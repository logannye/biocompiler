"""One checked BuildRequest -> Behavior -> synthetic candidate integration.

This named API completes only the declared finite-history synthetic profile.
It does not activate molecular compile() or claim biological implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    CompletionProfile,
    PassContract,
    PassManager,
    PipelineError,
    PipelineResult,
    ScopedObligation,
)
from biocompiler.compiler.request import BuildRequest, RealizationRequest
from biocompiler.ir.behavior import BehaviorProgram, SCHEMA_VERSION, SUPPORTED_KINDS
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.stages import Stage
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION
from biocompiler.registry.synthetic import SYNTHETIC_CATALOG, SYNTHETIC_PROFILE_VERSION
from biocompiler.semantics.evaluator import REFERENCE_EVALUATOR_VERSION
from biocompiler.synthesis.synthetic import (
    GENERATOR_VERSION,
    SYNTHETIC_CHECKER_VERSION,
    SyntheticCandidate,
    SyntheticGeneratorConfig,
    check_synthetic_candidate,
    generate_synthetic,
)
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from biocompiler.verification.realization import CHECKER_VERSION


@dataclass(frozen=True)
class SyntheticBuild:
    candidate: SyntheticCandidate
    result: PipelineResult
    manager: PassManager


def run_synthetic_pipeline(
    request: RealizationRequest,
    history,
    *,
    until=None,
    config: SyntheticGeneratorConfig | None = None,
) -> SyntheticBuild:
    """Generate and independently accept a synthetic candidate, or raise.

    Retain ``manager`` when checking freshness after changing dependency roots.
    ``result`` is a historical record, not a permanently fresh certificate;
    use manager.result('mechanism', scope='synthetic_realization') before reuse.
    """
    if not isinstance(request, RealizationRequest):
        raise TypeError("Expected a frozen RealizationRequest.")
    if request.build_request.artifact_scope != "synthetic_realization":
        raise PipelineError(
            "The request must explicitly select synthetic_realization scope."
        )
    config = SyntheticGeneratorConfig() if config is None else config
    if not isinstance(config, SyntheticGeneratorConfig):
        raise TypeError("Expected a SyntheticGeneratorConfig.")
    frames = tuple(history)
    dependencies = {
        "human_admission_policy": fingerprint(ADMISSION_POLICY_VERSION),
        "request": request.build_request.fingerprint,
        "request_artifact": request.build_request.artifact_fingerprint,
        "realization_request": request.fingerprint,
        "realization_artifact": request.artifact_fingerprint,
        "catalog": SYNTHETIC_CATALOG.fingerprint,
        "generator": fingerprint(config.to_dict()),
        "model": fingerprint(MODEL_RUNNER_VERSION),
        "checker": fingerprint(CHECKER_VERSION),
        "synthetic_acceptance": fingerprint(SYNTHETIC_CHECKER_VERSION),
        "evaluator": fingerprint(REFERENCE_EVALUATOR_VERSION),
        "history": fingerprint([frame.to_dict() for frame in frames]),
        "horizon": fingerprint(until),
    }
    preservation = ScopedObligation(
        "behavior_preservation",
        "synthetic_realization",
        EvidenceKind.EXACT,
        "Behavior preserves the independently frozen request.",
    )
    response = ScopedObligation(
        "finite_history_response",
        "synthetic_realization",
        EvidenceKind.MODEL_CONDITIONAL,
        "Synthetic response meets authored contracts on the exercised finite history.",
    )
    biology = ScopedObligation(
        "molecular_behavior",
        "complete_payload",
        EvidenceKind.EMPIRICAL,
        "A molecular implementation and biological applicability remain unestablished.",
    )
    manager = PassManager(
        target=request.target,
        dependencies=dependencies,
        completion_profiles=(
            CompletionProfile(
                "synthetic_realization",
                Stage.MECHANISM,
                SyntheticCandidate.schema_version,
                (preservation.id, response.id),
            ),
        ),
    )
    requirements = tuple(item.id for item in request.behavior.requirements)
    manager.add_input(
        "request",
        request.build_request,
        requirements=requirements,
        obligations=(preservation, biology),
    )
    lowering = PassContract(
        "intent_to_behavior",
        "biocompiler.checked_lowering.v0.2",
        Stage.INTENT,
        Stage.BEHAVIOR,
        BuildRequest.schema_version,
        SCHEMA_VERSION,
        "abstract_behavior",
        request.build_request.behavior_profile,
        tuple(sorted(SUPPORTED_KINDS)),
        (CheckSpec("preservation", EvidenceKind.EXACT, (preservation.id,)),),
        consumes_requirements=requirements,
    )

    def lower(context):
        behavior = lower_to_behavior(BuildRequest.from_dict(context.input))
        links = tuple(
            SourceLink(item.id, item.source_node_id, item.source_node_id, lowering.id)
            for item in behavior.requirements
        )
        return PassResult(behavior, (), links)

    def verify(context):
        report = verify_lowering(
            BuildRequest.from_dict(context.input),
            BehaviorProgram.from_dict(context.output),
        )
        return CheckDecision(
            CheckOutcome.PASS,
            "Authoritative request and complete source correspondence verified.",
            {
                "input_request": request.build_request.fingerprint,
                "behavior": report.behavior_fingerprint,
            },
        )

    manager.register(lowering, lower, {"preservation": verify})
    manager.run(lowering.id, "request", "behavior")
    generation = PassContract(
        "behavior_to_synthetic",
        GENERATOR_VERSION,
        Stage.BEHAVIOR,
        Stage.MECHANISM,
        SCHEMA_VERSION,
        SyntheticCandidate.schema_version,
        "synthetic_combinational",
        SYNTHETIC_PROFILE_VERSION,
        tuple(item.operation for item in SYNTHETIC_CATALOG.components),
        (CheckSpec("finite_history", EvidenceKind.MODEL_CONDITIONAL, (response.id,)),),
        dependency_keys=(
            "realization_request",
            "catalog",
            "generator",
            "model",
            "checker",
            "synthetic_acceptance",
            "history",
            "horizon",
        ),
        required_capabilities=("synthetic_signal_graph",),
        consumes_requirements=requirements,
        introduces=(response,),
        requires_observation_map=True,
        operation_path=("mechanism",),
    )

    def generate(context):
        behavior = BehaviorProgram.from_dict(context.input)
        bound = RealizationRequest.freeze(
            request.build_request, behavior, request.contract, request.domain
        )
        candidate = generate_synthetic(bound, config=config)
        links = tuple(
            SourceLink(requirement_id, source, node_id, generation.id)
            for node_id, origins in candidate.source_map.items()
            for requirement_id in candidate.behavior_requirement_ids[node_id]
            for source in origins
        )
        return PassResult(candidate, (), links, candidate.observation_map.to_dict())

    def check(context):
        candidate = SyntheticCandidate.from_dict(context.output)
        bound = RealizationRequest.freeze(
            request.build_request,
            BehaviorProgram.from_dict(context.input),
            request.contract,
            request.domain,
        )
        result = check_synthetic_candidate(bound, candidate, frames, until=until)
        return CheckDecision(result.outcome, result.claim_scope, result.to_dict())

    manager.register(generation, generate, {"finite_history": check})
    record = manager.run(
        generation.id, "behavior", "mechanism", configuration=config.to_dict()
    )
    result = manager.result("mechanism", scope="synthetic_realization")
    return SyntheticBuild(SyntheticCandidate.from_dict(record.payload), result, manager)
