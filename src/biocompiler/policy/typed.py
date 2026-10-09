"""Typed Python authoring handles that emit the unchanged policy source language.

This facade checks its supported expression categories and local invariants. It
does not evaluate a policy or establish native admission, proof or realization.
Explicit ``to_source()`` bridges retain the original nominal references/owners.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal, InvalidOperation
from typing import ClassVar, Generic, Literal, NoReturn, Self, TypeAlias, TypeVar, cast, final

from . import logic, model as m
from .programs import ProgramBuilder, ref
from .serialization import to_data
from .values import compatible, quantity as source_quantity


class TypedAuthoringError(TypeError):
    """A local typed-authoring contract is violated, not a compiler rejection."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TypedAuthoringError(message)


def _type(value: m.TypeSpec) -> None:
    _require(value.kind in ("truth", "integer", "text", "quantity", "event")
             and value.entity_kind is None, "Typed facade requires a scalar or event type")
    _require((value.kind == "quantity") == (value.unit is not None), "Only quantity expressions carry units")
    if value.unit is not None:
        unit = value.unit
        _require(bool(unit.id.strip()) and bool(unit.dimension.strip()) and bool(unit.quantity_kind.strip()),
                 "Quantity units need an identity, dimension and quantity kind")
        _require(len(unit.scale) <= 256, "Unit scale exceeds exact numeric limits")
        try:
            scale = Decimal(unit.scale)
            valid = scale.is_finite() and scale > 0 and abs(scale.adjusted()) <= 1024
        except InvalidOperation:
            valid = False
        _require(valid, "Unit scale must be a bounded positive finite decimal")


def _owners(*records: m.Record) -> None:
    owners: set[int] = set()
    pending: list[object] = list(records)
    visits = 0
    while pending:
        visits += 1
        _require(visits <= 100_000, "Typed ownership traversal exceeds the source work bound")
        value = pending.pop()
        if isinstance(value, m.Record):
            owner = getattr(value, "_policy_owner", None)
            if owner is not None:
                owners.add(id(owner))
            pending.extend(getattr(value, field.name) for field in fields(value))
        elif isinstance(value, tuple):
            pending.extend(value)
    _require(len(owners) <= 1, "Typed expressions cannot combine declarations from different programs")


def _subjects(source: m.Expr) -> set[m.Ref]:
    pending = [source]
    result: set[m.Ref] = set()
    while pending:
        item = pending.pop()
        if item.scope is not None and item.scope.kind == "Subject":
            result.add(item.scope)
        pending.extend(item.args)
    return result


_PHASES = ("requested", "initiated", "completed", "outcome", "failed", "timed_out",
           "cancel_requested", "cancel_acknowledged", "ceased")
EffectPhase: TypeAlias = Literal["requested", "initiated", "completed", "outcome", "failed", "timed_out",
                                 "cancel_requested", "cancel_acknowledged", "ceased"]


def _expression(source: m.Expr, expected: str) -> None:
    _require(type(source) is m.Expr, "Typed expressions require an exact source Expr")
    # Validate/bound without replacing the original object: cloning through the
    # decoder would discard the builder's nonwire ownership tokens.
    to_data(source)
    _require(source.value_type.kind == expected, "Expression category differs from its typed handle")
    pending = [source]
    while pending:
        item = pending.pop()
        _type(item.value_type)
        op, args = item.op, item.args
        _require(item.contract is None and item.duration is None and item.clock is None
                 and item.coverage is None and item.binding is None,
                 "This facade does not wrap custom or temporal source expressions")
        if op in ("observe", "state", "parameter", "updated", "effect_event"):
            kind = {"observe": "Observation", "state": "StateStore", "parameter": "Parameter",
                    "updated": "Observation", "effect_event": "Effect"}[op]
            _require(not args and item.ref is not None and item.ref.kind == kind,
                     "Source expression has the wrong nominal reference")
            if op in ("updated", "effect_event"):
                _require(item.value_type == m.EVENT, "Notifications must have event type")
                _require(item.value in _PHASES if op == "effect_event" else item.value is None,
                         "Invalid event phase or unexpected event value")
            else:
                _require(item.value_type.kind != "event" and item.value is None,
                         "Scalar references cannot have event values")
        elif op == "literal":
            _require(not args and item.ref is None and item.scope is None, "Invalid scalar literal shape")
            kind = item.value_type.kind
            valid = ((kind == "truth" and (type(item.value) is bool or item.value == "unknown"))
                     or (kind == "integer" and type(item.value) is int)
                     or (kind == "text" and type(item.value) is str)
                     or (kind == "quantity" and type(item.value) is m.Quantity
                         and item.value.unit == item.value_type.unit))
            _require(valid, "Literal value differs from its declared scalar type")
        else:
            _require(item.ref is None and item.scope is None and item.value is None,
                     "Operation carries unexpected reference, scope or value")
            if op in ("all", "any", "not"):
                _require(item.value_type == m.TRUTH and bool(args) and (op != "not" or len(args) == 1)
                         and all(arg.value_type == m.TRUTH for arg in args), "Logic requires truth expressions")
            elif op in ("eq", "ne", "lt", "le", "gt", "ge"):
                _require(len(args) == 2 and item.value_type == m.TRUTH, "Invalid comparison shape")
                _require(args[0].value_type.kind != "event" and compatible(args[0].value_type, args[1].value_type),
                         "Comparison requires matching scalar types, units and nominal references")
                _require(op in ("eq", "ne") or args[0].value_type.kind in ("integer", "quantity"),
                         "Ordered comparison requires numeric scalar expressions")
            elif op in ("add", "subtract"):
                _require(len(args) == 2 and item.value_type.kind in ("integer", "quantity"),
                         "Arithmetic requires two numeric scalar expressions")
                _require(compatible(args[0].value_type, args[1].value_type)
                         and compatible(item.value_type, args[0].value_type),
                         "Arithmetic requires compatible quantity kinds, dimensions and references")
            elif op == "rising":
                _require(len(args) == 1 and args[0].value_type == m.TRUTH and item.value_type == m.EVENT,
                         "Rising requires truth input and event output")
            else:
                raise TypedAuthoringError("Source operation is outside this typed facade: " + op)
        pending.extend(args)
    _owners(source)
    _require(len(_subjects(source)) <= 1, "Mixed observed subjects require an explicit relationship or quantifier")


@dataclass(frozen=True, eq=False)
class _Expression:
    _source: m.Expr
    _kind: ClassVar[str]

    def __post_init__(self) -> None:
        _require(type(self) in (TruthExpr, IntegerExpr, TextExpr, QuantityExpr, EventExpr),
                 "Typed expression categories are closed")
        _expression(self._source, self._kind)

    def to_source(self) -> m.Expr:
        """Return the original immutable source expression, retaining ownership."""
        _expression(self._source, self._kind)
        return self._source

    def __bool__(self) -> NoReturn:
        raise TypedAuthoringError("Symbolic expressions cannot be Python conditions; use a typed rule/guard")

    def __eq__(self, other: object) -> NoReturn:
        raise TypedAuthoringError("Use .eq() for scalar policy equality, or compare explicit source records")

    def __ne__(self, other: object) -> NoReturn:
        raise TypedAuthoringError("Use .ne() for scalar policy inequality, or compare explicit source records")


class _ScalarExpr(_Expression):
    def eq(self, other: Self) -> TruthExpr:
        _require(type(other) is type(self), "Equality requires the same scalar category")
        return TruthExpr(logic.compare(self._source, "eq", other._source))

    def ne(self, other: Self) -> TruthExpr:
        _require(type(other) is type(self), "Inequality requires the same scalar category")
        return TruthExpr(logic.compare(self._source, "ne", other._source))


@final
class TruthExpr(_ScalarExpr):
    _kind = "truth"

    def __and__(self, other: TruthExpr) -> TruthExpr:
        return all_of(self, other)

    def __or__(self, other: TruthExpr) -> TruthExpr:
        return any_of(self, other)

    def __invert__(self) -> TruthExpr:
        return not_(self)

    def rising(self) -> EventExpr:
        return rising(self)


class _NumericExpr(_ScalarExpr):
    def _compare(self, operator: Literal["lt", "le", "gt", "ge"], other: Self) -> TruthExpr:
        _require(type(other) is type(self), "Ordering requires the same numeric category")
        return TruthExpr(logic.compare(self._source, operator, other._source))

    def lt(self, other: Self) -> TruthExpr:
        return self._compare("lt", other)

    def le(self, other: Self) -> TruthExpr:
        return self._compare("le", other)

    def gt(self, other: Self) -> TruthExpr:
        return self._compare("gt", other)

    def ge(self, other: Self) -> TruthExpr:
        return self._compare("ge", other)

    def __add__(self, other: Self) -> Self:
        _require(type(other) is type(self), "Addition requires the same numeric category")
        return type(self)(logic.arithmetic(self._source, "add", other._source))

    def __sub__(self, other: Self) -> Self:
        _require(type(other) is type(self), "Subtraction requires the same numeric category")
        return type(self)(logic.arithmetic(self._source, "subtract", other._source))


@final
class IntegerExpr(_NumericExpr):
    _kind = "integer"


@final
class TextExpr(_ScalarExpr):
    _kind = "text"


@final
class QuantityExpr(_NumericExpr):
    _kind = "quantity"

    @property
    def unit(self) -> m.Unit:
        unit = self._source.value_type.unit
        assert unit is not None  # enforced at construction
        return unit


@final
class EventExpr(_Expression):
    _kind = "event"


ScalarExpression: TypeAlias = TruthExpr | IntegerExpr | TextExpr | QuantityExpr
S = TypeVar("S", bound=ScalarExpression)  # invariant: writable states must not widen


def truth(value: bool) -> TruthExpr:
    _require(type(value) is bool, "Truth literals require an exact bool")
    return TruthExpr(logic.literal(value))


def unknown() -> TruthExpr:
    return TruthExpr(logic.UNKNOWN)


def integer(value: int) -> IntegerExpr:
    _require(type(value) is int, "Integer literals require an exact int, not bool")
    return IntegerExpr(logic.literal(value))


def text(value: str) -> TextExpr:
    _require(type(value) is str, "Text literals require an exact str")
    return TextExpr(logic.literal(value))


def quantity(value: str | int | Decimal, unit: m.Unit) -> QuantityExpr:
    return QuantityExpr(logic.literal(source_quantity(value, unit)))


def _scalar(value: ScalarExpression) -> m.Expr:
    _require(type(value) in (TruthExpr, IntegerExpr, TextExpr, QuantityExpr), "Expected a typed scalar, not an event")
    return value.to_source()


def guard(value: TruthExpr) -> m.Expr:
    _require(type(value) is TruthExpr, "A guard requires TruthExpr")
    return value.to_source()


def trigger(value: EventExpr) -> m.Expr:
    _require(type(value) is EventExpr, "A trigger requires EventExpr")
    return value.to_source()


def all_of(first: TruthExpr, *rest: TruthExpr) -> TruthExpr:
    return TruthExpr(logic.all_of(*(guard(value) for value in (first, *rest))))


def any_of(first: TruthExpr, *rest: TruthExpr) -> TruthExpr:
    return TruthExpr(logic.any_of(*(guard(value) for value in (first, *rest))))


def not_(value: TruthExpr) -> TruthExpr:
    return TruthExpr(logic.not_(guard(value)))


def rising(value: TruthExpr) -> EventExpr:
    return EventExpr(logic.rising(guard(value)))


def argument(name: str, value: ScalarExpression) -> m.Argument:
    _require(type(name) is str and bool(name.strip()), "Effect argument needs a nonempty name")
    return m.Argument(name, _scalar(value))


def _wrapper(wrapper: type[S]) -> None:
    _require(wrapper in (TruthExpr, IntegerExpr, TextExpr, QuantityExpr), "Handles require a closed scalar category")


@dataclass(frozen=True, eq=False)
class Observation(Generic[S]):
    _source: m.Observation
    _expression_type: type[S]

    def __post_init__(self) -> None:
        _require(type(self._source) is m.Observation, "Observation handle requires an Observation declaration")
        _wrapper(self._expression_type)
        to_data(self._source)
        self._expression_type(self._source.expression)

    @property
    def value(self) -> S:
        return cast(S, self._expression_type(self._source.expression))

    @property
    def updated(self) -> EventExpr:
        return EventExpr(self._source.updated)

    def to_source(self) -> m.Observation:
        self.__post_init__()
        return self._source


@dataclass(frozen=True, eq=False)
class State(Generic[S]):
    _source: m.StateStore
    _expression_type: type[S]

    def __post_init__(self) -> None:
        _require(type(self._source) is m.StateStore, "State handle requires a StateStore declaration")
        _wrapper(self._expression_type)
        to_data(self._source)
        self._expression_type(self._source.expression)
        _expression(m.Expr("literal", self._source.value_type, value=self._source.initial), self._source.value_type.kind)
        if self._source.reset is not None:
            TruthExpr(self._source.reset)

    @property
    def value(self) -> S:
        return cast(S, self._expression_type(self._source.expression))

    def assign(self, value: S) -> Assignment:
        return Assignment(self._source, value)

    def with_reset(self, condition: TruthExpr) -> State[S]:
        """Return a source copy; an already-added builder declaration is not mutated."""
        reset = guard(condition)
        _owners(self._source, reset)
        changed = replace(self._source, reset=reset)
        owner = getattr(self._source, "_policy_owner", None)
        if owner is not None:
            object.__setattr__(changed, "_policy_owner", owner)
        return State(changed, self._expression_type)

    def to_source(self) -> m.StateStore:
        self.__post_init__()
        return self._source


@dataclass(frozen=True, eq=False)
class Parameter(Generic[S]):
    _source: m.Parameter
    _expression_type: type[S]

    def __post_init__(self) -> None:
        _require(type(self._source) is m.Parameter, "Parameter handle requires a Parameter declaration")
        _wrapper(self._expression_type)
        to_data(self._source)
        self._expression_type(m.Expr("parameter", self._source.value_type, ref=ref(self._source)))
        if self._source.value is not None:
            _expression(m.Expr("literal", self._source.value_type, value=self._source.value), self._source.value_type.kind)

    @property
    def value(self) -> S:
        return cast(S, self._expression_type(m.Expr("parameter", self._source.value_type, ref=ref(self._source))))

    def to_source(self) -> m.Parameter:
        self.__post_init__()
        return self._source


@dataclass(frozen=True, eq=False)
class Assignment:
    _state: m.StateStore
    _value: ScalarExpression

    def __post_init__(self) -> None:
        _require(type(self._state) is m.StateStore, "Assignment requires a StateStore declaration")
        to_data(self._state)
        source = _scalar(self._value)
        _require(compatible(self._state.value_type, source.value_type), "Assignment differs from the state's scalar type or units")
        _owners(self._state, source)
        if self._state.scope.kind == "target" and self._state.scope.subject is not None:
            _require(_subjects(source) <= {self._state.scope.subject}, "Assignment evidence refers to another target")

    def to_source(self) -> m.Assignment:
        self.__post_init__()
        return m.Assignment(ref(self._state), self._value.to_source())


@dataclass(frozen=True, eq=False)
class Effect:
    _source: m.Effect

    def __post_init__(self) -> None:
        _require(type(self._source) is m.Effect, "Effect handle requires an Effect declaration")
        to_data(self._source)
        for item in self._source.parameters:
            _require(item.value.value_type.kind != "event", "Effect argument cannot have event value")
            _expression(item.value, item.value.value_type.kind)

    def event(self, phase: EffectPhase) -> EventExpr:
        _require(phase in _PHASES, "Unknown effect lifecycle event")
        return EventExpr(self.to_source().event(phase))

    @property
    def requested(self) -> EventExpr:
        return self.event("requested")

    @property
    def initiated(self) -> EventExpr:
        return self.event("initiated")

    @property
    def completed(self) -> EventExpr:
        return self.event("completed")

    @property
    def failed(self) -> EventExpr:
        return self.event("failed")

    @property
    def timed_out(self) -> EventExpr:
        return self.event("timed_out")

    def to_source(self) -> m.Effect:
        self.__post_init__()
        return self._source


def truth_observation(source: m.Observation) -> Observation[TruthExpr]:
    return Observation(source, TruthExpr)


def integer_observation(source: m.Observation) -> Observation[IntegerExpr]:
    return Observation(source, IntegerExpr)


def text_observation(source: m.Observation) -> Observation[TextExpr]:
    return Observation(source, TextExpr)


def quantity_observation(source: m.Observation) -> Observation[QuantityExpr]:
    return Observation(source, QuantityExpr)


def truth_state(source: m.StateStore) -> State[TruthExpr]:
    return State(source, TruthExpr)


def integer_state(source: m.StateStore) -> State[IntegerExpr]:
    return State(source, IntegerExpr)


def text_state(source: m.StateStore) -> State[TextExpr]:
    return State(source, TextExpr)


def quantity_state(source: m.StateStore) -> State[QuantityExpr]:
    return State(source, QuantityExpr)


def truth_parameter(source: m.Parameter) -> Parameter[TruthExpr]:
    return Parameter(source, TruthExpr)


def integer_parameter(source: m.Parameter) -> Parameter[IntegerExpr]:
    return Parameter(source, IntegerExpr)


def text_parameter(source: m.Parameter) -> Parameter[TextExpr]:
    return Parameter(source, TextExpr)


def quantity_parameter(source: m.Parameter) -> Parameter[QuantityExpr]:
    return Parameter(source, QuantityExpr)


def _behavior(executor: m.Role, on: EventExpr, when: TruthExpr,
              effects: tuple[Effect, ...], assignments: tuple[Assignment, ...]) -> tuple[m.Expr, m.Expr]:
    _require(type(executor) is m.Role, "Behavior executor requires a Role declaration")
    event, condition = trigger(on), guard(when)
    to_data(executor)
    inputs = _subjects(event) | _subjects(condition)
    _require(len(inputs) <= 1, "Trigger and guard refer to different subjects")
    records: list[m.Record] = [executor, event, condition]
    for effect in effects:
        _require(type(effect) is Effect, "Effects require typed Effect handles")
        source = effect.to_source()
        _require(source.executor == ref(executor), "Effect belongs to a different executor")
        _require(not inputs - {source.subject} or source.relationship is not None,
                 "Redirecting evidence to another effect subject needs a relationship contract")
        records.append(source)
    for assignment in assignments:
        _require(type(assignment) is Assignment, "Updates require typed Assignment handles")
        if assignment._state.scope.kind == "executor":
            _require(assignment._state.scope.subject == ref(executor), "State belongs to a different executor")
        records.extend((assignment._state, assignment.to_source()))
    _owners(*records)
    return event, condition


def rule(builder: ProgramBuilder, identity: str, *, executor: m.Role, on: EventExpr, when: TruthExpr,
         unknown: Literal["defer", "request_stop"], effects: tuple[Effect, ...], arbitration: m.Arbitration,
         assignments: tuple[Assignment, ...] = (), emissions: tuple[m.Message, ...] = ()) -> m.Rule:
    event, condition = _behavior(executor, on, when, effects, assignments)
    _require(unknown in ("defer", "request_stop"), "Rule requires an explicit supported unknown branch")
    _require(all(type(message) is m.Message and message.sender == ref(executor) for message in emissions),
             "Emissions require Message declarations owned by this executor")
    candidate = m.Rule(builder.qualified(identity), executor=ref(executor), on=event, when=condition, unknown=unknown,
        effects=tuple(ref(effect.to_source()) for effect in effects), arbitration=arbitration,
        assignments=tuple(item.to_source() for item in assignments), emissions=tuple(ref(item) for item in emissions))
    to_data(candidate)
    return builder.add(candidate)


def transition(builder: ProgramBuilder, identity: str, *, machine: m.Machine, source: str, destination: str,
               on: EventExpr, when: TruthExpr, unknown: Literal["defer", "transition", "request_stop"],
               effects: tuple[Effect, ...] = (), assignments: tuple[Assignment, ...] = (),
               unknown_target: str | None = None, emissions: tuple[m.Message, ...] = ()) -> m.Transition:
    _require(type(machine) is m.Machine, "Transition requires a Machine declaration")
    to_data(machine)
    _require(source in machine.states and destination in machine.states, "Transition endpoints must belong to the machine")
    _require((unknown == "transition") == (unknown_target is not None)
             and (unknown_target is None or unknown_target in machine.states), "Unknown transition target is inconsistent")
    _require(unknown in ("defer", "transition", "request_stop"), "Unknown transition branch is invalid")
    event, condition = trigger(on), guard(when)
    inputs = _subjects(event) | _subjects(condition)
    _require(len(inputs) <= 1, "Transition trigger and guard refer to different subjects")
    for effect in effects:
        _require(type(effect) is Effect and effect.to_source().executor == machine.executor,
                 "Transition effect belongs to a different executor")
        _require(not inputs - {effect.to_source().subject} or effect.to_source().relationship is not None,
                 "Transition redirects evidence without a relationship contract")
    for assignment in assignments:
        _require(type(assignment) is Assignment, "Updates require typed Assignment handles")
        if assignment._state.scope.kind == "executor":
            _require(assignment._state.scope.subject == machine.executor, "State belongs to a different executor")
    _require(all(type(message) is m.Message and message.sender == machine.executor for message in emissions),
             "Emissions require Message declarations owned by the machine executor")
    _owners(machine, event, condition, *(effect.to_source() for effect in effects),
            *(item.to_source() for item in assignments), *emissions)
    candidate = m.Transition(builder.qualified(identity), machine=ref(machine), source=source, destination=destination,
        on=event, when=condition, unknown=unknown, effects=tuple(ref(effect.to_source()) for effect in effects),
        assignments=tuple(item.to_source() for item in assignments), unknown_target=unknown_target,
        emissions=tuple(ref(item) for item in emissions))
    to_data(candidate)
    return builder.add(candidate)


__all__ = [
    "TypedAuthoringError", "TruthExpr", "IntegerExpr", "TextExpr", "QuantityExpr", "EventExpr",
    "ScalarExpression", "EffectPhase", "Observation", "State", "Parameter", "Assignment", "Effect",
    "truth", "unknown", "integer", "text", "quantity", "guard", "trigger", "all_of", "any_of", "not_",
    "rising", "argument", "truth_observation", "integer_observation", "text_observation", "quantity_observation",
    "truth_state", "integer_state", "text_state", "quantity_state", "truth_parameter", "integer_parameter",
    "text_parameter", "quantity_parameter", "rule", "transition",
]
