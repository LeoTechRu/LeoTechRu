from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("validate.py")
SPEC = importlib.util.spec_from_file_location("platform_v1_conformance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONFORMANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFORMANCE)
FIXTURE_PATH = MODULE_PATH.parents[1] / "fixtures" / "valid" / "resolver-result.json"
INPUT_FIXTURE_PATH = MODULE_PATH.parents[1] / "fixtures" / "valid" / "resolver-input.json"


def test_resolver_result_binds_canonical_lock_digest() -> None:
    document = CONFORMANCE.load_source_json(FIXTURE_PATH)
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)

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

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^accepted_signer_roles"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)


def test_rejected_resolver_result_has_no_lock_digest_binding() -> None:
    resolver_input = CONFORMANCE.load_source_json(INPUT_FIXTURE_PATH)
    CONFORMANCE.validate_resolver_result_semantics(
        {
            "schema_version": "ResolverResultV1",
            "status": "rejected",
            "error": {"code": "UNSATISFIABLE", "message": "no solution"},
        },
        resolver_input,
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("installation", "installation_id"), "other.platform"),
        (("installation", "revision"), 8),
        (("installation_sha256",), "6" * 64),
        (("registry_snapshot", "registry_id"), "other.registry"),
        (("registry_snapshot", "version"), "2026.08.12"),
        (("registry_snapshot_sha256",), "6" * 64),
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

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^resolver_input_binding"):
        CONFORMANCE.validate_resolver_result_semantics(document, resolver_input)
