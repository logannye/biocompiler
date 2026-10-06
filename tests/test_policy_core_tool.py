"""Python-only controls for the hosted native policy campaign itself."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools.check_policy_core import (
    ImportBoundary, campaign, canonical_digest, compare_receipts, digest_file, load_cases, main, mutations, semantic_digest,
    read_json, run_bounded, source_identity, write_receipt,
)

FIXTURE = Path(__file__).resolve().parents[1] / 'core/test/data/policy_documents_v01.json'
SOURCE_IDENTITY = {'revision': '1' * 40, 'head_revision': '2' * 40, 'run_id': '12345', 'run_attempt': '1'}


class PolicyCoreToolTests(unittest.TestCase):
    def test_corpus_is_complete_and_digest_bound(self):
        cases = load_cases(FIXTURE)
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({row['name'] for row in cases}), 8)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.json'
            fixture = read_json(FIXTURE)
            fixture['cases'][0]['document']['id'] += '_changed'
            path.write_text(json.dumps(fixture))
            with self.assertRaisesRegex(AssertionError, 'artifact digest'):
                load_cases(path)
            fixture = read_json(FIXTURE)
            fixture['cases'][0] = copy.deepcopy(fixture['cases'][1])
            path.write_text(json.dumps(fixture))
            with self.assertRaisesRegex(AssertionError, 'Duplicate'):
                load_cases(path)

    def test_independent_mutations_preserve_original_corpus(self):
        cases = load_cases(FIXTURE)
        original = copy.deepcopy(cases)
        controls = mutations(cases)
        self.assertEqual(cases, original)
        self.assertEqual(len(controls), 10)
        self.assertEqual(len({name for name, _, _, _ in controls}), 10)
        self.assertEqual({status for _, _, status, _ in controls}, {'invalid', 'rejected'})
        original_hashes = {canonical_digest(row['document']) for row in cases}
        for name, value, _, code in controls:
            with self.subTest(name=name):
                self.assertNotIn(canonical_digest(value), original_hashes)
                self.assertTrue(code)
        mismatch = next(value for name, value, _, _ in controls if name == 'subject_scope_mismatch')
        rule = next(value for value in mismatch['declarations'] if value['$type'] == 'Rule')
        self.assertEqual(rule['when']['args'][0]['scope']['kind'], 'Role')

    def test_import_guard_allows_only_authoring_and_transport(self):
        guard = ImportBoundary(Path('/'))
        for name in ('biocompiler.compiler', 'biocompiler.semantics', 'biocompiler.verification',
                     'biocompiler.cli', 'biocompiler.core_pipeline_manager', '_biocompiler_core'):
            with self.subTest(name=name), self.assertRaises(ImportError):
                guard.find_spec(name)
        for name in ('biocompiler', 'biocompiler.core_policy', 'biocompiler.core_client',
                     'biocompiler.policy.native', 'biocompiler.policy.serialization', 'biocompiler.entrypoint'):
            self.assertIsNone(guard.find_spec(name))
        with self.assertRaises(AssertionError):
            guard.origins()

    def test_guard_detects_preloaded_forbidden_and_foreign_modules(self):
        forbidden = importlib.util.module_from_spec(importlib.machinery.ModuleSpec('biocompiler.compiler', loader=None))
        with patch.dict(sys.modules, {'biocompiler.compiler': forbidden}), self.assertRaises(AssertionError):
            ImportBoundary(Path('/')).origins()
        foreign = importlib.util.module_from_spec(importlib.machinery.ModuleSpec('biocompiler.core_policy', loader=None))
        foreign.__file__ = '/outside-install/core_policy.py'
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(sys.modules, {'biocompiler.core_policy': foreign}), self.assertRaises(AssertionError):
                ImportBoundary(Path(directory)).origins()

    def test_json_and_receipts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            write_receipt(path, {'status': 'passed'})
            self.assertEqual(read_json(path), {'status': 'passed'})
            with self.assertRaises(FileExistsError):
                write_receipt(path, {'status': 'changed'})
            for value in ('{"a":1,"a":2}', '{"a":0.1}', '{"a":NaN}'):
                path.write_text(value)
                with self.assertRaises(AssertionError):
                    read_json(path)
            other = Path(directory) / 'redirect.json'
            other.symlink_to(path)
            with self.assertRaises(AssertionError):
                read_json(other)

    def test_cli_runner_bounds_output_and_time_without_native_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ)
            self.assertEqual(run_bounded([sys.executable, '-c', 'print("ok")'], cwd=root, env=env),
                             (0, b'ok\n', b''))
            with self.assertRaisesRegex(AssertionError, 'output bound'):
                run_bounded([sys.executable, '-c', 'print("x" * 65536)'], cwd=root, env=env, maximum=32)
            with self.assertRaisesRegex(AssertionError, 'time bound'):
                run_bounded([sys.executable, '-c', 'import time; time.sleep(10)'], cwd=root, env=env, timeout=0.03)

    def test_campaign_refuses_checkout_before_native_calls(self):
        checkout = Path(__file__).resolve().parents[1]
        with patch('tools.check_policy_core.Path.cwd', return_value=checkout):
            with self.assertRaisesRegex(AssertionError, 'outside the source checkout'):
                campaign(Path('/not-executed/core'), Path('/not-executed/verify'), FIXTURE, Path('/not-executed/console'))

    def test_execution_guard_blocks_python_checking_calls(self):
        guard = ImportBoundary(Path('/'))
        for module, function in (('biocompiler.policy.validation', 'check'),
                                 ('biocompiler.policy.programs', 'freeze'),
                                 ('biocompiler.policy.handoff', 'prepare_submission')):
            frame = SimpleNamespace(f_globals={'__name__': module}, f_code=SimpleNamespace(co_name=function))
            with self.assertRaisesRegex(AssertionError, 'authoring-check'):
                guard.trace(frame, 'call', None)
        allowed = SimpleNamespace(f_globals={'__name__': 'biocompiler.policy.serialization'},
                                  f_code=SimpleNamespace(co_name='to_data'))
        guard.trace(allowed, 'call', None)
        with self.assertRaises(AssertionError):
            guard.origins()

    def comparison_fixture(self, system, minor):
        # Construct receipt-shaped test data only; no native executable runs.
        corpus = load_cases(FIXTURE)
        package = '/installed/biocompiler'
        origins = {name: package + '/' + name.rsplit('.', 1)[-1] + '.py'
                   for name in ('biocompiler', 'biocompiler.entrypoint', 'biocompiler.policy.cli',
                                'biocompiler.core_policy', 'biocompiler.core_client')}
        value = {'schema_version': 'biocompiler.policy_native_campaign.v0.1', 'status': 'passed',
                 'selected_inputs': {'core': '/installed/core', 'verify': '/installed/verify', 'fixture': str(FIXTURE)},
                 'counts': {'assessments': 48, 'fresh_replays': 48, 'forged_replays': 48,
                            'negative_controls': 20, 'installed_cli': 6},
                 'frontend_scope': 'independent_native_policy_source_contracts',
                 'semantic_execution': 'unsupported', 'lowering': 'unsupported',
                 'sequence_artifact': 'withheld', 'empirical_acceptance': 'not_established',
                 'python_version': [3, minor, 0], 'sys_platform': system,
                 'source_identity': dict(SOURCE_IDENTITY), 'machine': 'x86_64' if system == 'linux' else 'arm64',
                 'python': f'3.{minor}.0 (controlled test)', 'platform': ('Linux-' if system == 'linux' else 'macOS-') + 'controlled-test',
                 'installed_package': package, 'interpreter': '/installed/python',
                 'executables': {role: {'path': '/installed/' + role, 'sha256': hashlib.sha256(('test native bytes ' + role).encode()).hexdigest()} for role in ('core', 'verify')},
                 'console': {'path': '/installed/bin/biocompiler', 'sha256': 'b' * 64},
                 'fixture': {'path': str(FIXTURE), 'sha256': digest_file(FIXTURE)},
                 'parent_imports': origins, 'parent_execution_guard': True,
                 'cases': [], 'negative_controls': [], 'cli': []}
        for source in corpus:
            document = source['document']['request'] if source['kind'] == 'submission' else source['document']
            program = document['program'] if document['$type'] == 'BuildRequest' else document
            prefix = {'program': '/document', 'request': '/document/program', 'submission': '/document/request/program'}[source['kind']]
            ledger = [{'id': d['id'], 'kind': d['$type'], 'value': d, 'path': prefix + '/declarations/' + str(i),
                       'sources': [span for span in program['source_map'] if span['declaration_id'] == d['id']]}
                      for i, d in enumerate(program['declarations'])]
            assessment = {'schema_version': 'biocompiler.policy_assessment.v0.1', 'status': 'valid', 'diagnostics': [],
                          'semantic_status': 'unresolved', 'target_status': 'unassessed', 'lowering': 'unsupported',
                          'artifact': 'withheld', 'declarations': ledger,
                          'requirements': [entry for entry in ledger if entry['kind'] == 'Requirement'],
                          'document_digest': source['fingerprint'], 'program_digest': semantic_digest(program),
                          'artifact_digest': source['artifact_digest'], 'required_features': [],
                          'dependencies': [], 'assumptions': [], 'unresolved_obligations': []}
            for role in ('core', 'verify'):
                value['cases'].append({'name': source['name'], 'kind': source['kind'], 'role': role,
                    'artifact_digest': source['artifact_digest'], 'document_digest': source['fingerprint'],
                    'program_digest': semantic_digest(program), 'assessment_fingerprint': canonical_digest(assessment),
                    'assessment': assessment, 'fresh_replay': 'passed', 'forged_replay': 'rejected'})
        for name, document, status, code in mutations(corpus):
            for role in ('core', 'verify'):
                value['negative_controls'].append({'name': name, 'role': role, 'expected': status,
                    'required_diagnostic': code, 'diagnostics': [code], 'input_digest': canonical_digest(document)})
        for role in ('core', 'verify'):
            for kind in ('program', 'request', 'submission'):
                value['cli'].append({'role': role, 'kind': kind, 'status': 'passed',
                    'guard': {'status': 'ok', 'guard_active': True, 'execution_guard_active': True,
                              'python': [3, minor], 'executable': '/installed/python', 'origins': origins}})
        return value

    def test_four_variant_comparison_preserves_source_identity_and_scope(self):
        with tempfile.TemporaryDirectory() as directory, patch('tools.check_policy_core.source_identity', return_value=SOURCE_IDENTITY):
            native = Path(directory) / 'native'
            for system, folder, machine in (('Linux', 'linux-x86_64', 'x86_64'), ('Darwin', 'macos-arm64', 'arm64')):
                slot = native / folder
                slot.mkdir(parents=True)
                pins = {}
                for role in ('core', 'verify'):
                    binary = slot / ('biocompiler-' + role)
                    binary.write_bytes(('test native bytes ' + role).encode())
                    pins[binary.name] = digest_file(binary)
                (slot / 'binaries.json').write_text(json.dumps({'revision': SOURCE_IDENTITY['revision'],
                    'system': system, 'machine': machine, 'sha256': pins}))
            paths = []
            for system in ('linux', 'darwin'):
                for minor in (11, 14):
                    path = Path(directory) / f'{system}-{minor}.json'
                    path.write_text(json.dumps(self.comparison_fixture(system, minor)))
                    paths.append(path)
            result = compare_receipts(paths, native_artifacts=native)
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(len(result['variants']), 4)
            with self.assertRaisesRegex(AssertionError, 'four distinct'):
                compare_receipts(paths[:3], native_artifacts=native)
            with self.assertRaisesRegex(AssertionError, 'four distinct'):
                compare_receipts([paths[0], paths[0], *paths[2:]], native_artifacts=native)
            original = read_json(paths[-1])
            mutations_to_reject = []
            altered = copy.deepcopy(original)
            altered['source_identity']['run_attempt'] = '2'
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['machine'] = 'x86_64'
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['executables']['core']['sha256'] = '0' * 64
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['sys_platform'] = 'linux'
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['semantic_execution'] = 'proved'
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['parent_imports']['biocompiler.compiler'] = '/installed/biocompiler/compiler.py'
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['cases'][0]['assessment']['declarations'].reverse()
            altered['cases'][0]['assessment_fingerprint'] = canonical_digest(altered['cases'][0]['assessment'])
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['cases'][0]['assessment']['required_features'] = ['changed']
            altered['cases'][0]['assessment_fingerprint'] = canonical_digest(altered['cases'][0]['assessment'])
            mutations_to_reject.append(altered)
            altered = copy.deepcopy(original)
            altered['negative_controls'][0]['input_digest'] = '0' * 64
            mutations_to_reject.append(altered)
            for index, value in enumerate(mutations_to_reject):
                with self.subTest(index=index):
                    paths[-1].write_text(json.dumps(value))
                    with self.assertRaises(AssertionError):
                        compare_receipts(paths, native_artifacts=native)
            paths[-1].write_text(json.dumps(original))
            self.assertEqual(compare_receipts(paths, native_artifacts=native)['source_result_identity'], result['source_result_identity'])
            (native / 'linux-x86_64/biocompiler-core').write_bytes(b'changed published bytes')
            with self.assertRaisesRegex(AssertionError, 'Published native bytes'):
                compare_receipts(paths, native_artifacts=native)

    def test_workflow_identity_binds_git_head_run_and_attempt(self):
        environment = {'GITHUB_SHA': '1' * 40, 'GITHUB_HEAD_SHA': '2' * 40,
                       'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1'}
        with patch.dict(os.environ, environment, clear=True), patch('tools.check_policy_core.subprocess.run',
                return_value=SimpleNamespace(stdout='1' * 40 + '\n')):
            self.assertEqual(source_identity(), SOURCE_IDENTITY)
            with patch.dict(os.environ, {'GITHUB_SHA': '0' * 40}):
                with self.assertRaisesRegex(AssertionError, 'tested GitHub revision'):
                    source_identity()
            with patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '0'}):
                with self.assertRaisesRegex(AssertionError, 'attempt'):
                    source_identity()

    def test_failure_retains_receipt_without_claiming_native_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed.json'
            with patch('tools.check_policy_core.campaign', side_effect=AssertionError('controlled failure')):
                result = main(['--core', '/not-executed/core', '--verify', '/not-executed/verify',
                               '--console', sys.executable, '--output', str(output)])
            self.assertEqual(result, 1)
            receipt = read_json(output)
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(receipt['lowering'], 'unsupported')
            self.assertEqual(receipt['sequence_artifact'], 'withheld')


if __name__ == '__main__':
    unittest.main()
