"""Unchecked circuit construction candidates with explicit residue derivation.

These records contain proposed computed values, never independent expectations.
Fresh verification needs the complete, separately retained construction request.
"""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.artifacts.circuit_molecules import (
    CircuitMoleculeRecord,
    ExperimentalAmount,
)
from biocompiler.ir.circuit_molecules import CircuitMoleculeSet, MoleculeFeature
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.molecule_records import (
    CANONICAL_ALPHABETS,
    MAX_RESIDUES,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)


@dataclass(frozen=True)
class DerivedSegment(_MoleculeRecord):
    destination: IndexSpan
    source_id: str
    source_path: CoordinatePath
    rule: str
    schema_version: ClassVar[str] = "biocompiler.circuit_derived_segment.v0.1"
    _decoders: ClassVar[dict] = {
        "destination": IndexSpan.from_dict,
        "source_path": CoordinatePath.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.destination, IndexSpan),
            "Expected derivation destination span.",
        )
        require(
            isinstance(self.source_path, CoordinatePath),
            "Expected derivation source path.",
        )
        _text(self.source_id, "Derivation source identity")
        _choice(
            self.rule,
            {
                "copy",
                "complement",
                "dna_coding_to_rna.v1",
                "rna_editing.v1",
                "translation_codon.v1",
            },
            "derivation rule",
        )
        require(
            self.destination.length > 0
            and self.source_path.length
            == self.destination.length
            * (3 if self.rule == "translation_codon.v1" else 1),
            "Derivation cardinality must match its explicit residue rule.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ConsumedSegment(_MoleculeRecord):
    """An explicit event-local termination correspondence, never a dose count."""

    source_id: str
    source_path: CoordinatePath
    reason: str
    schema_version: ClassVar[str] = "biocompiler.circuit_consumed_segment.v0.1"
    _decoders: ClassVar[dict] = {"source_path": CoordinatePath.from_dict}

    def __post_init__(self):
        _text(self.source_id, "Consumed source identity")
        require(
            isinstance(self.source_path, CoordinatePath),
            "Expected consumed coordinates.",
        )
        _choice(self.reason, {"terminal_stop"}, "consumption reason")
        require(
            self.source_path.length == 3 and self.source_path.strand == "+",
            "Terminal stop requires three forward source bases.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ConstructedValue(_MoleculeRecord):
    id: str
    space: CoordinateSpace
    sequence: str
    chemistry: MoleculeChemistry
    features: tuple[MoleculeFeature, ...]
    segments: tuple[DerivedSegment, ...]
    step_id: str
    sequence_extent: str = "complete"
    consumed: tuple[ConsumedSegment, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_constructed_value.v0.1"
    _decoders: ClassVar[dict] = {
        "space": CoordinateSpace.from_dict,
        "chemistry": MoleculeChemistry.from_dict,
        "features": _decode_records(MoleculeFeature, 256),
        "segments": _decode_records(DerivedSegment, 128),
        "consumed": _decode_records(ConsumedSegment, 16),
    }

    def __post_init__(self):
        _text(self.id, "Constructed value identity")
        _text(self.step_id, "Producing step identity")
        require(
            isinstance(self.space, CoordinateSpace),
            "Expected constructed coordinate frame.",
        )
        require(
            isinstance(self.sequence, str) and 0 < len(self.sequence) <= MAX_RESIDUES,
            "Constructed spelling exceeds supported length.",
        )
        require(
            len(self.sequence) == self.space.length
            and set(self.sequence) <= CANONICAL_ALPHABETS[self.space.alphabet],
            "Constructed spelling and frame disagree.",
        )
        _choice(self.sequence_extent, {"complete", "exact_core"}, "constructed extent")
        require(
            isinstance(self.chemistry, MoleculeChemistry),
            "Expected explicit constructed chemistry.",
        )
        self.chemistry.validate_for(self.space, self.sequence, self.sequence_extent)
        object.__setattr__(
            self,
            "features",
            _records(self.features, MoleculeFeature, 256, "constructed features"),
        )
        for feature in self.features:
            if feature.path is not None:
                feature.path.validate_for(self.space)
        require(
            isinstance(self.segments, (tuple, list)) and 0 < len(self.segments) <= 128,
            "Expected bounded nonempty derivation partition.",
        )
        require(
            all(isinstance(segment, DerivedSegment) for segment in self.segments),
            "Expected typed derivation segments.",
        )
        segments = tuple(
            DerivedSegment.from_dict(segment.to_dict()) for segment in self.segments
        )
        cursor = 0
        for segment in segments:
            require(
                segment.destination.start == cursor,
                "Derivation partition contains a gap or overlap.",
            )
            cursor = segment.destination.end
        require(
            cursor == self.space.length, "Derivation must cover every proposed residue."
        )
        object.__setattr__(self, "segments", segments)
        require(
            isinstance(self.consumed, (tuple, list))
            and len(self.consumed) <= 16
            and all(isinstance(item, ConsumedSegment) for item in self.consumed),
            "Invalid consumed-source inventory.",
        )
        consumed = tuple(
            ConsumedSegment.from_dict(item.to_dict()) for item in self.consumed
        )
        require(
            len({item.fingerprint for item in consumed}) == len(consumed),
            "Duplicate consumed-source correspondence.",
        )
        object.__setattr__(self, "consumed", consumed)
        self._check_resources()


@dataclass(frozen=True)
class ConstructionCandidate(_MoleculeRecord):
    request_fingerprint: str
    values: tuple[ConstructedValue, ...]
    bundle: CircuitMoleculeSet | None
    missing_members: tuple[str, ...]
    diagnostics: tuple[str, ...]
    experimental_amounts: tuple[ExperimentalAmount, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_construction_candidate.v0.1"
    _decoders: ClassVar[dict] = {
        "values": _decode_records(ConstructedValue, 256),
        "bundle": _optional(CircuitMoleculeSet),
        "experimental_amounts": _decode_records(ExperimentalAmount, 128),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Construction request")
        object.__setattr__(
            self,
            "values",
            _records(self.values, ConstructedValue, 256, "constructed values"),
        )
        require(
            sum(value.space.length for value in self.values) <= MAX_RESIDUES,
            "Cumulative constructed residue limit exceeded.",
        )
        require(
            len({value.space.id for value in self.values}) == len(self.values),
            "Duplicate constructed coordinate frames.",
        )
        require(
            self.bundle is None or isinstance(self.bundle, CircuitMoleculeSet),
            "Expected proposed molecule set or explicit missing set.",
        )
        if self.bundle is not None:
            object.__setattr__(
                self, "bundle", CircuitMoleculeSet.from_dict(self.bundle.to_dict())
            )
        object.__setattr__(
            self,
            "experimental_amounts",
            _records(
                self.experimental_amounts,
                ExperimentalAmount,
                128,
                "constructed amounts",
            ),
        )
        if self.bundle is None:
            require(
                not self.experimental_amounts,
                "Missing molecule set cannot bind experimental amounts.",
            )
        else:
            CircuitMoleculeRecord(self.bundle, self.experimental_amounts, {})
        for key, maximum in (("missing_members", 256), ("diagnostics", 1024)):
            values = getattr(self, key)
            require(
                isinstance(values, (tuple, list)) and len(values) <= maximum,
                f"Invalid construction {key} inventory.",
            )
            for value in values:
                _text(value, key, maximum=16_384 if key == "diagnostics" else 4096)
            require(len(values) == len(set(values)), f"Duplicate construction {key}.")
            object.__setattr__(self, key, tuple(sorted(values)))
        self._check_resources()
