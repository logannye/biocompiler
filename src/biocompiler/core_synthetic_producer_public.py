"""Strict raw transport for complete native synthetic build-request selection.

The core validates source, portability and full build authority before selection.
This client checks complete byte identities, nested receipts and resource bounds;
it constructs no semantic Python records and grants no package acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Callable, cast

from biocompiler.core_client import (
    LIMITS, CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse,
    JsonValue, _object, decode_json, encode_json,
)
from biocompiler.core_synthetic_producer import (
    NativeSyntheticProduction, _result as _production_result,
    capability_profile as _producer_profile,
)

OPERATION = "select-synthetic-build-request"
OPERATIONS = (OPERATION,)
_PROFILE_JSON = '{"authority_encoding":"python-json-v1","claim_scope":"Complete portable build request validation and two-strategy software selection with fresh finite-history checks only; no pipeline freshness, package/export acceptance, molecular construction, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"history_samples":"exact_four_field_records_no_numeric_shorthand","history_schema":"biocompiler.synthetic_history.v0.1","implementation":"biocompiler.ocaml.synthetic_producer_public_service.v0.1","limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"operations":["select-synthetic-build-request"],"payload_fields":["profile","limits","build_request"],"presentation_fields":["frame_count","exit_code"],"producer_operation":"select-synthetic","producer_profile":"biocompiler.core.synthetic_selection.v1","producer_record_schema":"biocompiler.synthetic_selection_result.v0.1","profile":"biocompiler.core.synthetic_producer_public.v1","request_schema":"biocompiler.synthetic_build_request.v0.2","resources":{"nested_producer_controls":"five_reductions_with_outer_retained_history_subtracted_before_producer_import","protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_producer_public.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_build_request_payload","work_accounting":"single_ancestor_for_framing_full_source_import_fresh_lowering_selection_and_final_publication"}},"result_schema":"biocompiler.core.synthetic_public_production.v1","role":"bioc-core","source_check_order":["realization_fresh_lowering","history","config","horizon","profile","intended_use","artifact_scope","portable_sources","run_metadata"],"validation_scope":"portable-build-authority-two-strategy-selection-only-v1","wire_encoding":"python-json-v1"}'
PROFILE: dict[str, Any] = json.loads(_PROFILE_JSON)
VALIDATION_SCOPE = "portable-build-authority-two-strategy-selection-only-v1"
_RESULT_FIELDS = {"schema_version", "profile", "service_implementation", "resources", "validation_scope", "claim_scope",
    "supplied_authority_fingerprint", "supplied_build_request_fingerprint", "build_request_fingerprint",
    "normalized_build_request", "production_payload", "production", "presentation"}
_BUILD_FIELDS = {"schema_version", "realization", "history", "until", "config", "profile", "intended_use"}


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
    reduced = _object(limits, set(defaults), "Public synthetic producer limits")
    if any(type(reduced[key]) is not int or not 0 < cast(int, reduced[key]) <= maximum
           for key, maximum in defaults.items()):
        raise CoreProtocolError("Public synthetic producer limits must be positive integer reductions")
    return {key: cast(int, reduced[key]) for key in defaults}


def effective_resources(limits: JsonValue = None) -> dict[str, Any]:
    reduced = _limits(limits)
    def visit(value: JsonValue) -> JsonValue:
        if type(value) is dict:
            return {key: reduced[key] if key in reduced else visit(item) for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value
    return cast(dict[str, Any], visit(capability_profile()["resources"]))


def _negotiate(capabilities: CoreCapabilities) -> None:
    profile = capability_profile()
    nested = _producer_profile("select-synthetic")
    if (OPERATION not in capabilities.operations or "select-synthetic" not in capabilities.operations
            or not _same(capabilities.profiles.get("synthetic_producer_public"), profile)
            or not _same(capabilities.profiles.get("synthetic_selection"), nested)
            or profile["validation_scope"] not in capabilities.validation_scopes
            or nested["validation_scope"] not in capabilities.validation_scopes):
        raise CoreProtocolError("Incompatible public synthetic producer authority, resources or nested selection capability")


@dataclass(frozen=True)
class NativeSyntheticPublicProduction:
    request_id: str
    input_build_request: bytes
    authority_json: bytes
    normalized_build_request_json: bytes
    production_payload_json: bytes
    receipt_json: bytes
    production: NativeSyntheticProduction
    frame_count: int
    exit_code: int

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.receipt_json))

    @property
    def normalized_build_request(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.normalized_build_request_json))

    @property
    def production_payload(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.production_payload_json))

    @property
    def build_request_fingerprint(self) -> str:
        return _sha(self.normalized_build_request_json)


def _result(response: CoreResponse, payload: dict[str, JsonValue], original: bytes) -> NativeSyntheticPublicProduction:
    profile = capability_profile()
    result = _record(response.result, _RESULT_FIELDS, "Public synthetic production result")
    for key, wanted in {"schema_version": profile["result_schema"], "profile": profile["profile"],
            "service_implementation": profile["implementation"], "validation_scope": profile["validation_scope"],
            "claim_scope": profile["claim_scope"], "resources": effective_resources(payload["limits"])}.items():
        if not _same(result[key], wanted):
            raise CoreProtocolError("Public synthetic producer result changed its negotiated " + key)
    normalized = _record(result["normalized_build_request"], _BUILD_FIELDS, "Normalized synthetic build authority")
    normalized_json = _encoded(normalized)
    if (result["supplied_authority_fingerprint"] != _sha(_encoded(payload))
            or result["supplied_build_request_fingerprint"] != _sha(_encoded(payload["build_request"]))
            or result["build_request_fingerprint"] != _sha(normalized_json)):
        raise CoreProtocolError("Public synthetic production is bound to different supplied or normalized authority")
    supplied = _record(payload["build_request"], _BUILD_FIELDS, "Supplied synthetic build authority")
    if (normalized["schema_version"] != profile["request_schema"]
            or normalized["intended_use"] != "software_test"
            or normalized["profile"] not in ("synthetic_realization", "synthetic_components")
            or type(normalized["until"]) not in (int, float)
            or any(not _same(normalized[key], supplied[key]) for key in _BUILD_FIELDS - {"realization"})):
        raise CoreProtocolError("Normalized synthetic build authority changed its complete controls or numeric kinds")
    history = _record(normalized["history"], {"schema_version", "frames"}, "Normalized synthetic history")
    if history["schema_version"] != profile["history_schema"] or type(history["frames"]) is not list:
        raise CoreProtocolError("Normalized synthetic history schema or frame inventory differs")
    presentation = _record(result["presentation"], {"frame_count", "exit_code"}, "Native selection presentation")
    frame_count, exit_code = presentation["frame_count"], presentation["exit_code"]
    if (type(frame_count) is not int or frame_count <= 0 or frame_count != len(history["frames"])
            or type(exit_code) is not int or exit_code not in (0, 1, 2)):
        raise CoreProtocolError("Native selection presentation has invalid frame count or exit status")
    controls = _limits(payload["limits"])
    controls["max_monitor_items"] -= frame_count
    if controls["max_monitor_items"] <= 0:
        raise CoreProtocolError("Native selection omitted the outer retained-history resource reservation")
    expected_production: dict[str, JsonValue] = {"profile": profile["producer_profile"], "limits": cast(JsonValue, controls),
        "request": normalized["realization"], "config": normalized["config"],
        "history": history["frames"], "until": normalized["until"]}
    if not _same(result["production_payload"], expected_production):
        raise CoreProtocolError("Nested selection omitted or changed normalized build authority or shared controls")
    production_json = _encoded(expected_production)
    production = _production_result(replace(response, operation="select-synthetic", result=result["production"]),
        expected_production, production_json)
    if production.outcome == "unsupported":
        expected_exit = 2
    else:
        record = production.record
        if record is None or record["selected_strategy"] not in (None, "native", "de_morgan"):
            raise CoreProtocolError("Native selection omitted its selected strategy identity")
        expected_exit = 1 if record["selected_strategy"] is None else 0
    if exit_code != expected_exit:
        raise CoreProtocolError("Native selection command status differs from the complete native outcome")
    return NativeSyntheticPublicProduction(response.request_id, original, _encoded(payload), normalized_json,
        production_json, _encoded(result), production, frame_count, exit_code)


@dataclass(frozen=True)
class SyntheticProducerPublicClient:
    core: CoreClient

    def select_document(self, build_request: bytes, *, limits: JsonValue = None, request_id: str | None = None,
                        cancelled: Callable[[], bool] | None = None) -> NativeSyntheticPublicProduction:
        if self.core.role != "core":
            raise CoreProtocolError("Public synthetic selection requires the core executable role")
        if type(build_request) is not bytes:
            raise CoreProtocolError("Public synthetic build authority must be immutable JSON bytes")
        _limits(limits)
        # Freeze both caller-owned controls and complete raw authority before
        # negotiation; the structural decoder performs no source validation.
        payload = cast(dict[str, JsonValue], decode_json(encode_json({"profile": capability_profile()["profile"],
            "limits": limits, "build_request": decode_json(build_request, limit=LIMITS["max_request_bytes"])})))
        _negotiate(self.core.negotiate(OPERATION, cancelled=cancelled))
        return _result(self.core.call(OPERATION, payload, request_id=request_id, cancelled=cancelled), payload, build_request)

    def select(self, build_request: JsonValue, *, limits: JsonValue = None, request_id: str | None = None,
               cancelled: Callable[[], bool] | None = None) -> NativeSyntheticPublicProduction:
        return self.select_document(encode_json(build_request), limits=limits, request_id=request_id, cancelled=cancelled)
