"""Retained supplementary predicates preserve full source and unresolved duties."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import fingerprint
PATH=Path(__file__).resolve().parents[1]/'tools/freeze_circuit_bindings.py'
SPEC=importlib.util.spec_from_file_location('circuit_bindings_campaign',PATH)
campaign=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(campaign)
EXPECTED='eb5f4d4693cd8c1f1d722a9d56b89d4ea5df9ec0588ac351112b98377a4f3e32'

def validate(corpus):
    assert corpus['inventory_sha256']==campaign.inventory(corpus)==EXPECTED,'Binding inventory/signature drift'
    campaign.check_corpus(corpus)
    for item in corpus['rejections']:
        try: campaign.PayloadCircuitBinding.from_dict(corpus['documents'][item['document']])
        except SerializationError: pass
        else: raise AssertionError('Accepted intended binding import failure '+item['id'])
    return corpus

class CircuitBindingsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=campaign.CORPUS.read_bytes();cls.corpus=json.loads(cls.content)
        cls.checks={item['id']:item for item in cls.corpus['checks']}

    def test_rebuild_and_complete_pinned_census(self):
        rebuilt=validate(campaign.build_corpus())
        self.assertEqual(campaign.encoded(rebuilt),self.content)
        self.assertEqual(tuple(len(rebuilt[key]) for key in ('records','rejections','checks')),(5,31,53))

    def test_binding_codec_preserves_mapping_without_claiming_correspondence(self):
        literal=campaign.PayloadCircuitBinding.from_dict(campaign.LITERAL)
        self.assertEqual(literal.to_dict(),campaign.LITERAL)
        self.assertEqual(list(literal.signals),['a','z'])
        self.assertEqual(set(literal.signals.values()),{'same'})
        self.assertIn('unknown_field',{case['id'] for case in self.corpus['rejections']})
        maximum=next(case for case in self.corpus['records'] if case['id']=='maximum_mapping')
        self.assertEqual(len(self.corpus['documents'][maximum['normalized']]['signals']),256)

    def test_every_diagnostic_branch_and_error_precedence_has_literal_expectation(self):
        expected={x['id']:x['diagnostics'] for x in self.corpus['literal_expectations'] if 'diagnostics' in x}
        codes={value.split(':')[1] for values in expected.values() for value in values}
        self.assertEqual(codes,{'circuit_provider_mapping','circuit_binding_missing','circuit_source_action',
            'circuit_source_role_or_lineage','circuit_original_input_binding','circuit_source_product','circuit_lifecycle',
            'circuit_input_inventory','circuit_source_input_binding','circuit_guard_contradiction','circuit_temporal_or_input_refinement'})
        self.assertEqual(expected['eager/error_precedence/False'],['fail:circuit_source_input_binding:r'])
        self.assertEqual(expected['eager/error_precedence/True'],['unsupported:circuit_temporal_or_input_refinement:r'])
        self.assertEqual(expected['ordered_obligations'],['unsupported:circuit_provider_mapping:r:declared_host','unsupported:circuit_binding_missing:r'])

    def test_truth_table_rows_all_eight_inputs_and_scopes(self):
        for count in (1,2,8):
            for kind in ('and','or','not','signature'):
                case=self.checks[f'predicate/{count}/{kind}'];self.assertEqual(case['expected'],[])
                table=self.corpus['documents'][case['requirements'][0]]['behavior']['response']
                expected=[]
                for row in range(1<<count):
                    bits=[bool(row&(1<<(count-index-1))) for index in range(count)]
                    expected.append(any(bits) if kind=='or' else not all(bits) if kind=='not' else all(bits))
                self.assertEqual(table['outputs'],expected)
        for scope in ('internal','environment','contact'):
            self.assertEqual(self.checks['scope/'+scope]['expected'],[])
        self.assertEqual(self.checks['mapping/qualitative_ids']['expected'],[])

    def test_full_parameter_and_wrapper_authority_is_retained(self):
        for kind in ('default','override'):
            case=self.checks['parameter/'+kind]
            source=self.corpus['documents'][case['source']]
            self.assertEqual(source['resolved_bindings']['dwell']['value'],2 if kind=='default' else 3)
            self.assertEqual(case['expected'],['unsupported:circuit_temporal_or_input_refinement:r'])
            self.assertEqual(fingerprint(source),case['source_artifact_fingerprint'])
        for kind in ('behavior_request','deployment_request','acceptance_request'):
            case=self.checks['wrapper/'+kind];source=self.corpus['documents'][case['source']]
            self.assertNotEqual(source['schema_version'],'biocompiler.build_request.v0.1')
            self.assertEqual(case['expected'],['unsupported:circuit_binding_missing:supplementary'])
        for field in ('implementation_constraints','preferences'):
            case=self.checks['scope/'+field];source=self.corpus['documents'][case['source']]
            self.assertEqual(source[field],{'retained':True})
            self.assertIn('does not assess',self.corpus['compatibility']['scope'])

    def test_original_examples_remain_oracle_cases_without_acceptance_upgrade(self):
        cases=[x for x in self.checks.values() if x['id'].startswith('existing/')]
        self.assertEqual(len(cases),6)
        for case in cases:
            if any(marker in case['id'] for marker in ('temporal','memory','pulse')):
                self.assertEqual(case['expected'],['unsupported:circuit_temporal_or_input_refinement:response.0'])
            else: self.assertEqual(case['expected'],[])
        self.assertEqual(self.corpus['compatibility']['resource_profile'],'biocompiler.circuit_binding_check.resources.v1')
        self.assertEqual(self.corpus['compatibility']['max_output_bytes'],4000000)
        self.assertEqual(self.corpus['compatibility']['max_output_nodes'],100000)
        self.assertIn('circuit_binding_output_limit',self.corpus['compatibility']['native_difference'])
        self.assertIn('never partial success',self.corpus['compatibility']['native_difference'])

    def test_rehashed_missing_cases_or_changed_expected_diagnostics_are_detected(self):
        for group in ('records','rejections','checks','literal_expectations'):
            changed=deepcopy(self.corpus);changed[group].pop();changed['inventory_sha256']=campaign.inventory(changed)
            with self.assertRaisesRegex(AssertionError,'inventory'): validate(changed)
        changed=deepcopy(self.corpus);changed['checks'][0]['expected']=['wrong'];changed['inventory_sha256']=campaign.inventory(changed)
        with self.assertRaisesRegex(AssertionError,'inventory'): validate(changed)
        changed=deepcopy(self.corpus);next(iter(changed['documents'].values()))['forged']=True
        with self.assertRaises(AssertionError): validate(changed)

    def test_whole_fixture_bounded_including_keys_and_utf8(self):
        pending=[(self.corpus,0)];count=0;depth_max=0
        while pending:
            value,depth=pending.pop();count+=1;depth_max=max(depth_max,depth)
            if isinstance(value,dict): pending.extend((item,depth+1) for pair in value.items() for item in pair)
            elif isinstance(value,list): pending.extend((item,depth+1) for item in value)
            elif isinstance(value,str): self.assertLessEqual(len(value.encode()),4*1024*1024)
        self.assertLess(count,250000);self.assertLessEqual(depth_max,128);self.assertLess(len(self.content),16*1024*1024)

if __name__=='__main__':unittest.main()
