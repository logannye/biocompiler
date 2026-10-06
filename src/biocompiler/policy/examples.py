"""Eight abstract authoring examples, without molecular or biological claims.

Contracts here are deliberately supplied software definitions, not realizations.
All numerical values are illustrative authoring fixtures, not therapeutic values.
"""
from . import model as m
from .programs import ProgramBuilder, ref
from .values import quantity, SECOND
from .logic import all_of, not_, compare, literal
from . import patterns

NAMES = ("context_gated_response", "regulated_secretion", "staged_cleanup_repair", "encounter_sentinel", "target_sentinel", "local_restraint", "coordinated_populations", "lineage_bounded_response")
RATE = m.Unit("abstract_output_per_s", "count/time", "output_rate", reference="executor")


def semantic_bundle() -> m.SemanticBundle:
    definitions: list[m.SemanticDefinition] = [
        m.SemanticDefinition("example.interface", "1", "interface", "Abstract human immune executor interface; supplied, unvalidated capabilities."),
        m.SemanticDefinition("example.encounter", "1", "encounter", "One contact-bound target identity; contact loss ends the encounter."),
        m.SemanticDefinition("example.observation", "1", "observation", "Supplied cell-accessible observations with declared coherence and coverage; missing evidence is unknown.", result=m.TRUTH),
        m.SemanticDefinition("example.observation_rate", "1", "observation", "Supplied sampled rate observations in an explicitly typed executor reference scope.", result=m.TypeSpec("quantity", RATE)),
        m.SemanticDefinition("example.lifecycle", "1", "lifecycle", "Request, initiation, completion, failure and cancellation acknowledgment are separate feedback events bound to an attempt and subject."),
        m.SemanticDefinition("example.transport", "1", "transport", "Abstract addressed messages with explicit subject correlation; supplied transport assumptions are not a delivery guarantee."),
        m.SemanticDefinition("example.model", "1", "model", "Abstract human immune chassis operational model; no empirical execution claim."),
        m.SemanticDefinition("example.environment", "1", "environment", "Illustrative declared human in-vivo environment; all applicability remains unresolved."),
        m.SemanticDefinition("example.delivery", "1", "delivery", "Supplied delivery assumptions separately bind arrival, expression and activation; no implied empirical support."),
        m.SemanticDefinition("example.spatial", "1", "spatial", "Abstract local region; observation and effect scopes must be explicitly bound."),
        m.SemanticDefinition("example.inheritance", "1", "inheritance", "Declared copying of finite state to descendants; realization and preservation are unresolved."),
    ]
    for name in ("response", "cleanup", "repair", "report", "restrain", "stop"):
        definitions.append(m.SemanticDefinition("example." + name, "1", "operation", f"Request the abstract {name} effect on the bound subject; completion requires separate correlated feedback.", executor_kind="executor", subject_kind="cell"))
    definitions.append(m.SemanticDefinition("example.secrete", "1", "operation", "Request abstract secretion at the supplied rate; no molecular implementation is supplied.", parameters=(m.Parameter("rate", m.TypeSpec("quantity", RATE), selection="design"),), executor_kind="executor", subject_kind="cell"))
    return m.SemanticBundle("abstract_examples", "1", tuple(definitions))


def _definition(bundle: m.SemanticBundle, name: str) -> m.DefinitionRef:
    return next(d.ref for d in bundle.definitions if d.id == "example." + name)


def build_example(name: str) -> m.PolicyProgram:
    if name not in NAMES:
        raise ValueError(f"Unknown example: {name}")
    bundle = semantic_bundle()
    def contract(key: str) -> m.DefinitionRef:
        return _definition(bundle, key)
    p = ProgramBuilder(name, semantics=bundle)
    executor = p.executor("executor", requires=(contract("interface"),), lineage_role=name == "lineage_bounded_response")
    clock = p.clock("available_time", basis="availability", resolution=quantity("0.1", SECOND))
    encounter = p.encounter("encounter", executor=executor, contract=contract("encounter"))
    target = encounter.target
    if name == "target_sentinel":
        target = ref(p.subject("persistent_target", entity_kind="cell", identity_scope="stable", executor=executor))
    disease = p.observe("disease", observer=executor, subject=target, value_type=m.TRUTH, contract=contract("observation"), clock=clock, access="cell", coverage="continuous", coherence="target_frame", freshness=quantity(1, SECOND))
    exclusion = p.observe("exclusion", observer=executor, subject=target, value_type=m.TRUTH, contract=contract("observation"), clock=clock, access="cell", coverage="continuous", coherence="target_frame", freshness=quantity(1, SECOND))
    allowed = all_of(disease.expression, not_(exclusion.expression))
    arbitration = m.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
    lifecycle = m.EffectLifecycle("continuous", "request_stop", "request_stop", "acknowledged", "feedback", "feedback", contract("lifecycle"), quantity(10, SECOND))
    operation = "response"
    if name in ("encounter_sentinel", "target_sentinel", "coordinated_populations"):
        operation = "report"
    elif name == "staged_cleanup_repair":
        operation = "cleanup"
    elif name == "local_restraint":
        operation = "restrain"
    parameters: tuple[m.Argument, ...] = ()
    if name == "regulated_secretion":
        rate = p.observe("requested_rate", observer=executor, subject=target, value_type=m.TypeSpec("quantity", RATE), contract=contract("observation_rate"), clock=clock, access="cell", coverage="sampled", coherence="rate_frame", freshness=quantity(1, SECOND))
        operation = "secrete"
        allowed = all_of(allowed, compare(rate.expression, "ge", quantity(0, RATE)), compare(rate.expression, "le", quantity(5, RATE)))
        parameters = (m.Argument("rate", rate.expression),)
    spatial_scope = None
    if name == "local_restraint":
        region = p.subject("local_region", entity_kind="region", identity_scope="aggregate")
        spatial_scope = ref(p.add(m.SpatialScope("effect_region", "region", ref(region), contract("spatial"))))
    effect = p.effect("effect", contract=contract(operation), executor=executor, subject=target, lifecycle=lifecycle, parameters=parameters, spatial_scope=spatial_scope)
    encounter_scope = m.Scope("encounter", ref(encounter))
    if name == "context_gated_response":
        patterns.context_gate(p, "gate", executor=ref(executor), on=disease.updated, evidence=disease.expression, exclusion=exclusion.expression, effect=ref(effect), arbitration=arbitration)
    elif name in ("encounter_sentinel", "target_sentinel"):
        patterns.once_per_scope(p, "sentinel", executor=ref(executor), scope=encounter_scope if name == "encounter_sentinel" else m.Scope("target", target), on=disease.updated, permitted=allowed, effect=ref(effect), lifetime="encounter" if name == "encounter_sentinel" else "persistent", arbitration=arbitration)
    elif name == "staged_cleanup_repair":
        repair = p.effect("repair", contract=contract("repair"), executor=executor, subject=target, lifecycle=lifecycle)
        patterns.ordered_effects(p, "stages", executor=ref(executor), scope=encounter_scope, on=disease.updated, permitted=allowed, first=effect, second=repair, arbitration=arbitration)
    elif name == "local_restraint":
        patterns.persistence_gate(p, "persistent_context", executor=ref(executor), on=disease.updated, permitted=allowed, effect=ref(effect), duration=quantity(2, SECOND), clock=ref(clock), arbitration=arbitration)
    elif name == "coordinated_populations":
        population = p.subject("population", entity_kind="population", identity_scope="aggregate")
        receiver = p.executor("receiver", requires=(contract("interface"),), population=ref(population))
        channel = p.channel(m.Channel("handoff", ref(executor), (ref(receiver),), m.TEXT, contract("transport"), m.Scope("population", ref(population)), "fifo", "permitted", "deduplicate", "required", "bounded", max_attempts=3, latency=quantity(5, SECOND)))
        message = p.add(m.Message("message", ref(channel), ref(executor), target, target, literal("ready")))
        receiver_effect = p.effect("receiver_effect", contract=contract("response"), executor=receiver, subject=target, lifecycle=lifecycle, relationship=contract("transport"))
        patterns.population_handoff(p, "coordination", sender=ref(executor), receiver=ref(receiver), on=disease.updated, permitted=allowed, message=message, receiver_effect=ref(receiver_effect), arbitration=arbitration, sender_effects=(ref(effect),))
        p.require(m.Requirement("acknowledgment", "progress", "A sent message requires correlated acknowledgment under supplied transport assumptions.", m.Scope("population", ref(population)), response=message.event("acknowledged"), deadline=quantity(5, SECOND), applies_to=(ref(message),), trigger=message.event("sent"), clock=ref(clock)))
        p.require(m.Requirement("receiver_progress", "progress", "A receiver request requires completion of its correlated attempt.", m.Scope("executor", ref(receiver)), response=receiver_effect.completed, deadline=quantity(10, SECOND), trigger=receiver_effect.event("requested"), clock=ref(clock)))
    elif name == "lineage_bounded_response":
        lineage = p.subject("lineage", entity_kind="lineage", identity_scope="aggregate", executor=executor)
        p.state(m.StateStore("inherited_mode", m.TEXT, m.Scope("lineage", ref(lineage)), "ready", 1, "reject", "persistent", None, "copy", contract=contract("inheritance")))
        authorization = p.observe("authorization", observer=executor, subject=target, value_type=m.TRUTH, contract=contract("observation"), clock=clock, access="cell", coverage="continuous", coherence="control_frame", freshness=quantity(1, SECOND))
        patterns.bounded_response(p, "bounded", executor=ref(executor), scope=m.Scope("executor", ref(executor)), on=disease.updated, permitted=all_of(allowed, authorization.expression), effect=ref(effect), maximum=3, arbitration=arbitration)
        p.require(m.Requirement("authorization_required", "external_control", "Authorization permits new requests; lifecycle governs ongoing activity.", m.Scope("executor", ref(executor)), condition=authorization.expression, applies_to=(ref(effect),)))
    else:
        p.rule("feedback", executor=executor, on=disease.updated, when=allowed, unknown="defer", effects=(ref(effect),), arbitration=arbitration)
        p.require(m.Requirement("rate_bound", "bound", "Requested abstract secretion rate remains within the declared range.", m.Scope("executor", ref(executor)), lower=quantity(0, RATE), upper=quantity(5, RATE), applies_to=(ref(effect),)))
    p.require(m.Requirement("permission", "safety", "No new response starts without the declared permission.", m.Scope("executor", ref(executor)), condition=allowed, applies_to=(ref(effect),)))
    p.require(m.Requirement("response_progress", "progress", "A response request requires correlated completion under supplied execution assumptions.", m.Scope("executor", ref(executor)), response=effect.completed, deadline=quantity(10, SECOND), horizon=quantity(30, SECOND), trigger=effect.event("requested"), clock=ref(clock)))
    return p.freeze()


def build_request(name: str = "context_gated_response") -> m.BuildRequest:
    program = build_example(name)
    def contract(key: str) -> m.DefinitionRef:
        return _definition(program.semantics, key)
    roles = tuple(d for d in program.declarations if isinstance(d, m.Role))
    chassis = m.ChassisProfile("illustrative_immune", "1", "abstract_immune", "supplied_profile", ("declared",), ("declared",), (contract("interface"),), contract("model"), (contract("environment"),), (contract("interface"),))
    delivery = m.DeliveryContract("delivery", tuple(ref(r) for r in roles), contract("delivery"), contract("delivery"), contract("delivery"), "none_required", contract("delivery"))
    deployment = m.Deployment("deployment", tuple(m.RoleBinding(ref(r), chassis) for r in roles), (contract("environment"),), delivery, m.RNAConstraints(design_count=1, member_count=1, helper_count=0))
    requirements = tuple(d.id for d in program.declarations if isinstance(d, m.Requirement) and d.kind not in ("assumption", "preference", "objective"))
    return m.BuildRequest(program, deployment, m.ImplementationCatalogLock("empty_supplied_catalog", "1"), m.AssuranceRequest(requirements, "proof", quantity(30, SECOND)))
