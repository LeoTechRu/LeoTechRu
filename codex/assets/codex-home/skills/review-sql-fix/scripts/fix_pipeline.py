#!/usr/bin/env python3
"""Deterministic SQL remediation pipeline for review-sql-fix."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from backup_snapshot import BackupResult, create_snapshot  # noqa: E402
from safety_guard import PolicyDecision, SafetyGuardError, assert_runtime_sql_safe, enforce  # noqa: E402

ALLOWED_REVIEW_STATUSES = {
    "confirmed",
    "partially confirmed",
    "not confirmed",
    "outdated",
    "architecture opinion",
}

TRUNCATION_MARKERS = ("<Truncated in logs>", "Synthesis failed")

SECTION_TITLE_MAP = {
    "access control & roles": "access_control_roles",
    "network security": "network_security",
    "authentication & ssl": "auth_ssl",
    "audit & logging": "audit_logging",
    "connection management": "connection_management",
    "query performance": "query_performance",
    "wal & checkpoint": "wal_checkpoint",
    "autovacuum": "autovacuum",
    "query planner settings": "planner_settings",
    "parallelism & workers": "parallelism_workers",
    "extensions": "extensions",
    "cache efficiency": "cache_efficiency",
    "replication status": "replication_status",
}

INTNODE_CANDIDATES = [
    os.environ.get("INTNODE_BIN", "").strip() or None,
    "intnode",
]
COORD_OWNER = "codex:review-sql-fix"


class PipelineError(Exception):
    """Raised when an execution phase cannot continue."""


@dataclass
class FindingVerdict:
    finding_id: str
    section_id: str
    section_title: str
    severity: str
    finding_text: str
    review_status: str
    evidence: str
    decision: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run review-sql-fix remediation pipeline")
    parser.add_argument("--input", required=True, help="Path to remediation JSON input")
    parser.add_argument("--output-dir", required=True, help="Directory for remediation artifacts")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PipelineError(f"input file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError(f"invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise PipelineError("input must be a JSON object")
    return payload


def norm_status(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if text == "":
        return "INCOMPLETE"
    if text in ("critical", "warning", "advisory", "good"):
        return text.title()
    if text == "incomplete":
        return "INCOMPLETE"
    return str(raw).strip() or "INCOMPLETE"


def map_section_id(title: str, fallback: str) -> str:
    key = title.strip().lower()
    if key in SECTION_TITLE_MAP:
        return SECTION_TITLE_MAP[key]
    return fallback


def normalize_sections_from_object(raw_sections: Any) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    if isinstance(raw_sections, list):
        entries = raw_sections
    elif isinstance(raw_sections, dict):
        entries = []
        for sid, value in raw_sections.items():
            if isinstance(value, dict):
                merged = dict(value)
                merged.setdefault("id", sid)
                entries.append(merged)
    else:
        raise PipelineError("findings_bundle sections must be list or object map")

    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        section_id = str(entry.get("id") or f"section_{idx}").strip()
        title = str(entry.get("title") or section_id).strip()
        section_id = map_section_id(title, section_id)
        status = norm_status(entry.get("status"))
        findings = entry.get("findings") or []
        recs = entry.get("recommendations") or []
        if isinstance(findings, str):
            findings = [findings]
        if isinstance(recs, str):
            recs = [recs]
        sections.append(
            {
                "id": section_id,
                "title": title,
                "status": status,
                "findings": [str(x).strip() for x in findings if str(x).strip()],
                "recommendations": [str(x).strip() for x in recs if str(x).strip()],
            }
        )

    return sections


def extract_reports_from_bundle(bundle: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    outputs = bundle.get("outputs")
    if isinstance(outputs, dict):
        for key in ("security_report", "performance_report", "executive_summary"):
            if key in outputs:
                paths[key] = Path(str(outputs[key]))

    for key in ("security_report", "performance_report", "executive_summary"):
        if key in bundle and key not in paths:
            paths[key] = Path(str(bundle[key]))

    return paths


def parse_sections_from_report(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise PipelineError(f"report path does not exist: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    mode: str | None = None

    for line in lines:
        if line.startswith("### "):
            if current:
                sections.append(current)
            title = line[4:].strip()
            section_id = map_section_id(title, re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_"))
            current = {
                "id": section_id,
                "title": title,
                "status": "INCOMPLETE",
                "findings": [],
                "recommendations": [],
            }
            mode = None
            continue

        if not current:
            continue

        if line.startswith("**Status**:"):
            current["status"] = norm_status(line.split(":", 1)[1].strip())
            continue

        if line.startswith("**Findings**"):
            mode = "findings"
            continue

        if line.startswith("**Recommendations**"):
            mode = "recommendations"
            continue

        if line.startswith("- "):
            if mode == "findings":
                current["findings"].append(line[2:].strip())
            elif mode == "recommendations":
                current["recommendations"].append(line[2:].strip())

    if current:
        sections.append(current)
    return sections


def extract_sections(findings_bundle: Any) -> list[dict[str, Any]]:
    if not isinstance(findings_bundle, dict):
        raise PipelineError("findings_bundle must be an object")

    if "sections" in findings_bundle:
        return normalize_sections_from_object(findings_bundle["sections"])
    if "input_sections" in findings_bundle:
        return normalize_sections_from_object(findings_bundle["input_sections"])

    report_paths = extract_reports_from_bundle(findings_bundle)
    sections: list[dict[str, Any]] = []
    for key in ("security_report", "performance_report"):
        if key in report_paths:
            sections.extend(parse_sections_from_report(report_paths[key]))

    if not sections:
        raise PipelineError("findings_bundle must include sections or review-sql-find report paths")
    return sections


def contains_truncation(section: dict[str, Any]) -> bool:
    blob = "\n".join(
        [section.get("title", ""), section.get("status", "")]
        + list(section.get("findings", []))
        + list(section.get("recommendations", []))
    )
    for marker in TRUNCATION_MARKERS:
        if marker in blob:
            return True
    if re.search(r"(?mi)^\s*[-*]\s*(?:[\W_]*?)real\s*$", blob):
        return True
    if re.search(r"(?mi)^\s*[-*].*\bfor\s*$", blob):
        return True
    return False


def default_review_status(section_status: str) -> str:
    normalized = section_status.strip().lower()
    if normalized in ("critical", "warning"):
        return "confirmed"
    if normalized == "advisory":
        return "partially confirmed"
    if normalized == "good":
        return "not confirmed"
    return "not confirmed"


def normalize_review_status(raw: Any, default: str) -> str:
    status = str(raw or "").strip().lower()
    if status in ALLOWED_REVIEW_STATUSES:
        return status
    return default


def build_verdicts(
    sections: list[dict[str, Any]], payload: dict[str, Any]
) -> tuple[list[FindingVerdict], dict[str, str]]:
    explicit = payload.get("finding_reviews") or {}
    explicit_map: dict[str, str] = {}
    if isinstance(explicit, dict):
        for key, value in explicit.items():
            explicit_map[str(key)] = str(value)

    verdicts: list[FindingVerdict] = []
    finding_status_map: dict[str, str] = {}

    for section in sections:
        section_id = section["id"]
        title = section["title"]
        status = section["status"]
        default = default_review_status(status)
        findings = section.get("findings") or []

        if not findings:
            finding_id = f"{section_id}:0"
            review_status = normalize_review_status(explicit_map.get(finding_id), "not confirmed")
            verdict = FindingVerdict(
                finding_id=finding_id,
                section_id=section_id,
                section_title=title,
                severity=status,
                finding_text="No finding text provided",
                review_status=review_status,
                evidence="section has no explicit findings",
                decision="skip",
            )
            verdicts.append(verdict)
            finding_status_map[finding_id] = review_status
            continue

        for idx, finding_text in enumerate(findings, start=1):
            finding_id = f"{section_id}:{idx}"
            review_status = normalize_review_status(
                explicit_map.get(finding_id) or explicit_map.get(finding_text),
                default,
            )
            decision = "apply" if review_status in {"confirmed", "partially confirmed"} else "skip"
            verdicts.append(
                FindingVerdict(
                    finding_id=finding_id,
                    section_id=section_id,
                    section_title=title,
                    severity=status,
                    finding_text=finding_text,
                    review_status=review_status,
                    evidence=f"default by section severity={status}",
                    decision=decision,
                )
            )
            finding_status_map[finding_id] = review_status

    return verdicts, finding_status_map


def extract_sql_blocks(text: str) -> list[str]:
    blocks = re.findall(r"```sql\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return [block.strip() for block in blocks if block.strip()]


def build_runtime_actions(payload: dict[str, Any], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = payload.get("runtime_actions")
    if isinstance(actions, list):
        normalized: list[dict[str, Any]] = []
        for idx, action in enumerate(actions, start=1):
            if not isinstance(action, dict):
                continue
            sql = str(action.get("sql", "")).strip()
            if not sql:
                continue
            normalized.append(
                {
                    "id": str(action.get("id") or f"runtime_action_{idx}"),
                    "finding_id": str(action.get("finding_id") or ""),
                    "sql": sql,
                    "group": str(action.get("group") or "default"),
                }
            )
        return normalized

    generated: list[dict[str, Any]] = []
    for section in sections:
        section_id = section["id"]
        findings = section.get("findings") or []
        if len(findings) > 1:
            raise PipelineError(
                "cannot auto-map SQL recommendations for section "
                f"{section_id} with multiple findings; provide runtime_actions with explicit finding_id"
            )
        if not findings:
            continue
        for idx, recommendation in enumerate(section.get("recommendations") or [], start=1):
            for sql_block in extract_sql_blocks(recommendation):
                generated.append(
                    {
                        "id": f"{section_id}_sql_{idx}",
                        "finding_id": f"{section_id}:1",
                        "sql": sql_block,
                        "group": section_id,
                    }
                )
    return generated


def _trim_text(value: str, *, max_chars: int = 1200) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _runtime_executor(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get("runtime_executor")
    if isinstance(raw, dict):
        return raw
    return None


def _execute_runtime_sql(sql: str, payload: dict[str, Any]) -> dict[str, str]:
    executor = _runtime_executor(payload)
    if not executor:
        return {
            "status": "applied_simulated",
            "reason": "runtime apply simulated (runtime_executor is not configured)",
            "stdout": "",
            "stderr": "",
        }

    executor_type = str(executor.get("type", "psql")).strip().lower() or "psql"
    if executor_type != "psql":
        raise PipelineError(f"unsupported runtime executor type: {executor_type}")

    psql_bin = str(executor.get("psql_bin") or "psql").strip()
    dsn = str(executor.get("dsn") or "").strip()
    database = str(executor.get("database") or "").strip()
    extra_args_raw = executor.get("extra_args") or []
    extra_args = [str(x) for x in extra_args_raw] if isinstance(extra_args_raw, list) else []

    cmd: list[str] = [psql_bin]
    if dsn:
        cmd.extend(["--dbname", dsn])
    elif database:
        cmd.extend(["--dbname", database])
    cmd.extend(extra_args)
    cmd.extend(["-v", "ON_ERROR_STOP=1", "-c", sql])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = _trim_text(proc.stderr or proc.stdout or "")
        raise PipelineError(f"runtime SQL apply failed: {stderr}")

    return {
        "status": "applied",
        "reason": "runtime SQL executed via psql",
        "stdout": _trim_text(proc.stdout),
        "stderr": _trim_text(proc.stderr),
    }


def apply_runtime_lane(
    actions: list[dict[str, Any]],
    finding_status_map: dict[str, str],
    policy: PolicyDecision,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for action in actions:
        fid = action.get("finding_id", "")
        status = finding_status_map.get(fid, "not confirmed")
        eligible = status in {"confirmed", "partially confirmed"}
        sql = action["sql"]
        note = ""

        if not eligible:
            results.append(
                {
                    "id": action["id"],
                    "finding_id": fid,
                    "status": "skipped",
                    "reason": f"finding status={status}",
                    "sql": sql,
                    "stdout": "",
                    "stderr": "",
                }
            )
            continue

        assert_runtime_sql_safe([sql], policy.allow_dangerous)

        if not policy.allow_apply:
            note = "effective mode is plan_only"
            lane_status = "planned"
            stdout = ""
            stderr = ""
        else:
            runtime_result = _execute_runtime_sql(sql, payload)
            lane_status = runtime_result["status"]
            note = runtime_result["reason"]
            stdout = runtime_result["stdout"]
            stderr = runtime_result["stderr"]

        results.append(
            {
                "id": action["id"],
                "finding_id": fid,
                "status": lane_status,
                "reason": note,
                "sql": sql,
                "stdout": stdout,
                "stderr": stderr,
            }
        )

    return results


def _allowed_roots() -> list[Path]:
    roots: list[Path] = []
    for raw in ("/int", "/home/leon", "D:/int", "D:/home/leon", "C:/int", "C:/home/leon"):
        root = Path(raw).resolve()
        if root not in roots:
            roots.append(root)
    return roots


def _safe_resolve(path: Path) -> Path:
    resolved = path.resolve()
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise PipelineError(f"path outside allowed roots: {resolved}")


def _inside_any_root(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def resolve_repo_fix_path(fix_path: str, repo_targets: list[Path]) -> Path:
    candidate = Path(fix_path)
    if candidate.is_absolute():
        resolved = _safe_resolve(candidate)
        if not _inside_any_root(resolved, repo_targets):
            raise PipelineError(f"repo fix path not inside repo_targets: {resolved}")
        return resolved

    for root in repo_targets:
        resolved = _safe_resolve(root / candidate)
        if resolved.exists():
            return resolved

    raise PipelineError(f"unable to resolve repo fix path '{fix_path}' inside repo_targets")


def resolve_intnode() -> list[str]:
    for candidate in INTNODE_CANDIDATES:
        if not candidate:
            continue
        if "/" in candidate or "\\" in candidate:
            path = Path(candidate).expanduser()
            if path.exists():
                return [sys.executable, str(path)] if path.suffix.lower() == ".py" else [str(path)]
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    raise PipelineError("intnode not found in PATH; set INTNODE_BIN")


def run_intnode_coord(args: list[str]) -> dict[str, Any]:
    cmd = [*resolve_intnode(), "coord", *args, "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise PipelineError(f"intnode coord {' '.join(args[:1])} failed: {stderr}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise PipelineError(f"intnode coord returned invalid JSON: {proc.stdout}") from exc


def current_git_ref(repo_root: Path) -> tuple[str, str]:
    def git_value(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or proc.stdout.strip()
            raise PipelineError(f"git {' '.join(args)} failed for {repo_root}: {stderr}")
        return proc.stdout.strip()

    branch = git_value("rev-parse", "--abbrev-ref", "HEAD")
    commit = git_value("rev-parse", "HEAD")
    return branch, commit


def acquire_coord_intent(repo_root: Path, rel_path: str) -> str:
    _branch, base = current_git_ref(repo_root)
    session_payload = run_intnode_coord([
        "begin",
        "--repo-root",
        str(repo_root),
        "--owner",
        COORD_OWNER,
        "--base",
        base,
        "--path",
        rel_path,
    ])
    session = session_payload.get("session") or {}
    session_id = str(session.get("session_id") or "")
    if not session_id:
        raise PipelineError(f"intnode coord begin did not return session_id: {session_payload}")
    return session_id


def release_coord_session(session_id: str) -> None:
    run_intnode_coord(["release", "--session-id", session_id])


def apply_repo_lane(
    payload: dict[str, Any],
    finding_status_map: dict[str, str],
    policy: PolicyDecision,
) -> list[dict[str, Any]]:
    repo_fixes = payload.get("repo_fixes") or []
    repo_targets_raw = payload.get("repo_targets") or []
    repo_targets = [_safe_resolve(Path(str(p))) for p in repo_targets_raw]
    results: list[dict[str, Any]] = []

    if not repo_fixes:
        return results

    for item in repo_fixes:
        if not isinstance(item, dict):
            continue
        finding_id = str(item.get("finding_id", ""))
        status = finding_status_map.get(finding_id, "not confirmed")
        if status not in {"confirmed", "partially confirmed"}:
            results.append(
                {
                    "path": str(item.get("path", "")),
                    "finding_id": finding_id,
                    "status": "skipped",
                    "reason": f"finding status={status}",
                }
            )
            continue

        target = resolve_repo_fix_path(str(item.get("path", "")), repo_targets)
        search = str(item.get("search", ""))
        replace = str(item.get("replace", ""))

        if not search:
            results.append(
                {
                    "path": str(target),
                    "finding_id": finding_id,
                    "status": "skipped",
                    "reason": "empty search pattern",
                }
            )
            continue

        if not policy.allow_apply:
            results.append(
                {
                    "path": str(target),
                    "finding_id": finding_id,
                    "status": "planned",
                    "reason": "effective mode is plan_only",
                }
            )
            continue

        repo_root = None
        for root in repo_targets:
            if _inside_any_root(target, [root]):
                repo_root = root
                break
        if repo_root is None:
            raise PipelineError(f"cannot resolve repo root for target: {target}")

        rel_path = str(target.resolve().relative_to(repo_root.resolve()))
        coord_session_id = ""
        try:
            coord_session_id = acquire_coord_intent(repo_root, rel_path)

            original = target.read_text(encoding="utf-8")
            if search not in original:
                results.append(
                    {
                        "path": str(target),
                        "finding_id": finding_id,
                        "status": "skipped",
                        "reason": "search pattern not found",
                    }
                )
                continue

            updated = original.replace(search, replace, 1)
            target.write_text(updated, encoding="utf-8")
            results.append(
                {
                    "path": str(target),
                    "finding_id": finding_id,
                    "status": "applied",
                    "reason": "single replacement written",
                }
            )
        finally:
            if coord_session_id:
                release_coord_session(coord_session_id)

    return results


def run_postchecks(payload: dict[str, Any], repo_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    commands = payload.get("postcheck_commands") or []
    environment = str(payload.get("environment", "")).strip().lower()
    effective_mode = str(payload.get("_effective_mode", "")).strip().lower()

    shell_commands_allowed = environment != "prod" and effective_mode != "plan_only"

    for command in commands:
        if not isinstance(command, str) or not command.strip():
            continue
        if not shell_commands_allowed:
            checks.append(
                {
                    "type": "command",
                    "command": command,
                    "status": "skipped_by_policy",
                    "reason": "postcheck shell commands are disabled in prod/plan_only mode",
                }
            )
            continue

        proc = subprocess.run(command, shell=True, capture_output=True, text=True)
        checks.append(
            {
                "type": "command",
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        )

    applied_files = [r["path"] for r in repo_results if r.get("status") == "applied"]
    for path in applied_files:
        p = Path(path)
        checks.append(
            {
                "type": "repo_file_exists",
                "path": path,
                "ok": p.exists(),
            }
        )

    return checks


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def render_verdict_md(verdicts: list[FindingVerdict], policy: PolicyDecision) -> str:
    lines = [
        "# Fix Verdict",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- environment: `{policy.environment}`",
        f"- scope: `{policy.scope}`",
        f"- source: `{policy.source}`",
        f"- requested_fix_mode: `{policy.requested_fix_mode}`",
        f"- effective_mode: `{policy.effective_mode}`",
        "",
        "## Verdict по imported findings",
        "",
    ]
    for item in verdicts:
        lines += [
            f"### {item.finding_id}",
            "",
            f"- section: `{item.section_id}` ({item.section_title})",
            f"- severity: `{item.severity}`",
            f"- review_status: `{item.review_status}`",
            f"- decision: `{item.decision}`",
            f"- evidence: {item.evidence}",
            f"- finding: {item.finding_text}",
            "",
        ]
    return "\n".join(lines)


def render_runtime_md(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Applied Runtime SQL",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Runtime lane results",
        "",
    ]
    if not results:
        lines.append("- No runtime actions were provided.")
        return "\n".join(lines)

    for row in results:
        lines += [
            f"### {row.get('id', 'runtime_action')}",
            "",
            f"- finding_id: `{row.get('finding_id', '')}`",
            f"- status: `{row.get('status', '')}`",
            f"- reason: {row.get('reason', '')}",
            f"- stdout: {row.get('stdout', '') or '(empty)'}",
            f"- stderr: {row.get('stderr', '') or '(empty)'}",
            "",
            "```sql",
            row.get("sql", "").strip(),
            "```",
            "",
        ]
    return "\n".join(lines)


def render_repo_md(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Applied Repo Changes",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Repo lane results",
        "",
    ]
    if not results:
        lines.append("- No repo changes were requested.")
        return "\n".join(lines)

    for row in results:
        lines += [
            f"- path: `{row.get('path', '')}` | finding_id: `{row.get('finding_id', '')}` | status: `{row.get('status', '')}` | reason: {row.get('reason', '')}",
        ]
    lines.append("")
    return "\n".join(lines)


def render_postcheck_md(
    steps: list[str],
    checks: list[dict[str, Any]],
    error: str | None,
) -> str:
    lines = [
        "# Postcheck Report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Step sequence",
        "",
    ]
    for step in steps:
        lines.append(f"- {step}")
    lines.append("")

    lines += ["## Checks", ""]
    if checks:
        for item in checks:
            lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
    else:
        lines.append("- No checks executed.")
    lines.append("")

    lines += ["## Pipeline status", ""]
    if error:
        lines.append(f"- failed: {error}")
    else:
        lines.append("- success")
    lines.append("")
    return "\n".join(lines)


def render_rollback_md(backup: BackupResult | None, repo_results: list[dict[str, Any]]) -> str:
    lines = [
        "# Rollback Guide",
        "",
        f"Generated: {utc_now()}",
        "",
    ]

    if backup:
        lines += [
            f"- backup_root: `{backup.backup_root}`",
            f"- runtime_metadata: `{backup.runtime_metadata_path}`",
        ]
        for snap in backup.repo_snapshot_paths:
            lines.append(f"- repo_snapshot: `{snap}`")
    else:
        lines.append("- backup snapshot is unavailable.")

    lines += [
        "",
        "## Rollback checklist",
        "",
        "1. Restore repo files from snapshot paths if repo lane applied changes.",
        "2. Re-run precheck and postcheck in plan_only mode.",
        "3. For runtime SQL, execute manual rollback SQL based on applied-runtime-sql.md history.",
        "4. Record incident notes and rerun review-sql-find to confirm risk state.",
        "",
    ]

    applied_paths = [r.get("path") for r in repo_results if r.get("status") == "applied"]
    if applied_paths:
        lines.append("## Applied repo paths")
        lines.append("")
        for path in applied_paths:
            lines.append(f"- `{path}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    steps: list[str] = []
    checks: list[dict[str, Any]] = []
    policy: PolicyDecision | None = None
    backup: BackupResult | None = None
    verdicts: list[FindingVerdict] = []
    runtime_results: list[dict[str, Any]] = []
    repo_results: list[dict[str, Any]] = []
    error: str | None = None
    payload: dict[str, Any] = {}

    try:
        steps.append("backup -> precheck -> apply -> postcheck -> artifacts (required sequence)")
        payload = load_payload(Path(args.input))

        steps.append("backup:started")
        policy = enforce(payload)
        backup = create_snapshot(payload)
        steps.append("backup:completed")

        steps.append("precheck:started")
        sections = extract_sections(payload["findings_bundle"])
        for section in sections:
            if section.get("status") == "INCOMPLETE" or contains_truncation(section):
                raise PipelineError(f"precheck failed: section {section['id']} is incomplete/truncated")
        verdicts, finding_status_map = build_verdicts(sections, payload)
        steps.append("precheck:completed")

        steps.append("apply:started")
        runtime_actions = build_runtime_actions(payload, sections)
        runtime_results = apply_runtime_lane(runtime_actions, finding_status_map, policy, payload)
        repo_results = apply_repo_lane(payload, finding_status_map, policy)
        steps.append("apply:completed")

        steps.append("postcheck:started")
        payload["_effective_mode"] = policy.effective_mode
        checks = run_postchecks(payload, repo_results)
        steps.append("postcheck:completed")

    except (PipelineError, SafetyGuardError) as exc:
        error = str(exc)
        steps.append("pipeline:failed")
    except Exception as exc:  # pragma: no cover
        error = f"unexpected error: {exc}"
        steps.append("pipeline:failed")

    if policy is None:
        fallback_payload = payload if isinstance(payload, dict) else {}
        try:
            policy = enforce(
                {
                    "environment": fallback_payload.get("environment", "prod"),
                    "scope": fallback_payload.get("scope", "custom"),
                    "source": fallback_payload.get("source", "section_summaries"),
                    "fix_mode": "plan_only",
                    "findings_bundle": fallback_payload.get("findings_bundle", {"sections": []}),
                }
            )
        except SafetyGuardError:
            policy = PolicyDecision(
                environment="prod",
                scope="custom",
                source="section_summaries",
                requested_fix_mode="plan_only",
                effective_mode="plan_only",
                allow_apply=False,
                allow_dangerous=False,
                notes=["fallback policy used"],
            )

    steps.append("artifacts:started")
    write_markdown(output_dir / "fix-verdict.md", render_verdict_md(verdicts, policy))
    write_markdown(output_dir / "applied-runtime-sql.md", render_runtime_md(runtime_results))
    write_markdown(output_dir / "applied-repo-changes.md", render_repo_md(repo_results))
    write_markdown(output_dir / "postcheck-report.md", render_postcheck_md(steps, checks, error))
    write_markdown(output_dir / "rollback-guide.md", render_rollback_md(backup, repo_results))
    steps.append("artifacts:completed")

    response = {
        "ok": error is None,
        "error": error,
        "effective_mode": policy.effective_mode,
        "outputs": {
            "fix_verdict": str(output_dir / "fix-verdict.md"),
            "runtime_sql": str(output_dir / "applied-runtime-sql.md"),
            "repo_changes": str(output_dir / "applied-repo-changes.md"),
            "postcheck": str(output_dir / "postcheck-report.md"),
            "rollback": str(output_dir / "rollback-guide.md"),
        },
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0 if error is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
