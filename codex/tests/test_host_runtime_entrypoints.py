#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_ROOT = REPO_ROOT / "codex" / "bin"
if str(ROUTER_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROUTER_ROOT))

import codex_host_bootstrap as host_bootstrap  # noqa: E402
import codex_host_verify as host_verify  # noqa: E402
import codex_recovery_bundle as recovery_bundle  # noqa: E402


class HostRuntimeEntrypointsTest(unittest.TestCase):
    def test_windows_dispatch_uses_powershell_adapters(self) -> None:
        original = host_bootstrap.current_platform
        original_ps = host_bootstrap.resolve_powershell
        host_bootstrap.current_platform = lambda: "windows"
        host_bootstrap.resolve_powershell = lambda: "pwsh"
        self.addCleanup(setattr, host_bootstrap, "current_platform", original)
        self.addCleanup(setattr, host_bootstrap, "resolve_powershell", original_ps)

        install_command = host_bootstrap.build_repo_step_command(
            "codex/tools/install_tools.sh",
            "codex/tools/install_tools.ps1",
            binding_origin="ignored",
        )

        self.assertEqual(install_command[:2], ["pwsh", "-File"])
        self.assertTrue(install_command[2].replace("\\", "/").endswith("codex/tools/install_tools.ps1"))
        self.assertEqual(install_command[3:], ["-BindingOrigin", "ignored"])

    def test_windows_openclaw_adapter_is_machine_readable(self) -> None:
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh:
            self.skipTest("PowerShell runtime is required")

        completed = subprocess.run(
            [pwsh, "-File", str(REPO_ROOT / "openclaw" / "ops" / "install.ps1")],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("UNSUPPORTED_PLATFORM", completed.stderr)
        self.assertIn("linux-only", completed.stderr)

    def test_runtime_root_defaults_are_platform_aware(self) -> None:
        with tempfile.TemporaryDirectory(prefix="host_runtime_") as temp_root_raw:
            temp_root = Path(temp_root_raw)
            tools_root = temp_root / "sandbox" / "int" / "tools"
            codex_root = tools_root / "codex"
            codex_root.mkdir(parents=True, exist_ok=True)

            original_repo_root = host_bootstrap.REPO_ROOT
            original_root_dir = host_bootstrap.ROOT_DIR
            original_verify_repo_root = host_verify.REPO_ROOT
            original_recovery_file = recovery_bundle.__file__
            previous_env = {key: os.environ.get(key) for key in ("INT_ROOT", "CODEX_RUNTIME_ROOT", "CLOUD_ROOT", "BRAIN_ROOT")}

            try:
                host_bootstrap.REPO_ROOT = tools_root
                host_bootstrap.ROOT_DIR = codex_root
                host_verify.REPO_ROOT = tools_root
                recovery_bundle.__file__ = str(codex_root / "bin" / "codex_recovery_bundle.py")
                os.environ["INT_ROOT"] = str(temp_root / "sandbox" / "int")
                os.environ.pop("CODEX_RUNTIME_ROOT", None)
                os.environ.pop("CLOUD_ROOT", None)
                self.assertEqual(host_bootstrap.default_runtime_root(), temp_root / "sandbox" / "int" / "tools" / ".runtime")
                self.assertEqual(host_verify.default_runtime_root(), temp_root / "sandbox" / "int" / "tools" / ".runtime")
                self.assertEqual(recovery_bundle.default_runtime_root(), temp_root / "sandbox" / "int" / "tools" / ".runtime")
            finally:
                host_bootstrap.REPO_ROOT = original_repo_root
                host_bootstrap.ROOT_DIR = original_root_dir
                host_verify.REPO_ROOT = original_verify_repo_root
                recovery_bundle.__file__ = original_recovery_file
                for key, value in previous_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_host_bootstrap_does_not_write_codex_home(self) -> None:
        with tempfile.TemporaryDirectory(prefix="host_bootstrap_") as temp_root_raw:
            temp_root = Path(temp_root_raw)
            codex_home = temp_root / "codex-home"
            runtime_root = temp_root / "runtime"
            previous_env = {key: os.environ.get(key) for key in ("CODEX_HOME", "CODEX_RUNTIME_ROOT")}
            previous_argv = sys.argv[:]
            original_run_checked = host_bootstrap.run_checked

            try:
                os.environ["CODEX_HOME"] = str(codex_home)
                os.environ["CODEX_RUNTIME_ROOT"] = str(runtime_root)
                sys.argv = ["codex_host_bootstrap.py", "--verify-only"]
                host_bootstrap.run_checked = lambda *args, **kwargs: None

                self.assertEqual(host_bootstrap.main(), 0)
                self.assertFalse((codex_home / "config.toml").exists())
                self.assertFalse((codex_home / "AGENTS.md").exists())
                self.assertTrue((runtime_root / "codex-secrets").is_dir())
            finally:
                host_bootstrap.run_checked = original_run_checked
                sys.argv = previous_argv
                for key, value in previous_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_codex_home_sync_entrypoints_are_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "codex" / "sync_runtime_from_repo.sh").exists())
        self.assertFalse((REPO_ROOT / "codex" / "sync_runtime_from_repo.ps1").exists())
        self.assertFalse((REPO_ROOT / "codex" / "detach_home_git.sh").exists())
