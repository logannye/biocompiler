"""Pure Python adapter controls; no native execution or acceptance oracle."""
from pathlib import Path
import sys
from types import FunctionType
import unittest
from unittest.mock import patch

from biocompiler import core_reference_package_host as host


class PackageHostTests(unittest.TestCase):
    def test_all_native_choices_retain_exact_arguments_without_semantics(self):
        owner = host.PackageHost()
        argument, keyword = object(), object()
        for name in host._DEFAULTS:
            value = owner.call(name, argument, exact=keyword)
            self.assertIs(type(value), host.NativeCall)
            self.assertIs(value.args[0], argument)
            self.assertIs(value.kwargs['exact'], keyword)
            self.assertIs(value.owner, owner._owner)

    def test_actual_current_replacement_runs_once_and_retains_output(self):
        owner = host.PackageHost()
        argument, result, calls = object(), object(), []
        def replacement(value, *, exact):
            calls.append((value, exact))
            return result
        for name in host._DEFAULTS:
            module = host._SEQUENCES if name == 'check_molecular' else host._REFERENCE
            with patch.object(module, name, replacement):
                returned = owner.call(name, argument, exact=result)
            self.assertIs(owner.unwrap(returned), result)
            self.assertIs(calls[-1][0], argument)
            self.assertIs(calls[-1][1], result)
        self.assertEqual(len(calls), len(host._DEFAULTS))

    def test_verify_default_keeps_current_public_alias_replacement(self):
        owner = host.PackageHost()
        replacement = lambda: None
        with patch.object(host._SEQUENCES, 'check_molecular', replacement):
            self.assertIs(owner.verify_default('check_molecular'), host._DEFAULTS['check_molecular'].function)
            self.assertIs(host._SEQUENCES.check_molecular, replacement)
        with self.assertRaisesRegex(host.PackageBoundaryError, 'Unknown'):
            owner.verify_default('unknown')

    def test_base_exception_identity_and_no_output_observation(self):
        owner = host.PackageHost()
        for error in (RuntimeError('original'), KeyboardInterrupt('interrupt'), SystemExit('exit')):
            def replacement():
                raise error
            with patch.object(host._REFERENCE, 'check_construct', replacement):
                with self.assertRaises(type(error)) as caught:
                    owner.call('check_construct')
            self.assertIs(caught.exception, error)
        class Opaque:
            def __getattribute__(self, name):
                raise AssertionError('output observed: ' + name)
        result = Opaque()
        with patch.object(host._REFERENCE, 'export_reference_sequence', lambda: result):
            self.assertIs(owner.unwrap(owner.call('export_reference_sequence')), result)

    def test_mutated_retained_default_cannot_be_used_as_native(self):
        source = host._DEFAULTS['check_construct']
        code = source.function.__code__
        try:
            source.function.__code__ = (lambda *args, **kwargs: None).__code__
            with self.assertRaisesRegex(host.PackageBoundaryError, 'code or globals'):
                host.PackageHost().call('check_construct')
        finally:
            source.function.__code__ = code
        source = host._DEFAULTS['export_reference_sequence']
        prior = source.function.__kwdefaults__
        try:
            source.function.__kwdefaults__ = dict(prior, line_width=81)
            with self.assertRaisesRegex(host.PackageBoundaryError, 'argument values'):
                host.PackageHost().call('export_reference_sequence')
        finally:
            source.function.__kwdefaults__ = prior

    def test_distinct_code_copy_with_new_globals_is_an_actual_replacement(self):
        owner = host.PackageHost()
        original = host._DEFAULTS['_tools'].function
        calls, marker = [], object()
        def tool(key, value, pin):
            calls.append((key, value, pin))
            return marker
        namespace = dict(original.__globals__, ToolPin=tool, fingerprint=lambda value: ('host', value))
        replacement = FunctionType(original.__code__, namespace, original.__name__)
        with patch.object(host._REFERENCE, '_tools', replacement):
            result = owner.unwrap(owner.call('_tools'))
        self.assertEqual(len(calls), 13)
        self.assertTrue(all(value is marker for value in result))

    def test_late_current_versions_and_native_pin_construction_boundary(self):
        owner = host.PackageHost()
        with patch.object(host.biocompiler, '__version__', 'changed-sdk'):
            self.assertEqual(owner.package_version(), 'changed-sdk')
        with patch.object(host._REFERENCE, 'ToolPin', side_effect=AssertionError('semantic constructor')):
            with patch.object(host._REFERENCE, 'MOLECULAR_CHECKER_VERSION', 'current-checker'):
                versions = dict(owner.tool_versions(owner.call('_tools')))
        self.assertEqual(versions['molecular_checker'], 'current-checker')
        self.assertEqual(len(versions), 13)

    def test_foreign_outputs_and_foreign_tool_calls_reject(self):
        first, second = host.PackageHost(), host.PackageHost()
        with patch.object(host._REFERENCE, 'check_composition', lambda: object()):
            value = first.call('check_composition')
        with self.assertRaisesRegex(host.PackageBoundaryError, 'another owner'):
            second.unwrap(value)
        with self.assertRaisesRegex(host.PackageBoundaryError, 'foreign source call'):
            second.tool_versions(first.call('_tools'))
        with self.assertRaisesRegex(host.PackageBoundaryError, 'Unknown'):
            first.call('arbitrary_name')

    def test_forged_host_pass_is_only_opaque_data(self):
        owner = host.PackageHost()
        forged = {'passed': True, 'specification_bytes': b'forged', 'fasta_bytes': b'forged'}
        for name in ('check_composition', 'check_construct', 'export_reference_sequence'):
            with patch.object(host._REFERENCE, name, lambda: forged):
                result = owner.call(name)
            self.assertIs(type(result), host.HostValue)
            self.assertIs(owner.unwrap(result), forged)
            self.assertFalse(hasattr(result, 'accepted'))


if __name__ == '__main__':
    unittest.main()
