"""Only reviewed excluded-source metadata may bridge the immutable CLI corpus."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_workflow_cli_corpus as lineage


class WorkflowCliLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.blobs = lineage.load_baseline()

    def recapture(self):
        # Pure source-inventory fixture: production current_scope independently
        # validates actual filesystem/reviewed pins. The tests here isolate the
        # metadata projection, with no child commands and no product imports.
        actual = deepcopy(self.baseline)
        scope = actual["source_scope"]
        additions = {entry["path"]: entry["sha256"] for entry in scope["reviewed_additions"]}
        additions["src/biocompiler/core_artifacts.py"] = "1" * 64
        additions["src/biocompiler/core_workflow_authority.py"] = "2" * 64
        additions["src/biocompiler/workflow_backend.py"] = "3" * 64
        historical = {entry["path"]: entry["sha256"] for entry in scope["historical_sources"]}
        scope["actual_sources"] = [{"path": path, "sha256": pin} for path, pin in sorted({**historical, **additions}.items())]
        scope["actual_source_inventory_sha256"] = lineage.digest(scope["actual_sources"])
        scope["reviewed_additions"] = [{"path": path, "sha256": pin} for path, pin in sorted(additions.items())]
        scope["denied_modules"] = [path[4:-3].replace("/", ".") for path in sorted(additions)]
        self.rehash(actual)
        return actual, deepcopy(scope)

    def rehash(self, document):
        document["inventory_fingerprint"] = lineage.digest({key: value for key, value in document.items()
                                                           if key != "inventory_fingerprint"})

    def test_archived_scope_is_reconstructed_from_old_source_pins_without_current_relabeling(self):
        self.assertEqual(self.baseline["inventory_fingerprint"], lineage.CORPUS_PIN)
        self.assertEqual(lineage.digest(self.baseline["source_scope"]), lineage.SCOPE_PIN)
        self.assertEqual(len(self.blobs), 114)
        self.assertEqual(len(self.baseline["cases"]), 70)
        with patch.dict(lineage.FROZEN_ADDITIONS, {"src/biocompiler/core_artifacts.py": "0" * 64}):
            with self.assertRaisesRegex(AssertionError, "independently pinned"):
                lineage.load_baseline()

    def test_only_source_scope_and_index_identity_change_and_actual_metadata_is_retained(self):
        actual, scope = self.recapture()
        before = deepcopy(actual)
        with patch.object(lineage, "current_scope", return_value=scope):
            projected, evidence = lineage.historical_projection(actual)
            receipt = lineage.verify_recapture(actual, self.blobs, python_version="3.14")
        self.assertEqual(actual, before)
        self.assertEqual(projected, self.baseline)
        self.assertNotEqual(actual["inventory_fingerprint"], lineage.CORPUS_PIN)
        self.assertEqual(evidence["actual_source_scope"], scope)
        self.assertEqual(receipt["actual_source_scope"], scope)
        self.assertEqual(receipt["status"], "complete_original_cli_recapture_equal")
        self.assertEqual(receipt["actual_inventory_fingerprint"], actual["inventory_fingerprint"])
        self.assertEqual(receipt["projected_inventory_fingerprint"], lineage.CORPUS_PIN)
        self.assertEqual([row["path"] for row in receipt["source_changes"]], [
            "src/biocompiler/core_artifacts.py", "src/biocompiler/core_workflow_authority.py",
            "src/biocompiler/workflow_backend.py"])
        for key in actual:
            if key not in ("source_scope", "inventory_fingerprint"):
                self.assertEqual(lineage.canonical(projected[key]), lineage.canonical(actual[key]))

    def test_observation_environment_source_byte_and_blob_tampering_is_never_projected_away(self):
        actual, scope = self.recapture()
        mutations = [
            lambda value: value["cases"][0].update(exit_code=99),
            lambda value: value["cases"][0]["stdout"].update(sha256="a" * 64),
            lambda value: value["cases"][0]["stderr"].update(bytes=7),
            lambda value: value["cases"][0].update(files_after={}),
            lambda value: value["cases"].pop(),
            lambda value: value["capture_environment"].update(hash_seed="37"),
            lambda value: value["capture_environment"]["startup"].update(sha256="b" * 64),
            lambda value: value["capture_environment"]["entrypoint_source"].update(bytes=1),
            lambda value: value["retained_source_bytes"]["src/biocompiler/cli.py"].update(sha256="c" * 64),
        ]
        with patch.object(lineage, "current_scope", return_value=scope):
            for mutate in mutations:
                changed = deepcopy(actual)
                mutate(changed)
                self.rehash(changed)
                projected, _ = lineage.historical_projection(changed)
                self.assertNotEqual(projected, self.baseline)
                with self.assertRaisesRegex(AssertionError, "observations differ"):
                    lineage.verify_recapture(changed, self.blobs, python_version="3.14")
            blobs = dict(self.blobs)
            identity = next(iter(blobs))
            blobs[identity] += b"forged"
            with self.assertRaisesRegex(AssertionError, "content differs"):
                lineage.verify_recapture(actual, blobs, python_version="3.14")

    def test_only_exact_declared_python311_counterpart_projects_and_actual_bytes_remain(self):
        actual, scope = self.recapture()
        self.actual_blobs = dict(self.blobs)
        old = next(row for row in self.baseline["cases"] if row["id"] == "unknown-flag")
        row = next(row for row in actual["cases"] if row["id"] == old["id"])
        expected = lineage.runtime.workflow().expected(old, {"exit_code": old["exit_code"],
            **{field: lineage.frozen.restore(old[field], self.blobs) for field in ("stdout", "stderr")}}, "3.11")
        store = lineage.frozen.Store()
        replacement = store.retain(expected["stderr"])
        del self.actual_blobs[row["stderr"]["sha256"]]
        self.actual_blobs.update(store.blobs)
        row["stderr"] = replacement
        self.rehash(actual)
        before = deepcopy(actual)
        with patch.object(lineage, "current_scope", return_value=scope):
            receipt = lineage.verify_recapture(actual, self.actual_blobs, python_version="3.11.16")
            self.assertEqual(receipt["actual_capture"], before)
            self.assertEqual(actual, before)
            self.assertEqual(receipt["projected_inventory_fingerprint"], lineage.CORPUS_PIN)
            self.assertEqual(receipt["runtime_counterpart"]["changes"], [{"id": old["id"], "field": "stderr",
                "actual": replacement, "baseline": old["stderr"]}])
            for version in ("3.14", "3.12", "3.15"):
                with self.assertRaises(AssertionError):
                    lineage.verify_recapture(actual, self.actual_blobs, python_version=version)
            forged = deepcopy(actual); content = dict(self.actual_blobs)
            forged_row = next(row for row in forged["cases"] if row["id"] == old["id"])
            del content[forged_row["stderr"]["sha256"]]
            store = lineage.frozen.Store(); forged_row["stderr"] = store.retain(expected["stderr"] + b" ")
            content.update(store.blobs); self.rehash(forged)
            with self.assertRaisesRegex(AssertionError, "runtime counterpart stderr differs"):
                lineage.verify_recapture(forged, content, python_version="3.11")


    def test_rehashed_scope_forgeries_missing_sources_and_changed_import_audits_fail(self):
        actual, scope = self.recapture()
        with patch.object(lineage, "current_scope", return_value=scope):
            mutations = [
                lambda value: value["source_scope"]["actual_sources"][0].update(sha256="0" * 64),
                lambda value: value["source_scope"]["reviewed_additions"].pop(),
                lambda value: value["source_scope"]["denied_modules"].clear(),
                lambda value: value["source_scope"].update(historical_corpus_pin="forged"),
                lambda value: value["source_scope"].update(omitted_tests_for_focused_instrumentation=["tests/test_synthetic_generation.py"]),
                lambda value: value["source_scope"]["actual_sources"].append(value["source_scope"]["actual_sources"][0]),
                lambda value: value["cases"][0]["import_audit"].update(guard_active=False),
                lambda value: value["cases"][0]["import_audit"].update(denied_absent=False),
                lambda value: value["cases"][0]["import_audit"]["modules"].update({"biocompiler.workflow_backend": {
                    "path": "src/biocompiler/workflow_backend.py", "sha256": "3" * 64}}),
            ]
            for mutate in mutations:
                changed = deepcopy(actual)
                mutate(changed)
                self.rehash(changed)
                with self.assertRaises(AssertionError):
                    lineage.historical_projection(changed)
            changed = deepcopy(actual)
            first = next(iter(changed["cases"][0]["import_audit"]["modules"].values()))
            first["sha256"] = "f" * 64
            self.rehash(changed)
            with self.assertRaisesRegex(AssertionError, "not historical"):
                lineage.historical_projection(changed)
        with patch.object(lineage, "current_scope", return_value=self.baseline["source_scope"]):
            with self.assertRaisesRegex(AssertionError, "current reviewed bytes"):
                lineage.historical_projection(actual)

    def test_historical_and_archived_source_files_cannot_change_even_with_rehashed_metadata(self):
        actual, scope = self.recapture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = "src/biocompiler/cli.py"
            path = root / name
            path.parent.mkdir(parents=True)
            path.write_bytes(b"changed historical CLI")
            with patch.object(lineage, "ROOT", root):
                with self.assertRaisesRegex(AssertionError, "Archived CLI source bytes changed"):
                    lineage.load_baseline()
            forged = deepcopy(scope)
            name = forged["historical_sources"][0]["path"]
            forged["historical_sources"][0]["sha256"] = "4" * 64
            changed = deepcopy(actual)
            changed["source_scope"] = forged
            self.rehash(changed)
            with patch.object(lineage, "current_scope", return_value=forged):
                # Even a counterfeit current-scope result cannot replace the
                # immutable historical inventory or bytes used by projection.
                with self.assertRaises(AssertionError):
                    lineage.historical_projection(changed)

    def test_current_inventory_requires_explicit_reviewed_source_additions(self):
        with patch.dict(lineage.source.REVIEWED_ADDITIONS, {}, clear=True):
            with self.assertRaisesRegex(AssertionError, "Unreviewed workflow source addition"):
                lineage.current_scope()


if __name__ == "__main__":
    unittest.main()
