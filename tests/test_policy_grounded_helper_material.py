"""Hand-authored, inert helper receipt controls; no native acceptance evidence.

The small records isolate identity retention and transport boundaries. They are
not complete executable biological models or native realization fixtures.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_material as api
from biocompiler import core_policy_implementation as implementation
from biocompiler.core_client import (
    CORE_VERSION, PROTOCOL, CoreClient, CoreProtocolError, CoreResponse, decode_json, encode_json,
)
from biocompiler.policy import component_material as sdk
from tests import test_policy_instance_material as instance
from tests import test_policy_multi_member_material as multi
from tests import test_policy_prerequisite_evidence as closure_peer
from tests.test_core_policy_component_material import digest

REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.6"
PROFILE = "biocompiler.policy_grounded_helper_prerequisite_mrna.v0.1"
ASSEMBLY_PROFILE = "biocompiler.policy_grounded_helper_component_assembly.v0.1"
PROPOSAL_SCHEMA = "biocompiler.policy_component_assembly_proposal.v0.4"
REPORT_SCHEMA = "biocompiler.policy_component_material_assessment.v0.4"
SERVICE = "biocompiler.ocaml.policy_grounded_helper_prerequisite_material.v0.1"
SCOPE = "policy-grounded-helper-prerequisite-mrna-v0.1"


def original():
    value = multi.original()
    value.update(schema_version=REQUEST_SCHEMA, profile=PROFILE)
    value["context"].update(schema_version="biocompiler.policy_component_context.v0.3", profile=PROFILE)
    return value


def capabilities(role="core"):
    value = multi.capabilities(role)
    value["profiles"]["policy_grounded_helper_material"] = deepcopy(api.GROUNDED_HELPER_PROFILE)
    value["validation_scopes"].append(SCOPE)
    if role == "core":
        value["profiles"]["policy_grounded_helper_material_producer"] = deepcopy(api.GROUNDED_HELPER_PRODUCER_PROFILE)
    return value


class GroundedHelperTransportTests(unittest.TestCase):
    def setUp(self):
        self.request = original()
        self.client = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, mutate=lambda _: None, role="core"):
        def invoke(_binary, encoded, _timeout, _cancelled):
            call = decode_json(encoded)
            self.calls.append(call)
            value = capabilities(role) if call["operation"] == "capabilities" else {}
            if call["operation"] == "capabilities":
                mutate(value)
            return encode_json({"protocol": PROTOCOL, "request_id": call["request_id"],
                "operation": call["operation"], "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                         "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def test_all_four_operations_negotiate_helper_profile_and_originals(self):
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

    def test_missing_stale_or_promoted_capability_rejects_before_operation(self):
        mutations = [lambda v: v["profiles"].pop("policy_grounded_helper_material"),
            lambda v: v["profiles"].update(policy_grounded_helper_material=deepcopy(api.MULTI_MEMBER_PROFILE)),
            lambda v: v["profiles"]["policy_grounded_helper_material"].update(request_schema=api.MULTI_MEMBER_REQUEST_SCHEMA),
            lambda v: v["profiles"]["policy_grounded_helper_material"].update(empirical="verified"),
            lambda v: v["validation_scopes"].remove(SCOPE)]
        for mutate in mutations:
            self.calls.clear()
            with self.subTest(mutate=mutate), self.exchange(mutate), self.assertRaises(CoreProtocolError):
                self.client.check(self.request, instance.candidate(), {})
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_production_requires_helper_producer_and_core_role(self):
        with self.exchange(lambda v: v["profiles"].pop("policy_grounded_helper_material_producer")), self.assertRaises(CoreProtocolError):
            self.client.compile(self.request, {})
        verify = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
            verify.compile(self.request, {})
        with self.exchange(role="verify"), patch.object(api, "_result", return_value="inert"):
            self.assertEqual(verify.check(self.request, instance.candidate(), {}), "inert")

    def test_outer_and_inner_schema_boundaries_remain_distinct(self):
        mutations = [lambda r: r.update(schema_version=api.MULTI_MEMBER_REQUEST_SCHEMA),
            lambda r: r.update(profile=api.MULTI_MEMBER_REQUEST_PROFILE),
            lambda r: r["implementation_request"].update(schema_version=implementation.PREREQUISITE_REQUEST_SCHEMA),
            lambda r: r["implementation_request"].update(profile=implementation.TWO_OBSERVATION_REQUEST_PROFILE)]
        for mutate in mutations:
            value = deepcopy(self.request)
            mutate(value)
            with self.subTest(mutate=mutate), patch("subprocess.Popen", side_effect=AssertionError("No native execution")), self.assertRaises(CoreProtocolError):
                self.client.compile(value, {})
        self.assertEqual(implementation._multi_product_original(self.request["implementation_request"]), self.request["implementation_request"])

    def test_public_authoring_has_one_explicit_helper_family_option(self):
        fields = {key: deepcopy(value) for key, value in self.request.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**fields, instanced=True, prerequisites=True, grounded_helper=True)
            for flags in ({"grounded_helper": True}, {"instanced": True, "grounded_helper": True},
                          {"instanced": True, "prerequisites": True, "grounded_helper": True, "multi_member": True},
                          {"instanced": True, "prerequisites": True, "grounded_helper": True, "two_observations": True}):
                with self.subTest(flags=flags), self.assertRaises(ValueError):
                    sdk.prepare_request(**fields, **flags)
        self.assertEqual(prepared, self.request)
        fields["implementation_request"].clear()
        self.assertEqual(prepared, self.request)

    def test_request_and_replay_snapshots_precede_negotiation(self):
        candidate, saved = instance.candidate(), {"synthetic_receipt": ["original"]}
        before = deepcopy((self.request, candidate, saved))
        def mutate(_):
            self.request.clear()
            candidate.clear()
            saved.clear()
        with self.exchange(mutate), patch.object(api, "_result"):
            self.client.replay(self.request, candidate, {}, saved)
        payload = self.calls[-1]["payload"]
        self.assertEqual((payload["request"], payload["candidate"], payload["report"]), before)

    def test_replay_does_not_substitute_for_fresh_export(self):
        with self.exchange(), patch.object(api, "_result"):
            self.client.replay(self.request, instance.candidate(), {}, {"untrusted": "saved"})
            self.client.export(self.request, instance.candidate(), {})
        self.assertIn("report", self.calls[1]["payload"])
        self.assertNotIn("report", self.calls[3]["payload"])
        self.assertEqual(self.calls[3]["operation"], "export-policy-component-material")

    def test_research_project_and_result_family_cannot_fall_back(self):
        from biocompiler.policy import research_project
        source = research_project.SourceRecord("mock.helper", "urn:synthetic:grounded-helper", "1", "0" * 64,
            "specification", "Inert routing control only")
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            project = research_project.ResearchProject.from_request(project_id="mock.helper", title="Synthetic helper",
                request=self.request, limits={"max_work": 1}, sources=(source,), assumptions=("Inert control",))
            self.assertEqual(project.route, "component_material")
            self.assertEqual(project.preflight().native_status, "not_run")
        result = dict.fromkeys(api.material._RESULT_FIELDS)
        result.update(schema_version=api.RESULT_SCHEMA, implementation=SERVICE,
                      resource_profile=api.RESOURCE_PROFILE, validation_scope=SCOPE)
        for key, wrong in (("implementation", api.MULTI_MEMBER_IMPLEMENTATION), ("validation_scope", api.MULTI_MEMBER_VALIDATION_SCOPE)):
            response = CoreResponse("mock", "check-policy-component-material", "ok", result | {key: wrong}, (), "core", CORE_VERSION)
            with self.subTest(key=key), self.assertRaisesRegex(CoreProtocolError, "Negotiated component result"):
                api._result(response, {"request": self.request})

    def test_new_assessment_requires_full_internal_family_flags(self):
        report = instance.assessment()
        report.update(schema_version=REPORT_SCHEMA, profile=PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.6",
            prerequisites=None, prerequisite_status="unassessed")
        good = dict(instanced=True, prerequisites=True, multi_member=True, grounded_helper=True)
        self.assertEqual(api._report(report, **good), report)
        for flags in ({}, {"instanced": True, "prerequisites": True, "multi_member": True},
                      {**good, "multi_member": False}, {**good, "two_observations": True}):
            with self.subTest(flags=flags), self.assertRaises(CoreProtocolError):
                api._report(report, **flags)


def model_pin(name, body):
    return {"schema_version": "biocompiler.component_identity.v0.1", "kind": "model", "id": name,
            "version": "1", "content_fingerprint": digest(body)}


def helper_records():
    request, candidate, assembly, context = multi.projection_records()
    request.update(schema_version=REQUEST_SCHEMA, profile=PROFILE)
    original_context = request["context"]
    original_context.update(schema_version="biocompiler.policy_component_context.v0.3", profile=PROFILE)
    capability = {"$type": "DefinitionRef", "id": "helper.capacity", "version": "1", "digest": "a" * 64}
    product = {"identity": model_pin("helper.product", {"sequence": "M"}), "sequence": "M",
               "translation_policy": {"synthetic": "standard"}, "provenance": {"synthetic": "original"}}
    molecule = {"id": "rna.helper", "sequence": "ACGU", "features": [
        {"id": region, "path": {"space_id": "rna.helper", "start": i, "end": i + 1}}
        for i, region in enumerate(("u5", "cds", "u3", "tail"))], "chemistry": {"synthetic": "root-derived"}}
    root_molecule = deepcopy(molecule)
    root_molecule["id"] = "helper.local"
    for feature in root_molecule["features"]:
        feature["path"]["space_id"] = "helper.local"
    root = {"id": "helper.root", "molecule": root_molecule, "provenance": {"synthetic": "original"}}
    body = {"root": root, "regions": dict(zip(("utr5", "cds", "utr3", "poly_a"), ("u5", "cds", "u3", "tail"))),
            "product": product, "chemistry": root_molecule["chemistry"], "capability": capability, "prerequisites": []}
    material = {"schema_version": "biocompiler.policy_helper_material.v0.1",
                "profile": "biocompiler.policy_grounded_helper_rna.v0.1",
                "identity": model_pin("helper.material", body), "body": body}
    selection = {"source": "root.helper", "member": "rna.helper", "material": material}
    placement = {"id": "placement.helper", "member_id": "rna.helper"}
    declaration = {"schema_version": "biocompiler.architecture_helper.v0.1", "id": "helper",
        "capability": "helper.capacity", "consumer_component_ids": ["first", "second"], "recipient_role": "executor",
        "compartment": "cytosol", "availability": "other_rna", "initialization": "after_expression",
        "sharing": "shared", "capacity": 2, "assumptions": [], "placement_id": "placement.helper",
        "provider_component_id": "helper.material", "depends_on": []}
    delivery = deepcopy(context["member_allocations"][0]["delivery"])
    bootstrap = {"profile": "biocompiler.policy_source_independent_expression_completion.v0.1",
                 "completion": {"earliest": "1", "latest": "1"}, "prerequisites": []}
    available = {"onset_min": "1", "onset_max": "1", "duration_min": "8", "duration_max": "8"}
    provider_body = {"kind": "helper", "definition": capability,
        "material": material["identity"], "environment": {"id": "environment"}, "delivery": delivery["definition"],
        "capacity_profile": "biocompiler.policy_supplied_grounded_helper_capacity.v0.1", "bootstrap": bootstrap,
        "recipient": {"role": "executor", "identity": "cell", "compartment": "cytosol"}, "availability": available,
        "capacities": [{"id": "retained", "pool_id": "shared.retained", "unit": "retained_correlation_records",
            "scope": "per_executor", "quantity": 8, "slots": [], "record_layout_digest": "b" * 64, "availability": available}]}
    provider = {"schema_version": "biocompiler.policy_material_provider.v0.3",
                "identity": model_pin("helper.provider", provider_body), "body": provider_body}
    allocations = [{"demand": {"owner": {"kind": "node", "slot": slot, "node": "attempt"},
        "unit": "retained_correlation_records", "scope": "per_executor", "quantity": 4},
        "provider": capability, "capacity": "retained", "pool": "shared.retained", "reserved": 4}
        for slot in ("first", "second")]
    request["composition_rule"]["body"]["helper"] = selection
    request["composition_rule"]["body"]["material_authority"]["member_order"].append("rna.helper")
    original_context["helpers"] = [declaration]
    original_context["placements"].append(placement)
    original_context["providers"].append(provider)
    candidate["assembly_proposal"].update(schema_version=PROPOSAL_SCHEMA, profile=ASSEMBLY_PROFILE)
    candidate["construction"]["inventory"]["molecules"].append(molecule)
    assembly["structure"] = {"outcome": "pass"}
    assembly["helper_projections"] = [{"material": material, "source": "root.helper", "member": "rna.helper",
        "product": product, "root_fingerprint": digest(root), "molecule_fingerprint": digest(molecule)}]
    context["resource_allocations"] = allocations
    context["helper_allocations"] = [{"helper": declaration, "material": material["identity"], "capability": capability,
        "source": "root.helper", "member": "rna.helper", "placement": placement, "molecule_fingerprint": digest(molecule),
        "provider": provider["identity"], "provider_body": provider_body, "bootstrap": bootstrap, "delivery": delivery,
        "consumers": ["first", "second"], "resource_allocations": deepcopy(allocations)}]
    return deepcopy(request), deepcopy(candidate), deepcopy(assembly), deepcopy(context)


class GroundedHelperEvidenceTests(unittest.TestCase):
    def test_exact_third_material_and_separate_helper_allocation_are_retained(self):
        request, candidate, assembly, context = helper_records()
        api._candidate(candidate, instanced=True, multi_member=True, grounded_helper=True)
        api._projections(request, candidate, assembly)
        api._member_transport_inventory(request, candidate, context)
        api._helper_inventory(request, candidate, context)
        self.assertEqual(len(context["member_allocations"]), 2)
        self.assertEqual(len(context["helper_allocations"]), 1)

    def test_assembly_failure_retains_helper_projection_after_structure_pass(self):
        request, candidate, assembly, _ = helper_records()
        assembly.update(outcome="fail", diagnostics=["synthetic_other_carrier_failure"])
        api._projections(request, candidate, assembly)
        assembly["helper_projections"] = []
        with self.assertRaises(CoreProtocolError):
            api._projections(request, candidate, assembly)

    def test_unavailable_structure_keeps_empty_helper_projection(self):
        request, candidate, assembly, _ = helper_records()
        assembly.update(outcome="fail", structure={"outcome": "fail"}, helper_projections=[])
        api._projections(request, candidate, assembly)

    def test_prior_proposal_family_cannot_admit_helper(self):
        _, candidate, _, _ = helper_records()
        for flags in ({}, {"instanced": True}, {"instanced": True, "multi_member": True}):
            with self.subTest(flags=flags), self.assertRaises(CoreProtocolError):
                api._candidate(candidate, **flags)

    def test_projection_requires_exact_original_material_product_root_and_member(self):
        changes = [lambda row: row.update(source="other"), lambda row: row.update(member="rna.first"),
            lambda row: row["material"]["body"].update(prerequisites=["hidden"]),
            lambda row: row["product"].update(sequence="W"), lambda row: row.update(root_fingerprint="0" * 64),
            lambda row: row.update(molecule_fingerprint="0" * 64), lambda row: row.update(extra="ignored")]
        for change in changes:
            request, candidate, assembly, _ = helper_records()
            change(assembly["helper_projections"][0])
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._projections(request, candidate, assembly)

    def test_deletion_duplication_and_replacement_of_helper_evidence_reject(self):
        for field, check in (("helper_projections", api._projections), ("helper_allocations", api._helper_inventory)):
            for edit in (lambda rows: rows.clear(), lambda rows: rows.append(deepcopy(rows[0]))):
                request, candidate, assembly, context = helper_records()
                leaf = assembly if field == "helper_projections" else context
                edit(leaf[field])
                with self.subTest(field=field, edit=edit), self.assertRaises(CoreProtocolError):
                    check(request, candidate, leaf)

    def test_complete_helper_bootstrap_delivery_and_capacity_receipts_are_bound(self):
        changes = [lambda row: row["helper"].update(initialization="after_trigger"),
            lambda row: row.update(material={"id": "substitute"}), lambda row: row.update(capability={"id": "other"}),
            lambda row: row.update(source="payload.root"), lambda row: row.update(member="rna.first"),
            lambda row: row["placement"].update(member_id="rna.second"), lambda row: row.update(molecule_fingerprint="0" * 64),
            lambda row: row.update(provider={"id": "other"}), lambda row: row["provider_body"].update(capacity_profile="empirical"),
            lambda row: row["bootstrap"]["completion"].update(latest="99"),
            lambda row: row["delivery"]["body"]["expression"].update(latest=100),
            lambda row: row["consumers"].reverse(), lambda row: row["resource_allocations"].pop(),
            lambda row: row["resource_allocations"][0].update(reserved=0), lambda row: row.update(extra="ignored")]
        for change in changes:
            request, candidate, _, context = helper_records()
            change(context["helper_allocations"][0])
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._helper_inventory(request, candidate, context)

    def test_old_originals_cannot_be_reused_with_changed_helper_molecule(self):
        request, candidate, assembly, context = helper_records()
        candidate["construction"]["inventory"]["molecules"][-1]["sequence"] = "AAAA"
        with self.assertRaises(CoreProtocolError):
            api._projections(request, candidate, assembly)
        with self.assertRaises(CoreProtocolError):
            api._helper_inventory(request, candidate, context)

    def test_early_negative_context_retains_no_helper_acceptance(self):
        for status in ("fail", "unknown", "unsupported"):
            request, candidate, _, context = helper_records()
            context.update(outcome=status, helper_allocations=[])
            api._helper_inventory(request, candidate, context)
            context["helper_allocations"] = [{"invented": "partial acceptance"}]
            with self.subTest(status=status), self.assertRaises(CoreProtocolError):
                api._helper_inventory(request, candidate, context)


def closure_records():
    request, report = closure_peer.records()
    request.update(schema_version=REQUEST_SCHEMA, profile=PROFILE)
    original_request = request["implementation_request"]
    original_request.update(schema_version=implementation.MULTI_PRODUCT_REQUEST_SCHEMA,
                            profile=implementation.MULTI_PRODUCT_REQUEST_PROFILE)
    document = original_request["document"]
    definition = {"$type": "SemanticDefinition", "id": "helper", "version": "1", "category": "capability"}
    reference = {"$type": "DefinitionRef", "id": "helper", "version": "1", "digest": digest(definition)}
    document["program"]["semantics"]["definitions"].append(definition)
    refs = {p["body"]["definition"]["id"]: p["body"]["definition"] for p in request["context"]["providers"]}
    body = {"kind": "helper", "definition": reference, "environment": refs["environment"], "delivery": refs["delivery"]}
    provider = {"identity": model_pin("helper.provider", body), "body": body}
    request["context"]["providers"].append(provider)
    entry = document["implementations"]["implementations"][0]
    entry["dependencies"].append(reference)
    original_request["catalog_bindings"][0]["entry_digest"] = digest(entry)
    closure = report["prerequisites"]
    closure.update(schema_version="biocompiler.policy_provider_prerequisite_closure.v0.3", profile=PROFILE,
        original_request_fingerprint=digest(request), source_catalog=document["implementations"],
        member_allocations=[], transport_allocations=[], helper_allocations=[])
    pending = [{"entry_id": "catalog", "entry_digest": digest(entry), "dependency_index": i, "definition": ref}
               for i, ref in enumerate(entry["dependencies"])]
    closure["pending_dependencies"] = pending
    closure["providers"].append({"definition": reference, "identity": provider["identity"], "body_fingerprint": digest(body)})
    graph = closure["graph"]
    graph.update(schema_version="biocompiler.policy_provider_dependency_graph.v0.3", pending_dependencies=deepcopy(pending))
    graph["roots"][-1]["origin"]["entry_digest"] = digest(entry)
    graph["roots"].append({"origin": {"kind": "catalog_dependency", "entry_id": "catalog", "entry_digest": digest(entry),
                                     "dependency_index": 1}, "definition": reference})
    graph["nodes"].append({"definition": reference, "provider": provider["identity"]})
    graph["edges"].extend([{"source": reference, "relation": "helper_" + name, "index": 0, "target": refs[name]}
                           for name in ("environment", "delivery")])
    report["context"].update(member_allocations=[], transport_allocations=[], helper_allocations=[])
    closure_peer.sync(report)
    return deepcopy(request), deepcopy(report)


class GroundedHelperClosureTests(unittest.TestCase):
    def test_helper_dependency_edges_retain_original_definition_and_provider(self):
        request, report = closure_records()
        api._prerequisite_evidence(request, report)
        self.assertEqual([row["relation"] for row in report["prerequisites"]["graph"]["edges"][-2:]],
                         ["helper_environment", "helper_delivery"])

    def test_graph_and_closure_prior_schema_cannot_substitute(self):
        for target in ("closure", "graph"):
            request, report = closure_records()
            value = report["prerequisites"] if target == "closure" else report["prerequisites"]["graph"]
            value["schema_version"] = ("biocompiler.policy_provider_prerequisite_closure.v0.2" if target == "closure"
                                       else "biocompiler.policy_provider_dependency_graph.v0.2")
            closure_peer.sync(report)
            with self.subTest(target=target), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_changed_missing_or_duplicated_helper_edge_rejects(self):
        changes = [lambda graph: graph["edges"].pop(), lambda graph: graph["edges"].append(deepcopy(graph["edges"][-1])),
            lambda graph: graph["edges"][-1].update(relation="interface_environment"),
            lambda graph: graph["edges"][-1].update(index=1),
            lambda graph: graph["edges"][-1]["target"].update(digest="0" * 64),
            lambda graph: graph["nodes"][-1].update(provider={"id": "invented"})]
        for change in changes:
            request, report = closure_records()
            change(report["prerequisites"]["graph"])
            closure_peer.sync(report)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_context_closure_helper_allocation_copy_is_exact(self):
        request, report = closure_records()
        report["context"]["helper_allocations"] = [{"forged": "capacity"}]
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)

    def test_missing_helper_provider_retains_unknown_without_invented_edges(self):
        request, report = closure_records()
        request["context"]["providers"].pop()
        closure = report["prerequisites"]
        closure["providers"].pop()
        graph = closure["graph"]
        graph["nodes"][-1]["provider"] = None
        graph["edges"] = graph["edges"][:-2]
        graph["issues"] = [{"kind": "missing", "code": "prerequisite_provider_missing",
                            "references": [graph["nodes"][-1]["definition"]]}]
        closure["original_request_fingerprint"] = digest(request)
        closure["input_allocations"] = []
        closure_peer.outcome(report, "unknown", "prerequisite_provider_missing")
        api._prerequisite_evidence(request, report)
        closure["complete"] = True
        closure_peer.sync(report)
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)

    def test_early_fail_and_unsupported_do_not_promote_helper_closure(self):
        for status in ("fail", "unsupported"):
            request, report = closure_records()
            report["prerequisites"]["input_allocations"] = []
            closure_peer.outcome(report, status, "synthetic_helper_negative")
            api._prerequisite_evidence(request, report)


if __name__ == "__main__":
    unittest.main()
