"""Check invented, nonfunctional whole-molecule software fixtures.

Run: PYTHONPATH=src python examples/payload_readiness.py --output DIRECTORY
No fixture is a biological reference or an admitted compiler output.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from cellweave.ir.payload import (
    PayloadFeature,
    PayloadMolecule,
    PayloadReference,
    PayloadRegion,
    PayloadReview,
    PayloadSource,
)
from cellweave.semantics.coordinates import SequenceRange
from cellweave.verification.evidence import CheckOutcome
from cellweave.verification.payload import REVIEW_SCHEMA_VERSION, check_payload


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def build_fixture(artifact_class):
    """A frozen software expectation, invented independently of any emitter."""
    rna = artifact_class == "mature_linear_rna"
    circular = artifact_class == "circular_plasmid"
    if artifact_class not in ("mature_linear_rna", "linear_dna", "circular_plasmid"):
        raise ValueError("Unknown software fixture")
    sequence = (
        "GGAUGGCUUAACCAAAA" if rna else "GGATGGCTTAACC" + ("GC" if circular else "")
    )
    kinds = (
        ("five_prime_utr", "cds", "three_prime_utr", "poly_a")
        if rna
        else (
            ("promoter", "cds", "terminator", "backbone")
            if circular
            else ("promoter", "cds", "terminator")
        )
    )
    edges = (0, 2, 11, 13, len(sequence)) if rna or circular else (0, 2, 11, 13)
    regions = tuple(
        PayloadRegion(
            kind,
            kind,
            SequenceRange(start, end),
            SequenceRange(start, end),
            "invented region " + kind,
            "MA*" if kind == "cds" else None,
        )
        for kind, start, end in zip(kinds, edges, edges[1:])
    )
    features = (
        PayloadFeature(
            "cap",
            "known" if rna else "inapplicable",
            "invented cap",
            "cap1" if rna else None,
        ),
        PayloadFeature(
            "poly_a_tail",
            "known" if rna else "inapplicable",
            "invented tail",
            "exact:4" if rna else None,
        ),
        PayloadFeature(
            "nucleotide_modifications", "known", "invented chemistry", "none"
        ),
        PayloadFeature(
            "end_structure",
            "inapplicable" if circular else "known",
            "invented ends",
            None if circular else "single_strand" if rna else "blunt",
        ),
        PayloadFeature(
            "five_prime_end",
            "inapplicable" if circular else "known",
            "invented ends",
            None if circular else "capped" if rna else "phosphate_both_strands",
        ),
        PayloadFeature(
            "three_prime_end",
            "inapplicable" if circular else "known",
            "invented ends",
            None if circular else "hydroxyl" if rna else "hydroxyl_both_strands",
        ),
    )
    expected = PayloadMolecule(
        "nonfunctional_fixture",
        artifact_class,
        "RNA" if rna else "DNA",
        sequence,
        _sha(sequence.encode()),
        SequenceRange(0, len(sequence)),
        "circular" if circular else "linear",
        "single" if rna else "double",
        regions,
        features,
        "invented complete molecule",
    )
    primary = b"Software-only fixture. Region names are invented labels, not functional biological elements."
    raw = (sequence.lower() + "\n").encode("ascii")
    primary_source = PayloadSource("primary", _sha(primary), "invented definition")
    sequence_source = PayloadSource(
        "sequence", _sha(raw), "invented independent spelling"
    )
    retained = {"primary": primary, "sequence": raw}
    reviews = []
    for reviewer, role in (
        ("software_fixture_extractor", "extraction"),
        ("software_fixture_reviewer", "independent_review"),
    ):
        statement = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "molecule_fingerprint": expected.fingerprint,
            "primary_source_sha256": primary_source.sha256,
            "sequence_source_sha256": sequence_source.sha256,
            "reviewer": reviewer,
            "role": role,
            "decision": "accept",
            "source_kind": "software_fixture",
        }
        raw_review = json.dumps(statement, sort_keys=True).encode()
        retained[reviewer] = raw_review
        reviews.append(
            PayloadReview(
                reviewer,
                role,
                PayloadSource(
                    reviewer, _sha(raw_review), "invented review declaration"
                ),
            )
        )
    reference = PayloadReference(
        "software_fixture_" + artifact_class,
        "1",
        expected,
        "software_fixture",
        primary_source,
        sequence_source,
        tuple(reviews),
    )
    # A separate candidate object; no generator output determines the expectation.
    candidate = PayloadMolecule.from_json(expected.to_json())
    return candidate, reference, retained


def run_readiness():
    results = {}
    for profile in ("mature_linear_rna", "linear_dna", "circular_plasmid"):
        candidate, reference, retained = build_fixture(profile)
        pin = reference.fingerprint
        result = check_payload(
            candidate,
            reference,
            expected_reference_fingerprint=pin,
            retained_sources=retained,
        )
        assert result.passed, result.diagnostics
        assert result.evidence_boundary == "software_fixture"
        assert (
            result.reference_promotion == "not_promoted"
            and not result.compiler_admission
        )
        # Change a noncoding base and honestly recompute its hash. Source expectation stays frozen.
        sequence = "A" + candidate.sequence[1:]
        mutation = replace(
            candidate, sequence=sequence, sequence_sha256=_sha(sequence.encode())
        )
        rejected = check_payload(
            mutation,
            reference,
            expected_reference_fingerprint=pin,
            retained_sources=retained,
        )
        assert rejected.outcome is CheckOutcome.FAIL
        assert "exact_payload_mismatch" in {item.code for item in rejected.diagnostics}
        results[profile] = (candidate, reference, retained, result, mutation, rejected)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    for profile, (
        candidate,
        reference,
        retained,
        result,
        mutation,
        rejected,
    ) in run_readiness().items():
        print(
            f"{profile}: structural readiness {result.outcome.value}; changed sequence {rejected.outcome.value}; no compiler admission or reference promotion"
        )
        if args.output:
            directory = args.output / profile
            directory.mkdir(parents=True, exist_ok=True)
            for filename, artifact in (
                ("molecule.json", candidate),
                ("reference.json", reference),
                ("result.json", result),
                ("mutation.json", mutation),
                ("mutation-result.json", rejected),
            ):
                (directory / filename).write_text(
                    artifact.to_json() + "\n", encoding="utf-8"
                )
            (directory / "authority-pin.txt").write_text(
                reference.fingerprint + "\n", encoding="ascii"
            )
            sources = directory / "retained-sources"
            sources.mkdir(exist_ok=True)
            for source_id, content in retained.items():
                (sources / source_id).write_bytes(content)
    print(
        "All sequences, source labels and reviewer declarations are invented software fixtures; no biological evidence is asserted."
    )


if __name__ == "__main__":
    main()
