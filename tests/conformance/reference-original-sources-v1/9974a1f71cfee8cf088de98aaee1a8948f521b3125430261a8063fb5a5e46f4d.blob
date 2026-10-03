"""Declared circuit observations and products, with no biological inference.

An observation's molecular identity, quantity, compartment, scope, timing and
encoding are all nominal authority. In particular, a supplied mimic dose cannot
be interpreted as intracellular miRNA activity. Units are preserved exactly;
this profile neither converts units nor invents thresholds or measurement maps.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import ClassVar

from biocompiler.artifacts.manifest import _Record
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_logic import LogicValue
from biocompiler.ir.serialization import parse_json, require


MAX_OBSERVATION_JSON_BYTES = 64_000
MAX_OBSERVATION_TEXT_BYTES = 512
MAX_OBSERVATION_ITEMS = 512
MAX_OBSERVATION_DEPTH = 12


class QuantityKind(StrEnum):
    MIRNA_ACTIVITY = "mirna_activity"
    RNA_ABUNDANCE = "rna_abundance"
    PROTEIN_ABUNDANCE = "protein_abundance"
    LIGAND_CONCENTRATION = "ligand_concentration"
    TRANSLATION_RATE = "translation_rate"
    FLUORESCENCE = "fluorescence"
    DOWNSTREAM_ACTIVITY = "downstream_activity"


class ObservationScope(StrEnum):
    CELL_ACCESSIBLE = "cell_accessible"
    EVALUATOR = "evaluator"
    EXTERNAL = "external"


class ProductKind(StrEnum):
    PROTEIN_EXPRESSION = "protein_expression"
    MATURE_PROTEIN_QUANTITY = "mature_protein_quantity"
    REPORTER_FLUORESCENCE = "reporter_fluorescence"
    BIOLOGICAL_ACTIVITY = "biological_activity"
    RNA_PRODUCT = "rna_product"


def _text(value, label):
    require(isinstance(value, str), f"{label} must be text.")
    require(
        len(value) <= MAX_OBSERVATION_TEXT_BYTES, f"{label} exceeds the text limit."
    )
    require(
        bool(value.strip()) and value == value.strip(),
        f"{label} must be nonempty text without surrounding whitespace.",
    )
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise SerializationError(f"{label} must be UTF-8 text.") from exc
    require(size <= MAX_OBSERVATION_TEXT_BYTES, f"{label} exceeds the text limit.")
    require(
        not any(ord(char) < 32 or ord(char) == 127 for char in value),
        f"Invalid control text in {label}.",
    )


def _number(value, label):
    require(type(value) in (float, int), f"{label} must be a finite number.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    require(finite, f"{label} must be a finite number.")


def _bounded_tree(value):
    from collections.abc import Mapping

    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= MAX_OBSERVATION_ITEMS, "Observation item limit exceeded.")
        require(depth <= MAX_OBSERVATION_DEPTH, "Observation nesting limit exceeded.")
        remaining = MAX_OBSERVATION_ITEMS - count - len(stack)
        if isinstance(item, Mapping):
            require(2 * len(item) <= remaining, "Observation item limit exceeded.")
            for key, child in item.items():
                require(isinstance(key, str), "Observation keys must be strings.")
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (list, tuple)):
            require(len(item) <= remaining, "Observation item limit exceeded.")
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            _text(item, "Observation text")
        elif type(item) in (int, float):
            _number(item, "Observation number")
        else:
            require(item is None or type(item) is bool, "Invalid observation value.")


class _ObservationRecord(_Record):
    @classmethod
    def from_dict(cls, data):
        _bounded_tree(data)
        return super().from_dict(data)

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Observation JSON must be text.")
        require(
            len(text) <= MAX_OBSERVATION_JSON_BYTES, "Observation byte limit exceeded."
        )
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as exc:
            raise SerializationError("Observation JSON must be UTF-8.") from exc
        require(size <= MAX_OBSERVATION_JSON_BYTES, "Observation byte limit exceeded.")
        return cls.from_dict(parse_json(text))

    def to_json(self, *, indent=2):
        require(
            indent is None or (type(indent) is int and 0 <= indent <= 8),
            "Observation JSON indentation must be None or an integer from 0 to 8.",
        )
        try:
            text = super().to_json(indent=indent)
            size = len(text.encode("utf-8"))
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise SerializationError(f"Invalid observation JSON: {exc}") from exc
        require(
            size + 1 <= MAX_OBSERVATION_JSON_BYTES,
            "Observation byte limit exceeded (including publication newline).",
        )
        return text

    def _check_resources(self):
        _bounded_tree(self.to_dict())
        self.to_json()


def _optional(record):
    return lambda value: None if value is None else record.from_dict(value)


@dataclass(frozen=True)
class ObservationEntity(_ObservationRecord):
    """An exact declared identity; use literal ``unknown`` for unreported fields.

    An unknown version or isoform stays unknown, never a wildcard matching a
    resolved version/isoform. Namespaces and accessions are not database lookups.
    """

    namespace: str
    accession: str
    version: str
    isoform: str

    schema_version: ClassVar[str] = "biocompiler.observation_entity.v0.1"

    def __post_init__(self):
        for label in ("namespace", "accession", "version", "isoform"):
            _text(getattr(self, label), f"Entity {label}")
        self._check_resources()


@dataclass(frozen=True)
class NumericInterval(_ObservationRecord):
    """A finite nonempty range with explicitly controlled boundary inclusion."""

    lower: float | int
    upper: float | int
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    schema_version: ClassVar[str] = "biocompiler.observation_interval.v0.1"

    def __post_init__(self):
        _number(self.lower, "Interval lower bound")
        _number(self.upper, "Interval upper bound")
        require(
            type(self.lower_inclusive) is bool and type(self.upper_inclusive) is bool,
            "Interval inclusivity must be Boolean.",
        )
        require(self.lower <= self.upper, "Interval bounds are reversed.")
        require(
            self.lower < self.upper or (self.lower_inclusive and self.upper_inclusive),
            "An interval must contain at least one value.",
        )
        self._check_resources()

    def contains(self, value):
        _number(value, "Observed value")
        return (
            value > self.lower or (value == self.lower and self.lower_inclusive)
        ) and (value < self.upper or (value == self.upper and self.upper_inclusive))

    def overlaps(self, other):
        require(isinstance(other, NumericInterval), "Expected a numeric interval.")
        lower, upper = max(self.lower, other.lower), min(self.upper, other.upper)
        return lower < upper or (
            lower == upper and self.contains(lower) and other.contains(lower)
        )

    def encloses(self, other):
        require(isinstance(other, NumericInterval), "Expected a numeric interval.")
        low_ok = self.lower < other.lower or (
            self.lower == other.lower
            and (self.lower_inclusive or not other.lower_inclusive)
        )
        high_ok = self.upper > other.upper or (
            self.upper == other.upper
            and (self.upper_inclusive or not other.upper_inclusive)
        )
        return low_ok and high_ok


@dataclass(frozen=True)
class ObservationWindow(_ObservationRecord):
    """Declared observation timing, relative to an explicit named reference.

    Use reference/unit/aggregation ``unknown`` and absent bounds when timing was
    not reported. Unknown timing cannot match a known timing specification.
    """

    reference: str
    start: float | int | None
    end: float | int | None
    unit: str
    aggregation: str

    schema_version: ClassVar[str] = "biocompiler.observation_window.v0.1"

    def __post_init__(self):
        _text(self.reference, "Time reference")
        require(
            type(self.aggregation) is str
            and self.aggregation
            in {"instant", "mean", "integral", "any", "all", "unknown"},
            "Unsupported observation aggregation.",
        )
        if self.aggregation == "unknown":
            require(
                self.start is None
                and self.end is None
                and self.unit == "unknown"
                and self.reference == "unknown",
                "Unreported timing must remain wholly unknown.",
            )
        else:
            require(
                self.reference != "unknown", "Known timing needs a named reference."
            )
            require(
                type(self.unit) is str and self.unit in {"s", "ms", "min", "h", "d"},
                "Unsupported time unit.",
            )
            _number(self.start, "Observation start")
            _number(self.end, "Observation end")
            require(self.start <= self.end, "Observation timing is reversed.")
            if self.aggregation == "instant":
                require(
                    self.start == self.end, "Instant observations require one time."
                )
            else:
                require(
                    self.start < self.end,
                    "Aggregated observations require a time window.",
                )
        self._check_resources()


@dataclass(frozen=True)
class ObservationEncoding(_ObservationRecord):
    """Explicit HIGH/LOW regions. Gaps, missing values and ambiguity stay UNKNOWN.

    Numeric units are exact nominal symbols, not dimensional conversions.
    Qualitative reports retain their supplied labels without invented cutoffs.
    """

    mode: str
    unit: str
    low: NumericInterval | None = None
    high: NumericInterval | None = None
    allowed_range: NumericInterval | None = None

    schema_version: ClassVar[str] = "biocompiler.observation_encoding.v0.1"
    _decoders: ClassVar[dict] = {
        "low": _optional(NumericInterval),
        "high": _optional(NumericInterval),
        "allowed_range": _optional(NumericInterval),
    }

    def __post_init__(self):
        require(
            type(self.mode) is str and self.mode in {"qualitative", "numeric"},
            "Unsupported observation encoding.",
        )
        _text(self.unit, "Observation unit")
        if self.mode == "qualitative":
            require(
                self.unit == "qualitative"
                and self.low is None
                and self.high is None
                and self.allowed_range is None,
                "Qualitative encoding cannot carry numeric thresholds or units.",
            )
        else:
            require(
                self.unit not in {"qualitative", "unknown"},
                "Numeric encoding requires explicit units.",
            )
            require(
                isinstance(self.low, NumericInterval)
                and isinstance(self.high, NumericInterval),
                "Numeric encoding requires explicit LOW and HIGH intervals.",
            )
            require(not self.low.overlaps(self.high), "LOW and HIGH intervals overlap.")
            require(
                self.low.upper <= self.high.lower,
                "LOW interval must precede the HIGH interval.",
            )
            if self.allowed_range is not None:
                require(
                    isinstance(self.allowed_range, NumericInterval),
                    "Invalid allowed range.",
                )
                require(
                    self.allowed_range.encloses(self.low)
                    and self.allowed_range.encloses(self.high),
                    "Allowed range must contain both logical regions.",
                )
        self._check_resources()


@dataclass(frozen=True)
class CircuitObservation(_ObservationRecord):
    """Full nominal input/output observation declaration; no evidence claim."""

    id: str
    entity: ObservationEntity
    quantity: QuantityKind
    compartment: str
    scope: ObservationScope
    window: ObservationWindow
    encoding: ObservationEncoding

    schema_version: ClassVar[str] = "biocompiler.circuit_observation.v0.1"
    _decoders: ClassVar[dict] = {
        "entity": ObservationEntity.from_dict,
        "quantity": QuantityKind,
        "scope": ObservationScope,
        "window": ObservationWindow.from_dict,
        "encoding": ObservationEncoding.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Observation id")
        _text(self.compartment, "Observation compartment")
        require(
            isinstance(self.entity, ObservationEntity), "Invalid observation entity."
        )
        require(
            isinstance(self.quantity, QuantityKind),
            "Observation quantity must be typed.",
        )
        require(
            isinstance(self.scope, ObservationScope), "Observation scope must be typed."
        )
        require(
            isinstance(self.window, ObservationWindow), "Invalid observation timing."
        )
        require(
            isinstance(self.encoding, ObservationEncoding),
            "Invalid observation encoding.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ObservationSample(_ObservationRecord):
    """Supplied software value retaining the complete observation declaration."""

    observation: CircuitObservation
    value: float | int | str | None
    status: str = "observed"

    schema_version: ClassVar[str] = "biocompiler.observation_sample.v0.1"
    _decoders: ClassVar[dict] = {"observation": CircuitObservation.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.observation, CircuitObservation),
            "Invalid sample observation.",
        )
        require(
            type(self.status) is str
            and self.status in {"observed", "missing", "ambiguous"},
            "Invalid sample status.",
        )
        if self.status != "observed":
            require(
                self.value is None,
                "Missing or ambiguous samples must have no resolved value.",
            )
        elif self.observation.encoding.mode == "qualitative":
            require(
                type(self.value) is str and self.value in {"HIGH", "LOW", "UNKNOWN"},
                "Qualitative samples require HIGH, LOW or UNKNOWN.",
            )
        elif self.value != "UNKNOWN":
            _number(self.value, "Numeric observation sample")
        self._check_resources()


def classify_observation(
    observation: CircuitObservation, sample: ObservationSample
) -> LogicValue:
    """Decode a supplied sample against independent complete nominal authority.

    This performs declared software encoding only. It establishes no biological
    measurement, intracellular sensing mechanism or empirical behavior.
    """
    require(
        isinstance(observation, CircuitObservation), "Expected a circuit observation."
    )
    require(isinstance(sample, ObservationSample), "Expected an observation sample.")
    # Reparse both declarations so forged/deserialized objects are not authority.
    expected = CircuitObservation.from_dict(observation.to_dict())
    supplied = ObservationSample.from_dict(sample.to_dict())
    require(
        supplied.observation.fingerprint == expected.fingerprint
        and supplied.observation.to_dict() == expected.to_dict(),
        "Sample observation identity does not match expected authority.",
    )
    if supplied.status != "observed" or supplied.value == "UNKNOWN":
        return LogicValue.UNKNOWN
    encoding = expected.encoding
    if encoding.mode == "qualitative":
        return LogicValue.TRUE if supplied.value == "HIGH" else LogicValue.FALSE
    if encoding.allowed_range is not None and not encoding.allowed_range.contains(
        supplied.value
    ):
        return LogicValue.UNKNOWN
    if encoding.low.contains(supplied.value):
        return LogicValue.FALSE
    if encoding.high.contains(supplied.value):
        return LogicValue.TRUE
    return LogicValue.UNKNOWN


_PRODUCT_QUANTITIES = {
    ProductKind.PROTEIN_EXPRESSION: QuantityKind.TRANSLATION_RATE,
    ProductKind.MATURE_PROTEIN_QUANTITY: QuantityKind.PROTEIN_ABUNDANCE,
    ProductKind.REPORTER_FLUORESCENCE: QuantityKind.FLUORESCENCE,
    ProductKind.BIOLOGICAL_ACTIVITY: QuantityKind.DOWNSTREAM_ACTIVITY,
    ProductKind.RNA_PRODUCT: QuantityKind.RNA_ABUNDANCE,
}


@dataclass(frozen=True)
class CircuitProduct(_ObservationRecord):
    """A distinct declared output requirement, without implied biological effect."""

    id: str
    kind: ProductKind
    observation: CircuitObservation

    schema_version: ClassVar[str] = "biocompiler.circuit_product.v0.1"
    _decoders: ClassVar[dict] = {
        "kind": ProductKind,
        "observation": CircuitObservation.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Product requirement id")
        require(isinstance(self.kind, ProductKind), "Product kind must be typed.")
        require(
            isinstance(self.observation, CircuitObservation),
            "Invalid product observation.",
        )
        require(
            self.observation.quantity == _PRODUCT_QUANTITIES[self.kind],
            "Product requirement and observed quantity are different semantics.",
        )
        self._check_resources()
