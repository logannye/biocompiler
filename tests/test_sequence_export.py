"""Export fidelity, current acceptance and distinct file/sequence identities."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biocompiler.artifacts.sequences import (
    SequenceExport,
    export_reference_sequence,
    verify_sequence_export,
)
from biocompiler.backends.reference import emit_reference_sequence
from biocompiler.errors import SerializationError
from biocompiler.ir.molecular import MolecularArtifact
from test_construct_checker import candidate_for, fixture


def export_fixture(alphabet="DNA", *, line_width=80):
    request, construct, registry, manifests = fixture(alphabet)
    artifact = emit_reference_sequence(request, construct, registry, manifests)
    bundle = export_reference_sequence(
        request, construct, artifact, registry, manifests, line_width=line_width
    )
    return request, construct, artifact, registry, manifests, bundle


class SequenceExportTests(unittest.TestCase):
    def test_fasta_and_json_roundtrip_preserve_identity_and_provenance(self):
        for alphabet in ("DNA", "RNA"):
            with self.subTest(alphabet=alphabet):
                _, _, artifact, _, _, bundle = export_fixture(alphabet)
                self.assertTrue(verify_sequence_export(bundle, artifact))
                self.assertEqual(
                    MolecularArtifact.from_json(bundle.specification), artifact
                )
                self.assertEqual(
                    bundle.sequence_sha256, artifact.records[0].sequence_sha256
                )
                self.assertEqual(
                    bundle.fasta_sha256, hashlib.sha256(bundle.fasta_bytes).hexdigest()
                )
                self.assertEqual(
                    bundle.specification_sha256,
                    hashlib.sha256(bundle.specification_bytes).hexdigest(),
                )
                self.assertNotEqual(bundle.sequence_sha256, bundle.fasta_sha256)
                self.assertEqual(
                    bundle.fasta.splitlines()[0],
                    f">{artifact.records[0].reference.id} alphabet={alphabet} scope=CDS-reference-only",
                )
                self.assertNotIn(
                    artifact.records[0].source.file, bundle.fasta.splitlines()[0]
                )
                self.assertIn(artifact.records[0].source.file, bundle.specification)
                self.assertTrue(
                    bundle.fasta.endswith("\n") and bundle.specification.endswith("\n")
                )
                self.assertNotIn("\r", bundle.fasta)

    def test_wrapping_changes_file_digest_but_never_canonical_sequence_identity(self):
        inputs = fixture()
        artifact = emit_reference_sequence(*inputs)
        request, construct, registry, manifests = inputs
        bundles = [
            export_reference_sequence(
                request, construct, artifact, registry, manifests, line_width=width
            )
            for width in (1, 60, 80)
        ]
        self.assertEqual(len({bundle.fasta_sha256 for bundle in bundles}), 3)
        self.assertEqual(len({bundle.sequence_sha256 for bundle in bundles}), 1)
        self.assertEqual(len({bundle.specification_sha256 for bundle in bundles}), 1)
        self.assertTrue(
            all(verify_sequence_export(bundle, artifact) for bundle in bundles)
        )
        for width in (0, -1, 10001, True, 1.5, "80"):
            with (
                self.subTest(width=width),
                self.assertRaisesRegex(SerializationError, "line width"),
            ):
                export_reference_sequence(
                    request, construct, artifact, registry, manifests, line_width=width
                )

    def test_file_bytes_can_be_saved_and_reloaded_without_platform_newline_changes(
        self,
    ):
        _, _, artifact, _, _, bundle = export_fixture("RNA")
        with tempfile.TemporaryDirectory() as directory:
            fasta = Path(directory) / "reference.fasta"
            specification = Path(directory) / "reference.json"
            fasta.write_bytes(bundle.fasta_bytes)
            specification.write_bytes(bundle.specification_bytes)
            reread = SequenceExport(
                fasta.read_bytes().decode("utf-8"),
                specification.read_bytes().decode("utf-8"),
                bundle.line_width,
                bundle.sequence_sha256,
                bundle.molecular_fingerprint,
            )
        self.assertEqual(reread, bundle)
        self.assertTrue(verify_sequence_export(reread, artifact))

    def test_altered_headers_additional_records_and_silent_normalization_are_rejected(
        self,
    ):
        _, _, artifact, _, _, bundle = export_fixture()
        header, sequence = bundle.fasta.split("\n", 1)
        corruptions = (
            header.replace("seq2", "seq3") + "\n" + sequence,
            header.replace("alphabet=DNA", "alphabet=RNA") + "\n" + sequence,
            header.replace("CDS-reference-only", "complete-payload") + "\n" + sequence,
            ">%FF alphabet=DNA scope=CDS-reference-only\n" + sequence,
            bundle.fasta + ">unexpected\nACGT\n",
            bundle.fasta.replace("\n", "\r\n"),
            header + "\n" + sequence.lower(),
            header + "\n " + sequence,
            bundle.fasta + "\n",
            bundle.fasta[:-1],
        )
        for text in corruptions:
            with (
                self.subTest(header=text.splitlines()[0]),
                self.assertRaises(SerializationError),
            ):
                verify_sequence_export(replace(bundle, fasta=text), artifact)

    def test_changed_json_or_forged_sequence_identity_is_not_a_valid_roundtrip(self):
        _, _, artifact, _, _, bundle = export_fixture()
        changed = artifact.to_dict()
        changed["records"][0]["source"]["file"] = "another_request.py"
        for mutation in (
            {"specification": json.dumps(changed) + "\n"},
            {
                "specification": bundle.specification.replace(
                    '"schema_version":',
                    '"schema_version": "duplicate", "schema_version":',
                    1,
                )
            },
            {"sequence_sha256": "0" * 64},
            {"molecular_fingerprint": "0" * 64},
            {"line_width": 60},
        ):
            with (
                self.subTest(mutation=tuple(mutation)),
                self.assertRaises(SerializationError),
            ):
                verify_sequence_export(replace(bundle, **mutation), artifact)

    def test_export_rechecks_current_inputs_and_rejects_a_self_rehashed_mutation(self):
        request, construct, artifact, registry, manifests, _ = export_fixture()
        record = artifact.records[0]
        substituted = ("C" if record.sequence[0] != "C" else "G") + record.sequence[1:]
        changed = replace(
            artifact,
            records=(
                replace(
                    record,
                    sequence=substituted,
                    sequence_sha256=hashlib.sha256(
                        substituted.encode("ascii")
                    ).hexdigest(),
                ),
            ),
        )
        for current_artifact, current_registry, current_manifests in (
            (changed, registry, manifests),
            (artifact, replace(registry, version="2"), manifests),
            (artifact, registry, {}),
        ):
            with (
                self.subTest(artifact=current_artifact.fingerprint),
                self.assertRaisesRegex(
                    SerializationError, "independent molecular check"
                ),
            ):
                export_reference_sequence(
                    request,
                    construct,
                    current_artifact,
                    current_registry,
                    current_manifests,
                )

    def test_user_molecule_names_cannot_inject_a_fasta_header_or_local_path(self):
        request, _, registry, manifests = fixture()
        unusual_id = "local/folder\n>injected record"
        request = replace(
            request,
            molecules=(replace(request.molecules[0], id=unusual_id),),
            placements=(replace(request.placements[0], molecule_id=unusual_id),),
        )
        construct = candidate_for(request)
        artifact = emit_reference_sequence(request, construct, registry, manifests)
        bundle = export_reference_sequence(
            request, construct, artifact, registry, manifests
        )
        self.assertNotIn("local/folder", bundle.fasta)
        self.assertEqual(bundle.fasta.count(">"), 1)
        self.assertTrue(verify_sequence_export(bundle, artifact))
        self.assertEqual(
            MolecularArtifact.from_json(bundle.specification).records[0].molecule_id,
            unusual_id,
        )

    def test_repeated_export_has_identical_text_and_file_digests(self):
        request, construct, artifact, registry, manifests, first = export_fixture()
        second = export_reference_sequence(
            request, construct, artifact, registry, manifests
        )
        self.assertEqual(first, second)
        self.assertEqual(first.fasta_sha256, second.fasta_sha256)
        self.assertEqual(first.specification_sha256, second.specification_sha256)


if __name__ == "__main__":
    unittest.main()
