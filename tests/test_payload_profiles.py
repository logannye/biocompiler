"""Whole-molecule gate controls use invented software fixtures, not real payloads."""

from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.molecular import MolecularArtifact
from biocompiler.ir.payload import (
    ACCEPTED_BIOLOGICAL_PAYLOAD_PINS,
    PayloadFeature,
    PayloadMolecule,
    PayloadReference,
    PayloadRegion,
    PayloadReview,
    PayloadSource,
)
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.payload import (
    PayloadResult,
    REVIEW_SCHEMA_VERSION,
    check_payload,
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def reference_for(expected, *, source_kind="software_fixture", raw_sequence=None):
    """Create explicitly synthetic retained inputs; no actual independent reviewer."""
    primary = (
        b"Invented complete molecule for software tests only. No biological reference."
    )
    raw = (raw_sequence or expected.sequence.lower() + "\n").encode("ascii")
    primary_source = PayloadSource("primary", sha(primary), "fixture definition")
    sequence_source = PayloadSource("extraction", sha(raw), "fixture sequence")
    retained = {"primary": primary, "extraction": raw}
    reviews = []
    for reviewer, role in (
        ("fixture_extractor", "extraction"),
        ("fixture_reviewer", "independent_review"),
    ):
        statement = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "molecule_fingerprint": expected.fingerprint,
            "primary_source_sha256": primary_source.sha256,
            "sequence_source_sha256": sequence_source.sha256,
            "reviewer": reviewer,
            "role": role,
            "decision": "accept",
            "source_kind": source_kind,
        }
        raw_review = json.dumps(statement, sort_keys=True).encode("utf-8")
        retained[reviewer] = raw_review
        reviews.append(
            PayloadReview(
                reviewer,
                role,
                PayloadSource(reviewer, sha(raw_review), "fixture declaration"),
            )
        )
    reference = PayloadReference(
        "invented_software_molecule",
        "1",
        expected,
        source_kind,
        primary_source,
        sequence_source,
        tuple(reviews),
    )
    return reference, retained


def fixture(artifact_class="mature_linear_rna"):
    rna = artifact_class == "mature_linear_rna"
    circular = artifact_class == "circular_plasmid"
    # Frozen expected spelling, never obtained from an emitter or a biological source.
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
            "fixture " + kind,
            "MA*" if kind == "cds" else None,
        )
        for kind, start, end in zip(kinds, edges, edges[1:])
    )
    features = (
        PayloadFeature(
            "cap",
            "known" if rna else "inapplicable",
            "fixture chemistry",
            "cap1" if rna else None,
        ),
        PayloadFeature(
            "poly_a_tail",
            "known" if rna else "inapplicable",
            "fixture tail",
            "exact:4" if rna else None,
        ),
        PayloadFeature(
            "nucleotide_modifications", "known", "fixture chemistry", "none"
        ),
        PayloadFeature(
            "end_structure",
            "inapplicable" if circular else "known",
            "fixture ends",
            None if circular else "single_strand" if rna else "blunt",
        ),
        PayloadFeature(
            "five_prime_end",
            "inapplicable" if circular else "known",
            "fixture ends",
            None if circular else "capped" if rna else "phosphate_both_strands",
        ),
        PayloadFeature(
            "three_prime_end",
            "inapplicable" if circular else "known",
            "fixture ends",
            None if circular else "hydroxyl" if rna else "hydroxyl_both_strands",
        ),
    )
    candidate = PayloadMolecule(
        "invented_molecule",
        artifact_class,
        "RNA" if rna else "DNA",
        sequence,
        sha(sequence.encode()),
        SequenceRange(0, len(sequence)),
        "circular" if circular else "linear",
        "single" if rna else "double",
        regions,
        features,
        "fixture whole molecule",
    )
    reference, retained = reference_for(candidate)
    return candidate, reference, retained


def check(candidate, reference, retained, pin=None):
    return check_payload(
        candidate,
        reference,
        expected_reference_fingerprint=pin or reference.fingerprint,
        retained_sources=retained,
    )


class PayloadProfileTests(unittest.TestCase):
    def assert_code(self, result, code, outcome=CheckOutcome.FAIL):
        self.assertEqual(result.outcome, outcome)
        self.assertIn(code, {item.code for item in result.diagnostics})

    def test_three_explicit_profiles_pass_only_structural_fixture_readiness(self):
        for profile in ("mature_linear_rna", "linear_dna", "circular_plasmid"):
            candidate, reference, retained = fixture(profile)
            with patch(
                "socket.create_connection", side_effect=AssertionError("offline")
            ):
                result = check(candidate, reference, retained)
            self.assertTrue(result.passed, result.diagnostics)
            self.assertEqual(result.evidence_boundary, "software_fixture")
            self.assertEqual(result.reference_promotion, "not_promoted")
            self.assertIs(result.compiler_admission, False)
            self.assertEqual(PayloadMolecule.from_json(candidate.to_json()), candidate)
            self.assertEqual(PayloadReference.from_json(reference.to_json()), reference)
            self.assertEqual(PayloadResult.from_json(result.to_json()), result)
            self.assertFalse(ACCEPTED_BIOLOGICAL_PAYLOAD_PINS)

    def test_external_review_label_does_not_grant_promotion_or_admission(self):
        candidate, _, _ = fixture()
        reference, retained = reference_for(
            candidate, source_kind="externally_reviewed"
        )
        result = check(candidate, reference, retained)
        self.assertTrue(result.passed)
        self.assertEqual(result.reference_promotion, "not_promoted")
        self.assertFalse(result.compiler_admission)
        for field, value in (
            ("reference_promotion", "promoted"),
            ("compiler_admission", True),
        ):
            forged = result.to_dict() | {field: value}
            with self.assertRaises(SerializationError):
                PayloadResult.from_dict(forged)

    def test_authority_substitution_source_tamper_and_changed_extraction_fail(self):
        candidate, reference, retained = fixture()
        pin = reference.fingerprint
        changed = replace(candidate, source_locator="self asserted new source")
        forged_ref, forged_files = reference_for(changed)
        self.assert_code(
            check(changed, forged_ref, forged_files, pin), "payload_authority_pin"
        )
        self.assert_code(
            check(candidate, reference, retained | {"primary": b"tampered"}),
            "payload_source_hash",
        )
        wrong_ref, wrong_files = reference_for(
            candidate, raw_sequence="A" + candidate.sequence[1:]
        )
        self.assert_code(
            check(candidate, wrong_ref, wrong_files), "payload_source_sequence"
        )
        self.assert_code(
            check(candidate, reference, retained | {"extra": b"unreviewed"}),
            "payload_source_inventory",
        )

    def test_review_independence_and_exact_statement_are_checked(self):
        candidate, reference, retained = fixture()
        reviews = (
            reference.reviews[0],
            replace(reference.reviews[1], reviewer=reference.reviews[0].reviewer),
        )
        self.assert_code(
            check(candidate, replace(reference, reviews=reviews), retained),
            "independent_payload_review",
        )
        statement = json.loads(retained[reference.reviews[1].source.id])
        statement["molecule_fingerprint"] = "0" * 64
        raw = json.dumps(statement).encode()
        review = replace(
            reference.reviews[1],
            source=replace(reference.reviews[1].source, sha256=sha(raw)),
        )
        changed = replace(reference, reviews=(reference.reviews[0], review))
        self.assert_code(
            check(candidate, changed, retained | {review.source.id: raw}),
            "payload_review_statement",
        )

    def test_candidate_mutations_fail_even_when_sequence_hash_is_recomputed(self):
        candidate, reference, retained = fixture()
        # A synonymous codon preserves translation, but not the full-molecule identity.
        sequence = candidate.sequence[:7] + "C" + candidate.sequence[8:]
        changed = replace(
            candidate, sequence=sequence, sequence_sha256=sha(sequence.encode())
        )
        self.assert_code(check(changed, reference, retained), "exact_payload_mismatch")
        self.assertNotIn(
            "payload_protein_correspondence",
            {x.code for x in check(changed, reference, retained).diagnostics},
        )
        for changed, code in (
            (
                replace(
                    candidate, boundaries=SequenceRange(1, len(candidate.sequence))
                ),
                "whole_molecule_boundaries",
            ),
            (replace(candidate, topology="circular"), "payload_modality_mismatch"),
            (
                replace(
                    candidate,
                    regions=(candidate.regions[1], candidate.regions[0])
                    + candidate.regions[2:],
                ),
                "region_partition",
            ),
            (
                replace(
                    candidate,
                    regions=(
                        replace(candidate.regions[0], source_range=SequenceRange(1, 3)),
                    )
                    + candidate.regions[1:],
                ),
                "region_source_correspondence",
            ),
        ):
            self.assert_code(check(changed, reference, retained), code)

    def test_consistently_reauthored_incomplete_profiles_still_cannot_pass(self):
        candidate, _, _ = fixture()
        cases = (
            (
                replace(
                    candidate, boundaries=SequenceRange(1, len(candidate.sequence))
                ),
                "whole_molecule_boundaries",
                CheckOutcome.FAIL,
            ),
            (
                replace(candidate, completeness="CDS-reference-only"),
                "incomplete_molecule_claim",
                CheckOutcome.FAIL,
            ),
            (
                replace(candidate, artifact_class="dna_transcription_template"),
                "unsupported_payload_class",
                CheckOutcome.UNSUPPORTED,
            ),
            (
                replace(candidate, regions=(candidate.regions[1],)),
                "region_partition",
                CheckOutcome.FAIL,
            ),
            (
                replace(candidate, unknown_features=("actual_boundaries",)),
                "unknown_payload_features",
                CheckOutcome.UNKNOWN,
            ),
            (
                replace(
                    candidate,
                    features=tuple(
                        replace(x, status="unknown", value=None)
                        if x.feature == "cap"
                        else x
                        for x in candidate.features
                    ),
                ),
                "unknown_payload_chemistry",
                CheckOutcome.UNKNOWN,
            ),
            (
                replace(
                    candidate,
                    features=tuple(
                        replace(x, value="nominal:4")
                        if x.feature == "poly_a_tail"
                        else x
                        for x in candidate.features
                    ),
                ),
                "poly_a_tail_correspondence",
                CheckOutcome.FAIL,
            ),
            (
                replace(
                    candidate,
                    features=tuple(
                        replace(x, value="N1-methylpseudouridine")
                        if x.feature == "nucleotide_modifications"
                        else x
                        for x in candidate.features
                    ),
                ),
                "unsupported_payload_chemistry",
                CheckOutcome.UNSUPPORTED,
            ),
        )
        for changed, code, outcome in cases:
            reference, retained = reference_for(changed)
            self.assert_code(check(changed, reference, retained), code, outcome)

    def test_readiness_stales_on_sequence_layout_chemistry_authority_and_source_changes(
        self,
    ):
        candidate, reference, retained = fixture()
        result = check(candidate, reference, retained)
        pin = reference.fingerprint
        self.assertTrue(
            result.is_fresh(
                candidate,
                reference,
                expected_reference_fingerprint=pin,
                retained_sources=retained,
            )
        )
        for changed in (
            replace(candidate, source_locator="new locator"),
            replace(candidate, topology="circular"),
            replace(
                candidate,
                features=tuple(
                    replace(x, value="cap0") if x.feature == "cap" else x
                    for x in candidate.features
                ),
            ),
        ):
            self.assertFalse(
                result.is_fresh(
                    changed,
                    reference,
                    expected_reference_fingerprint=pin,
                    retained_sources=retained,
                )
            )
        self.assertFalse(
            result.is_fresh(
                candidate,
                reference,
                expected_reference_fingerprint="0" * 64,
                retained_sources=retained,
            )
        )
        self.assertFalse(
            result.is_fresh(
                candidate,
                reference,
                expected_reference_fingerprint=pin,
                retained_sources=retained | {"primary": b"changed"},
            )
        )

    def test_strict_ir_unknown_fields_claims_and_existing_cds_profile_remain_closed(
        self,
    ):
        candidate, reference, _ = fixture()
        with self.assertRaises(SerializationError):
            PayloadReference.from_dict(reference.to_dict() | {"accepted": True})
        with self.assertRaises(SerializationError):
            replace(candidate, unestablished_claims=())
        with self.assertRaises(SerializationError):
            PayloadMolecule.from_json('{"schema_version":"x","schema_version":"y"}')
        from test_molecular_checker import fixture as cds_fixture

        cds = cds_fixture()[2].to_dict()
        cds["profile"] = "mature_linear_rna"
        with self.assertRaises(SerializationError):
            MolecularArtifact.from_dict(cds)

    def test_terminal_chemistry_is_explicit_and_consistent_with_modality(self):
        for profile, feature, status, value, code in (
            ("mature_linear_rna", "cap", "known", "none", "cap_end_correspondence"),
            (
                "linear_dna",
                "three_prime_end",
                "inapplicable",
                None,
                "unsupported_payload_chemistry",
            ),
            (
                "circular_plasmid",
                "five_prime_end",
                "known",
                "phosphate_both_strands",
                "unsupported_payload_chemistry",
            ),
        ):
            candidate, _, _ = fixture(profile)
            changed = replace(
                candidate,
                features=tuple(
                    replace(x, status=status, value=value)
                    if x.feature == feature
                    else x
                    for x in candidate.features
                ),
            )
            reference, retained = reference_for(changed)
            result = check(changed, reference, retained)
            self.assert_code(
                result,
                code,
                CheckOutcome.FAIL
                if code == "cap_end_correspondence"
                else CheckOutcome.UNSUPPORTED,
            )

    def test_malformed_shapes_surrogates_and_outdated_receipts_are_rejected(self):
        candidate, reference, retained = fixture()
        for key in ("features", "regions"):
            with self.assertRaises(SerializationError):
                PayloadMolecule.from_dict(candidate.to_dict() | {key: None})
        with self.assertRaises(SerializationError):
            PayloadReference.from_dict(reference.to_dict() | {"reviews": 3})
        with self.assertRaises(SerializationError):
            replace(candidate, source_locator="\ud800")
        with self.assertRaises(SerializationError):
            replace(candidate, unknown_features=("\ud800",))
        result = check(candidate, reference, retained)
        with self.assertRaises(SerializationError):
            PayloadResult.from_dict(result.to_dict() | {"outcome": []})
        for key in ("checker", "profile", "schema"):
            data = result.to_dict()
            data["dependencies"][key] = "unreviewed.v999"
            with self.assertRaises(SerializationError):
                PayloadResult.from_dict(data)


if __name__ == "__main__":
    unittest.main()
