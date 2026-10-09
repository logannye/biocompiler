"""Original module bundles and proposed expansion, with fresh native handoff.

These data-only authoring values never grant a checked-linkage capability.
The existing module composer proposes ordinary source; native checking derives
that source independently from the retained originals.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, TypeVar, cast

from biocompiler.core_client import JsonValue, CoreProtocolError, decode_json, encode_json, _object as _wire_object
from biocompiler.core_policy_operational import _fingerprint
from . import model as m, modules as mod
from .serialization import from_data, to_data

if TYPE_CHECKING:
    from biocompiler.core_policy_module_linking import PolicyModuleLinkingClient, PolicyModuleLinkingResult, PolicyModuleMaterialClient, PolicyModuleMaterialResult

BUNDLE_SCHEMA = "biocompiler.policy_module_bundle.v0.1"
BUNDLE_PROFILE = "biocompiler.policy_module_linking.v0.1"
_LIMITS = {"max_work": 16_000_000, "max_bytes": 8 * 1024 * 1024, "max_depth": 64,
           "max_instances": 64, "max_declarations": 4096, "max_ports": 256}
_TEMPLATE_FIELDS = {"id", "version", "semantics", "inputs", "outputs", "declarations", "private", "assumptions", "guarantees", "source_map"}
R = TypeVar("R", bound=m.Record)


@dataclass(frozen=True, slots=True)
class ModuleLinkingLimits:
    """Native verification ceilings; local composition keeps its 1M work limit."""
    max_work: int = 16_000_000
    max_bytes: int = 8 * 1024 * 1024
    max_depth: int = 64
    max_instances: int = 64
    max_declarations: int = 4096
    max_ports: int = 256

    def __post_init__(self) -> None:
        for name, maximum in _LIMITS.items():
            value = getattr(self, name)
            mod._require(type(value) is int and 0 < value <= maximum, "Module linkage limits must lower fixed positive ceilings")

    def to_data(self) -> dict[str, JsonValue]:
        self.__post_init__()
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def _authoring(self) -> mod.ModuleLimits:
        self.__post_init__()
        return mod.ModuleLimits(min(self.max_work, 1_000_000), self.max_bytes, self.max_depth,
                               self.max_instances, self.max_declarations, self.max_ports)


def _object(value: JsonValue, keys: set[str], label: str) -> dict[str, JsonValue]:
    try:
        return _wire_object(value, keys, label)
    except CoreProtocolError as error:
        raise mod.ModuleError(str(error)) from error


def _rows(value: JsonValue, label: str, maximum: int = 4096) -> list[JsonValue]:
    mod._require(type(value) is list and len(value) <= maximum, label + " requires a bounded ordered array")
    return cast(list[JsonValue], value)


def _text(value: JsonValue) -> str:
    mod._require(type(value) is str, "Expected module text")
    return cast(str, value)


def _record(value: JsonValue, kind: type[R]) -> R:
    return from_data(value, kind)


def _declaration(value: JsonValue) -> m.Declaration:
    record = from_data(value)
    mod._require(type(record) in mod._DECLARATIONS, "Expected complete source declaration")
    return cast(m.Declaration, record)


def _source(value: m.Record) -> JsonValue:
    return cast(JsonValue, to_data(value))


def _template(value: mod.ModuleTemplate) -> dict[str, JsonValue]:
    return {"id": value.id, "version": value.version, "semantics": _source(value.semantics),
        "inputs": [{"name": port.name, "declaration": _source(port.declaration), "access": port.access} for port in value.inputs],
        "outputs": [{"name": port.name, "declaration": _source(port.declaration), "access": port.access} for port in value.outputs],
        **{name: [_source(row) for row in cast(tuple[m.Record, ...], getattr(value, name))]
           for name in ("declarations", "private", "assumptions", "guarantees", "source_map")}}


def _port(value: JsonValue, *, output: bool) -> mod.InputPort | mod.OutputPort:
    row = _object(value, {"name", "declaration", "access"}, "Module port")
    access = _text(row["access"])
    mod._require(access in mod._PORT_KINDS, "Unknown module port access")
    kind = mod.OutputPort if output else mod.InputPort
    return kind(_text(row["name"]), _declaration(row["declaration"]), cast(mod.Access, access))


def _read_template(value: JsonValue, limits: ModuleLinkingLimits) -> mod.ModuleTemplate:
    row = _object(value, _TEMPLATE_FIELDS, "Complete module template")
    return mod.ModuleTemplate(_text(row["id"]), _text(row["version"]), _record(row["semantics"], m.SemanticBundle),
        tuple(cast(mod.InputPort, _port(item, output=False)) for item in _rows(row["inputs"], "Inputs", limits.max_ports)),
        tuple(cast(mod.OutputPort, _port(item, output=True)) for item in _rows(row["outputs"], "Outputs", limits.max_ports)),
        tuple(_declaration(item) for item in _rows(row["declarations"], "Declarations", limits.max_declarations)),
        tuple(_record(item, m.Ref) for item in _rows(row["private"], "Private")),
        tuple(_record(item, m.Requirement) for item in _rows(row["assumptions"], "Assumptions")),
        tuple(_record(item, m.Requirement) for item in _rows(row["guarantees"], "Guarantees")),
        tuple(_record(item, m.SourceSpan) for item in _rows(row["source_map"], "Source map")))


def _preflight(value: JsonValue, limits: ModuleLinkingLimits) -> None:
    """Bound data and cycles before decoding any original source or hashing pins."""
    limits.__post_init__()
    pending: list[tuple[JsonValue, int, bool]] = [(value, 0, False)]
    active: set[int] = set()
    work = 0
    while pending:
        item, depth, leaving = pending.pop()
        if leaving:
            active.remove(id(item))
            continue
        work += 1
        mod._require(work <= min(limits.max_work, 250_000) and depth <= limits.max_depth, "Module wire data exceeds traversal limits")
        mod._require(type(item) in (dict, list, str, int, bool, type(None)), "Module wire data must contain only exact JSON data")
        if type(item) in (dict, list):
            mod._require(id(item) not in active, "Cyclic module wire data is forbidden")
            active.add(id(item))
            pending.append((item, depth, True))
            if type(item) is dict:
                row = item
                mod._require(all(type(key) is str for key in row), "Module wire keys must be text")
                mod._require(work + len(pending) + 2 * len(row) <= min(limits.max_work, 250_000), "Module wire data exceeds traversal limits")
                children: list[JsonValue] = []
                children.extend(row)
                children.extend(row.values())
            else:
                children = cast(list[JsonValue], item)
            mod._require(work + len(pending) + len(children) <= min(limits.max_work, 250_000), "Module wire data exceeds traversal limits")
            pending.extend((child, depth + 1, False) for child in children)
    try:
        encode_json(value, limit=limits.max_bytes)
    except CoreProtocolError as error:
        raise mod.ModuleError(str(error)) from error


@dataclass(frozen=True, slots=True)
class ModuleBundle:
    context: m.PolicyProgram
    instances: tuple[mod.ModuleInstance, ...]
    limits: ModuleLinkingLimits = ModuleLinkingLimits()
    _template_order: tuple[mod.ModuleTemplate, ...] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        mod._require(type(self.context) is m.PolicyProgram and type(self.limits) is ModuleLinkingLimits,
                     "Module bundle needs an ordinary complete context and explicit linking limits")
        mod._require(type(self.instances) is tuple and len(self.instances) <= self.limits.max_instances,
                     "Module instances require a bounded immutable sequence")
        budget = mod._Budget(self.limits._authoring())
        budget.scan(self.context)
        budget.scan(self.instances)
        mod._require(all(type(item) is mod.ModuleInstance for item in self.instances), "Expected original module instances")
        if self._template_order is not None:
            mod._require(type(self._template_order) is tuple, "Original template order must be immutable")
            budget.scan(self._template_order)
        for instance in self.instances:
            mod._validate_instance(instance, budget)

    def to_data(self) -> dict[str, JsonValue]:
        self.__post_init__()
        templates: dict[tuple[str, str], dict[str, JsonValue]] = {}
        for original_template in self._template_order or ():
            mod._require(type(original_template) is mod.ModuleTemplate, "Expected original template record")
            key = (original_template.id, original_template.version)
            mod._require(key not in templates, "Duplicate original template identity")
            templates[key] = _template(original_template)
        used: set[tuple[str, str]] = set()
        instances: list[JsonValue] = []
        for instance in self.instances:
            template = _template(instance.template)
            key = (instance.template.id, instance.template.version)
            mod._require(key not in templates or templates[key] == template, "A template id/version cannot name distinct original bodies")
            templates[key] = template
            used.add(key)
            bindings: list[JsonValue] = []
            for binding in instance.bindings:
                target: JsonValue = ({"kind": "context", "reference": _source(binding.target)} if type(binding.target) is m.Ref else
                    {"kind": "output", "instance": cast(mod.ModuleOutput, binding.target).instance, "port": cast(mod.ModuleOutput, binding.target).port})
                bindings.append({"port": binding.port, "target": target})
            instances.append({"name": instance.name, "template": {"id": key[0], "version": key[1], "content_fingerprint": _fingerprint(template)},
                "bindings": bindings, "assumptions": [_source(row) for row in instance.assumptions]})
        mod._require(used == set(templates), "Unused original templates are forbidden")
        result: dict[str, JsonValue] = {"schema_version": BUNDLE_SCHEMA, "profile": BUNDLE_PROFILE, "context": _source(self.context),
            "templates": list(templates.values()), "instances": instances, "limits": self.limits.to_data()}
        _preflight(result, self.limits)
        return result


def bundle_from_data(value: JsonValue) -> ModuleBundle:
    """Closed data codec; neither input hashes nor reconstruction imply checking."""
    _preflight(value, ModuleLinkingLimits())
    row = _object(value, {"schema_version", "profile", "context", "templates", "instances", "limits"}, "Original module bundle")
    mod._require(row["schema_version"] == BUNDLE_SCHEMA and row["profile"] == BUNDLE_PROFILE, "Unknown module bundle profile")
    raw_limits = _object(row["limits"], set(_LIMITS), "Module linking limits")
    mod._require(all(type(number) is int for number in raw_limits.values()), "Module linking limits must be exact integers")
    limits = ModuleLinkingLimits(**cast(dict[str, int], raw_limits))
    _preflight(value, limits)
    templates: dict[tuple[str, str, str], mod.ModuleTemplate] = {}
    identities: set[tuple[str, str]] = set()
    for raw in _rows(row["templates"], "Templates", limits.max_instances):
        template = _read_template(raw, limits)
        key = (template.id, template.version)
        mod._require(key not in identities, "Duplicate template identity")
        identities.add(key)
        templates[(*key, _fingerprint(raw))] = template
    instances = []
    used: set[tuple[str, str, str]] = set()
    for raw in _rows(row["instances"], "Instances", limits.max_instances):
        item = _object(raw, {"name", "template", "bindings", "assumptions"}, "Module instance")
        pin = _object(item["template"], {"id", "version", "content_fingerprint"}, "Complete template pin")
        pin_key = (_text(pin["id"]), _text(pin["version"]), _text(pin["content_fingerprint"]))
        mod._require(pin_key in templates, "Template pin does not identify its complete original body")
        used.add(pin_key)
        bindings = []
        for raw_binding in _rows(item["bindings"], "Bindings", limits.max_ports):
            binding = _object(raw_binding, {"port", "target"}, "Module binding")
            raw_target = binding["target"]
            mod._require(type(raw_target) is dict, "Binding target must be closed data")
            target_row = cast(dict[str, JsonValue], raw_target)
            target: m.Ref | mod.ModuleOutput
            if target_row.get("kind") == "context":
                target_row = _object(raw_target, {"kind", "reference"}, "Context target")
                target = _record(target_row["reference"], m.Ref)
            else:
                target_row = _object(raw_target, {"kind", "instance", "port"}, "Output target")
                mod._require(target_row["kind"] == "output", "Unknown binding target kind")
                target = mod.ModuleOutput(_text(target_row["instance"]), _text(target_row["port"]))
            bindings.append(mod.ModuleBinding(_text(binding["port"]), target))
        instances.append(mod.ModuleInstance(templates[pin_key], _text(item["name"]), tuple(bindings),
            tuple(_record(raw, m.Requirement) for raw in _rows(item["assumptions"], "Instance assumptions"))))
    mod._require(used == set(templates), "Unused original templates are forbidden")
    result = ModuleBundle(_record(row["context"], m.PolicyProgram), tuple(instances), limits)
    object.__setattr__(result, "_template_order", tuple(templates.values()))
    return result


@dataclass(frozen=True, slots=True)
class ModuleProposal:
    """Immutable transport snapshot, not a checked or admitted program."""
    _json: bytes

    @property
    def modules(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.to_data()["modules"])

    @property
    def program(self) -> m.PolicyProgram:
        return from_data(self.to_data()["program"], m.PolicyProgram)

    def to_data(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._json))


def prepare(bundle: ModuleBundle) -> ModuleProposal:
    mod._require(type(bundle) is ModuleBundle, "Expected an original ModuleBundle")
    original = bundle.to_data()
    snapshot = bundle_from_data(original)
    context = snapshot.context
    program = mod.compose_modules(context.id, semantics=context.semantics, declarations=context.declarations,
        instances=snapshot.instances, source_map=context.source_map, limits=snapshot.limits._authoring())
    return ModuleProposal(encode_json({"modules": original, "program": _source(program)}))


def check(proposal: ModuleProposal, *, client: PolicyModuleLinkingClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyModuleLinkingResult:
    return client.check(proposal.modules, _source(proposal.program), cancelled=cancelled)


def replay(proposal: ModuleProposal, *, report: JsonValue, client: PolicyModuleLinkingClient,
           cancelled: Callable[[], bool] | None = None) -> PolicyModuleLinkingResult:
    return client.replay(proposal.modules, _source(proposal.program), report, cancelled=cancelled)


def compile_material(modules: JsonValue, request: JsonValue, *, limits: JsonValue, client: PolicyModuleMaterialClient,
                     cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
    return client.compile(modules, request, limits, cancelled=cancelled)


def check_material(modules: JsonValue, request: JsonValue, *, candidate: JsonValue, limits: JsonValue,
                   client: PolicyModuleMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
    return client.check(modules, request, candidate, limits, cancelled=cancelled)


def replay_material(modules: JsonValue, request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
                    client: PolicyModuleMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
    return client.replay(modules, request, candidate, limits, report, cancelled=cancelled)


def export_material(modules: JsonValue, request: JsonValue, *, candidate: JsonValue, limits: JsonValue,
                    client: PolicyModuleMaterialClient, output: Path, replace: bool = False,
                    input_paths: Iterable[Path] = (), cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
    from .material import _publish_fresh
    return _publish_fresh(lambda: client.export(modules, request, candidate, limits, cancelled=cancelled),
        operation="export-policy-module-material", status="checked_component_material", output=output,
        replace=replace, input_paths=input_paths, cancelled=cancelled)


__all__ = ["ModuleLinkingLimits", "ModuleBundle", "ModuleProposal", "bundle_from_data", "prepare", "check", "replay",
           "compile_material", "check_material", "replay_material", "export_material"]
