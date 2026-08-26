from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ALLOWED_STATUSES = {
    "public-tool",
    "public-adapter",
    "catalog-link",
    "master-private",
    "runtime-state",
    "legacy-remove",
}

REQUIRED_FIELDS = {
    "id",
    "root",
    "status",
    "owner",
    "public_surface",
    "runtime_state",
    "target_home",
    "migration_action",
}


def _tracked_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _load_manifest(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("tools")
    if not isinstance(items, list):
        raise ValueError("manifest must contain a tools array")
    return items


def _top_level_dirs(tracked: list[str]) -> set[str]:
    dirs: set[str] = set()
    for item in tracked:
        top = item.split("/", 1)[0]
        if "/" in item and top and not top.startswith("."):
            dirs.add(top)
    return dirs


def _forbidden_artifacts(tracked: list[str]) -> list[str]:
    forbidden: list[str] = []
    for item in tracked:
        name = item.split("/")[-1]
        # Public repo instructions and product-local OpenSpec are allowed;
        # private/shared governance remains owned by the /int root repository.
        if item.startswith(".codex/"):
            forbidden.append(item)
        elif "/node_modules/" in f"/{item}/":
            forbidden.append(item)
        elif name == ".env" or name.endswith(".log") or name.endswith((".sqlite", ".sqlite3", ".db")):
            forbidden.append(item)
        elif item.startswith(".runtime/") or "/.runtime/" in f"/{item}/":
            forbidden.append(item)
    return forbidden


def validate(root: Path, *, skip_forbidden: bool = False) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "tools.catalog.v1.json"
    if not manifest_path.exists():
        return [f"missing manifest: {manifest_path}"]

    tracked = _tracked_files(root)
    top_dirs = _top_level_dirs(tracked)
    manifest = _load_manifest(manifest_path)
    by_root: dict[str, dict[str, object]] = {}
    ids: set[str] = set()

    for index, item in enumerate(manifest):
        missing = sorted(REQUIRED_FIELDS - set(item))
        if missing:
            errors.append(f"manifest entry {index} missing fields: {', '.join(missing)}")
            continue
        root_name = str(item["root"]).strip()
        item_id = str(item["id"]).strip()
        status = str(item["status"]).strip()
        if not root_name:
            errors.append(f"manifest entry {item_id or index} has empty root")
        if item_id in ids:
            errors.append(f"duplicate manifest id: {item_id}")
        ids.add(item_id)
        if root_name in by_root:
            errors.append(f"duplicate manifest root: {root_name}")
        by_root[root_name] = item
        if status not in ALLOWED_STATUSES:
            errors.append(f"{root_name}: invalid status {status}")
        if root_name and not (root / root_name).exists() and status != "catalog-link":
            errors.append(f"{root_name}: root is missing but status is {status}, not catalog-link")

    missing_dirs = sorted(top_dirs - set(by_root))
    extra_roots = sorted(
        root_name
        for root_name in by_root
        if root_name not in top_dirs and str(by_root[root_name]["status"]) != "catalog-link"
    )
    forbidden = [] if skip_forbidden else _forbidden_artifacts(tracked)

    if missing_dirs:
        errors.append(f"tracked top-level dirs missing from manifest: {', '.join(missing_dirs)}")
    if extra_roots:
        errors.append(f"manifest roots missing from tracked top-level dirs: {', '.join(extra_roots)}")
    if forbidden:
        preview = forbidden[:25]
        suffix = "" if len(forbidden) <= len(preview) else f"\n  ... {len(forbidden) - len(preview)} more"
        errors.append(
            f"forbidden tracked artifacts ({len(forbidden)} total):\n"
            + "\n".join(f"  - {item}" for item in preview)
            + suffix
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate intData-tools public catalog manifest.")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[2], type=Path)
    parser.add_argument("--skip-forbidden", action="store_true", help="Check manifest coverage only.")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root, skip_forbidden=args.skip_forbidden)
    if errors:
        print("[validate_tools_catalog] FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("[validate_tools_catalog] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
