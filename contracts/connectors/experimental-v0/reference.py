"""Stdlib-only reference Protocol and deterministic connector mock."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, MutableSet, Protocol, Sequence


CONTRACT_VERSION = "connectors-experimental-v0"
BRIDGE_AUDIENCE = "intdata-bridge"


class ContractError(ValueError):
    """A document pair fails a fail-closed cross-document invariant."""


def canonical_json(document: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON for digest binding.

    Contract schemas permit integers but no floating-point values, so the
    standard encoder has a stable numeric representation for valid documents.
    """

    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


def grant_claims(grant: Mapping[str, Any]) -> dict[str, Any]:
    claims = deepcopy(dict(grant))
    claims.pop("signature", None)
    claims.pop("claims_digest", None)
    return claims


def negotiate_version(
    offered: Sequence[str], supported: Sequence[str] = (CONTRACT_VERSION,)
) -> str:
    """Select only the exact experimental contract; no implicit downgrade."""

    offered_set = set(offered)
    for version in supported:
        if version == CONTRACT_VERSION and version in offered_set:
            return version
    raise ContractError("no exact supported contract version")


def validate_grant_for_plan(
    grant: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    now_epoch: int,
    consumed_nonces: set[str] | frozenset[str] = frozenset(),
) -> None:
    """Validate semantic binding; cryptographic JWS verification is external."""

    if plan.get("contract_version") != CONTRACT_VERSION:
        raise ContractError("unsupported plan contract version")
    if grant.get("contract_version") != CONTRACT_VERSION:
        raise ContractError("unsupported grant contract version")
    if plan.get("effect_class") != "provider_effect" or not plan.get("grant_required"):
        raise ContractError("grants apply only to provider effects")
    if grant.get("audience") != BRIDGE_AUDIENCE:
        raise ContractError("wrong grant audience")
    expected = {
        "tenant_id": plan.get("tenant_id"),
        "contour": plan.get("contour"),
        "connection_id": plan.get("connection_id"),
        "operation": plan.get("operation"),
        "target_digest": plan.get("target_digest"),
        "authorization_decision_digest": plan.get("authorization_decision_digest"),
        "policy_revision": plan.get("policy_revision"),
        "approving_principal": plan.get("approving_principal"),
        "approving_role": plan.get("approving_role"),
        "subject": plan.get("requesting_principal"),
    }
    for field, value in expected.items():
        if grant.get(field) != value:
            raise ContractError(f"grant {field} mismatch")
    if grant.get("plan_digest") != canonical_sha256(plan):
        raise ContractError("grant plan digest mismatch")
    if grant.get("claims_digest") != canonical_sha256(grant_claims(grant)):
        raise ContractError("grant claims digest mismatch")
    not_before = grant.get("not_before_epoch")
    expires = grant.get("expires_epoch")
    if not isinstance(not_before, int) or not isinstance(expires, int):
        raise ContractError("grant validity is malformed")
    if not_before > now_epoch or expires <= now_epoch or expires <= not_before:
        raise ContractError("grant is outside validity window")
    snapshot_issued = grant.get("revocation_snapshot_issued_epoch")
    snapshot_expires = grant.get("revocation_snapshot_expires_epoch")
    if not isinstance(snapshot_issued, int) or not isinstance(snapshot_expires, int):
        raise ContractError("revocation snapshot validity is malformed")
    if snapshot_issued > now_epoch or snapshot_expires <= now_epoch:
        raise ContractError("revocation snapshot is stale")
    if snapshot_expires <= snapshot_issued:
        raise ContractError("revocation snapshot validity is malformed")
    constraints = grant.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ContractError("grant constraints are malformed")
    if grant.get("grant_class") == "one_time":
        if constraints.get("max_effects") != 1:
            raise ContractError("one-time grant exceeds one effect")
        if constraints.get("target_set_digest") != plan.get("target_digest"):
            raise ContractError("one-time grant target set mismatch")
    nonce = grant.get("nonce")
    if not isinstance(nonce, str) or nonce in consumed_nonces:
        raise ContractError("grant nonce replay")


def validate_receipt_for_plan(
    receipt: Mapping[str, Any],
    plan: Mapping[str, Any],
    grant: Mapping[str, Any],
) -> None:
    expected = {
        "tenant_id": plan.get("tenant_id"),
        "contour": plan.get("contour"),
        "connection_id": plan.get("connection_id"),
        "operation": plan.get("operation"),
        "plan_digest": canonical_sha256(plan),
        "grant_digest": canonical_sha256(grant),
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ContractError(f"receipt {field} mismatch")
    outcome = receipt.get("outcome")
    if outcome == "succeeded" and (
        receipt.get("verification_state") != "verified"
        or receipt.get("terminal_state") != "terminal"
    ):
        raise ContractError("success lacks verified terminal evidence")
    if outcome == "indeterminate" and receipt.get("terminal_state") != "indeterminate":
        raise ContractError("indeterminate outcome was hidden")
    started_at = receipt.get("started_at")
    ended_at = receipt.get("ended_at")
    if not isinstance(started_at, str) or not isinstance(ended_at, str) or ended_at < started_at:
        raise ContractError("receipt timing is inconsistent")


class ConnectorProtocol(Protocol):
    """Portable connector seam. Implementations remain in their owning repo."""

    def describe(self) -> Mapping[str, Any]: ...

    def read_snapshot(
        self, operation: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def plan_effect(self, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def execute_effect(
        self,
        plan: Mapping[str, Any],
        grant: Mapping[str, Any],
        *,
        now_epoch: int,
    ) -> Mapping[str, Any]: ...


class MockConnector:
    """Deterministic no-I/O reference mock for consumer conformance tests."""

    def __init__(self, capability: Mapping[str, Any]) -> None:
        self._capability = deepcopy(dict(capability))
        self._consumed_nonces: MutableSet[str] = set()

    def describe(self) -> Mapping[str, Any]:
        return deepcopy(self._capability)

    def _operation(self, operation: str) -> Mapping[str, Any]:
        matches = [
            item
            for item in self._capability["operations"]
            if item["operation"] == operation
        ]
        if len(matches) != 1:
            raise ContractError("operation is unsupported or ambiguous")
        return matches[0]

    def read_snapshot(
        self, operation: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        capability = self._operation(operation)
        if capability["effect_class"] != "read_snapshot":
            raise ContractError("effect operation cannot use read path")
        if capability["network_methods"] != ["GET"] or capability["grant_required"]:
            raise ContractError("read capability is not GET-only")
        return {
            "contract_version": CONTRACT_VERSION,
            "operation": operation,
            "snapshot_digest": canonical_sha256(request),
        }

    def plan_effect(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        capability = self._operation(str(plan.get("operation", "")))
        if capability["effect_class"] != "provider_effect":
            raise ContractError("read operation cannot use effect path")
        if plan.get("effect_class") != "provider_effect" or not plan.get("grant_required"):
            raise ContractError("effect plan is not grant-gated")
        return deepcopy(dict(plan))

    def execute_effect(
        self,
        plan: Mapping[str, Any],
        grant: Mapping[str, Any],
        *,
        now_epoch: int,
    ) -> Mapping[str, Any]:
        self.plan_effect(plan)
        validate_grant_for_plan(
            grant,
            plan,
            now_epoch=now_epoch,
            consumed_nonces=set(self._consumed_nonces),
        )
        nonce = str(grant["nonce"])
        self._consumed_nonces.add(nonce)
        return {
            "accepted": True,
            "plan_digest": canonical_sha256(plan),
            "grant_digest": canonical_sha256(grant),
            "nonce": nonce,
        }
