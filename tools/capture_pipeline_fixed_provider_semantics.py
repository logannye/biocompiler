"""Additive original fixed-provider representation and selected alias witness.

Real fixed pipelines establish their own managers and providers. Each original
producer is called twice from one real manager callback; the first proposal is
then checked by the unchanged fixed validators. No saved output chooses a result.
This is a scoped supplement, not full fixed interception or manager parity.
"""
from __future__ import annotations

from dataclasses import fields, replace
from enum import Enum
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
_paths = list(sys.path)
try:
    # Existing installed biocompiler imports win. Restore authoring-only paths.
    sys.path.extend([str(ROOT / "src"), str(ROOT)])
    import biocompiler as bc
    from biocompiler.compiler import components, pipeline
    from biocompiler.compiler.passes import PassResult
    from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION
    from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig
    from biocompiler.semantics.types import BOOLEAN, LEVEL, DURATION
    from biocompiler.ir.composition import CompositionInstance
    from examples.checked_pipeline import build_request as static_request
    from examples.temporal_pipeline import build_request as temporal_request
finally:
    sys.path[:] = _paths

OUTPUT = ROOT / "tests/conformance/pipeline-fixed-provider-semantics-v1.json"
SCHEMA = "biocompiler.pipeline_fixed_provider_semantics.v1"
CASES = ("static:requested", "static:selected_equal", "temporal:requested")
PROVIDERS = (("intent_to_behavior", "request"), ("behavior_to_synthetic", "fixed-view:intent_to_behavior"),
             ("synthetic_to_components", "fixed-view:behavior_to_synthetic"))
TYPES = {
    "biocompiler.compiler.passes": ("PassResult",),
    "biocompiler.artifacts.provenance": ("SourceLink",),
    "biocompiler.ir.behavior": ("BehaviorNode", "BehaviorProgram"),
    "biocompiler.ir.intent": ("SourceLocation",),
    "biocompiler.semantics.contracts": ("BehaviorRequirement",),
    "biocompiler.synthesis.synthetic": ("SyntheticCandidate", "SyntheticGeneratorConfig"),
    "biocompiler.ir.mechanism": ("MechanismNode", "MechanismProgram"),
    "biocompiler.semantics.realization": ("Observable",),
    "biocompiler.semantics.types": ("TypeSpec", "ScalarLiteral"),
    "biocompiler.verification.realization": ("InputBinding", "OutputBinding", "ObservationMap"),
    "biocompiler.ir.components": ("ComponentLock",),
    "biocompiler.ir.component_assembly": ("ComponentAssembly",),
    "biocompiler.registry.components": ("ComponentRegistry", "RegistryLock"),
    "biocompiler.ir.composition": ("CompositionRequest", "CompositionInstance", "LifecycleInterval", "Connection",
        "Provider", "DependencyBinding", "ResourcePool", "ResourceBinding"),
    "biocompiler.ir.component_contracts": ("ComponentRecord", "PinnedIdentity", "ParameterProvenance",
        "DependencyRequirement", "ProvidedCapability", "ResourceReservation", "SequenceReferenceMetadata", "SyntheticOperatorModel"),
    "biocompiler.semantics.component_contracts": ("OperatingDomain", "ValueDomain", "PortContract"),
    "biocompiler.semantics.context": ("TargetContext",),
}
SAFE = {getattr(importlib.import_module(module), name) for module, names in TYPES.items() for name in names}
PENDING = ["136 original fixed boundaries and 476 manager contexts remain mandatory",
    "original fixed-registration interception is not exercised by these later wrappers",
    "complete captured typed-object aliases and named source origins require fresh installed native replay",
    "cross-session aliases, arbitrary external contexts and public default cutover remain separate gates"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def plain(value):
    """Observe trusted raw fields only, never a domain conversion or property."""
    if value is None or type(value) in (bool, int, float, str):
        return {"scalar": type(value).__name__, "value": value}
    if isinstance(value, Enum):
        return {"enum": type(value).__module__ + "." + type(value).__qualname__, "value": plain(value.value)}
    if type(value) in (dict, MappingProxyType):
        return {"mapping": type(value).__name__, "items": [[plain(key), plain(item)] for key, item in value.items()]}
    if type(value) in (list, tuple):
        return {"sequence": type(value).__name__, "items": [plain(item) for item in value]}
    if type(value) in SAFE:
        schema = vars(type(value)).get("schema_version")
        return {"class": type(value).__module__ + "." + type(value).__qualname__,
            "fields": [[item.name, plain(object.__getattribute__(value, item.name))] for item in fields(value)],
            "instance_fields": list(vars(value)),
            "class_schema": schema if type(schema) is str and "schema_version" not in vars(value) else None}
    raise AssertionError("Unsupported fixed provider observation type: " + type(value).__name__)


def authority(identity):
    assert identity in CASES
    temporal = identity.startswith("temporal:")
    request, history = (temporal_request if temporal else static_request)()
    # Author an explicit logical provenance path before this new witness freezes
    # its independent request. Never rewrite an existing frozen corpus.
    intent = replace(request.build_request.intent, nodes=tuple(replace(node, source=replace(node.source,
        file=Path(node.source.file).resolve().relative_to(ROOT).as_posix()) if Path(node.source.file).is_absolute()
        else node.source) if node.source is not None else node for node in request.build_request.intent.nodes))
    preferences = {"minimize": "none"} if identity.endswith("selected_equal") else {}
    build = replace(request.build_request, intent=intent, preferences=preferences)
    behavior = bc.lower_to_behavior(build)
    request = bc.RealizationRequest.freeze(build, behavior,
        replace(request.contract, behavior_fingerprint=behavior.fingerprint), request.domain)
    config = SyntheticGeneratorConfig(**({"profile_version": TEMPORAL_PROFILE_VERSION} if temporal else {}))
    return request, history, 9 if temporal else 7, config


def source_origins(request):
    """Closed source-owned roots; no value matching or arbitrary introspection."""
    result = [("constant:BOOLEAN", BOOLEAN), ("constant:LEVEL", LEVEL), ("constant:DURATION", DURATION),
        ("constant:default_lifecycle", CompositionInstance.__dataclass_fields__["lifetime"].default)]
    for index, item in enumerate(request.domain.inputs):
        result.extend([(f"request:domain.inputs[{index}].observable", item.observable),
            (f"request:domain.inputs[{index}].observable.dtype", item.observable.dtype)])
    for index, item in enumerate(request.contract.requirements):
        result.extend([(f"request:contract.requirements[{index}].observable", item.observable),
            (f"request:contract.requirements[{index}].observable.dtype", item.observable.dtype)])
    result.extend((f"request:behavior.nodes[{index}].source", node.source)
        for index, node in enumerate(request.behavior.nodes) if node.source is not None)
    return result


class Ledger:
    def __init__(self):
        self.retained = []
        self.semantic_objects, self.semantic_paths = [], []

    def semantics(self, value, path):
        if type(value) in SAFE:
            index = next((index for index, previous in enumerate(self.semantic_objects) if previous is value), None)
            if index is None:
                index = len(self.semantic_objects)
                self.semantic_objects.append(value)
                self.semantic_paths.append([])
            self.semantic_paths[index].append(path)
            for field in fields(value):
                self.semantics(object.__getattribute__(value, field.name), path + [field.name])
        elif type(value) in (dict, MappingProxyType):
            for key, item in value.items():
                assert type(key) is str
                self.semantics(item, path + [key])
        elif type(value) in (list, tuple):
            for index, item in enumerate(value):
                self.semantics(item, path + [index])

    def graph(self):
        return [{"class": type(value).__module__ + "." + type(value).__qualname__, "paths": paths}
            for value, paths in zip(self.semantic_objects, self.semantic_paths) if len(paths) > 1]

    def ref(self, value):
        for index, previous in enumerate(self.retained):
            if previous is value:
                return "object/" + str(index)
        self.retained.append(value)
        return "object/" + str(len(self.retained) - 1)

    def mutable_tree(self, value):
        if type(value) in (dict, MappingProxyType):
            return {"kind": type(value).__name__, "ref": self.ref(value),
                "items": [[key, self.mutable_tree(item)] for key, item in value.items()]}
        if type(value) in (list, tuple):
            return {"kind": type(value).__name__, "ref": self.ref(value), "items": [self.mutable_tree(item) for item in value]}
        assert value is None or type(value) in (bool, int, float, str)
        return plain(value)

    def proposal(self, value):
        assert type(value) is PassResult
        output = value.output
        aliases = {"proposal": self.ref(value), "output": self.ref(output), "source_links": self.ref(value.source_links),
            "link_elements": [self.ref(item) for item in value.source_links], "observation": self.mutable_tree(value.observation_map)}
        if type(output) is bc.BehaviorProgram:
            aliases["behavior_source_links"] = self.ref(output.source_links)
        elif type(output) is bc.SyntheticCandidate:
            aliases.update(generator_config=self.ref(output.generator_config), source_map=self.ref(output.source_map),
                typed_observation=self.ref(output.observation_map))
        else:
            assert type(output) is bc.ComponentAssembly
            composition = output.composition
            aliases.update(registry=self.ref(output.registry), composition=self.ref(composition),
                composition_target=self.ref(composition.target), behavior_sources=self.ref(output.behavior_sources),
                typed_observation=self.ref(output.observation_map),
                lock_components=[[item.node_id, self.ref(item)] for item in composition.registry_lock.components],
                instances=[[item.id, self.ref(item.component), self.ref(item.required_domain)] for item in composition.instances],
                supported_domains=[[item.id, self.ref(item.supported_domain)] for item in output.registry.components])
        return {"value": plain(value), "aliases": aliases}


def original_factory(request, history, *, until, config):
    return components.run_component_pipeline(request, history, until=until, config=config).manager


def original_registrations(manager):
    assert type(manager) is pipeline.PassManager
    return manager._passes


def run_case(identity, *, manager_factory=original_factory, registrations=original_registrations,
             observe=None, retain_manager=None):
    request, history, until, config = authority(identity)
    manager = manager_factory(request, history, until=until, config=config)
    if retain_manager is not None:
        retain_manager(manager)
    ledger = Ledger()
    ledger.semantics(request.target, ["target"])
    ledger.semantics(config, ["requested_config"])
    roots = {"target": ledger.ref(request.target), "manager_target": ledger.ref(manager.target), "requested_config": ledger.ref(config)}
    origins = []
    for name, value in source_origins(request):
        ledger.semantics(value, ["source_origins", name])
        origins.append({"origin": name, "ref": ledger.ref(value), "value": plain(value)})
    initial = registrations(manager)
    events = []
    for pass_id, input_id in PROVIDERS:
        contract, producer, validators = initial[pass_id]
        proposed = replace(contract, version=contract.version + ".fixed_view_witness")
        event = {"pass_id": pass_id, "input_id": input_id, "output_id": "fixed-view:" + pass_id,
            "contract": proposed.to_dict(), "calls": []}
        def wrapper(context, provider=producer, event=event, pass_id=pass_id):
            event["context_target"] = ledger.ref(context.target)
            first = None
            for ordinal in range(2):
                if observe is not None:
                    observe("before", manager, pass_id, ordinal, context, None)
                result = provider(context)
                ledger.semantics(result, ["calls", pass_id, ordinal])
                event["calls"].append(ledger.proposal(result))
                if observe is not None:
                    observe("after", manager, pass_id, ordinal, context, result)
                if first is None:
                    first = result
            return first
        manager.register(proposed, wrapper, validators)
        record = manager.run(pass_id, input_id, event["output_id"],
            configuration=config.to_dict() if pass_id == "behavior_to_synthetic" else None)
        event["record"] = record.to_dict()
        events.append(event)
    return {"id": identity, "authority": {"request": request.to_dict(), "history": [item.to_dict() for item in history],
        "until": until, "config": config.to_dict()}, "roots": roots, "source_origins": origins, "events": events,
        "retained_objects": len(ledger.retained), "semantic_alias_groups": ledger.graph()}


def capture():
    cases = [run_case(identity) for identity in CASES]
    paths = {"tools/capture_pipeline_fixed_provider_semantics.py", "examples/checked_pipeline.py", "examples/temporal_pipeline.py"}
    paths.update("src/" + module.replace(".", "/") + ".py" for module in TYPES)
    paths.update("src/biocompiler/" + path for path in ("compiler/synthetic.py", "compiler/components.py", "compiler/pipeline.py",
        "compiler/request.py", "compiler/behavior.py", "ir/serialization.py", "synthesis/components.py", "synthesis/selection.py", "registry/synthetic.py"))
    result = {"schema_version": SCHEMA, "source_files": {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)},
        "coverage": {"cases": len(cases), "providers": sum(len(case["events"]) for case in cases),
            "returns": sum(len(event["calls"]) for case in cases for event in case["events"])},
        "pending": PENDING, "cases": cases}
    result["inventory_fingerprint"] = sha(canonical(result))
    return result


def main():
    if OUTPUT.exists():
        raise SystemExit("Refusing to replace frozen original fixed-provider observations")
    OUTPUT.write_bytes(canonical(capture()) + b"\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
