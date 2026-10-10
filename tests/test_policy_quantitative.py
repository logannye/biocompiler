"""Exact authoring and inert quantitative transport controls; no native proof."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler.policy import quantitative as q, component_material as public
from biocompiler import core_policy_component_material as api, core_policy_material as material, core_policy_refinement as refinement
from biocompiler.core_client import CoreProtocolError, CoreResponse, CORE_VERSION
from tests import test_policy_finite_machine as finite
from tools import generate_policy_quantitative_fixture as generator

digest = generator.shared.digest


def law():
    return q.SampledReservoir("fixture.reservoir.amount", "fixture.executor.reservoir", p.COUNT,
        p.quantity("0.5", p.COUNT), p.quantity("1.5", p.COUNT), p.quantity(1, p.COUNT), p.quantity(0, p.COUNT), p.quantity(1, p.SECOND))


def leaf(request, candidate, table):
    original = request["quantitative"]
    return {"schema_version": "biocompiler.policy_quantitative_assessment.v0.1",
        "profile": "biocompiler.policy_sampled_saturating_reservoir.v0.1", "implementation": "biocompiler.ocaml.policy_quantitative_check.v0.1",
        "outcome": "pass", "claim_scope": "exact_sampled_reservoir_under_supplied_contract", "request_fingerprint": digest(request),
        "mechanism_fingerprint": digest(original["mechanism"]), "selection": deepcopy(original["selection"]), "source": deepcopy(original["source"]),
        "bindings": {"machine_bank": "control.machine", "observation_bank": "control.evidence", "observation_input": "condition",
            "crossing_transition": "up1", "request_endpoint": {"node": "control.commit2", "port": "request0"}},
        "table": deepcopy(table), "sampling": {"sample_period": deepcopy(original["mechanism"]["sample_period"]),
            "max_rows_per_slot_tick": 1, "observed_age_ticks": 0, "no_update": "hold", "unknown": "hold_without_request",
            "reset": "initial", "reservation": "existing_atomic_reservation"}, "issues": [],
        "usage": {"unit": "logical_data_visits_and_exact_finite_table_work", "charged_work": 1000}, "empirical": "unassessed"}


def obligations(quantitative):
    """Minimal literal obligation ledger, not a complete material assessment."""
    ids = ["machine_reachability_termination_and_progress", "material_correspondence"]
    binding = {"schema_version": "biocompiler.policy_implementation_binding_report.v0.5", "profile": "biocompiler.policy_finite_machine_source_graph.v0.1",
        "source_admission": {"source_assessment": {"unresolved_obligations": ids}}}
    preservation = {"status": "checked_implementation", "binding": binding}
    report = {"preservation": preservation, "assembly": {}, "context": {}, "catalog": {}, "assembly_status": "pass", "context_status": "pass",
        "status": api.ACCEPTED_STATUS, "all_original_obligations_discharged": True, "quantitative": deepcopy(quantitative), "quantitative_status": "pass"}
    report["obligations"] = [
        {"obligation": ids[0], "status": "discharged", "stage": "bounded_machine_semantics_and_declared_requirements", "evidence": {
            "preservation": digest(preservation), "machine_binding": digest(binding), "state_and_terminal_semantics": "exact_bounded_source_correspondence",
            "prefixes": "complete_original_domain", "retained_attempt_identity": "creation_fixed_injective", "universal_termination": "not_claimed",
            "progress": "declared_requirements_only", "quantitative": digest(quantitative)}},
        {"obligation": ids[1], "status": "discharged", "stage": "conditional_component_context_conjunction", "evidence": {
            "preservation": digest(preservation), "assembly": digest({}), "context": digest({}), "quantitative": digest(quantitative)}}]
    return report


class QuantitativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def setUp(self):
        self.request = deepcopy(self.packet["request"])
        self.candidate = finite.inert_candidate({"request": self.request, "expected": self.packet["expected"]})
        self.document = p.from_data(self.request["implementation_request"]["document"], p.BuildRequest)
        self.machine = next(row for row in self.document.program.declarations if isinstance(row, p.Machine))
        self.observation = next(row for row in self.document.program.declarations if isinstance(row, p.Observation))
        self.effect = next(row for row in self.document.program.declarations if isinstance(row, p.Effect))
        self.leaf = leaf(self.request, self.candidate, self.packet["expected"]["table"])

    def validate_leaf(self, value):
        api._quantitative_evidence(self.request, self.candidate,
            {"quantitative": value, "quantitative_status": value["outcome"],
             "status": api.ACCEPTED_STATUS if value["outcome"] == "pass" else "not_accepted"})

    def test_independent_fixture_is_deterministic_bounded_and_source_complete(self):
        self.assertEqual(generator.build(), self.packet)
        self.assertLess(generator.PATH.stat().st_size, 1_000_000)
        self.assertEqual(p.check(self.document).status, "complete")
        self.assertEqual(p.to_data(self.document), self.request["implementation_request"]["document"])
        self.assertEqual(len(self.packet["expected"]["table"]), 12)
        self.assertEqual(self.packet["expected"]["sequence"], "CCAUGGCUUAAGGAAAA")
        domain = self.request["implementation_request"]["operating_domain"]
        self.assertEqual(domain["horizon_ticks"], 15)
        self.assertEqual(domain["lifecycle_factors"], [{"slots": ["e1", "e2"], "ticks": [13], "actions": ["keep", "reset"]}])
        self.assertEqual([row["status"] for row in domain["fixed_observations"] if row["available_tick"] == 3], ["missing", "missing"])
        self.assertFalse(any(row["available_tick"] == 6 for row in domain["fixed_observations"]))
        self.assertTrue(all(row["available_tick"] == row["observed_tick"] for row in domain["fixed_observations"]))
        nodes = self.packet["expected"]["ordered_union"]["nodes"]
        self.assertEqual(len(nodes), 22)
        self.assertNotIn("truth_constant", [row["model"]["body"]["primitive"] for row in nodes])
        self.assertEqual(sum(row["model"]["body"]["primitive"] == "truth_not" for row in nodes), 1)
        self.assertEqual(self.packet["limits"]["candidate"]["max_work"], 10_000_000)
        self.assertEqual(hashlib.sha256((generator.ROOT / "core/test/data/policy_finite_machine_v01.json").read_bytes()).hexdigest(),
                         "908215f91399c59f9bed2da6e74c6fc87526fd3e9e110e550928a44058636d16")

    def test_exact_law_and_grid_ignore_decimal_context_and_do_not_extend_source_records(self):
        value = law()
        self.assertEqual(value.to_data(), self.request["quantitative"]["mechanism"])
        with localcontext() as context:
            context.prec = 1
            tiny = replace(value, quantum=p.quantity("0.123456789123456789", p.COUNT),
                capacity=p.quantity("0.370370367370370367", p.COUNT), threshold=p.quantity("0.246913578246913578", p.COUNT))
            self.assertEqual([row.amount for row in tiny.levels], ["0", "0.123456789123456789", "0.246913578246913578", "0.370370367370370367"])
        self.assertFalse(isinstance(value, p.Record))
        self.assertNotIn("SampledReservoir", p.schema()["$defs"])
        self.assertEqual(value.state_values(self.machine.states), self.request["component_library"]["components"][0]["body"]["quantitative_contracts"][0]["state"]["values"])
        with self.assertRaises(FrozenInstanceError):
            value.substance = "changed"
        value.to_data()["unit"]["id"] = "changed"
        self.assertEqual(value.unit, p.COUNT)

    def test_nominal_units_exact_grid_bounds_and_float_inputs_reject(self):
        value = law()
        mutations = [{"quantum": p.quantity(0, p.COUNT)}, {"capacity": p.quantity(8, p.COUNT)},
            {"threshold": p.quantity("0.75", p.COUNT)}, {"initial": p.quantity(-1, p.COUNT)},
            {"initial": p.quantity("0.25", p.COUNT)}, {"sample_period": p.quantity(0, p.SECOND)},
            {"sample_period": p.quantity(1, replace(p.SECOND, reference="other"))},
            {"quantum": p.quantity("0.5", replace(p.COUNT, id="other"))},
            {"capacity": p.quantity("1.5", replace(p.COUNT, scale="2"))},
            {"threshold": p.quantity(1, replace(p.COUNT, reference="other"))},
            {"unit": p.DIMENSIONLESS}, {"quantum": 0.5}, {"substance": ""}, {"compartment": "x" * 257}]
        for fields in mutations:
            with self.subTest(fields=fields), self.assertRaises((q.QuantitativeAuthoringError, TypeError, ValueError)):
                replace(value, **fields)
        with self.assertRaises(TypeError):
            p.quantity(0.5, p.COUNT)
        for states in (("q0",), ("q0",) * 4, list(self.machine.states)):
            with self.assertRaises(q.QuantitativeAuthoringError):
                value.state_values(states)

    def test_transition_expansion_matches_independently_authored_source(self):
        actual = law().transitions(self.machine, self.observation, self.effect, prefix="reservoir")
        expected = tuple(replace(row, id="reservoir/" + row.id) for row in self.document.program.declarations if isinstance(row, p.Transition))
        self.assertEqual([p.to_data(row) for row in actual], [p.to_data(row) for row in expected])
        self.assertEqual([row.id for row in actual if row.effects], ["reservoir/up1"])
        self.assertEqual(actual[1].source, actual[1].destination)
        self.assertEqual(actual[6].source, actual[6].destination)
        self.assertTrue(all(row.on.op == "updated" and row.unknown == "defer" for row in actual))
        for machine, observation, effect in ((replace(self.machine, initial="q1"), self.observation, self.effect),
                (replace(self.machine, terminal=("q3",)), self.observation, self.effect),
                (self.machine, replace(self.observation, freshness=p.quantity(0, p.SECOND)), self.effect),
                (self.machine, self.observation, replace(self.effect, subject=p.Ref("other", "Subject"))),
                (self.effect, self.observation, self.machine)):
            with self.subTest(machine=machine), self.assertRaises(q.QuantitativeAuthoringError):
                law().transitions(machine, observation, effect, prefix="reservoir")

    def test_binding_snapshots_original_law_selected_full_pin_and_nominal_source(self):
        component = deepcopy(self.request["quantitative"]["selection"]["component"])
        value = law().bind(instance="control", component=component, contract="reservoir", machine=self.machine,
                           observation=self.observation, effect=self.effect)
        self.assertEqual(value, self.request["quantitative"])
        component["content_fingerprint"] = "0" * 64
        self.assertNotEqual(value["selection"]["component"], component)
        prepared = public.prepare_request(**{key: val for key, val in self.request.items() if key not in ("schema_version", "profile")},
            instanced=True, prerequisites=True, finite_machine=True)
        self.assertEqual(prepared, self.request)
        self.request["quantitative"]["mechanism"]["substance"] = "different original"
        self.assertNotEqual(prepared, self.request)

    def test_new_profile_is_explicit_and_quantitative_components_reject_on_legacy_route(self):
        self.assertEqual(api._original(self.request), self.request)
        self.assertEqual(api._profile_settings(self.request)[0], "policy_quantitative_material")
        legacy = deepcopy(self.request)
        legacy.pop("quantitative")
        legacy.update(schema_version=api.FINITE_MACHINE_REQUEST_SCHEMA, profile=api.FINITE_MACHINE_REQUEST_PROFILE)
        with self.assertRaises(CoreProtocolError):
            api._original(legacy)
        for schema, profile in ((api.FINITE_MACHINE_REQUEST_SCHEMA, api.QUANTITATIVE_REQUEST_PROFILE),
                                (api.QUANTITATIVE_REQUEST_SCHEMA, api.FINITE_MACHINE_REQUEST_PROFILE)):
            with self.assertRaises(CoreProtocolError):
                api._original(self.request | {"schema_version": schema, "profile": profile})
        fields = {key: val for key, val in self.request.items() if key not in ("schema_version", "profile")}
        with self.assertRaises(ValueError):
            public.prepare_request(**fields, instanced=True, prerequisites=True)

    def test_all_four_routes_negotiate_quantitative_profile_and_snapshot_originals(self):
        calls = []
        transport = SimpleNamespace(role="core")
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_quantitative_material": deepcopy(api.QUANTITATIVE_PROFILE),
                      "policy_quantitative_material_producer": deepcopy(api.QUANTITATIVE_PRODUCER_PROFILE)},
            validation_scopes=[api.QUANTITATIVE_VALIDATION_SCOPE])
        def call(operation, payload, cancelled=None):
            calls.append((operation, deepcopy(payload)))
            return CoreResponse("inert-quantitative-route", operation, "ok", None, (), "core", CORE_VERSION)
        transport.call = call
        client = api.PolicyComponentMaterialClient(transport)
        with patch.object(api, "_result", side_effect=lambda response, payload: payload):
            client.compile(self.request, self.packet["limits"])
            client.check(self.request, self.candidate, self.packet["limits"])
            client.replay(self.request, self.candidate, self.packet["limits"], {"saved": "untrusted"})
            client.export(self.request, self.candidate, self.packet["limits"])
        self.assertEqual([row[0] for row in calls], ["compile-policy-component-material", "check-policy-component-material",
            "replay-policy-component-material", "export-policy-component-material"])
        self.assertTrue(all(row[1]["request"] == self.request for row in calls))
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_finite_machine_material": api.FINITE_MACHINE_PROFILE}, validation_scopes=[api.FINITE_MACHINE_VALIDATION_SCOPE])
        with self.assertRaises(CoreProtocolError):
            client.check(self.request, self.candidate, self.packet["limits"])
        self.assertEqual(len(calls), 4)

    def test_quantitative_report_profile_fields_do_not_widen_legacy_shapes(self):
        raw = {key: None for key in api._REPORT_FIELDS | {"prerequisites", "prerequisite_status", "quantitative", "quantitative_status"}}
        raw.update(schema_version="biocompiler.policy_component_material_assessment.v0.5", profile=api.QUANTITATIVE_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.8", resource_profile=api.RESOURCE_PROFILE,
            claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE, empirical="unassessed", artifact="withheld", export="withheld")
        self.assertEqual(api._report(raw, instanced=True, prerequisites=True, finite_machine=True, quantitative=True), raw)
        with self.assertRaises(CoreProtocolError):
            api._report(raw, instanced=True, prerequisites=True, finite_machine=True)
        with self.assertRaises(CoreProtocolError):
            api._report(raw, instanced=True, prerequisites=True, quantitative=True)

    def test_quantitative_leaf_retains_all_original_bindings_and_source_table(self):
        self.validate_leaf(self.leaf)
        self.assertEqual(self.leaf["table"], self.packet["expected"]["table"])
        self.assertEqual(self.leaf["table"][3], {"source": "q1", "input": "true", "destination": "q2", "request": True})
        self.assertEqual(self.leaf["table"][11], {"source": "q3", "input": "unknown", "destination": "q3", "request": False})

    def test_quantitative_leaf_rejects_identity_sampling_table_and_bound_tampering(self):
        mutations = [lambda row: row.update(request_fingerprint="0" * 64), lambda row: row.update(mechanism_fingerprint="0" * 64),
            lambda row: row["selection"].update(instance="other"), lambda row: row["source"].update(machine="other"),
            lambda row: row["bindings"].update(crossing_transition="up0"), lambda row: row["bindings"]["request_endpoint"].update(port="request1"),
            lambda row: row["table"].reverse(), lambda row: row["table"].pop(), lambda row: row["table"][0].update(destination="q3"),
            lambda row: row["table"][2].update(request=True), lambda row: row["sampling"].update(max_rows_per_slot_tick=2),
            lambda row: row["sampling"].update(max_rows_per_slot_tick=True), lambda row: row["sampling"].update(observed_age_ticks=1),
            lambda row: row["sampling"].update(unknown="degrade"), lambda row: row["sampling"].update(no_update="decay"),
            lambda row: row["sampling"]["sample_period"].update(amount="2"), lambda row: row.update(empirical="validated"),
            lambda row: row["usage"].update(charged_work=500000001), lambda row: row["usage"].update(charged_work=True),
            lambda row: row.update(issues=["unresolved"]), lambda row: row.update(artifact={})]
        for mutate in mutations:
            value = deepcopy(self.leaf)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(CoreProtocolError):
                self.validate_leaf(value)

    def test_unassessed_or_failed_quantitative_stage_cannot_mint_material_acceptance(self):
        api._quantitative_evidence(self.request, self.candidate, {"status": "not_accepted", "quantitative": None, "quantitative_status": "unassessed"})
        with self.assertRaises(CoreProtocolError):
            api._quantitative_evidence(self.request, self.candidate, {"status": api.ACCEPTED_STATUS, "quantitative": None, "quantitative_status": "unassessed"})
        failed = deepcopy(self.leaf)
        failed.update(outcome="fail", bindings=None, table=[], issues=["exact_saturating_law_and_unique_crossing_request"])
        self.validate_leaf(failed)
        for field, value in (("bindings", self.leaf["bindings"]), ("table", self.leaf["table"]), ("issues", [])):
            with self.assertRaises(CoreProtocolError):
                self.validate_leaf(failed | {field: value})

    def test_every_discharged_obligation_pins_quantitative_including_machine_special_case(self):
        def validate(report):
            material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
                conjunction_stage="conditional_component_context_conjunction", finite_machine=True, quantitative_key="quantitative")
        original = obligations(self.leaf)
        validate(original)
        for index in range(2):
            for remove in (False, True):
                value = deepcopy(original)
                evidence = value["obligations"][index]["evidence"]
                if remove:
                    evidence.pop("quantitative")
                else:
                    evidence["quantitative"] = "0" * 64
                with self.subTest(index=index, remove=remove), self.assertRaises(CoreProtocolError):
                    validate(value)
        failed = deepcopy(original)
        failed["quantitative"]["outcome"] = "fail"
        failed.update(quantitative_status="fail", status="not_accepted", all_original_obligations_discharged=False)
        with self.assertRaises(CoreProtocolError):
            validate(failed)
        for row in failed["obligations"]:
            row.update(status="unresolved", stage=None, evidence=None)
        validate(failed)

    def test_named_refinement_dispatch_retains_quantitative_flag_without_new_relation_claims(self):
        report = {"status": "not_accepted"}
        payload = {"request": self.request, "candidate": self.candidate, "limits": self.packet["limits"]}
        result = {"schema_version": refinement.RESULT_SCHEMA, "implementation": refinement.IMPLEMENTATION,
            "validation_scope": refinement.VALIDATION_SCOPE, "request_fingerprint": digest(self.request), "candidate_fingerprint": digest(self.candidate),
            "invocation_fingerprint": digest(payload), "material_report_fingerprint": digest(report), "material_report": report, "evidence": None}
        response = CoreResponse("inert-quantitative", "check-policy-refinement", "ok", result, (), "verify", CORE_VERSION)
        with (patch.object(api, "_candidate", return_value=self.candidate), patch.object(api, "_report", return_value=report) as parse,
                patch.object(api, "_assessment")):
            checked = refinement._result(response, payload)
        self.assertTrue(parse.call_args.kwargs["quantitative"])
        self.assertTrue(parse.call_args.kwargs["finite_machine"])
        self.assertIsNone(checked.evidence)
        self.assertEqual(len(refinement._RELATIONS), 10)
        self.assertEqual(len(refinement._PREMISES), 18)


if __name__ == "__main__":
    unittest.main()
