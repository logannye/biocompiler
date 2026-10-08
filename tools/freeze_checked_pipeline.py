#!/usr/bin/env python3
"""Observe original checked-manager semantics without replacing its providers.

Raw Python values retain type and ordering distinctions. Callback observations
are evidence, never imported acceptance or executable provider registration.
Real producer/checker replay remains an explicit separate obligation.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import fields, is_dataclass
import dis
from enum import Enum
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from tools.freeze_component_runtime import canonical, digest, inventory, load, require
from tools.freeze_realization_acceptance import FILES as FOUNDATION_FILES, METHOD_COUNTS as FOUNDATION_COUNTS, portable_sources
from biocompiler.compiler import pipeline
from biocompiler.compiler.passes import PassResult

BASE_ADDITIONS = ("test_checked_pipeline", "test_m9_admission_audit", "test_circuit_checker_independence",
                  "test_component_admission", "test_component_pipeline_manager", "test_pipeline")
BASE_COUNTS = (6, 6, 4, 10, 2, 21)
EXTRA = ("test_candidate_pipeline", "test_construct_pipeline", "test_construct_pipeline_audit",
         "test_implementation_workflow", "test_molecular_design", "test_molecular_design_build",
         "test_molecular_pipeline", "test_pipeline_audit", "test_reference_package",
         "test_reference_package_audit", "test_molecular_design_workflow", "test_studio_service")
EXTRA_COUNTS = (8, 9, 5, 11, 8, 10, 9, 4, 12, 4, 5, 9)
FILES = (*FOUNDATION_FILES, *("tests/" + name + ".py" for name in (*BASE_ADDITIONS, *EXTRA)))
CLASSES = (pipeline.ScopedObligation, pipeline.CheckSpec, pipeline.CheckDecision, pipeline.PassContract,
           pipeline.PassContext, pipeline.ComponentInputContract, pipeline.CompletionProfile,
           pipeline.StageRecord, pipeline.PipelineResult, PassResult, pipeline.NoCandidateFound)
MANAGER_METHODS = ("__init__", "register_completion_profile", "set_dependency", "register",
    "register_component_input", "admit_component_input", "add_input", "get", "run", "result")
PIPELINE_FILE = ROOT / "src/biocompiler/compiler/pipeline.py"
SCHEMA = "biocompiler.checked_pipeline_original_capture.v1"
SCOPE = "original_manager_discipline_and_callback_observations_no_imported_acceptance_or_real_native_callback_parity"
OUT = ROOT / "generated/migration-next/checked-pipeline-capture"
CORPUS = ROOT / "tests/conformance/checked-pipeline-v1.json"
MAX_DOCUMENT_BYTES, MAX_TOTAL_BYTES = 32 * 1024 * 1024, 512 * 1024 * 1024


def name(value):
    return type(value).__module__ + "." + type(value).__qualname__


def relative(path):
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


class Store:
    def __init__(self):
        self.documents, self.size = {}, 0

    def retain(self, value):
        raw = canonical(value)
        require(len(raw) + 1 <= MAX_DOCUMENT_BYTES, "Pipeline capture document exceeds reviewed bound")
        identity = digest(raw)
        if identity not in self.documents:
            self.documents[identity] = value
            self.size += len(raw) + 1
            require(self.size <= MAX_TOTAL_BYTES, "Pipeline capture exceeds reviewed storage bound")
        return identity


def callback_sites():
    tree = ast.parse(PIPELINE_FILE.read_text())
    return {node.lineno: "producer" if isinstance(node.func, ast.Name) else "validator"
        for node in ast.walk(tree) if isinstance(node, ast.Call) and
        (isinstance(node.func, ast.Name) and node.func.id == "producer" or
         isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Name) and node.func.value.id == "validators")}


class Observer:
    def __init__(self, paths, child_context=None):
        self.paths, self.store = set(paths), Store()
        self.context = None
        self.contexts, self.events, self.stack = [], [], []
        self.handles, self.retained_objects, self.providers = {}, [], {}
        self.serializing = 0
        self.callback_lines = callback_sites()
        require(len(self.callback_lines) == 3, "Original callback sites changed")
        self.opcodes = {}
        self.child_context = child_context

    @contextmanager
    def quiet(self):
        self.serializing += 1
        try:
            yield
        finally:
            self.serializing -= 1

    def handle(self, value, kind):
        key = id(value)
        if key not in self.handles:
            prefix = "" if self.child_context is None else self.child_context["id"] + "/"
            self.handles[key] = prefix + kind + "/" + str(len(self.handles))
            self.retained_objects.append(value)
        return self.handles[key]

    def provider(self, value):
        identity = self.handle(value, "provider")
        if identity not in self.providers:
            self.providers[identity] = {"id": identity, "class": name(value)}
            code = getattr(value, "__code__", None)
            if code is not None:
                record = {"module": value.__module__, "qualname": value.__qualname__,
                    "file": relative(code.co_filename), "line": code.co_firstlineno,
                    "source": inspect.getsource(value), "freevars": list(code.co_freevars),
                    "defaults": self.encode(value.__defaults__), "kwdefaults": self.encode(value.__kwdefaults__),
                    "closure": {key: self.encode(cell.cell_contents) for key, cell in
                        zip(code.co_freevars, value.__closure__ or ())}}
                record["origin"] = "original_test_provider" if record["file"].startswith("tests/") else "original_product_provider"
                record["native_recipe"] = {"status": "pending_review", "reason":
                    "source_reviewed_manager_fixture_required" if record["origin"] == "original_test_provider" else
                    "real_native_producer_or_checker_parity_required"}
                self.providers[identity].update(record)
            elif isinstance(value, Mock):
                self.providers[identity].update(origin="original_test_mock", module="unittest.mock",
                    return_value=self.encode(value.return_value), side_effect=self.encode(value.side_effect),
                    native_recipe={"status": "pending_review", "reason": "source_reviewed_mock_identity_and_call_count_required"})
            else:
                self.providers[identity].update(origin="original_callable_object", native_recipe={
                    "status": "pending_review", "reason": "callable_object_requires_explicit_replay"})
        return {"$type": "provider", "id": identity}

    def encode(self, value):
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is float:
            return value if math.isfinite(value) else {"$type": "nonfinite", "value": repr(value)}
        if isinstance(value, Enum):
            return {"$type": "enum", "class": name(value), "value": self.encode(value.value)}
        if isinstance(value, pipeline.PassManager):
            return {"$type": "manager", "id": self.handle(value, "manager")}
        if isinstance(value, type):
            return {"$type": "python_class", "class": value.__module__ + "." + value.__qualname__}
        if isinstance(value, unittest.TestCase):
            return {"$type": "object", "class": name(value), "id": self.handle(value, "object"),
                "attributes": {key: self.encode(item) for key, item in vars(value).items() if not key.startswith("_")}}
        if callable(value):
            return self.provider(value)
        if is_dataclass(value):
            return {"$type": "dataclass", "class": name(value), "fields": {
                field.name: self.encode(getattr(value, field.name)) for field in fields(value)}}
        if isinstance(value, Mapping):
            return {"$type": "mapping", "class": name(value),
                    "items": [[self.encode(key), self.encode(item)] for key, item in value.items()]}
        if isinstance(value, (tuple, list)):
            return {"$type": "tuple" if isinstance(value, tuple) else "list", "items": [self.encode(item) for item in value]}
        if isinstance(value, (set, frozenset)):
            return {"$type": "set", "class": name(value), "items": [self.encode(item) for item in value]}
        if type(value) is bytes:
            return {"$type": "bytes", "hex": value.hex()}
        if isinstance(value, BaseException):
            return self.error(value)
        if hasattr(value, "to_dict"):
            return {"$type": "document", "class": name(value), "value": self.encode(value.to_dict())}
        identity = self.handle(value, "object")
        attributes = {}
        # Test fixture handles remain explicit; retain all user-established
        # public state, excluding unittest's runner/traceback implementation.
        if isinstance(value, unittest.TestCase):
            attributes = {key: self.encode(item) for key, item in vars(value).items() if not key.startswith("_")}
        return {"$type": "object", "class": name(value), "id": identity, "attributes": attributes}

    def document(self, value):
        with self.quiet():
            return self.store.retain(self.encode(value))

    def state(self, manager):
        if manager is None:
            return None
        with self.quiet():
            return self.store.retain({"manager": self.handle(manager, "manager"),
                "fields": {key: self.encode(value) for key, value in vars(manager).items()}})

    def error(self, error):
        result = {"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}
        if isinstance(error, pipeline.NoCandidateFound):
            result["attributes"] = {key: self.encode(getattr(error, key)) for key in ("pass_id", "configuration", "dependencies")}
        return result

    def source(self):
        frame = inspect.currentframe()
        try:
            while frame is not None:
                path = relative(frame.f_code.co_filename)
                if path in self.paths:
                    return {"file": path, "line": frame.f_lineno, "function": frame.f_code.co_name}
                frame = frame.f_back
        finally:
            del frame
        if self.child_context is not None:
            return self.child_context["source"]
        raise AssertionError("Original pipeline operation has no retained source test")

    def begin(self, api, arguments, *, manager=None, callback=None):
        with self.quiet():
            source = self.source()
            if self.context is None:
                key = source["file"] + "::fixture." + source["function"]
                matches = [item for item in self.contexts if item["id"] == key]
                context = matches[0] if matches else {"id": key, "kind": "class_fixture", "assertion_status": "passed", "events": []}
                if not matches:
                    self.contexts.append(context)
            else:
                context = self.context
            identity = context["id"] + "/event/" + str(len(context["events"]))
            event = {"id": identity, "context": context["id"], "api": api, "source": source,
                "parent": self.stack[-1]["id"] if self.stack else None, "arguments": self.document(arguments),
                "manager": None if manager is None else self.handle(manager, "manager"), "state_before": self.state(manager)}
            if callback is not None:
                event["provider"] = self.provider(callback)["id"]
            self.events.append(event)
            context["events"].append(identity)
            self.stack.append(event)
            return event

    def finish(self, event, *, value=None, error=None, manager=None):
        with self.quiet():
            event["state_after"] = self.state(manager)
            if error is None:
                event.update(outcome="returned", result=self.document(value))
            else:
                event.update(outcome="raised", error=self.error(error))
            require(self.stack.pop() is event, "Original pipeline observation stack changed")

    def wrapped(self, api, original, *, constructor=False, manager_method=False):
        signature = inspect.signature(original)
        def observed(subject, *args, **kwargs):
            if self.serializing:
                return original(subject, *args, **kwargs)
            manager = subject if manager_method else None
            # Preserve supplied args before binding: invalid calls are genuine
            # Python boundary observations, not valid native constructor inputs.
            arguments = {"args": args, "kwargs": kwargs}
            if not constructor:
                arguments["subject"] = subject
            try:
                bound = signature.bind(subject, *args, **kwargs)
                bound.apply_defaults()
                arguments["bound"] = {key: value for key, value in bound.arguments.items() if key not in ("self", "cls")}
            except TypeError as error:
                arguments["binding_error"] = self.error(error)
            event = self.begin(api, arguments, manager=manager)
            try:
                result = original(subject, *args, **kwargs)
            except BaseException as error:
                self.finish(event, error=error, manager=manager)
                raise
            else:
                self.finish(event, value=subject if constructor else result, manager=manager)
                return result
        return observed

    def trace(self, frame, event, argument):
        if event != "call" or self.serializing:
            return None
        caller = frame.f_back
        if caller is None or caller.f_code.co_filename != str(PIPELINE_FILE) or caller.f_lineno not in self.callback_lines:
            return None
        manager = caller.f_locals["self"]
        callback = (caller.f_locals["producer"] if self.callback_lines[caller.f_lineno] == "producer"
                    else caller.f_locals["validators"][caller.f_locals["spec"].id])
        observation = self.begin("callback.invoke", {"locals": dict(frame.f_locals),
            "context": caller.f_locals["context"]}, manager=manager, callback=callback)
        last_error = [None]
        def local(current, kind, value):
            if kind == "exception":
                last_error[0] = value[1]
            elif kind == "return":
                if current.f_code not in self.opcodes:
                    self.opcodes[current.f_code] = {item.offset: item.opname for item in dis.get_instructions(current.f_code)}
                normal = self.opcodes[current.f_code].get(current.f_lasti, "").startswith("RETURN_")
                require(normal or last_error[0] is not None, "Callback unwind lost its original exception")
                self.finish(observation, value=value, error=None if normal else last_error[0], manager=manager)
            return local
        return local

    @contextmanager
    def installed(self):
        previous = sys.gettrace()
        with ExitStack() as patches:
            for cls in CLASSES:
                patches.enter_context(patch.object(cls, "__init__", self.wrapped(cls.__name__ + ".__init__", cls.__init__, constructor=True)))
                if "to_dict" in vars(cls):
                    patches.enter_context(patch.object(cls, "to_dict", self.wrapped(cls.__name__ + ".to_dict", cls.to_dict)))
                for key, item in tuple(vars(cls).items()):
                    if isinstance(item, property):
                        patches.enter_context(patch.object(cls, key, property(self.wrapped(cls.__name__ + "." + key, item.fget))))
            for method in MANAGER_METHODS:
                patches.enter_context(patch.object(pipeline.PassManager, method,
                    self.wrapped("PassManager." + method, getattr(pipeline.PassManager, method),
                                 constructor=method == "__init__", manager_method=True)))
            patches.enter_context(patch.object(pipeline, "_document", self.wrapped("_document", pipeline._document)))
            original = pipeline.PassManager.target
            patches.enter_context(patch.object(pipeline.PassManager, "target", property(self.wrapped(
                "PassManager.target", original.fget, manager_method=True))))
            sys.settrace(self.trace)
            try:
                yield
                require(sys.gettrace() == self.trace, "Original callback observer was replaced")
            finally:
                sys.settrace(previous)


def source_inventory(paths):
    sources = {path.relative_to(ROOT).as_posix(): digest(path.read_bytes())
        for folder in ("src/biocompiler", "examples") for path in (ROOT / folder).rglob("*.py")}
    sources.update({path: digest((ROOT / path).read_bytes()) for path in paths})
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve().parent == ROOT / "tests":
            sources[relative(path)] = digest(Path(path).read_bytes())
    return dict(sorted(sources.items()))


def child_main(script, context, output):
    observer = Observer((), context)
    observer.context = {"id": context["id"], "kind": "original_subprocess", "assertion_status": "passed", "events": []}
    # Child source locations remain exactly those used by the original child.
    # Parent authoring portability must not rewrite its complete stdout hashes.
    with observer.installed():
        exec(compile(script, "<string>", "exec"), {"__name__": "__main__"})
    require(not observer.stack, "Unclosed original child pipeline event")
    Path(output).write_bytes(canonical({"context": observer.context, "events": observer.events,
        "documents": observer.store.documents, "providers": observer.providers}) + b"\n")


def capture(*, pilot=False):
    require(os.environ.get("PYTHONHASHSEED") == "0", "Capture requires PYTHONHASHSEED=0")
    tool_pin = digest(Path(__file__).read_bytes())
    paths = ("tests/test_pipeline.py",) if pilot else FILES
    modules = [load(path) for path in paths]
    counts = [len(inventory(module)) for module in modules]
    require(counts == [21] if pilot else counts == [*FOUNDATION_COUNTS, *BASE_COUNTS, *EXTRA_COUNTS],
            "Original checked-pipeline method census changed")
    expected = [path + "::" + test.id().split(".", 1)[1] for path, module in zip(paths, modules) for test in inventory(module)]
    OUT.mkdir(parents=True, exist_ok=True)
    mode = "pilot" if pilot else "full"
    log_path = OUT / (mode + "-original-tests.log")
    sources = source_inventory(paths)
    original_subprocess, baseline_children, children = subprocess.run, [], []
    def baseline_subprocess(command, *args, **kwargs):
        result = original_subprocess(command, *args, **kwargs)
        baseline_children.append({"command": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr, "hash_seed": kwargs.get("env", {}).get("PYTHONHASHSEED")})
        return result
    with portable_sources(), patch.object(subprocess, "run", baseline_subprocess), log_path.open("w") as logs:
        baseline = unittest.TextTestRunner(stream=logs, verbosity=2).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
    require(baseline.wasSuccessful() and baseline.testsRun == sum(counts) and not baseline.skipped,
            "Uninstrumented original pipeline assertions failed: " + str(log_path))
    observer = Observer(paths)
    def observed_subprocess(command, *args, **kwargs):
        require(isinstance(command, list) and len(command) == 3 and command[:2] == [sys.executable, "-c"],
                "New original subprocess shape needs complete capture")
        context = {"id": observer.context["id"] + "/subprocess/" + str(len(children)), "source": observer.source()}
        with tempfile.TemporaryDirectory(prefix="checked-pipeline-child-") as directory:
            output = Path(directory) / "capture.json"
            bootstrap = "from tools.freeze_checked_pipeline import child_main; child_main(" + ",".join(
                repr(value) for value in (command[2], context, str(output))) + ")"
            result = original_subprocess([*command[:2], bootstrap], *args, **kwargs)
            require(output.exists(), "Original child omitted its complete pipeline ledger")
            child = json.loads(output.read_bytes())
            for identity, value in child["documents"].items():
                require(observer.store.retain(value) == identity, "Original child document changed")
            require(not set(child["providers"]) & set(observer.providers), "Child provider identity collision")
            observer.providers.update(child["providers"])
            observer.events.extend(child["events"])
            observer.contexts.append(child["context"])
            children.append({"id": context["id"], "parent_context": observer.context["id"], "source": context["source"],
                "command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                "hash_seed": kwargs.get("env", {}).get("PYTHONHASHSEED"), "events": len(child["events"])})
            return result
    class Recorded(unittest.TextTestResult):
        def startTest(self, test):
            path = paths[modules.index(sys.modules[type(test).__module__])]
            observer.context = {"id": path + "::" + test.id().split(".", 1)[1], "kind": "original_method",
                                "assertion_status": "passed", "events": []}
            super().startTest(test)
        def addFailure(self, test, error):
            observer.context["assertion_status"] = "failed"
            super().addFailure(test, error)
        def addError(self, test, error):
            observer.context["assertion_status"] = "error"
            super().addError(test, error)
        def addSubTest(self, test, subtest, error):
            if error is not None:
                observer.context["assertion_status"] = "failed_subtest"
            super().addSubTest(test, subtest, error)
        def stopTest(self, test):
            observer.contexts.append(observer.context)
            observer.context = None
            require(not observer.stack, "Unclosed original pipeline observation")
            super().stopTest(test)
    with portable_sources(), observer.installed(), patch.object(subprocess, "run", observed_subprocess), log_path.open("a") as logs:
        observed = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=Recorded).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
    require(observed.wasSuccessful() and observed.testsRun == sum(counts) and not observed.skipped,
            "Instrumented original pipeline assertions failed: " + str(log_path))
    require([context["id"] for context in observer.contexts if context["kind"] == "original_method"] == expected,
            "Complete original method ledger changed")
    require(sources == source_inventory(paths), "Original pipeline source files changed during capture")
    require(len(children) == len(baseline_children) == (0 if pilot else 2), "Original child invocation census changed")
    for before, after in zip(baseline_children, children):
        require(all(before[key] == after[key] for key in before), "Instrumented original child output changed")
    result = {"schema_version": SCHEMA, "scope": SCOPE, "capture_mode": mode,
        "source_files": sources, "original_methods": expected, "subprocesses": children,
        "baseline_subprocesses": baseline_children,
        "capture_tool": {"path": "tools/freeze_checked_pipeline.py", "sha256": tool_pin},
        "contexts": observer.contexts, "providers": observer.providers, "events": observer.events,
        "documents": observer.store.documents, "coverage": {"original_methods": sum(counts),
            "per_module_methods": dict(zip(paths, counts)), "contexts": len(observer.contexts),
            "events": len(observer.events), "documents": len(observer.store.documents),
            "document_bytes": observer.store.size, "api_census": dict(sorted(Counter(event["api"] for event in observer.events).items())),
            "outcomes": dict(Counter(event["outcome"] for event in observer.events)), "providers": len(observer.providers)},
        "native_replay": {"manager_isolation": "pending_source_reviewed_callback_recipes",
            "real_callback_pipeline_parity": "pending_native_producer_and_checker_execution"}}
    require(digest(Path(__file__).read_bytes()) == tool_pin, "Pipeline capture tool changed during execution")
    raw = canonical(result) + b"\n"
    path = OUT / (mode + "-capture.json")
    path.write_bytes(raw)
    receipt = {"capture_sha256": digest(raw), "bytes": len(raw), "generator_sha256": digest(Path(__file__).read_bytes()),
        "python": sys.version, "platform": platform.platform(), "coverage": result["coverage"]}
    (OUT / (mode + "-receipt.json")).write_bytes(canonical(receipt) + b"\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return result


def freeze(document, *, check=False):
    require(document["schema_version"] == SCHEMA and document["capture_mode"] == "full" and
        document["coverage"]["original_methods"] == 467, "Pilot or incomplete pipeline capture cannot be frozen")
    require(document["capture_tool"] == {"path": "tools/freeze_checked_pipeline.py", "sha256": digest(Path(__file__).read_bytes())},
            "Pipeline capture generator differs from reviewed current source")
    for path, pin in document["source_files"].items():
        require(digest((ROOT / path).read_bytes()) == pin, "Original pipeline source changed: " + path)
    directory = CORPUS.with_suffix("")
    index = {key: value for key, value in document.items() if key != "documents"}
    index.update(schema_version="biocompiler.checked_pipeline_conformance.v1", document_directory=directory.name,
        original_capture_fingerprint=digest(canonical(document)), documents=[
            {"id": identity, "bytes": len(canonical(value)) + 1} for identity, value in sorted(document["documents"].items())])
    index["inventory_fingerprint"] = digest(canonical(index))
    expected_files = {item["id"] + ".json" for item in index["documents"]}
    if check:
        require(CORPUS.read_bytes() == canonical(index) + b"\n", "Original pipeline index changed")
        require({path.name for path in directory.iterdir()} == expected_files, "Original pipeline document inventory changed")
    else:
        require(not CORPUS.exists() and not directory.exists(), "Refusing to replace an existing original pipeline corpus")
        directory.mkdir(parents=True)
    for identity, value in document["documents"].items():
        raw = canonical(value)
        require(digest(raw) == identity, "Captured pipeline content identity differs")
        path = directory / (identity + ".json")
        if check:
            require(path.read_bytes() == raw + b"\n", "Complete original pipeline document changed")
        else:
            path.write_bytes(raw + b"\n")
    if not check:
        CORPUS.write_bytes(canonical(index) + b"\n")
    print("checked-pipeline inventory", index["inventory_fingerprint"], "documents", len(index["documents"]), flush=True)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--freeze", type=Path, help="Freeze a completed full original capture")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(json.loads(args.freeze.read_bytes()), check=args.check)
    else:
        capture(pilot=args.pilot)


if __name__ == "__main__":
    main()
