"""Supplied many-to-many behavior, component and RNA architecture contracts.

A refinement pins an existing executable BehaviorProgram and exact construction
fragments. Its material correspondence is a declared conditional contract, not
biological evidence. Structural validation does not establish refinement,
placement feasibility, helper availability or satisfaction of source controls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import ClassVar

from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.architecture_deployment import RNAAvailabilityContract, RNADeploymentRequirement
from biocompiler.ir.circuit_intent import CircuitLifecycle
from biocompiler.ir.circuit_observations import CircuitProduct
from biocompiler.ir.component_contracts import ComponentRecord
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.molecule_records import (
    _MoleculeRecord, _choice, _decode_records, _records, _text,
)
from biocompiler.ir.payload_contracts import PayloadTemplate, _assumptions
from biocompiler.ir.serialization import require

MAX_ARCHITECTURE_RECORDS = 256
MAX_ARCHITECTURE_NODES = 4096
MAX_ARCHITECTURE_MATCH_STATES = 1_000_000
CONTROL_KINDS = frozenset({
    "activation", "production_adjustment", "activity_control", "memory_reset",
    "shutdown", "physical_separation", "dependency_disjointness",
})


def _names(values, label, *, nonempty=False, maximum=MAX_ARCHITECTURE_NODES):
    require(isinstance(values, (tuple, list)) and int(nonempty) <= len(values) <= maximum,
            f"Invalid {label} inventory.")
    for value in values:
        _text(value, label)
    require(len(set(values)) == len(values), f"Duplicate {label} identities.")
    return tuple(sorted(values))


def _mapping(value, label):
    require(isinstance(value, Mapping) and len(value) <= MAX_ARCHITECTURE_NODES,
            f"Invalid {label}.")
    for key, item in value.items():
        _text(key, label)
        _text(item, label)
    return freeze_json(dict(sorted(value.items())))


def _limit(value, label, maximum, *, optional=True, minimum=0):
    require((optional and value is None) or
            (type(value) is int and minimum <= value <= maximum), f"Invalid {label}.")


def _seconds(value, label, *, optional=False):
    require((optional and value is None) or
            (type(value) in (int, float) and math.isfinite(value)
             and 0 <= value <= 31_536_000), f"Invalid {label}.")


def _assume(values):
    result = _assumptions(values)
    require(bool(result), "Architecture correspondence requires explicit assumptions.")
    return result


@dataclass(frozen=True)
class ArchitectureBinding(_MoleculeRecord):
    """Many-to-many material ownership, separate from model equivalence."""

    id: str
    behavior_node_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    template_ids: tuple[str, ...]
    placement_ids: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.architecture_binding.v0.1"

    def __post_init__(self):
        _text(self.id, "Architecture binding")
        for key in ("behavior_node_ids", "component_ids", "template_ids", "placement_ids"):
            object.__setattr__(self, key, _names(getattr(self, key), key, nonempty=True))
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureConnection(_MoleculeRecord):
    """Explicit constituent wiring; compatibility is checked against port authority."""

    id: str
    producer_component_id: str
    producer_port_id: str
    consumer_component_id: str
    consumer_port_id: str
    schema_version: ClassVar[str] = "biocompiler.architecture_connection.v0.1"

    def __post_init__(self):
        for key in ("id", "producer_component_id", "producer_port_id",
                    "consumer_component_id", "consumer_port_id"):
            _text(getattr(self, key), key)
        self._check_resources()


@dataclass(frozen=True)
class ArchitecturePlacement(_MoleculeRecord):
    id: str
    template_id: str
    member_id: str
    recipient_role: str
    compartment: str
    delivery_group: str
    schema_version: ClassVar[str] = "biocompiler.architecture_placement.v0.1"

    def __post_init__(self):
        for key in ("id", "template_id", "member_id", "recipient_role", "compartment", "delivery_group"):
            _text(getattr(self, key), key)
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureControl(_MoleculeRecord):
    """Declared physical control domains; output proximity does not imply sharing."""

    id: str
    kind: str
    behavior_node_ids: tuple[str, ...]
    controlling_node_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    domain_id: str
    assumptions: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.architecture_control.v0.1"

    def __post_init__(self):
        _text(self.id, "Control identity")
        _text(self.domain_id, "Physical control domain")
        _choice(self.kind, CONTROL_KINDS, "control kind")
        for key in ("behavior_node_ids", "component_ids"):
            object.__setattr__(self, key, _names(getattr(self, key), key, nonempty=True))
        object.__setattr__(self, "controlling_node_ids", _names(
            self.controlling_node_ids, "controlling nodes"))
        object.__setattr__(self, "assumptions", _assume(self.assumptions))
        self._check_resources()


@dataclass(frozen=True)
class ControlRequirement(_MoleculeRecord):
    """Source output/action identities and the required relation between controls."""

    id: str
    kind: str
    behavior_node_ids: tuple[str, ...]
    relation: str
    forbidden_shared_dependencies: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.architecture_control_requirement.v0.1"

    def __post_init__(self):
        _text(self.id, "Control requirement")
        _choice(self.kind, CONTROL_KINDS, "control kind")
        _choice(self.relation, {"shared", "independent"}, "control relation")
        object.__setattr__(self, "behavior_node_ids", _names(
            self.behavior_node_ids, "source control nodes", nonempty=True))
        object.__setattr__(self, "forbidden_shared_dependencies", _names(
            self.forbidden_shared_dependencies, "forbidden shared dependencies"))
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureHelper(_MoleculeRecord):
    """Nominal capacity counts declared consumers, never inferred biochemical rates.

    ``same_rna`` and ``other_rna`` require a material placement. Host/external
    availability is a supplied assumption, not an emitted genetic member.
    Initialization and dependency cycles are eligibility checks, so a library can
    retain a structurally well-formed but infeasible alternative for explanation.
    """

    id: str
    capability: str
    consumer_component_ids: tuple[str, ...]
    recipient_role: str
    compartment: str
    availability: str
    initialization: str
    sharing: str
    capacity: int
    assumptions: tuple[str, ...]
    placement_id: str | None = None
    provider_component_id: str | None = None
    depends_on: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.architecture_helper.v0.1"

    def __post_init__(self):
        for key in ("id", "capability", "recipient_role", "compartment"):
            _text(getattr(self, key), key)
        _choice(self.availability, {"same_rna", "other_rna", "host", "external"}, "helper availability")
        _choice(self.initialization, {"available_at_start", "after_expression", "after_trigger"},
                "helper initialization")
        _choice(self.sharing, {"exclusive", "shared"}, "helper sharing")
        _limit(self.capacity, "helper consumer capacity", MAX_ARCHITECTURE_NODES, optional=False, minimum=1)
        object.__setattr__(self, "consumer_component_ids", _names(
            self.consumer_component_ids, "helper consumers", nonempty=True))
        object.__setattr__(self, "depends_on", _names(self.depends_on, "helper prerequisites"))
        for key in ("placement_id", "provider_component_id"):
            if getattr(self, key) is not None:
                _text(getattr(self, key), key)
        require((self.placement_id is not None) == (self.availability in {"same_rna", "other_rna"}),
                "Encoded helpers need material placement; host/external helpers cannot claim an emitted member.")
        object.__setattr__(self, "assumptions", _assume(self.assumptions))
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureChannel(_MoleculeRecord):
    """Declared directed transport between original source roles.

    Units and value types are inherited from the bound source channel. The
    explicit finite transport policy is checked independently against that type.
    """

    id: str
    source_channel_id: str
    sender_role: str
    receiver_role: str
    sender_node_id: str
    receiver_node_id: str
    latency_seconds: float
    persistence_seconds: float | None
    failure_mode: str
    aggregation: str
    initial_value: object
    assumptions: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.architecture_channel.v0.1"

    def __post_init__(self):
        for key in ("id", "source_channel_id", "sender_role", "receiver_role",
                    "sender_node_id", "receiver_node_id"):
            _text(getattr(self, key), key)
        require(self.sender_role != self.receiver_role, "A transport channel must cross recipient roles.")
        _seconds(self.latency_seconds, "channel latency")
        _seconds(self.persistence_seconds, "channel persistence", optional=True)
        _choice(self.failure_mode, {"retain_last", "clear", "unknown"}, "channel failure mode")
        _choice(self.aggregation, {"single_sender", "sum", "max"}, "channel aggregation")
        object.__setattr__(self, "initial_value", freeze_json(self.initial_value))
        object.__setattr__(self, "assumptions", _assume(self.assumptions))
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureOutputBinding(_MoleculeRecord):
    """Pin supplementary circuit output authority to local model actions."""

    id: str
    requirement_id: str
    action_ids: tuple[str, ...]
    product: CircuitProduct
    lifecycle: CircuitLifecycle
    schema_version: ClassVar[str] = "biocompiler.architecture_output_binding.v0.1"
    _decoders: ClassVar[dict] = {"product": CircuitProduct.from_dict,
                               "lifecycle": CircuitLifecycle.from_dict}

    def __post_init__(self):
        for key in ("id", "requirement_id"):
            _text(getattr(self, key), key)
        object.__setattr__(self, "action_ids", _names(self.action_ids, "output action identities", nonempty=True))
        require(isinstance(self.product, CircuitProduct) and isinstance(self.lifecycle, CircuitLifecycle),
                "Architecture outputs require exact typed circuit product and lifecycle authority.")
        object.__setattr__(self, "product", CircuitProduct.from_dict(self.product.to_dict()))
        object.__setattr__(self, "lifecycle", CircuitLifecycle.from_dict(self.lifecycle.to_dict()))
        self._check_resources()


@dataclass(frozen=True)
class RecipientDeliveryGroup(_MoleculeRecord):
    id: str
    recipient_roles: tuple[str, ...]
    mode: str
    same_recipient: bool
    assumptions: tuple[str, ...]
    exact_count: int | None = None
    max_count: int | None = None
    max_total_bases: int | None = None
    schema_version: ClassVar[str] = "biocompiler.recipient_delivery_group.v0.1"

    def __post_init__(self):
        _text(self.id, "Delivery group")
        object.__setattr__(self, "recipient_roles", _names(
            self.recipient_roles, "delivery recipients", nonempty=True))
        _choice(self.mode, {"co_delivered", "independent"}, "delivery group mode")
        require(type(self.same_recipient) is bool, "Same-recipient assumption must be explicit Boolean.")
        for key in ("exact_count", "max_count"):
            _limit(getattr(self, key), key, MAX_ARCHITECTURE_NODES)
        _limit(self.max_total_bases, "delivery nucleotide bound", 1_000_000)
        require(self.exact_count is None or self.max_count is None or self.exact_count <= self.max_count,
                "Delivery exact RNA count exceeds maximum count.")
        object.__setattr__(self, "assumptions", _assume(self.assumptions))
        self._check_resources()


@dataclass(frozen=True)
class RNAArchitectureConstraints(_MoleculeRecord):
    exact_count: int | None = None
    max_count: int | None = None
    max_member_bases: int | None = None
    max_total_bases: int | None = None
    delivery_groups: tuple[RecipientDeliveryGroup, ...] = ()
    control_requirements: tuple[ControlRequirement, ...] = ()
    preferred_refinement_ids: tuple[str, ...] = ()
    max_combinations: int = 256
    require_complete: bool = False
    max_match_states: int = 100_000
    max_match_instances: int = MAX_ARCHITECTURE_RECORDS
    deployment_requirements: tuple[RNADeploymentRequirement, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.rna_architecture_constraints.v0.2"
    _decoders: ClassVar[dict] = {
        "delivery_groups": _decode_records(RecipientDeliveryGroup, MAX_ARCHITECTURE_RECORDS),
        "control_requirements": _decode_records(ControlRequirement, MAX_ARCHITECTURE_RECORDS),
        "deployment_requirements": _decode_records(RNADeploymentRequirement, MAX_ARCHITECTURE_RECORDS),
    }

    def __post_init__(self):
        for key in ("exact_count", "max_count"):
            _limit(getattr(self, key), key, MAX_ARCHITECTURE_NODES)
        for key in ("max_member_bases", "max_total_bases"):
            _limit(getattr(self, key), key, 1_000_000)
        require(self.exact_count is None or self.max_count is None or self.exact_count <= self.max_count,
                "Exact RNA count exceeds maximum count.")
        _limit(self.max_combinations, "architecture search bound", 4096, optional=False, minimum=1)
        _limit(self.max_match_states, "architecture matching work bound", MAX_ARCHITECTURE_MATCH_STATES,
               optional=False, minimum=1)
        _limit(self.max_match_instances, "architecture matching instance bound", MAX_ARCHITECTURE_RECORDS,
               optional=False, minimum=1)
        for key, cls in (("delivery_groups", RecipientDeliveryGroup), ("control_requirements", ControlRequirement),
                         ("deployment_requirements", RNADeploymentRequirement)):
            object.__setattr__(self, key, _records(getattr(self, key), cls, MAX_ARCHITECTURE_RECORDS, key))
        object.__setattr__(self, "preferred_refinement_ids", _names(
            self.preferred_refinement_ids, "preferred refinements", maximum=MAX_ARCHITECTURE_RECORDS))
        require(type(self.require_complete) is bool, "Completeness constraint must be Boolean.")
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureMatchPolicy(_MoleculeRecord):
    """Identity-independent exact graph embedding, without semantic rewrites.

    Attributes, ordered inputs, types, role edges and execution policies remain
    authoritative. Source correspondence in the enclosing refinement supplies
    optional anchors; no nominal biological symbol is treated as a wildcard.
    """

    mode: str = "exact_semantic_subgraph"
    schema_version: ClassVar[str] = "biocompiler.architecture_match_policy.v0.1"

    def __post_init__(self):
        require(self.mode == "exact_semantic_subgraph", "Unsupported architecture matching policy.")
        self._check_resources()


@dataclass(frozen=True)
class ArchitectureRefinementInstance(_MoleculeRecord):
    """Complete selected correspondence to independently supplied authority."""

    id: str
    refinement_id: str
    source_bindings: Mapping[str, str]
    schema_version: ClassVar[str] = "biocompiler.architecture_refinement_instance.v0.1"

    def __post_init__(self):
        _text(self.id, "Architecture instance identity")
        _text(self.refinement_id, "Supplied refinement identity")
        object.__setattr__(self, "source_bindings", _mapping(self.source_bindings, "instance source correspondence"))
        require(bool(self.source_bindings), "Architecture instances need complete source correspondence.")
        require(len(set(self.source_bindings.values())) == len(self.source_bindings),
                "Instance source correspondence must be injective.")
        self._check_resources()


@dataclass(frozen=True)
class PayloadArchitectureRefinement(_MoleculeRecord):
    """One independently supplied composite behavior-to-material contract.

    Explicit refinements give every model node an injective source correspondence.
    A matching policy instead makes that map a set of optional anchors; emitted
    instances always retain the complete correspondence. ``owned_node_ids``
    distinguishes installed effects/state from the referenced boundary scaffold;
    overlap eligibility is checked during composition, never waived by a label.
    All behavior identities in placements, helpers, controls and channels are
    local model IDs, including role and channel identities. The source binding
    remaps them; source-side control/delivery constraints already use source IDs.
    Template sharing exists within this one declared composite only. Selecting
    the same fragment in distinct instances emits distinct namespaced members.
    """

    id: str
    version: str
    behavior: BehaviorProgram
    source_bindings: Mapping[str, str]
    owned_node_ids: tuple[str, ...]
    components: tuple[ComponentRecord, ...]
    templates: tuple[PayloadTemplate, ...]
    bindings: tuple[ArchitectureBinding, ...]
    placements: tuple[ArchitecturePlacement, ...]
    assumptions: tuple[str, ...]
    connections: tuple[ArchitectureConnection, ...] = ()
    controls: tuple[ArchitectureControl, ...] = ()
    helpers: tuple[ArchitectureHelper, ...] = ()
    channels: tuple[ArchitectureChannel, ...] = ()
    output_contracts: tuple[ArchitectureOutputBinding, ...] = ()
    match_policy: ArchitectureMatchPolicy | None = None
    availability: tuple[RNAAvailabilityContract, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_refinement.v0.2"
    _decoders: ClassVar[dict] = {
        "behavior": BehaviorProgram.from_dict,
        "match_policy": lambda data: None if data is None else ArchitectureMatchPolicy.from_dict(data),
        "availability": _decode_records(RNAAvailabilityContract, MAX_ARCHITECTURE_RECORDS),
        "components": _decode_records(ComponentRecord, MAX_ARCHITECTURE_RECORDS),
        "templates": _decode_records(PayloadTemplate, MAX_ARCHITECTURE_RECORDS),
        "bindings": _decode_records(ArchitectureBinding, MAX_ARCHITECTURE_RECORDS),
        "placements": _decode_records(ArchitecturePlacement, MAX_ARCHITECTURE_RECORDS),
        "connections": _decode_records(ArchitectureConnection, MAX_ARCHITECTURE_RECORDS),
        "controls": _decode_records(ArchitectureControl, MAX_ARCHITECTURE_RECORDS),
        "helpers": _decode_records(ArchitectureHelper, MAX_ARCHITECTURE_RECORDS),
        "channels": _decode_records(ArchitectureChannel, MAX_ARCHITECTURE_RECORDS),
        "output_contracts": _decode_records(ArchitectureOutputBinding, MAX_ARCHITECTURE_RECORDS),
    }

    def __post_init__(self):
        for key in ("id", "version"):
            _text(getattr(self, key), key)
        require(isinstance(self.behavior, BehaviorProgram), "Refinements require the existing typed behavior IR.")
        require(0 < len(self.behavior.nodes) <= MAX_ARCHITECTURE_NODES, "Invalid refinement graph size.")
        object.__setattr__(self, "behavior", BehaviorProgram.from_dict(self.behavior.to_dict()))
        object.__setattr__(self, "source_bindings", _mapping(self.source_bindings, "source correspondence"))
        nodes = {node.id: node for node in self.behavior.nodes}
        require(self.match_policy is None or isinstance(self.match_policy, ArchitectureMatchPolicy),
                "Invalid architecture matching policy.")
        if self.match_policy is None:
            require(set(self.source_bindings) == nodes.keys(), "Every model node needs exact source correspondence.")
        else:
            _text(self.id, "Automatically matched refinement identity", maximum=4000)
            require(set(self.source_bindings) <= nodes.keys(), "Source anchor refers to an absent model node.")
        require(len(set(self.source_bindings.values())) == len(self.source_bindings),
                "Source correspondence must be injective within a refinement.")
        object.__setattr__(self, "owned_node_ids", _names(
            self.owned_node_ids, "owned behavior nodes", nonempty=True))
        require(set(self.owned_node_ids) <= nodes.keys(), "Owned node is absent from the supplied model.")
        for key, cls, nonempty in (
            ("components", ComponentRecord, True), ("templates", PayloadTemplate, True),
            ("bindings", ArchitectureBinding, True), ("placements", ArchitecturePlacement, True),
            ("connections", ArchitectureConnection, False),
            ("controls", ArchitectureControl, False), ("helpers", ArchitectureHelper, False),
            ("channels", ArchitectureChannel, False), ("output_contracts", ArchitectureOutputBinding, False),
            ("availability", RNAAvailabilityContract, False),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls,
                               MAX_ARCHITECTURE_RECORDS, key, nonempty=nonempty))
        components = {record.id for record in self.components}
        placement_ids = {placement.id for placement in self.placements}
        require(all(contract.placement_id in placement_ids for contract in self.availability),
                "Availability contract references an absent placement.")
        require(len({contract.placement_id for contract in self.availability}) == len(self.availability),
                "Every placement can have only one supplied availability contract.")
        ports = {record.id: {port.id: port for port in record.ports} for record in self.components}
        destinations = set()
        for connection in self.connections:
            require(connection.producer_component_id in ports and connection.consumer_component_id in ports,
                    "Connection references absent components.")
            producer = ports[connection.producer_component_id].get(connection.producer_port_id)
            consumer = ports[connection.consumer_component_id].get(connection.consumer_port_id)
            require(producer is not None and consumer is not None,
                    "Connection references absent ports.")
            require(producer.direction == "output" and consumer.direction == "input",
                    "Connection must join a producer output to a consumer input.")
            destination = (connection.consumer_component_id, connection.consumer_port_id)
            require(destination not in destinations, "A constituent input cannot have multiple drivers.")
            destinations.add(destination)
        templates = {record.id: record for record in self.templates}
        owned, bound_components, bound_templates = set(), set(), set()
        for binding in self.bindings:
            require(set(binding.behavior_node_ids) <= nodes.keys(), "Material binding references absent model nodes.")
            require(set(binding.component_ids) <= components, "Material binding references absent components.")
            require(set(binding.template_ids) <= templates.keys(), "Material binding references absent templates.")
            owned.update(binding.behavior_node_ids)
            bound_components.update(binding.component_ids)
            bound_templates.update(binding.template_ids)
        require(set(self.owned_node_ids) <= owned, "Every owned behavior node needs material correspondence.")
        require(bound_components == components and bound_templates == templates.keys(),
                "Every supplied component and template needs explicit material correspondence.")
        members = {(template.id, member.id) for template in self.templates
                   for member in (*template.output_members, *template.complex_members)}
        placed = set()
        placement_keys = set()
        for placement in self.placements:
            key = (placement.template_id, placement.member_id)
            require(key in members, "Placement references an absent member.")
            require(placement.recipient_role in nodes and nodes[placement.recipient_role].kind == "role",
                    "Placement recipient must name a local model role.")
            require((*key, placement.recipient_role) not in placement_keys,
                    "Duplicate member placement in the same recipient role.")
            placement_keys.add((*key, placement.recipient_role))
            placed.add(key)
        require(placed == members, "Every emitted member needs an explicit recipient placement.")
        placements = {record.id: record for record in self.placements}
        for binding in self.bindings:
            require(all(identity in placements and placements[identity].template_id in binding.template_ids
                        for identity in binding.placement_ids),
                    "Binding placements must exist within its supplied templates.")
        helper_ids = {record.id for record in self.helpers}
        for control in self.controls:
            require(set((*control.behavior_node_ids, *control.controlling_node_ids)) <= nodes.keys()
                    and set(control.component_ids) <= components, "Control references absent model or component authority.")
        for helper in self.helpers:
            require(helper.recipient_role in nodes and nodes[helper.recipient_role].kind == "role",
                    "Helper recipient must name a local model role.")
            require(set(helper.consumer_component_ids) <= components
                    and (helper.provider_component_id is None or helper.provider_component_id in components),
                    "Helper references absent components.")
            require(helper.placement_id is None or helper.placement_id in placements,
                    "Helper references an absent material placement.")
            require(set(helper.depends_on) <= helper_ids, "Helper prerequisite is absent from the refinement.")
        for channel in self.channels:
            require(all(identity in nodes and nodes[identity].kind == "role"
                        for identity in (channel.sender_role, channel.receiver_role)),
                    "Channel recipients must name local model roles.")
            require(channel.source_channel_id in nodes and nodes[channel.source_channel_id].kind == "channel",
                    "Channel source must name a local model channel.")
            require(channel.sender_node_id in nodes and channel.receiver_node_id in nodes,
                    "Channel boundary references absent model nodes.")
        for output in self.output_contracts:
            require(set(output.action_ids) <= nodes.keys(), "Output binding references absent model nodes.")
            require(all(nodes[identity].kind.startswith("action.") for identity in output.action_ids),
                    "Output binding requires action nodes.")
        require(len({output.requirement_id for output in self.output_contracts}) == len(self.output_contracts),
                "Supplementary output requirements can be bound only once per refinement.")
        object.__setattr__(self, "assumptions", _assume(self.assumptions))
        self._check_resources()


@dataclass(frozen=True)
class PayloadArchitectureLibrary(_MoleculeRecord):
    id: str
    refinements: tuple[PayloadArchitectureRefinement, ...]
    assumptions: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_library.v0.1"
    _decoders: ClassVar[dict] = {
        "refinements": _decode_records(PayloadArchitectureRefinement, MAX_ARCHITECTURE_RECORDS),
    }

    def __post_init__(self):
        _text(self.id, "Architecture library identity")
        object.__setattr__(self, "refinements", _records(self.refinements,
            PayloadArchitectureRefinement, MAX_ARCHITECTURE_RECORDS, "refinements"))
        object.__setattr__(self, "assumptions", _assumptions(self.assumptions))
        component_meanings = {}
        for refinement in self.refinements:
            for component in refinement.components:
                key = (component.id, component.version)
                require(key not in component_meanings or component_meanings[key] == component.fingerprint,
                        "One component identity/version cannot carry contradictory architecture authority.")
                component_meanings[key] = component.fingerprint
        self._check_resources()
