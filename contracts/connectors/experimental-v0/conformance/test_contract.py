from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

from jsonschema import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_contract import REFERENCE, load_fixture, validate_capability, validate_document, validate_fixture_set


class ConnectorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = load_fixture("connector-capability.json")
        self.read_plan = load_fixture("action-plan-read.json")
        self.effect_plan = load_fixture("action-plan-effect.json")
        self.grant = load_fixture("effect-grant.json")
        self.receipt = load_fixture("effect-receipt.json")

    def test_fixture_set_is_schema_and_semantically_valid(self) -> None:
        result = validate_fixture_set()
        self.assertTrue(result["ok"])
        self.assertEqual(result["fixtures"], 7)

    def test_unknown_contract_version_is_rejected(self) -> None:
        document = copy.deepcopy(self.effect_plan)
        document["contract_version"] = "connectors-experimental-v1"
        with self.assertRaises(ValidationError):
            validate_document(document)
        with self.assertRaisesRegex(REFERENCE.ContractError, "no exact"):
            REFERENCE.negotiate_version(["connectors-experimental-v1"])

    def test_closed_objects_reject_arbitrary_command_and_secret_fields(self) -> None:
        for field in ("command", "argv", "env", "credential", "secret_ref"):
            document = copy.deepcopy(self.effect_plan)
            document[field] = "forbidden"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_document(document)

    def test_read_capability_is_get_only_and_not_grant_gated(self) -> None:
        capability = copy.deepcopy(self.capability)
        read = capability["operations"][0]
        read["network_methods"] = ["GET", "POST"]
        with self.assertRaises(ValidationError):
            validate_capability(capability)
        read["network_methods"] = ["GET"]
        read["grant_required"] = True
        with self.assertRaises(ValidationError):
            validate_capability(capability)

    def test_effect_plan_requires_approval_and_grant(self) -> None:
        for field in ("approving_principal", "approving_role"):
            plan = copy.deepcopy(self.effect_plan)
            del plan[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_document(plan)
        plan = copy.deepcopy(self.effect_plan)
        plan["grant_required"] = False
        with self.assertRaises(ValidationError):
            validate_document(plan)

    def test_read_plan_cannot_smuggle_approval_or_grant(self) -> None:
        plan = copy.deepcopy(self.read_plan)
        plan["approving_role"] = "role.integration.operator"
        with self.assertRaises(ValidationError):
            validate_document(plan)
        plan = copy.deepcopy(self.read_plan)
        plan["grant_required"] = True
        with self.assertRaises(ValidationError):
            validate_document(plan)

    def test_wrong_audience_tenant_and_contour_fail_closed(self) -> None:
        for field, value, message in (
            ("audience", "other-service", "audience"),
            ("tenant_id", "tenant.other", "tenant_id"),
            ("contour", "production", "contour"),
        ):
            grant = copy.deepcopy(self.grant)
            grant[field] = value
            grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
            with self.subTest(field=field), self.assertRaisesRegex(REFERENCE.ContractError, message):
                REFERENCE.validate_grant_for_plan(
                    grant, self.effect_plan, now_epoch=1786271400
                )

    def test_plan_connection_operation_target_and_policy_are_bound(self) -> None:
        for field, value in (
            ("connection_id", "connection.other"),
            ("operation", "contact.tag.remove"),
            ("target_digest", "1" * 64),
            ("policy_revision", 8),
        ):
            grant = copy.deepcopy(self.grant)
            grant[field] = value
            grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
            with self.subTest(field=field), self.assertRaisesRegex(REFERENCE.ContractError, field):
                REFERENCE.validate_grant_for_plan(
                    grant, self.effect_plan, now_epoch=1786271400
                )

    def test_expired_future_and_malformed_validity_fail_closed(self) -> None:
        for field, value in (
            ("expires_epoch", 1786271300),
            ("not_before_epoch", 1786271500),
            ("expires_epoch", 1786269500),
        ):
            grant = copy.deepcopy(self.grant)
            grant[field] = value
            grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
            with self.subTest(field=field, value=value), self.assertRaisesRegex(REFERENCE.ContractError, "validity"):
                REFERENCE.validate_grant_for_plan(
                    grant, self.effect_plan, now_epoch=1786271400
                )

    def test_nonce_replay_is_rejected_and_mock_consumes_once(self) -> None:
        with self.assertRaisesRegex(REFERENCE.ContractError, "nonce replay"):
            REFERENCE.validate_grant_for_plan(
                self.grant,
                self.effect_plan,
                now_epoch=1786271400,
                consumed_nonces={self.grant["nonce"]},
            )
        mock = REFERENCE.MockConnector(self.capability)
        result = mock.execute_effect(
            self.effect_plan, self.grant, now_epoch=1786271400
        )
        self.assertTrue(result["accepted"])
        with self.assertRaisesRegex(REFERENCE.ContractError, "nonce replay"):
            mock.execute_effect(self.effect_plan, self.grant, now_epoch=1786271400)

    def test_stale_revocation_snapshot_is_rejected(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["revocation_snapshot_expires_epoch"] = 1786271400
        grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
        with self.assertRaisesRegex(REFERENCE.ContractError, "snapshot is stale"):
            REFERENCE.validate_grant_for_plan(
                grant, self.effect_plan, now_epoch=1786271400
            )

    def test_requesting_subject_and_one_time_target_set_are_bound(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["subject"] = {"id": "agent.other", "kind": "agent"}
        grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
        with self.assertRaisesRegex(REFERENCE.ContractError, "subject mismatch"):
            REFERENCE.validate_grant_for_plan(
                grant, self.effect_plan, now_epoch=1786271400
            )
        grant = copy.deepcopy(self.grant)
        grant["constraints"]["target_set_digest"] = "3" * 64
        grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
        with self.assertRaisesRegex(REFERENCE.ContractError, "target set"):
            REFERENCE.validate_grant_for_plan(
                grant, self.effect_plan, now_epoch=1786271400
            )

    def test_claims_digest_and_plan_digest_are_immutable_bindings(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["plan_digest"] = "1" * 64
        grant["claims_digest"] = REFERENCE.canonical_sha256(REFERENCE.grant_claims(grant))
        with self.assertRaisesRegex(REFERENCE.ContractError, "plan digest"):
            REFERENCE.validate_grant_for_plan(
                grant, self.effect_plan, now_epoch=1786271400
            )
        grant = copy.deepcopy(self.grant)
        grant["claims_digest"] = "2" * 64
        with self.assertRaisesRegex(REFERENCE.ContractError, "claims digest"):
            REFERENCE.validate_grant_for_plan(
                grant, self.effect_plan, now_epoch=1786271400
            )

    def test_success_receipt_requires_verified_terminal_evidence(self) -> None:
        for field, value in (
            ("verification_state", "failed"),
            ("terminal_state", "indeterminate"),
        ):
            receipt = copy.deepcopy(self.receipt)
            receipt[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_document(receipt)

    def test_indeterminate_cannot_be_presented_as_terminal(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt.update(
            outcome="indeterminate",
            verification_state="indeterminate",
            terminal_state="terminal",
        )
        with self.assertRaises(ValidationError):
            validate_document(receipt)

    def test_receipt_binding_rejects_cross_scope_evidence(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["tenant_id"] = "tenant.other"
        with self.assertRaisesRegex(REFERENCE.ContractError, "tenant_id"):
            REFERENCE.validate_receipt_for_plan(
                receipt, self.effect_plan, self.grant
            )

    def test_mock_separates_read_and_effect_paths(self) -> None:
        mock = REFERENCE.MockConnector(self.capability)
        snapshot = mock.read_snapshot("contact.snapshot", {"contact_id": 42})
        self.assertEqual(snapshot["contract_version"], REFERENCE.CONTRACT_VERSION)
        with self.assertRaisesRegex(REFERENCE.ContractError, "effect operation"):
            mock.read_snapshot("contact.tag.add", {"contact_id": 42})
        with self.assertRaisesRegex(REFERENCE.ContractError, "read operation"):
            mock.plan_effect(self.read_plan)

    def test_duplicate_operation_is_rejected(self) -> None:
        capability = copy.deepcopy(self.capability)
        capability["operations"].append(copy.deepcopy(capability["operations"][0]))
        with self.assertRaisesRegex(REFERENCE.ContractError, "duplicate"):
            validate_capability(capability)


if __name__ == "__main__":
    unittest.main()
