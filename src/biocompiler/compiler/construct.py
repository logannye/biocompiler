"""Checked Components -> Construct pipeline for independently selected CDS records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from biocompiler.artifacts.provenance import SourceLink
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
from biocompiler.ir.construct import ConstructCandidate, ConstructRequest
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.ir.stages import Stage
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import REFERENCE_COMPONENT_VERSION
from biocompiler.registry.references import ReferenceManifest
from biocompiler.synthesis.construct import (
    CONSTRUCT_GENERATOR_VERSION,
    generate_construct,
)
from biocompiler.verification.components import (
    CHECKER_VERSION as LINKER_VERSION,
    check_composition,
)
from biocompiler.verification.construct import (
    CHECKER_VERSION,
    ConstructResult,
    check_construct,
    check_construct_request,
)
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind

CONSTRUCT_PIPELINE_VERSION = "biocompiler.reference_construct_pipeline.v0.2"


@dataclass(frozen=True)
class ConstructBuild:
    candidate: ConstructCandidate
    check_result: ConstructResult
    result: PipelineResult
    manager: PassManager


def run_construct_pipeline(
    request: ConstructRequest,
    registry: ComponentRegistry,
    manifests: Mapping[str, ReferenceManifest],
) -> ConstructBuild:
    """Check selected input authority, assemble a candidate, and verify its layout.

    Load manifests with ``load_reference_manifest(expected_fingerprint=...)``
    before freezing this offline snapshot. Changed files must be reloaded and
    changed dependencies supplied to the manager; it does not watch the disk.
    Reuse requires ``manager.result('construct', scope='reference_construct')``.
    No upstream behavioral proof or sequence-emission success is inferred.
    """
    from sys import modules
    _reference_backend = modules.get("biocompiler.reference_backend")
    _reference_route = None if _reference_backend is None else _reference_backend.current()
    if _reference_route is not None:
        return _reference_route.construct(request, registry, manifests)
    require(
        isinstance(request, ConstructRequest), "Expected a frozen ConstructRequest."
    )
    require(
        isinstance(registry, ComponentRegistry),
        "Expected an immutable component registry.",
    )
    require(
        isinstance(manifests, Mapping)
        and all(
            isinstance(key, str) and isinstance(value, ReferenceManifest)
            for key, value in manifests.items()
        ),
        "Expected a reference-set ID to manifest mapping.",
    )
    references = MappingProxyType(dict(manifests))
    dependencies = {
        "human_admission_policy": fingerprint(ADMISSION_POLICY_VERSION),
        "request": request.fingerprint,
        "composition": request.composition.fingerprint,
        "component_registry": registry.fingerprint,
        "component_lock": request.composition.registry_lock.fingerprint,
        "layout": request.layout_fingerprint,
        "references": fingerprint(
            {key: value.fingerprint for key, value in references.items()}
        ),
        "reference_adapter": fingerprint(REFERENCE_COMPONENT_VERSION),
        "component_checker": fingerprint(LINKER_VERSION),
        "construct_checker": fingerprint(CHECKER_VERSION),
        "construct_generator": fingerprint(CONSTRUCT_GENERATOR_VERSION),
        "construct_pipeline": fingerprint(CONSTRUCT_PIPELINE_VERSION),
    }
    authority = ScopedObligation(
        "reference_authority",
        "reference_construct",
        EvidenceKind.EXACT,
        "Selected component and supported layout agree with independently pinned reference records.",
    )
    linkage = ScopedObligation(
        "component_linkage",
        "reference_construct",
        EvidenceKind.MODEL_CONDITIONAL,
        "Current selected components satisfy their declared composition contracts.",
    )
    layout = ScopedObligation(
        "construct_layout",
        "reference_construct",
        EvidenceKind.EXACT,
        "Construct preserves exact selected membership, reference coordinates and source requirements.",
    )
    sequence = ScopedObligation(
        "emitted_sequence_identity",
        "exact_cds",
        EvidenceKind.EXACT,
        "Emit the selected nucleotide spelling and independently verify its exact reference identity.",
    )
    payload = ScopedObligation(
        "complete_payload_features",
        "complete_payload",
        EvidenceKind.EXACT,
        "Delivered molecule boundaries, regulatory context and other unknown payload features remain unresolved.",
    )
    biology = ScopedObligation(
        "molecular_behavior",
        "complete_payload",
        EvidenceKind.EMPIRICAL,
        "Molecular behavior and same-cell coexistence are not established by a reference layout.",
    )
    manager = PassManager(
        target=request.target,
        dependencies=dependencies,
        completion_profiles=(
            CompletionProfile(
                "reference_construct",
                Stage.CONSTRUCT,
                ConstructCandidate.schema_version,
                (authority.id, linkage.id, layout.id),
            ),
        ),
    )
    requirements = request.composition.requirement_ids
    admission = ComponentInputContract(
        "reference_components",
        CONSTRUCT_PIPELINE_VERSION,
        ConstructRequest.schema_version,
        (
            CheckSpec("reference_authority", EvidenceKind.EXACT, (authority.id,)),
            CheckSpec(
                "component_linkage", EvidenceKind.MODEL_CONDITIONAL, (linkage.id,)
            ),
        ),
        requirements,
        (authority, linkage, sequence, payload, biology),
        tuple(dependencies),
    )

    def verify_authority(context):
        bound = ConstructRequest.from_dict(context.input)
        if bound.composition.requirement_ids != context.requirements:
            raise PipelineError("Component admission changed its source requirements.")
        diagnostics = check_construct_request(bound, registry, references)
        statuses = {item.status for item in diagnostics}
        outcome = next(
            (
                CheckOutcome(value)
                for value in ("fail", "unsupported", "unknown")
                if value in statuses
            ),
            CheckOutcome.PASS,
        )
        return CheckDecision(
            outcome,
            "Checked frozen reference selection and supported layout authority.",
            {"diagnostics": [item.to_dict() for item in diagnostics]},
        )

    def verify_linkage(context):
        bound = ConstructRequest.from_dict(context.input)
        checked = check_composition(bound.composition, registry)
        return CheckDecision(checked.outcome, checked.claim_scope, checked.to_dict())

    manager.register_component_input(
        admission,
        {"reference_authority": verify_authority, "component_linkage": verify_linkage},
    )
    manager.admit_component_input(admission.id, "components", request)
    # Check now so a rejected imported root cannot invoke candidate generation.
    manager.get("components")
    contract = PassContract(
        "components_to_construct",
        CONSTRUCT_GENERATOR_VERSION,
        Stage.COMPONENTS,
        Stage.CONSTRUCT,
        ConstructRequest.schema_version,
        ConstructCandidate.schema_version,
        "reference_construct",
        CONSTRUCT_PIPELINE_VERSION,
        ("component_placement",),
        (
            CheckSpec("layout", EvidenceKind.EXACT, (layout.id,)),
            CheckSpec(
                "layout_composition", EvidenceKind.MODEL_CONDITIONAL, (linkage.id,)
            ),
        ),
        dependency_keys=tuple(dependencies),
        consumes_requirements=requirements,
        introduces=(layout,),
        changed_properties=(
            "layout",
            "molecule_membership",
            "orientation",
            "regulatory_context",
        ),
        invalidated_analyses=(linkage.id, biology.id),
    )

    def source_links(bound):
        return tuple(
            SourceLink(requirement, instance.id, instance.id, contract.id)
            for instance in bound.composition.instances
            for requirement in instance.requirement_ids
        )

    def assemble(context):
        bound = ConstructRequest.from_dict(context.input)
        return PassResult(generate_construct(bound), (), source_links(bound))

    def verify_layout(context):
        bound = ConstructRequest.from_dict(context.input)
        expected_links = sorted(
            (
                link.requirement_id,
                link.source_node_id,
                link.target_node_id,
                link.pass_name,
            )
            for link in source_links(bound)
        )
        actual_links = sorted(
            (
                link.requirement_id,
                link.source_node_id,
                link.target_node_id,
                link.pass_name,
            )
            for link in context.source_links
        )
        if actual_links != expected_links or context.observation_map:
            raise PipelineError(
                "Construct pass changed authoritative provenance or introduced unestablished observations."
            )
        checked = check_construct(
            bound, ConstructCandidate.from_dict(context.output), registry, references
        )
        return CheckDecision(checked.outcome, checked.claim_scope, checked.to_dict())

    manager.register(
        contract,
        assemble,
        {"layout": verify_layout, "layout_composition": verify_linkage},
    )
    record = manager.run(contract.id, "components", "construct")
    result = manager.result("construct", scope="reference_construct")
    candidate = ConstructCandidate.from_dict(record.payload)
    checked = check_construct(request, candidate, registry, references)
    return ConstructBuild(candidate, checked, result, manager)
