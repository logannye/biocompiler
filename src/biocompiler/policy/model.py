"""Portable authoring declarations, not executable biological semantics.

All persisted objects belong to this closed registry. Python constructs these
records; a future compatible core must independently validate their meaning.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from typing import Literal, TypeAlias

PROFILE = "biocompiler.policy.v0.1"
REGISTRY: dict[str, type[Record]] = {}


@dataclass(frozen=True)
class Record:
    """Base for immutable, data-only declarations."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__()
        if cls.__module__ not in ("biocompiler.policy.model", "biocompiler.policy.handoff"):
            raise TypeError("Policy wire records form a closed registry; use SemanticDefinition for extensions")
        REGISTRY[cls.__name__] = cls

    def __post_init__(self) -> None:
        # Copy caller-owned sequences, including nested sequences. No opaque
        # Python object, callback, mapping or float is a declaration value.
        def freeze(value: object) -> object:
            if isinstance(value, (list, tuple)):
                return tuple(freeze(item) for item in value)
            if value is None or type(value) in (str, int, bool) or isinstance(value, Record):
                return value
            raise TypeError(f"Non-declarative value: {type(value).__name__}")
        for field in fields(self):
            object.__setattr__(self, field.name, freeze(getattr(self, field.name)))

    def _repr_html_(self) -> str:
        from .inspection import render_html
        return render_html(self)


@dataclass(frozen=True)
class SourceSpan(Record):
    declaration_id: str
    file: str
    line: int
    column: int = 0
    pattern: str | None = None


@dataclass(frozen=True)
class Hole(Record):
    id: str
    expected: str
    question: str


@dataclass(frozen=True)
class Ref(Record):
    id: str
    kind: str


def declaration_ref(value: Record) -> Ref:
    """Retain in-process builder ownership without putting it on the wire."""
    identity = getattr(value, "id", None)
    if not isinstance(identity, str):
        raise TypeError("Only named declarations have references")
    result = Ref(identity, type(value).__name__)
    owner = getattr(value, "_policy_owner", None)
    if owner is not None:
        object.__setattr__(result, "_policy_owner", owner)
    return result


@dataclass(frozen=True)
class Unit(Record):
    id: str
    dimension: str
    quantity_kind: str
    scale: str = "1"
    reference: str | None = None


@dataclass(frozen=True)
class Quantity(Record):
    amount: str
    unit: Unit

    def __post_init__(self) -> None:
        if isinstance(self.amount, (bool, float)):
            raise TypeError("Use an exact decimal string or integer, not a float/bool")
        try:
            value = Decimal(self.amount)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Invalid decimal quantity") from exc
        if not value.is_finite() or len(value.as_tuple().digits) > 256 or abs(value.adjusted()) > 1024:
            raise ValueError("Quantity must be finite and within decimal representation limits")
        # Fixed representation, no dependence on the process Decimal context.
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        if len(text) > 256:
            raise ValueError("Canonical decimal spelling exceeds 256 characters")
        object.__setattr__(self, "amount", "0" if value == 0 else text)
        super().__post_init__()


@dataclass(frozen=True)
class TypeSpec(Record):
    kind: Literal["truth", "event", "quantity", "integer", "text", "entity"]
    unit: Unit | None = None
    entity_kind: str | None = None


TRUTH = TypeSpec("truth")
EVENT = TypeSpec("event")
INTEGER = TypeSpec("integer")
TEXT = TypeSpec("text")


@dataclass(frozen=True)
class DefinitionRef(Record):
    id: str
    version: str
    digest: str


@dataclass(frozen=True)
class Expr(Record):
    op: Literal["literal", "observe", "state", "parameter", "all", "any", "not", "eq", "ne", "lt", "le", "gt", "ge", "add", "subtract", "multiply", "divide", "exists", "forall", "count", "distinct", "holds", "recently", "followed_by", "within", "after", "until", "rising", "updated", "effect_event", "message_event", "call", "integrate"]
    value_type: TypeSpec
    args: tuple[Expr, ...] = ()
    ref: Ref | None = None
    value: str | int | bool | Quantity | None = None
    scope: Ref | None = None
    contract: DefinitionRef | None = None
    duration: Quantity | None = None
    clock: Ref | None = None
    coverage: Literal["continuous", "sampled", "event"] | None = None
    binding: Ref | None = None

    def __bool__(self) -> bool:
        raise TypeError("A policy expression is symbolic; use a policy rule and all_of/any_of/not_ instead of Python if/and/or/not")

    def __and__(self, other: Expr) -> Expr:
        from .logic import all_of
        return all_of(self, other)

    def __or__(self, other: Expr) -> Expr:
        from .logic import any_of
        return any_of(self, other)

    def __invert__(self) -> Expr:
        from .logic import not_
        return not_(self)

    def compare(self, operator: Literal["eq", "ne", "lt", "le", "gt", "ge"], other: Expr | Quantity | int | str | bool) -> Expr:
        from .logic import literal
        return Expr(operator, TRUTH, (self, other if isinstance(other, Expr) else literal(other)))


@dataclass(frozen=True)
class Parameter(Record):
    id: str
    value_type: TypeSpec
    value: str | int | bool | Quantity | None = None
    lower: Quantity | None = None
    upper: Quantity | None = None
    selection: Literal["fixed", "design", "measured", "uncertain"] = "fixed"


@dataclass(frozen=True)
class ContractClause(Record):
    kind: Literal["precondition", "postcondition", "transition", "event", "assumption", "progress", "resource"]
    description: str
    expression: Expr | None = None


@dataclass(frozen=True)
class SemanticDefinition(Record):
    id: str
    version: str
    category: Literal["operation", "capability", "encounter", "observation", "lifecycle", "environment", "delivery", "requirement", "inheritance", "resource", "interface", "spatial", "transport", "model"]
    meaning: str
    parameters: tuple[Parameter, ...] = ()
    result: TypeSpec | None = None
    clauses: tuple[ContractClause, ...] = ()
    assumptions: tuple[str, ...] = ()
    executor_kind: str | None = None
    subject_kind: str | None = None

    @property
    def ref(self) -> DefinitionRef:
        from .serialization import document_digest
        return DefinitionRef(self.id, self.version, document_digest(self))


@dataclass(frozen=True)
class SemanticBundle(Record):
    id: str
    version: str
    definitions: tuple[SemanticDefinition, ...] = ()
    profile: str = PROFILE


@dataclass(frozen=True)
class Scope(Record):
    kind: Literal["executor", "encounter", "target", "population", "lineage", "region", "program"]
    subject: Ref | None = None


@dataclass(frozen=True)
class Role(Record):
    id: str
    requires: tuple[DefinitionRef, ...]
    population: Ref | None = None
    lineage_role: bool = False


@dataclass(frozen=True)
class Subject(Record):
    id: str
    entity_kind: Literal["cell", "population", "region", "compartment", "lineage"]
    identity: Literal["encounter", "stable", "aggregate", "bound"]
    executor: Ref | None = None
    encounter: Ref | None = None
    domain: Ref | None = None


@dataclass(frozen=True)
class Encounter(Record):
    id: str
    executor: Ref
    target: Ref
    contract: DefinitionRef
    termination: Literal["contact_loss", "explicit_event", "contract"]


@dataclass(frozen=True)
class SpatialScope(Record):
    id: str
    kind: Literal["contact", "neighborhood", "compartment", "region"]
    anchor: Ref
    contract: DefinitionRef
    radius: Quantity | None = None


@dataclass(frozen=True)
class Clock(Record):
    id: str
    basis: Literal["availability", "observation", "logical"]
    resolution: Quantity
    simultaneous: Literal["atomic_batch"] = "atomic_batch"


@dataclass(frozen=True)
class Observation(Record):
    id: str
    observer: Ref
    subject: Ref
    value_type: TypeSpec
    contract: DefinitionRef
    clock: Ref
    access: Literal["cell", "external_evaluator"]
    coverage: Literal["continuous", "sampled", "event"]
    coherence: str
    freshness: Quantity
    spatial_scope: Ref | None = None
    invalidity: tuple[Literal["missing", "stale", "invalid", "conflicting"], ...] = ("missing", "stale", "invalid", "conflicting")

    @property
    def expression(self) -> Expr:
        return Expr("observe", self.value_type, ref=declaration_ref(self), scope=self.subject)

    @property
    def updated(self) -> Expr:
        return Expr("updated", EVENT, ref=declaration_ref(self), scope=self.subject)


@dataclass(frozen=True)
class StateStore(Record):
    id: str
    value_type: TypeSpec
    scope: Scope
    initial: str | int | bool | Quantity
    capacity: int | Ref | Literal["unbounded_requested"]
    overflow: Literal["reject", "saturate", "evict_oldest", "contract"]
    lifetime: Literal["encounter", "executor", "persistent", "duration"]
    reset: Expr | None
    inheritance: Literal["reset", "copy", "partition", "contract", "not_applicable"]
    duration: Quantity | None = None
    contract: DefinitionRef | None = None
    coordination: Ref | None = None

    @property
    def expression(self) -> Expr:
        return Expr("state", self.value_type, ref=declaration_ref(self), scope=self.scope.subject)


@dataclass(frozen=True)
class EffectLifecycle(Record):
    authorization: Literal["initiation", "continuous"]
    on_loss: Literal["continue", "request_cancel", "request_stop"]
    on_unknown: Literal["continue", "request_cancel", "request_stop", "defer"]
    cancellation: Literal["unsupported", "acknowledged", "contract"]
    completion: Literal["feedback", "contract"]
    failure: Literal["feedback", "contract"]
    contract: DefinitionRef
    timeout: Quantity | None = None
    feedback_identity: Literal["attempt_executor_subject"] = "attempt_executor_subject"


@dataclass(frozen=True)
class Argument(Record):
    name: str
    value: Expr


@dataclass(frozen=True)
class Effect(Record):
    id: str
    contract: DefinitionRef
    executor: Ref
    subject: Ref
    lifecycle: EffectLifecycle
    parameters: tuple[Argument, ...] = ()
    spatial_scope: Ref | None = None
    relationship: DefinitionRef | None = None
    resources: tuple[DefinitionRef, ...] = ()

    def event(self, outcome: Literal["requested", "initiated", "completed", "outcome", "failed", "timed_out", "cancel_requested", "cancel_acknowledged", "ceased"]) -> Expr:
        return Expr("effect_event", EVENT, ref=declaration_ref(self), value=outcome, scope=self.subject)

    @property
    def completed(self) -> Expr:
        return self.event("completed")

    @property
    def failed(self) -> Expr:
        return self.event("failed")


@dataclass(frozen=True)
class Assignment(Record):
    state: Ref
    value: Expr


@dataclass(frozen=True)
class Arbitration(Record):
    mode: Literal["exclusive", "priority", "concurrent", "nondeterministic"]
    tie: Literal["reject", "declared_order", "nondeterministic"]
    write_conflict: Literal["reject", "identical_only", "contract"]
    preemption: Literal["forbidden", "request_cancel", "contract"]
    fairness: Literal["none", "weak", "strong"]
    order: tuple[str, ...] = ()
    contract: DefinitionRef | None = None


@dataclass(frozen=True)
class Rule(Record):
    id: str
    executor: Ref
    on: Expr
    when: Expr
    unknown: Literal["defer", "transition", "request_stop"]
    effects: tuple[Ref, ...]
    assignments: tuple[Assignment, ...] = ()
    arbitration: Arbitration | None = None
    unknown_target: str | None = None
    emissions: tuple[Ref, ...] = ()


@dataclass(frozen=True)
class Machine(Record):
    id: str
    executor: Ref
    scope: Scope
    states: tuple[str, ...]
    initial: str
    terminal: tuple[str, ...]
    lifetime: Literal["encounter", "executor", "persistent"]
    arbitration: Arbitration


@dataclass(frozen=True)
class Transition(Record):
    id: str
    machine: Ref
    source: str
    destination: str
    on: Expr
    when: Expr
    unknown: Literal["defer", "transition", "request_stop"]
    effects: tuple[Ref, ...] = ()
    assignments: tuple[Assignment, ...] = ()
    unknown_target: str | None = None
    emissions: tuple[Ref, ...] = ()


@dataclass(frozen=True)
class Channel(Record):
    id: str
    sender: Ref
    recipients: tuple[Ref, ...]
    message_type: TypeSpec
    contract: DefinitionRef
    scope: Scope
    ordering: Literal["fifo", "unordered", "causal"]
    loss: Literal["permitted", "forbidden", "contract"]
    duplication: Literal["permitted", "deduplicate", "forbidden"]
    acknowledgment: Literal["none", "required"]
    retry: Literal["none", "bounded", "contract"]
    max_attempts: int | None = None
    latency: Quantity | None = None
    spatial_scope: Ref | None = None


@dataclass(frozen=True)
class Message(Record):
    id: str
    channel: Ref
    sender: Ref
    subject: Ref
    correlation: Ref
    payload: Expr
    identity_policy: Literal["per_emission_preserved_across_retries"] = "per_emission_preserved_across_retries"

    def event(self, phase: Literal["sent", "received", "acknowledged", "expired"]) -> Expr:
        return Expr("message_event", EVENT, ref=declaration_ref(self), value=phase, scope=self.subject)


@dataclass(frozen=True)
class Requirement(Record):
    id: str
    kind: Literal["safety", "progress", "bound", "observability", "external_control", "approximation", "assumption", "preference", "objective"]
    description: str
    scope: Scope
    condition: Expr | None = None
    response: Expr | None = None
    deadline: Quantity | None = None
    lower: Quantity | None = None
    upper: Quantity | None = None
    horizon: Quantity | Literal["unbounded_requested"] | None = None
    assumptions: tuple[str, ...] = ()
    applies_to: tuple[Ref, ...] = ()
    contract: DefinitionRef | None = None
    trigger: Expr | None = None
    clock: Ref | None = None


Declaration: TypeAlias = Role | Subject | Encounter | SpatialScope | Clock | Observation | StateStore | Effect | Rule | Machine | Transition | Channel | Message | Requirement | Parameter


@dataclass(frozen=True)
class ChassisProfile(Record):
    id: str
    version: str
    lineage: str
    subtype: str
    activation_states: tuple[str, ...]
    differentiation_states: tuple[str, ...]
    capabilities: tuple[DefinitionRef, ...]
    operational_model: DefinitionRef
    environment: tuple[DefinitionRef, ...]
    interfaces: tuple[DefinitionRef, ...]
    species: Literal["human"] = "human"
    recipient_class: Literal["immune", "immune_progenitor"] = "immune"


@dataclass(frozen=True)
class RoleBinding(Record):
    role: Ref
    chassis: ChassisProfile


@dataclass(frozen=True)
class DeliveryContract(Record):
    id: str
    intended_recipients: tuple[Ref, ...]
    arrival: DefinitionRef
    expression: DefinitionRef
    activation: DefinitionRef
    co_delivery: Literal["none_required", "same_recipient", "same_population", "contract"]
    contract: DefinitionRef
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class RNAConstraints(Record):
    design_count: int | None = None
    member_count: int | None = None
    helper_count: int | None = None
    copy_number: Parameter | None = None
    dose: Parameter | None = None
    orf_count: int | None = None
    product_count: int | None = None
    payload_persistence: Quantity | None = None
    effector_persistence: Quantity | None = None
    format: Literal["RNA"] = "RNA"


@dataclass(frozen=True)
class Deployment(Record):
    id: str
    bindings: tuple[RoleBinding, ...]
    environment: tuple[DefinitionRef, ...]
    delivery: DeliveryContract
    payload: RNAConstraints
    route: Literal["in_vivo"] = "in_vivo"


@dataclass(frozen=True)
class ImplementationBinding(Record):
    id: str
    version: str
    operation: DefinitionRef
    realization: DefinitionRef
    chassis: tuple[str, ...]
    payload_formats: tuple[Literal["RNA"], ...]
    dependencies: tuple[DefinitionRef, ...]
    evidence: tuple[DefinitionRef, ...]


@dataclass(frozen=True)
class ImplementationCatalogLock(Record):
    id: str
    version: str
    implementations: tuple[ImplementationBinding, ...] = ()


@dataclass(frozen=True)
class AssuranceRequest(Record):
    requirements: tuple[str, ...]
    level: Literal["structural", "bounded", "proof"]
    horizon: Quantity | Literal["unbounded_requested"]
    assumptions: tuple[str, ...] = ()
    tolerances: tuple[Argument, ...] = ()


@dataclass(frozen=True)
class PolicyDraft(Record):
    id: str
    semantics: SemanticBundle
    declarations: tuple[Declaration, ...]
    holes: tuple[Hole, ...] = ()
    source_map: tuple[SourceSpan, ...] = ()
    profile: str = PROFILE


@dataclass(frozen=True)
class PolicyProgram(Record):
    id: str
    semantics: SemanticBundle
    declarations: tuple[Declaration, ...]
    source_map: tuple[SourceSpan, ...] = ()
    profile: str = PROFILE


@dataclass(frozen=True)
class BuildRequest(Record):
    program: PolicyProgram
    deployment: Deployment
    implementations: ImplementationCatalogLock
    assurance: AssuranceRequest
    profile: str = PROFILE


Document: TypeAlias = PolicyDraft | PolicyProgram | BuildRequest


@dataclass(frozen=True)
class CompilationSubmission(Record):
    """Immutable authoring handoff; construction grants no semantic acceptance."""

    request: BuildRequest
    profile: str
    document_digest: str
    program_digest: str
    semantic_bundle: DefinitionRef
    implementation_catalog: DefinitionRef
    dependencies: tuple[DefinitionRef, ...]
    required_features: tuple[str, ...]
    assumptions: tuple[str, ...]
    outstanding_obligations: tuple[str, ...]
    schema_version: Literal["biocompiler.policy_submission.v0.1"] = "biocompiler.policy_submission.v0.1"
    authoring_status: Literal["complete"] = "complete"
    semantic_status: Literal["unassessed"] = "unassessed"
    target_status: Literal["unassessed"] = "unassessed"
    backend_execution: Literal["not_performed"] = "not_performed"
    claim_scope: str = "Structurally complete authoring data only; no semantic, realization, biological, admission or export acceptance."

    @property
    def program(self) -> PolicyProgram:
        return self.request.program


@dataclass(frozen=True)
class BackendCapabilities(Record):
    """Caller-declared feature inventory, never installed-code authority."""

    backend_id: str
    version: str
    profiles: tuple[str, ...]
    features: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("backend_id", "version"):
            value = getattr(self, name)
            if type(value) is not str or not value or len(value.encode("utf-8")) > 256:
                raise ValueError("Backend identity/version must be bounded nonempty strings.")
        for name in ("profiles", "features"):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > 4096:
                raise ValueError("Backend declarations require bounded feature/profile tuples.")
            if any(type(item) is not str or not item or len(item.encode("utf-8")) > 256 for item in values):
                raise ValueError("Backend profile/feature names must be bounded nonempty strings.")
            if len(set(values)) != len(values):
                raise ValueError("Backend profile/feature names must be unique.")


@dataclass(frozen=True)
class CapabilityAssessment(Record):
    """Immutable feature comparison, separate from any compiler assessment."""

    backend_id: str
    backend_version: str
    profile: str
    profile_supported: bool
    document_digest: str
    authoring_status: Literal["complete", "incomplete", "invalid"]
    required_features: tuple[str, ...]
    supported_features: tuple[str, ...]
    unsupported_features: tuple[str, ...]
    status: Literal["declared_compatible", "unsupported"]
    target_status: Literal["unassessed", "unbound"]
    schema_version: Literal["biocompiler.policy_capability_assessment.v0.1"] = "biocompiler.policy_capability_assessment.v0.1"
    semantic_status: Literal["unassessed"] = "unassessed"
    backend_execution: Literal["not_performed"] = "not_performed"
    claim_scope: str = "Caller-declared feature coverage only; no backend execution or semantic acceptance."
