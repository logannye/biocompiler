"""Two bounded digital implementations, independently checked before ranking.

This is whole-program native-AND versus De Morgan lowering, not arbitrary graph
search. Imported reports are historical records and never establish acceptance.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import ClassVar

from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.ir.serialization import JsonArtifact, fields, names, require
from biocompiler.semantics.evaluator import InputFrame
from biocompiler.synthesis.policy import (
    COST_VERSION,
    STRATEGIES,
    gate_count,
    policy_for_request,
)
from biocompiler.synthesis.synthetic import (
    SyntheticCandidate,
    SyntheticGeneratorConfig,
    _generate_synthetic,
    _identity,
    check_synthetic_candidate,
)
from biocompiler.verification.evidence import CheckOutcome, CheckResult

SELECTION_VERSION = "biocompiler.synthetic.selection.v0.1"


def _valid_horizon(value):
    try:
        return value is None or (
            type(value) in (int, float) and math.isfinite(value) and value >= 0
        )
    except (OverflowError, ValueError):
        return False


@dataclass(frozen=True)
class SyntheticAlternative(JsonArtifact):
    strategy: str
    candidate: SyntheticCandidate | None
    constraint_violations: tuple[str, ...] = ()
    check: CheckResult | None = None
    generation_error: str | None = None
    schema_version: ClassVar[str] = "biocompiler.synthetic_alternative.v0.1"

    def __post_init__(self):
        require(self.strategy in STRATEGIES, "Unknown bounded strategy.")
        require(
            self.candidate is None or isinstance(self.candidate, SyntheticCandidate),
            "Expected a synthetic candidate or null.",
        )
        require(
            self.check is None or isinstance(self.check, CheckResult),
            "Expected independent check or null.",
        )
        object.__setattr__(
            self,
            "constraint_violations",
            names(self.constraint_violations, "Constraint violations"),
        )
        if self.candidate is None:
            require(
                isinstance(self.generation_error, str)
                and bool(self.generation_error)
                and self.check is None
                and not self.constraint_violations,
                "Ungenerated alternatives require an explicit error only.",
            )
        else:
            require(
                self.candidate.generator_config.conjunction_strategy == self.strategy
                and self.generation_error is None,
                "Strategy and candidate disagree.",
            )
            require(
                (bool(self.constraint_violations) and self.check is None)
                or (not self.constraint_violations and self.check is not None),
                "Every structurally eligible alternative needs an independent check.",
            )
            if self.check is not None:
                deps = self.check.dependencies.values
                require(
                    deps["mechanism"] == self.candidate.mechanism.fingerprint
                    and deps["observation_map"]
                    == self.candidate.observation_map.fingerprint
                    and deps["settings"].get("synthetic_candidate")
                    == self.candidate.fingerprint,
                    "Alternative check identifies another candidate.",
                )

    @property
    def gate_count(self):
        return gate_count(self.candidate.mechanism) if self.candidate else None

    @property
    def status(self):
        if self.generation_error:
            return "unsupported"
        if self.constraint_violations:
            return "hard_rejected"
        return self.check.outcome.value

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "strategy": self.strategy,
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "constraint_violations": list(self.constraint_violations),
            "check": self.check.to_dict() if self.check else None,
            "generation_error": self.generation_error,
            "gate_count": self.gate_count,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "strategy",
                "candidate",
                "constraint_violations",
                "check",
                "generation_error",
                "gate_count",
                "status",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported alternative schema.",
        )
        result = cls(
            data["strategy"],
            SyntheticCandidate.from_dict(data["candidate"])
            if data["candidate"] is not None
            else None,
            data["constraint_violations"],
            CheckResult.from_dict(data["check"]) if data["check"] is not None else None,
            data["generation_error"],
        )
        require(
            type(data["gate_count"]) is type(result.gate_count)
            and data["gate_count"] == result.gate_count
            and data["status"] == result.status,
            "Alternative summary disagrees with its artifacts.",
        )
        return result


@dataclass(frozen=True)
class SyntheticSelectionResult(JsonArtifact):
    request_fingerprint: str
    history_fingerprint: str
    until: float | int | None
    config: SyntheticGeneratorConfig
    minimize: str
    alternatives: tuple[SyntheticAlternative, ...]
    schema_version: ClassVar[str] = "biocompiler.synthetic_selection_result.v0.1"

    def __post_init__(self):
        _identity(self.request_fingerprint, "Realization request")
        _identity(self.history_fingerprint, "Input history")
        require(_valid_horizon(self.until), "Invalid selection horizon.")
        require(
            isinstance(self.config, SyntheticGeneratorConfig),
            "Expected generator configuration.",
        )
        require(
            isinstance(self.minimize, str) and self.minimize in {"gate_count", "none"},
            "Unknown ranking policy.",
        )
        require(
            isinstance(self.alternatives, (tuple, list))
            and all(
                isinstance(item, SyntheticAlternative) for item in self.alternatives
            ),
            "Expected bounded alternatives.",
        )
        alternatives = tuple(self.alternatives)
        require(
            tuple(item.strategy for item in alternatives) == STRATEGIES,
            "The complete bounded search contains native then de_morgan exactly once.",
        )
        object.__setattr__(self, "alternatives", alternatives)
        for item in alternatives:
            if item.candidate is not None:
                require(
                    item.candidate.request_fingerprint == self.request_fingerprint
                    and item.candidate.generator_config
                    == replace(self.config, conjunction_strategy=item.strategy),
                    "Alternative belongs to another request/configuration.",
                )
            if item.check is not None:
                deps = item.check.dependencies.values
                require(
                    deps["history"] == self.history_fingerprint
                    and deps["horizon"]["until"] == self.until
                    and deps["settings"].get("realization_request")
                    == self.request_fingerprint,
                    "Alternative check belongs to another history/horizon/request.",
                )

    @property
    def selected_strategy(self):
        eligible = [
            item
            for item in self.alternatives
            if item.check is not None and item.check.outcome == CheckOutcome.PASS
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda item: (
                item.gate_count if self.minimize == "gate_count" else 0,
                STRATEGIES.index(item.strategy),
            ),
        ).strategy

    @property
    def candidate(self):
        return next(
            (
                item.candidate
                for item in self.alternatives
                if item.strategy == self.selected_strategy
            ),
            None,
        )

    @property
    def outcome(self):
        if self.candidate is not None:
            return "selected"
        if any(
            item.check is not None and item.check.outcome == CheckOutcome.UNKNOWN
            for item in self.alternatives
        ):
            return "unknown"
        if any(
            item.generation_error
            or (
                item.check is not None
                and item.check.outcome == CheckOutcome.UNSUPPORTED
            )
            for item in self.alternatives
        ):
            return "unsupported"
        return "exhausted"

    @property
    def checked_candidates(self):
        return sum(item.check is not None for item in self.alternatives)

    @property
    def rejected_candidates(self):
        return sum(
            bool(item.constraint_violations)
            or (item.check is not None and item.check.outcome == CheckOutcome.FAIL)
            for item in self.alternatives
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "selection_version": SELECTION_VERSION,
            "cost_version": COST_VERSION,
            "intended_use": "software_test",
            "human_therapeutic_admission": "not_admitted",
            "request_fingerprint": self.request_fingerprint,
            "history_fingerprint": self.history_fingerprint,
            "until": self.until,
            "config": self.config.to_dict(),
            "minimize": self.minimize,
            "alternatives": [item.to_dict() for item in self.alternatives],
            "selected_strategy": self.selected_strategy,
            "outcome": self.outcome,
            "checked_candidates": self.checked_candidates,
            "rejected_candidates": self.rejected_candidates,
            "search_scope": "two_whole_program_conjunction_strategies",
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "selection_version",
                "cost_version",
                "intended_use",
                "human_therapeutic_admission",
                "request_fingerprint",
                "history_fingerprint",
                "until",
                "config",
                "minimize",
                "alternatives",
                "selected_strategy",
                "outcome",
                "checked_candidates",
                "rejected_candidates",
                "search_scope",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version
            and data["selection_version"] == SELECTION_VERSION
            and data["cost_version"] == COST_VERSION
            and data["intended_use"] == "software_test"
            and data["human_therapeutic_admission"] == "not_admitted"
            and data["search_scope"] == "two_whole_program_conjunction_strategies",
            "Unsupported selection schema/policy.",
        )
        require(
            isinstance(data["alternatives"], (tuple, list)),
            "Expected alternatives array.",
        )
        result = cls(
            data["request_fingerprint"],
            data["history_fingerprint"],
            data["until"],
            SyntheticGeneratorConfig.from_dict(data["config"]),
            data["minimize"],
            tuple(
                SyntheticAlternative.from_dict(item) for item in data["alternatives"]
            ),
        )
        for key in (
            "selected_strategy",
            "outcome",
            "checked_candidates",
            "rejected_candidates",
        ):
            require(
                type(data[key]) is type(getattr(result, key))
                and data[key] == getattr(result, key),
                "Selection summary disagrees with checked alternatives.",
            )
        return result


def select_synthetic(request, history, *, until=None, config=None):
    """Generate both strategies, enforce hard constraints, check all eligible, rank.

    The sole enumerated configuration axis is conjunction_strategy. All other
    configuration fields remain fixed. Equal graphs without AND are retained as
    two strategy records; this never counts as exploring other graph families.
    """
    config = SyntheticGeneratorConfig() if config is None else config
    require(_valid_horizon(until), "Invalid selection horizon.")
    require(
        isinstance(config, SyntheticGeneratorConfig),
        "Expected generator configuration.",
    )
    policy = policy_for_request(request, config.profile_version)
    frames = tuple(history)
    require(
        all(isinstance(frame, InputFrame) for frame in frames),
        "Expected InputFrame history.",
    )
    # Match the existing independent realization checker's history identity.
    history_identity = hashlib.sha256(
        json.dumps(
            [frame.to_dict() for frame in frames],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    alternatives = []
    for strategy in STRATEGIES:
        try:
            candidate = _generate_synthetic(
                request, config=replace(config, conjunction_strategy=strategy)
            )
        except UnsupportedBehaviorError as error:
            alternatives.append(
                SyntheticAlternative(strategy, None, generation_error=str(error))
            )
            continue
        violations = policy.violations(candidate.mechanism)
        check = (
            None
            if violations
            else check_synthetic_candidate(request, candidate, frames, until=until)
        )
        alternatives.append(
            SyntheticAlternative(strategy, candidate, violations, check)
        )
    return SyntheticSelectionResult(
        request.fingerprint,
        history_identity,
        until,
        config,
        policy.minimize,
        tuple(alternatives),
    )
