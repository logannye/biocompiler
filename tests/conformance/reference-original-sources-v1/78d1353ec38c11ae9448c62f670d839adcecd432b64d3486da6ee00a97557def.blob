"""Explicit bounded coordinate frames and ordered residue paths.

Coordinates are zero based and half open in a nominated reference frame. A path
retains the supplied segment order; its strand controls traversal within each
segment. Consequently neither sorting segments nor reversing a segment tuple is
an implicit operation. This permits discontinuous and circular annotations
without asserting a processing mechanism or transforming molecular symbols.

Overlapping independent features are valid. Only self-overlap within one path
is rejected. A single empty span records an explicit boundary coordinate; an
assembly partition must separately enforce positive coverage of its product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.molecule_records import (
    MAX_RESIDUES,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_SPANS = 128
MAX_MATERIALIZED_POSITIONS = 100_000
DEFAULT_POSITION_LIMIT = 4_096
ALPHABETS = frozenset({"DNA", "RNA", "protein"})
TOPOLOGIES = frozenset({"linear", "circular"})
AXES = frozenset({"5prime_to_3prime", "N_to_C"})
STRANDS = frozenset({"+", "-"})


@dataclass(frozen=True)
class CoordinateSpace(_MoleculeRecord):
    """One declared, nonempty molecular reference frame with a retained origin.

    IDs are nominal references; the containing molecule inventory must ensure
    they are unique and retain the complete authoritative coordinate record.
    Circular frames preserve their nominated origin exactly as supplied.
    """

    id: str
    alphabet: str
    length: int
    topology: str
    axis: str
    schema_version: ClassVar[str] = "biocompiler.molecule_coordinate_space.v0.1"

    def __post_init__(self):
        _text(self.id, "Coordinate space identity")
        _choice(self.alphabet, ALPHABETS, "coordinate alphabet")
        _choice(self.topology, TOPOLOGIES, "coordinate topology")
        _choice(self.axis, AXES, "coordinate axis")
        require(
            type(self.length) is int and 1 <= self.length <= MAX_RESIDUES,
            "Coordinate space length must be an integer within the residue limit.",
        )
        require(
            self.axis
            == ("N_to_C" if self.alphabet == "protein" else "5prime_to_3prime"),
            "Coordinate axis must preserve its declared molecular alphabet.",
        )
        self._check_resources()


@dataclass(frozen=True)
class IndexSpan(_MoleculeRecord):
    """A half-open interval, including a single explicitly nominated boundary."""

    start: int
    end: int
    schema_version: ClassVar[str] = "biocompiler.molecule_index_span.v0.1"

    def __post_init__(self):
        require(
            type(self.start) is int
            and type(self.end) is int
            and 0 <= self.start <= self.end <= MAX_RESIDUES,
            "Index span requires integer coordinates 0 <= start <= end <= residue limit.",
        )
        self._check_resources()

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class CoordinatePath(_MoleculeRecord):
    """An ordered selection of disjoint spans in one declared reference frame.

    For example, an origin-crossing path on a length-10 circle can use spans
    (8, 10), (0, 3) with '+'; the opposite traversal uses (0, 3), (8, 10) with
    '-'. Neither wraparound nor reverse-complement symbol conversion is inferred.
    Discontinuous paths may skip or reorder segments, without claiming a splice,
    deletion, rearrangement or any other physical processing operation.
    """

    space_id: str
    spans: tuple[IndexSpan, ...]
    strand: str
    schema_version: ClassVar[str] = "biocompiler.molecule_coordinate_path.v0.1"
    _decoders: ClassVar[dict] = {"spans": _decode_records(IndexSpan, MAX_SPANS)}

    def __post_init__(self):
        _text(self.space_id, "Path coordinate-space identity")
        _choice(self.strand, STRANDS, "path strand")
        require(
            isinstance(self.spans, (tuple, list)) and 1 <= len(self.spans) <= MAX_SPANS,
            "Coordinate path requires a bounded, nonempty span inventory.",
        )
        require(
            all(isinstance(span, IndexSpan) for span in self.spans),
            "Coordinate paths require IndexSpan records.",
        )
        spans = tuple(IndexSpan.from_dict(span.to_dict()) for span in self.spans)
        require(
            len(spans) == 1 or all(span.length > 0 for span in spans),
            "A boundary annotation must be a single empty span, not a mixed residue path.",
        )
        ordered = sorted(spans, key=lambda span: (span.start, span.end))
        require(
            all(left.end <= right.start for left, right in zip(ordered, ordered[1:])),
            "A coordinate path cannot overlap itself or repeat residue positions.",
        )
        object.__setattr__(self, "spans", spans)
        self._check_resources()

    @property
    def length(self) -> int:
        """Number of selected residues; boundary annotations have zero length."""
        return sum(span.length for span in self.spans)

    def validate_for(self, space: CoordinateSpace) -> CoordinatePath:
        """Check nominal identity, bounds and alphabet without changing traversal."""
        require(isinstance(space, CoordinateSpace), "Expected a coordinate space.")
        require(self.space_id == space.id, "Path names a different coordinate space.")
        require(
            all(span.end <= space.length for span in self.spans),
            "Coordinate path extends beyond its declared coordinate space.",
        )
        require(
            space.alphabet != "protein" or self.strand == "+",
            "Protein coordinate paths must retain N-to-C traversal with '+' strand.",
        )
        return self

    def positions(
        self, space: CoordinateSpace, *, limit: int = DEFAULT_POSITION_LIMIT
    ) -> tuple[int, ...]:
        """Materialize a small index view; this does not emit molecular symbols."""
        require(
            type(limit) is int and 0 <= limit <= MAX_MATERIALIZED_POSITIONS,
            "Position limit must be an integer from 0 to 100000.",
        )
        self.validate_for(space)
        require(
            self.length <= limit, "Coordinate path exceeds the position-view limit."
        )
        if self.strand == "+":
            return tuple(
                position
                for span in self.spans
                for position in range(span.start, span.end)
            )
        return tuple(
            position
            for span in self.spans
            for position in range(span.end - 1, span.start - 1, -1)
        )
