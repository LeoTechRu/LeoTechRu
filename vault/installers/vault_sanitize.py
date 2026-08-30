#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
import sys


UTC = timezone.utc


STRICT_ALLOWED_EXTENSIONS = {
    "",
    ".md",
    ".canvas",
    ".excalidraw",
    ".drawio",
    ".txt",
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".rtf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".mp4",
    ".mov",
    ".webm",
    ".zip",
    ".7z",
    ".rar",
}

BALANCED_ALLOWED_EXTENSIONS = STRICT_ALLOWED_EXTENSIONS | {
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".toml",
}

PERMISSIVE_ALLOWED_EXTENSIONS = BALANCED_ALLOWED_EXTENSIONS | {
    ".js",
    ".css",
    ".html",
    ".sql",
    ".php",
    ".py",
    ".puml",
    ".ts",
    ".tsx",
    ".mhtml",
    ".sig",
    ".dip",
    ".tmp",
    ".rels",
}

ALLOWED_EXTENSIONS_BY_PROFILE = {
    "strict": STRICT_ALLOWED_EXTENSIONS,
    "balanced": BALANCED_ALLOWED_EXTENSIONS,
    "permissive": PERMISSIVE_ALLOWED_EXTENSIONS,
}

ROOT_ALLOWED_NAMES = {
    ".gitignore",
    "README.md",
    "AGENTS.md",
    "MEMORY.md",
    "Dashboard.md",
}

ROOT_ALLOWED_DIRS = {
    ".obsidian",
    ".git",
    ".trash",
    ".stfolder",
    "Archive",
    "Areas",
    "Diaries",
    "Inbox",
    "Projects",
    "Resources",
    "templates",
}


@dataclass(slots=True)
class Action:
    kind: str
    source: Path
    destination: Path | None
    note: str = ""


def now_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def canonical_runtime_root(brain_root: Path) -> Path:
    return (brain_root.parent / ".tmp" / "brain-runtime-vault").resolve()


def legacy_runtime_root(brain_root: Path) -> Path:
    return (brain_root / "runtime" / "vault").resolve()


def relpath(base: Path, value: Path) -> str:
    try:
        return str(value.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def merge_move_dir(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            merge_move_dir(child, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            shutil.move(str(child), str(target))
    source.rmdir()


def apply_action(action: Action) -> None:
    if action.kind == "move":
        assert action.destination is not None
        source = action.source
        destination = action.destination
        if not source.exists():
            return
        if source.is_dir():
            if destination.exists() and destination.is_dir():
                merge_move_dir(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                destination.unlink()
            shutil.move(str(source), str(destination))
        return

    if action.kind == "delete":
        source = action.source
        if not source.exists():
            return
        if source.is_dir():
            shutil.rmtree(source)
        else:
            source.unlink()
        return

    raise ValueError(f"unsupported_action_kind: {action.kind}")


def allowed_extensions(profile: str) -> set[str]:
    if profile not in ALLOWED_EXTENSIONS_BY_PROFILE:
        raise ValueError(f"unsupported_profile: {profile}")
    return ALLOWED_EXTENSIONS_BY_PROFILE[profile]


def is_whitelisted(vault_root: Path, path: Path, profile: str) -> bool:
    rel = path.relative_to(vault_root)
    rel_parts = rel.parts
    if not rel_parts:
        return True

    first = rel_parts[0]
    if first in ROOT_ALLOWED_DIRS:
        if first in {".obsidian", ".git", ".trash", ".stfolder"}:
            return True
    elif len(rel_parts) == 1 and first in ROOT_ALLOWED_NAMES:
        return True

    suffix = path.suffix.lower()
    return suffix in allowed_extensions(profile)


def scan_non_whitelist(vault_root: Path, profile: str) -> list[str]:
    issues: list[str] = []
    for file_path in sorted(vault_root.rglob("*")):
        if not file_path.is_file():
            continue
        if not is_whitelisted(vault_root, file_path, profile):
            issues.append(relpath(vault_root, file_path))
    return issues


def build_default_actions(vault_root: Path, runtime_root: Path, tools_root: Path) -> list[Action]:
    installers_root = tools_root / "vault" / "installers"
    runtime_artifacts_root = runtime_root / "artifacts"
    actions = [
        Action(
            kind="move",
            source=vault_root / "run-obsidian.sh",
            destination=installers_root / "run-obsidian.sh",
            note="move_vault_launcher_to_installers",
        ),
        Action(
            kind="move",
            source=vault_root / ".tmp" / "git-history-inspect",
            destination=installers_root / "git-history-inspect",
            note="extract_useful_git_history_tools",
        ),
        Action(
            kind="move",
            source=vault_root / "Resources" / "OpenClaw",
            destination=vault_root / "Resources" / "Agents" / "OpenClaw",
            note="move_agent_notes_to_generic_folder",
        ),
        Action(
            kind="move",
            source=vault_root / ".tmp",
            destination=runtime_artifacts_root / ".tmp",
            note="remove_runtime_tmp_from_vault",
        ),
        Action(
            kind="move",
            source=vault_root / "_.tmp",
            destination=runtime_artifacts_root / "_.tmp",
            note="remove_runtime_tmp_from_vault",
        ),
        Action(
            kind="move",
            source=vault_root / ".smart-env",
            destination=runtime_artifacts_root / ".smart-env",
            note="remove_runtime_index_from_vault",
        ),
        Action(
            kind="move",
            source=vault_root / ".smtcmp_json_db",
            destination=runtime_artifacts_root / ".smtcmp_json_db",
            note="remove_runtime_index_from_vault",
        ),
        Action(
            kind="move",
            source=vault_root / ".smtcmp_vector_db.tar.gz",
            destination=runtime_artifacts_root / ".smtcmp_vector_db.tar.gz",
            note="remove_runtime_index_from_vault",
        ),
    ]
    return actions


def build_whitelist_enforcement_actions(vault_root: Path, runtime_root: Path, profile: str) -> list[Action]:
    target_root = runtime_root / "non_whitelist"
    actions: list[Action] = []
    for rel in scan_non_whitelist(vault_root, profile):
        source = vault_root / rel
        destination = target_root / rel
        actions.append(Action(kind="move", source=source, destination=destination, note=f"enforce_{profile}"))
    return actions


def action_to_dict(vault_root: Path, brain_root: Path, action: Action, exists: bool) -> dict[str, str | bool]:
    return {
        "kind": action.kind,
        "source": relpath(vault_root, action.source),
        "source_abs": str(action.source),
        "destination": relpath(brain_root, action.destination) if action.destination else "",
        "destination_abs": str(action.destination) if action.destination else "",
        "exists": exists,
        "note": action.note,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vault sanitization: move operational artifacts out of Obsidian vault.")
    parser.add_argument("--vault-root", default=r"D:\Yandex.Disk\2brain", help="Vault path (local or /2brain on VDS).")
    parser.add_argument("--brain-root", default="dev@intdata.pro:/int/brain", help="int/brain repo root on dev@intdata.pro.")
    parser.add_argument("--tools-root", default=r"D:\int\tools", help="int/tools root path (local or /int/tools on VDS).")
    parser.add_argument(
        "--runtime-root",
        default="",
        help="Runtime root override. Default: <brain-root parent>/.tmp/brain-runtime-vault",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions only.")
    parser.add_argument("--apply", action="store_true", help="Execute planned actions.")
    parser.add_argument(
        "--profile",
        choices=("strict", "balanced", "permissive"),
        default="strict",
        help="Vault whitelist profile. strict is the default.",
    )
    parser.add_argument(
        "--enforce-whitelist",
        action="store_true",
        help="Deprecated alias for --profile strict (kept for backward compatibility).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and args.dry_run:
        raise SystemExit("Use either --dry-run or --apply, not both.")
    if not args.apply and not args.dry_run:
        args.dry_run = True

    vault_root = Path(args.vault_root).expanduser().resolve()
    brain_root = Path(args.brain_root).expanduser().resolve()
    tools_root = Path(args.tools_root).expanduser().resolve()
    if not vault_root.exists():
        raise SystemExit(f"vault_root_not_found: {vault_root}")
    if not brain_root.exists():
        raise SystemExit(f"brain_root_not_found: {brain_root}")
    if not tools_root.exists():
        raise SystemExit(f"tools_root_not_found: {tools_root}")

    runtime_root = (
        Path(args.runtime_root).expanduser().resolve()
        if args.runtime_root
        else canonical_runtime_root(brain_root)
    )
    legacy_root = legacy_runtime_root(brain_root)
    if runtime_root == legacy_root:
        print(
            "warning: --runtime-root points to legacy path; prefer canonical <brain-root parent>/.tmp/brain-runtime-vault",
            file=sys.stderr,
        )

    effective_profile = args.profile
    if args.enforce_whitelist:
        if args.profile != "strict":
            print("warning: --enforce-whitelist overrides --profile and sets strict", file=sys.stderr)
        else:
            print("warning: --enforce-whitelist is deprecated, use --profile strict", file=sys.stderr)
        effective_profile = "strict"

    stamp = now_stamp()
    actions = build_default_actions(vault_root, runtime_root, tools_root)
    actions.extend(build_whitelist_enforcement_actions(vault_root, runtime_root, effective_profile))

    pre_violations = scan_non_whitelist(vault_root, effective_profile)
    plan = []
    for action in actions:
        exists = action.source.exists()
        plan.append(action_to_dict(vault_root, brain_root, action, exists))

    if args.dry_run:
        report = {
            "mode": "dry-run",
            "profile": effective_profile,
            "vault_root": str(vault_root),
            "brain_root": str(brain_root),
            "tools_root": str(tools_root),
            "canonical_runtime_root": str(canonical_runtime_root(brain_root)),
            "runtime_root": str(runtime_root),
            "legacy_runtime_root": str(legacy_root),
            "action_count": len(plan),
            "existing_action_count": sum(1 for item in plan if item["exists"]),
            "pre_whitelist_violations": pre_violations,
            "actions": plan,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    manifest_root = runtime_root / "manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / f"vault-sanitize-{stamp}.json"

    applied: list[dict[str, str | bool]] = []
    skipped: list[dict[str, str | bool]] = []
    for action in actions:
        exists = action.source.exists()
        item = action_to_dict(vault_root, brain_root, action, exists)
        if not exists:
            skipped.append(item)
            continue
        apply_action(action)
        applied.append(item)

    post_violations = scan_non_whitelist(vault_root, effective_profile)
    report = {
        "mode": "apply",
        "profile": effective_profile,
        "vault_root": str(vault_root),
        "brain_root": str(brain_root),
        "tools_root": str(tools_root),
        "canonical_runtime_root": str(canonical_runtime_root(brain_root)),
        "runtime_root": str(runtime_root),
        "legacy_runtime_root": str(legacy_root),
        "manifest_path": str(manifest_path),
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "pre_whitelist_violations_count": len(pre_violations),
        "post_whitelist_violations_count": len(post_violations),
        "pre_whitelist_violations": pre_violations,
        "post_whitelist_violations": post_violations,
        "applied": applied,
        "skipped": skipped,
    }
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
