"""Small exact contract algebra for component composition, not a biological model.

Supported domains are nonempty finite Boolean sets and closed finite scalar
intervals. Units are explicit and never converted implicitly. Unknown information
cannot establish an inclusion, even when both operands carry the same unknown.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.serialization import JsonArtifact, fields, name, names, require
from cellweave.semantics.types import BOOLEAN, LEVEL, TypeSpec


def _schema(data, cls, keys):
    fields(data, keys | {"schema_version"}, cls.__name__)
    require(
        data["schema_version"] == cls.schema_version,
        f"Unsupported {cls.__name__} schema.",
    )


def contract_type(value) -> TypeSpec:
    """Require an immutable Boolean/scalar type without broad dimensional coercion."""
    require(isinstance(value, TypeSpec), "A contract requires a TypeSpec.")
    require(
        value.kind in {"scalar", "condition"},
        "Component contracts support Boolean and scalar types only.",
    )
    return value


def decode_type(data) -> TypeSpec:
    try:
        return contract_type(TypeSpec.from_dict(data))
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise SerializationError(f"Invalid component contract type: {exc}") from exc


def finite_number(value, label):
    require(type(value) in {int, float}, f"{label} must be a finite number.")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    require(valid, f"{label} must be a finite number.")
    return value


@dataclass(frozen=True)
class ValueDomain(JsonArtifact):
    kind: str
    dtype: TypeSpec
    unit: str
    values: tuple[bool, ...] = ()
    lower: int | float | None = None
    upper: int | float | None = None
    reason: str | None = None
    schema_version: ClassVar[str] = "cellweave.component_value_domain.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.kind, str)
            and self.kind in {"boolean", "scalar_interval", "unknown"},
            "Unsupported value domain kind.",
        )
        contract_type(self.dtype)
        name(self.unit, "Domain unit")
        require(
            isinstance(self.values, (list, tuple)), "Domain values must be an array."
        )
        values = tuple(self.values)
        require(
            all(type(value) is bool for value in values),
            "Boolean domains contain only Booleans.",
        )
        require(
            len(set(values)) == len(values), "Boolean domain values must be unique."
        )
        object.__setattr__(self, "values", tuple(sorted(values)))
        if self.dtype.kind == "condition":
            require(self.unit == "1", "Boolean domains use unit '1'.")
        if self.kind == "boolean":
            require(
                self.dtype.kind == "condition" and bool(values),
                "A Boolean domain requires a condition type and nonempty values.",
            )
            require(
                self.lower is None and self.upper is None and self.reason is None,
                "Boolean domains do not carry scalar bounds or an unknown reason.",
            )
        elif self.kind == "scalar_interval":
            require(
                self.dtype.kind == "scalar" and not values and self.reason is None,
                "Scalar intervals require a scalar type and no Boolean values/reason.",
            )
            finite_number(self.lower, "Lower domain bound")
            finite_number(self.upper, "Upper domain bound")
            require(self.lower <= self.upper, "Domain lower bound exceeds upper bound.")
        else:
            require(
                not values and self.lower is None and self.upper is None,
                "Unknown domains cannot carry known bounds or Boolean values.",
            )
            name(self.reason, "Unknown domain reason")

    @classmethod
    def boolean(cls, values=(False, True)):
        return cls("boolean", BOOLEAN, "1", values=values)

    @classmethod
    def interval(cls, lower, upper, dtype=LEVEL, unit="1"):
        return cls("scalar_interval", dtype, unit, lower=lower, upper=upper)

    @classmethod
    def unknown(cls, dtype=LEVEL, unit="1", reason="not established"):
        return cls("unknown", dtype, unit, reason=reason)

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "dtype": self.dtype.to_dict(),
            "unit": self.unit,
            "values": list(self.values),
            "lower": self.lower,
            "upper": self.upper,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data):
        _schema(
            data, cls, {"kind", "dtype", "unit", "values", "lower", "upper", "reason"}
        )
        return cls(
            data["kind"],
            decode_type(data["dtype"]),
            data["unit"],
            data["values"],
            data["lower"],
            data["upper"],
            data["reason"],
        )


@dataclass(frozen=True)
class DomainCheck(JsonArtifact):
    status: str
    reasons: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "cellweave.component_domain_check.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.status, str) and self.status in {"pass", "fail", "unknown"},
            "Unsupported domain check status.",
        )
        object.__setattr__(self, "reasons", names(self.reasons, "Domain check reasons"))

    @property
    def passed(self):
        return self.status == "pass"

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data):
        _schema(data, cls, {"status", "reasons"})
        return cls(data["status"], data["reasons"])


def _combine(checks):
    checks = tuple(checks)
    status = (
        "fail"
        if any(c.status == "fail" for c in checks)
        else ("unknown" if any(c.status == "unknown" for c in checks) else "pass")
    )
    return DomainCheck(
        status,
        tuple(dict.fromkeys(reason for check in checks for reason in check.reasons)),
    )


def domain_subset(required: ValueDomain, supported: ValueDomain) -> DomainCheck:
    """Prove required ⊆ supported only within the exact supported contract language."""
    require(
        isinstance(required, ValueDomain) and isinstance(supported, ValueDomain),
        "Domain inclusion requires ValueDomain objects.",
    )
    if required.dtype != supported.dtype or required.unit != supported.unit:
        return DomainCheck("fail", ("Domain types or explicit units differ.",))
    if "unknown" in {required.kind, supported.kind}:
        return DomainCheck(
            "unknown", ("Domain inclusion is unresolved because a domain is unknown.",)
        )
    if required.kind != supported.kind:
        return DomainCheck("fail", ("Domain kinds differ.",))
    contained = (
        set(required.values) <= set(supported.values)
        if required.kind == "boolean"
        else supported.lower <= required.lower <= required.upper <= supported.upper
    )
    return (
        DomainCheck("pass")
        if contained
        else DomainCheck("fail", ("Required domain exceeds the supported domain.",))
    )


@dataclass(frozen=True)
class OperatingDomain(JsonArtifact):
    """A conjunction of named constraints; omitted coordinates mean unknown."""

    constraints: Mapping[str, ValueDomain] = field(default_factory=dict)
    schema_version: ClassVar[str] = "cellweave.component_operating_domain.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.constraints, Mapping),
            "Domain constraints must be an object.",
        )
        for key, value in self.constraints.items():
            name(key, "Operating domain coordinate")
            require(
                isinstance(value, ValueDomain),
                "Domain constraints must be ValueDomains.",
            )
        object.__setattr__(
            self,
            "constraints",
            MappingProxyType(dict(sorted(self.constraints.items()))),
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "constraints": {
                key: value.to_dict() for key, value in self.constraints.items()
            },
        }

    @classmethod
    def from_dict(cls, data):
        _schema(data, cls, {"constraints"})
        require(
            isinstance(data["constraints"], Mapping),
            "Domain constraints must be an object.",
        )
        return cls(
            {
                key: ValueDomain.from_dict(value)
                for key, value in data["constraints"].items()
            }
        )


def operating_domain_subset(
    required: OperatingDomain, supported: OperatingDomain
) -> DomainCheck:
    require(
        isinstance(required, OperatingDomain)
        and isinstance(supported, OperatingDomain),
        "Operating domain inclusion requires OperatingDomain objects.",
    )
    checks = []
    for key in sorted(set(required.constraints) | set(supported.constraints)):
        if key not in required.constraints or key not in supported.constraints:
            checks.append(
                DomainCheck(
                    "unknown", (f"Operating coordinate {key!r} is unspecified.",)
                )
            )
        else:
            result = domain_subset(
                required.constraints[key], supported.constraints[key]
            )
            checks.append(
                DomainCheck(result.status, tuple(f"{key}: {r}" for r in result.reasons))
            )
    return _combine(checks)


@dataclass(frozen=True)
class PortContract(JsonArtifact):
    id: str
    direction: str
    meaning: str
    dtype: TypeSpec
    unit: str
    role: str
    scope: str
    compartment: str
    timing: str
    initialization: ValueDomain
    domain: ValueDomain
    schema_version: ClassVar[str] = "cellweave.component_port.v0.1"

    def __post_init__(self):
        for key in ("id", "meaning", "unit", "role", "compartment", "timing"):
            name(getattr(self, key), f"Port {key}")
        require(
            self.timing in {"atomic_snapshot_stateless.v0.1", "unknown"},
            "Unsupported component timing profile.",
        )
        require(
            isinstance(self.direction, str) and self.direction in {"input", "output"},
            "Port direction must be input or output.",
        )
        require(
            isinstance(self.scope, str) and self.scope in {"cell", "contact"},
            "Port scope must be cell or contact.",
        )
        contract_type(self.dtype)
        for key in ("initialization", "domain"):
            value = getattr(self, key)
            require(
                isinstance(value, ValueDomain), f"Port {key} requires a ValueDomain."
            )
            require(
                value.dtype == self.dtype and value.unit == self.unit,
                f"Port {key} type/unit disagrees with its interface.",
            )
        require(
            domain_subset(self.initialization, self.domain).status != "fail",
            "Initial port values must lie inside the runtime domain.",
        )

    def to_dict(self):
        result = {
            key: getattr(self, key)
            for key in (
                "id",
                "direction",
                "meaning",
                "unit",
                "role",
                "scope",
                "compartment",
                "timing",
            )
        }
        result.update(
            schema_version=self.schema_version,
            dtype=self.dtype.to_dict(),
            initialization=self.initialization.to_dict(),
            domain=self.domain.to_dict(),
        )
        return result

    @classmethod
    def from_dict(cls, data):
        _schema(
            data,
            cls,
            {
                "id",
                "direction",
                "meaning",
                "dtype",
                "unit",
                "role",
                "scope",
                "compartment",
                "timing",
                "initialization",
                "domain",
            },
        )
        return cls(
            data["id"],
            data["direction"],
            data["meaning"],
            decode_type(data["dtype"]),
            data["unit"],
            data["role"],
            data["scope"],
            data["compartment"],
            data["timing"],
            ValueDomain.from_dict(data["initialization"]),
            ValueDomain.from_dict(data["domain"]),
        )


def ports_compatible(producer: PortContract, consumer: PortContract) -> DomainCheck:
    require(
        isinstance(producer, PortContract) and isinstance(consumer, PortContract),
        "Interface checks require PortContract objects.",
    )
    checks = []
    if producer.direction != "output" or consumer.direction != "input":
        checks.append(
            DomainCheck(
                "fail", ("Connections require an output producer and input consumer.",)
            )
        )
    for key in ("meaning", "dtype", "unit", "role", "scope", "compartment"):
        if getattr(producer, key) != getattr(consumer, key):
            checks.append(DomainCheck("fail", (f"Port {key} differs.",)))
    if "unknown" in {producer.timing, consumer.timing}:
        checks.append(DomainCheck("unknown", ("Port timing is unknown.",)))
    elif producer.timing != consumer.timing:
        checks.append(DomainCheck("fail", ("Port timing differs.",)))
    checks.append(domain_subset(producer.domain, consumer.domain))
    initial = domain_subset(producer.initialization, consumer.initialization)
    checks.append(
        DomainCheck(
            initial.status, tuple(f"Initialization: {r}" for r in initial.reasons)
        )
    )
    return _combine(checks)
