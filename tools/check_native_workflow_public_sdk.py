"""Actual installed public workflow routes and complete four-way evidence checks.

All52 original workflow observations retain their89 full replay projections.
110 of112 raw cases apply to the public API; the two explicit resource-control
cases remain in the unchanged raw protocol campaign. Every supplemental record
also traverses mapping, typed and actual preceding native-view inputs. No
product module is imported during fixture loading or evidence comparison.
"""
from __future__ import annotations

import argparse
import builtins
from contextlib import contextmanager
from functools import lru_cache
import json
from uuid import UUID
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
    from . import check_native_workflow_presentation as p
    from . import check_workflow_reproducibility as r
else:
    import check_native_workflow as c
    import check_native_workflow_presentation as p
    import check_workflow_reproducibility as r

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN, CAPTURE_PIN, SUPPLEMENTAL_PIN = c.CORPUS_PIN, c.CAPTURE_PIN, c.SUPPLEMENT_PIN
PROFILE_PIN = "a15cfc3423bc7adc739e37ca81f9ecccde284cb22d666a4b3d0bbd768762d01c"
SCHEMA = "biocompiler.native_workflow_public_sdk_conformance.v1"
SCOPE = "actual_public_workflow_sdk_complete_records_cli_pipeline_cutover_separate"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "workflow-public-sdk.json", "workflow-public-sdk-artifacts"
CHECKS_PER_ROLE = 164
SOURCES = ("tools/check_native_workflow_public_sdk.py", "tests/test_native_workflow_public_sdk.py",
           "tools/check_native_workflow_presentation.py",
           "tools/check_native_workflow.py", "tools/check_workflow_reproducibility.py")
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
TRANSPORT_MODULES = c.TRANSPORT_MODULES | {"biocompiler.workflow_backend", "biocompiler.compiler.verification_workflow"}
CONTROL_BYTES = r.CONTROL_BYTES
require, canonical, digest, decode = r.require, r.canonical, r.digest, r.decode
read, Artifacts, descriptor, source_pins = r.read, r.Artifacts, r.descriptor, r.source_pins
verify_binaries = r.verify_binaries


# Only these leaf codecs may run on native output. Their checks validate the
# shape/identity of supplied leaves; they do not evaluate behavior or replay.
LEAF_FUNCTIONS = {
    "biocompiler.ir.intent": {"SourceLocation.to_dict", "SourceLocation.from_dict", "SourceLocation.__post_init__",
        "freeze_json", "thaw_json", "_keys", "_name"},
    "biocompiler.ir.serialization": {"fields", "require", "name", "fingerprint", "JsonArtifact.fingerprint"},
    "biocompiler.semantics.types": {"TypeSpec.__post_init__", "TypeSpec.from_dict", "TypeSpec.to_dict", "TypeSpec.compatible",
        "ScalarLiteral.to_dict", "Interval.__class_getitem__", "Interval.__init__", "Interval.to_dict",
        "_ScalarType.__new__", "_number", "_scalar_binding", "decode_binding", "to_type_spec"},
    "biocompiler.verification.evidence": {"_require", "_name", "_finite_nonnegative", "_canonical", "_fields",
        *(name + "." + method for name in ("CheckResult", "CheckDiagnostic", "Counterexample", "RequirementCoverage")
          for method in ("__post_init__", "from_dict", "to_dict")),
        "DependencySnapshot.__post_init__", "DependencySnapshot.to_dict", "CheckResult.fingerprint"},
    "biocompiler.verification.exploration": {"_Record.from_dict", "_Record.to_dict", "FailureSignature.__post_init__",
        "_utf8", "name"},
}
# These unchanged legacy serializers run only while backend's explicit input
# marker is active, before I/O. Exploration properties here are untrusted input
# claims. The complete native workflow independently checks all authority again.
INPUT_FUNCTIONS = {
    "biocompiler.compiler.request": {"BuildRequest.to_dict", "ElaborationProvenance.to_dict", "RealizationRequest.to_dict"},
    "biocompiler.ir.behavior": {"BehaviorNode.to_dict", "BehaviorProgram.to_dict"},
    "biocompiler.ir.components": {"ComponentLock.to_dict"},
    "biocompiler.ir.intent": {"IntentNode.__post_init__", "IntentNode.to_dict", "IntentProgram.to_dict"},
    "biocompiler.ir.mechanism": {"MechanismNode.to_dict", "MechanismProgram.to_dict"},
    "biocompiler.semantics.context": {"TargetContext.to_dict"},
    "biocompiler.semantics.contracts": {"BehaviorRequirement.to_dict"},
    "biocompiler.semantics.evaluator": {"InputFrame.to_dict", "SignalSample.to_dict"},
    "biocompiler.semantics.realization": {"BehaviorContract.to_dict", "InputDomain.to_dict", "Observable.to_dict",
        "OperatingDomain.to_dict", "ResponseRequirement.to_dict"},
    "biocompiler.synthesis.synthetic": {"SyntheticCandidate.to_dict", "SyntheticGeneratorConfig.to_dict"},
    "biocompiler.verification.exploration": {"_Record.to_dict", "BooleanContactConfig.possible_histories",
        "BooleanContactConfig.state_count", "BooleanInputConfig.state_count", "ExplorationReport.to_dict",
        "_stable_dependencies", *("ExplorationReport." + name for name in ("all_passed", "complete", "coverage_totals",
            "evaluated_histories", "outcome_counts", "possible_histories", "shared_dependencies", "state_count"))},
    "biocompiler.verification.realization": {"InputBinding.to_dict", "ObservationMap.to_dict", "OutputBinding.to_dict"},
}
GENERATED_CLASSES = {
    "biocompiler.ir.intent": {"SourceLocation"},
    "biocompiler.semantics.types": {"TypeSpec", "ScalarLiteral"},
    "biocompiler.verification.evidence": {"CheckResult", "CheckDiagnostic", "Counterexample", "DependencySnapshot", "RequirementCoverage"},
    "biocompiler.verification.exploration": {"FailureSignature"},
}
SOURCE_MODULES = TRANSPORT_MODULES | set(LEAF_FUNCTIONS) | set(INPUT_FUNCTIONS)


def input_phase():
    module = sys.modules.get("biocompiler.workflow_backend")
    return bool(module is not None and module._INPUT_SERIALIZATION.get())


def frame_owner(frame):
    current = frame
    while current is not None and current.f_globals is frame.f_globals:
        owner = current.f_locals.get("self", current.f_locals.get("cls"))
        if owner is not None:
            return owner.__name__ if isinstance(owner, type) else type(owner).__name__
        current = current.f_back
    return ""


@lru_cache(maxsize=8192)
def allowed_call(module, name, phase, owner):
    if module in c.TRANSPORT_MODULES or module == "biocompiler.workflow_backend":
        return True
    if module == "biocompiler.compiler.verification_workflow":
        return name in ("run_synthetic_verification", "replay_synthetic_verification") and phase == "output"
    root = name.split(".<locals>.")[0]
    generated = owner in GENERATED_CLASSES.get(module, set()) or (
        phase == "input" and module == "biocompiler.ir.intent" and owner == "IntentNode")
    if name in ("__create_fn__.<locals>.__init__", "__create_fn__.<locals>.__eq__"):
        return generated
    if generated and name in (owner + ".__init__", owner + ".__eq__"):
        return True
    if phase == "input" and root in INPUT_FUNCTIONS.get(module, set()):
        return True
    if root not in LEAF_FUNCTIONS.get(module, set()):
        return False
    if module == "biocompiler.verification.exploration" and root in ("_Record.from_dict", "_Record.to_dict"):
        return owner == "FailureSignature"
    if module == "biocompiler.ir.serialization" and root == "JsonArtifact.fingerprint":
        return owner == "FailureSignature"
    return True


def allowed_frame(frame):
    module = frame.f_globals.get("__name__", "")
    return not module.startswith("biocompiler") or allowed_call(
        module, frame.f_code.co_qualname, "input" if input_phase() else "output", frame_owner(frame))


@contextmanager
def routed_execution():
    """Executed product-call guard, reusable by actual CLI child campaigns."""
    previous, imported = sys.getprofile(), builtins.__import__
    seen = set()
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in SOURCE_MODULES, "Unreviewed public workflow import: " + name)
        return imported(name, *args, **kwargs)
    def calls(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler"):
                phase = "input" if input_phase() else "output"
                owner = "" if module in TRANSPORT_MODULES else frame_owner(frame)
                entry = (module, frame.f_code.co_qualname, phase, owner)
                require(allowed_call(*entry), "Python semantic fallback is forbidden: " + repr(entry))
                seen.add(entry)
    builtins.__import__ = imports
    sys.setprofile(calls)
    try:
        yield seen
        require(sys.getprofile() is calls and builtins.__import__ is imports,
                "Public workflow guard was replaced or disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = imported


def check_guard(entries, case):
    require(type(entries) is list and entries == sorted(entries) and len({tuple(item) for item in entries}) == len(entries),
            "Invalid executed guard census")
    for entry in entries:
        require(type(entry) is list and len(entry) == 4 and all(type(value) is str for value in entry), "Invalid guard frame")
        module, name, phase, owner = entry
        require(phase in ("input", "output") and allowed_call(module, name, phase, owner), "Unreviewed executed Python frame")
        require(phase != "input" or case["input_kind"] == "typed", "Unexpected legacy input serialization")
    modules = {entry[0] for entry in entries}
    require(TRANSPORT_MODULES <= modules, "Missing actual public SDK and native transport calls")
    route = "run_synthetic_verification" if case["operation"] == "run-verification-workflow" else "replay_synthetic_verification"
    require(any(item[:3] == ["biocompiler.compiler.verification_workflow", route, "output"] for item in entries),
            "Missing actual public SDK call")
    if case["input_kind"] == "typed":
        require(any(item[2] == "input" for item in entries), "Typed request bypassed audited serializer phase")


def project_cases(original):
    require(len(original) == 112, "Original v1 workflow matrix was narrowed")
    excluded = {case["id"] for case in original if case["limits"] is not None}
    require(excluded == {"boundary/work-one", "boundary/output-one-under"},
            "Only two raw protocol resource controls may be outside public SDK")
    result = [{**deepcopy(case), "command": None, "input_kind": "bytes", "seed_id": None}
              for case in original if case["limits"] is None]
    for case in original:
        if case["origin"] != "supplemental":
            continue
        for kind in ("mapping", "typed", "native"):
            result.append({**deepcopy(case), "id": kind + "/" + case["id"],
                "origin": "public_input_form", "command": None, "input_kind": kind,
                "seed_id": case["id"] if kind == "native" else None})
    require(len(result) == CHECKS_PER_ROLE and len({(v["id"], v["phase"]) for v in result}) == CHECKS_PER_ROLE,
            "Complete public SDK occurrence matrix changed")
    require(len({case["id"] for case in result if case["origin"] == "original"}) == 52,
            "Original 52 workflow occurrences were narrowed")
    return result


class Corpus:
    def __init__(self):
        # Golden independently rereads all385 original ledgers and requires the
        # complete exact52 original workflow ID/observation set before projection.
        original = r.Golden()
        self.profile = deepcopy(original.profile)
        self.profile.update(profile="biocompiler.core.verification_workflow.v2",
            implementation_version="biocompiler.ocaml.verification_workflow_service.v0.2",
            presentation_profile="biocompiler.core.verification_workflow.presentation.v1")
        require(digest(self.profile) == PROFILE_PIN, "Independent v2 profile changed")
        self._cases = project_cases(original.cases)

    def cases(self):
        return deepcopy(self._cases)


class Golden:
    def __init__(self):
        corpus = Corpus()
        self.profile, self.cases = corpus.profile, corpus.cases()

    expected = r.Golden.expected


def expected_presentation(case):
    # Derive exclusively from immutable full original bytes, never from native
    # candidate output, receipt claims or a product/workflow constructor.
    record = decode(case["expected"])
    operation, result = record["request"]["operation"], record["result"]
    original_frames = reduced_frames = None
    if operation == "check":
        passed = result["outcome"] == "pass"
    elif operation == "explore":
        passed = result["all_passed"]
        require(type(passed) is bool, "Original exploration status is not Boolean")
    else:
        require(operation == "reduce" and type(result["one_minimal"]) is bool, "Unknown original presentation result")
        passed = result["one_minimal"]
        original_frames, reduced_frames = len(result["original_history"]), len(result["history"])
    return {"profile": "biocompiler.core.verification_workflow.presentation.v1",
        "command_exit_code": 0 if case["operation"] == "replay-verification-workflow" or passed else 1,
        "original_frames": original_frames, "reduced_frames": reduced_frames}


def expected_semantic(profile, role, case, record, request_id):
    require(record == case["expected"], "Presentation oracle requires complete original record bytes")
    value = r.expected_semantic(profile, role, case, record)
    value.update(schema_version="biocompiler.core.verification_workflow_result.v2",
                 request_id=request_id, command=case["command"],
                 presentation=expected_presentation(case))
    return value


def _uuid(value):
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise AssertionError("Invalid generated public request UUID")
    require(parsed.version == 4 and str(parsed) == value, "Public request must retain its generated canonical UUID4")
    return value


def prepare_input(case, native_seeds):
    from biocompiler.compiler.verification_workflow import SyntheticVerificationRequest, SyntheticVerificationRecord
    kind = case["input_kind"]
    authority, retained = case["authority"], case["retained"]
    if kind == "bytes":
        return authority, retained, authority, retained
    if kind == "native":
        require(case["seed_id"] in native_seeds, "Missing actual preceding native public result")
        view = native_seeds[case["seed_id"]]
        request = view.request
        record = view if retained is not None else None
        return request, record, request.canonical_json, None if record is None else record.canonical_json
    request = decode(authority)
    record = None if retained is None else decode(retained)
    if kind == "typed":
        # Authoring occurs before selected execution. Only the exact serializer
        # runs within the marked untrusted-input phase under routed_execution.
        request = SyntheticVerificationRequest.from_dict(request)
        record = None if record is None else SyntheticVerificationRecord.from_dict(record)
        request_wire = json.dumps(request.to_dict(), separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        record_wire = None if record is None else json.dumps(record.to_dict(), separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    else:
        require(kind == "mapping", "Unknown public SDK input kind")
        request_wire, record_wire = canonical(request), None if record is None else canonical(record)
    return request, record, request_wire, record_wire


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.compiler.verification_workflow import run_synthetic_verification, replay_synthetic_verification
    from biocompiler.workflow_backend import WorkflowCoreError, NativeWorkflowRecord
    cases = corpus.cases()
    request_ids = set()
    for transport in clients:
        native_seeds = {}
        for case in cases:
            authority, historical, wire_authority, wire_retained = prepare_input(case, native_seeds)
            entry = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits", "command", "input_kind", "seed_id")}
            entry.update(role=transport.role, authority=c.artifact(receipt, case["authority"]),
                retained=None if case["retained"] is None else c.artifact(receipt, case["retained"]),
                wire_authority=c.artifact(receipt, wire_authority),
                wire_retained=None if wire_retained is None else c.artifact(receipt, wire_retained),
                expected=None if case["expected"] is None else c.artifact(receipt, case["expected"]),
                source_evidence=None if case["source_evidence"] is None else c.artifact(receipt, canonical(case["source_evidence"])))
            with routed_execution() as seen:
                try:
                    if case["operation"] == "run-verification-workflow":
                        view = run_synthetic_verification(authority, core=transport)
                    else:
                        view = replay_synthetic_verification(historical, expected_request=authority, core=transport)
                except WorkflowCoreError as error:
                    require(isinstance(error.core_error, CoreRejected), "Public workflow failure was not native rejection")
                    response = error.core_error.response
                    diagnostics = [{"code": d.code, "message": d.message, "path": d.path} for d in response.diagnostics]
                    require(case["error"] is not None and diagnostics == [case["error"]] and response.status == "error",
                            "Exact public rejection differs: " + case["id"] + "/" + case["phase"] + " " + str(diagnostics))
                    identity = _uuid(response.request_id)
                    envelope = {"protocol": "biocompiler.core.v1", "request_id": identity,
                        "operation": response.operation, "status": response.status, "diagnostics": diagnostics, "result": response.result,
                        "core": {"implementation": "ocaml", "version": response.version,
                                 "protocol": "biocompiler.core.v1", "executable": response.executable}}
                    entry.update(status="error", diagnostic=diagnostics[0], record=None, semantic_receipt=None,
                                 view_json=None, view_type=None, view_fingerprint=None, view_request_fingerprint=None)
                else:
                    require(type(view) is NativeWorkflowRecord, "Public route returned legacy workflow identity")
                    actual = view.native
                    identity = _uuid(actual.request_id)
                    require(case["error"] is None and actual.record_json == case["expected"],
                            "Complete public workflow output differs: " + case["id"] + "/" + case["phase"])
                    require(view.authority_json == wire_authority and view.canonical_json == case["expected"] and
                            canonical(view.to_dict()) == case["expected"], "Native public view changed complete bytes")
                    require(canonical(actual.receipt) == canonical(expected_semantic(corpus.profile, transport.role, case, case["expected"], identity)),
                            "Native public receipt differs from independent original oracle")
                    envelope = c.full_response(actual)
                    entry.update(status="ok", diagnostic=None, record=c.artifact(receipt, actual.record_json),
                        semantic_receipt=c.artifact(receipt, canonical(actual.receipt)),
                        view_json=c.artifact(receipt, view.to_json().encode()), view_type=type(view).__name__,
                        view_fingerprint=view.fingerprint, view_request_fingerprint=view.request.fingerprint)
                    if case["origin"] == "supplemental" and case["phase"] == "run":
                        native_seeds[case["id"]] = view
                entry["envelope"] = c.artifact(receipt, canonical(envelope))
            require(identity not in request_ids, "Public SDK reused an operation request UUID")
            request_ids.add(identity)
            entry["request_id"] = identity
            entry["guard_frames"] = [list(item) for item in sorted(seen)]
            check_guard(entry["guard_frames"], case)
            receipt["checks"].append(entry)
    require(Counter(item["role"] for item in receipt["checks"]) == {"core": CHECKS_PER_ROLE, "verify": CHECKS_PER_ROLE},
            "Complete two-role public SDK campaign was narrowed")


def validate_checks(receipt, golden, artifacts):
    expected = golden.expected()
    checks = receipt.get("checks")
    require(type(checks) is list and len(checks) == len(expected) and
            type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected),
            "Incomplete exact public workflow occurrence matrix")
    seen, identities = {}, set()
    fields = {"role", "id", "phase", "origin", "operation", "limits", "request_id", "authority", "retained",
        "expected", "source_evidence", "command", "status", "diagnostic", "record", "semantic_receipt", "envelope",
        "guard_frames", "input_kind", "seed_id", "wire_authority", "wire_retained", "view_json", "view_type",
        "view_fingerprint", "view_request_fingerprint"}
    projected = []
    for check in checks:
        require(type(check) is dict and set(check) == fields, "Incomplete public workflow occurrence receipt")
        key = check["role"], check["id"], check["phase"], check["operation"]
        require(key in expected and key not in seen, "Unknown, duplicate or stale public workflow occurrence")
        role, case = key[0], expected[key]
        identity = _uuid(check["request_id"])
        require(identity not in identities, "Duplicate public request UUID")
        identities.add(identity)
        require(all(canonical(check[name]) == canonical(case[name]) for name in
                    ("origin", "command", "limits", "input_kind", "seed_id")), "Public occurrence authority changed")
        check_guard(check["guard_frames"], case)
        for name in ("authority", "retained", "expected", "source_evidence"):
            reference = case[name]
            if name == "source_evidence" and reference is not None:
                reference = canonical(reference)
            if reference is None:
                require(check[name] is None, "Unexpected public workflow evidence: " + name)
            else:
                require(artifacts.raw(check[name]) == reference, "Complete original occurrence evidence differs: " + name)
        wire_authority = artifacts.raw(check["wire_authority"])
        wire_retained = None if check["wire_retained"] is None else artifacts.raw(check["wire_retained"])
        for wire, original in ((wire_authority, case["authority"]), (wire_retained, case["retained"])):
            if case["input_kind"] == "typed":
                require((wire is None and original is None) or (wire is not None and original is not None and
                        canonical(decode(wire)) == canonical(decode(original))), "Typed input wire changed original authority")
            else:
                require(wire == original, "Public input wire changed original bytes")
        envelope = artifacts.json(check["envelope"])
        expected_envelope = {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": case["operation"],
            "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": role}}
        item = deepcopy(check)
        # UUID and Python frame names are runtime metadata. All original bytes,
        # diagnostics, semantics and exact UUID bindings are checked first. Every
        # complete unprojected receipt/envelope remains retained in artifacts.
        item["request_id"] = "<runtime-uuid4>"
        item["guard_frames"] = "<independently-validated-runtime-frame-census>"
        if case["error"] is not None:
            require(check["status"] == "error" and canonical(check["diagnostic"]) == canonical(case["error"]) and
                    all(check[name] is None for name in ("record", "semantic_receipt", "view_json", "view_type",
                                                        "view_fingerprint", "view_request_fingerprint")),
                    "Exact original rejection changed or retained acceptance")
            expected_envelope.update(status="error", result=None, diagnostics=[case["error"]])
        else:
            require(check["status"] == "ok" and check["diagnostic"] is None, "Successful public result was rejected")
            record = artifacts.raw(check["record"])
            require(record == case["expected"] and canonical(decode(record)) == record,
                    "Complete public workflow result differs from original oracle")
            expected_receipt = expected_semantic(golden.profile, role, case, record, identity)
            semantic = artifacts.json(check["semantic_receipt"])
            require(canonical(semantic) == canonical(expected_receipt), "Public semantic authority, identity, profile or resources differ")
            result = {"schema_version": "biocompiler.core.artifact_response.v1", "transport": "biocompiler.core.artifact_transport.v1",
                "authority": descriptor(wire_authority), "retained_record": descriptor(wire_retained),
                "artifact": descriptor(record), "result": expected_receipt}
            expected_envelope.update(status="ok", result=result, diagnostics=[])
            require(check["view_type"] == "NativeWorkflowRecord" and check["view_fingerprint"] == hashlib.sha256(record).hexdigest() and
                    check["view_request_fingerprint"] == digest(decode(record)["request"]), "Public view changed exact identity or nominal type")
            pretty = json.dumps(decode(record), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode()
            require(artifacts.raw(check["view_json"]) == pretty, "Public view lost full formatted record")
            semantic["request_id"] = "<runtime-uuid4>"
            item["semantic_receipt"] = semantic
        require(canonical(envelope) == canonical(expected_envelope), "Full native envelope or actual UUID/wire binding differs")
        envelope["request_id"] = "<runtime-uuid4>"
        if envelope["status"] == "ok":
            envelope["result"]["result"]["request_id"] = "<runtime-uuid4>"
        item["envelope"] = envelope
        seen[key] = check
        projected.append((key, item))
    occurrence_order = {key: position for position, key in enumerate(seen)}
    for key, check in seen.items():
        if check["input_kind"] == "native":
            seed = seen.get((key[0], check["seed_id"], "run", "run-verification-workflow"))
            require(seed is not None and seed["status"] == "ok" and seed["record"] == check["expected"] and
                    occurrence_order[(key[0], check["seed_id"], "run", "run-verification-workflow")] < occurrence_order[key],
                    "Native-view input lacks complete preceding actual native result")
    require(artifacts.used == set(artifacts.declared), "Unreferenced public workflow artifact")
    return [item for _, item in sorted(projected)]


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
    transport_sources = source_pins("src/" + module.replace(".", "/") + ".py" for module in sorted(SOURCE_MODULES))
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
            complete = canonical({"checks": checks})
            if reference is None:
                reference = complete
            else:
                require(complete == reference, "Complete four-way workflow bytes or occurrence results differ")
            receipts[name] = {"native_inputs": inputs_pin, "workflow": receipt_pin}
    require(len(receipts) == 4 and reference is not None, "Incomplete four-way workflow matrix")
    return {"schema_version": "biocompiler.workflow_public_sdk_reproducibility.v1", "status": "success",
            "revision": revision, "source_revision": source_revision, "run_id": run_id,
            "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "supplemental_pin": SUPPLEMENTAL_PIN,
            "profile_pin": PROFILE_PIN, "receipts": receipts, "native_inputs": natives,
            "complete_results_sha256": hashlib.sha256(reference).hexdigest(),
            "runtime_metadata_projection": ["request_id UUID4", "validated executed Python frame census"],
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
    import biocompiler.workflow_backend
    import biocompiler.compiler.verification_workflow
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
        for name in sorted(SOURCE_MODULES):
            path = Path(sys.modules[name].__file__)
            pin = c.sha(path.read_bytes())
            relative = "src/" + name.replace(".", "/") + ".py"
            require(pin == c.sha((ROOT / relative).read_bytes()), "Installed workflow transport differs from tested source")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = {relative: c.sha((ROOT / relative).read_bytes()) for relative in
            SOURCES}
        corpus = Corpus()
        require(digest(bioc := biocompiler.core_workflow.presentation_capability_profile()) == PROFILE_PIN and bioc == corpus.profile,
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
    print("Native public workflow SDK campaign:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare every actual public SDK workflow occurrence across all four runtimes")
    parser.add_argument("--compare", action="store_true", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete public SDK records, native views and exact rejections match across four required variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
