"""Bounded producer-side embeddings of independently supplied Behavior graphs.

This module proposes correspondences. Independent verification reconstructs each
selected correspondence from the library and never imports this matcher.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.circuit_intent import ExecutableCircuitBehavior
from biocompiler.ir.payload_architecture import (
    ArchitectureRefinementInstance, MAX_ARCHITECTURE_MATCH_STATES,
    MAX_ARCHITECTURE_RECORDS, PayloadArchitectureRefinement,
)
from biocompiler.ir.serialization import fingerprint, require


@dataclass(frozen=True)
class ArchitectureMatchResult:
    instances: tuple[ArchitectureRefinementInstance, ...]
    states_examined: int
    exhausted: bool
    diagnostics: tuple[str, ...] = ()


def architecture_instance_id(refinement, source_bindings):
    """Content-address a correspondence without changing its component model."""
    if refinement.match_policy is None:
        return refinement.id
    return refinement.id + ".match." + fingerprint({
        "refinement": refinement.fingerprint,
        "source_bindings": dict(source_bindings),
    })


def instantiate_architecture_refinement(refinement, instance):
    require(instance.refinement_id == refinement.id, "Instance refers to different supplied authority.")
    return replace(refinement, id=instance.id, source_bindings=instance.source_bindings, match_policy=None)


def _signature(node):
    return fingerprint({"kind": node.kind, "attributes": node.attributes,
                        "data_type": node.data_type, "contact_bound": node.contact_bound,
                        "input_count": len(node.inputs), "has_role": node.role is not None})


def _output_constraints(refinement, source, circuit):
    """Retain explicit output requirement identity as authority, never an alias."""
    if not refinement.output_contracts:
        return {}, (), ()
    if circuit is None:
        return {}, (), ("matching_output_authority_missing",)
    requirements = {item.id: item for item in circuit.requirements}
    nodes = {item.id: item for item in source.nodes}
    allowed, obligations, diagnostics = {}, [], []
    for output in refinement.output_contracts:
        requirement = requirements.get(output.requirement_id)
        if requirement is None:
            diagnostics.append("matching_output_requirement_absent:" + output.requirement_id)
            continue
        if (output.product.fingerprint != requirement.behavior.output.fingerprint
                or output.lifecycle.fingerprint != requirement.behavior.lifecycle.fingerprint):
            diagnostics.append("matching_output_contract_mismatch:" + output.requirement_id)
            continue
        installed = {action for rule in source.nodes
                     if rule.kind == "rule" and rule.id in requirement.source_node_ids
                     for action in rule.inputs[2:]}
        candidates = {identity for identity in installed
                      if identity in requirement.source_node_ids
                      and nodes[identity].role == requirement.role_id}
        exact = None
        if isinstance(requirement.behavior, ExecutableCircuitBehavior):
            exact = frozenset(requirement.behavior.action_ids)
            candidates.intersection_update(exact)
            if len(exact) != len(output.action_ids):
                diagnostics.append("matching_output_action_inventory:" + output.requirement_id)
                continue
        elif len(output.action_ids) != 1:
            diagnostics.append("matching_output_action_inventory:" + output.requirement_id)
            continue
        for local in output.action_ids:
            allowed[local] = candidates if local not in allowed else allowed[local] & candidates
        obligations.append((output.action_ids, exact))
    return allowed, tuple(obligations), tuple(diagnostics)


def match_architecture_refinement(refinement, source, *, circuit=None,
                                 max_states=100_000, max_instances=MAX_ARCHITECTURE_RECORDS):
    """Enumerate exact injective embeddings under global remaining budgets.

    One examined state is one attempted model/source node-pair constraint. Edge
    propagation, rejected candidates and anchor checks consume that same budget.
    Results are not truncated optimistically: discovering an additional result or
    needing another pair check returns explicit exhaustion. The iterative search
    uses an undo trail rather than copying a graph for every branch.
    """
    require(isinstance(refinement, PayloadArchitectureRefinement) and isinstance(source, BehaviorProgram),
            "Matching requires supplied refinement and original source behavior.")
    require(type(max_states) is int and 0 <= max_states <= MAX_ARCHITECTURE_MATCH_STATES,
            "Invalid remaining architecture matching work.")
    require(type(max_instances) is int and 0 <= max_instances <= MAX_ARCHITECTURE_RECORDS,
            "Invalid remaining architecture matching instances.")
    if (refinement.behavior.schema_version != source.schema_version
            or fingerprint(refinement.behavior.policies) != fingerprint(source.policies)):
        return ArchitectureMatchResult((), 0, False, ("matching_execution_policy_mismatch",))
    model = {node.id: node for node in refinement.behavior.nodes}
    original = {node.id: node for node in source.nodes}
    allowed, output_obligations, diagnostics = _output_constraints(refinement, source, circuit)
    if diagnostics:
        return ArchitectureMatchResult((), 0, False, diagnostics)
    model_signatures = {key: _signature(node) for key, node in model.items()}
    source_signatures = {key: _signature(node) for key, node in original.items()}
    source_index = {}
    for identity in sorted(original):
        source_index.setdefault(source_signatures[identity], []).append(identity)
    candidates = {}
    for identity in model:
        options = source_index.get(model_signatures[identity], ())
        if identity in refinement.source_bindings:
            anchor = refinement.source_bindings[identity]
            options = (anchor,) if anchor in options else ()
        if identity in allowed:
            options = tuple(value for value in options if value in allowed[identity])
        candidates[identity] = tuple(options)
    if any(not values for values in candidates.values()):
        return ArchitectureMatchResult((), 0, False, ("no_semantic_graph_match",))

    order = tuple(sorted(model, key=lambda key: (len(candidates[key]), key)))
    mapping, inverse, trail, matches = {}, {}, [], []
    examined = 0

    class Exhausted(Exception):
        pass

    def rollback(mark):
        while len(trail) > mark:
            identity = trail.pop()
            inverse.pop(mapping.pop(identity))

    def assign(identity, target):
        nonlocal examined
        pending = [(identity, target)]
        while pending:
            local, remote = pending.pop()
            if examined >= max_states:
                raise Exhausted
            examined += 1
            if local in mapping:
                if mapping[local] != remote:
                    return False
                continue
            if remote in inverse or remote not in original:
                return False
            if model_signatures[local] != source_signatures[remote]:
                return False
            if local in refinement.source_bindings and refinement.source_bindings[local] != remote:
                return False
            if local in allowed and remote not in allowed[local]:
                return False
            mapping[local], inverse[remote] = remote, local
            trail.append(local)
            left, right = model[local], original[remote]
            edges = list(zip(left.inputs, right.inputs))
            if left.role is not None:
                edges.append((left.role, right.role))
            pending.extend(reversed(edges))
        return True

    def retain():
        for local_ids, exact in output_obligations:
            if exact is not None and frozenset(mapping[ref] for ref in local_ids) != exact:
                return True
        if len(matches) >= max_instances:
            return False
        matches.append(ArchitectureRefinementInstance(
            architecture_instance_id(refinement, mapping), refinement.id, dict(mapping)))
        return True

    try:
        for identity, target in sorted(refinement.source_bindings.items()):
            if not assign(identity, target):
                return ArchitectureMatchResult((), examined, False, ("no_semantic_graph_match",))
        if len(mapping) == len(model):
            complete = retain()
            return ArchitectureMatchResult(tuple(matches), examined, not complete,
                () if complete else ("architecture_matching_instance_budget_exhausted",))
        identity = next(key for key in order if key not in mapping)
        stack = [(identity, iter(candidates[identity]), len(trail))]
        while stack:
            identity, choices, mark = stack[-1]
            rollback(mark)
            target = next(choices, None)
            if target is None:
                stack.pop()
                continue
            if not assign(identity, target):
                continue
            if len(mapping) == len(model):
                if not retain():
                    return ArchitectureMatchResult(tuple(matches), examined, True,
                        ("architecture_matching_instance_budget_exhausted",))
                continue
            identity = next(key for key in order if key not in mapping)
            stack.append((identity, iter(candidates[identity]), len(trail)))
    except Exhausted:
        return ArchitectureMatchResult(tuple(matches), examined, True,
                                       ("architecture_matching_work_budget_exhausted",))
    return ArchitectureMatchResult(tuple(sorted(matches, key=lambda item: item.id)), examined, False,
                                   () if matches else ("no_semantic_graph_match",))
