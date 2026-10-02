#!/usr/bin/env python3
"""Freeze full original independent candidate-runtime observations without changing assertions."""
from __future__ import annotations

import ast
import argparse
import os
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack
import hashlib
import importlib.util
import inspect
import io
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated/migration-next/candidate-runtime-formal-capture"
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.models.synthetic import ModelInputFrame, ModelTrace, run_model

FILES = ("tests/test_synthetic_model.py", "tests/test_synthetic_temporal_model.py",
 "tests/test_payload_requirements.py", "tests/test_temporal_generation.py",
 "tests/test_temporal_components.py", "tests/test_synthetic_generation.py",
 "tests/test_realization_checker.py", "tests/test_realization_integration.py")
METHOD_COUNTS = [23, 27, 21, 15, 15, 17, 31, 6]
KINDS = sorted(("input", "constant", "and", "or", "not", "compare", "select", "delay",
                "held_for", "onset", "pulse", "memory", "output", "any_contact"))
SOURCE_FILES = tuple(sorted(set(FILES) | {
    path.relative_to(ROOT).as_posix()
    for directory in (ROOT / "src/biocompiler", ROOT / "examples")
    for path in directory.rglob("*.py")
} | {"tests/test_semantic_matrix.py"}))
PRIMARY_PINS = {"api_calls": "ec523f966b17acc2444c8514a30a61724a562e388a5b83c355f0b82e83c04f05",
                "runs": "2792d14c94ee0530943e990d0a306bfbe2fa1dadb2fc27a9678d440c5af55fa9",
                "source_tests": "a64141cffc9b3734303caca5320a5c9b42b75e45319684744838a6d008e8d81f"}



def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def plain(value):
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "Unserializable non-string input key")
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise AssertionError(f"Uncaptured Python input type: {type(value).__module__}.{type(value).__qualname__}")


def raw_input(args, kwargs):
    # NaN/infinities are preserved as raw Python-JSON text only. They are never
    # silently replaced with null or represented as valid protocol JSON values.
    return json.dumps({"args": plain(args), "kwargs": plain(kwargs)}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, allow_nan=True)


def load(relative, suffix):
    spec = importlib.util.spec_from_file_location(Path(relative).stem + suffix, ROOT / relative)
    require(spec is not None and spec.loader is not None, "Missing test module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def inventory(module):
    tests = unittest.defaultTestLoader.loadTestsFromModule(module)
    def leaves(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                yield from leaves(child)
        else:
            yield item
    return list(leaves(tests))


def capture(child_script=None, child_context=None):
    OUT.mkdir(parents=True, exist_ok=True)
    require(child_script is not None or os.environ.get("PYTHONHASHSEED") == "0", "Set PYTHONHASHSEED=0 for reproducible capture")
    before = {path: digest((ROOT / path).read_bytes()) for path in SOURCE_FILES}
    modules = [load(path, "_candidate_capture") for path in FILES] if child_script is None else []
    expected = [path + "::" + test.id().split(".", 1)[1]
                for path, module in zip(FILES, modules) for test in inventory(module)]
    logs = io.StringIO()
    if child_script is None:
        require(len(expected) == len(set(expected)) == sum(METHOD_COUNTS), "Expected every original test method")
        require([len(inventory(module)) for module in modules] == METHOD_COUNTS, "Per-module census drift")
        baseline = unittest.TextTestRunner(stream=logs, verbosity=2).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
        require(baseline.wasSuccessful() and baseline.testsRun == sum(METHOD_COUNTS) and not baseline.skipped,
                "Uninstrumented original tests failed")
    calls, runs, ledger, programs = [], [], [], {}
    current = {"id": None, "calls": [], "runs": [], "assertion_status": "running"}
    stack = []
    fixture_contexts = {}
    child_captures = []

    def callsite():
        frame = inspect.currentframe()
        try:
            while frame is not None:
                path = Path(frame.f_code.co_filename)
                if path in [ROOT / item for item in FILES]:
                    return {"file": str(path.relative_to(ROOT)), "line": frame.f_lineno,
                            "function": frame.f_code.co_name}
                frame = frame.f_back
        finally:
            del frame
        if child_context is not None:
            return child_context["source"]
        raise AssertionError("Captured call has no original test source")

    def begin(api, args, kwargs):
        source = callsite()
        context = current if current["id"] else fixture_contexts.setdefault(
            source["file"] + "::fixture." + source["function"],
            {"id": source["file"] + "::fixture." + source["function"], "calls": [], "runs": []})
        identity = context["id"] + "/api/" + str(len(context["calls"]))
        entry = {"id": identity, "source_test": context["id"], "api": api,
                 "parent_call": stack[-1] if stack else None, "source": source,
                 "input_json": raw_input(args, kwargs)}
        calls.append(entry)
        context["calls"].append(identity)
        stack.append(identity)
        return entry

    def success(entry, value):
        document = plain(value)
        entry.update(outcome="returned", result=document, result_fingerprint=digest(canonical(document)))

    def failure(entry, error):
        entry.update(outcome="raised", error={"module": type(error).__module__,
                     "type": type(error).__qualname__, "message": str(error)})

    def constructor(cls):
        original = cls.__init__
        def observed(self, *args, **kwargs):
            entry = begin(cls.__name__ + ".__init__", args, kwargs)
            try:
                original(self, *args, **kwargs)
                success(entry, self)
            except Exception as error:
                failure(entry, error)
                raise
            finally:
                require(stack.pop() == entry["id"], "Constructor call stack corrupted")
        return observed

    def classmethod_wrapper(cls, name):
        original = getattr(cls, name).__func__
        def observed(_cls, *args, **kwargs):
            entry = begin(_cls.__name__ + "." + name, args, kwargs)
            try:
                result = original(_cls, *args, **kwargs)
                success(entry, result)
                return result
            except Exception as error:
                failure(entry, error)
                raise
            finally:
                require(stack.pop() == entry["id"], "Import call stack corrupted")
        return classmethod(observed)

    def observed_run(program, history, **kwargs):
        # All retained callers supply concrete histories. Fail rather than consume
        # an iterator before the original runner or alter its evaluation order.
        require(isinstance(history, (tuple, list)), "Nonconcrete history needs separately reviewed capture")
        require(set(kwargs) <= {"until"}, "Unknown runtime option needs reviewed capture")
        until = kwargs.get("until")
        entry = begin("run_model", (program, history), kwargs)
        program_doc = plain(program)
        identity = digest(canonical(program_doc))
        require(program.fingerprint == identity, "Mechanism identity mismatch")
        programs.setdefault(identity, {"id": identity, "program": program_doc})
        context = current if current["id"] else fixture_contexts[entry["source_test"]]
        run = {"id": context["id"] + "/run/" + str(len(context["runs"])),
               "source_test": context["id"], "api_call": entry["id"], "program_id": identity,
               "history": plain(history), "until": until, "until_supplied": "until" in kwargs}
        runs.append(run)
        context["runs"].append(run["id"])
        try:
            result = run_model(program, history, **kwargs)
            success(entry, result)
            run.update(outcome="returned", trace=entry["result"], trace_fingerprint=entry["result_fingerprint"])
            return result
        except Exception as error:
            failure(entry, error)
            run.update(outcome="raised", error=entry["error"])
            raise
        finally:
            require(stack.pop() == entry["id"], "Runner call stack corrupted")

    class RecordedResult(unittest.TextTestResult):
        def startTest(self, test):
            relative = FILES[modules.index(sys.modules[type(test).__module__])]
            current.update(id=relative + "::" + test.id().split(".", 1)[1], calls=[], runs=[],
                           assertion_status="passed")
            super().startTest(test)
        def addFailure(self, test, err):
            current["assertion_status"] = "failed"
            super().addFailure(test, err)
        def addError(self, test, err):
            current["assertion_status"] = "error"
            super().addError(test, err)
        def addSubTest(self, test, subtest, err):
            if err is not None:
                current["assertion_status"] = "failed_subtest"
            super().addSubTest(test, subtest, err)
        def stopTest(self, test):
            ledger.append({"id": current["id"], "assertion_status": current["assertion_status"],
                           "api_calls": list(current["calls"]), "run_calls": list(current["runs"])})
            require(not stack, "Unclosed call after test")
            current["id"] = None
            super().stopTest(test)

    with ExitStack() as patches:
        for cls in (MechanismNode, MechanismProgram, ModelInputFrame, ModelTrace):
            patches.enter_context(patch.object(cls, "__init__", constructor(cls)))
            for method in ("from_dict", "from_json"):
                if hasattr(cls, method):
                    patches.enter_context(patch.object(cls, method, classmethod_wrapper(cls, method)))
        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            for name, value in tuple(vars(module).items()):
                if value is run_model and module is not sys.modules[__name__]:
                    patches.enter_context(patch.object(module, name, observed_run))
        if child_script is None:
            original_subprocess = subprocess.run
            def observed_subprocess(command, *args, **kwargs):
                require(isinstance(command, list) and len(command) == 3 and command[:2] == [sys.executable, "-c"],
                        "Unreviewed subprocess capture shape")
                context = {"id": current["id"] + "/subprocess/" + str(len(child_captures)), "source": callsite()}
                with tempfile.TemporaryDirectory(prefix="candidate-runtime-capture-") as directory:
                    output = Path(directory) / "capture.json"
                    bootstrap = ("from tools.freeze_candidate_runtime import child_main; child_main(" + repr(command[2]) + ", " + repr(context) + ", " + repr(str(output)) + ")")
                    result = original_subprocess([*command[:2], bootstrap], *args, **kwargs)
                    require(output.exists(), "Child capture did not complete")
                    child = json.loads(output.read_text())
                    child["invocation"] = {"id": context["id"], "source_test": current["id"], "source": context["source"],
                                           "script": command[2], "hash_seed": kwargs["env"]["PYTHONHASHSEED"],
                                           "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
                    child_captures.append(child)
                    return result
            patches.enter_context(patch.object(subprocess, "run", observed_subprocess))
            captured = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=RecordedResult).run(
                unittest.TestSuite(test for module in modules for test in inventory(module)))
        else:
            current.update(id=child_context["id"], calls=[], runs=[], assertion_status="passed")
            exec(compile(child_script, "<string>", "exec"), {"__name__": "__main__"})
            ledger.append({"id": current["id"], "assertion_status": "passed", "api_calls": list(current["calls"]),
                           "run_calls": list(current["runs"])})
            require(not stack, "Unclosed child API calls")
    if child_script is not None:
        return {"source_tests": ledger, "programs": list(programs.values()), "runs": runs, "api_calls": calls}
    (OUT / "original-tests.log").write_text(logs.getvalue())
    require(captured.wasSuccessful() and captured.testsRun == sum(METHOD_COUNTS) and not captured.skipped,
            "Instrumented original tests failed; see original-tests.log")
    require([entry["id"] for entry in ledger] == expected, "Missing, duplicate or reordered test ledger")
    require(before == {path: digest((ROOT / path).read_bytes()) for path in SOURCE_FILES}, "Source changed during capture")
    require(len({entry["id"] for entry in calls}) == len(calls), "Duplicate API call ID")
    require(len({entry["id"] for entry in runs}) == len(runs), "Duplicate runtime call ID")
    require(all(entry["assertion_status"] == "passed" for entry in ledger), "Failed original assertion")
    for child in child_captures:
        calls.extend(child["api_calls"])
        runs.extend(child["runs"])
        for record in child["programs"]:
            programs.setdefault(record["id"], record)
    require(len({entry["id"] for entry in calls}) == len(calls), "Duplicate child API call ID")
    require(len({entry["id"] for entry in runs}) == len(runs), "Duplicate child runtime call ID")
    # Replay every captured runtime input after all patches are removed. This is
    # consistency evidence only; the implementation remains the Python oracle.
    for entry in runs:
        program = MechanismProgram.from_dict(programs[entry["program_id"]]["program"])
        history = [ModelInputFrame.from_dict(frame) for frame in entry["history"]]
        try:
            result = run_model(program, history, **({"until": entry["until"]} if entry["until_supplied"] else {}))
        except Exception as error:
            require(entry["outcome"] == "raised" and entry["error"] == {
                "module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)},
                "Serialized runtime rejection changed: " + entry["id"])
        else:
            require(entry["outcome"] == "returned" and canonical(result.to_dict()) == canonical(entry["trace"]),
                    "Serialized complete runtime trace changed: " + entry["id"])
    kinds = sorted({node["kind"] for record in programs.values() for node in record["program"]["nodes"]})
    successful_kinds = sorted({node["kind"] for run in runs if run["outcome"] == "returned"
                              for node in programs[run["program_id"]]["program"]["nodes"]})
    coverage = {"original_methods": len(ledger), "per_module_methods": METHOD_COUNTS,
                "run_calls": len(runs), "run_outcomes": dict(sorted(Counter(run["outcome"] for run in runs).items())),
                "api_calls": len(calls), "api_outcomes": dict(sorted(Counter(call["outcome"] for call in calls).items())),
                "distinct_programs": len(programs), "supported_kinds": KINDS, "supplied_run_kinds": kinds,
                "successful_run_kinds": successful_kinds,
                "unexecuted_kinds": sorted(set(KINDS) - set(kinds)),
                "methods_without_runtime_call": [entry["id"] for entry in ledger if not entry["run_calls"]],
                "api_census": dict(sorted(Counter(call["api"] for call in calls).items()))}
    document = {"schema_version": "biocompiler.candidate_runtime_baseline_capture.v1",
                "claim_scope": "Original Python assertions and complete observed API outcomes only; no native parity, independent new oracle, biological evidence or acceptance authority.",
                "source_files": [{"path": path, "sha256": value} for path, value in sorted(before.items())],
                "source_tests": ledger, "subprocesses": [{"invocation": child["invocation"], "contexts": child["source_tests"]} for child in child_captures], "fixture_contexts": list(fixture_contexts.values()), "programs": list(programs.values()), "runs": runs, "api_calls": calls,
                "coverage": coverage,
                "capture_policy": {"original_assertions": "executed unchanged, both uninstrumented and instrumented",
                    "raw_nonfinite_inputs": "stored in input_json strings with original Python JSON NaN/Infinity tokens",
                    "api_wrappers": "observe constructor/import/runner inputs and results; return exact original object or re-raise original exception",
                    "nested_calls": "parent_call preserves imports and internal trace constructor calls, not independent extra test cases",
                    "source_paths": "relative file/line/function; no production normalization"}}
    payload = (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    (OUT / "capture.json").write_bytes(payload)
    receipt = {"capture_file": "capture.json", "bytes": len(payload), "sha256": digest(payload),
               "canonical_fingerprint": digest(canonical(document)), "generator_sha256": digest(Path(__file__).read_bytes()),
               "python": sys.version, "platform": platform.platform(), "baseline_tests": baseline.testsRun,
               "captured_tests": captured.testsRun, "serialized_runtime_replays": len(runs), "coverage": coverage}
    (OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in ("bytes", "sha256", "baseline_tests", "captured_tests", "serialized_runtime_replays")}, sort_keys=True))
    return document


def child_main(script, context, output):
    import biocompiler.frontend.graph as graph
    source_location = graph.SourceLocation
    def portable(file, line, function):
        path = Path(file)
        return source_location(path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file, line, function)
    with patch.object(graph, "SourceLocation", portable):
        result = capture(script, context)
    Path(output).write_bytes(canonical(result))

CORPUS = ROOT / "tests/conformance/candidate-runtime-v1.json"
SCHEMA = "biocompiler.candidate_runtime_conformance.v1"
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def runtime_code(message):
    if message.startswith("Model history"): return "synthetic_history"
    if message.startswith("Input snapshot"): return "synthetic_input_inventory"
    if message.startswith("Input '"): return "synthetic_input_type"
    if "duration must advance" in message or "deadline must be finite" in message: return "synthetic_deadline"
    raise AssertionError("Unclassified original runtime diagnostic: " + message)


def constructor_document(api, raw):
    fields, defaults = {
        "MechanismNode": (["id", "kind", "output", "inputs", "attributes", "requirement_ids"],
                          {"inputs": [], "attributes": {}, "requirement_ids": []}),
        "MechanismProgram": (["name", "nodes", "outputs", "required_capabilities", "schema_version"],
                             {"required_capabilities": [], "schema_version": "biocompiler.mechanism.synthetic.v0.2"}),
        "ModelInputFrame": (["time", "values", "contacts"], {"values": {}, "contacts": {}}),
        "ModelTrace": (["frames", "horizon", "program_fingerprint", "model_version"],
                       {"model_version": "biocompiler.synthetic.runner.v0.2"}),
    }[api]
    require(len(raw["args"]) <= len(fields), "Unknown positional constructor argument")
    result = {**defaults, **dict(zip(fields, raw["args"]))}
    require(not (set(fields[:len(raw["args"])]) & set(raw["kwargs"])), "Duplicate constructor argument")
    require(set(raw["kwargs"]) <= set(fields), "Unknown constructor keyword")
    result.update(raw["kwargs"])
    require(set(result) == set(fields), "Missing constructor argument")
    if api == "ModelTrace": result["schema_version"] = "biocompiler.synthetic.trace.v0.1"
    return result


def domain_code(api, document, message):
    if message.startswith("Duplicate JSON key:"): return "duplicate_key"
    if message.startswith("Invalid JSON number:") or message == "Signal value must be finite.": return "invalid_json"
    if api == "MechanismNode":
        if "typed Duration: A serialized binding must be an object" in message: return "invalid_type"
        if "canonical value disagrees" in message: return "canonical_value_mismatch"
        if "typed Duration: Expected Duration, got Level" in message: return "type_mismatch"
        if "duration must be positive" in message: return "invalid_measurement_contract"
        if message.startswith("Invalid attributes for"): return "unknown_field"
        if "values require a typed literal with units" in message: return "invalid_mechanism_node"
    if api == "MechanismProgram":
        if message == "Invalid mechanism program fields.": return "unknown_field"
        if message == "Unsupported mechanism schema version.":
            return "unsupported_schema" if isinstance(document["schema_version"], str) else "invalid_type"
        if message.endswith("must be an array.") or message == "Mechanism program name must be a nonempty string.":
            return "invalid_type"
        graph_errors = {
            "A mechanism program requires a nonempty node array.",
            "A mechanism program requires at least one output.",
            "Mechanism graph contains a dependency cycle.",
            "The synthetic profile represents one executing cell role per program.",
            "Unknown input reference on delay.",
        }
        node_errors = {
            "Temporal operators require Boolean ports.",
            "Trigger requires onset or explicit any_contact aggregation of onsets.",
            "Memory requires cell scope.",
            "Contact-to-cell flow requires explicit any_contact aggregation.",
            "Cross-compartment edges require an unimplemented transport model.",
            "Comparison operands have incompatible dimensions.",
            "Event values require a pulse/memory trigger or any_contact aggregation; they cannot serve as continuous level signals.",
        }
        if message in graph_errors or (": " in message and message.split(": ", 1)[1] in node_errors):
            return "invalid_mechanism"
    if api == "ModelTrace" and message == "Unsupported synthetic model runner version.": return "invalid_model_trace"
    raise AssertionError("Unclassified original domain diagnostic: " + api + ": " + message)


def native_observation(call, retain):
    if call["api"] == "run_model": return {"operation": "run_model", "runtime_case": call["id"]}
    api, method = call["api"].split(".")
    raw = json.loads(call["input_json"])
    if method == "__init__":
        document = constructor_document(api, raw)
        text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
    else:
        require(method in ("from_dict", "from_json") and len(raw["args"]) == 1 and not raw["kwargs"], "Unknown import signature")
        document = raw["args"][0]
        text = document if method == "from_json" else json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
        if method == "from_json":
            try: document = json.loads(text)
            except ValueError: document = None
    raw_boundary = "NaN" in text or "Infinity" in text
    code = None if call["outcome"] == "returned" else domain_code(api, document, call["error"]["message"])
    return {"operation": {"MechanismNode": "node", "MechanismProgram": "program", "ModelInputFrame": "input_frame",
                           "ModelFrame": "frame", "ModelTrace": "trace"}[api],
            "input": retain("json_text", text), "expected_code": code,
            "source_stage": "constructor" if method == "__init__" else "json_import" if method == "from_json" else "record_import",
            "native_stage": "wire" if raw_boundary or code == "duplicate_key" else "domain",
            "compatibility": "nonfinite_python_values_rejected_at_strict_json_boundary" if raw_boundary else "complete_record_codec"}


def static_ledger():
    patches, calls = [], []
    tracked = {"run_model", "run_component_model", "check_realization", "reconstruct_component_mechanism"}
    for path in FILES:
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call): continue
            name = ast.unparse(node.func)
            if name.split(".")[-1] in tracked:
                calls.append({"file": path, "line": node.lineno, "call": name})
            if name == "patch":
                require(node.args and isinstance(node.args[0], ast.Constant), "Unclassified monkeypatch")
                target = node.args[0].value
                if target in ("biocompiler.semantics.evaluator.evaluate", "biocompiler.synthesis.components.adapt_synthetic_components"):
                    disposition = "original_independence_assertion_retained; native_dependency_gate_and_literal_tests_are_counterpart"
                elif target == "biocompiler.semantics.payload_requirements.extract_payload_requirements":
                    disposition = "original_import_independence_assertion_retained; outside_candidate_runtime_semantics"
                elif target == "biocompiler.verification.realization.CHECKER_VERSION":
                    disposition = "original_checker_staleness_assertion_retained; outside_candidate_runtime_semantics"
                else: raise AssertionError("Unclassified monkeypatch target: " + target)
                patches.append({"file": path, "line": node.lineno, "target": target, "disposition": disposition})
    return {"source_callsites": sorted(calls, key=lambda x: (x["file"], x["line"])),
            "monkeypatches": sorted(patches, key=lambda x: (x["file"], x["line"]))}


def freeze(document, *, check=False):
    documents, kinds = {}, {}
    def retain(kind, value):
        payload = canonical(value) + b"\n"
        require(len(payload) <= 16 * 1024 * 1024, "Individual conformance document exceeds native wire bound")
        identity = digest(canonical(value))
        require(identity not in kinds or kinds[identity] == kind, "Cross-kind document collision")
        kinds[identity] = kind; documents[identity] = payload
        return identity
    calls_by_context = {}
    for original in document["api_calls"]:
        call = dict(original)
        call["native"] = native_observation(call, retain)
        call["input"] = retain("raw_arguments", call.pop("input_json"))
        if call["outcome"] == "returned":
            identity = retain("record", call.pop("result"))
            require(identity == call.pop("result_fingerprint"), "Captured API result identity changed")
            call["result"] = identity
        calls_by_context.setdefault(call["source_test"], []).append(call)
    contexts = []
    for method in document["source_tests"]:
        contexts.append({**method, "kind": "original_method"})
    for fixture in document["fixture_contexts"]:
        contexts.append({"id": fixture["id"], "api_calls": fixture["calls"], "run_calls": fixture["runs"],
                         "assertion_status": "passed", "kind": "class_fixture"})
    for child in document["subprocesses"]:
        for context in child["contexts"]: contexts.append({**context, "kind": "original_subprocess"})
    for context in contexts:
        observed = calls_by_context.get(context["id"], [])
        require([call["id"] for call in observed] == context["api_calls"], "Context lost observed API calls")
        context["ledger"] = retain("api_ledger", observed)
        context["api_calls"] = len(context["api_calls"])
    programs = {record["id"]: record["program"] for record in document["programs"]}
    runs = []
    for original in document["runs"]:
        run = dict(original)
        run["program"] = retain("record", programs[run.pop("program_id")])
        run["input"] = retain("runtime_input", {key: run.pop(key) for key in ("history", "until", "until_supplied")})
        if run["outcome"] == "returned":
            run["expected"] = retain("record", run.pop("trace"))
            require(run["expected"] == run.pop("trace_fingerprint"), "Captured trace identity changed")
            run["expected_code"] = None
        else:
            run["expected"] = None; run["expected_code"] = runtime_code(run["error"]["message"])
        runs.append(run)
    primary_calls = [x for x in document["api_calls"] if x["source_test"].split("::")[0] in FILES[:2]]
    primary_runs = [x for x in document["runs"] if x["source_test"].split("::")[0] in FILES[:2]]
    require(len(primary_calls) == 727 and len(primary_runs) == 55, "Original complete baseline changed")
    for key, pin in PRIMARY_PINS.items():
        subset = [entry for entry in document[key] if entry["id" if key == "source_tests" else "source_test"].split("::")[0] in FILES[:2]]
        require(digest(canonical(subset)) == pin, "Complete original baseline changed: " + key)
    require(document["coverage"]["successful_run_kinds"] == KINDS, "Missing successful operation witness")
    coverage = {**document["coverage"], "original_primary_methods": 50, "original_primary_api_calls": len(primary_calls),
                "original_primary_runs": len(primary_runs), "original_primary_pins": PRIMARY_PINS, "contexts": len(contexts),
                "domain_observations": len(document["api_calls"]) - len(runs),
                "domain_outcomes": dict(sorted(Counter(x["outcome"] for x in document["api_calls"] if x["api"] != "run_model").items())),
                "native_stages": dict(sorted(Counter(x["native"].get("native_stage", "runtime") for v in calls_by_context.values() for x in v).items())),
                "native_operations": dict(sorted(Counter(x["native"]["operation"] for v in calls_by_context.values() for x in v).items())),
                "subprocess_invocations": len(document["subprocesses"]), "unclassified_observations": 0}
    index = {"schema_version": SCHEMA, "claim_scope": "independent_synthetic_candidate_execution_only_no_biological_evidence",
             "source_files": document["source_files"], "source_ledger": static_ledger(), "contexts": contexts,
             "subprocesses": [child["invocation"] for child in document["subprocesses"]], "runs": runs,
             "documents": [{"id": identity, "kind": kinds[identity], "bytes": len(payload)} for identity, payload in sorted(documents.items())],
             "coverage": coverage,
             "compatibility": {"native_resource_profile": "biocompiler.synthetic.resources.v1", "native_resource_exhaustion": "no_partial_trace",
                "runtime_failures": "exact_legacy_message_and_explicit_native_code", "domain_failures": "original_python_type_message_retained; explicit_native_diagnostic_code",
                "nonfinite_inputs": "original raw Python-JSON text retained; native wire rejects NaN/Infinity before domain construction",
                "constructors": "captured signature arguments with explicit legacy defaults; nested typed records retain full serialized content",
                "numeric_identity": "canonical JSON preserves booleans, integer tokens, float tokens and signed zero; no numeric equality normalization",
                "monkeypatches": "actual original assertions run; never projected into invented serialized mutation",
                "source_paths": "relative locations established before in-process and child source construction; actual observed child stdout retained"}}
    index["inventory_fingerprint"] = digest(canonical(index))
    payload = canonical(index) + b"\n"
    total = len(payload) + sum(map(len, documents.values()))
    require(total <= MAX_TOTAL_BYTES, "Complete retained corpus exceeds reviewed storage ceiling")
    directory = CORPUS.with_suffix("")
    if check:
        require(CORPUS.read_bytes() == payload, "Fresh complete capture differs from pinned index")
        require({p.name for p in directory.iterdir()} == {identity + ".json" for identity in documents}, "Missing or extra retained document")
        for identity, value in documents.items(): require((directory / (identity + ".json")).read_bytes() == value, "Fresh retained document differs")
    else:
        require(not directory.exists() or not any(directory.iterdir()), "Refuse to overwrite an existing corpus; use --check or an explicitly new output")
        directory.mkdir(parents=True, exist_ok=True)
        for identity, value in documents.items(): (directory / (identity + ".json")).write_bytes(value)
        CORPUS.write_bytes(payload)
    print(json.dumps({"inventory_fingerprint": index["inventory_fingerprint"], "documents": len(documents), "bytes": total, "runs": len(runs), "api_calls": coverage["api_calls"]}, sort_keys=True))
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recapture all original assertions and compare every byte")
    parser.add_argument("--captured", type=Path, help="use an already captured complete observation file (development only)")
    args = parser.parse_args()
    import biocompiler.frontend.graph as graph
    source_location = graph.SourceLocation
    def portable(file, line, function):
        path = Path(file)
        return source_location(path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file, line, function)
    with patch.object(graph, "SourceLocation", portable):
        document = json.loads(args.captured.read_text()) if args.captured else capture()
    freeze(document, check=args.check)


if __name__ == "__main__":
    main()
