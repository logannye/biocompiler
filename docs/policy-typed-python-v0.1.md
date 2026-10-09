# Typed Python authoring facade v0.1

`biocompiler.policy.typed` provides Python type checking and runtime checks for a
useful subset of policy authoring. It produces the same ordinary source records
as `biocompiler.policy`; it defines no new wire language, canonical identity,
execution semantics, or admission authority. The
[language specification](policy-language-specification-v0.1.md) remains the
language contract. Full source checking and native profile admission remain
necessary after authoring.

```python
from biocompiler import policy as p
from biocompiler.policy import typed as t
```

## Expression and declaration types

| Type | Constructors or adapters | Supported operations |
| --- | --- | --- |
| `TruthExpr` | `truth(bool)`, `unknown()`, `truth_observation/state/parameter(record)` | `&`, `\|`, `~`, `.eq()`, `.ne()`, `.rising()` |
| `IntegerExpr` | `integer(int)`, `integer_observation/state/parameter(record)` | `+`, `-`, `.eq()`, `.ne()`, `.lt()`, `.le()`, `.gt()`, `.ge()` |
| `TextExpr` | `text(str)`, `text_observation/state/parameter(record)` | `.eq()`, `.ne()` |
| `QuantityExpr` | `quantity(str/int/Decimal, unit)`, `quantity_observation/state/parameter(record)` | Numeric operations above, `.unit` |
| `EventExpr` | observation `.updated`, truth `.rising()`, effect `.event(phase)` | `trigger(event)`; events are not scalar values |

Adapters return invariant generic handles: `Observation[TruthExpr]`,
`State[IntegerExpr]`, or `Parameter[QuantityExpr]`, for example. Each `.value`
returns its declared expression type. `State[S].assign(value: S)` returns a typed
`Assignment`. `State[S].with_reset(condition: TruthExpr)` returns a new handle
containing a source declaration with that reset condition; it does not replace a
declaration already added to a builder. Construct the reset-bearing state before
adding it, or explicitly construct a new source program with the replacement.

The generic constructors `Observation(record, TruthExpr)`, `State(record,
IntegerExpr)`, and `Parameter(record, QuantityExpr)` are equivalent to the named
adapters. They check the source declaration category at runtime. A truth state
cannot receive an integer assignment through generic type widening. Initial
state values and supplied parameter values must match their scalar categories.

`Effect(record)` retains the nominal effect declaration. Its `.requested`,
`.initiated`, `.completed`, `.failed`, and `.timed_out` properties return distinct
event expressions. `.event(phase)` also supports `outcome`, `cancel_requested`,
`cancel_acknowledged`, and `ceased`. Representing a phase does not establish that
an operational profile or a physical implementation can observe it.

Use `t.argument(name, scalar)` to construct a source effect argument. Events are
rejected in arguments, scalar equality, guards, assignments, and reset
conditions. `t.rule` takes a nominal source `Role`, an event `on`, a truth `when`,
typed effects and assignments, and explicit unknown handling and arbitration.
`t.transition` takes a nominal source `Machine`, declared state endpoints, an
event trigger, a truth guard, and an explicit unknown branch. A redirected effect
subject needs a relationship contract. These constructors validate the complete
prospective source declaration before adding it to the existing `ProgramBuilder`.

## Complete source example

This abstract software fixture requests a response on a signal update while the
signal is true and the request count is below three. Its numerical choices and
contracts are illustrative; they supply no biological or clinical evidence.

```python
from biocompiler import policy as p
from biocompiler.policy import typed as t

interface = p.SemanticDefinition(
    "interface", "1", "interface", "Supplied abstract executor interface.")
observed = p.SemanticDefinition(
    "observed", "1", "observation", "Supplied abstract evidence.", result=p.TRUTH)
operation = p.SemanticDefinition(
    "operation", "1", "operation", "Abstract response request.")
lifecycle = p.SemanticDefinition(
    "lifecycle", "1", "lifecycle", "Separately correlated response feedback.")
builder = p.ProgramBuilder("typed_example", semantics=p.SemanticBundle(
    "abstract_contracts", "1", (interface, observed, operation, lifecycle)))
executor = builder.executor("executor", requires=(interface.ref,))
target = builder.subject(
    "target", entity_kind="cell", identity_scope="stable", executor=executor)
clock = builder.clock(
    "time", basis="availability", resolution=p.quantity("0.1", p.SECOND))
signal = t.truth_observation(builder.observe(
    "signal", observer=executor, subject=target, value_type=p.TRUTH,
    contract=observed.ref, clock=clock, access="cell", coverage="event",
    coherence="target_frame", freshness=p.quantity("1", p.SECOND)))
count = t.integer_state(builder.state(p.StateStore(
    "count", p.INTEGER, p.Scope("executor", p.ref(executor)),
    0, 3, "reject", "executor", None, "not_applicable")))
maximum = t.integer_parameter(builder.add(p.Parameter("maximum", p.INTEGER, value=3)))
response = t.Effect(builder.effect(
    "response", contract=operation.ref, executor=executor, subject=target,
    lifecycle=p.EffectLifecycle(
        "initiation", "continue", "defer", "unsupported", "feedback", "feedback",
        lifecycle.ref, p.quantity("2", p.SECOND))))

allowed = signal.value & count.value.lt(maximum.value)
t.rule(builder, "respond", executor=executor, on=signal.updated, when=allowed,
    unknown="defer", effects=(response,),
    assignments=(count.assign(count.value + t.integer(1)),),
    arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
builder.require(p.Requirement(
    "permission", "safety", "Each new request requires the declared permission.",
    p.Scope("executor", p.ref(executor)), condition=t.guard(allowed),
    applies_to=(p.ref(response.to_source()),)))
program = builder.freeze()
report = p.check(program)  # source structure: complete; semantic status: unassessed
wire = p.dumps(program)   # unchanged policy-v0.1 serialization
```

An executable counterpart of this example and additional checked expressions
live in `tests/typecheck/policy_typed_positive.py`. The runtime test checks its
ordinary source rule, JSON round trip, canonical document digest, and source
report. No native execution or therapeutic realization is implied by that test.

## What typing catches

With strict mypy and the real imported module, these are errors:

```python
t.guard(signal.updated)                    # event cannot be a guard
t.trigger(signal.value)                    # truth cannot be a trigger
count.assign(t.truth(True))                 # integer state needs IntegerExpr
t.integer(1) + t.text("one")                # mixed scalar categories
t.text("ready").lt(t.text("waiting"))       # text has no ordered comparison
t.argument("feedback", response.completed) # event cannot be an effect argument
```

The matching runtime checks still apply when type checking is absent or inputs
come through dynamically typed code. Unit dimensions, quantity kinds, and
reference scopes are checked at runtime; these are not Python type parameters.
Compatible second and minute quantities may be combined, preserving the original
unit-bearing source operands and the left-hand result type. This facade neither
evaluates the conversion nor introduces dimension inference. Decimal inputs are
exact; floats, nonfinite scales, nonpositive scales, and oversized decimal
representations reject under existing source limits or facade checks.

Use `.eq()` and `.ne()` for policy equality. Python `==`, `!=`, `bool(expr)`,
`if expr`, `and`, and `or` must not silently consume a symbolic expression: truth
conversion and equality raise `TypedAuthoringError`. Use `&`, `|`, and `~` for
policy logic, with parentheses where Python precedence requires them. These
operators construct expressions; they do not evaluate a policy. `unknown()`
remains the language's explicit unknown truth value.

## Source bridge and assurance boundary

`.to_source()` and `guard()`/`trigger()` explicitly return existing source
dataclasses. Original builder ownership tokens and nominal references are
retained; the facade does not serialize and decode records to erase ownership.
Expressions from different builders or different observed subjects cannot be
silently combined. `to_source()` revalidates the current object, including bounded
serialization before recursive traversal, and returns the original immutable
source record. An assignment produces an ordinary source `Assignment` with its
original state reference. Malformed source or exceeded representation limits may
raise the source serializer's `ValueError`; local category violations raise
`TypedAuthoringError`, a `TypeError` subclass.

Static guarantees end at the explicit raw-source bridge. The source API remains
available for advanced vocabulary. Wrapping an arbitrary source expression only
checks the supported expression shape, its declared category, and local
invariants. It cannot resolve all references or establish observation access,
clock semantics, executor authority, effect lifecycle feasibility, requirement
proof, or physical realization. For example, an observation declared for an
external evaluator stays external when wrapped: using it in cellular behavior
still fails full source checking. Source-valid expressions may still be rejected
by operational admission. This facade is not a substitute for either checker.

Supported scalar expressions are literals, observation/state/parameter reads,
truth logic, scalar equality, numeric ordering, and addition/subtraction.
Supported events are observation updates, rising truth edges, and declared effect
lifecycle phases. Quantifiers, entities, custom calls, temporal expressions,
multiplication/division, and richer source-only vocabulary use the ordinary source
API for now. Their absence from this convenience layer does not remove them from
the language or make them executable in an existing native profile.

The focused check is `python -m unittest tests.test_policy_typed`. When mypy is
available in that Python environment, it additionally type-checks the facade and
positive fixture under `--strict --follow-imports=silent`, then checks the exact
line/error-category census of 17 intentionally invalid uses. Imported types are
analyzed; they are not skipped or replaced with `Any`. Without mypy, that one
static-tooling test is explicitly skipped while the runtime checks still run.
