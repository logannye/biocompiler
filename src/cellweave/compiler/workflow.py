"""Inspect authoring inputs at the boundary to future molecular realization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import json
import math
from types import MappingProxyType
from typing import Any

from cellweave.compiler.request import BuildRequest, RealizationRequest
from cellweave.errors import (
    CompilationUnavailableError,
    DefinitionError,
    TypeMismatchError,
)
from cellweave.ir.intent import IntentProgram, freeze_json, thaw_json
from cellweave.frontend.expressions import _constant_value
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.semantics.types import (
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
        # No molecular backend exists in the authoring release.
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
            "schema_version": "cellweave.plan.v0.2",
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
    unresolved.append(
        DesignChoice(
            "molecular_backend_unavailable",
            "Intent-to-molecular mechanism selection is not implemented; exact-reference CDS emission requires a separately pinned ConstructRequest.",
        )
    )
    return RealizationPlan(program, profile, bindings, tuple(unresolved))


def compile(design: RealizationPlan | BuildRequest | RealizationRequest) -> None:
    """Reject unsupported general intent compilation; reference CDS uses its own API."""
    if not isinstance(design, (RealizationPlan, BuildRequest, RealizationRequest)):
        raise TypeMismatchError(
            "compile() requires a RealizationPlan, BuildRequest or RealizationRequest."
        )
    raise CompilationUnavailableError(
        "General intent-to-molecular realization is not implemented. "
        "Use run_molecular_pipeline with an independently pinned ConstructRequest for exact-reference CDS emission; "
        "inspect design.unresolved or design.to_json() for unresolved intent designs."
    )
