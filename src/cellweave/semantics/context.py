"""Versioned target assumptions; identity and declared capabilities are not evidence.

Targets record host capabilities, modality, compartments and resource assumptions
before mechanism selection. No declaration certifies a biological implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar

from cellweave.errors import DefinitionError, SerializationError, TypeMismatchError
from cellweave.ir.serialization import JsonArtifact, fields, name, names, require
from cellweave.semantics.types import ScalarLiteral, TypeSpec, decode_binding


class PayloadFormat(StrEnum):
    DNA = "DNA"
    RNA = "RNA"


@dataclass(frozen=True)
class TargetContext(JsonArtifact):
    """Identify the versioned host assumptions required by a build.

    The original three positional arguments remain valid. Resource values are
    explicitly typed, nonnegative assumptions, not measured available capacity.
    """

    context_id: str
    context_version: str
    payload_format: PayloadFormat
    capabilities: tuple[str, ...] = ()
    compartments: tuple[str, ...] = ("abstract",)
    resources: Mapping[str, ScalarLiteral] = field(default_factory=dict)
    schema_version: ClassVar[str] = "cellweave.target.v0.1"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_id, str)
            or not self.context_id.strip()
            or not isinstance(self.context_version, str)
            or not self.context_version.strip()
        ):
            raise DefinitionError(
                "Target context id and version must be nonempty strings."
            )
        if not isinstance(self.payload_format, PayloadFormat):
            raise TypeMismatchError(
                "Target payload_format must be PayloadFormat.DNA or .RNA."
            )
        object.__setattr__(
            self,
            "capabilities",
            tuple(sorted(names(self.capabilities, "Capabilities"))),
        )
        compartments = tuple(sorted(names(self.compartments, "Compartments")))
        require(bool(compartments), "A target must declare at least one compartment.")
        object.__setattr__(self, "compartments", compartments)
        require(
            isinstance(self.resources, Mapping),
            "Resources must be a mapping of typed scalar assumptions.",
        )
        resources = {}
        for key, value in self.resources.items():
            name(key, "Resource id")
            require(
                isinstance(value, ScalarLiteral),
                "Resource assumptions require typed scalar literals.",
            )
            try:
                normalized = decode_binding(value.to_dict(), value.dtype)
            except (TypeMismatchError, ValueError, AttributeError) as exc:
                raise SerializationError(f"Invalid resource {key!r}: {exc}") from exc
            require(
                normalized.canonical_value >= 0,
                "Resource assumptions must be nonnegative.",
            )
            resources[key] = normalized
        object.__setattr__(self, "resources", MappingProxyType(resources))

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "context_id": self.context_id,
            "context_version": self.context_version,
            "payload_format": self.payload_format.value,
            "capabilities": list(self.capabilities),
            "compartments": list(self.compartments),
            "resources": {
                key: value.to_dict() for key, value in self.resources.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> TargetContext:
        fields(
            data,
            {
                "schema_version",
                "context_id",
                "context_version",
                "payload_format",
                "capabilities",
                "compartments",
                "resources",
            },
            "target context",
        )
        require(
            data["schema_version"] == cls.schema_version, "Unsupported target schema."
        )
        require(isinstance(data["resources"], Mapping), "Resources must be an object.")
        try:
            modality = PayloadFormat(data["payload_format"])
            resources = {}
            for key, value in data["resources"].items():
                require(
                    isinstance(value, Mapping)
                    and isinstance(value.get("type"), Mapping),
                    "Invalid typed resource.",
                )
                dtype = TypeSpec.from_dict(value["type"])
                require(dtype.kind == "scalar", "Resources must be scalar.")
                resources[key] = decode_binding(value, dtype)
            return cls(
                data["context_id"],
                data["context_version"],
                modality,
                data["capabilities"],
                data["compartments"],
                resources,
            )
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            if isinstance(exc, SerializationError):
                raise
            raise SerializationError(f"Invalid target context: {exc}") from exc
