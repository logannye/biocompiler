"""Check independent synthetic candidates against a declared response contract.

The signal graph is a software fixture, not a molecular implementation. Its output
is an abstract request readout, not a prediction of a cellular effect.
Run ``PYTHONPATH=src python examples/realization_check.py`` from the checkout.
"""

from __future__ import annotations

from dataclasses import replace

import cellweave as cw
from cellweave.semantics.types import BOOLEAN


def build_example():
    therapy = cw.Therapy("synthetic_realization")
    cell = therapy.engineer("responder", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    action = cell.rest()
    rule = cell.when(a.present() & b.present()).do(action)
    behavior = cw.lower_to_behavior(therapy.freeze())

    input_a = cw.Observable("A.present", BOOLEAN, cell.role, scope="contact")
    input_b = cw.Observable("B.present", BOOLEAN, cell.role, scope="contact")
    output = cw.Observable("abstract_rest_request_readout", cw.Level, cell.role)
    requirement = cw.ResponseRequirement(
        id="response.rest",
        rule_id=rule.node_id,
        specification_id=action.node_id,
        observable=output,
        active_range=cw.Interval(0.9, 1.1),
        inactive_range=cw.Interval(0, 0.1),
        max_activation_delay=cw.Duration(0.5),
        max_deactivation_delay=cw.Duration(0.5),
    )
    contract = cw.BehaviorContract(
        "rest_contract", behavior.fingerprint, (requirement,)
    )
    domain = cw.OperatingDomain(
        id="two_contact_fixture",
        version="1",
        role=cell.role,
        inputs=(
            cw.InputDomain(a.node_id, "present", input_a, (False, True)),
            cw.InputDomain(b.node_id, "present", input_b, (False, True)),
        ),
        minimum_horizon=cw.Duration(7),
        max_contacts=2,
    )
    target = cw.TargetContext(
        "synthetic_context",
        "1",
        cw.PayloadFormat.RNA,
        capabilities=("synthetic_signal_graph",),
    )

    # This implementation is authored independently of the Behavior IR. A and B
    # are conjoined per contact before reducing to the cell-scoped response.
    def boolean_endpoint(name, *, contact=False):
        return cw.Observable(
            name, BOOLEAN, cell.role, scope="contact" if contact else "cell"
        )

    def level_endpoint(name):
        return cw.Observable(name, cw.Level, cell.role)

    candidate = cw.MechanismProgram(
        name="responsive_fixture",
        nodes=(
            cw.MechanismNode("a", "input", input_a),
            cw.MechanismNode("b", "input", input_b),
            cw.MechanismNode(
                "joint", "and", boolean_endpoint("joint", contact=True), ("a", "b")
            ),
            cw.MechanismNode(
                "any_joint", "any_contact", boolean_endpoint("any_joint"), ("joint",)
            ),
            cw.MechanismNode(
                "zero", "constant", level_endpoint("zero"), attributes={"value": 0}
            ),
            cw.MechanismNode(
                "one", "constant", level_endpoint("one"), attributes={"value": 1}
            ),
            cw.MechanismNode(
                "level",
                "select",
                level_endpoint("selected_level"),
                ("any_joint", "one", "zero"),
            ),
            cw.MechanismNode(
                "delayed",
                "delay",
                level_endpoint("delayed_level"),
                ("level",),
                {"duration": cw.Duration(0.25), "initial": 0},
            ),
            cw.MechanismNode(
                "response",
                "output",
                output,
                ("delayed",),
                requirement_ids=(requirement.id,),
            ),
        ),
        outputs=("response",),
        required_capabilities=("synthetic_signal_graph",),
    )
    observation_map = cw.ObservationMap(
        inputs=(
            cw.InputBinding(a.node_id, "present", "a"),
            cw.InputBinding(b.node_id, "present", "b"),
        ),
        outputs=(cw.OutputBinding(requirement.id, "response"),),
    )

    def contact(first, second):
        return {
            a.node_id: cw.SignalSample(present=first),
            b.node_id: cw.SignalSample(present=second),
        }

    history = (
        cw.InputFrame(
            0, contacts={"first": contact(True, False), "second": contact(False, True)}
        ),
        cw.InputFrame(
            1, contacts={"first": contact(True, True), "second": contact(False, True)}
        ),
        cw.InputFrame(5, contacts={"first": contact(False, False)}),
    )
    return behavior, contract, domain, target, candidate, observation_map, history


def with_delay(candidate, duration):
    return replace(
        candidate,
        nodes=tuple(
            replace(node, attributes={"duration": cw.Duration(duration), "initial": 0})
            if node.id == "delayed"
            else node
            for node in candidate.nodes
        ),
    )


def run_example():
    behavior, contract, domain, target, candidate, mapping, history = build_example()
    late = with_delay(candidate, 2)
    silent = replace(
        candidate,
        name="silent_fixture",
        nodes=tuple(
            replace(node, inputs=("zero",)) if node.id == "response" else node
            for node in candidate.nodes
        ),
    )
    results = {
        label: cw.check_realization(
            behavior, contract, domain, target, model, mapping, history, until=7
        )
        for label, model in (
            ("responsive", candidate),
            ("silent", silent),
            ("late", late),
        )
    }
    dependencies = cw.realization_dependencies(
        behavior, contract, domain, target, late, mapping, history, until=7
    )
    return results, dependencies


def main():
    results, changed_dependencies = run_example()
    for name, result in results.items():
        print(f"{name:10} {result.outcome.value}")
        for item in result.counterexamples[:1]:
            print(
                f"  {item.requirement_id} at {item.time:g} s: "
                f"expected {item.expected['state']} range, observed {item.actual}"
            )
    assert results["responsive"].outcome == cw.CheckOutcome.PASS
    assert results["silent"].outcome == cw.CheckOutcome.FAIL
    assert results["late"].outcome == cw.CheckOutcome.FAIL
    assert not results["responsive"].is_fresh(changed_dependencies)
    print("Changing the model delay makes the earlier passing result stale.")
    print(
        "Claims apply only to these synthetic models, contracts, and supplied history."
    )


if __name__ == "__main__":
    main()
