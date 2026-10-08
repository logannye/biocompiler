"""Only pinned packaging and dispatch edits can explain original CLI metadata."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from tools import package_metadata_source_lineage as metadata
from tools import freeze_workflow_cli as workflow
from tools import freeze_synthetic_selection_cli as selection


class PackageMetadataSourceLineageTests(unittest.TestCase):
    def test_complete_original_bytes_match_both_immutable_cli_corpora(self):
        historical, proof = metadata.counterpart()
        for freezer, restore in ((workflow, workflow.restore), (selection, selection.f.restore)):
            document, blobs = freezer.load()
            self.assertEqual(historical, restore(document["retained_source_bytes"][metadata.PATH], blobs))
        old = tomllib.loads(historical.decode())
        current = tomllib.loads(proof["current_source"])
        self.assertEqual(current["project"].pop("optional-dependencies"),
                         {"core": ["biocompiler-core==0.1.0.dev29"]})
        self.assertEqual(current["tool"]["setuptools"]["package-data"]["biocompiler"].pop(0),
                         "_core_release.json")
        self.assertEqual(current["project"]["scripts"]["biocompiler"], "biocompiler.entrypoint:main")
        current["project"]["scripts"]["biocompiler"] = "biocompiler.cli:main"
        self.assertEqual(current, old)
        from tools import policy_entrypoint_source_lineage as policy
        self.assertEqual(proof["schema_version"], "biocompiler.package_metadata_source_counterpart.v2")
        self.assertEqual(proof["packaging_source_sha256"], metadata.CURRENT_SHA256)
        self.assertEqual(proof["policy_entrypoint_counterpart"]["witness_sha256"], policy.WITNESS_SHA256)
        self.assertEqual(proof["current_sha256"], metadata.sha((metadata.ROOT / metadata.PATH).read_bytes()))

    def test_stale_changed_or_missing_current_source_is_rejected(self):
        old, proof = metadata.counterpart()
        for raw in (old, proof["current_source"].encode() + b"\n",
                    proof["current_source"].replace("biocompiler.entrypoint:main", "elsewhere:main").encode()):
            with self.subTest(sha256=metadata.sha(raw)), self.assertRaises(ValueError):
                metadata.counterpart(current=raw)

    def test_each_uncomposed_revision_and_changed_policy_witness_is_rejected(self):
        from tools import policy_entrypoint_source_lineage as policy
        packaged = json.loads((metadata.ROOT / metadata.WITNESS).read_bytes())["current_source"].encode()
        dispatched = policy.witness()["sources"][metadata.PATH]["after_source"].encode()
        for raw in (packaged, dispatched):
            with self.subTest(sha256=metadata.sha(raw)), self.assertRaisesRegex(ValueError, "exact whole-source counterpart"):
                metadata.counterpart(current=raw)
        read = Path.read_bytes
        witness_path = metadata.ROOT / policy.WITNESS
        def changed(path):
            raw = read(path)
            return raw + b' ' if path == witness_path else raw
        with patch.object(Path, 'read_bytes', changed), self.assertRaisesRegex(ValueError, "Policy entrypoint witness bytes changed"):
            metadata.counterpart()

    def test_changed_witness_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            witness = root / metadata.WITNESS
            witness.parent.mkdir(parents=True)
            witness.write_bytes((metadata.ROOT / metadata.WITNESS).read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "witness bytes changed"):
                metadata.counterpart(root)

    def test_repaired_hashes_cannot_authorize_an_unlisted_console_script_edit(self):
        original = json.loads((metadata.ROOT / metadata.WITNESS).read_bytes())
        entry = deepcopy(original)
        entry["current_source"] = entry["current_source"].replace("biocompiler.cli:main", "elsewhere:main")
        entry["current_sha256"] = metadata.sha(entry["current_source"].encode())
        raw = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            witness = root / metadata.WITNESS
            witness.parent.mkdir(parents=True)
            witness.write_bytes(raw)
            with patch.object(metadata, "WITNESS_SHA256", metadata.sha(raw)), \
                    patch.object(metadata, "CURRENT_SHA256", entry["current_sha256"]), \
                    self.assertRaisesRegex(ValueError, "unlisted whole-source change"):
                metadata.counterpart(root, current=entry["current_source"].encode())

    def test_repaired_witness_cannot_change_the_closed_edit_recipe(self):
        entry = json.loads((metadata.ROOT / metadata.WITNESS).read_bytes())
        entry["changes"].append({"before": "biocompiler.cli:main", "after": "elsewhere:main"})
        raw = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            witness = root / metadata.WITNESS
            witness.parent.mkdir(parents=True)
            witness.write_bytes(raw)
            with patch.object(metadata, "WITNESS_SHA256", metadata.sha(raw)), \
                    self.assertRaisesRegex(ValueError, "exact recipe"):
                metadata.counterpart(root, current=entry["current_source"].encode())

    def test_actual_metadata_bytes_cannot_be_discarded_by_projection(self):
        from tests.test_workflow_cli_lineage import WorkflowCliLineageTests
        from tools import check_workflow_cli_corpus as checker
        fixture = WorkflowCliLineageTests()
        fixture.baseline, fixture.blobs = checker.load_baseline()
        actual, _ = fixture.recapture()
        changed = deepcopy(actual)
        changed["retained_source_bytes"][metadata.PATH] = deepcopy(
            fixture.baseline["retained_source_bytes"][metadata.PATH])
        fixture.rehash(changed)
        with self.assertRaisesRegex(AssertionError, "source byte identity differs"):
            checker.historical_projection(changed)
        blobs = dict(fixture.actual_blobs)
        identity = actual["retained_source_bytes"][metadata.PATH]["sha256"]
        blobs[identity] += b"changed"
        with self.assertRaises(AssertionError):
            checker.verify_recapture(actual, blobs, python_version="3.14")


if __name__ == "__main__":
    unittest.main()
