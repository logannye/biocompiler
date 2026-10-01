"""Retained Python baseline integrity, independently authored expectations and scope."""

from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from biocompiler.ir.intent import SourceLocation


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("case_b_freezer", ROOT / "tools/freeze_migration_case_b.py")
FREEZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZER)


class MigrationCaseBBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One generation per class: three Python producers, independently
        # authored source/model graphs, fresh checker replay and literal traces.
        cls.generated = FREEZER.generate()
        cls.oracle = json.loads(cls.generated["current-baseline-oracle.json"])

    def test_current_python_outputs_match_every_retained_byte(self):
        self.assertEqual(FREEZER.check_files(FREEZER.CORPUS, self.generated), [])

    def test_every_retained_input_and_output_has_exact_byte_identity(self):
        for name, record in self.oracle["files"].items():
            with self.subTest(name=name):
                content = (FREEZER.CORPUS / name).read_bytes()
                self.assertEqual(record, {"bytes": len(content), "sha256": FREEZER.digest(content)})
        self.assertEqual(set(self.oracle["files"]),
                         (set(self.generated) - {"current-baseline-oracle.json"}) | set(FREEZER.LITERAL_FILES))

    def test_stored_oracle_and_descriptors_do_not_claim_native_acceptance(self):
        self.assertIs(self.oracle["acceptance_authority"], False)
        self.assertEqual(self.oracle["native_execution"], "not_run")
        self.assertEqual(self.oracle["evidence_kind"], "current_python_baseline_oracle")
        descriptors = json.loads((FREEZER.CORPUS / "descriptors.json").read_bytes())
        FREEZER.validate_descriptors(descriptors)
        by_id = {item["id"]: item for item in descriptors["cases"]}
        self.assertGreaterEqual(len(by_id), 40)
        for name in ("control-input-not-causal", "control-material-correspondence",
                     "shared-control-input-contradiction", "alpha-renamed", "changed-valid-artificial-root",
                     "source-implementation-constraint", "source-preference", "wrapped-source-obligations",
                     "supplementary-input-observations", "provider-dependencies",
                     "global-material-limit-violations", "delivery-material-limit-violations"):
            self.assertIn(name, by_id)
            self.assertNotIn("python_evidence", by_id[name])
        self.assertEqual(by_id["forged-resolved-binding"]["prerequisites"],
                         ["parameter-default", "parameter-override"])

    def test_default_and_explicit_override_have_separate_frozen_authority(self):
        default = self.oracle["cases"]["parameter-default"]
        override = self.oracle["cases"]["parameter-override"]
        self.assertEqual(default["intent_fingerprint"], override["intent_fingerprint"])
        for key in ("source_request_fingerprint", "request_fingerprint", "candidate_fingerprint",
                    "behavior_fingerprint", "supplier_behavior_fingerprints"):
            self.assertNotEqual(default[key], override[key], key)
        self.assertEqual(default["literal_timelines_matched"]["initial_context_and_dwell"][-1]["time"], 2)
        self.assertEqual(override["literal_timelines_matched"]["override_changes_deadline"][-1]["time"], 3)

    def test_partial_label_changes_identity_without_granting_or_removing_completeness(self):
        base = self.oracle["cases"]["base"]
        partial = base["complete_partial_label_positive"]
        self.assertNotEqual(base["candidate_fingerprint"], partial["candidate_fingerprint"])
        for key in ("outcome", "translation_complete", "construction_complete", "claim_scope",
                    "search_verified", "empirical_validation", "human_therapeutic_admission"):
            self.assertEqual(base["python_verification"][key], partial["python_verification"][key])
        self.assertEqual(partial["python_verification"]["build_fingerprint"], partial["candidate_fingerprint"])

    def test_paths_are_standardized_before_enclosing_authority_is_constructed(self):
        raw = FREEZER.examples_module().make_architecture_request("B")
        canonical, mappings = FREEZER.make_request("base")
        self.assertEqual(raw.source.intent.fingerprint, canonical.source.intent.fingerprint)
        self.assertEqual(raw.source.fingerprint, canonical.source.fingerprint)
        self.assertNotEqual(raw.source.artifact_fingerprint, canonical.source.artifact_fingerprint)
        self.assertNotEqual(raw.fingerprint, canonical.fingerprint)
        self.assertEqual(self.oracle["cases"]["base"]["request_fingerprint"], canonical.fingerprint)
        for label in ("source", "supplier"):
            self.assertEqual(mappings[label]["raw_intent_semantic_fingerprint"],
                             mappings[label]["normalized_intent_semantic_fingerprint"])
            self.assertEqual(len(mappings[label]["nodes"]), 33)
            for item in mappings[label]["nodes"]:
                self.assertEqual(item["canonical"]["file"], "examples/payload_architectures.py")
                self.assertEqual(item["original"]["file"], "<checkout>/examples/payload_architectures.py")
                self.assertEqual(item["original"]["line"], item["canonical"]["line"])
                self.assertEqual(item["original"]["function"], item["canonical"]["function"])

    def test_source_relocation_is_independent_of_checkout_prefix(self):
        raw = FREEZER.examples_module().source_program("B")
        relocated = replace(raw, nodes=tuple(replace(
            node, source=SourceLocation("/another/checkout/examples/payload_architectures.py",
                                       node.source.line, node.source.function)) for node in raw.nodes))
        original, original_map = FREEZER.normalize_program(raw)
        other, other_map = FREEZER.normalize_program(relocated, root=Path("/another/checkout"))
        self.assertEqual(original.to_dict(), other.to_dict())
        self.assertEqual(original_map, other_map)
        with self.assertRaises(ValueError):
            FREEZER.normalize_program(relocated)

    def test_census_covers_separate_request_and_candidate_schemas(self):
        census = json.loads(self.generated["schema-census.json"])
        self.assertEqual(len(census), 6)
        for variant in FREEZER.VARIANTS:
            for artifact, schema in (("request", "biocompiler.payload_architecture_request.v0.1"),
                                     ("candidate", "biocompiler.payload_architecture_build.v0.2")):
                self.assertEqual(census[variant + "/" + artifact][schema]["paths"], ["/"])
                self.assertIn("biocompiler.intent.v0.1", census[variant + "/" + artifact])

    def test_byte_drift_and_missing_files_are_reported_without_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in self.generated.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            (root / "generation.json").write_bytes((FREEZER.CORPUS / "generation.json").read_bytes())
            changed = root / "base/candidate.json"
            changed.write_bytes(changed.read_bytes() + b" ")
            (root / "parameter-default/request.json").unlink()
            self.assertEqual(FREEZER.check_files(root, self.generated),
                             ["base/candidate.json", "parameter-default/request.json"])
            self.assertTrue(changed.read_bytes().endswith(b" "))

    def test_descriptor_scope_is_fail_closed(self):
        document = json.loads((FREEZER.CORPUS / "descriptors.json").read_bytes())
        forged = deepcopy(document)
        forged["cases"][0]["native_execution"] = "passed"
        with self.assertRaisesRegex(AssertionError, "cannot assert native"):
            FREEZER.validate_descriptors(forged)
        duplicate = deepcopy(document)
        duplicate["cases"].append(duplicate["cases"][0])
        with self.assertRaisesRegex(AssertionError, "Duplicate descriptor"):
            FREEZER.validate_descriptors(duplicate)


if __name__ == "__main__":
    unittest.main()
