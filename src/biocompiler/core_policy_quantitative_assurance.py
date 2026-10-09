"""Fresh native assurance transport. Response views are never proof capabilities.

The unchanged material assessment is validated against its original authority;
optional numerical and experimental reports keep separate conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, cast

from . import _policy_coupled_wire as coupled_wire
from . import core_policy_component_material as component
from . import core_policy_material as material
from . import core_policy_operational as operational
from . import core_policy_refinement as exact
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json

REQUEST_SCHEMA = "biocompiler.policy_quantitative_assurance_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_quantitative_assurance.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_quantitative_assurance.v1"
REPORT_SCHEMA = "biocompiler.policy_quantitative_assurance_assessment.v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_quantitative_assurance.v0.1"
VALIDATION_SCOPE = "policy-quantitative-assurance-v0.1"
MAX_WORK = 134_217_728
MAX_RESULT_BYTES = component.MAX_RESULT_BYTES
MAX_RESULT_NODES = component.MAX_RESULT_NODES
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-quantitative-assurance", "replay-policy-quantitative-assurance", "export-policy-quantitative-assurance"],
    "schema_version": RESULT_SCHEMA, "request_schema": REQUEST_SCHEMA, "implementation": IMPLEMENTATION,
    "validation_scope": VALIDATION_SCOPE, "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "fresh_exact_mrna_with_separate_assurance", "empirical": "unassessed",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {**PROFILE, "operations": ["compile-policy-quantitative-assurance"]}
_REQUEST_FIELDS = {"schema_version", "profile", "material_request", "approximation", "realization_evidence", "max_work"}
_RESULT_FIELDS = {"schema_version", "implementation", "validation_scope", "request_fingerprint", "candidate_fingerprint",
                  "invocation_fingerprint", "report_fingerprint", "candidate", "report", "artifact"}
_REPORT_FIELDS = {"schema_version", "request_fingerprint", "candidate_fingerprint", "invocation_fingerprint", "material",
                  "exact_refinement", "approximation", "realization_evidence", "export_permitted", "empirical_function"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _request(value: JsonValue) -> dict[str, JsonValue]:
    material._publication(value, 8_388_608, 250_000)
    request = _object(value, _REQUEST_FIELDS, "Complete assurance request")
    _require(request["schema_version"] == REQUEST_SCHEMA and request["profile"] == REQUEST_PROFILE,
             "Unknown quantitative assurance request profile")
    work = request["max_work"]
    _require(type(work) is int and 0 < work <= MAX_WORK, "Assurance work must lower its positive fixed ceiling")
    component._original(request["material_request"])
    for key, schema in (("approximation", "biocompiler.policy_approximation_contract.v0.1"),
                        ("realization_evidence", "biocompiler.policy_realization_evidence_contract.v0.1")):
        value = request[key]
        _require(value is None or type(value) is dict and value.get("schema_version") == schema,
                 "Optional assurance contract changed its schema")
    return request


def _material_report(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                     raw: JsonValue, limits: JsonValue) -> dict[str, JsonValue]:
    report = component._report(raw, instanced=component._instanced(request), prerequisites=component._prerequisites(request),
        two_observations=component._two_observations(request), multi_member=component._multi_member(request),
        grounded_helper=component._grounded_helper(request), finite_machine=component._finite_machine(request),
        quantitative=component._quantitative(request), network=component._network(request), multi_site=component._multi_site(request),
        transfer_pair=component._transfer_pair(request), transfer_network=component._transfer_network(request), composition=component._composition(request))
    component._assessment(response, request, candidate, report, limits)
    return report


def _optional_reports(request: dict[str, JsonValue], report: dict[str, JsonValue], accepted: bool) -> bool:
    from .policy import approximation, realization_evidence
    allowed = accepted
    for key in ("approximation", "realization_evidence"):
        contract, raw = request[key], report[key]
        if contract is None or not accepted:
            _require(raw is None, "Unrequested or materially rejected assurance published a child report")
            continue
        child = component._record(raw, "Fresh " + key + " assessment")
        operational._pin(child.get("contract_fingerprint"), contract, "Complete " + key + " authority")
        if key == "approximation":
            approximation.validate_assessment(raw, contract, request["material_request"], report["material"])
            _require(child.get("outcome") in ("pass", "fail"), "Unknown approximation outcome")
            allowed = allowed and child["outcome"] == "pass"
        else:
            realization_evidence.validate_assessment(raw, contract, request["material_request"], report["material"])
            _require(child.get("status") in ("supported", "incompatible", "unassessed"), "Unknown empirical compatibility status")
            original = component._record(contract, "Original realization evidence contract")
            _require(type(original.get("require_compatibility")) is bool, "Evidence compatibility requirement must be explicit")
            allowed = allowed and (not original["require_compatibility"] or child["status"] == "supported")
    return allowed


def _artifact(value: JsonValue, *, operation: str, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
              report: dict[str, JsonValue], limits: JsonValue) -> None:
    if operation != "export-policy-quantitative-assurance":
        _require(value is None, "Only fresh export may publish an artifact")
        return
    _require(report["export_permitted"] is True, "Withheld assurance cannot export")
    coupled = component._composition(component._record(request["material_request"], "Original material request"))
    same = component._document_same if coupled else operational._same
    pin = component._document_pin if coupled else operational._pin
    artifact = _object(value, {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Assurance export")
    _require(artifact["schema_version"] == "biocompiler.policy_quantitative_assurance_export.v0.1", "Unknown assurance export")
    manifest = _object(artifact["manifest"], {"schema_version", "request", "limits", "assessment", "assessment_fingerprint",
        "material_manifest", "material_manifest_sha256", "fasta_sha256", "claim_scope", "empirical_function", "original_authority"},
        "Complete assurance manifest")
    _require(manifest["schema_version"] == "biocompiler.policy_quantitative_assurance_manifest.v0.1"
        and manifest["claim_scope"] == "exact_material_and_scoped_mathematical_assurance_with_separate_supplied_evidence"
        and manifest["empirical_function"] == "unassessed" and manifest["original_authority"] == "retain_original_inputs_separately",
        "Assurance export changed its claim boundary")
    for key, original in (("request", request), ("limits", limits), ("assessment", report)):
        _require(same(manifest[key], original), "Assurance export changed original " + key)
    pin(manifest["assessment_fingerprint"], report, "Exported assurance assessment")
    pin(artifact["manifest_sha256"], manifest, "Complete assurance manifest")
    _require(manifest["fasta_sha256"] == artifact["fasta_sha256"], "Assurance manifest changed exact RNA identity")
    original_request = component._original(request["material_request"])
    # Validate the retained original material artifact using its original schema.
    # No child operation or PASS is fabricated: these are actual manifest fields.
    child: JsonValue = {"schema_version": component.EXPORT_SCHEMA, "fasta": artifact["fasta"],
        "fasta_sha256": artifact["fasta_sha256"], "manifest": manifest["material_manifest"],
        "manifest_sha256": manifest["material_manifest_sha256"]}
    material._artifact(child, operation="export-policy-component-material", request=original_request, candidate=candidate,
        report=component._record(report["material"], "Material assessment"), limits=limits,
        export_operation="export-policy-component-material", accepted_status=component.ACCEPTED_STATUS,
        export_schema=component.EXPORT_SCHEMA, manifest_schema=component.MANIFEST_SCHEMA,
        request_profile=cast(str, original_request["profile"]), claim_scope=component.CLAIM_SCOPE, premise=component.PREMISE,
        document_encoder=coupled_wire.canonical_bytes if coupled else encode_json)


@dataclass(frozen=True, slots=True)
class PolicyQuantitativeAssuranceResult:
    """Immutable response snapshot. Export always requires a fresh native call."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return component._stored_result(self._result_json)

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["report"])

    @property
    def candidate(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["candidate"])

    @property
    def export_permitted(self) -> bool:
        return self.report["export_permitted"] is True


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyQuantitativeAssuranceResult:
    result = _object(response.result, _RESULT_FIELDS, "Quantitative assurance response")
    _require(result["schema_version"] == RESULT_SCHEMA and result["implementation"] == IMPLEMENTATION
        and result["validation_scope"] == VALIDATION_SCOPE, "Assurance changed its negotiated profile")
    request = _request(payload["request"])
    original = component._original(request["material_request"])
    coupled = component._composition(original)
    pin = component._document_pin if coupled else operational._pin
    same = component._document_same if coupled else operational._same
    material._publication({"result": coupled_wire.pack(result) if coupled else result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    candidate = component._candidate(result["candidate"], instanced=component._instanced(original),
        multi_member=component._multi_member(original), grounded_helper=component._grounded_helper(original),
        multi_site=component._multi_site(original))
    if coupled:
        material._publication(candidate, 8_388_608, 250_000)
    _require("candidate" not in payload or operational._same(candidate, payload["candidate"]), "Assurance changed supplied candidate")
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": payload["limits"]}
    report = _object(result["report"], _REPORT_FIELDS, "Complete assurance assessment")
    for key, value in (("request_fingerprint", request), ("candidate_fingerprint", candidate), ("invocation_fingerprint", invocation)):
        pin(result[key], value, "Assurance " + key)
        _require(report[key] == result[key], "Nested assurance assessment changed its invocation")
    pin(result["report_fingerprint"], report, "Complete assurance assessment")
    _require(report["schema_version"] == REPORT_SCHEMA and report["empirical_function"] == "unassessed",
        "Mathematical assurance acquired an empirical function claim")
    checked = _material_report(response, original, candidate, report["material"], payload["limits"])
    accepted = checked["status"] == component.ACCEPTED_STATUS
    _require((report["exact_refinement"] is not None) == accepted, "Exact evidence contradicts material acceptance")
    if accepted:
        exact._bindings(exact._evidence(report["exact_refinement"]), original, candidate, checked, payload["limits"])
    allowed = _optional_reports(request, report, accepted)
    _require(type(report["export_permitted"]) is bool and report["export_permitted"] == allowed,
        "Assurance export does not conjoin every requested acceptance requirement")
    _artifact(result["artifact"], operation=response.operation, request=request, candidate=candidate, report=report, limits=payload["limits"])
    if response.operation == "replay-policy-quantitative-assurance":
        _require(same(result, payload["report"]), "Fresh assurance replay differs from retained complete result")
    return PolicyQuantitativeAssuranceResult(response.request_id, response.operation, response.executable,
        component._result_bytes(result, coupled=coupled))


@dataclass(frozen=True)
class PolicyQuantitativeAssuranceClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyQuantitativeAssuranceResult:
        raw = component._record(payload["request"], "Original assurance request")
        coupled = component._record(raw.get("material_request"), "Original material request").get("profile") == component.COMPOSITION_REQUEST_PROFILE
        snapshot = cast(dict[str, JsonValue], coupled_wire.snapshot(payload) if coupled else decode_json(encode_json(payload)))
        _request(snapshot["request"])
        if coupled and "candidate" in snapshot:
            material._publication(snapshot["candidate"], 8_388_608, 250_000)
        producing = operation == "compile-policy-quantitative-assurance"
        _require(not producing or self.transport.role == "core", "Assurance production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if coupled:
            component._wire_capability(capabilities.profiles, self.transport.role)
        _require(operational._same(capabilities.profiles.get("policy_quantitative_assurance"), PROFILE)
            and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks exact quantitative assurance profile")
        if producing:
            _require(operational._same(capabilities.profiles.get("policy_quantitative_assurance_producer"), PRODUCER_PROFILE),
                     "Selected producer lacks exact assurance production profile")
        wire = coupled_wire.pack(snapshot) if coupled else snapshot
        response = self.transport.call(operation, wire, cancelled=cancelled)
        return _result(component._wire_response(response, coupled=coupled), snapshot)

    def compile(self, request: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
        return self._call("compile-policy-quantitative-assurance", {"request": request, "limits": limits}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
        return self._call("check-policy-quantitative-assurance", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
        return self._call("replay-policy-quantitative-assurance", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
        return self._call("export-policy-quantitative-assurance", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)


__all__ = ["PolicyQuantitativeAssuranceClient", "PolicyQuantitativeAssuranceResult"]
