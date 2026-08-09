"""Stdlib-only reference Protocol and deterministic connector mock."""

from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, MutableSet, Protocol, Sequence


CONTRACT_VERSION = "connectors-experimental-v0"
BRIDGE_AUDIENCE = "intdata-bridge"


class ContractError(ValueError):
    """A document pair fails a fail-closed cross-document invariant."""


class TrustedJwsVerifier(Protocol):
    """Configured cryptographic authority; implementations own trusted JWKS."""

    def verify(
        self,
        *,
        issuer: str,
        kid: str,
        alg: str,
        signing_input: bytes,
        signature: bytes,
    ) -> bool: ...


@dataclass(frozen=True)
class TrustedRevocationContext:
    """Signature-verified revocation state supplied outside the grant."""

    issuer: str
    snapshot_digest: str
    revision: int
    issued_epoch: int
    expires_epoch: int
    revoked_nonces: frozenset[str]
    signature_verified: bool


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


def _b64url_decode(value: Any, *, field: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ContractError(f"{field} is not strict base64url")
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError) as error:
        raise ContractError(f"{field} is not valid base64url") from error


def _load_closed_json(raw: bytes, *, field: str) -> dict[str, Any]:
    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"duplicate key in {field}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=closed_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"{field} is not a JSON object") from error
    if not isinstance(value, dict):
        raise ContractError(f"{field} is not a JSON object")
    return value


def _verify_jws(
    grant: Mapping[str, Any], verifier: TrustedJwsVerifier | None
) -> None:
    if verifier is None:
        raise ContractError("trusted JWS verifier is required")
    signature_block = grant.get("signature")
    if not isinstance(signature_block, Mapping):
        raise ContractError("grant signature is malformed")
    alg = signature_block.get("alg")
    kid = signature_block.get("kid")
    issuer = grant.get("issuer")
    if alg != "EdDSA" or not isinstance(kid, str) or not isinstance(issuer, str):
        raise ContractError("grant signature authority is unsupported")
    protected_text = signature_block.get("protected")
    payload_text = signature_block.get("payload")
    if not isinstance(protected_text, str) or not isinstance(payload_text, str):
        raise ContractError("grant compact JWS is malformed")
    protected_raw = _b64url_decode(protected_text, field="protected header")
    protected = _load_closed_json(protected_raw, field="protected header")
    if set(protected) != {"alg", "kid", "typ"}:
        raise ContractError("protected header is not closed")
    if protected != {"alg": "EdDSA", "kid": kid, "typ": "JWT"}:
        raise ContractError("protected header authority mismatch")
    if protected_raw != canonical_json(protected):
        raise ContractError("protected header is not canonical JSON")
    payload_raw = _b64url_decode(payload_text, field="JWS payload")
    payload = _load_closed_json(payload_raw, field="JWS payload")
    claims = grant_claims(grant)
    if payload != claims:
        raise ContractError("JWS payload does not bind exact grant claims")
    if payload_raw != canonical_json(claims):
        raise ContractError("JWS payload is not canonical JSON")
    signature = _b64url_decode(signature_block.get("signature"), field="JWS signature")
    if len(signature) != 64:
        raise ContractError("Ed25519 signature length is invalid")
    signing_input = f"{protected_text}.{payload_text}".encode("ascii")
    try:
        verified = verifier.verify(
            issuer=issuer,
            kid=kid,
            alg=alg,
            signing_input=signing_input,
            signature=signature,
        )
    except Exception as error:
        raise ContractError("trusted JWS verification failed") from error
    if verified is not True:
        raise ContractError("trusted JWS verification failed")


def _validate_revocation_context(
    grant: Mapping[str, Any],
    context: TrustedRevocationContext | None,
    *,
    now_epoch: int,
) -> None:
    if context is None or context.signature_verified is not True:
        raise ContractError("trusted revocation context is required")
    expected = {
        "issuer": grant.get("issuer"),
        "snapshot_digest": grant.get("revocation_snapshot_digest"),
        "revision": grant.get("revocation_snapshot_revision"),
        "issued_epoch": grant.get("revocation_snapshot_issued_epoch"),
        "expires_epoch": grant.get("revocation_snapshot_expires_epoch"),
    }
    for field, value in expected.items():
        if getattr(context, field) != value:
            raise ContractError(f"revocation context {field} mismatch")
    if context.issued_epoch > now_epoch or context.expires_epoch <= now_epoch:
        raise ContractError("trusted revocation context is stale")
    if context.expires_epoch <= context.issued_epoch:
        raise ContractError("trusted revocation context validity is malformed")
    nonce = grant.get("nonce")
    if nonce in context.revoked_nonces:
        raise ContractError("grant nonce is revoked")


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
    verifier: TrustedJwsVerifier | None = None,
    revocation_context: TrustedRevocationContext | None = None,
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
    constraints = grant.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ContractError("grant constraints are malformed")
    if constraints.get("target_set_digest") != plan.get("target_digest"):
        raise ContractError("grant target set mismatch")
    if grant.get("grant_class") == "one_time" and constraints.get("max_effects") != 1:
        raise ContractError("one-time grant exceeds one effect")
    not_before = grant.get("not_before_epoch")
    expires = grant.get("expires_epoch")
    if not isinstance(not_before, int) or not isinstance(expires, int):
        raise ContractError("grant validity is malformed")
    if not_before > now_epoch or expires <= now_epoch or expires <= not_before:
        raise ContractError("grant is outside validity window")
    if grant.get("claims_digest") != canonical_sha256(grant_claims(grant)):
        raise ContractError("grant claims digest mismatch")
    _verify_jws(grant, verifier)
    _validate_revocation_context(grant, revocation_context, now_epoch=now_epoch)
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
    matrix = {
        "succeeded": ("verified", "terminal"),
        "failed": ("failed", "terminal"),
        "cancelled": ("not_applicable", "terminal"),
        "indeterminate": ("indeterminate", "indeterminate"),
    }
    expected_state = matrix.get(outcome)
    actual_state = (
        receipt.get("verification_state"),
        receipt.get("terminal_state"),
    )
    if expected_state is None or actual_state != expected_state:
        raise ContractError("receipt outcome evidence matrix mismatch")
    started_at = _parse_rfc3339_utc(receipt.get("started_at"), field="started_at")
    ended_at = _parse_rfc3339_utc(receipt.get("ended_at"), field="ended_at")
    if ended_at < started_at:
        raise ContractError("receipt timing is inconsistent")


def _parse_rfc3339_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ):
        raise ContractError(f"{field} is not RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ContractError(f"{field} is not RFC3339 UTC") from error
    if parsed.tzinfo != timezone.utc:
        raise ContractError(f"{field} is not RFC3339 UTC")
    return parsed


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

    def __init__(
        self,
        capability: Mapping[str, Any],
        *,
        verifier: TrustedJwsVerifier | None = None,
        revocation_context: TrustedRevocationContext | None = None,
    ) -> None:
        self._capability = deepcopy(dict(capability))
        self._consumed_nonces: MutableSet[str] = set()
        self._verifier = verifier
        self._revocation_context = revocation_context

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
            verifier=self._verifier,
            revocation_context=self._revocation_context,
        )
        nonce = str(grant["nonce"])
        self._consumed_nonces.add(nonce)
        return {
            "accepted": True,
            "plan_digest": canonical_sha256(plan),
            "grant_digest": canonical_sha256(grant),
            "nonce": nonce,
        }
