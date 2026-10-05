"""Package orchestration against scripted Python peers, not native acceptance."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import biocompiler
from biocompiler.compiler import reference
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_package_owner import PackageBoundaryError
from biocompiler.core_pipeline_callback_session import CallbackRejected
from biocompiler import core_reference_package_route as route
from biocompiler.core_reference_package_views import PackageViews
from biocompiler.errors import SerializationError
from biocompiler.pipeline_callback_objects import CallbackObjects

ROOT = Path(__file__).resolve().parents[1]


class ReferencePackageRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = reference.prepare_reference_build('DNA', ROOT / 'data/references/fap_car')
        # Existing Python output is only fixture material here. A scripted peer
        # cannot create acceptance or substitute for the installed 32-method run.
        cls.package = reference.build_reference_package(cls.request, ROOT / 'data/references/fap_car')
        cls.tools = reference._tools()
        _, _, cls.registry = reference.load_reference_inputs('DNA', ROOT / 'data/references/fap_car')
        cls.link = reference.check_composition(cls.request.construct.composition, cls.registry)

    def setUp(self):
        self.core = CoreClient(Path('/package-route-fixture/core'), expected_sha256='a' * 64)
        self.verify = CoreClient(Path('/package-route-fixture/verify'), role='verify', expected_sha256='b' * 64)
        self.selected = SimpleNamespace(core=self.core, verify=self.verify)
        self.events = []

    def runtime(self, package=None):
        package = self.package if package is None else package
        runtime = object.__new__(route._Runtime)
        runtime.route = self.selected
        runtime.files = SimpleNamespace(input_descriptor={'bytes': len(package.data), 'sha256': package.archive_sha256})
        runtime.views = PackageViews()
        from biocompiler.core_reference_package_host import PackageHost
        runtime.host = PackageHost()
        runtime.rebuilt = package
        runtime.packages = [(package, 'actual-package')]
        runtime.package_version = biocompiler.__version__
        runtime.tool_pins = self.tools
        runtime.authorities = [(package, biocompiler.__version__, self.tools)]
        runtime.response = {
            'capability': 'actual-package', 'request': package.request.to_dict(),
            'manifest': package.manifest.to_dict(),
            'archive': {'bytes': len(package.data), 'sha256': package.archive_sha256},
            'build_fingerprint': package.build_fingerprint,
        }
        def call(operation, arguments):
            self.events.append((operation, arguments))
            self.assertEqual(operation, 'package-reconstruct')
            return runtime.response
        runtime.call = call
        return runtime

    def selected_runtime(self, runtime):
        @contextmanager
        def enter(selected, archive=None):
            self.assertIs(selected, self.selected)
            self.events.append(('runtime', archive))
            yield runtime
        return patch.object(route, '_runtime', enter)

    def standalone(self, **options):
        return patch('biocompiler.core_reference_package_verify.verify_package', **options)

    def test_bad_build_and_missing_or_wrong_verify_authority_precede_owner_creation(self):
        with patch.object(route, '_runtime', side_effect=AssertionError('Owner created before authority checks')):
            with self.assertRaisesRegex(SerializationError, 'frozen ReferenceBuildRequest'):
                route.build(self.selected, object(), object())
            with self.assertRaisesRegex(SerializationError, 'independently trusted'):
                route.reconstruct(self.selected, object())
            with self.assertRaisesRegex(SerializationError, 'frozen ReferenceBuildRequest'):
                route.reconstruct(self.selected, object(), expected_request=object())

    def test_prepare_preserves_exact_loaded_construct_identity(self):
        construct = self.request.construct
        runtime = SimpleNamespace(views=PackageViews())
        runtime.load = lambda alphabet, directory: ((construct, object(), object()), 'loaded-here')
        def call(operation, arguments):
            self.assertEqual(operation, 'package-prepare')
            self.assertEqual(arguments, {'inputs': 'loaded-here', 'line_width': 80})
            return self.request.to_dict()
        runtime.call = call
        with self.selected_runtime(runtime):
            prepared = route.prepare(self.selected, 'DNA', object())
        self.assertIs(prepared.construct, construct)
        self.assertIsNot(prepared, self.request)

    def test_build_forwards_actual_request_directory_metadata_once(self):
        directory, metadata = object(), object()
        runtime = SimpleNamespace()
        def built(request, actual_directory, actual_metadata):
            self.assertIs(request, self.request)
            self.assertIs(actual_directory, directory)
            self.assertIs(actual_metadata, metadata)
            return self.package
        runtime.built = built
        with self.selected_runtime(runtime):
            self.assertIs(route.build(self.selected, self.request, directory, run_metadata=metadata), self.package)

    def test_direct_export_retains_five_actual_roots_and_line_width(self):
        arguments = tuple(object() for _ in range(5))
        width, exported = 87, object()
        runtime = SimpleNamespace()
        def export(actual, actual_width):
            for expected, item in zip(arguments, actual):
                self.assertIs(item, expected)
            self.assertIs(actual_width, width)
            return exported
        runtime.exported = export
        with self.selected_runtime(runtime):
            self.assertIs(route.export(self.selected, *arguments, line_width=width), exported)

    def test_reconstruct_runs_current_core_then_independent_verify_and_returns_actual_build(self):
        runtime = self.runtime()
        def verify(client, data, **authority):
            self.events.append(('standalone-verify', authority))
            self.assertIs(client, self.verify)
            self.assertIs(data, self.package.data)
            self.assertEqual(authority['expected_request'], self.request.to_dict())
            self.assertEqual(authority['expected_build_fingerprint'], self.package.build_fingerprint)
            self.assertEqual(authority['tool_pins'], [item.to_dict() for item in self.tools])
        with self.selected_runtime(runtime), self.standalone(side_effect=verify) as checker:
            actual = route.reconstruct(self.selected, self.package.data, expected_request=self.request,
                                       expected_build_fingerprint=self.package.build_fingerprint)
        self.assertIs(actual, self.package)
        self.assertEqual([event[0] for event in self.events], ['runtime', 'package-reconstruct', 'standalone-verify'])
        self.assertEqual(checker.call_count, 1)

    def test_reconstruct_rejects_another_same_owner_package_token(self):
        runtime = self.runtime()
        runtime.response['capability'] = 'previous-package'
        with self.selected_runtime(runtime), self.standalone() as checker:
            with self.assertRaises(PackageBoundaryError):
                route.reconstruct(self.selected, self.package.data, expected_request=self.request)
        checker.assert_not_called()

    def test_reconstruct_rejects_changed_native_build_fingerprint(self):
        runtime = self.runtime()
        runtime.response['build_fingerprint'] = '0' * 64
        with self.selected_runtime(runtime), self.standalone() as checker:
            with self.assertRaises(PackageBoundaryError):
                route.reconstruct(self.selected, self.package.data, expected_request=self.request)
        checker.assert_not_called()

    def test_reconstruct_without_current_public_build_never_reaches_verify(self):
        runtime = self.runtime()
        runtime.packages = []
        with self.selected_runtime(runtime), self.standalone() as checker:
            with self.assertRaisesRegex(PackageBoundaryError, 'current public build'):
                route.reconstruct(self.selected, self.package.data, expected_request=self.request)
        checker.assert_not_called()

    def test_reconstruct_requires_authority_owned_by_actual_returned_package(self):
        runtime = self.runtime()
        copied = reference.ReferencePackage(self.package.request, self.package.manifest, self.package.data)
        runtime.authorities = [(copied, biocompiler.__version__, self.tools)]
        with self.selected_runtime(runtime), self.standalone() as checker:
            with self.assertRaisesRegex(PackageBoundaryError, 'current tool authority'):
                route.reconstruct(self.selected, self.package.data, expected_request=self.request)
        checker.assert_not_called()

    def test_rebuild_uses_actual_current_public_build_and_cleans_temporary_files(self):
        runtime = self.runtime()
        runtime.rebuilt = None
        runtime.packages = []
        seen = []
        def current_build(request, directory, *, run_metadata):
            seen.append(directory)
            self.assertEqual(request.to_dict(), self.request.to_dict())
            self.assertEqual((directory / 'nested/source.txt').read_bytes(), b'exact retained bytes')
            self.assertIsNone(run_metadata)
            runtime.packages.append((self.package, 'current-build'))
            return self.package
        with patch.object(reference, 'build_reference_package', current_build):
            result = runtime.invoke('package-rebuild', {'request': self.request.to_dict(),
                'files': [['nested/source.txt', b'exact retained bytes'.hex()]], 'run_metadata': None})
        self.assertEqual(result, {'capability': 'current-build'})
        self.assertIs(runtime.rebuilt, self.package)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_rebuild_preserves_current_build_exception_and_cleans_files(self):
        runtime = self.runtime()
        error, seen = CoreProtocolError('raised by actual public wrapper'), []
        def current_build(request, directory, *, run_metadata):
            seen.append(directory)
            raise error
        with patch.object(reference, 'build_reference_package', current_build):
            with self.assertRaises(CoreProtocolError) as raised:
                runtime.invoke('package-rebuild', {'request': self.request.to_dict(),
                    'files': [['source.txt', '']], 'run_metadata': None})
        self.assertIs(raised.exception, error)
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_rebuild_rejects_equal_but_unregistered_package(self):
        runtime = self.runtime()
        copied = reference.ReferencePackage(self.package.request, self.package.manifest, self.package.data)
        with patch.object(reference, 'build_reference_package', return_value=copied):
            with self.assertRaisesRegex(PackageBoundaryError, 'same-owner native package'):
                runtime.invoke('package-rebuild', {'request': self.request.to_dict(), 'files': [], 'run_metadata': None})

    def test_publish_runs_current_verify_wrapper_then_atomic_write(self):
        runtime = self.runtime()
        output, published = object(), object()
        def current_verify(data, **authority):
            self.events.append(('current-verify', authority))
            return route.reconstruct(self.selected, data, **authority)
        def write(destination, data):
            self.events.append(('atomic-write', data))
            self.assertIs(destination, output)
            self.assertIs(data, self.package.data)
            return published
        with self.selected_runtime(runtime), self.standalone(), \
                patch.object(reference, 'verify_reference_package', current_verify), \
                patch.object(reference, 'write_archive_atomic', write):
            self.assertIs(route.publish(self.selected, self.package, output), published)
        self.assertEqual([event[0] for event in self.events],
                         ['current-verify', 'runtime', 'package-reconstruct', 'atomic-write'])

    def test_publish_rejects_wrapper_copy_even_after_successful_fresh_verification(self):
        runtime = self.runtime()
        def current_verify(data, **authority):
            checked = route.reconstruct(self.selected, data, **authority)
            return reference.ReferencePackage(checked.request, checked.manifest, checked.data)
        with self.selected_runtime(runtime), self.standalone(), \
                patch.object(reference, 'verify_reference_package', current_verify), \
                patch.object(reference, 'write_archive_atomic') as write:
            with self.assertRaisesRegex(PackageBoundaryError, 'fresh native verification'):
                route.publish(self.selected, self.package, object())
        write.assert_not_called()

    def test_publish_never_writes_after_verify_override_or_exception(self):
        errors = (None, CoreProtocolError('actual user verification failure'), KeyboardInterrupt('interrupted'))
        for error in errors:
            with self.subTest(error=error), \
                    patch.object(reference, 'verify_reference_package', side_effect=error, return_value=self.package), \
                    patch.object(reference, 'write_archive_atomic') as write:
                if error is None:
                    with self.assertRaises(PackageBoundaryError):
                        route.publish(self.selected, self.package, object())
                else:
                    with self.assertRaises(type(error)) as raised:
                        route.publish(self.selected, self.package, object())
                    self.assertIs(raised.exception, error)
            write.assert_not_called()

    def test_standalone_verify_failure_does_not_authorize_publication(self):
        runtime = self.runtime()
        error = CoreProtocolError('independent Verify rejected fixture')
        receipt = []
        token = route._PUBLICATION.set(receipt)
        try:
            with self.selected_runtime(runtime), self.standalone(side_effect=error):
                with self.assertRaises(CoreProtocolError) as raised:
                    route.reconstruct(self.selected, self.package.data, expected_request=self.request)
            self.assertIs(raised.exception, error)
            self.assertEqual(receipt, [])
        finally:
            route._PUBLICATION.reset(token)

    def test_rebuild_rejects_unsafe_members_before_current_build(self):
        runtime = self.runtime()
        for name in ('../escape', '/absolute', 'a/../b', 'a//b', 'a\\b'):
            with self.subTest(name=name), patch.object(reference, 'build_reference_package') as build:
                with self.assertRaises(PackageBoundaryError):
                    runtime.invoke('package-rebuild', {'request': self.request.to_dict(),
                        'files': [[name, '']], 'run_metadata': None})
            build.assert_not_called()

    def checker_runtime(self):
        runtime = self.runtime()
        objects = CallbackObjects()
        self.addCleanup(objects.close)
        runtime.owner = SimpleNamespace(objects=objects)
        runtime.request = self.request
        runtime.registry = self.registry
        def call(operation, arguments):
            self.events.append((operation, arguments))
            self.assertEqual((operation, arguments), ('package-check-native', {'check_id': 'current-check'}))
            return self.link.to_dict()
        runtime.call = call
        raw = {'name': 'composition', 'check_id': 'current-check', 'arguments': {
            'request': self.request.construct.composition.to_dict(), 'registry': self.registry.to_dict()}}
        return runtime, raw

    def test_actual_checker_wrapper_calls_captured_default_at_its_current_callpoint(self):
        runtime, raw = self.checker_runtime()
        captured = reference.check_composition
        def wrapper(request, registry):
            self.events.append(('wrapper-enter', None))
            self.assertIs(request, self.request.construct.composition)
            self.assertIs(registry, self.registry)
            value = captured(request, registry)
            self.events.append(('wrapper-return', value))
            return value
        with patch.object(reference, 'check_composition', wrapper):
            observed = runtime.checker('composition', raw)
        value = runtime.owner.objects.resolve(observed['value'])
        self.assertEqual(value.to_dict(), self.link.to_dict())
        self.assertEqual([event[0] for event in self.events],
                         ['wrapper-enter', 'package-check-native', 'wrapper-return'])
        self.assertIs(value, self.events[-1][1])

    def test_replacement_checker_result_is_opaque_until_original_report_reads(self):
        runtime, raw = self.checker_runtime()
        events = self.events
        class Report:
            @property
            def passed(self):
                events.append(('passed', None))
                return True
            def to_dict(self):
                events.append(('document', None))
                return {'host': 'untrusted declaration'}
        report = Report()
        with patch.object(reference, 'check_composition', return_value=report) as replacement:
            observed = runtime.checker('composition', raw)
        self.assertEqual(self.events, [])
        self.assertIs(runtime.owner.objects.resolve(observed['value']), report)
        replacement.assert_called_once_with(self.request.construct.composition, self.registry)
        self.assertTrue(runtime.invoke('package-report-passed', observed['value']))
        self.assertEqual(runtime.invoke('package-report-document', observed['value']),
                         {'host': 'untrusted declaration'})
        self.assertEqual([event[0] for event in self.events], ['passed', 'document'])

    def test_current_checker_exception_preserves_actual_object(self):
        runtime, raw = self.checker_runtime()
        error = CoreProtocolError('raised by current checker wrapper')
        with patch.object(reference, 'check_composition', side_effect=error) as checker:
            with self.assertRaises(CoreProtocolError) as raised:
                runtime.checker('composition', raw)
        self.assertIs(raised.exception, error)
        checker.assert_called_once()
        self.assertEqual(self.events, [])

    def test_captured_checker_repeated_or_changed_arguments_run_fresh_on_current_owner(self):
        runtime, raw = self.checker_runtime()
        captured = reference.check_composition
        copied = PackageViews().reference_composition(self.request.construct.composition.to_dict(), ())
        results = []
        def call(operation, arguments):
            self.events.append((operation, arguments))
            if operation == 'package-check-native':
                self.assertEqual(arguments, {'check_id': 'current-check'})
            else:
                self.assertEqual(operation, 'package-check-evaluate')
                self.assertEqual(arguments, {'check_id': 'current-check', 'name': 'composition',
                    'arguments': {'request': copied.to_dict(), 'registry': self.registry.to_dict()}})
            return self.link.to_dict()
        runtime.call = call
        def wrapper(request, registry):
            results.extend((captured(request, registry), captured(request, registry), captured(copied, registry)))
            return results[-1]
        with patch.object(reference, 'check_composition', wrapper):
            observed = runtime.checker('composition', raw)
        self.assertEqual([event[0] for event in self.events],
                         ['package-check-native', 'package-check-evaluate', 'package-check-evaluate'])
        self.assertEqual(len({id(value) for value in results}), 3)
        self.assertIs(runtime.owner.objects.resolve(observed['value']), results[-1])

    def test_export_report_reads_diagnostics_before_testing_passed_truth(self):
        runtime, _ = self.checker_runtime()
        events = []
        class Truth:
            def __bool__(self):
                events.append('truth')
                return True
        class Diagnostic:
            @property
            def code(self):
                events.append('code')
                return 'original-diagnostic'
        class Report:
            @property
            def passed(self):
                events.append('passed')
                return Truth()
            @property
            def diagnostics(self):
                events.append('diagnostics')
                return (Diagnostic(),)
        value = runtime.owner.objects.retain(Report())
        self.assertEqual(runtime.invoke('package-report-export', value),
                         {'passed': True, 'diagnostics': ['original-diagnostic']})
        self.assertEqual(events, ['passed', 'diagnostics', 'code', 'truth'])

    def test_export_diagnostic_failure_precedes_report_truth(self):
        runtime, _ = self.checker_runtime()
        events = []
        error = CoreProtocolError('diagnostic accessor raised')
        class Truth:
            def __bool__(self):
                events.append('truth')
                return True
        class Report:
            @property
            def passed(self):
                events.append('passed')
                return Truth()
            @property
            def diagnostics(self):
                events.append('diagnostics')
                raise error
        value = runtime.owner.objects.retain(Report())
        with self.assertRaises(CoreProtocolError) as raised:
            runtime.invoke('package-report-export', value)
        self.assertIs(raised.exception, error)
        self.assertEqual(events, ['passed', 'diagnostics'])

    def test_malformed_native_view_is_private_boundary_error_not_host_exception(self):
        error = CoreProtocolError('trusted native view shape is invalid')
        def decode():
            raise error
        with self.assertRaises(PackageBoundaryError) as raised:
            route._trusted_decode(decode)
        self.assertIs(raised.exception.__cause__, error)
        private = PackageBoundaryError('already a fatal boundary violation')
        with self.assertRaises(PackageBoundaryError) as preserved:
            route._trusted_decode(lambda: (_ for _ in ()).throw(private))
        self.assertIs(preserved.exception, private)

    def test_export_invalid_line_width_precedes_owner_or_root_inspection(self):
        class Unreadable:
            def __getattribute__(self, name):
                raise AssertionError('Export inspected root before checking line width')
        value = Unreadable()
        for width in (True, False, 0, -1, 10001, 2.0, '80', None):
            with self.subTest(width=width), patch.object(route, '_runtime', side_effect=AssertionError('early owner')):
                with self.assertRaisesRegex(SerializationError, 'FASTA line width'):
                    route.export(self.selected, value, value, value, value, value, line_width=width)

    def test_prepare_invalid_alphabet_precedes_owner_or_directory_inspection(self):
        for alphabet in ('dna', 'protein', '', None, True, 1):
            with self.subTest(alphabet=alphabet), patch.object(route, '_runtime', side_effect=AssertionError('early owner')):
                with self.assertRaisesRegex(SerializationError, 'DNA or RNA'):
                    route.prepare(self.selected, alphabet, object())

    @staticmethod
    def rejection(hex_bytes=None, *, message='Packaged request must be UTF-8 JSON.'):
        raw = {'module': 'biocompiler.errors', 'type': 'SerializationError',
               'message': message, 'attributes': {}, 'attributes_tree': ['object', []]}
        if hex_bytes is not None:
            raw['cause_utf8_bytes_hex'] = hex_bytes
        return raw

    def call_rejected(self, raw):
        runtime = object.__new__(route._Runtime)
        def call(operation, arguments):
            raise CallbackRejected(SimpleNamespace(result=raw))
        runtime.owner = SimpleNamespace(session=SimpleNamespace(call=call))
        runtime.call('package-reconstruct', {})

    def test_utf8_rejection_retains_exact_decode_args_cause_context_and_suppression(self):
        data = b'{"invalid":"\xf0\x28\x8c\x28"}'
        try:
            data.decode('utf-8')
        except UnicodeDecodeError as original:
            expected_args = original.args
            expected_fields = (original.encoding, original.object, original.start, original.end, original.reason)
        with self.assertRaises(SerializationError) as raised:
            self.call_rejected(self.rejection(data.hex()))
        error = raised.exception
        self.assertEqual(error.args, ('Packaged request must be UTF-8 JSON.',))
        self.assertIs(type(error.__cause__), UnicodeDecodeError)
        cause = error.__cause__
        self.assertEqual(cause.args, expected_args)
        self.assertEqual((cause.encoding, cause.object, cause.start, cause.end, cause.reason), expected_fields)
        self.assertIs(error.__context__, cause)
        self.assertTrue(error.__suppress_context__)
        self.assertIsNone(cause.__cause__)
        self.assertIsNone(cause.__context__)
        self.assertFalse(cause.__suppress_context__)

    def test_plain_native_rejection_does_not_expose_transport_exception_context(self):
        with self.assertRaises(SerializationError) as raised:
            self.call_rejected(self.rejection(message='Original logical rejection'))
        error = raised.exception
        self.assertEqual(error.args, ('Original logical rejection',))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        self.assertFalse(error.__suppress_context__)

    def test_native_utf8_cause_rejects_malformed_or_nonfailing_bytes(self):
        for value in ('', 'f', 'FF', 'zz', '616263', True, [], {}):
            with self.subTest(value=value), self.assertRaises(PackageBoundaryError):
                route._native_exception(self.rejection(value))
        with self.assertRaisesRegex(PackageBoundaryError, 'Unexpected native UTF-8'):
            route._native_exception(self.rejection('ff', message='Another unrelated failure'))
        null_cause = self.rejection()
        null_cause['cause_utf8_bytes_hex'] = None
        with self.assertRaisesRegex(PackageBoundaryError, 'UTF-8 cause'):
            route._native_exception(null_cause)


if __name__ == '__main__':
    unittest.main()
