"""Freeze delivery requirements with explicit unknowns; no delivery system is chosen."""

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path

import biocompiler as bc

if __package__:
    from .human_behavior import make_human_behavior
else:
    from human_behavior import make_human_behavior


PLATFORM_SOURCE = b"biocompiler RNA delivery specification fixture v1. No delivery technology, formulation, route, dose or biological performance is specified.\n"


def pending(description):
    return bc.TargetClaim(
        description,
        "unestablished",
        (),
        "Software specification only; applicable delivery evidence is not supplied.",
    )


def seconds(lower, upper):
    return bc.Interval(bc.Duration(lower), bc.Duration(upper), type=bc.Duration)


def make_human_deployment():
    behavior = make_human_behavior()
    target = behavior.target
    platform = bc.DeliveryPlatformSpec(
        bc.PinnedIdentity(
            "source",
            "unselected_delivery_fixture",
            "1",
            hashlib.sha256(PLATFORM_SOURCE).hexdigest(),
        ),
        bc.PayloadFormat.RNA,
        pending(
            "Administration route, setting and exposure conditions remain to be selected."
        ),
        pending(
            "Delivery must reach the intended human recipients independently of the cellular disease-recognition cue; targeting is unestablished."
        ),
        pending(
            "This pin identifies an artificial specification, not a characterized delivery platform."
        ),
    )
    exposure = bc.ExposureAssumption(
        "local_payload",
        "Normalized local intact-payload availability in an artificial software scenario.",
        "extracellular",
        bc.ValueDomain.unknown(
            reason="No exposure measurement or bounds are established."
        ),
        pending(
            "Exposure must be characterized separately from uptake, intracellular release and expression."
        ),
    )
    contract = bc.DeploymentContract(
        id="human_deployment_fixture",
        target_fingerprint=target.fingerprint,
        recipient_role=behavior.contract.input_measurement.observable.role,
        platform=platform,
        intended_population=target.human_target.population_inclusion,
        excluded_population=target.human_target.population_exclusion,
        intracellular_destination="cytoplasm",
        exposure_window=seconds(0, 1),
        exposures=(exposure,),
        timing=bc.ExpressionTiming(
            None,
            None,
            bc.Duration(2),
            "Expression onset and duration lack applicable data.",
            pending(
                "The deployment origin, exposure window and behavior offset are artificial requirements, not established biological timing."
            ),
        ),
        unintended_recipients=pending(
            "Other human recipient cells and tissues may be exposed; their identities, exposure and consequences require characterization. Absence is not asserted."
        ),
        co_payloads=(),
    )
    return bc.HumanDeploymentRequest(behavior, contract)


def with_fixture_bounds(request):
    deployment = request.deployment
    timing = replace(
        deployment.timing,
        onset=seconds(1, 2),
        duration=seconds(11, 15),
        unknown_reason=None,
        support=replace(
            deployment.timing.support,
            basis="assumed",
            description="Artificial interval values used solely to test conservative window arithmetic.",
        ),
    )
    exposures = tuple(
        replace(
            item,
            domain=bc.ValueDomain.interval(0, 1),
            support=replace(item.support, basis="assumed"),
        )
        for item in deployment.exposures
    )
    return replace(
        request, deployment=replace(deployment, timing=timing, exposures=exposures)
    )


def co_payload_fixture():
    return bc.CoPayloadRequirement(
        "additional_payload",
        bc.PinnedIdentity("reference", "nonexistent_software_payload", "1", "c" * 64),
        "declared_additional_capability",
        "cytoplasm",
        seconds(2, 12),
        pending(
            "A shared formulation or administration does not establish same-cell coexistence."
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    unknown = make_human_deployment()
    bounded = with_fixture_bounds(unknown)
    short = replace(
        bounded,
        deployment=replace(
            bounded.deployment,
            timing=replace(bounded.deployment.timing, duration=seconds(10, 15)),
        ),
    )
    co_payload = replace(
        bounded,
        deployment=replace(bounded.deployment, co_payloads=(co_payload_fixture(),)),
    )
    cases = (
        ("unknown", unknown),
        ("pass", bounded),
        ("fail", short),
        ("unsupported", co_payload),
    )
    records = []
    for expected, request in cases:
        result = bc.check_deployment(request)
        assert result.compatibility == expected
        assert (
            bc.HumanDeploymentRequest.from_json(request.to_json()).fingerprint
            == request.fingerprint
        )
        records.extend(
            ((f"request-{expected}", request), (f"assessment-{expected}", result))
        )
    print("Deployment declaration outcomes: unknown / pass / fail / unsupported")
    print("Biological delivery and expression: unestablished")
    print("Human mechanism selection: blocked")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "platform-fixture.txt").write_bytes(PLATFORM_SOURCE)
        for name, artifact in records:
            (args.output / f"{name}.json").write_text(
                artifact.to_json() + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
