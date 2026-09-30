"""Inspect versioned compiler artifacts and the compiler architecture."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from biocompiler import __version__
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
    if isinstance(artifact, (MolecularArtifact, SyntheticCandidate, BuildManifest)):
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
    args = parser.parse_args(argv)
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
            "biocompiler pipeline (checked synthetic generation, component linking, reference construct assembly and exact DNA/RNA CDS emission implemented; reproducible reference packaging implemented)"
        )
        print("Python authoring -> immutable intent graph")
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
