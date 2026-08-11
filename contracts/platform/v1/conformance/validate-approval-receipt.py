#!/usr/bin/env python3
"""Focused offline conformance validator for Bridge approval receipts (#889)."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "bridge-oauth-registration-approval-receipt.schema.json"
VECTOR_PATH = ROOT / "conformance" / "bridge-oauth-registration-approval-receipt-v1.vectors.json"
DIGEST_PATH = ROOT / "conformance" / "approval-receipt-digests.json"
URI_PROFILE_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.profile.json"
URI_VECTOR_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.vectors.json"
TERMINAL_VALIDATOR_PATH = ROOT / "conformance" / "validate-terminal-dependencies.py"
SCHEMA_ID = "urn:intdata:schema:bridge-oauth-registration-approval-receipt:v1"
VECTOR_ID = "urn:intdata:conformance:bridge-oauth-registration-approval-receipt:v1"
URI_PROFILE_ID = "bridge-oauth-registration-uri/v1"
CENTRAL_ISSUER = "https://bridge.intdata.pro/oauth"
CENTRAL_AUDIENCE = "https://api.intdata.pro/internal/platform-identity/v1/bridge/software-statements"
TRUST_ROLE = "bridge.oauth.registration-approval"
SAFE_INTEGER = 9007199254740991
ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
JTI_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
UUID7_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
SOFTWARE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
GRANT_TYPES = {"authorization_code", "urn:ietf:params:oauth:grant-type:device_code"}
AGGREGATE_ENCODING = "For each artifact in listed path order: lowercase SHA-256, two ASCII spaces, path, LF; SHA-256 the concatenated UTF-8 bytes."


class ConformanceError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def require_keys(value: Any, keys: set[str], where: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ConformanceError("closed-shape", where)


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or not raw.endswith(b"\n") or b"\r\n" in raw:
        raise ConformanceError("source-encoding", path.as_posix())

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ConformanceError("duplicate-key", key)
            result[key] = value
        return result

    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConformanceError("source-json", path.as_posix()) from error


def load_terminal_validator() -> Any:
    spec = importlib.util.spec_from_file_location("intdata_terminal_dependencies", TERMINAL_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ConformanceError("uri-validator-load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_integer_json(value: Any) -> None:
    if isinstance(value, float):
        raise ConformanceError("number-policy")
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > SAFE_INTEGER:
        raise ConformanceError("integer-policy")
    if isinstance(value, list):
        for item in value:
            assert_integer_json(item)
    elif isinstance(value, dict):
        for item in value.values():
            assert_integer_json(item)


def apply_mutation(document: Any, mutation: dict[str, Any]) -> None:
    operation = mutation.get("op")
    expected_keys = {"op", "pointer"} if operation == "remove" else {"op", "pointer", "value"}
    require_keys(mutation, expected_keys, "mutation")
    if operation not in {"add", "replace", "remove"}:
        raise ConformanceError("mutation-op")
    pointer = mutation["pointer"]
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ConformanceError("mutation-pointer")
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.split("/")[1:]]
    target = document
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    last = tokens[-1]
    if operation == "remove":
        if isinstance(target, list):
            del target[int(last)]
        else:
            del target[last]
    elif isinstance(target, list):
        target[int(last)] = mutation["value"]
    else:
        target[last] = mutation["value"]


def canonical_schema_reason(error: Any) -> str:
    tokens = [str(token).replace("~", "~0").replace("/", "~1") for token in error.absolute_path]
    pointer = "/" + "/".join(tokens) if tokens else "/"
    keyword = str(error.validator)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", keyword):
        raise ConformanceError("schema-keyword")
    return f"{pointer}#{keyword}"


def validate_context(context: Any) -> None:
    require_keys(
        context,
        {
            "mode",
            "authority_source",
            "expected_issuer",
            "expected_audience",
            "verifier_now",
            "clock_skew_seconds",
            "admitted_keys",
            "expected_projection",
            "request_jti",
            "workload_identity",
            "replay_rows",
            "admit_nondefault_redirect_port",
        },
        "verification-context",
    )
    if context["mode"] not in {"central", "lite"}:
        raise ConformanceError("mode")
    if not isinstance(context["expected_issuer"], str) or not isinstance(context["expected_audience"], str):
        raise ConformanceError("authority")
    if context["mode"] == "central":
        if context["authority_source"] != "central-profile" or context["expected_issuer"] != CENTRAL_ISSUER or context["expected_audience"] != CENTRAL_AUDIENCE:
            raise ConformanceError("central-authority-context")
    else:
        if context["authority_source"] != "active-InstallationLockV1":
            raise ConformanceError("lite-authority-source")
        if context["expected_issuer"] == CENTRAL_ISSUER or context["expected_audience"] == CENTRAL_AUDIENCE:
            raise ConformanceError("lite-central-fallback")
    now = context["verifier_now"]
    skew = context["clock_skew_seconds"]
    if isinstance(now, bool) or not isinstance(now, int) or not 0 <= now <= SAFE_INTEGER:
        raise ConformanceError("verifier-now")
    if isinstance(skew, bool) or not isinstance(skew, int) or not 0 <= skew <= 30:
        raise ConformanceError("clock-skew")
    if not isinstance(context["admit_nondefault_redirect_port"], bool):
        raise ConformanceError("redirect-port-policy")
    projection = context["expected_projection"]
    require_keys(projection, {"sub", "organization_id", "session_id", "membership_revision", "entitlement_revision"}, "projection")
    if not UUID_PATTERN.fullmatch(projection["sub"]) or not UUID_PATTERN.fullmatch(projection["organization_id"]):
        raise ConformanceError("projection-uuid")
    if not ID_PATTERN.fullmatch(projection["session_id"]):
        raise ConformanceError("projection-session")
    for name in ("membership_revision", "entitlement_revision"):
        value = projection[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= SAFE_INTEGER:
            raise ConformanceError("projection-revision")
    keys = context["admitted_keys"]
    if not isinstance(keys, list) or not 1 <= len(keys) <= 16:
        raise ConformanceError("admitted-keys-cardinality")
    kids: list[str] = []
    for key in keys:
        require_keys(key, {"kid", "role", "state"}, "admitted-key")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", key["kid"]):
            raise ConformanceError("admitted-kid")
        if key["role"] != TRUST_ROLE or key["state"] not in {"active", "retired", "revoked"}:
            raise ConformanceError("admitted-key-record")
        kids.append(key["kid"])
    if len(set(kids)) != len(kids):
        raise ConformanceError("duplicate-admitted-kid")
    if not isinstance(context["request_jti"], str) or not UUID7_PATTERN.fullmatch(context["request_jti"]):
        raise ConformanceError("request-jti")
    if context["workload_identity"] != "intdata-bridge":
        raise ConformanceError("workload-identity")
    rows = context["replay_rows"]
    if not isinstance(rows, list) or len(rows) > 64:
        raise ConformanceError("replay-rows-cardinality")
    row_keys = {"request_jti", "receipt_jti", "workload_identity", "organization_id", "registration_metadata_digest", "retention_until"}
    for row in rows:
        require_keys(row, row_keys, "replay-row")
        if not UUID7_PATTERN.fullmatch(row["request_jti"]) or not JTI_PATTERN.fullmatch(row["receipt_jti"]):
            raise ConformanceError("replay-row-jti")
        if row["workload_identity"] != "intdata-bridge" or not UUID_PATTERN.fullmatch(row["organization_id"]):
            raise ConformanceError("replay-row-binding")
        if not isinstance(row["registration_metadata_digest"], str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", row["registration_metadata_digest"]):
            raise ConformanceError("replay-row-digest")
        retention = row["retention_until"]
        if isinstance(retention, bool) or not isinstance(retention, int) or not 0 <= retention <= SAFE_INTEGER:
            raise ConformanceError("replay-row-retention")


def validate_header(header: Any, context: dict[str, Any]) -> None:
    require_keys(header, {"typ", "alg", "kid"}, "protected-header")
    if header["typ"] != "bridge-oauth-registration-approval+jwt":
        raise ConformanceError("typ")
    if header["alg"] != "ES256":
        raise ConformanceError("alg")
    kid = header["kid"]
    admitted = [key for key in context["admitted_keys"] if key["kid"] == kid]
    if len(admitted) != 1:
        raise ConformanceError("kid-not-admitted")
    if admitted[0]["role"] != TRUST_ROLE:
        raise ConformanceError("kid-role")
    if admitted[0]["state"] != "active":
        raise ConformanceError("kid-state")


def validate_metadata_shape(metadata: Any) -> None:
    require_keys(metadata, {"software_id", "client_name", "redirect_uris", "grant_types", "token_endpoint_auth_method", "scopes", "organization_id"}, "registration-metadata")
    if not isinstance(metadata["software_id"], str) or not SOFTWARE_ID_PATTERN.fullmatch(metadata["software_id"]):
        raise ConformanceError("software-id")
    client_name = metadata["client_name"]
    if not isinstance(client_name, str) or any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF for char in client_name):
        raise ConformanceError("client-name")
    try:
        client_name_bytes = client_name.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise ConformanceError("client-name") from error
    if not 1 <= len(client_name_bytes) <= 256:
        raise ConformanceError("client-name")
    if not UUID_PATTERN.fullmatch(metadata["organization_id"]):
        raise ConformanceError("metadata-organization")
    limits = {"redirect_uris": 16, "grant_types": 2, "scopes": 64}
    for field, maximum in limits.items():
        values = metadata[field]
        if not isinstance(values, list) or not 1 <= len(values) <= maximum or any(not isinstance(value, str) for value in values):
            raise ConformanceError(f"{field}-cardinality")
    if metadata["token_endpoint_auth_method"] != "none":
        raise ConformanceError("token-endpoint-auth-method")


def canonicalize_metadata(metadata: dict[str, Any], context: dict[str, Any], terminal: Any) -> dict[str, Any]:
    validate_metadata_shape(metadata)
    canonical = copy.deepcopy(metadata)
    try:
        canonical["redirect_uris"] = terminal.normalize_redirects(metadata["redirect_uris"], context["admit_nondefault_redirect_port"])
        if any(value not in GRANT_TYPES for value in metadata["grant_types"]):
            raise ConformanceError("token_grammar")
        if any(not 1 <= len(value.encode("ascii", "strict")) <= 128 or any(ord(char) < 0x21 or ord(char) > 0x7E for char in value) for value in metadata["scopes"]):
            raise ConformanceError("token_grammar")
        canonical["grant_types"] = sorted(set(metadata["grant_types"]), key=lambda item: item.encode("utf-8"))
        canonical["scopes"] = sorted(set(metadata["scopes"]), key=lambda item: item.encode("utf-8"))
    except terminal.ConformanceError as error:
        raise ConformanceError(error.reason) from error
    except UnicodeEncodeError as error:
        raise ConformanceError("token_grammar") from error
    return canonical


def request_uuid_timestamp(request_jti: str) -> int:
    return int(request_jti.replace("-", "")[:12], 16) // 1000


def validate_semantics(receipt: dict[str, Any], metadata: dict[str, Any], context: dict[str, Any], terminal: Any) -> bytes:
    claims = receipt["claims"]
    if claims["iss"] != context["expected_issuer"]:
        raise ConformanceError("issuer")
    if claims["aud"] != context["expected_audience"]:
        raise ConformanceError("audience")
    iat, nbf, exp = claims["iat"], claims["nbf"], claims["exp"]
    if not iat <= nbf < exp:
        raise ConformanceError("chronology")
    if exp > iat + 60:
        raise ConformanceError("ttl")
    now, skew = context["verifier_now"], context["clock_skew_seconds"]
    if iat > now + skew:
        raise ConformanceError("future-iat")
    if nbf > now + skew:
        raise ConformanceError("future-nbf")
    if exp <= now - skew:
        raise ConformanceError("expired")
    projection = context["expected_projection"]
    for field in projection:
        if claims[field] != projection[field]:
            raise ConformanceError(f"projection-{field.replace('_', '-')}")
    canonical = canonicalize_metadata(metadata, context, terminal)
    if canonical["organization_id"] != claims["organization_id"]:
        raise ConformanceError("metadata-organization-projection")
    canonical_bytes = terminal.jcs(canonical)
    if len(canonical_bytes) > 16384:
        raise ConformanceError("registration-metadata-byte-limit")
    digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    if claims["registration_metadata_digest"] != digest:
        raise ConformanceError("registration-metadata-digest")
    request_timestamp = request_uuid_timestamp(context["request_jti"])
    if request_timestamp < now - 300:
        raise ConformanceError("request-jti-stale")
    if request_timestamp > now + 30:
        raise ConformanceError("request-jti-future")
    expected_binding = {
        "request_jti": context["request_jti"],
        "receipt_jti": claims["jti"],
        "workload_identity": context["workload_identity"],
        "organization_id": claims["organization_id"],
        "registration_metadata_digest": digest,
        "retention_until": max(exp + 30, request_timestamp + 360),
    }
    for row in context["replay_rows"]:
        if row["request_jti"] == context["request_jti"] or row["receipt_jti"] == claims["jti"]:
            if row != expected_binding:
                raise ConformanceError("replay-binding-mismatch")
            raise ConformanceError("replayed-jti")
    return canonical_bytes


def evaluate(runtime: dict[str, Any], validator: Draft202012Validator, terminal: Any) -> tuple[str, str]:
    try:
        assert_integer_json(runtime)
    except ConformanceError as error:
        return "number-policy", error.reason
    try:
        validate_context(runtime["verification_context"])
    except (KeyError, TypeError, ConformanceError) as error:
        return "context", error.reason if isinstance(error, ConformanceError) else "closed-shape"
    try:
        validate_header(runtime["receipt"]["protected_header"], runtime["verification_context"])
    except (KeyError, TypeError, ConformanceError) as error:
        return "header", error.reason if isinstance(error, ConformanceError) else "closed-shape"
    errors = list(validator.iter_errors(runtime["receipt"]))
    if errors:
        return "schema", canonical_schema_reason(errors[0])
    try:
        validate_semantics(runtime["receipt"], runtime["registration_metadata_input"], runtime["verification_context"], terminal)
    except (KeyError, TypeError, ConformanceError) as error:
        return "semantic", error.reason if isinstance(error, ConformanceError) else "closed-shape"
    return "accepted", "accepted"


def validate_vectors() -> tuple[int, int]:
    terminal = load_terminal_validator()
    schema = load_json(SCHEMA_PATH)
    if schema.get("$id") != SCHEMA_ID:
        raise ConformanceError("schema-id")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    vectors = load_json(VECTOR_PATH)
    require_keys(vectors, {"vector_set_id", "version", "schema_id", "canonical_encoding", "dependencies", "contracts", "base", "positive_cases", "adverse_cases"}, "vectors")
    if vectors["vector_set_id"] != VECTOR_ID or vectors["version"] != "v1" or vectors["schema_id"] != SCHEMA_ID or vectors["canonical_encoding"] != "RFC8785-JCS-UTF-8-no-BOM-no-trailing-bytes":
        raise ConformanceError("vector-identity")
    dependencies = vectors["dependencies"]
    require_keys(dependencies, {"uri_profile_id", "uri_profile_path", "uri_profile_sha256", "uri_vector_path", "uri_vector_sha256"}, "dependencies")
    if dependencies != {
        "uri_profile_id": URI_PROFILE_ID,
        "uri_profile_path": "conformance/bridge-oauth-registration-uri-v1.profile.json",
        "uri_profile_sha256": hashlib.sha256(URI_PROFILE_PATH.read_bytes()).hexdigest(),
        "uri_vector_path": "conformance/bridge-oauth-registration-uri-v1.vectors.json",
        "uri_vector_sha256": hashlib.sha256(URI_VECTOR_PATH.read_bytes()).hexdigest(),
    }:
        raise ConformanceError("uri-dependency")
    contracts = vectors["contracts"]
    require_keys(contracts, {"protected_header", "central", "lite", "trusted_time", "registration_metadata", "request_jti", "single_use"}, "contracts")
    if contracts["protected_header"] != {"typ": "bridge-oauth-registration-approval+jwt", "alg": "ES256", "kid_trust_role": TRUST_ROLE}:
        raise ConformanceError("header-contract")
    if contracts["central"] != {"issuer": CENTRAL_ISSUER, "audience": CENTRAL_AUDIENCE}:
        raise ConformanceError("central-contract")
    if contracts["lite"] != {"authority_source": "active-InstallationLockV1", "substitutes": ["issuer", "audience"], "central_fallback": False}:
        raise ConformanceError("lite-contract")
    if contracts["trusted_time"] != {"numeric_date": "integer-non-boolean", "max_clock_skew_seconds": 30, "predicate": "iat <= nbf < exp <= iat + 60; iat <= now + skew; nbf <= now + skew; exp > now - skew"}:
        raise ConformanceError("time-contract")
    if contracts["registration_metadata"] != {
        "max_canonical_utf8_bytes": 16384,
        "software_id_pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        "client_name_utf8_bytes": [1, 256],
        "redirect_uris_count": [1, 16],
        "grant_types_count": [1, 2],
        "grant_types": ["authorization_code", "urn:ietf:params:oauth:grant-type:device_code"],
        "token_endpoint_auth_method": "none",
        "scopes_count": [1, 64],
        "scope_ascii_bytes": [1, 128],
        "array_order": "unsigned-utf8-ascending-after-canonicalize-deduplicate",
    }:
        raise ConformanceError("metadata-contract")
    if contracts["request_jti"] != {
        "format": "uuidv7",
        "max_age_seconds": 300,
        "max_future_skew_seconds": 30,
        "replay_binding": ["request_jti", "receipt_jti", "workload_identity", "organization_id", "registration_metadata_digest"],
        "retention": "max(receipt_exp+30,request_uuid_timestamp+360)",
    }:
        raise ConformanceError("request-jti-contract")
    if contracts["single_use"] != ["receipt_jti", "request_jti"]:
        raise ConformanceError("single-use-contract")
    base = vectors["base"]
    require_keys(base, {"receipt", "registration_metadata_input", "verification_context", "canonical_registration_metadata", "canonical_registration_metadata_utf8_hex", "canonical_registration_metadata_sha256"}, "base")
    canonical = canonicalize_metadata(base["registration_metadata_input"], base["verification_context"], terminal)
    canonical_bytes = terminal.jcs(canonical)
    if canonical != base["canonical_registration_metadata"] or canonical_bytes.hex() != base["canonical_registration_metadata_utf8_hex"] or hashlib.sha256(canonical_bytes).hexdigest() != base["canonical_registration_metadata_sha256"]:
        raise ConformanceError("base-metadata-canonicalization")
    if base["receipt"]["claims"]["registration_metadata_digest"] != "sha256:" + base["canonical_registration_metadata_sha256"]:
        raise ConformanceError("base-metadata-binding")
    positives, adverses = vectors["positive_cases"], vectors["adverse_cases"]
    if not isinstance(positives, list) or len(positives) != 4 or not isinstance(adverses, list) or len(adverses) != 67:
        raise ConformanceError("case-count")
    all_cases = positives + adverses
    names = [case.get("name") for case in all_cases if isinstance(case, dict)]
    if len(names) != 71 or any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ConformanceError("case-names")
    runtime_base = {key: copy.deepcopy(base[key]) for key in ("receipt", "registration_metadata_input", "verification_context")}
    checked_positive = 0
    for case in positives:
        require_keys(case, {"name", "mutations", "expected"}, "positive-case")
        if case["expected"] != {"valid": True}:
            raise ConformanceError("positive-expected", case["name"])
        runtime = copy.deepcopy(runtime_base)
        for mutation in case["mutations"]:
            apply_mutation(runtime, mutation)
        actual = evaluate(runtime, validator, terminal)
        if actual != ("accepted", "accepted"):
            raise ConformanceError("positive-case", f"{case['name']} got {actual[0]}/{actual[1]}")
        checked_positive += 1
    checked_adverse = 0
    for case in adverses:
        require_keys(case, {"name", "mutations", "expected"}, "adverse-case")
        require_keys(case["expected"], {"valid", "stage", "reason"}, "adverse-expected")
        if case["expected"]["valid"] is not False:
            raise ConformanceError("adverse-expected-valid", case["name"])
        runtime = copy.deepcopy(runtime_base)
        for mutation in case["mutations"]:
            apply_mutation(runtime, mutation)
        actual = evaluate(runtime, validator, terminal)
        expected = (case["expected"]["stage"], case["expected"]["reason"])
        if actual != expected:
            raise ConformanceError("adverse-case", f"{case['name']} got {actual[0]}/{actual[1]}")
        checked_adverse += 1
    oracle = copy.deepcopy(runtime_base)
    oracle["receipt"]["claims"]["__oracle_extra_claim"] = True
    if evaluate(oracle, validator, terminal) != ("schema", "/claims#additionalProperties"):
        raise ConformanceError("adverse-oracle")
    return checked_positive, checked_adverse


def validate_digests() -> int:
    manifest = load_json(DIGEST_PATH)
    require_keys(manifest, {"digest_set_id", "version", "algorithm", "canonical_encoding", "aggregate_encoding", "artifacts", "aggregate_manifest_utf8_hex", "aggregate_sha256"}, "digest-manifest")
    if manifest["digest_set_id"] != "urn:intdata:digest-set:bridge-oauth-registration-approval-receipt:v1" or manifest["version"] != "v1" or manifest["algorithm"] != "sha256" or manifest["canonical_encoding"] != "raw-file-bytes" or manifest["aggregate_encoding"] != AGGREGATE_ENCODING:
        raise ConformanceError("digest-metadata")
    expected = [
        (URI_PROFILE_ID, "uri-profile", "conformance/bridge-oauth-registration-uri-v1.profile.json"),
        (URI_PROFILE_ID, "uri-vectors", "conformance/bridge-oauth-registration-uri-v1.vectors.json"),
        (VECTOR_ID, "receipt-vectors", "conformance/bridge-oauth-registration-approval-receipt-v1.vectors.json"),
        ("urn:intdata:conformance-validator:bridge-oauth-registration-approval-receipt:v1", "validator", "conformance/validate-approval-receipt.py"),
        (SCHEMA_ID, "schema", "schemas/bridge-oauth-registration-approval-receipt.schema.json"),
    ]
    entries = manifest["artifacts"]
    if not isinstance(entries, list) or [(entry.get("artifact_id"), entry.get("artifact_kind"), entry.get("path")) for entry in entries] != expected:
        raise ConformanceError("digest-paths")
    lines: list[str] = []
    for entry in entries:
        require_keys(entry, {"artifact_id", "artifact_kind", "path", "sha256"}, "digest-entry")
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        if entry["sha256"] != actual:
            raise ConformanceError("digest-entry", entry["path"])
        lines.append(f"{actual}  {entry['path']}\n")
    aggregate_bytes = "".join(lines).encode("utf-8")
    if aggregate_bytes.hex() != manifest["aggregate_manifest_utf8_hex"] or hashlib.sha256(aggregate_bytes).hexdigest() != manifest["aggregate_sha256"]:
        raise ConformanceError("digest-aggregate")
    return len(entries)


def main() -> int:
    argparse.ArgumentParser().parse_args()
    positives, adverses = validate_vectors()
    checked = {"positive_vectors": positives, "adverse_vectors": adverses, "artifact_digests": validate_digests()}
    print(json.dumps({"ok": True, "checked": checked}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
