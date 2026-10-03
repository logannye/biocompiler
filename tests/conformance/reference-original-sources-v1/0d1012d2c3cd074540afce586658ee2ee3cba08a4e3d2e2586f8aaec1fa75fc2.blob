"""Check independent synthetic candidates against a declared response contract.

The signal graph is a software fixture, not a molecular implementation. Its output
is an abstract request readout, not a prediction of a cellular effect.
Run ``PYTHONPATH=src python examples/realization_check.py`` from the checkout.
"""

from __future__ import annotations

from dataclasses import replace

import biocompiler as bc
from biocompiler.compiler.request import BuildRequest, RealizationRequest
from biocompiler.semantics.types import BOOLEAN
from biocompiler.synthesis.synthetic import generate_synthetic


def build_example():
    therapy = bc.Therapy("synthetic_realization")
    cell = therapy.engineer("responder", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    action = cell.rest()
    rule = cell.when(a.present() & b.present()).do(action)
    target = bc.TargetContext(
        "synthetic_context",
        "1",
        bc.PayloadFormat.RNA,
        capabilities=("synthetic_signal_graph",),
    )
    request = BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="synthetic_realization"
    )
    behavior = bc.lower_to_behavior(request)

    input_a = bc.Observable("A.present", BOOLEAN, cell.role, scope="contact")
    input_b = bc.Observable("B.present", BOOLEAN, cell.role, scope="contact")
    output = bc.Observable("abstract_rest_request_readout", bc.Level, cell.role)
    requirement = bc.ResponseRequirement(
        id="response.rest",
        rule_id=rule.node_id,
        specification_id=action.node_id,
        observable=output,
        active_range=bc.Interval(0.9, 1.1),
        inactive_range=bc.Interval(0, 0.1),
        max_activation_delay=bc.Duration(0.5),
        max_deactivation_delay=bc.Duration(0.5),
    )
    contract = bc.BehaviorContract(
        "rest_contract", behavior.fingerprint, (requirement,)
    )
    domain = bc.OperatingDomain(
        id="two_contact_fixture",
        version="1",
        role=cell.role,
        inputs=(
            bc.InputDomain(a.node_id, "present", input_a, (False, True)),
            bc.InputDomain(b.node_id, "present", input_b, (False, True)),
        ),
        minimum_horizon=bc.Duration(7),
        max_contacts=2,
    )
    # Lowering retains the full per-contact conjunction before existential
    # aggregation. Acceptance still uses the independently implemented runner.
    generated = generate_synthetic(
        RealizationRequest.freeze(request, behavior, contract, domain)
    )
    candidate, observation_map = generated.mechanism, generated.observation_map

    def contact(first, second):
        return {
            a.node_id: bc.SignalSample(present=first),
            b.node_id: bc.SignalSample(present=second),
        }

    history = (
        bc.InputFrame(
            0, contacts={"first": contact(True, False), "second": contact(False, True)}
        ),
        bc.InputFrame(
            1, contacts={"first": contact(True, True), "second": contact(False, True)}
        ),
        bc.InputFrame(5, contacts={"first": contact(False, False)}),
    )
    return behavior, contract, domain, target, candidate, observation_map, history


def with_delay(candidate, duration):
    """Inject an adversarial delay; generation itself is stateless."""
    delays = tuple(
        bc.MechanismNode(
            f"delayed:{ref}",
            "delay",
            replace(candidate.get(ref).output, id=f"delayed:{ref}"),
            candidate.get(ref).inputs,
            {"duration": bc.Duration(duration), "initial": 0},
        )
        for ref in candidate.outputs
    )
    return replace(
        candidate,
        nodes=tuple(
            replace(node, inputs=(f"delayed:{node.id}",))
            if node.id in candidate.outputs
            else node
            for node in candidate.nodes
        )
        + delays,
    )


def run_example():
    behavior, contract, domain, target, candidate, mapping, history = build_example()
    late = with_delay(candidate, 2)
    silent = replace(
        candidate,
        name="silent_fixture",
        nodes=tuple(
            replace(node, inputs=("inactive:response.rest",))
            if node.id in candidate.outputs
            else node
            for node in candidate.nodes
        ),
    )
    results = {
        label: bc.check_realization(
            behavior, contract, domain, target, model, mapping, history, until=7
        )
        for label, model in (
            ("responsive", candidate),
            ("silent", silent),
            ("late", late),
        )
    }
    dependencies = bc.realization_dependencies(
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
    assert results["responsive"].outcome == bc.CheckOutcome.PASS
    assert results["silent"].outcome == bc.CheckOutcome.FAIL
    assert results["late"].outcome == bc.CheckOutcome.FAIL
    assert not results["responsive"].is_fresh(changed_dependencies)
    print("Changing the model delay makes the earlier passing result stale.")
    print(
        "Claims apply only to these synthetic models, contracts, and supplied history."
    )


if __name__ == "__main__":
    main()
