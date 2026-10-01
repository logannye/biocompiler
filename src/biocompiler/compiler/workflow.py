"""Inspect authoring inputs at the boundary to future molecular realization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import json
import math
from types import MappingProxyType
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from biocompiler.ir.executable_payload import PayloadCompilationRequest, PayloadBuild
    from biocompiler.ir.circuit_construction import CircuitConstructionRequest
    from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
    from biocompiler.ir.circuit_molecules import CircuitMoleculeSet
    from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
    from biocompiler.ir.circuit_intent import CircuitRequest
    from biocompiler.ir.circuit_profile import CircuitProfileRequest
    from biocompiler.ir.candidate import CandidateRequest
    from biocompiler.compiler.candidate import CandidateCompilation
    from biocompiler.ir.implementation import ImplementationRequest
    from biocompiler.compiler.implementation import ImplementationCompilation

from biocompiler.verification.admission import admission_for_target
from biocompiler.compiler.request import BuildRequest, RealizationRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.verification.deployment import check_deployment
from biocompiler.errors import (
    CompilationUnavailableError,
    DefinitionError,
    TypeMismatchError,
)
from biocompiler.ir.intent import IntentProgram, freeze_json, thaw_json
from biocompiler.frontend.expressions import _constant_value
from biocompiler.semantics.context import (
    HumanTargetContext,
    PayloadFormat,
    TargetContext,
)
from biocompiler.semantics.types import (
    Curve,
    Interval,
    ScalarLiteral,
    TypeSpec,
    validate_binding,
)


@dataclass(frozen=True)
class BuildProfile:
    """Molecular target plus optional typed bindings for named design parameters."""

    target: TargetContext
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, TargetContext):
            raise TypeMismatchError("BuildProfile.target must be a TargetContext.")
        if not isinstance(self.target.payload_format, PayloadFormat):
            raise TypeMismatchError(
                "Target payload_format must be PayloadFormat.DNA or .RNA."
            )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.target.context_id, self.target.context_version)
        ):
            raise DefinitionError(
                "A build target needs non-empty context id and version."
            )
        if not isinstance(self.parameters, Mapping):
            raise TypeMismatchError("Parameter bindings must be a mapping.")
        values = dict(self.parameters)
        for name, value in values.items():
            if not isinstance(name, str) or not name.strip():
                raise DefinitionError(
                    "Parameter binding names must be non-empty strings."
                )
            if isinstance(value, bool) or not isinstance(
                value, (int, float, ScalarLiteral, Interval, Curve)
            ):
                raise TypeMismatchError(
                    f"Unsupported binding for {name!r}; use a numeric or typed value."
                )
        object.__setattr__(self, "parameters", MappingProxyType(values))

    def freeze_request(self, program: IntentProgram, **request_options) -> BuildRequest:
        """Freeze this profile's bindings and target as executable input authority."""
        return BuildRequest.freeze(
            program, target=self.target, parameters=self.parameters, **request_options
        )


@dataclass(frozen=True)
class DesignChoice:
    """A remaining design choice, traceable to the authored node when applicable."""

    code: str
    message: str
    node_id: str | None = None

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "node_id": self.node_id}


@dataclass(frozen=True)
class RealizationPlan:
    """An inspectable planning report; this version selects no molecular parts."""

    program: IntentProgram
    profile: BuildProfile
    bindings: Mapping[str, Any]
    unresolved: tuple[DesignChoice, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", freeze_json(self.bindings))
        object.__setattr__(self, "unresolved", tuple(self.unresolved))

    @property
    def ready(self) -> bool:
        # Exact-reference backends do not implement general intent compilation.
        return False

    @property
    def diagnostics(self) -> tuple[DesignChoice, ...]:
        return self.unresolved

    def freeze_request(self, **request_options) -> BuildRequest:
        """Freeze fully bound inputs; unresolved molecular choices remain explicit.

        A missing design binding rejects this conversion. Freezing does not make
        the plan ready or discharge its implementation/biological obligations.
        """
        return self.profile.freeze_request(self.program, **request_options)

    def to_dict(self) -> dict:
        return {
            "schema_version": "biocompiler.plan.v0.3",
            "admission": admission_for_target(
                self.profile.target, boundary="planning"
            ).to_dict(),
            "status": "unresolved",
            "program": self.program.to_dict(),
            "program_fingerprint": self.program.fingerprint,
            "target": self.profile.target.to_dict(),
            "bindings": thaw_json(self.bindings),
            "unresolved": [choice.to_dict() for choice in self.unresolved],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, indent=indent, allow_nan=False
        )


def _check_bound_quantities(
    program: IntentProgram, bindings: Mapping[str, Any]
) -> None:
    """Recheck constant arithmetic affected by parameter binding, without simulation."""

    class BoundGraph:
        def __init__(self) -> None:
            self.nodes = {node.id: node for node in program.nodes}
            for node in program.find(kind="parameter"):
                name = node.attributes["name"]
                if name in bindings:
                    self.nodes[node.id] = replace(
                        node,
                        attributes={
                            **node.attributes,
                            "default": bindings[name],
                            "bound": True,
                        },
                    )

        def get(self, node_id: str):
            return self.nodes[node_id]

    graph = BoundGraph()
    for node in program.nodes:
        if node.kind == "divide" and _constant_value(graph, node.inputs[1]) == 0:
            raise TypeMismatchError(f"Parameter bindings make divisor {node.id} zero.")
        if node.kind in {"add", "subtract", "multiply", "divide", "negate"}:
            value = _constant_value(graph, node.id)
            if value is not None and not math.isfinite(value):
                raise TypeMismatchError(
                    f"Parameter bindings make quantity {node.id} non-finite."
                )
        duration_ref = None
        if node.kind in {"held_for", "recently", "integrated", "action.pulse"}:
            duration_ref = node.inputs[1]
        elif node.kind == "followed_by":
            duration_ref = node.inputs[2]
        elif node.kind == "memory":
            names = node.attributes.get("input_names", ())
            if "duration" in names:
                duration_ref = node.inputs[names.index("duration")]
        if duration_ref is not None:
            value = _constant_value(graph, duration_ref)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise TypeMismatchError(
                    f"Parameter bindings make duration of {node.id} non-positive or non-finite."
                )


def _profile_choices(program: IntentProgram) -> tuple[DesignChoice, ...]:
    """Name missing semantic obligations without inventing an execution profile.

    These are planning diagnostics, not implementations of the named dynamics.
    Scalar arithmetic and discrete state/pulse operations keep their existing
    abstract semantics; only explicit unsupported extension nodes are reported.
    """
    choices = []
    profiles = {
        "curve_apply": (
            "quantitative_profile_unavailable",
            "Quantitative response tracking needs a separately versioned execution profile and calibrated observation/output mapping.",
        ),
        "integrated": (
            "continuous_profile_unavailable",
            "Rolling integration needs defined history, boundary and numerical-error semantics; no continuous model adapter is installed.",
        ),
        "controller": (
            "feedback_profile_unavailable",
            "Feedback needs an explicit plant model, controller law, arbitration and stability/uncertainty obligations.",
        ),
        "spatial_signal": (
            "spatial_profile_unavailable",
            "Spatial observations need coordinates, geometry, transport and measurement semantics.",
        ),
        "action.migrate_toward": (
            "spatial_profile_unavailable",
            "Migration needs a spatial dynamics profile and context-supported response model.",
        ),
        "channel": (
            "population_profile_unavailable",
            "Intercellular communication needs population, delivery and observation semantics; a declared channel supplies no transport model.",
        ),
        "channel_observation": (
            "population_profile_unavailable",
            "Received signals need an explicit sender/receiver population and delivery model.",
        ),
        "action.emit": (
            "population_profile_unavailable",
            "Signal emission needs calibrated transport and receiver semantics.",
        ),
    }
    for node in program.nodes:
        if node.kind in profiles:
            code, message = profiles[node.kind]
            choices.append(DesignChoice(code, message, node.id))
        if node.kind in {"literal", "parameter"} and node.data_type:
            kind = TypeSpec.from_dict(node.data_type).kind
            if kind == "interval":
                choices.append(
                    DesignChoice(
                        "uncertainty_profile_unavailable",
                        "Interval-valued intent needs explicit quantifiers and uncertainty propagation; an interval is not an empirical distribution.",
                        node.id,
                    )
                )
            elif kind == "curve":
                choices.append(
                    DesignChoice(
                        "quantitative_profile_unavailable",
                        "A declared curve retains its interpolation policy but supplies no calibrated biological response or execution profile.",
                        node.id,
                    )
                )
    return tuple(choices)


def plan(program: IntentProgram, *, profile: BuildProfile) -> RealizationPlan:
    """Bind parameters and enumerate unresolved intent; do not synthesize parts."""
    if not isinstance(program, IntentProgram) or not isinstance(profile, BuildProfile):
        raise TypeMismatchError("plan() requires an IntentProgram and BuildProfile.")
    parameters = {
        node.attributes["name"]: node for node in program.find(kind="parameter")
    }
    unknown = set(profile.parameters) - parameters.keys()
    if unknown:
        raise DefinitionError(
            f"Unknown parameter bindings: {', '.join(sorted(unknown))}."
        )
    bindings = {}
    unresolved = []
    for name, node in parameters.items():
        if name in profile.parameters:
            if node.data_type is None:
                raise TypeMismatchError(f"Parameter {name!r} has no declared type.")
            bindings[name] = validate_binding(
                profile.parameters[name], TypeSpec.from_dict(node.data_type)
            )
        elif node.attributes.get("bound"):
            bindings[name] = thaw_json(node.attributes["default"])
        else:
            unresolved.append(
                DesignChoice(
                    "unbound_parameter", f"Choose a value for {name!r}.", node.id
                )
            )
    _check_bound_quantities(program, bindings)
    for node in program.nodes:
        if node.kind == "signal":
            unresolved.append(
                DesignChoice(
                    "observation_binding",
                    "Select a realization of this observation.",
                    node.id,
                )
            )
        elif node.kind == "goal":
            unresolved.append(
                DesignChoice(
                    "goal_refinement",
                    "Refine this therapeutic goal into a behavior or objective.",
                    node.id,
                )
            )
        elif node.kind == "qualitative":
            unresolved.append(
                DesignChoice(
                    "qualitative_threshold",
                    "Refine this named qualitative threshold.",
                    node.id,
                )
            )
        elif (
            node.kind == "action.secrete"
            and node.attributes.get("rate") == "unspecified"
        ):
            unresolved.append(
                DesignChoice(
                    "output_rate",
                    "Choose an output rate or response relationship.",
                    node.id,
                )
            )
    unresolved.extend(_profile_choices(program))
    if isinstance(profile.target, HumanTargetContext):
        unresolved.extend(_admission_choices(profile.target))
        unresolved.append(_human_target_choice())
        unresolved.append(_deployment_missing_choice())
        unresolved.append(_acceptance_missing_choice())
    unresolved.append(
        DesignChoice(
            "molecular_backend_unavailable",
            "Intent-to-molecular mechanism selection is not implemented; exact-reference CDS emission requires a separately pinned ConstructRequest.",
        )
    )
    return RealizationPlan(program, profile, bindings, tuple(unresolved))


def _admission_choices(target):
    assessment = admission_for_target(target, boundary="planning")
    return tuple(
        DesignChoice(
            code,
            "Human therapeutic compilation requires an independently admitted profile; declared evidence and software PASS results cannot authorize use.",
        )
        for code in assessment.diagnostics
    )


def _human_target_choice():
    return DesignChoice(
        "human_target_applicability_unestablished",
        "Human target declarations and evidence citations require independent applicability review; the target contract grants no biological or payload admission.",
    )


def _deployment_missing_choice():
    return DesignChoice(
        "deployment_contract_missing",
        "Freeze a HumanDeploymentRequest with explicit delivery, exposure, expression and dependency assumptions before human mechanism selection.",
    )


def _acceptance_missing_choice():
    return DesignChoice(
        "human_acceptance_contract_missing",
        "Freeze required and prohibited observations together in a HumanAcceptanceRequest before human mechanism selection.",
    )


def compile(
    design: RealizationPlan
    | BuildRequest
    | RealizationRequest
    | HumanBehaviorRequest
    | HumanDeploymentRequest
    | HumanAcceptanceRequest
    | CandidateRequest
    | ImplementationRequest
    | CircuitProfileRequest
    | CircuitRequest
    | CircuitMoleculeSet
    | CircuitMoleculeRecord
    | CircuitConstructionRequest
    | PayloadCompilationRequest,
) -> CandidateCompilation | ImplementationCompilation | CircuitConstructionBuild | PayloadBuild:
    """Compile explicit research candidates; reject unimplemented human realization."""
    from biocompiler.ir.circuit_construction import CircuitConstructionRequest
    from biocompiler.ir.executable_payload import PayloadCompilationRequest
    if isinstance(design, PayloadCompilationRequest):
        from biocompiler.compiler.executable_payload import compile_payload
        return compile_payload(design)
    from biocompiler.compiler.circuit_construction import build_circuit_construction
    from biocompiler.ir.circuit_molecules import CircuitMoleculeSet
    from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
    from biocompiler.ir.circuit_intent import CircuitRequest
    from biocompiler.ir.circuit_profile import CircuitProfileRequest
    from biocompiler.ir.candidate import CandidateRequest
    from biocompiler.ir.implementation import ImplementationRequest
    if isinstance(design, CircuitConstructionRequest):
        return build_circuit_construction(design)
    if isinstance(design, (CircuitMoleculeSet, CircuitMoleculeRecord)):
        raise CompilationUnavailableError(
            "Molecular declarations require a complete supplied construction request for independent construction checks.",
            diagnostics=("declared_assembly_unverified", "source_correspondence_unverified", "functional_implementation_unestablished", "human_therapeutic_use_not_admitted"),
        )
    if isinstance(design, CircuitRequest):
        from biocompiler.verification.circuit_intent import check_circuit_intent

        assessment = check_circuit_intent(design)
        raise CompilationUnavailableError(
            "Circuit intent is recorded; molecular circuit generation is not implemented.",
            diagnostics=assessment.diagnostics,
        )
    if isinstance(design, CircuitProfileRequest):
        from biocompiler.verification.circuit_profile import check_circuit_profile

        assessment = check_circuit_profile(design)
        raise CompilationUnavailableError(
            "Human circuit scope is recorded; molecular circuit generation is not implemented.",
            diagnostics=assessment.diagnostics,
        )
    if isinstance(design, ImplementationRequest):
        from biocompiler.compiler.implementation import compile_implementation
        return compile_implementation(design)
    if isinstance(design, CandidateRequest):
        from biocompiler.compiler.candidate import compile_candidate
        return compile_candidate(design)
    if not isinstance(
        design,
        (
            RealizationPlan,
            BuildRequest,
            RealizationRequest,
            HumanBehaviorRequest,
            HumanDeploymentRequest,
            HumanAcceptanceRequest,
        ),
    ):
        raise TypeMismatchError(
            "compile() requires a RealizationPlan, BuildRequest, RealizationRequest, HumanBehaviorRequest, HumanDeploymentRequest or HumanAcceptanceRequest."
        )
    acceptance = None
    if isinstance(design, HumanAcceptanceRequest):
        acceptance = HumanAcceptanceRequest.from_dict(design.to_dict())
        design = acceptance.deployment_request
    if isinstance(design, RealizationPlan):
        diagnostics = design.unresolved
    else:
        request = (
            design.build_request
            if isinstance(
                design,
                (RealizationRequest, HumanBehaviorRequest, HumanDeploymentRequest),
            )
            else design
        )
        diagnostics = list(_profile_choices(request.intent))
        if isinstance(request.target, HumanTargetContext):
            diagnostics.extend(_admission_choices(request.target))
            diagnostics.append(_human_target_choice())
            if not isinstance(design, HumanDeploymentRequest):
                diagnostics.append(_deployment_missing_choice())
            if acceptance is None:
                diagnostics.append(_acceptance_missing_choice())
        if isinstance(design, (HumanBehaviorRequest, HumanDeploymentRequest)):
            behavior = (
                design.behavior_request
                if isinstance(design, HumanDeploymentRequest)
                else design
            )
            diagnostics.append(
                DesignChoice(
                    "human_behavior_empirical_support_unestablished",
                    "The source-linked secretion observation contract defines requested behavior; measurement validity, biological realizability and therapeutic goal attainment remain unestablished.",
                    behavior.contract.goal_id,
                )
            )
        if isinstance(design, HumanDeploymentRequest):
            assessment = check_deployment(design)
            diagnostics.extend(
                DesignChoice(
                    code,
                    "Declared deployment dependency or timing prevents supported human mechanism selection.",
                )
                for code in assessment.diagnostics
            )
            diagnostics.append(
                DesignChoice(
                    "deployment_empirical_support_unestablished",
                    "A delivery specification and compatible timing declarations do not establish recipient targeting, intracellular delivery, expression or same-cell coexistence.",
                )
            )
        if request.artifact_scope == "complete_payload":
            diagnostics.append(
                DesignChoice(
                    "complete_payload_not_promoted",
                    "Complete-payload compilation requires an independently promoted whole-molecule reference and supported implementation profile; CDS identity and structural readiness cannot complete this scope.",
                )
            )
        diagnostics.append(
            DesignChoice(
                "molecular_behavior_unestablished",
                "An explicit molecular implementation contract must bind selected components to the requested observations with an applicable, independently validated model adapter.",
            )
        )
    if acceptance is not None:
        diagnostics.extend(
            (
                DesignChoice(
                    "human_acceptance_empirical_support_unestablished",
                    "Required/prohibited observations and their bounds need independent human-context evidence.",
                ),
                DesignChoice(
                    "input_loss_response_unimplemented",
                    "Input availability detection and recovery have no supported mechanism mapping.",
                ),
                DesignChoice(
                    "external_shutdown_actuator_unimplemented",
                    "The shutdown observation requirement does not supply a supported actuator or priority override.",
                ),
            )
        )
    detail = "; ".join(dict.fromkeys(choice.code for choice in diagnostics))
    raise CompilationUnavailableError(
        "General intent-to-molecular realization is not implemented. "
        "Use run_molecular_pipeline with an independently pinned ConstructRequest for exact-reference CDS emission; "
        f"unresolved obligations: {detail}.",
        diagnostics=diagnostics,
    )
