"""Describe tiny artificial molecules without constructing biological payloads.

Every spelling, annotation, source frame and amount here is a software fixture.
The RNA coding annotations are intentionally descriptive examples, not validated
ORFs. The declared molecules have no established connection to the Boolean
response, original therapeutic intent, physical experiment or human deployment.
"""

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path

from biocompiler.artifacts.circuit_molecules import (
    CircuitMoleculeRecord,
    ExperimentalAmount,
)
from biocompiler.ir.circuit_molecules import (
    AssemblyOrigin,
    CircuitMolecule,
    CircuitMoleculeSet,
    ComplexConstituent,
    FormCoordinateMapping,
    MolecularComplex,
    MoleculeFeature,
    MoleculeRoleInstance,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import (
    ChemicalIdentity,
    ChemistryClaim,
    MoleculeChemistry,
    TailDeclaration,
    TailLength,
)
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)

try:
    from examples.circuit_intent import make_circuit_requests
except ModuleNotFoundError:
    from circuit_intent import make_circuit_requests


_FIXTURE_NOTICE = (
    b"Tiny artificial molecular declarations in examples/circuit_molecules.py; "
    b"not a biological source, sequence verification, or experimental observation."
)


def fixture_provenance(locator="software-fixture-declaration"):
    """The pin identifies this notice only; it establishes no sequence authority."""
    return DeclarationProvenance(
        "declared",
        (
            PinnedIdentity(
                "source",
                "artificial-molecule-notice",
                "1",
                hashlib.sha256(_FIXTURE_NOTICE).hexdigest(),
            ),
        ),
        "examples/circuit_molecules.py:" + locator,
        "Artificial source-frame and annotation declarations only; the notice pin does not verify any bases or biology.",
    )


def fixture_chemistry(alphabet="RNA", topology="linear"):
    """Explicit nominal choices for fixtures, not measured material chemistry."""
    provenance = fixture_provenance("chemistry")

    def claim(status, identity=None):
        return ChemistryClaim(
            status,
            None
            if identity is None
            else ChemicalIdentity("software_fixture.chemical", identity, "1"),
            provenance,
        )

    cap = claim(
        "absent" if alphabet == "RNA" and topology == "linear" else "inapplicable"
    )
    if topology == "circular":
        start, finish = claim("inapplicable"), claim("inapplicable")
    elif alphabet == "protein":
        start, finish = (
            claim("declared", "amino_terminus"),
            claim("declared", "carboxyl_terminus"),
        )
    else:
        start, finish = claim("declared", "hydroxyl"), claim("declared", "hydroxyl")
    tail = (
        TailDeclaration(
            "declared", "absent", TailLength("exact", exact=0), None, provenance
        )
        if alphabet == "RNA" and topology == "linear"
        else TailDeclaration("inapplicable", None, None, None, provenance)
    )
    return MoleculeChemistry(cap, start, finish, (), "declared", provenance, tail)


def make_molecule(
    id,
    sequence,
    form="delivered_rna",
    topology="linear",
    coding_status="coding",
    chemistry=None,
    *,
    features=(),
    sequence_extent="complete",
):
    """Retain supplied fixture symbols and distinct source/destination frames."""
    alphabet = (
        "protein"
        if form in {"protein_precursor", "mature_protein"}
        else "DNA"
        if form
        in {"deposited_template_record", "dna_expression_template", "delivered_dna"}
        else "RNA"
    )
    if alphabet == "protein":
        coding_status = "inapplicable"
    axis = "N_to_C" if alphabet == "protein" else "5prime_to_3prime"
    destination = CoordinateSpace(
        id + ".space", alphabet, len(sequence), topology, axis
    )
    source = CoordinateSpace(
        id + ".declared_source_space", alphabet, len(sequence), "linear", axis
    )
    provenance = fixture_provenance(id)
    origin = AssemblyOrigin(
        id + ".origin",
        CoordinatePath(destination.id, (IndexSpan(0, len(sequence)),), "+"),
        source,
        CoordinatePath(source.id, (IndexSpan(0, len(sequence)),), "+"),
        provenance,
    )
    return CircuitMolecule(
        id,
        form,
        destination,
        sequence,
        sequence_extent,
        coding_status,
        (origin,),
        tuple(features),
        fixture_chemistry(alphabet, topology) if chemistry is None else chemistry,
        provenance,
    )


def _feature(molecule, id, kind, spans, *, reading_frame=None, strand="+"):
    return MoleculeFeature(
        id,
        kind,
        CoordinatePath(
            molecule.space.id, tuple(IndexSpan(*span) for span in spans), strand
        ),
        fixture_provenance("annotation." + id),
        reading_frame,
    )


def make_molecule_record():
    """Return a declaration archive exercising R3 structures with invented data."""
    request = make_circuit_requests()["product"]
    first = make_molecule("artificial_rna_A", "ACGUAGAAACGU")
    first = replace(
        first,
        features=(
            _feature(
                first, "short_upstream_annotation", "uORF", ((0, 6),), reading_frame=0
            ),
            _feature(
                first, "main_coding_annotation", "CDS", ((0, 12),), reading_frame=0
            ),
            _feature(first, "internal_conditional_stop", "conditional_stop", ((3, 6),)),
            _feature(first, "overlapping_recognition", "recognition_site", ((2, 7),)),
            _feature(first, "repeat_occurrence_1", "repeated_motif", ((0, 3),)),
            _feature(first, "repeat_occurrence_2", "repeated_motif", ((8, 11),)),
        ),
    )
    second = make_molecule("artificial_rna_B", "UACGACGU")
    noncoding = make_molecule(
        "artificial_noncoding", "CUACGU", coding_status="noncoding"
    )
    post_tail = make_molecule(
        "artificial_post_polya", "CGAAAACG", coding_status="noncoding"
    )
    post_tail = replace(
        post_tail,
        features=(
            _feature(post_tail, "internal_adenine_tract", "internal_poly_a", ((2, 6),)),
            _feature(
                post_tail, "post_polya_extension", "post_poly_a_extension", ((6, 8),)
            ),
        ),
    )
    circle = make_molecule(
        "artificial_circle", "ACGUAC", topology="circular", coding_status="noncoding"
    )
    circle = replace(
        circle,
        features=(
            _feature(
                circle,
                "crosses_nominated_origin",
                "origin_crossing_annotation",
                ((4, 6), (0, 2)),
            ),
            _feature(
                circle, "reverse_annotation", "recognition_site", ((1, 4),), strand="-"
            ),
        ),
    )
    precursor = make_molecule("artificial_precursor", "MAG", form="protein_precursor")
    mature = make_molecule("artificial_mature", "AG", form="mature_protein")
    complex_ = MolecularComplex(
        "artificial_protein_complex",
        "protein_complex",
        (
            ComplexConstituent(
                precursor.id,
                precursor.fingerprint,
                1,
                fixture_provenance("constituent_1"),
            ),
            ComplexConstituent(
                mature.id, mature.fingerprint, 2, fixture_provenance("constituent_2")
            ),
        ),
        fixture_provenance("complex"),
    )
    uncertain_chemistry = replace(
        fixture_chemistry(),
        terminal_tail=TailDeclaration(
            "declared",
            "appended_terminal",
            TailLength("bounded", lower=1, upper=4),
            None,
            DeclarationProvenance(
                "unknown",
                (),
                None,
                "Invented uncertainty example; no material or source measurements.",
            ),
        ),
    )
    core = make_molecule(
        "artificial_uncertain_core",
        "ACGU",
        coding_status="noncoding",
        chemistry=uncertain_chemistry,
        sequence_extent="exact_core",
    )
    mapping = FormCoordinateMapping(
        "declared_precursor_product_correspondence",
        precursor.id,
        precursor.fingerprint,
        mature.id,
        mature.fingerprint,
        CoordinatePath(precursor.space.id, (IndexSpan(1, 3),), "+"),
        CoordinatePath(mature.space.id, (IndexSpan(0, 2),), "+"),
        "protein_cleavage",
        fixture_provenance("unverified_processing_declaration"),
    )
    molecules = (first, second, noncoding, post_tail, circle, precursor, mature, core)
    roles = [
        MoleculeRoleInstance(
            "payload_A",
            first.id,
            first.fingerprint,
            "fixture_role_A",
            "requested_payload",
            "cytoplasm",
        ),
        MoleculeRoleInstance(
            "shared_A_role",
            first.id,
            first.fingerprint,
            "second_role_for_same_subject",
            "helper",
            "cytoplasm",
        ),
        MoleculeRoleInstance(
            "payload_B",
            second.id,
            second.fingerprint,
            "fixture_role_B",
            "requested_payload",
            "cytoplasm",
        ),
    ]
    roles.extend(
        MoleculeRoleInstance(
            subject.id + ".role",
            subject.id,
            subject.fingerprint,
            "declared_fixture_subject",
            "helper",
            "cytoplasm",
        )
        for subject in (*molecules[2:], complex_)
    )
    bundle = CircuitMoleculeSet(
        "artificial_molecule_set",
        request,
        molecules,
        (complex_,),
        tuple(roles),
        (mapping,),
    )
    amount = ExperimentalAmount(
        "one_unknown_preparation_amount",
        first.id,
        first.fingerprint,
        "artificial_shared_preparation",
        ("payload_A", "shared_A_role"),
        None,
        "unknown",
        DeclarationProvenance(
            "unknown",
            (),
            None,
            "Physical quantity was not supplied; two roles do not imply two doses.",
        ),
    )
    return CircuitMoleculeRecord(
        bundle,
        (amount,),
        {"fixture": "artificial_R3_declarations", "run_label": "example"},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    record = make_molecule_record()
    restored = CircuitMoleculeRecord.from_json(record.to_json())
    assert restored.to_dict() == record.to_dict()
    assert restored.nominal_bundle_identity == record.nominal_bundle_identity
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "record.json").write_text(record.to_json() + "\n", encoding="utf-8")
    (args.output / "bundle.json").write_text(
        record.bundle.to_json() + "\n", encoding="utf-8"
    )
    for molecule in record.bundle.molecules:
        completeness = (
            "complete" if molecule.declared_nominal_complete else "incomplete"
        )
        print(
            f"{molecule.id}: supplied-spelling {molecule.spelling_identity}; nominal declaration {completeness}"
        )
    print(
        "Molecular function: unestablished; source correspondence unverified; human admission not granted."
    )


if __name__ == "__main__":
    main()
