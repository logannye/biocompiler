"""Immutable views of complete native workflows, with no Python workflow authority.

Legacy objects may be serialized as untrusted input in one explicitly marked
phase. Native outputs use new view identities and only individually audited
CheckResult/FailureSignature leaf codecs; no legacy workflow constructor runs.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, cast

from biocompiler.core_artifacts import MAX_ARTIFACT_BYTES, _canonical, decode_artifact
from biocompiler.core_client import LIMITS, CoreClient, CoreError, CoreProtocolError, CoreRejected, Diagnostic, JsonValue
from biocompiler.core_workflow import WorkflowClient, WorkflowResult
from biocompiler.errors import SerializationError
from biocompiler.verification.evidence import CheckResult, RequirementCoverage
from biocompiler.verification.exploration import FailureSignature

_INPUT_SERIALIZATION: ContextVar[bool] = ContextVar("workflow_input_serialization", default=False)
_PRESENTATION = "biocompiler.core.verification_workflow.presentation.v1"
_REQUEST = "biocompiler.synthetic_verification_request.v0.1"
_RECORD = "biocompiler.synthetic_verification_record.v0.1"
_CONTACT = "biocompiler.boolean_contact_config.v0.1"
_MIXED = "biocompiler.boolean_input_config.v0.1"
_REPORT = "biocompiler.boolean_exploration_report.v0.1"
_MIXED_REPORT = "biocompiler.boolean_input_exploration_report.v0.1"
_REDUCTION = "biocompiler.history_reduction.v0.1"
_DERIVED = ("state_count", "possible_histories", "evaluated_histories", "complete", "all_passed",
            "outcome_counts", "coverage_totals", "shared_dependencies")


def serializing_legacy_input() -> bool:
    """Execution guards may allow exact pinned input serializers only here."""
    return _INPUT_SERIALIZATION.get()


class WorkflowCoreError(SerializationError):
    """Selected-core failure with its complete original structured diagnostics."""
    def __init__(self, operation: str, core_error: CoreError) -> None:
        self.operation = operation
        self.core_error = core_error
        self.diagnostics: tuple[Diagnostic, ...] = (
            core_error.response.diagnostics if isinstance(core_error, CoreRejected) else ())
        super().__init__(f"{operation} failed: {core_error}")


def _bytes(value: Any) -> bytes:
    return _canonical(cast(JsonValue, value), MAX_ARTIFACT_BYTES)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, NativeDocument):
        return value.to_dict()
    if type(value) in (CheckResult, FailureSignature, RequirementCoverage):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _fields(raw: Any, names: tuple[str, ...], label: str) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != set(names):
        raise CoreProtocolError(f"Invalid complete native {label} fields")
    return cast(dict[str, Any], raw)


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise CoreProtocolError(f"Native {label} must be an array")
    return value


def _json_text(value: Any, indent: int | None, *, sort_keys: bool = True,
               compact: bool = False, limit: int = MAX_ARTIFACT_BYTES) -> str:
    if indent is not None and (type(indent) is not int or indent > MAX_ARTIFACT_BYTES):
        raise CoreProtocolError("Invalid or oversized workflow indentation")
    encoder = json.JSONEncoder(sort_keys=sort_keys, indent=indent, ensure_ascii=False, allow_nan=False,
                               separators=(",", ":") if compact else None)
    result: list[str] = []
    size = 0
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > limit:
            raise CoreProtocolError("Formatted workflow exceeds the artifact byte limit")
        result.append(chunk)
    return "".join(result)


@dataclass(frozen=True, slots=True, eq=False)
class NativeDocument:
    """Read-only JSON fields, explicitly distinct from legacy semantic IR classes."""
    _data: Mapping[str, Any]
    _extras: Mapping[str, Any]
    _canonical_json: bytes
    _identity: str | None

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return self._data[name]
        if name in self._extras:
            return self._extras[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        return {key: _thaw(value) for key, value in self._data.items()}

    def to_json(self, *, indent: int | None = 2) -> str:
        return _json_text(self.to_dict(), indent, limit=MAX_ARTIFACT_BYTES)

    @property
    def canonical_json(self) -> bytes:
        return self._canonical_json

    @property
    def canonical_fingerprint(self) -> str:
        return _sha(self._canonical_json)

    @property
    def fingerprint(self) -> str:
        if self._identity is None:
            raise AttributeError("This raw document does not supply a semantic fingerprint; use canonical_fingerprint")
        return self._identity

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self._canonical_json == cast(NativeDocument, other)._canonical_json

    def __hash__(self) -> int:
        return hash((type(self), self._canonical_json))


class NativeWorkflowRecord(NativeDocument):
    __slots__ = ()


class NativeWorkflowRequest(NativeDocument):
    __slots__ = ()


class NativeExplorationReport(NativeDocument):
    __slots__ = ()


class NativeBooleanInputExplorationReport(NativeExplorationReport):
    __slots__ = ()


class NativeReductionResult(NativeDocument):
    __slots__ = ()


class NativeBooleanContactConfig(NativeDocument):
    __slots__ = ()


class NativeBooleanInputConfig(NativeBooleanContactConfig):
    __slots__ = ()


class NativeBooleanObservation(NativeDocument):
    __slots__ = ()


class NativeInputFrame(NativeDocument):
    __slots__ = ()


class NativeSignalSample(NativeDocument):
    __slots__ = ()


def _view(cls: type[NativeDocument], raw: dict[str, Any], values: Mapping[str, Any], *,
          extras: Mapping[str, Any] | None = None, identity: bool = True) -> NativeDocument:
    canonical = _bytes(raw)
    result = cls(MappingProxyType(dict(values)), MappingProxyType(dict(extras or {})),
                 canonical, _sha(canonical) if identity else None)
    if _bytes(result.to_dict()) != canonical:
        raise CoreProtocolError("Native view changed complete document identity")
    return result


def _generic(value: Any) -> Any:
    if type(value) is dict:
        if "schema_version" in value:
            return _view(NativeDocument, value, {key: _generic(item) for key, item in value.items()}, identity=False)
        return MappingProxyType({key: _generic(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_generic(item) for item in value)
    return value


def _leaf(raw: Any) -> CheckResult:
    if type(raw) is not dict:
        raise CoreProtocolError("Native check leaf must be an object")
    # Every native workflow leaf retains the independent checker's 32 MiB
    # ASCII ceiling even though its containing workflow may use 64 MiB UTF-8.
    # Bound the expansion before invoking the audited legacy leaf constructor.
    def encoded(value: Any) -> bytes:
        output = bytearray()
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        for text in encoder.iterencode(value):
            chunk = text.encode("ascii")
            if len(output) + len(chunk) > LIMITS["max_response_bytes"]:
                raise CoreProtocolError("Native check leaf exceeds its ASCII byte limit")
            output.extend(chunk)
        return bytes(output)

    expected = encoded(raw)
    result = CheckResult.from_dict(raw)
    actual = encoded(result.to_dict())
    if actual != expected or result.fingerprint != _sha(expected):
        raise CoreProtocolError("Audited check leaf hydration changed its complete ASCII identity")
    return result


def _signature(raw: Any) -> FailureSignature | None:
    if raw is None:
        return None
    if type(raw) is not dict:
        raise CoreProtocolError("Native failure signature must be an object")
    result = FailureSignature.from_dict(raw)
    expected = _bytes(raw)
    if _bytes(result.to_dict()) != expected or result.fingerprint != _sha(expected):
        raise CoreProtocolError("Audited failure signature hydration changed its complete UTF-8 identity")
    return result


def _sample(raw: Any) -> NativeSignalSample:
    names = ("value", "present", "high", "low")
    raw = _fields(raw, names, "signal sample")
    return cast(NativeSignalSample, _view(NativeSignalSample, raw, {key: raw[key] for key in names}, identity=False))


def _ordered_samples(raw: Any, context: Any) -> Mapping[str, NativeSignalSample]:
    if type(raw) is not dict:
        raise CoreProtocolError("Native signal samples must be an object")
    keys = list(context) if type(context) is dict and set(context) == set(raw) else list(raw)
    return MappingProxyType({key: _sample(raw[key]) for key in keys})


def _frame(raw: Any, context: Any = None) -> NativeInputFrame:
    raw = _fields(raw, ("time", "signals", "contacts"), "input frame")
    if type(raw["contacts"]) is not dict:
        raise CoreProtocolError("Native contacts must be an object")
    source = context if type(context) is dict and _bytes(context) == _bytes(raw) else {}
    contact_context = source.get("contacts", {})
    keys = list(contact_context) if set(contact_context) == set(raw["contacts"]) else list(raw["contacts"])
    contacts = MappingProxyType({key: _ordered_samples(raw["contacts"][key], contact_context.get(key)) for key in keys})
    return cast(NativeInputFrame, _view(NativeInputFrame, raw, {
        "time": raw["time"], "signals": _ordered_samples(raw["signals"], source.get("signals")), "contacts": contacts}, identity=False))


def _history(raw: Any, context: Any = None) -> tuple[NativeInputFrame, ...]:
    values = _array(raw, "history")
    sources = {_bytes(frame): frame for frame in context} if type(context) is list else {}
    return tuple(_frame(frame, sources.get(_bytes(frame))) for frame in values)


def _bounds(raw: Any, counts: Mapping[str, Any], context: Any = None) -> NativeBooleanContactConfig:
    if type(raw) is not dict or raw.get("schema_version") not in (_CONTACT, _MIXED):
        raise CoreProtocolError("Unsupported native bounds schema")
    mixed = raw["schema_version"] == _MIXED
    names: tuple[str, ...] = ("schema_version", "contact_ids", "observations", "variable_times", "until", "fixed_suffix", "max_histories")
    if mixed:
        names += ("cell_observations",)
    raw = _fields(raw, names, "bounds")
    source = context if type(context) is dict else {}
    values = {key: _freeze(raw[key]) for key in names}
    for key in ("observations", "cell_observations") if mixed else ("observations",):
        observations = []
        for item in _array(raw[key], "observations"):
            observation_fields = ("schema_version", "signal_id", "field")
            item = _fields(item, observation_fields, "Boolean observation")
            if item["schema_version"] != "biocompiler.boolean_observation.v0.1":
                raise CoreProtocolError("Unsupported native observation schema")
            observations.append(_view(NativeBooleanObservation, item,
                                      {name: item[name] for name in observation_fields}))
        values[key] = tuple(observations)
    values["fixed_suffix"] = _history(raw["fixed_suffix"], source.get("fixed_suffix"))
    extras = {key: counts[key] for key in ("state_count", "possible_histories")}
    cls = NativeBooleanInputConfig if mixed else NativeBooleanContactConfig
    return cast(NativeBooleanContactConfig, _view(cls, raw, values, extras=extras))


def _result(raw: Any, operation: str, context: dict[str, Any]) -> Any:
    if operation == "check":
        return _leaf(raw)
    if operation == "explore":
        names: tuple[str, ...] = ("schema_version", "config", "results", "explorer_version", "claim_scope", *_DERIVED)
        raw = _fields(raw, names, "exploration report")
        if raw["schema_version"] not in (_REPORT, _MIXED_REPORT):
            raise CoreProtocolError("Unsupported native exploration report schema")
        values = {key: _freeze(raw[key]) for key in names}
        # Historical summary formatting follows enum declaration order. This
        # copies supplied counts verbatim and does not count or classify results.
        outcome_order = ("pass", "fail", "unknown", "unsupported")
        counts = raw["outcome_counts"]
        if type(counts) is dict and set(counts) == set(outcome_order):
            values["outcome_counts"] = MappingProxyType({key: counts[key] for key in outcome_order})
        values["config"] = _bounds(raw["config"], raw, context.get("bounds"))
        values["results"] = tuple(_leaf(item) for item in _array(raw["results"], "check results"))
        values["coverage_totals"] = tuple(RequirementCoverage.from_dict(item)
            for item in _array(raw["coverage_totals"], "coverage totals"))
        cls = NativeBooleanInputExplorationReport if raw["schema_version"] == _MIXED_REPORT else NativeExplorationReport
        return _view(cls, raw, values)
    if operation == "reduce":
        names = ("schema_version", "original_history", "history", "until", "signature", "original_result",
                 "result", "evaluations", "one_minimal", "reducer_version")
        raw = _fields(raw, names, "reduction report")
        if raw["schema_version"] != _REDUCTION:
            raise CoreProtocolError("Unsupported native reduction report schema")
        values = {key: _freeze(raw[key]) for key in names}
        for key in ("original_history", "history"):
            values[key] = _history(raw[key], context.get("history"))
        values["signature"] = _signature(raw["signature"])
        values["original_result"] = _leaf(raw["original_result"])
        values["result"] = _leaf(raw["result"])
        return _view(NativeReductionResult, raw, values)
    raise CoreProtocolError("Unsupported native workflow operation")


def view_result(native: WorkflowResult, *, authority: bytes | None = None) -> NativeWorkflowRecord:
    """Expose a checked transport result without running Python workflow logic."""
    try:
        raw = _fields(decode_artifact(native.record_json),
            ("schema_version", "request", "result", "workflow_version", "claim_scope"), "workflow record")
        if raw["schema_version"] != _RECORD or _bytes(raw) != native.record_json or _sha(native.record_json) != native.record_fingerprint:
            raise CoreProtocolError("Native workflow bytes or identity differ")
        request = _fields(raw["request"], ("schema_version", "realization", "candidate", "operation", "mode",
            "history", "until", "bounds", "signature", "max_evaluations"), "workflow request")
        if (request["schema_version"] != _REQUEST or request["operation"] != native.workflow_operation
                or request["mode"] != native.mode or _sha(_bytes(request)) != native.request_fingerprint):
            raise CoreProtocolError("Native workflow request identity differs")
        context = request if authority is None else decode_artifact(authority, authority=True)
        if type(context) is not dict:
            raise CoreProtocolError("Workflow formatting authority must be an object")
        if authority is not None and _sha(_bytes(context)) != native.authority_fingerprint:
            raise CoreProtocolError("Formatting authority differs from native independent authority")
        presentation = _fields(native.receipt.get("presentation"),
            ("profile", "command_exit_code", "original_frames", "reduced_frames"), "presentation")
        if (presentation["profile"] != _PRESENTATION or type(presentation["command_exit_code"]) is not int
                or presentation["command_exit_code"] not in (0, 1)
                or any(value is not None and (type(value) is not int or value < 0)
                       for value in (presentation["original_frames"], presentation["reduced_frames"]))):
            raise CoreProtocolError("Invalid native workflow presentation")
        result = _result(raw["result"], native.workflow_operation, context)
        values = {key: _freeze(item) for key, item in request.items()}
        values["realization"] = _generic(request["realization"])
        candidate = request["candidate"]
        if type(candidate) is not dict:
            raise CoreProtocolError("Native candidate must be an object")
        values["candidate"] = _view(NativeDocument, candidate, {key: _generic(value) for key, value in candidate.items()})
        values["history"] = _history(request["history"], context.get("history"))
        values["signature"] = _signature(request["signature"])
        values["bounds"] = None if request["bounds"] is None else _bounds(request["bounds"], raw["result"], context.get("bounds"))
        request_view = _view(NativeWorkflowRequest, request, values)
        record = _view(NativeWorkflowRecord, raw, {"schema_version": raw["schema_version"],
            "request": request_view, "result": result, "workflow_version": raw["workflow_version"], "claim_scope": raw["claim_scope"]},
            extras={"presentation": _freeze(presentation), "command_exit_code": presentation["command_exit_code"],
                    "native": native, "authority_json": bytes(authority) if authority is not None else _bytes(request)})
        return cast(NativeWorkflowRecord, record)
    except CoreError:
        raise
    except (SerializationError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise CoreProtocolError(f"Native workflow cannot be exposed losslessly: {error}") from error


def _input_bytes(value: Any, *, request: bool) -> bytes:
    """Freeze input only; legacy derived fields are untrusted historical claims."""
    if type(value) is bytes:
        return value
    expected_view = NativeWorkflowRequest if request else NativeWorkflowRecord
    if type(value) is expected_view:
        return cast(NativeDocument, value).canonical_json
    if isinstance(value, Mapping):
        raw = _thaw(value)
    else:
        # These are already authored inputs. Never call their from_dict methods,
        # constructors, checker or evaluator here. The marker ends before I/O.
        from biocompiler.compiler.verification_workflow import SyntheticVerificationRecord, SyntheticVerificationRequest
        expected = SyntheticVerificationRequest if request else SyntheticVerificationRecord
        if type(value) is not expected:
            raise CoreProtocolError("Expected complete workflow request" if request else "Expected complete historical workflow record")
        token = _INPUT_SERIALIZATION.set(True)
        try:
            raw = value.to_dict()
        finally:
            _INPUT_SERIALIZATION.reset(token)
    # Preserve input mapping insertion order for legacy CLI formatting. Identity
    # is still separately canonicalized and checked by WorkflowClient.
    try:
        limit = LIMITS["max_request_bytes"] if request else MAX_ARTIFACT_BYTES
        encoded = _json_text(raw, None, sort_keys=False, compact=True, limit=limit).encode("utf-8")
        decode_artifact(encoded, authority=request)
        return encoded
    except CoreError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise CoreProtocolError(f"Malformed workflow input: {error}") from error


def run_document(*, request: Any, core: CoreClient, limits: JsonValue = None,
                 command: str | None = None, cancelled: Callable[[], bool] | None = None) -> tuple[NativeWorkflowRecord, WorkflowResult]:
    try:
        authority = _input_bytes(request, request=True)
        native = WorkflowClient(core).run_public(authority, limits=limits, command=command, cancelled=cancelled)
        return view_result(native, authority=authority), native
    except CoreError as error:
        raise WorkflowCoreError("run-verification-workflow", error) from error


def replay_document(*, request: Any, record: Any, core: CoreClient, limits: JsonValue = None,
                    command: str | None = None, cancelled: Callable[[], bool] | None = None) -> tuple[NativeWorkflowRecord, WorkflowResult]:
    try:
        authority = _input_bytes(request, request=True)
        historical = _input_bytes(record, request=False)
        native = WorkflowClient(core).replay_public(authority, historical, limits=limits, command=command, cancelled=cancelled)
        return view_result(native, authority=authority), native
    except CoreError as error:
        raise WorkflowCoreError("replay-verification-workflow", error) from error


def run_record(request: Any, *, core: CoreClient, **options: Any) -> NativeWorkflowRecord:
    return run_document(request=request, core=core, **options)[0]


def replay_record(record: Any, *, expected_request: Any, core: CoreClient, **options: Any) -> NativeWorkflowRecord:
    return replay_document(request=expected_request, record=record, core=core, **options)[0]
