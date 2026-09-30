"""Bounded, purely Boolean circuit descriptions with nominal input bindings.

The table, rather than a Python expression tree, is authoritative. Inputs are
sorted by ASCII identifier; the first input is the most-significant row bit.
Thus a two-input table has rows 00, 01, 10, 11. Construction accepts a table in
the supplied input order and permutes it into that canonical order. Even unused
inputs remain bound: simplification never discards observation obligations.

This module describes digital requirements, not molecular implementations or
biological evidence. Unknown observations use all compatible table rows, so a
result is definite only when every compatible completion agrees.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    parse_json,
    require,
)


LOGIC_PROFILE_VERSION = "biocompiler.circuit_logic.v0.1"
MAX_BOOLEAN_INPUTS = 8
MAX_BOOLEAN_ROWS = 1 << MAX_BOOLEAN_INPUTS
MAX_BOOLEAN_OPERANDS = 64
MAX_BOOLEAN_JSON_BYTES = 16_384
MAX_BOOLEAN_ITEMS = 2_048
MAX_BOOLEAN_DEPTH = 8
MAX_BOOLEAN_TEXT_BYTES = 256
MAX_SIGNAL_ID_LENGTH = 64
PUBLICATION_NEWLINE_BYTES = 1
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z", flags=re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", flags=re.ASCII)


class LogicValue(StrEnum):
    """A classified Boolean observation; UNKNOWN is never Python false."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    def __bool__(self):
        raise TypeError("LogicValue cannot control Python flow; compare it explicitly.")


def _bounded_document(value):
    """Reject oversized imported trees before decoding or recursive encoding."""
    stack = [(value, 0)]
    count = 0
    text_bytes = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= MAX_BOOLEAN_ITEMS, "Boolean item limit exceeded.")
        require(depth <= MAX_BOOLEAN_DEPTH, "Boolean nesting limit exceeded.")
        remaining = MAX_BOOLEAN_ITEMS - count - len(stack)
        if isinstance(item, Mapping):
            require(2 * len(item) <= remaining, "Boolean item limit exceeded.")
            for key, child in item.items():
                require(isinstance(key, str), "Boolean JSON keys must be strings.")
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (tuple, list)):
            require(len(item) <= remaining, "Boolean item limit exceeded.")
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            require(len(item) <= MAX_BOOLEAN_TEXT_BYTES, "Boolean text limit exceeded.")
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise SerializationError("Boolean text must be UTF-8.") from exc
            require(size <= MAX_BOOLEAN_TEXT_BYTES, "Boolean text limit exceeded.")
            text_bytes += size
            require(
                text_bytes <= MAX_BOOLEAN_JSON_BYTES, "Boolean byte limit exceeded."
            )
        else:
            require(
                item is None or type(item) in (bool, int, float),
                "Boolean imports require JSON values.",
            )


class _BooleanRecord(JsonArtifact):
    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Boolean JSON must be text.")
        require(len(text) <= MAX_BOOLEAN_JSON_BYTES, "Boolean byte limit exceeded.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as exc:
            raise SerializationError("Boolean JSON must be UTF-8.") from exc
        require(size <= MAX_BOOLEAN_JSON_BYTES, "Boolean byte limit exceeded.")
        return cls.from_dict(parse_json(text))

    def to_json(self, *, indent=2):
        require(
            indent is None or (type(indent) is int and 0 <= indent <= 8),
            "Boolean JSON indentation must be None or an integer from 0 to 8.",
        )
        data = self.to_dict()
        _bounded_document(data)
        text = json.dumps(
            data, sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False
        )
        require(
            len(text.encode("utf-8")) + PUBLICATION_NEWLINE_BYTES
            <= MAX_BOOLEAN_JSON_BYTES,
            "Boolean byte limit exceeded (including publication newline).",
        )
        return text

    def _check_resources(self):
        self.to_json()


class _BooleanOperators:
    def __bool__(self):
        raise TypeError(
            "Circuit logic cannot control Python flow; use ~, &, |, ^ or evaluate()."
        )

    def __invert__(self):
        return _combine(lambda values: not values[0], (self,))

    def __and__(self, other):
        return _combine(lambda values: values[0] and values[1], (self, other))

    def __rand__(self, other):
        return _combine(lambda values: values[0] and values[1], (other, self))

    def __or__(self, other):
        return _combine(lambda values: values[0] or values[1], (self, other))

    def __ror__(self, other):
        return _combine(lambda values: values[0] or values[1], (other, self))

    def __xor__(self, other):
        return _combine(lambda values: values[0] != values[1], (self, other))

    def __rxor__(self, other):
        return _combine(lambda values: values[0] != values[1], (other, self))


@dataclass(frozen=True)
class CircuitSignal(_BooleanOperators, _BooleanRecord):
    """Stable signal name bound to one complete observation's fingerprint."""

    id: str
    observation_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.circuit_signal.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.id, str)
            and 0 < len(self.id) <= MAX_SIGNAL_ID_LENGTH
            and _ID.fullmatch(self.id) is not None,
            "Signal ID must be an ASCII identifier of at most 64 characters.",
        )
        require(
            isinstance(self.observation_fingerprint, str)
            and len(self.observation_fingerprint) == 64
            and _HASH.fullmatch(self.observation_fingerprint) is not None,
            "Signal observation fingerprint must be lowercase SHA-256.",
        )
        self._check_resources()

    def expression(self) -> BooleanSpec:
        return BooleanSpec.projection(self)

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "observation_fingerprint": self.observation_fingerprint,
        }

    @classmethod
    def from_dict(cls, data):
        _bounded_document(data)
        fields(data, {"schema_version", "id", "observation_fingerprint"}, "signal")
        require(
            data["schema_version"] == cls.schema_version, "Unsupported signal schema."
        )
        return cls(data["id"], data["observation_fingerprint"])


def _checked_inputs(inputs):
    require(isinstance(inputs, (tuple, list)), "Boolean inputs must be an array.")
    require(len(inputs) <= MAX_BOOLEAN_INPUTS, "Boolean input limit exceeded.")
    require(
        all(isinstance(item, CircuitSignal) for item in inputs),
        "Boolean inputs require CircuitSignal records.",
    )
    result = tuple(inputs)
    require(
        len({signal.id for signal in result}) == len(result),
        "Boolean input IDs must be unique, including identical bindings.",
    )
    return result


def _row_in_order(row, size, positions):
    """Project one MSB-first row onto a different ordered subset of inputs."""
    projected = 0
    for position in positions:
        projected = (projected << 1) | ((row >> (size - 1 - position)) & 1)
    return projected


@dataclass(frozen=True)
class BooleanSpec(_BooleanOperators, _BooleanRecord):
    """A total truth table with explicit, immutable observation obligations."""

    inputs: tuple[CircuitSignal, ...]
    outputs: tuple[bool, ...]
    schema_version: ClassVar[str] = "biocompiler.boolean_spec.v0.1"

    def __post_init__(self):
        original = _checked_inputs(self.inputs)
        require(
            isinstance(self.outputs, (tuple, list)), "Boolean outputs must be an array."
        )
        require(
            len(self.outputs) == 1 << len(original),
            "Boolean table must contain exactly 2**input_count rows.",
        )
        require(
            all(type(value) is bool for value in self.outputs),
            "Boolean table outputs must be exact bool values.",
        )
        canonical = tuple(sorted(original, key=lambda signal: signal.id))
        positions = tuple(canonical.index(signal) for signal in original)
        outputs = tuple(
            self.outputs[_row_in_order(row, len(original), positions)]
            for row in range(1 << len(original))
        )
        object.__setattr__(self, "inputs", canonical)
        object.__setattr__(self, "outputs", outputs)
        self._check_resources()

    @classmethod
    def constant(cls, value: bool, *, inputs=()) -> BooleanSpec:
        require(type(value) is bool, "Boolean constant must be an exact bool.")
        checked = _checked_inputs(inputs)
        return cls(checked, (value,) * (1 << len(checked)))

    @classmethod
    def projection(cls, signal: CircuitSignal) -> BooleanSpec:
        require(
            isinstance(signal, CircuitSignal), "Projection requires a CircuitSignal."
        )
        return cls((signal,), (False, True))

    def evaluate(
        self, observations: Mapping[str, bool | LogicValue | None]
    ) -> LogicValue:
        require(
            isinstance(observations, Mapping), "Boolean observations must be a mapping."
        )
        require(
            len(observations) <= len(self.inputs),
            "Boolean observations include unknown signal IDs.",
        )
        allowed = {signal.id for signal in self.inputs}
        classified = {}
        for key, value in observations.items():
            require(
                isinstance(key, str) and key in allowed,
                "Boolean observations include unknown signal IDs.",
            )
            require(
                value is None or type(value) is bool or isinstance(value, LogicValue),
                "Observations must be exact bool, LogicValue, or None.",
            )
            if value is True or value is LogicValue.TRUE:
                classified[key] = True
            elif value is False or value is LogicValue.FALSE:
                classified[key] = False
        result = None
        for row, output in enumerate(self.outputs):
            if any(
                bool((row >> (len(self.inputs) - 1 - index)) & 1)
                != classified[signal.id]
                for index, signal in enumerate(self.inputs)
                if signal.id in classified
            ):
                continue
            if result is None:
                result = output
            elif result != output:
                return LogicValue.UNKNOWN
        return LogicValue.TRUE if result is True else LogicValue.FALSE

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "inputs": [signal.to_dict() for signal in self.inputs],
            "outputs": list(self.outputs),
        }

    @classmethod
    def from_dict(cls, data):
        _bounded_document(data)
        fields(data, {"schema_version", "inputs", "outputs"}, "Boolean specification")
        require(
            data["schema_version"] == cls.schema_version, "Unsupported Boolean schema."
        )
        raw_inputs = data["inputs"]
        require(
            isinstance(raw_inputs, (tuple, list)), "Boolean inputs must be an array."
        )
        require(len(raw_inputs) <= MAX_BOOLEAN_INPUTS, "Boolean input limit exceeded.")
        return cls(
            tuple(CircuitSignal.from_dict(item) for item in raw_inputs), data["outputs"]
        )


def _operand(value):
    if isinstance(value, BooleanSpec):
        return value
    if isinstance(value, CircuitSignal):
        return value.expression()
    if type(value) is bool:
        return BooleanSpec.constant(value)
    raise SerializationError(
        "Boolean operands require a specification, signal or exact bool."
    )


def _combine(operation, operands):
    require(len(operands) <= MAX_BOOLEAN_OPERANDS, "Boolean operand limit exceeded.")
    specifications = tuple(_operand(item) for item in operands)
    bindings = {}
    for spec in specifications:
        for signal in spec.inputs:
            prior = bindings.get(signal.id)
            require(
                prior is None or prior == signal,
                f"Conflicting observation binding for signal {signal.id}.",
            )
            bindings[signal.id] = signal
            require(
                len(bindings) <= MAX_BOOLEAN_INPUTS, "Boolean input limit exceeded."
            )
    inputs = tuple(sorted(bindings.values(), key=lambda signal: signal.id))
    positions = tuple(
        tuple(inputs.index(signal) for signal in spec.inputs) for spec in specifications
    )
    outputs = tuple(
        operation(
            tuple(
                spec.outputs[_row_in_order(row, len(inputs), projection)]
                for spec, projection in zip(specifications, positions, strict=True)
            )
        )
        for row in range(1 << len(inputs))
    )
    return BooleanSpec(inputs, outputs)


def nand(*operands) -> BooleanSpec:
    """Negated conjunction; at least one operand is required."""
    require(len(operands) >= 1, "NAND requires at least one operand.")
    return _combine(lambda values: not all(values), operands)


def nor(*operands) -> BooleanSpec:
    """Negated disjunction; at least one operand is required."""
    require(len(operands) >= 1, "NOR requires at least one operand.")
    return _combine(lambda values: not any(values), operands)


def parity(*operands) -> BooleanSpec:
    """True for an odd number of true operands; empty parity is false."""
    return _combine(lambda values: sum(values) % 2 == 1, operands)


def xnor(*operands) -> BooleanSpec:
    """Even parity, not chained binary XNOR; requires at least two operands."""
    require(len(operands) >= 2, "XNOR requires at least two operands.")
    return _combine(lambda values: sum(values) % 2 == 0, operands)


def all_equal(*operands) -> BooleanSpec:
    """True when all operands agree; unlike even parity for three or more."""
    require(len(operands) >= 2, "All-equal requires at least two operands.")
    return _combine(
        lambda values: all(value == values[0] for value in values), operands
    )
