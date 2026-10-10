"""Complete source-only example; also checked with strict mypy, without stubs."""
from typing import assert_type

from biocompiler import policy as p
from biocompiler.policy import typed as t


def complete_policy() -> p.PolicyProgram:
    """Request at most three abstract responses on a cell-accessible signal."""
    interface = p.SemanticDefinition("interface", "1", "interface", "Supplied abstract executor interface.")
    observed = p.SemanticDefinition("observed", "1", "observation", "Supplied abstract evidence.", result=p.TRUTH)
    operation = p.SemanticDefinition("operation", "1", "operation", "Abstract response request; no biological claim.")
    lifecycle = p.SemanticDefinition("lifecycle", "1", "lifecycle", "Separately correlated response feedback.")
    builder = p.ProgramBuilder("typed_example", semantics=p.SemanticBundle(
        "abstract_contracts", "1", (interface, observed, operation, lifecycle)))
    executor = builder.executor("executor", requires=(interface.ref,))
    target = builder.subject("target", entity_kind="cell", identity_scope="stable", executor=executor)
    clock = builder.clock("time", basis="availability", resolution=p.quantity("0.1", p.SECOND))
    signal = t.truth_observation(builder.observe("signal", observer=executor, subject=target,
        value_type=p.TRUTH, contract=observed.ref, clock=clock, access="cell", coverage="event",
        coherence="target_frame", freshness=p.quantity("1", p.SECOND)))
    count = t.integer_state(builder.state(p.StateStore("count", p.INTEGER, p.Scope("executor", p.ref(executor)),
        0, 3, "reject", "executor", None, "not_applicable")))
    maximum = t.integer_parameter(builder.add(p.Parameter("maximum", p.INTEGER, value=3)))
    response = t.Effect(builder.effect("response", contract=operation.ref, executor=executor, subject=target,
        lifecycle=p.EffectLifecycle("initiation", "continue", "defer", "unsupported", "feedback", "feedback",
                                    lifecycle.ref, p.quantity("2", p.SECOND))))
    allowed = signal.value & count.value.lt(maximum.value)
    assert_type(signal, t.Observation[t.TruthExpr])
    assert_type(signal.updated, t.EventExpr)
    assert_type(count.value + t.integer(1), t.IntegerExpr)
    assert_type(allowed, t.TruthExpr)
    assert_type(response.completed, t.EventExpr)
    assert_type(t.quantity("1", p.SECOND) + t.quantity("1", p.MINUTE), t.QuantityExpr)
    assert_type(t.text("ready").eq(t.text("ready")), t.TruthExpr)
    t.rule(builder, "respond", executor=executor, on=signal.updated, when=allowed, unknown="defer",
        effects=(response,), assignments=(count.assign(count.value + t.integer(1)),),
        arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    builder.require(p.Requirement("permission", "safety", "Each new request requires the declared permission.",
        p.Scope("executor", p.ref(executor)), condition=t.guard(allowed), applies_to=(p.ref(response.to_source()),)))
    return builder.freeze()


def staged_transitions(builder: p.ProgramBuilder, machine: p.Machine, signal: t.Observation[t.TruthExpr],
                       first: t.Effect, second: t.Effect) -> p.Transition:
    return t.transition(builder, "handoff", machine=machine, source="first", destination="second",
        on=first.completed, when=signal.value, unknown="defer", effects=(second,))


def reusable_state(state: t.State[t.TruthExpr], condition: t.TruthExpr) -> t.State[t.TruthExpr]:
    assert_type(state.assign(condition), t.Assignment)
    return state.with_reset(condition)
