from __future__ import annotations

import shlex
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
VALIDATOR = "contracts/platform/v1/conformance/validate-terminal-dependencies.py"
INSTALL_COMMAND = (
    'python -m pip install --disable-pip-version-check '
    '"jsonschema==4.20.0" "rfc3987==1.3.8" "PyYAML==6.0.2"'
)
CONFORMANCE_SCRIPT = f'''set -euo pipefail
validator="{VALIDATOR}"
git ls-files --error-unmatch "$validator" >/dev/null
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
python "$validator" > "$tmpdir/first.txt"
python "$validator" > "$tmpdir/second.txt"
cmp -- "$tmpdir/first.txt" "$tmpdir/second.txt"
cat "$tmpdir/first.txt"
'''


class CiWorkflowTests(unittest.TestCase):
    def assert_no_legacy_mcp_strings(self, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                self.assert_no_legacy_mcp_strings(key)
                self.assert_no_legacy_mcp_strings(item)
        elif isinstance(value, list):
            for item in value:
                self.assert_no_legacy_mcp_strings(item)
        elif isinstance(value, str):
            for legacy in ("tools-tests", "bitrix24-mcp", "getcourse-mcp"):
                self.assertNotIn(legacy, value)

    def assert_platform_contract_workflow(self, workflow_path: Path) -> None:
        parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, Mapping)
        jobs = parsed.get("jobs")
        self.assertIsInstance(jobs, Mapping)
        self.assertNotIn("tools-tests", jobs)
        self.assertIn("platform-contracts", jobs)
        self.assert_no_legacy_mcp_strings(parsed)

        job = jobs["platform-contracts"]
        self.assertIsInstance(job, Mapping)
        self.assertEqual(job.get("name"), "Platform contract conformance")
        self.assertEqual(job.get("runs-on"), "ubuntu-latest")
        self.assertEqual(
            job.get("steps"),
            [
                {"uses": "actions/checkout@v4"},
                {
                    "uses": "actions/setup-python@v5",
                    "with": {"python-version": "3.11", "cache": "pip"},
                },
                {"name": "Install conformance dependencies", "run": INSTALL_COMMAND},
                {
                    "name": "Check workflow regression",
                    "run": "python -m unittest codex.tests.test_ci_workflow -v",
                },
                {
                    "name": "Check deterministic platform conformance",
                    "shell": "bash",
                    "run": CONFORMANCE_SCRIPT,
                },
            ],
        )
        install = job["steps"][2]["run"]
        self.assertEqual(shlex.split(install), shlex.split(INSTALL_COMMAND))

    def test_platform_contract_conformance_replaces_packaged_mcp_matrix(self) -> None:
        self.assert_platform_contract_workflow(WORKFLOW)

    def test_structural_validation_rejects_commented_commands(self) -> None:
        fixture = '''jobs:
  platform-contracts:
    # runs-on: ubuntu-latest
    # python-version: "3.11"
    # python -m pip install --disable-pip-version-check "jsonschema==4.20.0" "rfc3987==1.3.8" "PyYAML==6.0.2"
    # git ls-files --error-unmatch "$validator" >/dev/null
    # python "$validator" > "$tmpdir/first.txt"
    # python "$validator" > "$tmpdir/second.txt"
    # cmp -- "$tmpdir/first.txt" "$tmpdir/second.txt"
    # cat "$tmpdir/first.txt"
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ci.yml"
            path.write_text(fixture, encoding="utf-8")
            with self.assertRaises(AssertionError):
                self.assert_platform_contract_workflow(path)


if __name__ == "__main__":
    unittest.main()