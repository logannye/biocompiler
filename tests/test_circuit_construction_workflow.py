"""Public supplied-construction workflows using tiny artificial software controls."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.ir.molecule_records import MAX_MOLECULE_JSON_BYTES
from test_circuit_construction_checking import fixture_request


def invoke(*arguments):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(list(map(str, arguments)))
    return code, stdout.getvalue(), stderr.getvalue()


class CircuitConstructionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = fixture_request()
        cls.build = bc.build_circuit_construction(cls.request)

    def files(self, directory, *, request=None, build=None):
        source = Path(directory) / "request.json"
        retained = Path(directory) / "build.json"
        source.write_text((request or self.request).to_json() + "\n", encoding="utf-8")
        retained.write_text((build or self.build).to_json() + "\n", encoding="utf-8")
        return source, retained

    def forged_build(self):
        # Rehash every identity an attacker controls, including the saved PASS.
        value = replace(self.build.candidate.values[0], sequence="CCCCCC")
        candidate = replace(self.build.candidate, values=(value,))
        assessment = replace(
            self.build.assessment,
            candidate_fingerprint=candidate.fingerprint,
            reconstructed_fingerprint=candidate.fingerprint,
        )
        return replace(self.build, candidate=candidate, assessment=assessment)

    def test_public_compile_roundtrip_and_complete_handoff_preserve_scope(self):
        build = bc.compile(self.request)
        self.assertEqual(build, self.build)
        restored = bc.CircuitConstructionBuild.from_json(build.to_json() + "\n")
        self.assertEqual(restored, build)
        self.assertEqual(
            bc.verify_circuit_construction(restored, expected_request=self.request),
            build.assessment,
        )
        molecules = bc.verified_circuit_molecules(
            restored, expected_request=self.request
        )
        self.assertEqual(molecules.bundle, build.candidate.bundle)
        self.assertEqual(molecules.bundle.request, self.request.circuit)
        self.assertEqual(
            molecules.experimental_amounts, build.candidate.experimental_amounts
        )
        self.assertEqual(molecules.bundle.molecules[0].sequence, "ACGUAC")
        self.assertTrue(build.assessment.complete)
        self.assertEqual(build.assessment.biological_function, "unestablished")
        self.assertEqual(build.assessment.empirical_validation, "unknown")
        self.assertEqual(build.assessment.human_therapeutic_admission, "not_admitted")

    def test_replay_and_handoff_do_not_call_the_producer(self):
        with patch(
            "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError(
                "fresh verification must use the independent checker"
            ),
        ):
            self.assertTrue(
                bc.verify_circuit_construction(
                    self.build, expected_request=self.request
                ).passed
            )
            self.assertIsInstance(
                bc.verified_circuit_molecules(
                    self.build, expected_request=self.request
                ),
                bc.CircuitMoleculeRecord,
            )

    def test_external_authority_is_required_and_must_be_typed(self):
        with self.assertRaises(TypeError):
            bc.verify_circuit_construction(self.build)
        for authority in (None, self.request.to_dict(), self.request.circuit):
            with self.subTest(authority=type(authority).__name__):
                with self.assertRaisesRegex(
                    bc.SerializationError, "independent complete"
                ):
                    bc.verify_circuit_construction(
                        self.build, expected_request=authority
                    )

    def test_changed_complete_external_authority_invalidates_old_build(self):
        source = self.request.sources[0]
        requirement = self.request.requirements[0]
        changes = (
            replace(self.request, mode="diagnostic"),
            replace(
                self.request,
                sources=(
                    replace(
                        source, molecule=replace(source.molecule, sequence="CCCCCC")
                    ),
                ),
            ),
            replace(
                self.request,
                circuit=replace(
                    self.request.circuit,
                    profile=replace(self.request.circuit.profile, boundary="export"),
                ),
            ),
            replace(
                self.request,
                requirements=(
                    replace(
                        requirement,
                        roles=(replace(requirement.roles[0], role="changed-role"),),
                    ),
                ),
            ),
            replace(self.request, payload_structures=()),
        )
        for authority in changes:
            with self.subTest(authority=authority.fingerprint):
                for operation in (
                    bc.verify_circuit_construction,
                    bc.verified_circuit_molecules,
                ):
                    with self.assertRaisesRegex(
                        bc.SerializationError, "independent complete authority"
                    ):
                        operation(self.build, expected_request=authority)

    def test_rehashed_tampering_cannot_reuse_a_historical_pass(self):
        forged = self.forged_build()
        self.assertTrue(forged.assessment.passed)
        self.assertEqual(
            forged.candidate.fingerprint, forged.assessment.candidate_fingerprint
        )
        for operation in (
            bc.verify_circuit_construction,
            bc.verified_circuit_molecules,
        ):
            with self.assertRaisesRegex(bc.SerializationError, "fresh complete replay"):
                operation(forged, expected_request=self.request)

    def test_fresh_failed_assessment_is_verifiable_but_cannot_be_handed_off(self):
        candidate = self.forged_build().candidate
        assessment = bc.check_circuit_construction(
            candidate, expected_request=self.request
        )
        build = replace(self.build, candidate=candidate, assessment=assessment)
        self.assertEqual(
            bc.verify_circuit_construction(build, expected_request=self.request),
            assessment,
        )
        self.assertFalse(assessment.passed)
        with self.assertRaisesRegex(bc.SerializationError, "fresh successful"):
            bc.verified_circuit_molecules(build, expected_request=self.request)

    def test_stale_checker_capability_construction_and_policy_versions_are_rejected(
        self,
    ):
        for field in (
            "checker_version",
            "capability_version",
            "construction_profile",
            "admission_policy",
        ):
            with self.subTest(field=field):
                document = self.build.to_dict()
                document["assessment"][field] = "historical-v0"
                with self.assertRaisesRegex(bc.SerializationError, "current checker"):
                    bc.CircuitConstructionBuild.from_dict(document)

    def test_diagnostic_pass_does_not_enable_complete_set_handoff(self):
        request = replace(self.request, mode="diagnostic")
        build = bc.build_circuit_construction(request)
        self.assertTrue(
            bc.verify_circuit_construction(build, expected_request=request).passed
        )
        with self.assertRaisesRegex(bc.SerializationError, "Diagnostic construction"):
            bc.verified_circuit_molecules(build, expected_request=request)

    def test_unresolved_strict_build_retains_diagnostics_and_rejects_handoff(self):
        request = replace(self.request, payload_structures=())
        build = bc.build_circuit_construction(request)
        self.assertFalse(build.assessment.passed)
        self.assertFalse(build.assessment.complete)
        self.assertIsNotNone(build.candidate.bundle)
        self.assertTrue(
            any(
                "payload_authority_missing" in item
                for item in build.assessment.diagnostics
            )
        )
        self.assertEqual(
            bc.verify_circuit_construction(build, expected_request=request),
            build.assessment,
        )
        with self.assertRaisesRegex(bc.SerializationError, "fresh successful"):
            bc.verified_circuit_molecules(build, expected_request=request)

    def test_cli_build_verify_export_and_inspect_retain_full_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            source, retained = self.files(directory)
            retained.unlink()
            output = Path(directory) / "export.json"
            for arguments in (
                ("circuit-build", "--request", source, "--output", retained),
                ("circuit-verify", retained, "--expected-request", source),
                (
                    "circuit-export",
                    retained,
                    "--expected-request",
                    source,
                    "--output",
                    output,
                ),
            ):
                code, stdout, stderr = invoke(*arguments)
                self.assertEqual((code, stderr), (0, ""))
                summary = json.loads(stdout)
                self.assertEqual(summary["outcome"], "pass")
                self.assertEqual(
                    summary["scope"], "supplied_construction_correspondence"
                )
                self.assertEqual(summary["source_fidelity"], "unestablished")
                self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
            self.assertEqual(output.read_bytes(), retained.read_bytes())
            exported = bc.CircuitConstructionBuild.from_json(output.read_text())
            self.assertEqual(exported.request, self.request)
            self.assertEqual(exported.candidate, self.build.candidate)
            for artifact in (
                self.request,
                self.build.candidate,
                self.build.assessment,
                exported,
            ):
                path = Path(directory) / "inspection.json"
                path.write_text(artifact.to_json(), encoding="utf-8")
                code, stdout, stderr = invoke("inspect", path)
                self.assertEqual((code, stderr), (0, ""))
                self.assertIn(
                    "independent complete construction authority",
                    json.loads(stdout)["inspection"],
                )

    def test_cli_nonpassing_strict_and_diagnostic_builds_cannot_export(self):
        for request in (
            replace(self.request, payload_structures=()),
            replace(self.request, mode="diagnostic"),
        ):
            with (
                self.subTest(mode=request.mode),
                tempfile.TemporaryDirectory() as directory,
            ):
                source, retained = self.files(directory, request=request)
                output = Path(directory) / "export.json"
                expected_code = 0 if request.mode == "diagnostic" else 1
                self.assertEqual(
                    invoke("circuit-build", "--request", source, "--output", retained)[
                        0
                    ],
                    expected_code,
                )
                self.assertEqual(
                    invoke("circuit-verify", retained, "--expected-request", source)[0],
                    expected_code,
                )
                code, stdout, stderr = invoke(
                    "circuit-export",
                    retained,
                    "--expected-request",
                    source,
                    "--output",
                    output,
                )
                self.assertEqual((code, stdout), (2, ""))
                self.assertTrue(stderr)
                self.assertFalse(output.exists())

    def test_cli_rehashed_pass_and_changed_authority_cannot_publish(self):
        cases = (
            (self.request, self.forged_build()),
            (replace(self.request, mode="diagnostic"), self.build),
        )
        for request, build in cases:
            with (
                self.subTest(request=request.fingerprint),
                tempfile.TemporaryDirectory() as directory,
            ):
                source, retained = self.files(directory, request=request, build=build)
                output = Path(directory) / "export.json"
                output.write_bytes(b"preserve previous output")
                self.assertEqual(
                    invoke("circuit-verify", retained, "--expected-request", source)[0],
                    2,
                )
                self.assertEqual(
                    invoke(
                        "circuit-export",
                        retained,
                        "--expected-request",
                        source,
                        "--output",
                        output,
                    )[0],
                    2,
                )
                self.assertEqual(output.read_bytes(), b"preserve previous output")

    def test_cli_requires_explicit_external_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            _, retained = self.files(directory)
            for operation in ("circuit-verify", "circuit-export"):
                with self.subTest(operation=operation), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        main([operation, str(retained)])
                    self.assertEqual(error.exception.code, 2)

    def test_cli_build_and_export_input_collisions_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source, retained = self.files(directory)
            originals = {path: path.read_bytes() for path in (source, retained)}
            for target in (source, retained):
                alias = Path(directory) / "alias.json"
                alias.symlink_to(target)
                for destination in (target, alias):
                    if target == source:
                        self.assertEqual(
                            invoke(
                                "circuit-build",
                                "--request",
                                source,
                                "--output",
                                destination,
                            )[0],
                            2,
                        )
                    self.assertEqual(
                        invoke(
                            "circuit-export",
                            retained,
                            "--expected-request",
                            source,
                            "--output",
                            destination,
                        )[0],
                        2,
                    )
                    self.assertEqual(
                        {path: path.read_bytes() for path in originals}, originals
                    )
                alias.unlink()

    def test_cli_export_does_not_follow_unrelated_output_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            source, retained = self.files(directory)
            unrelated = Path(directory) / "unrelated.json"
            unrelated.write_bytes(b"unrelated content")
            output = Path(directory) / "export.json"
            output.symlink_to(unrelated)
            self.assertEqual(
                invoke(
                    "circuit-export",
                    retained,
                    "--expected-request",
                    source,
                    "--output",
                    output,
                )[0],
                2,
            )
            self.assertEqual(unrelated.read_bytes(), b"unrelated content")
            self.assertTrue(output.is_symlink())

    def test_atomic_publication_failure_preserves_existing_destination_and_cleans_temp(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            source, retained = self.files(directory)
            output = Path(directory) / "output.json"
            for operation in ("circuit-build", "circuit-export"):
                arguments = (
                    (operation, "--request", source, "--output", output)
                    if operation == "circuit-build"
                    else (
                        operation,
                        retained,
                        "--expected-request",
                        source,
                        "--output",
                        output,
                    )
                )
                for failure in ("fsync", "replace"):
                    with self.subTest(operation=operation, failure=failure):
                        output.write_bytes(b"previous complete artifact")
                        with patch(
                            "biocompiler.cli.os." + failure,
                            side_effect=OSError("injected publication failure"),
                        ):
                            code, stdout, stderr = invoke(*arguments)
                        self.assertEqual((code, stdout), (2, ""))
                        self.assertIn("injected publication failure", stderr)
                        self.assertEqual(
                            output.read_bytes(), b"previous complete artifact"
                        )
                        self.assertEqual(list(Path(directory).glob(".*.tmp")), [])

    def test_cli_invalid_and_oversized_requests_never_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _ = self.files(directory)
            output = Path(directory) / "output.json"
            invalid = (
                "{bad json",
                json.dumps(
                    self.request.to_dict() | {"empirical_validation": "verified"}
                ),
                self.request.to_json() + " " * MAX_MOLECULE_JSON_BYTES,
            )
            for text in invalid:
                with self.subTest(length=len(text)):
                    source.write_text(text, encoding="utf-8")
                    code, stdout, stderr = invoke(
                        "circuit-build", "--request", source, "--output", output
                    )
                    self.assertEqual((code, stdout), (2, ""))
                    self.assertTrue(stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
