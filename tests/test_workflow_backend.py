"""Complete native views preserve historical data without Python workflow logic.

WorkflowResult values below are transport fixtures, not native execution claims.
All six complete operation/mode artifacts come from the independent Python oracle
and retain their pinned identities in test_core_workflow.fixture_records.
"""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import workflow_backend as backend
from biocompiler.compiler.verification_workflow import (
    SyntheticVerificationRecord, SyntheticVerificationRequest,
)
from biocompiler.core_client import (
    CoreCancelled, CoreClient, CoreProtocolError, CoreRejected, CoreResponse,
    CoreUnavailable, Diagnostic,
)
from biocompiler.core_workflow import WorkflowResult
from biocompiler.verification.evidence import CheckResult
from biocompiler.verification.exploration import (
    BooleanContactConfig, BooleanInputConfig, BooleanInputExplorationReport,
    ExplorationReport, FailureSignature, ReductionResult,
)
from test_core_workflow import canonical, fixture_records, sha


def native_fixture(record, *, authority=None, replay=False, presentation=None):
    """Fixture-only presentation oracle, outside any selected-core production code."""
    action = record["request"]["operation"]
    result = record["result"]
    if presentation is None:
        passed = (result["outcome"] == "pass" if action == "check" else
                  result["all_passed"] if action == "explore" else result["one_minimal"])
        presentation = {
            "profile": "biocompiler.core.verification_workflow.presentation.v1",
            "command_exit_code": 0 if replay or passed else 1,
            "original_frames": len(result["original_history"]) if action == "reduce" else None,
            "reduced_frames": len(result["history"]) if action == "reduce" else None,
        }
    receipt = {"presentation": presentation, "command": None}
    raw = canonical(record)
    return WorkflowResult(
        request_id="workflow-view-fixture", operation=("replay-verification-workflow" if replay
                                                       else "run-verification-workflow"),
        executable="verify", workflow_operation=action, mode=record["request"]["mode"],
        authority_fingerprint=sha(canonical(record["request"] if authority is None else authority)),
        request_fingerprint=sha(canonical(record["request"])),
        retained_record_fingerprint=sha(raw) if replay else None, record_fingerprint=sha(raw),
        record_json=raw, _receipt_json=canonical(receipt), _envelope_json=b"{}")


def leaves(view):
    if view.request.operation == "check":
        return (view.result,)
    if view.request.operation == "explore":
        return view.result.results
    return (view.result.original_result, view.result.result)


class WorkflowBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = fixture_records()
        # Legacy semantic imports happen while preparing untrusted authored input,
        # before the test guard which prohibits native-output reconstruction.
        cls.legacy = [SyntheticVerificationRecord.from_dict(raw) for raw in cls.records]

    def setUp(self):
        self.core = CoreClient(Path(sys.executable), role="verify")

    def forbid_semantics(self):
        stack = ExitStack()
        for cls in (SyntheticVerificationRequest, SyntheticVerificationRecord, BooleanContactConfig,
                    BooleanInputConfig, ExplorationReport, BooleanInputExplorationReport, ReductionResult):
            for name in ("from_dict", "__post_init__"):
                stack.enter_context(patch.object(cls, name, side_effect=AssertionError("Legacy semantic hydration")))
        for name in ExplorationReport._derived:
            stack.enter_context(patch.object(ExplorationReport, name,
                property(lambda _self: self.fail("Python report property ran"))))
        for name in ("state_count", "possible_histories"):
            stack.enter_context(patch.object(BooleanContactConfig, name,
                property(lambda _self: self.fail("Python bounds property ran"))))
        for target in ("biocompiler.verification.exploration.explore_boolean_histories",
                       "biocompiler.verification.exploration.reduce_counterexample",
                       "biocompiler.compiler.verification_workflow.check_realization",
                       "biocompiler.compiler.verification_workflow.check_synthetic_candidate"):
            stack.enter_context(patch(target, side_effect=AssertionError("Python semantic execution")))
        return stack

    def test_all_six_complete_records_and_exact_formats(self):
        self.assertEqual({(r["request"]["operation"], r["request"]["mode"]) for r in self.records},
                         {(a, m) for a in ("check", "explore", "reduce") for m in ("candidate", "model")})
        with self.forbid_semantics():
            for raw in self.records:
                with self.subTest(operation=raw["request"]["operation"], mode=raw["request"]["mode"]):
                    native = native_fixture(raw)
                    view = backend.view_result(native)
                    self.assertIs(type(view), backend.NativeWorkflowRecord)
                    self.assertNotIsInstance(view, SyntheticVerificationRecord)
                    self.assertEqual(view.to_dict(), raw)
                    self.assertEqual(view.canonical_json, canonical(raw))
                    self.assertEqual(view.fingerprint, native.record_fingerprint)
                    self.assertEqual(view.request.fingerprint, native.request_fingerprint)
                    for indent in (None, 0, 2, 4, -1):
                        self.assertEqual(view.to_json(indent=indent), json.dumps(raw,
                            sort_keys=True, ensure_ascii=False, allow_nan=False, indent=indent))
                    for leaf in leaves(view):
                        self.assertIs(type(leaf), CheckResult)
                        encoded = json.dumps(leaf.to_dict(), sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=True, allow_nan=False).encode()
                        self.assertEqual(leaf.fingerprint, sha(encoded))

    def test_native_derived_fields_are_projected_without_recomputation(self):
        raw = deepcopy(self.records[2])
        # A deliberately inconsistent transport fixture establishes that the view
        # copies native claims and does not confer semantic validity or recompute
        # them. The actual WorkflowClient/native service validates real responses.
        raw["result"].update(state_count=739, possible_histories=817, evaluated_histories=615,
                             complete=True, all_passed=True, outcome_counts={"native": 42})
        raw["result"]["shared_dependencies"]["settings"]["native_projection"] = "retained"
        with self.forbid_semantics():
            view = backend.view_result(native_fixture(raw))
            for name in ExplorationReport._derived:
                self.assertEqual(view.to_dict()["result"][name], raw["result"][name])
            self.assertEqual(view.request.bounds.state_count, 739)
            self.assertEqual(view.result.config.possible_histories, 817)
            self.assertNotIn("state_count", view.request.bounds.to_dict())
            self.assertEqual(view.result.outcome_counts["native"], 42)

    def test_deep_immutability_and_defensive_copies(self):
        view = backend.view_result(native_fixture(self.records[2]))
        with self.assertRaises((FrozenInstanceError, TypeError, AttributeError)):
            view.result = None
        with self.assertRaises(TypeError):
            view.result.outcome_counts["pass"] = 99
        with self.assertRaises(TypeError):
            view.request.bounds.fixed_suffix[0].contacts["x"]["n000003"] = None
        with self.assertRaises((FrozenInstanceError, TypeError)):
            view.result.results[0].outcome = None
        copied = view.to_dict()
        copied["result"]["results"].clear()
        copied["request"]["bounds"]["contact_ids"].append("changed")
        self.assertEqual(view.to_dict(), self.records[2])
        self.assertEqual(hash(view), hash(backend.view_result(native_fixture(self.records[2]))))
        self.assertEqual(view, backend.view_result(native_fixture(self.records[2])))
        self.assertNotEqual(view, self.legacy[2])
        self.assertEqual(view.native.record, self.records[2])
        with self.assertRaises(AttributeError):
            _ = view.request.realization.fingerprint
        self.assertEqual(view.request.realization.canonical_fingerprint,
                         sha(canonical(self.records[2]["request"]["realization"])))

    def test_unicode_ascii_leaves_and_utf8_record_identities(self):
        raw = deepcopy(self.records[0])
        raw["result"]["diagnostics"][0]["message"] = "RNA α / 细胞 🧬"
        view = backend.view_result(native_fixture(raw))
        leaf = json.dumps(raw["result"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        self.assertIn(b"\\u", leaf)
        self.assertNotEqual(sha(leaf), sha(canonical(raw["result"])))
        self.assertEqual(view.result.fingerprint, sha(leaf))
        self.assertEqual(view.fingerprint, sha(canonical(raw)))
        self.assertIn("细胞", view.to_json())
        self.assertEqual(view.to_dict(), raw)

    def test_failure_signature_typed_leaf_and_matches(self):
        for raw in (self.records[3], self.records[5]):
            view = backend.view_result(native_fixture(raw))
            self.assertIs(type(view.request.signature), FailureSignature)
            self.assertIs(type(view.result.signature), FailureSignature)
            self.assertTrue(view.result.signature.matches(view.result.result))
            self.assertEqual(view.result.signature.fingerprint, sha(canonical(raw["result"]["signature"])))

    def test_native_presentation_is_projected_without_exit_policy(self):
        raw = self.records[1]
        native = native_fixture(raw)
        receipt = native.receipt
        receipt["presentation"]["command_exit_code"] = 1
        view = backend.view_result(replace(native, _receipt_json=canonical(receipt)))
        self.assertTrue(view.result.passed)
        self.assertEqual(view.command_exit_code, 1)
        with self.assertRaises(TypeError):
            view.presentation["command_exit_code"] = 0
        for change in ({}, {"presentation": {}}, {"presentation": dict(receipt["presentation"], extra=1)},
                       {"presentation": dict(receipt["presentation"], command_exit_code=True)}):
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                backend.view_result(replace(native, _receipt_json=canonical(change)))

    def test_source_map_order_and_fixed_field_order_preserve_identity(self):
        raw = self.records[2]
        authority = deepcopy(raw["request"])
        for frame in authority["bounds"]["fixed_suffix"]:
            frame["contacts"]["x"] = dict(reversed(list(frame["contacts"]["x"].items())))
        source = json.dumps(authority, ensure_ascii=False).encode()
        view = backend.view_result(native_fixture(raw, authority=authority), authority=source)
        for bounds in (view.request.bounds, view.result.config):
            frame = bounds.fixed_suffix[0]
            self.assertEqual(list(frame.to_dict()), ["time", "signals", "contacts"])
            self.assertEqual(list(frame.contacts["x"]), ["n000004", "n000003"])
            self.assertEqual(list(frame.contacts["x"]["n000003"].to_dict()), ["value", "present", "high", "low"])
            self.assertEqual(list(bounds.observations[0].to_dict()), ["schema_version", "signal_id", "field"])
        self.assertEqual(list(view.result.outcome_counts), ["pass", "fail", "unknown", "unsupported"])
        self.assertEqual(view.canonical_json, canonical(raw))
        self.assertEqual(view.authority_json, source)
        authority["max_evaluations"] = 18
        with self.assertRaises(CoreProtocolError):
            backend.view_result(native_fixture(raw), authority=canonical(authority))

    def test_observed_cli_summary_format_matches_legacy_full_records(self):
        from biocompiler.cli import _verification_summary
        for raw, historical in zip(self.records, self.legacy):
            expected = json.dumps(_verification_summary(historical), indent=2)
            view = backend.view_result(native_fixture(raw))
            self.assertEqual(json.dumps(_verification_summary(view), indent=2), expected)

    def test_full_legacy_input_is_serialized_only_in_explicit_input_phase(self):
        original = SyntheticVerificationRecord.to_dict
        seen = []

        def serializer(value):
            self.assertTrue(backend.serializing_legacy_input())
            seen.append(value)
            return original(value)

        for raw, historical in zip(self.records, self.legacy):
            native = native_fixture(raw, replay=True)
            def exchange(_client, authority, retained, **options):
                self.assertFalse(backend.serializing_legacy_input())
                self.assertEqual(json.loads(authority), raw["request"])
                self.assertEqual(json.loads(retained), raw)
                self.assertEqual(options["command"], "synthetic-replay")
                return native
            with patch.object(SyntheticVerificationRecord, "to_dict", serializer), \
                 patch.object(backend.WorkflowClient, "replay_public", exchange):
                result = backend.replay_record(historical, expected_request=historical.request,
                                               core=self.core, command="synthetic-replay")
            self.assertEqual(result.to_dict(), raw)
            self.assertFalse(backend.serializing_legacy_input())
        self.assertEqual(len(seen), 6)

    def test_native_run_routes_options_and_never_constructs_legacy_records(self):
        cancelled = lambda: False
        limits = {"max_work": 1000}
        for raw in self.records:
            native = native_fixture(raw)
            def exchange(_client, authority, **options):
                self.assertFalse(backend.serializing_legacy_input())
                self.assertEqual(json.loads(authority), raw["request"])
                self.assertEqual(options, {"limits": limits, "command": None, "cancelled": cancelled})
                return native
            with self.forbid_semantics(), patch.object(backend.WorkflowClient, "run_public", exchange):
                view, response = backend.run_document(request=raw["request"], core=self.core,
                                                      limits=limits, cancelled=cancelled)
            self.assertIs(response, native)
            self.assertEqual(view.to_dict(), raw)

    def test_legacy_serializer_exception_resets_phase(self):
        with patch.object(SyntheticVerificationRecord, "to_dict", side_effect=ValueError("fixture serializer")):
            with self.assertRaisesRegex(ValueError, "fixture serializer"):
                backend.replay_record(self.legacy[0], expected_request=self.legacy[0].request, core=self.core)
        self.assertFalse(backend.serializing_legacy_input())

    def test_core_failures_do_not_fall_back_and_keep_original_error(self):
        for error in (CoreCancelled("cancelled"), CoreUnavailable("absent"), CoreProtocolError("incompatible")):
            with self.forbid_semantics(), patch.object(backend.WorkflowClient, "run_public", side_effect=error):
                with self.assertRaises(backend.WorkflowCoreError) as caught:
                    backend.run_record(self.records[0]["request"], core=self.core)
            self.assertIs(caught.exception.core_error, error)
            self.assertEqual(caught.exception.diagnostics, ())

    def test_structured_replay_rejection_is_retained_without_fallback(self):
        diagnostic = Diagnostic("workflow_replay", "Historical result differs", "retained_record.result")
        error = CoreRejected(CoreResponse("fixture", "replay-verification-workflow", "error", None,
                                         (diagnostic,), "verify", "fixture"))
        with self.forbid_semantics(), patch.object(backend.WorkflowClient, "replay_public", side_effect=error):
            with self.assertRaises(backend.WorkflowCoreError) as caught:
                backend.replay_document(request=self.records[0]["request"], record=self.records[0], core=self.core)
        self.assertIs(caught.exception.core_error, error)
        self.assertEqual(caught.exception.diagnostics, (diagnostic,))

    def test_native_view_can_be_resubmitted_as_untrusted_input(self):
        native = native_fixture(self.records[0], replay=True)
        view = backend.view_result(native)
        def exchange(_client, authority, retained, **_options):
            self.assertEqual(authority, view.request.canonical_json)
            self.assertEqual(retained, view.canonical_json)
            return native
        with self.forbid_semantics(), patch.object(backend.WorkflowClient, "replay_public", exchange):
            fresh = backend.replay_record(view, expected_request=view.request, core=self.core)
        self.assertEqual(fresh.to_dict(), self.records[0])

    def test_ascii_leaf_limit_is_checked_before_legacy_hydration(self):
        raw = self.records[0]["result"]
        size = len(json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
        with patch.dict(backend.LIMITS, max_response_bytes=size):
            self.assertEqual(backend._leaf(raw).to_dict(), raw)
        with patch.dict(backend.LIMITS, max_response_bytes=size - 1), \
             patch.object(CheckResult, "from_dict", side_effect=AssertionError("Hydrated before byte bound")):
            with self.assertRaisesRegex(CoreProtocolError, "ASCII byte limit"):
                backend._leaf(raw)

    def test_lossy_leaf_and_identity_mutations_are_rejected(self):
        native = native_fixture(self.records[0])
        changed = CheckResult.from_dict(self.records[1]["result"])
        with patch.object(CheckResult, "from_dict", return_value=changed), self.assertRaises(CoreProtocolError):
            backend.view_result(native)
        for changes in ({"record_fingerprint": "0" * 64}, {"request_fingerprint": "0" * 64},
                        {"mode": "candidate"}, {"record_json": native.record_json + b"\n"}):
            with self.subTest(changes=changes), self.assertRaises(CoreProtocolError):
                backend.view_result(replace(native, **changes))

    def test_wrong_nominal_input_rejected_before_transport(self):
        view = backend.view_result(native_fixture(self.records[0]))
        with patch.object(backend.WorkflowClient, "run_public", side_effect=AssertionError("Unexpected I/O")):
            for request in (view, object(), self.legacy[0]):
                with self.assertRaises(backend.WorkflowCoreError):
                    backend.run_record(request, core=self.core)

    def test_integer_float_negative_zero_and_format_limit(self):
        raw = deepcopy(self.records[0])
        raw["request"]["history"][0]["time"] = -0.0
        view = backend.view_result(native_fixture(raw))
        self.assertEqual(view.request.history[0].time, -0.0)
        self.assertIn(b'"time":-0.0', view.canonical_json)
        self.assertEqual(view.to_dict(), raw)
        with self.assertRaises(CoreProtocolError):
            view.to_json(indent=True)
        with patch.object(backend, "MAX_ARTIFACT_BYTES", 10):
            with self.assertRaises(CoreProtocolError):
                view.to_json()


if __name__ == "__main__":
    unittest.main()
