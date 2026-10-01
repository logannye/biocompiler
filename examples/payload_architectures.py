"""Artificial, independently authored A–F RNA architecture contracts.

Every sequence is a six-symbol software control. The source program and supplied
model are authored separately below; a source edit does not change model
contracts or supplied bases. Nothing here declares empirical therapeutic function.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.architecture_build import PayloadArchitectureRequest
from biocompiler.ir.behavior import BEHAVIOR_V2
from biocompiler.ir.circuit_intent import CircuitRequest, CircuitRequirement, ExecutableCircuitBehavior
from biocompiler.ir.component_contracts import ComponentRecord, DependencyRequirement, PinnedIdentity, ProvidedCapability
from biocompiler.ir.payload_architecture import (
    ArchitectureBinding, ArchitectureChannel, ArchitectureControl, ArchitectureHelper,
    ArchitectureOutputBinding, ArchitecturePlacement, ControlRequirement,
    PayloadArchitectureLibrary, PayloadArchitectureRefinement,
    RecipientDeliveryGroup, RNAArchitectureConstraints,
)
from biocompiler.semantics.component_contracts import OperatingDomain, PortContract, TEMPORAL_LEVEL_TIMING, ValueDomain
from biocompiler.semantics.types import BOOLEAN

from examples.circuit_intent import observation
from examples.executable_payload import artificial_template
from examples.human_target import make_human_target


ASSUMPTION = "The supplied artificial material conditionally implements the complete declared executable model; empirical function is unknown."


def source_program(case="A", *, product="artificial_alpha"):
    """Therapeutic source authoring, independently editable from supplied models."""
    case = case.upper()
    therapy = bc.Therapy("architecture_source_" + case)
    if case in {"A", "E"}:
        cell = therapy.engineer("recipient", cell_type="human_T_cell")
        context = cell.environment.signal("context").present()
        stop_alpha = cell.environment.signal("stop_alpha").present()
        stop_beta = cell.environment.signal("stop_beta").present()
        cell.when(context & ~stop_alpha).do(cell.secrete(product))
        cell.when(context & ~stop_beta).do(cell.secrete("artificial_beta"))
    elif case == "B":
        cell = therapy.engineer("recipient", cell_type="human_T_cell")
        context = cell.environment.signal("context").present()
        reset = cell.environment.signal("reset").present()
        stop = cell.environment.signal("shutdown").present()
        phase = cell.state("phase", values=("prime", "act", "recover"), initial="prime")
        allowed = ~reset & ~stop
        cell.when(phase.is_("prime") & context & allowed).do(phase.set("act"))
        cell.when(phase.is_("act").held_for(bc.Duration(2)) & allowed).do(phase.set("recover"))
        cell.when(reset & ~stop).do(phase.set("prime"))
        cell.when(stop).do(phase.set("recover"))
        cell.when(phase.is_("act") & allowed).do(cell.secrete(product))
    elif case == "C":
        cell = therapy.engineer("recipient", cell_type="human_T_cell")
        drive = cell.environment.signal("drive", type=bc.Level)
        measured = cell.internal.signal("measured_activity", type=bc.Level)
        stop = cell.environment.signal("shutdown").present()
        budget = measured.integrated(over=bc.Duration(10)) < bc.Duration(5)
        allowed = budget & ~stop
        cell.when((drive <= 0) & allowed).do(cell.secrete(product, rate=bc.ProductionRate(0)))
        cell.when((drive > 0) & (drive < 2) & allowed).do(cell.secrete(product, rate=drive * bc.ProductionRate(1)))
        cell.when((drive >= 2) & allowed).do(cell.secrete(product, rate=bc.ProductionRate(2)))
    elif case in {"D", "F"}:
        sender = therapy.engineer("sender", cell_type="human_T_cell")
        receiver = therapy.engineer("receiver", cell_type="human_T_cell")
        channel = therapy.channel("artificial_alert", scope="local", type=bc.Level)
        context = sender.environment.signal("context").present()
        sender.when(context).do(sender.emit(channel, value=1))
        received = receiver.sense(channel)
        stop = receiver.environment.signal("shutdown").present()
        active = (received > 0) & ~stop
        if case == "F":
            reset = receiver.environment.signal("reset").present()
            phase = receiver.state("phase", values=("prime", "act", "recover"), initial="prime")
            measured = receiver.internal.signal("measured_activity", type=bc.Level)
            budget = measured.integrated(over=bc.Duration(10)) < bc.Duration(5)
            allowed = ~reset & ~stop
            receiver.when(phase.is_("prime") & active & allowed).do(phase.set("act"))
            receiver.when(phase.is_("act").held_for(bc.Duration(2)) & allowed).do(phase.set("recover"))
            receiver.when(reset & ~stop).do(phase.set("prime"))
            receiver.when(stop).do(phase.set("recover"))
            active = active & phase.is_("act") & budget & allowed
        receiver.when(active).do(receiver.secrete(product))
    else:
        raise ValueError("Architecture example must be one of A, B, C, D, E or F.")
    return therapy.freeze()


def contract_program(case="A"):
    """Independent supplier model; deliberately never consumes source artifacts."""
    case = case.upper()
    model = bc.Therapy("supplied_contract_" + case)
    if case in {"A", "E"}:
        recipient = model.engineer("recipient", cell_type="human_T_cell")
        enabled = recipient.environment.signal("context").present()
        first_stop = recipient.environment.signal("stop_alpha").present()
        second_stop = recipient.environment.signal("stop_beta").present()
        recipient.when(enabled & ~first_stop).do(recipient.secrete("artificial_alpha"))
        recipient.when(enabled & ~second_stop).do(recipient.secrete("artificial_beta"))
    elif case == "B":
        recipient = model.engineer("recipient", cell_type="human_T_cell")
        priming = recipient.environment.signal("context").present()
        clear = recipient.environment.signal("reset").present()
        shutdown = recipient.environment.signal("shutdown").present()
        mode = recipient.state("phase", values=("prime", "act", "recover"), initial="prime")
        operate = ~clear & ~shutdown
        recipient.when(mode.is_("prime") & priming & operate).do(mode.set("act"))
        recipient.when(mode.is_("act").held_for(bc.Duration(2)) & operate).do(mode.set("recover"))
        recipient.when(clear & ~shutdown).do(mode.set("prime"))
        recipient.when(shutdown).do(mode.set("recover"))
        recipient.when(mode.is_("act") & operate).do(recipient.secrete("artificial_alpha"))
    elif case == "C":
        recipient = model.engineer("recipient", cell_type="human_T_cell")
        amount = recipient.environment.signal("drive", type=bc.Level)
        activity = recipient.internal.signal("measured_activity", type=bc.Level)
        shutdown = recipient.environment.signal("shutdown").present()
        under_limit = activity.integrated(over=bc.Duration(10)) < bc.Duration(5)
        operate = under_limit & ~shutdown
        recipient.when((amount <= 0) & operate).do(recipient.secrete("artificial_alpha", rate=bc.ProductionRate(0)))
        recipient.when((amount > 0) & (amount < 2) & operate).do(recipient.secrete("artificial_alpha", rate=amount * bc.ProductionRate(1)))
        recipient.when((amount >= 2) & operate).do(recipient.secrete("artificial_alpha", rate=bc.ProductionRate(2)))
    elif case in {"D", "F"}:
        origin = model.engineer("sender", cell_type="human_T_cell")
        destination = model.engineer("receiver", cell_type="human_T_cell")
        alert = model.channel("artificial_alert", scope="local", type=bc.Level)
        announce = origin.environment.signal("context").present()
        origin.when(announce).do(origin.emit(alert, value=1))
        local_value = destination.sense(alert)
        shutdown = destination.environment.signal("shutdown").present()
        enabled = (local_value > 0) & ~shutdown
        if case == "F":
            clear = destination.environment.signal("reset").present()
            mode = destination.state("phase", values=("prime", "act", "recover"), initial="prime")
            activity = destination.internal.signal("measured_activity", type=bc.Level)
            under_limit = activity.integrated(over=bc.Duration(10)) < bc.Duration(5)
            operate = ~clear & ~shutdown
            destination.when(mode.is_("prime") & enabled & operate).do(mode.set("act"))
            destination.when(mode.is_("act").held_for(bc.Duration(2)) & operate).do(mode.set("recover"))
            destination.when(clear & ~shutdown).do(mode.set("prime"))
            destination.when(shutdown).do(mode.set("recover"))
            enabled = enabled & mode.is_("act") & under_limit & operate
        destination.when(enabled).do(destination.secrete("artificial_alpha"))
    else:
        raise ValueError("Unknown supplied architecture model.")
    return model.freeze()


def _freeze(program, case):
    constraints = {"execution": {"integral_step": bc.Duration(1).to_dict()}} if case in {"C", "F"} else {}
    return BuildRequest.freeze(program, target=make_human_target(), behavior_profile=BEHAVIOR_V2,
                               implementation_constraints=constraints)


def _product_groups(behavior):
    nodes = {node.id: node for node in behavior.nodes}
    groups = {}
    for node in behavior.nodes:
        if node.kind == "action.secrete":
            product = nodes[node.inputs[0]].attributes["product"]
            groups.setdefault((node.role, product), []).append(node.id)
    return {key: tuple(sorted(values)) for key, values in sorted(groups.items())}


def _output_product(product, index):
    return bc.CircuitProduct(product, bc.ProductKind.PROTEIN_EXPRESSION,
                             observation("readout." + str(index), bc.QuantityKind.TRANSLATION_RATE,
                                         bc.ObservationScope.EVALUATOR))


def _circuit(source):
    target = source.target
    behavior = lower_to_behavior(source)
    profile = bc.CircuitProfileRequest(
        "human_immune_payload", "candidate_design", bc.PayloadFormat.RNA, "planning", target,
        bc.ImmuneRecipientIdentity(bc.ImmuneLineage.T_CELL, target.fingerprint,
                                  target.human_target.cell_subtype.fingerprint), source_request=source)
    requirements = []
    for index, ((role, product), actions) in enumerate(_product_groups(behavior).items()):
        output = _output_product(product, index)
        declared = ExecutableCircuitBehavior((), behavior, output, bc.CircuitLifecycle("production_control"),
                                              action_ids=actions)
        relevant = tuple(node.id for node in source.intent.nodes
                         if node.id == role or node.kind != "role" and node.role in (None, role))
        requirements.append(CircuitRequirement("response." + str(index), declared, role, relevant, None))
    return CircuitRequest(profile, tuple(requirements), "delivered_rna", "complete_nominal",
                          "declared-human-rna-architecture")


def _component(identity, behavior, role, *, helper=False, dependencies=()):
    ports = (PortContract("out", "output", "artificial-composite-status", BOOLEAN, "1", role, "cell",
                          "cytoplasm", TEMPORAL_LEVEL_TIMING, ValueDomain.boolean(), ValueDomain.boolean()),)
    return ComponentRecord(identity, "1", "modeled_component", "supplied_composite_behavior", ("RNA",),
                           ports, OperatingDomain(),
                           (PinnedIdentity("model", "independent-composite-model", "1", behavior.fingerprint),),
                           assumptions=(ASSUMPTION,), dependencies=dependencies,
                           capabilities=(ProvidedCapability("artificial_helper", role, "cell", "cytoplasm"),) if helper else ())


def supplied_refinement(case, variant="one_rna", *, shared_shutdown=False):
    """Build a supplied alternative from independent model and literal material authority."""
    behavior = lower_to_behavior(_freeze(contract_program(case), case))
    nodes = {node.id: node for node in behavior.nodes}
    roles = tuple(node.id for node in behavior.nodes if node.kind == "role")
    owned = tuple(node.id for node in behavior.nodes
                  if node.kind in {"rule", "state", "memory"} or node.kind.startswith("action."))
    identity = case.lower() + "." + variant + (".shared_shutdown" if shared_shutdown else "")
    components, templates, bindings, placements, helpers, controls = [], [], [], [], [], []
    # Templates are chosen before construction, not split or concatenated after
    # compilation. Different physical alternatives are explicit supplied records.
    per_role_count = {"one_rna": 1, "one_rna_helper": 1, "two_rna": 2, "three_rna": 3,
                      "many_components_one_rna": 1, "one_component_two_rna": 2}[variant]
    delivered_helper = variant == "one_rna_helper" or case in {"D", "F"}
    for role_index, role in enumerate(roles):
        role_owned = tuple(ref for ref in owned if nodes[ref].role == role)
        component_ids = ((f"{identity}.role{role_index}.logic", f"{identity}.role{role_index}.effector")
                         if variant == "many_components_one_rna" or case in {"A", "E"} and variant in {"two_rna", "three_rna"}
                         else (f"{identity}.role{role_index}.composite",))
        helper_id = f"{identity}.role{role_index}.helper"
        dependency = (DependencyRequirement("needs_helper", "artificial_helper", role, "cell", "cytoplasm"),) if delivered_helper else ()
        for component_id in component_ids:
            components.append(_component(component_id, behavior, role, dependencies=dependency))
        local_template_ids = []
        for index in range(per_role_count):
            template_id = f"role{role_index}.rna{index}"
            # Alternate literal six-base spellings are supplied authority; bases
            # are never inferred from the Behavior model or output product name.
            template = artificial_template(template_id, role, helper=delivered_helper and index == 0)
            if index:
                source = template.sources[0]
                molecule = replace(source.molecule, sequence="UGCAUG")
                template = replace(template, sources=(replace(source, molecule=molecule),))
            templates.append(template)
            local_template_ids.append(template_id)
            for member in template.output_members:
                placements.append(ArchitecturePlacement(f"{template_id}.{member.id}.delivery", template_id, member.id,
                                                        role, "cytoplasm", "delivery." + role))
        for component_index, component_id in enumerate(component_ids):
            allocated = tuple(ref for index, ref in enumerate(local_template_ids)
                              if len(component_ids) == 1 or len(local_template_ids) == 1
                              or index % len(component_ids) == component_index)
            bindings.append(ArchitectureBinding(f"role{role_index}.ownership{component_index}", role_owned,
                                                 (component_id,), allocated,
                                                 tuple(ref + ".payload.delivery" for ref in allocated)))
        if delivered_helper:
            components.append(_component(helper_id, behavior, role, helper=True))
            bindings.append(ArchitectureBinding(f"role{role_index}.helper_material", role_owned,
                                                 (helper_id,), (local_template_ids[0],),
                                                 (local_template_ids[0] + ".helper.delivery",)))
            helpers.append(ArchitectureHelper(
                helper_id, "artificial_helper", component_ids, role, "cytoplasm", "other_rna",
                "available_at_start", "shared", len(component_ids),
                ("The helper RNA and payload RNA are assumed available in the same recipient from startup.",),
                local_template_ids[0] + ".helper.delivery", helper_id))
        actions = tuple(node.id for node in behavior.nodes if node.role == role and node.kind == "action.secrete")
        context_nodes = tuple(node.id for node in behavior.nodes if node.role == role and node.kind == "qualitative"
                              and nodes[node.inputs[0]].attributes.get("name") == "context")
        if actions:
            controls.append(ArchitectureControl(f"role{role_index}.activation", "activation", actions,
                                                  context_nodes, component_ids, f"role{role_index}.activation-domain", (ASSUMPTION,)))
        for action_index, action in enumerate(actions):
            stop_name = ("stop_alpha" if action_index == 0 else "stop_beta") if case in {"A", "E"} else "shutdown"
            stop_nodes = tuple(node.id for node in behavior.nodes if node.role == role and node.kind == "signal"
                               and node.attributes.get("name") == stop_name)
            domain = (f"role{role_index}.stop-shared" if shared_shutdown
                      else f"role{role_index}.stop-{action_index}")
            controls.append(ArchitectureControl(f"role{role_index}.shutdown-{action_index}", "shutdown", (action,),
                                                  stop_nodes, (component_ids[action_index % len(component_ids)],), domain, (ASSUMPTION,)))
    channels = []
    for channel in (node for node in behavior.nodes if node.kind == "channel"):
        emit = next(node for node in behavior.nodes if node.kind == "action.emit" and channel.id in node.inputs)
        receiver = next(node for node in behavior.nodes if node.kind == "channel_observation" and channel.id in node.inputs)
        channels.append(ArchitectureChannel("transport." + channel.id, channel.id, emit.role, receiver.role,
                                             emit.id, receiver.id, 1, 2, "clear", "single_sender", bc.Level(0).to_dict(),
                                             ("Declared transport latency is one second; persistence is two seconds; loss clears receiver signal.",)))
    outputs = tuple(ArchitectureOutputBinding("output." + str(index), "response." + str(index), actions,
                                              _output_product(product, index), bc.CircuitLifecycle("production_control"))
                    for index, ((role, product), actions) in enumerate(_product_groups(behavior).items()))
    return PayloadArchitectureRefinement(identity, "1", behavior, {node.id: node.id for node in behavior.nodes}, owned,
                                          tuple(components), tuple(templates), tuple(bindings), tuple(placements),
                                          (ASSUMPTION,), controls=tuple(controls), helpers=tuple(helpers),
                                          channels=tuple(channels), output_contracts=outputs)


def make_architecture_request(case="A", *, variants=None, exact_count=None, max_count=None,
                              independent_shutdown=False, shared_shutdown=False,
                              source_product="artificial_alpha", require_complete=False):
    case = case.upper()
    source = _freeze(source_program(case, product=source_product), case)
    circuit = _circuit(source)
    if variants is None:
        variants = (("many_components_one_rna", "one_component_two_rna") if case == "E" else
                    ("one_rna", "two_rna", "one_rna_helper") if case == "A" else ("one_rna",))
    refinements = tuple(supplied_refinement(case, variant, shared_shutdown=shared_shutdown) for variant in variants)
    role_ids = tuple(node.id for node in source.intent.nodes if node.kind == "role")
    delivery = tuple(RecipientDeliveryGroup("delivery." + role, (role,), "co_delivered", True,
                                            ("All RNA members in this role's group are assumed present in the same recipient cell.",))
                     for role in role_ids)
    controls = ()
    if independent_shutdown:
        actions = tuple(node.id for node in source.intent.nodes if node.kind == "action.secrete")
        controls = (ControlRequirement("independent-output-shutdown", "shutdown", actions, "independent"),)
    constraints = RNAArchitectureConstraints(exact_count=exact_count, max_count=max_count,
                                              delivery_groups=delivery, control_requirements=controls,
                                              require_complete=require_complete)
    return PayloadArchitectureRequest("artificial-architecture-" + case.lower(), circuit,
                                       PayloadArchitectureLibrary("independent-artificial-architectures", refinements), constraints)


def main(argv=None):
    from biocompiler.compiler.payload_architecture import compile_payload_architecture, export_payload_architecture
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=tuple("ABCDEF") + ("all",), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    cases = "ABCDEF" if args.case == "all" else args.case
    for case in cases:
        request = (make_architecture_request(case, variants=("one_rna", "many_components_one_rna", "two_rna", "one_rna_helper"),
                                             independent_shutdown=True) if case == "A" else make_architecture_request(case))
        build = compile_payload_architecture(request)
        if args.output is not None:
            directory = args.output / case.lower()
            directory.mkdir(parents=True, exist_ok=True)
            for name, record in (("request", request), ("build", build)):
                (directory / (name + ".json")).write_text(record.to_json() + "\n", encoding="utf-8")
        print(case, build.status, flush=True)
        if build.construction is not None:
            exported = export_payload_architecture(build, expected_request=request)
            if args.output is not None:
                (directory / "payloads.fasta").write_text(exported.fasta, encoding="utf-8")
                (directory / "manifest.json").write_text(
                    json.dumps(exported.to_dict()["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
            else:
                print(exported.fasta, end="")
        else:
            for diagnostic in build.diagnostics:
                print(" ", diagnostic.category + ":", diagnostic.code)


if __name__ == "__main__":
    main()
