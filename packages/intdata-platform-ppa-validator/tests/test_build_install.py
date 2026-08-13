from __future__ import annotations

from collections import Counter
import importlib.metadata as metadata
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
RESOURCE_ROOT = Path("intdata_platform_ppa_validator/platform")
RESOURCE_PATHS = (
    "schemas/platform-product-assertion.schema.json",
    "conformance/platform-product-assertion-v1.vectors.json",
    "conformance/platform-product-assertion-v1.digests.json",
    "conformance/bridge-oauth-registration-uri-v1.profile.json",
    "conformance/bridge-oauth-registration-uri-v1.vectors.json",
    "conformance/terminal-dependency-digests.json",
    "conformance/validate-terminal-dependencies.py",
)
WHEEL_FILE_NAMES = frozenset(
    {
        "intdata_platform_ppa_validator/__init__.py",
        "intdata_platform_ppa_validator/_integrity.py",
        "intdata_platform_ppa_validator/cli.py",
        "intdata_platform_ppa_validator/platform/conformance/bridge-oauth-registration-uri-v1.profile.json",
        "intdata_platform_ppa_validator/platform/conformance/bridge-oauth-registration-uri-v1.vectors.json",
        "intdata_platform_ppa_validator/platform/conformance/platform-product-assertion-v1.digests.json",
        "intdata_platform_ppa_validator/platform/conformance/platform-product-assertion-v1.vectors.json",
        "intdata_platform_ppa_validator/platform/conformance/terminal-dependency-digests.json",
        "intdata_platform_ppa_validator/platform/conformance/validate-terminal-dependencies.py",
        "intdata_platform_ppa_validator/platform/schemas/platform-product-assertion.schema.json",
        "intdata_platform_ppa_validator-0.1.0.dist-info/METADATA",
        "intdata_platform_ppa_validator-0.1.0.dist-info/RECORD",
        "intdata_platform_ppa_validator-0.1.0.dist-info/WHEEL",
        "intdata_platform_ppa_validator-0.1.0.dist-info/entry_points.txt",
        "intdata_platform_ppa_validator-0.1.0.dist-info/licenses/LICENSE",
        "intdata_platform_ppa_validator-0.1.0.dist-info/top_level.txt",
    }
)
SDIST_ROOT = "intdata_platform_ppa_validator-0.1.0"
SDIST_FILE_NAMES = frozenset(
    {
        "LICENSE",
        "MANIFEST.in",
        "PKG-INFO",
        "README.md",
        "pyproject.toml",
        "setup.cfg",
        "src/intdata_platform_ppa_validator/__init__.py",
        "src/intdata_platform_ppa_validator/_integrity.py",
        "src/intdata_platform_ppa_validator/cli.py",
        "src/intdata_platform_ppa_validator/platform/conformance/bridge-oauth-registration-uri-v1.profile.json",
        "src/intdata_platform_ppa_validator/platform/conformance/bridge-oauth-registration-uri-v1.vectors.json",
        "src/intdata_platform_ppa_validator/platform/conformance/platform-product-assertion-v1.digests.json",
        "src/intdata_platform_ppa_validator/platform/conformance/platform-product-assertion-v1.vectors.json",
        "src/intdata_platform_ppa_validator/platform/conformance/terminal-dependency-digests.json",
        "src/intdata_platform_ppa_validator/platform/conformance/validate-terminal-dependencies.py",
        "src/intdata_platform_ppa_validator/platform/schemas/platform-product-assertion.schema.json",
        "src/intdata_platform_ppa_validator.egg-info/PKG-INFO",
        "src/intdata_platform_ppa_validator.egg-info/SOURCES.txt",
        "src/intdata_platform_ppa_validator.egg-info/dependency_links.txt",
        "src/intdata_platform_ppa_validator.egg-info/entry_points.txt",
        "src/intdata_platform_ppa_validator.egg-info/requires.txt",
        "src/intdata_platform_ppa_validator.egg-info/top_level.txt",
        "tests/test_build_install.py",
        "tests/test_cli.py",
    }
)
SDIST_DIRECTORY_NAMES = frozenset(
    {
        "",
        "src",
        "src/intdata_platform_ppa_validator",
        "src/intdata_platform_ppa_validator/platform",
        "src/intdata_platform_ppa_validator/platform/conformance",
        "src/intdata_platform_ppa_validator/platform/schemas",
        "src/intdata_platform_ppa_validator.egg-info",
        "tests",
    }
)


class OfflineBuildInstallTests(unittest.TestCase):
    def assert_archive_members(self, actual: object, expected: object) -> None:
        self.assertEqual(Counter(actual), Counter(expected))

    def command(self, *args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=True)

    def wheelhouse(self, root: Path) -> Path:
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        for name in ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "rfc3987", "rpds-py", "typing_extensions", "setuptools", "wheel"):
            dist = metadata.distribution(name)
            stage = wheelhouse / f"stage-{name}"
            files = dist.files
            if files:
                for item in files:
                    source, target = Path(dist.locate_file(item)), stage / item
                    if source.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
            else:
                module = {"attrs": "attrs", "jsonschema-specifications": "jsonschema_specifications", "rpds-py": "rpds", "typing_extensions": "typing_extensions"}.get(name, name.replace("-", "_"))
                origin = Path(importlib.util.find_spec(module).origin)
                if name == "attrs":
                    shutil.copytree(origin.parent.parent / "attr", stage / "attr")
                    shutil.copytree(origin.parent, stage / "attrs")
                elif origin.name == "__init__.py":
                    shutil.copytree(origin.parent, stage / origin.parent.name)
                else:
                    stage.mkdir(); shutil.copy2(origin, stage / origin.name)
                info = stage / f"{name.replace('-', '_')}-{dist.version}.dist-info"
                info.mkdir(); metadata_file = Path(dist._path) / "METADATA"
                if not metadata_file.exists(): metadata_file = Path(dist._path) / "PKG-INFO"
                shutil.copy2(metadata_file, info / "METADATA")
                (info / "WHEEL").write_text("Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                (info / "RECORD").write_text("")
            self.command(sys.executable, "-m", "wheel", "pack", str(stage), "--dest-dir", str(wheelhouse), cwd=root)
            shutil.rmtree(stage)
        return wheelhouse

    def build(self, root: Path) -> tuple[Path, Path]:
        source, dist = root / "source", root / "dist"
        shutil.copytree(PACKAGE_ROOT, source); dist.mkdir()
        env = {**os.environ, "SOURCE_DATE_EPOCH": "0", "PPA_OUT": str(dist)}
        self.command(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(dist), ".", cwd=source, env=env)
        self.command(sys.executable, "-c", "from setuptools.build_meta import build_sdist; import os; build_sdist(os.environ['PPA_OUT'])", cwd=source, env=env)
        return next(dist.glob("*.whl")), next(dist.glob("*.tar.gz"))

    def assert_installed(self, root: Path, wheelhouse: Path, artifact: Path) -> None:
        venv, outside = root / artifact.name, root / f"outside-{artifact.suffix}"
        self.command(sys.executable, "-m", "venv", str(venv), cwd=root)
        self.assertIn("include-system-site-packages = false", (venv / "pyvenv.cfg").read_text())
        python = venv / "bin" / "python"; cli = venv / "bin" / "intdata-ppa-validate"
        if artifact.suffix == ".gz":
            self.command(str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), "setuptools==80.9.0", "wheel==0.45.1", cwd=root)
        self.command(str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), "--no-build-isolation", str(artifact), cwd=root)
        self.command(str(python), "-m", "pip", "check", cwd=root)
        outside.mkdir(); env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        first = self.command(str(cli), cwd=outside, env=env).stdout
        second = self.command(str(cli), cwd=outside, env=env).stdout
        self.assertEqual(first, second)
        location = Path(self.command(str(python), "-c", "import intdata_platform_ppa_validator as p; print(p.__file__)", cwd=outside, env=env).stdout.strip())
        self.assertTrue(location.is_relative_to(venv))
        installed_root = location.parent / "platform"
        for relative in RESOURCE_PATHS:
            target, original = installed_root / relative, (installed_root / relative).read_bytes()
            target.unlink(); failed = subprocess.run([str(cli)], cwd=outside, env=env, text=True, capture_output=True)
            self.assertEqual(2, failed.returncode); target.write_bytes(original)
            target.write_bytes(original + b"x"); failed = subprocess.run([str(cli)], cwd=outside, env=env, text=True, capture_output=True)
            self.assertEqual(2, failed.returncode); target.write_bytes(original)
        print(f"offline-install artifact={artifact.name} venv={venv} outside={outside} resources={len(RESOURCE_PATHS)} negatives={len(RESOURCE_PATHS) * 2}")

    def test_clean_wheel_and_sdist_install_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); wheelhouse = self.wheelhouse(root); wheel, sdist = self.build(root)
            with zipfile.ZipFile(wheel) as archive:
                self.assert_archive_members(
                    ((member.filename, stat.S_IFMT(member.external_attr >> 16)) for member in archive.infolist()),
                    ((name, stat.S_IFREG) for name in WHEEL_FILE_NAMES),
                )
            with tarfile.open(sdist) as archive:
                self.assert_archive_members(
                    ((member.name, member.type) for member in archive.getmembers()),
                    tuple((f"{SDIST_ROOT}/{name}", tarfile.REGTYPE) for name in SDIST_FILE_NAMES)
                    + tuple((SDIST_ROOT if not name else f"{SDIST_ROOT}/{name}", tarfile.DIRTYPE) for name in SDIST_DIRECTORY_NAMES),
                )
            self.assert_installed(root, wheelhouse, wheel); self.assert_installed(root, wheelhouse, sdist)

    def test_archive_member_assertion_rejects_duplicates(self) -> None:
        with self.assertRaises(AssertionError):
            self.assert_archive_members((("member", stat.S_IFREG), ("member", stat.S_IFREG)), (("member", stat.S_IFREG),))
