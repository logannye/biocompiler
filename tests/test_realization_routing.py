"""Exercise every original SDK route with guarded transport fixtures, no native run."""
from contextlib import contextmanager
from copy import deepcopy
import sys
from types import FunctionType, SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreCancelled, CoreRejected, CoreResponse, CoreTimeout, Diagnostic
from biocompiler.core_realization import RealizationClient, RealizationResult
from biocompiler.realization_backend import RealizationCoreError
from tools.check_realization_protocol import APIS, Corpus, canonical, digest
from tools.check_realization_routing import (
    _ROUTES, allowed_frame, campaign, hydrate, routed_execution, sdk_function,
)


class RealizationRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()

    def _response(self, case, operation, role):
        if case["result"] is None:
            error = case["error"]
            raise CoreRejected(CoreResponse("fixture", operation, "error", None,
                (Diagnostic(error["code"], error["message"], None),), role, "test"))
        expected = self.corpus.document(case["result"])
        family = self.corpus.profiles[APIS[case["api"]][0]]
        encoding = family["dependency_encoding" if case["api"] == "realization_dependencies" else "assessment_encoding"]
        report = canonical(expected, ascii=encoding == "python-json-ascii-v1")
        return RealizationResult("fixture", operation, role, digest(expected, ascii=encoding == "python-json-ascii-v1"),
                                 encoding, report, b"{}")

    def test_all_original_and_supplemental_direct_sdk_calls_serialize_and_hydrate_under_guard(self):
        c = self.corpus
        expected_calls = [*c.cases, *c.extra]
        positions = {"core":0, "verify":0}
        def exchange(client, operation, payload, **kwargs):
            role = client.transport.role
            case = expected_calls[positions[role]]
            positions[role] += 1
            expected_operation, expected_payload = c.payload(case)
            self.assertEqual(operation, expected_operation)
            self.assertEqual(canonical(payload), canonical(expected_payload), case["id"])
            return self._response(case, operation, role)
        receipt = {"checks":[]}
        # This only substitutes the external transport result. All original SDK
        # routing, input serialization and historical output hydration execute.
        with patch.object(RealizationClient, "call", exchange):
            campaign([SimpleNamespace(role="core"), SimpleNamespace(role="verify")], c, receipt)
        self.assertEqual(positions, {"core":4157, "verify":4157})
        self.assertEqual(len(receipt["checks"]), 8314)
        self.assertEqual(receipt["guard"]["status"], "passed")
        seen = receipt["guard"]["allowed_executed_functions"]
        for module, functions in _ROUTES.items():
            for function in functions:
                self.assertIn(module + "." + function, seen)
        self.assertNotIn("biocompiler.compiler.request.RealizationRequest.__post_init__", seen)
        self.assertNotIn("biocompiler.verification.components.dependencies", seen)

    def test_every_selected_sdk_route_preserves_transport_failure_without_fallback(self):
        c = self.corpus
        for api in APIS:
            case = next(case for case in c.cases if case["api"] == api and case["result"] is not None)
            arguments = hydrate(api, c.authority(case))
            function = sdk_function(api)
            for error in (CoreTimeout("test bounded timeout"), CoreCancelled("test cancellation")):
                with self.subTest(api=api,error=type(error).__name__):
                    with patch.object(RealizationClient, "call", side_effect=error):
                        with routed_execution():
                            with self.assertRaises(RealizationCoreError) as raised:
                                function(**arguments, core=SimpleNamespace(role="core"))
                    self.assertIs(raised.exception.core_error, error)
                    self.assertEqual(raised.exception.diagnostics, ())

    def test_guard_denies_preimported_lowering_evaluation_dependency_generation_and_request_construction(self):
        def probe(): return None
        original = sys.getprofile()
        forbidden = [
            ("biocompiler.compiler.lowering", "verify_lowering"),
            ("biocompiler.compiler.request", "RealizationRequest.__post_init__"),
            ("biocompiler.compiler.request", "RealizationRequest.from_dict"),
            ("biocompiler.semantics.evaluator", "evaluate"),
            ("biocompiler.models.synthetic", "run_synthetic"),
            ("biocompiler.verification.realization", "_horizon"),
            ("biocompiler.verification.components", "dependencies"),
            ("biocompiler.verification.components", "check_composition"),
            ("biocompiler.synthesis.synthetic", "generate_synthetic"),
            ("biocompiler.synthesis.synthetic", "_generate_synthetic"),
            ("biocompiler.synthesis.components", "adapt_synthetic_components"),
            ("biocompiler.synthesis.selection", "select_synthetic"),
        ]
        for module,name in forbidden:
            code = probe.__code__.replace(co_qualname=name, co_name=name.split(".")[-1])
            alias = FunctionType(code, {"__name__":module})
            with self.subTest(module=module,function=name):
                with self.assertRaisesRegex(AssertionError, "Python semantic authority executed"):
                    with routed_execution(): alias()
            self.assertIs(sys.getprofile(), original)

    def test_sdk_inputs_are_hydrated_before_guard_and_retain_full_raw_identity(self):
        c = self.corpus
        for api in APIS:
            case = next(case for case in c.cases if case["api"] == api and case["result"] is not None)
            authority = c.authority(case)
            arguments = hydrate(api, authority)
            with routed_execution():
                actual = {key: value.to_dict() for key,value in arguments.items() if key not in ("history","until")}
                actual["history"] = [frame.to_dict() for frame in arguments["history"]]
                actual["until"] = arguments["until"]
            self.assertEqual(canonical(actual), canonical(authority))


if __name__ == "__main__": unittest.main()
