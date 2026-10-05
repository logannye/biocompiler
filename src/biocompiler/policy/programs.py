"""Typed Python construction of immutable policy documents."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import fields, replace
import inspect
import re
from typing import Iterator, Literal, TypeVar

from . import model as m
from .logic import TRUE

D = TypeVar("D", bound=m.Record)
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]*\Z")


def ref(value: m.Record | m.Ref) -> m.Ref:
    if isinstance(value, m.Ref):
        return value
    return m.declaration_ref(value)


class AuthoringError(ValueError):
    """A structural authoring error; never a compiler rejection."""


class ProgramBuilder:
    def __init__(self, name: str, *, semantics: m.SemanticBundle) -> None:
        if not _ID.fullmatch(name):
            raise ValueError("Program name must be an ASCII namespaced identifier")
        self.name = name
        self.semantics = semantics
        self._declarations: list[m.Declaration] = []
        self._ids: set[str] = set()
        self._holes: list[m.Hole] = []
        self._source_map: list[m.SourceSpan] = []
        self._namespace: list[str] = []
        self._owner = object()

    def qualified(self, identity: str) -> str:
        result = "/".join((*self._namespace, identity))
        if not _ID.fullmatch(result):
            raise ValueError("Declaration identity must be an ASCII namespaced identifier")
        return result

    @contextmanager
    def namespace(self, name: str) -> Iterator[ProgramBuilder]:
        self.qualified(name)
        self._namespace.append(name)
        try:
            yield self
        finally:
            self._namespace.pop()

    def add(self, declaration: D) -> D:
        allowed = (m.Role, m.Subject, m.Encounter, m.SpatialScope, m.Clock, m.Observation, m.StateStore, m.Effect, m.Rule, m.Machine, m.Transition, m.Channel, m.Message, m.Requirement, m.Parameter)
        if not isinstance(declaration, allowed):
            raise TypeError("Expected a policy declaration, not an arbitrary record")
        pending: list[object] = [declaration]
        while pending:
            node = pending.pop()
            if isinstance(node, m.Record):
                owner = getattr(node, "_policy_owner", self._owner)
                if owner is not self._owner:
                    raise AuthoringError("Cross-program declaration/reference: import declarative data explicitly or bind a local declaration")
                pending.extend(getattr(node, field.name) for field in fields(node))
            elif isinstance(node, tuple):
                pending.extend(node)
        identity = declaration.id
        if not _ID.fullmatch(identity) or identity in self._ids:
            raise AuthoringError(f"Invalid or duplicate declaration identity: {identity}")
        self._ids.add(identity)
        object.__setattr__(declaration, "_policy_owner", self._owner)
        self._declarations.append(declaration)
        frame = inspect.currentframe()
        try:
            caller = frame.f_back if frame else None
            while caller is not None and caller.f_globals.get("__name__", "").startswith("biocompiler.policy"):
                caller = caller.f_back
            if caller:
                self._source_map.append(m.SourceSpan(identity, caller.f_code.co_filename, caller.f_lineno, pattern="/".join(self._namespace) or None))
        finally:
            del frame
        return declaration

    def hole(self, identity: str, *, expected: str, question: str) -> m.Hole:
        slot = m.Hole(self.qualified(identity), expected, question)
        if slot.id in self._ids or any(x.id == slot.id for x in self._holes):
            raise AuthoringError(f"Duplicate identity: {slot.id}")
        self._holes.append(slot)
        return slot

    def resolve(self, identity: str, declaration: m.Declaration) -> None:
        if not any(x.id == identity for x in self._holes):
            raise KeyError(identity)
        self.add(declaration)
        self._holes = [x for x in self._holes if x.id != identity]

    def executor(self, identity: str, *, requires: tuple[m.DefinitionRef, ...], population: m.Ref | None = None, lineage_role: bool = False) -> m.Role:
        return self.add(m.Role(self.qualified(identity), requires, population, lineage_role))

    def subject(self, identity: str, *, entity_kind: Literal["cell", "population", "region", "compartment", "lineage"], identity_scope: Literal["encounter", "stable", "aggregate", "bound"], executor: m.Record | m.Ref | None = None, domain: m.Record | m.Ref | None = None) -> m.Subject:
        return self.add(m.Subject(self.qualified(identity), entity_kind, identity_scope, ref(executor) if executor is not None else None, domain=ref(domain) if domain is not None else None))

    def encounter(self, identity: str, *, executor: m.Record | m.Ref, contract: m.DefinitionRef, termination: Literal["contact_loss", "explicit_event", "contract"] = "contact_loss") -> m.Encounter:
        name = self.qualified(identity)
        target = self.add(m.Subject(name + "/target", "cell", "encounter", ref(executor), m.Ref(name, "Encounter")))
        return self.add(m.Encounter(name, ref(executor), ref(target), contract, termination))

    def clock(self, identity: str, *, basis: Literal["availability", "observation", "logical"], resolution: m.Quantity) -> m.Clock:
        return self.add(m.Clock(self.qualified(identity), basis, resolution))

    def observe(self, identity: str, *, observer: m.Record | m.Ref, subject: m.Record | m.Ref, value_type: m.TypeSpec, contract: m.DefinitionRef, clock: m.Record | m.Ref, access: Literal["cell", "external_evaluator"], coverage: Literal["continuous", "sampled", "event"], coherence: str, freshness: m.Quantity, spatial_scope: m.Ref | None = None) -> m.Observation:
        return self.add(m.Observation(self.qualified(identity), ref(observer), ref(subject), value_type, contract, ref(clock), access, coverage, coherence, freshness, spatial_scope))

    def state(self, declaration: m.StateStore) -> m.StateStore:
        return self.add(replace(declaration, id=self.qualified(declaration.id)))

    def effect(self, identity: str, *, contract: m.DefinitionRef, executor: m.Record | m.Ref, subject: m.Record | m.Ref, lifecycle: m.EffectLifecycle, parameters: tuple[m.Argument, ...] = (), spatial_scope: m.Ref | None = None, relationship: m.DefinitionRef | None = None, resources: tuple[m.DefinitionRef, ...] = ()) -> m.Effect:
        return self.add(m.Effect(self.qualified(identity), contract, ref(executor), ref(subject), lifecycle, parameters, spatial_scope, relationship, resources))

    def rule(self, identity: str, *, executor: m.Record | m.Ref, on: m.Expr, when: m.Expr, unknown: Literal["defer", "transition", "request_stop"], effects: tuple[m.Ref, ...], arbitration: m.Arbitration, assignments: tuple[m.Assignment, ...] = (), unknown_target: str | None = None, emissions: tuple[m.Ref, ...] = ()) -> m.Rule:
        return self.add(m.Rule(self.qualified(identity), ref(executor), on, when, unknown, effects, assignments, arbitration, unknown_target, emissions))

    def machine(self, identity: str, *, executor: m.Record | m.Ref, scope: m.Scope, states: tuple[str, ...], initial: str, terminal: tuple[str, ...], lifetime: Literal["encounter", "executor", "persistent"], arbitration: m.Arbitration) -> m.Machine:
        return self.add(m.Machine(self.qualified(identity), ref(executor), scope, states, initial, terminal, lifetime, arbitration))

    def transition(self, identity: str, *, machine: m.Record | m.Ref, source: str, destination: str, on: m.Expr, when: m.Expr = TRUE, unknown: Literal["defer", "transition", "request_stop"] = "defer", effects: tuple[m.Ref, ...] = (), assignments: tuple[m.Assignment, ...] = (), unknown_target: str | None = None, emissions: tuple[m.Ref, ...] = ()) -> m.Transition:
        return self.add(m.Transition(self.qualified(identity), ref(machine), source, destination, on, when, unknown, effects, assignments, unknown_target, emissions))

    def channel(self, declaration: m.Channel) -> m.Channel:
        return self.add(replace(declaration, id=self.qualified(declaration.id)))

    def require(self, declaration: m.Requirement) -> m.Requirement:
        return self.add(replace(declaration, id=self.qualified(declaration.id)))

    def snapshot(self) -> m.PolicyDraft:
        return m.PolicyDraft(self.name, self.semantics, tuple(self._declarations), tuple(self._holes), tuple(self._source_map))

    def freeze(self) -> m.PolicyProgram:
        from .validation import check
        draft = self.snapshot()
        report = check(draft)
        if report.status != "complete":
            details = "; ".join(f"[{item.code}] {item.message}" for item in report.diagnostics
                                if item.severity == "error" or item.category == "authoring_incomplete")
            raise AuthoringError(f"Cannot freeze {report.status} policy: {details}")
        return m.PolicyProgram(self.name, self.semantics, draft.declarations, draft.source_map)
