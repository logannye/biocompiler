"""Independent completeness and full original semantics for native protocol inputs."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import FunctionType
import unittest

from tools.check_realization_protocol import (
    APIS, BASE_PIN, BASE_CAPTURE_PIN, CORPUS, CORPUS_PIN, EXPECTED_API_COUNTS,
    VERSION_MUTATIONS, Baseline, Corpus, canonical, digest, require_installed, transport_only,
)


class RealizationProtocolCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()

    def test_all_4119_occurrences_preserve_original_contexts_parents_results_errors_and_children(self):
        c = self.corpus
        original = list(c.baseline.occurrences())
        self.assertEqual(len(original), 4119)
        self.assertEqual(Counter(row["api"] for _, _, row in original), EXPECTED_API_COUNTS)
        self.assertEqual(len({case["id"] for case in c.cases}), 4119)
        for case, (context, ordinal, row) in zip(c.cases, original):
            self.assertEqual(case["id"], context["id"] + "/api/" + str(ordinal))
            self.assertEqual(case["context"], context["id"])
            self.assertEqual((case["ordinal"], case["parent"], case["api"]), (ordinal, row["parent"], row["api"]))
            self.assertEqual(case["input"], "baseline:" + row["native"]["input"])
            self.assertEqual(case["source"], c.baseline.index["source_locations"][row["source"]])
            if row["outcome"] == "returned":
                self.assertEqual(case["historical_result"], "baseline:" + row["result"])
                self.assertIsNone(case["error"])
            else:
                self.assertEqual(case["error"], {"code": row["native"]["expected_code"], **row["error"]})
                self.assertIsNone(case["result"])
        base = c.index["baseline"]
        self.assertEqual(base["inventory_fingerprint"], BASE_PIN)
        self.assertEqual(base["original_capture_fingerprint"], BASE_CAPTURE_PIN)
        for key in ("source_files", "contexts", "subprocesses", "source_ledger"):
            self.assertEqual(base[key], c.baseline.index[key])
        self.assertEqual(sum(context["kind"] == "original_method" for context in base["contexts"]), 373)
        self.assertEqual(len(base["contexts"]), 381)
        self.assertEqual({child["invocation"]["hash_seed"] for child in base["subprocesses"]}, {"1", "37"})
        for child in base["subprocesses"]:
            self.assertEqual(child["invocation"]["returncode"], 0)
            self.assertEqual(sum(len(context["api_calls"]) for context in child["contexts"]), 24)
            self.assertTrue(child["invocation"]["script"] and child["invocation"]["stdout"])

    def test_every_original_direct_and_report_replay_is_in_the_complete_matrix(self):
        c = self.corpus
        operations = Counter()
        for case in c.cases:
            operation, payload = c.payload(case)
            operations[operation] += 1
            self.assertEqual(set(payload), set(c.profiles[APIS[case["api"]][0]]["payload_fields"][operation]))
            raw = c.authority(case)
            if "request" in raw:
                raw["expected_request"] = raw.pop("request")
            self.assertEqual(canonical({k:v for k,v in payload.items() if k not in ("profile","limits")}), canonical(raw))
            if case["result"] is not None and case["api"] != "realization_dependencies":
                replay, replay_payload = c.payload(case, replay=True)
                operations[replay] += 1
                self.assertEqual(replay_payload["assessment"], c.document(case["historical_result"]))
                self.assertEqual(digest(payload), digest({k:v for k,v in replay_payload.items() if k != "assessment"}))
        self.assertEqual(len(operations), 9)
        self.assertEqual(sum(operations.values()), 6231)
        self.assertEqual(sum(count for operation,count in operations.items() if operation.startswith("replay-")), 2112)
        self.assertEqual(c.index["coverage"]["unported_obligations"],
            ["full_workflow_routing", "pipeline_policy", "producer_dispatch", "archive_replay", "export_acceptance"])

    def test_exact_five_policy_mutants_have_independent_complete_current_counterparts(self):
        from tools.freeze_realization_protocol import oracle
        c = self.corpus
        cases = [case for case in c.cases if case["version_mutation"]]
        self.assertEqual({case["id"] for case in cases}, set(VERSION_MUTATIONS))
        for case in cases:
            original, current = (c.document(case[k]) for k in ("historical_result","result"))
            fresh = oracle(case["api"], c.authority(case))
            self.assertEqual(canonical(current), canonical(fresh))
            changed = deepcopy(original)
            dependencies = changed if case["api"] == "realization_dependencies" else changed["dependencies"]
            self.assertEqual(dependencies["checker"], VERSION_MUTATIONS[case["id"]][1])
            dependencies["checker"] = "biocompiler.realization_checker.v0.3"
            self.assertEqual(canonical(changed), canonical(current))
            self.assertNotEqual(canonical(original), canonical(current))

    def test_complete_new_unicode_numeric_source_witnesses_replay_original_python(self):
        from tools.freeze_realization_protocol import authority_identities, oracle
        c = self.corpus
        self.assertEqual(len(c.extra), 38)
        unicode_reports = []
        for case in c.extra:
            raw = c.authority(case)
            self.assertEqual(authority_identities(case["api"], raw), case["authority_identities"])
            try:
                result = oracle(case["api"], raw)
            except Exception as error:
                self.assertIsNone(case["result"], case["id"])
                self.assertEqual((type(error).__module__, type(error).__qualname__, str(error)),
                                 tuple(case["error"][key] for key in ("module","type","message")))
            else:
                expected = c.document(case["result"])
                self.assertEqual(canonical(result), canonical(expected), case["id"])
                if canonical(result) != canonical(result, ascii=True):
                    unicode_reports.append(case["id"])
            if "/unicode-" in case["id"]:
                self.assertNotEqual(canonical(raw), canonical(raw, ascii=True), case["id"])
        self.assertTrue(any("unicode-failing-history" in name for name in unicode_reports))
        for api in APIS:
            by_name = {case["recipe"].split("/")[-1]:case for case in c.extra if case["api"] == api}
            integer, floating = (by_name["horizon-" + label] for label in ("integer","float"))
            self.assertNotEqual(digest(c.authority(integer)), digest(c.authority(floating)))
            self.assertEqual(c.authority(integer)["until"], c.authority(floating)["until"])
            negative = c.authority(by_name["horizon-negative-zero"])
            self.assertIn(b'"until":-0.0', canonical(negative))

    def test_all_independent_authority_getters_and_full_report_family_hashes(self):
        from tools.freeze_realization_protocol import authority_identities
        c = self.corpus
        seen = {}
        for case in [*c.cases, *c.extra]:
            authority = c.authority(case)
            key = digest(authority)
            if key not in seen:
                seen[key] = authority_identities(case["api"], authority)
            self.assertEqual(case["authority_identities"], seen[key], case["id"])
            if case["result"] is not None:
                result = c.document(case["result"])
                family = c.profiles[APIS[case["api"]][0]]
                encoding = family["dependency_encoding" if case["api"] == "realization_dependencies" else "assessment_encoding"]
                self.assertIn(encoding, ("python-json-v1","python-json-ascii-v1"))
                self.assertEqual(len(digest(result, ascii=encoding == "python-json-ascii-v1")), 64)
        self.assertEqual(len({digest(c.authority(case)) for case in c.cases}), 1147)

    def test_boundary_recipes_cover_all_nine_operations_fields_strict_limits_and_replay_forgery(self):
        c = self.corpus
        self.assertEqual(len(c.index["boundary_cases"]), 420)
        self.assertEqual(len({case["id"] for case in c.index["boundary_cases"]}), 420)
        operations = set()
        by_id = {case["id"]:case for case in c.cases}
        for recipe in c.index["boundary_cases"]:
            source = by_id[recipe["source"]]
            operation, payload = c.payload(source, replay=recipe["replay"], current=True)
            operations.add(operation)
            for edit in recipe["edits"]:
                self.assertIn(edit["op"], ("set","remove"))
                self.assertTrue(edit["path"])
            self.assertIn(recipe["code"], {"missing_field","unknown_field","realization_protocol_profile",
                "invalid_type","realization_limits","realization_work_limit","realization_input_limit",
                "realization_report_limit","realization_monitor_limit","realization_assessment_mismatch",
                "composition_evidence","realization_evidence"})
        self.assertEqual(len(operations), 9)

    def test_independent_projection_rebuild_preserves_every_new_byte(self):
        from tools.freeze_realization_protocol import build
        index, documents = build()
        self.assertEqual(index, self.corpus.index)
        for identity, document in documents.items():
            self.assertEqual((CORPUS.with_suffix("") / (identity + ".json")).read_bytes(),
                             canonical(document["value"]) + b"\n")

    def test_integrity_and_alias_boundaries_reject_rehashed_or_mutated_data(self):
        c = Corpus()
        index = deepcopy(c.index); index["cases"].pop()
        index["inventory_fingerprint"] = digest({k:v for k,v in index.items() if k != "inventory_fingerprint"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"; path.write_text(json.dumps(index))
            with self.assertRaisesRegex(AssertionError, "inventory differs"):
                Corpus(path)
        identity = c.extra[0]["input"]
        value = c.document(identity); value["until"] = 999
        self.assertNotEqual(value, c.document(identity))
        c.cache[identity] = value
        with self.assertRaisesRegex(AssertionError, "document identity"):
            c.document(identity)

    def test_installed_transport_guard_rejects_preimported_semantic_aliases(self):
        def probe(): return None
        previous = sys.getprofile()
        for module in ("biocompiler.compiler.lowering", "biocompiler.compiler.request",
            "biocompiler.verification.realization", "biocompiler.synthesis.synthetic",
            "biocompiler.models.synthetic", "biocompiler.semantics.evaluator"):
            alias = FunctionType(probe.__code__, {"__name__":module})
            with self.assertRaisesRegex(AssertionError, "Python semantic execution is forbidden"):
                with transport_only(): alias()
            self.assertIs(sys.getprofile(), previous)
        with transport_only():
            self.assertEqual(digest({"unicode":"细胞"}), digest({"unicode":"细胞"}))
        from unittest.mock import patch
        with patch("tools.check_realization_protocol.Path.cwd", return_value=CORPUS.parents[2]):
            with self.assertRaisesRegex(AssertionError, "outside the checkout"):
                require_installed()


if __name__ == "__main__": unittest.main()
