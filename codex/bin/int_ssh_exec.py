#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from int_ssh_resolve import resolve_ssh_executable, resolve_target

DESTINATION_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,252}[A-Za-z0-9])?$")
MAX_ARGV_ITEMS = 64
MAX_ARG_BYTES = 4096
DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_OUTPUT_BYTES = 262144


def validate_destination(value: str) -> str:
    destination = value.strip()
    if not destination or destination.startswith("-") or not DESTINATION_RE.fullmatch(destination):
        raise ValueError("SSH destination must be an explicit safe alias or [user@]host")
    return destination


def validate_argv(raw: Sequence[str]) -> list[str]:
    argv = list(raw)
    if not argv or len(argv) > MAX_ARGV_ITEMS:
        raise ValueError(f"argv must contain 1..{MAX_ARGV_ITEMS} strings")
    for item in argv:
        if not isinstance(item, str) or not item or "\x00" in item or len(item.encode("utf-8")) > MAX_ARG_BYTES:
            raise ValueError("argv contains an invalid or oversized item")
    return argv


def build_remote_command(argv: Sequence[str], remote_cwd: str | None = None) -> str:
    safe_argv = validate_argv(argv)
    command = "exec " + shlex.join(safe_argv)
    if remote_cwd is None:
        return command
    cwd = remote_cwd.strip()
    if not cwd or "\x00" in cwd or len(cwd.encode("utf-8")) > MAX_ARG_BYTES:
        raise ValueError("remote_cwd is invalid or oversized")
    return f"cd -- {shlex.quote(cwd)} && {command}"


def build_ssh_command(host: str, argv: Sequence[str], *, remote_cwd: str | None = None, mode: str | None = None) -> tuple[list[str], dict[str, Any]]:
    requested = validate_destination(host)
    route = resolve_target(requested, mode=mode)
    ssh_args = list(route["ssh_args"])
    if not ssh_args:
        raise RuntimeError("SSH route returned no arguments")
    # Unknown names are accepted only because the caller supplied that exact
    # destination. Nothing is inferred or substituted.
    if route.get("logical_host") is None:
        ssh_args = [requested]
    command = [
        resolve_ssh_executable(),
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "StrictHostKeyChecking=yes",
        *ssh_args,
        build_remote_command(argv, remote_cwd),
    ]
    return command, route


def _run_bounded(command: Sequence[str], *, timeout: int, output_limit: int) -> tuple[int, bytes, bytes, bool, bool]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    totals = {"stdout": 0, "stderr": 0}

    def drain(name: str, stream: Any) -> None:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            totals[name] += len(chunk)
            remaining = output_limit - len(captured[name])
            if remaining > 0:
                captured[name].extend(chunk[:remaining])

    threads = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        returncode = 124
    for thread in threads:
        thread.join(timeout=2)
    truncated = totals["stdout"] > output_limit or totals["stderr"] > output_limit
    return returncode, bytes(captured["stdout"]), bytes(captured["stderr"]), truncated, timed_out


def execute(host: str, argv: Sequence[str], *, remote_cwd: str | None = None, mode: str | None = None, timeout_sec: int = DEFAULT_TIMEOUT_SEC, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> dict[str, Any]:
    timeout = max(1, min(300, int(timeout_sec)))
    output_limit = max(1024, min(1048576, int(max_output_bytes)))
    command, route = build_ssh_command(host, argv, remote_cwd=remote_cwd, mode=mode)
    returncode, stdout_raw, stderr_raw, truncated, timed_out = _run_bounded(command, timeout=timeout, output_limit=output_limit)
    return {
        "ok": returncode == 0,
        "returncode": returncode,
        "stdout": stdout_raw.decode("utf-8", errors="replace"),
        "stderr": stderr_raw.decode("utf-8", errors="replace"),
        "truncated": truncated,
        "timed_out": timed_out,
        "destination": route.get("destination"),
        "transport": route.get("transport"),
        "resolver_fallback_used": bool(route.get("fallback_used")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded command through native OpenSSH")
    parser.add_argument("--host", required=True)
    parser.add_argument("--remote-cwd")
    parser.add_argument("--mode", choices=("auto", "tailnet", "public"))
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command_argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    payload = execute(args.host, command_argv, remote_cwd=args.remote_cwd, mode=args.mode, timeout_sec=args.timeout_sec, max_output_bytes=args.max_output_bytes)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload["stdout"], end="")
        if payload["stderr"]:
            print(payload["stderr"], end="", file=__import__("sys").stderr)
    return 0 if payload["ok"] else int(payload["returncode"] or 1)


if __name__ == "__main__":
    raise SystemExit(main())
