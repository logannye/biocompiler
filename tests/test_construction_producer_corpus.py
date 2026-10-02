"""Full original authority, exact proposals and independent fresh workflow replay."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('construction_producer_campaign',ROOT/'tools/freeze_construction_producer.py')
campaign=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(campaign)
DIGEST='191464d3a469fbedfacf6d9951104578054a531b917fd98e289962231fbcc1d6'

class ConstructionProducerCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.index,cls.docs=campaign.load()
    def case(self,fragment,group='constructions'):
        return next(row for row in self.index[group] if fragment in row['id'])
    def changed(self):return deepcopy(self.index),dict(self.docs)
    def repin(self,index):index['inventory_fingerprint']=campaign.inventory(index)
    def test_exact_inventory_all_file_bytes_and_read_budgets(self):
        self.assertEqual(campaign.inventory(self.index),DIGEST)
        self.assertEqual(self.index['inventory_fingerprint'],DIGEST)
        self.assertEqual(campaign.encoded(self.index),campaign.CORPUS.read_bytes())
        self.assertEqual(tuple(len(self.index[key]) for key in ('constructions','recodings','workflows','typed_boundaries','documents')),(61,37,88,4,172))
        total=len(campaign.encoded(self.index))
        for entry in self.index['documents']:
            raw=self.docs[entry['id']];data=campaign.encoded(raw);total+=len(data)
            self.assertEqual(campaign.fingerprint(raw),entry['id'])
            self.assertEqual((campaign.DOCUMENTS/(entry['id']+'.json')).read_bytes(),data)
            self.assertEqual(len(data),entry['bytes']);self.assertLessEqual(len(data),4_000_000)
            self.assertNotIn(b'/Users/',data);self.assertNotIn(b'/home/runner/',data)
        self.assertEqual(total,9_275_816);self.assertLess(total,16*1024*1024)
    def test_every_complete_candidate_and_typed_document_replays(self):
        campaign.check_corpus(self.index,self.docs,fresh=True)
    def test_every_recoding_operation_replays_all_staged_values_and_work(self):
        from biocompiler.backends.circuit_recoding import construct_recoding_step
        for row in self.index['recodings']:
            with self.subTest(case=row['id']):
                step=campaign.TransformStep.from_dict(self.docs[row['step']])
                available={item['id']:campaign.KINDS[item['kind']].from_dict(self.docs[item['document']]) for item in row['available']}
                values,used,diagnostic=construct_recoding_step(step,available,row['remaining_residues'])
                self.assertEqual(campaign.encoded([value.to_dict() for value in values]),campaign.encoded([self.docs[x] for x in row['values']]))
                self.assertEqual((used,diagnostic),(row['used_residues'],row['diagnostic']))
                if diagnostic:self.assertEqual(values,())
    def test_all_fresh_public_workflow_results_and_intended_errors(self):
        import biocompiler.compiler.circuit_construction as workflow
        for row in self.index['workflows']:
            with self.subTest(case=row['id']):
                request=campaign.CircuitConstructionRequest.from_dict(self.docs[row['request']])
                operation=getattr(workflow,row['operation'])
                def run():
                    if row['operation']=='build_circuit_construction':return operation(request)
                    build=campaign.CircuitConstructionBuild.from_dict(self.docs[row['build']])
                    return operation(build,expected_request=request)
                if row['expected_error']:
                    with self.assertRaises(campaign.SerializationError) as caught:run()
                    self.assertEqual(campaign.ERRORS[str(caught.exception)],row['expected_error'])
                else:self.assertEqual(campaign.encoded(run().to_dict()),campaign.encoded(self.docs[row['result']]))
        self.assertEqual(Counter(x['expected_error'] for x in self.index['workflows']),{None:61,'construction_build_authority':17,'construction_assessment_mismatch':5,'construction_handoff_incomplete':3,'construction_handoff_mode':2})
    def test_complete_original_case_b_authorities_and_candidates_are_exact(self):
        for variant in ('base','parameter-default','parameter-override'):
            original=json.loads((ROOT/'tests/conformance/case-b'/variant/'candidate.json').read_bytes())['construction']
            row=self.case('case_b/'+variant)
            for key in ('request','candidate'):
                self.assertEqual(campaign.encoded(self.docs[row[key]]),campaign.encoded(original[key]))
            self.assertEqual(self.docs[row['candidate']]['request_fingerprint'],row['request'])
    def test_original_assertion_ledger_actual_operations_and_call_inventory(self):
        ledger=self.index['coverage']['methods'];self.assertEqual(len(ledger),77)
        self.assertEqual([entry['method'] for entry in ledger],campaign.source_methods())
        self.assertEqual(sum('.test_' in entry['method'] for entry in ledger),71)
        calls=[row['id'] for group in ('constructions','recodings','workflows','typed_boundaries') for row in self.index[group]]
        self.assertEqual(len(calls),190);self.assertEqual(len(set(calls)),190)
        for entry in ledger:
            self.assertEqual(entry['status'],'source_assertions_executed')
            self.assertEqual(entry['retained_calls'],sum(identity.startswith(entry['method']+'/') for identity in calls))
        operations={step['operation']['schema_version'] for row in self.index['constructions'] for step in self.docs[row['request']]['steps']}
        self.assertEqual(sorted(operations),self.index['coverage']['operations']);self.assertEqual(len(operations),14)
        self.assertEqual(self.index['coverage']['exclusions'],[])
        self.assertIn('Python class misuse',self.index['compatibility']['source_only_boundaries'])
        self.assertEqual({row['error_type'] for row in self.index['typed_boundaries']},{'TypeError','SerializationError'})
    def test_independent_literal_residues_atomicity_and_attempted_work(self):
        row=self.case('test_four_primitives_match_literal_expected_strings');candidate=self.docs[row['candidate']]
        self.assertEqual({value['id']:value['sequence'] for value in candidate['values']},{'joined':'AACGUA','oriented':'TAACGT','selected':'AACG','transcript':'UAACGU'})
        changed=self.docs[self.case('test_source_change_reaches_output')['candidate']]
        self.assertEqual(next(value['sequence'] for value in changed['values'] if value['id']=='joined'),'AAGGUA')
        failed=self.docs[self.case('test_failed_materialization_still_consumes_attempted_work_budget')['candidate']]
        self.assertEqual(failed['values'],[])
        self.assertEqual(failed['diagnostics'],['member:helper:unavailable_value','member:payload:unavailable_value','step:bad:invalid_operation','step:good:residue_budget'])
        late=[row for row in self.index['recodings'] if 'test_multi_translation_drops_all_staged_products_on_late_failure' in row['id']]
        self.assertEqual(len(late),2)
        for row in late:self.assertEqual((row['values'],row['used_residues'],row['diagnostic']),([],4,'invalid_operation'))
        early=self.case('test_multi_translation_budget_is_reserved_before_any_translation','recodings')
        self.assertEqual((early['values'],early['used_residues'],early['diagnostic']),([],0,'residue_budget'))
    def test_replay_and_handoff_never_call_production(self):
        import biocompiler.compiler.circuit_construction as workflow
        row=next(row for row in self.index['workflows'] if row['operation']=='verified_circuit_molecules' and row['expected_error'] is None)
        request=campaign.CircuitConstructionRequest.from_dict(self.docs[row['request']]);build=campaign.CircuitConstructionBuild.from_dict(self.docs[row['build']])
        with patch.object(workflow,'construct_circuit_candidate',side_effect=AssertionError('replay called producer')):
            workflow.verify_circuit_construction(build,expected_request=request)
            actual=workflow.verified_circuit_molecules(build,expected_request=request)
        self.assertEqual(campaign.encoded(actual.to_dict()),campaign.encoded(self.docs[row['result']]))
    def test_rehashed_truncation_stale_coverage_and_bad_authority_fail_closed(self):
        for mutation,pattern in ((lambda i,d:i['constructions'].pop(),'Stale producer method call census|Stale producer case census'),
             (lambda i,d:i['coverage']['methods'][0].update(retained_calls=-1),'Stale producer method call census'),
             (lambda i,d:d.pop(next(iter(d))),'Missing/extra/duplicate producer documents'),
             (lambda i,d:i['coverage'].update(exclusions=['not tested']),'Unexecuted source assertion'),
             (lambda i,d:i['constructions'][0].update(request=i['constructions'][0]['candidate']),'Wrong producer authority kind')):
            index,docs=self.changed();mutation(index,docs);self.repin(index)
            with self.assertRaisesRegex(AssertionError,pattern):campaign.check_corpus(index,docs)
    def test_mutation_of_receipt_or_candidate_always_changes_complete_pin(self):
        index,_=self.changed();index['workflows'][0]['expected_error']='construction_assessment_mismatch'
        self.assertNotEqual(campaign.inventory(index),DIGEST)
        index,_=self.changed();index['constructions'][0]['final_residues']=0
        self.assertNotEqual(campaign.inventory(index),DIGEST)
        candidate=deepcopy(self.docs[self.index['constructions'][0]['candidate']]);candidate['diagnostics'].append('forged')
        self.assertNotEqual(campaign.fingerprint(candidate),self.index['constructions'][0]['candidate'])

if __name__=='__main__':unittest.main()
