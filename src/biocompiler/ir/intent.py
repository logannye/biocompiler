"""Immutable, versioned intent graphs; these describe rather than simulate cells."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any

from biocompiler.errors import SerializationError, TypeMismatchError
from biocompiler.semantics.types import TypeSpec, decode_binding

SCHEMA_VERSION = "biocompiler.intent.v0.1"


def freeze_json(value: Any) -> Any:
    """Copy JSON data into recursively immutable containers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SerializationError("Non-finite numbers cannot be serialized.")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SerializationError("Object keys must be strings.")
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze_json(item) for item in value)
    raise SerializationError(f"Unsupported JSON value: {type(value).__name__}.")


def thaw_json(value: Any) -> Any:
    """Return an independent mutable JSON representation."""
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SerializationError(f"{label} must be a non-empty string.")
    return value


def _keys(data: Mapping, required: set[str], optional: set[str], label: str) -> None:
    if set(data) - required - optional or required - set(data):
        raise SerializationError(f"Invalid fields in {label}.")


@dataclass(frozen=True)
class SourceLocation:
    """Location at which an intent node was authored."""

    file: str
    line: int
    function: str = "<module>"

    def __post_init__(self) -> None:
        _name(self.file, "Source file")
        _name(self.function, "Source function")
        if type(self.line) is not int or self.line < 1:
            raise SerializationError("Source line must be a positive integer.")

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "function": self.function}

    @classmethod
    def from_dict(cls, data: Mapping) -> SourceLocation:
        if not isinstance(data, Mapping):
            raise SerializationError("Source location must be an object.")
        _keys(data, {"file", "line", "function"}, set(), "source location")
        return cls(**data)


@dataclass(frozen=True)
class IntentNode:
    """Semantic node with explicit references and owning cell role."""

    id: str
    kind: str
    inputs: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    data_type: Mapping[str, Any] | None = None
    role: str | None = None
    source: SourceLocation | None = None

    def __post_init__(self) -> None:
        _name(self.id, "Node id")
        _name(self.kind, "Node kind")
        if not isinstance(self.inputs, (tuple, list)):
            raise SerializationError("Node inputs must be an array.")
        for ref in self.inputs:
            _name(ref, "Input reference")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if not isinstance(self.attributes, Mapping):
            raise SerializationError("Node attributes must be an object.")
        object.__setattr__(self, "attributes", freeze_json(self.attributes))
        if self.data_type is not None:
            if not isinstance(self.data_type, Mapping):
                raise SerializationError("Node data_type must be an object or null.")
            try:
                TypeSpec.from_dict(self.data_type)
            except (TypeMismatchError, ValueError, KeyError) as exc:
                raise SerializationError(
                    f"Invalid data type on node {self.id}: {exc}"
                ) from exc
            object.__setattr__(self, "data_type", freeze_json(self.data_type))
        if self.kind in {"parameter", "literal"}:
            if self.data_type is None:
                raise SerializationError(
                    f"{self.kind} nodes require a declared data type."
                )
            value_key = "value"
            if self.kind == "parameter":
                _name(self.attributes.get("name"), "Parameter name")
                if type(self.attributes.get("bound")) is not bool:
                    raise SerializationError(
                        "Parameters must declare whether a default is bound."
                    )
                if self.attributes["bound"] != ("default" in self.attributes):
                    raise SerializationError(
                        "Parameter bound flag and default must agree."
                    )
                value_key = "default"
            if self.kind == "literal" or self.attributes["bound"]:
                try:
                    decode_binding(
                        self.attributes[value_key], TypeSpec.from_dict(self.data_type)
                    )
                except (TypeMismatchError, KeyError, ValueError) as exc:
                    raise SerializationError(
                        f"Invalid typed value on node {self.id}: {exc}"
                    ) from exc
        if self.role is not None:
            _name(self.role, "Role reference")
        if self.source is not None and not isinstance(self.source, SourceLocation):
            raise SerializationError("Node source must be a SourceLocation or null.")

    def to_dict(self, *, include_source: bool = True) -> dict:
        result = {
            "id": self.id,
            "kind": self.kind,
            "inputs": list(self.inputs),
            "attributes": thaw_json(self.attributes),
            "data_type": thaw_json(self.data_type),
            "role": self.role,
        }
        if include_source:
            result["source"] = self.source.to_dict() if self.source else None
        return result

    @classmethod
    def from_dict(cls, data: Mapping) -> IntentNode:
        if not isinstance(data, Mapping):
            raise SerializationError("Each node must be an object.")
        _keys(
            data,
            {"id", "kind", "inputs", "attributes", "data_type", "role"},
            {"source"},
            "intent node",
        )
        source = data.get("source")
        return cls(
            id=data["id"],
            kind=data["kind"],
            inputs=data["inputs"],
            attributes=data["attributes"],
            data_type=data["data_type"],
            role=data["role"],
            source=SourceLocation.from_dict(source) if source is not None else None,
        )


@dataclass(frozen=True)
class IntentProgram:
    """An immutable snapshot, retaining unresolved design concepts."""

    name: str
    nodes: tuple[IntentNode, ...]
    roots: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _name(self.name, "Program name")
        if self.schema_version != SCHEMA_VERSION:
            raise SerializationError(
                f"Unsupported intent schema: {self.schema_version!r}."
            )
        if not isinstance(self.nodes, (tuple, list)) or not all(
            isinstance(node, IntentNode) for node in self.nodes
        ):
            raise SerializationError(
                "Program nodes must be an array of IntentNode records."
            )
        if not isinstance(self.roots, (tuple, list)):
            raise SerializationError("Program roots must be an array.")
        for root in self.roots:
            _name(root, "Root reference")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "roots", tuple(self.roots))
        self._validate_references()

    def _validate_references(self) -> None:
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise SerializationError("Duplicate node ids in intent program.")
        if len(set(self.roots)) != len(self.roots):
            raise SerializationError("Duplicate root ids in intent program.")
        if any(root not in nodes for root in self.roots):
            raise SerializationError("Dangling root reference in intent program.")
        parameter_names = [
            node.attributes["name"] for node in self.nodes if node.kind == "parameter"
        ]
        if len(set(parameter_names)) != len(parameter_names):
            raise SerializationError("Duplicate parameter names in intent program.")
        dependents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        pending = {}
        for node in self.nodes:
            refs = set(node.inputs)
            if node.role is not None:
                if node.role not in nodes or nodes[node.role].kind != "role":
                    raise SerializationError(
                        f"Node {node.id} has an invalid role reference."
                    )
                refs.add(node.role)
            if refs - nodes.keys():
                raise SerializationError(
                    f"Node {node.id} has dangling input references."
                )
            pending[node.id] = len(refs)
            for ref in refs:
                dependents[ref].append(node.id)
        # Structural references are acyclic; runtime feedback is represented by controllers.
        queue = deque(node_id for node_id, count in pending.items() if count == 0)
        visited = 0
        while queue:
            node_id = queue.popleft()
            visited += 1
            for dependent in dependents[node_id]:
                pending[dependent] -= 1
                if pending[dependent] == 0:
                    queue.append(dependent)
        if visited != len(nodes):
            raise SerializationError("Cyclic structural references in intent program.")

    def find(
        self, *, kind: str | None = None, role: str | None = None
    ) -> tuple[IntentNode, ...]:
        return tuple(
            node
            for node in self.nodes
            if (kind is None or node.kind == kind)
            and (role is None or node.role == role)
        )

    def to_dict(self, *, include_source: bool = True) -> dict:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "nodes": [
                node.to_dict(include_source=include_source) for node in self.nodes
            ],
            "roots": list(self.roots),
        }

    def to_json(self, *, indent: int | None = 2, include_source: bool = True) -> str:
        return json.dumps(
            self.to_dict(include_source=include_source),
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
        """Canonical graph SHA-256, independent of authoring file locations."""
        data = json.dumps(
            self.to_dict(include_source=False),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def summary(self) -> dict:
        counts = Counter(node.kind for node in self.nodes)
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "node_count": len(self.nodes),
            "roles": counts["role"],
            "rules": counts["rule"],
            "channels": counts["channel"],
            "kinds": dict(sorted(counts.items())),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> IntentProgram:
        if not isinstance(data, Mapping):
            raise SerializationError("Intent program must be an object.")
        _keys(
            data, {"schema_version", "name", "nodes", "roots"}, set(), "intent program"
        )
        if not isinstance(data["nodes"], (tuple, list)):
            raise SerializationError("Program nodes must be an array.")
        return cls(
            name=data["name"],
            nodes=tuple(IntentNode.from_dict(n) for n in data["nodes"]),
            roots=data["roots"],
            schema_version=data["schema_version"],
        )

    @classmethod
    def from_json(cls, text: str) -> IntentProgram:
        def unique_object(pairs: list[tuple[str, Any]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise SerializationError(f"Duplicate JSON key: {key}.")
                result[key] = value
            return result

        def invalid_constant(value: str) -> None:
            raise SerializationError(f"Invalid JSON number: {value}.")

        try:
            data = json.loads(
                text, object_pairs_hook=unique_object, parse_constant=invalid_constant
            )
        except (TypeError, json.JSONDecodeError, RecursionError) as exc:
            raise SerializationError(f"Invalid intent JSON: {exc}") from exc
        return cls.from_dict(data)
