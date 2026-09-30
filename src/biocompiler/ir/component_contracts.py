"""Immutable component contracts and exact dependency identities for offline linking."""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import ClassVar

from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
    contract_type,
    decode_type,
    finite_number,
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
            return value

        return {
            "schema_version": self.schema_version,
            **{
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            },
        }


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
    schema_version: ClassVar[str] = "biocompiler.component_record.v0.1"

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
