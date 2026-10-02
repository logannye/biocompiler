"""Run all 72 original synthetic-select children with installed native authority.

Full process, publication and wire evidence is retained. Comparisons use the
immutable original CLI capture and four native public authority literals. Only
validated UUIDs, runtime paths and explicit pinned argparse counterparts are
projected across runtimes; rich SDK helpers and pipeline/export stay separate.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID
if __package__:
    from . import cli_runtime_counterparts as runtime
    from . import freeze_synthetic_selection_cli as frozen
    from . import freeze_workflow_cli as f
    from . import check_workflow_reproducibility as r
    from . import check_native_synthetic_producer as producer
else:
    import cli_runtime_counterparts as runtime
    import freeze_synthetic_selection_cli as frozen
    import freeze_workflow_cli as f
    import check_workflow_reproducibility as r
    import check_native_synthetic_producer as producer
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.native_synthetic_selection_cli_conformance.v1"
SCOPE = "complete_explicit_native_synthetic_selection_cli_no_pipeline_export_or_rich_helper_cutover"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "synthetic-selection-cli.json", "synthetic-selection-cli-artifacts"
BASELINE_PIN = "69556f367752be3076513d96e63c933fb250eaf7d9736f9e39baac1dec47e5d9"
COUNTERPART_PIN = "f9af4b5dedcdb12243209b862d0808866f1ae62355aca291465be75c7f00824b"
PUBLIC_PROFILE_PIN = "5b7d0ffc4f015a46b6432fbdbad824e989683f74abedbe128368012a5a5b4f03"
OPERATION = "select-synthetic-build-request"
OPERATIONS = {OPERATION, "capabilities"}
SOURCES = ("tools/check_native_synthetic_selection_cli.py", "tests/test_native_synthetic_selection_cli_campaign.py",
    "tools/freeze_synthetic_selection_cli.py", "tools/freeze_workflow_cli.py", "tools/cli_runtime_counterparts.py",
    "tools/check_native_synthetic_producer.py", "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py",
    "tests/conformance/synthetic-selection-cli-runtime-counterparts-v1.json", "protocol/synthetic-producer-public-v1.json",
    "protocol/synthetic-producer-v1.json", "core/test/test_synthetic_producer_public_protocol.ml",
    "core/lib/domain/synthetic_build_request.ml", "core/lib/domain/build_request.ml",
    "core/lib/producer_service/synthetic_producer_public_service.ml")
canonical, require, digest = r.canonical, r.require, r.digest
PLATFORMS, PYTHONS, ROLES = r.PLATFORMS, r.PYTHONS, r.ROLES
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_synthetic_producer",
    "biocompiler.core_synthetic_producer_public", "biocompiler.synthetic_producer_backend", "biocompiler.synthetic_producer_cli",
    "biocompiler.core_synthetic_inspection"}
CLI_CALLS = {"main", "_selection_command", "_bounded_text", "_publish_report", "_workflow_core_arguments",
    "_register_circuit_infrastructure_commands", "_architecture_core_arguments", "_synthetic_producer_core_arguments"}


@lru_cache(maxsize=4096)
def allowed_cli_call(module, name, phase, owner):
    if phase != "output" or owner != "": return False
    name = name.split(".<locals>.", 1)[0]
    return (module in TRANSPORT_MODULES or module == "biocompiler.cli" and name in CLI_CALLS
        or module == "biocompiler.__main__" and name == "<module>"
        or module == "biocompiler.ir.serialization" and name in {"parse_json", "require"}
        or module == "biocompiler.errors" and name in {"UnsupportedBehaviorError.__init__", "LoweringError.__init__"})


@contextmanager
def selection_paths():
    # Reuse only the original pure filesystem harness with selection's exclusive
    # namespaces; never run the old Python authoring/selection freezer.
    with patch.object(f, "ORIGINAL_ROOT", frozen.ORIGINAL_ROOT), patch.object(f, "CLI_ROOT", frozen.CLI_ROOT):
        yield


def counterparts():
    return runtime.Counterparts(ROOT / "tests/conformance/synthetic-selection-cli-runtime-counterparts-v1.json",
                                COUNTERPART_PIN, BASELINE_PIN)


def baseline():
    document, blobs = frozen.load()
    require(document["inventory_fingerprint"] == BASELINE_PIN and len(document["cases"]) == 72,
            "Complete immutable selection CLI baseline changed")
    return document, blobs


def cases(document, blobs):
    # Reconstruct every actual occurrence solely from retained original bytes.
    result = []
    for row in document["cases"]:
        case = {key: deepcopy(row[key]) for key in ("id", "argv", "entrypoint", "fault", "lineage")}
        case.update(files={}, directories=[], symlinks={})
        for path, item in row["files_before"].items():
            if item["kind"] == "file": case["files"][path] = f.restore(item["content"], blobs)
            elif item["kind"] == "directory": case["directories"].append(path)
            elif item["kind"] == "symlink": case["symlinks"][path] = item["target"]
            else: raise AssertionError("Unknown original filesystem kind")
        result.append(case)
    require(len(result) == 72 and len({item["id"] for item in result}) == 72, "Original child census changed")
    return result


class Oracle:
    def __init__(self):
        original, blobs = baseline()
        self.cases = {case["id"]: case for case in cases(original, blobs)}
        positive, negative = frozen.reference_fixtures()
        raw = (ROOT / "protocol/synthetic-producer-public-v1.json").read_bytes()
        require(f.sha(raw) == PUBLIC_PROFILE_PIN, "Public native profile declaration changed")
        self.profile = r.decode(raw)
        self.profiles = {**producer.declaration(), "synthetic_producer_public": self.profile}
        self.positive = {digest(row["payload"]["build_request"]): row for row in positive}
        self.negative = {digest(row["build_request"]): row for row in negative}
        self.verify_payload = deepcopy(positive[0]["payload"])

    def inputs(self, case):
        if "--request" not in case["argv"]: return None
        path = case["argv"][case["argv"].index("--request")+1]
        path = case["symlinks"].get(path, path)
        return case["files"].get(os.path.normpath(path))

    def trace(self, identifier):
        case = self.cases[identifier]
        if identifier in {"missing-required-request", "unknown-flag", "help", "invalid-json", "invalid-utf8",
                          "input-one-over", "input-at-limit", "missing-input"}: return None
        raw = self.inputs(case)
        require(raw is not None, "Original complete CLI authority missing")
        source = r.decode(raw); identity = digest(source)
        payload = {"profile": self.profile["profile"], "limits": None, "build_request": source}
        if identity in self.positive:
            fixture = self.positive[identity]
            require(canonical(payload) == canonical(fixture["payload"]), "Immutable complete public authority differs")
            return payload, "ok", deepcopy(fixture["expected"]), []
        require(identity in self.negative, "Unclassified original public CLI authority")
        fixture = self.negative[identity]
        return payload, "error", None, [self.diagnostic(fixture)]

    @staticmethod
    def diagnostic(fixture):
        # Explicit native source locations for the immutable malformed literals.
        # These select locations only; no source acceptance or domain parsing.
        name = fixture["name"]; path = "payload.build_request"
        if name == "source_before_history":
            return {"code": "missing_target", "path": "/target", "message": fixture["message"]}
        if name.startswith("history_") or name in {"initial_time", "unordered"}: path += "/history"
        elif name.startswith("config_"): path += "/config"
        elif name.startswith("frame_") or name in {"contacts_type", "signals_type"}:
            path += "/history/frames/0"
            if name == "signals_type": path += "/signals"
        elif name.startswith("sample_") or name == "numeric_sample": path += "/history/frames/0/contacts/x/n000003"
        return {"code": "synthetic_build_request", "path": path, "message": fixture["message"]}


# sitecustomize is observation/fault injection only. It does not replace main,
# native transport or domain decisions. Every allowed product call is audited.
STARTUP = r'''
import atexit, hashlib, json, os, pathlib, sys
config = json.loads(pathlib.Path(os.environ["BIOCOMPILER_NATIVE_CLI_CONFIG"]).read_bytes())
sys.path.insert(0, config["tools"])
import check_native_synthetic_selection_cli as policy
import biocompiler, biocompiler.cli as cli
import biocompiler.synthetic_producer_cli
import biocompiler.synthetic_producer_backend as backend
import biocompiler.core_synthetic_producer_public
root = pathlib.Path(biocompiler.__file__).resolve().parent
assert not root.is_relative_to(pathlib.Path(config["checkout"]))
fault = config["fault"]
if fault:
    class PublicationOS:
        def __getattr__(self, name): return getattr(os, name)
    cli.os = PublicationOS()
    kind = fault["kind"]
    if kind in ("replace", "fsync"):
        def broken(*args, **kwargs): raise OSError(fault["message"])
        setattr(cli.os, kind, broken)
    elif kind == "short_write":
        original = cli.os.fdopen
        class Short:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def __getattr__(self, key): return getattr(self.stream, key)
            def write(self, raw): return self.stream.write(raw[:-1])
        cli.os.fdopen = lambda *args, **kwargs: Short(original(*args, **kwargs))
    elif kind == "serialized_length":
        backend.NativeProducerDocument.to_json = lambda self: " " * fault["bytes"]
    else: raise AssertionError("Unknown publication fault")
seen, exchanges, receipts = set(), [], {}
def encoded(value): return json.dumps(value,sort_keys=True,separators=(",", ":"),ensure_ascii=False,allow_nan=False).encode()
def retain(raw):
    identity = hashlib.sha256(raw).hexdigest()
    destination = pathlib.Path(config["native_artifacts"]) / (identity + ".bin")
    if destination.exists(): assert destination.read_bytes() == raw
    else: destination.write_bytes(raw)
    return {"sha256":identity,"bytes":len(raw)}
def guard(frame, event, value):
    module, code = frame.f_globals.get("__name__", ""), frame.f_code
    if event == "call" and module.startswith("biocompiler"):
        entry = (module, code.co_qualname, "output", "")
        if not policy.allowed_cli_call(*entry): raise AssertionError("Forbidden Python authority on native selection CLI: " + repr(entry))
        seen.add(entry)
    if event == "return" and module == "biocompiler.core_client" and code.co_name == "_exchange" and value is not None:
        raw, exit_code = value
        exchanges.append({"request":retain(frame.f_locals["request"]),"response":retain(raw),"exit_code":exit_code,
                          "executable":str(frame.f_locals["executable"])})
        wire = json.loads(raw)
        if wire["operation"] == policy.OPERATION and wire["status"] == "ok":
            result = wire["result"]; production = result["production"]
            receipts[wire["request_id"]] = {"outer":retain(encoded(result)),"production":retain(encoded(production)),
                "record":None if production["record"] is None else retain(encoded(production["record"]))}
def audit():
    active = sys.getprofile() is guard
    sys.setprofile(None)
    modules = {}
    for name, module in sorted(sys.modules.items()):
        if name == "biocompiler" or name.startswith("biocompiler."):
            path = pathlib.Path(module.__file__).resolve()
            assert path.is_relative_to(root)
            relative = "src/biocompiler/" + path.relative_to(root).as_posix()
            modules[name] = {"path":relative,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    result = {"scope":config["scope"],"guard_active":active,"functions":sorted(seen),"modules":modules,
              "package_path":str(root),"exchanges":exchanges,"receipts":receipts}
    pathlib.Path(config["audit"]).write_bytes(encoded(result)+b"\n")
atexit.register(audit)
sys.setprofile(guard)
'''


def product_sources():
    return {path.relative_to(ROOT).as_posix(): f.sha(path.read_bytes())
            for path in sorted((ROOT / "src/biocompiler").rglob("*.py"))}


def read_artifacts(directory, declared):
    """Read every complete CLI byte member, including legitimate empty streams."""
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink() and type(declared) is dict and
            all(r.pin(key) for key in declared), "Unsafe CLI evidence inventory")
    require({path.name for path in directory.iterdir()} == {key + ".bin" for key in declared},
            "Missing or extra complete CLI content")
    result = {}
    for identity, descriptor in declared.items():
        require(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"} and
                descriptor["path"] == identity + ".bin" and descriptor["sha256"] == identity and
                type(descriptor["bytes"]) is int and 0 <= descriptor["bytes"] <= f.MAX_OUTPUT + 1,
                "Invalid complete CLI descriptor")
        path = directory / descriptor["path"]
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == descriptor["bytes"],
                "Missing, linked or resized CLI bytes")
        with path.open("rb") as source: raw = source.read(f.MAX_OUTPUT + 2)
        require(len(raw) == descriptor["bytes"] and f.sha(raw) == identity, "Complete CLI bytes differ")
        result[identity] = raw
    return result


def configure_case(case):
    for folder in (f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"):
        folder.mkdir(exist_ok=True)
        for child in folder.iterdir():
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
    for name in case["directories"]: f.safe_path(name).mkdir(parents=True, exist_ok=True)
    for name, raw in case["files"].items():
        path = f.safe_path(name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    for name, target in case["symlinks"].items():
        path = f.safe_path(name); path.parent.mkdir(parents=True, exist_ok=True)
        f.safe_path(target); path.symlink_to(target)


def run_case(case, role, executable, executable_pin, store):
    configure_case(case)
    scope = "native_synthetic_selection"
    before = f.snapshot((f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"), store)
    native_directory = f.CLI_ROOT / "native-artifacts"
    for path in native_directory.iterdir(): path.unlink()
    config = {"tools": str(ROOT / "tools"), "checkout": str(ROOT), "fault": case["fault"],
        "scope": scope, "operations": sorted(OPERATIONS), "audit": str(f.CLI_ROOT / "audit.json"),
        "native_artifacts": str(native_directory)}
    config_path = f.CLI_ROOT / "config.json"
    config_path.write_bytes(canonical(config))
    audit_path = f.CLI_ROOT / "audit.json"; audit_path.unlink(missing_ok=True)
    selected = [
        "--core-executable", str(executable),
        "--core-sha256", executable_pin, "--core-timeout", "300"]
    # Console uses the actual installed script; Python -m uses the actual module.
    console = shutil.which("biocompiler")
    require(console is not None and not Path(console).resolve().is_relative_to(ROOT), "Installed console script missing")
    command = [sys.executable, "-m", "biocompiler"] if case["entrypoint"] == "module" else [console]
    argv = [case["argv"][0], *selected, *case["argv"][1:]]
    environment = {**os.environ, "PYTHONPATH": str(f.CLI_ROOT / "startup"),
        "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
        "BIOCOMPILER_NATIVE_CLI_CONFIG": str(config_path)}
    child = subprocess.run([*command, *argv], cwd=f.CLI_ROOT / "cwd", env=environment,
                           capture_output=True, timeout=900)
    require(audit_path.is_file(), "Installed CLI child did not complete the execution audit")
    audit = r.decode(audit_path.read_bytes())
    artifacts = {}
    for path in native_directory.iterdir():
        require(path.is_file() and not path.is_symlink() and path.suffix == ".bin", "Unsafe child native artifact")
        artifacts[path.stem] = store.retain(path.read_bytes())
    return {"id": case["id"], "role": role, "scope": scope, "argv": argv,
        "entrypoint": case["entrypoint"], "fault": case["fault"], "lineage": case["lineage"],
        "files_before": before, "files_after": f.snapshot((f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"), store),
        "exit_code": child.returncode, "stdout": store.retain(child.stdout), "stderr": store.retain(child.stderr),
        "audit": store.retain(canonical(audit)), "native_artifacts": artifacts,
        "console_path": console, "python_executable": sys.executable}


def equal_observations(actual, original, blobs, old_blobs, *, python_version=None):
    expected = counterparts().expected(original, {"exit_code": original["exit_code"],
        **{field: f.restore(original[field], old_blobs) for field in ("stdout", "stderr")}}, python_version)
    require(type(actual["exit_code"]) is int and actual["exit_code"] == expected["exit_code"],
            "CLI exit differs: " + actual["id"])
    for field in ("stdout", "stderr"):
        require(f.restore(actual[field], blobs) == expected[field],
                "Complete CLI " + field + " differs: " + actual["id"])
    for field in ("files_before", "files_after"):
        left, right = actual[field], original[field]
        require(set(left) == set(right), "Complete CLI filesystem membership differs: " + actual["id"])
        for name, expected in right.items():
            require(type(left[name]) is dict and set(left[name]) == set(expected), "CLI filesystem metadata fields differ")
            require(left[name]["kind"] == expected["kind"], "CLI filesystem kind differs")
            if expected["kind"] == "file":
                require(f.restore(left[name]["content"], blobs) == f.restore(expected["content"], old_blobs),
                        "Complete CLI file bytes differ: " + name)
            else: require(left[name] == expected, "CLI directory or symlink differs")


def uuid_identity(identity, identities):
    try: value = UUID(identity)
    except (TypeError, ValueError, AttributeError) as error:
        raise AssertionError("Invalid actual native request identity") from error
    require(value.version == 4 and str(value) == identity and identity not in identities,
            "Duplicate or invalid actual request identity")
    identities.add(identity)


def content(descriptor, row, blobs, used):
    require(type(descriptor) is dict and set(descriptor) == {"sha256", "bytes"} and
            type(descriptor["bytes"]) is int and descriptor["sha256"] in row["native_artifacts"],
            "Missing complete actual native content")
    raw = f.restore(row["native_artifacts"][descriptor["sha256"]], blobs)
    require(canonical(descriptor) == canonical(r.descriptor(raw)), "Complete native content identity differs")
    used.add(descriptor["sha256"])
    return raw


def validate_exchanges(row, audit, blobs, oracle, executable, *, role="core", identities=None):
    identities = set() if identities is None else identities
    expected = oracle.trace(row["id"]) if role == "core" else (oracle.verify_payload, "unsupported", None, [producer.UNSUPPORTED])
    exchanges = audit["exchanges"]
    require(type(exchanges) is list and len(exchanges) == (0 if expected is None else 2),
            "Missing complete capability/production process trace")
    require(type(audit["receipts"]) is dict, "Invalid retained native receipt inventory")
    used, receipt_ids, projection = set(), set(), []
    for ordinal, exchange in enumerate(exchanges):
        require(type(exchange) is dict and set(exchange) == {"request", "response", "exit_code", "executable"} and
                type(exchange["exit_code"]) is int and exchange["executable"] == executable,
                "Invalid selected native process identity or exit")
        request_raw = content(exchange["request"], row, blobs, used)
        response_raw = content(exchange["response"], row, blobs, used)
        request, response = r.decode(request_raw), r.decode(response_raw)
        require(type(request) is dict and set(request) == {"protocol", "request_id", "operation", "payload"} and
                type(response) is dict and set(response) == {"protocol", "request_id", "operation", "status", "result", "diagnostics", "core"},
                "Unexpected native request/response fields")
        identifier = response["request_id"]
        if ordinal == 0:
            producer.validate_capability(response_raw, role, oracle, identities)
            wanted_request = {"protocol":"biocompiler.core.v1", "request_id":identifier, "operation":"capabilities", "payload":{}}
            require(exchange["exit_code"] == 0, "Native capability process failed")
        else:
            uuid_identity(identifier, identities)
            payload, status, result, diagnostics = expected
            wanted_request = {"protocol":"biocompiler.core.v1", "request_id":identifier, "operation":OPERATION, "payload":payload}
            wanted_response = producer.envelope(role, identifier, OPERATION, status, result, diagnostics)
            require(canonical(response) == canonical(wanted_response) and
                    exchange["exit_code"] == {"ok":0,"error":2,"unsupported":3}[status],
                    "Complete original native receipt, error, scope or numeric identity differs")
            if status == "ok":
                receipt_ids.add(identifier)
                retained = audit["receipts"].get(identifier)
                require(type(retained) is dict and set(retained) == {"outer", "production", "record"},
                        "Complete nested production receipts missing")
                for field, value in (("outer",result), ("production",result["production"]), ("record",result["production"]["record"])):
                    if value is None: require(retained[field] is None, "Unsupported result acquired a record")
                    else: require(content(retained[field],row,blobs,used) == canonical(value),
                                  "Full outer, nested or selection record differs from immutable literal")
        require(request_raw == canonical(wanted_request) and response_raw == canonical(response)+b"\n",
                "Complete actual request or canonical response bytes differ")
        # Exactly one top-level request identity exists in each raw envelope;
        # nested public/v1 receipts have no runtime UUID fields.
        require(request_raw.count(canonical(identifier)) == 1 and response_raw.count(canonical(identifier)) == 1,
                "UUID projection would change unreviewed native content")
        projected_request = request_raw.replace(canonical(identifier),canonical("runtime-request-"+str(ordinal)))
        projected_response = response_raw.replace(canonical(identifier),canonical("runtime-request-"+str(ordinal)))
        projection.append({"request":r.descriptor(projected_request),"response":r.descriptor(projected_response),
                           "exit_code":exchange["exit_code"]})
    require(set(audit["receipts"]) == receipt_ids and used == set(row["native_artifacts"]),
            "Unbound complete native receipt or wire bytes")
    return projection


def validate_audit(row, audit, blobs, sources, oracle, *, executable=None, identities=None):
    require(type(audit) is dict and set(audit) == {"scope", "guard_active", "functions", "modules", "package_path", "exchanges", "receipts"},
            "Unexpected complete selection CLI audit fields")
    require(audit["scope"] == row["scope"] == "native_synthetic_selection" and audit["guard_active"] is True,
            "Missing selected-native execution guard")
    require(type(audit["package_path"]) is str and Path(audit["package_path"]).is_absolute() and
            Path(audit["package_path"]).name == "biocompiler" and not Path(audit["package_path"]).is_relative_to(ROOT),
            "Missing installed package origin")
    require(type(audit["modules"]) is dict and "biocompiler.cli" in audit["modules"], "Missing installed product modules")
    for name, item in audit["modules"].items():
        require(type(item) is dict and set(item) == {"path", "sha256"} and
                item["path"] == "src/" + name.replace(".", "/") + ("/__init__.py" if name == "biocompiler" or
                item["path"].endswith("/__init__.py") else ".py") and sources.get(item["path"]) == item["sha256"],
                "Child imported changed or unpinned product source")
    frames = audit["functions"]
    require(type(frames) is list and all(type(entry) is list and len(entry) == 4 and all(type(x) is str for x in entry)
            for entry in frames), "Invalid executed-function tuple")
    require(frames == sorted(frames) and len({tuple(entry) for entry in frames}) == len(frames) and
            all(entry[0] in audit["modules"] and allowed_cli_call(*entry) for entry in frames),
            "Forbidden, unbound or repeated Python authority frame")
    require(["biocompiler.cli","main","output",""] in frames, "Actual CLI entry point missing")
    if oracle.trace(row["id"]) is not None:
        for module,name in (("biocompiler.cli","_selection_command"), ("biocompiler.synthetic_producer_cli","selection_command"),
                            ("biocompiler.core_client","_exchange"),
                            ("biocompiler.core_synthetic_producer_public","SyntheticProducerPublicClient.select_document")):
            require([module,name,"output",""] in frames, "Actual selected CLI and transport execution missing")
    if executable is None:
        executable = row["argv"][row["argv"].index("--core-executable")+1]
    return validate_exchanges(row,audit,blobs,oracle,executable,identities=identities)


def verify_witness(client, oracle, store):
    from biocompiler.core_client import CoreRejected
    with producer.transport_only() as (seen, exchanges):
        client.capabilities()
        try: client.call(OPERATION,oracle.verify_payload)
        except CoreRejected: pass
        else: raise AssertionError("Verifier dispatched public production")
    require(seen == {"biocompiler.core_client"} and len(exchanges) == 2, "Missing raw verifier capability/rejection witness")
    source = Path(sys.modules["biocompiler.core_client"].__file__).resolve()
    row = {"guard_modules":sorted(seen),"exchanges":[],"receipts":{},"native_artifacts":{},
           "module":{"path":"src/biocompiler/core_client.py","sha256":f.sha(source.read_bytes()),"origin":str(source)}}
    for exchange in exchanges:
        item = {key:exchange[key] for key in ("exit_code","executable")}
        for field in ("request","response"):
            raw = exchange[field]; descriptor = r.descriptor(raw)
            item[field] = descriptor
            row["native_artifacts"][descriptor["sha256"]] = store.retain(raw)
        row["exchanges"].append(item)
    return row


def validate(receipt, blobs, original, old_blobs, *, oracle=None):
    oracle = Oracle() if oracle is None else oracle
    required = {"schema_version","scope","status","baseline_pin","runtime_counterpart_sha256","revision","source_revision",
        "run_id","python_version","system","machine","native_platform","native_inputs","product_sources","campaign_sources",
        "executables","checks","completed_checks","verify_witness"}
    require(type(receipt) is dict and required <= set(receipt) <= required | {"duration_seconds","artifacts","artifact_directory"},
            "Unexpected selection CLI receipt fields")
    require(receipt["schema_version"] == SCHEMA and receipt["scope"] == SCOPE and receipt["status"] == "success" and
            receipt["baseline_pin"] == BASELINE_PIN and receipt["runtime_counterpart_sha256"] == COUNTERPART_PIN,
            "Incomplete or different native selection CLI evidence")
    require(receipt["product_sources"] == product_sources() and receipt["campaign_sources"] == r.source_pins(SOURCES),
            "Native CLI evidence comes from a different tested source")
    require(type(receipt["executables"]) is dict and set(receipt["executables"]) == set(ROLES) and
            all(type(path) is str and Path(path).is_absolute() and Path(path).name == "biocompiler-"+role
                for role,path in receipt["executables"].items()), "Invalid explicitly selected native executable identity")
    require(type(receipt["checks"]) is list and type(receipt["completed_checks"]) is int and
            receipt["completed_checks"] == len(receipt["checks"]) == 72, "Complete 72-child Core CLI matrix narrowed")
    expected = {case["id"]:case for case in original["cases"]}
    identities, seen, projection = set(), set(), []
    variants = counterparts()
    for row in receipt["checks"]:
        require(type(row) is dict and set(row) == {"id","role","scope","argv","entrypoint","fault","lineage","files_before",
            "files_after","exit_code","stdout","stderr","audit","native_artifacts","console_path","python_executable"},
            "Unexpected complete CLI occurrence fields")
        require(row["id"] in expected and row["id"] not in seen, "Missing, duplicate or unexpected original CLI occurrence")
        old = expected[row["id"]]; seen.add(row["id"])
        require(row["role"] == "core" and type(row["console_path"]) is str and Path(row["console_path"]).is_absolute() and
                Path(row["console_path"]).name == "biocompiler" and not Path(row["console_path"]).is_relative_to(ROOT) and
                type(row["python_executable"]) is str and Path(row["python_executable"]).is_absolute(), "Invalid CLI runtime or role")
        require(row["entrypoint"] == old["entrypoint"] and row["fault"] == old["fault"] and row["lineage"] == old["lineage"],
                "Original CLI invocation or fault changed")
        flags = ["--core-executable",receipt["executables"]["core"],"--core-sha256",
                 receipt["native_inputs"]["sha256"]["biocompiler-core"],"--core-timeout","300"]
        require(row["argv"] == [old["argv"][0],*flags,*old["argv"][1:]], "Explicit CLI native selection changed")
        equal_observations(row,old,blobs,old_blobs,python_version=receipt["python_version"])
        audit_raw = f.restore(row["audit"],blobs); audit = r.decode(audit_raw)
        require(audit_raw == canonical(audit), "Noncanonical complete CLI audit")
        exchanges = validate_audit(row,audit,blobs,receipt["product_sources"],oracle,
                                   executable=receipt["executables"]["core"],identities=identities)
        projection.append({"id":row["id"],"exchanges":exchanges,
            "receipts": sorted({value["sha256"] for item in audit["receipts"].values() for value in item.values() if value is not None}),
            "exit_code":row["exit_code"],"stdout":old["stdout"] if row["id"] in variants.cases else row["stdout"],
            "stderr":old["stderr"] if row["id"] in variants.cases else row["stderr"],
            "files_before":row["files_before"],"files_after":row["files_after"]})
    require(seen == set(expected), "Complete original CLI occurrences missing")
    witness = receipt["verify_witness"]
    require(type(witness) is dict and set(witness) == {"guard_modules","exchanges","receipts","native_artifacts","module"} and
            witness["guard_modules"] == ["biocompiler.core_client"], "Missing independent raw verifier role witness")
    module = witness["module"]
    require(type(module) is dict and set(module) == {"path","sha256","origin"} and
            module["path"] == "src/biocompiler/core_client.py" and
            module["sha256"] == receipt["product_sources"][module["path"]] and
            type(module["origin"]) is str and Path(module["origin"]).is_absolute() and
            Path(module["origin"]).name == "core_client.py" and not Path(module["origin"]).is_relative_to(ROOT),
            "Verifier witness used changed or checkout transport source")
    verify = validate_exchanges(witness,witness,blobs,oracle,receipt["executables"]["verify"],role="verify",identities=identities)
    used = set()
    def visit(value):
        if type(value) is dict:
            if value.get("kind") in ("blob","repeat"):
                f.restore(value,blobs)
                if value["kind"] == "blob": used.add(value["sha256"])
            else:
                for item in value.values(): visit(item)
        elif type(value) is list:
            for item in value: visit(item)
    visit(receipt["checks"]); visit(witness)
    require(used == set(blobs), "Unreferenced or missing complete CLI evidence")
    return {"children":sorted(projection,key=lambda row:row["id"]),"verify_witness":verify}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core","verify","native-root","output"): parser.add_argument("--"+name,required=True,type=Path)
    for name in ("core-sha256","verify-sha256"): parser.add_argument("--"+name,required=True)
    parser.add_argument("--platform",required=True,choices=PLATFORMS)
    args = parser.parse_args(argv)
    require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed CLI campaign outside checkout")
    native = r.verify_binaries(args.native_root,os.environ.get("GITHUB_SHA"),args.platform)
    require((platform.system(),platform.machine()) == PLATFORMS[args.platform], "Native platform mismatch")
    original, old_blobs = baseline(); oracle = Oracle(); store = f.Store()
    receipt = {"schema_version":SCHEMA,"scope":SCOPE,"status":"running","baseline_pin":BASELINE_PIN,
        "runtime_counterpart_sha256":COUNTERPART_PIN,"revision":os.environ.get("GITHUB_SHA"),
        "source_revision":os.environ.get("GITHUB_HEAD_SHA",os.environ.get("GITHUB_SHA")),"run_id":os.environ.get("GITHUB_RUN_ID"),
        "python_version":platform.python_version(),"system":platform.system(),"machine":platform.machine(),"native_platform":args.platform,
        "native_inputs":native,"product_sources":product_sources(),"campaign_sources":r.source_pins(SOURCES),
        "executables":{"core":str(args.core),"verify":str(args.verify)},"checks":[],"completed_checks":0}
    require(receipt["run_id"] and receipt["source_revision"], "Current hosted run metadata missing")
    started, code = time.monotonic(), 1
    try:
        for role, executable, pin in (("core",args.core,args.core_sha256),("verify",args.verify,args.verify_sha256)):
            require(executable.is_absolute() and executable.resolve() == (args.native_root / ("biocompiler-"+role)).resolve()
                and not executable.is_symlink() and os.access(executable,os.X_OK) and pin == native["sha256"]["biocompiler-"+role],
                "Unbound native executable")
        from biocompiler.core_client import CoreClient
        import biocompiler
        require(not Path(biocompiler.__file__).resolve().is_relative_to(ROOT), "Verifier witness uses checkout package")
        with selection_paths(), f.owned_directories():
            for name in ("startup","cwd","native-artifacts"): (f.CLI_ROOT / name).mkdir()
            (f.CLI_ROOT / "startup/sitecustomize.py").write_text(STARTUP)
            for case in oracle.cases.values():
                row = run_case(case,"core",args.core,args.core_sha256,store)
                receipt["checks"].append(row)
                old = next(value for value in original["cases"] if value["id"] == case["id"])
                equal_observations(row,old,store.blobs,old_blobs,python_version=receipt["python_version"])
            receipt["verify_witness"] = verify_witness(CoreClient(args.verify,role="verify",timeout_seconds=300,
                expected_sha256=args.verify_sha256),oracle,store)
        receipt.update(status="success",completed_checks=len(receipt["checks"]))
        validate(receipt,store.blobs,original,old_blobs,oracle=oracle); code = 0
    except Exception as error:
        receipt.update(status="failure",error=type(error).__name__+": "+str(error)); print(receipt["error"],file=sys.stderr)
    receipt.update(completed_checks=len(receipt["checks"]),duration_seconds=round(time.monotonic()-started,6))
    directory = args.output.with_name(ARTIFACT_DIRECTORY); directory.mkdir(parents=True,exist_ok=True)
    receipt["artifacts"] = {}
    for identity,raw in store.blobs.items():
        path = directory / (identity+".bin")
        require(not path.is_symlink() and (not path.exists() or path.read_bytes() == raw), "Conflicting CLI evidence")
        path.write_bytes(raw); receipt["artifacts"][identity] = {"path":path.name,"bytes":len(raw),"sha256":identity}
    receipt["artifact_directory"] = directory.name
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_bytes(canonical(receipt)+b"\n")
    print("Installed native selection CLI:",receipt["status"],receipt["completed_checks"],"actual children")
    return code

def compare(root, native_root, *, revision, source_revision, run_id):
    require(re.fullmatch(r"[0-9a-f]{40}", revision or "") and re.fullmatch(r"[0-9a-f]{40}", source_revision or "")
            and type(run_id) is str and run_id, "Missing current hosted revision identity")
    root, native_root = Path(root), Path(native_root)
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink() and
            {path.name for path in root.iterdir() if path.name.startswith("realization-")} == names, "Incomplete four-way CLI matrix")
    original, old_blobs = baseline(); oracle = Oracle(); reference, receipts = None, {}
    for target, (system, machine) in PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python; folder = root / name
            require(folder.is_dir() and not folder.is_symlink(), "Unsafe CLI matrix slot")
            inputs, _ = r.read(folder / "native-inputs.json", r.CONTROL_BYTES)
            value, pin = r.read(folder / RECEIPT_FILE)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision,
                    "CLI native inputs differ from same-run binary bytes")
            require(value["revision"] == revision and value["source_revision"] == source_revision and value["run_id"] == run_id and
                    value["system"] == system and value["machine"] == machine and value["native_platform"] == target and
                    value["python_version"] == inputs["python_version"] and value["python_version"].startswith(python + ".") and
                    value["native_inputs"] == native and value["artifact_directory"] == ARTIFACT_DIRECTORY,
                    "Stale or mixed native CLI receipt")
            blobs = read_artifacts(folder / ARTIFACT_DIRECTORY, value["artifacts"])
            projection = canonical(validate(value, blobs, original, old_blobs, oracle=oracle))
            if reference is None: reference = projection
            else: require(projection == reference, "Full CLI/native artifact observations differ across runtimes")
            receipts[name] = pin
    return {"schema_version": "biocompiler.synthetic_selection_cli_reproducibility.v1", "status": "success",
        "revision": revision, "source_revision": source_revision, "run_id": run_id,
        "baseline_pin": BASELINE_PIN, "receipts": receipts, "children_per_runtime": 72,
        "runtime_counterpart_sha256": counterparts().pin,
        "projection": "validated_actual_request_ids_runtime_paths_and_exact_pinned_argparse_runtime_counterpart_only; complete_actual_bytes_retained",
        "observation_sha256": f.sha(reference)}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments: return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare complete installed native CLI evidence")
    parser.add_argument("--compare", action="store_true", required=True)
    for name in ("root", "native-root", "output"): parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(arguments)
    value = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(canonical(value) + b"\n")
    print("Complete native CLI evidence matches across four runtimes")
    return 0


if __name__ == "__main__": raise SystemExit(main())
