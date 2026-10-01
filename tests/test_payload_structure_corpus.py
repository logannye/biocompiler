"""Source-only corpus integrity; native conformance is a separate hosted gate."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_payload_structure.py"
SPEC = importlib.util.spec_from_file_location("payload_structure_corpus_under_test", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class PayloadStructureCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)
        cls.cases = {item["id"]: item for item in cls.corpus["records"]}

    def test_exact_regeneration(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)

    def test_exact_case_and_diagnostic_inventory(self):
        self.assertEqual((len(self.corpus["records"]), len(self.corpus["rejections"])), (14, 44))
        self.assertEqual(campaign.inventory(self.corpus), "34f60cd9057611341e84ab3572af9839fd7817791496507684d007e590637094")
        self.assertEqual({item["kind"] for item in self.corpus["records"]}, {"region", "contract"})

    def test_original_case_b_contract_authority_preserved(self):
        for variant in ("base", "parameter-default", "parameter-override"):
            source = json.loads((campaign.ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
            expected = source["library"]["refinements"][0]["templates"][0]["payload_structures"][0]
            self.assertEqual(campaign.encoded(expected), campaign.encoded(self.cases["case_b/" + variant]["input"]))

    def test_modalities_and_unknown_authority_do_not_imply_acceptance(self):
        for form in ("delivered_rna", "delivered_dna"):
            for topology in ("linear", "circular"):
                case = self.cases[f"contract/{form}/{topology}"]
                self.assertEqual((case["normalized"]["form"], case["normalized"]["topology"]), (form, topology))
        self.assertEqual(self.cases["contract/unknown_authority"]["normalized"]["provenance"]["status"], "unknown")
        self.assertIn("no geometry", self.corpus["claim_scope"])

    def test_regions_are_a_sorted_inventory_with_exact_boundary(self):
        self.assertEqual(self.cases["contract/base"]["fingerprint"], self.cases["contract/reversed_input"]["fingerprint"])
        self.assertNotEqual(self.cases["contract/base"]["input"]["regions"], self.cases["contract/reversed_input"]["input"]["regions"])
        self.assertEqual(len(self.cases["contract/maximum_regions"]["normalized"]["regions"]), 256)
        self.assertTrue(any(item["id"] == "contract/too_many_regions" for item in self.corpus["rejections"]))

    def test_tampered_or_missing_authority_rejects(self):
        bad = deepcopy(self.corpus); bad["records"].pop()
        with self.assertRaisesRegex(AssertionError, "inventory"):
            campaign.check_corpus(bad)
        bad = deepcopy(self.corpus); bad["records"][0]["fingerprint"] = "0" * 64
        with self.assertRaises(AssertionError):
            campaign.check_corpus(bad)

    def test_fixture_is_bounded_and_has_no_machine_paths(self):
        pending, count, depth = [(self.corpus, 0)], 0, 0
        while pending:
            value, current = pending.pop(); count += 1; depth = max(depth, current)
            if isinstance(value, dict):
                pending.extend((v, current + 1) for pair in value.items() for v in pair)
            elif isinstance(value, list):
                pending.extend((v, current + 1) for v in value)
        self.assertLess(count, 250_000)
        self.assertLess(depth, 128)
        self.assertLess(len(self.content), 300_000)
        self.assertNotIn(b"/Users/", self.content)


if __name__ == "__main__":
    unittest.main()
