"""Reusable bounded mixed-input verification and selected wrong-reset replay.

Run: PYTHONPATH=src python examples/synthetic_verification.py --output generated/synthetic-verification
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from biocompiler.compiler.verification_workflow import (
    SyntheticVerificationRequest,
    replay_synthetic_verification,
    run_synthetic_verification,
)
from biocompiler.ir.mechanism import MechanismNode
from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION, catalog_for_profile
from biocompiler.semantics.evaluator import InputFrame, SignalSample
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.types import BOOLEAN
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig, generate_synthetic
from biocompiler.verification.exploration import (
    BooleanInputConfig,
    BooleanObservation,
    FailureSignature,
)

if __package__:
    from .temporal_pipeline import build_request
else:
    from temporal_pipeline import build_request


def verification_fixture():
    realization, history = build_request()
    candidate = generate_synthetic(
        realization,
        config=SyntheticGeneratorConfig(
            profile_version=TEMPORAL_PROFILE_VERSION,
        ),
    )
    return realization, candidate, history


def mixed_bounds(realization, *, max_histories=10000):
    contacts = tuple(
        BooleanObservation(item.signal_id, item.field)
        for item in realization.domain.inputs
        if item.observable.scope == "contact"
    )
    local = tuple(
        BooleanObservation(item.signal_id, item.field)
        for item in realization.domain.inputs
        if item.observable.scope == "cell"
    )

    def frame(time, active, resetting):
        return InputFrame(
            time,
            {item.signal_id: SignalSample(**{item.field: resetting}) for item in local},
            {
                "x": {
                    item.signal_id: SignalSample(**{item.field: active})
                    for item in contacts
                }
            },
        )

    return BooleanInputConfig(
        ("x",),
        contacts,
        (0, 1),
        10,
        (
            frame(2, True, False),
            frame(5, False, False),
            frame(6, False, True),
            frame(8, False, False),
        ),
        max_histories=max_histories,
        cell_observations=local,
    )


def ignored_reset(candidate, realization):
    """An explicitly retained diagnostic mutant, never an accepted compilation."""
    memory = candidate.mechanism.find("memory")[0]
    constant = MechanismNode(
        "diagnostic:ignored_reset",
        "constant",
        Observable("diagnostic_reset", BOOLEAN, realization.domain.role),
        attributes={"value": False},
    )
    mechanism = replace(
        candidate.mechanism,
        nodes=tuple(
            replace(node, inputs=(node.inputs[0], constant.id))
            if node.id == memory.id
            else node
            for node in candidate.mechanism.nodes
        )
        + (constant,),
    )
    return replace(
        candidate,
        mechanism=mechanism,
        source_map={
            **candidate.source_map,
            constant.id: candidate.source_map[memory.id],
        },
        behavior_requirement_ids={
            **candidate.behavior_requirement_ids,
            constant.id: candidate.behavior_requirement_ids[memory.id],
        },
        component_locks=catalog_for_profile(
            candidate.generator_config.profile_version
        ).lock(mechanism),
    )


def run_campaign():
    realization, candidate, history = verification_fixture()
    check_request = SyntheticVerificationRequest(
        realization, candidate, "check", history=history, until=9
    )
    check = run_synthetic_verification(check_request)
    bounds = mixed_bounds(realization)
    exploration_request = SyntheticVerificationRequest(
        realization, candidate, "explore", bounds=bounds
    )
    exploration = run_synthetic_verification(exploration_request)
    mutant = ignored_reset(candidate, realization)
    mutant_request = replace(check_request, candidate=mutant, mode="model")
    failed = run_synthetic_verification(mutant_request)
    selected = next(
        item
        for item in failed.result.counterexamples
        if item.requirement_id == "memory_readout"
        and item.expected["state"] == "inactive"
    )
    reduction_request = replace(
        mutant_request,
        operation="reduce",
        signature=FailureSignature.from_counterexample(selected),
        max_evaluations=100,
    )
    reduction = run_synthetic_verification(reduction_request)
    for record in (check, exploration, failed, reduction):
        replay_synthetic_verification(record, expected_request=record.request)
    return {
        "check": check,
        "exploration": exploration,
        "wrong-reset": failed,
        "reduction": reduction,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    records = run_campaign()
    exploration = records["exploration"].result
    reduction = records["reduction"].result
    print(
        json.dumps(
            {
                "check": records["check"].result.outcome.value,
                "state_count": exploration.state_count,
                "histories": exploration.evaluated_histories,
                "possible_histories": exploration.possible_histories,
                "complete": exploration.complete,
                "outcome_counts": dict(exploration.outcome_counts),
                "wrong_reset": records["wrong-reset"].result.outcome.value,
                "reduced_frames": len(reduction.history),
                "one_minimal": reduction.one_minimal,
                "scope": "Declared finite mixed-input lattice and exact suffix only; software-model evidence.",
            },
            indent=2,
        )
    )
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, record in records.items():
            (args.output / f"{name}-request.json").write_text(
                record.request.to_json() + "\n", encoding="utf-8"
            )
            (args.output / f"{name}-record.json").write_text(
                record.to_json() + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
