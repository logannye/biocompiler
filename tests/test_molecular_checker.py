"""Exact nucleotide acceptance remains separate from protein preservation."""

from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.construct import ConstructFeature
from biocompiler.ir.molecular import (
    EncodingChange,
    MolecularArtifact,
    MolecularRecord,
    TranslationPolicy,
    reference_feature_statuses,
)
from biocompiler.registry.references import translate_cds
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.molecular import MolecularResult, check_molecular
from test_component_adapters import DNA, MANIFEST, RNA
from test_construct_checker import fixture as construct_fixture


def sha(sequence):
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def fixture(alphabet="DNA"):
    """Construct the candidate by schema; never import a sequence emitter."""
    request, construct, registry, manifests = construct_fixture(alphabet)
    reference = manifests[MANIFEST.id].record(DNA.id if alphabet == "DNA" else RNA.id)
    placement = construct.placements[0]
    record = MolecularRecord(
        id=placement.molecule_id,
        instance_id=placement.instance_id,
        molecule_id=placement.molecule_id,
        alphabet=reference.alphabet,
        artifact_class=reference.artifact_class,
        sequence=reference.sequence,
        sequence_sha256=reference.sequence_sha256,
        component=placement.component,
        reference_selection=request.references[0].selection,
        source_range=placement.source_range,
        molecule_range=placement.molecule_range,
        feature_statuses=reference_feature_statuses(reference),
        completeness=reference.completeness,
        unknown_features=reference.unknown_features,
        evidence_relationships=reference.evidence_relationships,
        requirement_ids=placement.requirement_ids,
        source=placement.source,
    )
    artifact = MolecularArtifact(
        request.fingerprint,
        construct.fingerprint,
        construct.layout_fingerprint,
        construct.registry_lock,
        alphabet + "-CDS",
        (record,),
        source_request_fingerprint=request.source_request_fingerprint,
    )
    return request, construct, artifact, registry, manifests


def with_sequence(artifact, sequence):
    return replace(
        artifact,
        records=(
            replace(
                artifact.records[0], sequence=sequence, sequence_sha256=sha(sequence)
            ),
        ),
    )


class MolecularCheckerTests(unittest.TestCase):
    def test_dna_and_rna_pass_four_separate_independent_comparisons(self):
        for alphabet in ("DNA", "RNA"):
            inputs = fixture(alphabet)
            with patch(
                "socket.create_connection", side_effect=AssertionError("offline only")
            ):
                result = check_molecular(*inputs)
            self.assertEqual(result.outcome, CheckOutcome.PASS)
            self.assertEqual(
                {item.check for item in result.checks},
                {
                    "canonical_hash",
                    "exact_reference",
                    "translation_reference",
                    "dna_rna_correspondence",
                },
            )
            self.assertTrue(
                all(item.outcome is CheckOutcome.PASS for item in result.checks)
            )
            self.assertEqual(result.checked_requirement_ids, ("exact_reference",))
            self.assertEqual(MolecularResult.from_json(result.to_json()), result)
            self.assertTrue(result.is_fresh(*inputs))
            translation = next(
                item for item in result.checks if item.check == "translation_reference"
            )
            self.assertEqual(
                translation.expected_fingerprint,
                "ca35f562908d00ac249b9c7b8d6694ff5dc910e0a2ed4f7ddf4346162e91fec8",
            )

    def test_synonymous_edit_fails_exact_reference_despite_passing_translation(self):
        for alphabet in ("DNA", "RNA"):
            request, construct, artifact, registry, manifests = fixture(alphabet)
            original = artifact.records[0].sequence
            self.assertEqual(original[3:6], "GCC")
            edited = original[:5] + ("T" if alphabet == "DNA" else "U") + original[6:]
            self.assertEqual(
                translate_cds(edited, alphabet), translate_cds(original, alphabet)
            )
            result = check_molecular(
                request, construct, with_sequence(artifact, edited), registry, manifests
            )
            self.assertEqual(result.outcome, CheckOutcome.FAIL)
            outcomes = {item.check: item.outcome for item in result.checks}
            self.assertEqual(outcomes["canonical_hash"], CheckOutcome.PASS)
            self.assertEqual(outcomes["translation_reference"], CheckOutcome.PASS)
            self.assertEqual(outcomes["exact_reference"], CheckOutcome.FAIL)
            self.assertEqual(outcomes["dna_rna_correspondence"], CheckOutcome.FAIL)
            diagnostic = next(
                item for item in result.diagnostics if item.code == "exact_reference"
            )
            self.assertIn("nucleotide 5", diagnostic.message)
            self.assertEqual(diagnostic.requirement_ids, ("exact_reference",))
            self.assertEqual(diagnostic.source, construct.placements[0].source)

    def test_missense_truncation_and_stop_changes_fail_translation_and_identity(self):
        request, construct, artifact, registry, manifests = fixture()
        original = artifact.records[0].sequence
        sequences = (
            original[:4] + "A" + original[5:],
            original[:-1],
            original[:-3],
            original[:3] + "TAA" + original[6:],
            original[:-3] + "CAA",
            original + "TAA",
        )
        for sequence in sequences:
            with self.subTest(sequence_hash=sha(sequence)):
                result = check_molecular(
                    request,
                    construct,
                    with_sequence(artifact, sequence),
                    registry,
                    manifests,
                )
                outcomes = {item.check: item.outcome for item in result.checks}
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertEqual(outcomes["exact_reference"], CheckOutcome.FAIL)
                self.assertEqual(outcomes["translation_reference"], CheckOutcome.FAIL)

    def test_false_hash_frame_orientation_policy_scope_and_selected_reference_fail(
        self,
    ):
        request, construct, artifact, registry, manifests = fixture()
        record = artifact.records[0]
        changed_records = (
            replace(record, sequence_sha256="0" * 64),
            replace(record, reading_frame=1),
            replace(record, orientation="reverse"),
            replace(record, translation_policy=TranslationPolicy(genetic_code=2)),
            replace(
                record,
                translation_policy=TranslationPolicy(
                    protein_length_includes_stop=False
                ),
            ),
            replace(record, completeness="complete_payload"),
            replace(
                record,
                reference_selection=replace(record.reference_selection, reference=RNA),
            ),
            replace(record, source_range=SequenceRange(1, 1491)),
            replace(record, molecule_range=SequenceRange(0, 1490)),
            replace(record, source=None),
            replace(record, requirement_ids=()),
            replace(record, component=replace(record.component, version="2")),
            replace(record, id="invented-record"),
        )
        for changed in changed_records:
            with self.subTest(record=changed.fingerprint):
                self.assertEqual(
                    check_molecular(
                        request,
                        construct,
                        replace(artifact, records=(changed,)),
                        registry,
                        manifests,
                    ).outcome,
                    CheckOutcome.FAIL,
                )
        changed = replace(artifact, profile="RNA-CDS")
        self.assertEqual(
            check_molecular(request, construct, changed, registry, manifests).outcome,
            CheckOutcome.FAIL,
        )

    def test_wrong_alphabet_is_rejected_without_repair_or_modality_conversion(self):
        request, construct, artifact, registry, manifests = fixture()
        record = artifact.records[0]
        for sequence in (
            record.sequence.lower(),
            record.sequence + "N",
            record.sequence + "\n",
            record.sequence.replace("T", "U"),
        ):
            with self.assertRaises(SerializationError):
                replace(record, sequence=sequence)
        converted = record.sequence.replace("T", "U")
        changed = replace(
            record,
            alphabet="RNA",
            artifact_class="coding_rna",
            sequence=converted,
            sequence_sha256=sha(converted),
        )
        result = check_molecular(
            request,
            construct,
            replace(artifact, records=(changed,)),
            registry,
            manifests,
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("reference_metadata", {item.code for item in result.diagnostics})

    def test_claiming_known_delivered_features_or_invented_subfeatures_fails(self):
        request, construct, artifact, registry, manifests = fixture()
        record = artifact.records[0]
        statuses = tuple(
            replace(item, status="known", value="m7G")
            if (item.feature, item.scope) == ("cap", "delivered_molecule")
            else item
            for item in record.feature_statuses
        )
        invented = ConstructFeature(
            "domain",
            record.molecule_id,
            "binding-domain",
            SequenceRange(1, 100),
            DNA,
            SequenceRange(1, 100),
            "diagram",
            (registry.components[0].evidence[0],),
        )
        for changed in (
            replace(record, feature_statuses=statuses),
            replace(record, feature_statuses=()),
            replace(record, unknown_features=()),
            replace(record, evidence_relationships=("empirically-validated",)),
            replace(record, features=(invented,)),
        ):
            self.assertEqual(
                check_molecular(
                    request,
                    construct,
                    replace(artifact, records=(changed,)),
                    registry,
                    manifests,
                ).outcome,
                CheckOutcome.FAIL,
            )

    def test_missing_inventory_and_upstream_construct_changes_do_not_pass(self):
        request, construct, artifact, registry, manifests = fixture()
        self.assertEqual(
            check_molecular(
                request, construct, replace(artifact, records=()), registry, manifests
            ).outcome,
            CheckOutcome.FAIL,
        )
        record = artifact.records[0]
        self.assertEqual(
            check_molecular(
                request,
                construct,
                replace(artifact, records=(replace(record, molecule_id="other"),)),
                registry,
                manifests,
            ).outcome,
            CheckOutcome.FAIL,
        )
        changed_construct = replace(
            construct, placements=(replace(construct.placements[0], reading_frame=1),)
        )
        changed_artifact = replace(
            artifact,
            construct_fingerprint=changed_construct.fingerprint,
            layout_fingerprint=changed_construct.layout_fingerprint,
            records=(replace(record, reading_frame=1),),
        )
        result = check_molecular(
            request, changed_construct, changed_artifact, registry, manifests
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertTrue(
            any(item.code.startswith("construct:") for item in result.diagnostics)
        )

    def test_stale_registry_missing_references_and_rewritten_identity_roots_fail(self):
        request, construct, artifact, registry, manifests = fixture()
        self.assertEqual(
            check_molecular(request, construct, artifact, registry, {}).outcome,
            CheckOutcome.UNKNOWN,
        )
        self.assertEqual(
            check_molecular(
                request, construct, artifact, replace(registry, version="2"), manifests
            ).outcome,
            CheckOutcome.FAIL,
        )
        for key in (
            "request_fingerprint",
            "construct_fingerprint",
            "layout_fingerprint",
            "source_request_fingerprint",
        ):
            self.assertEqual(
                check_molecular(
                    request,
                    construct,
                    replace(artifact, **{key: "0" * 64}),
                    registry,
                    manifests,
                ).outcome,
                CheckOutcome.FAIL,
            )

    def test_encoding_change_record_does_not_authorize_optimization_or_reuse(self):
        request, construct, artifact, registry, manifests = fixture()
        record = artifact.records[0]
        change = EncodingChange(
            "optimization",
            record.id,
            record.sequence_sha256,
            record.sequence_sha256,
            ("sequence",),
            "Proposed future recoding",
            ("protein",),
        )
        changed = replace(artifact, changes=(change,))
        self.assertEqual(
            check_molecular(request, construct, changed, registry, manifests).outcome,
            CheckOutcome.UNSUPPORTED,
        )
        result = check_molecular(request, construct, artifact, registry, manifests)
        self.assertIn(
            "candidate",
            result.freshness(
                request, construct, changed, registry, manifests
            ).changed_dependencies,
        )
        self.assertIn("behavior", artifact.evidence_policy.invalidated_analyses)
        self.assertIn("expression", artifact.evidence_policy.invalidated_analyses)

    def test_result_is_immutable_strict_and_stale_for_changed_dependencies(self):
        request, construct, artifact, registry, manifests = fixture()
        result = check_molecular(request, construct, artifact, registry, manifests)
        with self.assertRaises(TypeError):
            result.dependencies["candidate"] = "0" * 64
        for key, value in (
            ("outcome", "proven"),
            ("checks", {}),
            ("checks", []),
            ("diagnostics", {}),
            ("dependencies", []),
            ("claim_scope", "universal behavior"),
        ):
            data = result.to_dict()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(SerializationError):
                MolecularResult.from_dict(data)
        data = result.to_dict()
        data["checks"][0]["actual_fingerprint"] = "0" * 64
        with self.assertRaises(SerializationError):
            MolecularResult.from_dict(data)
        sequence = artifact.records[0].sequence
        changed = with_sequence(artifact, sequence[:5] + "T" + sequence[6:])
        self.assertIn(
            "candidate",
            result.freshness(
                request, construct, changed, registry, manifests
            ).changed_dependencies,
        )
        self.assertIn(
            "registry",
            result.freshness(
                request, construct, artifact, replace(registry, version="2"), manifests
            ).changed_dependencies,
        )
        self.assertIn(
            "references",
            result.freshness(
                request, construct, artifact, registry, {}
            ).changed_dependencies,
        )


if __name__ == "__main__":
    unittest.main()
