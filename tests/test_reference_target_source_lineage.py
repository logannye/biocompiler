"""Exact default-target source restoration; no native code or corpus execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_realization_workflow_corpus as workflow
from tools import reference_attempt_source as source


class ReferenceTargetSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.current = (source.ROOT / source.SOURCE).read_bytes()
        self.encoded = (source.ROOT / source.TARGET_WITNESS).read_bytes()

    def test_two_exact_insertions_restore_unchanged_attempt_authority(self):
        previous, update = source.restore_targets(self.current)
        self.assertEqual((len(previous), source.sha(previous)), (43749, source.CURRENT))
        witness = json.loads((source.ROOT / source.WITNESS).read_bytes())
        self.assertEqual(source.sha((source.ROOT / source.WITNESS).read_bytes()), source.PIN)
        self.assertEqual(witness['current_sha256'], source.sha(previous))
        self.assertEqual(update['correspondence']['predecessor'],
                         {'path': source.WITNESS, 'sha256': source.PIN})
        original, proof = source.restore(self.current)
        old_original, old_proof = source.restore_attempt(previous)
        self.assertEqual(original, old_original)
        self.assertEqual(source.sha(original), source.OLD)
        self.assertEqual(proof, {**old_proof, 'target_update': update})
        self.assertEqual(proof['correspondence'], witness)
        self.assertEqual(len(witness['changes']), 31)

    def test_previous_restoration_body_and_pins_remain_byte_identical(self):
        module = (source.ROOT / 'tools/reference_attempt_source.py').read_text()
        restored = module[:module.index('\n\ndef restore_targets(')]
        restored = restored.replace('def restore_attempt(current):', 'def restore(current):', 1)
        restored = ''.join(line for line in restored.splitlines(keepends=True)
                           if not line.startswith(('TARGET_WITNESS = ', 'TARGET_PIN = ', 'TARGET_CURRENT = ')))
        self.assertEqual(source.sha(restored.encode()),
                         '982e158b49c7cfb1001f189769d6d381cb74da1e13b2738a212b74f309c24eaf')

    def test_stale_changed_or_unrelated_source_cannot_be_relabelled(self):
        previous, _ = source.restore_targets(self.current)
        original, _ = source.restore_attempt(previous)
        for raw in (previous, original, self.current + b'\n', b'# moved\n' + self.current,
                self.current.replace(b"object.__setattr__(contract, 'targets', _REFERENCE_TARGETS)",
                                     b"object.__setattr__(contract, 'targets', contract.targets)", 1)):
            with self.subTest(pin=source.sha(raw)), self.assertRaisesRegex(AssertionError, 'Unreviewed current'):
                source.restore(raw)

    def test_rehashed_witness_cannot_change_span_or_predecessor_authority(self):
        witness = json.loads(self.encoded)
        for kind in ('offset', 'boolean-offset', 'missing', 'duplicate', 'before', 'after', 'path',
                     'base', 'previous', 'current', 'old-bytes', 'new-bytes', 'predecessor', 'scope', 'extra'):
            changed = deepcopy(witness)
            if kind == 'offset': changed['changes'][1]['new_start_line'] += 1
            elif kind == 'boolean-offset': changed['changes'][0]['old_start_line'] = True
            elif kind == 'missing': changed['changes'].pop()
            elif kind == 'duplicate': changed['changes'].append(deepcopy(changed['changes'][0]))
            elif kind in ('before', 'after'): changed['changes'][0][kind] += '# forged\n'
            elif kind == 'path': changed['path'] = 'src/biocompiler/core_pipeline_manager.py'
            elif kind == 'base': changed['base_revision'] = '0' * 40
            elif kind == 'previous': changed['original_sha256'] = source.OLD
            elif kind == 'current': changed['current_sha256'] = source.CURRENT
            elif kind == 'old-bytes': changed['original_bytes'] += 1
            elif kind == 'new-bytes': changed['current_bytes'] += 1
            elif kind == 'predecessor': changed['predecessor']['sha256'] = '0' * 64
            elif kind == 'scope': changed['scope'] = 'current acceptance'
            else: changed['unreviewed'] = True
            encoded = json.dumps(changed, sort_keys=True).encode()
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AssertionError, 'target witness bytes'):
                    source.restore_targets(self.current, encoded)
                with patch.object(source, 'TARGET_PIN', source.sha(encoded)), self.assertRaises(AssertionError):
                    source.restore_targets(self.current, encoded)

    def test_missing_linked_or_changed_new_witness_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / source.TARGET_WITNESS
            path.parent.mkdir(parents=True)
            with patch.object(source, 'ROOT', root):
                with self.assertRaisesRegex(AssertionError, 'Missing exact'):
                    source.restore_targets(self.current)
                path.write_bytes(self.encoded + b'\n')
                with self.assertRaisesRegex(AssertionError, 'target witness bytes'):
                    source.restore_targets(self.current)
                target = root / 'elsewhere.json'
                target.write_bytes(self.encoded)
                path.unlink()
                path.symlink_to(target)
                with self.assertRaisesRegex(AssertionError, 'Missing exact'):
                    source.restore_targets(self.current)

    def test_workflow_addition_requires_live_source_and_complete_old_chain(self):
        additions = {source.SOURCE: source.TARGET_CURRENT}
        self.assertEqual(workflow.REVIEWED_ADDITIONS[source.SOURCE], source.sha(self.current))
        with patch.object(source, 'restore_attempt', wraps=source.restore_attempt) as checked:
            self.assertEqual(workflow.addition_counterparts(additions), [])
            self.assertEqual(source.sha(checked.call_args.args[0]), source.CURRENT)
        with patch.object(source, 'PIN', '0' * 64), self.assertRaises(AssertionError):
            workflow.addition_counterparts(additions)
        with self.assertRaisesRegex(AssertionError, 'facade addition identity'):
            workflow.addition_counterparts({source.SOURCE: source.CURRENT})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / source.SOURCE
            path.parent.mkdir(parents=True)
            changed = self.current + b'\n'
            path.write_bytes(changed)
            with patch.object(workflow, 'ROOT', root), self.assertRaisesRegex(AssertionError, 'Unreviewed current'):
                workflow.addition_counterparts(additions)
            with patch.dict(workflow.REVIEWED_ADDITIONS, {source.SOURCE: source.sha(changed)}), \
                    self.assertRaisesRegex(AssertionError, 'facade addition identity'):
                workflow.addition_counterparts({source.SOURCE: source.sha(changed)})

    def test_installed_reference_source_closure_contains_both_witnesses_and_controls(self):
        from tools import check_pipeline_reference_install as installed
        for path in (source.WITNESS, source.TARGET_WITNESS, 'tools/reference_attempt_source.py',
                     'tests/test_reference_attempt_source.py', 'tests/test_reference_target_source_lineage.py'):
            self.assertEqual(installed.SOURCES.count(path), 1)
            self.assertTrue((source.ROOT / path).is_file())


if __name__ == '__main__':
    unittest.main()
