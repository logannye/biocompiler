"""Exact RNA-CDS reference emission from its own pinned RNA source record."""

from cellweave.backends.reference import emit_reference_sequence
from cellweave.ir.construct import ConstructRequest
from cellweave.ir.serialization import require
from cellweave.semantics.context import PayloadFormat


def emit_rna_cds(request, construct, registry, manifests):
    """Emit selected coding RNA without inferring cap, UTRs, modifications or tail."""
    require(
        isinstance(request, ConstructRequest)
        and request.target.payload_format is PayloadFormat.RNA,
        "The RNA-CDS backend requires an explicit RNA target.",
    )
    return emit_reference_sequence(request, construct, registry, manifests)
