"""All original direct SDK calls against both installed native executable roles.

Authority records are hydrated before the guard: historical request construction
checks lowering. Within a selected native call, only serializers, output record
codecs, nominal input preflight and transport may execute. Workflow/archive/export
routing remains an explicit separate obligation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys

from biocompiler.core_client import CoreRejected
from biocompiler.realization_backend import RealizationCoreError
if __package__:
    from .check_realization_protocol import APIS, Corpus, artifact, canonical, digest, require, run_main
else:
    from check_realization_protocol import APIS, Corpus, artifact, canonical, digest, require, run_main

_TRANSPORT = frozenset(("biocompiler.core_client", "biocompiler.core_realization",
                        "biocompiler.realization_backend", "biocompiler.errors"))
_ROUTES = {
    "biocompiler.verification.realization": ("realization_dependencies", "check_realization"),
    "biocompiler.synthesis.synthetic": ("check_synthetic_candidate", "_request"),
    "biocompiler.compiler.components": ("check_component_behavior", "check_component_assembly"),
}
_OUTPUT_RECORDS = {
    "biocompiler.verification.evidence": ("DependencySnapshot", "CheckResult", "CheckDiagnostic",
                                        "Counterexample", "RequirementCoverage"),
    "biocompiler.verification.components": ("CompositionResult", "LinkDiagnostic", "ResolvedDependency", "ResourceUsage"),
}
_HELPERS = {
    "biocompiler.verification.evidence": ("_require", "_name", "_finite_nonnegative", "_canonical", "_fields"),
    "biocompiler.verification.components": ("_schema", "_strict_import", "_pairs"),
    "biocompiler.semantics.types": ("decode_binding", "_number", "to_type_spec", "_scalar_binding"),
}
# Input serialization and output range decoding use these reviewed record modules.
_SERIALIZERS = frozenset((
    "biocompiler.compiler.request", "biocompiler.synthesis.synthetic",
    "biocompiler.semantics.evaluator", "biocompiler.semantics.types",
    "biocompiler.semantics.context", "biocompiler.semantics.contracts",
    "biocompiler.semantics.realization", "biocompiler.semantics.component_contracts",
    "biocompiler.semantics.human_target", "biocompiler.semantics.measurement",
    "biocompiler.registry.components", "biocompiler.artifacts.provenance",
    "biocompiler.verification.realization",
))
_CODEC_METHODS = frozenset(("to_dict", "to_json", "fingerprint", "artifact_fingerprint"))
_TYPE_OUTPUT_METHODS = frozenset(("TypeSpec.from_dict", "TypeSpec.__post_init__",
    "Interval.__post_init__", "Interval.__init__", "Interval.__class_getitem__", "Interval.to_dict", "ScalarLiteral.__post_init__",
    "ScalarLiteral.to_dict", "TypeSpec.compatible", "TypeSpec._combine", "TypeSpec.__mul__", "_ScalarType.__new__"))


def _named(name, allowed):
    return any(name == item or name.startswith(item + ".<locals>.") for item in allowed)


def allowed_frame(frame):
    module, code = frame.f_globals.get("__name__", ""), frame.f_code
    name = code.co_qualname
    if not module.startswith("biocompiler") or module in _TRANSPORT:
        return True
    # IR modules encode/import immutable values; no compiler or checker lives in
    # this namespace. Source lowering is in compiler.lowering and remains denied.
    if module.startswith(("biocompiler.ir.", "biocompiler.artifacts.")):
        return True
    if _named(name, _ROUTES.get(module, ()) + _HELPERS.get(module, ())):
        return True
    if module in _SERIALIZERS:
        base = name.split(".<locals>.", 1)[0]
        if base.rsplit(".", 1)[-1] in _CODEC_METHODS:
            return True
    if module == "biocompiler.semantics.types" and _named(name, _TYPE_OUTPUT_METHODS):
        return True
    if any(name == cls + "." + method or name.startswith(cls + "." + method + ".<locals>.")
           for cls in _OUTPUT_RECORDS.get(module, ())
           for method in ("__init__", "__post_init__", "from_dict", "to_dict", "to_json", "fingerprint", "passed")):
        return True
    # Python 3.11/3.14 differ in generated dataclass constructor qualnames.
    if code.co_filename == "<string>" and code.co_name in ("__init__", "__eq__", "__repr__"):
        record = type(frame.f_locals.get("self"))
        return record.__module__ == module and (
            record.__qualname__ in _OUTPUT_RECORDS.get(module, ()) or
            module == "biocompiler.semantics.types" and record.__qualname__ in ("TypeSpec", "Interval", "ScalarLiteral"))
    return False


@contextmanager
def routed_execution():
    previous = sys.getprofile()
    seen = set()
    classified = {}
    def guard(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler"):
                code = frame.f_code
                key = module, id(code)
                cached = classified.get(key)
                if cached is None:
                    # Keep the code alive so object-id reuse cannot inherit an
                    # earlier permission. Generated methods still inspect self.
                    dynamic = code.co_filename == "<string>" and code.co_name in ("__init__", "__eq__", "__repr__")
                    qualified = module + "." + code.co_qualname
                    cached = (None if dynamic else allowed_frame(frame), qualified, code)
                    classified[key] = cached
                    seen.add(qualified)
                policy, qualified, _code = cached
                if not (allowed_frame(frame) if policy is None else policy):
                    require(False,
                            "Python semantic authority executed on native realization route: " + qualified)
    sys.setprofile(guard)
    try:
        yield seen
    finally:
        sys.setprofile(previous)


def hydrate(api, raw):
    """Original input hydration is deliberately outside the measured route."""
    from biocompiler.compiler.request import RealizationRequest
    from biocompiler.ir.behavior import BehaviorProgram
    from biocompiler.ir.component_assembly import ComponentAssembly
    from biocompiler.ir.mechanism import MechanismProgram
    from biocompiler.semantics.context import TargetContext
    from biocompiler.semantics.evaluator import InputFrame, SignalSample
    from biocompiler.synthesis.synthetic import SyntheticCandidate
    from biocompiler.verification.realization import BehaviorContract, OperatingDomain, ObservationMap
    classes = {"request": RealizationRequest, "behavior": BehaviorProgram, "contract": BehaviorContract,
               "domain": OperatingDomain, "target": TargetContext, "mechanism": MechanismProgram,
               "observation_map": ObservationMap, "candidate": SyntheticCandidate, "assembly": ComponentAssembly}
    values = {key: cls.from_dict(raw[key]) for key, cls in classes.items() if key in raw}
    values["history"] = tuple(InputFrame(frame["time"],
        {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
        {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
         for contact, samples in frame["contacts"].items()}) for frame in raw["history"])
    values["until"] = raw["until"]
    return values


def sdk_function(api):
    from biocompiler.verification.realization import realization_dependencies, check_realization
    from biocompiler.synthesis.synthetic import check_synthetic_candidate
    from biocompiler.compiler.components import check_component_behavior, check_component_assembly
    return {"realization_dependencies": realization_dependencies, "check_realization": check_realization,
            "check_synthetic_candidate": check_synthetic_candidate, "check_component_behavior": check_component_behavior,
            "check_component_assembly": check_component_assembly}[api]


def campaign(clients, corpus, receipt):
    seen = set()
    for transport in clients:
        for case in [*corpus.cases, *corpus.extra]:
            # No snapshot request constructor or original checker may be called
            # once the execution guard starts.
            values = hydrate(case["api"], corpus.authority(case))
            function = sdk_function(case["api"])
            operation = APIS[case["api"]][1]
            expected = None if case["result"] is None else corpus.document(case["result"])
            with routed_execution() as observed:
                try:
                    result = function(**values, core=transport)
                except RealizationCoreError as error:
                    require(case["result"] is None and isinstance(error.core_error, CoreRejected),
                            "Native SDK failed where the original returned a complete report")
                    require(error.core_error.response.result is None and len(error.diagnostics) == 1 and
                            error.diagnostics[0].code == case["error"]["code"] and
                            error.diagnostics[0].message == case["error"]["message"],
                            "SDK changed the original exact rejection")
                    actual = {"status": error.core_error.response.status, "result": None,
                              "diagnostics": [{"code": d.code, "message": d.message, "path": d.path}
                                              for d in error.diagnostics]}
                    detail = {"error": case["error"]["code"]}
                else:
                    require(expected is not None, "SDK accepted an original rejected authority")
                    actual = result.to_dict()
                    require(canonical(actual) == canonical(expected), "Complete public SDK report differs: " + case["id"])
                    family = APIS[case["api"]][0]
                    encoding = corpus.profiles[family]["dependency_encoding" if case["api"] == "realization_dependencies" else "assessment_encoding"]
                    require(result.fingerprint == digest(actual, ascii=encoding == "python-json-ascii-v1"),
                            "Public record codec changed report-family identity")
                    detail = {"report": result.fingerprint, "outcome": actual.get("outcome")}
                seen.update(observed)
            receipt["checks"].append({"role": transport.role, "id": case["id"], "operation": operation,
                                      "artifact": artifact(receipt, actual), **detail})
    receipt["guard"] = {"status": "passed", "allowed_executed_functions": sorted(seen),
                        "input_hydration": "outside_guard_before_native_call",
                        "snapshot_request_rehydration": "forbidden_during_native_call"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return run_main(parser.parse_args(argv), campaign, "biocompiler.realization_routing_conformance.v1")


if __name__ == "__main__":
    raise SystemExit(main())
