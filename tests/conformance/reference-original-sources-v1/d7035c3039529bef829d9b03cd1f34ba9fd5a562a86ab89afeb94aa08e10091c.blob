"""Exact DNA-CDS reference emission, distinct from complete DNA payloads."""

from biocompiler.backends.reference import emit_reference_sequence
from biocompiler.ir.construct import ConstructRequest
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import PayloadFormat


def emit_dna_cds(request, construct, registry, manifests):
    """Emit the independently selected DNA record through its checked construct."""
    require(
        isinstance(request, ConstructRequest)
        and request.target.payload_format is PayloadFormat.DNA,
        "The DNA-CDS backend requires an explicit DNA target.",
    )
    return emit_reference_sequence(request, construct, registry, manifests)
