"""Pin complete installed protocol authorities before any hosted native call."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.check_architecture_protocol import Corpus, CORPUS, INSTALLED, ORIGINAL, MUTATIONS


class ArchitectureProtocolCorpusTests(unittest.TestCase):
    def test_full_installed_and_original_authority_census_and_meaningful_mutations(self):
        selected = Corpus().selected()
        self.assertEqual(len(selected), len(INSTALLED) + len(ORIGINAL) + len(MUTATIONS))
        self.assertEqual([item[0]["id"] for item in selected[:13]], ["installed/" + name for name in INSTALLED])
        self.assertEqual([item[0]["id"] for item in selected[13:16]], ["case_b/" + name for name in ORIGINAL])
        self.assertEqual([item[3]["outcome"] for item in selected[-8:]], ["fail"] * 8)
        for case, request, build, assessment in selected:
            self.assertEqual(assessment["request_fingerprint"], case["request"])
            self.assertEqual(assessment["build_fingerprint"], case["build"])
            self.assertIn("source_request", request["circuit"]["profile"])
            self.assertIn("execution", build)

    def test_rehashed_index_cannot_change_the_independent_corpus_pin(self):
        index = json.loads(CORPUS.read_text())
        index["cases"].pop()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            path.write_text(json.dumps(index))
            with self.assertRaisesRegex(AssertionError, "inventory differs"):
                Corpus(path)

    def test_resolved_delta_must_retain_complete_identity(self):
        corpus = Corpus()
        descriptor = next(item for item in corpus.metadata.values() if item["format"] == "delta")
        corpus.document(descriptor["id"])
        changed = deepcopy(corpus.stored[descriptor["id"]])
        changed["edits"].append({"op": "set", "path": ["unexpected"], "value": True})
        corpus.stored[descriptor["id"]] = changed
        with self.assertRaisesRegex(AssertionError, "resolved fixture identity"):
            corpus.document(descriptor["id"])

    def test_fixture_reader_returns_independent_mutation_copies(self):
        corpus = Corpus()
        identity = corpus.cases["case_b/base"]["build"]
        first = corpus.document(identity)
        first["execution"]["ledger"].clear()
        self.assertTrue(corpus.document(identity)["execution"]["ledger"])
