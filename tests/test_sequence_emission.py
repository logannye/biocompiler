"""Exact reference emission uses each nucleotide source without optimization."""

from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

from biocompiler.backends.dna import emit_dna_cds
from biocompiler.backends.reference import emit_reference_sequence
from biocompiler.backends.rna import emit_rna_cds
from biocompiler.errors import SerializationError
from biocompiler.ir.molecular import MolecularArtifact
from biocompiler.registry.references import ReferenceManifest
from biocompiler.verification.construct import check_construct
from test_construct_checker import candidate_for, fixture

EXPECTED_HASHES = {
    "DNA": "04738ea1bec87847cce856152550621551af9d4f73a3e0bbeb929cb89dcbc643",
    "RNA": "90b1d6267fa865806bf73f384125d55d009207e65aac5328045ae7b8e0e4e9d6",
}


class SequenceEmissionTests(unittest.TestCase):
    def test_exact_dna_and_rna_records_have_pinned_symbols_and_explicit_scope(self):
        for alphabet, backend in (("DNA", emit_dna_cds), ("RNA", emit_rna_cds)):
            with self.subTest(alphabet=alphabet):
                request, construct, registry, manifests = fixture(alphabet)
                artifact = backend(request, construct, registry, manifests)
                record = artifact.records[0]
                selected = request.references[0].selection
                reference = manifests[selected.manifest.id].record(
                    selected.reference.id
                )
                self.assertEqual(record.sequence, reference.sequence)
                self.assertEqual(record.sequence_sha256, EXPECTED_HASHES[alphabet])
                self.assertEqual(
                    hashlib.sha256(record.sequence.encode("ascii")).hexdigest(),
                    EXPECTED_HASHES[alphabet],
                )
                self.assertEqual(record.alphabet, alphabet)
                self.assertEqual(record.length, 1491)
                self.assertEqual(record.reference_selection, selected)
                self.assertEqual(artifact.profile, alphabet + "-CDS")
                self.assertEqual(artifact.artifact_scope, "exact_cds")
                self.assertEqual(record.completeness, "CDS-reference-only")
                self.assertEqual(record.unknown_features, reference.unknown_features)
                self.assertEqual(
                    record.evidence_relationships, reference.evidence_relationships
                )
                self.assertEqual(
                    record.source_range, construct.placements[0].source_range
                )
                self.assertEqual(record.source, construct.placements[0].source)
                self.assertEqual(
                    record.requirement_ids, construct.placements[0].requirement_ids
                )
                self.assertEqual(artifact.registry_lock, construct.registry_lock)
                self.assertEqual(
                    artifact.layout_fingerprint, construct.layout_fingerprint
                )
                self.assertFalse(artifact.changes)
                self.assertEqual(artifact.encoding_policy.optimization, "disabled")
                self.assertFalse(
                    hasattr(artifact, "accepted") or hasattr(artifact, "passed")
                )
                self.assertEqual(
                    MolecularArtifact.from_json(artifact.to_json()), artifact
                )

    def test_rna_spelling_is_read_from_rna_record_without_reading_or_converting_dna(
        self,
    ):
        request, construct, registry, manifests = fixture("RNA")
        checked = check_construct(request, construct, registry, manifests)
        selected = request.references[0].selection.reference.id
        original = ReferenceManifest.record
        reads = []

        def selected_only(manifest, reference_id, **kwargs):
            self.assertEqual(reference_id, selected)
            reads.append(reference_id)
            return original(manifest, reference_id, **kwargs)

        # Isolate emission from the already established M5 checker. Any attempt
        # to synthesize RNA by opening the DNA record is now a test failure.
        with patch(
            "biocompiler.backends.reference.check_construct", return_value=checked
        ):
            with patch.object(ReferenceManifest, "record", selected_only):
                artifact = emit_rna_cds(request, construct, registry, manifests)
        self.assertEqual(reads, [selected])
        self.assertEqual(artifact.records[0].sequence_sha256, EXPECTED_HASHES["RNA"])
        self.assertNotIn("T", artifact.records[0].sequence)

    def test_modality_specific_backends_cannot_silently_convert_a_target(self):
        for alphabet, wrong_backend in (("RNA", emit_dna_cds), ("DNA", emit_rna_cds)):
            with (
                self.subTest(alphabet=alphabet),
                self.assertRaisesRegex(SerializationError, "explicit .* target"),
            ):
                wrong_backend(*fixture(alphabet))

    def test_changed_construct_or_current_reference_blocks_emission(self):
        request, construct, registry, manifests = fixture()
        changed = replace(
            construct,
            placements=(replace(construct.placements[0], orientation="reverse"),),
        )
        with self.assertRaisesRegex(SerializationError, "currently passing construct"):
            emit_reference_sequence(request, changed, registry, manifests)
        for current_registry, current_manifests in (
            (replace(registry, version="2"), manifests),
            (registry, {}),
        ):
            with (
                self.subTest(registry=current_registry.version),
                self.assertRaises(SerializationError),
            ):
                emit_reference_sequence(
                    request, construct, current_registry, current_manifests
                )

    def test_no_source_lineage_is_invented_when_optional_ancestor_is_absent(self):
        request, _, registry, manifests = fixture()
        request = replace(request, source_request_fingerprint=None)
        construct = candidate_for(request)
        artifact = emit_reference_sequence(request, construct, registry, manifests)
        self.assertIsNone(artifact.source_request_fingerprint)
        self.assertEqual(artifact.request_fingerprint, request.fingerprint)
        self.assertEqual(artifact.construct_fingerprint, construct.fingerprint)

    def test_known_unknown_and_inapplicable_features_keep_distinct_scopes(self):
        artifact = emit_rna_cds(*fixture("RNA"))
        statuses = {
            (item.scope, item.feature): item
            for item in artifact.records[0].feature_statuses
        }
        self.assertEqual(statuses["cds_record", "alphabet"].value, "RNA")
        self.assertEqual(statuses["cds_record", "reading-frame"].value, "0")
        self.assertEqual(statuses["cds_record", "cap"].status, "inapplicable")
        self.assertEqual(statuses["delivered_molecule", "cap"].status, "unknown")
        self.assertIsNone(statuses["delivered_molecule", "cap"].value)
        self.assertEqual(
            statuses["cds_record", "domain-feature-coordinates"].status, "unknown"
        )
        self.assertFalse(artifact.records[0].features)

    def test_repeated_offline_emission_has_identical_sequence_and_artifact_identities(
        self,
    ):
        inputs = fixture()
        with patch(
            "socket.create_connection", side_effect=AssertionError("offline only")
        ):
            first = emit_reference_sequence(*inputs)
            second = emit_reference_sequence(*inputs)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(
            first.records[0].sequence_sha256, second.records[0].sequence_sha256
        )


if __name__ == "__main__":
    unittest.main()
