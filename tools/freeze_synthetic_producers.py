#!/usr/bin/env python3
"""Retain original complete synthetic and assembly acceptance observations.

This isolated capture profile retains the original assertions and both actual
subprocesses. The existing domain/runtime/realization corpora remain separate
mandatory gates. Complete generation, adaptation, selection and selection record observations are retained.
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
from biocompiler.ir.components import SyntheticComponent
from biocompiler.registry.synthetic import SyntheticCatalog, catalog_for_profile
from biocompiler.synthesis.synthetic import (SyntheticGeneratorConfig, SyntheticCandidate,
    generate_synthetic, _generate_synthetic, check_synthetic_candidate)
from biocompiler.synthesis.selection import select_synthetic, SyntheticAlternative, SyntheticSelectionResult
from biocompiler.synthesis.components import adapt_synthetic_components, SyntheticComposition
from biocompiler.compiler.components import check_component_assembly, check_component_behavior
from biocompiler.verification.realization import check_realization, realization_dependencies

_module_name = "tools._synthetic_producers_capture"
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
    foundation.CLASSES = (SyntheticComponent, SyntheticCatalog, SyntheticGeneratorConfig, SyntheticCandidate, SyntheticAlternative, SyntheticSelectionResult)
    foundation.CLASS_BY_NAME = {cls.__name__: cls for cls in foundation.CLASSES}
    foundation.SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in foundation.CLASSES}
    foundation.CLASS_IMPORT_METHODS = {}
    foundation.METHODS = {SyntheticCatalog: ("for_operation", "lock")}
    foundation.FUNCTIONS = (catalog_for_profile, generate_synthetic, _generate_synthetic, select_synthetic, check_synthetic_candidate,
        adapt_synthetic_components, check_component_assembly, check_component_behavior,
        check_realization, realization_dependencies)
    foundation.PROPERTY_NAMES = ("fingerprint", "gate_count", "status", "selected_strategy", "candidate", "outcome", "checked_candidates", "rejected_candidates")
    foundation.CHILD_MODULE = "tools.freeze_synthetic_producers"
    foundation.OUT = ROOT / "generated/migration-next/synthetic-producers-capture"
    foundation.CORPUS = ROOT / "tests/conformance/synthetic-producers-v1.json"
    foundation.CORPUS_SCHEMA = "biocompiler.synthetic_producers_conformance.v1"
    foundation.CLAIM_SCOPE = "complete_synthetic_proposals_generation_selection_adaptation_and_independent_acceptance_no_biology"
    foundation.DEFERRED = set()
    foundation.DEFERRED_OBLIGATION = "full_original_producer_observation_retained_no_native_generation_adaptation_or_selection_claim"
    foundation.NATIVE_STAGE_BY_OPERATION = {"catalog_for_profile": "catalog", "SyntheticCatalog.for_operation": "catalog",
        "SyntheticCatalog.lock": "catalog", "check_synthetic_candidate": "synthetic_acceptance",
        "check_component_assembly": "assembly_acceptance", "check_component_behavior": "component_behavior",
        "check_realization": "realization", "realization_dependencies": "dependencies",
        "checker_version_mutation": "checker_version_mutation", "generate_synthetic": "generation", "_generate_synthetic": "proposal", "select_synthetic": "selection", "adapt_synthetic_components": "adaptation"}


configure()
_foundation_input = foundation.observation_input
_foundation_decode = foundation.python_decode
_foundation_constructor = foundation.constructor_document
_foundation_plain = foundation.plain


def plain(value):
    if isinstance(value, SyntheticComposition):
        from dataclasses import fields
        foundation.require(tuple(field.name for field in fields(value)) ==
            ("registry", "composition", "acceptance"), "SyntheticComposition field inventory changed")
        return {"registry": _foundation_plain(value.registry),
            "composition": _foundation_plain(value.composition),
            "acceptance": _foundation_plain(value.acceptance)}
    return _foundation_plain(value)



def constructor_document(name, raw):
    value = _foundation_constructor(name, raw)
    if name == "SyntheticCandidate":
        value.update(intended_use="software_test", human_therapeutic_admission="not_admitted")
    if name == "SyntheticGeneratorConfig" and value["catalog_fingerprint"] is None:
        # Constructor default is profile-dependent; preserving this default is
        # distinct from importing an explicit null, which Python rejects.
        try: value["catalog_fingerprint"] = catalog_for_profile(value["profile_version"]).fingerprint
        except Exception: pass
    return value


CHECKER_VERSION = "biocompiler.realization_checker.v0.3"
VERSION_MUTATION_CONTEXT = "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay"
VERSION_MUTATIONS = {
    "tests/test_realization_checker.py::CheckArtifactTests.test_public_dependency_helper_detects_context_parameter_and_history_changes/api/5":
        ("realization_dependencies", "changed", 540),
    **{VERSION_MUTATION_CONTEXT + "/api/" + str(number): (api, "changed.v999", 271)
       for number, api in ((128, "check_synthetic_candidate"), (130, "realization_dependencies"),
                          (190, "check_realization"), (191, "realization_dependencies"))},
}
ACCEPTANCE = {"check_synthetic_candidate", "check_component_assembly", "check_component_behavior",
              "check_realization", "realization_dependencies"}


PRODUCERS = {"generate_synthetic", "_generate_synthetic", "select_synthetic", "adapt_synthetic_components"}
SELECTION_MUTATIONS = {
    "tests/test_synthetic_selection.py::SyntheticSelectionTests.test_both_execution_failures_exhaust_only_the_declared_search/api/0": (46, "both_execution_failures"),
    "tests/test_synthetic_selection.py::SyntheticSelectionTests.test_independent_checker_rejects_faulty_demorgan_rewrite_before_ranking/api/0": (46, "faulty_demorgan"),
}
foundation.NATIVE_STAGE_BY_OPERATION.update({"selection_producer_mutation": "selection_producer_mutation"})


def observation_input(call, documents):
    if call["api"] in {"SyntheticAlternative.__init__", "SyntheticSelectionResult.__init__"}:
        name = call["api"].split(".")[0]
        raw = json.loads(documents[call["input"]]["value"])
        return name + ".make", constructor_document(name, raw), "constructor"
    if call["api"] in {"SyntheticCatalog.for_operation", "SyntheticCatalog.lock"}:
        raw = json.loads(documents[call["input"]]["value"])
        method = call["api"].split(".")[1]
        bound = inspect.signature(getattr(SyntheticCatalog, method)).bind(*raw["args"], **raw["kwargs"])
        bound.apply_defaults()
        values = foundation.plain(dict(bound.arguments)); values["subject"] = values.pop("self")
        return call["api"], values, "method"
    operation, value, stage = _foundation_input(call, documents)
    if call["api"] in ACCEPTANCE:
        if call["id"] in VERSION_MUTATIONS:
            api, version, line = VERSION_MUTATIONS[call["id"]]
            foundation.require(call["api"] == api and call["source"]["line"] == line
                and call["outcome"] == "returned", "Changed original version-mutation witness")
            original = documents[call["result"]]["value"]
            dependencies = original if api == "realization_dependencies" else original["dependencies"]
            foundation.require(dependencies["checker"] == version, "Changed original patched checker version")
            return "checker_version_mutation", {"api": api, "authority": value,
                "checker_version": version, "original_result": original}, "checker_version_mutation"
        stage = "direct_api"
    if call["api"] in PRODUCERS:
        if call["id"] in SELECTION_MUTATIONS:
            line, recipe = SELECTION_MUTATIONS[call["id"]]
            foundation.require(call["api"] == "select_synthetic" and call["source"]["line"] == line
                and call["outcome"] == "returned", "Changed original selector mutation witness")
            original = documents[call["result"]]["value"]
            proposals = [item["candidate"] for item in original["alternatives"]]
            foundation.require(all(item is not None for item in proposals), "Mutation lost proposed candidate")
            return "selection_producer_mutation", {"authority": value, "recipe": recipe,
                "proposals": proposals}, "selection_producer_mutation"
        stage = "direct_api"
    return operation, value, stage


def frames_from_json(values):
    from biocompiler.semantics.evaluator import InputFrame, SignalSample
    return tuple(InputFrame(frame["time"],
        {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
        {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
         for contact, samples in frame["contacts"].items()}) for frame in values)


def python_decode(operation, value):
    if operation in {"SyntheticAlternative.make", "SyntheticSelectionResult.make"}:
        if operation == "SyntheticAlternative.make":
            return SyntheticAlternative(value["strategy"],
                SyntheticCandidate.from_dict(value["candidate"]) if value["candidate"] is not None else None,
                value["constraint_violations"],
                foundation.CheckResult.from_dict(value["check"]) if value["check"] is not None else None,
                value["generation_error"])
        return SyntheticSelectionResult(value["request_fingerprint"], value["history_fingerprint"],
            value["until"], SyntheticGeneratorConfig.from_dict(value["config"]), value["minimize"],
            tuple(SyntheticAlternative.from_dict(item) for item in value["alternatives"]))
    if operation == "selection_producer_mutation":
        from unittest.mock import patch
        proposals = [SyntheticCandidate.from_dict(item) for item in value["proposals"]]
        foundation.require([item.generator_config.conjunction_strategy for item in proposals] == ["native", "de_morgan"],
            "Original patched proposal order differs")
        count = 0
        def propose(request, *, config):
            nonlocal count
            foundation.require(count < 2, "Mutation proposal invocation differs")
            candidate = proposals[count]; count += 1
            foundation.require(candidate.generator_config == config, "Mutation proposal changed configuration")
            return candidate
        with patch("biocompiler.synthesis.selection._generate_synthetic", side_effect=propose):
            result = python_decode("select_synthetic", value["authority"])
        foundation.require(count == 2, "Both original mutated proposals must be checked")
        return result
    if operation in PRODUCERS:
        from biocompiler.compiler.request import RealizationRequest
        request = RealizationRequest.from_dict(value["request"])
        if operation in {"generate_synthetic", "_generate_synthetic", "select_synthetic"}:
            config = SyntheticGeneratorConfig.from_dict(value["config"]) if value["config"] is not None else None
            if operation == "select_synthetic":
                return select_synthetic(request, frames_from_json(value["history"]), until=value["until"], config=config)
            return (generate_synthetic if operation == "generate_synthetic" else _generate_synthetic)(request, config=config)
        return adapt_synthetic_components(request, SyntheticCandidate.from_dict(value["candidate"]),
            frames_from_json(value["history"]), until=value["until"])
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
        from tools.freeze_realization_checks import python_decode as decode
        return decode(operation, value)
    if operation in {"check_synthetic_candidate", "check_component_assembly", "check_component_behavior"}:
        from biocompiler.compiler.request import RealizationRequest
        from biocompiler.ir.component_assembly import ComponentAssembly
        from biocompiler.semantics.evaluator import InputFrame, SignalSample
        request = RealizationRequest.from_dict(value["request"])
        frames = tuple(InputFrame(frame["time"],
            {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
            {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
             for contact, samples in frame["contacts"].items()}) for frame in value["history"])
        if operation == "check_component_behavior":
            return check_component_behavior(request, ComponentAssembly.from_dict(value["assembly"]), frames,
                until=value["until"])
        candidate = SyntheticCandidate.from_dict(value["candidate"])
        if operation == "check_synthetic_candidate":
            return check_synthetic_candidate(request, candidate, frames, until=value["until"])
        return check_component_assembly(request, candidate, ComponentAssembly.from_dict(value["assembly"]), frames,
            until=value["until"])
    if operation == "catalog_for_profile": return catalog_for_profile(value["profile"])
    if operation in {"SyntheticCatalog.for_operation", "SyntheticCatalog.lock"}:
        subject = SyntheticCatalog.from_dict(value["subject"])
        if operation.endswith("for_operation"): return subject.for_operation(value["operation"])
        from biocompiler.ir.mechanism import MechanismProgram
        return subject.lock(MechanismProgram.from_dict(value["mechanism"]))
    return _foundation_decode(operation, value)


def expected_code(call, operation, value):
    if call["outcome"] == "returned": return None
    error = call["error"]
    if operation in PRODUCERS:
        if error["type"] == "UnsupportedBehaviorError":
            foundation.require(error["module"] == "biocompiler.errors" and operation != "adapt_synthetic_components",
                "Unexpected producer unsupported family")
            return "synthetic_generator_unsupported"
        foundation.require(operation == "adapt_synthetic_components" and error == {
            "module": "biocompiler.errors", "type": "SerializationError",
            "message": "Component adaptation requires passing synthetic acceptance for the current request, candidate and history."},
            "Unclassified complete producer rejection: " + str(error))
        return "synthetic_component_acceptance"
    if operation in {"SyntheticAlternative", "SyntheticAlternative.make", "SyntheticSelectionResult", "SyntheticSelectionResult.make"}:
        foundation.require(error["module"] == "biocompiler.errors" and error["type"] == "SerializationError",
            "Unclassified selection record exception family")
        known = {"Selection summary disagrees with checked alternatives.", "Unsupported selection schema/policy.",
            "Alternative summary disagrees with its artifacts.", "Alternative check belongs to another history/horizon/request.",
            "Alternative belongs to another request/configuration."}
        foundation.require(error["message"] in known, "Unclassified selection record rejection: " + str(error))
        return "unsupported_schema" if error["message"] == "Unsupported selection schema/policy." else "synthetic_selection"
    if operation == "check_component_assembly":
        key = (error["module"], error["type"], error["message"])
        counterparts = {
            ("biocompiler.compiler.pipeline", "PipelineError", "Component assembly changed its authoritative source correspondence."): "component_assembly",
            ("biocompiler.errors", "SerializationError", "Component adaptation requires passing synthetic acceptance for the current request, candidate and history."): "synthetic_component_acceptance",
        }
        foundation.require(key in counterparts, "Unclassified full assembly rejection: " + str(key))
        return counterparts[key]
    foundation.require(error["module"] == "biocompiler.errors" and error["type"] == "SerializationError",
        "Unclassified synthetic authority exception family: " + str(error))
    counterparts = {
        ("SyntheticCandidate.from_dict", "Unsupported candidate schema."): "unsupported_schema",
        ("SyntheticGeneratorConfig.from_dict", "Unsupported generator-config schema."): "unsupported_schema",
        ("SyntheticGeneratorConfig.__init__", "The selected synthetic catalog is unavailable or stale."): "synthetic_authority",
        ("SyntheticGeneratorConfig.from_dict", "The selected synthetic catalog is unavailable or stale."): "synthetic_authority",
        ("SyntheticGeneratorConfig.__init__", "Unsupported synthetic generation profile."): "synthetic_authority",
        ("SyntheticGeneratorConfig.from_dict", "Unsupported synthetic generation profile."): "synthetic_authority",
        ("catalog_for_profile", "Unsupported synthetic generation profile."): "synthetic_authority",
    }
    key = (call["api"], error["message"])
    foundation.require(key in counterparts, "Unclassified synthetic authority rejection: " + str(key))
    return counterparts[key]


foundation.plain = plain
foundation.constructor_document = constructor_document
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
