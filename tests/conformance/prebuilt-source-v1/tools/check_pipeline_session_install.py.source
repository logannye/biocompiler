"""Installed persistent native replay of complete original fixed-pipeline evidence.

The retained Python records are independent comparison data. Requests contain
only original operation authority; no callbacks, accepted records or manager
snapshots are imported. Python protocol children test this harness locally;
actual OCaml execution is required on both hosted platforms and Python versions.
"""
from __future__ import annotations

import argparse
import builtins
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import subprocess
import sys
import time
from uuid import UUID, uuid4

if __package__:
    from . import check_workflow_reproducibility as r
else:
    import check_workflow_reproducibility as r

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.installed_pipeline_session_conformance.v1"
SCOPE = "126_original_fixed_calls_121_live_boundaries_563_continuations_not_unported_callbacks_or_empirical_acceptance"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "pipeline-session.json", "pipeline-session-artifacts"
DECLARATION_PIN = "0efb75e507d8aa72c0ef74077096634d07c6cfcdb81a557072ea536675450feb"
INDEXES = {
    "fixed": ("fixed-pipeline-native-v1.json", "ce976b30aa5e0a8f6477cc027d7bec4a780a31a567f19cfb0993b10839d58f6d"),
    "continuation": ("fixed-pipeline-continuations-native-v1.json", "45c78ef53692cb71fe644ea98331c9ce8caa1bda3b1eab67a93061f30557a9eb"),
}
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_pipeline_session"}
SOURCES = ("tools/check_pipeline_session_install.py", "tests/test_pipeline_session_campaign.py",
    "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py",
    "protocol/pipeline-session-v1.json", "core/test/test_fixed_pipeline_corpus.ml",
    "tools/capture_fixed_pipeline_literals.py", "tools/project_fixed_pipeline_continuations.py",
    "tools/project_fixed_pipeline_native.py")
CORE = {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": "core"}
canonical, digest, require, decode = r.canonical, r.digest, r.require, r.decode
Artifacts, source_pins, verify_binaries = r.Artifacts, r.source_pins, r.verify_binaries
PLATFORMS, PYTHONS = r.PLATFORMS, r.PYTHONS
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def source_tool(name):
    """Load finite checkout proof tools without replacing installed products."""
    require(name in ('realization_source_lineage', 'manager_registration_source_lineage',
        'pipeline_registration_guard', 'pipeline_original_counterpart'), 'Unreviewed source proof tool')
    paths = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT))
        module = importlib.import_module('tools.' + name)
    finally:
        sys.path[:] = paths
    require(Path(module.__file__).resolve() == ROOT / 'tools' / (name + '.py'),
        'Source proof tool origin differs')
    return module


def declaration():
    value, pin = r.read(ROOT / "protocol/pipeline-session-v1.json")
    require(pin == DECLARATION_PIN, "Session protocol declaration changed")
    return value


def equal(actual, expected, message):
    require(canonical(actual) == canonical(expected), message)


def mapping(raw):
    require(type(raw) is dict and raw.get("$type") == "mapping" and
            raw.get("class") in ("builtins.dict", "builtins.mappingproxy") and
            set(raw) == {"$type", "class", "items"}, "Unreviewed original mapping")
    result = {}
    for pair in raw["items"]:
        require(type(pair) is list and len(pair) == 2 and type(pair[0]) is str and pair[0] not in result,
                "Original mapping key is invalid or duplicated")
        result[pair[0]] = pair[1]
    return result


def unpack(raw):
    if type(raw) is list:
        return [unpack(value) for value in raw]
    if type(raw) is not dict:
        return raw
    tag = raw.get("$type")
    if tag is None:
        return {key: unpack(value) for key, value in raw.items()}
    if tag == "mapping":
        return {key: unpack(value) for key, value in mapping(raw).items()}
    if tag in ("list", "tuple"):
        require(set(raw) == {"$type", "items"}, "Unexpected original sequence fields")
        return [unpack(value) for value in raw["items"]]
    if tag == "enum":
        return raw["value"]
    if tag in ("manager", "provider"):
        require(set(raw) == {"$type", "id"}, "Unexpected original identity fields")
        return raw["id"]
    require(tag == "dataclass" and set(raw) == {"$type", "class", "fields"}, "Unreviewed original observation tag")
    name, fields = raw["class"], unpack(raw["fields"])
    additions = {
        "biocompiler.compiler.pipeline.StageRecord": {"schema_version": "biocompiler.stage_record.v0.1"},
        "biocompiler.semantics.context.TargetContext": {"schema_version": "biocompiler.target.v0.1"},
        "biocompiler.compiler.pipeline.ComponentInputContract": {"stage": "components"},
        **{name: {} for name in (
            "biocompiler.artifacts.provenance.SourceLink", "biocompiler.compiler.pipeline.ScopedObligation",
            "biocompiler.compiler.pipeline.CheckSpec", "biocompiler.compiler.pipeline.CheckDecision",
            "biocompiler.compiler.pipeline.PassContract", "biocompiler.compiler.pipeline.PassContext",
            "biocompiler.compiler.pipeline.CompletionProfile", "biocompiler.compiler.pipeline.PipelineResult")},
    }
    require(name in additions, "Unreviewed original dataclass: " + name)
    return {**additions[name], **fields}


def snapshot(raw):
    require(type(raw) is dict and set(raw) == {"manager", "fields"} and type(raw["manager"]) is str,
            "Incomplete original manager observation")
    fields = raw["fields"]
    require(set(fields) == {"_target", "_dependencies", "_passes", "_component_inputs",
        "_provider_history", "_records", "_profiles"}, "Incomplete original manager state")
    def registrations(value):
        result = {}
        for key, entry in mapping(value).items():
            parts = unpack(entry)
            require(type(parts) is list and len(parts) == 3, "Invalid original registration")
            result[key] = dict(zip(("contract", "producer", "validators"), parts))
        return result
    require(mapping(fields["_component_inputs"]) == {}, "Unreviewed fixed component-input registration")
    return {"target": unpack(fields["_target"]), "dependencies": unpack(fields["_dependencies"]),
        "passes": registrations(fields["_passes"]), "provider_history": registrations(fields["_provider_history"]),
        "component_inputs": {}, "component_input_history": {}, "records": unpack(fields["_records"]),
        "profiles": unpack(fields["_profiles"])}


SLOTS = {
    ("intent_to_behavior", "producer"): ("synthetic", "lower"),
    ("intent_to_behavior", "preservation"): ("synthetic", "verify"),
    ("behavior_to_synthetic", "producer"): ("synthetic", "generate"),
    ("behavior_to_synthetic", "finite_history"): ("synthetic", "check"),
    ("synthetic_to_components", "producer"): ("components", "generate"),
    ("synthetic_to_components", "composition"): ("components", "verify"),
}


class Providers:
    def __init__(self):
        self.forward, self.reverse, self.slots = {}, {}, {}

    def align(self, actual, expected, providers, family):
        actual = deepcopy(actual)
        require(type(actual) is dict and set(actual) == set(expected), "Incomplete actual manager fields")
        for field in ("passes", "provider_history"):
            require(set(actual[field]) == set(expected[field]), "Actual manager registration census differs")
            for key, wanted in expected[field].items():
                got = actual[field][key]
                require(set(got) == {"contract", "producer", "validators"}, "Unexpected registration fields")
                equal(got["contract"], wanted["contract"], "Actual fixed contract differs")
                require(set(got["validators"]) == set(wanted["validators"]), "Validator census differs")
                for slot in ("producer", *wanted["validators"]):
                    original = wanted["producer"] if slot == "producer" else wanted["validators"][slot]
                    native = got["producer"] if slot == "producer" else got["validators"][slot]
                    require(type(native) is str and re.fullmatch(r"provider/[0-9]+", native), "Invalid native provider token")
                    module, function = SLOTS[wanted["contract"]["id"], slot]
                    descriptor = providers[original]
                    require(descriptor["class"] == "builtins.function" and
                        descriptor["file"] == "src/biocompiler/compiler/" + module + ".py" and
                        descriptor["qualname"] == "run_" + ("component" if module == "components" else module) +
                            "_pipeline.<locals>." + function, "Unreviewed original fixed provider")
                    require(self.forward.get((family, native), original) == original and
                            self.reverse.get((family, original), native) == native,
                            "Provider physical identity changed or distinct providers aliased")
                    # The two independent original captures use different token
                    # namespaces. Their source-bound slot is the bridge, not a
                    # reason to forget native identity at the return boundary.
                    identity = wanted["contract"]["id"], slot
                    require(self.slots.get(identity, native) == native,
                            "Native provider identity changed between original captures")
                    require(all(token != native or previous_slot == identity
                                for previous_slot, token in self.slots.items()),
                            "Distinct original fixed provider slots aliased")
                    self.slots[identity] = native
                    self.forward[family, native], self.reverse[family, original] = original, native
                    if slot == "producer":
                        got["producer"] = original
                    else:
                        got["validators"][slot] = original
        equal(actual, expected, "Complete original manager state differs")
        return actual


class Corpus:
    def __init__(self):
        self.indexes, self.pins, self.descriptors, self.cache = {}, {}, {}, {}
        self.original_sources, self.provider_records = {}, {}
        for family, (name, pin) in INDEXES.items():
            path = ROOT / "tests/conformance" / name
            value, file_pin = r.read(path)
            require(value["inventory_fingerprint"] == pin and
                digest({key: entry for key, entry in value.items() if key != "inventory_fingerprint"}) == pin,
                "Pinned complete original pipeline corpus differs")
            require(value["document_directory"] == ("fixed-pipeline-literals-v1" if family == "fixed" else "checked-pipeline-v1"),
                    "Unexpected original document directory")
            self.indexes[family] = value
            self.pins[family] = {"path": "tests/conformance/" + name, "sha256": file_pin,
                "inventory_fingerprint": pin, "full_corpus": value["full_corpus"], "prior_ledger": value["prior_ledger"]}
            self.descriptors[family] = {entry["id"]: entry for entry in value["documents"]}
            require(len(self.descriptors[family]) == len(value["documents"]), "Duplicate original document descriptor")
            self._verify_lineage(value)
        fixed, continuation = self.indexes["fixed"], self.indexes["continuation"]
        self.all_cases, self.entries = fixed["cases"], continuation["entries"]
        require(len(self.all_cases) == len(self.entries) == 136 and len(fixed["original_methods"]) == 467,
                "Full original fixed cohort was narrowed")
        self.cases = [case for case in self.all_cases if self.eligible(case)]
        self.by_id = {case["id"]: case for case in self.all_cases}
        self.continuations = {entry["case"]: entry for entry in self.entries}
        require(len(self.by_id) == len(self.continuations) == 136, "Duplicate original fixed occurrence")
        for case, entry in zip(self.all_cases, self.entries):
            require(entry["case"] == case["id"] and entry["operation"] == case["api"], "Original continuation binding differs")
            for key in ("kind", "changed_bindings", "python_only_inputs"):
                equal(entry[key], case[key], "Original continuation classification differs")
        self.excluded = [case for case in self.all_cases if not self.eligible(case)]
        self.census = {"original_methods": 467, "all_calls": len(self.all_cases), "eligible_calls": len(self.cases),
            "returned": sum(c["outcome"] == "returned" for c in self.cases),
            "raised": sum(c["outcome"] == "raised" for c in self.cases),
            "boundaries": sum(self.continuations[c["id"]]["boundary"] is not None for c in self.cases),
            "continuations": sum(len(self.continuations[c["id"]].get("supported_prefix_events", [])) for c in self.cases),
            "pending_callback_suffix": sum(len(self.continuations[c["id"]].get("pending_callback_dependent_suffix", [])) for c in self.cases),
            "excluded_calls": len(self.excluded),
            "excluded_prefix": sum(len(self.continuations[c["id"]].get("supported_prefix_events", [])) for c in self.excluded),
            "excluded_suffix": sum(len(self.continuations[c["id"]].get("pending_callback_dependent_suffix", [])) for c in self.excluded)}
        require(list(self.census.values()) == [467, 136, 126, 121, 5, 121, 563, 254, 10, 24, 9], "Original pipeline census differs")
        require(Counter(c["api"] for c in self.cases) == {"run_synthetic_pipeline": 86, "run_component_pipeline": 40},
                "Original fixed API coverage differs")

    def _verify_lineage(self, index):
        for path, pin in index["source_files"].items():
            require(path.startswith(("src/", "tests/", "examples/")) and ".." not in Path(path).parts and r.pin(pin),
                    "Invalid original source authority")
            source_tool("realization_source_lineage").verify_captured_source(ROOT, {"path": path, "sha256": pin})
            if path not in self.original_sources:
                self.original_sources[path] = pin
            require(self.original_sources[path] == pin, "Original source changed: " + path)
        full = index["full_corpus"]
        require(Path(full["path"]).name == full["path"] and
                sha(r.raw_file(ROOT / "tests/conformance" / full["path"])) == full["sha256"],
                "Full original pipeline source index changed")
        require(index["provider_directory"] == "fixed-pipeline-provider-records-v1",
                "Unexpected complete original provider directory")
        records = {entry["id"]: entry for entry in index["provider_documents"]}
        require(len(records) == len(index["provider_documents"]), "Duplicate original provider descriptor")
        for original, provider in index["providers"].items():
            item = provider["complete_provider_record"]
            identity = item["id"]
            require(r.pin(identity) and item == records.get(identity), "Uninventoried original complete provider")
            if identity not in self.provider_records:
                path = ROOT / "tests/conformance" / index["provider_directory"] / (identity + ".json")
                raw = r.raw_file(path)
                value = decode(raw)
                require(len(raw) == item["bytes"] and raw == canonical(value) + b"\n" and digest(value) == identity,
                        "Complete original provider bytes changed")
                self.provider_records[identity] = {key: value[key] for key in provider if key != "complete_provider_record"}
            equal(self.provider_records[identity], {key: value for key, value in provider.items() if key != "complete_provider_record"},
                  "Original provider descriptor differs from its complete source-bound record")
            require(provider["id"] == original, "Original provider identity differs")

    @staticmethod
    def eligible(case):
        return case["kind"] == "actual_original_function" and case["changed_bindings"] == [] and case["python_only_inputs"] == []

    def document(self, family, identity):
        key = family, identity
        if key in self.cache:
            return deepcopy(self.cache[key])
        require(r.pin(identity) and identity in self.descriptors[family], "Uninventoried original document")
        entry, index = self.descriptors[family][identity], self.indexes[family]
        raw = r.raw_file(ROOT / "tests/conformance" / index["document_directory"] / (identity + ".json"))
        value = decode(raw)
        require(len(raw) == entry["bytes"] and raw == canonical(value) + b"\n" and digest(value) == identity,
                "Complete original document bytes changed")
        if len(self.cache) >= 8:
            self.cache.clear()
        self.cache[key] = value
        return deepcopy(value)

    def pending(self):
        return [{"case": case, "continuation": self.continuations[case["id"]]} for case in self.excluded] + [
            {"case": case["id"], "pending_callback_dependent_suffix": self.continuations[case["id"]].get("pending_callback_dependent_suffix", [])}
            for case in self.cases]

    def steps(self, case):
        authority = self.document("fixed", case["authority"])
        require(set(authority) == {"request", "history", "until", "config"}, "Original fixed authority fields differ")
        kind = "synthetic" if case["api"] == "run_synthetic_pipeline" else "components"
        steps = []
        def add(label, operation, payload, value=None, error=None, state=None, family="fixed"):
            steps.append({"label": label, "operation": operation, "payload": payload,
                "value": value, "error": error, "state": state, "family": family})
        add("initialize", "initialize-" + kind, authority,
            {"kind": kind, "manager": True, "artifacts": declaration()["artifacts"][kind]} if case["outcome"] == "returned" else None,
            case.get("error") if case["outcome"] == "raised" else None)
        manager_state = case["manager_state"]
        if manager_state is None and kind == "components" and case["outcome"] == "raised":
            children = [child for child in self.all_cases if child["parent"] == case["id"]]
            require(len(children) == 1 and children[0]["api"] == "run_synthetic_pipeline" and
                    children[0]["outcome"] == "raised" and children[0]["error"] == case["error"],
                    "Original nested component failure state is not uniquely bound")
            manager_state = children[0]["manager_state"]
        if manager_state is None:
            add("initial-state", "inspect", {}, error={"native_state_unavailable": True})
        else:
            add("initial-state", "inspect", {}, state=snapshot(self.document("fixed", manager_state)))
        if case["outcome"] == "returned":
            records = self.document("fixed", case["complete_records"])
            returned = self.document("fixed", case["result"])
            require(returned["$type"] == "dataclass" and returned["class"] ==
                "biocompiler.compiler." + ("synthetic.SyntheticBuild" if kind == "synthetic" else "components.ComponentBuild"),
                "Original returned fixed build class differs")
            equal(records["stages"], steps[-1]["state"]["records"], "Original complete stage inventory differs")
            for name in declaration()["artifacts"][kind]:
                value = unpack(returned["fields"]["result"]) if name == "pipeline_result" else records[name]
                add("artifact/" + name, "artifact", {"name": name}, value=value)
        entry = self.continuations[case["id"]]
        if entry["boundary"] is None:
            require(case["outcome"] == "raised" and entry["events"] == [], "Missing original live return boundary")
        else:
            prefix, suffix, events = entry["supported_prefix_events"], entry["pending_callback_dependent_suffix"], entry["events"]
            equal([event["id"] for event in events], prefix + suffix, "Complete original continuation ordering differs")
            replay = [entry["boundary"], *events[:len(prefix)]]
            for event in replay:
                require(event["parent"] is None and event["manager"] == entry["manager"], "Continuation is not on the original live manager")
                arguments = mapping(self.document("continuation", event["arguments"]))
                equal(unpack(arguments["subject"]), entry["manager"], "Continuation manager binding differs")
                operation = {"PassManager.get": "get", "PassManager.result": "result",
                    "PassManager.set_dependency": "set-dependency", "PassManager.target": "target"}[event["api"]]
                add(event["id"] + "/before", "inspect", {}, state=snapshot(self.document("continuation", event["state_before"])), family="continuation")
                add(event["id"], operation, unpack(arguments["bound"]),
                    value=unpack(self.document("continuation", event["result"])) if event["outcome"] == "returned" else None,
                    error=event.get("error"), family="continuation")
                add(event["id"] + "/after", "inspect", {}, state=snapshot(self.document("continuation", event["state_after"])), family="continuation")
            if suffix:
                require(events[len(prefix)]["api"] not in ("PassManager.get", "PassManager.result", "PassManager.set_dependency", "PassManager.target"),
                        "A supported original prefix observation was withheld")
        add("close", "close", {})
        return steps


def artifact(receipt, raw):
    identity = sha(raw)
    directory = Path(receipt["_artifact_directory"])
    path = directory / (identity + ".bin")
    if path.exists():
        require(path.read_bytes() == raw, "Evidence identity collision")
    else:
        path.write_bytes(raw)
    receipt["artifacts"][identity] = {"path": path.name, "bytes": len(raw), "sha256": identity}
    return identity


@contextmanager
def guarded_execution():
    previous, original_import = sys.getprofile(), builtins.__import__
    seen = set()
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in TRANSPORT_MODULES, "Unreviewed session product import: " + name)
        return original_import(name, *args, **kwargs)
    def calls(frame, event, result):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and module.startswith("biocompiler"):
            require(module in TRANSPORT_MODULES, "Python pipeline semantic fallback is forbidden: " + module)
            seen.add((module, frame.f_code.co_qualname))
    builtins.__import__, old = imports, sys.getprofile()
    sys.setprofile(calls)
    try:
        yield seen
        require(sys.getprofile() is calls and builtins.__import__ is imports, "Session execution guard was disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = original_import


def check_guard(entries):
    require(type(entries) is list and entries == sorted(entries) and all(type(item) is list and len(item) == 2 and
            all(type(value) is str for value in item) for item in entries) and len({tuple(item) for item in entries}) == len(entries),
            "Malformed complete session guard census")
    require(all(item[0] in TRANSPORT_MODULES for item in entries) and
            ["biocompiler.core_pipeline_session", "CorePipelineSession.__init__"] in entries and
            ["biocompiler.core_pipeline_session", "CorePipelineSession.call"] in entries,
            "Missing persistent transport calls or forbidden Python semantic execution")


def hello_step():
    profile = declaration()
    return {"label": "hello", "operation": "hello", "payload": {"profile": profile["profile"], "limits": None, "manager_limits": None},
        "value": {"profile": profile, "limits": profile["limits"], "manager_limits": profile["manager_limits"]},
        "error": None, "state": None, "family": "fixed"}


def frame_body(raw):
    require(type(raw) is bytes and len(raw) >= 9 and re.fullmatch(b"[0-9a-f]{8}\\n", raw[:9]) is not None and
            int(raw[:8], 16) == len(raw) - 9, "Incomplete or malformed exact session frame")
    value = decode(raw[9:])
    require(canonical(value) == raw[9:], "Noncanonical session body bytes")
    return value


def raw_session_exchange(path, request):
    """Exercise an actual executable's session entry with bounded pipe collection."""
    process = subprocess.Popen([str(path), declaration()["argument"]], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    output, errors = bytearray(), bytearray()
    deadline, offset = time.monotonic() + 30, 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream, event, name in ((process.stdin, selectors.EVENT_WRITE, "stdin"),
                    (process.stdout, selectors.EVENT_READ, "stdout"),
                    (process.stderr, selectors.EVENT_READ, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Raw session probe exceeded its deadline")
                for key, _ in selector.select(min(remaining, .1)):
                    if key.data == "stdin":
                        try:
                            offset += os.write(key.fileobj.fileno(), request[offset:])
                        except BrokenPipeError:
                            offset = len(request)
                        if offset == len(request):
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        raw = os.read(key.fileobj.fileno(), r.CONTROL_BYTES + 1)
                        if not raw:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        else:
                            target = output if key.data == "stdout" else errors
                            target.extend(raw)
                            require(len(output) + len(errors) <= r.CONTROL_BYTES,
                                    "Raw session probe exceeded its output bound")
            code = process.wait(timeout=max(.001, deadline - time.monotonic()))
        return code, bytes(output), bytes(errors)
    finally:
        # Reap descendants retaining a pipe even if the direct child exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            if process.poll() is None:
                process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def verify_rejection(path, pin, receipt):
    profile = declaration()
    body = canonical({"protocol": profile["protocol"], "session_id": str(uuid4()), "sequence": 0,
        "operation": "hello", "payload": hello_step()["payload"]})
    request = f"{len(body):08x}\n".encode() + body
    code, stdout, stderr = raw_session_exchange(path, request)
    receipt["verify_rejection"] = {"argv": [str(path), profile["argument"]], "executable_sha256": pin,
        "returncode": code, "request": artifact(receipt, request),
        "stdout": artifact(receipt, stdout), "stderr": artifact(receipt, canonical({"hex": stderr.hex()}))}


def validate_verify_rejection(receipt, artifacts):
    row, profile = receipt["verify_rejection"], declaration()
    require(type(row) is dict and set(row) == {"argv", "executable_sha256", "returncode", "request", "stdout", "stderr"} and
        row["argv"] == [receipt["executables"]["verify"], profile["argument"]] and
        row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-verify"] and
        type(row["returncode"]) is int and row["returncode"] == 2, "Verify session execution or role rejection differs")
    request = frame_body(artifacts.raw(row["request"]))
    require(type(request) is dict and type(request.get("session_id")) is str,
            "Missing actual Verify session request")
    nonce = request["session_id"]
    try:
        identity = UUID(nonce)
    except ValueError as error:
        raise AssertionError("Invalid Verify session nonce") from error
    require(identity.version == 4 and str(identity) == nonce, "Invalid Verify session nonce")
    equal(request, {"protocol": profile["protocol"], "session_id": nonce, "sequence": 0,
        "operation": "hello", "payload": hello_step()["payload"]}, "Verify was not invoked with the real session request")
    expected = {"protocol": CORE["protocol"], "request_id": None, "operation": None, "status": "error",
        "result": None, "diagnostics": [{"code": "unexpected_arguments",
            "message": "Expected standard JSON input or the exact inherited artifact descriptor arguments.", "path": None}],
        "core": {**CORE, "executable": "verify"}}
    require(artifacts.raw(row["stdout"]) == canonical(expected) + b"\n",
            "Actual independent Verify executable did not reject session mode exactly")
    equal(artifacts.json(row["stderr"]), {"hex": ""}, "Verify session rejection wrote unexpected stderr")


def framed(raw):
    return f"{len(raw):08x}\n".encode() + raw


def protocol_probes(nonce):
    """Exact byte recipes, including EOF and bytes after a terminal command."""
    profile = declaration()
    def request(sequence, operation, payload=None, identity=None):
        return {"protocol": profile["protocol"], "session_id": identity or nonce, "sequence": sequence,
            "operation": operation, "payload": {} if payload is None else payload}
    hello = request(0, "hello", hello_step()["payload"])
    close = request(1, "close")
    encode = lambda value: framed(canonical(value))
    prefix = encode(hello)
    result = []
    def add(name, raw, *, prior=(), binding=None, established=False, reserved=0, commands=0, terminal=True):
        result.append({"id": name, "stdin": raw, "prior": list(prior), "binding": binding,
            "session_id": nonce if established else None, "input_bytes": reserved,
            "commands": commands, "terminal": terminal})
    for name, raw in (("short-header", b"0000"), ("uppercase-header", b"0000000A\n"),
            ("nonhex-header", b"0000000g\n"), ("missing-header-newline", b"00000001 "),
            ("zero-body", b"00000000\n"), ("oversize-body", b"02000001\n")):
        add(name, raw)
    add("short-body", b"0000000a\n{}", reserved=19, commands=1)
    for name, raw in (("malformed-json", b"{"), ("duplicate-json-key", b'{"protocol":null,"protocol":null}')):
        add(name, framed(raw), reserved=len(raw) + 9, commands=1)
    target = request(0, "target")
    add("unsolicited-before-hello", encode(target) + prefix, binding=target, established=True,
        reserved=len(encode(target)), commands=1)
    for name, command in (("repeated-hello", request(1, "hello", hello_step()["payload"])),
            ("replayed-sequence", request(0, "target")), ("skipped-sequence", request(2, "target")),
            ("cross-session", request(1, "target", identity="ffffffff-ffff-4fff-bfff-ffffffffffff"))):
        add(name, prefix + encode(command) + encode(close), prior=(hello,), binding=command, established=True,
            reserved=len(prefix) + len(encode(command)), commands=2)
    add("short-header-after-hello", prefix + b"0000", prior=(hello,), established=True,
        reserved=len(prefix), commands=1)
    add("short-body-after-hello", prefix + b"0000000a\n{}", prior=(hello,), established=True,
        reserved=len(prefix) + 19, commands=2)
    add("trailing-frame-after-close", prefix + encode(close) + encode(request(2, "target")),
        prior=(hello, close), established=True, reserved=len(prefix) + len(encode(close)), commands=2, terminal=False)
    return result


def protocol_campaign(path, pin, receipt):
    receipt["protocol_checks"] = []
    for number in range(len(protocol_probes("00000000-0000-4000-8000-000000000000"))):
        nonce = str(uuid4())
        probe = protocol_probes(nonce)[number]
        code, stdout, stderr = raw_session_exchange(path, probe["stdin"])
        receipt["protocol_checks"].append({"id": probe["id"], "session_id": nonce,
            "argv": [str(path), declaration()["argument"]], "executable_sha256": pin,
            "returncode": code, "stdin": artifact(receipt, probe["stdin"]),
            "stdout": artifact(receipt, stdout), "stderr": artifact(receipt, canonical({"hex": stderr.hex()}))})


def split_frames(raw):
    frames = []
    while raw:
        require(len(raw) >= 9 and re.fullmatch(b"[0-9a-f]{8}\\n", raw[:9]), "Malformed installed session probe output")
        length = int(raw[:8], 16) + 9
        require(9 < length <= len(raw), "Truncated installed session probe output")
        frames.append((raw[:length], frame_body(raw[:length])))
        raw = raw[length:]
    return frames


def validate_protocol_checks(receipt, artifacts):
    rows, profile = receipt["protocol_checks"], declaration()
    require(type(rows) is list and len(rows) == len(protocol_probes("00000000-0000-4000-8000-000000000000")),
            "Incomplete installed protocol probe matrix")
    seen, projected = set(), []
    for ordinal, row in enumerate(rows):
        require(type(row) is dict and set(row) == {"id", "session_id", "argv", "executable_sha256", "returncode", "stdin", "stdout", "stderr"},
                "Incomplete installed protocol probe")
        nonce = row["session_id"]
        require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", nonce)
            and nonce not in seen and nonce != "ffffffff-ffff-4fff-bfff-ffffffffffff", "Reused or invalid installed protocol nonce")
        seen.add(nonce)
        probe = protocol_probes(nonce)[ordinal]
        require(row["id"] == probe["id"] and row["argv"] == [receipt["executables"]["core"], profile["argument"]] and
            row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-core"] and
            type(row["returncode"]) is int and row["returncode"] == 0, "Unbound installed protocol execution")
        require(artifacts.raw(row["stdin"]) == probe["stdin"], "Installed malformed input recipe changed")
        equal(artifacts.json(row["stderr"]), {"hex": ""}, "Installed protocol probe emitted stderr")
        frames = split_frames(artifacts.raw(row["stdout"], r.CONTROL_BYTES))
        require(len(frames) == len(probe["prior"]) + int(probe["terminal"]),
                "Installed protocol omitted or emitted extra terminal frames")
        normalized, output_bytes, prior_work = [], 0, -1
        for index, (raw, response) in enumerate(frames):
            terminal = index == len(probe["prior"])
            request = probe["binding"] if terminal else probe["prior"][index]
            binding = {"sequence": None, "operation": None, "request_sha256": None} if request is None else {
                "sequence": request["sequence"], "operation": request["operation"], "request_sha256": digest(request)}
            expected = {"protocol": profile["protocol"], "profile": profile["profile"], "session_id": probe["session_id"] if terminal else nonce,
                **binding, "status": "error" if terminal else "ok", "result": None,
                "diagnostics": [{"code": "pipeline_session_fatal", "message": "Session closed after a framing, identity, resource or internal failure.", "path": None}] if terminal else [],
                "exception": None, "closed": terminal or request["operation"] == "close", "core": CORE}
            if not terminal and request["operation"] == "hello":
                expected["result"] = hello_step()["value"]
            require(type(response) is dict and set(response) == set(profile["response_fields"]), "Malformed installed probe envelope")
            equal({key: value for key, value in response.items() if key != "usage"}, expected,
                  "Installed protocol frame binding or fatal semantics differ: " + probe["id"])
            require(not terminal or len(raw) <= profile["fixed_limits"]["terminal_reserve_bytes"], "Unbounded installed terminal reply")
            output_bytes += len(raw)
            usage = response["usage"]
            reserved = probe["input_bytes"] if terminal else sum(len(framed(canonical(value))) for value in probe["prior"][:index + 1])
            commands = probe["commands"] if terminal else index + 1
            require(type(usage) is dict and set(usage) == set(profile["usage_fields"]) and all(type(value) is int and value >= 0 for value in usage.values()) and
                usage["input_bytes"] == reserved and usage["output_bytes"] == output_bytes and usage["commands"] == commands and
                usage["work_charged"] >= max(prior_work, profile["fixed_limits"]["terminal_reserve_work"]) and
                usage["work_charged"] + usage["work_remaining"] == profile["limits"]["max_work"] and
                usage["retained_bytes"] <= profile["limits"]["max_retained_bytes"], "Installed protocol resource accounting differs")
            prior_work = usage["work_charged"]
            normalized.append({**response, "session_id": None if response["session_id"] is None else "<session-uuid4>",
                "request_sha256": None if response["request_sha256"] is None else "<exact-request-body-sha256>"})
        projected.append({"id": probe["id"], "frames_sha256": digest(normalized)})
    return projected


def check_response(response, step, corpus, aliases):
    if step["error"] is not None:
        require(response["status"] == "error" and response["result"] is None and response["closed"] is False,
                "Original semantic rejection did not retain the live process")
        if step["error"] == {"native_state_unavailable": True}:
            equal(response["diagnostics"], [{"code": "pipeline_session_state", "message": "This session has no live manager.", "path": None}],
                  "Missing-manager diagnostic differs")
            require(response["exception"] is None, "Native session state rejection invented a Python exception")
        else:
            wanted = {**step["error"], "attributes": step["error"].get("attributes", {})}
            equal(response["exception"], wanted, "Complete original pipeline exception differs")
            equal(response["diagnostics"], [{"code": "pipeline_error", "message": wanted["message"], "path": None}],
                  "Original pipeline rejection diagnostic differs")
    else:
        require(response["status"] == "ok" and response["exception"] is None and response["diagnostics"] == [] and
                response["closed"] is (step["operation"] == "close"), "Unexpected pipeline response status")
        if step["state"] is not None:
            return aliases.align(response["result"], step["state"], corpus.indexes[step["family"]]["providers"], step["family"])
        equal(response["result"], step["value"], "Complete original pipeline result differs: " + step["label"])
    return response["result"]


def metadata(corpus):
    return {"corpus_pins": corpus.pins, "corpus_census": corpus.census, "protocol_sha256": DECLARATION_PIN,
        "original_source_pins": corpus.original_sources, "complete_provider_records": len(corpus.provider_records)}


def campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_session import CorePipelineSession, SessionRejected, SessionUnsupported
    for case in corpus.cases:
        steps = corpus.steps(case)
        row = {"id": case["id"], "case": artifact(receipt, canonical(case)),
            "continuation": artifact(receipt, canonical(corpus.continuations[case["id"]])), "frames": [], "pids": []}
        session = None
        with guarded_execution() as seen:
            try:
                session = CorePipelineSession(core)
                row["pid"] = session.pid
                row["frames"].append({"label": "hello", "request": artifact(receipt, session.hello_response.request_frame),
                                      "response": artifact(receipt, session.hello_response.response_frame)})
                row["pids"].append(session.pid)
                for step in steps:
                    try:
                        response = session.close() if step["operation"] == "close" else session.call(step["operation"], step["payload"])
                    except (SessionRejected, SessionUnsupported) as error:
                        response = error.response
                    require(response is not None, "Session closed before its original final command")
                    row["frames"].append({"label": step["label"], "request": artifact(receipt, response.request_frame),
                                          "response": artifact(receipt, response.response_frame)})
                    row["pids"].append(session.pid)
            finally:
                if session is not None:
                    session.close()
            row.update(returncode=session.returncode, closed=session.closed, invalidated=session.invalidated,
                executable_sha256=session.executable_sha256,
                stderr=artifact(receipt, canonical({"hex": session.stderr_bytes.hex()})))
        row["guard"] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
        receipt["checks"].append(row)
    receipt["pending"] = artifact(receipt, canonical(corpus.pending()))


def validate_checks(receipt, corpus, artifacts):
    profile = declaration()
    validate_verify_rejection(receipt, artifacts)
    protocol_checks = validate_protocol_checks(receipt, artifacts)
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(corpus.cases) and
            type(receipt.get("checks")) is list and len(receipt["checks"]) == len(corpus.cases), "Incomplete original fixed session census")
    equal(artifacts.json(receipt["pending"], r.MAX_ARTIFACT_BYTES), corpus.pending(), "Excluded original evidence was dropped or relabeled")
    sessions, projected = set(), []
    for case, row in zip(corpus.cases, receipt["checks"]):
        require(set(row) == {"id", "case", "continuation", "frames", "pids", "pid", "returncode", "closed", "invalidated",
            "executable_sha256", "stderr", "guard"} and row["id"] == case["id"], "Original fixed occurrence missing, reordered or substituted")
        equal(artifacts.json(row["case"], r.MAX_ARTIFACT_BYTES), case, "Complete original case evidence differs")
        equal(artifacts.json(row["continuation"], r.MAX_ARTIFACT_BYTES), corpus.continuations[case["id"]], "Complete original continuation differs")
        check_guard(artifacts.json(row["guard"], r.MAX_ARTIFACT_BYTES))
        equal(artifacts.json(row["stderr"]), {"hex": ""}, "Native session wrote unexpected stderr")
        require(type(row["pid"]) is int and row["pid"] > 0 and type(row["returncode"]) is int and row["returncode"] == 0 and
            row["closed"] is True and row["invalidated"] is False and
            row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-core"], "Persistent process provenance or lifecycle differs")
        steps = [hello_step(), *corpus.steps(case)]
        require(type(row["frames"]) is list and len(row["frames"]) == len(steps) and row["pids"] == [row["pid"]] * len(steps),
                "Pipeline manager did not stay in one process for its complete original continuation")
        aliases = Providers()
        normalized, session_id, previous = [], None, None
        input_bytes = output_bytes = 0
        for sequence, (step, exchange) in enumerate(zip(steps, row["frames"])):
            require(set(exchange) == {"label", "request", "response"} and exchange["label"] == step["label"], "Session recipe frame missing or reordered")
            raw_request, raw_response = artifacts.raw(exchange["request"]), artifacts.raw(exchange["response"])
            request, response = frame_body(raw_request), frame_body(raw_response)
            if sequence == 0:
                session_id = request.get("session_id")
                try:
                    identity = UUID(session_id)
                except (ValueError, TypeError, AttributeError) as error:
                    raise AssertionError("Invalid session identity") from error
                require(identity.version == 4 and str(identity) == session_id and session_id not in sessions, "Reused or noncanonical session identity")
                sessions.add(session_id)
            equal(request, {"protocol": profile["protocol"], "session_id": session_id, "sequence": sequence,
                "operation": step["operation"], "payload": step["payload"]}, "Complete original session request authority differs")
            require(type(response) is dict and set(response) == set(profile["response_fields"]) and
                response["protocol"] == profile["protocol"] and response["profile"] == profile["profile"] and
                response["session_id"] == session_id and type(response["sequence"]) is int and response["sequence"] == sequence and
                response["operation"] == step["operation"] and response["request_sha256"] == sha(raw_request[9:]),
                "Session response identity or exact frame binding differs")
            equal(response["core"], CORE, "Wrong session executable role or protocol identity")
            usage = response["usage"]
            require(type(usage) is dict and set(usage) == set(profile["usage_fields"]) and
                all(type(value) is int and value >= 0 for value in usage.values()), "Invalid cumulative session usage")
            require(usage["work_charged"] + usage["work_remaining"] == profile["limits"]["max_work"] and
                usage["work_charged"] >= profile["fixed_limits"]["terminal_reserve_work"] and
                usage["retained_bytes"] <= profile["limits"]["max_retained_bytes"] and
                usage["commands"] == sequence + 1 <= profile["limits"]["max_commands"], "Session resource profile changed or exceeded")
            input_bytes += len(raw_request)
            require(usage["input_bytes"] == input_bytes and usage["output_bytes"] == output_bytes + len(raw_response),
                    "Exact session byte accounting differs")
            output_bytes += len(raw_response)
            require(input_bytes + output_bytes <= profile["limits"]["max_total_bytes"], "Session exceeded cumulative wire limit")
            if previous is not None:
                require(all(usage[key] >= previous[key] for key in usage if key != "work_remaining") and
                    usage["work_charged"] > previous["work_charged"] and
                    usage["work_remaining"] < previous["work_remaining"], "Session lifetime budget reset between commands")
            previous = usage
            result = check_response(response, step, corpus, aliases)
            normalized.append({"request": {**request, "session_id": "<session-uuid4>"},
                "response": {**response, "session_id": "<session-uuid4>", "request_sha256": "<exact-request-body-sha256>", "result": result}})
        projected.append({"id": case["id"], "case": row["case"], "continuation": row["continuation"], "frames_sha256": digest(normalized)})
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete session evidence")
    return {"original_calls": projected, "protocol_probes": protocol_checks}


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
        type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and type(run_id) is str and run_id,
        "Missing current session validation authority")
    root, native_root = Path(root), Path(native_root)
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink() and
        {p.name for p in root.iterdir() if p.name.startswith("realization-")} == names, "Incomplete four-runtime session matrix")
    corpus, receipts, binaries, reference = Corpus(), {}, {}, None
    transport_sources = source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(TRANSPORT_MODULES))
    for target, (system, machine) in PLATFORMS.items():
        native = verify_binaries(native_root / target, revision, target)
        binaries[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe session runtime slot")
            inputs, inputs_pin = r.read(directory / "native-inputs.json", r.CONTROL_BYTES)
            require(all(inputs.get(key) == value for key, value in native.items()) and inputs.get("run_id") == run_id and
                inputs.get("source_revision") == source_revision and type(inputs.get("python_version")) is str and
                inputs["python_version"].startswith(python + "."), "Stale session native inputs")
            receipt, receipt_pin = r.read(directory / RECEIPT_FILE)
            fields = {"schema_version": SCHEMA, "status": "success", "scope": SCOPE, "revision": revision,
                "source_revision": source_revision, "run_id": run_id, "python_version": inputs["python_version"],
                "system": system, "machine": machine, "native_platform": target, "artifact_directory": ARTIFACT_DIRECTORY,
                "native_inputs": native, "transport_sources": transport_sources, "campaign_sources": source_pins(SOURCES), **metadata(corpus)}
            for key, value in fields.items():
                equal(receipt.get(key), value, "Stale or mixed session receipt: " + key)
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute() and
                not Path(receipt["package_path"]).is_relative_to(ROOT), "Session package was not installed")
            require(type(receipt.get("executables")) is dict and set(receipt["executables"]) == {"core", "verify"} and
                all(type(path) is str and Path(path).is_absolute() and Path(path).name == "biocompiler-" + role
                    for role, path in receipt["executables"].items()) and
                Path(receipt["executables"]["core"]).parent == Path(receipt["executables"]["verify"]).parent,
                "Exact session binary selection missing")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt["artifacts"])
            projected = canonical(validate_checks(receipt, corpus, artifacts))
            require(reference is None or projected == reference, "Complete original session observations differ across runtimes")
            reference = projected
            receipts[name] = {"receipt_sha256": receipt_pin, "native_inputs_sha256": inputs_pin, "complete_artifacts": artifacts.verified}
    return {"schema_version": "biocompiler.pipeline_session_reproducibility.v1", "status": "success", "scope": SCOPE,
        "revision": revision, "source_revision": source_revision, "run_id": run_id, **metadata(corpus),
        "receipts": receipts, "native_inputs": binaries, "complete_results_sha256": sha(reference),
        "projection": "validated_unique_session_UUID4_process_PID_and_source_bound_bijective_provider_tokens_only;complete_frames_retained"}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ("core", "verify"):
        parser.add_argument("--" + role, required=True, type=Path)
        parser.add_argument("--" + role + "-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(TRANSPORT_MODULES):
        importlib.import_module(name)
    corpus, directory = Corpus(), args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), "Unsafe or nonempty session artifact directory")
    started = time.monotonic()
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE, **metadata(corpus),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python_version": platform.python_version(),
        "system": platform.system(), "machine": platform.machine(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": ARTIFACT_DIRECTORY, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed session campaign outside checkout")
        require(receipt["run_id"] and receipt["source_revision"] and (platform.system(), platform.machine()) == PLATFORMS[args.platform],
                "Missing or mismatched hosted session authority")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product loaded: " + name)
        native = verify_binaries(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"], receipt["executables"] = native, {}
        for role in ("core", "verify"):
            path, pin = getattr(args, role), getattr(args, role + "_sha256")
            require(path.is_absolute() and path.resolve() == (args.native_root / ("biocompiler-" + role)).resolve() and
                not path.is_symlink() and os.access(path, os.X_OK) and pin == native["sha256"][path.name], "Unbound session binary")
            receipt["executables"][role] = str(path)
        receipt["transport_sources"] = {}
        for name in sorted(TRANSPORT_MODULES):
            relative = "src/" + name.replace(".", "/") + ".py"
            pin = sha(Path(sys.modules[name].__file__).read_bytes())
            require(pin == sha((ROOT / relative).read_bytes()), "Installed session transport source differs")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = source_pins(SOURCES)
        client = CoreClient(args.core, role="core", expected_sha256=args.core_sha256, timeout_seconds=300)
        verify_rejection(args.verify, args.verify_sha256, receipt)
        protocol_campaign(args.core, args.core_sha256, receipt)
        campaign(client, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        equal(verify_binaries(args.native_root, receipt["revision"], args.platform), native, "Session binary changed during execution")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"], receipt["duration_seconds"] = len(receipt["checks"]), round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed pipeline sessions:", receipt["status"], receipt["completed_checks"], "original calls")
    return code


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in args:
        return campaign_main(args)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", required=True, action="store_true")
    for key in ("root", "native-root", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    options = parser.parse_args(args)
    result = compare(options.root, options.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_bytes(canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
