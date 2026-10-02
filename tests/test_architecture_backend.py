"""Historical-codec/native-routing boundary, using retained records only."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler import architecture_backend as backend
from biocompiler.core_architecture import (
    ASSESSMENT_SCHEMA, CHECKER_POLICY, CLAIM_SCOPE, IMPLEMENTATION as CHECKER_IMPLEMENTATION,
    PROFILE as CHECKER_PROFILE, RESOURCE_PROFILE as CHECKER_RESOURCE_PROFILE,
    RESULT_SCHEMA as CHECKER_RESULT_SCHEMA, VALIDATION_SCOPE as CHECKER_SCOPE,
)
from biocompiler.core_architecture_producer import (
    BUILD_RESULT_SCHEMA, EXPORT_RESULT_SCHEMA, EXPORT_SCHEMA, IMPLEMENTATION, PROFILE,
    RESOURCE_PROFILE, VALIDATION_SCOPE,
)
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreTimeout, CoreUnavailable, CoreUnsupported, encode_json,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.architecture_build import PayloadArchitectureBuild, PayloadArchitectureExport, PayloadArchitectureRequest
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification, check_payload_architecture_build


ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    # Public to_dict() leaves historical str-Enum values in place. The ordinary
    # public JSON representation encodes them as their declared string values.
    literal = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return encode_json(literal, limit=LIMITS["max_response_bytes"])


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


@contextmanager
def no_reference_execution():
    """Reject executing imported semantic aliases; allow historical constructors."""
    previous = sys.getprofile()
    forbidden = {
        "biocompiler.compiler.behavior": {"lower_to_behavior", "verify_lowering"},
        "biocompiler.semantics.payload_execution": {"derive_source_execution"},
        "biocompiler.compiler.architecture_matching": {"match_architecture_refinement"},
        "biocompiler.compiler.circuit_construction": {"build_circuit_construction", "verify_circuit_construction"},
        "biocompiler.verification.circuit_construction": {"check_circuit_construction"},
        "biocompiler.backends.circuit_construction": {"construct_circuit"},
        "biocompiler.semantics.evaluator": {"evaluate"},
    }
    def guard(frame, event, _argument):
        if event == "call":
            module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
            if name in forbidden.get(module, set()):
                raise AssertionError(f"Reference semantic execution on native route: {module}.{name}")
            if module in {"biocompiler.verification.payload_architecture", "biocompiler.compiler.payload_architecture"} and name.startswith("_") and not name.startswith("__"):
                raise AssertionError("Reference architecture checker helper executed: " + name)
            if module.startswith("biocompiler.backends."):
                raise AssertionError("Python molecular backend executed: " + module + "." + name)
    sys.setprofile(guard)
    try:
        yield
    finally:
        sys.setprofile(previous)


class ArchitectureBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT / "tests/conformance/case-b/base"
        cls.original_request = json.loads((base / "request.json").read_bytes())
        cls.original_build = json.loads((base / "candidate.json").read_bytes())

    def setUp(self):
        self.raw_request = deepcopy(self.original_request)
        self.raw_build = deepcopy(self.original_build)
        self.normalized_build = deepcopy(self.original_build)
        self.request = PayloadArchitectureRequest.from_dict(self.raw_request)
        self.build = PayloadArchitectureBuild.from_dict(self.raw_build)
        self.core = CoreClient(Path(sys.executable))
        self.calls = []
        self.outcome = "pass"
        self.translation_complete = True
        self.construction_complete = True
        self.unresolved = []

    def assessment(self):
        return {"schema_version": ASSESSMENT_SCHEMA, "request_fingerprint": fingerprint(self.original_request),
                "build_fingerprint": fingerprint(self.normalized_build), "outcome": self.outcome,
                "translation_complete": self.translation_complete, "construction_complete": self.construction_complete,
                "diagnostics": [], "unresolved": list(self.unresolved), "assumptions": ["Retained artificial fixture contracts."],
                "checker_version": CHECKER_POLICY, "claim_scope": CLAIM_SCOPE, "search_verified": False,
                "empirical_validation": "unknown", "human_therapeutic_admission": "not_admitted"}

    def verification(self, request, raw_build):
        assessment = self.assessment()
        return {"schema_version": CHECKER_RESULT_SCHEMA, "implementation": CHECKER_IMPLEMENTATION,
                "resource_profile": CHECKER_RESOURCE_PROFILE, "validation_scope": CHECKER_SCOPE,
                "supplied_request_fingerprint": fingerprint(request), "supplied_build_fingerprint": fingerprint(raw_build),
                "assessment_fingerprint": fingerprint(assessment), "assessment": assessment}

    def response_result(self, operation, payload):
        request = payload["request" if operation == "compile-architecture" else "expected_request"]
        raw_build = self.normalized_build if operation == "compile-architecture" else payload["build"]
        verification = self.verification(request, raw_build)
        if operation in ("verify-architecture", "replay-architecture"):
            return verification
        result = {"schema_version": BUILD_RESULT_SCHEMA if operation == "compile-architecture" else EXPORT_RESULT_SCHEMA,
                  "implementation": IMPLEMENTATION, "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
                  "supplied_request_fingerprint": fingerprint(request), "request_fingerprint": fingerprint(self.original_request),
                  "build_fingerprint": fingerprint(self.normalized_build), "verification": verification}
        if operation == "compile-architecture":
            result["build_json"] = encoded(self.normalized_build).decode()
        else:
            fasta = ">a000_t000_payload alphabet=RNA\nACGUAC\n"
            manifest = {"request_fingerprint": fingerprint(self.original_request), "build": self.normalized_build,
                        "verification": self.assessment(), "delivered_member_ids": ["a000_t000_payload"],
                        "source_authority": "Retain the independently supplied request separately."}
            result.update(supplied_build_fingerprint=fingerprint(raw_build), fasta=fasta,
                          fasta_sha256=hashlib.sha256(fasta.encode()).hexdigest(), manifest_json=encoded(manifest).decode(),
                          manifest_sha256=fingerprint(manifest),
                          export_fingerprint=fingerprint({"schema_version": EXPORT_SCHEMA, "fasta": fasta, "manifest": manifest}))
        return result

    def exchange(self, *, rejection=None, on_negotiate=None):
        def invoke(_executable, data, _timeout, cancelled):
            request = json.loads(data)
            operation = request["operation"]
            self.calls.append((request, cancelled))
            if operation == "capabilities":
                result = {"schema_version": CAPABILITIES_SCHEMA,
                          "operations": ["capabilities", "compile-architecture", "export-architecture", "verify-architecture", "replay-architecture"],
                          "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
                          "validation_scopes": [VALIDATION_SCOPE, CHECKER_SCOPE],
                          "profiles": {"architecture_producer": deepcopy(PROFILE), "architecture": deepcopy(CHECKER_PROFILE)},
                          "limits": dict(LIMITS), "claim_scope": "Supplied contracts only."}
                if on_negotiate:
                    on_negotiate()
            else:
                result = self.response_result(operation, request["payload"])
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": result if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "supplied_authority_rejected", "message": "Exact original required", "path": "/payload/build"}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": self.core.role}}
            return encoded(response), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def compile(self):
        return backend.compile_architecture(self.request, core=self.core)

    def export(self):
        return backend.export_architecture(self.build, expected_request=self.request, core=self.core)

    def check(self):
        return backend.check_architecture(self.build, expected_request=self.request, core=self.core)

    def replay(self):
        receipt = PayloadArchitectureVerification.from_dict(self.assessment())
        return backend.replay_architecture(receipt, self.build, expected_request=self.request, core=self.core)

    def test_typed_compile_preserves_full_public_object_and_already_fresh_receipt(self):
        with no_reference_execution(), self.exchange():
            build, receipt, native = self.compile()
        self.assertIsInstance(build, PayloadArchitectureBuild)
        self.assertIsInstance(receipt, PayloadArchitectureVerification)
        self.assertEqual(encoded(build.to_dict()), native.build_json)
        self.assertEqual(encoded(receipt.to_dict()), native.verification._assessment_json)
        self.assertEqual(build.to_dict(), self.original_build)
        self.assertEqual(build.fingerprint, native.build_fingerprint)
        self.assertEqual(self.calls[1][0]["payload"], {"request": self.request.to_dict()})
        self.assertEqual(len(self.calls), 2)

    def test_export_preserves_existing_class_and_complete_paired_native_bytes(self):
        with no_reference_execution(), self.exchange():
            artifact, build, receipt, native = self.export()
        self.assertIsInstance(artifact, PayloadArchitectureExport)
        self.assertEqual(artifact.to_dict(), native.export)
        self.assertEqual(artifact.fasta.encode(), native.fasta_bytes)
        self.assertEqual(encoded(artifact.to_dict()["manifest"]), native.manifest_json)
        self.assertEqual(encoded(build.to_dict()), encoded(native.manifest["build"]))
        self.assertEqual(receipt.to_dict(), native.verification.assessment)
        self.assertEqual(len(self.calls), 2)

    def test_check_and_replay_preserve_complete_external_authority(self):
        self.core = CoreClient(Path(sys.executable), role="verify")
        for method, expected_operation in ((self.check, "verify-architecture"), (self.replay, "replay-architecture")):
            self.calls.clear()
            with self.subTest(operation=expected_operation), no_reference_execution(), self.exchange():
                build, receipt, native = method()
            self.assertEqual(build.to_dict(), self.original_build)
            self.assertEqual(receipt.to_dict(), self.assessment())
            self.assertEqual(native.operation, expected_operation)
            payload = self.calls[1][0]["payload"]
            self.assertEqual(payload["expected_request"], self.request.to_dict())
            self.assertEqual(payload["build"], self.build.to_dict())
            if expected_operation == "replay-architecture":
                self.assertEqual(payload["assessment"], self.assessment())
            self.assertEqual(len(self.calls), 2)

    def test_all_historical_statuses_are_returned_without_promoting_claims(self):
        for status in ("compiled", "partial", "unsupported", "no_solution", "search_exhausted"):
            self.normalized_build = deepcopy(self.original_build)
            self.normalized_build["status"] = status
            if status not in ("compiled", "partial"):
                self.normalized_build.update(plan=None, construction=None)
            self.translation_complete = False
            self.construction_complete = status in ("compiled", "partial")
            self.unresolved = ["Unimplemented model obligation."]
            self.outcome = "pass" if self.construction_complete else "fail"
            with self.subTest(status=status), no_reference_execution(), self.exchange():
                build, receipt, native = self.compile()
            self.assertEqual(build.status, status)
            self.assertEqual(build.to_dict(), self.normalized_build)
            self.assertEqual(receipt.unresolved, tuple(self.unresolved))
            self.assertFalse(receipt.translation_complete)
            self.assertFalse(receipt.search_verified)
            self.assertEqual(receipt.empirical_validation, "unknown")
            self.assertEqual(receipt.human_therapeutic_admission, "not_admitted")
            self.assertEqual(native.status, status)

    def test_supported_partial_export_does_not_require_complete_translation(self):
        self.normalized_build["status"] = "partial"
        self.raw_build = deepcopy(self.normalized_build)
        self.build = PayloadArchitectureBuild.from_dict(self.raw_build)
        self.translation_complete = False
        self.unresolved = ["Additional explicit source obligation."]
        with no_reference_execution(), self.exchange():
            artifact, build, receipt, _native = self.export()
        self.assertEqual(build.status, "partial")
        self.assertTrue(receipt.passed and receipt.construction_complete)
        self.assertFalse(receipt.translation_complete)
        self.assertEqual(artifact.manifest["verification"]["unresolved"], tuple(self.unresolved))

    def test_raw_inputs_freeze_before_negotiation_and_retained_source_is_not_projected(self):
        original_request, original_build = deepcopy(self.raw_request), deepcopy(self.raw_build)
        original_request["circuit"]["profile"]["source_request"] = {
            "schema_version": "test.full.wrapper", "source": original_request["circuit"]["profile"]["source_request"],
            "contract": {"assumptions": ["do not unwrap"], "values": [9007199254740993, -0.0, "原始"]},
        }
        self.raw_request = deepcopy(original_request)
        def mutate():
            self.raw_request["circuit"]["profile"]["source_request"].clear()
            self.raw_build["execution"].clear()
        with no_reference_execution(), self.exchange(on_negotiate=mutate):
            build, _receipt, native = backend.check_document(expected_request=self.raw_request, build=self.raw_build, core=self.core)
        self.assertEqual(self.calls[1][0]["payload"], {"expected_request": original_request, "build": original_build})
        self.assertEqual(native.supplied_request_fingerprint, fingerprint(original_request))
        self.assertEqual(build.to_dict(), original_build)

    def test_valid_input_normalization_is_bound_to_native_normalized_identity(self):
        # Native and historical structural imports both sort this census. Raw
        # supplied identity remains distinct; this test makes no semantic claim.
        self.raw_build["match_instances"] = [
            {"schema_version": "biocompiler.architecture_refinement_instance.v0.1", "id": identity,
             "refinement_id": "supplied", "source_bindings": {"n": "m"}}
            for identity in ("z", "a")
        ]
        self.normalized_build = PayloadArchitectureBuild.from_dict(self.raw_build).to_dict()
        self.assertNotEqual(fingerprint(self.raw_build), fingerprint(self.normalized_build))
        with no_reference_execution(), self.exchange():
            build, _receipt, native = backend.check_document(expected_request=self.raw_request, build=self.raw_build, core=self.core)
        self.assertEqual(build.to_dict(), self.normalized_build)
        self.assertEqual(native.supplied_build_fingerprint, fingerprint(self.raw_build))
        self.assertEqual(native.build_fingerprint, fingerprint(self.normalized_build))

    def test_build_hydration_cannot_silently_change_even_one_source_field(self):
        changed = deepcopy(self.original_build)
        changed["execution"]["source"]["intent"]["nodes"][0]["source"]["file"] = "codec/changed.py"
        hydrated = PayloadArchitectureBuild.from_dict(changed)
        with self.exchange(), patch.object(PayloadArchitectureBuild, "from_dict", return_value=hydrated):
            with self.assertRaises(backend.ArchitectureCoreError) as caught:
                self.compile()
        self.assertIsInstance(caught.exception.core_error, CoreProtocolError)
        self.assertEqual(caught.exception.operation, "compile-architecture")
        self.assertIn("identity", str(caught.exception))

    def test_export_and_verification_hydration_must_be_exact(self):
        receipt = PayloadArchitectureVerification.from_dict(self.assessment())
        changed_receipt = replace(receipt, assumptions=("Codec dropped original assumptions.",))
        with self.exchange(), patch.object(PayloadArchitectureVerification, "from_dict", return_value=changed_receipt):
            with self.assertRaises(backend.ArchitectureCoreError):
                self.check()
        wrong_export = PayloadArchitectureExport(">other alphabet=RNA\nA\n", {"changed": True})
        with self.exchange(), patch.object(PayloadArchitectureExport, "from_dict", return_value=wrong_export):
            with self.assertRaises(backend.ArchitectureCoreError):
                self.export()

    def test_historical_codec_rejection_is_a_distinct_chained_protocol_error(self):
        rejected = SerializationError("Historical codec cannot represent this native field")
        with self.exchange(), patch.object(PayloadArchitectureBuild, "from_dict", side_effect=rejected):
            with self.assertRaises(backend.ArchitectureCoreError) as caught:
                self.compile()
        self.assertIsInstance(caught.exception, SerializationError)
        self.assertIsInstance(caught.exception.core_error, CoreProtocolError)
        self.assertIs(caught.exception.__cause__, caught.exception.core_error)
        self.assertIs(caught.exception.core_error.__cause__, rejected)
        self.assertEqual(caught.exception.diagnostics, ())

    def test_selected_transport_failures_never_execute_fallback(self):
        for error in (CoreUnavailable("missing"), CoreTimeout("timed out"), CoreCancelled("cancelled"),
                      CoreProtocolError("binary or negotiated profile mismatch")):
            for method, operation in ((self.compile, "compile-architecture"), (self.check, "verify-architecture"),
                                      (self.replay, "replay-architecture"), (self.export, "export-architecture")):
                with self.subTest(error=type(error).__name__, operation=operation), no_reference_execution():
                    with patch("biocompiler.core_client._exchange", side_effect=error) as exchange:
                        with self.assertRaises(backend.ArchitectureCoreError) as caught:
                            method()
                self.assertIs(caught.exception.core_error, error)
                self.assertIs(caught.exception.__cause__, error)
                self.assertEqual(caught.exception.operation, operation)
                self.assertEqual(exchange.call_count, 1)

    def test_native_rejection_keeps_structured_diagnostics_and_operation(self):
        for status, error_type in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.subTest(status=status), no_reference_execution(), self.exchange(rejection=status):
                with self.assertRaises(backend.ArchitectureCoreError) as caught:
                    self.export()
            failure = caught.exception
            self.assertIsInstance(failure.core_error, error_type)
            self.assertEqual(failure.operation, "export-architecture")
            self.assertEqual(failure.diagnostics, failure.core_error.response.diagnostics)
            self.assertEqual(failure.diagnostics[0].code, "supplied_authority_rejected")
            self.assertEqual(failure.diagnostics[0].path, "/payload/build")

    def test_cancellation_and_full_replay_document_are_forwarded_once(self):
        cancellation = lambda: False
        assessment = self.assessment()
        with no_reference_execution(), self.exchange():
            backend.replay_document(expected_request=self.raw_request, build=self.raw_build, assessment=assessment,
                                    core=self.core, cancelled=cancellation)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(cancelled is cancellation for _request, cancelled in self.calls))
        self.assertEqual(self.calls[1][0]["payload"]["assessment"], assessment)

    def test_public_native_entry_points_keep_classes_and_use_one_operation(self):
        receipt = PayloadArchitectureVerification.from_dict(self.assessment())
        cases = (
            (lambda: bc.compile(self.request, core=self.core), PayloadArchitectureBuild, "compile-architecture"),
            (lambda: bc.compile_payload_architecture(self.request, core=self.core), PayloadArchitectureBuild, "compile-architecture"),
            (lambda: bc.export_payload_architecture(self.build, expected_request=self.request, core=self.core), PayloadArchitectureExport, "export-architecture"),
            (lambda: bc.check_payload_architecture(self.build, expected_request=self.request, core=self.core), PayloadArchitectureVerification, "verify-architecture"),
            (lambda: check_payload_architecture_build(self.build, expected_request=self.request, core=self.core), PayloadArchitectureVerification, "verify-architecture"),
            (lambda: bc.verify_payload_architecture(receipt, self.build, expected_request=self.request, core=self.core), PayloadArchitectureVerification, "replay-architecture"),
        )
        for invoke, record_type, operation in cases:
            self.calls.clear()
            with self.subTest(operation=operation, invoke=invoke), no_reference_execution(), self.exchange():
                actual = invoke()
            self.assertIsInstance(actual, record_type)
            self.assertEqual([request["operation"] for request, _cancelled in self.calls], ["capabilities", operation])

    def test_bad_raw_json_fails_before_negotiation(self):
        self.raw_request["bad"] = float("nan")
        with self.exchange(), self.assertRaises(backend.ArchitectureCoreError) as caught:
            backend.compile_document(self.raw_request, core=self.core)
        self.assertIsInstance(caught.exception.core_error, CoreProtocolError)
        self.assertEqual(self.calls, [])

    def test_malformed_sdk_argument_types_keep_serialization_error_contract(self):
        receipt = PayloadArchitectureVerification.from_dict(self.assessment())
        calls = (
            lambda: backend.compile_architecture(object(), core=self.core),
            lambda: backend.check_architecture(object(), expected_request=self.request, core=self.core),
            lambda: backend.check_architecture(self.build, expected_request=object(), core=self.core),
            lambda: backend.export_architecture(object(), expected_request=self.request, core=self.core),
            lambda: backend.export_architecture(self.build, expected_request=object(), core=self.core),
            lambda: backend.replay_architecture(object(), self.build, expected_request=self.request, core=self.core),
            lambda: backend.replay_architecture(receipt, object(), expected_request=self.request, core=self.core),
            lambda: backend.replay_architecture(receipt, self.build, expected_request=object(), core=self.core),
        )
        with patch("biocompiler.core_client._exchange") as exchange:
            for index, call in enumerate(calls):
                with self.subTest(index=index), self.assertRaises(SerializationError) as caught:
                    call()
                self.assertNotIsInstance(caught.exception, backend.ArchitectureCoreError)
            exchange.assert_not_called()
