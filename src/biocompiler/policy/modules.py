"""Bounded hygienic policy modules with checked authoring interfaces.

Composition produces ordinary source declarations for fresh native assessment.
Neither an interface check nor an acknowledged premise proves a guarantee.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, fields, replace
import re
from typing import Literal, TypeVar, cast

from . import model as m
from .serialization import PolicySerializationError, from_data, to_data
from .validation import check

__all__ = [
    "Access", "ModuleError", "ModuleLimits", "InputPort", "OutputPort",
    "ModuleOutput", "ModuleBinding", "Footprint", "ModuleTemplate",
    "ModuleInstance", "instantiate", "compose_modules",
]

Access = Literal["context", "read", "write", "request"]
_DECLARATIONS = (m.Role, m.Subject, m.Encounter, m.SpatialScope, m.Clock,
                 m.Observation, m.StateStore, m.Effect, m.Rule, m.Machine,
                 m.Transition, m.Channel, m.Message, m.Requirement, m.Parameter)
_OWNED = (m.StateStore, m.Effect, m.Machine)
_PORT_KINDS: dict[str, tuple[type[m.Record], ...]] = {
    "context": (m.Role, m.Subject, m.Encounter, m.SpatialScope, m.Clock, m.Channel),
    "read": (m.Observation, m.StateStore, m.Parameter, m.Effect, m.Message),
    "write": (m.StateStore, m.Machine),
    "request": (m.Effect, m.Message),
}
_CAPABILITIES = {"context": frozenset({"context"}),
                 "read": frozenset({"context", "read"}),
                 "write": frozenset({"context", "read", "write"}),
                 "request": frozenset({"context", "read", "request"})}
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
R = TypeVar("R", bound=m.Record)


class ModuleError(ValueError):
    """An authoring contract is malformed or module composition is unsafe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModuleError(message)


def _name(value: object, label: str) -> str:
    _require(type(value) is str and _NAME.fullmatch(value) is not None,
             label + " must be a simple 1-64 character identifier")
    return cast(str, value)


def _tuple(value: object, label: str) -> tuple[object, ...]:
    _require(type(value) in (tuple, list), label + " must be an explicit finite sequence")
    _require(len(cast(tuple[object, ...], value)) <= 4096, label + " exceeds its item bound")
    return tuple(cast(tuple[object, ...], value))


@dataclass(frozen=True)
class ModuleLimits:
    max_work: int = 1_000_000
    max_bytes: int = 8 * 1024 * 1024
    max_depth: int = 64
    max_instances: int = 64
    max_declarations: int = 4096
    max_ports: int = 256

    def __post_init__(self) -> None:
        ceilings = (1_000_000, 8 * 1024 * 1024, 64, 64, 4096, 256)
        for field, maximum in zip(fields(self), ceilings):
            value = getattr(self, field.name)
            _require(type(value) is int and 0 < value <= maximum, "Module limits must be positive and within fixed safety ceilings")


class _Budget:
    def __init__(self, limits: ModuleLimits = ModuleLimits()):
        _require(type(limits) is ModuleLimits, "Expected explicit module limits")
        limits.__post_init__()
        self.limits = limits
        self.work = 0
        self.bytes = 0

    def charge(self, count: int = 1) -> None:
        self.work += count
        _require(self.work <= self.limits.max_work, "Module composition exceeds its work bound")

    def scan(self, value: object, depth: int = 0, active: set[int] | None = None) -> None:
        self.charge()
        _require(depth <= self.limits.max_depth, "Module data exceeds its depth bound")
        if value is None or type(value) is bool:
            return
        if type(value) is str:
            _require(len(value) <= 262_144, "Module text exceeds its string bound")
            try:
                self.bytes += len(value.encode("utf-8"))
            except UnicodeError as error:
                raise ModuleError("Module strings must be valid UTF-8") from error
            _require(self.bytes <= self.limits.max_bytes, "Module composition exceeds its aggregate byte bound")
            return
        if type(value) is int:
            _require(value.bit_length() <= 1024, "Module integer exceeds its numeric bound")
            self.bytes += len(str(value))
            _require(self.bytes <= self.limits.max_bytes, "Module composition exceeds its aggregate byte bound")
            return
        _require(type(value) is tuple or type(value) in _MODULE_RECORDS or type(value) in m.REGISTRY.values(),
                 "Module data must contain only reviewed immutable records")
        active = set() if active is None else active
        identity = id(value)
        _require(identity not in active, "Cyclic module data is forbidden")
        active.add(identity)
        try:
            if type(value) is tuple:
                _require(len(value) <= self.limits.max_work - self.work, "Module sequence exceeds remaining work")
                for item in value:
                    self.scan(item, depth + 1, active)
            else:
                for field in fields(cast(m.Record, value)):
                    self.scan(field.name, depth + 1, active)
                    self.scan(getattr(value, field.name), depth + 1, active)
        finally:
            active.remove(identity)


def _snapshot(value: R, budget: _Budget) -> R:
    budget.scan(value)
    try:
        return from_data(to_data(value), type(value))
    except (PolicySerializationError, TypeError, RecursionError, OverflowError) as error:
        raise ModuleError("Invalid closed policy record: " + str(error)) from error


def _sequence_field(owner: object, name: str) -> None:
    object.__setattr__(owner, name, _tuple(getattr(owner, name), name))


@dataclass(frozen=True)
class InputPort:
    """A full nominal declaration signature and explicit allowed operations."""
    name: str
    declaration: m.Declaration
    access: Access = "read"

    def __post_init__(self) -> None:
        _validate_port(self)


@dataclass(frozen=True)
class OutputPort:
    """An explicitly exported local declaration with its complete signature."""
    name: str
    declaration: m.Declaration
    access: Access = "read"

    def __post_init__(self) -> None:
        _validate_port(self)


def _validate_port(port: InputPort | OutputPort) -> None:
    _name(port.name, "Port name")
    _require(type(port.access) is str and port.access in _PORT_KINDS, "Unknown port access mode")
    _require(type(port.declaration) in _PORT_KINDS[port.access], "Port declaration kind does not support its access mode")


@dataclass(frozen=True)
class ModuleOutput:
    """A connection through one named instance output; never a raw private Ref."""
    instance: str
    port: str

    def __post_init__(self) -> None:
        _name(self.instance, "Instance name")
        _name(self.port, "Output port name")


@dataclass(frozen=True)
class ModuleBinding:
    port: str
    target: m.Ref | ModuleOutput

    def __post_init__(self) -> None:
        _name(self.port, "Input port name")
        _require(type(self.target) in (m.Ref, ModuleOutput), "Bindings require a nominal Ref or ModuleOutput")


@dataclass(frozen=True)
class Footprint:
    """Conservative syntactic may-read/write/request inventory, not a proof."""
    reads: tuple[m.Ref, ...]
    writes: tuple[m.Ref, ...]
    requests: tuple[m.Ref, ...]


@dataclass(frozen=True)
class ModuleTemplate:
    id: str
    version: str
    semantics: m.SemanticBundle
    inputs: tuple[InputPort, ...]
    outputs: tuple[OutputPort, ...]
    declarations: tuple[m.Declaration, ...]
    private: tuple[m.Ref, ...] = ()
    assumptions: tuple[m.Requirement, ...] = ()
    guarantees: tuple[m.Requirement, ...] = ()
    source_map: tuple[m.SourceSpan, ...] = ()

    def __post_init__(self) -> None:
        for name in ("inputs", "outputs", "declarations", "private", "assumptions", "guarantees", "source_map"):
            _sequence_field(self, name)
        _validate_template(self, _Budget())

    def footprint(self) -> Footprint:
        return _validate_template(self, _Budget()).footprint


@dataclass(frozen=True)
class ModuleInstance:
    """Original composition authority. There is no accepted flattened cache."""
    template: ModuleTemplate
    name: str
    bindings: tuple[ModuleBinding, ...]
    assumptions: tuple[m.Requirement, ...] = ()

    def __post_init__(self) -> None:
        _sequence_field(self, "bindings")
        _sequence_field(self, "assumptions")
        _validate_instance(self, _Budget())

    def output(self, name: str) -> ModuleOutput:
        data = _validate_instance(self, _Budget())
        _require(name in data.outputs, "Instance has no declared output port " + name)
        return ModuleOutput(self.name, name)


_MODULE_RECORDS = (InputPort, OutputPort, ModuleOutput, ModuleBinding, Footprint,
                   ModuleTemplate, ModuleInstance)


@dataclass(frozen=True)
class _TemplateData:
    program: m.PolicyProgram
    inputs: dict[str, InputPort]
    outputs: dict[str, OutputPort]
    body: tuple[m.Declaration, ...]
    private: frozenset[str]
    footprint: Footprint


def _walk(value: object, budget: _Budget) -> Iterator[m.Record]:
    """Traverse only already bounded snapshots, counting repeated occurrences."""
    stack = [value]
    while stack:
        budget.charge()
        item = stack.pop()
        if isinstance(item, m.Record):
            yield item
            stack.extend(getattr(item, field.name) for field in reversed(fields(item)))
        elif type(item) is tuple:
            stack.extend(reversed(item))


def _references(value: object, budget: _Budget) -> tuple[m.Ref, ...]:
    return tuple(item for item in _walk(value, budget) if type(item) is m.Ref)


def _footprint(declarations: tuple[m.Declaration, ...], budget: _Budget) -> Footprint:
    reads: set[m.Ref] = set()
    writes: set[m.Ref] = set()
    requests: set[m.Ref] = set()
    for item in _walk(declarations, budget):
        if type(item) is m.Expr and item.ref is not None and item.op in (
                "observe", "state", "parameter", "updated", "effect_event", "message_event"):
            reads.add(item.ref)
        elif type(item) is m.Assignment:
            writes.add(item.state)
        elif type(item) is m.StateStore and item.reset is not None:
            writes.add(m.Ref(item.id, "StateStore"))
        elif isinstance(item, (m.Rule, m.Transition)):
            requests.update(item.effects)
            requests.update(item.emissions)
            if type(item) is m.Transition:
                reads.add(item.machine)
                writes.add(item.machine)
    def order(ref: m.Ref) -> tuple[str, str]:
        return (ref.kind, ref.id)
    return Footprint(tuple(sorted(reads, key=order)), tuple(sorted(writes, key=order)), tuple(sorted(requests, key=order)))


def _same(left: m.Record, right: m.Record, budget: _Budget) -> bool:
    budget.scan(left)
    budget.scan(right)
    return to_data(left) == to_data(right)


def _check_program(program: m.PolicyProgram) -> None:
    report = check(program)
    if report.status != "complete":
        message = "; ".join(error.code + ": " + error.message for error in report.errors[:3])
        raise ModuleError("Expanded module source is structurally invalid: " + message)


def _validate_template(template: ModuleTemplate, budget: _Budget) -> _TemplateData:
    _require(type(template) is ModuleTemplate, "Expected an original ModuleTemplate")
    _require(all(type(getattr(template, name)) is tuple for name in ("inputs", "outputs", "declarations", "private", "assumptions", "guarantees", "source_map")),
             "Module template sequences must be frozen tuples")
    budget.scan(template)
    _name(template.id, "Module identity")
    _require(type(template.version) is str and 0 < len(template.version) <= 128, "Module version must be explicit bounded text")
    _require(type(template.semantics) is m.SemanticBundle, "Module semantics must be explicit")
    _require(len(template.inputs) + len(template.outputs) <= budget.limits.max_ports, "Module exceeds its port bound")
    inputs: dict[str, InputPort] = {}
    outputs: dict[str, OutputPort] = {}
    formal: dict[str, m.Declaration] = {}
    for port in template.inputs:
        _require(type(port) is InputPort, "Expected a typed input port")
        _validate_port(port)
        _require(port.name not in inputs and port.declaration.id not in formal, "Duplicate input port or formal identity")
        declaration = _snapshot(port.declaration, budget)
        inputs[port.name] = InputPort(port.name, declaration, port.access)
        formal[declaration.id] = declaration
    body = tuple(_snapshot(value, budget) for value in template.declarations + template.assumptions + template.guarantees)
    _require(len(body) + len(formal) <= budget.limits.max_declarations, "Module exceeds its declaration bound")
    local: dict[str, m.Declaration] = {}
    for value in body:
        _require(type(value) in _DECLARATIONS, "Module body contains a nondeclaration")
        _require(value.id not in local and value.id not in formal, "Duplicate or captured module identity")
        local[value.id] = value
    _require(all(type(value) is not m.Requirement for value in template.declarations),
             "Put module requirements explicitly in assumptions or guarantees")
    _require(all(type(value) is m.Requirement and value.kind == "assumption" for value in template.assumptions),
             "Module premises must already be complete assumption Requirements")
    _require(all(type(value) is m.Requirement and value.kind != "assumption" for value in template.guarantees),
             "Guarantees must retain their original non-assumption Requirement kinds")
    semantics = _snapshot(template.semantics, budget)
    # Definition formals are lexical. Keep their exact pinned body; a module
    # cannot capture ambient declarations in a definition and leave stale pins.
    for definition in semantics.definitions:
        formals = {parameter.id for parameter in definition.parameters}
        for reference in _references(definition, budget):
            _require(reference.kind == "Parameter" and reference.id in formals,
                     "Module definitions cannot capture program-local references")
    for declaration in formal.values():
        for reference in _references(declaration, budget):
            _require(reference.id in formal, "Input signature depends on a hidden local declaration")
    for output_port in template.outputs:
        _require(type(output_port) is OutputPort, "Expected a typed output port")
        _validate_port(output_port)
        _require(output_port.name not in outputs, "Duplicate output port")
        local_output = local.get(output_port.declaration.id)
        _require(local_output is not None and _same(cast(m.Record, local_output), output_port.declaration, budget),
                 "Output signature must equal its complete local declaration")
        outputs[output_port.name] = OutputPort(output_port.name, cast(m.Declaration, local_output), output_port.access)
    exported = {port.declaration.id for port in outputs.values()}
    _require(len(exported) == len(outputs), "A local identity may have only one output interface")
    private: set[str] = set()
    for reference in template.private:
        _require(type(reference) is m.Ref and reference.id in local, "Private ownership must name a local declaration")
        declaration = local[reference.id]
        _require(reference.kind == type(declaration).__name__, "Private ownership reference kind differs")
        _require(reference.id not in private and reference.id not in exported, "Private identities cannot be duplicated or exported")
        private.add(reference.id)
    required_private = {value.id for value in body if type(value) in _OWNED} - exported
    _require(required_private <= private, "Every unexported state, machine and effect requires explicit private ownership")
    for output_port in outputs.values():
        for reference in _references(output_port.declaration, budget):
            _require(reference.id in formal or reference.id in exported,
                     "Output signature exposes a private or undeclared local dependency")
    known = {**formal, **local}
    for reference in _references(body, budget):
        _require(reference.id in known and reference.kind == type(known[reference.id]).__name__,
                 "Module has a hidden external or incorrectly typed reference")
    for item in _walk(body, budget):
        if type(item) is m.Arbitration:
            for identity in item.order:
                _require(identity in local and type(local[identity]) in (m.Rule, m.Transition),
                         "Arbitration order must name local rule or transition identities")
    footprint = _footprint(body, budget)
    by_identity = {port.declaration.id: port for port in inputs.values()}
    for operation, references in (("read", footprint.reads), ("write", footprint.writes), ("request", footprint.requests)):
        for reference in references:
            if reference.id in by_identity:
                _require(operation in _CAPABILITIES[by_identity[reference.id].access],
                         "Input port does not authorize " + operation + ": " + reference.id)
    _require(all(type(span) is m.SourceSpan for span in template.source_map), "Module source map requires SourceSpan records")
    source_map = tuple(_snapshot(span, budget) for span in template.source_map)
    _require(all(span.declaration_id in local for span in source_map), "Module source map names an input or unknown declaration")
    program = m.PolicyProgram(template.id, semantics, tuple(formal.values()) + body, source_map)
    _check_program(program)
    return _TemplateData(program, inputs, outputs, body, frozenset(private), footprint)


def _validate_instance(instance: ModuleInstance, budget: _Budget) -> _TemplateData:
    _require(type(instance) is ModuleInstance, "Expected original module instance authority")
    _require(type(instance.bindings) is tuple and type(instance.assumptions) is tuple, "Module instance sequences must be frozen tuples")
    budget.scan(instance)
    _name(instance.name, "Instance name")
    data = _validate_template(instance.template, budget)
    bindings: set[str] = set()
    for binding in instance.bindings:
        _require(type(binding) is ModuleBinding, "Expected typed module bindings")
        binding.__post_init__()
        if type(binding.target) is m.Ref:
            _snapshot(binding.target, budget)
        else:
            cast(ModuleOutput, binding.target).__post_init__()
        _require(binding.port in data.inputs and binding.port not in bindings, "Unknown or duplicate module input binding")
        bindings.add(binding.port)
    _require(bindings == set(data.inputs), "Every module input requires an explicit binding")
    supplied: dict[str, m.Requirement] = {}
    for assumption in instance.assumptions:
        _require(type(assumption) is m.Requirement and assumption.kind == "assumption", "Premise acknowledgment requires the complete assumption body")
        _require(assumption.id not in supplied, "Duplicate acknowledged assumption")
        supplied[assumption.id] = _snapshot(assumption, budget)
    required = {value.id: value for value in instance.template.assumptions}
    _require(set(supplied) == set(required), "Missing or undeclared module assumptions")
    for identity, assumption in required.items():
        _require(_same(assumption, supplied[identity], budget), "Acknowledged assumption content differs from the original premise")
    return data


def instantiate(template: ModuleTemplate, name: str, *, bindings: tuple[ModuleBinding, ...],
                assumptions: tuple[m.Requirement, ...] = ()) -> ModuleInstance:
    """Retain checked original authority; external signatures are checked at composition."""
    return ModuleInstance(template, name, bindings, assumptions)


def _rewrite(value: object, mapping: dict[str, m.Ref], budget: _Budget, *, declaration: bool = False) -> object:
    budget.charge()
    if type(value) is m.Ref:
        _require(value.id in mapping, "Reference escaped its module interface")
        return mapping[value.id]
    if type(value) in (m.DefinitionRef, m.SemanticDefinition, m.SemanticBundle):
        return value
    if type(value) is tuple:
        return tuple(_rewrite(item, mapping, budget) for item in value)
    if isinstance(value, m.Record):
        updates = {field.name: _rewrite(getattr(value, field.name), mapping, budget) for field in fields(value)}
        if declaration:
            updates["id"] = mapping[cast(m.Declaration, value).id].id
        if type(value) is m.Arbitration:
            updates["order"] = tuple(mapping[identity].id for identity in value.order)
        if type(value) is m.SourceSpan:
            updates["declaration_id"] = mapping[value.declaration_id].id
        return replace(value, **updates)
    return value


def compose_modules(identity: str, *, semantics: m.SemanticBundle,
                    declarations: tuple[m.Declaration, ...] = (), instances: tuple[ModuleInstance, ...],
                    source_map: tuple[m.SourceSpan, ...] = (), limits: ModuleLimits = ModuleLimits()) -> m.PolicyProgram:
    """Revalidate original modules, signatures, effects and ownership; return source only.

    Instance outputs can connect only through ModuleOutput. Native checking of
    the returned complete source is still required before any acceptance.
    """
    _name(identity, "Program identity")
    budget = _Budget(limits)
    original_instances = _tuple(instances, "instances")
    _require(len(original_instances) <= limits.max_instances, "Composition exceeds its instance bound")
    original_base = _tuple(declarations, "declarations")
    _require(len(original_base) <= limits.max_declarations, "Context exceeds its declaration bound")
    base = tuple(_snapshot(cast(m.Declaration, value), budget) for value in original_base)
    _require(all(type(value) in _DECLARATIONS for value in base), "Context contains nondeclarations")
    base_semantics = _snapshot(semantics, budget)
    _require(type(base_semantics) is m.SemanticBundle, "Composition requires explicit semantic authority")
    base_map: dict[str, m.Declaration] = {}
    for value in base:
        _require(value.id not in base_map, "Duplicate context declaration")
        base_map[value.id] = value
    instance_map: dict[str, ModuleInstance] = {}
    validated: dict[str, _TemplateData] = {}
    for original in original_instances:
        _require(type(original) is ModuleInstance, "Composition requires original ModuleInstance records")
        instance = cast(ModuleInstance, original)
        _require(instance.name not in instance_map, "Duplicate instance namespace")
        validated[instance.name] = _validate_instance(instance, budget)
        instance_map[instance.name] = instance
    _require(len(base) + sum(len(data.body) for data in validated.values()) <= limits.max_declarations,
             "Expanded composition exceeds its declaration bound")
    prefixes = tuple(name + "/" for name in instance_map)
    for value in base:
        _require(not value.id.startswith(prefixes), "Context cannot shadow an instance namespace")
    for item in _walk(base, budget):
        if type(item) is m.Ref:
            _require(not item.id.startswith(prefixes), "Raw context references cannot escape a module interface")
        elif type(item) is m.Arbitration:
            _require(not any(identity.startswith(prefixes) for identity in item.order),
                     "Raw context arbitration cannot name module-local rule identities")
    for definition in base_semantics.definitions:
        for reference in _references(definition, budget):
            _require(not reference.id.startswith(prefixes), "Context definitions cannot capture instance-local references")
    expanded: dict[str, tuple[m.Declaration, ...]] = {}
    expanded_outputs: dict[str, dict[str, tuple[OutputPort, m.Declaration]]] = {}
    expanded_maps: dict[str, dict[str, m.Ref]] = {}
    visiting: set[str] = set()

    def expand(name: str) -> None:
        budget.charge()
        if name in expanded:
            return
        _require(name not in visiting, "Cyclic module output connections are unsupported")
        visiting.add(name)
        instance, data = instance_map[name], validated[name]
        mapping = {value.id: m.Ref(name + "/" + value.id, type(value).__name__) for value in data.body}
        actuals: dict[str, m.Declaration] = {}
        for binding in instance.bindings:
            budget.charge()
            port = data.inputs[binding.port]
            if type(binding.target) is m.Ref:
                reference = binding.target
                _require(not reference.id.startswith(prefixes), "Raw bindings cannot name instance-private or exported identities; use ModuleOutput")
                actual = base_map.get(reference.id)
                _require(actual is not None and reference.kind == type(actual).__name__, "Binding target is absent or has the wrong nominal kind")
            else:
                target = cast(ModuleOutput, binding.target)
                _require(target.instance in instance_map, "Output connection names an absent instance")
                expand(target.instance)
                provider = expanded_outputs[target.instance].get(target.port)
                _require(provider is not None, "Output connection names an undeclared port")
                output, actual = cast(tuple[OutputPort, m.Declaration], provider)
                _require(_CAPABILITIES[port.access] <= _CAPABILITIES[output.access], "Output interface does not authorize the requested input access")
                reference = m.Ref(actual.id, type(actual).__name__)
            mapping[port.declaration.id] = reference
            actuals[port.name] = cast(m.Declaration, actual)
        write_actuals: set[str] = set()
        input_ids = {port.declaration.id for port in data.inputs.values()}
        for reference in data.footprint.writes:
            if reference.id in input_ids:
                actual_id = mapping[reference.id].id
                _require(actual_id not in write_actuals, "Distinct module write inputs alias the same state")
                write_actuals.add(actual_id)
        for port in data.inputs.values():
            expected = cast(m.Declaration, _rewrite(port.declaration, mapping, budget, declaration=True))
            _require(_same(expected, actuals[port.name], budget), "Input signature differs in type, scope, units, lifecycle or contract: " + name + "/" + port.name)
        body = tuple(cast(m.Declaration, _rewrite(value, mapping, budget, declaration=True)) for value in data.body)
        budget.scan(body)
        by_id = {value.id: value for value in body}
        expanded[name] = body
        expanded_maps[name] = mapping
        expanded_outputs[name] = {port.name: (port, by_id[mapping[port.declaration.id].id]) for port in data.outputs.values()}
        visiting.remove(name)

    for name in instance_map:
        expand(name)
    combined = list(base)
    original_spans = _tuple(source_map, "source_map")
    _require(all(type(span) is m.SourceSpan for span in original_spans), "Context source map requires SourceSpan records")
    spans = [_snapshot(cast(m.SourceSpan, span), budget) for span in original_spans]
    _require(all(not span.declaration_id.startswith(prefixes) for span in spans), "Context source map cannot claim module-local declarations")
    definitions = {definition.id: definition for definition in base_semantics.definitions}
    _require(len(definitions) == len(base_semantics.definitions), "Duplicate base semantic definition")
    writers: dict[str, str] = {}
    for owner, body in [("<context>", base)] + [(name, expanded[name]) for name in instance_map]:
        footprint = _footprint(body, budget)
        for reference in footprint.writes:
            _require(reference.id not in writers or writers[reference.id] == owner,
                     "Conflicting shared writes across module ownership: " + reference.id)
            writers[reference.id] = owner
    for name, instance in instance_map.items():
        combined.extend(expanded[name])
        _require(len(combined) <= limits.max_declarations, "Expanded composition exceeds its declaration bound")
        for span in instance.template.source_map:
            spans.append(cast(m.SourceSpan, _rewrite(span, expanded_maps[name], budget)))
        for definition in validated[name].program.semantics.definitions:
            existing = definitions.get(definition.id)
            _require(existing is None or _same(existing, definition, budget), "Conflicting pinned semantic definitions")
            definitions[definition.id] = definition
    result = m.PolicyProgram(identity, replace(base_semantics, definitions=tuple(definitions.values())), tuple(combined), tuple(spans))
    budget.scan(result)
    _check_program(result)
    return result
