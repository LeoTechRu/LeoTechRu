from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "plugin_pack.py"
SPEC = importlib.util.spec_from_file_location("plugin_pack", MODULE_PATH)
assert SPEC and SPEC.loader
plugin_pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin_pack)


class PluginPackTests(unittest.TestCase):
    def repository(self, root: Path) -> Path:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        source = root / "plugin"
        source.mkdir()
        return source

    def test_pack_uses_only_tracked_files_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.repository(root)
            (source / "SKILL.md").write_text("tracked\n", encoding="utf-8")
            (source / "ignored.txt").write_text("untracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "plugin/SKILL.md"], check=True)
            first = plugin_pack.manifest(source)
            second = plugin_pack.manifest(source)
            self.assertEqual(first, second)
            self.assertEqual([item["path"] for item in first["files"]], ["SKILL.md"])

            output = root / "output"
            manifest_path = root / "artifact-manifest.json"
            packed = plugin_pack.pack(source, output, manifest_path)
            self.assertEqual(packed, first)
            self.assertTrue((output / "SKILL.md").is_file())
            self.assertFalse((output / "ignored.txt").exists())
            self.assertEqual(json.loads(manifest_path.read_text()), first)

    def test_pack_rejects_tracked_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.repository(root)
            secret = root / "outside.txt"
            secret.write_text("secret\n", encoding="utf-8")
            (source / "link.txt").symlink_to(secret)
            subprocess.run(["git", "-C", str(root), "add", "plugin/link.txt"], check=True)
            with self.assertRaisesRegex(plugin_pack.PackError, "symlink"):
                plugin_pack.manifest(source)

    def test_pack_rejects_tracked_secret_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.repository(root)
            (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "-f", "plugin/.env"], check=True)
            with self.assertRaisesRegex(plugin_pack.PackError, "secret-shaped"):
                plugin_pack.manifest(source)

    def test_pack_refuses_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.repository(root)
            (source / "SKILL.md").write_text("tracked\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "plugin/SKILL.md"], check=True)
            output = root / "output"
            output.mkdir()
            with self.assertRaisesRegex(plugin_pack.PackError, "overwrite output"):
                plugin_pack.pack(source, output, root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
