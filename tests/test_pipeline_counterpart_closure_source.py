"""Inert complete-source restoration; no original captures or product imports."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import pipeline_counterpart_closure_source as source
from tools import pipeline_policy_counterpart_source as policy
from tools import pipeline_capture_overlap_source as overlap
from tools import pipeline_continuation_parallel_source as parallel
from tools import pipeline_occurrence_source as occurrence

ROOT = Path(__file__).resolve().parents[1]
OLD_WITNESSES = {
    'pipeline-policy-counterpart-source-delta-v1.json': '96bd3db3678535fc57373a0d369c736c9c31ebfd5d331a2e91e373407fb82d54',
    'pipeline-capture-overlap-source-delta-v1.json': 'a6d817a7b8cbbca6a06608a0b495d2ad5520cb279e0793521d32310b26cb3c10',
    'pipeline-continuation-parallel-source-delta-v1.json': '16869820863ef1624f06ebf606861aa93aa3def3c88250e066dfb0be036d3bf9',
    'pipeline-occurrence-source-delta-v1.json': '8b8c455783299cfe6cda7f38f94b17a2459a2a0b2b61b6f2a2ece00797d89d9e',
}
ADDED_SOURCES = (
    'tools/pipeline_counterpart_closure_source.py',
    'tests/test_pipeline_counterpart_closure_snapshot.py',
    'tests/test_pipeline_counterpart_closure_source.py',
    'tests/conformance/pipeline-counterpart-closure-source-delta-v1.json',
)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class CounterpartClosureSourceTests(unittest.TestCase):
    def setUp(self):
        self.raw = source.WITNESS.read_bytes()
        self.proof = json.loads(self.raw)

    def test_complete_immediate_predecessors_equal_existing_policy_authority(self):
        previous = json.loads(policy.WITNESS.read_bytes())
        self.assertEqual(set(self.proof['files']), {
            'tools/pipeline_original_counterpart.py', 'tools/check_pipeline_fixed_continuation_install.py'})
        self.assertEqual(self.proof['base_revision'], '77d6be591921482735c48b1940ccbfdfd1b2362e')
        for path in source.PATHS:
            current = (ROOT / path).read_bytes()
            with self.subTest(path=path):
                restored = source.restore(path, current)
                self.assertEqual(restored, previous['files'][path]['current_source'].encode())
                self.assertEqual(pin(restored), previous['files'][path]['current'])
                self.assertEqual(current, self.proof['files'][path]['current_source'].encode())
                self.assertEqual(pin(current), self.proof['files'][path]['current'])
                self.assertNotEqual(current, restored)

    def test_all_prior_layers_keep_their_exact_bytes_and_full_restoration(self):
        for module in (policy, overlap, parallel, occurrence):
            self.assertEqual(module.WITNESS_SHA256, OLD_WITNESSES[module.WITNESS.name])
            self.assertEqual(pin(module.WITNESS.read_bytes())['sha256'], module.WITNESS_SHA256)
        for path in source.PATHS:
            current = (ROOT / path).read_bytes()
            for module in (policy, overlap, parallel, occurrence):
                proof = json.loads(module.WITNESS.read_bytes())
                if path not in proof['files']:
                    continue
                with self.subTest(path=path, layer=module.__name__):
                    self.assertEqual(pin(module.restore(path, current)), proof['files'][path]['historical'])

    def test_runner_changes_only_validate_and_driver_changes_only_four_source_entries(self):
        for path, row in self.proof['files'].items():
            before, after = ast.parse(row['historical_source']), ast.parse(row['current_source'])
            if path.endswith('pipeline_original_counterpart.py'):
                for tree in (before, after):
                    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'validate']
                    self.assertEqual(len(selected), 1)
                    tree.body.remove(selected[0])
            else:
                values = []
                for tree in (before, after):
                    selected = [node for node in tree.body if isinstance(node, ast.Assign) and
                                any(isinstance(target, ast.Name) and target.id == 'SOURCES' for target in node.targets)]
                    self.assertEqual(len(selected), 1)
                    tree.body.remove(selected[0])
                    values.append([node.value for node in ast.walk(selected[0])
                                   if isinstance(node, ast.Constant) and isinstance(node.value, str)])
                self.assertEqual([value for value in values[1] if value not in values[0]], list(ADDED_SOURCES))
                self.assertEqual([value for value in values[1] if value not in ADDED_SOURCES], values[0])
                self.assertTrue(all(values[1].count(value) == 1 for value in ADDED_SOURCES))
            self.assertEqual(ast.dump(before), ast.dump(after))

    def test_policy_hook_is_only_the_exact_lazy_predecessor_call(self):
        raw = (ROOT / 'tools/pipeline_policy_counterpart_source.py').read_bytes()
        hook = (b'    from tools import pipeline_counterpart_closure_source\n'
                b'    current = pipeline_counterpart_closure_source.restore(path, current)\n')
        self.assertEqual(raw.count(hook), 1)
        self.assertEqual(pin(raw.replace(hook, b'', 1))['sha256'],
                         '6d2fe803e5cf6ebe743a217bed4fef93c96174cc9fffc4e54c19755bdb44fe79')
        tree = ast.parse((ROOT / 'tools/pipeline_counterpart_closure_source.py').read_bytes())
        imports = [(type(node).__name__, ast.dump(node)) for node in tree.body
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        expected = ast.parse('import hashlib\nimport json\nfrom pathlib import Path\n').body
        self.assertEqual(imports, [(type(node).__name__, ast.dump(node)) for node in expected])

    def test_changed_source_stale_source_and_nonbytes_are_rejected(self):
        for path in source.PATHS:
            current = (ROOT / path).read_bytes()
            mutants = (current + b'\n', current.replace(b'\n', b'\r\n'),
                       self.proof['files'][path]['historical_source'].encode(), bytearray(current))
            for changed in mutants:
                with self.subTest(path=path, kind=type(changed).__name__), \
                     self.assertRaisesRegex(AssertionError, 'Current source differs'):
                    source.restore(path, changed)

    def test_original_policy_witness_authentication_precedes_new_source_restoration(self):
        original = json.loads(policy.WITNESS.read_bytes())
        for path in source.PATHS:
            changed = (ROOT / path).read_bytes() + b'\n# unreviewed\n'
            proof = deepcopy(original)
            proof['files'][path]['current_source'] = changed.decode()
            proof['files'][path]['current'] = pin(changed)
            with self.subTest(path=path), self.assertRaisesRegex(AssertionError, 'Unreviewed policy counterpart runner witness'):
                policy.restore(path, changed, json.dumps(proof).encode())
            with self.subTest(path=path), self.assertRaisesRegex(AssertionError, 'Current source differs'):
                policy.restore(path, changed)

    def test_rehashed_source_or_witness_mutations_cannot_replace_reviewed_authority(self):
        for path in source.PATHS:
            current = (ROOT / path).read_bytes()
            for mode in ('source', 'historical', 'path', 'schema', 'revision'):
                proof = deepcopy(self.proof)
                actual = current
                if mode in ('source', 'historical'):
                    side = 'current' if mode == 'source' else 'historical'
                    proof['files'][path][side + '_source'] += '\n# unreviewed\n'
                    changed = proof['files'][path][side + '_source'].encode()
                    proof['files'][path][side] = pin(changed)
                    if mode == 'source': actual = changed
                elif mode == 'path': proof['files']['tools/unreviewed.py'] = proof['files'].pop(path)
                elif mode == 'schema': proof['schema'] += '.unreviewed'
                else: proof['base_revision'] = '0' * 40
                with self.subTest(path=path, mode=mode), \
                     self.assertRaisesRegex(AssertionError, 'Unreviewed counterpart closure'):
                    source.restore(path, actual, json.dumps(proof).encode())

    def test_proof_bounds_missing_redirected_or_changed_files_fail_closed(self):
        path = sorted(source.PATHS)[0]
        current = (ROOT / path).read_bytes()
        for raw in (b'{}', self.raw + b' ', b' ' * (source.MAX_WITNESS_BYTES + 1), {}, bytearray(self.raw)):
            with self.subTest(kind=type(raw).__name__), self.assertRaisesRegex(AssertionError, 'Unreviewed'):
                source.restore(path, current, raw)
        with tempfile.TemporaryDirectory() as directory:
            witness = Path(directory) / 'witness.json'
            with patch.object(source, 'WITNESS', witness):
                with self.assertRaisesRegex(AssertionError, 'missing, redirected or oversized'):
                    source.restore(path, current)
                witness.write_bytes(self.raw)
                self.assertEqual(source.restore(path, current), self.proof['files'][path]['historical_source'].encode())
                witness.write_bytes(b' ' * (source.MAX_WITNESS_BYTES + 1))
                with self.assertRaisesRegex(AssertionError, 'missing, redirected or oversized'):
                    source.restore(path, current)
                witness.unlink()
                witness.symlink_to(ROOT / 'tests/conformance/pipeline-counterpart-closure-source-delta-v1.json')
                with self.assertRaisesRegex(AssertionError, 'missing, redirected or oversized'):
                    source.restore(path, current)

    def test_unlisted_paths_are_not_substituted_or_granted_a_source_proof(self):
        value = object()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No proof read for unlisted path')):
            self.assertIs(source.restore('tools/unreviewed.py', value), value)


if __name__ == '__main__':
    unittest.main()
