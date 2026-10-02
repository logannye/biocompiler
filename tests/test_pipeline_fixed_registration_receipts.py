"""Full failed-workflow framing and independently repaired semantic controls.

The peer is deliberately fabricated. Passing these tests validates the receipt
checker, not an OCaml executable or installed migration acceptance.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_manager import _ordered
from tests.pipeline_fixed_registration_fixture import framed_fixture
from tests.test_pipeline_manager_campaign import reframe
from tools import check_pipeline_fixed_registration_install as gate


class RegistrationReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = gate.continuation.load_oracle(installed=False)
        cls.objects = []
        cls.original = gate.capture_original(oracle=cls.oracle, retain=cls.objects)
        cls.corpus = gate.Corpus()

    def fixture(self, directory, index=0):
        expected = self.corpus.cases[index]
        objects = next(value for value in self.objects if value['context'] == expected['context'])
        original = next(value for value in self.original['cases'] if value['context'] == expected['context'])
        receipt = {'_artifact_directory': str(directory), 'artifacts': {}}
        frames, actual, evidence = framed_fixture(receipt, self.corpus, expected, objects, original, self.oracle)
        row = {'frames': frames}
        receipt['checks'] = [row]
        return receipt, row, actual, evidence, expected, objects, original

    def details(self, receipt, row):
        details = {}
        channel, application = gate.manager.declarations()
        gate.manager.validate_frames(row['frames'],
            gate.manager.Artifacts(Path(receipt['_artifact_directory']), receipt['artifacts']),
            channel, application, details=details, provider_calls=False, initializer='initialize-synthetic')
        return details

    def validate(self, fixture):
        receipt, row, actual, evidence, expected, objects, original = fixture
        return gate.validate_case(self.corpus, expected, actual, evidence, self.details(receipt, row),
            self.oracle, {'request': objects['request'], 'config': None}, original)

    def rejected(self, mutate, diagnostic, *, index=0):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory, index)
            receipt, row, actual, evidence, *_ = fixture
            self.validate(fixture)
            reframe(receipt, row, lambda values: mutate(values, evidence, actual))
            # Byte hashes, request ownership, invocation stack, resource totals
            # and frame schemas must all pass before the semantic rejection.
            self.details(receipt, row)
            with self.assertRaises((AssertionError, CoreProtocolError)) as failure:
                self.validate(fixture)
            errors = []
            error = failure.exception
            while error is not None:
                errors.append(str(error)); error = error.__cause__
            self.assertRegex('\n'.join(errors), diagnostic)

    def test_all_three_complete_source_mutation_graphs_and_33_original_calls(self):
        results = []
        for index in range(3):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(directory, index)
                results.append(self.validate(fixture))
                evidence = fixture[3]
                self.assertEqual(len(evidence['events']), 11)
                self.assertEqual(evidence['events'][-1]['outcome'], 'raised')
                self.assertEqual(evidence['outer_error'], gate.ERROR)
        self.assertEqual(sum(value['events'] for value in results), 33)

    def test_native_phase_and_actual_command_authority_cannot_be_detached(self):
        for change, diagnostic in (
            ('dependency', 'original command arguments'),
            ('profile', 'prepared completion profile'),
            ('contract', 'prepared contract'),
            ('producer', 'actual native closure'),
            ('obligation', 'Native typed binding projection|obligation'),
        ):
            def mutate(values, evidence, _actual):
                commands = {v['sequence']: v for v in values if v['kind'] == 'command'}
                replies = {v['sequence']: v for v in values if v['kind'] == 'reply'}
                if change == 'dependency':
                    commands[evidence['events'][0]['sequence']]['arguments']['identity'] = '0'*64
                elif change == 'profile':
                    replies[evidence['profile_sequence']]['outcome']['value']['scope'] += '.forged'
                else:
                    registration = replies[evidence['registration_sequence']]['outcome']['value']
                    if change == 'contract': registration['contract']['version'] += '.forged'
                    elif change == 'producer': registration['producer'] = deepcopy(registration['validators'][0][1])
                    else: registration['obligation_objects'][0]['tree'] = ['object', []]
            with self.subTest(change=change): self.rejected(mutate, diagnostic)

    def test_direct_provider_context_role_and_complete_typed_proposal_are_bound(self):
        for change, diagnostic in (
            ('context', 'Nested original producer authority'),
            ('provider', 'Nested original producer authority'),
            ('role', 'role'),
            ('tree', 'projection|ordered|proposal'),
            ('source-alias', 'binding|origin|original mutation graph'),
        ):
            def mutate(values, evidence, _actual):
                command = next(v for v in values if v['kind'] == 'command' and v['sequence'] == evidence['producer_sequence'])
                reply = next(v for v in values if v['kind'] == 'reply' and v['sequence'] == evidence['producer_sequence'])
                proposal = reply['outcome']['value']
                if change == 'context': command['arguments']['context_id'] = 'context/999999'
                elif change == 'provider':
                    command['arguments']['provider_id'] = next(token for token in evidence['providers'] if token != command['arguments']['provider_id'])
                elif change == 'role': proposal['view']['role'] = 'behavior_to_synthetic.producer'
                elif change == 'tree': proposal['view']['tree'] = ['scalar', False]
                else:
                    alias = next(item for item in proposal['view']['aliases'] if item['binding']['kind'] == 'host')
                    prior = deepcopy(alias['binding'])
                    document = proposal['value']
                    for part in alias['paths'][0]: document = document[part]
                    replacement = {'kind': 'native', 'identity': 'view/999999', 'tree': _ordered(document)}
                    for item in proposal['view']['aliases']:
                        if item['binding'] == prior: item['binding'] = deepcopy(replacement)
            with self.subTest(change=change): self.rejected(mutate, diagnostic)

    def test_actual_changed_proposal_observations_and_original_error_are_bound(self):
        for change, diagnostic in (
            ('returned-object', 'consumed another callback result'),
            ('document-object', 'observation action/order/object'),
            ('primitive-result', 'primitive|observation|result'),
            ('link-authority', 'observation action/order/object'),
            ('error', 'actual native rejection'),
        ):
            def mutate(values, evidence, _actual):
                run = evidence['events'][-1]['sequence']
                actions = [v for v in values if v['kind'] == 'invoke' and v['command_sequence'] == run]
                if change == 'error':
                    next(v for v in values if v['kind'] == 'reply' and v['sequence'] == run)['outcome']['value']['message'] += ' forged'
                    return
                action = next(v for v in actions if v['action'] == {
                    'returned-object': 'call-provider', 'document-object': 'document',
                    'primitive-result': 'is-instance', 'link-authority': 'source-link-set-equal'}[change])
                if change in ('returned-object', 'primitive-result'):
                    continuation = next(v for v in values if v['kind'] == 'continue' and v['invocation_id'] == action['invocation_id'])
                    continuation['outcome']['value'] = {'handle': evidence['wrapper']['context']} if change == 'returned-object' else False
                elif change == 'document-object': action['arguments']['object'] = {'handle': evidence['wrapper']['context']}
                else: action['arguments']['expected'][0]['source_node_id'] += '.forged'
            # The map mutation has equal link cardinality and therefore executes
            # the original final set comparison; the duplicate case does not.
            index = next(i for i, case in enumerate(self.corpus.cases) if 'observation' in case['context'])
            with self.subTest(change=change): self.rejected(mutate, diagnostic, index=index)

    def test_historical_source_record_and_failed_state_cannot_be_fabricated(self):
        for change, diagnostic in (
            ('record-source', 'record|historical|source'),
            ('payload-binding', 'binding projection'),
            ('state', 'original|snapshot|manager'),
            ('graph', 'Complete actual mutation graph'),
        ):
            def mutate(values, evidence, actual):
                replies = {v['sequence']: v for v in values if v['kind'] == 'reply'}
                if change == 'graph':
                    actual['roots'] = []
                elif change == 'state':
                    dependencies = replies[evidence['completed']]['outcome']['value']['snapshot']['dependencies']
                    dependencies[next(iter(dependencies))] = '0'*64
                elif change == 'record-source':
                    raw = replies[evidence['upstream_sequence']]['outcome']['value']
                    raw['sources']['candidate']['bindings']['record_id'] = 'record/999999'
                else:
                    raw = replies[evidence['initial']]['outcome']['value']['record_definitions'][0]
                    raw['bindings']['payload']['tree'] = ['scalar', False]
            with self.subTest(change=change): self.rejected(mutate, diagnostic)

    def test_observation_reuse_and_event_intervals_remain_exact(self):
        for change in ('reuse-across-phase', 'reuse-without-before', 'after-is-before', 'wrong-event-owner'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(directory)
                self.validate(fixture)
                events = fixture[3]['events']
                if change == 'reuse-across-phase': events[8]['before_reused'] = True
                elif change == 'reuse-without-before': events[1]['before_reused'] = False
                elif change == 'after-is-before': events[-1]['after'] = events[-1]['before']
                else:
                    for field in ('sequence', 'start_frame', 'end_frame'):
                        events[0][field], events[1][field] = events[1][field], events[0][field]
                self.details(fixture[0], fixture[1])
                with self.assertRaises(AssertionError): self.validate(fixture)

    def test_nested_native_call_cannot_move_to_context_publication_callback(self):
        from tests.test_pipeline_fixed_initializer_receipts import resequence
        def mutate(values, evidence, _actual):
            command = next(value for value in values if value['kind'] == 'command'
                and value['sequence'] == evidence['producer_sequence'])
            first = values.index(command)
            last = next(index for index in range(first+1, len(values)) if values[index]['kind'] == 'reply'
                and values[index]['sequence'] == command['sequence'])+1
            chunk = values[first:last]
            del values[first:last]
            context = next(index for index, value in enumerate(values) if value.get('action') == 'hydrate-context')
            values[context+1:context+1] = chunk
            # The enclosing run has the same total frame count and keeps its
            # before/after interval; only the nested command's actual parent
            # changes. Rebuild every physical identity/hash around that move.
            resequence(values)
            evidence['producer_sequence'] = command['sequence']
        self.rejected(mutate, 'nested native producer call')


if __name__ == '__main__':
    unittest.main()
