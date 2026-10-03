"""Offline digital operator catalogs with explicit combinational/temporal scope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.components import ComponentLock, SyntheticComponent
from biocompiler.ir.mechanism import MechanismProgram
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION

SYNTHETIC_PROFILE_VERSION = "biocompiler.synthetic.combinational.v0.1"
TEMPORAL_PROFILE_VERSION = "biocompiler.synthetic.temporal.v0.1"
CATALOG_VERSION = "biocompiler.synthetic.catalog.v0.2"


@dataclass(frozen=True)
class SyntheticCatalog(JsonArtifact):
    components: tuple[SyntheticComponent, ...]
    version: str = CATALOG_VERSION
    schema_version: ClassVar[str] = "biocompiler.synthetic_catalog.v0.1"

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

_TEMPORAL_INTERFACES = {
    "held_for": "Boolean input -> true after uninterrupted positive duration; false immediately on input loss; no prehistory.",
    "onset": "Boolean input -> event on false-to-true transition, including initially true; per binding and contact episode.",
    "pulse": "Event trigger -> true until exclusive expiry; every trigger refreshes expiry, including at the old deadline.",
    "memory": "Cell event-set and level-reset -> initially false latch; reset dominates set/expiry, set wins expiry; optional duration.",
}


def _catalog(profile, interfaces):
    return SyntheticCatalog(
        tuple(
            SyntheticComponent(
                id=f"synthetic.{operation}",
                version="2",
                operation=operation,
                interface=interface,
                model_version=MODEL_RUNNER_VERSION,
                assumptions=(
                    "Complete atomic snapshots with explicit contact identities and canonical units.",
                    "One role and one abstract compartment; no cross-role or compartment transport.",
                ),
                guarantees=(
                    "Atomic right-continuous digital evaluation, including startup and internal deadlines; external changes precede due timers."
                    if profile == TEMPORAL_PROFILE_VERSION
                    else "Stateless right-continuous digital evaluation, including the initial snapshot.",
                    "No quantitative biological guarantee or empirical evidence is supplied.",
                ),
                supported_profile=profile,
            )
            for operation, interface in interfaces.items()
        )
    )


SYNTHETIC_CATALOG = _catalog(SYNTHETIC_PROFILE_VERSION, _INTERFACES)
TEMPORAL_CATALOG = _catalog(
    TEMPORAL_PROFILE_VERSION, {**_INTERFACES, **_TEMPORAL_INTERFACES}
)


def catalog_for_profile(profile):
    require(
        isinstance(profile, str)
        and profile in {SYNTHETIC_PROFILE_VERSION, TEMPORAL_PROFILE_VERSION},
        "Unsupported synthetic generation profile.",
    )
    return (
        TEMPORAL_CATALOG if profile == TEMPORAL_PROFILE_VERSION else SYNTHETIC_CATALOG
    )
