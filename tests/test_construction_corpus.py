"""Integrity tests for the retained full construction declaration migration."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
PATH=Path(__file__).resolve().parents[1]/"tools/freeze_construction.py"
SPEC=importlib.util.spec_from_file_location("construction_corpus_under_test",PATH)
campaign=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)

class ConstructionCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=campaign.CORPUS.read_bytes()
        cls.corpus=json.loads(cls.content)
        cls.cases={item["id"]:item for item in cls.corpus["records"]}
    def document(self,identity):
        return self.corpus["documents"][self.cases[identity]["document_id"]]
    def test_exact_deterministic_authority_and_census(self):
        actual=campaign.build_corpus(); campaign.check_corpus(actual)
        self.assertEqual(campaign.encoded(actual),self.content)
        self.assertEqual((len(actual["records"]),len(actual["rejections"])),(72,245))
        self.assertEqual(len(actual["coverage"]["record_kinds"]),30)
        self.assertEqual(len(actual["coverage"]["operation_schemas"]),14)
    def test_complete_case_b_requests_remain_independently_pinned(self):
        for entry in self.corpus["coverage"]["case_b"]:
            raw=json.loads((campaign.ROOT/"tests/conformance/case-b"/entry["variant"]/"candidate.json").read_bytes())
            for key in entry["path"]: raw=raw[key]
            self.assertEqual(campaign.encoded(raw),campaign.encoded(self.document(entry["id"])))
        self.assertEqual(len(self.corpus["coverage"]["case_b"]),3)
    def test_operation_inventory_retains_multiplicity_branches_and_exact_assumptions(self):
        self.assertEqual(len(self.cases["operation/concatenate"]["expected"]["selections"]),2)
        self.assertEqual(len(self.cases["operation/multi_duplicate_selection"]["expected"]["selections"]),1)
        self.assertEqual(self.cases["operation/conditional_translation"]["expected"]["conditions"],
                         ["off_declared","on_declared","recoding_declared"])
        branches=self.document("operation/conditional_translation")["branches"]
        self.assertIsNone(branches[0]["policy"])
        self.assertIsNone(branches[0]["port_id"])
        self.assertIsNotNone(branches[0]["input"])
    def test_schema_declarations_preserve_unresolved_material_obligations(self):
        request=self.document("request/deferred_payload_structure")
        self.assertEqual(request["payload_structures"][0]["member_id"],"not_yet_materialized")
        self.assertNotIn("not_yet_materialized",{m["id"] for m in request["output_members"]})
        self.assertEqual(self.document("operation/circularization")["origin"],4)
        self.assertEqual(len(self.document("request/direct_root")["steps"]),0)
    def test_intended_dependency_mutations_reach_construction_boundary(self):
        for identity,child in (("step/chemistry_source","chemistry_transition"),("step/feature_source","feature_transition")):
            case=next(c for c in self.corpus["rejections"] if c["id"]==identity)
            raw=campaign.apply_edits(self.corpus["documents"][case["document_id"]],case["edits"])
            # Independent child parsing ensures this mutant rejects at the
            # operation-input authority boundary, not an invalid child schema.
            from biocompiler.ir.circuit_transitions import ChemistryTransition, FeatureTransition
            cls=ChemistryTransition if child=="chemistry_transition" else FeatureTransition
            cls.from_dict(raw["ports"][0][child])
            with self.assertRaisesRegex(campaign.SerializationError,"actual operation input"):
                campaign.C.TransformStep.from_dict(raw)
    def test_dropping_cases_and_rehashing_changed_expectations_fails(self):
        bad=deepcopy(self.corpus); bad["records"].pop()
        with self.assertRaisesRegex(AssertionError,"coverage count"): campaign.check_corpus(bad)
        bad=deepcopy(self.corpus); bad["records"][0]["expected"]["fingerprint"]="0"*64
        with self.assertRaisesRegex(AssertionError,"expectations differ"): campaign.check_corpus(bad)
        bad=deepcopy(self.corpus); bad["records"][1]["id"]=bad["records"][0]["id"]
        with self.assertRaisesRegex(AssertionError,"Duplicate"): campaign.check_corpus(bad)
    def test_native_wire_bounds_include_keys_and_full_deduplicated_corpus(self):
        pending=[(self.corpus,0)]; nodes=0; deepest=0
        while pending:
            value,depth=pending.pop(); nodes+=1; deepest=max(depth,deepest)
            if isinstance(value,dict): pending.extend((v,depth+1) for pair in value.items() for v in pair)
            elif isinstance(value,list): pending.extend((v,depth+1) for v in value)
        self.assertLess(nodes,250_000); self.assertLessEqual(deepest,128)
        self.assertLess(len(self.content),16*1024*1024)
        self.assertNotIn(b"/Users/",self.content)
    def test_all_constructor_default_fields_remain_mandatory_on_import(self):
        ids={case["id"] for case in self.corpus["rejections"]}
        self.assertTrue({"fields/selection/missing/path","fields/transcription/missing/mapping_profile",
                         "fields/request/missing/complex_members","fields/request/missing/amounts",
                         "fields/request/missing/payload_structures"}<=ids)

if __name__=="__main__": unittest.main()
