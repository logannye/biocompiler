"""Inert Verify-only consumer controls; never execute native code or OS filters."""
from copy import deepcopy
import errno
import importlib.util
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from biocompiler.core_client import CoreProtocolError, CoreRejected, CoreResponse, Diagnostic
from tests import test_core_policy_material as peers

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_material_consumer_test_tool", ROOT / "tools/check_policy_material_consumer.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
IDENTITY = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "12345", "run_attempt": "2"}


def inputs():
    request = peers.original()
    candidate = peers.candidate(request)
    limits = peers.fixture()["limits"]
    checked = peers.result({"request": request, "candidate": candidate, "limits": limits})
    exported = deepcopy(checked)
    exported["artifact"] = peers.artifact(request, candidate, limits, checked["report"])
    return {"request": request, "candidate": candidate, "limits": limits, "checked": checked, "exported": exported}


def rejected(operation, code, status="error"):
    return CoreRejected(CoreResponse("inert", operation, status, None,
        (Diagnostic(code, "Inert specific rejection", None),), "verify", "0.1.0"))


class StubVerify:
    def __init__(self, originals):
        self.originals, self.calls = originals, []

    def check(self, request, candidate, limits):
        self.calls.append(("check", deepcopy(request), deepcopy(candidate), deepcopy(limits)))
        if TOOL.digest(request) != TOOL.digest(self.originals["request"]):
            raise rejected("check-policy-material", "policy_correspondence")
        return SimpleNamespace(result=deepcopy(self.originals["checked"]))

    def replay(self, request, candidate, limits, report):
        self.calls.append(("replay", deepcopy(request), deepcopy(candidate), deepcopy(limits), deepcopy(report)))
        if TOOL.digest(request) != TOOL.digest(self.originals["request"]) or TOOL.digest(report) != TOOL.digest(self.originals["checked"]):
            raise rejected("replay-policy-material", "policy_material_replay")
        return SimpleNamespace(result=deepcopy(self.originals["checked"]))

    def export(self, request, candidate, limits):
        self.calls.append(("export", deepcopy(request), deepcopy(candidate), deepcopy(limits)))
        return SimpleNamespace(result=deepcopy(self.originals["exported"]))

    def call(self, operation, payload):
        self.calls.append((operation, deepcopy(payload)))
        raise rejected(operation, "unsupported_operation", "unsupported")


def worker_record(originals, manifest, system="Linux"):
    stub = StubVerify(originals)
    observations = TOOL.exercise(stub, stub, originals)
    return {"schema_version": TOOL.WORKER_SCHEMA, "status": "pass", "producer_absence": deepcopy(TOOL.PRODUCER_ABSENCE),
        "network": {"status": "os_denied", "mechanism": "linux_libseccomp" if system == "Linux" else "macos_sandbox_exec",
                    "scope": "worker_and_descendants", "probes": [{"family": name, "errno": errno.EPERM} for name in ("IPv4", "IPv6")]},
        "stage_manifest": deepcopy(manifest),
        "origins": {"biocompiler" if name == "__init__.py" else "biocompiler." + name[:-3]: "transport/biocompiler/" + name for name in TOOL.MODULE_FILES},
        "verify_launches": [manifest["verify_sha256"]] * 13,
        "observations": observations, "observations_fingerprint": TOOL.digest(observations)}


class MaterialConsumerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / "consumer"
        self.stage.mkdir()
        self.verify = self.root / "inert-verify"
        self.verify.write_bytes(b"NONEXECUTABLE NATIVE RECEIPT PLACEHOLDER")
        self.originals = inputs()
        self.manifest = TOOL.stage_consumer(self.stage, ROOT / "src/biocompiler", self.verify, self.originals)
        guard = patch("subprocess.Popen", side_effect=AssertionError("Pure Python consumer tests never execute native code"))
        guard.start()
        self.addCleanup(guard.stop)

    def test_stage_contains_only_pinned_transport_verify_and_separate_originals(self):
        TOOL.verify_stage(self.stage, self.manifest)
        self.assertFalse((self.stage / "bin/biocompiler-core").exists())
        self.assertFalse((self.stage / "transport/biocompiler/compiler").exists())
        self.assertFalse((self.stage / "transport/biocompiler/policy").exists())
        self.assertEqual(TOOL.read_json(self.stage / "authority/request.json"), self.originals["request"])
        self.assertEqual(TOOL.read_json(self.stage / "expectation/export.json"), self.originals["exported"])
        self.assertNotEqual(TOOL.INPUT_FILES["request"], TOOL.INPUT_FILES["exported"])
        self.assertEqual(self.manifest["producer_absence"]["host_filesystem"], "not_isolated")
        for filename in TOOL.MODULE_FILES:
            self.assertEqual(TOOL.file_digest(self.stage / "transport/biocompiler" / filename), TOOL.file_digest(ROOT / "src/biocompiler" / filename))

    def test_extra_core_missing_module_and_redirected_stage_fail(self):
        extra = self.stage / "bin/biocompiler-core"
        extra.write_bytes(b"foreign producer")
        with self.assertRaises(AssertionError):
            TOOL.verify_stage(self.stage, self.manifest)
        extra.unlink()
        path = self.stage / "transport/biocompiler/core_client.py"
        path.unlink()
        with self.assertRaises(AssertionError):
            TOOL.verify_stage(self.stage, self.manifest)
        path.symlink_to(ROOT / "src/biocompiler/core_client.py")
        with self.assertRaises(AssertionError):
            TOOL.verify_stage(self.stage, self.manifest)

    def test_stage_refuses_self_consistent_extra_producer_inventory(self):
        changed = deepcopy(self.manifest)
        path = self.stage / "bin/biocompiler-core"
        path.write_bytes(b"foreign producer")
        changed["files"]["bin/biocompiler-core"] = {"bytes": path.stat().st_size, "sha256": TOOL.file_digest(path)}
        with self.assertRaises(AssertionError):
            TOOL.verify_stage(self.stage, changed)

    def test_fresh_consumer_calls_and_specific_negative_rejections(self):
        stub = StubVerify(self.originals)
        observations = TOOL.exercise(stub, stub, self.originals)
        self.assertEqual([row["name"] for row in observations], list(TOOL.CASES))
        self.assertEqual([row[0] for row in stub.calls], ["check", "replay", "export", "replay", "check", "replay", "compile-policy-material"])
        self.assertEqual(stub.calls[0][1], self.originals["request"])
        self.assertEqual(stub.calls[1][-1], self.originals["checked"])
        self.assertNotIn("report", stub.calls[-1][1])
        self.assertNotEqual(stub.calls[4][1], self.originals["request"])
        self.assertEqual(self.originals["request"], TOOL.read_json(self.stage / "authority/request.json"))
        for operation in ("replay", "check", "call"):
            stub = StubVerify(self.originals)
            if operation == "call":
                override = lambda *args: SimpleNamespace(result=None)
            elif operation == "replay":
                override = lambda *args: SimpleNamespace(result=deepcopy(self.originals["checked"]))
            else:
                override = lambda *args: SimpleNamespace(result=deepcopy(self.originals["checked"]))
            with self.subTest(operation=operation), patch.object(stub, operation, side_effect=override), self.assertRaises(AssertionError):
                TOOL.exercise(stub, stub, self.originals)

    def test_changed_fresh_result_never_inherits_copied_pass(self):
        stub = StubVerify(self.originals)
        changed = deepcopy(self.originals["checked"])
        changed["report"]["empirical"] = "invented"
        with patch.object(stub, "check", return_value=SimpleNamespace(result=changed)), self.assertRaises(AssertionError):
            TOOL.exercise(stub, stub, self.originals)
        self.assertEqual(stub.calls, [])
        stub = StubVerify(self.originals)
        with patch.object(stub, "call", side_effect=rejected("compile-policy-material", "wrong_reason", "unsupported")), self.assertRaises(AssertionError):
            TOOL.exercise(stub, stub, self.originals)

    def test_complete_worker_receipt_validates_and_mutations_fail(self):
        value = worker_record(self.originals, self.manifest)
        TOOL.check_worker(value, self.originals, self.manifest)
        mutations = (
            lambda v: v["verify_launches"].pop(),
            lambda v: v["origins"].pop("biocompiler.core_policy_material"),
            lambda v: v["network"]["probes"].pop(),
            lambda v: v["network"]["probes"][0].update(errno=errno.ECONNREFUSED),
            lambda v: v["producer_absence"].update(host_filesystem="isolated"),
            lambda v: v["observations"].pop(),
            lambda v: v["observations"][0].update(assurance="invented"),
            lambda v: v["observations"][0]["result"]["report"].update(empirical="invented"),
            lambda v: v["observations"][-1]["result"]["diagnostics"][0].update(code="unrelated"),
        )
        for mutate in mutations:
            changed = deepcopy(value)
            mutate(changed)
            changed["observations_fingerprint"] = TOOL.digest(changed["observations"])
            with self.subTest(mutation=mutate), self.assertRaises((AssertionError, CoreProtocolError)):
                TOOL.check_worker(changed, self.originals, self.manifest)
        modified = deepcopy(self.manifest)
        modified["files"]["authority/request.json"]["bytes"] += 1
        with self.assertRaises(AssertionError):
            TOOL.check_worker(value, self.originals, modified)

    def test_deferred_network_can_never_pass_offline_gate(self):
        value = worker_record(self.originals, self.manifest)
        value["status"] = "producer_absence_only"
        value["network"] = {"status": "deferred", "mechanism": "none", "scope": "not_established", "probes": []}
        TOOL.check_worker(value, self.originals, self.manifest, require_offline=False)
        with self.assertRaises(AssertionError):
            TOOL.check_worker(value, self.originals, self.manifest)

    def test_network_probes_are_os_denial_not_connectivity_failure(self):
        with patch.object(TOOL.platform, "system", return_value="Linux"), patch.object(TOOL, "enforce_linux_network_denial") as enforce:
            with patch.object(TOOL.socket, "socket", side_effect=PermissionError(errno.EPERM, "Inert kernel denial")):
                result = TOOL.network_state("required", "linux_libseccomp")
            self.assertEqual(result["status"], "os_denied")
            self.assertEqual([row["family"] for row in result["probes"]], ["IPv4", "IPv6"])
            enforce.assert_called_once()
            with patch.object(TOOL.socket, "socket", side_effect=OSError(errno.ECONNREFUSED, "No network proof")), self.assertRaises(AssertionError):
                TOOL.network_state("required", "linux_libseccomp")
            with patch.object(TOOL.socket, "socket", return_value=Mock()), self.assertRaises(AssertionError):
                TOOL.network_state("required", "linux_libseccomp")
        probe = Mock()
        probe.connect.side_effect = PermissionError(errno.EACCES, "Inert sandbox denial")
        with patch.object(TOOL.platform, "system", return_value="Darwin"), patch.object(TOOL.socket, "socket", return_value=probe):
            result = TOOL.network_state("required", "macos_sandbox_exec")
        self.assertEqual(result["status"], "os_denied")
        self.assertEqual(probe.close.call_count, 2)

    def test_linux_missing_filter_and_rule_failure_fail_closed_without_native_calls(self):
        with patch("ctypes.CDLL", side_effect=OSError("Unavailable")), self.assertRaises(AssertionError):
            TOOL.enforce_linux_network_denial()
        library = SimpleNamespace(**{name: Mock() for name in ("seccomp_init", "seccomp_syscall_resolve_name", "seccomp_rule_add", "seccomp_load", "seccomp_release")})
        library.seccomp_init.return_value = 123
        library.seccomp_syscall_resolve_name.return_value = 42
        library.seccomp_rule_add.return_value = -1
        with patch("ctypes.CDLL", return_value=library), self.assertRaises(AssertionError):
            TOOL.enforce_linux_network_denial()
        library.seccomp_load.assert_not_called()
        library.seccomp_release.assert_called_once_with(123)

    def test_linux_filter_registers_complete_network_and_io_uring_denial_inventory(self):
        expected = ["socket", "socketpair", "connect", "bind", "listen", "accept", "accept4", "sendto", "sendmsg", "sendmmsg",
                    "recvfrom", "recvmsg", "recvmmsg", "shutdown", "io_uring_setup", "io_uring_enter", "io_uring_register"]
        library = SimpleNamespace(**{name: Mock() for name in ("seccomp_init", "seccomp_syscall_resolve_name", "seccomp_rule_add", "seccomp_load", "seccomp_release")})
        library.seccomp_init.return_value = 123
        library.seccomp_syscall_resolve_name.side_effect = range(100, 100 + len(expected))
        library.seccomp_rule_add.return_value = 0
        library.seccomp_load.return_value = 0
        with patch("ctypes.CDLL", return_value=library):
            TOOL.enforce_linux_network_denial()
        self.assertEqual([call.args for call in library.seccomp_syscall_resolve_name.call_args_list], [(name.encode(),) for name in expected])
        self.assertEqual([call.args for call in library.seccomp_rule_add.call_args_list], [(123, 0x00050000 | errno.EPERM, number, 0) for number in range(100, 100 + len(expected))])
        library.seccomp_load.assert_called_once_with(123)
        library.seccomp_release.assert_called_once_with(123)

    def test_worker_command_has_isolation_flags_and_no_silent_offline_fallback(self):
        with patch.object(TOOL.platform, "system", return_value="Linux"):
            command = TOOL.worker_command(self.stage, "required")
        self.assertEqual(command[1:4], ["-I", "-S", "-B"])
        self.assertEqual(command[-2:], ["--mechanism", "linux_libseccomp"])
        with patch.object(TOOL.platform, "system", return_value="Darwin"), patch.object(Path, "is_file", return_value=False), self.assertRaises(AssertionError):
            TOOL.worker_command(self.stage, "required")
        with patch.object(TOOL.platform, "system", return_value="Darwin"), patch.object(Path, "is_file", return_value=True):
            command = TOOL.worker_command(self.stage, "required")
        self.assertEqual(command[:3], ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"])
        self.assertEqual(TOOL.worker_command(self.stage, "deferred")[-2:], ["--mechanism", "deferred"])

    def test_consumer_launch_guard_rejects_core_foreign_hash_and_alternate_exec(self):
        boundary = TOOL.ConsumerBoundary(self.stage, self.manifest)
        verify = str(self.stage.resolve() / "bin/biocompiler-verify")
        boundary.audit("subprocess.Popen", (verify, [verify], None, None))
        self.assertEqual(boundary.launches, [self.manifest["verify_sha256"]])
        for arguments in ((verify, [verify, "--producer"], None, None), ("biocompiler-core", ["biocompiler-core"], None, None),
                          (verify, [verify], None, {"PATH": "foreign"})):
            with self.assertRaises(AssertionError):
                boundary.audit("subprocess.Popen", arguments)
        with self.assertRaises(AssertionError):
            boundary.audit("os.exec", ())
        with self.assertRaises(ImportError):
            boundary.find_spec("biocompiler.compiler")
        with self.assertRaises(ImportError):
            boundary.find_spec("biocompiler.policy")
        self.assertIsNone(boundary.find_spec("biocompiler.core_policy_material"))

    def test_producer_authoring_evidence_and_original_fixture_identity_are_required(self):
        fixture_path = self.root / "fixture.json"
        fixture = {"request": self.originals["request"], "limits": self.originals["limits"]}
        TOOL.write_json(fixture_path, fixture)
        observations = [{"name": "check-verify", "result": self.originals["checked"]},
                        {"name": "export-verify", "result": self.originals["exported"]}]
        authoring = {"builder": "independent-original-source"}
        receipt = {"schema_version": "inert.producer", "status": "pass", **IDENTITY, "system": "Linux", "machine": "x86_64", "python_version": "3.11.0",
                   "fixture_sha256": TOOL.file_digest(fixture_path), "binary_sha256": {"biocompiler-verify": self.manifest["verify_sha256"]},
                   "python_semantic_authority": "forbidden", "observations": observations, "observations_fingerprint": TOOL.digest(observations),
                   "parent_imports": {}, "package": "/installed/biocompiler", "cli_guards": {}, "authoring": authoring}
        material = SimpleNamespace(SCHEMA="inert.producer", CLI_CASES=(), authoring_witness=Mock(return_value=(None, authoring)),
                                   check_import_origins=Mock(), check_cli_guard=Mock(), check_observations=Mock())
        def validate(value):
            return TOOL.validate_producer(value, fixture, fixture_path, IDENTITY, self.manifest["verify_sha256"], expected_slot=("Linux", "x86_64", "3.11"))
        with patch.object(TOOL, "support", return_value=(None, material)):
            self.assertEqual(validate(receipt), self.originals)
            for field, changed in (("authoring", None), ("fixture_sha256", "0" * 64), ("run_id", "stale"), ("python_semantic_authority", "allowed")):
                with self.subTest(field=field), self.assertRaises(AssertionError):
                    validate({**receipt, field: changed})
        material.authoring_witness.assert_called_with(fixture["request"])

    def test_json_growth_after_stat_and_copy_growth_remain_bounded(self):
        path = self.root / "growing.json"
        path.write_bytes(b"[]")
        stream = BytesIO(b"[" + b" " * 32 + b"]")
        with patch.object(TOOL, "MAX_JSON_BYTES", 16), patch.object(Path, "open") as opened:
            opened.return_value.__enter__.return_value = stream
            with self.assertRaises(AssertionError):
                TOOL.read_json(path)
        self.assertEqual(stream.tell(), 17)
        destination = self.root / "copy"
        with self.assertRaises(AssertionError):
            TOOL.copy_bounded(path, destination, 1)
        self.assertEqual(destination.stat().st_size, 0)

    def test_duplicate_and_redirected_original_json_is_rejected(self):
        path = self.root / "bad.json"
        path.write_text('{"request":1,"request":2}')
        with self.assertRaises(AssertionError):
            TOOL.read_json(path)
        link = self.root / "link.json"
        link.symlink_to(path)
        with self.assertRaises(AssertionError):
            TOOL.read_json(link)
        path.write_text('{"quantity":1.5}')
        with self.assertRaises(AssertionError):
            TOOL.read_json(path)


class MaterialConsumerComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.native = self.root / "native"
        self.originals = inputs()
        self.fixture = self.root / "fixture.json"
        TOOL.write_json(self.fixture, {"request": self.originals["request"], "limits": self.originals["limits"]})
        self.producer_paths, self.consumer_paths, self.receipts, self.binaries = [], [], [], {}
        for system, machine, folder in (("Linux", "x86_64", "linux-x86_64"), ("Darwin", "arm64", "macos-arm64")):
            directory = self.native / folder
            directory.mkdir(parents=True)
            verify = directory / "biocompiler-verify"
            verify.write_bytes(("INERT NONEXECUTABLE " + system).encode())
            pin = TOOL.file_digest(verify)
            self.binaries[system.lower()] = {"sha256": {"biocompiler-verify": pin}}
            stage = self.root / (system + "-stage")
            stage.mkdir()
            manifest = TOOL.stage_consumer(stage, ROOT / "src/biocompiler", verify, self.originals)
            worker = worker_record(self.originals, manifest, system)
            for minor in ("3.11", "3.14"):
                producer_path = self.root / (system + minor + "-producer.json")
                TOOL.write_json(producer_path, {"system": system, "machine": machine, "python_version": minor + ".0", "expectation": "independently retained"})
                self.producer_paths.append(producer_path)
                package = "/installed/biocompiler"
                receipt = {"schema_version": TOOL.SCHEMA, "status": "pass", **IDENTITY, "system": system, "machine": machine, "python_version": minor + ".0",
                    "fixture_sha256": TOOL.file_digest(self.fixture), "producer_receipt_sha256": TOOL.file_digest(producer_path), "verify_sha256": pin,
                    "installed_package": package, "installed_modules": {name: {"origin": package + "/" + name, "sha256": TOOL.file_digest(ROOT / "src/biocompiler" / name)} for name in TOOL.MODULE_FILES},
                    "worker": deepcopy(worker)}
                self.receipts.append(receipt)
                self.consumer_paths.append(self.root / (system + minor + "-consumer.json"))
        self.write()

    def write(self):
        for path, value in zip(self.consumer_paths, self.receipts):
            TOOL.write_json(path, value)

    def compare(self, paths=None):
        core = SimpleNamespace(source_identity=Mock(return_value=IDENTITY), native_manifests=Mock(return_value=self.binaries))
        material = SimpleNamespace(compare=Mock(), checked_fixture=Mock(return_value=TOOL.read_json(self.fixture)))
        with patch.object(TOOL, "support", return_value=(core, material)), patch.object(TOOL, "validate_producer", return_value=self.originals):
            return TOOL.compare(self.consumer_paths if paths is None else paths, self.producer_paths, self.native, self.fixture)

    def test_complete_four_slot_consumer_evidence_passes(self):
        result = self.compare()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(result["network"], "os_denied_worker_and_descendants")
        self.assertEqual(result["producer_absence"]["host_filesystem"], "not_isolated")

    def test_missing_duplicate_stale_or_deferred_slots_do_not_pass(self):
        for paths in (self.consumer_paths[:3], [self.consumer_paths[0]] * 4):
            with self.assertRaises(AssertionError):
                self.compare(paths)
        baseline = deepcopy(self.receipts)
        for field, value in (("run_id", "stale"), ("head_revision", "0" * 40), ("verify_sha256", "0" * 64),
                             ("producer_receipt_sha256", "0" * 64), ("status", "producer_absence_only")):
            self.receipts = deepcopy(baseline)
            self.receipts[0][field] = value
            self.write()
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.compare()

    def test_extra_staged_core_wrong_os_mechanism_and_modified_transport_fail(self):
        baseline = deepcopy(self.receipts)
        mutations = (
            lambda v: v["worker"]["stage_manifest"]["files"].update({"bin/biocompiler-core": {"sha256": "0" * 64, "bytes": 1}}),
            lambda v: v["worker"]["network"].update(mechanism="macos_sandbox_exec"),
            lambda v: v["installed_modules"]["core_policy_material.py"].update(sha256="0" * 64),
            lambda v: v["worker"]["stage_manifest"]["files"]["bin/biocompiler-verify"].update(bytes=1),
            lambda v: v["worker"]["stage_manifest"]["inputs"].update(request="0" * 64),
        )
        for mutate in mutations:
            self.receipts = deepcopy(baseline)
            mutate(self.receipts[0])
            self.write()
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError):
                self.compare()

    def test_identically_rehashed_all_slot_observation_omission_fails(self):
        for receipt in self.receipts:
            receipt["worker"]["observations"].pop()
            receipt["worker"]["observations_fingerprint"] = TOOL.digest(receipt["worker"]["observations"])
        self.write()
        with self.assertRaises(AssertionError):
            self.compare()


if __name__ == "__main__":
    unittest.main()
