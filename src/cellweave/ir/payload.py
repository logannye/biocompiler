"""Frozen whole-molecule specifications, separate from accepted CDS artifacts.

These records describe supplied expectations; constructing one does not promote
a reference or admit it to a compiler pipeline. No complete biological reference
has been curated for these profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from cellweave.ir.serialization import (
    JsonArtifact,
    fields,
    name as _name,
    names as _names,
    require,
)
from cellweave.semantics.coordinates import SequenceRange

PAYLOAD_PROFILE_VERSION = "cellweave.payload_profiles.v0.1"
SUPPORTED_PAYLOAD_CLASSES = frozenset(
    {"mature_linear_rna", "linear_dna", "circular_plasmid"}
)
UNESTABLISHED_CLAIMS = (
    "expression",
    "molecular_behavior",
    "therapeutic_efficacy",
    "experimental_material_identity",
)
# Adding a real reference requires a separate reviewed source-promotion change.
ACCEPTED_BIOLOGICAL_PAYLOAD_PINS: frozenset[str] = frozenset()


def name(value, label):
    _name(value, label)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        from cellweave.errors import SerializationError

        raise SerializationError(f"{label} must be valid UTF-8.") from exc
    return value


def names(value, label):
    result = _names(value, label)
    for item in result:
        name(item, label)
    return result


def hash_value(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef"),
        f"Invalid {label} SHA-256.",
    )


def _array(value, kind, label):
    require(
        isinstance(value, (tuple, list)) and all(isinstance(x, kind) for x in value),
        f"Invalid {label} array.",
    )
    return tuple(value)


class _PayloadArtifact(JsonArtifact):
    def to_dict(self):
        def encode(value):
            if isinstance(value, JsonArtifact):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {"schema_version": self.schema_version} | {
            key: encode(getattr(self, key))
            for key, definition in self.__dataclass_fields__.items()
            if definition.init
        }

    @classmethod
    def _values(cls, data):
        fields(
            data,
            {key for key, item in cls.__dataclass_fields__.items() if item.init},
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version, "Unsupported payload schema."
        )
        return {key: value for key, value in data.items() if key != "schema_version"}


@dataclass(frozen=True)
class PayloadSource(_PayloadArtifact):
    """Retained opaque source bytes; identifiers are keys, never file paths."""

    id: str
    sha256: str
    locator: str
    schema_version: ClassVar[str] = "cellweave.payload_source.v0.1"

    def __post_init__(self):
        name(self.id, "Payload source id")
        name(self.locator, "Payload source locator")
        hash_value(self.sha256, "Payload source")

    @classmethod
    def from_dict(cls, data):
        return cls(**cls._values(data))


@dataclass(frozen=True)
class PayloadRegion(_PayloadArtifact):
    """Contiguous sequence partition; coordinates refer to normalized spelling."""

    id: str
    kind: str
    range: SequenceRange
    source_range: SequenceRange
    source_locator: str
    protein_sequence: str | None = None
    orientation: str = "forward"
    reading_frame: int = 0
    schema_version: ClassVar[str] = "cellweave.payload_region.v0.1"

    def __post_init__(self):
        for key in ("id", "kind", "source_locator", "orientation"):
            name(getattr(self, key), key)
        require(isinstance(self.range, SequenceRange), "Invalid payload region range.")
        require(
            isinstance(self.source_range, SequenceRange), "Invalid region source range."
        )
        require(type(self.reading_frame) is int, "Invalid payload reading frame.")
        if self.protein_sequence is not None:
            require(
                isinstance(self.protein_sequence, str)
                and bool(self.protein_sequence)
                and set(self.protein_sequence) <= set("ACDEFGHIKLMNPQRSTVWY*"),
                "Invalid independently expected protein spelling.",
            )

    @classmethod
    def from_dict(cls, data):
        values = cls._values(data)
        for key in ("range", "source_range"):
            values[key] = SequenceRange.from_dict(values[key])
        return cls(**values)


@dataclass(frozen=True)
class PayloadFeature(_PayloadArtifact):
    """A source-located chemistry/end assertion, not implied by base letters."""

    feature: str
    status: str
    source_locator: str
    value: str | None = None
    schema_version: ClassVar[str] = "cellweave.payload_feature.v0.1"

    def __post_init__(self):
        name(self.feature, "Payload feature")
        name(self.source_locator, "Payload feature source locator")
        require(
            self.status in ("known", "unknown", "inapplicable"),
            "Invalid feature status.",
        )
        require(
            (
                self.status == "known"
                and isinstance(self.value, str)
                and bool(self.value.strip())
            )
            or (self.status != "known" and self.value is None),
            "Only known payload features have values.",
        )

    @classmethod
    def from_dict(cls, data):
        return cls(**cls._values(data))


@dataclass(frozen=True)
class PayloadMolecule(_PayloadArtifact):
    id: str
    artifact_class: str
    alphabet: str
    sequence: str
    sequence_sha256: str
    boundaries: SequenceRange
    topology: str
    strandedness: str
    regions: tuple[PayloadRegion, ...]
    features: tuple[PayloadFeature, ...]
    source_locator: str
    completeness: str = "complete_molecule"
    orientation: str = "5prime-to-3prime"
    unknown_features: tuple[str, ...] = ()
    unestablished_claims: tuple[str, ...] = UNESTABLISHED_CLAIMS
    schema_version: ClassVar[str] = "cellweave.payload_molecule.v0.1"

    def __post_init__(self):
        for key in (
            "id",
            "artifact_class",
            "alphabet",
            "topology",
            "strandedness",
            "source_locator",
            "completeness",
            "orientation",
        ):
            name(getattr(self, key), key)
        require(self.alphabet in ("DNA", "RNA"), "Payload alphabet must be DNA or RNA.")
        require(
            isinstance(self.sequence, str)
            and bool(self.sequence)
            and set(self.sequence) <= set("ACGT" if self.alphabet == "DNA" else "ACGU"),
            "Payload spelling must use canonical uppercase symbols.",
        )
        hash_value(self.sequence_sha256, "Payload sequence")
        require(
            isinstance(self.boundaries, SequenceRange), "Invalid molecule boundaries."
        )
        for key, kind in (("regions", PayloadRegion), ("features", PayloadFeature)):
            object.__setattr__(self, key, _array(getattr(self, key), kind, key))
        require(
            len({x.id for x in self.regions}) == len(self.regions), "Duplicate regions."
        )
        require(
            len({x.feature for x in self.features}) == len(self.features),
            "Duplicate features.",
        )
        object.__setattr__(
            self, "unknown_features", names(self.unknown_features, "Unknown features")
        )
        claims = names(self.unestablished_claims, "Unestablished claims")
        require(
            claims == UNESTABLISHED_CLAIMS,
            "Payload evidence boundary cannot be weakened.",
        )
        object.__setattr__(self, "unestablished_claims", claims)

    @classmethod
    def from_dict(cls, data):
        values = cls._values(data)
        values["boundaries"] = SequenceRange.from_dict(values["boundaries"])
        for key, kind in (("regions", PayloadRegion), ("features", PayloadFeature)):
            require(isinstance(values[key], (tuple, list)), f"{key} must be an array.")
            values[key] = tuple(kind.from_dict(x) for x in values[key])
        return cls(**values)


@dataclass(frozen=True)
class PayloadReview(_PayloadArtifact):
    reviewer: str
    role: str
    source: PayloadSource
    schema_version: ClassVar[str] = "cellweave.payload_review.v0.1"

    def __post_init__(self):
        name(self.reviewer, "Reviewer identity")
        require(
            self.role in ("extraction", "independent_review"),
            "Invalid payload review role.",
        )
        require(
            isinstance(self.source, PayloadSource), "Invalid retained review source."
        )

    @classmethod
    def from_dict(cls, data):
        values = cls._values(data)
        values["source"] = PayloadSource.from_dict(values["source"])
        return cls(**values)


@dataclass(frozen=True)
class PayloadReference(_PayloadArtifact):
    """Externally pinned expectations, never reconstructed from emitted output."""

    id: str
    version: str
    expected: PayloadMolecule
    source_kind: str
    primary_source: PayloadSource
    sequence_source: PayloadSource
    reviews: tuple[PayloadReview, ...]
    schema_version: ClassVar[str] = "cellweave.payload_reference.v0.1"

    def __post_init__(self):
        name(self.id, "Payload reference id")
        name(self.version, "Payload reference version")
        require(
            isinstance(self.expected, PayloadMolecule), "Invalid expected molecule."
        )
        require(
            self.source_kind in ("software_fixture", "externally_reviewed"),
            "Invalid source kind.",
        )
        for source in (self.primary_source, self.sequence_source):
            require(isinstance(source, PayloadSource), "Invalid payload source.")
        object.__setattr__(
            self, "reviews", _array(self.reviews, PayloadReview, "Payload reviews")
        )
        sources = (self.primary_source, self.sequence_source) + tuple(
            x.source for x in self.reviews
        )
        require(
            len({x.id for x in sources}) == len(sources),
            "Duplicate payload source ids.",
        )

    @classmethod
    def from_dict(cls, data):
        values = cls._values(data)
        values["expected"] = PayloadMolecule.from_dict(values["expected"])
        for key in ("primary_source", "sequence_source"):
            values[key] = PayloadSource.from_dict(values[key])
        require(
            isinstance(values["reviews"], (tuple, list)), "Reviews must be an array."
        )
        values["reviews"] = tuple(PayloadReview.from_dict(x) for x in values["reviews"])
        return cls(**values)
