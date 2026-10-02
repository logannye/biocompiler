"""Frozen original identity/order evidence and adversarial replay controls."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("identity_capture", ROOT / "tools/capture_pipeline_identity_semantics.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
PIN = "7088dd2f6ad6db60f30e2541f770b73691ff0b0d98950839ef7c4c4ed1d50896"


class PipelineIdentitySemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = CAPTURE.OUTPUT.read_bytes()
        assert CAPTURE.sha(raw) == PIN
        cls.frozen = json.loads(raw)

    def test_complete_original_capture_and_source_pins(self):
        actual = CAPTURE.capture()
        self.assertEqual(actual, self.frozen)
        self.assertEqual(actual["coverage"], {"cases": 5, "events": 34, "records": 10})
        body = {key: value for key, value in self.frozen.items() if key != "inventory_fingerprint"}
        self.assertEqual(self.frozen["inventory_fingerprint"], CAPTURE.sha(CAPTURE.canonical(body)))
        for path, pin in self.frozen["source_files"].items():
            self.assertEqual(CAPTURE.sha((ROOT / path).read_bytes()), pin, path)

    def test_physical_sharing_and_order_are_explicit(self):
        case = self.frozen["cases"][0]
        root = next(item for item in case["events"] if item["event"] == "root")
        sharing = next(item for item in case["events"] if item["event"] == "sharing")
        self.assertTrue(root["target_is_supplied"])
        self.assertTrue(root["add_return_is_get"])
        self.assertTrue(root["source_obligations_tuple_is_supplied"])
        self.assertTrue(root["source_obligations_are_supplied"])
        self.assertFalse(root["payload_is_original"])
        for key in ("validators_same_context", "input_is_source", "target_is_supplied", "requirement_tuple_is_source",
                    "dependencies_are_callback_snapshot", "output_is_validator_output", "links_are_proposal_tuple",
                    "links_preserve_elements", "run_is_get", "repeated_get_same", "result_artifact_is_record",
                    "unresolved_items_reuse_obligations", "obligations_reuse_source", "introduced_obligation_is_contract"):
            self.assertTrue(sharing[key], key)
        self.assertTrue(all(sharing["shared_fields"].values()))
        for key in ("producer_is_validator", "observation_is_proposal_mapping", "configuration_is_argument",
                    "results_same", "producer_dependencies_are_root"):
            self.assertFalse(sharing[key], key)
        self.assertEqual(sharing["checks_order"], ["z_check", "a_check"])
        self.assertEqual(sharing["dependency_order"], ["zeta", "request", "registry", "alpha", "target"])
        self.assertEqual(sharing["output_nested_order"], ["omega", "alpha"])
        self.assertEqual(sharing["configuration_order"], ["zeta", "alpha"])

    def test_nested_failure_keeps_original_inner_record(self):
        case = next(item for item in self.frozen["cases"] if item["case"] == "run:nested_raises")
        sharing = next(item for item in case["events"] if item["event"] == "nested_sharing")
        self.assertTrue(sharing["marker_same"])
        self.assertTrue(sharing["inner_record_preserved"])
        self.assertTrue(sharing["producer_snapshots_distinct"])
        self.assertTrue(sharing["producer_configurations_distinct"])
        self.assertTrue(sharing["source_input_shared"])
        failed = next(item for item in case["events"] if item["event"] == "outer_get")
        self.assertEqual(failed["outcome"], "raised")
        self.assertEqual(failed["message"], "Missing artifact/provider: 'outer'.")

    def test_stale_error_keeps_stored_snapshot_and_accepted_history(self):
        case = next(item for item in self.frozen["cases"] if item["case"] == "run:validator_mutates_snapshot")
        snapshot = next(item for item in case["events"] if item["event"] == "after_stale")
        self.assertTrue(all(value for key, value in snapshot.items() if key != "event"))
        errors = [item for item in case["events"] if item.get("outcome") == "raised"]
        self.assertEqual(len(errors), 3)
        self.assertTrue(all("registry" in item["message"] for item in errors))

    def test_equivalent_record_copy_cannot_pass_identity_replay(self):
        class CopiesRecord(CAPTURE.pipeline.PassManager):
            def run(self, *args, **kwargs):
                return replace(super().run(*args, **kwargs))
        actual = CAPTURE.sharing_case(CopiesRecord)
        self.assertNotEqual(actual, self.frozen["cases"][0])
        sharing = next(item for item in actual["events"] if item["event"] == "sharing")
        self.assertFalse(sharing["run_is_get"])
        self.assertFalse(sharing["result_artifact_is_record"])
        # Complete field values still match; physical identity is independently checked.
        self.assertEqual(actual["records"], self.frozen["cases"][0]["records"])

    def test_fresh_equivalent_validator_context_cannot_pass_replay(self):
        class CopiesContext(CAPTURE.pipeline.PassManager):
            def register(self, contract, producer, validators):
                def wrapped(validator):
                    return lambda context: validator(replace(context))
                return super().register(contract, producer, {key: wrapped(value) for key, value in validators.items()})
        actual = CAPTURE.sharing_case(CopiesContext)
        sharing = next(item for item in actual["events"] if item["event"] == "sharing")
        self.assertFalse(sharing["validators_same_context"])
        self.assertEqual(actual["records"], self.frozen["cases"][0]["records"])
        self.assertNotEqual(actual, self.frozen["cases"][0])

    def test_sorted_mapping_cannot_pass_order_replay(self):
        class SortedConfiguration(CAPTURE.pipeline.PassManager):
            def run(self, pass_id, input_id, output_id, *, configuration=None):
                if configuration is not None:
                    configuration = dict(sorted(configuration.items()))
                return super().run(pass_id, input_id, output_id, configuration=configuration)
        actual = CAPTURE.sharing_case(SortedConfiguration)
        sharing = next(item for item in actual["events"] if item["event"] == "sharing")
        self.assertEqual(sharing["configuration_order"], ["alpha", "zeta"])
        self.assertNotEqual(actual, self.frozen["cases"][0])

    def test_safe_observer_never_uses_user_conversion(self):
        class UserValue:
            def to_dict(self):
                raise AssertionError("Must never be called by observer")
        with self.assertRaisesRegex(AssertionError, "Unsupported observation type"):
            CAPTURE.plain(UserValue())
        value = deepcopy(self.frozen)
        value["cases"][0]["events"][0]["target_is_supplied"] = False
        self.assertNotEqual(value, CAPTURE.capture())


def load_tests(loader, tests, pattern):
    from tools.pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, 'test_pipeline_identity_semantics')


if __name__ == "__main__":
    unittest.main()
