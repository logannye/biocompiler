"""Frozen assembly authority and independently checkable Construct IR candidates.

The request fixes selected composition and expected layout before assembly. A
candidate carries no acceptance certificate. Richer layouts are representable
for explicit unsupported diagnostics; schema validity proves no biology.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.ir.components import ComponentLock
from cellweave.ir.composition import CompositionRequest
from cellweave.ir.intent import SourceLocation
from cellweave.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    require,
)
from cellweave.registry.components import RegistryLock
from cellweave.registry.reference_components import ReferenceSelection
from cellweave.semantics.coordinates import ORIENTATIONS, SequenceRange


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"{label} must be a SHA-256 fingerprint.",
    )


def _enum(value, options, label):
    require(isinstance(value, str) and value in options, f"Invalid {label}.")


def _array(value, item_type, label):
    require(isinstance(value, (list, tuple)), f"{label} must be an array.")
    require(all(isinstance(item, item_type) for item in value), f"Invalid {label}.")
    return tuple(value)


def _decode_array(value, item_type):
    require(isinstance(value, (list, tuple)), "Construct records must be arrays.")
    return tuple(item_type.from_dict(item) for item in value)


def _reference(value):
    require(
        isinstance(value, PinnedIdentity) and value.kind == "reference",
        "A construct reference requires an exact pinned reference identity.",
    )


def _provenance(value):
    value = _array(value, PinnedIdentity, "Boundary/relationship provenance")
    require(
        all(item.kind in {"source", "evidence"} for item in value),
        "Boundary provenance must identify a source or review evidence.",
    )
    require(len(set(value)) == len(value), "Duplicate provenance identities.")
    return value


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _derived: ClassVar[frozenset[str]] = frozenset()

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

    @classmethod
    def from_dict(cls, data):
        try:
            fields(
                data,
                {item.name for item in dataclass_fields(cls)}
                | {"schema_version"}
                | set(cls._derived),
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                f"Unsupported {cls.__name__} schema.",
            )
            values = {
                item.name: cls._decoders.get(item.name, lambda value: value)(
                    data[item.name]
                )
                for item in dataclass_fields(cls)
            }
            result = cls(**values)
            for key in cls._derived:
                require(
                    fingerprint(data[key]) == fingerprint(result.to_dict()[key]),
                    f"Derived construct {key} differs from its authority.",
                )
            return result
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise SerializationError(f"Invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True)
class ConstructReference(_Record):
    """Caller-trusted reference selection for one selected component instance."""

    instance_id: str
    selection: ReferenceSelection
    schema_version: ClassVar[str] = "cellweave.construct_reference.v0.1"
    _decoders: ClassVar[dict] = {"selection": ReferenceSelection.from_dict}

    def __post_init__(self):
        name(self.instance_id, "Reference instance ID")
        require(isinstance(self.selection, ReferenceSelection), "Invalid selection.")


@dataclass(frozen=True)
class ConstructMolecule(_Record):
    """Explicit coding-segment or molecule inventory, without implied delivery."""

    id: str
    alphabet: str
    artifact_class: str
    length: int
    component_order: tuple[str, ...]
    topology: str = "unspecified"
    completeness: str = "CDS-reference-only"
    unknown_features: tuple[str, ...] = ()
    compartment: str = "unspecified"
    schema_version: ClassVar[str] = "cellweave.construct_molecule.v0.1"

    def __post_init__(self):
        for key in ("id", "artifact_class", "completeness", "compartment"):
            name(getattr(self, key), key)
        _enum(self.alphabet, {"DNA", "RNA"}, "construct alphabet")
        _enum(self.topology, {"linear", "circular", "unspecified"}, "topology")
        require(
            type(self.length) is int and self.length > 0, "Invalid molecule length."
        )
        for key in ("component_order", "unknown_features"):
            object.__setattr__(self, key, names(getattr(self, key), key))


@dataclass(frozen=True)
class ComponentPlacement(_Record):
    """Source and destination coordinates for one selected instance.

    Frame 0, 1 or 2 is relative to the oriented source slice's first symbol. Null
    asserts no translation frame. Neither coordinate validity nor frame proves ORF
    validity; the independent checker must reconcile the reviewed reference.
    """

    instance_id: str
    molecule_id: str
    component: ComponentLock
    reference: PinnedIdentity
    source_range: SequenceRange
    molecule_range: SequenceRange
    orientation: str = "forward"
    reading_frame: int | None = 0
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None
    schema_version: ClassVar[str] = "cellweave.component_placement.v0.1"
    _decoders: ClassVar[dict] = {
        "component": ComponentLock.from_dict,
        "reference": PinnedIdentity.from_dict,
        "source_range": SequenceRange.from_dict,
        "molecule_range": SequenceRange.from_dict,
        "source": lambda value: (
            SourceLocation.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        name(self.instance_id, "Placement instance ID")
        name(self.molecule_id, "Placement molecule ID")
        require(isinstance(self.component, ComponentLock), "Invalid component lock.")
        _reference(self.reference)
        for key in ("source_range", "molecule_range"):
            value = getattr(self, key)
            require(
                isinstance(value, SequenceRange) and value.length > 0,
                "Component placements require nonempty coordinate ranges.",
            )
        _enum(self.orientation, ORIENTATIONS, "placement orientation")
        require(
            self.reading_frame is None
            or (type(self.reading_frame) is int and self.reading_frame in (0, 1, 2)),
            "A reading frame must be 0, 1, 2 or unspecified.",
        )
        object.__setattr__(
            self, "requirement_ids", names(self.requirement_ids, "Requirement IDs")
        )
        require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid placement source location.",
        )


@dataclass(frozen=True)
class ConstructFeature(_Record):
    """Boundary claim with pinned provenance; source diagrams do not imply bases."""

    id: str
    molecule_id: str
    kind: str
    range: SequenceRange
    source_reference: PinnedIdentity
    source_range: SequenceRange
    source_locator: str
    provenance: tuple[PinnedIdentity, ...]
    orientation: str = "forward"
    schema_version: ClassVar[str] = "cellweave.construct_feature.v0.1"
    _decoders: ClassVar[dict] = {
        "range": SequenceRange.from_dict,
        "source_reference": PinnedIdentity.from_dict,
        "source_range": SequenceRange.from_dict,
        "provenance": lambda value: _decode_array(value, PinnedIdentity),
    }

    def __post_init__(self):
        for key in ("id", "molecule_id", "kind", "source_locator"):
            name(getattr(self, key), key)
        for key in ("range", "source_range"):
            value = getattr(self, key)
            require(
                isinstance(value, SequenceRange) and value.length > 0,
                "Features require nonempty coordinate ranges.",
            )
        _reference(self.source_reference)
        _enum(self.orientation, ORIENTATIONS, "feature orientation")
        object.__setattr__(self, "provenance", _provenance(self.provenance))
        require(bool(self.provenance), "Feature boundaries require pinned provenance.")


@dataclass(frozen=True)
class ConstructJunction(_Record):
    id: str
    molecule_id: str
    left_instance: str
    right_instance: str
    kind: str
    range: SequenceRange
    choice: str
    provenance: tuple[PinnedIdentity, ...] = ()
    schema_version: ClassVar[str] = "cellweave.construct_junction.v0.1"
    _decoders: ClassVar[dict] = {
        "range": SequenceRange.from_dict,
        "provenance": lambda value: _decode_array(value, PinnedIdentity),
    }

    def __post_init__(self):
        for key in ("id", "molecule_id", "left_instance", "right_instance", "choice"):
            name(getattr(self, key), key)
        _enum(self.kind, {"direct", "overlap", "gap"}, "junction kind")
        require(isinstance(self.range, SequenceRange), "Invalid junction range.")
        require(
            (self.kind == "direct") == (self.range.length == 0),
            "Direct junctions require an empty range; overlaps/gaps require a span.",
        )
        object.__setattr__(self, "provenance", _provenance(self.provenance))


@dataclass(frozen=True)
class RegulatoryRelationship(_Record):
    id: str
    kind: str
    regulator_instance: str
    target_instance: str
    provenance: tuple[PinnedIdentity, ...] = ()
    assumptions: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "cellweave.construct_regulation.v0.1"
    _decoders: ClassVar[dict] = {
        "provenance": lambda value: _decode_array(value, PinnedIdentity)
    }

    def __post_init__(self):
        for key in ("id", "kind", "regulator_instance", "target_instance"):
            name(getattr(self, key), key)
        object.__setattr__(self, "provenance", _provenance(self.provenance))
        object.__setattr__(
            self, "assumptions", names(self.assumptions, "Regulatory assumptions")
        )


@dataclass(frozen=True)
class ConstructDependency(_Record):
    """Cross-molecule dependency; same-cell coexistence remains an assumption."""

    id: str
    consumer_molecule: str
    provider_molecule: str
    kind: str
    assumption: str
    requirement_ids: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "cellweave.construct_dependency.v0.1"

    def __post_init__(self):
        for key in ("id", "consumer_molecule", "provider_molecule", "assumption"):
            name(getattr(self, key), key)
        _enum(
            self.kind,
            {"same_cell", "co_payload", "regulatory", "resource"},
            "construct dependency kind",
        )
        object.__setattr__(
            self, "requirement_ids", names(self.requirement_ids, "Requirement IDs")
        )


_SEMANTIC_PROPERTIES = (
    "membership",
    "order",
    "orientation",
    "boundaries",
    "junctions",
    "reading_frame",
    "regulation",
    "localization",
    "payload_partitioning",
)


@dataclass(frozen=True)
class LayoutEvidencePolicy(_Record):
    """Serialized invalidation rule, not a claim that analyses were rerun."""

    semantic_properties: tuple[str, ...] = _SEMANTIC_PROPERTIES
    invalidated_analyses: tuple[str, ...] = ("composition", "behavior")
    schema_version: ClassVar[str] = "cellweave.construct_evidence_policy.v0.1"

    def __post_init__(self):
        for key in ("semantic_properties", "invalidated_analyses"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            self.semantic_properties == _SEMANTIC_PROPERTIES
            and self.invalidated_analyses == ("composition", "behavior"),
            "Construct evidence invalidation policy cannot be weakened or replaced.",
        )


_LAYOUT_TYPES = {
    "molecules": ConstructMolecule,
    "placements": ComponentPlacement,
    "features": ConstructFeature,
    "junctions": ConstructJunction,
    "regulatory_relations": RegulatoryRelationship,
    "dependencies": ConstructDependency,
}
_LAYOUT_DECODERS = {
    key: (lambda value, cls=cls: _decode_array(value, cls))
    for key, cls in _LAYOUT_TYPES.items()
} | {"evidence_policy": LayoutEvidencePolicy.from_dict}


def _layout(record):
    for key, cls in _LAYOUT_TYPES.items():
        value = _array(getattr(record, key), cls, key)
        ids = [
            item.instance_id if isinstance(item, ComponentPlacement) else item.id
            for item in value
        ]
        require(len(set(ids)) == len(ids), f"Duplicate construct {key} IDs.")
        object.__setattr__(record, key, value)
    object.__setattr__(record, "assumptions", names(record.assumptions, "Assumptions"))
    require(
        isinstance(record.evidence_policy, LayoutEvidencePolicy),
        "Invalid layout evidence policy.",
    )


class _LayoutRecord(_Record):
    def layout_dict(self):
        """All layout/lineage assertions, separate from request identity roots."""
        data = super().to_dict()
        return {
            key: data[key] for key in (*_LAYOUT_TYPES, "assumptions", "evidence_policy")
        }

    @property
    def layout_fingerprint(self):
        return fingerprint(self.layout_dict())


@dataclass(frozen=True)
class ConstructRequest(_LayoutRecord):
    """Expected layout pinned independently of the assembly candidate."""

    composition: CompositionRequest
    references: tuple[ConstructReference, ...]
    molecules: tuple[ConstructMolecule, ...]
    placements: tuple[ComponentPlacement, ...]
    features: tuple[ConstructFeature, ...] = ()
    junctions: tuple[ConstructJunction, ...] = ()
    regulatory_relations: tuple[RegulatoryRelationship, ...] = ()
    dependencies: tuple[ConstructDependency, ...] = ()
    assumptions: tuple[str, ...] = ()
    source_request_fingerprint: str | None = None
    evidence_policy: LayoutEvidencePolicy = LayoutEvidencePolicy()
    schema_version: ClassVar[str] = "cellweave.construct_request.v0.1"
    _derived: ClassVar[frozenset[str]] = frozenset({"nodes", "target"})
    _decoders: ClassVar[dict] = _LAYOUT_DECODERS | {
        "composition": CompositionRequest.from_dict,
        "references": lambda value: _decode_array(value, ConstructReference),
    }

    def __post_init__(self):
        require(
            isinstance(self.composition, CompositionRequest),
            "A construct request requires its exact selected composition.",
        )
        references = _array(self.references, ConstructReference, "Construct references")
        require(
            len({item.instance_id for item in references}) == len(references),
            "Duplicate construct reference instance IDs.",
        )
        object.__setattr__(self, "references", references)
        if self.source_request_fingerprint is not None:
            _hash(self.source_request_fingerprint, "Source request")
        _layout(self)

    @property
    def target(self):
        return self.composition.target

    @property
    def registry_lock(self):
        return self.composition.registry_lock

    def to_dict(self):
        return super().to_dict() | {
            "target": self.target.to_dict(),
            "nodes": [
                {"id": item.id, "kind": "component_instance"}
                for item in self.composition.instances
            ],
        }


@dataclass(frozen=True)
class ConstructCandidate(_LayoutRecord):
    """Unchecked layout artifact; acceptance always requires the frozen request."""

    request_fingerprint: str
    composition_fingerprint: str
    registry_lock: RegistryLock
    molecules: tuple[ConstructMolecule, ...]
    placements: tuple[ComponentPlacement, ...]
    features: tuple[ConstructFeature, ...] = ()
    junctions: tuple[ConstructJunction, ...] = ()
    regulatory_relations: tuple[RegulatoryRelationship, ...] = ()
    dependencies: tuple[ConstructDependency, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence_policy: LayoutEvidencePolicy = LayoutEvidencePolicy()
    schema_version: ClassVar[str] = "cellweave.construct.v0.1"
    _derived: ClassVar[frozenset[str]] = frozenset({"nodes"})
    _decoders: ClassVar[dict] = _LAYOUT_DECODERS | {
        "registry_lock": RegistryLock.from_dict
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Construct request")
        _hash(self.composition_fingerprint, "Composition request")
        require(isinstance(self.registry_lock, RegistryLock), "Invalid registry lock.")
        _layout(self)

    def to_dict(self):
        return super().to_dict() | {
            "nodes": [
                {"id": item.instance_id, "kind": "component_placement"}
                for item in self.placements
            ]
        }
