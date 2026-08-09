#!/usr/bin/env python3
"""Conformance helpers for Agent Host experimental-v0."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = CONTRACT_ROOT / "schema.json"
FIXTURES_DIR = CONTRACT_ROOT / "fixtures"
SECRET_KEY = re.compile(r"(?:api[_-]?key|access[_-]?token|password|secret)", re.I)
SECRET_VALUE = re.compile(r"(?:sk-[A-Za-z0-9]{16,}|gh[opsu]_[A-Za-z0-9]{20,})")


class ConformanceError(ValueError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_json(document: Any) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def request_wire_digest(request_line: bytes) -> str:
    """Digest exactly one received JSON line, excluding its line delimiter."""
    wire = request_line.rstrip(b"\r\n")
    if not wire or b"\n" in wire or b"\r" in wire:
        raise ConformanceError("request must be exactly one non-empty JSON line")
    return hashlib.sha256(wire).hexdigest()


def validator() -> Draft202012Validator:
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_document(document: Mapping[str, Any]) -> None:
    errors = sorted(validator().iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise ConformanceError("; ".join(error.message for error in errors))


def validate_event_sequence(events: Sequence[Mapping[str, Any]]) -> None:
    if not events:
        raise ConformanceError("event sequence must not be empty")
    fields = ("request_id", "run_id", "attempt_id", "fence_token")
    identity = tuple(events[0].get(field) for field in fields)
    terminal_seen = False
    for expected, event in enumerate(events, start=1):
        validate_document(event)
        if tuple(event.get(field) for field in fields) != identity:
            raise ConformanceError("event identity or fence changed within stream")
        if event["sequence"] != expected:
            raise ConformanceError("event sequence must be contiguous and monotonic")
        if terminal_seen:
            raise ConformanceError("events must not follow a terminal state")
        terminal_seen = event["event"] in {"terminal", "cancelled", "indeterminate"}


def validate_completed_response(events: Sequence[Mapping[str, Any]], receipt: Mapping[str, Any]) -> None:
    """Validate a completed start/watch response before a consumer accepts it."""
    validate_event_sequence(events)
    validate_document(receipt)
    final = events[-1]
    if final["event"] not in {"terminal", "cancelled", "indeterminate"}:
        raise ConformanceError("completed response must end with a terminal event")
    fields = ("request_id", "run_id", "attempt_id", "fence_token")
    if tuple(final[field] for field in fields) != tuple(receipt[field] for field in fields):
        raise ConformanceError("receipt identity or fence does not match terminal event")
    expected_status = "indeterminate" if final["event"] == "indeterminate" else "terminal"
    if receipt["status"] != expected_status:
        raise ConformanceError("receipt status does not match terminal event")


def validate_replay_receipt(original: Mapping[str, Any], replay: Mapping[str, Any]) -> None:
    validate_document(original)
    validate_document(replay)
    if canonical_json(original) != canonical_json(replay):
        raise ConformanceError("terminal receipt is immutable across replay")


def validate_artifact(path: Path, expected_sha256: str, expected_size: int | None = None) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ConformanceError("artifact SHA-256 mismatch")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise ConformanceError("artifact size mismatch")


def assert_redacted(document: Any, trail: tuple[str, ...] = ()) -> None:
    if isinstance(document, Mapping):
        for key, value in document.items():
            if SECRET_KEY.search(str(key)):
                raise ConformanceError(f"secret-like field at {'.'.join(trail + (str(key),))}")
            assert_redacted(value, trail + (str(key),))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            assert_redacted(value, trail + (str(index),))
    elif isinstance(document, str) and SECRET_VALUE.search(document):
        raise ConformanceError(f"secret-like value at {'.'.join(trail)}")


def run_fixture_suite() -> dict[str, int]:
    valid = [FIXTURES_DIR / name for name in ("request-start.json", "event-terminal.json", "receipt-terminal.json")]
    invalid = sorted(FIXTURES_DIR.glob("invalid-*.json"))
    for path in valid:
        document = load_json(path)
        validate_document(document)
        assert_redacted(document)
    for path in invalid:
        try:
            validate_document(load_json(path))
        except ConformanceError:
            continue
        raise ConformanceError(f"invalid fixture passed: {path.name}")
    return {"valid": len(valid), "invalid": len(invalid)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    if not args.paths:
        print(json.dumps({"ok": True, "fixtures": run_fixture_suite()}, sort_keys=True))
        return 0
    for path in args.paths:
        document = load_json(path)
        validate_document(document)
        assert_redacted(document)
    print(json.dumps({"ok": True, "validated": len(args.paths)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
