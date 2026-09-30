"""Independent literal controls for software-only multi-region RNA emission."""

from dataclasses import replace
import hashlib
import unittest

from biocompiler.backends.molecular_design import emit_molecular_design
from biocompiler.compiler.molecular_design import (
    COMPLETION_SCOPE,
    run_molecular_design_pipeline,
)
from biocompiler.compiler.pipeline import ArtifactStatus, PipelineError
from biocompiler.errors import SerializationError
from biocompiler.ir.molecular_design import (
    FragmentPlacement,
    MolecularDesignRequest,
    SequenceFragment,
)
from biocompiler.ir.payload import PayloadFeature
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.stages import Stage
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.synthesis.molecular_design import generate_molecular_design_construct
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.molecular_design import (
    check_molecular_design,
    check_molecular_design_request,
)


def make_request(*, tail=True):
    """Artificial independently specified source slices; no functional elements."""
    values = [
        ("front", "five_prime_utr", "CGG", 1, 3, None),
        ("coding", "cds", "CCAUGGCUUAACC", 2, 11, "MA*"),
        ("back", "three_prime_utr", "CCU", 0, 2, None),
    ]
    if tail:
        values.append(("tail", "poly_a", "AAAA", 0, 4, None))
    fragments, placements = [], []
    cursor = 0
    for identity, kind, spelling, start, end, protein in values:
        fragment = SequenceFragment(
            identity,
            spelling,
            hashlib.sha256(spelling.encode()).hexdigest(),
            "invented:" + identity,
        )
        fragments.append(fragment)
        placements.append(
            FragmentPlacement(
                "region_" + identity,
                kind,
                identity,
                fragment.fingerprint,
                SequenceRange(start, end),
                SequenceRange(cursor, cursor + end - start),
                protein,
            )
        )
        cursor += end - start
    features = tuple(
        PayloadFeature(key, "known", "invented:" + key, value)
        for key, value in (
            ("cap", "none"),
            ("poly_a_tail", "exact:4" if tail else "absent"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "triphosphate"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    return MolecularDesignRequest(
        "invented_request",
        "invented_molecule",
        tuple(fragments),
        tuple(placements),
        features,
    )


class MolecularDesignTests(unittest.TestCase):
    def test_literal_slices_and_structured_specification(self):
        for tail in (False, True):
            with self.subTest(tail=tail):
                request = make_request(tail=tail)
                construct = generate_molecular_design_construct(request)
                candidate = emit_molecular_design(request, construct)
                self.assertEqual(
                    candidate.molecule.sequence,
                    "GGAUGGCUUAACC" + ("AAAA" if tail else ""),
                )
                self.assertEqual(
                    candidate.molecule.regions[1].source_range, SequenceRange(2, 11)
                )
                self.assertEqual(
                    candidate.molecule.regions[1].range, SequenceRange(2, 11)
                )
                self.assertEqual(
                    candidate.molecule.regions[0].source_range, SequenceRange(1, 3)
                )
                self.assertEqual(
                    candidate.molecule.regions[0].range, SequenceRange(0, 2)
                )
                self.assertEqual(candidate.source_maps, request.placements)
                self.assertEqual(candidate.molecule.features, request.features)
                self.assertEqual(
                    candidate.molecule.source_locator,
                    "molecular-design-request:invented_request",
                )
                self.assertEqual(candidate.human_therapeutic_admission, "not_admitted")
                self.assertTrue(
                    check_molecular_design(
                        request,
                        construct,
                        candidate,
                        expected_request_fingerprint=request.fingerprint,
                    ).passed
                )

    def test_strict_round_trips_and_immutable_containers(self):
        request = make_request()
        construct = generate_molecular_design_construct(request)
        artifact = emit_molecular_design(request, construct)
        for value in (
            *request.fragments,
            *request.placements,
            request,
            construct,
            artifact,
        ):
            with self.subTest(type=type(value).__name__):
                restored = type(value).from_json(value.to_json())
                self.assertEqual(restored, value)
                self.assertEqual(restored.fingerprint, value.fingerprint)
                malformed = value.to_dict() | {"extra": True}
                with self.assertRaises(SerializationError):
                    type(value).from_dict(malformed)
        source = list(request.fragments)
        copied = replace(request, fragments=source)
        source.clear()
        self.assertEqual(len(copied.fragments), 4)
        for value in (request, construct, artifact):
            data = value.to_dict()
            data["nodes"][0]["kind"] = "invented_dynamic_claim"
            with self.assertRaises(SerializationError):
                type(value).from_dict(data)
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            replace(request, target=TargetContext("\ud800", "1", PayloadFormat.RNA))

    def test_software_scope_cannot_be_relabelled(self):
        request = make_request()
        construct = generate_molecular_design_construct(request)
        artifact = emit_molecular_design(request, construct)
        for value in (request, construct, artifact):
            for key, changed in (
                ("intended_use", "human_therapeutic"),
                ("human_therapeutic_admission", "admitted"),
                ("reference_promotion", "promoted"),
                ("evidence_boundary", "externally_reviewed"),
            ):
                with (
                    self.subTest(type=type(value).__name__, key=key),
                    self.assertRaises(SerializationError),
                ):
                    type(value).from_dict(value.to_dict() | {key: changed})

    def test_emitter_never_fills_gaps_reverses_or_converts(self):
        request = make_request()
        changed_placement = replace(
            request.placements[0], molecule_range=SequenceRange(1, 3)
        )
        malformed = replace(
            request, placements=(changed_placement, *request.placements[1:])
        )
        with self.assertRaises(SerializationError):
            emit_molecular_design(
                malformed, generate_molecular_design_construct(malformed)
            )
        reversed_request = replace(
            request,
            placements=(
                replace(request.placements[0], orientation="reverse"),
                *request.placements[1:],
            ),
        )
        with self.assertRaises(SerializationError):
            emit_molecular_design(
                reversed_request, generate_molecular_design_construct(reversed_request)
            )
        fragment = replace(request.fragments[0], alphabet="DNA")
        dna_request = replace(
            request,
            fragments=(fragment, *request.fragments[1:]),
            placements=(
                replace(
                    request.placements[0], fragment_fingerprint=fragment.fingerprint
                ),
                *request.placements[1:],
            ),
        )
        with self.assertRaises(SerializationError):
            emit_molecular_design(
                dna_request, generate_molecular_design_construct(dna_request)
            )

    def test_checked_pipeline_has_three_stages_and_only_structural_completion(self):
        request = make_request()
        build = run_molecular_design_pipeline(
            request, expected_request_fingerprint=request.fingerprint
        )
        self.assertEqual(build.result.status, ArtifactStatus.COMPLETE)
        self.assertEqual(build.result.scope, COMPLETION_SCOPE)
        self.assertTrue(
            build.authority_result.passed
            and build.construct_result.passed
            and build.check_result.passed
        )
        self.assertEqual(build.candidate.molecule.sequence, "GGAUGGCUUAACCAAAA")
        self.assertEqual(
            tuple(
                build.manager.get(key).stage
                for key in ("components", "construct", "molecular")
            ),
            (Stage.COMPONENTS, Stage.CONSTRUCT, Stage.MOLECULAR),
        )
        self.assertIn(
            "source_behavior_realization", {x.id for x in build.result.unresolved}
        )
        for key in ("construct", "molecular"):
            self.assertFalse(build.manager.get(key).provenance["observation_map"])
        with self.assertRaises(PipelineError):
            build.manager.result("molecular", scope="complete_payload")

    def test_independent_request_authority_and_transitive_freshness(self):
        request = make_request()
        with self.assertRaises(PipelineError):
            run_molecular_design_pipeline(
                request, expected_request_fingerprint="0" * 64
            )
        for key in (
            "expected_request",
            "fragments",
            "layout",
            "molecular_design_checker",
            "human_admission_policy",
        ):
            with self.subTest(key=key):
                build = run_molecular_design_pipeline(
                    request, expected_request_fingerprint=request.fingerprint
                )
                build.manager.set_dependency(key, fingerprint("changed"))
                with self.assertRaises(PipelineError):
                    build.manager.result("molecular", scope=COMPLETION_SCOPE)

    def test_unknown_or_unsupported_request_cannot_complete_pipeline(self):
        request = make_request()
        cases = (
            (
                replace(request, unknown_features=("actual_material",)),
                CheckOutcome.UNKNOWN,
            ),
            (
                replace(
                    request,
                    features=(
                        replace(request.features[0], status="unknown", value=None),
                        *request.features[1:],
                    ),
                ),
                CheckOutcome.UNKNOWN,
            ),
            (
                replace(
                    request,
                    features=(
                        replace(request.features[0], value="unmodeled_cap"),
                        *request.features[1:],
                    ),
                ),
                CheckOutcome.UNSUPPORTED,
            ),
        )
        for changed, outcome in cases:
            with self.subTest(outcome=outcome):
                result = check_molecular_design_request(
                    changed, expected_request_fingerprint=changed.fingerprint
                )
                self.assertEqual(result.outcome, outcome)
                with self.assertRaises(PipelineError):
                    run_molecular_design_pipeline(
                        changed, expected_request_fingerprint=changed.fingerprint
                    )

    def test_candidate_mutation_cannot_redefine_fragment_authority(self):
        request = make_request()
        construct = generate_molecular_design_construct(request)
        candidate = emit_molecular_design(request, construct)
        sequence = "A" + candidate.molecule.sequence[1:]
        modified = replace(
            candidate,
            molecule=replace(
                candidate.molecule,
                sequence=sequence,
                sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
            ),
        )
        result = check_molecular_design(
            request,
            construct,
            modified,
            expected_request_fingerprint=request.fingerprint,
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)


if __name__ == "__main__":
    unittest.main()
