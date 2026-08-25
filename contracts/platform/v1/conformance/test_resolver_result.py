from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("validate.py")
SPEC = importlib.util.spec_from_file_location("platform_v1_conformance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONFORMANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFORMANCE)
FIXTURE_PATH = MODULE_PATH.parents[1] / "fixtures" / "valid" / "resolver-result.json"
REJECTED_FIXTURE_PATH = (
    MODULE_PATH.parents[1] / "fixtures" / "valid" / "resolver-result-rejected.json"
)
INPUT_FIXTURE_PATH = MODULE_PATH.parents[1] / "fixtures" / "valid" / "resolver-input.json"
REGISTRY_FIXTURE_PATH = (
    MODULE_PATH.parents[1] / "fixtures" / "valid" / "registry-snapshot.json"
)

REJECTED_ERROR_CODES = [
    "missing_capability",
    "version_conflict",
    "route_collision",
    "migration_lineage_broken",
    "secret_custody_missing",
    "mcp_binding_missing",
    "artifact_drift",
    "reverse_dependency_disable",
    "policy_rejected",
]


def _resolver_result_schema_errors(document: dict) -> list:
    schemas, registry = CONFORMANCE._schema_registry()
    validator = CONFORMANCE._validator(
        "urn:intdata:schema:resolver-result:v1", schemas, registry
    )
    return list(validator.iter_errors(document))


def _refresh_embedded_digest(resolver_input: dict, document_field: str) -> None:
    digest_field = {
        "installation": "installation_sha256",
        "registry_snapshot": "registry_snapshot_sha256",
    }[document_field]
    resolver_input[digest_field] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(resolver_input[document_field])
    ).hexdigest()


def _refresh_lock_binding(document: dict) -> None:
    lock_bytes = CONFORMANCE.jcs_canonical(document["lock"])
    document["lock_sha256"] = hashlib.sha256(lock_bytes).hexdigest()
    document["acceptance_signature"]["envelope"]["payload"] = base64.b64encode(
        lock_bytes
    ).decode("ascii")


def test_resolver_result_binds_canonical_lock_digest() -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("document_field", "digest_field"),
    [
        ("installation", "installation_sha256"),
        ("registry_snapshot", "registry_snapshot_sha256"),
    ],
)
def test_resolver_input_binds_embedded_document_digest(
    document_field: str, digest_field: str
) -> None:
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)

    assert resolver_input[digest_field] == hashlib.sha256(
        CONFORMANCE.jcs_canonical(resolver_input[document_field])
    ).hexdigest()


@pytest.mark.parametrize(
    ("document_field", "nested_field", "value"),
    [
        ("installation", "installation_id", "other.platform"),
        ("registry_snapshot", "registry_id", "other.registry"),
    ],
)
def test_resolver_result_rejects_stale_embedded_document_digest(
    document_field: str, nested_field: str, value: str
) -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    resolver_input[document_field][nested_field] = value

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_input_digest"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    "digest_field", ["installation_sha256", "registry_snapshot_sha256"]
)
def test_resolver_result_rejects_false_embedded_document_digest(
    digest_field: str,
) -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    resolver_input[digest_field] = "6" * 64

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_input_digest"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_rejects_stale_input_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document["lock"]["policy_input_sha256"] = "6" * 64

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_input_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_rejects_stale_lock_digest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document["lock"]["lock_id"] = "empty.lock.2"

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^lock_digest"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_rejects_alternate_acceptance_payload_type() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document["acceptance_signature"]["envelope"]["payloadType"] = "application/json"

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^acceptance_payload_type"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_rejects_acceptance_payload_for_different_lock() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document["acceptance_signature"]["envelope"]["payload"] = "e30="

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^acceptance_payload"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_treats_acceptance_keyid_as_hint() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document["acceptance_signature"]["envelope"]["signatures"][0]["keyid"] = (
        "key.module"
    )

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolver_result_rejects_missing_installation_actor_admission() -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    resolver_input["registry_snapshot"]["accepted_signers"] = [
        entry
        for entry in resolver_input["registry_snapshot"]["accepted_signers"]
        if entry["role"] != "installation-actor"
    ]
    _refresh_embedded_digest(resolver_input, "registry_snapshot")

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^accepted_signer_roles"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_registry_snapshot_binds_embedded_module_manifest_digest() -> None:
    snapshot = CONFORMANCE.load_source_json(REGISTRY_FIXTURE_PATH)

    CONFORMANCE.validate_registry_signer_semantics(snapshot)


@pytest.mark.parametrize("mutate_manifest", [False, True])
def test_registry_snapshot_rejects_stale_module_manifest_digest(
    mutate_manifest: bool,
) -> None:
    snapshot = CONFORMANCE.load_source_json(REGISTRY_FIXTURE_PATH)
    if mutate_manifest:
        snapshot["modules"][0]["module"]["module_id"] = "bridge.changed"
    else:
        snapshot["modules"][0]["manifest_sha256"] = "6" * 64

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^registry_module_digest"):
        CONFORMANCE.validate_registry_signer_semantics(snapshot)


@pytest.mark.parametrize(
    "field",
    ["manifest_sha256", "release_manifest_sha256", "signature_envelope_sha256"],
)
def test_resolved_result_rejects_module_digest_not_admitted_by_registry(
    field: str,
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    registry = CONFORMANCE.load_source_json(REGISTRY_FIXTURE_PATH)
    resolver_input["registry_snapshot"]["modules"] = registry["modules"]
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    entry = registry["modules"][0]
    document["lock"]["resolved_modules"] = [
        {
            "module_id": entry["module"]["module_id"],
            "version": entry["module"]["version"],
            "manifest_sha256": entry["manifest_sha256"],
            "release_manifest_sha256": entry["release_manifest_sha256"],
            "signature_envelope_sha256": entry["signature_envelope_sha256"],
        }
    ]
    document["lock"]["resolved_modules"][0][field] = "6" * 64
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^registry_module_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_rejected_resolver_result_has_no_lock_digest_binding() -> None:
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document = CONFORMANCE.load_source_json(REJECTED_FIXTURE_PATH)

    assert not _resolver_result_schema_errors(document)
    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_rejected_resolver_result_error_codes_match_schema() -> None:
    schemas, _ = CONFORMANCE._schema_registry()
    schema_error_codes = schemas["urn:intdata:schema:resolver-result:v1"]["$defs"][
        "rejected"
    ]["properties"]["error"]["properties"]["code"]["enum"]

    assert schema_error_codes == REJECTED_ERROR_CODES


@pytest.mark.parametrize("error_code", REJECTED_ERROR_CODES)
def test_rejected_resolver_result_accepts_only_closed_error_codes(
    error_code: str,
) -> None:
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    document = copy.deepcopy(CONFORMANCE.load_source_json(REJECTED_FIXTURE_PATH))
    document["error"]["code"] = error_code

    assert not _resolver_result_schema_errors(document)
    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_rejected_resolver_result_rejects_unknown_error_code() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(REJECTED_FIXTURE_PATH))
    document["error"]["code"] = "UNSATISFIABLE"

    assert _resolver_result_schema_errors(document)


@pytest.mark.parametrize(
    "field",
    ["lock", "lock_sha256", "acceptance_signature"],
)
def test_rejected_resolver_result_rejects_partial_success_fields(
    field: str,
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(REJECTED_FIXTURE_PATH))
    resolved_document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    document[field] = copy.deepcopy(resolved_document[field])

    assert _resolver_result_schema_errors(document)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("installation", "installation_id"), "other.platform"),
        (("installation", "revision"), 8),
        (("registry_snapshot", "registry_id"), "other.registry"),
        (("registry_snapshot", "version"), "2026.08.12"),
        (("resolver_version",), "1.0.1"),
        (("solver_policy_version",), "1.0.1"),
        (("policy_input_sha256",), "6" * 64),
    ],
)
def test_resolver_result_rejects_lock_for_different_input(
    path: tuple[str, ...], value: object
) -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    target = resolver_input
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    if path[0] in {"installation", "registry_snapshot"}:
        _refresh_embedded_digest(resolver_input, path[0])

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_input_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)
