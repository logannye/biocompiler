"""Typed lowering interfaces and preservation records.

Future pass records additionally track observation mappings, context/assumptions,
changed properties and invalidated analyses. A source link alone is not proof of
refinement; required responses must be checked as well as permitted behavior.
See docs/toolchain-contracts.md for downstream obligations.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
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
    observation_map: Mapping[str, Any] = field(default_factory=dict)
    search_status: str = "candidate"


class CompilerPass(Protocol[InputT, OutputT]):
    """Implementations must expose and discharge their preservation obligations."""

    name: str
    input_stage: Stage
    output_stage: Stage

    def run(self, module: InputT, *, target: TargetContext) -> PassResult[OutputT]:
        """Return a candidate transformation with explicit provenance and obligations."""
        ...
