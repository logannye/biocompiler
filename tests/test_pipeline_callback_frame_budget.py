"""Independent receipt-budget controls; fabricated traffic is not native parity."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_pipeline_manager_campaign import fake_frames
from tools import check_pipeline_manager_install as campaign


class CallbackFrameBudgetTests(unittest.TestCase):
    def fixture(self, directory, channel, application):
        directory.mkdir()
        receipt = {"_artifact_directory": str(directory), "artifacts": {}}
        with patch.object(campaign, "declarations", return_value=(channel, application)):
            rows = fake_frames(receipt)
        artifacts = campaign.Artifacts(directory, receipt["artifacts"])
        counts = [campaign.json_nodes(campaign.frame_body(artifacts.raw(row["frame"]))) for row in rows]
        return rows, artifacts, counts

    def test_independent_frame_and_lifetime_exact_and_one_short_bounds(self):
        channel, application = campaign.declarations()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            _, _, counts = self.fixture(directory / "baseline", channel, application)
            largest, total = max(counts), sum(counts)
            self.assertLess(largest, total)
            for frame_limit, lifetime_limit, diagnostic in (
                    (largest, total, None),
                    (largest - 1, total, "frame exceeds selected JSON node bound"),
                    (largest, total - 1, "Cumulative JSON node budget exceeded")):
                with self.subTest(frame_limit=frame_limit, lifetime_limit=lifetime_limit):
                    selected = deepcopy(channel)
                    selected["fixed_limits"]["max_frame_json_nodes"] = frame_limit
                    selected["limits"]["max_json_nodes"] = lifetime_limit
                    rows, artifacts, current_counts = self.fixture(
                        directory / f"{frame_limit}-{lifetime_limit}", selected, application)
                    self.assertEqual(current_counts, counts)
                    if diagnostic is None:
                        result = campaign.validate_frames(rows, artifacts, selected, application)
                        self.assertEqual(result["frames"], len(rows))
                    else:
                        with self.assertRaisesRegex(AssertionError, diagnostic):
                            campaign.validate_frames(rows, artifacts, selected, application)
