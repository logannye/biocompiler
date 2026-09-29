"""Typed interface for future lowering passes and their preservation records."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from cellweave.artifacts.provenance import SourceLink
from cellweave.ir.stages import Stage
from cellweave.semantics.context import TargetContext
from cellweave.verification.evidence import Obligation

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class PassResult(Generic[OutputT]):
    """A transformed IR with claims to check; construction does not verify them."""

    output: OutputT
    obligations: tuple[Obligation, ...]
    source_links: tuple[SourceLink, ...]


class CompilerPass(Protocol[InputT, OutputT]):
    """Implementations must expose and discharge their preservation obligations."""

    name: str
    input_stage: Stage
    output_stage: Stage

    def run(self, module: InputT, *, target: TargetContext) -> PassResult[OutputT]:
        """Return a candidate transformation with explicit provenance and obligations."""
        ...
