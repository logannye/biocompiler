"""Complete local architecture declarations and independent authority witnesses."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('architecture_contracts_corpus',ROOT/'tools/freeze_architecture_contracts.py')
campaign=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)

class ArchitectureContractsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=campaign.CORPUS.read_bytes()
        cls.corpus=json.loads(cls.content)
        cls.by_id={x['id']:x for x in cls.corpus['records']}

    def test_all_twelve_schemas_reproduce_exactly_with_bounded_whole_fixture(self):
        rebuilt=campaign.build_corpus()
        self.assertEqual(campaign.encoded(rebuilt),self.content)
        self.assertEqual(tuple(len(rebuilt[k]) for k in ('records','rejections','literal_expectations')),(88,345,4))
        self.assertEqual(rebuilt['coverage']['record_kinds'],sorted(campaign.KINDS))
        self.assertLess(len(self.content),2_500_000)
        self.assertNotIn(str(ROOT).encode(),self.content)

    def test_all_control_helper_channel_and_product_variants_are_retained(self):
        self.assertEqual({x['normalized']['kind'] for x in self.corpus['records'] if x['kind']=='control'},set(campaign.CONTROL_KINDS))
        for availability in ('same_rna','other_rna','host','external'):
            for initialization in ('available_at_start','after_expression','after_trigger'):
                self.assertIn('helper/'+availability+'/'+initialization,self.by_id)
        self.assertEqual({x['normalized']['product']['kind'] for x in self.corpus['records'] if x['kind']=='output_binding'},
            {'protein_expression','mature_protein_quantity','reporter_fluorescence','biological_activity','rna_product'})
        self.assertEqual({x['normalized']['lifecycle']['mode'] for x in self.corpus['records'] if x['kind']=='output_binding'},
            {'production_control','abundance_control','activity_control','readout'})

    def test_structural_import_does_not_discharge_feasibility_or_pairing(self):
        helper=self.by_id['helper/cycle_and_insufficient_exclusive_capacity_retained']['normalized']
        self.assertIn(helper['id'],helper['depends_on'])
        self.assertGreater(len(helper['consumer_component_ids']),helper['capacity'])
        channel=self.by_id['base/channel']['normalized']
        self.assertEqual(channel['latency_seconds'],0)
        self.assertIsNone(channel['persistence_seconds'])
        self.assertEqual(channel['failure_mode'],'unknown')
        out=self.by_id['output/lifecycle_readout_contextual_pairing_deferred']['normalized']
        self.assertEqual(out['product']['kind'],'protein_expression')
        self.assertEqual(out['lifecycle']['mode'],'readout')
        self.assertEqual(self.by_id['literal/connection']['normalized']['producer_component_id'],'same')

    def test_zero_null_false_numeric_kinds_and_full_initial_json_remain_distinct(self):
        base=self.by_id['base/constraints']['normalized'];zero=self.by_id['constraints/zero_complete']['normalized']
        self.assertIsNone(base['exact_count']);self.assertFalse(base['require_complete'])
        self.assertEqual(zero['exact_count'],0);self.assertTrue(zero['require_complete'])
        initial=self.by_id['base/channel']['normalized']['initial_value']['nested'][-1]
        self.assertIs(type(initial['numeric']),float)
        self.assertEqual(campaign.canonical(initial['negative_zero']),'-0.0')
        self.assertFalse(self.by_id['literal/group']['normalized']['same_recipient'])

    def test_sorting_bounds_and_source_mapping_are_frozen(self):
        ordered=self.by_id['constraints/sorted_inventories_contextual_refs_deferred']
        for key in ('delivery_groups','control_requirements','deployment_requirements'):
            self.assertEqual([x['id'] for x in ordered['input'][key]],['z','a'])
            self.assertEqual([x['id'] for x in ordered['normalized'][key]],['a','z'])
        self.assertEqual(ordered['normalized']['preferred_refinement_ids'],['a','z'])
        self.assertEqual(len(self.by_id['binding/exact_name_inventory_limit']['normalized']['behavior_node_ids']),4096)
        self.assertEqual(len(self.by_id['instance/exact_mapping_limit']['normalized']['source_bindings']),4096)
        self.assertEqual(len(self.by_id['binding/unicode_byte_limit']['normalized']['id'].encode()),4096)

    def test_retained_case_b_authority_is_not_recreated(self):
        raw=json.loads((ROOT/'tests/conformance/case-b/base/request.json').read_bytes())
        refinement=raw['library']['refinements'][0]
        for kind,original in [('binding',refinement['bindings'][0]),('placement',refinement['placements'][0]),
            ('control',refinement['controls'][1]),('output_binding',refinement['output_contracts'][0]),
            ('delivery_group',raw['constraints']['delivery_groups'][0]),('constraints',raw['constraints'])]:
            self.assertEqual(campaign.canonical(self.by_id['retained_case_b/'+kind]['input']),campaign.canonical(original))

    def test_missing_or_substituted_cases_and_relabelled_failures_are_rejected(self):
        changed=deepcopy(self.corpus);changed['records'].pop();changed['coverage']=campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError,'Truncated'):campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed['records'][0]['id']='replacement'
        changed['case_ids_sha256'],changed['rejections_sha256'],changed['literals_sha256']=campaign.signature(changed)
        with self.assertRaisesRegex(AssertionError,'retained case'):campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed['rejections'][0]['expected_code']='unsupported_schema'
        changed['case_ids_sha256'],changed['rejections_sha256'],changed['literals_sha256']=campaign.signature(changed)
        with self.assertRaisesRegex(AssertionError,'retained case'):campaign.check_corpus(changed)

    def test_forged_authority_and_independent_literal_cannot_pass(self):
        changed=deepcopy(self.corpus);changed['records'][0]['normalized']['id']='forged'
        changed['records'][0]['fingerprint']=campaign.fingerprint(changed['records'][0]['normalized'])
        with self.assertRaisesRegex(AssertionError,'complete normalized'):campaign.check_corpus(changed)
        changed=deepcopy(self.corpus);changed['literal_expectations'][0]['normalized']['id']='forged'
        changed['case_ids_sha256'],changed['rejections_sha256'],changed['literals_sha256']=campaign.signature(changed)
        with self.assertRaisesRegex(AssertionError,'retained case'):campaign.check_corpus(changed)
        changed=deepcopy(self.corpus)
        item=next(x for x in changed['rejections'] if x['id']=='channel/same_role')
        item['input']['receiver_role']='different'
        with self.assertRaisesRegex(AssertionError,'Accepted negative'):campaign.check_corpus(changed)

    def test_check_only_does_not_create_missing_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'absent.json'
            with self.assertRaises(FileNotFoundError):campaign.main(['--check','--output',str(target)])
            self.assertFalse(target.exists())

if __name__=='__main__':unittest.main()
