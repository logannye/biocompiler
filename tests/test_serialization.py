"""Roundtrip, identity, and snapshot checks for the portable intent artifact."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import importlib.util
from pathlib import Path
import unittest

import cellweave as cw


EXAMPLE_FILE = Path(__file__).resolve().parents[1] / "examples" / "intent_programs.py"
spec = importlib.util.spec_from_file_location("cellweave_examples", EXAMPLE_FILE)
examples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(examples)


class SerializationTests(unittest.TestCase):
    def setUp(self):
        self.program = examples.priming_and_phases()

    def test_every_complete_example_roundtrips_without_losing_information(self):
        for name, build in examples.EXAMPLES.items():
            with self.subTest(example=name):
                program = build()
                restored = cw.IntentProgram.from_json(program.to_json())
                self.assertEqual(restored.to_dict(), program.to_dict())
                self.assertEqual(restored.fingerprint, program.fingerprint)
                self.assertTrue(
                    restored.find(kind="rule") or restored.find(kind="controller")
                )

    def test_repeat_builds_have_deterministic_json_and_fingerprints(self):
        for name, build in examples.EXAMPLES.items():
            with self.subTest(example=name):
                first, second = build(), build()
                self.assertEqual(first.to_json(), second.to_json())
                self.assertEqual(first.fingerprint, second.fingerprint)

    def test_frozen_snapshot_is_unchanged_by_further_authoring(self):
        therapy = cw.Therapy("snapshot")
        cells = therapy.engineer("responders", cell_type="T_cell")
        old = therapy.freeze()
        before = old.to_json()
        cells.when(cells.contact.marker("A").present()).do(cells.rest())
        new = therapy.freeze()
        self.assertEqual(old.to_json(), before)
        self.assertNotEqual(old.fingerprint, new.fingerprint)
        self.assertFalse(old.find(kind="rule"))
        self.assertEqual(len(new.find(kind="rule")), 1)

    def test_snapshot_nodes_and_nested_attributes_are_immutable(self):
        (state,) = self.program.find(kind="state")
        with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
            self.program.name = "changed"
        with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
            state.kind = "changed"
        with self.assertRaises(TypeError):
            state.attributes["initial"] = "changed"
        with self.assertRaises(TypeError):
            state.attributes["values"][0] = "changed"

    def test_mutating_exported_dictionary_cannot_mutate_snapshot(self):
        original = self.program.to_json()
        data = self.program.to_dict()
        data["name"] = "changed"
        data["nodes"][0]["attributes"]["new"] = ["mutable"]
        data["nodes"].clear()
        self.assertEqual(self.program.to_json(), original)

    def test_input_dictionary_is_copied_on_deserialization(self):
        data = self.program.to_dict()
        restored = cw.IntentProgram.from_dict(data)
        original = restored.to_json()
        data["nodes"][0]["attributes"]["new"] = ["mutable"]
        data["roots"].clear()
        self.assertEqual(restored.to_json(), original)

    def test_sources_survive_roundtrip_but_do_not_change_fingerprint(self):
        data = self.program.to_dict()
        sourced = [node for node in data["nodes"] if node.get("source") is not None]
        self.assertTrue(sourced)
        for node in sourced:
            node["source"]["line"] += 100
        moved = cw.IntentProgram.from_dict(data)
        self.assertNotEqual(moved.to_json(), self.program.to_json())
        self.assertEqual(moved.fingerprint, self.program.fingerprint)

    def test_changed_behavior_changes_fingerprint(self):
        data = self.program.to_dict()
        state = next(node for node in data["nodes"] if node["kind"] == "state")
        state["attributes"]["initial"] = "active"
        changed = cw.IntentProgram.from_dict(data)
        self.assertNotEqual(changed.fingerprint, self.program.fingerprint)

    def test_dangling_reference_is_rejected(self):
        data = self.program.to_dict()
        data["nodes"][-1]["inputs"].append("does_not_exist")
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_duplicate_node_identity_is_rejected(self):
        data = self.program.to_dict()
        data["nodes"].append(copy.deepcopy(data["nodes"][0]))
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_dependency_cycle_is_rejected(self):
        data = self.program.to_dict()
        data["nodes"][0]["inputs"].append(data["nodes"][-1]["id"])
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_unknown_schema_version_is_rejected(self):
        data = self.program.to_dict()
        data["schema_version"] = "999.0"
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_missing_root_is_rejected(self):
        data = self.program.to_dict()
        data["roots"].append("does_not_exist")
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_role_reference_must_point_to_a_role(self):
        data = self.program.to_dict()
        state = next(node for node in data["nodes"] if node["kind"] == "state")
        rule = next(node for node in data["nodes"] if node["kind"] == "rule")
        rule["role"] = state["id"]
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_malformed_type_descriptors_are_rejected(self):
        malformed = (
            {},
            {
                "kind": "scalar",
                "name": "Bad",
                "dimensions": {"time": "once"},
                "arguments": [],
            },
            {"kind": "curve", "name": "Bad", "dimensions": {}, "arguments": []},
        )
        for descriptor in malformed:
            with self.subTest(descriptor=descriptor):
                data = self.program.to_dict()
                parameter = next(
                    node for node in data["nodes"] if node["kind"] == "parameter"
                )
                parameter["data_type"] = descriptor
                with self.assertRaises((TypeError, ValueError)):
                    cw.IntentProgram.from_dict(data)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_json('{"name":"first","name":"second"}')

    def test_imported_parameter_names_must_be_present_and_unique(self):
        data = self.program.to_dict()
        parameters = [node for node in data["nodes"] if node["kind"] == "parameter"]
        parameters[1]["attributes"]["name"] = parameters[0]["attributes"]["name"]
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)
        data = self.program.to_dict()
        parameter = next(node for node in data["nodes"] if node["kind"] == "parameter")
        del parameter["attributes"]["name"]
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_imported_parameter_default_must_match_declared_type(self):
        therapy = cw.Therapy("typed_defaults")
        therapy.parameter("threshold", type=cw.Level, default=0.5)
        data = therapy.freeze().to_dict()
        parameter = next(node for node in data["nodes"] if node["kind"] == "parameter")
        parameter["attributes"]["default"] = cw.Duration(5).to_dict()
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_imported_units_cannot_disagree_with_canonical_value(self):
        therapy = cw.Therapy("typed_defaults")
        therapy.parameter(
            "window", type=cw.Duration, default=cw.Duration(1, unit="min")
        )
        data = therapy.freeze().to_dict()
        parameter = next(node for node in data["nodes"] if node["kind"] == "parameter")
        parameter["attributes"]["default"]["canonical_value"] = 1
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_malformed_payloads_are_rejected(self):
        malformed = [None, [], "program", {"name": "incomplete"}]
        for value in malformed:
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                cw.IntentProgram.from_dict(value)
        for value in ("null", "[]", "{invalid", "42"):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                cw.IntentProgram.from_json(value)
        data = self.program.to_dict()
        data["nodes"][0]["inputs"] = "not_a_list_of_ids"
        with self.assertRaises((TypeError, ValueError)):
            cw.IntentProgram.from_dict(data)

    def test_summary_reports_the_serialized_program(self):
        summary = self.program.summary()
        self.assertEqual(summary["name"], self.program.name)
        self.assertEqual(summary["node_count"], len(self.program.nodes))
        self.assertEqual(summary["fingerprint"], self.program.fingerprint)


if __name__ == "__main__":
    unittest.main()
