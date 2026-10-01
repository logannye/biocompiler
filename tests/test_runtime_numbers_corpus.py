"""Retained scalar arithmetic oracle with independent edge-case witnesses."""

import json
import unittest

from tools import freeze_runtime_numbers as corpus


class RuntimeNumberCorpusTests(unittest.TestCase):
    def test_retained_corpus_matches_current_python_arithmetic_and_literal_witnesses(self):
        expected = corpus.build()
        self.assertEqual(corpus.CORPUS.read_bytes(), corpus.encoded(expected))
        self.assertEqual(len(expected["cases"]), 1948)
        self.assertEqual(len({case["id"] for case in expected["cases"]}), 1948)

    def test_full_numeric_primitive_coverage_preserves_result_representation(self):
        cases = json.loads(corpus.CORPUS.read_bytes())["cases"]
        self.assertEqual({case["operation"] for case in cases},
                         {"add", "sub", "mul", "div", "neg", "compare", "min", "max", "advance", "fsum"})
        literals = {case["id"]: case for case in cases if case["authority"] == "literal_and_cpython"}
        self.assertEqual(len(literals), 28)
        self.assertEqual(literals["zero_divided_by_negative_integer"]["canonical_json"], "-0.0")
        self.assertEqual(literals["integer_arithmetic_stays_integer"]["canonical_json"], "9007199254740993")
        self.assertEqual(literals["fsum_exact_cancellation"]["canonical_json"], "1.0")
        self.assertEqual(literals["fsum_intermediate_overflow"]["code"], "evaluation_overflow")


if __name__ == "__main__":
    unittest.main()
