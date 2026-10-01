"""Source-only fresh-check corpus gates; hosted native validation is separate."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_payload_structure_check.py"
SPEC = importlib.util.spec_from_file_location("payload_structure_check_campaign", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class PayloadStructureCheckCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)
        cls.cases = {item["id"]: item for item in cls.corpus["cases"]}

    def raw(self, case_id):
        return self.corpus["documents"][self.cases[case_id]["bundle_document"]]

    def test_exact_source_only_regeneration(self):
        current = campaign.build_corpus()
        campaign.check_corpus(current)
        self.assertEqual(campaign.encoded(current), self.content)

    def test_full_input_expected_and_scope_inventory(self):
        self.assertEqual((len(self.cases), len(self.corpus["documents"])), (99, 48))
        self.assertEqual(campaign.inventory(self.corpus), campaign.INVENTORY)
        diagnostics = {value.split(":")[0] for case in self.cases.values() for value in case["expected"]["diagnostics"]}
        unsupported = {value.split(":")[0] for case in self.cases.values() for value in case["expected"]["unsupported"]}
        self.assertEqual(diagnostics, {"payload_bundle_invalid", "payload_contract_extra", "payload_contract_inventory_invalid", "payload_form_mismatch", "payload_region_empty", "payload_region_kind_mismatch", "payload_region_missing", "payload_topology_mismatch"})
        self.assertEqual(unsupported, {"payload_authority_missing", "payload_authority_undeclared", "payload_boundary_authority_undeclared", "payload_chemistry_incomplete", "payload_complex_stoichiometry_unknown", "payload_extent_incomplete", "payload_modality_unsupported", "payload_region_coordinates_unknown"})

    def test_all_modalities_geometry_and_helpers_are_scoped(self):
        for modality in self.corpus["coverage"]["modalities"]:
            self.assertEqual(self.cases["modality/" + modality]["expected"], campaign.pair())
        for identity in ("geometry/overlap_reverse_cross_origin", "roles/repeated_payload_helper_excluded", "scope/protein_helper_ignored", "scope/changed_spelling_same_declared_regions"):
            self.assertEqual(self.cases[identity]["expected"], campaign.pair())
        self.assertIn("no construction replay", self.corpus["claim_scope"])
        self.assertIn("human therapeutic admission", self.corpus["claim_scope"])

    def test_typed_dictionary_misuse_is_not_serialized_import_parity(self):
        identity = "serialized_contract_dicts_are_imported"
        case = self.cases[identity]
        typed_bundle = campaign.CircuitMoleculeSet.from_dict(self.raw(identity))
        result = campaign.check_payload_structures(case["contracts"], bundle=typed_bundle)
        self.assertEqual(campaign.pair(*result), self.corpus["api_boundary"]["typed_dictionary_misuse"]["python_direct"])
        self.assertEqual(campaign.check_serialized(case["contracts"], self.raw(identity)), self.corpus["api_boundary"]["typed_dictionary_misuse"]["native_serialized"])
        self.assertNotEqual(campaign.pair(*result), case["expected"])

    def test_original_case_b_source_and_contracts_are_retained(self):
        for variant in ("base", "parameter-default", "parameter-override"):
            request = json.loads((campaign.ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
            candidate = json.loads((campaign.ROOT / f"tests/conformance/case-b/{variant}/candidate.json").read_bytes())
            base = "case_b/" + variant + "/complete"
            self.assertEqual(self.raw(base), candidate["construction"]["candidate"]["bundle"])
            self.assertEqual(self.raw(base)["request"], request["circuit"])
            self.assertEqual(self.cases[base]["contracts"], candidate["construction"]["request"]["payload_structures"])
            source_contract = deepcopy(request["library"]["refinements"][0]["templates"][0]["payload_structures"][0])
            self.assertEqual(source_contract["member_id"], "payload")
            source_contract["member_id"] = "a000_t000_payload"
            self.assertEqual(self.cases[base]["contracts"], [source_contract])
            for mutation in ("changed_kind_rehashed", "unknown_boundary_rehashed"):
                identity = "case_b/" + variant + "/" + mutation
                self.assertEqual(self.raw(identity)["request"], request["circuit"])
                self.assertEqual(self.cases[identity]["contracts"], self.cases[base]["contracts"])
                self.assertNotEqual(self.cases[identity]["expected"], campaign.pair())

    def test_rehashed_mutations_are_valid_candidates_with_original_source(self):
        examined = 0
        for case in self.cases.values():
            if case["original_bundle_document"] is None or case["boundary"] != "typed_and_serialized":
                continue
            original = self.corpus["documents"][case["original_bundle_document"]]
            changed = self.corpus["documents"][case["bundle_document"]]
            parsed = campaign.CircuitMoleculeSet.from_dict(changed)
            self.assertEqual(parsed.request.to_dict(), original["request"])
            self.assertNotEqual(campaign.fingerprint(changed), campaign.fingerprint(original))
            subject_pins = {item.id: item.fingerprint for item in (*parsed.molecules, *parsed.complexes)}
            self.assertTrue(all(item.subject_fingerprint == subject_pins[item.subject_id] for item in parsed.role_instances))
            examined += 1
        self.assertEqual(examined, 16)

    def test_complex_stoichiometry_and_import_precedence(self):
        self.assertEqual(self.cases["complex/rna_complex/unknown_stoichiometry_rehashed"]["expected"], campaign.pair(unsupported=["payload_complex_stoichiometry_unknown:assembly/one"]))
        self.assertEqual(self.cases["complex/dna_duplex/unknown_stoichiometry_rehashed"]["expected"], campaign.pair(["payload_bundle_invalid"]))
        self.assertEqual(self.cases["import/invalid_contract_precedes_invalid_bundle"]["expected"], campaign.pair(["payload_contract_inventory_invalid"]))
        self.assertEqual(self.cases["import/null_bundle_empty_contracts"]["expected"], campaign.pair(["payload_bundle_invalid"], ["payload_authority_missing"]))

    def test_exact_inventory_boundary_and_all_contract_import_failures(self):
        case = self.cases["bound/exact64_contracts"]
        self.assertEqual(len(case["contracts"]), 64)
        self.assertEqual(len(case["expected"]["diagnostics"]), 63)
        self.assertEqual(self.cases["import/contracts_over_limit"]["expected"], campaign.pair(["payload_contract_inventory_invalid"]))
        declarations = json.loads((campaign.ROOT / "tests/conformance/payload-structure-v1.json").read_bytes())
        self.assertEqual({key.removeprefix("import/contract/") for key in self.cases if key.startswith("import/contract/")},
                         {item["id"].removeprefix("contract/") for item in declarations["rejections"] if item["kind"] == "contract"})

    def test_false_coverage_claims_are_explicitly_excluded(self):
        self.assertEqual(self.corpus["api_boundary"]["unreachable_after_checked_import"], ["payload_modality_alphabet", "payload_region_coordinates_invalid", "payload_complex_modality_unsupported"])
        for identity in ("import/inconsistent_alphabet", "import/wrong_coordinate_frame", "import/protein_relabelled_payload"):
            self.assertEqual(self.cases[identity]["expected"], campaign.pair(["payload_bundle_invalid"]))

    def test_missing_substituted_expected_or_document_fail_closed(self):
        for edit in (
            lambda value: value["cases"].pop(),
            lambda value: value["cases"][0]["expected"]["unsupported"].append("forged"),
            lambda value: value["cases"][0].update(id="substitution"),
            lambda value: next(iter(value["documents"].values())).update(id="forged"),
        ):
            bad = deepcopy(self.corpus); edit(bad); bad["inventory_sha256"] = campaign.inventory(bad)
            with self.assertRaises(AssertionError):
                campaign.check_corpus(bad)

    def test_whole_fixture_budget_and_portable_source_locations(self):
        campaign.check_corpus(self.corpus)
        self.assertLess(len(self.content), 16 * 1024 * 1024)
        self.assertNotIn(b"/Users/", self.content)
        self.assertNotIn(b"/home/runner/", self.content)


if __name__ == "__main__":
    unittest.main()
