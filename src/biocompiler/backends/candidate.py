"""Emit an unchecked nominal RNA candidate without changing its source purpose."""

import hashlib

from biocompiler.ir.candidate import CandidateRequest
from biocompiler.ir.candidate_selection import CandidateLayout
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.molecular_design import structural_rna_diagnostics

EMITTER_VERSION = "biocompiler.candidate_emitter.v0.1"


def emit_candidate(
    request: CandidateRequest, layout: CandidateLayout
) -> PayloadMolecule:
    """Spell supplied source regions exactly; independent verification follows.

    No therapeutic compilation is admitted, and no source target is replaced by
    a generic software target. A whole structural molecule can still be a partial
    implementation of the authored behavior; the enclosing artifact records that.
    """
    require(
        isinstance(request, CandidateRequest), "Expected candidate source authority."
    )
    require(isinstance(layout, CandidateLayout), "Expected automatic candidate layout.")
    request = CandidateRequest.from_dict(request.to_dict())
    layout = CandidateLayout.from_dict(layout.to_dict())
    require(
        layout.request_fingerprint == request.fingerprint
        and layout.target == request.target,
        "Candidate layout differs from source authority or original target.",
    )
    require(
        request.target is not None
        and request.target.payload_format is PayloadFormat.RNA,
        "Candidate emission supports RNA only; no implicit conversion.",
    )
    require(
        not structural_rna_diagnostics(layout),
        "Candidate emission requires complete supported molecular structure.",
    )
    fragments = {item.id: item for item in layout.fragments}
    sequences, regions = [], []
    for placement in layout.placements:
        fragment = fragments[placement.fragment_id]
        require(
            placement.source_range == SequenceRange(0, len(fragment.sequence)),
            "Candidate emission requires whole supplied fragments.",
        )
        sequences.append(fragment.sequence)
        regions.append(
            PayloadRegion(
                id=placement.region_id,
                kind=placement.kind,
                range=placement.molecule_range,
                source_range=placement.source_range,
                source_locator=fragment.source_locator,
                protein_sequence=placement.protein_sequence,
                orientation=placement.orientation,
                reading_frame=placement.reading_frame,
            )
        )
    sequence = "".join(sequences)
    return PayloadMolecule(
        id=layout.molecule_id,
        artifact_class="mature_linear_rna",
        alphabet="RNA",
        sequence=sequence,
        sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        boundaries=SequenceRange(0, len(sequence)),
        topology="linear",
        strandedness="single",
        regions=tuple(regions),
        features=layout.features,
        source_locator="candidate-request:" + request.fingerprint,
        unknown_features=layout.unknown_features,
    )
