"""Checked intent-to-RNA product-cassette compilation and independent replay."""

from dataclasses import dataclass
from urllib.parse import quote

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.backends.candidate import EMITTER_VERSION, emit_candidate
from biocompiler.compiler.candidate_requirements import (
    LOWERER_VERSION,
    lower_candidate_requirements,
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
from biocompiler.ir.candidate import PROFILE_VERSION, CandidateRequest
from biocompiler.ir.candidate_selection import (
    LAYOUT_PROFILE_VERSION,
    SELECTION_PROFILE_VERSION,
)
from biocompiler.ir.candidate_build import (
    CandidateBuildRecord,
    CandidateComponents,
    CandidateStage,
)
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.ir.stages import Stage
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.context import PayloadFormat
from biocompiler.synthesis.candidate import (
    GENERATOR_VERSION,
    derive_candidate_layout,
    select_candidate,
)
from biocompiler.verification.candidate import (
    CHECKER_VERSION,
    check_candidate,
    check_candidate_layout,
    check_candidate_requirements,
    check_candidate_selection,
)
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION as STRUCTURAL_CHECKER_VERSION,
)

PIPELINE_VERSION = "biocompiler.candidate_pipeline.v0.1"
COMPLETION_SCOPE = "product_cassette_structure"


def _tools():
    return dict(
        pipeline=PIPELINE_VERSION,
        generator=GENERATOR_VERSION,
        lowerer=LOWERER_VERSION,
        requirements_profile=PROFILE_VERSION,
        selection_profile=SELECTION_PROFILE_VERSION,
        layout_profile=LAYOUT_PROFILE_VERSION,
        emitter=EMITTER_VERSION,
        checker=CHECKER_VERSION,
        structural_checker=STRUCTURAL_CHECKER_VERSION,
        admission_policy=ADMISSION_POLICY_VERSION,
    )


def _components(request, selection):
    selected = selection.selected
    require(selected is not None, "No selected molecular candidate.")
    architecture = next(
        item
        for item in request.library.architectures
        if item.id == selected.architecture_id
    )
    ids = (
        architecture.five_prime_part_id,
        selected.cds_part_id,
        architecture.three_prime_part_id,
    )
    if architecture.poly_a_part_id is not None:
        ids += (architecture.poly_a_part_id,)
    parts = {part.id: part for part in request.library.parts}
    return CandidateComponents(
        request.fingerprint,
        selection.fingerprint,
        architecture.id,
        selected.cds_part_id,
        tuple(parts[key] for key in ids),
    )


def _check_components(request, selection, components):
    """Independently reconcile expanded inventory with selected library roles."""
    selected = selection.selected
    require(selected is not None, "Components cannot exist without selection.")
    architectures = {entry.id: entry for entry in request.library.architectures}
    require(selected.architecture_id in architectures, "Unknown selected architecture.")
    recipe = architectures[selected.architecture_id]
    by_id = {part.id: part for part in request.library.parts}
    expected_ids = [
        recipe.five_prime_part_id,
        selected.cds_part_id,
        recipe.three_prime_part_id,
    ]
    if recipe.poly_a_part_id is not None:
        expected_ids.append(recipe.poly_a_part_id)
    valid = (
        components.request_fingerprint == request.fingerprint
        and components.selection_fingerprint == selection.fingerprint
        and components.architecture_id == selected.architecture_id
        and components.cds_part_id == selected.cds_part_id
        and [part.id for part in components.parts] == expected_ids
        and all(part == by_id.get(part.id) for part in components.parts)
    )
    return CheckDecision(
        CheckOutcome.PASS if valid else CheckOutcome.FAIL,
        "Exact selected library inventory; no component function established.",
    )


@dataclass(frozen=True)
class CandidateCompilation:
    record: CandidateBuildRecord
    manager: PassManager
    pipeline_result: object

    @property
    def molecule(self):
        return self.record.molecule

    @property
    def status(self):
        return self.record.status


def compile_candidate(request, *, expected_request_fingerprint=None):
    """Compile an explicit research candidate, retaining unimplemented behavior.

    Direct callers supply the authority object. Saved results always require a
    separately retained complete request for verification and sequence export.
    """
    require(isinstance(request, CandidateRequest), "Expected CandidateRequest.")
    request = CandidateRequest.from_dict(request.to_dict())
    pin = (
        request.fingerprint
        if expected_request_fingerprint is None
        else expected_request_fingerprint
    )
    require(
        pin == request.fingerprint,
        "Candidate request differs from independent authority.",
    )
    require(
        request.target is not None
        and request.target.payload_format is PayloadFormat.RNA,
        "Candidate compilation requires an explicit RNA target.",
    )
    tools = _tools()
    dependencies = {
        "request": request.fingerprint,
        "library": request.library.fingerprint,
        "expected_request": pin,
        **{key: fingerprint(value) for key, value in tools.items()},
    }
    completion = ScopedObligation(
        "candidate.structure",
        COMPLETION_SCOPE,
        EvidenceKind.EXACT,
        "Source-linked product coding identity and exact RNA structure.",
    )
    manager = PassManager(
        target=request.target,
        dependencies=dependencies,
        completion_profiles=(
            CompletionProfile(
                COMPLETION_SCOPE,
                Stage.MOLECULAR,
                CandidateStage.schema_version,
                (completion.id,),
            ),
        ),
    )
    source_ids = tuple(node.id for node in request.build_request.intent.nodes)
    manager.add_input("intent", request, requirements=source_ids)
    results = {}
    values = {}

    def run(label, before, after, producer, validator, *, obligations=()):
        parent = "intent" if before is Stage.INTENT else list(values)[-1]
        contract = PassContract(
            "candidate." + label,
            PIPELINE_VERSION,
            before,
            after,
            CandidateRequest.schema_version
            if before is Stage.INTENT
            else CandidateStage.schema_version,
            CandidateStage.schema_version,
            COMPLETION_SCOPE,
            PIPELINE_VERSION,
            ("retained_requirement",),
            (
                CheckSpec(
                    label,
                    EvidenceKind.EXACT,
                    (completion.id,) if after is Stage.MOLECULAR else (),
                ),
            ),
            dependency_keys=tuple(dependencies),
            targets=(PayloadFormat.RNA,),
            consumes_requirements=source_ids,
            introduces=obligations,
        )
        links = tuple(SourceLink(node, node, node, contract.id) for node in source_ids)

        def propose(context):
            value = producer()
            return PassResult(
                CandidateStage(request.fingerprint, label, value, source_ids), (), links
            )

        def check(context):
            stage = CandidateStage.from_dict(context.output)
            require(
                stage.stage == label
                and stage.request_fingerprint == request.fingerprint
                and stage.source_node_ids == source_ids
                and context.source_links == links
                and not context.observation_map,
                "Changed source correspondence or candidate stage.",
            )
            checked = validator(stage.payload)
            if isinstance(checked, CheckDecision):
                decision = checked
            else:
                decision = CheckDecision(
                    checked.outcome,
                    "Independent candidate correspondence.",
                    checked.to_dict(),
                )
            results[label] = decision.to_dict()
            return decision

        manager.register(contract, propose, {label: check})
        record = manager.run(contract.id, parent, label)
        if not record.accepted:
            raise PipelineError("Candidate stage failed independent checking: " + label)
        values[label] = CandidateStage.from_dict(manager.get(label).payload).payload
        return values[label]

    requirements = run(
        "requirements",
        Stage.INTENT,
        Stage.BEHAVIOR,
        lambda: lower_candidate_requirements(request),
        lambda result: check_candidate_requirements(
            request, result, expected_request_fingerprint=pin
        ),
    )
    unresolved = tuple(
        ScopedObligation(
            item.id,
            "therapeutic_implementation",
            EvidenceKind.UNRESOLVED,
            item.description,
        )
        for item in requirements.unresolved
    )
    selection = run(
        "selection",
        Stage.BEHAVIOR,
        Stage.MECHANISM,
        lambda: select_candidate(request, requirements),
        lambda result: check_candidate_selection(
            request, requirements, result, expected_request_fingerprint=pin
        ),
        obligations=unresolved,
    )
    components = layout = molecule = None
    if selection.selected is not None:
        components = run(
            "components",
            Stage.MECHANISM,
            Stage.COMPONENTS,
            lambda: _components(request, selection),
            lambda result: _check_components(request, selection, result),
        )
        layout = run(
            "layout",
            Stage.COMPONENTS,
            Stage.CONSTRUCT,
            lambda: derive_candidate_layout(request, requirements, selection),
            lambda result: check_candidate_layout(
                request,
                requirements,
                selection,
                result,
                expected_request_fingerprint=pin,
            ),
        )
        molecule = run(
            "molecule",
            Stage.CONSTRUCT,
            Stage.MOLECULAR,
            lambda: emit_candidate(request, layout),
            lambda result: check_candidate(
                request,
                requirements,
                selection,
                layout,
                result,
                expected_request_fingerprint=pin,
            ),
            obligations=(completion,),
        )
    result = manager.result(
        "molecule" if molecule is not None else "selection", scope=COMPLETION_SCOPE
    )
    record = CandidateBuildRecord(
        request, requirements, selection, components, layout, molecule, results, tools
    )
    return CandidateCompilation(record, manager, result)


def verify_candidate_build(record, *, expected_request):
    """Recheck saved output independently; never use a generator as its oracle."""
    require(
        isinstance(record, CandidateBuildRecord)
        and isinstance(expected_request, CandidateRequest),
        "Verification requires a candidate record and independent complete request.",
    )
    record = CandidateBuildRecord.from_dict(record.to_dict())
    request = CandidateRequest.from_dict(expected_request.to_dict())
    require(
        record.request == request and record.request.fingerprint == request.fingerprint,
        "Saved candidate differs from independent request authority.",
    )
    require(
        dict(record.tool_versions) == _tools(),
        "Candidate tools changed; rebuild with current tools.",
    )
    pin = request.fingerprint
    checks = {
        "requirements": check_candidate_requirements(
            request, record.requirements, expected_request_fingerprint=pin
        ),
        "selection": check_candidate_selection(
            request,
            record.requirements,
            record.selection,
            expected_request_fingerprint=pin,
        ),
    }
    if record.molecule is not None:
        checks.update(
            components=_check_components(request, record.selection, record.components),
            layout=check_candidate_layout(
                request,
                record.requirements,
                record.selection,
                record.layout,
                expected_request_fingerprint=pin,
            ),
            molecule=check_candidate(
                request,
                record.requirements,
                record.selection,
                record.layout,
                record.molecule,
                expected_request_fingerprint=pin,
            ),
        )
    recomputed = {}
    for label, checked in checks.items():
        decision = (
            checked
            if isinstance(checked, CheckDecision)
            else CheckDecision(
                checked.outcome,
                "Independent candidate correspondence.",
                checked.to_dict(),
            )
        )
        require(
            decision.outcome is CheckOutcome.PASS,
            "Saved candidate failed verification: " + label,
        )
        recomputed[label] = decision.to_dict()
    require(
        fingerprint(record.checks) == fingerprint(recomputed),
        "Saved candidate checks differ from fresh assessment.",
    )
    return record


def export_candidate_fasta(record, *, expected_request):
    record = verify_candidate_build(record, expected_request=expected_request)
    require(record.molecule is not None, "No molecular candidate to export.")
    molecule = record.molecule
    return (
        f">{quote(molecule.id, safe='-._~')} build={record.fingerprint} "
        "scope=product_cassette_structure therapeutic_implementation=partial human_use=not_admitted\n"
        + "\n".join(
            molecule.sequence[index : index + 80]
            for index in range(0, len(molecule.sequence), 80)
        )
        + "\n"
    )
