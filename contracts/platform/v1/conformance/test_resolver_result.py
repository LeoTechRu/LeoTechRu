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
MODULE_FIXTURE_PATH = (
    MODULE_PATH.parents[1] / "fixtures" / "valid" / "module-manifest.json"
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


def _add_registry_module_and_artifact_binding(document: dict, resolver_input: dict) -> None:
    registry = CONFORMANCE.load_source_json(REGISTRY_FIXTURE_PATH)
    entry = registry["modules"][0]
    module = entry["module"]
    artifact = module["artifacts"][0]
    resolver_input["registry_snapshot"]["modules"] = registry["modules"]
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"] = [
        {
            "module_id": module["module_id"],
            "version": module["version"],
            "manifest_sha256": entry["manifest_sha256"],
            "release_manifest_sha256": entry["release_manifest_sha256"],
            "signature_envelope_sha256": entry["signature_envelope_sha256"],
        }
    ]
    document["lock"]["artifact_bindings"] = [
        {
            "artifact_id": artifact["artifact_id"],
            "module_id": module["module_id"],
            "sha256": artifact["sha256"],
            "size_bytes": artifact["size_bytes"],
            "locations": ["https://artifacts.example/bridge-core.tar.gz"],
        }
    ]
    resolver_input["installation"]["modules"] = [
        {
            "module_id": module["module_id"],
            "version_constraint": module["version"],
            "state": "enabled",
        }
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    _refresh_lock_binding(document)


def _add_module_selection(
    document: dict,
    resolver_input: dict,
    *,
    required_dependency: bool,
    include_dependency: bool,
) -> None:
    _add_registry_module_and_artifact_binding(document, resolver_input)
    bridge_entry = resolver_input["registry_snapshot"]["modules"][0]
    bridge_manifest = bridge_entry["module"]
    dependency_entry = copy.deepcopy(bridge_entry)
    dependency_manifest = dependency_entry["module"]
    dependency_manifest["module_id"] = "other.core"
    dependency_manifest["capabilities"]["provides"] = []
    dependency_manifest["artifacts"][0]["artifact_id"] = "other.package"
    dependency_manifest["dependencies"] = []
    dependency_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(dependency_manifest)
    ).hexdigest()
    resolver_input["registry_snapshot"]["modules"].append(dependency_entry)
    if required_dependency:
        bridge_manifest["dependencies"] = [
            {
                "module_id": "other.core",
                "version_constraint": "1.0.0",
                "optional": False,
            }
        ]
        bridge_entry["manifest_sha256"] = hashlib.sha256(
            CONFORMANCE.jcs_canonical(bridge_manifest)
        ).hexdigest()
        document["lock"]["resolved_modules"][0]["manifest_sha256"] = bridge_entry[
            "manifest_sha256"
        ]
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    resolver_input["installation"]["modules"] = [
        {
            "module_id": "bridge.core",
            "version_constraint": "1.0.0",
            "state": "enabled",
        }
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    if include_dependency:
        document["lock"]["resolved_modules"].append(
            {
                "module_id": dependency_manifest["module_id"],
                "version": dependency_manifest["version"],
                "manifest_sha256": dependency_entry["manifest_sha256"],
                "release_manifest_sha256": dependency_entry[
                    "release_manifest_sha256"
                ],
                "signature_envelope_sha256": dependency_entry[
                    "signature_envelope_sha256"
                ],
            }
        )
        dependency_artifact = dependency_manifest["artifacts"][0]
        document["lock"]["artifact_bindings"].append(
            {
                "artifact_id": dependency_artifact["artifact_id"],
                "module_id": dependency_manifest["module_id"],
                "sha256": dependency_artifact["sha256"],
                "size_bytes": dependency_artifact["size_bytes"],
                "locations": ["https://artifacts.example/other-core.tar.gz"],
            }
        )
    _refresh_lock_binding(document)


def _add_route_binding(document: dict, resolver_input: dict) -> None:
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    manifest["routes"] = copy.deepcopy(
        CONFORMANCE.load_source_json(MODULE_FIXTURE_PATH)["routes"]
    )
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    route = manifest["routes"][0]
    document["lock"]["route_bindings"] = [
        {
            "route_id": route["route_id"],
            "module_id": manifest["module_id"],
            "origin": route["origin"],
            "path": route["path"],
            "runtime_unit_id": route["runtime_unit_id"],
        }
    ]
    _refresh_lock_binding(document)


def _add_web_module_binding(document: dict, resolver_input: dict) -> None:
    _add_route_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    web_module = {
        "web_module_id": "bridge.console",
        "entrypoint_artifact_id": "bridge.package",
        "route_id": "bridge.mcp",
    }
    manifest["web_modules"] = [web_module]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["web_module_bindings"] = [
        {
            "web_module_id": web_module["web_module_id"],
            "module_id": manifest["module_id"],
            "entrypoint_artifact_sha256": manifest["artifacts"][0]["sha256"],
            "route_id": web_module["route_id"],
        }
    ]
    _refresh_lock_binding(document)


def _add_second_route_binding(
    document: dict, resolver_input: dict, *, path: str
) -> None:
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    second_route = copy.deepcopy(manifest["routes"][0])
    second_route["route_id"] = "bridge.admin"
    second_route["path"] = path
    manifest["routes"].append(second_route)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["route_bindings"].append(
        {
            "route_id": second_route["route_id"],
            "module_id": manifest["module_id"],
            "origin": second_route["origin"],
            "path": second_route["path"],
            "runtime_unit_id": second_route["runtime_unit_id"],
        }
    )
    document["lock"]["route_bindings"].sort(
        key=lambda item: (
            item["module_id"].encode("utf-8"),
            item["route_id"].encode("utf-8"),
        )
    )
    _refresh_lock_binding(document)


def _add_migration_binding(document: dict, resolver_input: dict) -> None:
    _add_registry_module_and_artifact_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    migration = {
        "migration_id": "bridge.init",
        "lineage_parent": None,
        "artifact_id": "bridge.package",
        "order": 0,
    }
    manifest["migrations"] = [migration]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["migration_bindings"] = [
        {
            "migration_id": migration["migration_id"],
            "module_id": manifest["module_id"],
            "lineage_parent": migration["lineage_parent"],
            "artifact_sha256": manifest["artifacts"][0]["sha256"],
            "order": migration["order"],
        }
    ]
    _refresh_lock_binding(document)


def _add_child_migration(document: dict, resolver_input: dict) -> None:
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    migration = {
        "migration_id": "bridge.next",
        "lineage_parent": "bridge.init",
        "artifact_id": "bridge.package",
        "order": 1,
    }
    manifest["migrations"].append(migration)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["migration_bindings"].append(
        {
            "migration_id": migration["migration_id"],
            "module_id": manifest["module_id"],
            "lineage_parent": migration["lineage_parent"],
            "artifact_sha256": manifest["artifacts"][0]["sha256"],
            "order": migration["order"],
        }
    )
    _refresh_lock_binding(document)


def _add_runtime_binding(document: dict, resolver_input: dict) -> None:
    _add_registry_module_and_artifact_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    module_fixture = CONFORMANCE.load_source_json(MODULE_FIXTURE_PATH)
    manifest["runtime_units"] = copy.deepcopy(module_fixture["runtime_units"])
    manifest["configuration_requirements"] = copy.deepcopy(
        module_fixture["configuration_requirements"]
    )
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    resolver_input["installation"]["configuration_custody"] = [
        {
            "configuration_key": "database.url",
            "custody_ref": "vault.database.url",
            "present": True,
        }
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["runtime_bindings"] = [
        {
            "runtime_unit_id": "bridge.server",
            "module_id": "bridge.core",
            "artifact_sha256": manifest["artifacts"][0]["sha256"],
            "configuration_custody_refs": ["vault.database.url"],
        }
    ]
    _refresh_lock_binding(document)


def _add_mcp_binding(document: dict, resolver_input: dict) -> None:
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    route = copy.deepcopy(CONFORMANCE.load_source_json(MODULE_FIXTURE_PATH)["routes"][0])
    manifest["routes"] = [route]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "bridge.oauth",
            "provider_module_id": "bridge.core",
            "provider_version": "1.0.0",
        }
    ]
    document["lock"]["route_bindings"] = [
        {
            "route_id": route["route_id"],
            "module_id": manifest["module_id"],
            "origin": route["origin"],
            "path": route["path"],
            "runtime_unit_id": route["runtime_unit_id"],
        }
    ]
    document["lock"]["mcp_bindings"] = [
        {
            "capability_id": "bridge.oauth",
            "resource_uri": "https://bridge.intdata.pro/mcp",
            "audience": "https://bridge.intdata.pro/mcp",
            "runtime_unit_id": "bridge.server",
        }
    ]
    _refresh_lock_binding(document)


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


def test_resolver_result_rejects_noncanonical_acceptance_signature_base64() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    signature = document["acceptance_signature"]["envelope"]["signatures"][0]
    signature["sig"] = signature["sig"][:-3] + "B=="

    assert base64.b64decode(signature["sig"], validate=True) == bytes(64)
    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^acceptance_signature"):
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


def test_resolved_result_rejects_incompatible_enabled_module_version() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["modules"][0]["version_constraint"] = "2.0.0"
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^version_conflict"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_incompatible_dependency_version() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=True,
    )
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["dependencies"][0]["version_constraint"] = "2.0.0"
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^version_conflict"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("module_id", "other.module"),
        ("artifact_id", "other.package"),
        ("sha256", "6" * 64),
        ("size_bytes", "2048"),
    ],
)
def test_resolved_result_rejects_artifact_not_bound_to_admitted_manifest(
    field: str, value: str
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    document["lock"]["artifact_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^artifact_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_artifact_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    document["lock"]["artifact_bindings"].append(
        copy.deepcopy(document["lock"]["artifact_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^artifact_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unbound_manifest_artifact() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    document["lock"]["artifact_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^artifact_drift"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_capability_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["capabilities"] = [
        {"capability_id": "bridge.oauth", "version_constraint": "1.0.0"}
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "bridge.oauth",
            "provider_module_id": "bridge.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_incompatible_desired_capability_provider() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["capabilities"] = [
        {"capability_id": "bridge.oauth", "version_constraint": "2.0.0"}
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "bridge.oauth",
            "provider_module_id": "bridge.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^version_conflict"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_desired_capability_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["capabilities"] = [
        {"capability_id": "bridge.oauth", "version_constraint": "1.0.0"}
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^resolver_capability_selection"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability_id", "bridge.unknown"),
        ("provider_module_id", "other.module"),
        ("provider_version", "2.0.0"),
    ],
)
def test_resolved_result_rejects_capability_not_bound_to_admitted_manifest(
    field: str, value: str
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "bridge.oauth",
            "provider_module_id": "bridge.core",
            "provider_version": "1.0.0",
        }
    ]
    document["lock"]["capability_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^capability_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_capability_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    binding = {
        "capability_id": "bridge.oauth",
        "provider_module_id": "bridge.core",
        "provider_version": "1.0.0",
    }
    document["lock"]["capability_bindings"] = [binding, copy.deepcopy(binding)]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^capability_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_capability_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["capabilities"] = [
        {"capability_id": "bridge.admin", "version_constraint": "1.0.0"},
        {"capability_id": "bridge.oauth", "version_constraint": "1.0.0"},
    ]
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["capabilities"]["provides"].insert(
        0, {"capability_id": "bridge.admin", "version_constraint": "1.0.0"}
    )
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "installation")
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": capability_id,
            "provider_module_id": "bridge.core",
            "provider_version": "1.0.0",
        }
        for capability_id in ("bridge.oauth", "bridge.admin")
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_required_capability_provider() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=False,
        include_dependency=True,
    )
    bridge_entry, provider_entry = resolver_input["registry_snapshot"]["modules"]
    bridge_entry["module"]["capabilities"]["requires"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    provider_entry["module"]["capabilities"]["provides"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    for entry in (bridge_entry, provider_entry):
        entry["manifest_sha256"] = hashlib.sha256(
            CONFORMANCE.jcs_canonical(entry["module"])
        ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    for resolved in document["lock"]["resolved_modules"]:
        entry = bridge_entry if resolved["module_id"] == "bridge.core" else provider_entry
        resolved["manifest_sha256"] = entry["manifest_sha256"]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "other.service",
            "provider_module_id": "other.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_matching_nonfirst_capability_version() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=False,
        include_dependency=True,
    )
    bridge_entry, provider_entry = resolver_input["registry_snapshot"]["modules"]
    bridge_entry["module"]["capabilities"]["requires"] = [
        {"capability_id": "other.service", "version_constraint": "2.0.0"}
    ]
    provider_entry["module"]["capabilities"]["provides"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"},
        {"capability_id": "other.service", "version_constraint": "2.0.0"},
    ]
    for entry in (bridge_entry, provider_entry):
        entry["manifest_sha256"] = hashlib.sha256(
            CONFORMANCE.jcs_canonical(entry["module"])
        ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    for resolved in document["lock"]["resolved_modules"]:
        entry = bridge_entry if resolved["module_id"] == "bridge.core" else provider_entry
        resolved["manifest_sha256"] = entry["manifest_sha256"]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "other.service",
            "provider_module_id": "other.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_incompatible_required_capability_provider() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=False,
        include_dependency=True,
    )
    bridge_entry, provider_entry = resolver_input["registry_snapshot"]["modules"]
    bridge_entry["module"]["capabilities"]["requires"] = [
        {"capability_id": "other.service", "version_constraint": "2.0.0"}
    ]
    provider_entry["module"]["capabilities"]["provides"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    for entry in (bridge_entry, provider_entry):
        entry["manifest_sha256"] = hashlib.sha256(
            CONFORMANCE.jcs_canonical(entry["module"])
        ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    for resolved in document["lock"]["resolved_modules"]:
        entry = bridge_entry if resolved["module_id"] == "bridge.core" else provider_entry
        resolved["manifest_sha256"] = entry["manifest_sha256"]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "other.service",
            "provider_module_id": "other.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^missing_capability"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_required_capability_provider() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["capabilities"]["requires"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^missing_capability"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_isolated_self_supporting_capability_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=False,
        include_dependency=True,
    )
    isolated_entry = resolver_input["registry_snapshot"]["modules"][1]
    isolated_manifest = isolated_entry["module"]
    isolated_manifest["capabilities"]["provides"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    isolated_manifest["capabilities"]["requires"] = [
        {"capability_id": "other.service", "version_constraint": "1.0.0"}
    ]
    isolated_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(isolated_manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][1]["manifest_sha256"] = isolated_entry[
        "manifest_sha256"
    ]
    document["lock"]["capability_bindings"] = [
        {
            "capability_id": "other.service",
            "provider_module_id": "other.core",
            "provider_version": "1.0.0",
        }
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_module_selection"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_conflicting_selected_modules() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=True,
    )
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["conflicts"] = ["other.core"]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^version_conflict"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_route_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unprojected_manifest_route() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    document["lock"]["route_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^route_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_manifest_route_id() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    duplicate_route = copy.deepcopy(registry_entry["module"]["routes"][0])
    duplicate_route["path"] = "/admin"
    registry_entry["module"]["routes"].append(duplicate_route)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^route_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_routes_with_distinct_endpoints() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    _add_second_route_binding(document, resolver_input, path="/admin")

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_route_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    _add_second_route_binding(document, resolver_input, path="/admin")
    document["lock"]["route_bindings"].reverse()
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_route_with_missing_runtime_unit() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["routes"][0]["runtime_unit_id"] = "bridge.missing"
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["route_bindings"][0]["runtime_unit_id"] = "bridge.missing"
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^route_runtime_binding"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_route_endpoint_collision() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    _add_second_route_binding(document, resolver_input, path="/mcp")

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^route_collision"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route_id", "bridge.other"),
        ("module_id", "other.module"),
        ("origin", "https://other.intdata.pro"),
        ("path", "/other"),
        ("runtime_unit_id", "bridge.other"),
    ],
)
def test_resolved_result_rejects_route_not_bound_to_admitted_manifest(
    field: str, value: str
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    document["lock"]["route_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^route_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_route_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_route_binding(document, resolver_input)
    document["lock"]["route_bindings"].append(
        copy.deepcopy(document["lock"]["route_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^route_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_migration_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_ordered_migration_lineage() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_migration_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    document["lock"]["migration_bindings"].reverse()
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("lineage_parent", "order"),
    [("bridge.missing", 1), ("bridge.next", 1), ("bridge.init", 0)],
)
def test_resolved_result_rejects_broken_migration_lineage(
    lineage_parent: str, order: int
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    migration = resolver_input["registry_snapshot"]["modules"][0]["module"][
        "migrations"
    ][1]
    migration["lineage_parent"] = lineage_parent
    migration["order"] = order
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^migration_lineage_broken"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unprojected_manifest_migration() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    document["lock"]["migration_bindings"].pop()
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^migration_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_disconnected_migration_root() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["migrations"][1]["lineage_parent"] = None
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^migration_lineage_broken"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_migration_id() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    migrations = resolver_input["registry_snapshot"]["modules"][0]["module"][
        "migrations"
    ]
    migrations[1]["migration_id"] = migrations[0]["migration_id"]
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^migration_lineage_broken"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_nonpreceding_migration_parent() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    _add_child_migration(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["migrations"][0]["order"] = 2
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^migration_lineage_broken"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("migration_id", "bridge.other"),
        ("module_id", "other.module"),
        ("lineage_parent", "bridge.previous"),
        ("artifact_sha256", "6" * 64),
        ("order", 1),
    ],
)
def test_resolved_result_rejects_migration_not_bound_to_admitted_manifest(
    field: str, value: object
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    document["lock"]["migration_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^migration_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_migration_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_migration_binding(document, resolver_input)
    document["lock"]["migration_bindings"].append(
        copy.deepcopy(document["lock"]["migration_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^migration_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_web_module_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_web_module_binding(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unprojected_manifest_web_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_web_module_binding(document, resolver_input)
    document["lock"]["web_module_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^web_module_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("web_module_id", "bridge.other"),
        ("module_id", "other.module"),
        ("entrypoint_artifact_sha256", "6" * 64),
        ("route_id", "bridge.other"),
    ],
)
def test_resolved_result_rejects_web_module_not_bound_to_admitted_manifest(
    field: str, value: str
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_web_module_binding(document, resolver_input)
    document["lock"]["web_module_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^web_module_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_web_module_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_web_module_binding(document, resolver_input)
    document["lock"]["web_module_bindings"].append(
        copy.deepcopy(document["lock"]["web_module_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^web_module_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_web_module_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_web_module_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    second_web_module = copy.deepcopy(manifest["web_modules"][0])
    second_web_module["web_module_id"] = "bridge.admin"
    manifest["web_modules"].append(second_web_module)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    second_binding = copy.deepcopy(document["lock"]["web_module_bindings"][0])
    second_binding["web_module_id"] = second_web_module["web_module_id"]
    document["lock"]["web_module_bindings"].append(second_binding)
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_runtime_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unprojected_manifest_runtime_unit() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    document["lock"]["runtime_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^runtime_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_manifest_runtime_unit_id() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    duplicate_runtime = copy.deepcopy(registry_entry["module"]["runtime_units"][0])
    duplicate_runtime["entrypoint"] = "bin/bridge-worker"
    registry_entry["module"]["runtime_units"].append(duplicate_runtime)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^runtime_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime_unit_id", "bridge.other"),
        ("module_id", "other.module"),
        ("artifact_sha256", "6" * 64),
        ("configuration_custody_refs", ["vault.other"]),
    ],
)
def test_resolved_result_rejects_runtime_not_bound_to_admitted_manifest(
    field: str, value: object
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    document["lock"]["runtime_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^runtime_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_optional_runtime_configuration_without_custody() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["configuration_requirements"][0]["required"] = False
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    resolver_input["installation"]["configuration_custody"] = []
    _refresh_embedded_digest(resolver_input, "installation")
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["runtime_bindings"][0]["configuration_custody_refs"] = []
    _refresh_lock_binding(document)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_shared_custody_reference_for_runtime_keys() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    registry_entry["module"]["runtime_units"][0]["configuration_keys"].append(
        "other.value"
    )
    registry_entry["module"]["configuration_requirements"].append(
        {
            "key": "other.value",
            "value_type": "string",
            "required": True,
            "secret": False,
        }
    )
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    resolver_input["installation"]["configuration_custody"].append(
        {
            "configuration_key": "other.value",
            "custody_ref": "vault.database.url",
            "present": True,
        }
    )
    _refresh_embedded_digest(resolver_input, "installation")
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    _refresh_lock_binding(document)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_runtime_configuration_custody() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    resolver_input["installation"]["configuration_custody"][0]["present"] = False
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^secret_custody_missing"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_runtime_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    document["lock"]["runtime_bindings"].append(
        copy.deepcopy(document["lock"]["runtime_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^runtime_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_runtime_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_runtime_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    second_runtime = copy.deepcopy(registry_entry["module"]["runtime_units"][0])
    second_runtime["runtime_unit_id"] = "bridge.worker"
    registry_entry["module"]["runtime_units"].append(second_runtime)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(registry_entry["module"])
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    second_binding = copy.deepcopy(document["lock"]["runtime_bindings"][0])
    second_binding["runtime_unit_id"] = second_runtime["runtime_unit_id"]
    document["lock"]["runtime_bindings"].insert(0, second_binding)
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_mcp_binding_from_admitted_manifest() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_mcp_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)
    document["lock"]["mcp_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^mcp_binding_missing"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability_id", "bridge.unknown"),
        ("resource_uri", "https://bridge.intdata.pro/other"),
        ("audience", "https://other.intdata.pro/mcp"),
        ("runtime_unit_id", "bridge.other"),
    ],
)
def test_resolved_result_rejects_mcp_binding_not_bound_to_admitted_manifest(
    field: str, value: str
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)
    document["lock"]["mcp_bindings"][0][field] = value
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^mcp_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_mcp_capability_projected_by_another_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    other_entry = copy.deepcopy(registry_entry)
    other_manifest = other_entry["module"]
    other_manifest["module_id"] = "other.core"
    other_manifest["routes"] = []
    other_manifest["runtime_units"] = []
    other_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(other_manifest)
    ).hexdigest()
    resolver_input["registry_snapshot"]["modules"].append(other_entry)
    resolver_input["installation"]["modules"].append(
        {
            "module_id": "other.core",
            "version_constraint": other_manifest["version"],
            "state": "enabled",
        }
    )
    _refresh_embedded_digest(resolver_input, "installation")
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"].append(
        {
            "module_id": "other.core",
            "version": other_manifest["version"],
            "manifest_sha256": other_entry["manifest_sha256"],
            "release_manifest_sha256": other_entry["release_manifest_sha256"],
            "signature_envelope_sha256": other_entry["signature_envelope_sha256"],
        }
    )
    other_artifact = other_manifest["artifacts"][0]
    document["lock"]["artifact_bindings"].append(
        {
            "artifact_id": other_artifact["artifact_id"],
            "module_id": other_manifest["module_id"],
            "sha256": other_artifact["sha256"],
            "size_bytes": other_artifact["size_bytes"],
            "locations": ["https://artifacts.example/other-core.tar.gz"],
        }
    )
    document["lock"]["capability_bindings"][0]["provider_module_id"] = "other.core"
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^mcp_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_duplicate_mcp_binding() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)
    document["lock"]["mcp_bindings"].append(
        copy.deepcopy(document["lock"]["mcp_bindings"][0])
    )
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^mcp_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_mcp_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_mcp_binding(document, resolver_input)
    registry_entry = resolver_input["registry_snapshot"]["modules"][0]
    manifest = registry_entry["module"]
    second_capability = "bridge.zeta"
    manifest["capabilities"]["provides"].append(
        {"capability_id": second_capability, "version_constraint": "1.0.0"}
    )
    manifest["runtime_units"][0]["capabilities"].append(second_capability)
    registry_entry["manifest_sha256"] = hashlib.sha256(
        CONFORMANCE.jcs_canonical(manifest)
    ).hexdigest()
    _refresh_embedded_digest(resolver_input, "registry_snapshot")
    document["lock"]["registry_snapshot"]["sha256"] = resolver_input[
        "registry_snapshot_sha256"
    ]
    document["lock"]["resolved_modules"][0]["manifest_sha256"] = registry_entry[
        "manifest_sha256"
    ]
    document["lock"]["capability_bindings"].append(
        {
            "capability_id": second_capability,
            "provider_module_id": manifest["module_id"],
            "provider_version": manifest["version"],
        }
    )
    second_binding = copy.deepcopy(document["lock"]["mcp_bindings"][0])
    second_binding["capability_id"] = second_capability
    document["lock"]["mcp_bindings"].insert(0, second_binding)
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_enabled_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    resolver_input["installation"]["modules"] = [
        {
            "module_id": "bridge.core",
            "version_constraint": "1.0.0",
            "state": "enabled",
        }
    ]
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    document["lock"]["resolved_modules"] = []
    document["lock"]["artifact_bindings"] = []
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^resolver_module_selection"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_accepts_required_transitive_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=True,
    )

    CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_module_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=True,
    )
    document["lock"]["resolved_modules"].reverse()
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_artifact_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=True,
    )
    document["lock"]["artifact_bindings"].reverse()
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_noncanonical_artifact_location_order() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_registry_module_and_artifact_binding(document, resolver_input)
    document["lock"]["artifact_bindings"][0]["locations"] = [
        "https://mirror.example/bridge-core.tar.gz",
        "https://artifacts.example/bridge-core.tar.gz",
    ]
    _refresh_lock_binding(document)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_order"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


@pytest.mark.parametrize("include_dependency", [False, True])
def test_resolved_result_rejects_disabled_required_transitive_module(
    include_dependency: bool,
) -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=include_dependency,
    )
    resolver_input["installation"]["modules"].append(
        {
            "module_id": "other.core",
            "version_constraint": "1.0.0",
            "state": "disabled",
        }
    )
    _refresh_embedded_digest(resolver_input, "installation")
    document["lock"]["installation"]["sha256"] = resolver_input[
        "installation_sha256"
    ]
    _refresh_lock_binding(document)

    with pytest.raises(
        CONFORMANCE.ConformanceError, match=r"^reverse_dependency_disable"
    ):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_missing_required_transitive_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=True,
        include_dependency=False,
    )

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_module_selection"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_resolved_result_rejects_unrequested_module() -> None:
    document = copy.deepcopy(CONFORMANCE.load_source_json(FIXTURE_PATH))
    resolver_input = copy.deepcopy(CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH))
    _add_module_selection(
        document,
        resolver_input,
        required_dependency=False,
        include_dependency=True,
    )

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_module_selection"):
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
