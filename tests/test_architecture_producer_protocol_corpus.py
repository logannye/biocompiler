"""Installed producer campaign identities and non-semantic fixture transport."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import FunctionType
import unittest

from tools.check_architecture_producer_protocol import (
    CORPUS, CORPUS_PIN, EXPECTED_CHECKS, INSTALLED, ORIGINAL, Corpus,
    digest, malformed_mutation, mutations, require_installed, transport_only,
)


class ArchitectureProducerProtocolCorpusTests(unittest.TestCase):
    def test_complete_installed_and_original_build_export_authorities(self):
        selected = Corpus().selected()
        self.assertEqual(len(selected), len(INSTALLED) + len(ORIGINAL))
        self.assertEqual([item[0] for item in selected],
                         ["installed/" + value for value in INSTALLED] + ["case_b/" + value for value in ORIGINAL])
        self.assertEqual(EXPECTED_CHECKS, 2 + 16 * 3 + 2 * 2 + 2 + 2 + 4)
        for _prefix, compiled, exported, request, build in selected:
            self.assertEqual(digest(request), compiled["request"])
            self.assertEqual(digest(build), compiled["build"])
            self.assertEqual(build["request_fingerprint"], compiled["request"])
            self.assertEqual(exported["request"], compiled["request"])
            self.assertEqual(exported["build"], compiled["build"])
            self.assertEqual(len(exported["expected_fingerprint"]), 64)
            self.assertTrue(exported["fasta"].startswith(">"))
            self.assertIn("source_request", request["circuit"]["profile"])

    def test_rehashing_changed_case_inventory_does_not_replace_reviewed_pin(self):
        index = json.loads(CORPUS.read_text())
        index["cases"].pop()
        index["inventory_fingerprint"] = digest({k: v for k, v in index.items() if k != "inventory_fingerprint"})
        self.assertNotEqual(index["inventory_fingerprint"], CORPUS_PIN)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            path.write_text(json.dumps(index))
            with self.assertRaisesRegex(AssertionError, "inventory differs"):
                Corpus(path)

    def test_cached_storage_and_resolved_documents_retain_independent_pins(self):
        corpus = Corpus()
        descriptor = next(item for item in corpus.metadata.values() if item["format"] == "delta")
        corpus.document(descriptor["id"])
        changed = deepcopy(corpus.stored[descriptor["id"]])
        changed["edits"].append({"op": "set", "path": ["unexpected"], "value": True})
        corpus.stored[descriptor["id"]] = changed
        with self.assertRaisesRegex(AssertionError, "Stored document identity"):
            corpus.document(descriptor["id"])
        corpus.metadata[descriptor["id"]]["stored_fingerprint"] = digest(changed)
        with self.assertRaisesRegex(AssertionError, "resolved fixture identity"):
            corpus.document(descriptor["id"])

    def test_mutations_change_one_authority_without_replacing_embedded_pass(self):
        corpus = Corpus()
        case = corpus.cases["installed/B/compile/0"]
        request, build = (corpus.document(case[key]) for key in ("request", "build"))
        original_request, original_build = deepcopy(request), deepcopy(build)
        stale, changed = mutations(request, build)
        self.assertNotEqual(digest(stale[1]), case["request"])
        self.assertEqual(stale[2], build)
        self.assertEqual(changed[1], request)
        actual = changed[2]["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"]
        expected = build["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"]
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(sum(a != b for a, b in zip(actual, expected)), 1)
        actual_assessment = changed[2]["construction"]["assessment"]
        expected_assessment = build["construction"]["assessment"]
        self.assertEqual({key: value for key, value in actual_assessment.items() if key != "candidate_fingerprint"},
                         {key: value for key, value in expected_assessment.items() if key != "candidate_fingerprint"})
        self.assertEqual(actual_assessment["candidate_fingerprint"], digest(changed[2]["construction"]["candidate"]))
        self.assertEqual((request, build), (original_request, original_build))
        stale[2]["execution"]["ledger"].clear()
        self.assertTrue(corpus.document(case["build"])["execution"]["ledger"])

    def test_coherent_base_mutant_passes_historical_codec_but_malformed_mutant_does_not(self):
        from biocompiler.errors import SerializationError
        from biocompiler.ir.architecture_build import PayloadArchitectureBuild
        corpus = Corpus()
        case = corpus.cases["installed/B/compile/0"]
        request, build = (corpus.document(case[key]) for key in ("request", "build"))
        _name, _request, changed = mutations(request, build)[1]
        decoded = PayloadArchitectureBuild.from_dict(changed)
        self.assertNotEqual(decoded.fingerprint, case["build"])
        self.assertEqual(decoded.fingerprint, digest(changed))
        self.assertEqual(decoded.construction.candidate.fingerprint, decoded.construction.assessment.candidate_fingerprint)
        malformed = malformed_mutation(request, build)[2]
        with self.assertRaisesRegex(SerializationError, "Missing or stale molecular role subject"):
            PayloadArchitectureBuild.from_dict(malformed)
        # The old malformed candidate remains byte-for-byte different only at
        # the emitted sequence; historical pins and all PASS claims are intact.
        changed_sequence = malformed["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"]
        malformed["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"] = build["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"]
        self.assertNotEqual(changed_sequence, malformed["construction"]["candidate"]["bundle"]["molecules"][0]["sequence"])
        self.assertEqual(malformed, build)

    def test_execution_guard_blocks_preimported_python_authority_and_restores_profiler(self):
        def probe():
            return True

        old = sys.getprofile()
        for module in ("biocompiler.compiler.payload_architecture", "biocompiler.semantics.payload_execution",
                       "biocompiler.verification.payload_architecture"):
            forbidden = FunctionType(probe.__code__, {"__name__": module})
            with self.assertRaisesRegex(AssertionError, "Python semantic execution is forbidden"):
                with transport_only():
                    forbidden()
            self.assertIs(sys.getprofile(), old)
        with transport_only():
            self.assertEqual(digest({"value": 1}), digest({"value": 1}))
        self.assertIs(sys.getprofile(), old)

    def test_checkout_cannot_claim_installed_execution(self):
        # Unit discovery runs against the checkout; installed campaign execution
        # is a separate hosted gate with an installed package and external cwd.
        from unittest.mock import patch
        with patch("tools.check_architecture_producer_protocol.Path.cwd", return_value=CORPUS.parents[2]):
            with self.assertRaisesRegex(AssertionError, "outside the checkout"):
                require_installed()


if __name__ == "__main__":
    unittest.main()
