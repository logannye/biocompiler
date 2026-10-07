"""Pure provenance/mutation controls; no packaging, installation or native calls."""
from __future__ import annotations

import base64
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_material_prebuilt as campaign


IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
ENVIRONMENT = {"path": "", "loader_variables": [], "isolated": True, "dont_write_bytecode": True}


def record(entries, path):
    rows = []
    for name, (raw, _) in sorted(entries.items()):
        digest = "sha256=" + base64.urlsafe_b64encode(__import__("hashlib").sha256(raw).digest()).rstrip(b"=").decode()
        rows.append((name, digest, str(len(raw))))
    rows.append((path, "", ""))
    stream = io.StringIO(newline=""); csv.writer(stream, lineterminator="\n").writerows(rows)
    return stream.getvalue().encode()


class PrebuiltMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        # These guards make accidental broadening of a pure test immediately
        # fail instead of installing or executing a native artifact locally.
        self.popen = patch.object(campaign.subprocess, "Popen", side_effect=AssertionError("No processes in pure prebuilt tests"))
        self.popen.start(); self.addCleanup(self.popen.stop)
        self.writer = patch.object(campaign.build, "write_wheel", side_effect=AssertionError("No wheel packaging in pure tests"))
        self.writer.start(); self.addCleanup(self.writer.stop)

    def test_same_run_prior_attempt_is_preserved_not_relabelled(self):
        root = self.root / "sdk"; root.mkdir()
        (root / "candidate.json").write_text("{}")
        (root / ("biocompiler-" + campaign.build.VERSION + "-py3-none-any.whl")).write_bytes(b"inert-supplied-wheel-marker")
        prior = {**IDENTITY, "run_attempt": "1"}
        actual = campaign.stamp_artifacts(root, "sdk", prior)
        checked = campaign.check_stamp(root, "sdk", IDENTITY)
        self.assertEqual(checked["producer_run_attempt"], "1")
        self.assertEqual(campaign.read_json(root / "hosted-identity.json"), actual)
        for edits in ({"run_attempt": "4"}, {"run_attempt": "0"}, {"run_attempt": "01"}, {"run_attempt": 1},
                      {"run_id": "other"}, {"revision": "c" * 40}, {"head_revision": "c" * 40}):
            with self.subTest(edits=edits):
                campaign.write_json(root / "hosted-identity.json", {**actual, **edits})
                with self.assertRaises(ValueError):
                    campaign.check_stamp(root, "sdk", IDENTITY)
        campaign.write_json(root / "hosted-identity.json", actual)
        (root / "candidate.json").write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, "Artifact bytes"):
            campaign.check_stamp(root, "sdk", IDENTITY)

    def test_hosted_only_and_actual_consumer_attempt(self):
        with patch.dict(campaign.os.environ, {"GITHUB_ACTIONS": "false"}, clear=True):
            with self.assertRaisesRegex(ValueError, "hosted-only"):
                campaign.hosted_identity()
        with patch.dict(campaign.os.environ, {"GITHUB_ACTIONS": "true"}, clear=True), patch.object(campaign.core, "source_identity", return_value=IDENTITY):
            self.assertEqual(campaign.hosted_identity(), IDENTITY)
        self.assertFalse(campaign.prior_attempt({**IDENTITY, "run_attempt": "4"}, IDENTITY))
        self.assertTrue(campaign.prior_attempt({**IDENTITY, "run_attempt": "2"}, IDENTITY))

    def test_closed_install_plan_does_not_use_sources_or_legacy_campaigns(self):
        sdk = self.root / ("biocompiler-" + campaign.build.VERSION + "-py3-none-any.whl")
        native = self.root / ("biocompiler_core-" + campaign.build.VERSION + "-" + campaign.build.TARGETS["linux-x86_64"][2] + ".whl")
        argv = campaign.foundation.install_plan(Path("/driver/python"), Path("/fresh/env/bin/python"), sdk, native)
        self.assertEqual(argv, ["/driver/python", "-m", "pip", "--python", "/fresh/env/bin/python", "install",
                               "--no-index", "--no-deps", "--only-binary=:all:", str(sdk), str(native)])
        with self.assertRaises(ValueError):
            campaign.foundation.install_plan(Path("/driver/python"), Path("/env/bin/python"), self.root / "source.tar.gz", native)
        tree = __import__("ast").parse(Path(campaign.__file__).read_text())
        calls = [node for node in __import__("ast").walk(tree) if isinstance(node, __import__("ast").Call)]
        self.assertFalse(any(isinstance(node.func, __import__("ast").Attribute) and node.func.attr in
                             ("installed", "aggregate", "lifecycle_plan", "check_install") for node in calls))

    def test_probe_scrubs_loader_environment_and_path(self):
        with patch.dict(campaign.os.environ, {"PATH": "/native/bin", "LD_PRELOAD": "evil", "LD_AUDIT": "evil",
                "DYLD_FALLBACK_FRAMEWORK_PATH": "evil", "PYTHONPATH": "checkout/src", "PYTHONHOME": "evil",
                "OPAM_SWITCH_PREFIX": "evil", "CAML_LD_LIBRARY_PATH": "evil", "GITHUB_RUN_ID": "1234"}, clear=True):
            result = campaign.safe_environment(probe=True)
        self.assertEqual(result["PATH"], "")
        self.assertEqual(result["GITHUB_RUN_ID"], "1234")
        self.assertFalse(set(result) & {"LD_PRELOAD", "LD_AUDIT", "DYLD_FALLBACK_FRAMEWORK_PATH", "PYTHONPATH", "PYTHONHOME", "OPAM_SWITCH_PREFIX", "CAML_LD_LIBRARY_PATH"})
        self.assertEqual(result["PIP_NO_INDEX"], "1")

    def installed_tree(self):
        site = self.root / "env/lib/python3.14/site-packages"; site.mkdir(parents=True)
        sdk = site / "biocompiler"; native = site / "biocompiler_core"
        sdk_info = "biocompiler-" + campaign.build.VERSION + ".dist-info/"
        native_info = "biocompiler_core-" + campaign.build.VERSION + ".dist-info/"
        sdk_entries = {
            "biocompiler/_core_release.json": (campaign.build.canonical({"platforms": {"linux-x86_64": "a" * 64}}), 0o644),
            "biocompiler/core_policy_material.py": (b'VALIDATION_SCOPE = "policy-truth-mrna-v0.1"\n', 0o644),
            sdk_info + "METADATA": (b"Name: biocompiler\n", 0o644),
        }
        native_entries = {
            "biocompiler_core/bin/biocompiler-verify": (b"INERT-BINARY-NEVER-EXECUTED", 0o755),
            native_info + "METADATA": (("Name: biocompiler-core\nVersion: " + campaign.build.VERSION + "\n").encode(), 0o644),
            native_info + "WHEEL": (("Root-Is-Purelib: false\nTag: " + campaign.build.TARGETS["linux-x86_64"][2] + "\n").encode(), 0o644),
        }
        for entries, info in ((sdk_entries, sdk_info), (native_entries, native_info)):
            entries[info + "RECORD"] = (record(entries, info + "RECORD"), 0o644)
            for name, (raw, mode) in entries.items():
                path = site / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(mode)
        return {"package_root": str(native), "sdk_root": str(sdk), "native_platform": "linux-x86_64"}, site, sdk_entries, native_entries

    def test_each_actual_installed_mutation_restores_even_after_exception(self):
        ownership, site, _, _ = self.installed_tree()
        original = {str(path): (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns) for path in site.rglob("*") if path.is_file()}
        for case in campaign.CASES:
            with self.subTest(case=case):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    with campaign.installed_mutation(case, ownership) as changes:
                        self.assertEqual(len(changes), len(campaign.mutation_files(case, ownership)))
                        self.assertTrue(all(row["before"] != row["after"] for row in changes))
                        if case in ("changed-release", "mismatched-profile"):
                            metadata = campaign.mutation_files(case, ownership)[1]
                            rows = list(csv.reader(io.StringIO(metadata.read_text())))
                            name = "biocompiler/" + campaign.mutation_files(case, ownership)[0].name
                            selected = next(row for row in rows if row[0] == name)
                            raw = (site / name).read_bytes()
                            self.assertEqual(selected[2], str(len(raw)))
                            self.assertEqual(selected[1], "sha256=" + base64.urlsafe_b64encode(__import__("hashlib").sha256(raw).digest()).rstrip(b"=").decode())
                        raise RuntimeError("interrupted")
                self.assertEqual(original, {str(path): (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns) for path in site.rglob("*") if path.is_file()})

    def test_original_wheel_inventory_checks_actual_modes_bytes_and_symlinks(self):
        _, site, sdk_entries, _ = self.installed_tree()
        campaign.snapshot_entries(site, sdk_entries)
        path = site / "biocompiler/core_policy_material.py"
        raw = path.read_bytes(); path.write_bytes(raw + b"#edit")
        with self.assertRaisesRegex(ValueError, "bytes or mode|bound"):
            campaign.snapshot_entries(site, sdk_entries)
        path.write_bytes(raw); path.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "mode"):
            campaign.snapshot_entries(site, sdk_entries)
        path.unlink(); replacement = self.root / "foreign.py"; replacement.write_bytes(raw); path.symlink_to(replacement)
        with self.assertRaisesRegex(ValueError, "redirected"):
            campaign.snapshot_entries(site, sdk_entries)

    def test_bounded_pin_and_duplicate_json_fail_closed(self):
        path = self.root / "content"; path.write_bytes(b"12345")
        with self.assertRaisesRegex(ValueError, "bound"):
            campaign.pin(path, 4)
        path.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            campaign.read_json(path)
        path.write_text('{"a":1.0}')
        with self.assertRaisesRegex(AssertionError, "integer"):
            campaign.read_json(path)

    def test_unrelated_errors_cannot_count_as_installed_negative_controls(self):
        for case, (kind, message) in campaign.ERRORS.items():
            value = {"schema_version": campaign.PROBE_SCHEMA, "status": "rejected", "case": case, "type": kind,
                     "message": message + ": detail", "environment": ENVIRONMENT}
            campaign.check_rejection(value, case)
            for change in ({"message": "anything failed"}, {"type": "ValueError"}, {"status": "pass"}, {"environment": {**ENVIRONMENT, "path": "/usr/bin"}}):
                with self.subTest(case=case, change=change), self.assertRaises(ValueError):
                    campaign.check_rejection({**value, **change}, case)

    def command_fixture(self):
        origin = Path("/hosted/slot"); checkout = Path("/hosted/checkout")
        own = {"sdk_root": str(origin / "env/lib/site-packages/biocompiler"), "package_root": str(origin / "env/lib/site-packages/biocompiler_core"),
               "files": {"bin/biocompiler-" + role: {"path": str(origin / ("env/lib/site-packages/biocompiler_core/bin/biocompiler-" + role))} for role in ("core", "verify")}}
        sdk = "/artifacts/biocompiler-" + campaign.build.VERSION + "-py3-none-any.whl"
        native = "/artifacts/biocompiler_core-" + campaign.build.VERSION + "-" + campaign.build.TARGETS["linux-x86_64"][2] + ".whl"
        python = str(origin / "env/bin/python"); driver = "/driver/python"; fixture = Path("/original/fixture.json")
        receipt = {"checkout_root": str(checkout), "artifacts": {"sdk": {"name": Path(sdk).name}, "native_files": {Path(native).name: {}}}}
        plans = [("create-environment", [driver, "-m", "venv", "--without-pip", str(origin / "env")]),
                 ("install", campaign.foundation.install_plan(Path(driver), Path(python), Path(sdk), Path(native)))]
        def probe(name, mode, inputs=False):
            argv = [python, "-I", "-B", str(checkout / "tools/check_policy_material_prebuilt.py"), "--probe", mode,
                    "--output", str(origin / "evidence" / (name + ".json"))]
            if inputs:
                argv += ["--inputs", str(origin / "cwd/original-inputs.json")]
            return name, argv
        plans += [probe("ownership-before", "ownership"), ("material", [python, "-B", str(checkout / "tools/check_policy_material.py"),
            "--core", own["files"]["bin/biocompiler-core"]["path"], "--verify", own["files"]["bin/biocompiler-verify"]["path"],
            "--console", str(origin / "env/bin/biocompiler"), "--fixture", str(fixture), "--output", str(origin / "evidence/material.json")]),
            probe("resolver", "resolver", True)]
        for case in campaign.CASES:
            plans += [probe(case, case, case == "mismatched-profile"), probe(case + "-restored", "ownership")]
        plans += [("consumer", [python, "-B", str(checkout / "tools/check_policy_material_consumer.py"), "--verify", own["files"]["bin/biocompiler-verify"]["path"],
             "--fixture", str(fixture), "--producer-receipt", str(origin / "evidence/material.json"), "--network", "required", "--output", str(origin / "evidence/consumer.json")]),
             ("uninstall", [driver, "-m", "pip", "--python", python, "uninstall", "--yes", "biocompiler-core"]), probe("missing", "missing"),
             ("reinstall", campaign.foundation.install_plan(Path(driver), Path(python), Path(sdk), Path(native))), probe("ownership-after", "ownership")]
        logs = self.root / "logs"; logs.mkdir()
        rows = []
        for name, argv in plans:
            files = {}
            for suffix in ("stdout", "stderr"):
                path = logs / (name + "." + suffix + ".log"); path.write_bytes(b"bounded test-only log")
                files[str(path.relative_to(self.root))] = campaign.pin(path)
            rows.append({"name": name, "argv": argv, "cwd": str(origin / "cwd"), "executable": {"sha256": "e" * 64, "size": 123},
                         "returncode": 0, "timeout": False, "overflow": False,
                         "environment": "empty_path_scrubbed_loaders" if "--probe" in argv else "scrubbed_loaders", "logs": files})
        return rows, origin, own, fixture, receipt

    def test_full_exact_command_ledger_and_cross_checkout_paths(self):
        rows, origin, own, fixture, receipt = self.command_fixture()
        campaign.check_commands(self.root, rows, origin, own, Path("/downloaded/fixture.json"), receipt)
        mutations = []
        changed = deepcopy(rows); changed[1]["argv"].remove("--no-index"); mutations.append(changed)
        changed = deepcopy(rows); changed[1]["argv"][8] = "--no-binary=:all:"; mutations.append(changed)
        changed = deepcopy(rows); changed[2]["argv"].remove("-I"); mutations.append(changed)
        changed = deepcopy(rows); changed[2]["environment"] = "scrubbed_loaders"; mutations.append(changed)
        changed = deepcopy(rows); changed[3]["argv"][2] = "/foreign/check_policy_material.py"; mutations.append(changed)
        changed = deepcopy(rows); changed[-5]["argv"][-3] = "deferred"; mutations.append(changed)
        changed = deepcopy(rows); changed[-3]["returncode"] = 1; mutations.append(changed)
        changed = deepcopy(rows); changed.pop(); mutations.append(changed)
        changed = deepcopy(rows); changed.append(deepcopy(changed[-1])); mutations.append(changed)
        for index, changed in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises((ValueError, IndexError)):
                campaign.check_commands(self.root, changed, origin, own, fixture, receipt)
        next((self.root / name) for name in rows[0]["logs"]).write_bytes(b"changed retained command log")
        with self.assertRaisesRegex(ValueError, "logs differ"):
            campaign.check_commands(self.root, rows, origin, own, fixture, receipt)

    def test_failed_and_oversized_command_logs_are_bounded_retained_and_never_pass(self):
        from types import SimpleNamespace
        import sys
        for name, stdout, code in (("failed", b"actual failed command output", 7), ("overflow", b"x" * 17, 0)):
            process = SimpleNamespace(stdout=io.BytesIO(stdout), stderr=io.BytesIO(b"reason"), pid=777777,
                                      returncode=code, wait=lambda **kwargs: code)
            with patch.object(campaign.subprocess, "Popen", return_value=process), patch.object(campaign.os, "killpg"), \
                 patch.object(campaign, "MAX_LOG", 16 if name == "overflow" else 128):
                with self.assertRaisesRegex(ValueError, "Command failed"):
                    campaign.command(self.root, name, [str(Path(sys.executable).absolute()), "inert-test-command"],
                                     cwd=self.root, environment={"PATH": ""})
            retained = campaign.read_json(self.root / "commands.json")[-1]
            self.assertEqual(retained["name"], name)
            self.assertEqual(retained["returncode"], code)
            self.assertEqual(retained["overflow"], name == "overflow")
            self.assertEqual((self.root / "logs" / (name + ".stdout.log")).read_bytes(), stdout[:16] if name == "overflow" else stdout)

    def test_resolver_probe_freshly_checks_and_exports_both_roles_with_original_inputs(self):
        from argparse import Namespace
        from types import ModuleType, SimpleNamespace
        import sys
        calls = []
        inputs = {"request": {"original": "authority"}, "candidate": {"untrusted": "proposal"}, "limits": {"bound": 1},
                  "checked": {"receipt": "checked"}, "exported": {"receipt": "exported"}}
        path = self.root / "inputs.json"; campaign.write_json(path, inputs)
        ownership = {"inert_test_identity": "owned"}
        modules = {name: ModuleType(name) for name in ("biocompiler", "biocompiler.core_client", "biocompiler.core_distribution", "biocompiler.core_policy_material")}
        modules["biocompiler"].__path__ = []
        class CoreUnavailable(Exception):
            pass
        class CoreProtocolError(Exception):
            pass
        modules["biocompiler.core_client"].CoreUnavailable = CoreUnavailable
        modules["biocompiler.core_client"].CoreProtocolError = CoreProtocolError
        modules["biocompiler.core_distribution"].installed_distribution = lambda: SimpleNamespace(ownership=lambda: ownership)
        def installed_core(**kwargs):
            calls.append(("resolve", kwargs)); return kwargs["role"]
        modules["biocompiler.core_distribution"].installed_core = installed_core
        def client(role):
            def act(operation, request, candidate, limits):
                calls.append((operation, role, request, candidate, limits))
                return SimpleNamespace(result=deepcopy(inputs["checked" if operation == "check" else "exported"]))
            return SimpleNamespace(check=lambda *args: act("check", *args), export=lambda *args: act("export", *args))
        modules["biocompiler.core_policy_material"].PolicyMaterialClient = client
        args = Namespace(probe="resolver", inputs=path, output=self.root / "resolver.json")
        with patch.dict(sys.modules, modules), patch.object(campaign, "probe_environment", return_value=ENVIRONMENT):
            campaign.probe(args)
            self.assertEqual([row[0] for row in calls], ["resolve", "check", "export", "resolve", "check", "export"])
            for row in calls:
                if row[0] != "resolve":
                    self.assertEqual(row[2:], (inputs["request"], inputs["candidate"], inputs["limits"]))
            mutated = deepcopy(inputs); mutated["request"]["original"] = "changed source"
            campaign.write_json(path, mutated)
            # A forged saved receipt is not accepted merely because it says pass.
            modules["biocompiler.core_policy_material"].PolicyMaterialClient = lambda role: SimpleNamespace(
                check=lambda *a: SimpleNamespace(result={"status": "pass"}), export=lambda *a: SimpleNamespace(result=inputs["exported"]))
            with self.assertRaisesRegex(ValueError, "fresh check/export differs"):
                campaign.probe(args)

    def test_candidate_original_authority_rejected_before_archive_or_install(self):
        sdk = self.root / ("biocompiler-" + campaign.build.VERSION + "-py3-none-any.whl"); sdk.write_bytes(b"inert")
        candidate = {key: {} for key in campaign.CANDIDATE_KEYS}
        candidate.update(schema_version="biocompiler.prebuilt_candidate_validation.v1", status="pass", source_revision="b" * 40,
                         tested_revision="a" * 40, run_id="1234", native_execution=False,
                         acceptance="staged bytes verified; installed four-runtime gates required")
        path = self.root / "candidate.json"
        with patch.object(campaign.release_check, "read_wheel", side_effect=AssertionError("must reject before archive")):
            for edit in ({"source_revision": "c" * 40}, {"tested_revision": "c" * 40}, {"run_id": "old"},
                         {"native_execution": True}, {"status": "failed"}, {"unexpected": True}):
                campaign.write_json(path, {**candidate, **edit})
                with self.subTest(edit=edit), self.assertRaises(ValueError):
                    campaign.candidate_authority(path, sdk, IDENTITY)

    def ownership_fixture(self):
        environment = Path("/hosted/env")
        site = environment / "lib/python3.14/site-packages"
        package = site / "biocompiler_core"; sdk = site / "biocompiler"
        release = {"unexecuted": "pure ownership fixture"}
        sdk_entries = {"biocompiler/" + name: ((campaign.build.canonical(release) if name == "_core_release.json" else name.encode()), 0o644)
                       for name in ("__init__.py", "core_distribution.py", "core_client.py", "_core_release.json")}
        native_entries = {"biocompiler_core/" + name: (name.encode(), 0o755 if name.startswith("bin/") else 0o644) for name in campaign.build.FILES}
        manifest = {"source_revision": IDENTITY["head_revision"], "tested_revision": IDENTITY["revision"], "run_id": IDENTITY["run_id"],
                    "native_platform": "linux-x86_64", "files": {name: {"sha256": campaign.build.sha(native_entries["biocompiler_core/" + name][0]),
                    "size": len(native_entries["biocompiler_core/" + name][0])} for name in campaign.build.FILES}}
        native = {"distribution": manifest, "entries": native_entries}
        ownership = {"schema_version": "biocompiler.installed_core_ownership.v1", "package_root": str(package), "sdk_root": str(sdk),
                     **{key: manifest[key] for key in ("source_revision", "tested_revision", "run_id", "native_platform")},
                     "release_sha256": campaign.build.sha(campaign.build.canonical(release)),
                     "distribution_sha256": campaign.build.sha(campaign.build.canonical(manifest)),
                     "manifest_sha256": campaign.build.sha(native_entries["biocompiler_core/binaries.json"][0]),
                     "files": {name: {"path": str(package / name), **pin} for name, pin in manifest["files"].items()},
                     "sdk_files": {name.split("/", 1)[1]: {"path": str(site / name), "sha256": campaign.build.sha(raw), "size": len(raw)}
                                   for name, (raw, _) in sdk_entries.items()}}
        value = {"schema_version": campaign.PROBE_SCHEMA, "status": "owned", "ownership": ownership,
                 "inventory": {name: {"path": str(site / name), "sha256": campaign.build.sha(raw), "size": len(raw), "mode": mode}
                               for entries in (sdk_entries, native_entries) for name, (raw, mode) in entries.items()},
                 "origins": {name: str(sdk / file) for name, file in {"biocompiler": "__init__.py", "biocompiler.core_distribution": "core_distribution.py",
                            "biocompiler.core_client": "core_client.py"}.items()},
                 "runtime": {"system": "Linux", "machine": "x86_64", "python_version": "3.14.0"}, "environment": deepcopy(ENVIRONMENT)}
        return value, sdk_entries, native, {"release": release}, environment

    def test_complete_owned_inventory_rejects_omission_edit_escape_and_boolean(self):
        value, sdk, native, candidate, environment = self.ownership_fixture()
        campaign.check_ownership(value, sdk, native, candidate, environment)
        edits = []
        changed = deepcopy(value); changed["inventory"].pop(next(iter(changed["inventory"]))); edits.append(changed)
        changed = deepcopy(value); changed["inventory"]["foreign.py"] = {}; edits.append(changed)
        changed = deepcopy(value); changed["ownership"]["files"]["bin/biocompiler-verify"]["sha256"] = "0" * 64; edits.append(changed)
        changed = deepcopy(value); changed["ownership"]["package_root"] = "/outside/biocompiler_core"; edits.append(changed)
        changed = deepcopy(value); changed["origins"]["biocompiler.core_distribution"] = "/checkout/src/biocompiler/core_distribution.py"; edits.append(changed)
        changed = deepcopy(value); changed["environment"]["isolated"] = 1; edits.append(changed)
        for index, changed in enumerate(edits):
            with self.subTest(index=index), self.assertRaises(ValueError):
                campaign.check_ownership(changed, sdk, native, candidate, environment)

    def test_four_slot_comparison_passes_original_receipts_and_actual_wheel_bytes_to_existing_gates(self):
        from argparse import Namespace
        import importlib
        material = importlib.import_module("check_policy_material")
        slots = [("Linux", "x86_64", "3.11"), ("Linux", "x86_64", "3.14"), ("Darwin", "arm64", "3.11"), ("Darwin", "arm64", "3.14")]
        paths = [self.root / str(index) for index in range(4)]
        originals = {}
        for path, slot in zip(paths, slots):
            (path / "evidence").mkdir(parents=True)
            campaign.write_json(path / "prebuilt.json", {"system": slot[0], "machine": slot[1], "python_version": slot[2] + ".7", "run_attempt": "2"})
            for name in ("material", "consumer"):
                campaign.write_json(path / "evidence" / (name + ".json"), {"inert_unchecked_test_receipt": [*slot, name]})
                originals[path / "evidence" / (name + ".json")] = (path / "evidence" / (name + ".json")).read_bytes()
        fixture = self.root / "fixture.json"; fixture.write_text("{}")
        args = Namespace(compare=paths, platform_root=[self.root / "linux", self.root / "mac"], material_authority=[self.root / "a", self.root / "b"],
                         release_candidate=self.root / "candidate.json", sdk=self.root / "sdk.whl", fixture=fixture, output_dir=self.root / "comparison")
        def platform_data(root, *args):
            target = "linux-x86_64" if root.name == "linux" else "macos-arm64"
            entries = {"biocompiler_core/binaries.json": (campaign.canonical({"test": target}), 0o644)}
            entries.update({"biocompiler_core/bin/" + role: ((target + role).encode(), 0o755) for role in campaign.build.ROLES})
            return {"target": target, "entries": entries, "stamp": {"producer_run_attempt": "1"}}
        def gate(producers, native_root, actual_fixture):
            self.assertEqual(producers, [path / "evidence/material.json" for path in paths])
            self.assertEqual(actual_fixture, fixture)
            for target in campaign.build.TARGETS:
                self.assertEqual((native_root / target / "binaries.json").read_bytes(), campaign.canonical({"test": target}))
                for role in campaign.build.ROLES:
                    self.assertEqual((native_root / target / role).read_bytes(), (target + role).encode())
            self.assertTrue(all(path.read_bytes() == raw for path, raw in originals.items()))
            return {"status": "test_stub_pass"}
        def offline_gate(consumers, producers, native_root, actual_fixture):
            self.assertEqual(consumers, [path / "evidence/consumer.json" for path in paths])
            return gate(producers, native_root, actual_fixture)
        with patch.object(campaign, "hosted_identity", return_value=IDENTITY), patch.object(campaign, "candidate_authority", return_value=({}, {}, {"producer_run_attempt": "1"})), \
             patch.object(campaign, "platform_authority", side_effect=platform_data), patch.object(campaign, "verify_slot", side_effect=[(slot, {}) for slot in slots]), \
             patch.object(campaign, "source_pins", return_value={}), patch.object(material, "compare", side_effect=gate) as original_gate, \
             patch.object(campaign.consumer, "compare", side_effect=offline_gate) as consumer_gate:
            value = campaign.compare(args)
        self.assertEqual(original_gate.call_count, 1)
        self.assertEqual(consumer_gate.call_count, 1)
        self.assertEqual([row["run_attempt"] for row in value["slots"]], ["2"] * 4)
        self.assertEqual([row["upstream_attempts"] for row in value["slots"]], [{"sdk": "1", "native": "1"}] * 4)
        self.assertEqual(value["run_attempt"], "3")

    def test_compare_requires_all_distinct_slots_before_any_semantic_comparison(self):
        from argparse import Namespace
        args = Namespace(compare=[self.root / str(i) for i in range(4)], platform_root=[self.root / "linux", self.root / "mac"],
                         material_authority=[self.root / "linux/material-authority.json", self.root / "mac/material-authority.json"],
                         release_candidate=self.root / "candidate.json", sdk=self.root / "sdk.whl", fixture=self.root / "fixture.json", output_dir=self.root / "out")
        slots = [("Linux", "x86_64", "3.11"), ("Linux", "x86_64", "3.14"), ("Darwin", "arm64", "3.11"), ("Darwin", "arm64", "3.14")]
        import importlib
        material = importlib.import_module("check_policy_material")
        with patch.object(campaign, "hosted_identity", return_value=IDENTITY), patch.object(campaign, "candidate_authority", return_value=({}, {}, {})), \
             patch.object(campaign, "platform_authority", side_effect=lambda root, *a: {"target": "linux-x86_64" if root.name == "linux" else "macos-arm64"}), \
             patch.object(material, "compare", side_effect=AssertionError("no delegated comparator before source slot checks")), \
             patch.object(campaign.consumer, "compare", side_effect=AssertionError("no delegated comparator before source slot checks")):
            args.compare.pop()
            with self.assertRaisesRegex(ValueError, "exactly four"):
                campaign.compare(args)
            args.compare.append(self.root / "3")
            with patch.object(campaign, "verify_slot", side_effect=[(slots[0], {}), (slots[0], {}), (slots[2], {}), (slots[3], {})]):
                with self.assertRaisesRegex(ValueError, "Duplicate prebuilt"):
                    campaign.compare(args)
            with patch.object(campaign, "verify_slot", side_effect=ValueError("stale evidence")):
                with self.assertRaisesRegex(ValueError, "stale evidence"):
                    campaign.compare(args)


    def test_component_pairs_are_explicit_complete_and_versioned(self):
        from argparse import Namespace
        self.assertEqual(campaign.component_pairs(Namespace(), 1), [])
        self.assertNotEqual(campaign.SCHEMA, campaign.COMPONENT_SCHEMA)
        self.assertNotEqual(campaign.PROBE_SCHEMA, campaign.COMPONENT_PROBE_SCHEMA)
        for count in (1, 2):
            fixtures = [self.root / ('fixture' + str(i)) for i in range(count)]
            provenances = [self.root / ('provenance' + str(i)) for i in range(count)]
            self.assertEqual(campaign.component_pairs(Namespace(component_fixture=fixtures, component_provenance=provenances), count), list(zip(fixtures, provenances)))
            for left, right in ((fixtures, []), ([], provenances), (fixtures * 2, provenances), (fixtures, provenances * 2)):
                with self.subTest(count=count, left=left, right=right), self.assertRaisesRegex(ValueError, 'fixture/provenance pair'):
                    campaign.component_pairs(Namespace(component_fixture=left, component_provenance=right), count)

    def test_component_profile_byte_mutations_restore_both_roles_and_record(self):
        ownership, site, sdk_entries, _ = self.installed_tree()
        name = 'biocompiler/core_policy_component_material.py'
        raw = b'VALIDATION_SCOPE = "policy-component-mrna-v0.1"\n'
        sdk_entries[name] = (raw, 0o644); (site / name).write_bytes(raw)
        metadata = 'biocompiler-' + campaign.build.VERSION + '.dist-info/RECORD'
        (site / metadata).write_bytes(record({k: v for k, v in sdk_entries.items() if k != metadata}, metadata))
        before = {str(p): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in site.rglob('*') if p.is_file()}
        for case in ('component-profile-core', 'component-profile-verify'):
            with self.assertRaisesRegex(RuntimeError, 'deliberate interruption'):
                with campaign.installed_mutation(case, ownership) as changes:
                    self.assertEqual([x['path'] for x in changes], [str(site / name), str(site / metadata)])
                    self.assertEqual((site / name).read_bytes(), b'VALIDATION_SCOPE = "foreign-component-profile"\n')
                    row = next(x for x in csv.reader(io.StringIO((site / metadata).read_text())) if x[0] == name)
                    self.assertEqual(row[2], str(len((site / name).read_bytes())))
                    self.assertTrue(all(x['before'] != x['after'] for x in changes))
                    raise RuntimeError('deliberate interruption')
            self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in site.rglob('*') if p.is_file()})

    def component_probe_fixture(self, mode):
        inputs = {label: {'request': {'source': label}, 'limits': {'bound': 7}, 'candidate': {'proposal': label},
                         'checked': {'checked': label}, 'exported': {'exported': label}} for label in ('A', 'B')}
        before = {'ownership': {'literal_owner': 'owned'}, 'environment': deepcopy(ENVIRONMENT)}
        if mode == 'component-resolver':
            results = {label: {role: {'checked': {'checked': label}, 'exported': {'exported': label}} for role in ('core', 'verify')} for label in ('A', 'B')}
        else:
            role = 'verify' if mode == 'component-role' else mode.removeprefix('component-profile-')
            message = 'Component production requires an explicitly selected Core producer' if mode == 'component-role' else 'Selected executable lacks the exact component material profile'
            results = {label: {role: {'type': 'CoreProtocolError', 'message': message}} for label in ('A', 'B')}
        value = {'schema_version': campaign.COMPONENT_PROBE_SCHEMA, 'status': 'pass' if mode == 'component-resolver' else 'rejected',
                 'case': mode, **deepcopy(before), 'results': results}
        return inputs, before, value

    def test_component_probe_exact_outputs_roles_and_earliest_errors(self):
        for mode in ('component-resolver', 'component-role', 'component-profile-core', 'component-profile-verify'):
            inputs, before, value = self.component_probe_fixture(mode)
            campaign.check_component_probe(value, mode, inputs, before)
            mutants = []
            changed = deepcopy(value); changed['results'].pop('B'); mutants.append(changed)
            changed = deepcopy(value); changed['results']['A']['foreign-role'] = {}; mutants.append(changed)
            changed = deepcopy(value); changed['environment']['isolated'] = 1; mutants.append(changed)
            changed = deepcopy(value); changed['schema_version'] = campaign.PROBE_SCHEMA; mutants.append(changed)
            changed = deepcopy(value); changed['ownership'] = {'literal_owner': 'foreign'}; mutants.append(changed)
            changed = deepcopy(value); changed['results']['A'] = deepcopy(changed['results']['B']);
            if mode == 'component-resolver': mutants.append(changed)
            else:
                changed = deepcopy(value); next(iter(changed['results']['A'].values()))['message'] = 'any failure'; mutants.append(changed)
            for changed in mutants:
                with self.subTest(mode=mode, changed=changed), self.assertRaises(ValueError):
                    campaign.check_component_probe(changed, mode, inputs, before)

    def test_component_actual_probe_calls_complete_originals_on_each_owned_role(self):
        from argparse import Namespace
        from types import ModuleType, SimpleNamespace
        import sys
        inputs, before, expected = self.component_probe_fixture('component-resolver')
        path = self.root / 'inputs.json'; campaign.write_json(path, inputs)
        calls = []
        modules = {name: ModuleType(name) for name in ('biocompiler', 'biocompiler.core_client', 'biocompiler.core_distribution', 'biocompiler.core_policy_component_material')}
        modules['biocompiler'].__path__ = []
        class CoreUnavailable(Exception): pass
        class CoreProtocolError(Exception): pass
        modules['biocompiler.core_client'].CoreUnavailable = CoreUnavailable
        modules['biocompiler.core_client'].CoreProtocolError = CoreProtocolError
        modules['biocompiler.core_distribution'].installed_distribution = lambda: SimpleNamespace(ownership=lambda: before['ownership'])
        def resolve(**kwargs):
            calls.append(('resolve', kwargs)); return kwargs['role']
        modules['biocompiler.core_distribution'].installed_core = resolve
        mode = 'component-resolver'
        def client(role):
            def act(operation, request, *tail):
                calls.append((operation, role, deepcopy(request), deepcopy(tail)))
                if mode != 'component-resolver':
                    raise CoreProtocolError('Component production requires an explicitly selected Core producer' if mode == 'component-role' else 'Selected executable lacks the exact component material profile')
                return SimpleNamespace(result=inputs[request['source']]['checked' if operation == 'check' else 'exported'])
            return SimpleNamespace(check=lambda *a: act('check', *a), export=lambda *a: act('export', *a), compile=lambda *a: act('compile', *a))
        modules['biocompiler.core_policy_component_material'].PolicyComponentMaterialClient = client
        with patch.dict(sys.modules, modules), patch.object(campaign, 'probe_environment', return_value=ENVIRONMENT):
            for mode in ('component-resolver', 'component-role', 'component-profile-core', 'component-profile-verify'):
                calls.clear(); args = Namespace(probe=mode, inputs=path, output=self.root / (mode + '.json'))
                campaign.probe(args)
                self.assertEqual(campaign.read_json(args.output), self.component_probe_fixture(mode)[2])
                resolved = [row[1] for row in calls if row[0] == 'resolve']
                roles = ['core', 'verify', 'core', 'verify'] if mode == 'component-resolver' else ['verify' if mode == 'component-role' else mode.removeprefix('component-profile-')] * 2
                self.assertEqual(resolved, [{'role': role, 'operation': 'check-policy-component-material', 'timeout_seconds': 60} for role in roles])
                for row in calls:
                    if row[0] != 'resolve':
                        original = inputs[row[2]['source']]
                        self.assertEqual(row[3], (original['limits'],) if row[0] == 'compile' else (original['candidate'], original['limits']))
            modules['biocompiler.core_policy_component_material'].PolicyComponentMaterialClient = lambda role: SimpleNamespace(check=lambda *a: (_ for _ in ()).throw(CoreProtocolError('unrelated boundary')))
            with self.assertRaisesRegex(ValueError, 'unrelated boundary'):
                campaign.probe(Namespace(probe='component-profile-core', inputs=path, output=self.root / 'wrong.json'))

    def test_component_fixture_authority_uses_supplied_bytes_each_platform_and_rejects_duplicate(self):
        import importlib
        tool = importlib.import_module('check_policy_component_fixture')
        pairs=[]; native={}; calls=[]
        for target, platform_value in (('linux-x86_64', ('Linux','x86_64')), ('macos-arm64', ('Darwin','arm64'))):
            directory=self.root/target; directory.mkdir()
            fixture=directory/'originals.json'; fixture.write_text('{"same":"original"}')
            provenance=directory/'provenance.json'; campaign.write_json(provenance, {'platform':dict(zip(('system','machine'),platform_value))})
            pairs.append((fixture,provenance)); native[target]={'entries':{'biocompiler_core/bin/biocompiler-'+role:((target+role).encode(),0o755) for role in ('core','verify')}}
        def validate(root, fixture, provenance, **kwargs):
            calls.append((fixture,provenance,kwargs)); return {'sources':{'literal':'source'}}
        with patch.object(tool,'validate',side_effect=validate):
            result=campaign.component_authorities(pairs,IDENTITY,native)
            self.assertEqual(set(result),{('Linux','x86_64'),('Darwin','arm64')})
            for (fixture,provenance,kwargs), target in zip(calls, native):
                self.assertEqual(kwargs['identity'],IDENTITY)
                self.assertEqual(kwargs['native_sha256'],{role:campaign.build.sha((target+role).encode()) for role in ('core','verify')})
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                campaign.component_authorities([pairs[0],pairs[0]],IDENTITY,native)
            pairs[1][0].write_text('{"different":"original"}')
            with self.assertRaisesRegex(ValueError,'packets differ'):
                campaign.component_authorities(pairs,IDENTITY,native)
        with patch.object(tool,'validate',side_effect=AssertionError('stale source/run/emitter')):
            with self.assertRaisesRegex(AssertionError,'stale source/run/emitter'):
                campaign.component_authorities(pairs,IDENTITY,native)

    def test_component_command_ledger_is_additive_and_rejects_missing_guards(self):
        rows, origin, own, fixture, receipt = self.command_fixture()
        for role in ('core','verify'): own['files']['bin/biocompiler-'+role]['sha256']=('c' if role=='core' else 'd')*64
        authority={'fixture':Path('/original/component/originals.json'),'provenance':Path('/original/component/provenance.json')}
        python=str(origin/'env/bin/python'); checkout=Path(receipt['checkout_root'])
        plans=[]
        for name in ('component-material','component-resolver','component-role','component-profile-core','component-profile-core-restored','component-profile-verify','component-profile-verify-restored','component-consumer'):
            if name=='component-material':
                argv=[python,'-B',str(checkout/'tools/check_policy_component_material.py'),'--installed','--fixture',str(authority['fixture']),'--fixture-provenance',str(authority['provenance']),
                      '--core',own['files']['bin/biocompiler-core']['path'],'--core-sha256','c'*64,'--verify',own['files']['bin/biocompiler-verify']['path'],'--verify-sha256','d'*64,'--output',str(origin/'evidence/component-material.json')]
            elif name=='component-consumer':
                argv=[python,'-B',str(checkout/'tools/check_policy_material_consumer.py'),'--profile','component','--fixture',str(authority['fixture']),'--fixture-provenance',str(authority['provenance']),
                      '--producer-receipt',str(origin/'evidence/component-material.json'),'--verify',own['files']['bin/biocompiler-verify']['path'],'--core-sha256','c'*64,'--network','required','--output',str(origin/'evidence/component-consumer.json')]
            else:
                argv=[python,'-I','-B',str(checkout/'tools/check_policy_material_prebuilt.py'),'--probe','ownership' if name.endswith('-restored') else name,'--output',str(origin/'evidence'/(name+'.json'))]
                if not name.endswith('-restored'): argv+=['--inputs',str(origin/'cwd/component-original-inputs.json')]
            logs={}
            for suffix in ('stdout','stderr'):
                path=self.root/'logs'/(name+'.'+suffix+'.log'); path.write_bytes(b'inert component log'); logs[str(path.relative_to(self.root))]=campaign.pin(path)
            plans.append({'name':name,'argv':argv,'cwd':str(origin/'cwd'),'executable':{'sha256':'e'*64,'size':123},'returncode':0,'timeout':False,'overflow':False,
                          'environment':'empty_path_scrubbed_loaders' if '--probe' in argv else 'scrubbed_loaders','logs':logs})
        original_names=[r['name'] for r in rows]; split=next(i for i,r in enumerate(rows) if r['name']=='uninstall'); rows[split:split]=plans
        self.assertEqual([r['name'] for r in rows if r not in plans],original_names)
        campaign.check_commands(self.root,rows,origin,own,fixture,receipt,component_authority=authority)
        mutants=[]
        for name,flag,value in (('component-material','--installed',None),('component-material','--core-sha256','0'*64),('component-material','--verify-sha256','0'*64),
                               ('component-consumer','--network','deferred'),('component-consumer','--profile','material'),('component-consumer','--verify',own['files']['bin/biocompiler-core']['path']),
                               ('component-resolver','--inputs',str(origin/'cwd/original-inputs.json')),('component-role','-I',None)):
            changed=deepcopy(rows); argv=next(r for r in changed if r['name']==name)['argv']; index=argv.index(flag)
            if value is None: argv.pop(index)
            else: argv[index+1]=value
            mutants.append(changed)
        changed=deepcopy(rows); changed.pop(split); mutants.append(changed)
        changed=deepcopy(rows); changed.insert(split,deepcopy(changed[split])); mutants.append(changed)
        for changed in mutants:
            with self.assertRaises((ValueError,IndexError)):
                campaign.check_commands(self.root,changed,origin,own,fixture,receipt,component_authority=authority)
        with self.assertRaisesRegex(ValueError,'ledger differs'):
            campaign.check_commands(self.root,rows,origin,own,fixture,receipt)


    def test_component_staging_pins_every_sidecar_without_using_output_as_original(self):
        import importlib
        component=importlib.import_module('check_policy_component_material')
        evidence=self.root.resolve()/'evidence'; (evidence/'component-material').mkdir(parents=True)
        fixture={'cases':[{'id':label,'request':{'original_request':label},'limits':{'original_limit':9}} for label in ('A','B')]}
        authority={'fixture':self.root/'originals.json','provenance':self.root/'provenance.json','sources':{'authored':'source'},
                   'pins':{'fixture':{'sha256':'f'*64},'provenance':{'sha256':'e'*64}}}
        binaries={'biocompiler-core':'a'*64,'biocompiler-verify':'b'*64}; slot=('Linux','x86_64','3.11')
        receipt={'schema_version':component.INSTALLED_SCHEMA,'status':'pass',**IDENTITY,'system':slot[0],'machine':slot[1],'python_version':'3.11.15',
                 'package':'/installed/biocompiler','binary_sha256':binaries,'fixture_sha256':'f'*64,'fixture_provenance_sha256':'e'*64,
                 'source_snapshot_sha256':campaign.core.canonical_digest(authority['sources']),'python_semantic_authority':'forbidden','observations':[]}
        observations=[]
        for label in ('A','B'):
            for name in component.CASE_NAMES:
                value={'candidate':{'proposal':label},'report':{'saved':label}}
                if name=='export-verify': value={**value,'artifact':{'pair':label}}
                relative='component-material/'+label+'-'+name+'.json'; path=evidence/relative; campaign.write_json(path,value)
                receipt['observations'].append({'case':label,'name':name,'path':relative,'sha256':campaign.pin(path)['sha256'],'bytes':path.stat().st_size})
                observations.append({'case':label,'name':name,'result':value})
        receipt['observations_fingerprint']=campaign.core.canonical_digest(observations)
        def checked(value):
            return campaign.component_resolver_inputs(value,evidence,authority,IDENTITY,binaries,slot,'/installed/biocompiler')
        with patch.object(component,'checked_fixture',return_value=fixture), patch.object(component,'author_request',side_effect=AssertionError('No parent authoring imports')):
            result=checked(receipt)
            for label in ('A','B'):
                self.assertEqual(result[label]['request'],{'original_request':label}); self.assertEqual(result[label]['limits'],{'original_limit':9})
                self.assertEqual(result[label]['candidate'],{'proposal':label})
            for key,value in (('run_attempt','2'),('revision','c'*40),('package','/checkout/biocompiler'),('fixture_provenance_sha256','0'*64),('binary_sha256',{'biocompiler-core':'0'*64,'biocompiler-verify':'b'*64})):
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'authority differs'): checked({**receipt,key:value})
            omitted=deepcopy(receipt); omitted['observations'].pop(); omitted['observations_fingerprint']=campaign.core.canonical_digest(observations[:-1])
            with self.assertRaisesRegex(ValueError,'census differs'): checked(omitted)
            changed=deepcopy(receipt); changed['observations'][0]['path']='../escape.json'
            with self.assertRaisesRegex(AssertionError,'Unsafe'): checked(changed)
            path=evidence/receipt['observations'][0]['path']; path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(AssertionError,'bytes changed'): checked(receipt)

    def test_component_full_validation_delegation_is_mandatory_for_final_slot(self):
        import importlib
        component=importlib.import_module('check_policy_component_material')
        receipt={'untrusted_receipt':True}; evidence=self.root/'evidence'; authority={'fixture':self.root/'originals.json','provenance':self.root/'provenance.json','sources':{'original':'fullsource'}}
        binaries={'biocompiler-core':'a'*64,'biocompiler-verify':'b'*64}; slot=('Linux','x86_64','3.11'); fixture={'full':'original'}
        with patch.object(component,'checked_fixture',return_value=fixture),patch.object(component,'validate_installed',return_value={'A':{'validated':True},'B':{'validated':True}}) as validate:
            campaign.component_inputs(receipt,evidence,authority,IDENTITY,binaries,slot)
            validate.assert_called_once_with(receipt,evidence,fixture,authority['fixture'],IDENTITY,binaries,expected_sources=authority['sources'],fixture_provenance=authority['provenance'],expected_slot=slot)
        for failure in ('self-consistent omitted sidecar','changed actual ZIP','stale producer receipt','foreign source provenance'):
            with patch.object(component,'checked_fixture',return_value=fixture),patch.object(component,'validate_installed',side_effect=AssertionError(failure)):
                with self.assertRaisesRegex(AssertionError,failure):
                    campaign.component_inputs(receipt,evidence,authority,IDENTITY,binaries,slot)

    def test_expanded_comparison_preserves_old_gates_and_requires_both_new_four_slot_gates(self):
        from argparse import Namespace
        import importlib
        material=importlib.import_module('check_policy_material'); component=importlib.import_module('check_policy_component_material')
        slots=[('Linux','x86_64','3.11'),('Linux','x86_64','3.14'),('Darwin','arm64','3.11'),('Darwin','arm64','3.14')]
        paths=[self.root/str(i) for i in range(4)]
        for path,slot in zip(paths,slots):
            path.mkdir();campaign.write_json(path/'prebuilt.json',{'system':slot[0],'machine':slot[1],'python_version':slot[2]+'.6','run_attempt':'2'})
        fixture=self.root/'old.json';fixture.write_text('{}'); authorities={}
        for system,machine in (('Linux','x86_64'),('Darwin','arm64')):
            path=self.root/system;path.mkdir();f=path/'originals.json';p=path/'provenance.json';f.write_text('{}');p.write_text('{}')
            authorities[(system,machine)]={'fixture':f,'provenance':p,'sources':{},'pins':{'fixture':campaign.pin(f),'provenance':campaign.pin(p)}}
        args=Namespace(compare=paths,platform_root=[self.root/'linux',self.root/'mac'],material_authority=[self.root/'a',self.root/'b'],release_candidate=self.root/'candidate.json',
                       sdk=self.root/'sdk.whl',fixture=fixture,output_dir=self.root/'out',component_fixture=[x['fixture'] for x in authorities.values()],component_provenance=[x['provenance'] for x in authorities.values()])
        def native(path,*args):
            target='linux-x86_64' if path.name=='linux' else 'macos-arm64';entries={'biocompiler_core/binaries.json':(b'{"inert":true}',0o644)}
            entries.update({'biocompiler_core/bin/'+role:((target+role).encode(),0o755) for role in campaign.build.ROLES})
            return {'target':target,'entries':entries,'stamp':{'producer_run_attempt':'1'}}
        events=[]; failing=[None]
        def gate(kind,*arguments,**keywords):
            events.append(kind)
            if kind==failing[0]: raise AssertionError('mandatory '+kind+' failure')
            if kind=='component':
                self.assertEqual(arguments[0],[p/'evidence/component-material.json' for p in paths])
                self.assertEqual(arguments[3],{key:row['provenance'] for key,row in authorities.items()})
                for target in campaign.build.TARGETS:
                    self.assertEqual((arguments[1]/target/'biocompiler-verify').read_bytes(),(target+'biocompiler-verify').encode())
            return {'status':'inert_stub_pass','gate':kind}
        def offline(consumers,producers,native_root,actual_fixture,**kwargs):
            if kwargs:
                self.assertEqual(kwargs,{'profile':'component','fixture_provenances':{key:row['provenance'] for key,row in authorities.items()}})
                self.assertEqual(consumers,[p/'evidence/component-consumer.json' for p in paths]);self.assertEqual(producers,[p/'evidence/component-material.json' for p in paths])
                return gate('component-offline')
            self.assertEqual(consumers,[p/'evidence/consumer.json' for p in paths]);return gate('old-offline')
        with patch.object(campaign,'hosted_identity',return_value=IDENTITY),patch.object(campaign,'candidate_authority',return_value=({}, {}, {'producer_run_attempt':'1'})),\
             patch.object(campaign,'platform_authority',side_effect=native),patch.object(campaign,'component_authorities',return_value=authorities),\
             patch.object(campaign,'verify_slot',side_effect=lambda directory,*a:(slots[paths.index(directory)],{})) as verify,\
             patch.object(campaign,'source_pins',return_value={}),patch.object(material,'compare',side_effect=lambda *a:gate('old-material')),\
             patch.object(campaign.consumer,'compare',side_effect=offline),patch.object(component,'compare_installed',side_effect=lambda *a:gate('component',*a)):
            value=campaign.compare(args)
            self.assertEqual(events,['old-material','old-offline','component','component-offline']);self.assertEqual(verify.call_count,4)
            self.assertTrue(all(call.args[-1] is authorities for call in verify.call_args_list))
            self.assertEqual(value['schema_version'],campaign.COMPONENT_SCHEMA);self.assertEqual(value['claim'],campaign.COMPONENT_CLAIM)
            for index,name in enumerate(('old-material','old-offline','component','component-offline')):
                failing[0]=name;events.clear();args.output_dir=self.root/('failed'+str(index))
                with self.assertRaisesRegex(AssertionError,'mandatory '+name+' failure'):campaign.compare(args)
                self.assertFalse(args.output_dir.exists())
                self.assertEqual(events[-1],name)


    def component_control_fixture(self, *, installed=False):
        ownership,site,sdk_entries,_=self.installed_tree()
        module='biocompiler/core_policy_component_material.py';raw=b'VALIDATION_SCOPE = "policy-component-mrna-v0.1"\n'
        sdk_entries[module]=(raw,0o644);(site/module).write_bytes(raw)
        metadata='biocompiler-'+campaign.build.VERSION+'.dist-info/RECORD'
        entry_points=metadata.removesuffix('RECORD')+'entry_points.txt'
        sdk_entries[entry_points]=(b'[console_scripts]\nbiocompiler = biocompiler.entrypoint:main\n',0o644)
        (site/entry_points).write_bytes(sdk_entries[entry_points][0])
        sdk_entries[metadata]=(record({k:v for k,v in sdk_entries.items() if k!=metadata},metadata),0o644)
        original_record=sdk_entries[metadata][0]
        if installed:
            rows=list(csv.reader(io.StringIO(original_record.decode())))
            empty_hash='sha256='+base64.urlsafe_b64encode(__import__('hashlib').sha256(b'').digest()).rstrip(b'=').decode()
            rows.extend([[metadata.removesuffix('RECORD')+name,empty_hash,'0']
                         for name in ('INSTALLER','REQUESTED','direct_url.json')])
            rows.extend([['../../../bin/biocompiler',empty_hash,'0'],
                         ['biocompiler/__pycache__/core_policy_component_material.cpython-314.pyc','','']])
            stream=io.StringIO(newline='');csv.writer(stream,lineterminator='\r\n').writerows(rows)
            original_record=stream.getvalue().encode()
        (site/metadata).write_bytes(original_record)
        inputs,before,resolver=self.component_probe_fixture('component-resolver');before['ownership']=ownership;resolver['ownership']=ownership
        before['runtime']={'system':'Linux','machine':'x86_64','python_version':'3.14.6'}
        data={'ownership-before':before,'component-resolver':resolver,'component-role':self.component_probe_fixture('component-role')[2],'component-controls':[]}
        data['component-role']['ownership']=ownership
        (self.root/'evidence').mkdir()
        for case in ('component-profile-core','component-profile-verify'):
            rejection=self.component_probe_fixture(case)[2];rejection['ownership']=ownership
            # Actual inert mutation, independently checked against source wheel
            # bytes below; no executable or packaging call is possible.
            with campaign.installed_mutation(case,ownership) as changes:
                row={'case':case,'changes':deepcopy(changes),'rejection':rejection,'restored':campaign.consumer.digest(before)}
            row['installed_record']={'before':original_record.decode(),'restored':campaign.pin(site/metadata)}
            data['component-controls'].append(row)
            campaign.write_json(self.root/'evidence'/(case+'.json'),rejection)
            campaign.write_json(self.root/'evidence'/(case+'-restored.json'),before)
        return data,inputs,sdk_entries,metadata

    def test_component_control_receipts_bind_exact_original_and_changed_wheel_bytes(self):
        data,inputs,sdk_entries,metadata=self.component_control_fixture()
        campaign.check_component_controls(self.root,data,inputs,sdk_entries)
        mutations=[]
        changed=deepcopy(data);changed['component-controls'][0]['changes'][0]['before']['sha256']='0'*64;mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][0]['changes'][0]['after']['sha256']='0'*64;mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][1]['changes'][1]['after']['sha256']='0'*64;mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'].pop();mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][0]['restored']='0'*64;mutations.append(changed)
        for changed in mutations:
            with self.assertRaises(ValueError):campaign.check_component_controls(self.root,changed,inputs,sdk_entries)
        campaign.write_json(self.root/'evidence/component-profile-core-restored.json',{'forged':'restoration'})
        with self.assertRaisesRegex(ValueError,'sidecars differ'):campaign.check_component_controls(self.root,data,inputs,sdk_entries)

    def test_installed_record_additions_and_crlf_preserve_exact_wheel_authority(self):
        data,inputs,sdk_entries,metadata=self.component_control_fixture(installed=True)
        campaign.check_component_controls(self.root,data,inputs,sdk_entries)
        row=data['component-controls'][0]
        raw=row['installed_record']['before'].encode()
        self.assertNotEqual(raw,sdk_entries[metadata][0])
        self.assertIn(b'\r\n',raw)
        self.assertEqual(row['changes'][1]['before'],{'sha256':campaign.build.sha(raw),'size':len(raw)})
        module='biocompiler/core_policy_component_material.py'
        changed=sdk_entries[module][0].replace(b'policy-component-mrna-v0.1',b'foreign-component-profile')
        rows=list(csv.reader(io.StringIO(raw.decode(),newline='')))
        for entry in rows:
            if entry[0]==module:
                entry[1]='sha256='+base64.urlsafe_b64encode(__import__('hashlib').sha256(changed).digest()).rstrip(b'=').decode()
                entry[2]=str(len(changed))
        expected=io.StringIO(newline='');csv.writer(expected,lineterminator='\n').writerows(rows)
        expected=expected.getvalue().encode()
        self.assertEqual(row['changes'][1]['after'],{'sha256':campaign.build.sha(expected),'size':len(expected)})
        self.assertEqual(row['installed_record']['restored'],row['changes'][1]['before'])

    def test_installed_record_rejects_missing_changed_duplicate_and_foreign_rows(self):
        data,_,sdk_entries,metadata=self.component_control_fixture(installed=True)
        text=data['component-controls'][0]['installed_record']['before']
        original=list(csv.reader(io.StringIO(text,newline='')))
        cases=[]
        changed=deepcopy(original);changed.pop(0);cases.append(changed)
        changed=deepcopy(original);changed[0][1]='sha256='+'A'*43;cases.append(changed)
        changed=deepcopy(original);changed[0][2]='999';cases.append(changed)
        changed=deepcopy(original);changed.append(deepcopy(changed[-1]));cases.append(changed)
        for path in ('/absolute','../../../../foreign','../../../bin/foreign',
                     'biocompiler/__pycache__/foreign.cpython-314.pyc',
                     'biocompiler/__pycache__/core_policy_component_material.cpython-311.pyc',
                     'biocompiler/../outside.py','biocompiler/foreign.py'):
            changed=deepcopy(original);changed.append([path,'','']);cases.append(changed)
        changed=deepcopy(original);changed[-1][1]='sha256='+'A'*43;cases.append(changed)
        for value in ('-1','00','2097153'):
            changed=deepcopy(original);changed[-2][2]=value;cases.append(changed)
        changed=deepcopy(original);changed[-2][1]='sha256='+'B'*43;cases.append(changed)
        changed=deepcopy(original);next(row for row in changed if row[0]==metadata)[1]='sha256='+'A'*43;cases.append(changed)
        for index,rows in enumerate(cases):
            stream=io.StringIO(newline='');csv.writer(stream,lineterminator='\r\n').writerows(rows)
            with self.subTest(index=index),self.assertRaises(ValueError):
                campaign.component_installed_record(stream.getvalue(),metadata,sdk_entries,'3.14.6')
        for bad in ('"unterminated',text+'bad,extra,row,field\n',None,''):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                campaign.component_installed_record(bad,metadata,sdk_entries,'3.14.6')
        with patch.object(campaign,'MAX_INSTALLED_RECORD',4),self.assertRaises(ValueError):
            campaign.component_installed_record(text,metadata,sdk_entries,'3.14.6')

    def test_component_record_raw_bytes_restoration_and_role_lifecycle_are_bound(self):
        data,inputs,sdk_entries,metadata=self.component_control_fixture(installed=True)
        mutations=[]
        changed=deepcopy(data);del changed['component-controls'][0]['installed_record'];mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][0]['installed_record']['restored']['sha256']='0'*64;mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][0]['changes'][1]['before']['sha256']='0'*64;mutations.append(changed)
        changed=deepcopy(data);changed['component-controls'][0]['changes'][1]['after']['size']+=1;mutations.append(changed)
        changed=deepcopy(data);row=changed['component-controls'][1]
        raw=row['installed_record']['before'].replace('\r\n','\n')
        row['installed_record']['before']=raw
        row['installed_record']['restored']=row['changes'][1]['before']={'sha256':campaign.build.sha(raw.encode()),'size':len(raw.encode())}
        mutations.append(changed)
        for index,changed in enumerate(mutations):
            with self.subTest(index=index),self.assertRaises(ValueError):
                campaign.check_component_controls(self.root,changed,inputs,sdk_entries)

    def test_expanded_and_historical_receipt_shapes_cannot_be_relabelled(self):
        # Schema/census rejection precedes every unavailable artifact lookup.
        receipt={'schema_version':campaign.SCHEMA,'status':'pass',**IDENTITY,'system':'Linux','machine':'x86_64','python_version':'3.11.15',
                 'output_root':'/slot','checkout_root':'/checkout','fixture':{},'source_pins':{},'artifacts':{},'evidence':{},'commands':{},'cases':list(campaign.CASES),
                 'claim':'supplied_prebuilt_material_profile_only','python_semantic_authority':'forbidden','network':'consumer_required_os_denial','default_cutover':'unassessed'}
        campaign.write_json(self.root/'prebuilt.json',receipt)
        args=(self.root,IDENTITY,self.root/'missing-candidate',self.root/'missing-sdk',{}, {}, {}, self.root/'missing-fixture')
        with self.assertRaisesRegex(ValueError,'incomplete prebuilt slot'):campaign.verify_slot(*args,component_authority={})
        expanded={**receipt,'schema_version':campaign.COMPONENT_SCHEMA,'claim':campaign.COMPONENT_CLAIM,'component_originals':{},'component_cases':list(campaign.COMPONENT_CASES)}
        campaign.write_json(self.root/'prebuilt.json',expanded)
        with self.assertRaisesRegex(ValueError,'incomplete prebuilt slot'):campaign.verify_slot(*args)
        expanded['schema_version']=campaign.SCHEMA;campaign.write_json(self.root/'prebuilt.json',expanded)
        with self.assertRaisesRegex(ValueError,'incomplete prebuilt slot'):campaign.verify_slot(*args,component_authority={})


if __name__ == "__main__":
    unittest.main()
