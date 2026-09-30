"""Research compilation, source sensitivity and independent publication boundaries."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.compiler.pipeline import ArtifactStatus, PipelineError
from biocompiler.ir.implementation_build import ImplementationStage
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.stages import Stage
from examples.molecular_implementation import make_implementation_request


def invoke(*args):
    output, error = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(error):
        code = main(list(map(str, args)))
    return code, output.getvalue(), error.getvalue()


class ImplementationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = make_implementation_request()
        cls.compilation = bc.compile(cls.request)
        cls.record = cls.compilation.record

    def test_complete_structural_chain_preserves_original_human_authority(self):
        record = self.record
        self.assertEqual(record.molecule.sequence, "GGAUGGCUUUUUAACCAAAA")
        self.assertEqual(record.request.source, self.request.source)
        self.assertEqual(record.requirements.source, self.request.source)
        self.assertIsInstance(record.request.source, bc.HumanAcceptanceRequest)
        self.assertEqual(
            self.compilation.pipeline_result.status, ArtifactStatus.COMPLETE
        )
        self.assertEqual(record.scope, "secreted_precursor_structure")
        self.assertEqual(record.therapeutic_implementation, "partial")
        self.assertEqual(record.human_therapeutic_admission, "not_admitted")
        self.assertTrue(self.compilation.pipeline_result.unresolved)
        stages = (
            "intent",
            "requirements",
            "planning",
            "components",
            "construct",
            "molecule",
        )
        for name, expected in zip(stages, Stage):
            artifact = self.compilation.manager.get(name)
            self.assertEqual(artifact.stage, expected)
            self.assertEqual(
                set(artifact.requirements), set(record.requirements.source_node_ids)
            )
        self.assertEqual(
            record.plan.unresolved_obligation_ids,
            tuple(item.id for item in record.requirements.obligations),
        )
        product = next(
            item
            for item in record.construct.placements
            if item.kind == "mature_product"
        )
        self.assertEqual(product.molecule_range, bc.SequenceRange(8, 11))
        self.assertEqual(product.protein_range, bc.SequenceRange(2, 3))
        self.assertEqual(record.construct.cleavage_after_nt, 8)
        self.assertEqual(record.construct.mature_protein, "F")

    def test_architecture_changes_encoding_and_processing_map(self):
        request = replace(
            self.request,
            constraints=bc.ImplementationConstraints(
                allowed_architecture_ids=("extended",)
            ),
        )
        record = bc.compile(request).record
        self.assertEqual(record.molecule.sequence, "GGAUGGCUGCUUUUUAACCAAAA")
        self.assertEqual(record.construct.cleavage_after_nt, 11)
        self.assertEqual(record.construct.cleavage_after_aa, 3)
        self.assertEqual(
            record.construct.mature_protein, self.record.construct.mature_protein
        )
        self.assertNotEqual(record.fingerprint, self.record.fingerprint)

    def test_source_product_edit_cannot_reuse_old_product_architecture(self):
        source = self.request.build_request
        nodes = tuple(
            replace(
                node,
                attributes=dict(node.attributes) | {"product": "different_product"},
            )
            if node.kind == "secretion"
            else node
            for node in source.intent.nodes
        )
        request = replace(
            self.request,
            source=replace(source, intent=replace(source.intent, nodes=nodes)),
        )
        record = bc.compile(request).record
        self.assertEqual(record.status, "no_candidate_found")
        self.assertIsNone(record.molecule)
        self.assertTrue(record.selection.diagnostics)
        bc.verify_implementation_build(record, expected_request=request)
        with self.assertRaises(bc.SerializationError):
            bc.verify_implementation_build(self.record, expected_request=request)

    def test_guard_edit_changes_authority_and_retains_unimplemented_control(self):
        source = self.request.build_request
        before = replace(self.request, source=source)
        baseline = bc.compile(before).record
        nodes = tuple(
            replace(node, attributes={"band": "low"})
            if node.kind == "qualitative"
            else node
            for node in source.intent.nodes
        )
        after = replace(
            before, source=replace(source, intent=replace(source.intent, nodes=nodes))
        )
        changed = bc.compile(after).record
        self.assertNotEqual(
            changed.requirements.fingerprint, baseline.requirements.fingerprint
        )
        self.assertNotEqual(changed.fingerprint, baseline.fingerprint)
        self.assertEqual(changed.molecule.sequence, baseline.molecule.sequence)
        control = [
            item for item in changed.requirements.obligations if item.kind == "control"
        ]
        self.assertTrue(control)
        self.assertTrue(all(item.status == "unresolved" for item in control))
        with self.assertRaises(bc.SerializationError):
            bc.verify_implementation_build(baseline, expected_request=after)

    def test_no_candidate_records_replay_but_cannot_export(self):
        requests = (
            replace(
                self.request,
                constraints=bc.ImplementationConstraints(
                    require_implementation_complete=True
                ),
            ),
            replace(
                self.request, constraints=bc.ImplementationConstraints(max_length=1)
            ),
            replace(self.request, library=replace(self.request.library, providers=())),
        )
        for request in requests:
            with self.subTest(constraints=request.constraints):
                result = bc.compile(request)
                self.assertEqual(result.pipeline_result.status, ArtifactStatus.PARTIAL)
                self.assertIsNone(result.molecule)
                self.assertEqual(len(result.record.selection.alternatives), 2)
                self.assertTrue(
                    all(
                        item.rejections for item in result.record.selection.alternatives
                    )
                )
                bc.verify_implementation_build(result.record, expected_request=request)
                with self.assertRaises(bc.SerializationError):
                    bc.export_implementation_fasta(
                        result.record, expected_request=request
                    )

    def test_roundtrip_rebuild_and_frozen_stage_import(self):
        for value in (
            self.record,
            self.record.requirements,
            self.request,
            ImplementationStage(
                self.request.fingerprint,
                "requirements",
                self.record.requirements,
                self.record.requirements.source_node_ids,
            ),
        ):
            self.assertEqual(type(value).from_json(value.to_json()), value)
            self.assertEqual(type(value).from_dict(freeze_json(value.to_dict())), value)
        self.assertEqual(
            bc.compile(self.request).record.fingerprint, self.record.fingerprint
        )

    def test_saved_verification_never_calls_producers(self):
        module = "biocompiler.compiler.implementation."
        with ExitStack() as stack:
            for name in (
                "analyze_implementation_requirements",
                "select_implementation",
                "derive_implementation_plan",
                "derive_implementation_construct",
                "emit_implementation",
                "_components",
            ):
                stack.enter_context(
                    patch(
                        module + name,
                        side_effect=AssertionError("Producer used as oracle"),
                    )
                )
            verified = bc.verify_implementation_build(
                self.record, expected_request=self.request
            )
            fasta = bc.export_implementation_fasta(
                verified, expected_request=self.request
            )
        self.assertEqual("".join(fasta.splitlines()[1:]), "GGAUGGCUUUUUAACCAAAA")
        self.assertIn("physical_function=unestablished", fasta)

    def test_saved_claims_checks_components_and_rehashed_bases_cannot_promote(self):
        sequence = "GGAUGGCCUUUUAACCAAAA"
        forged = replace(
            self.record.molecule,
            sequence=sequence,
            sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
        )
        records = (
            replace(self.record, molecule=forged),
            replace(self.record, checks={}),
            replace(self.record, tool_versions={}),
            replace(
                self.record,
                components=replace(self.record.components, plan_fingerprint="f" * 64),
            ),
        )
        for record in records:
            with (
                self.subTest(identity=record.fingerprint),
                self.assertRaises(bc.SerializationError),
            ):
                bc.verify_implementation_build(record, expected_request=self.request)
        for changes in (
            {"therapeutic_implementation": "complete"},
            {"structural_completion": 1},
            {"physical_function": "established"},
            {"human_therapeutic_admission": "admitted"},
            {"extra": True},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(bc.SerializationError),
            ):
                bc.ImplementationBuildRecord.from_dict(self.record.to_dict() | changes)

    def test_dependency_changes_invalidate_accepted_pipeline_artifacts(self):
        result = bc.compile(self.request)
        result.manager.set_dependency("library", "f" * 64)
        with self.assertRaises(PipelineError):
            result.manager.get("molecule")

    def test_cli_analysis_build_inspect_verify_export_and_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, request, report, build = (
                root / name
                for name in ("source.json", "request.json", "report.json", "build.json")
            )
            source.write_text(self.request.source.to_json())
            request.write_text(self.request.to_json())
            for args in (
                ("implementation-analyze", "--request", source, "--output", report),
                ("implementation-build", "--request", request, "--output", build),
                ("implementation-verify", build, "--expected-request", request),
                ("inspect", report),
                ("inspect", build),
            ):
                code, _, error = invoke(*args)
                self.assertEqual(code, 0, error)
            code, fasta, error = invoke(
                "implementation-fasta", build, "--expected-request", request
            )
            self.assertEqual(code, 0, error)
            self.assertEqual("".join(fasta.splitlines()[1:]), "GGAUGGCUUUUUAACCAAAA")
            self.assertEqual(
                invoke(
                    "implementation-build", "--request", request, "--output", request
                )[0],
                2,
            )
            self.assertEqual(
                invoke(
                    "implementation-analyze", "--request", source, "--output", source
                )[0],
                2,
            )
            self.assertEqual(
                bc.ImplementationRequest.from_json(request.read_text()), self.request
            )
            self.assertEqual(
                bc.HumanAcceptanceRequest.from_json(source.read_text()),
                self.request.source,
            )

    def test_cli_empty_search_explains_rejections_and_invalid_input_preserves_output(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            request, build = (
                Path(directory) / name for name in ("request.json", "build.json")
            )
            strict = replace(
                self.request,
                constraints=bc.ImplementationConstraints(
                    require_implementation_complete=True
                ),
            )
            request.write_text(strict.to_json())
            code, output, error = invoke(
                "implementation-build", "--request", request, "--output", build
            )
            self.assertEqual(code, 1, error)
            summary = json.loads(output)
            self.assertEqual(
                summary["alternatives"][0]["rejections"][0]["code"],
                "implementation_incomplete",
            )
            self.assertEqual(
                invoke("implementation-verify", build, "--expected-request", request)[
                    0
                ],
                1,
            )
            code, output, _ = invoke(
                "implementation-fasta", build, "--expected-request", request
            )
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            retained = build.read_bytes()
            request.write_text('{"schema_version":"first","schema_version":"second"}')
            self.assertEqual(
                invoke("implementation-build", "--request", request, "--output", build)[
                    0
                ],
                2,
            )
            self.assertEqual(build.read_bytes(), retained)
            self.assertFalse(list(build.parent.glob(".*.tmp")))


if __name__ == "__main__":
    unittest.main()
