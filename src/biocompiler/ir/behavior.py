"""Immutable executable *abstract* behavior, with checked operation semantics.

This representation commits to language execution policies, not molecular
mechanisms. Future lowerings must retain requirement and observation mappings.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import (
    IntentNode,
    IntentProgram,
    SourceLocation,
    freeze_json,
    thaw_json,
)
from biocompiler.semantics.contracts import BehaviorRequirement, EXECUTION_POLICIES
from biocompiler.semantics.types import (
    BOOLEAN,
    DURATION,
    EVENT,
    PRODUCTION_RATE,
    TypeSpec,
)

SCHEMA_VERSION = "biocompiler.behavior.v0.1"
SUPPORTED_KINDS = frozenset(
    {
        "role",
        "scope",
        "signal",
        "qualitative",
        "literal",
        "parameter",
        "and",
        "or",
        "not",
        "at_least",
        "add",
        "subtract",
        "multiply",
        "divide",
        "negate",
        "compare",
        "held_for",
        "recently",
        "became_true",
        "followed_by",
        "memory",
        "memory.is_set",
        "state",
        "state.is",
        "signature",
        "secretion",
        "rule",
        "action.state_set",
        "action.report",
        "action.pulse",
        "action.eliminate",
        "action.engulf",
        "action.secrete",
        "action.present",
        "action.retain",
        "action.expand",
        "action.rest",
        "action.differentiate",
    }
)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise SerializationError(message)


def _exact(left: Any, right: Any) -> bool:
    return json.dumps(thaw_json(left), sort_keys=True, allow_nan=False) == json.dumps(
        thaw_json(right), sort_keys=True, allow_nan=False
    )


def _named(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class BehaviorNode:
    id: str
    kind: str
    inputs: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    data_type: Mapping[str, Any] | None = None
    role: str | None = None
    source: SourceLocation | None = None
    contact_bound: bool = False
    requirement_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        source = IntentNode(
            self.id,
            self.kind,
            self.inputs,
            self.attributes,
            self.data_type,
            self.role,
            self.source,
        )
        for name in ("inputs", "attributes", "data_type"):
            object.__setattr__(self, name, getattr(source, name))
        _require(type(self.contact_bound) is bool, "Contact binding must be Boolean.")
        _require(
            isinstance(self.requirement_ids, (tuple, list)),
            "Requirement ids must be an array.",
        )
        _require(
            all(_named(item) for item in self.requirement_ids),
            "Invalid requirement reference.",
        )
        _require(
            len(set(self.requirement_ids)) == len(self.requirement_ids),
            "Duplicate requirement references.",
        )
        object.__setattr__(self, "requirement_ids", tuple(self.requirement_ids))

    def to_dict(self, *, include_source: bool = True) -> dict:
        result = IntentNode(
            self.id,
            self.kind,
            self.inputs,
            self.attributes,
            self.data_type,
            self.role,
            self.source,
        ).to_dict(include_source=include_source)
        result.update(
            contact_bound=self.contact_bound, requirement_ids=list(self.requirement_ids)
        )
        return result

    @classmethod
    def from_dict(cls, data: Mapping) -> BehaviorNode:
        _require(isinstance(data, Mapping), "Behavior node must be an object.")
        required = {
            "id",
            "kind",
            "inputs",
            "attributes",
            "data_type",
            "role",
            "contact_bound",
            "requirement_ids",
        }
        _require(
            not (required - set(data)) and not (set(data) - required - {"source"}),
            "Invalid behavior node fields.",
        )
        node = IntentNode.from_dict(
            {
                key: value
                for key, value in data.items()
                if key not in {"contact_bound", "requirement_ids"}
            }
        )
        return cls(
            node.id,
            node.kind,
            node.inputs,
            node.attributes,
            node.data_type,
            node.role,
            node.source,
            data["contact_bound"],
            data["requirement_ids"],
        )


def lineage_for(nodes: Mapping[str, Any], node_id: str) -> tuple[str, ...]:
    """Return deterministic complete structural ancestry, including the node."""
    seen = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        node = nodes[current]
        pending.extend(node.inputs)
        if node.role is not None:
            pending.append(node.role)
    return tuple(sorted(seen))


def contact_bindings(nodes: Mapping[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}

    def binding(node_id: str) -> bool:
        if node_id in result:
            return result[node_id]
        node = nodes[node_id]
        if node.kind == "scope":
            value = node.attributes.get("scope") == "contact"
        elif node.kind in {
            "role",
            "state",
            "state.is",
            "memory",
            "memory.is_set",
            "literal",
            "parameter",
            "secretion",
            "action.state_set",
        }:
            value = False
        elif node.kind == "signature":
            value = binding(node.inputs[0])
        else:
            value = any(binding(ref) for ref in node.inputs)
        result[node_id] = value
        return value

    for key in nodes:
        binding(key)
    return result


def constant_value(nodes: Mapping[str, Any], node_id: str) -> float | int | None:
    node = nodes[node_id]
    if node.kind in {"literal", "parameter"}:
        value = node.attributes.get("value" if node.kind == "literal" else "default")
        return (
            value["canonical_value"]
            if value and value.get("kind") == "scalar"
            else None
        )
    if node.kind == "negate":
        value = constant_value(nodes, node.inputs[0])
        return None if value is None else -value
    if node.kind in {"add", "subtract", "multiply", "divide"}:
        left, right = (constant_value(nodes, item) for item in node.inputs)
        if left is None or right is None:
            return None
        if node.kind == "add":
            return left + right
        if node.kind == "subtract":
            return left - right
        if node.kind == "multiply":
            return left * right
        _require(right != 0, f"Constant division by zero at {node.id}.")
        return left / right
    return None


def _validate_operation(node: BehaviorNode, nodes: Mapping[str, BehaviorNode]) -> None:
    """Validate exact arity, attributes, ownership and semantic types per opcode."""
    k, a, refs = node.kind, node.attributes, node.inputs
    _require(
        k in SUPPORTED_KINDS, f"Unsupported behavior operation {k!r} at {node.id}."
    )
    inputs = [nodes[ref] for ref in refs]
    dtype = TypeSpec.from_dict(node.data_type) if node.data_type else None

    def check(ok: bool, message: str) -> None:
        _require(ok, f"{node.id} ({k}): {message}")

    def fields(required=(), optional=()):
        check(
            not (set(required) - set(a))
            and not (set(a) - set(required) - set(optional)),
            "Invalid operation attributes.",
        )

    def arity(count):
        check(len(refs) == count, f"Expected {count} inputs.")

    def typed(index, expected):
        actual = (
            TypeSpec.from_dict(inputs[index].data_type)
            if inputs[index].data_type
            else None
        )
        check(
            actual is not None
            and (
                actual.kind == expected
                if isinstance(expected, str)
                else actual.compatible(expected)
            ),
            f"Input {index} has an incompatible type.",
        )
        return actual

    def returns(expected):
        check(
            (dtype is None)
            if expected is None
            else (
                dtype is not None
                and (
                    dtype.kind == expected
                    if isinstance(expected, str)
                    else dtype.compatible(expected)
                )
            ),
            "Incompatible result type.",
        )

    def owner(index=0):
        check(
            node.role is not None
            and refs[index] == node.role
            and inputs[index].kind == "role",
            "Invalid owning role input.",
        )

    if k == "role":
        fields(("name", "cell_type", "engineering"))
        arity(0)
        returns(None)
        check(
            node.role is None
            and a["engineering"] == "in_vivo"
            and _named(a["name"])
            and _named(a["cell_type"]),
            "Invalid role declaration.",
        )
        return
    if k in {"literal", "parameter"}:
        arity(0)
        returns("scalar")
        check(node.role is None, "Design constants must be role-free.")
        fields(("value",) if k == "literal" else ("name", "bound", "default"))
        if k == "parameter":
            check(a["bound"] is True, "Behavior parameters must be bound.")
        return
    check(
        node.role is not None
        or k
        in {
            "add",
            "subtract",
            "multiply",
            "divide",
            "negate",
            "compare",
            "and",
            "or",
            "not",
            "at_least",
            "held_for",
            "recently",
            "became_true",
            "followed_by",
            "signature",
        },
        "Operation requires a cell role.",
    )
    check(
        all(other.role in (None, node.role) for other in inputs),
        "Cross-role input is not allowed.",
    )
    if k == "scope":
        fields(("name", "scope"))
        arity(1)
        owner()
        returns(None)
        check(
            a["scope"] in {"contact", "environment", "internal", "external"}
            and a["name"] == a["scope"],
            "Unknown or inconsistent scope.",
        )
    elif k == "signal":
        fields(("name", "scope", "observation"))
        arity(1)
        returns("scalar")
        check(
            inputs[0].kind == "scope"
            and a["scope"] == inputs[0].attributes["scope"]
            and _named(a["name"]),
            "Invalid signal scope.",
        )
        check(
            a["observation"] == "signal"
            or a["observation"] == "marker"
            and a["scope"] == "contact",
            "Invalid observation kind.",
        )
    elif k == "qualitative":
        fields(("band",))
        arity(1)
        returns(BOOLEAN)
        typed(0, "scalar")
        check(
            inputs[0].kind == "signal" and a["band"] in {"present", "high", "low"},
            "Invalid qualitative observation.",
        )
    elif k in {"and", "or", "not", "at_least"}:
        fields(("count",) if k == "at_least" else ())
        if k == "at_least":
            check(
                len(refs) > 0
                and type(a["count"]) is int
                and 0 <= a["count"] <= len(refs),
                "Invalid threshold.",
            )
        else:
            arity(1 if k == "not" else 2)
        returns(BOOLEAN)
        for index in range(len(refs)):
            typed(index, BOOLEAN)
    elif k in {"add", "subtract", "multiply", "divide", "negate", "compare"}:
        fields(("operator",) if k == "compare" else ())
        arity(1 if k == "negate" else 2)
        left = typed(0, "scalar")
        right = typed(1, "scalar") if k != "negate" else left
        if k in {"add", "subtract", "compare"}:
            check(left.compatible(right), "Operand dimensions do not agree.")
        if k == "compare":
            check(
                a["operator"] in {"lt", "le", "gt", "ge", "eq", "ne"},
                "Invalid comparison operator.",
            )
            returns(BOOLEAN)
        else:
            returns(
                left * right
                if k == "multiply"
                else left / right
                if k == "divide"
                else left
            )
    elif k in {"held_for", "recently", "became_true", "followed_by"}:
        attrs = {
            "held_for": {
                "history": "since_initialization",
                "requires_full_interval": True,
            },
            "recently": {"history": "since_initialization", "includes_present": True},
            "became_true": {"initially_true_emits": True},
            "followed_by": {
                "emits_at": "second_event",
                "history": "since_initialization",
            },
        }[k]
        check(_exact(a, attrs), "Unsupported temporal policy.")
        arity(1 if k == "became_true" else 3 if k == "followed_by" else 2)
        typed(0, EVENT if k == "followed_by" else BOOLEAN)
        if k == "followed_by":
            typed(1, EVENT)
        if k != "became_true":
            typed(len(refs) - 1, DURATION)
        returns(EVENT if k in {"became_true", "followed_by"} else BOOLEAN)
    elif k == "memory":
        fields(
            (
                "name",
                "input_names",
                "initial",
                "setting",
                "initial_true_is_onset",
                "reset_priority",
                "expiry",
            )
        )
        returns(BOOLEAN)
        names = a["input_names"]
        check(
            isinstance(names, tuple)
            and names
            in (
                ("owner", "set_when"),
                ("owner", "set_when", "reset_when"),
                ("owner", "set_when", "duration"),
                ("owner", "set_when", "reset_when", "duration"),
            ),
            "Invalid memory inputs.",
        )
        arity(len(names))
        owner()
        typed(1, BOOLEAN)
        check(
            _named(a["name"])
            and a["initial"] is False
            and a["setting"] == "onset"
            and a["initial_true_is_onset"] is True
            and a["reset_priority"] is True,
            "Unsupported memory policy.",
        )
        check(
            a["expiry"]
            == ("latest_setting_onset" if "duration" in names else "until_reset"),
            "Invalid memory expiry policy.",
        )
        for index, name in enumerate(names):
            if name == "reset_when":
                typed(index, BOOLEAN)
            elif name == "duration":
                typed(index, DURATION)
    elif k == "memory.is_set":
        fields()
        arity(1)
        returns(BOOLEAN)
        check(inputs[0].kind == "memory", "Expected memory declaration.")
    elif k == "state":
        fields(("name", "values", "initial", "observation", "arbitration"))
        arity(1)
        owner()
        returns(None)
        values = a["values"]
        check(
            isinstance(values, tuple)
            and len(values) > 0
            and all(type(value) in (str, bool, int, float) for value in values),
            "Invalid state values.",
        )
        keys = [(type(value), value) for value in values]
        check(
            len(set(keys)) == len(keys)
            and (type(a["initial"]), a["initial"]) in keys
            and _named(a["name"]),
            "Invalid state initialization.",
        )
        check(
            a["observation"] == "shared_pre_update_state"
            and a["arbitration"] == "coalesce_identical_else_error",
            "Unsupported state policy.",
        )
    elif k in {"state.is", "action.state_set"}:
        fields(("value",) if k == "state.is" else ("value", "idempotent", "ongoing"))
        arity(1)
        check(inputs[0].kind == "state", "Expected state declaration.")
        check(
            any(
                type(a["value"]) is type(value) and a["value"] == value
                for value in inputs[0].attributes["values"]
            ),
            "Undeclared state value.",
        )
        returns(BOOLEAN if k == "state.is" else None)
        if k == "action.state_set":
            check(
                a["idempotent"] is True and a["ongoing"] is False,
                "Unsupported assignment policy.",
            )
    elif k == "signature":
        fields(("definition", "bindings"))
        check(len(refs) > 0, "Signature requires an expression.")
        typed(0, BOOLEAN)
        returns(BOOLEAN)
        definition = a["definition"]
        check(
            isinstance(definition, Mapping)
            and set(definition) == {"name", "module", "qualname"}
            and all(_named(value) for value in definition.values()),
            "Invalid signature identity.",
        )
        check(isinstance(a["bindings"], Mapping), "Invalid signature bindings.")

        def validate_binding(value):
            if isinstance(value, Mapping):
                if set(value) == {"input"}:
                    check(
                        type(value["input"]) is int and 1 <= value["input"] < len(refs),
                        "Invalid signature input reference.",
                    )
                elif set(value) != {"literal"}:
                    for item in value.values():
                        validate_binding(item)
            elif isinstance(value, tuple):
                for item in value:
                    validate_binding(item)
            else:
                check(False, "Invalid signature binding descriptor.")

        for value in a["bindings"].values():
            validate_binding(value)
    elif k == "secretion":
        fields(("name", "product", "default", "activity"))
        arity(1)
        owner()
        returns(None)
        check(
            _named(a["name"])
            and _named(a["product"])
            and type(a["default"]) is bool
            and a["activity"] == "requires_rule_or_controller",
            "Invalid secretion declaration.",
        )
    elif k == "rule":
        fields(
            (
                "trigger",
                "execution",
                "priority",
                "ongoing_activation",
                "impulse_activation",
                "state_assignment",
            ),
            ("name", "ongoing_duration"),
        )
        check(len(refs) >= 3, "Rule needs a trigger and actions.")
        owner()
        returns(None)
        trigger = a["trigger"]
        check(trigger in {"condition", "event"}, "Invalid rule trigger.")
        typed(1, BOOLEAN if trigger == "condition" else EVENT)
        check(
            a["execution"] == "concurrent" and a["priority"] == "none",
            "Unsupported rule concurrency.",
        )
        check(
            a["ongoing_activation"]
            == ("level" if trigger == "condition" else "explicit_duration")
            and a["impulse_activation"]
            == ("onset" if trigger == "condition" else "event")
            and a["state_assignment"]
            == ("level" if trigger == "condition" else "event"),
            "Invalid rule activation policies.",
        )
        check(
            ("ongoing_duration" not in a)
            if trigger == "condition"
            else a.get("ongoing_duration") == "explicit",
            "Invalid event duration policy.",
        )
        check("name" not in a or _named(a["name"]), "Invalid rule name.")
        for action in inputs[2:]:
            check(action.kind.startswith("action."), "Rule input must be an action.")
            check(
                trigger != "event"
                or not action.attributes.get("ongoing")
                or action.kind == "action.pulse",
                "Event-triggered ongoing actions require explicit duration.",
            )
    elif k == "action.pulse":
        fields(("ongoing", "retrigger"))
        arity(2)
        returns(None)
        typed(1, DURATION)
        check(
            inputs[0].kind.startswith("action.")
            and inputs[0].kind != "action.pulse"
            and inputs[0].attributes.get("ongoing") is True,
            "Pulse requires a primitive ongoing action.",
        )
        check(
            a["ongoing"] is True and a["retrigger"] == "extend_from_latest_trigger",
            "Unsupported pulse policy.",
        )
    elif k == "action.secrete":
        fields(("ongoing", "rate"))
        returns(None)
        check(a["rate"] in {"unspecified", "expression"}, "Invalid rate mode.")
        arity(1 if a["rate"] == "unspecified" else 2)
        check(
            inputs[0].kind == "secretion" and a["ongoing"] is True,
            "Invalid secretion action.",
        )
        if len(refs) == 2:
            typed(1, PRODUCTION_RATE)
    else:
        extra = {
            "action.report": "label",
            "action.present": "antigen",
            "action.differentiate": "phenotype",
        }.get(k)
        fields(
            ("ongoing", extra) if extra else ("ongoing",),
            ("location",) if k == "action.retain" else (),
        )
        returns(None)
        check(a["ongoing"] is (k != "action.report"), "Invalid action duration class.")
        arity(
            2
            if k in {"action.eliminate", "action.engulf"}
            or k == "action.retain"
            and "location" not in a
            else 1
        )
        owner()
        if extra:
            check(_named(a[extra]), "Invalid action label.")
        if len(refs) == 2:
            check(inputs[1].kind == "scope", "Expected target scope.")
            if k in {"action.eliminate", "action.engulf"}:
                check(
                    inputs[1].attributes["scope"] == "contact",
                    "Action requires contacted object.",
                )
        if "location" in a:
            check(_named(a["location"]), "Invalid location.")


@dataclass(frozen=True)
class BehaviorProgram:
    name: str
    nodes: tuple[BehaviorNode, ...]
    roots: tuple[str, ...]
    source_fingerprint: str
    requirements: tuple[BehaviorRequirement, ...]
    source_links: Mapping[str, tuple[str, ...]]
    policies: Mapping[str, Any] = field(default_factory=lambda: EXECUTION_POLICIES)
    parameter_bindings: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require(self.schema_version == SCHEMA_VERSION, "Unsupported behavior schema.")
        _require(
            isinstance(self.nodes, (tuple, list))
            and all(isinstance(node, BehaviorNode) for node in self.nodes),
            "Behavior nodes must be BehaviorNode records.",
        )
        object.__setattr__(self, "nodes", tuple(self.nodes))
        # Reuse graph reference/cycle validation; operation validation below is stricter.
        graph = IntentProgram(
            self.name,
            tuple(
                IntentNode(
                    node.id,
                    node.kind,
                    node.inputs,
                    node.attributes,
                    node.data_type,
                    node.role,
                    node.source,
                )
                for node in self.nodes
            ),
            self.roots,
        )
        object.__setattr__(self, "roots", graph.roots)
        _require(
            isinstance(self.source_fingerprint, str)
            and len(self.source_fingerprint) == 64
            and all(c in "0123456789abcdef" for c in self.source_fingerprint),
            "Source fingerprint must be SHA-256 hex.",
        )
        _require(
            isinstance(self.policies, Mapping),
            "Unknown or modified execution policies.",
        )
        object.__setattr__(self, "policies", freeze_json(self.policies))
        _require(
            _exact(self.policies, EXECUTION_POLICIES),
            "Unknown or modified execution policies.",
        )
        _require(
            isinstance(self.parameter_bindings, Mapping),
            "Parameter bindings must be an object.",
        )
        object.__setattr__(
            self, "parameter_bindings", freeze_json(self.parameter_bindings)
        )
        _require(
            isinstance(self.requirements, (tuple, list))
            and all(isinstance(req, BehaviorRequirement) for req in self.requirements),
            "Invalid requirement records.",
        )
        object.__setattr__(self, "requirements", tuple(self.requirements))
        _require(
            isinstance(self.source_links, Mapping)
            and all(
                isinstance(value, (tuple, list)) and all(_named(item) for item in value)
                for value in self.source_links.values()
            ),
            "Source links must map node ids to lineage arrays.",
        )
        object.__setattr__(self, "source_links", freeze_json(self.source_links))
        try:
            self._validate()
        except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, SerializationError):
                raise
            raise SerializationError(f"Invalid behavior operation: {exc}") from exc

    def _validate(self) -> None:
        nodes = {node.id: node for node in self.nodes}
        for node in self.nodes:
            _validate_operation(node, nodes)
        bindings = contact_bindings(nodes)
        for node in self.nodes:
            _require(
                node.contact_bound == bindings[node.id],
                f"Incorrect contact binding at {node.id}.",
            )
            if node.kind in {
                "literal",
                "parameter",
                "add",
                "subtract",
                "multiply",
                "divide",
                "negate",
            }:
                value = constant_value(nodes, node.id)
                _require(
                    value is None or math.isfinite(value),
                    f"Non-finite constant at {node.id}.",
                )
            duration_ref = None
            if node.kind in {"held_for", "recently", "action.pulse"}:
                duration_ref = node.inputs[1]
            elif node.kind == "followed_by":
                duration_ref = node.inputs[2]
            elif node.kind == "memory" and "duration" in node.attributes["input_names"]:
                duration_ref = node.inputs[
                    node.attributes["input_names"].index("duration")
                ]
            if duration_ref is not None:
                value = constant_value(nodes, duration_ref)
                _require(
                    value is not None and math.isfinite(value) and value > 0,
                    f"Duration at {node.id} must be a positive design-time constant.",
                )
        declarations = {
            node.id
            for node in self.nodes
            if node.kind
            in {"role", "parameter", "memory", "state", "secretion", "rule"}
        }
        _require(
            set(self.roots) == declarations,
            "Behavior roots must include exactly all executable declarations.",
        )
        expected_links = {node.id: lineage_for(nodes, node.id) for node in self.nodes}
        _require(
            dict(self.source_links) == expected_links,
            "Incomplete or inconsistent source lineage.",
        )
        expected_reqs = tuple(
            BehaviorRequirement(
                f"requirement:{node.id}",
                node.kind,
                node.id,
                expected_links[node.id],
                node.source,
            )
            for node in self.nodes
            if node.kind in {"rule", "state", "memory"}
        )
        _require(
            self.requirements == expected_reqs,
            "Requirements must preserve every rule, state and memory declaration.",
        )
        for node in self.nodes:
            expected_ids = tuple(
                req.id for req in self.requirements if node.id in req.lineage
            )
            _require(
                node.requirement_ids == expected_ids,
                f"Incorrect requirement mapping at {node.id}.",
            )
        expected_parameters = {
            node.attributes["name"]: node.attributes["default"]
            for node in self.nodes
            if node.kind == "parameter"
        }
        _require(
            _exact(self.parameter_bindings, expected_parameters),
            "Parameter bindings disagree with the executable graph.",
        )

    def get(self, node_id: str) -> BehaviorNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def find(
        self, *, kind: str | None = None, role: str | None = None
    ) -> tuple[BehaviorNode, ...]:
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
            "source_fingerprint": self.source_fingerprint,
            "requirements": [
                req.to_dict(include_source=include_source) for req in self.requirements
            ],
            "source_links": thaw_json(self.source_links),
            "policies": thaw_json(self.policies),
            "parameter_bindings": thaw_json(self.parameter_bindings),
        }

    def to_json(self, *, indent: int | None = 2, include_source: bool = True) -> str:
        return json.dumps(
            self.to_dict(include_source=include_source),
            sort_keys=True,
            indent=indent,
            ensure_ascii=False,
            allow_nan=False,
        )

    @property
    def fingerprint(self) -> str:
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
            "requirements": len(self.requirements),
            "kinds": dict(sorted(counts.items())),
            "fingerprint": self.fingerprint,
            "source_fingerprint": self.source_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> BehaviorProgram:
        fields = {
            "schema_version",
            "name",
            "nodes",
            "roots",
            "source_fingerprint",
            "requirements",
            "source_links",
            "policies",
            "parameter_bindings",
        }
        _require(
            isinstance(data, Mapping) and set(data) == fields,
            "Invalid behavior program fields.",
        )
        _require(
            isinstance(data["nodes"], (tuple, list))
            and isinstance(data["requirements"], (tuple, list)),
            "Nodes and requirements must be arrays.",
        )
        return cls(
            name=data["name"],
            nodes=tuple(BehaviorNode.from_dict(node) for node in data["nodes"]),
            roots=data["roots"],
            source_fingerprint=data["source_fingerprint"],
            requirements=tuple(
                BehaviorRequirement.from_dict(req) for req in data["requirements"]
            ),
            source_links=data["source_links"],
            policies=data["policies"],
            parameter_bindings=data["parameter_bindings"],
            schema_version=data["schema_version"],
        )

    @classmethod
    def from_json(cls, text: str) -> BehaviorProgram:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                _require(key not in result, f"Duplicate JSON key: {key}.")
                result[key] = value
            return result

        def invalid(value):
            raise SerializationError(f"Invalid JSON number: {value}.")

        try:
            data = json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
        except (TypeError, json.JSONDecodeError, RecursionError) as exc:
            raise SerializationError(f"Invalid behavior JSON: {exc}") from exc
        return cls.from_dict(data)
