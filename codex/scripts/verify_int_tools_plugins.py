#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = ROOT / "codex" / "bin" / "mcp-intdata-cli.py"
MARKETPLACE_NAME = "intdata"
MARKETPLACE_DISPLAY_NAME = "intData"
PUBLIC_PLUGIN_NAMES = ("intbrain", "dba")
COMPATIBILITY_PROFILE_NAMES: tuple[str, ...] = ()
FORBIDDEN_PUBLIC_PLUGIN_NAMES = {"coordctl", "agent-plane"}
EXPECTED_COUNTS = {
    "intbrain": 31,
    "intdata-control": 12,
    "intdata-runtime": 9,
    "dba": 1,
}

PLUGIN_DIRS = {
    "intbrain": ROOT / "codex" / "plugins" / "intbrain",
    "dba": ROOT / "codex" / "plugins" / "dba",
}

TOOL_SKILLS = {
    "intbrain": {
        "intbrain_context_pack": "context-memory",
        "intbrain_memory_search": "context-memory",
        "intbrain_context_store": "context-memory",
        "intbrain_graph_link": "context-memory",
        "intbrain_sources_search": "context-memory",
        "intbrain_source_get": "context-memory",
        "intbrain_source_upsert": "context-memory",
        "intbrain_source_evaluate": "context-memory",
        "intbrain_people_resolve": "people-graph-policies",
        "intbrain_people_get": "people-graph-policies",
        "intbrain_graph_neighbors": "people-graph-policies",
        "intbrain_people_policy_tg_get": "people-graph-policies",
        "intbrain_group_policy_get": "people-graph-policies",
        "intbrain_group_policy_upsert": "people-graph-policies",
        "intbrain_policy_events_list": "people-graph-policies",
        "intbrain_jobs_list": "jobs-runtime",
        "intbrain_jobs_get": "jobs-runtime",
        "intbrain_jobs_sync_runtime": "jobs-runtime",
        "intbrain_job_policy_upsert": "jobs-runtime",
        "intbrain_pm_dashboard": "pm-dashboard-tasks",
        "intbrain_pm_tasks": "pm-dashboard-tasks",
        "intbrain_pm_para": "pm-dashboard-tasks",
        "intbrain_pm_health": "pm-dashboard-tasks",
        "intbrain_pm_constraints_validate": "pm-dashboard-tasks",
        "intbrain_pm_task_create": "pm-dashboard-tasks",
        "intbrain_pm_task_patch": "pm-dashboard-tasks",
        "intbrain_memory_recent_work": "session-memory",
        "intbrain_memory_session_brief": "session-memory",
        "intbrain_memory_sync_sessions": "session-memory",
        "intbrain_import_vault_pm": "external-imports",
        "intbrain_memory_import_mempalace": "external-imports",
    },
    "dba": {
        "intdata_cli": "doctor-status",
    },
}

REQUIRED_CARD_MARKERS = [
    "Когда:",
    "Required inputs:",
    "Optional/schema inputs:",
    "Режим:",
    "Approval / issue requirements:",
    "Не использовать когда:",
    "Пример вызова:",
    "Fallback/blocker:",
]

# Destructive maintenance that still requires owner approval. coordctl
# coordination writes (session_start/begin/intent_acquire/heartbeat/release) are
# intentionally NOT here: they are advisory provenance, not high-risk mutation.
GUARDED_TOOLS = {
    "openspec_archive", "openspec_change_mutate", "openspec_spec_mutate", "openspec_new", "openspec_exec_mutate",
    "host_bootstrap", "recovery_bundle", "browser_profile_launch", "ssh_execute",
    "intdata_vault_sanitize", "intdata_runtime_vault_gc",
    "intbrain_context_store", "intbrain_graph_link", "intbrain_group_policy_upsert", "intbrain_jobs_sync_runtime",
    "intbrain_job_policy_upsert", "intbrain_pm_task_create", "intbrain_pm_task_patch", "intbrain_import_vault_pm",
    "intbrain_memory_sync_sessions", "intbrain_memory_import_mempalace", "intbrain_source_upsert",
    "intbrain_source_evaluate", "intdata_cli",
}

ADVISORY_TOOLS: set[str] = set()

GUARD_WORDS = ["approval", "confirm_mutation", "issue_context", "owner approval"]
ADVISORY_MARKERS = ["Режим: advisory", "Режим: advisory write"]
READ_ONLY_MARKERS = ["Режим: read-only", "Режим: read-only by default"]
CABINET_RE = re.compile(r"cabinet|intbrain_cabinet", re.IGNORECASE)

REMOVED_INTDATA_CONTROL_TOOLS = {
    "multica_issue", "multica_project", "multica_agent", "multica_workspace", "multica_repo",
    "multica_skill", "multica_runtime", "multica_config", "multica_daemon", "multica_attachment",
    "multica_auth", "multica_exec", "multica_issue_read", "multica_issue_write",
    "multica_project_read", "multica_project_write", "multica_agent_read", "multica_agent_write",
    "multica_workspace_read", "multica_skill_read", "multica_skill_write", "multica_runtime_read",
    "multica_runtime_write", "multica_config_read", "multica_config_write", "multica_daemon_read",
    "multica_daemon_control", "multica_auth_read", "multica_auth_write", "multica_attachment_download",
    "multica_repo_checkout", "openspec_change", "openspec_spec", "openspec_exec",
    "sync_gate", "sync_gate_start", "sync_gate_finish", "int_git_sync_gate", "int_git_sync_gate.py",
    "mcp-lockctl.py", "mcp-lockctl.sh", "mcp-lockctl.cmd", "lockctl-mcp",
    "lockctl_acquire", "lockctl_renew", "lockctl_release_path", "lockctl_release_issue",
    "lockctl_status", "lockctl_gc",
    "multica_autopilot_report_sidecar.py", "AUTOPILOT_REPORT_TARGETS", "AUTOPILOT_REPORT_STATE_PATH",
    "publish_repo.py", "publish_data.py", "publish_assess.py", "publish_crm.py", "publish_id.py",
    "publish_nexus.py", "publish_bundle_dint.py", "publish_brain_dev.py",
    "publish_repo.ps1", "publish_data.ps1", "publish_assess.ps1", "publish_crm.ps1", "publish_id.ps1",
    "publish_nexus.ps1", "publish_bundle_dint.ps1", "publish_brain_dev.ps1",
}

ACTIVE_DOC_GUARD_PATHS = [
    ROOT / "AGENTS.md",
    ROOT / "openspec" / "changes" / "require-agent-plugin-tool-access" / "specs" / "process" / "spec.md",
    ROOT / "openspec" / "changes" / "remove-intdata-control-multica-surface" / "specs" / "process" / "spec.md",
    ROOT / "openspec" / "changes" / "remove-local-delivery-publish-surface" / "specs" / "process" / "spec.md",
    ROOT / "openspec" / "changes" / "remove-local-sync-gate-and-codex-home-mutation" / "specs" / "process" / "spec.md",
]

CODEX_HOME_FALLBACK_GUARD_PATHS = [
    ROOT / "codex" / "bin" / "mcp-intdata-cli.py",
    ROOT / "codex" / "bin" / "mcp-salebot.mjs",
    ROOT / "codex" / "bin" / "mcp-bitrix24.sh",
    ROOT / "codex" / "bin" / "twc-timeweb.sh",
    ROOT / "codex" / "bin" / "timeweb-app-diagnostics.sh",
    ROOT / "codex" / "lib" / "codex-env.sh",
]

REMOVED_CODEX_HOME_FALLBACK_REFS = {
    "LEGACY_CODEX_VAR_ROOT": re.compile(r"LEGACY_CODEX_VAR_ROOT"),
    "codex_legacy_env_hint": re.compile(r"codex_legacy_env_hint"),
    "codex_var_fallback": re.compile(r"\.codex[/\\]var|CODEX_HOME.*var"),
    "codex_memory_fallback": re.compile(r"\.codex[/\\]memories|CODEX_HOME.*memories"),
    "legacy_lockctl_memory_env": re.compile(r"LOCKCTL_LEGACY_WINDOWS_STATE_DIR"),
}

REMOVED_ACTIVE_DOC_REFS = {
    "mcp__openspec__": re.compile(r"mcp__openspec__"),
    **{
        name: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
        for name in REMOVED_INTDATA_CONTROL_TOOLS
    },
}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def frame(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload).encode("utf-8")
    return b"Content-Length: " + str(len(raw)).encode("ascii") + b"\r\n\r\n" + raw


def parse_frames(raw: bytes) -> list[dict[str, Any]]:
    messages = []
    rest = raw
    while rest:
        head, sep, body = rest.partition(b"\r\n\r\n")
        if not sep:
            break
        length = int(head.decode("ascii").split(":", 1)[1].strip())
        messages.append(json.loads(body[:length].decode("utf-8")))
        rest = body[length:]
    return messages


def mcp_exchange(profile: str, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = b"".join(frame(req) for req in requests)
    proc = subprocess.run(
        [sys.executable, str(MCP_SERVER), "--profile", profile],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"{profile} MCP exited {proc.returncode}: {proc.stderr.decode(errors='replace')}")
    return parse_frames(proc.stdout)


def tools_for(profile: str) -> list[dict[str, Any]]:
    responses = mcp_exchange(
        profile,
        [
            {"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"id": 2, "method": "ping", "params": {}},
            {"id": 3, "method": "tools/list", "params": {}},
        ],
    )
    by_id = {msg.get("id"): msg for msg in responses}
    if "error" in by_id[1]:
        raise AssertionError(f"{profile} initialize failed: {by_id[1]['error']}")
    if "error" in by_id[2]:
        raise AssertionError(f"{profile} ping failed: {by_id[2]['error']}")
    return by_id[3]["result"]["tools"]


def verify_manifests(report: dict[str, Any]) -> None:
    marketplace_path = ROOT / ".codex" / "plugins" / "marketplace.json"
    if not marketplace_path.exists():
        report["manifest_errors"].append(f"missing required marketplace catalog: {display_path(marketplace_path)}")
        entries = {}
    else:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        if marketplace.get("name") != MARKETPLACE_NAME:
            report["manifest_errors"].append(
                f"marketplace name must be {MARKETPLACE_NAME!r}, got {marketplace.get('name')!r}"
            )
        interface = marketplace.get("interface") or {}
        if interface.get("displayName") != MARKETPLACE_DISPLAY_NAME:
            report["manifest_errors"].append(
                f"marketplace displayName must be {MARKETPLACE_DISPLAY_NAME!r}, got {interface.get('displayName')!r}"
            )
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list):
            report["manifest_errors"].append("marketplace plugins must be a list")
            entries = {}
        else:
            entries = {entry["name"]: entry for entry in plugins if isinstance(entry, dict) and "name" in entry}
            public_names = set(entries)
            forbidden = sorted(public_names & FORBIDDEN_PUBLIC_PLUGIN_NAMES)
            if forbidden:
                report["manifest_errors"].append({"forbidden_public_plugins": forbidden})
            unexpected = sorted(public_names - set(PUBLIC_PLUGIN_NAMES) - FORBIDDEN_PUBLIC_PLUGIN_NAMES)
            if unexpected:
                report["manifest_errors"].append({"unexpected_public_plugins": unexpected})
    for name in PUBLIC_PLUGIN_NAMES:
        plugin_dir = PLUGIN_DIRS[name]
        if name not in entries:
            report["manifest_errors"].append(f"missing marketplace entry: {name}")
            continue
        manifest = json.loads((plugin_dir / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if manifest.get("name") != name:
            report["manifest_errors"].append(f"manifest name mismatch for {name}")
        required_keys = ("skills", "mcpServers", "interface") if name == "intbrain" else ("skills", "interface")
        for key in required_keys:
            if key not in manifest:
                report["manifest_errors"].append(f"{name} missing {key}")
        if name != "intbrain":
            if "mcpServers" in manifest:
                report["manifest_errors"].append(f"{name} must use host-native registration, not bundled mcpServers")
            if (plugin_dir / ".mcp.json").exists():
                report["manifest_errors"].append(f"{name} must not bundle .mcp.json")
        interface = manifest.get("interface", {})
        for key in ("displayName", "shortDescription", "longDescription", "defaultPrompt", "brandColor"):
            if key not in interface:
                report["manifest_errors"].append(f"{name} interface missing {key}")
        if name == "intbrain" and CABINET_RE.search(json.dumps(manifest, ensure_ascii=False)):
            report["manifest_errors"].append("intbrain manifest leaks Cabinet active surface")
        if name == "intbrain":
            mcp_config = json.loads((plugin_dir / ".mcp.json").read_text(encoding="utf-8"))
            args = (((mcp_config.get("mcpServers") or {}).get("intbrain") or {}).get("args") or [])
            if "D:\\int\\client\\mcp\\intbrain\\bin\\mcp-intbrain.py" not in args:
                report["manifest_errors"].append("intbrain .mcp.json must point to /int/client canonical entrypoint")


def extract_card(body: str, tool_name: str) -> str | None:
    marker = f"### {tool_name}"
    start = body.find(marker)
    if start < 0:
        return None
    next_start = body.find("\n### ", start + len(marker))
    return body[start:] if next_start < 0 else body[start:next_start]


def required_args(tool: dict[str, Any]) -> list[str]:
    return list(tool.get("inputSchema", {}).get("required", []) or [])


def verify_skill_card(profile: str, tool: dict[str, Any], report: dict[str, Any]) -> None:
    tool_name = tool["name"]
    skill = TOOL_SKILLS[profile].get(tool_name)
    row = {"profile": profile, "tool": tool_name, "skill": skill, "missing_guidance": []}
    report["matrix"].append(row)
    if not skill:
        row["missing_guidance"].append("no skill mapping")
        return
    path = PLUGIN_DIRS[profile] / "skills" / skill / "SKILL.md"
    if not path.exists():
        row["missing_guidance"].append(f"missing skill file: {path}")
        return
    body = path.read_text(encoding="utf-8")
    card = extract_card(body, tool_name)
    if not card:
        row["missing_guidance"].append("missing tool card heading")
        return
    for marker in REQUIRED_CARD_MARKERS:
        if marker not in card:
            row["missing_guidance"].append(f"missing marker {marker}")
    for arg in required_args(tool):
        if f"`{arg}`" not in card:
            row["missing_guidance"].append(f"required arg not documented: {arg}")
    if tool_name in GUARDED_TOOLS or {"confirm_mutation", "issue_context"} & set(required_args(tool)):
        missing = [word for word in GUARD_WORDS if word not in card]
        if missing:
            row["missing_guidance"].append(f"missing guard wording: {', '.join(missing)}")
    elif tool_name in ADVISORY_TOOLS:
        if not any(marker in card for marker in ADVISORY_MARKERS):
            row["missing_guidance"].append("missing advisory marker")
    else:
        if not any(marker in card for marker in READ_ONLY_MARKERS):
            row["missing_guidance"].append("missing read-only marker")
    if CABINET_RE.search(tool_name):
        row["missing_guidance"].append("Cabinet tool leaked into active surface")


def verify_skill_coverage(profile: str, tools: list[dict[str, Any]], report: dict[str, Any]) -> None:
    names = {tool["name"] for tool in tools}
    mapping = TOOL_SKILLS[profile]
    missing = sorted(names - set(mapping))
    extra = sorted(set(mapping) - names)
    if missing or extra:
        report["mapping_errors"].append({"profile": profile, "missing": missing, "extra": extra})
    for tool in tools:
        verify_skill_card(profile, tool, report)


def verify_cabinet_absent(report: dict[str, Any]) -> None:
    scan_roots = [
        ROOT / "codex" / "plugins" / "intbrain" / "skills",
        ROOT / "codex" / "plugins" / "intbrain" / ".codex-plugin" / "plugin.json",
    ]
    for root in scan_roots:
        paths = [root] if root.is_file() else list(root.rglob("*.md"))
        for path in paths:
            if CABINET_RE.search(path.read_text(encoding="utf-8")):
                report["cabinet_errors"].append(str(path.relative_to(ROOT)))


def verify_skill_frontmatter(report: dict[str, Any]) -> None:
    for plugin_dir in PLUGIN_DIRS.values():
        for path in sorted((plugin_dir / "skills").rglob("SKILL.md")):
            if not path.read_text(encoding="utf-8").startswith("---"):
                report["skill_frontmatter_errors"].append(display_path(path))


def active_doc_paths() -> list[Path]:
    paths = list(ACTIVE_DOC_GUARD_PATHS)
    for plugin_dir in PLUGIN_DIRS.values():
        paths.extend(sorted((plugin_dir / "skills").rglob("SKILL.md")))
    return paths


def verify_active_doc_references(report: dict[str, Any]) -> None:
    allowed_removed_context = (
        "removed",
        "forbidden",
        "must not expose",
        "no longer",
        "MUST NOT expose",
        "удалён",
        "удалены",
        "запрещён",
        "запрещены",
    )
    for path in active_doc_paths():
        if not path.exists():
            report["doc_guard_warnings"].append(f"missing active doc; skipped removed-reference scan: {display_path(path)}")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, pattern in REMOVED_ACTIVE_DOC_REFS.items():
                if pattern.search(line):
                    if any(marker in line for marker in allowed_removed_context):
                        continue
                    report["doc_guard_errors"].append({
                        "path": display_path(path),
                        "line": line_no,
                        "removed_ref": name,
                    })


def verify_no_codex_home_fallbacks(report: dict[str, Any]) -> None:
    for path in CODEX_HOME_FALLBACK_GUARD_PATHS:
        if not path.exists():
            report["doc_guard_errors"].append(f"missing fallback guard path: {display_path(path)}")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, pattern in REMOVED_CODEX_HOME_FALLBACK_REFS.items():
                if pattern.search(line):
                    report["doc_guard_errors"].append({
                        "path": display_path(path),
                        "line": line_no,
                        "removed_ref": name,
                    })


def verify_guard_cases(profile: str) -> None:
    guard_cases = {
        "intdata-control": [
            ("openspec_archive", {"change_name": "guard-negative"}),
            ("openspec_change_mutate", {"subcommand": "set", "args": ["guard-negative"]}),
        ],
        "intdata-runtime": [("host_bootstrap", {}), ("recovery_bundle", {}), ("ssh_execute", {"host": "dev-agents", "argv": ["true"], "execution_mode": "mutation"}), ("browser_profile_launch", {"profile": "firefox-default"}), ("intdata_vault_sanitize", {"dry_run": False})],
        "intbrain": [("intbrain_context_store", {"owner_id": 1, "kind": "note", "title": "guard", "text_content": "guard"}), ("intbrain_pm_task_create", {"owner_id": 1, "title": "guard"}), ("intbrain_jobs_sync_runtime", {"owner_id": 1})],
        "dba": [("intdata_cli", {"command": "dba", "args": ["migrate", "apply"]})],
    }
    requests = [{"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}]
    for idx, (tool, args) in enumerate(guard_cases.get(profile, []), start=2):
        requests.append({"id": idx, "method": "tools/call", "params": {"name": tool, "arguments": args}})
    responses = mcp_exchange(profile, requests)
    for msg in responses:
        if msg.get("id") == 1:
            continue
        text = json.dumps(msg, ensure_ascii=False)
        if "confirm_mutation" not in text and "issue_context" not in text:
            raise AssertionError(f"{profile} guard case did not reject mutation: {text}")


def build_report(skip_guards: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": True,
        "marketplace_name": MARKETPLACE_NAME,
        "public_plugins": list(PUBLIC_PLUGIN_NAMES),
        "compatibility_profiles": list(COMPATIBILITY_PROFILE_NAMES),
        "expected_counts": EXPECTED_COUNTS,
        "counts": {},
        "manifest_errors": [],
        "manifest_warnings": [],
        "mapping_errors": [],
        "cabinet_errors": [],
        "skill_frontmatter_errors": [],
        "doc_guard_errors": [],
        "doc_guard_warnings": [],
        "matrix": [],
    }
    verify_manifests(report)
    for profile, expected in EXPECTED_COUNTS.items():
        tools = tools_for(profile)
        names = {tool["name"] for tool in tools}
        report["counts"][profile] = len(tools)
        if len(tools) != expected:
            report["mapping_errors"].append({"profile": profile, "expected": expected, "actual": len(tools)})
        leaked = sorted(name for name in names if CABINET_RE.search(name))
        if leaked:
            report["cabinet_errors"].append({"profile": profile, "tools": leaked})
        if profile == "intdata-control":
            removed = sorted(name for name in names if name.startswith("multica_") or name in REMOVED_INTDATA_CONTROL_TOOLS)
            if removed:
                report["mapping_errors"].append({"profile": profile, "removed_tools_present": removed})
        if profile in TOOL_SKILLS:
            verify_skill_coverage(profile, tools, report)
        if not skip_guards:
            verify_guard_cases(profile)
    verify_cabinet_absent(report)
    verify_skill_frontmatter(report)
    verify_active_doc_references(report)
    verify_no_codex_home_fallbacks(report)
    missing_count = sum(len(row["missing_guidance"]) for row in report["matrix"])
    report["missing_guidance_count"] = missing_count
    report["ok"] = not (
        report["manifest_errors"]
        or report["mapping_errors"]
        or report["cabinet_errors"]
        or report["skill_frontmatter_errors"]
        or report["doc_guard_errors"]
        or missing_count
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-guards", action="store_true")
    parser.add_argument("--report-json", action="store_true")
    args = parser.parse_args()

    report = build_report(skip_guards=args.skip_guards)
    if args.report_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report["matrix"]:
            status = "ok" if not row["missing_guidance"] else "; ".join(row["missing_guidance"])
            print(f"{row['profile']}/{row['tool']} -> {row['skill']} -> {status}")
        if report["ok"]:
            print("ok: intData plugin manifests, MCP smoke, skill cards, Cabinet exclusion, doc guard, and guard checks passed")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
