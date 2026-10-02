#!/usr/bin/env python3
"""Capture complete original checked-request and realization acceptance calls.

The established foundation capture keeps its default 324-method contract. This
separate profile includes every original foundation method, 12 additional actual
request consumers, and four original independent-checker dependency guards.
No expected native acceptance result is synthesized here.
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
from biocompiler.compiler.request import RealizationRequest

# Keep this profile's capture settings isolated from the foundation module used
# by its existing tests. Importing this tool must not change their 324-method
# inventory, declarations or frozen fixture path in a shared test process.
_module_name = "tools._realization_checks_capture"
_spec = importlib.util.spec_from_file_location(_module_name, ROOT / "tools/freeze_realization_acceptance.py")
assert _spec is not None and _spec.loader is not None
foundation = importlib.util.module_from_spec(_spec)
sys.modules[_module_name] = foundation
_spec.loader.exec_module(foundation)


def configure():
    foundation.FILES = (*foundation.FILES,
        "tests/test_checked_pipeline.py", "tests/test_m9_admission_audit.py",
        "tests/test_circuit_checker_independence.py")
    foundation.METHOD_COUNTS = [*foundation.METHOD_COUNTS, 6, 6, 4]
    foundation.CLASSES = (*foundation.CLASSES, RealizationRequest)
    foundation.CLASS_BY_NAME = {cls.__name__: cls for cls in foundation.CLASSES}
    foundation.SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in foundation.CLASSES}
    foundation.CLASS_IMPORT_METHODS = {RealizationRequest: ("freeze",)}
    foundation.PROPERTY_NAMES = (*foundation.PROPERTY_NAMES,
        "artifact_fingerprint", "upstream_request_fingerprint", "target")
    foundation.CHILD_MODULE = "tools.freeze_realization_checks"
    foundation.OUT = ROOT / "generated/migration-next/realization-checks-capture"
    foundation.CORPUS = ROOT / "tests/conformance/realization-checks-v1.json"
    foundation.CORPUS_SCHEMA = "biocompiler.realization_checks_conformance.v1"
    foundation.CLAIM_SCOPE = "checked_request_correspondence_and_supplied_finite_history_realization_only_no_generic_component_acceptance_or_biology"
    foundation.DEFERRED = {"check_component_behavior", "check_component_assembly"}
    foundation.DEFERRED_OBLIGATION = "independent_generic_component_acceptance_and_correspondence_remain_unimplemented"
    foundation.NATIVE_STAGE_BY_OPERATION = {
        "RealizationRequest": "checked_request", "realization_dependencies": "dependencies",
        "check_realization": "realization", "checker_version_mutation": "checker_version_mutation"}


configure()

_foundation_input = foundation.observation_input
_foundation_decode = foundation.python_decode
_foundation_code = foundation.expected_code
CHECKER_VERSION = "biocompiler.realization_checker.v0.3"
VERSION_MUTATIONS = {
    "tests/test_realization_checker.py::CheckArtifactTests.test_public_dependency_helper_detects_context_parameter_and_history_changes/api/36":
        ("realization_dependencies", "changed", 540),
    "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay/api/90":
        ("realization_dependencies", "changed.v999", 271),
    "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay/api/118":
        ("check_realization", "changed.v999", 271),
    "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay/api/119":
        ("realization_dependencies", "changed.v999", 271),
}


def observation_input(call, documents):
    if call["api"] == "RealizationRequest.freeze":
        raw = json.loads(documents[call["input"]]["value"])
        return "RealizationRequest", foundation.constructor_document("RealizationRequest", raw), "constructor"
    operation, value, stage = _foundation_input(call, documents)
    if operation in {"check_realization", "realization_dependencies"}:
        if call["id"] in VERSION_MUTATIONS:
            api, version, line = VERSION_MUTATIONS[call["id"]]
            foundation.require(call["api"] == api and call["source"]["line"] == line
                and call["outcome"] == "returned", "Changed original version-mutation witness")
            original = documents[call["result"]]["value"]
            dependencies = original if api == "realization_dependencies" else original["dependencies"]
            foundation.require(dependencies["checker"] == version, "Changed original patched version")
            return "checker_version_mutation", {"api": api, "authority": value,
                "checker_version": version, "original_result": original}, "checker_version_mutation"
        stage = "direct_api"
    return operation, value, stage


def python_decode(operation, value):
    if operation == "checker_version_mutation":
        api = value["api"]
        current = foundation.plain(python_decode(api, value["authority"]))
        dependencies = current if api == "realization_dependencies" else current["dependencies"]
        foundation.require(dependencies["checker"] == CHECKER_VERSION, "Current checker identity changed")
        original = value["original_result"]
        restored = ({**original, "checker": CHECKER_VERSION} if api == "realization_dependencies"
                    else {**original, "dependencies": {**original["dependencies"], "checker": CHECKER_VERSION}})
        foundation.require(foundation.canonical(current) == foundation.canonical(restored),
                           "Original version mutation changed more than checker identity")
        changed = {**dependencies, "checker": value["checker_version"]}
        foundation.require(foundation.DependencySnapshot(dependencies).changed(
            foundation.DependencySnapshot(changed)) == ("checker",), "Wrong version freshness mutation")
        return (foundation.DependencySnapshot(changed) if api == "realization_dependencies"
                else foundation.CheckResult.from_dict({**current, "dependencies": changed}))
    if operation in {"check_realization", "realization_dependencies"}:
        from biocompiler.ir.behavior import BehaviorProgram
        from biocompiler.ir.mechanism import MechanismProgram
        from biocompiler.semantics.context import TargetContext
        from biocompiler.verification.realization import ObservationMap
        from biocompiler.semantics.evaluator import InputFrame, SignalSample
        function = (foundation.check_realization if operation == "check_realization"
                    else foundation.realization_dependencies)
        return function(BehaviorProgram.from_dict(value["behavior"]),
            foundation.BehaviorContract.from_dict(value["contract"]),
            foundation.OperatingDomain.from_dict(value["domain"]),
            TargetContext.from_dict(value["target"]), MechanismProgram.from_dict(value["mechanism"]),
            ObservationMap.from_dict(value["observation_map"]),
            tuple(InputFrame(frame["time"],
                {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
                {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
                 for contact, samples in frame["contacts"].items()})
                for frame in value["history"]), until=value["until"])
    return _foundation_decode(operation, value)


def expected_code(call, operation, value):
    if operation == "checker_version_mutation":
        foundation.require(call["outcome"] == "returned", "Unexpected version-mutation rejection")
        return None
    if operation == "RealizationRequest":
        from tools.realization_request_codes import expected_native_code
        return expected_native_code(call, operation, value)
    if operation in {"check_realization", "realization_dependencies"}:
        foundation.require(call["outcome"] == "returned", "New direct acceptance rejection requires precise classification")
        return None
    return _foundation_code(call, operation, value)


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
        with foundation.portable_sources():
            document = foundation.capture()
        receipt_path = foundation.OUT / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt.update(profile_generator_sha256=foundation.digest(Path(__file__).read_bytes()),
            original_functional_methods=336, original_dependency_guard_methods=4)
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    if not args.capture_only:
        foundation.freeze(document, check=args.check)


if __name__ == "__main__":
    main()
