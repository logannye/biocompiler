#!/usr/bin/env python3
"""Retain unchanged realization-domain, evidence and admission observations.

Capture includes future acceptance callers as explicitly separate observations;
domain or admission parity never claims the finite-history checker is ported.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import MISSING, fields as dataclass_fields
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from tools.freeze_component_runtime import canonical, digest, require, load, inventory
from biocompiler.semantics.types import _ScalarType
from biocompiler.semantics.realization import (
    Observable, InputDomain, OperatingDomain, ResponseRequirement, BehaviorContract)
from biocompiler.verification.evidence import (
    DependencySnapshot, FreshnessReport, CheckDiagnostic, Counterexample,
    RequirementCoverage, CheckResult)
from biocompiler.semantics.admission import AdmissionRequest, AdmissionAssessment
from biocompiler.verification.admission import (
    assess_admission, verify_admission, admission_for_target, require_software_use)
from biocompiler.verification.realization import check_realization, realization_dependencies
from biocompiler.compiler.components import check_component_behavior, check_component_assembly

OUT = ROOT / "generated/migration-next/realization-acceptance-capture"
FILES = tuple("tests/" + name + ".py" for name in (
    "test_realization_contracts", "test_realization_checker", "test_realization_integration",
    "test_verification_mutations", "test_build_request", "test_verification_exploration",
    "test_component_pipeline", "test_component_pipeline_audit", "test_temporal_components",
    "test_synthetic_design_workflows", "test_component_registry", "test_component_linker",
    "test_component_audit", "test_component_adapters", "test_synthetic_build", "test_human_admission",
    "test_construct_assembly", "test_construct_checker", "test_synthetic_generation",
    "test_temporal_generation", "test_synthetic_selection", "test_synthetic_verification_workflow",
    "test_molecular_behavior"))
METHOD_COUNTS = [13,31,6,7,22,14,9,7,15,8,11,30,12,5,11,33,10,12,17,15,15,10,11]
CLASSES = (Observable, InputDomain, OperatingDomain, ResponseRequirement, BehaviorContract,
    DependencySnapshot, FreshnessReport, CheckDiagnostic, Counterexample, RequirementCoverage,
    CheckResult, AdmissionRequest, AdmissionAssessment)
CLASS_BY_NAME = {cls.__name__: cls for cls in CLASSES}
SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in CLASSES}
CLASS_IMPORT_METHODS = {}
PROPERTY_NAMES = ("fingerprint", "passed", "exercised_requirement_ids", "fresh", "status")
CHILD_MODULE = "tools.freeze_realization_acceptance"
FUNCTIONS = (assess_admission, verify_admission, admission_for_target, require_software_use,
    realization_dependencies, check_realization, check_component_behavior, check_component_assembly)
METHODS = {InputDomain: ("contains",), ResponseRequirement: ("accepts",),
    DependencySnapshot: ("changed",), CheckResult: ("freshness", "is_fresh"),
    AdmissionAssessment: ("is_current",)}
MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
CORPUS = ROOT / "tests/conformance/realization-foundation-v1.json"
CORPUS_SCHEMA = "biocompiler.realization_foundation_conformance.v1"
CLAIM_SCOPE = "realization_domain_evidence_identity_and_fresh_admission_only_no_finite_history_acceptance_or_biology"
DEFERRED_OBLIGATION = "independent_complete_finite_history_acceptance_not_implemented_by_foundation"
NATIVE_STAGE_BY_OPERATION = {}
DEFERRED = {"realization_dependencies", "check_realization", "check_component_behavior", "check_component_assembly"}


def plain(value):
    if type(value) is type(iter(())):
        # Built-in tuple iterators expose their immutable backing tuple and
        # current offset without consuming or replacing the original iterator.
        factory, arguments, offset = value.__reduce__()
        require(factory is iter and len(arguments) == 1 and type(arguments[0]) is tuple
                and type(offset) is int and 0 <= offset <= len(arguments[0]),
                "Unexpected tuple iterator snapshot")
        return plain(arguments[0][offset:])
    if isinstance(value, type) and issubclass(value, _ScalarType) and value is not _ScalarType:
        return value._spec.to_dict()
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if isinstance(value, FreshnessReport):
        return {"changed_dependencies": plain(value.changed_dependencies)}
    if isinstance(value, Mapping):
        require(all(isinstance(key, str) for key in value), "Non-string input keys need explicit capture")
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise AssertionError(f"Uncaptured realization argument: {type(value).__module__}.{type(value).__qualname__}")


def python_types(value, path=()):
    kind = type(value)
    if isinstance(value, type):
        return [{"path": list(path), "type": "python_type", "value": value.__module__ + "." + value.__qualname__}]
    if hasattr(value, "to_dict") or isinstance(value, FreshnessReport):
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
        require(len(payload) + 1 <= MAX_DOCUMENT_BYTES, "Individual realization document exceeds storage bound")
        identity = digest(payload)
        if identity in self.records:
            require(self.records[identity]["kind"] == kind, "Cross-kind realization document collision")
        else:
            self.records[identity] = {"kind": kind, "value": value}
            self.size += len(payload) + 1
            require(self.size <= MAX_TOTAL_BYTES, "Complete realization documents exceed reviewed storage bound")
        return identity


def source_inventory():
    paths = set(FILES)
    for directory in (ROOT / "src/biocompiler", ROOT / "examples"):
        paths.update(path.relative_to(ROOT).as_posix() for path in directory.rglob("*.py"))
    for module in tuple(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve().parent == ROOT / "tests":
            paths.add(Path(file).resolve().relative_to(ROOT).as_posix())
    return [{"path": path, "sha256": digest((ROOT / path).read_bytes())} for path in sorted(paths)]


@contextmanager
def portable_sources():
    import biocompiler.frontend.graph as graph
    source_location = graph.SourceLocation
    def portable(file, line, function):
        path = Path(file)
        relative = path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file
        filename = (relative if relative == "examples/temporal_pipeline.py" else
                    "/__biocompiler_capture__/" + relative if path.is_absolute() else file)
        return source_location(filename, line, function)
    with patch.object(graph, "SourceLocation", portable):
        yield


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
        with log_path.open("w") as logs:
            baseline = unittest.TextTestRunner(stream=logs, verbosity=2).run(unittest.TestSuite(
                test for module in modules for test in inventory(module)))
        require(baseline.wasSuccessful() and baseline.testsRun == sum(METHOD_COUNTS) and not baseline.skipped,
                "Uninstrumented original assertions failed: " + str(log_path))
        print(f"realization capture: all {sum(METHOD_COUNTS)} uninstrumented original methods passed", flush=True)
    store, calls, ledger, fixtures, children = Store(), [], [], {}, []
    current = {"id": child_context["id"] if child_context else None, "api_calls": [],
               "assertion_status": "passed", "kind": "subprocess" if child_context else "original_method"}
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
        if child_context is not None: return child_context["source"]
        raise AssertionError("Observed realization call has no original test source")

    def begin(api, args, kwargs):
        source = callsite()
        context = current if current["id"] else fixtures.setdefault(
            source["file"] + "::fixture." + source["function"],
            {"id": source["file"] + "::fixture." + source["function"], "api_calls": [],
             "assertion_status": "passed", "kind": "class_fixture"})
        identity = context["id"] + "/api/" + str(len(context["api_calls"]))
        raw = {"args": plain(args), "kwargs": plain(kwargs)}
        raw_text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
        entry = {"id": identity, "source_test": context["id"], "api": api, "source": source,
            "parent_call": stack[-1] if stack else None, "input": store.retain("raw_arguments", raw_text),
            "python_types": python_types({"args": args, "kwargs": kwargs})}
        calls.append(entry); context["api_calls"].append(identity); stack.append(identity)
        return entry

    def success(entry, value):
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
            for name in PROPERTY_NAMES:
                if hasattr(type(value), name):
                    properties[name] = plain(getattr(value, name))
            if properties: entry["properties"] = store.retain("record", properties)

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

    def importer(cls, method):
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
            entry = begin(api, args, kwargs)
            try:
                result = original(*args, **kwargs); success(entry, result); return result
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
            with log_path.open("a") as logs:
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
    document = {"schema_version": "biocompiler.realization_acceptance_baseline_capture.v1",
        "source_files": sources, "contexts": contexts, "subprocesses": children, "api_calls": calls,
        "documents": store.records, "coverage": coverage}
    if child_script is not None: return document
    payload = canonical(document) + b"\n"
    (OUT / "capture.json").write_bytes(payload)
    receipt = {"capture_sha256": digest(payload), "bytes": len(payload), "generator_sha256": digest(Path(__file__).read_bytes()),
        "support_sha256": digest((ROOT / "tools/freeze_component_runtime.py").read_bytes()),
        "python": sys.version, "platform": platform.platform(), "baseline_tests": baseline.testsRun,
        "captured_tests": observed.testsRun, "coverage": coverage}
    (OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return document


def child_main(script, context, output):
    with portable_sources(): result = capture(script, context)
    Path(output).write_bytes(canonical(result))


def constructor_document(name, raw):
    cls = CLASS_BY_NAME[name]
    bound = SIGNATURES[name].bind(*raw["args"], **raw["kwargs"])
    bound.apply_defaults()
    result = plain(dict(bound.arguments))
    if name == "DependencySnapshot": return result["values"]
    for field in dataclass_fields(cls):
        if field.name not in result:
            if field.default is not MISSING: result[field.name] = plain(field.default)
            elif field.default_factory is not MISSING: result[field.name] = plain(field.default_factory())
            else: raise AssertionError("Missing constructor field: " + name + "." + field.name)
    if hasattr(cls, "schema_version") and "schema_version" not in result: result["schema_version"] = cls.schema_version
    result.update(getattr(cls, "_fixed_fields", {}))
    return result


def observation_input(call, documents):
    raw = json.loads(documents[call["input"]]["value"])
    api = call["api"]
    if api in DEFERRED: return api, raw, "deferred_acceptance"
    if "." not in api:
        function = next(value for value in FUNCTIONS if value.__name__ == api)
        bound = inspect.signature(function).bind(*raw["args"], **raw["kwargs"]); bound.apply_defaults()
        # Explicit transport selection was added after this historical semantic
        # capture. Its absent/None default is not part of original authority.
        if api in {"realization_dependencies", "check_realization", "check_synthetic_candidate", "check_component_behavior", "check_component_assembly"} and bound.arguments.get("core") is None:
            bound.arguments.pop("core", None)
        return api, plain(dict(bound.arguments)), "admission"
    name, method = api.split(".")
    if method == "__init__": return name, constructor_document(name, raw), "constructor"
    if method in ("from_dict", "from_json"):
        require(len(raw["args"]) == 1 and not raw["kwargs"], "New import signature")
        return name, raw["args"][0], "json_import" if method == "from_json" else "record_import"
    if method in ("contains", "accepts"):
        require(len(raw["args"]) == 2 and set(raw["kwargs"]) <= {"active"}, "New membership signature")
        scalar = any(item["path"] == ["args", 1] and item["type"] == "biocompiler.semantics.types.ScalarLiteral" for item in call["python_types"])
        return api, {"subject": raw["args"][0], "value": raw["args"][1],
            "value_kind": "scalar_literal" if scalar else "json", **raw["kwargs"]}, "method"
    require(method in ("changed", "freshness", "is_fresh", "is_current") and len(raw["args"]) == 2 and not raw["kwargs"], "New identity method")
    return api, {"subject": raw["args"][0], "current": raw["args"][1]}, "method"


def strict_input(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate_key")
            result[key] = value
        return result
    def invalid(_): raise ValueError("invalid_json")
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
        canonical(result)
    except UnicodeEncodeError as error: raise ValueError("invalid_json") from error
    return result


def python_decode(operation, value):
    if operation in CLASS_BY_NAME:
        if operation == "DependencySnapshot": return DependencySnapshot(value)
        if operation == "FreshnessReport": return FreshnessReport(**value)
        return CLASS_BY_NAME[operation].from_dict(value)
    if operation in ("InputDomain.contains", "ResponseRequirement.accepts"):
        from biocompiler.semantics.types import TypeSpec, decode_binding
        name, method = operation.split(".")
        subject = CLASS_BY_NAME[name].from_dict(value["subject"])
        sample = value["value"]
        if value["value_kind"] == "scalar_literal": sample = decode_binding(sample, TypeSpec.from_dict(sample["type"]))
        return getattr(subject, method)(sample, **({"active": value["active"]} if method == "accepts" else {}))
    if operation in ("DependencySnapshot.changed", "CheckResult.freshness", "CheckResult.is_fresh"):
        name, method = operation.split(".")
        subject = python_decode(name, value["subject"])
        return getattr(subject, method)(DependencySnapshot(value["current"]))
    if operation == "AdmissionAssessment.is_current":
        return AdmissionAssessment.from_dict(value["subject"]).is_current(AdmissionRequest.from_dict(value["current"]))
    if operation == "assess_admission": return assess_admission(AdmissionRequest.from_dict(value["request"]))
    if operation == "verify_admission": return verify_admission(AdmissionRequest.from_dict(value["request"]), AdmissionAssessment.from_dict(value["assessment"]))
    if operation in ("admission_for_target", "require_software_use"):
        from biocompiler.semantics.context import TargetContext
        from biocompiler.ir.component_contracts import ComponentRecord
        function = admission_for_target if operation == "admission_for_target" else require_software_use
        return function(TargetContext.from_dict(value["target"]), boundary=value["boundary"],
            components=tuple(ComponentRecord.from_dict(item) for item in value["components"]))
    raise AssertionError("Unclassified native operation: " + operation)


def evidence_code(call, operation, value):
    if call["outcome"] == "returned": return None
    message = call["error"]["message"]
    def exact(data, keys):
        if not isinstance(data, dict): return "invalid_type"
        if set(keys) - set(data): return "missing_field"
        if set(data) - set(keys): return "unknown_field"
        raise AssertionError("No evidence exact-field mismatch")
    if message == "Invalid check schema or scope.":
        if not isinstance(value["schema_version"], str): return "invalid_type"
        if value["schema_version"] != CheckResult.__dataclass_fields__["schema_version"].default: return "unsupported_schema"
        return "realization_evidence" if isinstance(value["claim_scope"], str) else "invalid_type"
    if message.startswith("Invalid check result:"):
        key = "outcome" if "CheckOutcome" in message else "evidence_kind"
        require("CheckOutcome" in message or "EvidenceKind" in message, "New enum rejection")
        return "realization_evidence" if isinstance(value[key], str) else "invalid_type"
    if message == "Dependencies must contain the complete checker input and tool inventory.":
        data = value["dependencies"] if operation == "CheckResult" else value
        return exact(data, {"behavior", "behavior_artifact", "contract", "domain", "target", "mechanism", "observation_map", "history", "horizon", "checker", "model_runner", "reference_evaluator", "settings"})
    if message == "Invalid checked requirements.":
        values = value["checked_requirement_ids"]
        if not isinstance(values, list): return "invalid_type"
        bad = next(item for item in values if not isinstance(item, str) or not item.strip())
        return "invalid_name" if isinstance(bad, str) else "invalid_type"
    if message == "Check details must be arrays.": return "invalid_type"
    if message.startswith("Invalid counterexample range:"):
        if message.endswith("A serialized type must be an object."): return "invalid_type"
        if message.endswith("A scalar binding's canonical value disagrees with its value and unit."): return "canonical_value_mismatch"
        raise AssertionError("Unclassified counterexample range rejection: " + message)
    if message == "Invalid check artifact fields.":
        candidates = [(operation, value)]
        if operation == "CheckResult": candidates += [("Counterexample", item) for item in value.get("counterexamples", [])]
        for name, data in candidates:
            keys = {field.name for field in dataclass_fields(CLASS_BY_NAME[name])}
            if not isinstance(data, dict) or set(data) != keys: return exact(data, keys)
            if name == "Counterexample" and (not isinstance(data["expected"], dict) or set(data["expected"]) != {"state", "range"}):
                return exact(data["expected"], {"state", "range"})
        raise AssertionError("Unlocated exact evidence fields")
    known = {"A passing result requires exercised active and inactive deadlines and complete response coverage.",
        "Counterexample refers to an unknown requirement.", "Counterexample state must be active or inactive.",
        "Counterexample actual must be a finite canonical scalar or null for a missing output.",
        "A passing check must identify checked requirements.", "This checker only reports model-conditional evidence."}
    require(message in known, "Unclassified evidence diagnostic: " + operation + ": " + message)
    if message == "Counterexample state must be active or inactive.":
        data = value["counterexamples"][0] if operation == "CheckResult" else value
        return "realization_evidence" if isinstance(data["expected"]["state"], str) else "invalid_type"
    return "realization_evidence"


def expected_code(call, operation, value):
    if operation.split(".")[0] in {"Observable", "InputDomain", "OperatingDomain", "ResponseRequirement", "BehaviorContract"}:
        from tools.realization_contract_codes import expected_code as classify
        return classify(call, operation, value)
    if operation.startswith("Admission") or operation in {"assess_admission", "verify_admission", "admission_for_target", "require_software_use"}:
        from tools.realization_admission_codes import expected_code as classify
        return classify(call, operation, value)
    return evidence_code(call, operation, value)


def static_ledger():
    calls, patches = [], []
    names = {function.__name__ for function in FUNCTIONS}
    for path in FILES:
        for node in ast.walk(ast.parse((ROOT / path).read_text())):
            if not isinstance(node, ast.Call): continue
            name = ast.unparse(node.func)
            if name.split(".")[-1] in names: calls.append({"file": path, "line": node.lineno, "call": name})
            if name in ("patch", "patch.object"):
                patches.append({"file": path, "line": node.lineno, "expression": ast.unparse(node),
                    "disposition": "original_assertion_retained; workflow_mutation_is_not_fabricated_as_standalone_domain_or_admission_input"})
    return {"callsites": sorted(calls, key=lambda x: (x["file"], x["line"])),
        "monkeypatches": sorted(patches, key=lambda x: (x["file"], x["line"]))}


def freeze(document, *, check=False):
    require(document["schema_version"] == "biocompiler.realization_acceptance_baseline_capture.v1", "Wrong captured schema")
    require(document["source_files"] == source_inventory(), "Captured authority source files are stale")
    store = Store()
    for identity, record in document["documents"].items():
        require(store.retain(record["kind"], record["value"]) == identity, "Captured document changed")
    locations, location_ids, grouped, order = [], {}, {}, []
    stages, operations = Counter(), Counter()
    for original in document["api_calls"]:
        context = original["source_test"]
        if context not in grouped: grouped[context] = []
        number = len(grouped[context]); order.append([context, number])
        require(original["id"] == context + "/api/" + str(number), "Original call order changed")
        parent = original["parent_call"]
        if parent is not None:
            require(parent.startswith(context + "/api/"), "Unrepresented cross-context parent")
            parent = int(parent.rsplit("/", 1)[1]); require(parent < number, "Unobserved call parent")
        key = canonical(original["source"])
        if key not in location_ids: location_ids[key] = len(locations); locations.append(original["source"])
        call = {"api": original["api"], "parent": parent, "source": location_ids[key], "input": original["input"],
            "python_types": store.retain("python_types", original["python_types"]), "outcome": original["outcome"]}
        for key in ("result", "result_format", "error", "properties"):
            if key in original: call[key] = original[key]
        operation, value, source_stage = observation_input(original, document["documents"])
        if source_stage == "deferred_acceptance":
            call["native"] = {"operation": operation, "source_stage": source_stage, "native_stage": "deferred_acceptance",
                "obligation": DEFERRED_OBLIGATION}
        else:
            text = value if source_stage == "json_import" else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
            identity = digest(canonical(text))
            input_format = store.records.get(identity, {}).get("kind", "json_text")
            require(input_format in {"json_text", "python_json_text"}, "Unexpected text identity alias")
            identity = store.retain(input_format, text)
            stage = NATIVE_STAGE_BY_OPERATION.get(operation,
                "admission" if source_stage == "admission" else "method" if source_stage == "method" else "domain")
            try: parsed = strict_input(text)
            except ValueError as error:
                code = str(error)
                require(code in {"duplicate_key", "invalid_json"}, "Unclassified strict wire failure")
                stage = "wire" if original["outcome"] == "raised" else "python_wire_boundary"
            else:
                code = expected_code(original, operation, parsed)
                if source_stage == "constructor" and original["outcome"] == "raised" and code != "python_type_boundary":
                    # The importer may reject at a different typed boundary
                    # from the original direct constructor. Retain both exact
                    # errors; never relabel either or claim their text matches.
                    try: python_decode(operation, parsed)
                    except Exception as error:
                        serialized = {"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}
                        if serialized != original["error"]: call["serialized_error"] = serialized
                    else: raise AssertionError("Unclassified valid serialized constructor counterpart: " + original["id"])
                if code == "python_type_boundary":
                    stage = "python_type_boundary"
                    try:
                        result = python_decode(operation, parsed)
                    except Exception as error:
                        counterpart = {"outcome": "raised", "error": {"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}}
                        code = expected_code({**original, **counterpart}, operation, parsed)
                        require(code != "python_type_boundary", "Recursive typed counterpart")
                    else:
                        counterpart = {"outcome": "returned", "result": store.retain("record", plain(result))}; code = None
                    call["counterpart"] = counterpart
            call["native"] = {"operation": operation, "input": identity, "input_format": input_format,
                "source_stage": source_stage, "native_stage": stage, "expected_code": code}
        stages[call["native"]["native_stage"]] += 1; operations[operation] += 1
        grouped[context].append(call)
    contexts = []
    for original in document["contexts"]:
        calls = grouped.get(original["id"], [])
        require(original["api_calls"] == [original["id"] + "/api/" + str(i) for i in range(len(calls))], "Incomplete context ledger")
        contexts.append({**original, "api_calls": len(calls), "ledger": store.retain("api_ledger", {"observations": calls})})
    context_ids = {item["id"]: index for index, item in enumerate(contexts)}
    index = {"schema_version": CORPUS_SCHEMA,
        "claim_scope": CLAIM_SCOPE,
        "source_files": document["source_files"], "source_ledger": static_ledger(), "contexts": contexts,
        "source_locations": locations, "capture_call_order": store.retain("call_order", [[context_ids[context], number] for context, number in order]),
        "subprocesses": document["subprocesses"], "original_documents": sorted(document["documents"]),
        "original_capture_fingerprint": digest(canonical(document)),
        "coverage": {**document["coverage"], "native_stages": dict(sorted(stages.items())),
            "native_operations": dict(sorted(operations.items())), "unclassified_observations": 0},
        "compatibility": {
            "original_assertions": f"all{sum(METHOD_COUNTS)}originalmethods_run_unchanged_before_and_during_capture_no_skips",
            "source_locations": "absolute_checkout_prefix_mapped_before_construction_to_/__biocompiler_capture__/_relative_unchanged_temporal_pipeline_original_relative_policy_preserved",
            "python_types": "complete_raw_arguments_typed_records_scalar_classes_tuple_iterators_and_mapping_identities_retained",
            "hashes": "fixture_content_addresses_UTF8_canonical;_legacy_evidence_properties_compact_ensure_ascii_True",
            "deferred_acceptance": "all_complete_inputs_outcomes_and_nested_calls_retained_but_future_acceptance_operations_are_not_native_parity",
            "python_boundaries": "nonfinite_duplicate_and_unpaired_surrogate_inputs_reject_at_wire;_Python_only_constructor_type_checks_and_returned_surrogates_are_explicit_boundary_observations;_distinct_constructor_and_import_error_texts_are_both_retained",
            "subprocesses": "both_actual_original_children_instrumented_with_script_hashseed_stdout_stderr_returncode_and_all_nested_calls"}}
    payloads = {identity: canonical(record["value"]) + b"\n" for identity, record in store.records.items()}
    index["documents"] = [{"id": identity, "kind": store.records[identity]["kind"], "bytes": len(payload)} for identity, payload in sorted(payloads.items())]
    index["inventory_fingerprint"] = digest(canonical(index)); payload = canonical(index) + b"\n"
    total = len(payload) + sum(map(len, payloads.values())); require(total <= MAX_TOTAL_BYTES, "Corpus exceeds bounded storage")
    directory = CORPUS.with_suffix("")
    if check:
        require(CORPUS.read_bytes() == payload, "Fresh full capture differs from corpus")
        require({path.name for path in directory.iterdir()} == {key + ".json" for key in payloads}, "Missing or extra corpus file")
        for identity, value in payloads.items(): require((directory / (identity + ".json")).read_bytes() == value, "Corpus document differs")
    else:
        require(not directory.exists() or not any(directory.iterdir()), "Refuse to overwrite corpus; use --check")
        directory.mkdir(parents=True, exist_ok=True)
        for identity, value in payloads.items(): (directory / (identity + ".json")).write_bytes(value)
        CORPUS.write_bytes(payload)
    print(json.dumps({"inventory_fingerprint": index["inventory_fingerprint"], "capture_fingerprint": index["original_capture_fingerprint"],
        "documents": len(payloads), "bytes": total, "coverage": index["coverage"]}, sort_keys=True), flush=True)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--captured", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.captured:
        for path in FILES: load(path)
        document = json.loads(args.captured.read_bytes())
    else:
        with portable_sources(): document = capture()
    if not args.capture_only: freeze(document, check=args.check)


if __name__ == "__main__":
    main()
