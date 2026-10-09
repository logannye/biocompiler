"""Independent step-law authoring and inert transport checks; no native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler import core_policy_component_material as api, core_policy_implementation as implementation
from biocompiler import core_policy_material as material, core_policy_refinement as refinement
from biocompiler.core_client import CoreProtocolError, CoreResponse, CORE_VERSION
from biocompiler.policy import quantitative as q, component_material as public, implementation as public_implementation
from tests import test_policy_finite_machine as finite, test_policy_quantitative as legacy
from tools import generate_policy_quantitative_step_fixture as generator


def assert_boundary_inventory(case, request):
    """Boundary identity and endpoint identity are independently unique."""
    components = {row["identity"]["id"]: row for row in request["component_library"]["components"]}
    rule = request["composition_rule"]["body"]
    boundaries = {}
    for selected in rule["components"]:
        ports = components[selected["component"]["id"]]["body"]["fragment"]["boundary_ports"]
        case.assertEqual(len({row["id"] for row in ports}), len(ports))
        case.assertEqual(len({(row["endpoint"]["node"], row["endpoint"]["port"]) for row in ports}), len(ports))
        boundaries.update({(selected["slot"], row["id"]): row for row in ports})
    used, consumers = set(), []
    for link in rule["links"]:
        for side, direction in (("producer", "output"), ("consumer", "input")):
            key = link[side]["slot"], link[side]["boundary"]
            case.assertIn(key, boundaries)
            case.assertEqual(boundaries[key]["direction"], direction)
            case.assertEqual(boundaries[key]["signal_type"], link["signal_type"])
            used.add(key)
            if side == "consumer": consumers.append(key)
    case.assertEqual(used, set(boundaries))
    case.assertEqual(len(consumers), len(set(consumers)))
    for suffix in ("product", "authorization"):
        links = [row for row in rule["links"] if row["id"].startswith("response." + suffix)]
        case.assertGreater(len(links), 1)
        case.assertEqual(len({(row["producer"]["slot"], row["producer"]["boundary"]) for row in links}), 1)


def law():
    return q.SampledStepReservoir(substance="fixture.reservoir.amount", compartment="fixture.executor.reservoir", unit=p.COUNT,
        quantum=p.quantity(1, p.COUNT), capacity=p.quantity(4, p.COUNT), threshold=p.quantity(3, p.COUNT),
        initial=p.quantity(0, p.COUNT), sample_period=p.quantity(1, p.SECOND), rise=p.quantity(2, p.COUNT), fall=p.quantity(1, p.COUNT))


def candidate(packet):
    value = finite.inert_candidate(packet)
    value["binding"].update(schema_version=implementation.MULTI_SITE_BINDING_SCHEMA, profile=implementation.MULTI_SITE_BINDING_PROFILE)
    value["implementation"].update(profile=generator.PRIMITIVE, observable_profile=generator.OBSERVABLE)
    return value


def leaf(request, actual, table):
    value = legacy.leaf(request, actual, table)
    value.update(schema_version="biocompiler.policy_quantitative_assessment.v0.2",
        profile="biocompiler.policy_sampled_saturating_step_reservoir.v0.1",
        implementation="biocompiler.ocaml.policy_quantitative_check.v0.2",
        claim_scope="exact_sampled_step_reservoir_under_supplied_contract")
    nodes = {node["id"]: node["model"] for node in actual["implementation"]["nodes"]}
    value["bindings"] = {"machine_bank": "control.machine", "observation_bank": "control.evidence", "observation_input": "condition",
        "attempt_bank": "actuator.response", "crossing_sites": [
            {"transition": "up1", "source_state": "q1", "input": True,
             "request_endpoint": {"node": "control.commit2", "port": "request0"}, "model": nodes["control.commit2"], "attempt_port": "request0"},
            {"transition": "up2", "source_state": "q2", "input": True,
             "request_endpoint": {"node": "control.commit4", "port": "request0"}, "model": nodes["control.commit4"], "attempt_port": "request1"}]}
    return value


class StepQuantitativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def setUp(self):
        self.request = deepcopy(self.packet["request"])
        self.candidate = candidate(self.packet)
        self.document = p.from_data(self.request["implementation_request"]["document"], p.BuildRequest)
        self.machine = next(row for row in self.document.program.declarations if isinstance(row, p.Machine))
        self.observation = next(row for row in self.document.program.declarations if isinstance(row, p.Observation))
        self.effect = next(row for row in self.document.program.declarations if isinstance(row, p.Effect))
        self.leaf = leaf(self.request, self.candidate, self.packet["expected"]["table"])

    def validate_leaf(self, value):
        api._quantitative_evidence(self.request, self.candidate,
            {"quantitative": value, "quantitative_status": value["outcome"],
             "status": api.ACCEPTED_STATUS if value["outcome"] == "pass" else "not_accepted"})

    def test_literal_fixture_complete_pins_source_ports_and_exact_rna(self):
        self.assertEqual(generator.build(), self.packet)
        assert_boundary_inventory(self, self.request)
        self.assertLess(generator.PATH.stat().st_size, 1_000_000)
        self.assertEqual(p.check(self.document).status, "complete")
        self.assertEqual(p.to_data(self.document), self.request["implementation_request"]["document"])
        self.assertEqual(len(self.packet["expected"]["table"]), 15)
        domain = self.request["implementation_request"]["operating_domain"]
        self.assertEqual(domain["horizon_ticks"], 16)
        self.assertGreater(self.packet["limits"]["source"]["max_ticks"], domain["horizon_ticks"])
        self.assertEqual(self.packet["limits"]["candidate"]["max_work"], 10_000_000)
        self.assertGreaterEqual(domain["logical_limits"]["max_source_attempts"], 3 * len(domain["encounters"]))
        self.assertEqual(domain["lifecycle_factors"], [{"slots": ["e1", "e2"], "ticks": [12], "actions": ["keep", "reset"]}])
        self.assertEqual(len(self.packet["expected"]["keep_trajectory"]), 17)
        self.assertEqual(len(self.packet["expected"]["reset_trajectory"]), 17)
        self.assertEqual(self.packet["expected"]["sequence"], "CCAUGGCUUAAGGAAAA")
        self.assertEqual(self.packet["expected"]["sequence"], self.packet["expected"]["molecule"]["sequence"])
        rule = self.request["composition_rule"]
        self.assertEqual(generator.shared.digest(rule["body"]), rule["identity"]["content_fingerprint"])
        self.assertEqual(generator.shared.digest(self.packet["expected"]["ordered_union"]), self.request["context"]["record_layout"]["union_digest"])
        for component in self.request["component_library"]["components"]:
            self.assertEqual(generator.shared.digest(component["body"]), component["identity"]["content_fingerprint"])
            boundaries = component["body"]["fragment"]["boundary_ports"]
            self.assertEqual(len({row["id"] for row in boundaries}), len(boundaries))
        bank = next(row for row in self.request["implementation_request"]["implementation_library"]["models"] if row["body"]["primitive"] == "attempt_bank_sites")
        self.assertEqual(bank["body"]["configuration"]["sites"], 2)
        self.assertEqual(bank["body"]["configuration"]["capacity"], domain["logical_limits"]["max_source_attempts"])
        self.assertEqual(self.request["context"]["record_layout"]["attempts"], domain["logical_limits"]["max_source_attempts"])
        actuator = self.request["component_library"]["components"][1]["body"]["fragment"]
        self.assertEqual([row["endpoint"]["port"] for row in actuator["boundary_ports"] if row["id"].startswith("response.request")], ["request0", "request1"])
        for provider in self.request["context"]["providers"]:
            self.assertEqual(generator.shared.digest(provider["body"]), provider["identity"]["content_fingerprint"])

    def test_boundary_coalescing_rejects_conflicting_interfaces_and_duplicate_inputs(self):
        boundary = {"id": "first", "direction": "output", "signal_type": "truth_value",
                    "endpoint": {"node": "evidence", "port": "value"}}
        for changes in ({"signal_type": "product_symbol"}, {"direction": "input"}, {"scope": "different"}):
            fragment = {"boundary_ports": [deepcopy(boundary), {**deepcopy(boundary), "id": "second", **changes}]}
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                generator.coalesce_output_boundaries({"control": fragment}, [])
        inputs = [{**deepcopy(boundary), "id": name, "direction": "input"} for name in ("first", "second")]
        with self.assertRaises(AssertionError):
            generator.coalesce_output_boundaries({"control": {"boundary_ports": inputs}}, [])

    def test_grid_and_two_distinct_crossings_match_literal_source(self):
        value = law()
        self.assertEqual(value.to_data(), self.request["quantitative"]["mechanism"])
        transitions = value.transitions(self.machine, self.observation, self.effect, prefix="step")
        expected = [replace(row, id="step/" + row.id) for row in self.document.program.declarations if isinstance(row, p.Transition)]
        self.assertEqual(transitions, tuple(expected))
        self.assertEqual([(row.source, row.destination) for row in transitions if row.effects], [("q1", "q3"), ("q2", "q4")])
        self.assertFalse(isinstance(value, p.Record))
        self.assertNotIn("SampledStepReservoir", p.schema()["$defs"])
        with self.assertRaises(FrozenInstanceError): value.rise = p.quantity(3, p.COUNT)

    def test_distinct_three_site_shape_and_larger_decline(self):
        value = replace(law(), capacity=p.quantity(5, p.COUNT), threshold=p.quantity(4, p.COUNT),
                        rise=p.quantity(3, p.COUNT), fall=p.quantity(2, p.COUNT))
        machine = replace(self.machine, states=("a", "b", "c", "d", "e", "f"), initial="a")
        transitions = value.transitions(machine, self.observation, self.effect, prefix="other")
        self.assertEqual([(row.source, row.destination) for row in transitions if row.effects], [("b", "e"), ("c", "f"), ("d", "f")])
        self.assertEqual([row.destination for row in transitions[1::2]], ["a", "a", "a", "b", "c", "d"])
        self.assertEqual([row.destination for row in transitions[::2]], ["d", "e", "f", "f", "f", "f"])

    def test_exact_decimal_steps_ignore_decimal_context(self):
        with localcontext() as context:
            context.prec = 1
            value = replace(law(), quantum=p.quantity("0.123456789123456789", p.COUNT),
                capacity=p.quantity("0.493827156493827156", p.COUNT), threshold=p.quantity("0.370370367370370367", p.COUNT),
                rise=p.quantity("0.246913578246913578", p.COUNT), fall=p.quantity("0.123456789123456789", p.COUNT))
            self.assertEqual([level.amount for level in value.levels], ["0", "0.123456789123456789", "0.246913578246913578", "0.370370367370370367", "0.493827156493827156"])
            self.assertEqual(len([row for row in value.transitions(self.machine, self.observation, self.effect, prefix="exact") if row.effects]), 2)

    def test_invalid_step_units_grid_and_bounds_fail_before_transport(self):
        for change in ({"rise": p.quantity(0, p.COUNT)}, {"fall": p.quantity(-1, p.COUNT)},
                       {"rise": p.quantity(5, p.COUNT)}, {"fall": p.quantity("0.5", p.COUNT)},
                       {"rise": p.quantity(2, replace(p.COUNT, id="other"))}, {"fall": 1.0}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(law(), **change)

    def test_original_authority_snapshots_and_closed_profile_routing(self):
        original = self.request["implementation_request"]
        inputs = {key: value for key, value in original.items() if key not in ("schema_version", "profile", "document")}
        self.assertEqual(public_implementation.prepare_request(self.document, **inputs, prerequisites=True, finite_machine=True, multi_site=True), original)
        fields = {key: val for key, val in self.request.items() if key not in ("schema_version", "profile")}
        prepared = public.prepare_request(**fields, instanced=True, prerequisites=True, finite_machine=True, multi_site=True)
        self.assertEqual(prepared, self.request)
        self.assertEqual(law().bind(instance="control", component=self.request["quantitative"]["selection"]["component"], contract="reservoir",
                         machine=self.machine, observation=self.observation, effect=self.effect), self.request["quantitative"])
        self.request["quantitative"]["mechanism"]["rise"]["amount"] = "3"
        self.assertNotEqual(prepared, self.request)
        for flags in ({"multi_site": True}, {"prerequisites": True, "multi_site": True}, {"prerequisites": True, "finite_machine": True, "multi_site": True, "network": True}):
            with self.assertRaises(ValueError): public_implementation.prepare_request(self.document, **inputs, **flags)
        for decode in (implementation._original, implementation._finite_machine_original, implementation._network_original):
            with self.assertRaises(CoreProtocolError): decode(original)
        for schema, profile in ((api.QUANTITATIVE_REQUEST_SCHEMA, api.STEP_QUANTITATIVE_REQUEST_PROFILE),
                                (api.STEP_QUANTITATIVE_REQUEST_SCHEMA, api.QUANTITATIVE_REQUEST_PROFILE)):
            with self.assertRaises(CoreProtocolError): api._original(prepared | {"schema_version": schema, "profile": profile})
        old_law = deepcopy(prepared); old_law["quantitative"]["mechanism"] = legacy.law().to_data()
        with self.assertRaises(CoreProtocolError): api._original(old_law)

    def test_all_routes_negotiate_step_profile_without_fallback(self):
        calls = []
        transport = SimpleNamespace(role="core")
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_step_quantitative_material": deepcopy(api.STEP_QUANTITATIVE_PROFILE),
                      "policy_step_quantitative_material_producer": deepcopy(api.STEP_QUANTITATIVE_PRODUCER_PROFILE)},
            validation_scopes=[api.STEP_QUANTITATIVE_VALIDATION_SCOPE])
        transport.call = lambda operation, payload, cancelled=None: calls.append((operation, deepcopy(payload)))
        client = api.PolicyComponentMaterialClient(transport)
        with patch.object(api, "_result", side_effect=lambda response, payload: payload):
            client.compile(self.request, self.packet["limits"])
            client.check(self.request, self.candidate, self.packet["limits"])
            client.replay(self.request, self.candidate, self.packet["limits"], {"saved": "untrusted"})
            client.export(self.request, self.candidate, self.packet["limits"])
        self.assertEqual([row[0] for row in calls], ["compile-policy-component-material", "check-policy-component-material", "replay-policy-component-material", "export-policy-component-material"])
        self.assertTrue(all(row[1]["request"] == self.request for row in calls))
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_quantitative_material": api.QUANTITATIVE_PROFILE}, validation_scopes=[api.QUANTITATIVE_VALIDATION_SCOPE])
        with self.assertRaises(CoreProtocolError): client.check(self.request, self.candidate, self.packet["limits"])
        self.assertEqual(len(calls), 4)

    def test_standalone_implementation_check_and_replay_preserve_new_profile(self):
        original = self.request["implementation_request"]
        actual = self.candidate
        transport = SimpleNamespace(role="core")
        transport.negotiate = lambda operation, cancelled=None: SimpleNamespace(
            profiles={"policy_multi_site_implementation": deepcopy(implementation.MULTI_SITE_PROFILE),
                      "policy_multi_site_implementation_producer": deepcopy(implementation.MULTI_SITE_PRODUCER_PROFILE)},
            validation_scopes=[implementation.MULTI_SITE_VALIDATION_SCOPE])
        def call(operation, payload, cancelled=None):
            value = finite.inert_result(payload, actual)
            value.update(implementation=implementation.MULTI_SITE_IMPLEMENTATION,
                         validation_scope=implementation.MULTI_SITE_VALIDATION_SCOPE)
            report = value["report"]
            report["profile"] = implementation.MULTI_SITE_PRESERVATION_PROFILE
            binding = report["binding"]
            binding.update(schema_version=implementation.MULTI_SITE_BINDING_REPORT_SCHEMA,
                           profile=implementation.MULTI_SITE_BINDING_PROFILE, observable_profile=generator.OBSERVABLE)
            binding["source_admission"]["profile"] = implementation.MULTI_SITE_REQUEST_PROFILE
            value["report_fingerprint"] = generator.shared.digest(report)
            return CoreResponse("inert-step", operation, "ok", value, (), "core", CORE_VERSION)
        transport.call = call
        client = implementation.PolicyImplementationClient(transport)
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python acceptance fallback")):
            compiled = client.compile(original, self.packet["limits"])
            checked = client.check(original, actual, self.packet["limits"])
            replayed = client.replay(original, actual, self.packet["limits"], checked.result)
        self.assertEqual(compiled.result, checked.result)
        self.assertEqual(checked.result, replayed.result)
        altered = checked.result
        altered["report"]["profile"] = implementation.PRESERVATION_PROFILE
        altered["report_fingerprint"] = generator.shared.digest(altered["report"])
        with self.assertRaises(CoreProtocolError): client.replay(original, actual, self.packet["limits"], altered)

    def test_step_report_and_named_refinement_cannot_fall_back_to_old_profiles(self):
        raw = {key: None for key in api._REPORT_FIELDS | {"prerequisites", "prerequisite_status", "quantitative", "quantitative_status"}}
        raw.update(schema_version="biocompiler.policy_component_material_assessment.v0.6", profile=api.STEP_QUANTITATIVE_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.10", resource_profile=api.RESOURCE_PROFILE,
            claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE, empirical="unassessed", artifact="withheld", export="withheld")
        flags = dict(instanced=True, prerequisites=True, finite_machine=True, quantitative=True, multi_site=True)
        self.assertEqual(api._report(raw, **flags), raw)
        with self.assertRaises(CoreProtocolError): api._report(raw, **(flags | {"multi_site": False}))
        report = {"status": "not_accepted"}
        payload = {"request": self.request, "candidate": self.candidate, "limits": self.packet["limits"]}
        result = {"schema_version": refinement.RESULT_SCHEMA, "implementation": refinement.IMPLEMENTATION,
            "validation_scope": refinement.VALIDATION_SCOPE, "request_fingerprint": generator.shared.digest(self.request),
            "candidate_fingerprint": generator.shared.digest(self.candidate), "invocation_fingerprint": generator.shared.digest(payload),
            "material_report_fingerprint": generator.shared.digest(report), "material_report": report, "evidence": None}
        response = CoreResponse("inert-step-refinement", "check-policy-refinement", "ok", result, (), "verify", CORE_VERSION)
        with (patch.object(api, "_candidate", return_value=self.candidate) as parse_candidate,
              patch.object(api, "_report", return_value=report) as parse_report, patch.object(api, "_assessment")):
            checked = refinement._result(response, payload)
        self.assertTrue(parse_candidate.call_args.kwargs["multi_site"])
        self.assertTrue(parse_report.call_args.kwargs["multi_site"])
        self.assertTrue(parse_report.call_args.kwargs["quantitative"])
        self.assertIsNone(checked.evidence)
        self.assertEqual((len(refinement._RELATIONS), len(refinement._PREMISES)), (10, 18))

    def test_transport_retains_complete_new_leaf_and_rejects_site_forgery(self):
        self.validate_leaf(self.leaf)
        mutations = [lambda row: row["bindings"]["crossing_sites"].pop(), lambda row: row["bindings"]["crossing_sites"].reverse(),
            lambda row: row["bindings"]["crossing_sites"][0].update(attempt_port="request1"),
            lambda row: row["bindings"]["crossing_sites"][1]["model"].update(content_fingerprint="0" * 64),
            lambda row: row["bindings"]["crossing_sites"][0].update(input=False),
            lambda row: row["bindings"].update(attempt_bank="other"), lambda row: row["table"].pop(),
            lambda row: row["table"][6].update(request=False), lambda row: row.update(claim_scope="empirically_validated"),
            lambda row: row.update(schema_version="biocompiler.policy_quantitative_assessment.v0.1"),
            lambda row: row["sampling"].update(no_update="decay"), lambda row: row.update(issues=["unresolved"])]
        for change in mutations:
            mutated = deepcopy(self.leaf); change(mutated)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError): self.validate_leaf(mutated)

    def test_quantitative_failure_and_obligation_hashes_remain_fail_closed(self):
        failed = deepcopy(self.leaf); failed.update(outcome="fail", bindings=None, table=[], issues=["law_mismatch"])
        self.validate_leaf(failed)
        with self.assertRaises(CoreProtocolError): self.validate_leaf(failed | {"table": self.leaf["table"]})
        report = legacy.obligations(self.leaf)
        report["preservation"]["binding"].update(schema_version=implementation.MULTI_SITE_BINDING_REPORT_SCHEMA,
                                              profile=implementation.MULTI_SITE_BINDING_PROFILE)
        for row in report["obligations"]:
            row["evidence"]["preservation"] = generator.shared.digest(report["preservation"])
            if "machine_binding" in row["evidence"]:
                row["evidence"]["machine_binding"] = generator.shared.digest(report["preservation"]["binding"])
        material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
            conjunction_stage="conditional_component_context_conjunction", finite_machine=True, multi_site=True, quantitative_key="quantitative")
        report["obligations"][0]["evidence"]["quantitative"] = "0" * 64
        with self.assertRaises(CoreProtocolError):
            material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
                conjunction_stage="conditional_component_context_conjunction", finite_machine=True, multi_site=True, quantitative_key="quantitative")

    def test_existing_law_fixture_bytes_remain_frozen(self):
        self.assertEqual(hashlib.sha256(legacy.generator.PATH.read_bytes()).hexdigest(),
                         "f57665997f2d36d90e24aaa9b4543142efa333044871ec51d3dee5d0d8401f87")


if __name__ == "__main__": unittest.main()
