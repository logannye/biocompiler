"""Independent producer edge regressions using tiny artificial fixture records."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.backends.circuit_recoding import construct_recoding_step
from biocompiler.ir.circuit_construction import (
    AmountDeclaration,
    ComplexMemberConstituent,
    ComplexMemberPlan,
    MemberRequirement,
    MultiORFTranslationOperation,
    PeptideProduct,
    RibosomalSkippingOperation,
    RoleDeclaration,
    TranslationOperation,
    TranslationProduct,
    ValueRef,
    ValueSelection,
)
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_recoding import CodonRecoding, TranslationPolicy
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.verification.circuit_construction import reconstruct_for_check
from examples.circuit_molecules import (
    fixture_chemistry,
    fixture_provenance,
    make_molecule,
)
from test_circuit_construction_checking import (
    fixture_request,
    named_port,
    translation_request,
    with_inosine,
)


def with_complex(request):
    provenance = fixture_provenance("edge_complex")
    complex_ = ComplexMemberPlan(
        "complex",
        "rna_complex",
        tuple(
            ComplexMemberConstituent(member.id, 1, provenance)
            for member in request.output_members
        ),
        provenance,
    )
    requirement = MemberRequirement(
        "complex_requirement",
        "control",
        complex_.id,
        None,
        None,
        (RoleDeclaration("complex_role", "complex", "assay_control", "cytoplasm"),),
    )
    return replace(
        request,
        complex_members=(complex_,),
        requirements=(*request.requirements, requirement),
    )


class CircuitConstructionEdgeTests(unittest.TestCase):
    def test_final_alias_budget_checked_before_any_member_allocation(self):
        request = fixture_request(helper=True)
        request = replace(
            request,
            steps=(),
            output_members=tuple(
                replace(member, value=ValueRef("root", "root"))
                for member in request.output_members
            ),
        )
        request = with_complex(request)
        with (
            patch("biocompiler.backends.circuit_construction.MAX_RESIDUES", 6),
            patch(
                "biocompiler.backends.circuit_construction.CircuitMolecule",
                side_effect=AssertionError(
                    "member allocation preceded final budget check"
                ),
            ),
        ):
            candidate = construct_circuit_candidate(request)
        with (
            patch("biocompiler.verification.circuit_construction.MAX_RESIDUES", 6),
            patch(
                "biocompiler.verification.circuit_construction._materialize_member",
                side_effect=AssertionError(
                    "checker allocation preceded final budget check"
                ),
            ),
        ):
            expected = reconstruct_for_check(request)
        self.assertEqual(candidate, expected)
        self.assertEqual(candidate.diagnostics, ("bundle:residue_budget",))
        self.assertEqual(
            set(candidate.missing_members), {"payload", "helper", "complex"}
        )
        self.assertIsNone(candidate.bundle)

    def test_failed_materialization_still_consumes_attempted_work_budget(self):
        request = fixture_request(helper=True)
        original = request.steps[0]
        bad_port = named_port(original.ports[0], "bad_product")
        bad_feature = MoleculeFeature(
            "outside_product",
            "software_fixture",
            CoordinatePath(bad_port.space_id, (IndexSpan(0, 7),), "+"),
            fixture_provenance("invalid-feature"),
        )
        bad_port = replace(
            bad_port,
            feature_transition=replace(
                bad_port.feature_transition, added=(bad_feature,)
            ),
        )
        bad = replace(original, id="bad", ports=(bad_port,))
        good = replace(original, id="good")
        members = tuple(
            replace(member, value=ValueRef("product", "bad_product"))
            if member.id == "payload"
            else member
            for member in request.output_members
        )
        request = replace(request, steps=(bad, good), output_members=members)
        with patch(
            "biocompiler.backends.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
            6,
        ):
            candidate = construct_circuit_candidate(request)
        with patch(
            "biocompiler.verification.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
            6,
        ):
            expected = reconstruct_for_check(request)
        self.assertEqual(candidate, expected)
        self.assertEqual(candidate.values, ())
        self.assertIn("step:bad:invalid_operation", candidate.diagnostics)
        self.assertIn("step:good:residue_budget", candidate.diagnostics)

    def test_final_member_cannot_silently_change_sequence_extent(self):
        request = fixture_request()
        request = replace(
            request,
            output_members=(
                replace(request.output_members[0], sequence_extent="exact_core"),
            ),
        )
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertIn("member:payload:invalid_molecule", candidate.diagnostics)
        self.assertEqual(candidate.missing_members, ("payload",))

    def test_recoding_ports_are_checked_before_invalid_start_or_allocation(self):
        request = translation_request(sequence="CCCGCUUAA")
        original = request.steps[0]
        request = replace(
            request,
            steps=(
                replace(original, ports=(replace(original.ports[0], alphabet="RNA"),)),
            ),
        )
        with patch(
            "biocompiler.backends.circuit_recoding._translate",
            side_effect=AssertionError("invalid output port reached translation"),
        ):
            candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertIn("step:step:unsupported_alphabet", candidate.diagnostics)

    def multi_request(self):
        selection = ValueSelection(
            ValueRef("root", "root"),
            CoordinatePath("source.space", (IndexSpan(0, 9),), "+"),
        )
        policy = TranslationPolicy("ordinary_cds")
        operation = MultiORFTranslationOperation(
            (
                TranslationProduct("first", selection, policy),
                TranslationProduct("second", selection, policy),
            )
        )
        return translation_request(operation, port_ids=("first", "second"))

    def test_translation_cheap_preconditions_precede_work_reservation(self):
        invalid_start = make_molecule("source", "CCCGCUUAA")
        unknown_chemistry = make_molecule("source", "AUGGCUUAA")
        unknown_chemistry = replace(
            unknown_chemistry,
            chemistry=replace(
                unknown_chemistry.chemistry, modification_inventory_status="unknown"
            ),
        )
        for source, code in (
            (invalid_start, "invalid_translation"),
            (unknown_chemistry, "unsupported_translation_chemistry"),
        ):
            with self.subTest(code=code):
                request = translation_request(source=source)
                with patch(
                    "biocompiler.backends.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
                    0,
                ):
                    candidate = construct_circuit_candidate(request)
                with patch(
                    "biocompiler.verification.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
                    0,
                ):
                    expected = reconstruct_for_check(request)
                self.assertEqual(candidate, expected)
                self.assertIn("step:step:" + code, candidate.diagnostics)

    def test_skipping_allocation_preflight_precedes_translation(self):
        operation = RibosomalSkippingOperation(
            ValueSelection(ValueRef("root", "root")),
            TranslationPolicy("ordinary_cds"),
            (PeptideProduct("translated", IndexSpan(1, 2)),),
            "declared_skipping",
        )
        request = translation_request(
            operation, sequence="AUGGCUAAA", assumptions=("declared_skipping",)
        )
        with patch(
            "biocompiler.backends.circuit_recoding._translate",
            side_effect=AssertionError("invalid allocation reached translation"),
        ):
            candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertIn("step:step:invalid_skipping_partition", candidate.diagnostics)

    def test_multi_translation_budget_is_reserved_before_any_translation(self):
        request = self.multi_request()
        with patch(
            "biocompiler.backends.circuit_recoding._translate",
            side_effect=AssertionError("allocation preceded combined budget"),
        ):
            values, used, code = construct_recoding_step(
                request.steps[0], {"root": request.sources[0].molecule}, 3
            )
        self.assertEqual((values, used, code), ((), 0, "residue_budget"))

    def test_multi_translation_drops_all_staged_products_on_late_failure(self):
        request = self.multi_request()
        step = request.steps[0]
        first, second = step.ports
        second = replace(
            second,
            chemistry_transition=replace(
                second.chemistry_transition, output=fixture_chemistry("RNA")
            ),
        )
        step = replace(step, ports=(first, second))
        values, used, code = construct_recoding_step(
            step, {"root": request.sources[0].molecule}, 10
        )
        self.assertEqual(values, ())
        self.assertEqual(used, 4)
        self.assertEqual(code, "invalid_operation")
        request = replace(request, steps=(step,))
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertEqual(candidate.values, ())

    def test_modified_initiation_and_terminal_codons_require_explicit_readouts(self):
        ordinary = TranslationPolicy("ordinary_cds")
        for position, codon_index, triplet, amino_acid in (
            (0, 0, "AUG", "M"),
            (7, 2, "UAA", "*"),
        ):
            with self.subTest(position=position):
                source = with_inosine(make_molecule("source", "AUGGCUUAA"), (position,))
                request = translation_request(source=source)
                candidate = construct_circuit_candidate(request)
                self.assertIn(
                    "step:step:unsupported_translation_chemistry", candidate.diagnostics
                )
                self.assertEqual(candidate, reconstruct_for_check(request))
                policy = replace(
                    ordinary,
                    profile="conditional_cds",
                    recodings=(
                        CodonRecoding(
                            codon_index, triplet, amino_acid, "explicit_readout"
                        ),
                    ),
                )
                operation = TranslationOperation(
                    ValueSelection(ValueRef("root", "root")), policy
                )
                explicit = translation_request(
                    operation, source=source, assumptions=("explicit_readout",)
                )
                candidate = construct_circuit_candidate(explicit)
                self.assertEqual(candidate, reconstruct_for_check(explicit))
                self.assertEqual(candidate.values[0].sequence, "MA")

    def test_skipping_source_maps_keep_offsets_and_explicit_terminal_stop(self):
        selection = ValueSelection(
            ValueRef("root", "root"),
            CoordinatePath("source.space", (IndexSpan(2, 11),), "+"),
        )
        operation = RibosomalSkippingOperation(
            selection,
            TranslationPolicy("ordinary_cds"),
            (
                PeptideProduct("left", IndexSpan(0, 1)),
                PeptideProduct("right", IndexSpan(1, 2)),
            ),
            "declared_skipping",
        )
        request = translation_request(
            operation,
            sequence="CCAUGGCUUAA",
            port_ids=("left", "right"),
            assumptions=("declared_skipping",),
        )
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        values = {value.id: value for value in candidate.values}
        self.assertEqual(
            (values["left"].sequence, values["right"].sequence), ("M", "A")
        )
        self.assertEqual(
            values["left"].segments[0].source_path.spans, (IndexSpan(2, 5),)
        )
        self.assertEqual(
            values["right"].segments[0].source_path.spans, (IndexSpan(5, 8),)
        )
        for value in values.values():
            self.assertEqual(value.consumed[0].source_path.spans, (IndexSpan(8, 11),))

    def test_missing_covalent_constituent_marks_complex_missing(self):
        request = with_complex(fixture_request(helper=True))
        request = replace(
            request,
            output_members=tuple(
                replace(member, form="mature_protein", coding_status="inapplicable")
                if member.id == "helper"
                else member
                for member in request.output_members
            ),
        )
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertEqual(set(candidate.missing_members), {"helper", "complex"})
        self.assertIn("member:complex:unavailable_value", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)

    def test_same_preparation_nominal_alias_amounts_do_not_duplicate_physical_subject(
        self,
    ):
        request = fixture_request(helper=True)
        provenance = fixture_provenance("amount-alias")
        amounts = tuple(
            AmountDeclaration(
                identity + "_amount",
                identity,
                "same_preparation",
                (identity + "_role",),
                1,
                "software_units",
                provenance,
            )
            for identity in ("payload", "helper")
        )
        request = replace(request, amounts=amounts)
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate, reconstruct_for_check(request))
        self.assertIsNone(candidate.bundle)
        self.assertEqual(candidate.experimental_amounts, ())
        self.assertIn("bundle:invalid_inventory", candidate.diagnostics)


if __name__ == "__main__":
    unittest.main()
