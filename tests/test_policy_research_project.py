"""Research workflow controls with synthetic transports, never native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CORE_VERSION, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError, CoreTransportError, encode_json
from biocompiler.policy import research_project as api
from tests import test_core_policy_component_material as component_peer
from tests import test_core_policy_component_selection as selection_peer


class ResearchProjectTests(unittest.TestCase):
    def setUp(self):
        self.peer = selection_peer.PolicyComponentSelectionTransportTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.core = CoreClient(Path(sys.executable))
        self.verify = CoreClient(Path("/usr/bin/true"), role="verify")
        self.source = api.SourceRecord("independent-original", "urn:research:test-specification", "1",
            hashlib.sha256(b"independent test specification").hexdigest(), "specification", "Synthetic test only")
        self.calls = []

    def project(self, route="component_material"):
        peer = self.peer.peer if route == "component_material" else self.peer
        return api.ResearchProject.from_request(project_id="research.reference", title="Synthetic protocol reference",
            request=peer.request, limits=peer.limits, sources=(self.source,),
            assumptions=("Supplied contracts are assumptions; empirical function is unassessed.",))

    def exchange(self, *, failure=None, not_accepted=False, mutate=None):
        def call(binary, encoded, timeout, cancelled):
            invocation = json.loads(encoded)
            role = "core" if binary == self.core.executable else "verify"
            self.calls.append((role, deepcopy(invocation)))
            operation = invocation["operation"]
            if operation == "capabilities":
                value = component_peer.capabilities(role)
                value["operations"].extend(selection_peer.api.OPERATIONS)
                value["validation_scopes"].append(selection_peer.api.VALIDATION_SCOPE)
                value["profiles"]["policy_component_selection"] = deepcopy(selection_peer.api.PROFILE)
                if role == "core":
                    value["operations"].append(selection_peer.api.COMPILE_OPERATION)
                    value["profiles"]["policy_component_selection_producer"] = deepcopy(selection_peer.api.PRODUCER_PROFILE)
            else:
                if failure and failure(operation):
                    raise CoreTransportError("Synthetic transport failure")
                if operation.endswith("component-selection"):
                    value = selection_peer.result(invocation["payload"], export=operation.startswith("export"))
                else:
                    value = component_peer.result(invocation["payload"], accepted=not not_accepted, export=operation.startswith("export"))
                if mutate:
                    mutate(operation, value)
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"], "operation": operation,
                "status": "ok", "result": value, "diagnostics": [], "core": {"implementation": "ocaml",
                "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def test_complete_originals_are_immutable_and_preflight_is_not_native_admission(self):
        project = self.project()
        original = deepcopy(project.data)
        self.peer.peer.request["context"].clear()
        project.request.clear()
        project.limits.clear()
        project.data.clear()
        self.assertEqual(project.data, original)
        with self.assertRaises(FrozenInstanceError):
            project._json = b"{}"
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            result = project.preflight()
        self.assertEqual((result.status, result.native_status, result.biological_status, result.provenance_status),
                         ("structurally_ready", "not_run", "unassessed", "caller_declared"))
        self.assertEqual(result.project_sha256, hashlib.sha256(encode_json(original)).hexdigest())
        self.assertEqual(result.source_count, 1)

    def test_incomplete_reference_or_unknown_profile_cannot_become_a_project(self):
        project = self.project()
        for request in ({"sequence": "AUG"}, {}, {**project.request, "profile": "invented"},
                        {key: value for key, value in project.request.items() if key != "composition_rule"}):
            with self.subTest(request=request), self.assertRaises((api.ResearchProjectError, CoreProtocolError)):
                api.ResearchProject.from_data({**project.data, "request": request})
        for changes in ({"route": "component_selection"}, {"limits": {}}, {"sources": []},
                        {"assumptions": "implicit"}, {"schema_version": "future"}, {"extra": True}):
            with self.subTest(changes=changes), self.assertRaises((api.ResearchProjectError, CoreProtocolError)):
                api.ResearchProject.from_data({**project.data, **changes})

    def test_source_metadata_is_explicit_versioned_and_not_an_evidence_claim(self):
        project = self.project()
        for changes in ({"sha256": "self-certified"}, {"version": ""}, {"reuse_terms": ""}, {"locator": ""}):
            data = project.data
            data["sources"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(api.ResearchProjectError):
                api.ResearchProject.from_data(data)
        data = project.data
        data["sources"].append(deepcopy(data["sources"][0]))
        with self.assertRaisesRegex(api.ResearchProjectError, "unique"):
            api.ResearchProject.from_data(data)

    def test_json_load_dump_are_bounded_inert_canonical_and_preserve_originals(self):
        project = self.project()
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "project.json"
            project.dump(original)
            loaded = api.ResearchProject.load(original)
            self.assertEqual(loaded.data, project.data)
            self.assertEqual(original.read_bytes(), encode_json(project.data))
            with self.assertRaisesRegex(api.ResearchProjectError, "original"):
                loaded.dump(original, replace=True)
            alias = Path(directory) / "alias.json"
            os.link(original, alias)
            with self.assertRaisesRegex(api.ResearchProjectError, "original"):
                loaded.dump(alias, replace=True)
            with self.assertRaises(FileExistsError):
                project.dump(original)
            original.write_bytes(b'{"schema_version":1,"schema_version":2}')
            with self.assertRaises(CoreProtocolError):
                api.ResearchProject.load(original)
            original.write_bytes(b"[]")
            with self.assertRaises(api.ResearchProjectError):
                api.ResearchProject.load(original)
            original.write_bytes(b" " * (api.MAX_PROJECT_BYTES + 1))
            with self.assertRaisesRegex(api.ResearchProjectError, "bounded"):
                api.ResearchProject.load(original)

    def test_symlinks_and_nonregular_sources_are_rejected_without_opening_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            self.project().dump(target)
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(api.ResearchProjectError, "symbolic"):
                api.ResearchProject.load(link)
            fifo = Path(directory) / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(api.ResearchProjectError, "regular"):
                api.ResearchProject.load(fifo)

    def test_both_routes_generate_with_core_and_freshly_export_and_reverify_with_verify(self):
        for route in ("component_material", "component_selection"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory, self.exchange():
                self.calls.clear()
                project = self.project(route)
                output = Path(directory) / "payload.zip"
                built = project.compile(output=output, core=self.core, verify=self.verify)
                self.assertEqual((built.compiled.executable, built.verified.executable), ("core", "verify"))
                self.assertEqual(built.project_sha256, project.digest)
                self.assertEqual(built.output, output.resolve())
                original = output.read_bytes()
                fresh = project.verify_bundle(output, verify=self.verify)
                self.assertEqual(fresh.artifact, built.verified.artifact)
                self.assertEqual(output.read_bytes(), original)
                suffix = route.replace("_", "-")
                self.assertEqual([(role, row["operation"]) for role, row in self.calls], [
                    ("core", "capabilities"), ("core", "compile-policy-" + suffix),
                    ("verify", "capabilities"), ("verify", "export-policy-" + suffix),
                    ("verify", "capabilities"), ("verify", "export-policy-" + suffix)])
                for _, row in self.calls:
                    if row["operation"] != "capabilities":
                        self.assertEqual(row["payload"]["request"], project.request)
                        self.assertEqual(row["payload"]["limits"], project.limits)

    def test_installed_resolution_requests_explicit_separate_roles_and_operations(self):
        project = self.project()
        def installed(**kwargs):
            return self.core if kwargs["role"] == "core" else self.verify
        with tempfile.TemporaryDirectory() as directory, self.exchange(), patch.object(api, "installed_core", side_effect=installed) as resolve:
            project.compile(output=Path(directory) / "payload.zip", timeout_seconds=41)
        self.assertEqual(resolve.call_args_list[0].kwargs,
            {"role": "core", "operation": "compile-policy-component-material", "timeout_seconds": 41})
        self.assertEqual(resolve.call_args_list[1].kwargs,
            {"role": "verify", "operation": "export-policy-component-material", "timeout_seconds": 41})

    def test_wrong_roles_are_rejected_before_any_native_work(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(CoreClient, "call", side_effect=AssertionError("No native process")):
            for core, verify in ((self.verify, self.verify), (self.core, self.core)):
                with self.subTest(core=core.role, verify=verify.role), self.assertRaisesRegex(api.ResearchProjectError, "role"):
                    self.project().compile(output=Path(directory) / "payload.zip", core=core, verify=verify)

    def test_output_ownership_and_missing_parent_are_checked_before_discovery(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(api, "installed_core", side_effect=AssertionError("No resolution")):
            original = Path(directory) / "original.zip"
            self.project().dump(original)
            project = api.ResearchProject.load(original)
            for output in (original, Path(directory) / "alias.zip"):
                if output != original:
                    os.link(original, output)
                with self.assertRaises(ValueError):
                    project.compile(output=output, replace=True)
            with self.assertRaises(FileExistsError):
                self.project().compile(output=original)
            with self.assertRaisesRegex(api.ResearchProjectError, "parent"):
                self.project().compile(output=Path(directory) / "missing" / "payload.zip")

    def test_rejection_and_verifier_failure_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "payload.zip"
            for options in ({"not_accepted": True}, {"failure": lambda operation: operation.startswith("export")}):
                output.write_bytes(b"preserved")
                with self.subTest(options=options), self.exchange(**options), self.assertRaises((api.ResearchProjectError, CoreTransportError)):
                    self.project().compile(output=output, core=self.core, verify=self.verify, replace=True)
                self.assertEqual(output.read_bytes(), b"preserved")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_native_rejection_retains_full_immutable_diagnostics_without_publication(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange(not_accepted=True):
            output = Path(directory) / "payload.zip"
            with self.assertRaises(api.ResearchProjectRejected) as caught:
                self.project().compile(output=output, core=self.core, verify=self.verify)
            error = caught.exception
            self.assertEqual(error.status, "not_accepted")
            self.assertEqual(error.report, error.compiled.report)
            self.assertEqual(error.compiled.executable, "core")
            self.assertIsNone(error.compiled.artifact)
            retained = error.report
            self.assertTrue(retained["obligations"])
            retained.clear()
            self.assertTrue(error.report["obligations"])
            with self.assertRaises(AttributeError):
                error.compiled = None
            self.assertFalse(output.exists())

    def test_cancellation_prevents_discovery_and_publication(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(api, "installed_core", side_effect=AssertionError("No resolution")):
            output = Path(directory) / "payload.zip"
            with self.assertRaises(CoreCancelled):
                self.project().compile(output=output, cancelled=lambda: True)
            self.assertFalse(output.exists())

    def test_bundle_embedded_authority_cannot_replace_the_current_independent_project(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            project = self.project()
            output = Path(directory) / "payload.zip"
            project.compile(output=output, core=self.core, verify=self.verify)
            changed = project.data
            changed["limits"]["max_work"] = 1
            other = api.ResearchProject.from_data(changed)
            with patch.object(CoreClient, "call", side_effect=AssertionError("No native process")), self.assertRaisesRegex(api.ResearchProjectError, "authority"):
                other.verify_bundle(output, verify=self.verify)

    def test_tampered_pair_candidate_extra_member_and_zip_metadata_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            project = self.project()
            source = Path(directory) / "payload.zip"
            project.compile(output=source, core=self.core, verify=self.verify)
            with zipfile.ZipFile(source) as archive:
                original = [(entry, archive.read(entry)) for entry in archive.infolist()]
            for mode in ("fasta", "manifest", "candidate", "extra", "duplicate", "compressed", "timestamp", "trailer"):
                target = Path(directory) / (mode + ".zip")
                with zipfile.ZipFile(target, "w") as archive:
                    for index, (entry, raw) in enumerate(deepcopy(original)):
                        if mode == "fasta" and index == 0:
                            raw = raw.replace(b"CCAUG", b"GCAUG")
                        if mode in ("manifest", "candidate") and index == 1:
                            value = json.loads(raw)
                            if mode == "manifest":
                                value["empirical"] = "validated"
                            else:
                                value["candidate"]["construction"]["inventory"]["molecules"][0]["sequence"] = "AAA"
                            raw = encode_json(value)
                        if mode == "compressed":
                            entry.compress_type = zipfile.ZIP_DEFLATED
                        if mode == "timestamp":
                            entry.date_time = (2026, 10, 7, 0, 0, 0)
                        archive.writestr(entry, raw)
                    if mode == "extra":
                        archive.writestr("extra.json", b"{}")
                    if mode == "duplicate":
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            archive.writestr(original[0][0], original[0][1])
                if mode == "trailer":
                    with target.open("ab") as handle:
                        handle.write(b"unexpected")
                with self.subTest(mode=mode), self.assertRaises((api.ResearchProjectError, CoreProtocolError)):
                    project.verify_bundle(target, verify=self.verify)

    def test_bundle_change_during_fresh_verification_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            project = self.project()
            output = Path(directory) / "payload.zip"
            project.compile(output=output, core=self.core, verify=self.verify)
            def change(operation, _value):
                if operation.startswith("export"):
                    output.write_bytes(b"changed while verifying")
            with self.exchange(mutate=change), self.assertRaisesRegex(api.ResearchProjectError, "changed"):
                project.verify_bundle(output, verify=self.verify)

    def test_project_dump_failure_preserves_existing_bytes_and_cleans_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project.json"
            output.write_bytes(b"preserved")
            for target in ("os.fsync", "os.replace"):
                with self.subTest(target=target), patch.object(getattr(api, target.split(".")[0]), target.split(".")[1], side_effect=OSError("failure")), self.assertRaises(OSError):
                    self.project().dump(output, replace=True)
                self.assertEqual(output.read_bytes(), b"preserved")
                self.assertFalse(list(Path(directory).glob(".research-project-*")))


if __name__ == "__main__":
    unittest.main()
