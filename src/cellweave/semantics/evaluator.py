"""Reference execution of the abstract, single-cell behavior profile.

This interpreter evaluates requested behavior against supplied observations. It
does not predict biology or feed requested actions back into its input history.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import json
import math
from numbers import Real
from types import MappingProxyType
from typing import Any

from cellweave.errors import EvaluationError, NonConvergenceError, StateConflictError
from cellweave.ir.behavior import BehaviorProgram
from cellweave.ir.intent import SourceLocation, freeze_json, thaw_json

REFERENCE_EVALUATOR_VERSION = "cellweave.behavior.evaluator.v0.1"


def _finite(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EvaluationError(f"{label} must be a finite real number, not a Boolean.")
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise EvaluationError(f"{label} must be finite.")
    return int(value) if isinstance(value, int) else float(value)


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be a nonempty string.")
    return value


@dataclass(frozen=True)
class SignalSample:
    """Explicit qualitative observations and/or a canonical numeric value."""

    value: float | int | None = None
    present: bool | None = None
    high: bool | None = None
    low: bool | None = None

    def __post_init__(self) -> None:
        if self.value is not None:
            object.__setattr__(self, "value", _finite(self.value, "Signal value"))
        for name in ("present", "high", "low"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise EvaluationError(f"Signal {name} must be a Boolean or None.")

    def to_dict(self) -> dict:
        return {
            name: getattr(self, name) for name in ("value", "present", "high", "low")
        }


def _samples(values: Mapping[str, Any], label: str) -> Mapping[str, SignalSample]:
    if not isinstance(values, Mapping):
        raise EvaluationError(f"{label} must map signal node IDs to samples.")
    result = {}
    for key, value in values.items():
        _identifier(key, "Signal node ID")
        result[key] = (
            value if isinstance(value, SignalSample) else SignalSample(value=value)
        )
    return MappingProxyType(result)


@dataclass(frozen=True)
class InputFrame:
    """An atomic, complete observation snapshot; time is in canonical seconds."""

    time: float | int
    signals: Mapping[str, SignalSample | float | int] = field(default_factory=dict)
    contacts: Mapping[str, Mapping[str, SignalSample | float | int]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        time = _finite(self.time, "Input time")
        if time < 0:
            raise EvaluationError("Input time must be nonnegative.")
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "signals", _samples(self.signals, "signals"))
        if not isinstance(self.contacts, Mapping):
            raise EvaluationError(
                "contacts must map object identities to signal snapshots."
            )
        contacts = {
            _identifier(identity, "Contact identity"): _samples(
                samples, "Contact signals"
            )
            for identity, samples in self.contacts.items()
        }
        object.__setattr__(self, "contacts", MappingProxyType(contacts))

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "signals": {key: value.to_dict() for key, value in self.signals.items()},
            "contacts": {
                key: {ref: value.to_dict() for ref, value in samples.items()}
                for key, samples in self.contacts.items()
            },
        }


@dataclass(frozen=True)
class ActionRequest:
    """A traceable abstract output request, not a simulated physical effect."""

    action_id: str
    rule_id: str
    kind: str
    contact_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    values: Mapping[str, Any] = field(default_factory=dict)
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None
    rule_source: SourceLocation | None = None
    started_at: float | int | None = None
    expires_at: float | int | None = None
    specification_id: str | None = None
    specification_source: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_json(self.attributes))
        object.__setattr__(self, "values", freeze_json(self.values))
        object.__setattr__(self, "requirement_ids", tuple(self.requirement_ids))
        if self.specification_id is None:
            object.__setattr__(self, "specification_id", self.action_id)
            object.__setattr__(self, "specification_source", self.source)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "rule_id": self.rule_id,
            "kind": self.kind,
            "contact_id": self.contact_id,
            "attributes": thaw_json(self.attributes),
            "values": thaw_json(self.values),
            "requirement_ids": list(self.requirement_ids),
            "source": self.source.to_dict() if self.source else None,
            "rule_source": self.rule_source.to_dict() if self.rule_source else None,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "specification_id": self.specification_id,
            "specification_source": self.specification_source.to_dict()
            if self.specification_source
            else None,
        }


@dataclass(frozen=True)
class EventOccurrence:
    node_id: str
    contact_id: str | None = None
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_ids", tuple(self.requirement_ids))

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "contact_id": self.contact_id,
            "requirement_ids": list(self.requirement_ids),
            "source": self.source.to_dict() if self.source else None,
        }


@dataclass(frozen=True)
class EvaluationFrame:
    """Settled state and active requests, plus reactions during this timestamp."""

    time: float | int
    actions: tuple[ActionRequest, ...] = ()
    reactions: tuple[ActionRequest, ...] = ()
    events: tuple[EventOccurrence, ...] = ()
    states: Mapping[str, Any] = field(default_factory=dict)
    memories: Mapping[str, bool] = field(default_factory=dict)
    microsteps: int = 1

    def __post_init__(self) -> None:
        for name in ("actions", "reactions", "events"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "states", freeze_json(self.states))
        object.__setattr__(self, "memories", freeze_json(self.memories))

    @property
    def active_actions(self) -> tuple[ActionRequest, ...]:
        return self.actions

    @property
    def instant_actions(self) -> tuple[ActionRequest, ...]:
        return self.reactions

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "actions": [item.to_dict() for item in self.actions],
            "reactions": [item.to_dict() for item in self.reactions],
            "events": [item.to_dict() for item in self.events],
            "states": thaw_json(self.states),
            "memories": thaw_json(self.memories),
            "microsteps": self.microsteps,
        }


@dataclass(frozen=True)
class EvaluationResult:
    frames: tuple[EvaluationFrame, ...]
    role: str
    horizon: float | int
    behavior_fingerprint: str
    source_fingerprint: str
    execution_profile: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", tuple(self.frames))

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "horizon": self.horizon,
            "behavior_fingerprint": self.behavior_fingerprint,
            "source_fingerprint": self.source_fingerprint,
            "execution_profile": self.execution_profile,
            "frames": [frame.to_dict() for frame in self.frames],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, indent=indent, allow_nan=False
        )


class _Session:
    def __init__(self, program: BehaviorProgram, role: str, max_microsteps: int):
        self.program, self.role, self.max_microsteps = program, role, max_microsteps
        self.nodes = {node.id: node for node in program.nodes}
        live = set()
        pending = [ref for ref in program.roots if self.nodes[ref].role in (None, role)]
        while pending:
            ref = pending.pop()
            if ref in live:
                continue
            live.add(ref)
            node = self.nodes[ref]
            pending.extend(node.inputs[:1] if node.kind == "signature" else node.inputs)
        self.local = tuple(
            node
            for node in program.nodes
            if node.id in live and node.role in (None, role)
        )
        self.rules = tuple(node for node in self.local if node.kind == "rule")
        self.memory_nodes = tuple(node for node in self.local if node.kind == "memory")
        self.memory_nodes = self._ordered_memories(self.memory_nodes)
        self._memory_working: dict[str, bool] | None = None
        self.states = {
            node.id: node.attributes["initial"]
            for node in self.local
            if node.kind == "state"
        }
        self.memories = {node.id: False for node in self.memory_nodes}
        self.previous: dict[tuple[str, str, str | None], bool] = {}
        self.held: dict[tuple[str, str | None], float | int] = {}
        self.recent: dict[tuple[str, str | None], float | int] = {}
        self.first_events: dict[tuple[str, str | None], list[float | int]] = {}
        self.timers: dict[tuple[str, str, str | None], float | int] = {}
        self.pulses: dict[
            tuple[str, str, str | None], tuple[float | int, float | int]
        ] = {}
        self.input = InputFrame(0)
        self.time: float | int = 0
        self.cache: dict[tuple[str, str | None], Any] = {}
        self.events: list[EventOccurrence] = []
        self.required = self._required_observations()

    def _ordered_memories(self, memories: tuple) -> tuple:
        """Resolve causal memory dependencies before consuming their controls."""
        ordered = []
        visited = set()
        visiting = set()

        def dependencies(node):
            pending = list(node.inputs)
            seen = set()
            result = set()
            while pending:
                ref = pending.pop()
                if ref in seen:
                    continue
                seen.add(ref)
                dependency = self.nodes[ref]
                if dependency.kind == "memory":
                    result.add(ref)
                else:
                    pending.extend(
                        dependency.inputs[:1]
                        if dependency.kind == "signature"
                        else dependency.inputs
                    )
            return sorted(result)

        def visit(node):
            if node.id in visited:
                return
            if node.id in visiting:
                raise self._error(node, "Memory controls contain a dependency cycle")
            visiting.add(node.id)
            for ref in dependencies(node):
                visit(self.nodes[ref])
            visiting.remove(node.id)
            visited.add(node.id)
            ordered.append(node)

        for node in memories:
            visit(node)
        return tuple(ordered)

    def _error(self, node: Any, message: str) -> EvaluationError:
        source = f" ({node.source.file}:{node.source.line})" if node.source else ""
        return EvaluationError(f"{message} [node {node.id}]{source}")

    def _required_observations(self) -> dict[str, set[str]]:
        required: dict[str, set[str]] = {}
        for node in self.local:
            if node.kind == "qualitative":
                required.setdefault(node.inputs[0], set()).add(node.attributes["band"])
            elif node.kind not in {"signature", "scope", "role"}:
                for ref in node.inputs:
                    if self.nodes[ref].kind == "signal":
                        required.setdefault(ref, set()).add("value")
        return required

    def update_input(self, frame: InputFrame) -> None:
        disappeared = set(self.input.contacts) - set(frame.contacts)
        for mapping in (self.previous, self.timers, self.pulses):
            for key in tuple(mapping):
                if key[-1] in disappeared:
                    del mapping[key]
        for mapping in (self.held, self.recent, self.first_events):
            for key in tuple(mapping):
                if key[-1] in disappeared:
                    del mapping[key]
        for identity, samples in ((None, frame.signals), *frame.contacts.items()):
            for ref in samples:
                node = self.nodes.get(ref)
                if node is None or node.kind != "signal" or node.role != self.role:
                    raise EvaluationError(
                        f"Unknown signal {ref!r} for the selected role."
                    )
                if node.contact_bound != (identity is not None):
                    raise self._error(
                        node, "Signal supplied in the wrong observation scope"
                    )
            for ref, fields in self.required.items():
                node = self.nodes[ref]
                if node.contact_bound != (identity is not None):
                    continue
                sample = samples.get(ref)
                if sample is None:
                    raise self._error(
                        node, f"Missing observation for contact {identity!r}"
                    )
                for name in fields:
                    if getattr(sample, name) is None:
                        raise self._error(
                            node,
                            f"Missing explicit {name} observation for contact {identity!r}",
                        )
        self.input = frame

    def bindings(self, node: Any) -> tuple[str | None, ...]:
        return tuple(sorted(self.input.contacts)) if node.contact_bound else (None,)

    def _deadline(self, key: tuple[str, str, str | None], duration: Any) -> float | int:
        deadline = _finite(self.time + duration, "Timer deadline")
        if deadline <= self.time:
            raise EvaluationError(
                "A positive duration must advance the representable timer deadline."
            )
        self.timers[key] = deadline
        return deadline

    def _onset(self, kind: str, node_id: str, binding: str | None, value: bool) -> bool:
        key = (kind, node_id, binding)
        before = self.previous.get(key, False)
        self.previous[key] = value
        return value and not before

    def value(self, node_id: str, binding: str | None = None) -> Any:
        node = self.nodes[node_id]
        binding = binding if node.contact_bound else None
        key = (node_id, binding)
        if key in self.cache:
            return self.cache[key]
        if node.contact_bound and binding is None:
            raise self._error(node, "A contacted-object binding is required")
        kind, attrs = node.kind, node.attributes

        def args():
            return [self.value(ref, binding) for ref in node.inputs]

        if kind in {"literal", "parameter"}:
            value = attrs["value" if kind == "literal" else "default"][
                "canonical_value"
            ]
        elif kind == "signal":
            samples = (
                self.input.contacts[binding]
                if binding is not None
                else self.input.signals
            )
            sample = samples.get(node_id)
            if sample is None or sample.value is None:
                raise self._error(node, "Missing numeric observation")
            value = sample.value
        elif kind == "qualitative":
            samples = (
                self.input.contacts[binding]
                if binding is not None
                else self.input.signals
            )
            sample = samples.get(node.inputs[0])
            value = getattr(sample, attrs["band"], None)
            if value is None:
                raise self._error(node, f"Missing explicit {attrs['band']} observation")
        elif kind in {"and", "or", "at_least"}:
            values = args()
            value = (
                all(values)
                if kind == "and"
                else any(values)
                if kind == "or"
                else sum(values) >= attrs["count"]
            )
        elif kind == "not":
            value = not self.value(node.inputs[0], binding)
        elif kind in {"add", "subtract", "multiply", "divide"}:
            left, right = args()
            if kind == "divide" and right == 0:
                raise self._error(node, "Division by zero during behavior evaluation")
            try:
                value = {
                    "add": lambda: left + right,
                    "subtract": lambda: left - right,
                    "multiply": lambda: left * right,
                    "divide": lambda: left / right,
                }[kind]()
                value = _finite(value, f"Arithmetic result at {node.id}")
            except OverflowError as exc:
                raise self._error(node, "Non-finite arithmetic result") from exc
        elif kind == "negate":
            value = -self.value(node.inputs[0], binding)
        elif kind == "compare":
            left, right = args()
            value = {
                "lt": lambda: left < right,
                "le": lambda: left <= right,
                "gt": lambda: left > right,
                "ge": lambda: left >= right,
                "eq": lambda: left == right,
                "ne": lambda: left != right,
            }[attrs["operator"]]()
        elif kind == "signature":
            value = self.value(node.inputs[0], binding)
        elif kind == "state.is":
            actual, expected = self.states[node.inputs[0]], attrs["value"]
            value = type(actual) is type(expected) and actual == expected
        elif kind in {"memory", "memory.is_set"}:
            memories = (
                self.memories if self._memory_working is None else self._memory_working
            )
            value = memories[node.id if kind == "memory" else node.inputs[0]]
        elif kind in {"held_for", "recently"}:
            active, duration = args()
            timer_key = (kind, node_id, binding)
            if kind == "held_for":
                if active:
                    if key not in self.held:
                        self.held[key] = self.time
                        self._deadline(timer_key, duration)
                    value = self.time >= self.held[key] + duration
                    if value:
                        self.timers.pop(timer_key, None)
                else:
                    self.held.pop(key, None)
                    self.timers.pop(timer_key, None)
                    value = False
            else:
                prev_key = ("recent_input", node_id, binding)
                was_active = self.previous.get(prev_key, False)
                self.previous[prev_key] = active
                if active:
                    self.recent.pop(key, None)
                    self.timers.pop(timer_key, None)
                    value = True
                else:
                    if was_active:
                        self.recent[key] = self._deadline(timer_key, duration)
                    value = self.time < self.recent.get(key, self.time)
                    if not value:
                        self.timers.pop(timer_key, None)
        elif kind == "became_true":
            value = self._onset(
                "event", node_id, binding, self.value(node.inputs[0], binding)
            )
        elif kind == "followed_by":
            first, second, duration = args()
            times = [
                time
                for time in self.first_events.get(key, ())
                if time >= self.time - duration
            ]
            value = second and any(time < self.time for time in times)
            if first and (not times or times[-1] != self.time):
                times.append(self.time)
            self.first_events[key] = times
        else:
            raise self._error(node, f"Unsupported expression kind {kind!r}")
        self.cache[key] = value
        if kind in {"became_true", "followed_by"} and value:
            self.events.append(
                EventOccurrence(node.id, binding, node.requirement_ids, node.source)
            )
        return value

    def _memory_updates(self) -> dict[str, bool]:
        # Consumer controls see settled producer memories. No rule or event
        # observes intermediate phase values, and each onset is evaluated once.
        updates = dict(self.memories)
        self._memory_working = updates
        try:
            for node in self.memory_nodes:
                self.cache = {}
                self._update_memory(node, updates)
        finally:
            self._memory_working = None
        return updates

    def _update_memory(self, node: Any, updates: dict[str, bool]) -> None:
        refs = dict(zip(node.attributes["input_names"], node.inputs))
        setting = self.nodes[refs["set_when"]]
        onset = False
        for binding in self.bindings(setting):
            current = self.value(setting.id, binding)
            onset = self._onset("memory_set", node.id, binding, current) or onset
        reset = False
        if "reset_when" in refs:
            resetting = self.nodes[refs["reset_when"]]
            reset = any(
                [
                    self.value(resetting.id, binding)
                    for binding in self.bindings(resetting)
                ]
            )
        timer_key = ("memory", node.id, None)
        if reset:
            updates[node.id] = False
            self.timers.pop(timer_key, None)
        elif onset:
            updates[node.id] = True
            if "duration" in refs:
                self._deadline(timer_key, self.value(refs["duration"]))
        elif self.timers.get(timer_key, math.inf) <= self.time:
            updates[node.id] = False
            self.timers.pop(timer_key, None)
        else:
            updates[node.id] = self.memories[node.id]

    def _request(
        self,
        rule: Any,
        action: Any,
        binding: str | None,
        *,
        started_at=None,
        expires_at=None,
        specification=None,
    ) -> ActionRequest:
        attrs = thaw_json(action.attributes)
        values = {}
        if action.kind == "action.secrete":
            secretion = self.nodes[action.inputs[0]]
            attrs["product"] = secretion.attributes["product"]
            attrs["secretion_id"] = secretion.id
            if len(action.inputs) > 1:
                values["rate"] = self.value(action.inputs[1], binding)
        requirements = tuple(
            sorted(set(rule.requirement_ids) | set(action.requirement_ids))
        )
        specification = action if specification is None else specification
        return ActionRequest(
            action.id,
            rule.id,
            action.kind,
            binding,
            attrs,
            values,
            requirements,
            action.source,
            rule.source,
            started_at,
            expires_at,
            specification.id,
            specification.source,
        )

    def step(self, time: float | int) -> EvaluationFrame:
        self.time = time
        self.events = []
        reactions = []
        microstep = 0
        while microstep < self.max_microsteps:
            # Settle memory controls before observing rule events. In particular,
            # a memory expiring now must not enable a reaction to a simultaneous
            # external input, and an onset refreshing it must not create a false
            # intermediate falling/rising edge.
            self.cache = {}
            memory_updates = self._memory_updates()
            if memory_updates != self.memories:
                self.memories = memory_updates
                microstep += 1
                if microstep >= self.max_microsteps:
                    raise NonConvergenceError(
                        f"Behavior exhausted {self.max_microsteps} microsteps during memory settlement at time {time}."
                    )
            microstep += 1
            self.cache = {}
            # Evaluate every used condition/event, including operands behind a
            # false guard, so history does not depend on short-circuit order.
            for node in self.local:
                if (
                    node.data_type
                    and node.data_type["kind"] in {"condition", "event"}
                    and node.kind != "memory"
                ):
                    for binding in self.bindings(node):
                        self.value(node.id, binding)
            writes: dict[str, tuple[Any, str]] = {}
            active = []
            for rule in self.rules:
                guard = self.nodes[rule.inputs[1]]
                guard_values = {
                    binding: self.value(guard.id, binding)
                    for binding in self.bindings(guard)
                }
                activations = {}
                for ref in rule.inputs[2:]:
                    action = self.nodes[ref]
                    for binding in self.bindings(action):
                        if binding not in activations:
                            enabled = (
                                guard_values.get(binding, False)
                                if guard.contact_bound and binding is not None
                                else any(guard_values.values())
                            )
                            trigger = (
                                enabled
                                if rule.attributes["trigger"] == "event"
                                else self._onset("rule", rule.id, binding, enabled)
                            )
                            activations[binding] = (enabled, trigger)
                        enabled, trigger = activations[binding]
                        if action.kind == "action.state_set":
                            if enabled:
                                state_id, desired = (
                                    action.inputs[0],
                                    action.attributes["value"],
                                )
                                if state_id in writes:
                                    previous, previous_rule = writes[state_id]
                                    if (
                                        type(previous) is not type(desired)
                                        or previous != desired
                                    ):
                                        raise StateConflictError(
                                            f"Conflicting assignments to state {state_id}: rules {previous_rule} and {rule.id} at time {time}."
                                        )
                                writes[state_id] = (desired, rule.id)
                        elif action.kind == "action.pulse":
                            key = (rule.id, action.id, binding)
                            if trigger:
                                duration = self.value(action.inputs[1], binding)
                                end = self._deadline(
                                    ("pulse", f"{rule.id}:{action.id}", binding),
                                    duration,
                                )
                                self.pulses[key] = (time, end)
                            pulse = self.pulses.get(key)
                            if pulse and time < pulse[1]:
                                active.append(
                                    self._request(
                                        rule,
                                        self.nodes[action.inputs[0]],
                                        binding,
                                        started_at=pulse[0],
                                        expires_at=pulse[1],
                                        specification=action,
                                    )
                                )
                            elif pulse:
                                del self.pulses[key]
                                self.timers.pop(
                                    ("pulse", f"{rule.id}:{action.id}", binding), None
                                )
                        elif action.attributes["ongoing"]:
                            if enabled:
                                active.append(self._request(rule, action, binding))
                        elif trigger:
                            reactions.append(
                                self._request(rule, action, binding, started_at=time)
                            )
            next_states = {
                **self.states,
                **{key: item[0] for key, item in writes.items()},
            }
            changed = any(
                type(self.states[key]) is not type(value) or self.states[key] != value
                for key, value in next_states.items()
            )
            self.states = next_states
            if not changed:
                return EvaluationFrame(
                    time,
                    tuple(active),
                    tuple(reactions),
                    tuple(self.events),
                    self.states,
                    self.memories,
                    microstep,
                )
        raise NonConvergenceError(
            f"Behavior did not converge at time {time} within {self.max_microsteps} microsteps."
        )


def evaluate(
    program: BehaviorProgram,
    history: Iterable[InputFrame],
    *,
    role: str | None = None,
    until: float | int | None = None,
    max_microsteps: int = 1000,
) -> EvaluationResult:
    """Evaluate one cell against a complete piecewise-constant input history.

    ``until`` defaults to the final supplied input time. Supply a later horizon
    to observe timer-driven behavior after that snapshot. The horizon is
    inclusive; pulse and recent-window expiry endpoints remain exclusive.
    """
    if not isinstance(program, BehaviorProgram):
        raise EvaluationError("evaluate() requires a lowered BehaviorProgram.")
    if type(max_microsteps) is not int or max_microsteps <= 0:
        raise EvaluationError("max_microsteps must be a positive integer.")
    roles = [node for node in program.nodes if node.kind == "role"]
    if role is None:
        if len(roles) != 1:
            raise EvaluationError(
                "Select a role explicitly when a program does not have exactly one role."
            )
        selected = roles[0].id
    else:
        if not isinstance(role, str):
            raise EvaluationError("role must be a role node ID or name.")
        matches = [
            node
            for node in roles
            if node.id == role or node.attributes.get("name") == role
        ]
        if len(matches) != 1:
            raise EvaluationError(f"Unknown or ambiguous role {role!r}.")
        selected = matches[0].id
    try:
        frames = tuple(history)
    except TypeError as exc:
        raise EvaluationError(
            "history must be an iterable of InputFrame snapshots."
        ) from exc
    if not frames or any(not isinstance(frame, InputFrame) for frame in frames):
        raise EvaluationError(
            "history must contain InputFrame snapshots, starting at time zero."
        )
    if frames[0].time != 0:
        raise EvaluationError("Input history must start at time zero.")
    if any(right.time <= left.time for left, right in zip(frames, frames[1:])):
        raise EvaluationError(
            "Input timestamps must be strictly increasing; combine simultaneous inputs atomically."
        )
    horizon = frames[-1].time if until is None else _finite(until, "Evaluation horizon")
    if horizon < 0:
        raise EvaluationError("Evaluation horizon must be nonnegative.")
    session = _Session(program, selected, max_microsteps)
    results = []
    index = 0
    time: float | int = 0
    while True:
        if index < len(frames) and frames[index].time == time:
            session.update_input(frames[index])
            index += 1
        results.append(session.step(time))
        if time == horizon:
            break
        candidates = [horizon]
        if index < len(frames) and frames[index].time <= horizon:
            candidates.append(frames[index].time)
        candidates.extend(
            deadline
            for deadline in session.timers.values()
            if time < deadline <= horizon
        )
        time = min(candidates)
    return EvaluationResult(
        tuple(results),
        selected,
        horizon,
        program.fingerprint,
        program.source_fingerprint,
        program.policies["profile"],
    )
