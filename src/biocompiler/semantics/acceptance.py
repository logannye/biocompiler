"""Required and prohibited observations; no actuator or biological guarantee."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.serialization import name, require
from biocompiler.semantics.human_behavior import (
    MeasurementSpec,
    _Record,
    _range,
    _scalar,
)
from biocompiler.semantics.human_target import TargetClaim
from biocompiler.semantics.realization import _duration, _interval
from biocompiler.semantics.types import (
    DURATION,
    PRODUCTION_RATE,
    Interval,
    ScalarLiteral,
    decode_binding,
)


@dataclass(frozen=True)
class InputAvailabilitySpec(_Record):
    id: str
    observation_method: str
    response_delay: ScalarLiteral
    observability: TargetClaim
    controllability: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.input_availability_spec.v0.1"
    _fixed: ClassVar[dict] = {
        "loss_requirement": "background_after_deadline_while_cell_access_unavailable",
        "reacquisition": "restart_predicate_timing_without_inferred_prehistory",
        "implementation": "unestablished",
    }
    _decoders: ClassVar[dict] = {
        "response_delay": lambda data: decode_binding(data, DURATION),
        "observability": TargetClaim.from_dict,
        "controllability": TargetClaim.from_dict,
    }

    def __post_init__(self):
        name(self.id, "Input availability id")
        name(self.observation_method, "Availability observation method")
        object.__setattr__(
            self,
            "response_delay",
            _duration(self.response_delay, "loss response delay"),
        )
        for key in ("observability", "controllability"):
            require(
                isinstance(getattr(self, key), TargetClaim),
                f"Explicit {key} claim required.",
            )
        self._utf8()


@dataclass(frozen=True)
class ExternalShutdownSpec(_Record):
    id: str
    request_definition: str
    observation_method: str
    response_delay: ScalarLiteral
    observability: TargetClaim
    controllability: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.external_shutdown_spec.v0.1"
    _fixed: ClassVar[dict] = {
        "request_access": "external_evaluator",
        "persistence": "latched_for_remaining_horizon",
        "requirement": "background_after_deadline",
        "overrides_source_guard": False,
        "actuator_support": "unimplemented",
    }
    _decoders: ClassVar[dict] = InputAvailabilitySpec._decoders

    def __post_init__(self):
        for key in ("id", "request_definition", "observation_method"):
            name(getattr(self, key), key)
        object.__setattr__(
            self, "response_delay", _duration(self.response_delay, "shutdown delay")
        )
        for key in ("observability", "controllability"):
            require(
                isinstance(getattr(self, key), TargetClaim),
                f"Explicit {key} claim required.",
            )
        self._utf8()


@dataclass(frozen=True)
class HumanAcceptanceContract(_Record):
    """Conjoin source-linked secretion requirements with explicit prohibitions."""

    id: str
    behavior_fingerprint: str
    healthy_measurement: MeasurementSpec
    context_domain: Interval
    healthy_range: Interval
    background_ceiling: ScalarLiteral
    peak_ceiling: ScalarLiteral
    max_response_duration: ScalarLiteral
    bounds_support: TargetClaim
    input_availability: InputAvailabilitySpec
    shutdown: ExternalShutdownSpec
    schema_version: ClassVar[str] = "biocompiler.human_acceptance_contract.v0.1"
    _fixed: ClassVar[dict] = {
        "combination": "conjunction_no_priority_override",
        "healthy_inactivity": "immediate_background_bound",
        "peak_scope": "all_observed_times_including_transition_grace",
        "response_duration": "continuous_bout_strictly_above_background_ceiling",
        "scope": "single_recipient_cell_finite_horizon",
    }
    _decoders: ClassVar[dict] = {
        "healthy_measurement": MeasurementSpec.from_dict,
        "context_domain": _range,
        "healthy_range": _range,
        "background_ceiling": lambda data: decode_binding(data, PRODUCTION_RATE),
        "peak_ceiling": lambda data: decode_binding(data, PRODUCTION_RATE),
        "max_response_duration": lambda data: decode_binding(data, DURATION),
        "bounds_support": TargetClaim.from_dict,
        "input_availability": InputAvailabilitySpec.from_dict,
        "shutdown": ExternalShutdownSpec.from_dict,
    }

    def __post_init__(self):
        name(self.id, "Acceptance id")
        require(
            isinstance(self.behavior_fingerprint, str)
            and len(self.behavior_fingerprint) == 64
            and set(self.behavior_fingerprint) <= set("0123456789abcdef"),
            "Invalid behavior fingerprint.",
        )
        require(
            isinstance(self.healthy_measurement, MeasurementSpec)
            and self.healthy_measurement.access == "external_evaluator",
            "Healthy context requires an evaluator measurement, not an invented cellular guard.",
        )
        dtype = self.healthy_measurement.observable.dtype
        domain = _interval(self.context_domain, dtype, "context domain")
        healthy = _interval(self.healthy_range, dtype, "healthy context range")
        require(
            domain.lower.canonical_value
            <= healthy.lower.canonical_value
            <= healthy.upper.canonical_value
            <= domain.upper.canonical_value,
            "Healthy range must be inside the declared context domain.",
        )
        require(
            (domain.lower.canonical_value, domain.upper.canonical_value)
            != (healthy.lower.canonical_value, healthy.upper.canonical_value),
            "Context domain must also allow a non-healthy observation.",
        )
        object.__setattr__(self, "context_domain", domain)
        object.__setattr__(self, "healthy_range", healthy)
        for key in ("background_ceiling", "peak_ceiling"):
            value = getattr(self, key)
            require(isinstance(value, ScalarLiteral), f"Typed {key} required.")
            object.__setattr__(
                self, key, decode_binding(value.to_dict(), PRODUCTION_RATE)
            )
        require(
            0
            <= self.background_ceiling.canonical_value
            < self.peak_ceiling.canonical_value,
            "Peak must exceed a nonnegative background ceiling.",
        )
        object.__setattr__(
            self,
            "max_response_duration",
            _duration(
                self.max_response_duration, "maximum response duration", positive=True
            ),
        )
        require(
            isinstance(self.bounds_support, TargetClaim),
            "Explicit bounds support required.",
        )
        require(
            isinstance(self.input_availability, InputAvailabilitySpec),
            "Explicit input availability specification required.",
        )
        require(
            isinstance(self.shutdown, ExternalShutdownSpec),
            "Explicit shutdown specification required.",
        )
        self._utf8()

    @property
    def claims(self):
        return (
            ("healthy_measurement", self.healthy_measurement.support),
            ("bounds_support", self.bounds_support),
            ("input_availability.observability", self.input_availability.observability),
            (
                "input_availability.controllability",
                self.input_availability.controllability,
            ),
            ("shutdown.observability", self.shutdown.observability),
            ("shutdown.controllability", self.shutdown.controllability),
        )

    @property
    def unresolved_evidence(self):
        return tuple(path for path, _ in self.claims)


@dataclass(frozen=True)
class AcceptanceSample(_Record):
    """Assert right-continuous observations; missing measurements stay unknown."""

    time: ScalarLiteral
    input_status: str
    input_value: ScalarLiteral | None
    output_value: ScalarLiteral | None
    context_value: ScalarLiteral | None
    control_status: str
    schema_version: ClassVar[str] = "biocompiler.acceptance_sample.v0.1"
    _decoders: ClassVar[dict] = {
        "time": lambda data: decode_binding(data, DURATION),
        **{
            key: lambda data: None if data is None else _scalar(data)
            for key in ("input_value", "output_value", "context_value")
        },
    }

    def __post_init__(self):
        object.__setattr__(self, "time", _duration(self.time, "sample time"))
        require(
            isinstance(self.input_status, str)
            and self.input_status in {"available", "cell_unavailable", "unobserved"},
            "Invalid input availability status.",
        )
        require(
            isinstance(self.control_status, str)
            and self.control_status in {"clear", "shutdown", "unobserved"},
            "Invalid external control status.",
        )
        require(
            (self.input_status == "available") == (self.input_value is not None),
            "An input value is required exactly when cell access is available.",
        )
        for key in ("input_value", "output_value", "context_value"):
            value = getattr(self, key)
            require(
                value is None or isinstance(value, ScalarLiteral),
                "Measurements require typed scalars or explicit null.",
            )
            if value is not None:
                object.__setattr__(self, key, _scalar(value.to_dict()))
        self._utf8()
