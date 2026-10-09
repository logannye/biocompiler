"""Inert retained-evidence controls; no subprocess or native execution is allowed."""
from argparse import Namespace
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_quantitative_assurance as campaign
from tools import check_policy_quantitative_assurance_prebuilt as companion
from tests.test_policy_coupled_wire import paired_export

IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}


class QuantitativeAssuranceCampaignTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.stack(patch("subprocess.Popen", side_effect=AssertionError("Native processes forbidden in inert tests")))
        self.stack(patch("subprocess.run", side_effect=AssertionError("Processes forbidden in inert tests")))
        self.validation = self.stack(patch.object(companion, "validate_result"))
        self.fixtures = {name: json.loads((campaign.ROOT / relative).read_text()) for name, relative in campaign.FIXTURES.items()}
        self.cases = campaign.original_cases(self.fixtures)
        self.binaries = {role: {"sha256": ("c" if role == "core" else "d") * 64, "bytes": 16} for role in ("core", "verify")}
        self.sdk = {}
        self.required = ("biocompiler", "biocompiler.core_client", "biocompiler.core_policy_quantitative_assurance",
            "biocompiler.policy.approximation", "biocompiler.policy.realization_evidence", "biocompiler.policy.quantitative_assurance",
            "biocompiler._policy_coupled_wire")
        for name in self.required:
            relative = name.replace(".", "/") + ("/__init__.py" if name == "biocompiler" else ".py")
            self.sdk[relative] = ((campaign.ROOT / "src" / relative).read_bytes(), 0o644)

    def stack(self, value):
        self.addCleanup(value.stop)
        return value.start()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))

    def packet(self, slot=("Linux", "x86_64", "3.11")):
        directory = self.root / ("-".join(slot))
        directory.mkdir()
        path = directory / companion.RECEIPT
        package = "/archived/" + "-".join(slot) + "/site-packages/biocompiler"
        modules = {}
        for name in self.required:
            relative = name.replace(".", "/") + ("/__init__.py" if name == "biocompiler" else ".py")
            raw = self.sdk[relative][0]
            modules[name] = {"path": str(Path(package).parent / relative), "sha256": companion.base.build.sha(raw), "bytes": len(raw)}
        data = {}
        for name, original, limits, sequence in self.cases:
            data[name + "-originals"] = {"request": original, "limits": limits, "expected_sequence": sequence}
            # Native response validation is mocked only at its explicit boundary;
            # every original, sidecar, command and slot remains real retained data.
            report = {"export_permitted": True, "material": {"status": "checked_component_material"},
                "approximation": {"outcome": "pass", "composition": {"maximum_error": {"numerator": "1" if name == "approximation" else "0"}}},
                "realization_evidence": {"status": "supported"}}
            result = {"candidate": {"inert": name}, "report": report}
            for suffix in ("compile", "check", "replay"): data[name + "-" + suffix] = deepcopy(result)
            data[name + "-export"] = dict(result, artifact={"fasta": ">literal\n" + sequence + "\n"})
            if name == "coupled":
                exported = paired_export(report)
                exported["candidate"] = result["candidate"]
                exported["artifact"]["fasta"] = ">literal\n" + sequence + "\n"
                data[name + "-export"] = exported
        data["insufficient-error-bound"] = {"report": {"export_permitted": False, "approximation": {"outcome": "fail"}, "material": {"status": "checked_component_material"}}}
        data["missing-gated-evidence"] = {"report": {"export_permitted": False, "realization_evidence": {"status": "unassessed"}, "material": {"status": "checked_component_material"}}}
        for name, operation in (("cumulative-budget", "check"), ("failed-bound-export", "export"), ("retained-pass-mutation", "replay"), ("verifier-production-role", "compile")):
            status, code = campaign.NEGATIVE_DIAGNOSTICS[name]
            data[name] = {"status": status, "operation": operation + "-policy-quantitative-assurance", "executable": "verify", "diagnostics": [{"code": code, "message": "retained control"}]}
        rows = []
        for name in campaign.OBSERVATIONS:
            target = path.with_suffix("") / (name + ".json")
            self.write(target, data[name])
            rows.append({"name": name, "path": str(target.relative_to(path.parent)), **campaign.file_pin(target)})
        receipt = {"schema_version": "biocompiler.policy_quantitative_assurance_campaign.v0.1", "status": "pass", "scope": "fresh_native_quantitative_assurance_sdk_with_exact_rna", **IDENTITY,
            "platform": slot[0], "machine": slot[1], "python": slot[2] + ".15", "installed": True, "binaries": self.binaries,
            "inputs": {name: campaign.file_pin(campaign.ROOT / relative) for name, relative in campaign.FIXTURES.items()},
            "imports": {"package": package, "modules": modules, "record_verified": True}, "campaign_script": campaign.file_pin(campaign.__file__),
            "observations": rows, "empirical_function": "unassessed"}
        self.write(path, receipt)
        return path, receipt, package, data

    def validate(self, path, package, slot=("Linux", "x86_64", "3.11")):
        return companion.validate_campaign(path, IDENTITY, slot, self.binaries, self.sdk, package)

    def repin(self, path, receipt, name, raw):
        row = next(row for row in receipt["observations"] if row["name"] == name)
        self.write(path.parent / row["path"], raw)
        row.update(campaign.file_pin(path.parent / row["path"]))
        self.write(path, receipt)

    def test_complete_retained_results_validate_with_full_original_payloads(self):
        path, receipt, package, data = self.packet()
        self.assertEqual(self.validate(path, package), data)
        self.assertEqual(self.validation.call_count, 14)
        calls = self.validation.call_args_list
        self.assertEqual([call.args[2] for call in calls[:4]], ["core", "verify", "verify", "verify"])
        self.assertEqual(calls[2].args[3]["report"], data["approximation-check"])
        self.assertEqual(calls[0].args[3]["request"], self.fixtures["approximation"] and self.cases[0][1])
        self.assertEqual(len(receipt["observations"]), 21)

    def test_missing_duplicate_stale_import_and_native_authorities_fail_closed(self):
        path, receipt, package, _ = self.packet()
        changes = [lambda row: row.update(status="incomplete"), lambda row: row.update(run_id="999"),
            lambda row: row.update(run_attempt="4"), lambda row: row.update(installed=False),
            lambda row: row["observations"].pop(), lambda row: row["observations"].reverse(),
            lambda row: row["binaries"]["core"].update(sha256="0" * 64),
            lambda row: row["imports"].update(record_verified=False),
            lambda row: row["imports"]["modules"]["biocompiler"].update(sha256="0" * 64),
            lambda row: row["imports"]["modules"].pop("biocompiler._policy_coupled_wire"),
            lambda row: row["inputs"].pop("coupled"), lambda row: row.update(empirical_function="verified")]
        for change in changes:
            value = deepcopy(receipt)
            change(value)
            self.write(path, value)
            with self.subTest(change=change), self.assertRaises((AssertionError, ValueError)):
                self.validate(path, package)

    def test_sidecar_bytes_paths_and_inventory_are_rehashed(self):
        path, receipt, package, _ = self.packet()
        row = receipt["observations"][0]
        target = path.parent / row["path"]
        saved = target.read_bytes()
        target.write_bytes(saved + b" ")
        with self.assertRaises(ValueError): self.validate(path, package)
        target.write_bytes(saved)
        bad = deepcopy(receipt)
        bad["observations"][0]["path"] = "../escape.json"
        self.write(path, bad)
        with self.assertRaises(ValueError): self.validate(path, package)
        self.write(path, receipt)
        (path.with_suffix("") / "extra.json").write_text("{}")
        with self.assertRaises(ValueError): self.validate(path, package)

    def test_repinned_original_rna_and_negative_gates_cannot_be_changed(self):
        path, receipt, package, data = self.packet()
        mutations = [
            ("approximation-originals", lambda row: row["request"].update(max_work=1)),
            ("coupled-export", lambda row: row["artifact"].update(fasta=">mutant\nACGU\n")),
            ("evidence-replay", lambda row: row.update(candidate={"inert": "changed"})),
            ("insufficient-error-bound", lambda row: row["report"].update(export_permitted=True)),
            ("missing-gated-evidence", lambda row: row["report"]["realization_evidence"].update(status="supported")),
            ("retained-pass-mutation", lambda row: row.update(status="ok")),
            ("verifier-production-role", lambda row: row.update(executable="core")),
            ("cumulative-budget", lambda row: row["diagnostics"][0].update(code="unrelated-wire-error")),
        ]
        for name, change in mutations:
            raw = deepcopy(data[name]); change(raw)
            self.repin(path, receipt, name, raw)
            with self.subTest(name=name), self.assertRaises((AssertionError, ValueError)):
                self.validate(path, package)
            self.repin(path, receipt, name, data[name])

    def test_installed_command_reuses_owned_environment_and_external_binary_pins(self):
        owner = {"files": {"bin/biocompiler-" + role: {"path": "/owned/bin/" + role, "sha256": role * 8} for role in ("core", "verify")}}
        command = companion.argv(Path("/checkout"), Path("/owned"), owner)
        self.assertEqual(command[:3], ["/owned/env/bin/python", "-B", "/checkout/tools/check_policy_quantitative_assurance.py"])
        self.assertIn("--require-installed", command)
        self.assertEqual(command[command.index("--core-sha256") + 1], "core" * 8)
        self.assertEqual(command[-1], "/owned/quantitative-assurance-installed/quantitative-assurance.json")
        self.assertFalse(any(word in command for word in ("pip", "venv", "dune", "cargo")))
        with patch.dict(os.environ, {"PYTHONPATH": "src", "PYTHONHOME": "/foreign", "LD_LIBRARY_PATH": "/foreign"}):
            environment = companion.base.safe_environment()
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertNotIn("LD_LIBRARY_PATH", environment)
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")

    def test_cross_platform_comparison_requires_four_distinct_equal_complete_results(self):
        self.stack(patch.object(companion.base, "hosted_identity", return_value=IDENTITY))
        self.stack(patch.object(companion.base, "authority_receipt", return_value={"inert": "external wheel authority"}))
        self.stack(patch.object(companion, "check_command"))
        slots = sorted(companion.SLOTS)
        native = {slot[:2]: {"entries": {"biocompiler_core/bin/biocompiler-" + role: (b"inert binary", 0o755) for role in ("core", "verify")}} for slot in slots}
        self.stack(patch.object(companion, "authorities", return_value=({}, self.sdk, {}, native)))
        sdk, candidate = self.root / "sdk.whl", self.root / "candidate.json"
        sdk.write_bytes(b"inert owned wheel")
        self.write(candidate, {})
        self.write(self.root / "hosted-identity.json", IDENTITY)
        directories, owned = [], {}
        for slot in slots:
            directory = self.root / ("slot-" + "-".join(slot))
            output = directory / companion.FOLDER
            for relative in ("prebuilt.json", "commands.json", "evidence/ownership-before.json", "evidence/ownership-after.json"):
                self.write(directory / relative, {"inert": relative})
            self.write(output / "commands.json", [])
            self.write(output / companion.RECEIPT, {"run_attempt": "3", "observations": []})
            ownership = {"sdk_root": "/owned/" + "-".join(slot)}
            owned[directory] = slot, directory, ownership
            self.write(output / "companion.json", {"schema_version": companion.SCHEMA, "status": "pass", **IDENTITY,
                "scope": companion.SCOPE, "slot": list(slot), "origin": str(directory), "checkout": "/source", "baseline": companion.pin(directory / "prebuilt.json"),
                "artifacts": {"inert": "external wheel authority"}, "command": {"logs": {}}, "receipt": companion.pin(output / companion.RECEIPT)})
            directories.append(directory)
        self.stack(patch.object(companion.ownership_gate, "owned_slot", side_effect=lambda path, *args: owned[path]))
        observations = {name: {"inert": name} for name in campaign.OBSERVATIONS}
        observations["coupled-export"] = paired_export()
        boundary = self.stack(patch.object(companion, "validate_campaign", return_value=observations))
        args = Namespace(slot=directories, sdk=sdk, release_candidate=candidate, platform_root=[], material_authority=[], output=self.root / "comparison.json")
        result = companion.compare(args)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(boundary.call_count, 4)
        args.output.unlink()
        for changed in (directories[:3], [directories[0], directories[0], *directories[2:]]):
            with self.subTest(slots=changed), self.assertRaises(ValueError):
                companion.compare(Namespace(**dict(vars(args), slot=changed)))
        different = deepcopy(observations)
        different["coupled-check"]["inert"] = "different"
        boundary.side_effect = [observations, different]
        with self.assertRaises(ValueError): companion.compare(args)

    def test_saved_logical_evidence_expansion_requires_explicit_coupled_identity(self):
        from biocompiler.core_client import CoreProtocolError
        large = [[None] * 1000] * 251
        raw = campaign.observation_bytes("coupled-check", large)
        self.assertEqual(json.loads(raw), large)
        with self.assertRaises(CoreProtocolError): campaign.observation_bytes("evidence-check", large)
        with self.assertRaises(AssertionError): campaign.observation_bytes("unknown-coupled-check", large)

    def test_incremental_complete_hash_preserves_canonical_identity_and_census(self):
        from biocompiler.core_client import encode_json
        values = {name: {"label": name, "value": [None, True, 3, "µ"]} for name in campaign.OBSERVATIONS}
        values["coupled-export"] = paired_export()
        self.assertEqual(campaign.observations_digest(values), hashlib.sha256(encode_json(values)).hexdigest())
        values["coupled-check"] = [[None] * 1000] * 251
        digest = campaign.observations_digest(values)
        # The aggregate is exactly the same full logical canonical JSON, even
        # though its complete tree cannot use the legacy 250k-node codec.
        raw = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        values["coupled-check"] = [[True] * 1000] + [[None] * 1000] * 250
        self.assertNotEqual(campaign.observations_digest(values), digest)
        values.pop("coupled-check")
        with self.assertRaises(AssertionError): campaign.observations_digest(values)

    def test_paired_export_sidecar_has_exact_named_scope_and_complete_digest(self):
        from biocompiler.core_client import CoreProtocolError
        value = paired_export([[None] * 1000] * 510, [[None] * 1000] * 510)
        raw = campaign.observation_bytes("coupled-export", value)
        self.assertEqual(json.loads(raw), value)
        for name in ("coupled-check", "coupled-replay", "coupled-originals", "evidence-export"):
            with self.subTest(name=name), self.assertRaises(CoreProtocolError): campaign.observation_bytes(name, value)
        values = {name: {} for name in campaign.OBSERVATIONS}
        values["coupled-export"] = value
        expected = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(campaign.observations_digest(values), hashlib.sha256(expected).hexdigest())
        values["unlisted"] = {}
        with self.assertRaises(AssertionError): campaign.observations_digest(values)

    def test_workflows_retain_original_gates_and_add_one_campaign_per_surface(self):
        development = (campaign.ROOT / ".github/workflows/policy-development.yml").read_text()
        ci = (campaign.ROOT / ".github/workflows/ci.yml").read_text()
        installed = ci.split("  policy-prebuilt-installed:", 1)[1].split("  policy-prebuilt-reproducibility:", 1)[0]
        comparison = ci.split("  policy-prebuilt-reproducibility:", 1)[1].split("  ci-success:", 1)[0]
        self.assertLess(development.index("check_policy_development.py sdk-all"), development.index("check_policy_quantitative_assurance.py"))
        self.assertEqual(installed.count("check_policy_quantitative_assurance_prebuilt.py run"), 1)
        self.assertEqual(comparison.count("check_policy_quantitative_assurance_prebuilt.py compare"), 1)
        self.assertIn("/quantitative-assurance-installed/", installed)
        for surface, name in ((installed, "Check quantitative assurance in the same exact installed environment"),
                              (comparison, "Compare complete quantitative assurance across four installed runtimes")):
            step = surface.split("- name: " + name, 1)[1].split("      - ", 1)[0]
            self.assertIn("PYTHONPATH: src", step)
        for existing in ("check_policy_material_prebuilt.py", "check_policy_grounded_helper_prebuilt.py", "check_policy_multi_member_prebuilt.py"):
            self.assertIn(existing, installed)
            self.assertIn(existing, comparison)
        for label in ("linux-x86_64-py3.11", "linux-x86_64-py3.14", "macos-arm64-py3.11", "macos-arm64-py3.14"):
            self.assertIn("--slot artifacts/installed/policy-prebuilt-" + label, comparison)


if __name__ == "__main__": unittest.main()
