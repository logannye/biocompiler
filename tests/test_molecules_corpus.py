"""Pure Python integrity checks for complete native molecular domain fixtures."""
import ast
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_molecules.py"
SPEC = importlib.util.spec_from_file_location("molecules_corpus_under_test", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class MoleculesCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)
        cls.cases = {item["id"]: item for item in cls.corpus["records"]}

    def document(self, identity):
        return self.corpus["documents"][self.cases[identity]["document_id"]]

    def test_deterministic_complete_python_authority(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)

    def test_exact_record_mutation_and_enum_census(self):
        self.assertEqual(len(self.corpus["records"]), 109)
        self.assertEqual(len(self.corpus["rejections"]), 136)
        self.assertEqual(len(self.corpus["relations"]), 16)
        counts = Counter(item["kind"] for item in self.corpus["records"])
        self.assertEqual(counts, dict(molecule=44, assembly_origin=1, feature=4, constituent=3,
                                     complex=4, role=5, mapping=11, set=20, artifact=8, amount=9))
        actual_forms = {self.document(item["id"])["form"] for item in self.corpus["records"] if item["kind"] == "molecule"}
        actual_relations = {self.document(item["id"])["relation"] for item in self.corpus["records"] if item["kind"] == "mapping"}
        self.assertEqual(actual_forms, campaign.FORMS)
        self.assertEqual(actual_relations, campaign.MAPPING_RELATIONS)
        tests = ast.parse((campaign.ROOT / "tests/test_circuit_molecule_integration.py").read_text())
        count = sum(isinstance(item, ast.FunctionDef) and item.name.startswith("test_") for item in ast.walk(tests))
        self.assertEqual(count, self.corpus["coverage"]["original_integration_tests"])

    def test_complete_original_example_and_wrapped_authority(self):
        artifact = self.document("artifact/full_example")
        bundle = artifact["bundle"]
        self.assertEqual((len(bundle["molecules"]), len(bundle["complexes"]), len(bundle["role_instances"]),
                          len(bundle["form_mappings"]), len(artifact["experimental_amounts"])), (8, 1, 10, 1, 1))
        self.assertEqual(bundle["request"]["profile"]["source_request"]["schema_version"], "biocompiler.human_acceptance_request.v0.1")
        observed = {self.document(identity)["request"]["profile"]["source_request"]["schema_version"]
                    for identity in ("set/plain", "set/wrapper_behavior", "set/wrapper_deployment", "set/wrapper_acceptance")}
        self.assertEqual(observed, {"biocompiler." + kind + ".v0.1" for kind in self.corpus["coverage"]["source_request_kinds"]})
        self.assertIsNone(artifact["experimental_amounts"][0]["quantity"])
        self.assertEqual(len(artifact["experimental_amounts"][0]["role_instance_ids"]), 2)

    def test_all_original_case_b_authority_occurrences_remain_exact(self):
        pointers = self.corpus["coverage"]["case_b"]
        self.assertEqual(len(pointers), 9)
        for item in pointers:
            original = json.loads((campaign.ROOT / "tests/conformance/case-b" / item["variant"] / "candidate.json").read_bytes())
            for key in item["path"]:
                original = original[key]
            self.assertEqual(campaign.encoded(original), campaign.encoded(self.document(item["id"])))

    def test_amount_numbers_keep_primitive_kind_signed_zero_and_full_integer_range(self):
        values = {name: self.document("amount/" + name)["quantity"]
                  for name in ("unknown", "zero", "float_zero", "negative_zero", "max_integer")}
        self.assertIsNone(values["unknown"])
        self.assertIs(type(values["zero"]), int)
        self.assertIs(type(values["float_zero"]), float)
        self.assertEqual(campaign.encoded(values["negative_zero"]), b"-0.0\n")
        self.assertEqual(values["max_integer"], (1 << 1024)-1)
        hashes = [self.cases["amount/" + name]["expected"]["fingerprint"] for name in values]
        self.assertEqual(len(set(hashes)), len(hashes))

    def test_constructor_default_is_still_required_on_import(self):
        missing = next(item for item in self.corpus["rejections"] if item["id"] == "fields/feature/missing/reading_frame")
        self.assertEqual(missing["expected_code"], "missing_field")
        feature = campaign.MoleculeFeature.from_dict(self.document("feature/unknown"))
        self.assertIsNone(feature.reading_frame)

    def test_whole_fixture_respects_native_budget_including_object_keys(self):
        pending, count, maximum_depth = [(self.corpus, 0)], 0, 0
        while pending:
            value, depth = pending.pop()
            count += 1
            maximum_depth = max(maximum_depth, depth)
            if isinstance(value, dict):
                pending.extend((item, depth + 1) for pair in value.items() for item in pair)
            elif isinstance(value, list):
                pending.extend((item, depth + 1) for item in value)
        self.assertLessEqual(count, 250_000)
        self.assertLessEqual(maximum_depth, 128)
        self.assertLess(len(self.content), 16 * 1024 * 1024)
        self.assertNotIn(b"/Users/", self.content)

    def test_stale_identity_missing_inventory_and_duplicate_cases_reject(self):
        stale = deepcopy(self.corpus)
        stale["records"][0]["expected"]["fingerprint"] = "a" * 64
        with self.assertRaisesRegex(AssertionError, "identity expectation"):
            campaign.check_corpus(stale)
        stale = deepcopy(self.corpus)
        stale["records"].pop()
        with self.assertRaisesRegex(AssertionError, "coverage count"):
            campaign.check_corpus(stale)
        stale = deepcopy(self.corpus)
        stale["records"][1]["id"] = stale["records"][0]["id"]
        with self.assertRaisesRegex(AssertionError, "Duplicate molecular"):
            campaign.check_corpus(stale)

    def test_intended_deep_set_and_artifact_mutations_cannot_become_acceptance(self):
        expected = {"set/stale_constituent", "set/target_compartment", "set/duplicate_destination",
                    "artifact/alias_preparation", "artifact/stale_amount", "artifact/missing_role"}
        actual = {item["id"] for item in self.corpus["rejections"]}
        self.assertTrue(expected <= actual)
        campaign.check_corpus(self.corpus)


if __name__ == "__main__":
    unittest.main()
