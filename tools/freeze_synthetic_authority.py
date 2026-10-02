#!/usr/bin/env python3
"""Retain original complete synthetic authority observations.

This isolated capture profile retains the original assertions and both actual
subprocesses. The existing domain/runtime/realization corpora remain separate
mandatory gates. Generation and source-correspondence calls remain explicitly deferred.
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
from biocompiler.synthesis.selection import select_synthetic
from biocompiler.synthesis.components import adapt_synthetic_components, SyntheticComposition
from biocompiler.compiler.components import check_component_assembly, check_component_behavior
from biocompiler.verification.realization import check_realization, realization_dependencies

_module_name = "tools._synthetic_authority_capture"
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
    foundation.CLASSES = (SyntheticComponent, SyntheticCatalog, SyntheticGeneratorConfig, SyntheticCandidate)
    foundation.CLASS_BY_NAME = {cls.__name__: cls for cls in foundation.CLASSES}
    foundation.SIGNATURES = {cls.__name__: inspect.signature(cls) for cls in foundation.CLASSES}
    foundation.CLASS_IMPORT_METHODS = {}
    foundation.METHODS = {SyntheticCatalog: ("for_operation", "lock")}
    foundation.FUNCTIONS = (catalog_for_profile, generate_synthetic, _generate_synthetic, select_synthetic, check_synthetic_candidate,
        adapt_synthetic_components, check_component_assembly, check_component_behavior,
        check_realization, realization_dependencies)
    foundation.PROPERTY_NAMES = ("fingerprint",)
    foundation.CHILD_MODULE = "tools.freeze_synthetic_authority"
    foundation.OUT = ROOT / "generated/migration-next/synthetic-authority-capture"
    foundation.CORPUS = ROOT / "tests/conformance/synthetic-authority-v1.json"
    foundation.CORPUS_SCHEMA = "biocompiler.synthetic_authority_conformance.v1"
    foundation.CLAIM_SCOPE = "synthetic_catalog_configuration_and_candidate_authority_only_no_generation_source_correspondence_or_biology"
    foundation.DEFERRED = {"generate_synthetic", "_generate_synthetic", "select_synthetic", "check_synthetic_candidate", "adapt_synthetic_components",
        "check_component_assembly", "check_component_behavior", "check_realization", "realization_dependencies"}
    foundation.DEFERRED_OBLIGATION = "full_original_observation_retained_not_a_domain_acceptance_or_generation_claim"
    foundation.NATIVE_STAGE_BY_OPERATION = {"catalog_for_profile": "catalog", "SyntheticCatalog.for_operation": "catalog",
        "SyntheticCatalog.lock": "catalog"}


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


def observation_input(call, documents):
    if call["api"] in {"SyntheticCatalog.for_operation", "SyntheticCatalog.lock"}:
        raw = json.loads(documents[call["input"]]["value"])
        method = call["api"].split(".")[1]
        bound = inspect.signature(getattr(SyntheticCatalog, method)).bind(*raw["args"], **raw["kwargs"])
        bound.apply_defaults()
        values = foundation.plain(dict(bound.arguments)); values["subject"] = values.pop("self")
        return call["api"], values, "method"
    return _foundation_input(call, documents)


def python_decode(operation, value):
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
