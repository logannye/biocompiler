"""Inert multi_member-original provenance controls; no native build or execution."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_component_fixture as legacy
from tools import check_policy_multi_member_fixture as fixture
from tools import check_policy_instance_fixture as previous


class MultiMemberFixtureTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.identity = {"revision": "a" * 40, "head_revision": "b" * 40,
                         "run_id": "123", "run_attempt": "2"}
        self.sources = {"source.py": {"sha256": "c" * 64, "size": 13,
                                      "git_blob": "d" * 40, "mode": "100644"}}
        self.binaries = {role: {"sha256": str(index) * 64, "size": 12}
                         for index, role in enumerate(("originals", "core", "verify"), 1)}
        for name in fixture.INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("independent source " + name)
        self.packet = {"schema_version": fixture.FIXTURE_SCHEMA, "status": "source_declarations_only",
            "acceptance": False,
            "source_sha256": {name: fixture.pin(self.root / name, fixture.MAX_FIXTURE)["sha256"]
                              for name in fixture.INPUTS},
            "cases": [{"id": name, "request": {}, "limits": {}, "expected": {}} for name in ("A", "B")]}
        self.directory = self.root / "supplied"
        self.directory.mkdir()
        self.original, self.provenance = self.directory / "originals.json", self.directory / "provenance.json"
        self.original.write_text(json.dumps(self.packet))
        for name in ("stdout.log", "stderr.log"):
            (self.directory / name).write_bytes(b"")
        self.document = {"schema_version": fixture.SCHEMA, "status": "source_declarations_only",
            "acceptance": False, "identity": self.identity, "platform": {"system": "Linux", "machine": "x86_64"},
            "sources": self.sources, "binaries": self.binaries,
            "fixture": fixture.pin(self.original, fixture.MAX_FIXTURE),
            "command": {"argv": fixture.logical_command(), "cwd": "checkout", "returncode": 0,
                "logs": {name: fixture.pin(self.directory / name, fixture.MAX_LOG, empty=True)
                         for name in ("stdout.log", "stderr.log")}}}
        self.save()
        snapshot = patch.object(legacy.development, "source_snapshot", return_value=self.sources)
        snapshot.start()
        self.addCleanup(snapshot.stop)
        process = patch.object(legacy.subprocess, "run", side_effect=AssertionError("No native launch"))
        self.process = process.start()
        self.addCleanup(process.stop)

    def save(self, document=None):
        self.provenance.write_text(json.dumps(self.document if document is None else document))

    def validate(self, **kwargs):
        return fixture.validate(self.root, self.original, self.provenance, identity=self.identity,
            native_sha256={role: self.binaries[role]["sha256"] for role in ("core", "verify")}, **kwargs)

    def test_fixed_multi_member_authority_is_separate_and_legacy_provenance_stays_three_roles(self):
        self.assertEqual(fixture.INPUTS, (
            "core/test/data/policy_staged_material_v01.json",
            "core/test/policy_multi_member_support/literals.ml",
            "core/test/policy_multi_member_support/requests.ml"))
        self.assertEqual(fixture.BINARIES, {"originals": "core/_build/default/test/multi_member_fixture_export/main.exe",
            "core": "core/_build/default/bin/core/main.exe", "verify": "core/_build/default/bin/verify/main.exe"})
        self.assertEqual(legacy.BINARIES, {"originals": "core/_build/default/test/component_fixture_export/main.exe",
            "core": "core/_build/default/bin/core/main.exe", "verify": "core/_build/default/bin/verify/main.exe"})
        before = legacy.logical_command()
        with patch.dict(legacy.development.SDK_BINARIES, {"future_exporter": "foreign.exe", "originals": "changed.exe"}):
            self.assertEqual(legacy.logical_command(), before)
            self.assertEqual(set(legacy.BINARIES), {"originals", "core", "verify"})
        self.assertEqual(self.validate(expected_platform=("Linux", "x86_64")), self.document)
        self.process.assert_not_called()

    def test_legacy_provenance_or_emitter_cannot_substitute_for_multi_member_authority(self):
        mutations = (
            lambda d: d.update(schema_version=legacy.SCHEMA),
            lambda d: d.update(schema_version=previous.SCHEMA),
            lambda d: d["command"].update(argv=previous.logical_command()),
            lambda d: d["command"].update(argv=legacy.logical_command()),
            lambda d: d["command"]["argv"].__setitem__(3, legacy.BINARIES["originals"]),
            lambda d: d["binaries"].update(multi_member_originals=deepcopy(d["binaries"]["originals"])),
            lambda d: d["binaries"].pop("originals"),
        )
        for index, mutate in enumerate(mutations):
            changed = deepcopy(self.document)
            mutate(changed)
            self.save(changed)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.validate()
        self.save()
        with self.assertRaises(AssertionError):
            legacy.validate(self.root, self.original, self.provenance, identity=self.identity,
                native_sha256={role: self.binaries[role]["sha256"] for role in ("core", "verify")})

    def test_rehashed_packet_cannot_drop_original_source_or_cross_profiles(self):
        mutations = (
            lambda p: p.update(schema_version=legacy.FIXTURE_SCHEMA),
            lambda p: p.update(schema_version=previous.FIXTURE_SCHEMA),
            lambda p: p["source_sha256"].pop(fixture.INPUTS[-1]),
            lambda p: p["source_sha256"].update({fixture.INPUTS[-1]: "f" * 64}),
            lambda p: p["cases"].reverse(),
            lambda p: p["cases"][0].update(accepted=True),
            lambda p: p.update(acceptance=True),
        )
        for index, mutate in enumerate(mutations):
            changed = deepcopy(self.packet)
            mutate(changed)
            self.original.write_text(json.dumps(changed))
            proof = deepcopy(self.document)
            proof["fixture"] = fixture.pin(self.original, fixture.MAX_FIXTURE)
            self.save(proof)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.validate()

    def test_identity_native_pins_scope_complete_command_and_logs_remain_bound(self):
        mutations = (
            lambda d: d["identity"].update(revision="f" * 40),
            lambda d: d["identity"].update(run_id="999"),
            lambda d: d["identity"].update(run_attempt="3"),
            lambda d: d["platform"].update(machine="arm64"),
            lambda d: d["sources"].clear(),
            lambda d: d["binaries"]["verify"].update(sha256="f" * 64),
            lambda d: d["binaries"]["originals"].update(size=True),
            lambda d: d.update(acceptance=True),
            lambda d: d.update(status="passed"),
            lambda d: d["command"].update(returncode=False),
            lambda d: d["command"]["argv"].pop(-2),
            lambda d: d["command"]["logs"].pop("stderr.log"),
        )
        for index, mutate in enumerate(mutations):
            changed = deepcopy(self.document)
            mutate(changed)
            self.save(changed)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.validate(expected_platform=("Linux", "x86_64"))
        self.save()
        (self.directory / "stdout.log").write_bytes(b"altered")
        with self.assertRaises(AssertionError):
            self.validate()

    def test_local_emission_rejects_before_any_process(self):
        with patch.dict(legacy.os.environ, {"GITHUB_ACTIONS": "false"}, clear=True):
            with self.assertRaisesRegex(AssertionError, "hosted"):
                fixture.emit(self.root)
        self.process.assert_not_called()

    def test_mocked_hosted_emission_preserves_exact_multi_member_command_and_separate_output(self):
        def emit(argv, **kwargs):
            self.assertEqual(argv, ["opam", "exec", "--", str(self.root / fixture.BINARIES["originals"]),
                *(str(self.root / name) for name in fixture.INPUTS), str(self.root / fixture.OUTPUT / "originals.json")])
            self.assertEqual(kwargs, {"cwd": self.root, "capture_output": True, "timeout": 90, "check": False})
            Path(argv[-1]).write_text(json.dumps(self.packet))
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        with patch.object(legacy, "hosted_identity", return_value=self.identity), \
                patch.object(legacy, "binary_pins", return_value=self.binaries), \
                patch.object(legacy.platform, "system", return_value="Linux"), \
                patch.object(legacy.platform, "machine", return_value="x86_64"), \
                patch.object(legacy.subprocess, "run", side_effect=emit) as run:
            self.assertEqual(fixture.emit(self.root), self.document)
            self.assertFalse((self.root / legacy.OUTPUT).exists())
            with self.assertRaises(FileExistsError):
                fixture.emit(self.root)
            self.assertEqual(run.call_count, 1)

    def test_failed_emission_retains_incomplete_multi_member_provenance(self):
        with patch.object(legacy, "hosted_identity", return_value=self.identity), \
                patch.object(legacy, "binary_pins", return_value=self.binaries), \
                patch.object(legacy.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"failed")):
            with self.assertRaisesRegex(AssertionError, "emission failed"):
                fixture.emit(self.root)
        report = json.loads((self.root / fixture.OUTPUT / "provenance.json").read_bytes())
        self.assertEqual(report["schema_version"], fixture.SCHEMA)
        self.assertEqual(report["status"], "incomplete")
        self.assertIs(report["acceptance"], False)


if __name__ == "__main__":
    unittest.main()
