"""Inspectable authoring expansions; these functions do not lower or execute."""
from typing import Literal

from . import model as m
from .programs import ProgramBuilder, ref
from .logic import all_of, not_, literal, arithmetic, compare
from .time import holds


def context_gate(builder: ProgramBuilder, name: str, *, executor: m.Ref, on: m.Expr, evidence: m.Expr, exclusion: m.Expr, effect: m.Ref, arbitration: m.Arbitration) -> m.Rule:
    with builder.namespace(name):
        return builder.rule("respond", executor=executor, on=on, when=all_of(evidence, not_(exclusion)), unknown="defer", effects=(effect,), arbitration=arbitration)


def once_per_scope(builder: ProgramBuilder, name: str, *, executor: m.Ref, scope: m.Scope, on: m.Expr, permitted: m.Expr, effect: m.Ref, lifetime: str, arbitration: m.Arbitration) -> m.Rule:
    if lifetime not in ("encounter", "executor", "persistent"):
        raise ValueError("Pattern requires encounter, executor or persistent lifetime")
    from typing import cast, Literal
    with builder.namespace(name):
        seen = builder.state(m.StateStore("seen", m.TRUTH, scope, False, 1, "reject", cast(Literal["encounter", "executor", "persistent"], lifetime), None, "reset"))
        return builder.rule("respond", executor=executor, on=on, when=all_of(permitted, not_(seen.expression)), unknown="defer", effects=(effect,), assignments=(m.Assignment(ref(seen), literal(True)),), arbitration=arbitration)


def ordered_effects(builder: ProgramBuilder, name: str, *, executor: m.Ref, scope: m.Scope, on: m.Expr, permitted: m.Expr, first: m.Effect, second: m.Effect, arbitration: m.Arbitration, lifetime: Literal["encounter", "executor", "persistent"] | None = None, handoff_when: m.Expr | None = None) -> m.Machine:
    """Declare two stages, including explicit failure and timeout transitions.

    The handoff guard is sampled on the first effect's completion event. A false
    or unknown guard leaves the machine in its current state; it does not queue
    a handoff for a later observation. Effect lifecycle declarations own timeout
    duration and authorization semantics. This expansion adds no completion,
    cancellation, retry or biological realization guarantee.
    """
    if lifetime is None:
        if scope.kind == "encounter":
            lifetime = "encounter"
        elif scope.kind == "executor":
            lifetime = "executor"
        else:
            raise ValueError("Ordered effects require an explicit lifetime outside executor or encounter scope")
    if lifetime not in ("encounter", "executor", "persistent"):
        raise ValueError("Pattern requires encounter, executor or persistent lifetime")
    if scope.kind in ("encounter", "executor") and lifetime != scope.kind:
        raise ValueError("Ordered effects lifetime must match executor or encounter scope")
    handoff_guard = permitted if handoff_when is None else handoff_when
    with builder.namespace(name):
        machine = builder.machine("stages", executor=executor, scope=scope, states=("ready", "first", "second", "completed", "failed"), initial="ready", terminal=("completed", "failed"), lifetime=lifetime, arbitration=arbitration)
        builder.transition("start", machine=machine, source="ready", destination="first", on=on, when=permitted, effects=(ref(first),))
        builder.transition("handoff", machine=machine, source="first", destination="second", on=first.completed, when=handoff_guard, effects=(ref(second),))
        builder.transition("completed", machine=machine, source="second", destination="completed", on=second.completed)
        builder.transition("first_failed", machine=machine, source="first", destination="failed", on=first.failed)
        builder.transition("second_failed", machine=machine, source="second", destination="failed", on=second.failed)
        builder.transition("first_timed_out", machine=machine, source="first", destination="failed", on=first.event("timed_out"))
        builder.transition("second_timed_out", machine=machine, source="second", destination="failed", on=second.event("timed_out"))
        return machine


def bounded_response(builder: ProgramBuilder, name: str, *, executor: m.Ref, scope: m.Scope, on: m.Expr, permitted: m.Expr, effect: m.Ref, maximum: int, arbitration: m.Arbitration) -> m.Rule:
    if type(maximum) is not int or maximum < 1:
        raise ValueError("maximum must be a positive integer")
    with builder.namespace(name):
        counter = builder.state(m.StateStore("count", m.INTEGER, scope, 0, maximum, "reject", "executor", None, "reset"))
        increment = arithmetic(counter.expression, "add", literal(1))
        return builder.rule("respond", executor=executor, on=on, when=all_of(permitted, compare(counter.expression, "lt", maximum)), unknown="defer", effects=(effect,), assignments=(m.Assignment(ref(counter), increment),), arbitration=arbitration)


def persistence_gate(builder: ProgramBuilder, name: str, *, executor: m.Ref, on: m.Expr, permitted: m.Expr, effect: m.Ref, duration: m.Quantity, clock: m.Ref, arbitration: m.Arbitration) -> m.Rule:
    with builder.namespace(name):
        return builder.rule("respond", executor=executor, on=on, when=holds(permitted, duration, clock=clock, coverage="continuous"), unknown="defer", effects=(effect,), arbitration=arbitration)


def population_handoff(builder: ProgramBuilder, name: str, *, sender: m.Ref, receiver: m.Ref, on: m.Expr, permitted: m.Expr, message: m.Message, receiver_effect: m.Ref, arbitration: m.Arbitration, sender_effects: tuple[m.Ref, ...] = ()) -> tuple[m.Rule, m.Rule]:
    with builder.namespace(name):
        send = builder.rule("send", executor=sender, on=on, when=permitted, unknown="defer", effects=sender_effects, emissions=(ref(message),), arbitration=arbitration)
        receive = builder.rule("receive", executor=receiver, on=message.event("received"), when=literal(True), unknown="defer", effects=(receiver_effect,), arbitration=arbitration)
        return send, receive
