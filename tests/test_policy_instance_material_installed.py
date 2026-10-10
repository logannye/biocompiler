"""Pure installed-instance evidence controls; no native execution or packaging.

Protocol and literal-oracle hooks are explicitly mocked for synthetic records.
Actual identity, origins, sidecars, ZIPs, census and comparison checks execute.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_material as transport
from biocompiler.core_client import CoreProtocolError
from tools import check_policy_instance_material_installed as installed
from tests import test_policy_component_material_campaign as peer

IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
BINARIES = {"biocompiler-core": "c" * 64, "biocompiler-verify": "d" * 64}
SOURCES = {"inert-source-only": {"sha256": "e" * 64}}


class InstanceInstalledTests(unittest.TestCase):
    def mock(self, owner, name, **kwargs):
        value = patch.object(owner, name, **kwargs)
        result = value.start()
        self.addCleanup(value.stop)
        return result

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.fixture_path = self.root / "originals.json"
        self.provenance = self.root / "provenance.json"
        self.fixture = {"cases": [{"id": label, "request": {"case": label, "profile": transport.INSTANCE_REQUEST_PROFILE},
                                  "limits": {"original": label}, "expected": {}} for label in ("A", "B")]}
        peer.write(self.fixture_path, self.fixture)
        peer.write(self.provenance, {"source": "inert provenance; validation tested separately"})
        for name in ("stdout.log", "stderr.log"):
            (self.root / name).write_bytes(b"")
        self.modules, self.origins = {}, {}
        for name in installed.component.REQUIRED_MODULES:
            relative = "__init__.py" if name == "biocompiler" else name.removeprefix("biocompiler.").replace(".", "/") + ".py"
            self.modules[relative] = {"sha256": "f" * 64, "bytes": 10}
            self.origins[name] = "/installed/biocompiler/" + relative
        self.author = lambda request, state: (deepcopy(request), {"request_digest": installed.canonical_digest(request), "state": state})
        self.mock(installed.instance, "checked_fixture", side_effect=lambda root, path: deepcopy(self.fixture))
        self.mock(installed.instance, "author_request", side_effect=self.author)
        self.oracle = self.mock(installed.instance, "checked_result")
        self.provenance_check = self.mock(installed.fixture_tool, "validate", return_value={"sources": SOURCES})
        self.mock(installed, "source_snapshot", return_value=SOURCES)
        self.mock(installed.component, "installed_source_modules", side_effect=lambda root: deepcopy(self.modules))
        self.mock(installed.component, "changed_candidate", side_effect=lambda candidate, kind: {**candidate, "changed": kind})
        self.protocol = self.mock(transport, "_result")
        self.complete = peer.observations(self.fixture)
        self.receipt_path = self.make_receipt(self.root / "slot", ("Linux", "x86_64", "3.11"))
        for target in ("subprocess.Popen", "subprocess.run"):
            guard = patch(target, side_effect=AssertionError("No processes in pure installed tests"))
            guard.start()
            self.addCleanup(guard.stop)

    def make_receipt(self, directory, slot):
        directory.mkdir()
        folder = directory / installed.FOLDER
        folder.mkdir()
        receipt = {"schema_version": installed.SCHEMA, "status": "pass", **IDENTITY,
            "system": slot[0], "machine": slot[1], "python_version": slot[2] + ".15", "scope": installed.SCOPE,
            "inputs": installed.input_pins(), "fixture_sha256": installed.pin(self.fixture_path)["sha256"],
            "fixture_provenance_sha256": installed.pin(self.provenance)["sha256"], "binary_sha256": deepcopy(BINARIES),
            "package": "/installed/biocompiler", "installed_modules": deepcopy(self.modules), "parent_imports": deepcopy(self.origins),
            "source_snapshot_sha256": installed.canonical_digest(SOURCES),
            "authoring": [{"case": case["id"], **self.author(case["request"], case["id"] == "B")[1]} for case in self.fixture["cases"]],
            "observations": [], "observations_fingerprint": installed.canonical_digest(self.complete), "publications": [],
            "python_semantic_authority": "forbidden", "empirical": "unassessed"}
        for row in self.complete:
            path = folder / (row["case"] + "-" + row["name"] + ".json")
            peer.write(path, row["result"])
            receipt["observations"].append({"case": row["case"], "name": row["name"], "path": str(path.relative_to(directory)), **installed.pin(path)})
        for case in ("A", "B"):
            path = folder / (case + "-program.zip")
            peer.publish(path, next(row["result"] for row in self.complete if row["case"] == case and row["name"] == "export-verify"))
            receipt["publications"].append({"case": case, "path": str(path.relative_to(directory)), **installed.pin(path)})
        path = directory / installed.RECEIPT
        peer.write(path, receipt)
        return path

    def validate(self, receipt=None):
        return installed.validate_installed(receipt or installed.read_json(self.receipt_path), self.receipt_path.parent,
            self.fixture_path, IDENTITY, BINARIES, expected_sources=SOURCES, fixture_provenance=self.provenance,
            expected_slot=("Linux", "x86_64", "3.11"))

    def test_hosted_gate_rejects_before_any_native_or_package_work(self):
        with patch.dict(installed.os.environ, {}, clear=True), self.assertRaisesRegex(AssertionError, "hosted-only"):
            installed.run(SimpleNamespace())
        with self.assertRaisesRegex(AssertionError, "outside checkout"):
            installed.component.installed_package_modules(installed.ROOT, installed.ROOT / "src/biocompiler")

    def test_complete_26_observations_and_two_zip_pairs_keep_original_authority(self):
        values = self.validate()
        self.assertEqual(list(values), ["A", "B"])
        self.assertEqual(len(self.complete), 26)
        self.assertEqual(self.protocol.call_count, 10)
        self.assertEqual(self.oracle.call_count, 8)
        for index, case in enumerate(self.fixture["cases"]):
            actual = values[case["id"]]
            self.assertEqual(actual["request"], case["request"])
            self.assertEqual(actual["limits"], case["limits"])
            calls = self.protocol.call_args_list[index * 5:index * 5 + 5]
            self.assertEqual([(call.args[0].operation, call.args[0].executable) for call in calls],
                [(name + "-policy-component-material", role) for name, role in
                 (("compile", "core"), ("check", "verify"), ("replay", "verify"), ("export", "verify"), ("check", "verify"))])
            for call in calls:
                self.assertEqual(call.args[1]["request"], case["request"])
                self.assertEqual(call.args[1]["limits"], case["limits"])
            self.assertEqual(calls[2].args[1]["report"], actual["checked"])
            self.assertEqual(calls[4].args[1]["candidate"], {**actual["candidate"], "changed": "material"})
        self.assertEqual(self.provenance_check.call_args.kwargs, {"identity": IDENTITY,
            "native_sha256": {role: BINARIES["biocompiler-" + role] for role in ("core", "verify")},
            "expected_platform": ("Linux", "x86_64")})

    def test_protocol_literal_oracle_and_provenance_are_each_mandatory(self):
        with patch.object(transport, "_result", side_effect=CoreProtocolError("mandatory protocol")), self.assertRaisesRegex(CoreProtocolError, "mandatory protocol"):
            self.validate()
        with patch.object(installed.instance, "checked_result", side_effect=AssertionError("mandatory original literals")), self.assertRaisesRegex(AssertionError, "mandatory original literals"):
            self.validate()
        with patch.object(installed.fixture_tool, "validate", side_effect=AssertionError("mandatory provenance")), self.assertRaisesRegex(AssertionError, "mandatory provenance"):
            self.validate()
        with patch.object(installed.fixture_tool, "validate", return_value={"sources": {}}), self.assertRaisesRegex(AssertionError, "source authority"):
            self.validate()

    def test_legacy_retained_validator_keeps_its_default_literal_oracle(self):
        with patch.object(installed.component, "checked_result") as original_oracle:
            installed.component.check_observations(self.complete, self.fixture)
        self.assertEqual(original_oracle.call_count, 8)
        self.oracle.assert_not_called()

    def test_development_receipt_or_changed_external_identity_cannot_pass(self):
        original = installed.read_json(self.receipt_path)
        mutations = [("schema_version", installed.instance.SCHEMA), ("status", "passed"), ("run_attempt", "4"),
            ("revision", "0" * 40), ("head_revision", "0" * 40), ("run_id", "9"), ("system", "Darwin"),
            ("python_version", "3.12.1"), ("python_version", "3.11.15\n"), ("scope", "release_accepted"),
            ("source_snapshot_sha256", "0" * 64), ("fixture_sha256", "0" * 64), ("fixture_provenance_sha256", "0" * 64),
            ("binary_sha256", {**BINARIES, "biocompiler-core": "0" * 64}), ("python_semantic_authority", "allowed"),
            ("empirical", "validated")]
        for key, value in mutations:
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                self.validate({**original, key: value})
        earlier = {**original, "run_attempt": "2"}
        self.validate(earlier)

    def test_origins_module_inventory_authoring_and_input_pins_are_exact(self):
        original = installed.read_json(self.receipt_path)
        mutations = [lambda r: r.update(package=str(installed.ROOT / "src/biocompiler")),
            lambda r: r["parent_imports"].update({"biocompiler.compiler": "/installed/biocompiler/compiler.py"}),
            lambda r: r["parent_imports"].update({"biocompiler.core_client": "/foreign/core_client.py"}),
            lambda r: r["parent_imports"].pop("biocompiler.core_policy_component_material"),
            lambda r: r["installed_modules"].pop("core_policy_component_material.py"),
            lambda r: r["authoring"][0].update(state=True),
            lambda r: r["inputs"][installed.instance.INPUTS[0]].update(sha256="0" * 64)]
        for index, mutate in enumerate(mutations):
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.validate(changed)

    def test_reordered_missing_duplicate_and_rehashed_false_observations_reject(self):
        original = installed.read_json(self.receipt_path)
        for rows in (original["observations"][:-1], original["observations"] + original["observations"][:1],
                     list(reversed(original["observations"]))):
            with self.assertRaisesRegex(AssertionError, "observations"):
                self.validate({**original, "observations": rows})
        mutations = [lambda rows: rows[5]["result"]["diagnostics"][0].update(code="unrelated"),
            lambda rows: rows[9]["result"]["report"].update(context_status="pass"),
            lambda rows: rows[1]["result"].update(extra="changed complete replay evidence"),
            lambda rows: rows[4]["result"].update(bytes=1)]
        for index, mutate in enumerate(mutations):
            observations, receipt = deepcopy(self.complete), deepcopy(original)
            mutate(observations)
            for observed, row in zip(observations, receipt["observations"]):
                path = self.receipt_path.parent / row["path"]
                peer.write(path, observed["result"])
                row.update(installed.pin(path))
            receipt["observations_fingerprint"] = installed.canonical_digest(observations)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.validate(receipt)

    def test_publications_extra_files_and_redirected_paths_reject(self):
        original = installed.read_json(self.receipt_path)
        for publications in ([], original["publications"][:1], original["publications"][::-1]):
            with self.assertRaisesRegex(AssertionError, "publications"):
                self.validate({**original, "publications": publications})
        changed = deepcopy(original)
        changed["observations"][0]["path"] = "../foreign.json"
        with self.assertRaisesRegex(AssertionError, "Foreign"):
            self.validate(changed)
        folder = self.receipt_path.parent / installed.FOLDER
        extra = folder / "foreign.json"
        extra.write_text("{}")
        with self.assertRaisesRegex(AssertionError, "extra"):
            self.validate()
        extra.unlink()
        path = self.receipt_path.parent / original["publications"][0]["path"]
        path.write_bytes(path.read_bytes() + b"trailer")
        original["publications"][0].update(installed.pin(path))
        with self.assertRaisesRegex(AssertionError, "publication|archive"):
            self.validate(original)

    def test_original_fixture_or_provenance_bytes_cannot_change(self):
        for path in (self.fixture_path, self.provenance):
            raw = path.read_bytes()
            path.write_bytes(raw + b" ")
            with self.subTest(path=path.name), self.assertRaisesRegex(AssertionError, "external authority"):
                self.validate()
            path.write_bytes(raw)

    def compare(self, paths, provenances=None):
        authorities = {platform: deepcopy(BINARIES) for platform in (("Linux", "x86_64"), ("Darwin", "arm64"))}
        provenances = provenances or {platform: self.provenance for platform in authorities}
        return installed.compare_installed(paths, self.fixture_path, IDENTITY, authorities,
            expected_sources=SOURCES, fixture_provenances=provenances)

    def test_four_slots_compare_complete_results_and_preserve_native_and_fixture_authority(self):
        paths = [self.make_receipt(self.root / ("compare-" + str(index)), slot)
                 for index, slot in enumerate(sorted(installed.component.SLOTS))]
        result = self.compare(paths)
        self.assertEqual(result["slots"], sorted(installed.component.SLOTS))
        self.assertEqual([row["run_attempt"] for row in result["attempts"]], ["3"] * 4)
        self.assertEqual({call.kwargs["expected_platform"] for call in self.provenance_check.call_args_list},
                         {("Linux", "x86_64"), ("Darwin", "arm64")})
        for bad in (paths[:3], paths[:3] + paths[:1]):
            with self.assertRaises(AssertionError):
                self.compare(bad)
        with patch.object(installed, "validate_installed", side_effect=AssertionError("mandatory slot")), self.assertRaisesRegex(AssertionError, "mandatory slot"):
            self.compare(paths)
        with patch.object(installed, "validate_installed", side_effect=[{"complete": 1}, {"complete": 2}]), self.assertRaisesRegex(AssertionError, "differ"):
            self.compare(paths)
        with patch.object(installed, "source_snapshot", side_effect=[SOURCES, {}]), self.assertRaisesRegex(AssertionError, "changed retained authority"):
            self.compare(paths)

    def test_comparison_rejects_different_platform_original_packet_and_midcomparison_edits(self):
        paths = [self.make_receipt(self.root / ("compare-" + str(index)), slot)
                 for index, slot in enumerate(sorted(installed.component.SLOTS))]
        foreign = self.root / "foreign"
        foreign.mkdir()
        (foreign / "originals.json").write_text('{"changed":true}')
        with self.assertRaisesRegex(AssertionError, "packets differ"):
            self.compare(paths, {("Linux", "x86_64"): self.provenance, ("Darwin", "arm64"): foreign / "provenance.json"})
        original_validate = installed.validate_installed
        count = 0
        def mutate_receipt(*args, **kwargs):
            nonlocal count
            value = original_validate(*args, **kwargs)
            count += 1
            if count == 4:
                paths[0].write_bytes(paths[0].read_bytes() + b" ")
            return value
        with patch.object(installed, "validate_installed", side_effect=mutate_receipt), self.assertRaisesRegex(AssertionError, "changed retained authority"):
            self.compare(paths)

    def test_comparison_compares_complete_negative_diagnostics_as_well_as_accepted_results(self):
        paths = [self.make_receipt(self.root / ("compare-" + str(index)), slot)
                 for index, slot in enumerate(sorted(installed.component.SLOTS))]
        receipt = installed.read_json(paths[-1])
        observations = deepcopy(self.complete)
        observations[5]["result"]["diagnostics"][0]["message"] = "Different complete diagnostic text"
        path = paths[-1].parent / receipt["observations"][5]["path"]
        peer.write(path, observations[5]["result"])
        receipt["observations"][5].update(installed.pin(path))
        receipt["observations_fingerprint"] = installed.canonical_digest(observations)
        peer.write(paths[-1], receipt)
        with self.assertRaisesRegex(AssertionError, "results differ"):
            self.compare(paths)


if __name__ == "__main__":
    unittest.main()
