"""Public native route fixture, codec and execution-guard regressions."""

from copy import deepcopy
import sys
from types import FunctionType
import unittest

import biocompiler as bc
from tools.check_architecture_producer_protocol import Corpus, digest
from tools.check_architecture_protocol import Corpus as CheckerCorpus
from tools.check_architecture_routing import EXPECTED_CHECKS, _document, coherent_mutations, routed_execution


class ArchitectureRoutingCorpusTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
