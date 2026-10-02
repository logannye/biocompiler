"""Precise RA-01 diagnostic projections for the retained source capture.

Fixture tooling only: this is neither an acceptance validator nor a runtime
adapter. Structural checks follow the native imports so nested primitive errors
are retained. The finite observed semantic-message set fails on new cases.
Python-only class restrictions are explicit separately replayed boundaries.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

_FIELDS = {
    "Observable": {"id", "dtype", "role", "scope", "compartment"},
    "InputDomain": {"signal_id", "field", "observable", "allowed"},
    "OperatingDomain": {"id", "version", "role", "inputs", "minimum_horizon", "max_contacts", "required_capabilities"},
    "ResponseRequirement": {"id", "rule_id", "specification_id", "observable", "active_range", "inactive_range", "max_activation_delay", "max_deactivation_delay"},
    "BehaviorContract": {"id", "behavior_fingerprint", "requirements"},
}
_SCHEMAS = dict(zip(_FIELDS, (
    "biocompiler.observable.v0.1", "biocompiler.input_domain.v0.1", "biocompiler.operating_domain.v0.1",
    "biocompiler.response_requirement.v0.1", "biocompiler.behavior_contract.v0.1",
)))
_TYPE_ERRORS = {
    "A serialized type has missing or unknown fields.", "A serialized type must be an object.",
    "A type requires nonempty kind and name strings.", "Dimensions require names and integer powers.",
    "Type dimensions must be an object and arguments must be an array.",
}
_BINDING_ERRORS = _TYPE_ERRORS | {
    "A quantity requires a real number, not a Boolean or arbitrary object.",
    "A scalar binding requires a nonempty unit.",
    "A scalar binding's canonical value disagrees with its value and unit.",
    "A serialized binding must be an object.",
    "A serialized scalar binding has invalid fields or kind.",
    "A serialized interval binding has invalid fields or kind.",
    "Expected Duration, got Duration.", "Expected Duration, got Level.",
    "interval requires 1 scalar type argument(s).",
}
_NAMES = {
    "Behavior action specification id", "Behavior contract id", "Behavior rule id", "Behavior signal id",
    "Observable compartment", "Observable id", "Observable role", "Operating domain id", "Operating domain role",
    "Operating domain version", "Response requirement id",
}
_CONTEXT = {
    "A behavior contract requires nonempty response requirements.",
    "All input domains must belong to the selected role.", "Allowed Boolean values must be unique.",
    "Behavior fingerprint must be SHA-256 hex.",
    "Each rule/action specification must have one response requirement in this profile.",
    "Fields of one signal must agree on scope and compartment.", "Input domains must have unique signal/field identities.",
    "Numeric observations require a scalar observable.",
    "Operating domain requires a nonempty array of InputDomain records.",
    "Qualitative input domain must be a nonempty array of Booleans.",
    "Response measurement endpoint ids must be unique.", "Response requirement ids must be unique.",
    "Unknown input observation field.", "max_contacts must be a nonnegative integer or None.",
}
_MEASUREMENT = {
    "Closed active and inactive response ranges must be disjoint.", "Observable scope must be cell or contact.",
    "activation delay must be nonnegative.", "minimum horizon must be positive.",
}
_BOUNDARIES = {"activation delay requires a typed Duration literal.", "minimum horizon requires a typed Duration literal."}
_ARRAY_ERRORS = {"Operating domain inputs must be an array.", "Required capabilities must be an array.", "Response requirements must be an array."}
_OBSERVED = (_CONTEXT | _MEASUREMENT | _BOUNDARIES | _ARRAY_ERRORS |
             {f"{name} must be a nonempty string." for name in _NAMES})
_OBSERVED |= {f"Invalid fields in {name}." for name in _FIELDS}
_OBSERVED |= {f"Unsupported {name} schema." for name in _FIELDS}
_OBSERVED |= {f"Invalid observable type: {message}" for message in _TYPE_ERRORS}
_OBSERVED |= {f"Invalid {label}: {message}" for label in ("activation delay", "active range", "deactivation delay", "inactive range", "minimum horizon") for message in _BINDING_ERRORS}
_OBSERVED |= {"Invalid active response range: Expected Interval[Level], got Interval[Duration].", "Duplicate JSON key: id.", "Invalid JSON number: NaN.", "Response activity must be Boolean."}


class _Code(Exception):
    def __init__(self, code: str):
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise _Code(code)


def _object(value: Any) -> dict:
    _require(isinstance(value, dict), "invalid_type")
    return value


def _fields(value: Any, required: set[str], optional: set[str] = frozenset()) -> dict:
    value = _object(value)
    _require(not required - value.keys(), "missing_field")
    _require(not value.keys() - required - optional, "unknown_field")
    return value


def _string(value: Any) -> str:
    _require(isinstance(value, str), "invalid_type")
    return value


def _name(value: Any) -> None:
    _require(bool(_string(value).strip()), "invalid_name")


def _array(value: Any) -> list:
    _require(isinstance(value, list), "invalid_type")
    return value


def _dtype(value: Any) -> dict:
    value = _fields(value, {"kind", "name"}, {"dimensions", "arguments"})
    kind = _string(value["kind"])
    _require(kind in {"scalar", "condition", "event", "interval", "curve"}, "invalid_type_spec")
    _require(bool(_string(value["name"])), "invalid_type_spec")
    dimensions = _object(value.get("dimensions", {}))
    for key, exponent in dimensions.items():
        _require(bool(key), "invalid_type_spec")
        _require(type(exponent) is int, "invalid_type")
    dimensions = {k: v for k, v in dimensions.items() if v != 0}
    arguments = [_dtype(item) for item in _array(value.get("arguments", []))]
    if kind == "scalar":
        _require(not arguments, "invalid_type_spec")
    elif kind in {"condition", "event"}:
        _require(not dimensions and not arguments, "invalid_type_spec")
    else:
        _require(not dimensions and len(arguments) == (1 if kind == "interval" else 2)
                 and all(item["kind"] == "scalar" for item in arguments), "invalid_type_spec")
    return {"kind": kind, "name": value["name"], "dimensions": dimensions, "arguments": arguments}


def _compatible(a: dict, b: dict) -> bool:
    return a["kind"] == b["kind"] and a["dimensions"] == b["dimensions"] and len(a["arguments"]) == len(b["arguments"]) and all(_compatible(x, y) for x, y in zip(a["arguments"], b["arguments"]))


_DURATION = {"kind": "scalar", "name": "Duration", "dimensions": {"time": 1}, "arguments": []}


def _number(value: Any) -> None:
    _require(type(value) in {int, float}, "invalid_type")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite, "numeric_overflow")


def _binding(value: Any, kind: str, expected: dict | None = None) -> None:
    # Measurement codecs inspect type before exact binding fields; malformed
    # type-only objects consequently retain missing_field/invalid_type.
    fields = _object(value)
    _require("type" in fields, "missing_field")
    dtype = _dtype(fields["type"])
    _require(dtype["kind"] == kind, "invalid_measurement_contract")
    keys = {"kind", "type", "value", "unit", "canonical_value"} if kind == "scalar" else {"kind", "type", "lower", "upper"}
    _fields(fields, keys)
    _require(_string(fields["kind"]) == kind, "invalid_binding")
    if expected is not None:
        _require(_compatible(dtype, expected), "type_mismatch")
    if kind == "scalar":
        _number(fields["value"])
        _number(fields["canonical_value"])
        _name(fields["unit"])
    else:
        _binding(fields["lower"], "scalar", dtype["arguments"][0])
        _binding(fields["upper"], "scalar", dtype["arguments"][0])


def _record(kind: str, value: Any) -> None:
    value = _fields(value, _FIELDS[kind] | {"schema_version"})
    _require(_string(value["schema_version"]) == _SCHEMAS[kind], "unsupported_schema")
    if kind == "Observable":
        dtype = _dtype(value["dtype"])
        _require(dtype["kind"] in {"scalar", "condition"}, "invalid_measurement_contract")
        _require(_string(value["scope"]) in {"cell", "contact"}, "invalid_measurement_contract")
        for key in ("id", "role", "compartment"):
            _name(value[key])
    elif kind == "InputDomain":
        _record("Observable", value["observable"])
        _name(value["signal_id"])
        field = _string(value["field"])
        _require(field in {"value", "present", "high", "low"}, "invalid_realization_contract")
        dtype = _dtype(value["observable"]["dtype"])
        if field == "value":
            _require(dtype["kind"] == "scalar", "invalid_realization_contract")
            _binding(value["allowed"], "interval", {"kind": "interval", "dimensions": {}, "arguments": [dtype]})
        else:
            _require(dtype["kind"] == "condition", "invalid_realization_contract")
            allowed = _array(value["allowed"])
            for item in allowed:
                _require(type(item) is bool, "invalid_type")
    elif kind == "ResponseRequirement":
        for key in ("id", "rule_id", "specification_id"):
            _name(value[key])
        _record("Observable", value["observable"])
        dtype = _dtype(value["observable"]["dtype"])
        _require(dtype["kind"] == "scalar", "invalid_measurement_contract")
        interval = {"kind": "interval", "dimensions": {}, "arguments": [dtype]}
        for key in ("active_range", "inactive_range"):
            _binding(value[key], "interval", interval)
        for key in ("max_activation_delay", "max_deactivation_delay"):
            _binding(value[key], "scalar", _DURATION)
    elif kind == "OperatingDomain":
        for item in _array(value["inputs"]):
            _record("InputDomain", item)
        _binding(value["minimum_horizon"], "scalar", _DURATION)
        for key in ("id", "version", "role"):
            _name(value[key])
        if value["max_contacts"] is not None:
            _require(type(value["max_contacts"]) is int, "invalid_type")
        for item in _array(value["required_capabilities"]):
            _name(item)
    else:
        for item in _array(value["requirements"]):
            _record("ResponseRequirement", item)
        _name(value["id"])
        _string(value["behavior_fingerprint"])


def expected_code(call: Mapping[str, Any], operation: str, value: Any) -> str | None:
    """Project only observed rejections; preserve original membership markers."""
    assert operation in set(_FIELDS) | {"InputDomain.contains", "ResponseRequirement.accepts"}, operation
    if call["outcome"] == "returned":
        return None
    assert call["outcome"] == "raised", call["outcome"]
    error = call["error"]
    assert error["module"] == "biocompiler.errors" and error["type"] == "SerializationError", error
    message = error["message"]
    assert message in _OBSERVED, f"Unclassified contract diagnostic: {operation}: {message}"
    if operation == "ResponseRequirement.accepts":
        assert message == "Response activity must be Boolean." and type(value["active"]) is not bool
        return "invalid_type"
    assert operation in _FIELDS, (operation, message)
    if message in {"Duplicate JSON key: id.", "Invalid JSON number: NaN."}:
        assert call["api"].endswith(".from_json") and isinstance(value, str)
        return "duplicate_key" if message.startswith("Duplicate") else "invalid_json"
    try:
        _record(operation, value)
    except _Code as error:
        return error.code
    if message in _CONTEXT:
        return "invalid_realization_contract"
    if message in _MEASUREMENT:
        return "invalid_measurement_contract"
    if message in _BOUNDARIES:
        # Only the constructor requires a ScalarLiteral Python object; the
        # native counterpart is explicitly replayed and may validly decode.
        assert call["api"].endswith(".__init__")
        from biocompiler.semantics import realization
        getattr(realization, operation).from_dict(value)
        return "python_type_boundary"
    if "canonical value disagrees with its value and unit." in message:
        return "canonical_value_mismatch"
    if message == "Invalid active response range: Expected Interval[Level], got Interval[Duration].":
        return "type_mismatch"
    raise AssertionError(f"Unclassified native contract rejection: {operation}: {message}")
