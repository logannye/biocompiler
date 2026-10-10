"""Inert prerequisite transport controls; native admission is separate evidence."""
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
    request.update(schema_version=api.PREREQUISITE_REQUEST_SCHEMA, profile=api.PREREQUISITE_REQUEST_PROFILE)
    request["implementation_request"].update(schema_version=implementation.PREREQUISITE_REQUEST_SCHEMA,
        profile=implementation.PREREQUISITE_REQUEST_PROFILE)
    return request


def capabilities(role="core"):
    value = instance.capabilities(role)
    value["profiles"]["policy_prerequisite_material"] = deepcopy(api.PREREQUISITE_PROFILE)
    value["validation_scopes"].append(api.PREREQUISITE_VALIDATION_SCOPE)
    if role == "core":
        value["profiles"]["policy_prerequisite_material_producer"] = deepcopy(api.PREREQUISITE_PRODUCER_PROFILE)
    return value


class PrerequisiteTransportTests(unittest.TestCase):
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
            lambda v: v["profiles"].pop("policy_prerequisite_material"),
            lambda v: v["profiles"].update(policy_prerequisite_material=deepcopy(api.INSTANCE_PROFILE)),
            lambda v: v["profiles"]["policy_prerequisite_material"].update(request_schema=api.INSTANCE_REQUEST_SCHEMA),
            lambda v: v["profiles"]["policy_prerequisite_material"].update(empirical="verified"),
            lambda v: v["validation_scopes"].remove(api.PREREQUISITE_VALIDATION_SCOPE),
        ]
        for mutate in mutations:
            self.calls.clear()
            with self.subTest(mutation=mutate), self.exchange(mutate), self.assertRaises(CoreProtocolError):
                self.client.check(self.request, instance.candidate(), {})
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_production_requires_new_producer_and_core_role(self):
        with self.exchange(lambda v: v["profiles"].pop("policy_prerequisite_material_producer")), self.assertRaises(CoreProtocolError):
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
        self.assertEqual(implementation._prerequisite_original(nested), nested)
        with self.assertRaises(CoreProtocolError):
            implementation._original(nested)
        with self.assertRaises(CoreProtocolError):
            implementation._prerequisite_original(instance.original()["implementation_request"])

    def test_preparation_keeps_explicit_profile_and_immutable_authority(self):
        fields = {key: deepcopy(value) for key, value in self.request.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**fields, instanced=True, prerequisites=True)
            with self.assertRaises(ValueError):
                sdk.prepare_request(**fields, prerequisites=True)
        self.assertEqual(prepared, self.request)
        fields["implementation_request"].clear()
        self.assertEqual(prepared, self.request)

    def test_pending_catalog_occurrences_retain_original_order_and_entry_pins(self):
        request = deepcopy(self.request["implementation_request"])
        entries = request["document"]["implementations"]["implementations"]
        entry = entries[0]
        dependency = {"$type": "DefinitionRef", "id": "synthetic.dependency", "version": "1", "digest": "0" * 64}
        entry["dependencies"] = [dependency, dependency | {"id": "synthetic.second"}]
        bridge = next(row for row in request["catalog_bindings"] if row["entry_id"] == entry["id"])
        bridge["entry_digest"] = digest(entry)
        expected = [{"entry_id": entry["id"], "entry_digest": digest(entry), "dependency_index": index,
                     "definition": value} for index, value in enumerate(entry["dependencies"])]
        self.assertEqual(implementation._pending_dependencies(request), expected)
        entry["dependencies"].reverse()
        with self.assertRaises(CoreProtocolError):
            implementation._pending_dependencies(request)

    def test_negative_closure_cannot_discharge_any_original_obligation(self):
        preservation = {"status": "checked_implementation", "binding": {"source_admission": {
            "source_assessment": {"unresolved_obligations": ["semantic_definition:dependency"]}}}}
        for status in ("fail", "unknown", "unsupported"):
            for stage in ("declared_context", "conditional_component_context_conjunction"):
                report = {"status": "not_accepted", "all_original_obligations_discharged": False,
                    "preservation": preservation, "assembly": {"outcome": "pass"}, "assembly_status": "pass",
                    "catalog": {}, "context": {"outcome": status}, "context_status": status,
                    "prerequisites": {"status": status}, "prerequisite_status": status}
                keys = ["context", "prerequisites"] if stage == "declared_context" else [
                    "preservation", "assembly", "context", "prerequisites"]
                report["obligations"] = [{"obligation": "semantic_definition:dependency", "status": "discharged",
                    "stage": stage, "evidence": {key: digest(report[key]) for key in keys}}]
                with self.subTest(status=status, stage=stage), self.assertRaisesRegex(CoreProtocolError, "complete checked context chain"):
                    api.material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
                        conjunction_stage="conditional_component_context_conjunction", prerequisite_key="prerequisites")
                report["obligations"][0].update(status="unresolved", stage=None, evidence=None)
                api.material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
                    conjunction_stage="conditional_component_context_conjunction", prerequisite_key="prerequisites")


if __name__ == "__main__":
    unittest.main()
