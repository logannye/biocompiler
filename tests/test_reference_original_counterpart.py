"""Finite original source execution, complete retained outcomes, and mutations."""
from copy import deepcopy
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import reference_original_counterpart as original


class ReferenceOriginalCounterpartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = original.run(test_module='tests.test_reference_contracts_corpus')

    def test_actual_original_methods_and_exact_frozen_source_closure(self):
        receipt = self.receipt
        value = original.validate(receipt)
        self.assertEqual(value['tests'], 8)
        self.assertEqual([row['status'] for row in value['outcomes']], ['success'] * 8)
        self.assertEqual(len(receipt['source_inventory']), 203)
        rows = {row['logical']: row for row in receipt['manifest']['sources']}
        self.assertEqual(len(rows), 207)
        product = [name for name in rows if name.startswith('src/biocompiler/')]
        self.assertEqual(len(product), 190)
        self.assertNotIn('src/biocompiler/core_reference_views.py', product)
        manager = rows['src/biocompiler/compiler/pipeline.py']
        self.assertEqual(manager['sha256'], 'dccba32618ecc7923b8a02ff54f114d515ff4e50908f45e27a8cda0a3f531be0')
        self.assertFalse(manager['substituted'])
        self.assertEqual([name for name, row in rows.items() if row['substituted']], sorted([original.CORE_SOURCE, original.TEST, *original.ROUTE_SOURCES]))
        self.assertEqual(rows[original.CORE_SOURCE]['origin_sha256'], original.CORE_CURRENT_SHA)
        self.assertEqual(rows[original.CORE_SOURCE]['sha256'], original.CORE_ORIGINAL_SHA)
        self.assertEqual(len(receipt['manifest']['data']), 4005)
        self.assertEqual(rows[original.TEST]['sha256'], original.TEST_SHA)
        self.assertEqual(receipt['modules']['biocompiler.compiler.pipeline']['namespace'], 'biocompiler.compiler.pipeline')
        self.assertTrue(all(row['class'] == 'tests.test_reference_contracts_corpus.ReferenceContractsCorpusTests'
                            for row in value['outcomes']))

    def test_whole_original_test_bytes_and_exact_single_hook_are_required(self):
        witness = original.test_witness()
        before, after = witness['original_source'].encode(), witness['current_source'].encode()
        self.assertEqual(original.sha(before), original.TEST_SHA)
        self.assertEqual(after, before + original.HOOK.encode())
        self.assertIsNone(original.test_witness(before)['hook'])
        changes = [after + b'\n# arbitrary addition\n', after + original.HOOK.encode(),
                   after.replace(b'self.assertEqual(len(self.docs), 4000)', b'self.assertEqual(len(self.docs), 1)'),
                   after.replace(b'return original_test_suite(loader, tests, pattern, __name__)', b'return tests')]
        for data in changes:
            with self.subTest(hash=original.sha(data)), self.assertRaisesRegex(AssertionError, 'bridge extension|whole original'):
                original.test_witness(data)

    def test_source_copy_module_and_complete_data_mutations_reject(self):
        for kind in ('old-manager', 'missing-source', 'extra-source', 'origin', 'copied-path',
                     'missing-data', 'data-hash', 'data-bytes', 'test-witness', 'namespace',
                     'module-path', 'missing-module', 'inventory', 'narrowed-tests', 'core-witness', 'core-update', 'route-witness', 'current-core-copy'):
            value = deepcopy(self.receipt)
            manifest = value['manifest']
            rows = manifest['sources']
            manager = next(row for row in rows if row['logical'] == 'src/biocompiler/compiler/pipeline.py')
            if kind == 'old-manager': manager['sha256'] = '2b1dea35ac3c861f1e933cf7808a241f1f6596e59cc04ceb0ec32e4a54d27331'
            elif kind == 'missing-source': rows.pop()
            elif kind == 'extra-source': rows.append(rows[-1].copy())
            elif kind == 'origin': manager['origin'] += '.changed'
            elif kind == 'copied-path': manager['path'] += '.changed'
            elif kind == 'missing-data': manifest['data'].pop()
            elif kind == 'data-hash': manifest['data'][-1]['sha256'] = '0' * 64
            elif kind == 'data-bytes': manifest['data'][-1]['bytes'] -= 1
            elif kind == 'test-witness': manifest['test_witness']['original_source'] += '\n'
            elif kind == 'namespace': value['modules']['biocompiler.compiler.pipeline']['namespace'] = 'oracle.pipeline'
            elif kind == 'module-path': value['modules']['biocompiler.compiler.pipeline']['path'] += '.changed'
            elif kind == 'missing-module': del value['modules']['biocompiler.compiler.pipeline']
            elif kind == 'inventory': value['source_inventory'].pop(next(iter(value['source_inventory'])))
            elif kind == 'core-witness': manifest['core_source_witness']['correspondence']['changes'][0]['after'] += '# extra\n'
            elif kind == 'core-update': manifest['core_source_witness']['update']['correspondence']['changes'][0]['after'] += '# extra\n'
            elif kind == 'route-witness': manifest['route_source_witnesses'][0]['correspondence']['insertion']['byte_offset'] += 1
            elif kind == 'current-core-copy':
                core = next(row for row in rows if row['logical'] == original.CORE_SOURCE)
                core['sha256'] = core['origin_sha256']
                core['substituted'] = False
            else:
                manifest['test_ids'].pop()
                value['value']['test_ids'].pop()
                value['value']['outcomes'].pop()
                value['value']['tests'] -= 1
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                original.validate(value)

    def test_new_unreferenced_source_is_excluded_but_changed_captured_source_rejects(self):
        index = original.authority()
        import biocompiler
        sources, _ = original.source_closure(index, Path(biocompiler.__file__).resolve().parent)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for logical, (_, current, _) in sources.items():
                target = root / logical
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(current)
            target = root / original.CORPUS
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((original.ROOT / original.CORPUS).read_bytes())
            for logical in (original.CORE_BLOB, original.CORE_WITNESS, original.CORE_UPDATE,
                            original.CORE_MERGE_UPDATE, original.ROUTE_WITNESS):
                target = root / logical
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((original.ROOT / logical).read_bytes())
            extra = root / 'src/biocompiler/unreferenced_new_module.py'
            extra.write_text('raise AssertionError("New code must not execute as old authority")\n')
            with patch.object(original, 'ROOT', root):
                actual, _ = original.source_closure(index, root / 'src/biocompiler')
                self.assertEqual(set(actual), set(sources))
                source = root / 'src/biocompiler/compiler/pipeline.py'
                source.write_bytes(source.read_bytes() + b'\n# changed captured code\n')
                with self.assertRaisesRegex(AssertionError, 'Captured reference source bytes changed'):
                    original.source_closure(index, root / 'src/biocompiler')

    def test_only_exact_six_span_core_revision_restores_complete_archive(self):
        current = (original.ROOT / original.CORE_SOURCE).read_bytes()
        archived, proof = original.core_source_witness(current)
        self.assertEqual(original.sha(current), original.CORE_CURRENT_SHA)
        self.assertEqual(original.sha(archived), original.CORE_ORIGINAL_SHA)
        self.assertEqual(archived, (original.ROOT / original.CORE_BLOB).read_bytes())
        self.assertEqual(len(proof['correspondence']['changes']), 6)
        self.assertEqual(len(proof['update']['correspondence']['changes']), 1)
        self.assertEqual(proof['update']['correspondence']['predecessor']['sha256'], original.CORE_WITNESS_SHA)
        extension = proof['ordered_merge_update']['correspondence']
        self.assertEqual(extension['predecessor'], {'path': original.CORE_UPDATE, 'sha256': original.CORE_UPDATE_SHA})
        self.assertEqual(extension['original_sha256'], original.CORE_ROUTING_SHA)
        self.assertEqual(len(extension['changes']), 4)
        self.assertIn('current native bridge validation is separate', proof['scope'])
        for changed in (current + b'\n', archived,
                        current.replace(b'_require_native_manager(self)', b'_require_native_manager(None)', 1)):
            with self.subTest(pin=original.sha(changed)), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                original.core_source_witness(changed)
        changed = deepcopy(self.receipt)
        changed['manifest']['core_source_witness']['ordered_merge_update']['correspondence']['changes'][-1]['after'] += '# forged\n'
        with self.assertRaises(AssertionError):
            original.validate(changed)
        witness = deepcopy(self.receipt)
        del witness['manifest']['core_source_witness']
        with self.assertRaisesRegex(AssertionError, 'Malformed original reference manifest'):
            original.validate(witness)

    def test_exact_public_prefixes_restore_whole_original_source(self):
        index = original.authority()
        for path in original.ROUTE_SOURCES:
            current = (original.ROOT / path).read_bytes()
            restored, proof = original.route_source_witness(path, current)
            self.assertEqual(original.sha(restored), index['source_files'][path])
            insertion = proof['correspondence']['insertion']
            offset, prefix = insertion['byte_offset'], insertion['text'].encode()
            self.assertEqual(current, restored[:offset] + prefix + restored[offset:])
            for changed in (current + b'\n', restored,
                            current.replace(b'return _reference_route.', b'return other.', 1),
                            current[:offset] + prefix + current[offset:]):
                with self.subTest(path=path, pin=original.sha(changed)), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                    original.route_source_witness(path, changed)
        with self.assertRaisesRegex(AssertionError, 'Unknown reference route'):
            original.route_source_witness('src/biocompiler/compiler/pipeline.py')

    def test_same_byte_relocated_package_cannot_replace_actual_import_origin(self):
        value = deepcopy(self.receipt)
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'biocompiler'
            package.mkdir()
            for row in value['manifest']['sources']:
                if row['logical'].startswith('src/biocompiler/'):
                    target = package / row['logical'].removeprefix('src/biocompiler/')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(Path(row['origin']).read_bytes())
                    self.assertEqual(original.sha(target.read_bytes()), row['origin_sha256'])
                    row['origin'] = str(target)
            value['manifest']['package_root'] = str(package)
            with self.assertRaisesRegex(AssertionError, 'installed package origin differs'):
                original.validate(value)

    def test_original_instances_and_each_actual_failure_status_are_forwarded(self):
        module = importlib.import_module('tests.test_reference_contracts_corpus')
        cls = module.ReferenceContractsCorpusTests
        cases = list(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        identities = [case.id() for case in cases]
        classname = cls.__module__ + '.' + cls.__qualname__
        value = self.receipt['value']
        self.assertEqual(value['test_ids'], identities)
        for kind in ('missing', 'duplicate', 'order', 'class', 'count', 'id'):
            changed = deepcopy(value)
            if kind == 'missing': changed['outcomes'].pop()
            elif kind == 'duplicate': changed['outcomes'][1] = changed['outcomes'][0].copy()
            elif kind == 'order': changed['outcomes'].reverse()
            elif kind == 'class': changed['outcomes'][0]['class'] = 'another.TestCase'
            elif kind == 'count': changed['tests'] -= 1
            else: changed['test_ids'][0] = 'another.TestCase.test_fake'
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                original.outcomes(changed, identities, classname)
        for status, field in (('failure', 'failures'), ('error', 'errors'), ('skipped', 'skipped'),
                              ('expected-failure', 'expectedFailures'), ('unexpected-success', 'unexpectedSuccesses')):
            changed = deepcopy(value)
            changed['outcomes'][0].update(status=status, detail='actual child ' + status)
            with patch.object(original, 'run', return_value={'value': changed}), patch.object(cls, 'setUpClass'):
                suite = original.original_test_suite(unittest.defaultTestLoader, unittest.TestSuite(cases), None, module.__name__)
                self.assertEqual(list(suite), cases)
                self.assertEqual([type(case) for case in suite], [cls] * len(cases))
                result = unittest.TestResult()
                suite.run(result)
            with self.subTest(status=status):
                self.assertEqual(result.testsRun, 8)
                self.assertEqual(len(getattr(result, field)), 1)
                if status != 'failure': self.assertEqual(result.failures, [])


if __name__ == '__main__':
    unittest.main()
