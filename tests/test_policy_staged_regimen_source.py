from copy import deepcopy
import json
from pathlib import Path
import unittest

from biocompiler import policy as p
from tools import generate_policy_staged_regimen_fixture as fixture
from tools import check_policy_staged_regimen_source as witness


class StagedRegimenSourceTests(unittest.TestCase):
    def test_public_authoring_matches_frozen_independent_original(self):
        path = Path(__file__).resolve().parents[1] / fixture.PATH
        frozen = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(fixture.fixture(), frozen)
        self.assertEqual(p.to_data(fixture.build_program()), frozen["document"])
        self.assertEqual(frozen["claim_scope"], "bounded_abstract_source_execution_only")

    def test_same_operation_distinct_effects_and_encounter_lifetime(self):
        document = p.to_data(fixture.build_program())
        rows = {row["id"]: row for row in document["declarations"]}
        self.assertEqual(rows["stage_one"]["contract"], rows["stage_two"]["contract"])
        self.assertEqual(rows["regimen/stages"]["lifetime"], "encounter")
        self.assertEqual(rows["condition"]["coverage"], "event")
        self.assertEqual(rows["condition"]["coherence"], "frame")
        transitions = [row for row in rows.values() if row["$type"] == "Transition"]
        self.assertEqual(len(transitions), 7)
        self.assertEqual([(row["source"], row["destination"]) for row in transitions if row["on"]["value"] == "timed_out"],
                         [("first", "failed"), ("second", "failed")])

    def test_finite_source_census_and_exact_deadline_literals(self):
        cases = fixture.fixture()["cases"]
        self.assertEqual(tuple(row["id"] for row in cases), witness.CASE_IDS)
        self.assertEqual(len(witness.OBSERVATIONS), 33)
        self.assertEqual(len(set(witness.OBSERVATIONS)), 33)
        for case in cases:
            self.assertEqual([row["time"] for row in case["expected"]["frames"]], list(map(str, range(7))))
            self.assertEqual(case["timeline"]["horizon"], "6")
            for attempt in case["expected"]["attempts"]:
                self.assertEqual(int(attempt["deadline"]), int(attempt["started_at"]) + 2)

    def test_inactive_handoff_guard_is_never_queued_for_later_truth(self):
        cases = {row["id"]: row for row in fixture.fixture()["cases"]}
        for identity in ("false_handoff_no_retry", "unknown_handoff_no_retry"):
            case = cases[identity]
            self.assertEqual([row["effect"] for row in case["expected"]["attempts"]], ["stage_one", "stage_one"])
            for frame in case["expected"]["frames"][2:]:
                self.assertEqual(frame["machines"][0]["state"], "first")
                self.assertEqual(frame["machines"][0]["attempts"], ["attempt/1"])
            self.assertIn({"id": "stale-completion", "reason": "stale_attempt"}, case["expected"]["feedback_rejected"])

    def test_literal_checker_rejects_state_or_attempt_mutation_before_replay(self):
        case = fixture.fixture()["cases"][0]
        # Only these inert fields are needed to reach the corresponding guards;
        # no synthetic execution is claimed or accepted by this test.
        partial = {"claim": "bounded_supplied_timeline_only", "frames": deepcopy(case["expected"]["frames"]),
                   "attempts": deepcopy(case["expected"]["attempts"])}
        state = deepcopy(partial)
        state["frames"][2]["machines"][0]["state"] = "completed"
        with self.assertRaisesRegex(AssertionError, "machine snapshots"):
            witness.check_literals(state, case)
        wrong_attempt = deepcopy(partial)
        wrong_attempt["attempts"][2]["binding"]["encounter"] = "e2"
        with self.assertRaisesRegex(AssertionError, "attempt identity"):
            witness.check_literals(wrong_attempt, case)


if __name__ == "__main__":
    unittest.main()
