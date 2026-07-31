#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


PROTOCOL_VERSION = "2024-11-05"
SERVER_VERSION = "0.1.0"
IO_MODE = "framed"

ROOT_DIR = Path(__file__).resolve().parents[2]
INT_ROOT = ROOT_DIR.parent
BRAIN_MCP = INT_ROOT / "brain" / "client" / "mcp" / "intbrain" / "bin" / "mcp-intbrain.py"


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


COMMON_RUN_PROPS = {
    "cwd": {"type": "string", "description": "Working directory under D:/int. Defaults to D:/int/tools."},
    "timeout_sec": {"type": "integer", "description": "Command timeout in seconds."},
}


def _args_prop(description: str = "Structured command arguments.") -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "description": description}


def _path_prop(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _mutation_props() -> dict[str, Any]:
    return {
        "confirm_mutation": {"type": "boolean"},
        "issue_context": {
            "type": "string",
            "pattern": r"^#[1-9][0-9]*$",
            "description": "Current LeoTechPro/int GitHub issue identifier, e.g. #800.",
        },
    }


def _spec_level_prop() -> dict[str, Any]:
    return {
        "type": "string",
        "enum": ["delta", "full"],
        "description": "Risk-based OpenSpec profile. `none` must not create a change package.",
    }


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": _schema(properties, required)}


def _load_browser_profile_registry() -> dict[str, dict[str, Any]]:
    path = ROOT_DIR / "codex" / "config" / "browser-profiles.v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = raw.get("profiles") if isinstance(raw, dict) else None
    if not isinstance(profiles, dict):
        raise RuntimeError(f"invalid browser profile registry: {path}")
    return profiles


BROWSER_PROFILE_REGISTRY = _load_browser_profile_registry()
BROWSER_PROFILE_NAMES = sorted(BROWSER_PROFILE_REGISTRY)


OPEN_SPEC_TOOLS = [
    _tool("openspec_list", "List OpenSpec changes or specs.", {**COMMON_RUN_PROPS, "specs": {"type": "boolean"}}),
    _tool("openspec_show", "Show an OpenSpec change or spec.", {**COMMON_RUN_PROPS, "item": {"type": "string"}, "json": {"type": "boolean"}}, ["item"]),
    _tool("openspec_validate", "Validate an OpenSpec change/spec or full catalog, optionally enforcing a delta/full profile.", {**COMMON_RUN_PROPS, "item": {"type": "string"}, "strict": {"type": "boolean"}, "spec_level": _spec_level_prop()}),
    _tool("openspec_status", "Show OpenSpec artifact completion status.", {**COMMON_RUN_PROPS, "item": {"type": "string"}}),
    _tool("openspec_instructions", "Output enriched OpenSpec instructions for an artifact.", {**COMMON_RUN_PROPS, "artifact": {"type": "string"}, "args": _args_prop("Additional OpenSpec instruction arguments.")}, ["artifact"]),
    _tool("openspec_archive", "Archive a completed OpenSpec change. Mutating; requires confirmation and issue context.", {**COMMON_RUN_PROPS, **_mutation_props(), "change_name": {"type": "string"}, "args": _args_prop()}, ["confirm_mutation", "issue_context", "change_name"]),
    _tool("openspec_change_mutate", "Run a mutating `openspec change` subcommand. Requires confirmation and issue context.", {**COMMON_RUN_PROPS, **_mutation_props(), "subcommand": {"type": "string"}, "args": _args_prop()}, ["confirm_mutation", "issue_context", "subcommand"]),
    _tool("openspec_spec_mutate", "Run a mutating `openspec spec` subcommand. Requires confirmation and issue context.", {**COMMON_RUN_PROPS, **_mutation_props(), "subcommand": {"type": "string"}, "args": _args_prop()}, ["confirm_mutation", "issue_context", "subcommand"]),
    _tool("openspec_new", "Create a delta/full OpenSpec change. `none` is rejected.", {**COMMON_RUN_PROPS, **_mutation_props(), "spec_level": _spec_level_prop(), "args": _args_prop()}, ["confirm_mutation", "issue_context", "spec_level", "args"]),
    _tool("openspec_exec_mutate", "Run a mutating structured OpenSpec CLI command. Requires confirmation and issue context.", {**COMMON_RUN_PROPS, **_mutation_props(), "args": _args_prop("Arguments after the openspec executable.")}, ["confirm_mutation", "issue_context", "args"]),
]

GOVERNANCE_TOOLS = [
    _tool("routing_validate", "Validate high-risk agent tool routing registry.", {**COMMON_RUN_PROPS, "strict": {"type": "boolean"}, "json": {"type": "boolean"}}),
    _tool("routing_resolve", "Resolve a logical high-risk tooling intent.", {**COMMON_RUN_PROPS, "intent": {"type": "string"}, "platform": {"type": "string"}, "json": {"type": "boolean"}}, ["intent"]),
]

RUNTIME_TOOLS = [
    _tool("host_preflight", "Run Codex preflight.", {**COMMON_RUN_PROPS, "json": {"type": "boolean"}}),
    _tool("host_verify", "Run Codex host verification.", {**COMMON_RUN_PROPS, "args": _args_prop()}),
    _tool("host_bootstrap", "Run Codex host bootstrap. Mutating; requires confirmation.", {**COMMON_RUN_PROPS, **_mutation_props(), "args": _args_prop()}, ["confirm_mutation", "issue_context"]),
    _tool("recovery_bundle", "Create a Codex recovery bundle. Mutating; requires confirmation.", {**COMMON_RUN_PROPS, **_mutation_props(), "args": _args_prop()}, ["confirm_mutation", "issue_context"]),
    _tool("ssh_resolve", "Resolve IntData SSH host transport and optional destination-only diagnostics.", {**COMMON_RUN_PROPS, "host": {"type": "string"}, "mode": {"type": "string"}, "json": {"type": "boolean"}, "destination_only": {"type": "boolean"}}, ["host"]),
    _tool(
        "ssh_execute",
        "Run a bounded structured command through native OpenSSH. Mutating mode requires confirmation and issue context.",
        {
            **COMMON_RUN_PROPS,
            **_mutation_props(),
            "host": {"type": "string", "description": "Explicit SSH alias or [user@]host."},
            "argv": _args_prop("Remote command argv; no local shell is used."),
            "remote_cwd": {"type": "string"},
            "mode": {"type": "string", "enum": ["auto", "tailnet", "public"]},
            "max_output_bytes": {"type": "integer", "minimum": 1024, "maximum": 1048576},
        },
        ["confirm_mutation", "issue_context", "host", "argv"],
    ),
    _tool("browser_profile_launch", "Deprecated compatibility: launch an allowed Firefox MCP profile. Mutating; requires confirmation.", {**COMMON_RUN_PROPS, **_mutation_props(), "profile": {"type": "string", "enum": BROWSER_PROFILE_NAMES}, "args": _args_prop("Optional launcher arguments.")}, ["confirm_mutation", "issue_context", "profile"]),
]

DBA_TOOLS = [
    _tool("intdata_cli", "Run a profile allowlisted CLI command with structured arguments.", {**COMMON_RUN_PROPS, **_mutation_props(), "command": {"type": "string"}, "profile": {"type": "string", "description": "DBA profile injected as --profile/--target for commands that require one."}, "args": _args_prop()}, ["command"]),
]

VAULT_TOOLS = [
    _tool("intdata_vault_sanitize", "Run vault sanitizer. Defaults to dry-run; non-dry-run requires confirmation.", {**COMMON_RUN_PROPS, **_mutation_props(), "dry_run": {"type": "boolean"}, "vault_root": _path_prop("Vault root. Defaults to D:/int/2brain on this host."), "brain_root": _path_prop("Brain repo root. Defaults to D:/int/brain on this host."), "tools_root": _path_prop("Tools repo root. Defaults to D:/int/tools."), "runtime_root": _path_prop("Runtime vault root override."), "args": _args_prop()}),
    _tool("intdata_runtime_vault_gc", "Run runtime vault GC. Defaults to dry-run; non-dry-run requires confirmation.", {**COMMON_RUN_PROPS, **_mutation_props(), "dry_run": {"type": "boolean"}, "brain_root": _path_prop("Brain repo root. Defaults to D:/int/brain on this host."), "runtime_root": _path_prop("Runtime vault root override."), "archive_root": _path_prop("Archive root override. Defaults to D:/int/.tmp."), "args": _args_prop()}),
]

RUNTIME_TOOLS.extend(VAULT_TOOLS)
CONTROL_TOOLS = [*OPEN_SPEC_TOOLS, *GOVERNANCE_TOOLS]
PROFILE_TOOLS: dict[str, list[dict[str, Any]]] = {
    "intbrain": [],
    "intdata-control": CONTROL_TOOLS,
    "intdata-runtime": RUNTIME_TOOLS,
    "dba": DBA_TOOLS,
}

OPEN_SPEC_READ_ONLY = {"list", "show", "validate", "status", "instructions", "templates", "schemas", "completion", "help"}
PROFILE_COMMANDS: dict[str, dict[str, list[str]]] = {"dba": {"dba": [sys.executable, str(ROOT_DIR / "dba" / "lib" / "dba.py")]}}


def _safe_args(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("args must be an array of strings")
    return raw


def _string_arg(arguments: dict[str, Any], key: str) -> str | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _append_path_arg(argv: list[str], arguments: dict[str, Any], key: str, flag: str, default: Path | None = None) -> None:
    value = _string_arg(arguments, key)
    if value is None and default is not None:
        value = str(default)
    if value:
        argv.extend([flag, value])


def _has_arg(args: list[str], flag: str) -> bool:
    return flag in args


def _cwd(raw: Any) -> str:
    base = Path(str(raw or ROOT_DIR)).resolve()
    allowed_roots = [ROOT_DIR.resolve(), INT_ROOT.resolve()]
    if not any(base == root or root in base.parents for root in allowed_roots):
        raise ValueError(f"cwd must be under {INT_ROOT}")
    return str(base)


def _require_mutation(arguments: dict[str, Any]) -> None:
    if arguments.get("confirm_mutation") is not True:
        raise PermissionError("mutating command requires confirm_mutation=true")
    issue = str(arguments.get("issue_context") or "").strip()
    if not re.fullmatch(r"#[1-9][0-9]*", issue):
        raise PermissionError("mutating command requires issue_context like #800")


def _require_spec_level(arguments: dict[str, Any]) -> str:
    level = arguments.get("spec_level")
    if level not in {"delta", "full"}:
        raise ValueError("spec_level must be `delta` or `full`; `none` must not create an OpenSpec change")
    return str(level)


def _new_change_name(arguments: dict[str, Any]) -> str:
    args = _safe_args(arguments.get("args"))
    if len(args) < 2 or args[0] != "change":
        raise ValueError("openspec_new args must start with `change` followed by `issue-N-slug`")
    change_name = args[1]
    match = re.fullmatch(r"issue-([1-9][0-9]*)-[a-z0-9][a-z0-9-]*", change_name)
    if not match:
        raise ValueError("OpenSpec change name must match issue-N-slug")
    issue_match = re.fullmatch(r"#([1-9][0-9]*)", str(arguments.get("issue_context") or "").strip())
    if not issue_match or match.group(1) != issue_match.group(1):
        raise ValueError(f"OpenSpec change {change_name!r} does not match issue_context")
    return change_name


def _openspec_profile_errors(repo_root: Path, change_name: str, spec_level: str) -> list[str]:
    change_dir = repo_root / "openspec" / "changes" / change_name
    if not change_dir.is_dir():
        return [f"missing OpenSpec change directory: {change_dir}"]

    errors: list[str] = []
    name_match = re.fullmatch(r"issue-([1-9][0-9]*)-[a-z0-9][a-z0-9-]*", change_name)
    if not name_match:
        errors.append("change name must match issue-N-slug")

    proposal = change_dir / "proposal.md"
    specs_root = change_dir / "specs"
    specs = sorted(specs_root.glob("*/spec.md")) if specs_root.is_dir() else []
    if not proposal.is_file():
        errors.append("missing proposal.md")
    if not specs:
        errors.append("missing specs/<capability>/spec.md")
    if proposal.is_file() and name_match:
        issue_url = f"https://github.com/LeoTechPro/int/issues/{name_match.group(1)}"
        if issue_url not in proposal.read_text(encoding="utf-8"):
            errors.append(f"proposal.md must link to {issue_url}")

    design = change_dir / "design.md"
    tasks = change_dir / "tasks.md"
    readme = change_dir / "README.md"
    if spec_level == "delta":
        for forbidden in (design, tasks, readme):
            if forbidden.exists():
                errors.append(f"delta profile forbids {forbidden.name}")
    elif spec_level == "full":
        if not design.is_file():
            errors.append("full profile requires design.md")
        if not tasks.is_file():
            errors.append("full profile requires tasks.md")
        if design.is_file() and not re.search(
            r"^## (?:Rollback|Migration Plan)\b",
            design.read_text(encoding="utf-8"),
            re.MULTILINE,
        ):
            errors.append("full profile design.md requires a Rollback or Migration Plan section")
    else:
        errors.append("spec_level must be delta or full")
    return errors


def _remove_scaffold_readme(cwd: str, change_name: str) -> None:
    readme = Path(cwd) / "openspec" / "changes" / change_name / "README.md"
    if readme.is_file():
        readme.unlink()


def _run(argv: list[str], *, cwd: str, timeout_sec: int | None = None) -> dict[str, Any]:
    timeout = int(timeout_sec or 60)
    completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, shell=False)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "argv": argv, "cwd": cwd, "stdout": completed.stdout, "stderr": completed.stderr}


def _script_entrypoint(name: str, *, windows_ext: str = ".cmd") -> list[str]:
    path = ROOT_DIR / "codex" / "bin" / f"{name}{windows_ext if os.name == 'nt' else ''}"
    if os.name == "nt":
        return ["cmd.exe", "/d", "/s", "/c", str(path)]
    return [str(path)]


def _powershell_base() -> list[str]:
    candidates = ("pwsh", "powershell.exe", "powershell") if os.name == "nt" else ("pwsh", "powershell")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, "-NoProfile", "-ExecutionPolicy", "Bypass"]
    fallback = "powershell.exe" if os.name == "nt" else "pwsh"
    return [fallback, "-NoProfile", "-ExecutionPolicy", "Bypass"]


def _openspec_base() -> list[str]:
    if os.name == "nt":
        return [*_powershell_base(), "-File", str(ROOT_DIR / "codex" / "bin" / "openspec.ps1")]
    return [str(ROOT_DIR / "codex" / "bin" / "openspec")]


def _is_openspec_mutating(args: list[str]) -> bool:
    if not args:
        return False
    command = args[0]
    if command in OPEN_SPEC_READ_ONLY:
        return False
    if command in {"change", "spec"} and len(args) > 1 and args[1] in {"list", "show", "get"}:
        return False
    return True


def _call_openspec(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _cwd(arguments.get("cwd"))
    timeout = arguments.get("timeout_sec")
    if name == "openspec_list":
        args = ["list"]
        if arguments.get("specs"):
            args.append("--specs")
    elif name == "openspec_show":
        args = ["show", str(arguments["item"])]
        if arguments.get("json"):
            args.append("--json")
    elif name == "openspec_validate":
        args = ["validate"]
        if arguments.get("strict"):
            args.append("--strict")
        if arguments.get("item"):
            args.append(str(arguments["item"]))
        if arguments.get("spec_level") is not None and not arguments.get("item"):
            raise ValueError("profile validation requires `item` with an issue-N-slug change name")
    elif name == "openspec_status":
        args = ["status"]
        if arguments.get("item"):
            args.append(str(arguments["item"]))
    elif name == "openspec_instructions":
        args = ["instructions", str(arguments["artifact"]), *_safe_args(arguments.get("args"))]
    elif name == "openspec_archive":
        _require_mutation(arguments)
        args = ["archive", str(arguments["change_name"]), *_safe_args(arguments.get("args"))]
    elif name == "openspec_change_mutate":
        _require_mutation(arguments)
        args = ["change", str(arguments["subcommand"]), *_safe_args(arguments.get("args"))]
        if not _is_openspec_mutating(args):
            raise ValueError("openspec_change_mutate cannot run read-only subcommands")
    elif name == "openspec_spec_mutate":
        _require_mutation(arguments)
        args = ["spec", str(arguments["subcommand"]), *_safe_args(arguments.get("args"))]
        if not _is_openspec_mutating(args):
            raise ValueError("openspec_spec_mutate cannot run read-only subcommands")
    elif name == "openspec_new":
        _require_mutation(arguments)
        _require_spec_level(arguments)
        change_name = _new_change_name(arguments)
        args = ["new", *_safe_args(arguments.get("args"))]
    elif name == "openspec_exec_mutate":
        _require_mutation(arguments)
        args = _safe_args(arguments.get("args"))
        if not _is_openspec_mutating(args):
            raise ValueError("openspec_exec_mutate cannot run read-only commands")
    else:
        raise ValueError(f"unknown openspec tool: {name}")
    result = _run([*_openspec_base(), *args], cwd=cwd, timeout_sec=timeout)
    if name == "openspec_validate" and arguments.get("spec_level") is not None:
        profile_errors = _openspec_profile_errors(
            Path(cwd),
            str(arguments["item"]),
            _require_spec_level(arguments),
        )
        result["profile_errors"] = profile_errors
        if profile_errors:
            result["ok"] = False
    elif name == "openspec_new" and result.get("ok"):
        _remove_scaffold_readme(cwd, change_name)
    return result


def _call_governance(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _cwd(arguments.get("cwd"))
    timeout = arguments.get("timeout_sec")
    if name == "routing_validate":
        argv = [sys.executable, str(ROOT_DIR / "codex" / "bin" / "agent_tool_routing.py"), "validate"]
        if arguments.get("strict"):
            argv.append("--strict")
        if arguments.get("json"):
            argv.append("--json")
        return _run(argv, cwd=cwd, timeout_sec=timeout)
    if name == "routing_resolve":
        argv = [sys.executable, str(ROOT_DIR / "codex" / "bin" / "agent_tool_routing.py"), "resolve", "--intent", str(arguments["intent"])]
        if arguments.get("platform"):
            argv.extend(["--platform", str(arguments["platform"])])
        if arguments.get("json"):
            argv.append("--json")
        return _run(argv, cwd=cwd, timeout_sec=timeout)
    raise ValueError(f"unknown governance tool: {name}")


def _call_runtime(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _cwd(arguments.get("cwd"))
    timeout = arguments.get("timeout_sec")
    if name == "host_verify":
        payload = _run([*_script_entrypoint("codex-host-verify"), *_safe_args(arguments.get("args"))], cwd=cwd, timeout_sec=timeout)
        output = f"{payload.get('stdout', '')}\n{payload.get('stderr', '')}"
        verify_ok = payload["returncode"] == 0 and "codex host verify: FAILED" not in output
        payload["verify_ok"] = verify_ok
        payload["ok"] = verify_ok
        return payload
    if name == "host_preflight":
        argv = [*_powershell_base(), "-File", str(ROOT_DIR / "codex" / "scripts" / "codex_preflight.ps1")]
        if arguments.get("json"):
            argv.append("-Json")
        payload = _run(argv, cwd=cwd, timeout_sec=timeout)
        payload["preflight_ok"] = payload["ok"]
        payload["ok"] = True
        return payload
    if name == "host_bootstrap":
        _require_mutation(arguments)
        return _run([*_script_entrypoint("codex-host-bootstrap"), *_safe_args(arguments.get("args"))], cwd=cwd, timeout_sec=timeout or 300)
    if name == "recovery_bundle":
        _require_mutation(arguments)
        return _run([*_script_entrypoint("codex-recovery-bundle"), *_safe_args(arguments.get("args"))], cwd=cwd, timeout_sec=timeout or 300)
    if name == "ssh_resolve":
        argv = [sys.executable, str(ROOT_DIR / "codex" / "bin" / "int_ssh_resolve.py"), "--requested-host", str(arguments["host"]), "--capability", "int_ssh_resolve", "--binding-origin", "codex/bin/mcp-intdata-cli.py"]
        if arguments.get("mode"):
            argv.extend(["--mode", str(arguments["mode"])])
        if arguments.get("json"):
            argv.append("--json")
        if arguments.get("destination_only"):
            argv.append("--destination-only")
        return _run(argv, cwd=cwd, timeout_sec=timeout)
    if name == "ssh_execute":
        _require_mutation(arguments)
        if not re.fullmatch(r"#[1-9][0-9]*", str(arguments.get("issue_context") or "")):
            raise PermissionError("arbitrary SSH execution requires issue_context=#N")
        argv = [
            sys.executable,
            str(ROOT_DIR / "codex" / "bin" / "int_ssh_exec.py"),
            "--host",
            str(arguments["host"]),
            "--json",
        ]
        if arguments.get("remote_cwd"):
            argv.extend(["--remote-cwd", str(arguments["remote_cwd"])])
        if arguments.get("mode"):
            argv.extend(["--mode", str(arguments["mode"])])
        if timeout is not None:
            argv.extend(["--timeout-sec", str(timeout)])
        if arguments.get("max_output_bytes") is not None:
            argv.extend(["--max-output-bytes", str(arguments["max_output_bytes"])])
        argv.extend(["--", *_safe_args(arguments.get("argv"))])
        return _run(argv, cwd=cwd, timeout_sec=(int(timeout) + 5) if timeout is not None else 35)
    if name == "browser_profile_launch":
        _require_mutation(arguments)
        profile = str(arguments["profile"])
        profile_config = BROWSER_PROFILE_REGISTRY.get(profile)
        if not profile_config:
            raise ValueError(f"unknown browser profile: {profile}")
        argv = [sys.executable, str(ROOT_DIR / "codex" / "bin" / "firefox_mcp_launcher.py"), "--capability", str(profile_config["capability"]), "--binding-origin", "codex/bin/mcp-intdata-cli.py", "--profile-key", str(profile_config["profile_key"]), "--start-url", str(profile_config["start_url"]), "--viewport", str(profile_config.get("viewport", "1440x900")), *_safe_args(arguments.get("args"))]
        return _run(argv, cwd=cwd, timeout_sec=timeout)
    raise ValueError(f"unknown runtime tool: {name}")


def _call_dba(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name != "intdata_cli":
        raise ValueError(f"unknown dba tool: {name}")
    command = str(arguments["command"])
    commands = PROFILE_COMMANDS["dba"]
    if command not in commands:
        raise ValueError(f"unknown dba command: {command}")
    args = _safe_args(arguments.get("args"))
    profile = _string_arg(arguments, "profile")
    if profile and args:
        if args[:1] in (["doctor"], ["sql"], ["file"]) and "--profile" not in args:
            args = [args[0], "--profile", profile, *args[1:]]
        elif args[:2] == ["migrate", "status"] and "--target" not in args:
            args = [args[0], args[1], "--target", profile, *args[2:]]
    safe_dba = not args or args[:1] in (["doctor"], ["--help"], ["-h"], ["help"]) or args[:2] == ["migrate", "status"]
    if not safe_dba:
        _require_mutation(arguments)
    return _run([*commands[command], *args], cwd=_cwd(arguments.get("cwd")), timeout_sec=arguments.get("timeout_sec"))


def _call_vault(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    cwd = _cwd(arguments.get("cwd"))
    args = _safe_args(arguments.get("args"))
    dry_run = arguments.get("dry_run", True) is not False
    if dry_run and _has_arg(args, "--apply"):
        raise ValueError("--apply requires dry_run=false and mutation confirmation")
    if not dry_run and _has_arg(args, "--dry-run"):
        raise ValueError("dry_run=false cannot be combined with --dry-run")
    if not dry_run:
        _require_mutation(arguments)
    script = "vault_sanitize.py" if name == "intdata_vault_sanitize" else "runtime_vault_gc.py"
    argv = [sys.executable, str(ROOT_DIR / "vault" / "installers" / script)]
    if dry_run:
        argv.append("--dry-run")
    else:
        argv.append("--apply")
    if name == "intdata_vault_sanitize":
        _append_path_arg(argv, arguments, "vault_root", "--vault-root", INT_ROOT / "2brain")
        _append_path_arg(argv, arguments, "brain_root", "--brain-root", INT_ROOT / "brain")
        _append_path_arg(argv, arguments, "tools_root", "--tools-root", ROOT_DIR)
        _append_path_arg(argv, arguments, "runtime_root", "--runtime-root")
    else:
        _append_path_arg(argv, arguments, "brain_root", "--brain-root", INT_ROOT / "brain")
        _append_path_arg(argv, arguments, "runtime_root", "--runtime-root")
        _append_path_arg(argv, arguments, "archive_root", "--archive-root")
    argv.extend(args)
    return _run(argv, cwd=cwd, timeout_sec=arguments.get("timeout_sec") or 300)


def _call_tool(profile: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if profile == "intdata-control":
        if name.startswith("openspec_"):
            return _call_openspec(name, arguments)
        return _call_governance(name, arguments)
    if profile == "intdata-runtime":
        if name in {tool["name"] for tool in VAULT_TOOLS}:
            return _call_vault(name, arguments)
        return _call_runtime(name, arguments)
    if profile == "dba":
        return _call_dba(name, arguments)
    raise ValueError(f"unknown profile: {profile}")


def _json_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _json_error(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


def _text_content(value: Any) -> dict[str, str]:
    return {"type": "text", "text": json.dumps(value, ensure_ascii=False)}


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if IO_MODE == "jsonl":
        sys.stdout.write(body.decode("utf-8"))
        sys.stdout.write("\n")
        sys.stdout.flush()
        return
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    global IO_MODE
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None
    first_decoded = first_line.decode("utf-8", errors="ignore").strip()
    if first_decoded.startswith("{"):
        IO_MODE = "jsonl"
        return json.loads(first_decoded)
    headers: dict[str, str] = {}
    line = first_line
    while True:
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("utf-8", errors="ignore").strip()
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        line = sys.stdin.buffer.readline()
        if not line:
            return None
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def _handle(profile: str, request: dict[str, Any]) -> dict[str, Any] | None:
    req_id = request.get("id")
    method = str(request.get("method") or "")
    params = request.get("params") or {}
    if method == "initialize":
        requested = str((params or {}).get("protocolVersion") or "").strip()
        return _json_result(req_id, {"protocolVersion": requested or PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": f"{profile}-mcp", "version": SERVER_VERSION}})
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return _json_result(req_id, {})
    if method == "tools/list":
        return _json_result(req_id, {"tools": PROFILE_TOOLS[profile]})
    if method == "tools/call":
        name = str((params or {}).get("name") or "")
        arguments = (params or {}).get("arguments") or {}
        if not name:
            return _json_error(req_id, -32602, "tools/call requires name")
        try:
            payload = _call_tool(profile, name, dict(arguments))
            return _json_result(req_id, {"content": [_text_content(payload)], "isError": not bool(payload.get("ok"))})
        except Exception as exc:  # noqa: BLE001
            return _json_result(req_id, {"content": [_text_content({"ok": False, "error": str(exc)})], "isError": True})
    return _json_error(req_id, -32601, f"Method not found: {method}")


def _delegate_intbrain() -> int:
    if not BRAIN_MCP.exists():
        print(json.dumps({"ok": False, "error": "config_error", "message": f"brain-owned intbrain MCP not found: {BRAIN_MCP}"}), file=sys.stderr)
        return 2
    print("warning: /int/tools intbrain profile is deprecated; delegating to /int/brain/client/mcp/intbrain", file=sys.stderr)
    os.execv(sys.executable, [sys.executable, str(BRAIN_MCP), "--stdio"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(PROFILE_TOOLS))
    args = parser.parse_args()
    if args.profile == "intbrain":
        return _delegate_intbrain()
    while True:
        message = _read_message()
        if message is None:
            return 0
        response = _handle(args.profile, message)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())
