"""Mocked hosted orchestration and inert evidence only; no native execution."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from tools import check_policy_development as dev
from tools import check_researcher_development as scoped
from tools import check_researcher_alpha as researcher
from tests import test_policy_development as native_fixture

ROOT = Path(__file__).resolve().parents[1]


class ResearcherDevelopmentTests(unittest.TestCase):
    freeze_tree = native_fixture.PolicyDevelopmentTests.freeze_tree
    git = native_fixture.PolicyDevelopmentTests.git
    launch = native_fixture.PolicyDevelopmentTests.launch
    report = native_fixture.PolicyDevelopmentTests.report

    def setUp(self):
        native_fixture.PolicyDevelopmentTests.setUp(self)
        self.env.update(GITHUB_REF='refs/heads/codex/dev-researcher/example',
            GITHUB_WORKFLOW_REF='owner/repository/.github/workflows/researcher-development.yml@refs/heads/codex/dev-researcher/example')
        patch = mock.patch.dict(os.environ, self.env, clear=True); patch.start(); self.addCleanup(patch.stop)

    def evidence(self):
        dev.prepare(self.root); dev.run(self.root)
        output = self.root / scoped.OUTPUT
        folder = output / scoped.FOLDER; folder.mkdir()
        for name in scoped.evidence_names():
            if name.startswith(scoped.FOLDER + '/'):
                (output / name).write_bytes(b'INERT RETAINED EVIDENCE')
        self.mutate = lambda argv: (output / 'researcher-alpha-sdk-witness.json').write_text('{"inert":true}\n')
        dev.researcher_alpha_sdk(self.root)
        return output

    def seal(self):
        with mock.patch.object(scoped, 'validate_researcher', return_value={'explicitly_mocked': True}):
            return scoped.seal(self.root)

    def researcher_envelope(self):
        """Inert structural envelopes; domain/ZIP delegates are explicitly mocked."""
        from biocompiler.core_client import encode_json
        from tools import check_researcher_alpha_installed as installed
        output = self.root / scoped.OUTPUT
        folder = output / scoped.FOLDER; folder.mkdir(parents=True)
        prepared = {'identity': dev.identity(self.root), 'sources': {'inert-source': {'size': 0}}}
        binaries = {path: {'sha256': '1' * 64, 'size': 8} for path in researcher.NATIVE_PATHS.values()}
        inputs = {name: {'sha256': '2' * 64, 'size': 8, 'git_blob': '3' * 40} for name in researcher.INPUTS}
        projects = {case: {'project_id': case, 'request': {'implementation_request': {
            'document': {'program': {'source_map': [{'file': case + '.py'}]}}}}, 'limits': {'inert': 1}}
            for case in researcher.PROJECT_IDS}
        packet = {'expected': {'cases': [{'id': case} for case in researcher.CASE_IDS]}}
        observations = {name: {'inert': name} for name in researcher.OBSERVATIONS}
        project_pins, publications = {}, []
        for case, project in projects.items():
            raw = encode_json(project); name = case + '-project.json'; (folder / name).write_bytes(raw)
            project_pins[case] = {'path': name, 'sha256': scoped.pin(raw)['sha256'],
                'project_sha256': researcher.canonical_digest(project),
                'originals_sha256': researcher.canonical_digest({key: project[key] for key in ('request', 'limits')})}
            changed = deepcopy(project)
            changed['request']['implementation_request']['document']['program']['source_map'][0]['file'] += '.changed'
            observations[case + '-changed-originals'] = {'changed_project_sha256': researcher.canonical_digest(changed)}
            publications.append(observations[case + '-paired-publication'])
            (folder / (case + '.zip')).write_bytes(b'INERT ZIP; PARSER MOCKED')
            if case in researcher.CASE_IDS:
                for kind in ('candidate', 'fasta'):
                    raw = (case + kind).encode(); (folder / (case + '-changed-' + kind + '.zip')).write_bytes(raw)
                    observations[case + '-changed-' + kind] = {'bundle_sha256': scoped.pin(raw)['sha256']}
        rows = []
        for name, value in observations.items():
            raw = encode_json(value); (folder / (name + '.json')).write_bytes(raw)
            rows.append({'name': name, 'path': scoped.FOLDER + '/' + name + '.json',
                         'sha256': scoped.pin(raw)['sha256'], 'bytes': len(raw)})
        source_identity = {key: prepared['identity'][key] for key in ('revision', 'run_id', 'run_attempt')}
        source_identity['head_revision'] = source_identity['revision']
        witness = {'schema_version': researcher.SCHEMA, 'status': 'passed', 'acceptance': False,
            'identity': prepared['identity'], 'source_identity': source_identity, 'python': scoped.platform.python_version(),
            'python_semantic_authority': 'forbidden', 'source_snapshot_sha256': researcher.canonical_digest(prepared['sources']),
            'inputs': inputs, 'binary_sha256': {role: binaries[path] for role, path in researcher.NATIVE_PATHS.items()},
            'observations': rows, 'projects': project_pins, 'publications': publications}
        self.domain_check = mock.Mock(side_effect=lambda values, actual_packet: (
            self.assertTrue(scoped.exact(values, observations)), self.assertEqual(actual_packet, packet)))
        self.archive_check, self.mutant_check = mock.Mock(), mock.Mock()
        for patch in (mock.patch.object(researcher, 'tracked_inputs', return_value=inputs),
                      mock.patch.object(researcher, 'checked_assets', return_value=packet),
                      mock.patch.object(researcher, 'expected_project', side_effect=lambda case, _: projects[case['id']]),
                      mock.patch.object(researcher, 'expected_authored_project', return_value=projects['authored']),
                      mock.patch.object(researcher, 'check_observations', self.domain_check),
                      mock.patch.object(researcher, 'archive_receipt', self.archive_check),
                      mock.patch.object(installed, 'check_mutant', self.mutant_check)):
            patch.start(); self.addCleanup(patch.stop)
        return output, witness, prepared, binaries

    def validate_envelope(self, envelope):
        return scoped.validate_researcher(self.root, *envelope)

    def test_researcher_envelope_rechecks_all_originals_sidecars_archives_and_mutants(self):
        envelope = self.researcher_envelope(); result = self.validate_envelope(envelope)
        self.assertEqual(result['observations'], list(researcher.OBSERVATIONS))
        self.assertEqual(len(result['input_pins']), 10)
        self.domain_check.assert_called_once()
        self.assertEqual([call.args[1].name for call in self.archive_check.call_args_list],
                         ['staged.zip', 'comparison.zip', 'authored.zip'])
        self.assertEqual([call.args[0].name for call in self.mutant_check.call_args_list],
                         ['staged-changed-candidate.zip', 'staged-changed-fasta.zip',
                          'comparison-changed-candidate.zip', 'comparison-changed-fasta.zip'])

    def test_researcher_envelope_rejects_stale_identity_input_and_binary_authority(self):
        output, witness, prepared, binaries = self.researcher_envelope()
        for mutate in (lambda value: value.update(python_semantic_authority='allowed'),
                       lambda value: value.update(acceptance=True),
                       lambda value: value['source_identity'].update(head_revision='4' * 40),
                       lambda value: value.update(source_snapshot_sha256='4' * 64),
                       lambda value: value['inputs'].pop(next(iter(value['inputs']))),
                       lambda value: value['binary_sha256']['core'].update(size=True)):
            value = deepcopy(witness); mutate(value)
            with self.assertRaises(ValueError): self.validate_envelope((output, value, prepared, binaries))
        self.domain_check.assert_not_called()

    def test_researcher_envelope_rejects_reordered_redirected_and_rehashed_sidecars(self):
        output, witness, prepared, binaries = self.researcher_envelope()
        for mutate in (lambda value: value['observations'].reverse(),
                       lambda value: value['observations'].append(value['observations'][0]),
                       lambda value: value['observations'][0].update(path='../foreign.json'),
                       lambda value: value['observations'][0].update(bytes=True)):
            value = deepcopy(witness); mutate(value)
            with self.assertRaises(ValueError): self.validate_envelope((output, value, prepared, binaries))
        path = output / witness['observations'][0]['path']; raw = b'{"inert":"rehashed unauthorized content"}'
        path.write_bytes(raw)
        with self.assertRaises(ValueError): self.validate_envelope((output, witness, prepared, binaries))
        witness['observations'][0].update(sha256=scoped.pin(raw)['sha256'], bytes=len(raw))
        with self.assertRaises(AssertionError): self.validate_envelope((output, witness, prepared, binaries))
        self.archive_check.assert_not_called()

    def test_researcher_envelope_preserves_canonical_project_types_and_originals(self):
        output, witness, prepared, binaries = self.researcher_envelope()
        for mutate in (lambda value: value['projects']['authored'].update(path='../authored-project.json'),
                       lambda value: value['projects']['authored'].update(originals_sha256='4' * 64),
                       lambda value: value['publications'].reverse()):
            value = deepcopy(witness); mutate(value)
            with self.assertRaises(ValueError): self.validate_envelope((output, value, prepared, binaries))
        path = output / scoped.FOLDER / 'authored-project.json'
        original = path.read_bytes(); changed = original.replace(b'"inert":1', b'"inert":true')
        self.assertNotEqual(original, changed); self.assertEqual(json.loads(original), json.loads(changed))
        path.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'original authority'): self.validate_envelope((output, witness, prepared, binaries))

    def test_researcher_envelope_rejects_mutant_bytes_and_propagates_native_result_failures(self):
        envelope = self.researcher_envelope(); output = envelope[0]
        self.domain_check.side_effect = ValueError('Native control failed')
        with self.assertRaisesRegex(ValueError, 'Native control failed'): self.validate_envelope(envelope)
        self.archive_check.assert_not_called()
        self.domain_check.side_effect = None
        (output / scoped.FOLDER / 'staged-changed-fasta.zip').write_bytes(b'changed mutant')
        with self.assertRaisesRegex(ValueError, 'mutant bytes'): self.validate_envelope(envelope)

    def test_closed_routes_accept_real_pairs_and_reject_crossed_pairs_before_git(self):
        self.assertEqual(scoped.identity(self.root)['workflow_ref'], self.env['GITHUB_WORKFLOW_REF'])
        for workflow, branch in dev.WORKFLOW_ROUTES:
            ref = 'refs/heads/' + branch + 'example'
            with mock.patch.dict(os.environ, {'GITHUB_REF': ref, 'GITHUB_WORKFLOW_REF': f'owner/repository/{workflow}@{ref}'}):
                self.assertEqual(dev.identity(self.root)['ref'], ref)
                if workflow != scoped.WORKFLOW:
                    with mock.patch.object(dev, 'git', side_effect=AssertionError('No Git before scope rejection')), self.assertRaisesRegex(ValueError, 'own workflow'):
                        scoped.identity(self.root)
        with mock.patch.object(dev, 'git', side_effect=AssertionError('Invalid pair reached Git')):
            for workflow, branch in ((dev.WORKFLOW, 'codex/dev-researcher/'), (scoped.WORKFLOW, 'codex/dev-policy/'),
                                     (scoped.WORKFLOW, 'codex/dev-researcherish/'), ('.github/workflows/unreviewed.yml', 'codex/dev-researcher/')):
                ref = 'refs/heads/' + branch + 'example'
                with self.subTest(workflow=workflow, branch=branch), mock.patch.dict(os.environ, {
                    'GITHUB_REF': ref, 'GITHUB_WORKFLOW_REF': f'owner/repository/{workflow}@{ref}'}), self.assertRaises(ValueError):
                    dev.identity(self.root)
            with mock.patch.dict(os.environ, {'GITHUB_WORKFLOW_SHA': '3' * 40}), self.assertRaises(ValueError):
                dev.identity(self.root)
        self.assertEqual(self.calls, [])

    def test_wrapper_delegates_only_guarded_existing_stages(self):
        # The module's real fixed checkout root differs from this inert fixture.
        # Exercise dispatch with a mocked guard, never an altered environment.
        with mock.patch.object(scoped, 'identity') as guard, mock.patch.object(dev, 'prepare') as prepare, \
             mock.patch.object(dev, 'run') as run, mock.patch.object(dev, 'researcher_alpha_sdk') as sdk, \
             mock.patch.object(scoped, 'seal') as seal, mock.patch.object(dev, 'sdk_all', side_effect=AssertionError('No full SDK route')):
            for stage, delegate in (('prepare', prepare), ('run', run), ('sdk', sdk)):
                scoped.main([stage]); delegate.assert_called_once_with(ROOT)
            self.assertEqual(guard.call_count, 3); seal.assert_called_once_with(ROOT)
        with mock.patch.object(scoped, 'identity', side_effect=ValueError('wrong scope')), \
             mock.patch.object(dev, 'prepare') as prepare, mock.patch.object(dev, 'run') as run, mock.patch.object(dev, 'researcher_alpha_sdk') as sdk:
            for stage in ('prepare', 'run', 'sdk'):
                with self.assertRaises(ValueError): scoped.main([stage])
            for delegate in (prepare, run, sdk): delegate.assert_not_called()

    def test_complete_scoped_seal_is79_files_without_full_campaign_acceptance(self):
        output = self.evidence(); result = self.seal()
        self.assertEqual(len(self.calls), 34)  # Dependencies, build,31 suites,1 complete researcher command.
        self.assertEqual(result['schema'], scoped.SCHEMA)
        self.assertIs(result['acceptance'], False)
        self.assertEqual(result['scope'], scoped.SCOPE)
        self.assertEqual(len(result['files']), 78)
        self.assertEqual(len(list(output.rglob('*'))) - 1, 79)  # Exclude the one directory.
        self.assertEqual(len(result['binaries']), 34)
        self.assertEqual(sum(name.startswith(scoped.FOLDER + '/') for name in result['files']), 40)
        self.assertEqual(result['scope']['complete_development_sdk_observations'], 'not_run')
        self.assertIs(result['scope']['release_acceptance'], False)
        self.assertEqual(result['identity'], dev.identity(self.root))
        with self.assertRaisesRegex(ValueError, 'stale scoped output'): self.seal()

    def test_missing_extra_redirected_files_or_failed_native_run_cannot_seal(self):
        output = self.evidence()
        for name in ('build.log', scoped.FOLDER + '/authored-catalog-authorization.json',
                     scoped.FOLDER + '/staged-changed-candidate.zip'):
            path = output / name; raw = path.read_bytes(); path.unlink()
            with self.subTest(name=name), self.assertRaises(ValueError): self.seal()
            path.symlink_to(output / 'dependencies.log')
            with self.assertRaisesRegex(ValueError, 'redirected'): self.seal()
            path.unlink(); path.write_bytes(raw)
        extra = output / 'selection-sdk.json'; extra.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'extra or stale'): self.seal()
        extra.unlink()
        feedback = output / 'feedback.json'; raw = feedback.read_bytes(); value = json.loads(raw); value['suites'].pop()
        feedback.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'census'): self.seal()
        self.assertFalse((output / scoped.SEAL).exists())

    def test_stale_driver_or_modified_native_log_cannot_self_authorize(self):
        output = self.evidence()
        driver_path = output / 'researcher-alpha-sdk.json'; original = driver_path.read_bytes()
        for mutate in (lambda value: value['identity'].update(run_attempt='1'),
                       lambda value: value['actions'][0].update(returncode=False),
                       lambda value: value.update(acceptance=True),
                       lambda value: value['outputs'].update({'foreign.json': {'sha256': '0' * 64, 'size': 1}})):
            value = json.loads(original); mutate(value); driver_path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): self.seal()
        driver_path.write_bytes(original)
        (output / 'build.log').write_text('changed native log')
        with self.assertRaisesRegex(ValueError, 'command log'): self.seal()
        self.assertFalse((output / scoped.SEAL).exists())

    def test_native_zero_sizes_cannot_be_replaced_by_false_in_source_or_log_pins(self):
        output = self.evidence(); path = output / 'feedback.json'
        original = json.loads(path.read_bytes()); prepared = scoped.document(output, 'preparation.json')
        value = deepcopy(original)
        value['sources_before']['src/empty.py']['size'] = False
        dev.validate_native_feedback(self.root, value, prepared)  # Existing equality equates False and zero.
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'source or identity types'): self.seal()
        value = deepcopy(original)
        (output / 'build.log').write_bytes(b'')
        value['actions'][1]['log_pin'] = {'sha256': hashlib.sha256(b'').hexdigest(), 'size': False}
        dev.validate_native_feedback(self.root, value, prepared)
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'log pin types'): self.seal()
        self.assertFalse((output / scoped.SEAL).exists())

    def test_bounds_and_late_changes_fail_before_seal_publication(self):
        output = self.evidence()
        with mock.patch.object(scoped, 'MAX_TOTAL', 100), self.assertRaisesRegex(ValueError, 'aggregate byte'): self.seal()
        real = scoped.inventory
        def late_change(folder):
            result = real(folder)
            (folder / scoped.FOLDER / 'authored-catalog-no-publication.json').write_text('late tampering')
            return result
        with mock.patch.object(scoped, 'inventory', side_effect=late_change), self.assertRaises(ValueError): self.seal()
        self.assertFalse((output / scoped.SEAL).exists())

    def test_retained_observation_failure_cannot_publish_scoped_success(self):
        output = self.evidence()
        with mock.patch.object(scoped, 'validate_researcher', side_effect=AssertionError('native negative-control mismatch')), self.assertRaises(AssertionError):
            scoped.seal(self.root)
        self.assertFalse((output / scoped.SEAL).exists())

    def test_workflow_is_separate_and_complete_native_plan_is_unchanged(self):
        full = (ROOT / '.github/workflows/policy-development.yml').read_bytes()
        release = (ROOT / '.github/workflows/ci.yml').read_bytes()
        self.assertEqual(hashlib.sha256(full).hexdigest(), 'f57111477343cbc0ad76ec95c3fe7daca8b7b3341ede7318d5c79e8e76471102')
        self.assertEqual(hashlib.sha256(release).hexdigest(), '6d4bf0bf7bdb703af3ff904bbbebd37f3bdf30da101939b66423b5fd0b4e6c1c')
        focused = (ROOT / '.github/workflows/researcher-development.yml').read_text()
        self.assertIn("branches: ['codex/dev-researcher/**']", focused)
        self.assertNotIn('workflow_dispatch', focused)
        for value in ("runs-on: ubuntu-24.04", "python-version: '3.11.15'", "ocaml-compiler: '5.4.0'",
                      'ocaml/setup-ocaml@93303b622b2522e4411e295f9e77411a24912ac7',
                      'ac27950e5eac6c981ad809dff370c937820b7893', 'shell: bash', 'if: always()',
                      'name: researcher-development-feedback-${{ github.run_id }}-${{ github.run_attempt }}'):
            self.assertIn(value, focused)
        self.assertNotIn('check_policy_development.py', focused)
        self.assertEqual(len(dev.SUITES), 31)
        self.assertEqual(len(researcher.OBSERVATIONS), 30)
        self.assertEqual(len(scoped.evidence_names()), 78)


if __name__ == '__main__':
    unittest.main()
