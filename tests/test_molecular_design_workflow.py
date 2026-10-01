"""Public complete-specification workflows preserve authority and claim scope."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.artifacts.archive import read_archive
from biocompiler.cli import main
from examples.molecular_design import (
    ALTERNATIVE_EXPECTED,
    EXPECTED,
    prepare_design_request,
    run_design,
)


class MolecularDesignWorkflowTests(unittest.TestCase):
    def call(self, arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main([str(value) for value in arguments])
        return (
            code,
            json.loads(output.getvalue()) if output.getvalue() else None,
            errors.getvalue(),
        )

    def test_example_emits_two_authorized_specs_and_retains_synonymous_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with redirect_stdout(io.StringIO()):
                run_design(root)
            molecules = []
            packages = []
            for name, request_name, expected in (
                ("design.bcb", "request.json", EXPECTED),
                ("alternative.bcb", "alternative-request.json", ALTERNATIVE_EXPECTED),
            ):
                request = bc.MolecularDesignRequest.from_json(
                    (root / request_name).read_text()
                )
                package = bc.verify_molecular_design_package(
                    (root / name).read_bytes(), expected_request=request
                )
                manifest, files, _ = read_archive(package.data)
                artifact = bc.MolecularDesignArtifact.from_json(
                    files["candidate.json"].decode()
                )
                self.assertEqual(artifact.molecule.sequence, expected)
                self.assertEqual(manifest.scope, "software_molecular_design")
                self.assertEqual(len(artifact.molecule.regions), 4)
                self.assertNotEqual(
                    artifact.source_maps[0].source_range,
                    artifact.source_maps[0].molecule_range,
                )
                self.assertEqual(artifact.molecule.regions[1].protein_sequence, "MA*")
                molecules.append(artifact.molecule)
                packages.append(package)
            self.assertNotEqual(
                packages[0].build_fingerprint, packages[1].build_fingerprint
            )
            self.assertNotEqual(
                molecules[0].sequence_sha256, molecules[1].sequence_sha256
            )
            failure = bc.MolecularDesignResult.from_json(
                (root / "substitution-failure.json").read_text()
            )
            self.assertEqual(failure.outcome, bc.CheckOutcome.FAIL)
            code, summary, error = self.call(
                ["inspect", root / "substitution-failure.json"]
            )
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(summary["outcome"], "fail")
            self.assertIn("Historical", summary["inspection"])
            self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")

    def test_cli_build_inspect_and_verify_with_both_authority_forms(self):
        request = prepare_design_request()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, archive = root / "request.json", root / "design.bcb"
            authority.write_text(request.to_json())
            code, built, error = self.call(
                ["molecular-design-build", "--request", authority, "--output", archive]
            )
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(built["scope"], "software_molecular_design")
            for arguments in (
                ["molecular-design-inspect", archive],
                ["molecular-design-verify", archive, "--expected-request", authority],
                [
                    "molecular-design-verify",
                    archive,
                    "--expected-build",
                    built["build_fingerprint"],
                ],
            ):
                with self.subTest(arguments=arguments):
                    code, summary, error = self.call(arguments)
                    self.assertEqual((code, error), (0, ""))
                    self.assertEqual(
                        summary["build_fingerprint"], built["build_fingerprint"]
                    )
                    self.assertEqual(summary["evidence_boundary"], "software_fixture")
                    self.assertEqual(
                        summary["human_therapeutic_admission"], "not_admitted"
                    )
            _, files, _ = read_archive(archive.read_bytes())
            for name in (
                "handoff.json",
                "candidate.json",
                "construct.json",
                "checks/molecular.json",
            ):
                path = root / Path(name).name
                path.write_bytes(files[name])
                code, summary, error = self.call(["inspect", path])
                self.assertEqual((code, error), (0, ""))
                self.assertIn("Historical", summary["inspection"])
                code, document, error = self.call(["inspect", path, "--json"])
                self.assertEqual((code, error), (0, ""))
                self.assertEqual(document, json.loads(files[name]))

    def test_unknown_chemistry_cannot_publish_or_replace_existing_output(self):
        request = prepare_design_request()
        unknown = replace(
            request,
            features=tuple(
                replace(item, status="unknown", value=None)
                if item.feature == "cap"
                else item
                for item in request.features
            ),
        )
        result = bc.check_molecular_design_request(
            unknown, expected_request_fingerprint=unknown.fingerprint
        )
        self.assertFalse(result.passed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, archive = root / "request.json", root / "design.bcb"
            authority.write_text(unknown.to_json())
            archive.write_bytes(b"previous complete user output")
            code, summary, error = self.call(
                ["molecular-design-build", "--request", authority, "--output", archive]
            )
            self.assertEqual(code, 2)
            self.assertIsNone(summary)
            self.assertTrue(error)
            self.assertEqual(archive.read_bytes(), b"previous complete user output")
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["design.bcb", "request.json"],
            )

    def test_cli_preserves_independent_request_and_run_metadata(self):
        request = prepare_design_request()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, metadata = root / "request.json", root / "run.json"
            authority.write_text(request.to_json())
            metadata.write_text("a user metadata file")
            for destination in (authority, metadata):
                original = destination.read_bytes()
                code, _, error = self.call(
                    [
                        "molecular-design-build",
                        "--request",
                        authority,
                        "--run-metadata",
                        metadata,
                        "--output",
                        destination,
                    ]
                )
                self.assertEqual(code, 2)
                self.assertIn("input authority", error)
                self.assertEqual(destination.read_bytes(), original)

    def test_cli_rejects_alternative_request_and_incorrect_build_authority(self):
        request = prepare_design_request()
        package = bc.build_molecular_design_package(request)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, authority = root / "design.bcb", root / "alternative.json"
            archive.write_bytes(package.data)
            authority.write_text(prepare_design_request(alternative=True).to_json())
            for arguments in (
                ["molecular-design-verify", archive, "--expected-request", authority],
                ["molecular-design-verify", archive, "--expected-build", "0" * 64],
                ["synthetic-inspect", archive],
            ):
                code, summary, error = self.call(arguments)
                self.assertEqual(code, 2)
                self.assertIsNone(summary)
                self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
