# Bounded staged-regimen execution contract

Status: implementation checkpoint; native, material and installed acceptance are
not established by this document. The development plan tracks validation.

This profile extends the existing Python policy language through independent
implementation checking and exact component/material contracts. It is a finite
compiler profile, not an arbitrary therapeutic-program realization claim.

## Source meaning

The first complete family contains one executor, one exact clock, one encounter
scope with two independently represented concrete slots, one truth observation,
and one five-state machine. Seven source transitions connect an initial state,
two active stages, a completed terminal state and a failed terminal state. The
two effect declarations have distinct identities and attempt banks. Both use
the same fixed product parameter. The source declares failure and timeout
transitions explicitly; lowering cannot add them on the user's behalf.

`patterns.ordered_effects` infers encounter or executor lifetime from its scope
unless the author supplies a lifetime. It now emits both failure and timeout
transitions. `handoff_when` can specify the guard at the first completion event;
omitting it reuses the initial permission expression. Python control flow runs
only during document construction. It is not cellular control flow.

A transition observes its source state, the current event and its guard at that
microstep. Only a known-true guard enables it. False or unknown is inactive and
does not queue a retry. Completing an attempt while the handoff guard is false
can leave the machine in its first state permanently. An explicit universal
completion requirement therefore needs an adequate domain premise and cannot
be inferred from this helper. A timeout of an already-completed attempt does
not provide a second chance at handoff.

## Independent primitive execution

The new primitive and observable profiles are respectively
`biocompiler.policy_staged_primitives.v0.1` and
`biocompiler.policy_staged_observables.v0.1`. Existing truth-only model bodies and
profiles keep their original interpretation. New stateful primitives require
encounter-slot replication and cannot enter a legacy graph under an old profile.

| Primitive | Configuration and responsibility |
| --- | --- |
| `machine_bank` | Finite ordered state labels, initial state, terminal states, writer count and retained-attempt capacity. Stores one state and a bounded ordered correlation list per active slot/generation. |
| `transition_gate` | Explicit source state and unbound or retained-attempt event correlation. Reads a machine snapshot, event batch and truth guard; preserves original cause identities. |
| `transition_commit` | Explicit destination state, truth-write count and request count. Commits its machine write, ordinary writes and stage requests atomically. |

These primitives contain no source AST, transition table interpreter or callback
to the source runtime. The independent runtime reconstructs behavior from the
actual model instances, typed ports, wires and atomic groups. Candidate model
or source names cannot override their semantics.

On a successful transition that starts an attempt, the machine's correlation
list is replaced with the newly started attempts. A transition starting no
attempt preserves the previous list; entering a terminal state clears it. Old
attempts remain distinct in global history. Reset/end invalidates active
attempts, clears scoped state and prevents feedback from an earlier generation
from advancing a later encounter.

Capacity and resource checks precede committing the complete batch. Exhaustion
returns no successor; it cannot silently drop a request or expose a partial
state transition. Separate limits cover live attempts, retained correlations,
work, event/trace records and settling microsteps. Feedback precedes an
equal-deadline timeout under the fixed execution phase contract.

## Source correspondence

Binding schema `biocompiler.policy_implementation_binding.v0.2` adds machine and
transition anchors under `biocompiler.policy_staged_source_graph.v0.1`. It retains
all original observation and effect identities and requires exactly the
supported source topology. Every transition gate, guard, event selector, bank,
commit, arbitration lane, state label and occurrence is reconstructed against
the unchanged original document. A producer proposal is never binding authority.

The checker preserves the complete ordered state dictionary; alternate encodings
are outside this first profile. It checks initial/terminal values, source and
destination states, scope/lifetime, distinct initiators, request/authorization
routes and the entire occurrence ledger. Missing or orphan nodes/ports/wires and
unsupported declarations fail closed.

Trace correspondence checks each prefix, including machine snapshots, retained
attempt identities, machine-transition actions, attempt ownership, event causes
and tick/microstep order. Injective event/attempt correspondences are fixed at
creation. The candidate cannot select a projection that hides machine state,
suppresses a request and initiation together, or merges two encounter identities.

The original finite causal domain drives both runtimes. Enumeration retains
silence, failed feedback and stale attempts wherever the declared grammar admits
them. Resource exhaustion is incomplete exploration, not success. Required
progress is assessed by independent monitors with global nonvacuity coverage.
The generic machine obligation is discharged only within bounded machine
semantics and all explicitly declared hard requirements; the evidence states
that universal termination is not claimed.

## Composition and exact RNA

The staged assembly profile retains two components: decision and driver. The
driver owns one immutable product constant, two attempt banks and six event
selectors. Each stage has an explicit product, request, authorization, completion,
failure and timeout link. Event returns identify the actual originating bank;
there is no implicit feedback bus or request multiplexer. Reused product or
authorization output boundaries are explicit, with each receiving input and
initiating guard independently checked.

An ordered total bijection relates this supplied component union to the checked
implementation. Original carrier declarations bind every model, configuration,
replication, wire, input, boundary, group and semantic export to the supplied
material. Construction retains exact root sequences, features, chemistry,
translation and the single RNA/single ORF/single product architecture.

The deployment context accounts for finite machine-state encoding bits and
machine correlation records in addition to the existing evidence, attempts,
timers, input rows, generation counters and control-event records. New complete
record shapes include machine ownership, state writes and retained identities;
every provider capacity pins the complete record layout. Shared capacities are
summed by actual owner and scope.

Exact graph-to-material behavior remains an explicit supplied contract. The
compiler checks the conjunction of source preservation, declared requirements,
component composition, material reconstruction and deployment context. It does
not infer that premise from a nucleotide string. Compilation withholds export;
a fresh independent check must precede the paired FASTA and full manifest.

The one-product profile does not make the illustrative two-product cleanup/repair
program molecularly supported. More products, helper payloads, persistent or
executor-scoped machines, quantitative control, cancellation and queued handoff
require additional explicit profiles and complete end-to-end validation.
