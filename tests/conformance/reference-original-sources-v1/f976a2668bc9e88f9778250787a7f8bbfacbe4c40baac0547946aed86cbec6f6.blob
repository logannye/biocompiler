"""Only fresh, independently checked reference spelling completes exact_cds."""

from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.cli import main
from biocompiler.compiler.molecular import run_molecular_pipeline
from biocompiler.compiler.pipeline import ArtifactStatus, PassManager, PipelineError
from biocompiler.ir.construct import ConstructRequest
from biocompiler.ir.molecular import MolecularArtifact
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.evidence import CheckOutcome
from examples.reference_construct import reference_request


class MolecularPipelineTests(unittest.TestCase):
    def setUp(self):
        self.request, self.manifest, self.registry = reference_request("RNA")
        self.manifests = {self.manifest.reference_set_id: self.manifest}

    def build(self, request=None, registry=None, manifests=None):
        return run_molecular_pipeline(
            self.request if request is None else request,
            self.registry if registry is None else registry,
            self.manifests if manifests is None else manifests,
        )

    def test_dna_and_rna_complete_exact_cds_with_remaining_payload_obligations(self):
        for alphabet in ("DNA", "RNA"):
            request, manifest, registry = reference_request(alphabet)
            build = run_molecular_pipeline(
                request, registry, {manifest.reference_set_id: manifest}
            )
            selected = request.references[0].selection.reference
            expected = manifest.record(selected.id)
            record = build.candidate.records[0]
            self.assertEqual(build.result.scope, "exact_cds")
            self.assertEqual(build.result.status, ArtifactStatus.COMPLETE)
            self.assertEqual(build.check_result.outcome, CheckOutcome.PASS)
            self.assertEqual(record.sequence, expected.sequence)
            self.assertEqual(record.sequence_sha256, expected.sequence_sha256)
            self.assertEqual(record.alphabet, alphabet)
            self.assertEqual(len(record.sequence), 1491)
            self.assertEqual(
                {item.id for item in build.result.unresolved},
                {"complete_payload_features", "molecular_behavior"},
            )
            self.assertEqual(build.manager.get("molecular").parent, "construct")
            with self.assertRaises(PipelineError):
                build.manager.result("molecular", scope="complete_payload")

    def test_imported_request_and_artifact_preserve_identity(self):
        first = self.build()
        restored = ConstructRequest.from_json(self.request.to_json())
        second = self.build(request=restored)
        self.assertEqual(first.candidate.fingerprint, second.candidate.fingerprint)
        self.assertEqual(
            first.result.artifact.fingerprint, second.result.artifact.fingerprint
        )
        self.assertEqual(
            MolecularArtifact.from_json(first.candidate.to_json()), first.candidate
        )

    def test_each_current_root_invalidates_exact_cds_reuse(self):
        build = self.build()
        roots = dict(build.manager.get("molecular").dependencies)
        for key, original in roots.items():
            if key == "target":
                continue
            build.manager.set_dependency(key, fingerprint("changed:" + key))
            with self.subTest(key=key):
                with self.assertRaisesRegex(PipelineError, "Stale"):
                    build.manager.result("molecular", scope="exact_cds")
            build.manager.set_dependency(key, original)
        with self.assertRaisesRegex(PipelineError, "Target"):
            build.manager.set_dependency("target", fingerprint("different modality"))

    def test_changed_molecular_providers_cannot_be_misattributed_on_rerun(self):
        build = self.build()
        roots = dict(build.manager.get("molecular").dependencies)
        for key in (
            "molecular_emitter",
            "molecular_checker",
            "molecular_profile",
            "encoding_policy",
            "molecular_pipeline",
        ):
            build.manager.set_dependency(key, fingerprint("unloaded:" + key))
            with self.subTest(key=key):
                with self.assertRaisesRegex(PipelineError, "rebuild the pipeline"):
                    build.manager.run(
                        "construct_to_molecular", "construct", "recreated"
                    )
            build.manager.set_dependency(key, roots[key])
        build.manager.run("construct_to_molecular", "construct", "recreated")
        self.assertEqual(
            build.manager.result("recreated", scope="exact_cds").status,
            ArtifactStatus.COMPLETE,
        )

    def test_failed_authority_never_invokes_emission(self):
        with patch(
            "biocompiler.compiler.molecular.emit_reference_sequence",
            side_effect=AssertionError("Should not emit"),
        ):
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build(registry=replace(self.registry, version="stale"))
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build(manifests={})

    def test_changed_base_cannot_be_accepted_by_updating_reported_sequence_hash(self):
        valid = self.build().candidate
        record = valid.records[0]
        sequence = (
            record.sequence[:30]
            + ("A" if record.sequence[30] != "A" else "C")
            + record.sequence[31:]
        )
        changed = replace(
            record,
            sequence=sequence,
            sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        )
        artifact = replace(valid, records=(changed,))
        with patch(
            "biocompiler.compiler.molecular.emit_reference_sequence",
            return_value=artifact,
        ):
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build()

    def run_with_pass_mutation(self, mutation):
        original_register = PassManager.register

        def register(manager, contract, producer, validators):
            if contract.id == "construct_to_molecular":
                original = producer

                def producer(context):
                    return mutation(original(context))

            return original_register(manager, contract, producer, validators)

        with patch.object(PassManager, "register", register):
            return self.build()

    def test_source_link_duplication_and_unestablished_observations_fail(self):
        for mutation in (
            lambda result: replace(
                result, source_links=(*result.source_links, result.source_links[0])
            ),
            lambda result: replace(
                result, observation_map={"biological_response": "passed"}
            ),
        ):
            with self.assertRaisesRegex(PipelineError, "source correspondence"):
                self.run_with_pass_mutation(mutation)

    def test_encoding_rechecks_layout_and_composition_without_granting_biology(self):
        build = self.build()
        record = build.manager.get("molecular")
        self.assertEqual(
            set(record.provenance["contract"]["invalidated_analyses"]),
            {"construct_layout", "component_linkage", "molecular_behavior"},
        )
        self.assertEqual(record.checks["encoding_composition"]["outcome"], "pass")
        self.assertIn("construct_layout", record.discharged)
        self.assertIn("emitted_sequence_identity", record.discharged)
        self.assertNotIn("molecular_behavior", record.discharged)
        self.assertEqual(
            build.manager.result("construct", scope="reference_construct").status,
            ArtifactStatus.COMPLETE,
        )

    def test_molecular_cli_inspection_is_historical(self):
        build = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "molecular.json"
            for artifact in (build.candidate, build.check_result):
                path.write_text(artifact.to_json())
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["inspect", str(path)]), 0)
                self.assertIn(artifact.fingerprint, output.getvalue())
                self.assertIn("inspection", output.getvalue())


if __name__ == "__main__":
    unittest.main()
