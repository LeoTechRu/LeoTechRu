#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_tool_routing import assert_binding  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT_DIR.parent


class HostBootstrapError(RuntimeError):
    def __init__(self, code: str, message: str, *, step: str | None = None):
        super().__init__(message)
        self.code = code
        self.step = step


def current_platform() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def resolve_int_root() -> Path:
    explicit = os.environ.get("INT_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    for parent in REPO_ROOT.resolve().parents:
        if parent.name.lower() == "int":
            return parent.resolve()

    candidates = (Path("D:/int"), Path("/int")) if current_platform() == "windows" else (Path("/int"), Path("D:/int"))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def default_runtime_root() -> Path:
    explicit = os.environ.get("CODEX_RUNTIME_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (REPO_ROOT / ".runtime").resolve()


def default_cloud_root() -> Path:
    explicit = os.environ.get("CLOUD_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (resolve_int_root() / "cloud").resolve()


def default_brain_root() -> Path:
    explicit = os.environ.get("BRAIN_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    candidates = (Path("D:/int/2brain"), Path("/2brain")) if current_platform() == "windows" else (Path("/2brain"), Path("D:/int/2brain"))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_powershell() -> str:
    for candidate in ("pwsh", "powershell"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError("powershell runtime was not found in PATH")


def build_repo_step_command(
    linux_relative_path: str,
    windows_relative_path: str | None = None,
    *,
    binding_origin: str | None = None,
) -> list[str]:
    if current_platform() == "windows":
        relative_path = windows_relative_path or linux_relative_path.removesuffix(".sh") + ".ps1"
        command = [resolve_powershell(), "-File", str((REPO_ROOT / relative_path).resolve())]
        if binding_origin:
            command.extend(["-BindingOrigin", binding_origin])
        return command
    command = [str((REPO_ROOT / linux_relative_path).resolve())]
    if binding_origin:
        command.extend(["--binding-origin", binding_origin])
    return command


def render_config_template(template_text: str, *, codex_home: Path) -> str:
    tools_root = REPO_ROOT.resolve().as_posix()
    int_root = resolve_int_root().as_posix()
    cloud_root = default_cloud_root().as_posix()
    brain_root = default_brain_root().as_posix()
    home_root = Path.home().resolve().as_posix()

    replacements = {
        "__CODEX_HOME__": codex_home.resolve().as_posix(),
        "__TOOLS_ROOT__": tools_root,
        "__INT_ROOT__": int_root,
        "__HOME_ROOT__": home_root,
        "__CLOUD_ROOT__": cloud_root,
        "__BRAIN_ROOT__": brain_root,
        "__SHELL_SNAPSHOT__": "false" if current_platform() == "windows" else "true",
    }

    if current_platform() == "windows":
        replacements.update(
            {
                "__MCP_GITHUB_COMMAND__": "bash",
                "__MCP_GITHUB_ARGS__": f'args = ["{tools_root}/codex/bin/mcp-github-from-gh.sh"]',
                "__MCP_POSTGRES_COMMAND__": "bash",
                "__MCP_POSTGRES_ARGS__": f'args = ["{tools_root}/codex/bin/mcp-postgres-from-backend-env.sh"]',
                "__MCP_OBSIDIAN_COMMAND__": "bash",
                "__MCP_OBSIDIAN_ARGS__": f'args = ["{tools_root}/codex/bin/mcp-obsidian-memory.sh"]',
                "__MCP_BITRIX24_COMMAND__": "bash",
                "__MCP_BITRIX24_ARGS__": f'args = ["{tools_root}/codex/bin/mcp-bitrix24.sh"]',
            }
        )
    else:
        replacements.update(
            {
                "__MCP_GITHUB_COMMAND__": f"{tools_root}/codex/bin/mcp-github-from-gh.sh",
                "__MCP_GITHUB_ARGS__": "",
                "__MCP_POSTGRES_COMMAND__": f"{tools_root}/codex/bin/mcp-postgres-from-backend-env.sh",
                "__MCP_POSTGRES_ARGS__": "",
                "__MCP_OBSIDIAN_COMMAND__": f"{tools_root}/codex/bin/mcp-obsidian-memory.sh",
                "__MCP_OBSIDIAN_ARGS__": "",
                "__MCP_BITRIX24_COMMAND__": f"{tools_root}/codex/bin/mcp-bitrix24.sh",
                "__MCP_BITRIX24_ARGS__": "",
            }
        )

    rendered = template_text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap Codex host runtime layout")
    parser.add_argument("--binding-origin", default="codex/bin/codex_host_bootstrap.py")
    parser.add_argument("--skip-tools", action="store_true")
    parser.add_argument("--skip-openclaw", action="store_true")
    parser.add_argument("--skip-cloud", action="store_true")
    parser.add_argument("--skip-cron", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}")


def install_tools_neutral() -> None:
    if current_platform() == "windows":
        run_checked(build_repo_step_command("codex/tools/install_tools.sh", "codex/tools/install_tools.ps1"))
        return
    run_checked([str(ROOT_DIR / "tools" / "install_tools.sh")])


def ensure_supported_step(step: str) -> None:
    if current_platform() != "windows":
        return
    step_messages = {
        "openclaw": "OpenClaw install remains Linux-only because it provisions user systemd services.",
        "cloud": "Cloud access install remains Linux-only because it provisions user systemd mount units.",
        "cron": "Orphan cleaner cron remains Linux-only because it provisions crontab entries.",
    }
    if step in step_messages:
        raise HostBootstrapError("STEP_UNSUPPORTED_PLATFORM", step_messages[step], step=step)


def run_verify_engine() -> None:
    run_checked(build_repo_step_command("codex/bin/codex-host-verify", "codex/bin/codex-host-verify.ps1", binding_origin="codex/bin/codex-host-verify.ps1" if current_platform() == "windows" else "codex/bin/codex-host-verify"))


def main() -> int:
    args = build_parser().parse_args()
    assert_binding("codex-host-bootstrap", args.binding_origin)

    runtime_root = default_runtime_root()
    secrets_root = Path(os.environ.get("CODEX_SECRETS_ROOT", runtime_root / "codex-secrets")).expanduser()

    runtime_root.mkdir(parents=True, exist_ok=True)
    secrets_root.mkdir(parents=True, exist_ok=True)

    if not args.verify_only:
        if not args.skip_tools:
            install_tools_neutral()
        if not args.skip_openclaw:
            ensure_supported_step("openclaw")
            run_checked(build_repo_step_command("openclaw/ops/install.sh", "openclaw/ops/install.ps1"))
        if not args.skip_cloud:
            ensure_supported_step("cloud")
            run_checked([str(ROOT_DIR / "install_cloud_access.sh")])
        if not args.skip_cron:
            ensure_supported_step("cron")
            run_checked([str(ROOT_DIR / "install_orphan_cleaner_cron.sh")])

    run_verify_engine()

    print("codex host bootstrap: ok")
    print("- codex home: unchanged")
    print(f"- runtime root: {runtime_root}")
    print(f"- secrets root: {secrets_root}")
    print("")
    print("If auth.json is absent, run:")
    print("  codex login")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HostBootstrapError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error_code": exc.code,
                    "step": exc.step,
                    "platform": current_platform(),
                    "message": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
