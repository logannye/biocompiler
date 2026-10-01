"""Independent correspondence checks for partial product-cassette candidates.

Original intent, human target and all unmet implementation requirements remain
authoritative. This module imports no requirements lowerer, selector, layout
generator or emitter. Structural agreement grants no therapeutic implementation.
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields
import hashlib
from types import SimpleNamespace
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.molecular_design import FragmentPlacement
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion, hash_value
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.evidence import CheckOutcome, FreshnessReport
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION as STRUCTURAL_CHECKER_VERSION,
    structural_rna_diagnostics,
)
from biocompiler.verification.payload import PayloadDiagnostic

CHECKER_VERSION = "biocompiler.candidate_checker.v0.1"
CLAIM_SCOPE = (
    "Partial product-cassette source correspondence, bounded supplied-library "
    "selection and exact structural RNA assembly only. Sensing, regulation, "
    "secretion, quantitative response, therapeutic goals, human applicability "
    "and use admission remain unresolved."
)
_STAGES = ("requirements", "selection", "layout", "molecule")
_CHECKS = (
    "original_request_authority",
    "complete_source_requirements",
    "bounded_alternative_selection",
    "derived_layout_correspondence",
    "emitted_molecule_correspondence",
)


def _outcome(diagnostics):
    states = {item.status for item in diagnostics}
    return next(
        (
            item
            for item in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if item.value in states
        ),
        CheckOutcome.PASS,
    )


def _sha(sequence):
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def _checks(stage):
    return _CHECKS[: 2 + _STAGES.index(stage)]


def _profiles():
    from biocompiler.ir.candidate import PROFILE_VERSION
    from biocompiler.ir.candidate_selection import (
        LAYOUT_PROFILE_VERSION,
        SELECTION_PROFILE_VERSION,
    )
    from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION

    return {
        "requirements": PROFILE_VERSION,
        "selection": SELECTION_PROFILE_VERSION,
        "layout": LAYOUT_PROFILE_VERSION,
        "admission": ADMISSION_POLICY_VERSION,
    }


def candidate_dependencies(
    request,
    requirements,
    selection=None,
    layout=None,
    candidate=None,
    *,
    expected_request_fingerprint,
):
    from biocompiler.ir.candidate import CandidateRequest, CandidateRequirements
    from biocompiler.ir.candidate_selection import CandidateSelection, CandidateLayout

    require(
        isinstance(request, CandidateRequest),
        "Expected full candidate request authority.",
    )
    require(
        request.target is not None,
        "Candidate checking requires the original explicit target.",
    )
    require(
        isinstance(requirements, CandidateRequirements),
        "Expected candidate requirements.",
    )
    for value, cls, label in (
        (selection, CandidateSelection, "selection"),
        (layout, CandidateLayout, "layout"),
        (candidate, PayloadMolecule, "molecule"),
    ):
        require(
            value is None or isinstance(value, cls), "Invalid candidate " + label + "."
        )
    require(
        layout is None or selection is not None, "Layout requires selection authority."
    )
    require(candidate is None or layout is not None, "Molecule requires actual layout.")
    hash_value(expected_request_fingerprint, "Expected candidate request")
    return {
        "request": request.fingerprint,
        "expected_request": expected_request_fingerprint,
        "source": request.source.fingerprint,
        "target": request.target.fingerprint,
        "library": request.library.fingerprint,
        "requirements": requirements.fingerprint,
        "selection": selection.fingerprint if selection is not None else None,
        "layout": layout.fingerprint if layout is not None else None,
        "candidate": candidate.fingerprint if candidate is not None else None,
        "checker": CHECKER_VERSION,
        "structural_checker": STRUCTURAL_CHECKER_VERSION,
        "profiles": _profiles(),
        "schemas": {
            "request": CandidateRequest.schema_version,
            "requirements": CandidateRequirements.schema_version,
            "selection": CandidateSelection.schema_version,
            "layout": CandidateLayout.schema_version,
            "molecule": PayloadMolecule.schema_version,
        },
    }


@dataclass(frozen=True)
class CandidateVerificationResult(JsonArtifact):
    stage: str
    outcome: CheckOutcome
    dependencies: Mapping
    diagnostics: tuple[PayloadDiagnostic, ...]
    checks: tuple[str, ...]
    unresolved: tuple
    source_node_ids: tuple[str, ...]
    scope: str = "partial_product_cassette_research"
    complete_therapeutic_implementation: bool = False
    human_therapeutic_admission: str = "not_admitted"
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "biocompiler.candidate_verification_result.v0.1"

    def __post_init__(self):
        from biocompiler.ir.candidate import (
            CandidateObligation,
            CandidateRequest,
            CandidateRequirements,
        )
        from biocompiler.ir.candidate_selection import (
            CandidateSelection,
            CandidateLayout,
        )

        require(
            isinstance(self.stage, str) and self.stage in _STAGES,
            "Invalid candidate check stage.",
        )
        require(isinstance(self.outcome, CheckOutcome), "Invalid candidate outcome.")
        fields(
            self.dependencies,
            {
                "request",
                "expected_request",
                "source",
                "target",
                "library",
                "requirements",
                "selection",
                "layout",
                "candidate",
                "checker",
                "structural_checker",
                "profiles",
                "schemas",
            },
            "Candidate check dependencies",
        )
        for key in (
            "request",
            "expected_request",
            "source",
            "target",
            "library",
            "requirements",
        ):
            hash_value(self.dependencies[key], key)
        stage_index = _STAGES.index(self.stage)
        for index, key in enumerate(("selection", "layout", "candidate"), start=1):
            value = self.dependencies[key]
            require(
                (value is not None) == (stage_index >= index),
                "Candidate check dependency inventory differs from stage.",
            )
            if value is not None:
                hash_value(value, key)
        require(
            self.dependencies["checker"] == CHECKER_VERSION
            and self.dependencies["structural_checker"] == STRUCTURAL_CHECKER_VERSION
            and self.dependencies["profiles"] == _profiles()
            and self.dependencies["schemas"]
            == {
                "request": CandidateRequest.schema_version,
                "requirements": CandidateRequirements.schema_version,
                "selection": CandidateSelection.schema_version,
                "layout": CandidateLayout.schema_version,
                "molecule": PayloadMolecule.schema_version,
            },
            "Historical candidate checks require fresh current-tool reconstruction.",
        )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        require(
            isinstance(self.diagnostics, (tuple, list))
            and all(isinstance(x, PayloadDiagnostic) for x in self.diagnostics),
            "Invalid candidate diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        require(
            self.outcome == _outcome(self.diagnostics),
            "Candidate outcome differs from diagnostics.",
        )
        require(
            isinstance(self.checks, (tuple, list))
            and tuple(self.checks) == _checks(self.stage),
            "Incomplete candidate check inventory.",
        )
        object.__setattr__(self, "checks", tuple(self.checks))
        require(
            isinstance(self.unresolved, (tuple, list))
            and bool(self.unresolved)
            and all(isinstance(x, CandidateObligation) for x in self.unresolved),
            "Candidate checks must retain unresolved obligations.",
        )
        object.__setattr__(self, "unresolved", tuple(self.unresolved))
        require(
            isinstance(self.source_node_ids, (tuple, list))
            and bool(self.source_node_ids)
            and all(isinstance(x, str) and x for x in self.source_node_ids)
            and len(set(self.source_node_ids)) == len(self.source_node_ids),
            "Invalid source coverage inventory.",
        )
        object.__setattr__(self, "source_node_ids", tuple(self.source_node_ids))
        require(
            self.scope == "partial_product_cassette_research"
            and self.complete_therapeutic_implementation is False
            and self.human_therapeutic_admission == "not_admitted"
            and self.claim_scope == CLAIM_SCOPE,
            "Candidate checks cannot promote partial structure to therapeutic implementation.",
        )

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def to_dict(self):
        def encode(value):
            if isinstance(value, JsonArtifact):
                return value.to_dict()
            if isinstance(value, PayloadDiagnostic):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(x) for x in value]
            if isinstance(value, CheckOutcome):
                return value.value
            return thaw_json(value)

        return {"schema_version": self.schema_version} | {
            item.name: encode(getattr(self, item.name))
            for item in dataclass_fields(self)
        }

    @classmethod
    def from_dict(cls, data):
        from biocompiler.ir.candidate import CandidateObligation

        try:
            fields(
                data,
                {item.name for item in dataclass_fields(cls)} | {"schema_version"},
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                "Unsupported candidate result schema.",
            )
            require(
                isinstance(data["outcome"], str)
                and data["outcome"] in {x.value for x in CheckOutcome},
                "Invalid candidate outcome.",
            )
            return cls(
                **{
                    key: CheckOutcome(value)
                    if key == "outcome"
                    else tuple(PayloadDiagnostic.from_dict(x) for x in value)
                    if key == "diagnostics"
                    else tuple(CandidateObligation.from_dict(x) for x in value)
                    if key == "unresolved"
                    else value
                    for key, value in data.items()
                    if key != "schema_version"
                }
            )
        except SerializationError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
            raise SerializationError(f"Invalid candidate result: {exc}") from exc

    def freshness(
        self,
        request,
        requirements,
        selection=None,
        layout=None,
        candidate=None,
        *,
        expected_request_fingerprint,
    ):
        current = candidate_dependencies(
            request,
            requirements,
            selection,
            layout,
            candidate,
            expected_request_fingerprint=expected_request_fingerprint,
        )
        return FreshnessReport(
            tuple(
                sorted(
                    key
                    for key in current
                    if freeze_json(current[key]) != self.dependencies[key]
                )
            )
        )

    def is_fresh(
        self,
        request,
        requirements,
        selection=None,
        layout=None,
        candidate=None,
        *,
        expected_request_fingerprint,
    ):
        return self.freshness(
            request,
            requirements,
            selection,
            layout,
            candidate,
            expected_request_fingerprint=expected_request_fingerprint,
        ).fresh


def _layout_expectations(request, architecture, binding):
    """Independently derive exact whole-fragment order and destination intervals."""
    part_by_id = {item.id: item for item in request.library.parts}
    part_ids = [
        architecture.five_prime_part_id,
        binding.cds_part_id,
        architecture.three_prime_part_id,
    ]
    if architecture.poly_a_part_id is not None:
        part_ids.append(architecture.poly_a_part_id)
    kinds = ("five_prime_utr", "cds", "three_prime_utr", "poly_a")
    fragments, placements = [], []
    cursor = 0
    for part_id, kind in zip(part_ids, kinds):
        fragment = part_by_id[part_id].fragment
        length = len(fragment.sequence)
        fragments.append(fragment)
        placements.append(
            FragmentPlacement(
                kind,
                kind,
                fragment.id,
                fragment.fingerprint,
                SequenceRange(0, length),
                SequenceRange(cursor, cursor + length),
                binding.protein_sequence if kind == "cds" else None,
            )
        )
        cursor += length
    return SimpleNamespace(
        fragments=tuple(fragments),
        placements=tuple(placements),
        features=architecture.features,
        unknown_features=(),
    )


def _selection_expectations(request, requirements):
    from biocompiler.ir.candidate_selection import (
        CandidateAlternative,
        CandidateRejection,
        CandidateSelection,
        REJECTION_MESSAGES,
    )

    policy = request.constraints
    bindings = [
        item
        for item in request.library.products
        if item.product == requirements.product
    ]
    alternatives = []
    for architecture in request.library.architectures:
        for binding in bindings:
            layout = _layout_expectations(request, architecture, binding)
            length = sum(len(item.sequence) for item in layout.fragments)
            rejections = []
            for condition, code, status in (
                (
                    bool(policy.allowed_architecture_ids)
                    and architecture.id not in policy.allowed_architecture_ids,
                    "architecture_not_allowed",
                    "fail",
                ),
                (
                    bool(policy.allowed_cds_part_ids)
                    and binding.cds_part_id not in policy.allowed_cds_part_ids,
                    "cds_part_not_allowed",
                    "fail",
                ),
                (
                    policy.max_length is not None and length > policy.max_length,
                    "max_length_exceeded",
                    "fail",
                ),
                (
                    request.target.payload_format.value != "RNA",
                    "unsupported_modality",
                    "unsupported",
                ),
            ):
                if condition:
                    rejections.append(
                        CandidateRejection(status, code, REJECTION_MESSAGES[code])
                    )
            rejections.extend(
                CandidateRejection(item.status, item.code, item.message)
                for item in structural_rna_diagnostics(layout)
            )
            alternatives.append(
                CandidateAlternative(
                    architecture.id, binding.cds_part_id, length, tuple(rejections)
                )
            )
    alternatives.sort(key=lambda item: (item.architecture_id, item.cds_part_id))
    eligible = [item for item in alternatives if item.status == "eligible"]
    if policy.preference == "shortest":
        eligible.sort(
            key=lambda item: (
                item.sequence_length,
                item.architecture_id,
                item.cds_part_id,
            )
        )
    # Otherwise deterministic architecture/CDS order is itself the ranking.
    selected_id = eligible[0].id if eligible else None
    diagnostics = (
        ()
        if eligible
        else ("bounded_candidates_exhausted",)
        if bindings
        else ("product_binding_unavailable",)
    )
    return CandidateSelection(
        request.fingerprint,
        requirements.fingerprint,
        tuple(alternatives),
        selected_id,
        diagnostics,
    )


def _selection_diagnostics(actual, expected):
    problems = []
    for condition, code, message in (
        (
            actual.request_fingerprint != expected.request_fingerprint
            or actual.requirements_fingerprint != expected.requirements_fingerprint,
            "selection_authority",
            "Selection binds different source request or requirements.",
        ),
        (
            actual.alternatives != expected.alternatives,
            "alternative_inventory",
            "Bounded alternatives, lengths or rejection reasons differ from independent library enumeration.",
        ),
        (
            actual.selected_alternative_id != expected.selected_alternative_id,
            "selection_ranking",
            "Selected alternative does not follow hard eligibility and frozen deterministic ranking.",
        ),
        (
            actual.diagnostics != expected.diagnostics,
            "selection_diagnostics",
            "Selection outcome diagnostics differ from independent bounded search.",
        ),
    ):
        if condition:
            problems.append(PayloadDiagnostic("fail", code, message))
    return problems


def _layout_diagnostics(request, requirements, selection, expected_selection, layout):
    diagnostics = []

    def problem(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    if (
        layout.request_fingerprint,
        layout.requirements_fingerprint,
        layout.selection_fingerprint,
    ) != (request.fingerprint, requirements.fingerprint, selection.fingerprint):
        problem(
            "layout_authority",
            "Layout changed its request, requirements or actual selection identity.",
        )
    if layout.target != request.target:
        problem(
            "original_target",
            "Layout must retain the complete original target; a software target cannot substitute for requested human context.",
        )
    if layout.molecule_id != request.build_request.intent.name + ".candidate":
        problem(
            "layout_molecule_id",
            "Candidate molecule identity differs from source-derived identity.",
        )
    selected = expected_selection.selected
    if selected is None:
        problem(
            "no_eligible_layout",
            "No eligible selected alternative exists for this layout.",
        )
        return diagnostics
    if (layout.selected_alternative_id, layout.architecture_id, layout.cds_part_id) != (
        selected.id,
        selected.architecture_id,
        selected.cds_part_id,
    ):
        problem(
            "layout_selection",
            "Actual layout uses a different architecture or product part than independent selection.",
        )
    architecture = next(
        item
        for item in request.library.architectures
        if item.id == selected.architecture_id
    )
    binding = next(
        item
        for item in request.library.products
        if item.product == requirements.product
        and item.cds_part_id == selected.cds_part_id
    )
    expected = _layout_expectations(request, architecture, binding)
    for key in ("fragments", "placements", "features", "unknown_features"):
        if getattr(layout, key) != getattr(expected, key):
            problem(
                "layout_" + key,
                "Actual layout "
                + key
                + " differ from independently derived selected whole-fragment authority.",
            )
    diagnostics.extend(structural_rna_diagnostics(layout))
    return diagnostics


def _molecule_diagnostics(request, layout, molecule):
    diagnostics = []

    def problem(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    if (
        molecule.id != request.build_request.intent.name + ".candidate"
        or molecule.artifact_class != "mature_linear_rna"
        or molecule.alphabet != "RNA"
        or molecule.topology != "linear"
        or molecule.strandedness != "single"
        or molecule.completeness != "complete_molecule"
        or molecule.orientation != "5prime-to-3prime"
    ):
        problem(
            "molecule_profile",
            "Emitted molecule changed requested identity or mature RNA structure.",
        )
    if molecule.source_locator != "candidate-request:" + request.fingerprint:
        problem(
            "molecule_source",
            "Emitted provenance must bind the complete original candidate request.",
        )
    length = layout.placements[-1].molecule_range.end
    if (
        molecule.boundaries != SequenceRange(0, length)
        or len(molecule.sequence) != length
    ):
        problem(
            "molecule_boundaries",
            "Emitted molecule must cover exactly its actual checked layout.",
        )
    if molecule.sequence_sha256 != _sha(molecule.sequence):
        problem(
            "molecule_hash",
            "Actual nucleotide symbols differ from emitted sequence hash.",
        )
    if (
        molecule.features != layout.features
        or molecule.unknown_features != layout.unknown_features
    ):
        problem(
            "molecule_features",
            "Emitted molecule changed the selected chemistry or unresolved features.",
        )
    fragments = {item.id: item for item in layout.fragments}
    regions = []
    for placement in layout.placements:
        fragment = fragments.get(placement.fragment_id)
        if fragment is None:
            problem("molecule_fragment", "Actual layout refers to an absent fragment.")
            continue
        regions.append(
            PayloadRegion(
                placement.region_id,
                placement.kind,
                placement.molecule_range,
                placement.source_range,
                fragment.source_locator,
                placement.protein_sequence,
                placement.orientation,
                placement.reading_frame,
            )
        )
        actual = molecule.sequence[
            placement.molecule_range.start : placement.molecule_range.end
        ]
        expected = fragment.sequence[
            placement.source_range.start : placement.source_range.end
        ]
        if actual != expected:
            problem(
                "molecule_nucleotides",
                "Emitted region "
                + placement.region_id
                + " differs from independently bound fragment symbols.",
            )
    if molecule.regions != tuple(regions):
        problem(
            "molecule_regions",
            "Emitted regions changed exact membership, source maps, coordinates or annotations.",
        )
    return diagnostics


def _source_roles(request):
    """Read original intent directly; no derived requirements are trusted here."""
    from biocompiler.semantics.types import BOOLEAN, PRODUCTION_RATE, TypeSpec

    nodes = request.build_request.intent.nodes
    by_id = {item.id: item for item in nodes}
    roles = [item for item in nodes if item.kind == "role"]
    secretions = [item for item in nodes if item.kind == "secretion"]
    actions = [item for item in nodes if item.kind.startswith("action.")]
    rules = [item for item in nodes if item.kind == "rule"]
    require(
        len(roles) == len(secretions) == len(actions) == len(rules) == 1,
        "Partial cassette source requires one role, secretion, action and rule.",
    )
    role, secretion, action, rule = roles[0], secretions[0], actions[0], rules[0]
    require(
        action.kind == "action.secrete",
        "Partial cassette source requires a secretion action.",
    )
    require(
        secretion.role == action.role == rule.role == role.id,
        "Product and action must retain the selected source role.",
    )
    require(
        secretion.inputs == (role.id,)
        and secretion.attributes.get("activity") == "requires_rule_or_controller",
        "Source product must retain explicit rule-controlled secretion identity.",
    )
    require(
        secretion.data_type is None
        and set(secretion.attributes) == {"name", "product", "default", "activity"}
        and type(secretion.attributes.get("default")) is bool,
        "Source product declaration contains unsupported semantics.",
    )
    require(
        isinstance(secretion.attributes.get("product"), str)
        and bool(secretion.attributes["product"].strip()),
        "Source product must have an explicit identity.",
    )
    rate = action.attributes.get("rate")
    require(
        action.attributes.get("ongoing") is True
        and rate in ("unspecified", "expression"),
        "Partial cassette source requires an ongoing secretion action.",
    )
    require(
        action.data_type is None and set(action.attributes) == {"ongoing", "rate"},
        "Source secretion action contains unsupported semantics.",
    )
    require(
        action.inputs and action.inputs[0] == secretion.id,
        "Source action must bind the selected product exactly.",
    )
    require(
        (rate == "unspecified" and action.inputs == (secretion.id,))
        or (
            rate == "expression"
            and len(action.inputs) == 2
            and action.inputs[1] in by_id
            and TypeSpec.from_dict(by_id[action.inputs[1]].data_type) == PRODUCTION_RATE
        ),
        "Source secretion rate must be unspecified or an explicit production-rate expression.",
    )
    require(
        len(rule.inputs) == 3
        and rule.inputs[0] == role.id
        and rule.inputs[2] == action.id
        and rule.inputs[1] in by_id,
        "Source rule must retain its exact guard and action.",
    )
    guard = by_id[rule.inputs[1]]
    require(
        TypeSpec.from_dict(guard.data_type) == BOOLEAN,
        "Source secretion rule requires a Boolean condition.",
    )
    require(
        rule.attributes.get("trigger") == "condition"
        and rule.attributes.get("execution") == "concurrent"
        and rule.attributes.get("priority") == "unspecified",
        "Unsupported source rule execution semantics.",
    )
    require(
        rule.data_type is None
        and {"trigger", "execution", "priority"} <= set(rule.attributes)
        and set(rule.attributes) <= {"trigger", "execution", "priority", "name"},
        "Source rule contains unsupported additional semantics.",
    )
    require(
        {role.id, secretion.id, rule.id} <= set(request.build_request.intent.roots),
        "Source roots must retain role, product and controlling rule.",
    )
    return nodes, role, secretion, action, rule, guard


def _requirements_expectations(request):
    from biocompiler.compiler.acceptance import HumanAcceptanceRequest
    from biocompiler.compiler.deployment import HumanDeploymentRequest
    from biocompiler.compiler.human_behavior import HumanBehaviorRequest
    from biocompiler.ir.candidate import (
        OBLIGATION_SPECS,
        CandidateObligation,
        CandidateRequirements,
    )
    from biocompiler.semantics.context import HumanTargetContext

    nodes, role, secretion, action, rule, guard = _source_roles(request)
    source_ids = tuple(item.id for item in nodes)
    references = [
        ("secretion_mechanism", (secretion.id, action.id)),
        ("conditional_control", (rule.id, guard.id, action.id)),
        ("quantitative_response", (action.id,)),
        ("biological_function", (secretion.id, action.id)),
        ("target_applicability", (role.id,)),
    ]

    def declared(identity, refs):
        category, description = OBLIGATION_SPECS[identity]
        return CandidateObligation(
            identity, tuple(dict.fromkeys(refs)), category, description
        )

    obligations = [declared(identity, refs) for identity, refs in references]
    for node in nodes:
        if node.id not in {role.id, secretion.id, action.id}:
            goal = node.kind == "goal"
            obligations.append(
                CandidateObligation(
                    "source:" + node.id,
                    (node.id,),
                    "evidence" if goal else "implementation",
                    "This source goal remains unestablished by coding candidate selection."
                    if goal
                    else f"Source operation {node.kind!r} remains unimplemented by coding-only candidate selection.",
                )
            )
    if isinstance(request.target, HumanTargetContext):
        obligations.append(declared("human_therapeutic_admission", (role.id,)))
    source = request.source
    behavior = (
        source
        if isinstance(source, HumanBehaviorRequest)
        else (
            source.behavior_request
            if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest))
            else None
        )
    )
    if behavior is not None:
        contract = behavior.contract
        references = [
            ("human_input_observation", (contract.input_signal_id,)),
            ("human_predicate_refinement", (contract.predicate.predicate_id,)),
            (
                "human_response_contract",
                (contract.response.rule_id, contract.response.specification_id),
            ),
            ("human_goal_refinement", (contract.goal_id,)),
            ("human_behavior_evidence", source_ids),
        ]
        obligations.extend(declared(identity, refs) for identity, refs in references)
    if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest)):
        obligations.extend(
            declared(identity, (role.id,))
            for identity in ("human_deployment_contract", "human_deployment_evidence")
        )
    if isinstance(source, HumanAcceptanceRequest):
        obligations.extend(
            declared(identity, (rule.id, action.id))
            for identity in (
                "human_prohibited_behavior",
                "human_input_loss_response",
                "human_external_shutdown",
            )
        )
        obligations.append(
            declared("human_acceptance_evidence", (role.id, rule.id, action.id))
        )
    return CandidateRequirements(
        request.fingerprint,
        role.id,
        secretion.id,
        action.id,
        secretion.attributes["product"],
        source_ids,
        tuple(obligations),
    )


def _verify(
    request, requirements, selection, layout, candidate, expected_request_fingerprint
):
    from biocompiler.ir.candidate import CandidateRequest, CandidateRequirements
    from biocompiler.ir.candidate_selection import CandidateSelection, CandidateLayout

    for value, cls in (
        (request, CandidateRequest),
        (requirements, CandidateRequirements),
    ):
        require(
            isinstance(value, cls),
            "Expected frozen candidate request and requirements.",
        )
    request = CandidateRequest.from_dict(request.to_dict())
    requirements = CandidateRequirements.from_dict(requirements.to_dict())
    if selection is not None:
        require(
            isinstance(selection, CandidateSelection), "Expected candidate selection."
        )
        selection = CandidateSelection.from_dict(selection.to_dict())
    if layout is not None:
        require(isinstance(layout, CandidateLayout), "Expected candidate layout.")
        layout = CandidateLayout.from_dict(layout.to_dict())
    if candidate is not None:
        require(
            isinstance(candidate, PayloadMolecule), "Expected actual emitted molecule."
        )
        candidate = PayloadMolecule.from_dict(candidate.to_dict())
    dependencies = candidate_dependencies(
        request,
        requirements,
        selection,
        layout,
        candidate,
        expected_request_fingerprint=expected_request_fingerprint,
    )
    diagnostics = []
    if request.fingerprint != expected_request_fingerprint:
        diagnostics.append(
            PayloadDiagnostic(
                "fail",
                "request_authority",
                "Full candidate request differs from independently retained authority.",
            )
        )
    try:
        expected_requirements = _requirements_expectations(request)
    except (SerializationError, TypeError, KeyError, AttributeError) as exc:
        expected_requirements = None
        diagnostics.append(
            PayloadDiagnostic("unsupported", "unsupported_source", str(exc))
        )
    if expected_requirements is not None:
        if requirements != expected_requirements:
            diagnostics.append(
                PayloadDiagnostic(
                    "fail",
                    "requirements_correspondence",
                    "Product identity, source coverage or unresolved implementation/evidence obligations differ from original authority.",
                )
            )
        if selection is not None:
            expected_selection = _selection_expectations(request, expected_requirements)
            diagnostics.extend(_selection_diagnostics(selection, expected_selection))
            if layout is not None:
                diagnostics.extend(
                    _layout_diagnostics(
                        request,
                        expected_requirements,
                        selection,
                        expected_selection,
                        layout,
                    )
                )
                if candidate is not None:
                    diagnostics.extend(
                        _molecule_diagnostics(request, layout, candidate)
                    )
    stage = (
        "molecule"
        if candidate is not None
        else "layout"
        if layout is not None
        else "selection"
        if selection is not None
        else "requirements"
    )
    # Malformed/unsupported source receipts cannot pass; retain supplied obligations
    # for diagnosis while valid-source receipts always use the independent inventory.
    obligations = (
        expected_requirements.unresolved
        if expected_requirements is not None
        else requirements.unresolved
    )
    return CandidateVerificationResult(
        stage,
        _outcome(diagnostics),
        dependencies,
        tuple(diagnostics),
        _checks(stage),
        obligations,
        tuple(node.id for node in request.build_request.intent.nodes),
    )


def check_candidate_requirements(
    request, requirements, *, expected_request_fingerprint
):
    return _verify(
        request, requirements, None, None, None, expected_request_fingerprint
    )


def check_candidate_selection(
    request, requirements, selection, *, expected_request_fingerprint
):
    return _verify(
        request, requirements, selection, None, None, expected_request_fingerprint
    )


def check_candidate_layout(
    request, requirements, selection, layout, *, expected_request_fingerprint
):
    return _verify(
        request, requirements, selection, layout, None, expected_request_fingerprint
    )


def check_candidate(
    request, requirements, selection, layout, candidate, *, expected_request_fingerprint
):
    return _verify(
        request,
        requirements,
        selection,
        layout,
        candidate,
        expected_request_fingerprint,
    )
