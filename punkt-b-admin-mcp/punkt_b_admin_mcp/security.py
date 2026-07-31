from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


SECRET_PARTS = ("token", "secret", "password", "cookie", "authorization", "webhook", "api_key", "apikey")
PII_PARTS = ("email", "phone", "message", "body", "content")


class GatewayError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def validate_json_schema(value: Any, schema: dict[str, Any], *, path: str = "input") -> None:
    """Validate the bounded JSON-Schema subset used by the committed registry."""
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise GatewayError("INVALID_INPUT", f"{path} must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise GatewayError("INVALID_INPUT", f"{path} is missing required fields")
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(properties)
            if unknown:
                raise GatewayError("INVALID_INPUT", f"{path} contains unknown fields")
        for key, item in value.items():
            child = properties.get(key)
            if isinstance(child, dict):
                validate_json_schema(item, child, path=f"{path}.{key}")
        return
    if expected == "array":
        if not isinstance(value, list):
            raise GatewayError("INVALID_INPUT", f"{path} must be an array")
        if len(value) > int(schema.get("maxItems", len(value))):
            raise GatewayError("INVALID_INPUT", f"{path} is too large")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_json_schema(item, item_schema, path=f"{path}[{index}]")
        return
    if expected == "string":
        if not isinstance(value, str):
            raise GatewayError("INVALID_INPUT", f"{path} must be a string")
        if len(value) < int(schema.get("minLength", 0)) or len(value) > int(schema.get("maxLength", len(value))):
            raise GatewayError("INVALID_INPUT", f"{path} length is outside the allowed range")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise GatewayError("INVALID_INPUT", f"{path} must be an integer")
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GatewayError("INVALID_INPUT", f"{path} must be a number")
    elif expected == "boolean" and not isinstance(value, bool):
        raise GatewayError("INVALID_INPUT", f"{path} must be a boolean")
    if "minimum" in schema and value < schema["minimum"]:
        raise GatewayError("INVALID_INPUT", f"{path} is below the minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise GatewayError("INVALID_INPUT", f"{path} exceeds the maximum")
    if "enum" in schema and value not in schema["enum"]:
        raise GatewayError("INVALID_INPUT", f"{path} is not an allowed value")


def redact(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "..."
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            lowered = str(key).lower()
            if any(part in lowered for part in SECRET_PARTS + PII_PARTS):
                result[str(key)] = "***redacted***"
            else:
                result[str(key)] = redact(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [redact(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        value = re.sub(r"(?i)bearer\s+[a-z0-9._~-]+", "Bearer ***redacted***", value)
        return value[:4000]
    return value


def canonical_preview_hash(preview: Any) -> str:
    encoded = json.dumps(preview, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class WriteApproval:
    idempotency_key: str
    target: str
    preview: Any


def validate_write_gates(payload: dict[str, Any]) -> WriteApproval:
    if payload.get("confirm_write") is not True:
        raise GatewayError("WRITE_CONFIRMATION_REQUIRED", "confirm_write=true is required")
    key = payload.get("idempotency_key")
    target = payload.get("target")
    preview = payload.get("preview")
    supplied_hash = payload.get("preview_hash")
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise GatewayError("INVALID_IDEMPOTENCY_KEY", "A bounded idempotency_key is required")
    if not isinstance(target, str) or not target.strip() or len(target) > 500:
        raise GatewayError("INVALID_TARGET", "An exact bounded target is required")
    if preview is None:
        raise GatewayError("PREVIEW_REQUIRED", "preview is required")
    expected_hash = canonical_preview_hash(preview)
    if not isinstance(supplied_hash, str) or supplied_hash != expected_hash:
        raise GatewayError("PREVIEW_HASH_MISMATCH", "preview_hash does not match preview")
    return WriteApproval(key.strip(), target.strip(), preview)


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, actor: str, tool_name: str, limit_per_minute: int) -> None:
        now = time.monotonic()
        events = self._events[(actor, tool_name)]
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= limit_per_minute:
            raise GatewayError("RATE_LIMITED", "Tool rate limit exceeded", retryable=True)
        events.append(now)


class IdempotencyGuard:
    """Reject repeated write keys before a service adapter can run.

    The dev gateway has all effect flags disabled. This process-local guard is
    an additional safety boundary for tests and future explicitly enabled dev
    effects; production requires a durable shared receipt store.
    """

    def __init__(self) -> None:
        self._reservations: dict[tuple[str, str], str] = {}

    def reserve(self, tool_name: str, approval: WriteApproval) -> None:
        identity = (tool_name, approval.idempotency_key)
        fingerprint = canonical_preview_hash({
            "target": approval.target,
            "preview": approval.preview,
        })
        if identity in self._reservations:
            raise GatewayError(
                "DUPLICATE_IDEMPOTENCY_KEY",
                "The idempotency_key was already used for this tool",
            )
        self._reservations[identity] = fingerprint
