"""Literal inert peers test transport integrity, never native admission evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from biocompiler import core_policy_controlled_composition as api
from biocompiler.core_client import CoreResponse, CoreProtocolError, CORE_VERSION
from biocompiler.core_policy import _semantic

ROOT = Path(__file__).resolve().parents[1]


def original():
    return json.loads((ROOT / 'core/test/data/policy_controlled_request_v014.json').read_text())


def peer_report(request):
    authority = request['source_authority']
    document = authority['document']
    program = document['program']
    definitions = program['semantics']['definitions']
    declarations = program['declarations']
    requirements = []
    deadlines = {'initial_activation':'onset_ticks','controller_cessation':'controller_off_ticks',
                 'antigen_cessation':'antigen_off_ticks','component_cessation':'component_off_ticks','reactivation':'reactivation_ticks'}
    for i,row in enumerate(declarations):
        if row['$type'] != 'Requirement': continue
        body = next(d for d in definitions if d['id'] == row['contract']['id'])
        kind = body['clauses'][0]['expression']['value'].removeprefix('biocompiler.controlled_source.').removesuffix('.v0.1')
        requirements.append({'id':row['id'],'kind':kind,'source_path':f'/document/program/declarations/{i}',
            'deadline_ticks':None if kind == 'no_unauthorized_activation' else authority['control_contract']['requested_deadlines'][deadlines[kind]]})
    source = {'schema_version':'biocompiler.policy_controlled_composition_source_admission.v0.1',
        'status':'source_admitted','profile':api.SOURCE_PROFILE,'document_fingerprint':api._fingerprint(_semantic(document)),
        'artifact_digest':api._fingerprint(document),'document':deepcopy(document),'horizon_ticks':request['operating_domain']['horizon_tick'],
        'requirements':requirements,'execution':'not_performed','material':'not_performed','empirical_status':'unassessed',
        'context_status':'supplied_not_realized','correspondence':{
            'declarations':[{'id':r['id'],'source_path':f'/document/program/declarations/{i}','source_index':i,'kind':r['$type'],'original':deepcopy(r)} for i,r in enumerate(declarations)],
            'definitions':[{'reference':{'$type':'DefinitionRef','id':r['id'],'version':r['version'],'digest':api._fingerprint(_semantic(r))},
                'source_path':f'/document/program/semantics/definitions/{i}','original':deepcopy(r)} for i,r in sorted(enumerate(definitions),key=lambda x:x[1]['id'])],
            'source_map':deepcopy(program['source_map'])}}
    model = request['mechanism_model']['body']; material=request['material_authority']
    return {'schema_version':api.REPORT_SCHEMA,'profile':api.REQUEST_PROFILE,'stage':'admission','status':'admitted',
        'claim_scope':'supplied_authority_and_complete_finite_domain_only','request_fingerprint':api._fingerprint(request),
        'source_fingerprint':api._fingerprint(document),'domain_fingerprint':api._fingerprint(request['operating_domain']),
        'material_fingerprint':api._fingerprint(material),'authority_inventory':{
            'definitions':len(definitions),'catalog_entries':len(document['implementations']['implementations']),
            'model_components':len(model['components']),'model_ports':len(model['ports']),'members':len(material['members']),
            'products':len(authority['control_contract']['products']),'roots':len(material['template']['sources']),
            'transforms':len(material['template']['steps']),'source_records':len(authority['project_context']['sources']),
            'empirical_assertions':len(request['context']['empirical_assertions'])},
        'domain_inventory':{k:len(request['operating_domain'][v]) for k,v in {'fixed_input_count':'fixed_inputs','physical_factor_count':'physical_factors','evidence_factor_count':'evidence_factors','lifecycle_factor_count':'lifecycle_factors'}.items()},
        'domain_counters':{'prefixes':12,'transitions':11,'histories':1,'work':100},'source_admission':source,
        'budgets':deepcopy(request['budgets']),'construction_status':'not_performed','behavior_status':'not_performed','empirical_status':'unassessed'}


def peer_result(request):
    report=peer_report(request)
    return {'schema_version':api.RESULT_SCHEMA,'implementation':api.IMPLEMENTATION,'resource_profile':api.RESOURCE_PROFILE,
        'validation_scope':api.VALIDATION_SCOPE,'request_fingerprint':api._fingerprint(request),
        'report_fingerprint':api._fingerprint(report),'report':report,'artifact':None,
        'usage':{'unit':'logical_data_visits_and_child_semantic_work','preparation_charged_work':10000,
                 'request_decoding_work':1000,'publication':'requires_original_one_shot_frame_guard'}}


class Peer:
    role='verify'
    def __init__(self, mutate=None, profile=None): self.mutate=mutate; self.profile=api.PROFILE if profile is None else profile
    def negotiate(self, operation, **kwargs):
        return SimpleNamespace(profiles={'policy_controlled_composition_admission':self.profile}, validation_scopes=(api.VALIDATION_SCOPE,))
    def call(self, operation, payload, **kwargs):
        result=peer_result(payload['request'])
        if self.mutate: self.mutate(result)
        return CoreResponse('peer',operation,'ok',result,(),'verify',CORE_VERSION)


class ControlledTransportTests(unittest.TestCase):
    def test_immutable_admission_only_result(self):
        request=original(); result=api.PolicyControlledCompositionClient(Peer()).admit(request)
        self.assertEqual(result.report['status'],'admitted')
        self.assertIsNone(result.result['artifact'])
        result.report['status']='forged'; request['profile']='changed'
        self.assertEqual(result.report['status'],'admitted')
        with self.assertRaises(FrozenInstanceError): result.operation='other'
        self.assertFalse(hasattr(api.PolicyControlledCompositionClient(Peer()), 'compile'))

    def test_negotiation_requires_exact_admission_capability(self):
        with self.assertRaises(CoreProtocolError): api.PolicyControlledCompositionClient(Peer(profile={})).admit(original())

    def test_rehashed_scope_correspondence_and_budget_tampering_rejected(self):
        mutations=[
            lambda r:r.update(artifact={'fasta':'forged'}),
            lambda r:r['report'].update(behavior_status='pass'),
            lambda r:r['report'].update(construction_status='checked_material'),
            lambda r:r['report'].update(empirical_status='validated'),
            lambda r:r['report'].update(source_fingerprint='0'*64),
            lambda r:r['report']['authority_inventory'].update(members=1),
            lambda r:r['report']['authority_inventory'].update(members=True),
            lambda r:r['report']['domain_counters'].update(histories=0),
            lambda r:r['report']['domain_counters'].update(prefixes=13),
            lambda r:r['report']['domain_counters'].update(histories=12),
            lambda r:r['report']['domain_counters'].update(work=9001),
            lambda r:r['report']['domain_counters'].update(work=1000001),
            lambda r:r['report']['budgets'].update(max_work=999999999),
            lambda r:r['report']['source_admission']['requirements'].pop(),
            lambda r:r['report']['source_admission']['correspondence']['declarations'].reverse(),
            lambda r:r['report']['source_admission']['correspondence']['definitions'][0].update(source_path='/wrong'),
            lambda r:r['report']['source_admission'].update(execution='pass'),
            lambda r:r['usage'].update(publication='complete_without_guard'),
            lambda r:r['usage'].update(preparation_charged_work=10000001),
        ]
        for mutation in mutations:
            def forged(result):
                mutation(result); result['report_fingerprint']=api._fingerprint(result['report'])
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                api.PolicyControlledCompositionClient(Peer(forged)).admit(original())

    def test_original_budget_bool_and_unknown_field_rejected(self):
        for key,value in [('max_work',True),('max_report_bytes',0)]:
            request=original();request['budgets'][key]=value
            with self.assertRaises(CoreProtocolError): api.PolicyControlledCompositionClient(Peer()).admit(request)
        request=original();request['candidate']={}
        with self.assertRaises(CoreProtocolError): api.PolicyControlledCompositionClient(Peer()).admit(request)

if __name__ == '__main__': unittest.main()
