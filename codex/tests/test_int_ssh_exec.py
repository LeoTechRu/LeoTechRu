#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "int_ssh_exec.py"
spec = importlib.util.spec_from_file_location("int_ssh_exec", MODULE_PATH)
ssh_exec = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ssh_exec)

MCP_PATH = Path(__file__).resolve().parents[1] / "bin" / "mcp-intdata-cli.py"
mcp_spec = importlib.util.spec_from_file_location("mcp_intdata_cli_ssh_test", MCP_PATH)
mcp_cli = importlib.util.module_from_spec(mcp_spec)
assert mcp_spec.loader
mcp_spec.loader.exec_module(mcp_cli)


class IntSshExecTest(unittest.TestCase):
    def test_destination_rejects_options_and_shell_syntax(self):
        for value in ("", "-oProxyCommand=x", "host;id", "user@host name", "user@@host"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ssh_exec.validate_destination(value)

    def test_direct_fallback_rejects_untrusted_bare_alias(self):
        with self.assertRaises(ValueError):
            ssh_exec.validate_direct_destination("work-alias")
        self.assertEqual(ssh_exec.validate_direct_destination("agents@vds.intdata.pro"), "agents@vds.intdata.pro")

    def test_remote_command_quotes_argv_and_cwd(self):
        command = ssh_exec.build_remote_command(["printf", "%s", "a; $(id)"], "/srv/space dir")
        self.assertEqual(command, "cd -- '/srv/space dir' && exec printf %s 'a; $(id)'")

    def test_build_uses_native_ssh_without_local_shell(self):
        route = {"ssh_args": ["safe-alias"], "destination": "safe-alias", "transport": "public", "fallback_used": True, "logical_host": "dev-agents"}
        with mock.patch.object(ssh_exec, "resolve_target", return_value=route), mock.patch.object(ssh_exec, "resolve_ssh_executable", return_value="/usr/bin/ssh"):
            command, _ = ssh_exec.build_ssh_command("dev-agents", ["uname", "-a"])
        self.assertIsInstance(command, list)
        self.assertEqual(command[0], "/usr/bin/ssh")
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("ForwardAgent=no", command)
        self.assertIn("ClearAllForwardings=yes", command)
        self.assertIn("PermitLocalCommand=no", command)
        self.assertIn("ProxyCommand=none", command)
        self.assertNotIn("shell=True", command)
        self.assertEqual(command[-1], "exec uname -a")

    def test_direct_fallback_isolates_user_config_and_agent(self):
        route = {"ssh_args": ["agents@vds.intdata.pro"], "destination": "agents@vds.intdata.pro", "transport": "legacy", "fallback_used": False, "logical_host": None}
        with mock.patch.object(ssh_exec, "resolve_target", return_value=route), mock.patch.object(ssh_exec, "resolve_ssh_executable", return_value="ssh"):
            command, _ = ssh_exec.build_ssh_command("agents@vds.intdata.pro", ["true"])
        self.assertIn("-F", command)
        self.assertIn("none", command)
        self.assertIn("IdentityAgent=none", command)
        self.assertIn("ForwardAgent=no", command)
        self.assertIn("ProxyCommand=none", command)

    def test_run_bounded_discards_excess_without_unbounded_capture(self):
        class Stream:
            def __init__(self, chunks):
                self.chunks = list(chunks)
            def read(self, _size):
                return self.chunks.pop(0) if self.chunks else b""

        process = mock.Mock()
        process.stdout = Stream([b"x" * 4096])
        process.stderr = Stream([b"y" * 4096])
        process.wait.return_value = 0
        with mock.patch.object(ssh_exec.subprocess, "Popen", return_value=process) as popen:
            rc, stdout, stderr, truncated, timed_out = ssh_exec._run_bounded(["ssh"], timeout=3, output_limit=1024)
        self.assertEqual(rc, 0)
        self.assertEqual(len(stdout), 1024)
        self.assertEqual(len(stderr), 1024)
        self.assertTrue(truncated)
        self.assertFalse(timed_out)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_arbitrary_execution_always_requires_confirmation_and_issue_before_spawn(self):
        args = {"host": "dev-agents", "argv": ["rm", "-rf", "/tmp/example"]}
        with mock.patch.object(mcp_cli, "_run") as run:
            with self.assertRaises(PermissionError):
                mcp_cli._call_runtime("ssh_execute", args)
        run.assert_not_called()

        args["confirm_mutation"] = True
        with mock.patch.object(mcp_cli, "_run") as run:
            with self.assertRaises(PermissionError):
                mcp_cli._call_runtime("ssh_execute", args)
        run.assert_not_called()

    def test_confirmed_execution_builds_structured_engine_argv(self):
        args = {"host": "dev-agents", "argv": ["uname", "-a"], "confirm_mutation": True, "issue_context": "#816", "timeout_sec": 7}
        with mock.patch.object(mcp_cli, "_run", return_value={"ok": True}) as run:
            payload = mcp_cli._call_runtime("ssh_execute", args)
        self.assertTrue(payload["ok"])
        command = run.call_args.args[0]
        self.assertIn("int_ssh_exec.py", command[1])
        self.assertEqual(command[-3:], ["--", "uname", "-a"])

    def test_execute_timeout_is_fail_closed(self):
        route = {"ssh_args": ["safe-alias"], "destination": "safe-alias", "transport": "public", "fallback_used": False, "logical_host": "dev-agents"}
        with mock.patch.object(ssh_exec, "resolve_target", return_value=route), mock.patch.object(ssh_exec, "resolve_ssh_executable", return_value="ssh"), mock.patch.object(ssh_exec, "_run_bounded", return_value=(124, b"", b"", False, True)):
            payload = ssh_exec.execute("dev-agents", ["sleep", "2"], timeout_sec=1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["timed_out"])
        self.assertEqual(payload["returncode"], 124)



if __name__ == "__main__":
    unittest.main()
