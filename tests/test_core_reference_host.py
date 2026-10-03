"""Actual Python callbacks and source-bound native-default selection only."""
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
import sys
from types import FunctionType, MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler import core_reference_host as host
from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.core_client import CoreProtocolError
from biocompiler.ir.molecular import MolecularArtifact, MolecularRecord


@contextmanager
def profile_calls():
    calls = []
    previous = sys.getprofile()
    def observe(frame, event, arg):
        if event == 'call':
            calls.append((frame.f_code, frame.f_globals))
        if previous is not None:
            previous(frame, event, arg)
    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


class CoreReferenceHostTests(unittest.TestCase):
    def setUp(self):
        self.request, self.registry, self.manifest = object(), object(), object()
        self.original = {'second': self.manifest, 'first': object()}
        self.host = host.ReferenceHost.for_molecular(self.request, self.registry, self.original)

    def test_defaults_select_native_without_executing_legacy_producers(self):
        with profile_calls() as calls:
            self.assertIs(self.host.generate(object()), host.NativeDefault.GENERATE)
            self.assertIs(self.host.emit(object()), host.NativeDefault.EMIT)
        for witness in (host._GENERATOR, host._EMITTER):
            self.assertFalse(any(code is witness.function.__code__ and namespace is witness.function.__globals__
                                 for code, namespace in calls))

    def test_distinct_snapshot_maps_preserve_original_values_order_and_authority(self):
        self.assertIs(self.host.request, self.request)
        self.assertIs(self.host.registry, self.registry)
        outer, inner = self.host.molecular_manifests, self.host.construct_manifests
        self.assertIs(type(outer), MappingProxyType)
        self.assertIs(type(inner), MappingProxyType)
        self.assertIsNot(outer, inner)
        self.assertIsNot(inner, self.original)
        self.assertEqual(list(inner), ['second', 'first'])
        self.assertEqual(list(outer), ['second', 'first'])
        for key, value in self.original.items():
            self.assertIs(inner[key], value)
            self.assertIs(outer[key], value)
        self.original['second'] = object()
        self.original['new'] = object()
        self.assertIs(inner['second'], self.manifest)
        self.assertNotIn('new', outer)
        with self.assertRaises(TypeError):
            inner['new'] = object()
        standalone = host.ReferenceHost.for_construct(self.request, self.registry, self.original)
        self.assertIsNone(standalone.molecular_manifests)
        with self.assertRaisesRegex(CoreProtocolError, 'original snapshot'):
            standalone.emit(object())
        with self.assertRaisesRegex(CoreProtocolError, 'original snapshot'):
            standalone.origin('molecular_manifests')

    def test_custom_manifest_mapping_is_copied_once_before_nested_plain_snapshot(self):
        events = []
        values = self.original
        class Supplied(Mapping):
            def __iter__(self):
                events.append('iter')
                return iter(values)
            def __len__(self):
                events.append('len')
                return len(values)
            def __getitem__(self, key):
                events.append(('get', key))
                return values[key]
        actual = host.ReferenceHost.for_molecular(self.request, self.registry, Supplied())
        self.assertEqual(events, ['iter', ('get', 'second'), ('get', 'first')])
        self.assertIsNot(actual.molecular_manifests, actual.construct_manifests)

    def test_dynamic_replacements_restoration_and_exact_call_arguments(self):
        calls, first, second = [], object(), object()
        def generate(value):
            calls.append(('generate', value))
            return first
        def emit(*values):
            calls.append(('emit', values))
            return second
        parsed_request, parsed_construct = object(), object()
        with patch.object(host._CONSTRUCT, 'generate_construct', generate):
            a = self.host.generate(parsed_request)
        self.assertIs(a.output, first)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1], parsed_request)
        self.assertIs(self.host.generate(parsed_request), host.NativeDefault.GENERATE)
        with patch.object(host._MOLECULAR, 'emit_reference_sequence', emit):
            b = self.host.emit(parsed_construct)
        self.assertIs(b.output, second)
        self.assertEqual(len(calls), 2)
        for actual, expected in zip(calls[1][1], (self.request, parsed_construct, self.registry,
                                                self.host.molecular_manifests)):
            self.assertIs(actual, expected)
        self.assertIs(self.host.emit(parsed_construct), host.NativeDefault.EMIT)
        with patch.object(host._CONSTRUCT, 'generate_construct', lambda value: host.NativeDefault.EMIT):
            marker_output = self.host.generate(parsed_request)
        self.assertIs(type(marker_output), host.HostValue)
        self.assertIs(marker_output.output, host.NativeDefault.EMIT)

    def test_distinct_code_copy_is_real_untrusted_replacement_not_default_authority(self):
        events, error = [], ValueError('actual copied-code call')
        def require(*args):
            events.append(args)
            raise error
        default = host._GENERATOR.function
        namespace = dict(default.__globals__, require=require)
        copied = FunctionType(default.__code__, namespace, default.__name__)
        with patch.object(host._CONSTRUCT, 'generate_construct', copied):
            with self.assertRaises(ValueError) as raised:
                self.host.generate(object())
        self.assertIs(raised.exception, error)
        self.assertEqual(len(events), 1)
        self.assertIs(self.host.generate(object()), host.NativeDefault.GENERATE)

    def test_opaque_output_not_observed_and_proposal_defaults_are_exact(self):
        events = []
        class Opaque:
            def __getattribute__(self, name):
                events.append(name)
                raise AssertionError('output observed')
            def __eq__(self, other):
                raise AssertionError('output compared')
            def __repr__(self):
                raise AssertionError('output printed')
        output = Opaque()
        class Replacement:
            def __call__(self, *args):
                events.append('call')
                return output
        with patch.object(host._CONSTRUCT, 'generate_construct', Replacement()):
            value = self.host.generate(object())
        self.assertEqual(events, ['call'])
        links = (SourceLink('r', 'a', 'b', 'components_to_construct'),)
        proposal = self.host.proposal(value, links)
        self.assertIs(type(proposal), PassResult)
        self.assertIs(proposal.output, output)
        self.assertIs(proposal.source_links, links)
        self.assertEqual(proposal.obligations, ())
        self.assertEqual(proposal.observation_map, {})
        self.assertEqual(proposal.search_status, 'candidate')
        second = self.host.proposal(value, links)
        self.assertIsNot(second.observation_map, proposal.observation_map)
        self.assertEqual(events, ['call'])
        with self.assertRaisesRegex(AssertionError, 'observed'):
            proposal.output.to_dict()
        self.assertEqual(events, ['call', 'to_dict'])
        foreign = host.ReferenceHost.for_construct(self.request, self.registry, self.original)
        with self.assertRaisesRegex(CoreProtocolError, 'another callback owner'):
            foreign.proposal(value, links)
        with self.assertRaisesRegex(CoreProtocolError, 'supplied tuple'):
            self.host.proposal(value, list(links))

    def test_original_callable_exception_identity_cause_and_reentrant_replacement(self):
        events, error, cause = [], ValueError('kept'), RuntimeError('cause')
        def later(value):
            events.append(('later', value))
            return error
        def replacement(value):
            events.append(('first', value))
            host._CONSTRUCT.generate_construct = later
            raise error from cause
        bound = object()
        with patch.object(host._CONSTRUCT, 'generate_construct', replacement):
            try:
                self.host.generate(bound)
            except ValueError as actual:
                self.assertIs(actual, error)
                self.assertIs(actual.__cause__, cause)
                self.assertTrue(actual.__suppress_context__)
                tail = actual.__traceback__
                while tail.tb_next is not None:
                    tail = tail.tb_next
                self.assertIs(tail.tb_frame.f_code, replacement.__code__)
            else:
                self.fail('Actual replacement exception was swallowed')
            self.assertIs(self.host.generate(bound).output, error)
        self.assertEqual([kind for kind, _ in events], ['first', 'later'])
        self.assertTrue(all(value is bound for _, value in events))

    def test_noncallable_replacement_keeps_original_python_call_failure(self):
        with patch.object(host._CONSTRUCT, 'generate_construct', None):
            with self.assertRaisesRegex(TypeError, "'NoneType' object is not callable"):
                self.host.generate(object())

    def test_retained_default_tampering_fails_closed_and_never_calls_changed_code(self):
        default = host._GENERATOR.function
        original = default.__code__
        # Give a no-closure function exactly the original signature.
        changed = compile('def changed(value):\n    raise AssertionError("executed")\n', '<changed>', 'exec').co_consts[0]
        try:
            default.__code__ = changed
            with self.assertRaisesRegex(CoreProtocolError, 'code or globals'):
                self.host.generate(object())
        finally:
            default.__code__ = original
        with patch.dict(vars(host._GENERATOR.module), {'__name__': 'forged.namespace'}):
            with self.assertRaisesRegex(CoreProtocolError, 'module origin'):
                self.host.generate(object())
        with patch.object(default, '__defaults__', (object(),)):
            with self.assertRaisesRegex(CoreProtocolError, 'code or globals'):
                self.host.generate(object())
        with patch.object(Path, 'read_bytes', return_value=b'changed source'):
            with self.assertRaisesRegex(CoreProtocolError, 'source bytes'):
                self.host.generate(object())
        self.assertIs(self.host.generate(object()), host.NativeDefault.GENERATE)

    def test_initial_canonical_default_with_forged_globals_is_rejected(self):
        default = host._GENERATOR
        forged = FunctionType(default.function.__code__, dict(default.function.__globals__), default.name)
        with patch.object(default.module, default.name, forged):
            with self.assertRaisesRegex(CoreProtocolError, 'code or globals'):
                host._default('synthesis.construct', default.name, default.sha256)

    def test_closed_original_policy_roots_are_exact_and_cannot_rebind(self):
        names = {
            'request': self.request, 'registry': self.registry,
            'construct_manifests': self.host.construct_manifests,
            'molecular_manifests': self.host.molecular_manifests,
            'translation_policy': vars(MolecularRecord)['translation_policy'],
            'encoding_policy': vars(MolecularArtifact)['encoding_policy'],
            'evidence_policy': vars(MolecularArtifact)['evidence_policy'],
        }
        for name, expected in names.items():
            self.assertIs(self.host.origin(name), expected)
        with self.assertRaisesRegex(CoreProtocolError, 'Unknown'):
            self.host.origin('__dict__')
        with patch.object(MolecularArtifact, 'encoding_policy', type(names['encoding_policy'])()):
            with self.assertRaisesRegex(CoreProtocolError, 'origin changed'):
                self.host.origin('encoding_policy')
        # A replacement installed before the host module captured class roots
        # still cannot impersonate the original dataclass constructor default.
        changed = type(names['encoding_policy'])()
        with patch.object(MolecularArtifact, 'encoding_policy', changed), \
                patch.dict(host._POLICY_VALUES, {'encoding_policy': changed}):
            with self.assertRaisesRegex(CoreProtocolError, 'origin changed'):
                self.host.origin('encoding_policy')

    def test_sorted_links_preserve_duplicate_multiplicity_and_order_independence(self):
        a, b = SourceLink('a', 'b', 'c', 'pass'), SourceLink('z', 'b', 'c', 'pass')
        self.assertTrue(host.sorted_source_links_equal((b, a, a), (a, b, a)))
        self.assertFalse(host.sorted_source_links_equal((a, a), (a,)))
        self.assertFalse(host.sorted_source_links_equal((a,), (a, a)))
        self.assertFalse(host.sorted_source_links_equal((a,), (SourceLink('a', 'b', 'c', 'other'),)))

    def test_link_accesses_and_sort_are_expected_first_with_exact_error_short_circuit(self):
        events = []
        class Ordered:
            def __init__(self, value): self.value = value
            def __lt__(self, other):
                events.append('expected-sort')
                return self.value < other.value
        class Link:
            def __init__(self, label, requirement):
                self.label, self.requirement = label, requirement
            def __getattr__(self, name):
                events.append((self.label, name))
                return self.requirement if name == 'requirement_id' else 'same'
        self.assertFalse(host.sorted_source_links_equal((Link('a1', Ordered(1)),),
            (Link('e1', Ordered(2)), Link('e2', Ordered(1)))))
        self.assertEqual(events, [(label, name) for label in ('e1', 'e2') for name in
            ('requirement_id', 'source_node_id', 'target_node_id', 'pass_name')] + ['expected-sort']
            + [('a1', name) for name in ('requirement_id', 'source_node_id', 'target_node_id', 'pass_name')])
        events.clear()
        error = ValueError('field')
        class Broken:
            def __getattr__(self, name):
                events.append(name)
                if name == 'target_node_id': raise error
                return 'value'
        def actual():
            events.append('actual-iter')
            yield Broken()
        with self.assertRaises(ValueError) as raised:
            host.sorted_source_links_equal(actual(), (Broken(),))
        self.assertIs(raised.exception, error)
        self.assertEqual(events, ['requirement_id', 'source_node_id', 'target_node_id'])
        events.clear()
        with self.assertRaises(ValueError) as raised:
            host.sorted_source_links_equal(actual(), ())
        self.assertIs(raised.exception, error)
        self.assertEqual(events, ['actual-iter', 'requirement_id', 'source_node_id', 'target_node_id'])

    def test_sort_and_actual_first_tuple_equality_errors_are_preserved(self):
        events, error = [], RuntimeError('comparison')
        class Sort:
            def __lt__(self, other):
                events.append('expected-sort')
                raise error
        def actual():
            events.append('actual-iteration')
            yield SourceLink('r', 'a', 'b', 'pass')
        expected = [SourceLink(Sort(), 'a', 'b', 'pass'), SourceLink(Sort(), 'a', 'b', 'pass')]
        with self.assertRaises(RuntimeError) as raised:
            host.sorted_source_links_equal(actual(), expected)
        self.assertIs(raised.exception, error)
        self.assertEqual(events, ['expected-sort'])
        events.clear()
        class Equality:
            def __init__(self, label): self.label = label
            def __eq__(self, other):
                events.append((self.label, other.label))
                raise error
        with self.assertRaises(RuntimeError) as raised:
            host.sorted_source_links_equal([SourceLink(Equality('actual'), 'a', 'b', 'pass')],
                [SourceLink(Equality('expected'), 'a', 'b', 'pass')])
        self.assertIs(raised.exception, error)
        self.assertEqual(events, [('actual', 'expected')])

    def test_base_exception_is_not_translated_and_helper_remains_available(self):
        error = KeyboardInterrupt('actual authoring interruption')
        events = []
        def emit(*args):
            events.append(args)
            raise error
        with patch.object(host._MOLECULAR, 'emit_reference_sequence', emit):
            try:
                self.host.emit(object())
            except BaseException as actual:
                self.assertIs(actual, error)
            else:
                self.fail('Original BaseException did not propagate')
        self.assertEqual(len(events), 1)
        self.assertIs(self.host.emit(object()), host.NativeDefault.EMIT)


if __name__ == '__main__':
    unittest.main()
