"""Full original fixed-pipeline observations and source-bound manager lineage."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'tests/conformance/fixed-pipeline-literals-v1.json'
INVENTORY_PIN = '28d8befb9fad240a80edf341ad64f822517f6e65f43c611966c9d0b7ff43d652'
CONTINUATION_PIN = '6b364ddf4b06140d788466fa7af5236ebfd3361854809d92d0ca99e0cac898f1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_inventory(value, pin=INVENTORY_PIN):
    actual = sha(canonical({key: item for key, item in value.items() if key != 'inventory_fingerprint'}))
    if value.get('inventory_fingerprint') != pin or actual != pin:
        raise AssertionError('Complete original fixed-pipeline inventory changed')


def read_document(directory, item):
    path = directory / (item['id'] + '.json')
    if path.is_symlink() or not path.is_file():
        raise AssertionError('Unsafe original boundary document')
    raw = path.read_bytes()
    value = json.loads(raw)
    if len(raw) != item['bytes'] or raw != canonical(value) + b'\n' or sha(raw[:-1]) != item['id']:
        raise AssertionError('Complete original boundary bytes changed')
    return value


class FixedPipelineLiteralsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = INDEX.read_bytes()
        cls.value = json.loads(raw)
        if raw != canonical(cls.value) + b'\n':
            raise AssertionError('Original boundary index bytes changed')
        validate_inventory(cls.value)
        cls.directory = INDEX.parent / cls.value['document_directory']
        cls.documents = {item['id']: item for item in cls.value['documents']}
        reference = cls.value['prior_ledger']
        path = ROOT / reference['manifest']
        if sha(path.read_bytes()) != reference['manifest_sha256']:
            raise AssertionError('Original complete manager manifest changed')
        manifest = json.loads(path.read_bytes())
        archive = (path.parent / manifest['archive']['path']).read_bytes()
        if sha(archive) != manifest['archive']['sha256']:
            raise AssertionError('Original complete manager archive changed')
        expanded = gzip.decompress(archive)
        if sha(expanded) != manifest['archive']['uncompressed_sha256']:
            raise AssertionError('Original complete manager ledger changed')
        cls.prior = json.loads(expanded)
        if cls.prior['inventory_fingerprint'] != reference['inventory_fingerprint']:
            raise AssertionError('Original manager inventory identity changed')
        cls.events = {item['id']: item for item in cls.prior['events']}

    def test_all_original_methods_and_actual_occurrences_remain_accounted(self):
        self.assertEqual(self.value['original_methods'], self.prior['original_methods'])
        self.assertEqual(len(self.value['original_methods']), 467)
        methods = [item for item in self.value['contexts'] if item['kind'] == 'original_method']
        self.assertEqual([item['id'] for item in methods], self.value['original_methods'])
        self.assertTrue(any(not item['events'] for item in methods))
        self.assertEqual(self.value['subprocesses'], self.prior['baseline_subprocesses'])
        self.assertEqual(self.value['subprocess_function_calls'],
            [{'actual_fixed_pipeline_calls': []}, {'actual_fixed_pipeline_calls': []}])
        cases = self.value['cases']
        self.assertEqual(len(cases), self.value['coverage']['cases'])
        self.assertEqual(len({item['id'] for item in cases}), len(cases))
        self.assertEqual(Counter(item['api'] for item in cases), self.value['coverage']['operations'])
        self.assertEqual(Counter(item['kind'] for item in cases), self.value['coverage']['kinds'])
        self.assertEqual(Counter(item['outcome'] for item in cases), self.value['coverage']['outcomes'])
        self.assertEqual(self.value['coverage']['original_manager_constructors'], 309)
        self.assertEqual({item['api'] for item in cases}, {'run_synthetic_pipeline', 'run_component_pipeline'})

    def test_every_complete_input_return_error_source_and_document_is_preserved(self):
        self.assertEqual({path.name for path in self.directory.iterdir()}, {key + '.json' for key in self.documents})
        self.assertEqual(sum(item['bytes'] for item in self.documents.values()), self.value['coverage']['document_bytes'])
        for item in self.documents.values():
            read_document(self.directory, item)
        for path, pin in self.value['source_files'].items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        for path, pin in self.value['capture_support'].items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)
        tool = self.value['capture_tool']
        self.assertEqual(sha((ROOT / tool['path']).read_bytes()), tool['sha256'])
        cases = {item['id']: item for item in self.value['cases']}
        for item in cases.values():
            for key in ('arguments', 'authority', 'locals_at_exit'):
                self.assertIn(item[key], self.documents)
            self.assertIn(item['source']['file'], self.value['source_files'])
            if item['parent'] is not None:
                self.assertIn(item['parent'], cases)
            if item['outcome'] == 'returned':
                self.assertIn(item['result'], self.documents)
                self.assertNotIn('error', item)
                if item['kind'] == 'actual_original_function':
                    records = read_document(self.directory, self.documents[item['complete_records']])
                    self.assertTrue({'candidate', 'selection_result', 'stages'} <= set(records))
                    self.assertTrue({'request', 'behavior', 'mechanism'} <= set(records['stages']))
                    if item['api'] == 'run_component_pipeline':
                        self.assertTrue({'assembly', 'link_result', 'behavior_result'} <= set(records))
                        self.assertIn('components', records['stages'])
            else:
                self.assertEqual(set(item['error']), {'module', 'type', 'message'})
                self.assertNotIn('result', item)

    def test_manager_lineage_retains_complete_internal_and_after_return_freshness_events(self):
        all_events = self.prior['events']
        stale, callbacks, dependency_updates = 0, 0, 0
        for case in self.value['cases']:
            binding = case['manager_ledger']
            if binding is None:
                self.assertIsNone(case['manager_state'])
                continue
            self.assertIn(case['manager_state'], self.documents)
            original = [item['id'] for item in all_events if item['manager'] == binding['manager']]
            self.assertEqual(binding['events'], original)
            constructor = self.events[binding['constructor_event']]
            self.assertEqual(constructor['api'], 'PassManager.__init__')
            self.assertEqual(constructor['manager'], binding['manager'])
            self.assertEqual(constructor['context'], binding['context'])
            for identity in original:
                event = self.events[identity]
                callbacks += event['api'] == 'callback.invoke'
                dependency_updates += event['api'] == 'PassManager.set_dependency'
                stale += event['outcome'] == 'raised' and 'Stale' in event['error']['message']
        self.assertGreater(stale, 0)
        self.assertGreater(callbacks, 0)
        self.assertGreater(dependency_updates, 0)

    def test_invalid_python_inputs_patched_callbacks_and_mocked_boundaries_remain_explicit(self):
        cases = self.value['cases']
        mocked = [item for item in cases if item['kind'] == 'mocked_boundary']
        self.assertTrue(mocked)
        self.assertTrue(all(item['outcome'] == 'raised' for item in mocked))
        self.assertTrue(all(item['mock_calls_after'] == item['mock_calls_before'] + 1 for item in mocked))
        self.assertTrue(any(item['python_only_inputs'] for item in cases))
        mutations = [item for item in cases if item['changed_bindings']]
        self.assertTrue(mutations)
        self.assertTrue(any('PassManager.register' in item['changed_bindings'] for item in mutations))
        for item in cases:
            self.assertEqual(item['native_replay'], 'pending_real_native_fixed_pipeline_execution')
            for provider in item['runtime_bindings'].values():
                self.assertIn(provider['id'], self.value['providers'])

    def test_continuation_projection_is_complete_exact_and_keeps_pending_suffixes(self):
        from tools.project_fixed_pipeline_continuations import derive
        path = INDEX.with_name('fixed-pipeline-continuations-v1.json')
        raw = path.read_bytes()
        value = json.loads(raw)
        self.assertEqual(raw, canonical(value) + b'\n')
        self.assertEqual(value['inventory_fingerprint'], CONTINUATION_PIN)
        self.assertEqual(sha(canonical({key: item for key, item in value.items() if key != 'inventory_fingerprint'})), CONTINUATION_PIN)
        self.assertEqual(value['fixed_index_sha256'], sha(INDEX.read_bytes()))
        self.assertEqual(value['prior_ledger'], self.value['prior_ledger'])
        generator = value['generator']
        self.assertEqual(sha((ROOT / generator['path']).read_bytes()), generator['sha256'])
        directory = INDEX.parent / self.prior['document_directory']
        descriptors = {item['id']: item for item in self.prior['documents']}
        expected = derive(self.value, self.prior, lambda identity: read_document(directory, descriptors[identity]))
        actual = {key: item for key, item in value.items() if key not in
                  ('inventory_fingerprint', 'generator', 'fixed_index_sha256', 'prior_ledger')}
        self.assertEqual(actual, expected)
        self.assertGreater(value['coverage']['supported_prefix_observations'], 0)
        self.assertGreater(value['coverage']['pending_suffix_observations'], 0)
        for entry in value['entries']:
            if entry['boundary'] is not None:
                self.assertEqual([item['id'] for item in entry['events']],
                    entry['supported_prefix_events'] + entry['pending_callback_dependent_suffix'])
            else:
                self.assertEqual(entry['native_partial_failure_state'], 'pending_inspection_outcome_api')

    def test_bounded_native_companions_preserve_all_complete_provider_bytes(self):
        from tools.project_fixed_pipeline_native import project, nodes
        pairs = (
            ('fixed-pipeline-literals-v1.json', 'fixed-pipeline-native-v1.json',
             'ce976b30aa5e0a8f6477cc027d7bec4a780a31a567f19cfb0993b10839d58f6d'),
            ('fixed-pipeline-continuations-v1.json', 'fixed-pipeline-continuations-native-v1.json',
             '45c78ef53692cb71fe644ea98331c9ce8caa1bda3b1eab67a93061f30557a9eb'))
        retained = {}
        for source, native, pin in pairs:
            source_bytes = (INDEX.parent / source).read_bytes()
            full = json.loads(source_bytes)
            raw = (INDEX.parent / native).read_bytes()
            value = json.loads(raw)
            self.assertEqual(raw, canonical(value) + b'\n')
            validate_inventory(value, pin)
            self.assertLess(nodes(value), 1000000)
            self.assertLess(len(raw), 64 * 1024 * 1024)
            expected, records = project(full, source, source_bytes)
            actual = {key: item for key, item in value.items() if key not in
                      ('inventory_fingerprint', 'projection_generator')}
            self.assertEqual(actual, expected)
            generator = value['projection_generator']
            self.assertEqual(sha((ROOT / generator['path']).read_bytes()), generator['sha256'])
            self.assertEqual({item['id']: item['bytes'] for item in value['provider_documents']},
                             {key: len(content) for key, content in records.items()})
            directory = INDEX.parent / value['provider_directory']
            for identity, content in records.items():
                path = directory / (identity + '.json')
                self.assertFalse(path.is_symlink())
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual(sha(content[:-1]), identity)
                retained[identity] = content
            identity = next(iter(value['providers']))
            forged = {**value, 'providers': {**value['providers'],
                      identity: {**value['providers'][identity], 'class': 'forged'}}}
            forged['inventory_fingerprint'] = sha(canonical({key: item for key, item in forged.items() if key != 'inventory_fingerprint'}))
            with self.assertRaisesRegex(AssertionError, 'inventory changed'):
                validate_inventory(forged, pin)
        self.assertEqual({path.name for path in directory.iterdir()}, {key + '.json' for key in retained})

    def test_rehashed_case_error_return_or_lineage_forgery_cannot_replace_original_evidence(self):
        case = self.value['cases'][0]
        bound = next(index for index, item in enumerate(self.value['cases']) if item['manager_ledger'] is not None)
        without_lineage = list(self.value['cases'])
        without_lineage[bound] = {**without_lineage[bound], 'manager_ledger': None}
        variants = ({'cases': self.value['cases'][:-1]},
                    {'cases': [{**case, 'outcome': 'returned', 'result': '0' * 64}, *self.value['cases'][1:]]},
                    {'cases': without_lineage},
                    {'original_methods': self.value['original_methods'][:-1]})
        for change in variants:
            value = {**self.value, **change}
            value['inventory_fingerprint'] = sha(canonical({key: item for key, item in value.items() if key != 'inventory_fingerprint'}))
            with self.assertRaisesRegex(AssertionError, 'inventory changed'):
                validate_inventory(value)

    def test_equal_json_different_bytes_is_not_original_observation(self):
        item = next(iter(self.documents.values()))
        value = read_document(self.directory, item)
        raw = canonical(value) + b' \n'
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / (item['id'] + '.json')).write_bytes(raw)
            with self.assertRaisesRegex(AssertionError, 'boundary bytes changed'):
                read_document(Path(directory), {**item, 'bytes': len(raw)})


if __name__ == '__main__':
    unittest.main()
