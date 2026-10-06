"""Exact quantities and explicit scientific-input conversion."""
from decimal import Decimal
from .model import INTEGER, TEXT, TRUTH, EVENT, Parameter, Quantity, TypeSpec, Unit

SECOND = Unit("s", "time", "duration")
MINUTE = Unit("min", "time", "duration", "60")
COUNT = Unit("count", "count", "count")
DIMENSIONLESS = Unit("one", "dimensionless", "ratio")


def quantity(amount: str | int | Decimal, unit: Unit) -> Quantity:
    """Construct an exact value; binary floats require an explicit conversion."""
    if isinstance(amount, (float, bool)):
        raise TypeError("Use a decimal string or from_float(value, unit)")
    return Quantity(str(amount), unit)


def from_float(value: float, unit: Unit) -> Quantity:
    """Explicitly preserve the float's exact binary value as a decimal."""
    return quantity(Decimal.from_float(value), unit)


def compatible(left: TypeSpec, right: TypeSpec) -> bool:
    if left.kind != right.kind:
        return False
    if left.kind == "quantity":
        a, b = left.unit, right.unit
        return a is not None and b is not None and (a.dimension, a.quantity_kind, a.reference) == (b.dimension, b.quantity_kind, b.reference)
    return left == right


__all__ = ["INTEGER", "TEXT", "TRUTH", "EVENT", "Parameter", "Quantity", "TypeSpec", "Unit", "SECOND", "MINUTE", "COUNT", "DIMENSIONLESS", "quantity", "from_float", "compatible"]
