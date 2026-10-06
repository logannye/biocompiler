"""Synthetic source/receipt validation only; no original or native execution."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import tools
from tools import pipeline_original_counterpart as counterpart


class ClosureSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.directory) / 'first'
        self.current_manager, self.original_manager = b'current manager fixture\n', b'original manager fixture\n'
        self.current_tool, self.original_tool = b'current helper fixture\n', b'original helper fixture\n'
        self.route, self.tool_route = {'manager': 'synthetic exact route'}, {'helper': 'synthetic exact route'}
        self.enterContext(patch.object(counterpart, 'ROOT', self.root))
        self.enterContext(patch.object(counterpart, 'reference_routes', return_value={}))
        self.enterContext(patch.object(counterpart, 'policy_routes', return_value={}))
        self.enterContext(patch.object(counterpart.lineage, 'original_source', return_value=self.original_manager))
        self.enterContext(patch.object(counterpart.lineage, 'original_tool_source', return_value=self.original_tool))
        self.enterContext(patch.object(counterpart.lineage, 'verify_source', side_effect=self.verify_manager))
        self.enterContext(patch.object(counterpart.lineage, 'verify_tool_source', side_effect=self.verify_tool))
        self.enterContext(patch.object(counterpart.subprocess, 'run', side_effect=AssertionError('No child execution in source fixture')))
        self.enterContext(patch.object(counterpart.subprocess, 'Popen', side_effect=AssertionError('No child execution in source fixture')))
        self.indexes = {}
        self.index_values = {}
        for family, offset in (('fixed', 0), ('continuation', 161)):
            name = family + '-synthetic-index.json'
            value = {'source_files': {'tests/indexed_%03d.py' % i: 'synthetic source authority'
                                     for i in range(offset, offset + 161)},
                     'full_corpus': {'path': family + '-synthetic-corpus.json'},
                     'provider_directory': 'synthetic-providers', 'provider_documents': []}
            value['inventory_fingerprint'] = counterpart.lineage.sha(counterpart.canonical(value))
            self.indexes[family] = name, value['inventory_fingerprint']
            self.index_values[name] = value
        self.stub_module('check_pipeline_session_install', INDEXES=self.indexes)
        self.stub_module('check_pipeline_fixed_registration_install',
                         overlay_files=lambda: (counterpart.lineage.TOOL_PATH,))
        self.stub_module('reference_original_counterpart', ROUTE_WITNESS='tests/conformance/synthetic-reference-route.json')
        self.stub_module('policy_entrypoint_source_lineage', WITNESS='tests/conformance/synthetic-policy-route.json')
        self.write_root(self.root, 'first')
        self.value = self.receipt()
        self.assertEqual(len(self.value['manifest']['sources']), 343)

    def stub_module(self, name, **attributes):
        module = ModuleType('tools.' + name)
        vars(module).update(attributes)
        self.enterContext(patch.dict(sys.modules, {module.__name__: module}))
        self.enterContext(patch.object(tools, name, module, create=True))

    def verify_manager(self, root, logical, _historical):
        self.assertEqual(logical, counterpart.lineage.PATH)
        self.assertEqual((root / logical).read_bytes(), self.current_manager)
        return self.route

    def verify_tool(self, raw):
        self.assertEqual(raw, self.current_tool)
        return self.tool_route

    def write_root(self, root, label):
        def write(logical, raw):
            path = root / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        for name, value in self.index_values.items():
            write('tests/conformance/' + name, counterpart.canonical(value))
        with patch.object(counterpart, 'ROOT', root):
            for logical in counterpart.task_files('fixed-build-original'):
                write(logical, ('synthetic ' + label + ': ' + logical + '\n').encode())
            for logical in counterpart.task_data('fixed-build-original'):
                if not (root / logical).exists():
                    write(logical, b'{"synthetic_data":true}\n')
        write(counterpart.lineage.PATH, self.current_manager)
        write(counterpart.lineage.TOOL_PATH, self.current_tool)
        write('src/biocompiler/__init__.py', ('synthetic package ' + label + '\n').encode())

    def receipt(self, task='fixed-build-original', test_module=None):
        root = counterpart.ROOT
        overlay, package = root / 'overlay', root / 'installed/biocompiler'
        paths = set(counterpart.task_files(task, test_module)) | {
            'src/biocompiler/__init__.py', counterpart.lineage.PATH}
        rows = []
        for logical in sorted(paths):
            raw = (root / logical).read_bytes()
            copied = self.original_manager if logical == counterpart.lineage.PATH else (
                self.original_tool if logical == counterpart.lineage.TOOL_PATH else raw)
            origin = package / logical.removeprefix('src/biocompiler/') if logical.startswith('src/') else root / logical
            rows.append({'logical': logical, 'origin': str(origin),
                         'origin_sha256': counterpart.lineage.sha(raw), 'path': str(overlay / logical),
                         'sha256': counterpart.lineage.sha(copied), 'substituted': copied != raw})
        manager = next(row for row in rows if row['logical'] == counterpart.lineage.PATH)
        return {'manifest': {'schema': counterpart.SCHEMA, 'task': task, 'test_module': test_module,
                'test_ids': None, 'root': str(overlay), 'package_root': str(package),
                'route': self.route, 'tool_route': self.tool_route if counterpart.lineage.TOOL_PATH in paths else None,
                'reference_routes': {}, 'policy_routes': {}, 'sources': rows,
                'data': [{'logical': logical, 'sha256': counterpart.lineage.sha((root / logical).read_bytes())}
                         for logical in counterpart.task_data(task, test_module)]},
                'modules': {'biocompiler.compiler.pipeline': {
                    'logical': manager['logical'], 'path': manager['path'], 'sha256': manager['sha256'],
                    'namespace': 'biocompiler.compiler.pipeline'}},
                'value': {'synthetic_only': True, 'retained_results': ['first', 'second']}}

    def during_source_rows(self, action):
        original = Path.read_bytes
        trigger = self.root / 'tests/indexed_001.py'
        fired = []
        def read(path):
            raw = original(path)
            if path == trigger and not fired:
                fired.append(True)
                action()
            return raw
        return patch.object(Path, 'read_bytes', read), fired

    def test_complete_343_row_result_uses_four_fresh_index_pairs_per_validation(self):
        original = deepcopy(self.value)
        with patch.object(counterpart, 'build_indexes', wraps=counterpart.build_indexes) as indexes, \
             patch.object(counterpart, 'task_files', wraps=counterpart.task_files) as files, \
             patch.object(counterpart, 'task_data', wraps=counterpart.task_data) as data:
            for iteration in range(1, 3):
                self.assertIs(counterpart.validate(self.value), self.value['value'])
                self.assertEqual(indexes.call_count, 4 * iteration)
                self.assertEqual(files.call_count, 2 * iteration)
                self.assertEqual(data.call_count, 2 * iteration)
        self.assertEqual(self.value, original)

    def test_each_call_resolves_its_actual_root_and_task_without_cross_call_state(self):
        counterpart.validate(self.value)
        second = Path(self.directory) / 'second'
        self.write_root(second, 'second')
        with patch.object(counterpart, 'ROOT', second):
            other = self.receipt()
            self.assertIs(counterpart.validate(other), other['value'])
            with self.assertRaisesRegex(AssertionError, 'origin bytes differ'):
                counterpart.validate(self.value)
        for task in ('deferred', 'callbacks', 'fixed-build-original'):
            value = self.receipt(task)
            self.assertIs(counterpart.validate(value), value['value'])
        counterpart.validate(self.value)

    def test_invalid_or_self_rehashed_index_is_rejected_at_entry(self):
        name = self.indexes['fixed'][0]
        path = self.root / 'tests/conformance' / name
        original = path.read_bytes()
        for repin in (False, True):
            changed = deepcopy(self.index_values[name])
            changed['source_files']['tests/foreign.py'] = 'foreign'
            if repin:
                changed['inventory_fingerprint'] = counterpart.lineage.sha(counterpart.canonical({
                    key: value for key, value in changed.items() if key != 'inventory_fingerprint'}))
            path.write_bytes(counterpart.canonical(changed))
            with self.subTest(repin=repin), self.assertRaisesRegex(AssertionError, 'Original build source index differs'):
                counterpart.validate(self.value)
        path.write_bytes(original)

    def test_index_changed_during_row_traversal_is_rechecked(self):
        path = self.root / 'tests/conformance' / self.indexes['fixed'][0]
        def mutate():
            value = json.loads(path.read_bytes())
            value['source_files'].pop('tests/indexed_000.py')
            path.write_bytes(counterpart.canonical(value))
        guard, fired = self.during_source_rows(mutate)
        with guard, self.assertRaisesRegex(AssertionError, 'Original build source index differs'):
            counterpart.validate(self.value)
        self.assertEqual(fired, [True])

    def test_data_bytes_changed_during_row_traversal_are_rechecked(self):
        path = self.root / counterpart.DATA[0]
        guard, fired = self.during_source_rows(lambda: path.write_bytes(b'changed data'))
        with guard, self.assertRaisesRegex(AssertionError, 'data closure changed during validation'):
            counterpart.validate(self.value)
        self.assertEqual(fired, [True])

    def test_rehashed_index_and_changed_in_memory_pin_cannot_replace_entry_authority(self):
        name, old_pin = self.indexes['fixed']
        path = self.root / 'tests/conformance' / name
        def mutate():
            value = json.loads(path.read_bytes())
            value['source_files']['tests/indexed_000.py'] = 'changed original authority'
            value['inventory_fingerprint'] = counterpart.lineage.sha(counterpart.canonical({
                key: item for key, item in value.items() if key != 'inventory_fingerprint'}))
            path.write_bytes(counterpart.canonical(value))
            self.indexes['fixed'] = name, value['inventory_fingerprint']
            # Both fresh index checks now succeed, with the same file census.
            self.assertNotEqual(value['inventory_fingerprint'], old_pin)
            counterpart.build_indexes()
        guard, fired = self.during_source_rows(mutate)
        with guard, self.assertRaisesRegex(AssertionError, 'data closure changed during validation'):
            counterpart.validate(self.value)
        self.assertEqual(fired, [True])

    def test_already_checked_source_origin_is_rechecked_before_return(self):
        path = self.root / 'tests/indexed_000.py'
        guard, fired = self.during_source_rows(lambda: path.write_bytes(b'changed source'))
        with guard, self.assertRaisesRegex(AssertionError, 'source bytes changed during validation'):
            counterpart.validate(self.value)
        self.assertEqual(fired, [True])

    def test_mutated_row_task_module_or_result_cannot_change_the_validated_input(self):
        for mode in ('past_row', 'future_row', 'task', 'test_module', 'result'):
            value = deepcopy(self.value)
            def mutate():
                if mode in ('past_row', 'future_row'):
                    logical = 'tests/indexed_000.py' if mode == 'past_row' else 'tests/indexed_002.py'
                    row = next(row for row in value['manifest']['sources'] if row['logical'] == logical)
                    row['origin_sha256'] = '0' * 64
                elif mode == 'result': value['value']['retained_results'].reverse()
                else: value['manifest'][mode] = 'callbacks' if mode == 'task' else 'test_pipeline_callback_semantics'
            guard, fired = self.during_source_rows(mutate)
            expected = 'origin bytes differ' if mode == 'future_row' else 'inputs changed during validation'
            with self.subTest(mode=mode), guard, self.assertRaisesRegex(AssertionError, expected):
                counterpart.validate(value)
            self.assertEqual(fired, [True])

    def test_root_changed_during_row_traversal_is_rejected(self):
        original = counterpart.ROOT
        guard, fired = self.during_source_rows(lambda: setattr(counterpart, 'ROOT', original / 'other'))
        try:
            with guard, self.assertRaisesRegex(AssertionError, 'inputs changed during validation'):
                counterpart.validate(self.value)
        finally:
            counterpart.ROOT = original
        self.assertEqual(fired, [True])

    def test_source_and_data_closure_order_are_rechecked(self):
        for helper, message in (('task_files', 'source closure changed'), ('task_data', 'data closure changed')):
            actual = getattr(counterpart, helper)
            count = []
            def changing(*args):
                value = actual(*args)
                count.append(True)
                return tuple(reversed(value)) if len(count) == 2 else value
            with self.subTest(helper=helper), patch.object(counterpart, helper, side_effect=changing), \
                 self.assertRaisesRegex(AssertionError, message):
                counterpart.validate(self.value)
            self.assertEqual(len(count), 2)

    def test_package_census_changed_after_first_census_is_rejected(self):
        def verify(*args):
            result = self.verify_manager(*args)
            (self.root / 'src/biocompiler/extra.py').write_bytes(b'extra source')
            return result
        with patch.object(counterpart.lineage, 'verify_source', side_effect=verify), \
             self.assertRaisesRegex(AssertionError, 'package census changed during validation'):
            counterpart.validate(self.value)

    def test_closing_routes_and_final_input_are_rechecked(self):
        for mode in ('reference', 'policy', 'late_input'):
            value = deepcopy(self.value)
            helper = 'policy_routes' if mode == 'policy' else 'reference_routes'
            count = []
            def changed(*_args):
                count.append(True)
                if len(count) == 2:
                    if mode == 'late_input': value['value']['synthetic_only'] = False
                    else: return {'changed': (b'changed', {})}
                return {}
            expected = 'inputs changed' if mode == 'late_input' else 'source routes changed'
            with self.subTest(mode=mode), patch.object(counterpart, helper, side_effect=changed), \
                 self.assertRaisesRegex(AssertionError, expected):
                counterpart.validate(value)

    def test_original_row_module_and_result_checks_remain_mandatory(self):
        for mode in ('missing_row', 'duplicate_row', 'unknown_row', 'origin', 'copied_hash',
                     'substitution', 'source_path', 'installed_origin', 'tool_origin',
                     'missing_data', 'module_hash', 'module_namespace', 'route', 'tool_route'):
            value = deepcopy(self.value)
            manifest = value['manifest']
            row = next(row for row in manifest['sources'] if row['logical'] == counterpart.lineage.PATH)
            if mode == 'missing_row': manifest['sources'].remove(row)
            elif mode == 'duplicate_row': manifest['sources'].append(deepcopy(row))
            elif mode == 'unknown_row': row['logical'] = 'tools/foreign.py'
            elif mode == 'origin': row['origin_sha256'] = '0' * 64
            elif mode == 'copied_hash': row['sha256'] = row['origin_sha256']
            elif mode == 'substitution': row['substituted'] = False
            elif mode == 'source_path': row['path'] += '-foreign'
            elif mode == 'installed_origin': row['origin'] += '-foreign'
            elif mode == 'tool_origin':
                next(item for item in manifest['sources'] if item['logical'].startswith('tools/'))['origin'] = '/foreign/wrong.py'
            elif mode == 'missing_data': manifest['data'].pop()
            elif mode == 'module_hash': value['modules']['biocompiler.compiler.pipeline']['sha256'] = '0' * 64
            elif mode == 'module_namespace': value['modules']['biocompiler.compiler.pipeline']['namespace'] = 'foreign'
            else: manifest[mode] = {'forged': True}
            with self.subTest(mode=mode), self.assertRaises(AssertionError):
                counterpart.validate(value)


if __name__ == '__main__':
    unittest.main()
