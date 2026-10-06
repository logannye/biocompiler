"""Inert campaign receipt adversaries; no native executable is invoked."""
from copy import deepcopy
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_core_policy_material as peers
from tests import test_core_policy_implementation as implementation_peers
from tests import test_core_policy_operational as source_peers
from tests.test_core_policy import assessment as basic_assessment

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_material_campaign_test_tool", ROOT / "tools/check_policy_material.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
FIXTURE = ROOT / "core/test/data/policy_material_request_v01.json"
IDENTITY = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "98765", "run_attempt": "2"}


def assessment(document):
    value = basic_assessment(document)
    value["unresolved_obligations"] = deepcopy(TOOL.OBLIGATIONS)
    return value


def repin(value):
    """Rehash fake evidence after a test mutation; no semantic interpretation."""
    report = value["report"]
    material, context = report["material"], report["context"]
    if material is not None:
        material["preservation_evidence_fingerprint"] = TOOL.canonical_digest(report["preservation"])
    if context is not None:
        context["material_binding_fingerprint"] = TOOL.canonical_digest(material)
    for row in report["obligations"]:
        if row["evidence"] is not None:
            row["evidence"] = {key: TOOL.canonical_digest(report[key]) for key in row["evidence"]}
    value["report_fingerprint"] = TOOL.canonical_digest(report)
    return value


def inert(payload, *, disposition="pass"):
    with patch.object(implementation_peers, "assessment", assessment), patch.object(source_peers, "source_assessment", assessment):
        value = peers.result(payload)
    report = value["report"]
    preservation = report["preservation"]
    preservation["coverage"].update(histories=9, transitions=47, prefixes_started=48, matched_prefixes=48)
    for row in preservation["requirements"]:
        row["histories"].update(**{"pass": 9})
    report["usage"].update(charged_work=1000000, request_decoding_work=480645)
    if disposition != "pass":
        report["status"] = "not_accepted"
        report["all_original_obligations_discharged"] = False
        for row in report["obligations"]:
            row.update(status="unresolved", stage=None, evidence=None)
        if disposition == "material":
            report["material_status"] = "fail"
            report["material"]["outcome"] = "fail"
            structure = report["material"]["structure"]
            structure.update(outcome="fail", content_outcome="fail")
            structure["content_reconstruction"]["outcome"] = "fail"
            report["context"], report["context_status"] = None, "unassessed"
        elif disposition in ("provider", "unsupported"):
            status = "unsupported" if disposition == "unsupported" else "fail"
            report["context_status"] = status
            report["context"]["outcome"] = status
            report["context"]["discharges"] = []
            for row in report["context"]["source_obligations"]:
                row["context_status"] = "outside_stage"
            report["context"]["diagnostics"] = ["independent_delivery_group_unimplemented" if disposition == "unsupported" else "shared_capacity_sum_exceeded"]
        else:
            with patch.object(implementation_peers, "assessment", assessment), patch.object(source_peers, "source_assessment", assessment):
                preservation = implementation_peers.report(payload["request"]["implementation_request"], value["candidate"], payload["limits"], status="incomplete")
            preservation["stopped"]["diagnostic"]["code"] = "policy_preservation_prefix_limit" if disposition == "prefix" else "policy_execution_work_limit"
            report["preservation"] = preservation
            report.update(catalog=None, material=None, context=None, material_status="unassessed", context_status="unassessed")
    return repin(value)


@lru_cache(maxsize=1)
def observations():
    fixture = TOOL.checked_fixture(FIXTURE)
    request, limits = fixture["request"], fixture["limits"]
    with patch.object(source_peers, "source_assessment", assessment):
        candidate = peers.candidate(request)
    compiled = inert({"request": request, "candidate": candidate, "limits": limits})
    exported = deepcopy(compiled)
    exported["artifact"] = peers.artifact(request, candidate, limits, exported["report"])
    values = {name: deepcopy(compiled) for name in ("compile", "check-core", "check-verify", "replay-verify", "compile-cli", "check-cli", "replay-cli")}
    values.update({"export-core": exported, "export-verify": deepcopy(exported), "export-library": TOOL.archive_receipt(exported), "export-cli": TOOL.archive_receipt(exported)})
    for name, kind in (("changed-provider", "provider"), ("unsupported-delivery", "unsupported"), ("prefix-limit", "prefix")):
        values[name] = inert({"request": TOOL.changed_request(request, kind), "candidate": candidate, "limits": limits}, disposition=kind)
    values["source-work-limit"] = inert({"request": request, "candidate": candidate, "limits": TOOL.source_work_limits(limits)}, disposition="source-work")
    values["changed-material"] = inert({"request": request, "candidate": TOOL.changed_candidate(candidate, "material"), "limits": limits}, disposition="material")
    for name, codes in TOOL.NEGATIVE_CODES.items():
        values[name] = {"status": "unsupported" if name == "verify-producer" else "error",
            "diagnostics": [{"code": sorted(codes)[0], "message": "Expected native rejection", "path": None}]}
    values["missing-binary"] = {"status": "transport_error", "type": "CoreUnavailable"}
    values["wrong-role"] = {"status": "transport_error", "type": "CoreProtocolError"}
    values["malformed-replay-cli"] = {"status": "error", "operation": "replay-material-native", "message": "policy_material_replay: Full wrapper differs"}
    return [{"name": name, "result": values[name]} for name in TOOL.CASE_NAMES]


class MaterialCampaignTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.native = self.root / "native"
        pins = {}
        for system, folder, machine in (("Linux", "linux-x86_64", "x86_64"), ("Darwin", "macos-arm64", "arm64")):
            slot = self.native / folder
            slot.mkdir(parents=True)
            binary_pins = {}
            for role in ("core", "verify"):
                binary = slot / ("biocompiler-" + role)
                binary.write_bytes(("Nonexecutable inert receipt bytes: " + system + role).encode())
                binary_pins[binary.name] = TOOL.digest_file(binary)
            (slot / "binaries.json").write_text(json.dumps({"revision": IDENTITY["revision"], "system": system, "machine": machine, "sha256": binary_pins}))
            pins[system] = binary_pins
        self.fixture = TOOL.checked_fixture(FIXTURE)
        self.paths, self.receipts = [], []
        for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")):
            for minor in (11, 14):
                package = "/installed/biocompiler"
                origins = {name: package + "/" + name.rsplit(".", 1)[-1] + ".py" for name in (
                    "biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational", "biocompiler.core_policy_implementation",
                    "biocompiler.core_policy_material", "biocompiler.policy.material", "biocompiler.entrypoint", "biocompiler.policy.cli")}
                guard = {"status": "ok", "guard_active": True, "execution_guard_active": True,
                         "python": [3, minor], "executable": "/installed/python", "origins": origins}
                retained = deepcopy(observations())
                self.receipts.append({"schema_version": TOOL.SCHEMA, "status": "pass", **IDENTITY, "system": system, "machine": machine,
                    "python_version": f"3.{minor}.0", "fixture_sha256": TOOL.digest_file(FIXTURE), "binary_sha256": pins[system], "package": package,
                    "authoring": TOOL.authoring_witness(self.fixture["request"])[1],
                    "parent_imports": origins, "cli_guards": {name: deepcopy(guard) for name in TOOL.CLI_CASES}, "observations": retained,
                    "observations_fingerprint": TOOL.canonical_digest(retained), "python_semantic_authority": "forbidden"})
                self.paths.append(self.root / f"{system}-{minor}.json")
        self.write()

    def write(self):
        for path, receipt in zip(self.paths, self.receipts):
            path.write_text(json.dumps(receipt), encoding="utf-8")

    def compare(self, paths=None):
        with patch.object(TOOL, "source_identity", return_value=IDENTITY):
            return TOOL.compare(self.paths if paths is None else paths, self.native, FIXTURE)

    def test_complete_four_slot_receipts_bind_real_bytes_and_finite_literals(self):
        result = self.compare()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(result["empirical"], "unassessed")
        self.assertEqual(result["artifact"], "fresh_native_pair_checked")
        context = self.receipts[0]["observations"][0]["result"]["report"]["context"]
        self.assertEqual([row["id"] for row in context["source_obligations"]], TOOL.OBLIGATIONS)
        self.assertEqual(len(context["resource_allocations"]), 14)
        self.assertLess(max(path.stat().st_size for path in self.paths), TOOL.MAX_RECEIPT_BYTES)
        self.receipts[0]["run_attempt"] = "1"
        self.write()
        self.assertEqual(self.compare()["status"], "pass")

    def test_slot_source_run_platform_fixture_and_binary_rejections(self):
        for paths in (self.paths[:3], [self.paths[0], self.paths[0], *self.paths[2:]], [*self.paths, self.paths[0]]):
            with self.subTest(paths=paths), self.assertRaises(AssertionError):
                self.compare(paths)
        redirected = self.root / "redirect.json"
        redirected.symlink_to(self.paths[0])
        with self.assertRaises(AssertionError):
            self.compare([redirected, *self.paths[1:]])
        original = deepcopy(self.receipts[0])
        for field, value in (("status", "failed"), ("revision", "0" * 40), ("head_revision", "0" * 40), ("run_id", "1"),
                             ("run_attempt", "0"), ("run_attempt", "3"), ("machine", "arm64"), ("python_version", "3.12.0"),
                             ("fixture_sha256", "0" * 64), ("binary_sha256", {}), ("python_semantic_authority", "allowed"),
                             ("authoring", {})):
            self.receipts[0] = {**deepcopy(original), field: value}
            self.write()
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.compare()
        self.receipts[0] = original
        self.write()
        (self.native / "linux-x86_64/biocompiler-core").write_bytes(b"different nonexecutable bytes")
        with self.assertRaisesRegex(AssertionError, "native bytes"):
            self.compare()

    def test_rehashed_observations_cannot_omit_inventory_or_upgrade_native_claim(self):
        original = deepcopy(self.receipts[0])
        for mutation in (lambda r: r["observations"].pop(), lambda r: r["observations"].reverse(),
                         lambda r: r["observations"].append(deepcopy(r["observations"][0])),
                         lambda r: r["observations"][0]["result"]["report"].update(empirical="validated")):
            self.receipts[0] = deepcopy(original)
            mutation(self.receipts[0])
            self.receipts[0]["observations_fingerprint"] = TOOL.canonical_digest(self.receipts[0]["observations"])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_all_matching_rehashed_receipts_still_require_original_census_and_obligations(self):
        for kind in ("census", "obligations", "context_source_obligations", "context_resource_allocations", "context_derived_demands"):
            changed = deepcopy(observations())
            for row in changed:
                value = row["result"]
                if "report" not in value:
                    continue
                if kind == "obligations":
                    value["report"]["obligations"].clear()
                elif kind.startswith("context_"):
                    context = value["report"]["context"]
                    if context is not None:
                        context[kind.removeprefix("context_")].clear()
                elif value["report"]["status"] == "checked_material":
                    value["report"]["preservation"]["coverage"].update(transitions=46, prefixes_started=47, matched_prefixes=47)
                repin(value)
                if value["artifact"] is not None:
                    value["artifact"] = peers.artifact(self.fixture["request"], value["candidate"], self.fixture["limits"], value["report"])
            exports = next(row["result"] for row in changed if row["name"] == "export-verify")
            for row in changed:
                if row["name"] in ("export-library", "export-cli"):
                    row["result"] = TOOL.archive_receipt(exports)
            for receipt in self.receipts:
                receipt["observations"] = deepcopy(changed)
                receipt["observations_fingerprint"] = TOOL.canonical_digest(changed)
            self.write()
            with self.subTest(kind=kind), self.assertRaisesRegex(AssertionError, "census|independent authority"):
                self.compare()

    def test_exact_export_pair_and_replay_wrapper_cannot_be_substituted(self):
        for name, mutate in (("export-library", lambda v: v.update(sha256="0" * 64)),
                             ("export-cli", lambda v: v["members"].pop()),
                             ("export-verify", lambda v: v["artifact"]["manifest"]["members"].clear()),
                             ("replay-verify", lambda v: v.update(report=v["report"]["preservation"]))):
            changed = deepcopy(observations())
            value = next(row["result"] for row in changed if row["name"] == name)
            mutate(value)
            if "report" in value:
                value["report_fingerprint"] = TOOL.canonical_digest(value["report"])
            if value.get("artifact") is not None:
                value["artifact"]["manifest_sha256"] = TOOL.canonical_digest(value["artifact"]["manifest"])
            with self.subTest(name=name), self.assertRaises(AssertionError):
                TOOL.check_observations(changed, self.fixture)

    def test_specific_failure_unsupported_and_incomplete_dispositions_are_required(self):
        for name, mutate in (("changed-guard", lambda v: v.update(diagnostics=[])),
                             ("verify-producer", lambda v: v.update(status="error")),
                             ("missing-binary", lambda v: v.update(status="ok")),
                             ("unsupported-delivery", lambda v: v["report"]["context"].update(diagnostics=["unrelated"])),
                             ("prefix-limit", lambda v: v["report"]["preservation"]["stopped"]["diagnostic"].update(code="unrelated"))):
            changed = deepcopy(observations())
            value = next(row["result"] for row in changed if row["name"] == name)
            mutate(value)
            if "report" in value:
                repin(value)
            with self.subTest(name=name), self.assertRaises(AssertionError):
                TOOL.check_observations(changed, self.fixture)

    def test_import_guards_and_mutations_preserve_inert_authority(self):
        self.assertTrue(TOOL.MaterialBoundary.allowed("biocompiler.core_policy_material"))
        self.assertFalse(TOOL.ImplementationBoundary.allowed("biocompiler.core_policy_material"))
        boundary = TOOL.MaterialBoundary(self.root)
        with self.assertRaises(ImportError):
            boundary.find_spec("biocompiler.compiler")
        frame = SimpleNamespace(f_globals={"__name__": "biocompiler.policy.validation"}, f_code=SimpleNamespace(co_name="check"))
        with self.assertRaises(AssertionError):
            boundary.trace(frame, "call", None)
        candidate = observations()[0]["result"]["candidate"]
        for kind in ("guard", "state", "feedback", "configuration", "material"):
            self.assertNotEqual(TOOL.changed_candidate(candidate, kind), candidate)
        for kind in ("catalog", "provider", "unsupported", "prefix", "work", "budget"):
            self.assertNotEqual(TOOL.changed_request(self.fixture["request"], kind), self.fixture["request"])
        self.assertEqual(self.fixture, TOOL.checked_fixture(FIXTURE))
        original = deepcopy(self.receipts[0])
        for mutate in (lambda r: r["cli_guards"].pop("export-cli"),
                       lambda r: r["cli_guards"]["export-cli"].update(execution_guard_active=False),
                       lambda r: r["cli_guards"]["export-cli"]["origins"].pop("biocompiler.policy.material"),
                       lambda r: r["parent_imports"].update({"biocompiler.compiler": "/installed/biocompiler/compiler.py"}),
                       lambda r: r["parent_imports"].update({"biocompiler.core_client": "/other/core_client.py"})):
            self.receipts[0] = deepcopy(original)
            mutate(self.receipts[0])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_fixture_is_complete_original_and_cli_fresh_export_checks_actual_pair(self):
        self.assertNotIn("behavior", self.fixture["candidate_parts"])
        self.assertEqual(self.fixture["expected"]["request_decoding_work"], 480645)
        exported = next(row["result"] for row in observations() if row["name"] == "export-verify")
        artifact = exported["artifact"]
        from biocompiler.core_client import encode_json
        from biocompiler.policy.material import _verify_staged
        import zipfile
        archive = self.root / "pair.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
            for name, data in (("program.fasta", artifact["fasta"].encode()), ("manifest.json", encode_json(artifact["manifest"]))):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                output.writestr(info, data)
        self.assertEqual(TOOL.archive_receipt(exported, archive), TOOL.archive_receipt(exported))
        _verify_staged(archive, (("program.fasta", artifact["fasta"].encode()), ("manifest.json", encode_json(artifact["manifest"]))))
        archive.write_bytes(archive.read_bytes()[:-1])
        with self.assertRaises(AssertionError):
            TOOL.archive_receipt(exported, archive)


if __name__ == "__main__":
    unittest.main()
