"""Select, compose, package and stress-check an offline digital design.

All costs and observations are software fixtures. No molecular implementation
or biological applicability is inferred from this design loop.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import tempfile

import biocompiler as bc
from biocompiler.registry.synthetic import catalog_for_profile

if __package__:
    from .synthetic_build import prepare_request
    from .synthetic_verification import mixed_bounds
else:
    from synthetic_build import prepare_request
    from synthetic_verification import mixed_bounds


def prepare_design_request():
    request = prepare_request()
    build = replace(
        request.realization.build_request,
        implementation_constraints={
            "allowed_operators": [
                item.operation
                for item in catalog_for_profile(
                    request.config.profile_version
                ).components
                if item.operation != "and"
            ],
        },
        preferences={"minimize": "gate_count"},
    )
    behavior = bc.lower_to_behavior(build)
    realization = bc.RealizationRequest.freeze(
        build,
        behavior,
        replace(
            request.realization.contract, behavior_fingerprint=behavior.fingerprint
        ),
        request.realization.domain,
    )
    return replace(request, realization=realization, profile="synthetic_components")


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    request = prepare_design_request()
    (output / "request.json").write_text(request.to_json() + "\n", encoding="utf-8")
    package = bc.build_synthetic_package(request)
    path = bc.publish_synthetic_package(package, output / "design.bcb")
    rebuilt = bc.verify_synthetic_package(path.read_bytes(), expected_request=request)
    assert rebuilt.data == package.data
    selected = bc.select_synthetic(
        request.realization,
        request.history.frames,
        until=request.until,
        config=request.config,
    )
    assert selected.selected_strategy == "de_morgan"
    (output / "selection.json").write_text(selected.to_json() + "\n", encoding="utf-8")
    campaign = bc.SyntheticVerificationRequest(
        request.realization,
        selected.candidate,
        "explore",
        bounds=mixed_bounds(request.realization),
    )
    (output / "campaign-request.json").write_text(
        campaign.to_json() + "\n", encoding="utf-8"
    )
    record = bc.run_synthetic_verification(campaign)
    assert record.result.complete and record.result.all_passed
    bc.replay_synthetic_verification(record, expected_request=campaign)
    (output / "campaign-record.json").write_text(
        record.to_json() + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "build_fingerprint": package.build_fingerprint,
                "scope": package.manifest.scope,
                "selected_strategy": selected.selected_strategy,
                "checked_candidates": selected.checked_candidates,
                "rejected_candidates": selected.rejected_candidates,
                "evaluated_histories": record.result.evaluated_histories,
                "possible_histories": record.result.possible_histories,
                "all_passed": record.result.all_passed,
                "intended_use": "software_test",
                "unresolved": ["molecular_behavior"],
            },
            indent=2,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output:
        run(args.output)
    else:
        with tempfile.TemporaryDirectory(prefix="biocompiler-design-") as directory:
            run(Path(directory))


if __name__ == "__main__":
    main()
