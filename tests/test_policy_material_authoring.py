"""Python construction fidelity only; no native executable is invoked."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.policy_material_authoring_witness import build

ROOT = Path(__file__).resolve().parents[1]


class PolicyMaterialAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ROOT / "core/test/data/policy_material_request_v01.json").read_text())["request"]

    def test_public_builders_and_both_request_helpers_preserve_full_original(self):
        from biocompiler.core_client import CoreClient
        with patch.object(CoreClient, "call", side_effect=AssertionError("Construction cannot execute native policy")):
            actual, receipt = build(self.original)
        self.assertEqual(actual, self.original)
        self.assertEqual(receipt["runtime_semantics"], "not_executed")
        self.assertEqual(receipt["declaration_count"], 14)
        actual["implementation_request"]["document"]["program"]["source_map"][0]["file"] = "changed.py"
        self.assertNotEqual(actual, self.original)
        self.assertEqual(build(self.original)[1], receipt)

    def test_changed_guard_or_source_location_cannot_masquerade_as_builder_output(self):
        for kind in ("guard", "source"):
            changed = deepcopy(self.original)
            program = changed["implementation_request"]["document"]["program"]
            if kind == "guard":
                rules = {row["id"]: row for row in program["declarations"] if row["$type"] == "Rule"}
                rules["select"]["when"] = deepcopy(rules["exclude"]["when"])
            else:
                program["source_map"][0]["file"] = "different.py"
            with self.subTest(kind=kind), self.assertRaisesRegex(AssertionError, "builder source"):
                build(changed)

    def test_supplied_contracts_remain_external_and_are_not_replaced_by_recipe(self):
        changed = deepcopy(self.original)
        changed["context"]["recipient"]["identity"] = "separately-supplied-recipient"
        actual, receipt = build(changed)
        self.assertEqual(actual, changed)
        self.assertNotEqual(receipt["material_request_digest"], build(self.original)[1]["material_request_digest"])
        self.assertEqual(receipt["runtime_semantics"], "not_executed")

    def test_changed_original_definition_is_rejected_before_native_work(self):
        changed = deepcopy(self.original)
        changed["implementation_request"]["document"]["program"]["semantics"]["definitions"][0]["description"] = "changed"
        with self.assertRaisesRegex(AssertionError, "authored source definitions"):
            build(changed)


if __name__ == "__main__":
    unittest.main()
