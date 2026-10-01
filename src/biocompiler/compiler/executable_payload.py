"""Connect source meaning, supplied executable contracts and complete molecules."""

from itertools import islice, product
import math

from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.ir.executable_payload import (
    PayloadAlternative, PayloadBuild, PayloadCompilationRequest,
)
from biocompiler.ir.intent import thaw_json
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.component_contracts import ports_compatible
from biocompiler.semantics.payload_requirements import (
    extract_payload_requirements, validate_boolean_mapping,
)
from biocompiler.semantics.realization import Observable


def _effect(output):
    action = output.semantics["primitive_action"]
    return {"kind": action["kind"], "attributes": thaw_json(action["attributes"]),
            "product": output.product}


def _circuit_diagnostics(request, requirements):
    diagnostics = []
    source_outputs = {(x.rule_id, x.action_id): x for x in requirements.outputs}
    bindings = {x.requirement_id: x for x in request.circuit_bindings}
    for item in request.circuit.requirements:
        diagnostics.extend("unresolved:circuit_provider_mapping:" + item.id + ":" + provider.id
                           for provider in item.behavior.dependencies)
        binding = bindings.get(item.id)
        if binding is None:
            diagnostics.append("unresolved:circuit_source_binding:" + item.id)
            continue
        output = source_outputs.get((binding.rule_id, binding.action_id))
        require(output is not None and output.role_id == item.role_id,
                "Circuit output binding contradicts the installed source action/role.")
        require({binding.rule_id, binding.action_id} <= set(item.source_node_ids),
                "Circuit output must retain its bound source rule and action.")
        if output.product is not None:
            require(item.behavior.output.id == output.product,
                    "Circuit product mapping contradicts original source product.")
        signals = {x.id: x for x in item.behavior.response.inputs}
        require(set(binding.signals) == set(signals), "Circuit source mapping must cover every observation.")
        require(len(set(binding.signals.values())) == len(binding.signals),
                "Distinct circuit observations cannot collapse to one source observation.")
        authored = {x.observation_id: x.source_node_id for x in item.input_bindings}
        require(not authored or authored == dict(binding.signals),
                "Payload bindings contradict the original circuit input bindings.")
        try:
            validate_boolean_mapping(request.source, binding.rule_id,
                                     {source: signals[key] for key, source in binding.signals.items()},
                                     item.behavior.response)
        except UnsupportedBehaviorError:
            diagnostics.append("unresolved:stateless_circuit_projection:" + item.id)
        # Lifecycle and quantitative observation refinements are retained, never
        # inferred from equality of the activation guard.
        if any(getattr(item.behavior.lifecycle, key) is not None
               for key in ("onset", "cessation", "clearance")):
            diagnostics.append("unresolved:circuit_lifecycle:" + item.id)
    return diagnostics


def _match(contract, node, nodes, outputs, target, request):
    component, reasons = contract.component, []
    model = component.synthetic_model
    if model.operation != node.kind:
        return ("operation_mismatch",)
    if fingerprint(model.attributes) != fingerprint(node.attributes):
        reasons.append("operator_parameters_mismatch")
    if len(model.input_ports) != len(node.inputs):
        reasons.append("operator_arity_mismatch")
    if target.payload_format.value not in component.supported_targets:
        reasons.append("unsupported_payload_format")
    output = component.port(model.output_port)
    for key, expected in (("dtype", node.output.dtype),
                          ("role", node.role), ("scope", node.scope)):
        if getattr(output, key) != expected:
            reasons.append("output_" + key + "_mismatch")
    for port_id, ref in zip(model.input_ports, node.inputs):
        port, upstream = component.port(port_id), nodes[ref]
        if (port.dtype, port.role, port.scope) != (
                upstream.output.dtype, upstream.role, upstream.scope):
            reasons.append("input_semantics_mismatch:" + port_id)
    if node.kind == "input" and output.meaning != node.output.id:
        reasons.append("source_observation_identity_mismatch")
    if any(binding.compartment not in target.compartments
           for binding in (*contract.port_bindings, *contract.capability_bindings)):
        reasons.append("undeclared_physical_compartment")
    if any(dependency.compartment not in target.compartments
           for dependency in component.dependencies if dependency.required):
        reasons.append("undeclared_dependency_compartment")
    if node.kind == "output" and fingerprint(contract.effect) != fingerprint(_effect(outputs[node.id])):
        reasons.append("source_action_or_product_mismatch")
    if node.kind == "output":
        output_requirement = outputs[node.id]
        circuit_requirements = {item.id: item for item in request.circuit.requirements}
        for binding in request.circuit_bindings:
            if (binding.rule_id, binding.action_id) == (output_requirement.rule_id, output_requirement.action_id):
                behavior = circuit_requirements[binding.requirement_id].behavior
                if (contract.output_product is None or contract.output_lifecycle is None
                        or contract.output_product.fingerprint != behavior.output.fingerprint
                        or contract.output_lifecycle.fingerprint != behavior.lifecycle.fingerprint):
                    reasons.append("supplementary_output_contract_mismatch:" + binding.requirement_id)
    if component.resources:
        reasons.append("unsupported_resource_reservations")
    # Domain coordinates have no implicit physiological interpretation. Unknown
    # domain requirements require a caller refinement before selection.
    if component.supported_domain.constraints:
        reasons.append("unsupported_operating_domain_refinement")
    if any(check.status != "pass" for check in model.domain_checks(component.ports, component.supported_domain)):
        reasons.append("unsupported_or_inconsistent_value_domain")
    return tuple(dict.fromkeys(reasons))


def _connections_and_dependencies(selected, graph, library, target):
    reasons = []
    for node in graph.nodes:
        contract = selected[node.id]
        model = contract.component.synthetic_model
        for port_id, ref in zip(model.input_ports, node.inputs):
            producer = selected[ref]
            result = ports_compatible(
                producer.component.port(producer.component.synthetic_model.output_port),
                contract.component.port(port_id))
            if result.status != "pass":
                reasons.append("incompatible_connection:" + ref + ":" + node.id + ":" + port_id)
    # Capabilities become usable only after their providers are grounded. This
    # establishes existence of an acyclic prerequisite order without making a
    # greedy provider choice that could create an avoidable cycle.
    providers = {provider.id: provider for provider in library.providers}
    available_providers, pending_providers = set(), set(providers)
    while pending_providers:
        ready = {
            identity for identity in pending_providers
            if providers[identity].kind in {"host", "external"}
            and target.payload_format.value in providers[identity].supported_targets
            and all(cap.compartment in target.compartments
                    for cap in providers[identity].capabilities)
            and (providers[identity].kind != "host" or all(
                cap.id in target.capabilities for cap in providers[identity].capabilities))
            and set(providers[identity].depends_on) <= available_providers
        }
        if not ready:
            break
        available_providers.update(ready)
        pending_providers.difference_update(ready)

    def capability_key(capability):
        return (capability.id, capability.role, capability.scope, capability.compartment)

    def dependency_key(dependency):
        return (dependency.capability, dependency.role, dependency.scope, dependency.compartment)

    available = {
        capability_key(capability) for identity in available_providers
        for capability in providers[identity].capabilities
    }
    pending_components = set(selected)
    while pending_components:
        ready = {
            identity for identity in pending_components
            if all(not dependency.required or dependency_key(dependency) in available
                   for dependency in selected[identity].component.dependencies)
        }
        if not ready:
            break
        pending_components.difference_update(ready)
        available.update(
            capability_key(capability) for identity in ready
            for capability in selected[identity].component.capabilities
        )
    all_declared = available | {
        capability_key(capability) for identity in pending_components
        for capability in selected[identity].component.capabilities
    }
    for identity in sorted(pending_components):
        for dependency in selected[identity].component.dependencies:
            key = dependency_key(dependency)
            if dependency.required and key not in available:
                reason = "ungrounded_dependency" if key in all_declared else "missing_dependency"
                reasons.append(reason + ":" + identity + ":" + dependency.id)

    return tuple(dict.fromkeys(reasons))


def _construction(selected, request):
    from biocompiler.ir.payload_contracts import namespace_payload_template, merge_payload_templates
    templates = tuple(namespace_payload_template(contract.template, f"p{index:03d}_")
                      for index, (_, contract) in enumerate(sorted(selected.items()))
                      if contract.template is not None)
    authority = merge_payload_templates(templates, request.circuit,
                                        id=request.id + ".construction", mode="strict")
    return build_circuit_construction(authority)


def _selected_mechanism(selected, graph):
    nodes = []
    for node in graph.nodes:
        component = selected[node.id].component
        model, port = component.synthetic_model, component.port(component.synthetic_model.output_port)
        nodes.append(MechanismNode(node.id, model.operation,
                                   Observable(port.meaning, port.dtype, port.role, port.scope, port.compartment),
                                   node.inputs, model.attributes, node.requirement_ids))
    return MechanismProgram(graph.name, tuple(nodes), graph.outputs, graph.required_capabilities)


def compile_payload(request: PayloadCompilationRequest) -> PayloadBuild:
    """Search supplied contracts and independently check the emitted molecule set.

    Exhaustion is bounded-search exhaustion, never a claim about all possible
    implementations. Unsupported source requirements remain in the result.
    """
    require(isinstance(request, PayloadCompilationRequest), "Expected a payload compilation request.")
    request = PayloadCompilationRequest.from_dict(request.to_dict())
    requirements = extract_payload_requirements(request.source)
    diagnostics = [f"{x.category}:{x.code}" for x in requirements.diagnostics]
    diagnostics.extend(_circuit_diagnostics(request, requirements))
    diagnostics = list(dict.fromkeys(diagnostics))
    assumptions = tuple(sorted(set((
        "Supplied component sequences are assumed to realize their declared executable contracts.",
        "Translation correctness establishes no biological function or human therapeutic admission.",
        *request.library.assumptions,
    ))))
    alternatives = []

    def finish(status, selected=None, mechanism=None, construction=None):
        result = PayloadBuild(request.fingerprint, requirements, selected or {}, mechanism, construction,
                              tuple(alternatives), tuple(diagnostics), assumptions, status)
        from biocompiler.verification.executable_payload import check_payload_build
        assessment = check_payload_build(result, expected_request=request)
        require(assessment.outcome == "pass", "Independent payload verification failed: " + str(assessment.diagnostics))
        return result

    graph = requirements.mechanism
    if graph is None or any(x.category == "contradiction" for x in requirements.diagnostics):
        return finish("unsupported")
    if request.constraints.require_complete and diagnostics:
        return finish("unsupported")
    require(len(graph.nodes) <= 128, "Executable payload node budget exceeded.")
    nodes = {node.id: node for node in graph.nodes}
    outputs = {item.id: item for item in requirements.outputs}
    target = requirements.build_request.target
    choices = []
    for identity in sorted(nodes):
        eligible = []
        for contract in request.library.contracts:
            reasons = _match(contract, nodes[identity], nodes, outputs, target, request)
            if reasons:
                if len(alternatives) >= 2048:
                    diagnostics.append("selection_record_budget_exhausted:2048")
                    return finish("search_exhausted")
                alternatives.append(PayloadAlternative({identity: contract.id}, reasons))
            else:
                eligible.append(contract)
        if not eligible:
            diagnostics.append("no_compatible_contract:" + identity)
        choices.append(tuple(eligible))
    if any(not choice for choice in choices):
        return finish("no_solution")
    total = math.prod(len(choice) for choice in choices)
    winner = None
    for combination in islice(product(*choices), request.constraints.max_combinations):
        if len(alternatives) >= 2048:
            diagnostics.append("selection_record_budget_exhausted:2048")
            return finish("search_exhausted")
        selected = dict(zip(sorted(nodes), combination))
        reasons = list(_connections_and_dependencies(selected, graph, request.library, target))
        construction = None
        if not reasons:
            try:
                construction = _construction(selected, request)
                if not construction.assessment.passed or not construction.assessment.complete:
                    reasons.extend("construction:" + x for x in construction.assessment.diagnostics)
                    if not reasons:
                        reasons.append("construction:incomplete_molecule_set")
                if construction.candidate.bundle is not None:
                    bundle = construction.candidate.bundle
                    if any(x.space.alphabet == "DNA" for x in bundle.molecules):
                        reasons.append("unsupported_final_dna_member:rna_payload_only")
                    molecules = {item.id: item for item in bundle.molecules}
                    complexes = {item.id: item for item in bundle.complexes}
                    delivered = {item.member_id for item in construction.request.requirements
                                 if item.category in {"payload", "delivered_helper"}}
                    for identity in sorted(delivered):
                        member_ids = ((identity,) if identity in molecules else
                                      tuple(item.molecule_id for item in complexes[identity].constituents)
                                      if identity in complexes else ())
                        if not member_ids or any(item not in molecules or molecules[item].space.alphabet != "RNA"
                                                 for item in member_ids):
                            reasons.append("unsupported_delivered_member:rna_payload_only:" + identity)
                    length = sum(len(x.sequence) for x in bundle.molecules
                                 if x.space.alphabet in {"DNA", "RNA"})
                    if request.constraints.max_total_bases is not None and length > request.constraints.max_total_bases:
                        reasons.append("complete_set_nucleotide_budget_exceeded")
                if not reasons:
                    from biocompiler.verification.executable_payload import check_payload_build
                    candidate_assumptions = tuple(sorted(set((*assumptions,
                        *(value for item in selected.values()
                          for value in (*item.assumptions, *item.component.assumptions))))))
                    trial = PayloadBuild(
                        request.fingerprint, requirements,
                        {key: item.id for key, item in selected.items()},
                        _selected_mechanism(selected, graph), construction, (), tuple(diagnostics),
                        candidate_assumptions, "partial" if diagnostics else "compiled")
                    check = check_payload_build(trial, expected_request=request)
                    if not check.passed or not check.construction_complete:
                        reasons.extend("independent_check:" + item for item in check.diagnostics)
                        if not reasons:
                            reasons.append("independent_check:incomplete_construction")
            except (SerializationError, ValueError) as error:
                reasons.append("construction_authority_rejected:" + str(error))
        keys = {key: item.id for key, item in selected.items()}
        alternatives.append(PayloadAlternative(keys, tuple(dict.fromkeys(reasons))))
        if not reasons:
            preference = request.constraints.preferred_contract_ids
            rank = (sum(preference.index(item.id) if item.id in preference else len(preference)
                        for item in combination), length, tuple(keys.values()))
            if winner is None or rank < winner[0]:
                winner = (rank, selected, construction)
    if total > request.constraints.max_combinations:
        diagnostics.append(f"search_budget_exhausted:{request.constraints.max_combinations}_of_{total}")
        return finish("search_exhausted")
    if winner is None:
        return finish("no_solution")
    _, selected, construction = winner
    assumptions = tuple(sorted(set((*assumptions,
                                    *(assumption for item in selected.values()
                                      for assumption in (*item.assumptions, *item.component.assumptions))))))
    return finish("partial" if diagnostics else "compiled",
                  {key: value.id for key, value in selected.items()},
                  _selected_mechanism(selected, graph), construction)


def export_payload_fasta(build, *, expected_request):
    """Export all RNA members only after fresh independent reconstruction.

    Chemistry and non-nucleotide members remain in the complete JSON build.
    FASTA by itself cannot carry a complete molecular specification.
    """
    from biocompiler.verification.executable_payload import check_payload_build
    result = check_payload_build(build, expected_request=expected_request)
    require(result.outcome == "pass" and result.construction_complete and build.construction is not None,
            "FASTA export requires fresh verified construction.")
    lines = []
    for member in build.construction.candidate.bundle.molecules:
        if member.space.alphabet == "RNA":
            lines.append(">" + member.id + " alphabet=" + member.space.alphabet)
            lines.extend(member.sequence[i:i + 80] for i in range(0, len(member.sequence), 80))
    require(bool(lines), "No RNA members in this construction.")
    return "\n".join(lines) + "\n"
