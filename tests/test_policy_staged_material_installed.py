"""Pure installed-evidence controls; no native execution, installs or packaging."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import check_policy_staged_material_installed as installed
from tests.test_policy_staged_component_sdk import inert_result

IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
BINARIES = {"biocompiler-core": "c" * 64, "biocompiler-verify": "d" * 64}
SOURCES = {"inert-source-only": {"sha256": "e" * 64}}


class StagedInstalledTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.fixture_path = installed.ROOT / installed.staged.FIXTURE
        self.fixture = installed.staged.checked_fixture(installed.ROOT, self.fixture_path)
        self.addCleanup(patch.stopall)
        patch("subprocess.Popen", side_effect=AssertionError("No processes in pure installed tests")).start()
        patch("subprocess.run", side_effect=AssertionError("No processes in pure installed tests")).start()

    def observations(self):
        # These are metadata-only records: the real transport rejects them.
        # The protocol hook is mocked explicitly when testing metadata layers.
        result = inert_result(self.fixture)
        values = {name: deepcopy(result) for name in ("compile", "check-verify", "replay-verify")}
        exported = inert_result(self.fixture, exported=True)
        values.update({"export-verify": exported, "paired-publication": installed.archive_receipt(exported),
            "changed-material": {"artifact": None, "report": {"status": "not_accepted", "assembly_status": "fail",
                "context_status": "unassessed", "assembly": {"structure": {"content_outcome": "fail"}}}},
            "insufficient-machine-capacity": {"artifact": None, "report": {"status": "not_accepted", "context_status": "fail"}},
            "completion-without-feedback": {"artifact": None, "report": {"status": "not_accepted",
                "preservation": {"requirements": [{"id": "second_initiation", "status": "fail"}]}}}})
        values.update({name: {"status": "unsupported" if name == "verify-has-no-producer" else "error",
            "diagnostics": [{"code": code, "message": "Inert metadata only", "path": None}]}
            for name, code in installed.staged.NEGATIVE_CODES.items()})
        return [{"name": name, "result": values[name]} for name in installed.staged.OBSERVATIONS]

    def receipt(self):
        observations = self.observations()
        folder = self.root / installed.FOLDER; folder.mkdir()
        rows = []
        for row in observations:
            path = folder / (row["name"] + ".json")
            path.write_text(json.dumps(row["result"]))
            rows.append({"name": row["name"], "path": str(path.relative_to(self.root)), **installed.pin(path)})
        exported = next(row["result"] for row in observations if row["name"] == "export-verify")
        from biocompiler.core_client import encode_json
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            for name, raw in (("program.fasta", exported["artifact"]["fasta"].encode()),
                              ("manifest.json", encode_json(exported["artifact"]["manifest"]))):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.create_system = 3; info.external_attr = 0o100644 << 16
                archive.writestr(info, raw)
        path = folder / "staged-program.zip"; path.write_bytes(buffer.getvalue())
        modules = installed.component.installed_source_modules(installed.ROOT)
        package = "/hosted/env/site-packages/biocompiler"
        origins = {}
        for name in installed.component.REQUIRED_MODULES:
            relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
            options = (relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",)
            origins[name] = str(Path(package) / next(name for name in options if name in modules))
        receipt = {"schema_version": installed.SCHEMA, "status": "pass", **IDENTITY,
            "system": "Linux", "machine": "x86_64", "python_version": "3.11.15", "scope": installed.SCOPE,
            "inputs": installed.input_pins(), "binary_sha256": BINARIES, "package": package, "installed_modules": modules,
            "parent_imports": origins, "source_snapshot_sha256": installed.canonical_digest(SOURCES),
            "authoring": installed.staged.author_request(self.fixture["request"])[1], "observations": rows,
            "observations_fingerprint": installed.canonical_digest(observations), "publications": [
                {"path": str(path.relative_to(self.root)), **installed.pin(path)}],
            "python_semantic_authority": "forbidden", "empirical": "unassessed"}
        return receipt, {row["name"]: row["result"] for row in observations}

    def validate(self, receipt):
        return installed.validate_installed(receipt, self.root, self.fixture_path, IDENTITY, BINARIES, expected_sources=SOURCES,
                                            expected_slot=("Linux", "x86_64", "3.11"))

    def test_hosted_gate_and_checkout_package_fail_before_native(self):
        with patch.dict(installed.os.environ, {}, clear=True), self.assertRaisesRegex(AssertionError, "hosted-only"):
            installed.run(SimpleNamespace())
        with self.assertRaisesRegex(AssertionError, "outside checkout"):
            installed.component.installed_package_modules(installed.ROOT, installed.ROOT / "src/biocompiler")

    def test_all_protocol_values_use_complete_original_payloads(self):
        observations = self.observations()
        from biocompiler import core_policy_component_material as transport
        from biocompiler.core_client import CoreProtocolError
        with self.assertRaises(CoreProtocolError):
            installed.check_observations(observations, self.fixture)
        with patch.object(transport, "_result") as checked, patch.object(installed, "changed_candidate", return_value={"inert-material-mutation": True}):
            values = installed.check_observations(observations, self.fixture)
        self.assertEqual(checked.call_count, 7)
        calls = checked.call_args_list
        self.assertEqual([row.args[0].operation for row in calls], ["compile-policy-component-material", "check-policy-component-material",
            "replay-policy-component-material", "export-policy-component-material", "check-policy-component-material",
            "check-policy-component-material", "compile-policy-component-material"])
        self.assertEqual(calls[2].args[1]["report"], values["compile"])
        self.assertEqual(calls[4].args[1]["candidate"], {"inert-material-mutation": True})
        self.assertEqual(calls[5].args[1]["request"], installed.staged.deficient_capacity(self.fixture["request"]))
        self.assertEqual(calls[6].args[1]["request"], installed.staged.completion_request(self.fixture["request"]))
        for row in calls:
            self.assertEqual(row.args[1]["limits"], self.fixture["limits"])

    def test_rehashed_false_controls_and_promoted_claims_are_rejected(self):
        from biocompiler import core_policy_component_material as transport
        mutations = [
            ("forged-replay", lambda value: value["diagnostics"][0].update(code="unrelated")),
            ("verify-has-no-producer", lambda value: value.update(status="error")),
            ("changed-material", lambda value: value["report"].update(status="accepted")),
            ("insufficient-machine-capacity", lambda value: value["report"].update(context_status="pass")),
            ("completion-without-feedback", lambda value: value["report"]["preservation"]["requirements"][0].update(status="pass")),
            ("compile", lambda value: value["report"]["obligations"][0]["evidence"].update(universal_termination="proved")),
        ]
        with patch.object(transport, "_result"), patch.object(installed, "changed_candidate", return_value={}):
            for name, mutate in mutations:
                changed = self.observations(); mutate(next(row["result"] for row in changed if row["name"] == name))
                with self.subTest(name=name), self.assertRaises(AssertionError):
                    installed.check_observations(changed, self.fixture)

    def test_exact_installed_sidecars_zip_origins_and_mandatory_protocol_gate(self):
        receipt, values = self.receipt()
        with patch.object(installed, "check_observations", return_value=values) as checked:
            self.assertEqual(self.validate(receipt), values)
            self.assertEqual(checked.call_count, 1)
        with patch.object(installed, "check_observations", side_effect=AssertionError("protocol gate mandatory")):
            with self.assertRaisesRegex(AssertionError, "mandatory"):
                self.validate(receipt)
        mutations = [lambda r: r.update(schema_version=installed.component.INSTALLED_SCHEMA),
            lambda r: r.update(run_id="stale"), lambda r: r.update(run_attempt="4"),
            lambda r: r.update(python_version="3.12.1"), lambda r: r.update(empirical="validated"),
            lambda r: r.update(package=str(installed.ROOT / "src/biocompiler")),
            lambda r: r["binary_sha256"].update({"biocompiler-core": "0" * 64}),
            lambda r: r["inputs"][installed.staged.FIXTURE].update(sha256="0" * 64),
            lambda r: r["installed_modules"].pop(next(iter(r["installed_modules"]))),
            lambda r: r["parent_imports"].update({"biocompiler.core_client": "/foreign/core_client.py"}),
            lambda r: r["observations"].pop(), lambda r: r["observations"].reverse(),
            lambda r: r["observations"][0].update(path="../foreign.json"),
            lambda r: r.update(observations_fingerprint="0" * 64), lambda r: r["publications"].clear()]
        with patch.object(installed, "check_observations", return_value=values):
            for mutate in mutations:
                changed = deepcopy(receipt); mutate(changed)
                with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                    self.validate(changed)
            extra = self.root / installed.FOLDER / "foreign.json"; extra.write_text("{}");
            with self.assertRaisesRegex(AssertionError, "extra"):
                self.validate(receipt)
            extra.unlink()
            path = self.root / receipt["publications"][0]["path"]
            path.write_bytes(b"replaced ZIP")
            receipt["publications"][0].update(installed.pin(path))
            with self.assertRaisesRegex(AssertionError, "publication|archive"):
                self.validate(receipt)

    def test_four_slot_comparison_is_complete_and_uses_external_platform_bytes(self):
        paths, receipts = [], []
        for index, slot in enumerate(sorted(installed.component.SLOTS)):
            path = self.root / str(index) / installed.RECEIPT; path.parent.mkdir()
            receipt = {"system": slot[0], "machine": slot[1], "python_version": slot[2] + ".6", "run_attempt": "2"}
            path.write_text(json.dumps(receipt)); paths.append(path); receipts.append(receipt)
        authorities = {platform: {key: value for key, value in BINARIES.items()}
                       for platform in (("Linux", "x86_64"), ("Darwin", "arm64"))}
        with patch.object(installed, "validate_installed", return_value={"all16": "identical"}) as checked:
            result = installed.compare_installed(paths, self.fixture_path, IDENTITY, authorities, expected_sources=SOURCES)
            self.assertEqual(result["status"], "pass"); self.assertEqual(checked.call_count, 4)
            for call in checked.call_args_list:
                self.assertIs(call.args[4], authorities[(call.args[0]["system"], call.args[0]["machine"])])
                self.assertEqual(call.kwargs["expected_sources"], SOURCES)
            with self.assertRaisesRegex(AssertionError, "four slots"):
                installed.compare_installed(paths[:3], self.fixture_path, IDENTITY, authorities, expected_sources=SOURCES)
            with self.assertRaisesRegex(AssertionError, "Duplicate"):
                installed.compare_installed(paths[:3] + paths[:1], self.fixture_path, IDENTITY, authorities, expected_sources=SOURCES)
        with patch.object(installed, "validate_installed", side_effect=[{"complete": 1}, {"complete": 2}]), self.assertRaisesRegex(AssertionError, "differ"):
            installed.compare_installed(paths, self.fixture_path, IDENTITY, authorities, expected_sources=SOURCES)
        with patch.object(installed, "validate_installed", side_effect=AssertionError("mandatory validation")), self.assertRaisesRegex(AssertionError, "mandatory"):
            installed.compare_installed(paths, self.fixture_path, IDENTITY, authorities, expected_sources=SOURCES)


if __name__ == "__main__":
    unittest.main()
