"""Complete source execution authority for supplied multi-node realizations.

This is a manifest of the existing intent/Behavior language, not another source
language or molecular simulator. State, arithmetic, temporal control and channel
requests retain original identities. Selected implementations must separately
bind these semantics to complete supplied construction authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.ir.behavior import BehaviorProgram, BEHAVIOR_V2
from biocompiler.ir.implementation_requirements import SOURCE_TYPES, MAX_SOURCE_NODES, source_request_from_dict
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.semantics.payload_requirements import (
    PayloadDiagnostic, PayloadOutputRequirement, _output_requirements, source_build_request,
)

PROFILE_VERSION = "biocompiler.source_execution_manifest.v0.1"
CLAIM_SCOPE = "exact_declared_source_execution_no_empirical_function"


@dataclass(frozen=True)
class SourceExecutionManifest(JsonArtifact):
    source: object
    behavior: BehaviorProgram | None
    roles: tuple[str, ...]
    outputs: tuple[PayloadOutputRequirement, ...]
    ledger: tuple[Mapping, ...]
    role_nodes: Mapping[str, tuple[str, ...]]
    states: tuple[Mapping, ...]
    channels: tuple[Mapping, ...]
    diagnostics: tuple[PayloadDiagnostic, ...]
    schema_version: ClassVar[str] = PROFILE_VERSION

    def __post_init__(self):
        require(isinstance(self.source, SOURCE_TYPES), "Source execution requires complete frozen source authority.")
        require(self.behavior is None or isinstance(self.behavior, BehaviorProgram), "Invalid executable source Behavior.")
        require(isinstance(self.roles, (tuple, list)) and len(self.roles) <= MAX_SOURCE_NODES
                and all(isinstance(item, str) for item in self.roles), "Invalid source role inventory.")
        object.__setattr__(self, "roles", tuple(self.roles))
        require(isinstance(self.role_nodes, Mapping), "Invalid per-role source inventory.")
        object.__setattr__(self, "role_nodes", freeze_json(self.role_nodes))
        for key, record in (("outputs", PayloadOutputRequirement), ("diagnostics", PayloadDiagnostic)):
            values = getattr(self, key)
            require(isinstance(values, (tuple, list)) and len(values) <= 4 * MAX_SOURCE_NODES
                    and all(isinstance(item, record) for item in values), "Invalid execution manifest records.")
            object.__setattr__(self, key, tuple(values))
        for key in ("ledger", "states", "channels"):
            values = getattr(self, key)
            require(isinstance(values, (tuple, list)) and len(values) <= MAX_SOURCE_NODES + 1
                    and all(isinstance(item, Mapping) for item in values), "Invalid retained source ledger.")
            object.__setattr__(self, key, tuple(freeze_json(item) for item in values))

    @property
    def build_request(self):
        return source_build_request(self.source)

    @property
    def source_fingerprint(self):
        return self.source.fingerprint

    @property
    def complete(self):
        return self.behavior is not None and not self.diagnostics

    def to_dict(self):
        return {
            "schema_version": self.schema_version, "claim_scope": CLAIM_SCOPE,
            "source": self.source.to_dict(),
            "behavior": self.behavior.to_dict() if self.behavior is not None else None,
            "roles": list(self.roles), "outputs": [item.to_dict() for item in self.outputs],
            "ledger": thaw_json(self.ledger), "role_nodes": thaw_json(self.role_nodes),
            "states": thaw_json(self.states), "channels": thaw_json(self.channels),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, {"schema_version", "claim_scope", "source", "behavior", "roles", "outputs",
                      "ledger", "role_nodes", "states", "channels", "diagnostics"}, "source execution manifest")
        require(data["schema_version"] == PROFILE_VERSION and data["claim_scope"] == CLAIM_SCOPE,
                "Unsupported source execution manifest profile.")
        for key in ("outputs", "diagnostics", "ledger", "states", "channels"):
            require(isinstance(data[key], (tuple, list)) and len(data[key]) <= 4 * MAX_SOURCE_NODES,
                    "Execution manifest inventory limit exceeded.")
        # Historical imports are structural. Independent verification must
        # reconstruct expected source authority without invoking this producer.
        return cls(source_request_from_dict(data["source"]),
                   BehaviorProgram.from_dict(data["behavior"]) if data["behavior"] is not None else None,
                   data["roles"], tuple(PayloadOutputRequirement.from_dict(item) for item in data["outputs"]),
                   data["ledger"], data["role_nodes"], data["states"], data["channels"],
                   tuple(PayloadDiagnostic.from_dict(item) for item in data["diagnostics"]))


def derive_source_execution(source):
    """Retain the whole original program and resolve only its chosen profile."""
    require(isinstance(source, SOURCE_TYPES), "Expected original frozen source request.")
    source = source_request_from_dict(source.to_dict())
    build = source_build_request(source)
    require(len(build.intent.nodes) <= MAX_SOURCE_NODES, "Executable source node limit exceeded.")
    nodes = {node.id: node for node in build.intent.nodes}
    roles = tuple(node.id for node in build.intent.find(kind="role"))
    outputs = _output_requirements(build)
    diagnostics, behavior = [], None
    try:
        behavior = lower_to_behavior(build)
    except UnsupportedBehaviorError as error:
        diagnostics.append(PayloadDiagnostic("source_execution_profile_unsupported", "unsupported_semantics",
                                             (error.node_id,) if error.node_id else (), str(error)))
    except SerializationError as error:
        diagnostics.append(PayloadDiagnostic("invalid_source_execution_semantics", "contradiction", (), str(error)))
    constraints = set(build.implementation_constraints)
    if build.behavior_profile == BEHAVIOR_V2:
        constraints.discard("execution")
    if constraints:
        diagnostics.append(PayloadDiagnostic("uninterpreted_implementation_constraints", "unsupported_semantics", (),
                                             "Retained implementation constraints require interpretation: " + ", ".join(sorted(constraints))))
    if build.preferences:
        diagnostics.append(PayloadDiagnostic("uninterpreted_source_preferences", "unsupported_semantics", (),
                                             "Original source preferences require a declared ranking interpretation."))
    if not isinstance(source, type(build)):
        diagnostics.append(PayloadDiagnostic("wrapped_source_obligations", "missing_refinement", (),
                                             "Wrapped deployment and acceptance obligations remain separate from executable source semantics."))
    ledger = tuple({"id": "source:" + node.id, "kind": node.kind, "source_node_ids": [node.id],
                    "semantics": node.to_dict(include_source=False)} for node in nodes.values()) + (
                        {"id": "source:complete_authority", "kind": "source_authority",
                         "source_node_ids": list(nodes), "semantics": source.to_dict()},)
    role_nodes = {role: tuple(node.id for node in nodes.values() if node.role in (None, role)) for role in roles}
    states = tuple({
        "id": node.id, "declaration": node.to_dict(include_source=False),
        "assignments": [
            {"output_id": output.id, "rule_id": output.rule_id, "action_id": output.action_id,
             "guard_id": output.guard_id, "value": thaw_json(output.semantics["primitive_action"]["attributes"]["value"])}
            for output in outputs if output.action_kind == "action.state_set"
            and output.semantics["primitive_action"]["inputs"][0] == node.id
        ],
    } for node in nodes.values() if node.kind == "state")
    channels = tuple({
        "id": node.id, "declaration": node.to_dict(include_source=False),
        "senders": [
            {"output_id": output.id, "role_id": output.role_id, "rule_id": output.rule_id,
             "action_id": output.action_id,
             "value_id": output.semantics["primitive_action"]["inputs"][2]
             if len(output.semantics["primitive_action"]["inputs"]) == 3 else None}
            for output in outputs if output.action_kind == "action.emit"
            and output.semantics["primitive_action"]["inputs"][1] == node.id
        ],
        "receivers": [{"observation_id": item.id, "role_id": item.role}
                      for item in nodes.values() if item.kind == "channel_observation" and item.inputs[1] == node.id],
        "transport": "requires_explicit_architecture_contract",
    } for node in nodes.values() if node.kind == "channel")
    return SourceExecutionManifest(source, behavior, roles, outputs, ledger, role_nodes,
                                   states, channels, tuple(diagnostics))
