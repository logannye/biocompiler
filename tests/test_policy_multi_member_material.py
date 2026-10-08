"""Inert multi-member transport controls; native acceptance is separate."""
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
    request.update(schema_version=api.MULTI_MEMBER_REQUEST_SCHEMA, profile=api.MULTI_MEMBER_REQUEST_PROFILE)
    request["implementation_request"].update(schema_version=implementation.MULTI_PRODUCT_REQUEST_SCHEMA,
        profile=implementation.MULTI_PRODUCT_REQUEST_PROFILE)
    request["context"]["profile"] = api.MULTI_MEMBER_REQUEST_PROFILE
    return request


def capabilities(role="core"):
    value = instance.capabilities(role)
    value["profiles"]["policy_multi_member_material"] = deepcopy(api.MULTI_MEMBER_PROFILE)
    value["validation_scopes"].append(api.MULTI_MEMBER_VALIDATION_SCOPE)
    if role == "core":
        value["profiles"]["policy_multi_member_material_producer"] = deepcopy(api.MULTI_MEMBER_PRODUCER_PROFILE)
    return value


class MultiMemberTransportTests(unittest.TestCase):
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
            lambda v: v["profiles"].pop("policy_multi_member_material"),
            lambda v: v["profiles"].update(policy_multi_member_material=deepcopy(api.INSTANCE_PROFILE)),
            lambda v: v["profiles"]["policy_multi_member_material"].update(request_schema=api.INSTANCE_REQUEST_SCHEMA),
            lambda v: v["profiles"]["policy_multi_member_material"].update(empirical="verified"),
            lambda v: v["validation_scopes"].remove(api.MULTI_MEMBER_VALIDATION_SCOPE),
        ]
        for mutate in mutations:
            self.calls.clear()
            with self.subTest(mutation=mutate), self.exchange(mutate), self.assertRaises(CoreProtocolError):
                self.client.check(self.request, instance.candidate(), {})
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_production_requires_new_producer_and_core_role(self):
        with self.exchange(lambda v: v["profiles"].pop("policy_multi_member_material_producer")), self.assertRaises(CoreProtocolError):
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
        self.assertEqual(implementation._multi_product_original(nested), nested)
        with self.assertRaises(CoreProtocolError):
            implementation._original(nested)
        with self.assertRaises(CoreProtocolError):
            implementation._multi_product_original(instance.original()["implementation_request"])

    def test_preparation_keeps_explicit_profile_and_immutable_authority(self):
        fields = {key: deepcopy(value) for key, value in self.request.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**fields, instanced=True, prerequisites=True, multi_member=True)
            with self.assertRaises(ValueError):
                sdk.prepare_request(**fields, multi_member=True)
        self.assertEqual(prepared, self.request)
        fields["implementation_request"].clear()
        self.assertEqual(prepared, self.request)

    def test_research_project_and_result_family_are_explicit(self):
        from biocompiler.policy import research_project
        from biocompiler.core_client import CoreResponse
        source = research_project.SourceRecord("mock.source", "urn:synthetic:multi-member", "1",
            "0" * 64, "specification", "Synthetic routing control only")
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            project = research_project.ResearchProject.from_request(project_id="mock.multi-members",
                title="Synthetic routing", request=self.request, limits={"max_work": 1}, sources=(source,),
                assumptions=("Transport control only.",))
            self.assertEqual(project.route, "component_material")
            self.assertEqual(project.request, self.request)
            self.assertEqual(project.preflight().native_status, "not_run")
        value = dict.fromkeys(api.material._RESULT_FIELDS)
        value.update(schema_version=api.RESULT_SCHEMA, implementation=api.MULTI_MEMBER_IMPLEMENTATION,
                     resource_profile=api.RESOURCE_PROFILE, validation_scope=api.MULTI_MEMBER_VALIDATION_SCOPE)
        for field, wrong in (("implementation", api.PREREQUISITE_IMPLEMENTATION),
                             ("validation_scope", api.PREREQUISITE_VALIDATION_SCOPE)):
            response = CoreResponse("mock", "check-policy-component-material", "ok", value | {field: wrong}, (), "core", CORE_VERSION)
            with self.subTest(field=field), self.assertRaisesRegex(CoreProtocolError, "Negotiated component result"):
                api._result(response, {"request": self.request})

    def test_assessment_version_cannot_cross_the_prerequisite_boundary(self):
        report = instance.assessment()
        report.update(schema_version="biocompiler.policy_component_material_assessment.v0.3",
            profile=api.MULTI_MEMBER_REQUEST_PROFILE,
            implementation="biocompiler.ocaml.policy_component_material_check.v0.5",
            prerequisites=None, prerequisite_status="unassessed")
        self.assertEqual(api._report(report, instanced=True, prerequisites=True, multi_member=True), report)
        for flags in ({}, {"instanced": True}, {"instanced": True, "prerequisites": True}, {"two_observations": True}):
            with self.subTest(flags=flags), self.assertRaises(CoreProtocolError):
                api._report(report, **flags)
        for key, wrong in (("implementation", "biocompiler.ocaml.policy_component_material_check.v0.3"),
                           ("profile", api.PREREQUISITE_REQUEST_PROFILE)):
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api._report(report | {key: wrong}, instanced=True, prerequisites=True, multi_member=True)

    def test_closure_family_and_negative_statuses_remain_bound(self):
        from tests import test_policy_prerequisite_evidence as peer
        # Synthetic provider records isolate retained identity and outcome
        # checks. Native observation admission is deliberately outside this test.
        request, report = peer.records()
        request.update(schema_version=api.MULTI_MEMBER_REQUEST_SCHEMA, profile=api.MULTI_MEMBER_REQUEST_PROFILE)
        request["implementation_request"].update(schema_version=implementation.MULTI_PRODUCT_REQUEST_SCHEMA,
            profile=implementation.MULTI_PRODUCT_REQUEST_PROFILE)
        closure = report["prerequisites"]
        closure.update(schema_version="biocompiler.policy_provider_prerequisite_closure.v0.2",
            profile=api.MULTI_MEMBER_REQUEST_PROFILE, original_request_fingerprint=peer.pin(request),
            member_allocations=[], transport_allocations=[])
        closure["graph"]["schema_version"] = "biocompiler.policy_provider_dependency_graph.v0.2"
        report["context"].update(member_allocations=[], transport_allocations=[])
        peer.sync(report)
        api._prerequisite_evidence(request, report)
        closure["profile"] = api.PREREQUISITE_REQUEST_PROFILE
        peer.sync(report)
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)
        closure["profile"] = api.MULTI_MEMBER_REQUEST_PROFILE
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
            prepare_request(document, **fields, multi_product=True)
        prepared = prepare_request(document, **fields, prerequisites=True, multi_product=True)
        self.assertEqual(prepared, request)
        with self.assertRaises(CoreProtocolError):
            implementation._prerequisite_original(prepared)



def projection_records():
    """Inert two-root authority; repeated local feature names live on distinct RNA."""
    request = original()
    components, selections, roots, members, molecules, local_rows, nodes = [], [], [], [], [], [], []
    for slot, source, member in (("first", "root.first", "rna.first"), ("second", "root.second", "rna.second")):
        local_path = {"space_id": "local", "start": 0, "end": 2}
        path = {"space_id": member, "start": 0, "end": 2}
        identity = {"id": "component." + slot}
        target = {"kind": "boundary_port", "id": "signal"}
        components.append({"identity": identity, "body": {
            "fragment": {"boundary_ports": [{"id": "signal", "endpoint": {"node": "node", "port": "value"}}]},
            "carriers": [{"target": target, "sites": [{"root": "local.root", "feature": "region", "path": local_path}]}]}})
        selections.append({"slot": slot, "component": identity})
        roots.append({"slot": slot, "source": source})
        members.append({"slot": slot, "source": source, "member": member})
        molecules.append({"id": member, "sequence": "AC", "features": [{"id": "region", "path": path}]})
        nodes.append({"slot": slot, "node": "node", "actual": "actual." + slot})
        local_rows.append({"slot": slot, "target": target, "sites": [{"slot": slot, "root": "local.root",
            "source": source, "feature": "region", "final_feature": "region", "local_path": local_path,
            "member": member, "path": path}]})
    available = {"onset_min": "0", "onset_max": "0", "duration_min": "9", "duration_max": "9"}
    transport = {"definition": {"id": "transport"}, "provider": {"id": "transport.body"},
                 "producer_member": "rna.first", "consumer_member": "rna.second"}
    transport_body = {"kind": "transport", "definition": transport["definition"], "availability": available}
    delivery = {"definition": {"id": "delivery"}, "provider": {"id": "delivery.body"},
                "body": {"kind": "delivery", "definition": {"id": "delivery"}, "availability": available,
                         "arrival": {"earliest": 0, "latest": 0}, "expression": {"earliest": 0, "latest": 0},
                         "activation": {"earliest": 0, "latest": 0}}}
    placements = [{"id": "placement." + row["slot"], "member_id": row["member"]} for row in members]
    request["implementation_request"]["document"]["deployment"] = {"delivery": {"contract": delivery["definition"]}}
    request["context"] = {"placements": placements, "providers": [
        {"identity": transport["provider"], "body": transport_body},
        {"identity": delivery["provider"], "body": delivery["body"]}]}
    request["component_library"] = {"components": components}
    request["composition_rule"] = {"body": {"components": selections, "root_bindings": roots,
        "member_bindings": members, "material_authority": {"member_order": ["rna.first", "rna.second"]}, "joins": [],
        "links": [{"id": "signal", "producer": {"slot": "first", "boundary": "signal"},
                   "consumer": {"slot": "second", "boundary": "signal"}, "signal_type": "bool", "scope": "executor"}],
        "link_carriers": [{"link": "signal", "producer_site": 0, "consumer_site": 0, "transport": transport}]}}
    candidate = instance.candidate()
    candidate["assembly_proposal"].update(schema_version="biocompiler.policy_component_assembly_proposal.v0.3",
        profile=api.MULTI_MEMBER_ASSEMBLY_PROFILE, nodes=nodes)
    candidate["construction"] = {"inventory": {"molecules": molecules}}
    assembly = {"outcome": "pass", "carrier_projections": local_rows, "link_projections": [{
        "link": "signal", "transport": deepcopy(transport),
        "producer_endpoint": {"node": "actual.first", "port": "value"},
        "consumer_endpoint": {"node": "actual.second", "port": "value"},
        "producer": deepcopy(local_rows[0]["sites"][0]), "consumer": deepcopy(local_rows[1]["sites"][0])}]}
    context = {"outcome": "pass", "member_allocations": [{**row, "placement": placement,
        "molecule_fingerprint": digest(molecule), "delivery": deepcopy(delivery)}
        for row, placement, molecule in zip(members, placements, molecules)],
        "transport_allocations": [{"link": "signal", **transport, "signal_type": "bool", "scope": "executor",
            "transport_profile": "biocompiler.policy_complete_signal_identity_transport.v0.1",
            "phase_profile": "biocompiler.policy_staged_primitive_execution.v0.1", "available": available}]}
    return deepcopy(request), deepcopy(candidate), deepcopy(assembly), deepcopy(context)


class MultiMemberEvidenceTests(unittest.TestCase):
    def test_local_feature_names_are_preserved_on_distinct_members(self):
        request, candidate, assembly, context = projection_records()
        api._candidate(candidate, instanced=True, multi_member=True)
        api._projections(request, candidate, assembly)
        api._member_transport_inventory(request, candidate, context)
        for flags in ({}, {"instanced": True}):
            with self.subTest(flags=flags), self.assertRaises(CoreProtocolError):
                api._candidate(candidate, **flags)

    def test_carrier_members_local_ids_and_transport_are_exact(self):
        changes = [
            lambda r, c, a: a["carrier_projections"][0]["sites"][0].update(member="rna.second"),
            lambda r, c, a: a["carrier_projections"][0]["sites"][0].update(final_feature='["first","region"]'),
            lambda r, c, a: a["carrier_projections"][0]["sites"][0]["path"].update(start=1),
            lambda r, c, a: a["link_projections"][0].update(joins=[]),
            lambda r, c, a: a["link_projections"][0]["transport"].update(consumer_member="rna.first"),
            lambda r, c, a: a["link_projections"][0]["transport"].update(provider={"id": "substitute"}),
            lambda r, c, a: a["link_projections"][0].pop("transport"),
        ]
        for change in changes:
            request, candidate, assembly, _ = projection_records()
            change(request, candidate, assembly)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._projections(request, candidate, assembly)

    def test_complete_member_and_transport_censuses_are_required(self):
        for key in ("member_allocations", "transport_allocations"):
            for edit in (lambda v: v.pop(), lambda v: v.append(deepcopy(v[0]))):
                request, candidate, _, context = projection_records()
                edit(context[key])
                with self.subTest(key=key, edit=edit), self.assertRaises(CoreProtocolError):
                    api._member_transport_inventory(request, candidate, context)
        request, candidate, _, context = projection_records()
        context["member_allocations"].reverse()
        with self.assertRaises(CoreProtocolError):
            api._member_transport_inventory(request, candidate, context)

    def test_each_member_binds_its_full_molecule_placement_and_shared_delivery(self):
        changes = [lambda row: row.update(molecule_fingerprint="0" * 64),
                   lambda row: row.update(source="root.second"),
                   lambda row: row["placement"].update(member_id="rna.second"),
                   lambda row: row["delivery"].update(provider={"id": "unbound"}),
                   lambda row: row["delivery"]["body"]["availability"].update(onset_max="2"),
                   lambda row: row.pop("delivery")]
        for change in changes:
            request, candidate, _, context = deepcopy(projection_records())
            # Separate receipt bytes from original authority, just as a response does.
            context = deepcopy(context)
            change(context["member_allocations"][0])
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._member_transport_inventory(request, candidate, context)

    def test_transport_premise_and_endpoints_cannot_be_substituted(self):
        for key, wrong in (("provider", {"id": "unbound"}), ("definition", {"id": "other"}),
                           ("producer_member", "rna.second"), ("signal_type", "product"), ("scope", "encounter"),
                           ("transport_profile", "co_delivery"), ("phase_profile", "truth"),
                           ("available", {"onset_min": "10"})):
            request, candidate, _, context = projection_records()
            context = deepcopy(context)
            context["transport_allocations"][0][key] = wrong
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api._member_transport_inventory(request, candidate, context)

    def test_negative_receipts_keep_only_completed_original_prefixes(self):
        for status in ("fail", "unknown", "unsupported"):
            request, candidate, _, context = projection_records()
            context["outcome"] = status
            context["member_allocations"].pop()
            context["transport_allocations"].clear()
            api._member_transport_inventory(request, candidate, context)
            context["member_allocations"][0]["molecule_fingerprint"] = "0" * 64
            with self.subTest(status=status), self.assertRaises(CoreProtocolError):
                api._member_transport_inventory(request, candidate, context)

    def test_opt_in_families_are_mutually_exclusive(self):
        request = original()
        fields = {key: value for key, value in request.items() if key not in ("schema_version", "profile")}
        for flags in ({"multi_member": True}, {"multi_member": True, "prerequisites": True},
                      {"multi_member": True, "prerequisites": True, "instanced": True, "two_observations": True}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                sdk.prepare_request(**fields, **flags)


class MultiProductAnchorTests(unittest.TestCase):
    def setUp(self):
        self.anchors = {"effects": [{"source": "effect." + name, "bank": "bank." + name, "feedback": "feedback." + name}
                                    for name in ("first", "second")]}
        self.graph = {"inputs": [{"id": "feedback." + name, "kind": "feedback",
                       "consumer": {"node": "bank." + name, "port": "feedback"}} for name in ("first", "second")]}
        self.declarations = [{"$type": "Effect", "id": "effect." + name} for name in ("first", "second")]

    def check(self):
        implementation._multi_product_anchors(self.anchors, self.graph, self.declarations)

    def test_two_original_effects_keep_distinct_banks_and_feedback(self):
        self.check()
        self.graph["inputs"].reverse()
        self.check()
        self.anchors["effects"].reverse()
        with self.assertRaises(CoreProtocolError):
            self.check()

    def test_missing_or_aliased_owner_bank_and_feedback_are_rejected(self):
        changes = [lambda: self.anchors["effects"].pop(), lambda: self.declarations.pop(),
                   lambda: self.graph["inputs"].pop(),
                   lambda: self.graph["inputs"][0]["consumer"].update(node="bank.second")]
        changes += [lambda key=key: self.anchors["effects"][1].update({key: self.anchors["effects"][0][key]})
                    for key in ("source", "bank", "feedback")]
        for change in changes:
            self.setUp()
            change()
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                self.check()


class MultiMemberClosureTests(unittest.TestCase):
    def records(self):
        from tests import test_policy_prerequisite_evidence as peer
        request, report = peer.records()
        request.update(schema_version=api.MULTI_MEMBER_REQUEST_SCHEMA, profile=api.MULTI_MEMBER_REQUEST_PROFILE)
        original = request["implementation_request"]
        original.update(schema_version=implementation.MULTI_PRODUCT_REQUEST_SCHEMA,
                        profile=implementation.MULTI_PRODUCT_REQUEST_PROFILE)
        definition = {"$type": "SemanticDefinition", "id": "transport", "version": "1", "category": "interface"}
        reference = {"$type": "DefinitionRef", "id": "transport", "version": "1", "digest": digest(definition)}
        original["document"]["program"]["semantics"]["definitions"].append(definition)
        entry = original["document"]["implementations"]["implementations"][0]
        entry["dependencies"].append(reference)
        entry_digest = digest(entry)
        original["catalog_bindings"][0]["entry_digest"] = entry_digest
        environment = next(row["body"]["definition"] for row in request["context"]["providers"]
                           if row["identity"]["id"] == "environment")
        provider = {"schema_version": "biocompiler.policy_material_provider.v0.2", "identity": {"id": "transport.body"},
                    "body": {"kind": "transport", "definition": reference, "environment": environment}}
        request["context"]["providers"].append(provider)
        closure = report["prerequisites"]
        closure.update(schema_version="biocompiler.policy_provider_prerequisite_closure.v0.2",
                       profile=api.MULTI_MEMBER_REQUEST_PROFILE, original_request_fingerprint=digest(request),
                       source_catalog=deepcopy(original["document"]["implementations"]),
                       member_allocations=[], transport_allocations=[])
        report["context"].update(member_allocations=[], transport_allocations=[])
        closure["providers"].append({"definition": reference, "identity": provider["identity"], "body_fingerprint": digest(provider["body"])})
        pending = closure["pending_dependencies"]
        pending[0]["entry_digest"] = entry_digest
        pending.append({"entry_id": entry["id"], "entry_digest": entry_digest, "dependency_index": 1, "definition": reference})
        graph = closure["graph"]
        graph.update(schema_version="biocompiler.policy_provider_dependency_graph.v0.2", pending_dependencies=deepcopy(pending))
        graph["roots"][-1]["origin"]["entry_digest"] = entry_digest
        graph["roots"].append({"origin": {"kind": "catalog_dependency", "entry_id": entry["id"], "entry_digest": entry_digest,
                                        "dependency_index": 1}, "definition": reference})
        graph["nodes"].append({"definition": reference, "provider": provider["identity"]})
        graph["edges"].append({"source": reference, "relation": "transport_environment", "index": 0, "target": environment})
        peer.sync(report)
        return request, report

    def test_transport_graph_is_an_exact_additive_catalog_dependency(self):
        request, report = self.records()
        api._prerequisite_evidence(request, report)

    def test_graph_schema_environment_edge_and_body_pin_are_bound(self):
        from tests import test_policy_prerequisite_evidence as peer
        changes = [lambda c: c["graph"].update(schema_version="biocompiler.policy_provider_dependency_graph.v0.1"),
                   lambda c: c["graph"]["edges"].pop(),
                   lambda c: c["graph"]["edges"][-1].update(relation="interface_environment"),
                   lambda c: c["graph"]["edges"][-1].update(index=1),
                   lambda c: c["graph"]["nodes"][-1].update(provider={"id": "substitute"}),
                   lambda c: c["graph"]["roots"].pop(),
                   lambda c: c["providers"][-1].update(body_fingerprint="0" * 64),
                   lambda c: c.update(schema_version="biocompiler.policy_provider_prerequisite_closure.v0.1")]
        for change in changes:
            request, report = self.records()
            change(report["prerequisites"])
            peer.sync(report)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_closure_repeats_exact_checked_member_and_transport_rows(self):
        from tests import test_policy_prerequisite_evidence as peer
        for key in ("member_allocations", "transport_allocations"):
            request, report = self.records()
            report["prerequisites"][key] = [{"invented": "retained"}]
            peer.sync(report)
            report["context"][key] = []
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_missing_transport_keeps_unknown_and_has_no_provider_body_pin(self):
        from tests import test_policy_prerequisite_evidence as peer
        request, report = self.records()
        request["context"]["providers"].pop()
        closure = report["prerequisites"]
        closure["providers"].pop()
        node = closure["graph"]["nodes"][-1]
        node["provider"] = None
        closure["graph"]["edges"].pop()
        closure["graph"]["issues"] = [{"kind": "missing", "code": "prerequisite_provider_missing", "references": [node["definition"]]}]
        closure["original_request_fingerprint"] = digest(request)
        peer.outcome(report, "unknown", "prerequisite_provider_missing")
        api._prerequisite_evidence(request, report)
        closure["complete"] = True
        peer.sync(report)
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)


class MultiProductMachineObligationTests(unittest.TestCase):
    def records(self):
        obligation = "machine_reachability_termination_and_progress"
        binding = {"schema_version": implementation.MULTI_PRODUCT_BINDING_REPORT_SCHEMA,
                   "profile": implementation.MULTI_PRODUCT_BINDING_PROFILE,
                   "source_admission": {"source_assessment": {"unresolved_obligations": [obligation]}}}
        preservation = {"status": "checked_implementation", "binding": binding}
        evidence = {"preservation": digest(preservation), "machine_binding": digest(binding),
                    "state_and_terminal_semantics": "exact_bounded_source_correspondence", "prefixes": "complete_original_domain",
                    "retained_attempt_identity": "creation_fixed_injective", "universal_termination": "not_claimed",
                    "progress": "declared_requirements_only"}
        return {"preservation": preservation, "catalog": {}, "assembly_status": "pass", "context_status": "pass",
                "prerequisites": {"status": "pass"}, "prerequisite_status": "pass", "status": api.ACCEPTED_STATUS,
                "all_original_obligations_discharged": True,
                "obligations": [{"obligation": obligation, "status": "discharged",
                    "stage": "bounded_machine_semantics_and_declared_requirements", "evidence": evidence}]}

    def check(self, report, *, multi_product=True):
        api.material._obligations(report, material_key="assembly", accepted_status=api.ACCEPTED_STATUS,
            conjunction_stage="conditional_component_context_conjunction", prerequisite_key="prerequisites",
            multi_product=multi_product)

    def test_bounded_machine_discharge_retains_new_source_family(self):
        report = self.records()
        self.check(report)
        with self.assertRaises(CoreProtocolError):
            self.check(report, multi_product=False)

    def test_prior_family_promoted_claim_or_incomplete_chain_cannot_discharge(self):
        changes = [lambda r: r["preservation"]["binding"].update(schema_version="biocompiler.policy_implementation_binding_report.v0.2"),
                   lambda r: r["preservation"]["binding"].update(profile="biocompiler.policy_staged_source_graph.v0.1"),
                   lambda r: r["obligations"][0]["evidence"].update(universal_termination="proven"),
                   lambda r: r["obligations"][0]["evidence"].update(progress="universal"),
                   lambda r: r["prerequisites"].update(status="unknown"),
                   lambda r: r.update(prerequisite_status="unknown"),
                   lambda r: r.update(assembly_status="fail"),
                   lambda r: r.update(context_status="fail")]
        for change in changes:
            report = self.records()
            change(report)
            report["obligations"][0]["evidence"].update(preservation=digest(report["preservation"]),
                machine_binding=digest(report["preservation"]["binding"]))
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                self.check(report)


if __name__ == "__main__":
    unittest.main()
