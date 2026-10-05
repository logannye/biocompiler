"""Progress diagnostics leave campaign control flow and evidence unchanged."""
import ast
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from tools import check_pipeline_reference_install as gate


class ReferenceCampaignDiagnosticsTests(unittest.TestCase):
    def test_phase_markers_flush_elapsed_to_stderr(self):
        stream = io.StringIO()
        with patch.object(gate.sys, 'stderr', stream), \
                patch.object(gate.time, 'monotonic', side_effect=(10, 12.5)), \
                patch('builtins.print') as printed:
            with gate.diagnostic_phase('sample'):
                pass
        self.assertEqual(printed.call_args_list, [
            call('Reference campaign: sample started', file=stream, flush=True),
            call('Reference campaign: sample complete (2.500s)', file=stream, flush=True)])

    def test_phase_failure_preserves_original_exception(self):
        for error in (ValueError('original'), KeyboardInterrupt('original')):
            with self.subTest(kind=type(error).__name__), \
                    patch.object(gate.time, 'monotonic', side_effect=(10, 12.5)), \
                    patch('builtins.print') as printed:
                with self.assertRaises(type(error)) as caught:
                    with gate.diagnostic_phase('sample'):
                        raise error
                self.assertIs(caught.exception, error)
                self.assertEqual(printed.call_args_list[-1],
                    call('Reference campaign: sample failed (2.500s)', file=gate.sys.stderr, flush=True))

    def test_script_timer_is_repeated_and_cancelled_for_every_exit(self):
        tree = ast.parse(Path(gate.__file__).read_text())
        script = tree.body[-1]
        self.assertIsInstance(script, ast.If)
        code = compile(ast.Module(body=[script], type_ignores=[]), str(gate.__file__), 'exec')
        for outcome in (7, ValueError('original'), KeyboardInterrupt('original')):
            with self.subTest(outcome=repr(outcome)):
                events = Mock()
                handler = SimpleNamespace(dump_traceback_later=events.arm,
                                          cancel_dump_traceback_later=events.cancel)
                if isinstance(outcome, BaseException):
                    events.main.side_effect = outcome
                else:
                    events.main.return_value = outcome
                namespace = {'__name__': '__main__', 'faulthandler': handler,
                             'sys': gate.sys, 'main': events.main}
                expected = type(outcome) if isinstance(outcome, BaseException) else SystemExit
                with self.assertRaises(expected) as caught:
                    exec(code, namespace)
                if isinstance(outcome, BaseException):
                    self.assertIs(caught.exception, outcome)
                else:
                    self.assertEqual(caught.exception.code, outcome)
                self.assertEqual(events.mock_calls, [
                    call.arm(300, repeat=True, file=gate.sys.stderr), call.main(), call.cancel()])

    def test_phase_removal_recovers_every_original_statement(self):
        labels = []

        def document(node):
            if isinstance(node, ast.AST):
                # Empty generic parameters were added to the AST after 3.11.
                return [type(node).__name__, [[key, document(value)] for key, value in ast.iter_fields(node)
                    if not (key == 'type_params' and value == [])]]
            if type(node) is list:
                return [document(value) for value in node]
            return node

        class RemoveDiagnostics(ast.NodeTransformer):
            def visit_With(self, node):
                self.generic_visit(node)
                if len(node.items) == 1:
                    expression = node.items[0].context_expr
                    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name) \
                            and expression.func.id == 'diagnostic_phase':
                        labels.append(ast.literal_eval(expression.args[0]))
                        return node.body
                return node

        expected = {
            'run_bodies': '1d821ae2aa97abc7a0bcaaa74dc0f5116b75707bb19b06f8af7fb7ddefd9fb56',
            'run_observed': '08b56704bee0ad441b27dbc33a5ae07132ee336e586980ebc2f7592aa87a3a98',
            'reconstruct': 'ca90e9d240fa3d25d5b76da3d27f1907192bb08f367f37fb67c909a6c7215522',
        }
        for function in ast.parse(Path(gate.__file__).read_text()).body:
            if isinstance(function, ast.FunctionDef) and function.name in expected:
                restored = RemoveDiagnostics().visit(function)
                self.assertEqual(hashlib.sha256(json.dumps(document(restored), separators=(',', ':')).encode()).hexdigest(),
                                 expected[function.name])
        self.assertCountEqual(labels, ['run_observed', 'run_bodies', 'cleanup', 'reconstruct'])


if __name__ == '__main__':
    unittest.main()
