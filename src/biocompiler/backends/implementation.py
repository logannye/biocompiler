"""Emit exact supplied precursor segments; independent acceptance follows."""

import hashlib

from biocompiler.ir.implementation import ImplementationConstruct, ImplementationRequest
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange

EMITTER_VERSION = "biocompiler.implementation_emitter.v0.1"


def emit_implementation(request, construct):
    """Materialize the nominal RNA without granting any functional claim."""
    require(
        isinstance(request, ImplementationRequest)
        and isinstance(construct, ImplementationConstruct),
        "Expected original request and derived implementation construct.",
    )
    require(
        request.target.payload_format is PayloadFormat.RNA,
        "Implementation emission supports explicit RNA only.",
    )
    require(
        not request.constraints.require_implementation_complete,
        "This structural family cannot satisfy complete therapeutic implementation.",
    )
    require(
        construct.request_fingerprint == request.fingerprint,
        "Construct differs from original request authority.",
    )
    architecture = next(
        (x for x in request.library.architectures if x.id == construct.architecture_id),
        None,
    )
    require(
        architecture is not None, "Construct architecture is missing from authority."
    )
    by_id = {x.id: x for x in architecture.authorities}
    slices = []
    cursor = 0
    for placement in construct.placements:
        source = by_id.get(placement.authority_id)
        require(
            source is not None
            and placement.authority_fingerprint == source.fingerprint,
            "Encoding source differs from pinned authority.",
        )
        require(
            placement.source_range == SequenceRange(0, len(source.sequence))
            and placement.molecule_range
            == SequenceRange(cursor, cursor + len(source.sequence)),
            "Encoding must preserve contiguous whole supplied segments.",
        )
        slices.append(source.sequence)
        cursor += len(source.sequence)
    sequence = "".join(slices)
    front = len(architecture.five_prime_utr.sequence)
    cds_end = front + sum(len(x.sequence.sequence) for x in architecture.segments)
    back_end = cds_end + len(architecture.three_prime_utr.sequence)
    locator = "implementation-request:" + request.fingerprint
    regions = [
        PayloadRegion(
            "five_prime_utr",
            "five_prime_utr",
            SequenceRange(0, front),
            SequenceRange(0, front),
            architecture.five_prime_utr.source_locator,
        ),
        PayloadRegion(
            "cds",
            "cds",
            SequenceRange(front, cds_end),
            SequenceRange(0, cds_end - front),
            locator + "#composite-cds",
            construct.precursor_protein,
        ),
        PayloadRegion(
            "three_prime_utr",
            "three_prime_utr",
            SequenceRange(cds_end, back_end),
            SequenceRange(0, back_end - cds_end),
            architecture.three_prime_utr.source_locator,
        ),
    ]
    if architecture.poly_a is not None:
        regions.append(
            PayloadRegion(
                "poly_a",
                "poly_a",
                SequenceRange(back_end, cursor),
                SequenceRange(0, cursor - back_end),
                architecture.poly_a.source_locator,
            )
        )
    return PayloadMolecule(
        construct.molecule_id,
        "mature_linear_rna",
        "RNA",
        sequence,
        hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        SequenceRange(0, len(sequence)),
        "linear",
        "single",
        tuple(regions),
        construct.features,
        locator,
    )
