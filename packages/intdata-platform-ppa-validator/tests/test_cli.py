from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
PLATFORM_RELATIVE = Path("intdata_platform_ppa_validator/platform")
sys.path.insert(0, str(SOURCE_ROOT))
EXPECTED = {
    "checked": {
        "ppa_artifact_digests": 2,
        "ppa_vectors": 104,
        "terminal_artifact_digests": 4,
        "uri_vectors": 35,
    },
    "ok": True,
}


class OfflinePpaCliTests(unittest.TestCase):
    def run_cli(self, source_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(source_root)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as temporary:
            return subprocess.run(
                [sys.executable, "-m", "intdata_platform_ppa_validator.cli", *args],
                cwd=temporary,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )

    def test_cli_runs_offline_from_outside_the_repository(self) -> None:
        result = self.run_cli(SOURCE_ROOT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(EXPECTED, json.loads(result.stdout))

    def test_cli_success_output_matches_the_published_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            published = subprocess.run(
                [sys.executable, str(REPOSITORY_ROOT / "contracts/platform/v1/conformance/validate-terminal-dependencies.py")],
                cwd=temporary,
                check=False,
                capture_output=True,
                text=True,
            )
        wrapped = self.run_cli(SOURCE_ROOT)
        self.assertEqual(0, published.returncode, published.stderr)
        self.assertEqual(0, wrapped.returncode, wrapped.stderr)
        self.assertEqual(published.stdout, wrapped.stdout)

    def test_invalid_invocation_has_a_deterministic_compact_error(self) -> None:
        result = self.run_cli(SOURCE_ROOT, "unexpected")
        self.assertEqual(64, result.returncode)
        self.assertEqual('{"code":"invalid_invocation","error":"expected_no_arguments"}\n', result.stdout)

    def test_each_embedded_resource_rejects_missing_or_tampered_bytes(self) -> None:
        from intdata_platform_ppa_validator._integrity import RAW_SHA256

        for relative_path in RAW_SHA256:
            for action in ("missing", "tampered"):
                with self.subTest(resource=relative_path, action=action), tempfile.TemporaryDirectory() as temporary:
                    copied_source = Path(temporary) / "site"
                    shutil.copytree(SOURCE_ROOT, copied_source)
                    target = copied_source / PLATFORM_RELATIVE / relative_path
                    if action == "missing":
                        target.unlink()
                    else:
                        target.write_bytes(target.read_bytes() + b"x")
                    result = self.run_cli(copied_source)
                    self.assertEqual(2, result.returncode)
                    self.assertEqual("integrity_failed", json.loads(result.stdout)["code"])

    def test_cli_ignores_a_timestamp_valid_poisoned_validator_pyc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_source = Path(temporary) / "site"
            shutil.copytree(SOURCE_ROOT, copied_source)
            validator = copied_source / PLATFORM_RELATIVE / "conformance/validate-terminal-dependencies.py"
            authentic = validator.read_bytes()
            needle = b'"ppa_vectors": validate_ppa(),'
            replacement = b'"ppa_vectors": 0' + b" " * (len(needle) - len(b'"ppa_vectors": 0') - 1) + b","
            self.assertIn(needle, authentic)
            malicious = authentic.replace(needle, replacement)
            self.assertEqual(len(authentic), len(malicious))
            timestamp = 1_700_000_000
            validator.write_bytes(malicious)
            os.utime(validator, (timestamp, timestamp))
            py_compile.compile(str(validator), doraise=True)
            cache = Path(importlib.util.cache_from_source(str(validator)))
            self.assertTrue(cache.exists())
            validator.write_bytes(authentic)
            os.utime(validator, (timestamp, timestamp))

            specification = importlib.util.spec_from_file_location("poisoned_validator", validator)
            self.assertIsNotNone(specification)
            self.assertIsNotNone(specification.loader)
            poisoned = importlib.util.module_from_spec(specification)
            specification.loader.exec_module(poisoned)
            self.assertEqual(0, poisoned.run()["ppa_vectors"])

            result = self.run_cli(copied_source)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(EXPECTED, json.loads(result.stdout))

    def test_aggregate_semantics_reject_an_internal_manifest_mismatch(self) -> None:
        from intdata_platform_ppa_validator import _integrity

        manifest = _integrity._load_manifest("conformance/platform-product-assertion-v1.digests.json")
        manifest["aggregate_sha256"] = "0" * 64
        with self.assertRaisesRegex(_integrity.IntegrityError, "manifest-aggregate:ppa"):
            _integrity._verify_manifest(
                manifest,
                (
                    "ppa",
                    (
                        "conformance/platform-product-assertion-v1.vectors.json",
                        "schemas/platform-product-assertion.schema.json",
                    ),
                    _integrity.PPA_AGGREGATE_SHA256,
                ),
            )


if __name__ == "__main__":
    unittest.main()
