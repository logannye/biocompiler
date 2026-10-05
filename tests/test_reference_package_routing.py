"""Explicit selection and public callpoint controls, without native acceptance."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
from unittest.mock import patch

import biocompiler
from biocompiler.artifacts import sequences
from biocompiler.compiler import reference
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.reference_package_backend import (
    PackageRoute, UNSELECTED, at_default, current, default, reference_package_core,
)
from biocompiler.registry import reference_builds
from biocompiler.verification import components, construct, molecular

# Retain real public/SDK aliases before any native selection is entered.
PREPARE = biocompiler.prepare_reference_build
BUILD = biocompiler.build_reference_package
VERIFY = biocompiler.verify_reference_package
PUBLISH = biocompiler.publish_reference_package
EXPORT = biocompiler.export_reference_sequence


class ReferencePackageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.core = CoreClient(Path('/package-route-fixture/core'), expected_sha256='a' * 64)
        self.verify = CoreClient(Path('/package-route-fixture/verify'), role='verify', expected_sha256='b' * 64)

    def test_selection_keeps_explicit_roles_pins_timeout_and_detached_limits(self):
        limits = {'max_members': 30}
        self.assertIsNone(current())
        with patch.object(CoreClient, 'call', side_effect=AssertionError('Selection launched a process')):
            with reference_package_core(self.core, self.verify, timeout=45, limits=limits) as selected:
                self.assertIs(current(), selected)
                self.assertEqual((selected.core.executable, selected.core.expected_sha256),
                                 (self.core.executable, 'a' * 64))
                self.assertEqual((selected.verify.role, selected.verify.expected_sha256), ('verify', 'b' * 64))
                self.assertEqual((selected.core.timeout_seconds, selected.verify.timeout_seconds), (45, 45))
                limits['max_members'] = 1
                self.assertEqual(selected.limits, {'max_members': 30})
                copy = selected.limits
                copy['max_members'] = 2
                self.assertEqual(selected.limits, {'max_members': 30})
        self.assertIsNone(current())
        self.assertEqual(self.core.timeout_seconds, 30)

    def test_wrong_roles_or_client_subclasses_are_rejected_before_selection(self):
        class ClientSubclass(CoreClient):
            pass
        cases = ((self.verify, self.core), (self.core, self.core),
                 (ClientSubclass(self.core.executable), self.verify), (object(), self.verify))
        for core, verify in cases:
            with self.subTest(core=type(core), verify=type(verify)):
                with self.assertRaises(TypeError):
                    with reference_package_core(core, verify):
                        self.fail('Invalid selection became current')
                self.assertIsNone(current())

    def test_nested_selection_and_exception_restore_actual_outer_route(self):
        error = KeyboardInterrupt('current callpoint')
        with reference_package_core(self.core, self.verify) as outer:
            with self.assertRaises(KeyboardInterrupt) as raised:
                with reference_package_core(self.core, self.verify) as inner:
                    self.assertIs(current(), inner)
                    self.assertIsNot(inner, outer)
                    raise error
            self.assertIs(raised.exception, error)
            self.assertIs(current(), outer)
        self.assertIsNone(current())

    def test_another_thread_does_not_inherit_selected_owner(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            with reference_package_core(self.core, self.verify):
                self.assertIsNone(worker.submit(current).result())

    def test_all_captured_public_aliases_route_exact_arguments(self):
        self.assertIs(PREPARE, reference.prepare_reference_build)
        self.assertIs(BUILD, reference.build_reference_package)
        self.assertIs(VERIFY, reference.verify_reference_package)
        self.assertIs(PUBLISH, reference.publish_reference_package)
        self.assertIs(EXPORT, sequences.export_reference_sequence)
        self.assertIs(reference.export_reference_sequence, EXPORT)
        sentinels = tuple(object() for _ in range(7))
        cases = (
            ('prepare', PREPARE, sentinels[:2], {'fasta_line_width': sentinels[2]}),
            ('build', BUILD, sentinels[:2], {'run_metadata': sentinels[2]}),
            ('reconstruct', VERIFY, sentinels[:1], {'expected_request': sentinels[1],
                                                 'expected_build_fingerprint': sentinels[2]}),
            ('publish', PUBLISH, sentinels[:2], {}),
            ('export', EXPORT, sentinels[:5], {'line_width': sentinels[5]}),
        )
        with reference_package_core(self.core, self.verify) as selected:
            for method, public, args, kwargs in cases:
                with self.subTest(method=method), patch.object(PackageRoute, method, autospec=True,
                                                             return_value=sentinels[6]) as routed:
                    self.assertIs(public(*args, **kwargs), sentinels[6])
                    actual_args, actual_kwargs = routed.call_args
                    self.assertEqual(len(actual_args), len(args) + 1)
                    self.assertIs(actual_args[0], selected)
                    for actual, expected in zip(actual_args[1:], args):
                        self.assertIs(actual, expected)
                    self.assertEqual(set(actual_kwargs), set(kwargs))
                    for name, value in kwargs.items():
                        self.assertIs(actual_kwargs[name], value)
                    self.assertEqual(routed.call_count, 1)

    def test_selected_route_exception_propagates_once_without_python_fallback(self):
        for error in (CoreProtocolError('protocol result'), KeyboardInterrupt('host interruption')):
            with reference_package_core(self.core, self.verify):
                with patch.object(PackageRoute, 'build', side_effect=error) as routed, \
                        patch.object(reference, 'require_software_use', side_effect=AssertionError('Python fallback')):
                    with self.assertRaises(type(error)) as raised:
                        BUILD(object(), object())
                    self.assertIs(raised.exception, error)
                    self.assertEqual(routed.call_count, 1)

    def test_scoped_default_callbacks_keep_actual_aliases_and_exact_values(self):
        arguments = tuple(object() for _ in range(5))
        answer, calls = object(), []
        cases = (
            ('load_reference_inputs', reference_builds.load_reference_inputs, arguments[:2]),
            ('collect_reference_files', reference_builds.collect_reference_files, arguments[:2]),
            ('_tools', reference._tools, ()),
            ('check_composition', components.check_composition, arguments[:2]),
            ('check_construct', construct.check_construct, arguments[:4]),
            ('check_molecular', molecular.check_molecular, arguments),
        )
        for name, public, args in cases:
            def callback(*actual, **kwargs):
                calls.append((actual, kwargs))
                return answer
            with self.subTest(name=name), at_default(name, callback):
                self.assertIs(public(*args), answer)
            self.assertEqual(calls[-1][1], {})
            for actual, expected in zip(calls[-1][0], args):
                self.assertIs(actual, expected)
            self.assertIs(default(name, *args), UNSELECTED)
        self.assertEqual(len(calls), len(cases))

    def test_scoped_default_context_restores_on_opaque_exception(self):
        sentinel = object()
        error = CoreProtocolError('actual user exception')
        with at_default('outer', lambda: sentinel):
            with self.assertRaises(CoreProtocolError) as raised:
                with at_default('inner', lambda: (_ for _ in ()).throw(error)):
                    self.assertIs(default('outer'), UNSELECTED)
                    default('inner')
            self.assertIs(raised.exception, error)
            self.assertIs(default('outer'), sentinel)
        self.assertIs(default('outer'), UNSELECTED)


if __name__ == '__main__':
    unittest.main()
