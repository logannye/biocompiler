"""Inert declaration-provenance controls; never execute or build native code."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_component_fixture as fixture


class ComponentFixtureTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.identity = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "123", "run_attempt": "2"}
        self.sources = {"source.py": {"sha256": "c" * 64, "size": 13, "git_blob": "d" * 40, "mode": "100644"}}
        self.binaries = {role: {"sha256": str(index) * 64, "size": 12} for index, role in enumerate(fixture.BINARIES, 1)}
        for name in fixture.INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("independent source " + name)
        self.packet = {"schema_version": fixture.FIXTURE_SCHEMA, "status": "source_declarations_only", "acceptance": False,
            "source_sha256": {name: fixture.pin(self.root / name, fixture.MAX_FIXTURE)["sha256"] for name in fixture.INPUTS},
            "cases": [{"id": name, "request": {}, "limits": {}, "expected": {}} for name in ("A", "B")]}
        self.directory = self.root / "supplied"
        self.directory.mkdir()
        self.original = self.directory / "originals.json"
        self.provenance = self.directory / "provenance.json"
        self.original.write_text(json.dumps(self.packet))
        for name in ("stdout.log", "stderr.log"):
            (self.directory / name).write_bytes(b"")
        self.document = {"schema_version": fixture.SCHEMA, "status": "source_declarations_only", "acceptance": False,
            "identity": self.identity, "platform": {"system": "Linux", "machine": "x86_64"}, "sources": self.sources,
            "binaries": self.binaries, "fixture": fixture.pin(self.original, fixture.MAX_FIXTURE),
            "command": {"argv": fixture.logical_command(), "cwd": "checkout", "returncode": 0,
                "logs": {name: fixture.pin(self.directory / name, fixture.MAX_LOG, empty=True)
                         for name in ("stdout.log", "stderr.log")}}}
        self.save()
        self.snapshot = patch.object(fixture.development, "source_snapshot", return_value=self.sources)
        self.snapshot.start()
        self.addCleanup(self.snapshot.stop)
        self.process = patch.object(fixture.subprocess, "run", side_effect=AssertionError("No child execution in fixture tests"))
        self.process_mock = self.process.start()
        self.addCleanup(self.process.stop)

    def save(self, value=None):
        self.provenance.write_text(json.dumps(self.document if value is None else value))

    def validate(self, **kwargs):
        return fixture.validate(self.root, self.original, self.provenance, identity=self.identity,
            native_sha256={role: self.binaries[role]["sha256"] for role in ("core", "verify")}, **kwargs)

    def test_exact_data_is_validated_without_native_or_producer_acceptance(self):
        self.assertEqual(self.validate(expected_platform=("Linux", "x86_64")), self.document)
        self.process_mock.assert_not_called()
        self.assertIs(self.document["acceptance"], False)

    def test_source_run_attempt_platform_and_binary_authority_are_independent(self):
        mutations = [
            lambda d: d["identity"].update(revision="f" * 40),
            lambda d: d["identity"].update(head_revision="f" * 40),
            lambda d: d["identity"].update(run_id="999"),
            lambda d: d["identity"].update(run_attempt="3"),
            lambda d: d["identity"].update(run_attempt="02"),
            lambda d: d["identity"].update(run_attempt=True),
            lambda d: d["platform"].update(machine="arm64"),
            lambda d: d["sources"].clear(),
            lambda d: d["binaries"]["core"].update(sha256="f" * 64),
            lambda d: d["binaries"]["verify"].update(sha256="f" * 64),
            lambda d: d["binaries"].pop("originals"),
            lambda d: d["binaries"]["originals"].update(size=True),
        ]
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                changed = deepcopy(self.document)
                mutate(changed)
                self.save(changed)
                with self.assertRaises(AssertionError):
                    self.validate(expected_platform=("Linux", "x86_64"))
        earlier = deepcopy(self.document)
        earlier["identity"]["run_attempt"] = "1"
        self.save(earlier)
        self.assertEqual(self.validate()["identity"]["run_attempt"], "1")

    def test_claim_command_logs_and_fixture_cannot_be_changed(self):
        mutations = [lambda d: d.update(acceptance=True), lambda d: d.update(status="passed"),
            lambda d: d.update(extra="unreviewed"), lambda d: d["command"].update(returncode=1),
            lambda d: d["command"].update(returncode=False),
            lambda d: d["command"]["argv"].reverse(), lambda d: d["command"].update(cwd="foreign"),
            lambda d: d["command"]["logs"].pop("stderr.log"), lambda d: d["fixture"].update(sha256="f" * 64)]
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                changed = deepcopy(self.document)
                mutate(changed)
                self.save(changed)
                with self.assertRaises(AssertionError):
                    self.validate()
        self.save()
        (self.directory / "stdout.log").write_bytes(b"altered")
        with self.assertRaises(AssertionError):
            self.validate()

    def test_rehashed_packet_still_requires_original_sources_and_closed_cases(self):
        for mutate in (lambda p: p["source_sha256"].update({fixture.INPUTS[0]: "f" * 64}),
                       lambda p: p["cases"].reverse(), lambda p: p["cases"].append(p["cases"][0]),
                       lambda p: p["cases"][0].update(extra=True), lambda p: p.update(acceptance=True)):
            changed = deepcopy(self.packet)
            mutate(changed)
            self.original.write_text(json.dumps(changed))
            changed_proof = deepcopy(self.document)
            changed_proof["fixture"] = fixture.pin(self.original, fixture.MAX_FIXTURE)
            self.save(changed_proof)
            with self.assertRaises(AssertionError):
                self.validate()

    def test_late_changes_and_redirected_inputs_reject(self):
        def changed_snapshot(root):
            (self.directory / "stderr.log").write_bytes(b"late change")
            return self.sources
        with patch.object(fixture.development, "source_snapshot", side_effect=changed_snapshot):
            with self.assertRaises(AssertionError):
                self.validate()
        log = self.directory / "stderr.log"
        log.unlink()
        log.symlink_to(self.directory / "stdout.log")
        with self.assertRaisesRegex(AssertionError, "redirected"):
            self.validate()

    def test_local_emission_rejects_before_any_process(self):
        with patch.dict(fixture.os.environ, {"GITHUB_ACTIONS": "false"}, clear=True):
            with self.assertRaisesRegex(AssertionError, "hosted"):
                fixture.emit(self.root)
        self.process_mock.assert_not_called()

    def test_mocked_hosted_emission_pins_one_fixed_command_and_complete_evidence(self):
        def emit(argv, **kwargs):
            self.assertEqual(argv, ["opam", "exec", "--", str(self.root / fixture.BINARIES["originals"]),
                *(str(self.root / name) for name in fixture.INPUTS), str(self.root / fixture.OUTPUT / "originals.json")])
            self.assertEqual(kwargs, {"cwd": self.root, "capture_output": True, "timeout": 90, "check": False})
            Path(argv[-1]).write_text(json.dumps(self.packet))
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        with patch.object(fixture, "hosted_identity", return_value=self.identity), \
                patch.object(fixture, "binary_pins", return_value=self.binaries), \
                patch.object(fixture.platform, "system", return_value="Linux"), \
                patch.object(fixture.platform, "machine", return_value="x86_64"), \
                patch.object(fixture.subprocess, "run", side_effect=emit) as run:
            self.assertEqual(fixture.emit(self.root)["status"], "source_declarations_only")
            self.assertEqual(run.call_count, 1)
            with self.assertRaises(FileExistsError):
                fixture.emit(self.root)
            self.assertEqual(run.call_count, 1)

    def test_failed_emission_retains_failure_without_accepted_provenance(self):
        with patch.object(fixture, "hosted_identity", return_value=self.identity), \
                patch.object(fixture, "binary_pins", return_value=self.binaries), \
                patch.object(fixture.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"failure")):
            with self.assertRaisesRegex(AssertionError, "emission failed"):
                fixture.emit(self.root)
        report = json.loads((self.root / fixture.OUTPUT / "provenance.json").read_bytes())
        self.assertEqual(report["status"], "incomplete")
        self.assertIs(report["acceptance"], False)


if __name__ == "__main__":
    unittest.main()
