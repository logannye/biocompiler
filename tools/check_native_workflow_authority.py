"""Installed source-authority-only campaign and complete four-way byte comparator.

No product module is imported during fixture loading or comparison. The original v1/v2 workflow campaigns remain separate. All nine full original
requests and explicit normalization, source and resource witnesses are retained;
this service supplies no workflow acceptance or reusable validation token.
"""
from __future__ import annotations

import argparse
import builtins
from contextlib import contextmanager
from collections import Counter
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import platform
import re
import sys
import time

if __package__:
    from . import check_native_workflow as c
    from . import check_workflow_reproducibility as r
else:
    import check_native_workflow as c
    import check_workflow_reproducibility as r

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN, CAPTURE_PIN, SUPPLEMENTAL_PIN = c.CORPUS_PIN, c.CAPTURE_PIN, c.SUPPLEMENT_PIN
PROFILE_PIN = "3f2328785095df64e4eee9f4210eebb8282be8b68d3594bd2bdaa1e92a611e2e"
SCHEMA = "biocompiler.native_workflow_authority_conformance.v1"
SCOPE = "fresh_source_authority_only_no_workflow_acceptance_public_cli_and_pipeline_unmigrated"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "workflow-authority.json", "workflow-authority-artifacts"
CHECKS_PER_ROLE = 23
SOURCES = ("tools/check_native_workflow_authority.py", "tests/test_native_workflow_authority.py",
           "tools/check_native_workflow.py", "tools/check_workflow_reproducibility.py")
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
TRANSPORT_MODULES = c.TRANSPORT_MODULES | {"biocompiler.core_workflow_authority"}
OPERATION = "validate-verification-workflow-authority"
TRANSPORT_PROFILE = "biocompiler.core.artifact_transport.authority.v1"
CONTROL_BYTES = r.CONTROL_BYTES
require, canonical, digest, decode = r.require, r.canonical, r.digest, r.decode
read, Artifacts, descriptor, source_pins = r.read, r.Artifacts, r.descriptor, r.source_pins
verify_binaries = r.verify_binaries


def request_identity(role, case):
    return "workflow-authority-" + c.sha((role + "|" + case["id"] + "|" + case["phase"]).encode())[:32]


class Corpus:
    def __init__(self):
        original = c.Corpus()
        self.profile = {key: deepcopy(value) for key, value in original.profile.items() if key != "record_schema"}
        self.profile.update(profile="biocompiler.core.verification_workflow_authority.v1",
            implementation_version="biocompiler.ocaml.verification_workflow_authority.v0.1",
            operations=[OPERATION], validation_scope="fresh_source_authority_only")
        require(digest(self.profile) == PROFILE_PIN, "Independent authority profile changed")
        self._cases = []
        def add(name, authority, *, expected=None, error=None, limits=None, origin="boundary", evidence=None):
            self._cases.append({"id": name, "phase": "validate", "origin": origin, "operation": OPERATION,
                "authority": authority if type(authority) is bytes else canonical(authority), "retained": None,
                "expected": None if expected is None else canonical(expected), "error": error,
                "limits": limits, "source_evidence": evidence})
        for row in original.supplement["cases"]:
            request = row["expected"]["request"]
            add("original/" + row["name"], request, expected=request, origin="original",
                evidence={"supplemental_pin": SUPPLEMENTAL_PIN, "name": row["name"],
                    "complete_original_record": row["expected"], "complete_original_record_fingerprint": row["fingerprint"]})
        base = deepcopy(original.supplement["cases"][0]["expected"]["request"])
        require(original.supplement["cases"][0]["name"] == "candidate_pass", "Original authority ordering changed")
        altered = deepcopy(base); altered["candidate"]["component_locks"].reverse()
        add("normalization/reversed-locks", altered, expected=base, origin="normalization")
        altered = deepcopy(base); altered["until"] = 9.0
        add("identity/float-horizon", altered, expected=altered, origin="scalar_identity")
        altered = deepcopy(base)
        for frame in altered["history"]:
            frame["contacts"] = {"café-α" if key == "x" else key: value for key, value in frame["contacts"].items()}
        add("identity/unicode-contact", altered, expected=altered, origin="unicode_identity")
        def rejection(code, message, path=None): return {"code": code, "message": message, "path": path}
        structural = rejection("verification_workflow", "Invalid fields in SyntheticVerificationRequest.", "authority")
        add("malformed/extra-outcome", {**base, "outcome": "pass"}, error=structural)
        altered = deepcopy(base); del altered["schema_version"]
        add("malformed/missing-schema", altered, error=structural)
        add("malformed/mode", {**base, "mode": "unsupported"}, error=rejection(
            "verification_workflow", "Unsupported verification mode.", "authority"))
        forged = deepcopy(base); forged["realization"]["behavior"]["name"] = "forged"
        source = rejection("lowering_source_identity", "Source semantic fingerprint and program identity match.")
        add("malformed/source", forged, error=source)
        add("malformed/source-before-mode", {**forged, "mode": "unsupported"}, error=source)
        limits = {"max_work": 1_000_000_000_000, "max_monitor_items": 7_000_000,
            "max_request_bytes": 16_777_216, "max_report_bytes": 1_048_576, "max_report_nodes": 100_000}
        add("resources/all-five-reductions", base, expected=base, limits=limits, origin="resource_success")
        defaults = self.profile["resources"]["workflow"]
        errors = {
            "max_work": rejection("workflow_work_limit", "Independent checker work limit exceeded under biocompiler.verification_workflow.resources.v1."),
            "max_monitor_items": rejection("workflow_retention_limit", "Live workflow inventory exceeds its declared bound."),
            "max_request_bytes": rejection("artifact_transport", "Complete raw input artifacts and control exceed the operation byte limit."),
            "max_report_bytes": rejection("verification_exploration_limit", "Verification workflow exceeds its native resource boundary.", ""),
            # Publication measures the complete ten-field request. At one node,
            # Codec.length rejects its second root field without a path before
            # inspect can reach its path-aware object-size checks.
            "max_report_nodes": rejection("verification_exploration_limit", "Verification workflow exceeds its native resource boundary."),
        }
        for key, error in errors.items():
            selected = {field: 1 if field == key else defaults[field] for field in c.LIMIT_FIELDS}
            add("resources/" + key, base, limits=selected, error=error, origin="resource_failure")
        require(len(self._cases) == CHECKS_PER_ROLE and len({row["id"] for row in self._cases}) == CHECKS_PER_ROLE,
                "Complete source authority matrix changed")

    def cases(self): return deepcopy(self._cases)


class Golden:
    def __init__(self):
        corpus = Corpus()
        self.profile, self.cases = corpus.profile, corpus.cases()

    expected = r.Golden.expected


def expected_semantic(profile, role, case, request):
    require(request == case["expected"], "Authority oracle requires complete independent request bytes")
    authority = decode(case["authority"])
    return {"schema_version": "biocompiler.core.verification_workflow_authority_result.v1",
        "profile": profile["profile"], "operation": OPERATION, "executable": role,
        "request_id": request_identity(role, case), "validation_scope": "fresh_source_authority_only",
        "implementation_version": profile["implementation_version"], "workflow_version": profile["workflow_version"],
        "workflow_operation": authority["operation"], "mode": authority["mode"],
        "authority_fingerprint": digest(authority), "request_fingerprint": c.sha(request),
        "resources": r.effective_resources(profile, case["limits"])}


@contextmanager
def transport_only():
    previous, imported = sys.getprofile(), builtins.__import__
    seen = set()
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in TRANSPORT_MODULES, "Python semantic import is forbidden: " + name)
        return imported(name, *args, **kwargs)
    def calls(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler"):
                require(module in TRANSPORT_MODULES, "Python semantic execution is forbidden: " + module + "." + frame.f_code.co_qualname)
                seen.add(module)
    builtins.__import__ = imports; sys.setprofile(calls)
    try:
        yield seen
        require(sys.getprofile() is calls and builtins.__import__ is imports,
                "Strict authority semantic guard was replaced or disabled")
    finally:
        sys.setprofile(previous); builtins.__import__ = imported


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_workflow_authority import AuthorityClient
    cases = corpus.cases()
    for transport in clients:
        client = AuthorityClient(transport)
        for case in cases:
            identity = request_identity(transport.role, case)
            entry = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits")}
            entry.update(role=transport.role, request_id=identity, authority=c.artifact(receipt, case["authority"]),
                retained=None if case["retained"] is None else c.artifact(receipt, case["retained"]),
                expected=None if case["expected"] is None else c.artifact(receipt, case["expected"]),
                source_evidence=None if case["source_evidence"] is None else c.artifact(receipt, canonical(case["source_evidence"])))
            with transport_only() as seen:
                try:
                    actual = client.validate(case["authority"], limits=case["limits"], request_id=identity)
                except CoreRejected as error:
                    response = error.response
                    diagnostics = [{"code": d.code, "message": d.message, "path": d.path} for d in response.diagnostics]
                    require(case["error"] is not None and diagnostics == [case["error"]] and response.status == "error",
                            "Exact authority rejection differs: " + case["id"] + "/" + case["phase"] + " " + str(diagnostics))
                    envelope = {"protocol": "biocompiler.core.v1", "request_id": response.request_id,
                        "operation": response.operation, "status": response.status, "diagnostics": diagnostics, "result": response.result,
                        "core": {"implementation": "ocaml", "version": response.version,
                                 "protocol": "biocompiler.core.v1", "executable": response.executable}}
                    entry.update(status="error", diagnostic=diagnostics[0], request=None, semantic_receipt=None)
                else:
                    require(case["error"] is None and actual.request_json == case["expected"],
                            "Complete original authority output differs: " + case["id"] + "/" + case["phase"])
                    require(canonical(actual.receipt) == canonical(expected_semantic(corpus.profile, transport.role, case, case["expected"])),
                            "Native authority differs from independent original record oracle")
                    envelope = c.full_response(actual)
                    entry.update(status="ok", diagnostic=None, request=c.artifact(receipt, actual.request_json),
                        semantic_receipt=c.artifact(receipt, canonical(actual.receipt)))
                entry["envelope"] = c.artifact(receipt, canonical(envelope))
            require(seen == TRANSPORT_MODULES, "Required strict authority transport path was not exercised")
            entry["guard_modules"] = sorted(seen)
            receipt["checks"].append(entry)
    require(Counter(item["role"] for item in receipt["checks"]) == {"core": CHECKS_PER_ROLE, "verify": CHECKS_PER_ROLE},
            "Complete two-role authority campaign was narrowed")


def validate_checks(receipt, golden, artifacts):
    expected = golden.expected()
    checks = receipt.get("checks")
    require(type(checks) is list and len(checks) == len(expected) and
            type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected),
            "Incomplete exact workflow occurrence matrix")
    seen = {}
    fields = {"role", "id", "phase", "origin", "operation", "limits", "request_id", "authority", "retained",
              "expected", "source_evidence", "status", "diagnostic", "request", "semantic_receipt", "envelope", "guard_modules"}
    for check in checks:
        require(type(check) is dict and set(check) == fields, "Incomplete workflow occurrence receipt")
        key = check["role"], check["id"], check["phase"], check["operation"]
        require(key in expected and key not in seen, "Unknown, duplicate or stale workflow occurrence")
        role = key[0]
        case = expected[key]
        require(check["origin"] == case["origin"] and canonical(check["limits"]) == canonical(case["limits"]) and
                check["request_id"] == request_identity(role, case), "Workflow occurrence authority or request identity changed")
        require(check["guard_modules"] == sorted(TRANSPORT_MODULES), "Missing or weakened executed no-fallback guard")
        for name in ("authority", "retained", "expected", "source_evidence"):
            reference = case[name]
            if name == "source_evidence" and reference is not None:
                reference = canonical(reference)
            if reference is None:
                require(check[name] is None, "Unexpected supplied workflow evidence: " + name)
            else:
                require(artifacts.raw(check[name]) == reference, "Complete original occurrence evidence differs: " + name)
        envelope = artifacts.json(check["envelope"])
        expected_envelope = {
            "protocol": "biocompiler.core.v1", "request_id": request_identity(role, case),
            "operation": case["operation"],
            "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": role},
        }
        if case["error"] is not None:
            require(check["status"] == "error" and canonical(check["diagnostic"]) == canonical(case["error"]) and
                    check["request"] is None and check["semantic_receipt"] is None,
                    "Exact original workflow rejection changed or retained acceptance")
            expected_envelope.update(status="error", result=None, diagnostics=[case["error"]])
        else:
            require(check["status"] == "ok" and check["diagnostic"] is None,
                    "Successful original workflow result was rejected")
            record = artifacts.raw(check["request"])
            require(record == case["expected"] and canonical(decode(record)) == record,
                    "Complete workflow result differs from original oracle")
            semantic = artifacts.json(check["semantic_receipt"])
            expected_receipt = expected_semantic(golden.profile, role, case, record)
            require(canonical(semantic) == canonical(expected_receipt),
                    "Complete workflow semantic authority, identity, profile or resources differ")
            result = {"schema_version": "biocompiler.core.artifact_response.v1",
                      "transport": TRANSPORT_PROFILE,
                      "authority": descriptor(case["authority"]), "retained_record": descriptor(case["retained"]),
                      "artifact": descriptor(record), "result": expected_receipt}
            expected_envelope.update(status="ok", result=result, diagnostics=[])
        require(canonical(envelope) == canonical(expected_envelope),
                "Complete native protocol envelope, diagnostics or transport bindings differ")
        seen[key] = check
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete workflow artifact")
    return [seen[key] for key in sorted(seen)]



def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and
            type(run_id) is str and bool(run_id), "Invalid current workflow authority")
    root, native_root = Path(root), Path(native_root)
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink(),
            "Unsafe workflow evidence roots")
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require({path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
            "Missing or extra four-way workflow matrix slot")
    golden = Golden()
    transport_sources = source_pins("src/" + module.replace(".", "/") + ".py" for module in sorted(TRANSPORT_MODULES))
    campaign_sources = source_pins(SOURCES)
    receipts, natives = {}, {}
    reference = None
    for target, (system, machine) in PLATFORMS.items():
        native_directory = native_root / target
        require(native_directory.is_dir() and not native_directory.is_symlink(), "Unsafe native platform directory")
        native = verify_binaries(native_directory, revision, target)
        natives[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe workflow matrix directory")
            inputs, inputs_pin = read(directory / "native-inputs.json", CONTROL_BYTES)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale or mixed same-run native-input receipt")
            receipt, receipt_pin = read(directory / RECEIPT_FILE)
            require(receipt.get("schema_version") == SCHEMA and
                    receipt.get("status") == "success" and
                    receipt.get("scope") == SCOPE and
                    receipt.get("revision") == revision and receipt.get("source_revision") == source_revision and
                    receipt.get("run_id") == run_id and receipt.get("python_version") == inputs["python_version"] and
                    receipt.get("system") == system and receipt.get("machine") == machine and
                    receipt.get("native_platform") == target and
                    receipt.get("corpus_pin") == CORPUS_PIN and receipt.get("supplemental_pin") == SUPPLEMENTAL_PIN and
                    receipt.get("profile_pin") == PROFILE_PIN,
                    "Stale, wrong-platform, incomplete or mixed workflow receipt")
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute(),
                    "Missing installed workflow package provenance")
            require(canonical(receipt.get("native_inputs")) == canonical(native),
                    "Workflow selected binaries differ from complete same-revision downloaded bytes")
            require(canonical(receipt.get("transport_sources")) == canonical(transport_sources) and
                    canonical(receipt.get("campaign_sources")) == canonical(campaign_sources),
                    "Installed transport or campaign source differs from tested revision")
            require(receipt.get("artifact_directory") == ARTIFACT_DIRECTORY, "Unsafe workflow sibling artifact path")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt.get("artifacts"))
            checks = validate_checks(receipt, golden, artifacts)
            # Every identity in this cross-platform content census was rehashed
            # from the complete bytes above, and all referenced contents were
            # independently compared with their exact original/profile oracle.
            complete = canonical({"checks": checks, "artifacts": artifacts.verified})
            if reference is None:
                reference = complete
            else:
                require(complete == reference, "Complete four-way workflow bytes or occurrence results differ")
            receipts[name] = {"native_inputs": inputs_pin, "workflow": receipt_pin}
    require(len(receipts) == 4 and reference is not None, "Incomplete four-way workflow matrix")
    return {"schema_version": "biocompiler.workflow_authority_reproducibility.v1", "status": "success",
            "revision": revision, "source_revision": source_revision, "run_id": run_id,
            "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "supplemental_pin": SUPPLEMENTAL_PIN,
            "profile_pin": PROFILE_PIN, "receipts": receipts, "native_inputs": natives,
            "complete_results_sha256": hashlib.sha256(reference).hexdigest(),
            "checks_per_role": len(golden.cases), "completed_checks_per_variant": len(golden.expected())}



def campaign_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--verify-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=("linux-x86_64", "macos-arm64"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if __package__:
        from .check_realization_binaries import verify, PLATFORMS
    else:
        from check_realization_binaries import verify, PLATFORMS
    import biocompiler
    from biocompiler.core_client import CoreClient
    import biocompiler.core_artifacts
    import biocompiler.core_workflow
    import biocompiler.core_workflow_authority
    started = time.monotonic()
    directory = args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink(), "Unsafe workflow artifact directory")
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE,
        "corpus_pin": CORPUS_PIN, "supplemental_pin": SUPPLEMENTAL_PIN, "profile_pin": PROFILE_PIN,
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": directory.name, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run native workflow campaign outside checkout")
        require(receipt["run_id"] is not None and receipt["source_revision"] is not None,
                "Same-run hosted source metadata required")
        require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Host/native platform mismatch")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product module loaded: " + name)
        native = verify(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"] = native
        pins = {"core": args.core_sha256, "verify": args.verify_sha256}
        clients = []
        for role, path in (("core", args.core), ("verify", args.verify)):
            expected = args.native_root / ("biocompiler-" + role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink()
                    and os.access(path, os.X_OK), "Unbound or nonexecutable installed native binary")
            require(pins[role] == native["sha256"][expected.name], "Explicit release pin differs from same-run native manifest")
            clients.append(CoreClient(path, role=role, expected_sha256=pins[role], timeout_seconds=300))
        receipt["transport_sources"] = {}
        for name in sorted(TRANSPORT_MODULES):
            path = Path(sys.modules[name].__file__)
            pin = c.sha(path.read_bytes())
            relative = "src/" + name.replace(".", "/") + ".py"
            require(pin == c.sha((ROOT / relative).read_bytes()), "Installed workflow transport differs from tested source")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = {relative: c.sha((ROOT / relative).read_bytes()) for relative in
            SOURCES}
        corpus = Corpus()
        require(digest(bioc := biocompiler.core_workflow_authority.capability_profile()) == PROFILE_PIN and bioc == corpus.profile,
                "Installed workflow profile differs from independent oracle")
        campaign(clients, corpus, receipt)
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"] = "failure"
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Native workflow authority campaign:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare every complete source authority occurrence across all four runtimes")
    parser.add_argument("--compare", action="store_true", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete source authority requests, rejections and resources match across four required variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
