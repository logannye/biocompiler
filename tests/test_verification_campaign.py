"""Exercise bounded exploration against real independent compiler engines."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from cellweave.cli import main
from cellweave.verification.evidence import CheckOutcome, EvidenceKind
from cellweave.verification.exploration import ExplorationReport, ReductionResult
from examples.verification_campaign import run_campaign


class VerificationCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.stress_config, cls.cases, cls.outcomes, cls.reduced = (
            run_campaign()
        )

    def test_presence_aware_space_complete_and_coverage_explicit(self):
        self.assertEqual(self.report.state_count, 25)
        self.assertEqual(self.report.possible_histories, 625)
        self.assertEqual(self.report.evaluated_histories, 625)
        self.assertTrue(self.report.complete)
        self.assertTrue(self.report.all_passed)
        self.assertTrue(
            all(
                result.evidence_kind is EvidenceKind.MODEL_CONDITIONAL
                for result in self.report.results
            )
        )
        self.assertTrue(
            all(
                item.activation_deadlines_checked > 0
                and item.inactive_deadlines_checked > 0
                for result in self.report.results
                for item in result.coverage
            )
        )
        self.assertGreater(self.outcomes.get("unknown", 0), 0)
        self.assertTrue(any(case.intentionally_incomplete for case in self.cases))
        self.assertTrue(
            all(
                case.config_fingerprint == self.stress_config.fingerprint
                for case in self.cases
            )
        )

    def test_reduction_keeps_selected_failure_and_explicit_horizon(self):
        self.assertEqual(self.reduced.history[0].time, 0)
        self.assertLess(len(self.reduced.history), 7)
        self.assertTrue(self.reduced.one_minimal)
        self.assertEqual(self.reduced.result.outcome, CheckOutcome.FAIL)
        self.assertEqual(
            self.reduced.result.dependencies.values["horizon"]["effective"], 7
        )
        self.assertTrue(
            any(
                item.expected["state"] == "active"
                for item in self.reduced.result.counterexamples
            )
        )

    def test_reports_roundtrip_and_cli_inspection_cannot_recheck(self):
        for artifact, kind in (
            (self.report, ExplorationReport),
            (self.reduced, ReductionResult),
        ):
            self.assertEqual(kind.from_json(artifact.to_json()), artifact)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "report.json"
                path.write_text(artifact.to_json(), encoding="utf-8")
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["inspect", str(path)]), 0)
                self.assertIn("Historical", output.getvalue())
                self.assertIn(artifact.fingerprint, output.getvalue())


if __name__ == "__main__":
    unittest.main()
