"""Explicit native architecture routing through historical public record codecs.

Only the selected native clients produce, check, replay or authorize export.
Record hydration preserves the public API and must reproduce the complete native
identity. Hydrated records carry no reusable acceptance authority.
"""

from __future__ import annotations

import hashlib
from typing import Callable, Protocol, TypeVar, cast

from biocompiler.core_architecture import ArchitectureClient, ArchitectureResult
from biocompiler.core_architecture_producer import (
    ArchitectureCompileResult, ArchitectureExportResult, ArchitectureProducerClient,
)
from biocompiler.core_client import (
    LIMITS, CoreClient, CoreError, CoreProtocolError, CoreRejected, Diagnostic,
    JsonValue, decode_json, encode_json,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.architecture_build import (
    PayloadArchitectureBuild, PayloadArchitectureExport, PayloadArchitectureRequest,
)
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification


class ArchitectureCoreError(SerializationError):
    """A selected native operation failed; its original error remains available."""

    def __init__(self, operation: str, core_error: CoreError) -> None:
        self.operation = operation
        self.core_error = core_error
        self.diagnostics: tuple[Diagnostic, ...] = (
            core_error.response.diagnostics if isinstance(core_error, CoreRejected) else ()
        )
        super().__init__(f"{operation} failed: {core_error}")


class _RecordView(Protocol):
    def to_json(self, *, indent: int | None = None) -> str: ...


_T = TypeVar("_T")
CompileOutcome = tuple[PayloadArchitectureBuild, PayloadArchitectureVerification, ArchitectureCompileResult]
CheckOutcome = tuple[PayloadArchitectureBuild, PayloadArchitectureVerification, ArchitectureResult]
ExportOutcome = tuple[PayloadArchitectureExport, PayloadArchitectureBuild,
                      PayloadArchitectureVerification, ArchitectureExportResult]


def _document(record: object) -> JsonValue:
    # Historical to_dict() retains string-Enum instances. Its existing bounded
    # JSON codec encodes those as their declared strings. Strict decoding yields
    # literal JSON without weakening the transport validator or dropping fields.
    return decode_json(cast(_RecordView, record).to_json(indent=None).encode("utf-8"))


def _snapshot(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], decode_json(encode_json(payload)))


def _input_document(record: object, expected_type: type[object], operation: str) -> JsonValue:
    if not isinstance(record, expected_type):
        raise SerializationError(f"{operation} requires {expected_type.__name__} authority.")
    try:
        return _document(record)
    except CoreError as error:
        raise ArchitectureCoreError(operation, error) from error


def _encoded(document: JsonValue) -> bytes:
    return encode_json(document, limit=LIMITS["max_response_bytes"])


def _hydrate(decoder: Callable[[JsonValue], _T], document: JsonValue, *,
             fingerprint: str, exact: bytes | None, label: str) -> _T:
    try:
        record = decoder(document)
        reproduced = _encoded(_document(record))
    except (SerializationError, ValueError, TypeError) as error:
        raise CoreProtocolError(f"Native {label} cannot be represented by its public record codec: {error}") from error
    if ((exact is not None and reproduced != exact)
            or hashlib.sha256(reproduced).hexdigest() != fingerprint):
        raise CoreProtocolError(f"Public {label} hydration changed the complete native artifact identity")
    return record


def _build(document: JsonValue, fingerprint: str, *, exact: bytes | None) -> PayloadArchitectureBuild:
    return _hydrate(cast(Callable[[JsonValue], PayloadArchitectureBuild], PayloadArchitectureBuild.from_dict),
                    document, fingerprint=fingerprint, exact=exact, label="architecture build")


def _verification(native: ArchitectureResult) -> PayloadArchitectureVerification:
    return _hydrate(cast(Callable[[JsonValue], PayloadArchitectureVerification], PayloadArchitectureVerification.from_dict),
                    native.assessment, fingerprint=native.assessment_fingerprint,
                    exact=native._assessment_json, label="architecture verification")


def compile_document(request: JsonValue, *, core: CoreClient,
                     cancelled: Callable[[], bool] | None = None) -> CompileOutcome:
    """Compile exact raw authority and hydrate only the returned native records."""
    operation = "compile-architecture"
    try:
        supplied = _snapshot({"request": request})
        native = ArchitectureProducerClient(core).compile(request=supplied["request"], cancelled=cancelled)
        build = _build(native.build, native.build_fingerprint, exact=native.build_json)
        return build, _verification(native.verification), native
    except CoreError as error:
        raise ArchitectureCoreError(operation, error) from error


def check_document(*, expected_request: JsonValue, build: JsonValue, core: CoreClient,
                   cancelled: Callable[[], bool] | None = None) -> CheckOutcome:
    """Check raw authority before hydrating its normalized public build view."""
    operation = "verify-architecture"
    try:
        supplied = _snapshot({"expected_request": expected_request, "build": build})
        native = ArchitectureClient(core).verify(expected_request=supplied["expected_request"],
                                                build=supplied["build"], cancelled=cancelled)
        # Input inventories may normalize on import. The independent native
        # assessment pins that normalized identity, separately from the raw hash.
        hydrated = _build(supplied["build"], native.build_fingerprint, exact=None)
        return hydrated, _verification(native), native
    except CoreError as error:
        raise ArchitectureCoreError(operation, error) from error


def replay_document(*, expected_request: JsonValue, build: JsonValue, assessment: JsonValue,
                    core: CoreClient, cancelled: Callable[[], bool] | None = None) -> CheckOutcome:
    """Resupply the complete stored report and independent authority for replay."""
    operation = "replay-architecture"
    try:
        supplied = _snapshot({"expected_request": expected_request, "build": build, "assessment": assessment})
        native = ArchitectureClient(core).replay(expected_request=supplied["expected_request"],
                                                build=supplied["build"], assessment=supplied["assessment"],
                                                cancelled=cancelled)
        hydrated = _build(supplied["build"], native.build_fingerprint, exact=None)
        return hydrated, _verification(native), native
    except CoreError as error:
        raise ArchitectureCoreError(operation, error) from error


def export_document(*, expected_request: JsonValue, build: JsonValue, core: CoreClient,
                    cancelled: Callable[[], bool] | None = None) -> ExportOutcome:
    """Freshly check and export the complete pair without a reusable PASS token."""
    operation = "export-architecture"
    try:
        supplied = _snapshot({"expected_request": expected_request, "build": build})
        native = ArchitectureProducerClient(core).export(expected_request=supplied["expected_request"],
                                                         build=supplied["build"], cancelled=cancelled)
        exported = _hydrate(cast(Callable[[JsonValue], PayloadArchitectureExport], PayloadArchitectureExport.from_dict),
                            native.export, fingerprint=native.export_fingerprint, exact=_encoded(native.export),
                            label="architecture export")
        normalized_build = native.manifest["build"]
        hydrated = _build(normalized_build, native.build_fingerprint, exact=_encoded(normalized_build))
        return exported, hydrated, _verification(native.verification), native
    except CoreError as error:
        raise ArchitectureCoreError(operation, error) from error


def compile_architecture(request: PayloadArchitectureRequest, *, core: CoreClient,
                         cancelled: Callable[[], bool] | None = None) -> CompileOutcome:
    return compile_document(_input_document(request, PayloadArchitectureRequest, "compile-architecture"),
                            core=core, cancelled=cancelled)


def check_architecture(build: PayloadArchitectureBuild, *, expected_request: PayloadArchitectureRequest,
                       core: CoreClient, cancelled: Callable[[], bool] | None = None) -> CheckOutcome:
    return check_document(expected_request=_input_document(expected_request, PayloadArchitectureRequest, "verify-architecture"),
                          build=_input_document(build, PayloadArchitectureBuild, "verify-architecture"),
                          core=core, cancelled=cancelled)


def replay_architecture(receipt: PayloadArchitectureVerification, build: PayloadArchitectureBuild, *,
                        expected_request: PayloadArchitectureRequest, core: CoreClient,
                        cancelled: Callable[[], bool] | None = None) -> CheckOutcome:
    return replay_document(expected_request=_input_document(expected_request, PayloadArchitectureRequest, "replay-architecture"),
                           build=_input_document(build, PayloadArchitectureBuild, "replay-architecture"),
                           assessment=_input_document(receipt, PayloadArchitectureVerification, "replay-architecture"),
                           core=core, cancelled=cancelled)


def export_architecture(build: PayloadArchitectureBuild, *, expected_request: PayloadArchitectureRequest,
                        core: CoreClient, cancelled: Callable[[], bool] | None = None) -> ExportOutcome:
    return export_document(expected_request=_input_document(expected_request, PayloadArchitectureRequest, "export-architecture"),
                           build=_input_document(build, PayloadArchitectureBuild, "export-architecture"),
                           core=core, cancelled=cancelled)
