#!/usr/bin/env python3
"""Delegate expired coordination cleanup to intnode coord gc."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

INTNODE_BIN = os.environ.get("INTNODE_BIN", "intnode")


def resolve_intnode_bin() -> str:
    candidate = INTNODE_BIN.strip()
    if not candidate:
        raise RuntimeError("intnode command is empty")
    if "/" in candidate or "\\" in candidate or re.match(r"^[A-Za-z]:", candidate):
        path = Path(candidate).expanduser()
        if os.name == "nt" and not path.is_absolute() and candidate.startswith("/") and not candidate.startswith("//"):
            drives = [Path(__file__).resolve().drive, Path.cwd().drive, os.environ.get("SystemDrive", "")]
            seen: set[str] = set()
            for drive in drives:
                value = str(drive or "").strip()
                if not value:
                    continue
                if not value.endswith(":"):
                    value = f"{value}:"
                key = value.upper()
                if key in seen:
                    continue
                seen.add(key)
                candidate_path = Path(f"{value}{candidate}").expanduser()
                if candidate_path.exists():
                    path = candidate_path
                    break
            else:
                for drive in drives:
                    value = str(drive or "").strip()
                    if not value:
                        continue
                    if not value.endswith(":"):
                        value = f"{value}:"
                    path = Path(f"{value}{candidate}").expanduser()
                    break
        if path.exists():
            return str(path)
        raise RuntimeError(f"missing intnode: {path}")
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    raise RuntimeError(f"missing intnode in PATH: {candidate}")


def intnode_coord_cmd(*args: str) -> list[str]:
    intnode = resolve_intnode_bin()
    prefix = [sys.executable, intnode] if intnode.lower().endswith(".py") else [intnode]
    return [*prefix, "coord", *args]


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete expired coordination sessions and leases via intnode coord gc.")
    parser.add_argument("--dry-run", action="store_true", help="Print compatibility summary only.")
    args = parser.parse_args()

    try:
        cmd = intnode_coord_cmd("gc", "--dry-run" if args.dry_run else "--apply", "--format", "json")
    except RuntimeError as exc:
        print(f"[INTNODE_MISSING] {exc}", file=sys.stderr)
        return 2

    cp = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if cp.returncode != 0:
        print(cp.stderr.strip() or cp.stdout.strip() or "[INTNODE_COORD_FAILED] gc failed", file=sys.stderr)
        return cp.returncode
    try:
        payload = json.loads(cp.stdout)
    except json.JSONDecodeError:
        print(cp.stdout.strip(), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
