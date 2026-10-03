"""Literal multi-region RNA emission, without optimization or conversion."""

import hashlib

from biocompiler.ir.molecular_design import (
    SOURCE_LOCATOR_PREFIX,
    MolecularDesignArtifact,
    MolecularDesignConstruct,
    MolecularDesignRequest,
)
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion
from biocompiler.ir.serialization import require
from biocompiler.verification.admission import require_software_use
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange

EMITTER_VERSION = "biocompiler.molecular_design_emitter.v0.1"


def emit_molecular_design(
    request: MolecularDesignRequest, construct: MolecularDesignConstruct
) -> MolecularDesignArtifact:
    """Return an unchecked candidate from literal source slices and typed layout.

    Source coordinates index the supplied fragment, not a pre-existing whole
    molecule. The independent checker reconciles every emitted base, source map,
    chemistry declaration and translated CDS against the separate request.
    """
    require(
        isinstance(request, MolecularDesignRequest),
        "Expected a molecular design request.",
    )
    require(
        isinstance(construct, MolecularDesignConstruct),
        "Expected a molecular design construct.",
    )
    require_software_use(request.target, boundary="selection")
    require(
        request.target.payload_format is PayloadFormat.RNA,
        "This emitter supports RNA only; no alphabet conversion is implemented.",
    )
    require(
        construct.request_fingerprint == request.fingerprint
        and construct.molecule_id == request.molecule_id
        and construct.placements == request.placements
        and construct.features == request.features
        and construct.unknown_features == request.unknown_features,
        "Construct differs from the independently authored design layout.",
    )
    require(
        tuple(x.kind for x in construct.placements)
        in (
            ("five_prime_utr", "cds", "three_prime_utr"),
            ("five_prime_utr", "cds", "three_prime_utr", "poly_a"),
        ),
        "Emission requires the supported single-CDS mature linear RNA region order.",
    )
    fragments = {fragment.id: fragment for fragment in request.fragments}
    sequence_parts = []
    regions = []
    cursor = 0
    for placement in construct.placements:
        fragment = fragments.get(placement.fragment_id)
        require(fragment is not None, "Placed fragment is missing from authority.")
        require(
            fragment.fingerprint == placement.fragment_fingerprint,
            "Placed fragment pin differs from authority.",
        )
        require(
            fragment.alphabet == "RNA", "RNA emission cannot convert a DNA fragment."
        )
        require(
            placement.orientation == "forward" and placement.reading_frame == 0,
            "Only forward frame-zero emission is supported.",
        )
        require(
            0 < placement.source_range.length
            and placement.source_range.end <= len(fragment.sequence)
            and placement.molecule_range.start == cursor
            and placement.molecule_range.length == placement.source_range.length,
            "Fragment placement must cover the molecule once without gaps or clipping.",
        )
        sequence_parts.append(
            fragment.sequence[placement.source_range.start : placement.source_range.end]
        )
        regions.append(
            PayloadRegion(
                placement.region_id,
                placement.kind,
                placement.molecule_range,
                placement.source_range,
                fragment.source_locator,
                placement.protein_sequence,
                placement.orientation,
                placement.reading_frame,
            )
        )
        cursor = placement.molecule_range.end
    sequence = "".join(sequence_parts)
    molecule = PayloadMolecule(
        id=construct.molecule_id,
        artifact_class="mature_linear_rna",
        alphabet="RNA",
        sequence=sequence,
        sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        boundaries=SequenceRange(0, len(sequence)),
        topology="linear",
        strandedness="single",
        regions=tuple(regions),
        features=construct.features,
        source_locator=SOURCE_LOCATOR_PREFIX + request.id,
        unknown_features=construct.unknown_features,
    )
    return MolecularDesignArtifact(
        request.fingerprint, construct.fingerprint, molecule, construct.placements
    )
