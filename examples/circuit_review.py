"""Portable review of artificial records; no biological or published evidence.

Keep authority.json independently of review.bcb. Copying authority out of an
untrusted archive does not establish independence. The source inventory is an
unrelated metadata control and establishes no case-to-construction correspondence.
"""

import argparse
import json
from pathlib import Path

import biocompiler as bc

try:
    from examples.circuit_infrastructure import make_infrastructure_requests
    from examples.circuit_sources import make_source_inventory
except ModuleNotFoundError:
    from circuit_infrastructure import make_infrastructure_requests
    from circuit_sources import make_source_inventory


def make_review_records():
    construction, bindings, evidence = make_infrastructure_requests()
    build = bc.build_circuit_construction(construction)
    inventory = make_source_inventory()
    receipt = bc.capture_circuit_evidence(build, expected_request=evidence)
    authority = bc.CircuitReviewAuthority(
        construction,
        sources=inventory,
        bindings=bindings,
        evidence=evidence,
        evidence_receipt_fingerprint=receipt.fingerprint,
    )
    records = {
        "source_assessment": bc.check_circuit_sources(inventory),
        "binding_assessment": bc.check_circuit_bindings(
            build.candidate,
            expected_request=bindings,
        ),
        "evidence_receipt": receipt,
        "evidence_assessment": bc.check_circuit_evidence(
            receipt,
            build,
            expected_request=evidence,
        ),
    }
    return build, authority, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build, authority, records = make_review_records()
    bundle = bc.create_circuit_review_bundle(
        build,
        expected_authority=authority,
        **records,
    )
    bc.publish_circuit_review_bundle(
        bundle,
        args.output / "review.bcb",
        expected_authority=authority,
    )
    retained = {"build": build, "authority": authority, **records}
    for name, record in retained.items():
        (args.output / (name.replace("_", "-") + ".json")).write_text(
            record.to_json() + "\n",
            encoding="utf-8",
        )
    report = bc.verify_circuit_review_bundle(bundle.data, expected_authority=authority)
    (args.output / "verification.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
