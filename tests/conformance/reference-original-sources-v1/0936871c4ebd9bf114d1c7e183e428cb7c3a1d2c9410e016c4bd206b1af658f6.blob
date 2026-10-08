"""Conjunctive, finite observation checking, independent of any implementation."""

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from typing import ClassVar

from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.ir.serialization import fingerprint, names, require
from biocompiler.semantics.acceptance import AcceptanceSample
from biocompiler.semantics.human_behavior import _Record
from biocompiler.semantics.realization import _duration, _inside
from biocompiler.semantics.types import DURATION, ScalarLiteral, decode_binding
from biocompiler.verification.deployment import check_deployment

CHECKER_VERSION = "biocompiler.human_acceptance_checker.v0.1"
COVERAGE = frozenset(
    {"active", "inactive", "recovered", "healthy", "input_loss_recovered", "shutdown"}
)


def _number(value):
    return Fraction(str(value.canonical_value))


@dataclass(frozen=True)
class HumanAcceptanceResult(_Record):
    request_fingerprint: str
    trace_fingerprint: str
    outcome: str
    checked_until: ScalarLiteral
    coverage: tuple[str, ...]
    diagnostics: tuple[str, ...]
    unresolved_evidence: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.human_acceptance_result.v0.1"
    _fixed: ClassVar[dict] = {
        "checker": CHECKER_VERSION,
        "scope": "declared_deployment_and_supplied_piecewise_constant_trace_only",
        "biological_applicability": "unestablished",
        "actuator_support": "unimplemented",
        "mechanism_selection": "blocked",
    }
    _decoders: ClassVar[dict] = {
        "checked_until": lambda data: decode_binding(data, DURATION)
    }

    def __post_init__(self):
        for value in (self.request_fingerprint, self.trace_fingerprint):
            require(
                isinstance(value, str)
                and len(value) == 64
                and set(value) <= set("0123456789abcdef"),
                "Invalid dependency fingerprint.",
            )
        require(
            isinstance(self.outcome, str)
            and self.outcome in {"pass", "fail", "unknown", "unsupported"},
            "Invalid acceptance outcome.",
        )
        object.__setattr__(
            self, "checked_until", _duration(self.checked_until, "checked horizon")
        )
        for key in ("coverage", "diagnostics", "unresolved_evidence"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        object.__setattr__(self, "coverage", tuple(sorted(self.coverage)))
        require(set(self.coverage) <= COVERAGE, "Unknown acceptance coverage label.")
        require(
            bool(self.unresolved_evidence),
            "Empirical and actuator evidence cannot be discharged here.",
        )
        require(
            (self.outcome == "pass") == (not self.diagnostics),
            "PASS requires no structural or trace diagnostic.",
        )
        require(
            self.outcome != "pass" or set(self.coverage) == COVERAGE,
            "PASS requires non-vacuous coverage of all acceptance scenarios.",
        )
        self._utf8()

    def is_current(self, request, samples):
        """Identity comparison only; acceptance always requires a fresh check."""
        require(
            isinstance(request, HumanAcceptanceRequest),
            "Expected HumanAcceptanceRequest.",
        )
        return (
            self.request_fingerprint == request.fingerprint
            and self.trace_fingerprint
            == fingerprint([item.to_dict() for item in samples])
        )


def check_human_acceptance(request, samples):
    """Check all known violations even when other observations are unknown.

    Cell access loss is a declared failure scenario with its own background
    requirement. It is never interpreted as a measured zero cue. Evaluator
    missingness is UNKNOWN. Healthy/control limits never override a known
    source guard: incompatible obligations are failures, not priorities.
    """
    require(
        isinstance(request, HumanAcceptanceRequest),
        "Expected HumanAcceptanceRequest authority.",
    )
    request = HumanAcceptanceRequest.from_dict(request.to_dict())
    require(
        isinstance(samples, (list, tuple))
        and samples
        and all(isinstance(item, AcceptanceSample) for item in samples),
        "Expected nonempty AcceptanceSample trace.",
    )
    samples = tuple(AcceptanceSample.from_dict(item.to_dict()) for item in samples)
    behavior, acceptance = request.behavior_request.contract, request.acceptance
    times = tuple(_number(item.time) for item in samples)
    require(
        times[0] == 0
        and all(a < b for a, b in zip(times, times[1:]))
        and times[-1] <= _number(behavior.horizon),
        "Trace must begin at zero, strictly increase and stay within the declared horizon.",
    )
    for item in samples:
        for value, dtype in (
            (item.input_value, behavior.input_measurement.observable.dtype),
            (item.output_value, behavior.output_measurement.observable.dtype),
            (item.context_value, acceptance.healthy_measurement.observable.dtype),
        ):
            if value is not None:
                decode_binding(value.to_dict(), dtype)
    deployment = check_deployment(request.deployment_request)
    failures, unknown, unsupported = [], [], []
    if deployment.compatibility != "pass":
        {"fail": failures, "unknown": unknown, "unsupported": unsupported}[
            deployment.compatibility
        ].extend(deployment.diagnostics)

    schedules, deadlines = [], set()
    previous, since, recovered = None, Fraction(0), False
    shutdown_at = None
    for time, item in zip(times, samples):
        if item.input_status == "available":
            if _inside(behavior.input_range, item.input_value):
                state = ("available", behavior.predicate.accepts(item.input_value))
            else:
                unknown.append(f"input_outside_declared_domain_at:{time}")
                state = ("unobserved", None)
        else:
            state = (item.input_status, None)
        if state[0] == "unobserved":
            unknown.append(f"input_unobserved_at:{time}")
        if state != previous:
            recovered = previous == ("available", True) and state == (
                "available",
                False,
            )
            since = time
        if state[0] == "available":
            delay = (
                behavior.response.max_activation_delay
                if state[1]
                else behavior.response.max_deactivation_delay
            )
            deadline = since + _number(delay)
            if since == 0 and state[1] is False:
                deadline = Fraction(0)
        elif state[0] == "cell_unavailable":
            deadline = since + _number(acceptance.input_availability.response_delay)
        else:
            deadline = None
        if deadline is not None:
            deadlines.add(deadline)
        schedules.append((state, deadline, recovered))
        previous = state
        if item.control_status == "unobserved":
            unknown.append(f"external_control_unobserved_at:{time}")
        elif item.control_status == "shutdown" and shutdown_at is None:
            shutdown_at = time + _number(acceptance.shutdown.response_delay)
            deadlines.add(shutdown_at)
        if item.output_value is None:
            unknown.append(f"output_unobserved_at:{time}")
        if item.context_value is None or not _inside(
            acceptance.context_domain, item.context_value
        ):
            unknown.append(f"healthy_context_unobserved_or_out_of_domain_at:{time}")

    first = samples[0]
    if first.input_status == "cell_unavailable" or (
        first.input_value is not None
        and _inside(behavior.input_range, first.input_value)
        and behavior.predicate.accepts(first.input_value)
    ):
        failures.append("initial_input_must_be_available_and_inactive")
    if first.output_value is not None and not _inside(
        behavior.initial_range, first.output_value
    ):
        failures.append("initial_output_outside_initial_range")
    if first.control_status == "shutdown":
        failures.append("initial_control_must_be_clear")

    points = sorted(
        set(times) | {value for value in deadlines if 0 <= value <= times[-1]}
    )
    coverage, bout_start = set(), None
    background = _number(acceptance.background_ceiling)
    for index, time in enumerate(points):
        sample_index = bisect_right(times, time) - 1
        item = samples[sample_index]
        state, deadline, recovered = schedules[sample_index]
        span = points[index + 1] - time if index + 1 < len(points) else Fraction(0)
        healthy = (
            item.context_value is not None
            and _inside(acceptance.context_domain, item.context_value)
            and _inside(acceptance.healthy_range, item.context_value)
        )
        source_due = state[0] == "available" and time >= deadline
        loss_due = state[0] == "cell_unavailable" and time >= deadline
        shutdown_due = shutdown_at is not None and time >= shutdown_at
        constraints = []
        if healthy:
            constraints.append("healthy")
        if loss_due:
            constraints.append("input_loss_recovered")
        if shutdown_due:
            constraints.append("shutdown")
        if source_due and not state[1]:
            constraints.append("inactive")
        if source_due and state[1] and constraints:
            failures.append(
                f"required_active_conflicts_with_{'+'.join(constraints)}_at:{time}"
            )
        if span > 0:
            coverage.update(constraints)
            if source_due:
                coverage.add("active" if state[1] else "inactive")
                if recovered:
                    coverage.add("recovered")
        if item.output_value is None:
            bout_start = None
            continue
        rate = _number(item.output_value)
        if rate < 0:
            failures.append(f"negative_secretion_rate_at:{time}")
        if rate > _number(acceptance.peak_ceiling):
            failures.append(f"peak_ceiling_exceeded_at:{time}")
        if constraints and rate > background:
            failures.extend(
                f"{key}_background_exceeded_at:{time}" for key in constraints
            )
        if source_due:
            expected = (
                behavior.response.active_range
                if state[1]
                else behavior.response.inactive_range
            )
            if not _inside(expected, item.output_value):
                failures.append(
                    f"{'active' if state[1] else 'inactive'}_range_violation_at:{time}"
                )
        if rate > background:
            if bout_start is None:
                bout_start = time
            if time + span - bout_start > _number(acceptance.max_response_duration):
                failures.append(
                    f"response_duration_exceeded_in_interval_starting:{time}"
                )
        else:
            bout_start = None

    unknown.extend(f"unexercised_{key}_interval" for key in sorted(COVERAGE - coverage))
    if times[-1] < _number(behavior.horizon):
        unknown.append("trace_ends_before_declared_horizon")
    outcome = (
        "fail"
        if failures
        else "unsupported"
        if unsupported
        else "unknown"
        if unknown
        else "pass"
    )
    return HumanAcceptanceResult(
        request.fingerprint,
        fingerprint([item.to_dict() for item in samples]),
        outcome,
        samples[-1].time,
        tuple(coverage),
        tuple(dict.fromkeys(failures + unsupported + unknown)),
        (
            *deployment.unresolved_evidence,
            *(f"acceptance.{path}" for path in acceptance.unresolved_evidence),
        ),
    )
