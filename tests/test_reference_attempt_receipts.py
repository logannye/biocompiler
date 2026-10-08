"""Mechanical complete-frame controls; no fabricated peer counts as native parity."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tests.test_pipeline_fixed_provider_campaign import Script
from tests.test_pipeline_manager_campaign import reframe
from tools import check_pipeline_manager_install as manager
from tools import reference_attempt_receipts as attempt


def reject(script, sequence):
    script.server('reply', {'sequence': sequence, 'request_sha256': manager.sha(script.bodies[sequence]),
        'outcome': {'status': 'rejected', 'value': {'module': 'biocompiler.compiler.pipeline',
            'type': 'PipelineError', 'message': "Completion profile 'exact_cds' is already registered.",
            'attributes': {}, 'attributes_tree': ['object', []]}}, 'closed': False})


def build(identity):
    return {'kind': 'molecular', 'build_id': identity, 'candidate': {'source': identity},
            'check_result': {}, 'result': {'artifact': identity}, 'construct': {'build_id': 'construct/1'}}


def fixture(directory, *, nested=False):
    """Framing and capability linkage only; deliberately not native accepted values."""
    receipt = {'_artifact_directory': directory, 'artifacts': {}, 'test_case': {'frames': []}}
    script = Script(receipt)
    initial = {key: None for key in script.application['operations']['initialize-reference']['fields']}
    initial.update(target_object={'handle': 'object/0'}, request_object={'handle': 'object/1'},
        registry_object={'handle': 'object/2'}, construct_manifests_object={'handle': 'object/3'},
        molecular_manifests_object={'handle': 'object/4'}, policy_objects={})
    script.reply(script.command('initialize-reference', initial), None)
    script.reply(script.command('finish-reference-construct', {'record_id': 'record/1', 'result_sequence': 1}),
        {'kind': 'construct', 'build_id': 'construct/1'})
    def prepare(number):
        token = 'reference-preparation/' + str(number)
        dependencies = [[key, 'identity/' + str(number) + '/' + str(index)] for index, key in enumerate(
            ('human_admission_policy', 'molecular_emitter', 'molecular_checker', 'molecular_profile', 'encoding_policy', 'molecular_pipeline'))]
        script.reply(script.command('prepare-reference-molecular', {}),
            {'preparation_id': token, 'dependencies': dependencies})
        for key, identity in dependencies:
            script.reply(script.command('set-dependency', {'key': key, 'identity': identity}), None)
        return token
    def profile(token):
        script.reply(script.command('reference-molecular-profile', {'preparation_id': token}), {'scope': 'exact_cds'})
        script.reply(script.command('register-completion-profile', {'profile': {'scope': 'exact_cds'}}), None)
    def registration(token, number):
        sequence = script.command('reference-molecular-registration', {'preparation_id': token})
        refs = []
        for offset, role in enumerate(attempt.ROLES):
            ref = {'handle': 'object/' + str(10 + number * 3 + offset)}
            script.invoke(sequence, 'reference-molecular-provider', {'preparation_id': token,
                'provider_id': 'provider/' + str(number * 3 + offset), 'role': role}, ref)
            refs.append(ref)
        script.reply(sequence, {'contract': {'id': 'construct_to_molecular'}, 'producer': refs[0],
            'validators': [[name, ref] for name, ref in zip(('sequence_identity', 'encoding_composition'), refs[1:])],
            'obligation_objects': []})
    def emit(token, number):
        sequence = script.command('call-native-provider', {'provider_id': 'provider/' + str(number*3), 'context_id': 'context/1'})
        script.invoke(sequence, 'reference-emit', {'preparation_id': token, 'provider_id': 'provider/' + str(number*3),
            'input': {'source': 'construct'}, 'argument': {'source': 'construct'}, 'tree': ['object', []]},
            {'kind': 'host', 'argument': {'handle': 'object/50'}, 'output': {'handle': 'object/51'}})
        script.invoke(sequence, 'reference-molecular-proposal', {'preparation_id': token,
            'output': {'handle': 'object/51'}, 'source_links': []}, {'handle': 'object/52'})
        script.reply(sequence, {'kind': 'host', 'object': {'handle': 'object/52'}})
    def finish(token, number):
        script.reply(script.command('finish-reference-molecular', {'preparation_id': token,
            'record_id': 'record/' + str(number+2), 'result_sequence': 1, 'upstream': None}), build('build/' + str(number)))
    def leave(token): script.reply(script.command(attempt.LEAVE, {'preparation_id': token}), None)
    outer = prepare(0); profile(outer); registration(outer, 0)
    if nested:
        # Nested scope is entered during an actual live callback, not in an
        # unrelated top-level command. The fixture asserts lifecycle only.
        seq = script.command('call-native-provider', {'provider_id': 'provider/0', 'context_id': 'context/1'})
        callback = script.begin(seq, 'reference-emit', {'preparation_id': outer, 'provider_id': 'provider/0',
            'input': {}, 'argument': {}, 'tree': ['object', []]})
        inner = prepare(1); profile(inner); registration(inner, 1); finish(inner, 1); leave(inner)
        script.end(callback, {'kind': 'native', 'argument': {'handle': 'object/50'}, 'output': None})
        script.reply(seq, {'kind': 'proposal'})
        finish(outer, 0); leave(outer)
    else:
        emit(outer, 0); finish(outer, 0); leave(outer)
        inner = prepare(1)
        script.reply(script.command('reference-molecular-profile', {'preparation_id': inner}), {'scope': 'exact_cds'})
        reject(script, script.command('register-completion-profile', {'profile': {'scope': 'exact_cds'}}))
        # An old saved proxy still owns the first immutable source roots.
        emit(outer, 0); leave(inner)
    script.reply(script.command('reference-build-result', {'kind': 'molecular'}), build('build/0'))
    script.reply(script.command('target', {}), None)
    script.close(); receipt['test_case']['frames'] = script.rows
    return receipt


def checked(receipt):
    details = {}
    channel, application = manager.declarations()
    manager.validate_frames(receipt['test_case']['frames'], manager.Artifacts(receipt['_artifact_directory'], receipt['artifacts']),
        channel, application, details=details, provider_calls=False, initializer='initialize-reference')
    return details


class ReferenceAttemptReceiptTests(unittest.TestCase):
    def test_complete_old_provider_and_added_cleanup_census(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(directory)
            details = checked(receipt)
            proof = attempt.validate([details])
            self.assertEqual(len(proof['attempts']), 2)
            self.assertEqual([len(row['writes']) for row in proof['attempts']], [6, 6])
            self.assertEqual(len(proof['lifecycle_commands']), 2)
            self.assertEqual(sum(row['operation'] == attempt.LEAVE for row in details['commands']), 2)
            self.assertTrue(all(row['classification'] == 'nonsemantic_native_attempt_scope_cleanup'
                                for row in proof['lifecycle_commands']))
            self.assertIn('original439operation', proof['scope'])

    def mutate(self, change, message, *, nested=False):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(directory, nested=nested)
            attempt.validate([checked(receipt)])
            reframe(receipt, receipt['test_case'], change)
            details = checked(receipt)  # Complete repaired frame/hash/counter proof must pass first.
            with self.assertRaisesRegex(AssertionError, message): attempt.validate([details])

    def test_repaired_provider_attempt_role_and_publication_binding_mutants(self):
        def invokes(values): return [row for row in values if row['kind']=='invoke' and row['action']=='reference-molecular-provider']
        mutations = [
            (lambda rows: invokes(rows)[0]['arguments'].update(preparation_id='reference-preparation/99'), 'attempt was rebound'),
            (lambda rows: invokes(rows)[0]['arguments'].update(role=attempt.ROLES[1]), 'publication order'),
            (lambda rows: next(row for row in rows if row['kind']=='continue').update(outcome={'status':'return','value':{'handle':'object/0'}}), 'aliases'),
            (lambda rows: next(row for row in rows if row['kind']=='invoke' and row['action']=='reference-emit')['arguments'].update(preparation_id='reference-preparation/1'), 'captured provider'),
            (lambda rows: next(row for row in rows if row['kind']=='invoke' and row['action']=='reference-emit')['arguments'].update(provider_id='provider/1'), 'captured provider'),
        ]
        for change, diagnostic in mutations:
            with self.subTest(diagnostic=diagnostic): self.mutate(change, diagnostic)
        def registration(rows):
            reply = next(row for row in rows if row['kind']=='reply' and row['outcome']['status']=='ok'
                and type(row['outcome']['value']) is dict and 'validators' in row['outcome']['value'])
            reply['outcome']['value']['producer'] = {'handle':'object/0'}
        self.mutate(registration, 'substituted its producer')

    def test_repaired_opaque_output_and_proposal_scope_mutants(self):
        for field, value in [('preparation_id','reference-preparation/1'),('output',{'handle':'object/99'})]:
            def change(rows, field=field, value=value):
                row=next(row for row in rows if row['kind']=='invoke' and row['action']=='reference-molecular-proposal')
                row['arguments'][field]=value
            self.mutate(change,'paired proposal')
        def changed_action(rows):
            row=next(row for row in rows if row['kind']=='invoke' and row['action']=='reference-molecular-proposal')
            row['action']='reference-proposal';del row['arguments']['preparation_id']
        self.mutate(changed_action,'paired proposal')

    def test_repaired_build_identity_content_and_last_completion(self):
        for field, value in [('build_id','build/1'),('candidate',{'source':'other'})]:
            def change(rows, field=field, value=value):
                sequence=next(row['sequence'] for row in rows if row['kind']=='command' and row['operation']=='reference-build-result')
                next(row for row in rows if row['kind']=='reply' and row['sequence']==sequence)['outcome']['value'][field]=value
            self.mutate(change, 'last completed|content was rebound')
        with tempfile.TemporaryDirectory() as directory:
            proof=attempt.validate([checked(fixture(directory,nested=True))])
            self.assertEqual([row['builds'] for row in proof['attempts']], [['build/0'],['build/1']])
        def creation_order(rows):
            sequence=next(row['sequence'] for row in rows if row['kind']=='command' and row['operation']=='reference-build-result')
            next(row for row in rows if row['kind']=='reply' and row['sequence']==sequence)['outcome']['value']=build('build/1')
        self.mutate(creation_order,'last completed',nested=True)

    def test_repaired_missing_extra_replayed_and_cancelled_cleanup(self):
        def leaves(rows):return [row for row in rows if row['kind']=='command' and row['operation']==attempt.LEAVE]
        def missing(rows):
            row=leaves(rows)[-1];row['operation']='target';row['arguments']={}
        self.mutate(missing,'omitted an attempt leave')
        def replay(rows):
            row=next(row for row in rows if row['kind']=='command' and row['operation']=='target')
            row['operation']=attempt.LEAVE;row['arguments']={'preparation_id':'reference-preparation/0'}
        self.mutate(replay,'active attempt')
        def wrong(rows):leaves(rows)[-1]['arguments']['preparation_id']='reference-preparation/0'
        self.mutate(wrong,'active attempt')
        def cancelled(rows):
            sequence=leaves(rows)[-1]['sequence']
            next(row for row in rows if row['kind']=='reply' and row['sequence']==sequence)['outcome']={'status':'raise','token':'exception/1'}
        self.mutate(cancelled,'exact lifecycle')
        def nested_wrong(rows):leaves(rows)[0]['arguments']['preparation_id']='reference-preparation/0'
        self.mutate(nested_wrong,'active attempt',nested=True)

    def test_repaired_dependency_cadence_and_fresh_capability(self):
        def order(rows):
            row=next(row for row in rows if row['kind']=='command' and row['operation']=='set-dependency')
            row['arguments']['identity']='different'
        self.mutate(order,'dependency write order')
        def reused(rows):
            seqs=[row['sequence'] for row in rows if row['kind']=='command' and row['operation']=='prepare-reference-molecular']
            next(row for row in rows if row['kind']=='reply' and row['sequence']==seqs[1])['outcome']['value']['preparation_id']='reference-preparation/0'
        self.mutate(reused,'capability was reused')


if __name__ == '__main__': unittest.main()
