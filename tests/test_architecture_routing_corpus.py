"""Public native route fixture, codec and execution-guard regressions."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from types import FunctionType
import unittest
from unittest.mock import patch

import biocompiler as bc
from tools.check_architecture_producer_protocol import Corpus, digest
from tools.check_architecture_protocol import Corpus as CheckerCorpus
from tools.check_architecture_routing import EXPECTED_CHECKS, _document, coherent_mutations, routed_execution
from tools import check_architecture_routing as routing


class ArchitectureRoutingCorpusTests(unittest.TestCase):
    def test_fresh_process_loads_legacy_exports_before_guard_and_still_blocks_semantics(self):
        # Other unit modules may have warmed the lazy root; isolate the installed
        # campaign's first public lookup without running a native executable.
        code = '''
import biocompiler as bc
from tools.check_architecture_routing import routed_execution
assert not bc._legacy_loaded
with routed_execution():
    assert bc._legacy_loaded
    assert bc.PayloadArchitectureRequest is not None
    assert bc.compile_payload_architecture is not None
    try:
        bc.__getattr__("PayloadArchitectureRequest")
    except AssertionError as error:
        assert "biocompiler.__getattr__" in str(error)
    else:
        raise AssertionError("The execution guard allowed lazy loading inside a native operation")
from biocompiler.compiler.behavior import lower_to_behavior
with routed_execution():
    try:
        lower_to_behavior(None)
    except AssertionError as error:
        assert "Python semantic authority executed" in str(error)
    else:
        raise AssertionError("Legacy compiler authority escaped the execution guard")
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()
        cls.case = cls.corpus.cases["installed/B/compile/0"]
        cls.request = cls.corpus.document(cls.case["request"])
        cls.build = cls.corpus.document(cls.case["build"])
        checker = CheckerCorpus()
        cls.assessment = checker.document(checker.cases["installed/B"]["assessment"])

    def test_all_original_installed_cases_are_compiled_complete_authorities(self):
        cases = self.corpus.selected()
        self.assertEqual(len(cases), 16)
        self.assertEqual(EXPECTED_CHECKS, 16 * 10 + 2 * 5 + 1 + 2 + 2)
        self.assertEqual({build["status"] for _, _, _, _, build in cases}, {"compiled"})
        for _name, compiled, exported, request, build in cases:
            self.assertEqual(digest(request), compiled["request"])
            self.assertEqual(digest(build), exported["build"])
            self.assertTrue(build["construction"] and build["plan"])

    def test_historical_codecs_and_public_interfaces_do_not_execute_authority(self):
        with routed_execution() as seen:
            request = bc.PayloadArchitectureRequest.from_dict(self.request)
            build = bc.PayloadArchitectureBuild.from_dict(self.build)
            assessment = bc.PayloadArchitectureVerification.from_dict(self.assessment)
            self.assertEqual(digest(_document(request)), self.case["request"])
            self.assertEqual(digest(_document(build)), self.case["build"])
            self.assertTrue(assessment.passed)
            self.assertIsNotNone(build.molecules)
            self.assertEqual(bc.PayloadArchitectureBuild.from_json(build.to_json()).fingerprint, self.case["build"])
        self.assertTrue(any("SourceExecutionManifest.from_dict" in name for name in seen))

    def test_forged_base_pass_is_self_consistent_for_codec_but_changes_original_candidate(self):
        original = deepcopy(self.build)
        stale, forged = coherent_mutations(self.request, self.build)
        with routed_execution():
            stale_request = bc.PayloadArchitectureRequest.from_dict(stale[1])
            forged_build = bc.PayloadArchitectureBuild.from_dict(forged[2])
            self.assertNotEqual(stale_request.fingerprint, self.case["request"])
            self.assertNotEqual(forged_build.fingerprint, self.case["build"])
            self.assertEqual(forged_build.construction.candidate.fingerprint,
                             forged_build.construction.assessment.candidate_fingerprint)
            self.assertEqual(forged[2]["construction"]["assessment"]["outcome"],
                             self.build["construction"]["assessment"]["outcome"])
            self.assertEqual(forged_build.to_dict(), forged[2])
        self.assertEqual(self.build, original)

    def test_legacy_semantic_helpers_and_evaluators_remain_blocked(self):
        def forbidden():
            return True

        previous = sys.getprofile()
        for module, name in (("biocompiler.semantics.payload_execution", "derive_source_execution"),
                             ("biocompiler.compiler.behavior", "lower_to_behavior"),
                             ("biocompiler.verification.payload_architecture", "_source_manifest_checks"),
                             ("biocompiler.verification.circuit_construction", "check_circuit_construction"),
                             ("biocompiler.compiler.payload_architecture", "_matching_options")):
            function = FunctionType(forbidden.__code__.replace(co_name=name, co_qualname=name), {"__name__": module})
            with self.assertRaisesRegex(AssertionError, "Python semantic authority executed"):
                with routed_execution():
                    function()
            self.assertIs(sys.getprofile(), previous)

    def test_guard_caches_code_policy_and_keeps_every_observation(self):
        def allowed():
            return True

        code = allowed.__code__.replace(co_name="to_dict", co_qualname="BuildRequest.to_dict")
        function = FunctionType(code, {"__name__": "biocompiler.compiler.request"})
        with patch.object(routing, "_frame_policy", wraps=routing._frame_policy) as classify:
            with routed_execution() as seen:
                for _ in range(100):
                    self.assertTrue(function())
                self.assertEqual(seen, {"biocompiler.compiler.request.BuildRequest.to_dict"})
                seen.clear()
                function()
            self.assertEqual(seen, {"biocompiler.compiler.request.BuildRequest.to_dict"})
            self.assertEqual(classify.call_count, 1)
            with routed_execution():
                function()
            self.assertEqual(classify.call_count, 2)

    def test_cached_policy_rechecks_current_globals_and_shared_code_module(self):
        def allowed():
            return True

        code = allowed.__code__.replace(co_name="to_dict", co_qualname="BuildRequest.to_dict")
        namespace = {"__name__": "biocompiler.compiler.request"}
        first = FunctionType(code, namespace)
        other = FunctionType(code, {"__name__": "biocompiler.compiler.behavior"})
        for mutate, forbidden in ((lambda: None, other),
                                  (lambda: namespace.update(__name__="biocompiler.compiler.behavior"), first)):
            namespace["__name__"] = "biocompiler.compiler.request"
            previous = sys.getprofile()
            with self.assertRaisesRegex(AssertionError, "Python semantic authority executed"):
                with routed_execution():
                    first()
                    mutate()
                    forbidden()
            self.assertIs(sys.getprofile(), previous)

    def test_cached_policy_does_not_authorize_replaced_function_code(self):
        def function():
            return True

        allowed = function.__code__.replace(co_name="to_dict", co_qualname="BuildRequest.to_dict")
        forbidden = function.__code__.replace(co_name="_resolve_authority", co_qualname="_resolve_authority")
        target = FunctionType(allowed, {"__name__": "biocompiler.compiler.request"})
        with self.assertRaisesRegex(AssertionError, "Python semantic authority executed"):
            with routed_execution():
                target()
                target.__code__ = forbidden
                target()

    def test_generated_method_checks_current_self_and_mutable_type_identity(self):
        namespace = {"__name__": "biocompiler.compiler.request"}
        exec(compile("def __init__(self):\n    pass\n", "<string>", "exec"), namespace)
        function = namespace["__init__"]
        for change in ("self", "module", "qualname"):
            allowed = type("BuildRequest", (), {"__module__": "biocompiler.compiler.request"})
            instance = allowed()
            bad = type("Unapproved", (), {"__module__": "biocompiler.compiler.request"})()
            with self.subTest(change=change), self.assertRaisesRegex(AssertionError, "Python semantic authority executed"):
                with routed_execution() as seen:
                    function(instance)
                    function(instance)
                    self.assertEqual(seen, {"biocompiler.compiler.request.__init__"})
                    if change == "self":
                        instance = bad
                    elif change == "module":
                        allowed.__module__ = "biocompiler.compiler.behavior"
                    else:
                        allowed.__qualname__ = "Unapproved"
                    function(instance)


if __name__ == "__main__":
    unittest.main()
