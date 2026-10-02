"""Public architecture engine selection precedes every reference algorithm."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch, sentinel

import biocompiler as bc
from biocompiler.compiler import payload_architecture as producer
from biocompiler.verification import payload_architecture as checker
from biocompiler.core_client import CoreClient
from biocompiler.errors import CompilationUnavailableError, SerializationError


class ArchitectureCoreRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tests/conformance/case-b/base/request.json'
        cls.request = bc.PayloadArchitectureRequest.from_dict(json.loads(path.read_bytes()))
        cls.core = CoreClient(Path('/explicit/biocompiler-core'))

    def test_named_and_general_compile_choose_the_explicit_core(self):
        with patch('biocompiler.architecture_backend.compile_architecture',
                   return_value=(sentinel.build, sentinel.assessment, sentinel.native)) as native, \
             patch.object(producer, 'derive_source_execution', side_effect=AssertionError('Python source execution')):
            for compile_ in (bc.compile, bc.compile_payload_architecture, producer.compile_payload_architecture):
                with self.subTest(entry=compile_):
                    self.assertIs(compile_(self.request, core=self.core), sentinel.build)
                    native.assert_called_with(self.request, core=self.core)
            self.assertEqual(native.call_count, 3)

    def test_named_export_uses_one_fresh_native_operation(self):
        with patch('biocompiler.architecture_backend.export_architecture',
                   return_value=(sentinel.export, sentinel.build, sentinel.assessment, sentinel.native)) as native, \
             patch.object(checker, 'check_payload_architecture', side_effect=AssertionError('Python checking')):
            for export in (bc.export_payload_architecture, producer.export_payload_architecture):
                self.assertIs(export(sentinel.build, expected_request=self.request, core=self.core), sentinel.export)
            self.assertEqual(native.call_count, 2)
            native.assert_called_with(sentinel.build, expected_request=self.request, core=self.core)

    def test_checker_aliases_preserve_the_selected_engine(self):
        with patch('biocompiler.architecture_backend.check_architecture',
                   return_value=(sentinel.build, sentinel.assessment, sentinel.native)) as native, \
             patch.object(checker, '_source_manifest_checks', side_effect=AssertionError('Python checking')):
            for check in (bc.check_payload_architecture, checker.check_payload_architecture,
                          checker.check_payload_architecture_build):
                self.assertIs(check(sentinel.build, expected_request=self.request, core=self.core), sentinel.assessment)
            self.assertEqual(native.call_count, 3)
            native.assert_called_with(sentinel.build, expected_request=self.request, core=self.core)

    def test_replay_passes_full_receipt_to_native_without_python_rechecking(self):
        with patch('biocompiler.architecture_backend.replay_architecture',
                   return_value=(sentinel.build, sentinel.assessment, sentinel.native)) as native, \
             patch.object(checker, 'check_payload_architecture', side_effect=AssertionError('Python replay')):
            for replay in (bc.verify_payload_architecture, checker.verify_payload_architecture):
                self.assertIs(replay(sentinel.receipt, sentinel.build, expected_request=self.request,
                                     core=self.core), sentinel.assessment)
            native.assert_called_with(sentinel.receipt, sentinel.build, expected_request=self.request, core=self.core)
            self.assertEqual(native.call_count, 2)

    def test_selected_core_failure_is_never_a_reference_fallback(self):
        failure = SerializationError('Selected core rejected the operation')
        for name, action in (
            ('compile_architecture', lambda: bc.compile(self.request, core=self.core)),
            ('export_architecture', lambda: bc.export_payload_architecture(sentinel.build, expected_request=self.request, core=self.core)),
            ('check_architecture', lambda: bc.check_payload_architecture(sentinel.build, expected_request=self.request, core=self.core)),
            ('replay_architecture', lambda: bc.verify_payload_architecture(sentinel.receipt, sentinel.build, expected_request=self.request, core=self.core)),
        ):
            with self.subTest(operation=name), patch('biocompiler.architecture_backend.' + name, side_effect=failure) as native:
                with self.assertRaises(SerializationError) as caught:
                    action()
                self.assertIs(caught.exception, failure)
                native.assert_called_once()

    def test_general_compile_rejects_core_for_every_other_profile(self):
        with patch('biocompiler.compiler.executable_payload.compile_payload', side_effect=AssertionError('Python fallback')), \
             patch('biocompiler.compiler.circuit_construction.build_circuit_construction', side_effect=AssertionError('Python fallback')):
            for value in (object(), self.request.source, self.request.circuit):
                with self.subTest(profile=type(value).__name__), self.assertRaisesRegex(CompilationUnavailableError, 'selected OCaml core'):
                    bc.compile(value, core=self.core)

    def test_default_general_route_preserves_the_reference_call_contract(self):
        with patch.object(producer, 'compile_payload_architecture', return_value=sentinel.build) as reference:
            self.assertIs(bc.compile(self.request), sentinel.build)
            reference.assert_called_once_with(self.request)

    def test_scoped_native_error_is_a_public_serialization_error(self):
        self.assertTrue(issubclass(bc.ArchitectureCoreError, SerializationError))
        self.assertIn('ArchitectureCoreError', bc.__all__)
