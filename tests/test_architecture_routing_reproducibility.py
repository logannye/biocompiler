"""Fail-closed four-way evidence comparison, using fake bytes and no binaries."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.check_architecture_routing_reproducibility import (
    CASES, CORPUS_PIN, PLATFORMS, PYTHONS, compare, expected_artifacts, expected_checks,
)


REVISION, SOURCE, RUN = "a" * 40, "b" * 40, "123456"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def fixture(root):
    checks = [{"id": identity, "operation": operation,
               **{key: "c" * 64 if value is None else value for key, value in values.items()}}
              for (identity, operation), values in expected_checks().items()]
    for platform, (system, machine) in PLATFORMS.items():
        slot = root / platform
        slot.mkdir(parents=True)
        pins = {}
        for role in ("core", "verify"):
            name = "biocompiler-" + role
            content = (platform + "/" + role).encode()
            (slot / name).write_bytes(content)
            pins[name] = hashlib.sha256(content).hexdigest()
        write(slot / "binaries.json", {"revision": REVISION, "system": system, "machine": machine, "sha256": pins})
        for python in PYTHONS:
            directory = slot / ("architecture-routing-" + python) / "artifacts"
            inventory = {}
            for name in expected_artifacts():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = ("complete fake artifact: " + name + "\n").encode()
                path.write_bytes(payload)
                inventory[name] = hashlib.sha256(payload).hexdigest()
            write(slot / ("architecture-routing-" + python + ".json"), {
                "schema_version": "biocompiler.architecture_routing_conformance.v1", "status": "success",
                "revision": REVISION, "source_revision": SOURCE, "run_id": RUN, "corpus_pin": CORPUS_PIN,
                "system": system, "machine": machine, "platform": "native metadata " + platform,
                "python_version": python + ".1", "completed_checks": 175, "python_semantics_blocked": True,
                "checks": checks, "artifacts": inventory, "artifacts_path": "/never/read/this/untrusted/host/path",
                "executables": {role: {"path": "/original/host/" + role, "sha256": pins["biocompiler-" + role]}
                                for role in ("core", "verify")},
            })


class ArchitectureRoutingReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        fixture(self.root)
        self.path = self.root / "linux-x86_64/architecture-routing-3.11.json"

    def run_comparison(self):
        return compare(self.root, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def change(self, mutate):
        value = json.loads(self.path.read_text())
        mutate(value)
        write(self.path, value)

    def test_complete_four_way_identity_preserves_platform_binaries_and_raw_receipt_pins(self):
        result = self.run_comparison()
        self.assertEqual((result["compared_runs"], result["checks_per_run"], result["artifact_count"]), (4, 175, 219))
        self.assertEqual(result["cases"], list(CASES))
        self.assertNotEqual(result["platform_binaries"]["linux-x86_64"]["sha256"], result["platform_binaries"]["macos-arm64"]["sha256"])
        self.assertEqual(result["source_receipts"]["linux-x86_64/3.11"]["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_stale_revision_source_run_and_failed_or_unguarded_execution_are_rejected(self):
        original = json.loads(self.path.read_text())
        for field, value in (("revision", "d" * 40), ("source_revision", "d" * 40), ("run_id", "other"),
                             ("status", "failure"), ("python_semantics_blocked", False), ("corpus_pin", "d" * 64)):
            with self.subTest(field=field):
                changed = deepcopy(original); changed[field] = value; write(self.path, changed)
                with self.assertRaises(AssertionError): self.run_comparison()
        write(self.path, original)

    def test_missing_duplicate_extra_and_incomplete_case_checks_are_rejected(self):
        original = json.loads(self.path.read_text())
        for mutation in (lambda r: r["checks"].pop(), lambda r: r["checks"].append(r["checks"][0]),
                         lambda r: r["checks"].__setitem__(1, r["checks"][0]),
                         lambda r: r["checks"][0].update(id="installed/unreviewed"),
                         lambda r: r.update(completed_checks=174),
                         lambda r: r["checks"][-1].update(preserved_output=False)):
            changed = deepcopy(original); mutation(changed); write(self.path, changed)
            with self.assertRaises(AssertionError): self.run_comparison()

    def test_wrong_python_platform_and_binary_role_pins_are_rejected(self):
        original = json.loads(self.path.read_text())
        for mutate in (lambda r: r.update(python_version="3.12.0"), lambda r: r.update(system="Darwin"),
                       lambda r: r.update(machine="arm64"), lambda r: r["executables"]["core"].update(sha256="d" * 64),
                       lambda r: r["executables"].pop("verify")):
            changed = deepcopy(original); mutate(changed); write(self.path, changed)
            with self.assertRaises(AssertionError): self.run_comparison()

    def test_stale_binary_manifest_and_changed_actual_binary_bytes_are_rejected(self):
        path = self.root / "linux-x86_64/binaries.json"
        original = json.loads(path.read_text())
        changed = deepcopy(original); changed["revision"] = "d" * 40; write(path, changed)
        with self.assertRaisesRegex(AssertionError, "Stale revision"): self.run_comparison()
        write(path, original)
        (path.parent / "biocompiler-core").write_bytes(b"substituted binary")
        with self.assertRaisesRegex(AssertionError, "binary bytes"): self.run_comparison()

    def test_missing_extra_empty_and_changed_artifact_bytes_are_rejected(self):
        root = self.path.with_suffix("") / "artifacts"
        path = root / "b/payloads.fasta"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(AssertionError, "Missing artifact"): self.run_comparison()
        for content in (b"", b"changed RNA"):
            path.write_bytes(content)
            with self.assertRaises(AssertionError): self.run_comparison()
        path.write_bytes(original)
        (root / "extra.json").write_bytes(b"extra")
        with self.assertRaisesRegex(AssertionError, "Extra canonical artifact"): self.run_comparison()

    def test_rehashing_changed_artifacts_cannot_hide_four_way_drift(self):
        path = self.path.with_suffix("") / "artifacts/b/payloads.fasta"
        path.write_bytes(b"changed accepted RNA\n")
        self.change(lambda r: r["artifacts"].update({"b/payloads.fasta": hashlib.sha256(path.read_bytes()).hexdigest()}))
        with self.assertRaisesRegex(AssertionError, "Four-way exact canonical artifacts"): self.run_comparison()

    def test_rehashing_missing_required_artifact_inventory_is_rejected(self):
        self.change(lambda r: r["artifacts"].pop("case_b-parameter-override/manifest.json"))
        with self.assertRaisesRegex(AssertionError, "Incomplete or extra"): self.run_comparison()

    def test_missing_fourth_receipt_and_artifact_symlinks_are_rejected(self):
        path = self.root / "macos-arm64/architecture-routing-3.14.json"
        raw = path.read_bytes(); path.unlink()
        with self.assertRaises(AssertionError): self.run_comparison()
        path.write_bytes(raw)
        artifact = self.path.with_suffix("") / "artifacts/b/payloads.fasta"
        artifact.unlink(); artifact.symlink_to(self.path)
        with self.assertRaisesRegex(AssertionError, "Symlink"): self.run_comparison()

    def test_identical_files_do_not_hide_changed_result_receipt(self):
        self.change(lambda r: next(item for item in r["checks"] if item["operation"] == "sdk.export").update(export="d" * 64))
        with self.assertRaisesRegex(AssertionError, "operation results"): self.run_comparison()


if __name__ == "__main__":
    unittest.main()
