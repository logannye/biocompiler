"""Exact pinned nucleotide spelling through a checked whole-CDS construct.

The emitter returns an unchecked molecular artifact. Independent molecular
acceptance must reconcile it with the retained DNA/RNA/protein expectations.
No optimization, inferred chemistry or DNA-to-RNA conversion is performed.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib

from biocompiler.ir.construct import ConstructCandidate, ConstructRequest
from biocompiler.ir.molecular import (
    MolecularArtifact,
    MolecularRecord,
    reference_feature_statuses,
)
from biocompiler.ir.serialization import require
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.references import ReferenceManifest
from biocompiler.verification.construct import check_construct

EMITTER_VERSION = "biocompiler.reference_sequence_emitter.v0.2"


def emit_reference_sequence(
    request: ConstructRequest,
    construct: ConstructCandidate,
    registry: ComponentRegistry,
    manifests: Mapping[str, ReferenceManifest],
) -> MolecularArtifact:
    """Emit the selected source's own DNA or RNA spelling, never a converted copy.

    Manifests must first be loaded with independent expected fingerprints and
    retained evidence checks. The current M5 construct is independently checked
    here; this does not certify the new molecular output.
    """
    require(isinstance(request, ConstructRequest), "Expected a construct request.")
    require(
        isinstance(construct, ConstructCandidate), "Expected a construct candidate."
    )
    checked = check_construct(request, construct, registry, manifests)
    require(
        checked.passed,
        "Exact reference emission requires a currently passing construct check: "
        + "; ".join(item.code for item in checked.diagnostics),
    )
    # M5's supported profile establishes one whole, forward, frame-zero CDS.
    # Resolve its own selected record after checking the current authority; RNA
    # therefore comes from SEQ3 even though DNA/RNA consistency is also checked.
    selection = request.references[0].selection
    reference = manifests[selection.manifest.id].record(selection.reference.id)
    molecule = construct.molecules[0]
    placement = construct.placements[0]
    sequence = reference.sequence
    record = MolecularRecord(
        id=molecule.id,
        instance_id=placement.instance_id,
        molecule_id=molecule.id,
        alphabet=reference.alphabet,
        artifact_class=reference.artifact_class,
        sequence=sequence,
        sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        component=placement.component,
        reference_selection=selection,
        source_range=placement.source_range,
        molecule_range=placement.molecule_range,
        features=construct.features,
        feature_statuses=reference_feature_statuses(reference),
        orientation=placement.orientation,
        reading_frame=placement.reading_frame,
        completeness=reference.completeness,
        unknown_features=reference.unknown_features,
        evidence_relationships=reference.evidence_relationships,
        requirement_ids=placement.requirement_ids,
        source=placement.source,
    )
    return MolecularArtifact(
        request_fingerprint=request.fingerprint,
        construct_fingerprint=construct.fingerprint,
        layout_fingerprint=construct.layout_fingerprint,
        registry_lock=construct.registry_lock,
        profile=reference.alphabet + "-CDS",
        records=(record,),
        source_request_fingerprint=request.source_request_fingerprint,
    )
