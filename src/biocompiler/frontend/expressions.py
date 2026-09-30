"""Symbolic expressions: Python assembles these nodes; cells do not run Python."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from biocompiler.errors import ScopeError, TypeMismatchError
from biocompiler.semantics.types import (
    BOOLEAN,
    DURATION,
    EVENT,
    LEVEL,
    ScalarLiteral,
    TypeSpec,
    to_type_spec,
    validate_binding,
)

T = TypeVar("T")


class Expr(Generic[T]):
    def __init__(
        self, graph: Any, node_id: str, dtype: TypeSpec, role: str | None = None
    ) -> None:
        self._graph = graph
        self.node_id = node_id
        self.dtype = to_type_spec(dtype)
        self.role = role

    def __bool__(self) -> bool:
        raise TypeMismatchError(
            "A symbolic biocompiler expression has no Python truth value. "
            "Use &, |, ~ and cells.when(...), not and/or/not/if or chained comparisons."
        )

    def __eq__(self, other: Any) -> Any:
        raise TypeMismatchError(
            "This symbolic object does not support equality; use its typed predicate methods."
        )

    def __ne__(self, other: Any) -> Any:
        raise TypeMismatchError(
            "This symbolic object does not support equality; use its typed predicate methods."
        )

    __hash__ = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(node_id={self.node_id!r}, type={self.dtype.name!r}, role={self.role!r})"

    def _node(
        self,
        kind: str,
        cls: type,
        *,
        inputs: tuple[str, ...] | None = None,
        dtype: TypeSpec | None = None,
        role: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Any:
        dtype = self.dtype if dtype is None else dtype
        role = self.role if role is None else role
        node_id = self._graph.add(
            kind,
            inputs=(self.node_id,) if inputs is None else inputs,
            data_type=dtype.to_dict(),
            role=role,
            attributes=attributes,
        )
        return cls(self._graph, node_id, dtype, role)


def ensure_compatible(
    *expressions: Expr, graph: Any = None, role: str | None = None
) -> str | None:
    """Check graph and executing-role ownership, allowing role-free parameters."""
    merged = role
    for expression in expressions:
        if not isinstance(expression, Expr):
            raise TypeMismatchError("Expected a symbolic biocompiler expression.")
        if graph is None:
            graph = expression._graph
        if expression._graph is not graph:
            raise ScopeError("Expressions from different therapies cannot be combined.")
        if expression.role is not None:
            if merged is not None and expression.role != merged:
                raise ScopeError(
                    "Expressions from different cell roles cannot be combined; use a channel for communication."
                )
            merged = expression.role
    return merged


def coerce_quantity(
    value: Any, *, graph: Any, expected: Any = None, role: str | None = None
) -> Quantity:
    """Turn a scalar literal into a graph node, or validate an existing expression."""
    expected = None if expected is None else to_type_spec(expected)
    if isinstance(value, Quantity):
        ensure_compatible(value, graph=graph, role=role)
        if value.dtype.kind != "scalar":
            raise TypeMismatchError("A scalar quantity is required here.")
        if expected is not None and not value.dtype.compatible(expected):
            raise TypeMismatchError(
                f"Expected {expected.name}, got {value.dtype.name}."
            )
        return value
    dtype = value.dtype if isinstance(value, ScalarLiteral) else LEVEL
    if expected is not None and not dtype.compatible(expected):
        raise TypeMismatchError(
            f"Expected {expected.name}; use a typed literal with the appropriate units."
        )
    data = validate_binding(value, dtype)
    node_id = graph.add(
        "literal", attributes={"value": data}, data_type=dtype.to_dict(), intern=True
    )
    return Quantity(graph, node_id, dtype)


def ensure_duration(value: Any, *, graph: Any, role: str | None = None) -> Quantity:
    quantity = coerce_quantity(value, graph=graph, expected=DURATION, role=role)
    known = _constant_value(graph, quantity.node_id)
    if known is not None and known <= 0:
        raise TypeMismatchError(
            "A temporal window or action duration must be positive."
        )
    return quantity


def _constant_value(graph: Any, node_id: str) -> float | int | None:
    """Inspect canonical constants/defaults, without evaluating biological signals."""
    node = graph.get(node_id)
    if node.kind in {"literal", "parameter"}:
        value = node.attributes.get("value" if node.kind == "literal" else "default")
        if value is not None and value.get("kind") == "scalar":
            return value["canonical_value"]
    if node.kind == "negate":
        value = _constant_value(graph, node.inputs[0])
        return None if value is None else -value
    if node.kind in {"add", "subtract", "multiply", "divide"}:
        left, right = (_constant_value(graph, ref) for ref in node.inputs)
        if left is None or right is None:
            return None
        if node.kind == "add":
            return left + right
        if node.kind == "subtract":
            return left - right
        if node.kind == "multiply":
            return left * right
        return None if right == 0 else left / right
    return None


class Quantity(Expr[T]):
    def _binary(self, other: Any, kind: str, *, reverse: bool = False) -> Quantity:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Arithmetic requires scalar quantities.")
        other = coerce_quantity(other, graph=self._graph, role=self.role)
        role = ensure_compatible(self, other)
        left, right = (other, self) if reverse else (self, other)
        if kind in {"add", "subtract"}:
            if not left.dtype.compatible(right.dtype):
                raise TypeMismatchError(
                    f"Cannot {kind} {left.dtype.name} and {right.dtype.name}."
                )
            dtype = left.dtype
        elif kind == "multiply":
            dtype = left.dtype * right.dtype
        else:
            dtype = left.dtype / right.dtype
            if _constant_value(self._graph, right.node_id) == 0:
                raise TypeMismatchError(
                    "A quantity cannot be divided by a known zero value."
                )
        return self._node(
            kind, Quantity, inputs=(left.node_id, right.node_id), dtype=dtype, role=role
        )

    def __add__(self, other: Any) -> Quantity:
        return self._binary(other, "add")

    def __radd__(self, other: Any) -> Quantity:
        return self._binary(other, "add", reverse=True)

    def __sub__(self, other: Any) -> Quantity:
        return self._binary(other, "subtract")

    def __rsub__(self, other: Any) -> Quantity:
        return self._binary(other, "subtract", reverse=True)

    def __mul__(self, other: Any) -> Quantity:
        return self._binary(other, "multiply")

    def __rmul__(self, other: Any) -> Quantity:
        return self._binary(other, "multiply", reverse=True)

    def __truediv__(self, other: Any) -> Quantity:
        return self._binary(other, "divide")

    def __rtruediv__(self, other: Any) -> Quantity:
        return self._binary(other, "divide", reverse=True)

    def __neg__(self) -> Quantity:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Negation requires a scalar quantity.")
        return self._node("negate", Quantity)

    def __pos__(self) -> Quantity:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Unary plus requires a scalar quantity.")
        return self

    def _compare(self, other: Any, operator: str) -> Condition:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Numeric comparisons require scalar quantities.")
        other = coerce_quantity(
            other, graph=self._graph, expected=self.dtype, role=self.role
        )
        role = ensure_compatible(self, other)
        return self._node(
            "compare",
            Condition,
            inputs=(self.node_id, other.node_id),
            dtype=BOOLEAN,
            role=role,
            attributes={"operator": operator},
        )

    def __lt__(self, other: Any) -> Condition:
        return self._compare(other, "lt")

    def __le__(self, other: Any) -> Condition:
        return self._compare(other, "le")

    def __gt__(self, other: Any) -> Condition:
        return self._compare(other, "gt")

    def __ge__(self, other: Any) -> Condition:
        return self._compare(other, "ge")

    def __eq__(self, other: Any) -> Condition:
        return self._compare(other, "eq")

    def __ne__(self, other: Any) -> Condition:
        return self._compare(other, "ne")

    __hash__ = None

    def integrated(self, *, over: Any) -> Quantity:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Integration requires a scalar quantity.")
        duration = ensure_duration(over, graph=self._graph, role=self.role)
        role = ensure_compatible(self, duration)
        return self._node(
            "integrated",
            Quantity,
            inputs=(self.node_id, duration.node_id),
            dtype=self.dtype * DURATION,
            role=role,
            attributes={"window": "rolling", "history": "since_initialization"},
        )


class Signal(Quantity[T]):
    def _qualitative(self, band: str) -> Condition:
        if self.dtype.kind != "scalar":
            raise TypeMismatchError("Qualitative predicates require a scalar signal.")
        return self._node(
            "qualitative", Condition, dtype=BOOLEAN, attributes={"band": band}
        )

    def present(self) -> Condition:
        return self._qualitative("present")

    def high(self) -> Condition:
        return self._qualitative("high")

    def low(self) -> Condition:
        return self._qualitative("low")


class SpatialSignal(Expr[T]):
    """A spatial observation, deliberately separate from scalar arithmetic."""


class Condition(Expr[bool]):
    def _logical(self, other: Any, kind: str) -> Condition:
        if not isinstance(other, Condition):
            raise TypeMismatchError("Logical operators require Condition operands.")
        role = ensure_compatible(self, other)
        return self._node(
            kind,
            Condition,
            inputs=(self.node_id, other.node_id),
            dtype=BOOLEAN,
            role=role,
        )

    def __and__(self, other: Any) -> Condition:
        return self._logical(other, "and")

    def __or__(self, other: Any) -> Condition:
        return self._logical(other, "or")

    def __invert__(self) -> Condition:
        return self._node("not", Condition, dtype=BOOLEAN)

    def held_for(self, duration: Any) -> Condition:
        duration = ensure_duration(duration, graph=self._graph, role=self.role)
        role = ensure_compatible(self, duration)
        return self._node(
            "held_for",
            Condition,
            inputs=(self.node_id, duration.node_id),
            dtype=BOOLEAN,
            role=role,
            attributes={
                "history": "since_initialization",
                "requires_full_interval": True,
            },
        )

    def recently(self, *, within: Any) -> Condition:
        duration = ensure_duration(within, graph=self._graph, role=self.role)
        role = ensure_compatible(self, duration)
        return self._node(
            "recently",
            Condition,
            inputs=(self.node_id, duration.node_id),
            dtype=BOOLEAN,
            role=role,
            attributes={"history": "since_initialization", "includes_present": True},
        )

    def became_true(self) -> Event:
        return self._node(
            "became_true", Event, dtype=EVENT, attributes={"initially_true_emits": True}
        )


class Event(Expr[None]):
    def followed_by(self, other: Event, *, within: Any) -> Event:
        if not isinstance(other, Event):
            raise TypeMismatchError("followed_by requires another Event.")
        role = ensure_compatible(self, other)
        duration = ensure_duration(within, graph=self._graph, role=role)
        role = ensure_compatible(self, other, duration)
        return self._node(
            "followed_by",
            Event,
            inputs=(self.node_id, other.node_id, duration.node_id),
            dtype=EVENT,
            role=role,
            attributes={"emits_at": "second_event", "history": "since_initialization"},
        )


class Parameter(Quantity[T]):
    def __call__(self, value: Any) -> Quantity:
        if self.dtype.kind != "curve":
            raise TypeMismatchError("Only a Parameter with a Curve type can be called.")
        source, target = self.dtype.arguments
        value = coerce_quantity(
            value, graph=self._graph, expected=source, role=self.role
        )
        role = ensure_compatible(self, value)
        return self._node(
            "curve_apply",
            Quantity,
            inputs=(self.node_id, value.node_id),
            dtype=target,
            role=role,
        )


class ControlPort(Quantity[T]):
    """An addressable output quantity that a controller can adjust."""


def at_least(count: int, *conditions: Condition) -> Condition:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatchError("at_least count must be an integer.")
    if not conditions or count < 0 or count > len(conditions):
        raise TypeMismatchError(
            "at_least requires conditions and a count from zero through their number."
        )
    if any(not isinstance(condition, Condition) for condition in conditions):
        raise TypeMismatchError("at_least operands must be Conditions.")
    role = ensure_compatible(*conditions)
    first = conditions[0]
    return first._node(
        "at_least",
        Condition,
        inputs=tuple(item.node_id for item in conditions),
        dtype=BOOLEAN,
        role=role,
        attributes={"count": count},
    )
