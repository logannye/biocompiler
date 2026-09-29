"""The small offline catalog used by the combinational synthetic generator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from cellweave.ir.components import ComponentLock, SyntheticComponent
from cellweave.ir.mechanism import MechanismProgram
from cellweave.ir.serialization import JsonArtifact, fields, require
from cellweave.models.synthetic import MODEL_RUNNER_VERSION

SYNTHETIC_PROFILE_VERSION = "cellweave.synthetic.combinational.v0.1"
CATALOG_VERSION = "cellweave.synthetic.catalog.v0.1"


@dataclass(frozen=True)
class SyntheticCatalog(JsonArtifact):
    components: tuple[SyntheticComponent, ...]
    version: str = CATALOG_VERSION
    schema_version: ClassVar[str] = "cellweave.synthetic_catalog.v0.1"

    def __post_init__(self):
        require(
            self.version == CATALOG_VERSION, "Unsupported synthetic catalog version."
        )
        require(
            isinstance(self.components, (list, tuple))
            and bool(self.components)
            and all(isinstance(item, SyntheticComponent) for item in self.components),
            "A catalog requires synthetic component records.",
        )
        components = tuple(sorted(self.components, key=lambda item: item.id))
        require(
            len({item.id for item in components}) == len(components)
            and len({item.operation for item in components}) == len(components),
            "Catalog component IDs and operation providers must be unique.",
        )
        object.__setattr__(self, "components", components)

    def for_operation(self, operation: str) -> SyntheticComponent:
        for component in self.components:
            if component.operation == operation:
                return component
        raise KeyError(operation)

    def lock(self, mechanism: MechanismProgram) -> tuple[ComponentLock, ...]:
        return tuple(
            ComponentLock(
                node.id, component.id, component.version, component.fingerprint
            )
            for node in sorted(mechanism.nodes, key=lambda item: item.id)
            for component in (self.for_operation(node.kind),)
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "version": self.version,
            "components": [item.to_dict() for item in self.components],
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(data, {"schema_version", "version", "components"}, cls.__name__)
        require(
            data["schema_version"] == cls.schema_version, "Unsupported catalog schema."
        )
        require(
            isinstance(data["components"], (tuple, list)),
            "Components must be an array.",
        )
        return cls(
            tuple(SyntheticComponent.from_dict(item) for item in data["components"]),
            data["version"],
        )


_INTERFACES = {
    "input": "External Boolean or canonical scalar observation -> identical typed port.",
    "constant": "Explicit typed Boolean or canonical scalar literal -> identical typed port.",
    "and": "At least two Boolean ports -> Boolean conjunction, preserving contact binding.",
    "or": "At least two Boolean ports -> Boolean disjunction, preserving contact binding.",
    "not": "One Boolean port -> Boolean negation, preserving contact binding.",
    "compare": "Two dimension-compatible scalar ports -> Boolean comparison.",
    "select": "Boolean condition and two dimension-compatible values -> branch value of that type.",
    "any_contact": "One Boolean contact port -> Boolean existential reduction at cell scope.",
    "output": "One port -> identical type and exact declared observable endpoint.",
}

SYNTHETIC_CATALOG = SyntheticCatalog(
    tuple(
        SyntheticComponent(
            id=f"synthetic.{operation}",
            version="1",
            operation=operation,
            interface=interface,
            model_version=MODEL_RUNNER_VERSION,
            assumptions=(
                "Complete atomic snapshots with explicit contact identities and canonical units.",
                "One role and one abstract compartment; no cross-role or compartment transport.",
            ),
            guarantees=(
                "Stateless right-continuous digital evaluation, including the initial snapshot.",
                "No quantitative biological guarantee or empirical evidence is supplied.",
            ),
            supported_profile=SYNTHETIC_PROFILE_VERSION,
        )
        for operation, interface in _INTERFACES.items()
    )
)
