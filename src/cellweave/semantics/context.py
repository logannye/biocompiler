"""Explicit target references; a reference is not a validated biological context."""

from dataclasses import dataclass
from enum import StrEnum


class PayloadFormat(StrEnum):
    DNA = "DNA"
    RNA = "RNA"


@dataclass(frozen=True)
class TargetContext:
    """Identify the versioned host assumptions required by a build."""

    context_id: str
    context_version: str
    payload_format: PayloadFormat
