"""Inspect non-biological source-metadata fixtures; no publication reconstruction."""

import argparse
from dataclasses import replace
from pathlib import Path

from biocompiler.ir.circuit_sources import (
    COVERAGE_FIELDS,
    CircuitSourceCase,
    CircuitSourceInventory,
    SourceDocument,
    SourceGap,
    SourceReview,
)
from biocompiler.verification.circuit_sources import (
    check_circuit_sources,
    verify_circuit_sources,
)
from biocompiler.verification.evidence import CheckOutcome


def make_source_inventory():
    document = SourceDocument(
        id="software_fixture",
        version="1",
        title="Non-biological provenance example; no publication or molecule",
        url="https://example.invalid/metadata-fixture",
        record_kind="author_record",
        access_status="not_retrieved",
        reuse_status="unreviewed",
        reuse_locator="Software fixture; no external source bytes supplied.",
        correction_status="not_checked",
    )
    case = CircuitSourceCase(
        id="software_metadata_case",
        family_id="matsuura_2018_mrna",
        label="Artificial metadata fixture; not an actual study case",
        source_ids=(document.id,),
        coverage=tuple(
            SourceGap(
                field=field,
                status="not_reviewed",
                note="No scientific authority supplied by this software fixture.",
            )
            for field in sorted(COVERAGE_FIELDS)
        ),
    )
    review = SourceReview(
        id="software_metadata_review",
        subject_kind="case",
        subject_fingerprint=case.fingerprint,
        reviewer_kind="software_agent",
        reviewer_id="example_fixture",
        method="Demonstrate metadata consistency and explicit missing coverage.",
        findings=("This review establishes no publication or experimental claim.",),
        disposition="metadata_review_only",
    )
    return CircuitSourceInventory(
        id="software_inventory",
        version="1",
        sources=(document,),
        cases=(case,),
        reviews=(review,),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = make_source_inventory()
    assessment = check_circuit_sources(inventory)
    verify_circuit_sources(assessment, expected_inventory=inventory)
    assert assessment.outcome == CheckOutcome.PASS
    assert assessment.molecular_readiness == "unassessed"
    assert assessment.source_bytes == "not_checked"
    assert assessment.human_admission == "not_admitted"
    stale = replace(
        inventory, cases=(replace(inventory.cases[0], label="Changed fixture label"),)
    )
    rejected = check_circuit_sources(stale)
    assert rejected.outcome == CheckOutcome.FAIL
    for label, artifact in (
        ("inventory", inventory),
        ("assessment", assessment),
        ("stale-review.inventory", stale),
        ("stale-review.assessment", rejected),
    ):
        (args.output / f"{label}.json").write_text(
            artifact.to_json() + "\n", encoding="utf-8"
        )
    print("Metadata consistency checked; all scientific coverage remains unresolved.")
    print("Changed case metadata correctly invalidates its prior review.")


if __name__ == "__main__":
    main()
