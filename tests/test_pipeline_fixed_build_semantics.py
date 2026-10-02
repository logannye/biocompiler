"""Original build graph controls; no native executable runs in this suite."""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
import sys
from types import MappingProxyType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import capture_pipeline_fixed_build_semantics as oracle


class PipelineFixedBuildSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = []
        cls.current = oracle.capture(retain=cls.retained)
        cls.frozen = json.loads(oracle.OUTPUT.read_bytes())

    def test_full_original_values_and_all_physical_edges_are_frozen(self):
        self.assertEqual(self.current, self.frozen)
        self.assertEqual(oracle.sha(oracle.canonical({key: value for key, value in self.frozen.items()
            if key != "inventory_fingerprint"})), self.frozen["inventory_fingerprint"])
        self.assertEqual([case["id"] for case in self.frozen["cases"]], list(oracle.CASES))
        self.assertEqual([len(case["nodes"]) for case in self.frozen["cases"]], [2008, 6606, 2177, 2177, 2343, 7819])

    def test_all_original_continuation_authorities_remain_in_the_inventory(self):
        self.assertEqual([len(case["original_cases"]) for case in self.frozen["cases"]], [22, 2, 1, 1, 1, 12])
        self.assertEqual(len({identity for case in self.frozen["cases"] for identity in case["original_cases"]}), 39)
        self.assertEqual(self.frozen["coverage"], {"authorities": 6, "fixed_boundaries": 136,
            "manager_contexts": 476, "eligible_continuation_chains": 39, "suffix_operations": 254,
            "prefix_operations": 312, "public_returns": 12, "producer_returns": 18, "excluded_boundaries": 10})
        for case in self.frozen["cases"]:
            self.assertEqual(oracle.sha(oracle.canonical(case["authority"])), case["authority_sha256"])

    def test_same_manager_candidate_selection_and_exact_historical_artifacts(self):
        for case in self.frozen["cases"]:
            with self.subTest(case=case["id"]):
                roots = case["roots"]
                upstream, build = roots["synthetic"], roots["component"]
                records = dict(roots["component_records"])
                self.assertEqual(oracle.at(case, upstream, "manager"), oracle.at(case, build, "manager"))
                self.assertEqual(oracle.at(case, upstream, "candidate"), oracle.at(case, build, "candidate"))
                self.assertEqual(oracle.at(case, upstream, "selection_result"), oracle.at(case, build, "selection_result"))
                self.assertEqual(oracle.at(case, upstream, "result", "artifact"), records["mechanism"])
                self.assertEqual(oracle.at(case, build, "result", "artifact"), records["components"])
                self.assertEqual(dict(roots["synthetic_records"]), {key: records[key] for key in ("request", "behavior", "mechanism")})

    def test_fresh_parsed_roots_are_distinct_from_producer_and_authored_roots(self):
        for case in self.frozen["cases"]:
            roots = case["roots"]
            outputs = dict(roots["producer_returns"])
            build = roots["component"]
            self.assertNotEqual(oracle.at(case, build, "candidate"), oracle.at(case, outputs["generate"], "output"))
            self.assertNotEqual(oracle.at(case, build, "assembly"), oracle.at(case, outputs["components"], "output"))
            self.assertNotEqual(oracle.at(case, build, "assembly", "composition", "target"), roots["target"])
            self.assertNotEqual(oracle.at(case, build, "candidate", "generator_config"), roots["selected_config"])

    def test_requested_and_selected_config_origin_is_preserved(self):
        for case in self.frozen["cases"]:
            roots = case["roots"]
            if case["id"] == "selected_temporal":
                self.assertNotEqual(roots["requested_config"], roots["selected_config"])
                selection = oracle.at(case, roots["synthetic"], "selection_result")
                self.assertEqual(oracle.at(case, selection, "config"), roots["requested_config"])
                self.assertEqual(oracle.at(case, selection, "alternatives", 1, "candidate", "generator_config"), roots["selected_config"])
                self.assertNotEqual(oracle.at(case, selection, "alternatives", 0, "candidate", "generator_config"), roots["requested_config"])
            else:
                self.assertEqual(roots["requested_config"], roots["selected_config"])

    def test_complete_parsed_to_record_container_alias_rule_is_source_bounded(self):
        counts = []
        for case in self.frozen["cases"]:
            aliases = oracle.historical_aliases(case)
            retained = []
            for entry in aliases["candidate"]:
                value = oracle.node(case, entry["node"])
                self.assertEqual((value["kind"], value["class"]), ("sequence", "tuple"))
                if value["items"]:
                    self.assertEqual(entry["public"], entry["stored"])
                    path = entry["public"]
                    self.assertTrue(path in (["mechanism", "outputs"], ["mechanism", "required_capabilities"])
                        or (len(path) == 4 and path[:2] == ["mechanism", "nodes"]
                            and type(path[2]) is int and path[3] in ("inputs", "requirement_ids")))
                    retained.append(entry)
            counts.append(len(retained))
            self.assertEqual(len(aliases["assembly"]), 1)
            self.assertEqual(oracle.node(case, aliases["assembly"][0]["node"]),
                {"kind": "sequence", "class": "tuple", "items": []})
        self.assertEqual(counts, [14, 43, 14, 14, 16, 49])

    def test_equal_value_alias_and_scalar_or_order_mutations_are_not_invisible(self):
        case = self.frozen["cases"][0]
        changed = deepcopy(case)
        root = oracle.node(changed, changed["roots"]["component"])
        candidate = next(value for key, value in root["fields"] if key == "candidate")
        changed["nodes"].append(deepcopy(oracle.node(changed, candidate)))
        for pair in root["fields"]:
            if pair[0] == "candidate":
                pair[1] = {"ref": "object/" + str(len(changed["nodes"]) - 1)}
        self.assertNotEqual(changed, case)
        self.assertNotEqual(oracle.at(changed, changed["roots"]["synthetic"], "candidate"),
            oracle.at(changed, changed["roots"]["component"], "candidate"))
        graph = oracle.Graph()
        self.assertNotEqual(graph.encode(True), graph.encode(1))
        self.assertNotEqual(graph.encode({"a": 1, "b": False}), graph.encode({"b": False, "a": 1}))
        self.assertNotEqual(graph.encode({"a": 1}), graph.encode(MappingProxyType({"a": 1})))
        shared = {"a": 1}
        self.assertEqual(graph.encode(shared), graph.encode(shared))
        self.assertNotEqual(graph.encode(shared), graph.encode(dict(shared)))

    def test_observer_does_not_invoke_domain_conversion_or_equality(self):
        actual = self.retained[0]["component"]
        graph = oracle.Graph()
        with patch.object(type(actual.assembly), "to_dict", side_effect=AssertionError("semantic converter")), \
                patch.object(type(actual.assembly), "__eq__", side_effect=AssertionError("domain equality")):
            reference = graph.encode(actual)
            self.assertEqual(reference, graph.encode(actual))
        self.assertEqual(list(dict(oracle.node({"nodes": graph.nodes}, reference)["fields"])),
            [item.name for item in fields(actual)])

    def test_profiler_chains_and_restores_on_original_exception(self):
        calls = []
        previous = sys.getprofile()
        def outer(frame, event, result):
            if frame.f_code is probe.__code__:
                calls.append(event)
        def probe():
            raise LookupError("original exception")
        sys.setprofile(outer)
        try:
            with self.assertRaisesRegex(LookupError, "original exception"):
                with oracle.Observer().installed():
                    probe()
            self.assertIs(sys.getprofile(), outer)
        finally:
            sys.setprofile(previous)
        self.assertEqual(calls, ["call", "return"])


if __name__ == "__main__":
    unittest.main()
