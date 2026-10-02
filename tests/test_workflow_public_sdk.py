"""Optional public routes preserve old behavior and delegate native authority.

Native WorkflowResult objects here are complete transport fixtures. These tests
execute Python only; installed native workflow campaigns remain required in CI.
"""
from contextlib import ExitStack
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import workflow_backend as backend
from biocompiler.compiler import verification_workflow as workflow
from biocompiler.core_client import (
    CoreCancelled, CoreClient, CoreProtocolError, CoreRejected, CoreResponse,
    CoreUnavailable, Diagnostic,
)
from biocompiler.errors import SerializationError
from test_core_workflow import canonical, fixture_records
from test_workflow_backend import native_fixture


class WorkflowPublicSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = fixture_records()
        cls.legacy = [workflow.SyntheticVerificationRecord.from_dict(raw)
                      for raw in cls.records]

    def setUp(self):
        # The client is never executed. WorkflowClient exchanges below are
        # explicit fixture boundaries, not fake claims of native execution.
        self.core = CoreClient(Path(sys.executable), role="verify")

    def forbid_python_semantics(self):
        stack = ExitStack()
        for name in ("_checker", "check_synthetic_candidate", "check_realization",
                     "explore_boolean_histories", "reduce_counterexample"):
            stack.enter_context(patch.object(workflow, name,
                side_effect=AssertionError("Python semantic fallback ran")))
        for cls in (workflow.SyntheticVerificationRequest, workflow.SyntheticVerificationRecord):
            for name in ("from_dict", "__post_init__"):
                stack.enter_context(patch.object(cls, name,
                    side_effect=AssertionError("Legacy semantic hydration ran")))
        return stack

    def test_core_selection_is_optional_and_keyword_only(self):
        for operation in (workflow.run_synthetic_verification,
                          workflow.replay_synthetic_verification):
            parameter = inspect.signature(operation).parameters["core"]
            self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIsNone(parameter.default)
        with self.assertRaises(TypeError):
            workflow.run_synthetic_verification(self.legacy[0].request, self.core)
        with self.assertRaises(TypeError):
            workflow.replay_synthetic_verification(self.legacy[0], core=self.core)

    def test_all_six_default_operations_keep_complete_original_behavior(self):
        self.assertEqual({(raw["request"]["operation"], raw["request"]["mode"])
                          for raw in self.records},
                         {(operation, mode) for operation in ("check", "explore", "reduce")
                          for mode in ("candidate", "model")})
        with patch.object(backend, "run_record", side_effect=AssertionError("Unexpected native route")), \
             patch.object(backend, "replay_record", side_effect=AssertionError("Unexpected native route")):
            for raw, historical in zip(self.records, self.legacy):
                for options in ({}, {"core": None}):
                    with self.subTest(operation=historical.request.operation,
                                      mode=historical.request.mode, options=options):
                        result = workflow.run_synthetic_verification(historical.request, **options)
                        self.assertIs(type(result), workflow.SyntheticVerificationRecord)
                        self.assertEqual(result.to_dict(), raw)
                        replay = workflow.replay_synthetic_verification(
                            historical, expected_request=historical.request, **options)
                        self.assertIs(type(replay), workflow.SyntheticVerificationRecord)
                        self.assertEqual(replay.to_dict(), raw)
                        self.assertEqual(replay.fingerprint, historical.fingerprint)

    def test_selected_run_accepts_complete_typed_bytes_mapping_and_native_request(self):
        for raw, historical in zip(self.records, self.legacy):
            native = native_fixture(raw)
            view = backend.view_result(native)
            requests = (historical.request, canonical(raw["request"]), raw["request"], view.request)
            for request in requests:
                with self.subTest(operation=view.request.operation, mode=view.request.mode,
                                  input_type=type(request).__name__):
                    def exchange(client, authority, **options):
                        self.assertIs(client.core, self.core)
                        self.assertFalse(backend.serializing_legacy_input())
                        self.assertEqual(json.loads(authority), raw["request"])
                        self.assertEqual(options, {"limits": None, "command": None, "cancelled": None})
                        return native
                    with self.forbid_python_semantics(), \
                         patch.object(backend.WorkflowClient, "run_public", exchange):
                        result = workflow.run_synthetic_verification(request, core=self.core)
                    self.assertIs(type(result), backend.NativeWorkflowRecord)
                    self.assertNotIsInstance(result, workflow.SyntheticVerificationRecord)
                    self.assertEqual(result.to_dict(), raw)
                    self.assertEqual(result.fingerprint, historical.fingerprint)
                    self.assertIs(result.native, native)

    def test_selected_replay_accepts_complete_typed_bytes_mapping_and_native_records(self):
        for raw, historical in zip(self.records, self.legacy):
            native = native_fixture(raw, replay=True)
            view = backend.view_result(native)
            inputs = ((historical, historical.request), (canonical(raw), canonical(raw["request"])),
                      (raw, raw["request"]), (view, view.request))
            for record, authority in inputs:
                with self.subTest(operation=view.request.operation, mode=view.request.mode,
                                  input_type=type(record).__name__):
                    def exchange(client, source, retained, **options):
                        self.assertIs(client.core, self.core)
                        self.assertFalse(backend.serializing_legacy_input())
                        self.assertEqual(json.loads(source), raw["request"])
                        self.assertEqual(json.loads(retained), raw)
                        self.assertEqual(options, {"limits": None, "command": None, "cancelled": None})
                        return native
                    with self.forbid_python_semantics(), \
                         patch.object(backend.WorkflowClient, "replay_public", exchange):
                        result = workflow.replay_synthetic_verification(
                            record, expected_request=authority, core=self.core)
                    self.assertIs(type(result), backend.NativeWorkflowRecord)
                    self.assertNotIsInstance(result, workflow.SyntheticVerificationRecord)
                    self.assertEqual(result.to_dict(), raw)
                    self.assertEqual(result.fingerprint, historical.fingerprint)
                    self.assertIs(result.native, native)

    def test_selected_dispatch_passes_inputs_unchanged_before_legacy_validation(self):
        request, record, result = object(), object(), object()
        # A false-valued selector is still selected; only None chooses Python.
        core = False
        with self.forbid_python_semantics(), patch.object(backend, "run_record", return_value=result) as run:
            self.assertIs(workflow.run_synthetic_verification(request, core=core), result)
            run.assert_called_once_with(request, core=core)
        with self.forbid_python_semantics(), patch.object(backend, "replay_record", return_value=result) as replay:
            self.assertIs(workflow.replay_synthetic_verification(
                record, expected_request=request, core=core), result)
            replay.assert_called_once_with(record, expected_request=request, core=core)

    def test_default_input_contracts_remain_nominal(self):
        native = backend.view_result(native_fixture(self.records[0]))
        with patch.object(backend, "run_record", side_effect=AssertionError("Unexpected native route")), \
             patch.object(backend, "replay_record", side_effect=AssertionError("Unexpected native route")):
            for request in (self.records[0]["request"], canonical(self.records[0]["request"]), native.request):
                with self.assertRaisesRegex(SerializationError, "Expected complete verification request"):
                    workflow.run_synthetic_verification(request)
            with self.assertRaisesRegex(SerializationError, "Expected historical verification record"):
                workflow.replay_synthetic_verification(native, expected_request=self.legacy[0].request)
            with self.assertRaisesRegex(SerializationError, "independently trusted complete operation authority"):
                workflow.replay_synthetic_verification(self.legacy[0], expected_request=native.request)

    def test_selected_transport_failures_keep_cause_without_fallback(self):
        for error in (CoreCancelled("cancelled"), CoreUnavailable("absent"), CoreProtocolError("incompatible")):
            with self.subTest(error=type(error).__name__), self.forbid_python_semantics():
                with patch.object(backend.WorkflowClient, "run_public", side_effect=error), \
                     self.assertRaises(backend.WorkflowCoreError) as caught:
                    workflow.run_synthetic_verification(self.records[0]["request"], core=self.core)
                self.assertIs(caught.exception.core_error, error)
                self.assertIs(caught.exception.__cause__, error)
                with patch.object(backend.WorkflowClient, "replay_public", side_effect=error), \
                     self.assertRaises(backend.WorkflowCoreError) as caught:
                    workflow.replay_synthetic_verification(self.records[0],
                        expected_request=self.records[0]["request"], core=self.core)
                self.assertIs(caught.exception.core_error, error)
                self.assertIs(caught.exception.__cause__, error)

    def test_selected_rejection_preserves_full_diagnostics(self):
        diagnostic = Diagnostic("workflow_replay", "Historical result differs", "retained_record.result")
        error = CoreRejected(CoreResponse("fixture", "replay-verification-workflow", "error", None,
                                         (diagnostic,), "verify", "fixture"))
        with self.forbid_python_semantics(), \
             patch.object(backend.WorkflowClient, "replay_public", side_effect=error), \
             self.assertRaises(backend.WorkflowCoreError) as caught:
            workflow.replay_synthetic_verification(self.records[0],
                expected_request=self.records[0]["request"], core=self.core)
        self.assertIs(caught.exception.core_error, error)
        self.assertEqual(caught.exception.diagnostics, (diagnostic,))

    def test_selected_wrong_input_kind_rejected_without_transport_or_fallback(self):
        with self.forbid_python_semantics(), \
             patch.object(backend.WorkflowClient, "run_public", side_effect=AssertionError("Unexpected I/O")), \
             patch.object(backend.WorkflowClient, "replay_public", side_effect=AssertionError("Unexpected I/O")):
            with self.assertRaises(backend.WorkflowCoreError):
                workflow.run_synthetic_verification(self.legacy[0], core=self.core)
            with self.assertRaises(backend.WorkflowCoreError):
                workflow.replay_synthetic_verification(self.legacy[0].request,
                    expected_request=self.records[0]["request"], core=self.core)


if __name__ == "__main__":
    unittest.main()
