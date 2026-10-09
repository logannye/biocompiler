"""Intentional static errors. Each E marker identifies one expected diagnostic."""
from biocompiler import policy as p
from biocompiler.policy import typed as t


def mistakes(builder: p.ProgramBuilder, executor: p.Role, effect: t.Effect,
             observation: p.Observation, state: t.State[t.TruthExpr], machine: p.Machine) -> None:
    condition = t.truth(True)
    event = condition.rising()
    condition.eq(t.integer(1))  # E: arg-type
    t.integer(1) + t.text("one")  # E: operator
    t.quantity("1", p.SECOND).lt(t.integer(1))  # E: arg-type
    t.guard(event)  # E: arg-type
    t.trigger(condition)  # E: arg-type
    state.assign(t.integer(1))  # E: arg-type
    state.with_reset(event)  # E: arg-type
    t.text("a").lt(t.text("b"))  # E: attr-defined
    t.argument("product", event)  # E: arg-type
    t.rising(event)  # E: arg-type
    t.Observation(observation, t.EventExpr)  # E: type-var
    widened: t.State[t.ScalarExpression] = state  # E: assignment
    t.rule(builder, "bad_trigger", executor=executor, on=condition, when=condition, unknown="defer",  # E: arg-type
           effects=(effect,), arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    t.rule(builder, "bad_guard", executor=executor, on=event, when=event, unknown="defer",  # E: arg-type
           effects=(effect,), arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    t.rule(builder, "bad_executor", executor=effect.to_source(), on=event, when=condition, unknown="defer",  # E: arg-type
           effects=(effect,), arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    t.transition(builder, "bad_machine", machine=executor, source="a", destination="b",  # E: arg-type
                 on=event, when=condition, unknown="defer")
    t.transition(builder, "bad_effect", machine=machine, source="a", destination="b",
                 on=event, when=condition, unknown="defer", effects=(executor,))  # E: arg-type
