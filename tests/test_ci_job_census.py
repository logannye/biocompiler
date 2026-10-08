"""Inert actual-job provenance controls; no network, builds or native execution."""
from copy import deepcopy
import unittest

from tools import ci_job_census as census


class JobCensusTests(unittest.TestCase):
    def fixture(self, scope="full"):
        expected = {"run_id": "123", "run_attempt": "2", "source_revision": "a" * 40,
                    "repository": "owner/repo", "event": "pull_request", "workflow_path": ".github/workflows/ci.yml",
                    "revision": "b" * 40}
        full = {census.FINAL, "build (Linux)", "build (Darwin)", "unit-tests (3.11, 0)"}
        skipped = {"build", "unit-tests"}
        families = {"build": {"build (Linux)", "build (Darwin)"}, "unit-tests": {"unit-tests (3.11, 0)"}}
        wanted = full | census.ROUTING if scope == "full" else skipped | census.ROUTING | {census.FINAL}
        rows = []
        for index, name in enumerate(sorted(wanted)):
            is_final = name == census.FINAL
            should_skip = name == "docs-validation" if scope == "full" else name in skipped
            rows.append({"id": index + 1, "name": name, "run_id": 123, "run_attempt": 2,
                         "head_sha": "a" * 40, "status": "in_progress" if is_final else "completed",
                         "conclusion": None if is_final else "skipped" if should_skip else "success"})
        run = {"id": 123, "run_attempt": 2, "head_sha": "a" * 40, "repository": {"full_name": "owner/repo"},
               "event": "pull_request", "path": ".github/workflows/ci.yml", "status": "in_progress", "conclusion": None}
        return {"run": run, "pages": [{"total_count": len(rows), "jobs": rows}]}, {
            "expected": expected, "scope": scope, "full_job_names": full,
            "skipped_job_keys": skipped, "full_job_families": families}

    def rows(self, payload):
        return payload["pages"][0]["jobs"]

    def row(self, payload, name="build (Linux)"):
        return next(row for row in self.rows(payload) if row["name"] == name)

    def add(self, payload, row):
        self.rows(payload).append(row)
        payload["pages"][0]["total_count"] += 1

    def test_full_and_docs_routes_keep_distinct_exact_censuses(self):
        for scope in ("full", "docs_only"):
            payload, args = self.fixture(scope)
            result = census.validate_census(payload, **args)
            self.assertEqual(result["scope"], scope)
            self.assertEqual(set(result["selected"]), {row["name"] for row in self.rows(payload)})
            self.assertEqual(result["job_count"], len(self.rows(payload)))
            self.assertEqual(result["superseded"], [])
            # No receipt or qualification is manufactured from GitHub job state.
            self.assertNotIn("native_qualification", result)
            self.assertNotIn("jobs", result)

    def test_source_sha_is_not_synthetic_tested_revision(self):
        payload, args = self.fixture()
        self.assertNotEqual(args["expected"]["revision"], payload["run"]["head_sha"])
        result = census.validate_census(payload, **args)
        self.assertEqual(result["identity"]["source_revision"], "a" * 40)
        payload["run"]["head_sha"] = "b" * 40
        with self.assertRaises(ValueError): census.validate_census(payload, **args)

    def test_preserved_success_keeps_its_actual_earlier_attempt(self):
        payload, args = self.fixture()
        self.row(payload)["run_attempt"] = 1
        result = census.validate_census(payload, **args)
        self.assertEqual(result["selected"]["build (Linux)"]["run_attempt"], 1)

    def test_latest_actual_attempt_wins_independently_of_id_order_or_prior_failure(self):
        payload, args = self.fixture()
        old = {**self.row(payload), "id": 999, "run_attempt": 1, "conclusion": "failure"}
        self.add(payload, old)
        self.rows(payload).reverse()
        result = census.validate_census(payload, **args)
        self.assertEqual(result["selected"]["build (Linux)"]["run_attempt"], 2)
        self.assertEqual(result["superseded"], [old])

    def test_old_collapsed_skip_is_retained_after_every_expanded_slot_retries(self):
        payload, args = self.fixture()
        old = {**self.row(payload), "id": 999, "name": "build", "run_attempt": 1, "conclusion": "skipped"}
        self.add(payload, old)
        original = deepcopy(payload)
        result = census.validate_census(payload, **args)
        self.assertEqual(set(result["selected"]), args["full_job_names"] | census.ROUTING)
        self.assertEqual(result["superseded"], [old])
        self.assertEqual(result["job_count"], result["selected_count"] + 1)
        self.assertEqual(payload, original)
        result["superseded"][0]["conclusion"] = "changed"
        self.assertEqual(payload, original)

    def test_collapsed_skip_requires_strictly_later_attempt_for_every_family_slot(self):
        for selected_attempt, collapsed_attempt in ((1, 1), (2, 2), (2, 3)):
            payload, args = self.fixture()
            self.row(payload, "build (Darwin)")["run_attempt"] = selected_attempt
            self.add(payload, {**self.row(payload), "id": 999, "name": "build",
                               "run_attempt": collapsed_attempt, "conclusion": "skipped"})
            with self.subTest(selected=selected_attempt, collapsed=collapsed_attempt), self.assertRaises(ValueError):
                census.validate_census(payload, **args)

    def test_collapsed_history_must_be_skipped_authenticated_and_unambiguous(self):
        changes = ({"conclusion": "success"}, {"conclusion": "failure"}, {"conclusion": "cancelled"},
                   {"status": "in_progress", "conclusion": None}, {"status": "queued"},
                   {"run_id": 124}, {"head_sha": "c" * 40}, {"name": "build-other"})
        for change in changes:
            payload, args = self.fixture()
            old = {**self.row(payload), "id": 999, "name": "build", "run_attempt": 1,
                   "conclusion": "skipped", **change}
            self.add(payload, old)
            with self.subTest(change=change), self.assertRaises(ValueError):
                census.validate_census(payload, **args)
        for duplicate_id in (False, True):
            payload, args = self.fixture()
            old = {**self.row(payload), "id": 999, "name": "build", "run_attempt": 1, "conclusion": "skipped"}
            self.add(payload, old)
            self.add(payload, {**old, "id": old["id"] if duplicate_id else 1000})
            with self.subTest(duplicate_id=duplicate_id), self.assertRaisesRegex(ValueError, "Duplicate actual"):
                census.validate_census(payload, **args)

    def test_old_collapsed_skip_cannot_replace_missing_or_failed_expanded_work(self):
        for outcome in ("missing", "failure", "skipped", "cancelled"):
            payload, args = self.fixture()
            self.add(payload, {**self.row(payload), "id": 999, "name": "build",
                               "run_attempt": 1, "conclusion": "skipped"})
            if outcome == "missing":
                self.rows(payload).remove(self.row(payload)); payload["pages"][0]["total_count"] -= 1
            else:
                self.row(payload)["conclusion"] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                census.validate_census(payload, **args)

    def test_family_mapping_must_partition_exact_registered_jobs_without_prefix_inference(self):
        mappings = ({}, {"build": {"build (Linux)", "build (Darwin)"}},
                    {"build": {"build (Linux)"}, "unit-tests": {"unit-tests (3.11, 0)"}},
                    {"build": {"build (Linux)", "build (Darwin)"}, "unit-tests": {"build (Linux)", "unit-tests (3.11, 0)"}},
                    {"build": {"build (Linux)", "build (Darwin)", "unknown"}, "unit-tests": {"unit-tests (3.11, 0)"}},
                    {"build": {"build (Linux)", "build (Darwin)"}, "unit-tests": ["unit-tests (3.11, 0)"]})
        for mapping in mappings:
            for scope in ("full", "docs_only"):
                payload, args = self.fixture(scope)
                with self.subTest(mapping=mapping, scope=scope), self.assertRaises(ValueError):
                    census.validate_census(payload, **{**args, "full_job_families": mapping})

    def test_docs_route_does_not_accept_historical_expanded_execution(self):
        payload, args = self.fixture("docs_only")
        self.add(payload, {**self.row(payload, "build"), "id": 999, "name": "build (Linux)",
                           "run_attempt": 1, "conclusion": "success"})
        with self.assertRaisesRegex(ValueError, "Unknown or malformed actual job"):
            census.validate_census(payload, **args)

    def test_newer_failure_cancel_or_incomplete_cannot_hide_behind_old_success(self):
        for status, conclusion in (("completed", "failure"), ("completed", "cancelled"),
                                   ("completed", "skipped"), ("in_progress", None), ("queued", None),
                                   ("completed", "neutral"), ("completed", "timed_out")):
            with self.subTest(status=status, conclusion=conclusion):
                payload, args = self.fixture()
                self.add(payload, {**self.row(payload), "id": 999, "run_attempt": 1})
                self.row(payload).update(status=status, conclusion=conclusion)
                with self.assertRaisesRegex(ValueError, "Latest actual job"):
                    census.validate_census(payload, **args)

    def test_duplicate_ids_and_name_attempts_are_rejected_even_if_successful(self):
        for same_id in (False, True):
            payload, args = self.fixture()
            duplicate = deepcopy(self.row(payload))
            if not same_id: duplicate["id"] = 999
            self.add(payload, duplicate)
            with self.assertRaisesRegex(ValueError, "Duplicate actual"):
                census.validate_census(payload, **args)
        payload, args = self.fixture()
        self.rows(payload)[1]["id"] = self.rows(payload)[0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate actual"):
            census.validate_census(payload, **args)

    def test_missing_extra_or_collapsed_full_matrix_slot_cannot_pass(self):
        for mutation in ("missing", "extra", "collapsed"):
            payload, args = self.fixture()
            if mutation == "missing":
                self.rows(payload).remove(self.row(payload)); payload["pages"][0]["total_count"] -= 1
            elif mutation == "extra":
                self.add(payload, {**self.row(payload), "id": 999, "name": "unregistered"})
            else:
                self.row(payload)["name"] = "build"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                census.validate_census(payload, **args)

    def test_docs_cannot_claim_executed_full_jobs_or_full_route_missing_checks(self):
        for scope in ("full", "docs_only"):
            payload, args = self.fixture(scope)
            name = "docs-validation" if scope == "full" else "build"
            self.row(payload, name)["conclusion"] = "success"
            with self.assertRaises(ValueError): census.validate_census(payload, **args)
        payload, args = self.fixture("docs_only")
        self.row(payload, "change-scope")["conclusion"] = "skipped"
        with self.assertRaises(ValueError): census.validate_census(payload, **args)

    def test_only_current_final_job_may_be_in_progress(self):
        for change in ({"run_attempt": 1}, {"status": "completed", "conclusion": "success"},
                       {"status": "queued"}, {"conclusion": "failure"}):
            payload, args = self.fixture(); self.row(payload, census.FINAL).update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                census.validate_census(payload, **args)
        payload, args = self.fixture()
        old = {**self.row(payload, census.FINAL), "id": 999, "run_attempt": 1,
               "status": "completed", "conclusion": "success"}
        self.add(payload, old)
        self.assertEqual(census.validate_census(payload, **args)["selected"][census.FINAL]["run_attempt"], 2)

    def test_run_repository_event_workflow_source_attempt_and_state_are_authenticated(self):
        for field, value in (("id", 124), ("run_attempt", 1), ("run_attempt", True), ("head_sha", "c" * 40),
                             ("repository", {"full_name": "other/repo"}), ("event", "push"), ("path", "other.yml"),
                             ("status", "completed"), ("conclusion", "success")):
            payload, args = self.fixture(); payload["run"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                census.validate_census(payload, **args)

    def test_every_historical_job_must_belong_to_exact_run_source_and_valid_attempt(self):
        for change in ({"run_id": 124}, {"head_sha": "c" * 40}, {"run_attempt": 3},
                       {"run_attempt": 0}, {"run_attempt": True}, {"id": True}):
            payload, args = self.fixture()
            old = {**self.row(payload), "id": 999, "run_attempt": 1, **change}
            self.add(payload, old)
            with self.subTest(change=change), self.assertRaises(ValueError): census.validate_census(payload, **args)

    def test_complete_paginated_input_is_required(self):
        payload, args = self.fixture(); rows = self.rows(payload)
        payload["pages"] = [{"total_count": len(rows), "jobs": rows[:2]}, {"total_count": len(rows), "jobs": rows[2:]}]
        self.assertEqual(census.validate_census(payload, **args)["job_count"], len(rows))
        for mutation in ("omit", "changed_total", "duplicate_page", "empty_page", "missing_total", "bool_total"):
            changed = deepcopy(payload)
            if mutation == "omit": changed["pages"].pop()
            elif mutation == "changed_total": changed["pages"][1]["total_count"] += 1
            elif mutation == "duplicate_page": changed["pages"].append(deepcopy(changed["pages"][0]))
            elif mutation == "empty_page": changed["pages"].append({"total_count": len(rows), "jobs": []})
            elif mutation == "missing_total": del changed["pages"][0]["total_count"]
            else: changed["pages"][0]["total_count"] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): census.validate_census(changed, **args)

    def test_input_bounds_and_unknown_scope_fail_closed(self):
        payload, args = self.fixture()
        for scope in ("docs", "", None):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                census.validate_census(payload, **{**args, "scope": scope})
        for pages in ([], [{}] * (census.MAX_PAGES + 1), [{"total_count": census.MAX_JOBS + 1, "jobs": [{}]}]):
            with self.assertRaises(ValueError): census.validate_census({**payload, "pages": pages}, **args)
        for field, value in (("run_attempt", "02"), ("run_attempt", 2), ("run_id", "0"), ("source_revision", "bad")):
            changed = deepcopy(args); changed["expected"][field] = value
            with self.assertRaises(ValueError): census.validate_census(payload, **changed)

    def test_selected_evidence_is_detached_and_input_is_unchanged(self):
        payload, args = self.fixture(); original = deepcopy(payload)
        result = census.validate_census(payload, **args)
        self.assertEqual(payload, original)
        result["selected"]["build (Linux)"]["conclusion"] = "changed"
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
