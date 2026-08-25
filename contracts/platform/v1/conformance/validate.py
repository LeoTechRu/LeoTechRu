#!/usr/bin/env python3
"""Offline schema, fixture, JCS, URI-profile and semantic conformance checks."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
VECTORS_PATH = ROOT / "conformance" / "vectors.json"
URI_PROFILE_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.profile.json"
URI_VECTORS_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.vectors.json"
SCHEMA_SET_PATH = ROOT / "schema-set.json"
DIGESTS_PATH = ROOT / "conformance" / "digests.json"
SAFE_INTEGER = 9007199254740991
URI_PROFILE_ID = "bridge-oauth-registration-uri/v1"
ROOT_SIGNER_IDS = {"root.one", "root.two", "root.three"}
ROOT_KEY_FINGERPRINTS = {
    "root.one": "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925",
    "root.three": "7837bcfa947697ca65738dec250cbe22f3ee721bae49b3e7602dc2fbcd573f6e",
    "root.two": "37d171c864533cb2a2a1e63bd901ed3857c07f44f6e9be28010da8e5fc667ecb",
}

EXPECTED_SCHEMAS = {
    "urn:intdata:schema:module-manifest:v1": "schemas/module-manifest.schema.json",
    "urn:intdata:schema:installation-manifest:v1": "schemas/installation-manifest.schema.json",
    "urn:intdata:schema:registry-snapshot:v1": "schemas/registry-snapshot.schema.json",
    "urn:intdata:schema:resolver-input:v1": "schemas/resolver-input.schema.json",
    "urn:intdata:schema:resolver-result:v1": "schemas/resolver-result.schema.json",
    "urn:intdata:schema:installation-lock:v1": "schemas/installation-lock.schema.json",
    "urn:intdata:schema:release-manifest:v1": "schemas/release-manifest.schema.json",
    "urn:intdata:schema:signature-envelope:v1": "schemas/signature-envelope.schema.json",
    "urn:intdata:schema:trust-bundle:v1": "schemas/trust-bundle.schema.json",
    "urn:intdata:schema:scan-attestation:v1": "schemas/scan-attestation.schema.json",
    "urn:intdata:schema:bridge-oauth-registration-approval-receipt:v1": (
        "schemas/bridge-oauth-registration-approval-receipt.schema.json"
    ),
    "urn:intdata:schema:release-verification-key-set:v1": (
        "schemas/release-verification-key-set.schema.json"
    ),
    "urn:intdata:schema:platform-product-assertion:v1": (
        "schemas/platform-product-assertion.schema.json"
    ),
}

EXPECTED_SCHEMA_NAMES = {
    "urn:intdata:schema:module-manifest:v1": "ModuleManifestV1",
    "urn:intdata:schema:installation-manifest:v1": "InstallationManifestV1",
    "urn:intdata:schema:registry-snapshot:v1": "RegistrySnapshotV1",
    "urn:intdata:schema:resolver-input:v1": "ResolverInputV1",
    "urn:intdata:schema:resolver-result:v1": "ResolverResultV1",
    "urn:intdata:schema:installation-lock:v1": "InstallationLockV1",
    "urn:intdata:schema:release-manifest:v1": "ReleaseManifestV1",
    "urn:intdata:schema:signature-envelope:v1": "SignatureEnvelopeV1",
    "urn:intdata:schema:trust-bundle:v1": "TrustBundleV1",
    "urn:intdata:schema:scan-attestation:v1": "ScanAttestationV1",
    "urn:intdata:schema:bridge-oauth-registration-approval-receipt:v1": (
        "BridgeOAuthRegistrationApprovalReceiptV1"
    ),
    "urn:intdata:schema:release-verification-key-set:v1": (
        "ReleaseVerificationKeySetV1"
    ),
    "urn:intdata:schema:platform-product-assertion:v1": "PlatformProductAssertionV1",
}


class ConformanceError(ValueError):
    """Closed conformance failure with a stable reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class DuplicateKeyError(ConformanceError):
    def __init__(self, key: str) -> None:
        super().__init__("parse", f"duplicate key {key!r}")


class FloatRejected(ConformanceError):
    def __init__(self, value: str) -> None:
        super().__init__("number-policy", f"floating value {value!r}")


def _pairs_no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_float(value: str) -> Any:
    raise FloatRejected(value)


def _reject_constant(value: str) -> Any:
    raise ConformanceError("parse", f"non-JSON constant {value!r}")


def _assert_unicode_and_numbers(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ConformanceError("unicode-policy", "lone surrogate")
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int):
        if abs(value) > SAFE_INTEGER:
            raise ConformanceError("integer-policy", "unsafe integer")
    elif isinstance(value, float):
        raise ConformanceError("number-policy", "floating value")
    elif isinstance(value, list):
        for item in value:
            _assert_unicode_and_numbers(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_unicode_and_numbers(key)
            _assert_unicode_and_numbers(item)
    else:
        raise ConformanceError("parse", f"unsupported JSON value {type(value)!r}")


def strict_parse(raw: bytes) -> Any:
    if raw.startswith(b"\xef\xbb\xbf") or raw != raw.strip(b" \t\r\n"):
        raise ConformanceError("parse", "BOM or outer whitespace")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise ConformanceError("parse", "invalid UTF-8") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except ConformanceError:
        raise
    except json.JSONDecodeError as error:
        raise ConformanceError("parse", "invalid JSON") from error
    _assert_unicode_and_numbers(value)
    return value


def load_source_json(path: Path, enforce_data_policy: bool = True) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ConformanceError("parse", f"BOM in {path}")
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConformanceError("parse", f"invalid source JSON {path}") from error
    if enforce_data_policy:
        _assert_unicode_and_numbers(value)
    return value


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def jcs_canonical(value: Any) -> bytes:
    _assert_unicode_and_numbers(value)
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, int):
        return str(value).encode("ascii")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if isinstance(value, list):
        return b"[" + b",".join(jcs_canonical(item) for item in value) + b"]"
    if isinstance(value, dict):
        members = []
        for key in sorted(value, key=_utf16_sort_key):
            members.append(jcs_canonical(key) + b":" + jcs_canonical(value[key]))
        return b"{" + b",".join(members) + b"}"
    raise ConformanceError("canonicalization", "unsupported value")


def _schema_registry() -> tuple[dict[str, Any], Registry]:
    schemas: dict[str, Any] = {}
    actual_files = {
        path.relative_to(ROOT).as_posix() for path in SCHEMA_DIR.glob("*.schema.json")
    }
    if actual_files != set(EXPECTED_SCHEMAS.values()):
        raise ConformanceError("schema-set", "unknown, missing or extra schema file")
    for schema_id, relative in EXPECTED_SCHEMAS.items():
        schema = load_source_json(ROOT / relative)
        if schema.get("$id") != schema_id:
            raise ConformanceError("schema-set", f"$id mismatch for {relative}")
        Draft202012Validator.check_schema(schema)
        schemas[schema_id] = schema
    registry = Registry().with_resources(
        (schema_id, Resource.from_contents(schema))
        for schema_id, schema in schemas.items()
    )
    return schemas, registry


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ConformanceError("schema-set", f"closed {label}")
    return value


def validate_schema_set(schemas: dict[str, Any]) -> None:
    schema_set = _require_exact_keys(
        load_source_json(SCHEMA_SET_PATH),
        {"schema_set_version", "draft", "schemas", "profiles", "vectors"},
        "registry",
    )
    if (
        schema_set.get("schema_set_version") != "1.0.0"
        or schema_set.get("draft") != "https://json-schema.org/draft/2020-12/schema"
    ):
        raise ConformanceError("schema-set", "wrong registry version or draft")
    entries = schema_set.get("schemas")
    if not isinstance(entries, list) or len(entries) != len(EXPECTED_SCHEMAS):
        raise ConformanceError("schema-set", "wrong schema count")
    seen: set[str] = set()
    for raw_entry in entries:
        entry = _require_exact_keys(
            raw_entry, {"name", "version", "id", "filename", "sha256"}, "schema entry"
        )
        schema_id = entry.get("id")
        if schema_id in seen or schema_id not in EXPECTED_SCHEMAS:
            raise ConformanceError("schema-set", "duplicate or unknown schema id")
        seen.add(schema_id)
        if (
            entry.get("name") != EXPECTED_SCHEMA_NAMES[schema_id]
            or entry.get("version") != "v1"
            or entry.get("filename") != EXPECTED_SCHEMAS[schema_id]
        ):
            raise ConformanceError("schema-set", f"metadata mismatch for {schema_id}")
        raw = (ROOT / entry["filename"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise ConformanceError("schema-set", f"hash mismatch for {schema_id}")
    if seen != set(schemas):
        raise ConformanceError("schema-set", "missing schema id")
    profiles = schema_set.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise ConformanceError("schema-set", "wrong profile count")
    profile = _require_exact_keys(
        profiles[0],
        {
            "id",
            "version",
            "filename",
            "sha256",
            "vectors_filename",
            "vectors_sha256",
        },
        "profile entry",
    )
    expected_profile = {
        "id": URI_PROFILE_ID,
        "version": "v1",
        "filename": URI_PROFILE_PATH.relative_to(ROOT).as_posix(),
        "vectors_filename": URI_VECTORS_PATH.relative_to(ROOT).as_posix(),
    }
    for key, value in expected_profile.items():
        if profile.get(key) != value:
            raise ConformanceError("schema-set", f"profile {key} mismatch")
    if hashlib.sha256(URI_PROFILE_PATH.read_bytes()).hexdigest() != profile.get("sha256"):
        raise ConformanceError("schema-set", "profile hash mismatch")
    if hashlib.sha256(URI_VECTORS_PATH.read_bytes()).hexdigest() != profile.get(
        "vectors_sha256"
    ):
        raise ConformanceError("schema-set", "profile vectors hash mismatch")
    vectors = schema_set.get("vectors")
    if not isinstance(vectors, list) or len(vectors) != 1:
        raise ConformanceError("schema-set", "conformance vector linkage mismatch")
    vector = _require_exact_keys(
        vectors[0], {"id", "version", "filename", "sha256"}, "vector entry"
    )
    if vector != {
        "id": "platform-v1-conformance",
        "version": "1.0.0",
        "filename": "conformance/vectors.json",
        "sha256": hashlib.sha256(VECTORS_PATH.read_bytes()).hexdigest(),
    }:
        raise ConformanceError("schema-set", "conformance vector linkage mismatch")


def validate_priority_digests() -> int:
    digest_set = load_source_json(DIGESTS_PATH)
    if (
        digest_set.get("digest_set_version") != "1.0.0"
        or digest_set.get("algorithm") != "sha256"
    ):
        raise ConformanceError("digest-set", "metadata")
    artifacts = digest_set.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise ConformanceError("digest-set", "artifact count")
    paths = [entry["path"] for entry in artifacts]
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")):
        raise ConformanceError("digest-set", "path order")
    lines = []
    for entry in artifacts:
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ConformanceError("digest-set", entry["path"])
        lines.append(f"{actual}  {entry['path']}\n")
    manifest = "".join(lines).encode("utf-8")
    if manifest.hex() != digest_set["aggregate_manifest_utf8_hex"]:
        raise ConformanceError("digest-set", "aggregate bytes")
    if hashlib.sha256(manifest).hexdigest() != digest_set["aggregate_sha256"]:
        raise ConformanceError("digest-set", "aggregate digest")
    return len(artifacts)


def _validator(
    schema_id: str, schemas: dict[str, Any], registry: Registry
) -> Draft202012Validator:
    return Draft202012Validator(
        schemas[schema_id], registry=registry, format_checker=FormatChecker()
    )


def _apply_mutation(document: Any, mutation: dict[str, Any]) -> None:
    tokens = [
        token.replace("~1", "/").replace("~0", "~")
        for token in mutation["pointer"].split("/")[1:]
    ]
    target = document
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    last = tokens[-1]
    if mutation["operation"] == "remove":
        if isinstance(target, list):
            del target[int(last)]
        else:
            del target[last]
        return
    if mutation["operation"] not in {"replace", "add"}:
        raise ConformanceError("vector", "unsupported mutation")
    if isinstance(target, list):
        target[int(last)] = mutation["value"]
    else:
        target[last] = mutation["value"]


def validate_keyset_semantics(payload: dict[str, Any], context: dict[str, Any]) -> None:
    if context.get("pae_length_bytes", 0) > 262144:
        raise ConformanceError("pae_size")
    if (
        payload["bootstrap_root_set_digest"]
        != context["pinned_bootstrap_root_set_digest"]
    ):
        raise ConformanceError("bootstrap_pin")
    current_revision = context["current_revision"]
    if payload["revision"] != current_revision + 1:
        raise ConformanceError("revision")
    if current_revision == 0:
        if payload["previous_digest"] is not None:
            raise ConformanceError("previous_digest")
    elif payload["previous_digest"] != "sha256:" + context["current_digest"]:
        raise ConformanceError("previous_digest")
    admitted = {
        signer.get("public_key_sha256", ROOT_KEY_FINGERPRINTS[signer["key_id"]])
        for signer in context["root_signers"]
        if signer.get("role") == "release.trust.root"
        and signer.get("key_id") in ROOT_SIGNER_IDS
        and signer.get(
            "public_key_sha256", ROOT_KEY_FINGERPRINTS[signer["key_id"]]
        )
        == ROOT_KEY_FINGERPRINTS[signer["key_id"]]
    }
    if len(admitted) < 2:
        raise ConformanceError("root_quorum")
    key_ids = [key["key_id"] for key in payload["keys"]]
    if len(key_ids) != len(set(key_ids)):
        raise ConformanceError("duplicate_key_id")
    if key_ids != sorted(key_ids, key=lambda item: item.encode("utf-8")):
        raise ConformanceError("key_order")
    key_fingerprints = []
    for key in payload["keys"]:
        try:
            public_key = base64.b64decode(key["public_key_base64"], validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ConformanceError("online_key") from error
        fingerprint = hashlib.sha256(public_key).hexdigest()
        if fingerprint in ROOT_KEY_FINGERPRINTS.values():
            raise ConformanceError("root_online_alias")
        key_fingerprints.append(fingerprint)
    if len(key_fingerprints) != len(set(key_fingerprints)):
        raise ConformanceError("online_key_alias")
    allowed_transitions = {
        "active": {"active", "retired", "revoked"},
        "retired": {"retired", "revoked"},
        "revoked": {"revoked"},
    }
    current_states = context.get("current_key_states", {})
    for key in payload["keys"]:
        if key["valid_from"] >= key["valid_until"]:
            raise ConformanceError("lifecycle_time")
        if key["retired_at"] is not None and not (
            key["valid_from"] <= key["retired_at"] <= key["valid_until"]
        ):
            raise ConformanceError("lifecycle_time")
        if key["revoked_at"] is not None and not (
            key["valid_from"] <= key["revoked_at"] <= key["valid_until"]
        ):
            raise ConformanceError("lifecycle_time")
        if (
            key["retired_at"] is not None
            and key["revoked_at"] is not None
            and key["retired_at"] > key["revoked_at"]
        ):
            raise ConformanceError("lifecycle_time")
        previous = current_states.get(key["key_id"])
        if previous is not None and key["state"] not in allowed_transitions[previous]:
            raise ConformanceError("key_resurrection")
    current_keys = context.get("current_keys")
    if current_keys is not None:
        next_by_id = {key["key_id"]: key for key in payload["keys"]}
        for current in current_keys:
            candidate = next_by_id.get(current["key_id"])
            if candidate is None:
                raise ConformanceError("key_deletion")
            for immutable in ("role", "algorithm", "public_key_base64", "valid_from"):
                if candidate[immutable] != current[immutable]:
                    raise ConformanceError("key_identity")
    verification = context.get("verification")
    if verification is not None:
        selected = next(
            (key for key in payload["keys"] if key["key_id"] == verification["key_id"]),
            None,
        )
        if selected is None:
            raise ConformanceError("verification_key")
        if selected["state"] == "revoked":
            raise ConformanceError("revoked_key")
        signed_at = verification["signed_at"]
        if selected["state"] == "retired" and signed_at > selected["retired_at"]:
            raise ConformanceError("retired_cutoff")
        if not selected["valid_from"] <= signed_at <= selected["valid_until"]:
            raise ConformanceError("key_validity")


def validate_bootstrap_root_set(payload: dict[str, Any]) -> None:
    if set(payload) != {"schema_version", "role", "threshold", "keys"}:
        raise ConformanceError("root_shape")
    if (
        payload["schema_version"] != 1
        or isinstance(payload["schema_version"], bool)
        or payload["role"] != "release.trust.root"
        or payload["threshold"] != 2
        or isinstance(payload["threshold"], bool)
    ):
        raise ConformanceError("root_shape")
    keys = payload["keys"]
    if not isinstance(keys, list) or len(keys) != 3:
        raise ConformanceError("root_keys")
    key_ids = [key.get("key_id") for key in keys if isinstance(key, dict)]
    if (
        len(key_ids) != 3
        or len(set(key_ids)) != 3
        or key_ids != sorted(key_ids, key=lambda item: item.encode("utf-8"))
    ):
        raise ConformanceError("root_keys")
    public_fingerprints: list[str] = []
    for key in keys:
        if set(key) != {"key_id", "algorithm", "public_key_base64"}:
            raise ConformanceError("root_key")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", key["key_id"]):
            raise ConformanceError("root_key")
        if key["algorithm"] != "Ed25519":
            raise ConformanceError("root_key")
        try:
            public_key = base64.b64decode(key["public_key_base64"], validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ConformanceError("root_key") from error
        if len(public_key) != 32 or not re.fullmatch(
            r"[A-Za-z0-9+/]{43}=", key["public_key_base64"]
        ):
            raise ConformanceError("root_key")
        public_fingerprints.append(hashlib.sha256(public_key).hexdigest())
    if len(public_fingerprints) != len(set(public_fingerprints)):
        raise ConformanceError("root_keys")


def check_strict_vectors(vectors: dict[str, Any]) -> int:
    checked = 0
    for vector in vectors["strict_json"]:
        expected = vector["expected"]
        try:
            document = strict_parse(bytes.fromhex(vector["input_utf8_hex"]))
            canonical = jcs_canonical(document)
        except ConformanceError as error:
            if expected["ok"] or error.reason != expected["stage"]:
                raise ConformanceError("vector", f"{vector['name']}: {error}") from error
        else:
            if not expected["ok"]:
                raise ConformanceError("vector", f"{vector['name']} unexpectedly passed")
            if canonical.hex() != expected["canonical_utf8_hex"]:
                raise ConformanceError("vector", f"{vector['name']} canonical bytes")
            if hashlib.sha256(canonical).hexdigest() != expected["canonical_sha256"]:
                raise ConformanceError("vector", f"{vector['name']} digest")
        checked += 1
    return checked


def _load_conformance_module(filename: str, name: str) -> Any:
    path = ROOT / "conformance" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ConformanceError("delegated-validator", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_delegated_vector_sets(vectors: dict[str, Any]) -> dict[str, int]:
    expected = [
        (
            "urn:intdata:conformance:platform-product-assertion:v1",
            "conformance/platform-product-assertion-v1.vectors.json",
            "6517584d65b3c8bcb7be1b50e0de8806a199f20c7f290f2986a7f08d71b5fa46",
            "conformance/terminal-dependency-digests.json",
            "000e868d2b972d8ad11af021f7df052fbf81fb3d60f09ed1373ed114e273a9e4",
        ),
        (
            "urn:intdata:conformance:bridge-oauth-registration-uri:v1",
            "conformance/bridge-oauth-registration-uri-v1.vectors.json",
            "2712a642ff85abf7e7caac42123afe01639413963bb5ca92c667dcc735c37c89",
            "conformance/terminal-dependency-digests.json",
            "000e868d2b972d8ad11af021f7df052fbf81fb3d60f09ed1373ed114e273a9e4",
        ),
        (
            "urn:intdata:conformance:bridge-oauth-registration-approval-receipt:v1",
            "conformance/bridge-oauth-registration-approval-receipt-v1.vectors.json",
            "477284f0d5f9254fc7413e5aeade5c0c6abde933c185b2105aa46a5cb9073727",
            "conformance/approval-receipt-digests.json",
            "56a86537f25d03598169fa65e09ca75c9e845504873e8a7e96cea77d49b9a6e5",
        ),
    ]
    entries = vectors.get("delegated_vector_sets")
    actual = [
        (
            entry.get("id"),
            entry.get("vectors_path"),
            entry.get("vectors_sha256"),
            entry.get("digest_manifest_path"),
            entry.get("digest_manifest_sha256"),
        )
        for entry in entries or []
    ]
    if actual != expected:
        raise ConformanceError("delegated-vectors", "closed index")
    for _, vector_path, vector_sha, manifest_path, manifest_sha in expected:
        if hashlib.sha256((ROOT / vector_path).read_bytes()).hexdigest() != vector_sha:
            raise ConformanceError("delegated-vectors", vector_path)
        if hashlib.sha256((ROOT / manifest_path).read_bytes()).hexdigest() != manifest_sha:
            raise ConformanceError("delegated-vectors", manifest_path)
    terminal = _load_conformance_module(
        "validate-terminal-dependencies.py", "intdata_terminal_dependencies"
    )
    receipt = _load_conformance_module(
        "validate-approval-receipt.py", "intdata_approval_receipt"
    )
    terminal_checked = terminal.run()
    positives, adverses = receipt.validate_vectors()
    return {
        "delegated_vector_sets": len(expected),
        "platform_assertion_vectors": terminal_checked["ppa_vectors"],
        "uri_vectors": terminal_checked["uri_vectors"],
        "approval_receipt_positive_vectors": positives,
        "approval_receipt_adverse_vectors": adverses,
        "delegated_artifact_digests": (
            terminal_checked["ppa_artifact_digests"]
            + terminal_checked["terminal_artifact_digests"]
            + receipt.validate_digests()
        ),
    }


def validate_release_manifest_semantics(
    manifest: dict[str, Any], context: dict[str, Any]
) -> None:
    if manifest["source_commit"] != manifest["source"]["commit"]:
        raise ConformanceError("source_commit")
    modules = manifest["modules"]
    if len(modules) != 1 or modules[0]["module_id"] != manifest["module_id"]:
        raise ConformanceError("module_binding")
    for field in (
        "producer_id",
        "module_id",
        "installation_lock_digest",
        "source_commit",
        "release_id",
    ):
        if manifest[field] != context[field]:
            raise ConformanceError(f"{field}_binding")
    if manifest["signature_policy"]["role"] != "intdata.release-manifest.v1":
        raise ConformanceError("role")


def validate_resolver_result_semantics(
    result: dict[str, Any], resolver_input: dict[str, Any]
) -> None:
    for document_field, digest_field in (
        ("installation", "installation_sha256"),
        ("registry_snapshot", "registry_snapshot_sha256"),
    ):
        actual_digest = hashlib.sha256(
            jcs_canonical(resolver_input[document_field])
        ).hexdigest()
        if resolver_input[digest_field] != actual_digest:
            raise ConformanceError("resolver_input_digest", document_field)
    if result["status"] != "resolved":
        return
    validate_registry_signer_semantics(resolver_input["registry_snapshot"])
    lock = result["lock"]
    expected_bindings = {
        "installation_id": resolver_input["installation"]["installation_id"],
        "installation_revision": resolver_input["installation"]["revision"],
        "installation_sha256": resolver_input["installation_sha256"],
        "registry_id": resolver_input["registry_snapshot"]["registry_id"],
        "registry_version": resolver_input["registry_snapshot"]["version"],
        "registry_sha256": resolver_input["registry_snapshot_sha256"],
        "resolver_version": resolver_input["resolver_version"],
        "solver_policy_version": resolver_input["solver_policy_version"],
        "policy_input_sha256": resolver_input["policy_input_sha256"],
    }
    actual_bindings = {
        "installation_id": lock["installation"]["installation_id"],
        "installation_revision": lock["installation"]["revision"],
        "installation_sha256": lock["installation"]["sha256"],
        "registry_id": lock["registry_snapshot"]["registry_id"],
        "registry_version": lock["registry_snapshot"]["version"],
        "registry_sha256": lock["registry_snapshot"]["sha256"],
        "resolver_version": lock["resolver_version"],
        "solver_policy_version": lock["solver_policy_version"],
        "policy_input_sha256": lock["policy_input_sha256"],
    }
    for field, expected in expected_bindings.items():
        if actual_bindings[field] != expected:
            raise ConformanceError("resolver_input_binding", field)
    registry_modules: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in resolver_input["registry_snapshot"]["modules"]:
        key = (entry["module"]["module_id"], entry["module"]["version"])
        if key in registry_modules:
            raise ConformanceError("registry_module_binding", "duplicate registry module")
        registry_modules[key] = entry
    resolved_keys: set[tuple[str, str]] = set()
    resolved_manifests: dict[str, dict[str, Any]] = {}
    for resolved in lock["resolved_modules"]:
        key = (resolved["module_id"], resolved["version"])
        if key in resolved_keys:
            raise ConformanceError("registry_module_binding", "duplicate resolved module")
        resolved_keys.add(key)
        registry_entry = registry_modules.get(key)
        if registry_entry is None or any(
            resolved[field] != registry_entry[field]
            for field in (
                "manifest_sha256",
                "release_manifest_sha256",
                "signature_envelope_sha256",
            )
        ):
            raise ConformanceError("registry_module_binding", resolved["module_id"])
        if resolved["module_id"] in resolved_manifests:
            raise ConformanceError("registry_module_binding", "multiple resolved versions")
        resolved_manifests[resolved["module_id"]] = registry_entry["module"]
    capability_ids: set[str] = set()
    for binding in lock["capability_bindings"]:
        capability_id = binding["capability_id"]
        if capability_id in capability_ids:
            raise ConformanceError("capability_binding", "duplicate capability")
        capability_ids.add(capability_id)
        manifest = resolved_manifests.get(binding["provider_module_id"])
        if (
            manifest is None
            or binding["provider_version"] != manifest["version"]
            or capability_id
            not in {
                provided["capability_id"]
                for provided in manifest["capabilities"]["provides"]
            }
        ):
            raise ConformanceError("capability_binding", capability_id)
    artifact_keys: set[tuple[str, str]] = set()
    for binding in lock["artifact_bindings"]:
        key = (binding["module_id"], binding["artifact_id"])
        if key in artifact_keys:
            raise ConformanceError("artifact_binding", "duplicate artifact")
        artifact_keys.add(key)
        manifest = resolved_manifests.get(binding["module_id"])
        if manifest is None:
            raise ConformanceError("artifact_binding", binding["module_id"])
        artifact = next(
            (
                candidate
                for candidate in manifest["artifacts"]
                if candidate["artifact_id"] == binding["artifact_id"]
            ),
            None,
        )
        if artifact is None or any(
            binding[field] != artifact[field] for field in ("sha256", "size_bytes")
        ):
            raise ConformanceError("artifact_binding", binding["artifact_id"])
    route_keys: set[tuple[str, str]] = set()
    for binding in lock["route_bindings"]:
        key = (binding["module_id"], binding["route_id"])
        if key in route_keys:
            raise ConformanceError("route_binding", "duplicate route")
        route_keys.add(key)
        manifest = resolved_manifests.get(binding["module_id"])
        if manifest is None:
            raise ConformanceError("route_binding", binding["module_id"])
        route = next(
            (
                candidate
                for candidate in manifest["routes"]
                if candidate["route_id"] == binding["route_id"]
            ),
            None,
        )
        if route is None or any(
            binding[field] != route[field]
            for field in ("origin", "path", "runtime_unit_id")
        ):
            raise ConformanceError("route_binding", binding["route_id"])
    lock_bytes = jcs_canonical(result["lock"])
    actual = hashlib.sha256(lock_bytes).hexdigest()
    if result["lock_sha256"] != actual:
        raise ConformanceError("lock_digest")
    envelope = result["acceptance_signature"]["envelope"]
    if envelope["payloadType"] != "application/vnd.intdata.installation-lock.v1+json":
        raise ConformanceError("acceptance_payload_type")
    try:
        signed_payload = base64.b64decode(
            envelope["payload"], validate=True
        )
    except (ValueError, binascii.Error) as error:
        raise ConformanceError("acceptance_payload") from error
    if signed_payload != lock_bytes:
        raise ConformanceError("acceptance_payload")


def validate_registry_signer_semantics(snapshot: dict[str, Any]) -> None:
    expected_roles = ["installation-actor", "module", "registry", "scan"]
    entries = snapshot["accepted_signers"]
    roles = [entry["role"] for entry in entries]
    if roles != expected_roles:
        raise ConformanceError("accepted_signer_roles")
    for entry in entries:
        key_ids = entry["key_ids"]
        if key_ids != sorted(set(key_ids), key=lambda item: item.encode("utf-8")):
            raise ConformanceError("accepted_signer_key_ids")
    for entry in snapshot["modules"]:
        manifest_sha256 = hashlib.sha256(jcs_canonical(entry["module"])).hexdigest()
        if entry["manifest_sha256"] != manifest_sha256:
            raise ConformanceError("registry_module_digest")


def run() -> dict[str, int]:
    schemas, registry = _schema_registry()
    validate_schema_set(schemas)
    vectors = load_source_json(VECTORS_PATH, enforce_data_policy=False)
    resolver_input = load_source_json(ROOT / "fixtures/valid/resolver-input.json")
    schema_count = 0
    resolver_result_count = 0
    for fixture in vectors["schema_fixtures"]:
        document = load_source_json(ROOT / fixture["path"])
        errors = list(
            _validator(fixture["schema_id"], schemas, registry).iter_errors(document)
        )
        if bool(errors) == fixture["valid"]:
            raise ConformanceError("fixture", fixture["path"])
        if (
            fixture["schema_id"] == "urn:intdata:schema:resolver-result:v1"
            and not errors
        ):
            validate_resolver_result_semantics(document, resolver_input)
            resolver_result_count += 1
        schema_count += 1
    mutation_count = 0
    for vector in vectors["schema_mutations"]:
        document = copy.deepcopy(load_source_json(ROOT / vector["base_fixture"]))
        _apply_mutation(document, vector["mutation"])
        expected = vector["expected"]
        try:
            _assert_unicode_and_numbers(document)
        except ConformanceError as error:
            if error.reason != expected["stage"]:
                raise ConformanceError("mutation", vector["name"]) from error
            mutation_count += 1
            continue
        errors = list(
            _validator(vector["schema_id"], schemas, registry).iter_errors(document)
        )
        if errors:
            if expected["stage"] != "schema":
                raise ConformanceError("mutation", vector["name"])
            mutation_count += 1
            continue
        raise ConformanceError(
            "mutation", f"{vector['name']} unexpectedly passed schema"
        )
    bootstrap = vectors["release_bootstrap_root_set"]
    bootstrap_payload = bootstrap["payload"]
    validate_bootstrap_root_set(bootstrap_payload)
    bootstrap_canonical = jcs_canonical(bootstrap_payload)
    if bootstrap_canonical.hex() != bootstrap["canonical_utf8_hex"]:
        raise ConformanceError("bootstrap-root-vector", "canonical bytes")
    if hashlib.sha256(bootstrap_canonical).hexdigest() != bootstrap["sha256"]:
        raise ConformanceError("bootstrap-root-vector", "digest")
    bootstrap_adverse_count = 0
    for adverse in bootstrap["adverse"]:
        candidate = copy.deepcopy(bootstrap_payload)
        _apply_mutation(candidate, adverse["mutation"])
        try:
            validate_bootstrap_root_set(candidate)
        except ConformanceError as error:
            if error.reason != adverse["reason"]:
                raise ConformanceError(
                    "bootstrap-root-vector", f"{adverse['name']}: {error}"
                ) from error
        else:
            raise ConformanceError(
                "bootstrap-root-vector", f"{adverse['name']} unexpectedly passed"
            )
        bootstrap_adverse_count += 1
    keyset_count = 0
    for vector in vectors["release_keyset_semantics"]:
        payload = copy.deepcopy(load_source_json(ROOT / vector["fixture"]))
        if "mutation" in vector:
            _apply_mutation(payload, vector["mutation"])
        expected = vector["expected"]
        try:
            validate_keyset_semantics(payload, vector["context"])
        except ConformanceError as error:
            if expected["valid"] or error.reason != expected["reason"]:
                raise ConformanceError(
                    "keyset-vector", f"{vector['name']}: {error}"
                ) from error
        else:
            if not expected["valid"]:
                raise ConformanceError(
                    "keyset-vector", f"{vector['name']} unexpectedly passed"
                )
        keyset_count += 1
    release_manifest_count = 0
    release_schema_id = "urn:intdata:schema:release-manifest:v1"
    for vector in vectors["release_manifest_semantics"]:
        document = copy.deepcopy(load_source_json(ROOT / vector["base_fixture"]))
        if "mutation" in vector:
            _apply_mutation(document, vector["mutation"])
        expected = vector["expected"]
        errors = list(
            _validator(release_schema_id, schemas, registry).iter_errors(document)
        )
        if errors:
            if expected["stage"] != "schema":
                raise ConformanceError("release-manifest-vector", vector["name"])
        else:
            try:
                validate_release_manifest_semantics(document, vector["context"])
            except ConformanceError as error:
                if expected["stage"] != "semantic" or error.reason != expected["reason"]:
                    raise ConformanceError(
                        "release-manifest-vector", f"{vector['name']}: {error}"
                    ) from error
            else:
                if expected["stage"] != "valid":
                    raise ConformanceError(
                        "release-manifest-vector",
                        f"{vector['name']} unexpectedly passed",
                    )
        release_manifest_count += 1
    registry_signer_count = 0
    registry_schema_id = "urn:intdata:schema:registry-snapshot:v1"
    for vector in vectors["registry_signer_semantics"]:
        document = copy.deepcopy(load_source_json(ROOT / vector["base_fixture"]))
        if "mutation" in vector:
            _apply_mutation(document, vector["mutation"])
        expected = vector["expected"]
        errors = list(
            _validator(registry_schema_id, schemas, registry).iter_errors(document)
        )
        if errors:
            if expected["stage"] != "schema":
                raise ConformanceError("registry-signer-vector", vector["name"])
        else:
            try:
                validate_registry_signer_semantics(document)
            except ConformanceError as error:
                if expected["stage"] != "semantic" or error.reason != expected["reason"]:
                    raise ConformanceError(
                        "registry-signer-vector", f"{vector['name']}: {error}"
                    ) from error
            else:
                if expected["stage"] != "valid":
                    raise ConformanceError(
                        "registry-signer-vector", f"{vector['name']} unexpectedly passed"
                    )
        registry_signer_count += 1
    checked = {
        "schemas": len(schemas),
        "schema_fixtures": schema_count,
        "schema_mutations": mutation_count,
        "strict_json_vectors": check_strict_vectors(vectors),
        "release_keyset_vectors": keyset_count,
        "bootstrap_root_vectors": bootstrap_adverse_count + 1,
        "release_manifest_vectors": release_manifest_count,
        "resolver_result_vectors": resolver_result_count,
        "registry_signer_vectors": registry_signer_count,
        "priority_artifact_digests": validate_priority_digests(),
    }
    checked.update(validate_delegated_vector_sets(vectors))
    return checked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps({"ok": True, "checked": run()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

