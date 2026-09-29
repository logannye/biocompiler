"""Records for distinguishing kinds of support and unresolved obligations."""

from dataclasses import dataclass
from enum import StrEnum


class EvidenceKind(StrEnum):
    EXACT = "exact"
    MODEL_CONDITIONAL = "model_conditional"
    EMPIRICAL = "empirical"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Obligation:
    """A claim awaiting an independent check, not a certificate of correctness."""

    requirement_id: str
    description: str
    evidence_kind: EvidenceKind = EvidenceKind.UNRESOLVED
    evidence_refs: tuple[str, ...] = ()
