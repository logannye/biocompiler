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


@dataclass(frozen=True, slots=True)
class SampledStepReservoir(SampledReservoir):
    """Exact asymmetric steps on a finite grid, with every upward crossing retained.

    ``quantum`` fixes the state grid. ``rise`` and ``fall`` are amounts per
    accepted True and False sample, respectively; neither denotes a rate.
    """

    rise: m.Quantity
    fall: m.Quantity

    def _validate(self) -> tuple[int, int, int]:
        bounds = SampledReservoir._validate(self)
        for step in (self.rise, self.fall):
            value = _value(step)
            _require(step.unit == self.unit, "Step quantities require the complete reservoir unit")
            _require(0 < value <= _value(self.capacity), "Rise and fall must be positive and no larger than capacity")
            _require((value / _value(self.quantum)).denominator == 1, "Rise and fall must be exact multiples of quantum")
        return bounds

    def to_data(self) -> dict[str, JsonValue]:
        original = SampledReservoir.to_data(self)
        return {**original, "schema_version": "biocompiler.policy_sampled_reservoir.v0.2",
            "profile": "biocompiler.policy_sampled_saturating_step_reservoir.v0.1",
            "rise": cast(JsonValue, to_data(self.rise)), "fall": cast(JsonValue, to_data(self.fall))}

    def transitions(self, machine: m.Machine, observation: m.Observation, effect: m.Effect, *, prefix: str) -> tuple[m.Transition, ...]:
        """Expand every state/sample pair, including distinct sites for one effect."""
        top, crossing = self._source(machine, observation, effect)
        _name(prefix)
        rise = int(_value(self.rise) / _value(self.quantum))
        fall = int(_value(self.fall) / _value(self.quantum))
        result = []
        for index, state in enumerate(machine.states):
            destination = min(index + rise, top)
            result.append(m.Transition(prefix + "/up" + str(index), ref(machine), state, machine.states[destination],
                observation.updated, observation.expression, "defer", (ref(effect),) if index < crossing <= destination else ()))
            result.append(m.Transition(prefix + "/down" + str(index), ref(machine), state, machine.states[max(index - fall, 0)],
                observation.updated, logic.not_(observation.expression), "defer", ()))
        return tuple(result)


@dataclass(frozen=True, slots=True)
class ReservoirCompartment:
    """A named finite amount store; shared substance and grid belong to its law."""

    compartment: str
    capacity: m.Quantity
    initial: m.Quantity

    def __post_init__(self) -> None:
        _name(self.compartment)
        capacity, initial = _value(self.capacity), _value(self.initial)
        _require(self.capacity.unit == self.initial.unit, "Compartment amounts require identical complete units")
        _require(capacity > 0 and 0 <= initial <= capacity, "Compartment capacity must be positive and initial must lie within it")

    def to_data(self) -> dict[str, JsonValue]:
        return {"compartment": self.compartment, "capacity": cast(JsonValue, to_data(self.capacity)),
                "initial": cast(JsonValue, to_data(self.initial))}


@dataclass(frozen=True, slots=True)
class SampledTransferPair:
    """Two exact stores with conservative, simultaneous transfer from prestate.

    True transfers source to destination; False reverses the direction. Unknown
    and absent samples hold both stores. Reset restores the original pair and
    starts a new encounter generation; it is outside sample conservation.
    """

    substance: str
    unit: m.Unit
    quantum: m.Quantity
    source: ReservoirCompartment
    destination: ReservoirCompartment
    forward: m.Quantity
    reverse: m.Quantity
    threshold: m.Quantity
    sample_period: m.Quantity

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> tuple[int, int, int, int, int, int, int]:
        _require(type(self.source) is ReservoirCompartment and type(self.destination) is ReservoirCompartment,
                 "Transfer pairs require two explicit reservoir compartments")
        _require(self.source.compartment != self.destination.compartment, "Transfer compartments must have distinct nominal identities")
        # Apply the already closed exact unit/grid/clock rules to each store.
        grids = [SampledReservoir(self.substance, compartment.compartment, self.unit, self.quantum,
                    compartment.capacity, self.quantum, compartment.initial, self.sample_period)._validate()
                 for compartment in (self.source, self.destination)]
        source_top, _, source_initial = grids[0]
        destination_top, _, destination_initial = grids[1]
        _require((source_top + 1) * (destination_top + 1) <= 16, "The complete Cartesian transfer grid must contain at most sixteen states")
        values = []
        for value, capacity in ((self.forward, self.source.capacity), (self.reverse, self.destination.capacity),
                                (self.threshold, self.destination.capacity)):
            amount = _value(value)
            _require(value.unit == self.unit, "Transfer steps and threshold require the complete shared unit")
            count = amount / _value(self.quantum)
            _require(0 < amount <= _value(capacity) and count.denominator == 1,
                     "Transfer steps and destination threshold must be positive exact grid multiples within their own capacity")
            values.append(count.numerator)
        return source_top, destination_top, source_initial, destination_initial, values[0], values[1], values[2]

    @property
    def levels(self) -> tuple[tuple[m.Quantity, m.Quantity], ...]:
        """Complete source-major, destination-minor Cartesian quantity vectors."""
        source_top, destination_top, *_ = self._validate()
        return tuple((_scaled(self.quantum, source), _scaled(self.quantum, destination))
                     for source in range(source_top + 1) for destination in range(destination_top + 1))

    def to_data(self) -> dict[str, JsonValue]:
        self._validate()
        return {"schema_version": "biocompiler.policy_sampled_transfer_pair.v0.1",
            "profile": "biocompiler.policy_sampled_conservative_transfer_pair.v0.1",
            "substance": self.substance, "unit": cast(JsonValue, to_data(self.unit)),
            "quantum": cast(JsonValue, to_data(self.quantum)), "source": self.source.to_data(), "destination": self.destination.to_data(),
            **{key: cast(JsonValue, to_data(value)) for key, value in (("forward", self.forward), ("reverse", self.reverse),
                ("threshold", self.threshold), ("sample_period", self.sample_period))}}

    def state_values(self, states: tuple[str, ...]) -> list[JsonValue]:
        levels = self.levels
        _require(type(states) is tuple and len(states) == len(levels), "State labels must cover the complete ordered Cartesian quantity grid")
        for state in states:
            _name(state)
        _require(len(set(states)) == len(states), "Transfer-pair state labels must be distinct")
        return [{"state": state, "source": cast(JsonValue, to_data(source)), "destination": cast(JsonValue, to_data(destination))}
                for state, (source, destination) in zip(states, levels)]

    def _source(self, machine: m.Machine, observation: m.Observation, effect: m.Effect) -> tuple[int, int, int, int, int, int, int]:
        shape = self._validate()
        _require(type(machine) is m.Machine and type(observation) is m.Observation and type(effect) is m.Effect,
                 "Use exact source machine, observation and effect declarations")
        for value in (machine, observation, effect):
            to_data(value)
            _name(value.id)
        _source_owners(machine, observation, effect)
        self.state_values(machine.states)
        _, destination_top, source_initial, destination_initial, *_ = shape
        initial_index = source_initial * (destination_top + 1) + destination_initial
        _require(machine.initial == machine.states[initial_index] and machine.terminal == () and machine.lifetime == "encounter",
                 "Transfer machine must reset to the original initial pair and have no terminal states")
        _require(machine.scope.kind == "encounter" and machine.arbitration == m.Arbitration("exclusive", "reject", "reject", "forbidden", "none"),
                 "Transfer machine requires encounter scope and exclusive rejection arbitration")
        _require(observation.value_type == m.TRUTH and observation.subject == effect.subject
                 and observation.observer == machine.executor == effect.executor and observation.freshness == self.sample_period,
                 "Transfer observation and effect must share executor, subject and one-period fresh truth samples")
        return shape

    def transitions(self, machine: m.Machine, observation: m.Observation, effect: m.Effect, *, prefix: str) -> tuple[m.Transition, ...]:
        """Author every nonzero transfer; zero-transfer cases use source stuttering."""
        source_top, destination_top, _, _, forward, reverse, threshold = self._source(machine, observation, effect)
        _name(prefix)
        result = []
        for source in range(source_top + 1):
            for destination in range(destination_top + 1):
                index = source * (destination_top + 1) + destination
                for positive, step in ((True, forward), (False, reverse)):
                    amount = min(step, source, destination_top - destination) if positive else min(step, destination, source_top - source)
                    if amount == 0:
                        continue
                    next_source = source - amount if positive else source + amount
                    next_destination = destination + amount if positive else destination - amount
                    next_index = next_source * (destination_top + 1) + next_destination
                    result.append(m.Transition(prefix + ("/forward" if positive else "/reverse") + str(index), ref(machine),
                        machine.states[index], machine.states[next_index], observation.updated,
                        observation.expression if positive else logic.not_(observation.expression), "defer",
                        (ref(effect),) if destination < threshold <= next_destination else ()))
        return tuple(result)

    def bind(self, *, instance: str, component: JsonValue, contract: str,
             machine: m.Machine, observation: m.Observation, effect: m.Effect) -> dict[str, JsonValue]:
        """Snapshot the complete original pair law and independently supplied pin."""
        self._source(machine, observation, effect)
        _name(instance)
        _name(contract)
        pin = decode_json(encode_json(component))
        _require(type(pin) is dict and set(pin) == {"schema_version", "kind", "id", "version", "content_fingerprint"},
                 "Selected component requires a complete exact model identity")
        identity = cast(dict[str, JsonValue], pin)
        _require(identity["schema_version"] == "biocompiler.component_identity.v0.1" and identity["kind"] == "model",
                 "Selected transfer component must use the model identity profile")
        for key in ("id", "version"):
            _name(cast(str, identity[key]))
        digest = identity["content_fingerprint"]
        _require(type(digest) is str and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest),
                 "Selected component fingerprint must be lowercase SHA-256")
        return {"mechanism": self.to_data(), "selection": {"instance": instance, "component": identity, "contract": contract},
                "source": {"machine": machine.id, "observation": observation.id, "effect": effect.id}}


@dataclass(frozen=True, slots=True)
class TransferEdge:
    """One ordered reservation instruction within an atomic transfer sample."""

    id: str
    source: str
    destination: str
    amount: m.Quantity
    when: bool

    def __post_init__(self) -> None:
        for value in (self.id, self.source, self.destination):
            _name(value)
        _require(self.source != self.destination, "A transfer edge requires distinct source and destination compartments")
        _require(_value(self.amount) > 0, "A transfer amount must be a positive exact quantity")
        _require(type(self.when) is bool, "Transfer activation must be an exact Boolean sample value")

    def to_data(self) -> dict[str, JsonValue]:
        self.__post_init__()
        return {"id": self.id, "source": self.source, "destination": self.destination,
                "amount": cast(JsonValue, to_data(self.amount)), "when": self.when}


@dataclass(frozen=True, slots=True)
class SampledTransferNetwork:
    """Bounded ordered transfers under one atomic state owner.

    Enabled edges reserve donor stock and recipient headroom from the same
    prestate in declared order. Incoming stock and freed outgoing room cannot
    fund another edge in that sample. All reserved deltas commit together.
    """

    substance: str
    unit: m.Unit
    quantum: m.Quantity
    reservoirs: tuple[ReservoirCompartment, ...]
    transfers: tuple[TransferEdge, ...]
    threshold_compartment: str
    threshold: m.Quantity
    sample_period: m.Quantity

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> tuple[tuple[int, ...], tuple[int, ...], tuple[tuple[int, int, int, bool], ...], int, int]:
        _require(type(self.reservoirs) is tuple and 2 <= len(self.reservoirs) <= 4
                 and all(type(row) is ReservoirCompartment for row in self.reservoirs),
                 "Use two to four exact, explicitly ordered reservoir compartments")
        names = tuple(row.compartment for row in self.reservoirs)
        _require(len(set(names)) == len(names), "Network reservoirs require distinct nominal compartment identities")
        grids = [SampledReservoir(self.substance, row.compartment, self.unit, self.quantum,
                    row.capacity, self.quantum, row.initial, self.sample_period)._validate() for row in self.reservoirs]
        tops = tuple(row[0] for row in grids)
        initials = tuple(row[2] for row in grids)
        states = 1
        for top in tops:
            states *= top + 1
        _require(states <= 16, "The complete Cartesian network grid must contain at most sixteen states")
        _require(type(self.transfers) is tuple and 1 <= len(self.transfers) <= 8
                 and all(type(row) is TransferEdge for row in self.transfers), "Use one to eight explicitly ordered exact transfer edges")
        _require(len({row.id for row in self.transfers}) == len(self.transfers), "Transfer identities must be unique")
        edges = []
        for row in self.transfers:
            row.__post_init__()
            _require(row.source in names and row.destination in names, "Every transfer endpoint must name a declared reservoir")
            source, destination = names.index(row.source), names.index(row.destination)
            amount = _value(row.amount) / _value(self.quantum)
            _require(row.amount.unit == self.unit and amount.denominator == 1 and amount.numerator <= tops[source],
                     "Each transfer amount must use the complete shared unit and fit its donor capacity on the exact grid")
            edges.append((source, destination, amount.numerator, row.when))
        _require(self.threshold_compartment in names, "Threshold must name one declared reservoir")
        threshold_index = names.index(self.threshold_compartment)
        threshold = _value(self.threshold) / _value(self.quantum)
        _require(self.threshold.unit == self.unit and threshold.denominator == 1 and 0 < threshold.numerator <= tops[threshold_index],
                 "Threshold must use the complete shared unit and be a positive grid amount within its reservoir")
        return tops, initials, tuple(edges), threshold_index, threshold.numerator

    def _vectors(self) -> tuple[tuple[int, ...], ...]:
        tops, *_ = self._validate()
        vectors: list[tuple[int, ...]] = [()]
        for top in tops:
            vectors = [prefix + (amount,) for prefix in vectors for amount in range(top + 1)]
        return tuple(vectors)

    @property
    def levels(self) -> tuple[tuple[m.Quantity, ...], ...]:
        """Complete Cartesian quantity vectors, first reservoir coordinate major."""
        return tuple(tuple(_scaled(self.quantum, amount) for amount in vector) for vector in self._vectors())

    def to_data(self) -> dict[str, JsonValue]:
        self._validate()
        return {"schema_version": "biocompiler.policy_sampled_transfer_network.v0.1",
            "profile": "biocompiler.policy_sampled_reserved_transfer_network.v0.1", "substance": self.substance,
            "unit": cast(JsonValue, to_data(self.unit)), "quantum": cast(JsonValue, to_data(self.quantum)),
            "reservoirs": [row.to_data() for row in self.reservoirs], "transfers": [row.to_data() for row in self.transfers],
            "threshold": {"compartment": self.threshold_compartment, "amount": cast(JsonValue, to_data(self.threshold))},
            "sample_period": cast(JsonValue, to_data(self.sample_period)),
            "arbitration": "declared_order_prestate_reservation", "ownership": "single_atomic_state_owner"}

    def state_values(self, states: tuple[str, ...]) -> list[JsonValue]:
        levels = self.levels
        _require(type(states) is tuple and len(states) == len(levels), "State labels must cover the complete ordered Cartesian quantity grid")
        for state in states:
            _name(state)
        _require(len(set(states)) == len(states), "Network state labels must be distinct")
        return [{"state": state, "amounts": [cast(JsonValue, to_data(amount)) for amount in vector]}
                for state, vector in zip(states, levels)]

    def _source(self, machine: m.Machine, observation: m.Observation, effect: m.Effect) -> None:
        _, initials, *_ = self._validate()
        _require(type(machine) is m.Machine and type(observation) is m.Observation and type(effect) is m.Effect,
                 "Use exact source machine, observation and effect declarations")
        for value in (machine, observation, effect):
            to_data(value)
            _name(value.id)
        _source_owners(machine, observation, effect)
        self.state_values(machine.states)
        _require(machine.initial == machine.states[self._vectors().index(initials)] and machine.terminal == () and machine.lifetime == "encounter",
                 "Transfer network machine must reset to its declared initial vector and have no terminal states")
        _require(machine.scope.kind == "encounter" and machine.arbitration == m.Arbitration("exclusive", "reject", "reject", "forbidden", "none"),
                 "Transfer network machine requires encounter scope and exclusive rejection arbitration")
        _require(observation.value_type == m.TRUTH and observation.subject == effect.subject
                 and observation.observer == machine.executor == effect.executor and observation.freshness == self.sample_period,
                 "Network observation and effect must share executor, subject and one-period fresh truth samples")

    def transitions(self, machine: m.Machine, observation: m.Observation, effect: m.Effect, *, prefix: str) -> tuple[m.Transition, ...]:
        """Author nonzero flow rows, retaining self-transitions for circulating flow."""
        self._source(machine, observation, effect)
        _name(prefix)
        tops, _, edges, threshold_index, threshold = self._validate()
        vectors = self._vectors()
        result = []
        for index, before in enumerate(vectors):
            for truth in (True, False):
                outgoing, incoming = [0] * len(tops), [0] * len(tops)
                flows = []
                for source, destination, maximum, enabled in edges:
                    amount = min(maximum, before[source] - outgoing[source], tops[destination] - before[destination] - incoming[destination]) if truth == enabled else 0
                    outgoing[source] += amount
                    incoming[destination] += amount
                    flows.append(amount)
                if not any(flows):
                    continue
                after = tuple(amount - outgoing[coordinate] + incoming[coordinate] for coordinate, amount in enumerate(before))
                result.append(m.Transition(prefix + ("/forward" if truth else "/reverse") + str(index), ref(machine),
                    machine.states[index], machine.states[vectors.index(after)], observation.updated,
                    observation.expression if truth else logic.not_(observation.expression), "defer",
                    (ref(effect),) if before[threshold_index] < threshold <= after[threshold_index] else ()))
        return tuple(result)

    def bind(self, *, instance: str, component: JsonValue, contract: str,
             machine: m.Machine, observation: m.Observation, effect: m.Effect) -> dict[str, JsonValue]:
        """Snapshot the complete original network and its selected atomic owner."""
        self._source(machine, observation, effect)
        _name(instance)
        _name(contract)
        pin = decode_json(encode_json(component))
        _require(type(pin) is dict and set(pin) == {"schema_version", "kind", "id", "version", "content_fingerprint"},
                 "Selected component requires a complete exact model identity")
        identity = cast(dict[str, JsonValue], pin)
        _require(identity["schema_version"] == "biocompiler.component_identity.v0.1" and identity["kind"] == "model",
                 "Selected network component must use the model identity profile")
        for key in ("id", "version"):
            _name(cast(str, identity[key]))
        digest = identity["content_fingerprint"]
        _require(type(digest) is str and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest),
                 "Selected component fingerprint must be lowercase SHA-256")
        return {"mechanism": self.to_data(), "selection": {"instance": instance, "component": identity, "contract": contract},
                "source": {"machine": machine.id, "observation": observation.id, "effect": effect.id}}


__all__ = ["QuantitativeAuthoringError", "SampledReservoir", "SampledStepReservoir", "ReservoirCompartment", "SampledTransferPair", "TransferEdge", "SampledTransferNetwork"]
