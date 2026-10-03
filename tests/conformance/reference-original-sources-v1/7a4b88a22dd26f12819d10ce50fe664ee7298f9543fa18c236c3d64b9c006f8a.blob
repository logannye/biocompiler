"""Explicit measurement and lifecycle semantics for conditional secretion.

These are requested observations, not a sensor, secretion mechanism, biological
prediction or demonstration that the source therapeutic goal will be achieved.
"""

from dataclasses import dataclass, fields as record_fields
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import JsonArtifact, fields, name, require
from biocompiler.semantics.human_target import TargetClaim
from biocompiler.semantics.realization import (
    Observable,
    ResponseRequirement,
    _duration,
    _interval,
)
from biocompiler.semantics.types import (
    DURATION,
    PRODUCTION_RATE,
    Interval,
    ScalarLiteral,
    TypeSpec,
    decode_binding,
)


def _scalar(data):
    require(isinstance(data, dict), "Expected a typed scalar object.")
    dtype = TypeSpec.from_dict(data.get("type"))
    require(dtype.kind == "scalar", "Expected a scalar measurement.")
    return decode_binding(data, dtype)


def _range(data):
    require(isinstance(data, dict), "Expected a typed interval object.")
    dtype = TypeSpec.from_dict(data.get("type"))
    require(dtype.kind == "interval", "Expected a measurement interval.")
    return decode_binding(data, dtype)


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _fixed: ClassVar[dict] = {}

    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "schema_version": self.schema_version,
            **self._fixed,
            **{
                field.name: encode(getattr(self, field.name))
                for field in record_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {field.name for field in record_fields(cls)}
            | {"schema_version"}
            | set(cls._fixed),
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported human behavior schema.",
        )
        for key, value in cls._fixed.items():
            require(
                type(data[key]) is type(value) and data[key] == value,
                f"Unsupported {key}.",
            )
        try:
            return cls(
                **{
                    field.name: cls._decoders.get(field.name, lambda value: value)(
                        data[field.name]
                    )
                    for field in record_fields(cls)
                }
            )
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

    def _utf8(self):
        try:
            self.to_json(indent=None).encode("utf-8")
        except UnicodeError as error:
            raise SerializationError(
                "Human behavior strings must be valid UTF-8."
            ) from error


@dataclass(frozen=True)
class MeasurementSpec(_Record):
    """A physical readout definition, with access and interpretation kept explicit."""

    observable: Observable
    meaning: str
    access: str
    method: str
    support: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.measurement_spec.v0.1"
    _decoders: ClassVar[dict] = {
        "observable": Observable.from_dict,
        "support": TargetClaim.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.observable, Observable)
            and self.observable.dtype.kind == "scalar"
            and self.observable.scope == "cell",
            "This profile requires a scalar single-cell observable.",
        )
        require(
            isinstance(self.access, str)
            and self.access in {"cell", "external_evaluator"},
            "Measurement access must be cell or external_evaluator.",
        )
        name(self.meaning, "Measurement meaning")
        name(self.method, "Measurement interpretation/method")
        require(
            isinstance(self.support, TargetClaim),
            "Measurement support requires an explicit TargetClaim.",
        )
        self._utf8()


@dataclass(frozen=True)
class PredicateRefinement(_Record):
    """An explicit threshold for one source qualitative predicate; no hysteresis."""

    predicate_id: str
    operator: str
    threshold: ScalarLiteral
    support: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.predicate_refinement.v0.1"
    _decoders: ClassVar[dict] = {"threshold": _scalar, "support": TargetClaim.from_dict}

    def __post_init__(self):
        name(self.predicate_id, "Source predicate id")
        require(
            isinstance(self.operator, str) and self.operator in {">", ">=", "<", "<="},
            "Unsupported threshold operator.",
        )
        require(
            isinstance(self.threshold, ScalarLiteral),
            "Threshold requires an explicit typed scalar.",
        )
        object.__setattr__(self, "threshold", _scalar(self.threshold.to_dict()))
        require(
            isinstance(self.support, TargetClaim),
            "Threshold support requires a TargetClaim.",
        )
        self._utf8()

    def accepts(self, value):
        require(
            isinstance(value, ScalarLiteral), "Predicate input requires a typed scalar."
        )
        actual = decode_binding(value.to_dict(), self.threshold.dtype).canonical_value
        boundary = self.threshold.canonical_value
        return {
            ">": actual > boundary,
            ">=": actual >= boundary,
            "<": actual < boundary,
            "<=": actual <= boundary,
        }[self.operator]


@dataclass(frozen=True)
class ConditionalSecretionContract(_Record):
    """One reversible, level-triggered, single-cell secretion requirement.

    Output units are amount/time per selected cell. Input/output measurements
    are distinct endpoints. A finite horizon is required; no prehistory, memory,
    population averaging or post-horizon persistence is inferred.
    """

    id: str
    goal_id: str
    product: str
    input_signal_id: str
    input_measurement: MeasurementSpec
    input_range: Interval
    predicate: PredicateRefinement
    output_measurement: MeasurementSpec
    response: ResponseRequirement
    initial_range: Interval
    horizon: ScalarLiteral
    goal_refinement: TargetClaim
    response_support: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.conditional_secretion_contract.v0.1"
    _fixed: ClassVar[dict] = {
        "profile": "human_conditional_secretion.v0.1",
        "initialization": "inactive_input_and_output_at_zero_no_prehistory",
        "persistence": "active_range_after_deadline_while_input_qualifies",
        "termination": "inactive_range_after_recovery_deadline",
        "retrigger": "latest_input_transition_replaces_pending_deadline",
    }
    _decoders: ClassVar[dict] = {
        "input_measurement": MeasurementSpec.from_dict,
        "input_range": _range,
        "predicate": PredicateRefinement.from_dict,
        "output_measurement": MeasurementSpec.from_dict,
        "response": ResponseRequirement.from_dict,
        "initial_range": _range,
        "horizon": lambda data: decode_binding(data, DURATION),
        "goal_refinement": TargetClaim.from_dict,
        "response_support": TargetClaim.from_dict,
    }

    def __post_init__(self):
        for key in ("id", "goal_id", "product", "input_signal_id"):
            name(getattr(self, key), key)
        require(
            isinstance(self.input_measurement, MeasurementSpec)
            and self.input_measurement.access == "cell",
            "Runtime input must be available to the cell; evaluator-only measurements cannot drive a guard.",
        )
        require(
            isinstance(self.output_measurement, MeasurementSpec)
            and self.output_measurement.access == "external_evaluator",
            "Secretion output requires a separate evaluator measurement.",
        )
        require(
            isinstance(self.predicate, PredicateRefinement),
            "Expected PredicateRefinement.",
        )
        require(
            isinstance(self.response, ResponseRequirement),
            "Expected ResponseRequirement.",
        )
        require(
            isinstance(self.goal_refinement, TargetClaim),
            "Goal refinement requires an explicit justification and limitations.",
        )
        require(
            isinstance(self.response_support, TargetClaim),
            "Response bounds and lifecycle require explicit support and limitations.",
        )
        incoming, outgoing = (
            self.input_measurement.observable,
            self.output_measurement.observable,
        )
        require(
            incoming.id != outgoing.id and incoming.role == outgoing.role,
            "Input/output endpoints must be distinct and belong to one role.",
        )
        require(
            outgoing.dtype == PRODUCTION_RATE,
            "Output must measure secretion amount/time per selected cell.",
        )
        require(
            self.response.observable == outgoing,
            "Response must bind the exact output measurement endpoint.",
        )
        require(
            self.predicate.threshold.dtype == incoming.dtype,
            "Threshold units/type must match the input measurement.",
        )
        bounds = _interval(self.input_range, incoming.dtype, "input domain")
        lower, upper, threshold = (
            bounds.lower.canonical_value,
            bounds.upper.canonical_value,
            self.predicate.threshold.canonical_value,
        )
        require(
            lower <= threshold <= upper,
            "Threshold must lie inside the declared input domain.",
        )
        require(
            self.predicate.accepts(bounds.lower)
            != self.predicate.accepts(bounds.upper),
            "Input domain must exercise both active and inactive predicate values.",
        )
        object.__setattr__(self, "input_range", bounds)
        initial = _interval(self.initial_range, outgoing.dtype, "initial output range")
        inactive = self.response.inactive_range
        require(
            0 <= initial.lower.canonical_value <= initial.upper.canonical_value
            and inactive.lower.canonical_value <= initial.lower.canonical_value
            and initial.upper.canonical_value <= inactive.upper.canonical_value,
            "Initial output range must be a nonnegative subset of the inactive range.",
        )
        require(
            0 <= inactive.lower.canonical_value
            and inactive.upper.canonical_value
            < self.response.active_range.lower.canonical_value,
            "Secretion active rates must exceed nonnegative inactive rates.",
        )
        object.__setattr__(self, "initial_range", initial)
        horizon = _duration(self.horizon, "horizon", positive=True)
        require(
            horizon.canonical_value
            > self.response.max_activation_delay.canonical_value
            + self.response.max_deactivation_delay.canonical_value,
            "Horizon must allow active and recovered intervals.",
        )
        object.__setattr__(self, "horizon", horizon)
        self._utf8()

    @property
    def claims(self):
        return (
            ("input_measurement", self.input_measurement.support),
            ("predicate", self.predicate.support),
            ("output_measurement", self.output_measurement.support),
            ("goal_refinement", self.goal_refinement),
            ("response_support", self.response_support),
        )

    @property
    def unresolved_evidence(self):
        return tuple(path for path, _ in self.claims)


@dataclass(frozen=True)
class SecretionSample(_Record):
    """Complete right-continuous input/output values at one canonical time.

    Samples assert piecewise-constant values through the next timestamp. Sparse
    laboratory samples do not establish that interpolation; no inference is made.
    """

    time: ScalarLiteral
    input_value: ScalarLiteral
    output_value: ScalarLiteral
    schema_version: ClassVar[str] = "biocompiler.secretion_sample.v0.1"
    _decoders: ClassVar[dict] = {
        "time": lambda data: decode_binding(data, DURATION),
        "input_value": _scalar,
        "output_value": _scalar,
    }

    def __post_init__(self):
        object.__setattr__(self, "time", _duration(self.time, "sample time"))
        for key in ("input_value", "output_value"):
            value = getattr(self, key)
            require(
                isinstance(value, ScalarLiteral),
                "Measurements require typed scalar values.",
            )
            object.__setattr__(self, key, _scalar(value.to_dict()))
        self._utf8()
