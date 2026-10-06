# Bounded operational policy v0.1

This experimental profile makes a declared subset of the rich policy language
executable as an OCaml reference model. Its input is the original frozen
`biocompiler.policy.v0.1` document plus an explicit, versioned operational
definition bundle. Its output is a checked behavior representation and, when
requested, a bounded trace and requirement ledger. It does not select molecular
implementations, establish target feasibility, emit RNA or grant human-use
admission. Source implementation and hosted acceptance are separate milestones.

The starting dependency is PR88 at
`88421d068ebc8437d6d0d4fa1a1bfdb32f150883`, verified pushed and still open on
2026-10-05 Pacific. This development dependency is not a release receipt. The
separate `codex/bounded-policy-execution` branch owns this increment. PR85, PR87,
PR88 and their validation owners retain their existing responsibilities.

## Operational authority and admission

The descriptor envelope is closed:

```json
{
  "schema_version": "biocompiler.policy_operational_definitions.v0.1",
  "profile": "biocompiler.policy_operational.v0.1",
  "definitions": [
    {"definition": {"$type": "DefinitionRef", "id": "supplied.id", "version": "1", "digest": "<full SHA-256>"},
     "semantics": "effect.abstract_attempt.v1"}
  ]
}
```

Each descriptor must resolve the complete identity of a definition in the
original source bundle. Missing, duplicate, conflicting, stale and unused
interpretations fail admission. Operation names, definition prose, Python
callbacks and capability labels cannot supply executable meaning. Existing
source checking runs again at admission and correspondence checking.

| Descriptor | Operational meaning |
| --- | --- |
| `encounter.explicit.v1` | Explicit concrete encounter and target bindings, with timeline start/end/reset events. |
| `observation.external_evidence.v1` | Typed, timestamped supplied evidence with distinct availability and observation times, exact freshness and invalidity status. |
| `effect.abstract_attempt.v1` | Abstract request occurrence with executor/subject/encounter identity and a fresh attempt identity. |
| `lifecycle.correlated_feedback.v1` | Matching completion/failure feedback and declared exact timeout. |
| `capability.deferred.v1` | Retain an interface/capability requirement without assessing its target implementation. |

Definition clauses without operational interpretation block admission. All
source assumptions and requirements remain visible, including unsupported proof
forms. An admitted abstract operation does not establish the capability of a
cell, chassis, environment or supplied molecular implementation.

Abstract-effect formal parameters are signatures in this profile: selection is
`fixed`, and `value`, `lower` and `upper` are null. Actual call arguments retain
their own typed expressions. Formal defaults, design/measured/uncertain selection
and refinements have no executable interpretation here and reject before
lowering, even if the supplied actual argument is fixed. Generic source
authoring can still represent those fields for future profiles.

## Checked behavior representation

The dedicated behavior profile is separate from legacy Behavior v0.1/v0.2. Each
instruction carries its opcode, declaration identity, source path and complete
source operands. It retains the full source artifact, ordered declaration and
requirement ledgers, source spans, exact descriptor bundle, assumptions and
unresolved obligations. The decoder produces separate typed execution records.
The first producer performs no optimization or declaration elimination.

`Policy_admission.t` is opaque; behavior records are private and created through
the domain decoder. `Policy_lowering` consumes admitted source. The separately
linked `Policy_correspondence` checker reconstructs every expected instruction
operand from the original external source. It does not import the producer.
Removing, reordering or changing an instruction, source span or obligation fails
checking even if the candidate's own fingerprints are recomputed. The standalone
Verify executable cannot compile a policy.

Shared trusted primitives are closed data decoding, exact arithmetic, hashing
and typed representations. Fresh replay repeats the source checker,
correspondence checker and reference executor; it is not a second independently
implemented execution semantics or a candidate molecular realization check.

## Executable subset

The initial subset admits one executor role and one exact shared logical or
availability clock. Each concrete executor has its own nominal identity. Multiple
distinct instances of declared encounters bind concrete target identities.
Executor, subject, encounter, event and effect-attempt identities occupy distinct
roles; equal observation values never establish identity.

Supported predicates use Strong Kleene truth, exact integer/quantity comparison,
literal values, observations, fixed parameters and finite scoped state. Missing,
stale, invalid and conflicting evidence remain distinct; unavailable evidence
evaluates to unknown. Malformed supplied values are errors. `rising` requires an
observed false-to-true edge; initial true or unknown-to-true is not a rising edge.

State is scoped by declaration and concrete executor or encounter, with explicit
finite capacity, initialization and matching lifetime. Assignments read the same
pre-update state and commit atomically. Rules and machines use explicit exclusive
or priority arbitration with deterministic tie and write-conflict policies.
Declaration order grants no implicit priority. A machine retains the effect
attempt it started when awaiting its correlated feedback.

Each effect request creates a fresh attempt. Its `requested` event is emitted
before its `initiated` event, with consecutive creation identities in that
order. Both belong to the same atomic commit microstep. Completion/failure feedback must
match attempt, effect, executor, subject and encounter. Continuous authorization
retains the initiating guard and its binding environment. This subset admits
explicit `on_loss=continue` and `on_unknown=continue|defer`; neither causes an
implicit stop. Cancellation, stop requests, cessation guarantees and reversal
remain unsupported. Reset/end invalidates live encounter state and attempts.

Reachable messaging, quantification, complex spatial relations, inheritance,
sampled integration, custom calls, continuous-coverage claims, multi-observation
coherence groups, contract-defined
arbitration and unimplemented lifecycle behavior fail admission. Unsupported
requirements remain in the complete obligation ledger rather than disappearing.

Requirement monitoring admits only `requested`, `initiated`, `completed`,
`failed` and `timed_out` effect phases. `outcome`, cancellation requests,
cancellation acknowledgment and cessation remain unsupported even when they are
source-valid declarations. Every non-null original condition, trigger and response
must have an executable decoded expression; an unsupported expression is never
treated as an absent condition or silently replaced with true.

An effect-triggered progress obligation retains that exact attempt. An event
response is therefore supported only for a lifecycle event of the same effect;
cross-effect event responses and observation-update responses need a separately
specified correlation rule. They report `unsupported`, rather than monitoring an
impossible match and reporting failure. Effect-triggered truth responses and
observation/rising-triggered event responses retain their existing semantics.

## Timeline and deterministic bounds

Timeline profile `biocompiler.policy_timeline.v0.1` has exactly `profile`,
`executor`, `horizon`, `encounters`, `observations`, `feedback` and `bounds`.
Times are finite exact decimal strings in the source clock's base-unit domain,
aligned to its positive resolution. A row records both `observed_at` and
`available_at`; future or malformed evidence cannot be silently coerced.

The frozen example in
[`policy_operational_v01.json`](../core/test/data/policy_operational_v01.json)
shows the complete wire contract. Candidate ingress separately limits the complete duplicated IR to 8 MiB, depth
64 and 400,000 visited keys/values before decoding. Timeline ingress retains the
2 MiB/depth-64/100,000-node source-data limits. Bounds explicitly limit ticks, inputs,
encounters, attempts, charged work, trace items and same-time microsteps.
Exhaustion is an error, never proof of infeasibility or a successful partial trace.

Every aligned clock tick through the horizon runs, even without new observations.
At a tick, encounter end/reset precedes the atomic observation batch; feedback
precedes equal-time timeout, so completion at its deadline succeeds. State reset
predicates read current freshness-aware evidence and a shared pre-reset state
snapshot; their initial values commit together once per tick. Continuous
authorization is then refreshed against that state and current evidence. Rules
and transitions settle under the declared arbitration and work bound. Requirement deadlines are
checked after settling, allowing a matching response exactly at the deadline.

Safety samples settled tick states, rather than intermediate microsteps. Unknown
truth can be stored or passed as an abstract typed parameter under a true guard;
unavailable values defer the entire atomic activation. Truth-valued progress
responses with unknown coverage remain unknown at their deadline. Missing event
responses fail only under the explicit complete supplied-event timeline contract.

Safety and progress results are conditional on the supplied finite timeline and
explicit assumptions. Missing coverage and unsupported forms stay unresolved.
Untriggered progress cannot pass through inactivity. No finite supplied history
establishes universal satisfaction, candidate implementation behavior or
biological function.

Requirement horizon coverage uses exact rational comparison independently of
scheduler tick allocation. A large retained horizon remains incomplete or
unsupported as appropriate; it does not overflow an integer scheduler merely
while reporting the original obligation. Timeline and effect/deadline scheduling
retain their separate explicit bounds.

## Explicit native operations

The negotiated `policy_operational` profile exposes `check-policy-lowering`,
`execute-policy` and `replay-policy-execution` through Core and Verify. Core also
advertises `policy_operational_producer` with `compile-policy`. All operations
take original external `document` and `definitions`; checking adds `candidate`,
execution adds `timeline`, and replay also adds the complete retained `report`.

The Python `OperationalPolicyClient` and `policy.operational` bridge only encode,
negotiate and check transport identity/shape. CLI entry points are
`policy compile-native`, `check-lowering-native`, `execute-native` and
`replay-execution-native`. Each requires explicit executable selection and exact
definition authority. Native rejection, incompatibility or timeout never falls
back to Python semantics. Reports keep `artifact=withheld`,
`target_status=unassessed` and `realization=unassessed`.

PR88 `assess-policy` and `replay-policy-assessment` retain their original profile
and source-only statuses, including `semantic_status=unresolved` and
`lowering=unsupported`. Operational success in the new profile does not alter
the meaning of an existing assessment.

## Validation and remaining boundaries

Native literal and mutation suites run only on hosted CI. They cover external
source authority, complete correspondence, descriptor failures, scoped evidence,
atomic state, arbitration, repeated attempts, correlated feedback, reset/end and
silent-time expiry. Installed campaigns run both binaries and the CLI outside
the checkout with Python semantic authorities forbidden. Four-slot comparison
requires all Linux x86_64/macOS arm64 and Python 3.11/3.14 receipts, exact tested
source/run/attempt and actual binary digests, and identical complete results.
These additive checks retain all existing native and release gates.

Deployment binding, supplied realization reconstruction, source-to-material
correspondence, RNA emission, rich-policy Studio, conversational review and
production cutover remain subsequent milestones. The preserved reference-package
route already has source implementations; this increment does not recreate it
or claim its pending compatibility and hosted acceptance work.


Operational occurrence coordinates have the canonical `/document` root. The
optional diagnostic prefix used while decoding a source record cannot alter
lowered instruction paths or independent correspondence. Admission redecodes the
same complete original source under this coordinate root; authored `source_map`,
provenance and every source field remain byte-identical. Native metamorphic tests
compare direct, `/document`, and `/payload/document` ingress.
