"""Bounded, source-authored software constraints; no biological cost model."""

from dataclasses import dataclass

from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.registry.synthetic import catalog_for_profile

STRATEGIES = ("native", "de_morgan")
COST_VERSION = "biocompiler.synthetic.gate_count.v0.1"
ZERO_COST_OPERATIONS = frozenset({"input", "constant", "output"})


def gate_count(mechanism):
    """Each operation other than input/constant/output costs one software gate."""
    return sum(node.kind not in ZERO_COST_OPERATIONS for node in mechanism.nodes)


@dataclass(frozen=True)
class SyntheticPolicy:
    allowed_operators: frozenset[str]
    max_gate_count: int | None
    minimize: str

    def violations(self, mechanism):
        result = []
        forbidden = sorted(
            {node.kind for node in mechanism.nodes} - self.allowed_operators
        )
        if forbidden:
            result.append("operator_not_allowed:" + ",".join(forbidden))
        cost = gate_count(mechanism)
        if self.max_gate_count is not None and cost > self.max_gate_count:
            result.append(f"gate_count_exceeded:{cost}>{self.max_gate_count}")
        return tuple(result)


def policy_for_request(request, profile):
    constraints = request.build_request.implementation_constraints
    preferences = request.build_request.preferences

    def reject(message):
        raise UnsupportedBehaviorError(message)

    if set(constraints) - {"allowed_operators", "max_gate_count"}:
        reject("Unsupported synthetic implementation-constraint fields.")
    if set(preferences) - {"minimize"}:
        reject("Unsupported synthetic preference fields.")
    available = {item.operation for item in catalog_for_profile(profile).components}
    allowed = constraints.get("allowed_operators", tuple(sorted(available)))
    if (
        not isinstance(allowed, (tuple, list))
        or any(not isinstance(item, str) for item in allowed)
        or len(set(allowed)) != len(allowed)
        or set(allowed) - available
    ):
        reject(
            "allowed_operators must be unique names in the selected synthetic catalog."
        )
    maximum = constraints.get("max_gate_count")
    if "max_gate_count" in constraints and (type(maximum) is not int or maximum < 0):
        reject("max_gate_count must be a nonnegative integer.")
    minimize = preferences.get("minimize", "gate_count")
    if not isinstance(minimize, str) or minimize not in {"gate_count", "none"}:
        reject("Synthetic minimize preference must be gate_count or none.")
    return SyntheticPolicy(frozenset(allowed), maximum, minimize)
