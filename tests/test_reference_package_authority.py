"""Whole original package witnesses; these controls never execute native code."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reference_package_authority", ROOT / "tools/capture_reference_packages.py")
authority = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(authority)


class ReferencePackageAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = authority.capture()
        cls.frozen = json.loads((ROOT / "tests/conformance/reference-packages-314.json").read_bytes())
        cls.rows = {row["id"]: row for row in cls.current["cases"]}

    def test_complete_original_capture(self):
        self.assertEqual(self.current, self.frozen)
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(len(self.current["cases"]), 8)
        self.assertEqual((ROOT / "tests/conformance/reference-packages-311.json").read_bytes(), (ROOT / "tests/conformance/reference-packages-314.json").read_bytes())
        for path, pin in self.current["sources"].items():
            self.assertEqual(hashlib.sha256((authority.ROOT / path).read_bytes()).hexdigest(), pin)

    def test_full_archive_manifest_and_members(self):
        for row in self.rows.values():
            if row["outcome"]["status"] != "return":
                continue
            value = row["outcome"]["value"]
            data = bytes.fromhex(value["data"])
            manifest, files, metadata = authority.read_archive(data)
            self.assertEqual(hashlib.sha256(data).hexdigest(), value["archive_sha256"])
            self.assertEqual(manifest.to_dict(), value["manifest"])
            self.assertEqual(manifest.build_fingerprint, value["build_fingerprint"])
            self.assertEqual([[key, item.hex()] for key, item in files.items()], value["files"])
            self.assertEqual(len(manifest.accepted_stages), 3)
            self.assertEqual(len(manifest.toolchain), 13)
            self.assertEqual(None if metadata is None else metadata.to_dict(), row["input"]["run_metadata"])

    def test_fresh_callpoints_and_early_failure(self):
        complete = ["load_reference_inputs", "collect_reference_files", "run_molecular_pipeline",
            "export_reference_sequence", "check_composition", "check_construct", "_tools"]
        for key, row in self.rows.items():
            self.assertEqual(row["calls"], complete if key != "DNA:unsupported-layout" else complete[:3])
        self.assertEqual(self.rows["DNA:unsupported-layout"]["outcome"], {"status": "raise",
            "module": "biocompiler.compiler.pipeline", "type": "PipelineError",
            "message": "Artifact 'components' has not passed its acceptance checks."})

    def test_current_metadata_changes_complete_package_identity(self):
        for baseline, changed in (("DNA:default", "DNA:current-sdk"), ("RNA:default", "RNA:current-tool")):
            before, after = (self.rows[key]["outcome"]["value"] for key in (baseline, changed))
            self.assertEqual(before["request"], after["request"])
            self.assertEqual(before["files"], after["files"])
            self.assertNotEqual(before["build_fingerprint"], after["build_fingerprint"])
            self.assertNotEqual(before["archive_sha256"], after["archive_sha256"])

    def test_width_and_run_metadata_profiles(self):
        plain = self.rows["DNA:default"]["outcome"]["value"]
        run = self.rows["DNA:run-metadata"]["outcome"]["value"]
        self.assertEqual(plain["manifest"], run["manifest"])
        self.assertNotEqual(plain["archive_sha256"], run["archive_sha256"])
        for key, width in (("DNA:width1", 1), ("RNA:width10000", 10000)):
            files = dict(self.rows[key]["outcome"]["value"]["files"])
            lines = bytes.fromhex(files["sequence.fasta"]).splitlines()
            self.assertTrue(all(0 < len(line) <= width for line in lines[1:]))


if __name__ == "__main__":
    unittest.main()
