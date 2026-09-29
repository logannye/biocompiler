"""Central sequence-coordinate convention: normalized symbols, not raw text.

Intervals are zero based and half open on the reference's declared 5-prime to
3-prime spelling. Orientation is separate: reverse means reverse-complement
traversal for DNA/RNA, without reversing coordinates. Normalization remains the
pinned reference record's policy; this module never transforms or emits bases.
"""

from dataclasses import dataclass
from typing import ClassVar

from cellweave.ir.serialization import JsonArtifact, fields, require

COORDINATE_CONVENTION = "zero-based-half-open-reference-5prime-to-3prime.v1"
ORIENTATIONS = frozenset({"forward", "reverse"})


@dataclass(frozen=True)
class SequenceRange(JsonArtifact):
    """A normalized-symbol interval; empty intervals can mark direct junctions."""

    start: int
    end: int
    schema_version: ClassVar[str] = "cellweave.sequence_range.v0.1"

    def __post_init__(self):
        require(
            type(self.start) is int
            and type(self.end) is int
            and 0 <= self.start <= self.end,
            "Sequence coordinates require integers with 0 <= start <= end.",
        )

    @property
    def length(self) -> int:
        return self.end - self.start

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "convention": COORDINATE_CONVENTION,
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, {"schema_version", "convention", "start", "end"}, cls.__name__)
        require(
            data["schema_version"] == cls.schema_version
            and data["convention"] == COORDINATE_CONVENTION,
            "Unsupported sequence coordinate schema/convention.",
        )
        return cls(data["start"], data["end"])
