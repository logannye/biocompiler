"""Shared graph construction behind public authoring objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import json
from pathlib import Path
from typing import Any

from biocompiler.errors import DefinitionError
from biocompiler.ir.intent import IntentNode, IntentProgram, SourceLocation

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def capture_source() -> SourceLocation | None:
    frame = inspect.currentframe()
    try:
        while frame is not None:
            filename = frame.f_code.co_filename
            if not Path(filename).resolve().is_relative_to(_PACKAGE_ROOT):
                return SourceLocation(filename, frame.f_lineno, frame.f_code.co_name)
            frame = frame.f_back
    finally:
        del frame
    return None


class GraphBuilder:
    """Assign ids, retain source locations, and freeze rooted snapshots."""

    def __init__(self) -> None:
        self._nodes: dict[str, IntentNode] = {}
        self._roots: dict[str, None] = {}
        self._names: dict[tuple[str, str], str] = {}
        self._interned: dict[str, str] = {}

    @staticmethod
    def validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise DefinitionError("Names must be non-empty strings.")
        return name

    @staticmethod
    def _type_data(data_type: Any) -> Mapping | None:
        if data_type is not None and hasattr(data_type, "to_dict"):
            return data_type.to_dict()
        return data_type

    @staticmethod
    def _key(node: IntentNode) -> str:
        data = node.to_dict(include_source=False)
        del data["id"]
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def add(
        self,
        kind: str,
        *,
        inputs: Sequence[str] = (),
        attributes: Mapping[str, Any] | None = None,
        data_type: Any = None,
        role: str | None = None,
        intern: bool = False,
    ) -> str:
        node_id = f"n{len(self._nodes) + 1:06d}"
        node = IntentNode(
            node_id,
            kind,
            tuple(inputs),
            attributes or {},
            self._type_data(data_type),
            role,
            capture_source(),
        )
        for ref in (*node.inputs, *((role,) if role is not None else ())):
            if ref not in self._nodes:
                raise DefinitionError(f"Unknown graph reference: {ref}.")
        key = self._key(node)
        if intern and key in self._interned:
            return self._interned[key]
        self._nodes[node_id] = node
        if intern:
            self._interned[key] = node_id
        return node_id

    def declare(self, namespace: str, name: str, kind: str, **kwargs: Any) -> str:
        self.validate_name(namespace)
        self.validate_name(name)
        attributes = dict(kwargs.pop("attributes", None) or {})
        if "name" in attributes and attributes["name"] != name:
            raise DefinitionError("Declaration name disagrees with its attributes.")
        attributes["name"] = name
        key = (namespace, name)
        if key in self._names:
            previous = self.get(self._names[key])
            proposed = IntentNode(
                previous.id,
                kind,
                tuple(kwargs.get("inputs", ())),
                attributes,
                self._type_data(kwargs.get("data_type")),
                kwargs.get("role"),
            )
            if self._key(previous) != self._key(proposed):
                raise DefinitionError(
                    f"Conflicting definition of {name!r} in {namespace!r}."
                )
            return previous.id
        node_id = self.add(kind, attributes=attributes, **kwargs)
        self._names[key] = node_id
        return node_id

    def get(self, node_id: str) -> IntentNode:
        return self._nodes[node_id]

    def mark_root(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise DefinitionError(f"Unknown root reference: {node_id}.")
        self._roots[node_id] = None

    def freeze(self, name: str) -> IntentProgram:
        self.validate_name(name)
        reachable: set[str] = set()
        pending = list(self._roots)
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            node = self.get(node_id)
            pending.extend(node.inputs)
            if node.role is not None:
                pending.append(node.role)
        return IntentProgram(
            name,
            tuple(
                node for node_id, node in self._nodes.items() if node_id in reachable
            ),
            tuple(self._roots),
        )
