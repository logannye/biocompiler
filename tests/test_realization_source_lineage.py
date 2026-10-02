"""Historical corpus pins cannot hide unrelated edits during optional routing."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import realization_source_lineage as lineage


class RealizationSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.witness = lineage.load_witness()
        self.path = "src/biocompiler/compiler/components.py"
        self.entry = self.witness[self.path]
        self.raw = (lineage.ROOT / self.path).read_bytes()

    def verify_changed(self, raw):
        # Even updating the reviewed current byte pin cannot disguise a change
        # to historical semantics. Production load_witness separately pins it.
        entry = copy.deepcopy(self.entry)
        entry["routed_sha256"] = lineage.sha256(raw)
        return lineage.verify_route_extension(entry, raw, entry["historical_sha256"])

    def test_all_reviewed_routes_preserve_whole_original_ast(self):
        for path, entry in self.witness.items():
            result = lineage.verify_captured_source(lineage.ROOT, {
                "path": path, "sha256": entry["historical_sha256"]})
            self.assertEqual(result["current_sha256"], entry["routed_sha256"])
            self.assertEqual(result["historical_sha256"], entry["historical_sha256"])
            self.assertNotEqual(result["current_sha256"], result["historical_sha256"])

    def test_default_body_and_unrelated_import_changes_fail(self):
        mutations = [self.raw + b"\nimport os\n", self.raw.replace(
            b'raise TypeError("Expected a ComponentAssembly.")',
            b'raise ValueError("Expected a ComponentAssembly.")')]
        for raw in mutations:
            self.assertNotEqual(raw, self.raw)
            with self.assertRaisesRegex(ValueError, "implementation AST differs"):
                self.verify_changed(raw)

    def test_signature_and_guard_changes_fail(self):
        for old, new in [(b"core=None", b"core=True"),
                         (b"if core is not None:", b"if core:")]:
            with self.assertRaises(ValueError):
                self.verify_changed(self.raw.replace(old, new, 1))

    def test_current_historical_and_route_inventory_pins_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Current routed source bytes differ"):
            lineage.verify_route_extension(self.entry, self.raw + b"\n",
                                           self.entry["historical_sha256"])
        with self.assertRaisesRegex(ValueError, "Historical source bytes differ"):
            lineage.verify_route_extension(self.entry, self.raw, "0" * 64)
        altered = copy.deepcopy(self.entry)
        altered["historical_source"] += "\n"
        with self.assertRaisesRegex(ValueError, "Historical source bytes differ"):
            lineage.verify_route_extension(altered, self.raw, self.entry["historical_sha256"])
        altered = copy.deepcopy(self.entry)
        altered["functions"].append("unchecked")
        with self.assertRaisesRegex(ValueError, "Unreviewed source route"):
            lineage.verify_route_extension(altered, self.raw, self.entry["historical_sha256"])

    def test_witness_integrity_and_unreviewed_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "witness.json"
            fixture.write_bytes(lineage.WITNESS.read_bytes() + b"\n")
            with patch.object(lineage, "WITNESS", fixture):
                with self.assertRaisesRegex(ValueError, "witness bytes differ"):
                    lineage.load_witness()
            source = root / "other.py"
            source.write_bytes(b"x = 1\n")
            exact = {"path": source.name, "sha256": lineage.sha256(source.read_bytes())}
            self.assertEqual(lineage.verify_captured_source(root, exact)["kind"], "identical_bytes")
            with self.assertRaisesRegex(ValueError, "Captured source bytes differ"):
                lineage.verify_captured_source(root, {"path": source.name, "sha256": "0" * 64})
