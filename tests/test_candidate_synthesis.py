"""Source-driven coding choices and layouts, without biological inference."""

from dataclasses import replace
import hashlib
import unittest

import biocompiler as bc
from biocompiler.backends.candidate import emit_candidate
from biocompiler.compiler.candidate_requirements import lower_candidate_requirements
from biocompiler.errors import SerializationError
from biocompiler.ir.candidate import (
    CandidateConstraints,
    CandidateRequest,
    MolecularLibrary,
    MolecularPart,
    ProductBinding,
    RNAArchitecture,
)
from biocompiler.ir.candidate_selection import CandidateLayout, CandidateSelection
from biocompiler.ir.molecular_design import SequenceFragment
from biocompiler.ir.payload import PayloadFeature
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.synthesis.candidate import derive_candidate_layout, select_candidate


def fixture_library():
    """Independently spelled nonfunctional short test products and RNA parts."""
    values = (
        ("short_five", "five_prime_utr", "GG"),
        ("long_five", "five_prime_utr", "CCCC"),
        ("short_three", "three_prime_utr", "CC"),
        ("long_three", "three_prime_utr", "GGG"),
        ("tail", "poly_a", "AAAA"),
        ("a_cds", "cds", "AUGGCUUAA"),
        ("a_synonymous", "cds", "AUGGCCUAA"),
        ("b_cds", "cds", "AUGGGUUAA"),
    )
    parts = tuple(
        MolecularPart(
            identity,
            SequenceFragment(
                "fragment." + identity,
                sequence,
                hashlib.sha256(sequence.encode()).hexdigest(),
                "invented:" + identity,
            ),
            kind,
        )
        for identity, kind, sequence in values
    )
    products = (
        ProductBinding("product_a", "a_cds", "MA*"),
        ProductBinding("product_a", "a_synonymous", "MA*"),
        ProductBinding("product_b", "b_cds", "MG*"),
    )
    features = tuple(
        PayloadFeature(key, "known", "invented:" + key, value)
        for key, value in (
            ("cap", "none"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "triphosphate"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    architectures = (
        RNAArchitecture("a_long", "1", "long_five", "long_three", "tail", features),
        RNAArchitecture("z_short", "1", "short_five", "short_three", "tail", features),
    )
    return MolecularLibrary("artificial_library", "1", parts, products, architectures)


def fixture_request(
    product="product_a", *, constraints=None, library=None, target=None, cue="cue"
):
    therapy = bc.Therapy("source_product_candidate")
    cell = therapy.engineer("recipient", cell_type="abstract_cell")
    cell.when(cell.external.signal(cue).present()).do(cell.secrete(product))
    source = bc.BuildRequest.freeze(
        therapy.freeze(),
        target=target
        or bc.TargetContext("candidate_fixture", "1", bc.PayloadFormat.RNA),
        artifact_scope="complete_payload",
    )
    return CandidateRequest(
        source, library or fixture_library(), constraints or CandidateConstraints()
    )


def build_candidate(request):
    requirements = lower_candidate_requirements(request)
    selection = select_candidate(request, requirements)
    layout = derive_candidate_layout(request, requirements, selection)
    return requirements, selection, layout, emit_candidate(request, layout)


class CandidateSynthesisTests(unittest.TestCase):
    def test_source_product_selects_coding_part_and_changes_emitted_sequence(self):
        first = fixture_request("product_a")
        second = fixture_request("product_b")
        req_a, selection_a, layout_a, molecule_a = build_candidate(first)
        req_b, selection_b, layout_b, molecule_b = build_candidate(second)
        self.assertEqual(selection_a.selected.cds_part_id, "a_cds")
        self.assertEqual(selection_b.selected.cds_part_id, "b_cds")
        self.assertEqual(molecule_a.sequence, "GGAUGGCUUAACCAAAA")
        self.assertEqual(molecule_b.sequence, "GGAUGGGUUAACCAAAA")
        self.assertEqual(molecule_a.regions[1].protein_sequence, "MA*")
        self.assertEqual(molecule_b.regions[1].protein_sequence, "MG*")
        self.assertEqual(len(selection_a.alternatives), 4)
        self.assertEqual(len(selection_b.alternatives), 2)
        self.assertEqual(layout_a.request_fingerprint, first.fingerprint)
        self.assertEqual(layout_b.request_fingerprint, second.fingerprint)
        self.assertNotEqual(req_a.fingerprint, req_b.fingerprint)

    def test_recipe_coordinates_and_chemistry_are_derived_without_caller_placements(
        self,
    ):
        request = fixture_request()
        _, selection, layout, molecule = build_candidate(request)
        self.assertEqual(selection.selected.architecture_id, "z_short")
        self.assertEqual(layout.molecule_id, "source_product_candidate.candidate")
        self.assertEqual(
            tuple(item.region_id for item in layout.placements),
            ("five_prime_utr", "cds", "three_prime_utr", "poly_a"),
        )
        self.assertEqual(
            tuple(item.molecule_range for item in layout.placements),
            (
                SequenceRange(0, 2),
                SequenceRange(2, 11),
                SequenceRange(11, 13),
                SequenceRange(13, 17),
            ),
        )
        for fragment, placement, region in zip(
            layout.fragments, layout.placements, molecule.regions
        ):
            self.assertEqual(placement.fragment_fingerprint, fragment.fingerprint)
            self.assertEqual(
                placement.source_range, SequenceRange(0, len(fragment.sequence))
            )
            self.assertEqual(region.source_locator, fragment.source_locator)
        self.assertEqual(molecule.features, request.library.architectures[1].features)
        self.assertEqual(
            molecule.source_locator, "candidate-request:" + request.fingerprint
        )
        no_tail = replace(
            request.library.architectures[1],
            poly_a_part_id=None,
            features=tuple(
                replace(item, value="absent") if item.feature == "poly_a_tail" else item
                for item in request.library.architectures[1].features
            ),
        )
        changed = replace(
            request, library=replace(request.library, architectures=(no_tail,))
        )
        self.assertEqual(build_candidate(changed)[3].sequence, "GGAUGGCUUAACC")

    def test_hard_constraints_precede_preferences_with_every_rejection_retained(self):
        request = fixture_request(
            constraints=CandidateConstraints(
                allowed_architecture_ids=("a_long",),
                allowed_cds_part_ids=("a_synonymous",),
            )
        )
        _, selection, _, molecule = build_candidate(request)
        self.assertEqual(
            (selection.selected.architecture_id, selection.selected.cds_part_id),
            ("a_long", "a_synonymous"),
        )
        self.assertEqual(molecule.sequence, "CCCCAUGGCCUAAGGGAAAA")
        self.assertEqual(len(selection.alternatives), 4)
        reasons = {
            item.cds_part_id + ":" + item.architecture_id: item.rejection_reasons
            for item in selection.alternatives
        }
        self.assertEqual(
            reasons["a_cds:z_short"],
            ("architecture_not_allowed", "cds_part_not_allowed"),
        )
        exhausted = replace(request, constraints=CandidateConstraints(max_length=0))
        result = select_candidate(exhausted, lower_candidate_requirements(exhausted))
        self.assertIsNone(result.selected)
        self.assertEqual(result.diagnostics, ("bounded_candidates_exhausted",))
        self.assertTrue(
            all(
                "max_length_exceeded" in item.rejection_reasons
                for item in result.alternatives
            )
        )
        with self.assertRaises(SerializationError):
            derive_candidate_layout(
                exhausted, lower_candidate_requirements(exhausted), result
            )

    def test_preference_and_input_order_do_not_hide_alternatives(self):
        shortest = fixture_request()
        lexical = replace(
            shortest, constraints=CandidateConstraints(preference="lexical")
        )
        self.assertEqual(
            build_candidate(shortest)[1].selected.architecture_id, "z_short"
        )
        self.assertEqual(build_candidate(lexical)[1].selected.architecture_id, "a_long")
        reordered = replace(
            shortest,
            library=replace(
                shortest.library,
                products=tuple(reversed(shortest.library.products)),
                architectures=tuple(reversed(shortest.library.architectures)),
            ),
        )
        chosen = select_candidate(reordered, lower_candidate_requirements(reordered))
        self.assertEqual(chosen.selected.architecture_id, "z_short")
        self.assertEqual(
            [(item.architecture_id, item.cds_part_id) for item in chosen.alternatives],
            [
                ("a_long", "a_cds"),
                ("a_long", "a_synonymous"),
                ("z_short", "a_cds"),
                ("z_short", "a_synonymous"),
            ],
        )

    def test_unknown_invalid_or_unsupported_structure_never_ranks_as_eligible(self):
        request = fixture_request()
        long, short = request.library.architectures
        unknown = replace(
            short,
            features=tuple(
                replace(item, status="unknown", value=None)
                if item.feature == "cap"
                else item
                for item in short.features
            ),
        )
        changed = replace(
            request, library=replace(request.library, architectures=(long, unknown))
        )
        _, result, _, _ = build_candidate(changed)
        self.assertEqual(result.selected.architecture_id, "a_long")
        self.assertTrue(
            all(
                item.status == "unknown"
                for item in result.alternatives
                if item.architecture_id == "z_short"
            )
        )
        bad_binding = replace(request.library.products[0], protein_sequence="MG*")
        changed = replace(
            request,
            library=replace(
                request.library, products=(bad_binding, *request.library.products[1:])
            ),
        )
        result = build_candidate(changed)[1]
        self.assertEqual(result.selected.cds_part_id, "a_synonymous")
        self.assertTrue(
            all(
                "protein_correspondence" in item.rejection_reasons
                for item in result.alternatives
                if item.cds_part_id == "a_cds"
            )
        )
        bad_part = replace(
            request.library.parts[5],
            fragment=replace(
                request.library.parts[5].fragment, sequence_sha256="0" * 64
            ),
        )
        changed = replace(
            request,
            library=replace(
                request.library,
                parts=(
                    *request.library.parts[:5],
                    bad_part,
                    *request.library.parts[6:],
                ),
            ),
        )
        result = build_candidate(changed)[1]
        self.assertEqual(result.selected.cds_part_id, "a_synonymous")
        self.assertTrue(
            all(
                "fragment_hash" in item.rejection_reasons
                for item in result.alternatives
                if item.cds_part_id == "a_cds"
            )
        )

    def test_missing_product_and_wrong_modality_are_specific_bounded_rejections(self):
        missing = fixture_request("unlisted_product")
        result = select_candidate(missing, lower_candidate_requirements(missing))
        self.assertEqual(result.alternatives, ())
        self.assertEqual(result.diagnostics, ("product_binding_unavailable",))
        dna = fixture_request(
            target=bc.TargetContext("DNA_fixture", "1", bc.PayloadFormat.DNA)
        )
        result = select_candidate(dna, lower_candidate_requirements(dna))
        self.assertIsNone(result.selected)
        self.assertTrue(
            all(
                item.status == "unsupported"
                and item.rejection_reasons == ("unsupported_modality",)
                for item in result.alternatives
            )
        )

    def test_guard_changes_remain_required_instead_of_becoming_sequence_controls(self):
        first = fixture_request(cue="first_cue")
        second = fixture_request(cue="second_cue")
        first_req, _, first_layout, first_molecule = build_candidate(first)
        second_req, _, second_layout, second_molecule = build_candidate(second)
        self.assertEqual(first_molecule.sequence, second_molecule.sequence)
        self.assertNotEqual(
            first_layout.request_fingerprint, second_layout.request_fingerprint
        )
        for request, requirements in ((first, first_req), (second, second_req)):
            self.assertEqual(
                requirements.source_node_ids,
                tuple(node.id for node in request.build_request.intent.nodes),
            )
            self.assertIn(
                "conditional_control", {item.id for item in requirements.unresolved}
            )
            self.assertIn(
                "secretion_mechanism", {item.id for item in requirements.unresolved}
            )

    def test_human_target_is_retained_without_software_relabelling_or_admission(self):
        from examples.human_behavior import make_human_behavior

        source = make_human_behavior()
        library = fixture_library()
        library = replace(
            library,
            products=(replace(library.products[0], product=source.contract.product),),
        )
        request = CandidateRequest(source, library)
        requirements, _, layout, molecule = build_candidate(request)
        self.assertEqual(layout.target, source.target)
        self.assertEqual(layout.target.fingerprint, source.target.fingerprint)
        self.assertEqual(molecule.sequence, "GGAUGGCUUAACCAAAA")
        self.assertIn(
            "human_therapeutic_admission", {item.id for item in requirements.unresolved}
        )

    def test_strict_selection_layout_roundtrips_and_forged_choices(self):
        request = fixture_request()
        requirements, selection, layout, _ = build_candidate(request)
        for artifact in (*selection.alternatives, selection, layout):
            self.assertEqual(type(artifact).from_json(artifact.to_json()), artifact)
            with self.assertRaises(SerializationError):
                type(artifact).from_dict(artifact.to_dict() | {"extra": True})
        changed = selection.to_dict()
        changed["outcome"] = "complete_therapeutic_program"
        with self.assertRaises(SerializationError):
            CandidateSelection.from_dict(changed)
        changed = layout.to_dict()
        changed["nodes"][0]["kind"] = "invented_sensor"
        with self.assertRaises(SerializationError):
            CandidateLayout.from_dict(changed)
        forged = replace(
            selection, selected_alternative_id=selection.alternatives[0].id
        )
        with self.assertRaisesRegex(SerializationError, "current bounded"):
            derive_candidate_layout(request, requirements, forged)
        with self.assertRaisesRegex(SerializationError, "complete source authority"):
            select_candidate(request, replace(requirements, product="product_b"))

    def test_emission_rejects_changed_authority_and_incomplete_chemistry(self):
        request = fixture_request()
        _, _, layout, _ = build_candidate(request)
        with self.assertRaisesRegex(SerializationError, "source authority"):
            emit_candidate(fixture_request("product_b"), layout)
        changed = replace(
            layout,
            features=tuple(
                replace(item, status="unknown", value=None)
                if item.feature == "cap"
                else item
                for item in layout.features
            ),
        )
        with self.assertRaisesRegex(
            SerializationError, "supported molecular structure"
        ):
            emit_candidate(request, changed)


if __name__ == "__main__":
    unittest.main()
