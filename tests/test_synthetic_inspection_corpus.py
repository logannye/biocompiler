from __future__ import annotations
import builtins
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.synthetic_inspection_corpus import (
    Corpus, Original, EXPECTED_CENSUS, PINS, ROOT, SUPPLEMENTAL_NAME, SUPPLEMENTAL_SHA256,
    bind_authority, canonical, digest, supplemental,
)


class SyntheticInspectionCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.startswith("biocompiler"):
                raise AssertionError("Corpus projection imported semantic product code")
            return original_import(name, *args, **kwargs)
        with patch("builtins.__import__", guarded):
            cls.corpus = Corpus()

    def test_every_original_method_and_property_occurrence_is_retained(self):
        self.assertEqual(self.corpus.original_count, 9632)
        self.assertEqual({name: value for name, value in self.corpus.census.items() if name in EXPECTED_CENSUS}, EXPECTED_CENSUS)
        original = self.corpus.cases[:self.corpus.original_count]
        self.assertEqual(len({case["id"] for case in original}), 9632)
        counts = Counter(case["api"] for case in original)
        self.assertEqual(counts["CheckResult.exercised_requirement_ids"], 7781)
        self.assertEqual(counts["SelectionResult.outcome"], 70)
        self.assertEqual(sum(case["error"] is not None for case in original), 13)
        for case in original:
            retained = case["evidence"]
            self.assertEqual(retained["context"]["assertion_status"], "passed")
            self.assertIn("parent", retained["observation"])
            self.assertIn("raw_arguments", retained)
            self.assertIn("python_types", retained)
            self.assertIn("source", retained)

    def test_public_properties_and_rejections_come_from_complete_original_observations(self):
        for case in self.corpus.cases[:self.corpus.original_count]:
            retained, api = case["evidence"], case["api"]
            with self.subTest(api=api, identity=case["id"]):
                if case["error"] is not None:
                    self.assertEqual(case["expected_public"], {"error": retained["observation"]["error"]})
                    self.assertEqual(case["error"]["message"], retained["observation"]["error"]["message"])
                    continue
                if api == "CheckResult.exercised_requirement_ids":
                    self.assertEqual(canonical(case["payload"]["record"]), canonical(retained["original_result"]))
                    self.assertEqual(case["expected_public"]["value"], retained["properties"]["exercised_requirement_ids"])
                    self.assertEqual(case["payload"]["query"], "coverage")
                elif api == "SelectionResult.outcome":
                    self.assertEqual(canonical(case["payload"]["selection"]), canonical(retained["original_result"]))
                    self.assertEqual(case["expected_public"]["value"], retained["properties"]["outcome"])
                else:
                    self.assertEqual(canonical(case["expected_public"]["value"]), canonical(retained["original_result"]))
                    self.assertEqual(case["expected_public"]["properties"], retained["properties"] or {})

    def test_complete_frozen_supplement_retains_all_values_errors_and_capture_source(self):
        value = supplemental(ROOT)
        self.assertEqual(canonical(self.corpus.cases[9632:]), canonical(value["cases"]))
        self.assertEqual(len(self.corpus.cases), 9660)
        self.assertEqual(len({case["id"] for case in self.corpus.cases}), 9660)
        self.assertEqual(sum(case["error"] is not None for case in value["cases"]), 8)
        self.assertEqual(len({case["operation"] for case in value["cases"]}), 8)
        self.assertEqual(self.corpus.pins[SUPPLEMENTAL_NAME]["file_sha256"], SUPPLEMENTAL_SHA256)
        for mutation in (lambda x: x["cases"].pop(), lambda x: x.update(capture_source="different source"),
                         lambda x: x["cases"][0]["expected_value"].update(nodes=[])):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "tests/conformance" / (SUPPLEMENTAL_NAME + ".json")
                path.parent.mkdir(parents=True)
                changed = deepcopy(value)
                mutation(changed)
                path.write_bytes(canonical(changed) + b"\n")
                with self.assertRaisesRegex(AssertionError, "supplemental helper capture changed"):
                    supplemental(root)

    def test_projection_rejects_added_or_missing_authority_fields(self):
        original = {"registry": {"complete": True}, "selections": {"node": {"id": "literal"}}}
        self.assertEqual(bind_authority("ComponentRegistry.lock", original),
                         {"registry": original["registry"], "instances": original["selections"]})
        for mutant in ({**original, "omitted_semantics": "unreviewed"}, {"registry": original["registry"]}):
            with self.assertRaisesRegex(AssertionError, "without loss"):
                bind_authority("ComponentRegistry.lock", mutant)

    def test_self_consistent_rehashed_inventory_cannot_replace_original_corpus(self):
        name = "component-runtime-v1"
        index = json.loads((ROOT / "tests/conformance" / (name + ".json")).read_bytes())
        index["contexts"] = index["contexts"][:-1]
        index["inventory_fingerprint"] = digest({k: v for k, v in index.items() if k != "inventory_fingerprint"})
        self.assertNotEqual(index["inventory_fingerprint"], PINS[name][0])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "tests/conformance" / (name + ".json")
            path.parent.mkdir(parents=True)
            path.write_bytes(canonical(index) + b"\n")
            with self.assertRaisesRegex(AssertionError, "inventory changed"):
                Original(root, name)

    def test_complete_document_bytes_are_checked_even_when_json_value_is_equal(self):
        value = {"number": 9007199254740993, "float": 1.0, "text": "é"}
        identity = digest(value)
        raw = canonical(value) + b"\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Original.__new__(Original)
            source.directory = Path(tmp)
            source.metadata = {identity: {"bytes": len(raw)}}
            source.cache = {}
            path = source.directory / (identity + ".json")
            path.write_bytes(raw)
            self.assertEqual(source.document(identity), value)
            source.cache = {}
            changed = json.dumps(value, ensure_ascii=True, sort_keys=True).encode() + b"\n"
            path.write_bytes(changed)
            source.metadata[identity]["bytes"] = len(changed)
            with self.assertRaisesRegex(AssertionError, "complete helper bytes changed"):
                source.document(identity)


if __name__ == "__main__":
    unittest.main()
