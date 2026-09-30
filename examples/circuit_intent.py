"""Author typed Boolean requirements using artificial observation declarations.

No published case, source sequence, molecular implementation or empirical
observation is supplied. The reference lock is a software-only consistency test.
"""

import argparse
from dataclasses import replace
from pathlib import Path

import biocompiler as bc

try:
    from examples.circuit_profile import make_profile_requests
except ModuleNotFoundError:
    from circuit_profile import make_profile_requests


def observation(
    identity,
    quantity=bc.QuantityKind.MIRNA_ACTIVITY,
    scope=bc.ObservationScope.CELL_ACCESSIBLE,
):
    return bc.CircuitObservation(
        id=identity,
        entity=bc.ObservationEntity("software_fixture", identity, "1", "unknown"),
        quantity=quantity,
        compartment="cytoplasm",
        scope=scope,
        window=bc.ObservationWindow("unknown", None, None, "unknown", "unknown"),
        encoding=bc.ObservationEncoding("qualitative", "qualitative"),
    )


def make_circuit_requests():
    profiles = make_profile_requests()
    first, second = observation("A"), observation("B")
    output = bc.CircuitProduct(
        "reporter",
        bc.ProductKind.REPORTER_FLUORESCENCE,
        observation(
            "reporter_readout",
            bc.QuantityKind.FLUORESCENCE,
            bc.ObservationScope.EVALUATOR,
        ),
    )
    lifecycle = bc.CircuitLifecycle("readout")
    product_profile = profiles["product"]
    deployment = product_profile.source_request.deployment_request.deployment
    product_builder = bc.CircuitBuilder(
        "supplementary_response", product_profile, role_id=deployment.recipient_role
    )
    a, b = product_builder.observe(first), product_builder.observe(second)
    product_builder.require("response", a & b, output, lifecycle=lifecycle)
    product = product_builder.freeze(
        requested_form="delivered_rna",
        fidelity_scope="complete_nominal",
        deployment_id=deployment.id,
    )

    reference_profile = profiles["reference"]
    reference_builder = bc.CircuitBuilder("reference_response", reference_profile)
    a, b = reference_builder.observe(first), reference_builder.observe(second)
    reference_builder.require("response", a & b, output, lifecycle=lifecycle)
    # A separately authored table is the expectation for this software fixture.
    # Real source authority still requires curation and independent review.
    expected = bc.CircuitBehavior(
        (first, second),
        bc.BooleanSpec((a, b), (False, False, False, True)),
        output,
        lifecycle,
    )
    realization = bc.PinnedIdentity(
        "reference", "artificial_AND_declaration", "1", expected.fingerprint
    )
    lock = bc.CircuitReferenceLock(
        (bc.CircuitBehaviorExpectation("response", expected),),
        realization,
        reference_profile.source_experiment.sources,
        reference_profile.source_experiment,
        "delivered_rna",
        "source_nominal",
    )
    reference = reference_builder.freeze(
        requested_form="delivered_rna",
        fidelity_scope="source_nominal",
        deployment_id=None,
        selected_realization=realization,
        reference_lock=lock,
    )
    return {"product": product, "reference": reference}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    for label, request in make_circuit_requests().items():
        assessment = bc.check_circuit_intent(request)
        bc.verify_circuit_intent(assessment, expected_request=request)
        (args.output / f"{label}.request.json").write_text(
            request.to_json() + "\n", encoding="utf-8"
        )
        (args.output / f"{label}.assessment.json").write_text(
            assessment.to_json() + "\n", encoding="utf-8"
        )
        try:
            bc.compile(request)
        except bc.CompilationUnavailableError:
            pass
        else:
            raise AssertionError("Typed requirements cannot compile molecules.")
        print(
            f"{label}: {assessment.intent_consistency}; molecular implementation {assessment.molecular_implementation}"
        )
    reference = make_circuit_requests()["reference"]
    requirement = reference.requirements[0]
    a, b = requirement.behavior.response.inputs
    try:
        replace(
            reference,
            requirements=(
                replace(
                    requirement, behavior=replace(requirement.behavior, response=a | b)
                ),
            ),
        )
    except bc.SerializationError:
        print("Locked AND-to-OR edit: rejected")
    else:
        raise AssertionError("Changed behavior must not retain reference authority.")


if __name__ == "__main__":
    main()
