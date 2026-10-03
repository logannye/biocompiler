"""Frozen inputs for offline component linking; declarations are not evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields
import math
from typing import ClassVar

from biocompiler.ir.component_contracts import ProvidedCapability
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.intent import SourceLocation
from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.registry.components import RegistryLock
from biocompiler.semantics.component_contracts import OperatingDomain, decode_type
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.types import LEVEL, TypeSpec


def _array(value, item_type, label):
    require(isinstance(value, (tuple, list)), f"{label} must be an array.")
    require(all(isinstance(item, item_type) for item in value), f"Invalid {label}.")
    return tuple(value)


def _quantity(value, label, *, optional=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    require(
        (optional and value is None) or valid,
        f"{label} must be a finite nonnegative quantity or an allowed unknown.",
    )


class _Record(JsonArtifact):
    """Small strict nested records, identified by their containing artifact."""

    def to_dict(self):
        result = {}
        for field in dataclass_fields(self):
            value = getattr(self, field.name)
            if hasattr(value, "to_dict"):
                value = value.to_dict()
            elif isinstance(value, tuple):
                value = [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in value
                ]
            result[field.name] = value
        return result

    @classmethod
    def _fields(cls, data):
        fields(data, {item.name for item in dataclass_fields(cls)}, cls.__name__)


@dataclass(frozen=True)
class LifecycleInterval(_Record):
    """Half-open [start,end) lifetime; null end means no known release time."""

    start: float | int = 0
    end: float | int | None = None
    unit: str = "s"

    def __post_init__(self):
        _quantity(self.start, "Lifecycle start")
        _quantity(self.end, "Lifecycle end", optional=True)
        require(
            self.end is None or self.end > self.start,
            "A lifecycle must have positive duration.",
        )
        name(self.unit, "Lifecycle unit")

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class CompositionInstance(_Record):
    id: str
    component: ComponentLock
    required_domain: OperatingDomain
    placement: str = "encoded_here"
    lifetime: LifecycleInterval = LifecycleInterval()
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None

    def __post_init__(self):
        name(self.id, "Instance id")
        require(
            isinstance(self.component, ComponentLock)
            and self.component.node_id == self.id,
            "An instance must carry its own exact component lock.",
        )
        require(
            isinstance(self.required_domain, OperatingDomain),
            "Invalid required domain.",
        )
        require(
            isinstance(self.placement, str)
            and self.placement in {"encoded_here", "co_payload"},
            "Invalid instance placement.",
        )
        require(
            isinstance(self.lifetime, LifecycleInterval), "Invalid instance lifetime."
        )
        object.__setattr__(
            self, "requirement_ids", names(self.requirement_ids, "Requirement ids")
        )
        require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid instance source.",
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(
            data["id"],
            ComponentLock.from_dict(data["component"]),
            OperatingDomain.from_dict(data["required_domain"]),
            data["placement"],
            LifecycleInterval.from_dict(data["lifetime"]),
            data["requirement_ids"],
            SourceLocation.from_dict(data["source"])
            if data["source"] is not None
            else None,
        )


@dataclass(frozen=True)
class Connection(_Record):
    producer_instance: str
    producer_port: str
    consumer_instance: str
    consumer_port: str

    def __post_init__(self):
        for item in dataclass_fields(self):
            name(getattr(self, item.name), item.name)

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class Provider(_Record):
    """An explicit target/supply assumption, with optional provider prerequisites.

    Payload providers are derived from selected records and cannot be asserted
    through this class. External declarations are conditional inputs, never an
    empirical claim that the named supply has been observed.
    """

    id: str
    kind: str
    capabilities: tuple[ProvidedCapability, ...]
    supported_targets: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        name(self.id, "Provider id")
        require(
            isinstance(self.kind, str)
            and self.kind in {"host", "external", "unresolved"},
            "Invalid explicit provider kind.",
        )
        object.__setattr__(
            self,
            "capabilities",
            _array(self.capabilities, ProvidedCapability, "Provider capabilities"),
        )
        require(
            len({item.id for item in self.capabilities}) == len(self.capabilities),
            "Duplicate provider capabilities.",
        )
        for key in ("supported_targets", "depends_on", "evidence_refs"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            bool(self.supported_targets), "A provider must declare supported targets."
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        require(
            isinstance(data["capabilities"], (list, tuple)),
            "Provider capabilities must be an array.",
        )
        return cls(
            data["id"],
            data["kind"],
            tuple(ProvidedCapability.from_dict(item) for item in data["capabilities"]),
            data["supported_targets"],
            data["depends_on"],
            data["evidence_refs"],
        )


@dataclass(frozen=True)
class DependencyBinding(_Record):
    instance_id: str
    requirement_id: str
    provider_id: str

    def __post_init__(self):
        for item in dataclass_fields(self):
            name(getattr(self, item.name), item.name)

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class ResourcePool(_Record):
    """One physical provider/resource pool; capacity None is explicitly unknown."""

    id: str
    resource: str
    unit: str
    capacity: float | int | None
    provider_id: str
    dtype: TypeSpec = LEVEL

    def __post_init__(self):
        for key in ("id", "resource", "unit", "provider_id"):
            name(getattr(self, key), key)
        _quantity(self.capacity, "Resource capacity", optional=True)
        require(
            isinstance(self.dtype, TypeSpec) and self.dtype.kind == "scalar",
            "Resource pools require a scalar type.",
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(
            data["id"],
            data["resource"],
            data["unit"],
            data["capacity"],
            data["provider_id"],
            decode_type(data["dtype"]),
        )


@dataclass(frozen=True)
class ResourceBinding(_Record):
    instance_id: str
    reservation_id: str
    pool_id: str

    def __post_init__(self):
        for item in dataclass_fields(self):
            name(getattr(self, item.name), item.name)

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class CompositionRequest(JsonArtifact):
    target: TargetContext
    registry_lock: RegistryLock
    instances: tuple[CompositionInstance, ...]
    connections: tuple[Connection, ...] = ()
    providers: tuple[Provider, ...] = ()
    dependency_bindings: tuple[DependencyBinding, ...] = ()
    resource_pools: tuple[ResourcePool, ...] = ()
    resource_bindings: tuple[ResourceBinding, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.composition_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.target, TargetContext),
            "A composition requires a frozen target context.",
        )
        require(
            isinstance(self.registry_lock, RegistryLock),
            "A composition requires an exact registry lock.",
        )
        for key, item_type in (
            ("instances", CompositionInstance),
            ("connections", Connection),
            ("providers", Provider),
            ("dependency_bindings", DependencyBinding),
            ("resource_pools", ResourcePool),
            ("resource_bindings", ResourceBinding),
        ):
            values = _array(getattr(self, key), item_type, key)
            object.__setattr__(
                self,
                key,
                tuple(sorted(values, key=lambda item: item.to_json(indent=None))),
            )
        require(
            bool(self.instances),
            "A composition requires at least one selected instance.",
        )
        for key in ("instances", "providers", "resource_pools"):
            values = getattr(self, key)
            require(
                len({item.id for item in values}) == len(values),
                f"Duplicate {key} ids.",
            )
        require(
            not (
                {item.id for item in self.instances}
                & {item.id for item in self.providers}
            ),
            "Explicit providers cannot replace selected component providers.",
        )
        object.__setattr__(
            self,
            "requirement_ids",
            tuple(sorted(names(self.requirement_ids, "Requirement ids"))),
        )
        require(
            all(
                set(item.requirement_ids) <= set(self.requirement_ids)
                for item in self.instances
            ),
            "Instance requirements must belong to the request.",
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "target": self.target.to_dict(),
            "registry_lock": self.registry_lock.to_dict(),
            **{
                key: [item.to_dict() for item in getattr(self, key)]
                for key in (
                    "instances",
                    "connections",
                    "providers",
                    "dependency_bindings",
                    "resource_pools",
                    "resource_bindings",
                )
            },
            "requirement_ids": list(self.requirement_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {item.name for item in dataclass_fields(cls)} | {"schema_version"},
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported composition schema.",
        )
        values = {
            "target": TargetContext.from_dict(data["target"]),
            "registry_lock": RegistryLock.from_dict(data["registry_lock"]),
            "requirement_ids": data["requirement_ids"],
        }
        for key, item_type in (
            ("instances", CompositionInstance),
            ("connections", Connection),
            ("providers", Provider),
            ("dependency_bindings", DependencyBinding),
            ("resource_pools", ResourcePool),
            ("resource_bindings", ResourceBinding),
        ):
            require(isinstance(data[key], (list, tuple)), f"{key} must be an array.")
            values[key] = tuple(item_type.from_dict(item) for item in data[key])
        return cls(**values)
