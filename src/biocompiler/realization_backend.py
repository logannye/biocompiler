"""Explicit native realization routing, hydrating only historical report codecs.

Raw authority is sent without constructing RealizationRequest or invoking Python
lowering. The three result codecs are immutable record validation only; exact
family bytes and fingerprints must survive hydration. No native failure falls
back to a Python checker, producer or evaluator.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Iterable, Protocol, TypeAlias, cast

from biocompiler.core_client import (
    LIMITS, CoreClient, CoreError, CoreProtocolError, CoreRejected, Diagnostic,
    JsonValue, decode_json, encode_json,
)
from biocompiler.core_realization import RealizationClient, RealizationResult, encode_report
from biocompiler.errors import SerializationError
from biocompiler.verification.components import CompositionResult
from biocompiler.verification.evidence import CheckResult, DependencySnapshot

HistoricalResult: TypeAlias = CheckResult | DependencySnapshot | CompositionResult
CheckOutcome: TypeAlias = tuple[HistoricalResult, RealizationResult]


class RealizationCoreError(SerializationError):
    """Failure of the explicitly selected core, retaining original diagnostics."""
    def __init__(self, operation: str, core_error: CoreError) -> None:
        self.operation = operation
        self.core_error = core_error
        self.diagnostics: tuple[Diagnostic, ...] = (
            core_error.response.diagnostics if isinstance(core_error, CoreRejected) else ()
        )
        super().__init__(f"{operation} failed: {core_error}")


def _hydrate(native: RealizationResult) -> HistoricalResult:
    try:
        document = native.report
        record: HistoricalResult
        if native.operation == "realization-dependencies":
            record = DependencySnapshot(document)
        elif native.operation.endswith("component-assembly"):
            record = CompositionResult.from_dict(document)
        else:
            record = CheckResult.from_dict(document)
        reproduced = encode_report(record.to_dict(), native.report_encoding)
        if (reproduced != native.report_json or hashlib.sha256(reproduced).hexdigest() != native.report_fingerprint
                or record.fingerprint != native.report_fingerprint):
            raise CoreProtocolError("Public realization report hydration changed the complete native identity")
        return record
    except (SerializationError, ValueError, TypeError) as error:
        raise CoreProtocolError(f"Native realization report cannot be represented by its public record codec: {error}") from error


def check_document(*, operation: str, core: CoreClient, limits: JsonValue = None,
                   cancelled: Callable[[], bool] | None = None, **authority: JsonValue) -> CheckOutcome:
    """Fresh check/replay of raw complete authority; hydrate only the output report."""
    from biocompiler.core_realization import _profile
    try:
        _, profile = _profile(operation)
        # The transport itself freezes the complete payload before any I/O.
        native = RealizationClient(core).call(operation, {"profile": profile["profile"], "limits": limits, **authority},
                                              cancelled=cancelled)
        return _hydrate(native), native
    except CoreError as error:
        raise RealizationCoreError(operation, error) from error


def replay_document(*, operation: str, assessment: JsonValue, core: CoreClient, limits: JsonValue = None,
                    cancelled: Callable[[], bool] | None = None, **authority: JsonValue) -> CheckOutcome:
    """Replay the complete historical report under all independently supplied inputs."""
    if not operation.startswith("replay-"):
        raise RealizationCoreError(operation, CoreProtocolError("Expected a realization replay operation"))
    return check_document(operation=operation, assessment=assessment, core=core, limits=limits,
                          cancelled=cancelled, **authority)


def dependencies_document(*, core: CoreClient, limits: JsonValue = None,
                          cancelled: Callable[[], bool] | None = None, **authority: JsonValue) -> CheckOutcome:
    return check_document(operation="realization-dependencies", core=core, limits=limits,
                          cancelled=cancelled, **authority)


class _RecordView(Protocol):
    def to_json(self, *, indent: int | None = None) -> str: ...


def _record_document(record: object) -> JsonValue:
    # Existing serializers encode immutable mappings and string enums. No input
    # constructor/from_dict is called: RealizationRequest construction lowers.
    text = cast(_RecordView, record).to_json(indent=None)
    return decode_json(text.encode("utf-8"), limit=LIMITS["max_request_bytes"])


def check_records(*, operation: str, core: CoreClient, history: Iterable[Any], until: JsonValue = None, **authority: object) -> HistoricalResult:
    """SDK adapter for already-authored immutable records and exact InputFrames."""
    from biocompiler.semantics.evaluator import InputFrame
    frames = tuple(history)
    if any(not isinstance(frame, InputFrame) for frame in frames):
        raise TypeError("History must contain InputFrame objects.")
    try:
        documents = {key: _record_document(value) for key, value in authority.items()}
        # InputFrame has no JsonArtifact/to_json codec and carries no schema tag.
        # Its to_dict is already a complete JSON description; strict encoding
        # preserves integer/float kinds and validates the aggregate before I/O.
        documents["history"] = [frame.to_dict() for frame in frames]
        documents["until"] = until
        snapshot = cast(dict[str, Any], decode_json(encode_json(documents)))
        return check_document(operation=operation, core=core, **snapshot)[0]
    except CoreError as error:
        raise RealizationCoreError(operation, error) from error
