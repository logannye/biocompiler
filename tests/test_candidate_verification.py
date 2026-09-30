"""Independent source, bounded-selection and emitted research-candidate checks."""

from dataclasses import replace
import hashlib
import inspect
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.candidate import (
    OBLIGATION_SPECS,
    CandidateConstraints,
    CandidateObligation,
    CandidateRequirements,
)
from biocompiler.ir.candidate_selection import (
    CandidateAlternative,
    CandidateLayout,
    CandidateSelection,
)
from biocompiler.ir.molecular_design import FragmentPlacement
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.admission import admission_for_target
from biocompiler.verification.candidate import (
    CandidateVerificationResult,
    check_candidate,
    check_candidate_layout,
    check_candidate_requirements,
    check_candidate_selection,
)
from biocompiler.verification.evidence import CheckOutcome
from examples.intent_candidate import make_candidate_request


def sha(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def fixture():
    """Author expected selections, layout and spelling without invoking producers."""
    request = make_candidate_request()
    ids = tuple(f"n{i:06}" for i in range(1, 9))
    references = (
        ("secretion_mechanism", ("n000006", "n000007")),
        ("conditional_control", ("n000008", "n000005", "n000007")),
        ("quantitative_response", ("n000007",)),
        ("biological_function", ("n000006", "n000007")),
        ("target_applicability", ("n000001",)),
    )

    def declared(key, refs):
        category, description = OBLIGATION_SPECS[key]
        return CandidateObligation(key, refs, category, description)

    obligations = [declared(key, refs) for key, refs in references]
    for identity, kind in (
        ("n000002", "goal"),
        ("n000003", "scope"),
        ("n000004", "signal"),
        ("n000005", "qualitative"),
        ("n000008", "rule"),
    ):
        obligations.append(
            CandidateObligation(
                "source:" + identity,
                (identity,),
                "evidence" if kind == "goal" else "implementation",
                "This source goal remains unestablished by coding candidate selection."
                if kind == "goal"
                else f"Source operation {kind!r} remains unimplemented by coding-only candidate selection.",
            )
        )
    references = (
        ("human_therapeutic_admission", ("n000001",)),
        ("human_input_observation", ("n000004",)),
        ("human_predicate_refinement", ("n000005",)),
        ("human_response_contract", ("n000008", "n000007")),
        ("human_goal_refinement", ("n000002",)),
        ("human_behavior_evidence", ids),
        ("human_deployment_contract", ("n000001",)),
        ("human_deployment_evidence", ("n000001",)),
        ("human_prohibited_behavior", ("n000008", "n000007")),
        ("human_input_loss_response", ("n000008", "n000007")),
        ("human_external_shutdown", ("n000008", "n000007")),
        ("human_acceptance_evidence", ("n000001", "n000008", "n000007")),
    )
    obligations.extend(declared(key, refs) for key, refs in references)
    requirements = CandidateRequirements(
        request.fingerprint,
        "n000001",
        "n000006",
        "n000007",
        "declared_product",
        ids,
        tuple(obligations),
    )
    alternatives = (
        CandidateAlternative("compact", "coding_a", 17),
        CandidateAlternative("extended", "coding_a", 19),
    )
    selection = CandidateSelection(
        request.fingerprint, requirements.fingerprint, alternatives, alternatives[0].id
    )
    parts = {item.id: item for item in request.library.parts}
    fragments = tuple(
        parts[key].fragment for key in ("front_short", "coding_a", "back", "tail")
    )
    definitions = (
        ("five_prime_utr", 0, 2, None),
        ("cds", 2, 11, "MA*"),
        ("three_prime_utr", 11, 13, None),
        ("poly_a", 13, 17, None),
    )
    placements = tuple(
        FragmentPlacement(
            kind,
            kind,
            fragment.id,
            fragment.fingerprint,
            SequenceRange(0, end - start),
            SequenceRange(start, end),
            protein,
        )
        for fragment, (kind, start, end, protein) in zip(fragments, definitions)
    )
    molecule_id = request.build_request.intent.name + ".candidate"
    features = request.library.architectures[0].features
    layout = CandidateLayout(
        request.fingerprint,
        requirements.fingerprint,
        selection.fingerprint,
        alternatives[0].id,
        "compact",
        "coding_a",
        molecule_id,
        request.target,
        fragments,
        placements,
        features,
    )
    regions = tuple(
        PayloadRegion(
            kind,
            kind,
            SequenceRange(start, end),
            SequenceRange(0, end - start),
            fragment.source_locator,
            protein,
        )
        for fragment, (kind, start, end, protein) in zip(fragments, definitions)
    )
    sequence = "GGAUGGCUUAACCAAAA"
    molecule = PayloadMolecule(
        molecule_id,
        "mature_linear_rna",
        "RNA",
        sequence,
        sha(sequence),
        SequenceRange(0, 17),
        "linear",
        "single",
        regions,
        features,
        "candidate-request:" + request.fingerprint,
    )
    return request, requirements, selection, layout, molecule


def check(values, *, pin=None):
    return check_candidate(
        *values,
        expected_request_fingerprint=values[0].fingerprint if pin is None else pin,
    )


def produced(request):
    """Exercise independent checking of proposals for additional policy cases."""
    from biocompiler.compiler.candidate_requirements import lower_candidate_requirements
    from biocompiler.synthesis.candidate import (
        select_candidate,
        derive_candidate_layout,
    )
    from biocompiler.backends.candidate import emit_candidate

    requirements = lower_candidate_requirements(request)
    selection = select_candidate(request, requirements)
    if selection.selected is None:
        return request, requirements, selection, None, None
    layout = derive_candidate_layout(request, requirements, selection)
    return request, requirements, selection, layout, emit_candidate(request, layout)


class CandidateVerificationTests(unittest.TestCase):
    def assert_code(self, result, code, outcome=CheckOutcome.FAIL):
        self.assertEqual(result.outcome, outcome, result.diagnostics)
        self.assertIn(code, {item.code for item in result.diagnostics})

    def test_literal_candidate_passes_all_stages_and_keeps_original_human_request(self):
        request, requirements, selection, layout, molecule = fixture()
        results = (
            check_candidate_requirements(
                request, requirements, expected_request_fingerprint=request.fingerprint
            ),
            check_candidate_selection(
                request,
                requirements,
                selection,
                expected_request_fingerprint=request.fingerprint,
            ),
            check_candidate_layout(
                request,
                requirements,
                selection,
                layout,
                expected_request_fingerprint=request.fingerprint,
            ),
            check((request, requirements, selection, layout, molecule)),
        )
        for stage, result in zip(
            ("requirements", "selection", "layout", "molecule"), results
        ):
            self.assertTrue(result.passed, result.diagnostics)
            self.assertEqual(result.stage, stage)
            self.assertEqual(result.unresolved, requirements.unresolved)
            self.assertEqual(
                result.source_node_ids,
                tuple(node.id for node in request.build_request.intent.nodes),
            )
            self.assertFalse(result.complete_therapeutic_implementation)
            self.assertEqual(result.human_therapeutic_admission, "not_admitted")
            self.assertEqual(
                CandidateVerificationResult.from_json(result.to_json()), result
            )
        self.assertEqual(layout.target, request.source.target)
        self.assertEqual(
            admission_for_target(layout.target, boundary="export").decision,
            "not_admitted",
        )

    def test_checking_cannot_call_requirement_selection_or_sequence_producers(self):
        import biocompiler.verification.candidate as module

        source = inspect.getsource(module)
        for forbidden in (
            "biocompiler.synthesis",
            "biocompiler.backends",
            "compiler.candidate_requirements",
        ):
            self.assertNotIn(forbidden, source)
        values = fixture()
        with (
            patch(
                "biocompiler.compiler.candidate_requirements.lower_candidate_requirements",
                side_effect=AssertionError("lowerer"),
            ),
            patch(
                "biocompiler.synthesis.candidate.select_candidate",
                side_effect=AssertionError("selector"),
            ),
            patch(
                "biocompiler.synthesis.candidate.derive_candidate_layout",
                side_effect=AssertionError("layout"),
            ),
            patch(
                "biocompiler.backends.candidate.emit_candidate",
                side_effect=AssertionError("emitter"),
            ),
            patch("socket.create_connection", side_effect=AssertionError("network")),
        ):
            self.assertTrue(check(values).passed)

    def test_no_unresolved_requirement_can_be_removed_or_reclassified(self):
        request, requirements, *_ = fixture()
        for index, obligation in enumerate(requirements.unresolved):
            with self.subTest(obligation=obligation.id):
                forged = replace(
                    requirements,
                    unresolved=requirements.unresolved[:index]
                    + requirements.unresolved[index + 1 :],
                )
                self.assert_code(
                    check_candidate_requirements(
                        request,
                        forged,
                        expected_request_fingerprint=request.fingerprint,
                    ),
                    "requirements_correspondence",
                )
        item = requirements.unresolved[0]
        for change in (
            {"category": "evidence"},
            {"source_ids": (requirements.role_id,)},
            {"description": "already implemented"},
        ):
            forged = replace(
                requirements,
                unresolved=(replace(item, **change),) + requirements.unresolved[1:],
            )
            self.assert_code(
                check_candidate_requirements(
                    request, forged, expected_request_fingerprint=request.fingerprint
                ),
                "requirements_correspondence",
            )

    def test_wrong_product_omitted_source_or_stripped_contract_cannot_be_rehashed_into_authority(
        self,
    ):
        request, requirements, *_ = fixture()
        for changes in (
            {"product": "alternative_product"},
            {"request_fingerprint": "a" * 64},
            {"source_node_ids": tuple(reversed(requirements.source_node_ids))},
        ):
            forged = replace(requirements, **changes)
            self.assert_code(
                check_candidate_requirements(
                    request, forged, expected_request_fingerprint=request.fingerprint
                ),
                "requirements_correspondence",
            )
        removed = "n000002"
        forged = replace(
            requirements,
            source_node_ids=tuple(
                x for x in requirements.source_node_ids if x != removed
            ),
            unresolved=tuple(
                x for x in requirements.unresolved if removed not in x.source_ids
            ),
        )
        self.assert_code(
            check_candidate_requirements(
                request, forged, expected_request_fingerprint=request.fingerprint
            ),
            "requirements_correspondence",
        )
        stripped = replace(request, source=request.build_request)
        proposal = produced(stripped)
        self.assert_code(check(proposal, pin=request.fingerprint), "request_authority")

    def test_full_alternative_inventory_and_ranking_are_independently_recomputed(self):
        request, requirements, selection, *_ = fixture()
        for forged, code in (
            (
                replace(selection, alternatives=selection.alternatives[:1]),
                "alternative_inventory",
            ),
            (
                replace(
                    selection,
                    alternatives=(
                        replace(selection.alternatives[0], sequence_length=1),
                    )
                    + selection.alternatives[1:],
                ),
                "alternative_inventory",
            ),
            (
                replace(
                    selection, selected_alternative_id=selection.alternatives[1].id
                ),
                "selection_ranking",
            ),
            (replace(selection, selected_alternative_id=None), "selection_ranking"),
            (replace(selection, diagnostics=("made_up",)), "selection_diagnostics"),
            (
                replace(selection, requirements_fingerprint="a" * 64),
                "selection_authority",
            ),
        ):
            self.assert_code(
                check_candidate_selection(
                    request,
                    requirements,
                    forged,
                    expected_request_fingerprint=request.fingerprint,
                ),
                code,
            )

    def test_authored_hard_constraints_change_choice_and_exhaustion_remains_bounded(
        self,
    ):
        request, *_ = fixture()
        forced = produced(
            replace(
                request,
                constraints=CandidateConstraints(
                    allowed_architecture_ids=("extended",)
                ),
            )
        )
        self.assertEqual(forced[2].selected.architecture_id, "extended")
        self.assertEqual(forced[4].sequence, "GGGGAUGGCUUAACCAAAA")
        self.assertTrue(check(forced).passed)
        rejected = forced[2].alternatives[0]
        forged = replace(
            forced[2],
            alternatives=(replace(rejected, rejections=()),)
            + forced[2].alternatives[1:],
            selected_alternative_id=rejected.id,
        )
        self.assert_code(
            check_candidate_selection(
                forced[0],
                forced[1],
                forged,
                expected_request_fingerprint=forced[0].fingerprint,
            ),
            "alternative_inventory",
        )
        for maximum in (0, 16):
            exhausted = produced(
                replace(request, constraints=CandidateConstraints(max_length=maximum))
            )
            self.assertIsNone(exhausted[2].selected)
            self.assertEqual(
                exhausted[2].diagnostics, ("bounded_candidates_exhausted",)
            )
            self.assertTrue(
                check_candidate_selection(
                    *exhausted[:3],
                    expected_request_fingerprint=exhausted[0].fingerprint,
                ).passed
            )
        changed = produced(make_candidate_request(product="alternative_product"))
        self.assertEqual(changed[2].selected.cds_part_id, "coding_b")
        self.assertEqual(changed[4].sequence, "GGAUGUUUUAACCAAAA")
        self.assertTrue(check(changed).passed)

    def test_unknown_chemistry_and_wrong_protein_cannot_be_ranked_as_eligible(self):
        request, *_ = fixture()
        architectures = tuple(
            replace(
                a,
                features=tuple(
                    replace(f, status="unknown", value=None)
                    if f.feature == "cap"
                    else f
                    for f in a.features
                ),
            )
            for a in request.library.architectures
        )
        unknown = produced(
            replace(
                request, library=replace(request.library, architectures=architectures)
            )
        )
        self.assertTrue(all(x.status == "unknown" for x in unknown[2].alternatives))
        self.assertTrue(
            check_candidate_selection(
                *unknown[:3], expected_request_fingerprint=unknown[0].fingerprint
            ).passed
        )
        products = (
            replace(request.library.products[0], protein_sequence="MV*"),
        ) + request.library.products[1:]
        invalid = produced(
            replace(request, library=replace(request.library, products=products))
        )
        self.assertIsNone(invalid[2].selected)
        self.assertTrue(
            all(
                "protein_correspondence" in x.rejection_reasons
                for x in invalid[2].alternatives
            )
        )
        self.assertTrue(
            check_candidate_selection(
                *invalid[:3], expected_request_fingerprint=invalid[0].fingerprint
            ).passed
        )

    def test_target_part_layout_and_chemistry_substitution_are_detected_after_rehashing(
        self,
    ):
        request, requirements, selection, layout, molecule = fixture()
        mutations = (
            (
                {"target": TargetContext("generic", "1", PayloadFormat.RNA)},
                "original_target",
            ),
            ({"cds_part_id": "coding_b"}, "layout_selection"),
            ({"architecture_id": "extended"}, "layout_selection"),
            ({"molecule_id": "different"}, "layout_molecule_id"),
            ({"selection_fingerprint": "a" * 64}, "layout_authority"),
            (
                {
                    "placements": (
                        replace(layout.placements[0], source_range=SequenceRange(0, 1)),
                    )
                    + layout.placements[1:]
                },
                "layout_placements",
            ),
            ({"features": layout.features[:-1]}, "layout_features"),
            ({"unknown_features": ("cap",)}, "layout_unknown_features"),
        )
        for changes, code in mutations:
            forged = replace(layout, **changes)
            self.assert_code(
                check((request, requirements, selection, forged, molecule)), code
            )
        fragment = replace(
            layout.fragments[0],
            sequence="CC",
            sequence_sha256=sha("CC"),
            source_locator="relabeled",
        )
        placements = (
            replace(layout.placements[0], fragment_fingerprint=fragment.fingerprint),
        ) + layout.placements[1:]
        forged = replace(
            layout, fragments=(fragment,) + layout.fragments[1:], placements=placements
        )
        altered = replace(
            molecule,
            sequence="CCAUGGCUUAACCAAAA",
            sequence_sha256=sha("CCAUGGCUUAACCAAAA"),
        )
        self.assert_code(
            check((request, requirements, selection, forged, altered)),
            "layout_fragments",
        )

    def test_rehashed_emitted_symbols_source_maps_features_and_identity_fail(self):
        request, requirements, selection, layout, molecule = fixture()
        for sequence in ("GAAUGGCUUAACCAAAA", "GGAUGGCCUAACCAAAA", "GGAUGGCUUAACCAAAC"):
            altered = replace(
                molecule, sequence=sequence, sequence_sha256=sha(sequence)
            )
            self.assert_code(
                check((request, requirements, selection, layout, altered)),
                "molecule_nucleotides",
            )
        for changes, code in (
            ({"sequence_sha256": "a" * 64}, "molecule_hash"),
            ({"source_locator": "candidate-request:" + "a" * 64}, "molecule_source"),
            ({"boundaries": SequenceRange(1, 17)}, "molecule_boundaries"),
            ({"id": "wrong"}, "molecule_profile"),
            ({"topology": "circular"}, "molecule_profile"),
            ({"features": molecule.features[:-1]}, "molecule_features"),
            (
                {
                    "regions": (
                        replace(molecule.regions[0], source_locator="other-source"),
                    )
                    + molecule.regions[1:]
                },
                "molecule_regions",
            ),
        ):
            self.assert_code(
                check(
                    (
                        request,
                        requirements,
                        selection,
                        layout,
                        replace(molecule, **changes),
                    )
                ),
                code,
            )

    def test_result_currentness_strict_import_and_fixed_partial_claims(self):
        values = fixture()
        result = check(values)
        self.assertTrue(
            result.is_fresh(*values, expected_request_fingerprint=values[0].fingerprint)
        )
        altered = replace(values[-1], source_locator="changed")
        self.assertEqual(
            result.freshness(
                *values[:-1],
                altered,
                expected_request_fingerprint=values[0].fingerprint,
            ).changed_dependencies,
            ("candidate",),
        )
        for changes in (
            {"schema_version": "old"},
            {"outcome": []},
            {"stage": []},
            {"checks": []},
            {"scope": "therapeutic"},
            {"complete_therapeutic_implementation": True},
            {"human_therapeutic_admission": "admitted"},
            {"claim_scope": "effective"},
            {"unresolved": []},
            {"source_node_ids": []},
            {"extra": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                CandidateVerificationResult.from_dict(result.to_dict() | changes)
        for key in ("checker", "structural_checker"):
            data = result.to_dict()
            data["dependencies"][key] = "old"
            with self.assertRaises(SerializationError):
                CandidateVerificationResult.from_dict(data)
        for key in ("requirements", "selection", "layout", "admission"):
            data = result.to_dict()
            data["dependencies"]["profiles"][key] = "old"
            with self.assertRaises(SerializationError):
                CandidateVerificationResult.from_dict(data)
        with patch(
            "biocompiler.semantics.admission.ADMISSION_POLICY_VERSION", "changed"
        ):
            self.assertEqual(
                result.freshness(
                    *values, expected_request_fingerprint=values[0].fingerprint
                ).changed_dependencies,
                ("profiles",),
            )


if __name__ == "__main__":
    unittest.main()
