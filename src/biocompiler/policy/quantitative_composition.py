"""Typed partitioned reservoir authoring under a supplied atomic coordinator.

The returned records are original specifications, never checking capabilities.
Selected transfer signals express a supplied Boolean mechanism contract, not
physical transport or a claim about human-cell behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from . import logic, model as m
from .programs import ref
from .quantitative import SampledTransferNetwork, _name, _require


@dataclass(frozen=True, slots=True)
class ReservoirStateOwner:
    """Bind one nominal reservoir to an explicit encounter-local private store."""

    compartment: str
    state: m.StateStore


@dataclass(frozen=True, slots=True)
class CoupledTransferNetwork:
    """Binary reservoir components coordinated by one atomic source machine.

    Transfer expressions read immutable prestate and reserve stock and room in
    declared order. Every allocating transition atomically writes all stores.
    Unknown input leaves them unchanged because no transition is admitted.
    """

    network: SampledTransferNetwork
    owners: tuple[ReservoirStateOwner, ...]

    def __post_init__(self) -> None:
        _require(type(self.network) is SampledTransferNetwork, "Use an exact sampled network")
        tops, initials, *_ = self.network._validate()
        _require(all(top == 1 for top in tops), "Coupled reservoirs require exactly one quantum of capacity")
        _require(type(self.owners) is tuple and all(type(owner) is ReservoirStateOwner for owner in self.owners),
                 "Use ordered explicit reservoir state owners")
        _require(tuple(owner.compartment for owner in self.owners) == tuple(row.compartment for row in self.network.reservoirs),
                 "Private owners must partition the original reservoir coordinates in order")
        _require(all(type(owner.state) is m.StateStore for owner in self.owners), "Each private owner requires an explicit StateStore")
        _require(len({owner.state.id for owner in self.owners}) == len(self.owners), "Reservoir stores cannot alias")
        for owner, initial in zip(self.owners, initials):
            _name(owner.compartment)
            store = owner.state
            _require(type(store) is m.StateStore and store.value_type == m.TRUTH and type(store.initial) is bool
                     and store.initial == bool(initial) and store.capacity == 2 and store.overflow == "reject"
                     and store.scope.kind == "encounter" and store.lifetime == "encounter" and store.reset is None
                     and store.inheritance == "not_applicable" and store.duration is None
                     and store.contract is None and store.coordination is None,
                     "Use exact known binary encounter state with encounter reset only")

    def expressions(self, observation: m.Observation) -> tuple[tuple[m.Expr, ...], tuple[m.Expr, ...]]:
        """Explicit edge allocations and per-owner next-value expressions."""
        self.__post_init__()
        states = {owner.compartment: owner.state.expression for owner in self.owners}
        flows: list[m.Expr] = []
        for index, edge in enumerate(self.network.transfers):
            prior = [flows[previous] for previous, other in enumerate(self.network.transfers[:index])
                     if other.source == edge.source or other.destination == edge.destination]
            operands = [observation.expression if edge.when else logic.not_(observation.expression),
                        states[edge.source], logic.not_(states[edge.destination])]
            if prior:
                operands.append(logic.not_(logic.any_of(*prior)))
            flows.append(logic.all_of(*operands))
        next_values = []
        for owner in self.owners:
            outgoing = [flow for flow, edge in zip(flows, self.network.transfers) if edge.source == owner.compartment]
            incoming = [flow for flow, edge in zip(flows, self.network.transfers) if edge.destination == owner.compartment]
            held = logic.all_of(states[owner.compartment], logic.not_(logic.any_of(*outgoing))) if outgoing else states[owner.compartment]
            next_values.append(logic.any_of(held, *incoming) if incoming else held)
        return tuple(flows), tuple(next_values)

    def transitions(self, machine: m.Machine, observation: m.Observation, effect: m.Effect, *, prefix: str) -> tuple[m.Transition, ...]:
        self.network._source(machine, observation, effect)
        _require(all(owner.state.scope == machine.scope for owner in self.owners),
                 "All reservoir stores and their atomic writer must share the original encounter scope")
        _, next_values = self.expressions(observation)
        assignments = tuple(m.Assignment(ref(owner.state), value) for owner, value in zip(self.owners, next_values))
        return tuple(replace(transition, assignments=assignments)
                     for transition in self.network.transitions(machine, observation, effect, prefix=prefix))

    def bind(self, *, coordinator_instance: str, coordinator_component: JsonValue, coordinator_contract: str,
             owners: tuple[tuple[str, JsonValue, str], ...], machine: m.Machine,
             observation: m.Observation, effect: m.Effect) -> dict[str, JsonValue]:
        """Pin independently supplied component bodies, without granting admission."""
        self.transitions(machine, observation, effect, prefix="binding-validation")
        _require(type(owners) is tuple and len(owners) == len(self.owners), "Select every reservoir component exactly once")
        _require(len({coordinator_instance, *(row[0] for row in owners)}) == 1 + len(owners),
                 "Coordinator and reservoir components must be distinct selected instances")
        network = self.network.bind(instance=coordinator_instance, component=coordinator_component,
                                    contract=coordinator_contract, machine=machine, observation=observation, effect=effect)
        selected: list[JsonValue] = []
        for owner, (instance, component, contract) in zip(self.owners, owners):
            # Reuse only strict nominal pin validation, not native checking.
            checked = self.network.bind(instance=instance, component=component, contract=contract,
                                        machine=machine, observation=observation, effect=effect)
            pin = cast(dict[str, JsonValue], checked["selection"])["component"]
            selected.append({"instance": instance, "component": decode_json(encode_json(pin)),
                             "contract": contract, "compartment": owner.compartment, "state": owner.state.id})
        return {"network": network, "owners": selected, "synchronization": "one_prestate_one_atomic_commit"}


__all__ = ["ReservoirStateOwner", "CoupledTransferNetwork"]
