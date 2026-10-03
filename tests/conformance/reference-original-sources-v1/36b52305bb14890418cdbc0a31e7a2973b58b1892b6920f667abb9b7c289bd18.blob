"""Execution policies and preservation records for the abstract behavior profile.

These are exact language-level contracts. Future mechanism passes must add
observation maps, context assumptions and model-dependent refinement evidence;
source correspondence alone is never such evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import SourceLocation, freeze_json

EXECUTION_POLICIES = freeze_json(
    {
        "profile": "abstract_single_cell.v0.1",
        "time": "nonnegative_seconds_piecewise_constant",
        "initial_time": 0,
        "simultaneous_inputs": "atomic_snapshot",
        "contact_binding": "same_object_before_existential_aggregation",
        "local_action_binding": "existential_aggregate_then_onset",
        "targeted_action_binding": "per_contact_object",
        "memory_binding": "any_contact_onset_sets_cell_local_memory",
        "contact_disappearance": "clear_episode_history_and_contact_pulses",
        "observation_missing": "error",
        "qualitative_observations": "explicit_boolean",
        "state_reads": "shared_pre_update_state",
        "state_writes": "coalesce_identical_else_error",
        "state_propagation": "atomic_microsteps_until_stable",
        "condition_ongoing": "level",
        "condition_impulses": "onset",
        "event_ongoing": "explicit_duration_required",
        "initial_true": "rising_event",
        "held_for": "full_continuous_interval",
        "recently": "includes_present_excludes_expiry",
        "followed_by": "strictly_later_inclusive_window_nonconsuming",
        "memory_initial": False,
        "memory_visibility": "settled_controls_before_rule_effects",
        "memory_dependencies": "causal_topological_settlement",
        "memory_setting": "onset_latest_refresh",
        "memory_precedence": "reset_then_new_onset_then_expiry",
        "pulse_interval": "closed_start_open_end",
        "pulse_retrigger": "extend_from_latest_trigger",
        "timer_input_precedence": "external_snapshot_before_due_timers",
        "history": "since_initialization",
        "outputs": "abstract_requests_no_input_side_effects",
    }
)


def _string(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SerializationError(f"{label} must be a nonempty string.")


@dataclass(frozen=True)
class BehaviorRequirement:
    """A required rule or state declaration, identified within its source snapshot."""

    id: str
    kind: str
    source_node_id: str
    lineage: tuple[str, ...]
    source: SourceLocation | None = None

    def __post_init__(self) -> None:
        _string(self.id, "Requirement id")
        _string(self.source_node_id, "Requirement source node")
        if self.kind not in {"rule", "state", "memory"}:
            raise SerializationError("Unknown behavior requirement kind.")
        if not isinstance(self.lineage, (tuple, list)):
            raise SerializationError("Requirement lineage must be an array.")
        for item in self.lineage:
            _string(item, "Lineage reference")
        if len(set(self.lineage)) != len(self.lineage):
            raise SerializationError("Requirement lineage contains duplicates.")
        object.__setattr__(self, "lineage", tuple(self.lineage))
        if self.source is not None and not isinstance(self.source, SourceLocation):
            raise SerializationError("Requirement source must be a SourceLocation.")

    def to_dict(self, *, include_source: bool = True) -> dict:
        result = {
            "id": self.id,
            "kind": self.kind,
            "source_node_id": self.source_node_id,
            "lineage": list(self.lineage),
        }
        if include_source:
            result["source"] = self.source.to_dict() if self.source else None
        return result

    @classmethod
    def from_dict(cls, data: Mapping) -> BehaviorRequirement:
        if (
            not isinstance(data, Mapping)
            or set(data) - {"id", "kind", "source_node_id", "lineage", "source"}
            or {"id", "kind", "source_node_id", "lineage"} - set(data)
        ):
            raise SerializationError("Invalid requirement fields.")
        return cls(
            data["id"],
            data["kind"],
            data["source_node_id"],
            data["lineage"],
            SourceLocation.from_dict(data["source"])
            if data.get("source") is not None
            else None,
        )


@dataclass(frozen=True)
class PreservationCheck:
    """An exact checker result, never a claim of molecular realizability."""

    property: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class LoweringReport:
    source_fingerprint: str
    behavior_fingerprint: str
    checks: tuple[PreservationCheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)
