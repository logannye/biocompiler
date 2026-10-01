"""Offline public workflows preserve nominal claims and independent authority."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import _read_artifact, main
from biocompiler.ir.molecule_records import MAX_MOLECULE_JSON_BYTES
from examples.circuit_molecules import fixture_provenance
from examples.circuit_sources import make_source_inventory
from test_circuit_bindings import binding_fixture


def invoke(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, arguments)))
    return code, out.getvalue(), err.getvalue()


class CircuitInfrastructureWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = binding_fixture()
        cls.construction = cls.binding.construction
        cls.build = bc.build_circuit_construction(cls.construction)
        cls.source = bc.CircuitEvidenceSource(
            "artificial-reference",
            "reference",
            "1",
            "a" * 64,
            "reference_only",
            None,
            (),
            fixture_provenance("artificial-evidence-metadata"),
        )
        cls.evidence = bc.CircuitEvidenceRequest(cls.construction, (cls.source,))

    def files(self, directory):
        records = {
            "construction": self.construction,
            "build": self.build,
            "candidate": self.build.candidate,
            "bindings": self.binding,
            "evidence": self.evidence,
        }
        paths = {}
        for name, record in records.items():
            paths[name] = Path(directory) / (name + ".json")
            paths[name].write_text(record.to_json() + "\n", encoding="utf-8")
        return paths

    def test_public_api_and_typed_generic_inspection_roundtrip(self):
        binding_assessment = bc.check_circuit_bindings(
            self.build.candidate, expected_request=self.binding
        )
        receipt = bc.capture_circuit_evidence(
            self.build, expected_request=self.evidence
        )
        evidence_assessment = bc.check_circuit_evidence(
            receipt, self.build, expected_request=self.evidence
        )
        inventory = make_source_inventory()
        records = (
            self.binding,
            self.binding.bindings[0],
            binding_assessment,
            self.evidence,
            self.source,
            receipt,
            receipt.sources[0],
            evidence_assessment,
            evidence_assessment.dependencies[0],
            bc.CircuitEvidenceObservationBinding("response", "A"),
            inventory,
            *inventory.sources,
            *inventory.cases,
            *inventory.reviews,
            inventory.cases[0].coverage[0],
            bc.check_circuit_sources(inventory),
        )
        for record in records:
            with self.subTest(schema=record.schema_version):
                self.assertIn(type(record).__name__, bc.__all__)
                self.assertEqual(_read_artifact(record.to_json()), record)
        for name in (
            "inspect_circuit_construction",
            "diff_circuit_constructions",
            "inspect_circuit_source_readiness",
        ):
            self.assertIn(name, bc.__all__)

    def test_bindings_cli_checks_replays_and_preserves_input_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            assessment = Path(directory) / "assessment.json"
            args = (
                "circuit-bindings-check",
                paths["candidate"],
                "--expected-request",
                paths["bindings"],
            )
            code, text, error = invoke(*args, "--output", assessment)
            self.assertEqual((code, error), (0, ""))
            summary = json.loads(text)
            self.assertTrue(summary["complete_nominal_bindings"])
            self.assertEqual(summary["independent_entity_identity"], "unestablished")
            self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
            code, _, error = invoke(
                "circuit-bindings-verify",
                assessment,
                "--candidate",
                paths["candidate"],
                "--expected-request",
                paths["bindings"],
            )
            self.assertEqual((code, error), (0, ""))
            for protected in (paths["candidate"], paths["bindings"]):
                original = protected.read_bytes()
                code, _, _ = invoke(*args, "--output", protected)
                self.assertEqual(code, 2)
                self.assertEqual(protected.read_bytes(), original)
            paths["bindings"].write_text(
                replace(
                    self.binding, assumptions=("Changed explicit assumption.",)
                ).to_json(),
                encoding="utf-8",
            )
            code, _, _ = invoke(
                "circuit-bindings-verify",
                assessment,
                "--candidate",
                paths["candidate"],
                "--expected-request",
                paths["bindings"],
            )
            self.assertEqual(code, 2)

    def test_missing_bindings_publish_failure_and_replay_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            paths["bindings"].write_text(
                replace(self.binding, bindings=()).to_json(), encoding="utf-8"
            )
            assessment = Path(directory) / "missing.json"
            code, _, error = invoke(
                "circuit-bindings-check",
                paths["candidate"],
                "--expected-request",
                paths["bindings"],
                "--output",
                assessment,
            )
            self.assertEqual((code, error), (1, ""))
            self.assertEqual(
                bc.CircuitBindingAssessment.from_json(assessment.read_text()).outcome,
                bc.CheckOutcome.FAIL,
            )
            code, _, error = invoke(
                "circuit-bindings-verify",
                assessment,
                "--candidate",
                paths["candidate"],
                "--expected-request",
                paths["bindings"],
            )
            self.assertEqual((code, error), (1, ""))

    def test_evidence_cli_capture_check_replay_and_stale_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            receipt, assessment = (
                Path(directory) / "receipt.json",
                Path(directory) / "evidence-assessment.json",
            )
            code, _, error = invoke(
                "circuit-evidence-capture",
                paths["build"],
                "--expected-request",
                paths["evidence"],
                "--output",
                receipt,
            )
            self.assertEqual((code, error), (0, ""))
            args = (
                "circuit-evidence-check",
                receipt,
                "--build",
                paths["build"],
                "--expected-request",
                paths["evidence"],
            )
            code, text, error = invoke(*args, "--output", assessment)
            self.assertEqual((code, error), (0, ""))
            summary = json.loads(text)
            self.assertEqual(summary["freshness"], "current")
            self.assertEqual(summary["prediction"], "unsupported")
            self.assertEqual(summary["evidence_applicability"], "unassessed")
            replay = (
                "circuit-evidence-verify",
                assessment,
                "--receipt",
                receipt,
                "--build",
                paths["build"],
                "--expected-request",
                paths["evidence"],
            )
            code, _, error = invoke(*replay)
            self.assertEqual((code, error), (0, ""))
            for protected in (receipt, paths["build"], paths["evidence"]):
                original = protected.read_bytes()
                code, _, _ = invoke(*args, "--output", protected)
                self.assertEqual(code, 2)
                self.assertEqual(protected.read_bytes(), original)
            paths["evidence"].write_text(
                replace(
                    self.evidence, sources=(replace(self.source, version="2"),)
                ).to_json(),
                encoding="utf-8",
            )
            code, _, _ = invoke(*replay)
            self.assertEqual(code, 2)
            code, text, error = invoke(*args, "--output", assessment)
            self.assertEqual((code, error), (1, ""))
            self.assertEqual(json.loads(text)["freshness"], "stale")
            code, _, error = invoke(*replay)
            self.assertEqual((code, error), (1, ""))

    def test_evidence_missing_is_distinct_from_freshness_and_prediction_support(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            paths["evidence"].write_text(
                replace(self.evidence, sources=()).to_json(), encoding="utf-8"
            )
            receipt, assessment = (
                Path(directory) / "receipt.json",
                Path(directory) / "assessment.json",
            )
            code, _, error = invoke(
                "circuit-evidence-capture",
                paths["build"],
                "--expected-request",
                paths["evidence"],
                "--output",
                receipt,
            )
            self.assertEqual((code, error), (0, ""))
            code, text, error = invoke(
                "circuit-evidence-check",
                receipt,
                "--build",
                paths["build"],
                "--expected-request",
                paths["evidence"],
                "--output",
                assessment,
            )
            self.assertEqual((code, error), (1, ""))
            self.assertEqual(json.loads(text)["freshness"], "missing")
            self.assertTrue(json.loads(text)["missing_evidence"])

    def test_construction_inspection_requires_explicit_fresh_replay_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            view = Path(directory) / "view.json"
            code, text, error = invoke(
                "circuit-inspect", paths["build"], "--output", view
            )
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(text)["freshness"]["status"], "not_replayed")
            self.assertEqual(json.loads(text), json.loads(view.read_text()))
            code, text, error = invoke(
                "circuit-inspect",
                paths["build"],
                "--expected-request",
                paths["construction"],
            )
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(
                json.loads(text)["freshness"]["status"], "replayed_external_authority"
            )
            original = paths["construction"].read_bytes()
            code, _, _ = invoke(
                "circuit-inspect",
                paths["build"],
                "--expected-request",
                paths["construction"],
                "--output",
                paths["construction"],
            )
            self.assertEqual(code, 2)
            self.assertEqual(paths["construction"].read_bytes(), original)

    def test_diff_preserves_numeric_types_and_requires_both_replay_authorities(self):
        provenance = fixture_provenance("amount-type-comparison")
        amount = bc.AmountDeclaration(
            "amount",
            "artificial-output",
            "preparation",
            ("payload-role",),
            1,
            "artificial-units",
            provenance,
        )
        first = replace(self.construction, amounts=(amount,))
        second = replace(first, amounts=(replace(amount, quantity=1.0),))
        first_build, second_build = (
            bc.build_circuit_construction(first),
            bc.build_circuit_construction(second),
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                Path(directory) / name
                for name in (
                    "first.json",
                    "second.json",
                    "first-request.json",
                    "second-request.json",
                )
            ]
            for path, artifact in zip(
                paths, (first_build, second_build, first, second)
            ):
                path.write_text(artifact.to_json(), encoding="utf-8")
            code, text, error = invoke("circuit-diff", paths[0], paths[1])
            self.assertEqual((code, error), (0, ""))
            report = json.loads(text)
            self.assertFalse(report["identical_content"])
            self.assertTrue(
                any(
                    item["section"] == "authority.amounts"
                    and "quantity" in item["fields"]
                    for item in report["changes"]
                )
            )
            code, _, _ = invoke(
                "circuit-diff", paths[0], paths[1], "--expected-before", paths[2]
            )
            self.assertEqual(code, 2)
            code, text, error = invoke(
                "circuit-diff",
                paths[0],
                paths[1],
                "--expected-before",
                paths[2],
                "--expected-after",
                paths[3],
                "--max-changes",
                1,
            )
            self.assertEqual((code, error), (0, ""))
            self.assertTrue(json.loads(text)["truncated"])
            self.assertEqual(
                json.loads(text)["freshness"]["after"]["status"],
                "replayed_external_authority",
            )

    def test_raw_json_byte_limits_duplicate_keys_and_unknown_fields_fail_closed(self):
        document = self.binding.to_json()
        for text in (
            document
            + " " * (MAX_MOLECULE_JSON_BYTES - len(document.encode("utf-8")) + 1),
            document.replace("{", '{"schema_version":"shadow",', 1),
            document.replace("{", '{"unexpected":true,', 1),
        ):
            with self.subTest(size=len(text)), self.assertRaises(bc.SerializationError):
                _read_artifact(text)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"\xff")
            code, _, _ = invoke("circuit-inspect", path)
            self.assertEqual(code, 2)

    def test_source_readiness_keeps_missing_fields_and_protects_inventory(self):
        inventory = make_source_inventory()
        with tempfile.TemporaryDirectory() as directory:
            path, view = (
                Path(directory) / "inventory.json",
                Path(directory) / "readiness.json",
            )
            path.write_text(inventory.to_json(), encoding="utf-8")
            code, text, error = invoke(
                "circuit-sources-readiness",
                path,
                "--case-id",
                inventory.cases[0].id,
                "--output",
                view,
            )
            self.assertEqual((code, error), (0, ""))
            report = json.loads(text)
            self.assertEqual(report["readiness"], "not_established")
            self.assertEqual(report["source_bytes"], "not_checked")
            self.assertGreater(report["cases"][0]["missing_field_count"], 0)
            self.assertEqual(json.loads(view.read_text()), report)
            original = path.read_bytes()
            code, _, _ = invoke("circuit-sources-readiness", path, "--output", path)
            self.assertEqual(code, 2)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
