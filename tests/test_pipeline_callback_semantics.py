"""Original callable comparisons, exact live effects and immutable oracle pins."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.capture_pipeline_callback_semantics import ROOT, canonical, capture, sha

PATH = ROOT / 'tests/conformance/pipeline-callback-semantics-v1.json'
INVENTORY_PIN = '81462d7732ba6205791831030b21ebcbaa3f8d4c58837deb38d072b3e1025d45'


def validate(value):
    content = {key: item for key, item in value.items() if key != 'inventory_fingerprint'}
    if value.get('inventory_fingerprint') != INVENTORY_PIN or sha(canonical(content)) != INVENTORY_PIN:
        raise AssertionError('Original callback semantics inventory changed')


class PipelineCallbackSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = PATH.read_bytes()
        cls.value = json.loads(cls.raw)
        validate(cls.value)
        cls.cases = {item['id']: item for item in cls.value['cases']}

    def events(self, identity, *, kind=None, top=False):
        return [event for event in self.cases[identity]['events']
                if (kind is None or event['kind'] == kind) and (not top or event['parent'] is None)]

    def comparisons(self, identity):
        return [(event['recipe']['left'], event['recipe']['right'])
                for event in self.events(identity, kind='comparison')]

    def test_complete_original_execution_reproduces_every_byte_and_source(self):
        self.assertEqual(self.raw, canonical(self.value) + b'\n')
        self.assertEqual(canonical(capture()) + b'\n', self.raw)
        self.assertEqual(self.value['coverage'], {
            'cases': 34, 'manager_events': 78, 'comparison_events': 28, 'raised_events': 18})
        for path, pin in self.value['source_files'].items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        self.assertEqual(len(self.cases), 34)
        for case in self.cases.values():
            events = case['events']
            self.assertEqual([event['id'] for event in events], list(range(len(events))))
            self.assertEqual([event['recipe'] for event in events if event['parent'] is None], case['actions'])
            for event in events:
                if event['parent'] is not None:
                    self.assertLess(event['parent'], event['id'])
                self.assertEqual(set(event) - {'result', 'error'},
                    {'id', 'parent', 'kind', 'recipe', 'before', 'after', 'outcome'})
                self.assertEqual(('result' in event, 'error' in event),
                                 (event['outcome'] == 'returned', event['outcome'] == 'raised'))
            self.assertEqual(events[0]['before'], case['initial_state'])
            self.assertEqual([event for event in events if event['parent'] is None][-1]['after'], case['final_state'])

    def test_identity_shortcuts_bound_methods_and_self_certification_remain_distinct(self):
        for mode in ('pass', 'admission'):
            identity = mode + ':identity_shortcut'
            self.assertEqual(self.comparisons(identity), [])
            self.assertTrue(all(event['outcome'] == 'returned' for event in self.events(identity)))
            bound = mode + ':bound_method_equivalent'
            self.assertEqual(self.comparisons(bound), [])
            self.assertTrue(all(event['outcome'] == 'returned' for event in self.events(bound)))
            self.assertEqual(self.cases[bound]['providers']['old'], self.cases[bound]['providers']['new'])
            self.assertNotEqual(self.cases[bound]['actions'][0]['validators'], self.cases[bound]['actions'][1]['validators'])
            ordinary = self.events(mode + ':default_identity_distinct', top=True)
            self.assertEqual(ordinary[-1]['outcome'], 'raised')
            self.assertEqual(ordinary[-1]['before'], ordinary[-1]['after'])
        self.assertEqual(self.events('pass:same_callable_cannot_self_certify')[-1]['error']['message'],
                         'Candidate generation cannot certify itself.')
        for identity in ('pass:distinct_callable_roles_skip_equality', 'pass:distinct_equal_bound_method_roles'):
            self.assertEqual(self.comparisons(identity), [])
            self.assertEqual(self.events(identity)[-1]['outcome'], 'returned')
        changed = 'pass:bound_producer_identity_change'
        self.assertEqual(self.comparisons(changed), [])
        self.assertEqual(self.events(changed)[-1]['error']['message'],
                         'Changed pass/check providers must increment the contract version.')

    def test_rich_equality_dispatch_false_and_exceptions_are_original_observations(self):
        for mode in ('pass', 'admission'):
            self.assertEqual(self.comparisons(mode + ':equal'), [('old', 'new')])
            self.assertEqual(self.events(mode + ':equal', kind='comparison')[0]['result'], True)
            self.assertEqual(self.events(mode + ':unequal', kind='comparison')[0]['result'], False)
            raised = self.events(mode + ':raises')
            self.assertEqual(raised[-1]['error'], {'module': 'builtins', 'type': 'ValueError',
                                                  'message': 'Original comparator rejected old'})
            self.assertEqual(raised[1]['error'], raised[-1]['error'])
            reflected = mode + ':reflected_not_implemented'
            self.assertEqual(self.comparisons(reflected), [('old', 'new'), ('new', 'old')])
            self.assertEqual(self.events(reflected, kind='comparison')[0]['result'],
                             {'python_singleton': 'NotImplemented'})
            self.assertEqual(self.comparisons(mode + ':subclass_reflection'), [('new', 'old')])

    def test_dictionary_iteration_and_short_circuit_use_previous_mapping_order(self):
        for mode in ('pass', 'admission'):
            identity = mode + ':comparison_order'
            case = self.cases[identity]
            self.assertEqual(self.comparisons(identity), [('old_second', 'new_second'), ('old_first', 'new_first')])
            self.assertEqual([item[0] for item in case['actions'][0]['validators']][0], 'second_check')
            self.assertNotEqual(case['actions'][0]['validators'][0][0], case['actions'][1]['validators'][0][0])
            self.assertNotEqual(case['setup']['contracts']['first']['checks'][0]['id'], 'second_check')
            short = mode + ':comparison_short_circuit'
            self.assertEqual(self.comparisons(short), [('old_second', 'new_second')])
            self.assertEqual(self.events(short, top=True)[-1]['outcome'], 'raised')

    def test_mutation_and_reentrant_calls_survive_errors_and_history_replacement(self):
        for mode in ('pass', 'admission'):
            for suffix in ('mutation_true', 'mutation_raises'):
                case = self.cases[mode + ':' + suffix]
                before = case['initial_state']['state']['dependencies']
                after = case['final_state']['state']['dependencies']
                self.assertNotEqual(before['registry'], after['registry'])
                self.assertEqual({key: item for key, item in before.items() if key != 'registry'},
                                 {key: item for key, item in after.items() if key != 'registry'})
                nested = [event for event in case['events'] if event['kind'] == 'manager' and event['parent'] is not None]
                self.assertEqual([event['recipe']['operation'] for event in nested], ['set_dependency'])
            for suffix in ('mutation_true', 'mutation_raises'):
                stale = self.events('pass:' + suffix, top=True)[-1]
                self.assertEqual(stale['error']['message'], "Stale artifact 'input'; changed dependencies: registry.")
            reads = self.events(mode + ':reentrant_reads', kind='manager')
            self.assertEqual([event['recipe']['operation'] for event in reads if event['parent'] is not None],
                             ['target', 'get'] if mode == 'pass' else ['target'])
            for suffix in ('reentrant_registration', 'history_restore'):
                case = self.cases[mode + ':' + suffix]
                state = case['final_state']['state']
                registrations = state['passes' if mode == 'pass' else 'component_inputs']
                history = state['provider_history' if mode == 'pass' else 'component_input_history']
                self.assertEqual(len(history), 2)
                active = next(iter(registrations.values()))
                self.assertEqual(active['contract']['version'], '1')
                self.assertEqual(list(active['validators'].values()), ['new'])
                self.assertEqual({value['contract']['version'] for value in history.values()}, {'1', '2'})

    def test_self_consistent_observation_or_source_forgery_cannot_replace_original_oracle(self):
        for mutate in ('observation', 'source'):
            forged = deepcopy(self.value)
            if mutate == 'observation':
                forged['cases'][0]['events'][0]['after']['state']['dependencies']['request'] = '0' * 64
            else:
                forged['source_files']['src/biocompiler/compiler/pipeline.py'] = '0' * 64
            forged['inventory_fingerprint'] = sha(canonical({key: item for key, item in forged.items()
                                                           if key != 'inventory_fingerprint'}))
            with self.assertRaisesRegex(AssertionError, 'inventory changed'):
                validate(forged)


def load_tests(loader, tests, pattern):
    from tools.pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, 'test_pipeline_callback_semantics')


if __name__ == '__main__':
    unittest.main()
