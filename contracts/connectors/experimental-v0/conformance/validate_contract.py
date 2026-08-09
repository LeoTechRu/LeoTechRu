"""Independent schema and semantic validation for connectors experimental v0."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

_SPEC = importlib.util.spec_from_file_location(
    "connector_contract_reference", ROOT / "reference.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load reference module")
REFERENCE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = REFERENCE
_SPEC.loader.exec_module(REFERENCE)


class ExactFixtureJwsVerifier:
    """Non-cryptographic verifier accepting one exact public fixture only."""

    def verify(
        self,
        *,
        issuer: str,
        kid: str,
        alg: str,
        signing_input: bytes,
        signature: bytes,
    ) -> bool:
        return (
            issuer == "agent.grant.issuer"
            and kid == "key.fixture.2026"
            and alg == "EdDSA"
            and hashlib.sha256(signing_input).hexdigest()
            == "c568785cd7bb88ad5c9f0ba3da0ea7054c669d068950d7e0d0f92e0899c99efb"
            and hashlib.sha256(signature).hexdigest()
            == "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b"
        )


FIXTURE_VERIFIER = ExactFixtureJwsVerifier()
FIXTURE_REVOCATION = REFERENCE.TrustedRevocationContext(
    issuer="agent.grant.issuer",
    snapshot_digest="1212121212121212121212121212121212121212121212121212121212121212",
    revision=4,
    issued_epoch=1786270800,
    expires_epoch=1786272600,
    revoked_nonces=frozenset(),
    signature_verified=True,
)


class DuplicateKeyError(ValueError):
    pass


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def load_document(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_closed_object)
    if not isinstance(value, dict):
        raise ValueError("contract document must be an object")
    return value


def validate_document(document: dict[str, Any]) -> None:
    VALIDATOR.validate(document)
    if REFERENCE.canonical_json(document) != REFERENCE.canonical_json(
        json.loads(REFERENCE.canonical_json(document))
    ):
        raise ValueError("canonical JSON round-trip mismatch")


def validate_capability(capability: dict[str, Any]) -> None:
    validate_document(capability)
    REFERENCE.negotiate_version(capability["supported_contract_versions"])
    operations = [item["operation"] for item in capability["operations"]]
    if len(operations) != len(set(operations)):
        raise REFERENCE.ContractError("duplicate connector operation")


def load_fixture(name: str) -> dict[str, Any]:
    return load_document(ROOT / "fixtures" / name)


def validate_fixture_set() -> dict[str, Any]:
    fixtures = {
        path.name: load_document(path)
        for path in sorted((ROOT / "fixtures").glob("*.json"))
    }
    for document in fixtures.values():
        validate_document(document)
    capability = fixtures["connector-capability.json"]
    validate_capability(capability)
    plan = fixtures["action-plan-effect.json"]
    grant = fixtures["effect-grant.json"]
    receipt = fixtures["effect-receipt.json"]
    REFERENCE.validate_grant_for_plan(
        grant,
        plan,
        now_epoch=1786271400,
        consumed_nonces=frozenset(),
        verifier=FIXTURE_VERIFIER,
        revocation_context=FIXTURE_REVOCATION,
    )
    REFERENCE.validate_receipt_for_plan(receipt, plan, grant)
    mock = REFERENCE.MockConnector(
        capability,
        verifier=FIXTURE_VERIFIER,
        revocation_context=FIXTURE_REVOCATION,
    )
    mock.read_snapshot("contact.snapshot", {"contact_id": 42})
    mock.execute_effect(plan, grant, now_epoch=1786271400)
    return {"ok": True, "fixtures": len(fixtures), "contract_version": REFERENCE.CONTRACT_VERSION}


if __name__ == "__main__":
    print(json.dumps(validate_fixture_set(), sort_keys=True))
