"""Independent validation helpers for provider-experimental-v0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
SECRET_LIKE = re.compile(
    r"(?i)(?:sk-|bearer\s|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"private[_-]?key|password|secret)"
)


class ContractError(ValueError):
    """Raised when cross-document provider semantics are inconsistent."""


def validate_document(document: Mapping[str, Any]) -> None:
    VALIDATOR.validate(document)
    _reject_secret_like_values(document)


def canonical_sha256(document: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_secret_like_values(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_secret_like_values(child, path=(*path, str(key)))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like_values(child, path=(*path, str(index)))
        return
    if not isinstance(value, str) or path == ("prompt",):
        return
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ContractError(f"control character in metadata at {'.'.join(path)}")
    if SECRET_LIKE.search(value):
        raise ContractError(f"secret-like metadata at {'.'.join(path)}")


def validate_provider_pair(
    descriptor: Mapping[str, Any], invocation: Mapping[str, Any]
) -> None:
    validate_document(descriptor)
    validate_document(invocation)
    if descriptor["message_type"] != "provider_descriptor":
        raise ContractError("descriptor message_type is invalid")
    if invocation["message_type"] != "provider_invocation":
        raise ContractError("invocation message_type is invalid")
    if descriptor["provider_id"] != invocation["provider_id"]:
        raise ContractError("provider mismatch")
    if invocation["provider_id"] == "hermes":
        raise ContractError("provider unavailable")
    if descriptor["runtime_status"] != "available":
        raise ContractError("provider unavailable")
    if invocation["execution_mode"] not in descriptor["supported_modes"]:
        raise ContractError("execution mode unsupported")
    if invocation["verifier_profile"] not in descriptor["verifier_profiles"]:
        raise ContractError("verifier profile unsupported")


def validate_artifact_for_invocation(
    invocation: Mapping[str, Any], artifact: Mapping[str, Any]
) -> None:
    validate_document(invocation)
    validate_document(artifact)
    if invocation["message_type"] != "provider_invocation":
        raise ContractError("invocation message_type is invalid")
    if artifact["message_type"] != "provider_execution_artifact":
        raise ContractError("artifact message_type is invalid")
    if artifact["provider_id"] != invocation["provider_id"]:
        raise ContractError("provider mismatch")
    if artifact["invocation_sha256"] != canonical_sha256(invocation):
        raise ContractError("invocation digest mismatch")
    if artifact["runtime"] != invocation["runtime_pin"]:
        raise ContractError("runtime pin mismatch")
    if artifact["base_tree_sha256"] != invocation["base_tree_sha256"]:
        raise ContractError("base tree mismatch")
    allowed = set(invocation["allowed_paths"])
    changed_entries = artifact["changed_paths"]
    changed = {entry["path"] for entry in changed_entries}
    if len(changed) != len(changed_entries):
        raise ContractError("duplicate changed path")
    for entry in changed_entries:
        before = entry["before_sha256"]
        after = entry["after_sha256"]
        if before is None and after is None:
            raise ContractError("changed path has no content identity")
        if before == after:
            raise ContractError("changed path hashes are equal")
    if not changed.issubset(allowed):
        raise ContractError("changed path outside allowlist")
    if artifact["patch"]["size_bytes"] > invocation["limits"]["max_patch_bytes"]:
        raise ContractError("patch exceeds invocation limit")
    if artifact["provider_output"]["size_bytes"] > invocation["limits"]["max_total_bytes"]:
        raise ContractError("provider output exceeds invocation limit")
    verifier = artifact["verifier"]
    if verifier["passed"] != (verifier["exit_code"] == 0):
        raise ContractError("verifier result contradicts exit code")
    sequences = [event["sequence"] for event in artifact["provider_events"]]
    if sequences != list(range(1, len(sequences) + 1)):
        raise ContractError("provider event sequence is not contiguous")
    if len(sequences) != artifact["provider_output"]["event_count"]:
        raise ContractError("provider event count is incomplete")
    event_sizes = [event["size_bytes"] for event in artifact["provider_events"]]
    if any(size > invocation["limits"]["max_line_bytes"] for size in event_sizes):
        raise ContractError("provider event exceeds invocation line limit")
    if sum(event_sizes) != artifact["provider_output"]["size_bytes"]:
        raise ContractError("provider event sizes contradict total output")


def load_fixture(name: str) -> dict[str, Any]:
    value = json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("fixture must be an object")
    return value


if __name__ == "__main__":
    fixtures = sorted((ROOT / "fixtures").glob("*.json"))
    for fixture in fixtures:
        value = json.loads(fixture.read_text(encoding="utf-8"))
        validate_document(value)
    print(json.dumps({"ok": True, "fixtures": len(fixtures)}, sort_keys=True))
