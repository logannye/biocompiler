"""Immutable native policy-to-mRNA transport; no Python semantic fallback."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Literal, cast

from biocompiler import core_policy_implementation as implementation
from biocompiler import core_policy_operational as operational
from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json,
)

VALIDATION_SCOPE = "policy-truth-mrna-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_material.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_material_resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_material.v1"
CANDIDATE_SCHEMA = "biocompiler.policy_material_candidate.v0.1"
REQUEST_SCHEMA = "biocompiler.policy_material_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_truth_mrna.v0.1"
REPORT_SCHEMA = "biocompiler.policy_material_assessment.v0.1"
EXPORT_SCHEMA = "biocompiler.policy_mrna_export.v0.1"
MAX_RESULT_BYTES = 8323072
MAX_RESULT_NODES = 249968
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-material", "replay-policy-material", "export-policy-material"],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "on_fresh_export_only", "empirical": "unassessed",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {
    "operations": ["compile-policy-material"],
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
}
_REQUEST_FIELDS = {"schema_version", "profile", "implementation_request", "material_contract", "context", "catalog_binding", "budgets"}
_CANDIDATE_FIELDS = {"schema_version", "behavior", "implementation", "binding", "material_binding", "construction"}
_RESULT_FIELDS = {"schema_version", "implementation", "resource_profile", "validation_scope", "request_fingerprint",
                  "candidate_fingerprint", "invocation_fingerprint", "report_fingerprint", "candidate", "report", "artifact"}
_REPORT_FIELDS = {"schema_version", "profile", "implementation", "resource_profile", "request_fingerprint", "candidate_fingerprint",
                  "invocation_fingerprint", "status", "claim_scope", "premise", "preservation", "catalog", "material", "context",
                  "material_status", "context_status", "obligations", "all_original_obligations_discharged", "limits", "budgets",
                  "empirical", "artifact", "export", "usage"}
_same = operational._same
_pin = operational._pin
_fingerprint = operational._fingerprint
_record = implementation._record
_rows = implementation._rows
_count = implementation._count


def _original(value: JsonValue) -> dict[str, JsonValue]:
    request = _object(value, _REQUEST_FIELDS, "Original material request")
    if request["schema_version"] != REQUEST_SCHEMA or request["profile"] != REQUEST_PROFILE:
        raise CoreProtocolError("Material request changed its closed original profile")
    implementation._original(request["implementation_request"])
    for key in ("material_contract", "context", "catalog_binding", "budgets"):
        _record(request[key], "Original " + key)
    return request


def _preservation(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                  report: dict[str, JsonValue], limits: JsonValue, *, prerequisites: bool = False,
                  two_observations: bool = False, multi_product: bool = False, finite_machine: bool = False, network: bool = False) -> None:
    decoder = (implementation._network_original if network else implementation._finite_machine_original if finite_machine else implementation._multi_product_original if multi_product else implementation._two_observation_original if two_observations else
               implementation._prerequisite_original if prerequisites else implementation._original)
    original = decoder(request["implementation_request"])
    evidence = _object(report["preservation"], implementation._REPORT_FIELDS, "Complete preservation evidence")
    if (evidence["schema_version"] != "biocompiler.policy_preservation_report.v0.1"
            or evidence["profile"] != implementation.PRESERVATION_PROFILE or not _same(evidence["limits"], limits)):
        raise CoreProtocolError("Material checking changed original preservation profile or limits")
    _pin(evidence["request_fingerprint"], original, "Original implementation request")
    implementation._claim(evidence)
    implementation._authority(response, original, candidate, evidence, prerequisites=prerequisites,
                              two_observations=two_observations, multi_product=multi_product, finite_machine=finite_machine, network=network)
    implementation._evidence(original, evidence)



def _context_obligations(request: dict[str, JsonValue], report: dict[str, JsonValue],
                         leaf: dict[str, JsonValue]) -> None:
    """Retain complete source obligations and exact original provider evidence."""
    preservation = _record(report["preservation"], "Preservation")
    binding = _record(preservation["binding"], "Binding")
    admission = _record(binding["source_admission"], "Admission")
    assessment = _record(admission["source_assessment"], "Original source assessment")
    original_ids = assessment.get("unresolved_obligations")
    if type(original_ids) is not list or any(type(value) is not str for value in original_ids):
        raise CoreProtocolError("Context lacks the complete original source obligation inventory")
    context = _record(request["context"], "Original context")
    providers = _rows(context.get("providers"), "Original context providers")
    provider_bodies = [_record(provider.get("body"), "Original provider body") for provider in providers]
    names = ["chassis_capability_and_delivery_suitability"]
    for provider in provider_bodies:
        definition = _record(provider.get("definition"), "Original provider definition")
        identifier = definition.get("id")
        if type(identifier) is not str:
            raise CoreProtocolError("Context provider lacks its original definition identity")
        names.append("semantic_definition:" + identifier)
    discharged = [value for value in original_ids if value in names] if leaf["outcome"] == "pass" else []
    expected_discharges: JsonValue = [{"id": value, "evidence": [provider.get("identity") for provider in providers]}
                                     for value in discharged]
    expected_obligations: JsonValue = [{"id": value, "context_status": "discharged" if value in discharged else "outside_stage"}
                                      for value in original_ids]
    if not _same(leaf["discharges"], expected_discharges) or not _same(leaf["source_obligations"], expected_obligations):
        raise CoreProtocolError("Context changed or omitted original source obligations or provider discharge evidence")


def _context_inventories(request: dict[str, JsonValue], report: dict[str, JsonValue],
                         leaf: dict[str, JsonValue]) -> None:
    """Retain original inventories; capacity and biological semantics remain native."""
    _context_obligations(request, report, leaf)
    context = _record(request["context"], "Original context")
    providers = _rows(context.get("providers"), "Original context providers")
    provider_bodies = [_record(provider.get("body"), "Original provider body") for provider in providers]
    contract = _record(request["material_contract"], "Original material contract")
    body = _record(contract.get("body"), "Original material body")
    resources = _rows(body.get("resources"), "Original resources")
    derived = [_object(row, {"unit", "scope", "owner", "quantity"}, "Retained derived demand")
               for row in _rows(leaf["derived_demands"], "Retained derived demands")]
    for row in derived:
        quantity = row["quantity"]
        if type(quantity) is not int or quantity <= 0:
            raise CoreProtocolError("Context derived demand has an invalid positive quantity")
    if leaf["outcome"] == "pass":
        def demand_key(row: dict[str, JsonValue]) -> bytes:
            return encode_json({key: row.get(key) for key in ("unit", "scope", "owner")})
        originals = sorted(resources, key=demand_key)
        retained = sorted(derived, key=demand_key)
        if [demand_key(row) for row in originals] != [demand_key(row) for row in retained]:
            raise CoreProtocolError("Context omitted or changed the original derived-demand inventory")
        for original, actual in zip(originals, retained):
            declared = _count(original.get("quantity"), "Original declared demand quantity")
            required = _count(actual["quantity"], "Retained derived demand quantity")
            if required > declared:
                raise CoreProtocolError("Context derived demand exceeds its original declared reservation")
    allocations = _rows(body.get("allocations"), "Original resource allocations")
    returned = _rows(leaf["resource_allocations"], "Retained resource allocations")
    if len(returned) > len(allocations) or (leaf["outcome"] == "pass" and len(returned) != len(allocations)):
        raise CoreProtocolError("Context omitted or added original resource allocations")
    # Failure may occur midway through allocation checking. Only emitted rows
    # claim a resolved reservation, and they retain the original prefix order.
    for row, allocation in zip(returned, allocations):
        demands = [value for value in resources if value.get("id") == allocation.get("demand_id")]
        owners = [value for value in provider_bodies if _same(value.get("definition"), allocation.get("provider"))]
        if len(demands) != 1 or len(owners) != 1:
            raise CoreProtocolError("Retained allocation has no unique original demand or provider")
        capacities = [value for value in _rows(owners[0].get("capacities"), "Original provider capacities")
                      if value.get("id") == allocation.get("capacity_id")]
        if len(capacities) != 1:
            raise CoreProtocolError("Retained allocation has no unique original capacity")
        expected: JsonValue = {"demand": demands[0].get("id"), "provider": owners[0].get("definition"),
                               "capacity": capacities[0].get("id"), "pool": capacities[0].get("pool_id"),
                               "reserved": demands[0].get("quantity")}
        if not _same(row, expected):
            raise CoreProtocolError("Context changed an original allocation reservation or its order")


def _structure(value: JsonValue, *, authority: JsonValue, construction: JsonValue, outcome: JsonValue) -> None:
    """Validate retained PM/content evidence; all semantic checking remains native."""
    structure = _object(value, {"schema_version", "profile", "implementation_version", "claim_scope", "authority_fingerprint",
        "candidate_fingerprint", "content_reconstruction", "content_outcome", "structural_outcome", "outcome", "checked_clauses",
        "PM-08_scope", "unassessed_clauses", "members", "diagnostics", "context_status", "implementation", "policy", "material_binding", "export"}, "Fresh structural evidence")
    if (structure.get("schema_version") != "biocompiler.policy_mrna_structure_assessment.v0.1"
            or structure.get("profile") != "biocompiler.policy_mrna_completeness.v0.1"
            or structure.get("implementation_version") != "biocompiler.ocaml.policy_mrna_structure_check.v0.1"
            or structure.get("claim_scope") != "exact_supplied_mrna_structure_and_derivation_only"):
        raise CoreProtocolError("Structural evidence changed its narrow profile")
    _pin(structure.get("authority_fingerprint"), authority, "Original structure authority")
    _pin(structure.get("candidate_fingerprint"), construction, "Original construction candidate")
    if (not _same(structure["checked_clauses"], ["PM-02", "PM-03", "PM-04", "PM-05", "PM-06", "PM-07", "PM-09"])
            or not _same(structure["unassessed_clauses"], ["PM-01", "PM-08_external_component_binding", "PM-10", "PM-11", "PM-12"])
            or structure["PM-08_scope"] != "supplied_construction_region_chemistry_product_declaration_provenance_only"
            or any(structure[key] != "unassessed" for key in ("context_status", "implementation", "policy", "material_binding"))
            or structure["export"] != "withheld"):
        raise CoreProtocolError("Structural evidence upgraded or omitted a separate obligation")
    content = _object(structure["content_reconstruction"], {"schema_version", "implementation_version", "claim_scope", "authority_fingerprint",
        "candidate_fingerprint", "reconstructed_fingerprint", "outcome", "context_status", "payload_completeness", "diagnostics"}, "Independent content reconstruction")
    authority = _record(authority, "Original structure authority")
    if (content["schema_version"] != "biocompiler.construction_content_assessment.v0.1"
            or content["implementation_version"] != "biocompiler.ocaml.construction_content_check.v0.1"
            or content["claim_scope"] != "exact_supplied_template_molecular_content"
            or content["context_status"] != "unassessed" or content["payload_completeness"] != "unassessed"):
        raise CoreProtocolError("Content reconstruction changed its authority or claim scope")
    _pin(content["authority_fingerprint"], {"schema_version": "biocompiler.construction_content_authority.v0.1",
        "template": authority.get("template"), "member_order": authority.get("member_order")}, "Original neutral construction authority")
    _pin(content["candidate_fingerprint"], construction, "Content candidate")
    if content["outcome"] == "pass":
        _pin(content["reconstructed_fingerprint"], construction, "Independently reconstructed content")
    if content["outcome"] != structure["content_outcome"]:
        raise CoreProtocolError("Structure omitted independent reconstruction outcome")
    if outcome == "pass" and any(structure.get(key) != "pass" for key in ("outcome", "content_outcome", "structural_outcome")):
        raise CoreProtocolError("Material PASS contradicts structural reconstruction")


def _leaves(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    contract = _record(request["material_contract"], "Original material contract")
    body = _record(contract.get("body"), "Original complete material case")
    material = report["material"]
    if material is not None:
        leaf = _object(material, {"schema_version", "checker_version", "profile", "contract_fingerprint", "implementation_fingerprint",
            "proposed_fingerprint", "candidate_fingerprint", "outcome", "diagnostics", "claim_scope", "premise", "structure",
            "preservation_evidence_fingerprint", "context", "resource_capacity", "input_compatibility", "source_obligation_discharge",
            "empirical", "artifact", "export"}, "Material correspondence evidence")
        if (leaf["schema_version"] != "biocompiler.policy_material_binding_assessment.v0.1"
                or leaf["checker_version"] != "biocompiler.ocaml.policy_material_binding_check.v0.1"
                or leaf["profile"] != "biocompiler.policy_truth_mrna_material.v0.1"
                or leaf["claim_scope"] != "exact_supplied_whole_graph_material_case"
                or leaf["premise"] != "supplied_conditional_model_to_sequence_contract"):
            raise CoreProtocolError("Material evidence changed its supplied-contract claim")
        for key in ("context", "resource_capacity", "input_compatibility", "source_obligation_discharge", "empirical"):
            if leaf[key] != "unassessed":
                raise CoreProtocolError("Material leaf upgraded a deferred obligation")
        if leaf["artifact"] != "withheld" or leaf["export"] != "withheld":
            raise CoreProtocolError("Material leaf cannot grant export authority")
        for key, original in (("contract_fingerprint", contract), ("implementation_fingerprint", candidate["implementation"]),
                ("proposed_fingerprint", candidate["material_binding"]), ("candidate_fingerprint", candidate["construction"]),
                ("preservation_evidence_fingerprint", report["preservation"])):
            _pin(leaf[key], original, key)
        _structure(leaf["structure"], authority=body.get("structure_authority"),
                   construction=candidate["construction"], outcome=leaf["outcome"])
    context = report["context"]
    if context is not None:
        leaf = _object(context, {"schema_version", "profile", "implementation_version", "context_fingerprint", "material_binding_fingerprint",
            "outcome", "claim_scope", "record_layout", "derived_demands", "resource_allocations", "source_obligations", "discharges",
            "diagnostics", "source_receipt_status", "biological_validity", "human_use", "export"}, "Context evidence")
        original_context = _record(request["context"], "Original context")
        if (leaf["schema_version"] != "biocompiler.policy_material_context_assessment.v0.1"
                or leaf["profile"] != original_context.get("profile")
                or leaf["implementation_version"] != "biocompiler.ocaml.policy_material_context_check.v0.1"
                or leaf["claim_scope"] != "conditional_exact_context_and_complete_record_capacity"
                or leaf["source_receipt_status"] != "unchanged" or leaf["biological_validity"] != "unassessed"
                or leaf["human_use"] != "unassessed" or leaf["export"] != "withheld"):
            raise CoreProtocolError("Context evidence upgraded or changed its declared scope")
        _pin(leaf["context_fingerprint"], original_context, "Original context")
        _pin(leaf["material_binding_fingerprint"], material, "Fresh material evidence")
        if not _same(leaf["record_layout"], original_context.get("record_layout")):
            raise CoreProtocolError("Context evidence changed its original record layout")
        _context_inventories(request, report, leaf)
    catalog = report["catalog"]
    if catalog is not None:
        row = _object(catalog, {"status", "original_binding", "selected_catalog_entry", "contract_fingerprint", "premise"}, "Original material catalog bridge")
        original = _record(request["catalog_binding"], "Original material catalog bridge")
        if (row["status"] != "pass" or not _same(row["original_binding"], original)
                or row["selected_catalog_entry"] != original.get("entry_id")
                or row["premise"] != "supplied_conditional_model_to_sequence_contract"):
            raise CoreProtocolError("Material catalog evidence changed its external original authority")
        _pin(row["contract_fingerprint"], contract, "Original material case")
    for field, key in ((material, "material_status"), (context, "context_status")):
        expected = "unassessed" if field is None else _record(field, key).get("outcome")
        if expected not in ("unassessed", "pass", "fail", "unknown", "unsupported") or report[key] != expected:
            raise CoreProtocolError("Material stage status contradicts its retained evidence")


def _obligations(report: dict[str, JsonValue], *, material_key: str = "material",
                 accepted_status: str = "checked_material",
                 conjunction_stage: str = "conditional_material_context_conjunction",
                 prerequisite_key: str | None = None, multi_product: bool = False,
                 finite_machine: bool = False, network: bool = False, quantitative_key: str | None = None) -> None:
    preservation = _record(report["preservation"], "Preservation")
    binding = _record(preservation["binding"], "Binding")
    admission = _record(binding["source_admission"], "Admission")
    assessment = _record(admission["source_assessment"], "Original source assessment")
    rows = _rows(report["obligations"], "Complete original obligation ledger")
    if not _same([row.get("obligation") for row in rows], assessment.get("unresolved_obligations")):
        raise CoreProtocolError("Material checking removed or reordered an original source obligation")
    for value in rows:
        row = _object(value, {"obligation", "status", "stage", "evidence"}, "Obligation disposition")
        if row["status"] == "unresolved":
            if row["stage"] is not None or row["evidence"] is not None:
                raise CoreProtocolError("Unresolved obligation carries contradictory discharge evidence")
        elif row["status"] == "discharged":
            quantitative_fields = {quantitative_key} if quantitative_key is not None else set()
            if quantitative_key is not None:
                quantitative = report.get(quantitative_key)
                if (quantitative is None or _record(quantitative, "Required quantitative report").get("outcome") != "pass"
                        or report.get(quantitative_key + "_status") != "pass"):
                    raise CoreProtocolError("Quantitative obligations require a fresh passing original-law correspondence")
                _pin(_record(row["evidence"], "Quantitative obligation evidence").get(quantitative_key), quantitative, "Obligation quantitative")
            stage = row["stage"]
            if stage == "bounded_machine_semantics_and_declared_requirements":
                evidence = _object(row["evidence"], {"preservation", "machine_binding", "state_and_terminal_semantics", "prefixes",
                    "retained_attempt_identity", "universal_termination", "progress"} | quantitative_fields, "Bounded machine evidence")
                if (material_key != "assembly" or row["obligation"] != "machine_reachability_termination_and_progress"
                        or binding.get("schema_version") != (implementation.NETWORK_BINDING_REPORT_SCHEMA if network else implementation.FINITE_MACHINE_BINDING_REPORT_SCHEMA if finite_machine else implementation.MULTI_PRODUCT_BINDING_REPORT_SCHEMA if multi_product else "biocompiler.policy_implementation_binding_report.v0.2")
                        or binding.get("profile") != (implementation.NETWORK_BINDING_PROFILE if network else implementation.FINITE_MACHINE_BINDING_PROFILE if finite_machine else implementation.MULTI_PRODUCT_BINDING_PROFILE if multi_product else "biocompiler.policy_staged_source_graph.v0.1")
                        or preservation.get("status") != "checked_implementation"
                        or any(evidence[key] != expected for key, expected in (
                            ("state_and_terminal_semantics", "exact_bounded_source_correspondence"),
                            ("prefixes", "complete_original_domain"), ("retained_attempt_identity", "creation_fixed_injective"),
                            ("universal_termination", "not_claimed"), ("progress", "declared_requirements_only")))):
                    raise CoreProtocolError("Machine obligation widened its exact bounded interpretation")
                _pin(evidence["preservation"], preservation, "Machine preservation")
                _pin(evidence["machine_binding"], binding, "Machine binding")
                continue
            if row["obligation"] == "machine_reachability_termination_and_progress":
                raise CoreProtocolError("Machine obligation requires its explicit bounded interpretation")
            extra = (prerequisite_key,) if prerequisite_key is not None else ()
            keys = {"bounded_implementation_preservation": ("preservation",), "declared_context": ("context",) + extra,
                    conjunction_stage: ("preservation", material_key, "context") + extra}
            if type(stage) is not str or stage not in keys:
                raise CoreProtocolError("Unknown original-obligation discharge stage")
            evidence = _object(row["evidence"], set(keys[stage]) | quantitative_fields, "Obligation evidence pins")
            for key in keys[stage]:
                if report[key] is None:
                    raise CoreProtocolError("Discharged obligation lacks its checked stage")
                _pin(evidence[key], report[key], "Obligation " + key)
        else:
            raise CoreProtocolError("Unknown obligation disposition")
    complete = report["all_original_obligations_discharged"]
    checked = report["status"] == accepted_status
    stages = (preservation["status"] == "checked_implementation" and report["catalog"] is not None
              and report[material_key + "_status"] == "pass" and report["context_status"] == "pass")
    if prerequisite_key is not None:
        closure = report[prerequisite_key]
        stages = (stages and closure is not None and _record(closure, "Required prerequisite closure").get("status") == "pass"
                  and report.get("prerequisite_status") == "pass")
        if not stages and any(row["status"] == "discharged" for row in rows):
            raise CoreProtocolError("Prerequisite obligations require the complete checked context chain")
    if quantitative_key is not None:
        quantitative = report.get(quantitative_key)
        stages = (stages and quantitative is not None and _record(quantitative, "Required quantitative report").get("outcome") == "pass"
                  and report.get(quantitative_key + "_status") == "pass")
    if (type(complete) is not bool or report["status"] not in (accepted_status, "not_accepted")
            or checked != (stages and all(row["status"] == "discharged" for row in rows)) or complete != checked):
        raise CoreProtocolError("Material acceptance contradicts complete stage and obligation evidence")


def _artifact(value: JsonValue, *, operation: str, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
              report: dict[str, JsonValue], limits: JsonValue,
              export_operation: str = "export-policy-material", accepted_status: str = "checked_material",
              export_schema: str = EXPORT_SCHEMA, manifest_schema: str = "biocompiler.policy_mrna_manifest.v0.1",
              request_profile: str = REQUEST_PROFILE, claim_scope: str = "bounded_conditional_policy_to_exact_mrna",
              premise: str = "supplied_model_to_sequence_and_provider_contracts") -> None:
    if operation != export_operation:
        if value is not None:
            raise CoreProtocolError("Only a fresh native export invocation may return an artifact")
        return
    if report["status"] != accepted_status:
        raise CoreProtocolError("Export returned without complete fresh material acceptance")
    artifact = _object(value, {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Fresh paired export")
    if artifact["schema_version"] != export_schema or type(artifact["fasta"]) is not str:
        raise CoreProtocolError("Export changed its exact artifact profile")
    if artifact["fasta_sha256"] != hashlib.sha256(artifact["fasta"].encode("utf-8")).hexdigest():
        raise CoreProtocolError("FASTA bytes differ from their native digest")
    _pin(artifact["manifest_sha256"], artifact["manifest"], "Complete native manifest")
    manifest = _object(artifact["manifest"], {"schema_version", "profile", "claim_scope", "premise", "request", "candidate", "limits",
        "assessment", "bindings", "members", "fasta_sha256", "empirical", "original_authority"}, "Complete native manifest")
    if any(manifest[key] != expected for key, expected in (
            ("schema_version", manifest_schema), ("profile", request_profile),
            ("claim_scope", claim_scope), ("premise", premise),
            ("empirical", "unassessed"), ("original_authority", "retain_original_inputs_separately"))):
        raise CoreProtocolError("Manifest upgraded or changed its exact export claim")
    for key, expected in (("request", request), ("candidate", candidate), ("limits", limits), ("assessment", report)):
        if not _same(manifest[key], expected):
            raise CoreProtocolError("Manifest changed complete original " + key)
    bindings = _object(manifest["bindings"], {"request_fingerprint", "candidate_fingerprint", "invocation_fingerprint", "assessment_fingerprint"}, "Manifest identity bindings")
    for key, expected in (("request_fingerprint", request), ("candidate_fingerprint", candidate),
            ("invocation_fingerprint", {"request": request, "candidate": candidate, "limits": limits}), ("assessment_fingerprint", report)):
        _pin(bindings[key], expected, "Manifest " + key)
    _artifact_members(construction=candidate["construction"], members=manifest["members"],
                      fasta=artifact["fasta"], fasta_sha256=artifact["fasta_sha256"],
                      manifest_fasta_sha256=manifest["fasta_sha256"])


def _artifact_members(*, construction: JsonValue, members: JsonValue, fasta: JsonValue,
                      fasta_sha256: JsonValue, manifest_fasta_sha256: JsonValue) -> None:
    """Validate the exact pair against checked construction data, independent of envelope."""
    construction = _record(construction, "Checked construction")
    inventory = _record(construction.get("inventory"), "Checked molecular inventory")
    molecules = _rows(inventory.get("molecules"), "Checked molecules")
    member_rows = _rows(members, "Manifest members")
    if not molecules or len(member_rows) != len(molecules) or not _same([molecule.get("id") for molecule in molecules], construction.get("member_order")):
        raise CoreProtocolError("Manifest lost the exact nonempty ordered member inventory")
    fasta_parts: list[str] = []
    for index, (raw, molecule) in enumerate(zip(member_rows, molecules), 1):
        member = _object(raw, {"fasta_id", "member_id", "molecule", "sequence_sha256"}, "Manifest member")
        fasta_id = f"rna_{index:04d}"
        sequence = molecule.get("sequence")
        if type(sequence) is not str or not sequence or any(base not in "ACGU" for base in sequence):
            raise CoreProtocolError("Checked export lacks exact RNA spelling")
        if member["fasta_id"] != fasta_id or member["member_id"] != molecule.get("id") or not _same(member["molecule"], molecule):
            raise CoreProtocolError("Manifest substituted an exact checked member")
        if member["sequence_sha256"] != hashlib.sha256(sequence.encode("utf-8")).hexdigest():
            raise CoreProtocolError("Manifest sequence hash differs from exact native sequence bytes")
        fasta_parts.append(f">{fasta_id} alphabet=RNA\n")
        fasta_parts.extend(sequence[offset:offset + 80] + "\n" for offset in range(0, len(sequence), 80))
    if fasta != "".join(fasta_parts) or manifest_fasta_sha256 != fasta_sha256:
        raise CoreProtocolError("FASTA and manifest do not represent the same exact checked member pair")


@dataclass(frozen=True)
class PolicyMaterialResult:
    """Immutable evidence; only a fresh export call produces paired native bytes."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    request_fingerprint: str
    candidate_fingerprint: str
    invocation_fingerprint: str
    report_fingerprint: str
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def candidate(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["candidate"])

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["report"])

    @property
    def artifact(self) -> dict[str, JsonValue] | None:
        return cast(dict[str, JsonValue] | None, self.result["artifact"])

    @property
    def status(self) -> str:
        return cast(str, self.report["status"])


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyMaterialResult:
    result = _object(response.result, _RESULT_FIELDS, "Material result")
    if any(result[key] != expected for key, expected in (("schema_version", RESULT_SCHEMA), ("implementation", IMPLEMENTATION),
            ("resource_profile", RESOURCE_PROFILE), ("validation_scope", VALIDATION_SCOPE))):
        raise CoreProtocolError("Material result changed its negotiated profile")
    request = _original(payload["request"])
    candidate = _object(result["candidate"], _CANDIDATE_FIELDS, "Complete material candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA or "candidate" in payload and not _same(candidate, payload["candidate"]):
        raise CoreProtocolError("Material checking changed the complete supplied candidate")
    report = _object(result["report"], _REPORT_FIELDS, "Complete material assessment")
    if any(report[key] != expected for key, expected in (("schema_version", REPORT_SCHEMA), ("profile", REQUEST_PROFILE),
            ("implementation", "biocompiler.ocaml.policy_material_check.v0.1"), ("resource_profile", RESOURCE_PROFILE),
            ("claim_scope", "bounded_conditional_policy_to_exact_mrna"), ("premise", "supplied_model_to_sequence_and_provider_contracts"),
            ("empirical", "unassessed"), ("artifact", "withheld"), ("export", "withheld"))):
        raise CoreProtocolError("Material report changed its conditional claim scope")
    request_hash = _pin(result["request_fingerprint"], request, "Complete original material request")
    candidate_hash = _pin(result["candidate_fingerprint"], candidate, "Complete material candidate")
    invocation_hash = _pin(result["invocation_fingerprint"], {"request": request, "candidate": candidate, "limits": payload["limits"]}, "Complete material invocation")
    report_hash = _pin(result["report_fingerprint"], report, "Complete material report")
    if report["request_fingerprint"] != request_hash:
        raise CoreProtocolError("Material report changed original request identity")
    _pin(report["candidate_fingerprint"], candidate, "Checker candidate")
    _pin(report["invocation_fingerprint"], {"request": request, "candidate": candidate, "limits": payload["limits"]}, "Checker invocation")
    if not _same(report["limits"], payload["limits"]) or not _same(report["budgets"], request["budgets"]):
        raise CoreProtocolError("Material checking changed original budgets or preservation limits")
    usage = _object(report["usage"], {"unit", "charged_work", "request_decoding_work"}, "Material work accounting")
    if (usage["unit"] != "logical_data_visits_and_child_semantic_work"
            or _count(usage["charged_work"], "Material work") < _count(usage["request_decoding_work"], "Request decoding work")):
        raise CoreProtocolError("Material accounting omitted request decoding or changed its unit")
    budgets = _record(request["budgets"], "Original material budgets")
    if _count(usage["charged_work"], "Material work") > _count(budgets.get("max_work"), "Original maximum work"):
        raise CoreProtocolError("Material report exceeds the original work budget")
    _preservation(response, request, candidate, report, payload["limits"])
    _leaves(request, candidate, report)
    _obligations(report)
    _artifact(result["artifact"], operation=response.operation, request=request, candidate=candidate, report=report, limits=payload["limits"])
    if response.operation == "replay-policy-material" and not _same(result, payload["report"]):
        raise CoreProtocolError("Fresh replay differs from the complete retained material wrapper")
    _publication(report, _count(budgets.get("max_report_bytes"), "Original report byte ceiling"),
                 _count(budgets.get("max_report_nodes"), "Original report node ceiling"))
    _publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyMaterialResult(response.request_id, response.operation, response.executable,
                                request_hash, candidate_hash, invocation_hash, report_hash, encode_json(result))


def _publication(raw: JsonValue, maximum_bytes: int, maximum_nodes: int) -> None:
    pending = [raw]
    nodes = 0
    while pending:
        value = pending.pop()
        nodes += 1
        if type(value) is dict:
            nodes += len(value)
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        if nodes + len(pending) > maximum_nodes:
            raise CoreProtocolError("Complete material evidence exceeds its declared node bound")
    if len(encode_json(raw)) > maximum_bytes:
        raise CoreProtocolError("Complete material evidence exceeds its declared publication bound")


@dataclass(frozen=True)
class PolicyMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyMaterialResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _original(snapshot["request"])
        if operation == "compile-policy-material" and self.transport.role != "core":
            raise CoreProtocolError("Material production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if not _same(capabilities.profiles.get("policy_material"), PROFILE) or VALIDATION_SCOPE not in capabilities.validation_scopes:
            raise CoreProtocolError("Selected executable lacks the exact material profile")
        if operation == "compile-policy-material" and not _same(capabilities.profiles.get("policy_material_producer"), PRODUCER_PROFILE):
            raise CoreProtocolError("Selected executable lacks the exact material producer profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def compile(self, request: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
        return self._call("compile-policy-material", {"request": request, "limits": limits}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
        return self._call("check-policy-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
        return self._call("replay-policy-material", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
        """Freshly check original inputs and return the native FASTA/manifest pair."""
        return self._call("export-policy-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)
