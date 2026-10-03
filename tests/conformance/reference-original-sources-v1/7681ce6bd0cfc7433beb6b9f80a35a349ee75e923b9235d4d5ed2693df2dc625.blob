"""Checked structural fragment Components -> Construct -> Molecular pipeline."""

from dataclasses import dataclass

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.backends.molecular_design import EMITTER_VERSION, emit_molecular_design
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    CompletionProfile,
    ComponentInputContract,
    PassContract,
    PassManager,
    PipelineError,
    PipelineResult,
    ScopedObligation,
)
from biocompiler.ir.molecular_design import (
    PROFILE_VERSION,
    MolecularDesignArtifact,
    MolecularDesignConstruct,
    MolecularDesignRequest,
)
from biocompiler.ir.payload import hash_value
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.ir.stages import Stage
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.context import PayloadFormat
from biocompiler.synthesis.molecular_design import (
    GENERATOR_VERSION,
    generate_molecular_design_construct,
)
from biocompiler.verification.evidence import EvidenceKind
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION,
    UNRESOLVED_OBLIGATIONS,
    MolecularDesignResult,
    check_molecular_design,
    check_molecular_design_construct,
    check_molecular_design_request,
)

PIPELINE_VERSION = "biocompiler.molecular_design_pipeline.v0.1"
COMPLETION_SCOPE = "software_molecular_design"


@dataclass(frozen=True)
class MolecularDesignBuild:
    request: MolecularDesignRequest
    construct: MolecularDesignConstruct
    candidate: MolecularDesignArtifact
    authority_result: MolecularDesignResult
    construct_result: MolecularDesignResult
    check_result: MolecularDesignResult
    result: PipelineResult
    manager: PassManager


def run_molecular_design_pipeline(
    request: MolecularDesignRequest, *, expected_request_fingerprint: str
) -> MolecularDesignBuild:
    """Complete the software structural scope using fresh independent checks.

    Caller authority is the complete request pin, supplied separately from the
    candidate. The component entry contains only literal sequence fragments;
    no upstream intent, dynamic composition or biological proof is synthesized.
    """
    require(
        isinstance(request, MolecularDesignRequest),
        "Expected a molecular design request.",
    )
    hash_value(expected_request_fingerprint, "Expected molecular design request")
    dependencies = {
        "request": request.fingerprint,
        "expected_request": expected_request_fingerprint,
        "human_admission_policy": fingerprint(ADMISSION_POLICY_VERSION),
        "molecular_design_profile": fingerprint(PROFILE_VERSION),
        "molecular_design_generator": fingerprint(GENERATOR_VERSION),
        "molecular_design_emitter": fingerprint(EMITTER_VERSION),
        "molecular_design_checker": fingerprint(CHECKER_VERSION),
        "molecular_design_pipeline": fingerprint(PIPELINE_VERSION),
        "fragments": fingerprint(
            {fragment.id: fragment.fingerprint for fragment in request.fragments}
        ),
        "layout": fingerprint(
            [placement.to_dict() for placement in request.placements]
        ),
    }
    authority = ScopedObligation(
        "fragment_authority",
        COMPLETION_SCOPE,
        EvidenceKind.EXACT,
        "Exact supplied fragment identities and software design request authority.",
    )
    layout = ScopedObligation(
        "fragment_layout",
        COMPLETION_SCOPE,
        EvidenceKind.EXACT,
        "Construct retains every authorized fragment slice, region, chemistry declaration and placement.",
    )
    molecular = ScopedObligation(
        "molecular_design_identity",
        COMPLETION_SCOPE,
        EvidenceKind.EXACT,
        "Every emitted nucleotide and structured property matches independent fragment and layout authority.",
    )
    unresolved = tuple(
        ScopedObligation(
            identity,
            "human_complete_payload",
            EvidenceKind.EMPIRICAL,
            "Unestablished by software fixture assembly: "
            + identity.replace("_", " ")
            + ".",
        )
        for identity in UNRESOLVED_OBLIGATIONS
    )
    manager = PassManager(
        target=request.target,
        dependencies=dependencies,
        completion_profiles=(
            CompletionProfile(
                COMPLETION_SCOPE,
                Stage.MOLECULAR,
                MolecularDesignArtifact.schema_version,
                (authority.id, layout.id, molecular.id),
            ),
        ),
    )

    def providers(context):
        if any(
            context.dependencies.get(key) != value
            for key, value in dependencies.items()
        ):
            raise PipelineError(
                "Molecular design authority or tool identity changed; reconstruct with current providers."
            )

    def decision(checked):
        return CheckDecision(checked.outcome, checked.claim_scope, checked.to_dict())

    def check_authority(context):
        providers(context)
        bound = MolecularDesignRequest.from_dict(context.input)
        if bound.requirement_ids != context.requirements:
            raise PipelineError(
                "Fragment component admission changed layout requirement identities."
            )
        return decision(
            check_molecular_design_request(
                bound, expected_request_fingerprint=expected_request_fingerprint
            )
        )

    admission = ComponentInputContract(
        "molecular_design_fragments",
        PIPELINE_VERSION,
        MolecularDesignRequest.schema_version,
        (CheckSpec("fragment_authority", EvidenceKind.EXACT, (authority.id,)),),
        request.requirement_ids,
        (authority, *unresolved),
        tuple(dependencies),
    )
    manager.register_component_input(admission, {"fragment_authority": check_authority})
    manager.admit_component_input(admission.id, "components", request)
    manager.get("components")
    assembly = PassContract(
        "molecular_design_components_to_construct",
        GENERATOR_VERSION,
        Stage.COMPONENTS,
        Stage.CONSTRUCT,
        MolecularDesignRequest.schema_version,
        MolecularDesignConstruct.schema_version,
        COMPLETION_SCOPE,
        PROFILE_VERSION,
        ("fragment_placement",),
        (CheckSpec("fragment_layout", EvidenceKind.EXACT, (layout.id,)),),
        dependency_keys=tuple(dependencies),
        targets=(PayloadFormat.RNA,),
        consumes_requirements=request.requirement_ids,
        introduces=(layout,),
        changed_properties=("layout", "region_membership"),
        invalidated_analyses=UNRESOLVED_OBLIGATIONS,
    )

    def layout_links(bound):
        return tuple(
            SourceLink(
                "region:" + item.region_id,
                item.fragment_id,
                item.region_id,
                assembly.id,
            )
            for item in bound.placements
        )

    def maps(context, expected):
        if context.source_links != expected or context.observation_map:
            raise PipelineError(
                "Molecular design pass changed layout provenance or introduced unestablished observations."
            )

    def assemble(context):
        providers(context)
        bound = MolecularDesignRequest.from_dict(context.input)
        return PassResult(
            generate_molecular_design_construct(bound), (), layout_links(bound)
        )

    def check_layout(context):
        providers(context)
        bound = MolecularDesignRequest.from_dict(context.input)
        maps(context, layout_links(bound))
        return decision(
            check_molecular_design_construct(
                bound,
                MolecularDesignConstruct.from_dict(context.output),
                expected_request_fingerprint=expected_request_fingerprint,
            )
        )

    manager.register(assembly, assemble, {"fragment_layout": check_layout})
    construct_record = manager.run(assembly.id, "components", "construct")
    construct = MolecularDesignConstruct.from_dict(construct_record.payload)
    emission = PassContract(
        "molecular_design_construct_to_molecular",
        EMITTER_VERSION,
        Stage.CONSTRUCT,
        Stage.MOLECULAR,
        MolecularDesignConstruct.schema_version,
        MolecularDesignArtifact.schema_version,
        COMPLETION_SCOPE,
        PROFILE_VERSION,
        ("molecular_region",),
        (
            CheckSpec(
                "molecular_design_identity",
                EvidenceKind.EXACT,
                (molecular.id, layout.id),
            ),
        ),
        dependency_keys=tuple(dependencies),
        targets=(PayloadFormat.RNA,),
        consumes_requirements=request.requirement_ids,
        introduces=(molecular,),
        changed_properties=("sequence_spelling", "molecular_features"),
        invalidated_analyses=(layout.id, *UNRESOLVED_OBLIGATIONS),
    )

    def emission_links(bound):
        return tuple(
            SourceLink(
                "region:" + item.region_id, item.region_id, item.region_id, emission.id
            )
            for item in bound.placements
        )

    def emit(context):
        providers(context)
        bound = MolecularDesignConstruct.from_dict(context.input)
        return PassResult(
            emit_molecular_design(request, bound), (), emission_links(bound)
        )

    def check_output(context):
        providers(context)
        bound = MolecularDesignConstruct.from_dict(context.input)
        maps(context, emission_links(bound))
        return decision(
            check_molecular_design(
                request,
                bound,
                MolecularDesignArtifact.from_dict(context.output),
                expected_request_fingerprint=expected_request_fingerprint,
            )
        )

    manager.register(emission, emit, {"molecular_design_identity": check_output})
    record = manager.run(emission.id, "construct", "molecular")
    result = manager.result("molecular", scope=COMPLETION_SCOPE)
    candidate = MolecularDesignArtifact.from_dict(record.payload)
    return MolecularDesignBuild(
        request,
        construct,
        candidate,
        check_molecular_design_request(
            request, expected_request_fingerprint=expected_request_fingerprint
        ),
        check_molecular_design_construct(
            request,
            construct,
            expected_request_fingerprint=expected_request_fingerprint,
        ),
        check_molecular_design(
            request,
            construct,
            candidate,
            expected_request_fingerprint=expected_request_fingerprint,
        ),
        result,
        manager,
    )
