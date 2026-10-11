"""Typed authoring for one existing finite-machine component-material profile.

The source is a public ``BuildRequest``. Implementation models, components,
construction, providers and their bindings remain complete imported authority.
Import checks literal transport structure only; it never admits a mechanism,
repins a changed source or supplies missing molecular information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler import core_policy_component_material as component
from .model import BuildRequest
from .serialization import from_data, to_data

LIMITS_PROFILE = "biocompiler.policy_preservation_resources.v0.1"


class FiniteBuildError(ValueError):
    """Incomplete or unsupported literal finite-machine build description."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise FiniteBuildError(message)


def _object(value: JsonValue, names: set[str], label: str) -> dict[str, JsonValue]:
    _require(type(value) is dict and set(value) == names, label + " requires its complete closed fields")
    return cast(dict[str, JsonValue], value)


def _count(value: JsonValue, maximum: int, label: str) -> int:
    _require(type(value) is int and 0 < value <= maximum, label + " is outside its explicit finite allowance")
    return cast(int, value)


def _numbers(value: object, maxima: dict[str, int]) -> dict[str, JsonValue]:
    return {name: _count(getattr(value, name), maximum, name) for name, maximum in maxima.items()}


@dataclass(frozen=True, slots=True)
class SourceExecutionLimits:
    max_ticks: int
    max_inputs: int
    max_encounters: int
    max_attempts: int
    max_work: int
    max_trace_items: int
    max_microsteps: int

    def __post_init__(self) -> None:
        self.to_data()

    def to_data(self) -> dict[str, JsonValue]:
        return _numbers(self, {"max_ticks": 10_000, "max_inputs": 10_000, "max_encounters": 1_000,
            "max_attempts": 10_000, "max_work": 10_000_000, "max_trace_items": 100_000, "max_microsteps": 1_000})

    @classmethod
    def from_data(cls, value: JsonValue) -> SourceExecutionLimits:
        row = _object(value, {"max_ticks", "max_inputs", "max_encounters", "max_attempts", "max_work",
                              "max_trace_items", "max_microsteps"}, "Source execution limits")
        return cls(**cast(dict[str, int], row))


@dataclass(frozen=True, slots=True)
class CandidateExecutionLimits:
    max_work: int
    max_events: int
    max_attempts: int
    max_microsteps: int

    def __post_init__(self) -> None:
        self.to_data()

    def to_data(self) -> dict[str, JsonValue]:
        return _numbers(self, {"max_work": 10_000_000, "max_events": 1_000_000,
            "max_attempts": 10_000, "max_microsteps": 1_000})

    @classmethod
    def from_data(cls, value: JsonValue) -> CandidateExecutionLimits:
        row = _object(value, {"max_work", "max_events", "max_attempts", "max_microsteps"}, "Candidate execution limits")
        return cls(**cast(dict[str, int], row))


@dataclass(frozen=True, slots=True)
class RequirementMonitorLimits:
    max_work: int
    max_obligations: int
    max_samples: int

    def __post_init__(self) -> None:
        self.to_data()

    def to_data(self) -> dict[str, JsonValue]:
        return _numbers(self, {"max_work": 10_000_000, "max_obligations": 10_000, "max_samples": 1_000_000})

    @classmethod
    def from_data(cls, value: JsonValue) -> RequirementMonitorLimits:
        row = _object(value, {"max_work", "max_obligations", "max_samples"}, "Requirement monitor limits")
        return cls(**cast(dict[str, int], row))


@dataclass(frozen=True, slots=True)
class PreservationLimits:
    """Explicit caller budgets, with the existing native profile's hard ceilings."""
    source: SourceExecutionLimits
    candidate: CandidateExecutionLimits
    monitor: RequirementMonitorLimits
    max_step_work: int
    max_step_retained: int
    max_report_bytes: int
    max_report_nodes: int

    def __post_init__(self) -> None:
        _require(type(self.source) is SourceExecutionLimits and type(self.candidate) is CandidateExecutionLimits
                 and type(self.monitor) is RequirementMonitorLimits, "Use typed source, candidate and monitor limits")
        self.to_data()

    def to_data(self) -> dict[str, JsonValue]:
        return {"profile": LIMITS_PROFILE, "source": self.source.to_data(), "candidate": self.candidate.to_data(),
            "monitor": self.monitor.to_data(), **_numbers(self, {"max_step_work": 10_000_000,
                "max_step_retained": 1_000_000, "max_report_bytes": 8 * 1024 * 1024, "max_report_nodes": 1_000_000})}

    @classmethod
    def from_data(cls, value: JsonValue) -> PreservationLimits:
        row = _object(value, {"profile", "source", "candidate", "monitor", "max_step_work", "max_step_retained",
                              "max_report_bytes", "max_report_nodes"}, "Preservation limits")
        _require(row["profile"] == LIMITS_PROFILE, "Unsupported preservation resource profile")
        return cls(SourceExecutionLimits.from_data(row["source"]), CandidateExecutionLimits.from_data(row["candidate"]),
            RequirementMonitorLimits.from_data(row["monitor"]),
            **cast(dict[str, int], {name: row[name] for name in
                ("max_step_work", "max_step_retained", "max_report_bytes", "max_report_nodes")}))


def _request(value: JsonValue) -> dict[str, JsonValue]:
    row = component._original(value)
    _require((row["schema_version"], row["profile"]) ==
        (component.FINITE_MACHINE_REQUEST_SCHEMA, component.FINITE_MACHINE_REQUEST_PROFILE),
        "Typed finite builds require exactly the existing finite-machine component-material profile")
    original = cast(dict[str, JsonValue], row["implementation_request"])["document"]
    document = from_data(original, BuildRequest)
    _require(encode_json(cast(JsonValue, to_data(document))) == encode_json(original),
        "Typed source import must preserve the complete original document without normalization")
    return row


@dataclass(frozen=True, slots=True)
class FiniteMachineAuthority:
    """Complete supplied implementation/material authority, never inferred from source.

    The original document is retained for inspection. Binding a different typed
    document changes only that document; all catalog, component and context pins
    stay untouched and must pass a fresh native check.
    """
    _json: bytes

    def __post_init__(self) -> None:
        _require(type(self._json) is bytes, "Authority requires canonical literal JSON bytes")
        row = _request(decode_json(self._json))
        _require(encode_json(row) == self._json, "Authority bytes must be canonical")

    @classmethod
    def from_request(cls, request: JsonValue) -> FiniteMachineAuthority:
        return cls(encode_json(request))

    def to_data(self) -> dict[str, JsonValue]:
        """Return a detached copy of every supplied original, including source."""
        return cast(dict[str, JsonValue], decode_json(self._json))

    @property
    def original_document(self) -> BuildRequest:
        raw = cast(dict[str, JsonValue], self.to_data()["implementation_request"])["document"]
        return from_data(raw, BuildRequest)


@dataclass(frozen=True, slots=True)
class FiniteMachineBuild:
    """Typed source, complete supplied authority and explicit execution limits."""
    document: BuildRequest
    authority: FiniteMachineAuthority
    limits: PreservationLimits

    def __post_init__(self) -> None:
        _require(type(self.document) is BuildRequest and type(self.authority) is FiniteMachineAuthority
                 and type(self.limits) is PreservationLimits, "Use a BuildRequest, FiniteMachineAuthority and PreservationLimits")
        # Public source serialization rejects nonliteral values and preserves the
        # closed declaration registry. No Python evaluator or native process runs.
        object.__setattr__(self, "document", from_data(to_data(self.document), BuildRequest))
        _request(self.to_request())

    @classmethod
    def from_request(cls, request: JsonValue, *, limits: JsonValue) -> FiniteMachineBuild:
        authority = FiniteMachineAuthority.from_request(request)
        return cls(authority.original_document, authority, PreservationLimits.from_data(limits))

    def to_request(self) -> dict[str, JsonValue]:
        request = self.authority.to_data()
        cast(dict[str, JsonValue], request["implementation_request"])["document"] = cast(JsonValue, to_data(self.document))
        return request

    def to_limits(self) -> dict[str, JsonValue]:
        return self.limits.to_data()

    def with_document(self, document: BuildRequest) -> FiniteMachineBuild:
        """Explicit source edit; preserve every other original and never repin it."""
        return FiniteMachineBuild(document, self.authority, self.limits)
