"""Joined project orchestration with inert peers, never native acceptance."""
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CORE_VERSION, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError, CoreTransportError, encode_json
from biocompiler import core_policy_controlled_workflow as wire
from biocompiler.policy import research_project as api
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from tests import test_core_policy_controlled_workflow as peer


class ControlledLegacyImportIsolationTests(unittest.TestCase):
    def test_legacy_project_import_does_not_load_controlled_or_semantic_execution_modules(self):
        # An isolated invocation of this same installed Python examines imports;
        # it cannot invoke Core/Verify or execute any native compiler toolchain.
        source = Path(__file__).resolve().parents[1] / "src"
        script = """import sys
sys.path.insert(0, sys.argv[1])
from biocompiler.policy import research_project
unexpected = sorted(name for name in sys.modules if name.startswith((
    'biocompiler.compiler', 'biocompiler.semantics', 'biocompiler.policy.controlled_',
    'biocompiler.core_policy_controlled_')))
assert not unexpected, unexpected
"""
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(source)],
                                   check=False, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


def rewrite_bundle(path, mutate):
    with zipfile.ZipFile(path) as archive:
        members = [(name, archive.read(name)) for name in archive.namelist()]
    members = mutate(members)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, raw in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)


class ControlledResearchProjectTests(unittest.TestCase):
    def setUp(self):
        self.build = ControlledWorkflowRequest.from_request(peer.original())
        self.project = api.ResearchProject.from_controlled(self.build)
        self.core = CoreClient(Path(sys.executable), role="core")
        self.verify = CoreClient(Path("/usr/bin/true"), role="verify")
        self.calls = []
        guard = patch("subprocess.Popen", side_effect=AssertionError("Native execution forbidden in inert project tests"))
        guard.start(); self.addCleanup(guard.stop)

    @contextmanager
    def exchange(self, *, hook=None, failure=None):
        def respond(binary, encoded, timeout, cancelled):
            invocation = json.loads(encoded)
            role = "core" if binary == self.core.executable else "verify"
            self.assertIn(binary, (self.core.executable, self.verify.executable))
            operation = invocation["operation"]
            self.calls.append((role, deepcopy(invocation)))
            if operation == "capabilities":
                # Retain the full ordinary Core protocol capability envelope.
                from tests.test_core_policy_component_material import capabilities
                value = capabilities(role)
                value["operations"] = ["capabilities", wire.CHECK, wire.REPLAY, wire.EXPORT] + ([wire.COMPILE] if role == "core" else [])
                value["profiles"] = {"policy_controlled_workflow": deepcopy(wire.PRODUCER_PROFILE if role == "core" else wire.PROFILE)}
                value["validation_scopes"] = [wire.VALIDATION_SCOPE]
            else:
                if failure == operation:
                    raise CoreTransportError("Inert Verify failure")
                payload = invocation["payload"]
                value = peer.peer_result(payload["request"], payload.get("candidate", peer.candidate(payload["request"])), operation)
            if hook is not None:
                hook(operation, value)
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"],
                "operation": operation, "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), 0
        with patch("biocompiler.core_client._exchange", side_effect=respond):
            yield

    def compile(self, output, **kwargs):
        return self.project.compile(output=output, core=self.core, verify=self.verify, **kwargs)

    def test_v03_roundtrip_retains_originals_context_limits_and_inert_status(self):
        data = self.project.data
        self.assertEqual(data["schema_version"], api.CONTROLLED_SCHEMA)
        self.assertEqual(data["route"], "controlled_composition")
        self.assertEqual(self.project.controlled.to_request(), self.build.to_request())
        self.assertEqual(self.project.limits, self.build.limits)
        self.assertEqual((self.project.preflight().native_status, self.project.preflight().biological_status), ("not_run", "unassessed"))
        self.project.request.clear(); self.project.limits.clear(); self.project.data.clear()
        self.assertEqual(self.project.data, data)
        with self.assertRaises(FrozenInstanceError): self.project._json = b"{}"
        with self.assertRaises(api.ResearchProjectError): api.ResearchProject.from_controlled(self.build.to_request())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            self.project.dump(path)
            loaded = api.ResearchProject.load(path)
            self.assertEqual(loaded.data, data)
            with self.assertRaisesRegex(api.ResearchProjectError, "original"):
                loaded.dump(path, replace=True)

    def test_all_context_and_source_record_fields_remain_complete_native_authority(self):
        for key in ("project_id", "title", "sources", "assumptions"):
            data = self.project.data
            data[key] = "foreign" if isinstance(data[key], str) else []
            with self.subTest(key=key), self.assertRaisesRegex(api.ResearchProjectError, "metadata"):
                api.ResearchProject.from_data(data)
        for key in self.project.data["sources"][0]:
            data = self.project.data
            data["sources"][0][key] = "0" * 64 if key == "sha256" else "foreign"
            with self.subTest(source_field=key), self.assertRaisesRegex(api.ResearchProjectError, "metadata"):
                api.ResearchProject.from_data(data)

    def test_limits_and_route_versions_have_no_legacy_fallback(self):
        for key in self.project.limits:
            data = self.project.data
            data["limits"][key] = "foreign"
            with self.subTest(key=key), self.assertRaisesRegex(api.ResearchProjectError, "limits"):
                api.ResearchProject.from_data(data)
        for fields in ({"schema_version": api.SCHEMA}, {"schema_version": api.EXPRESSION_SCHEMA},
                       {"route": "component_material"}, {"limits": None}, {"extra": True}):
            with self.subTest(fields=fields), self.assertRaises((api.ResearchProjectError, CoreProtocolError)):
                api.ResearchProject.from_data({**self.project.data, **fields})

    def test_core_compile_fresh_verify_export_and_verify_only_reopen_preserve_every_byte(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "program.zip"
            built = self.compile(output)
            raw = output.read_bytes()
            self.calls.clear()
            reopened = self.project.verify_bundle(output, verify=self.verify)
            self.assertEqual(built.compiled.executable, "core")
            self.assertEqual(built.verified.executable, "verify")
            self.assertEqual(reopened.artifact, built.verified.artifact)
            self.assertEqual(output.read_bytes(), raw)
            self.assertEqual([(role, call["operation"]) for role, call in self.calls],
                             [("verify", "capabilities"), ("verify", wire.EXPORT)])
            self.assertEqual(self.calls[-1][1]["payload"]["request"], self.project.request)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                self.assertEqual(archive.read("program.fasta"), reopened.artifact["fasta"].encode())
                self.assertEqual(archive.read("manifest.json"), encode_json(reopened.artifact["manifest"]))

    def test_installed_resolution_and_explicit_roles_remain_separate(self):
        def resolve(**kwargs):
            return self.core if kwargs["role"] == "core" else self.verify
        with tempfile.TemporaryDirectory() as directory, self.exchange(), patch.object(api, "installed_core", side_effect=resolve) as installed:
            output = Path(directory) / "program.zip"
            self.project.compile(output=output, timeout_seconds=29)
            self.project.verify_bundle(output, timeout_seconds=29)
            self.assertEqual([call.kwargs for call in installed.call_args_list], [
                {"role": "core", "operation": wire.COMPILE, "timeout_seconds": 29},
                {"role": "verify", "operation": wire.EXPORT, "timeout_seconds": 29},
                {"role": "verify", "operation": wire.EXPORT, "timeout_seconds": 29}])
        with tempfile.TemporaryDirectory() as directory, patch.object(CoreClient, "call", side_effect=AssertionError("No native work")):
            for core, verify in ((self.verify, self.verify), (self.core, self.core)):
                with self.subTest(core=core.role, verify=verify.role), self.assertRaisesRegex(api.ResearchProjectError, "role"):
                    self.project.compile(output=Path(directory)/"program.zip", core=core, verify=verify)

    def test_foreign_original_and_bundle_limits_reject_before_executable_discovery(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "program.zip"
            self.compile(output)
            foreign = self.build.to_request()
            foreign["behavior_request"]["original"]["source_authority"]["project_context"]["title"] = "Foreign complete original"
            other = api.ResearchProject.from_controlled(ControlledWorkflowRequest.from_request(foreign))
            with patch.object(api, "installed_core", side_effect=AssertionError("No discovery before original comparison")), self.assertRaisesRegex(api.ResearchProjectError, "authority"):
                other.verify_bundle(output)
            def change_limits(members):
                manifest = json.loads(members[1][1]); manifest["limits"]["horizon_tick"] = 9
                return [members[0], ("manifest.json", encode_json(manifest))]
            rewrite_bundle(output, change_limits)
            with patch.object(api, "installed_core", side_effect=AssertionError("No discovery before limit comparison")), self.assertRaisesRegex(api.ResearchProjectError, "limits"):
                self.project.verify_bundle(output)

    def test_fasta_candidate_report_and_archive_changes_fail_fresh_reopen(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "program.zip"
            self.compile(output); saved = output.read_bytes()
            def mutate_manifest(members, section):
                manifest = json.loads(members[1][1])
                if section == "candidate":
                    manifest[section]["behavior_candidate"]["implementation"]["primitives"][6]["onset_ticks"] = 3
                else:
                    manifest[section]["empirical_status"] = "established"
                return [members[0], ("manifest.json", encode_json(manifest))]
            mutations = [lambda m: [("program.fasta", m[0][1] + b"A"), m[1]],
                         lambda m: mutate_manifest(m, "candidate"), lambda m: mutate_manifest(m, "report"),
                         lambda m: list(reversed(m)), lambda m: m + [("extra.txt", b"extra")]]
            for mutation in mutations:
                output.write_bytes(saved); rewrite_bundle(output, mutation)
                with self.subTest(mutation=mutation), self.assertRaises((api.ResearchProjectError, CoreProtocolError)):
                    self.project.verify_bundle(output, verify=self.verify)

    def test_failed_verify_cancellation_and_nonacceptance_leave_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.zip"; output.write_bytes(b"keep original")
            with self.exchange(failure=wire.EXPORT), self.assertRaises(CoreTransportError):
                self.compile(output, replace=True)
            self.assertEqual(output.read_bytes(), b"keep original")
            cancelled = False
            def cancel_after_compile(operation, value):
                nonlocal cancelled
                if operation == wire.COMPILE: cancelled = True
            with self.exchange(hook=cancel_after_compile), self.assertRaises(CoreCancelled):
                self.compile(output, replace=True, cancelled=lambda: cancelled)
            self.assertEqual(output.read_bytes(), b"keep original")
            # A decoded genuine result with a nonaccepted outcome must retain
            # diagnostics and withhold publication; transport validation is
            # covered separately by the native-protocol inert peer tests.
            compiled = wire.PolicyControlledWorkflowClient(peer.Peer("core")).compile(self.project.request)
            raw = compiled.result; raw["report"].update(status="not_accepted", outcome="unknown")
            rejected = wire.PolicyControlledWorkflowResult(compiled.request_id, compiled.operation, compiled.executable,
                compiled.request_fingerprint, compiled.candidate_fingerprint, compiled.invocation_fingerprint,
                compiled.report_fingerprint, encode_json(raw))
            with patch.object(wire.PolicyControlledWorkflowClient, "compile", return_value=rejected), self.assertRaises(api.ResearchProjectRejected) as caught:
                self.compile(output, replace=True)
            self.assertEqual(caught.exception.report["outcome"], "unknown")
            self.assertEqual(output.read_bytes(), b"keep original")
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["program.zip"])

    def test_changed_bundle_and_loaded_input_alias_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            root = Path(directory); output = root / "program.zip"; self.compile(output)
            original = root / "project.json"; self.project.dump(original)
            loaded = api.ResearchProject.load(original)
            alias = root / "alias.zip"; alias.hardlink_to(original)
            with self.assertRaisesRegex(ValueError, "original"):
                loaded.compile(output=alias, core=self.core, verify=self.verify, replace=True)
            def mutate_bundle(operation, value):
                if operation == wire.EXPORT: output.write_bytes(output.read_bytes() + b"changed")
            with self.exchange(hook=mutate_bundle), self.assertRaisesRegex(api.ResearchProjectError, "changed"):
                self.project.verify_bundle(output, verify=self.verify)
