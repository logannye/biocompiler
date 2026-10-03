"""Checked source-to-precursor research compilation and independent saved replay."""

from dataclasses import dataclass
from urllib.parse import quote

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.backends.implementation import EMITTER_VERSION, emit_implementation
from biocompiler.compiler.implementation_requirements import (
    ANALYZER_VERSION,
    analyze_implementation_requirements,
)
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    CompletionProfile,
    PassContract,
    PassManager,
    PipelineError,
    ScopedObligation,
)
from biocompiler.ir.implementation import PROFILE_VERSION, ImplementationRequest
from biocompiler.ir.implementation_build import (
    COMPLETION_SCOPE,
    ImplementationBuildRecord,
    ImplementationComponents,
    ImplementationPlanning,
    ImplementationStage,
)
from biocompiler.ir.implementation_requirements import (
    PROFILE_VERSION as REQUIREMENTS_PROFILE,
    ImplementationRequirements,
    source_request_from_dict,
)
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.ir.stages import Stage
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.context import TargetContext
from biocompiler.synthesis.implementation import (
    GENERATOR_VERSION,
    derive_implementation_construct,
    derive_implementation_plan,
    select_implementation,
)
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from biocompiler.verification.implementation import (
    CHECKER_VERSION,
    check_implementation,
    check_implementation_construct,
    check_implementation_plan,
    check_implementation_requirements,
    check_implementation_selection,
)
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION as STRUCTURAL_CHECKER_VERSION,
)
from biocompiler.verification.deployment import (
    CHECKER_VERSION as DEPLOYMENT_CHECKER_VERSION,
)

PIPELINE_VERSION = "biocompiler.implementation_pipeline.v0.1"


def _tools():
    return dict(
        pipeline=PIPELINE_VERSION,
        analyzer=ANALYZER_VERSION,
        requirements_profile=REQUIREMENTS_PROFILE,
        family=PROFILE_VERSION,
        generator=GENERATOR_VERSION,
        emitter=EMITTER_VERSION,
        checker=CHECKER_VERSION,
        structural_checker=STRUCTURAL_CHECKER_VERSION,
        deployment_checker=DEPLOYMENT_CHECKER_VERSION,
        admission_policy=ADMISSION_POLICY_VERSION,
    )


def _decision(checked):
    return CheckDecision(
        checked.outcome, "Independent implementation correspondence.", checked.to_dict()
    )


def verify_implementation_requirements(report, *, expected_source):
    """Verify an analysis against the separately retained complete source request."""
    require(
        isinstance(report, ImplementationRequirements),
        "Expected implementation analysis.",
    )
    report = ImplementationRequirements.from_dict(report.to_dict())
    source = source_request_from_dict(expected_source.to_dict())
    result = check_implementation_requirements(
        source,
        report,
        expected_source_fingerprint=source.fingerprint,
    )
    require(
        result.outcome is CheckOutcome.PASS,
        "Requirements differ from source authority.",
    )
    return report


def _planning_check(request, requirements, planning):
    selection = check_implementation_selection(
        request,
        requirements,
        planning.selection,
        expected_request_fingerprint=request.fingerprint,
    )
    evidence = {"selection": selection.to_dict()}
    outcome = selection.outcome
    if planning.plan is not None:
        plan = check_implementation_plan(
            request,
            requirements,
            planning.selection,
            planning.plan,
            expected_request_fingerprint=request.fingerprint,
        )
        evidence["plan"] = plan.to_dict()
        if plan.outcome is not CheckOutcome.PASS:
            outcome = plan.outcome
    return CheckDecision(
        outcome, "Bounded selection and declared molecular relationships.", evidence
    )


def _components(request, plan):
    architecture = next(
        item
        for item in request.library.architectures
        if item.id == plan.architecture_id
    )
    return ImplementationComponents(request.fingerprint, plan.fingerprint, architecture)


def _components_check(request, plan, components):
    expected = {item.id: item for item in request.library.architectures}.get(
        plan.architecture_id
    )
    valid = (
        components.request_fingerprint == request.fingerprint
        and components.plan_fingerprint == plan.fingerprint
        and expected is not None
        and components.architecture.fingerprint == expected.fingerprint
        and components.architecture.fingerprint == plan.architecture_fingerprint
    )
    return CheckDecision(
        CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        "Exact selected sequence and architecture authority; function remains unestablished.",
    )


@dataclass(frozen=True)
class ImplementationCompilation:
    record: ImplementationBuildRecord
    manager: PassManager
    pipeline_result: object

    @property
    def molecule(self):
        return self.record.molecule

    @property
    def status(self):
        return self.record.status


def compile_implementation(request, *, expected_request_fingerprint=None):
    require(
        isinstance(request, ImplementationRequest), "Expected ImplementationRequest."
    )
    request = ImplementationRequest.from_dict(request.to_dict())
    require(
        isinstance(request.target, TargetContext),
        "Molecular selection needs an explicit target.",
    )
    pin = (
        request.fingerprint
        if expected_request_fingerprint is None
        else expected_request_fingerprint
    )
    require(
        pin == request.fingerprint,
        "Implementation request differs from independent authority.",
    )
    tools = _tools()
    dependencies = {
        "request": pin,
        "source": request.source.fingerprint,
        "library": request.library.fingerprint,
        **{key: fingerprint(value) for key, value in tools.items()},
    }
    completion = ScopedObligation(
        "implementation.structure",
        COMPLETION_SCOPE,
        EvidenceKind.EXACT,
        "Declared precursor architecture, processing coordinates and exact RNA correspondence.",
    )
    manager = PassManager(
        target=request.target,
        dependencies=dependencies,
        completion_profiles=(
            CompletionProfile(
                COMPLETION_SCOPE,
                Stage.MOLECULAR,
                ImplementationStage.schema_version,
                (completion.id,),
            ),
        ),
    )
    source = request.source
    build = source if hasattr(source, "intent") else source.build_request
    source_ids = tuple(node.id for node in build.intent.nodes)
    manager.add_input("intent", request, requirements=source_ids)
    checks, values = {}, {}

    def run(label, before, after, producer, validator, *, obligations=()):
        parent = "intent" if before is Stage.INTENT else list(values)[-1]
        contract = PassContract(
            "implementation." + label,
            PIPELINE_VERSION,
            before,
            after,
            ImplementationRequest.schema_version
            if before is Stage.INTENT
            else ImplementationStage.schema_version,
            ImplementationStage.schema_version,
            COMPLETION_SCOPE,
            PROFILE_VERSION,
            ("retained_requirement",),
            (
                CheckSpec(
                    label,
                    EvidenceKind.EXACT,
                    (completion.id,) if after is Stage.MOLECULAR else (),
                ),
            ),
            dependency_keys=tuple(dependencies),
            targets=(request.target.payload_format,),
            consumes_requirements=source_ids,
            introduces=obligations,
        )
        links = tuple(SourceLink(node, node, node, contract.id) for node in source_ids)

        def propose(context):
            return PassResult(
                ImplementationStage(pin, label, producer(), source_ids), (), links
            )

        def check(context):
            stage = ImplementationStage.from_dict(context.output)
            require(
                stage.stage == label
                and stage.request_fingerprint == pin
                and stage.source_node_ids == source_ids
                and context.source_links == links
                and not context.observation_map,
                "Changed implementation source correspondence.",
            )
            assessment = validator(stage.payload)
            decision = (
                assessment
                if isinstance(assessment, CheckDecision)
                else _decision(assessment)
            )
            checks[label] = decision.to_dict()
            return decision

        manager.register(contract, propose, {label: check})
        receipt = manager.run(contract.id, parent, label)
        if not receipt.accepted:
            raise PipelineError(
                "Implementation stage failed independent checking: " + label
            )
        values[label] = ImplementationStage.from_dict(
            manager.get(label).payload
        ).payload
        return values[label]

    requirements = run(
        "requirements",
        Stage.INTENT,
        Stage.BEHAVIOR,
        lambda: analyze_implementation_requirements(request.source),
        lambda report: check_implementation_requirements(
            request.source,
            report,
            expected_source_fingerprint=request.source.fingerprint,
        ),
    )

    def propose_planning():
        selection = select_implementation(request, requirements)
        plan = (
            derive_implementation_plan(request, requirements, selection)
            if selection.selected_architecture_id is not None
            else None
        )
        return ImplementationPlanning(selection, plan)

    unresolved = tuple(
        ScopedObligation(
            item.id,
            "therapeutic_implementation",
            EvidenceKind.UNRESOLVED,
            item.semantics["operation"],
        )
        for item in requirements.obligations
    )
    planning = run(
        "planning",
        Stage.BEHAVIOR,
        Stage.MECHANISM,
        propose_planning,
        lambda result: _planning_check(request, requirements, result),
        obligations=unresolved,
    )
    selection, plan = planning.selection, planning.plan
    components = construct = molecule = None
    if plan is not None:
        components = run(
            "components",
            Stage.MECHANISM,
            Stage.COMPONENTS,
            lambda: _components(request, plan),
            lambda value: _components_check(request, plan, value),
        )
        construct = run(
            "construct",
            Stage.COMPONENTS,
            Stage.CONSTRUCT,
            lambda: derive_implementation_construct(request, requirements, plan),
            lambda value: check_implementation_construct(
                request,
                requirements,
                selection,
                plan,
                value,
                expected_request_fingerprint=pin,
            ),
        )
        molecule = run(
            "molecule",
            Stage.CONSTRUCT,
            Stage.MOLECULAR,
            lambda: emit_implementation(request, construct),
            lambda value: check_implementation(
                request,
                requirements,
                selection,
                plan,
                construct,
                value,
                expected_request_fingerprint=pin,
            ),
            obligations=(completion,),
        )
    record = ImplementationBuildRecord(
        request,
        requirements,
        selection,
        plan,
        components,
        construct,
        molecule,
        checks,
        tools,
    )
    result = manager.result(
        "molecule" if molecule is not None else "planning", scope=COMPLETION_SCOPE
    )
    return ImplementationCompilation(record, manager, result)


def verify_implementation_build(record, *, expected_request):
    """Fresh replay uses only independent checkers, never construction functions."""
    require(
        isinstance(record, ImplementationBuildRecord)
        and isinstance(expected_request, ImplementationRequest),
        "Verification needs a build and independent complete implementation request.",
    )
    record = ImplementationBuildRecord.from_dict(record.to_dict())
    request = ImplementationRequest.from_dict(expected_request.to_dict())
    require(
        record.request.fingerprint == request.fingerprint,
        "Saved build differs from original request.",
    )
    require(
        fingerprint(record.tool_versions) == fingerprint(_tools()),
        "Implementation tools changed; rebuild.",
    )
    pin = request.fingerprint
    checks = {
        "requirements": _decision(
            check_implementation_requirements(
                request.source,
                record.requirements,
                expected_source_fingerprint=request.source.fingerprint,
            )
        ),
        "planning": _planning_check(
            request,
            record.requirements,
            ImplementationPlanning(record.selection, record.plan),
        ),
    }
    if record.molecule is not None:
        checks.update(
            components=_components_check(request, record.plan, record.components),
            construct=_decision(
                check_implementation_construct(
                    request,
                    record.requirements,
                    record.selection,
                    record.plan,
                    record.construct,
                    expected_request_fingerprint=pin,
                )
            ),
            molecule=_decision(
                check_implementation(
                    request,
                    record.requirements,
                    record.selection,
                    record.plan,
                    record.construct,
                    record.molecule,
                    expected_request_fingerprint=pin,
                )
            ),
        )
    for name, decision in checks.items():
        require(
            decision.outcome is CheckOutcome.PASS,
            "Saved implementation failed checking: " + name,
        )
    require(
        fingerprint(record.checks)
        == fingerprint({key: value.to_dict() for key, value in checks.items()}),
        "Saved implementation checks differ from fresh independent assessment.",
    )
    return record


def export_implementation_fasta(record, *, expected_request):
    record = verify_implementation_build(record, expected_request=expected_request)
    require(
        record.molecule is not None, "No eligible molecular implementation to export."
    )
    molecule = record.molecule
    return (
        f">{quote(molecule.id, safe='-._~')} build={record.fingerprint} scope={COMPLETION_SCOPE} "
        "physical_function=unestablished therapeutic_implementation=partial human_use=not_admitted\n"
        + "\n".join(
            molecule.sequence[index : index + 80]
            for index in range(0, len(molecule.sequence), 80)
        )
        + "\n"
    )
