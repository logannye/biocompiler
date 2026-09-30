"""Integration of frozen input authority, real passes, generation and acceptance."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.compiler.pipeline import ArtifactStatus, PipelineError
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.ir.serialization import fingerprint
from examples.checked_pipeline import build_request


class CheckedPipelineTests(unittest.TestCase):
    def setUp(self):
        self.request, self.history = build_request()

    def test_real_passes_complete_scoped_profile_and_preserve_unknowns(self):
        build = run_synthetic_pipeline(self.request, self.history, until=7)
        self.assertEqual(build.result.status, ArtifactStatus.COMPLETE)
        self.assertEqual(build.candidate.request_fingerprint, self.request.fingerprint)
        self.assertEqual(
            [x.id for x in build.result.unresolved], ["molecular_behavior"]
        )
        record = build.manager.get("mechanism")
        self.assertEqual(
            record.to_dict()["provenance"]["observation_map"],
            build.candidate.observation_map.to_dict(),
        )
        self.assertEqual(record.checks["finite_history"]["evidence"]["outcome"], "pass")
        self.assertEqual(
            build.manager.get("behavior").dependencies["request"],
            self.request.build_request.fingerprint,
        )

    def test_imported_request_builds_without_authoring_and_has_same_identity(self):
        restored = bc.RealizationRequest.from_json(self.request.to_json())
        first = run_synthetic_pipeline(self.request, self.history, until=7)
        second = run_synthetic_pipeline(restored, self.history, until=7)
        self.assertEqual(first.candidate.fingerprint, second.candidate.fingerprint)
        self.assertEqual(
            first.result.artifact.fingerprint, second.result.artifact.fingerprint
        )

    def test_upstream_catalog_change_invalidates_accepted_result(self):
        build = run_synthetic_pipeline(self.request, self.history, until=7)
        build.manager.set_dependency("catalog", fingerprint("changed registry"))
        with self.assertRaisesRegex(PipelineError, "Stale"):
            build.manager.result("mechanism", scope="synthetic_realization")

    def test_unexercised_history_cannot_complete(self):
        with self.assertRaisesRegex(PipelineError, "not passed"):
            run_synthetic_pipeline(self.request, self.history[:1], until=7)

    def test_wrong_scope_and_invalid_configuration_are_rejected(self):
        request = replace(
            self.request,
            build_request=replace(
                self.request.build_request, artifact_scope="exact_cds"
            ),
        )
        with self.assertRaisesRegex(PipelineError, "synthetic_realization"):
            run_synthetic_pipeline(request, self.history, until=7)
        for value in ({}, False, []):
            with self.assertRaises(TypeError):
                run_synthetic_pipeline(
                    self.request, self.history, until=7, config=value
                )

    def test_request_cli_import_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            for request in (self.request.build_request, self.request):
                path.write_text(request.to_json())
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(main(["inspect", str(path)]), 0)
                self.assertIn(request.fingerprint, out.getvalue())
        with self.assertRaises(bc.SerializationError):
            bc.BuildRequest.from_json('{"schema_version":"a","schema_version":"b"}')


if __name__ == "__main__":
    unittest.main()
