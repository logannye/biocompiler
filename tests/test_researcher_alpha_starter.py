"""Pure starter copy-plan tests; no wheel assembly, native execution or network."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import researcher_alpha_starter as starter


class ResearcherStarterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in starter.SOURCE_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("INERT SOURCE\n")
        self.output = self.root / "output"
        self.output.mkdir()
        self.sdk = self.root / "sdk.whl"
        self.sdk.write_bytes(b"INERT SDK BYTES, NEVER INSTALLED")
        self.candidate_path = self.root / "candidate.json"
        self.natives = {}
        for target in ("linux-x86_64", "macos-arm64"):
            wheel = self.root / (target + ".whl")
            wheel.write_bytes(b"INERT NATIVE BYTES, NEVER EXECUTED")
            self.natives[target] = {"native": wheel}
        self.identity = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "12", "run_attempt": "1"}
        self.comparison = {"schema_version": "biocompiler.policy_material_prebuilt_campaign.v0.4", "status": "pass",
            **self.identity, "researcher_project": {"status": "pass"}, "slots": [
                {"slot": [system, machine, minor]} for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
                for minor in ("3.11", "3.14")]}
        self.candidate = {"sdk": starter.pin(self.sdk.read_bytes()), "source_revision": self.identity["head_revision"],
            "tested_revision": self.identity["revision"], "run_id": self.identity["run_id"], "platforms": {
                name: {"name": row["native"].name, **starter.pin(row["native"].read_bytes())}
                for name, row in self.natives.items()}}
        self.slots = [self.root / ("slot" + str(index)) for index in range(4)]
        evidence = self.slots[0] / "evidence"
        (evidence / "researcher-alpha").mkdir(parents=True)
        self.child = {**self.identity, "status": "pass", "files": {}, "system": "Linux", "machine": "x86_64", "python_version": "3.11.15"}
        for name in ("staged-project.json", "comparison-project.json", "staged.zip", "comparison.zip"):
            relative = "researcher-alpha/" + name
            (evidence / relative).write_bytes(b"INERT PAIRED EXAMPLE")
            measured = starter.pin((evidence / relative).read_bytes())
            self.child["files"][relative] = {"sha256": measured["sha256"], "bytes": measured["size"]}
        (evidence / "researcher-alpha.json").write_text(json.dumps(self.child))
        measured_child = starter.pin((evidence / "researcher-alpha.json").read_bytes())
        self.comparison["researcher_project"]["attempts"] = [{"slot": ["Linux", "x86_64", "3.11"],
            "run_attempt": "1", "receipt": {"sha256": measured_child["sha256"], "bytes": measured_child["size"]}}]
        self.candidate_path.write_text(json.dumps(self.candidate))
        self.save_comparison()
        self.args = SimpleNamespace(sdk=self.sdk, release_candidate=self.candidate_path, output_dir=self.output, compare=self.slots)

    def save_comparison(self):
        (self.output / "prebuilt-comparison.json").write_text(json.dumps(self.comparison))

    def plan(self):
        return starter.plan(self.args, self.comparison, self.natives, root=self.root)

    def test_exact_copy_plan_keeps_installed_candidate_scope(self):
        files, manifest = self.plan()
        self.assertEqual(len(files), len(starter.SOURCE_FILES) + 10)
        self.assertEqual(set(files), set(manifest["files"]))
        self.assertEqual(manifest["status"], "installed_candidate")
        self.assertEqual(manifest["release_acceptance"], "pending_overall_and_actual_main_gates")
        self.assertEqual(manifest["empirical"], "unassessed")
        self.assertEqual(manifest["real_researcher_project"], "unqualified")
        self.assertFalse((self.output / "researcher-starter").exists())

    def test_partial_or_duplicate_slots_cannot_prepare_a_handoff(self):
        original = deepcopy(self.comparison)
        for mutate in (lambda: self.comparison.update(status="failed"),
                       lambda: self.comparison["researcher_project"].update(status="failed"),
                       lambda: self.comparison["slots"].pop(),
                       lambda: self.comparison["slots"].__setitem__(0, self.comparison["slots"][1])):
            mutate()
            self.save_comparison()
            with self.assertRaises(ValueError):
                self.plan()
            self.comparison = deepcopy(original)

    def test_changed_wheel_example_or_saved_comparison_is_rejected(self):
        paths = [self.sdk, self.natives["linux-x86_64"]["native"],
                 self.slots[0] / "evidence/researcher-alpha/staged.zip",
                 self.output / "prebuilt-comparison.json"]
        for path in paths:
            raw = path.read_bytes()
            path.write_bytes(b"{}")
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.plan()
            path.write_bytes(raw)

    def test_stale_source_or_run_does_not_transfer_candidate_identity(self):
        for key in ("source_revision", "tested_revision", "run_id"):
            candidate = deepcopy(self.candidate)
            candidate[key] = "stale"
            self.candidate_path.write_text(json.dumps(candidate))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "identity"):
                self.plan()
        self.candidate_path.write_text(json.dumps(self.candidate))

    def test_receipt_and_example_cannot_self_authorize_a_post_comparison_change(self):
        evidence = self.slots[0] / "evidence"
        example = evidence / "researcher-alpha/staged.zip"
        example.write_bytes(b"changed example with matching child hash")
        measured = starter.pin(example.read_bytes())
        self.child["files"]["researcher-alpha/staged.zip"] = {"sha256": measured["sha256"], "bytes": measured["size"]}
        (evidence / "researcher-alpha.json").write_text(json.dumps(self.child))
        with self.assertRaisesRegex(ValueError, "independent installed comparison"):
            self.plan()

    def test_bounds_redirects_and_local_assembly_fail_closed(self):
        source = self.root / starter.SOURCE_FILES[0]
        source.unlink()
        source.symlink_to(self.sdk)
        with self.assertRaisesRegex(ValueError, "redirected"):
            self.plan()
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "hosted-only"):
            starter.create_starter(self.args, self.comparison, self.natives)

    def test_distributed_sources_require_the_complete_tested_git_tree(self):
        rows = []
        for name in starter.SOURCE_FILES:
            raw = (self.root / name).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            rows.append(f"100644 blob {blob}\t{name}".encode())
        with patch.object(starter.subprocess, "check_output", return_value=b"\0".join(rows)) as git:
            result = starter.source_authority(self.root, self.identity["revision"])
            self.assertEqual(set(result), set(starter.SOURCE_FILES))
            git.assert_called_once_with(["git", "ls-tree", "-r", "-z", self.identity["revision"], "--", *starter.SOURCE_FILES], cwd=self.root)
            (self.root / starter.SOURCE_FILES[0]).write_text("late mutation")
            with self.assertRaisesRegex(ValueError, "tested revision"):
                starter.source_authority(self.root, self.identity["revision"])


if __name__ == "__main__":
    unittest.main()
