"""Exact sampled reservoir authoring; supplied contracts are not biological proof.

One accepted True sample adds one quantum; False subtracts one quantum, with
saturation. Unknown and absent updates hold. Only upward threshold crossing
requests an effect. Quantities express amount per sample, not a continuous rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from . import logic, model as m
from .programs import ref
from .serialization import to_data
from .typed import _owners as _source_owners


class QuantitativeAuthoringError(ValueError):
    """Invalid local contract authoring; no native admission has occurred."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QuantitativeAuthoringError(message)


def _name(value: str) -> None:
    _require(type(value) is str and 0 < len(value.encode("utf-8")) <= 256 and bool(value.strip()), "A bounded explicit identity is required")


def _value(value: m.Quantity) -> Fraction:
    _require(type(value) is m.Quantity and type(value.amount) is str, "Use an exact source Quantity")
    to_data(value)
    # Source Quantity canonicalizes bounded decimal strings independently of the
    # process Decimal precision. Fractions preserve every subsequent comparison.
    canonical = m.Quantity(value.amount, value.unit)
    _require(canonical.amount == value.amount, "Quantity must retain canonical exact decimal spelling")
    return Fraction(value.amount)


def _scaled(quantum: m.Quantity, multiple: int) -> m.Quantity:
    digits = quantum.amount.replace(".", "")
    places = len(quantum.amount.partition(".")[2])
    integer = int(digits) * multiple
    text = str(integer).zfill(places + 1)
    if places:
        text = text[:-places] + "." + text[-places:]
    return m.Quantity(text, quantum.unit)


@dataclass(frozen=True, slots=True)
class SampledReservoir:
    """Original finite amount law; no policy Record or checked native capability."""
    substance: str
    compartment: str
    unit: m.Unit
    quantum: m.Quantity
    capacity: m.Quantity
    threshold: m.Quantity
    initial: m.Quantity
    sample_period: m.Quantity

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> tuple[int, int, int]:
        _name(self.substance)
        _name(self.compartment)
        _require(type(self.unit) is m.Unit, "Reservoir requires a complete source Unit")
        to_data(self.unit)
        _require((self.unit.dimension, self.unit.quantity_kind) in (("count", "count"), ("amount", "amount")),
                 "Reservoir units must explicitly denote count or amount")
        _name(self.unit.id)
        if self.unit.reference is not None:
            _name(self.unit.reference)
        _require(_value(m.Quantity(self.unit.scale, self.unit)) > 0, "Unit scale must be a positive exact decimal")
        values = (self.quantum, self.capacity, self.threshold, self.initial)
        for value in values:
            _value(value)
            _require(value.unit == self.unit, "All reservoir quantities require identical complete units; conversions are explicit")
        quantum, capacity, threshold, initial = (_value(value) for value in values)
        _require(quantum > 0, "Quantum must be positive")
        counts = tuple(value / quantum for value in (capacity, threshold, initial))
        _require(all(value.denominator == 1 for value in counts), "Capacity, threshold and initial must be exact multiples of quantum")
        top, crossing, start = (value.numerator for value in counts)
        _require(1 <= top <= 15 and 1 <= crossing <= top and 0 <= start <= top,
                 "Reservoir requires 2–16 grid states, a positive threshold, and an in-range initial amount")
        _require(_value(self.sample_period) > 0 and self.sample_period.unit.dimension == "time"
                 and self.sample_period.unit.quantity_kind == "duration", "Sampling requires a positive exact duration")
        _name(self.sample_period.unit.id)
        _require(self.sample_period.unit.reference is None, "Sampling duration units require an unreferenced time identity")
        _require(_value(m.Quantity(self.sample_period.unit.scale, self.sample_period.unit)) > 0, "Sampling unit scale must be positive")
        return top, crossing, start

    @property
    def levels(self) -> tuple[m.Quantity, ...]:
        top, _, _ = self._validate()
        return tuple(_scaled(self.quantum, index) for index in range(top + 1))

    def to_data(self) -> dict[str, JsonValue]:
        self._validate()
        return {"schema_version": "biocompiler.policy_sampled_reservoir.v0.1",
            "profile": "biocompiler.policy_sampled_saturating_reservoir.v0.1", "substance": self.substance,
            "compartment": self.compartment, "unit": cast(JsonValue, to_data(self.unit)),
            **{key: cast(JsonValue, to_data(value)) for key, value in (("quantum", self.quantum), ("capacity", self.capacity),
                ("threshold", self.threshold), ("initial", self.initial), ("sample_period", self.sample_period))}}

    def state_values(self, states: tuple[str, ...]) -> list[JsonValue]:
        levels = self.levels
        _require(type(states) is tuple and len(states) == len(levels), "State names must cover the complete ordered quantity grid")
        for state in states:
            _name(state)
        _require(len(set(states)) == len(states), "Reservoir state names must be distinct")
        return [{"state": state, "quantity": cast(JsonValue, to_data(value))} for state, value in zip(states, levels)]

    def _source(self, machine: m.Machine, observation: m.Observation, effect: m.Effect) -> tuple[int, int]:
        top, crossing, start = self._validate()
        _require(type(machine) is m.Machine and type(observation) is m.Observation and type(effect) is m.Effect,
                 "Use distinct source machine, observation and effect declarations")
        for value in (machine, observation, effect):
            to_data(value)
            _name(value.id)
        _source_owners(machine, observation, effect)
        self.state_values(machine.states)
        _require(machine.initial == machine.states[start] and machine.terminal == () and machine.lifetime == "encounter",
                 "Machine initial, terminal and reset declarations must implement the original reservoir law")
        _require(machine.scope.kind == "encounter" and machine.arbitration == m.Arbitration("exclusive", "reject", "reject", "forbidden", "none"),
                 "Reservoir machine needs explicit encounter scope and exclusive rejection arbitration")
        _require(observation.value_type == m.TRUTH and observation.subject == effect.subject
                 and observation.observer == machine.executor == effect.executor,
                 "Reservoir observation and effect must share the machine executor and exact subject")
        _require(observation.freshness == self.sample_period,
                 "This profile requires one sampling-period freshness for same-tick observations")
        return top, crossing

    def transitions(self, machine: m.Machine, observation: m.Observation, effect: m.Effect, *, prefix: str) -> tuple[m.Transition, ...]:
        """Author ordinary source; later admission checks clock, domain and contracts."""
        top, crossing = self._source(machine, observation, effect)
        _name(prefix)
        result = []
        for index, state in enumerate(machine.states):
            result.append(m.Transition(prefix + "/up" + str(index), ref(machine), state, machine.states[min(index + 1, top)],
                observation.updated, observation.expression, "defer", (ref(effect),) if index + 1 == crossing else ()))
            result.append(m.Transition(prefix + "/down" + str(index), ref(machine), state, machine.states[max(index - 1, 0)],
                observation.updated, logic.not_(observation.expression), "defer", ()))
        return tuple(result)

    def bind(self, *, instance: str, component: JsonValue, contract: str,
             machine: m.Machine, observation: m.Observation, effect: m.Effect) -> dict[str, JsonValue]:
        """Snapshot independent original law and selected component contract identity."""
        self._source(machine, observation, effect)
        _name(instance)
        _name(contract)
        pin = decode_json(encode_json(component))
        _require(type(pin) is dict and set(pin) == {"schema_version", "kind", "id", "version", "content_fingerprint"},
                 "Selected component requires a complete exact model identity")
        identity = cast(dict[str, JsonValue], pin)
        _require(identity["schema_version"] == "biocompiler.component_identity.v0.1" and identity["kind"] == "model",
                 "Selected quantitative component must use the model identity profile")
        for key in ("id", "version"):
            _name(cast(str, identity[key]))
        digest = identity["content_fingerprint"]
        _require(type(digest) is str and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest),
                 "Selected component fingerprint must be lowercase SHA-256")
        return {"mechanism": self.to_data(), "selection": {"instance": instance, "component": identity, "contract": contract},
            "source": {"machine": machine.id, "observation": observation.id, "effect": effect.id}}


__all__ = ["QuantitativeAuthoringError", "SampledReservoir"]
