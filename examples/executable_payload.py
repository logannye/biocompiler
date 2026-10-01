"""Compile artificial RNA records under explicit executable software contracts.

Six-symbol strings are deliberately nonfunctional software fixtures. The example
exercises source-to-sequence translation and supplies no biological mechanism,
therapeutic sequence, experimental evidence or human-use admission.
"""

import argparse
from dataclasses import replace
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.executable_payload import compile_payload, export_payload_fasta
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.circuit_construction import MemberRequirement, OutputMember, RoleDeclaration, RootSource, ValueRef
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.component_contracts import ComponentRecord, PinnedIdentity, SyntheticOperatorModel
from biocompiler.ir.executable_payload import PayloadCircuitBinding, PayloadCompilationRequest
from biocompiler.ir.intent import thaw_json
from biocompiler.ir.payload_contracts import PayloadComponentContract, PayloadContractLibrary, PayloadPortBinding, PayloadTemplate
from biocompiler.semantics.component_contracts import (
    OperatingDomain, PortContract, TEMPORAL_EVENT_TIMING, TEMPORAL_LEVEL_TIMING,
    ValueDomain, canonical_synthetic_unit,
)
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.semantics.payload_requirements import extract_payload_requirements

try:
    from examples.circuit_intent import observation
    from examples.circuit_molecules import fixture_provenance, make_molecule
    from examples.human_target import make_human_target
except ModuleNotFoundError:
    from circuit_intent import observation
    from circuit_molecules import fixture_provenance, make_molecule
    from human_target import make_human_target


def artificial_template(identity, role_id, *, helper=False):
    """Complete independent RNA spelling, chemistry and region authority."""
    provenance = fixture_provenance("executable-payload:" + identity)
    sources, members, requirements, structures = [], [], [], []
    for member_id, sequence, category in (
        ("payload", "ACGUAC", "payload"),
        *((("helper", "UGCAUG", "delivered_helper"),) if helper else ()),
    ):
        molecule = make_molecule(member_id + ".root", sequence, coding_status="noncoding")
        region = MoleculeFeature("contract-region", "artificial_contract_region",
                                 CoordinatePath(molecule.space.id, (IndexSpan(0, 6),), "+"), provenance)
        molecule = replace(molecule, features=(region,))
        sources.append(RootSource(member_id + ".source", molecule, provenance))
        members.append(OutputMember(member_id, ValueRef("root", member_id + ".source"),
                                    member_id + ".final", "delivered_rna", "complete", "noncoding", provenance))
        requirements.append(MemberRequirement(
            "required." + member_id, category, member_id, None, None,
            (RoleDeclaration("role." + member_id, role_id,
                             "helper" if category == "delivered_helper" else "requested_payload", "cytoplasm"),)))
        if category == "payload":
            structures.append(PayloadStructureContract(
                member_id, "delivered_rna", "linear",
                (RequiredPayloadRegion("contract-region", "artificial_contract_region"),), provenance))
    return PayloadTemplate(identity, tuple(sources), (), tuple(members), tuple(requirements),
                           payload_structures=tuple(structures))


def supplied_artificial_library(requirements, *, helper=True):
    """Author a distinct exact formal contract for every required software node.

    This convenience constructs a test library, not a biological design library.
    Production callers supply their own independently authored sequence templates
    and executable behavior contracts.
    """
    graph = requirements.mechanism
    nodes = {node.id: node for node in graph.nodes}
    outputs = {output.id: output for output in requirements.outputs}

    def timing(node):
        if node.kind == "onset":
            return TEMPORAL_EVENT_TIMING
        if node.kind == "any_contact" and timing(nodes[node.inputs[0]]) == TEMPORAL_EVENT_TIMING:
            return TEMPORAL_EVENT_TIMING
        return TEMPORAL_LEVEL_TIMING

    def port(identity, direction, node):
        unit = canonical_synthetic_unit(node.output.dtype)
        domain = (ValueDomain.boolean() if node.output.dtype.kind == "condition"
                  else ValueDomain.interval(-1_000_000, 1_000_000, node.output.dtype, unit))
        return PortContract(identity, direction, node.output.id, node.output.dtype, unit,
                            node.role, node.scope, "cytoplasm", timing(node), domain, domain)

    contracts = []
    for index, node in enumerate(sorted(graph.nodes, key=lambda item: item.id)):
        identity = f"artificial.{index:03d}.{node.kind}"
        inputs = tuple(f"in{position}" for position in range(len(node.inputs)))
        model = SyntheticOperatorModel(node.kind, node.attributes, inputs)
        ports = tuple(port(port_id, "input", nodes[ref]) for port_id, ref in zip(inputs, node.inputs))
        component = ComponentRecord(
            identity, "1", "synthetic_model", node.kind, ("RNA",), (*ports, port("out", "output", node)),
            OperatingDomain(), (PinnedIdentity("model", identity, "1", model.fingerprint),),
            synthetic_model=model)
        template = None if node.kind == "input" else artificial_template(identity + ".template", node.role,
                                                                          helper=helper and node.kind == "output")
        bindings = tuple(PayloadPortBinding(item.id, None if template is None else "payload", "cytoplasm",
                                           None if template is None else "contract-region",
                                           item.meaning if template is None else None) for item in component.ports)
        output = outputs.get(node.id)
        effect = None if output is None else {
            "kind": output.semantics["primitive_action"]["kind"],
            "attributes": thaw_json(output.semantics["primitive_action"]["attributes"]),
            "product": output.product,
        }
        contracts.append(PayloadComponentContract(
            identity, component, template, bindings,
            ("Artificial supplied RNA is assumed to realize this exact software contract; no biological function is established.",),
            effect=effect))
    return PayloadContractLibrary("artificial-rna-contract-library", tuple(contracts),
                                  assumptions=("External software inputs are assumed accessible in the nominated compartment.",))


def make_payload_request(*, guard="and", product="artificial_product", multi_output=False,
                         temporal=False, memory=False, pulse=False, helper=True):
    therapy = bc.Therapy("conditional_artificial_rna")
    cell = therapy.engineer("recipient", cell_type="human_T_cell")
    first = cell.environment.signal("requested_context")
    shutdown = cell.environment.signal("shutdown")
    condition = first.present()
    if memory:
        condition = cell.memory("active", set_when=condition, reset_when=shutdown.present(),
                                duration=bc.Duration(3)).is_set()
    elif temporal:
        condition = condition.held_for(bc.Duration(2))
    condition = condition & ~shutdown.present() if guard == "and" else condition | ~shutdown.present()
    actions = (cell.secrete(product),)
    if multi_output:
        actions += (cell.secrete("artificial_secondary_product"),)
    if pulse:
        cell.on(condition.became_true()).do(*(action.for_(bc.Duration(2)) for action in actions))
    else:
        cell.when(condition).do(*actions)
    target = make_human_target()
    source = BuildRequest.freeze(therapy.freeze(), target=target)
    requirements = extract_payload_requirements(source)
    profile = bc.CircuitProfileRequest(
        "human_immune_payload", "candidate_design", bc.PayloadFormat.RNA, "planning", target,
        bc.ImmuneRecipientIdentity(bc.ImmuneLineage.T_CELL, target.fingerprint,
                                  target.human_target.cell_subtype.fingerprint), source_request=source)
    builder = bc.CircuitBuilder("source-linked-response", profile, role_id=cell.node_id)
    a = builder.observe(observation("context"), first.node_id)
    b = builder.observe(observation("shutdown"), shutdown.node_id)
    response = a & ~b if guard == "and" else a | ~b
    bindings = []
    for index, output in enumerate(requirements.outputs):
        identity = "response." + str(index)
        product_contract = bc.CircuitProduct(
            output.product, bc.ProductKind.PROTEIN_EXPRESSION,
            observation("readout." + str(index), bc.QuantityKind.TRANSLATION_RATE, bc.ObservationScope.EVALUATOR))
        builder.require(identity, response, product_contract, lifecycle=bc.CircuitLifecycle("production_control"),
                        source=(output.rule_id, output.action_id))
        bindings.append(PayloadCircuitBinding(identity, output.rule_id, output.action_id,
                                               {"context": first.node_id, "shutdown": shutdown.node_id}))
    circuit = builder.freeze(requested_form="delivered_rna", fidelity_scope="complete_nominal", deployment_id="declared-human-rna-deployment")
    library = supplied_artificial_library(requirements, helper=helper)
    supplementary = {
        f"output:{binding.rule_id}:{binding.action_id}": next(
            item.behavior for item in circuit.requirements if item.id == binding.requirement_id)
        for binding in bindings
    }
    contracts = []
    for contract in library.contracts:
        if contract.component.synthetic_model.operation == "output":
            behavior = supplementary[contract.component.port(contract.component.synthetic_model.output_port).meaning]
            contract = replace(contract, output_product=behavior.output, output_lifecycle=behavior.lifecycle)
        contracts.append(contract)
    return PayloadCompilationRequest("artificial-rna-payload", circuit,
                                     replace(library, contracts=tuple(contracts)), tuple(bindings))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    request = make_payload_request(multi_output=True)
    build = compile_payload(request)
    fasta = export_payload_fasta(build, expected_request=request)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, record in (("request", request), ("build", build)):
            (args.output / (name + ".json")).write_text(record.to_json() + "\n", encoding="utf-8")
        (args.output / "payloads.fasta").write_text(fasta, encoding="utf-8")
    print("Conditional software translation:", build.status)
    print(fasta, end="")


if __name__ == "__main__":
    main()
