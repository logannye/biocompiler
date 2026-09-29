"""Check supplied piecewise-constant traces against declared secretion bounds.

This checks a mathematical observation contract only. It does not simulate
biology, validate an assay or establish a source goal's therapeutic efficacy.
"""

from bisect import bisect_right
from dataclasses import dataclass
from typing import ClassVar

from cellweave.compiler.human_behavior import HumanBehaviorRequest
from cellweave.ir.serialization import fingerprint, names, require
from cellweave.semantics.human_behavior import SecretionSample, _Record
from cellweave.semantics.realization import _inside
from cellweave.semantics.types import DURATION, ScalarLiteral, decode_binding

CHECKER_VERSION = "cellweave.conditional_secretion_checker.v0.1"


@dataclass(frozen=True)
class SecretionTraceResult(_Record):
    request_fingerprint: str
    trace_fingerprint: str
    outcome: str
    checked_until: ScalarLiteral
    coverage: tuple[str, ...]
    diagnostics: tuple[str, ...]
    schema_version: ClassVar[str] = "cellweave.secretion_trace_result.v0.1"
    _fixed: ClassVar[dict] = {
        "checker": CHECKER_VERSION,
        "scope": "supplied_piecewise_constant_trace_only",
        "biological_applicability": "unestablished",
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
            and self.outcome in {"pass", "fail", "unknown"},
            "Invalid trace outcome.",
        )
        require(
            isinstance(self.checked_until, ScalarLiteral),
            "Expected typed checked horizon.",
        )
        from cellweave.semantics.realization import _duration

        object.__setattr__(
            self, "checked_until", _duration(self.checked_until, "checked horizon")
        )
        object.__setattr__(
            self, "coverage", tuple(sorted(names(self.coverage, "Coverage")))
        )
        object.__setattr__(self, "diagnostics", names(self.diagnostics, "Diagnostics"))
        require(
            set(self.coverage) <= {"active", "inactive", "recovered"},
            "Unknown coverage label.",
        )
        require(
            self.outcome != "pass"
            or set(self.coverage) == {"active", "inactive", "recovered"}
            and not self.diagnostics,
            "PASS requires non-vacuous coverage and no diagnostic.",
        )
        require(
            self.outcome == "pass" or bool(self.diagnostics),
            "Non-passing results require diagnostics.",
        )
        self._utf8()


def check_secretion_trace(request, samples):
    """Evaluate boundaries and deadlines without extrapolating beyond the trace.

    A pass requires positive-duration active, inactive and post-recovery coverage,
    plus the declared final horizon. Out-of-domain input is UNKNOWN. Missing or
    malformed typed measurements are errors. Imported results are never authority.
    """
    require(
        isinstance(request, HumanBehaviorRequest),
        "Expected HumanBehaviorRequest authority.",
    )
    # Freshly revalidate source correspondence instead of accepting artifact labels.
    request = HumanBehaviorRequest.from_dict(request.to_dict())
    require(
        isinstance(samples, (tuple, list))
        and samples
        and all(isinstance(item, SecretionSample) for item in samples),
        "Expected a nonempty complete SecretionSample trace.",
    )
    samples = tuple(samples)
    contract = request.contract
    times = tuple(item.time.canonical_value for item in samples)
    horizon = contract.horizon.canonical_value
    require(
        times[0] == 0
        and all(left < right for left, right in zip(times, times[1:]))
        and times[-1] <= horizon,
        "Trace must begin at zero, strictly increase and stay within the contract horizon.",
    )
    for item in samples:
        decode_binding(
            item.input_value.to_dict(), contract.input_measurement.observable.dtype
        )
        decode_binding(
            item.output_value.to_dict(), contract.output_measurement.observable.dtype
        )
    trace_id = fingerprint([item.to_dict() for item in samples])

    def result(outcome, coverage, diagnostics):
        return SecretionTraceResult(
            request.fingerprint,
            trace_id,
            outcome,
            samples[-1].time,
            tuple(coverage),
            tuple(dict.fromkeys(diagnostics)),
        )

    if any(not _inside(contract.input_range, item.input_value) for item in samples):
        return result("unknown", (), ("input_outside_declared_domain",))

    failures = []
    if contract.predicate.accepts(samples[0].input_value):
        failures.append("initial_input_must_be_inactive")
    if not _inside(contract.initial_range, samples[0].output_value):
        failures.append("initial_output_outside_initial_range")
    transitions = [(0, contract.predicate.accepts(samples[0].input_value))]
    for item in samples[1:]:
        active = contract.predicate.accepts(item.input_value)
        if active != transitions[-1][1]:
            transitions.append((item.time.canonical_value, active))
    transition_times = [time for time, _ in transitions]
    delays = {
        True: contract.response.max_activation_delay.canonical_value,
        False: contract.response.max_deactivation_delay.canonical_value,
    }
    points = sorted(
        set(times)
        | {
            time + delays[active]
            for time, active in transitions[1:]
            if time + delays[active] <= times[-1]
        }
    )
    coverage = set()
    for index, time in enumerate(points):
        sample = samples[bisect_right(times, time) - 1]
        transition_index = bisect_right(transition_times, time) - 1
        transition, active = transitions[transition_index]
        if sample.output_value.canonical_value < 0:
            failures.append(f"negative_secretion_rate_at:{time}")
        constrained = transition_index == 0 or time >= transition + delays[active]
        if not constrained:
            continue
        expected = (
            contract.response.active_range
            if active
            else contract.response.inactive_range
        )
        if not _inside(expected, sample.output_value):
            failures.append(
                f"{'active' if active else 'inactive'}_range_violation_at:{time}"
            )
        if index + 1 < len(points) and points[index + 1] > time:
            coverage.add("active" if active else "inactive")
            if not active and transition_index > 0:
                coverage.add("recovered")
    if failures:
        return result("fail", coverage, failures)
    missing = [
        f"unexercised_{key}_interval"
        for key in ("active", "inactive", "recovered")
        if key not in coverage
    ]
    if times[-1] < horizon:
        missing.append("trace_ends_before_declared_horizon")
    return result("unknown" if missing else "pass", coverage, missing)
