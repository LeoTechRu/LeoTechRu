"""Closed offline Draft 2020-12 schema registry."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from referencing.jsonschema import DRAFT202012

from ._json import (
    StrictJSONError,
    _validate_value,
    canonical_sha256,
    canonicalize,
    strict_loads,
)


def _validation_error_key(error: ValidationError) -> tuple[object, ...]:
    def path_key(path: Iterable[object]) -> tuple[tuple[str, str], ...]:
        return tuple((type(part).__name__, str(part)) for part in path)

    return (
        path_key(error.absolute_path),
        path_key(error.absolute_schema_path),
        str(error.validator),
        error.message,
    )

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_SET_VERSION = "1.0.0"
_SCHEMA_ID = re.compile(r"urn:intdata:schema:([a-z0-9]+(?:-[a-z0-9]+)*):v1\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SET_FIELDS = {"schema_set_version", "draft", "schemas", "profiles", "vectors"}
_ENTRY_FIELDS = {"name", "version", "id", "filename", "sha256"}
_PROFILE_FIELDS = {
    "id",
    "version",
    "filename",
    "sha256",
    "vectors_filename",
    "vectors_sha256",
}
_VECTOR_ENTRY_FIELDS = {"id", "version", "filename", "sha256"}
EXPECTED_SCHEMA_IDS = frozenset(
    {
        "urn:intdata:schema:module-manifest:v1",
        "urn:intdata:schema:installation-manifest:v1",
        "urn:intdata:schema:registry-snapshot:v1",
        "urn:intdata:schema:resolver-input:v1",
        "urn:intdata:schema:resolver-result:v1",
        "urn:intdata:schema:installation-lock:v1",
        "urn:intdata:schema:release-manifest:v1",
        "urn:intdata:schema:signature-envelope:v1",
        "urn:intdata:schema:trust-bundle:v1",
        "urn:intdata:schema:scan-attestation:v1",
        "urn:intdata:schema:bridge-oauth-registration-approval-receipt:v1",
        "urn:intdata:schema:release-verification-key-set:v1",
        "urn:intdata:schema:platform-product-assertion:v1",
    }
)
EXPECTED_PROFILE_ID = "bridge-oauth-registration-uri/v1"
EXPECTED_PROFILE_FILENAME = "conformance/bridge-oauth-registration-uri-v1.profile.json"
EXPECTED_PROFILE_VECTORS_FILENAME = (
    "conformance/bridge-oauth-registration-uri-v1.vectors.json"
)
EXPECTED_CONFORMANCE_VECTOR_ID = "platform-v1-conformance"
EXPECTED_CONFORMANCE_VECTOR_FILENAME = "conformance/vectors.json"
EXPECTED_SCHEMA_REGISTRY = {
    "urn:intdata:schema:module-manifest:v1": (
        "ModuleManifestV1",
        "schemas/module-manifest.schema.json",
    ),
    "urn:intdata:schema:installation-manifest:v1": (
        "InstallationManifestV1",
        "schemas/installation-manifest.schema.json",
    ),
    "urn:intdata:schema:registry-snapshot:v1": (
        "RegistrySnapshotV1",
        "schemas/registry-snapshot.schema.json",
    ),
    "urn:intdata:schema:resolver-input:v1": (
        "ResolverInputV1",
        "schemas/resolver-input.schema.json",
    ),
    "urn:intdata:schema:resolver-result:v1": (
        "ResolverResultV1",
        "schemas/resolver-result.schema.json",
    ),
    "urn:intdata:schema:installation-lock:v1": (
        "InstallationLockV1",
        "schemas/installation-lock.schema.json",
    ),
    "urn:intdata:schema:release-manifest:v1": (
        "ReleaseManifestV1",
        "schemas/release-manifest.schema.json",
    ),
    "urn:intdata:schema:signature-envelope:v1": (
        "SignatureEnvelopeV1",
        "schemas/signature-envelope.schema.json",
    ),
    "urn:intdata:schema:trust-bundle:v1": (
        "TrustBundleV1",
        "schemas/trust-bundle.schema.json",
    ),
    "urn:intdata:schema:scan-attestation:v1": (
        "ScanAttestationV1",
        "schemas/scan-attestation.schema.json",
    ),
    "urn:intdata:schema:bridge-oauth-registration-approval-receipt:v1": (
        "BridgeOAuthRegistrationApprovalReceiptV1",
        "schemas/bridge-oauth-registration-approval-receipt.schema.json",
    ),
    "urn:intdata:schema:release-verification-key-set:v1": (
        "ReleaseVerificationKeySetV1",
        "schemas/release-verification-key-set.schema.json",
    ),
    "urn:intdata:schema:platform-product-assertion:v1": (
        "PlatformProductAssertionV1",
        "schemas/platform-product-assertion.schema.json",
    ),
}
EXPECTED_PROFILE_DOCUMENT: dict[str, Any] = {
    "profile_id": EXPECTED_PROFILE_ID,
    "version": "v1",
    "input": {
        "encoding": "strict-ascii",
        "min_bytes": 1,
        "max_bytes": 2048,
        "reject": [
            "controls",
            "whitespace",
            "backslash",
            "raw-non-ascii",
            "invalid-utf8",
            "userinfo",
            "fragment",
        ],
    },
    "scheme_and_authority": {
        "https": "allowed",
        "http": (
            "allowed-only-for-exact-127.0.0.1-or-bracketed-ipv6-loopback-with-an-"
            "explicit-non-default-port"
        ),
        "dns": "lowercase-ldh-without-empty-labels-leading-or-trailing-hyphen-or-trailing-dot",
        "ip": "canonical-text",
        "port": "absent-or-canonical-decimal-1-through-65535",
        "default_ports": "forbidden",
        "non_loopback_non_default_port": "requires-signed-installation-policy-admission",
    },
    "path": {
        "empty_input_path": "normalize-to-slash",
        "output": "absolute-nonempty",
        "reject": [
            "dot-segment",
            "encoded-dot-segment",
            "repeated-slash",
            "any-other-path-normalization",
        ],
    },
    "percent_encoding": {
        "hex_output": "input-and-output-uppercase-only",
        "forbid_encoded": [
            "ascii-unreserved",
            "slash",
            "backslash",
            "nul",
            "control",
        ],
        "utf8": "percent-octets-must-form-valid-utf8",
        "reserved": "preserve-byte-and-uppercase-escape-exact",
    },
    "query": {
        "order": "preserve-exact",
        "duplicates": "preserve-exact",
        "percent_rules": "same-as-path",
        "empty_question_mark": "forbidden",
        "plus": "literal-plus-with-no-form-decoding",
    },
    "output": {
        "form": "lowercase-scheme-and-host-plus-canonical-ip-and-port-plus-exact-path-and-query",
        "idempotence": "reparse-output-must-equal-output",
    },
    "arrays": {
        "redirect_uris": (
            "normalize-each-reject-distinct-input-collision-then-deduplicate-"
            "exact-normalized-and-sort-ascending-unsigned-utf8"
        ),
        "grant_types": (
            "ascii-schema-token-identity-normalization-deduplicate-and-sort-"
            "ascending-unsigned-utf8"
        ),
        "scopes": (
            "ascii-schema-token-identity-normalization-deduplicate-and-sort-"
            "ascending-unsigned-utf8"
        ),
    },
}
_PROFILE_LINK_KEYS = frozenset({"$ref", "$dynamicRef", "ref", "href", "url", "links"})
_FOREIGN_PROFILE_LINK = re.compile(r"(?:https?|file)://|urn:", re.IGNORECASE)


class SchemaSetError(ValueError):
    """Raised when the schema set or a requested validation is invalid."""


@dataclass(frozen=True)
class SchemaEntry:
    name: str
    version: str
    id: str
    filename: str
    sha256: str
    document: dict[str, Any]


@dataclass(frozen=True)
class ProfileEntry:
    id: str
    version: str
    filename: str
    sha256: str
    document: dict[str, Any]
    vectors_filename: str
    vectors_sha256: str
    vectors_document: dict[str, Any]


def _deny_retrieval(uri: str) -> Resource[Any]:
    raise NoSuchResource(ref=uri)


def _require_closed_object(
    value: Any, expected_fields: set[str], *, context: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaSetError(f"{context} must be an object")
    fields = set(value)
    if fields != expected_fields:
        missing = sorted(expected_fields - fields)
        unknown = sorted(fields - expected_fields)
        details: list[str] = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        raise SchemaSetError(f"{context} has invalid fields: {', '.join(details)}")
    return value


def _exact_relative_path(root: Path, relative: PurePosixPath, *, context: str) -> Path:
    current = root
    for part in relative.parts:
        if current.is_symlink():
            raise SchemaSetError(f"{context} traverses a symlink: {current}")
        if not current.is_dir():
            raise SchemaSetError(f"{context} parent is not a directory: {current}")
        try:
            children = list(current.iterdir())
        except OSError as error:
            raise SchemaSetError(f"cannot inventory {context}: {error}") from error
        exact = [child for child in children if child.name == part]
        if not exact:
            folded = sorted(
                child.name
                for child in children
                if child.name.casefold() == part.casefold()
            )
            if folded:
                raise SchemaSetError(
                    f"{context} has on-disk case mismatch: expected {part!r}, found {folded}"
                )
            raise SchemaSetError(f"{context} is missing path component: {part!r}")
        current = exact[0]
    if current.is_symlink():
        raise SchemaSetError(f"{context} is a symlink: {current}")
    return current


def _source_path(root: Path, filename: str) -> Path:
    if not filename or "\\" in filename:
        raise SchemaSetError(f"schema filename is not canonical POSIX: {filename!r}")
    relative = PurePosixPath(filename)
    if relative.is_absolute() or str(relative) != filename:
        raise SchemaSetError(f"schema filename is not canonical relative path: {filename!r}")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise SchemaSetError(f"schema filename contains traversal: {filename!r}")
    candidate = _exact_relative_path(root, relative, context=filename)
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as error:
        raise SchemaSetError(f"schema path escapes schema-set directory: {filename}") from error
    if not candidate.is_file():
        raise SchemaSetError(f"schema file is missing: {filename}")
    return candidate


def _require_exact_schema_inventory(root: Path, filenames: set[str]) -> None:
    expected_names = {PurePosixPath(filename).name for filename in filenames}
    schema_dir = _exact_relative_path(
        root, PurePosixPath("schemas"), context="registered schema directory"
    )
    if not schema_dir.is_dir():
        raise SchemaSetError("registered schema path 'schemas' is not a directory")
    try:
        children = list(schema_dir.iterdir())
    except OSError as error:
        raise SchemaSetError(f"cannot inventory registered schema directory: {error}") from error

    actual_names = {child.name for child in children}
    for expected in sorted(expected_names - actual_names):
        folded = sorted(name for name in actual_names if name.casefold() == expected.casefold())
        if folded:
            raise SchemaSetError(
                "registered schema has on-disk case mismatch: "
                f"expected {expected!r}, found {folded}"
            )
    missing = sorted(expected_names - actual_names)
    unknown = sorted(actual_names - expected_names)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        raise SchemaSetError(
            f"registered schema inventory mismatch: {', '.join(details)}"
        )
    for child in children:
        if child.is_symlink() or not child.is_file():
            raise SchemaSetError(
                f"registered schema is not a regular file: schemas/{child.name}"
            )


def _reject_profile_links(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _PROFILE_LINK_KEYS:
                raise SchemaSetError(f"URI profile contains forbidden link field at {path}.{key}")
            _reject_profile_links(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_profile_links(child, path=f"{path}[{index}]")
    elif isinstance(value, str) and _FOREIGN_PROFILE_LINK.search(value):
        raise SchemaSetError(f"URI profile contains a foreign link at {path}")


def _validate_profile_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaSetError("URI normalization profile must be an object")
    _reject_profile_links(value)
    if value != EXPECTED_PROFILE_DOCUMENT:
        raise SchemaSetError(
            "URI normalization profile does not match the closed v1 identity and semantics"
        )
    return value


def _walk_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef"} and isinstance(child, str):
                references.append(child)
            references.extend(_walk_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_walk_references(child))
    return references


class SchemaSet:
    """A digest-verified schema registry which can never retrieve a URL."""

    def __init__(
        self,
        path: Path,
        entries: list[SchemaEntry],
        profiles: list[ProfileEntry],
        registry: Registry[Any],
    ):
        self.path = path
        self.entries = tuple(entries)
        self.profiles = tuple(profiles)
        self._by_id = {entry.id: entry for entry in entries}
        self._registry = registry

    @classmethod
    def load(cls, path: str | Path) -> "SchemaSet":
        set_path = Path(path).resolve()
        if not set_path.is_file():
            raise SchemaSetError(f"schema set is missing: {set_path}")
        try:
            raw_set = set_path.read_bytes()
        except OSError as error:
            raise SchemaSetError(f"cannot read schema set: {error}") from error
        set_document = _require_closed_object(
            strict_loads(raw_set, allow_outer_whitespace=True),
            _SET_FIELDS,
            context="schema set",
        )
        if set_document["schema_set_version"] != SCHEMA_SET_VERSION:
            raise SchemaSetError("unsupported schema_set_version")
        if set_document["draft"] != DRAFT_2020_12:
            raise SchemaSetError("schema set must use Draft 2020-12")
        raw_entries = set_document["schemas"]
        if not isinstance(raw_entries, list) or not raw_entries:
            raise SchemaSetError("schema set must contain a non-empty schemas array")
        entry_ids = {
            entry.get("id")
            for entry in raw_entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        if entry_ids != EXPECTED_SCHEMA_IDS or len(raw_entries) != len(EXPECTED_SCHEMA_IDS):
            missing = sorted(EXPECTED_SCHEMA_IDS - entry_ids)
            unknown = sorted(
                str(item) for item in entry_ids - EXPECTED_SCHEMA_IDS
            )
            raise SchemaSetError(
                f"schema set v1 identity mismatch: missing {missing}, unknown {unknown}"
            )

        entries: list[SchemaEntry] = []
        seen_names: set[str] = set()
        seen_ids: set[str] = set()
        seen_filenames: set[str] = set()
        root = set_path.parent
        expected_filenames = {
            "schemas/"
            + schema_id.removeprefix("urn:intdata:schema:").removesuffix(":v1")
            + ".schema.json"
            for schema_id in EXPECTED_SCHEMA_IDS
        }
        _require_exact_schema_inventory(root, expected_filenames)
        for index, raw_entry in enumerate(raw_entries):
            item = _require_closed_object(
                raw_entry, _ENTRY_FIELDS, context=f"schemas[{index}]"
            )
            if not all(isinstance(item[field], str) for field in _ENTRY_FIELDS):
                raise SchemaSetError(f"schemas[{index}] fields must all be strings")
            schema_id = item["id"]
            if _SCHEMA_ID.fullmatch(schema_id) is None:
                raise SchemaSetError(f"schemas[{index}] id is not canonical")
            expected_name, expected_filename = EXPECTED_SCHEMA_REGISTRY[schema_id]
            name = item["name"]
            if name != expected_name:
                raise SchemaSetError(
                    f"schemas[{index}] name must be {expected_name!r} for {schema_id}"
                )
            if item["version"] != "v1":
                raise SchemaSetError(f"schemas[{index}] version must be v1")
            if item["filename"] != expected_filename:
                raise SchemaSetError(
                    f"schemas[{index}] filename must be {expected_filename!r}"
                )
            if _DIGEST.fullmatch(item["sha256"]) is None:
                raise SchemaSetError(f"schemas[{index}] sha256 is not lowercase SHA-256")
            if name in seen_names or schema_id in seen_ids or item["filename"] in seen_filenames:
                raise SchemaSetError(f"schemas[{index}] duplicates a registry identity")
            seen_names.add(name)
            seen_ids.add(schema_id)
            seen_filenames.add(item["filename"])

            schema_path = _source_path(root, item["filename"])
            schema_raw = schema_path.read_bytes()
            actual_digest = hashlib.sha256(schema_raw).hexdigest()
            if actual_digest != item["sha256"]:
                raise SchemaSetError(
                    f"schema digest mismatch for {item['filename']}: "
                    f"expected {item['sha256']}, got {actual_digest}"
                )
            schema_document = strict_loads(schema_raw, allow_outer_whitespace=True)
            if not isinstance(schema_document, dict):
                raise SchemaSetError(f"schema must be an object: {item['filename']}")
            if schema_document.get("$id") != schema_id:
                raise SchemaSetError(f"schema $id mismatch: {item['filename']}")
            if schema_document.get("$schema") != DRAFT_2020_12:
                raise SchemaSetError(f"schema draft mismatch: {item['filename']}")
            try:
                Draft202012Validator.check_schema(schema_document)
            except SchemaError as error:
                raise SchemaSetError(
                    f"invalid Draft 2020-12 schema {item['filename']}: {error.message}"
                ) from error
            entries.append(
                SchemaEntry(
                    name=name,
                    version=item["version"],
                    id=schema_id,
                    filename=item["filename"],
                    sha256=item["sha256"],
                    document=schema_document,
                )
            )

        raw_profiles = set_document["profiles"]
        if not isinstance(raw_profiles, list) or len(raw_profiles) != 1:
            raise SchemaSetError("schema set v1 must contain exactly one profile")
        profile_item = _require_closed_object(
            raw_profiles[0], _PROFILE_FIELDS, context="profiles[0]"
        )
        if not all(isinstance(profile_item[field], str) for field in _PROFILE_FIELDS):
            raise SchemaSetError("profiles[0] fields must all be strings")
        if profile_item["id"] != EXPECTED_PROFILE_ID:
            raise SchemaSetError(f"unknown profile id: {profile_item['id']}")
        if profile_item["version"] != "v1":
            raise SchemaSetError("profiles[0] version must be v1")
        if profile_item["filename"] != EXPECTED_PROFILE_FILENAME:
            raise SchemaSetError("profiles[0] filename is not canonical")
        if profile_item["vectors_filename"] != EXPECTED_PROFILE_VECTORS_FILENAME:
            raise SchemaSetError("profiles[0] vectors_filename is not canonical")
        if _DIGEST.fullmatch(profile_item["sha256"]) is None:
            raise SchemaSetError("profiles[0] sha256 is not lowercase SHA-256")
        if _DIGEST.fullmatch(profile_item["vectors_sha256"]) is None:
            raise SchemaSetError(
                "profiles[0] vectors_sha256 is not lowercase SHA-256"
            )
        profile_path = _source_path(root, profile_item["filename"])
        profile_raw = profile_path.read_bytes()
        profile_digest = hashlib.sha256(profile_raw).hexdigest()
        if profile_digest != profile_item["sha256"]:
            raise SchemaSetError(
                "profile digest mismatch: "
                f"expected {profile_item['sha256']}, got {profile_digest}"
            )
        profile_document = _validate_profile_document(
            strict_loads(profile_raw, allow_outer_whitespace=True)
        )
        profile_vectors_path = _source_path(root, profile_item["vectors_filename"])
        profile_vectors_raw = profile_vectors_path.read_bytes()
        profile_vectors_digest = hashlib.sha256(profile_vectors_raw).hexdigest()
        if profile_vectors_digest != profile_item["vectors_sha256"]:
            raise SchemaSetError(
                "profile vectors digest mismatch: "
                f"expected {profile_item['vectors_sha256']}, got {profile_vectors_digest}"
            )
        profile_vectors_document = _require_closed_object(
            strict_loads(profile_vectors_raw, allow_outer_whitespace=True),
            {
                "vector_set_id",
                "version",
                "uri_cases",
                "redirect_array_cases",
                "token_array_cases",
            },
            context="URI profile vectors",
        )
        if profile_vectors_document["vector_set_id"] != EXPECTED_PROFILE_ID:
            raise SchemaSetError("URI profile vector_set_id does not match profile id")
        if profile_vectors_document["version"] != "v1":
            raise SchemaSetError("URI profile vectors version must be v1")
        for field in ("uri_cases", "redirect_array_cases", "token_array_cases"):
            if not isinstance(profile_vectors_document[field], list):
                raise SchemaSetError(f"URI profile vectors {field} must be an array")
        profiles = [
            ProfileEntry(
                id=profile_item["id"],
                version=profile_item["version"],
                filename=profile_item["filename"],
                sha256=profile_item["sha256"],
                document=profile_document,
                vectors_filename=profile_item["vectors_filename"],
                vectors_sha256=profile_item["vectors_sha256"],
                vectors_document=profile_vectors_document,
            )
        ]

        raw_vectors = set_document["vectors"]
        if not isinstance(raw_vectors, list) or len(raw_vectors) != 1:
            raise SchemaSetError("schema set v1 must contain exactly one conformance vector set")
        vector_item = _require_closed_object(
            raw_vectors[0], _VECTOR_ENTRY_FIELDS, context="vectors[0]"
        )
        if not all(isinstance(vector_item[field], str) for field in _VECTOR_ENTRY_FIELDS):
            raise SchemaSetError("vectors[0] fields must all be strings")
        if vector_item["id"] != EXPECTED_CONFORMANCE_VECTOR_ID:
            raise SchemaSetError("vectors[0] id is not canonical")
        if vector_item["version"] != SCHEMA_SET_VERSION:
            raise SchemaSetError("vectors[0] version must equal schema_set_version")
        if vector_item["filename"] != EXPECTED_CONFORMANCE_VECTOR_FILENAME:
            raise SchemaSetError("vectors[0] filename is not canonical")
        if _DIGEST.fullmatch(vector_item["sha256"]) is None:
            raise SchemaSetError("vectors[0] sha256 is not lowercase SHA-256")
        vector_path = _source_path(root, vector_item["filename"])
        vector_raw = vector_path.read_bytes()
        vector_digest = hashlib.sha256(vector_raw).hexdigest()
        if vector_digest != vector_item["sha256"]:
            raise SchemaSetError(
                "conformance vectors digest mismatch: "
                f"expected {vector_item['sha256']}, got {vector_digest}"
            )

        known_ids = {entry.id for entry in entries}
        for entry in entries:
            for reference in _walk_references(entry.document):
                base = reference.split("#", 1)[0]
                if base and base not in known_ids:
                    raise SchemaSetError(
                        f"schema {entry.id} references unavailable offline resource {reference!r}"
                    )

        registry: Registry[Any] = Registry(retrieve=_deny_retrieval)
        for entry in entries:
            resource = Resource.from_contents(
                entry.document, default_specification=DRAFT202012
            )
            registry = registry.with_resource(entry.id, resource)
        return cls(set_path, entries, profiles, registry)

    def entry(self, schema_id: str) -> SchemaEntry:
        try:
            return self._by_id[schema_id]
        except KeyError as error:
            raise SchemaSetError(f"unknown schema id: {schema_id}") from error

    def validate_value(self, value: Any, schema_id: str) -> None:
        entry = self.entry(schema_id)
        try:
            _validate_value(value)
        except StrictJSONError as error:
            raise SchemaSetError(str(error)) from error
        validator = Draft202012Validator(
            entry.document,
            registry=self._registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        try:
            errors = sorted(
                validator.iter_errors(value),
                key=_validation_error_key,
            )
        except Exception as error:
            raise SchemaSetError(
                f"offline reference resolution failed for {schema_id}: {error}"
            ) from error
        if errors:
            error = errors[0]
            path = "/" + "/".join(str(part) for part in error.absolute_path)
            raise SchemaSetError(
                f"{schema_id} validation failed at {path or '/'}: {error.message}"
            )

    def validate_raw(self, raw: bytes, schema_id: str) -> Any:
        value = strict_loads(raw)
        self.validate_value(value, schema_id)
        return value

    def canonicalize_raw(self, raw: bytes, schema_id: str) -> bytes:
        value = self.validate_raw(raw, schema_id)
        return canonicalize(value)

    def digest_raw(self, raw: bytes, schema_id: str) -> str:
        value = self.validate_raw(raw, schema_id)
        return canonical_sha256(value)
