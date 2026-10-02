"""Downloaded executable identities are checked before any native invocation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import check_realization_binaries as binaries


class NativeInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.revision = "a" * 40
        pins = {}
        for name in binaries.BINARIES:
            content = ("inert non-executed fixture: " + name).encode()
            (self.root / name).write_bytes(content)
            pins[name] = hashlib.sha256(content).hexdigest()
        self.manifest = {"revision": self.revision, "system": "Linux", "machine": "x86_64", "sha256": pins}
        self.write(self.manifest)

    def write(self, value):
        (self.root / "binaries.json").write_text(json.dumps(value), encoding="utf-8")

    def check(self):
        return binaries.verify(self.root, self.revision, "linux-x86_64")

    def test_complete_inputs_bind_revision_platform_and_both_bytes_without_execution(self):
        result = self.check()
        self.assertEqual(result["sha256"], self.manifest["sha256"])
        self.assertEqual(result["revision"], self.revision)
        self.assertEqual(result["status"], "pass")
        for name in binaries.BINARIES:
            self.assertEqual((self.root / name).stat().st_mode & 0o111, 0)

    def test_manifest_cannot_replace_runtime_or_omit_either_binary(self):
        changes = ({"revision": "b" * 40}, {"system": "Darwin"}, {"machine": "arm64"},
                   {"sha256": {}}, {"sha256": {"../other": "b" * 64}}, {"extra": "ignored"})
        for change in changes:
            with self.subTest(change=change):
                self.write({**self.manifest, **change})
                with self.assertRaises(ValueError):
                    self.check()

    def test_changed_missing_empty_or_symlinked_file_cannot_reuse_manifest(self):
        for name in binaries.BINARIES:
            path = self.root / name
            original = path.read_bytes()
            with self.subTest(name=name, mutation="changed"):
                path.write_bytes(original + b" changed")
                with self.assertRaisesRegex(ValueError, "bytes differ"):
                    self.check()
            with self.subTest(name=name, mutation="empty"):
                path.write_bytes(b"")
                with self.assertRaisesRegex(ValueError, "empty"):
                    self.check()
            path.unlink()
            with self.subTest(name=name, mutation="missing"), self.assertRaises(ValueError):
                self.check()
            target = self.root / (name + ".target")
            target.write_bytes(original)
            path.symlink_to(target)
            with self.subTest(name=name, mutation="symlink"), self.assertRaisesRegex(ValueError, "symlinked"):
                self.check()
            path.unlink()
            path.write_bytes(original)

    def test_duplicate_and_malformed_identity_fields_fail(self):
        path = self.root / "binaries.json"
        path.write_text('{"revision":"first",' + json.dumps(self.manifest)[1:])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.check()
        for pin in (True, "A" * 64, "0" * 63, None):
            value = deepcopy(self.manifest)
            value["sha256"]["biocompiler-core"] = pin
            self.write(value)
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, "identities"):
                self.check()
