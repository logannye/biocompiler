"""Inspect versioned compiler artifacts and the compiler architecture."""

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys
import tempfile

from biocompiler import __version__
from biocompiler.ir.candidate import CandidateRequest, CandidateRequirements, MolecularLibrary
from biocompiler.ir.candidate_build import CandidateBuildRecord
from biocompiler.ir.candidate_selection import CandidateSelection, CandidateLayout
from biocompiler.semantics.admission import AdmissionAssessment, AdmissionRequest
from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.semantics.acceptance import (
    AcceptanceSample,
    ExternalShutdownSpec,
    HumanAcceptanceContract,
    InputAvailabilitySpec,
)
from biocompiler.verification.acceptance import HumanAcceptanceResult

from biocompiler.compiler.request import BuildRequest, RealizationRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.semantics.deployment import (
    CoPayloadRequirement,
    DeliveryPlatformSpec,
    DeploymentContract,
    ExposureAssumption,
    ExpressionTiming,
)
from biocompiler.verification.deployment import DeploymentAssessment
from biocompiler.semantics.human_behavior import (
    ConditionalSecretionContract,
    MeasurementSpec,
    PredicateRefinement,
    SecretionSample,
)
from biocompiler.verification.human_behavior import SecretionTraceResult
from biocompiler.ir.stages import STAGE_ORDER
from biocompiler.errors import SerializationError
from biocompiler.ir.intent import IntentProgram
from biocompiler.ir.behavior import BehaviorProgram, SCHEMA_VERSION as BEHAVIOR_SCHEMA
from biocompiler.ir.intent import SCHEMA_VERSION as INTENT_SCHEMA
from biocompiler.ir.mechanism import MechanismProgram
from biocompiler.ir.serialization import parse_json
from biocompiler.semantics.context import HumanTargetContext, TargetContext
from biocompiler.semantics.human_target import (
    HumanHostDependency,
    HumanOperatingCondition,
    HumanTargetContract,
    TargetClaim,
    TargetEvidence,
)
from biocompiler.semantics.realization import BehaviorContract, OperatingDomain
from biocompiler.verification.evidence import CheckResult
from biocompiler.verification.exploration import (
    AdversarialConfig,
    BooleanContactConfig,
    ExplorationReport,
    ReductionResult,
)
from biocompiler.verification.realization import ObservationMap
from biocompiler.synthesis.synthetic import SyntheticCandidate, SyntheticGeneratorConfig
from biocompiler.registry.synthetic import SyntheticCatalog
from biocompiler.registry.references import ReferenceManifest
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.component_contracts import ComponentRecord
from biocompiler.ir.composition import CompositionRequest
from biocompiler.registry.components import (
    ComponentRegistry,
    RegistryLock,
    SelectionRequest,
    SelectionResult,
)
from biocompiler.registry.reference_components import ReferenceSelection
from biocompiler.semantics.component_contracts import (
    OperatingDomain as ComponentOperatingDomain,
    PortContract,
    ValueDomain,
)
from biocompiler.verification.components import CompositionResult
from biocompiler.ir.construct import ConstructCandidate, ConstructRequest
from biocompiler.verification.construct import ConstructResult
from biocompiler.ir.molecular import MolecularArtifact
from biocompiler.verification.molecular import MolecularResult
from biocompiler.semantics.molecular_behavior import (
    MolecularEvidence,
    MolecularImplementationContract,
    MolecularInputBinding,
    MolecularParameter,
    MolecularResponseBinding,
)
from biocompiler.verification.molecular_behavior import (
    MolecularBehaviorDiagnostic,
    MolecularBehaviorResult,
)
from biocompiler.ir.payload import (
    PayloadFeature,
    PayloadMolecule,
    PayloadReference,
    PayloadRegion,
    PayloadReview,
    PayloadSource,
)
from biocompiler.verification.payload import PayloadResult
from biocompiler.artifacts.archive import read_archive
from biocompiler.artifacts.manifest import (
    BuildManifest,
    ReferenceBuildRequest,
    RunMetadata,
)
from biocompiler.compiler.reference import (
    build_reference_package,
    prepare_reference_build,
    publish_reference_package,
    verify_reference_package,
)
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.errors import BiocompilerError
from biocompiler.artifacts.synthetic_build import (
    SyntheticBuildManifest,
    SyntheticBuildRequest,
    SyntheticHistory,
)
from biocompiler.compiler.synthetic_build import (
    build_synthetic_package,
    publish_synthetic_package,
    verify_synthetic_package,
)
from biocompiler.ir.molecular_design import (
    SequenceFragment,
    FragmentPlacement,
    MolecularDesignRequest,
    MolecularDesignConstruct,
    MolecularDesignArtifact,
)
from biocompiler.artifacts.molecular_design import (
    MolecularDesignBuildManifest,
    MolecularDesignHandoff,
)
from biocompiler.compiler.molecular_design_build import (
    build_molecular_design_package,
    publish_molecular_design_package,
    verify_molecular_design_package,
)
from biocompiler.verification.molecular_design import MolecularDesignResult
from biocompiler.compiler.verification_workflow import (
    SyntheticVerificationRequest,
    SyntheticVerificationRecord,
    run_synthetic_verification,
    replay_synthetic_verification,
)
from biocompiler.synthesis.selection import SyntheticSelectionResult, select_synthetic
from biocompiler.verification.exploration import (
    BooleanInputConfig,
    BooleanInputExplorationReport,
)


def _read_artifact(document):
    # Parse strictly before dispatch: duplicate schema keys must not select a
    # different parser or weaken an artifact's validation boundary.
    header = parse_json(document)
    schema = header.get("schema_version") if isinstance(header, dict) else None
    types = {INTENT_SCHEMA: IntentProgram, BEHAVIOR_SCHEMA: BehaviorProgram}
    types.update(
        {
            cls.schema_version: cls
            for cls in (
                AdmissionRequest,
                AdmissionAssessment,
                BuildRequest,
                CandidateRequest,
                CandidateRequirements,
                MolecularLibrary,
                CandidateBuildRecord,
                CandidateSelection,
                CandidateLayout,
                RealizationRequest,
                HumanBehaviorRequest,
                HumanDeploymentRequest,
                HumanAcceptanceRequest,
                HumanAcceptanceContract,
                InputAvailabilitySpec,
                ExternalShutdownSpec,
                AcceptanceSample,
                HumanAcceptanceResult,
                CoPayloadRequirement,
                DeliveryPlatformSpec,
                DeploymentContract,
                ExposureAssumption,
                ExpressionTiming,
                DeploymentAssessment,
                ConditionalSecretionContract,
                MeasurementSpec,
                PredicateRefinement,
                SecretionSample,
                SecretionTraceResult,
                SyntheticCandidate,
                SyntheticGeneratorConfig,
                SyntheticCatalog,
                ReferenceManifest,
                MechanismProgram,
                TargetContext,
                HumanTargetContext,
                HumanTargetContract,
                HumanHostDependency,
                HumanOperatingCondition,
                TargetClaim,
                TargetEvidence,
                BehaviorContract,
                OperatingDomain,
                ObservationMap,
                CheckResult,
                AdversarialConfig,
                BooleanContactConfig,
                ExplorationReport,
                ReductionResult,
                ComponentAssembly,
                ComponentRecord,
                CompositionRequest,
                ComponentRegistry,
                RegistryLock,
                SelectionRequest,
                SelectionResult,
                ReferenceSelection,
                ComponentOperatingDomain,
                PortContract,
                ValueDomain,
                CompositionResult,
                ConstructRequest,
                ConstructCandidate,
                ConstructResult,
                MolecularArtifact,
                MolecularResult,
                MolecularImplementationContract,
                MolecularEvidence,
                MolecularParameter,
                MolecularInputBinding,
                MolecularResponseBinding,
                MolecularBehaviorDiagnostic,
                MolecularBehaviorResult,
                PayloadFeature,
                PayloadMolecule,
                PayloadReference,
                PayloadRegion,
                PayloadReview,
                PayloadSource,
                PayloadResult,
                BuildManifest,
                ReferenceBuildRequest,
                RunMetadata,
                SyntheticBuildManifest,
                SyntheticBuildRequest,
                SyntheticHistory,
                SyntheticVerificationRequest,
                SyntheticVerificationRecord,
                SyntheticSelectionResult,
                BooleanInputConfig,
                BooleanInputExplorationReport,
                SequenceFragment,
                FragmentPlacement,
                MolecularDesignRequest,
                MolecularDesignConstruct,
                MolecularDesignArtifact,
                MolecularDesignBuildManifest,
                MolecularDesignHandoff,
                MolecularDesignResult,
            )
        }
    )
    if not isinstance(schema, str) or schema not in types:
        raise SerializationError(f"Unknown or missing artifact schema: {schema!r}.")
    return types[schema].from_dict(header)


def _summary(artifact):
    if isinstance(artifact, (IntentProgram, BehaviorProgram)):
        return artifact.summary()
    summary = {
        "schema_version": artifact.schema_version,
        "fingerprint": artifact.fingerprint,
    }
    if isinstance(artifact, CandidateBuildRecord):
        summary.update(
            status=artifact.status, scope="product_cassette_structure",
            therapeutic_implementation="partial", human_therapeutic_admission="not_admitted",
            inspection="Historical candidate only; fresh verification requires independent complete request authority.",
        )
    if isinstance(artifact, SyntheticVerificationRecord):
        summary.update(_verification_summary(artifact))
        summary["inspection"] = (
            "Historical report only; fresh replay requires independent complete operation authority."
        )
    if isinstance(artifact, SyntheticSelectionResult):
        summary.update(
            outcome=artifact.outcome,
            selected_strategy=artifact.selected_strategy,
            checked_candidates=artifact.checked_candidates,
            rejected_candidates=artifact.rejected_candidates,
            inspection="Historical bounded digital selection only; rerun with independent request/history/configuration authority.",
        )
    for key in ("id", "name", "context_id", "outcome", "evidence_kind"):
        if hasattr(artifact, key):
            summary[key] = getattr(artifact, key)
    if isinstance(artifact, AdmissionAssessment):
        summary["intended_use"] = artifact.intended_use
        summary["decision"] = artifact.decision
        summary["diagnostics"] = list(artifact.diagnostics)
        summary["evidence"] = [item.to_dict() for item in artifact.evidence]
        summary["inspection"] = (
            "Historical admission record only; rerun assess_admission with independent request authority. Declared evidence is unvalidated; no human therapeutic profile is admitted."
        )
    if isinstance(artifact, SelectionResult):
        summary["admission"] = artifact.admission.to_dict()
    if isinstance(
        artifact,
        (MolecularArtifact, SyntheticCandidate, BuildManifest, SyntheticBuildManifest),
    ):
        summary["intended_use"] = "software_test"
        summary["human_therapeutic_admission"] = "not_admitted"
    if isinstance(artifact, (HumanAcceptanceRequest, HumanAcceptanceContract)):
        contract = (
            artifact.acceptance
            if isinstance(artifact, HumanAcceptanceRequest)
            else artifact
        )
        summary["unresolved_evidence"] = list(contract.unresolved_evidence)
        summary["inspection"] = (
            "Required and prohibited observation declarations only; healthy classification, input-loss detection and external shutdown are unestablished. No actuator or human payload admission."
        )
    if isinstance(artifact, HumanAcceptanceResult):
        summary["coverage"] = list(artifact.coverage)
        summary["diagnostics"] = list(artifact.diagnostics)
        summary["unresolved_evidence"] = list(artifact.unresolved_evidence)
        summary["inspection"] = (
            "Imported finite-trace record only; rerun check_human_acceptance with independent request and trace authority. No biological or shutdown guarantee."
        )
    if isinstance(artifact, (HumanDeploymentRequest, DeploymentContract)):
        contract = (
            artifact.deployment
            if isinstance(artifact, HumanDeploymentRequest)
            else artifact
        )
        summary["unresolved_evidence"] = list(contract.unresolved_evidence)
        summary["co_payload_obligations"] = len(contract.co_payloads)
        summary["inspection"] = (
            "Frozen delivery declarations only; targeting is separate from disease recognition. Biological delivery, expression and same-cell coexistence remain unestablished."
        )
    if isinstance(artifact, DeploymentAssessment):
        summary["compatibility"] = artifact.compatibility
        summary["diagnostics"] = list(artifact.diagnostics)
        summary["unresolved_evidence"] = list(artifact.unresolved_evidence)
        summary["inspection"] = (
            "Imported declaration-compatibility record only; rerun check_deployment with independent request authority. Human mechanism selection remains blocked."
        )
    if isinstance(artifact, (HumanBehaviorRequest, ConditionalSecretionContract)):
        contract = (
            artifact.contract
            if isinstance(artifact, HumanBehaviorRequest)
            else artifact
        )
        summary["unresolved_evidence"] = list(contract.unresolved_evidence)
        summary["inspection"] = (
            "Source-linked conditional secretion specification only; biological applicability and therapeutic goal attainment remain unestablished."
        )
    if isinstance(artifact, SecretionTraceResult):
        summary["coverage"] = list(artifact.coverage)
        summary["diagnostics"] = list(artifact.diagnostics)
        summary["inspection"] = (
            "Imported finite-trace record only; rerun check_secretion_trace with independent request/trace authority. No biological validation or therapeutic efficacy is established."
        )
    if isinstance(artifact, (HumanTargetContext, HumanTargetContract)):
        contract = (
            artifact.human_target
            if isinstance(artifact, HumanTargetContext)
            else artifact
        )
        summary["unresolved_evidence"] = list(contract.unresolved_evidence)
        summary["inspection"] = (
            "Declared human in-vivo target only; evidence citations are not independently validated and grant no biological or payload admission."
        )
    if isinstance(artifact, ReferenceManifest):
        summary["reference_set_id"] = artifact.reference_set_id
        summary["status"] = artifact.status
        summary["inspection"] = (
            "Schema/content inspection only; use load_reference_manifest with a trusted fingerprint to verify retained source files."
        )
    if isinstance(artifact, CheckResult):
        summary["counterexamples"] = len(artifact.counterexamples)
        summary["diagnostics"] = [item.to_dict() for item in artifact.diagnostics]
    if isinstance(
        artifact,
        (
            ComponentAssembly,
            CompositionResult,
            SelectionResult,
            ConstructRequest,
            ConstructCandidate,
            ConstructResult,
            MolecularArtifact,
            MolecularResult,
            MolecularImplementationContract,
            MolecularBehaviorResult,
            PayloadMolecule,
            PayloadReference,
            PayloadResult,
            ExplorationReport,
            ReductionResult,
            BuildManifest,
            ReferenceBuildRequest,
            SyntheticBuildManifest,
            SyntheticBuildRequest,
        ),
    ):
        summary["inspection"] = (
            "Historical content inspection only; recompute acceptance and freshness against current authoritative inputs before reuse."
        )
    if isinstance(artifact, MolecularBehaviorResult):
        summary["linkage_outcome"] = artifact.linkage_outcome.value
        summary["claim_scope"] = artifact.claim_scope
        summary["diagnostics"] = [item.to_dict() for item in artifact.diagnostics]
    if isinstance(artifact, MolecularImplementationContract):
        summary["model_profile"] = artifact.model_profile
        summary["unestablished_claims"] = list(artifact.unestablished_claims)
    if isinstance(artifact, PayloadResult):
        summary["evidence_boundary"] = artifact.evidence_boundary
        summary["reference_promotion"] = artifact.reference_promotion
        summary["compiler_admission"] = artifact.compiler_admission
        summary["claim_scope"] = artifact.claim_scope
        summary["diagnostics"] = [item.to_dict() for item in artifact.diagnostics]
    if isinstance(artifact, PayloadMolecule):
        summary["artifact_class"] = artifact.artifact_class
        summary["unknown_features"] = list(artifact.unknown_features)
        summary["unestablished_claims"] = list(artifact.unestablished_claims)
    if isinstance(artifact, PayloadReference):
        summary["source_kind"] = artifact.source_kind
        summary["reference_promotion"] = "not_promoted"
    if isinstance(
        artifact,
        (
            MolecularDesignRequest,
            MolecularDesignConstruct,
            MolecularDesignArtifact,
            MolecularDesignBuildManifest,
            MolecularDesignHandoff,
            MolecularDesignResult,
        ),
    ):
        summary.update(
            intended_use="software_test",
            human_therapeutic_admission="not_admitted",
            reference_promotion="not_promoted",
            evidence_boundary="software_fixture",
            inspection="Historical structural design content only; current acceptance requires independent request authority and fresh checks. Biological behavior and experimental material identity remain unresolved.",
        )
    if isinstance(artifact, MolecularDesignResult):
        summary["stage"] = artifact.stage
        summary["claim_scope"] = artifact.claim_scope
        summary["diagnostics"] = [item.to_dict() for item in artifact.diagnostics]
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"biocompiler {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "architecture", help="Show implemented and planned compiler stages"
    )
    inspect_command = commands.add_parser(
        "inspect", help="Inspect a saved versioned JSON artifact"
    )
    inspect_command.add_argument(
        "path",
        type=Path,
        help="Request, graph, component, construct, molecular, contract, context, or check JSON file",
    )
    inspect_command.add_argument(
        "--json", action="store_true", help="Print the normalized full graph"
    )
    reference_build = commands.add_parser(
        "reference-build", help="Build one pinned DNA/RNA reference CDS package offline"
    )
    source = reference_build.add_mutually_exclusive_group(required=True)
    source.add_argument("--alphabet", choices=("DNA", "RNA"))
    source.add_argument(
        "--request", type=Path, help="Frozen ReferenceBuildRequest JSON"
    )
    reference_build.add_argument("--reference-dir", type=Path, required=True)
    reference_build.add_argument(
        "--output", type=Path, required=True, help="Atomic .bcb package destination"
    )
    reference_build.add_argument(
        "--run-metadata",
        type=Path,
        help="Optional RunMetadata JSON, excluded from build identity",
    )
    reference_inspect = commands.add_parser(
        "reference-inspect",
        help="Inspect package integrity without granting fresh acceptance",
    )
    reference_inspect.add_argument("path", type=Path)
    reference_verify = commands.add_parser(
        "reference-verify", help="Rebuild and independently check a package offline"
    )
    reference_verify.add_argument("path", type=Path)
    authority = reference_verify.add_mutually_exclusive_group(required=True)
    authority.add_argument(
        "--expected-build", help="Independently retained canonical build fingerprint"
    )
    authority.add_argument(
        "--expected-request",
        type=Path,
        help="Independently retained ReferenceBuildRequest JSON",
    )
    synthetic_build = commands.add_parser(
        "synthetic-build",
        help="Build a frozen finite-history software-model package offline",
    )
    synthetic_build.add_argument(
        "--request",
        type=Path,
        required=True,
        help="SyntheticBuildRequest JSON binding realization, history, horizon and config",
    )
    synthetic_build.add_argument("--output", type=Path, required=True)
    synthetic_build.add_argument("--run-metadata", type=Path)
    synthetic_inspect = commands.add_parser(
        "synthetic-inspect",
        help="Inspect synthetic package integrity without fresh acceptance",
    )
    synthetic_inspect.add_argument("path", type=Path)
    synthetic_verify = commands.add_parser(
        "synthetic-verify", help="Reconstruct and check a synthetic package offline"
    )
    synthetic_verify.add_argument("path", type=Path)
    synthetic_authority = synthetic_verify.add_mutually_exclusive_group(required=True)
    synthetic_authority.add_argument("--expected-build")
    synthetic_authority.add_argument(
        "--expected-request",
        type=Path,
        help="Independent complete SyntheticBuildRequest JSON, including history/horizon/config",
    )
    for operation in ("check", "explore", "reduce"):
        workflow = commands.add_parser(
            f"synthetic-{operation}",
            help=f"Run a declared {operation} operation and retain scoped software-model evidence",
        )
        workflow.add_argument(
            "--request",
            type=Path,
            required=True,
            help="Complete SyntheticVerificationRequest JSON",
        )
        workflow.add_argument(
            "--output", type=Path, help="Atomic JSON report destination"
        )
    replay = commands.add_parser(
        "synthetic-replay",
        help="Reexecute a report with independent complete operation authority",
    )
    replay.add_argument("path", type=Path)
    replay.add_argument("--expected-request", type=Path, required=True)
    replay.add_argument("--output", type=Path)
    selection = commands.add_parser(
        "synthetic-select",
        help="Check two bounded digital implementations before ranking",
    )
    selection.add_argument(
        "--request",
        type=Path,
        required=True,
        help="SyntheticBuildRequest JSON binding source, history, horizon and policy",
    )
    selection.add_argument(
        "--output", type=Path, help="Atomic selection report destination"
    )
    molecular_build = commands.add_parser(
        "molecular-design-build",
        help="Assemble, independently check and package one software RNA design",
    )
    molecular_build.add_argument("--request", type=Path, required=True)
    molecular_build.add_argument("--output", type=Path, required=True)
    molecular_build.add_argument("--run-metadata", type=Path)
    molecular_inspect = commands.add_parser(
        "molecular-design-inspect",
        help="Inspect a molecular design package without granting fresh acceptance",
    )
    molecular_inspect.add_argument("path", type=Path)
    molecular_verify = commands.add_parser(
        "molecular-design-verify",
        help="Reconstruct a molecular design package from independent authority",
    )
    molecular_verify.add_argument("path", type=Path)
    molecular_authority = molecular_verify.add_mutually_exclusive_group(required=True)
    molecular_authority.add_argument("--expected-build")
    molecular_authority.add_argument("--expected-request", type=Path)
    candidate_build = commands.add_parser(
        "candidate-build", help="Compile a source-rooted RNA research candidate"
    )
    candidate_build.add_argument("--request", type=Path, required=True)
    candidate_build.add_argument("--output", type=Path, required=True)
    for operation in ("verify", "fasta"):
        candidate_command = commands.add_parser(
            "candidate-" + operation,
            help="Independently verify a research candidate" if operation == "verify"
            else "Export verified candidate bases with scope and build identity",
        )
        candidate_command.add_argument("path", type=Path)
        candidate_command.add_argument("--expected-request", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command.startswith("candidate-"):
        return _candidate_command(args)
    if args.command.startswith("molecular-design-"):
        return _molecular_design_command(args)
    if args.command in {
        "synthetic-check",
        "synthetic-explore",
        "synthetic-reduce",
        "synthetic-replay",
    }:
        return _verification_command(args)
    if args.command == "synthetic-select":
        return _selection_command(args)
    if args.command.startswith("synthetic-"):
        return _synthetic_command(args)
    if args.command.startswith("reference-"):
        try:
            if args.command == "reference-build":
                request = (
                    ReferenceBuildRequest.from_json(
                        args.request.read_text(encoding="utf-8")
                    )
                    if args.request
                    else prepare_reference_build(args.alphabet, args.reference_dir)
                )
                metadata = (
                    RunMetadata.from_json(args.run_metadata.read_text(encoding="utf-8"))
                    if args.run_metadata
                    else None
                )
                package = build_reference_package(
                    request, args.reference_dir, run_metadata=metadata
                )
                output = publish_reference_package(package, args.output)
                print(
                    json.dumps(
                        {
                            "output": str(output),
                            "build_fingerprint": package.build_fingerprint,
                            "archive_sha256": package.archive_sha256,
                            "scope": "exact_cds",
                            "intended_use": "software_test",
                            "human_therapeutic_admission": "not_admitted",
                            "status": "complete",
                            "unresolved": [
                                "complete_payload_features",
                                "molecular_behavior",
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                if args.path.stat().st_size > 64 * 1024 * 1024:
                    raise SerializationError(
                        "Reference archive exceeds the size limit."
                    )
                data = args.path.read_bytes()
                if args.command == "reference-verify":
                    expected = (
                        ReferenceBuildRequest.from_json(
                            args.expected_request.read_text(encoding="utf-8")
                        )
                        if args.expected_request
                        else None
                    )
                    package = verify_reference_package(
                        data,
                        expected_request=expected,
                        expected_build_fingerprint=args.expected_build,
                    )
                    print(
                        json.dumps(
                            {
                                "build_fingerprint": package.build_fingerprint,
                                "scope": "exact_cds",
                                "intended_use": "software_test",
                                "human_therapeutic_admission": "not_admitted",
                                "verification": "fresh independent offline reconstruction passed",
                                "unresolved": [
                                    "complete_payload_features",
                                    "molecular_behavior",
                                ],
                            },
                            indent=2,
                        )
                    )
                else:
                    manifest, _, metadata = read_archive(data)
                    if not isinstance(manifest, BuildManifest):
                        raise SerializationError("Expected a reference package.")
                    print(
                        json.dumps(
                            {
                                "build_fingerprint": manifest.build_fingerprint,
                                "scope": manifest.scope,
                                "intended_use": manifest.intended_use,
                                "human_therapeutic_admission": manifest.human_therapeutic_admission,
                                "files": len(manifest.files),
                                "run_metadata": metadata.to_dict()
                                if metadata
                                else None,
                                "inspection": "Historical content and file integrity only; acceptance requires independent authority and current offline reconstruction.",
                            },
                            indent=2,
                        )
                    )
        except (
            OSError,
            UnicodeError,
            SerializationError,
            PipelineError,
            RecursionError,
        ) as exc:
            print(f"biocompiler: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "architecture":
        print(
            "biocompiler pipeline (checked synthetic generation, component linking, reference construct assembly and exact DNA/RNA CDS emission implemented; reproducible reference and synthetic packaging implemented)"
        )
        print("Python authoring -> immutable intent graph")
        print("Implemented candidate path: source product -> bounded RNA architecture/parts -> derived layout -> exact RNA")
        print("Candidate completion: product cassette structure; therapeutic implementation remains partial")
        for stage in STAGE_ORDER:
            print(f"  -> {stage.value}")
        print("  -> packaged digital build artifact")
        print(
            "Independent checking: contract + domain + target + observation map + supplied history"
        )
    elif args.command == "inspect":
        try:
            document = args.path.read_text(encoding="utf-8")
            program = _read_artifact(document)
        except (
            OSError,
            UnicodeError,
            SerializationError,
            json.JSONDecodeError,
            RecursionError,
        ) as exc:
            print(f"biocompiler: {exc}", file=sys.stderr)
            return 2
        print(
            program.to_json() if args.json else json.dumps(_summary(program), indent=2)
        )
    return 0


def _candidate_command(args):
    from biocompiler.compiler.candidate import compile_candidate, export_candidate_fasta, verify_candidate_build
    from biocompiler.ir.candidate import CandidateRequest
    from biocompiler.ir.candidate_build import CandidateBuildRecord

    try:
        if args.command == "candidate-build":
            request = CandidateRequest.from_json(_bounded_text(args.request))
            record = compile_candidate(request).record
            _publish_report(record, args.output, inputs=(args.request,))
        else:
            request = CandidateRequest.from_json(_bounded_text(args.expected_request))
            record = CandidateBuildRecord.from_json(_bounded_text(args.path, limit=64 * 1024 * 1024))
            record = verify_candidate_build(record, expected_request=request)
            if args.command == "candidate-fasta":
                print(export_candidate_fasta(record, expected_request=request), end="")
                return 0
        print(json.dumps(dict(
            build_fingerprint=record.fingerprint, status=record.status,
            scope="product_cassette_structure", therapeutic_implementation="partial",
            human_therapeutic_admission="not_admitted",
            unresolved=[item.id for item in record.requirements.unresolved],
        ), sort_keys=True, indent=2))
        return 0 if record.molecule is not None else 1
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _bounded_text(path, limit=16 * 1024 * 1024):
    with path.open("rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise SerializationError("Input JSON exceeds the size limit.")
    return data.decode("utf-8")


def _publish_report(artifact, destination, *, inputs=()):
    """Atomically retain diagnostics as diagnostics, including nonpassing results."""
    if destination is None:
        return
    if destination.resolve() in {path.resolve() for path in inputs}:
        raise SerializationError(
            "A report cannot overwrite its independent input authority."
        )
    if not destination.parent.is_dir():
        raise SerializationError("Report destination parent must already exist.")
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise SerializationError("Report destination must be a regular file.")
    payload = (artifact.to_json() + "\n").encode("utf-8")
    if len(payload) > 64 * 1024 * 1024:
        raise SerializationError("Verification report exceeds the 64 MiB size limit.")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as target:
            descriptor = None
            if target.write(payload) != len(payload):
                raise OSError("Incomplete verification report write.")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        Path(temporary).unlink(missing_ok=True)


def _verification_summary(record):
    operation = record.request.operation
    result = record.result
    summary = {
        "record_fingerprint": record.fingerprint,
        "request_fingerprint": record.request.fingerprint,
        "operation": operation,
        "mode": record.request.mode,
        "intended_use": "software_test",
        "human_therapeutic_admission": "not_admitted",
        "claim_scope": record.claim_scope,
    }
    if operation == "check":
        summary.update(
            outcome=result.outcome.value,
            diagnostics=[item.to_dict() for item in result.diagnostics],
            counterexamples=[item.to_dict() for item in result.counterexamples],
            coverage=[item.to_dict() for item in result.coverage],
        )
    elif operation == "explore":
        summary.update(
            complete=result.complete,
            all_passed=result.all_passed,
            evaluated_histories=result.evaluated_histories,
            possible_histories=result.possible_histories,
            outcome_counts=dict(result.outcome_counts),
            bounds=result.config.to_dict(),
        )
    else:
        summary.update(
            outcome=result.result.outcome.value,
            one_minimal=result.one_minimal,
            evaluations=result.evaluations,
            original_frames=len(result.original_history),
            reduced_frames=len(result.history),
            selected_failure=result.signature.to_dict(),
        )
    return summary


def _verification_command(args):
    try:
        if args.command == "synthetic-replay":
            authority = SyntheticVerificationRequest.from_json(
                _bounded_text(args.expected_request)
            )
            historical = SyntheticVerificationRecord.from_json(
                _bounded_text(args.path, 64 * 1024 * 1024)
            )
            record = replay_synthetic_verification(
                historical, expected_request=authority
            )
            inputs = (args.path, args.expected_request)
            exit_code = 0  # Reproducing a retained failure is a successful replay.
        else:
            authority = SyntheticVerificationRequest.from_json(
                _bounded_text(args.request)
            )
            if args.command != f"synthetic-{authority.operation}":
                raise SerializationError(
                    "Command and frozen verification operation disagree."
                )
            record = run_synthetic_verification(authority)
            inputs = (args.request,)
            if authority.operation == "check":
                exit_code = 0 if record.result.passed else 1
            elif authority.operation == "explore":
                exit_code = 0 if record.result.all_passed else 1
            else:
                exit_code = 0 if record.result.one_minimal else 1
        _publish_report(record, args.output, inputs=inputs)
        summary = _verification_summary(record)
        if args.command == "synthetic-replay":
            summary["replay"] = (
                "Fresh execution reproduced the declared outcome; this does not turn a failure or unknown into PASS."
            )
        if args.output:
            summary["output"] = str(args.output)
        print(json.dumps(summary, indent=2))
        return exit_code
    except (OSError, UnicodeError, BiocompilerError, RecursionError) as exc:
        print(f"biocompiler: {exc}", file=sys.stderr)
        return 2


def _selection_command(args):
    try:
        request = SyntheticBuildRequest.from_json(_bounded_text(args.request))
        result = select_synthetic(
            request.realization,
            request.history.frames,
            until=request.until,
            config=request.config,
        )
        _publish_report(result, args.output, inputs=(args.request,))
        print(result.to_json())
        return 0 if result.candidate is not None else 1
    except (OSError, UnicodeError, BiocompilerError, RecursionError) as exc:
        print(f"biocompiler: {exc}", file=sys.stderr)
        return 2


def _molecular_design_command(args):
    try:
        if args.command == "molecular-design-build":
            inputs = (args.request, args.run_metadata)
            if args.output.resolve() in {
                path.resolve() for path in inputs if path is not None
            }:
                raise SerializationError(
                    "A design package cannot overwrite its independent input authority."
                )
            request = MolecularDesignRequest.from_json(_bounded_text(args.request))
            metadata = (
                RunMetadata.from_json(_bounded_text(args.run_metadata, 1024 * 1024))
                if args.run_metadata
                else None
            )
            package = build_molecular_design_package(request, run_metadata=metadata)
            output = publish_molecular_design_package(package, args.output)
            summary = {
                "output": str(output),
                "build_fingerprint": package.build_fingerprint,
                "archive_sha256": package.archive_sha256,
                "status": "complete",
            }
        else:
            with args.path.open("rb") as source:
                data = source.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise SerializationError(
                    "Molecular design archive exceeds the size limit."
                )
            if args.command == "molecular-design-verify":
                expected = (
                    MolecularDesignRequest.from_json(
                        _bounded_text(args.expected_request)
                    )
                    if args.expected_request
                    else None
                )
                package = verify_molecular_design_package(
                    data,
                    expected_request=expected,
                    expected_build_fingerprint=args.expected_build,
                )
                summary = {
                    "build_fingerprint": package.build_fingerprint,
                    "verification": "fresh independent offline reconstruction passed",
                }
            else:
                manifest, files, metadata = read_archive(data)
                if not isinstance(manifest, MolecularDesignBuildManifest):
                    raise SerializationError("Expected a molecular design package.")
                summary = {
                    "build_fingerprint": manifest.build_fingerprint,
                    "files": len(files),
                    "run_metadata": metadata.to_dict() if metadata else None,
                    "inspection": "Historical content and file integrity only; acceptance requires independent authority and current offline reconstruction.",
                }
        summary.update(
            scope="software_molecular_design",
            intended_use="software_test",
            human_therapeutic_admission="not_admitted",
            reference_promotion="not_promoted",
            evidence_boundary="software_fixture",
            claim_scope="Exact structural RNA design under frozen fragment, layout and chemistry authority; no biological or experimental-material claim.",
        )
        print(json.dumps(summary, indent=2))
    except (OSError, UnicodeError, BiocompilerError, RecursionError) as exc:
        print(f"biocompiler: {exc}", file=sys.stderr)
        return 2
    return 0


def _synthetic_command(args):
    try:
        if args.command == "synthetic-build":
            request = SyntheticBuildRequest.from_json(_bounded_text(args.request))
            metadata = (
                RunMetadata.from_json(_bounded_text(args.run_metadata, 1024 * 1024))
                if args.run_metadata
                else None
            )
            package = build_synthetic_package(request, run_metadata=metadata)
            scope = package.manifest.scope
            output = publish_synthetic_package(package, args.output)
            summary = {
                "output": str(output),
                "build_fingerprint": package.build_fingerprint,
                "archive_sha256": package.archive_sha256,
                "status": "complete",
            }
        else:
            with args.path.open("rb") as source:
                data = source.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise SerializationError("Synthetic archive exceeds the size limit.")
            if args.command == "synthetic-verify":
                expected = (
                    SyntheticBuildRequest.from_json(
                        _bounded_text(args.expected_request)
                    )
                    if args.expected_request
                    else None
                )
                package = verify_synthetic_package(
                    data,
                    expected_request=expected,
                    expected_build_fingerprint=args.expected_build,
                )
                scope = package.manifest.scope
                summary = {
                    "build_fingerprint": package.build_fingerprint,
                    "verification": "fresh independent offline reconstruction passed",
                }
            else:
                manifest, files, metadata = read_archive(data)
                if not isinstance(manifest, SyntheticBuildManifest):
                    raise SerializationError("Expected a synthetic package.")
                scope = manifest.scope
                summary = {
                    "build_fingerprint": manifest.build_fingerprint,
                    "files": len(files),
                    "run_metadata": metadata.to_dict() if metadata else None,
                    "inspection": "Historical content and file integrity only; acceptance requires independent authority and current offline reconstruction.",
                }
        summary.update(
            scope=scope,
            intended_use="software_test",
            human_therapeutic_admission="not_admitted",
            unresolved=["molecular_behavior"],
            claim_scope="Finite supplied-history software-model evidence only.",
        )
        print(json.dumps(summary, indent=2))
    except (OSError, UnicodeError, BiocompilerError, RecursionError) as exc:
        print(f"biocompiler: {exc}", file=sys.stderr)
        return 2
    return 0
