"""Pure CAR handoff plans with inert bytes; no packaging or native execution."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import car_payload_starter as starter


class CarStarterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in starter.SOURCE_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"INERT SOURCE DATA")
        self.output = self.root / "output"
        self.output.mkdir()
        self.sdk = self.root / "sdk.whl"
        self.sdk.write_bytes(b"INERT SDK, NEVER INSTALLED")
        self.natives = {}
        for target in ("linux-x86_64", "macos-arm64"):
            wheel = self.root / (target + ".whl")
            wheel.write_bytes(b"INERT NATIVE, NEVER EXECUTED")
            self.natives[target] = {"native": wheel}
        self.identity = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "12", "run_attempt": "3"}
        self.comparison = {"schema_version": starter.PREBUILT_SCHEMA, "status": "pass", "claim": starter.PREBUILT_CLAIM,
            **self.identity, "slots": [{"slot": list(slot)} for slot in sorted(starter.SLOTS)],
            **{name: {"status": "pass"} for name in ("material", "consumer", "component_material", "component_consumer",
                "staged_material", "researcher_project", "car_payload")}}
        self.candidate = {"sdk": starter.pin(self.sdk.read_bytes()), "source_revision": self.identity["head_revision"],
            "tested_revision": self.identity["revision"], "run_id": self.identity["run_id"], "platforms": {
                name: {"name": row["native"].name, **starter.pin(row["native"].read_bytes())} for name, row in self.natives.items()}}
        self.candidate_path = self.root / "candidate.json"
        self.candidate_path.write_text(json.dumps(self.candidate))
        self.slots = [self.root / ("slot" + str(index)) for index in range(4)]
        evidence = self.slots[0] / "evidence"
        (evidence / "car-payload").mkdir(parents=True)
        self.child = {**self.identity, "run_attempt": "2", "status": "pass", "files": {}, "system": "Linux", "machine": "x86_64",
            "python_version": "3.11.15", "empirical": "unassessed", "human_use": "unassessed", "real_researcher_project_qualified": False}
        for name in starter.PUBLICATIONS:
            relative = "car-payload/" + name
            path = evidence / relative
            path.write_bytes(b"INERT EXACT PROJECT OR ARCHIVE " + name.encode())
            measured = starter.pin(path.read_bytes())
            self.child["files"][relative] = {"sha256": measured["sha256"], "bytes": measured["size"]}
        self.child_path = evidence / "car-payload.json"
        self.child_path.write_text(json.dumps(self.child))
        measured = starter.pin(self.child_path.read_bytes())
        self.comparison["car_payload"]["attempts"] = [{"slot": ["Linux", "x86_64", "3.11"], "run_attempt": "2",
            "receipt": {"sha256": measured["sha256"], "bytes": measured["size"]}}]
        self.save()
        self.args = SimpleNamespace(sdk=self.sdk, release_candidate=self.candidate_path, output_dir=self.output, compare=self.slots)
        blocked = patch.object(starter.subprocess, "Popen", side_effect=AssertionError("No process in pure CAR starter tests"))
        blocked.start(); self.addCleanup(blocked.stop)

    def save(self):
        (self.output / "prebuilt-comparison.json").write_text(json.dumps(self.comparison))

    def plan(self):
        return starter.plan(self.args, self.comparison, self.natives, root=self.root)

    def test_exact_distinct_plan_retains_conditional_scope_and_producer_attempt(self):
        files, manifest = self.plan()
        self.assertEqual(manifest["schema_version"], "biocompiler.car_payload_starter.v0.1")
        self.assertEqual(manifest["parent_comparison_schema"], starter.PREBUILT_SCHEMA)
        self.assertEqual(len(files), len(starter.SOURCE_FILES) + len(starter.PUBLICATIONS) + 6)
        self.assertEqual(set(files), set(manifest["files"]))
        self.assertEqual(manifest["run_attempt"], "3")
        self.assertEqual(manifest["example_producer_attempt"], "2")
        self.assertEqual(manifest["status"], "installed_candidate")
        self.assertEqual(manifest["release_acceptance"], "pending_overall_and_actual_main_gates")
        for name in ("empirical", "human_use"):
            self.assertEqual(manifest[name], "unassessed")
        self.assertEqual(manifest["real_researcher_project"], "unqualified")
        self.assertEqual(manifest["redistribution_or_manufacturing_rights"], "not_granted")
        self.assertEqual(sum(name.startswith("accepted-examples/") for name in files), 4)
        self.assertEqual(sum(name.startswith("rejected-controls/") for name in files), 3)
        self.assertFalse((self.output / "car-starter").exists())

    def test_each_required_gate_and_four_distinct_slots_remain_required(self):
        before = deepcopy(self.comparison)
        for name in ("material", "consumer", "component_material", "component_consumer", "staged_material", "researcher_project", "car_payload"):
            self.comparison = deepcopy(before); self.comparison[name]["status"] = "failed"; self.save()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "complete additive"):
                self.plan()
        for mutate in (lambda v: v.update(schema_version="biocompiler.policy_material_prebuilt_campaign.v0.4"),
                       lambda v: v.update(claim="universal"), lambda v: v["slots"].pop(),
                       lambda v: v["slots"].__setitem__(0, deepcopy(v["slots"][1]))):
            self.comparison = deepcopy(before); mutate(self.comparison); self.save()
            with self.assertRaises(ValueError):
                self.plan()

    def test_missing_platform_or_supplied_slot_rejects_partial_handoff(self):
        native = self.natives.pop("macos-arm64")
        with self.assertRaisesRegex(ValueError, "both validated native"):
            self.plan()
        self.natives["macos-arm64"] = native
        self.args.compare.pop()
        with self.assertRaisesRegex(ValueError, "four supplied"):
            self.plan()

    def test_changed_wheel_project_archive_and_saved_comparison_reject(self):
        paths = [self.sdk, self.natives["linux-x86_64"]["native"], self.output / "prebuilt-comparison.json"]
        paths += [self.slots[0] / "evidence/car-payload" / name for name in starter.PUBLICATIONS]
        for path in paths:
            original = path.read_bytes(); path.write_bytes(b"{}")
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.plan()
            path.write_bytes(original)

    def test_child_and_rehashed_artifact_cannot_self_authorize_change(self):
        name = next(iter(starter.PUBLICATIONS))
        path = self.slots[0] / "evidence/car-payload" / name
        path.write_bytes(b"altered and repinned untrusted example")
        measured = starter.pin(path.read_bytes())
        self.child["files"]["car-payload/" + name] = {"sha256": measured["sha256"], "bytes": measured["size"]}
        self.child_path.write_text(json.dumps(self.child))
        with self.assertRaisesRegex(ValueError, "independent installed comparison"):
            self.plan()

    def test_producer_attempt_cannot_be_relabelled_as_latest_comparison(self):
        self.child["run_attempt"] = self.identity["run_attempt"]
        self.child_path.write_text(json.dumps(self.child))
        with self.assertRaisesRegex(ValueError, "independent installed comparison"):
            self.plan()

    def test_stale_candidate_and_child_scope_reject(self):
        for key in ("source_revision", "tested_revision", "run_id"):
            self.candidate_path.write_text(json.dumps({**self.candidate, key: "stale"}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "identity"):
                self.plan()
        self.candidate_path.write_text(json.dumps(self.candidate))
        for key, value in (("revision", "stale"), ("head_revision", "stale"), ("run_id", "stale"),
                           ("empirical", "pass"), ("human_use", "approved"), ("real_researcher_project_qualified", True)):
            self.child_path.write_text(json.dumps({**self.child, key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "evidence scope"):
                self.plan()

    def test_complete_expected_and_reference_pack_are_mandatory_sources(self):
        for name in ("data/car_payload/expected.json", "src/biocompiler/policy/data/car_rm61461_reference_v01.json"):
            source = self.root / name; original = source.read_bytes(); source.unlink()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "starter input"):
                self.plan()
            source.write_bytes(original)

    def test_bounds_redirects_and_local_assembly_fail_closed(self):
        with patch.object(starter, "MAX_FILE", 4), self.assertRaisesRegex(ValueError, "oversized"):
            self.plan()
        with patch.object(starter, "MAX_TOTAL", 4), self.assertRaisesRegex(ValueError, "total byte bound"):
            self.plan()
        source = self.root / starter.SOURCE_FILES[0]; source.unlink(); source.symlink_to(self.sdk)
        with self.assertRaisesRegex(ValueError, "redirected"):
            self.plan()
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "hosted-only"):
            starter.create_starter(self.args, self.comparison, self.natives)

    def test_saved_parent_keeps_json_meaning_without_collapsing_scalar_types(self):
        self.comparison["car_payload"]["slots"] = sorted(starter.SLOTS)
        self.comparison["count"] = 1
        self.save(); self.plan()
        saved = json.loads((self.output / "prebuilt-comparison.json").read_text())
        saved["count"] = True
        (self.output / "prebuilt-comparison.json").write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "Saved CAR parent"):
            self.plan()

    def test_distributed_reference_docs_and_expected_require_exact_source_tree(self):
        rows = []
        for name in starter.SOURCE_FILES:
            raw = (self.root / name).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            rows.append(f"100644 blob {blob}\t{name}".encode())
        with patch.object(starter.subprocess, "check_output", return_value=b"\0".join(rows)) as git:
            self.assertEqual(set(starter.source_authority(self.root, self.identity["revision"])), set(starter.SOURCE_FILES))
            git.assert_called_once_with(["git", "ls-tree", "-r", "-z", self.identity["revision"], "--", *starter.SOURCE_FILES], cwd=self.root)
            (self.root / starter.SOURCE_FILES[-1]).write_bytes(b"changed public literal authority")
            with self.assertRaisesRegex(ValueError, "tested revision"):
                starter.source_authority(self.root, self.identity["revision"])
        for bad in (rows[:-1], rows + [rows[0]], [rows[0].replace(b"100644", b"120000")] + rows[1:]):
            with patch.object(starter.subprocess, "check_output", return_value=b"\0".join(bad)), self.assertRaises(ValueError):
                starter.source_authority(self.root, self.identity["revision"])


if __name__ == "__main__":
    unittest.main()
