"""Source-authoritative executable requirements for supplied payload contracts.

The digital graph describes requested activation, not a molecular mechanism or
an admission decision. Original actions, wrappers, and unsupported requirements
remain authoritative. No target, physiological observation, or sequence is inferred.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import ClassVar

from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.ir.behavior import BehaviorProgram, SUPPORTED_KINDS, lineage_for
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.circuit_logic import BooleanSpec, CircuitSignal
from biocompiler.ir.implementation_requirements import (
    MAX_SOURCE_NODES, SOURCE_TYPES, source_request_from_dict,
)
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.types import BOOLEAN, DURATION, TypeSpec, decode_binding
from biocompiler.verification.realization import InputBinding, ObservationMap, OutputBinding

PROFILE_VERSION = "biocompiler.payload_requirements.v0.1"
CLAIM_SCOPE = "source_semantics_under_declared_contracts_no_empirical_function"
_DIGITAL_EXPRESSIONS = frozenset({
    "qualitative", "signal", "literal", "parameter", "signature", "and", "or",
    "not", "compare", "held_for", "became_true", "memory", "memory.is_set",
})


def _decode_source(data):
    if data.get("schema_version") == CircuitRequest.schema_version:
        return CircuitRequest.from_dict(thaw_json(data))
    return source_request_from_dict(data)


def source_build_request(source):
    """Retain the original target while finding the complete source program."""
    if isinstance(source, CircuitRequest):
        source = source.profile.source_request
    require(isinstance(source, SOURCE_TYPES), "Payload compilation requires original source authority.")
    return source if isinstance(source, BuildRequest) else source.build_request


@dataclass(frozen=True)
class PayloadDiagnostic(JsonArtifact):
    code: str
    category: str
    source_node_ids: tuple[str, ...]
    message: str

    def __post_init__(self):
        require(isinstance(self.category, str) and self.category in {"unsupported_semantics", "missing_refinement", "contradiction"},
                "Invalid payload diagnostic category.")
        require(isinstance(self.code, str) and bool(self.code)
                and isinstance(self.message, str) and bool(self.message), "Diagnostic text is required.")
        require(isinstance(self.source_node_ids, (tuple, list))
                and len(self.source_node_ids) <= MAX_SOURCE_NODES
                and all(isinstance(item, str) and bool(item) for item in self.source_node_ids),
                "Diagnostic source references must be a bounded array of identities.")
        object.__setattr__(self, "source_node_ids", tuple(self.source_node_ids))

    def to_dict(self):
        return {"code": self.code, "category": self.category,
                "source_node_ids": list(self.source_node_ids), "message": self.message}

    @classmethod
    def from_dict(cls, data):
        fields(data, {"code", "category", "source_node_ids", "message"}, "payload diagnostic")
        return cls(**data)


@dataclass(frozen=True)
class PayloadOutputRequirement(JsonArtifact):
    """One installed action, preserving action identity separately from activation."""
    id: str
    rule_id: str
    action_id: str
    guard_id: str
    role_id: str
    action_kind: str
    lineage: tuple[str, ...]
    trigger: str
    activation: str
    product: str | None
    semantics: Mapping

    def __post_init__(self):
        for key in ("id", "rule_id", "action_id", "guard_id", "role_id", "action_kind"):
            require(isinstance(getattr(self, key), str) and bool(getattr(self, key)),
                    "Output identities must be nonempty strings.")
        require(isinstance(self.trigger, str) and self.trigger in {"condition", "event"}, "Invalid output trigger.")
        require(isinstance(self.activation, str) and self.activation in {"level", "event", "onset", "explicit_duration"},
                "Invalid output activation.")
        require(self.product is None or isinstance(self.product, str), "Invalid product identity.")
        require(isinstance(self.lineage, (tuple, list)) and all(isinstance(item, str) for item in self.lineage),
                "Output lineage must be an array of source identities.")
        require(isinstance(self.semantics, Mapping), "Output semantics must be an object.")
        object.__setattr__(self, "lineage", tuple(self.lineage))
        object.__setattr__(self, "semantics", freeze_json(self.semantics))

    def to_dict(self):
        return {key: thaw_json(getattr(self, key)) for key in (
            "id", "rule_id", "action_id", "guard_id", "role_id", "action_kind",
            "lineage", "trigger", "activation", "product", "semantics",
        )}


    @classmethod
    def from_dict(cls, data):
        fields(data, {"id", "rule_id", "action_id", "guard_id", "role_id", "action_kind",
                      "lineage", "trigger", "activation", "product", "semantics"}, "payload output")
        return cls(**data)


@dataclass(frozen=True)
class PayloadRequirements(JsonArtifact):
    source: object
    behavior: BehaviorProgram | None
    outputs: tuple[PayloadOutputRequirement, ...]
    requirements: tuple[Mapping, ...]
    diagnostics: tuple[PayloadDiagnostic, ...]
    mechanism: MechanismProgram | None
    observation_map: ObservationMap
    source_map: Mapping[str, tuple[str, ...]]
    schema_version: ClassVar[str] = PROFILE_VERSION

    def __post_init__(self):
        require(isinstance(self.source, (*SOURCE_TYPES, CircuitRequest)), "Invalid payload source.")
        require(self.behavior is None or isinstance(self.behavior, BehaviorProgram), "Invalid payload behavior.")
        require(self.mechanism is None or isinstance(self.mechanism, MechanismProgram), "Invalid payload graph.")
        require(isinstance(self.observation_map, ObservationMap), "Invalid payload observation map.")
        for key, record in (("outputs", PayloadOutputRequirement), ("diagnostics", PayloadDiagnostic)):
            require(isinstance(getattr(self, key), (tuple, list))
                    and len(getattr(self, key)) <= 4 * MAX_SOURCE_NODES
                    and all(isinstance(item, record) for item in getattr(self, key)), "Invalid payload records.")
            object.__setattr__(self, key, tuple(getattr(self, key)))
        require(isinstance(self.requirements, (tuple, list))
                and len(self.requirements) <= MAX_SOURCE_NODES + 1
                and all(isinstance(item, Mapping) for item in self.requirements), "Invalid retained requirements.")
        require(isinstance(self.source_map, Mapping) and len(self.source_map) <= 4 * MAX_SOURCE_NODES,
                "Invalid source map.")
        require(all(isinstance(key, str) and isinstance(value, (tuple, list))
                    and len(value) <= MAX_SOURCE_NODES and all(isinstance(ref, str) for ref in value)
                    for key, value in self.source_map.items()), "Invalid source lineage.")
        object.__setattr__(self, "requirements", tuple(freeze_json(item) for item in self.requirements))
        object.__setattr__(self, "source_map", freeze_json(self.source_map))

    @property
    def build_request(self):
        return source_build_request(self.source)

    @property
    def source_fingerprint(self):
        return self.source.fingerprint

    @property
    def unsupported(self):
        return tuple(item for item in self.diagnostics if item.category == "unsupported_semantics")

    def to_dict(self):
        return {"schema_version": self.schema_version, "claim_scope": CLAIM_SCOPE,
                "source": self.source.to_dict(),
                "behavior": self.behavior.to_dict() if self.behavior else None,
                "outputs": [item.to_dict() for item in self.outputs],
                "requirements": thaw_json(self.requirements),
                "diagnostics": [item.to_dict() for item in self.diagnostics],
                "mechanism": self.mechanism.to_dict() if self.mechanism else None,
                "observation_map": self.observation_map.to_dict(),
                "source_map": thaw_json(self.source_map)}

    @classmethod
    def from_dict(cls, data):
        fields(data, {"schema_version", "claim_scope", "source", "behavior", "outputs",
                      "requirements", "diagnostics", "mechanism", "observation_map", "source_map"},
               "payload requirements")
        require(data["schema_version"] == PROFILE_VERSION and data["claim_scope"] == CLAIM_SCOPE,
                "Unsupported payload requirements profile.")
        for key, maximum in (("outputs", 4 * MAX_SOURCE_NODES), ("diagnostics", 4 * MAX_SOURCE_NODES),
                             ("requirements", MAX_SOURCE_NODES + 1)):
            require(isinstance(data[key], (tuple, list)) and len(data[key]) <= maximum,
                    "Payload record inventory limit exceeded.")
        # Parsing is deliberately structural: an imported analysis is historical,
        # and cannot call its producer to supply the verifier's expected values.
        return cls(_decode_source(data["source"]),
                   BehaviorProgram.from_dict(data["behavior"]) if data["behavior"] is not None else None,
                   tuple(PayloadOutputRequirement.from_dict(item) for item in data["outputs"]),
                   data["requirements"],
                   tuple(PayloadDiagnostic.from_dict(item) for item in data["diagnostics"]),
                   MechanismProgram.from_dict(data["mechanism"]) if data["mechanism"] is not None else None,
                   ObservationMap.from_dict(data["observation_map"]), data["source_map"])


def _output_requirements(build):
    nodes = {node.id: node for node in build.intent.nodes}
    outputs = []
    for rule in build.intent.find(kind="rule"):
        require(len(rule.inputs) >= 3, "Source rule requires guard and action.")
        for action_id in rule.inputs[2:]:
            action = nodes[action_id]
            primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
            product = None
            if primitive.kind == "action.secrete" and primitive.inputs:
                product = nodes[primitive.inputs[0]].attributes.get("product")
            trigger = rule.attributes.get("trigger")
            activation = ("explicit_duration" if action.kind == "action.pulse" else
                          "level" if primitive.attributes.get("ongoing") else
                          "event" if trigger == "event" else "onset")
            outputs.append(PayloadOutputRequirement(
                f"output:{rule.id}:{action.id}", rule.id, action.id, rule.inputs[1],
                rule.role, primitive.kind, lineage_for(nodes, rule.id), trigger,
                activation, product,
                {"action": action.to_dict(include_source=False),
                 "primitive_action": primitive.to_dict(include_source=False),
                 "dependencies": [nodes[ref].to_dict(include_source=False)
                                  for ref in lineage_for(nodes, action.id)]},
            ))
    return tuple(outputs)


def _digital_graph(behavior, outputs):
    """Compile activation only; each selected output still needs its action contract."""
    nodes = {node.id: node for node in behavior.nodes}
    roles = behavior.find(kind="role")
    if len(roles) != 1:
        raise UnsupportedBehaviorError("Executable payload graph currently requires one recipient role.")
    role = roles[0].id
    generated, source_map, cache, bindings = {}, {}, {}, {}
    outputs_by_id = {item.id: item for item in outputs}

    def reject(node, message):
        raise UnsupportedBehaviorError(message, node_id=node.id, source=node.source)

    def add(identity, kind, scope, refs, inputs=(), attributes=None, dtype=BOOLEAN):
        lineage = tuple(sorted({ancestor for ref in refs for ancestor in behavior.source_links[ref]}))
        requirement_ids = tuple(item.id for item in outputs if set(refs) & set(item.lineage))
        generated[identity] = MechanismNode(
            identity, kind, Observable(identity, dtype, role, scope, "abstract"),
            tuple(inputs), attributes or {}, requirement_ids,
        )
        source_map[identity] = lineage
        return identity

    def merge_source(identity, ref):
        # Coalescing equal observations/forwarded expressions must retain every
        # original output requirement that names a contributing source node.
        # Do not intersect complete ancestry here: shared role ancestors would
        # spuriously attribute unrelated output requirements to every node.
        source_map[identity] = tuple(sorted(set(source_map[identity]) | set(behavior.source_links[ref])))
        attributed = set(generated[identity].requirement_ids)
        attributed.update(item.id for item in outputs if ref in item.lineage)
        generated[identity] = replace(generated[identity], requirement_ids=tuple(
            item.id for item in outputs if item.id in attributed))

    def aggregate(ref, identity, source):
        return ref if generated[ref].scope == "cell" else add(identity, "any_contact", "cell", (source,), (ref,))

    def duration(ref):
        node = nodes[ref]
        if node.kind not in {"literal", "parameter"}:
            reject(node, "Digital duration requires a supplied literal or bound parameter.")
        return decode_binding(node.attributes["value" if node.kind == "literal" else "default"], DURATION).to_dict()

    def expression(ref):
        if ref in cache:
            return cache[ref]
        node = nodes[ref]
        scope = "contact" if node.contact_bound else "cell"
        identity = f"expression:{ref}"
        if node.kind in {"qualitative", "signal"}:
            signal_id, field = ((node.inputs[0], node.attributes["band"])
                                if node.kind == "qualitative" else (ref, "value"))
            key = (signal_id, field)
            identity = f"input:{signal_id}:{field}"
            if key not in bindings:
                dtype = BOOLEAN if field != "value" else TypeSpec.from_dict(node.data_type)
                add(identity, "input", scope, (ref,), dtype=dtype)
                bindings[key] = InputBinding(signal_id, field, identity)
            else:
                merge_source(identity, ref)
        elif node.kind in {"signature", "memory.is_set"}:
            identity = expression(node.inputs[0])
            merge_source(identity, ref)
        elif node.kind in {"literal", "parameter"}:
            add(identity, "constant", "cell", (ref,), attributes={"value": node.attributes[
                "value" if node.kind == "literal" else "default"]}, dtype=TypeSpec.from_dict(node.data_type))
        elif node.kind in {"and", "or", "not", "compare"}:
            add(identity, node.kind, scope, (ref,), tuple(expression(item) for item in node.inputs),
                {"operator": node.attributes["operator"]} if node.kind == "compare" else None)
        elif node.kind in {"held_for", "became_true"}:
            add(identity, "held_for" if node.kind == "held_for" else "onset", scope, (ref,),
                (expression(node.inputs[0]),),
                {"duration": duration(node.inputs[1])} if node.kind == "held_for" else None)
        elif node.kind == "memory":
            controls = dict(zip(node.attributes["input_names"], node.inputs))
            setting = expression(controls["set_when"])
            event = add(f"memory_onset:{ref}", "onset", generated[setting].scope, (ref,), (setting,))
            setting = aggregate(event, f"memory_set:{ref}", ref)
            reset = (aggregate(expression(controls["reset_when"]), f"memory_reset:{ref}", ref)
                     if "reset_when" in controls else
                     add(f"memory_reset:{ref}", "constant", "cell", (ref,), attributes={"value": False}))
            add(identity, "memory", "cell", (ref,), (setting, reset),
                {"duration": duration(controls["duration"]) if "duration" in controls else None})
        else:
            reject(node, f"Operation {node.kind!r} has no executable supplied-contract graph translation.")
        cache[ref] = identity
        return identity

    for memory in behavior.find(kind="memory"):
        expression(memory.id)
    for output in outputs:
        rule, action = nodes[output.rule_id], nodes[output.action_id]
        primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
        if not primitive.attributes.get("ongoing") or primitive.kind == "action.state_set":
            reject(action, "Impulse and finite-state outputs require an additional executable output contract.")
        if primitive.kind == "action.secrete" and primitive.attributes.get("rate") != "unspecified":
            reject(action, "Quantitative secretion rate remains an explicit unsupported requirement.")
        if primitive.kind == "action.retain" and "location" not in primitive.attributes:
            reject(action, "Scope-valued retention requires an explicit target effect contract; the original scope remains retained.")
        scope = "contact" if action.contact_bound else "cell"
        guard = expression(output.guard_id)
        if scope == "cell":
            guard = aggregate(guard, f"aggregate:{output.id}", rule.id)
        if action.kind == "action.pulse":
            if rule.attributes["trigger"] == "condition":
                guard = add(f"pulse_onset:{output.id}", "onset", scope, (rule.id, action.id), (guard,))
            guard = add(f"pulse:{output.id}", "pulse", scope, (rule.id, action.id), (guard,),
                        {"duration": duration(action.inputs[1])})
        add(output.id, "output", scope, (rule.id, action.id), (guard,))
    if not outputs_by_id:
        raise UnsupportedBehaviorError("Executable payload graph requires installed output actions.")
    mechanism = MechanismProgram(behavior.name + ".payload_contracts",
                                 tuple(generated[key] for key in sorted(generated)), tuple(outputs_by_id))
    return mechanism, ObservationMap(tuple(bindings[key] for key in sorted(bindings)),
                                    tuple(OutputBinding(item.id, item.id) for item in outputs)), source_map


def extract_payload_requirements(source):
    """Derive source activation and retain every unimplemented obligation explicitly."""
    require(isinstance(source, (*SOURCE_TYPES, CircuitRequest)), "Expected frozen source authority.")
    source = _decode_source(source.to_dict())
    build = source_build_request(source)
    require(len(build.intent.nodes) <= MAX_SOURCE_NODES, "Payload source node limit exceeded.")
    outputs = _output_requirements(build)
    requirements, diagnostics = [], []
    for node in build.intent.nodes:
        requirements.append({"id": "source:" + node.id, "kind": node.kind,
                             "source_node_ids": [node.id], "semantics": node.to_dict(include_source=False)})
        if node.kind not in SUPPORTED_KINDS:
            diagnostics.append(PayloadDiagnostic("unsupported_source_operation", "unsupported_semantics", (node.id,),
                                                 f"Retained source operation {node.kind!r} requires another execution profile."))
    # Preserve every request wrapper, including target, acceptance, and future
    # fields. Retention is not satisfaction of its deployment/clinical obligations.
    source_data = source.to_dict()
    requirements.append({"id": "source:complete_authority", "kind": "source_authority",
                         "source_node_ids": [node.id for node in build.intent.nodes], "semantics": source_data})
    for key in ("implementation_constraints", "preferences"):
        if getattr(build, key):
            diagnostics.append(PayloadDiagnostic("uninterpreted_" + key, "unsupported_semantics", (),
                                                 f"Frozen {key} are retained and require explicit interpretation."))
    if not isinstance(source, BuildRequest):
        diagnostics.append(PayloadDiagnostic("wrapped_contracts_retained", "missing_refinement", (),
                                             "Source wrapper obligations remain independent of digital activation contracts."))
    behavior, mechanism, source_map = None, None, {}
    observation_map = ObservationMap((), ())
    try:
        behavior = lower_to_behavior(build)
    except UnsupportedBehaviorError as error:
        diagnostics.append(PayloadDiagnostic("behavior_profile_unsupported", "unsupported_semantics",
                                             (error.node_id,) if error.node_id else (), str(error)))
    if behavior is not None:
        try:
            mechanism, observation_map, source_map = _digital_graph(behavior, outputs)
        except UnsupportedBehaviorError as error:
            diagnostics.append(PayloadDiagnostic("executable_payload_profile_unsupported", "unsupported_semantics",
                                                 (error.node_id,) if error.node_id else (), str(error)))
    if behavior is not None:
        graph_kinds = _DIGITAL_EXPRESSIONS | {"role", "scope", "rule", "secretion", "action.pulse"}
        for node in behavior.nodes:
            supported_action = (node.kind.startswith("action.")
                                and node.attributes.get("ongoing") is True
                                and node.kind != "action.state_set"
                                and not (node.kind == "action.retain" and "location" not in node.attributes))
            if node.kind not in graph_kinds and not supported_action:
                diagnostics.append(PayloadDiagnostic("unrepresented_source_operation", "unsupported_semantics", (node.id,),
                                                     f"Source operation {node.kind!r} remains outside the supplied-contract graph profile."))
    if isinstance(source, CircuitRequest):
        _validate_circuit_mappings(source, build, diagnostics)
    return PayloadRequirements(source, behavior, outputs, tuple(requirements), tuple(diagnostics),
                               mechanism, observation_map, source_map)


def derive_boolean_response(source, rule_id, input_bindings):
    """Derive a guard table from source; temporal and mixed bands cannot collapse.

    Keys bind source qualitative predicates (preferred) or source signal IDs.
    A signal binding is permitted only when all uses have the same band. High,
    low and present are independent observations, never inferred complements.
    """
    build = source_build_request(source)
    require(len(build.intent.nodes) <= MAX_SOURCE_NODES, "Payload source node limit exceeded.")
    # Guard extraction cannot legitimize altered rule policies or malformed
    # operations merely because their Boolean spelling still looks familiar.
    lower_to_behavior(build)
    require(isinstance(input_bindings, Mapping), "Boolean source bindings must be a mapping.")
    require(all(isinstance(value, CircuitSignal) for value in input_bindings.values()),
            "Boolean source bindings require CircuitSignal values.")
    nodes = {node.id: node for node in build.intent.nodes}
    require(rule_id in nodes and nodes[rule_id].kind == "rule", "Unknown source rule binding.")
    rule = nodes[rule_id]
    if rule.attributes.get("trigger") != "condition":
        raise UnsupportedBehaviorError("Event source guards require temporal contracts.", node_id=rule_id)
    bands, used, cache = {}, set(), {}
    for ref in lineage_for(nodes, rule.inputs[1]):
        node = nodes[ref]
        if node.kind == "qualitative":
            bands.setdefault(node.inputs[0], set()).add(node.attributes.get("band"))

    def expression(ref):
        if ref in cache:
            return cache[ref]
        node = nodes[ref]
        if node.kind == "qualitative":
            key = ref if ref in input_bindings else node.inputs[0]
            require(key in input_bindings, f"Missing explicit source binding for predicate {ref}.")
            require(key == ref or len(bands[key]) == 1,
                    "Mixed qualitative bands require separate predicate bindings.")
            used.add(key)
            result = input_bindings[key].expression()
        elif node.kind == "signature":
            result = expression(node.inputs[0])
        elif node.kind == "not":
            result = ~expression(node.inputs[0])
        elif node.kind in {"and", "or"}:
            values = [expression(child) for child in node.inputs]
            result = values[0]
            for value in values[1:]:
                result = result & value if node.kind == "and" else result | value
        elif node.kind == "at_least":
            raise UnsupportedBehaviorError("Threshold-count Boolean tables require a separate refinement.", node_id=ref)
        else:
            raise UnsupportedBehaviorError(f"Source operation {node.kind!r} cannot be represented by a stateless Boolean table.",
                                           node_id=ref, source=node.source)
        cache[ref] = result
        return result

    result = expression(rule.inputs[1])
    require(used == set(input_bindings), "Boolean mapping includes unused or unrelated source bindings.")
    require(len({signal.id for signal in input_bindings.values()}) == len(input_bindings),
            "Distinct source observations cannot collapse to one circuit input.")
    return result


def validate_boolean_mapping(source, rule_id, input_bindings, claimed):
    require(isinstance(claimed, BooleanSpec), "Expected supplied Boolean response.")
    expected = derive_boolean_response(source, rule_id, input_bindings)
    require(expected.to_dict() == claimed.to_dict(), "Circuit mapping contradicts the original source guard.")
    return expected


def _validate_circuit_mappings(request, build, diagnostics):
    for item in request.requirements:
        rules = [node for node in build.intent.find(kind="rule") if node.id in item.source_node_ids]
        if len(rules) != 1 or not item.input_bindings:
            diagnostics.append(PayloadDiagnostic("circuit_mapping_incomplete", "missing_refinement", item.source_node_ids,
                                                 "Supplementary circuit mapping needs one explicit source rule and complete input bindings."))
            continue
        signals = {signal.id: signal for signal in item.behavior.response.inputs}
        bindings = {binding.source_node_id: signals[binding.observation_id] for binding in item.input_bindings}
        require(len(bindings) == len(item.input_bindings), "Circuit inputs cannot collapse distinct observations to one source node.")
        try:
            validate_boolean_mapping(build, rules[0].id, bindings, item.behavior.response)
        except UnsupportedBehaviorError as error:
            diagnostics.append(PayloadDiagnostic("circuit_mapping_requires_temporal_contract", "unsupported_semantics",
                                                 (error.node_id,) if error.node_id else (), str(error)))
        diagnostics.append(PayloadDiagnostic("circuit_output_binding_missing", "missing_refinement", item.source_node_ids,
                                             "Circuit product requires an explicit action/product correspondence; guard equality alone is insufficient."))
