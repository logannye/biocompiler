"""Immutable inspection views for explicitly selected native synthetic producers.

These views are distinct from the legacy semantic classes. Their complete JSON
can be copied, edited and submitted as untrusted input to a fresh core operation.
Output decoding never constructs a Python mechanism, selects a strategy, checks
a model, or promotes retained evidence to current acceptance.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Protocol, cast

from biocompiler.core_client import (
    LIMITS, CoreClient, CoreError, CoreProtocolError, CoreRejected, Diagnostic,
    JsonValue, decode_json, encode_json,
)
from biocompiler.core_synthetic_producer import NativeSyntheticProduction, SyntheticProducerClient
from biocompiler.core_synthetic_inspection import NativeSyntheticInspection, SyntheticInspectionClient
from biocompiler.errors import SerializationError, UnsupportedBehaviorError

_INPUT_SERIALIZATION: ContextVar[bool] = ContextVar("synthetic_producer_input_serialization", default=False)
VIEW_PROFILE = "biocompiler.python.native_synthetic_producer_views.v1"


def serializing_legacy_input() -> bool:
    """The only phase where pinned legacy input serializers may execute."""
    return _INPUT_SERIALIZATION.get()


class SyntheticProducerCoreError(SerializationError):
    """Preserve complete selected-core diagnostics without trying a fallback."""
    def __init__(self, operation: str, core_error: CoreError) -> None:
        self.operation = operation
        self.core_error = core_error
        self.diagnostics: tuple[Diagnostic, ...] = (
            core_error.response.diagnostics if isinstance(core_error, CoreRejected) else ())
        super().__init__(f"{operation} failed: {core_error}")


class _TypedInput(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def _bytes(value: Any, *, ascii_only: bool = False) -> bytes:
    # All decoded output is already bounded; canonicalization also bounds the
    # expansion of copied input and pretty JSON below.
    limit = LIMITS["max_response_bytes"]
    if not ascii_only:
        return encode_json(cast(JsonValue, value), limit=limit)
    return _json(value, None, ascii_only=True, compact=True).encode("ascii")


def _json(value: Any, indent: int | None, *, ascii_only: bool = False, compact: bool = False) -> str:
    if indent is not None and (type(indent) is not int or indent > LIMITS["max_response_bytes"]):
        raise CoreProtocolError("Invalid native producer JSON indentation")
    encoder = json.JSONEncoder(sort_keys=True, indent=indent, ensure_ascii=ascii_only, allow_nan=False,
        separators=(",", ":") if compact else None)
    chunks: list[str] = []
    size = 0
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode("utf-8"))
        if size > LIMITS["max_response_bytes"]:
            raise CoreProtocolError("Native producer JSON exceeds the response byte limit")
        chunks.append(chunk)
    return "".join(chunks)


def _thaw(value: Any) -> Any:
    if isinstance(value, NativeProducerDocument):
        return value.to_dict()
    if isinstance(value, NativeEnumValue):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_thaw(item) for item in value]
    return value


class NativeEnumValue(str):
    """Read-only spelling of a native decision, compatible with string enums."""
    __slots__ = ()

    @property
    def value(self) -> str:
        return str(self)


@dataclass(frozen=True, slots=True, eq=False)
class NativeProducerDocument:
    _data: Mapping[str, Any]
    _canonical_json: bytes
    _native: NativeSyntheticProduction | None = None
    _extras: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    _core: CoreClient | None = None
    _inspection: NativeSyntheticInspection | None = None

    def __getattr__(self, name: str) -> Any:
        if name in self._extras:
            return self._extras[name]
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        # Decode the retained bytes, independently of presentation aliases.
        return cast(dict[str, Any], decode_json(self._canonical_json))

    def to_json(self, *, indent: int | None = 2) -> str:
        return _json(self.to_dict(), indent, ascii_only=isinstance(self, (NativeMechanismProgram, NativeCheckResult)))

    @property
    def canonical_json(self) -> bytes:
        return self._canonical_json

    @property
    def fingerprint(self) -> str:
        raw = _bytes(self.to_dict(), ascii_only=True) if isinstance(self, (NativeCheckResult, NativeDependencies)) else self._canonical_json
        return hashlib.sha256(raw).hexdigest()

    @property
    def native_result(self) -> NativeSyntheticProduction | None:
        return self._native

    @property
    def native_inspection(self) -> NativeSyntheticInspection | None:
        return self._inspection

    def _inspect(self, operation: str, **authority: JsonValue) -> NativeSyntheticInspection:
        if self._core is None:
            raise UnsupportedBehaviorError("Native " + operation + " inspection requires an explicit core context; historical bytes grant no fresh acceptance.")
        try:
            return SyntheticInspectionClient(self._core).call(operation, **cast(Any, authority))
        except CoreRejected as error:
            if error.response.status == "error" and len(error.response.diagnostics) == 1:
                diagnostic = error.response.diagnostics[0]
                original: Exception = (TypeError(diagnostic.message) if diagnostic.code == "synthetic_inspection_type"
                                       else SerializationError(diagnostic.message))
                setattr(original, "core_error", error)
                setattr(original, "diagnostics", error.response.diagnostics)
                setattr(original, "operation", operation)
                raise original from error
            raise SyntheticProducerCoreError(operation, error) from error
        except CoreError as error:
            raise SyntheticProducerCoreError(operation, error) from error

    @classmethod
    def from_dict(cls, document: Mapping[str, Any], *, core: CoreClient | None = None) -> NativeProducerDocument:
        # Historical views carry no core receipt and no fresh authority.
        raw = decode_json(_bytes(_thaw(document)))
        if type(raw) is not dict:
            raise CoreProtocolError("Native producer view requires a complete object")
        view = _view(raw, field="dependencies" if cls is NativeDependencies else "", core=core)
        if cls is not NativeProducerDocument and type(view) is not cls:
            raise CoreProtocolError("Historical producer view schema differs from the selected class")
        return view

    @classmethod
    def from_json(cls, text: str, *, core: CoreClient | None = None) -> NativeProducerDocument:
        if type(text) is not str:
            raise CoreProtocolError("Native producer JSON must be text")
        raw = decode_json(text.encode("utf-8"))
        if type(raw) is not dict:
            raise CoreProtocolError("Native producer JSON must be an object")
        return cls.from_dict(raw, core=core)

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self._canonical_json == cast(NativeProducerDocument, other)._canonical_json

    def __hash__(self) -> int:
        return hash((type(self), self._canonical_json))


class NativeSyntheticCandidate(NativeProducerDocument):
    __slots__ = ()


class NativeSyntheticGeneratorConfig(NativeProducerDocument):
    __slots__ = ()


class NativeSyntheticAlternative(NativeProducerDocument):
    __slots__ = ()


class NativeSyntheticSelectionResult(NativeProducerDocument):
    __slots__ = ()

    @property
    def candidate(self) -> NativeSyntheticCandidate | None:
        selected = self._data["selected_strategy"]
        if selected is None:
            return None
        # This follows an explicit native identity; it never ranks alternatives.
        matches = [item for item in self._data["alternatives"] if item.strategy == selected]
        if len(matches) != 1 or matches[0].candidate is None:
            raise CoreProtocolError("Native selected strategy does not name one retained candidate")
        return cast(NativeSyntheticCandidate, matches[0].candidate)


class NativeSyntheticComposition(NativeProducerDocument):
    __slots__ = ()


class NativeMechanismProgram(NativeProducerDocument):
    __slots__ = ()

    def get(self, node_id: str) -> NativeProducerDocument:
        for node in self._data["nodes"]:
            if node.id == node_id:
                return cast(NativeProducerDocument, node)
        raise KeyError(node_id)

    def find(self, kind: str) -> tuple[NativeProducerDocument, ...]:
        return tuple(node for node in self._data["nodes"] if node.kind == kind)

    def topological_nodes(self) -> tuple[NativeProducerDocument, ...]:
        result = self._inspect("inspect-synthetic-mechanism", mechanism=self.to_dict())
        return tuple(_view(node, core=self._core, inspection=result) for node in result.value["nodes"])


class NativeComponentRecord(NativeProducerDocument):
    __slots__ = ()

    def port(self, port_id: str) -> NativeProducerDocument:
        for port in self._data["ports"]:
            if port.id == port_id:
                return cast(NativeProducerDocument, port)
        raise KeyError(port_id)


class NativeComponentRegistry(NativeProducerDocument):
    __slots__ = ()

    def resolve(self, lock: Any) -> dict[str, NativeComponentRecord]:
        result = self._inspect("resolve-synthetic-registry", registry=self.to_dict(), lock=_inspection_input(lock, kind="registry_lock"))
        return {key: cast(NativeComponentRecord, _view(raw, core=self._core, inspection=result))
                for key, raw in result.value["instances"].items()}

    def lock(self, instances: Any) -> NativeProducerDocument:
        supplied = ({key: _inspection_input(item, kind="component") for key, item in instances.items()}
                    if isinstance(instances, Mapping) else _inspection_input(instances, kind="component"))
        result = self._inspect("lock-synthetic-registry", registry=self.to_dict(), instances=supplied)
        return _view(result.value["lock"], core=self._core, inspection=result)

    def select(self, request: Any) -> NativeComponentSelectionResult:
        result = self._inspect("select-synthetic-registry", registry=self.to_dict(), request=_inspection_input(request, kind="selection_request"))
        return cast(NativeComponentSelectionResult, _view(result.value["selection"], core=self._core, inspection=result,
                    presentation={"outcome": result.value["outcome"]}))

    def verify_selection(self, request: Any, result: Any) -> bool:
        inspected = self._inspect("verify-synthetic-registry-selection", registry=self.to_dict(),
            request=_inspection_input(request, kind="selection_request"), selection=_inspection_input(result, kind="selection"))
        return cast(bool, inspected.value["valid"])


class NativeComponentSelectionResult(NativeProducerDocument):
    __slots__ = ()

    @property
    def outcome(self) -> str:
        if "outcome" in self._extras:
            return cast(str, self._extras["outcome"])
        result = self._inspect("inspect-synthetic-registry-selection", selection=self.to_dict())
        return cast(str, result.value["outcome"])


class NativeFreshnessReport(NativeProducerDocument):
    __slots__ = ()


class NativeCheckResult(NativeProducerDocument):
    __slots__ = ()

    @property
    def passed(self) -> bool:
        """A display alias for the recorded native outcome, not a fresh check."""
        return bool(self._data["outcome"] == "pass")

    @property
    def exercised_requirement_ids(self) -> tuple[str, ...]:
        result = self._inspect("inspect-synthetic-check-result", record=self.to_dict(), query="coverage", current=None)
        return tuple(result.value["exercised_requirement_ids"])

    def freshness(self, current: Any) -> NativeFreshnessReport:
        result = self._inspect("inspect-synthetic-check-result", record=self.to_dict(), query="freshness", current=_inspection_input(current, kind="dependencies"))
        freshness = result.value["freshness"]
        return cast(NativeFreshnessReport, _view({"changed_dependencies": freshness["changed_dependencies"]},
            core=self._core, inspection=result, field="freshness",
            presentation={"fresh": freshness["fresh"], "status": freshness["status"]}))

    def is_fresh(self, current: Any) -> bool:
        return cast(bool, self.freshness(current).fresh)


class NativeDependencies(NativeProducerDocument):
    __slots__ = ()

    @property
    def values(self) -> Mapping[str, Any]:
        return self._data

    def changed(self, current: Any) -> tuple[str, ...]:
        result = self._inspect("compare-synthetic-dependencies", previous=self.to_dict(), current=_inspection_input(current, kind="dependencies"))
        return tuple(result.value["changed_dependencies"])


class NativeSourceLocation(NativeProducerDocument):
    __slots__ = ()


_SCHEMAS: dict[str, type[NativeProducerDocument]] = {
    "biocompiler.synthetic_candidate.v0.4": NativeSyntheticCandidate,
    "biocompiler.synthetic_generator_config.v0.3": NativeSyntheticGeneratorConfig,
    "biocompiler.synthetic_alternative.v0.1": NativeSyntheticAlternative,
    "biocompiler.synthetic_selection_result.v0.1": NativeSyntheticSelectionResult,
    "biocompiler.mechanism.synthetic.v0.2": NativeMechanismProgram,
    "biocompiler.component_record.v0.2": NativeComponentRecord,
    "biocompiler.component_registry.v0.2": NativeComponentRegistry,
    "biocompiler.realization_check.v0.1": NativeCheckResult,
    "biocompiler.component_selection_result.v0.2": NativeComponentSelectionResult,
}
_MAPPINGS = {"attributes", "source_map", "behavior_requirement_ids", "constraints", "expected", "actual", "settings"}


def _plain(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _plain(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_plain(item) for item in value)
    return value


def _freeze(value: Any, *, field: str = "", native: NativeSyntheticProduction | None = None,
            core: CoreClient | None = None, inspection: NativeSyntheticInspection | None = None) -> Any:
    if type(value) is dict:
        if field in _MAPPINGS:
            if field == "constraints":
                return MappingProxyType({key: _freeze(item, native=native, core=core, inspection=inspection) for key, item in value.items()})
            return _plain(value)
        return _view(value, field=field, native=native, core=core, inspection=inspection)
    if type(value) is list:
        return tuple(_freeze(item, native=native, core=core, inspection=inspection) for item in value)
    return value


def _view(raw: dict[str, Any], *, field: str = "", native: NativeSyntheticProduction | None = None,
          core: CoreClient | None = None, inspection: NativeSyntheticInspection | None = None,
          presentation: Mapping[str, Any] | None = None) -> NativeProducerDocument:
    cls = _SCHEMAS.get(raw.get("schema_version", ""), NativeProducerDocument)
    if set(raw) == {"registry", "composition", "acceptance"}:
        cls = NativeSyntheticComposition
    elif field == "dependencies" and "checker" in raw:
        cls = NativeDependencies
    elif field == "freshness":
        cls = NativeFreshnessReport
    elif set(raw) == {"file", "line", "function"}:
        cls = NativeSourceLocation
    values = {key: _freeze(value, field=key, native=native, core=core, inspection=inspection) for key, value in raw.items()}
    extras: dict[str, Any] = {} if presentation is None else dict(presentation)
    if cls is NativeDependencies:
        values = {key: _plain(value) for key, value in raw.items()}
    if cls is NativeCheckResult:
        for key in ("outcome", "evidence_kind"):
            if type(raw[key]) is not str:
                raise CoreProtocolError("Native check decision must be a string")
            values[key] = NativeEnumValue(raw[key])
    if set(raw) == {"id", "kind", "output", "inputs", "attributes", "requirement_ids"}:
        output = values["output"]
        extras = {key: getattr(output, key) for key in ("role", "scope", "compartment")}
        extras["data_type"] = _freeze(raw["output"]["dtype"], field="attributes")
    if set(raw) == {"kind", "name", "dimensions", "arguments"}:
        extras["dimensions"] = tuple(raw["dimensions"].items())
    return cls(MappingProxyType(values), _bytes(raw), native, MappingProxyType(extras), core, inspection)


def _input(value: Any, *, kind: str) -> JsonValue:
    if type(value) is bytes:
        return decode_json(value, limit=LIMITS["max_request_bytes"])
    if isinstance(value, NativeProducerDocument):
        return cast(JsonValue, value.to_dict())
    if isinstance(value, Mapping):
        return cast(JsonValue, _thaw(value))
    if value is None:
        return None
    expected = {
        "request": ("biocompiler.compiler.request", "RealizationRequest"),
        "candidate": ("biocompiler.synthesis.synthetic", "SyntheticCandidate"),
        "config": ("biocompiler.synthesis.synthetic", "SyntheticGeneratorConfig"),
        "frame": ("biocompiler.semantics.evaluator", "InputFrame"),
        "registry_lock": ("biocompiler.registry.components", "RegistryLock"),
        "component": ("biocompiler.ir.component_contracts", "ComponentRecord"),
        "selection_request": ("biocompiler.registry.components", "SelectionRequest"),
        "selection": ("biocompiler.registry.components", "SelectionResult"),
        "dependencies": ("biocompiler.verification.evidence", "DependencySnapshot"),
    }[kind]
    if (type(value).__module__, type(value).__name__) != expected:
        raise CoreProtocolError("Expected an authored " + kind + ", raw JSON bytes, mapping or native view")
    token = _INPUT_SERIALIZATION.set(True)
    try:
        return cast(JsonValue, cast(_TypedInput, value).to_dict())
    finally:
        _INPUT_SERIALIZATION.reset(token)


def _inspection_input(value: Any, *, kind: str) -> JsonValue:
    if type(value) in (str, int, float, bool, list, tuple):
        return cast(JsonValue, _thaw(value))
    return _input(value, kind=kind)


def _history(value: Any) -> JsonValue:
    if type(value) is bytes:
        return decode_json(value, limit=LIMITS["max_request_bytes"])
    if not isinstance(value, Iterable) or isinstance(value, (str, Mapping)):
        raise CoreProtocolError("Expected complete frame history")
    result: list[JsonValue] = []
    for index, frame in enumerate(value):
        if index >= LIMITS["max_json_nodes"]:
            raise CoreProtocolError("Native producer history exceeds the node limit")
        result.append(_input(frame, kind="frame"))
    return result


def view_result(native: NativeSyntheticProduction, *, core: CoreClient | None = None) -> NativeProducerDocument:
    if native.outcome == "unsupported":
        detail = native.generation_error
        if detail is None:
            raise CoreProtocolError("Missing complete native Unsupported detail")
        source = None if detail["source"] is None else cast(NativeSourceLocation, _view(detail["source"]))
        error = UnsupportedBehaviorError(detail["message"], node_id=detail["node_id"], source=source)
        if str(error) != detail["formatted"]:
            raise CoreProtocolError("Native Unsupported detail changed during public presentation")
        raise error
    raw = native.record
    if raw is None:
        raise CoreProtocolError("Missing complete native producer record")
    view = _view(raw, native=native, core=core)
    if view.canonical_json != native.record_json:
        raise CoreProtocolError("Public native producer view changed the complete record")
    return view


def _run(operation: str, core: CoreClient, invoke: Callable[[SyntheticProducerClient], NativeSyntheticProduction]) -> NativeProducerDocument:
    try:
        if not isinstance(core, CoreClient):
            raise CoreProtocolError("An explicit CoreClient is required for native production")
        if core.role != "core":
            raise CoreProtocolError("Synthetic production requires the core executable role")
        return view_result(invoke(SyntheticProducerClient(core)), core=core)
    except CoreError as error:
        raise SyntheticProducerCoreError(operation, error) from error


def generate_record(request: Any, *, config: Any = None, core: CoreClient) -> NativeSyntheticCandidate:
    return cast(NativeSyntheticCandidate, _run("generate-synthetic", core,
        lambda client: client.generate(request=_input(request, kind="request"), config=_input(config, kind="config"))))


def select_record(request: Any, history: Any, *, until: JsonValue = None, config: Any = None,
                  core: CoreClient) -> NativeSyntheticSelectionResult:
    return cast(NativeSyntheticSelectionResult, _run("select-synthetic", core,
        lambda client: client.select(request=_input(request, kind="request"), history=_history(history), until=until,
                                     config=_input(config, kind="config"))))


def adapt_record(request: Any, candidate: Any, history: Any, *, until: JsonValue = None,
                 core: CoreClient) -> NativeSyntheticComposition:
    return cast(NativeSyntheticComposition, _run("adapt-synthetic-components", core,
        lambda client: client.adapt(request=_input(request, kind="request"), candidate=_input(candidate, kind="candidate"),
                                    history=_history(history), until=until)))
