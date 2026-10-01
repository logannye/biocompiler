"""Pure Python authority and integrity checks for native request conformance."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_PATH = Path(__file__).resolve().parents[1] / "tools/freeze_request_domains.py"
_SPEC = importlib.util.spec_from_file_location("request_domains_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class RequestDomainCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.retained)

    def test_retained_corpus_reproduces_exactly_from_python_authority(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.retained)

    def test_whole_fixture_fits_native_json_resource_bounds(self):
        count, maximum_depth, maximum_string = 0, 0, 0
        pending = [(self.corpus, 0)]
        while pending:
            value, depth = pending.pop()
            count += 1
            maximum_depth = max(maximum_depth, depth)
            if isinstance(value, dict):
                pending.extend((item, depth + 1) for item in value.values())
                maximum_string = max([maximum_string] + [len(key.encode("utf-8")) for key in value])
            elif isinstance(value, list):
                pending.extend((item, depth + 1) for item in value)
            elif isinstance(value, str):
                maximum_string = max(maximum_string, len(value.encode("utf-8")))
        self.assertLess(len(self.retained), 8_000_000)
        self.assertLess(count, 250_000)
        self.assertLessEqual(maximum_depth, 128)
        self.assertLessEqual(maximum_string, 4 * 1024 * 1024)

    def test_all_public_records_and_lowering_pairs_remain_mandatory(self):
        self.assertEqual(self.corpus["coverage"]["covered_record_kinds"], sorted(campaign.PARSERS))
        self.assertEqual(len(self.corpus["cases"]), 49)
        self.assertEqual(len(self.corpus["rejections"]), 62)
        self.assertEqual(len(self.corpus["lowering_cases"]), 14)
        self.assertEqual(len(self.corpus["lowering_rejections"]), 14)
        self.assertEqual(len(self.corpus["coverage"]["variants"]["immune_lineages"]), 11)

    def test_stale_normalization_hash_and_duplicate_ids_cannot_pass(self):
        for field, value, error in (("fingerprint", "0" * 64, "Wrong request fingerprint"),
                                    ("normalized", {}, "Wrong normalized request")):
            with self.subTest(field=field):
                changed = deepcopy(self.corpus)
                changed["cases"][0][field] = value
                with self.assertRaisesRegex(AssertionError, error):
                    campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["cases"][1]["id"] = changed["cases"][0]["id"]
        with self.assertRaisesRegex(AssertionError, "Duplicate fixture identities"):
            campaign.check_corpus(changed)

    def test_valid_typed_wrappers_retain_full_original_authority(self):
        cases = [case for case in self.corpus["cases"] if case["id"].startswith("wrapped_")]
        self.assertEqual(len(cases), 3)
        actual_schemas = []
        for case in cases:
            profile = campaign.CircuitProfileRequest.from_dict(case["input"])
            self.assertEqual(campaign.encoded(profile.to_dict()), campaign.encoded(case["normalized"]))
            actual_schemas.append(profile.source_request.schema_version)
            self.assertNotEqual(profile.source_request.schema_version, campaign.BuildRequest.schema_version)
        self.assertEqual(sorted(actual_schemas), campaign.WRAPPER_SCHEMAS)
        self.assertFalse(any(case["expected_outcome"] == "unsupported" for case in self.corpus["rejections"]))

    def test_source_only_mutation_preserves_semantics_but_breaks_correspondence(self):
        positive = next(case for case in self.corpus["lowering_cases"] if case["id"] == "explicit_source_locations")
        negative = next(case for case in self.corpus["lowering_rejections"] if case["id"] == "changed_diagnostic_source_only")
        self.assertEqual(positive["request_fingerprint"], negative["request_fingerprint"])
        self.assertEqual(positive["behavior_fingerprint"], negative["behavior_fingerprint"])
        self.assertNotEqual(positive["behavior_artifact_fingerprint"], negative["behavior_artifact_fingerprint"])
        self.assertEqual(negative["expected_code"], "lowering_source_location")

    def test_stale_lowering_receipt_hash_is_rejected(self):
        changed = deepcopy(self.corpus)
        changed["lowering_cases"][0]["behavior_artifact_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "Wrong lowering fixture identity"):
            campaign.check_corpus(changed)

    def test_missing_fixture_check_does_not_create_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                campaign.main(["--output", str(path)])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
