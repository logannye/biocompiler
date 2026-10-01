"""Distinct source controls compiled through independently supplied RNA contracts.

All material is artificial six-base software authority. No empirical function,
protein identity or human therapeutic admission is established by these cases.
The source and supplier programs below are authored separately, so changing a
source program cannot silently rewrite its expected implementation behavior.
"""

import argparse
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.ir.circuit_intent import CircuitRequest, CircuitRequirement, ExecutableCircuitBehavior
from biocompiler.ir.payload_architecture import (
    ArchitectureBinding, ArchitectureControl, ArchitectureOutputBinding, ArchitecturePlacement,
    ControlRequirement, PayloadArchitectureLibrary, PayloadArchitectureRefinement,
    RecipientDeliveryGroup, RNAArchitectureConstraints,
)

from examples.circuit_intent import observation
from examples.executable_payload import artificial_template
from examples.payload_architectures import ASSUMPTION, _component, _freeze


CASES = ("memory_reset", "state_reset", "production_adjustment", "activity_control")


def source_program(case, *, false_control=False, coupled=False):
    """Original therapeutic source; false_control is a deliberate adversary."""
    therapy = bc.Therapy("control_source_" + case)
    cell = therapy.engineer("recipient", cell_type="human_T_cell")
    if case == "memory_reset":
        context = cell.environment.signal("context").present()
        reset = cell.environment.signal("reset").present()
        memory = cell.memory("licensed", set_when=context, reset_when=~reset if false_control else reset)
        cell.when(memory.is_set()).do(cell.secrete("artificial_alpha"))
    elif case == "state_reset":
        context = cell.environment.signal("context").present()
        reset = cell.environment.signal("reset").present()
        phase = cell.state("phase", values=("idle", "primed", "active"), initial="idle")
        cell.when(reset).do(phase.set("active" if false_control else "idle"))
        cell.when(~reset & context & phase.is_("idle")).do(phase.set("primed"))
        cell.when(~reset & context & phase.is_("primed")).do(phase.set("active"))
        cell.when(~reset & phase.is_("active")).do(cell.secrete("artificial_alpha"))
    elif case == "production_adjustment":
        adjust = cell.environment.signal("adjust").present()
        basal = cell.secretion("basal", product="artificial_alpha")
        boosted = cell.secretion("boosted", product="artificial_alpha")
        cell.when(~adjust).do(basal.produce(rate=bc.ProductionRate(1)))
        cell.when(adjust).do(boosted.produce(rate=bc.ProductionRate(1 if false_control else 3)))
    elif case == "activity_control":
        activate = cell.environment.signal("activate").present()
        context = cell.environment.signal("context").present()
        cell.when((~activate if false_control else activate) & context).do(cell.rest())
    elif case == "production_independence":
        a = cell.environment.signal("adjust_A").present()
        b = cell.environment.signal("adjust_B").present()
        first = cell.secretion("named_A", product="artificial_alpha")
        additional = cell.secretion("additional_A", product="artificial_alpha")
        cell.when(a).do(first.produce(rate=bc.ProductionRate(3)))
        cell.when(~a & b if coupled else ~a).do(additional.produce(rate=bc.ProductionRate(1)))
        cell.when(b).do(cell.secrete("artificial_beta", rate=bc.ProductionRate(4)))
    else:
        raise ValueError("Unknown control example.")
    return therapy.freeze()


def contract_program(case, *, false_control=False, coupled=False):
    """Independent supplier authority; it never reads the source program."""
    model = bc.Therapy("supplied_control_" + case)
    recipient = model.engineer("recipient", cell_type="human_T_cell")
    if case == "memory_reset":
        setting = recipient.environment.signal("context").present()
        clear = recipient.environment.signal("reset").present()
        latch = recipient.memory("licensed", set_when=setting, reset_when=~clear if false_control else clear)
        recipient.when(latch.is_set()).do(recipient.secrete("artificial_alpha"))
    elif case == "state_reset":
        priming = recipient.environment.signal("context").present()
        clear = recipient.environment.signal("reset").present()
        mode = recipient.state("phase", values=("idle", "primed", "active"), initial="idle")
        recipient.when(clear).do(mode.set("active" if false_control else "idle"))
        recipient.when(~clear & priming & mode.is_("idle")).do(mode.set("primed"))
        recipient.when(~clear & priming & mode.is_("primed")).do(mode.set("active"))
        recipient.when(~clear & mode.is_("active")).do(recipient.secrete("artificial_alpha"))
    elif case == "production_adjustment":
        selector = recipient.environment.signal("adjust").present()
        low = recipient.secretion("basal", product="artificial_alpha")
        high = recipient.secretion("boosted", product="artificial_alpha")
        recipient.when(~selector).do(low.produce(rate=bc.ProductionRate(1)))
        recipient.when(selector).do(high.produce(rate=bc.ProductionRate(1 if false_control else 3)))
    elif case == "activity_control":
        enable = recipient.environment.signal("activate").present()
        environment = recipient.environment.signal("context").present()
        recipient.when((~enable if false_control else enable) & environment).do(recipient.rest())
    elif case == "production_independence":
        first_selector = recipient.environment.signal("adjust_A").present()
        second_selector = recipient.environment.signal("adjust_B").present()
        upper = recipient.secretion("named_A", product="artificial_alpha")
        lower = recipient.secretion("additional_A", product="artificial_alpha")
        recipient.when(first_selector).do(upper.produce(rate=bc.ProductionRate(3)))
        recipient.when(~first_selector & second_selector if coupled else ~first_selector).do(lower.produce(rate=bc.ProductionRate(1)))
        recipient.when(second_selector).do(recipient.secrete("artificial_beta", rate=bc.ProductionRate(4)))
    else:
        raise ValueError("Unknown supplied control model.")
    return model.freeze()


def _outputs(behavior):
    nodes = {node.id: node for node in behavior.nodes}
    groups = {}
    for node in behavior.nodes:
        if node.kind == "action.secrete":
            key = nodes[node.inputs[0]].attributes["product"]
        elif node.kind == "action.rest":
            key = "artificial_rest_activity"
        else:
            continue
        groups.setdefault(key, []).append(node.id)
    outputs = []
    for index, (identity, actions) in enumerate(sorted(groups.items())):
        activity = nodes[actions[0]].kind == "action.rest"
        product = bc.CircuitProduct(identity,
                    bc.ProductKind.BIOLOGICAL_ACTIVITY if activity else bc.ProductKind.PROTEIN_EXPRESSION,
                    observation("control.readout." + str(index),
                                bc.QuantityKind.DOWNSTREAM_ACTIVITY if activity else bc.QuantityKind.TRANSLATION_RATE,
                                bc.ObservationScope.EVALUATOR))
        lifecycle = bc.CircuitLifecycle("activity_control" if activity else "production_control")
        outputs.append(("response." + str(index), tuple(actions), product, lifecycle))
    return tuple(outputs)


def _circuit(source):
    target = source.target
    profile = bc.CircuitProfileRequest(
        "human_immune_payload", "candidate_design", bc.PayloadFormat.RNA, "planning", target,
        bc.ImmuneRecipientIdentity(bc.ImmuneLineage.T_CELL, target.fingerprint,
                                  target.human_target.cell_subtype.fingerprint), source_request=source)
    behavior = lower_to_behavior(source)
    role = next(node.id for node in source.intent.nodes if node.kind == "role")
    requirements = tuple(CircuitRequirement(identity,
                         ExecutableCircuitBehavior((), behavior, product, lifecycle, action_ids=actions),
                         role, tuple(node.id for node in source.intent.nodes), None)
                         for identity, actions, product, lifecycle in _outputs(behavior))
    return CircuitRequest(profile, requirements, "delivered_rna", "complete_nominal", "declared-control-rna")


def _control_targets(behavior, case):
    nodes = {node.id: node for node in behavior.nodes}
    if case in {"memory_reset", "state_reset"}:
        target = next(node.id for node in behavior.nodes if node.kind == ("memory" if case == "memory_reset" else "state"))
        return (("memory_reset", (target,), "reset"),)
    if case == "activity_control":
        return (("activity_control", tuple(node.id for node in behavior.nodes if node.kind == "action.rest"), "activate"),)
    groups = {}
    for node in behavior.nodes:
        if node.kind == "action.secrete":
            groups.setdefault(nodes[node.inputs[0]].attributes["product"], []).append(node.id)
    return tuple(("production_adjustment", tuple(actions),
                  ("adjust_A" if product == "artificial_alpha" else "adjust_B")
                  if case == "production_independence" else "adjust")
                 for product, actions in sorted(groups.items()))


def supplied_refinement(case, *, false_control=False, coupled=False, omit_aggregate=False):
    behavior = lower_to_behavior(_freeze(contract_program(case, false_control=false_control, coupled=coupled), "A"))
    nodes = {node.id: node for node in behavior.nodes}
    role = next(node.id for node in behavior.nodes if node.kind == "role")
    owned = tuple(node.id for node in behavior.nodes
                  if node.kind in {"rule", "state", "memory"} or node.kind.startswith("action."))
    template = artificial_template("control-rna", role)
    placement = ArchitecturePlacement("control-rna.payload.delivery", template.id, "payload", role,
                                      "cytoplasm", "delivery." + role)
    targets = _control_targets(behavior, case)
    component_ids = tuple("control-component-" + str(index) for index in range(len(targets)))
    components = tuple(_component(identity, behavior, role) for identity in component_ids)
    bindings = []
    controls = []
    for index, (kind, actions, signal_name) in enumerate(targets):
        relevant = owned if len(targets) == 1 else tuple(ref for ref in owned if ref in actions
                    or nodes[ref].kind == "rule" and set(nodes[ref].inputs[2:]).intersection(actions))
        bindings.append(ArchitectureBinding("ownership." + str(index), relevant, (component_ids[index],),
                                             (template.id,), (placement.id,)))
        signal = next(node.id for node in behavior.nodes if node.kind == "signal" and node.attributes["name"] == signal_name)
        claimed = actions[:1] if omit_aggregate and kind == "production_adjustment" else actions
        controls.append(ArchitectureControl("control." + str(index), kind, claimed, (signal,),
                        (component_ids[index],), "domain." + str(index), (ASSUMPTION,)))
    outputs = tuple(ArchitectureOutputBinding("output." + str(index), identity, actions, product, lifecycle)
                    for index, (identity, actions, product, lifecycle) in enumerate(_outputs(behavior)))
    return PayloadArchitectureRefinement("supplied-" + case, "1", behavior,
            {node.id: node.id for node in behavior.nodes}, owned, components, (template,), tuple(bindings),
            (placement,), (ASSUMPTION,), controls=tuple(controls), output_contracts=outputs)


def make_control_request(case="memory_reset", *, false_control=False, coupled=False, omit_aggregate=False):
    """Complete human immune RNA request with separately supplied model/material.

    The four normal cases are in CASES. production_independence is an additional
    two-product regression; coupled=True must be rejected for cross-influence.
    false_control makes coherent but functionally false source/model examples.
    omit_aggregate removes part of the declared production material scope.
    """
    source = _freeze(source_program(case, false_control=false_control, coupled=coupled), "A")
    circuit = _circuit(source)
    model = supplied_refinement(case, false_control=false_control, coupled=coupled, omit_aggregate=omit_aggregate)
    role = next(node.id for node in source.intent.nodes if node.kind == "role")
    targets = _control_targets(lower_to_behavior(source), case)
    constraints = RNAArchitectureConstraints(exact_count=1,
        delivery_groups=(RecipientDeliveryGroup("delivery." + role, (role,), "co_delivered", True,
                         ("All declared RNA members are assumed present in the same recipient cell.",)),),
        control_requirements=(ControlRequirement("source-control-" + case, targets[0][0],
            tuple(actions[0] for _, actions, _ in targets),
            "independent" if case == "production_independence" else "shared"),))
    return bc.PayloadArchitectureRequest("artificial-control-" + case, circuit,
            PayloadArchitectureLibrary("independent-control-contracts", (model,), (ASSUMPTION,)), constraints)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=(*CASES, "production_independence", "all"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    for case in CASES if args.case == "all" else (args.case,):
        request = make_control_request(case)
        build = bc.compile_payload_architecture(request)
        exported = bc.export_payload_architecture(build, expected_request=request)
        if args.output is not None:
            directory = args.output / case
            directory.mkdir(parents=True, exist_ok=True)
            for name, record in (("request", request), ("build", build)):
                (directory / (name + ".json")).write_text(record.to_json() + "\n", encoding="utf-8")
            (directory / "payloads.fasta").write_text(exported.fasta, encoding="utf-8")
            (directory / "manifest.json").write_text(json.dumps(exported.to_dict()["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(case, build.status, flush=True)


if __name__ == "__main__":
    main()
