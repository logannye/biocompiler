"""Immutable component contracts and exact dependency identities for offline linking."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Any, ClassVar

from biocompiler.ir.intent import freeze_json
from biocompiler.ir.mechanism import MechanismNode
from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
    contract_type,
    decode_type,
    finite_number,
    canonical_synthetic_unit,
    synthetic_output_domain, domain_subset,
    STATELESS_TIMING, TEMPORAL_LEVEL_TIMING, TEMPORAL_EVENT_TIMING,
)
from biocompiler.semantics.types import LEVEL, TypeSpec


def _read(data, cls):
    fields(
        data,
        {item.name for item in dataclass_fields(cls)} | {"schema_version"},
        cls.__name__,
    )
    require(
        data["schema_version"] == cls.schema_version,
        f"Unsupported {cls.__name__} schema.",
    )
    return {key: value for key, value in data.items() if key != "schema_version"}


def _array(values, cls, label):
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    require(all(isinstance(item, cls) for item in values), f"Invalid {label} records.")
    result = tuple(values)
    if result and hasattr(result[0], "id"):
        require(
            len({item.id for item in result}) == len(result), f"Duplicate {label} IDs."
        )
        result = tuple(sorted(result, key=lambda item: item.id))
    return result


def _decode_array(values, cls, label):
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    return tuple(cls.from_dict(item) for item in values)


class _Record(JsonArtifact):
    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if isinstance(value, Mapping):
                return {key: encode(item) for key, item in value.items()}
            return value

        return {
            "schema_version": self.schema_version,
            **{
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            },
        }


SYNTHETIC_TRANSITION_POLICY = "biocompiler.synthetic_component_dynamics.v0.1"


@dataclass(frozen=True)
class SyntheticOperatorModel(_Record):
    """Closed executable software contract, never arbitrary code or a model URL.

    The policy fixes initial internal state, no prehistory, event ordering and
    contact lifecycle. Port initialization describes *settled* startup outputs.
    """

    operation: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    input_ports: tuple[str, ...] = ()
    output_port: str = "out"
    policy: str = SYNTHETIC_TRANSITION_POLICY
    schema_version: ClassVar[str] = "biocompiler.synthetic_operator_model.v0.1"

    def __post_init__(self):
        require(isinstance(self.operation, str) and self.operation in {
            "input", "constant", "and", "or", "not", "compare", "select",
            "any_contact", "output", "held_for", "onset", "pulse", "memory",
        }, "Unsupported synthetic component operation.")
        require(isinstance(self.attributes, Mapping), "Operator attributes must be an object.")
        expected = ({"value"} if self.operation == "constant" else
                    {"operator"} if self.operation == "compare" else
                    {"duration"} if self.operation in {"held_for", "pulse", "memory"} else set())
        require(set(self.attributes) == expected, "Unexpected executable operator attributes.")
        object.__setattr__(self, "attributes", freeze_json(dict(self.attributes)))
        object.__setattr__(self, "input_ports", names(self.input_ports, "Operator inputs"))
        name(self.output_port, "Operator output")
        require(self.output_port not in self.input_ports, "Operator ports must be distinct.")
        require(self.policy == SYNTHETIC_TRANSITION_POLICY,
                "Unsupported synthetic transition policy.")

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))

    def domain_checks(self, ports, supported_domain):
        by_id = {port.id: port for port in ports}
        output = by_id[self.output_port]
        contacts = supported_domain.constraints.get("concurrent_contacts")
        maximum = contacts.upper if contacts is not None and contacts.kind == "scalar_interval" else None
        result = []
        for attribute in ("domain", "initialization"):
            inferred = synthetic_output_domain(
                self.operation, self.attributes,
                [getattr(by_id[ref], attribute) for ref in self.input_ports],
                output.dtype, initialization=attribute == "initialization", max_contacts=maximum,
            )
            if inferred is not None:
                result.append(domain_subset(inferred, getattr(output, attribute)))
        return tuple(result)

    def validate_ports(self, ports, supported_domain):
        by_id = {port.id: port for port in ports}
        require(all(port.unit == canonical_synthetic_unit(port.dtype) for port in ports),
                "Executable synthetic ports require canonical units; unit conversion is unsupported.")
        require(set(by_id) == {*self.input_ports, self.output_port},
                "Executable operator must cover exactly its declared ports.")
        output = by_id[self.output_port]
        require(output.direction == "output" and all(
            by_id[ref].direction == "input" for ref in self.input_ports
        ), "Executable operator port directions disagree.")
        # Reuse strict literal/attribute typing, without inventing a graph or
        # taking any operation parameters from a source candidate.
        validated = MechanismNode(
            "operator", self.operation,
            Observable(output.meaning, output.dtype, output.role,
                       output.scope, output.compartment),
            self.input_ports, self.attributes,
        )
        require(validated.attributes == self.attributes,
                "Executable operator attributes must use canonical typed literals.")
        incoming = [by_id[ref] for ref in self.input_ports]
        count = {"input": 0, "constant": 0, "not": 1, "output": 1,
                 "held_for": 1, "onset": 1, "pulse": 1, "memory": 2,
                 "any_contact": 1, "compare": 2, "select": 3}.get(self.operation)
        require(len(incoming) >= 2 if count is None else len(incoming) == count,
                "Executable operator has the wrong input count.")
        for port in incoming:
            require(port.role == output.role and port.compartment == output.compartment,
                    "Executable operators cannot cross roles or compartments.")
            require(not (port.scope == "contact" and output.scope == "cell")
                    or self.operation == "any_contact",
                    "Contact-to-cell execution requires explicit aggregation.")
        if self.operation in {"and", "or", "not", "held_for", "onset", "pulse", "memory", "any_contact"}:
            require(output.dtype.kind == "condition" and all(
                port.dtype.kind == "condition" for port in incoming
            ), "Executable logical/temporal operators require Boolean ports.")
        if self.operation == "memory":
            require(output.scope == "cell", "Executable memory requires cell scope.")
        if self.operation == "any_contact":
            require(output.scope == "cell" and incoming[0].scope == "contact",
                    "Executable aggregation requires a contact input and cell output.")
        if self.operation == "compare":
            require(output.dtype.kind == "condition"
                    and all(port.dtype.kind == "scalar" for port in incoming)
                    and incoming[0].dtype.compatible(incoming[1].dtype),
                    "Executable comparison port types disagree.")
        if self.operation == "select":
            require(incoming[0].dtype.kind == "condition" and all(
                output.dtype.compatible(port.dtype) for port in incoming[1:]
            ), "Executable selection port types disagree.")
        if self.operation == "output":
            require(output.dtype.compatible(incoming[0].dtype),
                    "Executable output port types disagree.")
        event_output = self.operation == "onset" or (
            self.operation == "any_contact" and incoming[0].timing == TEMPORAL_EVENT_TIMING
        )
        temporal = output.timing != STATELESS_TIMING
        require(output.timing == (TEMPORAL_EVENT_TIMING if event_output else
                TEMPORAL_LEVEL_TIMING if temporal else STATELESS_TIMING),
                "Executable output event/level timing is inconsistent.")
        for index, port in enumerate(incoming):
            expects_event = (self.operation in {"pulse", "memory"} and index == 0) or (
                self.operation == "any_contact" and event_output
            )
            expected = TEMPORAL_EVENT_TIMING if expects_event else (
                TEMPORAL_LEVEL_TIMING if temporal else STATELESS_TIMING
            )
            require(port.timing == expected,
                    "Executable input event/level timing is inconsistent.")
        if self.operation in {"held_for", "onset", "pulse", "memory"}:
            require(temporal, "Stateful operators require the discrete-event timing profile.")
        require(all(check.status != "fail" for check in self.domain_checks(ports, supported_domain)),
                "Executable output runtime/initialization guarantees exclude possible operator values.")


@dataclass(frozen=True)
class PinnedIdentity(_Record):
    kind: str
    id: str
    version: str
    content_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.component_identity.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.kind, str)
            and self.kind in {"model", "reference", "registry", "source", "evidence"},
            "Unsupported pinned identity kind.",
        )
        name(self.id, "Identity ID")
        name(self.version, "Identity version")
        require(
            isinstance(self.content_fingerprint, str)
            and len(self.content_fingerprint) == 64
            and all(char in "0123456789abcdef" for char in self.content_fingerprint),
            "A pinned identity requires a SHA-256 content fingerprint.",
        )

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))


@dataclass(frozen=True)
class ParameterProvenance(_Record):
    id: str
    value: ValueDomain
    source: PinnedIdentity
    method: str
    schema_version: ClassVar[str] = "biocompiler.component_parameter.v0.1"

    def __post_init__(self):
        name(self.id, "Parameter ID")
        name(self.method, "Parameter provenance method")
        require(
            isinstance(self.value, ValueDomain),
            "A parameter requires a typed value domain.",
        )
        require(
            isinstance(self.source, PinnedIdentity),
            "Parameter provenance requires a pinned source.",
        )

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["value"] = ValueDomain.from_dict(values["value"])
        values["source"] = PinnedIdentity.from_dict(values["source"])
        return cls(**values)


@dataclass(frozen=True)
class DependencyRequirement(_Record):
    id: str
    capability: str
    role: str
    scope: str
    compartment: str
    required: bool = True
    schema_version: ClassVar[str] = "biocompiler.component_dependency.v0.1"

    def __post_init__(self):
        for key in ("id", "capability", "role", "compartment"):
            name(getattr(self, key), f"Dependency {key}")
        require(
            isinstance(self.scope, str) and self.scope in {"cell", "contact"},
            "Dependency scope must be cell or contact.",
        )
        require(type(self.required) is bool, "Dependency required must be Boolean.")

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))


@dataclass(frozen=True)
class ProvidedCapability(_Record):
    id: str
    role: str
    scope: str
    compartment: str
    schema_version: ClassVar[str] = "biocompiler.component_capability.v0.1"

    def __post_init__(self):
        for key in ("id", "role", "compartment"):
            name(getattr(self, key), f"Capability {key}")
        require(
            isinstance(self.scope, str) and self.scope in {"cell", "contact"},
            "Capability scope must be cell or contact.",
        )

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))


@dataclass(frozen=True)
class ResourceReservation(_Record):
    id: str
    resource: str
    amount: int | float | None
    unit: str
    dtype: TypeSpec = LEVEL
    reusable: bool = False
    role: str = "cell"
    scope: str = "cell"
    compartment: str = "abstract"
    schema_version: ClassVar[str] = "biocompiler.component_resource_reservation.v0.1"

    def __post_init__(self):
        for key in ("id", "resource", "unit", "role", "compartment"):
            name(getattr(self, key), f"Resource {key}")
        require(
            isinstance(self.scope, str) and self.scope in {"cell", "contact"},
            "Resource scope must be cell or contact.",
        )
        contract_type(self.dtype)
        require(
            self.dtype.kind == "scalar", "Resource quantities require scalar types."
        )
        if self.amount is not None:
            finite_number(self.amount, "Resource amount")
            require(self.amount >= 0, "Resource amount cannot be negative.")
        require(type(self.reusable) is bool, "Resource reuse must be explicit Boolean.")

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["dtype"] = decode_type(values["dtype"])
        return cls(**values)


@dataclass(frozen=True)
class SequenceReferenceMetadata(_Record):
    artifact_class: str
    sequence_length: int
    unknown_features: tuple[str, ...]
    completeness: str = "CDS-reference-only"
    schema_version: ClassVar[str] = "biocompiler.component_sequence_reference.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.artifact_class, str)
            and self.artifact_class in {"coding_dna", "coding_rna", "protein"},
            "Unsupported reference artifact class.",
        )
        require(
            type(self.sequence_length) is int and self.sequence_length > 0,
            "A reference sequence requires a positive integer length.",
        )
        require(
            self.completeness == "CDS-reference-only",
            "Only CDS reference scope is supported.",
        )
        object.__setattr__(
            self,
            "unknown_features",
            names(self.unknown_features, "Unknown reference features"),
        )

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))


@dataclass(frozen=True)
class ComponentRecord(_Record):
    id: str
    version: str
    classification: str
    implementation_role: str
    supported_targets: tuple[str, ...]
    ports: tuple[PortContract, ...]
    supported_domain: OperatingDomain
    identities: tuple[PinnedIdentity, ...]
    assumptions: tuple[str, ...] = ()
    guarantees: tuple[str, ...] = ()
    evidence: tuple[PinnedIdentity, ...] = ()
    parameters: tuple[ParameterProvenance, ...] = ()
    dependencies: tuple[DependencyRequirement, ...] = ()
    capabilities: tuple[ProvidedCapability, ...] = ()
    resources: tuple[ResourceReservation, ...] = ()
    reference_metadata: SequenceReferenceMetadata | None = None
    synthetic_model: SyntheticOperatorModel | None = None
    schema_version: ClassVar[str] = "biocompiler.component_record.v0.2"

    def __post_init__(self):
        for key in ("id", "version", "implementation_role"):
            name(getattr(self, key), f"Component {key}")
        require(
            isinstance(self.classification, str)
            and self.classification
            in {"synthetic_model", "sequence_reference", "modeled_component"},
            "Unsupported component classification.",
        )
        for key in ("supported_targets", "assumptions", "guarantees"):
            object.__setattr__(self, key, names(getattr(self, key), f"Component {key}"))
        require(
            bool(self.supported_targets),
            "A component must declare at least one supported target.",
        )
        require(
            isinstance(self.supported_domain, OperatingDomain),
            "A component requires an explicit operating domain.",
        )
        for key, cls in (
            ("ports", PortContract),
            ("identities", PinnedIdentity),
            ("evidence", PinnedIdentity),
            ("parameters", ParameterProvenance),
            ("dependencies", DependencyRequirement),
            ("capabilities", ProvidedCapability),
            ("resources", ResourceReservation),
        ):
            object.__setattr__(self, key, _array(getattr(self, key), cls, key))
        identity_kinds = {item.kind for item in self.identities}
        if self.synthetic_model is not None:
            require(isinstance(self.synthetic_model, SyntheticOperatorModel)
                    and self.classification == "synthetic_model",
                    "Executable synthetic models require synthetic_model classification.")
            require(self.implementation_role == self.synthetic_model.operation,
                    "Implementation role disagrees with executable operation.")
            self.synthetic_model.validate_ports(self.ports, self.supported_domain)
        if self.classification == "sequence_reference":
            require(
                "reference" in identity_kinds,
                "A sequence reference must pin its reference identity.",
            )
            require(
                isinstance(self.reference_metadata, SequenceReferenceMetadata),
                "A sequence reference must record its coding scope and unknown features.",
            )
            require(
                "model" not in identity_kinds
                and not self.ports
                and not self.capabilities
                and not self.resources
                and not self.dependencies,
                "A sequence-only reference cannot declare dynamic interfaces or implementation obligations.",
            )
        else:
            require(
                "model" in identity_kinds,
                "A modeled component must pin its model identity.",
            )
            require(
                self.reference_metadata is None,
                "Reference metadata belongs to sequence references only.",
            )

    def port(self, port_id: str) -> PortContract:
        for port in self.ports:
            if port.id == port_id:
                return port
        raise KeyError(port_id)

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["supported_domain"] = OperatingDomain.from_dict(
            values["supported_domain"]
        )
        if values["reference_metadata"] is not None:
            values["reference_metadata"] = SequenceReferenceMetadata.from_dict(
                values["reference_metadata"]
            )
        if values["synthetic_model"] is not None:
            values["synthetic_model"] = SyntheticOperatorModel.from_dict(values["synthetic_model"])
        for key, item_cls in (
            ("ports", PortContract),
            ("identities", PinnedIdentity),
            ("evidence", PinnedIdentity),
            ("parameters", ParameterProvenance),
            ("dependencies", DependencyRequirement),
            ("capabilities", ProvidedCapability),
            ("resources", ResourceReservation),
        ):
            values[key] = _decode_array(values[key], item_cls, key)
        return cls(**values)
