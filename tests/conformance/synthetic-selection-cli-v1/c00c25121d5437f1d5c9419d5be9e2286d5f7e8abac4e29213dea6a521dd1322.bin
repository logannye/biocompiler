"""Public design workflows preserve scope, authority and diagnostic outcomes."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.artifacts.archive import assemble_archive, read_archive
from biocompiler.cli import main
from biocompiler.compiler.pipeline import PipelineError
from examples.synthetic_build import prepare_request
from examples.synthetic_design import prepare_design_request
from examples.synthetic_verification import (
    ignored_reset,
    mixed_bounds,
    verification_fixture,
)


class SyntheticDesignWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = prepare_design_request()
        cls.package = bc.build_synthetic_package(cls.request)
        realization, candidate, history = verification_fixture()
        cls.check = bc.SyntheticVerificationRequest(
            realization, candidate, "check", history=history, until=9
        )

    def call(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(value) for value in arguments])
        return (
            code,
            json.loads(out.getvalue()) if out.getvalue() else None,
            err.getvalue(),
        )

    def test_selected_temporal_components_package_reconstructs_every_stage(self):
        manifest, files, _ = read_archive(self.package.data)
        self.assertEqual(manifest.scope, "synthetic_components")
        self.assertEqual(len(files), 15)
        self.assertEqual(
            json.loads(files["selection.json"])["selected_strategy"], "de_morgan"
        )
        self.assertEqual(
            json.loads(files["checks/component-behavior.json"])["outcome"], "pass"
        )
        summary = json.loads(files["result.json"])
        self.assertEqual(
            [stage["id"] for stage in summary["stages"]],
            ["request", "behavior", "mechanism", "components"],
        )
        self.assertEqual(
            [item["id"] for item in summary["unresolved"]], ["molecular_behavior"]
        )
        self.assertNotEqual(
            summary["generator_config_fingerprint"],
            summary["selected_generator_config_fingerprint"],
        )
        self.assertTrue(
            {
                "component_model",
                "component_adapter",
                "component_linker",
                "synthetic_selection",
            }
            <= {pin.id for pin in manifest.toolchain}
        )
        self.assertEqual(
            bc.verify_synthetic_package(
                self.package.data, expected_request=self.request
            ).data,
            self.package.data,
        )
        self.assertEqual(
            bc.build_synthetic_package(
                bc.SyntheticBuildRequest.from_json(self.request.to_json())
            ).data,
            self.package.data,
        )

    def test_rehashed_component_and_selection_documents_do_not_establish_acceptance(
        self,
    ):
        manifest, original, metadata = read_archive(self.package.data)
        for path in (
            "assembly.json",
            "selection.json",
            "checks/composition.json",
            "checks/component-behavior.json",
            "stages/components.json",
        ):
            files = dict(original)
            value = json.loads(files[path])
            value["forged_claim"] = "verified"
            files[path] = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
            entries = tuple(
                replace(
                    entry,
                    sha256=hashlib.sha256(files[entry.path]).hexdigest(),
                    byte_length=len(files[entry.path]),
                )
                for entry in manifest.files
            )
            forged = assemble_archive(replace(manifest, files=entries), files, metadata)
            with self.subTest(path=path), self.assertRaises(bc.SerializationError):
                bc.verify_synthetic_package(forged, expected_request=self.request)
        with self.assertRaisesRegex(bc.SerializationError, "independent authority"):
            bc.verify_synthetic_package(
                self.package.data,
                expected_request=replace(self.request, profile="synthetic_realization"),
            )
        with self.assertRaisesRegex(bc.SerializationError, "inventory"):
            replace(
                manifest, profile="synthetic_realization", scope="synthetic_realization"
            )

    def test_unconstrained_default_stays_at_mechanism_and_does_not_invent_search(self):
        package = bc.build_synthetic_package(prepare_request())
        manifest, files, _ = read_archive(package.data)
        self.assertEqual(manifest.scope, "synthetic_realization")
        self.assertEqual(json.loads(files["selection.json"])["status"], "not_requested")
        self.assertNotIn("assembly.json", files)

    def test_selected_pipeline_receipts_expire_when_selection_policy_changes(self):
        build = bc.run_component_pipeline(
            self.request.realization,
            self.request.history.frames,
            until=self.request.until,
            config=self.request.config,
        )
        self.assertEqual(build.selection_result.selected_strategy, "de_morgan")
        self.assertTrue(build.behavior_result.passed)
        build.manager.set_dependency("selection_policy", "0" * 64)
        with self.assertRaisesRegex(PipelineError, "Stale"):
            build.manager.result("components", scope="synthetic_components")

    def test_component_package_and_selection_cli_report_actual_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, package, report = (
                root / "request.json",
                root / "design.bcb",
                root / "selection.json",
            )
            authority.write_text(self.request.to_json())
            code, summary, errors = self.call(
                ["synthetic-build", "--request", authority, "--output", package]
            )
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(summary["scope"], "synthetic_components")
            for args in (
                ["synthetic-inspect", package],
                ["synthetic-verify", package, "--expected-request", authority],
            ):
                code, summary, errors = self.call(args)
                self.assertEqual((code, errors), (0, ""))
                self.assertEqual(summary["scope"], "synthetic_components")
            code, summary, errors = self.call(
                ["synthetic-select", "--request", authority, "--output", report]
            )
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(summary["selected_strategy"], "de_morgan")
            self.assertEqual(
                bc.SyntheticSelectionResult.from_json(
                    report.read_text()
                ).selected_strategy,
                "de_morgan",
            )

    def test_cli_retains_unknown_and_replays_without_turning_it_into_pass(self):
        unknown = replace(self.check, history=(self.check.history[0],))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, report = root / "request.json", root / "report.json"
            request.write_text(unknown.to_json())
            code, summary, errors = self.call(
                ["synthetic-check", "--request", request, "--output", report]
            )
            self.assertEqual((code, errors), (1, ""))
            self.assertEqual(summary["outcome"], "unknown")
            self.assertTrue(report.exists())
            code, summary, errors = self.call(
                ["synthetic-replay", report, "--expected-request", request]
            )
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(summary["outcome"], "unknown")
            self.assertIn("does not turn", summary["replay"])
            request.write_text(self.check.to_json())
            code, _, errors = self.call(
                ["synthetic-replay", report, "--expected-request", request]
            )
            self.assertEqual(code, 2)
            self.assertIn("independent authority", errors)

    def test_cli_capped_campaign_and_selected_failure_reduction(self):
        campaign = replace(
            self.check,
            operation="explore",
            history=(),
            until=None,
            bounds=mixed_bounds(self.check.realization, max_histories=2),
        )
        mutant = replace(
            self.check,
            candidate=ignored_reset(self.check.candidate, self.check.realization),
            mode="model",
        )
        failed = bc.run_synthetic_verification(mutant)
        signature = bc.FailureSignature.from_counterexample(
            next(
                item
                for item in failed.result.counterexamples
                if item.requirement_id == "memory_readout"
                and item.expected["state"] == "inactive"
            )
        )
        reduction = replace(
            mutant, operation="reduce", signature=signature, max_evaluations=100
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, report = root / "request.json", root / "report.json"
            for operation, expected in (
                (self.check, 0),
                (campaign, 1),
                (mutant, 1),
                (reduction, 0),
            ):
                request.write_text(operation.to_json())
                code, summary, errors = self.call(
                    [
                        f"synthetic-{operation.operation}",
                        "--request",
                        request,
                        "--output",
                        report,
                    ]
                )
                self.assertEqual((code, errors), (expected, ""))
                if operation.operation == "explore":
                    self.assertFalse(summary["complete"])
                    self.assertFalse(summary["all_passed"])
                if operation.operation == "reduce":
                    self.assertTrue(summary["one_minimal"])
                    self.assertLess(
                        summary["reduced_frames"], summary["original_frames"]
                    )
                code, inspected, errors = self.call(["inspect", report])
                self.assertEqual((code, errors), (0, ""))
                self.assertIn("Historical", inspected["inspection"])

    def test_invalid_cli_and_failed_atomic_publication_preserve_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, report = root / "request.json", root / "report.json"
            request.write_text(self.check.to_json())
            report.write_text("prior diagnostic evidence")
            code, _, errors = self.call(
                ["synthetic-explore", "--request", request, "--output", report]
            )
            self.assertEqual(code, 2)
            self.assertIn("disagree", errors)
            self.assertEqual(report.read_text(), "prior diagnostic evidence")
            with patch(
                "biocompiler.cli.os.replace", side_effect=OSError("disk unavailable")
            ):
                code, _, errors = self.call(
                    ["synthetic-check", "--request", request, "--output", report]
                )
                self.assertEqual(code, 2)
            self.assertEqual(report.read_text(), "prior diagnostic evidence")
            self.assertEqual(
                {path.name for path in root.iterdir()}, {"request.json", "report.json"}
            )
            original = request.read_text()
            code, _, errors = self.call(
                ["synthetic-check", "--request", request, "--output", request]
            )
            self.assertEqual(code, 2)
            self.assertIn("independent input authority", errors)
            self.assertEqual(request.read_text(), original)


if __name__ == "__main__":
    unittest.main()
