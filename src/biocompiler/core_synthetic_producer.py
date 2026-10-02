"""Explicit native synthetic production, with immutable complete transport views.

The core owns generation, selection, fresh acceptance and adaptation. This
module verifies the wire contract and identity links without importing Python
semantic constructors or implementing ranking. A generated proposal is not an
accepted pipeline, and a retained record never authorizes a later export.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Literal, cast

from biocompiler.core_client import (
    LIMITS, CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse,
    JsonValue, _object, decode_json, encode_json,
)

OPERATIONS = ("generate-synthetic", "select-synthetic", "adapt-synthetic-components")
_FAMILIES = ("synthetic_generation", "synthetic_selection", "synthetic_components")
RESULT_SCHEMA = "biocompiler.core.synthetic_production.v1"
_PROFILES_JSON = '{"synthetic_components":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint"],"claim_scope":"Complete registry and composition from a freshly accepted supplied synthetic candidate and finite history only; no component linking, molecular construction, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.synthetic_components.v0.2","input_schemas":{"candidate":["biocompiler.synthetic_candidate.v0.4"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["adapt-synthetic-components"],"outcomes":["produced","unsupported"],"payload_fields":{"adapt-synthetic-components":["profile","limits","request","candidate","history","until"]},"profile":"biocompiler.core.synthetic_components.v1","record_encoding":"python-json-v1","record_fields":["registry","composition","acceptance"],"record_schema":null,"resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","resources":{"producer":{"acceptance":{"profile":"biocompiler.synthetic_candidate_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"allocation":"cumulative_ASCII_fragments_and_typed_constructors_share_work","profile":"biocompiler.synthetic_component_adapter.resources.v1","shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_and_limits","work_accounting":"single_ancestor_for_framing_import_authority_hash_production_and_publication"}},"result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"fresh-synthetic-component-adaptation-only-v1","wire_encoding":"python-json-v1"},"synthetic_generation":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","config_fingerprint"],"claim_scope":"Complete deterministic software proposal and hard-policy checking only; no finite-history acceptance, search completeness, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"implementation":"biocompiler.synthetic.generator.v0.4","input_schemas":{"config":["biocompiler.synthetic_generator_config.v0.3"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["generate-synthetic"],"outcomes":["produced","unsupported"],"payload_fields":{"generate-synthetic":["profile","limits","request","config"]},"profile":"biocompiler.core.synthetic_generation.v1","record_encoding":"python-json-v1","record_fields":null,"record_schema":"biocompiler.synthetic_candidate.v0.4","resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","resources":{"producer":{"derived_fragments":"cumulative_report_bytes_nodes_and_shared_work","profile":"biocompiler.synthetic_generator.resources.v1","shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_and_limits","work_accounting":"single_ancestor_for_framing_import_authority_hash_production_and_publication"}},"result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"deterministic-synthetic-proposal-only-v1","wire_encoding":"python-json-v1"},"synthetic_selection":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","config_fingerprint","history_ascii_fingerprint"],"claim_scope":"Complete native and de_morgan strategy proposals, hard-policy rejections, fresh finite-history checks and deterministic ranking only; no search completeness, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.synthetic_selection.v0.1","input_schemas":{"config":["biocompiler.synthetic_generator_config.v0.3"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["select-synthetic"],"outcomes":["produced","unsupported"],"payload_fields":{"select-synthetic":["profile","limits","request","config","history","until"]},"profile":"biocompiler.core.synthetic_selection.v1","record_encoding":"python-json-v1","record_fields":null,"record_schema":"biocompiler.synthetic_selection_result.v0.1","resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","resources":{"producer":{"child_retention":"remaining_aggregate_peak_retained_items","profile":"biocompiler.synthetic_selection.producer_resources.v1","publication":"all_alternatives_and_complete_result_reserved_cumulatively","shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"},"strategies":["native","de_morgan"]},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_and_limits","work_accounting":"single_ancestor_for_framing_import_authority_hash_production_and_publication"}},"result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"two-strategy-synthetic-selection-finite-history-v1","wire_encoding":"python-json-v1"}}'
PROFILES: dict[str, JsonValue] = json.loads(_PROFILES_JSON)
VALIDATION_SCOPES = tuple(cast(dict[str, Any], value)["validation_scope"] for value in PROFILES.values())
_LIMIT_FIELDS = {"max_work", "max_monitor_items", "max_request_bytes", "max_report_bytes", "max_report_nodes"}
_RESULT_FIELDS = {"schema_version", "profile", "implementation", "service_implementation",
    "resource_profile", "resources", "validation_scope", "claim_scope",
    "supplied_authority_fingerprint", "authority_identities", "outcome", "record",
    "record_fingerprint", "generation_error"}
_CANDIDATE_FIELDS = {"schema_version", "request_fingerprint", "generator_config", "mechanism",
    "observation_map", "source_map", "behavior_requirement_ids", "component_locks",
    "intended_use", "human_therapeutic_admission"}
_SELECTION_FIELDS = {"schema_version", "selection_version", "cost_version", "intended_use",
    "human_therapeutic_admission", "request_fingerprint", "history_fingerprint", "until", "config",
    "minimize", "alternatives", "selected_strategy", "outcome", "checked_candidates",
    "rejected_candidates", "search_scope"}


def _encoded(value: JsonValue) -> bytes:
    return encode_json(value, limit=LIMITS["max_response_bytes"])


def _same(left: JsonValue, right: JsonValue) -> bool:
    # Python equality collapses bool/int and int/float; wire identities do not.
    return _encoded(left) == _encoded(right)


def _hash(value: JsonValue, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise CoreProtocolError(label + " must be a lowercase SHA-256 fingerprint")
    return value


def _fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _record(value: JsonValue, fields: set[str], label: str) -> dict[str, Any]:
    return cast(dict[str, Any], _object(value, fields, label))


def capability_profile(operation: str) -> dict[str, Any]:
    """Return a defensive copy of the exact installed producer contract."""
    if type(operation) is not str or operation not in OPERATIONS:
        raise CoreProtocolError("Unknown synthetic producer operation")
    return cast(dict[str, Any], json.loads(_PROFILES_JSON)[_FAMILIES[OPERATIONS.index(operation)]])


def default_limits(operation: str) -> dict[str, int]:
    profile = capability_profile(operation)
    return cast(dict[str, int], profile["default_limits"])


def _limits(operation: str, value: JsonValue) -> dict[str, int]:
    defaults = default_limits(operation)
    if value is None:
        return defaults
    fields = _object(value, _LIMIT_FIELDS, "Synthetic producer limits")
    if any(type(fields[key]) is not int or not 0 < cast(int, fields[key]) <= maximum
           for key, maximum in defaults.items()):
        raise CoreProtocolError("Synthetic producer limits must be positive integer reductions")
    return {key: cast(int, fields[key]) for key in defaults}


def effective_resources(operation: str, limits: JsonValue = None) -> dict[str, Any]:
    reduced = _limits(operation, limits)
    def visit(value: JsonValue) -> JsonValue:
        if type(value) is dict:
            return {key: reduced[key] if key in reduced else visit(item) for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value
    return cast(dict[str, Any], visit(capability_profile(operation)["resources"]))


def _negotiate(capabilities: CoreCapabilities, operation: str) -> None:
    family = _FAMILIES[OPERATIONS.index(operation)]
    profile = capability_profile(operation)
    if (not _same(capabilities.profiles.get(family), profile)
            or any(item not in capabilities.operations for item in OPERATIONS)
            or profile["validation_scope"] not in capabilities.validation_scopes):
        raise CoreProtocolError("Incompatible synthetic producer profile, operations, resources or scope")


def _payload(operation: str, value: JsonValue) -> dict[str, Any]:
    fields = {"profile", "limits", "request"}
    fields |= {"candidate", "history", "until"} if operation == OPERATIONS[2] else {"config"}
    if operation == OPERATIONS[1]:
        fields |= {"history", "until"}
    payload = _record(value, fields, "Synthetic producer payload")
    if payload["profile"] != capability_profile(operation)["profile"]:
        raise CoreProtocolError("Synthetic producer payload profile differs")
    _limits(operation, payload["limits"])
    return payload


def _error(value: JsonValue) -> None:
    error = _record(value, {"message", "node_id", "source", "formatted"}, "Generator Unsupported detail")
    if type(error["message"]) is not str or not error["message"]:
        raise CoreProtocolError("Generator Unsupported message must be nonempty text")
    node = error["node_id"]
    if node is not None and (type(node) is not str or not node):
        raise CoreProtocolError("Generator Unsupported node must be text or null")
    formatted = error["message"] + (" [" + node + "]" if node is not None else "")
    if error["source"] is not None:
        source = _record(error["source"], {"file", "line", "function"}, "Generator Unsupported source")
        if (any(type(source[key]) is not str or not source[key] for key in ("file", "function"))
                or type(source["line"]) is not int or source["line"] < 1):
            raise CoreProtocolError("Generator Unsupported source fields are invalid")
        formatted += " at " + source["file"] + ":" + str(source["line"])
    if error["formatted"] != formatted:
        raise CoreProtocolError("Generator Unsupported formatted text differs from its complete detail")


def _candidate(value: JsonValue, request_fingerprint: str) -> dict[str, Any]:
    record = _record(value, _CANDIDATE_FIELDS, "Synthetic candidate")
    if (record["schema_version"] != "biocompiler.synthetic_candidate.v0.4"
            or record["request_fingerprint"] != request_fingerprint
            or record["intended_use"] != "software_test"
            or record["human_therapeutic_admission"] != "not_admitted"):
        raise CoreProtocolError("Synthetic candidate schema, authority or scope differs")
    return record


def _record_links(operation: str, value: JsonValue, identities: dict[str, Any], payload: dict[str, Any]) -> None:
    request = identities["request_fingerprint"]
    if operation == OPERATIONS[0]:
        record = _candidate(value, request)
        if _fingerprint(record["generator_config"]) != identities["config_fingerprint"]:
            raise CoreProtocolError("Generated candidate differs from the effective configuration")
    elif operation == OPERATIONS[1]:
        record = _record(value, _SELECTION_FIELDS, "Synthetic selection")
        if (record["schema_version"] != "biocompiler.synthetic_selection_result.v0.1"
                or record["selection_version"] != "biocompiler.synthetic.selection.v0.1"
                or record["cost_version"] != "biocompiler.synthetic.gate_count.v0.1"
                or record["search_scope"] != "two_whole_program_conjunction_strategies"
                or record["request_fingerprint"] != request
                or record["history_fingerprint"] != identities["history_ascii_fingerprint"]
                or _fingerprint(record["config"]) != identities["config_fingerprint"]
                or not _same(record["until"], payload["until"])
                or record["intended_use"] != "software_test"
                or record["human_therapeutic_admission"] != "not_admitted"):
            raise CoreProtocolError("Synthetic selection schema, authority or scope differs")
        # Retain every alternative and its native decision. Do not rerank or
        # promote an imported candidate/check to fresh Python acceptance.
        if type(record["alternatives"]) is not list or len(record["alternatives"]) != 2:
            raise CoreProtocolError("Synthetic selection must retain both strategy alternatives")
        for strategy, alternative in zip(("native", "de_morgan"), record["alternatives"]):
            item = _record(alternative, {"schema_version", "strategy", "candidate", "constraint_violations",
                "check", "generation_error", "gate_count", "status"}, "Synthetic alternative")
            if (item["schema_version"] != "biocompiler.synthetic_alternative.v0.1"
                    or item["strategy"] != strategy
                    or item["gate_count"] is not None and (type(item["gate_count"]) is not int or item["gate_count"] < 0)):
                raise CoreProtocolError("Synthetic alternative schema, strategy or gate count differs")
            if item["candidate"] is not None:
                _candidate(item["candidate"], request)
        for key in ("checked_candidates", "rejected_candidates"):
            if type(record[key]) is not int or record[key] < 0:
                raise CoreProtocolError("Synthetic selection counts must be nonnegative integers")
    else:
        record = _record(value, {"registry", "composition", "acceptance"}, "Synthetic component adaptation")
        if any(type(record[key]) is not dict for key in record):
            raise CoreProtocolError("Adaptation must retain registry, composition and acceptance records")
        acceptance = record["acceptance"]
        dependencies = acceptance.get("dependencies")
        if (acceptance.get("schema_version") != "biocompiler.realization_check.v0.1"
                or acceptance.get("outcome") != "pass" or type(dependencies) is not dict):
            raise CoreProtocolError("Adaptation must retain its complete passing finite-history acceptance")
        settings = dependencies.get("settings")
        horizon = dependencies.get("horizon")
        if (type(settings) is not dict or type(horizon) is not dict
                or settings.get("realization_request") != request
                or settings.get("synthetic_candidate") != identities["candidate_fingerprint"]
                or dependencies.get("history") != identities["history_ascii_fingerprint"]
                or not _same(horizon.get("until"), payload["until"])):
            raise CoreProtocolError("Adaptation acceptance differs from its request, candidate, history or horizon")


@dataclass(frozen=True)
class NativeSyntheticProduction:
    """Complete native result; Unsupported detail remains structured and lossless."""
    request_id: str
    operation: str
    profile: str
    outcome: Literal["produced", "unsupported"]
    record_json: bytes | None
    record_fingerprint: str | None
    input_document: bytes
    authority_json: bytes
    receipt_json: bytes

    @property
    def record(self) -> dict[str, Any] | None:
        return None if self.record_json is None else cast(dict[str, Any], decode_json(self.record_json))

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.receipt_json))

    @property
    def authority_identities(self) -> dict[str, str]:
        return cast(dict[str, str], self.receipt["authority_identities"])

    @property
    def generation_error(self) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self.receipt["generation_error"])


def _result(response: CoreResponse, payload: dict[str, Any], input_document: bytes) -> NativeSyntheticProduction:
    operation = response.operation
    profile = capability_profile(operation)
    receipt = _record(response.result, _RESULT_FIELDS, "Synthetic production receipt")
    for key in ("profile", "implementation", "service_implementation", "resource_profile", "validation_scope", "claim_scope"):
        if not _same(receipt[key], profile[key]):
            raise CoreProtocolError("Synthetic production receipt changed its negotiated " + key)
    if (receipt["schema_version"] != RESULT_SCHEMA
            or receipt["supplied_authority_fingerprint"] != _fingerprint(payload)
            or not _same(receipt["resources"], effective_resources(operation, payload["limits"]))):
        raise CoreProtocolError("Synthetic production receipt changed authority, schema or effective resources")
    fields = {"request_fingerprint", "request_artifact_fingerprint"}
    fields |= {"candidate_fingerprint", "history_ascii_fingerprint"} if operation == OPERATIONS[2] else {"config_fingerprint"}
    if operation == OPERATIONS[1]:
        fields.add("history_ascii_fingerprint")
    identities = _record(receipt["authority_identities"], fields, "Synthetic producer authority identities")
    for key in fields:
        _hash(identities[key], key)
    outcome = receipt["outcome"]
    if outcome == "unsupported":
        if receipt["record"] is not None or receipt["record_fingerprint"] is not None:
            raise CoreProtocolError("Unsupported generation cannot retain a produced record")
        _error(receipt["generation_error"])
        data, fingerprint = None, None
    elif outcome == "produced":
        if receipt["generation_error"] is not None:
            raise CoreProtocolError("Produced record cannot retain a generation error")
        _record_links(operation, receipt["record"], identities, payload)
        data = _encoded(receipt["record"])
        fingerprint = _hash(receipt["record_fingerprint"], "Produced record")
        if hashlib.sha256(data).hexdigest() != fingerprint:
            raise CoreProtocolError("Complete synthetic production record fingerprint differs")
    else:
        raise CoreProtocolError("Unknown synthetic production outcome")
    return NativeSyntheticProduction(response.request_id, operation, profile["profile"], outcome,
        data, fingerprint, input_document, _encoded(payload), _encoded(receipt))


@dataclass(frozen=True)
class SyntheticProducerClient:
    core: CoreClient

    def _call_document(self, operation: str, document: bytes, *, request_id: str | None,
                       cancelled: Callable[[], bool] | None) -> NativeSyntheticProduction:
        if self.core.role != "core":
            raise CoreProtocolError("Synthetic production requires the core executable role")
        if type(document) is not bytes:
            raise CoreProtocolError("Synthetic producer document must be immutable bytes")
        payload = _payload(operation, decode_json(document, limit=LIMITS["max_request_bytes"]))
        _negotiate(self.core.negotiate(operation, cancelled=cancelled), operation)
        response = self.core.call(operation, payload, request_id=request_id, cancelled=cancelled)
        return _result(response, payload, document)

    def generate_document(self, document: bytes, *, request_id: str | None = None,
                          cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self._call_document(OPERATIONS[0], document, request_id=request_id, cancelled=cancelled)

    def select_document(self, document: bytes, *, request_id: str | None = None,
                        cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self._call_document(OPERATIONS[1], document, request_id=request_id, cancelled=cancelled)

    def adapt_document(self, document: bytes, *, request_id: str | None = None,
                       cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self._call_document(OPERATIONS[2], document, request_id=request_id, cancelled=cancelled)

    def generate(self, *, request: JsonValue, config: JsonValue = None, limits: JsonValue = None,
                 request_id: str | None = None, cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self.generate_document(encode_json({"profile": capability_profile(OPERATIONS[0])["profile"],
            "limits": limits, "request": request, "config": config}), request_id=request_id, cancelled=cancelled)

    def select(self, *, request: JsonValue, history: JsonValue, until: JsonValue = None,
               config: JsonValue = None, limits: JsonValue = None, request_id: str | None = None,
               cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self.select_document(encode_json({"profile": capability_profile(OPERATIONS[1])["profile"],
            "limits": limits, "request": request, "config": config, "history": history, "until": until}),
            request_id=request_id, cancelled=cancelled)

    def adapt(self, *, request: JsonValue, candidate: JsonValue, history: JsonValue, until: JsonValue = None,
              limits: JsonValue = None, request_id: str | None = None,
              cancelled: Callable[[], bool] | None = None) -> NativeSyntheticProduction:
        return self.adapt_document(encode_json({"profile": capability_profile(OPERATIONS[2])["profile"],
            "limits": limits, "request": request, "candidate": candidate, "history": history, "until": until}),
            request_id=request_id, cancelled=cancelled)
