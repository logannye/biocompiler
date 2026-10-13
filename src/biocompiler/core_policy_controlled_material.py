"""Native structural two-RNA checkpoint; no Python construction or activity model."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, cast

from . import core_policy_controlled_composition as admission
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json
from .core_policy import _semantic
from .core_policy_material import PolicyMaterialResult, _artifact_members, _publication
from .core_policy_operational import _fingerprint, _pin, _same

CONSTRUCT = "construct-policy-controlled-material"
CHECK = "check-policy-controlled-material"
PUBLISH = "publish-policy-controlled-material"
VALIDATION_SCOPE = "policy-controlled-composition-material-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_controlled_material.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_controlled_material.v1"
CANDIDATE_SCHEMA = "biocompiler.policy_controlled_composition_material_candidate.v0.1"
REPORT_SCHEMA = "biocompiler.policy_controlled_composition_material_assessment.v0.1"
MANIFEST_SCHEMA = "biocompiler.policy_controlled_composition_material_manifest.v0.1"
ACCEPTED_STATUS = "checked_controlled_material"
PROFILE: dict[str, JsonValue] = {**admission.PROFILE, "operations": [CHECK, PUBLISH],
    "candidate_schema": CANDIDATE_SCHEMA, "schema_version": RESULT_SCHEMA,
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
    "stage": "material", "artifact": "structural_pair_only"}
PRODUCER_PROFILE: dict[str, JsonValue] = {**PROFILE, "operations": [CHECK, PUBLISH, CONSTRUCT]}
_RESULT_FIELDS = set("schema_version implementation resource_profile validation_scope request_fingerprint candidate_fingerprint invocation_fingerprint candidate report_fingerprint report artifact usage".split())
_REPORT_FIELDS = set("schema_version profile implementation stage status outcome claim_scope request_fingerprint candidate_fingerprint invocation_fingerprint admission structure material_limits bindings context resources budgets behavior_status empirical_status human_use therapeutic_export".split())
_STRUCTURE_FIELDS = set("schema_version profile implementation_version claim_scope authority_fingerprint candidate_fingerprint content_reconstruction content_outcome structural_outcome outcome checked_clauses PM-08_scope unassessed_clauses members diagnostics context_status implementation policy material_binding export".split())
_NOMINAL_STRUCTURE_FIELDS = _STRUCTURE_FIELDS | {"source_request_fingerprint", "nominal_translation_definition", "physical_translation_status"}
_OUTCOMES = {"pass", "fail", "unsupported", "unknown"}
_record = admission._record
_rows = admission._rows
_count = admission._count


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _flags(value: dict[str, JsonValue], expected: dict[str, JsonValue], label: str) -> None:
    _require(all(value.get(key) == item for key, item in expected.items()), label)


def _nominal_translation_definition() -> dict[str, JsonValue]:
    """Exact transport premise; this reader does not evaluate translation."""
    return {"$type": "SemanticDefinition", "id": "biocompiler.controlled.nominal_translation.v1",
        "version": "1", "category": "model",
        "meaning": "Decode canonical parent RNA bases with the standard genetic code and one terminal stop; declared N1-methylpseudouridine at canonical U positions is projected to U for nominal sequence correspondence only. Physical translation of modified nucleotides, processing and biological expression remain unmeasured assumptions.",
        "parameters": [], "result": None, "clauses": [], "assumptions": [],
        "executor_kind": None, "subject_kind": None}


def _requests_nominal_translation(original: dict[str, JsonValue]) -> bool:
    definition = _nominal_translation_definition()
    entry = _record(_record(original["catalog_binding"])["entry"])
    dependencies = [_record(row) for row in _rows(entry["dependencies"])]
    pins = [row for row in dependencies if row.get("id") == definition["id"]]
    if not pins:
        return False
    document = _record(_record(original["source_authority"])["document"])
    semantics = _record(_record(document["program"])["semantics"])
    bodies = [_record(row) for row in _rows(semantics["definitions"])]
    matches = [row for row in bodies if row.get("id") == definition["id"]]
    reference: JsonValue = {"$type": "DefinitionRef", "id": definition["id"], "version": "1",
        "digest": _fingerprint(_semantic(definition))}
    _require(len(pins) == len(matches) == 1 and _same(pins[0], reference) and _same(matches[0], definition),
             "Nominal translation requires the exact original definition and selected dependency")
    return True


def _candidate(value: JsonValue) -> dict[str, JsonValue]:
    candidate = _object(value, {"schema_version", "request_fingerprint", "construction"}, "Controlled material candidate")
    _require(candidate["schema_version"] == CANDIDATE_SCHEMA, "Unknown material-only candidate")
    content = _object(candidate["construction"], set("schema_version authority_fingerprint member_order values inventory missing_members diagnostics experimental_amounts".split()), "Construction content")
    _require(content["schema_version"] == "biocompiler.construction_content.v0.1", "Unknown source-neutral construction")
    for field in ("member_order", "values", "missing_members", "diagnostics", "experimental_amounts"):
        _rows(content[field])
    if content["inventory"] is not None:
        inventory = _object(content["inventory"], {"schema_version", "id", "molecules", "complexes", "role_instances", "form_mappings"}, "Complete molecular inventory")
        _require(inventory["schema_version"] == "biocompiler.molecular_content_inventory.v0.1", "Unknown molecular inventory")
        for field in ("molecules", "complexes", "role_instances", "form_mappings"):
            for row in _rows(inventory[field]):
                _record(row)
    _publication(candidate, 4_000_000, 100_000)
    return candidate


def _admission(value: JsonValue, original: dict[str, JsonValue], total: int, decoding: int) -> None:
    """Bind retained admission evidence directly, without fabricating a child call."""
    report = _object(value, admission._REPORT_FIELDS, "Retained original admission")
    _flags(report, {"schema_version": admission.REPORT_SCHEMA, "profile": admission.REQUEST_PROFILE,
        "stage": "admission", "status": "admitted", "claim_scope": "supplied_authority_and_complete_finite_domain_only",
        "construction_status": "not_performed", "behavior_status": "not_performed", "empirical_status": "unassessed"},
        "Retained admission crossed its original stage")
    authority, domain, material = (_record(original[key]) for key in ("source_authority", "operating_domain", "material_authority"))
    document = _record(authority["document"])
    for key, obj in (("request_fingerprint", original), ("source_fingerprint", document),
                     ("domain_fingerprint", domain), ("material_fingerprint", material)):
        _pin(report[key], obj, "Retained " + key)
    _require(_same(report["budgets"], original["budgets"]), "Retained admission changed original limits")
    program = _record(document["program"])
    model = _record(_record(original["mechanism_model"])["body"])
    originals = {"definitions": _record(program["semantics"])["definitions"],
        "catalog_entries": _record(document["implementations"])["implementations"],
        "model_components": model["components"], "model_ports": model["ports"],
        "members": material["members"], "products": _record(authority["control_contract"])["products"],
        "roots": _record(material["template"])["sources"], "transforms": _record(material["template"])["steps"],
        "source_records": _record(authority["project_context"])["sources"],
        "empirical_assertions": _record(original["context"])["empirical_assertions"]}
    inventory = _object(report["authority_inventory"], set(originals), "Complete admitted authority")
    for key, rows in originals.items():
        _require(_count(inventory[key], 1_000_000) == len(_rows(rows)), "Retained authority census changed")
    factors = {"fixed_input_count": "fixed_inputs", "physical_factor_count": "physical_factors",
               "evidence_factor_count": "evidence_factors", "lifecycle_factor_count": "lifecycle_factors"}
    inventory = _object(report["domain_inventory"], set(factors), "Complete domain inventory")
    for key, field in factors.items():
        _require(_count(inventory[key], 1_000_000) == len(_rows(domain[field])), "Domain factors changed")
    counters = _object(report["domain_counters"], {"prefixes", "transitions", "histories", "work"}, "Complete domain counters")
    limits = _record(domain["limits"])
    counts = {key: _count(raw, _count(limits.get("max_" + key), 16_000_000, 1), 1) for key, raw in counters.items()}
    _require(counts["prefixes"] == counts["transitions"] + 1 and counts["histories"] <= counts["transitions"]
             and counts["work"] <= total - decoding, "Retained enumeration exceeds cumulative work")
    admission._source(report["source_admission"], authority, domain)
    _require(_count(_record(report["source_admission"])["horizon_ticks"], 64, 1) == domain["horizon_tick"],
             "Retained source admission changed its exact integral horizon")


def _normalized_authority(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Existing inert codecs define child identities; full request pins stay raw."""
    from .ir.payload_contracts import PayloadTemplate
    from .ir.molecule_chemistry import MoleculeChemistry
    from .ir.molecule_records import DeclarationProvenance
    from .ir.circuit_recoding import TranslationPolicy
    from .ir.component_contracts import PinnedIdentity
    try:
        members: list[JsonValue] = []
        for raw in _rows(value["members"]):
            member = _record(raw)
            product = _record(member["product"])
            members.append({**member, "chemistry": MoleculeChemistry.from_dict(member["chemistry"]).to_dict(),
                "product": {**product, "identity": PinnedIdentity.from_dict(product["identity"]).to_dict(),
                    "translation_policy": TranslationPolicy.from_dict(product["translation_policy"]).to_dict(),
                    "provenance": DeclarationProvenance.from_dict(product["provenance"]).to_dict()}})
        return {**value, "template": PayloadTemplate.from_dict(value["template"]).to_dict(), "members": members}
    except (ValueError, TypeError, KeyError) as error:
        raise CoreProtocolError("Malformed original molecular authority") from error


def _normalized_content(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    from .artifacts.circuit_construction import ConstructedValue
    from .ir.circuit_molecules import CircuitMolecule, MolecularComplex, MoleculeRoleInstance, FormCoordinateMapping
    from .artifacts.circuit_molecules import ExperimentalAmount
    try:
        result = dict(value)
        result["values"] = sorted([ConstructedValue.from_dict(row).to_dict() for row in _rows(value["values"])], key=lambda row: str(_record(row)["id"]))
        result["experimental_amounts"] = sorted([ExperimentalAmount.from_dict(row).to_dict() for row in _rows(value["experimental_amounts"])], key=lambda row: str(_record(row)["id"]))
        result["diagnostics"] = cast(list[JsonValue], sorted(cast(list[str], _rows(value["diagnostics"]))))
        result["missing_members"] = cast(list[JsonValue], sorted(cast(list[str], _rows(value["missing_members"]))))
        if value["inventory"] is not None:
            inventory = _record(value["inventory"])
            result["inventory"] = {**inventory,
                "molecules": [CircuitMolecule.from_dict(row).to_dict() for row in _rows(inventory["molecules"])],
                "complexes": [MolecularComplex.from_dict(row).to_dict() for row in _rows(inventory["complexes"])],
                "role_instances": [MoleculeRoleInstance.from_dict(row).to_dict() for row in _rows(inventory["role_instances"])],
                "form_mappings": [FormCoordinateMapping.from_dict(row).to_dict() for row in _rows(inventory["form_mappings"])]}
        return result
    except (ValueError, TypeError, KeyError) as error:
        raise CoreProtocolError("Malformed construction content") from error


def _structure(value: JsonValue, original: dict[str, JsonValue], candidate: dict[str, JsonValue]) -> str:
    nominal = _requests_nominal_translation(original)
    report = _object(value, _NOMINAL_STRUCTURE_FIELDS if nominal else _STRUCTURE_FIELDS,
                     "Complete independent structural assessment")
    material = _normalized_authority(_record(original["material_authority"]))
    content = _normalized_content(_record(candidate["construction"]))
    if nominal:
        _flags(report, {"schema_version": "biocompiler.policy_controlled_nominal_structure_assessment.v0.1",
            "profile": "biocompiler.policy_controlled_nominal_structure.v0.1",
            "implementation_version": "biocompiler.ocaml.policy_controlled_nominal_structure_check.v0.1",
            "claim_scope": "exact_supplied_mrna_structure_under_explicit_controlled_nominal_translation_premise",
            "physical_translation_status": "unassessed"}, "Nominal structural leaf upgraded its limited scope")
        _pin(report["source_request_fingerprint"], original, "Nominal translation original request")
        _require(_same(report["nominal_translation_definition"], _nominal_translation_definition()),
                 "Nominal structural leaf changed its exact source premise")
    else:
        _flags(report, {"schema_version": "biocompiler.policy_mrna_structure_assessment.v0.1",
            "profile": "biocompiler.policy_mrna_completeness.v0.1",
            "implementation_version": "biocompiler.ocaml.policy_mrna_structure_check.v0.1",
            "claim_scope": "exact_supplied_mrna_structure_and_derivation_only"}, "Structural leaf upgraded its limited scope")
    _flags(report, {"PM-08_scope": "supplied_construction_region_chemistry_product_declaration_provenance_only",
        "checked_clauses": ["PM-02", "PM-03", "PM-04", "PM-05", "PM-06", "PM-07", "PM-09"],
        "unassessed_clauses": ["PM-01", "PM-08_external_component_binding", "PM-10", "PM-11", "PM-12"],
        "context_status": "unassessed", "implementation": "unassessed", "policy": "unassessed",
        "material_binding": "unassessed", "export": "withheld"}, "Structural leaf upgraded its limited scope")
    _pin(report["authority_fingerprint"], material, "Complete structural authority")
    _pin(report["candidate_fingerprint"], content, "Complete construction content")
    reconstructed = _object(report["content_reconstruction"], set("schema_version implementation_version claim_scope authority_fingerprint candidate_fingerprint reconstructed_fingerprint outcome context_status payload_completeness diagnostics".split()), "Independent reconstruction")
    _flags(reconstructed, {"schema_version": "biocompiler.construction_content_assessment.v0.1",
        "implementation_version": "biocompiler.ocaml.construction_content_check.v0.1",
        "claim_scope": "exact_supplied_template_molecular_content", "context_status": "unassessed",
        "payload_completeness": "unassessed"}, "Construction evidence upgraded its scope")
    authority: JsonValue = {"schema_version": "biocompiler.construction_content_authority.v0.1",
        "template": material["template"], "member_order": material["member_order"]}
    _pin(reconstructed["authority_fingerprint"], authority, "Independent construction authority")
    _pin(reconstructed["candidate_fingerprint"], content, "Independent reconstruction candidate")
    diagnostics = _rows(reconstructed["diagnostics"])
    _require(all(type(row) is str for row in diagnostics), "Malformed construction diagnostics")
    for key in ("outcome", "content_outcome", "structural_outcome"):
        _require(type(report[key]) is str and report[key] in _OUTCOMES, "Unknown structural outcome")
    _require(reconstructed["outcome"] == report["content_outcome"], "Construction outcomes disagree")
    outcomes = (report["content_outcome"], report["structural_outcome"])
    expected_outcome = next((item for item in ("fail", "unsupported", "unknown") if item in outcomes), "pass")
    _require(report["outcome"] == expected_outcome, "Structural outcomes do not compose")
    for row in _rows(report["diagnostics"]):
        finding = _object(row, {"clause", "member", "severity", "code"}, "Structural diagnostic")
        _require(finding["severity"] in ("fail", "unsupported", "unknown") and type(finding["code"]) is str,
                 "Unknown structural diagnostic")
    inventory = None if content["inventory"] is None else _record(content["inventory"])
    molecules = [] if inventory is None else [_record(row) for row in _rows(inventory["molecules"])]
    expected_members = [_record(row) for row in _rows(material["members"])]
    expected_rows: list[JsonValue] = []
    for member in expected_members:
        matches = [mol for mol in molecules if mol.get("id") == member["id"]]
        if len(matches) == 1:
            expected_rows.append({"member": member["id"], "molecule_fingerprint": _fingerprint(matches[0]),
                "product_identity": _record(member["product"])["identity"],
                "expected_product": _record(member["product"])["sequence"]})
    rows = _rows(report["members"])
    _require(len(rows) == len(expected_rows), "Structural member evidence inventory changed")
    for raw, expected in zip(rows, expected_rows):
        row = _object(raw, {"member", "molecule_fingerprint", "product_identity", "expected_product", "translated_product"}, "Complete member evidence")
        _require(all(_same(row[key], item) for key, item in _record(expected).items()), "Member evidence changed original product identity")
        _require(row["translated_product"] is None or type(row["translated_product"]) is str, "Malformed translation observation")
        if report["outcome"] == "pass":
            _require(row["translated_product"] == row["expected_product"], "Accepted translation differs from supplied product")
    if reconstructed["outcome"] == "pass":
        _pin(reconstructed["reconstructed_fingerprint"], content, "Fresh reconstructed content")
        _require(not diagnostics, "Accepted reconstruction retained failures")
    if report["outcome"] == "pass":
        _require(not _rows(report["diagnostics"]) and len(rows) == 2, "Accepted structural report omitted a member or retained failures")
        _pin(content["authority_fingerprint"], authority, "Candidate original authority")
        _require(content["missing_members"] == content["diagnostics"] == content["experimental_amounts"] == [], "Accepted content retained unsupported or missing material")
    return cast(str, report["outcome"])


@dataclass(frozen=True)
class PolicyControlledMaterialResult(PolicyMaterialResult):
    """Immutable structural evidence; it never grants therapeutic export authority."""


def _validate_report(report: dict[str, JsonValue], request: dict[str, JsonValue],
                     candidate: dict[str, JsonValue], *, total: int, decoding: int) -> None:
    """Validate retained leaf evidence directly; this grants no native capability."""
    _object(report, _REPORT_FIELDS, "Complete retained material assessment")
    original = request
    request_hash = _fingerprint(request)
    candidate_hash = _fingerprint(candidate)
    invocation_hash = _fingerprint({"request_fingerprint": request_hash, "candidate_fingerprint": candidate_hash})
    _flags(report, {"schema_version": REPORT_SCHEMA, "profile": admission.REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_controlled_material_check.v0.1", "stage": "material",
        "claim_scope": "exact_supplied_two_member_rna_structure_only", "request_fingerprint": request_hash,
        "candidate_fingerprint": candidate_hash, "invocation_fingerprint": invocation_hash,
        "behavior_status": "not_performed", "empirical_status": "unassessed", "human_use": "unassessed",
        "therapeutic_export": "withheld"}, "Material evidence upgraded its original structural scope")
    for key in ("context", "resources", "budgets"):
        _require(_same(report[key], original[key]), "Material report changed original " + key)
    _require(_same(report["bindings"], _record(original["assembly"])["product_bindings"]), "Material bindings changed original identities")
    budgets = _record(original["budgets"])
    _admission(report["admission"], original, total, decoding)
    structural_outcome = _structure(report["structure"], original, candidate)
    content = _record(candidate["construction"])
    inventory = None if content["inventory"] is None else _record(content["inventory"])
    molecules = [] if inventory is None else [_record(row) for row in _rows(inventory["molecules"])]
    resources = _record(original["resources"])
    expected_order = _record(original["material_authority"])["member_order"]
    lengths: list[JsonValue] = []
    for molecule in molecules:
        sequence = molecule.get("sequence")
        _require(type(sequence) is str, "Candidate molecule lacks exact sequence text")
        length = len(cast(str, sequence))
        lengths.append({"member_id": molecule.get("id"), "rna_nt": length,
                        "within_limit": length <= cast(int, resources["max_member_rna_nt"])})
    order: JsonValue = [m.get("id") for m in molecules]
    count = sum(cast(int, _record(row)["rna_nt"]) for row in lengths)
    passed = len(molecules) == 2 and _same(order, expected_order) and all(_record(row)["within_limit"] is True for row in lengths) and count <= cast(int, resources["max_total_rna_nt"])
    expected_limits: JsonValue = {"member_order": order, "expected_member_order": expected_order, "members": lengths,
        "max_member_rna_nt": resources["max_member_rna_nt"], "total_rna_nt": count,
        "max_total_rna_nt": resources["max_total_rna_nt"], "outcome": "pass" if passed else "fail"}
    _require(_same(report["material_limits"], expected_limits), "Material accounting differs from original bounds and complete candidate")
    outcome = structural_outcome if passed else "fail"
    _require(report["outcome"] == outcome and report["status"] == (ACCEPTED_STATUS if outcome == "pass" else "not_accepted"), "Material verdict contradicts independent leaf or limits")
    _publication(report, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyControlledMaterialResult:
    _require(response.operation in (CONSTRUCT, CHECK, PUBLISH) and response.status == "ok" and not response.diagnostics,
             "Material checkpoint requires an unambiguous native response")
    original = _record(payload["request"])
    value = _object(response.result, _RESULT_FIELDS, "Complete material-only result")
    _flags(value, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
        "resource_profile": admission.RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE}, "Material result changed its negotiated profile")
    candidate = _candidate(value["candidate"])
    _pin(candidate["request_fingerprint"], original, "Candidate original request")
    if "candidate" in payload:
        _require(_same(candidate, payload["candidate"]), "Native checker substituted the supplied candidate")
    request_hash = _pin(value["request_fingerprint"], original, "Complete request")
    candidate_hash = _pin(value["candidate_fingerprint"], candidate, "Complete candidate")
    invocation_hash = _pin(value["invocation_fingerprint"], {"request_fingerprint": request_hash,
        "candidate_fingerprint": candidate_hash}, "Material invocation")
    report = _object(value["report"], _REPORT_FIELDS, "Material-only assessment")
    report_hash = _pin(value["report_fingerprint"], report, "Complete assessment")
    budgets = _record(original["budgets"])
    usage = _object(value["usage"], {"unit", "preparation_charged_work", "request_decoding_work", "publication"}, "Material work accounting")
    _flags(usage, {"unit": "logical_data_visits_and_child_semantic_work", "publication": "requires_original_one_shot_frame_guard"}, "Material work accounting changed")
    total = _count(usage["preparation_charged_work"], cast(int, budgets["max_work"]), 1)
    decoding = _count(usage["request_decoding_work"], total, 1)
    _validate_report(report, original, candidate, total=total, decoding=decoding)
    outcome = report["outcome"]
    content = _record(candidate["construction"])
    artifact = value["artifact"]
    if response.operation != PUBLISH or outcome != "pass":
        _require(artifact is None, "Unchecked or nonpublication result returned material bytes")
    else:
        pair = _object(artifact, {"fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Structural pair")
        _require(type(pair["fasta"]) is str and pair["fasta_sha256"] == hashlib.sha256(pair["fasta"].encode()).hexdigest(), "Structural FASTA digest changed")
        manifest = _object(pair["manifest"], set("schema_version stage request candidate report request_fingerprint candidate_fingerprint invocation_fingerprint report_fingerprint members behavior_status empirical_status human_use therapeutic_export".split()), "Complete structural manifest")
        _flags(manifest, {"schema_version": MANIFEST_SCHEMA, "stage": "material", "request_fingerprint": request_hash,
            "candidate_fingerprint": candidate_hash, "invocation_fingerprint": invocation_hash, "report_fingerprint": report_hash,
            "behavior_status": "not_performed", "empirical_status": "unassessed", "human_use": "unassessed", "therapeutic_export": "withheld"}, "Structural manifest upgraded its claim")
        for key, obj in (("request", original), ("candidate", candidate), ("report", report)):
            _require(_same(manifest[key], obj), "Structural manifest changed full " + key)
        _pin(pair["manifest_sha256"], manifest, "Complete structural manifest")
        _artifact_members(construction=content, members=manifest["members"], fasta=pair["fasta"],
                          fasta_sha256=pair["fasta_sha256"], manifest_fasta_sha256=pair["fasta_sha256"])
    _publication(report, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))
    _publication({"result": value}, admission.MAX_RESULT_BYTES, admission.MAX_RESULT_NODES)
    return PolicyControlledMaterialResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(value))


@dataclass(frozen=True)
class PolicyControlledMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyControlledMaterialResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        admission._original(snapshot["request"])
        if "candidate" in snapshot:
            _candidate(snapshot["candidate"])
        _require(operation != CONSTRUCT or self.transport.role == "core", "Material construction requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        profile = PRODUCER_PROFILE if self.transport.role == "core" else PROFILE
        _require(_same(capabilities.profiles.get("policy_controlled_composition_material"), profile)
                 and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks the exact material-only capability")
        response = self.transport.call(operation, snapshot, cancelled=cancelled)
        _require(response.operation == operation and response.executable == self.transport.role, "Material response changed operation or executable role")
        return _result(response, snapshot)

    def construct_material(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledMaterialResult:
        return self._call("construct-policy-controlled-material", {"request": request}, cancelled=cancelled)

    def check_material(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledMaterialResult:
        return self._call("check-policy-controlled-material", {"request": request, "candidate": candidate}, cancelled=cancelled)

    def publish_material(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledMaterialResult:
        return self._call("publish-policy-controlled-material", {"request": request, "candidate": candidate}, cancelled=cancelled)
