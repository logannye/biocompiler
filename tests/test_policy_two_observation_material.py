"""Inert two-observation transport controls; native acceptance is separate."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_material as api
from biocompiler import core_policy_implementation as implementation
from biocompiler.core_client import CoreClient, CoreProtocolError, CORE_VERSION, PROTOCOL, encode_json, decode_json
from biocompiler.policy import component_material as sdk
from tests import test_policy_instance_material as instance
from tests.test_core_policy_component_material import digest


def original():
    request = instance.original()
    request.update(schema_version=api.TWO_OBSERVATION_REQUEST_SCHEMA, profile=api.TWO_OBSERVATION_REQUEST_PROFILE)
    request["implementation_request"].update(schema_version=implementation.TWO_OBSERVATION_REQUEST_SCHEMA,
        profile=implementation.TWO_OBSERVATION_REQUEST_PROFILE)
    request["context"]["profile"] = api.TWO_OBSERVATION_REQUEST_PROFILE
    return request


def capabilities(role="core"):
    value = instance.capabilities(role)
    value["profiles"]["policy_two_observation_material"] = deepcopy(api.TWO_OBSERVATION_PROFILE)
    value["validation_scopes"].append(api.TWO_OBSERVATION_VALIDATION_SCOPE)
    if role == "core":
        value["profiles"]["policy_two_observation_material_producer"] = deepcopy(api.TWO_OBSERVATION_PRODUCER_PROFILE)
    return value


class TwoObservationTransportTests(unittest.TestCase):
    def setUp(self):
        self.request = original()
        self.client = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, mutation=lambda _: None, role="core"):
        def invoke(_binary, encoded, _timeout, _cancelled):
            call = decode_json(encoded)
            self.calls.append(call)
            value = capabilities(role) if call["operation"] == "capabilities" else {}
            if call["operation"] == "capabilities":
                mutation(value)
            return encode_json({"protocol": PROTOCOL, "request_id": call["request_id"],
                "operation": call["operation"], "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                         "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def test_all_four_operations_require_exact_new_capability(self):
        token = object()
        with self.exchange(), patch.object(api, "_result", return_value=token):
            self.assertIs(self.client.compile(self.request, {}), token)
            self.assertIs(self.client.check(self.request, instance.candidate(), {}), token)
            self.assertIs(self.client.replay(self.request, instance.candidate(), {}, {}), token)
            self.assertIs(self.client.export(self.request, instance.candidate(), {}), token)
        self.assertEqual([row["operation"] for row in self.calls][1::2], [
            "compile-policy-component-material", "check-policy-component-material",
            "replay-policy-component-material", "export-policy-component-material"])
        self.assertTrue(all(row["payload"]["request"] == self.request for row in self.calls[1::2]))

    def test_prior_profiles_and_promoted_claims_cannot_substitute(self):
        mutations = [
            lambda v: v["profiles"].pop("policy_two_observation_material"),
            lambda v: v["profiles"].update(policy_two_observation_material=deepcopy(api.INSTANCE_PROFILE)),
            lambda v: v["profiles"]["policy_two_observation_material"].update(request_schema=api.INSTANCE_REQUEST_SCHEMA),
            lambda v: v["profiles"]["policy_two_observation_material"].update(empirical="verified"),
            lambda v: v["validation_scopes"].remove(api.TWO_OBSERVATION_VALIDATION_SCOPE),
        ]
        for mutate in mutations:
            self.calls.clear()
            with self.subTest(mutation=mutate), self.exchange(mutate), self.assertRaises(CoreProtocolError):
                self.client.check(self.request, instance.candidate(), {})
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_production_requires_new_producer_and_core_role(self):
        with self.exchange(lambda v: v["profiles"].pop("policy_two_observation_material_producer")), self.assertRaises(CoreProtocolError):
            self.client.compile(self.request, {})
        verify = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
            verify.compile(self.request, {})
        with self.exchange(role="verify"), patch.object(api, "_result", return_value="checked"):
            self.assertEqual(verify.check(self.request, instance.candidate(), {}), "checked")

    def test_nested_and_outer_versions_cannot_be_crossmixed(self):
        mutations = [
            lambda r: r.update(schema_version=api.INSTANCE_REQUEST_SCHEMA),
            lambda r: r.update(profile=api.INSTANCE_REQUEST_PROFILE),
            lambda r: r["implementation_request"].update(schema_version=implementation.REQUEST_SCHEMA),
            lambda r: r["implementation_request"].update(profile=implementation.REQUEST_PROFILE),
        ]
        for mutate in mutations:
            request = deepcopy(self.request)
            mutate(request)
            with self.subTest(mutation=mutate), patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
                self.client.compile(request, {})

    def test_legacy_implementation_entrypoint_rejects_new_nested_authority(self):
        nested = self.request["implementation_request"]
        self.assertEqual(implementation._two_observation_original(nested), nested)
        with self.assertRaises(CoreProtocolError):
            implementation._original(nested)
        with self.assertRaises(CoreProtocolError):
            implementation._two_observation_original(instance.original()["implementation_request"])

    def test_preparation_keeps_explicit_profile_and_immutable_authority(self):
        fields = {key: deepcopy(value) for key, value in self.request.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**fields, instanced=True, prerequisites=True, two_observations=True)
            with self.assertRaises(ValueError):
                sdk.prepare_request(**fields, two_observations=True)
        self.assertEqual(prepared, self.request)
        fields["implementation_request"].clear()
        self.assertEqual(prepared, self.request)

    def test_research_project_and_result_family_are_explicit(self):
        from biocompiler.policy import research_project
        from biocompiler.core_client import CoreResponse
        source = research_project.SourceRecord("mock.source", "urn:synthetic:two-observation", "1",
            "0" * 64, "specification", "Synthetic routing control only")
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            project = research_project.ResearchProject.from_request(project_id="mock.two-observations",
                title="Synthetic routing", request=self.request, limits={"max_work": 1}, sources=(source,),
                assumptions=("Transport control only.",))
            self.assertEqual(project.route, "component_material")
            self.assertEqual(project.request, self.request)
            self.assertEqual(project.preflight().native_status, "not_run")
        value = dict.fromkeys(api.material._RESULT_FIELDS)
        value.update(schema_version=api.RESULT_SCHEMA, implementation=api.TWO_OBSERVATION_IMPLEMENTATION,
                     resource_profile=api.RESOURCE_PROFILE, validation_scope=api.TWO_OBSERVATION_VALIDATION_SCOPE)
        for field, wrong in (("implementation", api.PREREQUISITE_IMPLEMENTATION),
                             ("validation_scope", api.PREREQUISITE_VALIDATION_SCOPE)):
            response = CoreResponse("mock", "check-policy-component-material", "ok", value | {field: wrong}, (), "core", CORE_VERSION)
            with self.subTest(field=field), self.assertRaisesRegex(CoreProtocolError, "Negotiated component result"):
                api._result(response, {"request": self.request})

    def test_assessment_version_cannot_cross_the_prerequisite_boundary(self):
        report = instance.assessment()
        report.update(schema_version="biocompiler.policy_component_material_assessment.v0.2",
            profile=api.TWO_OBSERVATION_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.4",
            prerequisites=None, prerequisite_status="unassessed")
        self.assertEqual(api._report(report, instanced=True, prerequisites=True, two_observations=True), report)
        for flags in ({}, {"instanced": True}, {"instanced": True, "prerequisites": True}, {"two_observations": True}):
            with self.subTest(flags=flags), self.assertRaises(CoreProtocolError):
                api._report(report, **flags)
        for key, wrong in (("implementation", "biocompiler.ocaml.policy_component_material_check.v0.3"),
                           ("profile", api.PREREQUISITE_REQUEST_PROFILE)):
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api._report(report | {key: wrong}, instanced=True, prerequisites=True, two_observations=True)

    def test_closure_family_and_negative_statuses_remain_bound(self):
        from tests import test_policy_prerequisite_evidence as peer
        # Synthetic provider records isolate retained identity and outcome
        # checks. Native observation admission is deliberately outside this test.
        request, report = peer.records()
        request.update(schema_version=api.TWO_OBSERVATION_REQUEST_SCHEMA, profile=api.TWO_OBSERVATION_REQUEST_PROFILE)
        request["implementation_request"].update(schema_version=implementation.TWO_OBSERVATION_REQUEST_SCHEMA,
            profile=implementation.TWO_OBSERVATION_REQUEST_PROFILE)
        closure = report["prerequisites"]
        closure.update(profile=api.TWO_OBSERVATION_REQUEST_PROFILE, original_request_fingerprint=peer.pin(request))
        peer.sync(report)
        api._prerequisite_evidence(request, report)
        closure["profile"] = api.PREREQUISITE_REQUEST_PROFILE
        peer.sync(report)
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)
        closure["profile"] = api.TWO_OBSERVATION_REQUEST_PROFILE
        for status in ("fail", "unknown", "unsupported"):
            peer.outcome(report, status, "synthetic_negative_boundary")
            api._prerequisite_evidence(request, report)
            closure["complete"] = True
            peer.sync(report)
            with self.subTest(status=status), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_inner_authoring_requires_explicit_prerequisites(self):
        from biocompiler.policy.implementation import prepare_request
        from biocompiler import policy as p
        request = self.request["implementation_request"]
        document = p.from_data(request["document"], p.BuildRequest)
        fields = {key: deepcopy(value) for key, value in request.items()
                  if key not in ("schema_version", "profile", "document")}
        with self.assertRaises(ValueError):
            prepare_request(document, **fields, two_observations=True)
        prepared = prepare_request(document, **fields, prerequisites=True, two_observations=True)
        self.assertEqual(prepared, request)
        with self.assertRaises(CoreProtocolError):
            implementation._prerequisite_original(prepared)


class TwoObservationAnchorTests(unittest.TestCase):
    def setUp(self):
        self.proposed = {"observations": [
            {"source": "condition_a", "bank": "bank_a", "input": "input_a"},
            {"source": "condition_b", "bank": "bank_b", "input": "input_b"}]}
        self.graph = {"nodes": [{"id": "bank_a", "model": {"id": "first"}},
                                  {"id": "bank_b", "model": {"id": "second"}}],
                      "inputs": [{"id": "input_" + name, "kind": "evidence",
                                  "consumer": {"node": "bank_" + name, "port": "samples"}}
                                 for name in ("a", "b")]}
        self.library = {"models": [{"identity": {"id": name}, "body": {"primitive": "evidence_bank"}}
                                   for name in ("first", "second")]}
        self.outputs = [{"node": "bank_" + name, "operation": "evidence_bank"} for name in ("a", "b")]
        self.declarations = [{"$type": "Observation", "id": "condition_" + name} for name in ("a", "b")]

    def check(self):
        implementation._two_observation_anchors(self.proposed, self.graph, self.library,
                                                self.outputs, self.declarations)

    def test_complete_two_original_identities_are_retained(self):
        self.check()

    def test_rule_input_order_may_differ_without_changing_source_mapping(self):
        self.graph["inputs"].reverse()
        self.check()

    def test_anchor_cardinality_uniqueness_and_original_order_are_exact(self):
        changes = [lambda a: a.pop(), lambda a: a.reverse(), lambda a: a.append(deepcopy(a[0]))]
        changes += [lambda a, key=key: a[1].update({key: a[0][key]}) for key in ("source", "bank", "input")]
        changes += [lambda a: a[0].update(extra="ignored"), lambda a: a[1].update(source="other")]
        for change in changes:
            self.setUp()
            change(self.proposed["observations"])
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                self.check()

    def test_actual_bank_input_and_report_orders_bind_originals(self):
        changes = [lambda: self.graph["nodes"].reverse(),
                   lambda: self.outputs.reverse(), lambda: self.graph["inputs"].pop(),
                   lambda: self.graph["inputs"][1]["consumer"].update(node="bank_a"),
                   lambda: self.library["models"].pop(),
                   lambda: self.library["models"][0]["body"].update(primitive="all2")]
        for change in changes:
            self.setUp()
            change()
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                self.check()


if __name__ == "__main__":
    unittest.main()
