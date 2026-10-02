"""Compile supported RNA candidates and inspect therapeutic design artifacts."""

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys
import tempfile

from biocompiler import __version__
from biocompiler.ir.executable_payload import PayloadCompilationRequest, PayloadBuild
from biocompiler.ir.architecture_build import PayloadArchitectureRequest, PayloadArchitectureBuild, PayloadArchitectureExport
from biocompiler.ir.payload_architecture import PayloadArchitectureLibrary
from biocompiler.semantics.payload_execution import SourceExecutionManifest
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification
from biocompiler.ir.payload_contracts import PayloadContractLibrary
from biocompiler.semantics.payload_requirements import PayloadRequirements
from biocompiler.verification.executable_payload import PayloadVerification
from biocompiler.artifacts.circuit_review import CircuitReviewAuthority, CircuitReviewManifest, MAX_AUTHORITY_BYTES
from biocompiler.artifacts.circuit_review_bundle import (
    create_circuit_review_bundle, publish_circuit_review_bundle,
)
from biocompiler.verification.circuit_review import (
    inspect_circuit_review_bundle, verify_circuit_review_bundle,
)
from biocompiler.ir.circuit_bindings import CircuitBindingRequest, CircuitEntityBinding
from biocompiler.verification.circuit_bindings import (
    CircuitBindingAssessment, check_circuit_bindings, verify_circuit_binding_assessment,
)
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceObservationBinding, CircuitEvidenceSource, CircuitEvidenceRequest,
    CircuitEvidenceSourceReceipt, CircuitEvidenceReceipt,
)
from biocompiler.verification.circuit_evidence import (
    CircuitEvidenceDependencyStatus, CircuitEvidenceAssessment,
    capture_circuit_evidence, check_circuit_evidence, verify_circuit_evidence_assessment,
)
from biocompiler.ir.circuit_sources import (
    SourceDocument, SourceGap, CircuitSourceCase, SourceReview, CircuitSourceInventory,
)
from biocompiler.verification.circuit_sources import (
    CircuitSourcesAssessment, check_circuit_sources, verify_circuit_sources,
    inspect_circuit_source_readiness,
)
from biocompiler.artifacts.circuit_inspection import (
    inspect_circuit_construction, diff_circuit_constructions,
)
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.artifacts.circuit_construction import ConstructionCandidate
from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.verification.circuit_construction import CircuitConstructionAssessment
from biocompiler.compiler.circuit_construction import (
    build_circuit_construction, verify_circuit_construction, verified_circuit_molecules,
)
from biocompiler.ir.circuit_molecules import CircuitMolecule, CircuitMoleculeSet
from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.verification.circuit_intent import (
    CircuitIntentAssessment, check_circuit_intent, verify_circuit_intent,
)
from biocompiler.ir.circuit_profile import (
    CircuitProfileRequest,
    HumanExperimentContext,
    ImmuneRecipientIdentity,
)
from biocompiler.verification.circuit_profile import (
    CircuitProfileAssessment,
    check_circuit_profile,
    verify_circuit_profile,
)
from biocompiler.ir.candidate import CandidateRequest, CandidateRequirements, MolecularLibrary
from biocompiler.ir.candidate_build import CandidateBuildRecord
from biocompiler.ir.implementation import (
    ImplementationRequest, ImplementationLibrary, ImplementationSelection,
    ImplementationPlan, ImplementationConstruct,
)
from biocompiler.ir.implementation_requirements import ImplementationRequirements
from biocompiler.ir.implementation_build import ImplementationBuildRecord
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


_CIRCUIT_INFRASTRUCTURE_TYPES = (
    CircuitReviewAuthority, CircuitReviewManifest,
    CircuitBindingRequest, CircuitEntityBinding, CircuitBindingAssessment,
    CircuitEvidenceObservationBinding, CircuitEvidenceSource, CircuitEvidenceRequest,
    CircuitEvidenceSourceReceipt, CircuitEvidenceReceipt,
    CircuitEvidenceDependencyStatus, CircuitEvidenceAssessment,
    SourceDocument, SourceGap, CircuitSourceCase, SourceReview, CircuitSourceInventory,
    CircuitSourcesAssessment,
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
                *_CIRCUIT_INFRASTRUCTURE_TYPES,
                CircuitConstructionRequest, ConstructionCandidate, CircuitConstructionBuild, CircuitConstructionAssessment,
                CircuitMolecule,
                CircuitMoleculeSet,
                CircuitMoleculeRecord,
                CircuitRequest,
                CircuitIntentAssessment,
                CircuitProfileRequest,
                HumanExperimentContext,
                ImmuneRecipientIdentity,
                CircuitProfileAssessment,
                AdmissionRequest,
                AdmissionAssessment,
                BuildRequest,
                CandidateRequest,
                ImplementationRequest,
                ImplementationLibrary,
                ImplementationRequirements,
                ImplementationSelection,
                ImplementationPlan,
                ImplementationConstruct,
                ImplementationBuildRecord,
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
                PayloadCompilationRequest,
                PayloadBuild,
                PayloadArchitectureRequest,
                PayloadArchitectureBuild,
                PayloadArchitectureExport,
                PayloadArchitectureLibrary,
                SourceExecutionManifest,
                PayloadArchitectureVerification,
                PayloadContractLibrary,
                PayloadRequirements,
                PayloadVerification,
            )
        }
    )
    if not isinstance(schema, str) or schema not in types:
        raise SerializationError(f"Unknown or missing artifact schema: {schema!r}.")
    if types[schema] in (
        *_CIRCUIT_INFRASTRUCTURE_TYPES,
        CircuitConstructionRequest, ConstructionCandidate, CircuitConstructionBuild, CircuitConstructionAssessment,
        CircuitMolecule,
        CircuitMoleculeSet,
        CircuitMoleculeRecord,
        CircuitRequest,
        CircuitIntentAssessment,
        CircuitProfileRequest,
        HumanExperimentContext,
        ImmuneRecipientIdentity,
        CircuitProfileAssessment,
    ):
        # Preserve the profile's raw-byte limits even for whitespace-padded
        # records inspected through the generic artifact entry point.
        return types[schema].from_json(document)
    return types[schema].from_dict(header)


def _summary(artifact):
    if isinstance(artifact, (IntentProgram, BehaviorProgram)):
        return artifact.summary()
    summary = {
        "schema_version": artifact.schema_version,
        "fingerprint": artifact.fingerprint,
    }
    if isinstance(artifact, (PayloadBuild, PayloadCompilationRequest, PayloadContractLibrary,
                             PayloadRequirements, PayloadVerification)):
        summary.update(scope="contract_conditional_human_immune_rna",
                       verification="not_replayed", empirical_validation="unknown",
                       human_therapeutic_admission="not_admitted")
        if isinstance(artifact, PayloadBuild):
            summary.update(status=artifact.status, selected=dict(artifact.selected),
                           diagnostics=list(artifact.diagnostics), assumptions=list(artifact.assumptions),
                           rna_members=[] if artifact.molecules is None else
                           [item.id for item in artifact.molecules.molecules if item.space.alphabet == "RNA"])
    if isinstance(artifact, (PayloadArchitectureBuild, PayloadArchitectureRequest, PayloadArchitectureExport,
                             PayloadArchitectureLibrary, SourceExecutionManifest, PayloadArchitectureVerification)):
        summary.update(scope="contract_conditional_human_immune_rna_architecture",
                       verification="not_replayed", empirical_validation="unknown",
                       human_therapeutic_admission="not_admitted")
        if isinstance(artifact, PayloadArchitectureBuild):
            summary.update(status=artifact.status,
                           selected=[] if artifact.plan is None else list(artifact.plan.selected_refinement_ids),
                           diagnostics=[item.to_dict() for item in artifact.diagnostics],
                           requirements=[] if artifact.plan is None else [item.to_dict() for item in artifact.plan.ledger])
    if isinstance(artifact, (CircuitReviewAuthority, CircuitReviewManifest)):
        summary.update(
            scope="retained_circuit_review", verification="not_replayed",
            reviewed_reference_correspondence="not_established",
            human_biological_applicability="unassessed", human_admission="not_admitted",
        )
    if isinstance(artifact, (SourceDocument, SourceGap, CircuitSourceCase, SourceReview, CircuitSourceInventory, CircuitSourcesAssessment)):
        summary.update(
            scope="source_metadata_only", source_bytes="not_checked",
            molecular_readiness="unassessed", empirical_validation="unknown",
            human_admission="not_admitted",
        )
        if isinstance(artifact, CircuitSourceInventory):
            summary.update(sources=len(artifact.sources), cases=len(artifact.cases), reviews=len(artifact.reviews))
        elif isinstance(artifact, CircuitSourcesAssessment):
            summary.update(outcome=artifact.outcome.value, claim_scope=artifact.claim_scope,
                           diagnostics=list(artifact.diagnostics))
        elif isinstance(artifact, SourceDocument):
            summary.update(id=artifact.id, access_status=artifact.access_status,
                           reuse_status=artifact.reuse_status, correction_status=artifact.correction_status)
        elif isinstance(artifact, SourceGap):
            summary.update(field=artifact.field, availability=artifact.status)
        elif isinstance(artifact, CircuitSourceCase):
            summary.update(id=artifact.id, family_id=artifact.family_id,
                           missing_field_count=sum(item.status != "provided" for item in artifact.coverage))
        elif isinstance(artifact, SourceReview):
            summary.update(id=artifact.id, subject_kind=artifact.subject_kind,
                           disposition=artifact.disposition)
    if isinstance(artifact, (CircuitBindingRequest, CircuitEntityBinding, CircuitBindingAssessment)):
        summary.update(scope="supplied_nominal_binding_correspondence",
                       independent_entity_identity="unestablished", molecular_implementation="unimplemented",
                       biological_function="unestablished", empirical_validation="unknown",
                       human_therapeutic_admission="not_admitted")
        if isinstance(artifact, CircuitBindingRequest):
            summary.update(bindings=len(artifact.bindings), assumptions=list(artifact.assumptions))
        elif isinstance(artifact, CircuitEntityBinding):
            summary.update(id=artifact.id, requirement_id=artifact.requirement_id,
                           source_kind=artifact.source_kind, source_id=artifact.source_id,
                           role_id=artifact.role_id, subject_kind=artifact.subject_kind)
        elif isinstance(artifact, CircuitBindingAssessment):
            summary.update(outcome=artifact.outcome.value, complete_nominal_bindings=artifact.complete,
                           assumptions=list(artifact.assumptions), diagnostics=list(artifact.diagnostics),
                           provider_availability=artifact.provider_availability,
                           provider_colocation=artifact.provider_colocation)
    if isinstance(artifact, (CircuitEvidenceObservationBinding, CircuitEvidenceSource, CircuitEvidenceRequest,
                             CircuitEvidenceSourceReceipt, CircuitEvidenceReceipt,
                             CircuitEvidenceDependencyStatus, CircuitEvidenceAssessment)):
        summary.update(scope="declared_evidence_dependencies_only", prediction="unsupported",
                       empirical_validation="unknown", evidence_applicability="unassessed",
                       human_therapeutic_admission="not_admitted")
        if isinstance(artifact, CircuitEvidenceAssessment):
            summary.update(freshness=artifact.freshness, construction_status=artifact.construction_status,
                           missing_evidence=artifact.missing_evidence,
                           dependencies=[dict(item.to_dict(), status=item.status) for item in artifact.dependencies])
        elif isinstance(artifact, (CircuitEvidenceRequest, CircuitEvidenceReceipt)):
            summary.update(sources=len(artifact.sources))
        elif isinstance(artifact, CircuitEvidenceSource):
            summary.update(id=artifact.id, kind=artifact.kind, use=artifact.use,
                           version=artifact.version, population_scope=artifact.population_scope,
                           observation_bindings=len(artifact.observations))
        elif isinstance(artifact, CircuitEvidenceDependencyStatus):
            summary.update(id=artifact.id, dependency_status=artifact.status)
    if isinstance(artifact, (CircuitMolecule, CircuitMoleculeSet, CircuitMoleculeRecord)):
        summary.update(
            scope="declared_molecular_identity",
            source_correspondence="unverified", molecular_function="unestablished",
            molecular_assembly="unverified", human_therapeutic_admission="not_admitted",
            inspection="Supplied molecular declarations only; no checked transformation, circuit implementation or experimental validation.",
        )
        if isinstance(artifact, CircuitMolecule):
            summary.update(
                form=artifact.form, alphabet=artifact.space.alphabet,
                topology=artifact.space.topology, sequence_extent=artifact.sequence_extent,
                spelling_identity=artifact.spelling_identity,
                declared_nominal_identity=artifact.declared_nominal_identity,
                declared_nominal_complete=artifact.declared_nominal_complete,
                base_rotation_identity=artifact.base_rotation_identity,
            )
        else:
            bundle = artifact.bundle if isinstance(artifact, CircuitMoleculeRecord) else artifact
            summary.update(
                purpose=bundle.request.profile.purpose,
                requested_form=bundle.request.requested_form,
                molecule_records=len(bundle.molecules), complex_records=len(bundle.complexes),
                role_instances=len(bundle.role_instances),
                declared_nominal_bundle_identity=bundle.declared_nominal_bundle_identity,
                declared_nominal_complete=bundle.declared_nominal_complete,
            )
            if isinstance(artifact, CircuitMoleculeRecord):
                summary.update(experimental_specification_identity=artifact.experimental_specification_identity)
    if isinstance(artifact, (CircuitConstructionRequest, ConstructionCandidate, CircuitConstructionBuild, CircuitConstructionAssessment)):
        summary.update(scope="supplied_construction_correspondence", source_fidelity="unestablished",
                       biological_function="unestablished", human_therapeutic_admission="not_admitted",
                       inspection="Historical or proposed record; fresh verification requires independent complete construction authority.")
        if isinstance(artifact, CircuitConstructionRequest):
            summary.update(steps=len(artifact.steps), required_members=len(artifact.requirements), mode=artifact.mode)
        elif isinstance(artifact, ConstructionCandidate):
            summary.update(constructed_values=len(artifact.values), missing_members=list(artifact.missing_members), diagnostics=list(artifact.diagnostics))
        else:
            assessment = artifact.assessment if isinstance(artifact, CircuitConstructionBuild) else artifact
            summary.update(outcome=assessment.outcome.value, complete_supplied_construction=assessment.complete, diagnostics=list(assessment.diagnostics))
    if isinstance(artifact, CircuitRequest):
        summary.update(
            purpose=artifact.profile.purpose, mode=artifact.profile.mode,
            requested_form=artifact.requested_form, fidelity_scope=artifact.fidelity_scope,
            deployment_id=artifact.deployment_id, requirements=len(artifact.requirements),
            inspection="Declared typed intent only; molecular implementation remains unsupported.",
        )
    if isinstance(artifact, CircuitIntentAssessment):
        summary.update(
            intent_consistency=artifact.intent_consistency,
            outcome=artifact.outcome.value,
            molecular_implementation=artifact.molecular_implementation,
            empirical_validation=artifact.empirical_validation,
            human_therapeutic_admission=artifact.human_therapeutic_admission,
            diagnostics=list(artifact.diagnostics),
            inspection="Historical consistency record; fresh verification requires independent complete request authority.",
        )
    if isinstance(artifact, CircuitProfileRequest):
        summary.update(
            purpose=artifact.purpose,
            mode=artifact.mode,
            molecular_form=artifact.molecular_form.value,
            boundary=artifact.boundary,
            inspection="Declared scope only; molecular compilation is not implemented.",
        )
    if isinstance(artifact, CircuitProfileAssessment):
        summary.update(
            purpose=artifact.request.purpose,
            boundary=artifact.boundary,
            eligibility=artifact.eligibility,
            dimensions=dict(artifact.dimensions),
            diagnostics=list(artifact.diagnostics),
            molecular_generation=artifact.molecular_generation,
            human_therapeutic_admission=artifact.human_therapeutic_admission,
            inspection="Historical scope assessment; fresh verification requires independent complete request authority.",
        )
    if isinstance(artifact, CandidateBuildRecord):
        summary.update(
            status=artifact.status, scope="product_cassette_structure",
            therapeutic_implementation="partial", human_therapeutic_admission="not_admitted",
            inspection="Historical candidate only; fresh verification requires independent complete request authority.",
        )
    if isinstance(artifact, ImplementationRequirements):
        summary.update(
            scope=artifact.scope, supported_profile=artifact.supported_profile,
            products=[item.product for item in artifact.products],
            obligations=len(artifact.obligations),
            diagnostics=[item.to_dict() for item in artifact.diagnostics],
            physical_function="unestablished",
            inspection="Historical analysis; compare against the independently retained source.",
        )
    if isinstance(artifact, ImplementationBuildRecord):
        summary.update(_implementation_summary(artifact))
        summary["inspection"] = "Historical build; fresh verification requires independent complete request authority."
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


def _architecture_core_arguments(command, verification):
    executable = command.add_mutually_exclusive_group()
    executable.add_argument("--core-executable", type=Path,
                            help="Use the explicitly selected absolute-path OCaml core")
    if verification:
        executable.add_argument("--verifier-executable", type=Path,
                                help="Use the absolute-path standalone OCaml verifier")
    command.add_argument("--core-sha256", help="Require this SHA-256 for the selected executable")
    command.add_argument("--core-timeout", type=float,
                         help="Positive finite timeout in seconds (requires an executable)")


def _workflow_core_arguments(command):
    executable = command.add_mutually_exclusive_group()
    executable.add_argument("--core-executable", type=Path, help=argparse.SUPPRESS)
    executable.add_argument("--verify-executable", type=Path, help=argparse.SUPPRESS)
    command.add_argument("--core-sha256", help=argparse.SUPPRESS)
    command.add_argument("--core-timeout", type=float, help=argparse.SUPPRESS)


def _synthetic_producer_core_arguments(command):
    command.add_argument("--core-executable", type=Path, help=argparse.SUPPRESS)
    command.add_argument("--core-sha256", help=argparse.SUPPRESS)
    command.add_argument("--core-timeout", type=float, help=argparse.SUPPRESS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"biocompiler {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _register_circuit_infrastructure_commands(commands)
    architecture_build = commands.add_parser("architecture-build", help="Select supplied implementations and complete RNA partitions")
    architecture_build.add_argument("--request", type=Path, required=True)
    architecture_build.add_argument("--output", type=Path, required=True)
    _architecture_core_arguments(architecture_build, False)
    for operation in ("verify", "export"):
        command = commands.add_parser("architecture-" + operation, help="Independently verify RNA architecture or export FASTA with its manifest")
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
        if operation == "export":
            command.add_argument("--output", type=Path, required=True)
        _architecture_core_arguments(command, operation == "verify")
    payload_build = commands.add_parser("payload-build", help="Compile therapeutic intent to RNA under supplied executable contracts")
    payload_build.add_argument("--request", type=Path, required=True)
    payload_build.add_argument("--output", type=Path, required=True)
    for operation in ("verify", "fasta"):
        command = commands.add_parser("payload-" + operation, help="Independently reconstruct payload translation and RNA")
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
    construction_build = commands.add_parser("circuit-build", help="Build and independently check an explicit supplied construction")
    construction_build.add_argument("--request", type=Path, required=True)
    construction_build.add_argument("--output", type=Path, required=True)
    for operation in ("verify", "export"):
        command = commands.add_parser("circuit-" + operation, help="Freshly verify supplied construction" if operation == "verify" else "Publish the freshly verified complete set and its construction authority")
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
        if operation == "export":
            command.add_argument("--output", type=Path, required=True)
    intent_check = commands.add_parser(
        "circuit-intent-check",
        help="Check complete typed circuit intent without molecular generation",
    )
    intent_check.add_argument("--request", type=Path, required=True)
    intent_check.add_argument("--output", type=Path, required=True)
    intent_verify = commands.add_parser(
        "circuit-intent-verify",
        help="Replay intent consistency against independent complete authority",
    )
    intent_verify.add_argument("path", type=Path)
    intent_verify.add_argument("--expected-request", type=Path, required=True)
    circuit_check = commands.add_parser(
        "circuit-profile-check",
        help="Check declared human circuit scope without compiling a molecule",
    )
    circuit_check.add_argument("--request", type=Path, required=True)
    circuit_check.add_argument("--output", type=Path, required=True)
    circuit_verify = commands.add_parser(
        "circuit-profile-verify",
        help="Recheck a scope assessment against independent request authority",
    )
    circuit_verify.add_argument("path", type=Path)
    circuit_verify.add_argument("--expected-request", type=Path, required=True)
    studio = commands.add_parser(
        "studio", help="Open the guided local design workspace in your browser"
    )
    studio.add_argument(
        "--port", type=int, default=8765,
        help="Local port (default: 8765; use 0 to choose an available port)",
    )
    studio.add_argument(
        "--no-open", action="store_true",
        help="Print the local URL without opening a browser",
    )
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
        _workflow_core_arguments(workflow)
    replay = commands.add_parser(
        "synthetic-replay",
        help="Reexecute a report with independent complete operation authority",
    )
    replay.add_argument("path", type=Path)
    replay.add_argument("--expected-request", type=Path, required=True)
    replay.add_argument("--output", type=Path)
    _workflow_core_arguments(replay)
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
    _synthetic_producer_core_arguments(selection)
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
    implementation_analyze = commands.add_parser(
        "implementation-analyze", help="Inspect full therapeutic implementation obligations"
    )
    implementation_analyze.add_argument("--request", type=Path, required=True)
    implementation_analyze.add_argument("--output", type=Path, required=True)
    implementation_build = commands.add_parser(
        "implementation-build", help="Compile a checked declared precursor RNA architecture"
    )
    implementation_build.add_argument("--request", type=Path, required=True)
    implementation_build.add_argument("--output", type=Path, required=True)
    for operation in ("verify", "fasta"):
        command = commands.add_parser(
            "implementation-" + operation,
            help="Freshly verify a molecular implementation build" if operation == "verify"
            else "Export independently verified precursor RNA with completion scope",
        )
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in {"architecture-build", "architecture-verify", "architecture-export"}:
        return _architecture_command(args)
    if args.command in {"payload-build", "payload-verify", "payload-fasta"}:
        return _payload_command(args)
    if args.command in _CIRCUIT_INFRASTRUCTURE_COMMANDS:
        return _circuit_infrastructure_command(args)
    if args.command in {"circuit-build", "circuit-verify", "circuit-export"}:
        return _circuit_construction_command(args)
    if args.command.startswith("circuit-intent-"):
        return _circuit_intent_command(args)
    if args.command.startswith("circuit-profile-"):
        return _circuit_profile_command(args)
    if args.command == "studio":
        if not 0 <= args.port <= 65535:
            parser.error("studio --port must be between 0 and 65535")
        from biocompiler.studio.server import serve

        try:
            serve(port=args.port, open_browser=not args.no_open)
        except OSError as exc:
            print(
                f"Unable to start the local workspace: {exc}. "
                "Try biocompiler studio --port 0.",
                file=sys.stderr,
            )
            return 2
        return 0
    if args.command.startswith("candidate-"):
        return _candidate_command(args)
    if args.command.startswith("implementation-"):
        return _implementation_command(args)
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
            "biocompiler pipeline: therapeutic program design -> complete supplied RNA architectures for human immune cells in vivo"
        )
        print("Python authoring -> immutable intent graph")
        print("Architecture path: executable source -> supplied composite contracts -> components, helpers and recipient/RNA partitions -> exact RNA plus manifest")
        print("Independent translation checks: source meaning, control domains, dependency grounding, complete template authority and every emitted molecule")
        print("Earlier cassette candidate path: source product -> bounded RNA architecture/parts -> derived layout -> exact RNA; functional requirements remain partial in that profile")
        print("Shared infrastructure: checked synthetic generation, component linking, reference assembly, exact DNA/RNA CDS emission and reproducible packaging")
        for stage in STAGE_ORDER:
            print(f"  -> {stage.value}")
        print("  -> packaged digital build artifact")
        print(
            "Independent checking: contract + domain + target + observation map + supplied history"
        )
    elif args.command == "inspect":
        try:
            document = _bounded_text(args.path)
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


_CIRCUIT_INFRASTRUCTURE_COMMANDS = frozenset({
    "circuit-review-create", "circuit-review-inspect", "circuit-review-verify",
    "circuit-inspect", "circuit-diff", "circuit-sources-check", "circuit-sources-verify",
    "circuit-sources-readiness", "circuit-bindings-check", "circuit-bindings-verify",
    "circuit-evidence-capture", "circuit-evidence-check", "circuit-evidence-verify",
})


def _register_circuit_infrastructure_commands(commands):
    for operation in ("create", "inspect", "verify"):
        command = commands.add_parser(
            "circuit-review-" + operation,
            help="Package or review retained circuit records without granting biological acceptance",
        )
        command.add_argument("path", type=Path, help="Retained build JSON for create; review .bcb archive otherwise")
        command.add_argument("--output", type=Path, required=operation == "create")
        if operation != "inspect":
            command.add_argument("--expected-authority", type=Path, required=True,
                                 help="Separately retained complete CircuitReviewAuthority JSON")
        if operation == "create":
            command.add_argument("--source-assessment", type=Path)
            command.add_argument("--binding-assessment", type=Path)
            command.add_argument("--evidence-receipt", type=Path)
            command.add_argument("--evidence-assessment", type=Path)
    command = commands.add_parser("circuit-inspect", help="Inspect a retained construction without inferring biological function")
    command.add_argument("path", type=Path)
    command.add_argument("--expected-request", type=Path)
    command.add_argument("--output", type=Path)
    command = commands.add_parser("circuit-diff", help="Compare retained construction records and exact identities")
    command.add_argument("before", type=Path)
    command.add_argument("after", type=Path)
    command.add_argument("--expected-before", type=Path)
    command.add_argument("--expected-after", type=Path)
    command.add_argument("--max-changes", type=int, default=256)
    command.add_argument("--output", type=Path)
    command = commands.add_parser("circuit-sources-check", help="Check declared source metadata relationships")
    command.add_argument("--inventory", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("circuit-sources-verify", help="Replay a source metadata assessment against independent inventory")
    command.add_argument("path", type=Path)
    command.add_argument("--expected-inventory", type=Path, required=True)
    command = commands.add_parser("circuit-sources-readiness", help="Inspect missing source fields without granting case acceptance")
    command.add_argument("path", type=Path)
    command.add_argument("--case-id")
    command.add_argument("--output", type=Path)
    for operation in ("check", "verify"):
        command = commands.add_parser("circuit-bindings-" + operation, help="Check supplied nominal bindings against fresh construction replay")
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
        if operation == "check":
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--candidate", type=Path, required=True)
    for operation in ("capture", "check", "verify"):
        command = commands.add_parser("circuit-evidence-" + operation, help="Capture or replay evidence dependency metadata without biological validation")
        command.add_argument("path", type=Path)
        command.add_argument("--expected-request", type=Path, required=True)
        if operation != "capture":
            command.add_argument("--build", type=Path, required=True)
        if operation == "verify":
            command.add_argument("--receipt", type=Path, required=True)
        else:
            command.add_argument("--output", type=Path, required=True)


class _InspectionReport:
    """Publication wrapper for bounded display data, never verification authority."""

    def __init__(self, document):
        self.document = document

    def to_json(self):
        return json.dumps(self.document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _circuit_infrastructure_command(args):
    if args.command.startswith("circuit-review-"):
        return _circuit_review_command(args)
    def read(cls, path, limit=4_000_000):
        return cls.from_json(_bounded_text(path, limit))

    try:
        if args.command == "circuit-inspect":
            request = None if args.expected_request is None else read(CircuitConstructionRequest, args.expected_request)
            document = inspect_circuit_construction(read(CircuitConstructionBuild, args.path), expected_request=request)
            report, summary, code = _InspectionReport(document), document, 0
        elif args.command == "circuit-diff":
            before = None if args.expected_before is None else read(CircuitConstructionRequest, args.expected_before)
            after = None if args.expected_after is None else read(CircuitConstructionRequest, args.expected_after)
            document = diff_circuit_constructions(
                read(CircuitConstructionBuild, args.before), read(CircuitConstructionBuild, args.after),
                expected_before=before, expected_after=after, max_changes=args.max_changes,
            )
            report, summary, code = _InspectionReport(document), document, 0
        elif args.command == "circuit-sources-readiness":
            document = inspect_circuit_source_readiness(read(CircuitSourceInventory, args.path), case_id=args.case_id)
            report, summary = _InspectionReport(document), document
            code = 0 if document["metadata_consistency"] == "pass" else 1
        elif args.command == "circuit-sources-check":
            report = check_circuit_sources(read(CircuitSourceInventory, args.inventory))
            summary, code = _summary(report), 0 if report.outcome.value == "pass" else 1
        elif args.command == "circuit-sources-verify":
            report = verify_circuit_sources(
                read(CircuitSourcesAssessment, args.path, 12_000_000),
                expected_inventory=read(CircuitSourceInventory, args.expected_inventory),
            )
            summary, code = _summary(report), 0 if report.outcome.value == "pass" else 1
        elif args.command.startswith("circuit-bindings-"):
            request = read(CircuitBindingRequest, args.expected_request)
            candidate_path = args.path if args.command == "circuit-bindings-check" else args.candidate
            candidate = read(ConstructionCandidate, candidate_path)
            if args.command == "circuit-bindings-check":
                report = check_circuit_bindings(candidate, expected_request=request)
            else:
                report = verify_circuit_binding_assessment(read(CircuitBindingAssessment, args.path), candidate, expected_request=request)
            summary, code = _summary(report), 0 if report.passed else 1
        else:
            request = read(CircuitEvidenceRequest, args.expected_request)
            build_path = args.path if args.command == "circuit-evidence-capture" else args.build
            build = read(CircuitConstructionBuild, build_path)
            if args.command == "circuit-evidence-capture":
                report = capture_circuit_evidence(build, expected_request=request)
                code = 0
            else:
                receipt_path = args.path if args.command == "circuit-evidence-check" else args.receipt
                receipt = read(CircuitEvidenceReceipt, receipt_path)
                if args.command == "circuit-evidence-check":
                    report = check_circuit_evidence(receipt, build, expected_request=request)
                else:
                    report = verify_circuit_evidence_assessment(read(CircuitEvidenceAssessment, args.path), receipt, build, expected_request=request)
                code = 0 if report.freshness == "current" else 1
            summary = _summary(report)
        destination = getattr(args, "output", None)
        # Preserve every independent input, including aliases resolved through
        # symbolic links. The destination itself is not an input authority.
        protected = tuple(value for key, value in vars(args).items() if key != "output" and isinstance(value, Path))
        _publish_report(report, destination, inputs=protected)
        print(json.dumps(summary, sort_keys=True, indent=2))
        return code
    except (BiocompilerError, OSError, ValueError, TypeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _circuit_review_command(args):
    """Offline review archives require external authority even after relocation."""
    def read(cls, path):
        limit = MAX_AUTHORITY_BYTES if cls is CircuitReviewAuthority else 16 * 1024 * 1024
        return cls.from_json(_bounded_text(path, limit))

    try:
        inputs = tuple(value for key, value in vars(args).items()
                       if key != "output" and isinstance(value, Path))
        if args.output is not None and args.output.resolve() in {p.resolve() for p in inputs}:
            raise SerializationError("A review output cannot overwrite its independent input authority.")
        if args.command == "circuit-review-create":
            authority = read(CircuitReviewAuthority, args.expected_authority)
            records = {}
            for name, cls in (
                ("source_assessment", CircuitSourcesAssessment),
                ("binding_assessment", CircuitBindingAssessment),
                ("evidence_receipt", CircuitEvidenceReceipt),
                ("evidence_assessment", CircuitEvidenceAssessment),
            ):
                path = getattr(args, name)
                records[name] = None if path is None else read(cls, path)
            bundle = create_circuit_review_bundle(
                read(CircuitConstructionBuild, args.path),
                expected_authority=authority, **records,
            )
            publish_circuit_review_bundle(bundle, args.output, expected_authority=authority)
            summary = verify_circuit_review_bundle(bundle.data, expected_authority=authority)
        else:
            with args.path.open("rb") as source:
                data = source.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise SerializationError("Circuit review archive exceeds the size limit.")
            if args.command == "circuit-review-inspect":
                summary = inspect_circuit_review_bundle(data)
            else:
                summary = verify_circuit_review_bundle(
                    data, expected_authority=read(CircuitReviewAuthority, args.expected_authority),
                )
            _publish_report(_InspectionReport(summary), args.output, inputs=inputs)
        print(json.dumps(summary, sort_keys=True, indent=2))
        # Successful replay describes agreement, including honest failures and
        # unsupported claims. Inspect individual tracks for scientific status.
        return 0
    except (BiocompilerError, OSError, ValueError, TypeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _circuit_construction_command(args):
    try:
        if args.command == "circuit-build":
            request = CircuitConstructionRequest.from_json(_bounded_text(args.request, 4_000_000))
            build = build_circuit_construction(request)
            verify_circuit_construction(build, expected_request=request)
            _publish_report(build, args.output, inputs=(args.request,))
            assessment = build.assessment
        else:
            request = CircuitConstructionRequest.from_json(_bounded_text(args.expected_request, 4_000_000))
            build = CircuitConstructionBuild.from_json(_bounded_text(args.path, 4_000_000))
            assessment = verify_circuit_construction(build, expected_request=request)
            if args.command == "circuit-export":
                verified_circuit_molecules(build, expected_request=request)
                # Preserve all roots, operations, chemistry, amounts and receipts.
                # A standalone base-only file would lose required construction authority.
                _publish_report(build, args.output, inputs=(args.path, args.expected_request))
        print(json.dumps(_summary(assessment), sort_keys=True, indent=2))
        return 0 if assessment.passed else 1
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _circuit_intent_command(args):
    try:
        if args.command == "circuit-intent-check":
            request = CircuitRequest.from_json(_bounded_text(args.request))
            assessment = check_circuit_intent(request)
            verify_circuit_intent(assessment, expected_request=request)
            _publish_report(assessment, args.output, inputs=(args.request,))
        else:
            request = CircuitRequest.from_json(_bounded_text(args.expected_request))
            assessment = CircuitIntentAssessment.from_json(_bounded_text(args.path))
            assessment = verify_circuit_intent(assessment, expected_request=request)
        print(json.dumps(_summary(assessment), sort_keys=True, indent=2))
        return 0
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _circuit_profile_command(args):
    try:
        if args.command == "circuit-profile-check":
            request = CircuitProfileRequest.from_json(_bounded_text(args.request))
            assessment = check_circuit_profile(request)
            verify_circuit_profile(assessment, expected_request=request)
            _publish_report(assessment, args.output, inputs=(args.request,))
        else:
            request = CircuitProfileRequest.from_json(
                _bounded_text(args.expected_request)
            )
            assessment = CircuitProfileAssessment.from_json(_bounded_text(args.path))
            assessment = verify_circuit_profile(assessment, expected_request=request)
        print(json.dumps(_summary(assessment), sort_keys=True, indent=2))
        # This command checks scope/record consistency, not molecular capability.
        return 0
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _implementation_summary(record):
    return dict(
        build_fingerprint=record.fingerprint,
        status=record.status,
        scope=record.scope,
        selected_architecture=record.selection.selected_architecture_id,
        structural_completion=record.molecule is not None,
        physical_function="unestablished",
        therapeutic_implementation="partial",
        human_therapeutic_admission="not_admitted",
        unresolved=[item.id for item in record.requirements.obligations],
        diagnostics=[item.to_dict() for item in record.requirements.diagnostics],
        selection_diagnostics=list(record.selection.diagnostics),
        alternatives=[item.to_dict() for item in record.selection.alternatives],
    )


def _architecture_core_client(args):
    from biocompiler.core_client import CoreClient

    verifier = getattr(args, "verifier_executable", None)
    executable = args.core_executable if args.core_executable is not None else verifier
    if executable is None:
        if args.core_sha256 is not None or args.core_timeout is not None:
            raise SerializationError("Core timeout and digest options require an explicit executable.")
        return None
    return CoreClient(executable, role="verify" if verifier is not None else "core",
                      expected_sha256=args.core_sha256,
                      timeout_seconds=30.0 if args.core_timeout is None else args.core_timeout)


def _architecture_core_command(args, core):
    from biocompiler.architecture_backend import compile_document, check_document, export_document
    from biocompiler.core_client import LIMITS, decode_json

    def document(path):
        # Preserve the supplied JSON before domain normalization; the native
        # result separately binds supplied and normalized authority identities.
        return decode_json(_bounded_text(path).encode("utf-8"), limit=LIMITS["max_request_bytes"])

    if args.command == "architecture-build":
        build, assessment, _ = compile_document(document(args.request), core=core)
        _publish_report(build, args.output, inputs=(args.request,))
    else:
        request, candidate = document(args.expected_request), document(args.path)
        if args.command == "architecture-export":
            bundle, build, assessment, _ = export_document(
                expected_request=request, build=candidate, core=core)
            _publish_report(bundle, args.output, inputs=(args.path, args.expected_request))
        else:
            build, assessment, _ = check_document(expected_request=request, build=candidate, core=core)
    return build, assessment


def _architecture_command(args):
    from biocompiler.core_client import CoreError

    try:
        core = _architecture_core_client(args)
        if core is not None:
            build, assessment = _architecture_core_command(args, core)
        else:
            from biocompiler.compiler.payload_architecture import compile_payload_architecture, export_payload_architecture
            from biocompiler.verification.payload_architecture import check_payload_architecture

            if args.command == "architecture-build":
                request = PayloadArchitectureRequest.from_json(_bounded_text(args.request))
                build = compile_payload_architecture(request)
                _publish_report(build, args.output, inputs=(args.request,))
            else:
                request = PayloadArchitectureRequest.from_json(_bounded_text(args.expected_request))
                build = PayloadArchitectureBuild.from_json(_bounded_text(args.path))
            assessment = check_payload_architecture(build, expected_request=request)
            if args.command == "architecture-export":
                bundle = export_payload_architecture(build, expected_request=request)
                _publish_report(bundle, args.output, inputs=(args.path, args.expected_request))
        print(json.dumps({"status": build.status, "verification": assessment.to_dict(),
                          "diagnostics": [item.to_dict() for item in build.diagnostics]}, sort_keys=True, indent=2))
        return 0 if assessment.passed and build.construction is not None else 1
    except (BiocompilerError, CoreError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _payload_command(args):
    from biocompiler.compiler.executable_payload import compile_payload, export_payload_fasta
    from biocompiler.verification.executable_payload import check_payload_build
    try:
        if args.command == "payload-build":
            request = PayloadCompilationRequest.from_json(_bounded_text(args.request))
            build = compile_payload(request)
            _publish_report(build, args.output, inputs=(args.request,))
        else:
            request = PayloadCompilationRequest.from_json(_bounded_text(args.expected_request))
            build = PayloadBuild.from_json(_bounded_text(args.path))
        assessment = check_payload_build(build, expected_request=request)
        if args.command == "payload-fasta":
            print(export_payload_fasta(build, expected_request=request), end="")
            return 0
        print(json.dumps({"status": build.status, "verification": assessment.to_dict(),
                          "diagnostics": list(build.diagnostics),
                          "human_therapeutic_admission": "not_admitted"}, sort_keys=True, indent=2))
        return 0 if assessment.outcome == "pass" and build.construction is not None else 1
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


def _implementation_command(args):
    from biocompiler.compiler.implementation import (
        compile_implementation, export_implementation_fasta,
        verify_implementation_build, verify_implementation_requirements,
    )
    from biocompiler.compiler.implementation_requirements import analyze_implementation_requirements
    from biocompiler.ir.implementation_requirements import source_request_from_dict

    try:
        if args.command == "implementation-analyze":
            source = source_request_from_dict(parse_json(_bounded_text(args.request)))
            report = analyze_implementation_requirements(source)
            verify_implementation_requirements(report, expected_source=source)
            _publish_report(report, args.output, inputs=(args.request,))
            print(json.dumps(_summary(report), sort_keys=True, indent=2))
            return 0  # Successful analysis is not a claim of implementability.
        if args.command == "implementation-build":
            request = ImplementationRequest.from_json(_bounded_text(args.request))
            record = compile_implementation(request).record
            _publish_report(record, args.output, inputs=(args.request,))
        else:
            request = ImplementationRequest.from_json(_bounded_text(args.expected_request))
            record = ImplementationBuildRecord.from_json(_bounded_text(args.path, limit=64 * 1024 * 1024))
            record = verify_implementation_build(record, expected_request=request)
            if args.command == "implementation-fasta":
                print(export_implementation_fasta(record, expected_request=request), end="")
                return 0
        print(json.dumps(_implementation_summary(record), sort_keys=True, indent=2))
        return 0 if record.molecule is not None else 1
    except (BiocompilerError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


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
    if any(getattr(args, name, None) is not None for name in
           ("core_executable", "verify_executable", "core_sha256", "core_timeout")):
        from biocompiler.workflow_cli import selected_core_command

        return selected_core_command(args, bounded_text=_bounded_text, publish_report=_publish_report)
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
    if any(getattr(args, name, None) is not None for name in ("core_executable", "core_sha256", "core_timeout")):
        from biocompiler.synthetic_producer_cli import selection_command
        return selection_command(args, bounded_text=_bounded_text, publish_report=_publish_report)
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
