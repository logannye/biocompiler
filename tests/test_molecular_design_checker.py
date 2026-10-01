"""Independent software-fragment controls; these are not biological sequences."""

from dataclasses import replace
import hashlib
import inspect
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.molecular_design import (
    FragmentPlacement,
    MolecularDesignArtifact,
    MolecularDesignConstruct,
    MolecularDesignRequest,
    SequenceFragment,
)
from biocompiler.ir.payload import PayloadFeature, PayloadMolecule, PayloadRegion
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.molecular_design import (
    MolecularDesignResult,
    check_molecular_design,
    check_molecular_design_construct,
    check_molecular_design_request,
)
from biocompiler.verification.payload import check_payload
from examples.human_target import make_human_target
from test_payload_profiles import reference_for


def sha(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def fixture():
    """Independent literal expectation: no assembler or emitter supplies an oracle."""
    fragments = tuple(
        SequenceFragment(
            identity, sequence, sha(sequence), "invented-source:" + identity
        )
        for identity, sequence in (
            ("utr5", "AGGC"),
            ("coding", "CCAUGGCUUAAG"),
            ("utr3", "GCCU"),
            ("tail", "AAAA"),
        )
    )
    specifications = (
        ("five", "five_prime_utr", 1, 3, 0, 2, None),
        ("coding", "cds", 2, 11, 2, 11, "MA*"),
        ("three", "three_prime_utr", 1, 3, 11, 13, None),
        ("tail", "poly_a", 0, 4, 13, 17, None),
    )
    placements = tuple(
        FragmentPlacement(
            identity,
            kind,
            source.id,
            source.fingerprint,
            SequenceRange(start, end),
            SequenceRange(left, right),
            protein,
        )
        for source, (identity, kind, start, end, left, right, protein) in zip(
            fragments, specifications
        )
    )
    features = tuple(
        PayloadFeature(key, "known", "invented-chemistry:" + key, value)
        for key, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    request = MolecularDesignRequest(
        "invented-design", "invented-rna", fragments, placements, features
    )
    construct = MolecularDesignConstruct(
        request.fingerprint, "invented-rna", placements, features
    )
    # This exact sequence is a separately authored oracle rather than joined source output.
    sequence = "GGAUGGCUUAACCAAAA"
    regions = tuple(
        PayloadRegion(
            identity,
            kind,
            SequenceRange(left, right),
            SequenceRange(start, end),
            source.source_locator,
            protein,
        )
        for source, (identity, kind, start, end, left, right, protein) in zip(
            fragments, specifications
        )
    )
    molecule = PayloadMolecule(
        "invented-rna",
        "mature_linear_rna",
        "RNA",
        sequence,
        sha(sequence),
        SequenceRange(0, 17),
        "linear",
        "single",
        regions,
        features,
        "molecular-design-request:invented-design",
    )
    candidate = MolecularDesignArtifact(
        request.fingerprint, construct.fingerprint, molecule, placements
    )
    return request, construct, candidate


def check(request, construct, candidate, *, pin=None):
    return check_molecular_design(
        request,
        construct,
        candidate,
        expected_request_fingerprint=request.fingerprint if pin is None else pin,
    )


def molecule_change(candidate, **changes):
    if "sequence" in changes and "sequence_sha256" not in changes:
        changes["sequence_sha256"] = sha(changes["sequence"])
    return replace(candidate, molecule=replace(candidate.molecule, **changes))


class MolecularDesignCheckerTests(unittest.TestCase):
    def assert_code(self, result, code, outcome=CheckOutcome.FAIL):
        self.assertEqual(result.outcome, outcome, result.diagnostics)
        self.assertIn(code, {item.code for item in result.diagnostics})

    def test_independently_authored_complete_design_checks_all_stages_offline(self):
        request, construct, candidate = fixture()
        with patch("socket.create_connection", side_effect=AssertionError("offline")):
            results = (
                check_molecular_design_request(
                    request, expected_request_fingerprint=request.fingerprint
                ),
                check_molecular_design_construct(
                    request, construct, expected_request_fingerprint=request.fingerprint
                ),
                check(request, construct, candidate),
            )
        for stage, result in zip(("request", "construct", "molecule"), results):
            self.assertTrue(result.passed, result.diagnostics)
            self.assertEqual(result.stage, stage)
            self.assertEqual(result.evidence_boundary, "software_fixture")
            self.assertEqual(result.human_therapeutic_admission, "not_admitted")
            self.assertEqual(result.reference_promotion, "not_promoted")
            self.assertIn("source_behavior_realization", result.unresolved_obligations)
            self.assertEqual(MolecularDesignResult.from_json(result.to_json()), result)
        self.assertTrue(
            results[-1].is_fresh(
                request,
                construct,
                candidate,
                expected_request_fingerprint=request.fingerprint,
            )
        )

    def test_checker_does_not_import_or_call_producers(self):
        import biocompiler.verification.molecular_design as checker

        source = inspect.getsource(checker)
        self.assertNotIn("biocompiler.synthesis", source)
        self.assertNotIn("biocompiler.backends", source)
        request, construct, candidate = fixture()
        with (
            patch(
                "biocompiler.synthesis.molecular_design.generate_molecular_design_construct",
                side_effect=AssertionError("assembler"),
            ),
            patch(
                "biocompiler.backends.molecular_design.emit_molecular_design",
                side_effect=AssertionError("emitter"),
            ),
        ):
            self.assertTrue(check(request, construct, candidate).passed)

    def test_rehashed_nucleotide_changes_fail_even_when_protein_is_unchanged(self):
        request, construct, candidate = fixture()
        for sequence in (
            "GAAUGGCUUAACCAAAA",  # noncoding change
            "GGAUGGCCUAACCAAAA",  # synonymous alanine codon
            "GGAUGGCUUAACUAAAA",  # three-prime UTR change
            "GGAUGGCUUAACCAAAC",  # tail change
        ):
            with self.subTest(sequence=sequence):
                altered = molecule_change(candidate, sequence=sequence)
                self.assert_code(
                    check(request, construct, altered), "fragment_nucleotides"
                )

    def test_cds_start_stop_frame_and_protein_are_checked_independently(self):
        request, construct, candidate = fixture()
        for sequence in (
            "GGGUGGCUUAACCAAAA",  # no AUG
            "GGAUGGCUUGGCCAAAA",  # no terminal stop
            "GGAUGUAAGAACCAAAA",  # internal stop
        ):
            self.assert_code(
                check(
                    request, construct, molecule_change(candidate, sequence=sequence)
                ),
                "emitted_coding_translation",
            )
        placements = list(request.placements)
        placements[1] = replace(placements[1], protein_sequence="MV*")
        bad = replace(request, placements=tuple(placements))
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "protein_correspondence",
        )
        for change in ({"orientation": "reverse"}, {"reading_frame": 1}):
            placements[1] = replace(request.placements[1], **change)
            bad = replace(request, placements=tuple(placements))
            self.assert_code(
                check_molecular_design_request(
                    bad, expected_request_fingerprint=bad.fingerprint
                ),
                "unsupported_traversal",
                CheckOutcome.UNSUPPORTED,
            )

    def test_source_sequence_pin_and_source_fragment_lock_are_both_checked(self):
        request, _, _ = fixture()
        source = replace(request.fragments[0], sequence="ACCC")
        placements = (
            replace(request.placements[0], fragment_fingerprint=source.fingerprint),
        ) + request.placements[1:]
        bad = replace(
            request, fragments=(source,) + request.fragments[1:], placements=placements
        )
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "fragment_hash",
        )
        source = replace(source, sequence_sha256=sha(source.sequence))
        bad = replace(request, fragments=(source,) + request.fragments[1:])
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "fragment_lock",
        )
        forged = replace(
            bad,
            placements=(
                replace(bad.placements[0], fragment_fingerprint=source.fingerprint),
            )
            + bad.placements[1:],
        )
        self.assert_code(
            check_molecular_design_request(
                forged, expected_request_fingerprint=request.fingerprint
            ),
            "request_authority",
        )

    def test_exact_fragment_inventory_source_ranges_and_destination_partition(self):
        request, _, _ = fixture()
        variants = (
            (replace(request, fragments=request.fragments[:-1]), "fragment_inventory"),
            (
                replace(
                    request,
                    fragments=request.fragments
                    + (SequenceFragment("extra", "G", sha("G"), "extra"),),
                ),
                "fragment_inventory",
            ),
            (
                replace(
                    request,
                    placements=(
                        replace(
                            request.placements[0], source_range=SequenceRange(3, 5)
                        ),
                    )
                    + request.placements[1:],
                ),
                "source_range",
            ),
            (
                replace(
                    request,
                    placements=(
                        replace(
                            request.placements[0], source_range=SequenceRange(1, 1)
                        ),
                    )
                    + request.placements[1:],
                ),
                "source_range",
            ),
            (
                replace(
                    request,
                    placements=(
                        replace(
                            request.placements[0], molecule_range=SequenceRange(1, 3)
                        ),
                    )
                    + request.placements[1:],
                ),
                "destination_partition",
            ),
        )
        for bad, code in variants:
            with self.subTest(code=code):
                self.assert_code(
                    check_molecular_design_request(
                        bad, expected_request_fingerprint=bad.fingerprint
                    ),
                    code,
                )
        switched = replace(
            request,
            placements=(request.placements[1], request.placements[0])
            + request.placements[2:],
        )
        self.assert_code(
            check_molecular_design_request(
                switched, expected_request_fingerprint=switched.fingerprint
            ),
            "destination_partition",
        )

    def test_construct_rehashing_does_not_authorize_changed_maps_or_chemistry(self):
        request, construct, candidate = fixture()
        variants = (
            (replace(construct, molecule_id="swapped"), "construct_molecule_id"),
            (replace(construct, request_fingerprint="a" * 64), "construct_request"),
            (
                replace(
                    construct,
                    placements=(replace(construct.placements[0], fragment_id="utr3"),)
                    + construct.placements[1:],
                ),
                "construct_placements",
            ),
            (replace(construct, unknown_features=("cap",)), "construct_features"),
            (
                replace(construct, features=construct.features[:-1]),
                "construct_features",
            ),
        )
        for bad, code in variants:
            forged = replace(candidate, construct_fingerprint=bad.fingerprint)
            self.assert_code(check(request, bad, forged), code)

    def test_emitted_regions_maps_provenance_and_chemistry_are_exact(self):
        request, construct, candidate = fixture()
        for changes, code in (
            ({"id": "other"}, "molecule_profile"),
            ({"source_locator": "self-declared"}, "molecule_provenance"),
            ({"sequence_sha256": "a" * 64}, "molecule_hash"),
            ({"boundaries": SequenceRange(1, 17)}, "molecule_boundaries"),
            ({"sequence": candidate.molecule.sequence + "A"}, "molecule_boundaries"),
            ({"features": candidate.molecule.features[:-1]}, "molecule_features"),
            ({"unknown_features": ("cap",)}, "molecule_features"),
        ):
            self.assert_code(
                check(request, construct, molecule_change(candidate, **changes)), code
            )
        region = candidate.molecule.regions[0]
        for changes in (
            {"range": SequenceRange(0, 1)},
            {"source_range": SequenceRange(0, 2)},
            {"source_locator": "different source"},
            {"kind": "cds"},
            {"reading_frame": 1},
        ):
            altered = molecule_change(
                candidate,
                regions=(replace(region, **changes),) + candidate.molecule.regions[1:],
            )
            self.assert_code(check(request, construct, altered), "molecule_regions")
        for changes, code in (
            ({"request_fingerprint": "a" * 64}, "candidate_request"),
            ({"construct_fingerprint": "a" * 64}, "candidate_construct"),
            ({"source_maps": candidate.source_maps[:-1]}, "candidate_source_maps"),
        ):
            self.assert_code(
                check(request, construct, replace(candidate, **changes)), code
            )

    def test_unknown_chemistry_is_unknown_and_unsupported_features_not_admitted(self):
        request, _, _ = fixture()
        features = (
            replace(request.features[0], status="unknown", value=None),
        ) + request.features[1:]
        bad = replace(request, features=features)
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "unknown_chemistry",
            CheckOutcome.UNKNOWN,
        )
        bad = replace(request, unknown_features=("exact_tail_material",))
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "unknown_molecule_features",
            CheckOutcome.UNKNOWN,
        )
        features = list(request.features)
        features[2] = replace(features[2], value="modified_bases")
        bad = replace(request, features=tuple(features))
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "unsupported_chemistry",
            CheckOutcome.UNSUPPORTED,
        )
        features = list(request.features)
        features[0] = replace(features[0], value="none")
        bad = replace(request, features=tuple(features))
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "cap_end_correspondence",
        )
        features = list(request.features)
        features[1] = replace(features[1], value="exact:3")
        bad = replace(request, features=tuple(features))
        self.assert_code(
            check_molecular_design_request(
                bad, expected_request_fingerprint=bad.fingerprint
            ),
            "tail_length",
        )

    def test_explicit_no_tail_profile_is_supported_without_inventing_adenines(self):
        request, construct, candidate = fixture()
        features = tuple(
            replace(x, value="absent") if x.feature == "poly_a_tail" else x
            for x in request.features
        )
        request = replace(
            request,
            fragments=request.fragments[:-1],
            placements=request.placements[:-1],
            features=features,
        )
        construct = replace(
            construct,
            request_fingerprint=request.fingerprint,
            placements=request.placements,
            features=features,
        )
        candidate = molecule_change(
            candidate,
            sequence="GGAUGGCUUAACC",
            boundaries=SequenceRange(0, 13),
            regions=candidate.molecule.regions[:-1],
            features=features,
        )
        candidate = replace(
            candidate,
            request_fingerprint=request.fingerprint,
            construct_fingerprint=construct.fingerprint,
            source_maps=request.placements,
        )
        self.assertTrue(check(request, construct, candidate).passed)

    def test_human_dna_and_host_claims_never_become_software_eligibility(self):
        request, _, _ = fixture()
        for target, code in (
            (make_human_target(), "human_use_not_admitted"),
            (TargetContext("software", "1", PayloadFormat.DNA), "unsupported_modality"),
            (
                TargetContext(
                    "software", "1", PayloadFormat.RNA, capabilities=("expression",)
                ),
                "unsupported_target_assumptions",
            ),
        ):
            bad = replace(request, target=target)
            self.assert_code(
                check_molecular_design_request(
                    bad, expected_request_fingerprint=bad.fingerprint
                ),
                code,
                CheckOutcome.UNSUPPORTED,
            )

    def test_new_authorized_combination_passes_but_original_authority_and_reference_refuse(
        self,
    ):
        request, construct, candidate = fixture()
        # Old readiness uses independently authored whole-source coordinates.
        original = replace(
            candidate.molecule,
            regions=tuple(
                replace(x, source_range=x.range) for x in candidate.molecule.regions
            ),
        )
        reference, sources = reference_for(original)
        self.assertTrue(
            check_payload(
                original,
                reference,
                expected_reference_fingerprint=reference.fingerprint,
                retained_sources=sources,
            ).passed
        )
        source = replace(
            request.fragments[0], sequence="ACCC", sequence_sha256=sha("ACCC")
        )
        placement = replace(
            request.placements[0], fragment_fingerprint=source.fingerprint
        )
        updated = replace(
            request,
            fragments=(source,) + request.fragments[1:],
            placements=(placement,) + request.placements[1:],
        )
        assembly = replace(
            construct,
            request_fingerprint=updated.fingerprint,
            placements=updated.placements,
        )
        proposed = molecule_change(candidate, sequence="CCAUGGCUUAACCAAAA")
        proposed = replace(
            proposed,
            request_fingerprint=updated.fingerprint,
            construct_fingerprint=assembly.fingerprint,
            source_maps=updated.placements,
        )
        self.assertTrue(check(updated, assembly, proposed).passed)
        self.assert_code(
            check(updated, assembly, proposed, pin=request.fingerprint),
            "request_authority",
        )
        self.assert_code(check(request, construct, proposed), "fragment_nucleotides")
        comparison = replace(proposed.molecule, regions=original.regions)
        self.assertFalse(
            check_payload(
                comparison,
                reference,
                expected_reference_fingerprint=reference.fingerprint,
                retained_sources=sources,
            ).passed
        )

    def test_receipt_freshness_and_strict_tool_schema_scope_and_diagnostic_import(self):
        request, construct, candidate = fixture()
        result = check(request, construct, candidate)
        changed = molecule_change(candidate, sequence="GAAUGGCUUAACCAAAA")
        self.assertEqual(
            result.freshness(
                request,
                construct,
                changed,
                expected_request_fingerprint=request.fingerprint,
            ).changed_dependencies,
            ("candidate",),
        )
        for changes in (
            {"schema_version": "old"},
            {"stage": []},
            {"outcome": []},
            {"checks": []},
            {"claim_scope": "biological"},
            {"evidence_boundary": "empirical"},
            {"human_therapeutic_admission": "admitted"},
            {"reference_promotion": "promoted"},
            {"unresolved_obligations": []},
            {"extra": "field"},
            {"stage": "request"},
            {
                "diagnostics": [
                    {"status": "fail", "code": "bad", "message": "not passing"}
                ]
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                MolecularDesignResult.from_dict(result.to_dict() | changes)
        for key in ("checker", "profile", "admission_policy"):
            data = result.to_dict()
            data["dependencies"][key] = "old"
            with self.assertRaises(SerializationError):
                MolecularDesignResult.from_dict(data)
        data = result.to_dict()
        data["dependencies"]["schemas"]["fragment"] = "old"
        with self.assertRaises(SerializationError):
            MolecularDesignResult.from_dict(data)
        failure = check(request, construct, changed)
        self.assertEqual(MolecularDesignResult.from_json(failure.to_json()), failure)


if __name__ == "__main__":
    unittest.main()
