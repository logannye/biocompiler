"""Explicit native direct SDK routing and audited output hydration only."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import realization_backend as backend
from biocompiler.core_client import CoreCancelled, CoreClient, CoreProtocolError, CoreRejected, CoreTimeout, CoreUnavailable
from biocompiler.core_realization import OPERATIONS
from biocompiler.verification.evidence import CheckResult, DependencySnapshot
from biocompiler.verification.components import CompositionResult
from biocompiler.verification.realization import check_realization, realization_dependencies
from biocompiler.synthesis.synthetic import check_synthetic_candidate
from biocompiler.compiler.components import check_component_behavior, check_component_assembly
import test_core_realization as transport_tests
from test_core_realization import fixture, family_for, payload_for


@contextmanager
def no_python_acceptance():
    previous = sys.getprofile()
    allowed_routes = {
        ("biocompiler.verification.realization", "check_realization"),
        ("biocompiler.verification.realization", "realization_dependencies"),
        ("biocompiler.synthesis.synthetic", "check_synthetic_candidate"),
        ("biocompiler.compiler.components", "check_component_behavior"),
        ("biocompiler.compiler.components", "check_component_assembly"),
    }
    observed = []
    forbidden = {
        "biocompiler.compiler.behavior": {"lower_to_behavior", "verify_lowering"},
        "biocompiler.semantics.evaluator": {"evaluate"},
        "biocompiler.models.synthetic": {"run_model"},
        "biocompiler.models.components": {"reconstruct_component_mechanism"},
        "biocompiler.synthesis.synthetic": {"generate_synthetic", "_generate_synthetic"},
        "biocompiler.synthesis.components": {"adapt_synthetic_components", "_output_domains"},
        "biocompiler.synthesis.policy": {"policy_for_request"},
        "biocompiler.registry.synthetic": {"catalog_for_profile"},
        "biocompiler.verification.components": {"check_composition", "composition_dependencies"},
        "biocompiler.verification.admission": {"admission_for_target"},
        "biocompiler.verification.realization": {"_horizon", "_runtime_observations"},
    }
    def guard(frame, event, _argument):
        if event != "call": return
        module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
        if (module, name) in allowed_routes:
            observed.append((module, name))
            if len(observed) > 1:
                raise AssertionError("Nested Python acceptance on selected native route")
        if name in forbidden.get(module, set()):
            raise AssertionError("Python acceptance on selected native route: " + module + "." + name)
        if module == "biocompiler.compiler.request" and name in {"from_dict", "from_json", "__post_init__"}:
            raise AssertionError("Native raw authority hydrated a Python request")
    sys.setprofile(guard)
    try: yield observed
    finally: sys.setprofile(previous)


class RealizationBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture()

    setUp = transport_tests.RealizationTransportTests.setUp
    exchange = transport_tests.RealizationTransportTests.exchange

    def direct(self, operation, *, core):
        direct = (self.request.behavior, self.request.contract, self.request.domain, self.request.target,
                  self.candidate.mechanism, self.candidate.observation_map, iter(self.history))
        if operation == "realization-dependencies": return realization_dependencies(*direct, until=7, core=core)
        if operation == "verify-realization": return check_realization(*direct, until=7, core=core)
        if operation == "verify-synthetic-candidate": return check_synthetic_candidate(self.request, self.candidate, iter(self.history), until=7, core=core)
        if operation == "verify-component-behavior": return check_component_behavior(self.request, self.assembly, iter(self.history), until=7, core=core)
        return check_component_assembly(self.request, self.candidate, self.assembly, iter(self.history), until=7, core=core)

    def test_all_nine_raw_routes_hydrate_only_complete_reports_without_request_import(self):
        for operation in OPERATIONS:
            payload = payload_for(operation, self.docs, self.reports)
            del payload["profile"]
            with self.subTest(operation=operation), self.exchange(), no_python_acceptance() as routed:
                result, native = backend.check_document(operation=operation, core=self.core, **payload)
            expected = self.reports[operation if operation == "realization-dependencies" else family_for(operation)]
            self.assertEqual(result.to_dict(), expected.to_dict())
            self.assertEqual(result.fingerprint, expected.fingerprint)
            self.assertEqual(native.report_fingerprint, result.fingerprint)
            self.assertEqual(routed, [])
            self.assertIsInstance(result, DependencySnapshot if operation == "realization-dependencies" else
                                  CompositionResult if operation.endswith("component-assembly") else CheckResult)

    def test_five_public_sdk_routes_never_call_nested_python_semantics(self):
        for operation in OPERATIONS:
            if operation.startswith("replay-"): continue
            self.calls.clear()
            with self.subTest(operation=operation), self.exchange(), no_python_acceptance() as routed:
                result = self.direct(operation, core=self.core)
            expected = self.reports[operation if operation == "realization-dependencies" else family_for(operation)]
            self.assertEqual(result.to_dict(), expected.to_dict())
            self.assertEqual(len(routed), 1)
            self.assertEqual([call["operation"] for call in self.calls], ["capabilities", operation])
            self.assertEqual(self.calls[1]["payload"]["history"], self.docs["history"])

    def test_no_core_keeps_original_complete_python_results(self):
        for operation in OPERATIONS:
            if operation.startswith("replay-"): continue
            with self.subTest(operation=operation), patch("biocompiler.realization_backend.check_records", side_effect=AssertionError("unexpected native route")):
                result = self.direct(operation, core=None)
            expected = self.reports[operation if operation == "realization-dependencies" else family_for(operation)]
            self.assertEqual(result.to_dict(), expected.to_dict())
            self.assertEqual(result.fingerprint, expected.fingerprint)

    def test_explicit_native_failures_retain_diagnostics_without_fallback(self):
        for operation in OPERATIONS:
            if operation.startswith("replay-"): continue
            self.calls.clear()
            with self.exchange(rejection="error"), no_python_acceptance(), self.assertRaises(backend.RealizationCoreError) as caught:
                self.direct(operation, core=self.core)
            self.assertEqual(caught.exception.operation, operation)
            self.assertIsInstance(caught.exception.core_error, CoreRejected)
            self.assertEqual(caught.exception.diagnostics[0].code, "realization_work_limit")
            self.assertEqual(caught.exception.diagnostics[0].message, "Exhausted")
            self.assertEqual(len(self.calls), 2)
        for error in (CoreTimeout("timeout"), CoreCancelled("cancelled"), CoreUnavailable("missing")):
            with patch("biocompiler.core_client._exchange", side_effect=error), no_python_acceptance(), self.assertRaises(backend.RealizationCoreError) as caught:
                self.direct("verify-realization", core=self.core)
            self.assertIs(caught.exception.core_error, error)
            self.assertEqual(caught.exception.diagnostics, ())

    def test_hydration_rejects_complete_record_or_fingerprint_changes(self):
        original = CheckResult.from_dict
        def changed(document):
            record = original(document)
            return replace(record, coverage=(replace(record.coverage[0], activation_deadlines_checked=999),))
        with self.exchange(), patch.object(CheckResult, "from_dict", side_effect=changed), self.assertRaises(backend.RealizationCoreError) as caught:
            self.direct("verify-realization", core=self.core)
        self.assertIsInstance(caught.exception.core_error, CoreProtocolError)
        self.assertIn("complete native identity", str(caught.exception))

    def test_nominal_type_errors_and_history_exhaustion_happen_before_io(self):
        direct = (self.request.behavior, self.request.contract, self.request.domain, self.request.target,
                  self.candidate.mechanism, self.candidate.observation_map)
        def broken_history():
            yield self.history[0]
            raise LookupError("authoring iterator stopped")
        for core in (None, self.core):
            with patch("biocompiler.core_client._exchange", side_effect=AssertionError("I/O occurred")):
                with self.assertRaisesRegex(TypeError, "Expected BehaviorProgram, got object"):
                    check_realization(object(), *direct[1:], (), core=core)
                with self.assertRaisesRegex(TypeError, "History must contain InputFrame"):
                    realization_dependencies(*direct, (object(),), core=core)
                with self.assertRaisesRegex(TypeError, "Expected a SyntheticCandidate"):
                    check_synthetic_candidate(self.request, object(), (), core=core)
                with self.assertRaisesRegex(TypeError, "Expected a RealizationRequest and ComponentAssembly"):
                    check_component_behavior(object(), self.assembly, (), core=core)
                with self.assertRaisesRegex(TypeError, "Expected a ComponentAssembly"):
                    check_component_assembly(self.request, self.candidate, object(), (), core=core)
                with self.assertRaisesRegex(LookupError, "authoring iterator stopped"):
                    check_realization(*direct, broken_history(), core=core)

    def test_raw_replay_helper_and_dependency_helper_preserve_cancellation(self):
        callback = lambda: False
        payload = payload_for("replay-realization", self.docs, self.reports); del payload["profile"]
        with self.exchange():
            report, native = backend.replay_document(operation="replay-realization", core=self.core, cancelled=callback, **payload)
        self.assertEqual(report.fingerprint, native.report_fingerprint)
        payload = payload_for("realization-dependencies", self.docs, self.reports); del payload["profile"]
        with self.exchange():
            report, native = backend.dependencies_document(core=self.core, **payload)
        self.assertEqual(report.fingerprint, native.dependencies_fingerprint)
        with self.assertRaises(backend.RealizationCoreError):
            backend.replay_document(operation="verify-realization", assessment={}, core=self.core)
