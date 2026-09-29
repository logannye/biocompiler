# Behavior semantics v0.1

This document defines the first abstract execution profile below the Python authoring API. It evaluates specified behavior against supplied input histories; it is not a biological simulator. The authoring language remains broader than this profile. Unsupported constructs produce source-linked diagnostics, never a silently partial executable.

## Identity, observations and time

An evaluation represents one engineered cell of a selected role. Each session has independent cell-local state. Inputs are complete snapshots at strictly increasing nonnegative times, starting at zero; values are piecewise constant between snapshots. Times and scalar values use the declared canonical units (seconds for time). Inputs with the same timestamp must be combined into one snapshot, so simultaneous observations are atomic.

Contact observations are keyed by stable contacted-object identities. A compound contact condition is evaluated for each object before existential aggregation. A and B on different objects do not satisfy A AND B. Cell-local actions aggregate the complete guard existentially and activate once, regardless of how many contacts qualify; condition-triggered local impulses/pulses use the onset of that aggregate condition. Contact-targeted or contact-valued actions retain one request per binding. Local event actions coalesce simultaneous qualifying bindings; memory setting retains per-binding onset semantics. Temporal history is maintained per object and contact episode; disappearance clears that object's temporal histories and contact-bound pulses. A cell-local pulse already triggered by a contact persists until its own deadline. Reappearance starts a new episode. Cell-local memory survives contact disappearance. Non-contact observations are cell-local and broadcast into contact-bound expressions when combined.

Qualitative predicates (present/high/low) are explicitly supplied Boolean observations. No arbitrary numeric threshold is inferred. Numeric expressions use canonical scalar values and declared dimensions. Missing required observations, wrong types and non-finite values are errors, not false/zero defaults.

## Concurrent execution

At a timestamp, new external inputs and due timers are considered together. Automatic memory controls settle first in causal dependency order, before rule effects or event emission. Each producer memory is resolved before evaluating a consumer memory's setting/reset conditions or onset history; finite state stays fixed throughout this phase. The structural graph is acyclic, so no provisional latch updates are needed. Settled memory is published to rules only after this phase completes. Rules then observe settled memory and a shared pre-update finite state. This prevents a stale memory value from producing a reaction exactly at reset or expiry; a simultaneous refresh does not introduce a false/true glitch. All enabled assignments commit atomically: identical typed assignments coalesce; conflicting assignments to the same state are errors. Python declaration order is not priority.

After a finite-state change, another same-time microstep settles memory controls and propagates rule changes until state is stable. Rising events are emitted once per transition, not once per polling step. A bounded microstep limit detects nonconvergent behavior rather than silently choosing an order. Results distinguish ongoing active actions from instantaneous reactions. Actions describe requested outputs; they do not mutate the external input history or simulate biological consequences.

`when(condition)` enables ongoing actions while the condition holds; instantaneous actions and pulses trigger on condition onset. `on(event)` triggers instantaneous actions or explicit-duration pulses. An ongoing event action without a duration remains an unresolved design choice and cannot execute in this profile. Independent ongoing requests remain individually traceable; the evaluator does not invent a physical arbitration law for distinct outputs.

Finite-state predicates observe the shared pre-update state in each microstep. Initial state is declared explicitly. State assignments in enabled condition rules assert their value; idempotent repeated assignments do not create new events.

## Temporal operators

History begins at initialization: there is no inferred prehistory. An initially true condition is a rising event. `held_for(T)` becomes true after a full uninterrupted interval of length T, per binding. `recently(within=T)` includes the present and stays true for T after the condition ceases; the expiry endpoint is excluded. `followed_by` emits on the second event when a first event occurred strictly earlier within the inclusive window; coincident first and second events alone do not qualify. First events are non-consuming and may justify multiple later second events in the window.

Memory is initially false and is set by onsets of its setting condition. Any qualifying contact-binding onset can set/refresh cell-local memory. Reset is level-sensitive and dominates setting and expiry at the same time. Without reset, a new setting onset wins over old expiry. Duration is measured from the latest setting onset; a continuously true setting condition does not refresh it. Memory controls become visible before rule effects in the same microstep, and dependent memories consume the settled producer value. Expiry/reset cannot leave an irreversible latch in a downstream memory through a provisional intermediate value.

Pulses occupy [trigger, trigger + duration). A repeated trigger extends expiry from the latest trigger; it does not create stacked copies. Condition-bound pulses trigger on onset, not repeatedly while true. Timers are processed at their actual deadlines even when the input history has no snapshot at that time. A simultaneous external input takes effect before evaluating a due timer at that timestamp. A requested evaluation horizon truncates execution explicitly. By default the horizon is the final input snapshot; `until` may extend it, holding that last snapshot constant. The evaluator emits a settled frame at each input change, internal deadline and final horizon.

## Supported first slice and obligations

The initial slice covers roles/scopes, scalar observations and arithmetic/comparisons, qualitative/Boolean conditions, temporal guards/events, memory, finite state, rules, abstract output requests and explicit pulses. Durations must be positive bound design-time constants. Signatures preserve their source correspondence while forwarding the expression they describe.

Continuous integration, curve controllers, multicell transport/spatial models and unresolved therapeutic goals require additional execution profiles or semantic refinements. Reject them explicitly in lowering. Preserve the original intent fingerprint, source links and requirement identities; normalized policy choices are recorded in the Behavior IR. Validate imported IR against this execution profile as well as its structural schema.

A reference evaluator provides a semantics oracle for subsequent compiler work. It does not certify molecular realizability. Future checks compare mechanism-model observables to these contracts, with explicit tolerances, context and observation maps. See [toolchain contracts](toolchain-contracts.md).

## Python workflow

```python
import cellweave as cw

therapy = cw.Therapy("abstract_dwell")
cell = therapy.engineer("observer", cell_type="abstract_cell")
signal = cell.environment.signal("A")
cell.when(signal.present().held_for(cw.Duration(2, unit="s"))).do(
    cell.report("dwell_complete")
)
intent = therapy.freeze()
behavior = cw.lower_to_behavior(intent)
assert cw.verify_lowering(intent, behavior).passed
restored = cw.BehaviorProgram.from_json(behavior.to_json())
assert restored.fingerprint == behavior.fingerprint

result = cw.evaluate(
    restored,
    [cw.InputFrame(0, signals={signal.node_id: cw.SignalSample(present=True)})],
    until=3,
)
assert [frame.time for frame in result.frames if frame.reactions] == [2]
```

`lower_to_behavior(intent, parameters={...})` accepts typed scalar design-parameter overrides, validates their dimensions, and records the resolved bindings. Unbound parameters and unsupported operations fail explicitly. `verify_lowering(intent, behavior)` returns a `LoweringReport` with exact correspondence checks, or raises `LoweringVerificationError`. This checks the pass's supported transformation; it is not a general formal proof of biological refinement.

`evaluate(behavior, history, role=None, until=None, max_microsteps=1000)` accepts a role name or role-node ID; selection is required when a program has multiple roles. Each call creates a fresh single-cell session. Histories use complete snapshots: omitted contacts disappear, and required missing observations cause errors. A numeric sample is a canonical scalar (for example seconds or the type's canonical concentration unit); qualitative bands are separate Boolean fields on `SignalSample`. Signal bindings use retained intent node IDs, available from each authored signal's `node_id`.

`EvaluationResult.frames` contains settled snapshots at external changes, internal deadlines and the horizon. A frame's `actions` are ongoing requests; `reactions` are instantaneous requests; `events` are emitted event occurrences; `states` and `memories` are post-settlement values keyed by declaration ID. A frame's `microsteps` records convergence work. `result.to_json()` serializes the trace for inspection. Source locations and requirement IDs accompany requested actions/events. Each action request retains both its primitive `action_id` and installed `specification_id` (the pulse wrapper where applicable). Results record the behavior fingerprint, original intent fingerprint and execution profile. The [complete example](../examples/behavior_trace.py) adds contact identity, memory, state transitions and a pulse.

Behavior documents can also be inspected using `cellweave inspect behavior.json` or `cellweave inspect behavior.json --json`. Both parsers reject malformed or unsupported schemas. Requirement IDs are stable within a frozen source snapshot, not guaranteed edit-stable identities across source refactoring. The source fingerprint distinguishes graphs, and source locations are excluded from structural fingerprints.
