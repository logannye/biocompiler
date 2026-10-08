"""External-cwd original authoring remains exact; no installed/native execution."""
from contextlib import chdir, contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler.frontend.graph as graph
from examples import checked_pipeline, temporal_pipeline
from tools import freeze_realization_acceptance as frozen
from tools import pipeline_authoring_sources as authoring

ROOT = Path(__file__).resolve().parents[1]


def authored_bytes(function):
    request, history = function()
    return json.dumps({'request': request.to_dict(), 'history': [frame.to_dict() for frame in history]},
                      sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class AuthoringSourceTests(unittest.TestCase):
    def setUp(self):
        self.external = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.enterContext(chdir(self.external))
        self.original_factory = graph.SourceLocation
        self.portable = authoring.bind_portable_sources(frozen.portable_sources, ROOT)

    def test_original_temporal_external_cwd_failure_is_reproduced(self):
        with self.assertRaises(ValueError) as raised:
            with frozen.portable_sources():
                temporal_pipeline.build_request()
        self.assertIn(str(self.external / 'examples/temporal_pipeline.py'), str(raised.exception))
        self.assertEqual(Path.cwd(), self.external)
        self.assertIs(graph.SourceLocation, self.original_factory)

    def test_actual_temporal_authoring_retains_all_original_bytes_and_logical_sources(self):
        with chdir(ROOT), frozen.portable_sources():
            expected = authored_bytes(temporal_pipeline.build_request)
        with self.portable():
            self.assertEqual(Path.cwd(), self.external)
            actual = authored_bytes(temporal_pipeline.build_request)
        self.assertEqual(actual, expected)
        self.assertIn(b'examples/temporal_pipeline.py', actual)
        self.assertNotIn(str(ROOT).encode(), actual)
        self.assertEqual(Path.cwd(), self.external)
        self.assertIs(graph.SourceLocation, self.original_factory)

    def test_actual_non_temporal_authoring_is_unchanged(self):
        with chdir(ROOT), frozen.portable_sources():
            expected = authored_bytes(checked_pipeline.build_request)
        with self.portable():
            actual = authored_bytes(checked_pipeline.build_request)
        self.assertEqual(actual, expected)
        self.assertIn(b'/__biocompiler_capture__/examples/checked_pipeline.py', actual)
        self.assertEqual(Path.cwd(), self.external)
        self.assertIs(graph.SourceLocation, self.original_factory)

    def test_non_temporal_factory_arguments_order_and_foreign_source_rejection_remain(self):
        calls = []

        def factory(*args):
            calls.append(args)
            return self.original_factory(*args)

        inputs = [(str(ROOT / 'examples/checked_pipeline.py'), 17, 'build_request'),
                  ('relative_fixture.py', 29, 'nested'), ('examples/temporal_pipeline.py.extra', 31, 'other')]
        with patch.object(graph, 'SourceLocation', factory):
            with frozen.portable_sources():
                expected = [graph.SourceLocation(*args) for args in inputs]
            original_calls = calls[:]
            calls.clear()
            with self.portable():
                actual = [graph.SourceLocation(*args) for args in inputs]
                with self.assertRaises(ValueError):
                    graph.SourceLocation(str(self.external / 'foreign.py'), 1, 'foreign')
            self.assertEqual(calls, original_calls)
            self.assertEqual(actual, expected)
            self.assertIs(graph.SourceLocation, factory)
        self.assertIs(graph.SourceLocation, self.original_factory)

    def test_original_context_and_body_exceptions_restore_factory_and_cwd(self):
        error = RuntimeError('original authoring error')
        events = []

        @contextmanager
        def fails_on_entry():
            events.append('enter')
            raise error
            yield

        with self.assertRaises(RuntimeError) as raised:
            with authoring.bind_portable_sources(fails_on_entry, ROOT)():
                self.fail('entry error was swallowed')
        self.assertIs(raised.exception, error)
        self.assertEqual(events, ['enter'])
        self.assertIs(graph.SourceLocation, self.original_factory)
        with self.assertRaises(RuntimeError) as raised:
            with self.portable():
                raise error
        self.assertIs(raised.exception, error)
        self.assertEqual(Path.cwd(), self.external)
        self.assertIs(graph.SourceLocation, self.original_factory)

    def test_oracle_loader_binds_shared_context_and_finite_child_source_closure(self):
        from tools import check_pipeline_fixed_continuation_install as continuation
        from tools import check_pipeline_fixed_registration_install as registration
        from tools import pipeline_original_counterpart as counterpart
        oracle = continuation.load_oracle(installed=False)
        self.assertIs(oracle.portable_sources.__wrapped__, frozen.portable_sources)
        with oracle.portable_sources():
            actual = authored_bytes(temporal_pipeline.build_request)
        with chdir(ROOT), frozen.portable_sources():
            expected = authored_bytes(temporal_pipeline.build_request)
        self.assertEqual(actual, expected)
        self.assertEqual(Path.cwd(), self.external)
        self.assertIs(graph.SourceLocation, self.original_factory)
        for path in ('tools/pipeline_authoring_sources.py', 'tests/test_pipeline_authoring_sources.py'):
            self.assertIn(path, continuation.SOURCES)
            self.assertIn(path, registration.SOURCES)
        self.assertIn('tools/pipeline_authoring_sources.py', registration.overlay_files())
        for task in ('fixed-provider-original', 'fixed-build-original', 'fixed-registration-original'):
            self.assertIn('tools/pipeline_authoring_sources.py', counterpart.task_files(task))


if __name__ == '__main__':
    unittest.main()
