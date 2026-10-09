"""Finite-machine source fixtures and inert SDK peers; no native acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler.policy import implementation as request_api, component_material as component_api
from biocompiler import core_policy_implementation as implementation
from biocompiler import core_policy_component_material as material
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse, encode_json
from tests import test_core_policy_implementation as peer
from tools import generate_policy_finite_machine_fixture as generator

ROOT = Path(__file__).resolve().parents[1]


def packet():
    return json.loads(generator.PATH.read_text())


def source_rows(request, kind):
    return [row for row in request["document"]["program"]["declarations"] if row["$type"] == kind]


def inert_candidate(case):
    """Wire ledgers only: this function is deliberately not a graph compiler."""
    request = case["request"]["implementation_request"]
    union = case["expected"]["ordered_union"]
    identify = lambda slot, node: slot + "." + node
    graph = {"schema_version": "biocompiler.policy_implementation.v0.1",
        "profile": "biocompiler.policy_staged_primitives.v0.1", "observable_profile": "biocompiler.policy_staged_observables.v0.1",
        "authority": {"source_artifact_digest": peer.digest(request["document"]), "descriptors_digest": peer.digest(request["definitions"]),
            "domain_digest": peer.digest(request["operating_domain"]), "implementation_catalog_digest": peer.digest(request["document"]["implementations"]),
            "library_digest": peer.digest(request["implementation_library"])}, "slot_layout": union["slot_layout"],
        "nodes": [{"id": identify(row["slot"], row["node"]), "model": row["model"]["identity"]} for row in union["nodes"]],
        "wires": [], "inputs": [{"id": row["id"], "kind": row["kind"], "consumer": {
            "node": identify(row["consumer"]["slot"], row["consumer"]["node"]), "port": row["consumer"]["port"]}} for row in union["inputs"]],
        "atomic_groups": [], "semantic_exports": [], "occurrences": []}
    proposed = {"schema_version": implementation.FINITE_MACHINE_BINDING_SCHEMA, "profile": implementation.FINITE_MACHINE_BINDING_PROFILE,
        "catalog_entry": request["catalog_bindings"][0]["entry_id"], "states": [], "rules": [],
        "observations": [{"source": "condition", "bank": "control.evidence", "input": "condition"}],
        "effects": [{"source": row["id"], "bank": "actuator." + row["id"], "feedback": row["id"] + "_feedback"} for row in source_rows(request, "Effect")],
        "machines": [{"source": "machine", "bank": "control.machine"}],
        "transitions": [{"source": row["id"], "gate": "control.gate" + str(i), "arbiter": "control.arbiter", "lane": i,
            "commit": "control.commit" + str(i)} for i, row in enumerate(source_rows(request, "Transition"))]}
    return {"schema_version": implementation.CANDIDATE_SCHEMA,
        "behavior": peer.source_peer.candidate(request["document"], request["definitions"]),
        "implementation": graph, "binding": proposed}


def inert_result(payload, actual):
    request = payload["request"]
    actual = deepcopy(payload.get("candidate") or actual)
    report = peer.report(request, actual, payload["limits"])
    binding = report["binding"]
    binding.update(schema_version=implementation.FINITE_MACHINE_BINDING_REPORT_SCHEMA,
        profile=implementation.FINITE_MACHINE_BINDING_PROFILE, observable_profile="biocompiler.policy_staged_observables.v0.1",
        state_encoding="exact_ordered_source_labels")
    binding["source_admission"].update(schema_version="biocompiler.policy_realization_admission.v0.2",
        profile=implementation.FINITE_MACHINE_REQUEST_PROFILE, pending_dependencies=implementation._pending_dependencies(request))
    return {"schema_version": implementation.RESULT_SCHEMA, "implementation": implementation.FINITE_MACHINE_IMPLEMENTATION,
        "resource_profile": implementation.RESOURCE_PROFILE, "validation_scope": implementation.FINITE_MACHINE_VALIDATION_SCOPE,
        "request_fingerprint": peer.digest(request), "candidate_fingerprint": peer.digest(actual),
        "invocation_fingerprint": peer.digest({"request": request, "candidate": actual, "limits": payload["limits"]}),
        "report_fingerprint": peer.digest(report), "candidate": actual, "report": report}


class InertTransport:
    """No process is launched. The peer asserts untrusted synthetic evidence."""
    role = "core"

    def __init__(self, case, *, component=False):
        self.case, self.calls, self.component = case, [], component
        api = material if component else implementation
        key = "policy_finite_machine_material" if component else "policy_finite_machine_implementation"
        self.capabilities = SimpleNamespace(profiles={key: deepcopy(api.FINITE_MACHINE_PROFILE),
            key + "_producer": deepcopy(api.FINITE_MACHINE_PRODUCER_PROFILE)},
            validation_scopes=[api.FINITE_MACHINE_VALIDATION_SCOPE])
        self.mutate = None

    def negotiate(self, operation, *, cancelled=None):
        self.calls.append(("negotiate", operation))
        return self.capabilities

    def call(self, operation, payload, *, cancelled=None):
        self.calls.append((operation, deepcopy(payload)))
        value = inert_result(payload, inert_candidate(self.case)) if not self.component else None
        if self.mutate: self.mutate(value)
        return CoreResponse("inert-finite", operation, "ok", value, (), self.role, CORE_VERSION)


class FiniteFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = packet()

    def test_original_generator_is_deterministic_bounded_and_source_complete(self):
        self.assertEqual(generator.build(), self.fixture)
        self.assertLess(generator.PATH.stat().st_size, 2_000_000)
        self.assertEqual([case["id"] for case in self.fixture["cases"]], ["retry_cycle", "guarded_branch", "updated_fork"])
        for case in self.fixture["cases"]:
            raw = case["request"]["implementation_request"]
            document = p.from_data(raw["document"], p.BuildRequest)
            with self.subTest(case=case["id"]):
                self.assertEqual(p.check(document).status, "complete")
                self.assertEqual(p.to_data(document), raw["document"])
                self.assertEqual((len(source_rows(raw, "Machine")[0]["states"]), len(source_rows(raw, "Transition")), len(source_rows(raw, "Effect"))),
                    (case["expected"]["state_count"], case["expected"]["transition_count"], case["expected"]["effect_count"]))
                self.assertEqual(source_rows(raw, "StateStore") + source_rows(raw, "Rule"), [])

    def test_three_topologies_have_distinct_control_and_unknown_event_inputs(self):
        retry, branch, updated = self.fixture["cases"]
        retry_request = retry["request"]["implementation_request"]
        self.assertEqual({row["destination"] for row in source_rows(retry_request, "Transition") if row["source"] == "active"}, {"ready", "done"})
        factors = retry_request["operating_domain"]["feedback_factors"]
        self.assertEqual([row["ticks"] for row in factors], [[2], [4]])
        self.assertTrue(all(row["attempt_selector"] == "all_previously_created" for row in factors))
        branch_request = branch["request"]["implementation_request"]
        guarded = [row for row in source_rows(branch_request, "Transition") if row["on"]["value"] == "completed" and row["source"] == "deciding"]
        self.assertEqual([row["when"]["op"] for row in guarded], ["observe", "not"])
        self.assertTrue(branch_request["operating_domain"]["observation_factors"])
        updated_request = updated["request"]["implementation_request"]
        self.assertEqual(source_rows(updated_request, "Transition")[0]["on"]["op"], "updated")
        unknown = [row for row in updated_request["operating_domain"]["fixed_observations"] if row["available_tick"] == 1]
        self.assertEqual([row["status"] for row in unknown], ["missing", "missing"])
        self.assertTrue(all(row["unknown"] == "defer" for row in source_rows(updated_request, "Transition")))

    def test_component_material_originals_retain_all_pins_nodes_links_and_exact_sequence(self):
        for case in self.fixture["cases"]:
            request, expected = case["request"], case["expected"]
            rule = request["composition_rule"]
            with self.subTest(case=case["id"]):
                self.assertEqual(rule["profile"], material.INSTANCE_ASSEMBLY_PROFILE)
                self.assertEqual([row["slot"] for row in rule["body"]["components"]], ["control", "actuator"])
                self.assertEqual(rule["identity"]["content_fingerprint"], peer.digest(rule["body"]))
                self.assertEqual(request["context"]["record_layout"]["union_digest"], peer.digest(expected["ordered_union"]))
                for component in request["component_library"]["components"]:
                    body = component["body"]
                    boundaries = body["fragment"]["boundary_ports"]
                    endpoints = [(row["endpoint"]["node"], row["endpoint"]["port"]) for row in boundaries]
                    self.assertEqual(len(endpoints), len(set(endpoints)))
                    self.assertEqual(component["identity"]["content_fingerprint"], peer.digest(body))
                    for node in body["fragment"]["nodes"]:
                        self.assertEqual(node["model"]["identity"]["content_fingerprint"], peer.digest(node["model"]["body"]))
                        for kind in ("primitive", "configuration", "replication"):
                            self.assertIn({"kind": kind, "id": node["id"]}, [row["target"] for row in body["carriers"]])
                self.assertEqual(len(expected["ordered_union"]["nodes"]), expected["node_count"])
                self.assertEqual(sum(row["model"]["body"]["primitive"] == "truth_constant"
                    for row in expected["ordered_union"]["nodes"]), 1)
                self.assertEqual(len(rule["body"]["links"]), expected["link_count"])
                consumers = [(row["consumer"]["slot"], row["consumer"]["boundary"]) for row in rule["body"]["links"]]
                self.assertEqual(len(consumers), len(set(consumers)))
                if case["id"] == "guarded_branch":
                    # Both requests still consume the shared product and authorization;
                    # accept/reject still consume the same completed event occurrence.
                    producers = [(row["producer"]["slot"], row["producer"]["boundary"]) for row in rule["body"]["links"]]
                    self.assertEqual(len(producers) - len(set(producers)), 3)
                self.assertEqual(expected["molecule"]["sequence"], "CCAUGGCUUAAGGAAAA")
                self.assertEqual(expected["sequence"], expected["molecule"]["sequence"])
                self.assertEqual({row["id"] for row in expected["molecule"]["features"]},
                    {'["control","utr5"]', '["actuator","cds"]', '["actuator","utr3"]', '["actuator","poly_a"]'})
                for provider in request["context"]["providers"]:
                    self.assertEqual(provider["identity"]["content_fingerprint"], peer.digest(provider["body"]))

    def test_legacy_five_state_seven_transition_originals_are_frozen(self):
        for name, digest in (("policy_staged_material_v01.json", "d764d9a8f3ca3e64998eddb43de5750cc30425fb59713b09b09cb31560f74daf"),
                             ("policy_staged_realization_request_v01.json", "59eab0475a71f6d7db6481d0cc5103af861f8baedff5ab2b931eb8cd6f19ad24")):
            self.assertEqual(hashlib.sha256((ROOT / "core/test/data" / name).read_bytes()).hexdigest(), digest)
        old = json.loads((ROOT / "core/test/data/policy_staged_realization_request_v01.json").read_text())
        self.assertEqual((len(source_rows(old, "Machine")[0]["states"]), len(source_rows(old, "Transition")), len(source_rows(old, "Effect"))), (5, 7, 2))


class FiniteTransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = packet()
        self.case = self.fixture["cases"][0]
        self.request = self.case["request"]["implementation_request"]
        self.limits = self.fixture["limits"]

    def test_explicit_request_builders_snapshot_exact_finite_profiles(self):
        args = {key: self.request[key] for key in ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")}
        prepared = request_api.prepare_request(p.from_data(self.request["document"], p.BuildRequest),
            **args, prerequisites=True, finite_machine=True)
        self.assertEqual(prepared, self.request)
        for flags in ({"finite_machine": True}, {"finite_machine": True, "prerequisites": True, "multi_product": True}):
            with self.assertRaises(ValueError):
                request_api.prepare_request(p.from_data(self.request["document"], p.BuildRequest), **args, **flags)
        supplied = self.case["request"]
        component_args = {key: value for key, value in supplied.items() if key not in ("schema_version", "profile")}
        result = component_api.prepare_request(**component_args, instanced=True, prerequisites=True, finite_machine=True)
        self.assertEqual(result, supplied)
        result["context"]["providers"].clear()
        self.assertTrue(supplied["context"]["providers"])
        for flags in ({"finite_machine": True}, {"finite_machine": True, "instanced": True, "prerequisites": True, "multi_member": True}):
            with self.assertRaises(ValueError): component_api.prepare_request(**component_args, **flags)

    def test_legacy_decoders_never_accept_finite_or_mixed_schema_profiles(self):
        for decoder in (implementation._original, implementation._prerequisite_original, implementation._multi_product_original):
            with self.assertRaises(CoreProtocolError): decoder(self.request)
        for key, value in (("profile", implementation.REQUEST_PROFILE), ("schema_version", implementation.REQUEST_SCHEMA)):
            changed = deepcopy(self.request); changed[key] = value
            with self.assertRaises(CoreProtocolError): implementation._request(changed)
        for key, value in (("profile", material.INSTANCE_REQUEST_PROFILE), ("schema_version", material.INSTANCE_REQUEST_SCHEMA)):
            changed = deepcopy(self.case["request"]); changed[key] = value
            with self.assertRaises(CoreProtocolError): material._original(changed)
        changed = deepcopy(self.case["request"])
        changed["implementation_request"]["profile"] = implementation.PREREQUISITE_REQUEST_PROFILE
        with self.assertRaises(CoreProtocolError): material._original(changed)

    def test_standalone_compile_check_replay_validate_complete_wire_evidence(self):
        for case in self.fixture["cases"]:
            transport = InertTransport(case)
            client = implementation.PolicyImplementationClient(transport)
            request = case["request"]["implementation_request"]
            with self.subTest(case=case["id"]), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python fallback")):
                compiled = client.compile(request, self.limits)
                checked = client.check(request, compiled.candidate, self.limits)
                replay = client.replay(request, compiled.candidate, self.limits, checked.result)
                self.assertEqual(compiled.result, checked.result)
                self.assertEqual(checked.result, replay.result)
                self.assertEqual(checked.report["binding"]["profile"], implementation.FINITE_MACHINE_BINDING_PROFILE)
                self.assertEqual(checked.report["material"], "unassessed")
                changed = checked.result; changed["implementation"] = implementation.IMPLEMENTATION
                with self.assertRaises(CoreProtocolError): client.replay(request, compiled.candidate, self.limits, changed)

    def test_finite_lane_source_input_and_inventory_mutations_reject_after_rehash(self):
        transport = InertTransport(self.case); client = implementation.PolicyImplementationClient(transport)
        actual = inert_candidate(self.case)
        for mutation in (lambda value: value["binding"]["transitions"][0].update(lane=1),
                         lambda value: value["binding"]["transitions"].reverse(),
                         lambda value: value["binding"]["effects"][0].update(feedback="invented"),
                         lambda value: value["binding"].update(profile="biocompiler.policy_staged_source_graph.v0.1"),
                         lambda value: value["implementation"]["nodes"].extend([{"id": str(i)} for i in range(65)])):
            changed = deepcopy(actual); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError): client.check(self.request, changed, self.limits)
        transport.mutate = lambda value: value.update(implementation=implementation.IMPLEMENTATION)
        with self.assertRaises(CoreProtocolError): client.check(self.request, actual, self.limits)

    def test_finite_negotiation_rejects_old_capabilities_before_dispatch(self):
        for component in (False, True):
            transport = InertTransport(self.case, component=component)
            transport.capabilities.profiles = {"policy_component_material" if component else "policy_implementation":
                                               material.PROFILE if component else implementation.PROFILE}
            client = material.PolicyComponentMaterialClient(transport) if component else implementation.PolicyImplementationClient(transport)
            with self.subTest(component=component), self.assertRaises(CoreProtocolError):
                client.compile(self.case["request"] if component else self.request, self.limits)
            self.assertEqual(len(transport.calls), 1)
            transport.role = "verify"
            transport.calls.clear()
            with self.assertRaises(CoreProtocolError): client.compile(self.case["request"] if component else self.request, self.limits)
            self.assertEqual(transport.calls, [])

    def test_material_dispatch_uses_finite_capability_and_preserves_all_originals(self):
        transport = InertTransport(self.case, component=True)
        client = material.PolicyComponentMaterialClient(transport)
        sentinel = object()
        # This isolates negotiation and payload routing, not material assessment.
        with patch.object(material, "_result", return_value=sentinel) as decode:
            result = client.compile(self.case["request"], self.limits)
        self.assertIs(result, sentinel)
        self.assertEqual(transport.calls[-1][1], {"request": self.case["request"], "limits": self.limits})
        self.assertEqual(decode.call_count, 1)
        self.assertTrue(material._instanced(self.case["request"]))
        self.assertTrue(material._prerequisites(self.case["request"]))
        self.assertFalse(material._multi_member(self.case["request"]))

    def test_material_machine_obligation_keeps_explicit_finite_scope_and_no_termination_claim(self):
        binding = {"schema_version": implementation.FINITE_MACHINE_BINDING_REPORT_SCHEMA,
            "profile": implementation.FINITE_MACHINE_BINDING_PROFILE, "source_admission": {"source_assessment": {
                "unresolved_obligations": ["machine_reachability_termination_and_progress"]}}}
        preservation = {"status": "checked_implementation", "binding": binding}
        report = {"preservation": preservation, "assembly_status": "pass", "context_status": "pass", "catalog": {},
            "prerequisites": {"status": "pass"}, "prerequisite_status": "pass", "all_original_obligations_discharged": True,
            "status": material.ACCEPTED_STATUS, "obligations": [{"obligation": "machine_reachability_termination_and_progress",
                "status": "discharged", "stage": "bounded_machine_semantics_and_declared_requirements", "evidence": {
                    "preservation": peer.digest(preservation), "machine_binding": peer.digest(binding),
                    "state_and_terminal_semantics": "exact_bounded_source_correspondence", "prefixes": "complete_original_domain",
                    "retained_attempt_identity": "creation_fixed_injective", "universal_termination": "not_claimed",
                    "progress": "declared_requirements_only"}}]}
        def validate(value, finite=True):
            material.material._obligations(value, material_key="assembly", accepted_status=material.ACCEPTED_STATUS,
                prerequisite_key="prerequisites", finite_machine=finite)
        validate(report)
        with self.assertRaises(CoreProtocolError): validate(report, finite=False)
        for key, value in (("universal_termination", "proved"), ("progress", "all_paths_complete")):
            changed = deepcopy(report); changed["obligations"][0]["evidence"][key] = value
            with self.subTest(key=key), self.assertRaises(CoreProtocolError): validate(changed)

    def test_material_assessment_requires_its_exact_finite_profile_and_checker(self):
        report = {key: None for key in material._REPORT_FIELDS | {"prerequisites", "prerequisite_status"}}
        report.update(schema_version="biocompiler.policy_component_material_assessment.v0.2",
            profile=material.FINITE_MACHINE_REQUEST_PROFILE, implementation="biocompiler.ocaml.policy_component_material_check.v0.7",
            resource_profile=material.RESOURCE_PROFILE, claim_scope=material.CLAIM_SCOPE, premise=material.PREMISE,
            empirical="unassessed", artifact="withheld", export="withheld")
        self.assertEqual(material._report(report, instanced=True, prerequisites=True, finite_machine=True), report)
        for key, value in (("profile", material.PREREQUISITE_REQUEST_PROFILE),
                           ("implementation", "biocompiler.ocaml.policy_component_material_check.v0.3"),
                           ("schema_version", material.REPORT_SCHEMA)):
            changed = deepcopy(report); changed[key] = value
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                material._report(changed, instanced=True, prerequisites=True, finite_machine=True)


if __name__ == "__main__": unittest.main()
