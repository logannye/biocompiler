"""Pure original file-source controls; native execution remains hosted-only."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reference_input_authority", ROOT / "tools/capture_reference_inputs.py")
authority = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(authority)


class ReferenceInputAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = authority.capture()
        cls.frozen = json.loads((ROOT / "tests/conformance/reference-inputs-314.json").read_bytes())
        cls.rows = {row["id"]: row for row in cls.current["cases"]}

    def test_complete_original_and_runtime_equality(self):
        self.assertEqual(self.current, self.frozen)
        self.assertEqual(len(self.rows), 17)
        self.assertEqual(len(self.current["cases"]), 17)
        self.assertEqual((ROOT / "tests/conformance/reference-inputs-314.json").read_bytes(), (ROOT / "tests/conformance/reference-inputs-311.json").read_bytes())
        self.assertEqual({row["operation"] for row in self.rows.values()}, {"load", "collect", "prepare", "manifest-bytes"})

    def test_source_and_raw_snapshot_hashes(self):
        for path, pin in self.current["sources"].items():
            self.assertEqual(hashlib.sha256((authority.ROOT / path).read_bytes()).hexdigest(), pin)
        value = self.rows["load:original"]["outcome"]["value"]
        files = dict(value["files"])
        manifest = authority.ReferenceManifest.from_dict(value["manifest"])
        self.assertEqual(manifest.fingerprint, authority.source.MANIFEST_PIN.content_fingerprint)
        self.assertEqual(bytes.fromhex(files["manifest.json"]), manifest.to_json().encode())
        for name, pin in authority.source._retained_paths(manifest).items():
            self.assertEqual(hashlib.sha256(bytes.fromhex(files[name])).hexdigest(), pin)

    def test_equal_snapshot_spellings_and_excluded_unrelated_file(self):
        outcome = self.rows["load:original"]["outcome"]
        for label in ("reversed-input", "irrelevant-file", "compact-manifest", "reordered-manifest"):
            self.assertEqual(self.rows["load:" + label]["outcome"], outcome)
        self.assertNotIn("unused.txt", dict(outcome["value"]["files"]))
        self.assertEqual(self.rows["collect:original"]["outcome"]["value"], outcome["value"]["files"])

    def test_rechecked_bytes_stale_manifest_and_construct_authorities(self):
        for label in ("source-excerpts.html", "independent-audit.json"):
            self.assertEqual(self.rows["load:altered:" + label]["outcome"]["message"], "Retained reference hash mismatch: " + label + ".")
        self.assertEqual(self.rows["collect:stale-source"]["outcome"]["message"], "Supplied manifest differs from the current pinned offline reference snapshot.")
        for alphabet in ("DNA", "RNA"):
            value = self.rows["prepare:" + alphabet]["outcome"]["value"]
            self.assertEqual(value["request"]["composition"]["target"]["payload_format"], alphabet)
            self.assertEqual(value["registry"]["id"], "reviewed-cds")
            self.assertEqual(value["request"]["composition"]["requirement_ids"], ["preserve_selected_cds"])

    def test_reference_ascii_spelling_is_distinct_from_package_utf8(self):
        accent = bytes.fromhex(self.rows["manifest-bytes:accent-astral"]["outcome"]["value"])
        separators = bytes.fromhex(self.rows["manifest-bytes:separators"]["outcome"]["value"])
        self.assertTrue(accent.isascii() and separators.isascii())
        self.assertIn(b"\\u00e9 \\ud83e\\uddec", accent)
        self.assertIn(b"line\\u2028paragraph\\u2029", separators)


if __name__ == "__main__":
    unittest.main()
