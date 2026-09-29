"""Typed synthetic mechanism graphs for testing realization contracts.

These digital operators are a bounded model fixture, not molecular components.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from typing import Any

from cellweave.errors import SerializationError, TypeMismatchError
from cellweave.ir.intent import freeze_json, thaw_json
from cellweave.ir.serialization import fingerprint, parse_json
from cellweave.semantics.realization import Observable
from cellweave.semantics.types import (
    DURATION,
    ScalarLiteral,
    decode_binding,
    validate_binding,
)

SCHEMA_VERSION = "cellweave.mechanism.synthetic.v0.1"
SUPPORTED_OPERATIONS = frozenset(
    {
        "input",
        "constant",
        "and",
        "or",
        "not",
        "compare",
        "select",
        "delay",
        "output",
        "any_contact",
    }
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SerializationError(message)


def _name(value: Any, label: str) -> None:
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"{label} must be a nonempty string.",
    )


def _names(values: Any, label: str) -> tuple[str, ...]:
    _require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    for value in values:
        _name(value, label)
    _require(len(set(values)) == len(values), f"{label} must not contain duplicates.")
    return tuple(values)


def _literal(value: Any, dtype: Any) -> Any:
    if dtype.kind == "condition":
        _require(type(value) is bool, "A Boolean port requires a Boolean literal.")
        return value
    try:
        if isinstance(value, Mapping):
            return decode_binding(value, dtype).to_dict()
        return decode_binding(validate_binding(value, dtype), dtype).to_dict()
    except (TypeMismatchError, ValueError, KeyError) as exc:
        raise SerializationError(f"Invalid typed model literal: {exc}") from exc


@dataclass(frozen=True)
class MechanismNode:
    """One typed semantic output port and its synthetic operation.

    ``id`` identifies the graph node; ``output.id`` identifies signal meaning.
    Scalar constants use typed literals, or plain dimensionless numbers.
    """

    id: str
    kind: str
    output: Observable
    inputs: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    requirement_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _name(self.id, "Mechanism node ID")
        _require(
            isinstance(self.kind, str) and self.kind in SUPPORTED_OPERATIONS,
            f"Unsupported synthetic operation {self.kind!r}.",
        )
        _require(
            isinstance(self.output, Observable),
            "A mechanism node requires an Observable output port.",
        )
        _require(
            self.output.dtype.kind in {"scalar", "condition"},
            "Synthetic ports support scalar and Boolean types only.",
        )
        _require(
            isinstance(self.inputs, (tuple, list)), "Mechanism inputs must be an array."
        )
        for ref in self.inputs:
            _name(ref, "Mechanism input reference")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(
            self,
            "requirement_ids",
            _names(self.requirement_ids, "Source requirement IDs"),
        )
        _require(
            isinstance(self.attributes, Mapping),
            "Mechanism attributes must be an object.",
        )
        attrs = dict(self.attributes)
        expected = (
            {"value"}
            if self.kind == "constant"
            else {"operator"}
            if self.kind == "compare"
            else {"duration", "initial"}
            if self.kind == "delay"
            else set()
        )
        _require(set(attrs) == expected, f"Invalid attributes for {self.kind!r}.")
        if self.kind == "constant":
            attrs["value"] = _literal(attrs["value"], self.output.dtype)
        elif self.kind == "compare":
            _require(
                isinstance(attrs["operator"], str)
                and attrs["operator"] in {"lt", "le", "gt", "ge", "eq", "ne"},
                "Unknown comparison operator.",
            )
        elif self.kind == "delay":
            value = attrs["duration"]
            if isinstance(value, ScalarLiteral):
                value = value.to_dict()
            try:
                duration = decode_binding(value, DURATION)
            except (TypeMismatchError, ValueError, KeyError) as exc:
                raise SerializationError(
                    f"Delay duration requires a typed Duration: {exc}"
                ) from exc
            _require(
                duration.canonical_value > 0, "An inertial delay must be positive."
            )
            attrs["duration"] = duration.to_dict()
            attrs["initial"] = _literal(attrs["initial"], self.output.dtype)
        object.__setattr__(self, "attributes", freeze_json(attrs))

    @property
    def data_type(self) -> Mapping:
        return freeze_json(self.output.dtype.to_dict())

    @property
    def role(self) -> str:
        return self.output.role

    @property
    def scope(self) -> str:
        return self.output.scope

    @property
    def compartment(self) -> str:
        return self.output.compartment

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "output": self.output.to_dict(),
            "inputs": list(self.inputs),
            "attributes": thaw_json(self.attributes),
            "requirement_ids": list(self.requirement_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> MechanismNode:
        fields = {"id", "kind", "output", "inputs", "attributes", "requirement_ids"}
        _require(
            isinstance(data, Mapping) and set(data) == fields,
            "Invalid mechanism node fields.",
        )
        return cls(
            data["id"],
            data["kind"],
            Observable.from_dict(data["output"]),
            data["inputs"],
            data["attributes"],
            data["requirement_ids"],
        )


def _validate_node(node: MechanismNode, nodes: Mapping[str, MechanismNode]) -> None:
    inputs = [nodes[ref] for ref in node.inputs]
    label = f"{node.id} ({node.kind})"

    def check(condition, message):
        _require(condition, f"{label}: {message}")

    def same_type(other):
        return node.output.dtype.compatible(other.output.dtype)

    for other in inputs:
        check(
            other.role == node.role,
            "Cross-role edges require an unimplemented transport model.",
        )
        check(
            other.compartment == node.compartment,
            "Cross-compartment edges require an unimplemented transport model.",
        )
        if other.scope == "contact" and node.scope == "cell":
            check(
                node.kind == "any_contact",
                "Contact-to-cell flow requires explicit any_contact aggregation.",
            )
    if node.kind in {"input", "constant"}:
        check(not inputs, "Expected no input edges.")
    elif node.kind in {"and", "or"}:
        check(len(inputs) >= 2, "Expected at least two input edges.")
        check(
            node.output.dtype.kind == "condition"
            and all(other.output.dtype.kind == "condition" for other in inputs),
            "Logical operators require Boolean ports.",
        )
    elif node.kind == "not":
        check(len(inputs) == 1, "Expected one input edge.")
        check(
            node.output.dtype.kind == "condition"
            and inputs[0].output.dtype.kind == "condition",
            "Logical negation requires Boolean ports.",
        )
    elif node.kind == "compare":
        check(len(inputs) == 2, "Expected two input edges.")
        check(
            node.output.dtype.kind == "condition"
            and all(other.output.dtype.kind == "scalar" for other in inputs),
            "Comparison requires scalar operands and a Boolean result.",
        )
        check(
            inputs[0].output.dtype.compatible(inputs[1].output.dtype),
            "Comparison operands have incompatible dimensions.",
        )
    elif node.kind == "select":
        check(len(inputs) == 3, "Expected condition, true value and false value.")
        check(
            inputs[0].output.dtype.kind == "condition"
            and same_type(inputs[1])
            and same_type(inputs[2]),
            "Select condition or branch types disagree with its output.",
        )
    elif node.kind in {"delay", "output"}:
        check(len(inputs) == 1, "Expected one input edge.")
        check(same_type(inputs[0]), "Input and output types must agree.")
    elif node.kind == "any_contact":
        check(len(inputs) == 1, "Expected one input edge.")
        check(
            node.scope == "cell" and inputs[0].scope == "contact",
            "any_contact requires a contact input and a cell output.",
        )
        check(
            node.output.dtype.kind == "condition"
            and inputs[0].output.dtype.kind == "condition",
            "any_contact requires Boolean ports.",
        )


@dataclass(frozen=True)
class MechanismProgram:
    """A single-role acyclic synthetic candidate with explicit external ports."""

    name: str
    nodes: tuple[MechanismNode, ...]
    outputs: tuple[str, ...]
    required_capabilities: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _name(self.name, "Mechanism program name")
        _require(
            self.schema_version == SCHEMA_VERSION,
            "Unsupported mechanism schema version.",
        )
        _require(
            isinstance(self.nodes, (tuple, list)) and bool(self.nodes),
            "A mechanism program requires a nonempty node array.",
        )
        _require(
            all(isinstance(node, MechanismNode) for node in self.nodes),
            "Invalid mechanism node.",
        )
        nodes = {node.id: node for node in self.nodes}
        _require(len(nodes) == len(self.nodes), "Duplicate mechanism node IDs.")
        _require(
            len({node.role for node in self.nodes}) == 1,
            "The synthetic profile represents one executing cell role per program.",
        )
        for node in self.nodes:
            _require(
                all(ref in nodes for ref in node.inputs),
                f"Unknown input reference on {node.id}.",
            )
            _validate_node(node, nodes)
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(
            self, "outputs", _names(self.outputs, "Mechanism output IDs")
        )
        _require(
            bool(self.outputs), "A mechanism program requires at least one output."
        )
        _require(
            all(ref in nodes and nodes[ref].kind == "output" for ref in self.outputs),
            "Program outputs must name output operations.",
        )
        object.__setattr__(
            self,
            "required_capabilities",
            _names(self.required_capabilities, "Required capabilities"),
        )
        self.topological_nodes()

    def get(self, node_id: str) -> MechanismNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def find(self, kind: str) -> tuple[MechanismNode, ...]:
        return tuple(node for node in self.nodes if node.kind == kind)

    def topological_nodes(self) -> tuple[MechanismNode, ...]:
        nodes = {node.id: node for node in self.nodes}
        pending = {node.id: set(node.inputs) for node in self.nodes}
        ordered = []
        while pending:
            ready = sorted(
                ref for ref, dependencies in pending.items() if not dependencies
            )
            _require(bool(ready), "Mechanism graph contains a dependency cycle.")
            ordered.extend(nodes[ref] for ref in ready)
            for ref in ready:
                del pending[ref]
            for dependencies in pending.values():
                dependencies.difference_update(ready)
        return tuple(ordered)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "outputs": list(self.outputs),
            "required_capabilities": list(self.required_capabilities),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, indent=indent, allow_nan=False
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping) -> MechanismProgram:
        fields = {"schema_version", "name", "nodes", "outputs", "required_capabilities"}
        _require(
            isinstance(data, Mapping) and set(data) == fields,
            "Invalid mechanism program fields.",
        )
        _require(
            isinstance(data["nodes"], (tuple, list)),
            "Mechanism nodes must be an array.",
        )
        return cls(
            data["name"],
            tuple(MechanismNode.from_dict(node) for node in data["nodes"]),
            data["outputs"],
            data["required_capabilities"],
            data["schema_version"],
        )

    @classmethod
    def from_json(cls, text: str) -> MechanismProgram:
        return cls.from_dict(parse_json(text))
