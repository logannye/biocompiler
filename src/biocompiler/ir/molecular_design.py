"""Frozen software-only fragment authority and multi-region RNA candidates.

The request is an independently supplied design specification, not inferred
biological support. Fragment symbols are retained literally; source locators are
declarations, not evidence that an external source was extracted or reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.payload import PayloadFeature, PayloadMolecule, hash_value, name
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    names,
    require,
)
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.coordinates import SequenceRange

PROFILE_VERSION = "biocompiler.molecular_design_profile.v0.1"
SOURCE_LOCATOR_PREFIX = "molecular-design-request:"
SOFTWARE_TARGET = TargetContext("software_molecular_design", "1", PayloadFormat.RNA)
MAX_FRAGMENT_BASES = 100_000
MAX_FRAGMENTS = 16


def _records(value, cls, label):
    require(
        isinstance(value, (tuple, list)) and all(isinstance(x, cls) for x in value),
        f"Invalid {label} records.",
    )
    return tuple(value)


def _decode_records(value, cls):
    require(isinstance(value, (tuple, list)), "Records must be an array.")
    return tuple(cls.from_dict(x) for x in value)


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _derived: ClassVar[tuple[str, ...]] = ()

    def to_dict(self):
        def encode(value):
            if isinstance(value, JsonArtifact):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(x) for x in value]
            return value

        return (
            {"schema_version": self.schema_version}
            | {
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            }
            | {key: encode(getattr(self, key)) for key in self._derived}
        )

    @classmethod
    def from_dict(cls, data):
        try:
            keys = {item.name for item in dataclass_fields(cls)}
            fields(data, keys | {"schema_version"} | set(cls._derived), cls.__name__)
            require(
                data["schema_version"] == cls.schema_version,
                "Unsupported molecular design schema.",
            )
            result = cls(
                **{
                    key: cls._decoders.get(key, lambda value: value)(data[key])
                    for key in keys
                }
            )
            for key in cls._derived:
                require(
                    fingerprint(data[key]) == fingerprint(getattr(result, key)),
                    f"Derived molecular design {key} differs from authority.",
                )
            return result
        except SerializationError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
            raise SerializationError(f"Invalid {cls.__name__}: {exc}") from exc


def _software_labels(record):
    require(record.profile == PROFILE_VERSION, "Unsupported molecular design profile.")
    require(
        record.intended_use == "software_test"
        and record.human_therapeutic_admission == "not_admitted"
        and record.reference_promotion == "not_promoted"
        and record.evidence_boundary == "software_fixture",
        "Molecular design artifacts cannot promote fixtures or admit human use.",
    )


@dataclass(frozen=True)
class SequenceFragment(_Record):
    """Literal source symbols independently pinned by the frozen design request."""

    id: str
    sequence: str
    sequence_sha256: str
    source_locator: str
    alphabet: str = "RNA"
    evidence_boundary: str = "software_fixture"
    schema_version: ClassVar[str] = "biocompiler.sequence_fragment.v0.1"

    def __post_init__(self):
        name(self.id, "Fragment id")
        name(self.source_locator, "Fragment source locator")
        require(self.alphabet in ("DNA", "RNA"), "Invalid fragment alphabet.")
        require(
            isinstance(self.sequence, str)
            and 0 < len(self.sequence) <= MAX_FRAGMENT_BASES
            and set(self.sequence) <= set("ACGU" if self.alphabet == "RNA" else "ACGT"),
            "Fragment symbols must be explicit canonical uppercase nucleotides within the size limit.",
        )
        hash_value(self.sequence_sha256, "Fragment sequence")
        require(
            self.evidence_boundary == "software_fixture",
            "Only software fragment authority is supported.",
        )


@dataclass(frozen=True)
class FragmentPlacement(_Record):
    """A frozen fragment slice and destination, not a functional component claim."""

    region_id: str
    kind: str
    fragment_id: str
    fragment_fingerprint: str
    source_range: SequenceRange
    molecule_range: SequenceRange
    protein_sequence: str | None = None
    orientation: str = "forward"
    reading_frame: int = 0
    schema_version: ClassVar[str] = "biocompiler.fragment_placement.v0.1"
    _decoders: ClassVar[dict] = {
        "source_range": SequenceRange.from_dict,
        "molecule_range": SequenceRange.from_dict,
    }

    def __post_init__(self):
        for key in ("region_id", "kind", "fragment_id"):
            name(getattr(self, key), key)
        hash_value(self.fragment_fingerprint, "Placed fragment")
        require(
            isinstance(self.source_range, SequenceRange)
            and isinstance(self.molecule_range, SequenceRange),
            "Invalid fragment coordinates.",
        )
        require(
            self.orientation in ("forward", "reverse"), "Invalid fragment orientation."
        )
        require(
            type(self.reading_frame) is int and self.reading_frame in (0, 1, 2),
            "Invalid fragment reading frame.",
        )
        if self.protein_sequence is not None:
            require(
                isinstance(self.protein_sequence, str)
                and bool(self.protein_sequence)
                and set(self.protein_sequence) <= set("ACDEFGHIKLMNPQRSTVWY*"),
                "Invalid supplied protein spelling.",
            )


def _layout(record):
    name(record.molecule_id, "Molecule id")
    for key, cls in (("placements", FragmentPlacement), ("features", PayloadFeature)):
        values = _records(getattr(record, key), cls, key)
        object.__setattr__(record, key, values)
    require(len(record.placements) <= MAX_FRAGMENTS, "Too many placements.")
    require(
        len({x.region_id for x in record.placements}) == len(record.placements),
        "Duplicate placed region identities.",
    )
    require(
        len({x.feature for x in record.features}) == len(record.features),
        "Duplicate chemistry features.",
    )
    object.__setattr__(
        record,
        "unknown_features",
        names(record.unknown_features, "Unknown molecular features"),
    )
    for value in record.unknown_features:
        name(value, "Unknown molecular feature")
    _software_labels(record)


@dataclass(frozen=True)
class MolecularDesignRequest(_Record):
    id: str
    molecule_id: str
    fragments: tuple[SequenceFragment, ...]
    placements: tuple[FragmentPlacement, ...]
    features: tuple[PayloadFeature, ...]
    unknown_features: tuple[str, ...] = ()
    target: TargetContext = SOFTWARE_TARGET
    profile: str = PROFILE_VERSION
    intended_use: str = "software_test"
    human_therapeutic_admission: str = "not_admitted"
    reference_promotion: str = "not_promoted"
    evidence_boundary: str = "software_fixture"
    schema_version: ClassVar[str] = "biocompiler.molecular_design_request.v0.1"
    _derived: ClassVar[tuple[str, ...]] = ("nodes",)
    _decoders: ClassVar[dict] = {
        "fragments": lambda value: _decode_records(value, SequenceFragment),
        "placements": lambda value: _decode_records(value, FragmentPlacement),
        "features": lambda value: _decode_records(value, PayloadFeature),
        "target": TargetContext.from_dict,
    }

    def __post_init__(self):
        name(self.id, "Design request id")
        object.__setattr__(
            self, "fragments", _records(self.fragments, SequenceFragment, "fragments")
        )
        require(
            0 < len(self.fragments) <= MAX_FRAGMENTS, "Invalid fragment inventory size."
        )
        require(
            len({x.id for x in self.fragments}) == len(self.fragments),
            "Duplicate fragment identities.",
        )
        require(isinstance(self.target, TargetContext), "A frozen target is required.")
        try:
            self.target.to_json(indent=None).encode("utf-8")
        except UnicodeError as exc:
            raise SerializationError(
                "Molecular design target must contain valid UTF-8 text."
            ) from exc
        _layout(self)

    @property
    def requirement_ids(self):
        """Layout identities only; none is an intent or functional requirement."""
        return tuple("region:" + placement.region_id for placement in self.placements)

    @property
    def nodes(self):
        return tuple(
            {
                "id": fragment.id,
                "kind": "component_instance",
                "component_kind": "sequence_fragment",
                "fragment_fingerprint": fragment.fingerprint,
            }
            for fragment in self.fragments
        )


@dataclass(frozen=True)
class MolecularDesignConstruct(_Record):
    request_fingerprint: str
    molecule_id: str
    placements: tuple[FragmentPlacement, ...]
    features: tuple[PayloadFeature, ...]
    unknown_features: tuple[str, ...] = ()
    profile: str = PROFILE_VERSION
    intended_use: str = "software_test"
    human_therapeutic_admission: str = "not_admitted"
    reference_promotion: str = "not_promoted"
    evidence_boundary: str = "software_fixture"
    schema_version: ClassVar[str] = "biocompiler.molecular_design_construct.v0.1"
    _derived: ClassVar[tuple[str, ...]] = ("nodes",)
    _decoders: ClassVar[dict] = {
        "placements": lambda value: _decode_records(value, FragmentPlacement),
        "features": lambda value: _decode_records(value, PayloadFeature),
    }

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Construct request")
        _layout(self)

    @property
    def nodes(self):
        return tuple(
            {"id": placement.region_id, "kind": "fragment_placement"}
            for placement in self.placements
        )


@dataclass(frozen=True)
class MolecularDesignArtifact(_Record):
    request_fingerprint: str
    construct_fingerprint: str
    molecule: PayloadMolecule
    source_maps: tuple[FragmentPlacement, ...]
    profile: str = PROFILE_VERSION
    intended_use: str = "software_test"
    human_therapeutic_admission: str = "not_admitted"
    reference_promotion: str = "not_promoted"
    evidence_boundary: str = "software_fixture"
    schema_version: ClassVar[str] = "biocompiler.molecular_design_artifact.v0.1"
    _derived: ClassVar[tuple[str, ...]] = ("nodes",)
    _decoders: ClassVar[dict] = {
        "molecule": PayloadMolecule.from_dict,
        "source_maps": lambda value: _decode_records(value, FragmentPlacement),
    }

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Molecular request")
        hash_value(self.construct_fingerprint, "Molecular construct")
        require(
            isinstance(self.molecule, PayloadMolecule),
            "A structured molecule is required.",
        )
        object.__setattr__(
            self,
            "source_maps",
            _records(self.source_maps, FragmentPlacement, "source maps"),
        )
        require(
            len(self.source_maps) <= MAX_FRAGMENTS, "Too many molecular source maps."
        )
        require(
            len({x.region_id for x in self.source_maps}) == len(self.source_maps),
            "Duplicate molecular source maps.",
        )
        _software_labels(self)

    @property
    def nodes(self):
        return tuple(
            {"id": placement.region_id, "kind": "molecular_region"}
            for placement in self.source_maps
        )
