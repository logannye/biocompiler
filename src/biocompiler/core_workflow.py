"""Opt-in native workflow transport with opaque complete record results.

This module checks transport contracts and exact artifact identities. It never
constructs Python biological records, executes models, or falls back to Python
workflow semantics. A retained record is historical evidence, not fresh authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Literal, cast

from biocompiler.core_artifacts import (
    MAX_ARTIFACT_BYTES, MAX_CONTROL_BYTES, _canonical, _preflight_bytes,
    call_artifact, decode_artifact,
)
from biocompiler.core_client import (
    CoreCapabilities, CoreClient, CoreProtocolError, JsonValue, _object,
    decode_json, encode_json,
)

OPERATIONS = ("run-verification-workflow", "replay-verification-workflow")
_PROFILE_JSON = '{"artifact_encoding":"python-json-v1","engine_version":"biocompiler.ocaml.synthetic_verification.v0.1","implementation_version":"biocompiler.ocaml.verification_workflow_service.v0.1","modes":["candidate","model"],"operations":["run-verification-workflow","replay-verification-workflow"],"profile":"biocompiler.core.verification_workflow.v1","record_schema":"biocompiler.synthetic_verification_record.v0.1","request_schema":"biocompiler.synthetic_verification_request.v0.1","resources":{"realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"synthetic":{"profile":"biocompiler.synthetic_candidate_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"workflow":{"aggregation_work_allowance":4098000274944,"canonical_encoding":"compact_utf8","max_artifact_bytes":67108864,"max_artifact_nodes":1000000,"max_callback_report_bytes":33554432,"max_callback_report_nodes":500000,"max_evaluation_work":50000000,"max_evaluations":100000,"max_exploration_trial_work":112040813076,"max_monitor_items":8000000,"max_reduction_trial_work":84910277138,"max_report_bytes":67108864,"max_report_nodes":1000000,"max_request_bytes":83951616,"max_request_nodes":2000000,"max_retained_checks":19607,"max_retained_validation_work":90468782096,"max_work":8500125714074944,"max_workspace_items":2000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.verification_workflow.resources.v1","report_accounting":"incremental_records_transfer_to_complete_final_publication","retention_accounting":"live_items_released_only_when_discarded_work_never_refunded","work_accounting":"single_ancestor_for_import_all_evaluations_validation_replay_and_publication","work_integer_encoding":"exact_json_integer_below_2_to_53"}},"validation_scope":"complete_fresh_verification_workflow","workflow_operations":["check","explore","reduce"],"workflow_version":"biocompiler.synthetic_verification_workflow.v0.1"}'
_LIMIT_FIELDS = frozenset(("max_work", "max_monitor_items", "max_request_bytes",
                           "max_report_bytes", "max_report_nodes"))
_RECEIPT_FIELDS = {"schema_version", "profile", "operation", "executable", "request_id",
    "validation_scope", "implementation_version", "workflow_version", "workflow_operation",
    "mode", "authority_fingerprint", "request_fingerprint", "retained_record_fingerprint",
    "record_fingerprint", "resources"}
_RECORD_FIELDS = {"schema_version", "request", "result", "workflow_version", "claim_scope"}
_HISTORICAL_SCOPE = ("Historical finite-history software-model verification record; fresh replay "
    "requires independent complete operation authority. No universal, biological or human therapeutic claim.")
_RESULT_SCHEMAS = {
    "check": {"biocompiler.realization_check.v0.1"},
    "explore": {"biocompiler.boolean_exploration_report.v0.1",
                "biocompiler.boolean_input_exploration_report.v0.1"},
    "reduce": {"biocompiler.history_reduction.v0.1"},
}


def capability_profile() -> dict[str, Any]:
    """Return a defensive copy of the exact installed workflow contract."""
    return cast(dict[str, Any], json.loads(_PROFILE_JSON))


def presentation_capability_profile() -> dict[str, Any]:
    """The opt-in public presentation contract; raw v1 remains unchanged."""
    profile = capability_profile()
    profile.update(profile="biocompiler.core.verification_workflow.v2",
                   implementation_version="biocompiler.ocaml.verification_workflow_service.v0.2",
                   presentation_profile="biocompiler.core.verification_workflow.presentation.v1")
    return profile


def default_limits() -> dict[str, int]:
    workflow = capability_profile()["resources"]["workflow"]
    return {key: cast(int, workflow[key]) for key in _LIMIT_FIELDS}


def _limits(value: JsonValue) -> dict[str, int]:
    defaults = default_limits()
    if value is None:
        return defaults
    fields = _object(value, set(_LIMIT_FIELDS), "Workflow limits")
    if any(type(fields[key]) is not int or not 0 < cast(int, fields[key]) <= maximum
           for key, maximum in defaults.items()):
        raise CoreProtocolError("Workflow limits must be positive integer reductions")
    return {key: cast(int, fields[key]) for key in defaults}


def effective_resources(limits: JsonValue = None) -> dict[str, Any]:
    """Map exact reductions through the pinned aggregate and leaf resources."""
    reduced = _limits(limits)
    resources = capability_profile()["resources"]
    resources["workflow"].update(reduced)
    resources["workflow"]["max_evaluation_work"] = min(50_000_000, reduced["max_work"])

    def visit(value: Any) -> Any:
        if type(value) is dict:
            return {key: min(item, reduced[key]) if key in reduced else visit(item)
                    for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value

    resources["realization"] = visit(resources["realization"])
    resources["synthetic"] = visit(resources["synthetic"])
    return cast(dict[str, Any], resources)


def _same(left: JsonValue, right: JsonValue) -> bool:
    # JSON identities distinguish bool/int, integer/float, and signed zero.
    return encode_json(left, limit=MAX_CONTROL_BYTES) == encode_json(right, limit=MAX_CONTROL_BYTES)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _mapping(value: JsonValue, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CoreProtocolError(label + " must be an object")
    return cast(dict[str, Any], value)


class _WorkflowCore(CoreClient):
    """Check the semantic and artifact contracts in the same negotiation."""

    def _profile(self) -> tuple[str, dict[str, Any]]:
        return "verification_workflow", capability_profile()

    def negotiate(self, operation: str, *, cancelled: Callable[[], bool] | None = None) -> CoreCapabilities:
        capabilities = super().negotiate(operation, cancelled=cancelled)
        key, expected = self._profile()
        if (not _same(capabilities.profiles.get(key), expected)
                or any(name not in capabilities.operations for name in OPERATIONS)
                or expected["validation_scope"] not in capabilities.validation_scopes):
            raise CoreProtocolError("Incompatible workflow operations, schema, resources or validation scope")
        return capabilities


class _PublicWorkflowCore(_WorkflowCore):
    def _profile(self) -> tuple[str, dict[str, Any]]:
        return "verification_workflow_presentation", presentation_capability_profile()


def _presentation(value: JsonValue, *, action: str, replay: bool) -> dict[str, Any]:
    """Validate native presentation shape without deriving result semantics."""
    fields = _object(value, {"profile", "command_exit_code", "original_frames", "reduced_frames"},
                     "Workflow presentation")
    if (fields["profile"] != presentation_capability_profile()["presentation_profile"]
            or type(fields["command_exit_code"]) is not int
            or fields["command_exit_code"] not in (0, 1)
            or replay and fields["command_exit_code"] != 0):
        raise CoreProtocolError("Invalid native workflow presentation")
    for name in ("original_frames", "reduced_frames"):
        count = fields[name]
        if action == "reduce":
            if type(count) is not int or not 0 <= count <= 1_000_000:
                raise CoreProtocolError("Invalid native workflow frame count")
        elif count is not None:
            raise CoreProtocolError("Unexpected native workflow frame count")
    return cast(dict[str, Any], fields)


@dataclass(frozen=True)
class WorkflowResult:
    """Complete immutable native bytes with defensive structural accessors.

    Accessors decode JSON only. They do not rerun or infer verification, reduce a
    counterexample, reconstruct dependencies, or grant fresh acceptance.
    """

    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    workflow_operation: str
    mode: str
    authority_fingerprint: str
    request_fingerprint: str
    retained_record_fingerprint: str | None
    record_fingerprint: str
    record_json: bytes
    _receipt_json: bytes
    _envelope_json: bytes

    @property
    def record(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_artifact(self.record_json))

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self._receipt_json, limit=MAX_CONTROL_BYTES))

    @property
    def envelope(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self._envelope_json, limit=MAX_CONTROL_BYTES))


@dataclass(frozen=True)
class WorkflowClient:
    core: CoreClient

    def _call(self, operation: str, request: bytes, record: bytes | None, *,
              limits: JsonValue, request_id: str | None,
              cancelled: Callable[[], bool] | None, public: bool = False,
              command: str | None = None) -> WorkflowResult:
        if command is not None and type(command) is not str:
            raise CoreProtocolError("Workflow command must be a string or null")
        # All mutable controls are copied before invoking negotiation. Raw
        # artifacts are exact bytes; the transport rejects mutable byte arrays.
        reduced = _limits(limits)
        frozen_limits: JsonValue = None if limits is None else cast(JsonValue, dict(reduced))
        authority = decode_artifact(request, authority=True)
        canonical_authority = _canonical(authority, MAX_ARTIFACT_BYTES)
        profile = presentation_capability_profile() if public else capability_profile()
        core_type = _PublicWorkflowCore if public else _WorkflowCore
        core = core_type(self.core.executable, self.core.role,
                         self.core.timeout_seconds, self.core.expected_sha256)
        payload: dict[str, JsonValue] = {"profile": profile["profile"], "limits": frozen_limits}
        if public:
            payload["command"] = command
        result = call_artifact(core, operation, payload, authority=request,
            retained_record=record, output_limit=reduced["max_report_bytes"],
            request_id=request_id, cancelled=cancelled)
        # Native replay checks independent source authority before decoding the
        # retained record. Inspect that historical JSON only after success so a
        # malformed record cannot hide the authoritative native rejection.
        retained = None if record is None else _canonical(decode_artifact(record), MAX_ARTIFACT_BYTES)
        envelope = _mapping(result.response.result, "Artifact envelope")
        fields = _RECEIPT_FIELDS | {"command", "presentation"} if public else _RECEIPT_FIELDS
        receipt = _object(envelope["result"], fields, "Workflow receipt")
        _preflight_bytes(result.artifact, limit=reduced["max_report_bytes"], nodes=reduced["max_report_nodes"])
        document = _object(decode_artifact(result.artifact), _RECORD_FIELDS, "Workflow record")
        supplied = _mapping(authority, "Independent workflow request")
        normalized = _mapping(document["request"], "Returned workflow request")
        action, mode = supplied.get("operation"), supplied.get("mode")
        if (type(action) is not str or action not in _RESULT_SCHEMAS
                or type(mode) is not str or mode not in ("candidate", "model")):
            raise CoreProtocolError("Successful workflow response has unsupported independent authority")
        value = _mapping(document["result"], "Workflow result")
        result_schema = value.get("schema_version")
        if (document["schema_version"] != profile["record_schema"]
                or document["workflow_version"] != profile["workflow_version"]
                or document["claim_scope"] != _HISTORICAL_SCOPE
                or normalized.get("schema_version") != profile["request_schema"]
                or normalized.get("operation") != action or normalized.get("mode") != mode
                or type(result_schema) is not str or result_schema not in _RESULT_SCHEMAS[action]):
            raise CoreProtocolError("Workflow record schema, operation, mode or claim differs")
        actual = _sha(result.artifact)
        normalized_identity = _sha(_canonical(normalized, MAX_ARTIFACT_BYTES))
        expected: dict[str, JsonValue] = {
            "schema_version": ("biocompiler.core.verification_workflow_result.v2" if public
                               else "biocompiler.core.verification_workflow_result.v1"),
            "profile": profile["profile"], "operation": operation,
            "executable": self.core.role, "request_id": result.response.request_id,
            "validation_scope": profile["validation_scope"],
            "implementation_version": profile["implementation_version"],
            "workflow_version": profile["workflow_version"],
            "workflow_operation": action, "mode": mode,
            "authority_fingerprint": _sha(canonical_authority),
            "request_fingerprint": normalized_identity,
            "retained_record_fingerprint": None if retained is None else _sha(retained),
            "record_fingerprint": actual, "resources": effective_resources(frozen_limits),
        }
        if public:
            expected["command"] = command
            expected["presentation"] = _presentation(receipt["presentation"], action=action,
                                                     replay=operation == OPERATIONS[1])
        if not _same(receipt, expected):
            raise CoreProtocolError("Workflow receipt differs from complete independent authority or effective resources")
        if retained is not None and result.artifact != retained:
            raise CoreProtocolError("Fresh replay differs from the complete retained record")
        return WorkflowResult(result.response.request_id, operation, self.core.role, action, mode,
            _sha(canonical_authority), normalized_identity, None if retained is None else _sha(retained),
            actual, result.artifact, encode_json(receipt, limit=MAX_CONTROL_BYTES),
            encode_json(envelope, limit=MAX_CONTROL_BYTES))

    def run(self, request: bytes, *, limits: JsonValue = None, request_id: str | None = None,
            cancelled: Callable[[], bool] | None = None) -> WorkflowResult:
        return self._call(OPERATIONS[0], request, None, limits=limits, request_id=request_id, cancelled=cancelled)

    def replay(self, request: bytes, record: bytes, *, limits: JsonValue = None,
               request_id: str | None = None, cancelled: Callable[[], bool] | None = None) -> WorkflowResult:
        return self._call(OPERATIONS[1], request, record, limits=limits, request_id=request_id, cancelled=cancelled)


    def run_public(self, request: bytes, *, command: str | None = None,
                   limits: JsonValue = None, request_id: str | None = None,
                   cancelled: Callable[[], bool] | None = None) -> WorkflowResult:
        """Run with separately negotiated native CLI/view presentation metadata."""
        return self._call(OPERATIONS[0], request, None, limits=limits, request_id=request_id,
                          cancelled=cancelled, public=True, command=command)

    def replay_public(self, request: bytes, record: bytes, *, command: str | None = None,
                      limits: JsonValue = None, request_id: str | None = None,
                      cancelled: Callable[[], bool] | None = None) -> WorkflowResult:
        """Fresh replay with native exit policy, including retained failures."""
        return self._call(OPERATIONS[1], request, record, limits=limits, request_id=request_id,
                          cancelled=cancelled, public=True, command=command)
