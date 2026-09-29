"""Bounded software-model exploration; this is not universal or biological proof.

Run: PYTHONPATH=src python examples/verification_campaign.py
Use --output DIRECTORY to retain the exact bounded report and reduced failure.
"""

import argparse
from collections import Counter
from pathlib import Path
import json

import cellweave as cw
from cellweave.synthesis.synthetic import generate_synthetic, check_synthetic_candidate
from cellweave.verification.exploration import (
    AdversarialConfig,
    BooleanContactConfig,
    BooleanObservation,
    FailureSignature,
    explore_boolean_histories,
    generate_adversarial_histories,
    reduce_counterexample,
)

if __package__:
    from .checked_pipeline import build_request
    from .realization_check import with_delay
else:
    from checked_pipeline import build_request
    from realization_check import with_delay


def run_campaign():
    request, original_history = build_request()
    candidate = generate_synthetic(request)
    observations = tuple(
        BooleanObservation(item.signal_id, item.field) for item in request.domain.inputs
    )

    def sample(value):
        return {item.signal_id: cw.SignalSample(present=value) for item in observations}

    suffix = (
        cw.InputFrame(4, contacts={"x": sample(True), "y": sample(True)}),
        cw.InputFrame(6, contacts={"x": sample(False), "y": sample(False)}),
    )
    bounds = BooleanContactConfig(("x", "y"), observations, (0, 2), 7, suffix)

    def check(history, *, until):
        return check_synthetic_candidate(request, candidate, history, until=until)

    report = explore_boolean_histories(bounds, check)
    assert report.complete and report.all_passed, {
        "evaluated": report.evaluated_histories,
        "possible": report.possible_histories,
        "first_nonpass": next(
            (
                (index, result.to_dict())
                for index, result in enumerate(report.results)
                if result.outcome is not cw.CheckOutcome.PASS
            ),
            None,
        ),
    }
    assert report.state_count == 25 and report.evaluated_histories == 625

    stress_bounds = BooleanContactConfig(
        ("x", "y"), observations, (0, 0.25, 0.5, 1, 2, 3), 7, suffix
    )
    stress_config = AdversarialConfig(stress_bounds, seed=20260929, random_cases=16)
    cases = generate_adversarial_histories(stress_config)
    outcomes = Counter()
    for case in cases:
        result = check(case.history, until=case.until)
        outcomes[result.outcome.value] += 1
        assert result.outcome in {cw.CheckOutcome.PASS, cw.CheckOutcome.UNKNOWN}, {
            "case": case.to_dict(),
            "result": result.to_dict(),
        }
        if case.intentionally_incomplete:
            assert result.outcome is cw.CheckOutcome.UNKNOWN, {
                "case": case.to_dict(),
                "result": result.to_dict(),
            }

    delayed = with_delay(candidate.mechanism, 2)

    def check_delayed(history, *, until):
        return cw.check_realization(
            request.behavior,
            request.contract,
            request.domain,
            request.target,
            delayed,
            candidate.observation_map,
            history,
            until=until,
        )

    noisy = (
        original_history[0],
        cw.InputFrame(0.25, contacts=original_history[0].contacts),
        original_history[1],
        cw.InputFrame(2, contacts=original_history[1].contacts),
        cw.InputFrame(3, contacts=original_history[1].contacts),
        cw.InputFrame(4, contacts=original_history[1].contacts),
        original_history[2],
    )
    failure = check_delayed(noisy, until=7)
    assert failure.outcome is cw.CheckOutcome.FAIL
    signature = FailureSignature.from_counterexample(failure.counterexamples[0])
    reduced = reduce_counterexample(noisy, 7, check_delayed, signature)
    assert reduced.one_minimal and reduced.result.outcome is cw.CheckOutcome.FAIL
    return report, stress_config, cases, dict(sorted(outcomes.items())), reduced


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report, stress_config, cases, outcomes, reduced = run_campaign()
    print(
        f"Bounded exploration: {report.evaluated_histories}/{report.possible_histories} histories; {report.state_count} snapshot states; all passed: {report.all_passed}"
    )
    print(
        "Bounds: two named contacts; two Boolean fields; variable times 0,2; fixed active/inactive suffix 4,6; horizon 7 seconds"
    )
    print(f"Seeded adversarial cases: {len(cases)}; outcomes: {outcomes}")
    print(
        f"Delayed-model failure: 7 -> {len(reduced.history)} frames; deletion-1-minimal: {reduced.one_minimal}"
    )
    print(
        "Model-conditional regression evidence only; UNKNOWN is retained; no universal or empirical claim."
    )
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "bounded-report.json").write_text(
            report.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "reduced-failure.json").write_text(
            reduced.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "adversarial-summary.json").write_text(
            json.dumps(
                {
                    "configuration": stress_config.to_dict(),
                    "outcomes": outcomes,
                    "cases": [
                        {
                            "id": case.id,
                            "kind": case.kind,
                            "history": [frame.to_dict() for frame in case.history],
                            "until": case.until,
                            "intentionally_incomplete": case.intentionally_incomplete,
                            "config_fingerprint": case.config_fingerprint,
                        }
                        for case in cases
                    ],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
