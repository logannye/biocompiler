"""Pinned reference build inputs are offline, bounded and relocation independent."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from cellweave.errors import SerializationError
from cellweave.registry.reference_builds import (
    MANIFEST_PIN,
    REFERENCE_PINS,
    collect_reference_files,
    load_reference_inputs,
)
from cellweave.registry.references import ReferenceManifest

REFERENCE_DIRECTORY = Path(__file__).resolve().parents[1] / "data/references/fap_car"


class ReferenceBuildInputsTests(unittest.TestCase):
    def test_dna_and_rna_match_reviewed_pins_without_network_or_authoring(self):
        for alphabet in ("DNA", "RNA"):
            with (
                self.subTest(alphabet=alphabet),
                patch(
                    "socket.create_connection",
                    side_effect=AssertionError("network forbidden"),
                ),
                patch(
                    "runpy.run_path", side_effect=AssertionError("authoring forbidden")
                ),
            ):
                request, manifest, registry = load_reference_inputs(
                    alphabet, REFERENCE_DIRECTORY
                )
            self.assertEqual(manifest.fingerprint, MANIFEST_PIN.content_fingerprint)
            self.assertEqual(
                request.references[0].selection.reference, REFERENCE_PINS[alphabet]
            )
            self.assertEqual(request.target.payload_format.value, alphabet)
            self.assertEqual(
                registry.resolve(request.registry_lock)["fap_cds"].classification,
                "sequence_reference",
            )
            self.assertEqual(request.molecules[0].length, 1491)
            self.assertEqual(request.molecules[0].completeness, "CDS-reference-only")
            self.assertEqual(
                request.source_request_fingerprint, request.composition.fingerprint
            )

    def test_copied_directory_reproduces_request_registry_and_retained_bytes(self):
        original = load_reference_inputs("DNA", REFERENCE_DIRECTORY)
        expected_files = collect_reference_files(REFERENCE_DIRECTORY, original[1])
        with tempfile.TemporaryDirectory() as temporary:
            relocated = Path(temporary) / "relocated"
            shutil.copytree(REFERENCE_DIRECTORY, relocated)
            (relocated / "author.py").write_text(
                "raise AssertionError('must not execute')\n", encoding="utf-8"
            )
            (relocated / "unrelated.txt").write_text(
                "not part of reference evidence", encoding="utf-8"
            )
            copied = load_reference_inputs("DNA", relocated)
            actual_files = collect_reference_files(relocated, copied[1])
        self.assertEqual(
            tuple(item.fingerprint for item in original),
            tuple(item.fingerprint for item in copied),
        )
        self.assertEqual(actual_files, expected_files)
        self.assertEqual(
            set(actual_files),
            {"manifest.json", "source-excerpts.html", "independent-audit.json"},
        )

    def test_manifest_formatting_is_canonical_but_source_and_review_bytes_are_exact(
        self,
    ):
        _, manifest, _ = load_reference_inputs("RNA", REFERENCE_DIRECTORY)
        expected = collect_reference_files(REFERENCE_DIRECTORY, manifest)
        with tempfile.TemporaryDirectory() as temporary:
            relocated = Path(temporary) / "reference"
            shutil.copytree(REFERENCE_DIRECTORY, relocated)
            (relocated / "manifest.json").write_text(
                json.dumps(manifest.to_dict(), separators=(",", ":")), encoding="utf-8"
            )
            _, copied, _ = load_reference_inputs("RNA", relocated)
            actual = collect_reference_files(relocated, copied)
        self.assertEqual(actual, expected)
        self.assertEqual(actual["manifest.json"], manifest.to_json().encode("utf-8"))
        for path in ("source-excerpts.html", "independent-audit.json"):
            self.assertEqual(actual[path], (REFERENCE_DIRECTORY / path).read_bytes())

    def test_tampered_source_review_or_manifest_cannot_be_loaded_or_packaged(self):
        _, original, _ = load_reference_inputs("DNA", REFERENCE_DIRECTORY)
        for path in ("source-excerpts.html", "independent-audit.json", "manifest.json"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "reference"
                shutil.copytree(REFERENCE_DIRECTORY, destination)
                selected = destination / path
                if path == "manifest.json":
                    changed = original.to_dict()
                    changed["redistribution"]["note"] += " edited"
                    selected.write_text(json.dumps(changed), encoding="utf-8")
                else:
                    selected.write_bytes(selected.read_bytes() + b"tampered")
                with self.assertRaises(SerializationError):
                    load_reference_inputs("DNA", destination)
                with self.assertRaises(SerializationError):
                    collect_reference_files(destination, original)

    def test_valid_but_unreviewed_manifest_and_caller_manifest_substitution_fail(self):
        _, original, _ = load_reference_inputs("DNA", REFERENCE_DIRECTORY)
        changed = original.to_dict()
        changed["redistribution"]["note"] += " alternate unreviewed metadata"
        different = ReferenceManifest.from_dict(changed)
        self.assertNotEqual(original.fingerprint, different.fingerprint)
        with self.assertRaisesRegex(SerializationError, "Supplied manifest"):
            collect_reference_files(REFERENCE_DIRECTORY, different)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "reference"
            shutil.copytree(REFERENCE_DIRECTORY, destination)
            (destination / "manifest.json").write_text(
                different.to_json(), encoding="utf-8"
            )
            with self.assertRaisesRegex(SerializationError, "reviewed pin"):
                load_reference_inputs("DNA", destination)

    def test_unknown_modality_and_missing_directory_fail_explicitly(self):
        for alphabet in ("protein", "dna", "mRNA", "complete_payload", None, [], 1):
            with self.subTest(alphabet=alphabet), self.assertRaises(SerializationError):
                load_reference_inputs(alphabet, REFERENCE_DIRECTORY)
        for directory in (None, "", [], REFERENCE_DIRECTORY / "absent"):
            with (
                self.subTest(directory=directory),
                self.assertRaises(SerializationError),
            ):
                load_reference_inputs("DNA", directory)
        with self.assertRaises(TypeError):
            REFERENCE_PINS["DNA"] = REFERENCE_PINS["RNA"]

    def test_manifest_source_and_review_symlinks_are_rejected_inside_or_outside_root(
        self,
    ):
        _, original, _ = load_reference_inputs("DNA", REFERENCE_DIRECTORY)
        for name in ("manifest.json", "source-excerpts.html", "independent-audit.json"):
            for outside in (False, True):
                with (
                    self.subTest(name=name, outside=outside),
                    tempfile.TemporaryDirectory() as temporary,
                ):
                    destination = Path(temporary) / "reference"
                    shutil.copytree(REFERENCE_DIRECTORY, destination)
                    selected = destination / name
                    target = (
                        Path(temporary) if outside else destination
                    ) / "target.bin"
                    target.write_bytes(selected.read_bytes())
                    selected.unlink()
                    selected.symlink_to(target)
                    with self.assertRaisesRegex(SerializationError, "symlink"):
                        load_reference_inputs("DNA", destination)
                    with self.assertRaisesRegex(SerializationError, "symlink"):
                        collect_reference_files(destination, original)

    def test_bounded_reads_and_missing_evidence_fail_before_acceptance(self):
        with patch("cellweave.registry.reference_builds.MAX_REFERENCE_FILE_BYTES", 1):
            with self.assertRaisesRegex(SerializationError, "bounded"):
                load_reference_inputs("DNA", REFERENCE_DIRECTORY)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "reference"
            shutil.copytree(REFERENCE_DIRECTORY, destination)
            (destination / "independent-audit.json").unlink()
            with self.assertRaises(SerializationError):
                load_reference_inputs("DNA", destination)


if __name__ == "__main__":
    unittest.main()
