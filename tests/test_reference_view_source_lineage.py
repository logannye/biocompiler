"""Exact structural-view source and registration-site lineage; no execution."""
from copy import deepcopy
import dis
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import CodeType
import unittest
from unittest.mock import patch

from tools import reference_original_counterpart as original
from tools import check_realization_workflow_corpus as workflow
from tools import pipeline_registration_guard as registration


class ReferenceViewSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.current = (original.ROOT / original.CORE_SOURCE).read_bytes()
        self.encoded = (original.ROOT / original.CORE_VIEW_UPDATE).read_bytes()

    def test_new_then_unchanged_old_chain_restores_complete_original_module(self):
        previous, update = original.core_view_source_witness(self.current)
        self.assertEqual((len(previous), original.sha(previous)), (93594, original.CORE_PRE_VIEW_SHA))
        old = json.loads((original.ROOT / original.CORE_ATTEMPT_UPDATE).read_bytes())
        self.assertEqual(old['current_sha256'], original.sha(previous))
        self.assertEqual(update['correspondence']['predecessor'],
            {'path': original.CORE_ATTEMPT_UPDATE, 'sha256': original.CORE_ATTEMPT_UPDATE_SHA})
        restored, proof = original.core_source_witness(self.current)
        self.assertEqual(restored, (original.ROOT / original.CORE_BLOB).read_bytes())
        self.assertEqual(original.sha(restored), original.CORE_ORIGINAL_SHA)
        self.assertEqual(proof['attempt_update']['correspondence'], old)
        self.assertEqual(proof['view_update'], update)
        self.assertEqual(proof['current_sha256'], original.sha(self.current))

    def test_stale_changed_and_unrelated_source_bytes_are_rejected(self):
        previous, _ = original.core_view_source_witness(self.current)
        for raw in (previous, (original.ROOT / original.CORE_BLOB).read_bytes(), self.current + b'\n',
                self.current.replace(b"names = ('scope', 'stage', 'schema', 'obligations')",
                                     b"names = ('stage', 'scope', 'schema', 'obligations')", 1),
                self.current.replace(b'def _native_register(', b'def unreviewed_register(', 1)):
            with self.subTest(sha=original.sha(raw)), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                original.core_source_witness(raw)

    def test_rehashed_witness_cannot_expand_exact_spans_or_predecessor(self):
        witness = json.loads(self.encoded)
        for kind in ('offset', 'missing', 'duplicate', 'before', 'after', 'path', 'base',
                     'previous', 'current', 'bytes', 'predecessor', 'scope', 'extra'):
            changed = deepcopy(witness)
            if kind == 'offset': changed['changes'][0]['new_start_line'] += 1
            elif kind == 'missing': changed['changes'].clear()
            elif kind == 'duplicate': changed['changes'].append(deepcopy(changed['changes'][0]))
            elif kind in ('before', 'after'): changed['changes'][0][kind] += '# forged\n'
            elif kind == 'path': changed['path'] = original.CALLBACK_SOURCE
            elif kind == 'base': changed['base_revision'] = '0' * 40
            elif kind == 'previous': changed['original_sha256'] = original.CORE_ORIGINAL_SHA
            elif kind == 'current': changed['current_sha256'] = original.CORE_PRE_VIEW_SHA
            elif kind == 'bytes': changed['original_bytes'] += 1
            elif kind == 'predecessor': changed['predecessor']['sha256'] = '0' * 64
            elif kind == 'scope': changed['scope'] = 'current acceptance'
            else: changed['unreviewed'] = True
            encoded = original.canonical(changed) + b'\n'
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AssertionError, 'view source witness changed'):
                    original.core_view_source_witness(self.current, encoded)
                with patch.object(original, 'CORE_VIEW_UPDATE_SHA', original.sha(encoded)), self.assertRaises(AssertionError):
                    original.core_view_source_witness(self.current, encoded)

    def test_workflow_addition_requires_exact_live_source_and_complete_chain(self):
        additions = {original.CORE_SOURCE: original.CORE_CURRENT_SHA}
        self.assertEqual(workflow.REVIEWED_ADDITIONS[original.CORE_SOURCE], original.sha(self.current))
        with patch.object(original, 'core_source_witness', wraps=original.core_source_witness) as checked:
            proof = workflow.addition_counterparts(additions)
            self.assertEqual(proof, [original.core_source_witness(self.current)[1]])
            self.assertEqual(checked.call_args_list[0].args, (self.current,))
        with patch.object(original, 'CORE_VIEW_UPDATE_SHA', '0' * 64), self.assertRaisesRegex(AssertionError, 'view source witness changed'):
            workflow.addition_counterparts(additions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / original.CORE_SOURCE
            path.parent.mkdir(parents=True)
            changed = self.current + b'# unreviewed\n'
            path.write_bytes(changed)
            with patch.object(workflow, 'ROOT', root), patch.dict(workflow.REVIEWED_ADDITIONS,
                    {original.CORE_SOURCE: original.sha(changed)}), self.assertRaisesRegex(AssertionError, 'Core addition identity'):
                workflow.addition_counterparts({original.CORE_SOURCE: original.sha(changed)})

    def test_new_witness_is_in_complete_data_and_source_closure_without_execution(self):
        index = original.authority()
        data = original.data_closure(index)
        self.assertEqual(len(data), 4013)
        self.assertEqual([row for row in data if row['logical'] == original.CORE_VIEW_UPDATE],
            [{'logical': original.CORE_VIEW_UPDATE, 'sha256': original.CORE_VIEW_UPDATE_SHA,
              'bytes': len(self.encoded)}])
        sources, _ = original.source_closure(index, original.ROOT / 'src/biocompiler')
        self.assertEqual(len(sources), 207)
        _, current, copied = sources[original.CORE_SOURCE]
        self.assertEqual(current, self.current)
        self.assertEqual(copied, (original.ROOT / original.CORE_BLOB).read_bytes())

    def test_native_source_gate_retains_entire_old_body_and_same_finite_authority(self):
        source = (original.ROOT / 'core/test/test_reference_contracts_corpus.ml').read_text()
        session_start = source.index('let reference_session_original ')
        session_end = source.index('let reference_original root ')
        source = (source[:session_start] + source[session_end:]).replace(
            '    else if name="src/biocompiler/core_pipeline_session.py" then\n'
            '      reference_session_original root name expected current\n', '', 1)
        start = source.index('let reference_manager_view_original ')
        end = source.index('let reference_manager_original ')
        update = source[start:end]
        added = '  let current=reference_manager_view_original root name current in\n'
        self.assertEqual(source.count(added), 1)
        restored = (source[:start] + source[end:]).replace(added, '')
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),
                         'f18d50b65996c7c77b5fffcddffba47cf878f2cd57a77d666841c1f94f48fe14')
        for value in (original.CORE_CURRENT_SHA, original.CORE_PRE_VIEW_SHA, original.CORE_VIEW_UPDATE,
                original.CORE_VIEW_UPDATE_SHA, original.CORE_ATTEMPT_UPDATE, original.CORE_ATTEMPT_UPDATE_SHA,
                'spans=[112,117,112,139]', 'String.length restored=93594', 'Canonical.sha256 restored=previous_pin'):
            self.assertIn(value, update)
        # Literal OCaml authority consistency only; compilation remains hosted.

    def test_registration_sites_are_actual_source_derived_with_only_line_shift(self):
        old_path = original.ROOT / 'tests/conformance/manager-registration-runtime-sites-v5.json'
        self.assertEqual(original.sha(old_path.read_bytes()),
                         'd3ce9b28fd52b2ce0b4b26e715cdf90a20da1192a0dca53d5d422269159e4de0')
        previous = json.loads(old_path.read_bytes())
        path = original.ROOT / registration.RUNTIME_SITES
        self.assertEqual(original.sha(path.read_bytes()), registration.RUNTIME_PIN)
        current = json.loads(path.read_bytes())
        self.assertEqual([row['runtime'] for row in previous['runtimes']], [[3, 11], [3, 14]])
        self.assertEqual([row['runtime'] for row in current['runtimes']], [[3, 11], [3, 14]])
        self.assertEqual(current['derivation']['source_update'],
            {'path': original.CORE_VIEW_UPDATE, 'sha256': original.CORE_VIEW_UPDATE_SHA})
        for before, after in zip(previous['runtimes'], current['runtimes']):
            self.assertEqual(after, {**before, 'source_sha256': original.CORE_CURRENT_SHA,
                'sites': [{**site, 'line': None if site['line'] is None else site['line'] + 22}
                          for site in before['sites']]})
            self.assertEqual(registration.runtime_authority(after['runtime']), after)
        def codes(code):
            yield code
            for value in code.co_consts:
                if type(value) is CodeType:
                    yield from codes(value)
        code = next(value for value in codes(compile(self.current, original.CORE_SOURCE, 'exec', dont_inherit=True))
                    if value.co_qualname == 'CorePassManager._native_register')
        actual = registration.runtime_authority(list(sys.version_info[:2]))
        self.assertEqual(original.sha(code.co_code), actual['bytecode_sha256'])
        self.assertEqual(original.sha(code.co_linetable), actual['line_table_sha256'])
        self.assertEqual([{'line': item.positions.lineno, 'offset': item.offset, 'opcode': item.opname}
            for item in dis.get_instructions(code, show_caches=True)], actual['sites'])
        with patch.object(registration, 'RUNTIME_PIN', '0' * 64), self.assertRaisesRegex(AssertionError, 'runtime-site witness changed'):
            registration.runtime_authority(list(sys.version_info[:2]))


if __name__ == '__main__':
    unittest.main()
