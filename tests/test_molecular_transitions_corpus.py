"""Complete typed transition/edit corpus and independently retained leaf policies."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_molecular_transitions.py"
SPEC = importlib.util.spec_from_file_location("molecular_transition_corpus_under_test", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class MolecularTransitionsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)
        cls.records = {item["id"]: item for item in cls.corpus["records"]}

    def test_complete_compatibility_corpus_reproduces(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)
        self.assertEqual((len(rebuilt["records"]), len(rebuilt["rejections"])), (153, 199))
        self.assertEqual(campaign.inventories(rebuilt), campaign.INVENTORIES)

    def test_closed_dispositions_and_profiles_are_all_retained(self):
        records = self.corpus["records"]
        for kind, field, expected in (
            ("chemistry_disposition", "decision", {"mapped_copy", "declared_replacement", "not_carried", "unknown"}),
            ("feature_disposition", "decision", {"exact", "partial", "split", "not_carried", "outside_selection", "unknown"}),
            ("chemistry_transition", "mode", {"exact_inheritance", "explicit_output"}),
            ("translation_policy", "profile", {"ordinary_cds", "conditional_cds"}),
        ):
            self.assertEqual({row["normalized"][field] for row in records if row["kind"] == kind}, expected)
        self.assertEqual({row["kind"] for row in records}, set(campaign.PARSERS))

    def test_all_canonical_substitutions_and_exclusive_index_edges_remain(self):
        for position in (0, 999999):
            for expected in "ACGU":
                for replacement in "ACGU":
                    identity = f"canonical/{position}/{expected}/{replacement}"
                    if expected != replacement:
                        raw = self.records[identity]["normalized"]
                        self.assertEqual((raw["position"], raw["expected"], raw["replacement"]), (position, expected, replacement))
                    else:
                        row = next(row for row in self.corpus["rejections"] if row["id"] == identity)
                        self.assertEqual(row["input"]["position"], position)
                        self.assertEqual(row["expected_code"], "invalid_canonical_edit")
        self.assertEqual(self.records["recoding/last_index"]["normalized"]["codon_index"], 333332)

    def test_source_independent_chemical_identity_never_rewrites_parent(self):
        addition = self.records["literal/chemical"]["normalized"]
        self.assertEqual(addition["parent"], "A")
        self.assertIsNone(addition["before"])
        self.assertEqual(addition["after"]["accession"], "inosine")
        for label in ("namespace", "version", "custom", "unknown"):
            self.assertEqual(self.records["chemical/unrecognized_" + label]["normalized"]["parent"], "C")
        self.assertNotEqual(self.records["literal/chemical"]["fingerprint"], self.records["literal/canonical"]["fingerprint"])

    def test_nominal_unknown_and_sorted_declarations_preserve_complete_authority(self):
        for left, right in (("policy/conditional", "policy/unsorted"), ("chemistry/explicit", "chemistry/order_normalization"),
                            ("feature/transition", "feature/transition_normalization")):
            self.assertEqual(self.records[left]["fingerprint"], self.records[right]["fingerprint"])
            self.assertNotEqual(self.records[right]["input"], self.records[right]["normalized"])
        self.assertEqual(self.records["chemistry/explicit_empty"]["normalized"]["dispositions"], [])
        self.assertTrue(self.records["feature/unknown_outputs"]["normalized"]["outputs"])
        self.assertIn("source-bound edits", self.corpus["claim_scope"])

    def test_independent_complete_literals_and_all_sixty_four_codons(self):
        campaign.check_corpus(self.corpus)
        self.assertEqual(len(self.corpus["literal_expectations"]), 6)
        table = self.corpus["codon_table"]
        self.assertEqual(len(table), 64)
        self.assertEqual(table["AUG"], "M")
        self.assertEqual({codon for codon, residue in table.items() if residue == "*"}, {"UAA", "UAG", "UGA"})
        self.assertFalse({"U", "O"} & set(table.values()))

    def test_case_identity_diagnostics_literals_and_normalization_cannot_be_forged(self):
        for family, index, key, value, message in (
            ("rejections", 0, "expected_code", "invalid_type", "intended diagnostic"),
            ("records", 0, "id", "replacement_case", "case inventory"),
            ("records", 0, "fingerprint", "0" * 64, "identity drift"),
            ("records", 0, "normalized", {}, "declaration drift"),
        ):
            changed = deepcopy(self.corpus)
            changed[family][index][key] = value
            with self.assertRaisesRegex(AssertionError, message): campaign.check_corpus(changed)
        changed = deepcopy(self.corpus); changed["literal_expectations"].pop()
        with self.assertRaisesRegex(AssertionError, "independent complete literals"): campaign.check_corpus(changed)
        changed = deepcopy(self.corpus); changed["codon_table"]["UGA"] = "U"
        with self.assertRaisesRegex(AssertionError, "standard codon table"): campaign.check_corpus(changed)

    def test_whole_retained_document_is_bounded_and_machine_independent(self):
        usage = campaign.check_corpus(self.corpus)
        self.assertLess(usage["bytes"], 400000)
        self.assertLess(usage["nodes"], 20000)
        self.assertNotIn(str(campaign.ROOT).encode(), self.content)
        self.assertNotIn(b"/Users/", self.content)


if __name__ == "__main__":
    unittest.main()
