#!/usr/bin/env python3
"""Check and manage host-native Codex MCP registrations for intData."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROFILES = ("intdata-control", "intdata-runtime")
SECRET_OPTION_NAMES = {"password", "passwd", "secret", "bearer", "api-key", "apikey", "access-token", "token"}
EXPECTED_COUNTS = {"intdata-control": 12, "intdata-runtime": 9}
ROOT = Path(__file__).resolve().parents[2]
ADAPTER = (ROOT / "codex" / "bin" / "mcp-intdata-cli.py").resolve()
DEFAULT_BACKUP_DIR = ROOT / ".runtime" / "intdata-mcp-registration" / "backups"
Runner = Callable[..., subprocess.CompletedProcess[str]]


class RegistrationError(RuntimeError):
    pass


def run_command(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        timeout=30,
        **kwargs,
    )


def require_absolute_file(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise RegistrationError(f"{label} must be an existing absolute file")
    return path.resolve()


def desired_rows(python: Path) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "type": "stdio",
            "command": str(python),
            "args": [str(ADAPTER), "--profile", name],
            "env": None,
            "env_vars": [],
            "cwd": None,
            "enabled": True,
            "startup_timeout_sec": None,
            "tool_timeout_sec": None,
        }
        for name in PROFILES
    }


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    transport = row.get("transport") or row
    return {
        "type": transport.get("type", "stdio"),
        "command": transport.get("command"),
        "args": transport.get("args") or [],
        "env": transport.get("env"),
        "env_vars": transport.get("env_vars") or [],
        "cwd": transport.get("cwd"),
        "enabled": row.get("enabled", True),
        "startup_timeout_sec": row.get("startup_timeout_sec"),
        "tool_timeout_sec": row.get("tool_timeout_sec"),
    }


def inventory(codex: str, runner: Runner = run_command) -> dict[str, dict[str, Any]]:
    result = runner([codex, "mcp", "list", "--json"])
    if result.returncode:
        raise RegistrationError("codex mcp list --json failed")
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RegistrationError("codex mcp list returned invalid JSON") from exc
    if not isinstance(rows, list):
        raise RegistrationError("codex mcp list returned an unexpected schema")
    return {row["name"]: normalize(row) for row in rows if isinstance(row, dict) and row.get("name") in PROFILES}


def classify(current: dict[str, dict[str, Any]], desired: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {name: "missing" if name not in current else "exact" if current[name] == wanted else "drift" for name, wanted in desired.items()}


def assert_safe_to_capture(current: dict[str, dict[str, Any]], changed: list[str]) -> None:
    for name in changed:
        row = current.get(name)
        if row and row.get("type") != "stdio":
            raise RegistrationError(f"{name} is not stdio; refusing lossy backup")
        if row and (not isinstance(row.get("command"), str) or not isinstance(row.get("args"), list)):
            raise RegistrationError(f"{name} has an unsupported stdio schema")
        if row and (row.get("env") or row.get("env_vars") or row.get("cwd")):
            raise RegistrationError(f"{name} has env/env_vars/cwd; refusing secret-bearing or non-portable backup")
        if row and (not row.get("enabled", True) or row.get("startup_timeout_sec") is not None or row.get("tool_timeout_sec") is not None):
            raise RegistrationError(f"{name} has disabled/timeout policy that codex mcp add cannot preserve")
        if row:
            tokens = [str(row.get("command", "")), *(str(value) for value in row.get("args", []))]
            serialized = " ".join(tokens)
            if "/.codex/plugins/cache/" in serialized.replace("\\", "/"):
                raise RegistrationError(f"{name} points into plugin cache; upgrade/uninstall the old plugin before native replacement")
            option_names = {
                re.split(r"[=:]", token.lstrip("-"), maxsplit=1)[0].lower().replace("_", "-")
                for token in tokens
                if token.startswith("-") or "=" in token or ":" in token
            }
            if option_names & SECRET_OPTION_NAMES or re.search(r"(?i)(password|passwd|secret|bearer|api[_-]?key|access[_-]?token)(=|:)", serialized):
                raise RegistrationError(f"{name} command/args look secret-bearing; refusing backup")


def write_backup(current: dict[str, dict[str, Any]], backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"intdata-mcp-{stamp}-{os.getpid()}.json"
    payload = {"schema": 1, "profiles": {name: current.get(name) for name in PROFILES}}
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=backup_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def remove(codex: str, name: str, runner: Runner) -> None:
    result = runner([codex, "mcp", "remove", name])
    if result.returncode:
        raise RegistrationError(f"failed to remove {name}")


def add(codex: str, name: str, row: dict[str, Any], runner: Runner) -> None:
    if row.get("type") != "stdio":
        raise RegistrationError(f"cannot restore non-stdio registration {name}")
    result = runner([codex, "mcp", "add", name, "--", row["command"], *row["args"]])
    if result.returncode:
        raise RegistrationError(f"failed to add {name}")


def restore(codex: str, captured: dict[str, Any], runner: Runner) -> None:
    if set(captured) != set(PROFILES):
        raise RegistrationError("backup must contain exactly the managed profiles")
    present = {name: row for name, row in captured.items() if row is not None}
    for name, row in present.items():
        if set(row) != {"type", "command", "args", "env", "env_vars", "cwd", "enabled", "startup_timeout_sec", "tool_timeout_sec"}:
            raise RegistrationError(f"unsupported backup row for {name}")
    assert_safe_to_capture(present, list(present))
    now = inventory(codex, runner)
    for name in PROFILES:
        if name in now:
            remove(codex, name, runner)
        row = captured.get(name)
        if row is not None:
            add(codex, name, row, runner)


def smoke(python: Path, runner: Runner = run_command) -> dict[str, int]:
    counts: dict[str, int] = {}
    for profile in PROFILES:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "intdata-registration", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
        ]
        payload = b"".join(
            b"Content-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw
            for raw in (json.dumps(request).encode() for request in requests)
        )
        proc = subprocess.run(
            [str(python), str(ADAPTER), "--profile", profile],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if proc.returncode:
            raise RegistrationError(f"{profile} native MCP process failed")
        messages: dict[int, dict[str, Any]] = {}
        rest = proc.stdout
        while rest:
            head, separator, body = rest.partition(b"\r\n\r\n")
            if not separator:
                break
            length = int(head.decode().split(":", 1)[1].strip())
            message = json.loads(body[:length])
            if isinstance(message.get("id"), int):
                messages[message["id"]] = message
            rest = body[length:]
        try:
            tools = messages[3]["result"]["tools"]
        except (KeyError, TypeError) as exc:
            raise RegistrationError(f"{profile} handshake/tools-list failed") from exc
        counts[profile] = len(tools)
        if counts[profile] != EXPECTED_COUNTS[profile]:
            raise RegistrationError(f"{profile} expected {EXPECTED_COUNTS[profile]} tools, got {counts[profile]}")
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="absolute verified Python interpreter")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args(argv)


def verify_python(python: Path, runner: Runner) -> None:
    if not os.access(python, os.X_OK):
        raise RegistrationError("--python is not executable")
    result = runner([str(python), "--version"])
    if result.returncode:
        raise RegistrationError("--python failed its version probe")


def main(argv: list[str] | None = None, runner: Runner = run_command) -> int:
    args = parse_args(argv)
    try:
        python = require_absolute_file(args.python, "--python")
        require_absolute_file(str(ADAPTER), "MCP adapter")
        verify_python(python, runner)
        if args.rollback:
            if not args.apply:
                raise RegistrationError("--rollback requires --apply")
            payload = json.loads(args.rollback.read_text(encoding="utf-8"))
            if payload.get("schema") != 1 or not isinstance(payload.get("profiles"), dict):
                raise RegistrationError("unsupported backup schema")
            current = inventory(args.codex, runner)
            assert_safe_to_capture(current, list(current))
            safety_backup = write_backup(current, args.backup_dir)
            try:
                restore(args.codex, payload["profiles"], runner)
                after = inventory(args.codex, runner)
                expected = {name: row for name, row in payload["profiles"].items() if row is not None}
                if after != expected:
                    raise RegistrationError("post-rollback registry verification failed")
            except Exception as original:
                try:
                    restore(args.codex, {name: current.get(name) for name in PROFILES}, runner)
                    if inventory(args.codex, runner) != current:
                        raise RegistrationError("safety restore verification failed")
                except Exception as recovery:
                    raise RegistrationError(f"rollback failed ({original}); safety restore also failed ({recovery}); recover manually from {safety_backup}") from recovery
                raise RegistrationError(f"rollback failed and pre-rollback state was restored: {original}; safety backup {safety_backup}") from original
            print(json.dumps({"ok": True, "action": "rollback", "backup": str(args.rollback), "pre_rollback_backup": str(safety_backup)}))
            return 0
        wanted = desired_rows(python)
        current = inventory(args.codex, runner)
        states = classify(current, wanted)
        report: dict[str, Any] = {"ok": all(v == "exact" for v in states.values()), "mode": "apply" if args.apply else "check", "profiles": states}
        if not args.apply:
            if args.smoke:
                report["smoke"] = smoke(python, runner)
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 2
        changed = [name for name, state in states.items() if state != "exact"]
        drift = [name for name, state in states.items() if state == "drift"]
        if drift and not args.replace:
            raise RegistrationError("drift exists; rerun with explicit --replace")
        assert_safe_to_capture(current, changed)
        smoke(python, runner)
        backup = write_backup(current, args.backup_dir)
        try:
            for name in changed:
                if name in current:
                    remove(args.codex, name, runner)
                add(args.codex, name, wanted[name], runner)
            after = inventory(args.codex, runner)
            final = classify(after, wanted)
            if any(value != "exact" for value in final.values()):
                raise RegistrationError("post-apply registry verification failed")
            if args.smoke:
                report["smoke"] = smoke(python, runner)
        except Exception as original:
            try:
                restore(args.codex, {name: current.get(name) for name in PROFILES}, runner)
                restored = inventory(args.codex, runner)
                if restored != current:
                    raise RegistrationError("automatic restore verification failed")
            except Exception as recovery:
                raise RegistrationError(f"apply failed ({original}); automatic restore also failed ({recovery}); registry may be partial, recover manually from {backup}") from recovery
            raise RegistrationError(f"apply failed and previous registry was restored: {original}") from original
        report.update({"ok": True, "profiles": final, "backup": str(backup)})
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, RegistrationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
