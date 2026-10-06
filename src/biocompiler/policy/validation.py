"""Closed structural checks for policy documents; no policy is executed here."""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Iterator, Literal

from . import model as m


@dataclass(frozen=True)
class Diagnostic:
    code: str
    category: str
    severity: Literal["error", "warning", "info"]
    declaration_id: str | None
    path: str
    source: m.SourceSpan | None
    related: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, object]:
        from .serialization import to_data
        return {"code": self.code, "category": self.category, "severity": self.severity,
                "declaration_id": self.declaration_id, "path": self.path,
                "source": to_data(self.source) if self.source is not None else None,
                "related": list(self.related), "message": self.message}


@dataclass(frozen=True)
class CheckReport:
    status: Literal["complete", "incomplete", "invalid"]
    diagnostics: tuple[Diagnostic, ...]
    assumptions: tuple[str, ...]
    required_features: tuple[str, ...]
    deferred_obligations: tuple[str, ...]
    semantic_status: Literal["unassessed"] = "unassessed"
    target_status: Literal["unassessed"] = "unassessed"

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "error")

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": "biocompiler.policy_check.v0.1", "status": self.status,
                "scope": "authoring_structure_only", "diagnostics": [x.to_dict() for x in self.diagnostics],
                "assumptions": list(self.assumptions), "required_features": list(self.required_features),
                "deferred_obligations": list(self.deferred_obligations),
                "semantic_status": self.semantic_status, "target_status": self.target_status}


def _walk(value: object, path: str = "", owner: str | None = None) -> Iterator[tuple[m.Record, str, str | None]]:
    stack = [(value, path, owner)]
    while stack:
        item, location, identity = stack.pop()
        if isinstance(item, m.Record):
            if hasattr(item, "id") and not isinstance(item, (m.Ref, m.DefinitionRef, m.Unit)):
                identity = str(getattr(item, "id"))
            yield item, location, identity
            stack.extend((getattr(item, field.name), location + "/" + field.name, identity)
                         for field in reversed(fields(item)))
        elif isinstance(item, tuple):
            stack.extend((element, location + "/" + str(index), identity)
                         for index, element in reversed(tuple(enumerate(item))))


def _compatible(left: m.TypeSpec, right: m.TypeSpec) -> bool:
    if left.kind != right.kind or left.entity_kind != right.entity_kind:
        return False
    if left.kind != "quantity":
        return left.unit is None and right.unit is None
    return (left.unit is not None and right.unit is not None
            and (left.unit.dimension, left.unit.quantity_kind, left.unit.reference)
            == (right.unit.dimension, right.unit.quantity_kind, right.unit.reference))


def _literal_type(value: object) -> m.TypeSpec | None:
    if type(value) is bool or value == "unknown":
        return m.TRUTH
    if type(value) is int:
        return m.INTEGER
    if type(value) is str:
        return m.TEXT
    if isinstance(value, m.Quantity):
        return m.TypeSpec("quantity", value.unit)
    return None


def _unscaled_count(unit: m.Unit) -> bool:
    if (unit.dimension, unit.quantity_kind, unit.reference) != ("count", "count", None):
        return False
    try:
        return Decimal(unit.scale) == 1
    except InvalidOperation:
        return False


def _subject_scopes(expression: m.Expr) -> set[m.Ref]:
    """Collect free subject scopes without turning quantified members into targets."""
    if expression.op in {"exists", "forall", "count", "call"}:
        return set()
    scopes = {expression.scope} if expression.scope is not None and expression.scope.kind == "Subject" else set()
    for argument in expression.args:
        scopes.update(_subject_scopes(argument))
    return scopes


def _mentions_binding(expression: m.Expr, binding: m.Ref) -> bool:
    if expression.op in {"exists", "forall", "count"} and expression.binding == binding:
        return False
    return (expression.scope == binding or expression.ref == binding
            or any(_mentions_binding(argument, binding) for argument in expression.args))


_DEFERRED = (
    "policy_execution_and_lowering", "temporal_and_uncertainty_semantics",
    "safety_and_progress_satisfaction", "realizability_and_target_suitability",
)
_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]*\Z")


class _Checker:
    def __init__(self, document: m.Document):
        self.document = document
        self.program = document.program if isinstance(document, m.BuildRequest) else document
        self.base = "/program" if isinstance(document, m.BuildRequest) else ""
        self.diagnostics: list[Diagnostic] = []
        self.index: dict[str, m.Declaration] = {}
        self.definitions: dict[str, m.SemanticDefinition] = {}
        self.digests: dict[str, str] = {}
        self.sources: dict[str, m.SourceSpan] = {}
        self.features: set[str] = {"profile:" + m.PROFILE}
        self.obligations = set(_DEFERRED)
        self.assumptions: set[str] = set()
        for source in self.program.source_map:
            self.sources.setdefault(source.declaration_id, source)

    def issue(self, code: str, message: str, path: str, owner: str | None = None,
              *, category: str = "structure", severity: Literal["error", "warning", "info"] = "error",
              related: tuple[str, ...] = ()) -> None:
        self.diagnostics.append(Diagnostic(code, category, severity, owner, path,
                                           self.sources.get(owner or ""), related, message))

    def require(self, condition: bool, code: str, message: str, path: str, owner: str | None = None,
                *, related: tuple[str, ...] = ()) -> None:
        if not condition:
            self.issue(code, message, path, owner, related=related)

    def ref(self, ref: m.Ref, kinds: tuple[type, ...], path: str, owner: str | None) -> m.Declaration | None:
        actual = self.lookup(ref, path)
        if actual is None:
            self.issue("missing_reference", "Reference does not resolve to a declaration.", path, owner, related=(ref.id,))
            return None
        if ref.kind != type(actual).__name__ or type(actual) not in kinds:
            self.issue("reference_kind", "Reference kind does not match the required declaration type.", path, owner, related=(ref.id,))
            return None
        return actual

    def lookup(self, ref: m.Ref, path: str) -> m.Declaration | None:
        # Formal parameters are lexical to a definition body. A program
        # declaration may legitimately share that definition's nominal ID.
        prefix = self.base + "/semantics/definitions/"
        if ref.kind == "Parameter" and path.startswith(prefix):
            index = path[len(prefix):].split("/", 1)[0]
            if index.isdecimal() and int(index) < len(self.program.semantics.definitions):
                for parameter in self.program.semantics.definitions[int(index)].parameters:
                    if parameter.id == ref.id:
                        return parameter
        return self.index.get(ref.id)

    def definition(self, ref: m.DefinitionRef, path: str, owner: str | None,
                   categories: tuple[str, ...] = ()) -> m.SemanticDefinition | None:
        actual = self.definitions.get(ref.id)
        if actual is None:
            self.issue("missing_definition", "Semantic definition body is absent from the pinned bundle.", path, owner, related=(ref.id,))
            return None
        self.require(ref.version == actual.version and ref.digest == self.digests[ref.id],
                     "definition_identity", "Definition version and document digest must match its complete body.", path, owner,
                     related=(ref.id,))
        if categories:
            self.require(actual.category in categories, "definition_category", "Definition has the wrong category for this use.", path, owner, related=(ref.id,))
        return actual

    def duration(self, value: m.Quantity | None, path: str, owner: str | None, *, required: bool = True,
                 positive: bool = True) -> None:
        if value is None:
            self.require(not required, "missing_duration", "An explicit duration is required.", path, owner)
            return
        self.require(value.unit.dimension == "time" and value.unit.quantity_kind == "duration", "duration_dimension", "Duration must have time dimension and duration quantity kind.", path, owner)
        self.require(Decimal(value.amount) > 0 if positive else Decimal(value.amount) >= 0,
                     "duration_bound", "Duration is outside its permitted positive/nonnegative bound.", path, owner)

    def scope(self, value: m.Scope, path: str, owner: str | None) -> None:
        self.features.add("scope:" + value.kind)
        if value.kind == "program":
            self.require(value.subject is None, "scope_subject", "Program scope has no subject reference.", path, owner)
            return
        self.require(value.subject is not None, "scope_subject", "This scope requires an explicit subject.", path, owner)
        if value.subject is None:
            return
        kind = (m.Role,) if value.kind == "executor" else (m.Encounter,) if value.kind == "encounter" else (m.Subject,)
        target = self.ref(value.subject, kind, path + "/subject", owner)
        self.require(not isinstance(target, m.Subject) or target.identity != "bound", "bound_subject_escape", "Bound subjects may only be used within their quantifier's expressions or observation templates.", path, owner)
        if isinstance(target, m.Subject) and value.kind in {"population", "lineage", "region"}:
            self.require(target.entity_kind == value.kind, "scope_entity", "Scope does not match its subject's nominal entity kind.", path, owner)

    def expression(self, expr: m.Expr, path: str, owner: str | None) -> None:
        op, args = expr.op, expr.args
        self.features.add("expression:" + op)
        if expr.value_type.kind == "truth":
            self.features.add("truth:three_valued")
        def check(condition: bool, code: str, message: str) -> None:
            self.require(condition, code, message, path, owner)
        def signature(count: int | None, inputs: str | None, output: str) -> None:
            check((count is None and bool(args)) or (count is not None and len(args) == count), "expression_arity", "Expression argument count does not match its operation.")
            check(inputs is None or all(arg.value_type.kind == inputs for arg in args), "expression_input_type", "Expression operands have the wrong type.")
            check(expr.value_type.kind == output, "expression_result_type", "Expression result type does not match its operation.")
        reference_ops = {"observe": (m.Observation,), "state": (m.StateStore,), "parameter": (m.Parameter,),
                         "updated": (m.Observation,), "effect_event": (m.Effect,), "message_event": (m.Message,)}
        if op in reference_ops:
            check(not args and expr.ref is not None, "expression_reference", "Reference expressions require a reference and no positional arguments.")
            if expr.ref is not None:
                target = self.ref(expr.ref, reference_ops[op], path + "/ref", owner)
                if isinstance(target, (m.Observation, m.StateStore, m.Parameter)) and op != "updated":
                    check(_compatible(expr.value_type, target.value_type), "reference_value_type", "Expression type differs from the referenced declaration.")
                elif target is not None:
                    check(expr.value_type == m.EVENT, "expression_result_type", "Observation/effect/message notifications are events.")
                expected_scope = target.subject if isinstance(target, (m.Observation, m.Effect, m.Message)) else target.scope.subject if isinstance(target, m.StateStore) else None
                check(expr.scope == expected_scope, "expression_scope", "Expression scope differs from its referenced declaration.")
        elif op == "literal":
            check(not args, "expression_arity", "Literals cannot contain positional arguments.")
            if expr.value_type.kind == "entity":
                check(expr.ref is not None and expr.value is None, "entity_literal", "Entity literals require a nominal reference, not a string value.")
                if expr.ref is not None:
                    target = self.ref(expr.ref, (m.Role, m.Subject, m.Encounter), path + "/ref", owner)
                    if isinstance(target, m.Subject):
                        check(expr.value_type.entity_kind == target.entity_kind, "entity_type", "Entity type differs from the referenced subject.")
                    check(expr.scope == expr.ref, "expression_scope", "Entity literal scope must be its nominal reference.")
            else:
                actual = _literal_type(expr.value)
                # The string 'unknown' may also be an ordinary text literal.
                if expr.value_type.kind == "text" and type(expr.value) is str:
                    actual = m.TEXT
                check(actual is not None and _compatible(expr.value_type, actual), "literal_type", "Literal value differs from its declared type.")
                check(expr.ref is None, "unexpected_expression_field", "Nonentity literals cannot carry references.")
        elif op in {"all", "any", "not"}:
            signature(1 if op == "not" else None, "truth", "truth")
        elif op in {"eq", "ne", "lt", "le", "gt", "ge"}:
            signature(2, None, "truth")
            if len(args) == 2:
                check(_compatible(args[0].value_type, args[1].value_type), "incompatible_operands", "Comparison operands must have compatible nominal types and units.")
                if op not in {"eq", "ne"}:
                    check(args[0].value_type.kind in {"quantity", "integer"}, "ordered_comparison", "Ordering is only declared for quantities and integers.")
        elif op in {"add", "subtract", "multiply", "divide"}:
            check(len(args) == 2, "expression_arity", "Arithmetic requires two operands.")
            check(all(arg.value_type.kind in {"quantity", "integer"} for arg in args), "expression_input_type", "Arithmetic operands must be numeric.")
            check(expr.value_type.kind in {"quantity", "integer"}, "expression_result_type", "Arithmetic result must have an explicit numeric type.")
            if len(args) == 2 and op in {"add", "subtract"}:
                check(_compatible(args[0].value_type, args[1].value_type) and _compatible(expr.value_type, args[0].value_type), "incompatible_operands", "Addition/subtraction requires compatible operand and result units.")
            elif op in {"multiply", "divide"}:
                self.obligations.add("derived_quantity_operation_semantics")
        elif op in {"exists", "forall", "count"}:
            signature(1, "truth", "integer" if op == "count" else "truth")
            check(expr.scope is not None, "quantifier_domain", "Quantification requires an explicit domain.")
            check(expr.binding is not None, "quantifier_binding", "Quantification requires an explicit bound subject.")
            if expr.scope is not None:
                target = self.ref(expr.scope, (m.Subject,), path + "/scope", owner)
                if isinstance(target, m.Subject):
                    check(target.entity_kind in {"population", "region"}, "quantifier_domain", "Quantifier domains must be populations or regions.")
            if expr.binding is not None:
                binding = self.ref(expr.binding, (m.Subject,), path + "/binding", owner)
                if isinstance(binding, m.Subject):
                    check(binding.identity == "bound" and binding.domain == expr.scope, "quantifier_binding", "Quantifier binding must be a bound subject in its declared domain.")
                check(len(args) == 1 and _mentions_binding(args[0], expr.binding), "unused_quantifier_binding", "Quantifier predicate must actually reference its own bound subject.")
            self.obligations.add("quantifier_membership_and_coverage")
        elif op == "distinct":
            signature(None, "entity", "truth")
            check(len(args) >= 2, "expression_arity", "Distinct requires at least two entity operands.")
        elif op in {"holds", "recently"}:
            signature(1, "truth", "truth")
        elif op in {"followed_by", "within", "after"}:
            signature(2, "event", "truth" if op == "within" else "event")
        elif op == "until":
            signature(2, "truth", "truth")
        elif op == "rising":
            signature(1, "truth", "event")
        elif op == "integrate":
            signature(1, "quantity", "quantity")
            check(expr.coverage == "sampled", "integration_coverage", "Integration must declare sampled coverage in this authoring profile.")
            self.obligations.add("integration_and_derived_unit_semantics")
        elif op == "call":
            check(expr.contract is not None, "operation_contract", "Calls require a complete pinned operation definition.")
            if expr.contract is not None:
                definition = self.definition(expr.contract, path + "/contract", owner, ("operation",))
                if definition is not None:
                    check(len(args) == len(definition.parameters), "call_arity", "Call arguments must cover its declared parameters.")
                    for arg, parameter in zip(args, definition.parameters):
                        check(_compatible(arg.value_type, parameter.value_type), "call_argument_type", "Call argument differs from its declared parameter type.")
                    check(definition.result is not None and _compatible(expr.value_type, definition.result), "call_result_type", "Call result differs from its declared signature.")
        temporal = {"holds", "recently", "followed_by", "within", "after", "until", "integrate"}
        if op in temporal:
            check(expr.clock is not None, "missing_clock", "Temporal expressions require an explicit clock.")
            if op in {"holds", "recently", "followed_by", "within", "integrate"}:
                self.duration(expr.duration, path + "/duration", owner)
            if op in {"holds", "recently", "followed_by", "integrate"}:
                check(expr.coverage is not None, "missing_coverage", "Temporal expressions require an explicit coverage policy.")
            if op in {"holds", "recently"}:
                check(expr.coverage in {"continuous", "sampled"}, "temporal_coverage", "Truth windows require continuous or sampled coverage.")
            elif op in {"followed_by", "within", "after"}:
                check(expr.coverage == "event", "temporal_coverage", "Event ordering requires event coverage.")
            elif op == "until":
                check(expr.coverage is None, "unexpected_expression_field", "Until does not declare a coverage field.")
            if op in {"after", "until"}:
                check(expr.duration is None, "unexpected_expression_field", "This temporal operation does not declare a duration.")
        else:
            check(expr.duration is None and expr.clock is None and expr.coverage is None, "unexpected_expression_field", "This operation does not declare temporal fields.")
        if expr.clock is not None:
            self.ref(expr.clock, (m.Clock,), path + "/clock", owner)
        if expr.coverage is not None:
            self.features.add("coverage:" + expr.coverage)
        check(expr.contract is None or op == "call", "unexpected_expression_field", "Only calls carry an operation contract.")
        check(expr.ref is None or op in reference_ops or op == "literal", "unexpected_expression_field", "This operation cannot carry a reference.")
        check(expr.value is None or op in {"literal", "effect_event", "message_event"}, "unexpected_expression_field", "This operation cannot carry a literal/event value.")
        check(expr.binding is None or op in {"exists", "forall", "count"}, "unexpected_expression_field", "Only quantifiers declare a bound subject.")
        check(expr.scope is None or op in reference_ops or op in {"exists", "forall", "count"} or (op == "literal" and expr.value_type.kind == "entity"), "unexpected_expression_field", "Scope is carried by referenced entities and explicit quantifier domains.")
        if op == "effect_event":
            check(expr.value in {"requested", "initiated", "completed", "outcome", "failed", "timed_out", "cancel_requested", "cancel_acknowledged", "ceased"}, "effect_event", "Unknown effect lifecycle event.")
        if op == "message_event":
            check(expr.value in {"sent", "received", "acknowledged", "expired"}, "message_event", "Unknown message event.")
        if op not in {"exists", "forall", "count", "distinct", "call"}:
            scopes = set().union(*(_subject_scopes(arg) for arg in args)) if args else set()
            check(len(scopes) <= 1, "mixed_subject_scope", "Operands on different subjects require an explicit quantifier or operation contract.")

    def bindings(self, expression: m.Expr, path: str, owner: str | None,
                 active: frozenset[m.Ref] = frozenset()) -> None:
        for ref in (expression.scope, expression.ref):
            target = self.index.get(ref.id) if ref is not None else None
            if isinstance(target, m.Subject) and target.identity == "bound":
                self.require(ref in active, "unbound_subject", "A bound subject cannot be used outside its quantifier's predicate.", path, owner, related=(target.id,))
        if expression.op in {"exists", "forall", "count"} and expression.binding is not None:
            self.require(expression.binding not in active, "quantifier_shadowing", "Nested quantifiers require distinct bound subject identities.", path, owner)
            active = active | {expression.binding}
            for argument in expression.args:
                self.require(_subject_scopes(argument) <= active, "quantifier_free_subject", "Quantifier predicate contains an unrelated free subject; use a declared relationship operation explicitly.", path, owner)
        for index, argument in enumerate(expression.args):
            self.bindings(argument, path + f"/args/{index}", owner, active)

    def scope_executor(self, scope: m.Scope) -> m.Ref | None:
        if scope.subject is None:
            return None
        target = self.index.get(scope.subject.id)
        if isinstance(target, m.Role):
            return scope.subject
        if isinstance(target, m.Encounter):
            return target.executor
        if isinstance(target, m.Subject):
            if target.executor is not None:
                return target.executor
            encounter = self.index.get(target.encounter.id) if target.encounter is not None else None
            if isinstance(encounter, m.Encounter):
                return encounter.executor
        return None

    def owned_state(self, state: m.StateStore, executor: m.Ref, path: str, owner: str) -> None:
        declared_owner = self.scope_executor(state.scope)
        self.require(declared_owner is None or declared_owner == executor, "executor_ownership", "State belongs to another executor's declared scope.", path, owner, related=(state.id,))
        if state.coordination is not None:
            channel = self.index.get(state.coordination.id)
            if isinstance(channel, m.Channel):
                self.require(executor == channel.sender or executor in channel.recipients, "executor_ownership", "Shared state access requires participation in its declared coordination channel.", path, owner, related=(state.id,))

    def owned(self, expression: m.Expr, executor: m.Ref, path: str, owner: str) -> None:
        for item, location, _ in _walk(expression, path, owner):
            if isinstance(item, m.Expr) and item.ref is not None:
                target = self.index.get(item.ref.id)
                if isinstance(target, m.Observation):
                    self.require(target.access == "cell", "observation_access", "Evaluator-only observations cannot drive cellular behavior.", location, owner, related=(target.id,))
                    self.require(target.observer == executor, "executor_ownership", "A rule must use its executor's observation interface.", location, owner, related=(target.id,))
                if isinstance(target, m.Effect):
                    self.require(target.executor == executor, "executor_ownership", "Effect feedback belongs to another executor.", location, owner, related=(target.id,))
                if isinstance(target, m.StateStore):
                    self.owned_state(target, executor, location, owner)
                if isinstance(target, m.Message):
                    channel = self.index.get(target.channel.id)
                    allowed = executor in channel.recipients if item.value == "received" and isinstance(channel, m.Channel) else executor == target.sender
                    self.require(allowed, "executor_ownership", "Message notifications require the declared sender or receiving interface for that phase.", location, owner, related=(target.id,))

    def behavior(self, item: m.Rule | m.Transition, path: str, executor: m.Ref) -> None:
        self.require(item.on.value_type == m.EVENT, "trigger_type", "The on field must be an event expression.", path + "/on", item.id)
        self.require(item.when.value_type == m.TRUTH, "guard_type", "The when field must be a truth expression.", path + "/when", item.id)
        self.owned(item.on, executor, path + "/on", item.id)
        self.owned(item.when, executor, path + "/when", item.id)
        if isinstance(item, m.Rule):
            self.require(item.unknown != "transition", "unknown_transition_context", "Unknown-to-state transitions require a machine transition.", path, item.id)
        self.require((item.unknown == "transition") == (item.unknown_target is not None), "unknown_target", "Only an unknown-transition policy carries a target state.", path, item.id)
        for index, ref in enumerate(item.effects):
            effect = self.ref(ref, (m.Effect,), path + f"/effects/{index}", item.id)
            if isinstance(effect, m.Effect):
                self.require(effect.executor == executor, "executor_ownership", "Effect belongs to another executor.", path + f"/effects/{index}", item.id, related=(effect.id,))
                evidence_subjects = _subject_scopes(item.on) | _subject_scopes(item.when)
                redirected = any(subject != effect.subject for subject in evidence_subjects)
                self.require(not redirected or effect.relationship is not None, "effect_relationship", "Redirecting subject-bound evidence to a different affected subject requires an explicit relationship contract.", path + f"/effects/{index}", item.id, related=(effect.id,))
        for index, assignment in enumerate(item.assignments):
            location = path + f"/assignments/{index}"
            target = self.ref(assignment.state, (m.StateStore,), location + "/state", item.id)
            self.owned(assignment.value, executor, location + "/value", item.id)
            if isinstance(target, m.StateStore):
                self.require(_compatible(target.value_type, assignment.value.value_type), "assignment_type", "Assignment differs from the state store's type.", location, item.id)
                self.owned_state(target, executor, location, item.id)
        for index, ref in enumerate(item.emissions):
            message = self.ref(ref, (m.Message,), path + f"/emissions/{index}", item.id)
            if isinstance(message, m.Message):
                self.require(message.sender == executor, "executor_ownership", "Message emission belongs to another executor.", path + f"/emissions/{index}", item.id, related=(message.id,))

    def declaration(self, item: m.Declaration, path: str) -> None:
        owner = item.id
        self.features.add("declaration:" + type(item).__name__)
        if isinstance(item, (m.Observation, m.Effect, m.Channel)) and item.spatial_scope is not None:
            self.ref(item.spatial_scope, (m.SpatialScope,), path + "/spatial_scope", owner)
        if isinstance(item, (m.Effect, m.Message, m.Encounter, m.SpatialScope, m.Role)):
            for name in ("subject", "target", "anchor", "population", "correlation"):
                reference = getattr(item, name, None)
                target = self.index.get(reference.id) if isinstance(reference, m.Ref) else None
                self.require(not isinstance(target, m.Subject) or target.identity != "bound", "bound_subject_escape", "Bound subjects cannot become unbound declaration targets or persistent identities.", path + "/" + name, owner)
        if isinstance(item, (m.StateStore, m.Machine)) and item.lifetime == "persistent":
            target = self.index.get(item.scope.subject.id) if item.scope.subject is not None else None
            if isinstance(target, m.Encounter) or isinstance(target, m.Subject) and target.identity == "encounter":
                self.issue("persistent_encounter_identity", "Persistence beyond an encounter requires an identity-lifetime interpretation; encounter identity alone does not establish stable cross-encounter memory.", path + "/scope", owner, category="semantics_deferred", severity="warning")
                self.obligations.add("persistent_encounter_identity_lifetime")
        if isinstance(item, m.Role):
            for index, ref in enumerate(item.requires):
                self.definition(ref, path + f"/requires/{index}", owner, ("capability", "interface"))
            if item.population is not None:
                target = self.ref(item.population, (m.Subject,), path + "/population", owner)
                self.require(not isinstance(target, m.Subject) or target.entity_kind == "population", "population_kind", "Role population must identify a population subject.", path, owner)
        elif isinstance(item, m.Subject):
            if item.executor is not None:
                self.ref(item.executor, (m.Role,), path + "/executor", owner)
            if item.encounter is not None:
                encounter = self.ref(item.encounter, (m.Encounter,), path + "/encounter", owner)
                if isinstance(encounter, m.Encounter):
                    self.require(encounter.target == m.Ref(item.id, "Subject") and (item.executor is None or item.executor == encounter.executor), "subject_encounter", "Encounter-local identity must name its encounter's target and executor.", path, owner)
            self.require((item.identity == "encounter") == (item.encounter is not None), "subject_encounter", "Encounter-local identity requires its encounter reference; other identities do not carry one.", path, owner)
            self.require((item.identity == "bound") == (item.domain is not None), "subject_domain", "Exactly bound subjects declare a quantifier domain.", path, owner)
            if item.domain is not None:
                domain = self.ref(item.domain, (m.Subject,), path + "/domain", owner)
                self.require(isinstance(domain, m.Subject) and domain.entity_kind in {"population", "region"} and domain.id != item.id, "subject_domain", "Bound subjects require a distinct population or region domain.", path, owner)
        elif isinstance(item, m.Encounter):
            self.ref(item.executor, (m.Role,), path + "/executor", owner)
            self.ref(item.target, (m.Subject,), path + "/target", owner)
            self.definition(item.contract, path + "/contract", owner, ("encounter",))
        elif isinstance(item, m.SpatialScope):
            self.ref(item.anchor, (m.Role, m.Subject, m.Encounter), path + "/anchor", owner)
            self.definition(item.contract, path + "/contract", owner, ("spatial",))
            if item.radius is not None:
                self.require(item.radius.unit.dimension == "length" and Decimal(item.radius.amount) >= 0, "spatial_radius", "Spatial radius must be a nonnegative length.", path, owner)
        elif isinstance(item, m.Clock):
            self.duration(item.resolution, path + "/resolution", owner)
        elif isinstance(item, m.Observation):
            self.ref(item.observer, (m.Role,), path + "/observer", owner)
            self.ref(item.subject, (m.Subject, m.Role), path + "/subject", owner)
            self.ref(item.clock, (m.Clock,), path + "/clock", owner)
            definition = self.definition(item.contract, path + "/contract", owner, ("observation",))
            if definition is not None:
                self.require(definition.result is not None and _compatible(definition.result, item.value_type), "observation_signature", "Observation contract result must match the observation type.", path, owner)
            self.duration(item.freshness, path + "/freshness", owner, positive=False)
            self.require(bool(item.coherence.strip()), "observation_coherence", "Observation requires an explicit coherent-frame identity.", path, owner)
            self.require(len(item.invalidity) == len(set(item.invalidity)), "duplicate_invalidity", "Invalidity reasons must be unique.", path, owner)
        elif isinstance(item, m.StateStore):
            actual = m.TEXT if item.value_type.kind == "text" and type(item.initial) is str else _literal_type(item.initial)
            self.require(actual is not None and _compatible(item.value_type, actual), "state_initial_type", "Initial state value differs from its declared type.", path, owner)
            if type(item.capacity) is int:
                self.require(item.capacity > 0, "state_capacity", "State capacity must be positive.", path, owner)
            elif isinstance(item.capacity, m.Ref):
                target = self.ref(item.capacity, (m.Parameter,), path + "/capacity", owner)
                if isinstance(target, m.Parameter):
                    self.require(target.value_type == m.INTEGER, "state_capacity", "Capacity parameters must be integers.", path, owner)
                    if target.selection == "fixed" and type(target.value) is int:
                        self.require(target.value > 0, "state_capacity", "A fixed capacity parameter must be positive.", path, owner)
            else:
                self.obligations.add("unbounded_state_capacity")
            self.require((item.lifetime == "duration") == (item.duration is not None), "state_lifetime", "Only duration-scoped state carries a duration.", path, owner)
            self.duration(item.duration, path + "/duration", owner, required=False)
            if item.reset is not None:
                self.require(item.reset.value_type == m.TRUTH, "state_reset_type", "Reset must be a truth expression.", path, owner)
                if item.scope.kind == "executor" and item.scope.subject is not None:
                    self.owned(item.reset, item.scope.subject, path + "/reset", owner)
            self.require(item.scope.kind != "population" or item.coordination is not None, "population_coordination", "Population state requires an explicit coordination channel.", path, owner)
            if item.coordination is not None:
                self.ref(item.coordination, (m.Channel,), path + "/coordination", owner)
            self.require(item.overflow != "contract" and item.inheritance != "contract" or item.contract is not None, "state_contract", "Contract-defined storage policies require their definition.", path, owner)
            self.obligations.add("state_lifetime_capacity_and_inheritance")
        elif isinstance(item, m.Effect):
            self.features.add("effects:lifecycle")
            self.ref(item.executor, (m.Role,), path + "/executor", owner)
            subject = self.ref(item.subject, (m.Subject, m.Role), path + "/subject", owner)
            definition = self.definition(item.contract, path + "/contract", owner, ("operation", "capability"))
            for index, resource in enumerate(item.resources):
                self.definition(resource, path + f"/resources/{index}", owner, ("resource",))
            if definition is not None:
                names = [argument.name for argument in item.parameters]
                self.require(len(names) == len(set(names)) and set(names) == {parameter.id for parameter in definition.parameters}, "effect_arguments", "Effect arguments must cover its definition parameters exactly once.", path, owner)
                declared = {parameter.id: parameter for parameter in definition.parameters}
                for arg in item.parameters:
                    if arg.name in declared:
                        self.require(_compatible(arg.value.value_type, declared[arg.name].value_type), "effect_argument_type", "Effect parameter differs from its contract signature.", path, owner)
                    self.owned(arg.value, item.executor, path + "/parameters", owner)
                if isinstance(subject, m.Subject) and definition.subject_kind is not None:
                    self.require(subject.entity_kind == definition.subject_kind, "effect_subject_type", "Effect subject kind differs from its contract.", path, owner)
            self.obligations.add("effect_authorization_feedback_and_cancellation")
        elif isinstance(item, m.Rule):
            self.ref(item.executor, (m.Role,), path + "/executor", owner)
            self.behavior(item, path, item.executor)
        elif isinstance(item, m.Machine):
            self.ref(item.executor, (m.Role,), path + "/executor", owner)
            declared_owner = self.scope_executor(item.scope)
            self.require(declared_owner is None or declared_owner == item.executor, "executor_ownership", "Machine executor differs from the owner of its declared scope.", path, owner)
            self.require(bool(item.states) and all(state.strip() for state in item.states) and len(item.states) == len(set(item.states)), "machine_states", "Machine states must be nonempty and unique.", path, owner)
            self.require(item.initial in item.states and set(item.terminal) <= set(item.states) and len(item.terminal) == len(set(item.terminal)), "machine_membership", "Initial and terminal states must belong to the machine.", path, owner)
            self.obligations.add("machine_reachability_termination_and_progress")
        elif isinstance(item, m.Transition):
            machine = self.ref(item.machine, (m.Machine,), path + "/machine", owner)
            if isinstance(machine, m.Machine):
                self.require(item.source in machine.states and item.destination in machine.states and (item.unknown_target is None or item.unknown_target in machine.states), "transition_membership", "Transition endpoints must belong to the referenced machine.", path, owner)
                self.behavior(item, path, machine.executor)
        elif isinstance(item, m.Channel):
            self.features.add("coordination:declared_transport")
            self.ref(item.sender, (m.Role,), path + "/sender", owner)
            self.require(bool(item.recipients) and len(item.recipients) == len(set(item.recipients)), "channel_recipients", "Channels require a nonempty unique recipient inventory.", path, owner)
            for index, recipient in enumerate(item.recipients):
                self.ref(recipient, (m.Role,), path + f"/recipients/{index}", owner)
            self.definition(item.contract, path + "/contract", owner, ("transport",))
            self.require((item.retry == "bounded") == (item.max_attempts is not None), "retry_bound", "Only bounded retry carries a maximum attempt count.", path, owner)
            self.require(item.max_attempts is None or item.max_attempts > 0, "retry_bound", "Maximum attempts must be positive.", path, owner)
            self.duration(item.latency, path + "/latency", owner, required=False, positive=False)
            self.obligations.add("delivery_ordering_loss_duplicates_and_retry")
        elif isinstance(item, m.Message):
            channel = self.ref(item.channel, (m.Channel,), path + "/channel", owner)
            self.ref(item.sender, (m.Role,), path + "/sender", owner)
            self.ref(item.subject, (m.Role, m.Subject), path + "/subject", owner)
            self.ref(item.correlation, (m.Role, m.Subject, m.Encounter, m.StateStore, m.Parameter), path + "/correlation", owner)
            if isinstance(channel, m.Channel):
                self.require(item.sender == channel.sender and _compatible(item.payload.value_type, channel.message_type), "message_signature", "Message sender and payload must match its channel.", path, owner)
            self.owned(item.payload, item.sender, path + "/payload", owner)
        elif isinstance(item, m.Requirement):
            if item.condition is not None:
                self.require(item.condition.value_type.kind in {"truth", "event"}, "requirement_condition", "Requirement conditions must be truth or event expressions.", path, owner)
            if item.trigger is not None:
                self.require(item.trigger.value_type == m.EVENT, "requirement_trigger", "Requirement triggers must be event expressions.", path + "/trigger", owner)
            if item.clock is not None:
                self.ref(item.clock, (m.Clock,), path + "/clock", owner)
            self.require(item.deadline is None or item.trigger is not None and item.clock is not None, "requirement_deadline_anchor", "A deadline requires an explicit trigger and clock.", path, owner)
            if item.kind == "progress":
                self.require(item.condition is not None or item.trigger is not None or item.contract is not None, "progress_enabling", "Progress requires a declared enabling condition, event trigger or interpretation contract.", path, owner)
                self.require(item.response is not None, "progress_response", "Progress must retain the response it requires.", path, owner)
            self.duration(item.deadline, path + "/deadline", owner, required=False)
            if isinstance(item.horizon, m.Quantity):
                self.duration(item.horizon, path + "/horizon", owner)
            if item.horizon == "unbounded_requested":
                self.obligations.add("unbounded_requirement_horizon")
            if item.kind == "assumption":
                self.assumptions.add(item.description)

    def run(self) -> CheckReport:
        from .serialization import document_digest
        self.require(self.program.profile == m.PROFILE and self.program.semantics.profile == m.PROFILE,
                     "unsupported_profile", "Policy and semantics must select the supported authoring profile.", self.base + "/profile")
        for index, definition in enumerate(self.program.semantics.definitions):
            location = self.base + f"/semantics/definitions/{index}"
            self.require(definition.id not in self.definitions, "duplicate_definition", "Definition IDs must be unique in a bundle.", location, definition.id)
            self.definitions.setdefault(definition.id, definition)
            self.digests.setdefault(definition.id, document_digest(definition))
            names = [parameter.id for parameter in definition.parameters]
            self.require(len(names) == len(set(names)), "duplicate_parameter", "Definition parameters must have unique names.", location, definition.id)
        for index, declaration in enumerate(self.program.declarations):
            self.require(declaration.id not in self.index, "duplicate_declaration", "Declaration IDs must be unique.", self.base + f"/declarations/{index}", declaration.id)
            self.require(_IDENTIFIER.fullmatch(declaration.id) is not None, "invalid_identifier", "Declaration IDs must be ASCII namespaced identifiers.", self.base + f"/declarations/{index}/id", declaration.id)
            self.index.setdefault(declaration.id, declaration)
        for item, path, owner in _walk(self.document):
            if isinstance(item, (m.PolicyDraft, m.PolicyProgram, m.SemanticDefinition, m.Parameter, m.Hole)):
                self.require(_IDENTIFIER.fullmatch(item.id) is not None, "invalid_identifier", "Program, definition and parameter IDs must be ASCII namespaced identifiers.", path + "/id", owner)
            for field in fields(item):
                value = getattr(item, field.name)
                if field.name in {"id", "name", "version", "description", "meaning", "question", "expected"} and isinstance(value, str):
                    self.require(bool(value.strip()), "empty_name", "Required names and descriptions cannot be blank.", path + "/" + field.name, owner)
            if hasattr(item, "assumptions"):
                self.assumptions.update(getattr(item, "assumptions"))
            if isinstance(item, m.Ref):
                resolved = self.lookup(item, path)
                self.require(resolved is not None and item.kind == type(resolved).__name__, "reference_identity", "Reference must resolve with its exact declaration kind.", path, owner, related=(item.id,))
            elif isinstance(item, m.DefinitionRef):
                self.definition(item, path, owner)
            elif isinstance(item, m.TypeSpec):
                self.require((item.kind == "quantity") == (item.unit is not None), "type_unit", "Exactly quantity types carry a unit.", path, owner)
                self.require((item.kind == "entity") == (item.entity_kind is not None), "type_entity", "Exactly entity types carry a nominal entity kind.", path, owner)
            elif isinstance(item, m.Unit):
                try:
                    scale = Decimal(item.scale)
                    valid = scale.is_finite() and scale > 0 and len(scale.as_tuple().digits) <= 256 and abs(scale.adjusted()) <= 1024
                except InvalidOperation:
                    valid = False
                self.require(valid, "unit_scale", "Unit scale must be a bounded positive finite decimal.", path, owner)
                self.require(bool(item.dimension.strip()) and bool(item.quantity_kind.strip()), "unit_dimension", "Units require an explicit dimension and quantity kind.", path, owner)
            elif isinstance(item, m.Expr):
                self.expression(item, path, owner)
                if "/args/" not in path:
                    self.bindings(item, path, owner)
            elif isinstance(item, m.Scope):
                self.scope(item, path, owner)
            elif isinstance(item, m.Parameter):
                if item.value is not None:
                    actual = m.TEXT if item.value_type.kind == "text" and type(item.value) is str else _literal_type(item.value)
                    self.require(actual is not None and _compatible(item.value_type, actual), "parameter_type", "Parameter value differs from its declared type.", path, owner)
                formal = path.startswith(self.base + "/semantics/definitions/") and "/parameters/" in path
                self.require(formal or item.selection != "fixed" or item.value is not None, "fixed_parameter_value", "Fixed parameters require a value.", path, owner)
                for name, bound in (("lower", item.lower), ("upper", item.upper)):
                    if bound is not None:
                        integer_count = item.value_type == m.INTEGER and _unscaled_count(bound.unit)
                        valid_type = _compatible(item.value_type, m.TypeSpec("quantity", bound.unit)) or integer_count
                        self.require(valid_type, "parameter_bound_type", "Parameter bounds require compatible quantity units or unscaled count units for integers.", path + "/" + name, owner)
                        amount: Fraction | None = None
                        if isinstance(item.value, m.Quantity) and valid_type:
                            amount = Fraction(item.value.amount) * Fraction(item.value.unit.scale)
                        elif type(item.value) is int and integer_count:
                            amount = Fraction(item.value)
                        if amount is not None:
                            bound_amount = Fraction(bound.amount) * Fraction(bound.unit.scale)
                            self.require(amount >= bound_amount if name == "lower" else amount <= bound_amount, "parameter_bound_value", "Declared parameter value lies outside its literal bound.", path + "/" + name, owner)
            elif isinstance(item, m.EffectLifecycle):
                self.definition(item.contract, path + "/contract", owner, ("lifecycle",))
                self.duration(item.timeout, path + "/timeout", owner, required=False)
                self.require(item.on_loss != "request_cancel" and item.on_unknown != "request_cancel" or item.cancellation != "unsupported", "cancellation_contract", "Requested cancellation cannot use an unsupported cancellation lifecycle.", path, owner)
            elif isinstance(item, m.Arbitration):
                self.require(len(item.order) == len(set(item.order)), "arbitration_order", "Declared order cannot repeat participants.", path, owner)
                self.require(item.tie != "declared_order" and item.mode != "priority" or bool(item.order), "arbitration_order", "Priority and declared-order ties require an explicit participant order.", path, owner)
                self.require(item.write_conflict != "contract" and item.preemption != "contract" or item.contract is not None, "arbitration_contract", "Contract-defined arbitration needs its definition.", path, owner)
                self.obligations.add("arbitration_fairness_and_conflict_resolution")
            elif isinstance(item, m.SourceSpan):
                self.require(item.declaration_id in self.index and item.line > 0 and item.column >= 0, "source_map", "Source spans need a known declaration and positive line/nonnegative column.", path, item.declaration_id)
            elif isinstance(item, m.Hole):
                self.issue("design_hole", item.question, path, item.id, category="authoring_incomplete", severity="warning")
            if hasattr(item, "lower") and hasattr(item, "upper"):
                lower, upper = getattr(item, "lower"), getattr(item, "upper")
                if lower is not None and upper is not None:
                    self.require(_compatible(m.TypeSpec("quantity", lower.unit), m.TypeSpec("quantity", upper.unit)), "bound_units", "Bounds must have compatible units.", path, owner)
                    # Literal interval ordering uses exact supplied multiplicative
                    # scales; it does not evaluate policy expressions or goals.
                    if _compatible(m.TypeSpec("quantity", lower.unit), m.TypeSpec("quantity", upper.unit)):
                        self.require(Fraction(lower.amount) * Fraction(lower.unit.scale) <= Fraction(upper.amount) * Fraction(upper.unit.scale), "bound_order", "Literal lower bound exceeds the upper bound.", path, owner)
        for index, declaration in enumerate(self.program.declarations):
            self.declaration(declaration, self.base + f"/declarations/{index}")
        self.conflicts()
        if isinstance(self.document, m.BuildRequest):
            self.request()
        invalid = any(item.severity == "error" for item in self.diagnostics)
        incomplete = isinstance(self.program, m.PolicyDraft) and bool(self.program.holes)
        return CheckReport("invalid" if invalid else "incomplete" if incomplete else "complete",
                           tuple(self.diagnostics), tuple(sorted(self.assumptions)), tuple(sorted(self.features)),
                           tuple(sorted(self.obligations)))

    def conflicts(self) -> None:
        # No guard satisfiability or ordering is inferred. Multiple declared
        # writers require an explicit policy even if their guards look disjoint.
        writers: dict[str, list[m.Rule | m.Transition]] = {}
        policies: dict[str, m.Arbitration | None] = {}
        executors: dict[str, m.Ref] = {}
        for item in self.program.declarations:
            if isinstance(item, m.Rule):
                policies[item.id] = item.arbitration
                executors[item.id] = item.executor
            elif isinstance(item, m.Transition):
                machine = self.index.get(item.machine.id)
                if isinstance(machine, m.Machine):
                    policies[item.id] = machine.arbitration
                    executors[item.id] = machine.executor
            if isinstance(item, (m.Rule, m.Transition)) and item.id in policies:
                for key in {"state:" + assignment.state.id for assignment in item.assignments} | {"effect:" + ref.id for ref in item.effects}:
                    writers.setdefault(key, []).append(item)
        for key, participants in sorted(writers.items()):
            if len(participants) > 1:
                self.require(all(policies[item.id] is not None for item in participants), "missing_arbitration", "Multiple declared writers/requesters require explicit arbitration; guards are not solved.", self.base + "/declarations", participants[0].id, related=tuple(item.id for item in participants[1:]))
                shared = [policies[item.id] for item in participants if policies[item.id] is not None]
                self.require(not shared or all(policy == shared[0] for policy in shared), "inconsistent_arbitration", "Participants sharing an output must declare the same arbitration policy.", self.base + "/declarations", participants[0].id)
                for policy in shared:
                    if policy is not None and (policy.mode == "priority" or policy.tie == "declared_order"):
                        self.require({item.id for item in participants} <= set(policy.order), "arbitration_order_coverage", "Explicit ordering must include every participant sharing an output.", self.base + "/declarations", participants[0].id)
        for item in self.program.declarations:
            if isinstance(item, (m.Rule, m.Machine)) and item.arbitration is not None:
                participant_ids = {identity for identity, executor in executors.items() if executor == item.executor}
                self.require(set(item.arbitration.order) <= participant_ids, "arbitration_participant", "Arbitration order refers to participants outside its executor.", self.base + "/declarations", item.id)
                required = {other.id for other in self.program.declarations if isinstance(other, m.Transition) and other.machine.id == item.id} if isinstance(item, m.Machine) else {item.id}
                if item.arbitration.mode == "priority" or item.arbitration.tie == "declared_order":
                    self.require(required <= set(item.arbitration.order), "arbitration_order_coverage", "Explicit ordering must cover the rule or every machine transition it governs.", self.base + "/declarations", item.id)

    def request(self) -> None:
        request = self.document
        assert isinstance(request, m.BuildRequest)
        self.require(request.profile == m.PROFILE, "unsupported_profile", "Unsupported authoring request profile.", "/profile")
        roles = {item.id for item in self.program.declarations if isinstance(item, m.Role)}
        supplied = [binding.role.id for binding in request.deployment.bindings]
        self.require(set(supplied) == roles and len(supplied) == len(set(supplied)), "deployment_role_coverage", "Deployment must bind every role exactly once.", "/deployment/bindings")
        for index, binding in enumerate(request.deployment.bindings):
            self.ref(binding.role, (m.Role,), f"/deployment/bindings/{index}/role", None)
        for index, ref in enumerate(request.deployment.delivery.intended_recipients):
            self.ref(ref, (m.Role, m.Subject), f"/deployment/delivery/intended_recipients/{index}", None)
        self.require(bool(request.deployment.delivery.intended_recipients), "delivery_recipients", "Delivery requires intended recipients.", "/deployment/delivery")
        for field in fields(request.deployment.payload):
            value = getattr(request.deployment.payload, field.name)
            if field.name.endswith("_count") and value is not None:
                self.require(value >= 0, "payload_count", "Declared payload counts cannot be negative.", "/deployment/payload/" + field.name)
        ids = [item.id for item in request.implementations.implementations]
        self.require(len(ids) == len(set(ids)), "implementation_identity", "Implementation lock entries must have unique IDs.", "/implementations")
        requirements = {item.id for item in self.program.declarations if isinstance(item, m.Requirement)}
        self.require(set(request.assurance.requirements) <= requirements and len(set(request.assurance.requirements)) == len(request.assurance.requirements), "assurance_requirements", "Assurance must reference unique declared requirements.", "/assurance/requirements")
        if isinstance(request.assurance.horizon, m.Quantity):
            self.duration(request.assurance.horizon, "/assurance/horizon", None)
        self.features.add("request:deployment_catalog_assurance")
        self.obligations.update(("chassis_capability_and_delivery_suitability", "implementation_catalog_applicability", "requested_assurance_not_established"))


def check(document: object) -> CheckReport:
    """Check representation and declared interfaces without evaluating behavior."""
    from .serialization import from_data, to_data
    if not isinstance(document, (m.PolicyDraft, m.PolicyProgram, m.BuildRequest)) or type(document) not in (m.PolicyDraft, m.PolicyProgram, m.BuildRequest):
        error = Diagnostic("document_type", "structure", "error", None, "", None, (),
                           "Expected a policy draft, program or build request.")
        return CheckReport("invalid", (error,), (), (), _DEFERRED)
    try:
        # Constructor calls alone do not enforce annotations. Reuse the closed,
        # bounded decoder to catch forged field types and unsupported enum values.
        decoded = from_data(to_data(document), type(document))
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        error = Diagnostic("document_shape", "structure", "error", None, "", None, (), str(exc))
        return CheckReport("invalid", (error,), (), (), _DEFERRED)
    return _Checker(decoded).run()
