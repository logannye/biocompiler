"""Adversarial literal transport peers; these do not establish native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_material as api
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError,
    CoreRejected, CoreTimeout, CoreTransportError, CoreUnavailable, CoreUnsupported, encode_json,
)
from tests import test_core_policy_implementation as peer

ROOT = Path(__file__).resolve().parents[1]
digest = peer.digest


def fixture():
    return json.loads((ROOT / "core/test/data/policy_material_context_v01.json").read_text())


def original():
    literal = fixture()
    source = literal["source_case"]["request"]
    bridge = source["catalog_bindings"][0]
    return {"schema_version": api.REQUEST_SCHEMA, "profile": api.REQUEST_PROFILE,
        "implementation_request": source, "material_contract": literal["contract"], "context": literal["context"],
        "catalog_binding": {key: deepcopy(bridge[key]) for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")}
            | {"material_contract": deepcopy(literal["contract"]["identity"])},
        "budgets": {"profile": api.RESOURCE_PROFILE, "max_work": 1000000000, "max_report_bytes": api.MAX_RESULT_BYTES, "max_report_nodes": api.MAX_RESULT_NODES}}


def candidate(request):
    literal = fixture()
    return {**peer.candidate(request["implementation_request"]), "schema_version": api.CANDIDATE_SCHEMA,
            "material_binding": deepcopy(literal["proposed"]), "construction": deepcopy(literal["candidate"])}


def report(request, actual, limits, *, status="checked_material"):
    preservation = peer.report(request["implementation_request"], actual, limits,
                               status="checked_implementation" if status == "checked_material" else "requirements_not_satisfied")
    contract = request["material_contract"]
    authority = contract["body"]["structure_authority"]
    structure = {"schema_version": "biocompiler.policy_mrna_structure_assessment.v0.1",
        "profile": "biocompiler.policy_mrna_completeness.v0.1", "implementation_version": "biocompiler.ocaml.policy_mrna_structure_check.v0.1",
        "claim_scope": "exact_supplied_mrna_structure_and_derivation_only", "authority_fingerprint": digest(authority),
        "candidate_fingerprint": digest(actual["construction"]), "content_outcome": "pass", "structural_outcome": "pass", "outcome": "pass"}
    structure.update({"content_reconstruction": {"schema_version": "biocompiler.construction_content_assessment.v0.1",
        "implementation_version": "biocompiler.ocaml.construction_content_check.v0.1", "claim_scope": "exact_supplied_template_molecular_content",
        "authority_fingerprint": digest({"schema_version": "biocompiler.construction_content_authority.v0.1", "template": authority["template"], "member_order": authority["member_order"]}),
        "candidate_fingerprint": digest(actual["construction"]), "reconstructed_fingerprint": digest(actual["construction"]), "outcome": "pass",
        "context_status": "unassessed", "payload_completeness": "unassessed", "diagnostics": []},
        "checked_clauses": ["PM-02", "PM-03", "PM-04", "PM-05", "PM-06", "PM-07", "PM-09"],
        "PM-08_scope": "supplied_construction_region_chemistry_product_declaration_provenance_only",
        "unassessed_clauses": ["PM-01", "PM-08_external_component_binding", "PM-10", "PM-11", "PM-12"], "members": [], "diagnostics": [],
        "context_status": "unassessed", "implementation": "unassessed", "policy": "unassessed", "material_binding": "unassessed", "export": "withheld"})
    material = {"schema_version": "biocompiler.policy_material_binding_assessment.v0.1", "checker_version": "biocompiler.ocaml.policy_material_binding_check.v0.1",
        "profile": "biocompiler.policy_truth_mrna_material.v0.1", "contract_fingerprint": digest(contract),
        "implementation_fingerprint": digest(actual["implementation"]), "proposed_fingerprint": digest(actual["material_binding"]),
        "candidate_fingerprint": digest(actual["construction"]), "outcome": "pass", "diagnostics": [],
        "claim_scope": "exact_supplied_whole_graph_material_case", "premise": "supplied_conditional_model_to_sequence_contract", "structure": structure,
        "preservation_evidence_fingerprint": digest(preservation), "context": "unassessed", "resource_capacity": "unassessed",
        "input_compatibility": "unassessed", "source_obligation_discharge": "unassessed", "empirical": "unassessed", "artifact": "withheld", "export": "withheld"}
    context = {"schema_version": "biocompiler.policy_material_context_assessment.v0.1", "profile": api.REQUEST_PROFILE,
        "implementation_version": "biocompiler.ocaml.policy_material_context_check.v0.1", "context_fingerprint": digest(request["context"]),
        "material_binding_fingerprint": digest(material), "outcome": "pass", "claim_scope": "conditional_exact_context_and_complete_record_capacity",
        "record_layout": deepcopy(request["context"]["record_layout"]), "derived_demands": deepcopy(contract["body"]["resources"]), "resource_allocations": [],
        "source_obligations": [], "discharges": [], "diagnostics": [], "source_receipt_status": "unchanged", "biological_validity": "unassessed",
        "human_use": "unassessed", "export": "withheld"}
    catalog = {"status": "pass", "original_binding": deepcopy(request["catalog_binding"]),
        "selected_catalog_entry": request["catalog_binding"]["entry_id"], "contract_fingerprint": digest(contract),
        "premise": "supplied_conditional_model_to_sequence_contract"}
    accepted = status == "checked_material"
    obligations = [{"obligation": item, "status": "discharged" if accepted else "unresolved",
                    "stage": "conditional_material_context_conjunction" if accepted else None,
                    "evidence": {"preservation": digest(preservation), "material": digest(material), "context": digest(context)} if accepted else None}
                   for item in preservation["binding"]["source_admission"]["source_assessment"]["unresolved_obligations"]]
    return {"schema_version": api.REPORT_SCHEMA, "profile": api.REQUEST_PROFILE, "implementation": "biocompiler.ocaml.policy_material_check.v0.1",
        "resource_profile": api.RESOURCE_PROFILE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
        "invocation_fingerprint": digest({"request": request, "candidate": actual, "limits": limits}), "status": status,
        "claim_scope": "bounded_conditional_policy_to_exact_mrna", "premise": "supplied_model_to_sequence_and_provider_contracts",
        "preservation": preservation, "catalog": catalog if accepted else None, "material": material if accepted else None,
        "context": context if accepted else None, "material_status": "pass" if accepted else "unassessed", "context_status": "pass" if accepted else "unassessed",
        "obligations": obligations, "all_original_obligations_discharged": accepted, "limits": deepcopy(limits), "budgets": deepcopy(request["budgets"]),
        "empirical": "unassessed", "artifact": "withheld", "export": "withheld", "usage": {"unit": "logical_data_visits_and_child_semantic_work", "charged_work": 10000, "request_decoding_work": 2000}}


def artifact(request, actual, limits, checked):
    fasta = ""
    members = []
    for index, molecule in enumerate(actual["construction"]["inventory"]["molecules"], 1):
        name = f"rna_{index:04d}"
        sequence = molecule["sequence"]
        fasta += f">{name} alphabet=RNA\n" + "".join(sequence[offset:offset + 80] + "\n" for offset in range(0, len(sequence), 80))
        members.append({"fasta_id": name, "member_id": molecule["id"], "molecule": deepcopy(molecule), "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest()})
    fasta_sha = hashlib.sha256(fasta.encode()).hexdigest()
    manifest = {"schema_version": "biocompiler.policy_mrna_manifest.v0.1", "profile": api.REQUEST_PROFILE,
        "claim_scope": "bounded_conditional_policy_to_exact_mrna", "premise": "supplied_model_to_sequence_and_provider_contracts",
        "request": deepcopy(request), "candidate": deepcopy(actual), "limits": deepcopy(limits), "assessment": deepcopy(checked),
        "bindings": {"request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
                     "invocation_fingerprint": digest({"request": request, "candidate": actual, "limits": limits}), "assessment_fingerprint": digest(checked)},
        "members": members, "fasta_sha256": fasta_sha, "empirical": "unassessed", "original_authority": "retain_original_inputs_separately"}
    return {"schema_version": api.EXPORT_SCHEMA, "fasta": fasta, "fasta_sha256": fasta_sha, "manifest": manifest, "manifest_sha256": digest(manifest)}


def result(payload, *, status="checked_material", export=False):
    request = payload["request"]
    actual = deepcopy(payload.get("candidate") or candidate(request))
    checked = report(request, actual, payload["limits"], status=status)
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "resource_profile": api.RESOURCE_PROFILE,
        "validation_scope": api.VALIDATION_SCOPE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
        "invocation_fingerprint": digest({"request": request, "candidate": actual, "limits": payload["limits"]}),
        "report_fingerprint": digest(checked), "candidate": actual, "report": checked,
        "artifact": artifact(request, actual, payload["limits"], checked) if export else None}


def capabilities(role):
    profiles = {"policy_material": deepcopy(api.PROFILE)}
    operations = ["capabilities", *api.PROFILE["operations"]]
    if role == "core":
        profiles["policy_material_producer"] = deepcopy(api.PRODUCER_PROFILE)
        operations.append("compile-policy-material")
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": operations, "intent_schemas": ["biocompiler.intent.v0.1"],
        "canonicalization": "python-json-v1", "validation_scopes": [api.VALIDATION_SCOPE], "profiles": profiles,
        "limits": dict(LIMITS), "claim_scope": "Conditional native material checking only."}


class PolicyMaterialTransportTests(unittest.TestCase):
    def setUp(self):
        self.request = original()
        self.candidate = candidate(self.request)
        self.limits = fixture()["limits"]
        self.client = api.PolicyMaterialClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, *, mutate=None, mutate_capabilities=None, on_negotiate=None, role="core", status="checked_material", failure=None, rejection=None):
        def call(_binary, encoded, _timeout, _cancelled):
            request = json.loads(encoded)
            self.calls.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities(role)
                if mutate_capabilities:
                    mutate_capabilities(value)
                if on_negotiate:
                    on_negotiate()
            else:
                if failure:
                    raise failure
                value = result(request["payload"], status=status, export=operation == "export-policy-material")
                if mutate:
                    mutate(value)
            native_status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation, "status": native_status,
                "result": value if native_status == "ok" else None,
                "diagnostics": [] if native_status == "ok" else [{"code": "material_rejected", "message": "Rejected", "path": "/request"}],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}
            return encode_json(response), {"ok": 0, "error": 2, "unsupported": 3}[native_status]
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def check(self):
        return self.client.check(self.request, self.candidate, self.limits)

    def test_compile_check_replay_and_fresh_export_have_exact_inputs(self):
        with self.exchange():
            compiled = self.client.compile(self.request, self.limits)
            checked = self.client.check(self.request, compiled.candidate, self.limits)
            replayed = self.client.replay(self.request, compiled.candidate, self.limits, checked.result)
            exported = self.client.export(self.request, compiled.candidate, self.limits)
        self.assertEqual(compiled.result, replayed.result)
        self.assertIsNone(compiled.artifact)
        self.assertIsNotNone(exported.artifact)
        self.assertEqual(exported.report, checked.report)
        self.assertEqual(exported.artifact["manifest"]["request"], self.request)
        self.assertNotIn("report", self.calls[-1]["payload"])

    def test_native_rejection_is_visible_without_artifact(self):
        with self.exchange(status="not_accepted"):
            value = self.check()
        self.assertEqual(value.status, "not_accepted")
        self.assertIsNone(value.artifact)
        with self.exchange(status="not_accepted"), self.assertRaises(CoreProtocolError):
            self.client.export(self.request, self.candidate, self.limits)

    def test_verify_can_export_but_never_compile(self):
        client = api.PolicyMaterialClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("subprocess.Popen", side_effect=AssertionError("No producer")), self.assertRaises(CoreProtocolError):
            client.compile(self.request, self.limits)
        with self.exchange(role="verify"):
            checked = client.check(self.request, self.candidate, self.limits)
            self.assertEqual(client.replay(self.request, self.candidate, self.limits, checked.result).result, checked.result)
            self.assertIsNotNone(client.export(self.request, self.candidate, self.limits).artifact)

    def test_capabilities_are_exact_and_negotiated_before_operation(self):
        for mutation in (lambda v: v["profiles"].clear(), lambda v: v["validation_scopes"].clear(),
                         lambda v: v["profiles"]["policy_material"].update(artifact="accepted"),
                         lambda v: v["profiles"]["policy_material"].update(max_result_nodes=True)):
            self.calls.clear()
            with self.exchange(mutate_capabilities=mutation), self.assertRaises(CoreProtocolError):
                self.check()
            self.assertEqual(len(self.calls), 1)
        with self.exchange(mutate_capabilities=lambda v: v["profiles"].pop("policy_material_producer")), self.assertRaises(CoreProtocolError):
            self.client.compile(self.request, self.limits)

    def test_snapshot_is_immutable_and_frozen_before_negotiation(self):
        old = deepcopy(self.request)
        with self.exchange(on_negotiate=lambda: self.request["budgets"].update(max_work=1)):
            value = self.check()
        self.assertEqual(self.calls[-1]["payload"]["request"], old)
        value.report["obligations"].clear()
        value.candidate["construction"]["inventory"]["molecules"].clear()
        self.assertTrue(value.report["obligations"])
        self.assertTrue(value.candidate["construction"]["inventory"]["molecules"])
        with self.assertRaises(FrozenInstanceError):
            value.report_fingerprint = "changed"

    def test_rehashed_original_identity_and_claim_mutations_fail(self):
        mutations = (
            lambda v: v.update(implementation="foreign"), lambda v: v.update(request_fingerprint="0" * 64),
            lambda v: v.update(invocation_fingerprint="0" * 64), lambda v: v["report"].update(empirical="verified"),
            lambda v: v["report"].update(artifact="accepted"), lambda v: v["report"]["obligations"].pop(),
            lambda v: v["report"]["obligations"].extend(deepcopy(v["report"]["obligations"])), lambda v: v["report"]["obligations"][0].update(evidence={}),
            lambda v: v["report"].update(all_original_obligations_discharged=1),
            lambda v: v["report"]["usage"].update(charged_work=True),
            lambda v: v["report"]["usage"].update(request_decoding_work=10001),
            lambda v: v["report"]["usage"].update(unit="bytes"), lambda v: v["report"]["usage"].update(charged_work=1000000001),
            lambda v: v["report"]["budgets"].update(max_work=1), lambda v: v["report"]["limits"]["source"].update(max_work=1),
            lambda v: v["report"]["material"].update(contract_fingerprint="0" * 64),
            lambda v: v["report"]["material"].update(resource_capacity="pass"),
            lambda v: v["report"]["context"].update(context_fingerprint="0" * 64),
            lambda v: v["report"]["catalog"]["original_binding"].update(entry_id="foreign"),
            lambda v: v["report"]["preservation"]["requirements"].clear(),
            lambda v: v["candidate"]["construction"]["inventory"]["molecules"][0].update(sequence="AAAA"),
            lambda v: v["candidate"]["behavior"]["source_document"]["assurance"]["requirements"].clear(),
        )
        for index, mutate in enumerate(mutations):
            def changed(value):
                mutate(value)
                value["report_fingerprint"] = digest(value["report"])
                value["candidate_fingerprint"] = digest(value["candidate"])
            with self.subTest(mutation=index), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.check()

    def test_export_pair_must_match_complete_originals_and_checked_members_even_when_rehashed(self):
        mutations = (lambda a: a.update(fasta="wrong\n"), lambda a: a["manifest"].update(empirical="verified"),
            lambda a: a["manifest"]["members"].clear(), lambda a: a["manifest"]["members"][0].update(fasta_id="injected\nheader"),
            lambda a: a["manifest"]["members"][0]["molecule"].update(sequence="AAAA"),
            lambda a: a["manifest"]["request"]["budgets"].update(max_work=1),
            lambda a: a["manifest"]["assessment"].update(status="forged"), lambda a: a["manifest"].pop("bindings"))
        for index, mutate in enumerate(mutations):
            def changed(value):
                mutate(value["artifact"])
                value["artifact"]["manifest_sha256"] = digest(value["artifact"]["manifest"])
                value["artifact"]["fasta_sha256"] = hashlib.sha256(value["artifact"]["fasta"].encode()).hexdigest()
            with self.subTest(mutation=index), self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
                self.client.export(self.request, self.candidate, self.limits)
        with self.exchange(mutate=lambda v: v.update(artifact={})), self.assertRaises(CoreProtocolError):
            self.check()

    def test_replay_requires_entire_check_wrapper_and_cannot_reuse_export(self):
        with self.exchange():
            checked = self.check()
            exported = self.client.export(self.request, self.candidate, self.limits)
        for saved in (checked.report, exported.result, {**checked.result, "implementation": "foreign"}):
            with self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, self.candidate, self.limits, saved)

    def test_transport_failures_have_no_semantic_fallback(self):
        for failure in (CoreTimeout("timeout"), CoreTransportError("crash"), CoreCancelled("cancelled")):
            with self.exchange(failure=failure), self.assertRaises(type(failure)), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No fallback")):
                self.check()
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.exchange(rejection=status), self.assertRaises(error):
                self.check()
        client = api.PolicyMaterialClient(CoreClient(ROOT / "missing-material-executable"))
        with self.assertRaises(CoreUnavailable):
            client.compile(self.request, self.limits)

    def test_literal_input_and_complete_publication_bounds(self):
        for request in (object(), lambda: self.request, self.request["implementation_request"]):
            with self.assertRaises(CoreProtocolError), patch("subprocess.Popen", side_effect=AssertionError("No Python execution")):
                self.client.compile(request, self.limits)
        for key in ("MAX_RESULT_BYTES", "MAX_RESULT_NODES"):
            with self.exchange(), patch.object(api, key, 10), self.assertRaises(CoreProtocolError):
                self.check()
        self.assertEqual(api.MAX_RESULT_BYTES, LIMITS["max_response_bytes"] - 6 * LIMITS["max_string_bytes"] - 65536)
        self.assertEqual(api.MAX_RESULT_NODES, LIMITS["max_json_nodes"] - 32)


if __name__ == "__main__":
    unittest.main()
