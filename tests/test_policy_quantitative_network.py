"""Independent transfer-network premises and inert Python transport; no native acceptance."""
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
from tests import test_policy_quantitative_step as step, test_policy_quantitative as legacy, test_policy_quantitative_transfer as pair
from tools import generate_policy_quantitative_network_fixture as generator


def law():
    return q.SampledTransferNetwork(substance="fixture.reservoir.amount", unit=p.COUNT, quantum=p.quantity(1, p.COUNT),
        reservoirs=tuple(q.ReservoirCompartment(name, p.quantity(1, p.COUNT), p.quantity(initial, p.COUNT))
                         for name, initial in (("a", 1), ("b", 1), ("c", 0))),
        transfers=tuple(q.TransferEdge(identity, source, destination, p.quantity(1, p.COUNT), truth)
                        for identity, source, destination, truth in (("a_to_b", "a", "b", True), ("b_to_c", "b", "c", True),
                            ("a_to_c", "a", "c", True), ("b_to_a", "b", "a", False), ("c_to_a", "c", "a", False))),
        threshold_compartment="b", threshold=p.quantity(1, p.COUNT), sample_period=p.quantity(1, p.SECOND))


def leaf(request, actual, table):
    value = legacy.leaf(request, actual, table)
    value.update(schema_version="biocompiler.policy_quantitative_assessment.v0.4",
        profile="biocompiler.policy_sampled_reserved_transfer_network.v0.1",
        implementation="biocompiler.ocaml.policy_quantitative_check.v0.4",
        claim_scope="exact_sampled_reserved_transfer_network_under_supplied_contract",
        arbitration="declared_order_prestate_reservation", ownership="single_atomic_state_owner",
        conservation={"scope": "accepted_samples_within_encounter_generation", "quantity": "sum_all_reservoirs",
                      "reset": "restore_declared_initial_vector", "checked_rows": 24})
    nodes = {node["id"]: node["model"] for node in actual["implementation"]["nodes"]}
    value["bindings"] = {"machine_bank": "control.machine", "observation_bank": "control.evidence", "observation_input": "condition",
        "attempt_bank": "actuator.response", "crossing_sites": [
            {"transition": transition, "source_state": state, "input": True,
             "request_endpoint": {"node": "control." + commit, "port": "request0"}, "model": nodes["control." + commit],
             "attempt_port": "request" + str(site)} for site, (transition, state, commit) in enumerate(
                 (("forward4", "q100", "commit4"), ("forward5", "q101", "commit5")))]}
    return value


class NetworkQuantitativeTests(unittest.TestCase):
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
        step.assert_boundary_inventory(self, self.request)
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
        self.assertEqual((bank["body"]["configuration"]["sites"], bank["body"]["configuration"]["capacity"]), (2, 6))
        self.assertEqual(self.request["context"]["record_layout"]["attempts"], 6)

    def test_sparse_expansion_matches_independent_source_flows_and_complete_table(self):
        value = law()
        self.assertEqual(value.to_data(), self.request["quantitative"]["mechanism"])
        transitions = value.transitions(self.machine, self.observation, self.effect, prefix="network")
        self.assertEqual(transitions, tuple(replace(row, id="network/" + row.id) for row in self.document.program.declarations if isinstance(row, p.Transition)))
        self.assertEqual(len(transitions), 7)
        self.assertEqual([(row.source, row.destination) for row in transitions if row.effects], [("q100", "q010"), ("q101", "q011")])
        self.assertEqual(len(self.packet["expected"]["table"]), 24)
        for row in self.packet["expected"]["table"]:
            self.assertEqual(sum(row["before"]), sum(row["after"]))
            self.assertEqual([flow["transfer"] for flow in row["flows"]], generator.EDGE_IDS)
        self.assertEqual(self.packet["expected"]["table"][12]["after"], [0, 1, 0])
        self.assertEqual(self.packet["expected"]["table"][18]["after"], [1, 0, 1])
        self.assertFalse(isinstance(value, p.Record))
        self.assertNotIn("SampledTransferNetwork", p.schema()["$defs"])
        with self.assertRaises(FrozenInstanceError): value.transfers = ()

    def test_declared_priority_reversal_changes_competition_and_false_crossing(self):
        value = law()
        reordered = replace(value, transfers=(value.transfers[2], value.transfers[1], value.transfers[0]) + value.transfers[3:])
        transitions = reordered.transitions(self.machine, self.observation, self.effect, prefix="reordered")
        self.assertEqual(next(row.destination for row in transitions if row.id == "reordered/forward4"), "q001")
        self.assertEqual(next(row.destination for row in transitions if row.id == "reordered/forward6"), "q011")
        reordered_headroom = replace(value, transfers=(value.transfers[1], value.transfers[0], value.transfers[2]) + value.transfers[3:])
        headroom = reordered_headroom.transitions(self.machine, self.observation, self.effect, prefix="headroom")
        self.assertEqual(next(row.destination for row in headroom if row.id == "headroom/forward6"), "q101")
        false_crossing = replace(value, threshold_compartment="a").transitions(self.machine, self.observation, self.effect, prefix="reverse")
        self.assertEqual([(row.source, row.destination, row.when.op) for row in false_crossing if row.effects],
                         [("q001", "q100", "not"), ("q010", "q100", "not"), ("q011", "q101", "not")])

    def test_four_reservoir_chain_preserves_prestate_no_cascade(self):
        value = replace(law(), reservoirs=tuple(q.ReservoirCompartment(name, p.quantity(1, p.COUNT), p.quantity(int(index == 0), p.COUNT))
                for index, name in enumerate(("a", "b", "c", "d"))),
            transfers=tuple(q.TransferEdge(source + destination, source, destination, p.quantity(1, p.COUNT), True)
                for source, destination in (("a", "b"), ("b", "c"), ("c", "d"))), threshold_compartment="d")
        machine = replace(self.machine, states=tuple("s" + str(i) for i in range(16)), initial="s8")
        transitions = value.transitions(machine, self.observation, self.effect, prefix="chain")
        by_id = {row.id: row for row in transitions}
        self.assertEqual(len(value.levels), 16)
        self.assertEqual(by_id["chain/forward8"].destination, "s4")
        self.assertEqual(by_id["chain/forward12"].destination, "s10")
        self.assertEqual(by_id["chain/forward14"].destination, "s13")
        self.assertEqual(by_id["chain/forward10"].destination, "s5")
        self.assertTrue(by_id["chain/forward10"].effects)
        self.assertLessEqual(len(transitions), 28)
        self.assertLessEqual(2 * len(transitions) + 7, 64)

    def test_circulating_positive_flow_retains_net_zero_self_transition(self):
        value = replace(law(), reservoirs=tuple(q.ReservoirCompartment(name, p.quantity(2, p.COUNT), p.quantity(1, p.COUNT)) for name in ("a", "b")),
            transfers=(q.TransferEdge("ab", "a", "b", p.quantity(1, p.COUNT), True),
                       q.TransferEdge("ba", "b", "a", p.quantity(1, p.COUNT), True)), threshold=p.quantity(2, p.COUNT))
        machine = replace(self.machine, states=tuple("s" + str(i) for i in range(9)), initial="s4")
        transitions = value.transitions(machine, self.observation, self.effect, prefix="cycle")
        center = next(row for row in transitions if row.id == "cycle/forward4")
        self.assertEqual((center.source, center.destination, center.effects), ("s4", "s4", ()))
        self.assertFalse(any(row.id.startswith("cycle/reverse") for row in transitions))
        self.assertNotIn("cycle/forward0", [row.id for row in transitions])
        self.assertNotIn("cycle/forward8", [row.id for row in transitions])

    def test_exact_fractional_grid_ignores_ambient_decimal_context(self):
        with localcontext() as context:
            context.prec = 1
            quantum = p.quantity("0.123456789123456789", p.COUNT)
            value = replace(law(), quantum=quantum,
                reservoirs=tuple(replace(row, capacity=quantum, initial=quantum if row.initial.amount == "1" else row.initial) for row in law().reservoirs),
                transfers=tuple(replace(row, amount=quantum) for row in law().transfers), threshold=quantum)
            self.assertEqual([amount.amount for amount in value.levels[5]], ["0.123456789123456789", "0", "0.123456789123456789"])
            self.assertEqual(len(value.transitions(self.machine, self.observation, self.effect, prefix="exact")), 7)

    def test_rejects_aliasing_units_inexact_grids_edges_and_product_overflow(self):
        value = law()
        for changes in ({"reservoirs": value.reservoirs[:2] + (value.reservoirs[0],)},
                {"reservoirs": value.reservoirs[:1]}, {"reservoirs": [*value.reservoirs]},
                {"transfers": ()}, {"transfers": value.transfers + value.transfers},
                {"transfers": (replace(value.transfers[0], source="missing"),)},
                {"transfers": (replace(value.transfers[0], amount=p.quantity("0.5", p.COUNT)),)},
                {"transfers": (replace(value.transfers[0], amount=p.quantity(2, p.COUNT)),)},
                {"transfers": (replace(value.transfers[0], amount=p.quantity(1, p.SECOND)),)},
                {"threshold": p.quantity(1, replace(p.COUNT, id="other"))}, {"threshold_compartment": "missing"},
                {"reservoirs": (replace(value.reservoirs[0], capacity=p.quantity(4, p.COUNT)),) + value.reservoirs[1:]}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)): replace(value, **changes)
        for changes in ({"when": 1}, {"when": "true"}, {"destination": "a"}, {"amount": p.quantity(0, p.COUNT)}):
            with self.assertRaises((TypeError, ValueError)): replace(value.transfers[0], **changes)
        with self.assertRaises(ValueError): value.state_values(("same",) * 8)
        with self.assertRaises(ValueError): value.transitions(replace(self.machine, initial="q000"), self.observation, self.effect, prefix="bad")

    def test_original_authority_snapshot_and_explicit_profile_routing(self):
        fields = {key: val for key, val in self.request.items() if key not in ("schema_version", "profile")}
        prepared = public.prepare_request(**fields, instanced=True, prerequisites=True, finite_machine=True, multi_site=True, transfer_network=True)
        self.assertEqual(prepared, self.request)
        self.assertEqual(law().bind(instance="control", component=self.request["quantitative"]["selection"]["component"], contract="network",
                         machine=self.machine, observation=self.observation, effect=self.effect), self.request["quantitative"])
        self.request["quantitative"]["mechanism"]["transfers"][0]["amount"]["amount"] = "2"
        self.assertNotEqual(prepared, self.request)
        with self.assertRaises(ValueError): public.prepare_request(**fields, instanced=True, prerequisites=True, finite_machine=True, transfer_network=True)
        for schema, profile in ((api.STEP_QUANTITATIVE_REQUEST_SCHEMA, api.TRANSFER_NETWORK_REQUEST_PROFILE),
                                (api.TRANSFER_NETWORK_REQUEST_SCHEMA, api.STEP_QUANTITATIVE_REQUEST_PROFILE)):
            with self.assertRaises(CoreProtocolError): api._original(prepared | {"schema_version": schema, "profile": profile})
        old = deepcopy(prepared); old["quantitative"]["mechanism"] = step.law().to_data()
        with self.assertRaises(CoreProtocolError): api._original(old)

    def test_all_routes_negotiate_transfer_profile_without_fallback(self):
        calls = []
        transport = SimpleNamespace(role="core")
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_transfer_network_material": deepcopy(api.TRANSFER_NETWORK_PROFILE),
                      "policy_transfer_network_material_producer": deepcopy(api.TRANSFER_NETWORK_PRODUCER_PROFILE)},
            validation_scopes=[api.TRANSFER_NETWORK_VALIDATION_SCOPE])
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
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(row[1]["request"] == self.request for row in calls))
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_step_quantitative_material": api.STEP_QUANTITATIVE_PROFILE}, validation_scopes=[api.STEP_QUANTITATIVE_VALIDATION_SCOPE])
        with self.assertRaises(CoreProtocolError): client.check(self.request, self.candidate, self.packet["limits"])
        self.assertEqual(len(calls), 4)

    def test_leaf_preserves_conservation_sparse_holds_and_complete_site_inventory(self):
        self.validate_leaf(self.leaf)
        mutations = [lambda row: row["conservation"].update(checked_rows=8), lambda row: row.update(conservation=None),
            lambda row: row["conservation"].update(scope="including_resets"), lambda row: row["table"][0].update(after=[1, 0, 0]),
            lambda row: row["table"][12]["flows"][0].update(quanta=0), lambda row: row["table"][0].update(request=True),
            lambda row: row["bindings"]["crossing_sites"].pop(), lambda row: row["bindings"]["crossing_sites"].reverse(),
            lambda row: row["bindings"]["crossing_sites"][0].update(attempt_port="request1"),
            lambda row: row.update(schema_version="biocompiler.policy_quantitative_assessment.v0.2"),
            lambda row: row.update(claim_scope="unbounded_mass_conservation"), lambda row: row["table"].pop(), lambda row: row["table"][12]["flows"].reverse(),
            lambda row: row["table"][12]["flows"][0].update(quanta=True), lambda row: row["table"][12]["flows"][0].update(transfer="other"),
            lambda row: row.update(arbitration="sequential"), lambda row: row.update(ownership="distributed")]
        for change in mutations:
            mutated = deepcopy(self.leaf); change(mutated)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError): self.validate_leaf(mutated)

    def test_parallel_flow_forgery_rejects_even_with_identical_state_delta(self):
        # A later parallel edge cannot steal the earlier edge's reserved stock.
        mechanism = self.request["quantitative"]["mechanism"]
        parallel = deepcopy(mechanism["transfers"][0]); parallel["id"] = "later_parallel"
        mechanism["transfers"].append(parallel)
        self.request["component_library"]["components"][0]["body"]["quantitative_contracts"][0]["mechanism"] = deepcopy(mechanism)
        table = deepcopy(self.packet["expected"]["table"])
        for row in table: row["flows"].append({"transfer": "later_parallel", "quanta": 0})
        report = leaf(self.request, self.candidate, table)
        self.validate_leaf(report)
        forged = deepcopy(report)
        forged["table"][12]["flows"][0]["quanta"] = 0
        forged["table"][12]["flows"][-1]["quanta"] = 1
        self.assertEqual(forged["table"][12]["before"], report["table"][12]["before"])
        self.assertEqual(forged["table"][12]["after"], report["table"][12]["after"])
        with self.assertRaises(CoreProtocolError): self.validate_leaf(forged)

    def test_both_crossing_polarities_use_grid_order_and_original_request_lanes(self):
        # Inert report-order control: declaration order fixes request lanes while
        # the complete quantitative output census uses state/True/False order.
        mechanism = self.request["quantitative"]["mechanism"]
        opposite = deepcopy(mechanism["transfers"][0]); opposite.update(id="opposite", when=False)
        mechanism["transfers"].append(opposite)
        self.request["component_library"]["components"][0]["body"]["quantitative_contracts"][0]["mechanism"] = deepcopy(mechanism)
        declarations = self.request["implementation_request"]["document"]["program"]["declarations"]
        for identity in ("forward4", "forward5"):
            index = next(i for i, row in enumerate(declarations) if row.get("id") == identity)
            negative = deepcopy(declarations[index]); negative.update(id=identity + "negative", when=p.to_data(p.not_(self.observation.expression)))
            declarations.insert(index, negative)
            anchor = deepcopy(next(row for row in self.candidate["binding"]["transitions"] if row["source"] == identity))
            anchor["source"] = identity + "negative"
            self.candidate["binding"]["transitions"].append(anchor)
        table = deepcopy(self.packet["expected"]["table"])
        for row in table: row["flows"].append({"transfer": "opposite", "quanta": 0})
        for index, after in ((13, [0, 1, 0]), (16, [0, 1, 1])):
            table[index].update(destination="q010" if index == 13 else "q011", after=after, request=True)
            table[index]["flows"][-1]["quanta"] = 1
        report = leaf(self.request, self.candidate, table)
        sites = []
        for index, original in enumerate(report["bindings"]["crossing_sites"]):
            positive = deepcopy(original); positive["attempt_port"] = "request" + str(2 * index + 1)
            negative = deepcopy(original); negative.update(transition=original["transition"] + "negative", input=False, attempt_port="request" + str(2 * index))
            sites.extend([positive, negative])
        report["bindings"]["crossing_sites"] = sites
        self.validate_leaf(report)
        report["bindings"]["crossing_sites"][0:2] = reversed(report["bindings"]["crossing_sites"][0:2])
        with self.assertRaises(CoreProtocolError): self.validate_leaf(report)

    def test_failing_leaf_withholds_conservation_and_complete_table(self):
        failed = deepcopy(self.leaf); failed.update(outcome="fail", bindings=None, conservation=None, table=[], issues=["law_mismatch"])
        self.validate_leaf(failed)
        for changes in ({"conservation": self.leaf["conservation"]}, {"table": self.leaf["table"]}, {"bindings": self.leaf["bindings"]}):
            with self.assertRaises(CoreProtocolError): self.validate_leaf(failed | changes)

    def test_new_material_report_and_named_refinement_retain_profile(self):
        raw = {key: None for key in api._REPORT_FIELDS | {"prerequisites", "prerequisite_status", "quantitative", "quantitative_status"}}
        raw.update(schema_version="biocompiler.policy_component_material_assessment.v0.8", profile=api.TRANSFER_NETWORK_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.12", resource_profile=api.RESOURCE_PROFILE,
            claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE, empirical="unassessed", artifact="withheld", export="withheld")
        flags = dict(instanced=True, prerequisites=True, finite_machine=True, quantitative=True, multi_site=True, transfer_network=True)
        self.assertEqual(api._report(raw, **flags), raw)
        with self.assertRaises(CoreProtocolError): api._report(raw, **(flags | {"transfer_network": False}))
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
        self.assertTrue(parse_report.call_args.kwargs["transfer_network"])
        self.assertTrue(parse_report.call_args.kwargs["multi_site"])

    def test_existing_scalar_and_step_fixtures_remain_frozen(self):
        self.assertEqual(hashlib.sha256(legacy.generator.PATH.read_bytes()).hexdigest(), "f57665997f2d36d90e24aaa9b4543142efa333044871ec51d3dee5d0d8401f87")
        self.assertEqual(hashlib.sha256(step.generator.PATH.read_bytes()).hexdigest(), "9054c1f97922ff7f8de58aeffab2def7c6a6094338c3e0666505e44525bf0662")
        self.assertEqual(hashlib.sha256(pair.generator.PATH.read_bytes()).hexdigest(), "ec9bd340ada1cac4b39aa0fbcec0fa7887719fe175e3511631244efc8f2acc35")


if __name__ == "__main__": unittest.main()
