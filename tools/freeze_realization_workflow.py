#!/usr/bin/env python3
"""Freeze every original whole-workflow observation and evaluator invocation.

The profile is isolated from prior frozen corpora. Original assertions execute
before and during capture, including the omitted complete 625-history campaign.
Callbacks remain executable only in the original tests; fixtures retain their
source identity and complete ordered argument/result/error transcripts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
import functools
import inspect
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from tools import freeze_synthetic_producers as previous
from tools.freeze_component_runtime import canonical, digest, require, load, inventory
from biocompiler.verification import exploration as exploration
from biocompiler.compiler import verification_workflow as workflow
from biocompiler import cli
from biocompiler.verification import realization

BASE = previous.foundation
FILES = (*BASE.FILES, "tests/test_verification_campaign.py")
METHOD_COUNTS = [*BASE.METHOD_COUNTS, 3]
WORKFLOW_CLASSES = (workflow.SyntheticVerificationRequest, workflow.SyntheticVerificationRecord,
    exploration.BooleanObservation, exploration.BooleanContactConfig, exploration.BooleanInputConfig,
    exploration.ExplorationReport, exploration.BooleanInputExplorationReport,
    exploration.FailureSignature, exploration.ReductionResult,
    exploration.AdversarialConfig, exploration.HistoryCase)
CLASSES = (*BASE.CLASSES, *WORKFLOW_CLASSES)
CLASS_BY_NAME = {cls.__name__: cls for cls in CLASSES}
SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in CLASSES}
CLASS_IMPORT_METHODS = {exploration.FailureSignature: ("from_counterexample", "from_diagnostic")}
METHODS = {**BASE.METHODS, exploration.FailureSignature: ("matches",)}
WORKFLOW_FUNCTIONS = (workflow.run_synthetic_verification, workflow.replay_synthetic_verification,
    exploration.enumerate_boolean_histories, exploration.explore_boolean_histories,
    exploration.reduce_counterexample, exploration.generate_adversarial_histories,
    exploration.boolean_config_from_dict)
FUNCTIONS = (*BASE.FUNCTIONS, *WORKFLOW_FUNCTIONS)
PROPERTY_NAMES = BASE.PROPERTY_NAMES
WORKFLOW_PROPERTIES = ("fingerprint", "state_count", "possible_histories", "evaluated_histories",
    "complete", "all_passed", "outcome_counts", "coverage_totals", "shared_dependencies")
CHILD_MODULE = "tools.freeze_realization_workflow"
OUT = ROOT / "generated/migration-next/realization-workflow-capture"
CORPUS = ROOT / "tests/conformance/realization-workflow-v1.json"
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
PRIOR_PIN = "2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b"
PORTABLE_TEMP = Path("/tmp/biocompiler-workflow-conformance-v1")
portable_sources = BASE.portable_sources
python_types = BASE.python_types


def callback_identity(value):
    """Record source rather than executable closures or address-bearing reprs."""
    original = getattr(value, "__workflow_original__", value)
    require(inspect.isfunction(original), "New callback kind needs explicit source capture")
    code = original.__code__
    path = Path(code.co_filename).resolve()
    require(path.is_relative_to(ROOT), "Callback source must be in the pinned repository")
    text = inspect.getsource(original)
    return {"module": original.__module__, "qualname": original.__qualname__,
        "file": path.relative_to(ROOT).as_posix(), "line": code.co_firstlineno,
        "source": text, "source_sha256": digest(text.encode()),
        "free_variables": list(code.co_freevars),
        "closure_policy": "complete_each_invocation_inputs_results_and_errors_no_executable_closure_import"}


def plain(value):
    if inspect.isfunction(value):
        return {"__workflow_callback__": callback_identity(value)}
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return previous.plain(value)


class Store:
    def __init__(self):
        self.records = {}; self.size = 0

    def retain(self, kind, value):
        payload = canonical(value)
        require(len(payload) + 1 <= MAX_DOCUMENT_BYTES, "Workflow document exceeds reviewed 64 MiB bound")
        identity = digest(payload)
        if identity in self.records:
            require(self.records[identity]["kind"] == kind, "Cross-kind workflow document collision")
        else:
            self.records[identity] = {"kind": kind, "value": value}
            self.size += len(payload) + 1
            require(self.size <= MAX_TOTAL_BYTES, "Workflow documents exceed reviewed 512 MiB bound")
        return identity


def source_inventory():
    paths = set(FILES)
    for directory in (ROOT / "src/biocompiler", ROOT / "examples"):
        paths.update(path.relative_to(ROOT).as_posix() for path in directory.rglob("*.py"))
    return [{"path": path, "sha256": digest((ROOT / path).read_bytes())} for path in sorted(paths)]


@contextmanager
def portable_temporary_directories():
    """Choose stable paths before execution; retain original CLI bytes verbatim."""
    PORTABLE_TEMP.mkdir()  # Exclusive: never remove or reuse another process's data.
    counter = 0
    class Directory:
        def __init__(self, suffix=None, prefix=None, dir=None, **options):
            nonlocal counter
            require(not options, "New TemporaryDirectory options need reviewed capture")
            counter += 1
            parent = Path(dir) if dir is not None else PORTABLE_TEMP
            self.name = str(parent / ((prefix or "tmp") + f"workflow-{counter:06d}" + (suffix or "")))
            Path(self.name).mkdir()
            self._closed = False
        def __enter__(self): return self.name
        def cleanup(self):
            if not self._closed:
                shutil.rmtree(self.name); self._closed = True
        def __exit__(self, *unused): self.cleanup()
    try:
        with patch.object(tempfile, "TemporaryDirectory", Directory): yield
    finally:
        # This exclusive parent contains only directories created by this scope.
        shutil.rmtree(PORTABLE_TEMP)


class Tee:
    def __init__(self, target): self.target = target; self.value = io.StringIO()
    def write(self, text): self.value.write(text); return self.target.write(text)
    def flush(self): self.target.flush()
    def __getattr__(self, name): return getattr(self.target, name)


def capture(child_script=None, child_context=None):
    require(child_script is not None or os.environ.get("PYTHONHASHSEED") == "0",
            "Set PYTHONHASHSEED=0 for reproducible parent capture")
    OUT.mkdir(parents=True, exist_ok=True)
    modules = [load(path) for path in FILES] if child_script is None else []
    sources = source_inventory()
    expected = [path + "::" + test.id().split(".", 1)[1]
        for path, module in zip(FILES, modules) for test in inventory(module)]
    log_path = OUT / "original-tests.log"
    if child_script is None:
        require([len(inventory(module)) for module in modules] == METHOD_COUNTS, "Original realization census drift")
        require(len(expected) == len(set(expected)) == sum(METHOD_COUNTS), "Missing or duplicate original realization test")
        with portable_temporary_directories(), log_path.open("w") as logs:
            baseline = unittest.TextTestRunner(stream=logs, verbosity=2).run(unittest.TestSuite(
                test for module in modules for test in inventory(module)))
        require(baseline.wasSuccessful() and baseline.testsRun == sum(METHOD_COUNTS) and not baseline.skipped,
                "Uninstrumented original assertions failed: " + str(log_path))
        print(f"workflow capture: all {sum(METHOD_COUNTS)} uninstrumented original methods passed", flush=True)
    store, calls, ledger, fixtures, children = Store(), [], [], {}, []
    current = {"id": child_context["id"] if child_context else None, "api_calls": [],
               "assertion_status": "passed", "kind": "subprocess" if child_context else "original_method"}
    stack = []
    serializing = [False]
    selected_paths = {str(ROOT / path): path for path in FILES}

    def callsite():
        frame = inspect.currentframe()
        try:
            while frame is not None:
                if frame.f_code.co_filename in selected_paths:
                    return {"file": selected_paths[frame.f_code.co_filename], "line": frame.f_lineno,
                            "function": frame.f_code.co_name}
                frame = frame.f_back
        finally: del frame
        if child_context is not None: return child_context["source"]
        raise AssertionError("Observed realization call has no original test source")

    def begin(api, args, kwargs):
        source = callsite()
        context = current if current["id"] else fixtures.setdefault(
            source["file"] + "::fixture." + source["function"],
            {"id": source["file"] + "::fixture." + source["function"], "api_calls": [],
             "assertion_status": "passed", "kind": "class_fixture"})
        identity = context["id"] + "/api/" + str(len(context["api_calls"]))
        serializing[0] = True
        try: raw = {"args": plain(args), "kwargs": plain(kwargs)}
        finally: serializing[0] = False
        raw_text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
        entry = {"id": identity, "source_test": context["id"], "api": api, "source": source,
            "parent_call": stack[-1] if stack else None, "input": store.retain("raw_arguments", raw_text),
            "python_types": python_types({"args": args, "kwargs": kwargs})}
        if realization.CHECKER_VERSION != previous.CHECKER_VERSION:
            entry["policy_override"] = {"checker_version": realization.CHECKER_VERSION}
        calls.append(entry); context["api_calls"].append(identity); stack.append(identity)
        return entry

    def success(entry, value):
        serializing[0] = True
        try: _success(entry, value)
        finally: serializing[0] = False

    def _success(entry, value):
        raw = plain(value)
        try:
            identity = store.retain("record", raw)
            representation = "record"
        except UnicodeEncodeError:
            # Some Python evidence leaves allow lone surrogates until a later
            # enclosing workflow rejects UTF-8. Preserve that actual return,
            # without claiming it can cross the stricter native wire boundary.
            representation = "python_json_text"
            identity = store.retain(representation, json.dumps(raw, sort_keys=True,
                separators=(",", ":"), ensure_ascii=True, allow_nan=False))
        entry.update(outcome="returned", result=identity, result_format=representation)
        if isinstance(value, CLASSES):
            properties = {}
            for name in (WORKFLOW_PROPERTIES if isinstance(value, WORKFLOW_CLASSES) else PROPERTY_NAMES):
                if hasattr(type(value), name):
                    properties[name] = plain(getattr(value, name))
            if properties: entry["properties"] = store.retain("record", properties)

    def failure(entry, error):
        entry.update(outcome="raised", error={"module": type(error).__module__,
            "type": type(error).__qualname__, "message": str(error)})

    def constructor(cls):
        original = cls.__init__
        def observed(self, *args, **kwargs):
            if serializing[0]: return original(self, *args, **kwargs)
            entry = begin(cls.__name__ + ".__init__", args, kwargs)
            try:
                original(self, *args, **kwargs); success(entry, self)
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Constructor stack corruption")
        return observed

    def importer(cls, method):
        original = getattr(cls, method).__func__
        def observed(actual_cls, *args, **kwargs):
            if serializing[0]: return original(actual_cls, *args, **kwargs)
            entry = begin(actual_cls.__name__ + "." + method, args, kwargs)
            try:
                result = original(actual_cls, *args, **kwargs); success(entry, result); return result
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Import stack corruption")
        return classmethod(observed)

    def callback(parent, original):
        @functools.wraps(original)
        def observed(*args, **kwargs):
            entry = begin("workflow.callback", args, kwargs)
            entry["callback_parent"] = parent["id"]
            entry["callback_identity"] = store.retain("callback_identity", callback_identity(original))
            parent.setdefault("callback_calls", []).append(entry["id"])
            try:
                result = original(*args, **kwargs); success(entry, result); return result
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Callback stack corruption")
        observed.__workflow_original__ = original
        return observed

    def function(api, original):
        @functools.wraps(original)
        def observed(*args, **kwargs):
            if serializing[0]: return original(*args, **kwargs)
            entry = begin(api, args, kwargs)
            try:
                if api in {"explore_boolean_histories", "reduce_counterexample"}:
                    bound = inspect.signature(original).bind(*args, **kwargs)
                    evaluator = bound.arguments["evaluate"]
                    if inspect.isfunction(evaluator):
                        bound.arguments["evaluate"] = callback(entry, evaluator)
                    # Wrong nominal callback arguments must fail in original code.
                    result = original(*bound.args, **bound.kwargs)
                else: result = original(*args, **kwargs)
                if api == "enumerate_boolean_histories":
                    entry.update(outcome="iterator", yields=[], iterator_state="created")
                    return observed_iterator(entry, result)
                success(entry, result); return result
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Function stack corruption")
        return observed

    def observed_iterator(entry, iterator):
        # Original generator creation remains lazy. Each next/throw/close is
        # forwarded; yielded frame objects are returned unchanged.
        class ObservedIterator:
            def __iter__(self): return self
            def __next__(self): return self.send(None)
            def send(self, value): return self._advance("send", value)
            def throw(self, *args): return self._advance("throw", *args)
            def _advance(self, method, *args):
                stack.append(entry["id"])
                try:
                    value = getattr(iterator, method)(*args)
                    entry["yields"].append(store.retain("record", plain(value)))
                    entry["iterator_state"] = "suspended"
                    return value
                except StopIteration as stopped:
                    entry["iterator_state"] = "exhausted"
                    entry["return_value"] = store.retain("record", plain(stopped.value))
                    raise
                except Exception as error:
                    entry["iterator_state"] = "raised"
                    entry["iteration_error"] = {"module": type(error).__module__,
                        "type": type(error).__qualname__, "message": str(error)}
                    raise
                finally: require(stack.pop() == entry["id"], "Iterator stack corruption")
            def close(self):
                iterator.close(); entry["iterator_state"] = "closed"
        return ObservedIterator()

    def cli_function(original):
        @functools.wraps(original)
        def observed(argv=None):
            values = list(sys.argv[1:] if argv is None else argv)
            eligible = bool(values) and values[0] in {
                "synthetic-check", "synthetic-explore", "synthetic-reduce", "synthetic-replay"}
            if values and values[0] == "inspect" and len(values) >= 2:
                try: candidate = json.loads(Path(values[1]).read_bytes())
                except (OSError, ValueError): candidate = {}
                eligible = candidate.get("schema_version") in {cls.schema_version for cls in WORKFLOW_CLASSES}
            if not eligible: return original(argv)
            entry = begin("workflow.cli", (values,), {})
            if isinstance(cli.os.replace, unittest.mock.Mock):
                error = cli.os.replace.side_effect
                require(isinstance(error, OSError), "New CLI publication mutation needs explicit capture")
                entry["publication_override"] = {"operation": "os.replace", "error": {
                    "module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}}
            def files():
                result = {}
                for item in values[1:]:
                    path = Path(item)
                    if path.is_file():
                        payload = path.read_bytes()
                        require(len(payload) <= MAX_DOCUMENT_BYTES, "CLI input/output exceeds capture bound")
                        result[item] = {"bytes": len(payload), "sha256": digest(payload),
                            "text": payload.decode("utf-8")}
                return result
            entry["files_before"] = store.retain("cli_files", files())
            stdout, stderr = Tee(sys.stdout), Tee(sys.stderr)
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr): result = original(argv)
                success(entry, result); return result
            except BaseException as error:
                failure(entry, error); raise
            finally:
                entry["stdout"] = store.retain("cli_text", stdout.value.getvalue())
                entry["stderr"] = store.retain("cli_text", stderr.value.getvalue())
                entry["files_after"] = store.retain("cli_files", files())
                require(stack.pop() == entry["id"], "CLI stack corruption")
        return observed

    class RecordedResult(unittest.TextTestResult):
        def startTest(self, test):
            path = FILES[modules.index(sys.modules[type(test).__module__])]
            current.update(id=path + "::" + test.id().split(".", 1)[1], api_calls=[],
                           assertion_status="passed", kind="original_method")
            super().startTest(test)
        def addFailure(self, test, error):
            current["assertion_status"] = "failed"; super().addFailure(test, error)
        def addError(self, test, error):
            current["assertion_status"] = "error"; super().addError(test, error)
        def addSubTest(self, test, subtest, error):
            if error is not None: current["assertion_status"] = "failed_subtest"
            super().addSubTest(test, subtest, error)
        def stopTest(self, test):
            ledger.append(dict(current)); require(not stack, "Unclosed observed API call")
            current["id"] = None; super().stopTest(test)

    with ExitStack() as patches:
        for cls in CLASSES:
            patches.enter_context(patch.object(cls, "__init__", constructor(cls)))
            for method in ("from_dict", "from_json", *CLASS_IMPORT_METHODS.get(cls, ())):
                if hasattr(cls, method): patches.enter_context(patch.object(cls, method, importer(cls, method)))
            for method in METHODS.get(cls, ()):
                patches.enter_context(patch.object(cls, method, function(cls.__name__ + "." + method, getattr(cls, method))))
        for original in FUNCTIONS:
            wrapped = function(original.__name__, original)
            for module in tuple(sys.modules.values()):
                if module is None or module is sys.modules[__name__]: continue
                for name, value in tuple(vars(module).items()):
                    if value is original: patches.enter_context(patch.object(module, name, wrapped))
        original_main = cli.main
        wrapped_main = cli_function(original_main)
        for module in tuple(sys.modules.values()):
            if module is None or module is sys.modules[__name__]: continue
            for name, value in tuple(vars(module).items()):
                if value is original_main: patches.enter_context(patch.object(module, name, wrapped_main))
        if child_script is None:
            original_subprocess = subprocess.run
            def observed_subprocess(command, *args, **kwargs):
                require(isinstance(command, list) and len(command) == 3 and command[:2] == [sys.executable, "-c"],
                        "New subprocess shape requires complete child capture")
                context = {"id": current["id"] + "/subprocess/" + str(len(children)), "source": callsite()}
                with tempfile.TemporaryDirectory(prefix="realization-capture-") as directory:
                    output = Path(directory) / "capture.json"
                    bootstrap = ("from " + CHILD_MODULE + " import child_main; child_main(" +
                                 repr(command[2]) + "," + repr(context) + "," + repr(str(output)) + ")")
                    result = original_subprocess([*command[:2], bootstrap], *args, **kwargs)
                    require(output.exists(), "Original child did not produce its complete capture")
                    child = json.loads(output.read_bytes())
                    for identity, record in child["documents"].items():
                        require(store.retain(record["kind"], record["value"]) == identity, "Child document changed")
                    calls.extend(child["api_calls"])
                    child["invocation"] = {"id": context["id"], "source_test": current["id"], "source": context["source"],
                        "script": command[2], "hash_seed": kwargs["env"]["PYTHONHASHSEED"], "returncode": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr}
                    children.append({"invocation": child["invocation"], "contexts": child["contexts"]})
                    return result
            patches.enter_context(patch.object(subprocess, "run", observed_subprocess))
            with portable_temporary_directories(), log_path.open("a") as logs:
                observed = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=RecordedResult).run(
                    unittest.TestSuite(test for module in modules for test in inventory(module)))
            require(observed.wasSuccessful() and observed.testsRun == sum(METHOD_COUNTS) and not observed.skipped,
                    "Instrumented original assertions failed: " + str(log_path))
        else:
            exec(compile(child_script, "<string>", "exec"), {"__name__": "__main__"})
            ledger.append(dict(current)); require(not stack, "Unclosed original child call")
    if child_script is None:
        require([entry["id"] for entry in ledger] == expected, "Original assertion ledger differs")
        require(sources == source_inventory(), "Original source inventory changed during capture")
    require(len({call["id"] for call in calls}) == len(calls), "Duplicate realization API call")
    contexts = [*ledger, *fixtures.values()]
    for child in children: contexts.extend(child["contexts"])
    coverage = {"original_methods": len(ledger) if child_script is None else 0, "per_module_methods": METHOD_COUNTS,
        "contexts": len(contexts), "api_calls": len(calls), "documents": len(store.records),
        "document_bytes": store.size, "api_census": dict(sorted(Counter(c["api"] for c in calls).items())),
        "api_outcomes": dict(sorted(Counter(c["outcome"] for c in calls).items())), "subprocess_invocations": len(children)}
    document = {"schema_version": "biocompiler.realization_workflow_baseline_capture.v1",
        "source_files": sources, "contexts": contexts, "subprocesses": children, "api_calls": calls,
        "documents": store.records, "coverage": coverage,
        "capture_environment": {"temporary_directories": str(PORTABLE_TEMP),
            "temporary_directory_policy": "exclusive_owned_stable_paths_before_execution_no_output_normalization",
            "source_paths": "portable_before_original_construction",
            "python_hash_seed": "0" if child_script is None else os.environ.get("PYTHONHASHSEED")}}
    if child_script is not None: return document
    payload = canonical(document) + b"\n"
    (OUT / "capture.json").write_bytes(payload)
    receipt = {"capture_sha256": digest(payload), "bytes": len(payload), "generator_sha256": digest(Path(__file__).read_bytes()),
        "support_sha256": digest((ROOT / "tools/freeze_component_runtime.py").read_bytes()),
        "python": sys.version, "platform": platform.platform(), "baseline_tests": baseline.testsRun,
        "captured_tests": observed.testsRun, "coverage": coverage, "capture_environment": document["capture_environment"]}
    (OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return document



def child_main(script, context, output):
    with portable_sources(): result = capture(script, context)
    Path(output).write_bytes(canonical(result))




def hydrate_arguments(call, documents):
    """Reconstruct nominal original arguments independently from raw wire bytes."""
    import importlib
    from types import MappingProxyType
    raw = json.loads(documents[call["input"]]["value"])
    def resolve(name):
        module, _, member = name.rpartition(".")
        require(module.startswith("biocompiler.") or module == "builtins", "Unreviewed nominal argument class")
        return getattr(importlib.import_module(module), member)
    for descriptor in sorted(call["python_types"], key=lambda item: len(item["path"]), reverse=True):
        path = descriptor["path"]
        container = raw
        for part in path[:-1]: container = container[part]
        value = container[path[-1]] if path else raw
        name = descriptor["type"]
        if name == "builtins.tuple": replacement = tuple(value)
        elif name == "builtins.tuple_iterator": replacement = iter(tuple(value))
        elif name == "builtins.mappingproxy": replacement = MappingProxyType(value)
        elif name == "python_type": replacement = resolve(descriptor["value"])
        elif name == "builtins.function": continue  # Explicit transcript replaces evaluator below.
        elif name == "biocompiler.semantics.evaluator.InputFrame":
            replacement = previous.frames_from_json([value])[0]
        elif name == "biocompiler.semantics.evaluator.SignalSample":
            from biocompiler.semantics.evaluator import SignalSample
            replacement = SignalSample(**value)
        else:
            cls = resolve(name)
            replacement = cls.from_dict(value) if hasattr(cls, "from_dict") else cls(value)
        if path: container[path[-1]] = replacement
        else: raw = replacement
    return raw


def original_exception(value):
    import importlib
    require(value["module"] in {"builtins", "biocompiler.errors"}, "Unreviewed callback exception class")
    cls = getattr(importlib.import_module(value["module"]), value["type"])
    return cls(value["message"])


def replay_observation(call, documents, calls):
    """Replay one original new-domain/kernel occurrence, never its expected result."""
    api = call["api"]
    raw = hydrate_arguments(call, documents)
    if "." in api:
        name, method = api.split(".")
        require(name in {cls.__name__ for cls in WORKFLOW_CLASSES}, "Not a workflow domain observation")
        cls = CLASS_BY_NAME[name]
        function = cls if method == "__init__" else getattr(cls, method)
    else:
        function = next(item for item in WORKFLOW_FUNCTIONS if item.__name__ == api)
    invoked = []
    if api in {"explore_boolean_histories", "reduce_counterexample"}:
        bound = inspect.signature(function).bind(*raw["args"], **raw["kwargs"])
        if isinstance(bound.arguments["evaluate"], dict) and "__workflow_callback__" in bound.arguments["evaluate"]:
            transcript = list(call.get("callback_calls", []))
            def evaluate(*args, **kwargs):
                require(len(invoked) < len(transcript), "Fresh kernel made an extra callback")
                expected = calls[transcript[len(invoked)]]
                supplied = {"args": plain(args), "kwargs": plain(kwargs)}
                original = json.loads(documents[expected["input"]]["value"])
                require(canonical(supplied) == canonical(original), "Fresh kernel callback input/order/horizon differs")
                invoked.append(expected["id"])
                if expected["outcome"] == "raised": raise original_exception(expected["error"])
                result = documents[expected["result"]]["value"]
                if expected["result_format"] == "python_json_text": result = json.loads(result)
                if isinstance(result, dict) and result.get("schema_version") == BASE.CheckResult.schema_version:
                    return BASE.CheckResult.from_dict(result)
                return result  # Actual wrong-nominal callbacks remain wrong nominal values.
            bound.arguments["evaluate"] = evaluate
            raw = {"args": bound.args, "kwargs": bound.kwargs}
    policy = call.get("policy_override")
    with ExitStack() as patches:
        if policy:
            require(policy == {"checker_version": "changed.v999"}, "Unreviewed workflow policy mutation")
            patches.enter_context(patch.object(realization, "CHECKER_VERSION", policy["checker_version"]))
        try:
            result = function(*raw["args"], **raw["kwargs"])
            if api == "enumerate_boolean_histories":
                for identity in call["yields"]:
                    require(canonical(plain(next(result))) == canonical(documents[identity]["value"]),
                        "Original generator yielded a different complete history")
                state = call["iterator_state"]
                if state == "exhausted":
                    try: next(result)
                    except StopIteration as stopped:
                        require(plain(stopped.value) == documents[call["return_value"]]["value"], "Generator return differs")
                    else: raise AssertionError("Original generator retained extra histories")
                elif state == "raised":
                    try: next(result)
                    except Exception as error:
                        require({"module": type(error).__module__, "type": type(error).__qualname__,
                            "message": str(error)} == call["iteration_error"], "Generator exception differs")
                    else: raise AssertionError("Original generator exception disappeared")
                result.close()
                return {"outcome": "iterator"}
            outcome = {"outcome": "returned", "result": plain(result)}
            if isinstance(result, WORKFLOW_CLASSES):
                outcome["properties"] = {name: plain(getattr(result, name)) for name in WORKFLOW_PROPERTIES
                    if hasattr(type(result), name)}
            return outcome
        except Exception as error:
            return {"outcome": "raised", "error": {"module": type(error).__module__,
                "type": type(error).__qualname__, "message": str(error)}}
        finally:
            if api in {"explore_boolean_histories", "reduce_counterexample"}:
                require(invoked == call.get("callback_calls", []), "Fresh kernel did not consume every original callback")


def verify_replay(document):
    documents = document["documents"]
    calls = {call["id"]: call for call in document["api_calls"]}
    domain_names = {cls.__name__ for cls in WORKFLOW_CLASSES}
    function_names = {function.__name__ for function in WORKFLOW_FUNCTIONS}
    count = 0
    for call in calls.values():
        if call["api"].split(".")[0] not in domain_names and call["api"] not in function_names: continue
        actual = replay_observation(call, documents, calls)
        expected = {"outcome": call["outcome"]}
        if call["outcome"] == "returned":
            expected["result"] = documents[call["result"]]["value"]
            if call["result_format"] == "python_json_text": expected["result"] = json.loads(expected["result"])
            if "properties" in call: expected["properties"] = documents[call["properties"]]["value"]
        elif call["outcome"] == "raised": expected["error"] = call["error"]
        require(json.dumps(actual, sort_keys=True, ensure_ascii=True) == json.dumps(expected, sort_keys=True, ensure_ascii=True),
            "Independent complete Python replay differs: " + call["id"] + " " + call["api"] +
            (" " + str(actual.get("error")) if actual["outcome"] == "raised" else ""))
        count += 1
    return count


def load_previous():
    path = ROOT / "tests/conformance/synthetic-producers-v1.json"
    index = json.loads(path.read_bytes())
    require(index["inventory_fingerprint"] == PRIOR_PIN and digest(canonical(
        {key: value for key, value in index.items() if key != "inventory_fingerprint"})) == PRIOR_PIN,
        "Immutable producer inventory differs")
    descriptors = {row["id"]: row for row in index["documents"]}
    cache = {}
    def document(identity):
        if identity not in cache:
            payload = (path.with_suffix("") / (identity + ".json")).read_bytes()
            value = json.loads(payload)
            require(len(payload) == descriptors[identity]["bytes"] and
                canonical(value) + b"\n" == payload and digest(canonical(value)) == identity,
                "Prior complete document changed")
            cache[identity] = value
        return cache[identity]
    calls = {}
    for context in index["contexts"]:
        rows = document(context["ledger"])["observations"]
        calls[context["id"]] = [
            {**row, "source": index["source_locations"][row["source"]],
             "python_types": document(row["python_types"])} for row in rows]
    return index, document, calls


def verify_prior_projection(capture, *, complete=True):
    """Compare each old occurrence in order; shared documents never dedup calls."""
    index, old_document, old_calls = load_previous()
    old_apis = set(index["coverage"]["api_census"])
    grouped = {}
    for call in capture["api_calls"]:
        if call["api"] in old_apis:
            grouped.setdefault(call["source_test"], []).append(call)
    signatures = ("api", "source", "input", "python_types", "outcome", "result", "result_format", "error", "properties")
    matched = {}
    current_contexts = {item["id"] for item in capture["contexts"]}
    required_contexts = set(old_calls) if complete else set(old_calls) & current_contexts
    for context in sorted(required_contexts):
        current, prior = grouped.get(context, []), old_calls[context]
        require(len(current) == len(prior), "Prior occurrence census differs: " + context)
        renumber = {call["id"]: number for number, call in enumerate(current)}
        by_id = {call["id"]: call for call in capture["api_calls"] if call["source_test"] == context}
        for number, (call, expected) in enumerate(zip(current, prior)):
            require({key: call[key] for key in signatures if key in call} ==
                    {key: expected[key] for key in signatures if key in expected},
                    "Prior complete observation differs: " + context + "/api/" + str(number))
            parent = call["parent_call"]
            while parent is not None and parent not in renumber:
                parent = by_id[parent]["parent_call"]
            require((renumber[parent] if parent is not None else None) == expected["parent"],
                    "Prior observed call nesting differs")
            for key in ("input", "result", "properties"):
                if key in expected:
                    require(capture["documents"][call[key]]["value"] == old_document(expected[key]),
                            "Prior full argument/result document differs")
            matched[call["id"]] = {"id": context + "/api/" + str(number), "native": expected["native"]}
    if complete:
        require(len(matched) == 47901 and required_contexts <= current_contexts,
            "Missing original producer observation/context")
        require(capture["subprocesses"] == index["subprocesses"], "Original actual children differ")
    return matched


def bind_operation(call, documents):
    raw = json.loads(documents[call["input"]]["value"])
    api = call["api"]
    if api in {"workflow.callback", "workflow.cli"}: return raw
    if "." in api:
        name, method = api.split(".")
        cls = CLASS_BY_NAME[name]
        if method == "__init__": signature = SIGNATURES[name]
        else: signature = inspect.signature(getattr(cls, method))
    else:
        original = next(function for function in FUNCTIONS if function.__name__ == api)
        signature = inspect.signature(original)
    bound = signature.bind(*raw["args"], **raw["kwargs"])
    bound.apply_defaults()
    value = plain(dict(bound.arguments))
    if api in previous.ACCEPTANCE and value.get("core") is None: value.pop("core", None)
    return value


def freeze(document, *, check=False):
    require(document["schema_version"] == "biocompiler.realization_workflow_baseline_capture.v1", "Wrong workflow capture schema")
    require(document["source_files"] == source_inventory(), "Workflow captured sources changed")
    matched = verify_prior_projection(document)
    store = Store()
    for identity, item in document["documents"].items():
        require(store.retain(item["kind"], item["value"]) == identity, "Workflow original document changed")
    def retain_input(kind, value):
        # Full identical JSON may serve as a constructor input and a returned
        # record. Keep the original storage kind and explicit operation role.
        identity = digest(canonical(value))
        return store.retain(store.records.get(identity, {}).get("kind", kind), value)
    grouped = {}
    locations, location_ids = [], {}
    new_names = {cls.__name__ for cls in WORKFLOW_CLASSES}
    new_functions = {function.__name__ for function in WORKFLOW_FUNCTIONS}
    stages = Counter()
    for original in document["api_calls"]:
        call = dict(original)
        if call["id"] in matched:
            old = matched[call["id"]]
            call["native"] = {"stage": "pinned_prerequisite", "corpus": "synthetic-producers-v1",
                "inventory_fingerprint": PRIOR_PIN, "occurrence": int(old["id"].rsplit("/", 1)[1])}
        elif call["api"].split(".")[0] in new_names or call["api"] in new_functions:
            bound = bind_operation(call, document["documents"])
            call["native"] = {"stage": "workflow_domain" if "." in call["api"] else "workflow_kernel",
                "operation": call["api"], "input": retain_input("bound_arguments_text",
                    json.dumps(bound, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True))}
        elif call["api"] == "workflow.callback":
            call["native"] = {"stage": "test_only_callback_transcript", "operation": call["api"]}
        elif call["api"] == "workflow.cli":
            call["native"] = {"stage": "original_cli_publication", "operation": call["api"],
                "routed_child_obligation": "execute_same_original_cli_authority_with_both_installed_roles_after_workflow_endpoints"}
        else:
            # Additional complete campaign calls retain existing semantics. No
            # prior occurrence is invented for this newly included source cohort.
            operation, value, source_stage = previous.observation_input(call, document["documents"])
            call["native"] = {"stage": "additional_prerequisite", "operation": operation,
                "source_stage": source_stage, "input": retain_input("bound_arguments", value),
                "expected_code": previous.expected_code(call, operation, value)}
        stages[call["native"]["stage"]] += 1
        grouped.setdefault(call["source_test"], []).append(call)
    contexts = []
    for context in document["contexts"]:
        calls = grouped.get(context["id"], [])
        require(context["api_calls"] == [call["id"] for call in calls], "Workflow occurrence list differs")
        rows = []
        for number, original in enumerate(calls):
            require(original["id"] == context["id"] + "/api/" + str(number), "Workflow local order changed")
            call = {key: value for key, value in original.items() if key not in {"id", "source_test"}}
            key = canonical(call["source"])
            if key not in location_ids:
                location_ids[key] = len(locations); locations.append(call["source"])
            call["source"] = location_ids[key]
            call["python_types"] = store.retain("python_types", call["python_types"])
            for key in ("parent_call", "callback_parent"):
                if key in call and call[key] is not None:
                    require(call[key].startswith(context["id"] + "/api/"), "Cross-context workflow parent")
                    call[key] = int(call[key].rsplit("/", 1)[1])
            if "callback_calls" in call:
                call["callback_calls"] = [int(identity.rsplit("/", 1)[1]) for identity in call["callback_calls"]]
            rows.append(call)
        contexts.append({**context, "api_calls": len(calls), "ledger": store.retain("workflow_ledger", rows)})
    context_numbers = {context["id"]: number for number, context in enumerate(contexts)}
    index = {"schema_version": "biocompiler.realization_workflow_conformance.v1",
        "claim_scope": "complete_original_workflow_domain_kernels_callbacks_and_cli_observations_no_native_or_biology_claim",
        "source_files": document["source_files"], "contexts": contexts,
        "source_locations": locations, "original_documents": sorted(document["documents"]),
        "original_capture_environment": document["capture_environment"],
        "subprocesses": document["subprocesses"], "original_capture_fingerprint": digest(canonical(document)),
        "capture_call_order": store.retain("call_order", [[context_numbers[call["source_test"]],
            int(call["id"].rsplit("/", 1)[1])] for call in document["api_calls"]]),
        "coverage": {**document["coverage"], "native_stages": dict(sorted(stages.items())),
            "preserved_prior_occurrences": len(matched), "unclassified_observations": 0},
        "prerequisites": [{"corpus": "synthetic-producers-v1", "inventory_fingerprint": PRIOR_PIN,
            "original_occurrences": 47901}],
        "capture_environment": {"python_hash_seed": "0", "portable_source_paths": "/__biocompiler_capture__/",
            "temporary_directories": str(PORTABLE_TEMP), "temporary_directory_policy":
            "exclusive_owned_root_stable_paths_before_original_execution_no_output_normalization",
            "callbacks": "source_pinned_full_ordered_invocations_no_executable_closures",
            "cli": "original_in_process_execution_full_argv_files_stdout_stderr_exit_unmodified"}}
    payloads = {identity: canonical(record["value"]) + b"\n" for identity, record in store.records.items()}
    index["documents"] = [{"id": identity, "kind": store.records[identity]["kind"], "bytes": len(payload)}
        for identity, payload in sorted(payloads.items())]
    index["inventory_fingerprint"] = digest(canonical(index))
    payload = canonical(index) + b"\n"
    total = len(payload) + sum(map(len, payloads.values()))
    require(total <= MAX_TOTAL_BYTES, "Complete workflow corpus exceeds reviewed 512 MiB bound")
    directory = CORPUS.with_suffix("")
    if check:
        require(CORPUS.read_bytes() == payload, "Independent workflow capture index differs")
        require({path.name for path in directory.iterdir()} == {key + ".json" for key in payloads}, "Workflow inventory differs")
        for identity, value in payloads.items(): require((directory / (identity + ".json")).read_bytes() == value, "Workflow complete document differs")
    else:
        require(not CORPUS.exists() and not directory.exists(), "Refuse to overwrite workflow golden corpus")
        directory.mkdir(parents=True)
        for identity, value in payloads.items(): (directory / (identity + ".json")).write_bytes(value)
        CORPUS.write_bytes(payload)
    print(json.dumps({"inventory_fingerprint": index["inventory_fingerprint"], "bytes": total,
        "coverage": index["coverage"]}, sort_keys=True), flush=True)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--captured", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.captured: document = json.loads(args.captured.read_bytes())
    else:
        with portable_sources(): document = capture()
    if not args.capture_only: freeze(document, check=args.check)


if __name__ == "__main__": main()
