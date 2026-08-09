"""Independent schema and semantic validation for connectors experimental v0."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
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
_SPEC.loader.exec_module(REFERENCE)


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
        grant, plan, now_epoch=1786271400, consumed_nonces=frozenset()
    )
    REFERENCE.validate_receipt_for_plan(receipt, plan, grant)
    mock = REFERENCE.MockConnector(capability)
    mock.read_snapshot("contact.snapshot", {"contact_id": 42})
    mock.execute_effect(plan, grant, now_epoch=1786271400)
    return {"ok": True, "fixtures": len(fixtures), "contract_version": REFERENCE.CONTRACT_VERSION}


if __name__ == "__main__":
    print(json.dumps(validate_fixture_set(), sort_keys=True))
