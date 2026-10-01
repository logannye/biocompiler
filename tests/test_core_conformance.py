"""Pure-Python checks of the hosted native campaign's authority and coverage."""

from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


_PATH = Path(__file__).resolve().parents[1] / "tools/check_core_conformance.py"
_SPEC = importlib.util.spec_from_file_location("core_conformance_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class CoreConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.load_corpus()
        cls.programs = campaign.source_programs()

    def test_literal_expectations_retain_independent_bytes_and_digests(self):
        by_id = {value["id"]: value for value in self.corpus["literal_vectors"]}
        self.assertEqual(by_id["null"]["sha256"], "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b")
        self.assertIn("1.0", by_id["integer-and-float-spelling"]["canonical_json"])
        self.assertIn("-0.0", by_id["integer-and-float-spelling"]["canonical_json"])
        self.assertIn("9007199254740993", by_id["large-exact-integers"]["canonical_json"])
        self.assertIn("é", by_id["unicode-not-normalized"]["canonical_json"])
        self.assertEqual(by_id["asymmetric-binary-rounding-interval"]["canonical_json"],
                         "[6.617444900424222e-24,-6.617444900424222e-24]")

    def test_changed_expected_literal_cannot_be_repaired_by_core_output(self):
        corpus = deepcopy(self.corpus)
        corpus["literal_vectors"][0]["canonical_json"] = "false"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(corpus))
            with self.assertRaisesRegex(AssertionError, "Stale literal fingerprint"):
                campaign.load_corpus(path)

    def test_bit_pattern_oracle_is_seeded_broad_finite_and_exact(self):
        settings = self.corpus["python_oracle"]
        first = campaign.float_patterns(settings["seed"], settings["finite_float_count"])
        self.assertEqual(first, campaign.float_patterns(settings["seed"], settings["finite_float_count"]))
        self.assertGreaterEqual(len(first), 2048)
        self.assertGreater(len({(bits >> 52) & 0x7ff for bits, _ in first}), 1000)
        self.assertEqual({bits >> 63 for bits, _ in first}, {0, 1})
        for bits, value in first:
            self.assertTrue(math.isfinite(value))
            self.assertEqual(struct.pack(">d", value), bits.to_bytes(8, "big"))
        with self.assertRaisesRegex(AssertionError, "2048"):
            campaign.float_patterns(1, 20)

    def test_decimal_boundaries_cover_both_signed_zero_and_extremes(self):
        values = campaign.boundary_floats()
        self.assertGreater(len(values), 3000)
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertIn(struct.pack(">d", -0.0), [struct.pack(">d", value) for value in values])
        self.assertIn(5e-324, values)

    def test_binary_boundaries_include_asymmetric_intervals_and_four_ulps(self):
        values = campaign.binary_boundary_floats(**self.corpus["python_oracle"]["binary_boundaries"])
        patterns = {int.from_bytes(struct.pack(">d", value), "big") for value in values}
        self.assertEqual(len(values), len(patterns))
        self.assertGreater(len(values), 37000)
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertTrue({0, 1 << 63, 1, (1 << 63) | 1}.issubset(patterns))
        for center in (0x0010000000000000, 0x3b20000000000000, 0x7fe0000000000000):
            for offset in range(-4, 5):
                self.assertIn(center + offset, patterns)
                self.assertIn((center + offset) | (1 << 63), patterns)
        # Literal decimal expected at 2**-77; the old nearest-only formatter
        # incorrectly continued to 17 significant digits at this boundary.
        self.assertEqual(campaign.canonical(math.ldexp(1.0, -77)), "6.617444900424222e-24")
        self.assertEqual(float("6.6174449004242214e-24"), math.ldexp(1.0, -77))

    def test_every_authored_example_keeps_source_location_invariance(self):
        self.assertGreaterEqual(len(self.programs), 6)
        for name, program in self.programs.items():
            for variant, document in campaign.source_variants(program.to_dict()).items():
                with self.subTest(example=name, variant=variant):
                    restored = campaign.IntentProgram.from_dict(document)
                    self.assertEqual(restored.summary(), program.summary())
                    self.assertNotEqual(restored.to_dict(), program.to_dict())

    def test_typed_positive_cases_retain_optional_field_identity(self):
        values = campaign.typed_programs()
        fingerprints = {name: campaign.IntentProgram.from_dict(value).fingerprint for name, value in values.items()}
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["scalar-negative-zero"])
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["optional-type-fields-omitted"])
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["declared-zero-dimension-retained"])

    def test_mutations_are_invalid_and_have_specific_rejection_signatures(self):
        cases = campaign.intent_mutations(self.programs)
        self.assertGreaterEqual(len(cases), 25)
        self.assertEqual(len(cases), len({name for name, _, _ in cases}))
        for name, code, document in cases:
            with self.subTest(case=name):
                self.assertNotIn(code, {"internal_error", "resource_exhausted", "invalid_json"})
                with self.assertRaises(Exception):
                    campaign.IntentProgram.from_dict(document)

    def test_summary_comparison_cannot_promote_scope_or_drop_obligations(self):
        program = next(iter(self.programs.values()))
        correct = {"validation_scope": campaign.SCOPE, "summary": program.summary(),
                   "unimplemented_obligations": campaign.OBLIGATIONS}
        client = SimpleNamespace(role="core", validate_intent=lambda _: SimpleNamespace(result=correct))
        runner = campaign.Campaign({"checks": []})
        runner.intent(client, "positive", program.to_dict(), program.summary())
        self.assertEqual(len(runner.receipt["checks"]), 1)
        for key, value in (("validation_scope", "whole-therapy-verified"), ("unimplemented_obligations", [])):
            forged = {**correct, key: value}
            client.validate_intent = lambda _, result=forged: SimpleNamespace(result=result)
            with self.assertRaisesRegex(AssertionError, "promoted its scope"):
                runner.intent(client, "forged", program.to_dict(), program.summary())
        self.assertEqual(len(runner.receipt["checks"]), 1)

    def test_raw_requests_retain_lexical_numbers_and_invalid_bytes(self):
        request = campaign.request_bytes(b'{"x":-0,"x":1.0,"bad":"\xff"}')
        self.assertIn(b'{"x":-0,"x":1.0,"bad":"\xff"}', request)
        self.assertTrue(request.endswith(b"}}"))

    def test_wrong_native_rejection_never_counts_as_mutant_detection(self):
        runner = campaign.Campaign({"checks": []})
        client = SimpleNamespace(role="core")
        crash = {"status": "error", "result": None, "diagnostics": [{"code": "internal_error"}],
                 "request_id": None, "operation": None}
        with patch.object(campaign, "raw_response", return_value=crash):
            with self.assertRaisesRegex(AssertionError, "wrong rejection signature"):
                runner.rejection(client, "duplicate", b"invalid", "duplicate_key")
        self.assertEqual(runner.receipt["checks"], [])


if __name__ == "__main__":
    unittest.main()
