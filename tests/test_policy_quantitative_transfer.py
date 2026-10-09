"""Independent transfer-pair premises and inert Python transport; no native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler import core_policy_component_material as api, core_policy_refinement as refinement
from biocompiler.core_client import CoreProtocolError, CoreResponse, CORE_VERSION
from biocompiler.policy import quantitative as q, component_material as public
from tests import test_policy_quantitative_step as step, test_policy_quantitative as legacy
from tools import generate_policy_quantitative_transfer_fixture as generator


def law():
    return q.SampledTransferPair(substance="fixture.reservoir.amount", unit=p.COUNT, quantum=p.quantity(1, p.COUNT),
        source=q.ReservoirCompartment("fixture.executor.source", p.quantity(2, p.COUNT), p.quantity(2, p.COUNT)),
        destination=q.ReservoirCompartment("fixture.executor.destination", p.quantity(2, p.COUNT), p.quantity(0, p.COUNT)),
        forward=p.quantity(2, p.COUNT), reverse=p.quantity(1, p.COUNT), threshold=p.quantity(2, p.COUNT), sample_period=p.quantity(1, p.SECOND))


def leaf(request, actual, table):
    value = legacy.leaf(request, actual, table)
    value.update(schema_version="biocompiler.policy_quantitative_assessment.v0.3",
        profile="biocompiler.policy_sampled_conservative_transfer_pair.v0.1",
        implementation="biocompiler.ocaml.policy_quantitative_check.v0.3",
        claim_scope="exact_sampled_conservative_transfer_pair_under_supplied_contract",
        conservation={"scope": "accepted_samples_within_encounter_generation", "quantity": "source_plus_destination",
                      "reset": "restore_declared_initial_pair", "checked_rows": 27})
    nodes = {node["id"]: node["model"] for node in actual["implementation"]["nodes"]}
    value["bindings"] = {"machine_bank": "control.machine", "observation_bank": "control.evidence", "observation_input": "condition",
        "attempt_bank": "actuator.response", "crossing_sites": [
            {"transition": transition, "source_state": state, "input": True,
             "request_endpoint": {"node": "control." + commit, "port": "request0"}, "model": nodes["control." + commit],
             "attempt_port": "request" + str(site)} for site, (transition, state, commit) in enumerate(
                 (("forward4", "q11", "commit3"), ("forward6", "q20", "commit6"), ("forward7", "q21", "commit7")))]}
    return value


class TransferQuantitativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def setUp(self):
        self.request = deepcopy(self.packet["request"])
        self.candidate = step.candidate(self.packet)
        self.document = p.from_data(self.request["implementation_request"]["document"], p.BuildRequest)
        self.machine = next(row for row in self.document.program.declarations if isinstance(row, p.Machine))
        self.observation = next(row for row in self.document.program.declarations if isinstance(row, p.Observation))
        self.effect = next(row for row in self.document.program.declarations if isinstance(row, p.Effect))
        self.leaf = leaf(self.request, self.candidate, self.packet["expected"]["table"])

    def validate_leaf(self, value):
        api._quantitative_evidence(self.request, self.candidate,
            {"quantitative": value, "quantitative_status": value["outcome"],
             "status": api.ACCEPTED_STATUS if value["outcome"] == "pass" else "not_accepted"})

    def test_fixture_independent_original_pins_and_bounded_execution_premises(self):
        self.assertEqual(generator.build(), self.packet)
        self.assertEqual(p.check(self.document).status, "complete")
        domain = self.request["implementation_request"]["operating_domain"]
        self.assertEqual(domain["horizon_ticks"], 12)
        self.assertGreater(self.packet["limits"]["source"]["max_ticks"], domain["horizon_ticks"])
        self.assertEqual(self.packet["limits"]["candidate"]["max_work"], 10_000_000)
        self.assertGreaterEqual(domain["logical_limits"]["max_source_attempts"], 3 * len(domain["encounters"]))
        self.assertEqual(domain["lifecycle_factors"], [{"slots": ["e1", "e2"], "ticks": [7], "actions": ["keep", "reset"]}])
        self.assertEqual(len(self.packet["expected"]["keep_trajectory"]), 13)
        self.assertEqual(len(self.packet["expected"]["reset_trajectory"]), 13)
        self.assertEqual(self.packet["expected"]["molecule"]["sequence"], "CCAUGGCUUAAGGAAAA")
        for component in self.request["component_library"]["components"]:
            self.assertEqual(generator.shared.digest(component["body"]), component["identity"]["content_fingerprint"])
        rule = self.request["composition_rule"]
        self.assertEqual(generator.shared.digest(rule["body"]), rule["identity"]["content_fingerprint"])
        self.assertEqual(generator.shared.digest(self.packet["expected"]["ordered_union"]), self.request["context"]["record_layout"]["union_digest"])
        for provider in self.request["context"]["providers"]:
            self.assertEqual(generator.shared.digest(provider["body"]), provider["identity"]["content_fingerprint"])
        bank = next(row for row in self.request["implementation_request"]["implementation_library"]["models"] if row["body"]["primitive"] == "attempt_bank_sites")
        self.assertEqual((bank["body"]["configuration"]["sites"], bank["body"]["configuration"]["capacity"]), (3, 6))
        self.assertEqual(self.request["context"]["record_layout"]["attempts"], 6)

    def test_sparse_expansion_matches_independent_source_and_complete_table(self):
        value = law()
        self.assertEqual(value.to_data(), self.request["quantitative"]["mechanism"])
        transitions = value.transitions(self.machine, self.observation, self.effect, prefix="pair")
        self.assertEqual(transitions, tuple(replace(row, id="pair/" + row.id) for row in self.document.program.declarations if isinstance(row, p.Transition)))
        self.assertEqual(len(transitions), 8)
        self.assertEqual([(row.source, row.destination) for row in transitions if row.effects], [("q11", "q02"), ("q20", "q02"), ("q21", "q12")])
        table = self.packet["expected"]["table"]
        self.assertEqual(len(table), 27)
        for row in table:
            self.assertEqual(sum(row["before"]), sum(row["after"]))
        self.assertEqual(table[18], {"source": "q20", "input": "true", "destination": "q02", "request": True,
                                     "before": [2, 0], "after": [0, 2], "transfer_quanta": 2})
        self.assertFalse(isinstance(value, p.Record))
        self.assertNotIn("SampledTransferPair", p.schema()["$defs"])
        with self.assertRaises(FrozenInstanceError): value.forward = p.quantity(1, p.COUNT)

    def test_maximal_four_by_four_shape_uses_saturation_and_sparse_stuttering(self):
        value = replace(law(), source=replace(law().source, capacity=p.quantity(3, p.COUNT), initial=p.quantity(3, p.COUNT)),
            destination=replace(law().destination, capacity=p.quantity(3, p.COUNT)), forward=p.quantity(3, p.COUNT),
            reverse=p.quantity(2, p.COUNT), threshold=p.quantity(2, p.COUNT))
        machine = replace(self.machine, states=tuple("s" + str(i) for i in range(16)), initial="s12")
        transitions = value.transitions(machine, self.observation, self.effect, prefix="max")
        self.assertEqual(len(value.levels), 16)
        self.assertEqual(len(transitions), 18)
        self.assertEqual([(row.source, row.destination) for row in transitions if row.effects],
                         [("s5", "s2"), ("s8", "s2"), ("s9", "s3"), ("s12", "s3"), ("s13", "s7")])
        by_id = {row.id: row for row in transitions}
        self.assertEqual(by_id["max/reverse2"].destination, "s8")
        self.assertEqual(by_id["max/reverse7"].destination, "s13")
        self.assertNotIn("max/forward15", by_id)
        self.assertNotIn("max/reverse12", by_id)

    def test_exact_fractional_grid_ignores_ambient_decimal_context(self):
        with localcontext() as context:
            context.prec = 1
            unit = p.COUNT
            quantum = p.quantity("0.123456789123456789", unit)
            double = p.quantity("0.246913578246913578", unit)
            value = replace(law(), quantum=quantum, source=replace(law().source, capacity=double, initial=double),
                destination=replace(law().destination, capacity=double), forward=double, reverse=quantum, threshold=double)
            self.assertEqual(value.levels[5][0].amount, "0.123456789123456789")
            self.assertEqual(value.levels[5][1].amount, "0.246913578246913578")
            self.assertEqual(len(value.transitions(self.machine, self.observation, self.effect, prefix="exact")), 8)

    def test_rejects_aliasing_units_inexact_grids_and_product_overflow(self):
        value = law()
        for changes in ({"destination": replace(value.destination, compartment=value.source.compartment)},
                {"forward": p.quantity(0, p.COUNT)}, {"reverse": p.quantity(3, p.COUNT)},
                {"forward": p.quantity("0.5", p.COUNT)}, {"threshold": p.quantity(1, replace(p.COUNT, id="other"))},
                {"source": replace(value.source, capacity=p.quantity(5, p.COUNT))}, {"source": "source"}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)): replace(value, **changes)
        for changes in ({"capacity": p.quantity(0, p.COUNT)}, {"initial": p.quantity(3, p.COUNT)},
                        {"initial": p.quantity(0, p.SECOND)}):
            with self.assertRaises((TypeError, ValueError)): replace(value.source, **changes)
        with self.assertRaises(ValueError): value.state_values(("same",) * 9)
        with self.assertRaises(ValueError): value.transitions(replace(self.machine, initial="q00"), self.observation, self.effect, prefix="bad")

    def test_original_authority_snapshot_and_explicit_profile_routing(self):
        fields = {key: val for key, val in self.request.items() if key not in ("schema_version", "profile")}
        prepared = public.prepare_request(**fields, instanced=True, prerequisites=True, finite_machine=True, multi_site=True, transfer_pair=True)
        self.assertEqual(prepared, self.request)
        self.assertEqual(law().bind(instance="control", component=self.request["quantitative"]["selection"]["component"], contract="transfer",
                         machine=self.machine, observation=self.observation, effect=self.effect), self.request["quantitative"])
        self.request["quantitative"]["mechanism"]["forward"]["amount"] = "1"
        self.assertNotEqual(prepared, self.request)
        with self.assertRaises(ValueError): public.prepare_request(**fields, instanced=True, prerequisites=True, finite_machine=True, transfer_pair=True)
        for schema, profile in ((api.STEP_QUANTITATIVE_REQUEST_SCHEMA, api.TRANSFER_PAIR_REQUEST_PROFILE),
                                (api.TRANSFER_PAIR_REQUEST_SCHEMA, api.STEP_QUANTITATIVE_REQUEST_PROFILE)):
            with self.assertRaises(CoreProtocolError): api._original(prepared | {"schema_version": schema, "profile": profile})
        old = deepcopy(prepared); old["quantitative"]["mechanism"] = step.law().to_data()
        with self.assertRaises(CoreProtocolError): api._original(old)

    def test_all_routes_negotiate_transfer_profile_without_fallback(self):
        calls = []
        transport = SimpleNamespace(role="core")
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_transfer_pair_material": deepcopy(api.TRANSFER_PAIR_PROFILE),
                      "policy_transfer_pair_material_producer": deepcopy(api.TRANSFER_PAIR_PRODUCER_PROFILE)},
            validation_scopes=[api.TRANSFER_PAIR_VALIDATION_SCOPE])
        transport.call = lambda operation, payload, cancelled=None: calls.append((operation, deepcopy(payload)))
        client = api.PolicyComponentMaterialClient(transport)
        with patch.object(api, "_result", side_effect=lambda response, payload: payload):
            client.compile(self.request, self.packet["limits"])
            client.check(self.request, self.candidate, self.packet["limits"])
            client.replay(self.request, self.candidate, self.packet["limits"], {"saved": "untrusted"})
            client.export(self.request, self.candidate, self.packet["limits"])
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(row[1]["request"] == self.request for row in calls))
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_step_quantitative_material": api.STEP_QUANTITATIVE_PROFILE}, validation_scopes=[api.STEP_QUANTITATIVE_VALIDATION_SCOPE])
        with self.assertRaises(CoreProtocolError): client.check(self.request, self.candidate, self.packet["limits"])
        self.assertEqual(len(calls), 4)

    def test_leaf_preserves_conservation_sparse_holds_and_complete_site_inventory(self):
        self.validate_leaf(self.leaf)
        mutations = [lambda row: row["conservation"].update(checked_rows=8), lambda row: row.update(conservation=None),
            lambda row: row["conservation"].update(scope="including_resets"), lambda row: row["table"][0].update(after=[1, 0]),
            lambda row: row["table"][18].update(transfer_quanta=1), lambda row: row["table"][0].update(request=True),
            lambda row: row["bindings"]["crossing_sites"].pop(), lambda row: row["bindings"]["crossing_sites"].reverse(),
            lambda row: row["bindings"]["crossing_sites"][0].update(attempt_port="request1"),
            lambda row: row.update(schema_version="biocompiler.policy_quantitative_assessment.v0.2"),
            lambda row: row.update(claim_scope="unbounded_mass_conservation"), lambda row: row["table"].pop()]
        for change in mutations:
            mutated = deepcopy(self.leaf); change(mutated)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError): self.validate_leaf(mutated)

    def test_failing_leaf_withholds_conservation_and_complete_table(self):
        failed = deepcopy(self.leaf); failed.update(outcome="fail", bindings=None, conservation=None, table=[], issues=["law_mismatch"])
        self.validate_leaf(failed)
        for changes in ({"conservation": self.leaf["conservation"]}, {"table": self.leaf["table"]}, {"bindings": self.leaf["bindings"]}):
            with self.assertRaises(CoreProtocolError): self.validate_leaf(failed | changes)

    def test_new_material_report_and_named_refinement_retain_profile(self):
        raw = {key: None for key in api._REPORT_FIELDS | {"prerequisites", "prerequisite_status", "quantitative", "quantitative_status"}}
        raw.update(schema_version="biocompiler.policy_component_material_assessment.v0.7", profile=api.TRANSFER_PAIR_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.11", resource_profile=api.RESOURCE_PROFILE,
            claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE, empirical="unassessed", artifact="withheld", export="withheld")
        flags = dict(instanced=True, prerequisites=True, finite_machine=True, quantitative=True, multi_site=True, transfer_pair=True)
        self.assertEqual(api._report(raw, **flags), raw)
        with self.assertRaises(CoreProtocolError): api._report(raw, **(flags | {"transfer_pair": False}))
        report = {"status": "not_accepted"}
        payload = {"request": self.request, "candidate": self.candidate, "limits": self.packet["limits"]}
        result = {"schema_version": refinement.RESULT_SCHEMA, "implementation": refinement.IMPLEMENTATION,
            "validation_scope": refinement.VALIDATION_SCOPE, "request_fingerprint": generator.shared.digest(self.request),
            "candidate_fingerprint": generator.shared.digest(self.candidate), "invocation_fingerprint": generator.shared.digest(payload),
            "material_report_fingerprint": generator.shared.digest(report), "material_report": report, "evidence": None}
        response = CoreResponse("inert-transfer-refinement", "check-policy-refinement", "ok", result, (), "verify", CORE_VERSION)
        with (patch.object(api, "_candidate", return_value=self.candidate), patch.object(api, "_report", return_value=report) as parse_report,
              patch.object(api, "_assessment")):
            self.assertIsNone(refinement._result(response, payload).evidence)
        self.assertTrue(parse_report.call_args.kwargs["transfer_pair"])
        self.assertTrue(parse_report.call_args.kwargs["multi_site"])

    def test_existing_scalar_and_step_fixtures_remain_frozen(self):
        self.assertEqual(hashlib.sha256(legacy.generator.PATH.read_bytes()).hexdigest(), "22c1f47c3fbb135bb51df9dfd22530bac347a206e6575de4806b58bd4f36227b")
        self.assertEqual(hashlib.sha256(step.generator.PATH.read_bytes()).hexdigest(), "2fefcdb64ea2e955683cdc6b122f7804e6ca4c1cb78d51554b04ad8c6cbf5041")


if __name__ == "__main__": unittest.main()
