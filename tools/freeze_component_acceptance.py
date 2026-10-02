#!/usr/bin/env python3
"""Retain original complete composition acceptance and component selection calls.

This isolated capture profile retains the original assertions and both actual
subprocesses. The existing domain/runtime/realization corpora remain separate
mandatory gates. Component source-correspondence calls remain explicitly deferred.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
from biocompiler.registry.components import (
    ComponentRegistry, SelectionRequest, SelectionAlternative, SelectionResult)
from biocompiler.verification.components import (
    LinkDiagnostic, ResolvedDependency, ResourceUsage, CompositionResult,
    composition_dependencies, check_composition)
from biocompiler.compiler.components import check_component_behavior, check_component_assembly

_module_name = "tools._component_acceptance_capture"
_spec = importlib.util.spec_from_file_location(_module_name, ROOT / "tools/freeze_realization_acceptance.py")
assert _spec is not None and _spec.loader is not None
foundation = importlib.util.module_from_spec(_spec)
sys.modules[_module_name] = foundation
_spec.loader.exec_module(foundation)


def configure():
    foundation.FILES = (*foundation.FILES,
        "tests/test_checked_pipeline.py", "tests/test_m9_admission_audit.py",
        "tests/test_circuit_checker_independence.py", "tests/test_component_admission.py",
        "tests/test_component_pipeline_manager.py", "tests/test_pipeline.py")
    foundation.METHOD_COUNTS = [*foundation.METHOD_COUNTS, 6, 6, 4, 10, 2, 21]
    foundation.CLASSES = (ComponentRegistry, SelectionRequest, SelectionAlternative,
        SelectionResult, LinkDiagnostic, ResolvedDependency, ResourceUsage, CompositionResult)
    foundation.CLASS_BY_NAME = {cls.__name__: cls for cls in foundation.CLASSES}
    foundation.SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in foundation.CLASSES}
    foundation.CLASS_IMPORT_METHODS = {}
    foundation.METHODS = {ComponentRegistry: ("select", "verify_selection"),
        CompositionResult: ("freshness", "is_fresh")}
    foundation.FUNCTIONS = (composition_dependencies, check_composition,
        check_component_behavior, check_component_assembly)
    foundation.PROPERTY_NAMES = ("fingerprint", "passed", "outcome", "status")
    foundation.CHILD_MODULE = "tools.freeze_component_acceptance"
    foundation.OUT = ROOT / "generated/migration-next/component-acceptance-capture"
    foundation.CORPUS = ROOT / "tests/conformance/component-acceptance-v1.json"
    foundation.CORPUS_SCHEMA = "biocompiler.component_acceptance_conformance.v1"
    foundation.CLAIM_SCOPE = "generic_composition_selection_and_actual_component_behavior_only_no_source_correspondence_or_biology"
    foundation.DEFERRED = {"check_component_assembly"}
    foundation.DEFERRED_OBLIGATION = "independent_source_to_component_correspondence_remains_unimplemented"
    foundation.NATIVE_STAGE_BY_OPERATION = {"composition_dependencies": "dependencies",
        "check_composition": "composition", "ComponentRegistry.select": "selection",
        "ComponentRegistry.verify_selection": "selection_replay", "check_component_behavior": "component_behavior",
        "admission_policy_mutation": "admission_policy_mutation"}


configure()
_foundation_input = foundation.observation_input
_foundation_decode = foundation.python_decode
POLICY_MUTATION_CONTEXT = "tests/test_human_admission.py::AdmissionBoundaryTests.test_policy_change_invalidates_all_implementation_check_snapshots"
POLICY_MUTATIONS = {POLICY_MUTATION_CONTEXT + "/api/" + str(number): api for number, api in (
    (13, "CompositionResult.is_fresh"), (14, "CompositionResult.freshness"), (15, "composition_dependencies"))}
POLICY_VERSION = "biocompiler.human_admission_policy.v0.1"


def mutation_input(call, documents, operation, value, stage):
    if call["id"] not in POLICY_MUTATIONS: return operation, value, stage
    foundation.require(call["api"] == POLICY_MUTATIONS[call["id"]] and call["source"]["line"] == 535
        and call["outcome"] == "returned", "Changed original admission-policy mutation witness")
    child = next(item for item in documents.values() if item["kind"] == "record"
        and isinstance(item["value"], dict) and item["value"].get("admission_policy") == "future"
        and item["value"].get("request") == (value.get("subject", {}).get("dependencies", {}).get("request")
            or foundation.digest(foundation.canonical(value["request"]))))
    return "admission_policy_mutation", {"api": call["api"], "authority": value,
        "policy_version": "future", "original_dependencies": child["value"]}, "admission_policy_mutation"


def observation_input(call, documents):
    api = call["api"]
    if api in {"ComponentRegistry.select", "ComponentRegistry.verify_selection",
               "CompositionResult.freshness", "CompositionResult.is_fresh"}:
        raw = json.loads(documents[call["input"]]["value"])
        cls, method = api.split(".")
        original = getattr(foundation.CLASS_BY_NAME[cls], method)
        bound = inspect.signature(original).bind(*raw["args"], **raw["kwargs"])
        bound.apply_defaults()
        values = foundation.plain(dict(bound.arguments))
        values["subject"] = values.pop("self")
        return mutation_input(call, documents, api, values, "method")
    operation, value, stage = _foundation_input(call, documents)
    return mutation_input(call, documents, operation, value,
        "direct_api" if api in {f.__name__ for f in foundation.FUNCTIONS} and api not in foundation.DEFERRED else stage)


def python_decode(operation, value):
    from biocompiler.ir.composition import CompositionRequest
    if operation == "admission_policy_mutation":
        authority = value["authority"]
        current = python_decode("composition_dependencies", {key: authority[key] for key in ("request", "registry")})
        foundation.require(current["admission_policy"] == POLICY_VERSION, "Current admission policy changed")
        foundation.require(foundation.canonical(current) == foundation.canonical(
            {**value["original_dependencies"], "admission_policy": POLICY_VERSION}),
            "Original policy mutation changed more than the policy identity")
        changed = {**current, "admission_policy": value["policy_version"]}
        foundation.require(foundation.canonical(changed) == foundation.canonical(value["original_dependencies"]),
            "Complete policy mutant differs")
        if value["api"] == "composition_dependencies": return changed
        previous = authority["subject"]["dependencies"]
        keys = tuple(sorted(key for key in changed if changed[key] != previous[key]))
        foundation.require(keys == ("admission_policy",), "Policy change must invalidate only that dependency")
        return not keys if value["api"].endswith("is_fresh") else foundation.FreshnessReport(keys)
    if operation in {"composition_dependencies", "check_composition"}:
        function = composition_dependencies if operation == "composition_dependencies" else check_composition
        return function(CompositionRequest.from_dict(value["request"]), ComponentRegistry.from_dict(value["registry"]))
    if operation in {"ComponentRegistry.select", "ComponentRegistry.verify_selection"}:
        registry = ComponentRegistry.from_dict(value["subject"])
        request = SelectionRequest.from_dict(value["request"])
        return (registry.select(request) if operation.endswith(".select") else
                registry.verify_selection(request, SelectionResult.from_dict(value["result"])))
    if operation in {"CompositionResult.freshness", "CompositionResult.is_fresh"}:
        result = CompositionResult.from_dict(value["subject"])
        return getattr(result, operation.split(".")[1])(
            CompositionRequest.from_dict(value["request"]), ComponentRegistry.from_dict(value["registry"]))
    if operation == "check_component_behavior":
        from biocompiler.compiler.request import RealizationRequest
        from biocompiler.ir.component_assembly import ComponentAssembly
        from biocompiler.semantics.evaluator import InputFrame, SignalSample
        frames = tuple(InputFrame(frame["time"],
            {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
            {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
             for contact, samples in frame["contacts"].items()}) for frame in value["history"])
        return check_component_behavior(RealizationRequest.from_dict(value["request"]),
            ComponentAssembly.from_dict(value["assembly"]), frames, until=value["until"])
    return _foundation_decode(operation, value)


def expected_code(call, operation, value):
    if call["outcome"] == "returned": return None
    if operation == "ComponentRegistry":
        from tools.freeze_component_runtime import expected_code as classify
    elif operation.startswith("Selection") or operation.startswith("ComponentRegistry."):
        from tools.component_selection_codes import expected_code as classify
    elif operation in {"LinkDiagnostic", "ResolvedDependency", "ResourceUsage", "CompositionResult"}:
        from tools.composition_evidence_codes import expected_code as classify
    else:
        raise AssertionError("Unclassified acceptance rejection: " + operation + ": " + call["error"]["message"])
    return classify(call, operation, value)


foundation.observation_input = observation_input
foundation.python_decode = python_decode
foundation.expected_code = expected_code


def child_main(script, context, output):
    foundation.child_main(script, context, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--captured", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.captured:
        for path in foundation.FILES: foundation.load(path)
        document = json.loads(args.captured.read_bytes())
    else:
        with foundation.portable_sources(): document = foundation.capture()
        receipt_path = foundation.OUT / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["profile_generator_sha256"] = foundation.digest(Path(__file__).read_bytes())
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    if not args.capture_only: foundation.freeze(document, check=args.check)


if __name__ == "__main__":
    main()
