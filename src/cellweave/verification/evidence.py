"""Immutable evidence for independently checked, finite-trace response contracts.

Result artifacts retain explicit claim scope, exercised coverage, source-linked
counterexamples and complete dependency identities. Model-conditional outcomes
remain distinct from empirical evidence and unresolved future obligations.
See docs/toolchain-contracts.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
from typing import Any

from cellweave.errors import SerializationError
from cellweave.ir.intent import SourceLocation, freeze_json, thaw_json
from cellweave.semantics.types import Interval, TypeSpec, decode_binding


class EvidenceKind(StrEnum):
    EXACT = "exact"
    MODEL_CONDITIONAL = "model_conditional"
    EMPIRICAL = "empirical"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Obligation:
    """A claim awaiting an independent check, not a certificate of correctness."""

    requirement_id: str
    description: str
    evidence_kind: EvidenceKind = EvidenceKind.UNRESOLVED
    evidence_refs: tuple[str, ...] = ()


class CheckOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


CLAIM_SCOPE = "Only the listed contract requirements, supplied input history, operating domain, and finite evaluation horizon were checked; this is not whole-program or universal biological refinement."


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SerializationError(message)


def _name(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_nonnegative(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except (OverflowError, ValueError):
        return False


def _canonical(value: Any) -> str:
    return json.dumps(
        thaw_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _fields(data: Any, names: set[str]) -> None:
    _require(
        isinstance(data, Mapping) and set(data) == names,
        "Invalid check artifact fields.",
    )


@dataclass(frozen=True)
class DependencySnapshot:
    """Exact, immutable inputs and tool identities supporting a finite-trace claim."""

    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        required = {
            "behavior",
            "behavior_artifact",
            "contract",
            "domain",
            "target",
            "mechanism",
            "observation_map",
            "history",
            "horizon",
            "checker",
            "model_runner",
            "reference_evaluator",
            "settings",
        }
        _require(
            isinstance(self.values, Mapping) and set(self.values) == required,
            "Dependencies must contain the complete checker input and tool inventory.",
        )
        _require(
            all(_name(key) for key in self.values),
            "Dependency names must be nonempty strings.",
        )
        for key in {
            "behavior",
            "behavior_artifact",
            "contract",
            "domain",
            "target",
            "mechanism",
            "observation_map",
            "history",
        }:
            value = self.values[key]
            _require(
                isinstance(value, str)
                and len(value) == 64
                and all(char in "0123456789abcdef" for char in value),
                f"Dependency {key} must be a SHA-256 fingerprint.",
            )
        _require(
            _name(self.values["checker"])
            and _name(self.values["model_runner"])
            and _name(self.values["reference_evaluator"]),
            "Tool versions must be nonempty strings.",
        )
        _require(
            isinstance(self.values["settings"], Mapping)
            and bool(self.values["settings"]),
            "Checker settings must be recorded.",
        )
        _fields(self.values["horizon"], {"until", "effective"})
        for key, value in self.values["horizon"].items():
            _require(
                key == "until" and value is None or _finite_nonnegative(value),
                "Invalid recorded evaluation horizon.",
            )
        object.__setattr__(self, "values", freeze_json(self.values))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.values).encode()).hexdigest()

    def changed(self, current: DependencySnapshot) -> tuple[str, ...]:
        if not isinstance(current, DependencySnapshot):
            raise TypeError("Freshness comparison requires a DependencySnapshot.")
        keys = set(self.values) | set(current.values)
        return tuple(
            sorted(
                key
                for key in keys
                if key not in self.values
                or key not in current.values
                or _canonical(self.values[key]) != _canonical(current.values[key])
            )
        )

    def to_dict(self) -> dict:
        return thaw_json(self.values)


@dataclass(frozen=True)
class FreshnessReport:
    changed_dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        _require(
            isinstance(self.changed_dependencies, (tuple, list))
            and all(_name(item) for item in self.changed_dependencies),
            "Invalid freshness dependencies.",
        )
        object.__setattr__(
            self, "changed_dependencies", tuple(self.changed_dependencies)
        )

    @property
    def fresh(self) -> bool:
        return not self.changed_dependencies

    @property
    def status(self) -> str:
        return "fresh" if self.fresh else "stale"


@dataclass(frozen=True)
class CheckDiagnostic:
    code: str
    message: str
    requirement_id: str | None = None
    node_id: str | None = None
    source: SourceLocation | None = None

    def __post_init__(self) -> None:
        _require(
            _name(self.code) and _name(self.message),
            "Diagnostic code and message must be nonempty.",
        )
        _require(
            all(
                value is None or _name(value)
                for value in (self.requirement_id, self.node_id)
            ),
            "Invalid diagnostic reference.",
        )
        _require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid diagnostic source.",
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "requirement_id": self.requirement_id,
            "node_id": self.node_id,
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> CheckDiagnostic:
        _fields(data, {"code", "message", "requirement_id", "node_id", "source"})
        return cls(
            data["code"],
            data["message"],
            data["requirement_id"],
            data["node_id"],
            SourceLocation.from_dict(data["source"])
            if data["source"] is not None
            else None,
        )


@dataclass(frozen=True)
class Counterexample:
    requirement_id: str
    time: float | int
    contact_id: str | None
    expected: Mapping[str, Any]
    actual: Any
    rule_id: str
    specification_id: str
    source: SourceLocation | None = None

    def __post_init__(self) -> None:
        _require(
            _name(self.requirement_id)
            and _name(self.rule_id)
            and _name(self.specification_id),
            "Invalid counterexample references.",
        )
        _require(
            _finite_nonnegative(self.time),
            "Invalid counterexample time.",
        )
        _require(
            self.contact_id is None or _name(self.contact_id),
            "Invalid counterexample contact.",
        )
        _fields(self.expected, {"state", "range"})
        _require(
            isinstance(self.expected["state"], str)
            and self.expected["state"] in {"active", "inactive"},
            "Counterexample state must be active or inactive.",
        )
        try:
            raw_range = self.expected["range"]
            _require(
                isinstance(raw_range, Mapping),
                "Counterexample range must be a typed interval.",
            )
            dtype = TypeSpec.from_dict(raw_range.get("type"))
            _require(
                dtype.kind == "interval",
                "Counterexample range must be a typed scalar interval.",
            )
            interval = decode_binding(raw_range, dtype)
            _require(
                isinstance(interval, Interval),
                "Counterexample range must be a typed scalar interval.",
            )
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            if isinstance(exc, SerializationError):
                raise
            raise SerializationError(f"Invalid counterexample range: {exc}") from exc
        try:
            valid_actual = (
                self.actual is None
                or type(self.actual) in (int, float)
                and math.isfinite(self.actual)
            )
        except (OverflowError, ValueError):
            valid_actual = False
        _require(
            valid_actual,
            "Counterexample actual must be a finite canonical scalar or null for a missing output.",
        )
        _require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid counterexample source.",
        )
        object.__setattr__(
            self,
            "expected",
            freeze_json({"state": self.expected["state"], "range": interval.to_dict()}),
        )
        object.__setattr__(self, "actual", freeze_json(self.actual))

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "time": self.time,
            "contact_id": self.contact_id,
            "expected": thaw_json(self.expected),
            "actual": thaw_json(self.actual),
            "rule_id": self.rule_id,
            "specification_id": self.specification_id,
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> Counterexample:
        _fields(
            data,
            {
                "requirement_id",
                "time",
                "contact_id",
                "expected",
                "actual",
                "rule_id",
                "specification_id",
                "source",
            },
        )
        return cls(
            data["requirement_id"],
            data["time"],
            data["contact_id"],
            data["expected"],
            data["actual"],
            data["rule_id"],
            data["specification_id"],
            SourceLocation.from_dict(data["source"])
            if data["source"] is not None
            else None,
        )


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_id: str
    activation_deadlines_checked: int = 0
    inactive_deadlines_checked: int = 0
    incomplete_episode_count: int = 0
    cancelled_episode_count: int = 0

    def __post_init__(self) -> None:
        _require(_name(self.requirement_id), "Invalid coverage requirement.")
        for name in (
            "activation_deadlines_checked",
            "inactive_deadlines_checked",
            "incomplete_episode_count",
            "cancelled_episode_count",
        ):
            value = getattr(self, name)
            _require(
                type(value) is int and value >= 0,
                "Coverage counts must be nonnegative integers.",
            )

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "activation_deadlines_checked": self.activation_deadlines_checked,
            "inactive_deadlines_checked": self.inactive_deadlines_checked,
            "incomplete_episode_count": self.incomplete_episode_count,
            "cancelled_episode_count": self.cancelled_episode_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> RequirementCoverage:
        _fields(
            data,
            {
                "requirement_id",
                "activation_deadlines_checked",
                "inactive_deadlines_checked",
                "incomplete_episode_count",
                "cancelled_episode_count",
            },
        )
        return cls(**data)


@dataclass(frozen=True)
class CheckResult:
    """A supplied-history claim, never universal refinement or biological evidence."""

    outcome: CheckOutcome
    dependencies: DependencySnapshot
    checked_requirement_ids: tuple[str, ...]
    diagnostics: tuple[CheckDiagnostic, ...] = ()
    counterexamples: tuple[Counterexample, ...] = ()
    evidence_kind: EvidenceKind = EvidenceKind.MODEL_CONDITIONAL
    claim_scope: str = CLAIM_SCOPE
    schema_version: str = "cellweave.realization_check.v0.1"
    coverage: tuple[RequirementCoverage, ...] = ()

    def __post_init__(self) -> None:
        _require(isinstance(self.outcome, CheckOutcome), "Invalid check outcome.")
        _require(
            isinstance(self.dependencies, DependencySnapshot),
            "Invalid check dependencies.",
        )
        _require(
            self.evidence_kind is EvidenceKind.MODEL_CONDITIONAL,
            "This checker only reports model-conditional evidence.",
        )
        _require(
            self.schema_version == "cellweave.realization_check.v0.1"
            and self.claim_scope == CLAIM_SCOPE,
            "Invalid check schema or scope.",
        )
        for name, item_type in (
            ("diagnostics", CheckDiagnostic),
            ("counterexamples", Counterexample),
            ("coverage", RequirementCoverage),
        ):
            value = getattr(self, name)
            _require(
                isinstance(value, (tuple, list))
                and all(isinstance(item, item_type) for item in value),
                f"Invalid {name}.",
            )
            object.__setattr__(self, name, tuple(value))
        _require(
            isinstance(self.checked_requirement_ids, (tuple, list))
            and all(_name(item) for item in self.checked_requirement_ids),
            "Invalid checked requirements.",
        )
        _require(
            len(set(self.checked_requirement_ids)) == len(self.checked_requirement_ids),
            "Duplicate checked requirements.",
        )
        object.__setattr__(
            self, "checked_requirement_ids", tuple(self.checked_requirement_ids)
        )
        _require(
            not self.counterexamples or self.outcome is CheckOutcome.FAIL,
            "Counterexamples require a failed outcome.",
        )
        _require(
            self.outcome is not CheckOutcome.PASS or bool(self.checked_requirement_ids),
            "A passing check must identify checked requirements.",
        )
        known = set(self.checked_requirement_ids)
        _require(
            all(item.requirement_id in known for item in self.counterexamples),
            "Counterexample refers to an unknown requirement.",
        )
        _require(
            all(
                item.requirement_id is None or item.requirement_id in known
                for item in self.diagnostics
            ),
            "Diagnostic refers to an unknown requirement.",
        )
        coverage_ids = [item.requirement_id for item in self.coverage]
        _require(
            len(set(coverage_ids)) == len(coverage_ids) and set(coverage_ids) <= known,
            "Invalid requirement coverage references.",
        )
        if self.outcome is CheckOutcome.PASS:
            _require(
                not self.diagnostics and not self.counterexamples,
                "A passing result cannot contain unresolved diagnostics or counterexamples.",
            )
            _require(
                set(coverage_ids) == known
                and all(
                    item.activation_deadlines_checked > 0
                    and item.inactive_deadlines_checked > 0
                    and item.incomplete_episode_count == 0
                    for item in self.coverage
                ),
                "A passing result requires exercised active and inactive deadlines and complete response coverage.",
            )

    @property
    def passed(self) -> bool:
        return self.outcome is CheckOutcome.PASS

    @property
    def exercised_requirement_ids(self) -> tuple[str, ...]:
        return tuple(
            item.requirement_id
            for item in self.coverage
            if item.activation_deadlines_checked > 0
            and item.inactive_deadlines_checked > 0
        )

    def freshness(self, current: DependencySnapshot) -> FreshnessReport:
        return FreshnessReport(self.dependencies.changed(current))

    def is_fresh(self, current: DependencySnapshot) -> bool:
        return self.freshness(current).fresh

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "outcome": self.outcome.value,
            "evidence_kind": self.evidence_kind.value,
            "claim_scope": self.claim_scope,
            "dependencies": self.dependencies.to_dict(),
            "checked_requirement_ids": list(self.checked_requirement_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "counterexamples": [item.to_dict() for item in self.counterexamples],
            "coverage": [item.to_dict() for item in self.coverage],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, indent=indent, allow_nan=False
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()

    @classmethod
    def from_dict(cls, data: Mapping) -> CheckResult:
        _fields(
            data,
            {
                "schema_version",
                "outcome",
                "evidence_kind",
                "claim_scope",
                "dependencies",
                "checked_requirement_ids",
                "diagnostics",
                "counterexamples",
                "coverage",
            },
        )
        _require(
            isinstance(data["diagnostics"], (list, tuple))
            and isinstance(data["counterexamples"], (list, tuple))
            and isinstance(data["coverage"], (list, tuple)),
            "Check details must be arrays.",
        )
        try:
            return cls(
                CheckOutcome(data["outcome"]),
                DependencySnapshot(data["dependencies"]),
                data["checked_requirement_ids"],
                tuple(CheckDiagnostic.from_dict(item) for item in data["diagnostics"]),
                tuple(
                    Counterexample.from_dict(item) for item in data["counterexamples"]
                ),
                EvidenceKind(data["evidence_kind"]),
                data["claim_scope"],
                data["schema_version"],
                tuple(RequirementCoverage.from_dict(item) for item in data["coverage"]),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, SerializationError):
                raise
            raise SerializationError(f"Invalid check result: {exc}") from exc

    @classmethod
    def from_json(cls, text: str) -> CheckResult:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                _require(key not in result, f"Duplicate JSON key: {key}.")
                result[key] = value
            return result

        def invalid(value):
            raise SerializationError(f"Invalid JSON number: {value}.")

        try:
            data = json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
        except (TypeError, json.JSONDecodeError, RecursionError) as exc:
            raise SerializationError(f"Invalid check JSON: {exc}") from exc
        return cls.from_dict(data)
