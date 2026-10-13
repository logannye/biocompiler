"""Independent literal molecular input and inert transport peers, not native evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from biocompiler import core_policy_controlled_material as api
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse
from biocompiler.policy import controlled_material as sdk
from tests.test_core_policy_controlled_composition import original, peer_report

ROOT = Path(__file__).resolve().parents[1]


def literal():
    return json.loads((ROOT/'core/test/data/policy_controlled_material_v01.json').read_text())


def nominal_definition():
    # An independent literal report expectation, not the production reader's constant.
    return {'$type':'SemanticDefinition','id':'biocompiler.controlled.nominal_translation.v1',
        'version':'1','category':'model',
        'meaning':'Decode canonical parent RNA bases with the standard genetic code and one terminal stop; declared N1-methylpseudouridine at canonical U positions is projected to U for nominal sequence correspondence only. Physical translation of modified nucleotides, processing and biological expression remain unmeasured assumptions.',
        'parameters':[],'result':None,'clauses':[],'assumptions':[],
        'executor_kind':None,'subject_kind':None}


def nominal_original():
    request=original();definition=nominal_definition()
    document=request['source_authority']['document']
    document['program']['semantics']['definitions'].append(definition)
    reference={'$type':'DefinitionRef','id':definition['id'],'version':'1','digest':api._fingerprint(definition)}
    entry=request['catalog_binding']['entry'];entry['dependencies'].append(reference)
    selected=next(row for row in document['implementations']['implementations'] if row['id']==entry['id'])
    selected['dependencies'].append(deepcopy(reference))
    return request


def nominal_structure(structure, request):
    structure.update(schema_version='biocompiler.policy_controlled_nominal_structure_assessment.v0.1',
        profile='biocompiler.policy_controlled_nominal_structure.v0.1',
        implementation_version='biocompiler.ocaml.policy_controlled_nominal_structure_check.v0.1',
        claim_scope='exact_supplied_mrna_structure_under_explicit_controlled_nominal_translation_premise',
        source_request_fingerprint=api._fingerprint(request), nominal_translation_definition=nominal_definition(),
        physical_translation_status='unassessed')


def peer_result(request, candidate, operation):
    content=candidate['construction']; material=api._normalized_authority(request['material_authority'])
    construction_authority={'schema_version':'biocompiler.construction_content_authority.v0.1',
        'template':material['template'],'member_order':material['member_order']}
    structure={'schema_version':'biocompiler.policy_mrna_structure_assessment.v0.1',
        'profile':'biocompiler.policy_mrna_completeness.v0.1','implementation_version':'biocompiler.ocaml.policy_mrna_structure_check.v0.1',
        'claim_scope':'exact_supplied_mrna_structure_and_derivation_only','authority_fingerprint':api._fingerprint(material),
        'candidate_fingerprint':api._fingerprint(content),'content_reconstruction':{
            'schema_version':'biocompiler.construction_content_assessment.v0.1','implementation_version':'biocompiler.ocaml.construction_content_check.v0.1',
            'claim_scope':'exact_supplied_template_molecular_content','authority_fingerprint':api._fingerprint(construction_authority),
            'candidate_fingerprint':api._fingerprint(content),'reconstructed_fingerprint':api._fingerprint(content),'outcome':'pass',
            'context_status':'unassessed','payload_completeness':'unassessed','diagnostics':[]},
        'content_outcome':'pass','structural_outcome':'pass','outcome':'pass',
        'checked_clauses':['PM-02','PM-03','PM-04','PM-05','PM-06','PM-07','PM-09'],
        'PM-08_scope':'supplied_construction_region_chemistry_product_declaration_provenance_only',
        'unassessed_clauses':['PM-01','PM-08_external_component_binding','PM-10','PM-11','PM-12'],
        'members':[{'member':m['id'],'molecule_fingerprint':api._fingerprint(m),
             'product_identity':e['product']['identity'],'expected_product':e['product']['sequence'],
             'translated_product':e['product']['sequence']} for m,e in zip(content['inventory']['molecules'],material['members'])],
        'diagnostics':[],'context_status':'unassessed','implementation':'unassessed','policy':'unassessed','material_binding':'unassessed','export':'withheld'}
    request_hash=api._fingerprint(request); candidate_hash=api._fingerprint(candidate)
    invocation_hash=api._fingerprint({'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash})
    report={'schema_version':api.REPORT_SCHEMA,'profile':api.admission.REQUEST_PROFILE,
        'implementation':'biocompiler.ocaml.policy_controlled_material_check.v0.1','stage':'material',
        'status':api.ACCEPTED_STATUS,'outcome':'pass','claim_scope':'exact_supplied_two_member_rna_structure_only',
        'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash,'invocation_fingerprint':invocation_hash,
        'admission':peer_report(request),'structure':structure,'material_limits':{
            'member_order':['rna-a','rna-b'],'expected_member_order':['rna-a','rna-b'],
            'members':[{'member_id':x,'rna_nt':17,'within_limit':True} for x in ('rna-a','rna-b')],
            'max_member_rna_nt':request['resources']['max_member_rna_nt'],'total_rna_nt':34,
            'max_total_rna_nt':request['resources']['max_total_rna_nt'],'outcome':'pass'},
        'bindings':deepcopy(request['assembly']['product_bindings']),'context':deepcopy(request['context']),
        'resources':deepcopy(request['resources']),'budgets':deepcopy(request['budgets']),
        'behavior_status':'not_performed','empirical_status':'unassessed','human_use':'unassessed','therapeutic_export':'withheld'}
    result={'schema_version':api.RESULT_SCHEMA,'implementation':api.IMPLEMENTATION,'resource_profile':api.admission.RESOURCE_PROFILE,
        'validation_scope':api.VALIDATION_SCOPE,'request_fingerprint':request_hash,'candidate_fingerprint':candidate_hash,
        'invocation_fingerprint':invocation_hash,'candidate':deepcopy(candidate),'report_fingerprint':api._fingerprint(report),'report':report,'artifact':None,
        'usage':{'unit':'logical_data_visits_and_child_semantic_work','preparation_charged_work':100000,
                 'request_decoding_work':1000,'publication':'requires_original_one_shot_frame_guard'}}
    if operation==api.PUBLISH:
        fasta=literal()['expected']['fasta']
        manifest={'schema_version':api.MANIFEST_SCHEMA,'stage':'material','request':deepcopy(request),
            'candidate':deepcopy(candidate),'report':deepcopy(report),
            **{key:result[key] for key in ('request_fingerprint','candidate_fingerprint','invocation_fingerprint','report_fingerprint')},
            'members':[{'fasta_id':f'rna_{i:04d}','member_id':m['id'],'molecule':deepcopy(m),
                'sequence_sha256':hashlib.sha256(m['sequence'].encode()).hexdigest()}
                for i,m in enumerate(content['inventory']['molecules'],1)],
            'behavior_status':'not_performed','empirical_status':'unassessed','human_use':'unassessed','therapeutic_export':'withheld'}
        result['artifact']={'fasta':fasta,'fasta_sha256':hashlib.sha256(fasta.encode()).hexdigest(),
                            'manifest':manifest,'manifest_sha256':api._fingerprint(manifest)}
    return result


class Peer:
    def __init__(self, role='verify', mutate=None, profile=None):
        self.role=role; self.mutate=mutate; self.calls=[]
        self.profile=profile if profile is not None else (api.PRODUCER_PROFILE if role=='core' else api.PROFILE)
    def negotiate(self,operation,**kwargs):
        self.calls.append(('negotiate',operation))
        return SimpleNamespace(profiles={'policy_controlled_composition_material':deepcopy(self.profile)},validation_scopes=(api.VALIDATION_SCOPE,))
    def call(self,operation,payload,**kwargs):
        self.calls.append((operation,deepcopy(payload)))
        result=peer_result(payload['request'],payload.get('candidate',literal()['literal_candidate']),operation)
        if self.mutate: self.mutate(result)
        return CoreResponse('peer',operation,'ok',result,(),self.role,CORE_VERSION)


class ControlledMaterialTransportTests(unittest.TestCase):
    def test_nominal_profile_is_explicit_source_bound_and_works_in_joined_reader(self):
        request=nominal_original();candidate=literal()['literal_candidate']
        candidate['request_fingerprint']=api._fingerprint(request)
        def nominal_peer(result):
            nominal_structure(result['report']['structure'],request)
            result['report_fingerprint']=api._fingerprint(result['report'])
        result=api.PolicyControlledMaterialClient(Peer(mutate=nominal_peer)).check_material(request,candidate)
        self.assertEqual(result.report['structure']['physical_translation_status'],'unassessed')
        self.assertEqual(result.report['structure']['nominal_translation_definition'],nominal_definition())
        # Joined results use the same leaf reader and must not fall back to the old schema.
        from tests import test_core_policy_controlled_workflow as workflow
        joined=workflow.original();joined['behavior_request']['original']=request
        joined['limits']=workflow.api._limits(joined['behavior_request'])
        def nominal_joined(result):
            nominal_structure(result['report']['material']['structure'],request)
            workflow.repin(result)
        checked=workflow.api.PolicyControlledWorkflowClient(workflow.Peer(mutate=nominal_joined)).check(
            joined,workflow.candidate(joined))
        self.assertEqual(checked.report['material']['structure'],result.report['structure'])

    def test_nominal_report_cannot_drop_or_upgrade_premise_and_source_binding(self):
        request=nominal_original();candidate=literal()['literal_candidate']
        candidate['request_fingerprint']=api._fingerprint(request)
        mutations=[lambda s:s.update(schema_version='biocompiler.policy_mrna_structure_assessment.v0.1'),
            lambda s:s.update(profile='biocompiler.policy_mrna_completeness.v0.1'),
            lambda s:s.update(implementation_version='biocompiler.ocaml.policy_mrna_structure_check.v0.1'),
            lambda s:s.update(claim_scope='exact_supplied_mrna_structure_and_derivation_only'),
            lambda s:s.update(source_request_fingerprint='0'*64),
            lambda s:s.update(physical_translation_status='pass'),
            lambda s:s['nominal_translation_definition'].update(meaning='Physical translation established'),
            lambda s:s['nominal_translation_definition'].update(extra=True),
            lambda s:s.pop('source_request_fingerprint'),lambda s:s.pop('nominal_translation_definition'),
            lambda s:s.pop('physical_translation_status'),lambda s:s.update(extra=True)]
        for mutate in mutations:
            def forged(result):
                structure=result['report']['structure'];nominal_structure(structure,request);mutate(structure)
                result['report_fingerprint']=api._fingerprint(result['report'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api.PolicyControlledMaterialClient(Peer(mutate=forged)).check_material(request,candidate)
        # Even a fully rehashed ordinary report cannot erase a selected nominal premise.
        with self.assertRaises(CoreProtocolError):
            api.PolicyControlledMaterialClient(Peer()).check_material(request,candidate)

    def test_nominal_report_requires_unique_exact_definition_and_selected_dependency(self):
        def altered_body(request):
            body=request['source_authority']['document']['program']['semantics']['definitions'][-1]
            body['meaning']='Physical translation established'
            request['catalog_binding']['entry']['dependencies'][-1]['digest']=api._fingerprint(body)
        mutations=[lambda r:r['catalog_binding']['entry']['dependencies'].pop(),
            lambda r:r['catalog_binding']['entry']['dependencies'][-1].update(digest='0'*64),
            lambda r:r['catalog_binding']['entry']['dependencies'].append(deepcopy(r['catalog_binding']['entry']['dependencies'][-1])),
            lambda r:r['source_authority']['document']['program']['semantics']['definitions'].pop(),
            lambda r:r['source_authority']['document']['program']['semantics']['definitions'].append(nominal_definition()),
            altered_body]
        for mutate in mutations:
            request=nominal_original();mutate(request);candidate=literal()['literal_candidate']
            candidate['request_fingerprint']=api._fingerprint(request)
            def forged(result):
                nominal_structure(result['report']['structure'],request)
                result['report_fingerprint']=api._fingerprint(result['report'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api.PolicyControlledMaterialClient(Peer(mutate=forged)).check_material(request,candidate)

    def test_literal_oracle_and_immutable_result_round_trip(self):
        fixture=literal(); request=original(); candidate=fixture['literal_candidate']
        self.assertEqual(api._fingerprint(request),fixture['request_sha256'])
        self.assertEqual(api._fingerprint(candidate),fixture['candidate_sha256'])
        core=api.PolicyControlledMaterialClient(Peer('core')); verify=api.PolicyControlledMaterialClient(Peer())
        built=sdk.construct_material(request,client=core); checked=sdk.check_material(request,candidate=candidate,client=verify)
        self.assertEqual(built.result,checked.result)
        published=verify.publish_material(request,candidate)
        self.assertEqual(published.artifact['fasta'],fixture['expected']['fasta'])
        self.assertEqual(published.report['behavior_status'],'not_performed')
        published.candidate['construction']['member_order'].reverse()
        self.assertEqual(published.candidate,candidate)
        with self.assertRaises(FrozenInstanceError): published.operation='forged'
        self.assertFalse(hasattr(core,'compile'));self.assertFalse(hasattr(core,'export'))

    def test_verifier_never_constructs_and_capability_must_match_exactly(self):
        peer=Peer();client=api.PolicyControlledMaterialClient(peer)
        with self.assertRaises(CoreProtocolError):client.construct_material(original())
        self.assertEqual(peer.calls,[])
        for profile in ({},api.admission.PROFILE,api.PRODUCER_PROFILE):
            with self.subTest(profile=profile),self.assertRaises(CoreProtocolError):
                api.PolicyControlledMaterialClient(Peer(profile=profile)).check_material(original(),literal()['literal_candidate'])

    def test_rehashed_report_original_scope_and_material_tampering_rejected(self):
        mutations=[lambda r:r['report'].update(behavior_status='pass'),lambda r:r['report'].update(human_use='accepted'),
            lambda r:r['report'].update(therapeutic_export='permitted'),lambda r:r['report']['bindings'].reverse(),
            lambda r:r['report']['context'].update(recipient='foreign'),lambda r:r['report']['material_limits'].update(total_rna_nt=17),
            lambda r:r['report']['material_limits']['members'][1].update(within_limit=False),
            lambda r:r['report']['structure']['members'][1].update(translated_product='MA'),
            lambda r:r['report']['structure'].update(authority_fingerprint='0'*64),
            lambda r:r['report']['structure']['content_reconstruction'].update(reconstructed_fingerprint='0'*64),
            lambda r:r['report']['structure'].update(unassessed_clauses=[]),
            lambda r:r['report']['structure'].update(policy='pass'),
            lambda r:r['report']['admission']['source_admission']['correspondence']['declarations'].pop(),
            lambda r:r['report']['admission']['domain_inventory'].update(physical_factor_count=2),
            lambda r:r['report']['admission']['domain_counters'].update(work=99001),
            lambda r:r['usage'].update(publication='complete'),lambda r:r['usage'].update(preparation_charged_work=10**9),
            lambda r:r.update(artifact={'fasta':'foreign'}),lambda r:r['report'].update(extra=True)]
        for mutate in mutations:
            def forged(r):mutate(r);r['report_fingerprint']=api._fingerprint(r['report'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api.PolicyControlledMaterialClient(Peer(mutate=forged)).check_material(original(),literal()['literal_candidate'])

    def test_rehashed_manifest_and_fasta_tampering_rejected(self):
        mutations=[lambda a:a['manifest']['members'].reverse(),lambda a:a['manifest']['members'][1].update(molecule=a['manifest']['members'][0]['molecule']),
            lambda a:a['manifest']['request']['context'].update(extra=True),lambda a:a['manifest'].update(behavior_status='pass'),
            lambda a:a.update(fasta=a['fasta'].replace('GCU','GGU')),lambda a:a['manifest']['members'].pop()]
        for mutate in mutations:
            def forged(r):
                a=r['artifact'];mutate(a);a['fasta_sha256']=hashlib.sha256(a['fasta'].encode()).hexdigest();a['manifest_sha256']=api._fingerprint(a['manifest'])
            with self.subTest(mutate=mutate),self.assertRaises(CoreProtocolError):
                api.PolicyControlledMaterialClient(Peer(mutate=forged)).publish_material(original(),literal()['literal_candidate'])

    def test_coherent_rejection_retains_complete_report_and_no_artifact(self):
        def reject(r):
            report=r['report'];structure=report['structure']
            structure.update(structural_outcome='fail',outcome='fail',diagnostics=[{'clause':'PM-04','member':'rna-b','severity':'fail','code':'complete_product_spelling_mismatch'}])
            structure['members'][1]['translated_product']='MA'
            report.update(status='not_accepted',outcome='fail');r['report_fingerprint']=api._fingerprint(report);r['artifact']=None
        result=api.PolicyControlledMaterialClient(Peer(mutate=reject)).publish_material(original(),literal()['literal_candidate'])
        self.assertEqual(result.status,'not_accepted');self.assertIsNone(result.artifact)

    def test_changed_supplied_candidate_cannot_be_replaced_by_a_peer(self):
        def substitute(r):
            r['candidate']['construction']['diagnostics']=['changed'];r['candidate_fingerprint']=api._fingerprint(r['candidate'])
        with self.assertRaises(CoreProtocolError):
            api.PolicyControlledMaterialClient(Peer(mutate=substitute)).check_material(original(),literal()['literal_candidate'])


if __name__=='__main__':unittest.main()
