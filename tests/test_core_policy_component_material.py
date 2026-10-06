"""Synthetic protocol peers only; these do not establish native admission.

The original source/preservation peer is reused. Minimal component bodies below
exercise retained transport inventories, not the native component domain grammar.
Actual admitted A/B composition is covered by the independent OCaml service test.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_material as api
from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreTimeout, CoreRejected, CoreUnsupported,
    PROTOCOL, CORE_VERSION, encode_json,
)
from tests import test_core_policy_material as old

digest = old.digest


def pin(name, body):
    return {"schema_version": "biocompiler.component_identity.v0.1", "kind": "model",
            "id": name, "version": "1", "content_fingerprint": digest(body)}


def original():
    legacy = old.original()
    actual = old.candidate(legacy)
    features = {row["id"]: row for row in actual["construction"]["inventory"]["molecules"][0]["features"]}
    components = []
    for slot, node, port, feature in (("decision", "evidence", "value", "utr5"), ("driver", "attempt", "authorization", "cds")):
        body = {"fragment": {"boundary_ports": [{"id": "authorization", "endpoint": {"node": node, "port": port}}]},
                "carriers": [{"target": {"kind": "boundary_port", "id": "authorization"},
                              "sites": [{"root": slot + ".root", "feature": feature, "path": deepcopy(features[feature]["path"])}]}]}
        components.append({"identity": pin("mock." + slot, body), "body": body})
    body = {"components": [{"slot": slot, "component": deepcopy(value["identity"])} for slot, value in zip(("decision", "driver"), components)],
            "root_bindings": [{"slot": slot, "source": slot + ".root"} for slot in ("decision", "driver")],
            "links": [{"id": "authorization", "producer": {"slot": "decision", "boundary": "authorization"},
                       "consumer": {"slot": "driver", "boundary": "authorization"}}],
            "link_carriers": [{"link": "authorization", "producer_site": 0, "consumer_site": 0, "join": "mock.join"}],
            "join": {"id": "mock.join", "offset": 2},
            "material_authority": deepcopy(legacy["material_contract"]["body"]["structure_authority"])}
    rule = {"identity": pin("mock.rule", body), "body": body}
    context = deepcopy(legacy["context"])
    layout = context["record_layout"]
    layout.pop("kernel_digest")
    layout.update(profile="biocompiler.policy_component_complete_records.v0.1", rule=deepcopy(rule["identity"]), union_digest=digest("mock union"))
    context.update(schema_version="biocompiler.policy_component_context.v0.1", profile=api.REQUEST_PROFILE)
    for provider in context["providers"]:
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = digest(layout)
        provider["identity"]["content_fingerprint"] = digest(provider["body"])
    provider = deepcopy(context["providers"][0]["body"]["definition"])
    resources = [{"owner": {"kind": "node", "slot": "decision", "node": "selected"}, "unit": "truth_cells",
                  "scope": "per_encounter_slot", "provider": provider, "capacity": "shared.truth"}]
    return {"schema_version": api.REQUEST_SCHEMA, "profile": api.REQUEST_PROFILE,
            "implementation_request": deepcopy(legacy["implementation_request"]),
            "component_library": {"components": components}, "composition_rule": rule,
            "catalog_binding": {key: deepcopy(value) for key, value in legacy["catalog_binding"].items() if key != "material_contract"}
                | {"components": deepcopy(body["components"]), "rule": deepcopy(rule["identity"])},
            "input_bindings": [{"input": "condition", "source": "condition", "provider": deepcopy(context["providers"][2]["body"]["definition"]), "channel": "condition"}],
            "resource_bindings": resources, "context": context,
            "budgets": {**deepcopy(legacy["budgets"]), "profile": api.RESOURCE_PROFILE}}


def candidate(request):
    value = old.candidate(old.original())
    value.pop("material_binding")
    value.update(schema_version=api.CANDIDATE_SCHEMA,
        assembly_proposal={"schema_version": "biocompiler.policy_component_assembly_proposal.v0.1",
            "profile": "biocompiler.policy_exact_component_assembly.v0.1", "rule": deepcopy(request["composition_rule"]["identity"]),
            "nodes": [{"slot": "decision", "node": "evidence", "actual": "evidence"}, {"slot": "driver", "node": "attempt", "actual": "attempt"}]})
    return value


def report(request, actual, limits, *, accepted=True):
    legacy = old.original()
    legacy["implementation_request"] = deepcopy(request["implementation_request"])
    legacy_actual = deepcopy(actual) | {"material_binding": old.candidate(legacy)["material_binding"]}
    result = old.report(legacy, legacy_actual, limits, status="checked_material" if accepted else "not_accepted")
    preservation = result["preservation"]
    rule = request["composition_rule"]
    carrier_rows = []
    features = {row["id"]: row for row in actual["construction"]["inventory"]["molecules"][0]["features"]}
    for slot, component in zip(("decision", "driver"), request["component_library"]["components"]):
        carrier = component["body"]["carriers"][0]
        site = carrier["sites"][0]
        projected = {"slot": slot, "root": site["root"], "source": slot + ".root", "feature": site["feature"],
                     "local_path": deepcopy(site["path"]), "member": "payload", "path": deepcopy(features[site["feature"]]["path"])}
        carrier_rows.append({"slot": slot, "target": deepcopy(carrier["target"]), "sites": [projected]})
    assembly = {"schema_version": "biocompiler.policy_component_assembly_assessment.v0.1",
        "checker_version": "biocompiler.ocaml.policy_component_assembly_check.v0.1", "profile": "biocompiler.policy_exact_component_assembly.v0.1",
        "original_fingerprint": digest(request["implementation_request"]), "components_fingerprint": digest(request["component_library"]),
        "rule_fingerprint": digest(rule), "implementation_fingerprint": digest(actual["implementation"]),
        "proposed_fingerprint": digest(actual["assembly_proposal"]), "candidate_fingerprint": digest(actual["construction"]),
        "outcome": "pass", "diagnostics": [], "claim_scope": "exact_supplied_component_graph_and_material_correspondence",
        "premise": "supplied_conditional_model_to_sequence_composition_rule", "structure": deepcopy(result["material"]["structure"]) if accepted else None,
        "carrier_projections": carrier_rows, "link_projections": [{"link": "authorization", "join": "mock.join", "offset": 2,
            "producer_endpoint": {"node": "evidence", "port": "value"}, "consumer_endpoint": {"node": "attempt", "port": "authorization"},
            "producer": deepcopy(carrier_rows[0]["sites"][0]), "consumer": deepcopy(carrier_rows[1]["sites"][0])}],
        "preservation_evidence_fingerprint": digest(preservation),
        **{key: "unassessed" for key in ("catalog_authorization", "context", "resource_capacity", "input_compatibility", "source_obligation_discharge", "empirical")},
        "artifact": "withheld", "export": "withheld"}
    providers = request["context"]["providers"]
    source_ids = preservation["binding"]["source_admission"]["source_assessment"]["unresolved_obligations"]
    discharge_ids = {"chassis_capability_and_delivery_suitability"} | {"semantic_definition:" + row["body"]["definition"]["id"] for row in providers}
    demand = {key: deepcopy(request["resource_bindings"][0][key]) for key in ("owner", "unit", "scope")} | {"quantity": 1}
    context = {"schema_version": "biocompiler.policy_component_context_assessment.v0.1", "profile": api.REQUEST_PROFILE,
        "implementation_version": "biocompiler.ocaml.policy_component_context_check.v0.1", "request_fingerprint": digest(request),
        "context_fingerprint": digest(request["context"]), "assembly_fingerprint": digest(assembly), "outcome": "pass",
        "claim_scope": "conditional_component_context_and_complete_record_capacity", "record_layout": deepcopy(request["context"]["record_layout"]),
        "minimum_record_layout": deepcopy(request["context"]["record_layout"]), "derived_demands": [demand],
        "resource_allocations": [{"demand": deepcopy(demand), "provider": deepcopy(providers[0]["body"]["definition"]),
            "capacity": "shared.truth", "pool": "executor.pool.shared.truth", "reserved": 1}],
        "source_obligations": [{"id": value, "context_status": "discharged" if value in discharge_ids else "outside_stage"} for value in source_ids],
        "discharges": [{"id": value, "evidence": [deepcopy(row["identity"]) for row in providers]} for value in source_ids if value in discharge_ids],
        "diagnostics": [], "source_receipt_status": "unchanged", "biological_validity": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld"}
    result.pop("material")
    result.pop("material_status")
    result.update(schema_version=api.REPORT_SCHEMA, profile=api.REQUEST_PROFILE, implementation="biocompiler.ocaml.policy_component_material_check.v0.1",
        resource_profile=api.RESOURCE_PROFILE, request_fingerprint=digest(request), candidate_fingerprint=digest(actual),
        invocation_fingerprint=digest({"request": request, "candidate": actual, "limits": limits}),
        status=api.ACCEPTED_STATUS if accepted else "not_accepted", claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE,
        budgets=deepcopy(request["budgets"]), assembly=assembly if accepted else None, assembly_status="pass" if accepted else "unassessed",
        context=context if accepted else None,
        catalog={"status": "pass", "original_binding": deepcopy(request["catalog_binding"]),
                 "selected_catalog_entry": request["catalog_binding"]["entry_id"], "component_library_fingerprint": digest(request["component_library"]),
                 "rule_fingerprint": digest(rule), "premise": "supplied_conditional_component_composition_and_provider_contracts"} if accepted else None)
    result["obligations"] = [{"obligation": value, "status": "discharged" if accepted else "unresolved",
        "stage": "conditional_component_context_conjunction" if accepted else None,
        "evidence": {"preservation": digest(preservation), "assembly": digest(assembly), "context": digest(context)} if accepted else None} for value in source_ids]
    return result


def result(payload, *, accepted=True, export=False):
    request = payload["request"]
    actual = deepcopy(payload.get("candidate") or candidate(request))
    checked = report(request, actual, payload["limits"], accepted=accepted)
    artifact = None
    if export and accepted:
        artifact = old.artifact(request, actual, payload["limits"], checked)
        artifact["schema_version"] = api.EXPORT_SCHEMA
        artifact["manifest"].update(schema_version=api.MANIFEST_SCHEMA, profile=api.REQUEST_PROFILE, claim_scope=api.CLAIM_SCOPE, premise=api.PREMISE)
        artifact["manifest_sha256"] = digest(artifact["manifest"])
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "resource_profile": api.RESOURCE_PROFILE,
        "validation_scope": api.VALIDATION_SCOPE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
        "invocation_fingerprint": digest({"request": request, "candidate": actual, "limits": payload["limits"]}),
        "report_fingerprint": digest(checked), "candidate": actual, "report": checked, "artifact": artifact}


def capabilities(role):
    value = old.capabilities(role)
    value.update(operations=["capabilities", *api.PROFILE["operations"]], validation_scopes=[api.VALIDATION_SCOPE],
                 profiles={"policy_component_material": deepcopy(api.PROFILE)})
    if role == "core":
        value["profiles"]["policy_component_material_producer"] = deepcopy(api.PRODUCER_PROFILE)
        value["operations"].append("compile-policy-component-material")
    return value


def rehash(value):
    report = value["report"]
    if report["assembly"] is not None:
        report["assembly"]["preservation_evidence_fingerprint"] = digest(report["preservation"])
    if report["context"] is not None:
        report["context"]["assembly_fingerprint"] = digest(report["assembly"])
    for row in report["obligations"]:
        if row["evidence"] is not None:
            row["evidence"] = {key: digest(report[key]) for key in row["evidence"]}
    value["report_fingerprint"] = digest(report)


class PolicyComponentMaterialTransportTests(unittest.TestCase):
    def setUp(self):
        self.legacy = old.PolicyMaterialTransportTests()
        self.addCleanup(self.legacy.doCleanups)
        self.legacy.setUp()
        self.request, self.limits = original(), old.fixture()["limits"]
        self.candidate = candidate(self.request)
        self.client = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, *, mutate=None, negotiate=None, role="core", accepted=True, failure=None, rejection=None):
        def call(_binary, encoded, _timeout, _cancelled):
            invocation = json.loads(encoded)
            self.calls.append(invocation)
            operation = invocation["operation"]
            if operation == "capabilities":
                value = capabilities(role)
                if negotiate:
                    negotiate(value)
            else:
                if failure:
                    raise failure
                value = result(invocation["payload"], accepted=accepted, export=operation == "export-policy-component-material")
                if mutate:
                    mutate(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"], "operation": operation,
                "status": status, "result": value if status == "ok" else None,
                "diagnostics": [] if status == "ok" else [{"code": "rejected_component", "message": "Rejected", "path": "/request"}],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def check(self):
        return self.client.check(self.request, self.candidate, self.limits)

    def test_all_four_routes_preserve_complete_original_inputs(self):
        with self.exchange():
            compiled = self.client.compile(self.request, self.limits)
            checked = self.client.check(self.request, compiled.candidate, self.limits)
            replayed = self.client.replay(self.request, compiled.candidate, self.limits, checked.result)
            exported = self.client.export(self.request, compiled.candidate, self.limits)
        self.assertEqual(compiled.result, replayed.result)
        self.assertIsNone(compiled.artifact)
        self.assertEqual(exported.artifact["manifest"]["request"], self.request)
        self.assertEqual(exported.report, checked.report)
        self.assertEqual(self.calls[-1]["payload"], {"request": self.request, "candidate": compiled.candidate, "limits": self.limits})
        self.assertEqual([row["operation"] for row in self.calls][1::2], ["compile-policy-component-material", "check-policy-component-material", "replay-policy-component-material", "export-policy-component-material"])

    def test_verify_capabilities_and_no_semantic_fallback(self):
        client = api.PolicyComponentMaterialClient(CoreClient(Path(sys.executable), role="verify"))
        with self.assertRaises(CoreProtocolError):
            client.compile(self.request, self.limits)
        self.assertEqual(self.calls, [])
        with self.exchange(role="verify"):
            self.assertIsNotNone(client.export(self.request, self.candidate, self.limits).artifact)
        for mutation in (lambda value: value["profiles"].clear(), lambda value: value["validation_scopes"].clear(),
                         lambda value: value["profiles"]["policy_component_material"].update(artifact="accepted")):
            with self.exchange(negotiate=mutation), self.assertRaises(CoreProtocolError):
                self.check()
        with self.exchange(failure=CoreTimeout("timeout")), self.assertRaises(CoreTimeout), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No fallback")):
            self.check()
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.exchange(rejection=status), self.assertRaises(error):
                self.check()

    def test_snapshot_precedes_negotiation_and_result_is_immutable(self):
        before = deepcopy(self.request)
        with self.exchange(negotiate=lambda _: self.request["component_library"]["components"].clear()):
            value = self.check()
        self.assertEqual(self.calls[-1]["payload"]["request"], before)
        value.report["obligations"].clear()
        value.candidate["assembly_proposal"]["nodes"].clear()
        self.assertTrue(value.report["obligations"])
        self.assertTrue(value.candidate["assembly_proposal"]["nodes"])
        with self.assertRaises(FrozenInstanceError):
            value.report_fingerprint = "changed"

    def test_rehashed_assembly_owner_site_and_link_mutations_reject(self):
        mutations = [lambda a: a.update(rule_fingerprint="0" * 64), lambda a: a.update(catalog_authorization="pass"),
            lambda a: a["carrier_projections"].pop(), lambda a: a["carrier_projections"].reverse(),
            lambda a: a["carrier_projections"][0]["sites"].clear(), lambda a: a["carrier_projections"][0]["sites"][0].update(root="foreign"),
            lambda a: a["carrier_projections"][0]["sites"][0]["path"].update(space_id="foreign"),
            lambda a: a["link_projections"].clear(), lambda a: a["link_projections"][0].update(offset=3),
            lambda a: a["link_projections"][0]["consumer_endpoint"].update(node="unowned"),
            lambda a: a["link_projections"][0]["producer"].update(slot="driver")]
        for mutate in mutations:
            def changed(value):
                mutate(value["report"]["assembly"])
                rehash(value)
            with self.subTest(mutate=mutate), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.check()

    def test_rehashed_context_originals_bounds_and_inventory_mutations_reject(self):
        mutations = [lambda c: c.update(request_fingerprint="0" * 64), lambda c: c["source_obligations"].pop(),
            lambda c: c["discharges"].clear(), lambda c: c["discharges"][0]["evidence"].pop(),
            lambda c: c["minimum_record_layout"].update(identifier_bytes=1000000),
            lambda c: c["minimum_record_layout"].update(horizon_ticks=5), lambda c: c["record_layout"].update(attempts=99),
            lambda c: c["derived_demands"].clear(), lambda c: c["derived_demands"][0]["owner"].update(slot="driver"),
            lambda c: c["derived_demands"][0].update(quantity=True), lambda c: c["resource_allocations"].clear(),
            lambda c: c["resource_allocations"][0].update(pool="foreign"), lambda c: c["resource_allocations"][0].update(reserved=2)]
        for mutate in mutations:
            def changed(value):
                mutate(value["report"]["context"])
                rehash(value)
            with self.subTest(mutate=mutate), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.check()

    def test_failed_context_retains_truthful_minimum_and_partial_reservations(self):
        self.request["context"]["record_layout"]["horizon_ticks"] = 5
        def changed(value):
            checked = value["report"]
            context = checked["context"]
            context.update(outcome="fail", diagnostics=["complete_finite_record_identity"], resource_allocations=[], discharges=[])
            context["minimum_record_layout"]["horizon_ticks"] = 6
            context["source_obligations"] = [{"id": row["id"], "context_status": "outside_stage"} for row in context["source_obligations"]]
            checked.update(status="not_accepted", context_status="fail", all_original_obligations_discharged=False)
            checked["obligations"] = [{"obligation": row["obligation"], "status": "unresolved", "stage": None, "evidence": None} for row in checked["obligations"]]
            rehash(value)
        with self.exchange(mutate=changed):
            value = self.check()
        self.assertEqual(value.status, "not_accepted")
        self.assertEqual(value.report["context"]["minimum_record_layout"]["horizon_ticks"], 6)
        self.assertIsNone(value.artifact)

    def test_whole_wrapper_budget_ledger_and_replay_mutations_reject(self):
        mutations = [lambda v: v.update(request_fingerprint="0" * 64), lambda v: v["report"]["catalog"]["original_binding"].update(entry_id="foreign"),
            lambda v: v["report"]["obligations"].pop(), lambda v: v["report"].update(empirical="verified"),
            lambda v: v["report"]["usage"].update(charged_work=True), lambda v: v["report"]["usage"].update(charged_work=1000000001),
            lambda v: v["report"]["limits"]["source"].update(max_work=1), lambda v: v["candidate"]["assembly_proposal"]["nodes"].pop()]
        for mutation in mutations:
            def changed(value):
                mutation(value)
                rehash(value)
            with self.subTest(mutation=mutation), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.check()
        with self.exchange():
            saved = self.check()
            exported = self.client.export(self.request, self.candidate, self.limits)
        for report_value in (saved.report, exported.result, {**saved.result, "implementation": "foreign"}):
            with self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, self.candidate, self.limits, report_value)

    def test_export_pair_rehash_cannot_hide_changed_material_or_originals(self):
        mutations = [lambda a: a.update(fasta="wrong\n"), lambda a: a["manifest"]["members"].clear(),
            lambda a: a["manifest"]["request"]["input_bindings"].clear(), lambda a: a["manifest"].update(claim_scope="universal"),
            lambda a: a["manifest"]["members"][0]["molecule"].update(sequence="AAAA")]
        for mutation in mutations:
            def changed(value):
                mutation(value["artifact"])
                value["artifact"]["manifest_sha256"] = digest(value["artifact"]["manifest"])
                value["artifact"]["fasta_sha256"] = hashlib.sha256(value["artifact"]["fasta"].encode()).hexdigest()
            with self.subTest(mutation=mutation), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.client.export(self.request, self.candidate, self.limits)

    def test_not_accepted_and_publication_exhaustion_have_no_artifact(self):
        with self.exchange(accepted=False):
            self.assertEqual(self.check().status, "not_accepted")
        with self.exchange(accepted=False), self.assertRaises(CoreProtocolError):
            self.client.export(self.request, self.candidate, self.limits)
        for key in ("MAX_RESULT_BYTES", "MAX_RESULT_NODES"):
            with self.exchange(), patch.object(api, key, 10), self.assertRaises(CoreProtocolError):
                self.check()


if __name__ == "__main__":
    unittest.main()
