"""Small, serializable types and literal values for therapeutic intent.

These types describe quantities in the intent graph. They neither select a
biological implementation nor assign a numerical value to a named signal.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, Mapping

from cellweave.errors import TypeMismatchError


@dataclass(frozen=True)
class TypeSpec:
    """A semantic type, including physical dimensions and generic arguments."""

    kind: str
    name: str
    dimensions: tuple[tuple[str, int], ...] = ()
    arguments: tuple[TypeSpec, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kind, str)
            or not self.kind
            or not isinstance(self.name, str)
            or not self.name
        ):
            raise TypeMismatchError("A type requires nonempty kind and name strings.")
        if self.kind not in {"scalar", "condition", "event", "interval", "curve"}:
            raise TypeMismatchError(f"Unknown type kind: {self.kind!r}.")
        dimensions = dict()
        for key, power in self.dimensions:
            if (
                not isinstance(key, str)
                or not key
                or isinstance(power, bool)
                or not isinstance(power, int)
            ):
                raise TypeMismatchError("Dimensions require names and integer powers.")
            dimensions[key] = dimensions.get(key, 0) + power
        dimensions = tuple(
            sorted((key, power) for key, power in dimensions.items() if power)
        )
        arguments = tuple(self.arguments)
        if any(not isinstance(argument, TypeSpec) for argument in arguments):
            raise TypeMismatchError("Type arguments must be TypeSpec objects.")
        if self.kind == "scalar" and arguments:
            raise TypeMismatchError("Scalar types cannot have generic arguments.")
        if self.kind in {"interval", "curve"}:
            required = 1 if self.kind == "interval" else 2
            if (
                dimensions
                or len(arguments) != required
                or any(arg.kind != "scalar" for arg in arguments)
            ):
                raise TypeMismatchError(
                    f"{self.kind} requires {required} scalar type argument(s)."
                )
        if self.kind in {"condition", "event"} and (dimensions or arguments):
            raise TypeMismatchError(
                f"{self.kind} types have no physical dimensions or generic arguments."
            )
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "arguments", arguments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "dimensions": dict(self.dimensions),
            "arguments": [argument.to_dict() for argument in self.arguments],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TypeSpec:
        if not isinstance(value, Mapping):
            raise TypeMismatchError("A serialized type must be an object.")
        if {"kind", "name"} - value.keys() or value.keys() - {
            "kind",
            "name",
            "dimensions",
            "arguments",
        }:
            raise TypeMismatchError("A serialized type has missing or unknown fields.")
        dimensions, arguments = value.get("dimensions", {}), value.get("arguments", ())
        if not isinstance(dimensions, Mapping) or not isinstance(
            arguments, (list, tuple)
        ):
            raise TypeMismatchError(
                "Type dimensions must be an object and arguments must be an array."
            )
        return cls(
            kind=value["kind"],
            name=value["name"],
            dimensions=tuple(dimensions.items()),
            arguments=tuple(cls.from_dict(item) for item in arguments),
        )

    def compatible(self, other: TypeSpec) -> bool:
        return (
            self.kind == other.kind
            and self.dimensions == other.dimensions
            and len(self.arguments) == len(other.arguments)
            and all(
                left.compatible(right)
                for left, right in zip(self.arguments, other.arguments)
            )
        )

    def _combine(self, other: TypeSpec, sign: int) -> TypeSpec:
        if self.kind != "scalar" or other.kind != "scalar":
            raise TypeMismatchError(
                "Dimensional arithmetic requires scalar quantities."
            )
        dimensions = dict(self.dimensions)
        for dimension, power in other.dimensions:
            dimensions[dimension] = dimensions.get(dimension, 0) + sign * power
        normalized = tuple(
            sorted((key, value) for key, value in dimensions.items() if value)
        )
        for known in (LEVEL, DURATION, CONCENTRATION, SURFACE_DENSITY, PRODUCTION_RATE):
            if known.dimensions == normalized:
                return known
        operator = "*" if sign == 1 else "/"
        return TypeSpec("scalar", f"({self.name}{operator}{other.name})", normalized)

    def __mul__(self, other: TypeSpec) -> TypeSpec:
        return self._combine(other, 1)

    def __truediv__(self, other: TypeSpec) -> TypeSpec:
        return self._combine(other, -1)


LEVEL = TypeSpec("scalar", "Level")
DURATION = TypeSpec("scalar", "Duration", (("time", 1),))
CONCENTRATION = TypeSpec("scalar", "Concentration", (("amount", 1), ("length", -3)))
SURFACE_DENSITY = TypeSpec("scalar", "SurfaceDensity", (("amount", 1), ("length", -2)))
PRODUCTION_RATE = TypeSpec("scalar", "ProductionRate", (("amount", 1), ("time", -1)))
BOOLEAN = TypeSpec("condition", "Condition")
EVENT = TypeSpec("event", "Event")


def _number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeMismatchError(
            "A quantity requires a real number, not a Boolean or arbitrary object."
        )
    try:
        finite = math.isfinite(value)
    except OverflowError as error:
        raise TypeMismatchError(
            "A quantity must fit in a finite numerical value."
        ) from error
    if not finite:
        raise TypeMismatchError("A quantity must be finite.")
    return int(value) if isinstance(value, int) else float(value)


@dataclass(frozen=True)
class ScalarLiteral:
    """A value with explicit units and a canonical value for comparison."""

    value: float | int
    dtype: TypeSpec
    unit: str
    canonical_value: float | int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "scalar",
            "value": self.value,
            "unit": self.unit,
            "canonical_value": self.canonical_value,
            "type": self.dtype.to_dict(),
        }


_AVOGADRO = 6.02214076e23


class _ScalarType:
    _spec: TypeSpec
    _default_unit: str
    _units: dict[str, float]

    def __new__(cls, value: float, *, unit: str | None = None) -> ScalarLiteral:
        value = _number(value)
        unit = cls._default_unit if unit is None else unit
        if unit not in cls._units:
            raise TypeMismatchError(
                f"Unsupported {cls._spec.name} unit {unit!r}; expected one of {tuple(cls._units)}."
            )
        return ScalarLiteral(value, cls._spec, unit, _number(value * cls._units[unit]))


class Level(_ScalarType):
    _spec = LEVEL
    _default_unit = "1"
    _units = {"1": 1, "dimensionless": 1}


class Duration(_ScalarType):
    _spec = DURATION
    _default_unit = "s"
    _units = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "ms": 0.001,
        "min": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }


class Concentration(_ScalarType):
    _spec = CONCENTRATION
    _default_unit = "mol/m^3"
    _units = {
        "mol/m^3": 1,
        "mol/L": 1000,
        "M": 1000,
        "mM": 1,
        "uM": 1e-3,
        "µM": 1e-3,
        "nM": 1e-6,
        "pM": 1e-9,
    }


class SurfaceDensity(_ScalarType):
    _spec = SURFACE_DENSITY
    _default_unit = "mol/m^2"
    _units = {
        "mol/m^2": 1,
        "molecules/um^2": 1e12 / _AVOGADRO,
        "molecules/µm^2": 1e12 / _AVOGADRO,
    }


class ProductionRate(_ScalarType):
    _spec = PRODUCTION_RATE
    _default_unit = "mol/s"
    _units = {
        "mol/s": 1,
        "mol/min": 1 / 60,
        "molecules/s": 1 / _AVOGADRO,
        "molecules/min": 1 / (60 * _AVOGADRO),
    }


def to_type_spec(value: Any) -> TypeSpec:
    """Normalize a public type token; literal values are not type declarations."""
    if isinstance(value, TypeSpec):
        return value
    if (
        isinstance(value, type)
        and issubclass(value, _ScalarType)
        and value is not _ScalarType
    ):
        return value._spec
    raise TypeMismatchError(
        f"Expected a CellWeave type such as Level or Curve[Level, ProductionRate], got {value!r}."
    )


validate_type = to_type_spec


def _scalar_binding(value: Any, dtype: TypeSpec) -> ScalarLiteral:
    if isinstance(value, ScalarLiteral):
        if not value.dtype.compatible(dtype):
            raise TypeMismatchError(f"Expected {dtype.name}, got {value.dtype.name}.")
        return value
    if dtype.kind == "scalar" and not dtype.dimensions:
        return ScalarLiteral(_number(value), dtype, "1", _number(value))
    raise TypeMismatchError(f"{dtype.name} values require a typed literal with units.")


@dataclass(frozen=True, init=False)
class Interval:
    lower: ScalarLiteral
    upper: ScalarLiteral
    dtype: TypeSpec

    def __init__(self, lower: Any, upper: Any, *, type: Any = Level) -> None:
        item = to_type_spec(type)
        if item.kind != "scalar":
            raise TypeMismatchError("An interval requires a scalar element type.")
        low = _scalar_binding(lower, item)
        high = _scalar_binding(upper, item)
        if low.canonical_value > high.canonical_value:
            raise TypeMismatchError(
                "An interval lower bound must not exceed its upper bound."
            )
        object.__setattr__(self, "lower", low)
        object.__setattr__(self, "upper", high)
        object.__setattr__(self, "dtype", Interval[item])

    @classmethod
    def __class_getitem__(cls, item: Any) -> TypeSpec:
        item = to_type_spec(item)
        if item.kind != "scalar":
            raise TypeMismatchError("An interval requires a scalar element type.")
        return TypeSpec("interval", f"Interval[{item.name}]", arguments=(item,))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "interval",
            "lower": self.lower.to_dict(),
            "upper": self.upper.to_dict(),
            "type": self.dtype.to_dict(),
        }


@dataclass(frozen=True, init=False)
class Curve:
    """An inspectable piecewise response curve.

    ``step`` holds a knot's value until the next knot, where the new value applies.
    ``clamp`` holds the first/last value outside the supplied input range.
    The object records these choices; it is not a simulator or Python callback.
    """

    points: tuple[tuple[ScalarLiteral, ScalarLiteral], ...]
    dtype: TypeSpec
    interpolation: str
    extrapolation: str

    def __init__(
        self,
        *,
        points: Any,
        input: Any,
        output: Any,
        interpolation: str = "linear",
        extrapolation: str = "clamp",
    ) -> None:
        source, target = to_type_spec(input), to_type_spec(output)
        if source.kind != "scalar" or target.kind != "scalar":
            raise TypeMismatchError(
                "Curve inputs and outputs must be scalar quantities."
            )
        if interpolation not in {"linear", "step"}:
            raise TypeMismatchError("Curve interpolation must be 'linear' or 'step'.")
        if extrapolation not in {"clamp", "error"}:
            raise TypeMismatchError("Curve extrapolation must be 'clamp' or 'error'.")
        resolved = tuple(
            (_scalar_binding(x, source), _scalar_binding(y, target)) for x, y in points
        )
        if len(resolved) < 2:
            raise TypeMismatchError("A curve requires at least two points.")
        if any(
            left[0].canonical_value >= right[0].canonical_value
            for left, right in zip(resolved, resolved[1:])
        ):
            raise TypeMismatchError(
                "Curve input coordinates must be strictly increasing."
            )
        object.__setattr__(self, "points", resolved)
        object.__setattr__(self, "dtype", Curve[source, target])
        object.__setattr__(self, "interpolation", interpolation)
        object.__setattr__(self, "extrapolation", extrapolation)

    @classmethod
    def __class_getitem__(cls, arguments: Any) -> TypeSpec:
        if not isinstance(arguments, tuple) or len(arguments) != 2:
            raise TypeMismatchError("A curve type requires input and output types.")
        source, target = (to_type_spec(item) for item in arguments)
        if source.kind != "scalar" or target.kind != "scalar":
            raise TypeMismatchError(
                "Curve inputs and outputs must be scalar quantities."
            )
        return TypeSpec(
            "curve", f"Curve[{source.name}, {target.name}]", arguments=(source, target)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "curve",
            "type": self.dtype.to_dict(),
            "points": [[x.to_dict(), y.to_dict()] for x, y in self.points],
            "interpolation": self.interpolation,
            "extrapolation": self.extrapolation,
        }


def validate_binding(value: Any, dtype: Any) -> dict[str, Any]:
    """Validate and serialize a concrete parameter value without evaluating intent."""
    dtype = to_type_spec(dtype)
    if dtype.kind == "scalar":
        return _scalar_binding(value, dtype).to_dict()
    if isinstance(value, (Interval, Curve)) and value.dtype.compatible(dtype):
        return value.to_dict()
    raise TypeMismatchError(f"Expected a literal value of type {dtype.name}.")


def decode_binding(data: Any, dtype: Any) -> ScalarLiteral | Interval | Curve:
    """Validate and reconstruct a serialized value against its declared type.

    Built-in scalar types use their registered unit conversions. Custom scalar
    types retain the explicitly supplied finite canonical value and unit; their
    conversion convention belongs to that custom type's definition.
    """
    expected = to_type_spec(dtype)
    if not isinstance(data, Mapping):
        raise TypeMismatchError("A serialized binding must be an object.")
    fields = {
        "scalar": {"kind", "value", "unit", "canonical_value", "type"},
        "interval": {"kind", "lower", "upper", "type"},
        "curve": {"kind", "points", "interpolation", "extrapolation", "type"},
    }
    if expected.kind not in fields:
        raise TypeMismatchError(f"{expected.name} does not accept literal bindings.")
    if set(data) != fields[expected.kind] or data["kind"] != expected.kind:
        raise TypeMismatchError(
            f"A serialized {expected.kind} binding has invalid fields or kind."
        )
    actual = TypeSpec.from_dict(data["type"])
    if not actual.compatible(expected):
        raise TypeMismatchError(f"Expected {expected.name}, got {actual.name}.")

    if actual.kind == "scalar":
        value, canonical = _number(data["value"]), _number(data["canonical_value"])
        unit = data["unit"]
        if not isinstance(unit, str) or not unit.strip():
            raise TypeMismatchError("A scalar binding requires a nonempty unit.")
        for scalar_type in (
            Level,
            Duration,
            Concentration,
            SurfaceDensity,
            ProductionRate,
        ):
            if actual == scalar_type._spec:
                normalized = scalar_type(value, unit=unit)
                if canonical != normalized.canonical_value:
                    raise TypeMismatchError(
                        "A scalar binding's canonical value disagrees with its value and unit."
                    )
                return normalized
        return ScalarLiteral(value, actual, unit, canonical)

    if actual.kind == "interval":
        item_type = actual.arguments[0]
        result = Interval(
            decode_binding(data["lower"], item_type),
            decode_binding(data["upper"], item_type),
            type=item_type,
        )
        object.__setattr__(result, "dtype", actual)
        return result

    points = data["points"]
    if not isinstance(points, (list, tuple)) or any(
        not isinstance(point, (list, tuple)) or len(point) != 2 for point in points
    ):
        raise TypeMismatchError("Curve points must be an array of input/output pairs.")
    if not isinstance(data["interpolation"], str) or not isinstance(
        data["extrapolation"], str
    ):
        raise TypeMismatchError(
            "Curve interpolation and extrapolation must be strings."
        )
    source, target = actual.arguments
    result = Curve(
        points=[
            (decode_binding(x, source), decode_binding(y, target)) for x, y in points
        ],
        input=source,
        output=target,
        interpolation=data["interpolation"],
        extrapolation=data["extrapolation"],
    )
    object.__setattr__(result, "dtype", actual)
    return result
