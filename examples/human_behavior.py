"""Reversible conditional secretion: artificial contract values, no biological model."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

import cellweave as cw

if __package__:
    from .human_target import make_human_target
else:
    from human_target import make_human_target


def make_human_behavior():
    def assumed(description):
        return cw.TargetClaim(
            description,
            "assumed",
            (),
            "Artificial software fixture only. No assay, sensor, product, clinical threshold or timing is validated.",
        )

    therapy = cw.Therapy("conditional_secretion_specification")
    cell = therapy.engineer("recipient", cell_type="human_T_cell")
    goal = therapy.goal(
        "conditional_therapeutic_secretion",
        description="Secrete a declared product while a qualifying cue is present, then return to baseline.",
    )
    cue = cell.external.signal("declared_cue", type=cw.Concentration)
    predicate = cue.high()
    action = cell.secrete("declared_product")
    rule = cell.when(predicate).do(action)
    target = replace(make_human_target(), compartments=("cytoplasm", "extracellular"))
    build = cw.BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="complete_payload"
    )
    input_observable = cw.Observable(
        "local_cue_concentration",
        cw.Concentration,
        cell.role,
        compartment="extracellular",
    )
    output_observable = cw.Observable(
        "product_secretion_rate_per_cell",
        cw.ProductionRate,
        cell.role,
        compartment="extracellular",
    )
    input_spec = cw.MeasurementSpec(
        input_observable,
        "Local concentration of the declared extracellular cue at the recipient cell.",
        "cell",
        "A context-matched sensing/readout relationship must be supplied; no receptor is selected.",
        assumed(
            "Runtime accessibility and readout correspondence are requested, not established."
        ),
    )
    output_spec = cw.MeasurementSpec(
        output_observable,
        "Exported declared product amount per unit time from this one recipient cell.",
        "external_evaluator",
        "Requires a calibrated per-cell secretion-rate measurement, not accumulated bulk concentration.",
        assumed(
            "The output is a required measurement; no assay or conversion has been validated."
        ),
    )
    contract = cw.ConditionalSecretionContract(
        id="conditional_secretion_fixture",
        goal_id=goal.node_id,
        product="declared_product",
        input_signal_id=cue.node_id,
        input_measurement=input_spec,
        input_range=cw.Interval(
            cw.Concentration(0, unit="nM"),
            cw.Concentration(10, unit="nM"),
            type=cw.Concentration,
        ),
        predicate=cw.PredicateRefinement(
            predicate.node_id,
            ">=",
            cw.Concentration(5, unit="nM"),
            assumed("A software-only threshold refines the source high predicate."),
        ),
        output_measurement=output_spec,
        response=cw.ResponseRequirement(
            "response.secretion",
            rule.node_id,
            action.node_id,
            output_observable,
            cw.Interval(
                cw.ProductionRate(2, unit="molecules/s"),
                cw.ProductionRate(3, unit="molecules/s"),
                type=cw.ProductionRate,
            ),
            cw.Interval(
                cw.ProductionRate(0, unit="molecules/s"),
                cw.ProductionRate(0.1, unit="molecules/s"),
                type=cw.ProductionRate,
            ),
            cw.Duration(2),
            cw.Duration(1),
        ),
        initial_range=cw.Interval(
            cw.ProductionRate(0, unit="molecules/s"),
            cw.ProductionRate(0.05, unit="molecules/s"),
            type=cw.ProductionRate,
        ),
        horizon=cw.Duration(10),
        goal_refinement=assumed(
            "The source goal is refined to secretion of the same declared product under the same cue; this readout does not establish clinical benefit."
        ),
        response_support=assumed(
            "All numeric ranges, delays and the horizon are invented test values, not recommended biological requirements."
        ),
    )
    return cw.HumanBehaviorRequest(build, contract)


def sample(time, cue, rate):
    return cw.SecretionSample(
        cw.Duration(time),
        cw.Concentration(cue, unit="nM"),
        cw.ProductionRate(rate, unit="molecules/s"),
    )


def example_trace():
    return (
        sample(0, 0, 0),
        sample(1, 6, 0),
        sample(3, 6, 2.5),
        sample(6, 0, 2.5),
        sample(7, 0, 0),
        sample(10, 0, 0),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    request = make_human_behavior()
    trace = example_trace()
    passing = cw.check_secretion_trace(request, trace)
    silent = cw.check_secretion_trace(
        request,
        tuple(replace(item, output_value=cw.ProductionRate(0)) for item in trace),
    )
    inactive = cw.check_secretion_trace(request, (sample(0, 0, 0), sample(10, 0, 0)))
    assert (passing.outcome, silent.outcome, inactive.outcome) == (
        "pass",
        "fail",
        "unknown",
    )
    assert (
        cw.HumanBehaviorRequest.from_json(request.to_json()).fingerprint
        == request.fingerprint
    )
    print("Conditional secretion contract: source correspondence checked")
    print("Artificial trace outcomes: pass / fail / unknown")
    print("Biological applicability and therapeutic efficacy: unestablished")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "supplied-trace.json").write_text(
            json.dumps([item.to_dict() for item in trace], sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        for name, artifact in (
            ("human-behavior-request", request),
            ("trace-pass", passing),
            ("trace-fail", silent),
            ("trace-unknown", inactive),
        ):
            (args.output / f"{name}.json").write_text(
                artifact.to_json() + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
