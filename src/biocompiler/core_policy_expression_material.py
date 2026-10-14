"""Strict transport for conditional, static expression-to-original-mRNA checking.

This module checks retained identities and evidence consistency. Only the fresh
native checker can establish the supported conditional correspondence; Python
contains no expression lowerer, translation engine, or biological fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Callable, cast

from biocompiler import core_policy as source
from biocompiler.core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json
from biocompiler.core_policy_material import PolicyMaterialResult, _publication
from biocompiler.core_policy_operational import _fingerprint, _pin, _same

REQUEST_SCHEMA = "biocompiler.policy_expression_material_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_single_expression_mrna.v0.1"
SOURCE_PROFILE = "biocompiler.policy_expression_source.v0.1"
CONTRACT_SCHEMA = "biocompiler.policy_expression_contract.v0.1"
CANDIDATE_SCHEMA = "biocompiler.policy_expression_material_candidate.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_expression_material.v1"
REPORT_SCHEMA = "biocompiler.policy_expression_material_assessment.v0.2"
IMPLEMENTATION = "biocompiler.ocaml.policy_expression_material.v0.2"
RESOURCE_PROFILE = "biocompiler.policy_expression_material_resources.v0.1"
VALIDATION_SCOPE = "policy-single-expression-mrna-v0.1"
EXPORT_SCHEMA = "biocompiler.policy_expression_mrna_export.v0.1"
MANIFEST_SCHEMA = "biocompiler.policy_expression_mrna_manifest.v0.1"
MAX_WORK = 100_000_000
MAX_RESULT_BYTES = 8_323_072
MAX_RESULT_NODES = 249_968
ACCEPTED_STATUS = "checked_expression_material"
CLAIM = "conditional_encoding_and_localization"
PREMISE = "supplied_expression_localization_recipient_and_nominal_translation_contracts"
# Complete immutable native normative bodies, not caller-defined names alone.
_NORMATIVE_DEFINITION_DIGESTS = frozenset({
    "418dbfb378593d54f9e37135d0caa6645de0c006aa3dc727b30da21d68b1d642",
    "dd335bd49a8159b03e4f3da39f78859b6bcf2adc5bf990b75a99719493b6f5ce",
    "624602f1b346a1c996c48478b76cc71b96fabdfc318da3f6687c1d20eddc313e",
})
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-expression-material", "replay-policy-expression-material", "export-policy-expression-material"],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "on_fresh_export_only", "empirical": "unassessed",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {"operations": ["compile-policy-expression-material"],
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE}
_RESULT_FIELDS = {"schema_version", "implementation", "resource_profile", "validation_scope", "request_fingerprint",
    "candidate_fingerprint", "invocation_fingerprint", "report_fingerprint", "candidate", "report", "artifact", "usage"}
_REPORT_FIELDS = {"schema_version", "profile", "implementation", "resource_profile", "request_fingerprint", "candidate_fingerprint",
    "invocation_fingerprint", "status", "claim_scope", "premise", "source_admission", "structure", "requirements", "obligations",
    "all_original_obligations_dispositioned", "budgets", "empirical", "human_use", "artifact", "export", "usage"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _record(raw: JsonValue, label: str) -> dict[str, JsonValue]:
    return source._record(raw, label)


def _rows(raw: JsonValue, label: str) -> list[JsonValue]:
    _require(type(raw) is list, label + " must be an array")
    return cast(list[JsonValue], raw)


def _integer(raw: JsonValue, label: str, maximum: int, *, minimum: int = 0) -> int:
    _require(type(raw) is int and minimum <= raw <= maximum, label + " exceeds its exact integer bounds")
    return cast(int, raw)


def _bounded_text(raw: JsonValue, label: str, maximum: int) -> str:
    value = source._text(raw, label)
    _require(len(value.encode("utf-8")) <= maximum, label + " exceeds its UTF-8 byte bound")
    return value


def _identity(raw: JsonValue, kind: str) -> dict[str, JsonValue]:
    value = _object(raw, {"schema_version", "kind", "id", "version", "content_fingerprint"}, "Original identity")
    _require(value["schema_version"] == "biocompiler.component_identity.v0.1" and value["kind"] == kind,
             "Original identity changed its kind or schema")
    source._text(value["id"], "Identity id")
    source._text(value["version"], "Identity version")
    source._hash(value["content_fingerprint"])
    return value


def _original(raw: JsonValue) -> dict[str, JsonValue]:
    """Closed transport representation; this does not admit source semantics."""
    _publication(raw, 4_000_000, 100_000)
    request = _object(raw, {"schema_version", "profile", "document", "selection", "expression_contract", "structure_authority", "budgets", "project_context"}, "Expression request")
    _require(request["schema_version"] == REQUEST_SCHEMA and request["profile"] == REQUEST_PROFILE, "Unsupported expression request profile")
    context = _object(request["project_context"], {"project_id", "title", "sources", "assumptions"}, "Original project context")
    for key in ("project_id", "title"):
        _bounded_text(context[key], "Project " + key, 128 if key == "project_id" else 4096)
    records = _rows(context["sources"], "Project sources")
    _require(1 <= len(records) <= 128, "Project source census exceeds its bounds")
    ids: set[str] = set()
    for raw_source in records:
        row = _object(raw_source, {"id", "locator", "version", "sha256", "role", "reuse_terms"}, "Project source")
        for key in ("id", "locator", "version", "role", "reuse_terms"):
            _bounded_text(row[key], "Source " + key, 4096)
        source._hash(row["sha256"])
        name = cast(str, row["id"])
        _require(name not in ids, "Duplicate original project source id")
        ids.add(name)
    assumptions = _rows(context["assumptions"], "Project assumptions")
    _require(len(assumptions) <= 128, "Project assumption inventory exceeds its bound")
    for assumption in assumptions:
        _bounded_text(assumption, "Project assumption", 4096)
    document = _record(request["document"], "Original expression source")
    _require(document.get("$type") == "BuildRequest" and document.get("profile") == SOURCE_PROFILE,
             "Expression checking requires the explicit static source profile")
    selection = _object(request["selection"], {"objective", "recipient", "implementation", "member", "cds"}, "Expression selection")
    for key in ("objective", "recipient", "member", "cds"):
        source._text(selection[key], "Selected " + key)
    _identity(selection["implementation"], "registry")
    contract = _object(request["expression_contract"], {"identity", "body"}, "Supplied expression contract")
    identity = _identity(contract["identity"], "model")
    body = _object(contract["body"], {"schema_version", "operation", "realization", "product", "recipient", "deployment", "localization", "material", "translation", "dependencies", "evidence", "claim_scope"}, "Complete expression contract")
    _require(body["schema_version"] == CONTRACT_SCHEMA and body["claim_scope"] == CLAIM, "Expression contract changed its conditional scope")
    _pin(identity["content_fingerprint"], body, "Original complete expression contract")
    _identity(body["product"], "reference")
    material = _object(body["material"], {"structure_sha256", "member", "cds"}, "Contract material binding")
    _pin(material["structure_sha256"], request["structure_authority"], "Original structure authority")
    _require(material["member"] == selection["member"] and material["cds"] == selection["cds"], "Selected material differs from the original contract")
    translation = _object(body["translation"], {"interpretation", "terminal_stop_codons", "model"}, "Nominal translation premise")
    _require(translation["interpretation"] == "nominal_canonical_parent_bases", "Unrecognized translation interpretation")
    _integer(translation["terminal_stop_codons"], "Terminal stop count", 2, minimum=1)
    for key in ("dependencies", "evidence"):
        _require(len(_rows(body[key], "Original " + key)) <= 32, "Expression reference inventory exceeds its bound")
    _require(len(_rows(body["dependencies"], "Dependencies")) + len(_rows(body["evidence"], "Evidence")) <= 32, "Combined original reference inventory exceeds its bound")
    budgets = _object(request["budgets"], {"profile", "max_work", "max_report_bytes", "max_report_nodes"}, "Original expression budgets")
    _require(budgets["profile"] == RESOURCE_PROFILE, "Expression resource profile changed")
    for key, limit in (("max_work", MAX_WORK), ("max_report_bytes", MAX_RESULT_BYTES), ("max_report_nodes", MAX_RESULT_NODES)):
        _integer(budgets[key], key, limit, minimum=1)
    return request


def _source(response: CoreResponse, request: dict[str, JsonValue], report: dict[str, JsonValue]) -> dict[str, JsonValue]:
    admission = _object(report["source_admission"], {"schema_version", "status", "request_fingerprint", "source_artifact_digest",
        "source_semantic_digest", "objective", "objective_path", "product", "maximum_rna_nt", "unresolved_obligations", "source_assessment",
        "temporal_execution", "expression_claim", "empirical_realization", "human_use", "export"}, "Static source admission")
    expected: dict[str, JsonValue] = {"schema_version": "biocompiler.policy_expression_source_admission.v0.1",
        "status": "admitted_static_expression_source", "temporal_execution": "not_requested_by_supported_objective",
        "expression_claim": "withheld", "empirical_realization": "unassessed", "human_use": "unassessed", "export": "withheld"}
    _require(all(admission[key] == value for key, value in expected.items()), "Source admission changed its limited scope")
    document = _record(request["document"], "Original source")
    program = _record(document.get("program"), "Original program")
    selection = _record(request["selection"], "Original selection")
    body = _record(_record(request["expression_contract"], "Contract")["body"], "Contract body")
    _pin(admission["request_fingerprint"], request, "Source request")
    _pin(admission["source_artifact_digest"], document, "Complete source")
    _pin(admission["source_semantic_digest"], source._semantic(document), "Semantic source")
    assessment = admission["source_assessment"]
    wrapper: JsonValue = {"schema_version": source.RESULT_SCHEMA, "implementation": source.IMPLEMENTATION,
        "resource_profile": source.RESOURCE_PROFILE, "validation_scope": source.VALIDATION_SCOPE,
        "supplied_document_fingerprint": _fingerprint(document), "assessment_fingerprint": _fingerprint(assessment), "assessment": assessment}
    checked = source._result(replace(response, result=wrapper), document)
    _require(checked.status == "valid", "Expression admission lacks a valid fresh source assessment")
    declarations = [_record(row, "Declaration") for row in _rows(program.get("declarations"), "Declarations")]
    objectives = [(index, row) for index, row in enumerate(declarations) if row.get("$type") == "Requirement"]
    _require(len(objectives) == 1, "Static source objective census changed")
    index, objective = objectives[0]
    _require(admission["objective"] == selection["objective"] == objective.get("id")
        and admission["objective_path"] == f"/document/program/declarations/{index}", "Source objective identity or occurrence changed")
    maximum = [row.get("value") for row in declarations if row.get("$type") == "Parameter" and row.get("id") == "maximum_rna_nt"]
    _require(len(maximum) == 1 and _same(admission["maximum_rna_nt"], maximum[0]), "Source RNA bound changed")
    _integer(admission["maximum_rna_nt"], "Source RNA ceiling", 1_000_000, minimum=1)
    _require(_same(admission["product"], body["product"]), "Source product differs from original contract")
    obligations = _rows(checked.assessment["unresolved_obligations"], "Source obligations")
    # The child inventory cannot serve as its own authority. Reconstruct the
    # mandatory IDs from complete originals while retaining unsupported extras
    # for negative diagnostics; their semantic origin remains native authority.
    definitions = _rows(_record(program.get("semantics"), "Original semantics").get("definitions"), "Original definitions")
    definition_ids = [source._text(_record(value, "Original definition").get("id"), "Original definition id") for value in definitions]
    _require(len(definition_ids) == len(set(definition_ids)), "Duplicate original semantic definition id")
    implementations = _rows(_record(document.get("implementations"), "Original catalog").get("implementations"), "Original implementations")
    _require(len(implementations) == 1, "Static source requires exactly one original implementation")
    implementation = _record(implementations[0], "Original implementation")
    selected = _identity(selection["implementation"], "registry")
    _require(implementation.get("id") == selected["id"] and implementation.get("version") == selected["version"],
             "Selected implementation differs from the original catalog entry")
    _pin(selected["content_fingerprint"], implementation, "Complete original implementation")
    mandatory = {
        "policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "safety_and_progress_satisfaction",
        "realizability_and_target_suitability", "chassis_capability_and_delivery_suitability",
        "implementation_catalog_applicability", "requested_assurance_not_established",
        "implementation_applicability:" + cast(str, selected["id"]),
        "requirement_satisfaction:" + cast(str, admission["objective"]),
        *("semantic_definition:" + name for name in definition_ids),
    }
    child_ids = [source._text(value, "Source obligation id") for value in obligations]
    _require(len(child_ids) == len(set(child_ids)) and mandatory.issubset(child_ids),
             "Source obligation census omitted or duplicated an original obligation")
    _require("expression_material_correspondence" not in child_ids,
             "Generic source cannot supply the reserved expression correspondence obligation")
    expected_obligations = cast(JsonValue, sorted([*child_ids, "expression_material_correspondence"]))
    _require(_same(admission["unresolved_obligations"], expected_obligations), "Admission omitted or reordered an original obligation")
    return admission


def _structure(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> bool:
    leaf = _object(report["structure"], {"schema_version", "profile", "implementation_version", "claim_scope", "translation_interpretation",
        "terminal_stop_codons", "translation_model", "physical_translation", "authority_fingerprint", "candidate_fingerprint", "content_reconstruction",
        "content_outcome", "structural_outcome", "outcome", "checked_clauses", "PM-08_scope", "unassessed_clauses", "members", "diagnostics",
        "context_status", "implementation", "policy", "material_binding", "export"}, "Nominal expression structure")
    constants: dict[str, JsonValue] = {"schema_version": "biocompiler.policy_expression_structure_assessment.v0.1",
        "profile": "biocompiler.policy_expression_nominal_structure.v0.1", "implementation_version": "biocompiler.ocaml.policy_expression_structure_check.v0.1",
        "claim_scope": "exact_supplied_mrna_structure_under_nominal_translation_premise", "translation_interpretation": "nominal_canonical_parent_bases",
        "physical_translation": "unassessed", "context_status": "unassessed", "implementation": "unassessed", "policy": "unassessed", "material_binding": "unassessed", "export": "withheld",
        "checked_clauses": ["PM-02", "PM-03", "PM-04", "PM-05", "PM-06", "PM-07", "PM-09"],
        "PM-08_scope": "supplied_construction_region_chemistry_product_declaration_provenance_only",
        "unassessed_clauses": ["PM-01", "PM-08_external_component_binding", "PM-10", "PM-11", "PM-12"]}
    _require(all(_same(leaf[key], value) for key, value in constants.items()), "Structure upgraded or omitted its conditional scope")
    authority = _record(request["structure_authority"], "Original structure")
    body = _record(_record(request["expression_contract"], "Contract")["body"], "Contract body")
    translation = _record(body["translation"], "Original nominal translation")
    _require(_same(leaf["terminal_stop_codons"], translation["terminal_stop_codons"]) and _same(leaf["translation_model"], translation["model"]), "Original nominal translation premise changed")
    _pin(leaf["authority_fingerprint"], authority, "Original structure")
    _pin(leaf["candidate_fingerprint"], candidate["construction"], "Complete construction")
    content = _object(leaf["content_reconstruction"], {"schema_version", "implementation_version", "claim_scope", "authority_fingerprint",
        "candidate_fingerprint", "reconstructed_fingerprint", "outcome", "context_status", "payload_completeness", "diagnostics"}, "Independent reconstruction")
    _require(content["schema_version"] == "biocompiler.construction_content_assessment.v0.1"
        and content["implementation_version"] == "biocompiler.ocaml.construction_content_check.v0.1"
        and content["claim_scope"] == "exact_supplied_template_molecular_content"
        and content["context_status"] == "unassessed" and content["payload_completeness"] == "unassessed", "Reconstruction scope changed")
    _pin(content["authority_fingerprint"], {"schema_version": "biocompiler.construction_content_authority.v0.1", "template": authority.get("template"), "member_order": authority.get("member_order")}, "Original reconstruction authority")
    _pin(content["candidate_fingerprint"], candidate["construction"], "Reconstruction candidate")
    outcomes = {"pass", "fail", "unknown", "unsupported"}
    _require(all(type(leaf[key]) is str and leaf[key] in outcomes for key in ("content_outcome", "structural_outcome", "outcome")) and content["outcome"] == leaf["content_outcome"], "Contradictory structural outcomes")
    if content["outcome"] == "pass":
        _pin(content["reconstructed_fingerprint"], candidate["construction"], "Reconstructed original material")
    combined = next((value for value in ("fail", "unsupported", "unknown") if value in (leaf["content_outcome"], leaf["structural_outcome"])), "pass")
    _require(leaf["outcome"] == combined, "Structural conjunction changed")
    for key in ("diagnostics", "members"):
        _rows(leaf[key], "Structure " + key)
    _rows(content["diagnostics"], "Reconstruction diagnostics")
    if combined == "pass":
        construction = _record(candidate["construction"], "Construction")
        inventory = _record(construction.get("inventory"), "Complete inventory")
        molecules = [_record(row, "Molecule") for row in _rows(inventory.get("molecules"), "Molecules")]
        originals = [_record(row, "Original member") for row in _rows(authority.get("members"), "Original members")]
        rows = _rows(leaf["members"], "Structural member evidence")
        _require(len(molecules) == len(originals) == len(rows) == 1 and leaf["diagnostics"] == [] and content["diagnostics"] == [], "Passing structure lacks complete single-member evidence")
        member, original = molecules[0], originals[0]
        row = _object(rows[0], {"member", "molecule_fingerprint", "product_identity", "expected_product", "translated_product"}, "Product correspondence")
        product = _record(original.get("product"), "Original product")
        _require(row["member"] == original.get("id") == member.get("id") and _same(authority.get("member_order"), [member.get("id")]) , "Exact member order changed")
        _pin(row["molecule_fingerprint"], member, "Complete molecule")
        _require(_same(row["product_identity"], product.get("identity")) and _same(row["product_identity"], body["product"])
            and row["expected_product"] == row["translated_product"] == product.get("sequence"), "Exact product correspondence changed")
    return combined == "pass"


def _requirements_and_ledger(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue], admission: dict[str, JsonValue], structure_ok: bool) -> None:
    selection = _record(request["selection"], "Selection")
    contract = _record(request["expression_contract"], "Contract")
    body = _record(contract["body"], "Contract body")
    requirements = _rows(report["requirements"], "Complete source requirements")
    _require(len(requirements) == 1, "Source objective evidence was omitted or duplicated")
    requirement = _object(requirements[0], {"id", "path", "status", "product", "member", "cds", "maximum_rna_nt", "actual_rna_nt", "length_status", "localization", "localization_status", "diagnostics"}, "Source requirement")
    construction = _record(candidate["construction"], "Construction")
    inventory = construction.get("inventory")
    molecules = [] if inventory is None else _rows(_record(inventory, "Inventory").get("molecules"), "Molecules")
    actual_length = len(source._text(_record(molecules[0], "Molecule").get("sequence"), "RNA sequence")) if len(molecules) == 1 else None
    maximum = cast(int, admission["maximum_rna_nt"])
    bound_ok = actual_length is not None and actual_length <= maximum
    objective_ok = structure_ok and bound_ok
    expected: dict[str, JsonValue] = {"id": admission["objective"], "path": admission["objective_path"], "product": body["product"], "member": selection["member"], "cds": selection["cds"],
        "maximum_rna_nt": maximum, "actual_rna_nt": actual_length, "length_status": "pass" if bound_ok else "fail", "status": "pass" if objective_ok else "fail",
        "localization": body["localization"], "localization_status": "supplied_premise"}
    _require(all(_same(requirement[key], value) for key, value in expected.items()), "Source requirement evidence changed original meaning or outcome")
    diagnostics = _rows(requirement["diagnostics"], "Requirement diagnostics")
    _require((diagnostics == []) == bound_ok, "RNA length diagnostic contradicts its result")
    document = _record(request["document"], "Source")
    program = _record(document.get("program"), "Program")
    definitions = _rows(_record(program.get("semantics"), "Semantics").get("definitions"), "Definitions")
    definition_index = {source._text(_record(value, "Definition").get("id"), "Definition id"):
                        (index, _record(value, "Definition")) for index, value in enumerate(definitions)}
    source_pin = _fingerprint(admission)
    pins: JsonValue = {"source": source_pin, "structure": _fingerprint(report["structure"]), "contract": contract["identity"]}
    rows = _rows(report["obligations"], "Complete obligation ledger")
    _require(_same([_record(row, "Obligation").get("obligation") for row in rows], admission["unresolved_obligations"]), "Original obligation census or order changed")
    na = {"policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "safety_and_progress_satisfaction"}
    conditional_paths = {
        "realizability_and_target_suitability": "/document/deployment",
        "chassis_capability_and_delivery_suitability": "/document/deployment",
        "implementation_catalog_applicability": "/document/implementations",
        "requested_assurance_not_established": "/document/assurance",
        "expression_material_correspondence": "/document",
    }
    implementation_id = _record(selection["implementation"], "Implementation")["id"]
    closed = True
    for value in rows:
        row = _object(value, {"obligation", "path", "status", "stage", "evidence"}, "Obligation disposition")
        name = source._text(row["obligation"], "Obligation id")
        status, stage, evidence = "unresolved", "unimplemented_obligation", cast(JsonValue, None)
        path = "/document"
        if name in na:
            status, stage, evidence = "not_applicable", "closed_static_source_admission", {"source": source_pin}
            path = "/document/program"
        elif name == "requirement_satisfaction:" + cast(str, admission["objective"]):
            status, stage, evidence = ("discharged" if objective_ok else "unresolved"), "exact_static_encoding_and_length", pins
            path = cast(str, admission["objective_path"])
        elif name in conditional_paths or name == "implementation_applicability:" + cast(str, implementation_id):
            status = "conditional" if objective_ok else "unresolved"
            stage = "supplied_expression_localization_and_recipient_premises" if name in conditional_paths else "complete_supplied_implementation_contract"
            path = conditional_paths.get(name, "/document/implementations/implementations/0")
            evidence = pins
        elif name.startswith("semantic_definition:") and name[len("semantic_definition:"):] in definition_index:
            index, definition = definition_index[name[len("semantic_definition:"):]]
            path = f"/document/program/semantics/definitions/{index}"
            interpreted = _fingerprint(definition) in _NORMATIVE_DEFINITION_DIGESTS
            status = "discharged" if interpreted else "conditional"
            stage = "closed_normative_static_interpretation" if interpreted else "resolved_original_context_or_component_premise"
            evidence = {"source": source_pin, "definition": {"$type": "DefinitionRef", "id": definition["id"],
                "version": definition["version"], "digest": _fingerprint(source._semantic(definition))},
                "body": definition, "contract": contract["identity"]}
        _require(row["path"] == path and row["status"] == status and row["stage"] == stage and _same(row["evidence"], evidence), "Obligation changed its exact path, disposition or evidence")
        closed = closed and status != "unresolved"
    _require(type(report["all_original_obligations_dispositioned"]) is bool and report["all_original_obligations_dispositioned"] == closed, "Obligation closure contradicts complete ledger")
    _require(report["status"] == ("checked_expression_material" if objective_ok and closed else "not_accepted"), "Expression status contradicts its complete evidence")


def _artifact(raw: JsonValue, *, operation: str, request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    if operation != "export-policy-expression-material":
        _require(raw is None, "Only a fresh export may publish expression material")
        return
    _require(report["status"] == "checked_expression_material", "Unaccepted expression cannot export")
    artifact = _object(raw, {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Exact expression export")
    construction = _record(candidate["construction"], "Construction")
    molecules = _rows(_record(construction.get("inventory"), "Inventory").get("molecules"), "Molecules")
    fasta, members = "", []
    for index, value in enumerate(molecules, 1):
        molecule = _record(value, "Molecule")
        sequence = source._text(molecule.get("sequence"), "RNA sequence")
        name = f"rna_{index:04d}"
        fasta += f">{name} alphabet=RNA\n" + "".join(sequence[offset:offset + 80] + "\n" for offset in range(0, len(sequence), 80))
        members.append({"fasta_id": name, "member_id": molecule.get("id"), "molecule": molecule, "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest()})
    fasta_hash = hashlib.sha256(fasta.encode()).hexdigest()
    manifest: JsonValue = {"schema_version": MANIFEST_SCHEMA, "profile": REQUEST_PROFILE, "claim_scope": CLAIM, "premise": PREMISE,
        "request": request, "candidate": candidate, "assessment": report, "bindings": {"request_fingerprint": _fingerprint(request),
            "candidate_fingerprint": _fingerprint(candidate), "invocation_fingerprint": _fingerprint({"request": request, "candidate": candidate}), "assessment_fingerprint": _fingerprint(report)},
        "members": cast(JsonValue, members), "fasta_sha256": fasta_hash, "empirical": "unassessed", "human_use": "unassessed", "original_authority": "retain_original_inputs_separately"}
    _require(artifact["schema_version"] == EXPORT_SCHEMA and artifact["fasta"] == fasta and artifact["fasta_sha256"] == fasta_hash
        and _same(artifact["manifest"], manifest), "Export changed exact FASTA, originals, or conditional manifest")
    _pin(artifact["manifest_sha256"], manifest, "Complete manifest")


@dataclass(frozen=True)
class PolicyExpressionMaterialResult(PolicyMaterialResult):
    """Immutable fresh native evidence; biological function remains unassessed."""


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyExpressionMaterialResult:
    result = _object(response.result, _RESULT_FIELDS, "Expression result")
    _require(response.status == "ok" and response.operation in cast(list[str], PROFILE["operations"]) + ["compile-policy-expression-material"], "Unexpected expression response operation or status")
    for key, expected in (("schema_version", RESULT_SCHEMA), ("implementation", IMPLEMENTATION), ("resource_profile", RESOURCE_PROFILE), ("validation_scope", VALIDATION_SCOPE)):
        _require(result[key] == expected, "Expression result changed its negotiated profile")
    request = _original(payload["request"])
    candidate = _object(result["candidate"], {"schema_version", "construction"}, "Complete expression candidate")
    _require(candidate["schema_version"] == CANDIDATE_SCHEMA and ("candidate" not in payload or _same(candidate, payload["candidate"])), "Checking changed the supplied expression candidate")
    report = _object(result["report"], _REPORT_FIELDS, "Complete expression evidence")
    fixed: dict[str, JsonValue] = {"schema_version": REPORT_SCHEMA, "profile": REQUEST_PROFILE, "implementation": "biocompiler.ocaml.policy_expression_material_check.v0.2",
        "resource_profile": RESOURCE_PROFILE, "claim_scope": CLAIM, "premise": PREMISE, "empirical": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld"}
    _require(all(report[key] == value for key, value in fixed.items()), "Expression report changed its conditional scope")
    request_hash = _pin(result["request_fingerprint"], request, "Complete original request")
    candidate_hash = _pin(result["candidate_fingerprint"], candidate, "Complete original candidate")
    invocation_hash = _pin(result["invocation_fingerprint"], {"request": request, "candidate": candidate}, "Complete invocation")
    report_hash = _pin(result["report_fingerprint"], report, "Complete native report")
    _require(all(report[key] == result[key] for key in ("request_fingerprint", "candidate_fingerprint", "invocation_fingerprint")) and _same(report["budgets"], request["budgets"]), "Checker evidence changed original identities or budgets")
    budget = _record(request["budgets"], "Budgets")
    usage = _object(report["usage"], {"unit", "charged_work", "request_decoding_work"}, "Checker accounting")
    outer = _object(result["usage"], {"unit", "total_charged_work", "checker_charged_work"}, "Complete operation accounting")
    _require(usage["unit"] == outer["unit"] == "logical_data_visits_and_child_semantic_work", "Expression accounting unit changed")
    maximum = cast(int, budget["max_work"])
    work = _integer(usage["charged_work"], "Checker work", maximum)
    _integer(usage["request_decoding_work"], "Decoding work", work)
    _require(_integer(outer["checker_charged_work"], "Retained checker work", maximum) == work, "Outer operation omitted checker work")
    _integer(outer["total_charged_work"], "Complete operation work", maximum, minimum=work)
    admission = _source(response, request, report)
    structure_ok = _structure(request, candidate, report)
    _requirements_and_ledger(request, candidate, report, admission, structure_ok)
    _artifact(result["artifact"], operation=response.operation, request=request, candidate=candidate, report=report)
    if response.operation == "replay-policy-expression-material":
        _require(_same(result, payload["report"]), "Fresh replay differs from the complete saved expression result")
    _publication(report, cast(int, budget["max_report_bytes"]), cast(int, budget["max_report_nodes"]))
    _publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyExpressionMaterialResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(result))


@dataclass(frozen=True)
class PolicyExpressionMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyExpressionMaterialResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _original(snapshot["request"])
        if operation == "compile-policy-expression-material":
            _require(self.transport.role == "core", "Expression production requires an explicit Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        _require(_same(capabilities.profiles.get("policy_expression_material"), PROFILE) and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks the exact expression profile")
        if operation == "compile-policy-expression-material":
            _require(_same(capabilities.profiles.get("policy_expression_material_producer"), PRODUCER_PROFILE), "Selected Core lacks the exact expression producer profile")
        response = self.transport.call(operation, snapshot, cancelled=cancelled)
        _require(response.operation == operation and response.executable == self.transport.role, "Expression transport response changed operation or executable")
        return _result(response, snapshot)

    def compile(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
        return self._call("compile-policy-expression-material", {"request": request}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
        return self._call("check-policy-expression-material", {"request": request, "candidate": candidate}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
        return self._call("replay-policy-expression-material", {"request": request, "candidate": candidate, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
        return self._call("export-policy-expression-material", {"request": request, "candidate": candidate}, cancelled=cancelled)
