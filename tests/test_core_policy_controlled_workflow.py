"""Inert transport peers only; these do not supply native/biological evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
from types import SimpleNamespace
import unittest

from biocompiler import core_policy_controlled_workflow as api
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse
from tests import test_core_policy_controlled_material as material
from tests import test_core_policy_controlled_behavior as behavior


def original():
    request = behavior.original()
    request['original']['budgets']['max_work'] = 100_000_000
    return {'schema_version': api.REQUEST_SCHEMA, 'behavior_request': request, 'limits': api._limits(request)}


def candidate(request):
    b = request['behavior_request']
    m = deepcopy(material.literal()['literal_candidate'])
    m['request_fingerprint'] = api._fingerprint(b['original'])
    return {'schema_version': api.CANDIDATE_SCHEMA, 'request_fingerprint': api._fingerprint(request),
            'material_candidate': m, 'behavior_candidate': behavior.candidate(b)}


def peer_result(request, proposal, operation):
    b = request['behavior_request']; raw = b['original']
    m = material.peer_result(raw, proposal['material_candidate'], material.api.PUBLISH)
    br = behavior.peer_result(b, proposal['behavior_candidate'])
    request_hash = api._fingerprint(request); candidate_hash = api._fingerprint(proposal)
    pins = {'request_fingerprint': request_hash, 'candidate_fingerprint': candidate_hash}
    pins['invocation_fingerprint'] = api._fingerprint(pins)
    flags = {'empirical_status': 'unassessed', 'human_use': 'unassessed', 'therapeutic_export': 'withheld'}
    report = {'schema_version': api.REPORT_SCHEMA, 'profile': api.admission.REQUEST_PROFILE,
        'implementation': 'biocompiler.ocaml.policy_controlled_workflow_check.v0.1', 'stage': 'joined',
        'status': api.ACCEPTED_STATUS, 'outcome': 'pass',
        'claim_scope': 'exact_supplied_two_member_rna_and_conditional_behavior_in_complete_finite_domain',
        **pins, 'material': m['report'], 'behavior': br['report'],
        'project_context': deepcopy(raw['source_authority']['project_context']),
        'limits': deepcopy(request['limits']), **{key: deepcopy(raw[key]) for key in ('context','resources','budgets')}, **flags}
    pins['report_fingerprint'] = api._fingerprint(report)
    artifact = None
    if operation == api.EXPORT:
        manifest = {'schema_version': api.MANIFEST_SCHEMA, 'stage': 'joined', 'request': deepcopy(request),
            'limits': deepcopy(request['limits']), 'candidate': deepcopy(proposal), 'report': deepcopy(report),
            **pins, 'members': deepcopy(m['artifact']['manifest']['members']), **flags}
        artifact = {'fasta': m['artifact']['fasta'], 'fasta_sha256': m['artifact']['fasta_sha256'],
                    'manifest': manifest, 'manifest_sha256': api._fingerprint(manifest)}
    return {'schema_version': api.RESULT_SCHEMA, 'implementation': api.IMPLEMENTATION,
        'resource_profile': api.admission.RESOURCE_PROFILE, 'validation_scope': api.VALIDATION_SCOPE,
        **pins, 'candidate': deepcopy(proposal), 'report': report, 'artifact': artifact,
        'usage': {'unit': 'logical_data_visits_and_child_semantic_work', 'preparation_charged_work': 200_000,
                  'request_decoding_work': 2_000, 'publication': 'requires_original_one_shot_frame_guard'}}


class Peer:
    def __init__(self, role='verify', mutate=None, profile=None):
        self.role=role; self.mutate=mutate; self.calls=[]
        self.profile=profile if profile is not None else (api.PRODUCER_PROFILE if role=='core' else api.PROFILE)
    def negotiate(self, operation, **kwargs):
        self.calls.append(('negotiate',operation))
        return SimpleNamespace(profiles={'policy_controlled_workflow':deepcopy(self.profile)}, validation_scopes=(api.VALIDATION_SCOPE,))
    def call(self, operation, payload, **kwargs):
        self.calls.append((operation,deepcopy(payload)))
        result=peer_result(payload['request'],payload.get('candidate',candidate(payload['request'])),operation)
        if self.mutate:self.mutate(result)
        return CoreResponse('peer',operation,'ok',result,(),self.role,CORE_VERSION)


def repin(result):
    result['report_fingerprint']=api._fingerprint(result['report'])
    if result['artifact'] is not None:
        pair=result['artifact'];manifest=pair['manifest']
        manifest['report']=deepcopy(result['report']);manifest['report_fingerprint']=result['report_fingerprint']
        pair['manifest_sha256']=api._fingerprint(manifest)


class ControlledWorkflowTransportTests(unittest.TestCase):
    def test_four_operations_preserve_complete_original_and_immutable_pair(self):
        request=original();proposal=candidate(request);core=Peer('core');verify=Peer()
        built=api.PolicyControlledWorkflowClient(core).compile(request)
        checked=api.PolicyControlledWorkflowClient(verify).check(request,proposal)
        replayed=api.PolicyControlledWorkflowClient(verify).replay(request,proposal,checked.report)
        exported=api.PolicyControlledWorkflowClient(verify).export(request,proposal)
        self.assertEqual(built.report,checked.report);self.assertEqual(checked.report,replayed.report)
        self.assertEqual(exported.status,api.ACCEPTED_STATUS)
        self.assertEqual(exported.artifact['manifest']['request'],request)
        self.assertEqual(exported.artifact['fasta'],material.literal()['expected']['fasta'])
        self.assertEqual([x[0] for x in verify.calls if x[0]!='negotiate'],[api.CHECK,api.REPLAY,api.EXPORT])
        exported.report['behavior']['status']='forged';exported.artifact['manifest']['request'].clear()
        self.assertEqual(exported.report['behavior']['status'],behavior.api.ACCEPTED_STATUS)
        with self.assertRaises(FrozenInstanceError):exported.operation='forged'

    def test_complete_limits_reject_every_mismatched_projection_before_launch(self):
        request=original()
        paths=[('horizon_tick',),('intervention_cutoff_tick',),('schema_version',)]
        paths += [(section,key) for section in ('budgets','domain_limits','resources') for key in request['limits'][section]]
        for path in paths:
            with self.subTest(path=path):
                altered=deepcopy(request);row=altered['limits']
                for key in path[:-1]:row=row[key]
                old=row[path[-1]];row[path[-1]]=old+1 if type(old)is int else 'changed'
                peer=Peer('core')
                with self.assertRaises(CoreProtocolError):api.PolicyControlledWorkflowClient(peer).compile(altered)
                self.assertEqual(peer.calls,[])

    def test_verify_cannot_compile_and_exact_capability_is_required(self):
        peer=Peer()
        with self.assertRaises(CoreProtocolError):api.PolicyControlledWorkflowClient(peer).compile(original())
        self.assertEqual(peer.calls,[])
        profile=deepcopy(api.PROFILE);profile['artifact']='structural_pair_only'
        peer=Peer(profile=profile)
        with self.assertRaises(CoreProtocolError):api.PolicyControlledWorkflowClient(peer).check(original(),candidate(original()))
        self.assertEqual(len(peer.calls),1)

    def test_repinning_nested_scope_verdict_or_authority_does_not_authorize_join(self):
        edits=[('material','behavior_status','checked'),('material','outcome','fail'),
               ('behavior','material_status','joined'),('behavior','evidence_status','unknown'),
               ('behavior','status','not_accepted'),('behavior','request_fingerprint','0'*64)]
        for child,key,value in edits:
            with self.subTest(child=child,key=key):
                def mutate(result):result['report'][child][key]=value;repin(result)
                with self.assertRaises(CoreProtocolError):
                    api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).export(original(),candidate(original()))

    def test_full_context_limits_and_empirical_flags_cannot_be_rewritten(self):
        paths=[('project_context','title'),('project_context','assumptions'),('limits','horizon_tick'),
               ('empirical_status',),('human_use',),('therapeutic_export',)]
        for path in paths:
            with self.subTest(path=path):
                def mutate(result):
                    row=result['report']
                    for key in path[:-1]:row=row[key]
                    row[path[-1]]='changed';repin(result)
                with self.assertRaises(CoreProtocolError):
                    api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).export(original(),candidate(original()))

    def test_every_pair_byte_and_full_member_order_are_bound(self):
        def fasta(result):
            p=result['artifact'];p['fasta']+='A';p['fasta_sha256']=hashlib.sha256(p['fasta'].encode()).hexdigest()
        def members(result):result['artifact']['manifest']['members'].reverse();repin(result)
        def limits(result):result['artifact']['manifest']['limits']['horizon_tick']+=1;repin(result)
        def original_change(result):result['artifact']['manifest']['request']['behavior_request']['readout_evidence']['freshness_ticks']+=1;repin(result)
        for mutate in (fasta,members,limits,original_change):
            with self.subTest(mutate=mutate.__name__),self.assertRaises(CoreProtocolError):
                api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).export(original(),candidate(original()))

    def test_compile_and_check_cannot_return_export_or_substitute_candidate(self):
        def artifact(result):result['artifact']=peer_result(original(),candidate(original()),api.EXPORT)['artifact']
        def substituted(result):result['candidate']['material_candidate']['request_fingerprint']='0'*64
        for mutate in (artifact,substituted):
            with self.subTest(mutate=mutate.__name__),self.assertRaises(CoreProtocolError):
                api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).check(original(),candidate(original()))

    def test_cumulative_work_and_report_publication_are_bounded(self):
        def work(result):result['usage']['preparation_charged_work']=original()['limits']['budgets']['max_work']+1
        def decoding(result):result['usage']['request_decoding_work']=result['usage']['preparation_charged_work']
        def separately_fitting(result):
            report=result['report']
            counts=[report['material']['admission']['domain_counters']['work'],
                report['behavior']['admission']['domain_counters']['work'],report['behavior']['domain']['counters']['work']]
            result['usage']['preparation_charged_work']=result['usage']['request_decoding_work']+max(counts)
        for mutate in (work,decoding,separately_fitting):
            with self.subTest(mutate=mutate.__name__),self.assertRaises(CoreProtocolError):
                api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).check(original(),candidate(original()))

    def test_rehashed_material_admission_cannot_replace_integer_horizon_with_float(self):
        def mutate(result):
            report=result['report']['material']['admission']['source_admission']
            report['horizon_ticks']=float(report['horizon_ticks']);repin(result)
        with self.assertRaises(CoreProtocolError):
            api.PolicyControlledWorkflowClient(Peer(mutate=mutate)).check(original(),candidate(original()))


if __name__=='__main__':unittest.main()
