"""End-to-end source sensitivity, independent replay and publication boundaries."""

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.compiler.pipeline import ArtifactStatus, PipelineError
from biocompiler.ir.candidate_build import CandidateComponents, CandidateStage
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.stages import Stage
from examples.intent_candidate import make_candidate_request


class CandidatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.request = make_candidate_request()
        self.build = bc.compile(self.request)
        self.record = self.build.record

    def test_full_source_to_sequence_and_scoped_completion(self):
        self.assertEqual(self.record.molecule.sequence, "GGAUGGCUUAACCAAAA")
        self.assertEqual(self.build.pipeline_result.status, ArtifactStatus.COMPLETE)
        self.assertEqual(self.record.to_dict()["therapeutic_implementation"], "partial")
        self.assertEqual(
            self.record.to_dict()["human_therapeutic_admission"], "not_admitted"
        )
        self.assertEqual(self.record.layout.target, self.request.target)
        self.assertEqual(self.build.manager.target, self.request.target)
        stages = (
            "intent",
            "requirements",
            "selection",
            "components",
            "layout",
            "molecule",
        )
        for identity, expected in zip(stages, Stage):
            stage = self.build.manager.get(identity)
            self.assertEqual(stage.stage, expected)
            self.assertEqual(
                set(stage.requirements),
                {node.id for node in self.request.build_request.intent.nodes},
            )
        unresolved = {item.id for item in self.record.requirements.unresolved}
        self.assertTrue(
            {
                "secretion_mechanism",
                "conditional_control",
                "human_external_shutdown",
                "human_prohibited_behavior",
                "human_deployment_contract",
            }
            <= unresolved
        )
        self.assertTrue(self.build.pipeline_result.unresolved)
        coding = next(
            item
            for item in self.record.source_map
            if item["correspondence"] == "product_encoding"
        )
        self.assertEqual(coding["part_id"], "coding_a")
        self.assertEqual(coding["molecule_range"], bc.SequenceRange(2, 11).to_dict())

    def test_source_and_architecture_edits_change_actual_output(self):
        changed = bc.compile(
            make_candidate_request(product="alternative_product")
        ).record
        self.assertEqual(changed.molecule.sequence, "GGAUGUUUUAACCAAAA")
        self.assertNotEqual(changed.fingerprint, self.record.fingerprint)
        changed = bc.compile(
            make_candidate_request(
                constraints=bc.CandidateConstraints(
                    allowed_architecture_ids=("extended",)
                )
            )
        ).record
        self.assertEqual(changed.molecule.sequence, "GGGGAUGGCUUAACCAAAA")
        self.assertEqual(len(changed.selection.alternatives), 2)
        with self.assertRaises(bc.CompilationUnavailableError):
            bc.compile(self.request.source)

    def test_exhaustion_retains_rejected_choices_without_sequence(self):
        request = make_candidate_request(
            constraints=bc.CandidateConstraints(max_length=1)
        )
        build = bc.compile(request)
        self.assertEqual(build.status, "no_candidate_found")
        self.assertIsNone(build.molecule)
        self.assertEqual(build.pipeline_result.status, ArtifactStatus.PARTIAL)
        self.assertEqual(len(build.record.selection.alternatives), 2)
        self.assertEqual(
            bc.verify_candidate_build(build.record, expected_request=request),
            build.record,
        )
        with self.assertRaises(bc.SerializationError):
            bc.export_candidate_fasta(build.record, expected_request=request)

    def test_roundtrip_relocation_and_canonical_rebuild(self):
        record = bc.CandidateBuildRecord.from_json(self.record.to_json())
        self.assertEqual(record, self.record)
        self.assertEqual(
            bc.verify_candidate_build(record, expected_request=self.request),
            self.record,
        )
        self.assertEqual(
            bc.compile(self.request).record.fingerprint, self.record.fingerprint
        )
        for value in (
            self.record.components,
            CandidateStage(
                self.request.fingerprint,
                "molecule",
                self.record.molecule,
                self.record.requirements.source_node_ids,
            ),
        ):
            self.assertEqual(type(value).from_dict(freeze_json(value.to_dict())), value)
        fasta = bc.export_candidate_fasta(record, expected_request=self.request)
        self.assertIn("therapeutic_implementation=partial", fasta.splitlines()[0])
        self.assertEqual("".join(fasta.splitlines()[1:]), "GGAUGGCUUAACCAAAA")

    def test_independent_authority_and_rehashed_molecule_mutations(self):
        wrong = make_candidate_request(product="alternative_product")
        with self.assertRaises(bc.SerializationError):
            bc.verify_candidate_build(self.record, expected_request=wrong)
        sequence = "GGAUGGCCUAACCAAAA"
        forged = replace(
            self.record,
            molecule=replace(
                self.record.molecule,
                sequence=sequence,
                sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
            ),
        )
        with self.assertRaises(bc.SerializationError):
            bc.verify_candidate_build(forged, expected_request=self.request)
        for patch in (
            {"therapeutic_implementation": "complete"},
            {"human_therapeutic_admission": "admitted"},
            {"source_map": []},
            {"extra": True},
        ):
            with self.subTest(patch=patch), self.assertRaises(bc.SerializationError):
                bc.CandidateBuildRecord.from_dict(self.record.to_dict() | patch)

    def test_stale_dependencies_and_saved_check_promotion(self):
        self.build.manager.set_dependency("library", "f" * 64)
        with self.assertRaises(PipelineError):
            self.build.manager.get("molecule")
        with self.assertRaises(bc.SerializationError):
            bc.verify_candidate_build(
                replace(self.record, checks={}), expected_request=self.request
            )
        with self.assertRaises(bc.SerializationError):
            bc.verify_candidate_build(
                replace(self.record, tool_versions={}), expected_request=self.request
            )
        parts = list(self.record.components.parts)
        parts[0] = next(
            part for part in self.request.library.parts if part.id == "front_long"
        )
        forged = replace(
            self.record, components=replace(self.record.components, parts=tuple(parts))
        )
        with self.assertRaises(bc.SerializationError):
            bc.verify_candidate_build(forged, expected_request=self.request)

    def test_cli_build_verify_fasta_and_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source, result = (
                Path(directory) / "request.json",
                Path(directory) / "result.json",
            )
            source.write_text(self.request.to_json(), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "candidate-build",
                            "--request",
                            str(source),
                            "--output",
                            str(result),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "candidate-verify",
                            str(result),
                            "--expected-request",
                            str(source),
                        ]
                    ),
                    0,
                )
                self.assertEqual(main(["inspect", str(result)]), 0)
                self.assertEqual(
                    main(
                        [
                            "candidate-build",
                            "--request",
                            str(source),
                            "--output",
                            str(source),
                        ]
                    ),
                    2,
                )
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "candidate-fasta",
                            str(result),
                            "--expected-request",
                            str(source),
                        ]
                    ),
                    0,
                )
            self.assertIn("GGAUGGCUUAACCAAAA", output.getvalue())
            self.assertEqual(
                bc.CandidateRequest.from_json(source.read_text()), self.request
            )

    def test_strict_build_stage_and_components_readers(self):
        for value in (self.record, self.record.components):
            data = value.to_dict()
            data["extra"] = True
            with self.assertRaises(bc.SerializationError):
                type(value).from_dict(data)
        with self.assertRaises(bc.SerializationError):
            CandidateComponents.from_dict({})


if __name__ == "__main__":
    unittest.main()
