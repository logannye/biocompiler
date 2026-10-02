"""Trusted host mechanics without a native process or imported acceptance."""
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
import gc
import threading
import unittest
from unittest.mock import patch
import weakref

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.core_client import CoreProtocolError
from biocompiler.ir.intent import freeze_json
from biocompiler.pipeline_callback_objects import (
    CallbackObjectProtocolError, CallbackObjects, ObjectLimits,
)
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind


class CallbackObjectsTests(unittest.TestCase):
    def setUp(self):
        self.broker = CallbackObjects()
        self.addCleanup(self.broker.close)

    def value(self, action, **arguments):
        completion = self.broker.execute(action, arguments)
        self.assertEqual(completion.status, 'ok')
        return completion.value

    def object(self, action, **arguments):
        return self.broker.resolve(self.value(action, **arguments))

    def call(self, function, *arguments):
        return self.broker.execute('call', {
            'callable': self.broker.retain(function),
            'args': [self.broker.retain(value) for value in arguments], 'kwargs': {},
        })

    def test_physical_identity_never_calls_hash_equality_or_getattr(self):
        class Unobservable:
            def __hash__(self):
                raise AssertionError('hash')

            def __eq__(self, other):
                raise AssertionError('equality')

            def __getattribute__(self, name):
                raise AssertionError('attribute')

        first, second = Unobservable(), Unobservable()
        first_ref = self.broker.retain(first)
        self.assertEqual(first_ref, self.broker.retain(first))
        self.assertNotEqual(first_ref, self.broker.retain(second))
        self.assertIs(self.broker.resolve(first_ref), first)
        self.broker.release([first_ref])
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'released'):
            self.broker.resolve(first_ref)
        self.assertNotEqual(first_ref, self.broker.retain(first))

    def test_handles_strongly_retain_then_release_without_id_reuse(self):
        class Value:
            pass

        value = Value()
        weak = weakref.ref(value)
        reference = self.broker.retain(value)
        del value
        gc.collect()
        self.assertIsNotNone(weak())
        self.broker.release([reference])
        gc.collect()
        self.assertIsNone(weak())

    def test_provider_binding_is_stable_physical_identity_and_calls_original(self):
        events = []

        class Provider:
            __hash__ = None

            def __eq__(self, other):
                raise AssertionError('identity binding invoked equality')

            def __call__(self, context):
                events.append(context)
                return context

        first, second = Provider(), Provider()
        first_ref, second_ref = self.broker.retain(first), self.broker.retain(second)
        self.broker.bind_provider('native/1', first_ref)
        self.broker.bind_provider('native/1', first_ref)
        self.broker.bind_provider('native/2', second_ref)
        context = object()
        result = self.object('call-provider', provider_id='native/1', context=self.broker.retain(context))
        self.assertIs(result, context)
        self.assertEqual(len(events), 1)
        self.assertIs(events[0], context)
        for provider, reference in [('native/1', second_ref), ('native/3', first_ref)]:
            with self.assertRaises(CallbackObjectProtocolError):
                self.broker.bind_provider(provider, reference)
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'cannot be released'):
            self.broker.release([first_ref])

    def test_actual_rich_comparison_reflection_boolean_and_identity_are_distinct(self):
        events = []

        class Truth:
            def __bool__(self):
                events.append('bool')
                return True

        class Left:
            def __eq__(self, other):
                events.append('left')
                return NotImplemented

        class Right:
            def __eq__(self, other):
                events.append('right')
                return Truth()

        left, right = self.broker.retain(Left()), self.broker.retain(Right())
        self.assertTrue(self.value('compare', left=left, right=right, operator='eq'))
        self.assertEqual(events, ['left', 'right', 'bool'])
        events.clear()
        self.assertFalse(self.value('compare', left=left, right=right, operator='is'))
        self.assertEqual(events, [])

    def test_closed_enum_constants_keep_actual_singleton_identity(self):
        for name, value in [('CheckOutcome', CheckOutcome.PASS), ('EvidenceKind', EvidenceKind.UNRESOLVED)]:
            reference = self.value('enum', type=name, value=value.value)
            self.assertIs(self.broker.resolve(reference), value)
            self.assertTrue(self.value('compare', left=reference, right=self.broker.retain(value), operator='is'))
        for name, value in [('os.system', 'pass'), ('CheckOutcome', 'PASS'), ('CheckOutcome', [])]:
            with self.assertRaises(CallbackObjectProtocolError):
                self.value('enum', type=name, value=value)
        with self.assertRaises(CallbackObjectProtocolError):
            self.value('is-instance', object=self.broker.retain(None), type='os.system')

    def test_document_only_converts_without_touching_shape_or_fingerprint(self):
        events = []

        class Authored:
            @property
            def fingerprint(self):
                raise AssertionError('premature fingerprint')

            def to_dict(self):
                events.append('to_dict')
                return ['an invalid artifact which the native manager must reject']

        authored = self.broker.retain(Authored())
        result = self.value('document', object=authored)
        self.assertEqual(events, ['to_dict'])
        self.assertFalse(self.value('is-instance', object=result, type='Mapping'))
        self.assertEqual(self.broker.resolve(result), ['an invalid artifact which the native manager must reject'])

        class Document(dict):
            def to_dict(self):
                raise AssertionError('Mapping conversion called to_dict')

        document = Document(schema_version='test')
        self.assertIs(self.object('document', object=self.broker.retain(document)), document)

    def test_deferred_pass_result_getters_and_source_iteration_remain_lazy(self):
        events = []

        class Result(PassResult):
            def __getattribute__(self, name):
                if name in ('output', 'source_links', 'obligations', 'search_status', 'observation_map'):
                    events.append('get:' + name)
                return super().__getattribute__(name)

        def links():
            events.append('first')
            yield 'bad first item'
            events.append('second')
            yield object()
            events.append('exhausted')

        result = Result(output={'schema_version': 'fixture'}, obligations=(), source_links=links())
        reference = self.broker.retain(result)
        self.assertTrue(self.value('is-instance', object=reference, type='PassResult'))
        self.assertEqual(events, [])
        links_ref = self.value('attr', object=reference, name='source_links')
        self.assertEqual(events, ['get:source_links'])
        values = self.object('tuple', object=links_ref)
        self.assertEqual(events, ['get:source_links', 'first', 'second', 'exhausted'])
        self.assertFalse(self.value('is-instance', object=self.broker.retain(values[0]), type='SourceLink'))

    def test_obligation_iteration_short_circuits_at_native_request_boundary(self):
        events = []

        def obligations():
            events.append('first')
            yield None
            events.append('second')
            raise AssertionError('must not consume after native rejection')

        iterator = self.value('iter', object=self.broker.retain(obligations()))
        self.assertEqual(events, [])
        first = self.value('next', object=iterator)
        self.assertFalse(first['exhausted'])
        self.assertIsNone(self.broker.resolve(first['object']))
        self.assertEqual(events, ['first'])
        end = self.value('next', object=self.broker.retain(iter(())))
        self.assertEqual(end, {'exhausted': True, 'object': None})

    def test_freezing_preserves_original_mapping_access_order(self):
        class ObservedMapping(Mapping):
            def __init__(self, events):
                self.events = events
                self.data = {'schema_version': 'fixture', 'nested': [1, {'x': 2}]}

            def __iter__(self):
                self.events.append('iter')
                return iter(self.data)

            def __len__(self):
                self.events.append('len')
                return len(self.data)

            def __getitem__(self, key):
                self.events.append(('get', key))
                return self.data[key]

        original_events, broker_events = [], []
        original = freeze_json(ObservedMapping(original_events))
        frozen = self.object('freeze-json', object=self.broker.retain(ObservedMapping(broker_events)))
        self.assertEqual(original_events, broker_events)
        self.assertEqual(original, frozen)
        self.assertEqual(self.value('json', object=self.broker.retain(frozen)),
                         {'schema_version': 'fixture', 'nested': [1, {'x': 2}]})

    def test_source_links_stay_same_objects_through_callback_and_late_vars(self):
        link = SourceLink('requirement', 'source', 'target', 'pass')
        reference = self.broker.retain(link)

        def validator(context):
            self.assertIs(context[0], link)
            object.__setattr__(context[0], 'target_node_id', 'mutated-during-validator')

        self.call(validator, (link,))
        data = self.object('vars', object=reference)
        self.assertIs(data, vars(link))
        self.assertEqual(data['target_node_id'], 'mutated-during-validator')

    def test_set_comprehension_interleaves_attribute_reads_with_hashes(self):
        events = []

        class Key(str):
            def __hash__(self):
                events.append('hash:' + str(self))
                return super().__hash__()

        class Link:
            def __init__(self, name):
                self.name = name

            @property
            def requirement_id(self):
                events.append('get:' + self.name)
                return Key(self.name)

        refs = [self.broker.retain(Link(value)) for value in ('first', 'second')]
        self.assertTrue(self.value('set-attribute-equal', objects=refs, name='requirement_id', values=['first', 'second']))
        self.assertEqual(events, ['get:first', 'hash:first', 'get:second', 'hash:second'])

    def test_lookup_uses_actual_host_hash_equality_and_key_error(self):
        events = []

        class Key:
            def __hash__(self):
                events.append('hash')
                return hash('requirement')

            def __eq__(self, other):
                events.append(('eq', other))
                return other == 'requirement'

        key = self.broker.retain(Key())
        self.assertEqual(self.object('lookup', object=key, entries=[['requirement', {'kind': 'exact'}]]), {'kind': 'exact'})
        self.assertEqual(events, ['hash', ('eq', 'requirement')])
        missing = object()
        completion = self.broker.execute('lookup', {'object': self.broker.retain(missing), 'entries': []})
        with self.assertRaises(KeyError) as caught:
            self.broker.rethrow(completion.value['exception_token'])
        self.assertIs(caught.exception.args[0], missing)

    def test_merge_uses_original_mapping_unpack_order_and_rejects_pairs(self):
        events = []

        class Decision:
            def keys(self):
                events.append('keys')
                return ['outcome', 'detail']

            def __getitem__(self, key):
                events.append(('get', key))
                return {'outcome': 'pass', 'detail': 'custom'}[key]

        merged = self.object('merge', object=self.broker.retain(Decision()),
                             before={'outcome': 'unknown', 'id': 'check'}, after={'subject': 'native'})
        self.assertEqual(events, ['keys', ('get', 'outcome'), ('get', 'detail')])
        self.assertEqual(merged, {'outcome': 'pass', 'detail': 'custom', 'id': 'check', 'subject': 'native'})
        completion = self.broker.execute('merge', {'object': self.broker.retain([('outcome', 'pass')]),
                                                   'before': {}, 'after': {}})
        self.assertEqual(completion.status, 'exception')
        with self.assertRaises(TypeError):
            self.broker.rethrow(completion.value['exception_token'])

    def test_reentrant_calls_use_same_broker_and_do_not_rollback_mutation(self):
        state = []
        nested_error = ValueError('nested')

        def inner(context):
            state.append(context)
            raise nested_error

        self.broker.bind_provider('native/inner', self.broker.retain(inner))

        def outer(context):
            failed = self.broker.execute('call-provider', {'provider_id': 'native/inner', 'context': self.broker.retain(context)})
            try:
                self.broker.rethrow(failed.value['exception_token'])
            except ValueError as caught:
                self.assertIs(caught, nested_error)
            state.append('outer-resumed')
            return context

        self.broker.bind_provider('native/outer', self.broker.retain(outer))
        context = object()
        self.assertIs(self.object('call-provider', provider_id='native/outer', context=self.broker.retain(context)), context)
        self.assertEqual(state, [context, 'outer-resumed'])
        self.assertEqual(self.broker.counts['exceptions'], 0)

    def test_exception_identity_cause_context_tail_and_suppression_are_preserved(self):
        class UnobservableError(ValueError):
            def __str__(self):
                raise AssertionError('exception stringification')

            def __getattribute__(self, name):
                if name in ('__traceback__', '__cause__', '__context__', '__suppress_context__', 'with_traceback'):
                    raise AssertionError('exception attribute observer')
                return super().__getattribute__(name)

        error, cause, context = UnobservableError('retained'), LookupError('cause'), RuntimeError('context')

        def raising():
            try:
                raise context
            except RuntimeError:
                raise error from cause

        completion = self.call(raising)
        self.assertEqual(completion.status, 'exception')
        original_tb = BaseException.__getattribute__(error, '__traceback__')
        caught = None
        try:
            self.broker.rethrow(completion.value['exception_token'])
        except UnobservableError as current:
            caught = current
        self.assertIs(caught, error)
        self.assertIs(BaseException.__getattribute__(error, '__cause__'), cause)
        self.assertIs(BaseException.__getattribute__(error, '__context__'), context)
        self.assertTrue(BaseException.__getattribute__(error, '__suppress_context__'))
        traceback = BaseException.__getattribute__(error, '__traceback__')
        while traceback is not None and traceback is not original_tb:
            traceback = traceback.tb_next
        self.assertIs(traceback, original_tb)
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'consumed'):
            self.broker.rethrow(completion.value['exception_token'])

    def test_keyboard_interrupt_system_exit_and_protocol_errors_are_local_exceptions(self):
        for error in (KeyboardInterrupt(), SystemExit(7), CoreProtocolError('user'), CallbackObjectProtocolError('user')):
            def raising():
                raise error

            completion = self.call(raising)
            self.assertEqual(completion.status, 'exception')
            try:
                self.broker.rethrow(completion.value['exception_token'])
            except BaseException as caught:
                self.assertIs(caught, error)
            else:
                self.fail('Exception was lost')
            self.assertTrue(self.value('is-none', object=self.broker.retain(None)))

    def test_exception_slot_properties_cannot_observe_capture_or_restore(self):
        def observe(*arguments):
            raise AssertionError('Shadowed exception descriptor must not execute')

        class Shadowed(Exception):
            __traceback__ = property(observe, observe)
            __cause__ = property(observe, observe)
            __context__ = property(observe, observe)
            __suppress_context__ = property(observe, observe)

        error, cause, context = Shadowed('original'), ValueError('cause'), LookupError('context')

        def raising():
            try:
                raise context
            except LookupError:
                raise error from cause

        completion = self.call(raising)
        self.assertEqual(completion.status, 'exception')
        slots = BaseException.__dict__
        tail = slots['__traceback__'].__get__(error)
        caught = None
        try:
            self.broker.rethrow(completion.value['exception_token'])
        except Shadowed as current:
            caught = current
        self.assertIs(caught, error)
        self.assertIs(slots['__cause__'].__get__(error), cause)
        self.assertIs(slots['__context__'].__get__(error), context)
        self.assertTrue(slots['__suppress_context__'].__get__(error))
        current = slots['__traceback__'].__get__(error)
        while current is not None and current is not tail:
            current = current.tb_next
        self.assertIs(current, tail)

    def test_resource_limits_fail_as_broker_faults_not_callback_exceptions(self):
        broker = CallbackObjects(limits=ObjectLimits(max_objects=1, max_actions=1))
        self.addCleanup(broker.close)
        reference = broker.retain(None)
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'handle limit'):
            broker.retain(object())
        self.assertEqual(broker.execute('is-none', {'object': reference}).value, True)
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'action limit'):
            broker.execute('is-none', {'object': reference})
        self.assertEqual(broker.counts['exceptions'], 0)
        for limits in ({'max_objects': True}, {'max_actions': 0}, {'max_document_nodes': 1_000_001}):
            with self.assertRaises(CallbackObjectProtocolError):
                ObjectLimits(**limits)

    def test_document_byte_and_node_caps_are_checked_for_instructions_and_observations(self):
        for limits, value in [(ObjectLimits(max_document_bytes=128), 'x' * 129),
                              (ObjectLimits(max_document_nodes=8), list(range(20)))]:
            broker = CallbackObjects(limits=limits)
            self.addCleanup(broker.close)
            with self.assertRaises(CallbackObjectProtocolError):
                broker.execute('literal', {'kind': 'json', 'value': value})
            reference = broker.retain(value)
            with self.assertRaises(CallbackObjectProtocolError):
                broker.execute('json', {'object': reference})
            self.assertEqual(broker.counts['exceptions'], 0)

    def test_exception_and_provider_tables_have_separate_limits(self):
        broker = CallbackObjects(limits=ObjectLimits(max_exceptions=1, max_providers=1))
        self.addCleanup(broker.close)

        def raising(context):
            raise ValueError('test')

        broker.bind_provider('one', broker.retain(raising))
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'provider handle limit'):
            broker.bind_provider('two', broker.retain(lambda value: value))
        arguments = {'provider_id': 'one', 'context': broker.retain(None)}
        self.assertEqual(broker.execute('call-provider', arguments).status, 'exception')
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'exception handle limit'):
            broker.execute('call-provider', arguments)

    def test_malformed_instructions_unknown_refs_and_release_are_atomic(self):
        first, second = self.broker.retain(object()), self.broker.retain(object())
        for action, arguments in [
            ('eval', {'code': 'anything'}), ('attr', {'object': first, 'name': 'x', 'extra': 1}),
            ('is-none', {'object': {'handle': 'unknown'}}), ('is-none', {'object': {'handle': 1}}),
            ('compare', {'left': first, 'right': second, 'operator': 'call'}),
            ('lookup', {'object': first, 'entries': [['same', 1], ['same', 2]]}),
            ('literal', {'kind': 'set', 'value': [[]]}),
        ]:
            with self.subTest(action=action, arguments=arguments), self.assertRaises(CallbackObjectProtocolError):
                self.broker.execute(action, arguments)
        with self.assertRaises(CallbackObjectProtocolError):
            self.broker.release([first, second, first])
        self.broker.resolve(first)
        self.broker.resolve(second)
        self.assertEqual(self.broker.counts['exceptions'], 0)

    def test_thread_process_ownership_and_closed_registry_are_enforced(self):
        errors = []

        def access():
            try:
                self.broker.retain(None)
            except CallbackObjectProtocolError as error:
                errors.append(error)

        thread = threading.Thread(target=access)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        with patch('biocompiler.pipeline_callback_objects.os.getpid', return_value=-1):
            with self.assertRaisesRegex(CallbackObjectProtocolError, 'creating thread and process'):
                self.broker.retain(None)
        self.broker.close()
        self.broker.close()
        with self.assertRaisesRegex(CallbackObjectProtocolError, 'closed'):
            self.broker.retain(None)

    def test_completion_bytes_and_decoded_values_are_immutable(self):
        completion = self.broker.execute('json', {'object': self.broker.retain({'a': [1]})})
        value = completion.value
        value['a'].append(2)
        self.assertEqual(completion.value, {'a': [1]})
        with self.assertRaises(FrozenInstanceError):
            completion.document = b'null'


if __name__ == '__main__':
    unittest.main()
