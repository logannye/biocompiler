"""Read-only native controlled-composition admission; no Python evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, cast

from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json,
)
from biocompiler.core_policy import _semantic
from biocompiler.core_policy_material import _publication
from biocompiler.core_policy_operational import _fingerprint, _pin, _same

OPERATION = "admit-policy-component-material"
VALIDATION_SCOPE = "policy-controlled-composition-admission-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_controlled_composition.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_controlled_composition_resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_controlled_composition.v1"
REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.14"
REQUEST_PROFILE = "biocompiler.policy_controlled_composition_mrna.v0.1"
SOURCE_PROFILE = "biocompiler.policy_controlled_composition_source.v0.1"
REPORT_SCHEMA = "biocompiler.policy_controlled_composition_assessment.v0.1"
MAX_RESULT_BYTES = 8_323_072
MAX_RESULT_NODES = 249_968
PROFILE: dict[str, JsonValue] = {
    "operations": [OPERATION], "request_schema": REQUEST_SCHEMA,
    "request_profile": REQUEST_PROFILE, "source_profile": SOURCE_PROFILE,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "stage": "admission", "artifact": "none", "empirical": "unassessed",
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
}
_REQUEST_FIELDS = set("schema_version profile source_authority mechanism_model operating_domain material_authority catalog_binding assembly context resources budgets".split())
_RESULT_FIELDS = set("schema_version implementation resource_profile validation_scope request_fingerprint report_fingerprint report artifact usage".split())
_REPORT_FIELDS = set("schema_version profile stage status claim_scope request_fingerprint source_fingerprint domain_fingerprint material_fingerprint authority_inventory domain_counters domain_inventory source_admission budgets construction_status behavior_status empirical_status".split())
_SOURCE_FIELDS = set("schema_version status profile document_fingerprint artifact_digest document horizon_ticks requirements correspondence execution material empirical_status context_status".split())
_DEADLINES = {"initial_activation": "onset_ticks", "controller_cessation": "controller_off_ticks",
              "antigen_cessation": "antigen_off_ticks", "component_cessation": "component_off_ticks",
              "reactivation": "reactivation_ticks"}


def _record(value: JsonValue) -> dict[str, JsonValue]:
    if type(value) is not dict:
        raise CoreProtocolError("Controlled authority must retain complete records")
    return value


def _rows(value: JsonValue) -> list[JsonValue]:
    if type(value) is not list:
        raise CoreProtocolError("Controlled authority must retain complete arrays")
    return value


def _count(value: JsonValue, maximum: int, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CoreProtocolError("Controlled admission changed an exact bounded counter")
    return value


def _original(value: JsonValue) -> dict[str, JsonValue]:
    original = _object(value, _REQUEST_FIELDS, "Complete controlled request")
    if original["schema_version"] != REQUEST_SCHEMA or original["profile"] != REQUEST_PROFILE:
        raise CoreProtocolError("Controlled request changed its closed profile")
    budgets = _object(original["budgets"], {"profile", "max_work", "max_report_bytes", "max_report_nodes"}, "Original budgets")
    if budgets["profile"] != RESOURCE_PROFILE:
        raise CoreProtocolError("Controlled request changed its budget profile")
    for key, maximum in (("max_work", 1_000_000_000), ("max_report_bytes", MAX_RESULT_BYTES), ("max_report_nodes", MAX_RESULT_NODES)):
        _count(budgets[key], maximum, 1)
    for key in _REQUEST_FIELDS - {"schema_version", "profile"}:
        _record(original[key])
    _publication(original, 4_000_000, 100_000)
    return original


def _source(value: JsonValue, authority: dict[str, JsonValue], domain: dict[str, JsonValue]) -> None:
    source = _object(value, _SOURCE_FIELDS, "Complete controlled source admission")
    expected_flags: dict[str, JsonValue] = {
        "schema_version": "biocompiler.policy_controlled_composition_source_admission.v0.1",
        "status": "source_admitted", "profile": SOURCE_PROFILE,
        "execution": "not_performed", "material": "not_performed",
        "empirical_status": "unassessed", "context_status": "supplied_not_realized",
    }
    if any(source[key] != expected for key, expected in expected_flags.items()):
        raise CoreProtocolError("Controlled source admission upgraded its claim")
    document = _record(authority.get("document"))
    if not _same(source["document"], document) or source["horizon_ticks"] != domain.get("horizon_tick"):
        raise CoreProtocolError("Controlled source admission changed original authority or horizon")
    _pin(source["artifact_digest"], document, "Exact source document")
    _pin(source["document_fingerprint"], _semantic(document), "Semantic source document")
    program = _record(document.get("program"))
    declarations = [_record(row) for row in _rows(program.get("declarations"))]
    definitions = [_record(row) for row in _rows(_record(program.get("semantics")).get("definitions"))]
    correspondence = _object(source["correspondence"], {"declarations", "definitions", "source_map"}, "Source correspondence")
    expected_declarations: JsonValue = [{"id": row.get("id"), "source_path": f"/document/program/declarations/{index}",
        "source_index": index, "kind": row.get("$type"), "original": row} for index, row in enumerate(declarations)]
    expected_definitions: list[JsonValue] = []
    for index, definition in sorted(enumerate(definitions), key=lambda item: str(item[1].get("id"))):
        expected_definitions.append({"reference": {"$type": "DefinitionRef", "id": definition.get("id"),
            "version": definition.get("version"), "digest": _fingerprint(_semantic(definition))},
            "source_path": f"/document/program/semantics/definitions/{index}", "original": definition})
    if (not _same(correspondence["declarations"], expected_declarations)
            or not _same(correspondence["definitions"], expected_definitions)
            or not _same(correspondence["source_map"], program.get("source_map"))):
        raise CoreProtocolError("Controlled correspondence changed complete original occurrences")
    deadlines = _record(_record(authority.get("control_contract")).get("requested_deadlines"))
    requirements: list[JsonValue] = []
    for index, row in enumerate(declarations):
        if row.get("$type") != "Requirement":
            continue
        contract = _record(row.get("contract"))
        matches = [body for body in definitions if body.get("id") == contract.get("id")]
        if len(matches) != 1:
            raise CoreProtocolError("Source requirement lost its unique original definition")
        clauses = _rows(matches[0].get("clauses"))
        if len(clauses) != 1:
            raise CoreProtocolError("Controlled requirement lost its exact original clause")
        marker = _record(_record(clauses[0]).get("expression")).get("value")
        prefix, suffix = "biocompiler.controlled_source.", ".v0.1"
        if type(marker) is not str or not marker.startswith(prefix) or not marker.endswith(suffix):
            raise CoreProtocolError("Controlled requirement changed its native meaning marker")
        kind = marker[len(prefix):-len(suffix)]
        if kind != "no_unauthorized_activation" and kind not in _DEADLINES:
            raise CoreProtocolError("Controlled requirement changed its admitted obligation kind")
        requirements.append({"id": row.get("id"), "kind": kind,
            "source_path": f"/document/program/declarations/{index}",
            "deadline_ticks": None if kind == "no_unauthorized_activation" else deadlines.get(_DEADLINES[kind])})
    if len(requirements) != 6 or not _same(source["requirements"], requirements):
        raise CoreProtocolError("Controlled admission changed original source obligations")


@dataclass(frozen=True)
class PolicyControlledCompositionResult:
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    request_fingerprint: str
    report_fingerprint: str
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["report"])


def _result(response: CoreResponse, original: dict[str, JsonValue]) -> PolicyControlledCompositionResult:
    if response.operation != OPERATION or response.status != "ok" or response.diagnostics:
        raise CoreProtocolError("Controlled admission requires an unambiguous native success")
    result = _object(response.result, _RESULT_FIELDS, "Controlled admission result")
    for key, expected in (("schema_version", RESULT_SCHEMA), ("implementation", IMPLEMENTATION),
                          ("resource_profile", RESOURCE_PROFILE), ("validation_scope", VALIDATION_SCOPE)):
        if result[key] != expected:
            raise CoreProtocolError("Controlled admission changed its negotiated profile")
    if result["artifact"] is not None:
        raise CoreProtocolError("Admission cannot publish a constructed artifact")
    request_fingerprint = _pin(result["request_fingerprint"], original, "Complete request")
    report_fingerprint = _pin(result["report_fingerprint"], result["report"], "Complete admission report")
    report = _object(result["report"], _REPORT_FIELDS, "Controlled admission report")
    flags: dict[str, JsonValue] = {"schema_version": REPORT_SCHEMA, "profile": REQUEST_PROFILE,
        "stage": "admission", "status": "admitted", "claim_scope": "supplied_authority_and_complete_finite_domain_only",
        "construction_status": "not_performed", "behavior_status": "not_performed", "empirical_status": "unassessed"}
    if any(report[key] != value for key, value in flags.items()):
        raise CoreProtocolError("Controlled admission upgraded its limited claim")
    authority, domain, material = (_record(original[key]) for key in ("source_authority", "operating_domain", "material_authority"))
    document = _record(authority.get("document"))
    for key, value in (("request_fingerprint", original), ("source_fingerprint", document),
                       ("domain_fingerprint", domain), ("material_fingerprint", material)):
        _pin(report[key], value, key)
    budgets = _record(original["budgets"])
    if not _same(report["budgets"], budgets):
        raise CoreProtocolError("Admission changed original publication or work budgets")
    program = _record(document.get("program"))
    model = _record(_record(original["mechanism_model"]).get("body"))
    template = _record(material.get("template"))
    originals = {"definitions": _record(program.get("semantics")).get("definitions"),
        "catalog_entries": _record(document.get("implementations")).get("implementations"),
        "model_components": model.get("components"), "model_ports": model.get("ports"),
        "members": material.get("members"), "products": _record(authority.get("control_contract")).get("products"),
        "roots": template.get("sources"), "transforms": template.get("steps"),
        "source_records": _record(authority.get("project_context")).get("sources"),
        "empirical_assertions": _record(original["context"]).get("empirical_assertions")}
    inventory = _object(report["authority_inventory"], set(originals), "Original authority inventory")
    for key, rows in originals.items():
        if _count(inventory[key], 1_000_000) != len(_rows(rows)):
            raise CoreProtocolError("Admission changed the complete original authority inventory")
    counters = _object(report["domain_counters"], {"prefixes", "transitions", "histories", "work"}, "Complete domain counters")
    limits = _record(domain.get("limits"))
    for key in counters:
        _count(counters[key], _count(limits.get("max_" + key), 16_000_000, 1), 1)
    factor_fields = {"fixed_input_count": "fixed_inputs", "physical_factor_count": "physical_factors",
                     "evidence_factor_count": "evidence_factors", "lifecycle_factor_count": "lifecycle_factors"}
    domain_inventory = _object(report["domain_inventory"], set(factor_fields), "Domain grammar inventory")
    for key, field in factor_fields.items():
        if _count(domain_inventory[key], 1_000_000) != len(_rows(domain.get(field))):
            raise CoreProtocolError("Admission changed the complete domain grammar inventory")
    _source(report["source_admission"], authority, domain)
    usage = _object(result["usage"], {"unit", "preparation_charged_work", "request_decoding_work", "publication"}, "Admission work")
    if (usage["unit"] != "logical_data_visits_and_child_semantic_work"
            or usage["publication"] != "requires_original_one_shot_frame_guard"):
        raise CoreProtocolError("Admission changed its resource accounting unit")
    total = _count(usage["preparation_charged_work"], cast(int, budgets["max_work"]), 1)
    decoding = _count(usage["request_decoding_work"], total, 1)
    if (cast(int, counters["prefixes"]) != cast(int, counters["transitions"]) + 1
            or cast(int, counters["histories"]) > cast(int, counters["transitions"])
            or cast(int, counters["work"]) > total - decoding):
        raise CoreProtocolError("Admission counters contradict complete prefix traversal or cumulative work")
    _publication(report, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))
    _publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyControlledCompositionResult(response.request_id, response.operation, response.executable,
                                             request_fingerprint, report_fingerprint, encode_json(result))


@dataclass(frozen=True)
class PolicyControlledCompositionClient:
    transport: CoreClient

    def admit(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledCompositionResult:
        original = _original(decode_json(encode_json(request)))
        capabilities = self.transport.negotiate(OPERATION, cancelled=cancelled)
        if (not _same(capabilities.profiles.get("policy_controlled_composition_admission"), PROFILE)
                or VALIDATION_SCOPE not in capabilities.validation_scopes):
            raise CoreProtocolError("Selected executable lacks the exact native controlled admission profile")
        return _result(self.transport.call(OPERATION, {"request": original}, cancelled=cancelled), original)
