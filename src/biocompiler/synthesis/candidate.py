"""Bounded source-product selection and automatic nominal RNA layout.

This producer proposes coding cassettes from supplied parts. Conditional control
and secretion remain source requirements, never inferred from sequence labels.
"""

from dataclasses import dataclass

from biocompiler.compiler.candidate_requirements import lower_candidate_requirements
from biocompiler.ir.candidate import CandidateRequest, CandidateRequirements
from biocompiler.ir.candidate_selection import (
    REJECTION_MESSAGES,
    CandidateAlternative,
    CandidateLayout,
    CandidateRejection,
    CandidateSelection,
)
from biocompiler.ir.molecular_design import FragmentPlacement, SequenceFragment
from biocompiler.ir.payload import PayloadFeature
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.molecular_design import structural_rna_diagnostics

GENERATOR_VERSION = "biocompiler.candidate_generator.v0.1"


@dataclass(frozen=True)
class _Recipe:
    fragments: tuple[SequenceFragment, ...]
    placements: tuple[FragmentPlacement, ...]
    features: tuple[PayloadFeature, ...]
    unknown_features: tuple[str, ...] = ()


def _recipe(library, architecture, binding):
    parts = {part.id: part for part in library.parts}
    identities = [
        architecture.five_prime_part_id,
        binding.cds_part_id,
        architecture.three_prime_part_id,
    ]
    if architecture.poly_a_part_id is not None:
        identities.append(architecture.poly_a_part_id)
    fragments, placements = [], []
    cursor = 0
    for identity in identities:
        part = parts[identity]
        fragment = part.fragment
        length = len(fragment.sequence)
        fragments.append(fragment)
        placements.append(
            FragmentPlacement(
                region_id=part.kind,
                kind=part.kind,
                fragment_id=fragment.id,
                fragment_fingerprint=fragment.fingerprint,
                source_range=SequenceRange(0, length),
                molecule_range=SequenceRange(cursor, cursor + length),
                protein_sequence=binding.protein_sequence
                if part.kind == "cds"
                else None,
            )
        )
        cursor += length
    return _Recipe(tuple(fragments), tuple(placements), architecture.features)


def _authority(request, requirements):
    require(
        isinstance(request, CandidateRequest),
        "Expected complete candidate request authority.",
    )
    require(
        isinstance(requirements, CandidateRequirements),
        "Expected lowered candidate requirements.",
    )
    request = CandidateRequest.from_dict(request.to_dict())
    requirements = CandidateRequirements.from_dict(requirements.to_dict())
    require(
        requirements == lower_candidate_requirements(request),
        "Candidate requirements differ from complete source authority.",
    )
    return request, requirements


def select_candidate(
    request: CandidateRequest, requirements: CandidateRequirements
) -> CandidateSelection:
    """Evaluate every supplied product/architecture combination before ranking.

    The fixed library bound limits enumeration. Exhaustion applies only to this
    supplied family, never to all molecular designs or biological feasibility.
    """
    request, requirements = _authority(request, requirements)
    bindings = tuple(
        item
        for item in request.library.products
        if item.product == requirements.product
    )
    alternatives = []
    constraints = request.constraints
    for architecture in sorted(request.library.architectures, key=lambda item: item.id):
        for binding in sorted(bindings, key=lambda item: item.cds_part_id):
            recipe = _recipe(request.library, architecture, binding)
            length = sum(len(fragment.sequence) for fragment in recipe.fragments)
            rejections = []

            def reject(code, status="fail"):
                rejections.append(
                    CandidateRejection(status, code, REJECTION_MESSAGES[code])
                )

            if (
                constraints.allowed_architecture_ids
                and architecture.id not in constraints.allowed_architecture_ids
            ):
                reject("architecture_not_allowed")
            if (
                constraints.allowed_cds_part_ids
                and binding.cds_part_id not in constraints.allowed_cds_part_ids
            ):
                reject("cds_part_not_allowed")
            if constraints.max_length is not None and length > constraints.max_length:
                reject("max_length_exceeded")
            if (
                request.target is None
                or request.target.payload_format is not PayloadFormat.RNA
            ):
                reject("unsupported_modality", "unsupported")
            rejections.extend(
                CandidateRejection(item.status, item.code, item.message)
                for item in structural_rna_diagnostics(recipe)
            )
            alternatives.append(
                CandidateAlternative(
                    architecture.id, binding.cds_part_id, length, tuple(rejections)
                )
            )
    eligible = [item for item in alternatives if item.status == "eligible"]
    if constraints.preference == "shortest":
        eligible.sort(
            key=lambda item: (
                item.sequence_length,
                item.architecture_id,
                item.cds_part_id,
            )
        )
    else:
        eligible.sort(key=lambda item: (item.architecture_id, item.cds_part_id))
    diagnostics = (
        ()
        if eligible
        else ("product_binding_unavailable",)
        if not bindings
        else ("bounded_candidates_exhausted",)
    )
    return CandidateSelection(
        request.fingerprint,
        requirements.fingerprint,
        tuple(alternatives),
        eligible[0].id if eligible else None,
        diagnostics,
    )


def derive_candidate_layout(
    request: CandidateRequest,
    requirements: CandidateRequirements,
    selection: CandidateSelection,
) -> CandidateLayout:
    """Compute full-fragment coordinates from a freshly checked bounded choice.

    The caller never supplies nucleotide placements. Source target identity is
    retained verbatim, including human targets; this proposal grants no use gate.
    """
    request, requirements = _authority(request, requirements)
    require(
        isinstance(selection, CandidateSelection), "Expected a candidate selection."
    )
    selection = CandidateSelection.from_dict(selection.to_dict())
    require(
        selection == select_candidate(request, requirements),
        "Candidate selection differs from current bounded source/library evaluation.",
    )
    selected = selection.selected
    require(
        selected is not None,
        "The supplied bounded design family has no eligible candidate.",
    )
    architecture = next(
        item
        for item in request.library.architectures
        if item.id == selected.architecture_id
    )
    binding = next(
        item
        for item in request.library.products
        if item.product == requirements.product
        and item.cds_part_id == selected.cds_part_id
    )
    recipe = _recipe(request.library, architecture, binding)
    require(
        not structural_rna_diagnostics(recipe),
        "Selected candidate has unresolved or invalid molecular structure.",
    )
    return CandidateLayout(
        request_fingerprint=request.fingerprint,
        requirements_fingerprint=requirements.fingerprint,
        selection_fingerprint=selection.fingerprint,
        selected_alternative_id=selected.id,
        architecture_id=selected.architecture_id,
        cds_part_id=selected.cds_part_id,
        molecule_id=request.build_request.intent.name + ".candidate",
        target=request.target,
        fragments=recipe.fragments,
        placements=recipe.placements,
        features=recipe.features,
    )
