"""Finite-trace operating domains and explicit observable response contracts.

These artifacts bind abstract behavior to named measurements and response
windows. They do not specify a molecular mechanism or prove behavior outside a
checked history. Endpoint identity, compartment and scope are semantic fields;
dimensional compatibility alone never establishes their correspondence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, ClassVar

from cellweave.errors import SerializationError, TypeMismatchError
from cellweave.ir.serialization import JsonArtifact, fields, name, names, require
from cellweave.semantics.types import (
    BOOLEAN,
    DURATION,
    Interval,
    ScalarLiteral,
    TypeSpec,
    decode_binding,
    to_type_spec,
)


def _type(value: Any) -> TypeSpec:
    try:
        return to_type_spec(value)
    except (TypeError, ValueError) as exc:
        raise SerializationError(f"Invalid observable type: {exc}") from exc


def _duration(value: Any, label: str, *, positive: bool = False) -> ScalarLiteral:
    require(
        isinstance(value, ScalarLiteral), f"{label} requires a typed Duration literal."
    )
    try:
        result = decode_binding(value.to_dict(), DURATION)
    except (TypeMismatchError, ValueError, AttributeError) as exc:
        raise SerializationError(f"Invalid {label}: {exc}") from exc
    require(
        result.canonical_value > 0 if positive else result.canonical_value >= 0,
        f"{label} must be {'positive' if positive else 'nonnegative'}.",
    )
    return result


def _interval(value: Any, expected: TypeSpec, label: str) -> Interval:
    require(isinstance(value, Interval), f"{label} must be a typed Interval.")
    try:
        return decode_binding(value.to_dict(), Interval[expected])
    except (TypeError, ValueError, AttributeError) as exc:
        raise SerializationError(f"Invalid {label}: {exc}") from exc


def _decode(data: Any, dtype: TypeSpec, label: str):
    try:
        return decode_binding(data, dtype)
    except (TypeError, ValueError, KeyError) as exc:
        raise SerializationError(f"Invalid {label}: {exc}") from exc


def _schema(data: Any, cls: type, keys: set[str]) -> None:
    fields(data, keys | {"schema_version"}, cls.__name__)
    require(
        data["schema_version"] == cls.schema_version,
        f"Unsupported {cls.__name__} schema.",
    )


def _inside(interval: Interval, value: Any) -> bool:
    if isinstance(value, ScalarLiteral):
        try:
            value = decode_binding(
                value.to_dict(), interval.dtype.arguments[0]
            ).canonical_value
        except (TypeError, ValueError, AttributeError):
            return False
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return (
            math.isfinite(value)
            and interval.lower.canonical_value
            <= value
            <= interval.upper.canonical_value
        )
    except (OverflowError, ValueError):
        return False


@dataclass(frozen=True)
class Observable(JsonArtifact):
    """A semantic measurement endpoint, independently of a graph node identity."""

    id: str
    dtype: TypeSpec
    role: str
    scope: str = "cell"
    compartment: str = "abstract"
    schema_version: ClassVar[str] = "cellweave.observable.v0.1"

    def __post_init__(self) -> None:
        name(self.id, "Observable id")
        name(self.role, "Observable role")
        name(self.compartment, "Observable compartment")
        require(
            isinstance(self.scope, str) and self.scope in {"cell", "contact"},
            "Observable scope must be cell or contact.",
        )
        dtype = _type(self.dtype)
        require(
            dtype.kind in {"scalar", "condition"},
            "This observable profile supports scalar and Boolean measurements.",
        )
        object.__setattr__(self, "dtype", dtype)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "dtype": self.dtype.to_dict(),
            "role": self.role,
            "scope": self.scope,
            "compartment": self.compartment,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> Observable:
        _schema(data, cls, {"id", "dtype", "role", "scope", "compartment"})
        try:
            dtype = TypeSpec.from_dict(data["dtype"])
        except (TypeError, ValueError, KeyError) as exc:
            raise SerializationError(f"Invalid observable type: {exc}") from exc
        return cls(data["id"], dtype, data["role"], data["scope"], data["compartment"])


@dataclass(frozen=True)
class InputDomain(JsonArtifact):
    """Admissible canonical observations of one field of a behavior signal."""

    signal_id: str
    field: str
    observable: Observable
    allowed: tuple[bool, ...] | Interval
    schema_version: ClassVar[str] = "cellweave.input_domain.v0.1"

    def __post_init__(self) -> None:
        name(self.signal_id, "Behavior signal id")
        require(
            isinstance(self.field, str)
            and self.field in {"value", "present", "high", "low"},
            "Unknown input observation field.",
        )
        require(
            isinstance(self.observable, Observable),
            "InputDomain requires an Observable.",
        )
        if self.field == "value":
            require(
                self.observable.dtype.kind == "scalar",
                "Numeric observations require a scalar observable.",
            )
            object.__setattr__(
                self,
                "allowed",
                _interval(self.allowed, self.observable.dtype, "input range"),
            )
        else:
            require(
                self.observable.dtype.compatible(BOOLEAN),
                "Qualitative observations require a Boolean observable.",
            )
            require(
                isinstance(self.allowed, (tuple, list))
                and bool(self.allowed)
                and all(type(value) is bool for value in self.allowed),
                "Qualitative input domain must be a nonempty array of Booleans.",
            )
            require(
                len(set(self.allowed)) == len(self.allowed),
                "Allowed Boolean values must be unique.",
            )
            object.__setattr__(self, "allowed", tuple(sorted(self.allowed)))

    @property
    def scope(self) -> str:
        return self.observable.scope

    @property
    def role(self) -> str:
        return self.observable.role

    def contains(self, value: Any) -> bool:
        """Check a supplied value in canonical units, without inferring thresholds."""
        if isinstance(self.allowed, Interval):
            return _inside(self.allowed, value)
        return type(value) is bool and value in self.allowed

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "signal_id": self.signal_id,
            "field": self.field,
            "observable": self.observable.to_dict(),
            "allowed": self.allowed.to_dict()
            if isinstance(self.allowed, Interval)
            else list(self.allowed),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> InputDomain:
        _schema(data, cls, {"signal_id", "field", "observable", "allowed"})
        observable = Observable.from_dict(data["observable"])
        allowed = (
            _decode(data["allowed"], Interval[observable.dtype], "input range")
            if data["field"] == "value" and observable.dtype.kind == "scalar"
            else data["allowed"]
        )
        return cls(data["signal_id"], data["field"], observable, allowed)


@dataclass(frozen=True)
class OperatingDomain(JsonArtifact):
    """Declared bounds for histories of one selected cell role.

    Contact identity is the stable key in each supplied contact snapshot, with
    episode semantics supplied by the Behavior IR. max_contacts bounds concurrent
    objects; it does not collapse distinct identities or assert co-delivery.
    """

    id: str
    version: str
    role: str
    inputs: tuple[InputDomain, ...]
    minimum_horizon: ScalarLiteral
    max_contacts: int | None = None
    required_capabilities: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "cellweave.operating_domain.v0.1"

    def __post_init__(self) -> None:
        name(self.id, "Operating domain id")
        name(self.version, "Operating domain version")
        name(self.role, "Operating domain role")
        require(
            isinstance(self.inputs, (tuple, list))
            and bool(self.inputs)
            and all(isinstance(item, InputDomain) for item in self.inputs),
            "Operating domain requires a nonempty array of InputDomain records.",
        )
        inputs = tuple(
            sorted(self.inputs, key=lambda item: (item.signal_id, item.field))
        )
        require(
            len({(item.signal_id, item.field) for item in inputs}) == len(inputs),
            "Input domains must have unique signal/field identities.",
        )
        require(
            len({item.observable.id for item in inputs}) == len(inputs),
            "Input measurement endpoint ids must be unique.",
        )
        require(
            all(item.role == self.role for item in inputs),
            "All input domains must belong to the selected role.",
        )
        by_signal = {}
        for item in inputs:
            meaning = (item.scope, item.observable.compartment)
            require(
                item.signal_id not in by_signal or by_signal[item.signal_id] == meaning,
                "Fields of one signal must agree on scope and compartment.",
            )
            by_signal[item.signal_id] = meaning
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(
            self,
            "minimum_horizon",
            _duration(self.minimum_horizon, "minimum horizon", positive=True),
        )
        require(
            self.max_contacts is None
            or type(self.max_contacts) is int
            and self.max_contacts >= 0,
            "max_contacts must be a nonnegative integer or None.",
        )
        require(
            self.max_contacts != 0
            or not any(item.scope == "contact" for item in inputs),
            "A contact input domain needs a nonzero allowed contact bound.",
        )
        object.__setattr__(
            self,
            "required_capabilities",
            tuple(sorted(names(self.required_capabilities, "Required capabilities"))),
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "version": self.version,
            "role": self.role,
            "inputs": [item.to_dict() for item in self.inputs],
            "minimum_horizon": self.minimum_horizon.to_dict(),
            "max_contacts": self.max_contacts,
            "required_capabilities": list(self.required_capabilities),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> OperatingDomain:
        _schema(
            data,
            cls,
            {
                "id",
                "version",
                "role",
                "inputs",
                "minimum_horizon",
                "max_contacts",
                "required_capabilities",
            },
        )
        require(
            isinstance(data["inputs"], (tuple, list)),
            "Operating domain inputs must be an array.",
        )
        return cls(
            data["id"],
            data["version"],
            data["role"],
            tuple(InputDomain.from_dict(item) for item in data["inputs"]),
            _decode(data["minimum_horizon"], DURATION, "minimum horizon"),
            data["max_contacts"],
            data["required_capabilities"],
        )


@dataclass(frozen=True)
class ResponseRequirement(JsonArtifact):
    """A rule/action request must reach its range within explicit time bounds.

    Both intervals are closed and disjoint. Delays use canonical seconds and may
    be zero. The checker must evaluate inactive behavior as well as required
    activation; an always-silent candidate cannot satisfy an active response.
    """

    id: str
    rule_id: str
    specification_id: str
    observable: Observable
    active_range: Interval
    inactive_range: Interval
    max_activation_delay: ScalarLiteral
    max_deactivation_delay: ScalarLiteral
    schema_version: ClassVar[str] = "cellweave.response_requirement.v0.1"

    def __post_init__(self) -> None:
        name(self.id, "Response requirement id")
        name(self.rule_id, "Behavior rule id")
        name(self.specification_id, "Behavior action specification id")
        require(
            isinstance(self.observable, Observable)
            and self.observable.dtype.kind == "scalar",
            "Response ranges require a scalar Observable.",
        )
        active = _interval(
            self.active_range, self.observable.dtype, "active response range"
        )
        inactive = _interval(
            self.inactive_range, self.observable.dtype, "inactive response range"
        )
        require(
            active.upper.canonical_value < inactive.lower.canonical_value
            or inactive.upper.canonical_value < active.lower.canonical_value,
            "Closed active and inactive response ranges must be disjoint.",
        )
        object.__setattr__(self, "active_range", active)
        object.__setattr__(self, "inactive_range", inactive)
        object.__setattr__(
            self,
            "max_activation_delay",
            _duration(self.max_activation_delay, "activation delay"),
        )
        object.__setattr__(
            self,
            "max_deactivation_delay",
            _duration(self.max_deactivation_delay, "deactivation delay"),
        )

    def accepts(self, value: Any, *, active: bool) -> bool:
        require(type(active) is bool, "Response activity must be Boolean.")
        return _inside(self.active_range if active else self.inactive_range, value)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "rule_id": self.rule_id,
            "specification_id": self.specification_id,
            "observable": self.observable.to_dict(),
            "active_range": self.active_range.to_dict(),
            "inactive_range": self.inactive_range.to_dict(),
            "max_activation_delay": self.max_activation_delay.to_dict(),
            "max_deactivation_delay": self.max_deactivation_delay.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> ResponseRequirement:
        _schema(
            data,
            cls,
            {
                "id",
                "rule_id",
                "specification_id",
                "observable",
                "active_range",
                "inactive_range",
                "max_activation_delay",
                "max_deactivation_delay",
            },
        )
        observable = Observable.from_dict(data["observable"])
        require(
            observable.dtype.kind == "scalar",
            "Response ranges require scalar measurements.",
        )
        return cls(
            data["id"],
            data["rule_id"],
            data["specification_id"],
            observable,
            _decode(data["active_range"], Interval[observable.dtype], "active range"),
            _decode(
                data["inactive_range"], Interval[observable.dtype], "inactive range"
            ),
            _decode(data["max_activation_delay"], DURATION, "activation delay"),
            _decode(data["max_deactivation_delay"], DURATION, "deactivation delay"),
        )


@dataclass(frozen=True)
class BehaviorContract(JsonArtifact):
    """An exact behavior identity and complete named response obligations.

    Graph correspondence is checked against the supplied BehaviorProgram by the
    realization checker; a fingerprint-shaped string alone establishes no claim.
    """

    id: str
    behavior_fingerprint: str
    requirements: tuple[ResponseRequirement, ...]
    schema_version: ClassVar[str] = "cellweave.behavior_contract.v0.1"

    def __post_init__(self) -> None:
        name(self.id, "Behavior contract id")
        require(
            isinstance(self.behavior_fingerprint, str)
            and len(self.behavior_fingerprint) == 64
            and all(
                character in "0123456789abcdef"
                for character in self.behavior_fingerprint
            ),
            "Behavior fingerprint must be SHA-256 hex.",
        )
        require(
            isinstance(self.requirements, (tuple, list))
            and bool(self.requirements)
            and all(
                isinstance(item, ResponseRequirement) for item in self.requirements
            ),
            "A behavior contract requires nonempty response requirements.",
        )
        requirements = tuple(sorted(self.requirements, key=lambda item: item.id))
        require(
            len({item.id for item in requirements}) == len(requirements),
            "Response requirement ids must be unique.",
        )
        require(
            len({(item.rule_id, item.specification_id) for item in requirements})
            == len(requirements),
            "Each rule/action specification must have one response requirement in this profile.",
        )
        require(
            len({item.observable.id for item in requirements}) == len(requirements),
            "Response measurement endpoint ids must be unique.",
        )
        require(
            len({item.observable.role for item in requirements}) == 1,
            "A finite-trace behavior contract must select one role.",
        )
        object.__setattr__(self, "requirements", requirements)

    @property
    def role(self) -> str:
        return self.requirements[0].observable.role

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "behavior_fingerprint": self.behavior_fingerprint,
            "requirements": [item.to_dict() for item in self.requirements],
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> BehaviorContract:
        _schema(data, cls, {"id", "behavior_fingerprint", "requirements"})
        require(
            isinstance(data["requirements"], (tuple, list)),
            "Response requirements must be an array.",
        )
        return cls(
            data["id"],
            data["behavior_fingerprint"],
            tuple(ResponseRequirement.from_dict(item) for item in data["requirements"]),
        )
