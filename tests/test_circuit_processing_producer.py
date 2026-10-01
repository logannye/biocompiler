"""Artificial literal controls for declared partition and circle construction."""

from dataclasses import replace
import unittest

from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.ir.circuit_construction import (
    CircularizationOperation,
    MemberRequirement,
    OutputMember,
    ProcessingProduct,
    ProductPort,
    ProteinCleavageOperation,
    ProteinSplicingOperation,
    RNACleavageOperation,
    RNASplicingOperation,
    RoleDeclaration,
    RootSource,
    TransformStep,
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
from examples.circuit_construction import make_construction_request
from examples.circuit_molecules import (
    fixture_chemistry,
    fixture_provenance,
    make_molecule,
)


def processing_request(operation_cls=RNACleavageOperation, *, origin=2):
    baseline = make_construction_request()
    protein = operation_cls in (ProteinCleavageOperation, ProteinSplicingOperation)
    circle = operation_cls is CircularizationOperation
    alphabet = "protein" if protein else "RNA"
    provenance = fixture_provenance("artificial-processing")
    source = RootSource(
        "substrate",
        make_molecule(
            "substrate-record",
            "MACDEF" if protein else "AACCGG",
            "protein_precursor" if protein else "delivered_rna",
            coding_status="noncoding",
        ),
        provenance,
    )
    selected = ValueSelection(ValueRef("root", source.id))
    if circle:
        recipes = ()
        operation = operation_cls(selected, origin)
        names = ("circle",)
    else:
        spans = (
            (((0, 2), (4, 6)), ((2, 4),))
            if operation_cls in (RNASplicingOperation, ProteinSplicingOperation)
            else (((0, 2),), ((2, 6),))
        )
        recipes = tuple(
            ProcessingProduct(
                name,
                CoordinatePath(
                    source.molecule.space.id,
                    tuple(IndexSpan(*span) for span in path),
                    "+",
                ),
            )
            for name, path in zip(("retained", "released"), spans)
        )
        operation = operation_cls(selected, recipes)
        names = tuple(recipe.port_id for recipe in recipes)
    ports, members, requirements = [], [], []
    for index, name in enumerate(names):
        topology = "circular" if circle else "linear"
        chemistry = ChemistryTransition(
            "explicit_output",
            fixture_chemistry(alphabet, topology),
            tuple(
                ChemistryDisposition(
                    source.id, facet, "declared_replacement", (facet,), provenance
                )
                for facet in sorted(CHEMISTRY_FACETS)
            ),
            provenance,
        )
        ports.append(
            ProductPort(
                name,
                name + ".frame",
                alphabet,
                topology,
                chemistry,
                FeatureTransition((), (), provenance),
            )
        )
        members.append(
            OutputMember(
                name + ".member",
                ValueRef("product", name),
                name + ".final",
                "mature_protein" if protein else "delivered_rna",
                "complete",
                "inapplicable" if protein else "noncoding",
                provenance,
            )
        )
        category = "encoded_product" if protein or index else "payload"
        role = RoleDeclaration(
            name + ".role",
            "artificial-processing",
            "helper" if category == "encoded_product" else "requested_payload",
            baseline.circuit.profile.target.compartments[0],
        )
        requirements.append(
            MemberRequirement(
                name + ".requirement", category, members[-1].id, None, None, (role,)
            )
        )
    sources = [source]
    if protein:
        payload = RootSource(
            "payload-source",
            make_molecule("supplied-payload", "AC", coding_status="noncoding"),
            provenance,
        )
        sources.append(payload)
        members.append(
            OutputMember(
                "payload",
                ValueRef("root", payload.id),
                "payload.final",
                "delivered_rna",
                "complete",
                "noncoding",
                provenance,
            )
        )
        requirements.append(
            MemberRequirement(
                "payload.requirement",
                "payload",
                "payload",
                None,
                None,
                (
                    RoleDeclaration(
                        "payload.role",
                        "artificial-payload",
                        "requested_payload",
                        baseline.circuit.profile.target.compartments[0],
                    ),
                ),
            )
        )
    circuit = (
        replace(baseline.circuit, requested_form="circular_rna")
        if circle
        else baseline.circuit
    )
    step = TransformStep(
        "processing",
        operation,
        tuple(ports),
        ("Artificial declared product partition only.",),
        provenance,
    )
    return replace(
        baseline,
        circuit=circuit,
        sources=tuple(sources),
        steps=(step,),
        output_members=tuple(members),
        requirements=tuple(requirements),
        payload_structures=(),
    )


class ProcessingProducerTests(unittest.TestCase):
    def test_explicit_rna_cleavage_retains_every_fragment(self):
        candidate = construct_circuit_candidate(processing_request())
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"retained": "AA", "released": "CCGG"},
        )
        self.assertEqual(len(candidate.bundle.molecules), 2)

    def test_explicit_rna_splicing_retains_excised_fragment(self):
        candidate = construct_circuit_candidate(
            processing_request(RNASplicingOperation)
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"retained": "AAGG", "released": "CC"},
        )

    def test_protein_cleavage_and_splicing_are_distinct(self):
        cleavage = construct_circuit_candidate(
            processing_request(ProteinCleavageOperation)
        )
        splicing = construct_circuit_candidate(
            processing_request(ProteinSplicingOperation)
        )
        self.assertEqual(cleavage.diagnostics, ())
        self.assertEqual(splicing.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in cleavage.values},
            {"retained": "MA", "released": "CDEF"},
        )
        self.assertEqual(
            {value.id: value.sequence for value in splicing.values},
            {"retained": "MAEF", "released": "CD"},
        )

    def test_declared_circle_keeps_exact_nominated_origin(self):
        candidate = construct_circuit_candidate(
            processing_request(CircularizationOperation)
        )
        self.assertEqual(candidate.diagnostics, ())
        value = candidate.values[0]
        self.assertEqual(value.sequence, "CCGGAA")
        self.assertEqual(value.space.topology, "circular")
        self.assertEqual(
            tuple(
                (span.start, span.end) for span in value.segments[0].source_path.spans
            ),
            ((2, 6), (0, 2)),
        )

    def test_circle_origin_at_length_cannot_silently_become_zero(self):
        candidate = construct_circuit_candidate(
            processing_request(CircularizationOperation, origin=6)
        )
        self.assertIn("step:processing:invalid_selection", candidate.diagnostics)
        self.assertEqual(candidate.values, ())
        self.assertIsNone(candidate.bundle)

    def test_omitted_or_duplicate_residues_reject_whole_processing_step(self):
        request = processing_request()
        step = request.steps[0]
        for start in (1, 3):
            recipe = step.operation.products[0]
            # Recipe order is by port ID: released, then retained.
            changed_recipe = replace(
                recipe, path=replace(recipe.path, spans=(IndexSpan(start, 6),))
            )
            changed_op = replace(
                step.operation, products=(changed_recipe, step.operation.products[1])
            )
            changed = replace(request, steps=(replace(step, operation=changed_op),))
            candidate = construct_circuit_candidate(changed)
            self.assertIn(
                "step:processing:invalid_processing_partition", candidate.diagnostics
            )
            self.assertEqual(candidate.values, ())
            self.assertIsNone(candidate.bundle)


if __name__ == "__main__":
    unittest.main()
