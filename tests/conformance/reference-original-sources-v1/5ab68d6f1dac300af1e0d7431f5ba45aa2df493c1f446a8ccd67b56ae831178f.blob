"""Strict Core-only transport for native synthetic record helper operations.

Complete caller-owned authority is frozen before negotiation. Returned native
computations retain their full receipt, exact resource/scope declaration and all
input/value identities; no Python semantic constructor or fallback executes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, cast

from biocompiler.core_client import (
    LIMITS, CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse,
    JsonValue, _object, decode_json, encode_json,
)

_PROFILE_JSON = '{"authority_encoding":"python-json-v1","check_result_queries":["coverage","freshness"],"claim_scope":"Fresh structural import and named helper computation over complete supplied historical authority only. Dependency freshness means equality of supplied snapshots; registry selection is freshly recomputed. No current whole-program acceptance, package/export acceptance, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"fingerprints":"sha256_complete_canonical_utf8_payload_each_supplied_input_and_value_no_omissions","freshness_fields":["changed_dependencies","fresh","status"],"implementation":"biocompiler.ocaml.synthetic_inspection_service.v0.1","limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"operations":["inspect-synthetic-mechanism","inspect-synthetic-check-result","compare-synthetic-dependencies","lock-synthetic-registry","resolve-synthetic-registry","select-synthetic-registry","verify-synthetic-registry-selection","inspect-synthetic-registry-selection"],"payload_fields":{"compare-synthetic-dependencies":["profile","limits","previous","current"],"inspect-synthetic-check-result":["profile","limits","record","query","current"],"inspect-synthetic-mechanism":["profile","limits","mechanism"],"inspect-synthetic-registry-selection":["profile","limits","selection"],"lock-synthetic-registry":["profile","limits","registry","instances"],"resolve-synthetic-registry":["profile","limits","registry","lock"],"select-synthetic-registry":["profile","limits","registry","request"],"verify-synthetic-registry-selection":["profile","limits","registry","request","selection"]},"profile":"biocompiler.core.synthetic_inspection.v1","resources":{"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_inspection.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_value_complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_inspection_payload","work_accounting":"one_ancestor_for_framing_bounded_import_helpers_replay_hashes_and_final_publication"},"selection":{"ancestor":"same_inspection_request_ancestor","max_components":10000,"profile":"biocompiler.component_selection_producer.resources.v1"},"structural_import":{"comparison_accounting":"complete_import_bytes_plus_bounded_pairwise_identifier_bytes","precharged_byte_multiplier":128,"retention":"all_supplied_json_values_and_object_keys_plus_resolved_component_occurrences"}},"result_fields":["schema_version","profile","service_implementation","operation","resources","validation_scope","claim_scope","supplied_authority_fingerprint","input_fingerprints","value","value_fingerprint"],"result_schema":"biocompiler.core.synthetic_inspection_result.v1","role":"bioc-core","validation_scope":"supplied-synthetic-authority-helper-inspection-only-v1","value_fields":{"compare-synthetic-dependencies":["changed_dependencies"],"inspect-synthetic-check-result":["exercised_requirement_ids","freshness"],"inspect-synthetic-mechanism":["nodes"],"inspect-synthetic-registry-selection":["outcome"],"lock-synthetic-registry":["lock"],"resolve-synthetic-registry":["instances"],"select-synthetic-registry":["selection","outcome"],"verify-synthetic-registry-selection":["valid"]},"verify_selection_null":"false_after_structural_registry_and_request_import_without_selection_replay","wire_encoding":"python-json-v1"}'
PROFILE: dict[str, Any] = json.loads(_PROFILE_JSON)
OPERATIONS: tuple[str, ...] = tuple(PROFILE["operations"])
VALIDATION_SCOPE = "supplied-synthetic-authority-helper-inspection-only-v1"
VALIDATION_SCOPES = (VALIDATION_SCOPE,)
PROFILES = {"synthetic_inspection": PROFILE}


def capability_profile() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_PROFILE_JSON))


def _encoded(value: JsonValue) -> bytes:
    return encode_json(value, limit=LIMITS["max_response_bytes"])


def _same(left: JsonValue, right: JsonValue) -> bool:
    return _encoded(left) == _encoded(right)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record(value: JsonValue, fields: set[str], label: str) -> dict[str, Any]:
    return cast(dict[str, Any], _object(value, fields, label))


def _limits(limits: JsonValue) -> dict[str, int]:
    defaults = cast(dict[str, int], capability_profile()["default_limits"])
    if limits is None:
        return defaults
    reduced = _object(limits, set(defaults), "Synthetic inspection limits")
    if any(type(reduced[key]) is not int or not 0 < cast(int, reduced[key]) <= maximum
           for key, maximum in defaults.items()):
        raise CoreProtocolError("Synthetic inspection limits must be positive integer reductions")
    return {key: cast(int, reduced[key]) for key in defaults}


def effective_resources(limits: JsonValue = None) -> dict[str, Any]:
    controls = _limits(limits)
    def visit(value: JsonValue) -> JsonValue:
        if type(value) is dict:
            return {key: controls[key] if key in controls else visit(item) for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value
    return cast(dict[str, Any], visit(capability_profile()["resources"]))


def _negotiate(capabilities: CoreCapabilities) -> None:
    profile = capability_profile()
    if (not set(profile["operations"]) <= set(capabilities.operations)
            or not _same(capabilities.profiles.get("synthetic_inspection"), profile)
            or profile["validation_scope"] not in capabilities.validation_scopes):
        raise CoreProtocolError("Incompatible synthetic inspection operations, resources or scope")


def _strings(value: JsonValue, label: str) -> None:
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        raise CoreProtocolError("Native synthetic inspection requires " + label + " as complete string identifiers")


# Wire structure only: these inventories do not construct domain objects or
# reproduce native ordering, compatibility, ranking, or acceptance decisions.
_SHAPES: dict[str, tuple[str, dict[str, str]]] = {
    "_type": ("kind name", {"dimensions": "{}int", "arguments": "[]_type"}),
    "_node": ("id kind", {"output": "observable.v0.1", "inputs": "[]str", "attributes": "object", "requirement_ids": "[]str"}),
    "observable.v0.1": ("id role scope compartment", {"dtype": "_type"}),
    "component_lock.v0.1": ("node_id component_id version content_fingerprint", {}),
    "component_registry_lock.v0.1": ("registry_id registry_version registry_fingerprint", {"components": "[]component_lock.v0.1", "identities": "[]component_identity.v0.1"}),
    "component_selection_result.v0.2": ("registry_fingerprint request_fingerprint", {"selected": "?component_lock.v0.1", "alternatives": "[]component_selection_alternative.v0.1", "admission": "admission_assessment.v0.1"}),
    "component_selection_alternative.v0.1": ("component_id version content_fingerprint status", {"reasons": "[]str", "preference_rank": "?int"}),
    "admission_assessment.v0.1": ("request_fingerprint target_fingerprint intended_use boundary decision policy human_therapeutic_admission claim_scope evidence_status", {"diagnostics": "[]str", "component_fingerprints": "[]str", "evidence": "[]target_evidence.v0.1"}),
    "target_evidence.v0.1": ("id system source_context locator limitations", {"source": "component_identity.v0.1", "taxon_id": "?int"}),
    "component_record.v0.2": ("id version classification implementation_role", {"supported_targets": "[]str", "ports": "[]component_port.v0.2", "supported_domain": "component_operating_domain.v0.1", "identities": "[]component_identity.v0.1", "assumptions": "[]str", "guarantees": "[]str", "evidence": "[]component_identity.v0.1", "parameters": "[]component_parameter.v0.1", "dependencies": "[]component_dependency.v0.1", "capabilities": "[]component_capability.v0.1", "resources": "[]component_resource_reservation.v0.1", "reference_metadata": "?component_sequence_reference.v0.1", "synthetic_model": "?synthetic_operator_model.v0.1"}),
    "component_identity.v0.1": ("id kind version content_fingerprint", {}),
    "component_parameter.v0.1": ("id method", {"value": "component_value_domain.v0.1", "source": "component_identity.v0.1"}),
    "component_dependency.v0.1": ("id capability role scope compartment", {"required": "bool"}),
    "component_capability.v0.1": ("id role scope compartment", {}),
    "component_resource_reservation.v0.1": ("id resource unit role scope compartment", {"amount": "?number", "dtype": "_type", "reusable": "bool"}),
    "component_sequence_reference.v0.1": ("artifact_class completeness", {"sequence_length": "int", "unknown_features": "[]str"}),
    "synthetic_operator_model.v0.1": ("operation output_port policy", {"attributes": "object", "input_ports": "[]str"}),
    "component_operating_domain.v0.1": ("", {"constraints": "{}component_value_domain.v0.1"}),
    "component_port.v0.2": ("id direction meaning unit role scope compartment timing", {"dtype": "_type", "initialization": "component_value_domain.v0.1", "domain": "component_value_domain.v0.1"}),
    "component_value_domain.v0.1": ("kind unit", {"dtype": "_type", "values": "[]bool", "lower": "?number", "upper": "?number", "reason": "?str"}),
}


def _structure(value: JsonValue, shape: str, label: str, depth: int = 0) -> None:
    if depth > 128:
        raise CoreProtocolError("Native synthetic record exceeds structural depth")
    if shape.startswith("?"):
        if value is not None:
            _structure(value, shape[1:], label, depth + 1)
        return
    if shape.startswith("[]") or shape.startswith("{}"):
        wanted_type = list if shape.startswith("[]") else dict
        if type(value) is not wanted_type:
            raise CoreProtocolError("Native synthetic record has invalid " + label + " collection")
        items = value.values() if isinstance(value, dict) else cast(list[JsonValue], value)
        for item in items:
            _structure(item, shape[2:], label + " member", depth + 1)
        return
    primitives = {"str": (str,), "int": (int,), "number": (int, float), "bool": (bool,), "object": (dict,)}
    if shape in primitives:
        if type(value) not in primitives[shape]:
            raise CoreProtocolError("Native synthetic record has invalid " + label + " type")
        return
    text_fields, other_fields = _SHAPES[shape]
    fields = {key: "str" for key in text_fields.split()}
    fields.update(other_fields)
    if not shape.startswith("_"):
        fields["schema_version"] = "str"
    record = _record(value, set(fields), "Native synthetic " + label)
    if not shape.startswith("_") and record["schema_version"] != "biocompiler." + shape:
        raise CoreProtocolError("Native synthetic record has invalid " + label + " schema")
    for key, child_shape in fields.items():
        _structure(record[key], child_shape, label + "/" + key, depth + 1)


def _value(operation: str, raw: JsonValue, payload: dict[str, JsonValue]) -> dict[str, Any]:
    value = _record(raw, set(capability_profile()["value_fields"][operation]), "Synthetic inspection value")
    if operation == "inspect-synthetic-mechanism":
        _structure(value["nodes"], "[]_node", "topological nodes")
    elif operation == "inspect-synthetic-check-result":
        _strings(value["exercised_requirement_ids"], "exercised requirement IDs")
        if payload["query"] == "coverage":
            if value["freshness"] is not None:
                raise CoreProtocolError("Coverage-only inspection unexpectedly granted dependency freshness")
        elif payload["query"] == "freshness":
            freshness = _record(value["freshness"], {"changed_dependencies", "fresh", "status"}, "Native dependency freshness")
            _strings(freshness["changed_dependencies"], "changed dependency IDs")
            if type(freshness["fresh"]) is not bool or freshness["status"] not in ("fresh", "stale"):
                raise CoreProtocolError("Native dependency freshness presentation is invalid")
        else:
            raise CoreProtocolError("Native result accepted an unknown check inspection query")
    elif operation == "compare-synthetic-dependencies":
        _strings(value["changed_dependencies"], "changed dependency IDs")
    elif operation == "lock-synthetic-registry":
        _structure(value["lock"], "component_registry_lock.v0.1", "registry lock")
    elif operation == "resolve-synthetic-registry":
        instances = value["instances"]
        if type(instances) is not dict or any(type(key) is not str or not key for key in instances):
            raise CoreProtocolError("Native resolved registry must retain named complete instances")
        for record in instances.values():
            _structure(record, "component_record.v0.2", "resolved component")
    elif operation == "select-synthetic-registry":
        _structure(value["selection"], "component_selection_result.v0.2", "registry selection")
    elif operation == "verify-synthetic-registry-selection":
        if type(value["valid"]) is not bool:
            raise CoreProtocolError("Native selection verification must retain a Boolean decision")
    if operation in ("select-synthetic-registry", "inspect-synthetic-registry-selection"):
        if value["outcome"] not in ("pass", "fail", "unknown", "unsupported"):
            raise CoreProtocolError("Native registry selection outcome is invalid")
    return value


@dataclass(frozen=True)
class NativeSyntheticInspection:
    request_id: str
    operation: str
    input_document: bytes
    authority_json: bytes
    receipt_json: bytes
    value_json: bytes

    @property
    def value(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.value_json))

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.receipt_json))

    @property
    def input_fingerprints(self) -> dict[str, str]:
        return cast(dict[str, str], self.receipt["input_fingerprints"])


def _result(response: CoreResponse, payload: dict[str, JsonValue], original: bytes) -> NativeSyntheticInspection:
    profile = capability_profile()
    result = _record(response.result, set(profile["result_fields"]), "Synthetic inspection result")
    for key, wanted in {"schema_version": profile["result_schema"], "profile": profile["profile"],
            "service_implementation": profile["implementation"], "operation": response.operation,
            "validation_scope": profile["validation_scope"], "claim_scope": profile["claim_scope"],
            "resources": effective_resources(payload["limits"])}.items():
        if not _same(result[key], wanted):
            raise CoreProtocolError("Synthetic inspection changed its negotiated " + key)
    expected_inputs = {key: _sha(_encoded(value)) for key, value in payload.items() if key not in ("profile", "limits")}
    if (result["supplied_authority_fingerprint"] != _sha(_encoded(payload))
            or not _same(result["input_fingerprints"], cast(JsonValue, expected_inputs))):
        raise CoreProtocolError("Synthetic inspection is bound to different complete input authority")
    value = _value(response.operation, result["value"], payload)
    value_json = _encoded(value)
    if result["value_fingerprint"] != _sha(value_json):
        raise CoreProtocolError("Synthetic inspection changed its complete value identity")
    return NativeSyntheticInspection(response.request_id, response.operation, original, _encoded(payload),
                                     _encoded(result), value_json)


@dataclass(frozen=True)
class SyntheticInspectionClient:
    core: CoreClient

    def call_document(self, operation: str, document: bytes, *, request_id: str | None = None,
                      cancelled: Callable[[], bool] | None = None) -> NativeSyntheticInspection:
        if not isinstance(self.core, CoreClient) or self.core.role != "core":
            raise CoreProtocolError("Synthetic inspection requires an explicit core executable role")
        profile = capability_profile()
        if operation not in profile["operations"]:
            raise CoreProtocolError("Unsupported synthetic inspection operation")
        if type(document) is not bytes:
            raise CoreProtocolError("Synthetic inspection requires immutable complete JSON bytes")
        payload = _record(decode_json(document, limit=LIMITS["max_request_bytes"]),
                          set(profile["payload_fields"][operation]), "Synthetic inspection payload")
        if payload["profile"] != profile["profile"]:
            raise CoreProtocolError("Unsupported synthetic inspection profile")
        _limits(payload["limits"])
        _negotiate(self.core.negotiate(operation, cancelled=cancelled))
        response = self.core.call(operation, payload, request_id=request_id, cancelled=cancelled)
        return _result(response, payload, document)

    def call(self, operation: str, *, limits: JsonValue = None, request_id: str | None = None,
             cancelled: Callable[[], bool] | None = None, **authority: JsonValue) -> NativeSyntheticInspection:
        payload: dict[str, JsonValue] = {"profile": capability_profile()["profile"], "limits": limits, **authority}
        return self.call_document(operation, encode_json(payload), request_id=request_id, cancelled=cancelled)
