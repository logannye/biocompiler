"""Exercise generic construction bookkeeping with six-symbol artificial fixtures.

This example does not recreate a published construct or implement the attached
circuit intent. Explicit chemistry replacements are specifications, not evidence
that cells carry out any of the declared operations.
"""

import argparse
from pathlib import Path

from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_payloads import (
    PayloadStructureContract,
    RequiredPayloadRegion,
)
from biocompiler.ir.circuit_construction import (
    CircuitConstructionRequest,
    ConcatenateOperation,
    MemberRequirement,
    OrientationOperation,
    OutputMember,
    ProductPort,
    RoleDeclaration,
    RootSource,
    SliceOperation,
    TransformStep,
    TranscriptionOperation,
    ValueRef,
    ValueSelection,
)
from biocompiler.ir.circuit_transitions import (
    CHEMISTRY_FACETS,
    ChemistryDisposition,
    ChemistryTransition,
    FeatureTransition,
)
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan

try:
    from examples.circuit_intent import make_circuit_requests
    from examples.circuit_molecules import (
        fixture_chemistry,
        fixture_provenance,
        make_molecule,
    )
except ModuleNotFoundError:
    from circuit_intent import make_circuit_requests
    from circuit_molecules import fixture_chemistry, fixture_provenance, make_molecule


def make_construction_request():
    """Output metadata contains no expected bases; roots and operations are fixed."""
    provenance = fixture_provenance("construction-software-fixture")
    circuit = make_circuit_requests()["product"]
    source = RootSource(
        "source",
        make_molecule("artificial-dna", "ACGTTA", "deposited_template_record"),
        provenance,
    )

    def selection(id, spans=None, *, root=False):
        return ValueSelection(
            ValueRef("root" if root else "product", id),
            None
            if spans is None
            else CoordinatePath(
                id + ".frame", tuple(IndexSpan(*span) for span in spans), "+"
            ),
        )

    def port(id, alphabet, source_ids):
        dispositions = tuple(
            ChemistryDisposition(
                source_id, facet, "declared_replacement", (facet,), provenance
            )
            for source_id in source_ids
            for facet in sorted(CHEMISTRY_FACETS)
        )
        chemistry = ChemistryTransition(
            "explicit_output", fixture_chemistry(alphabet), dispositions, provenance
        )
        return ProductPort(
            id,
            id + ".frame",
            alphabet,
            "linear",
            chemistry,
            FeatureTransition(
                (),
                (
                    MoleculeFeature(
                        "nominal-region",
                        "artificial_noncoding_region",
                        CoordinatePath(id + ".frame", (IndexSpan(0, 6),), "+"),
                        provenance,
                    ),
                )
                if id == "joined"
                else (),
                provenance,
            ),
        )

    steps = (
        TransformStep(
            "orient",
            OrientationOperation(selection("source", root=True), "reverse_complement"),
            (port("oriented", "DNA", ("source",)),),
            ("Explicit software orientation only.",),
            provenance,
        ),
        TransformStep(
            "transcribe",
            TranscriptionOperation(selection("oriented")),
            (port("transcript", "RNA", ("oriented",)),),
            ("Explicit coding-strand symbol mapping only.",),
            provenance,
        ),
        TransformStep(
            "slice",
            SliceOperation(selection("transcript", ((1, 5),))),
            (port("selected", "RNA", ("transcript",)),),
            ("Declared software substring, not a cleavage reaction.",),
            provenance,
        ),
        TransformStep(
            "join",
            ConcatenateOperation(
                (selection("selected"), selection("transcript", ((0, 2),)))
            ),
            (port("joined", "RNA", ("selected", "transcript")),),
            ("Declared symbol concatenation, not a ligation reaction.",),
            provenance,
        ),
    )
    output = OutputMember(
        "artificial-output",
        ValueRef("product", "joined"),
        "artificial-output.frame",
        "delivered_rna",
        "complete",
        "noncoding",
        provenance,
    )
    role = RoleDeclaration(
        "payload-role",
        "artificial-structural-fixture",
        "requested_payload",
        circuit.profile.target.compartments[0],
    )
    requirement = MemberRequirement(
        "required-payload", "payload", output.id, None, None, (role,)
    )
    return CircuitConstructionRequest(
        "artificial-construction",
        circuit,
        (source,),
        steps,
        (output,),
        (requirement,),
        "strict",
        payload_structures=(
            PayloadStructureContract(
                output.id,
                "delivered_rna",
                "linear",
                (
                    RequiredPayloadRegion(
                        "nominal-region", "artificial_noncoding_region"
                    ),
                ),
                provenance,
            ),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    request = make_construction_request()
    build = build_circuit_construction(request)
    candidate = build.candidate
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "request.json").write_text(
            request.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "candidate.json").write_text(
            candidate.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "build.json").write_text(
            build.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "assessment.json").write_text(
            build.assessment.to_json() + "\n", encoding="utf-8"
        )
    print("Supplied construction correspondence:", build.assessment.outcome.value)
    print(
        "Circuit function, reference reconstruction and human admission remain unestablished."
    )
    print(
        "Proposed intermediate values:",
        [(value.id, value.sequence) for value in candidate.values],
    )
    print("Diagnostics:", candidate.diagnostics)


if __name__ == "__main__":
    main()
