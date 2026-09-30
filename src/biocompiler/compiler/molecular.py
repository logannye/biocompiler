"""Checked Construct -> Molecular emission for exact DNA/RNA coding references."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.backends.reference import EMITTER_VERSION, emit_reference_sequence
from biocompiler.compiler.construct import run_construct_pipeline
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    CompletionProfile,
    PassContract,
    PassManager,
    PipelineError,
    PipelineResult,
)
from biocompiler.ir.construct import ConstructCandidate, ConstructRequest
from biocompiler.ir.molecular import EncodingPolicy, MolecularArtifact
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.ir.stages import Stage
from biocompiler.verification.components import check_composition
from biocompiler.verification.evidence import EvidenceKind
from biocompiler.verification.molecular import (
    CHECKER_VERSION,
    MolecularResult,
    check_molecular,
)

MOLECULAR_PIPELINE_VERSION = "biocompiler.exact_cds_pipeline.v0.1"


@dataclass(frozen=True)
class MolecularBuild:
    construct: ConstructCandidate
    candidate: MolecularArtifact
    check_result: MolecularResult
    result: PipelineResult
    manager: PassManager


def run_molecular_pipeline(
    request: ConstructRequest, registry, manifests
) -> MolecularBuild:
    """Complete exact_cds only after independent construct and nucleotide checks.

    Inputs are independently pinned offline snapshots, as for
    run_construct_pipeline. Complete-payload and empirical claims remain
    unresolved. Reuse requires manager.result('molecular', scope='exact_cds')
    after supplying current dependency roots; serialized reports cannot grant it.
    """
    require(isinstance(manifests, Mapping), "Expected a reference manifest mapping.")
    references = MappingProxyType(dict(manifests))
    # Admission and emission use one immutable snapshot of the supplied map.
    upstream = run_construct_pipeline(request, registry, references)
    manager = upstream.manager
    dependencies = {
        "molecular_emitter": fingerprint(EMITTER_VERSION),
        "molecular_checker": fingerprint(CHECKER_VERSION),
        "molecular_profile": fingerprint(request.target.payload_format.value + "-CDS"),
        "encoding_policy": EncodingPolicy().fingerprint,
        "molecular_pipeline": fingerprint(MOLECULAR_PIPELINE_VERSION),
    }
    for key, value in dependencies.items():
        manager.set_dependency(key, value)
    manager.register_completion_profile(
        CompletionProfile(
            "exact_cds",
            Stage.MOLECULAR,
            MolecularArtifact.schema_version,
            (
                "reference_authority",
                "component_linkage",
                "construct_layout",
                "emitted_sequence_identity",
            ),
        )
    )
    contract = PassContract(
        "construct_to_molecular",
        EMITTER_VERSION,
        Stage.CONSTRUCT,
        Stage.MOLECULAR,
        ConstructCandidate.schema_version,
        MolecularArtifact.schema_version,
        "exact_cds",
        MOLECULAR_PIPELINE_VERSION,
        ("cds_record",),
        (
            CheckSpec(
                "sequence_identity",
                EvidenceKind.EXACT,
                ("emitted_sequence_identity", "construct_layout"),
            ),
            CheckSpec(
                "encoding_composition",
                EvidenceKind.MODEL_CONDITIONAL,
                ("component_linkage",),
            ),
        ),
        dependency_keys=tuple(dependencies),
        consumes_requirements=request.composition.requirement_ids,
        changed_properties=("sequence_spelling", "molecular_feature_declarations"),
        invalidated_analyses=(
            "construct_layout",
            "component_linkage",
            "molecular_behavior",
        ),
    )

    def source_links(construct):
        return tuple(
            SourceLink(
                requirement, placement.instance_id, placement.instance_id, contract.id
            )
            for placement in construct.placements
            for requirement in placement.requirement_ids
        )

    def require_current_providers(context):
        if any(
            context.dependencies.get(key) != value
            for key, value in dependencies.items()
        ):
            raise PipelineError(
                "Molecular provider or policy identity changed; rebuild the pipeline with current providers."
            )

    def emit(context):
        require_current_providers(context)
        construct = ConstructCandidate.from_dict(context.input)
        artifact = emit_reference_sequence(request, construct, registry, references)
        return PassResult(artifact, (), source_links(construct))

    def check(context):
        require_current_providers(context)
        construct = ConstructCandidate.from_dict(context.input)
        expected = sorted(
            (
                link.requirement_id,
                link.source_node_id,
                link.target_node_id,
                link.pass_name,
            )
            for link in source_links(construct)
        )
        actual = sorted(
            (
                link.requirement_id,
                link.source_node_id,
                link.target_node_id,
                link.pass_name,
            )
            for link in context.source_links
        )
        if actual != expected or context.observation_map:
            raise PipelineError(
                "Molecular emission changed source correspondence or introduced unestablished observations."
            )
        artifact = MolecularArtifact.from_dict(context.output)
        checked = check_molecular(request, construct, artifact, registry, references)
        return CheckDecision(checked.outcome, checked.claim_scope, checked.to_dict())

    def check_linkage(context):
        require_current_providers(context)
        checked = check_composition(request.composition, registry)
        return CheckDecision(checked.outcome, checked.claim_scope, checked.to_dict())

    manager.register(
        contract,
        emit,
        {"sequence_identity": check, "encoding_composition": check_linkage},
    )
    record = manager.run(contract.id, "construct", "molecular")
    result = manager.result("molecular", scope="exact_cds")
    artifact = MolecularArtifact.from_dict(record.payload)
    checked = check_molecular(
        request, upstream.candidate, artifact, registry, references
    )
    return MolecularBuild(upstream.candidate, artifact, checked, result, manager)
