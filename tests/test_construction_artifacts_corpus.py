"""Unchecked construction records retain authority without granting acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from biocompiler.artifacts.circuit_molecules import ExperimentalAmount
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import CircuitMoleculeSet

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_construction_artifacts.py"
SPEC = importlib.util.spec_from_file_location("construction_artifact_corpus_under_test", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class ConstructionArtifactsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)
        cls.records = {item["id"]: item for item in cls.corpus["records"]}
        cls.rejections = {item["id"]: item for item in cls.corpus["rejections"]}

    def document(self, identity):
        return self.corpus["documents"][self.records[identity]["document_id"]]

    def test_complete_corpus_reproduces_without_native_build(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)
        self.assertEqual((len(rebuilt["records"]), len(rebuilt["rejections"])), (36, 70))
        self.assertEqual(campaign.inventory(rebuilt), campaign.EXPECTED_INVENTORY)

    def test_all_record_families_derivation_rules_and_original_case_b_candidates(self):
        self.assertEqual({item["kind"] for item in self.records.values()}, set(campaign.KINDS))
        self.assertEqual({self.document(identity)["rule"] for identity in self.records if identity.startswith("derived/rule/")},
                         {"copy", "complement", "dna_coding_to_rna.v1", "rna_editing.v1", "translation_codon.v1"})
        for variant in ("base", "parameter-default", "parameter-override"):
            original = json.loads((campaign.ROOT / f"tests/conformance/case-b/{variant}/candidate.json").read_bytes())
            self.assertEqual(self.document("case_b/" + variant), original["construction"]["candidate"])

    def test_independent_literals_and_unchecked_source_claims_remain_explicit(self):
        self.assertEqual(len(self.corpus["literal_expectations"]), 4)
        for identity, expected in campaign.LITERALS.items():
            self.assertEqual(self.document(identity), expected)
        self.assertEqual(self.document("literal/candidate")["values"], [])
        self.assertIsNone(self.document("candidate/unbound_value")["bundle"])
        self.assertEqual(self.document("value/changed_source_unchecked")["segments"][0]["source_id"], "not_authority")
        self.assertEqual(self.document("value/changed_sequence_unchecked")["sequence"], "ACGAAC")
        self.assertIn("no independent construction acceptance", self.corpus["claim_scope"])

    def test_ordered_consumption_is_distinct_from_sorted_inventories(self):
        left = self.document("value/ordered_consumption")
        right = self.document("value/reversed_consumption")
        self.assertEqual(left["consumed"], list(reversed(right["consumed"])))
        self.assertNotEqual(self.records["value/ordered_consumption"]["fingerprint"], self.records["value/reversed_consumption"]["fingerprint"])
        for left, right in (("candidate/ordered_values", "candidate/value_normalization"),
                            ("candidate/unresolved", "candidate/text_normalization")):
            self.assertEqual(self.records[left]["fingerprint"], self.records[right]["fingerprint"])
            self.assertTrue(self.records[right]["edits"])

    def test_amount_rejections_reach_cross_record_authority_checks(self):
        for suffix in ("without_bundle", "stale", "missing_subject", "wrong_role", "missing_role"):
            case = self.rejections["candidate/amount_" + suffix]
            raw = campaign.apply_edits(self.corpus["documents"][case["document_id"]], case["edits"])
            for value in raw["experimental_amounts"]:
                ExperimentalAmount.from_dict(value)
            if raw["bundle"] is not None:
                CircuitMoleculeSet.from_dict(raw["bundle"])
            with self.assertRaises(SerializationError): campaign.ConstructionCandidate.from_dict(raw)
        integer = self.document("candidate/amount")["experimental_amounts"][0]["quantity"]
        floating = self.document("candidate/amount_float")["experimental_amounts"][0]["quantity"]
        self.assertIs(type(integer), int)
        self.assertIs(type(floating), float)
        self.assertNotEqual(self.records["candidate/amount"]["fingerprint"], self.records["candidate/amount_float"]["fingerprint"])
        self.assertIsNone(self.document("candidate/amount_unknown")["experimental_amounts"][0]["quantity"])

    def test_duplicate_frames_use_individually_valid_values(self):
        case = self.rejections["candidate/duplicate_frames"]
        raw = campaign.apply_edits(self.corpus["documents"][case["document_id"]], case["edits"])
        values = [campaign.ConstructedValue.from_dict(value) for value in raw["values"]]
        self.assertEqual(len({value.id for value in values}), 2)
        self.assertEqual(len({value.space.id for value in values}), 1)
        with self.assertRaises(SerializationError): campaign.ConstructionCandidate.from_dict(raw)

    def test_cumulative_boundary_is_generated_without_retaining_megabase_strings(self):
        cases = {item["id"]: item for item in self.corpus["runtime_cases"]}
        exact = cases["cumulative/exact"]
        value = campaign.runtime_candidate(exact["lengths"])
        self.assertEqual(sum(len(item.sequence) for item in value.values), 1_000_000)
        self.assertEqual(value.fingerprint, exact["fingerprint"])
        overflow = cases["cumulative/overflow"]
        self.assertTrue(all(length <= 1_000_000 for length in overflow["lengths"]))
        with self.assertRaisesRegex(SerializationError, "Cumulative constructed residue limit"): campaign.runtime_candidate(overflow["lengths"])
        self.assertLess(max(len(doc.get("sequence", "")) for doc in self.corpus["documents"].values()), 1000)

    def test_pins_intended_diagnostics_and_independent_sections_cannot_be_forged(self):
        for family, key, value, message in (
            ("records", "id", "replacement", "inventory"),
            ("rejections", "expected_code", "invalid_type", "inventory"),
            ("records", "fingerprint", "0" * 64, "fingerprint"),
        ):
            changed = deepcopy(self.corpus)
            changed[family][0][key] = value
            changed["inventory_sha256"] = campaign.inventory(changed)
            with self.assertRaisesRegex(AssertionError, message): campaign.check_corpus(changed)
        for key in campaign.EXPECTED_SECTIONS:
            changed = deepcopy(self.corpus); changed[key].pop()
            with self.assertRaisesRegex(AssertionError, key): campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        next(iter(changed["documents"].values()))["schema_version"] = "forged"
        with self.assertRaisesRegex(AssertionError, "document pin"): campaign.check_corpus(changed)

    def test_whole_wire_document_remains_bounded_and_checkout_independent(self):
        usage = campaign.check_corpus(self.corpus)
        self.assertLess(usage["bytes"], 4_000_000)
        self.assertLess(usage["nodes"], 150_000)
        self.assertLessEqual(usage["depth"], 16)
        self.assertNotIn(str(campaign.ROOT).encode(), self.content)
        self.assertNotIn(b"/Users/", self.content)


if __name__ == "__main__":
    unittest.main()
