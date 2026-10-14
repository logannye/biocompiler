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


# Literal M1 contract oracle. These values come from the normative disposition
# table and the versioned correction proposal, never from a production grouping.
REPORT_V02 = "biocompiler.policy_expression_material_assessment.v0.2"
CHECKER_V02 = "biocompiler.ocaml.policy_expression_material_check.v0.2"
SERVICE_V02 = "biocompiler.ocaml.policy_expression_material.v0.2"
EXACT_FASTA = ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n"
FIXED_DISPOSITIONS = (
    ("policy_execution_and_lowering", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", "source"),
    ("temporal_and_uncertainty_semantics", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", "source"),
    ("safety_and_progress_satisfaction", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", "source"),
    ("realizability_and_target_suitability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/deployment", "join"),
    ("chassis_capability_and_delivery_suitability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/deployment", "join"),
    ("implementation_catalog_applicability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/implementations", "join"),
    ("requested_assurance_not_established", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/assurance", "join"),
    ("implementation_applicability:artificial.expression.entry", "conditional", "unresolved", "complete_supplied_implementation_contract", "/document/implementations/implementations/0", "join"),
    ("requirement_satisfaction:encode", "discharged", "unresolved", "exact_static_encoding_and_length", "/document/program/declarations/6", "join"),
    ("expression_material_correspondence", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document", "join"),
)
DEFINITION_DISPOSITIONS = (
    ("biocompiler.expression.objective.v1", "discharged", "closed_normative_static_interpretation"),
    ("biocompiler.expression.encode.v1", "discharged", "closed_normative_static_interpretation"),
    ("biocompiler.expression.nominal_translation.v1", "discharged", "closed_normative_static_interpretation"),
    ("artificial.expression", "conditional", "resolved_original_context_or_component_premise"),
    ("artificial.surface", "conditional", "resolved_original_context_or_component_premise"),
    ("artificial.environment", "conditional", "resolved_original_context_or_component_premise"),
    ("artificial.delivery", "conditional", "resolved_original_context_or_component_premise"),
    ("artificial.chassis_model", "conditional", "resolved_original_context_or_component_premise"),
    ("artificial.capability", "conditional", "resolved_original_context_or_component_premise"),
)
PHANTOM_RUNTIME_IDS = (
    "persistent_encounter_identity_lifetime",
    "state_lifetime_capacity_and_inheritance",
    "effect_authorization_feedback_and_cancellation",
    "arbitration_fairness_and_conflict_resolution",
)


def literal_ledger(request, admission, leaf, passed):
    """Supply inert report bytes from the independent literal contract table."""
    source_pin = digest(admission)
    contract = request["expression_contract"]["identity"]
    evidence = {"source": {"source": source_pin},
        "join": {"source": source_pin, "structure": digest(leaf), "contract": contract}}
    rows = []
    for name, success, failure, stage, path, dependency in FIXED_DISPOSITIONS:
        if name == "requirement_satisfaction:encode":
            path = admission["objective_path"]
        rows.append({"obligation": name, "path": path,
            "status": success if passed else failure, "stage": stage,
            "evidence": deepcopy(evidence[dependency])})
    normative = {value["id"]: value for value in
        original()["document"]["program"]["semantics"]["definitions"]
        if value["id"] in {name for name, status, _ in DEFINITION_DISPOSITIONS if status == "discharged"}}
    seen = set()
    for index, value in enumerate(request["document"]["program"]["semantics"]["definitions"]):
        # Malicious-peer tests deliberately present duplicate originals while
        # claiming a unique child census; the SDK must reject the originals.
        if value["id"] in seen:
            continue
        seen.add(value["id"])
        interpreted = value == normative.get(value["id"])
        rows.append({"obligation": "semantic_definition:" + value["id"],
            "path": f"/document/program/semantics/definitions/{index}",
            "status": "discharged" if interpreted else "conditional",
            "stage": "closed_normative_static_interpretation" if interpreted else "resolved_original_context_or_component_premise",
            "evidence": {"source": source_pin, "definition": pin(value),
                "body": deepcopy(value), "contract": deepcopy(contract)}})
    return sorted(rows, key=lambda row: row["obligation"])


def rehash_result(value, *, rebind_dependencies=False):
    """Rehash transport attacks without consulting production dispositions."""
    checked = value["report"]
    if rebind_dependencies:
        for row in checked["obligations"]:
            evidence = row["evidence"]
            if isinstance(evidence, dict):
                if "source" in evidence:
                    evidence["source"] = digest(checked["source_admission"])
                if "structure" in evidence:
                    evidence["structure"] = digest(checked["structure"])
    value["report_fingerprint"] = digest(checked)


def report(request, actual):
    doc = request["document"]
    assessed = assessment(doc)
    definitions = doc["program"]["semantics"]["definitions"]
    assessed["unresolved_obligations"] = sorted({*[row[0] for row in FIXED_DISPOSITIONS if row[0] != "expression_material_correspondence"], *["semantic_definition:" + value["id"] for value in definitions]})
    max_nt = next(value["value"] for value in doc["program"]["declarations"] if value["id"] == "maximum_rna_nt")
    body = request["expression_contract"]["body"]
    objective_index = next(index for index, value in enumerate(doc["program"]["declarations"]) if value["$type"] == "Requirement")
    admission = {"schema_version": "biocompiler.policy_expression_source_admission.v0.1", "status": "admitted_static_expression_source", "request_fingerprint": digest(request), "source_artifact_digest": digest(doc), "source_semantic_digest": digest(semantic(doc)), "objective": "encode", "objective_path": f"/document/program/declarations/{objective_index}", "product": body["product"], "maximum_rna_nt": max_nt,
        "unresolved_obligations": sorted([*assessed["unresolved_obligations"], "expression_material_correspondence"]), "source_assessment": assessed, "temporal_execution": "not_requested_by_supported_objective", "expression_claim": "withheld", "empirical_realization": "unassessed", "human_use": "unassessed", "export": "withheld"}
    leaf = structure(request, actual)
    length = len(actual["construction"]["inventory"]["molecules"][0]["sequence"])
    passed = length <= max_nt
    rows = literal_ledger(request, admission, leaf, passed)
    requirement = {"id": "encode", "path": admission["objective_path"], "status": "pass" if passed else "fail", "product": body["product"], "member": "payload", "cds": "cds", "maximum_rna_nt": max_nt, "actual_rna_nt": length, "length_status": "pass" if passed else "fail", "localization": body["localization"], "localization_status": "supplied_premise", "diagnostics": [] if passed else [{"code": "expression_rna_length_requirement", "path": admission["objective_path"], "message": "RNA exceeds source bound."}]}
    return {"schema_version": REPORT_V02, "profile": api.REQUEST_PROFILE, "implementation": CHECKER_V02, "resource_profile": api.RESOURCE_PROFILE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest({"request": request, "candidate": actual}), "status": "checked_expression_material" if passed else "not_accepted", "claim_scope": api.CLAIM, "premise": api.PREMISE,
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
    return {"schema_version": api.RESULT_SCHEMA, "implementation": SERVICE_V02, "resource_profile": api.RESOURCE_PROFILE, "validation_scope": api.VALIDATION_SCOPE,
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

    def assert_literal_dispositions(self, checked, *, passed):
        """Independent table equality, including every dependency field."""
        rows = checked.report["obligations"]
        admission = checked.report["source_admission"]
        source = {"source": digest(admission)}
        joined = {**source, "structure": digest(checked.report["structure"]),
                  "contract": self.request["expression_contract"]["identity"]}
        expected = []
        declarations = self.request["document"]["program"]["declarations"]
        objective_index = next(index for index, row in enumerate(declarations) if row["id"] == "encode")
        for name, success, failure, stage, path, dependency in FIXED_DISPOSITIONS:
            if name == "requirement_satisfaction:encode":
                path = f"/document/program/declarations/{objective_index}"
            expected.append({"obligation": name, "path": path, "status": success if passed else failure,
                "stage": stage, "evidence": deepcopy(source if dependency == "source" else joined)})
        definitions = self.request["document"]["program"]["semantics"]["definitions"]
        for name, status, stage in DEFINITION_DISPOSITIONS:
            index, value = next((index, value) for index, value in enumerate(definitions) if value["id"] == name)
            expected.append({"obligation": "semantic_definition:" + name,
                "path": f"/document/program/semantics/definitions/{index}", "status": status, "stage": stage,
                "evidence": {**source, "definition": pin(value), "body": value,
                    "contract": self.request["expression_contract"]["identity"]}})
        self.assertEqual(rows, sorted(expected, key=lambda row: row["obligation"]))
        self.assertEqual(len(rows), 19)
        counts = {status: sum(row["status"] == status for row in rows)
                  for status in ("not_applicable", "discharged", "conditional", "unresolved")}
        self.assertEqual(counts, {"not_applicable": 3, "discharged": 4 if passed else 3,
                                 "conditional": 12 if passed else 6, "unresolved": 0 if passed else 7})
        self.assertEqual(len(admission["source_assessment"]["unresolved_obligations"]), 18)
        self.assertNotIn("expression_material_correspondence", admission["source_assessment"]["unresolved_obligations"])
        self.assertTrue(set(PHANTOM_RUNTIME_IDS).isdisjoint(row["obligation"] for row in rows))

    def test_m1_literal_success_and_failed_conjunction_tables_and_exact_rna(self):
        self.assertEqual((api.REPORT_SCHEMA, api.IMPLEMENTATION), (REPORT_V02, SERVICE_V02))
        self.assertEqual((api.REQUEST_SCHEMA, api.CANDIDATE_SCHEMA, api.RESOURCE_PROFILE, api.VALIDATION_SCOPE, api.SOURCE_PROFILE),
            ("biocompiler.policy_expression_material_request.v0.1", "biocompiler.policy_expression_material_candidate.v0.1",
             "biocompiler.policy_expression_material_resources.v0.1", "policy-single-expression-mrna-v0.1", "biocompiler.policy_expression_source.v0.1"))
        for ceiling, passed in ((1000, True), (17, True), (16, False)):
            with self.subTest(ceiling=ceiling):
                next(row for row in self.request["document"]["program"]["declarations"] if row["id"] == "maximum_rna_nt")["value"] = ceiling
                with self.peer():
                    checked = self.client().check(self.request, self.candidate)
                self.assert_literal_dispositions(checked, passed=passed)
                self.assertEqual(checked.report["schema_version"], REPORT_V02)
                self.assertEqual(checked.report["implementation"], CHECKER_V02)
                self.assertEqual(checked.report["requirements"][0]["actual_rna_nt"], 17)
                self.assertEqual(checked.report["requirements"][0]["status"], "pass" if passed else "fail")
                self.assertEqual(checked.report["all_original_obligations_dispositioned"], passed)
                self.assertEqual(checked.report["empirical"], "unassessed")
                self.assertEqual(checked.report["human_use"], "unassessed")
                if passed:
                    with self.peer():
                        exported = self.client().export(self.request, self.candidate)
                    self.assertEqual(exported.artifact["fasta"], EXACT_FASTA)
                    self.assertEqual(exported.candidate, self.candidate)
                else:
                    self.assertEqual(checked.report["requirements"][0]["diagnostics"][0]["code"], "expression_rna_length_requirement")
                    with self.peer(), self.assertRaises(CoreProtocolError):
                        self.client().export(self.request, self.candidate)

    def test_m1_material_failure_keeps_failed_child_dependencies_and_static_absences(self):
        self.candidate["construction"]["inventory"]["molecules"][0]["sequence"] = "CCAUGGAAUAAGGAAAA"
        def failed_material(value):
            checked = value["report"]
            checked["structure"]["content_reconstruction"].update(outcome="fail", reconstructed_fingerprint=None,
                diagnostics=[{"code": "fixture_content_mismatch", "path": "/candidate", "message": "Independent negative transport fixture."}])
            checked["structure"].update(content_outcome="fail", outcome="fail",
                diagnostics=[{"code": "fixture_content_mismatch", "path": "/candidate", "message": "Independent negative transport fixture."}])
            checked["requirements"][0]["status"] = "fail"
            by_id = {row["obligation"]: row for row in checked["obligations"]}
            for name, _, failure, _, _, _ in FIXED_DISPOSITIONS:
                by_id[name]["status"] = failure
            checked.update(status="not_accepted", all_original_obligations_dispositioned=False)
            rehash_result(value, rebind_dependencies=True)
        with self.peer(mutate=failed_material):
            checked = self.client().check(self.request, self.candidate)
        self.assert_literal_dispositions(checked, passed=False)
        self.assertEqual(checked.report["requirements"][0]["length_status"], "pass")
        self.assertEqual(checked.status, "not_accepted")
        self.assertIsNone(checked.artifact)
        with self.peer(mutate=failed_material), self.assertRaises(CoreProtocolError):
            self.client().export(self.request, self.candidate)

    def test_m1_paths_follow_original_occurrences_and_normative_bodies_survive_reordering(self):
        program = self.request["document"]["program"]
        program["semantics"]["definitions"].reverse()
        program["declarations"] = program["declarations"][-1:] + program["declarations"][:-1]
        with self.peer():
            checked = self.client().check(self.request, self.candidate)
        self.assert_literal_dispositions(checked, passed=True)
        self.assertEqual(checked.report["source_admission"]["objective_path"], "/document/program/declarations/0")
        self.assertEqual(checked.report["empirical"], "unassessed")

    def test_m1_coherent_mandatory_census_deletions_and_duplicates_reject(self):
        mandatory = sorted([row[0] for row in FIXED_DISPOSITIONS if row[0] != "expression_material_correspondence"]
                           + ["semantic_definition:" + row[0] for row in DEFINITION_DISPOSITIONS])
        self.assertEqual(len(mandatory), 18)
        for maximum in (1000, 16):
            next(row for row in self.request["document"]["program"]["declarations"] if row["id"] == "maximum_rna_nt")["value"] = maximum
            for name in mandatory:
                for attack in ("delete", "duplicate"):
                    def mutate(value, name=name, attack=attack):
                        checked = value["report"]
                        admission = checked["source_admission"]
                        for ids in (admission["source_assessment"]["unresolved_obligations"], admission["unresolved_obligations"]):
                            ids.remove(name) if attack == "delete" else ids.append(name)
                            ids.sort()
                        rows = checked["obligations"]
                        row = next(row for row in rows if row["obligation"] == name)
                        rows.remove(row) if attack == "delete" else rows.append(deepcopy(row))
                        rows.sort(key=lambda row: row["obligation"])
                        rehash_result(value, rebind_dependencies=True)
                    with self.subTest(maximum=maximum, name=name, attack=attack), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                        self.client().check(self.request, self.candidate)

    def test_m1_failed_conjunction_cannot_reuse_successful_dispositions_or_source_evidence(self):
        successful = {row["obligation"]: row for row in report(self.request, self.candidate)["obligations"]}
        next(row for row in self.request["document"]["program"]["declarations"] if row["id"] == "maximum_rna_nt")["value"] = 16
        for name, success, failure, _, _, _ in FIXED_DISPOSITIONS:
            if failure != "unresolved":
                continue
            for field, replacement in (("status", success), ("evidence", successful[name]["evidence"])):
                def mutate(value, name=name, field=field, replacement=replacement):
                    next(row for row in value["report"]["obligations"] if row["obligation"] == name)[field] = deepcopy(replacement)
                    rehash_result(value)
                with self.subTest(name=name, field=field), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                    self.client().check(self.request, self.candidate)

    def test_m1_phantom_or_unknown_obligations_cannot_be_blessed_by_a_coherent_peer(self):
        for name in (*PHANTOM_RUNTIME_IDS, "unsupported.extra"):
            for status in ("not_applicable", "conditional", "discharged"):
                def mutate(value, name=name, status=status):
                    checked = value["report"]
                    admission = checked["source_admission"]
                    for ids in (admission["source_assessment"]["unresolved_obligations"], admission["unresolved_obligations"]):
                        ids.append(name)
                        ids.sort()
                    checked["obligations"].append({"obligation": name, "path": "/document", "status": status,
                        "stage": "closed_static_source_admission" if status == "not_applicable" else "supplied_expression_localization_and_recipient_premises",
                        "evidence": {"source": digest(admission)}})
                    checked["obligations"].sort(key=lambda row: row["obligation"])
                    rehash_result(value, rebind_dependencies=True)
                with self.subTest(name=name, status=status), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                    self.client().check(self.request, self.candidate)

    def test_m1_every_status_stage_path_and_dependency_is_authoritative(self):
        control = report(self.request, self.candidate)
        for original_row in control["obligations"]:
            name = original_row["obligation"]
            mutations = [("status", "conditional" if original_row["status"] == "discharged" else "discharged"),
                ("stage", "invented_reason"), ("path", "/document/assurance" if name == "safety_and_progress_satisfaction" else "/foreign")]
            for key in original_row["evidence"]:
                altered = deepcopy(original_row["evidence"])
                del altered[key]
                mutations.append(("evidence", altered))
                altered = deepcopy(original_row["evidence"])
                if key in ("source", "structure"):
                    altered[key] = "0" * 64
                elif key == "body":
                    altered[key]["meaning"] += " Changed premise."
                elif key == "definition":
                    altered[key]["digest"] = "0" * 64
                else:
                    altered[key]["content_fingerprint"] = "0" * 64
                mutations.append(("evidence", altered))
            for field, replacement in mutations:
                def mutate(value, name=name, field=field, replacement=replacement):
                    next(row for row in value["report"]["obligations"] if row["obligation"] == name)[field] = deepcopy(replacement)
                    rehash_result(value)  # Do not repair the deliberately wrong dependency.
                with self.subTest(name=name, field=field, replacement=replacement), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                    self.client().check(self.request, self.candidate)

    @staticmethod
    def add_unresolved_extra(value):
        """Transport consistency fixture; genuine semantic origin is tested natively."""
        checked = value["report"]
        admission = checked["source_admission"]
        name = "derived_quantity_operation_semantics"
        for ids in (admission["source_assessment"]["unresolved_obligations"], admission["unresolved_obligations"]):
            ids.append(name)
            ids.sort()
        checked["obligations"].append({"obligation": name, "path": "/document", "status": "unresolved",
            "stage": "unimplemented_obligation", "evidence": None})
        checked["obligations"].sort(key=lambda row: row["obligation"])
        checked.update(status="not_accepted", all_original_obligations_dispositioned=False)
        rehash_result(value, rebind_dependencies=True)

    def test_m1_unknown_extra_is_retained_only_in_a_negative_diagnostic_report(self):
        with self.peer(mutate=self.add_unresolved_extra):
            checked = self.client().check(self.request, self.candidate)
        self.assertEqual(checked.status, "not_accepted")
        self.assertEqual(checked.report["requirements"][0]["status"], "pass")
        self.assertEqual(len(checked.report["obligations"]), 20)
        self.assertEqual(next(row for row in checked.report["obligations"] if row["obligation"] == "derived_quantity_operation_semantics"),
            {"obligation": "derived_quantity_operation_semantics", "path": "/document", "status": "unresolved", "stage": "unimplemented_obligation", "evidence": None})
        self.assertFalse(checked.report["all_original_obligations_dispositioned"])
        self.assertIsNone(checked.artifact)
        for attack in ("drop", "promote", "claim_closed"):
            def mutate(value, attack=attack):
                self.add_unresolved_extra(value)
                checked = value["report"]
                row = next(row for row in checked["obligations"] if row["obligation"] == "derived_quantity_operation_semantics")
                if attack == "drop":
                    checked["obligations"].remove(row)
                    checked["source_admission"]["unresolved_obligations"].remove(row["obligation"])
                elif attack == "promote":
                    row.update(status="conditional", stage="supplied_expression_localization_and_recipient_premises")
                else:
                    checked.update(status="checked_expression_material", all_original_obligations_dispositioned=True)
                rehash_result(value, rebind_dependencies=True)
            with self.subTest(attack=attack), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)
        with self.peer(mutate=self.add_unresolved_extra), self.assertRaises(CoreProtocolError):
            self.client().export(self.request, self.candidate)

    def test_m1_reserved_profile_obligation_cannot_originate_in_generic_child(self):
        for maximum in (1000, 16):
            next(row for row in self.request["document"]["program"]["declarations"] if row["id"] == "maximum_rna_nt")["value"] = maximum
            def mutate(value):
                ids = value["report"]["source_admission"]["source_assessment"]["unresolved_obligations"]
                ids.append("expression_material_correspondence")
                ids.sort()
                # The final ledger still contains exactly one profile row.
                rehash_result(value, rebind_dependencies=True)
            with self.subTest(maximum=maximum), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)

    def test_m1_original_catalog_and_definition_occurrences_cannot_be_collapsed(self):
        for attack in ("no_entry", "two_entries", "different_id", "different_version", "different_body", "duplicate_definition", "conflicting_definition"):
            self.request = original()
            entries = self.request["document"]["implementations"]["implementations"]
            definitions = self.request["document"]["program"]["semantics"]["definitions"]
            if attack == "no_entry":
                entries.clear()
            elif attack == "two_entries":
                entries.append({**deepcopy(entries[0]), "id": "another.entry"})
            elif attack == "different_id":
                entries[0]["id"] = "another.entry"
            elif attack == "different_version":
                entries[0]["version"] = "2"
            elif attack == "different_body":
                entries[0]["payload_formats"] = ["RNA", "DNA"]
            else:
                duplicate = deepcopy(definitions[-1])
                if attack == "conflicting_definition":
                    duplicate.update(version="2", meaning="Different complete original body.")
                definitions.append(duplicate)
            with self.subTest(attack=attack), self.peer(), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)

    def test_m1_supplied_unknown_descriptor_stays_conditional_with_complete_body(self):
        definitions = self.request["document"]["program"]["semantics"]["definitions"]
        old = next(row for row in definitions if row["id"] == "artificial.environment")
        old_pin = pin(old)
        old["meaning"] = "Supplied environmental applicability remains unknown; no executable interpretation."
        new_pin = pin(old)
        def repin(value):
            if isinstance(value, dict):
                if value == old_pin:
                    value.update(new_pin)
                else:
                    for item in value.values():
                        repin(item)
            elif isinstance(value, list):
                for item in value:
                    repin(item)
        repin(self.request)
        self.request["expression_contract"]["identity"]["content_fingerprint"] = digest(self.request["expression_contract"]["body"])
        with self.peer():
            checked = self.client().check(self.request, self.candidate)
        row = next(row for row in checked.report["obligations"] if row["obligation"] == "semantic_definition:artificial.environment")
        self.assertEqual((row["status"], row["stage"]), ("conditional", "resolved_original_context_or_component_premise"))
        self.assertEqual(row["evidence"]["definition"], new_pin)
        self.assertEqual(row["evidence"]["body"], old)
        self.assertEqual(row["evidence"]["contract"], self.request["expression_contract"]["identity"])

    def test_m1_additional_reachable_descriptive_premise_expands_the_exact_census(self):
        supplied = definition("artificial.additional_environment", "environment", "Additional supplied environment premise; applicability is unknown.")
        self.request["document"]["program"]["semantics"]["definitions"].append(supplied)
        self.request["document"]["deployment"]["environment"].append(pin(supplied))
        self.request["expression_contract"]["body"]["deployment"] = deepcopy(self.request["document"]["deployment"])
        self.request["expression_contract"]["identity"]["content_fingerprint"] = digest(self.request["expression_contract"]["body"])
        with self.peer():
            checked = self.client().check(self.request, self.candidate)
        self.assertEqual(checked.status, "checked_expression_material")
        self.assertEqual(len(checked.report["source_admission"]["source_assessment"]["unresolved_obligations"]), 19)
        self.assertEqual(len(checked.report["obligations"]), 20)
        row = next(row for row in checked.report["obligations"] if row["obligation"] == "semantic_definition:artificial.additional_environment")
        self.assertEqual(row, {"obligation": "semantic_definition:artificial.additional_environment",
            "path": "/document/program/semantics/definitions/9", "status": "conditional",
            "stage": "resolved_original_context_or_component_premise",
            "evidence": {"source": digest(checked.report["source_admission"]), "definition": pin(supplied),
                "body": supplied, "contract": self.request["expression_contract"]["identity"]}})

    def test_m1_old_or_mixed_assessment_checker_service_versions_reject(self):
        for mask in range(1, 8):
            def mutate(value, mask=mask):
                if mask & 1:
                    value["report"]["schema_version"] = "biocompiler.policy_expression_material_assessment.v0.1"
                if mask & 2:
                    value["report"]["implementation"] = "biocompiler.ocaml.policy_expression_material_check.v0.1"
                if mask & 4:
                    value["implementation"] = "biocompiler.ocaml.policy_expression_material.v0.1"
                rehash_result(value)
            with self.subTest(mask=mask), self.peer(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client().check(self.request, self.candidate)
        for role, profile in (("verify", "policy_expression_material"),
                              ("core", "policy_expression_material"),
                              ("core", "policy_expression_material_producer")):
            self.calls.clear()
            def old_capability(value, profile=profile):
                value["profiles"][profile]["implementation"] = "biocompiler.ocaml.policy_expression_material.v0.1"
            with self.subTest(role=role, profile=profile):
                with self.peer(role, caps=old_capability), self.assertRaises(CoreProtocolError):
                    if role == "core":
                        self.client(role).compile(self.request)
                    else:
                        self.client(role).check(self.request, self.candidate)
                self.assertEqual([call["operation"] for call in self.calls], ["capabilities"])

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
