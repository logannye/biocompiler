"""Checked reference layout scopes preserve exact authority and unresolved work."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.cli import main
from biocompiler.compiler.construct import run_construct_pipeline
from biocompiler.compiler.pipeline import ArtifactStatus, PassManager, PipelineError
from biocompiler.ir.construct import ConstructCandidate, ConstructRequest, SequenceRange
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.evidence import CheckOutcome
from examples.reference_construct import reference_request


class ConstructPipelineTests(unittest.TestCase):
    def setUp(self):
        self.request, self.manifest, self.registry = reference_request("RNA")
        self.manifests = {self.manifest.reference_set_id: self.manifest}

    def build(self, request=None, registry=None, manifests=None):
        return run_construct_pipeline(
            self.request if request is None else request,
            self.registry if registry is None else registry,
            self.manifests if manifests is None else manifests,
        )

    def test_dna_and_rna_complete_only_reference_layout_scope(self):
        for alphabet in ("DNA", "RNA"):
            request, manifest, registry = reference_request(alphabet)
            build = run_construct_pipeline(
                request, registry, {manifest.reference_set_id: manifest}
            )
            self.assertEqual(build.result.status, ArtifactStatus.COMPLETE)
            self.assertEqual(build.result.scope, "reference_construct")
            self.assertEqual(build.check_result.outcome, CheckOutcome.PASS)
            self.assertEqual(build.candidate.molecules[0].alphabet, alphabet)
            self.assertEqual(
                build.candidate.placements[0].molecule_range, SequenceRange(0, 1491)
            )
            self.assertEqual(
                {item.id for item in build.result.unresolved},
                {
                    "emitted_sequence_identity",
                    "complete_payload_features",
                    "molecular_behavior",
                },
            )
            self.assertEqual(build.manager.get("construct").parent, "components")
            with self.assertRaises(PipelineError):
                build.manager.result("construct", scope="exact_cds")

    def test_roundtrip_request_builds_without_reexecuting_authoring(self):
        first = self.build()
        restored = ConstructRequest.from_json(self.request.to_json())
        second = self.build(request=restored)
        self.assertEqual(first.candidate.fingerprint, second.candidate.fingerprint)
        self.assertEqual(
            first.result.artifact.fingerprint, second.result.artifact.fingerprint
        )
        self.assertEqual(
            ConstructCandidate.from_json(first.candidate.to_json()), first.candidate
        )
        # The schema permits omitted archival lineage; structural authority is
        # still pinned by the complete request and embedded composition.
        omitted = replace(restored, source_request_fingerprint=None)
        checked = self.build(request=omitted)
        self.assertTrue(checked.check_result.passed)
        self.assertEqual(
            checked.candidate.composition_fingerprint, omitted.composition.fingerprint
        )

    def test_all_current_roots_invalidate_both_admission_and_construct(self):
        build = self.build()
        for key in build.manager.get("construct").dependencies:
            if key == "target":
                continue
            original = build.manager.get("construct").dependencies[key]
            build.manager.set_dependency(key, fingerprint("changed:" + key))
            with self.subTest(key=key):
                with self.assertRaisesRegex(PipelineError, "Stale"):
                    build.manager.result("construct", scope="reference_construct")
                with self.assertRaisesRegex(PipelineError, "Stale"):
                    build.manager.get("components")
            build.manager.set_dependency(key, original)
        with self.assertRaisesRegex(PipelineError, "Target"):
            build.manager.set_dependency("target", fingerprint("new target"))

    def test_layout_pass_invalidates_and_rechecks_conditional_composition(self):
        build = self.build()
        record = build.manager.get("construct")
        self.assertIn(
            "component_linkage", record.provenance["contract"]["invalidated_analyses"]
        )
        self.assertIn(
            "molecular_behavior", record.provenance["contract"]["invalidated_analyses"]
        )
        self.assertEqual(record.checks["layout_composition"]["outcome"], "pass")
        self.assertIn("component_linkage", record.discharged)
        self.assertNotIn("molecular_behavior", record.discharged)

    def test_bad_authority_never_invokes_candidate_generator(self):
        changed = replace(self.registry, version="stale")
        with patch(
            "biocompiler.compiler.construct.generate_construct",
            side_effect=AssertionError("Should not generate"),
        ):
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build(registry=changed)
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build(manifests={})

    def test_source_requirement_and_unknown_feature_metadata_survive(self):
        build = self.build()
        instance = self.request.composition.instances[0]
        self.assertEqual(
            build.candidate.placements[0].requirement_ids, instance.requirement_ids
        )
        self.assertEqual(
            build.candidate.molecules[0].unknown_features,
            self.request.molecules[0].unknown_features,
        )
        links = build.manager.get("construct").provenance["source_links"]
        self.assertEqual(
            {link["requirement_id"] for link in links},
            set(self.request.composition.requirement_ids),
        )
        self.assertEqual({link["source_node_id"] for link in links}, {instance.id})

    def test_candidate_with_edited_orientation_is_not_accepted(self):
        from biocompiler.synthesis.construct import generate_construct

        valid = generate_construct(self.request)
        changed = replace(
            valid, placements=(replace(valid.placements[0], orientation="reverse"),)
        )
        with patch(
            "biocompiler.compiler.construct.generate_construct", return_value=changed
        ):
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.build()

    def test_nonempty_observation_map_cannot_smuggle_behavioral_evidence(self):
        original_register = PassManager.register

        def register(manager, contract, producer, validators):
            original = producer

            def forged(context):
                return replace(
                    original(context), observation_map={"behavior": "verified"}
                )

            return original_register(manager, contract, forged, validators)

        with patch.object(PassManager, "register", register):
            with self.assertRaisesRegex(PipelineError, "provenance"):
                self.build()

    def test_inspection_is_historical_and_never_implies_acceptance(self):
        build = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "construct.json"
            for artifact in (self.request, build.candidate, build.check_result):
                path.write_text(artifact.to_json())
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["inspect", str(path)]), 0)
                self.assertIn(artifact.fingerprint, output.getvalue())
                self.assertIn("inspection", output.getvalue())


if __name__ == "__main__":
    unittest.main()
