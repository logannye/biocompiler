"""Authority, relocation, deterministic identity and current package evidence."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.artifacts.archive import assemble_archive, read_archive
from biocompiler.artifacts.manifest import ReferenceBuildRequest, RunMetadata
from biocompiler.cli import main
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.compiler.reference import (
    build_reference_package,
    prepare_reference_build,
    publish_reference_package,
    verify_reference_package,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import fingerprint

REFERENCE = Path(__file__).resolve().parents[1] / "data/references/fap_car"


class ReferencePackageTests(unittest.TestCase):
    def setUp(self):
        self.request = prepare_reference_build("RNA", REFERENCE)

    def build(self, **kwargs):
        return build_reference_package(self.request, REFERENCE, **kwargs)

    def altered_package(self, package, path, mutate):
        manifest, files, metadata = read_archive(package.data)
        contents = dict(files)
        contents[path] = mutate(contents[path])
        entries = tuple(
            replace(
                entry,
                sha256=hashlib.sha256(contents[entry.path]).hexdigest(),
                byte_length=len(contents[entry.path]),
            )
            for entry in manifest.files
        )
        return assemble_archive(replace(manifest, files=entries), contents, metadata)

    def test_both_modalities_package_exact_scope_and_all_stage_evidence(self):
        for alphabet in ("DNA", "RNA"):
            request = prepare_reference_build(alphabet, REFERENCE)
            package = build_reference_package(request, REFERENCE)
            manifest, files, metadata = read_archive(package.data)
            self.assertIsNone(metadata)
            self.assertEqual(manifest.scope, "exact_cds")
            self.assertEqual(
                [item.stage for item in manifest.accepted_stages],
                ["components", "construct", "molecular"],
            )
            self.assertEqual(
                json.loads(files["molecular.json"])["profile"], alphabet + "-CDS"
            )
            summary = json.loads(files["result.json"])
            self.assertEqual(
                {item["id"] for item in summary["unresolved"]},
                {"complete_payload_features", "molecular_behavior"},
            )
            self.assertEqual(summary["model_locks"], [])
            self.assertIsNone(summary["upstream_intent"])
            self.assertEqual(
                verify_reference_package(package.data, expected_request=request).data,
                package.data,
            )

    def test_repeated_and_relocated_builds_have_identical_bytes(self):
        first = self.build()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "elsewhere"
            shutil.copytree(REFERENCE, copied)
            request = prepare_reference_build("RNA", copied)
            second = build_reference_package(request, copied)
            # Original directory is no longer an input to verification.
            shutil.rmtree(copied)
            restored = verify_reference_package(
                second.data, expected_build_fingerprint=first.build_fingerprint
            )
        self.assertEqual(first.request, request)
        self.assertEqual(first.data, second.data)
        self.assertEqual(first.data, restored.data)

    def test_run_metadata_changes_archive_but_not_canonical_build(self):
        first = self.build(
            run_metadata=RunMetadata(
                "2026-09-29T00:00:00Z", "machine-a", {"author": "/one/design.py"}
            )
        )
        second = self.build(
            run_metadata=RunMetadata(
                "2026-09-30T00:00:00Z", "machine-b", {"author": "/another/design.py"}
            )
        )
        self.assertEqual(first.build_fingerprint, second.build_fingerprint)
        self.assertNotEqual(first.data, second.data)
        self.assertNotEqual(first.archive_sha256, second.archive_sha256)
        self.assertEqual(
            verify_reference_package(
                second.data, expected_build_fingerprint=first.build_fingerprint
            ).data,
            second.data,
        )

    def test_file_format_policy_changes_build_identity_not_sequence_identity(self):
        first = self.build()
        second = build_reference_package(
            replace(self.request, fasta_line_width=60), REFERENCE
        )
        self.assertNotEqual(first.build_fingerprint, second.build_fingerprint)
        _, a, _ = read_archive(first.data)
        _, b, _ = read_archive(second.data)
        self.assertEqual(
            json.loads(a["molecular.json"])["records"][0]["sequence_sha256"],
            json.loads(b["molecular.json"])["records"][0]["sequence_sha256"],
        )

    def test_imported_pass_and_updated_file_hash_cannot_forge_acceptance(self):
        valid = self.build()
        for path in ("stages/molecular.json", "checks/molecular.json", "result.json"):

            def mutate(content):
                value = json.loads(content)
                if path == "result.json":
                    value["unresolved"] = []
                elif path.startswith("checks"):
                    value["dependencies"]["checker"] = "forged.v99"
                else:
                    value["dependencies"]["molecular_checker"] = fingerprint("forged")
                return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()

            altered = self.altered_package(valid, path, mutate)
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    SerializationError, "stale|altered|unsupported"
                ):
                    verify_reference_package(altered, expected_request=self.request)

    def test_sequence_edit_with_rehashed_inventory_fails_reconstruction(self):
        package = self.build()
        altered = self.altered_package(
            package, "sequence.fasta", lambda data: data.replace(b"AUG", b"ACG", 1)
        )
        with self.assertRaises(SerializationError):
            verify_reference_package(altered, expected_request=self.request)

    def test_current_tools_and_fresh_checks_are_required(self):
        package = self.build()
        with patch(
            "biocompiler.compiler.reference.MOLECULAR_CHECKER_VERSION", "changed.v2"
        ):
            with self.assertRaisesRegex(
                SerializationError, "stale|altered|unsupported"
            ):
                verify_reference_package(package.data, expected_request=self.request)
        with patch(
            "biocompiler.compiler.reference.run_molecular_pipeline",
            side_effect=PipelineError("fresh check rejected"),
        ):
            with self.assertRaisesRegex(PipelineError, "fresh check rejected"):
                verify_reference_package(package.data, expected_request=self.request)

    def test_distribution_version_is_pinned_and_rechecked(self):
        from biocompiler import __version__

        package = self.build()
        self.assertEqual(package.manifest.package_version, __version__)
        with patch("biocompiler.__version__", "0.1.0.dev999"):
            with self.assertRaisesRegex(
                SerializationError, "stale|altered|unsupported"
            ):
                verify_reference_package(package.data, expected_request=self.request)

    def test_verification_needs_independent_authority(self):
        package = self.build()
        with self.assertRaisesRegex(SerializationError, "independently trusted"):
            verify_reference_package(package.data)
        with self.assertRaisesRegex(
            SerializationError, "independently trusted identity"
        ):
            verify_reference_package(package.data, expected_build_fingerprint="0" * 64)
        dna = prepare_reference_build("DNA", REFERENCE)
        with self.assertRaisesRegex(SerializationError, "independent authority"):
            verify_reference_package(package.data, expected_request=dna)
        with self.assertRaisesRegex(SerializationError, "ReferenceBuildRequest"):
            build_reference_package(self.request.construct, REFERENCE)

    def test_failed_publication_preserves_previously_accepted_result(self):
        package = self.build()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "accepted.bcb"
            publish_reference_package(package, path)
            prior = path.read_bytes()
            bad = replace(
                package,
                data=self.altered_package(
                    package,
                    "sequence.fasta",
                    lambda data: data.replace(b"AUG", b"ACG", 1),
                ),
            )
            with self.assertRaises(SerializationError):
                publish_reference_package(bad, path)
            self.assertEqual(path.read_bytes(), prior)
            self.assertEqual(
                sorted(item.name for item in path.parent.iterdir()), ["accepted.bcb"]
            )

    def test_cli_build_inspect_verify_and_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reference.bcb"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "reference-build",
                            "--alphabet",
                            "RNA",
                            "--reference-dir",
                            str(REFERENCE),
                            "--output",
                            str(path),
                        ]
                    ),
                    0,
                )
            identity = json.loads(output.getvalue())["build_fingerprint"]
            for args, expected in (
                (["reference-inspect", str(path)], "Historical content"),
                (
                    ["reference-verify", str(path), "--expected-build", identity],
                    "fresh independent",
                ),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(args), 0)
                self.assertIn(expected, output.getvalue())
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(
                    main(["reference-verify", str(path), "--expected-build", "bad"]), 2
                )
            self.assertIn("identity", stderr.getvalue())
            self.assertEqual(path.read_bytes(), self.build().data)

    def test_request_roundtrip_is_authoritative(self):
        request = ReferenceBuildRequest.from_json(self.request.to_json())
        self.assertEqual(
            build_reference_package(request, REFERENCE).data, self.build().data
        )


if __name__ == "__main__":
    unittest.main()
