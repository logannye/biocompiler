"""Declared temporal operators with explicit clocks and coverage."""
from typing import Literal
from .model import EVENT, TRUTH, Expr, Quantity, Ref, TypeSpec


def _window(duration: Quantity) -> None:
    from decimal import Decimal
    if duration.unit.dimension != "time" or duration.unit.quantity_kind != "duration" or Decimal(duration.amount) <= 0:
        raise ValueError("Temporal windows require a positive duration")


def holds(condition: Expr, duration: Quantity, *, clock: Ref, coverage: Literal["continuous", "sampled"]) -> Expr:
    _window(duration)
    if condition.value_type != TRUTH:
        raise TypeError("holds requires a truth condition")
    return Expr("holds", TRUTH, (condition,), duration=duration, clock=clock, coverage=coverage)


def recently(condition: Expr, duration: Quantity, *, clock: Ref, coverage: Literal["continuous", "sampled"]) -> Expr:
    _window(duration)
    if condition.value_type != TRUTH:
        raise TypeError("recently requires a truth condition")
    return Expr("recently", TRUTH, (condition,), duration=duration, clock=clock, coverage=coverage)


def followed_by(first: Expr, second: Expr, *, within: Quantity, clock: Ref) -> Expr:
    _window(within)
    if first.value_type != EVENT or second.value_type != EVENT:
        raise TypeError("followed_by requires two events")
    return Expr("followed_by", EVENT, (first, second), duration=within, clock=clock, coverage="event")


def within(anchor: Expr, completion: Expr, deadline: Quantity, *, clock: Ref) -> Expr:
    _window(deadline)
    if anchor.value_type != EVENT or completion.value_type != EVENT:
        raise TypeError("within requires an explicit anchor event and completion event")
    return Expr("within", TRUTH, (anchor, completion), duration=deadline, clock=clock, coverage="event")


def after(first: Expr, second: Expr, *, clock: Ref) -> Expr:
    if first.value_type != EVENT or second.value_type != EVENT:
        raise TypeError("after requires two events")
    return Expr("after", EVENT, (first, second), clock=clock, coverage="event")


def until(activity: Expr, stop: Expr, *, clock: Ref) -> Expr:
    if activity.value_type != TRUTH or stop.value_type != TRUTH:
        raise TypeError("until requires truth conditions")
    return Expr("until", TRUTH, (activity, stop), clock=clock)


def integrate(signal: Expr, duration: Quantity, *, clock: Ref, result: TypeSpec) -> Expr:
    _window(duration)
    if signal.value_type.kind != "quantity" or result.kind != "quantity":
        raise TypeError("integrate requires a quantity and explicit integrated quantity type")
    return Expr("integrate", result, (signal,), duration=duration, clock=clock, coverage="sampled")
