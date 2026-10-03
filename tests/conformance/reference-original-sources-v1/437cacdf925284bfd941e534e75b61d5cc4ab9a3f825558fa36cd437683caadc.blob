"""Independent checks of conditional source-to-payload translations.

Expected operations come from the retained source and expected residues from
separately supplied component templates. No selector, emitter or requirements
producer is an oracle. A successful check is conditional on declarations; it
does not establish that a component implements its contract in a patient.
"""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.manifest import _Record, _hash
from biocompiler.compiler.behavior import verify_lowering
from biocompiler.errors import BiocompilerError, SerializationError
from biocompiler.ir.behavior import contact_bindings, lineage_for
from biocompiler.ir.circuit_intent import source_build_request
from biocompiler.ir.intent import thaw_json
from biocompiler.ir.serialization import fingerprint, names, require
from biocompiler.semantics.component_contracts import ports_compatible
from biocompiler.semantics.types import BOOLEAN, DURATION, TypeSpec, decode_binding
from biocompiler.verification.circuit_construction import check_circuit_construction
from biocompiler.verification.evidence import CheckOutcome


CHECKER_VERSION = "biocompiler.executable_payload_checker.v0.1"
CLAIM_SCOPE = (
    "Exact source, supplied executable component contract and complete molecule "
    "correspondence under explicit assumptions only. No biological function, "
    "experimental validation or human therapeutic admission is established."
)


@dataclass(frozen=True)
class PayloadVerification(_Record):
    request_fingerprint: str
    build_fingerprint: str
    outcome: CheckOutcome
    translation_complete: bool
    construction_complete: bool
    diagnostics: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    checker_version: str = CHECKER_VERSION
    claim_scope: str = CLAIM_SCOPE
    empirical_validation: str = "unknown"
    human_therapeutic_admission: str = "not_admitted"
    search_verified: bool = False
    search_claim: str = "selection_ranking_and_exhaustion_not_independently_certified"
    schema_version: ClassVar[str] = "biocompiler.executable_payload_verification.v0.1"

    def __post_init__(self):
        _hash(self.request_fingerprint, "Independent payload request")
        _hash(self.build_fingerprint, "Payload build")
        require(isinstance(self.outcome, CheckOutcome), "Invalid payload outcome.")
        for key in ("translation_complete", "construction_complete"):
            require(type(getattr(self, key)) is bool, "Invalid completeness flag.")
        for key in ("diagnostics", "assumptions", "unresolved"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(self.checker_version == CHECKER_VERSION and self.claim_scope == CLAIM_SCOPE,
                "Payload verification scope or checker cannot change.")
        require(self.empirical_validation == "unknown"
                and self.human_therapeutic_admission == "not_admitted",
                "Conditional translation cannot grant empirical or human-use claims.")
        require(self.search_verified is False
                and self.search_claim == "selection_ranking_and_exhaustion_not_independently_certified",
                "Selected implementation checking cannot certify search optimality or exhaustion.")
        require(self.outcome is not CheckOutcome.PASS or not self.diagnostics,
                "Passing payload verification cannot contain contradictions.")
        require(not self.translation_complete or (self.construction_complete and not self.unresolved),
                "Complete translation cannot contain unresolved obligations.")

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    @classmethod
    def from_dict(cls, data):
        from biocompiler.ir.serialization import fields
        from dataclasses import fields as dataclass_fields

        fields(data, {item.name for item in dataclass_fields(cls)} | {"schema_version"}, cls.__name__)
        require(data["schema_version"] == cls.schema_version, "Unsupported payload verification schema.")
        values = {key: value for key, value in data.items() if key != "schema_version"}
        values["outcome"] = CheckOutcome(values["outcome"])
        return cls(**values)


def _signature(kind, dtype, role, scope, attributes, inputs=()):
    """Small canonical symbolic form independent of implementation node names."""
    value = (kind, fingerprint(dtype.to_dict()), role, scope,
             fingerprint(attributes), tuple(child[6] for child in inputs))
    return (*value, fingerprint(value))


def _source_symbols(source):
    """Reconstruct required logical behavior directly from original source nodes.

    Event ordering, timer parameters, reset dominance and contact aggregation
    are represented by distinct closed operators; none is collapsed to a
    combinational truth table. Physical action contracts are checked separately.
    """
    build = source_build_request(source)
    nodes = {node.id: node for node in build.intent.nodes}
    contacts = contact_bindings(nodes)
    cache, automatic = {}, {}
    roles = tuple(node.id for node in nodes.values() if node.kind == "role")

    def role(node):
        return node.role or (roles[0] if len(roles) == 1 else None)

    def scope(ref):
        return "contact" if contacts[ref] else "cell"

    def constant(ref):
        node = nodes[ref]
        require(node.kind in {"literal", "parameter"},
                "Executable durations and constants need literal or bound parameter authority.")
        return (node.attributes["value"] if node.kind == "literal"
                else build.resolved_bindings[node.attributes["name"]])

    def duration(ref):
        return decode_binding(constant(ref), DURATION).to_dict()

    def symbol(kind, node, children=(), attrs=None, result_scope=None, dtype=BOOLEAN):
        return _signature(kind, dtype, role(node), result_scope or scope(node.id),
                          attrs or {}, children)

    def aggregate(value, node):
        if value[3] == "cell":
            return value
        return symbol("any_contact", node, (value,), result_scope="cell")

    def expression(ref):
        if ref in cache:
            return cache[ref]
        node = nodes[ref]
        kind = node.kind
        if kind in {"signature", "memory.is_set"}:
            value = expression(node.inputs[0])
        elif kind in {"signal", "qualitative"}:
            signal = node if kind == "signal" else nodes[node.inputs[0]]
            field = "value" if kind == "signal" else node.attributes["band"]
            dtype = TypeSpec.from_dict(signal.data_type) if field == "value" else BOOLEAN
            value = symbol("input", signal, attrs={"source_signal": signal.id, "field": field}, dtype=dtype)
        elif kind in {"literal", "parameter"}:
            value = symbol("constant", node, attrs={"value": constant(ref)},
                           dtype=TypeSpec.from_dict(node.data_type), result_scope="cell")
        elif kind in {"and", "or", "not", "compare"}:
            attrs = {"operator": node.attributes["operator"]} if kind == "compare" else {}
            value = symbol(kind, node, tuple(expression(item) for item in node.inputs), attrs)
        elif kind == "held_for":
            value = symbol(kind, node, (expression(node.inputs[0]),), {"duration": duration(node.inputs[1])})
        elif kind == "became_true":
            value = symbol("onset", node, (expression(node.inputs[0]),))
        elif kind == "memory":
            controls = dict(zip(node.attributes["input_names"], node.inputs, strict=True))
            setting = expression(controls["set_when"])
            setting = _signature("onset", BOOLEAN, role(node), setting[3], {}, (setting,))
            setting = aggregate(setting, node)
            resetting = (aggregate(expression(controls["reset_when"]), node)
                         if "reset_when" in controls else
                         symbol("constant", node, attrs={"value": False}, result_scope="cell"))
            value = symbol("memory", node, (setting, resetting),
                           {"duration": duration(controls["duration"]) if "duration" in controls else None},
                           result_scope="cell")
            automatic[ref] = value
        else:
            raise SerializationError(f"Unsupported source expression: {ref}:{kind}")
        cache[ref] = value
        return value

    for node in nodes.values():
        if node.kind == "memory":
            expression(node.id)
    outputs, actions = {}, {}
    for rule in nodes.values():
        if rule.kind != "rule":
            continue
        for action_id in rule.inputs[2:]:
            action = nodes[action_id]
            primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
            require(primitive.attributes.get("ongoing") is True
                    and primitive.kind != "action.state_set",
                    f"Unsupported impulse or finite-state action: {action_id}")
            require(primitive.kind != "action.secrete"
                    or primitive.attributes.get("rate") == "unspecified",
                    f"Unsupported quantitative source output: {action_id}")
            require(primitive.kind != "action.retain" or "location" in primitive.attributes,
                    f"Scoped retention needs an explicit action-target contract: {action_id}")
            ref = f"output:{rule.id}:{action_id}"
            guard = expression(rule.inputs[1])
            if not contacts[action.id]:
                guard = aggregate(guard, rule)
            if action.kind == "action.pulse":
                if rule.attributes["trigger"] == "condition":
                    guard = _signature("onset", BOOLEAN, role(rule), guard[3], {}, (guard,))
                guard = _signature("pulse", BOOLEAN, role(rule), guard[3],
                                   {"duration": duration(action.inputs[1])}, (guard,))
            elif rule.attributes["trigger"] == "event" and action.attributes.get("ongoing"):
                raise SerializationError(f"Source event output needs an explicit duration: {action_id}")
            outputs[ref] = _signature("output", BOOLEAN, role(rule), scope(action.id), {}, (guard,))
            actions[ref] = action
    return outputs, automatic, actions


def _mechanism_symbols(mechanism, observation_map):
    """Read actual graph operations and full observation bindings recursively."""
    nodes = {node.id: node for node in mechanism.nodes}
    inputs = {}
    for binding in observation_map.inputs:
        require(binding.mechanism_input_id not in inputs, "Duplicate executable observation binding.")
        inputs[binding.mechanism_input_id] = binding
    require(set(inputs) == {node.id for node in nodes.values() if node.kind == "input"},
            "Every executable input requires exact source observation authority.")
    cache, active = {}, set()

    def visit(ref):
        if ref in cache:
            return cache[ref]
        require(ref not in active, "Executable graph cannot contain combinational cycles.")
        active.add(ref)
        node = nodes[ref]
        attrs = thaw_json(node.attributes)
        if node.kind == "input":
            binding = inputs[ref]
            attrs = {"source_signal": binding.signal_id, "field": binding.field}
        value = _signature(node.kind, node.output.dtype, node.output.role, node.output.scope,
                           attrs, tuple(visit(item) for item in node.inputs))
        active.remove(ref)
        cache[ref] = value
        return value

    outputs = {}
    for binding in observation_map.outputs:
        require(binding.requirement_id not in outputs, "Duplicate executable output correspondence.")
        require(binding.mechanism_output_id in mechanism.outputs, "Observation names a non-output mechanism node.")
        outputs[binding.requirement_id] = visit(binding.mechanism_output_id)
    require({binding.mechanism_output_id for binding in observation_map.outputs} == set(mechanism.outputs)
            == {node.id for node in nodes.values() if node.kind == "output"},
            "Every executable output requires exact source correspondence.")
    memories = tuple(visit(node.id) for node in nodes.values() if node.kind == "memory")
    return outputs, memories


def _source_inventory(source):
    build = source_build_request(source)
    nodes = {node.id: node for node in build.intent.nodes}
    requirements = [
        {"id": "source:" + node.id, "kind": node.kind,
         "source_node_ids": [node.id], "semantics": node.to_dict(include_source=False)}
        for node in nodes.values()
    ]
    requirements.append({"id": "source:complete_authority", "kind": "source_authority",
                         "source_node_ids": list(nodes), "semantics": source.to_dict()})
    outputs = []
    for rule in nodes.values():
        if rule.kind != "rule":
            continue
        for ref in rule.inputs[2:]:
            action = nodes[ref]
            primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
            product = (nodes[primitive.inputs[0]].attributes.get("product")
                       if primitive.kind == "action.secrete" and primitive.inputs else None)
            trigger = rule.attributes.get("trigger")
            activation = ("explicit_duration" if action.kind == "action.pulse" else
                          "level" if primitive.attributes.get("ongoing") else
                          "event" if trigger == "event" else "onset")
            outputs.append({
                "id": f"output:{rule.id}:{action.id}", "rule_id": rule.id,
                "action_id": action.id, "guard_id": rule.inputs[1], "role_id": rule.role,
                "action_kind": primitive.kind, "lineage": list(lineage_for(nodes, rule.id)),
                "trigger": trigger, "activation": activation, "product": product,
                "semantics": {"action": action.to_dict(include_source=False),
                              "primitive_action": primitive.to_dict(include_source=False),
                              "dependencies": [nodes[item].to_dict(include_source=False)
                                               for item in lineage_for(nodes, action.id)]},
            })
    return requirements, outputs


def _source_correspondence(source):
    """Reconstruct the profile's exact graph identities, edges and source ancestry."""
    build = source_build_request(source)
    nodes = {node.id: node for node in build.intent.nodes}
    contacts = contact_bindings(nodes)
    ancestry = {ref: set(lineage_for(nodes, ref)) for ref in nodes}
    mapped, edges, cache, contributors = {}, {}, {}, {}

    def add(identity, refs, inputs=()):
        mapped.setdefault(identity, set()).update(ancestor for ref in refs for ancestor in ancestry[ref])
        contributors.setdefault(identity, set()).update(refs)
        edges[identity] = tuple(inputs)
        return identity

    def expression(ref):
        if ref in cache:
            return cache[ref]
        node = nodes[ref]
        identity = "expression:" + ref
        if node.kind in {"signal", "qualitative"}:
            signal, field = ((ref, "value") if node.kind == "signal" else
                             (node.inputs[0], node.attributes["band"]))
            identity = add(f"input:{signal}:{field}", (ref,))
        elif node.kind in {"signature", "memory.is_set"}:
            identity = expression(node.inputs[0])
            mapped[identity].update(ancestry[ref])
            contributors[identity].add(ref)
        elif node.kind in {"literal", "parameter"}:
            add(identity, (ref,))
        elif node.kind in {"and", "or", "not", "compare"}:
            add(identity, (ref,), tuple(expression(item) for item in node.inputs))
        elif node.kind in {"held_for", "became_true"}:
            add(identity, (ref,), (expression(node.inputs[0]),))
        elif node.kind == "memory":
            controls = dict(zip(node.attributes["input_names"], node.inputs, strict=True))
            setting = add("memory_onset:" + ref, (ref,), (expression(controls["set_when"]),))
            if contacts[controls["set_when"]]:
                setting = add("memory_set:" + ref, (ref,), (setting,))
            if "reset_when" in controls:
                resetting = expression(controls["reset_when"])
                if contacts[controls["reset_when"]]:
                    resetting = add("memory_reset:" + ref, (ref,), (resetting,))
            else:
                resetting = add("memory_reset:" + ref, (ref,))
            add(identity, (ref,), (setting, resetting))
        else:
            raise SerializationError("Unsupported source correspondence operation: " + node.kind)
        cache[ref] = identity
        return identity

    for node in nodes.values():
        if node.kind == "memory":
            expression(node.id)
    for rule in nodes.values():
        if rule.kind != "rule":
            continue
        for action_id in rule.inputs[2:]:
            action = nodes[action_id]
            identity = f"output:{rule.id}:{action_id}"
            guard = expression(rule.inputs[1])
            if contacts[rule.inputs[1]] and not contacts[action_id]:
                guard = add("aggregate:" + identity, (rule.id,), (guard,))
            if action.kind == "action.pulse":
                if rule.attributes["trigger"] == "condition":
                    guard = add("pulse_onset:" + identity, (rule.id, action_id), (guard,))
                guard = add("pulse:" + identity, (rule.id, action_id), (guard,))
            add(identity, (rule.id, action_id), (guard,))
    _, outputs = _source_inventory(source)
    requirement_ids = {
        identity: tuple(output["id"] for output in outputs
                        if refs.intersection(output["lineage"]))
        for identity, refs in contributors.items()
    }
    return {identity: tuple(sorted(refs)) for identity, refs in mapped.items()}, edges, requirement_ids


def _check_circuit_bindings(request):
    """Check supplied table rows against original predicates without a lowerer."""
    problems = []
    source = source_build_request(request.source)
    nodes = {node.id: node for node in source.intent.nodes}
    requirements = {item.id: item for item in request.circuit.requirements}
    bindings = {item.requirement_id: item for item in request.circuit_bindings}
    for identity, item in requirements.items():
        for provider in item.behavior.dependencies:
            problems.append(f"unsupported:circuit_provider_mapping:{identity}:{provider.id}")
    for identity in sorted(requirements.keys() - bindings.keys()):
        problems.append("unsupported:circuit_binding_missing:" + identity)
    for identity, binding in bindings.items():
        item = requirements[identity]
        rule = nodes.get(binding.rule_id)
        if rule is None or rule.kind != "rule" or binding.action_id not in rule.inputs[2:]:
            problems.append("fail:circuit_source_action:" + identity)
            continue
        if item.role_id != rule.role or not {binding.rule_id, binding.action_id} <= set(item.source_node_ids):
            problems.append("fail:circuit_source_role_or_lineage:" + identity)
        authored = {entry.observation_id: entry.source_node_id for entry in item.input_bindings}
        if authored and authored != dict(binding.signals):
            problems.append("fail:circuit_original_input_binding:" + identity)
        action = nodes[binding.action_id]
        primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
        if primitive.kind == "action.secrete":
            product = nodes[primitive.inputs[0]].attributes.get("product")
            if product is not None and item.behavior.output.id != product:
                problems.append("fail:circuit_source_product:" + identity)
        if any(getattr(item.behavior.lifecycle, key) is not None for key in ("onset", "cessation", "clearance")):
            problems.append("unsupported:circuit_lifecycle:" + identity)
        signals = tuple(signal.id for signal in item.behavior.response.inputs)
        if set(binding.signals) != set(signals) or len(set(binding.signals.values())) != len(signals):
            problems.append("fail:circuit_input_inventory:" + identity)
            continue
        inverse = {value: key for key, value in binding.signals.items()}
        used, bands = set(), {}
        for ref in lineage_for(nodes, rule.inputs[1]):
            node = nodes[ref]
            if node.kind == "qualitative":
                bands.setdefault(node.inputs[0], set()).add(node.attributes["band"])

        def evaluate(ref, assignment):
            node = nodes[ref]
            if node.kind == "qualitative":
                bound = ref if ref in inverse else node.inputs[0]
                require(bound in inverse and (bound == ref or len(bands[bound]) == 1),
                        "Missing or ambiguous qualitative predicate binding.")
                used.add(bound)
                return assignment[inverse[bound]]
            if node.kind == "signature":
                return evaluate(node.inputs[0], assignment)
            if node.kind == "not":
                return not evaluate(node.inputs[0], assignment)
            if node.kind in {"and", "or"}:
                operands = tuple(evaluate(ref, assignment) for ref in node.inputs)
                return all(operands) if node.kind == "and" else any(operands)
            raise _TemporalProjection("Circuit table needs an explicit temporal or scalar refinement.")

        try:
            if rule.attributes["trigger"] != "condition":
                raise _TemporalProjection("Circuit table cannot replace event semantics.")
            values = []
            for row in range(1 << len(signals)):
                assignment = {signal: bool(row & (1 << (len(signals) - index - 1)))
                              for index, signal in enumerate(signals)}
                values.append(evaluate(rule.inputs[1], assignment))
            require(used == set(inverse), "Circuit mapping contains unused source inputs.")
            if tuple(values) != item.behavior.response.outputs:
                problems.append("fail:circuit_guard_contradiction:" + identity)
        except _TemporalProjection:
            problems.append("unsupported:circuit_temporal_or_input_refinement:" + identity)
        except (SerializationError, KeyError):
            problems.append("fail:circuit_source_input_binding:" + identity)
    return problems


class _TemporalProjection(Exception):
    pass


def _component_checks(request, build, actual_nodes, expected_outputs):
    problems = []
    contracts = {item.id: item for item in request.library.contracts}
    selected = {}
    for identity, contract_id in build.selected.items():
        contract = contracts.get(contract_id)
        if contract is None:
            problems.append("fail:selected_component_authority:" + identity)
        else:
            selected[identity] = contract
    if selected.keys() != actual_nodes.keys():
        problems.append("fail:complete_component_inventory")
        return selected, problems
    target = request.circuit.profile.target
    source_outputs = {item["id"]: item for item in expected_outputs}
    circuit_requirements = {item.id: item for item in request.circuit.requirements}
    bound_outputs = {}
    for binding in request.circuit_bindings:
        bound_outputs.setdefault(f"output:{binding.rule_id}:{binding.action_id}", []).append(
            circuit_requirements[binding.requirement_id]
        )
    for identity, contract in selected.items():
        node, record = actual_nodes[identity], contract.component
        model = record.synthetic_model
        output = record.port(model.output_port)
        if (node.kind != model.operation or fingerprint(node.attributes) != fingerprint(model.attributes)
                or len(node.inputs) != len(model.input_ports)):
            problems.append("fail:component_operation:" + identity)
        if (node.output.id, node.output.dtype, node.output.role, node.output.scope,
            node.output.compartment) != (output.meaning, output.dtype, output.role,
                                        output.scope, output.compartment):
            problems.append("fail:component_output_interface:" + identity)
        if node.kind == "input" and node.output.id != identity:
            problems.append("fail:component_source_meaning:" + identity)
        if target.payload_format.value not in record.supported_targets:
            problems.append("fail:component_target:" + identity)
        if any(item.compartment not in target.compartments
               for item in (*record.ports, *(dependency for dependency in record.dependencies if dependency.required),
                            *record.capabilities, *record.resources)):
            problems.append("fail:component_compartment:" + identity)
        if record.resources:
            problems.append("fail:component_resource_accounting:" + identity)
        if record.supported_domain.constraints:
            problems.append("fail:component_operating_domain:" + identity)
        if any(check.status != "pass" for check in model.domain_checks(record.ports, record.supported_domain)):
            problems.append("fail:component_value_domain:" + identity)
        if node.kind == "output" and identity in source_outputs:
            required = source_outputs[identity]
            primitive = required["semantics"]["primitive_action"]
            effect = {"kind": primitive["kind"], "attributes": primitive["attributes"],
                      "product": required["product"]}
            if fingerprint(getattr(contract, "effect", None)) != fingerprint(effect):
                problems.append("fail:component_action_effect:" + identity)
            for requirement in bound_outputs.get(identity, ()):
                product = getattr(contract, "output_product", None)
                lifecycle = getattr(contract, "output_lifecycle", None)
                if product is None or product.fingerprint != requirement.behavior.output.fingerprint:
                    problems.append("fail:component_circuit_output:" + requirement.id)
                if lifecycle is None or lifecycle.fingerprint != requirement.behavior.lifecycle.fingerprint:
                    problems.append("fail:component_circuit_lifecycle:" + requirement.id)
        for index, source_id in enumerate(node.inputs):
            if source_id not in selected or index >= len(model.input_ports):
                problems.append("fail:component_wiring:" + identity)
                continue
            producer = selected[source_id].component
            match = ports_compatible(producer.port(producer.synthetic_model.output_port),
                                     record.port(model.input_ports[index]))
            if not match.passed:
                problems.append(f"fail:component_connection:{source_id}:{identity}:{index}:{match.status}")

    providers = {item.id: item for item in request.library.providers}
    available, pending = set(), set(providers)
    while pending:
        progress = {identity for identity in pending
                    if providers[identity].kind in {"host", "external"}
                    and target.payload_format.value in providers[identity].supported_targets
                    and all(cap.compartment in target.compartments
                            for cap in providers[identity].capabilities)
                    and (providers[identity].kind != "host" or
                         all(cap.id in target.capabilities for cap in providers[identity].capabilities))
                    and set(providers[identity].depends_on) <= available}
        if not progress:
            break
        available.update(progress)
        pending.difference_update(progress)
    capabilities = {(cap.id, cap.role, cap.scope, cap.compartment)
                    for identity in available for cap in providers[identity].capabilities}
    pending_components = set(selected)
    while pending_components:
        grounded = {identity for identity in pending_components if all(
            (dependency.capability, dependency.role, dependency.scope, dependency.compartment) in capabilities
            for dependency in selected[identity].component.dependencies if dependency.required)}
        if not grounded:
            break
        for identity in grounded:
            capabilities.update((cap.id, cap.role, cap.scope, cap.compartment)
                                for cap in selected[identity].component.capabilities)
        pending_components.difference_update(grounded)
    for identity in sorted(pending_components):
        problems.append(f"fail:component_dependency_ungrounded:{identity}")
    return selected, problems


def _expected_construction(request, selected):
    """Rebuild namespace correspondence from independent templates, not a merge."""
    from biocompiler.ir.circuit_construction import CircuitConstructionRequest

    fields = ("sources", "steps", "output_members", "requirements",
              "complex_members", "amounts", "payload_structures")
    result = {key: [] for key in fields}
    local_types = {
        "payload_template", "construction_root_source", "circuit_molecule",
        "construction_transform_step", "construction_product_port", "construction_value_ref",
        "construction_output_member", "construction_member_requirement",
        "construction_role_declaration", "construction_complex_member",
        "construction_amount_declaration",
    }
    for index, identity in enumerate(sorted(selected)):
        template = selected[identity].template
        if template is None:
            continue
        prefix = f"p{index:03d}_"
        document = template.to_dict()
        frames = {source.molecule.space.id for source in template.sources}
        frames.update(port.space_id for step in template.steps for port in step.ports)
        frames.update(member.space_id for member in template.output_members)
        pending = [document]
        while pending:
            value = pending.pop()
            if isinstance(value, list):
                pending.extend(value)
                continue
            if not isinstance(value, dict):
                continue
            schema = value.get("schema_version", "")
            schema_type = schema.removeprefix("biocompiler.").rsplit(".v", 1)[0]
            if schema_type == "molecular_declaration_provenance":
                continue
            pending.extend(child for child in value.values() if isinstance(child, (dict, list)))
            if schema_type in local_types or (
                schema_type == "molecule_coordinate_space" and value.get("id") in frames
            ):
                value["id"] = prefix + value["id"]
            if value.get("space_id") in frames:
                value["space_id"] = prefix + value["space_id"]
            for key in ("member_id", "port_id"):
                if value.get(key) is not None:
                    value[key] = prefix + value[key]
            if schema_type in {"chemistry_disposition", "feature_disposition"}:
                value["source_id"] = prefix + value["source_id"]
            if schema_type == "construction_amount_declaration":
                for key in ("subject_id", "preparation_id"):
                    value[key] = prefix + value[key]
                value["role_instance_ids"] = [prefix + item for item in value["role_instance_ids"]]
        for key in fields:
            result[key].extend(document[key])
    return CircuitConstructionRequest.from_dict({
        "schema_version": CircuitConstructionRequest.schema_version,
        "id": request.id + ".construction", "circuit": request.circuit.to_dict(),
        "mode": "strict", **result,
    })


def _molecular_bindings(selected, bundle):
    problems = []
    molecules = {item.id: item for item in bundle.molecules}
    subjects = set(molecules) | {item.id for item in bundle.complexes}
    for index, identity in enumerate(sorted(selected)):
        contract = selected[identity]
        prefix = f"p{index:03d}_"
        for binding in (*contract.port_bindings, *contract.capability_bindings):
            if binding.member_id is None:
                continue
            member_id = prefix + binding.member_id
            if member_id not in subjects:
                problems.append("fail:component_material_member:" + identity + ":" + member_id)
                continue
            feature = getattr(binding, "feature_id", None)
            if feature is not None:
                molecule = molecules.get(member_id)
                if molecule is None or feature not in {item.id for item in molecule.features}:
                    problems.append("fail:component_material_feature:" + identity + ":" + feature)
            if not any(role.subject_id == member_id and role.compartment == binding.compartment
                       for role in bundle.role_instances):
                problems.append("fail:component_material_compartment:" + identity + ":" + member_id)
    return problems


def _delivered_rna_diagnostics(construction, bundle):
    """Delivered payload and helper members must be RNA, including complexes.

    The requirement category is authoritative here: encoded protein products
    share a helper role label but remain permissible derived-product metadata.
    """
    molecules = {item.id: item for item in bundle.molecules}
    complexes = {item.id: item for item in bundle.complexes}
    diagnostics = []
    for requirement in construction.requirements:
        if requirement.category not in {"payload", "delivered_helper"}:
            continue
        identity = requirement.member_id
        if identity in molecules:
            components = (molecules[identity],)
        elif identity in complexes:
            components = tuple(molecules.get(item.molecule_id)
                               for item in complexes[identity].constituents)
        else:
            components = ()
        if not components or any(item is None or item.space.alphabet != "RNA" for item in components):
            diagnostics.append("fail:delivered_member_not_rna:" + str(identity))
    return diagnostics


def check_payload_build(build, *, expected_request):
    """Check source, selected contracts and every molecule against separate authority.

    Selection ranking is not accepted as an optimization proof. The selected
    implementation, its action meaning, complete molecule set, hard nucleotide
    limit and all retained obligations are checked independently of that ranking.
    """
    from biocompiler.ir.executable_payload import PayloadBuild, PayloadCompilationRequest

    require(isinstance(build, PayloadBuild), "Expected a payload build candidate.")
    require(isinstance(expected_request, PayloadCompilationRequest),
            "Payload replay requires the complete independent request and component library.")
    request = PayloadCompilationRequest.from_dict(expected_request.to_dict())
    diagnostics = []
    requirements = build.requirements
    if build.request_fingerprint != request.fingerprint:
        diagnostics.append("fail:payload_request_authority")
    if requirements.source.fingerprint != request.source.fingerprint:
        diagnostics.append("fail:original_source_authority")
    expected_inventory, expected_outputs = _source_inventory(request.source)
    if fingerprint(requirements.requirements) != fingerprint(expected_inventory):
        diagnostics.append("fail:complete_source_requirement_inventory")
    if fingerprint([item.to_dict() for item in requirements.outputs]) != fingerprint(expected_outputs):
        diagnostics.append("fail:complete_source_output_inventory")
    source_build = source_build_request(request.source)
    if requirements.behavior is None:
        diagnostics.append("unsupported:source_behavior_profile")
    else:
        try:
            verify_lowering(source_build, requirements.behavior)
        except BiocompilerError:
            diagnostics.append("fail:source_behavior_correspondence")

    # Keep original deployment, acceptance and quantitative requirements visible
    # even though no experimental evidence is requested by this code profile.
    for item in requirements.diagnostics:
        status = "fail" if item.category == "contradiction" else "unsupported"
        diagnostics.append(f"{status}:retained_source:{item.code}")
    digital_kinds = {
        "role", "scope", "signal", "qualitative", "literal", "parameter", "signature",
        "and", "or", "not", "compare", "held_for", "became_true", "memory", "memory.is_set",
        "rule", "secretion", "action.pulse",
    }
    for node in source_build.intent.nodes:
        if node.kind not in digital_kinds and not (
            node.kind.startswith("action.") and node.attributes.get("ongoing")
            and node.kind != "action.state_set"
        ):
            diagnostics.append("unsupported:unrepresented_source_operation:" + node.id)
            if not any(node.id in item.source_node_ids and item.category == "unsupported_semantics"
                       for item in requirements.diagnostics):
                diagnostics.append("fail:omitted_source_unsupported_obligation:" + node.id)
        if node.kind == "action.retain" and "location" not in node.attributes:
            diagnostics.append("unsupported:scope_valued_retention_target:" + node.id)
            candidates = {node.id} | {item.id for item in source_build.intent.nodes
                                     if item.kind == "action.pulse" and item.inputs[0] == node.id}
            if not any(candidates.intersection(item.source_node_ids)
                       and item.category == "unsupported_semantics" for item in requirements.diagnostics):
                diagnostics.append("fail:omitted_action_target_obligation:" + node.id)
    for key in ("implementation_constraints", "preferences"):
        if getattr(source_build, key):
            diagnostics.append("unsupported:source_" + key)
    if request.source.schema_version != "biocompiler.build_request.v0.1":
        diagnostics.append("unsupported:source_wrapper_obligations")
    diagnostics.extend(_check_circuit_bindings(request))

    # Source-stage artifacts are checked even when selection did not produce an
    # implementation. An unsuccessful search cannot hide a corrupted graph.
    if requirements.mechanism is not None:
        try:
            wanted, automatic, _ = _source_symbols(request.source)
            observed, remembered = _mechanism_symbols(requirements.mechanism, requirements.observation_map)
            lineage, edges, required_ids = _source_correspondence(request.source)
            if observed != wanted or sorted(remembered, key=repr) != sorted(automatic.values(), key=repr):
                diagnostics.append("fail:source_activation_graph_semantics")
            if fingerprint(requirements.source_map) != fingerprint(lineage):
                diagnostics.append("fail:source_activation_lineage")
            if {node.id: node.inputs for node in requirements.mechanism.nodes} != edges:
                diagnostics.append("fail:source_activation_node_inventory")
            if {node.id: node.requirement_ids for node in requirements.mechanism.nodes} != required_ids:
                diagnostics.append("fail:source_activation_requirement_ids")
        except (BiocompilerError, KeyError, ValueError, RecursionError):
            diagnostics.append("fail:source_activation_reconstruction")
    elif requirements.behavior is not None and not any(
        item.category == "unsupported_semantics" for item in requirements.diagnostics
    ):
        diagnostics.append("fail:unexplained_missing_source_activation_graph")

    selected = {}
    if build.mechanism is None:
        diagnostics.append("unsupported:no_selected_executable_implementation")
        if build.status in {"no_solution", "search_exhausted"}:
            diagnostics.append("unsupported:search_outcome_not_independently_replayed")
    else:
        try:
            expected_symbols, expected_memories, _ = _source_symbols(request.source)
            actual_symbols, actual_memories = _mechanism_symbols(build.mechanism, requirements.observation_map)
            if actual_symbols != expected_symbols:
                diagnostics.append("fail:source_executable_output_semantics")
            if sorted(actual_memories, key=repr) != sorted(expected_memories.values(), key=repr):
                diagnostics.append("fail:source_automatic_memory_semantics")
            if requirements.mechanism is None:
                diagnostics.append("fail:missing_source_activation_graph")
            else:
                source_symbols, source_memories = _mechanism_symbols(requirements.mechanism, requirements.observation_map)
                if source_symbols != expected_symbols or sorted(source_memories, key=repr) != sorted(expected_memories.values(), key=repr):
                    diagnostics.append("fail:source_activation_graph_semantics")
                actual_nodes = {node.id: node for node in build.mechanism.nodes}
                source_nodes = {node.id: node for node in requirements.mechanism.nodes}
                expected_map, expected_edges, expected_requirement_ids = _source_correspondence(request.source)
                if fingerprint(requirements.source_map) != fingerprint(expected_map):
                    diagnostics.append("fail:source_activation_lineage")
                if actual_nodes.keys() != source_nodes.keys() or actual_nodes.keys() != expected_edges.keys():
                    diagnostics.append("fail:source_activation_node_inventory")
                for identity in actual_nodes.keys() & source_nodes.keys():
                    actual, original = actual_nodes[identity], source_nodes[identity]
                    if (actual.inputs != original.inputs or actual.inputs != expected_edges.get(identity)
                            or actual.requirement_ids != original.requirement_ids):
                        diagnostics.append("fail:source_activation_wiring:" + identity)
                    if actual.requirement_ids != expected_requirement_ids.get(identity):
                        diagnostics.append("fail:source_activation_requirement_ids:" + identity)
                selected, problems = _component_checks(request, build, actual_nodes, expected_outputs)
                diagnostics.extend(problems)
        except (BiocompilerError, KeyError, ValueError, RecursionError):
            diagnostics.append("fail:source_executable_reconstruction")

    assumptions = {
        "Supplied component sequences are assumed to realize their declared executable contracts.",
        "Translation correctness establishes no biological function or human therapeutic admission.",
        *request.library.assumptions,
    }
    for contract in selected.values():
        assumptions.update(contract.assumptions)
        assumptions.update(contract.component.assumptions)
    if build.selected and set(build.assumptions) != assumptions:
        diagnostics.append("fail:complete_contract_assumptions")
    construction_complete = False
    if build.construction is None:
        diagnostics.append("unsupported:no_complete_molecule_set")
    elif selected:
        try:
            expected_construction = _expected_construction(request, selected)
            if build.construction.request.fingerprint != expected_construction.fingerprint:
                diagnostics.append("fail:selected_template_construction_authority")
            check = check_circuit_construction(build.construction.candidate,
                                              expected_request=expected_construction)
            construction_complete = check.passed
            diagnostics.extend(check.diagnostics)
            if not check.passed:
                diagnostics.append("fail:selected_molecule_set_incomplete")
            if build.construction.assessment.fingerprint != check.fingerprint:
                diagnostics.append("fail:historical_construction_assessment")
            if build.molecules is not None:
                diagnostics.extend(_molecular_bindings(selected, build.molecules))
                diagnostics.extend(_delivered_rna_diagnostics(expected_construction, build.molecules))
                if any(item.space.alphabet == "DNA" for item in build.molecules.molecules):
                    diagnostics.append("fail:final_dna_member_outside_rna_payload_scope")
                limit = request.constraints.max_total_bases
                total = sum(len(item.sequence) for item in build.molecules.molecules
                            if item.space.alphabet in {"DNA", "RNA"})
                if limit is not None and total > limit:
                    diagnostics.append("fail:complete_molecule_nucleotide_budget")
        except (BiocompilerError, KeyError, ValueError, RecursionError):
            diagnostics.append("fail:selected_template_reconstruction")
    else:
        diagnostics.append("fail:construction_without_authoritative_components")
    unresolved = tuple(sorted({item for item in diagnostics if not item.startswith("fail:")}))
    diagnostics = tuple(sorted({item for item in diagnostics if item.startswith("fail:")}))
    translation_complete = bool(build.selected) and not diagnostics and not unresolved
    if build.status == "compiled" and not translation_complete:
        diagnostics = tuple(sorted((*diagnostics, "fail:unsupported_complete_translation_claim")))
    if request.constraints.require_complete and build.selected and not translation_complete:
        diagnostics = tuple(sorted((*diagnostics, "fail:strict_translation_completeness")))
    outcome = CheckOutcome.FAIL if diagnostics else CheckOutcome.PASS
    return PayloadVerification(request.fingerprint, build.fingerprint, outcome,
                               translation_complete, construction_complete, diagnostics,
                               tuple(sorted(assumptions)), unresolved)


def verify_payload_build(verification, build, *, expected_request):
    """Recompute a historical receipt using separately retained complete authority."""
    require(isinstance(verification, PayloadVerification), "Expected a payload verification receipt.")
    fresh = check_payload_build(build, expected_request=expected_request)
    require(verification.fingerprint == fresh.fingerprint,
            "Payload verification differs from current independent complete replay.")
    return fresh
