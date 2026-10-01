"""Construct and reconstruct a complete, nonfunctional software RNA fixture.

All fragments, labels and chemistry declarations are invented test authority.
No sequence is offered as a functional component or biological reference.
Run: PYTHONPATH=src python examples/molecular_design.py --output DIRECTORY
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from biocompiler.artifacts.archive import read_archive
from biocompiler.compiler.molecular_design_build import (
    build_molecular_design_package,
    publish_molecular_design_package,
    verify_molecular_design_package,
)
from biocompiler.ir.molecular_design import (
    FragmentPlacement,
    MolecularDesignArtifact,
    MolecularDesignConstruct,
    MolecularDesignRequest,
    SequenceFragment,
)
from biocompiler.ir.payload import PayloadFeature
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.molecular_design import check_molecular_design


EXPECTED = "GGAUGGCUUAACCAAAA"
ALTERNATIVE_EXPECTED = "GGAUGGCCUAACCAAAA"


def prepare_design_request(*, alternative=False):
    """Freeze independent fragment/layout authority, before invoking generation."""
    definitions = (
        ("leader", "CCGGUU", "five_prime_utr", 2, 4, 0, 2, None),
        (
            "coding",
            "CCAUGGCCUAAGG" if alternative else "CCAUGGCUUAAGG",
            "cds",
            2,
            11,
            2,
            11,
            "MA*",
        ),
        ("trailer", "UCCG", "three_prime_utr", 1, 3, 11, 13, None),
        ("tail", "AAAA", "poly_a", 0, 4, 13, 17, None),
    )
    fragments = []
    placements = []
    for (
        identity,
        sequence,
        kind,
        start,
        end,
        dest_start,
        dest_end,
        protein,
    ) in definitions:
        fragment = SequenceFragment(
            identity,
            sequence,
            hashlib.sha256(sequence.encode("ascii")).hexdigest(),
            f"fixtures/molecular_design.json#{identity}",
        )
        fragments.append(fragment)
        placements.append(
            FragmentPlacement(
                identity,
                kind,
                fragment.id,
                fragment.fingerprint,
                SequenceRange(start, end),
                SequenceRange(dest_start, dest_end),
                protein_sequence=protein,
            )
        )
    features = tuple(
        PayloadFeature(name, "known", f"fixtures/molecular_design.json#{name}", value)
        for name, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    return MolecularDesignRequest(
        "nonfunctional_rna_design",
        "nonfunctional_rna",
        tuple(fragments),
        tuple(placements),
        features,
    )


def run_design(output):
    output.mkdir(parents=True, exist_ok=True)
    request = prepare_design_request()
    package = build_molecular_design_package(request)
    verified = verify_molecular_design_package(package.data, expected_request=request)
    assert verified.build_fingerprint == package.build_fingerprint
    _, files, _ = read_archive(package.data)
    artifact = MolecularDesignArtifact.from_json(files["candidate.json"].decode())
    construct = MolecularDesignConstruct.from_json(files["construct.json"].decode())
    assert artifact.molecule.sequence == EXPECTED
    assert artifact.molecule.boundaries == SequenceRange(0, 17)
    (output / "request.json").write_text(request.to_json() + "\n", encoding="utf-8")
    publish_molecular_design_package(package, output / "design.bcb")
    for name in ("candidate.json", "molecular.json", "construct.json", "handoff.json"):
        (output / name).write_bytes(files[name])

    alternative = prepare_design_request(alternative=True)
    second = build_molecular_design_package(alternative)
    _, alternate_files, _ = read_archive(second.data)
    alternate_artifact = MolecularDesignArtifact.from_json(
        alternate_files["candidate.json"].decode()
    )
    assert alternate_artifact.molecule.sequence == ALTERNATIVE_EXPECTED
    assert second.build_fingerprint != package.build_fingerprint
    (output / "alternative-request.json").write_text(
        alternative.to_json() + "\n", encoding="utf-8"
    )
    publish_molecular_design_package(second, output / "alternative.bcb")

    # Recompute the sequence hash: exact request authority must still reject this
    # synonymous substitution even though the expected protein stays MA*.
    edited_molecule = replace(
        artifact.molecule,
        sequence=ALTERNATIVE_EXPECTED,
        sequence_sha256=hashlib.sha256(ALTERNATIVE_EXPECTED.encode()).hexdigest(),
    )
    forged = replace(artifact, molecule=edited_molecule)
    failure = check_molecular_design(
        request, construct, forged, expected_request_fingerprint=request.fingerprint
    )
    assert failure.outcome is CheckOutcome.FAIL
    (output / "substitution-failure.json").write_text(
        failure.to_json() + "\n", encoding="utf-8"
    )
    print(
        f"Complete structural RNA software fixture: {len(EXPECTED)} bases, 4 regions."
    )
    print(f"Build fingerprint: {package.build_fingerprint}")
    print(
        "Authorized alternate design reconstructed; unauthorized synonymous edit rejected."
    )
    print(
        "Biological behavior, material identity and human therapeutic admission remain unestablished."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        run_design(args.output)
    else:
        with TemporaryDirectory(prefix="biocompiler-molecular-design-") as directory:
            run_design(Path(directory))


if __name__ == "__main__":
    main()
