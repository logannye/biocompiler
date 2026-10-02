"""Unchanged original fixed producers: complete values plus physical aliases."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
from types import MappingProxyType
import unittest
from unittest.mock import patch

from tools import capture_pipeline_fixed_provider_semantics as original
from biocompiler.ir.intent import freeze_json


def mutated_registration(transform, selected="behavior_to_synthetic"):
    def read(manager):
        result = dict(original.original_registrations(manager))
        contract, producer, validators = result[selected]
        result[selected] = contract, lambda context: transform(producer(context)), validators
        return result
    return read


def values(case):
    return [[call["value"] for call in event["calls"]] for event in case["events"]]


class PipelineFixedProviderSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = original.OUTPUT.read_bytes()
        assert original.sha(raw) == '1f25d16d8fa9688ea34b4937f1d4a2c10fdf44d862daf8990168247758a019e7'
        cls.frozen = json.loads(raw)

    def test_complete_fresh_original_capture_matches_frozen_observations(self):
        actual = original.capture()
        self.assertEqual(actual, self.frozen)
        self.assertEqual(actual["coverage"], {"cases": 3, "providers": 9, "returns": 18})
        self.assertEqual(actual["inventory_fingerprint"], original.sha(original.canonical(
            {key: value for key, value in actual.items() if key != "inventory_fingerprint"})))
        for path, identity in actual["source_files"].items():
            self.assertEqual(original.sha((original.ROOT / path).read_bytes()), identity)

    def test_fresh_roots_and_source_link_members_are_not_interned(self):
        for case in self.frozen["cases"]:
            for event in case["events"]:
                first, second = [item["aliases"] for item in event["calls"]]
                for key in ("proposal", "output", "source_links"):
                    self.assertNotEqual(first[key], second[key])
                self.assertTrue(set(first["link_elements"]).isdisjoint(second["link_elements"]))
                self.assertNotEqual(first["observation"]["ref"], second["observation"]["ref"])
                self.assertEqual(first["observation"]["kind"], "dict")
                self.assertEqual(event["context_target"], case["roots"]["target"])
                self.assertEqual(event["calls"][0]["value"], event["calls"][1]["value"])

    def test_requested_and_equal_selected_configs_have_different_origins(self):
        for case in self.frozen["cases"]:
            calls = case["events"][1]["calls"]
            left, right = [call["aliases"]["generator_config"] for call in calls]
            self.assertEqual(left, right)
            self.assertEqual(left == case["roots"]["requested_config"], not case["id"].endswith("selected_equal"))
        selected = self.frozen["cases"][1]
        candidate = dict(selected["events"][1]["calls"][0]["value"]["fields"])["output"]
        config = dict(candidate["fields"])["generator_config"]
        self.assertEqual({key: value["value"] for key, value in config["fields"]},
            {key: value for key, value in selected["authority"]["config"].items() if key != "schema_version"})

    def test_components_preserve_adapted_roots_locks_and_all_domain_aliases(self):
        for case in self.frozen["cases"]:
            left, right = [call["aliases"] for call in case["events"][2]["calls"]]
            for key in ("registry", "composition", "composition_target", "lock_components", "instances", "supported_domains"):
                self.assertEqual(left[key], right[key])
            self.assertEqual(left["composition_target"], case["roots"]["target"])
            locks = dict(left["lock_components"])
            for identity, component, _ in left["instances"]:
                self.assertEqual(component, locks[identity])
            domains = {item[2] for item in left["instances"]} | {item[1] for item in left["supported_domains"]}
            self.assertEqual(len(domains), 1)
            for key in ("typed_observation", "behavior_sources"):
                self.assertNotEqual(left[key], right[key])

    def test_equal_config_copy_is_detected_without_changing_values(self):
        actual = original.run_case("static:requested", registrations=mutated_registration(
            lambda result: replace(result, output=replace(result.output,
                generator_config=replace(result.output.generator_config)))))
        self.assertEqual(values(actual), values(self.frozen["cases"][0]))
        self.assertEqual([event["record"] for event in actual["events"]],
            [event["record"] for event in self.frozen["cases"][0]["events"]])
        self.assertNotEqual(actual["semantic_alias_groups"], self.frozen["cases"][0]["semantic_alias_groups"])
        config = actual["events"][1]["calls"][0]["aliases"]["generator_config"]
        self.assertNotEqual(config, actual["roots"]["requested_config"])

    def test_equal_component_domain_copy_is_detected(self):
        def changed(result):
            output = result.output
            composition = replace(output.composition, instances=tuple(replace(item,
                required_domain=replace(item.required_domain)) for item in output.composition.instances))
            return replace(result, output=replace(output, composition=composition))
        actual = original.run_case("static:requested", registrations=mutated_registration(changed, "synthetic_to_components"))
        self.assertEqual(values(actual), values(self.frozen["cases"][0]))
        aliases = actual["events"][2]["calls"][0]["aliases"]
        self.assertGreater(len({item[2] for item in aliases["instances"]}), 1)
        self.assertNotEqual(actual["semantic_alias_groups"], self.frozen["cases"][0]["semantic_alias_groups"])

    def test_mutable_observation_and_mapping_order_cannot_be_lost(self):
        actual = original.run_case("static:requested", registrations=mutated_registration(
            lambda result: replace(result, observation_map=freeze_json(result.observation_map))))
        self.assertNotEqual(values(actual), values(self.frozen["cases"][0]))
        self.assertEqual(actual["events"][1]["calls"][0]["aliases"]["observation"]["kind"], "mappingproxy")
        reordered = original.run_case("static:requested", registrations=mutated_registration(
            lambda result: replace(result, observation_map=dict(reversed(tuple(result.observation_map.items()))))))
        self.assertNotEqual(values(reordered), values(self.frozen["cases"][0]))
        self.assertEqual(reordered["events"][1]["record"], self.frozen["cases"][0]["events"][1]["record"])

    def test_raw_observation_never_calls_domain_conversions_or_acceptance(self):
        returned = []
        original.run_case("static:requested", observe=lambda event, manager, role, ordinal, context, result:
            returned.append(result) if event == "after" else None)
        expected = [original.plain(value) for value in returned]
        def forbidden(*args, **kwargs):
            raise AssertionError("Observation executed domain semantics")
        with ExitStack() as stack:
            for cls in original.SAFE:
                for name in ("to_dict", "from_dict", "__post_init__", "resolve"):
                    if hasattr(cls, name):
                        stack.enter_context(patch.object(cls, name, forbidden))
            stack.enter_context(patch.object(original.pipeline.PassManager, "run", forbidden))
            self.assertEqual([original.plain(value) for value in returned], expected)

    def test_full_graph_inventory_includes_all_semantic_aliases(self):
        for case in self.frozen["cases"]:
            groups = case["semantic_alias_groups"]
            self.assertTrue(all(len(item["paths"]) > 1 for item in groups))
            classes = {item["class"].split(".")[-1] for item in groups}
            self.assertTrue({"PinnedIdentity", "TypeSpec", "ValueDomain", "LifecycleInterval", "SourceLocation"} <= classes)
            paths = [tuple(path) for group in groups for path in group["paths"]]
            self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("136", self.frozen["pending"][0])
        self.assertIn("476", self.frozen["pending"][0])

    def test_named_source_and_global_origins_bind_actual_returned_objects(self):
        for case in self.frozen["cases"]:
            origins = {item["origin"]: item for item in case["source_origins"]}
            self.assertTrue({"constant:BOOLEAN", "constant:LEVEL", "constant:DURATION", "constant:default_lifecycle"} <= set(origins))
            groups = case["semantic_alias_groups"]
            for name in ("constant:BOOLEAN", "constant:LEVEL", "constant:default_lifecycle",
                         "request:domain.inputs[0].observable", "request:contract.requirements[0].observable",
                         "request:behavior.nodes[0].source"):
                matches = [group for group in groups if ["source_origins", name] in group["paths"]]
                self.assertEqual(len(matches), 1, name)
                self.assertTrue(any(path[0] == "calls" for path in matches[0]["paths"]), name)
            self.assertEqual(origins["constant:BOOLEAN"]["ref"], origins["request:domain.inputs[0].observable.dtype"]["ref"])
            self.assertEqual(origins["constant:LEVEL"]["ref"], origins["request:contract.requirements[0].observable.dtype"]["ref"])

    def test_eight_closed_alias_types_plus_stable_roots_cover_full_graph(self):
        aliases = {"SourceLocation", "TypeSpec", "Observable", "OperatingDomain", "ValueDomain",
            "PinnedIdentity", "ComponentLock", "LifecycleInterval"}
        roots = {"TargetContext", "SyntheticGeneratorConfig", "ComponentRegistry", "CompositionRequest"}
        for case in self.frozen["cases"]:
            for group in case["semantic_alias_groups"]:
                if group["class"].split(".")[-1] in aliases | roots:
                    continue
                paths = group["paths"]
                self.assertEqual(len(paths), 2, group)
                self.assertEqual([path[2] for path in paths], [0, 1])
                self.assertTrue(all(path[:2] == ["calls", "synthetic_to_components"]
                    and path[3:5] in (["output", "registry"], ["output", "composition"]) for path in paths))
                self.assertEqual(paths[0][3:], paths[1][3:])

    def test_scalar_kinds_and_classvar_shape_are_explicit(self):
        self.assertNotEqual(original.plain(True), original.plain(1))
        self.assertNotEqual(original.plain(1), original.plain(1.0))
        self.assertNotEqual(original.plain({"zeta": [1], "alpha": 2}), original.plain(MappingProxyType({"zeta": (1,), "alpha": 2})))
        config = original.plain(original.SyntheticGeneratorConfig())
        self.assertNotIn("schema_version", config["instance_fields"])
        self.assertIsNotNone(config["class_schema"])


if __name__ == "__main__":
    unittest.main()
