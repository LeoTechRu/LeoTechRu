"""Single-command offline entry point for the published PPA conformance corpus."""

from __future__ import annotations

import hashlib
import json
import sys
from types import ModuleType
from typing import Sequence

from ._integrity import IntegrityError, PLATFORM_ROOT, RAW_SHA256, verify_embedded


def _emit(value: dict[str, str]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _load_published_validator() -> ModuleType:
    relative_path = "conformance/validate-terminal-dependencies.py"
    source = PLATFORM_ROOT / relative_path
    try:
        source_bytes = source.read_bytes()
    except OSError as error:
        raise IntegrityError(f"missing-resource:{relative_path}") from error
    if hashlib.sha256(source_bytes).hexdigest() != RAW_SHA256[relative_path]:
        raise IntegrityError(f"raw-sha256:{relative_path}")
    module = ModuleType("_intdata_published_ppa_validator")
    module.__file__ = str(source)
    exec(compile(source_bytes, str(source), "exec", dont_inherit=True), module.__dict__)
    return module


def run() -> dict[str, int]:
    """Run unchanged published validator logic after integrity verification."""
    verify_embedded()
    validator = _load_published_validator()
    return validator.run()


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        _emit({"code": "invalid_invocation", "error": "expected_no_arguments"})
        return 64
    try:
        checked = run()
    except IntegrityError as error:
        _emit({"code": "integrity_failed", "error": str(error)})
        return 2
    except Exception as error:
        _emit({"code": "validation_failed", "error": str(getattr(error, "reason", "validation_failed"))})
        return 1
    print(json.dumps({"ok": True, "checked": checked}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
