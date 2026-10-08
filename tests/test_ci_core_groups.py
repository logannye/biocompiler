"""The bounded executor must retain whole original groups and complete accounting."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools import ci_core_groups as runner

ROOT = Path(__file__).resolve().parents[1]
PLAN_PIN = "27c418288415ea541d684b3ef92657c1882a1bcf05e8ddd8945bd68863352189"


class CoreGroupTests(unittest.TestCase):
    def group(self, index, script):
        return {"id": f"group-{index:02d}", "name": "inert group " + str(index),
                "run": script, "environment": {}}

    def test_original_complete_plan_and_distinct_output_paths(self):
        raw = (ROOT / "tools/ci_core_groups.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), PLAN_PIN)
        plan = runner.load_plan(ROOT)
        self.assertEqual(len(plan), 67)
        self.assertEqual(len({row["name"] for row in plan}), 67)
        import re
        paths = [path for row in plan for path in re.findall(r"(?:tee |--output [\"']?\$GITHUB_WORKSPACE/|--output )(generated/core/[^\s\"']+)", row["run"])]
        self.assertEqual(len(paths), 79)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(sum(bool(row["environment"]) for row in plan), 3)
        for row in plan:
            for path in re.findall(r'\$GITHUB_WORKSPACE/((?:tests/conformance|protocol)/[^\"\s]+)', row["run"]):
                self.assertTrue((ROOT / path).exists(), path)

    def test_changed_missing_duplicate_reordered_recipe_is_rejected(self):
        original = json.loads((ROOT / "tools/ci_core_groups.json").read_bytes())
        for mutation in ("missing", "duplicate", "reorder", "command"):
            changed = deepcopy(original)
            groups = changed["groups"]
            if mutation == "missing": groups.pop()
            if mutation == "duplicate": groups.append(groups[0])
            if mutation == "reorder": groups.reverse()
            if mutation == "command": groups[0]["run"] = "true\n"
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "tools").mkdir()
                (root / "tools/ci_core_groups.json").write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "plan changed"):
                    runner.load_plan(root)

    def test_two_groups_overlap_and_keep_original_receipt_order(self):
        barrier = threading.Barrier(2, timeout=5)
        observed = []
        lock = threading.Lock()
        def execute(root, output, row):
            with lock: observed.append(row["id"])
            barrier.wait()
            return row
        groups = [self.group(i, "true") for i in range(4)]
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "run_group", side_effect=execute):
            rows = runner.execute_groups(Path(directory), Path(directory) / "out", groups, 2)
        self.assertEqual(rows, groups)
        self.assertCountEqual(observed, [row["id"] for row in groups])

    def test_shell_order_pipefail_all_groups_and_full_logs(self):
        groups = [self.group(0, "printf first; printf second\n"),
                  self.group(1, "false | cat\nprintf should-not-run\n"),
                  self.group(2, "printf later-group\n")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "out"
            rows = runner.execute_groups(root, output, groups, 2)
            self.assertEqual([r["status"] for r in rows], ["pass", "fail", "pass"])
            self.assertEqual((output / "group-00.log").read_bytes(), b"firstsecond")
            self.assertNotIn(b"should-not-run", (output / "group-01.log").read_bytes())
            self.assertEqual((output / "group-02.log").read_bytes(), b"later-group")

    def test_timeout_and_spawn_failure_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A pure Python sleeping child, no project native executable.
            import shlex
            group = self.group(0, shlex.quote(sys.executable) + " -c 'import time; time.sleep(30)'")
            row = runner.run_group(root, root, group, timeout=0.05)
            self.assertEqual(row["status"], "timeout")
            with patch.object(runner.subprocess, "Popen", side_effect=OSError("inert spawn failure")):
                row = runner.run_group(root, root, self.group(1, "true"))
            self.assertEqual(row["status"], "error")
            self.assertIn(b"inert spawn failure", (root / "group-01.log").read_bytes())

    def test_receipts_reject_stale_missing_duplicate_failed_and_modified_logs(self):
        groups = [self.group(i, "printf complete") for i in range(2)]
        identity = {"revision": "a" * 40, "run_id": "123", "run_attempt": "1"}
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "load_plan", return_value=groups), \
                patch.object(runner.ci, "identity", return_value=identity), patch.dict(os.environ, {"GITHUB_HEAD_SHA": "b" * 40}):
            root = Path(directory); output = root / "out"
            document = runner.run(root, output, 2)
            self.assertEqual(runner.check(root, output), document)
            for mutation in ("stale", "source", "platform", "missing", "duplicate", "reorder", "failed", "log"):
                changed = deepcopy(document)
                if mutation == "stale": changed["run_id"] = "122"
                if mutation == "source": changed["source_revision"] = "c" * 40
                if mutation == "platform": changed["system"] = "other"
                if mutation == "missing": changed["groups"].pop()
                if mutation == "duplicate": changed["groups"].append(changed["groups"][0])
                if mutation == "reorder": changed["groups"].reverse()
                if mutation == "failed": changed["groups"][0]["returncode"] = 1
                if mutation == "log": changed["groups"][0]["log"]["sha256"] = "0" * 64
                runner.ci.write_json(output / "receipt.json", changed)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    runner.check(root, output)
            runner.ci.write_json(output / "receipt.json", document)
            (output / "group-00.log").write_text("changed")
            with self.assertRaisesRegex(ValueError, "changed direct-core"):
                runner.check(root, output)

    def test_worker_count_is_bounded_before_execution(self):
        for workers in (0, 3, True):
            with tempfile.TemporaryDirectory() as directory, patch.object(runner, "run_group") as execute:
                with self.assertRaises(ValueError):
                    runner.execute_groups(Path(directory), Path(directory) / "out", [], workers)
                execute.assert_not_called()

    def test_workflow_runs_and_checks_complete_plan_before_success(self):
        import inspect
        self.assertIsNone(inspect.signature(runner.run_group).parameters["timeout"].default)
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        job = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-sdk:\n", 1)[0]
        run = "python tools/ci_core_groups.py run --output generated/core/command-groups --workers 2"
        check = "python tools/ci_core_groups.py check --output generated/core/command-groups"
        self.assertEqual(job.count(run), 1)
        self.assertEqual(job.count(check), 1)
        self.assertLess(job.index("tools/ci_native_bundle.py restore"), job.index(run))
        self.assertLess(job.index(run), job.index(check))
        self.assertLess(job.index(check), job.index("Record successful complete ocaml-core"))
        self.assertIn("steps.restore_native.outcome == 'success'", job)
        self.assertNotIn("continue-on-error", job)
        self.assertIn("timeout-minutes: 60", job)
        self.assertIn("tests.test_ci_core_groups", text.split("\n  unit-plan:", 1)[0])


if __name__ == "__main__":
    unittest.main()
