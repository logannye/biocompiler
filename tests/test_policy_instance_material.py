"""Synthetic named-instance transport controls; no native admission evidence.

The records below isolate capability/profile boundaries and retained projection
inventories. They deliberately do not model a complete native source, PM grammar,
or biological mechanism. Native original-input tests establish those contracts.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_material as api
from biocompiler.core_client import (
    CORE_VERSION, PROTOCOL, CoreClient, CoreProtocolError, CoreResponse, decode_json, encode_json,
)
from biocompiler.policy import component_material as sdk
from biocompiler.policy import research_project
from tests import test_core_policy_component_material as peer


def original():
    value = peer.original()
    value.update(schema_version=api.INSTANCE_REQUEST_SCHEMA, profile=api.INSTANCE_REQUEST_PROFILE)
    return value


def candidate():
    value = {key: {} for key in api._CANDIDATE_FIELDS}
    value.update(schema_version=api.CANDIDATE_SCHEMA, assembly_proposal={
        "schema_version": "biocompiler.policy_component_assembly_proposal.v0.2",
        "profile": api.INSTANCE_ASSEMBLY_PROFILE, "rule": {}, "nodes": [],
    })
    return value


def assessment():
    value = dict.fromkeys(api._REPORT_FIELDS)
    value.update(schema_version=api.REPORT_SCHEMA, profile=api.INSTANCE_REQUEST_PROFILE,
        implementation="biocompiler.ocaml.policy_component_material_check.v0.2",
        resource_profile=api.RESOURCE_PROFILE, claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE,
        empirical="unassessed", artifact="withheld", export="withheld")
    return value


def capabilities(role="core"):
    value = peer.capabilities(role)
    value["profiles"]["policy_instance_material"] = deepcopy(api.INSTANCE_PROFILE)
    value["validation_scopes"].append(api.INSTANCE_VALIDATION_SCOPE)
    if role == "core":
        value["profiles"]["policy_instance_material_producer"] = deepcopy(api.INSTANCE_PRODUCER_PROFILE)
    return value


def projection_records():
    """Three instances with colliding local feature IDs and a two-join link."""
    request, actual = original(), candidate()
    slots = ["sensor", "relay", 'output."quoted"']
    components, selections, roots, nodes, features, carriers = [], [], [], [], [], []
    for index, slot in enumerate(slots):
        path = {"space_id": "local", "start": 0, "end": 2}
        final_path = {"space_id": "payload", "start": 2 * index, "end": 2 * index + 2}
        identity = {"id": "mock." + str(index)}
        target = {"kind": "boundary_port", "id": "signal"}
        local = {"root": "local.root", "feature": "region", "path": path}
        components.append({"identity": identity, "body": {
            "fragment": {"boundary_ports": [{"id": "signal", "endpoint": {"node": "node", "port": "value"}}]},
            "carriers": [{"target": target, "sites": [local]}],
        }})
        selections.append({"slot": slot, "component": identity})
        roots.append({"slot": slot, "source": "source." + str(index)})
        nodes.append({"slot": slot, "node": "node", "actual": "actual." + str(index)})
        final_id = encode_json([slot, "region"]).decode("utf-8")
        features.append({"id": final_id, "path": final_path})
        projected = {"slot": slot, "root": "local.root", "source": "source." + str(index),
            "feature": "region", "final_feature": final_id, "local_path": deepcopy(path),
            "member": "payload", "path": deepcopy(final_path)}
        carriers.append({"slot": slot, "target": deepcopy(target), "sites": [projected]})
    request["component_library"] = {"components": components}
    request["composition_rule"] = {"body": {
        "components": selections, "root_bindings": roots, "material_authority": {"member_order": ["payload"]},
        "joins": [{"id": "first", "offset": 2}, {"id": "second", "offset": 4}],
        "links": [{"id": "signal.link", "producer": {"slot": slots[0], "boundary": "signal"},
                   "consumer": {"slot": slots[2], "boundary": "signal"}}],
        "link_carriers": [{"link": "signal.link", "producer_site": 0, "consumer_site": 0,
                           "joins": ["first", "second"]}],
    }}
    actual["construction"] = {"inventory": {"molecules": [{"id": "payload", "features": features}]}}
    actual["assembly_proposal"]["nodes"] = nodes
    leaf = {"outcome": "pass", "carrier_projections": carriers, "link_projections": [{
        "link": "signal.link", "joins": ["first", "second"], "offsets": [2, 4],
        "producer_endpoint": {"node": "actual.0", "port": "value"},
        "consumer_endpoint": {"node": "actual.2", "port": "value"},
        "producer": deepcopy(carriers[0]["sites"][0]), "consumer": deepcopy(carriers[2]["sites"][0]),
    }]}
    return request, actual, leaf


class PolicyInstanceMaterialTransportTests(unittest.TestCase):
    def setUp(self):
        self.request, self.candidate = original(), candidate()
        self.client = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, *, mutate=None, role="core"):
        def invoke(_binary, encoded, _timeout, _cancelled):
            invocation = decode_json(encoded)
            self.calls.append(invocation)
            operation = invocation["operation"]
            value = capabilities(role) if operation == "capabilities" else {"mock_result": True}
            if operation == "capabilities" and mutate:
                mutate(value)
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"],
                "operation": operation, "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                         "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def check(self):
        return self.client.check(self.request, self.candidate, {})

    def test_exact_instance_capabilities_route_all_four_operations(self):
        # Isolate routing: nested result acceptance has separate decoder controls.
        token = object()
        with self.exchange(), patch.object(api, "_result", return_value=token) as decode:
            self.assertIs(self.client.compile(self.request, {}), token)
            self.assertIs(self.check(), token)
            self.assertIs(self.client.replay(self.request, self.candidate, {}, {}), token)
            self.assertIs(self.client.export(self.request, self.candidate, {}), token)
        self.assertEqual([row["operation"] for row in self.calls][1::2], [
            "compile-policy-component-material", "check-policy-component-material",
            "replay-policy-component-material", "export-policy-component-material"])
        self.assertEqual(decode.call_count, 4)
        self.assertTrue(all(row["payload"]["request"] == self.request for row in self.calls[1::2]))

    def test_legacy_capability_cannot_substitute_for_exact_instance_capability(self):
        mutations = [
            lambda v: v["profiles"].pop("policy_instance_material"),
            lambda v: v["profiles"].update(policy_instance_material=deepcopy(api.PROFILE)),
            lambda v: v["profiles"]["policy_instance_material"].update(request_schema=api.REQUEST_SCHEMA),
            lambda v: v["profiles"]["policy_instance_material"].update(artifact="accepted"),
            lambda v: v["profiles"]["policy_instance_material"].update(max_result_nodes=True),
            lambda v: v["validation_scopes"].remove(api.INSTANCE_VALIDATION_SCOPE),
        ]
        for index, mutation in enumerate(mutations):
            self.calls.clear()
            with self.subTest(index=index), self.exchange(mutate=mutation), self.assertRaises(CoreProtocolError):
                self.check()
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_instance_production_requires_matching_producer_and_core_role(self):
        for mutation in (
            lambda v: v["profiles"].pop("policy_instance_material_producer"),
            lambda v: v["profiles"].update(policy_instance_material_producer=deepcopy(api.PRODUCER_PROFILE)),
        ):
            self.calls.clear()
            with self.exchange(mutate=mutation), self.assertRaises(CoreProtocolError):
                self.client.compile(self.request, {})
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])
        verify = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
            verify.compile(self.request, {})
        with self.exchange(role="verify"), patch.object(api, "_result", return_value="checked"):
            self.assertEqual(verify.check(self.request, self.candidate, {}), "checked")

    def test_request_snapshot_precedes_capability_negotiation(self):
        before = deepcopy(self.request)
        with self.exchange(mutate=lambda _: self.request.update(profile=api.REQUEST_PROFILE)), patch.object(api, "_result"):
            self.check()
        self.assertEqual(self.calls[-1]["payload"]["request"], before)

    def test_prepare_request_explicit_instance_flag_preserves_an_independent_snapshot(self):
        fields = {key: deepcopy(value) for key, value in self.request.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**fields, instanced=True)
            legacy = sdk.prepare_request(**fields)
        self.assertEqual(prepared, self.request)
        self.assertEqual((legacy["schema_version"], legacy["profile"]), (api.REQUEST_SCHEMA, api.REQUEST_PROFILE))
        for value in fields.values():
            value.clear()
        self.assertEqual(prepared, self.request)

    def test_request_schema_and_profile_cannot_be_crossmixed(self):
        for schema, profile in ((api.REQUEST_SCHEMA, api.INSTANCE_REQUEST_PROFILE),
                                (api.INSTANCE_REQUEST_SCHEMA, api.REQUEST_PROFILE)):
            request = deepcopy(self.request) | {"schema_version": schema, "profile": profile}
            with self.subTest(schema=schema), patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
                self.client.compile(request, {})

    def test_research_project_routes_instance_requests_without_relaxing_profile_checks(self):
        source = research_project.SourceRecord("mock.source", "urn:synthetic:instance-routing", "1",
            "0" * 64, "specification", "Synthetic routing test only")
        def project(request):
            return research_project.ResearchProject.from_request(project_id="mock.instances",
                title="Synthetic instance routing", request=request, limits={"max_work": 1},
                sources=(source,), assumptions=("Transport control; native admission unassessed.",))
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            for request in (peer.original(), self.request):
                prepared = project(request)
                self.assertEqual(prepared.route, "component_material")
                self.assertEqual(prepared.request, request)
                self.assertEqual(prepared.preflight().native_status, "not_run")
                prepared.request.clear()
                self.assertEqual(prepared.request, request)
            for schema, profile in ((api.REQUEST_SCHEMA, api.INSTANCE_REQUEST_PROFILE),
                                    (api.INSTANCE_REQUEST_SCHEMA, api.REQUEST_PROFILE)):
                with self.subTest(schema=schema), self.assertRaises(CoreProtocolError):
                    project(deepcopy(self.request) | {"schema_version": schema, "profile": profile})

    def test_proposal_and_assessment_profiles_are_bound_to_the_requested_family(self):
        self.assertEqual(api._candidate(self.candidate, instanced=True), self.candidate)
        self.assertEqual(api._report(assessment(), instanced=True), assessment())
        with self.assertRaises(CoreProtocolError):
            api._candidate(self.candidate)
        with self.assertRaises(CoreProtocolError):
            api._report(assessment())
        for field, wrong in (("schema_version", "biocompiler.policy_component_assembly_proposal.v0.1"),
                             ("profile", "biocompiler.policy_exact_component_assembly.v0.1")):
            value = deepcopy(self.candidate)
            value["assembly_proposal"][field] = wrong
            with self.subTest(field=field), self.assertRaises(CoreProtocolError):
                api._candidate(value, instanced=True)
        for field, wrong in (("profile", api.REQUEST_PROFILE),
                             ("implementation", "biocompiler.ocaml.policy_component_material_check.v0.1")):
            with self.subTest(field=field), self.assertRaises(CoreProtocolError):
                api._report(assessment() | {field: wrong}, instanced=True)

    def test_result_rejects_legacy_implementation_or_scope_before_nested_evidence(self):
        value = dict.fromkeys(api.material._RESULT_FIELDS)
        value.update(schema_version=api.RESULT_SCHEMA, implementation=api.INSTANCE_IMPLEMENTATION,
                     resource_profile=api.RESOURCE_PROFILE, validation_scope=api.INSTANCE_VALIDATION_SCOPE)
        for field, wrong in (("implementation", api.IMPLEMENTATION), ("validation_scope", api.VALIDATION_SCOPE)):
            response = CoreResponse("mock", "check-policy-component-material", "ok", value | {field: wrong}, (), "core", CORE_VERSION)
            with self.subTest(field=field), self.assertRaisesRegex(CoreProtocolError, "Negotiated component result"):
                api._result(response, {"request": self.request})


class PolicyInstanceProjectionTests(unittest.TestCase):
    def test_three_instances_retain_collision_free_feature_names_and_complete_join_path(self):
        request, actual, leaf = projection_records()
        api._projections(request, actual, leaf)
        identifiers = [row["sites"][0]["final_feature"] for row in leaf["carrier_projections"]]
        self.assertEqual(len(set(identifiers)), 3)
        self.assertEqual([decode_json(value.encode()) for value in identifiers],
                         [[slot, "region"] for slot in ("sensor", "relay", 'output."quoted"')])

    def test_retained_instance_feature_owner_and_coordinate_tampering_reject(self):
        mutations = [
            lambda v: v["carrier_projections"][0]["sites"][0].update(final_feature="region"),
            lambda v: v["carrier_projections"][0]["sites"][0].update(final_feature=encode_json(["relay", "region"]).decode()),
            lambda v: v["carrier_projections"][0]["sites"][0].pop("final_feature"),
            lambda v: v["carrier_projections"][0]["sites"][0].update(slot="relay"),
            lambda v: v["carrier_projections"][0]["sites"][0]["path"].update(start=1),
            lambda v: v["carrier_projections"].reverse(),
            lambda v: v["carrier_projections"].pop(),
            lambda v: v["link_projections"][0]["consumer"].update(final_feature="region"),
        ]
        for index, mutate in enumerate(mutations):
            request, actual, leaf = projection_records()
            mutate(leaf)
            with self.subTest(index=index), self.assertRaises(CoreProtocolError):
                api._projections(request, actual, leaf)

    def test_cross_link_requires_all_original_joins_in_order_and_exact_offsets(self):
        mutations = [
            lambda v: v.update(joins=["first"], offsets=[2]),
            lambda v: v.update(joins=["second", "first"], offsets=[4, 2]),
            lambda v: v.update(joins=["first", "first"], offsets=[2, 2]),
            lambda v: v.update(offsets=[2, 5]),
            lambda v: v.update(join="first", offset=2),
            lambda v: v["consumer_endpoint"].update(node="actual.0"),
        ]
        for index, mutate in enumerate(mutations):
            request, actual, leaf = projection_records()
            mutate(leaf["link_projections"][0])
            with self.subTest(index=index), self.assertRaises(CoreProtocolError):
                api._projections(request, actual, leaf)

    def test_checked_member_must_retain_each_instance_qualified_feature_once(self):
        for duplicate in (False, True):
            request, actual, leaf = projection_records()
            features = actual["construction"]["inventory"]["molecules"][0]["features"]
            if duplicate:
                features.append(deepcopy(features[0]))
            else:
                features[0]["id"] = "region"
            with self.subTest(duplicate=duplicate), self.assertRaises(CoreProtocolError):
                api._projections(request, actual, leaf)


if __name__ == "__main__":
    unittest.main()
