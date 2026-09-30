"""Explicit finite Boolean history exploration and failure-preserving reduction.

Enumeration coverage is separate from each finite-history CheckResult. These
utilities never turn missing coverage, UNKNOWN or a capped prefix into a proof.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields
import hashlib
import json
import math
from types import MappingProxyType
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name as _base_name,
    names as _base_names,
    require,
)
from biocompiler.semantics.evaluator import InputFrame, SignalSample
from biocompiler.verification.evidence import (
    CheckDiagnostic,
    CheckOutcome,
    CheckResult,
    Counterexample,
    RequirementCoverage,
)

EXPLORATION_VERSION = "biocompiler.boolean_exploration.v0.1"
CLAIM_SCOPE = (
    "Only the declared Boolean contact states on the variable time lattice with "
    "the exact fixed suffix and finite horizon are enumerated. Completion means "
    "enumeration coverage, not whole-profile, temporal or biological refinement."
)


def _utf8(value):
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise SerializationError("Exploration text must be valid UTF-8.") from error
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _utf8(key)
            _utf8(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _utf8(item)


def name(value, label):
    result = _base_name(value, label)
    _utf8(result)
    return result


def names(values, label):
    result = _base_names(values, label)
    _utf8(result)
    return result


def _time(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    require(valid, "Exploration times must be finite nonnegative numbers.")
    return value


def _integer(value, lower, upper, label):
    require(type(value) is int and lower <= value <= upper, f"Invalid {label}.")


def _history_hash(history):
    # This is the existing realization checker's exact history identity format.
    return hashlib.sha256(
        json.dumps(
            [frame.to_dict() for frame in history],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _frame(data):
    fields(data, {"time", "signals", "contacts"}, "InputFrame")

    def samples(values):
        require(isinstance(values, Mapping), "Samples must be a mapping.")
        result = {}
        for key, value in values.items():
            fields(value, {"value", "present", "high", "low"}, "SignalSample")
            result[key] = SignalSample(**value)
        return result

    require(isinstance(data["contacts"], Mapping), "Contacts must be a mapping.")
    return InputFrame(
        data["time"],
        samples(data["signals"]),
        {key: samples(value) for key, value in data["contacts"].items()},
    )


def _frames(values):
    require(isinstance(values, (tuple, list)), "History must be an array.")
    return tuple(_frame(value) for value in values)


def _history(values, until, *, initial=True):
    require(
        isinstance(values, (tuple, list))
        and all(isinstance(item, InputFrame) for item in values),
        "History must contain frozen InputFrames.",
    )
    values = tuple(values)
    for frame in values:
        _utf8(frame.to_dict())
    _time(until)
    require(
        not initial or bool(values) and values[0].time == 0,
        "History must start at time zero.",
    )
    require(
        all(a.time < b.time for a, b in zip(values, values[1:]))
        and all(item.time <= until for item in values),
        "History times must increase within the fixed horizon.",
    )
    return values


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _derived: ClassVar[tuple] = ()

    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if isinstance(value, Mapping):
                return {key: encode(item) for key, item in value.items()}
            return value

        return {
            "schema_version": self.schema_version,
            **{
                field.name: encode(getattr(self, field.name))
                for field in dataclass_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        try:
            _utf8(data)
            fields(
                data,
                {field.name for field in dataclass_fields(cls)}
                | {"schema_version"}
                | set(cls._derived),
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                "Unsupported exploration schema.",
            )
            result = cls(
                **{
                    field.name: cls._decoders.get(field.name, lambda value: value)(
                        data[field.name]
                    )
                    for field in dataclass_fields(cls)
                }
            )
            for key in cls._derived:
                require(
                    fingerprint(data[key]) == fingerprint(result.to_dict()[key]),
                    f"Inconsistent exploration {key}.",
                )
            return result
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            AttributeError,
            IndexError,
            OverflowError,
            RecursionError,
        ) as error:
            raise SerializationError(f"Invalid {cls.__name__}: {error}") from error


def _decode_array(value, cls):
    require(isinstance(value, (tuple, list)), "Exploration records must be an array.")
    return tuple(cls.from_dict(item) for item in value)


@dataclass(frozen=True)
class BooleanObservation(_Record):
    signal_id: str
    field: str = "present"
    schema_version: ClassVar[str] = "biocompiler.boolean_observation.v0.1"

    def __post_init__(self):
        name(self.signal_id, "Signal ID")
        require(
            isinstance(self.field, str) and self.field in {"present", "high", "low"},
            "Exploration requires a Boolean observation field.",
        )


@dataclass(frozen=True)
class BooleanContactConfig(_Record):
    contact_ids: tuple[str, ...]
    observations: tuple[BooleanObservation, ...]
    variable_times: tuple[int | float, ...]
    until: int | float
    fixed_suffix: tuple[InputFrame, ...] = ()
    max_histories: int = 10000
    schema_version: ClassVar[str] = "biocompiler.boolean_contact_config.v0.1"
    _decoders: ClassVar[dict] = {
        "observations": lambda value: _decode_array(value, BooleanObservation),
        "fixed_suffix": _frames,
    }

    def __post_init__(self):
        object.__setattr__(self, "contact_ids", names(self.contact_ids, "Contact IDs"))
        require(
            1 <= len(self.contact_ids) <= 8,
            "Exploration supports one to eight fixed contact IDs.",
        )
        require(
            isinstance(self.observations, (tuple, list))
            and 1 <= len(self.observations) <= 8
            and all(isinstance(item, BooleanObservation) for item in self.observations),
            "Exploration supports one to eight Boolean observations.",
        )
        object.__setattr__(self, "observations", tuple(self.observations))
        require(
            len({(item.signal_id, item.field) for item in self.observations})
            == len(self.observations),
            "Duplicate Boolean observation.",
        )
        require(
            isinstance(self.variable_times, (tuple, list))
            and 1 <= len(self.variable_times) <= 16,
            "Exploration needs one to sixteen variable times.",
        )
        times = tuple(_time(value) for value in self.variable_times)
        require(
            times[0] == 0 and all(a < b for a, b in zip(times, times[1:])),
            "Variable lattice must start at zero and strictly increase.",
        )
        _time(self.until)
        require(times[-1] <= self.until, "Variable lattice exceeds the horizon.")
        object.__setattr__(self, "variable_times", times)
        suffix = _history(self.fixed_suffix, self.until, initial=False)
        require(
            not suffix or suffix[0].time > times[-1],
            "Fixed suffix must follow all variable times.",
        )
        for frame in suffix:
            _complete_snapshot(self, frame)
        object.__setattr__(self, "fixed_suffix", suffix)
        _integer(self.max_histories, 1, 100000, "history evaluation cap")

    @property
    def state_count(self):
        return (1 + 2 ** len(self.observations)) ** len(self.contact_ids)

    @property
    def possible_histories(self):
        return self.state_count ** len(self.variable_times)


def _complete_snapshot(config, frame):
    require(
        not frame.signals and set(frame.contacts) <= set(config.contact_ids),
        "Snapshot contains signals or contacts outside the Boolean bounds.",
    )
    expected = {(item.signal_id, item.field) for item in config.observations}
    signal_ids = {item.signal_id for item in config.observations}
    for samples in frame.contacts.values():
        require(
            set(samples) == signal_ids,
            "Present contacts require the complete declared signal inventory.",
        )
        for signal_id, sample in samples.items():
            for key, value in sample.to_dict().items():
                require(
                    type(value) is bool
                    if (signal_id, key) in expected
                    else value is None,
                    "Snapshot observations differ from the declared Boolean bounds.",
                )


def _snapshot(config, time, code):
    contacts = {}
    radix = 1 + 2 ** len(config.observations)
    for identity in config.contact_ids:
        code, state = divmod(code, radix)
        if state == 0:
            continue
        state -= 1
        samples = {}
        for index, observation in enumerate(config.observations):
            samples.setdefault(observation.signal_id, {})[observation.field] = bool(
                state & (1 << index)
            )
        contacts[identity] = {
            key: SignalSample(**value) for key, value in samples.items()
        }
    return InputFrame(time, contacts=contacts)


def _history_at(config, index):
    codes = [0] * len(config.variable_times)
    for position in reversed(range(len(codes))):
        index, codes[position] = divmod(index, config.state_count)
    return (
        tuple(
            _snapshot(config, time, code)
            for time, code in zip(config.variable_times, codes)
        )
        + config.fixed_suffix
    )


def enumerate_boolean_histories(config: BooleanContactConfig):
    """Yield a deterministic prefix; count/cap completeness belongs to the report."""
    require(
        isinstance(config, BooleanContactConfig), "Expected Boolean contact bounds."
    )
    for index in range(min(config.possible_histories, config.max_histories)):
        yield _history_at(config, index)


def _stable_dependencies(result):
    return {
        key: thaw_json(value)
        for key, value in result.dependencies.values.items()
        if key != "history"
    }


def _validate_result(result, history, until, stable=None):
    require(
        isinstance(result, CheckResult), "History evaluator must return a CheckResult."
    )
    _utf8(result.to_dict())
    dependencies = result.dependencies.values
    require(
        dependencies["history"] == _history_hash(history),
        "Evaluator returned stale or unrelated history evidence.",
    )
    require(
        dependencies["horizon"]["until"] == until
        and dependencies["horizon"]["effective"] == until,
        "Evaluator changed the explicit finite horizon.",
    )
    if stable is not None:
        require(
            fingerprint(_stable_dependencies(result)) == fingerprint(stable),
            "Evaluator changed model, request, contract, domain, target or tool dependencies.",
        )
    return result


@dataclass(frozen=True)
class ExplorationReport(_Record):
    config: BooleanContactConfig
    results: tuple[CheckResult, ...]
    explorer_version: str = EXPLORATION_VERSION
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "biocompiler.boolean_exploration_report.v0.1"
    _decoders: ClassVar[dict] = {
        "config": BooleanContactConfig.from_dict,
        "results": lambda value: _decode_array(value, CheckResult),
    }
    _derived: ClassVar[tuple] = (
        "state_count",
        "possible_histories",
        "evaluated_histories",
        "complete",
        "all_passed",
        "outcome_counts",
        "coverage_totals",
        "shared_dependencies",
    )

    def __post_init__(self):
        require(
            isinstance(self.config, BooleanContactConfig), "Invalid exploration bounds."
        )
        require(
            isinstance(self.results, (tuple, list))
            and 0
            < len(self.results)
            <= min(self.config.possible_histories, self.config.max_histories),
            "Invalid evaluated history count.",
        )
        object.__setattr__(self, "results", tuple(self.results))
        require(
            self.explorer_version == EXPLORATION_VERSION
            and self.claim_scope == CLAIM_SCOPE,
            "Invalid exploration version or claim scope.",
        )
        stable = None
        requirements = None
        for index, result in enumerate(self.results):
            _validate_result(
                result, _history_at(self.config, index), self.config.until, stable
            )
            stable = _stable_dependencies(result)
            require(
                requirements is None or requirements == result.checked_requirement_ids,
                "Evaluator changed checked requirement inventory.",
            )
            requirements = result.checked_requirement_ids

    @property
    def state_count(self):
        return self.config.state_count

    @property
    def possible_histories(self):
        return self.config.possible_histories

    @property
    def evaluated_histories(self):
        return len(self.results)

    @property
    def complete(self):
        return self.evaluated_histories == self.possible_histories

    @property
    def all_passed(self):
        return self.complete and all(
            item.outcome is CheckOutcome.PASS for item in self.results
        )

    @property
    def outcome_counts(self):
        return MappingProxyType(
            {
                outcome.value: sum(item.outcome is outcome for item in self.results)
                for outcome in CheckOutcome
            }
        )

    @property
    def coverage_totals(self):
        counts = {}
        for result in self.results:
            for item in result.coverage:
                values = counts.setdefault(item.requirement_id, [0, 0, 0, 0])
                for index, key in enumerate(
                    (
                        "activation_deadlines_checked",
                        "inactive_deadlines_checked",
                        "incomplete_episode_count",
                        "cancelled_episode_count",
                    )
                ):
                    values[index] += getattr(item, key)
        return tuple(RequirementCoverage(key, *counts[key]) for key in sorted(counts))

    @property
    def shared_dependencies(self):
        return freeze_json(_stable_dependencies(self.results[0]))

    def to_dict(self):
        return super().to_dict() | {
            "state_count": self.state_count,
            "possible_histories": self.possible_histories,
            "evaluated_histories": self.evaluated_histories,
            "complete": self.complete,
            "all_passed": self.all_passed,
            "outcome_counts": dict(self.outcome_counts),
            "coverage_totals": [item.to_dict() for item in self.coverage_totals],
            "shared_dependencies": thaw_json(self.shared_dependencies),
        }


def explore_boolean_histories(
    config: BooleanContactConfig, evaluate
) -> ExplorationReport:
    """Evaluate the entire declared lattice or an explicitly capped prefix."""
    require(callable(evaluate), "Expected a history evaluator callback.")
    results = []
    stable = None
    for history in enumerate_boolean_histories(config):
        result = _validate_result(
            evaluate(history, until=config.until), history, config.until, stable
        )
        stable = _stable_dependencies(result)
        results.append(result)
    return ExplorationReport(config, tuple(results))


@dataclass(frozen=True)
class AdversarialConfig(_Record):
    bounds: BooleanContactConfig
    seed: int
    random_cases: int = 16
    schema_version: ClassVar[str] = "biocompiler.adversarial_history_config.v0.1"
    _decoders: ClassVar[dict] = {"bounds": BooleanContactConfig.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.bounds, BooleanContactConfig)
            and len(self.bounds.variable_times) >= 3,
            "Adversarial transition cases need at least three variable times.",
        )
        _integer(self.seed, 0, 2**64 - 1, "history seed")
        _integer(self.random_cases, 0, 1000, "random case count")


@dataclass(frozen=True)
class HistoryCase(_Record):
    id: str
    kind: str
    history: tuple[InputFrame, ...]
    until: int | float
    config_fingerprint: str
    intentionally_incomplete: bool = False
    schema_version: ClassVar[str] = "biocompiler.adversarial_history.v0.1"
    _decoders: ClassVar[dict] = {"history": _frames}

    def __post_init__(self):
        name(self.id, "History case ID")
        name(self.kind, "History case kind")
        object.__setattr__(self, "history", _history(self.history, self.until))
        require(
            isinstance(self.config_fingerprint, str)
            and len(self.config_fingerprint) == 64
            and all(char in "0123456789abcdef" for char in self.config_fingerprint),
            "Invalid generator configuration identity.",
        )
        require(
            type(self.intentionally_incomplete) is bool,
            "Incomplete-observation marker must be Boolean.",
        )


def generate_adversarial_histories(
    config: AdversarialConfig,
) -> tuple[HistoryCase, ...]:
    """Named transition cases plus SHA-256-counter seeded samples; no random proof."""
    require(
        isinstance(config, AdversarialConfig), "Expected adversarial configuration."
    )
    bounds = config.bounds
    count = len(bounds.variable_times)
    all_active = bounds.state_count - 1
    # State 1 per contact means present with every field false; state 0 is absent.
    radix = 1 + 2 ** len(bounds.observations)
    all_inactive = sum(radix**index for index in range(len(bounds.contact_ids)))
    patterns = [
        ("startup_active", [all_active] * count),
        (
            "rapid_oscillation",
            [all_active if index % 2 == 0 else all_inactive for index in range(count)],
        ),
        (
            "dropout_reappearance",
            [all_active if index != 1 else 0 for index in range(count)],
        ),
        ("absent_contacts", [0] * count),
    ]
    for index in range(config.random_cases):
        codes = [
            int.from_bytes(
                hashlib.sha256(
                    f"{EXPLORATION_VERSION}:{config.seed}:{index}:{step}".encode(
                        "ascii"
                    )
                ).digest(),
                "big",
            )
            % bounds.state_count
            for step in range(count)
        ]
        patterns.append((f"seeded_{index:04d}", codes))
    cases = []
    for label, codes in patterns:
        history = (
            tuple(
                _snapshot(bounds, time, code)
                for time, code in zip(bounds.variable_times, codes)
            )
            + bounds.fixed_suffix
        )
        cases.append(
            HistoryCase(
                label,
                "seeded" if label.startswith("seeded_") else label,
                history,
                bounds.until,
                config.fingerprint,
            )
        )
    first = _snapshot(bounds, 0, all_active)
    contacts = {key: dict(value) for key, value in first.contacts.items()}
    observation = bounds.observations[0]
    samples = contacts[bounds.contact_ids[0]]
    values = samples[observation.signal_id].to_dict()
    values[observation.field] = None
    samples[observation.signal_id] = SignalSample(**values)
    incomplete = (InputFrame(0, contacts=contacts), *cases[0].history[1:])
    cases.append(
        HistoryCase(
            "incomplete_observation",
            "diagnostic",
            incomplete,
            bounds.until,
            config.fingerprint,
            True,
        )
    )
    return tuple(cases)


@dataclass(frozen=True)
class FailureSignature(_Record):
    kind: str
    requirement_id: str | None
    code: str | None = None
    rule_id: str | None = None
    specification_id: str | None = None
    contact_id: str | None = None
    state: str | None = None
    node_id: str | None = None
    schema_version: ClassVar[str] = "biocompiler.failure_signature.v0.1"

    def __post_init__(self):
        require(
            self.kind in {"response", "diagnostic"}, "Invalid failure signature kind."
        )
        for field in dataclass_fields(self):
            value = getattr(self, field.name)
            if value is not None:
                name(value, field.name)
        if self.kind == "response":
            require(
                self.requirement_id is not None
                and self.rule_id is not None
                and self.specification_id is not None
                and self.state in {"active", "inactive"}
                and self.code is self.node_id is None,
                "Invalid response failure signature.",
            )
        else:
            require(
                self.code is not None
                and self.rule_id
                is self.specification_id
                is self.contact_id
                is self.state
                is None,
                "Invalid diagnostic failure signature.",
            )

    @classmethod
    def from_counterexample(cls, item: Counterexample):
        require(isinstance(item, Counterexample), "Expected a response counterexample.")
        return cls(
            "response",
            item.requirement_id,
            rule_id=item.rule_id,
            specification_id=item.specification_id,
            contact_id=item.contact_id,
            state=item.expected["state"],
        )

    @classmethod
    def from_diagnostic(cls, item: CheckDiagnostic):
        require(isinstance(item, CheckDiagnostic), "Expected a check diagnostic.")
        return cls(
            "diagnostic", item.requirement_id, code=item.code, node_id=item.node_id
        )

    def matches(self, result):
        if result.outcome is not CheckOutcome.FAIL:
            return False
        values = (
            (self.from_counterexample(item) for item in result.counterexamples)
            if self.kind == "response"
            else (self.from_diagnostic(item) for item in result.diagnostics)
        )
        return any(value == self for value in values)


@dataclass(frozen=True)
class ReductionResult(_Record):
    original_history: tuple[InputFrame, ...]
    history: tuple[InputFrame, ...]
    until: int | float
    signature: FailureSignature
    original_result: CheckResult
    result: CheckResult
    evaluations: int
    one_minimal: bool
    reducer_version: str = EXPLORATION_VERSION
    schema_version: ClassVar[str] = "biocompiler.history_reduction.v0.1"
    _decoders: ClassVar[dict] = {
        "original_history": _frames,
        "history": _frames,
        "signature": FailureSignature.from_dict,
        "original_result": CheckResult.from_dict,
        "result": CheckResult.from_dict,
    }

    def __post_init__(self):
        object.__setattr__(
            self, "original_history", _history(self.original_history, self.until)
        )
        object.__setattr__(self, "history", _history(self.history, self.until))
        require(
            isinstance(self.signature, FailureSignature),
            "Invalid selected failure signature.",
        )
        _integer(self.evaluations, 1, 100000, "reduction evaluation count")
        require(type(self.one_minimal) is bool, "Minimality marker must be Boolean.")
        require(
            self.reducer_version == EXPLORATION_VERSION,
            "Unsupported reduction policy version.",
        )
        _validate_result(self.original_result, self.original_history, self.until)
        _validate_result(
            self.result,
            self.history,
            self.until,
            _stable_dependencies(self.original_result),
        )
        require(
            self.original_result.checked_requirement_ids
            == self.result.checked_requirement_ids,
            "Reduction changed checked requirement inventory.",
        )
        require(
            self.signature.matches(self.original_result)
            and self.signature.matches(self.result),
            "Reduction changed its selected explicit failure.",
        )
        original = {frame.time: frame.to_dict() for frame in self.original_history}
        require(
            self.history[0].to_dict() == self.original_history[0].to_dict()
            and all(
                frame.time in original and frame.to_dict() == original[frame.time]
                for frame in self.history
            ),
            "Reduction may delete snapshots only; initial state and horizon stay fixed.",
        )


def reduce_counterexample(
    history, until, evaluate, signature: FailureSignature, *, max_evaluations=1000
) -> ReductionResult:
    """Delete snapshots to a deterministic 1-minimal selected failure, within budget.

    Initial state and explicit horizon never change. A FAIL with a different
    signature, UNKNOWN or UNSUPPORTED cannot replace the selected counterexample.
    Greedy deletion restarts after each success; 1-minimal is not globally minimal.
    """
    history = _history(history, until)
    require(
        callable(evaluate) and isinstance(signature, FailureSignature),
        "Reducer needs an evaluator and explicit failure selection.",
    )
    _integer(max_evaluations, 1, 100000, "reduction evaluation budget")
    initial = _validate_result(evaluate(history, until=until), history, until)
    require(
        signature.matches(initial),
        "Initial history does not exhibit the selected FAIL signature.",
    )
    stable = _stable_dependencies(initial)
    current, result, evaluations = history, initial, 1
    while True:
        removed = False
        for index in range(1, len(current)):
            if evaluations >= max_evaluations:
                return ReductionResult(
                    history,
                    current,
                    until,
                    signature,
                    initial,
                    result,
                    evaluations,
                    False,
                )
            trial = current[:index] + current[index + 1 :]
            checked = _validate_result(
                evaluate(trial, until=until), trial, until, stable
            )
            evaluations += 1
            require(
                checked.checked_requirement_ids == initial.checked_requirement_ids,
                "Reducer evaluator changed checked requirements.",
            )
            if signature.matches(checked):
                current, result, removed = trial, checked, True
                break
        if not removed:
            return ReductionResult(
                history, current, until, signature, initial, result, evaluations, True
            )
