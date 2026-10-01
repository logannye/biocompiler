"""Release assets must match their pinned source and installed byte inventory."""

import hashlib
from importlib import resources
import json
from pathlib import Path
import re
import unittest


class StudioAssetTests(unittest.TestCase):
    def test_installed_javascript_inventory_matches_release_manifest(self):
        static = resources.files("biocompiler.studio").joinpath("static")
        manifest = json.loads(static.joinpath("studio-assets.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "biocompiler.studio_assets.v0.1")
        self.assertEqual(set(manifest["assets"]), {"app.js", "construction.js", "transport.js"})
        for name, expected in manifest["assets"].items():
            with self.subTest(asset=name):
                content = static.joinpath(name).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), expected)
                self.assertTrue(content.startswith(b"// Generated from studio/src;"))
                imports = re.findall(r'from [\'"]([^\'"]+)[\'"]', content.decode())
                self.assertTrue(all(value == "./transport.js" for value in imports))
        for name, script in (("index.html", "/app.js"), ("construction.html", "/construction.js")):
            self.assertIn(f'<script src="{script}" type="module"></script>', static.joinpath(name).read_text())

    def test_source_config_and_lock_changes_cannot_hide_behind_old_assets(self):
        root = Path(__file__).resolve().parents[1] / "studio"
        static = resources.files("biocompiler.studio").joinpath("static")
        manifest = json.loads(static.joinpath("studio-assets.json").read_text(encoding="utf-8"))
        expected = {"package.json", "package-lock.json", "tsconfig.json", "tools/build.mjs"}
        expected.update(f"src/{path.name}" for path in (root / "src").glob("*.ts"))
        self.assertEqual(set(manifest["inputs"]), expected)
        self.assertEqual(manifest["typescript"], json.loads((root / "package.json").read_text())["devDependencies"]["typescript"])
        for name, digest in manifest["inputs"].items():
            with self.subTest(source=name):
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
