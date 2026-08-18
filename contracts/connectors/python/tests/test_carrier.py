from __future__ import annotations

import ast
import copy
import hashlib
import importlib.resources
import json
from pathlib import Path
import unittest

import intdata_connector_contracts as contracts


FIXTURES = (
    Path(__file__).resolve().parents[2] / "experimental-v0" / "fixtures"
)


class ConnectorContractCarrierTests(unittest.TestCase):
    def test_provenance_and_resource_bytes_are_exact(self) -> None:
        schema = contracts.schema_bytes()
        reference = contracts.reference_bytes()
        self.assertEqual(len(schema), contracts.SCHEMA_SIZE)
        self.assertEqual(hashlib.sha256(schema).hexdigest(), contracts.SCHEMA_SHA256)
        self.assertEqual(len(reference), contracts.REFERENCE_SIZE)
        self.assertEqual(
            hashlib.sha256(reference).hexdigest(), contracts.REFERENCE_SHA256
        )
        self.assertEqual(
            contracts.SOURCE_COMMIT,
            "1101cdfb743e5819f07b5b0b2b042f5a4aea6aa4",
        )

    def test_all_canonical_fixtures_validate_and_canonicalize(self) -> None:
        paths = sorted(FIXTURES.glob("*.json"))
        self.assertEqual(len(paths), 7)
        for path in paths:
            with self.subTest(path=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                contracts.validate_document(document)
                expected = json.dumps(
                    document,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.assertEqual(contracts.canonical_json(document), expected)
                self.assertEqual(
                    contracts.canonical_sha256(document),
                    hashlib.sha256(expected).hexdigest(),
                )

    def test_validation_error_is_closed_and_deterministic(self) -> None:
        source = json.loads(
            (FIXTURES / "action-plan-effect.json").read_text(encoding="utf-8")
        )
        observed = []
        for secret in ("first-secret", "second-secret"):
            document = copy.deepcopy(source)
            document["unexpected"] = secret
            with self.assertRaises(contracts.ContractValidationError) as raised:
                contracts.validate_document(document)
            error = raised.exception
            observed.append((error.reason_code, error.path, error.json_pointer))
            self.assertNotIn(secret, str(error))
            self.assertNotIn(secret, repr(error))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0], ("schema_violation", (), ""))

    def test_invalid_timestamp_precision_and_non_json_value_fail_closed(self) -> None:
        receipt = json.loads(
            (FIXTURES / "effect-receipt.json").read_text(encoding="utf-8")
        )
        receipt["started_at"] = "2026-08-09T10:01:00.1234567Z"
        with self.assertRaises(contracts.ContractValidationError) as raised:
            contracts.validate_document(receipt)
        self.assertEqual(raised.exception.reason_code, "schema_violation")
        self.assertEqual(raised.exception.path, ("started_at",))

        receipt["started_at"] = object()
        with self.assertRaises(contracts.ContractValidationError) as raised:
            contracts.canonical_json(receipt)
        self.assertEqual(raised.exception.reason_code, "canonicalization_error")
        self.assertEqual(raised.exception.path, ("started_at",))

    def test_reference_resource_is_not_importable_or_executed(self) -> None:
        root = importlib.resources.files("intdata_connector_contracts")
        names = {item.name for item in (root / "_resources").iterdir()}
        self.assertEqual(names, {"reference.py.txt", "schema.json"})

        source = (root / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"compile", "eval", "exec", "run_path", "run_module"}
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(forbidden.isdisjoint(calls))


if __name__ == "__main__":
    unittest.main()
