"""Per-occurrence source restoration and isolated original source closure."""
import hashlib
import json
import unittest

from tools import pipeline_occurrence_source as source
from tools import pipeline_original_counterpart as counterpart


class OccurrenceSourceTests(unittest.TestCase):
    def test_exact_complete_predecessors_are_restored(self):
        proof = json.loads(source.WITNESS.read_bytes())
        for path, row in proof['files'].items():
            with self.subTest(path=path):
                current = (source.ROOT / path).read_bytes()
                restored = source.restore(path, current)
                self.assertNotEqual(current, restored)
                self.assertEqual({'bytes': len(restored), 'sha256': hashlib.sha256(restored).hexdigest()},
                    row['historical'])

    def test_extra_changes_and_rehashed_witnesses_are_rejected(self):
        proof = json.loads(source.WITNESS.read_bytes())
        for path in proof['files']:
            current = (source.ROOT / path).read_bytes()
            for changed in (current+b'\n# extra\n', current.replace(b'\n', b'\r\n'),
                    source.restore(path, current)):
                with self.subTest(path=path), self.assertRaisesRegex(AssertionError, 'Current source differs'):
                    source.restore(path, changed)
                forged = json.loads(source.WITNESS.read_bytes())
                forged['files'][path]['current'] = {'bytes': len(changed), 'sha256': hashlib.sha256(changed).hexdigest()}
                with self.assertRaisesRegex(AssertionError, 'Unreviewed per-occurrence'):
                    source.restore(path, changed, json.dumps(forged).encode())

    def test_new_original_task_keeps_the_complete_prior_source_and_data_closure(self):
        task = 'fixed-continuation-original'
        self.assertIn(task, counterpart.TASKS)
        old = set(counterpart.task_files('fixed-build-original'))
        new = set(counterpart.task_files(task))
        self.assertEqual(new, old)
        self.assertIn('tools/capture_pipeline_fixed_continuation_semantics.py', new)
        old_data = set(counterpart.task_data('fixed-build-original'))
        new_data = set(counterpart.task_data(task))
        self.assertFalse(old_data-new_data)
        from tools import check_pipeline_fixed_continuation_install as continuation
        corpus = continuation.Corpus()
        authorities = {'tests/conformance/fixed-pipeline-literals-v1/' + case['authority_sha256'] + '.json'
            for case in corpus.build['cases']}
        self.assertEqual(len(authorities), 6)
        self.assertEqual(new_data-old_data, authorities | {'data/references/fap_car/' + name for name in
            ('manifest.json', 'source-excerpts.html', 'independent-audit.json', 'curation.md')})
        for case in corpus.build['cases']:
            self.assertEqual(corpus.fixed.document('fixed', case['authority_sha256']), case['authority'])
        self.assertTrue(all((source.ROOT/path).is_file() for path in new_data))
        self.assertEqual(counterpart.reference_routes(task), counterpart.reference_routes('fixed-build-original'))
        self.assertTrue(all(not path.endswith(('.so', '.dylib', '.exe')) for path in new))

    def test_occurrence_controls_run_before_native_work_with_prior_preflight(self):
        workflow = (source.ROOT / '.github/workflows/ci.yml').read_text()
        preflight = workflow.split('  ci-preflight:', 1)[1].split('  unit-plan:', 1)[0]
        plan = workflow.split('  unit-plan:', 1)[1].split('  unit-tests:', 1)[0]
        self.assertIn('needs: ci-preflight', plan)
        for module in ('test_pipeline_authoring_sources', 'test_prebuilt_command_diagnostics',
                'test_pipeline_fixed_continuation_identity', 'test_pipeline_occurrence_source'):
            self.assertIn('tests.' + module, preflight)
            self.assertNotIn('tests.' + module, plan)
        native = workflow.split('  ocaml-build:', 1)[1].split('\n  ocaml-native-tests:', 1)[0]
        self.assertIn('needs: ci-preflight', native)
        core = workflow.split('  ocaml-core:', 1)[1].split('\n  architecture-sdk:', 1)[0]
        self.assertIn('needs: ocaml-build', core)


if __name__ == '__main__':
    unittest.main()
