"""Exact original authority and complete reference-foundation capture controls."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('freeze_reference_contracts', ROOT / 'tools/freeze_reference_contracts.py')
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)
INVENTORY = '69c26f9329ec1d3a40e17a0a5f70d311611121d57b9b9f9962163678b1dc952c'


class ReferenceContractsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.docs = oracle.load()

    def repaired(self):
        return deepcopy(self.index)

    def reject(self, value, pattern):
        value['inventory_fingerprint'] = oracle.inventory(value)
        with self.assertRaisesRegex(AssertionError, pattern):
            oracle.validate(value, self.docs, sources=False)

    def test_frozen_complete_inventory_and_bounded_native_input(self):
        self.assertEqual(self.index['inventory_fingerprint'], INVENTORY)
        self.assertEqual(len(self.index['test_ids']), 72)
        self.assertEqual(len(self.index['observations']), 22584)
        self.assertEqual(len(self.docs), 4000)
        self.assertEqual(sum(x['bytes'] for x in self.index['documents'].values()), 34923274)
        self.assertEqual(set(self.index['documents']), {p.stem for p in oracle.DOCUMENTS.glob('*.json')})
        self.assertLessEqual(oracle.CORPUS.stat().st_size, 16 * 1024 * 1024)
        stack, nodes = [self.index], 0
        while stack:
            value = stack.pop()
            nodes += 1
            if isinstance(value, dict):
                stack.extend(x for pair in value.items() for x in pair)
            elif isinstance(value, list):
                stack.extend(value)
        self.assertLessEqual(nodes, 1_000_000)

    def test_complete_fresh_original_capture_matches_every_byte_value(self):
        index, docs = oracle.capture()
        oracle.validate(index, docs)
        self.assertEqual(index, self.index)
        self.assertEqual(docs, self.docs)

    def test_every_original_method_and_outcome_remains_required(self):
        value = self.repaired()
        value['test_ids'].pop()
        value['test_outcomes'].pop()
        self.reject(value, 'per-test census')
        value = self.repaired()
        value['test_outcomes'][0]['status'] = 'fail'
        self.reject(value, 'accounting')

    def test_unknown_operations_missing_authority_and_duplicate_ids_reject(self):
        value = self.repaired()
        row = next(x for x in value['observations'] if x['operation'] == 'check-molecular')
        del row['inputs']['registry']
        self.reject(value, 'incomplete original authority')
        value = self.repaired()
        value['observations'][0]['operation'] = 'accept-cached-result'
        self.reject(value, 'Unknown operation')
        value = self.repaired()
        value['observations'][1]['id'] = value['observations'][0]['id']
        self.reject(value, 'Duplicate reference observation')

    def test_public_and_layout_fingerprints_are_bound_to_complete_return(self):
        value = self.repaired()
        row = next(x for x in value['observations'] if 'fingerprint' in x['outcome'])
        row['outcome']['fingerprint'] = '0' * 64
        self.reject(value, 'public fingerprint')
        value = self.repaired()
        row = next(x for x in value['observations'] if 'layout_fingerprint' in x['outcome'])
        row['outcome']['layout_fingerprint'] = '0' * 64
        self.reject(value, 'layout fingerprint')

    def test_complete_expected_documents_cannot_be_swapped_or_omitted(self):
        value = self.repaired()
        row = next(x for x in value['observations'] if 'json' in x['outcome'])
        row['outcome']['value'] = next(key for key, raw in self.docs.items() if raw is None)
        self.reject(value, 'complete JSON return')
        docs = dict(self.docs)
        docs.pop(next(iter(docs)))
        with self.assertRaisesRegex(AssertionError, 'document inventory'):
            oracle.validate(self.index, docs, sources=False)

    def test_checker_mutations_and_rich_supported_schema_remain_distinct(self):
        operations = self.index['operation_counts']
        self.assertGreaterEqual(operations['check-construct'], 89)
        self.assertGreaterEqual(operations['check-molecular'], 42)
        self.assertEqual(operations['emit-reference-sequence'], 44)
        checker_returns = [self.docs[r['outcome']['value']] for r in self.index['observations']
            if r['operation'] in ('check-construct', 'check-molecular') and r['outcome']['status'] == 'return']
        self.assertTrue({'pass', 'fail', 'unsupported'} <= {r['outcome'] for r in checker_returns})
        diagnoses = [d for r in checker_returns for d in r['diagnostics']]
        self.assertTrue(any(d['code'] == 'exact_reference' for d in diagnoses))
        rich = [self.docs[r['outcome']['value']] for r in self.index['observations']
            if r['operation'] == 'decode-construct-candidate' and r['outcome']['status'] == 'return']
        self.assertTrue(any(x['junctions'] and x['dependencies'] and x['regulatory_relations'] for x in rich))
        # Reports are never authority slots, even when replaying their original inputs.
        for row in self.index['observations']:
            if row['operation'] in ('check-construct', 'check-molecular', 'emit-reference-sequence'):
                self.assertNotIn('result', row['inputs'])
                self.assertNotIn('accepted', row['inputs'])

    def test_source_code_and_real_module_namespace_are_required(self):
        with oracle.source_paths():
            kinds, functions = oracle.definitions()
        oracle.verify_functions(kinds, functions)
        fn = functions['generate-construct']
        clone = types.FunctionType(fn.__code__, dict(fn.__globals__), fn.__name__, fn.__defaults__, fn.__closure__)
        clone.__module__ = fn.__module__
        with self.assertRaisesRegex(AssertionError, 'namespace'):
            oracle.verify_functions(kinds, functions | {'generate-construct': clone})
        namespace = fn.__globals__
        replacement = types.FunctionType((lambda request: request).__code__, namespace)
        replacement.__module__ = fn.__module__
        with self.assertRaisesRegex(AssertionError, 'source differs'):
            oracle.verify_functions(kinds, functions | {'generate-construct': replacement})


if __name__ == '__main__':
    unittest.main()


def load_tests(loader, tests, pattern):
    from tools.reference_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, __name__)
