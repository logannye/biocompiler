"""Inert original-edit and routing checks; no native activity or RNA execution."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from biocompiler.core_client import CoreProtocolError, encode_json
from biocompiler.policy.controlled_behavior import ControlledBehaviorRequest
from biocompiler.policy import controlled_workflow as api

ROOT = Path(__file__).resolve().parents[1]


def behavior():
    return json.loads((ROOT / "core/test/data/policy_controlled_behavior_v01.json").read_text())


def request():
    return api.ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(behavior()))


class ControlledWorkflowTests(unittest.TestCase):
    def setUp(self):
        guard = patch("subprocess.Popen", side_effect=AssertionError("No native subprocess in inert tests"))
        guard.start()
        self.addCleanup(guard.stop)

    def test_complete_snapshot_limits_and_reopened_behavior_are_detached(self):
        raw = behavior()
        build = api.ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(raw))
        expected = build.to_request()
        self.assertEqual(build.behavior.to_request(), raw)
        self.assertEqual(build.native_status, "not_performed")
        self.assertEqual(build.sha256, hashlib.sha256(encode_json(expected)).hexdigest())
        raw.clear()
        build.to_request().clear()
        build.limits.clear()
        self.assertEqual(build.to_request(), expected)
        self.assertEqual(api.ControlledWorkflowRequest.from_request(expected).to_request(), expected)
        with self.assertRaises(FrozenInstanceError):
            build._json = b"{}"
        with self.assertRaises(CoreProtocolError):
            api.ControlledWorkflowRequest.from_behavior(behavior())

    def test_every_limits_projection_field_and_closed_shape_are_checked(self):
        raw = request().to_request()
        changes = {"schema_version": "foreign", "budgets": {}, "domain_limits": {},
                   "horizon_tick": 9, "intervention_cutoff_tick": 4, "resources": {}}
        for key, value in changes.items():
            changed = deepcopy(raw)
            changed["limits"][key] = value
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api.ControlledWorkflowRequest.from_request(changed)
        for changed in ({**raw, "cached_pass": True}, {**raw, "schema_version": "foreign"},
                        {key: value for key, value in raw.items() if key != "limits"}):
            with self.assertRaises(CoreProtocolError):
                api.ControlledWorkflowRequest.from_request(changed)

    def test_rna_limit_edits_do_not_change_material_or_mechanism(self):
        original = request()
        edited = original.with_rna_limits(max_member_rna_nt=16, max_total_rna_nt=33)
        changed = edited.to_request()
        expected = original.to_request()
        expected["behavior_request"]["original"]["resources"].update(max_member_rna_nt=16, max_total_rna_nt=33)
        expected["limits"]["resources"].update(max_member_rna_nt=16, max_total_rna_nt=33)
        self.assertEqual(changed, expected)
        self.assertNotEqual(edited.sha256, original.sha256)
        for bad in (True, 0, -1, 1.5):
            with self.subTest(value=bad), self.assertRaises((ValueError, CoreProtocolError)):
                original.with_rna_limits(max_member_rna_nt=bad, max_total_rna_nt=34)

    def test_all_deadline_edits_change_source_and_domain_without_rewriting_actual_model(self):
        original = request()
        values = dict(onset_ticks=1, controller_off_ticks=3, antigen_off_ticks=4,
                      component_off_ticks=5, reactivation_ticks=6)
        changed = original.with_deadlines(**values).to_request()
        raw = changed["behavior_request"]["original"]
        self.assertEqual(raw["operating_domain"]["source_deadlines"], values)
        self.assertEqual(raw["source_authority"]["control_contract"]["requested_deadlines"], values)
        kinds = {"onset": 1, "controller-off": 3, "antigen-off": 4, "component-off": 5, "reactivation": 6}
        for row in raw["source_authority"]["document"]["program"]["declarations"]:
            if row["id"] in kinds:
                self.assertEqual(row["deadline"]["amount"], str(kinds[row["id"]]))
                row["deadline"]["amount"] = "2"
        raw["operating_domain"]["source_deadlines"] = {key: 2 for key in values}
        raw["source_authority"]["control_contract"]["requested_deadlines"] = {key: 2 for key in values}
        self.assertEqual(changed, original.to_request())
        for bad in (0, True, 1.5, 10001):
            with self.subTest(value=bad), self.assertRaises((ValueError, CoreProtocolError)):
                original.with_deadlines(onset_ticks=bad)
        divergent = original.behavior.to_request()
        divergent["original"]["operating_domain"]["source_deadlines"]["controller_off_ticks"] = 7
        build = api.ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(divergent))
        edited = build.with_deadlines(onset_ticks=1).behavior.to_request()["original"]
        self.assertEqual(edited["operating_domain"]["source_deadlines"]["controller_off_ticks"], 7)
        self.assertEqual(edited["source_authority"]["control_contract"]["requested_deadlines"]["controller_off_ticks"], 2)

    def test_edited_durations_use_exact_original_clock_units_and_unambiguous_contracts(self):
        raw = behavior()
        raw["original"]["operating_domain"]["clock"]["resolution"]["amount"] = "0.25"
        build = api.ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(raw))
        changed = build.with_deadlines(onset_ticks=3).behavior.to_request()
        row = next(row for row in changed["original"]["source_authority"]["document"]["program"]["declarations"] if row["id"] == "onset")
        self.assertEqual(row["deadline"]["amount"], "0.75")
        # Editing is representation work; malformed source authority remains
        # rejectable rather than silently rewriting an unrelated requirement.
        source = raw["original"]["source_authority"]["document"]["program"]
        source["declarations"] = [row for row in source["declarations"] if row["id"] != "onset"]
        build = api.ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(raw))
        with self.assertRaisesRegex(CoreProtocolError, "lacks"):
            build.with_deadlines(onset_ticks=3)

    def test_horizon_edits_require_original_evidence_and_do_not_prune_domain(self):
        original = request()
        raw = original.behavior.to_request()
        evidence = deepcopy(raw["readout_evidence"])
        evidence["samples"] = evidence["samples"][:10]
        changed = original.with_horizon(9, readout_evidence=evidence)
        new = changed.behavior.to_request()["original"]
        self.assertEqual(new["operating_domain"]["fixed_inputs"], raw["original"]["operating_domain"]["fixed_inputs"])
        self.assertEqual(new["source_authority"]["document"]["assurance"]["horizon"]["amount"], "9")
        self.assertTrue(all(row["horizon"]["amount"] == "9" for row in new["source_authority"]["document"]["program"]["declarations"] if row["$type"] == "Requirement"))
        domain = deepcopy(new["operating_domain"])
        domain["fixed_inputs"] = [row for row in domain["fixed_inputs"] if row["tick"] <= 9]
        explicit = original.with_horizon(9, readout_evidence=evidence, operating_domain=domain)
        self.assertEqual(explicit.behavior.to_request()["original"]["operating_domain"], domain)
        evidence.clear(); domain.clear()
        self.assertEqual(len(explicit.behavior.to_request()["readout_evidence"]["samples"]), 10)
        with self.assertRaises(CoreProtocolError):
            original.with_horizon(9, readout_evidence=raw["readout_evidence"])
        with self.assertRaises(CoreProtocolError):
            original.with_horizon(9, readout_evidence=raw["readout_evidence"], operating_domain=raw["original"]["operating_domain"])

    def test_full_material_edits_preserve_model_and_expected_product_authority(self):
        original = request()
        authority = original.behavior.original.to_request()["material_authority"]
        authority["template"]["sources"][0]["molecule"]["provenance"]["reason"] = "Explicit revised independent material declaration."
        changed = original.with_material_authority(authority)
        expected = original.to_request()
        expected["behavior_request"]["original"]["material_authority"] = deepcopy(authority)
        self.assertEqual(changed.to_request(), expected)
        self.assertNotEqual(changed.sha256, original.sha256)
        authority.clear()
        self.assertEqual(changed.to_request(), expected)
        with self.assertRaises((ValueError, CoreProtocolError)):
            original.with_material_authority({})

    def test_public_wrappers_forward_complete_originals_candidate_report_and_cancellation(self):
        build = request(); client = Mock(); stop = lambda: False
        candidate = {"complete": "candidate"}; report = {"complete": "report"}
        self.assertIs(api.compile(build, client=client, cancelled=stop), client.compile.return_value)
        self.assertIs(api.check(build, candidate=candidate, client=client, cancelled=stop), client.check.return_value)
        self.assertIs(api.replay(build, candidate=candidate, report=report, client=client, cancelled=stop), client.replay.return_value)
        client.compile.assert_called_once_with(build.to_request(), cancelled=stop)
        client.check.assert_called_once_with(build.to_request(), candidate, cancelled=stop)
        client.replay.assert_called_once_with(build.to_request(), candidate, report, cancelled=stop)
