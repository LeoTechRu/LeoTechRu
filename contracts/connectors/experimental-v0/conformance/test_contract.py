from __future__ import annotations

import base64
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

from jsonschema import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_contract import (
    FIXTURE_REVOCATION,
    FIXTURE_VERIFIER,
    REFERENCE,
    load_fixture,
    validate_capability,
    validate_document,
    validate_fixture_set,
)


def b64url_json(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode()


class ConnectorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = load_fixture("connector-capability.json")
        self.read_plan = load_fixture("action-plan-read.json")
        self.effect_plan = load_fixture("action-plan-effect.json")
        self.grant = load_fixture("effect-grant.json")
        self.receipt = load_fixture("effect-receipt.json")

    def validate_grant(self, grant, plan=None, **kwargs) -> None:
        kwargs.setdefault("now_epoch", 1786271400)
        kwargs.setdefault("verifier", FIXTURE_VERIFIER)
        kwargs.setdefault("revocation_context", FIXTURE_REVOCATION)
        REFERENCE.validate_grant_for_plan(
            grant, plan or self.effect_plan, **kwargs
        )

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
            grant["claims_digest"] = REFERENCE.canonical_sha256(
                REFERENCE.grant_claims(grant)
            )
            with self.subTest(field=field), self.assertRaisesRegex(
                REFERENCE.ContractError, message
            ):
                self.validate_grant(grant)

    def test_plan_connection_operation_target_and_policy_are_bound(self) -> None:
        for field, value in (
            ("connection_id", "connection.other"),
            ("operation", "contact.tag.remove"),
            ("target_digest", "1" * 64),
            ("policy_revision", 8),
        ):
            grant = copy.deepcopy(self.grant)
            grant[field] = value
            grant["claims_digest"] = REFERENCE.canonical_sha256(
                REFERENCE.grant_claims(grant)
            )
            with self.subTest(field=field), self.assertRaisesRegex(
                REFERENCE.ContractError, field
            ):
                self.validate_grant(grant)

    def test_expired_future_and_malformed_validity_fail_closed(self) -> None:
        for field, value in (
            ("expires_epoch", 1786271300),
            ("not_before_epoch", 1786271500),
            ("expires_epoch", 1786269500),
        ):
            grant = copy.deepcopy(self.grant)
            grant[field] = value
            grant["claims_digest"] = REFERENCE.canonical_sha256(
                REFERENCE.grant_claims(grant)
            )
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                REFERENCE.ContractError, "validity"
            ):
                self.validate_grant(grant)

    def test_missing_trusted_verifier_fails_closed(self) -> None:
        with self.assertRaisesRegex(REFERENCE.ContractError, "verifier is required"):
            self.validate_grant(self.grant, verifier=None)
        mock = REFERENCE.MockConnector(
            self.capability, revocation_context=FIXTURE_REVOCATION
        )
        with self.assertRaisesRegex(REFERENCE.ContractError, "verifier is required"):
            mock.execute_effect(self.effect_plan, self.grant, now_epoch=1786271400)
        with self.assertRaisesRegex(REFERENCE.ContractError, "revocation context is required"):
            self.validate_grant(self.grant, revocation_context=None)

    def test_alg_none_and_untrusted_header_are_rejected(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["signature"]["alg"] = "none"
        with self.assertRaises(ValidationError):
            validate_document(grant)
        with self.assertRaisesRegex(REFERENCE.ContractError, "unsupported"):
            self.validate_grant(grant)

    def test_unrelated_payload_is_rejected_before_verifier(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["signature"]["payload"] = b64url_json({"issuer": grant["issuer"]})
        with self.assertRaisesRegex(REFERENCE.ContractError, "exact grant claims"):
            self.validate_grant(grant)
        grant = copy.deepcopy(self.grant)
        claims = REFERENCE.grant_claims(grant)
        noncanonical = json.dumps(claims, sort_keys=False, indent=1).encode()
        grant["signature"]["payload"] = (
            base64.urlsafe_b64encode(noncanonical).rstrip(b"=").decode()
        )
        with self.assertRaisesRegex(REFERENCE.ContractError, "not canonical"):
            self.validate_grant(grant)

    def test_fake_signature_is_rejected_by_trusted_verifier(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["signature"]["signature"] = "B" * 86
        with self.assertRaisesRegex(REFERENCE.ContractError, "verification failed"):
            self.validate_grant(grant)

    def test_nonce_replay_is_rejected_and_mock_consumes_once(self) -> None:
        with self.assertRaisesRegex(REFERENCE.ContractError, "nonce replay"):
            self.validate_grant(
                self.grant, consumed_nonces={self.grant["nonce"]}
            )
        mock = REFERENCE.MockConnector(
            self.capability,
            verifier=FIXTURE_VERIFIER,
            revocation_context=FIXTURE_REVOCATION,
        )
        result = mock.execute_effect(
            self.effect_plan, self.grant, now_epoch=1786271400
        )
        self.assertTrue(result["accepted"])
        with self.assertRaisesRegex(REFERENCE.ContractError, "nonce replay"):
            mock.execute_effect(self.effect_plan, self.grant, now_epoch=1786271400)

    def test_revocation_context_is_trusted_current_and_scope_bound(self) -> None:
        cases = (
            (
                FIXTURE_REVOCATION,
                "context is stale",
                1786272600,
            ),
            (
                replace(FIXTURE_REVOCATION, snapshot_digest="3" * 64),
                "snapshot_digest mismatch",
                1786271400,
            ),
            (
                replace(FIXTURE_REVOCATION, revision=5),
                "revision mismatch",
                1786271400,
            ),
            (
                replace(
                    FIXTURE_REVOCATION,
                    revoked_nonces=frozenset({self.grant["nonce"]}),
                ),
                "nonce is revoked",
                1786271400,
            ),
            (
                replace(FIXTURE_REVOCATION, signature_verified=False),
                "context is required",
                1786271400,
            ),
        )
        for context, message, now_epoch in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                REFERENCE.ContractError, message
            ):
                self.validate_grant(
                    self.grant,
                    revocation_context=context,
                    now_epoch=now_epoch,
                )

    def test_requesting_subject_and_target_set_are_bound(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["subject"] = {"id": "agent.other", "kind": "agent"}
        grant["claims_digest"] = REFERENCE.canonical_sha256(
            REFERENCE.grant_claims(grant)
        )
        with self.assertRaisesRegex(REFERENCE.ContractError, "subject mismatch"):
            self.validate_grant(grant)
        grant = copy.deepcopy(self.grant)
        grant.update(grant_class="persistent")
        grant["constraints"].update(
            max_effects=100,
            rate_per_minute=10,
            schedule_digest="4" * 64,
            target_set_digest="3" * 64,
        )
        grant["claims_digest"] = REFERENCE.canonical_sha256(
            REFERENCE.grant_claims(grant)
        )
        with self.assertRaisesRegex(REFERENCE.ContractError, "target set mismatch"):
            self.validate_grant(grant)

    def test_claims_digest_and_plan_digest_are_immutable_bindings(self) -> None:
        grant = copy.deepcopy(self.grant)
        grant["plan_digest"] = "1" * 64
        grant["claims_digest"] = REFERENCE.canonical_sha256(
            REFERENCE.grant_claims(grant)
        )
        with self.assertRaisesRegex(REFERENCE.ContractError, "plan digest"):
            self.validate_grant(grant)
        grant = copy.deepcopy(self.grant)
        grant["claims_digest"] = "2" * 64
        with self.assertRaisesRegex(REFERENCE.ContractError, "claims digest"):
            self.validate_grant(grant)

    def test_receipt_outcome_matrix_is_closed(self) -> None:
        invalid = (
            ("succeeded", "failed", "terminal"),
            ("failed", "indeterminate", "indeterminate"),
            ("cancelled", "failed", "terminal"),
            ("indeterminate", "indeterminate", "terminal"),
        )
        for outcome, verification, terminal in invalid:
            receipt = copy.deepcopy(self.receipt)
            receipt.update(
                outcome=outcome,
                verification_state=verification,
                terminal_state=terminal,
            )
            with self.subTest(outcome=outcome), self.assertRaises(ValidationError):
                validate_document(receipt)
            with self.assertRaisesRegex(REFERENCE.ContractError, "matrix"):
                REFERENCE.validate_receipt_for_plan(
                    receipt, self.effect_plan, self.grant
                )

    def test_receipt_binding_rejects_cross_scope_evidence(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["tenant_id"] = "tenant.other"
        with self.assertRaisesRegex(REFERENCE.ContractError, "tenant_id"):
            REFERENCE.validate_receipt_for_plan(
                receipt, self.effect_plan, self.grant
            )

    def test_receipt_timestamps_are_compared_as_utc_instants(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["started_at"] = "2026-08-09T10:01:00.900Z"
        receipt["ended_at"] = "2026-08-09T10:01:00.100Z"
        validate_document(receipt)
        with self.assertRaisesRegex(REFERENCE.ContractError, "timing"):
            REFERENCE.validate_receipt_for_plan(
                receipt, self.effect_plan, self.grant
            )

    def test_indeterminate_error_is_reconcile_only(self) -> None:
        error = load_fixture("connector-error.json")
        error["retry_class"] = "bounded"
        with self.assertRaises(ValidationError):
            validate_document(error)

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
