"""Canonical-frame controls for the native manager's ordered merge primitive."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import unittest

from biocompiler.compiler.pipeline import CheckDecision, CheckSpec
from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from tests import test_core_pipeline_manager as fixtures


class OrderedMergeTests(unittest.TestCase):
    setUp = fixtures.CorePipelineManagerTests.setUp

    def instruction(self, source, before, after):
        # Exercise the exact canonical transport that exposed the hosted bug;
        # a direct in-process dict would accidentally retain literal order.
        return decode_document(encode_document({'object': self.manager._objects.retain(source),
            'before': before, 'after': after, 'before_tree': _ordered(before), 'after_tree': _ordered(after)}))

    def merge(self, source, before, after):
        completion = self.manager._invoke('ordered-merge', self.instruction(source, before, after))
        self.assertEqual(completion.status, 'ok')
        return self.manager._objects.resolve(completion.value)

    def test_full_original_check_order_survives_canonical_frames(self):
        spec = CheckSpec('z_check', EvidenceKind.EXACT, ('identity',))
        decision = CheckDecision(CheckOutcome.PASS, 'Independently checked.', {'zeta': 1, 'alpha': 2})
        dependencies = {'zeta': 'a' * 64, 'request': 'b' * 64, 'alpha': 'c' * 64, 'target': 'd' * 64}
        first = self.merge(decision.to_dict(), spec.to_dict(), {})
        second = self.merge(first, {}, {'subject': 'e' * 64, 'dependencies': dependencies})
        expected = {**spec.to_dict(), **decision.to_dict(), 'subject': 'e' * 64, 'dependencies': dependencies}
        self.assertEqual(_ordered(second), _ordered(expected))
        self.assertEqual(list(second), ['id', 'evidence_kind', 'discharges', 'outcome',
            'detail', 'evidence', 'subject', 'dependencies'])
        self.assertEqual(list(second['dependencies']), list(dependencies))
        self.assertEqual(list(second['evidence']), ['zeta', 'alpha'])
        evaluator = self.manager._ordered_merge_callable
        self.assertEqual(sum(value is evaluator for value in self.manager._objects._objects.values()), 1)
        # Same values remain exactly canonical: order carries no new acceptance.
        self.assertEqual(encode_document(second), encode_document(expected))

    def test_actual_mapping_unpack_order_overwrite_and_exception_identity_remain_original(self):
        events = []
        class Authored(Mapping):
            def __iter__(self):
                events.append('iter')
                return iter(('id', 'outcome'))
            def __len__(self):
                raise AssertionError('Unpacking must not read mapping length')
            def __getitem__(self, key):
                events.append(('get', key))
                return {'id': 'replacement', 'outcome': 'pass'}[key]
        source = Authored()
        before, after = {'id': 'initial', 'evidence_kind': 'exact'}, {'outcome': 'fail', 'subject': 'identity'}
        expected = {**before, **source, **after}
        original_events = events[:]; events.clear()
        actual = self.merge(source, before, after)
        self.assertEqual(events, original_events)
        self.assertEqual(_ordered(actual), _ordered(expected))
        marker = ValueError('actual authored mapping failure')
        class Raising(Authored):
            def __getitem__(self, key):
                raise marker
        completion = self.manager._invoke('ordered-merge', self.instruction(Raising(), before, after))
        self.assertEqual(completion.status, 'exception')
        try:
            self.manager._objects.rethrow(completion.value['exception_token'])
        except ValueError as error:
            self.assertIs(error, marker)
        else:
            self.fail('The actual mapping exception was lost')
        self.assertFalse(self.session.invalidated)

    def test_invalid_ordered_projection_never_observes_authored_mapping(self):
        class Forbidden(Mapping):
            def __iter__(self): raise AssertionError('Authored mapping observed before validation')
            def __len__(self): raise AssertionError('Authored mapping observed before validation')
            def __getitem__(self, key): raise AssertionError('Authored mapping observed before validation')
        source = Forbidden()
        base = self.instruction(source, {'zeta': True, 'alpha': {'b': 1, 'a': 2}}, {})
        changes = (
            lambda value: value['before_tree'][1].append(value['before_tree'][1][0]),
            lambda value: value['before'].update(zeta=1),
            lambda value: value.update(after_tree=['array', []]),
            lambda value: value['before_tree'][1][1][1][1][0][1].__setitem__(1, 9),
        )
        for change in changes:
            with self.subTest(change=change):
                raw = deepcopy(base); change(raw)
                counts = self.manager._objects.counts
                with self.assertRaises(CoreProtocolError): self.manager._invoke('ordered-merge', raw)
                self.assertEqual(self.manager._objects.counts, counts)
        self.manager._objects.limits = replace(self.manager._objects.limits, max_document_nodes=8)
        with self.assertRaises(CoreProtocolError): self.manager._invoke('ordered-merge', base)


if __name__ == '__main__':
    unittest.main()
