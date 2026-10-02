"""Independent chemistry/annotation checker oracle and literal inventory."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from biocompiler.errors import SerializationError

PATH=Path(__file__).resolve().parents[1]/'tools/freeze_transition_check.py'
SPEC=importlib.util.spec_from_file_location('transition_check_corpus_under_test',PATH)
campaign=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class TransitionCheckCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=campaign.CORPUS.read_bytes()
        cls.corpus=json.loads(cls.content)
        cls.cases={item['id']:item for item in cls.corpus['cases']}
        cls.runtime={item['id']:item for item in cls.corpus['runtime_cases']}

    def test_complete_original_assertions_and_corpus_reproduce(self):
        rebuilt=campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt),self.content)
        self.assertEqual((len(rebuilt['cases']),len(rebuilt['parser_rejections']),len(rebuilt['runtime_cases'])),(125,6,11))
        self.assertEqual(rebuilt['coverage']['source_test_count'],33)
        self.assertEqual(rebuilt['coverage']['captured_calls'],86)
        self.assertEqual(campaign.inventory(rebuilt),campaign.EXPECTED_INVENTORY)

    def test_complete_literal_results_keep_unknown_and_contradiction_distinct(self):
        empty=self.cases['literal/empty']['expected']
        self.assertEqual(empty,dict(chemistry=None,features=[],diagnostics=['transition_derivation: Expected bounded participating source values.'],unsupported=[]))
        unknown=self.cases['literal/unknown']['expected']
        self.assertEqual(unknown['chemistry'],campaign.LITERAL_VALUE['chemistry'])
        self.assertEqual(unknown['diagnostics'],[])
        self.assertEqual(unknown['unsupported'],['unknown_output_chemistry: nominal chemistry remains incomplete'])
        changed=self.cases['literal/changed']['expected']
        self.assertIsNone(changed['chemistry'])
        self.assertEqual(changed['unsupported'],[])
        self.assertEqual(changed['diagnostics'],['chemistry_exact_inheritance: Exact chemistry inheritance requires unchanged spelling, alphabet and topology.'])

    def test_structural_import_failures_are_separate_from_resolution(self):
        for case in self.corpus['parser_rejections']:
            raw=self.corpus['documents'][case['document_id']]
            changed=deepcopy(raw);changed['derivation']=[]
            campaign.decode_call(changed)
            with self.assertRaises(SerializationError): campaign.decode_call(raw)
            self.assertEqual(case['expected_code'],'invalid_construction_artifact')
            self.assertTrue(case['legacy_result']['diagnostics'][0].startswith('transition_derivation:'))
        excluded=self.corpus['typed_unrepresentable']
        self.assertEqual(len(excluded),1)
        self.assertIn('Malformed foreign Python object',excluded[0]['reason'])
        self.assertIn("has no attribute 'chemistry'",excluded[0]['expected']['diagnostics'][0])

    def test_all_original_chemistry_contexts_retain_output_diagnostics(self):
        contexts=[item for key,item in self.cases.items() if key.startswith('chemistry_context/')]
        self.assertEqual(len(contexts),29)
        self.assertTrue(any(any(value.startswith('output_chemistry:') for value in item['expected']['diagnostics']) for item in contexts))
        unicode=self.cases['mutation/output_unicode']['expected']
        self.assertEqual(unicode['diagnostics'],['output_chemistry: Sequence must match the coordinate space and its canonical alphabet.'])
        self.assertIsNotNone(unicode['chemistry'])

    def test_runtime_boundaries_preserve_semantic_projection_limits(self):
        for kind in ('feature','modification','tail'):
            exact=self.runtime[f'runtime/{kind}/100000']['expected']
            self.assertEqual(exact['diagnostics'],[])
            self.assertEqual(exact['unsupported'],[])
            overflow=self.runtime[f'runtime/{kind}/100001']['expected']
            self.assertEqual(overflow['diagnostics'],[])
            self.assertTrue(any('projection_budget:' in value for value in overflow['unsupported']))
        self.assertEqual(self.runtime['runtime/copied_feature/100000']['expected']['unsupported'],
                         ['feature_projection_budget: source/feature: Projected residue limit exceeded.'])
        for kind,exact,overflow,message in (
            ('segments',4096,4097,'Invalid derivation segment inventory.'),
            ('path_blocks',2048,2049,'Derivation path-block limit exceeded.'),
        ):
            self.assertEqual(self.runtime[f'runtime/{kind}/{exact}']['expected']['diagnostics'],[])
            self.assertEqual(self.runtime[f'runtime/{kind}/{overflow}']['expected']['diagnostics'],['transition_derivation: '+message])

    def test_runtime_expansions_match_independent_declared_recipes(self):
        for case in self.runtime.values():
            chemistry,features,kwargs=campaign.runtime_call(case['recipe'])
            expanded=campaign.expand_runtime(case['template'])
            self.assertEqual(expanded,campaign.call_dict(chemistry,features,kwargs))
            self.assertEqual(campaign.run(expanded),case['expected'])
        self.assertNotIn(b'A'*1000,self.content)

    def test_case_reports_diagnostics_and_scope_pins_cannot_be_substituted(self):
        changed=deepcopy(self.corpus);changed['cases'][0]['id']='replacement';changed['inventory_sha256']=campaign.inventory(changed)
        with self.assertRaisesRegex(AssertionError,'inventory'): campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed['parser_rejections'][0]['expected_code']='invalid_type';changed['inventory_sha256']=campaign.inventory(changed)
        with self.assertRaisesRegex(AssertionError,'inventory'): campaign.check_corpus(changed)
        for key in campaign.EXPECTED_SECTIONS:
            changed=deepcopy(self.corpus)
            if isinstance(changed[key],list): changed[key].pop()
            else: changed[key]['case_count']=0
            with self.assertRaisesRegex(AssertionError,key+'|inventory'): campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed['cases'][0]['expected']['diagnostics']=['invented failure']
        with self.assertRaisesRegex(AssertionError,'complete transition result'): campaign.check_corpus(changed)

    def test_full_wire_document_is_bounded_and_checkout_independent(self):
        usage=campaign.check_corpus(self.corpus)
        self.assertLess(usage['bytes'],3_500_000)
        self.assertLess(usage['nodes'],130_000)
        self.assertLessEqual(usage['depth'],12)
        self.assertNotIn(str(campaign.ROOT).encode(),self.content)
        self.assertNotIn(b'/Users/',self.content)


if __name__=='__main__': unittest.main()
