"""Typed finite originals and inert project orchestration; no native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler import policy as p
from biocompiler import core_policy_component_material as material
from biocompiler.core_client import CoreClient, CoreProtocolError, encode_json
from biocompiler.policy.finite_build import (
    CandidateExecutionLimits, FiniteBuildError, FiniteMachineAuthority,
    FiniteMachineBuild, PreservationLimits, RequirementMonitorLimits, SourceExecutionLimits,
)
from biocompiler.policy.research_project import ResearchProject, ResearchProjectError, ResearchProjectRejected, SourceRecord

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "core/test/data/policy_finite_machine_v01.json"


def digest(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


class FiniteBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())

    def setUp(self):
        self.source = SourceRecord("supplied-finite-originals", "urn:biocompiler:artificial-finite-originals", "1",
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), "software_fixture", "Repository software regression only")
        self.core = CoreClient(Path(sys.executable), role="core")
        self.verify = CoreClient(Path("/usr/bin/true"), role="verify")
        self.calls = []

    def build(self, index=0):
        return FiniteMachineBuild.from_request(self.fixture["cases"][index]["request"], limits=self.fixture["limits"])

    def project(self, build=None):
        return ResearchProject.from_build(project_id="finite.software-example", title="Supplied finite-machine originals",
            build=self.build() if build is None else build, sources=(self.source,),
            assumptions=("Artificial model and RNA authority; biological function is unassessed.",))

    def test_two_distinct_shapes_import_and_reopen_complete_original_bytes(self):
        for index in (0, 1):
            original = self.fixture["cases"][index]["request"]
            with self.subTest(shape=self.fixture["cases"][index]["id"]):
                build = self.build(index)
                self.assertIs(type(build.document), p.BuildRequest)
                self.assertEqual(encode_json(build.to_request()), encode_json(original))
                self.assertEqual(encode_json(build.to_limits()), encode_json(self.fixture["limits"]))
                project = self.project(build)
                self.assertEqual(project.route, "component_material")
                self.assertEqual(project.build, build)
                self.assertEqual(project.preflight().native_status, "not_run")
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "project.json"
                    project.dump(path)
                    loaded = ResearchProject.load(path)
                    self.assertEqual(loaded.build, build)
                    self.assertEqual(loaded.digest, project.digest)

    def test_source_state_order_scope_subject_and_lifecycle_remain_distinct(self):
        retry, branch = self.build(0), self.build(1)
        for build in (retry, branch):
            original = build.authority.to_data()["implementation_request"]["document"]
            declarations = p.to_data(build.document)["program"]["declarations"]
            self.assertEqual(declarations, original["program"]["declarations"])
            self.assertEqual(p.to_data(build.document)["deployment"], original["deployment"])
            for kind in ("Subject", "Encounter", "Observation", "Effect", "Machine", "Transition"):
                with self.subTest(program=build.document.program.id, kind=kind):
                    self.assertEqual([row for row in declarations if row["$type"] == kind],
                                     [row for row in original["program"]["declarations"] if row["$type"] == kind])
        transitions = [row for row in branch.document.program.declarations if type(row) is p.Transition]
        self.assertEqual([row.id for row in transitions],
                         ["launch", "accept", "reject", "complete", "probe_fail", "probe_timeout", "response_fail", "response_timeout"])
        self.assertEqual((transitions[0].source, transitions[0].destination), ("ready", "deciding"))
        self.assertEqual([row.source for row in transitions[1:3]], ["deciding", "deciding"])
        self.assertEqual([row.when.op for row in transitions[1:3]], ["observe", "not"])
        self.assertEqual([row.on.op for row in transitions[1:3]], ["effect_event", "effect_event"])
        self.assertEqual([row.unknown for row in transitions], ["defer"] * 8)

    def test_explicit_typed_authoring_preserves_all_independent_material_authority(self):
        imported = self.build()
        document = p.from_data(imported.to_request()["implementation_request"]["document"], p.BuildRequest)
        limits = imported.limits
        authored_limits = PreservationLimits(
            SourceExecutionLimits(**limits.source.to_data()), CandidateExecutionLimits(**limits.candidate.to_data()),
            RequirementMonitorLimits(**limits.monitor.to_data()), limits.max_step_work,
            limits.max_step_retained, limits.max_report_bytes, limits.max_report_nodes)
        authored = FiniteMachineBuild(document, imported.authority, authored_limits)
        self.assertEqual(authored.to_request(), imported.to_request())
        self.assertEqual(authored.to_limits(), imported.to_limits())
        for name in ("component_library", "composition_rule", "catalog_binding", "input_bindings",
                     "resource_bindings", "context", "budgets"):
            self.assertEqual(authored.to_request()[name], self.fixture["cases"][0]["request"][name])

    def test_caller_owned_snapshots_cannot_change_frozen_build_or_project(self):
        original = deepcopy(self.fixture["cases"][0]["request"])
        limits = deepcopy(self.fixture["limits"])
        build = FiniteMachineBuild.from_request(original, limits=limits)
        expected = build.to_request()
        project = self.project(build)
        original["component_library"].clear()
        limits["candidate"]["max_work"] = 1
        build.authority.to_data().clear()
        build.to_request()["context"].clear()
        build.to_limits()["monitor"].clear()
        project.request.clear()
        self.assertEqual(build.to_request(), expected)
        self.assertEqual(project.build.to_request(), expected)
        self.assertEqual(build.to_limits(), self.fixture["limits"])
        for value, attribute, replacement in ((build, "document", None), (build.authority, "_json", b"{}"),
                                               (build.limits.source, "max_work", 1)):
            with self.subTest(attribute=attribute), self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, replacement)

    def test_explicit_source_change_does_not_normalize_repair_or_repin_authority(self):
        original = self.build(1)
        declarations = list(original.document.program.declarations)
        position = next(i for i, row in enumerate(declarations) if type(row) is p.Transition and row.id == "accept")
        declarations[position] = replace(declarations[position], when=p.FALSE)
        document = replace(original.document, program=replace(original.document.program, declarations=tuple(declarations)))
        changed = original.with_document(document)
        expected = original.to_request()
        expected["implementation_request"]["document"] = p.to_data(document)
        self.assertEqual(changed.to_request(), expected)
        self.assertEqual(changed.authority.to_data(), original.authority.to_data())
        self.assertNotEqual(self.project(changed).digest, self.project(original).digest)
        self.assertEqual(changed.to_limits(), original.to_limits())

    def test_caller_budget_change_remains_explicit_and_exact(self):
        original = self.build()
        limits = replace(original.limits, monitor=replace(original.limits.monitor, max_work=1))
        changed = FiniteMachineBuild(original.document, original.authority, limits)
        self.assertEqual(changed.to_request(), original.to_request())
        expected = original.to_limits()
        expected["monitor"]["max_work"] = 1
        self.assertEqual(self.project(changed).limits, expected)

    def test_limits_reject_unknown_omitted_noninteger_and_outside_existing_ceiling(self):
        cases = []
        for key, value in (("max_work", True), ("max_work", 0), ("max_work", 10_000_001), ("max_events", 1.5)):
            row = deepcopy(self.fixture["limits"])
            row["candidate"][key] = value
            cases.append(row)
        for change in (lambda row: row.update(profile="invented"), lambda row: row.pop("monitor"),
                       lambda row: row["source"].update(extra=1), lambda row: row.update(max_report_bytes=8_388_609)):
            row = deepcopy(self.fixture["limits"])
            change(row)
            cases.append(row)
        for row in cases:
            with self.subTest(limits=row), self.assertRaises(FiniteBuildError):
                PreservationLimits.from_data(row)

    def test_unsupported_material_nested_profiles_and_noncanonical_source_reject(self):
        original = self.build().to_request()
        changes = (
            lambda row: row.update(profile="invented"),
            lambda row: row.update(schema_version=material.NETWORK_REQUEST_SCHEMA, profile=material.NETWORK_REQUEST_PROFILE),
            lambda row: row["implementation_request"].update(profile="invented"),
            lambda row: row["implementation_request"]["document"].update(extra=True),
            lambda row: row.pop("composition_rule"),
            lambda row: row["component_library"]["components"][0]["body"].update(quantitative_contracts=[]),
        )
        for change in changes:
            request = deepcopy(original)
            change(request)
            with self.subTest(change=change), self.assertRaises((FiniteBuildError, CoreProtocolError, p.PolicySerializationError)):
                FiniteMachineBuild.from_request(request, limits=self.fixture["limits"])
        with self.assertRaises(FiniteBuildError):
            FiniteMachineBuild(original, self.build().authority, self.build().limits)
        with self.assertRaisesRegex(FiniteBuildError, "canonical"):
            FiniteMachineAuthority(json.dumps(original, indent=2).encode())


    def peers(self, build, *, reject=False):
        """Mock native client calls; real paired publication/reopen is exercised."""
        expected_request, expected_limits = build.to_request(), build.to_limits()
        candidate = {"inert_candidate": "not a native checked implementation", "original": digest(expected_request)}
        def result(operation, role, request, limits, *, export=False, supplied=None):
            self.calls.append((role, operation, deepcopy(request), deepcopy(limits), deepcopy(supplied)))
            self.assertEqual(request, expected_request)
            self.assertEqual(limits, expected_limits)
            if supplied is not None:
                self.assertEqual(supplied, candidate)
            report = {"status": "not_accepted" if reject else material.ACCEPTED_STATUS,
                      "empirical": "unassessed", "inert_test_only": True}
            artifact = None
            if export:
                artifact = {"fasta": ">inert-test-only\nAUG\n", "manifest": {
                    "request": deepcopy(request), "limits": deepcopy(limits), "candidate": deepcopy(candidate),
                    "inert_test_only": True}}
            raw = {"candidate": candidate, "report": report, "artifact": artifact}
            return material.PolicyComponentMaterialResult("inert", operation, role, digest(request), digest(candidate),
                digest({"request": request, "candidate": candidate, "limits": limits}), digest(report), encode_json(raw))
        def compile(client, request, limits, *, cancelled=None):
            self.assertEqual(client.transport.role, "core")
            return result("compile-policy-component-material", "core", request, limits)
        def export(client, request, supplied, limits, *, cancelled=None):
            self.assertEqual(client.transport.role, "verify")
            return result("export-policy-component-material", "verify", request, limits, export=True, supplied=supplied)
        return (patch.object(material.PolicyComponentMaterialClient, "compile", compile),
                patch.object(material.PolicyComponentMaterialClient, "export", export))

    def test_two_shapes_use_core_then_independent_verify_and_reopen_originals(self):
        for index in (0, 1):
            build = self.build(index)
            compile_peer, export_peer = self.peers(build)
            with self.subTest(shape=index), tempfile.TemporaryDirectory() as directory, compile_peer, export_peer:
                self.calls.clear()
                project = self.project(build)
                original_path, output = Path(directory) / "project.json", Path(directory) / "payload.zip"
                project.dump(original_path)
                loaded = ResearchProject.load(original_path)
                result = loaded.compile(output=output, core=self.core, verify=self.verify)
                self.assertEqual((result.compiled.executable, result.verified.executable), ("core", "verify"))
                fresh = ResearchProject.load(original_path).verify_bundle(output, verify=self.verify)
                self.assertEqual(fresh.artifact, result.verified.artifact)
                self.assertEqual([(row[0], row[1]) for row in self.calls], [("core", "compile-policy-component-material"),
                    ("verify", "export-policy-component-material"), ("verify", "export-policy-component-material")])
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                    manifest = json.loads(archive.read("manifest.json"))
                    self.assertEqual(manifest["request"], build.to_request())
                    self.assertEqual(manifest["limits"], build.to_limits())

    def test_stale_bundle_and_mutated_originals_reject_before_native_call(self):
        build = self.build()
        compile_peer, export_peer = self.peers(build)
        with tempfile.TemporaryDirectory() as directory, compile_peer, export_peer:
            output = Path(directory) / "payload.zip"
            self.project(build).compile(output=output, core=self.core, verify=self.verify)
            mutations = [build.with_document(replace(build.document, program=replace(build.document.program, id="changed"))),
                FiniteMachineBuild(build.document, build.authority, replace(build.limits, max_step_work=1))]
            request = build.to_request()
            request["component_library"]["components"][0]["identity"]["content_fingerprint"] = "0" * 64
            mutations.append(FiniteMachineBuild.from_request(request, limits=build.to_limits()))
            for changed in mutations:
                before = len(self.calls)
                with self.subTest(change=changed), self.assertRaisesRegex(ResearchProjectError, "original authority"):
                    self.project(changed).verify_bundle(output, verify=self.verify)
                self.assertEqual(len(self.calls), before)
            raw = bytearray(output.read_bytes())
            position = raw.index(b"AUG")
            raw[position:position + 3] = b"AAA"
            output.write_bytes(raw)
            with self.assertRaises((ResearchProjectError, CoreProtocolError)):
                self.project(build).verify_bundle(output, verify=self.verify)

    def test_rejected_changed_source_keeps_native_report_and_withholds_publication(self):
        original = self.build()
        changed = original.with_document(replace(original.document, program=replace(original.document.program, id="changed")))
        compile_peer, export_peer = self.peers(changed, reject=True)
        with tempfile.TemporaryDirectory() as directory, compile_peer, export_peer:
            output = Path(directory) / "payload.zip"
            with self.assertRaises(ResearchProjectRejected) as rejected:
                self.project(changed).compile(output=output, core=self.core, verify=self.verify)
            self.assertEqual(rejected.exception.status, "not_accepted")
            self.assertTrue(rejected.exception.report["inert_test_only"])
            self.assertFalse(output.exists())
            self.assertEqual(len(self.calls), 1)

    def test_wrong_roles_fail_before_producer_or_verifier_calls(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(CoreClient, "call", side_effect=AssertionError("No native call")):
            for core, verify in ((self.verify, self.verify), (self.core, self.core)):
                with self.subTest(core=core.role, verify=verify.role), self.assertRaisesRegex(ResearchProjectError, "role"):
                    self.project().compile(output=Path(directory) / "payload.zip", core=core, verify=verify)


if __name__ == "__main__":
    unittest.main()
