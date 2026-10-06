"""Hosted Verify-only material consumer; no producer or Python semantics in stage.

The staged directory is physically producer-free; the host filesystem is not
isolated. Required network isolation applies to the worker and all descendants.
Explicit deferred mode records producer absence only and cannot pass comparison.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import errno
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile

SCHEMA = "biocompiler.policy_material_consumer_campaign.v0.1"
WORKER_SCHEMA = "biocompiler.policy_material_consumer_worker.v0.1"
MAX_JSON_BYTES = 64 * 1024 * 1024
MODULE_FILES = ("__init__.py", "core_client.py", "core_policy.py", "core_policy_operational.py",
                "core_policy_implementation.py", "core_policy_material.py")
MODULES = {"biocompiler" if name == "__init__.py" else "biocompiler." + name[:-3] for name in MODULE_FILES}
CASES = ("check", "replay", "export", "forged-replay", "stale-source", "changed-budget-replay", "producer-rejected")
NETWORK_SYSCALLS = ("socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
                    "sendto", "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg", "shutdown",
                    "io_uring_setup", "io_uring_enter", "io_uring_register")
INPUT_FILES = {"request": "authority/request.json", "limits": "authority/limits.json",
               "candidate": "proposal/candidate.json", "checked": "expectation/check.json", "exported": "expectation/export.json"}
PRODUCER_ABSENCE = {"core_binary": "absent_from_staged_tree", "producer_modules": "absent_from_staged_tree",
                   "host_filesystem": "not_isolated", "python": "isolated_no_site", "launch_guard": "pinned_staged_verify_only"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    value, consumed = hashlib.sha256(), 0
    maximum = 256 * 1024 * 1024
    with Path(path).open("rb") as stream:
        while chunk := stream.read(min(65536, maximum + 1 - consumed)):
            consumed += len(chunk)
            if consumed > maximum:
                raise AssertionError("Consumer file exceeds its bounded hashing inventory")
            value.update(chunk)
    return value.hexdigest()


def copy_bounded(source, destination, maximum):
    consumed = 0
    with source.open("rb") as original, destination.open("xb") as staged:
        while chunk := original.read(min(65536, maximum + 1 - consumed)):
            consumed += len(chunk)
            if consumed > maximum:
                raise AssertionError("Consumer code grew beyond its bounded staging inventory")
            staged.write(chunk)


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_JSON_BYTES:
        raise AssertionError("Missing, redirected or oversized consumer JSON input")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise AssertionError("Duplicate consumer JSON field")
            result[key] = value
        return result
    def invalid(value):
        raise AssertionError("Consumer JSON number is outside the closed integer wire: " + value)
    with path.open("rb") as stream:
        content = stream.read(MAX_JSON_BYTES + 1)
    if not 0 < len(content) <= MAX_JSON_BYTES:
        raise AssertionError("Consumer JSON input changed beyond its bounded read inventory")
    return json.loads(content, object_pairs_hook=pairs, parse_constant=invalid, parse_float=invalid)


def write_json(path, value):
    content = canonical(value)
    if len(content) > MAX_JSON_BYTES:
        raise AssertionError("Complete consumer evidence exceeds publication bound")
    Path(path).write_bytes(content)


def support():
    try:
        import check_policy_core as core
        import check_policy_material as material
    except ModuleNotFoundError:
        from tools import check_policy_core as core, check_policy_material as material
    return core, material


def slot(value):
    return value["system"], value["machine"], ".".join(value["python_version"].split(".")[:2])


def validate_producer(receipt, fixture, fixture_path, identity, verify_sha, *, expected_slot):
    _, material = support()
    if (receipt.get("schema_version") != material.SCHEMA or receipt.get("status") != "pass"
            or any(receipt.get(key) != identity[key] for key in ("revision", "head_revision", "run_id"))
            or type(receipt.get("run_attempt")) is not str or not receipt["run_attempt"].isdecimal()
            or not 0 < int(receipt["run_attempt"]) <= int(identity["run_attempt"])
            or slot(receipt) != expected_slot or receipt.get("fixture_sha256") != file_digest(fixture_path)
            or receipt.get("binary_sha256", {}).get("biocompiler-verify") != verify_sha
            or receipt.get("python_semantic_authority") != "forbidden"
            or receipt.get("observations_fingerprint") != digest(receipt.get("observations"))):
        raise AssertionError("Producer expectation lacks exact original/source/run/platform/Verify identity")
    if digest(receipt.get("authoring")) != digest(material.authoring_witness(fixture["request"])[1]):
        raise AssertionError("Producer expectation omitted or changed the original Python authoring phase")
    material.check_import_origins(receipt["parent_imports"], receipt["package"], MODULES - {"biocompiler"})
    if set(receipt["cli_guards"]) != set(material.CLI_CASES):
        raise AssertionError("Producer expectation lacks complete installed guards")
    for name, guard in receipt["cli_guards"].items():
        material.check_cli_guard(guard, receipt["package"], receipt["python_version"], case=name)
    material.check_observations(receipt["observations"], fixture)
    outputs = {row["name"]: row["result"] for row in receipt["observations"]}
    return {"request": deepcopy(fixture["request"]), "limits": deepcopy(fixture["limits"]),
            "candidate": deepcopy(outputs["check-verify"]["candidate"]),
            "checked": deepcopy(outputs["check-verify"]), "exported": deepcopy(outputs["export-verify"])}


def stage_consumer(root, package, verify, inputs):
    root, package, verify = Path(root), Path(package), Path(verify)
    if any(root.iterdir()):
        raise AssertionError("Consumer stage must start empty")
    sources = {"consumer.py": Path(__file__).resolve(), "bin/biocompiler-verify": verify}
    sources.update({"transport/biocompiler/" + name: package / name for name in MODULE_FILES})
    for relative, source in sources.items():
        maximum = 256 * 1024 * 1024 if relative.startswith("bin/") else 4 * 1024 * 1024
        if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= maximum:
            raise AssertionError("Missing, redirected or oversized staged code")
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_bounded(source, destination, maximum)
        destination.chmod(0o500 if relative.startswith("bin/") else 0o400)
        if file_digest(destination) != file_digest(source):
            raise AssertionError("Staged code differs from installed original bytes")
    for name, relative in INPUT_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, inputs[name])
        path.chmod(0o400)
    files = {path.relative_to(root).as_posix(): {"sha256": file_digest(path), "bytes": path.stat().st_size}
             for path in sorted(root.rglob("*")) if path.is_file()}
    manifest = {"schema_version": WORKER_SCHEMA, "files": files, "inputs": {name: digest(value) for name, value in inputs.items()},
                "verify_sha256": file_digest(verify), "producer_absence": PRODUCER_ABSENCE}
    write_json(root / "stage.json", manifest)
    (root / "stage.json").chmod(0o400)
    return manifest


def check_manifest(manifest):
    expected = {"consumer.py", "bin/biocompiler-verify", *INPUT_FILES.values(),
                *("transport/biocompiler/" + name for name in MODULE_FILES)}
    if (type(manifest) is not dict or set(manifest) != {"schema_version", "files", "inputs", "verify_sha256", "producer_absence"}
            or manifest["schema_version"] != WORKER_SCHEMA or type(manifest["files"]) is not dict
            or set(manifest["files"]) != expected or manifest["producer_absence"] != PRODUCER_ABSENCE
            or type(manifest["inputs"]) is not dict or set(manifest["inputs"]) != set(INPUT_FILES)):
        raise AssertionError("Consumer stage inventory contains missing or extra authority/code")
    def sha(value):
        return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
    for relative, pin in manifest["files"].items():
        maximum = 256 * 1024 * 1024 if relative.startswith("bin/") else MAX_JSON_BYTES
        if (type(pin) is not dict or set(pin) != {"sha256", "bytes"} or type(pin["bytes"]) is not int
                or not 0 < pin["bytes"] <= maximum or not sha(pin["sha256"])):
            raise AssertionError("Consumer stage byte inventory is invalid or unbounded")
    if (not sha(manifest["verify_sha256"]) or any(not sha(value) for value in manifest["inputs"].values())
            or manifest["files"]["bin/biocompiler-verify"]["sha256"] != manifest["verify_sha256"]):
        raise AssertionError("Stage Verify or input pin differs from supplied authority")
    return expected


def verify_stage(root, manifest):
    expected = check_manifest(manifest)
    paths = list(Path(root).rglob("*"))
    if any(path.is_symlink() for path in paths) or {p.relative_to(root).as_posix() for p in paths if p.is_file()} != expected | {"stage.json"}:
        raise AssertionError("Consumer stage contains producer, foreign, redirected or undeclared files")
    for relative, pin in manifest["files"].items():
        path = Path(root) / relative
        if path.stat().st_size != pin["bytes"] or file_digest(path) != pin["sha256"]:
            raise AssertionError("Consumer stage bytes differ from original installed pins")


def enforce_linux_network_denial():
    """Kernel filter inherited across exec; no Python socket monkeypatch."""
    import ctypes
    try:
        library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as error:
        raise AssertionError("Required Linux libseccomp is unavailable; offline gate is withheld") from error
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    context = library.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise AssertionError("Required Linux network filter could not initialize")
    try:
        # io_uring can create/connect sockets without invoking socket/connect
        # syscall entries, so its complete submission surface is denied too.
        for name in NETWORK_SYSCALLS:
            syscall = library.seccomp_syscall_resolve_name(name.encode("ascii"))
            if syscall < 0 or library.seccomp_rule_add(context, 0x00050000 | errno.EPERM, syscall, 0) != 0:
                raise AssertionError("Required network syscall denial is unavailable: " + name)
        # libseccomp's default no-new-privileges attribute prevents exec from
        # discarding the filter or acquiring privilege to evade it.
        if library.seccomp_load(context) != 0:
            raise AssertionError("Required Linux network filter could not load")
    finally:
        library.seccomp_release(context)


def network_state(mode, mechanism):
    if mode == "deferred":
        if mechanism != "deferred":
            raise AssertionError("Deferred mode cannot claim OS enforcement")
        return {"status": "deferred", "mechanism": "none", "scope": "not_established", "probes": []}
    if mode != "required":
        raise AssertionError("Unknown network isolation mode")
    if platform.system() == "Linux" and mechanism == "linux_libseccomp":
        enforce_linux_network_denial()
    elif platform.system() != "Darwin" or mechanism != "macos_sandbox_exec":
        raise AssertionError("Required OS network isolation is unavailable")
    probes = []
    for name, family in (("IPv4", socket.AF_INET), ("IPv6", socket.AF_INET6)):
        probe = None
        try:
            probe = socket.socket(family, socket.SOCK_STREAM)
            probe.settimeout(1)
            probe.connect(("127.0.0.1" if family == socket.AF_INET else "::1", 9))
        except OSError as error:
            if error.errno not in (errno.EPERM, errno.EACCES):
                raise AssertionError("Network probe failed for an unrelated reason") from error
            probes.append({"family": name, "errno": error.errno})
        else:
            raise AssertionError("OS network denial probe succeeded; offline gate withheld")
        finally:
            if probe is not None:
                probe.close()
    return {"status": "os_denied", "mechanism": mechanism, "scope": "worker_and_descendants", "probes": probes}


class ConsumerBoundary(importlib.abc.MetaPathFinder):
    def __init__(self, root, manifest):
        self.root, self.manifest, self.launches = Path(root).resolve(), manifest, []

    def find_spec(self, fullname, path=None, target=None):
        if (fullname == "biocompiler" or fullname.startswith(("biocompiler.", "_biocompiler", "biocompiler_core"))) and fullname not in MODULES:
            raise ImportError("Consumer stage has no producer/semantic module: " + fullname)
        return None

    def audit(self, event, arguments):
        if event == "subprocess.Popen":
            executable, argv, cwd, environment = arguments
            verify = self.root / "bin/biocompiler-verify"
            if (str(executable) != str(verify) or list(argv) != [str(verify)] or cwd is not None
                    or environment is not None or file_digest(verify) != self.manifest["verify_sha256"]):
                raise AssertionError("Consumer may launch only its exact pinned staged Verify")
            self.launches.append(self.manifest["verify_sha256"])
        elif event in ("os.system", "os.exec", "os.posix_spawn", "os.spawn"):
            raise AssertionError("Consumer disallows alternate executable launch paths")

    def origins(self):
        result = {}
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith(("biocompiler.", "_biocompiler", "biocompiler_core")):
                if name not in MODULES:
                    raise AssertionError("Unexpected producer or semantic module in consumer")
                path = Path(module.__file__).resolve()
                relative = path.relative_to(self.root).as_posix()
                if relative not in self.manifest["files"] or file_digest(path) != self.manifest["files"][relative]["sha256"]:
                    raise AssertionError("Consumer imported a foreign or modified transport")
                result[name] = relative
        if set(result) != MODULES:
            raise AssertionError("Consumer did not load the complete pinned transport closure")
        return result


def exercise(client, transport, inputs):
    from biocompiler.core_client import CoreRejected
    request, candidate, limits = inputs["request"], inputs["candidate"], inputs["limits"]
    results = []
    for name, action, expected in (
        ("check", lambda: client.check(request, candidate, limits), inputs["checked"]),
        ("replay", lambda: client.replay(request, candidate, limits, inputs["checked"]), inputs["checked"]),
        ("export", lambda: client.export(request, candidate, limits), inputs["exported"]),
    ):
        fresh = action().result
        if digest(fresh) != digest(expected):
            raise AssertionError("Fresh consumer result differs from separately supplied expectation: " + name)
        results.append({"name": name, "result": fresh})
    forged = deepcopy(inputs["checked"])
    forged["report"]["empirical"] = "validated"
    forged["report_fingerprint"] = digest(forged["report"])
    stale = deepcopy(request)
    stale["implementation_request"]["document"]["program"]["source_map"][0]["file"] = "consumer-stale-original.py"
    changed_budget = deepcopy(request)
    changed_budget["budgets"]["max_work"] -= 1
    controls = (
        ("forged-replay", "policy_material_replay", "error", lambda: client.replay(request, candidate, limits, forged)),
        ("stale-source", "policy_correspondence", "error", lambda: client.check(stale, candidate, limits)),
        ("changed-budget-replay", "policy_material_replay", "error", lambda: client.replay(changed_budget, candidate, limits, inputs["checked"])),
        ("producer-rejected", "unsupported_operation", "unsupported", lambda: transport.call("compile-policy-material", {"request": request, "limits": limits})),
    )
    for name, code, status, action in controls:
        try:
            action()
        except CoreRejected as error:
            response = error.response
            if response.status != status or response.result is not None or code not in {row.code for row in response.diagnostics}:
                raise AssertionError("Consumer control failed for an unrelated reason: " + name) from error
            result = {"status": response.status, "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics]}
            results.append({"name": name, "result": result})
        else:
            raise AssertionError("Consumer accepted stale, forged or producer authority: " + name)
    return results


def worker(root, mode, mechanism):
    root = Path(root).resolve()
    if Path.cwd().resolve() != root or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise AssertionError("Consumer requires -I -S -B and its separate staged working directory")
    if any("site-packages" in path or "dist-packages" in path for path in sys.path):
        raise AssertionError("Consumer inherited installed producer search paths")
    manifest = read_json(root / "stage.json")
    verify_stage(root, manifest)
    network = network_state(mode, mechanism)
    boundary = ConsumerBoundary(root, manifest)
    sys.meta_path.insert(0, boundary)
    sys.addaudithook(boundary.audit)
    sys.path.insert(0, str(root / "transport"))
    from biocompiler.core_client import CoreClient
    from biocompiler.core_policy_material import PolicyMaterialClient
    inputs = {name: read_json(root / relative) for name, relative in INPUT_FILES.items()}
    if {name: digest(value) for name, value in inputs.items()} != manifest["inputs"]:
        raise AssertionError("Separate original/proposal/expectation inputs changed after staging")
    transport = CoreClient(root / "bin/biocompiler-verify", role="verify", expected_sha256=manifest["verify_sha256"], timeout_seconds=60)
    observations = exercise(PolicyMaterialClient(transport), transport, inputs)
    verify_stage(root, manifest)
    result = {"schema_version": WORKER_SCHEMA, "status": "pass" if mode == "required" else "producer_absence_only",
              "producer_absence": PRODUCER_ABSENCE, "network": network, "stage_manifest": manifest,
              "origins": boundary.origins(), "verify_launches": boundary.launches, "observations": observations,
              "observations_fingerprint": digest(observations)}
    write_json(root / "worker-result.json", result)
    print(json.dumps({"status": result["status"], "worker_fingerprint": digest(result)}))


def worker_command(root, mode):
    command = [sys.executable, "-I", "-S", "-B", str(Path(root) / "consumer.py"), "--worker", str(root), "--network", mode]
    if mode == "deferred":
        return command + ["--mechanism", "deferred"]
    if platform.system() == "Linux":
        return command + ["--mechanism", "linux_libseccomp"]
    if platform.system() == "Darwin":
        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.is_file():
            raise AssertionError("Required macOS sandbox-exec unavailable; offline gate withheld")
        return [str(sandbox), "-p", "(version 1)(allow default)(deny network*)", *command, "--mechanism", "macos_sandbox_exec"]
    raise AssertionError("Required network isolation unsupported on this host")


def check_worker(value, inputs, manifest, *, require_offline=True):
    from biocompiler.core_client import CoreResponse
    from biocompiler.core_policy_material import _result
    check_manifest(manifest)
    for name, relative in INPUT_FILES.items():
        content = canonical(inputs[name])
        if (manifest["inputs"][name] != digest(inputs[name])
                or manifest["files"][relative] != {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}):
            raise AssertionError("Separate original/proposal/expectation byte inventory changed")
    if (set(value) != {"schema_version", "status", "producer_absence", "network", "stage_manifest", "origins", "verify_launches", "observations", "observations_fingerprint"}
            or value["schema_version"] != WORKER_SCHEMA or value["producer_absence"] != PRODUCER_ABSENCE
            or value["stage_manifest"] != manifest or value["observations_fingerprint"] != digest(value["observations"])):
        raise AssertionError("Incomplete or changed consumer worker evidence")
    expected_origins = {"biocompiler" if name == "__init__.py" else "biocompiler." + name[:-3]: "transport/biocompiler/" + name for name in MODULE_FILES}
    if value["origins"] != expected_origins or value["verify_launches"] != [manifest["verify_sha256"]] * 13:
        raise AssertionError("Consumer omitted actual Verify launches or exact transport origins")
    network = value["network"]
    if (set(network) != {"status", "mechanism", "scope", "probes"}
            or (require_offline and (value["status"] != "pass" or network["status"] != "os_denied"))):
        raise AssertionError("Deferred/absent OS network enforcement cannot pass the offline gate")
    if network["status"] == "os_denied":
        if (value["status"] != "pass" or network["mechanism"] not in ("linux_libseccomp", "macos_sandbox_exec") or network["scope"] != "worker_and_descendants"
                or len(network["probes"]) != 2 or [row.get("family") for row in network["probes"]] != ["IPv4", "IPv6"]
                or any(set(row) != {"family", "errno"} or type(row["errno"]) is not int or row["errno"] not in (errno.EPERM, errno.EACCES) for row in network["probes"])):
            raise AssertionError("Consumer OS-denial probes are absent or unrelated")
    elif value["status"] != "producer_absence_only" or network != {"status": "deferred", "mechanism": "none", "scope": "not_established", "probes": []}:
        raise AssertionError("Unknown consumer isolation claim")
    observations = value["observations"]
    if (type(observations) is not list or any(type(row) is not dict or set(row) != {"name", "result"} for row in observations)
            or [row.get("name") for row in observations] != list(CASES)):
        raise AssertionError("Consumer observations missing, duplicated or reordered")
    outputs = {row["name"]: row["result"] for row in observations}
    for name, operation, expected in (("check", "check-policy-material", inputs["checked"]),
                                    ("replay", "replay-policy-material", inputs["checked"]),
                                    ("export", "export-policy-material", inputs["exported"])):
        payload = {key: inputs[key] for key in ("request", "candidate", "limits")}
        if name == "replay":
            payload["report"] = inputs["checked"]
        _result(CoreResponse("consumer-receipt", operation, "ok", outputs[name], (), "verify", "0.1.0"), payload)
        if digest(outputs[name]) != digest(expected):
            raise AssertionError("Consumer copied/changed evidence rather than reproducing the exact expectation")
    for name, code, status in (("forged-replay", "policy_material_replay", "error"), ("stale-source", "policy_correspondence", "error"),
                              ("changed-budget-replay", "policy_material_replay", "error"), ("producer-rejected", "unsupported_operation", "unsupported")):
        row = outputs[name]
        if (type(row) is not dict or set(row) != {"status", "diagnostics"} or row["status"] != status
                or type(row["diagnostics"]) is not list or not row["diagnostics"]
                or any(type(item) is not dict or set(item) != {"code", "message", "path"} or type(item["code"]) is not str
                       or type(item["message"]) is not str or item["path"] is not None and type(item["path"]) is not str for item in row["diagnostics"])
                or code not in {item["code"] for item in row["diagnostics"]}):
            raise AssertionError("Consumer negative control lacks its specific native rejection")


def run(args):
    core, material = support()
    identity = core.source_identity()
    if identity["run_id"] == "local":
        raise AssertionError("Native consumer campaign is hosted-only")
    checkout = Path(__file__).resolve().parents[1]
    spec = importlib.util.find_spec("biocompiler")
    if spec is None or spec.origin is None:
        raise AssertionError("Install the reviewed pure Python package before the consumer campaign")
    package = Path(spec.origin).resolve().parent
    if package.is_relative_to(checkout) or Path.cwd().resolve().is_relative_to(checkout):
        raise AssertionError("Consumer campaign requires installed modules and a directory outside checkout")
    for name in MODULE_FILES:
        if file_digest(package / name) != file_digest(checkout / "src/biocompiler" / name):
            raise AssertionError("Installed transport differs from exact tested source: " + name)
    fixture = material.checked_fixture(args.fixture)
    producer = read_json(args.producer_receipt)
    verify = args.verify.resolve(strict=True)
    verify_sha = file_digest(verify)
    inputs = validate_producer(producer, fixture, args.fixture, identity, verify_sha,
                               expected_slot=(platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"))
    with tempfile.TemporaryDirectory(prefix="policy-material-consumer-") as temporary:
        root = Path(temporary)
        manifest = stage_consumer(root, package, verify, inputs)
        code, stdout, stderr = core.run_bounded(worker_command(root, args.network), cwd=root,
            env={"PATH": str(root / "bin"), "LANG": "C", "LC_ALL": "C"}, timeout=480, maximum=1024 * 1024)
        if code != 0 or stderr:
            raise AssertionError("Verify-only consumer failed closed: " + stderr.decode("utf-8", "replace")[:16000])
        value = read_json(root / "worker-result.json")
        if json.loads(stdout) != {"status": value["status"], "worker_fingerprint": digest(value)}:
            raise AssertionError("Consumer completion differs from complete retained evidence")
        check_worker(value, inputs, manifest, require_offline=args.network == "required")
    return {"schema_version": SCHEMA, "status": value["status"], **identity,
            "system": platform.system(), "machine": platform.machine(), "python_version": platform.python_version(),
            "fixture_sha256": file_digest(args.fixture), "producer_receipt_sha256": file_digest(args.producer_receipt),
            "verify_sha256": verify_sha, "installed_package": str(package),
            "installed_modules": {name: {"origin": str(package / name), "sha256": file_digest(package / name)} for name in MODULE_FILES},
            "worker": value}


def compare(paths, producer_paths, native_root, fixture_path):
    core, material = support()
    identity = core.source_identity()
    material.compare(producer_paths, native_root, fixture_path)
    binaries = core.native_manifests(native_root, identity["revision"])
    fixture = material.checked_fixture(fixture_path)
    producers = {slot(value): (path, value) for path in producer_paths for value in [read_json(path)]}
    expected = {(system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")) for minor in ("3.11", "3.14")}
    if len(paths) != 4 or set(producers) != expected:
        raise AssertionError("All four consumer and original producer slots are required exactly once")
    found, baseline = set(), None
    checkout = Path(__file__).resolve().parents[1]
    for path in paths:
        receipt = read_json(path)
        fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
                  "fixture_sha256", "producer_receipt_sha256", "verify_sha256", "installed_package", "installed_modules", "worker"}
        if type(receipt) is not dict or set(receipt) != fields:
            raise AssertionError("Malformed consumer campaign receipt")
        current = slot(receipt)
        if current not in expected or current in found:
            raise AssertionError("Missing, duplicate or unexpected consumer platform slot")
        found.add(current)
        producer_path, producer = producers[current]
        verify_sha = binaries[receipt["system"].lower()]["sha256"]["biocompiler-verify"]
        if (receipt["schema_version"] != SCHEMA or receipt["status"] != "pass"
                or any(receipt[key] != identity[key] for key in ("revision", "head_revision", "run_id"))
                or type(receipt["run_attempt"]) is not str or not receipt["run_attempt"].isdecimal()
                or not 0 < int(receipt["run_attempt"]) <= int(identity["run_attempt"])
                or receipt["fixture_sha256"] != file_digest(fixture_path) or receipt["producer_receipt_sha256"] != file_digest(producer_path)
                or receipt["verify_sha256"] != verify_sha):
            raise AssertionError("Consumer receipt lacks exact current source/run/original expectation/binary identity")
        inputs = validate_producer(producer, fixture, fixture_path, identity, verify_sha, expected_slot=current)
        manifest = receipt["worker"]["stage_manifest"]
        package = Path(receipt["installed_package"])
        if not package.is_absolute() or ".." in package.parts or set(receipt["installed_modules"]) != set(MODULE_FILES):
            raise AssertionError("Consumer lost installed transport package origins")
        check_manifest(manifest)
        for name, evidence in receipt["installed_modules"].items():
            source = checkout / "src/biocompiler" / name
            expected_pin = file_digest(source)
            if (evidence != {"origin": str(package / name), "sha256": expected_pin}
                    or manifest["files"]["transport/biocompiler/" + name] != {"sha256": expected_pin, "bytes": source.stat().st_size}):
                raise AssertionError("Consumer transport source/origin pin changed")
        folder = "linux-x86_64" if receipt["system"] == "Linux" else "macos-arm64"
        if manifest["files"]["bin/biocompiler-verify"] != {"sha256": verify_sha, "bytes": (native_root / folder / "biocompiler-verify").stat().st_size}:
            raise AssertionError("Consumer staged binary inventory differs from published native bytes")
        if (manifest["files"]["consumer.py"] != {"sha256": file_digest(Path(__file__)), "bytes": Path(__file__).stat().st_size}
                or manifest["verify_sha256"] != verify_sha or manifest["inputs"] != {name: digest(value) for name, value in inputs.items()}):
            raise AssertionError("Consumer worker or separate original-input pins changed")
        check_worker(receipt["worker"], inputs, manifest)
        required_mechanism = "linux_libseccomp" if receipt["system"] == "Linux" else "macos_sandbox_exec"
        if receipt["worker"]["network"]["mechanism"] != required_mechanism:
            raise AssertionError("Consumer network enforcement belongs to another OS")
        fingerprint = receipt["worker"]["observations_fingerprint"]
        if baseline is not None and baseline != fingerprint:
            raise AssertionError("Complete fresh consumer outputs differ across four slots")
        baseline = fingerprint
    return {"schema_version": SCHEMA, "status": "pass", **identity, "slots": sorted(found),
            "fixture_sha256": file_digest(fixture_path), "observations_fingerprint": baseline,
            "producer_absence": PRODUCER_ABSENCE, "network": "os_denied_worker_and_descendants",
            "claim_scope": "fresh_verify_only_bounded_conditional_material_reproduction", "empirical": "unassessed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "producer-receipt", "verify", "output", "native-artifacts", "worker"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--network", choices=("required", "deferred"), default="required")
    parser.add_argument("--mechanism")
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--producer-receipts", type=Path, action="append", default=[])
    args = parser.parse_args()
    if args.worker is not None:
        worker(args.worker, args.network, args.mechanism)
        return
    if args.fixture is None or args.output is None:
        parser.error("--fixture and --output are required")
    if args.compare:
        if args.native_artifacts is None:
            parser.error("--compare requires --native-artifacts and four --producer-receipts")
        value = compare(args.compare, args.producer_receipts, args.native_artifacts, args.fixture)
    else:
        if args.producer_receipt is None or args.verify is None:
            parser.error("--producer-receipt and --verify are required")
        value = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, value)
    print(json.dumps({"status": value["status"], "schema_version": SCHEMA, "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
