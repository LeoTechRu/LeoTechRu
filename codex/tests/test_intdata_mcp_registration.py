from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "intdata_mcp_registration.py"
SPEC = importlib.util.spec_from_file_location("intdata_mcp_registration", MODULE_PATH)
assert SPEC and SPEC.loader
registration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registration)


class FakeCodex:
    def __init__(self, rows=None):
        self.rows = {row["name"]: row for row in (rows or [])}
        self.calls: list[list[str]] = []
        self.fail_once: list[str] = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(argv)
        if argv[0] == str(Path(__import__("sys").executable).resolve()) and argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, "Python test", "")
        if argv[1:4] == ["mcp", "list", "--json"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(list(self.rows.values())), "")
        if argv[1:3] == ["mcp", "remove"]:
            if "remove" in self.fail_once:
                self.fail_once.remove("remove")
                return subprocess.CompletedProcess(argv, 1, "", "failure")
            self.rows.pop(argv[3], None)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:3] == ["mcp", "add"]:
            if "add" in self.fail_once:
                self.fail_once.remove("add")
                return subprocess.CompletedProcess(argv, 1, "", "failure")
            name = argv[3]
            separator = argv.index("--")
            command = argv[separator + 1]
            args = argv[separator + 2 :]
            self.rows[name] = {"name": name, "enabled": True, "startup_timeout_sec": None, "tool_timeout_sec": None, "transport": {"type": "stdio", "command": command, "args": args, "env": None, "env_vars": [], "cwd": None}}
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)


def row(name: str, command: str, args: list[str], **extra):
    transport = {"type": "stdio", "command": command, "args": args, "env": None, "env_vars": [], "cwd": None}
    transport.update(extra)
    return {"name": name, "enabled": True, "startup_timeout_sec": None, "tool_timeout_sec": None, "transport": transport}


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.python = Path(__import__("sys").executable).resolve()
        self.wanted = registration.desired_rows(self.python)
        self.real_smoke = registration.smoke
        registration.smoke = lambda _python, _runner: registration.EXPECTED_COUNTS.copy()

    def tearDown(self):
        registration.smoke = self.real_smoke

    def exact_rows(self):
        return [row(name, wanted["command"], wanted["args"]) for name, wanted in self.wanted.items()]

    def test_classifies_exact_missing_and_drift(self):
        current = {name: value.copy() for name, value in self.wanted.items()}
        current.pop("dba")
        current["intdata-runtime"]["args"] = ["wrong"]
        self.assertEqual(registration.classify(current, self.wanted), {"intdata-control": "exact", "intdata-runtime": "drift", "dba": "missing"})

    def test_check_never_mutates(self):
        fake = FakeCodex([])
        rc = registration.main(["--python", str(self.python)], runner=fake)
        self.assertEqual(rc, 2)
        self.assertFalse(any(call[1:3] in (["mcp", "add"], ["mcp", "remove"]) for call in fake.calls))

    def test_drift_requires_replace(self):
        fake = FakeCodex([row("intdata-control", "/wrong", [])])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)
        self.assertFalse(any(call[1:3] == ["mcp", "remove"] for call in fake.calls))

    def test_apply_backs_up_and_registers_all_profiles(self):
        fake = FakeCodex([])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--backup-dir", directory], runner=fake)
            backups = list(Path(directory).glob("*.json"))
            if __import__("os").name != "nt":
                self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(rc, 0)
        self.assertEqual(len(backups), 1)
        self.assertEqual(registration.classify(registration.inventory("codex", fake), self.wanted), {name: "exact" for name in registration.PROFILES})

    def test_non_executable_python_is_rejected_before_inventory(self):
        fake = FakeCodex([])
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "python"
            candidate.write_text("not python", encoding="utf-8")
            candidate.chmod(0o600)
            rc = registration.main(["--python", str(candidate)], runner=fake)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.calls, [])

    def test_secret_bearing_drift_is_refused(self):
        fake = FakeCodex([row("dba", "/wrong", [], env={"TOKEN": "secret"})])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
            self.assertEqual(list(Path(directory).glob("*.json")), [])
        self.assertEqual(rc, 1)

    def test_secret_bearing_argv_forms_are_refused(self):
        for args in (["--access-token", "value"], ["--api-key=value"], ["password:secret"]):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                fake = FakeCodex([row("dba", "/wrong", list(args))])
                rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
                self.assertEqual(rc, 1)
                self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_non_stdio_drift_is_refused_before_mutation(self):
        fake = FakeCodex([{"name": "dba", "enabled": True, "startup_timeout_sec": None, "tool_timeout_sec": None, "transport": {"type": "streamable_http", "url": "https://example.invalid/mcp"}}])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)
        self.assertFalse(any(call[1:3] == ["mcp", "remove"] for call in fake.calls))

    def test_plugin_cache_origin_is_refused(self):
        fake = FakeCodex([row("dba", "/usr/bin/python3", ["/home/agents/.codex/plugins/cache/intprobe/runtime.py"])])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)

    def test_rollback_failure_restores_pre_rollback_registry(self):
        original = self.exact_rows()
        fake = FakeCodex(original)
        fake.fail_once = ["remove"]
        captured = {"schema": 1, "profiles": {name: None for name in registration.PROFILES}}
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "target.json"
            backup.write_text(json.dumps(captured), encoding="utf-8")
            rc = registration.main(["--python", str(self.python), "--rollback", str(backup), "--apply", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)
        self.assertEqual(registration.inventory("codex", fake), {row["name"]: registration.normalize(row) for row in original})

    def test_disabled_registration_is_drift_and_refused(self):
        existing = self.exact_rows()[0]
        existing["enabled"] = False
        fake = FakeCodex([existing])
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)

    def test_add_failure_restores_previous_registry(self):
        original = [row("intdata-control", "/old/python", ["old.py"])]
        fake = FakeCodex(original)
        fake.fail_once = ["add"]
        with tempfile.TemporaryDirectory() as directory:
            rc = registration.main(["--python", str(self.python), "--apply", "--replace", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 1)
        self.assertEqual(registration.inventory("codex", fake), {"intdata-control": registration.normalize(original[0])})

    def test_windows_wrapper_has_override_bundled_and_path_discovery(self):
        wrapper = (MODULE_PATH.parent / "register-intdata-mcp.ps1").read_text(encoding="utf-8")
        self.assertIn("INTDATA_MCP_PYTHON", wrapper)
        self.assertIn("codex-primary-runtime", wrapper)
        self.assertIn("Get-Command python.exe", wrapper)
        self.assertIn("IsPathRooted", wrapper)

    def test_rollback_restores_captured_rows(self):
        fake = FakeCodex(self.exact_rows())
        captured = {"schema": 1, "profiles": {name: None for name in registration.PROFILES}}
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.json"
            backup.write_text(json.dumps(captured), encoding="utf-8")
            rc = registration.main(["--python", str(self.python), "--rollback", str(backup), "--apply", "--backup-dir", directory], runner=fake)
        self.assertEqual(rc, 0)
        self.assertEqual(fake.rows, {})


if __name__ == "__main__":
    unittest.main()
