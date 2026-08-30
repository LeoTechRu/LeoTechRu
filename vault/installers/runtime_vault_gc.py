#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys


UTC = timezone.utc


def now_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def canonical_runtime_root(brain_root: Path) -> Path:
    return (brain_root.parent / ".tmp" / "brain-runtime-vault").resolve()


def legacy_runtime_root(brain_root: Path) -> Path:
    return (brain_root / "runtime" / "vault").resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive and clean vault runtime artifacts (canonical root in .tmp)."
    )
    parser.add_argument("--brain-root", default="dev@intdata.pro:/int/brain", help="int/brain repo root on dev@intdata.pro.")
    parser.add_argument(
        "--runtime-root",
        default="",
        help="Runtime root override. Default: <brain-root parent>/.tmp/brain-runtime-vault",
    )
    parser.add_argument(
        "--archive-root",
        default="",
        help="Archive base directory. Default: <brain-root parent>/.tmp",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes only.")
    parser.add_argument("--apply", action="store_true", help="Apply archive + cleanup.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and args.dry_run:
        raise SystemExit("Use either --dry-run or --apply, not both.")
    if not args.apply and not args.dry_run:
        args.dry_run = True

    brain_root = Path(args.brain_root).expanduser().resolve()
    if not brain_root.exists():
        raise SystemExit(f"brain_root_not_found: {brain_root}")

    canonical_root = canonical_runtime_root(brain_root)
    legacy_root = legacy_runtime_root(brain_root)
    runtime_root = (
        Path(args.runtime_root).expanduser().resolve()
        if args.runtime_root
        else canonical_root
    )
    using_legacy_override = runtime_root == legacy_root
    if using_legacy_override:
        print(
            "warning: --runtime-root points to legacy path; prefer canonical <brain-root parent>/.tmp/brain-runtime-vault",
            file=sys.stderr,
        )

    archive_base = (
        Path(args.archive_root).expanduser().resolve()
        if args.archive_root
        else (brain_root.parent / ".tmp").resolve()
    )

    stamp = now_stamp()
    archive_runtime_dir = archive_base / stamp / "brain-runtime-vault"
    archive_legacy_dir = archive_base / stamp / "brain-runtime-vault-legacy"
    preserve_dirs = [
        runtime_root / "artifacts",
        runtime_root / "manifests",
        runtime_root / "non_whitelist",
    ]

    entries: list[str] = []
    if runtime_root.exists():
        for item in sorted(runtime_root.rglob("*")):
            entries.append(str(item))

    legacy_entries: list[str] = []
    if legacy_root.exists() and legacy_root != runtime_root:
        for item in sorted(legacy_root.rglob("*")):
            legacy_entries.append(str(item))

    planned_actions: list[dict[str, object]] = []
    if runtime_root.exists():
        planned_actions.append(
            {
                "action": "archive_runtime_root",
                "source": str(runtime_root),
                "destination": str(archive_runtime_dir),
            }
        )
    if legacy_root.exists() and legacy_root != runtime_root:
        planned_actions.append(
            {
                "action": "archive_legacy_root",
                "source": str(legacy_root),
                "destination": str(archive_legacy_dir),
            }
        )
        planned_actions.append(
            {
                "action": "recreate_empty_legacy_root",
                "path": str(legacy_root),
            }
        )
    planned_actions.append(
        {
            "action": "recreate_runtime_root",
            "path": str(runtime_root),
            "preserve_dirs": [str(p) for p in preserve_dirs],
        }
    )

    report: dict[str, object] = {
        "mode": "apply" if args.apply else "dry-run",
        "brain_root": str(brain_root),
        "canonical_runtime_root": str(canonical_root),
        "runtime_root": str(runtime_root),
        "legacy_runtime_root": str(legacy_root),
        "using_legacy_override": using_legacy_override,
        "archive_root": str(archive_base),
        "archive_runtime_dir": str(archive_runtime_dir),
        "archive_legacy_dir": str(archive_legacy_dir),
        "runtime_exists": runtime_root.exists(),
        "entries_count": len(entries),
        "legacy_exists": legacy_root.exists(),
        "legacy_entries_count": len(legacy_entries),
        "preserve_dirs": [str(p) for p in preserve_dirs],
        "planned_actions": planned_actions,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    archived_runtime_path = ""
    if runtime_root.exists():
        if archive_runtime_dir.exists():
            raise SystemExit(f"archive_dir_already_exists: {archive_runtime_dir}")
        archive_runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(runtime_root), str(archive_runtime_dir))
        archived_runtime_path = str(archive_runtime_dir)

    runtime_root.mkdir(parents=True, exist_ok=True)
    for path in preserve_dirs:
        path.mkdir(parents=True, exist_ok=True)

    archived_legacy_path = ""
    if legacy_root.exists() and legacy_root != runtime_root:
        if archive_legacy_dir.exists():
            raise SystemExit(f"archive_dir_already_exists: {archive_legacy_dir}")
        archive_legacy_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_root), str(archive_legacy_dir))
        archived_legacy_path = str(archive_legacy_dir)
        legacy_root.mkdir(parents=True, exist_ok=True)

    report["archived_runtime_path"] = archived_runtime_path
    report["archived_legacy_path"] = archived_legacy_path
    report["recreated"] = [str(p) for p in preserve_dirs]
    report["legacy_root_recreated"] = str(legacy_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
