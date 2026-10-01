"""Propose bounded precursor plans and encodings from explicit authority.

All provider and processing declarations remain assumptions. Acceptance is the
responsibility of the separately implemented verification module.
"""

from dataclasses import dataclass
import hashlib

from biocompiler.compiler.implementation_requirements import (
    analyze_implementation_requirements,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.implementation import (
    DEPENDENCY_COMPARTMENTS,
    PLAN_EDGES,
    PLAN_ROLES,
    ImplementationAlternative,
    ImplementationConstruct,
    ImplementationDependency,
    ImplementationEdge,
    ImplementationPlacement,
    ImplementationPlan,
    ImplementationRejection,
    ImplementationRequest,
    ImplementationRole,
    ImplementationSelection,
)
from biocompiler.ir.molecular_design import FragmentPlacement
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.registry.references import translate_cds
from biocompiler.semantics.context import HumanTargetContext, PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.molecular_design import structural_rna_diagnostics

GENERATOR_VERSION = "biocompiler.implementation_generator.v0.1"


def _sha(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class _StructuralFragment:
    """Derived checker input, never a new biological source or fixture record."""

    id: str
    sequence: str
    sequence_sha256: str
    fingerprint: str
    alphabet: str = "RNA"


@dataclass(frozen=True)
class _StructuralRecipe:
    fragments: tuple
    placements: tuple
    features: tuple
    unknown_features: tuple = ()


def _structural_recipe(architecture):
    coding = "".join(x.sequence.sequence for x in architecture.segments)
    items = [
        (
            "five_prime_utr",
            architecture.five_prime_utr.sequence,
            architecture.five_prime_utr.fingerprint,
        ),
        ("cds", coding, fingerprint([x.fingerprint for x in architecture.segments])),
        (
            "three_prime_utr",
            architecture.three_prime_utr.sequence,
            architecture.three_prime_utr.fingerprint,
        ),
    ]
    if architecture.poly_a is not None:
        items.append(
            ("poly_a", architecture.poly_a.sequence, architecture.poly_a.fingerprint)
        )
    cursor, fragments, placements = 0, [], []
    for kind, sequence, pin in items:
        fragment = _StructuralFragment(kind, sequence, _sha(sequence), pin)
        fragments.append(fragment)
        placements.append(
            FragmentPlacement(
                kind,
                kind,
                kind,
                pin,
                SequenceRange(0, len(sequence)),
                SequenceRange(cursor, cursor + len(sequence)),
                architecture.precursor_protein if kind == "cds" else None,
            )
        )
        cursor += len(sequence)
    return _StructuralRecipe(tuple(fragments), tuple(placements), architecture.features)


def _authority(request, requirements):
    require(
        isinstance(request, ImplementationRequest),
        "Expected complete implementation request.",
    )
    request = ImplementationRequest.from_dict(request.to_dict())
    require(
        requirements == analyze_implementation_requirements(request.source),
        "Requirements differ from original source authority.",
    )
    return request


def select_implementation(request, requirements):
    """Enumerate exact supplied family options before ranking eligible structures."""
    request = _authority(request, requirements)
    if requirements.supported_profile is None or len(requirements.products) != 1:
        return ImplementationSelection(
            request.fingerprint,
            requirements.fingerprint,
            (),
            None,
            ("unsupported_source_profile",),
        )
    product = requirements.products[0]
    architectures = sorted(
        (x for x in request.library.architectures if x.product == product.product),
        key=lambda x: x.id,
    )
    alternatives = []
    for architecture in architectures:
        problems = []

        def reject(code, message, status="fail"):
            problems.append(ImplementationRejection(code, message, status))

        if request.target is None:
            reject(
                "target_required",
                "An original target context is required.",
                "unsupported",
            )
        elif request.target.payload_format is not PayloadFormat.RNA:
            reject(
                "unsupported_modality",
                "This family requires RNA; implicit DNA conversion is unsupported.",
                "unsupported",
            )
        if any(x.category == "contradiction" for x in requirements.diagnostics):
            reject(
                "source_contradiction",
                "The retained source contains contradictory required behavior.",
            )
        if request.constraints.require_implementation_complete:
            reject(
                "implementation_incomplete",
                "This structural family leaves required sensing, control and physical function unresolved.",
                "unsupported",
            )
        if (
            request.constraints.allowed_architecture_ids
            and architecture.id not in request.constraints.allowed_architecture_ids
        ):
            reject(
                "architecture_not_allowed",
                "Architecture is outside the authored allowlist.",
            )
        if (
            request.target is None
            or architecture.target_fingerprint != request.target.fingerprint
        ):
            reject(
                "target_mismatch",
                "Architecture declares a different exact target context.",
            )
        if request.target is not None and not {x[2] for x in PLAN_ROLES} <= set(
            request.target.compartments
        ):
            reject(
                "target_compartments",
                "Target does not declare every compartment required by this architecture.",
            )
        length = sum(len(x.sequence) for x in architecture.authorities)
        if (
            request.constraints.max_length is not None
            and length > request.constraints.max_length
        ):
            reject(
                "max_length_exceeded",
                "Assembled RNA exceeds the authored maximum length.",
            )
        for authority in architecture.authorities:
            if _sha(authority.sequence) != authority.sequence_sha256:
                reject(
                    "sequence_hash",
                    f"Sequence authority {authority.id!r} differs from its pinned bases.",
                )
        for segment in architecture.segments:
            sequence = segment.sequence.sequence
            if len(sequence) % 3:
                reject(
                    "segment_frame", f"Coding segment {segment.id!r} is not in frame."
                )
                continue
            if segment.kind == "terminal_stop":
                if sequence not in {"UAA", "UAG", "UGA"}:
                    reject(
                        "segment_translation",
                        f"Coding segment {segment.id!r} is not exactly one stop codon.",
                    )
                continue
            try:
                peptide = translate_cds("AUG" + sequence + "UAA", "RNA")[1:-1]
            except SerializationError:
                reject(
                    "segment_translation",
                    f"Coding segment {segment.id!r} contains invalid translation or stops.",
                )
            else:
                if peptide != segment.protein_sequence:
                    reject(
                        "segment_translation",
                        f"Coding segment {segment.id!r} differs from its declared peptide.",
                    )
        expected_precursor = "".join(x.protein_sequence for x in architecture.segments)
        if architecture.precursor_protein != expected_precursor:
            reject(
                "precursor_correspondence",
                "Declared precursor differs from its ordered segment peptides.",
            )
        mature = next(x for x in architecture.segments if x.kind == "mature_product")
        if architecture.mature_protein != mature.protein_sequence:
            reject(
                "mature_product_correspondence",
                "Declared mature product differs from the mature coding segment.",
            )
        prefix = sum(
            len(x.protein_sequence)
            for x in architecture.segments
            if x.kind in {"signal_peptide", "junction"}
        )
        if (
            architecture.cleavage_after_aa != prefix
            or architecture.precursor_protein[architecture.cleavage_after_aa : -1]
            != architecture.mature_protein
        ):
            reject(
                "processing_correspondence",
                "The declared cleavage boundary does not yield the exact mature product.",
            )
        for diagnostic in structural_rna_diagnostics(_structural_recipe(architecture)):
            reject(diagnostic.code, diagnostic.message, diagnostic.status)
        providers = {x.id: x for x in request.library.providers}
        bindings = {
            x.dependency_id: x.provider_id for x in architecture.dependency_bindings
        }
        for dependency in sorted(architecture.dependencies, key=lambda x: x.id):
            if (
                not dependency.required
                or dependency.role != product.role_id
                or dependency.scope != "cell"
                or dependency.compartment
                != DEPENDENCY_COMPARTMENTS[dependency.capability]
            ):
                reject(
                    "dependency_context",
                    f"Dependency {dependency.id!r} differs from its required role, scope or compartment.",
                )
            provider = providers.get(bindings[dependency.id])
            if provider is None or provider.kind == "unresolved":
                reject(
                    "dependency_unresolved",
                    f"Dependency {dependency.id!r} has no declared host or external provider.",
                    "unknown",
                )
                continue
            if provider.depends_on:
                reject(
                    "provider_prerequisites_unsupported",
                    f"Provider {provider.id!r} has prerequisites outside this bounded family.",
                    "unsupported",
                )
            if (
                request.target is not None
                and provider.kind == "host"
                and (
                    dependency.capability not in request.target.capabilities
                    or dependency.compartment not in request.target.compartments
                )
            ):
                reject(
                    "host_capability_undeclared",
                    f"Host dependency {dependency.id!r} is not declared by the original target.",
                )
            if (
                isinstance(request.target, HumanTargetContext)
                and provider.kind == "host"
                and not any(
                    x.capability == dependency.capability
                    and x.compartment == dependency.compartment
                    for x in request.target.human_target.host_dependencies
                )
            ):
                reject(
                    "human_host_dependency_undeclared",
                    f"Host dependency {dependency.id!r} is absent from the human target contract.",
                )
            expected = (
                dependency.capability,
                dependency.role,
                dependency.scope,
                dependency.compartment,
            )
            if (
                architecture.target_fingerprint not in provider.supported_targets
                or not any(
                    (x.id, x.role, x.scope, x.compartment) == expected
                    for x in provider.capabilities
                )
            ):
                reject(
                    "dependency_incompatible",
                    f"Provider {provider.id!r} does not declare the exact dependency and target context.",
                )
        alternatives.append(
            ImplementationAlternative(
                architecture.id, architecture.fingerprint, length, tuple(problems)
            )
        )
    eligible = [x for x in alternatives if x.eligible]
    eligible.sort(
        key=(lambda x: (x.length_nt, x.architecture_id))
        if request.constraints.preference == "shortest"
        else lambda x: x.architecture_id
    )
    diagnostics = (
        ()
        if eligible
        else (
            ("bounded_candidates_exhausted",)
            if architectures
            else ("product_binding_unavailable",)
        )
    )
    return ImplementationSelection(
        request.fingerprint,
        requirements.fingerprint,
        tuple(alternatives),
        eligible[0].architecture_id if eligible else None,
        diagnostics,
    )


def derive_implementation_plan(request, requirements, selection):
    request = _authority(request, requirements)
    require(
        selection == select_implementation(request, requirements),
        "Selection differs from current authority.",
    )
    require(
        selection.selected_architecture_id is not None,
        "No eligible implementation architecture.",
    )
    architecture = next(
        x
        for x in request.library.architectures
        if x.id == selection.selected_architecture_id
    )
    product = requirements.products[0]
    all_segments = tuple(x.id for x in architecture.segments)
    prefix_segments = tuple(
        x.id for x in architecture.segments if x.kind in {"signal_peptide", "junction"}
    )
    mature_segments = tuple(
        x.id for x in architecture.segments if x.kind == "mature_product"
    )
    role_segments = {
        "translation": all_segments,
        "precursor": all_segments,
        "processing": prefix_segments + mature_segments,
        "product": mature_segments,
        "export": (),
    }
    roles = tuple(
        ImplementationRole(
            identity, kind, compartment, (product.id,), role_segments[identity]
        )
        for identity, kind, compartment in PLAN_ROLES
    )
    providers = {x.id: x for x in request.library.providers}
    bindings = {
        x.dependency_id: x.provider_id for x in architecture.dependency_bindings
    }
    dependencies = tuple(
        ImplementationDependency(x, providers.get(bindings[x.id]))
        for x in sorted(architecture.dependencies, key=lambda x: x.id)
    )
    return ImplementationPlan(
        request.fingerprint,
        requirements.fingerprint,
        selection.fingerprint,
        architecture.id,
        architecture.fingerprint,
        product.id,
        product.source_ids,
        roles,
        tuple(ImplementationEdge(*x) for x in PLAN_EDGES),
        dependencies,
        tuple(x.id for x in requirements.obligations),
    )


def derive_implementation_construct(request, requirements, plan):
    request = _authority(request, requirements)
    selection = select_implementation(request, requirements)
    require(
        plan == derive_implementation_plan(request, requirements, selection),
        "Plan differs from current source and architecture authority.",
    )
    architecture = next(
        x for x in request.library.architectures if x.id == plan.architecture_id
    )
    items = [
        (
            "five_prime_utr",
            "five_prime_utr",
            architecture.five_prime_utr,
            None,
            "translation",
        )
    ]
    aa = 0
    for segment in architecture.segments:
        end = aa + (
            0 if segment.kind == "terminal_stop" else len(segment.protein_sequence)
        )
        items.append(
            (
                "segment:" + segment.id,
                segment.kind,
                segment.sequence,
                SequenceRange(aa, end),
                "product" if segment.kind == "mature_product" else "precursor",
            )
        )
        aa = end
    items.append(
        (
            "three_prime_utr",
            "three_prime_utr",
            architecture.three_prime_utr,
            None,
            "translation",
        )
    )
    if architecture.poly_a is not None:
        items.append(("poly_a", "poly_a", architecture.poly_a, None, "translation"))
    placements, cursor = [], 0
    for identity, kind, authority, protein_range, role in items:
        end = cursor + len(authority.sequence)
        placements.append(
            ImplementationPlacement(
                identity,
                kind,
                authority.id,
                authority.fingerprint,
                SequenceRange(0, len(authority.sequence)),
                SequenceRange(cursor, end),
                protein_range,
                (plan.product_requirement_id,),
                role,
            )
        )
        cursor = end
    cds_start = len(architecture.five_prime_utr.sequence)
    junctions, offset = [], cds_start
    for segment in architecture.segments[:-1]:
        offset += len(segment.sequence.sequence)
        junctions.append(offset)
    return ImplementationConstruct(
        request.fingerprint,
        requirements.fingerprint,
        plan.fingerprint,
        architecture.id,
        requirements.build_request.intent.name + ".precursor",
        tuple(placements),
        architecture.precursor_protein,
        architecture.mature_protein,
        architecture.cleavage_after_aa,
        cds_start + 3 * architecture.cleavage_after_aa,
        tuple(junctions),
        architecture.features,
    )
