"""Additive original public-build value and physical-identity witness.

The six authored authorities cover every one of the 39 unchanged component
continuation chains. Original fixture/test bodies construct and check them;
an observation-only profiler retains the real fixed producer and public returns.
No accepted result or saved state is supplied to the original implementation.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import fields
from enum import Enum
import importlib
import json
from pathlib import Path
import sys
from types import CodeType, MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
_paths = list(sys.path)
try:
    sys.path.extend((str(ROOT / "src"), str(ROOT), str(ROOT / "tests")))
    from tools import capture_pipeline_fixed_provider_semantics as providers
    from tools.check_pipeline_session_install import Corpus
    from tools.freeze_realization_acceptance import portable_sources
    from biocompiler.compiler import components, pipeline, synthetic
    from biocompiler.compiler.passes import PassResult
    from test_component_pipeline import ComponentPipelineTests
    from test_temporal_components import TemporalComponentTests
    from test_synthetic_design_workflows import SyntheticDesignWorkflowTests
finally:
    sys.path[:] = _paths

SCHEMA = "biocompiler.pipeline_fixed_build_semantics.v1"
OUTPUT = ROOT / "tests/conformance/pipeline-fixed-build-semantics-v1.json"
CASES = ("static", "temporal", "memory:retain", "memory:reset", "startup", "selected_temporal")
EXTRA_TYPES = {
    "biocompiler.compiler.synthetic": ("SyntheticBuild",),
    "biocompiler.compiler.components": ("ComponentBuild",),
    "biocompiler.compiler.pipeline": ("StageRecord", "PipelineResult", "ScopedObligation"),
    "biocompiler.synthesis.selection": ("SyntheticAlternative", "SyntheticSelectionResult"),
    "biocompiler.verification.components": ("CompositionResult", "LinkDiagnostic", "ResolvedDependency", "ResourceUsage"),
    "biocompiler.verification.evidence": ("CheckResult", "DependencySnapshot", "CheckDiagnostic", "Counterexample", "RequirementCoverage"),
}
TYPES = {**providers.TYPES, **EXTRA_TYPES}
SAFE = {getattr(importlib.import_module(module), name) for module, names in TYPES.items() for name in names}
canonical, sha = providers.canonical, providers.sha
PENDING = ["All 136 original fixed boundaries and 476 manager contexts remain mandatory",
    "This original witness does not execute native Core or establish compatibility",
    "Original fixed registration interception and ten excluded boundaries remain pending"]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Graph:
    """Closed raw field graph: no semantic constructors, properties or equality."""
    def __init__(self, *, manager_type=pipeline.PassManager):
        self.objects = []
        self.nodes = []
        self.identities = {}
        self.manager_type = manager_type

    def encode(self, value):
        if value is None or type(value) in (bool, int, float, str):
            return {"scalar": type(value).__name__, "value": value}
        if isinstance(value, Enum):
            return {"enum": type(value).__module__ + "." + type(value).__qualname__, "value": self.encode(value.value)}
        allowed = type(value) in SAFE or type(value) in (dict, MappingProxyType, list, tuple, self.manager_type)
        require(allowed, "Unreviewed public build graph type: " + type(value).__module__ + "." + type(value).__qualname__)
        if id(value) in self.identities:
            index = self.identities[id(value)]
            require(self.objects[index] is value, "Retained graph identity collision")
            return {"ref": "object/" + str(index)}
        index = len(self.objects)
        self.identities[id(value)] = index
        self.objects.append(value)
        self.nodes.append(None)
        if type(value) is self.manager_type:
            node = {"kind": "manager", "class": "biocompiler.compiler.pipeline.PassManager"}
        elif type(value) in (dict, MappingProxyType):
            node = {"kind": "mapping", "class": type(value).__name__,
                "items": [[self.encode(key), self.encode(item)] for key, item in value.items()]}
        elif type(value) in (list, tuple):
            node = {"kind": "sequence", "class": type(value).__name__, "items": [self.encode(item) for item in value]}
        else:
            schema = vars(type(value)).get("schema_version")
            node = {"kind": "dataclass", "class": type(value).__module__ + "." + type(value).__qualname__,
                "fields": [[item.name, self.encode(object.__getattribute__(value, item.name))] for item in fields(value)],
                "instance_fields": list(vars(value)),
                "class_schema": schema if type(schema) is str and "schema_version" not in vars(value) else None}
        self.nodes[index] = node
        return {"ref": "object/" + str(index)}

    def value(self, reference):
        """Expand exact values for independent comparisons, retaining scalar kind."""
        if "ref" not in reference:
            return reference
        node = self.nodes[int(reference["ref"].split("/")[1])]
        if node["kind"] == "manager":
            return {"kind": "manager"}
        result = {key: value for key, value in node.items() if key not in ("items", "fields")}
        if node["kind"] == "dataclass":
            result["fields"] = [[key, self.value(value)] for key, value in node["fields"]]
        elif node["kind"] == "mapping":
            result["items"] = [[self.value(key), self.value(value)] for key, value in node["items"]]
        else:
            result["items"] = [self.value(value) for value in node["items"]]
        return result


def code_children(code):
    yield code
    for value in code.co_consts:
        if type(value) is CodeType:
            yield from code_children(value)


def node(case, reference):
    require(type(reference) is dict and set(reference) == {"ref"}, "Expected retained graph reference")
    return case["nodes"][int(reference["ref"].split("/")[1])]


def children(case, reference):
    if "ref" not in reference:
        return []
    value = node(case, reference)
    if value["kind"] == "dataclass":
        return value["fields"]
    if value["kind"] == "sequence":
        return list(enumerate(value["items"]))
    if value["kind"] == "mapping":
        require(all(key.get("scalar") == "str" for key, _ in value["items"]), "Expected named graph mapping")
        return [(key["value"], item) for key, item in value["items"]]
    return []


def at(case, reference, *path):
    for key in path:
        reference = dict(children(case, reference))[key]
    return reference


def reachable(case, reference):
    """One closed path per retained node, without treating equality as identity."""
    result, queue = {}, [(reference, [])]
    for item, path in queue:
        if "ref" not in item or item["ref"] in result:
            continue
        result[item["ref"]] = path
        queue.extend((child, [*path, key]) for key, child in children(case, item))
    return result


def historical_aliases(case):
    roots = case["roots"]
    component = roots["component"]
    records = dict(roots["component_records"])
    result = {}
    for field, stage in (("candidate", "mechanism"), ("assembly", "components")):
        public = reachable(case, at(case, component, field))
        stored = reachable(case, at(case, records[stage], "payload"))
        result[field] = [{"public": public[key], "stored": stored[key], "node": {"ref": key}}
            for key in public if key in stored]
    return result


class Observer:
    def __init__(self):
        self.cases = []
        self.active = None
        self.producer_codes = {}
        for function in (synthetic.run_synthetic_pipeline, components.run_component_pipeline):
            for code in code_children(function.__code__):
                if code.co_name in ("lower", "generate"):
                    self.producer_codes[code] = ("components" if function is components.run_component_pipeline else code.co_name)

    def profile(self, frame, event, value):
        code = frame.f_code
        if code is components.run_component_pipeline.__code__:
            if event == "call":
                require(self.active is None, "Unexpected recursive original component build")
                self.active = {"authority_objects": {key: frame.f_locals[key] for key in ("request", "history", "until", "config")},
                    "producer_returns": []}
            elif event == "return":
                require(type(value) is components.ComponentBuild and self.active is not None,
                    "Original component body did not return a public build")
                self.active["component"] = value
                self.active["component_records"] = tuple(value.manager._records.items())
                self.cases.append(self.active)
                self.active = None
        elif self.active is not None and event == "return":
            if code is synthetic.run_synthetic_pipeline.__code__:
                require(type(value) is synthetic.SyntheticBuild, "Original upstream public build is missing")
                self.active["synthetic"] = value
                self.active["synthetic_records"] = tuple(value.manager._records.items())
                self.active["requested_config"] = frame.f_locals["requested_config"]
                self.active["selected_config"] = frame.f_locals["config"]
            elif code in self.producer_codes:
                require(type(value) is PassResult, "Original fixed producer omitted its complete proposal")
                self.active["producer_returns"].append((self.producer_codes[code], value))

    @contextmanager
    def installed(self):
        previous = sys.getprofile()
        def combined(frame, event, value):
            self.profile(frame, event, value)
            if previous is not None:
                previous(frame, event, value)
        sys.setprofile(combined)
        try:
            yield
        finally:
            intact = sys.getprofile() is combined
            sys.setprofile(previous)
            require(intact, "Original build observation profiler was replaced")


def original_bodies():
    ComponentPipelineTests.setUpClass()
    TemporalComponentTests.setUpClass()
    TemporalComponentTests("test_reset_set_and_expiry_precedence_survive_component_reconstruction").test_reset_set_and_expiry_precedence_survive_component_reconstruction()
    TemporalComponentTests("test_startup_memory_contact_loss_and_reset_have_literal_output_timeline").test_startup_memory_contact_loss_and_reset_have_literal_output_timeline()
    SyntheticDesignWorkflowTests.setUpClass()


def observe_case(identity, objects, *, manager_type=pipeline.PassManager):
    graph = Graph(manager_type=manager_type)
    authored = objects["authority_objects"]
    request = authored["request"]
    roots = {"target": graph.encode(request.target), "config_argument": graph.encode(authored["config"]),
        "requested_config": graph.encode(objects["requested_config"]), "selected_config": graph.encode(objects["selected_config"])}
    origins = [[name, graph.encode(value)] for name, value in providers.source_origins(request)]
    roots["producer_returns"] = [[name, graph.encode(value)] for name, value in objects["producer_returns"]]
    roots["synthetic"] = graph.encode(objects["synthetic"])
    roots["synthetic_records"] = [[name, graph.encode(value)] for name, value in objects["synthetic_records"]]
    roots["component"] = graph.encode(objects["component"])
    roots["component_records"] = [[name, graph.encode(value)] for name, value in objects["component_records"]]
    require([name for name, _ in roots["producer_returns"]] == ["lower", "generate", "components"], "Original producer return census differs")
    authority = {"request": request.to_dict(), "history": [frame.to_dict() for frame in authored["history"]],
        "until": authored["until"], "config": authored["config"].to_dict() if authored["config"] is not None else None}
    return {"id": identity, "authority": authority, "authority_sha256": sha(canonical(authority)),
        "roots": roots, "source_origins": origins, "nodes": graph.nodes}


def source_files():
    paths = {"tools/capture_pipeline_fixed_build_semantics.py", "tools/capture_pipeline_fixed_provider_semantics.py",
        "tools/check_pipeline_session_install.py", "tools/freeze_realization_acceptance.py",
        "tests/test_component_pipeline.py", "tests/test_temporal_components.py", "tests/test_temporal_generation.py",
        "tests/test_synthetic_design_workflows.py", "examples/checked_pipeline.py", "examples/temporal_pipeline.py",
        "examples/synthetic_design.py", "examples/synthetic_build.py", "examples/synthetic_verification.py"}
    paths.update("src/" + module.replace(".", "/") + ".py" for module in TYPES)
    paths.update("src/biocompiler/" + path
        for path in ("compiler/request.py", "compiler/behavior.py", "compiler/synthetic_build.py", "ir/serialization.py",
            "synthesis/components.py", "registry/synthetic.py", "frontend/graph.py"))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def capture(*, retain=None):
    source_before = source_files()
    observer = Observer()
    with portable_sources(), observer.installed():
        original_bodies()
    require(observer.active is None and len(observer.cases) == len(CASES), "Original public build census differs")
    cases = [observe_case(identity, values) for identity, values in zip(CASES, observer.cases)]
    if retain is not None:
        retain.extend(observer.cases)
    corpus = Corpus()
    continuation_cases = [case for case in corpus.cases if corpus.continuations[case["id"]].get("pending_callback_dependent_suffix")]
    frequencies = Counter(case["authority"] for case in continuation_cases)
    require(len(continuation_cases) == 39 and set(frequencies) == {case["authority_sha256"] for case in cases},
        "Public build witness does not cover exactly all six original continuation authorities")
    for case in cases:
        case["original_cases"] = [entry["id"] for entry in continuation_cases if entry["authority"] == case["authority_sha256"]]
    require(source_before == source_files(), "Original source changed during public build capture")
    result = {"schema_version": SCHEMA, "source_files": source_before,
        "coverage": {"authorities": 6, "fixed_boundaries": 136, "manager_contexts": 476,
            "eligible_continuation_chains": 39, "suffix_operations": 254, "prefix_operations": 312,
            "public_returns": 12, "producer_returns": 18, "excluded_boundaries": 10},
        "pending": PENDING, "cases": cases}
    result["inventory_fingerprint"] = sha(canonical(result))
    return result


def main():
    require(not OUTPUT.exists(), "Refusing to replace frozen original public build observations")
    OUTPUT.write_bytes(canonical(capture()) + b"\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
