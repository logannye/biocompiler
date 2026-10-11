"""Inert expression transport peers; none of these tests establish native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler import core_policy_expression_material as api
from biocompiler.core_client import (CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL,
    CoreClient, CoreProtocolError, CoreResponse, CoreTransportError, CoreRejected, encode_json)
from biocompiler.policy.expression_material import ExpressionBudgets, ExpressionMaterialRequest, ExpressionSelection
from biocompiler.policy import expression_material as facade
from biocompiler.policy.model import BuildRequest
from biocompiler.policy.serialization import from_data, to_data
from tests.test_core_policy import assessment, digest, semantic

ROOT = Path(__file__).resolve().parents[1]


def definition(name, category, meaning="Artificial conditional software premise; biological function unassessed."):
    return {"$type": "SemanticDefinition", "id": name, "version": "1", "category": category, "meaning": meaning,
        "parameters": [], "result": None, "clauses": [], "assumptions": [], "executor_kind": None, "subject_kind": None}


def ref(kind, name):
    return {"$type": "Ref", "id": name, "kind": kind}


def pin(value):
    return {"$type": "DefinitionRef", "id": value["id"], "version": value["version"], "digest": digest(semantic(value))}


def identity(kind, name, body):
    return {"schema_version": "biocompiler.component_identity.v0.1", "kind": kind, "id": name, "version": "1", "content_fingerprint": digest(body)}


def original():
    """Artificial MA authority and explicit static source, not a CAR or biological fixture."""
    base = json.loads((ROOT / "core/test/data/policy_material_request_v01.json").read_text())
    authority = base["request"]["material_contract"]["body"]["structure_authority"]
    product = identity("reference", "artificial.complete.product", {"schema_version": "biocompiler.policy_mrna_product_content.v0.1", "alphabet": "protein", "sequence_extent": "complete", "sequence": "MA"})
    authority["members"][0]["product"]["identity"] = product
    objective_def = definition("biocompiler.expression.objective.v1", "requirement", "Exact source-selected complete product encoding and supplied conditional localization for one declared human immune recipient; no empirical expression or therapeutic function is established.")
    operation = definition("biocompiler.expression.encode.v1", "operation", "Construct one complete original mRNA encoding the exact supplied product under the explicit expression/localization contract; no runtime action or biological realization is inferred.")
    translation = definition("biocompiler.expression.nominal_translation.v1", "model", "Decode the explicitly declared canonical parent RNA bases with the standard genetic code and the selected one or two consecutive terminal stop codons; this nominal correspondence does not establish physical translation of modified nucleotides or biological expression.")
    realization = definition("artificial.expression", "model")
    localization = definition("artificial.surface", "spatial")
    environment = definition("artificial.environment", "environment")
    delivery = definition("artificial.delivery", "delivery")
    chassis_model = definition("artificial.chassis_model", "model")
    capability = definition("artificial.capability", "capability")
    role = {"$type": "Role", "id": "recipient", "requires": [pin(capability)], "population": None, "lineage_role": False}
    parameters = [{"$type": "Parameter", "id": name, "value_type": {"$type": "TypeSpec", "kind": kind, "unit": None, "entity_kind": None}, "value": value, "lower": None, "upper": None, "selection": "fixed"}
        for name, kind, value in (("product_id", "text", product["id"]), ("product_version", "text", "1"), ("product_sha256", "text", product["content_fingerprint"]), ("localization", "text", localization["id"]), ("maximum_rna_nt", "integer", 1000))]
    objective = {"$type": "Requirement", "id": "encode", "kind": "objective", "description": "Artificial exact encoding objective, not a biological claim.", "scope": {"$type": "Scope", "kind": "executor", "subject": ref("Role", "recipient")},
        "condition": None, "response": None, "deadline": None, "lower": None, "upper": None, "horizon": None, "assumptions": [],
        "applies_to": [ref("Role", "recipient"), *[ref("Parameter", item["id"]) for item in parameters]], "contract": pin(objective_def), "trigger": None, "clock": None}
    program = {"$type": "PolicyProgram", "id": "artificial.expression.source", "semantics": {"$type": "SemanticBundle", "id": "artificial.definitions", "version": "1", "definitions": [objective_def, operation, translation, realization, localization, environment, delivery, chassis_model, capability], "profile": "biocompiler.policy.v0.1"}, "declarations": [role, *parameters, objective], "source_map": [], "profile": "biocompiler.policy.v0.1"}
    chassis = {"$type": "ChassisProfile", "id": "artificial.human_immune", "version": "1", "lineage": "immune", "subtype": "artificial", "activation_states": [], "differentiation_states": [], "capabilities": [pin(capability)], "operational_model": pin(chassis_model), "environment": [pin(environment)], "interfaces": [], "species": "human", "recipient_class": "immune"}
    deployment = {"$type": "Deployment", "id": "artificial.deployment", "bindings": [{"$type": "RoleBinding", "role": ref("Role", "recipient"), "chassis": chassis}], "environment": [pin(environment)],
        "delivery": {"$type": "DeliveryContract", "id": "artificial.delivery_contract", "intended_recipients": [ref("Role", "recipient")], "arrival": pin(delivery), "expression": pin(delivery), "activation": pin(delivery), "co_delivery": "none_required", "contract": pin(delivery), "assumptions": []},
        "payload": {"$type": "RNAConstraints", "design_count": 1, "member_count": 1, "helper_count": 0, "copy_number": None, "dose": None, "orf_count": 1, "product_count": 1, "payload_persistence": None, "effector_persistence": None, "format": "RNA"}, "route": "in_vivo"}
    entry = {"$type": "ImplementationBinding", "id": "artificial.expression.entry", "version": "1", "operation": pin(operation), "realization": pin(realization), "chassis": [chassis["id"]], "payload_formats": ["RNA"], "dependencies": [pin(translation)], "evidence": []}
    document = {"$type": "BuildRequest", "program": program, "deployment": deployment, "implementations": {"$type": "ImplementationCatalogLock", "id": "artificial.catalog", "version": "1", "implementations": [entry]},
        "assurance": {"$type": "AssuranceRequest", "requirements": ["encode"], "level": "structural", "horizon": "not_applicable", "assumptions": [], "tolerances": []}, "profile": api.SOURCE_PROFILE}
    body = {"schema_version": api.CONTRACT_SCHEMA, "operation": pin(operation), "realization": pin(realization), "product": product, "recipient": chassis, "deployment": deployment, "localization": localization,
        "material": {"structure_sha256": digest(authority), "member": "payload", "cds": "cds"}, "translation": {"interpretation": "nominal_canonical_parent_bases", "terminal_stop_codons": 1, "model": pin(translation)}, "dependencies": [pin(translation)], "evidence": [], "claim_scope": api.CLAIM}
    return {"schema_version": api.REQUEST_SCHEMA, "profile": api.REQUEST_PROFILE, "document": document,
        "selection": {"objective": "encode", "recipient": "recipient", "implementation": identity("registry", entry["id"], entry), "member": "payload", "cds": "cds"},
        "expression_contract": {"identity": identity("model", "artificial.expression.contract", body), "body": body}, "structure_authority": authority,
        "project_context": {"project_id": "artificial.expression", "title": "Artificial software evidence only", "sources": [{"id": "artificial-source", "locator": "software fixture", "version": "1", "sha256": digest(authority), "role": "artificial fixture", "reuse_terms": "repository software fixture"}], "assumptions": ["No biological claim."]},
        "budgets": ExpressionBudgets().to_data()}


def candidate():
    fixture = json.loads((ROOT / "core/test/data/policy_material_request_v01.json").read_text())
    return {"schema_version": api.CANDIDATE_SCHEMA, "construction": fixture["candidate_parts"]["construction"]}


def structure(request, actual):
    from tests.test_core_policy_material import report as old_report, original as old_original, candidate as old_candidate, fixture as old_fixture
    # Reuse only the independent literal content-receipt shape, not old acceptance.
    old_request = old_original()
    result = old_report(old_request, old_candidate(old_request), old_fixture()["limits"])["material"]["structure"]
    authority = request["structure_authority"]
    result.update(schema_version="biocompiler.policy_expression_structure_assessment.v0.1", profile="biocompiler.policy_expression_nominal_structure.v0.1", implementation_version="biocompiler.ocaml.policy_expression_structure_check.v0.1",
        claim_scope="exact_supplied_mrna_structure_under_nominal_translation_premise", translation_interpretation="nominal_canonical_parent_bases", terminal_stop_codons=1,
        translation_model=request["expression_contract"]["body"]["translation"]["model"], physical_translation="unassessed", authority_fingerprint=digest(authority), candidate_fingerprint=digest(actual["construction"]))
    result["content_reconstruction"].update(authority_fingerprint=digest({"schema_version": "biocompiler.construction_content_authority.v0.1", "template": authority["template"], "member_order": authority["member_order"]}), candidate_fingerprint=digest(actual["construction"]), reconstructed_fingerprint=digest(actual["construction"]))
    molecule = actual["construction"]["inventory"]["molecules"][0]
    result["members"] = [{"member": "payload", "molecule_fingerprint": digest(molecule), "product_identity": authority["members"][0]["product"]["identity"], "expected_product": "MA", "translated_product": "MA"}]
    return result


def report(request, actual):
    doc = request["document"]
    assessed = assessment(doc)
    definitions = doc["program"]["semantics"]["definitions"]
    assessed["unresolved_obligations"] = sorted(["policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "persistent_encounter_identity_lifetime", "state_lifetime_capacity_and_inheritance", "effect_authorization_feedback_and_cancellation", "arbitration_fairness_and_conflict_resolution", "safety_and_progress_satisfaction", "requested_assurance_not_established", "realizability_and_target_suitability", "implementation_catalog_applicability", "chassis_capability_and_delivery_suitability", "requirement_satisfaction:encode", "implementation_applicability:artificial.expression.entry", *["semantic_definition:" + value["id"] for value in definitions]])
    max_nt = next(value["value"] for value in doc["program"]["declarations"] if value["id"] == "maximum_rna_nt")
    body = request["expression_contract"]["body"]
    admission = {"schema_version": "biocompiler.policy_expression_source_admission.v0.1", "status": "admitted_static_expression_source", "request_fingerprint": digest(request), "source_artifact_digest": digest(doc), "source_semantic_digest": digest(semantic(doc)), "objective": "encode", "objective_path": "/document/program/declarations/6", "product": body["product"], "maximum_rna_nt": max_nt,
        "unresolved_obligations": sorted([*assessed["unresolved_obligations"], "expression_material_correspondence"]), "source_assessment": assessed, "temporal_execution": "not_requested_by_supported_objective", "expression_claim": "withheld", "empirical_realization": "unassessed", "human_use": "unassessed", "export": "withheld"}
    leaf = structure(request, actual)
    length = len(actual["construction"]["inventory"]["molecules"][0]["sequence"])
    passed = length <= max_nt
    pins = {"source": digest(admission), "structure": digest(leaf), "contract": request["expression_contract"]["identity"]}
    rows = []
    for name in admission["unresolved_obligations"]:
        if name in {"policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "persistent_encounter_identity_lifetime", "state_lifetime_capacity_and_inheritance", "effect_authorization_feedback_and_cancellation", "arbitration_fairness_and_conflict_resolution"}:
            status, stage, evidence = "not_applicable", "closed_static_source_admission", {"source": digest(admission)}
        elif name.startswith("semantic_definition:"):
            definition_value = next(value for value in definitions if value["id"] == name.split(":", 1)[1])
            interpreted = definition_value in definitions[:3]
            status = "discharged" if interpreted else "conditional"
            stage = "closed_normative_static_interpretation" if interpreted else "resolved_original_context_or_component_premise"
            evidence = {"source": digest(admission), "definition": pin(definition_value), "body": definition_value, "contract": request["expression_contract"]["identity"]}
        elif name in {"realizability_and_target_suitability", "implementation_catalog_applicability", "chassis_capability_and_delivery_suitability"}:
            status, stage, evidence = "conditional" if passed else "unresolved", "supplied_expression_localization_and_recipient_premises", pins
        elif name.startswith("implementation_applicability:"):
            status, stage, evidence = "conditional" if passed else "unresolved", "complete_supplied_implementation_contract", pins
        else:
            status, stage, evidence = "discharged" if passed else "unresolved", "exact_static_encoding_and_length", pins
        rows.append({"obligation": name, "status": status, "stage": stage, "evidence": evidence})
    requirement = {"id": "encode", "path": admission["objective_path"], "status": "pass" if passed else "fail", "product": body["product"], "member": "payload", "cds": "cds", "maximum_rna_nt": max_nt, "actual_rna_nt": length, "length_status": "pass" if passed else "fail", "localization": body["localization"], "localization_status": "supplied_premise", "diagnostics": [] if passed else [{"code": "expression_rna_length_requirement", "path": admission["objective_path"], "message": "RNA exceeds source bound."}]}
    return {"schema_version": api.REPORT_SCHEMA, "profile": api.REQUEST_PROFILE, "implementation": "biocompiler.ocaml.policy_expression_material_check.v0.1", "resource_profile": api.RESOURCE_PROFILE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest({"request": request, "candidate": actual}), "status": "checked_expression_material" if passed else "not_accepted", "claim_scope": api.CLAIM, "premise": api.PREMISE,
        "source_admission": admission, "structure": leaf, "requirements": [requirement], "obligations": rows, "all_original_obligations_dispositioned": passed, "budgets": request["budgets"], "empirical": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld", "usage": {"unit": "logical_data_visits_and_child_semantic_work", "charged_work": 10000, "request_decoding_work": 2000}}


def artifact(request, actual, checked):
    molecule = actual["construction"]["inventory"]["molecules"][0]
    sequence = molecule["sequence"]
    fasta = ">rna_0001 alphabet=RNA\n" + "".join(sequence[index:index + 80] + "\n" for index in range(0, len(sequence), 80))
    fasta_hash = hashlib.sha256(fasta.encode()).hexdigest()
    manifest = {"schema_version": api.MANIFEST_SCHEMA, "profile": api.REQUEST_PROFILE, "claim_scope": api.CLAIM, "premise": api.PREMISE, "request": deepcopy(request), "candidate": deepcopy(actual), "assessment": deepcopy(checked),
        "bindings": {"request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest({"request": request, "candidate": actual}), "assessment_fingerprint": digest(checked)},
        "members": [{"fasta_id": "rna_0001", "member_id": molecule["id"], "molecule": deepcopy(molecule), "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest()}], "fasta_sha256": fasta_hash,
        "empirical": "unassessed", "human_use": "unassessed", "original_authority": "retain_original_inputs_separately"}
    return {"schema_version": api.EXPORT_SCHEMA, "fasta": fasta, "fasta_sha256": fasta_hash, "manifest": manifest, "manifest_sha256": digest(manifest)}


def result(payload, operation="check-policy-expression-material"):
    request = deepcopy(payload["request"])
    actual = deepcopy(payload.get("candidate", candidate()))
    checked = report(request, actual)
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "resource_profile": api.RESOURCE_PROFILE, "validation_scope": api.VALIDATION_SCOPE,
        "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest({"request": request, "candidate": actual}), "report_fingerprint": digest(checked),
        "candidate": actual, "report": checked, "artifact": artifact(request, actual, checked) if operation == "export-policy-expression-material" else None,
        "usage": {"unit": "logical_data_visits_and_child_semantic_work", "total_charged_work": 20000, "checker_charged_work": 10000}}


def capabilities(role):
    profiles = {"policy_expression_material": deepcopy(api.PROFILE)}
    operations = ["capabilities", *api.PROFILE["operations"]]
    if role == "core":
        profiles["policy_expression_material_producer"] = deepcopy(api.PRODUCER_PROFILE)
        operations.append("compile-policy-expression-material")
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": operations, "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1", "validation_scopes": [api.VALIDATION_SCOPE], "profiles": profiles, "limits": dict(LIMITS), "claim_scope": "Conditional supplied expression contract only."}


class ExpressionMaterialTransportTests(unittest.TestCase):
    def setUp(self):
        self.request = original()
        self.candidate = candidate()
        self.calls = []

    def peer(self, role="verify", mutate=None, caps=None, on_negotiate=None):
        def exchange(_executable, encoded, _timeout, _cancelled):
            raw = json.loads(encoded)
            self.calls.append(raw)
            operation = raw["operation"]
            if operation == "capabilities":
                value = capabilities(role)
                if caps:
                    caps(value)
                if on_negotiate:
                    on_negotiate()
            else:
                value = result(raw["payload"], operation)
                if mutate:
                    mutate(value)
            return encode_json({"protocol": PROTOCOL, "request_id": raw["request_id"], "operation": operation, "status": "ok", "result": value, "diagnostics": [], "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=exchange)

    def client(self, role="verify"):
        return api.PolicyExpressionMaterialClient(CoreClient(Path(sys.executable), role=role))

    def test_complete_compile_check_replay_export_routes(self):
        with self.peer("core"):
            compiled = self.client("core").compile(self.request)
        with self.peer():
            checked = self.client().check(self.request, compiled.candidate)
            replayed = self.client().replay(self.request, compiled.candidate, checked.result)
            exported = self.client().export(self.request, compiled.candidate)
        self.assertEqual(checked.result, replayed.result)
        self.assertEqual(exported.artifact["manifest"]["request"], self.request)
        self.assertEqual(exported.artifact["manifest"]["human_use"], "unassessed")
        self.assertNotIn("limits", self.calls[-1]["payload"])
        self.assertEqual({call["operation"] for call in self.calls if call["operation"] != "capabilities"}, set(api.PROFILE["operations"]) | {"compile-policy-expression-material"})

    def test_snapshot_before_negotiation_and_detached_evidence(self):
        expected = deepcopy(self.request)
        with self.peer(on_negotiate=lambda: self.request["project_context"].update(title="changed caller")):
            checked = self.client().check(self.request, self.candidate)
        self.assertEqual(self.calls[-1]["payload"]["request"], expected)
        checked.report["status"] = "forged"
        checked.candidate["schema_version"] = "forged"
        self.assertEqual(checked.status, "checked_expression_material")
        self.assertEqual(checked.candidate["schema_version"], api.CANDIDATE_SCHEMA)
        with self.assertRaises(FrozenInstanceError):
            checked.operation = "forged"

    def test_semantic_source_edit_is_retained_and_can_fail_without_export(self):
        self.request["document"]["program"]["declarations"][5]["value"] = 1
        with self.peer():
            checked = self.client().check(self.request, self.candidate)
        self.assertEqual(checked.status, "not_accepted")
        self.assertFalse(checked.report["all_original_obligations_dispositioned"])
        self.assertIsNone(checked.artifact)
        with self.peer(), self.assertRaises(CoreProtocolError):
            self.client().export(self.request, self.candidate)

    def test_rejects_rehashed_claim_ledger_source_and_structure_forgery(self):
        def nested(path, value):
            def mutate(result):
                current = result["report"]
                for key in path[:-1]:
                    current = current[key]
                current[path[-1]] = value
                result["report_fingerprint"] = digest(result["report"])
            return mutate
        mutations = [(("human_use",), "validated"), (("premise",), "empirical"), (("obligations",), []),
            (("all_original_obligations_dispositioned",), False), (("obligations", 0, "status"), "discharged"),
            (("source_admission", "objective_path"), "/foreign"), (("source_admission", "source_assessment", "declarations", 0, "value", "id"), "foreign"),
            (("structure", "translation_model", "digest"), "0" * 64), (("structure", "physical_translation"), "proven"),
            (("structure", "members", 0, "translated_product"), "different"), (("structure", "unassessed_clauses"), []),
            (("structure", "content_reconstruction", "authority_fingerprint"), "0" * 64), (("requirements", 0, "actual_rna_nt"), 1),
            (("requirements", 0, "localization_status"), "demonstrated")]
        for path, value in mutations:
            with self.subTest(path=path), self.peer(mutate=nested(path, value)), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)

    def test_rejects_complete_invocation_and_work_accounting_forgery(self):
        for mutate in (lambda r: r.update(request_fingerprint="0" * 64), lambda r: r["candidate"].update(schema_version="old"),
                       lambda r: r.update(invocation_fingerprint=digest({"request": self.request, "candidate": self.candidate, "limits": {}})),
                       lambda r: r["usage"].update(total_charged_work=100_000_001), lambda r: r["usage"].update(checker_charged_work=9999),
                       lambda r: r["usage"].update(total_charged_work=9999), lambda r: r["usage"].update(total_charged_work=True)):
            with self.subTest(mutate=mutate), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)

    def test_rejects_export_mutation_even_with_updated_manifest_digest(self):
        for key, value in (("human_use", "accepted"), ("request", {}), ("members", []), ("extra", "hidden")):
            def mutate(result):
                result["artifact"]["manifest"][key] = value
                result["artifact"]["manifest_sha256"] = digest(result["artifact"]["manifest"])
            with self.subTest(key=key), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client().export(self.request, self.candidate)
        with self.peer(mutate=lambda r: r["artifact"].update(fasta="different")), self.assertRaises(CoreProtocolError):
            self.client().export(self.request, self.candidate)

    def test_rejects_forged_replay_and_nonexport_publication(self):
        saved = result({"request": self.request, "candidate": self.candidate})
        saved["usage"]["total_charged_work"] += 1
        with self.peer(), self.assertRaises(CoreProtocolError):
            self.client().replay(self.request, self.candidate, saved)
        with self.peer(mutate=lambda r: r.update(artifact={})), self.assertRaises(CoreProtocolError):
            self.client().check(self.request, self.candidate)

    def test_capability_role_and_transport_fail_closed(self):
        with self.assertRaises(CoreProtocolError):
            self.client().compile(self.request)
        for mutate in (lambda c: c["profiles"].pop("policy_expression_material"), lambda c: c["profiles"]["policy_expression_material"].update(empirical="proven"), lambda c: c.update(validation_scopes=[])):
            with self.peer(caps=mutate), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)
        with patch("biocompiler.core_client._exchange", side_effect=CoreTransportError("unavailable")), self.assertRaises(CoreTransportError):
            self.client().check(self.request, self.candidate)

    def test_closed_originals_and_budget_rejections(self):
        for path, value in ((["profile"], "legacy"), (["extra"], {}), (["budgets", "max_work"], True), (["budgets", "max_work"], 100_000_001), (["expression_contract", "identity", "content_fingerprint"], "0" * 64), (["project_context", "sources"], []), (["project_context", "sources"], [self.request["project_context"]["sources"][0]] * 2)):
            changed = deepcopy(self.request)
            row = changed
            for key in path[:-1]:
                row = row[key]
            row[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(CoreProtocolError):
                api._original(changed)

    def test_complete_normative_definitions_and_context_premises_remain_distinct(self):
        definitions = self.request["document"]["program"]["semantics"]["definitions"]
        self.assertEqual({digest(value) for value in definitions[:3]}, api._NORMATIVE_DEFINITION_DIGESTS)
        with self.peer():
            checked = self.client().check(self.request, self.candidate)
        dispositions = {row["obligation"]: row for row in checked.report["obligations"]}
        for definition_value in definitions[:3]:
            row = dispositions["semantic_definition:" + definition_value["id"]]
            self.assertEqual(row["status"], "discharged")
            self.assertEqual(row["evidence"]["body"], definition_value)
        self.assertEqual(dispositions["chassis_capability_and_delivery_suitability"]["status"], "conditional")
        def mutate(result):
            row = next(row for row in result["report"]["obligations"] if row["obligation"] == "semantic_definition:artificial.surface")
            row["status"] = "discharged"
            row["stage"] = "closed_normative_static_interpretation"
            result["report_fingerprint"] = digest(result["report"])
        with self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
            self.client().check(self.request, self.candidate)

    def test_project_metadata_and_nominal_model_edits_invalidate_retained_results(self):
        stale = result({"request": self.request, "candidate": self.candidate})
        for field, value in (("title", "different supplied study"), ("assumptions", ["different context"])):
            changed = deepcopy(self.request)
            changed["project_context"][field] = value
            response = CoreResponse("test", "check-policy-expression-material", "ok", stale, (), "verify", CORE_VERSION)
            with self.subTest(field=field), self.assertRaises(CoreProtocolError):
                api._result(response, {"request": changed, "candidate": self.candidate})
        changed = deepcopy(self.request)
        changed["expression_contract"]["body"]["translation"]["terminal_stop_codons"] = 2
        changed["expression_contract"]["identity"]["content_fingerprint"] = digest(changed["expression_contract"]["body"])
        with self.peer(), self.assertRaises(CoreProtocolError):
            self.client().check(changed, self.candidate)  # Peer still advertises the one-stop leaf.

    def test_explicit_rejection_never_becomes_a_python_candidate(self):
        def exchange(_executable, encoded, _timeout, _cancelled):
            raw = json.loads(encoded)
            operation = raw["operation"]
            value = capabilities("verify") if operation == "capabilities" else None
            response = {"protocol": PROTOCOL, "request_id": raw["request_id"], "operation": operation,
                "status": "ok" if value is not None else "error", "result": value,
                "diagnostics": [] if value is not None else [{"code": "policy_expression_source_unsupported", "message": "Unsupported source objective", "path": "/document/program/declarations/6"}],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "verify"}}
            return encode_json(response), 0 if value is not None else 2
        with patch("biocompiler.core_client._exchange", side_effect=exchange), self.assertRaises(CoreRejected) as raised:
            self.client().check(self.request, self.candidate)
        self.assertEqual(raised.exception.response.diagnostics[0].code, "policy_expression_source_unsupported")

    def test_exact_project_context_utf8_and_source_census_bounds(self):
        for path, value in ((["project_id"], "é" * 65), (["title"], "x" * 4097),
                            (["assumptions"], ["x"] * 129), (["sources"], self.request["project_context"]["sources"] * 129),
                            (["sources", 0, "sha256"], "G" * 64), (["sources", 0, "reuse_terms"], " ")):
            changed = deepcopy(self.request)
            row = changed["project_context"]
            for key in path[:-1]:
                row = row[key]
            row[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(CoreProtocolError):
                ExpressionMaterialRequest.from_request(changed)
        self.request["project_context"]["title"] = "  preserved title  "
        self.assertEqual(ExpressionMaterialRequest.from_request(self.request).to_request(), self.request)

    def test_typed_constructor_and_exact_import_are_immutable(self):
        typed = ExpressionMaterialRequest.from_request(self.request)
        constructed = ExpressionMaterialRequest(document=typed.document, selection=typed.selection, budgets=typed.budgets,
            expression_contract=self.request["expression_contract"], structure_authority=self.request["structure_authority"], project_context=self.request["project_context"])
        self.assertEqual(constructed.to_request(), self.request)
        self.assertEqual(to_data(typed.document), self.request["document"])
        self.request["project_context"]["title"] = "later mutation"
        constructed.to_request()["expression_contract"]["body"]["claim_scope"] = "forged"
        self.assertEqual(constructed.to_request(), typed.to_request())
        with self.assertRaises(FrozenInstanceError):
            typed._request_json = b"{}"
        with self.assertRaises(TypeError):
            ExpressionMaterialRequest(document={}, selection=typed.selection, expression_contract={}, structure_authority={}, project_context={})

    def test_typed_routes_and_atomic_exact_export(self):
        typed = ExpressionMaterialRequest.from_request(self.request)
        with self.peer("core"):
            compiled = facade.compile(typed, client=self.client("core"))
        with tempfile.TemporaryDirectory() as directory, self.peer():
            path = Path(directory) / "expression.zip"
            checked = facade.check(typed, candidate=compiled.candidate, client=self.client())
            facade.replay(typed, candidate=compiled.candidate, report=checked.result, client=self.client())
            exported = facade.export(typed, candidate=compiled.candidate, client=self.client(), output=path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                self.assertEqual(archive.read("program.fasta"), exported.artifact["fasta"].encode())
                self.assertEqual(archive.read("manifest.json"), encode_json(exported.artifact["manifest"]))
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                facade.export(typed, candidate=compiled.candidate, client=self.client(), output=path)
            self.assertEqual(path.read_bytes(), before)

    def test_publication_ceiling_and_unknown_field_are_not_ignored(self):
        self.request["budgets"]["max_report_nodes"] = 1
        with self.peer(), self.assertRaises(CoreProtocolError):
            self.client().check(self.request, self.candidate)
        self.request = original()
        with self.peer(mutate=lambda r: r.update(extra="unreviewed")), self.assertRaises(CoreProtocolError):
            self.client().check(self.request, self.candidate)


if __name__ == "__main__":
    unittest.main()
