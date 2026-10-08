"""Execute every original rich producer-view helper with installed native authority.

Each original occurrence remains distinct. Complete requests, responses, public
observations, source evidence and execution guards are retained as exact bytes.
Only independently checked UUIDs and runtime guard frames are projected across
four hosted runtimes. This grants no pipeline, package or empirical acceptance.
"""
from __future__ import annotations

import argparse
import builtins
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time
from types import SimpleNamespace
from uuid import UUID

if __package__:
    from . import check_native_synthetic_producer as base
    from . import check_native_workflow_public_sdk as serializers
    from . import check_workflow_reproducibility as r
    from .synthetic_inspection_corpus import Corpus
else:
    import check_native_synthetic_producer as base
    import check_native_workflow_public_sdk as serializers
    import check_workflow_reproducibility as r
    from synthetic_inspection_corpus import Corpus

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.native_synthetic_inspection_conformance.v1"
SCOPE = "complete_original_public_helper_observations_no_pipeline_package_or_empirical_acceptance"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "synthetic-inspection.json", "synthetic-inspection-artifacts"
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
canonical, digest, require, decode = r.canonical, r.digest, r.require, r.decode
read, Artifacts, source_pins, verify_binaries = r.read, r.Artifacts, r.source_pins, r.verify_binaries
artifact, envelope, UNSUPPORTED = base.artifact, base.envelope, base.UNSUPPORTED
sha = lambda raw: hashlib.sha256(raw).hexdigest()
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_synthetic_producer",
    "biocompiler.core_synthetic_inspection", "biocompiler.synthetic_producer_backend"}
INPUT_MODULES = {"biocompiler.ir.mechanism", "biocompiler.ir.components", "biocompiler.ir.component_contracts",
    "biocompiler.ir.composition", "biocompiler.verification.evidence", "biocompiler.synthesis.selection",
    "biocompiler.ir.serialization"}
SOURCE_MODULES = TRANSPORT_MODULES | INPUT_MODULES | {"biocompiler.errors"}
SOURCES = ("tools/check_native_synthetic_inspection.py", "tests/test_native_synthetic_inspection_campaign.py",
    "tools/synthetic_inspection_corpus.py", "tests/test_synthetic_inspection_corpus.py", "tools/check_native_synthetic_producer.py",
    "tools/check_native_workflow_public_sdk.py", "tools/check_workflow_reproducibility.py",
    "tools/check_realization_binaries.py", "protocol/synthetic-inspection-v1.json",
    "tests/conformance/synthetic-inspection-supplemental-v1.json", "core/test/test_synthetic_inspection_protocol.ml")
DECLARATION_SHA256 = "64256b32c001d6b836a0c94c6cf4afcafb6a96a7062d463bcb06dd4f5c6cb603"
PUBLIC_METHODS = {
    "MechanismProgram.topological_nodes": "NativeMechanismProgram.topological_nodes",
    "ComponentRegistry.lock": "NativeComponentRegistry.lock",
    "ComponentRegistry.resolve": "NativeComponentRegistry.resolve",
    "ComponentRegistry.select": "NativeComponentRegistry.select",
    "ComponentRegistry.verify_selection": "NativeComponentRegistry.verify_selection",
    "SelectionResult.outcome": "NativeComponentSelectionResult.outcome",
    "CheckResult.exercised_requirement_ids": "NativeCheckResult.exercised_requirement_ids",
    "CheckResult.freshness": "NativeCheckResult.freshness",
    "CheckResult.is_fresh": "NativeCheckResult.is_fresh",
    "DependencySnapshot.changed": "NativeDependencies.changed",
}


def declaration():
    value, pin = read(ROOT / "protocol/synthetic-inspection-v1.json")
    require(pin == DECLARATION_SHA256 and value["profile"] == "biocompiler.core.synthetic_inspection.v1" and
            len(value["operations"]) == 8, "Independent inspection declaration differs")
    return value


def expected_semantic(case):
    """Bind independently captured whole values to their complete supplied inputs."""
    profile, payload = declaration(), case["payload"]
    controls = profile["default_limits"] if payload["limits"] is None else payload["limits"]
    require(set(controls) == set(profile["default_limits"]) and all(
        type(controls[key]) is int and 0 < controls[key] <= maximum
        for key, maximum in profile["default_limits"].items()), "Invalid expected resource reductions")
    def resources(value):
        if type(value) is dict:
            return {key: controls[key] if key in controls else resources(item) for key, item in value.items()}
        if type(value) is list:
            return [resources(item) for item in value]
        return value
    return {"schema_version": profile["result_schema"], "profile": profile["profile"],
        "service_implementation": profile["implementation"], "operation": case["operation"],
        "resources": resources(profile["resources"]), "validation_scope": profile["validation_scope"],
        "claim_scope": profile["claim_scope"], "supplied_authority_fingerprint": digest(payload),
        "input_fingerprints": {key: digest(value) for key, value in payload.items() if key not in ("profile", "limits")},
        "value": case["expected_value"], "value_fingerprint": digest(case["expected_value"])}


def input_phase():
    module = sys.modules.get("biocompiler.synthetic_producer_backend")
    return bool(module is not None and module._INPUT_SERIALIZATION.get())


def allowed_call(module, name, phase, owner):
    if module in TRANSPORT_MODULES:
        return True
    if module == "biocompiler.errors":
        return phase == "output" and name in {"UnsupportedBehaviorError.__init__", "LoweringError.__init__"}
    return phase == "input" and module in INPUT_MODULES and serializers.allowed_call(module, name, "input", owner)


@contextmanager
def guarded_execution():
    previous, original_import = sys.getprofile(), builtins.__import__
    seen, exchanges = set(), []
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in SOURCE_MODULES, "Unreviewed inspection product import: " + name)
        return original_import(name, *args, **kwargs)
    def calls(frame, event, result):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and module.startswith("biocompiler"):
            entry = (module, frame.f_code.co_qualname, "input" if input_phase() else "output",
                     "" if module in TRANSPORT_MODULES else serializers.frame_owner(frame))
            require(allowed_call(*entry), "Python inspection semantic fallback is forbidden: " + repr(entry))
            seen.add(entry)
        if event == "return" and module == "biocompiler.core_client" and frame.f_code.co_name == "_exchange" and result is not None:
            raw, code = result
            exchanges.append({"request": frame.f_locals["request"], "response": raw, "exit_code": code,
                              "executable": str(frame.f_locals["executable"])})
    builtins.__import__ = imports
    sys.setprofile(calls)
    try:
        yield seen, exchanges
        require(sys.getprofile() is calls and builtins.__import__ is imports, "Inspection execution guard was disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = original_import


def uuid4_identity(value, used):
    try:
        identity = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise AssertionError("Invalid inspection request identity") from error
    require(identity.version == 4 and str(identity) == value and value not in used,
            "Reused or noncanonical v4 inspection request identity")
    used.add(value)


def expected_cases(corpus):
    cases = {("core", case["id"]): case for case in corpus.cases}
    require(len(cases) == len(corpus.cases), "Duplicate original inspection occurrence")
    operations = sorted({case["operation"] for case in corpus.cases})
    require(operations == sorted(declaration()["operations"]), "Complete eight-operation inspection inventory differs")
    for operation in operations:
        case = deepcopy(next(case for case in corpus.cases if case["operation"] == operation))
        case["id"] = "verify-role-rejection/" + operation
        cases["verify", case["id"]] = case
    return cases


def metadata(corpus):
    return {"corpus_pins": corpus.pins, "corpus_census": corpus.census,
            "original_occurrences": corpus.original_count,
            "profile_pin": digest(declaration())}


def check_guard(entries, case, role):
    require(type(entries) is list and all(type(item) is list and len(item) == 4 and
        all(type(value) is str for value in item) for item in entries), "Malformed inspection guard frames")
    require(entries == sorted(entries) and len({tuple(item) for item in entries}) == len(entries),
            "Incomplete inspection guard census")
    for item in entries:
        require(item[2] == "output" and allowed_call(*item), "Forbidden inspection semantic guard frame")
    modules = {item[0] for item in entries}
    if role == "verify":
        require(modules == {"biocompiler.core_client"}, "Verifier inspection guard differs")
    else:
        backend = "biocompiler.synthetic_producer_backend"
        require({backend, "biocompiler.core_client", "biocompiler.core_synthetic_inspection"} <= modules and
            [backend, PUBLIC_METHODS[case["api"]], "output", ""] in entries and
            [backend, "NativeProducerDocument.from_dict", "output", ""] in entries and
            [backend, "NativeProducerDocument._inspect", "output", ""] in entries,
            "Missing actual native view import, public helper or native transport")


def invoke_public(case, core):
    """Import complete historical views and invoke their actual public helpers."""
    import biocompiler.synthetic_producer_backend as views
    payload, api = case["payload"], case["api"]
    require(payload["limits"] is None, "Public view helper does not accept resource overrides")
    if api == "MechanismProgram.topological_nodes":
        return views.NativeMechanismProgram.from_dict(payload["mechanism"], core=core).topological_nodes()
    if api.startswith("ComponentRegistry."):
        registry = views.NativeComponentRegistry.from_dict(payload["registry"], core=core)
        if api.endswith(".lock"):
            return registry.lock(payload["instances"])
        if api.endswith(".resolve"):
            return registry.resolve(payload["lock"])
        if api.endswith(".select"):
            return registry.select(payload["request"])
        return registry.verify_selection(payload["request"], payload["selection"])
    if api == "SelectionResult.outcome":
        return views.NativeComponentSelectionResult.from_dict(payload["selection"], core=core).outcome
    if api == "DependencySnapshot.changed":
        return views.NativeDependencies.from_dict(payload["previous"], core=core).changed(payload["current"])
    require(api.startswith("CheckResult."), "Unreviewed public helper API")
    check = views.NativeCheckResult.from_dict(payload["record"], core=core)
    if api == "CheckResult.exercised_requirement_ids":
        return check.exercised_requirement_ids
    if api == "CheckResult.freshness":
        return check.freshness(payload["current"])
    require(api == "CheckResult.is_fresh", "Unreviewed check helper API")
    return check.is_fresh(payload["current"])


def public_plain(value):
    from biocompiler.synthetic_producer_backend import NativeProducerDocument
    if isinstance(value, NativeProducerDocument):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [public_plain(item) for item in value]
    if type(value) is dict:
        return {key: public_plain(item) for key, item in value.items()}
    require(value is None or type(value) in (bool, str, int, float), "Unreviewed helper public value")
    return value


def public_error(error, case):
    from biocompiler.core_client import CoreRejected
    core = getattr(error, "core_error", None)
    require(isinstance(core, CoreRejected) and error.__cause__ is core and
        getattr(error, "operation", None) == case["operation"] and
        canonical([{"code": d.code, "message": d.message, "path": d.path} for d in error.diagnostics]) ==
        canonical([case["error"]]), "Public helper lost original native error authority")
    return {"module": type(error).__module__, "type": type(error).__name__, "message": str(error)}


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.errors import SerializationError
    clients = {client.role: client for client in clients}
    for (role, _), case in expected_cases(corpus).items():
        with guarded_execution() as (seen, exchanges):
            public = None
            if role == "core":
                try:
                    value = invoke_public(case, clients[role])
                    public = {"value": public_plain(value), "properties": {
                        key: public_plain(getattr(value, key)) for key in case["expected_public"].get("properties", {})}}
                except (SerializationError, TypeError) as error:
                    require(case["error"] is not None, "Unexpected public helper rejection")
                    public = {"error": public_error(error, case)}
                require(canonical(public) == canonical(case["expected_public"]),
                        "Complete original helper value, properties or exception differs: " + case["id"])
            else:
                try:
                    clients[role].call(case["operation"], case["payload"])
                except CoreRejected:
                    pass
                else:
                    raise AssertionError("Verifier dispatched a synthetic inspection")
        entries = [list(item) for item in sorted(seen)]
        check_guard(entries, case, role)
        row = {"id": case["id"], "api": case["api"], "operation": case["operation"], "role": role,
            "authority": artifact(receipt, canonical(case["payload"])),
            "expected": artifact(receipt, canonical({"value": case["expected_value"], "error": case["error"],
                                                    "public": case["expected_public"]})),
            "evidence": artifact(receipt, canonical(case["evidence"])),
            "public": None if public is None else artifact(receipt, canonical(public)),
            "guard": artifact(receipt, canonical(entries)), "exchanges": []}
        for exchange in exchanges:
            row["exchanges"].append({**exchange, "request": artifact(receipt, exchange["request"]),
                                     "response": artifact(receipt, exchange["response"])})
        receipt["checks"].append(row)
    with guarded_execution() as (seen, exchanges):
        clients["verify"].capabilities()
    require(len(exchanges) == 1 and {entry[0] for entry in seen} == {"biocompiler.core_client"},
            "Verifier inspection capability witness missing")
    receipt["verify_capability_guard"] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
    receipt["verify_capabilities"] = {**exchanges[0], "request": artifact(receipt, exchanges[0]["request"]),
                                      "response": artifact(receipt, exchanges[0]["response"])}


def validate_checks(receipt, corpus, artifacts):
    expected = expected_cases(corpus)
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected) and
        type(receipt.get("checks")) is list and len(receipt["checks"]) == len(expected), "Incomplete helper occurrences")
    identities, seen, projected = set(), set(), []
    capabilities = SimpleNamespace(profiles={"synthetic_inspection": declaration()})
    for row in receipt["checks"]:
        require(type(row) is dict and set(row) == {"id", "api", "operation", "role", "authority", "expected",
            "evidence", "public", "guard", "exchanges"}, "Unexpected helper observation fields")
        key = row["role"], row["id"]
        require(key in expected and key not in seen, "Missing, duplicated or substituted helper occurrence")
        seen.add(key)
        case, role = expected[key], row["role"]
        require(row["api"] == case["api"] and row["operation"] == case["operation"] and
            artifacts.raw(row["authority"]) == canonical(case["payload"]) and
            artifacts.raw(row["expected"]) == canonical({"value": case["expected_value"], "error": case["error"],
                                                        "public": case["expected_public"]}) and
            artifacts.raw(row["evidence"]) == canonical(case["evidence"]), "Original complete helper evidence differs")
        require(row["public"] is None if role == "verify" else
            artifacts.raw(row["public"]) == canonical(case["expected_public"]), "Complete helper public presentation differs")
        check_guard(artifacts.json(row["guard"]), case, role)
        exchanges = row["exchanges"]
        require(type(exchanges) is list and len(exchanges) == (2 if role == "core" else 1), "Incomplete helper process trace")
        normalized = []
        for ordinal, exchange in enumerate(exchanges):
            require(type(exchange) is dict and set(exchange) == {"request", "response", "exit_code", "executable"} and
                type(exchange["exit_code"]) is int, "Incomplete helper wire evidence")
            path = Path(exchange["executable"])
            require(path.is_absolute() and path.name == "biocompiler-" + role and str(path) == receipt["executables"][role],
                    "Wrong selected helper executable")
            raw_request, raw_response = artifacts.raw(exchange["request"]), artifacts.raw(exchange["response"])
            request, response = decode(raw_request), decode(raw_response)
            if role == "core" and ordinal == 0:
                identity, response_projection = base.validate_capability(raw_response, role, capabilities, identities)
                require(canonical(request) == canonical({"protocol": "biocompiler.core.v1", "request_id": identity,
                    "operation": "capabilities", "payload": {}}) and exchange["exit_code"] == 0,
                    "Helper capability request differs")
            else:
                identity = request.get("request_id")
                uuid4_identity(identity, identities)
                require(raw_request == canonical({"protocol": "biocompiler.core.v1", "request_id": identity,
                    "operation": case["operation"], "payload": case["payload"]}), "Complete helper request differs")
                if role == "verify":
                    wanted, code = envelope(role, identity, case["operation"], "unsupported", None, [UNSUPPORTED]), 3
                elif case["error"] is not None:
                    wanted, code = envelope(role, identity, case["operation"], "error", None, [case["error"]]), 2
                else:
                    wanted, code = envelope(role, identity, case["operation"], "ok", expected_semantic(case), []), 0
                require(canonical(response) == canonical(wanted) and exchange["exit_code"] == code,
                        "Complete helper native receipt, value or exception differs")
                response_projection = {**response, "request_id": "<capability-uuid4>"}
            require(raw_request == canonical(request) and raw_response == canonical(response) + b"\n",
                    "Noncanonical complete helper wire bytes")
            normalized.append({"request": {**request, "request_id": "<capability-uuid4>"},
                               "response": response_projection, "exit_code": exchange["exit_code"]})
        complete = {**{key: value for key, value in row.items() if key not in ("guard", "exchanges")},
                    "exchanges": normalized}
        projected.append({"role": role, "id": case["id"], "complete_observation_sha256": digest(complete)})
    require(seen == set(expected), "Original helper occurrence omitted")
    exchange = receipt["verify_capabilities"]
    check_guard(artifacts.json(receipt["verify_capability_guard"]), {}, "verify")
    require(type(exchange) is dict and set(exchange) == {"request", "response", "exit_code", "executable"} and
        type(exchange["exit_code"]) is int and exchange["exit_code"] == 0 and
        exchange["executable"] == receipt["executables"]["verify"], "Missing verifier inspection capability trace")
    raw = artifacts.raw(exchange["response"])
    identity, response = base.validate_capability(raw, "verify", capabilities, identities)
    require(artifacts.raw(exchange["request"]) == canonical({"protocol": "biocompiler.core.v1", "request_id": identity,
        "operation": "capabilities", "payload": {}}) and raw == canonical(decode(raw)) + b"\n",
        "Verifier inspection capability binding differs")
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete inspection evidence")
    return {"checks": projected, "verify_capabilities": response}


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and
            type(run_id) is str and run_id, "Missing current inspection validation authority")
    root, native_root = Path(root), Path(native_root)
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink() and
            {path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
            "Incomplete or unsafe four-runtime inspection matrix")
    corpus, receipts, binaries, reference = Corpus(), {}, {}, None
    transport_sources = source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(SOURCE_MODULES))
    campaign_sources = source_pins(SOURCES)
    for target, (system, machine) in PLATFORMS.items():
        native_directory = native_root / target
        require(native_directory.is_dir() and not native_directory.is_symlink(), "Unsafe inspection native directory")
        native = verify_binaries(native_directory, revision, target)
        binaries[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe inspection runtime slot")
            inputs, inputs_pin = read(directory / "native-inputs.json", r.CONTROL_BYTES)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale or mixed inspection native inputs")
            receipt, receipt_pin = read(directory / RECEIPT_FILE)
            fields = {"schema_version": SCHEMA, "status": "success", "scope": SCOPE,
                "revision": revision, "source_revision": source_revision, "run_id": run_id,
                "python_version": inputs["python_version"], "system": system, "machine": machine,
                "native_platform": target, "artifact_directory": ARTIFACT_DIRECTORY, "native_inputs": native,
                "transport_sources": transport_sources, "campaign_sources": campaign_sources, **metadata(corpus)}
            for key, wanted in fields.items():
                require(canonical(receipt.get(key)) == canonical(wanted), "Stale/mixed inspection receipt: " + key)
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute() and
                    not Path(receipt["package_path"]).is_relative_to(ROOT), "Missing installed inspection package origin")
            executables = receipt.get("executables")
            require(type(executables) is dict and set(executables) == set(ROLES) and all(
                type(executables[role]) is str and Path(executables[role]).is_absolute() and
                Path(executables[role]).name == "biocompiler-" + role for role in ROLES) and
                Path(executables["core"]).parent == Path(executables["verify"]).parent,
                "Missing exact inspection executable selection")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt.get("artifacts"))
            projected = canonical(validate_checks(receipt, corpus, artifacts))
            if reference is None:
                reference = projected
            else:
                require(projected == reference, "Complete inspection observations differ across runtimes")
            receipts[name] = {"native_inputs": inputs_pin, "inspection": receipt_pin,
                              "complete_artifacts": artifacts.verified}
    require(len(receipts) == 4 and reference is not None, "Incomplete inspection matrix")
    return {"schema_version": "biocompiler.synthetic_inspection_reproducibility.v1", "status": "success",
        "revision": revision, "source_revision": source_revision, "run_id": run_id, **metadata(corpus),
        "receipts": receipts, "native_inputs": binaries, "complete_results_sha256": sha(reference),
        "core_occurrences": len(corpus.cases), "verify_role_rejections": 8,
        "completed_checks_per_variant": len(expected_cases(corpus)),
        "projection": "validated_unique_UUID4_ids_and_execution_guard_frames_only; all_actual_bytes_retained"}


def campaign_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ROLES:
        parser.add_argument("--" + role, required=True, type=Path)
        parser.add_argument("--" + role + "-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(SOURCE_MODULES):
        importlib.import_module(name)
    corpus = Corpus()
    directory = args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()),
            "Unsafe or nonempty inspection evidence directory")
    started = time.monotonic()
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE, **metadata(corpus),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python_version": platform.python_version(),
        "system": platform.system(), "machine": platform.machine(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": directory.name, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed inspection campaign outside checkout")
        require(receipt["run_id"] and receipt["source_revision"], "Current hosted inspection identity is missing")
        require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Inspection platform mismatch")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product loaded: " + name)
        native = verify_binaries(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"], receipt["executables"], clients = native, {}, []
        for role in ROLES:
            path, pin = getattr(args, role), getattr(args, role + "_sha256")
            expected = args.native_root / ("biocompiler-" + role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink() and
                    os.access(path, os.X_OK) and pin == native["sha256"][expected.name], "Unbound inspection executable")
            receipt["executables"][role] = str(path)
            clients.append(CoreClient(path, role=role, expected_sha256=pin, timeout_seconds=300))
        receipt["transport_sources"] = {}
        for name in sorted(SOURCE_MODULES):
            path = Path(sys.modules[name].__file__)
            relative = "src/" + name.replace(".", "/") + ".py"
            pin = sha(path.read_bytes())
            require(pin == sha((ROOT / relative).read_bytes()), "Installed inspection source differs from tested revision")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = source_pins(SOURCES)
        campaign(clients, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        require(canonical(verify_binaries(args.native_root, receipt["revision"], args.platform)) == canonical(native),
                "Inspection binaries changed during execution")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed synthetic inspection:", receipt["status"], receipt["completed_checks"], "complete occurrences")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare every rich helper observation across four hosted runtimes")
    parser.add_argument("--compare", required=True, action="store_true")
    for name in ("root", "native-root", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete rich helper evidence matches across all four runtimes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
