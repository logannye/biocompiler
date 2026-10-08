"""Inert installed-companion orchestration controls; never install or execute.

Wheel/source inspection and the downstream observation checker are mocked at
their boundaries. Actual retained JSON, command recipes, hashes, logs, runtime
censuses and original-receipt preservation are exercised here.
"""
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_policy_two_observation_prebuilt as companion


IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
SOURCES = {"test-only-source.py": {"sha256": "c" * 64, "size": 12}}
INTERPRETER = {"sha256": "d" * 64, "size": 321}
SLOTS = (("Darwin", "arm64", "3.11"), ("Darwin", "arm64", "3.14"),
         ("Linux", "x86_64", "3.11"), ("Linux", "x86_64", "3.14"))


class TwoObservationPrebuiltTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.popen = self.mock("subprocess.Popen", side_effect=AssertionError("No processes in inert companion tests"))
        self.process = self.mock("subprocess.run", side_effect=AssertionError("No processes in inert companion tests"))
        self.mock.object(companion.base.build, "write_wheel", side_effect=AssertionError("No wheel packaging"))
        self.mock.object(companion, "ROOT", self.checkout)
        self.hosted_identity = companion.base.hosted_identity
        self.mock.object(companion.base, "hosted_identity", return_value=IDENTITY)
        self.mock.object(companion.base, "selected_target", return_value="linux-x86_64")
        self.source_audit = self.mock.object(companion.base, "source_pins", return_value=deepcopy(SOURCES))
        self.owner_audit = self.mock.object(companion.base, "check_ownership")
        self.snapshots = self.mock.object(companion.base, "snapshot_entries")
        self.candidate = {"inert": "independently supplied wheel authority"}
        self.sdk_entries = {"biocompiler/test_only.py": (b"inert sdk", 0o644)}
        self.stamp = {"producer_run_attempt": "1"}
        self.native = {}
        roots, materials, fixtures, provenances = [], [], [], []
        for target, key in (("macos-arm64", ("Darwin", "arm64")), ("linux-x86_64", ("Linux", "x86_64"))):
            directory = self.checkout / "artifacts" / ("core-" + target)
            directory.mkdir(parents=True)
            original = directory / "two-observation-originals"
            original.mkdir()
            fixture, provenance = original / "originals.json", original / "provenance.json"
            companion.write(fixture, {"declaration": "identical independent A/B originals"})
            companion.write(provenance, {"platform": {"system": key[0], "machine": key[1]}, "sources": SOURCES})
            (directory / (target + ".whl")).write_bytes(b"inert supplied native wheel " + target.encode())
            companion.write(directory / "hosted-identity.json", {"inert": "native producer stamp"})
            self.native[key] = {"target": target, "entries": {
                "biocompiler_core/bin/biocompiler-" + role: ((target + " inert " + role).encode(), 0o755)
                for role in ("core", "verify")}, "artifact_files": {target + ".whl": {"sha256": "e" * 64}},
                "stamp": {"producer_run_attempt": "1"}, "native": directory / "inert.whl"}
            roots.append(directory); materials.append(directory / "material-authority.json")
            fixtures.append(fixture); provenances.append(provenance)
        self.args = Namespace(release_candidate=self.root / "candidate.json", sdk=self.root / "sdk.whl",
            platform_root=roots, material_authority=materials, two_observation_fixture=fixtures,
            two_observation_provenance=provenances, slot=[], output=self.root / "comparison.json")
        companion.write(self.args.release_candidate, self.candidate)
        self.args.sdk.write_bytes(b"inert supplied SDK wheel")
        companion.write(self.args.sdk.parent / "hosted-identity.json", {"inert": "SDK producer stamp"})
        self.mock.object(companion.base, "artifact_files", side_effect=lambda root, kind: {
            path.name: companion.pin(path) for path in root.glob("*.whl")})
        self.candidate_audit = self.mock.object(companion.base, "candidate_authority",
            return_value=(self.candidate, self.sdk_entries, self.stamp))
        self.platform_audit = self.mock.object(companion.base, "platform_authority", side_effect=lambda root, *args:
            next(value for value in self.native.values() if root.name == "core-" + value["target"]))
        self.fixture_audit = self.mock.object(companion.fixture_tool, "validate",
            side_effect=lambda root, fixture, provenance, **kwargs: companion.read(provenance))
        self.observation_audit = self.mock.object(companion.campaign, "compare_installed",
            return_value={"status": "pass", "inert": "observation validation boundary"})

    @property
    def mock(self):
        # A small patch factory keeps each child process guard active throughout
        # the test while allowing narrower boundary overrides with context managers.
        owner = self
        class Factory:
            def __call__(self, *args, **kwargs):
                value = patch(*args, **kwargs)
                owner.addCleanup(value.stop)
                return value.start()
            def object(self, *args, **kwargs):
                value = patch.object(*args, **kwargs)
                owner.addCleanup(value.stop)
                return value.start()
        return Factory()

    def artifacts(self, key):
        return companion.base.authority_receipt(self.args.release_candidate, self.args.sdk, self.stamp, self.native[key])

    def paths(self, slot):
        directory = self.checkout / "artifacts" / ("core-" + self.native[slot[:2]]["target"]) / "two-observation-originals"
        return directory / "originals.json", directory / "provenance.json"

    def command_row(self, output, origin, ownership, slot):
        fixture, provenance = self.paths(slot)
        files = ownership["files"]
        argv = [str(origin / "env/bin/python"), "-B", str(self.checkout / "tools/check_policy_two_observation_material_installed.py"),
            "--fixture", str(fixture), "--fixture-provenance", str(provenance),
            "--core", files["bin/biocompiler-core"]["path"], "--verify", files["bin/biocompiler-verify"]["path"],
            "--core-sha256", files["bin/biocompiler-core"]["sha256"], "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
            "--output", str(origin / companion.FOLDER / "evidence" / companion.campaign.RECEIPT)]
        logs = {}
        for suffix in ("stdout", "stderr"):
            path = output / "logs" / ("two-observation-material." + suffix + ".log")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"inert retained " + suffix.encode())
            logs[str(path.relative_to(output))] = companion.pin(path)
        return {"name": "two-observation-material", "argv": argv, "cwd": str(origin / "cwd"),
            "executable": deepcopy(INTERPRETER), "returncode": 0, "timeout": False, "overflow": False,
            "environment": "scrubbed_loaders", "logs": logs}

    def installed_slot(self, slot, *, completed=True, relocated=False, suffix=""):
        label = "-".join(slot) + suffix
        directory = self.root / "installed" / label
        directory.mkdir(parents=True)
        origin = Path("/archived-hosted/" + label) if relocated else directory
        package = origin / "env/lib/site-packages"
        ownership = {"sdk_root": str(package / "biocompiler"), "package_root": str(package / "biocompiler_core"),
            "files": {"bin/biocompiler-" + role: {
                "path": str(package / "biocompiler_core/bin" / ("biocompiler-" + role)),
                "sha256": companion.base.build.sha(self.native[slot[:2]]["entries"]["biocompiler_core/bin/biocompiler-" + role][0])}
                for role in ("core", "verify")}}
        runtime = {"system": slot[0], "machine": slot[1], "python_version": slot[2] + ".9"}
        before = {"runtime": runtime, "ownership": ownership}
        (directory / "evidence").mkdir()
        for name in ("ownership-before", "ownership-after"):
            companion.write(directory / "evidence" / (name + ".json"), before)
        old_rows = [{"argv": [str(origin / "env/bin/python"), "-I", "old-owned-probe"], "executable": deepcopy(INTERPRETER)}]
        companion.write(directory / "commands.json", old_rows)
        baseline = {"schema_version": companion.base.RESEARCHER_SCHEMA, "status": "pass", **IDENTITY,
            "run_attempt": "1", **runtime, "output_root": str(origin), "checkout_root": str(self.checkout),
            "source_pins": deepcopy(SOURCES), "artifacts": self.artifacts(slot[:2]),
            "commands": companion.pin(directory / "commands.json"), "evidence": {
                "evidence/" + name + ".json": companion.pin(directory / "evidence" / (name + ".json"))
                for name in ("ownership-before", "ownership-after")}}
        companion.write(directory / "prebuilt.json", baseline)
        if completed:
            output = directory / companion.FOLDER
            (output / "evidence").mkdir(parents=True)
            command = self.command_row(output, origin, ownership, slot)
            companion.write(output / "commands.json", [command])
            receipt = self.child_receipt(slot, ownership)
            companion.write(output / "evidence" / companion.campaign.RECEIPT, receipt)
            fixture, provenance = self.paths(slot)
            value = {"schema_version": companion.SCHEMA, "status": "pass", **IDENTITY, "scope": companion.SCOPE,
                "slot": list(slot), "origin": str(origin), "checkout": str(self.checkout),
                "baseline": companion.pin(directory / "prebuilt.json"), "artifacts": self.artifacts(slot[:2]),
                "originals": {"fixture": companion.pin(fixture), "provenance": companion.pin(provenance)},
                "command": command, "receipt": companion.pin(output / "evidence" / companion.campaign.RECEIPT)}
            companion.write(output / "companion.json", value)
        return directory, origin, ownership

    def child_receipt(self, slot, ownership):
        return {"schema_version": companion.campaign.SCHEMA, "status": "pass", **IDENTITY,
            "system": slot[0], "machine": slot[1], "python_version": slot[2] + ".9", "package": ownership["sdk_root"],
            "binary_sha256": companion.binary_hashes(self.native[slot[:2]]), "scope": companion.campaign.SCOPE,
            "python_semantic_authority": "forbidden"}

    def matrix(self):
        self.args.slot = [self.installed_slot(slot, relocated=True)[0] for slot in SLOTS]

    def change_companion(self, directory, mutate):
        path = directory / companion.FOLDER / "companion.json"
        value = companion.read(path)
        mutate(value)
        companion.write(path, value)
        return value

    def test_authorities_bind_each_original_to_its_native_platform_and_full_source(self):
        result = companion.authorities(self.args, IDENTITY, 2)
        self.assertEqual(set(result[3]), {slot[:2] for slot in SLOTS})
        self.assertEqual(set(result[4]), set(result[3]))
        self.assertEqual(self.fixture_audit.call_count, 2)
        for call in self.fixture_audit.call_args_list:
            key = call.kwargs["expected_platform"]
            self.assertEqual(call.kwargs["identity"], IDENTITY)
            self.assertEqual(call.kwargs["native_sha256"], {
                role: companion.binary_hashes(self.native[key])["biocompiler-" + role] for role in ("core", "verify")})
        self.popen.assert_not_called(); self.process.assert_not_called()

    def test_authority_census_rejects_missing_duplicate_and_foreign_platforms(self):
        for field in ("platform_root", "material_authority", "two_observation_fixture", "two_observation_provenance"):
            args = deepcopy(self.args); getattr(args, field).pop()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "exactly one"):
                companion.authorities(args, IDENTITY, 2)
        args = deepcopy(self.args); args.platform_root[1] = args.platform_root[0]
        with self.assertRaisesRegex(ValueError, "Duplicate.*native"):
            companion.authorities(args, IDENTITY, 2)
        args = deepcopy(self.args); args.two_observation_provenance[1] = args.two_observation_provenance[0]
        with self.assertRaisesRegex(ValueError, "Duplicate or foreign"):
            companion.authorities(args, IDENTITY, 2)
        companion.write(self.args.two_observation_provenance[0], {"platform": {"system": "Windows", "machine": "AMD64"}})
        with self.assertRaisesRegex(ValueError, "foreign"):
            companion.authorities(self.args, IDENTITY, 2)

    def test_original_fixture_bytes_and_source_snapshots_must_match_across_platforms(self):
        original = self.args.two_observation_fixture[0].read_bytes()
        self.args.two_observation_fixture[0].write_bytes(b"different independently supplied originals")
        with self.assertRaisesRegex(ValueError, "differ"):
            companion.authorities(self.args, IDENTITY, 2)
        self.args.two_observation_fixture[0].write_bytes(original)
        proof = companion.read(self.args.two_observation_provenance[0]); proof["sources"] = {"changed": {"sha256": "f" * 64}}
        companion.write(self.args.two_observation_provenance[0], proof)
        with self.assertRaisesRegex(ValueError, "source snapshots differ"):
            companion.authorities(self.args, IDENTITY, 2)

    def test_original_fixture_validator_is_a_mandatory_gate(self):
        with patch.object(companion.fixture_tool, "validate", side_effect=ValueError("independent fixture gate")):
            with self.assertRaisesRegex(ValueError, "independent fixture gate"):
                companion.authorities(self.args, IDENTITY, 2)

    def test_owned_slot_preserves_earlier_attempt_and_authenticates_its_ledger(self):
        directory, origin, ownership = self.installed_slot(SLOTS[0])
        before = (directory / "prebuilt.json").read_bytes()
        result = companion.owned_slot(directory, IDENTITY, self.candidate, self.sdk_entries, self.stamp, self.native, self.args)
        self.assertEqual(result, (SLOTS[0], origin, ownership))
        self.assertEqual((directory / "prebuilt.json").read_bytes(), before)
        self.owner_audit.assert_called_once()
        rows = companion.read(directory / "commands.json")
        rows[0]["executable"]["sha256"] = "f" * 64
        companion.write(directory / "commands.json", rows)
        with self.assertRaisesRegex(ValueError, "command|ledger|receipt"):
            companion.owned_slot(directory, IDENTITY, self.candidate, self.sdk_entries, self.stamp, self.native, self.args)

    def test_owned_slot_rejects_changed_original_identity_sources_and_ownership(self):
        directory, _, _ = self.installed_slot(SLOTS[0])
        path = directory / "prebuilt.json"; original = companion.read(path)
        for fields in ({"run_id": "foreign"}, {"run_attempt": "4"}, {"status": "failed"},
                       {"schema_version": "legacy"}, {"source_pins": {}}, {"artifacts": {}},
                       {"output_root": str(self.checkout / "unsafe-environment")}):
            with self.subTest(fields=fields):
                companion.write(path, original | fields)
                with self.assertRaises(ValueError):
                    companion.owned_slot(directory, IDENTITY, self.candidate, self.sdk_entries, self.stamp, self.native, self.args)
        companion.write(path, original)
        companion.write(directory / "evidence/ownership-after.json", {"changed": "ownership"})
        with self.assertRaises(ValueError):
            companion.owned_slot(directory, IDENTITY, self.candidate, self.sdk_entries, self.stamp, self.native, self.args)

    def test_exact_command_recipe_rejects_rehashed_paths_flags_status_and_interpreter(self):
        directory, origin, ownership = self.installed_slot(SLOTS[0], relocated=True)
        output = directory / companion.FOLDER
        value = companion.read(output / "companion.json")
        companion.check_command(output, value, origin, ownership)
        def argument(flag, replacement):
            return lambda row: row["argv"].__setitem__(row["argv"].index(flag) + 1, replacement)
        mutations = [lambda row: row["argv"].__setitem__(0, "/foreign/python"),
            lambda row: row["argv"].__setitem__(2, "/foreign/check_policy_two_observation_material_installed.py"),
            argument("--fixture", "/foreign/originals.json"), argument("--fixture-provenance", "/foreign/provenance.json"),
            argument("--core", "/foreign/core"), argument("--verify-sha256", "f" * 64),
            argument("--output", "/foreign/receipt.json"), lambda row: row.update(cwd="/foreign/cwd"),
            lambda row: row.update(returncode=True), lambda row: row.update(returncode=1),
            lambda row: row.update(timeout=True), lambda row: row.update(overflow=True),
            lambda row: row.update(environment="inherited"), lambda row: row["executable"].update(sha256="f" * 64),
            lambda row: row.update(extra="unknown")]
        for index, mutate in enumerate(mutations):
            changed = deepcopy(value); mutate(changed["command"])
            companion.write(output / "commands.json", [changed["command"]])
            with self.subTest(index=index), self.assertRaises(ValueError):
                companion.check_command(output, changed, origin, ownership)

    def test_command_census_and_log_bytes_cannot_be_substituted(self):
        directory, origin, ownership = self.installed_slot(SLOTS[0])
        output = directory / companion.FOLDER; value = companion.read(output / "companion.json")
        for rows in ([], [value["command"], value["command"]]):
            companion.write(output / "commands.json", rows)
            with self.assertRaisesRegex(ValueError, "census"):
                companion.check_command(output, value, origin, ownership)
        companion.write(output / "commands.json", [value["command"]])
        log = output / "logs/two-observation-material.stdout.log"
        log.write_bytes(b"changed after campaign")
        with self.assertRaisesRegex(ValueError, "logs differ"):
            companion.check_command(output, value, origin, ownership)

    def test_four_slot_comparison_retains_original_attempts_and_calls_observation_gate(self):
        self.matrix()
        before = {path: (path / "prebuilt.json").read_bytes() for path in self.args.slot}
        result = companion.compare(self.args)
        self.assertEqual(result["status"], "pass")
        self.assertEqual([row["slot"] for row in result["slots"]], [list(slot) for slot in SLOTS])
        self.assertTrue(all(row["run_attempt"] == "3" for row in result["slots"]))
        self.assertEqual({path: (path / "prebuilt.json").read_bytes() for path in self.args.slot}, before)
        call = self.observation_audit.call_args
        self.assertEqual(call.args[0], [path / companion.FOLDER / "evidence" / companion.campaign.RECEIPT for path in self.args.slot])
        self.assertEqual(call.args[2], IDENTITY)
        self.assertEqual(call.args[3], {key: companion.binary_hashes(value) for key, value in self.native.items()})
        self.assertEqual(call.kwargs["expected_sources"], SOURCES)
        self.assertEqual(set(call.kwargs["fixture_provenances"]), set(self.native))
        self.popen.assert_not_called(); self.process.assert_not_called()

    def test_four_slot_comparison_rejects_missing_duplicate_and_stale_companions(self):
        self.matrix()
        original = list(self.args.slot)
        for paths in (original[:3], original[:3] + original[:1]):
            self.args.slot = paths
            with self.assertRaisesRegex(ValueError, "four installed|Duplicate"):
                companion.compare(self.args)
            self.assertFalse(self.args.output.exists())
        self.args.slot = original
        for fields in ({"revision": "f" * 40}, {"run_attempt": "4"}, {"scope": "promoted"},
                       {"schema_version": "biocompiler.policy_instance_prebuilt_companion.v0.1"},
                       {"checkout": "/foreign/checkout"}, {"originals": {}}, {"receipt": {}}, {"baseline": {}}):
            path = original[0] / companion.FOLDER / "companion.json"; saved = path.read_bytes()
            self.change_companion(original[0], lambda value: value.update(fields))
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                companion.compare(self.args)
            path.write_bytes(saved)
        self.observation_audit.assert_not_called()

    def test_changed_child_receipt_or_original_campaign_cannot_reach_comparison(self):
        self.matrix()
        directory = self.args.slot[0]
        receipt = directory / companion.FOLDER / "evidence" / companion.campaign.RECEIPT
        saved = receipt.read_bytes()
        companion.write(receipt, companion.read(receipt) | {"package": "/foreign/package"})
        self.change_companion(directory, lambda value: value.update(receipt=companion.pin(receipt)))
        with self.assertRaisesRegex(ValueError, "package or attempt"):
            companion.compare(self.args)
        receipt.write_bytes(saved)
        self.change_companion(directory, lambda value: value.update(receipt=companion.pin(receipt)))
        baseline = directory / "prebuilt.json"
        companion.write(baseline, companion.read(baseline) | {"unrelated_edit": True})
        with self.assertRaisesRegex(ValueError, "Stale or altered"):
            companion.compare(self.args)
        self.observation_audit.assert_not_called()

    def test_downstream_observation_failure_prevents_summary_publication(self):
        self.matrix()
        self.observation_audit.side_effect = AssertionError("complete installed observations rejected")
        with self.assertRaisesRegex(AssertionError, "complete installed"):
            companion.compare(self.args)
        self.assertFalse(self.args.output.exists())

    def test_late_retained_evidence_and_wheel_changes_prevent_comparison_publication(self):
        self.matrix()
        directory = self.args.slot[0]
        output = directory / companion.FOLDER
        targets = [directory / "prebuilt.json", directory / "commands.json",
            directory / "evidence/ownership-after.json", output / "companion.json", output / "commands.json",
            output / "logs/two-observation-material.stderr.log", self.args.sdk, self.args.release_candidate,
            self.args.sdk.parent / "hosted-identity.json", self.args.platform_root[0] / "macos-arm64.whl",
            self.args.platform_root[0] / "hosted-identity.json"]
        for path in targets:
            saved = path.read_bytes()
            def change_after_check(*args, **kwargs):
                path.write_bytes(saved + b"\nlate alteration")
                return {"status": "pass", "inert": "downstream gate returned"}
            self.observation_audit.side_effect = change_after_check
            with self.subTest(path=path.relative_to(self.root)), self.assertRaisesRegex(ValueError, "changed during comparison"):
                companion.compare(self.args)
            self.assertFalse(self.args.output.exists())
            path.write_bytes(saved)

    def test_prior_companion_attempt_is_retained_without_relabeling_or_overwriting(self):
        self.matrix()
        for directory in self.args.slot:
            receipt = directory / companion.FOLDER / "evidence" / companion.campaign.RECEIPT
            companion.write(receipt, companion.read(receipt) | {"run_attempt": "2"})
            self.change_companion(directory, lambda value: value.update(run_attempt="2", receipt=companion.pin(receipt)))
        result = companion.compare(self.args)
        self.assertEqual([row["run_attempt"] for row in result["slots"]], ["2"] * 4)
        original = self.args.output.read_bytes()
        with self.assertRaisesRegex(ValueError, "fresh"):
            companion.compare(self.args)
        self.assertEqual(self.args.output.read_bytes(), original)

    def test_hosted_and_runtime_guards_precede_authority_or_execution(self):
        with patch.object(companion.base, "hosted_identity", self.hosted_identity), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "hosted-only"):
                companion.run(self.args)
        with patch.object(companion.base, "selected_target", side_effect=ValueError("Unsupported runtime")):
            with self.assertRaisesRegex(ValueError, "Unsupported runtime"):
                companion.run(self.args)
        self.candidate_audit.assert_not_called()
        self.popen.assert_not_called(); self.process.assert_not_called()

    def test_launch_rejects_relocation_runtime_and_off_recipe_originals_before_command(self):
        slot = SLOTS[2]
        directory, _, _ = self.installed_slot(slot, completed=False)
        args = deepcopy(self.args)
        for field in ("platform_root", "material_authority", "two_observation_fixture", "two_observation_provenance"):
            setattr(args, field, getattr(args, field)[1:])
        args.slot = [directory]
        baseline_path = directory / "prebuilt.json"
        baseline = baseline_path.read_bytes()
        with patch.object(companion.base, "command") as launch, \
                patch.object(companion.platform, "system", return_value=slot[0]), \
                patch.object(companion.platform, "machine", return_value=slot[1]), \
                patch.object(companion.sys, "version_info", SimpleNamespace(major=3, minor=11)):
            companion.write(baseline_path, companion.read(baseline_path) | {"output_root": "/archived-hosted/relocated"})
            with self.assertRaisesRegex(ValueError, "relocated or foreign"):
                companion.run(args)
            baseline_path.write_bytes(baseline)
            with patch.object(companion.platform, "machine", return_value="arm64"):
                with self.assertRaisesRegex(ValueError, "relocated or foreign"):
                    companion.run(args)
            foreign = self.root / "same-bytes-foreign-originals.json"
            foreign.write_bytes(args.two_observation_fixture[0].read_bytes())
            args.two_observation_fixture = [foreign]
            with self.assertRaisesRegex(ValueError, "fixture path"):
                companion.run(args)
            launch.assert_not_called()
        self.assertFalse((directory / companion.FOLDER).exists())

    def test_mocked_run_publishes_additive_receipt_without_changing_old_campaign(self):
        slot = SLOTS[2]
        directory, origin, ownership = self.installed_slot(slot, completed=False)
        args = deepcopy(self.args)
        for field in ("platform_root", "material_authority", "two_observation_fixture", "two_observation_provenance"):
            setattr(args, field, getattr(args, field)[1:])
        args.slot = [directory]
        before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
        def command(output, name, arguments, **kwargs):
            self.assertEqual(name, "two-observation-material")
            row = self.command_row(output, origin, ownership, slot)
            self.assertEqual(arguments, row["argv"])
            self.assertEqual(kwargs["cwd"], origin / "cwd")
            companion.write(output / "commands.json", [row])
            companion.write(output / "evidence" / companion.campaign.RECEIPT, self.child_receipt(slot, ownership))
            return row
        with patch.object(companion.platform, "system", return_value=slot[0]), \
                patch.object(companion.platform, "machine", return_value=slot[1]), \
                patch.object(companion.sys, "version_info", SimpleNamespace(major=3, minor=11)), \
                patch.object(companion.base, "command", side_effect=command) as launched:
            result = companion.run(args)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(launched.call_count, 1)
            with self.assertRaisesRegex(ValueError, "fresh"):
                companion.run(args)
            self.assertEqual(launched.call_count, 1)
        self.assertEqual({path: (directory / path).read_bytes() for path in before}, before)
        self.assertEqual(companion.read(directory / "prebuilt.json")["run_attempt"], "1")
        self.assertEqual(self.snapshots.call_count, 4)

    def test_failed_or_foreign_child_never_publishes_passing_companion(self):
        slot = SLOTS[2]
        changes = [{"status": "failed"}, {"schema_version": "foreign"},
            {"schema_version": "biocompiler.policy_instance_material_campaign.v0.1"}, {"run_attempt": "2"},
            {"package": "/foreign/package"}, {"binary_sha256": {}}, {"scope": "promoted"},
            {"python_semantic_authority": "permitted"}, {"machine": "arm64"}]
        for index, fields in enumerate(changes):
            directory, origin, ownership = self.installed_slot(slot, completed=False, suffix="-child-" + str(index))
            args = deepcopy(self.args)
            for field in ("platform_root", "material_authority", "two_observation_fixture", "two_observation_provenance"):
                setattr(args, field, getattr(args, field)[1:])
            args.slot = [directory]
            baseline = (directory / "prebuilt.json").read_bytes()
            def command(output, name, arguments, **kwargs):
                row = self.command_row(output, origin, ownership, slot)
                companion.write(output / "commands.json", [row])
                companion.write(output / "evidence" / companion.campaign.RECEIPT, self.child_receipt(slot, ownership) | fields)
                return row
            with self.subTest(fields=fields), patch.object(companion.platform, "system", return_value=slot[0]), \
                    patch.object(companion.platform, "machine", return_value=slot[1]), \
                    patch.object(companion.sys, "version_info", SimpleNamespace(major=3, minor=11)), \
                    patch.object(companion.base, "command", side_effect=command) as launched:
                with self.assertRaisesRegex(ValueError, "child changed"):
                    companion.run(args)
                self.assertEqual(launched.call_count, 1)
            self.assertFalse((directory / companion.FOLDER / "companion.json").exists())
            self.assertEqual((directory / "prebuilt.json").read_bytes(), baseline)


if __name__ == "__main__":
    unittest.main()
