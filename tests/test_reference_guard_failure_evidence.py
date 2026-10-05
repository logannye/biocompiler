"""Rejected guard comparisons retain diagnostic bytes without granting acceptance."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import check_pipeline_reference_install as gate


class ReferenceGuardFailureEvidenceTests(unittest.TestCase):
    def test_failed_comparison_retains_both_guards_and_sources_before_cleanup(self):
        with tempfile.TemporaryDirectory() as destination:
            receipt = {'_artifact_directory': destination, 'artifacts': {}}
            native = {'calls': [{'count': 1}], 'unchanged': 'full native evidence'}
            current = {'calls': [{'count': 2}], 'unchanged': 'full replay evidence'}
            receipt['guard'] = gate.manager.artifact(receipt, gate.canonical(native))
            original = AssertionError('Current reconstruction changed its complete guarded execution')
            with tempfile.TemporaryDirectory() as temporary:
                replay = {'_artifact_directory': temporary, 'artifacts': {}}
                replay['guard'] = gate.manager.artifact(replay, gate.canonical(current))
                source = gate.manager.artifact(replay, b'exact reviewed source\n')
                proof = {'files': {'/replay/helper.py': {'logical': 'tools/helper.py', 'artifact': source},
                                   '<string>': {'logical': '<generated-dataclass>', 'artifact': None}}}
                replay['observation_sources'] = gate.manager.artifact(replay, gate.canonical(proof))
                artifacts = gate.manager.Artifacts(temporary, replay['artifacts'])
                stream = io.StringIO()
                with patch.object(gate, 'guarded_projection', side_effect=lambda value, paths: deepcopy(value)), \
                        patch.object(gate.sys, 'stderr', stream), self.assertRaises(AssertionError) as caught:
                    with gate.guarded_comparison_diagnostics(current, {'/replay/helper.py': 'tools/helper.py'},
                            native, {'/native/helper.py': 'tools/helper.py'}, receipt=receipt, replay=replay,
                            replay_artifacts=artifacts, retain=lambda raw: gate.manager.artifact(receipt, raw)):
                        raise original
                self.assertIs(caught.exception, original)
                self.assertIn('$.calls[0].count', stream.getvalue())
            self.assertFalse(Path(temporary).exists())
            saved = gate.manager.Artifacts(destination, receipt['artifacts'])
            failure = saved.json(receipt['reconstruction_failure'])
            self.assertIs(failure['acceptance'], False)
            self.assertEqual(saved.json(failure['native_guard']), native)
            self.assertEqual(saved.json(failure['replay']['guard']), current)
            self.assertEqual(saved.json(failure['replay']['observation_sources']), proof)
            self.assertEqual(saved.raw(source), b'exact reviewed source\n')
            self.assertEqual(failure['first_difference'], {'path': '$.calls[0].count', 'current': '2', 'native': '1'})

    def test_success_does_not_publish_failure_evidence(self):
        receipt, retain = {}, Mock()
        with gate.guarded_comparison_diagnostics({}, {}, {}, {}, receipt=receipt,
                replay={}, replay_artifacts=None, retain=retain):
            pass
        self.assertEqual(receipt, {})
        retain.assert_not_called()

    def test_storage_or_stderr_failure_cannot_mask_original_rejection(self):
        for retention in (None, Mock(side_effect=OSError('storage unavailable'))):
            original = AssertionError('original comparison rejected')
            with self.subTest(retention=retention), \
                    patch.object(gate, 'guarded_projection', side_effect=lambda value, paths: value), \
                    patch('builtins.print', side_effect=OSError('stderr unavailable')), \
                    self.assertRaises(AssertionError) as caught:
                with gate.guarded_comparison_diagnostics({'x': 2}, {}, {'x': 1}, {}, receipt={},
                        replay={'guard': 'guard'}, replay_artifacts=Mock(), retain=retention):
                    raise original
            self.assertIs(caught.exception, original)

    def test_first_difference_identifies_types_missing_keys_and_lengths_with_bounds(self):
        self.assertIsNone(gate.first_guard_difference({'a': [1, None]}, {'a': [1, None]}))
        self.assertEqual(gate.first_guard_difference({'a': [True]}, {'a': [1]})['path'], '$.a[0]')
        self.assertEqual(gate.first_guard_difference({'a': [1]}, {'a': []})['path'], '$.a.length')
        self.assertEqual(gate.first_guard_difference({}, {'a': 1})['current'], 'missing')
        difference = gate.first_guard_difference('x' * 2000, 'y' * 2000, 'z' * 2000)
        self.assertLessEqual(len(difference['path']), 512)
        self.assertLessEqual(len(difference['current']), 160)
        self.assertLessEqual(len(difference['native']), 160)


if __name__ == '__main__':
    unittest.main()
