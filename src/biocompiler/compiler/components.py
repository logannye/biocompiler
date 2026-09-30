"""Checked synthetic Mechanism -> Components lowering with exact registry locks."""

from __future__ import annotations

from dataclasses import dataclass

from biocompiler.artifacts.provenance import SourceLink
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
from biocompiler.compiler.request import RealizationRequest
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.stages import Stage
from biocompiler.registry.components import REGISTRY_POLICY_VERSION
from biocompiler.synthesis.components import (
    SYNTHETIC_COMPONENT_ADAPTER_VERSION,
    adapt_synthetic_components,
)
from biocompiler.synthesis.synthetic import SyntheticCandidate, SyntheticGeneratorConfig
from biocompiler.verification.components import (
    CHECKER_VERSION as COMPONENT_CHECKER_VERSION,
    CompositionResult,
    check_composition,
)
from biocompiler.verification.evidence import EvidenceKind


@dataclass(frozen=True)
class ComponentBuild:
    candidate: SyntheticCandidate
    assembly: ComponentAssembly
    link_result: CompositionResult
    result: PipelineResult
    manager: PassManager


def check_component_assembly(request, candidate, assembly, history, *, until=None):
    """Recompute source correspondence and check contracts; never import success.

    Linking a compatible graph alone cannot prove it implements the selected
    Mechanism. The fixed adapter also binds every operation, parameter, edge and
    source requirement to the independently accepted synthetic candidate.
    """
    if not isinstance(assembly, ComponentAssembly):
        raise TypeError("Expected a ComponentAssembly.")
    expected = adapt_synthetic_components(request, candidate, history, until=until)
    if (
        assembly.request_fingerprint != request.fingerprint
        or assembly.candidate_fingerprint != candidate.fingerprint
        or assembly.registry.fingerprint != expected.registry.fingerprint
        or assembly.composition.fingerprint != expected.composition.fingerprint
        or fingerprint(assembly.behavior_sources) != fingerprint(candidate.source_map)
    ):
        raise PipelineError(
            "Component assembly changed its authoritative source correspondence."
        )
    # This structural check is separate from the producer and adapter's port
    # construction: exact graph connectivity and input order must survive.
    actual_edges = {
        (
            edge.producer_instance,
            edge.producer_port,
            edge.consumer_instance,
            edge.consumer_port,
        )
        for edge in assembly.composition.connections
    }
    expected_edges = {
        (source, "out", node.id, f"in:{index}")
        for node in candidate.mechanism.nodes
        for index, source in enumerate(node.inputs)
    }
    if actual_edges != expected_edges or {
        item.id for item in assembly.composition.instances
    } != {node.id for node in candidate.mechanism.nodes}:
        raise PipelineError("Component assembly changed the mechanism graph.")
    return check_composition(assembly.composition, assembly.registry)


def run_component_pipeline(
    request: RealizationRequest,
    history,
    *,
    until=None,
    config: SyntheticGeneratorConfig | None = None,
) -> ComponentBuild:
    """Extend checked synthetic generation to the synthetic_components scope.

    Completion remains conditional on the exercised finite history and declared
    contracts. Reuse requires manager.result('components',
    scope='synthetic_components') so changed roots cannot reuse an old receipt.
    """
    frames = tuple(history)
    upstream = run_synthetic_pipeline(request, frames, until=until, config=config)
    candidate = upstream.candidate
    adapted = adapt_synthetic_components(request, candidate, frames, until=until)
    manager = upstream.manager
    dependencies = {
        "component_registry": adapted.registry.fingerprint,
        "component_lock": adapted.composition.registry_lock.fingerprint,
        "composition_request": adapted.composition.fingerprint,
        "component_adapter": fingerprint(SYNTHETIC_COMPONENT_ADAPTER_VERSION),
        "component_registry_policy": fingerprint(REGISTRY_POLICY_VERSION),
        "component_checker": fingerprint(COMPONENT_CHECKER_VERSION),
    }
    for key, value in dependencies.items():
        manager.set_dependency(key, value)
    linkage = ScopedObligation(
        "component_linkage",
        "synthetic_components",
        EvidenceKind.MODEL_CONDITIONAL,
        "Locked components preserve the accepted synthetic graph and satisfy declared composition contracts.",
    )
    manager.register_completion_profile(
        CompletionProfile(
            "synthetic_components",
            Stage.COMPONENTS,
            ComponentAssembly.schema_version,
            ("behavior_preservation", "finite_history_response", linkage.id),
        )
    )
    requirements = tuple(item.id for item in request.behavior.requirements)
    contract = PassContract(
        "synthetic_to_components",
        SYNTHETIC_COMPONENT_ADAPTER_VERSION,
        Stage.MECHANISM,
        Stage.COMPONENTS,
        SyntheticCandidate.schema_version,
        ComponentAssembly.schema_version,
        "synthetic_components",
        SYNTHETIC_COMPONENT_ADAPTER_VERSION,
        ("component_instance",),
        (CheckSpec("composition", EvidenceKind.MODEL_CONDITIONAL, (linkage.id,)),),
        dependency_keys=tuple(dependencies),
        consumes_requirements=requirements,
        required_capabilities=("synthetic_signal_graph",),
        introduces=(linkage,),
        requires_observation_map=True,
    )

    def generate(context):
        source = SyntheticCandidate.from_dict(context.input)
        assembly = ComponentAssembly(
            adapted.registry,
            adapted.composition,
            request.fingerprint,
            source.fingerprint,
            source.source_map,
        )
        links = tuple(
            SourceLink(requirement_id, node_id, node_id, contract.id)
            for node_id, ids in source.behavior_requirement_ids.items()
            for requirement_id in ids
        )
        return PassResult(assembly, (), links, source.observation_map.to_dict())

    def verify(context):
        source = SyntheticCandidate.from_dict(context.input)
        expected_links = tuple(
            SourceLink(requirement_id, node_id, node_id, contract.id)
            for node_id, ids in source.behavior_requirement_ids.items()
            for requirement_id in ids
        )
        if (
            len(context.source_links) != len(expected_links)
            or set(context.source_links) != set(expected_links)
            or fingerprint(context.observation_map)
            != fingerprint(source.observation_map.to_dict())
        ):
            raise PipelineError(
                "Component pass provenance changed authoritative source links or observations."
            )
        checked = check_component_assembly(
            request,
            source,
            ComponentAssembly.from_dict(context.output),
            frames,
            until=until,
        )
        return CheckDecision(
            checked.outcome,
            "Declared component contracts checked; finite-history scope retained.",
            checked.to_dict(),
        )

    manager.register(contract, generate, {"composition": verify})
    record = manager.run(contract.id, "mechanism", "components")
    result = manager.result("components", scope="synthetic_components")
    assembly = ComponentAssembly.from_dict(record.payload)
    # The report remains historical, just like the pipeline result. Freshness is
    # checked against the caller's current request and registry before reuse.
    linked = check_composition(assembly.composition, assembly.registry)
    return ComponentBuild(candidate, assembly, linked, result, manager)
