"""Pure failure detail and finite source restoration; no campaign fixtures."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT/'tools/check_pipeline_fixed_continuation_install.py'


def definitions(path, names, namespace):
    """Load the actual selected pure definitions without campaign imports."""
    nodes = [node for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError('Missing selected source definition')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)


def pure_checker():
    namespace = {'json': json}
    definitions(ROOT/'tools/check_workflow_reproducibility.py', ('canonical', 'require'), namespace)
    definitions(ROOT/'tools/check_pipeline_session_install.py', ('equal',), namespace)
    definitions(CHECKER, ('public_graph_difference', 'equal_public_graph'), namespace)
    return namespace


class PublicGraphDiagnosticTests(unittest.TestCase):
    def test_success_uses_original_equal_and_never_requests_diagnostics(self):
        api = pure_checker()
        actual, expected = {'b': [1], 'a': True}, {'a': True, 'b': [1]}
        original, calls = api['equal'], []
        def equal(left, right, message):
            calls.append((left, right, message))
            return original(left, right, message)
        def forbidden(*args):
            raise AssertionError('Success called diagnostics')
        api.update(equal=equal, public_graph_difference=forbidden)
        self.assertIsNone(api['equal_public_graph'](actual, expected))
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], actual)
        self.assertIs(calls[0][1], expected)
        self.assertEqual(calls[0][2], 'Complete public native build values or physical identities differ')

    def test_mapping_order_failure_retains_exact_first_actual_and_expected_leaf(self):
        api = pure_checker()
        expected = {'roots': {'target': {'ref': 'object/0'}}, 'source_origins': [], 'nodes': [
            {'kind': 'mapping', 'class': 'dict', 'items': [
                [{'scalar': 'str', 'value': 'alpha'}, {'scalar': 'int', 'value': 1}],
                [{'scalar': 'str', 'value': 'beta'}, {'scalar': 'int', 'value': 2}]]}]}
        actual = deepcopy(expected)
        actual['nodes'][0]['items'].reverse()
        saved = deepcopy((actual, expected))
        with self.assertRaises(AssertionError) as caught:
            api['equal_public_graph'](actual, expected)
        prefix, raw = str(caught.exception).split('; first public graph difference: ', 1)
        self.assertEqual(prefix, 'Complete public native build values or physical identities differ')
        self.assertEqual(json.loads(raw), {'path': ['nodes', 0, 'items', 0, 0, 'value'],
            'reason': 'value', 'actual': {'type': 'str', 'length': 4, 'prefix': 'beta'},
            'expected': {'type': 'str', 'length': 5, 'prefix': 'alpha'}})
        self.assertEqual((actual, expected), saved)

    def test_canonical_scalar_types_signed_zero_missing_keys_and_lengths_stay_distinct(self):
        api = pure_checker()
        for actual, expected, reason in ((1, True, 'type'), (1, 1.0, 'type'),
                (-0.0, 0.0, 'value'), ({'a': 1}, {}, 'missing-key'), ([1], [1, 2], 'length')):
            with self.subTest(actual=actual, expected=expected):
                with self.assertRaises(AssertionError):
                    api['equal_public_graph'](actual, expected)
                self.assertEqual(json.loads(api['public_graph_difference'](actual, expected))['reason'], reason)

    def test_diagnostic_limits_are_bounded_and_do_not_call_live_object_hooks(self):
        api = pure_checker()
        left, right = [], []
        left.append(left); right.append(right)
        for actual, expected in ((left, right), ([None]*17_000, [None]*17_000),
                ('x'*5000, 'y'*5000), (1 << 1024, 1 << 1025),
                ({str(i): i for i in range(65)}, {})):
            raw = api['public_graph_difference'](actual, expected)
            self.assertLessEqual(len(raw.encode()), 8192)
            self.assertEqual(json.loads(raw)['reason'], 'scan-limit')
        class Hook:
            def __repr__(self):
                raise AssertionError('Diagnostic invoked repr')
            def __eq__(self, other):
                raise AssertionError('Diagnostic invoked equality')
        self.assertEqual(json.loads(api['public_graph_difference'](Hook(), Hook()))['reason'], 'unsupported')

    def test_failed_diagnostic_preserves_original_comparison_exception_and_nonassertion_errors(self):
        api = pure_checker()
        sentinel = AssertionError('original comparison')
        calls = []
        def fail(*args):
            calls.append('equal')
            raise sentinel
        def broken(*args):
            calls.append('diagnostic')
            raise ValueError('diagnostic error')
        api.update(equal=fail, public_graph_difference=broken)
        with self.assertRaises(AssertionError) as caught:
            api['equal_public_graph']({}, {})
        self.assertIs(caught.exception, sentinel)
        self.assertEqual(calls, ['equal', 'diagnostic'])
        self.assertEqual(str(sentinel), 'original comparison; first public graph difference: '
            '{"reason":"diagnostic-unavailable"}')
        other = ValueError('original serialization failure')
        def fail_other(*args):
            raise other
        api['equal'] = fail_other
        with self.assertRaises(ValueError) as caught:
            api['equal_public_graph']({}, {})
        self.assertIs(caught.exception, other)
        self.assertEqual(calls, ['equal', 'diagnostic'])


class PublicGraphDiagnosticSourceTests(unittest.TestCase):
    @staticmethod
    def plan():
        path = ROOT/'tests/test_prebuilt_ci_plan.py'
        spec = importlib.util.spec_from_file_location('graph_diagnostic_source_plan', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_new_delta_composes_before_unchanged_authoring_and_original_path_proofs(self):
        plan = self.plan()
        restored = plan.restore_public_graph_diagnostic_source(CHECKER.read_bytes(),
            plan.GRAPH_DIAGNOSTIC_DELTA.read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            '733d9823b203dc31c9f36715433f98ef654d08e1c6aba3cefb19e9b85e9447fd')
        restored = plan.restore_installed_authoring_source(restored, plan.AUTHORING_DELTA.read_bytes())
        original = json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/check_pipeline_fixed_continuation_install.py']['current_sha256'])
        before = Path(str(plan.SOURCE/'tools/check_pipeline_fixed_continuation_install.py')+'.source').read_text()
        def functions(source):
            return {node.name: ast.dump(node) for node in ast.parse(source).body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        old, new = functions(before), functions(restored)
        self.assertEqual(set(old), set(new))
        self.assertEqual([name for name in old if old[name] != new[name]], ['campaign_main'])

    def test_extra_source_omitted_diagnostic_and_rehashed_witness_are_rejected(self):
        plan = self.plan()
        current, witness = CHECKER.read_bytes(), plan.GRAPH_DIAGNOSTIC_DELTA.read_bytes()
        restored = plan.restore_public_graph_diagnostic_source(current, witness)
        for mutant in (restored, current+b'\n# unreviewed\n', current.replace(b'16_384', b'16_385'),
                current.replace(b'case[\'graph\'] = observed_public_graph(', b'case[\'graph\'] = unreviewed_graph('),
                current.replace(b'\n', b'\r\n')):
            self.assertNotEqual(mutant, current)
            with self.assertRaisesRegex(AssertionError, 'Current continuation driver differs'):
                plan.restore_public_graph_diagnostic_source(mutant, witness)
            forged = json.loads(witness)
            forged['current'] = {'bytes': len(mutant), 'sha256': hashlib.sha256(mutant).hexdigest()}
            with self.assertRaisesRegex(AssertionError, 'Unreviewed public-graph diagnostic source witness'):
                plan.restore_public_graph_diagnostic_source(mutant,
                    json.dumps(forged, sort_keys=True, indent=2).encode()+b'\n')
        forged = json.loads(witness)
        forged['spans'][0]['offset'] += 1
        with self.assertRaisesRegex(AssertionError, 'Unreviewed public-graph diagnostic source witness'):
            plan.restore_public_graph_diagnostic_source(current, json.dumps(forged).encode())


if __name__ == '__main__':
    unittest.main()
