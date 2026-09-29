"""Small, versioned synthetic component records and exact implementation locks.

These records describe digital fixture operators. They are not sequence records
or biological parts; provider, resource and biological-domain linking remains a
separate unimplemented profile.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from cellweave.ir.serialization import JsonArtifact, fields, name, names, require


@dataclass(frozen=True)
class SyntheticComponent(JsonArtifact):
    id: str
    version: str
    operation: str
    interface: str
    model_version: str
    assumptions: tuple[str, ...]
    guarantees: tuple[str, ...]
    supported_profile: str
    schema_version: ClassVar[str] = "cellweave.component.synthetic.v0.1"

    def __post_init__(self):
        for key in (
            "id",
            "version",
            "operation",
            "interface",
            "model_version",
            "supported_profile",
        ):
            name(getattr(self, key), key)
        for key in ("assumptions", "guarantees"):
            object.__setattr__(self, key, names(getattr(self, key), key))

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "version": self.version,
            "operation": self.operation,
            "interface": self.interface,
            "model_version": self.model_version,
            "assumptions": list(self.assumptions),
            "guarantees": list(self.guarantees),
            "supported_profile": self.supported_profile,
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "id",
                "version",
                "operation",
                "interface",
                "model_version",
                "assumptions",
                "guarantees",
                "supported_profile",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported synthetic component schema.",
        )
        return cls(
            **{key: value for key, value in data.items() if key != "schema_version"}
        )


@dataclass(frozen=True)
class ComponentLock(JsonArtifact):
    """Pin one graph instance to the exact offline operator definition.

    Concrete types, units, endpoint meanings, role and contact scope belong to
    the locked candidate's MechanismNode ports and are validated by its schema.
    """

    node_id: str
    component_id: str
    version: str
    content_fingerprint: str
    schema_version: ClassVar[str] = "cellweave.component_lock.v0.1"

    def __post_init__(self):
        for key in ("node_id", "component_id", "version"):
            name(getattr(self, key), key)
        require(
            isinstance(self.content_fingerprint, str)
            and len(self.content_fingerprint) == 64
            and all(char in "0123456789abcdef" for char in self.content_fingerprint),
            "A component lock requires a SHA-256 content identity.",
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "component_id": self.component_id,
            "version": self.version,
            "content_fingerprint": self.content_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "node_id",
                "component_id",
                "version",
                "content_fingerprint",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported component-lock schema.",
        )
        return cls(
            **{key: value for key, value in data.items() if key != "schema_version"}
        )
