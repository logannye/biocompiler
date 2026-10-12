"""Inert literal transport peers only; these tests do not execute native semantics."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from biocompiler import core_policy_controlled_behavior as api
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse
from biocompiler.policy import controlled_behavior as sdk
from biocompiler.policy.controlled_material import ControlledCompositionRequest
from tests.test_core_policy_controlled_composition import peer_report

ROOT = Path(__file__).resolve().parents[1]


def original():
    return json.loads((ROOT/'core/test/data/policy_controlled_behavior_v01.json').read_text())


def candidate(request):
    raw=request['original'];source=raw['source_authority']
    primitives=[{'id':'encounter','op':'encounter_live'},
        *[{'id':name,'op':'physical_input','key':key} for name,key in
          [('antigen','antigen'),('controller','controller'),('protein-a','protein_a'),('protein-b','protein_b')]],
        {'id':'gate','op':'all'},
        {'id':'activity','op':'delayed_reversible',**raw['mechanism_model']['body']['delays'],
         'initial_band':'background','timer_scope':'executor','activation_scope':'encounter_generation'},
        {'id':'readout','op':'activity_band'}]
    wires=[{'from':a,'to':b,'input':c} for a,b,c in [('encounter','gate','live'),('antigen','gate','antigen'),
        ('controller','gate','controller'),('protein-a','gate','protein_a'),('protein-b','gate','protein_b'),
        ('gate','activity','enabled'),('activity','readout','band')]]
    return {'schema_version':api.CANDIDATE_SCHEMA,'request_fingerprint':api._fingerprint(request),
        'implementation':{'schema_version':'biocompiler.policy_controlled_activity_implementation.v0.1',
          'mechanism_model':deepcopy(raw['mechanism_model']),'control_contract':deepcopy(source['control_contract']),
          'semantics':deepcopy(source['document']['program']['semantics']),
          **{key:deepcopy(raw[key]) for key in ('catalog_binding','assembly','context','resources')},
          'primitives':primitives,'wires':wires}}


def peer_result(request, proposal):
    raw=request['original'];admission=peer_report(raw)
    admission['domain_counters']={'prefixes':21,'transitions':20,'histories':2,'work':100}
    source=admission['source_admission'];correspondence=source['correspondence']
    requirements=[]
    for row in source['requirements']:
        declaration=next(d['original'] for d in correspondence['declarations'] if d['id']==row['id'])
        definition=next(d['original'] for d in correspondence['definitions'] if d['reference']['id']==declaration['contract']['id'])
        requirements.append({**{key:row[key] for key in ('id','kind','source_path')},
            'original':deepcopy(declaration),'contract':deepcopy(definition),
            'pass':2,'fail':0,'unknown':0,'not_exercised':0})
    bindings=raw['assembly']['product_bindings']
    request_hash=api._fingerprint(request);candidate_hash=api._fingerprint(proposal)
    invocation_hash=api._fingerprint({'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash})
    report={'schema_version':api.REPORT_SCHEMA,'profile':api.admission.REQUEST_PROFILE,
        'implementation':'biocompiler.ocaml.policy_controlled_behavior_check.v0.1','stage':'behavior',
        'status':api.ACCEPTED_STATUS,'outcome':'pass',
        'claim_scope':'conditional_supplied_model_and_source_requirements_in_complete_finite_domain',
        'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash,'invocation_fingerprint':invocation_hash,
        'admission':admission,'source_correspondence':deepcopy(correspondence),
        'composition':{'rule':'two_executor_owned_availability_projections_into_one_reversible_activity',
            'modules':[{'member_id':b['member_id'],'product_parameter':b['product_parameter'],'assumptions':deepcopy(raw['context']),
                'input':'protein_a' if i==0 else 'protein_b','guarantee':'identity_projection_of_supplied_functional_availability',
                'biological_realization':'unassessed'} for i,b in enumerate(bindings)],
            'wires':deepcopy(proposal['implementation']['wires']),'controller_records':1,'observation_records':2,'timer_cells':3,'state_bits':4,
            'dependency_reconstruction':'pass','whole_program_crosscheck':'pass',
            'executable_authority':'complete_supplied_deterministic_delay_model',
            'component_definition_role':'declared_realization_dependencies_not_independent_executors'},
        'domain':{'completion':'complete','counters':deepcopy(admission['domain_counters']),'assessed_histories':2,'pending_at_horizon':False},
        'requirements':requirements,'coverage':{key:True for key in api._COVERAGE},
        'model_correspondence':'pass','evidence_status':'resolved',
        'availability':[{'member_id':b['member_id'],'scope':'executor','rna_absent_frames':2,'protein_absent_frames':2,
            'rna_unknown_evidence_frames':0,'protein_unknown_evidence_frames':0,
            'deployment_assumptions':'admitted_conditional_premises','physical_loss':'observed_in_domain','evidence_status':'resolved'} for b in bindings],
        'counterexample':None,'context':deepcopy(raw['context']),
        'assumptions':deepcopy(raw['source_authority']['project_context']['assumptions']),
        'resources':deepcopy(raw['resources']),'budgets':deepcopy(raw['budgets']),
        'material_status':'not_joined','empirical_status':'unassessed','human_use':'unassessed','therapeutic_export':'withheld'}
    return {'schema_version':api.RESULT_SCHEMA,'implementation':api.IMPLEMENTATION,'resource_profile':api.admission.RESOURCE_PROFILE,
        'validation_scope':api.VALIDATION_SCOPE,'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash,
        'invocation_fingerprint':invocation_hash,'candidate':deepcopy(proposal),'report_fingerprint':api._fingerprint(report),
        'report':report,'artifact':None,'usage':{'unit':'logical_data_visits_and_child_semantic_work','preparation_charged_work':100000,
            'request_decoding_work':1000,'publication':'requires_original_one_shot_frame_guard'}}


class Peer:
    def __init__(self,role='verify',mutate=None,profile=None):
        self.role=role;self.mutate=mutate;self.calls=[]
        self.profile=profile if profile is not None else (api.PRODUCER_PROFILE if role=='core' else api.PROFILE)
    def negotiate(self,operation,**kwargs):
        self.calls.append(('negotiate',operation))
        return SimpleNamespace(profiles={'policy_controlled_composition_behavior':deepcopy(self.profile)},validation_scopes=(api.VALIDATION_SCOPE,))
    def call(self,operation,payload,**kwargs):
        self.calls.append((operation,deepcopy(payload)))
        result=peer_result(payload['request'],payload.get('candidate',candidate(payload['request'])))
        if self.mutate:self.mutate(result)
        return CoreResponse('peer',operation,'ok',result,(),self.role,CORE_VERSION)


class ControlledBehaviorTransportTests(unittest.TestCase):
    def test_original_wrapper_is_immutable_closed_and_keeps_typed_original(self):
        raw=original();snapshot=sdk.ControlledBehaviorRequest.from_request(raw)
        self.assertEqual(snapshot.sha256,api._fingerprint(raw));self.assertEqual(snapshot.native_status,'not_performed')
        self.assertEqual(snapshot.original.to_request(),raw['original'])
        rebuilt=sdk.ControlledBehaviorRequest.from_original(ControlledCompositionRequest.from_request(raw['original']),readout_evidence=raw['readout_evidence'])
        self.assertEqual(rebuilt.to_request(),raw)
        raw['readout_evidence']['samples'][0]['status']='missing'
        self.assertEqual(snapshot.to_request()['readout_evidence']['samples'][0]['status'],'valid')
        with self.assertRaises(FrozenInstanceError):snapshot._json=b'{}'

    def test_typed_wrappers_route_all_three_exact_operations(self):
        raw=original();snapshot=sdk.ControlledBehaviorRequest.from_request(raw);proposal=candidate(raw)
        core=Peer('core');verify=Peer();built=sdk.construct_behavior(snapshot,client=api.PolicyControlledBehaviorClient(core))
        checked=sdk.check_behavior(snapshot,candidate=proposal,client=api.PolicyControlledBehaviorClient(verify))
        replayed=sdk.replay_behavior(snapshot,candidate=proposal,report=checked.report,client=api.PolicyControlledBehaviorClient(verify))
        self.assertEqual(built.result,checked.result);self.assertEqual(replayed.report,checked.report)
        self.assertEqual([r[0] for r in verify.calls if r[0]!='negotiate'],[api.CHECK,api.REPLAY])
        checked.candidate['request_fingerprint']='0'*64;checked.report['status']='forged'
        self.assertEqual(checked.status,api.ACCEPTED_STATUS);self.assertEqual(checked.candidate,proposal)
        self.assertIsNone(checked.artifact)
        with self.assertRaises(FrozenInstanceError):checked.operation='forged'

    def test_missing_stale_boolean_and_future_readout_authority_rejected(self):
        mutations=[lambda r:r.pop('readout_evidence'),lambda r:r['readout_evidence']['samples'].pop(),
            lambda r:r['readout_evidence'].update(freshness_ticks=True),
            lambda r:r['readout_evidence']['samples'][0].update(status='stale'),
            lambda r:r['readout_evidence']['samples'][0].update(status='missing'),
            lambda r:r['readout_evidence']['samples'][0].update(observed_tick=1),
            lambda r:r['readout_evidence']['samples'][0].update(tick=True),lambda r:r.update(extra={})]
        for mutate in mutations:
            raw=original();mutate(raw)
            with self.subTest(mutate=mutate),self.assertRaises((CoreProtocolError,ValueError)):
                sdk.ControlledBehaviorRequest.from_request(raw)
        raw=original();raw['readout_evidence']['samples'][3].update(status='missing',observed_tick=None)
        self.assertEqual(sdk.ControlledBehaviorRequest.from_request(raw).native_status,'not_performed')

    def test_verify_cannot_construct_or_accept_another_profile(self):
        peer=Peer()
        with self.assertRaises(CoreProtocolError):api.PolicyControlledBehaviorClient(peer).construct_behavior(original())
        self.assertEqual(peer.calls,[])
        for profile in ({},api.admission.PROFILE,api.PRODUCER_PROFILE):
            with self.subTest(profile=profile),self.assertRaises(CoreProtocolError):
                api.PolicyControlledBehaviorClient(Peer(profile=profile)).check_behavior(original(),candidate(original()))

    def test_rehashed_scope_counter_binding_and_omission_forgery_rejected(self):
        mutations=[lambda r:r.update(artifact={}),lambda r:r['report'].update(material_status='joined'),
            lambda r:r['report'].update(empirical_status='validated'),lambda r:r['report']['coverage'].update(active=False),
            lambda r:r['report']['coverage'].update(active=1),lambda r:r['report']['domain'].update(assessed_histories=True),
            lambda r:r['report']['domain']['counters'].update(histories=1),lambda r:r['report']['requirements'].pop(),
            lambda r:r['report']['requirements'][0].update(source_path='/other'),
            lambda r:r['report']['requirements'][0].update(**{'pass':1}),
            lambda r:r['report']['requirements'][0]['original'].update(id='foreign'),
            lambda r:r['report']['requirements'][0]['contract'].update(description='foreign'),
            lambda r:r['report']['composition'].update(timer_cells=True),
            lambda r:r['report']['composition']['modules'][0].update(member_id='foreign'),
            lambda r:r['report']['availability'][0].update(rna_unknown_evidence_frames=1),
            lambda r:r['report']['availability'][0].update(rna_absent_frames=23),
            lambda r:r['report']['source_correspondence']['declarations'].pop(),
            lambda r:r['report']['assumptions'].clear(),lambda r:r['report'].update(extra={}),
            lambda r:r['usage'].update(preparation_charged_work=10000001)]
        for mutate in mutations:
            def forge(result):
                mutate(result);result['report_fingerprint']=api._fingerprint(result['report'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api.PolicyControlledBehaviorClient(Peer(mutate=forge)).check_behavior(original(),candidate(original()))

    def test_unknown_counterexample_retains_complete_original_monitor_and_history(self):
        raw=original();raw['readout_evidence']['samples'][3].update(status='missing',observed_tick=None)
        proposal=candidate(raw);value=peer_result(raw,proposal);report=value['report']
        report.update(status='not_accepted',outcome='unknown',evidence_status='unknown')
        rows=[];definitions=report['source_correspondence']['definitions']
        for aggregate,authority in zip(report['requirements'],report['admission']['source_admission']['requirements']):
            aggregate.update(**{'pass':0,'unknown':2})
            reference=aggregate['original']['contract']
            definition=next(row for row in definitions if row['reference']['id']==reference['id'])
            rows.append({'id':aggregate['id'],'kind':aggregate['kind'],'source_path':aggregate['source_path'],
                'status':'unknown','deadline_ticks':authority['deadline_ticks'],'source_declaration':deepcopy(aggregate['original']),
                'contract':{'identity':reference['id'],'path':definition['source_path'],
                    'reference':deepcopy(reference),'body':deepcopy(aggregate['contract'])},'events':[]})
        trace=[];history=[]
        for tick in range(11):
            physical={key:True for key in ('antigen','controller','rna_a','rna_b','protein_a','protein_b')}
            physical['controller']=tick!=2
            if tick==5:
                for key in ('antigen','rna_a','rna_b','protein_a','protein_b'):physical[key]=False
            inputs={'tick':tick,'event':'start' if tick==0 else 'none','live':True,'generation':1,
                'generation_started_tick':0,'physical':physical,'evidence':{
                    key:{'status':'valid','observed_tick':tick,'generation':1 if key=='antigen' else None} for key in physical}}
            active=tick not in (0,3,6)
            sample={'tick':tick,'band':'active' if active else 'background','activation_generation':1 if active else None}
            trace.append({'input':deepcopy(inputs),'candidate':deepcopy(sample),'model_reference':deepcopy(sample),'corresponds':True})
            history.append({'input':inputs,'activity':sample,'readout_evidence':'missing' if tick==3 else 'valid',
                'qualified_gate':tick not in (2,5),'inputs_required':True})
        monitor={'schema_version':'biocompiler.policy_controlled_source_monitor.v0.1','profile':api.admission.REQUEST_PROFILE,
            'complete':True,'outcome':'unknown','horizon_ticks':10,'last_tick':10,'pending':False,
            'evidence_policy':'biocompiler.controlled_evidence.conservative.v0.1','requirements':rows,
            'coverage':deepcopy(report['coverage']),'evidence_gaps':[{'tick':3,'channel':'activity','status':'missing'}],'history':history}
        report['counterexample']={'history_index':1,'reduction':'none_complete_original_history',
            'model_correspondence':True,'pending_at_horizon':False,'deployment_evidence_unknown':False,'source_monitor':monitor,'trace':trace}
        value['report_fingerprint']=api._fingerprint(report)
        response=CoreResponse('peer',api.CHECK,'ok',value,(),'verify',CORE_VERSION)
        decoded=api._result(response,{'request':raw,'candidate':proposal})
        self.assertEqual(decoded.status,'not_accepted');self.assertEqual(decoded.report['outcome'],'unknown')
        mutations=[lambda r:r['counterexample']['trace'].pop(),
            lambda r:r['counterexample']['source_monitor']['requirements'][0]['contract'].update(identity='foreign'),
            lambda r:r['counterexample']['source_monitor']['history'][0]['activity'].update(band='active'),
            lambda r:r['counterexample']['source_monitor'].update(complete=1)]
        for mutate in mutations:
            altered=deepcopy(value);mutate(altered['report']);altered['report_fingerprint']=api._fingerprint(altered['report'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api._result(CoreResponse('peer',api.CHECK,'ok',altered,(),'verify',CORE_VERSION),{'request':raw,'candidate':proposal})

    def test_full_candidate_and_replay_report_substitution_rejected(self):
        def change(result):
            result['candidate']['implementation']['primitives'][6]['onset_ticks']=3
            result['candidate_fingerprint']=api._fingerprint(result['candidate'])
        with self.assertRaises(CoreProtocolError):api.PolicyControlledBehaviorClient(Peer(mutate=change)).check_behavior(original(),candidate(original()))
        raw=original();proposal=candidate(raw);saved=peer_result(raw,proposal)['report'];saved['coverage']['active']=False
        with self.assertRaises(CoreProtocolError):api.PolicyControlledBehaviorClient(Peer()).replay_behavior(raw,proposal,saved)


if __name__=='__main__':unittest.main()
