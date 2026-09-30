"""A locked component candidate with source lineage, not an acceptance receipt."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.ir.composition import CompositionRequest
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    names,
    require,
)
from biocompiler.registry.components import ComponentRegistry
from biocompiler.verification.realization import ObservationMap


@dataclass(frozen=True)
class ComponentAssembly(JsonArtifact):
    registry: ComponentRegistry
    composition: CompositionRequest
    request_fingerprint: str
    candidate_fingerprint: str
    behavior_sources: Mapping[str, tuple[str, ...]]
    observation_map: ObservationMap
    schema_version: ClassVar[str] = "biocompiler.component_assembly.v0.2"

    def __post_init__(self):
        require(isinstance(self.observation_map, ObservationMap),
                "A component assembly requires explicit input/output bindings.")
        require(
            isinstance(self.registry, ComponentRegistry),
            "Expected a component registry.",
        )
        require(
            isinstance(self.composition, CompositionRequest),
            "Expected a composition request.",
        )
        for value in (self.request_fingerprint, self.candidate_fingerprint):
            require(
                isinstance(value, str)
                and len(value) == 64
                and all(char in "0123456789abcdef" for char in value),
                "An assembly must pin its source request and candidate.",
            )
        require(
            isinstance(self.behavior_sources, Mapping),
            "Behavior sources must be an object.",
        )
        ids = {item.id for item in self.composition.instances}
        require(
            set(self.behavior_sources) == ids,
            "Every component requires source lineage.",
        )
        sources = {}
        for key, values in self.behavior_sources.items():
            sources[key] = names(values, "Behavior source IDs")
            require(bool(sources[key]), "Component source lineage cannot be empty.")
        object.__setattr__(self, "behavior_sources", MappingProxyType(sources))
        # Resolving checks registry/model/reference hashes without claiming that
        # the resulting connections or behavior have been accepted.
        resolved = self.registry.resolve(self.composition.registry_lock)
        require(
            set(resolved) == ids, "The assembly lock must cover exactly its instances."
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "registry": self.registry.to_dict(),
            "composition": self.composition.to_dict(),
            "request_fingerprint": self.request_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "observation_map": self.observation_map.to_dict(),
            "behavior_sources": {
                key: list(value) for key, value in self.behavior_sources.items()
            },
            "nodes": [
                {"id": item.id, "kind": "component_instance"}
                for item in self.composition.instances
            ],
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "registry",
                "composition",
                "request_fingerprint",
                "candidate_fingerprint",
                "behavior_sources",
                "observation_map",
                "nodes",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported component assembly schema.",
        )
        result = cls(
            ComponentRegistry.from_dict(data["registry"]),
            CompositionRequest.from_dict(data["composition"]),
            data["request_fingerprint"],
            data["candidate_fingerprint"],
            data["behavior_sources"],
            ObservationMap.from_dict(data["observation_map"]),
        )
        require(
            isinstance(data["nodes"], (tuple, list))
            and fingerprint(data["nodes"]) == fingerprint(result.to_dict()["nodes"]),
            "The component inventory must match the locked composition.",
        )
        return result
