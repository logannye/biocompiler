"""Exact-CDS schema identity, immutability and strict untrusted import boundaries."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.molecular import (
    EncodingChange,
    EncodingEvidencePolicy,
    EncodingPolicy,
    FeatureStatus,
    MolecularArtifact,
    MolecularRecord,
    TranslationPolicy,
    canonical_sequence_sha256,
    reference_feature_statuses,
)
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.synthesis.construct import (
    generate_construct,
    prepare_reference_construct,
)
from test_construct_assembly import reference_inputs


def fixture(alphabet="DNA"):
    inputs = reference_inputs(alphabet)
    manifest, selection, _, _ = inputs
    request = prepare_reference_construct(*inputs)
    construct = generate_construct(request)
    placement = construct.placements[0]
    reference = manifest.record(selection.reference.id)
    record = MolecularRecord(
        id="cds-record",
        instance_id=placement.instance_id,
        molecule_id=placement.molecule_id,
        alphabet=reference.alphabet,
        artifact_class=reference.artifact_class,
        sequence=reference.sequence,
        sequence_sha256=reference.sequence_sha256,
        component=placement.component,
        reference_selection=selection,
        source_range=placement.source_range,
        molecule_range=placement.molecule_range,
        features=construct.features,
        feature_statuses=reference_feature_statuses(reference),
        orientation=placement.orientation,
        reading_frame=placement.reading_frame,
        completeness=reference.completeness,
        unknown_features=reference.unknown_features,
        evidence_relationships=reference.evidence_relationships,
        requirement_ids=placement.requirement_ids,
        source=placement.source,
    )
    return MolecularArtifact(
        request_fingerprint=request.fingerprint,
        construct_fingerprint=construct.fingerprint,
        layout_fingerprint=construct.layout_fingerprint,
        registry_lock=construct.registry_lock,
        profile=alphabet + "-CDS",
        records=(record,),
        source_request_fingerprint=request.source_request_fingerprint,
    )


class MolecularSchemaTests(unittest.TestCase):
    def test_dna_rna_roundtrip_pins_scope_reference_lineage_and_policies(self):
        for alphabet in ("DNA", "RNA"):
            with self.subTest(alphabet=alphabet):
                artifact = fixture(alphabet)
                self.assertEqual(
                    MolecularArtifact.from_json(artifact.to_json()), artifact
                )
                record = artifact.records[0]
                self.assertEqual(MolecularRecord.from_json(record.to_json()), record)
                self.assertEqual(artifact.profile, alphabet + "-CDS")
                self.assertEqual(artifact.artifact_scope, "exact_cds")
                self.assertEqual(record.completeness, "CDS-reference-only")
                self.assertEqual(record.reference, record.reference_selection.reference)
                self.assertEqual(record.length, 1491)
                self.assertEqual(record.source.line, 7)
                self.assertEqual(artifact.encoding_policy, EncodingPolicy())
                self.assertNotIn("accepted", artifact.to_dict())
                self.assertNotIn("passed", artifact.to_dict())

    def test_canonical_sequence_identity_excludes_wrapping_and_artifact_metadata(self):
        artifact = fixture()
        record = artifact.records[0]
        self.assertEqual(
            canonical_sequence_sha256(record.sequence, record.alphabet),
            record.sequence_sha256,
        )
        self.assertEqual(
            hashlib.sha256(record.sequence.encode("ascii")).hexdigest(),
            record.sequence_sha256,
        )
        changed = replace(artifact, request_fingerprint="0" * 64)
        self.assertNotEqual(artifact.fingerprint, changed.fingerprint)
        self.assertEqual(record.sequence_sha256, changed.records[0].sequence_sha256)
        compact = artifact.to_json(indent=None)
        expanded = artifact.to_json(indent=4)
        self.assertNotEqual(compact, expanded)
        self.assertEqual(
            MolecularArtifact.from_json(compact).fingerprint,
            MolecularArtifact.from_json(expanded).fingerprint,
        )

    def test_input_spelling_is_never_repaired_or_silently_transcribed(self):
        for alphabet, invalid in (
            ("DNA", "atgtaa"),
            ("DNA", "ATG TAA"),
            ("DNA", "ATGTAA\n"),
            ("DNA", "AUGUAA"),
            ("RNA", "ATGTAA"),
            ("DNA", "ATGNAA"),
            ("RNA", "AUGUАA"),  # Cyrillic A.
            ("DNA", ""),
            ("DNA", None),
            ("DNA", []),
            ("protein", "M*"),
        ):
            with (
                self.subTest(alphabet=alphabet, invalid=invalid),
                self.assertRaises(SerializationError),
            ):
                canonical_sequence_sha256(invalid, alphabet)
        record = fixture().records[0]
        with self.assertRaises(SerializationError):
            replace(record, sequence=record.sequence + "\n")

    def test_scoped_feature_statuses_preserve_every_reference_unknown(self):
        for alphabet in ("DNA", "RNA"):
            record = fixture(alphabet).records[0]
            statuses = {(s.scope, s.feature): s for s in record.feature_statuses}
            self.assertEqual(
                {s.feature for s in statuses.values() if s.status == "unknown"},
                set(record.unknown_features),
            )
            self.assertEqual(statuses[("delivered_molecule", "cap")].status, "unknown")
            self.assertEqual(statuses[("cds_record", "cap")].status, "inapplicable")
            self.assertIsNone(statuses[("delivered_molecule", "cap")].value)
            self.assertEqual(statuses[("cds_record", "reading-frame")].value, "0")
            self.assertEqual(
                statuses[("cds_record", "canonical-sequence-sha256")].value,
                record.sequence_sha256,
            )
            self.assertEqual(
                statuses[("cds_record", "domain-feature-coordinates")].status,
                "unknown",
            )
        for status, value in (
            ("known", None),
            ("unknown", "absent"),
            ("inapplicable", "no"),
        ):
            with self.subTest(status=status), self.assertRaises(SerializationError):
                FeatureStatus("cap", status, "cds_record", "Reason", value)

    def test_shape_validity_does_not_certify_semantic_candidate_claims(self):
        artifact = fixture()
        record = artifact.records[0]
        altered = replace(
            record,
            sequence_sha256="0" * 64,
            orientation="reverse",
            reading_frame=1,
            translation_policy=TranslationPolicy(genetic_code=2),
            source_range=SequenceRange(3, 1491),
        )
        candidate = replace(artifact, records=(altered,))
        self.assertEqual(MolecularArtifact.from_json(candidate.to_json()), candidate)
        self.assertNotEqual(artifact.fingerprint, candidate.fingerprint)

    def test_records_nested_lists_and_source_lineage_are_immutable(self):
        artifact = fixture()
        record = artifact.records[0]
        requirements = list(record.requirement_ids)
        statuses = list(record.feature_statuses)
        copied = replace(
            record, requirement_ids=requirements, feature_statuses=statuses
        )
        requirements.append("forged")
        statuses.clear()
        self.assertEqual(copied, record)
        with self.assertRaises(FrozenInstanceError):
            artifact.profile = "RNA-CDS"
        with self.assertRaises(FrozenInstanceError):
            record.reference_selection.reference.version = "other"
        mutable = artifact.to_dict()
        mutable["records"][0]["source"]["line"] = 999
        self.assertEqual(record.source.line, 7)

    def test_derived_nodes_and_lengths_cannot_be_forged(self):
        artifact = fixture()
        self.assertEqual(
            artifact.to_dict()["nodes"], [{"id": "cds", "kind": "cds_record"}]
        )
        for bad in ([], [{"id": "forged", "kind": "cds_record"}]):
            with self.subTest(nodes=bad), self.assertRaises(SerializationError):
                MolecularArtifact.from_dict(artifact.to_dict() | {"nodes": bad})
        for bad in (0, 1490, True, "1491", None):
            data = artifact.to_dict()
            data["records"][0]["length"] = bad
            with self.subTest(length=bad), self.assertRaises(SerializationError):
                MolecularArtifact.from_dict(data)

    def test_nested_import_shapes_raise_public_serialization_error(self):
        artifact = fixture()
        samples = (
            artifact,
            artifact.records[0],
            artifact.records[0].feature_statuses[0],
            TranslationPolicy(),
            EncodingPolicy(),
            EncodingEvidencePolicy(),
            EncodingChange(
                "change", "cds", "0" * 64, "1" * 64, ("sequence",), "Proposal"
            ),
        )
        for sample in samples:
            original = sample.to_dict()
            for key in original:
                for bad in (None, True, 1, [], {}):
                    if original[key] == bad:
                        continue
                    if key == "reading_frame" and type(bad) is int and bad in (0, 1, 2):
                        continue
                    if isinstance(original[key], list) and bad == []:
                        continue  # Empty inventories are an independent check.
                    if (
                        key in {"source_request_fingerprint", "source", "reading_frame"}
                        and bad is None
                    ):
                        continue
                    data = deepcopy(original)
                    data[key] = bad
                    with (
                        self.subTest(schema=type(sample).__name__, key=key, bad=bad),
                        self.assertRaises(SerializationError),
                    ):
                        type(sample).from_dict(data)
            for bad in (None, [], "bad", 1, True):
                with (
                    self.subTest(schema=type(sample).__name__, root=bad),
                    self.assertRaises(SerializationError),
                ):
                    type(sample).from_dict(bad)

    def test_unknown_keys_duplicate_json_and_duplicate_inventory_reject(self):
        artifact = fixture()
        for change in ({"accepted": True}, {"schema_version": "future"}):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                MolecularArtifact.from_dict(artifact.to_dict() | change)
        text = artifact.to_json(indent=None)
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON"):
            MolecularArtifact.from_json(text[:-1] + ',"records":[]}')
        with self.assertRaises(SerializationError):
            replace(artifact, records=artifact.records * 2)
        record = artifact.records[0]
        with self.assertRaises(SerializationError):
            replace(record, feature_statuses=record.feature_statuses * 2)

    def test_reference_policy_cannot_enable_unreviewed_optimization(self):
        for change in (
            {"mode": "synonymous"},
            {"optimization": "enabled"},
            {"transformations": ["T-to-U"]},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                EncodingPolicy.from_dict(EncodingPolicy().to_dict() | change)
        policy = EncodingEvidencePolicy()
        self.assertIn("behavior", policy.invalidated_analyses)
        self.assertIn("expression", policy.invalidated_analyses)
        for change in (
            {"semantic_properties": ["sequence"]},
            {"invalidated_analyses": []},
            {"invalidated_analyses": ["molecular"]},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                EncodingEvidencePolicy.from_dict(policy.to_dict() | change)
        artifact = fixture()
        record = artifact.records[0]
        proposal = EncodingChange(
            "future-proposal",
            record.id,
            record.sequence_sha256,
            "0" * 64,
            ("sequence",),
            "A future profile must check an explicit comparison contract",
            ("protein-preserved",),
        )
        changed = replace(artifact, changes=(proposal,))
        self.assertEqual(MolecularArtifact.from_json(changed.to_json()), changed)
        self.assertNotEqual(artifact.fingerprint, changed.fingerprint)
        self.assertEqual(changed.evidence_policy, artifact.evidence_policy)


if __name__ == "__main__":
    unittest.main()
