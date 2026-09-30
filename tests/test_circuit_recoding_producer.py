"""Tiny artificial editing/translation controls, without biological function claims."""

from dataclasses import replace
import unittest

from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.ir.circuit_construction import (
    BaseEditingOperation,
    ConditionalTranslationOperation,
    MemberRequirement,
    MultiORFTranslationOperation,
    OutputMember,
    PeptideProduct,
    ProductPort,
    RibosomalSkippingOperation,
    RoleDeclaration,
    RootSource,
    TransformStep,
    TranslationBranch,
    TranslationOperation,
    TranslationProduct,
    ValueRef,
    ValueSelection,
)
from biocompiler.ir.circuit_recoding import (
    CanonicalBaseEdit,
    ChemicalBaseEdit,
    CodonRecoding,
    TranslationPolicy,
)
from biocompiler.ir.circuit_transitions import (
    CHEMISTRY_FACETS,
    ChemistryDisposition,
    ChemistryTransition,
    FeatureTransition,
)
from biocompiler.ir.molecule_chemistry import BaseModification, ChemicalIdentity
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from examples.circuit_construction import make_construction_request
from examples.circuit_molecules import (
    fixture_chemistry,
    fixture_provenance,
    make_molecule,
)


PROVENANCE = fixture_provenance("recoding-fixture")
INOSINE = ChemicalIdentity("biocompiler.chemical", "inosine", "1")


def recoding_request(
    sequence="AUGGCUUAA",
    *,
    kind="ordinary",
    input_chemistry=None,
    output_chemistry=None,
):
    baseline = make_construction_request()
    source = RootSource(
        "rna",
        make_molecule("rna-record", sequence, chemistry=input_chemistry),
        PROVENANCE,
    )
    selection = ValueSelection(ValueRef("root", "rna"))
    policy = TranslationPolicy("ordinary_cds")
    assumptions = ()
    names = ("peptide",)
    if kind == "ordinary":
        operation = TranslationOperation(selection, policy)
    elif kind == "conditional":
        policy = TranslationPolicy(
            "conditional_cds", recodings=(CodonRecoding(1, "UAG", "Q", "readthrough"),)
        )
        assumptions = ("readthrough",)
        operation = TranslationOperation(selection, policy)
    elif kind == "chemical_edit":
        operation = BaseEditingOperation(
            selection, (), (ChemicalBaseEdit(1, "A", None, INOSINE),)
        )
        names = ("edited",)
    elif kind == "canonical_edit":
        operation = BaseEditingOperation(
            selection, (CanonicalBaseEdit(1, "A", "G"),), ()
        )
        names = ("edited",)
    elif kind == "skipping":
        operation = RibosomalSkippingOperation(
            selection,
            policy,
            (
                PeptideProduct("first", IndexSpan(0, 2)),
                PeptideProduct("second", IndexSpan(2, 3)),
            ),
            "declared_skip",
        )
        assumptions = ("declared_skip",)
        names = ("first", "second")
    elif kind == "multi_orf":
        first = ValueSelection(
            selection.value,
            CoordinatePath(source.molecule.space.id, (IndexSpan(0, 6),), "+"),
        )
        second = ValueSelection(
            selection.value,
            CoordinatePath(source.molecule.space.id, (IndexSpan(6, 15),), "+"),
        )
        operation = MultiORFTranslationOperation(
            (
                TranslationProduct("first", first, policy),
                TranslationProduct("second", second, policy),
            )
        )
        names = ("first", "second")
    elif kind == "branches":
        operation = ConditionalTranslationOperation(
            (
                TranslationBranch("on", "on-state", selection, policy, "peptide"),
                TranslationBranch("off", "off-state", selection, None, None),
            )
        )
        assumptions = ("on-state", "off-state")
    else:
        raise ValueError(kind)
    editing = kind.endswith("edit")
    alphabet = "RNA" if editing else "protein"
    chemistry = output_chemistry or fixture_chemistry(alphabet)
    facets = set(CHEMISTRY_FACETS) | {
        "modification:" + item.id for item in source.molecule.chemistry.modifications
    }
    dispositions = []
    for facet in sorted(facets):
        targets = (facet,) if facet in CHEMISTRY_FACETS else ("modification_inventory",)
        if facet == "modification_inventory":
            targets += tuple(
                "modification:" + item.id for item in chemistry.modifications
            )
        dispositions.append(
            ChemistryDisposition(
                "rna", facet, "declared_replacement", targets, PROVENANCE
            )
        )
    transition = ChemistryTransition(
        "explicit_output", chemistry, tuple(dispositions), PROVENANCE
    )
    ports = tuple(
        ProductPort(
            name,
            name + ".frame",
            alphabet,
            "linear",
            transition,
            FeatureTransition((), (), PROVENANCE),
        )
        for name in names
    )
    step = TransformStep("event", operation, ports, assumptions, PROVENANCE)
    members = [
        OutputMember(
            "payload",
            selection.value,
            "payload.final",
            "delivered_rna",
            "complete",
            "coding",
            PROVENANCE,
        )
    ]
    compartment = baseline.circuit.profile.target.compartments[0]
    requirements = [
        MemberRequirement(
            "payload.required",
            "payload",
            "payload",
            None,
            None,
            (
                RoleDeclaration(
                    "payload.role",
                    "artificial-payload",
                    "requested_payload",
                    compartment,
                ),
            ),
        )
    ]
    for name in names:
        members.append(
            OutputMember(
                name,
                ValueRef("product", name),
                name + ".final",
                "edited_rna" if editing else "mature_protein",
                "complete",
                "coding" if editing else "inapplicable",
                PROVENANCE,
            )
        )
        requirements.append(
            MemberRequirement(
                name + ".required",
                "encoded_product",
                name,
                None,
                None,
                (
                    RoleDeclaration(
                        name + ".role", "artificial-product", "helper", compartment
                    ),
                ),
            )
        )
    return replace(
        baseline,
        sources=(source,),
        steps=(step,),
        output_members=tuple(members),
        requirements=tuple(requirements),
        payload_structures=(),
    )


class RecodingProducerTests(unittest.TestCase):
    def test_standard_translation_has_exact_codon_and_stop_provenance(self):
        candidate = construct_circuit_candidate(recoding_request())
        self.assertEqual(candidate.diagnostics, ())
        value = candidate.values[0]
        self.assertEqual(value.sequence, "MA")
        self.assertEqual(value.segments[0].rule, "translation_codon.v1")
        self.assertEqual(value.segments[0].source_path.spans, (IndexSpan(0, 6),))
        self.assertEqual(value.consumed[0].source_path.spans, (IndexSpan(6, 9),))
        self.assertEqual(value.consumed[0].reason, "terminal_stop")

    def test_structural_translation_never_guesses_a_terminal_stop(self):
        candidate = construct_circuit_candidate(recoding_request("AUGGCUGCU"))
        self.assertIn("step:event:invalid_translation", candidate.diagnostics)
        self.assertEqual(candidate.values, ())
        self.assertIsNone(candidate.bundle)

    def test_conditional_internal_stop_requires_bound_literal_recoding(self):
        candidate = construct_circuit_candidate(
            recoding_request("AUGUAGUAA", kind="conditional")
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(candidate.values[0].sequence, "MQ")
        ordinary = construct_circuit_candidate(recoding_request("AUGUAGUAA"))
        self.assertIn("step:event:invalid_translation", ordinary.diagnostics)

    def test_inosine_edit_preserves_canonical_a_with_separate_chemistry(self):
        modification = BaseModification(
            "edited-I", INOSINE, "A", "positions", (1,), PROVENANCE
        )
        chemistry = replace(fixture_chemistry(), modifications=(modification,))
        candidate = construct_circuit_candidate(
            recoding_request("AAA", kind="chemical_edit", output_chemistry=chemistry)
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(candidate.values[0].sequence, "AAA")
        self.assertEqual(
            candidate.values[0].chemistry.modifications[0].identity, INOSINE
        )

    def test_canonical_change_is_a_different_explicit_operation_declaration(self):
        candidate = construct_circuit_candidate(
            recoding_request("AAA", kind="canonical_edit")
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(candidate.values[0].sequence, "AGA")
        self.assertEqual(candidate.values[0].chemistry.modifications, ())

    def test_offsite_chemical_change_is_not_authorized_by_one_edit(self):
        modification = BaseModification(
            "wrong-I", INOSINE, "A", "positions", (2,), PROVENANCE
        )
        chemistry = replace(fixture_chemistry(), modifications=(modification,))
        candidate = construct_circuit_candidate(
            recoding_request("AAA", kind="chemical_edit", output_chemistry=chemistry)
        )
        self.assertIn("step:event:invalid_edit", candidate.diagnostics)
        self.assertEqual(candidate.values, ())

    def test_modified_codon_requires_an_explicit_readout(self):
        modification = BaseModification(
            "I", INOSINE, "A", "positions", (0,), PROVENANCE
        )
        chemistry = replace(fixture_chemistry(), modifications=(modification,))
        request = recoding_request(input_chemistry=chemistry)
        candidate = construct_circuit_candidate(request)
        self.assertIn(
            "step:event:unsupported_translation_chemistry", candidate.diagnostics
        )
        step = request.steps[0]
        policy = TranslationPolicy(
            "conditional_cds",
            recodings=(CodonRecoding(0, "AUG", "M", "declared-readout"),),
        )
        changed = replace(
            request,
            steps=(
                replace(
                    step,
                    operation=replace(step.operation, policy=policy),
                    assumptions=("declared-readout",),
                ),
            ),
        )
        candidate = construct_circuit_candidate(changed)
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(candidate.values[0].sequence, "MA")

    def test_ribosomal_skipping_keeps_all_residues_without_covalent_precursor(self):
        candidate = construct_circuit_candidate(
            recoding_request("AUGGCUGGUUAA", kind="skipping")
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"first": "MA", "second": "G"},
        )
        self.assertEqual(
            candidate.values[1].segments[0].source_path.spans, (IndexSpan(6, 9),)
        )
        self.assertEqual(
            candidate.values[1].consumed[0].source_path.spans, (IndexSpan(9, 12),)
        )

    def test_skipping_cannot_drop_one_junction_residue(self):
        request = recoding_request("AUGGCUGGUUAA", kind="skipping")
        step = request.steps[0]
        operation = replace(
            step.operation,
            products=(
                PeptideProduct("first", IndexSpan(0, 1)),
                PeptideProduct("second", IndexSpan(2, 3)),
            ),
        )
        candidate = construct_circuit_candidate(
            replace(request, steps=(replace(step, operation=operation),))
        )
        self.assertIn("step:event:invalid_skipping_partition", candidate.diagnostics)

    def test_multi_orf_keeps_separate_explicit_coding_paths(self):
        candidate = construct_circuit_candidate(
            recoding_request("AUGUAAAUGGCUUAA", kind="multi_orf")
        )
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"first": "M", "second": "MA"},
        )

    def test_declared_no_product_branch_does_not_erase_required_output(self):
        request = recoding_request(kind="branches")
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(tuple(value.id for value in candidate.values), ("peptide",))
        self.assertEqual(len(request.steps[0].operation.branches), 2)
        self.assertEqual(candidate.missing_members, ())


if __name__ == "__main__":
    unittest.main()
