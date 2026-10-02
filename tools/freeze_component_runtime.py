#!/usr/bin/env python3
"""Retain complete original locked-component observations without replacing assertions."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import MISSING, fields as dataclass_fields
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from copy import deepcopy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated/migration-next/component-runtime-formal-capture"
CORPUS = ROOT / "tests/conformance/component-runtime-v1.json"
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from biocompiler.ir.components import ComponentLock
from biocompiler.registry.components import RegistryLock, ComponentRegistry
from biocompiler.ir.composition import (LifecycleInterval, CompositionInstance, Connection, Provider,
    DependencyBinding, ResourcePool, ResourceBinding, CompositionRequest)
from biocompiler.verification.realization import InputBinding, OutputBinding, ObservationMap
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.models.components import reconstruct_component_mechanism, run_component_model
from biocompiler.models.synthetic import run_model

FILES = ("tests/test_component_pipeline.py", "tests/test_component_pipeline_audit.py",
    "tests/test_temporal_components.py", "tests/test_synthetic_design_workflows.py",
    "tests/test_component_registry.py", "tests/test_component_linker.py", "tests/test_component_audit.py",
    "tests/test_component_adapters.py", "tests/test_synthetic_build.py", "tests/test_human_admission.py",
    "tests/test_construct_assembly.py", "tests/test_construct_checker.py")
METHOD_COUNTS = [9, 7, 15, 8, 11, 30, 12, 5, 11, 33, 10, 12]
KINDS = sorted(("input", "constant", "and", "or", "not", "compare", "select", "any_contact",
                "output", "held_for", "onset", "pulse", "memory"))
CLASSES = (ComponentLock, RegistryLock, ComponentRegistry, LifecycleInterval, CompositionInstance,
    Connection, Provider, DependencyBinding, ResourcePool, ResourceBinding, CompositionRequest,
    InputBinding, OutputBinding, ObservationMap, ComponentAssembly)
CLASS_BY_NAME = {cls.__name__: cls for cls in CLASSES}
SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in CLASSES}
EXECUTION_APIS = ("reconstruct_component_mechanism", "run_component_model", "run_locked_mechanism")
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def plain(value):
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "Non-string input key needs explicit capture")
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise AssertionError(f"Uncaptured Python input type: {type(value).__module__}.{type(value).__qualname__}")


def python_types(value, path=()):
    """Retain Python-only distinctions separately from complete JSON contents."""
    kind = type(value)
    if hasattr(value, "to_dict"):
        return [{"path": list(path), "type": kind.__module__ + "." + kind.__qualname__}]
    result = []
    if kind not in (dict, list, str, bool, int, float, type(None)):
        result.append({"path": list(path), "type": kind.__module__ + "." + kind.__qualname__})
    if isinstance(value, Mapping):
        for key, item in value.items(): result.extend(python_types(item, (*path, key)))
    elif isinstance(value, (tuple, list)):
        for key, item in enumerate(value): result.extend(python_types(item, (*path, key)))
    return result


class Store:
    def __init__(self):
        self.records = {}
        self.size = 0

    def retain(self, kind, value):
        payload = canonical(value)
        require(len(payload) + 1 <= 16 * 1024 * 1024, "Individual component document exceeds wire bound")
        identity = digest(payload)
        if identity in self.records:
            require(self.records[identity]["kind"] == kind, "Cross-kind document collision")
        else:
            self.records[identity] = {"kind": kind, "value": value}
            self.size += len(payload) + 1
            require(self.size <= MAX_TOTAL_BYTES, "Complete component documents exceed reviewed storage ceiling")
        return identity


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem + "_component_capture", ROOT / relative)
    require(spec is not None and spec.loader is not None, "Missing original test module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def inventory(module):
    def leaves(item):
        if isinstance(item, unittest.TestSuite):
            for child in item: yield from leaves(child)
        else: yield item
    return list(leaves(unittest.defaultTestLoader.loadTestsFromModule(module)))


def source_inventory():
    paths = set(FILES)
    for directory in (ROOT / "src/biocompiler", ROOT / "examples"):
        paths.update(path.relative_to(ROOT).as_posix() for path in directory.rglob("*.py"))
    for module in tuple(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve().parent == ROOT / "tests":
            paths.add(Path(file).resolve().relative_to(ROOT).as_posix())
    return [{"path": path, "sha256": digest((ROOT / path).read_bytes())} for path in sorted(paths)]


def capture():
    require(os.environ.get("PYTHONHASHSEED") == "0", "Set PYTHONHASHSEED=0 for reproducible capture")
    OUT.mkdir(parents=True, exist_ok=True)
    modules = [load(path) for path in FILES]
    source_files = source_inventory()
    expected = [path + "::" + test.id().split(".", 1)[1]
        for path, module in zip(FILES, modules) for test in inventory(module)]
    require([len(inventory(module)) for module in modules] == METHOD_COUNTS, "Original method census drift")
    require(len(expected) == len(set(expected)) == sum(METHOD_COUNTS), "Missing or duplicate original test")
    log_path = OUT / "original-tests.log"
    with log_path.open("w") as logs:
        baseline = unittest.TextTestRunner(stream=logs, verbosity=2).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
    require(baseline.wasSuccessful() and baseline.testsRun == len(expected) and not baseline.skipped,
            "Uninstrumented original assertions failed: " + str(log_path))
    store, calls, ledger, fixtures = Store(), [], [], {}
    current = {"id": None}
    reconstructed_objects = {}
    stack = []
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
        raise AssertionError("Observed component call has no original test source")

    def begin(api, args, kwargs):
        source = callsite()
        context = current if current["id"] else fixtures.setdefault(
            source["file"] + "::fixture." + source["function"],
            {"id": source["file"] + "::fixture." + source["function"], "api_calls": [],
             "assertion_status": "passed", "kind": "class_fixture"})
        identity = context["id"] + "/api/" + str(len(context["api_calls"]))
        raw = {"args": plain(args), "kwargs": plain(kwargs)}
        raw_text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
        entry = {"id": identity, "source_test": context["id"], "api": api, "source": source,
            "parent_call": stack[-1] if stack else None, "input": store.retain("raw_arguments", raw_text),
            "python_types": python_types({"args": args, "kwargs": kwargs})}
        calls.append(entry); context["api_calls"].append(identity); stack.append(identity)
        return entry

    def success(entry, value):
        entry.update(outcome="returned", result=store.retain("record", plain(value)))

    def failure(entry, error):
        entry.update(outcome="raised", error={"module": type(error).__module__,
            "type": type(error).__qualname__, "message": str(error)})

    def constructor(cls):
        original = cls.__init__
        def observed(self, *args, **kwargs):
            entry = begin(cls.__name__ + ".__init__", args, kwargs)
            try:
                original(self, *args, **kwargs); success(entry, self)
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Constructor stack corruption")
        return observed

    def import_method(cls, method):
        original = getattr(cls, method).__func__
        def observed(actual_cls, *args, **kwargs):
            entry = begin(actual_cls.__name__ + "." + method, args, kwargs)
            try:
                result = original(actual_cls, *args, **kwargs); success(entry, result); return result
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Import stack corruption")
        return classmethod(observed)

    def function(api, original):
        def observed(*args, **kwargs):
            reconstruction = None
            if api == "run_locked_mechanism":
                reconstruction = reconstructed_objects.get(id(args[0]))
                if reconstruction is None:
                    require(getattr(args[0], "name", None) != "locked_component_assembly",
                            "Locked mechanism execution lost its actual reconstruction observation")
                    return original(*args, **kwargs)
                require(reconstruction[0] is args[0], "Reconstructed object identity was reused")
            if api in ("run_component_model", "run_locked_mechanism"):
                require(len(args) == 2 and isinstance(args[1], (tuple, list)), "Unreviewed runtime history/signature")
            entry = begin(api, args, kwargs)
            if reconstruction is not None: entry["reconstruction_call"] = reconstruction[1]
            try:
                result = original(*args, **kwargs); success(entry, result)
                if api == "reconstruct_component_mechanism": reconstructed_objects[id(result)] = (result, entry["id"])
                return result
            except Exception as error:
                failure(entry, error); raise
            finally: require(stack.pop() == entry["id"], "Function stack corruption")
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
            for method in ("from_dict", "from_json"):
                if hasattr(cls, method): patches.enter_context(patch.object(cls, method, import_method(cls, method)))
        for method in ("lock", "resolve"):
            patches.enter_context(patch.object(ComponentRegistry, method,
                function("ComponentRegistry." + method, getattr(ComponentRegistry, method))))
        for original in (reconstruct_component_mechanism, run_component_model, run_model):
            wrapped = function("run_locked_mechanism" if original is run_model else original.__name__, original)
            for module in tuple(sys.modules.values()):
                if module is None or module is sys.modules[__name__]: continue
                for name, value in tuple(vars(module).items()):
                    if value is original: patches.enter_context(patch.object(module, name, wrapped))
        # These original modules currently launch no subprocesses. Reject a new
        # child rather than silently omit its nested semantic observations.
        def unexpected_subprocess(*args, **kwargs):
            raise AssertionError("New subprocess requires real child instrumentation")
        patches.enter_context(patch.object(subprocess, "run", unexpected_subprocess))
        with log_path.open("a") as logs:
            observed = unittest.TextTestRunner(stream=logs, verbosity=2, resultclass=RecordedResult).run(
                unittest.TestSuite(test for module in modules for test in inventory(module)))
    require(observed.wasSuccessful() and observed.testsRun == len(expected) and not observed.skipped,
            "Instrumented original assertions failed: " + str(log_path))
    require([entry["id"] for entry in ledger] == expected, "Original assertion ledger differs")
    require(source_files == source_inventory(), "Original source inventory changed during capture")
    require(len({call["id"] for call in calls}) == len(calls), "Duplicate observed call")
    returned_mechanisms = [store.records[c["result"]]["value"] for c in calls
        if c["api"] == "reconstruct_component_mechanism" and c["outcome"] == "returned"]
    coverage = {"original_methods": len(ledger), "per_module_methods": METHOD_COUNTS,
        "contexts": len(ledger) + len(fixtures), "api_calls": len(calls),
        "api_census": dict(sorted(Counter(c["api"] for c in calls).items())),
        "api_outcomes": dict(sorted(Counter(c["outcome"] for c in calls).items())),
        "execution_outcomes": {api: dict(sorted(Counter(c["outcome"] for c in calls if c["api"] == api).items())) for api in EXECUTION_APIS},
        "successful_reconstruction_kinds": sorted({n["kind"] for p in returned_mechanisms for n in p["nodes"]}),
        "supported_kinds": KINDS, "subprocess_invocations": 0}
    document = {"schema_version": "biocompiler.component_runtime_baseline_capture.v1",
        "source_files": source_files, "contexts": [*ledger, *fixtures.values()], "api_calls": calls,
        "documents": store.records, "coverage": coverage}
    payload = canonical(document) + b"\n"
    (OUT / "capture.json").write_bytes(payload)
    receipt = {"capture_sha256": digest(payload), "bytes": len(payload), "generator_sha256": digest(Path(__file__).read_bytes()),
        "python": sys.version, "platform": platform.platform(), "baseline_tests": baseline.testsRun,
        "captured_tests": observed.testsRun, "coverage": coverage}
    (OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return document


def constructor_document(name, raw):
    cls = CLASS_BY_NAME[name]
    bound = SIGNATURES[name].bind(*raw["args"], **raw["kwargs"])
    document = dict(bound.arguments)
    for item in dataclass_fields(cls):
        if item.name in document: continue
        if item.default is not MISSING: document[item.name] = plain(item.default)
        elif item.default_factory is not MISSING: document[item.name] = plain(item.default_factory())
        else: raise AssertionError("Missing constructor field: " + name + "." + item.name)
    if hasattr(cls, "schema_version"): document["schema_version"] = cls.schema_version
    if name == "ComponentAssembly":
        document["nodes"] = [{"id": item["id"], "kind": "component_instance"}
                             for item in document["composition"]["instances"]]
    return document


def observation_input(call, documents):
    raw = json.loads(documents[call["input"]]["value"])
    api = call["api"]
    if api == "ComponentRegistry.lock":
        require(len(raw["args"]) == 2 and not raw["kwargs"], "Unknown registry lock signature")
        return "registry_lock", {"registry": raw["args"][0], "selections": raw["args"][1]}, "operation"
    if api == "ComponentRegistry.resolve":
        require(len(raw["args"]) == 2 and not raw["kwargs"], "Unknown registry resolve signature")
        return "registry_resolve", {"registry": raw["args"][0], "lock": raw["args"][1]}, "operation"
    if api == "reconstruct_component_mechanism":
        require(len(raw["args"]) == 1 and not raw["kwargs"], "Unknown reconstruct signature")
        return "reconstruct", raw["args"][0], "reconstruction"
    if api in ("run_component_model", "run_locked_mechanism"):
        require(len(raw["args"]) == 2 and set(raw["kwargs"]) <= {"until"}, "Unknown runtime signature")
        return api, {"subject": raw["args"][0], "history": raw["args"][1],
                     "until": raw["kwargs"].get("until"), "until_supplied": "until" in raw["kwargs"]}, "runtime"
    name, method = api.split(".")
    if method == "__init__": return name, constructor_document(name, raw), "constructor"
    require(method in ("from_dict", "from_json") and len(raw["args"]) == 1 and not raw["kwargs"], "Unknown import signature")
    return name, raw["args"][0], "json_import" if method == "from_json" else "record_import"


def failure_leaf(operation, value, expected_error):
    """Observe the actual deepest Python import that rejects a retained input.

    This identifies nested field/type boundaries for explicit code mapping; it
    neither changes an input nor turns a constructor failure into a generic one.
    """
    from biocompiler.ir.component_contracts import (ComponentRecord, PinnedIdentity,
        SyntheticOperatorModel, SequenceReferenceMetadata)
    from biocompiler.semantics.component_contracts import ValueDomain, OperatingDomain
    from biocompiler.semantics.types import TypeSpec
    observed = []
    def wrapper(cls):
        original = cls.from_dict.__func__
        def decode(actual_cls, data):
            try: return original(actual_cls, data)
            except Exception as error:
                observed.append((actual_cls, data, str(error))); raise
        return classmethod(decode)
    with ExitStack() as patches:
        for cls in (*CLASSES, ComponentRecord, PinnedIdentity, SyntheticOperatorModel,
                    SequenceReferenceMetadata, ValueDomain, OperatingDomain, TypeSpec):
            patches.enter_context(patch.object(cls, "from_dict", wrapper(cls)))
        try: CLASS_BY_NAME[operation].from_dict(value)
        except Exception as error:
            require({"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)} == expected_error,
                    "Native-boundary Python rejection differs from original: " + operation + ": " + str(error))
        else: raise AssertionError("Serialized constructor rejection was accepted: " + operation)
    require(observed, "Unobserved rejection leaf")
    return observed[0]


def expected_code(call, operation, value):
    if call["outcome"] == "returned": return None
    message = call["error"]["message"]
    if operation == "registry_resolve":
        require(message in {"Registry identity/version/content lock mismatch.",
            "Selected component identity/version/content lock mismatch.",
            "Model/reference/evidence dependency lock mismatch."}, "Unknown resolver rejection")
        return "component_registry"
    if operation == "reconstruct":
        require(message in {"A selected component lacks an executable synthetic model.",
            "Assembly observation bindings must cover every executable input exactly once.",
            "Assembly observation bindings must cover every executable output exactly once."}, "Unknown reconstructor rejection")
        return "component_model"
    require(operation in CLASS_BY_NAME, "Unclassified operation rejection: " + operation)
    cls, data, leaf_message = failure_leaf(operation, value, call["error"])
    name = cls.__name__
    def string_code(item, other="invalid_name"):
        return other if isinstance(item, str) else "invalid_type"
    def exact_fields():
        if not isinstance(data, dict): return "invalid_type"
        expected = {item.name for item in dataclass_fields(cls)}
        if hasattr(cls, "schema_version"): expected.add("schema_version")
        if name == "ComponentAssembly": expected.add("nodes")
        if name == "TypeSpec": expected = {"kind", "name", "dimensions", "arguments"}
        required = {"kind", "name"} if name == "TypeSpec" else expected
        if name == "PinnedIdentity" and set(data) - expected: return "unknown_field"
        if required - set(data): return "missing_field"
        if set(data) - expected: return "unknown_field"
        raise AssertionError("No exact-field difference at rejection leaf: " + name)
    if leaf_message.startswith("Invalid fields in ") or leaf_message == "A serialized type has missing or unknown fields.":
        return exact_fields()
    if "schema" in leaf_message.lower() and leaf_message.startswith("Unsupported"):
        return string_code(data["schema_version"], "unsupported_identity_schema" if name == "PinnedIdentity" else "unsupported_schema")
    if name == "TypeSpec":
        if not isinstance(data, dict): return "invalid_type"
        if leaf_message == "A type requires nonempty kind and name strings.":
            return "invalid_type" if not all(isinstance(data[k], str) for k in ("kind", "name")) else "invalid_type_spec"
        if leaf_message == "Type dimensions must be an object and arguments must be an array.": return "invalid_type"
        if leaf_message.startswith("Unknown type kind:"): return "invalid_type_spec"
    name_fields = {
        "Registry ID": "id" if name == "ComponentRegistry" else "registry_id", "Registry version": "version" if name == "ComponentRegistry" else "registry_version",
        "node_id": "node_id", "component_id": "component_id", "version": "version",
        "Identity ID": "id", "Identity version": "version", "Component id": "id", "Component version": "version",
        "Component implementation_role": "implementation_role", "Domain unit": "unit", "Unknown domain reason": "reason",
    }
    suffix = " must be a nonempty string."
    if leaf_message.endswith(suffix):
        label = leaf_message[:-len(suffix)]
        if label in name_fields: return string_code(data[name_fields[label]])
        if label in {"Component guarantees", "Component supported_targets"}:
            key = "guarantees" if label == "Component guarantees" else "supported_targets"
            invalid = next(item for item in data[key] if not isinstance(item, str) or not item.strip())
            return string_code(invalid)
    if leaf_message in {"A component lock requires a SHA-256 content identity.", "Registry fingerprint must be a SHA-256 identity."}:
        return string_code(data["content_fingerprint" if name == "ComponentLock" else "registry_fingerprint"], "component_registry")
    if leaf_message == "A pinned identity requires a SHA-256 content fingerprint.":
        return string_code(data["content_fingerprint"], "invalid_identity_fingerprint")
    if leaf_message == "Unsupported pinned identity kind.": return string_code(data["kind"], "invalid_identity_kind")
    if leaf_message == "Unsupported component classification.": return string_code(data["classification"], "component_record")
    if leaf_message == "Unsupported value domain kind.": return string_code(data["kind"], "component_contract")
    if leaf_message.endswith("must be an array.") or leaf_message.endswith("must be an object."):
        return "invalid_type"
    known = {
        "ComponentRegistry": {"Ambiguous dependency identity: one kind/ID/version has different hashes.", "Duplicate or ambiguous component ID/version in registry."},
        "ComponentAssembly": {"The component inventory must match the locked composition."},
        "ComponentRecord": {"A component must declare at least one supported target.", "A modeled component must pin its model identity."},
        "ValueDomain": {"Lower domain bound must be a finite number.", "Upper domain bound must be a finite number.",
            "Scalar intervals require a scalar type and no Boolean values/reason.", "Unknown domains cannot carry known bounds or Boolean values."},
        "ResourcePool": {"Resource capacity must be a finite nonnegative quantity or an allowed unknown."},
    }
    if leaf_message in known.get(name, set()):
        return {"ComponentRegistry": "component_registry", "ComponentAssembly": "component_assembly",
            "ComponentRecord": "component_record", "ValueDomain": "component_contract", "ResourcePool": "composition_record"}[name]
    if name == "ComponentAssembly" and leaf_message == "Registry identity/version/content lock mismatch.": return "component_registry"
    raise AssertionError("Unclassified original domain diagnostic: " + name + ": " + leaf_message)


def static_ledger():
    patches, calls = [], []
    tracked = {"run_component_model", "reconstruct_component_mechanism", "check_component_behavior",
               "check_component_assembly", "run_component_pipeline", "build_synthetic_package", "verify_synthetic_package"}
    for path in FILES:
        for node in ast.walk(ast.parse((ROOT / path).read_text())):
            if not isinstance(node, ast.Call): continue
            name = ast.unparse(node.func)
            if name.split(".")[-1] in tracked:
                calls.append({"file": path, "line": node.lineno, "call": name})
            if name not in ("patch", "patch.object"): continue
            expression = ast.unparse(node)
            if "PassManager" in expression:
                disposition = "original_provenance_assertion_retained; standalone_assembly_does_not_encode_PassResult_mutation"
            elif path == "tests/test_temporal_components.py":
                disposition = "original_independence_assertion_retained; native_dependency_gate_and_literals_are_counterpart"
            elif "socket.create_connection" in expression:
                disposition = "original_offline_assertion_retained; no_network_in_native_runtime"
            else:
                disposition = "original_workflow_assertion_retained; version_admission_reference_or_atomic_IO_not_standalone_runtime_mutation"
            patches.append({"file": path, "line": node.lineno, "expression": expression, "disposition": disposition})
    return {"callsites": sorted(calls, key=lambda x: (x["file"], x["line"])),
            "monkeypatches": sorted(patches, key=lambda x: (x["file"], x["line"]))}


def supplemental_cases(store):
    """New literal witnesses are kept distinct from the unchanged original ledger."""
    from dataclasses import replace
    from tools.freeze_components import executable, port
    from biocompiler.ir.component_contracts import PinnedIdentity, SyntheticOperatorModel
    from biocompiler.models.synthetic import MODEL_RUNNER_VERSION, ModelInputFrame
    from biocompiler.semantics.component_contracts import OperatingDomain
    from biocompiler.semantics.context import TargetContext, PayloadFormat
    from biocompiler.semantics.types import LEVEL
    records = {
        "left": replace(executable("input"), id="literal:left", ports=(port(dtype=LEVEL),)),
        "right": replace(executable("input"), id="literal:right", ports=(port(dtype=LEVEL),)),
        "compare": executable("compare"), "result": executable("output"),
    }
    records = {key: replace(value, identities=(PinnedIdentity("model", "literal-model", MODEL_RUNNER_VERSION, "a" * 64),))
               for key, value in records.items()}
    registry = ComponentRegistry("literal-comparison", "1", tuple(records.values()))
    lock = registry.lock(records)
    composition = CompositionRequest(TargetContext("literal", "1", PayloadFormat.RNA,
        capabilities=("synthetic_signal_graph",)), lock,
        tuple(CompositionInstance(item.node_id, item, OperatingDomain(), requirement_ids=("comparison",)) for item in lock.components),
        (Connection("left", "out", "compare", "in0"), Connection("right", "out", "compare", "in1"),
         Connection("compare", "out", "result", "in0")), requirement_ids=("comparison",))
    assembly = ComponentAssembly(registry, composition, "b" * 64, "c" * 64,
        {key: ("literal-source:" + key,) for key in records},
        ObservationMap((InputBinding("left", "value", "left"), InputBinding("right", "value", "right")),
                       (OutputBinding("comparison", "result"),)))
    history = (ModelInputFrame(0, {"left": 0, "right": 1}), ModelInputFrame(1, {"left": 1, "right": 1}))
    mechanism = reconstruct_component_mechanism(assembly)
    trace = run_component_model(assembly, history, until=1)
    require([frame.values["result"] for frame in trace.frames] == [False, True], "Comparison literal does not witness both results")
    case = {"id": "new_literal_compare_equal", "origin": "explicit_new_literal_not_original_assertion",
        "assembly": store.retain("record", plain(assembly)), "mechanism": store.retain("record", plain(mechanism)),
        "runtime_input": store.retain("record", {"history": plain(history), "until": 1}),
        "trace": store.retain("record", plain(trace))}
    raw = deepcopy(records["compare"].synthetic_model.to_dict()); raw["operation"] = "delay"
    try: SyntheticOperatorModel.from_dict(raw)
    except Exception as error:
        rejection = {"id": "new_literal_delay_not_component_operation", "origin": "explicit_new_literal_not_original_assertion",
            "input": store.retain("record", raw), "expected_code": "component_record",
            "error": {"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}}
    else: raise AssertionError("Component profile unexpectedly accepted delay")
    return [case], [rejection]


def freeze(document, *, check=False):
    require(document["schema_version"] == "biocompiler.component_runtime_baseline_capture.v1", "Wrong captured schema")
    require(document["source_files"] == source_inventory(), "Captured authority source files are stale")
    store = Store()
    for identity, record in document["documents"].items():
        require(store.retain(record["kind"], record["value"]) == identity, "Captured document identity changed")
    locations, location_ids, grouped, context_order = [], {}, {}, []
    stages, operations, outcomes = Counter(), Counter(), Counter()
    for original in document["api_calls"]:
        context = original["source_test"]
        if context not in grouped: grouped[context] = []; context_order.append(context)
        number = len(grouped[context])
        require(original["id"] == context + "/api/" + str(number), "Original API order changed")
        parent = original["parent_call"]
        if parent is not None:
            require(parent.startswith(context + "/api/"), "Cross-context nesting requires an explicit new representation")
            parent = int(parent.rsplit("/", 1)[1]); require(parent < number, "Unobserved API parent")
        location_key = canonical(original["source"])
        if location_key not in location_ids:
            location_ids[location_key] = len(locations); locations.append(original["source"])
        call = {"api": original["api"], "parent": parent, "source": location_ids[location_key],
            "input": original["input"], "python_types": store.retain("python_types", original["python_types"]),
            "outcome": original["outcome"]}
        for key in ("result", "error", "reconstruction_call"):
            if key in original: call[key] = original[key]
        operation, raw, stage = observation_input(original, document["documents"])
        if stage == "json_import":
            input_format, identity = "json_text", store.retain("json_text", raw)
            parsed = json.loads(raw)
        else:
            parsed = raw
            try: identity = store.retain("record", raw); input_format = "record"
            except ValueError:
                require(original["outcome"] == "raised", "Successful nonfinite input is unsupported")
                identity = store.retain("json_text", json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True))
                input_format = "json_text"
        code = expected_code(original, operation, parsed)
        native_stage = "runtime" if stage == "runtime" else "reconstruction" if stage == "reconstruction" else "registry" if stage == "operation" else "domain"
        if input_format == "json_text":
            def nonfinite(token): raise ValueError(token)
            try: json.loads(store.records[identity]["value"], parse_constant=nonfinite)
            except ValueError:
                require(code == "composition_record", "Unreviewed nonfinite rejection")
                code, native_stage = "invalid_json", "wire"
        call["native"] = {"operation": operation, "input": identity, "input_format": input_format,
            "source_stage": stage, "native_stage": native_stage, "expected_code": code}
        stages[native_stage] += 1; operations[operation] += 1; outcomes[original["outcome"]] += 1
        grouped[context].append(call)
    contexts = []
    for original in document["contexts"]:
        calls = grouped.get(original["id"], [])
        require(original["api_calls"] == [original["id"] + "/api/" + str(i) for i in range(len(calls))], "Incomplete context calls")
        contexts.append({**original, "api_calls": len(calls), "ledger": store.retain("api_ledger", {"observations": calls})})
    supplemental, rejections = supplemental_cases(store)
    original_kinds = document["coverage"]["successful_reconstruction_kinds"]
    require(original_kinds == sorted(set(KINDS) - {"compare"}), "Original operation coverage changed")
    require(sorted(set(original_kinds) | {"compare"}) == KINDS, "Incomplete component operation coverage")
    index = {"schema_version": "biocompiler.component_runtime_conformance.v1",
        "claim_scope": "locked_component_identity_reconstruction_and_digital_execution_only_no_acceptance_or_biology",
        "source_files": document["source_files"], "source_ledger": static_ledger(), "contexts": contexts,
        "source_locations": locations, "capture_context_order": context_order,
        "original_documents": sorted(document["documents"]),
        "original_capture_fingerprint": digest(canonical(document)),
        "supplemental": supplemental, "supplemental_rejections": rejections,
        "coverage": {**document["coverage"], "native_stages": dict(sorted(stages.items())),
            "native_operations": dict(sorted(operations.items())), "unclassified_observations": 0,
            "supplemental_successes": len(supplemental), "supplemental_rejections": len(rejections)},
        "compatibility": {"original_assertions": "all 163 methods executed unchanged both before and during observation; no skipped assertions",
            "source_locations": "before construction, absolute checkout paths map to /__biocompiler_capture__/ plus relative path; temporal_pipeline.py retains its own original relative authoring policy; relative paths unchanged",
            "python_types": "full JSON contents plus original typed-record, tuple and nonstandard mapping identities; no JSON numeric equality normalization",
            "nested_calls": "every observed call retained; compact per-context numbers reconstruct exact original IDs and parent links",
            "domain_failures": "exact original type/message retained; explicit native diagnostic category at actual nested decoder boundary",
            "nonfinite": "raw Python JSON NaN/Infinity text preserved; strict native JSON boundary rejects before domain import",
            "monkeypatches": "original assertions executed; workflow-only mutations never fabricated into standalone assembly cases",
            "subprocesses": "none observed; new child execution fails capture until actual child instrumentation is implemented"}}
    payloads = {identity: canonical(record["value"]) + b"\n" for identity, record in store.records.items()}
    index["documents"] = [{"id": identity, "kind": store.records[identity]["kind"], "bytes": len(payload)}
        for identity, payload in sorted(payloads.items())]
    index["inventory_fingerprint"] = digest(canonical(index))
    payload = canonical(index) + b"\n"
    total = len(payload) + sum(map(len, payloads.values()))
    require(total <= MAX_TOTAL_BYTES, "Complete component corpus exceeds reviewed storage ceiling: " + str(total))
    directory = CORPUS.with_suffix("")
    if check:
        require(CORPUS.read_bytes() == payload, "Fresh original capture differs from pinned corpus")
        require({p.name for p in directory.iterdir()} == {key + ".json" for key in payloads}, "Missing or extra retained document")
        for identity, value in payloads.items(): require((directory / (identity + ".json")).read_bytes() == value, "Retained document differs")
    else:
        require(not directory.exists() or not any(directory.iterdir()), "Refuse to overwrite existing corpus; use --check")
        directory.mkdir(parents=True, exist_ok=True)
        for identity, value in payloads.items(): (directory / (identity + ".json")).write_bytes(value)
        CORPUS.write_bytes(payload)
    print(json.dumps({"inventory_fingerprint": index["inventory_fingerprint"], "documents": len(payloads),
        "bytes": total, "api_calls": len(document["api_calls"]), "coverage": index["coverage"]}, sort_keys=True))
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--captured", type=Path, help="reuse complete raw capture during development")
    parser.add_argument("--check", action="store_true", help="freshly recapture original assertions and compare every retained byte")
    args = parser.parse_args()
    import biocompiler.frontend.graph as graph
    source_location = graph.SourceLocation
    def portable(file, line, function):
        path = Path(file)
        # Preserve absolute-vs-relative semantics: original package tests
        # deliberately reject absolute authoring locations. Only the physical
        # checkout prefix is fixed, before any source or identity is built.
        relative = path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file
        # This original example immediately resolves against its physical
        # repository and freezes this exact relative path itself. Preserve
        # that authoring-time normalization instead of substituting a foreign
        # absolute prefix before its relative_to check.
        filename = (relative if relative == "examples/temporal_pipeline.py" else
                    "/__biocompiler_capture__/" + relative if path.is_absolute() else file)
        return source_location(filename, line, function)
    # Load original modules even when reviewing saved observations, so their
    # transitive source inventory is checked against the captured authority.
    if args.captured:
        for path in FILES: load(path)
        document = json.loads(args.captured.read_bytes())
    else:
        with patch.object(graph, "SourceLocation", portable): document = capture()
    if not args.capture_only: freeze(document, check=args.check)
    return document


if __name__ == "__main__":
    main()
