"""Source-only composite authority gates; hosted OCaml validation is separate."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_architecture_domains.py"
SPEC = importlib.util.spec_from_file_location("architecture_domains_campaign", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class ArchitectureDomainsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contents = {"templates":campaign.TEMPLATES.read_bytes(),"architecture":campaign.CORPUS.read_bytes()}
        cls.corpora = {key:json.loads(value) for key,value in cls.contents.items()}
        cls.cases = {item["id"]:(corpus,item) for corpus in cls.corpora.values() for item in corpus["records"]}
        cls.negatives = {item["id"]:(corpus,item) for corpus in cls.corpora.values() for item in corpus["rejections"]}

    def raw(self, identity):
        corpus,case = self.cases[identity]
        return corpus["documents"][case["normalized"]]

    def test_exact_source_only_regeneration(self):
        rebuilt = campaign.partition_corpora(campaign.build_corpus())
        for key,corpus in rebuilt.items():
            campaign.check_corpus(corpus)
            self.assertEqual(campaign.encoded(corpus),self.contents[key])

    def test_full_case_input_and_expected_inventory(self):
        self.assertEqual((len(self.cases),len(self.negatives)),(65,192))
        for key,corpus in self.corpora.items():
            self.assertEqual(campaign.inventory(corpus),campaign.INVENTORIES[key])
            self.assertEqual({item["kind"] for item in corpus["records"]},set(corpus["coverage"]["record_kinds"]))
            self.assertEqual(len(corpus["coverage"]["construction_operations"]),14)

    def test_original_case_b_is_complete_at_every_layer(self):
        for variant in ("base","parameter-default","parameter-override"):
            original=json.loads((campaign.ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
            self.assertEqual(self.raw("request/case_b/"+variant),original)
            self.assertEqual(self.raw("library/case_b/"+variant),original["library"])
            self.assertEqual(self.raw("refinement/case_b/"+variant),original["library"]["refinements"][0])
            self.assertEqual(self.raw("template/case_b_source/"+variant),original["library"]["refinements"][0]["templates"][0])

    def test_all_fourteen_operations_and_real_request_conversions(self):
        corpus=self.corpora["templates"]
        self.assertEqual(len(corpus["conversions"]),25)
        schemas={step["operation"]["schema_version"] for item in corpus["conversions"] for step in corpus["documents"][item["template"]]["steps"]}
        self.assertEqual(sorted(schemas),corpus["coverage"]["construction_operations"])
        for item in corpus["conversions"]:
            request=campaign.CircuitConstructionRequest.from_dict(corpus["documents"][item["request"]])
            template=campaign.PayloadTemplate.from_dict(corpus["documents"][item["template"]])
            self.assertEqual(template.to_construction_request(request.circuit,mode=request.mode).to_dict(),request.to_dict())
            self.assertEqual(campaign.PayloadTemplate.from_construction_request(request,id="").to_dict(),template.to_dict())
            self.assertEqual(template.to_construction_request(request.circuit,id="",mode=request.mode).to_dict(),request.to_dict())

    def test_template_and_contextual_request_have_distinct_rules(self):
        helper=self.raw("template/helper_only")
        self.assertEqual(helper["requirements"][0]["category"],"delivered_helper")
        external=self.raw("template/source_independent_external_provider")
        self.assertEqual(external["requirements"][0]["external_id"],"undeclared-provider")
        self.assertEqual(self.raw("template/source_independent_compartment")["requirements"][0]["roles"][0]["compartment"],"undeclared-compartment")
        self.assertEqual(self.raw("template/payload_modality_is_contextual")["payload_structures"][0]["form"],"delivered_dna")
        self.assertIn("template/payload_structure_missing_member",self.negatives)
        circuit=campaign.CircuitConstructionRequest.from_dict(self.corpora["templates"]["documents"][self.corpora["templates"]["conversions"][0]["request"]]).circuit
        with self.assertRaises(campaign.SerializationError):
            campaign.PayloadTemplate.from_dict(helper).to_construction_request(circuit)

    def test_ordered_steps_and_selection_paths_preserved(self):
        template=self.raw("template/request/chain")
        self.assertEqual([step["id"] for step in template["steps"]],["step_A","step_B"])
        self.assertIn("template/forward_reference",self.negatives)
        self.assertIn("template/selection_frame_mismatch",self.negatives)
        source=self.raw("template/explicit_selection")
        self.assertEqual(source["steps"][0]["operation"]["input"]["path"]["spans"][0]["end"],1)

    def test_match_anchors_and_source_identity_are_explicit(self):
        self.assertEqual(self.raw("refinement/empty_match_anchors")["source_bindings"],{})
        self.assertIsNotNone(self.raw("refinement/empty_match_anchors")["match_policy"])
        self.assertEqual(len(self.raw("refinement/partial_match_anchors")["source_bindings"]),1)
        self.assertIn("refinement/missing_source_node",self.negatives)
        self.assertIn("refinement/noninjective_sources",self.negatives)
        self.assertEqual(len(self.raw("refinement/matched_maximum_id")["id"]),4000)
        self.assertEqual(len(self.raw("refinement/explicit_maximum_id")["id"]),4096)

    def test_structurally_legal_infeasible_alternatives_stay_representable(self):
        helper=self.raw("refinement/helper_cycle_structural")["helpers"][0]
        self.assertEqual(helper["depends_on"],[helper["id"]])
        channel=self.raw("refinement/zero_unknown_untyped_channel_structural")["channels"][0]
        self.assertEqual((channel["latency_seconds"],channel["persistence_seconds"],channel["failure_mode"]),(0,0,"unknown"))
        self.assertEqual(channel["initial_value"],{"supplied":"untyped structural declaration"})
        placements=self.raw("refinement/same_member_multiple_roles_structural")["placements"]
        self.assertEqual(len({item["recipient_role"] for item in placements}),2)
        self.assertEqual(self.raw("library/empty")["refinements"],[])
        self.assertEqual(self.raw("request/empty_library")["library"]["refinements"],[])
        self.assertIn("no model refinement",self.corpora["architecture"]["claim_scope"])

    def test_full_human_wrappers_are_never_flattened(self):
        expected={"behavior":"biocompiler.human_behavior_request.v0.1","deployment":"biocompiler.human_deployment_request.v0.1","acceptance":"biocompiler.human_acceptance_request.v0.1"}
        for kind,schema in expected.items():
            raw=self.raw("request/full_wrapped_"+kind)
            self.assertEqual(raw["circuit"]["profile"]["source_request"]["schema_version"],schema)
            decoded=campaign.PayloadArchitectureRequest.from_dict(raw)
            self.assertEqual(decoded.source.to_dict(),raw["circuit"]["profile"]["source_request"])
        self.assertIn("request/historical_not_source_authority",self.negatives)
        self.assertIn("request/dna_not_rna_profile",self.negatives)

    def test_full_component_identity_and_binding_coverage(self):
        self.assertIn("library/conflicting_component",self.negatives)
        self.assertEqual(len(self.raw("library/shared_exact_component")["refinements"]),2)
        self.assertEqual({ref["components"][0]["version"] for ref in self.raw("library/distinct_component_version")["refinements"]},{"1","2"})
        for identity in ("refinement/unbound_components","refinement/unbound_templates","refinement/binding_placement_wrong_template","refinement/unplaced_extra_template","refinement/output_duplicate_requirement","refinement/multiple_drivers"):
            self.assertIn(identity,self.negatives)

    def test_tampering_or_omission_fails_even_with_refreshed_manifest(self):
        for original in self.corpora.values():
            for change in (
                lambda corpus:corpus["records"].pop(),
                lambda corpus:corpus["rejections"][0].update(expected_code="accepted"),
                lambda corpus:corpus["records"][0].update(id="replacement"),
                lambda corpus:next(iter(corpus["documents"].values())).update(id="forged"),
            ):
                bad=deepcopy(original);change(bad);bad["inventory_sha256"]=campaign.inventory(bad)
                with self.assertRaises(AssertionError):campaign.check_corpus(bad)

    def test_each_full_fixture_is_bounded_and_portable(self):
        for key,corpus in self.corpora.items():
            campaign.check_corpus(corpus)
            self.assertLess(len(self.contents[key]),16*1024*1024)
            self.assertNotIn(b"/Users/",self.contents[key])
            self.assertNotIn(b"/home/runner/",self.contents[key])

if __name__=="__main__":unittest.main()
