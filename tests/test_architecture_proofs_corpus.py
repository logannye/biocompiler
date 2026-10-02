"""Complete pinned theorem inputs and source-oracle regression inventory."""
from copy import deepcopy
import json
import unittest
from tools import freeze_architecture_proofs as f

PINS={'controls':('3281755936e663372e4091d3b7f9212ca886e66d69b37d3a1b42afeea42412c4',112,89),
      'deployment':('a602b00a7dbb7f614dd6f577fa32b1da4215ffdf93d1e0dcd5452134f711e001',30,36)}
class ArchitectureProofCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.corpora={k:json.loads(p.read_bytes()) for k,p in f.PATHS.items()}
    def test_full_inputs_and_expected_results_replay(self):
        for c in self.corpora.values():f.verify(c)
    def test_exact_inventory_pins_and_census(self):
        for kind,c in self.corpora.items():
            sha,cases,documents=PINS[kind];self.assertEqual((f.inventory(c),len(c['cases']),len(c['documents'])),(sha,cases,documents))
    def test_regeneration_is_host_independent(self):
        for kind,build in [('controls',f.build_controls),('deployment',f.build_deployment)]:self.assertEqual(f.encoded(build()),f.PATHS[kind].read_bytes())
    def test_explicit_helper_resource_profile(self):
        profile=self.corpora['controls']['native_boundary']
        self.assertEqual((profile['controls_max_source_nodes'],profile['controls_max_controllers'],profile['controls_max_expression_depth']),(4096,4096,512))
    def test_all_existing_functional_control_assertions_run(self):
        c=self.corpora['controls'];self.assertEqual(c['coverage']['legacy_assertion_tests'],28)
        self.assertEqual(set(c['coverage']['theorem_kinds']),{'activation','shutdown','memory_reset','production_adjustment','activity_control','physical_separation','dependency_disjointness'})
    def test_default_and_explicit_empty_bindings_are_distinct(self):
        c=self.corpora['controls'];self.assertTrue(any(x['parameter_bindings']=={} and x['expected']['reason']=='unbound_parameter' for x in c['cases']))
        self.assertTrue(any(x['parameter_bindings'] is None and x['expected']['reason'] is None for x in c['cases']))
    def test_decimal_boundaries_use_exact_rational_witnesses(self):
        by_id={x['id']:x for x in self.corpora['deployment']['cases']}
        self.assertEqual(by_id['decimal_exact']['expected']['failures'],[])
        self.assertTrue(all('common_window_insufficient' in x for x in by_id['decimal_real_gap']['expected']['failures']))
        self.assertEqual(by_id['decimal_exact']['expected']['witnesses'][0]['earliest_end'],{'numerator':3,'denominator':10})
    def test_historical_mapping_projection_is_explicit(self):
        by_id={x['id']:x for x in self.corpora['deployment']['cases']}
        self.assertEqual(by_id['cached_lie']['expected']['failures'],[])
        self.assertTrue(by_id['duplicate_window_last_wins']['expected']['failures'])
        self.assertIn('deployment_clock_mismatch',by_id['wrong_clock']['expected']['failures'][0])
    def test_changed_expectation_cannot_pass_rehashed_corpus(self):
        c=deepcopy(self.corpora['controls']);c['cases'][0]['expected']['reason']='forged';c['inventory_sha256']=f.inventory(c)
        with self.assertRaises(AssertionError):f.verify(c)
    def test_missing_case_cannot_preserve_pinned_inventory(self):
        c=deepcopy(self.corpora['deployment']);c['cases'].pop();self.assertNotEqual(f.inventory(c),PINS['deployment'][0])
    def test_no_host_paths_and_all_three_case_b_bindings(self):
        for c in self.corpora.values():self.assertNotIn('/Users/',f.encoded(c).decode())
        ids={x['id'] for x in self.corpora['deployment']['cases']}
        self.assertTrue({'case_b/base','case_b/parameter-default','case_b/parameter-override'}<=ids)
if __name__=='__main__':unittest.main()
