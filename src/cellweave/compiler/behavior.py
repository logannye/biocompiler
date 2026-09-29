"""Checked intent-to-behavior lowering, retaining every source requirement.

This pass binds design constants and resolves execution policies. It selects no
molecular components and supplies no biological evidence. Its independent
checker compares complete source operations and provenance, not just graph size.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from cellweave.errors import (
    LoweringVerificationError,
    SerializationError,
    TypeMismatchError,
    UnsupportedBehaviorError,
)
from cellweave.ir.behavior import (
    BehaviorNode,
    BehaviorProgram,
    SUPPORTED_KINDS,
    contact_bindings,
    constant_value,
    lineage_for,
)
from cellweave.ir.intent import IntentNode, IntentProgram, thaw_json
from cellweave.semantics.contracts import (
    BehaviorRequirement,
    LoweringReport,
    PreservationCheck,
)
from cellweave.semantics.types import TypeSpec, decode_binding, validate_binding


def _unsupported(node: IntentNode, message: str) -> None:
    raise UnsupportedBehaviorError(message, node_id=node.id, source=node.source)


def _check_source_profile(program: IntentProgram) -> None:
    nodes = {node.id: node for node in program.nodes}
    for node in program.nodes:
        if node.kind not in SUPPORTED_KINDS:
            _unsupported(
                node,
                f"Operation {node.kind!r} needs an additional execution profile or semantic refinement.",
            )
        if (
            node.kind in {"literal", "parameter"}
            and TypeSpec.from_dict(node.data_type).kind != "scalar"
        ):
            _unsupported(
                node,
                "The first behavior profile supports bound scalar design values only.",
            )
        if node.kind == "state":
            if (
                node.attributes.get("observation") != "prior_state"
                or node.attributes.get("arbitration") != "unspecified"
            ):
                _unsupported(
                    node, "Unknown source state-read or arbitration semantics."
                )
        elif node.kind == "rule":
            attrs = node.attributes
            if (
                attrs.get("execution") != "concurrent"
                or attrs.get("priority") != "unspecified"
            ):
                _unsupported(
                    node, "Unknown source rule execution or priority semantics."
                )
            trigger = attrs.get("trigger")
            if trigger not in {"condition", "event"}:
                _unsupported(node, "Unknown source trigger semantics.")
            allowed = {"trigger", "execution", "priority", "name"}
            if trigger == "event":
                allowed.add("ongoing_duration")
                if attrs.get("ongoing_duration") != "explicit_or_design_choice":
                    _unsupported(node, "Unknown source event-duration semantics.")
                for ref in node.inputs[2:]:
                    action = nodes[ref]
                    if (
                        action.attributes.get("ongoing")
                        and action.kind != "action.pulse"
                    ):
                        _unsupported(
                            node,
                            "Event-triggered ongoing actions require an explicit duration via for_().",
                        )
            if set(attrs) - allowed:
                _unsupported(node, "Unrecognized source rule policy fields.")
        elif (
            node.kind == "action.pulse"
            and node.inputs
            and nodes[node.inputs[0]].kind == "action.pulse"
        ):
            _unsupported(
                node, "Nested pulses need an explicit duration-composition policy."
            )


def _bind_parameters(
    program: IntentProgram, parameters: Mapping[str, Any] | None
) -> dict:
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, Mapping):
        raise TypeMismatchError("Parameter bindings must be a mapping.")
    declarations = {
        node.attributes["name"]: node for node in program.find(kind="parameter")
    }
    unknown = set(parameters) - declarations.keys()
    if unknown:
        raise TypeMismatchError(
            f"Unknown parameter bindings: {', '.join(sorted(map(str, unknown)))}."
        )
    bindings = {}
    for name, node in declarations.items():
        if name in parameters:
            bindings[name] = validate_binding(
                parameters[name], TypeSpec.from_dict(node.data_type)
            )
        elif node.attributes["bound"]:
            bindings[name] = thaw_json(node.attributes["default"])
        else:
            _unsupported(
                node,
                f"Design parameter {name!r} must be bound before behavior execution.",
            )
    return bindings


def _normalized_attributes(node: IntentNode, bindings: Mapping[str, Any]) -> dict:
    attrs = thaw_json(node.attributes)
    if node.kind == "parameter":
        attrs.update(bound=True, default=thaw_json(bindings[attrs["name"]]))
    elif node.kind == "state":
        attrs.update(
            observation="shared_pre_update_state",
            arbitration="coalesce_identical_else_error",
        )
    elif node.kind == "rule":
        event = attrs["trigger"] == "event"
        attrs.update(
            priority="none",
            ongoing_activation="explicit_duration" if event else "level",
            impulse_activation="event" if event else "onset",
            state_assignment="event" if event else "level",
        )
        if event:
            attrs["ongoing_duration"] = "explicit"
    return attrs


def lower_to_behavior(
    program: IntentProgram, *, parameters: Mapping[str, Any] | None = None
) -> BehaviorProgram:
    """Resolve the supported abstract execution profile or reject the whole graph.

    Original node identities are retained for history bindings and diagnostics.
    Bound constants, requirements and source ancestry are serialized in the result.
    No unsupported construct is discarded merely because it has no immediate output.
    """
    if not isinstance(program, IntentProgram):
        raise TypeMismatchError("lower_to_behavior() requires an IntentProgram.")
    _check_source_profile(program)
    bindings = _bind_parameters(program, parameters)
    source_nodes = {node.id: node for node in program.nodes}
    links = {node.id: lineage_for(source_nodes, node.id) for node in program.nodes}
    requirements = tuple(
        BehaviorRequirement(
            f"requirement:{node.id}", node.kind, node.id, links[node.id], node.source
        )
        for node in program.nodes
        if node.kind in {"rule", "state", "memory"}
    )
    # Derive contact binding after strict operation validation by the constructed
    # program; malformed source arities get a source-linked error here as well.
    try:
        contacts = contact_bindings(source_nodes)
        nodes = tuple(
            BehaviorNode(
                id=node.id,
                kind=node.kind,
                inputs=node.inputs,
                attributes=_normalized_attributes(node, bindings),
                data_type=node.data_type,
                role=node.role,
                source=node.source,
                contact_bound=contacts[node.id],
                requirement_ids=tuple(
                    req.id for req in requirements if node.id in req.lineage
                ),
            )
            for node in program.nodes
        )
        bound_nodes = {node.id: node for node in nodes}
        for node in nodes:
            duration_ref = None
            if (
                node.kind in {"held_for", "recently", "action.pulse"}
                and len(node.inputs) == 2
            ):
                duration_ref = node.inputs[1]
            elif node.kind == "followed_by" and len(node.inputs) == 3:
                duration_ref = node.inputs[2]
            elif node.kind == "memory" and "duration" in node.attributes.get(
                "input_names", ()
            ):
                duration_ref = node.inputs[
                    node.attributes["input_names"].index("duration")
                ]
            if (
                duration_ref is not None
                and constant_value(bound_nodes, duration_ref) is None
            ):
                _unsupported(
                    source_nodes[node.id],
                    "A temporal duration must be a bound design-time constant.",
                )
        result = BehaviorProgram(
            program.name,
            nodes,
            program.roots,
            program.fingerprint,
            requirements,
            links,
            parameter_bindings=bindings,
        )
    except (KeyError, IndexError) as exc:
        raise SerializationError(
            f"Malformed source operation during behavior lowering: {exc}"
        ) from exc
    verify_lowering(program, result)
    return result


def verify_lowering(intent: IntentProgram, behavior: BehaviorProgram) -> LoweringReport:
    """Check exact correspondence for this pass; raise on any changed obligation.

    Checks cover retained operations/edges/types/scopes, explicitly permitted
    parameter substitution and policy normalization, and full requirement/source
    lineage. They are not a proof that biological mechanisms implement the graph.
    """
    if not isinstance(intent, IntentProgram) or not isinstance(
        behavior, BehaviorProgram
    ):
        raise TypeMismatchError(
            "verify_lowering() requires IntentProgram and BehaviorProgram."
        )
    checks = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append(PreservationCheck(name, passed, detail))
        if not passed:
            raise LoweringVerificationError(f"{name}: {detail}")

    _check_source_profile(intent)
    check(
        "source_identity",
        behavior.source_fingerprint == intent.fingerprint
        and behavior.name == intent.name,
        "The source fingerprint and program identity must match.",
    )
    original = {node.id: node for node in intent.nodes}
    emitted = {node.id: node for node in behavior.nodes}
    check(
        "complete_graph",
        tuple(original) == tuple(emitted) and intent.roots == behavior.roots,
        "Every source node and root must be retained in deterministic order.",
    )
    # Independently validate serialized bindings against their source declarations;
    # override values are deliberate design inputs, not constraints to source defaults.
    expected_names = {node.attributes["name"] for node in intent.find(kind="parameter")}
    check(
        "parameter_inventory",
        set(behavior.parameter_bindings) == expected_names,
        "Bindings must cover exactly the declared design parameters.",
    )
    for node in intent.find(kind="parameter"):
        try:
            decode_binding(
                behavior.parameter_bindings[node.attributes["name"]],
                TypeSpec.from_dict(node.data_type),
            )
        except (TypeMismatchError, ValueError) as exc:
            raise LoweringVerificationError(
                f"Invalid parameter binding for {node.id}: {exc}"
            ) from exc
    for node_id, source in original.items():
        target = emitted[node_id]
        check(
            f"operation:{node_id}",
            source.kind == target.kind
            and source.inputs == target.inputs
            and source.role == target.role
            and source.data_type == target.data_type,
            "Operation, dependencies, role and semantic type must be preserved.",
        )
        check(
            f"semantics:{node_id}",
            json.dumps(thaw_json(target.attributes), sort_keys=True)
            == json.dumps(
                _normalized_attributes(source, behavior.parameter_bindings),
                sort_keys=True,
            ),
            "Only declared parameter binding and execution-policy normalization may change attributes.",
        )
        check(
            f"source:{node_id}",
            source.source == target.source,
            "Authoring source location must be retained.",
        )
    expected_links = {node.id: lineage_for(original, node.id) for node in intent.nodes}
    expected_reqs = tuple(
        BehaviorRequirement(
            f"requirement:{node.id}",
            node.kind,
            node.id,
            expected_links[node.id],
            node.source,
        )
        for node in intent.nodes
        if node.kind in {"rule", "state", "memory"}
    )
    check(
        "requirements_and_lineage",
        behavior.requirements == expected_reqs
        and dict(behavior.source_links) == expected_links,
        "All rule/state/memory requirements and ancestor source links must survive.",
    )
    expected_contacts = contact_bindings(original)
    check(
        "identity_binding",
        all(
            node.contact_bound == expected_contacts[node.id] for node in behavior.nodes
        ),
        "Contact-object correlation and cell-local state boundaries must be retained.",
    )
    return LoweringReport(intent.fingerprint, behavior.fingerprint, tuple(checks))
