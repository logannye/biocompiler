"""Exact policy-entrypoint restoration for original Python-only build captures."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from tools import pipeline_original_counterpart as counterpart
from tools import pipeline_policy_counterpart_source as runner_source
from tools import policy_entrypoint_source_lineage as policy


def original_without_descendant_processes(task):
    """Allow the isolated Python child and deny every process launch within it."""
    execute = counterpart.subprocess.run
    guard = '''import sys
def reject_process(event, arguments):
    if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.spawn', 'os.posix_spawn', 'os.fork', 'os.forkpty'):
        raise AssertionError('Original capture attempted a descendant process: ' + event)
sys.addaudithook(reject_process)
try:
    sys.audit('subprocess.Popen', 'denied-native-sentinel', (), None, None)
except AssertionError:
    pass
else:
    raise AssertionError('Process denial guard did not activate')
'''

    def guarded(command, **kwargs):
        if command[:3] != [sys.executable, '-I', '-c']:
            raise AssertionError('Unexpected original child launch')
        command = list(command)
        command[3] = guard + command[3]
        return execute(command, **kwargs)

    with patch.object(counterpart.subprocess, 'run', side_effect=guarded):
        return counterpart.run(task)


class PolicyCounterpartClosureTests(unittest.TestCase):
    def test_only_build_and_continuation_scopes_add_the_exact_policy_closure(self):
        expected = {path: policy.restore(path) for path in sorted(policy.ROUTES)}
        for task, module in (('fixed-build-original', None), ('fixed-continuation-original', None),
                             ('tests', 'tests.test_pipeline_fixed_build_semantics')):
            with self.subTest(task=task, module=module):
                self.assertEqual(counterpart.policy_routes(task, module), expected)
                files, data = counterpart.task_files(task, module), counterpart.task_data(task, module)
                self.assertEqual(files.count('tools/policy_entrypoint_source_lineage.py'), 1)
                self.assertEqual(data.count(policy.WITNESS), 1)
                self.assertIn(counterpart.lineage.TOOL_PATH, files)
                self.assertIn(counterpart.lineage.INSTALLED_TOOL_WITNESS, data)
        for task, module in (('deferred', None), ('callbacks', None), ('identity', None),
                             ('fixed-provider-original', None), ('fixed-registration-original', None),
                             ('tests', 'tests.test_pipeline_contract_literals'),
                             ('tests', 'tests.test_pipeline_fixed_provider_semantics')):
            with self.subTest(task=task, module=module):
                self.assertEqual(counterpart.policy_routes(task, module), {})
                self.assertNotIn('tools/policy_entrypoint_source_lineage.py', counterpart.task_files(task, module))
                self.assertNotIn(policy.WITNESS, counterpart.task_data(task, module))

    def test_child_rechecks_independent_witness_current_origins_and_whole_original_bytes(self):
        routes = counterpart.policy_routes('fixed-build-original')
        for mode in ('valid', 'origin', 'copied_pin', 'not_substituted', 'current_bytes',
                     'extra_bytes', 'missing_route', 'forged_route', 'extra_route', 'witness', 'wrong_scope'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                witness = root / policy.WITNESS
                witness.parent.mkdir(parents=True)
                witness.write_bytes((counterpart.ROOT / policy.WITNESS).read_bytes())
                manifest = {'task': 'fixed-build-original', 'test_module': None,
                            'policy_routes': {path: proof for path, (_, proof) in routes.items()}}
                manifest = deepcopy(manifest)
                rows = {}
                for logical, (raw, proof) in routes.items():
                    path = root / logical
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                    rows[logical] = {'origin_sha256': proof['current_sha256'],
                                     'sha256': proof['historical_sha256'], 'substituted': True}
                logical = 'src/biocompiler/__init__.py'
                if mode == 'origin': rows[logical]['origin_sha256'] = rows[logical]['sha256']
                elif mode == 'copied_pin': rows[logical]['sha256'] = rows[logical]['origin_sha256']
                elif mode == 'not_substituted': rows[logical]['substituted'] = False
                elif mode == 'current_bytes': (root / logical).write_bytes((counterpart.ROOT / logical).read_bytes())
                elif mode == 'extra_bytes': (root / logical).write_bytes((root / logical).read_bytes() + b'\n')
                elif mode == 'missing_route': manifest['policy_routes'].pop(logical)
                elif mode == 'forged_route': manifest['policy_routes'][logical]['witness_sha256'] = '0' * 64
                elif mode == 'extra_route': manifest['policy_routes']['pyproject.toml'] = {}
                elif mode == 'witness': witness.write_bytes(witness.read_bytes() + b' ')
                elif mode == 'wrong_scope': manifest['task'] = 'fixed-provider-original'
                with patch.object(counterpart, 'ROOT', root):
                    if mode == 'valid': counterpart.verify_child_policy_routes(manifest, rows)
                    else:
                        with self.assertRaises((AssertionError, ValueError)):
                            counterpart.verify_child_policy_routes(manifest, rows)

    def test_changed_installed_policy_source_is_rejected_before_child_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'biocompiler'
            for path in (counterpart.ROOT / 'src/biocompiler').rglob('*.py'):
                copied = package / path.relative_to(counterpart.ROOT / 'src/biocompiler')
                copied.parent.mkdir(parents=True, exist_ok=True)
                copied.write_bytes(path.read_bytes())
            path = package / '__init__.py'
            path.write_bytes(path.read_bytes() + b'\n# unreviewed installed source\n')
            with patch.object(counterpart.importlib, 'import_module', return_value=SimpleNamespace(__file__=str(path))), \
                 patch.object(counterpart.subprocess, 'run') as child:
                with self.assertRaisesRegex(AssertionError, 'Installed policy entrypoint differs'):
                    counterpart.run('fixed-build-original')
                child.assert_not_called()

    def test_new_runner_layer_recovers_both_exact_predecessors_without_changing_old_witnesses(self):
        from tools import pipeline_capture_overlap_source as overlap
        from tools import pipeline_occurrence_source as occurrence
        proof = json.loads(runner_source.WITNESS.read_bytes())
        old = json.loads(overlap.WITNESS.read_bytes())
        self.assertEqual(hashlib.sha256(overlap.WITNESS.read_bytes()).hexdigest(), overlap.WITNESS_SHA256)
        self.assertEqual(hashlib.sha256(occurrence.WITNESS.read_bytes()).hexdigest(), occurrence.WITNESS_SHA256)
        self.assertEqual(set(proof['files']), runner_source.PATHS)
        for logical in runner_source.PATHS:
            current = (counterpart.ROOT / logical).read_bytes()
            restored = runner_source.restore(logical, current)
            self.assertEqual({'bytes': len(restored), 'sha256': hashlib.sha256(restored).hexdigest()},
                             old['files'][logical]['current'])
            self.assertEqual(restored, proof['files'][logical]['historical_source'].encode())
            self.assertNotEqual(restored, current)
            occurrence.restore(logical, current)
        driver = 'tools/check_pipeline_fixed_continuation_install.py'
        before = ast.parse(proof['files'][driver]['historical_source'])
        after = ast.parse(proof['files'][driver]['current_source'])
        def remove_sources(tree):
            tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
                         any(isinstance(target, ast.Name) and target.id == 'SOURCES' for target in node.targets))]
            return ast.dump(tree)
        self.assertEqual(remove_sources(before), remove_sources(after))

    def test_new_runner_layer_rejects_rehashed_or_extra_source_and_witness_changes(self):
        proof = json.loads(runner_source.WITNESS.read_bytes())
        for logical in runner_source.PATHS:
            current = (counterpart.ROOT / logical).read_bytes()
            for raw in (current + b'\n', current.replace(b'\n', b'\r\n'),
                        proof['files'][logical]['historical_source'].encode()):
                with self.subTest(path=logical), self.assertRaisesRegex(AssertionError, 'Current source differs'):
                    runner_source.restore(logical, raw)
                changed = deepcopy(proof)
                changed['files'][logical]['current_source'] = raw.decode()
                changed['files'][logical]['current'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                with self.assertRaisesRegex(AssertionError, 'Unreviewed'):
                    runner_source.restore(logical, raw, json.dumps(changed).encode())
        self.assertEqual(runner_source.restore('unrelated.py', b'unchanged'), b'unchanged')


class ActualPolicyBuildCounterpartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A fresh isolated Python original, never an installed/native campaign.
        cls.receipt = original_without_descendant_processes('fixed-build-original')

    def test_fresh_six_case_capture_preserves_entire_frozen_original_and_provenance(self):
        value = counterpart.validate(self.receipt)
        frozen = json.loads((counterpart.ROOT / 'tests/conformance/pipeline-fixed-build-semantics-v1.json').read_bytes())
        self.assertEqual(value, frozen)
        self.assertEqual(len(value['cases']), 6)
        self.assertEqual(value['coverage']['eligible_continuation_chains'], 39)
        self.assertEqual(self.receipt['manifest']['schema'], 'biocompiler.original_manager_counterpart.v2')
        rows = {row['logical']: row for row in self.receipt['manifest']['sources']}
        routes = counterpart.policy_routes('fixed-build-original')
        for logical, (raw, proof) in routes.items():
            self.assertEqual(rows[logical]['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(rows[logical]['origin_sha256'], proof['current_sha256'])
            self.assertTrue(rows[logical]['substituted'])
        self.assertEqual(rows[counterpart.lineage.TOOL_PATH]['sha256'], counterpart.lineage.TOOL_HISTORICAL)
        self.assertEqual(self.receipt['modules']['biocompiler']['sha256'],
                         routes['src/biocompiler/__init__.py'][1]['historical_sha256'])
        self.assertNotIn('biocompiler.entrypoint', self.receipt['modules'])

    def test_policy_metadata_projection_preserves_every_nonmetadata_byte(self):
        # Exercise the policy branch explicitly; the frozen build capture itself
        # does not list package entrypoints in its observed source metadata.
        original = deepcopy(self.receipt)
        for logical, (_, proof) in counterpart.policy_routes('fixed-build-original').items():
            original['value']['source_files'][logical] = proof['historical_sha256']

        def repin(value):
            value['inventory_fingerprint'] = counterpart.lineage.sha(counterpart.canonical({
                key: item for key, item in value.items() if key != 'inventory_fingerprint'}))
            return value

        repin(original['value'])
        current = deepcopy(original['value'])
        current['source_files'] = {path: counterpart.lineage.sha((counterpart.ROOT / path).read_bytes())
                                   for path in current['source_files']}
        repin(current)
        proof = counterpart.metadata_correspondence(current, original)
        self.assertEqual(proof['complete_body_sha256'], counterpart.lineage.sha(counterpart.canonical({
            key: item for key, item in original['value'].items() if key not in ('source_files', 'inventory_fingerprint')})))
        for mode in ('body', 'unrelated_source', 'policy_source'):
            changed = deepcopy(current)
            if mode == 'body': changed['cases'][0]['id'] += '-forged'
            elif mode == 'policy_source': changed['source_files']['src/biocompiler/__init__.py'] = '0' * 64
            else: changed['source_files']['tools/capture_pipeline_fixed_build_semantics.py'] = '0' * 64
            with self.subTest(mode=mode), self.assertRaises(AssertionError):
                counterpart.metadata_correspondence(repin(changed), original)

    def test_parent_rejects_forged_policy_proofs_copied_bytes_origins_and_closure(self):
        for mode in ('schema', 'missing_proof', 'extra_proof', 'proof', 'origin', 'copy', 'substituted',
                     'missing_source', 'missing_helper', 'missing_witness', 'module'):
            changed = deepcopy(self.receipt)
            manifest = changed['manifest']
            logical = 'src/biocompiler/__init__.py'
            row = next(row for row in manifest['sources'] if row['logical'] == logical)
            if mode == 'schema': manifest['schema'] = 'biocompiler.original_manager_counterpart.v1'
            elif mode == 'missing_proof': manifest['policy_routes'].pop(logical)
            elif mode == 'extra_proof': manifest['policy_routes']['pyproject.toml'] = {}
            elif mode == 'proof': manifest['policy_routes'][logical]['historical_sha256'] = '0' * 64
            elif mode == 'origin': row['origin_sha256'] = row['sha256']
            elif mode == 'copy': row['sha256'] = row['origin_sha256']
            elif mode == 'substituted': row['substituted'] = False
            elif mode == 'missing_source': manifest['sources'].remove(row)
            elif mode == 'missing_helper':
                manifest['sources'] = [row for row in manifest['sources']
                                       if row['logical'] != 'tools/policy_entrypoint_source_lineage.py']
            elif mode == 'missing_witness':
                manifest['data'] = [row for row in manifest['data'] if row['logical'] != policy.WITNESS]
            else: changed['modules']['biocompiler']['sha256'] = row['origin_sha256']
            with self.subTest(mode=mode), self.assertRaises(AssertionError):
                counterpart.validate(changed)


if __name__ == '__main__':
    unittest.main()
