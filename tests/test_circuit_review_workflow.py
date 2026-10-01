"""Public review workflows preserve external authority across relocation."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.artifacts.circuit_review import REVIEW_PACKAGE_VERSION
from biocompiler.cli import _read_artifact, main
from examples.circuit_review import make_review_records


def invoke(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, arguments)))
    return code, out.getvalue(), err.getvalue()


class CircuitReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build, cls.authority, cls.records = make_review_records()

    def files(self, directory):
        paths = {}
        for name, value in {
            "build": self.build,
            "authority": self.authority,
            **self.records,
        }.items():
            paths[name] = Path(directory) / (name + ".json")
            paths[name].write_text(value.to_json() + "\n", encoding="utf-8")
        return paths

    def create(self, paths, destination):
        arguments = [
            "circuit-review-create",
            paths["build"],
            "--expected-authority",
            paths["authority"],
            "--output",
            destination,
        ]
        for name in self.records:
            arguments.extend(["--" + name.replace("_", "-"), paths[name]])
        return invoke(*arguments)

    def test_public_api_and_authority_generic_inspection(self):
        self.assertEqual(REVIEW_PACKAGE_VERSION, bc.__version__)
        self.assertEqual(_read_artifact(self.authority.to_json()), self.authority)
        self.assertEqual(
            bc.CircuitReviewAuthority.from_json(self.authority.to_json()),
            self.authority,
        )
        for name in (
            "CircuitReviewAuthority",
            "CircuitReviewManifest",
            "CircuitReviewBundle",
            "create_circuit_review_bundle",
            "publish_circuit_review_bundle",
            "inspect_circuit_review_bundle",
            "verify_circuit_review_bundle",
        ):
            self.assertIn(name, bc.__all__)

    def test_cli_create_inspect_relocate_and_fresh_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            archive = Path(directory) / "review.bcb"
            code, out, err = self.create(paths, archive)
            self.assertEqual(code, 0, err)
            expected = json.loads(out)
            moved = Path(directory) / "relocated"
            moved.mkdir()
            relocated = archive.rename(moved / archive.name)
            report = moved / "inspection.json"
            code, out, err = invoke(
                "circuit-review-inspect", relocated, "--output", report
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out), json.loads(report.read_text()))
            code, out, err = invoke(
                "circuit-review-verify",
                relocated,
                "--expected-authority",
                paths["authority"],
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out), expected)

    def test_wrong_external_authority_cannot_publish_report(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            archive = Path(directory) / "review.bcb"
            self.assertEqual(self.create(paths, archive)[0], 0)
            wrong = replace(
                self.authority, sources=replace(self.authority.sources, version="2")
            )
            paths["authority"].write_text(wrong.to_json(), encoding="utf-8")
            report = Path(directory) / "verification.json"
            report.write_text("preserve previous report", encoding="utf-8")
            code, _, _ = invoke(
                "circuit-review-verify",
                archive,
                "--expected-authority",
                paths["authority"],
                "--output",
                report,
            )
            self.assertEqual(code, 2)
            self.assertEqual(report.read_text(), "preserve previous report")

    def test_create_refuses_missing_assessments_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            archive = Path(directory) / "review.bcb"
            code, _, _ = invoke(
                "circuit-review-create",
                paths["build"],
                "--expected-authority",
                paths["authority"],
                "--output",
                archive,
            )
            self.assertEqual(code, 2)
            self.assertFalse(archive.exists())
            before = paths["authority"].read_bytes()
            code, _, _ = self.create(paths, paths["authority"])
            self.assertEqual(code, 2)
            self.assertEqual(paths["authority"].read_bytes(), before)

    def test_report_cannot_overwrite_archive_or_external_authority_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            archive = Path(directory) / "review.bcb"
            self.assertEqual(self.create(paths, archive)[0], 0)
            before = archive.read_bytes()
            code, _, _ = invoke("circuit-review-inspect", archive, "--output", archive)
            self.assertEqual(code, 2)
            self.assertEqual(archive.read_bytes(), before)
            alias = Path(directory) / "alias.json"
            alias.symlink_to(paths["authority"])
            code, _, _ = invoke(
                "circuit-review-verify",
                archive,
                "--expected-authority",
                paths["authority"],
                "--output",
                alias,
            )
            self.assertEqual(code, 2)

    def test_bounded_invalid_archive_never_creates_report(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.bcb"
            archive.write_bytes(b"not an archive")
            report = Path(directory) / "report.json"
            code, _, _ = invoke("circuit-review-inspect", archive, "--output", report)
            self.assertEqual(code, 2)
            self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
