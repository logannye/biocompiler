"""Required/prohibited behavior with invented software bounds, no human therapy."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

import biocompiler as bc

if __package__:
    from .human_deployment import (
        make_human_deployment,
        pending,
        seconds,
        with_fixture_bounds,
    )
else:
    from human_deployment import (
        make_human_deployment,
        pending,
        seconds,
        with_fixture_bounds,
    )


def make_human_acceptance():
    deployment = with_fixture_bounds(make_human_deployment())
    behavior = replace(
        deployment.behavior_request,
        contract=replace(deployment.behavior_request.contract, horizon=bc.Duration(16)),
    )
    deployment = replace(
        deployment,
        behavior_request=behavior,
        deployment=replace(
            deployment.deployment,
            timing=replace(deployment.deployment.timing, duration=seconds(20, 22)),
        ),
    )
    acceptance = bc.HumanAcceptanceContract(
        "conditional_secretion_acceptance_fixture",
        behavior.fingerprint,
        bc.MeasurementSpec(
            bc.Observable(
                "context_classification",
                bc.Level,
                behavior.contract.input_measurement.observable.role,
                compartment="extracellular",
            ),
            "Artificial context label: zero denotes a healthy-context test case, one a challenge case.",
            "external_evaluator",
            "Asserted fixture classification; no clinical classifier is supplied.",
            pending(
                "A real healthy-context definition and context-specific assay require evidence."
            ),
        ),
        bc.Interval(bc.Level(0), bc.Level(1), type=bc.Level),
        bc.Interval(bc.Level(0), bc.Level(0.4), type=bc.Level),
        bc.ProductionRate(0.1, unit="molecules/s"),
        bc.ProductionRate(4, unit="molecules/s"),
        bc.Duration(4),
        pending(
            "All ceilings, classifications and durations are invented software-test values, not clinical limits."
        ),
        bc.InputAvailabilitySpec(
            "cell_input_access",
            "Fixture asserts whether cell access is available; evaluator missingness is a separate state.",
            bc.Duration(1),
            pending(
                "Cell access failure detection has no established assay or cellular signal."
            ),
            pending(
                "Requested recovery after access loss has no established implementation."
            ),
        ),
        bc.ExternalShutdownSpec(
            "external_shutdown",
            "An externally recorded stop request, latched through the finite horizon.",
            "Fixture event log; no route, drug, controller or actuator is supplied.",
            bc.Duration(1),
            pending("Request delivery and observation need applicable evidence."),
            pending(
                "No shutdown actuator is supported; a passing readout does not prove causal controllability."
            ),
        ),
    )
    return bc.HumanAcceptanceRequest(deployment, acceptance)


def sample(time, cue=0, rate=0, context=1, input_status="available", control="clear"):
    return bc.AcceptanceSample(
        bc.Duration(time),
        input_status,
        None if cue is None else bc.Concentration(cue, unit="nM"),
        None if rate is None else bc.ProductionRate(rate, unit="molecules/s"),
        None if context is None else bc.Level(context),
        control,
    )


def example_trace():
    return (
        sample(0, context=0),
        sample(1, cue=6),
        sample(3, cue=6, rate=2.5),
        sample(6, rate=2.5),
        sample(7, context=0),
        sample(8, cue=None, input_status="cell_unavailable"),
        sample(10),
        sample(12, control="shutdown"),
        sample(16),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    request, trace = make_human_acceptance(), example_trace()
    peak = list(trace)
    peak.insert(2, sample(2, cue=6, rate=5))
    missing = list(trace)
    missing[5] = sample(8, cue=None, input_status="unobserved")
    co_payload = replace(
        request,
        deployment_request=replace(
            request.deployment_request,
            deployment=replace(
                request.deployment_request.deployment,
                intracellular_destination="extracellular",
            ),
        ),
    )
    cases = (
        ("pass", request, trace),
        ("fail", request, peak),
        ("unknown", request, missing),
        ("unsupported", co_payload, trace),
    )
    records = [("human-acceptance-request", request)]
    for expected, authority, observations in cases:
        result = bc.check_human_acceptance(authority, observations)
        assert result.outcome == expected, result.diagnostics
        records.extend(
            ((f"request-{expected}", authority), (f"assessment-{expected}", result))
        )
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / f"trace-{expected}.json").write_text(
                json.dumps([item.to_dict() for item in observations], indent=2) + "\n"
            )
    print("Acceptance observations: pass / fail / unknown / unsupported")
    print(
        "Biological applicability and controllability: unestablished; actuator support: unimplemented"
    )
    if args.output:
        for name, artifact in records:
            (args.output / f"{name}.json").write_text(artifact.to_json() + "\n")


if __name__ == "__main__":
    main()
