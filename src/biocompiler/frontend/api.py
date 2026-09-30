"""Public authoring objects for biocompiler's symbolic cell-behavior language.

Constructors describe intent. Only declarations and installed rules/controllers
are roots of a frozen program; merely constructing an action never activates it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from biocompiler.errors import DefinitionError, ScopeError, TypeMismatchError
from biocompiler.frontend.expressions import (
    Condition,
    ControlPort,
    Event,
    Expr,
    Parameter,
    Quantity,
    Signal,
    SpatialSignal,
    coerce_quantity,
    ensure_duration,
)
from biocompiler.frontend.graph import GraphBuilder
from biocompiler.semantics.types import (
    BOOLEAN,
    PRODUCTION_RATE,
    SURFACE_DENSITY,
    Level,
    TypeSpec,
    to_type_spec,
    validate_binding,
)


def _name(value: str, label: str = "name") -> str:
    if not isinstance(value, str) or not value.strip():
        raise DefinitionError(f"{label} must be a nonempty string")
    return value


def _same_owner(owner: Any, other: Any, *, local: bool = True) -> None:
    if getattr(other, "_graph", None) is not owner._graph:
        raise ScopeError("Objects from different therapies cannot be combined")
    if local and getattr(other, "role", None) not in (None, owner.role):
        raise ScopeError(
            "Cell-scoped objects must belong to the same role; use a channel to communicate"
        )


class Handle:
    """A named semantic object in one therapy graph."""

    def __init__(self, graph: GraphBuilder, node_id: str, *, role: str | None = None):
        self._graph = graph
        self.node_id = node_id
        self.role = role

    def __bool__(self) -> bool:
        raise TypeError(
            "biocompiler objects are symbolic; use biological conditions explicitly"
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(node_id={self.node_id!r})"


class Therapy:
    """A collection of in-vivo cell roles and their therapeutic behavior."""

    def __init__(self, name: str):
        self.name = _name(name, "therapy name")
        self._graph = GraphBuilder()
        self._roles: dict[str, CellProgram] = {}

    def engineer(self, name: str, *, cell_type: str) -> CellProgram:
        name, cell_type = _name(name), _name(cell_type, "cell_type")
        node = self._graph.declare(
            "roles",
            name,
            "role",
            attributes={"cell_type": cell_type, "engineering": "in_vivo"},
        )
        self._graph.mark_root(node)
        if name not in self._roles:
            self._roles[name] = CellProgram(
                self._graph, node, name=name, cell_type=cell_type
            )
        return self._roles[name]

    def parameter(
        self, name: str, *, type: Any = Level, default: Any = None
    ) -> Parameter:
        dtype = to_type_spec(type)
        attributes: dict[str, Any] = {"bound": default is not None}
        if default is not None:
            attributes["default"] = validate_binding(default, dtype)
        node = self._graph.declare(
            "parameters",
            _name(name),
            "parameter",
            attributes=attributes,
            data_type=dtype,
        )
        self._graph.mark_root(node)
        return Parameter(self._graph, node, dtype, None)

    def channel(self, name: str, *, scope: str, type: Any = Level) -> Channel:
        dtype = to_type_spec(type)
        if dtype.kind != "scalar":
            raise TypeMismatchError("A channel must carry a scalar quantity type")
        node = self._graph.declare(
            "channels",
            _name(name),
            "channel",
            attributes={"scope": _name(scope, "channel scope")},
            data_type=dtype,
        )
        self._graph.mark_root(node)
        return Channel(self._graph, node, dtype=dtype)

    def goal(self, name: str, *, description: str | None = None) -> Goal:
        attributes = (
            {}
            if description is None
            else {"description": _name(description, "goal description")}
        )
        node = self._graph.declare("goals", _name(name), "goal", attributes=attributes)
        self._graph.mark_root(node)
        return Goal(self._graph, node)

    def freeze(self):
        """Return an immutable snapshot; authoring may continue afterward."""
        return self._graph.freeze(self.name)


class Channel(Handle):
    def __init__(self, graph: GraphBuilder, node_id: str, *, dtype: TypeSpec):
        super().__init__(graph, node_id)
        self.dtype = dtype


class Goal(Handle):
    pass


class Scope(Handle):
    """An observation context bound to a particular cell role."""

    def __init__(self, graph: GraphBuilder, node_id: str, *, role: str, kind: str):
        super().__init__(graph, node_id, role=role)
        self.kind = kind

    def signal(self, name: str, *, type: Any = Level) -> Signal:
        dtype = to_type_spec(type)
        if dtype.kind != "scalar":
            raise TypeMismatchError("A signal must have a scalar quantity type")
        node = self._graph.declare(
            f"{self.node_id}:observations",
            _name(name),
            "signal",
            inputs=(self.node_id,),
            attributes={"observation": "signal", "scope": self.kind},
            data_type=dtype,
            role=self.role,
        )
        return Signal(self._graph, node, dtype, self.role)


class ContactScope(Scope):
    def marker(self, name: str, *, type: Any = None) -> Signal:
        dtype = SURFACE_DENSITY if type is None else to_type_spec(type)
        if dtype.kind != "scalar":
            raise TypeMismatchError(
                "A marker observation must have a scalar quantity type"
            )
        node = self._graph.declare(
            f"{self.node_id}:markers",
            _name(name),
            "signal",
            inputs=(self.node_id,),
            attributes={"observation": "marker", "scope": self.kind},
            data_type=dtype,
            role=self.role,
        )
        return Signal(self._graph, node, dtype, self.role)


class EnvironmentScope(Scope):
    def gradient(self, source: Channel | Signal) -> SpatialSignal:
        _same_owner(self, source)
        if isinstance(source, Channel):
            node = self._graph.add(
                "spatial_signal",
                inputs=(self.node_id, source.node_id),
                attributes={"source": "channel", "scope": "local"},
                data_type=source.dtype,
                role=self.role,
                intern=True,
            )
        elif isinstance(source, Signal):
            if source.role != self.role:
                raise ScopeError(
                    "A gradient must observe a signal in this cell's environment"
                )
            source_node = self._graph.get(source.node_id)
            if (
                source_node.kind not in ("signal", "channel_observation")
                or not source_node.inputs
                or source_node.inputs[0] != self.node_id
            ):
                raise ScopeError(
                    "A gradient requires a signal from this environment scope"
                )
            node = self._graph.add(
                "spatial_signal",
                inputs=(self.node_id, source.node_id),
                attributes={"source": "signal", "scope": "local"},
                data_type=source.dtype,
                role=self.role,
                intern=True,
            )
        else:
            raise TypeMismatchError(
                "gradient() expects a channel or environmental signal"
            )
        return SpatialSignal(self._graph, node, source.dtype, self.role)


class InternalScope(Scope):
    pass


class ExternalScope(Scope):
    pass


class CellProgram(Handle):
    """Intent executed independently by each cell assigned to a named role."""

    def __init__(self, graph: GraphBuilder, node_id: str, *, name: str, cell_type: str):
        super().__init__(graph, node_id, role=node_id)
        self.name, self.cell_type = name, cell_type
        self._scopes: dict[str, Scope] = {}

    def _scope(self, name: str, cls: type[Scope]) -> Scope:
        if name not in self._scopes:
            node = self._graph.declare(
                f"{self.role}:scopes",
                name,
                "scope",
                inputs=(self.node_id,),
                attributes={"scope": name},
                role=self.role,
            )
            self._scopes[name] = cls(self._graph, node, role=self.role, kind=name)
        return self._scopes[name]

    @property
    def contact(self) -> ContactScope:
        return self._scope("contact", ContactScope)

    @property
    def environment(self) -> EnvironmentScope:
        return self._scope("environment", EnvironmentScope)

    @property
    def internal(self) -> InternalScope:
        return self._scope("internal", InternalScope)

    @property
    def external(self) -> ExternalScope:
        return self._scope("external", ExternalScope)

    def when(self, condition: Condition, *, name: str | None = None) -> RuleBuilder:
        if not isinstance(condition, Condition):
            raise TypeMismatchError("when() expects a Condition; use on() for an Event")
        _same_owner(self, condition)
        return RuleBuilder(self, condition, trigger="condition", name=name)

    def on(self, event: Event, *, name: str | None = None) -> RuleBuilder:
        if not isinstance(event, Event):
            raise TypeMismatchError("on() expects an Event; use when() for a Condition")
        _same_owner(self, event)
        return RuleBuilder(self, event, trigger="event", name=name)

    def memory(
        self,
        name: str,
        *,
        set_when: Condition,
        reset_when: Condition | None = None,
        duration: Any = None,
    ) -> Memory:
        if not isinstance(set_when, Condition) or (
            reset_when is not None and not isinstance(reset_when, Condition)
        ):
            raise TypeMismatchError(
                "Memory setting and reset inputs must be Conditions"
            )
        _same_owner(self, set_when)
        inputs, input_names = [self.node_id, set_when.node_id], ["owner", "set_when"]
        if reset_when is not None:
            _same_owner(self, reset_when)
            inputs.append(reset_when.node_id)
            input_names.append("reset_when")
        if duration is not None:
            span = ensure_duration(duration, graph=self._graph, role=self.role)
            inputs.append(span.node_id)
            input_names.append("duration")
        node = self._graph.declare(
            f"{self.role}:memories",
            _name(name),
            "memory",
            inputs=tuple(inputs),
            attributes={
                "input_names": tuple(input_names),
                "initial": False,
                "setting": "onset",
                "initial_true_is_onset": True,
                "reset_priority": True,
                "expiry": "latest_setting_onset"
                if duration is not None
                else "until_reset",
            },
            data_type=BOOLEAN,
            role=self.role,
        )
        self._graph.mark_root(node)
        return Memory(self._graph, node, role=self.role)

    def state(self, name: str, *, values: Sequence[Any], initial: Any) -> State:
        if (
            isinstance(values, (str, bytes))
            or not isinstance(values, Sequence)
            or not values
        ):
            raise DefinitionError("State values must be a nonempty sequence")
        options = tuple(values)
        for value in options:
            if (
                not isinstance(value, (str, int, float, bool))
                or isinstance(value, float)
                and not math.isfinite(value)
            ):
                raise DefinitionError("State values must be finite JSON scalar values")
        keys = [(type(value), value) for value in options]
        if len(set(keys)) != len(keys):
            raise DefinitionError("State values must be distinct")
        if (type(initial), initial) not in keys:
            raise DefinitionError("Initial state must be one of the declared values")
        node = self._graph.declare(
            f"{self.role}:states",
            _name(name),
            "state",
            inputs=(self.node_id,),
            attributes={
                "values": options,
                "initial": initial,
                "observation": "prior_state",
                "arbitration": "unspecified",
            },
            role=self.role,
        )
        self._graph.mark_root(node)
        return State(self._graph, node, role=self.role, values=options)

    def secretion(self, name: str, *, product: str) -> Secretion:
        return self._secretion(
            _name(name), product=_name(product, "product"), default=False
        )

    def _secretion(self, name: str, *, product: str, default: bool) -> Secretion:
        namespace = (
            f"{self.role}:default_secretions" if default else f"{self.role}:secretions"
        )
        node = self._graph.declare(
            namespace,
            name,
            "secretion",
            inputs=(self.node_id,),
            attributes={
                "product": product,
                "default": default,
                "activity": "requires_rule_or_controller",
            },
            role=self.role,
        )
        self._graph.mark_root(node)
        return Secretion(self._graph, node, role=self.role, product=product)

    def regulate(
        self,
        name: str,
        *,
        observed: Quantity,
        target: Any,
        actuator: ControlPort,
        effect: str,
        when: Condition | None = None,
    ) -> Controller:
        if (
            not isinstance(observed, Quantity)
            or observed.dtype.kind != "scalar"
            or not isinstance(actuator, ControlPort)
        ):
            raise TypeMismatchError(
                "regulate() requires an observed scalar quantity and a controllable output port"
            )
        _same_owner(self, observed)
        _same_owner(self, actuator)
        if actuator.role != self.role:
            raise ScopeError("The actuator must belong to this cell role")
        if isinstance(target, Expr):
            _same_owner(self, target)
            target_expr = target
        elif getattr(getattr(target, "dtype", None), "kind", None) == "interval":
            binding = validate_binding(target, target.dtype)
            target_node = self._graph.add(
                "literal",
                attributes={"value": binding},
                data_type=target.dtype,
                intern=True,
            )
            target_expr = Expr(self._graph, target_node, target.dtype)
        else:
            target_expr = coerce_quantity(
                target, graph=self._graph, role=self.role, expected=observed.dtype
            )
        dtype = target_expr.dtype
        target_type = dtype.arguments[0] if dtype.kind == "interval" else dtype
        if not observed.dtype.compatible(target_type):
            raise TypeMismatchError(
                "Controller target must have the observed quantity's dimension, or an interval of that dimension"
            )
        if effect not in ("increase_observed", "decrease_observed"):
            raise DefinitionError(
                "effect must be 'increase_observed' or 'decrease_observed'"
            )
        inputs = [self.node_id, observed.node_id, target_expr.node_id, actuator.node_id]
        input_names = ["owner", "observed", "target", "actuator"]
        if when is not None:
            if not isinstance(when, Condition):
                raise TypeMismatchError("Controller when= must be a Condition")
            _same_owner(self, when)
            inputs.append(when.node_id)
            input_names.append("when")
        node = self._graph.declare(
            f"{self.role}:controllers",
            _name(name),
            "controller",
            inputs=tuple(inputs),
            attributes={
                "input_names": tuple(input_names),
                "effect": effect,
                "arbitration": "unspecified",
                "implementation": "unspecified",
            },
            role=self.role,
        )
        self._graph.mark_root(node)
        return Controller(self._graph, node, role=self.role)

    def sense(self, channel: Channel) -> Signal:
        if not isinstance(channel, Channel):
            raise TypeMismatchError("sense() expects a Channel")
        _same_owner(self, channel)
        node = self._graph.add(
            "channel_observation",
            inputs=(self.environment.node_id, channel.node_id),
            attributes={"scope": "receiver_local", "delivery": "biological_signal"},
            data_type=channel.dtype,
            role=self.role,
            intern=True,
        )
        return Signal(self._graph, node, channel.dtype, self.role)

    def receives(self, channel: Channel) -> Condition:
        return self.sense(channel).present()

    def _action(
        self,
        kind: str,
        *,
        inputs: tuple[str, ...] = (),
        attributes: dict[str, Any] | None = None,
        ongoing: bool = True,
    ) -> Action:
        attrs = {"ongoing": ongoing, **(attributes or {})}
        node = self._graph.add(
            f"action.{kind}",
            inputs=(self.node_id, *inputs),
            attributes=attrs,
            role=self.role,
        )
        return Action(self._graph, node, role=self.role, ongoing=ongoing)

    def _target_action(self, kind: str, target: ContactScope) -> Action:
        if not isinstance(target, ContactScope):
            raise TypeMismatchError(f"{kind}() expects an encountered target scope")
        _same_owner(self, target)
        return self._action(kind, inputs=(target.node_id,))

    def eliminate(self, target: ContactScope) -> Action:
        return self._target_action("eliminate", target)

    def engulf(self, target: ContactScope) -> Action:
        return self._target_action("engulf", target)

    def secrete(self, product: str, *, rate: Any = None) -> Action:
        product = _name(product, "product")
        return self._secretion(product, product=product, default=True).produce(
            rate=rate
        )

    def present(self, antigen: str) -> Action:
        return self._action(
            "present", attributes={"antigen": _name(antigen, "antigen")}
        )

    def emit(self, channel: Channel, *, value: Any = None) -> Action:
        if not isinstance(channel, Channel):
            raise TypeMismatchError("emit() expects a Channel")
        _same_owner(self, channel)
        inputs = (channel.node_id,)
        if value is not None:
            expression = coerce_quantity(
                value, graph=self._graph, role=self.role, expected=channel.dtype
            )
            inputs += (expression.node_id,)
        return self._action(
            "emit",
            inputs=inputs,
            attributes={"value": "unspecified" if value is None else "expression"},
        )

    def migrate_toward(self, signal: SpatialSignal) -> Action:
        if not isinstance(signal, SpatialSignal):
            raise TypeMismatchError(
                "migrate_toward() expects a spatial signal, such as environment.gradient(channel)"
            )
        _same_owner(self, signal)
        return self._action("migrate_toward", inputs=(signal.node_id,))

    def retain(self, location: str | Scope) -> Action:
        if isinstance(location, Scope):
            _same_owner(self, location)
            return self._action("retain", inputs=(location.node_id,))
        return self._action(
            "retain", attributes={"location": _name(location, "location")}
        )

    def expand(self) -> Action:
        return self._action("expand")

    def rest(self) -> Action:
        return self._action("rest")

    def differentiate(self, state: str) -> Action:
        return self._action(
            "differentiate", attributes={"phenotype": _name(state, "phenotype")}
        )

    def report(self, label: str) -> Action:
        return self._action(
            "report", attributes={"label": _name(label, "report label")}, ongoing=False
        )


class Action(Handle):
    def __init__(
        self, graph: GraphBuilder, node_id: str, *, role: str, ongoing: bool = True
    ):
        super().__init__(graph, node_id, role=role)
        self.ongoing = ongoing

    def for_(self, duration: Any) -> Action:
        if not self.ongoing:
            raise TypeMismatchError(
                "for_() applies to ongoing actions, not event reactions or state assignments"
            )
        span = ensure_duration(duration, graph=self._graph, role=self.role)
        node = self._graph.add(
            "action.pulse",
            inputs=(self.node_id, span.node_id),
            attributes={"ongoing": True, "retrigger": "extend_from_latest_trigger"},
            role=self.role,
        )
        return Action(self._graph, node, role=self.role, ongoing=True)


class RuleBuilder:
    def __init__(
        self,
        owner: CellProgram,
        trigger_expression: Condition | Event,
        *,
        trigger: str,
        name: str | None,
    ):
        self.owner, self.expression, self.trigger = owner, trigger_expression, trigger
        self.name = _name(name) if name is not None else None

    def do(self, *actions: Action) -> Rule:
        if not actions:
            raise DefinitionError("A rule must contain at least one action")
        for action in actions:
            if not isinstance(action, Action):
                raise TypeMismatchError("do() accepts Action specifications")
            _same_owner(self.owner, action)
        attrs = {
            "trigger": self.trigger,
            "execution": "concurrent",
            "priority": "unspecified",
        }
        if self.trigger == "event":
            attrs["ongoing_duration"] = "explicit_or_design_choice"
        inputs = (
            self.owner.node_id,
            self.expression.node_id,
            *(action.node_id for action in actions),
        )
        graph = self.owner._graph
        if self.name is None:
            node = graph.add(
                "rule", inputs=inputs, attributes=attrs, role=self.owner.role
            )
        else:
            node = graph.declare(
                f"{self.owner.role}:rules",
                self.name,
                "rule",
                inputs=inputs,
                attributes=attrs,
                role=self.owner.role,
            )
        graph.mark_root(node)
        return Rule(graph, node, role=self.owner.role)


class Rule(Handle):
    pass


class Controller(Handle):
    pass


class Memory(Handle):
    def is_set(self) -> Condition:
        node = self._graph.add(
            "memory.is_set",
            inputs=(self.node_id,),
            data_type=BOOLEAN,
            role=self.role,
            intern=True,
        )
        return Condition(self._graph, node, BOOLEAN, self.role)


class State(Handle):
    def __init__(
        self, graph: GraphBuilder, node_id: str, *, role: str, values: tuple[Any, ...]
    ):
        super().__init__(graph, node_id, role=role)
        self.values = values

    def _check_value(self, value: Any) -> None:
        if not any(
            type(value) is type(option) and value == option for option in self.values
        ):
            raise DefinitionError(f"{value!r} is not a declared state value")

    def is_(self, value: Any) -> Condition:
        self._check_value(value)
        node = self._graph.add(
            "state.is",
            inputs=(self.node_id,),
            attributes={"value": value},
            data_type=BOOLEAN,
            role=self.role,
            intern=True,
        )
        return Condition(self._graph, node, BOOLEAN, self.role)

    def set(self, value: Any) -> Action:
        self._check_value(value)
        node = self._graph.add(
            "action.state_set",
            inputs=(self.node_id,),
            attributes={"value": value, "idempotent": True, "ongoing": False},
            role=self.role,
        )
        return Action(self._graph, node, role=self.role, ongoing=False)


class Secretion(Handle):
    def __init__(self, graph: GraphBuilder, node_id: str, *, role: str, product: str):
        super().__init__(graph, node_id, role=role)
        self.product = product

    @property
    def rate(self) -> ControlPort:
        node = self._graph.add(
            "control_port",
            inputs=(self.node_id,),
            attributes={"port": "rate"},
            data_type=PRODUCTION_RATE,
            role=self.role,
            intern=True,
        )
        return ControlPort(self._graph, node, PRODUCTION_RATE, self.role)

    def produce(self, *, rate: Any = None) -> Action:
        inputs = (self.node_id,)
        if rate is not None:
            expression = coerce_quantity(
                rate, graph=self._graph, role=self.role, expected=PRODUCTION_RATE
            )
            inputs += (expression.node_id,)
        node = self._graph.add(
            "action.secrete",
            inputs=inputs,
            attributes={
                "ongoing": True,
                "rate": "unspecified" if rate is None else "expression",
            },
            role=self.role,
        )
        return Action(self._graph, node, role=self.role)
