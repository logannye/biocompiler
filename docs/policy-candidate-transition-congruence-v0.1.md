# Checked candidate transition congruence

Design checkpoint: 2026-10-08. This is the first bounded assurance increment for
[priority 5](core-architecture-session-priorities-2026-10-08.md). Implementation
and hosted validation are in progress; this document grants no acceptance.

## Measured starting point

Prerequisite development run `37798264346`, attempt 1, at
`a34ebd6bc557b52e9e253e8fe7e4fbce8ae1f9a4` completed on Linux x86-64 and passed
an independent inert artifact audit. Each of its two original-bound witnesses
explored nine histories, 47 transitions and 48 prefixes. The receipts recorded:

| Logical work | Witness A | Witness B |
| --- | ---: | ---: |
| Complete check | 8,892,506 | 9,402,101 |
| Source execution | 1,377,877 | 1,404,224 |
| Candidate execution | 3,301,742 | 3,558,496 |
| Requirement monitor | 821,380 | 883,724 |

These are charged logical work units, not CPU measurements. The recorded
115.327 seconds covers the entire 26-observation SDK campaign. It cannot be
attributed to a single preservation check or used to predict a speedup.
That run's native prerequisite service suite took 24.224 seconds and its
preservation suite took 2.019 seconds; neither receipt separates candidate CPU.
The new hosted comparison must measure execution phases and proof bookkeeping
separately, retain both enabled and disabled results, and report unsuccessful
sharing opportunities as well as successful ones.

## Narrow rule

Let `step(s, i, g)` be the existing deterministic candidate transition, where
`s` is the complete immutable runtime state, `i` is the complete input batch,
and `g` contains both per-step resource guards. A successful fresh execution
produces `(s', f)`. Within that same preservation invocation, a private witness
may supply `(s', f)` again only after checking equality of every input to the
transition. A matching digest alone is insufficient.

Equality retains the implementation plan and original environment/limits;
next tick; slot identity, activity, generation and generation start;
registers, evidence, freshness and occurrence identities; rising-edge memory;
machine state and lineage; every retained attempt and causal identity;
allocation/event sequence counters; cumulative work and retained counts; and
both complete sets of consumed observation and feedback identities. The batch
retains exact order, subjects, executor, input/attempt/slot identities,
timestamps, outcomes and lifecycle operations. No renaming, history
normalization, removal of old attempts, or replacement of unknown reasons is
authorized.

The justification is functional congruence: the transition reads only those
immutable inputs, creates a fresh local worker, and returns a successor/frame
or raises a diagnostic. Equal complete inputs yield equal outputs and work
deltas. This argument depends on the current implementation's determinism and
complete state representation; it is not a machine-checked soundness theorem.
Changes that introduce an external read, hidden mutable state, a new state
field, or new resource behavior invalidate this review obligation.

Only successful actual executions can create witnesses. Failures are executed
fresh. Witnesses cannot be decoded, loaded from prior runs, supplied by a
producer, or transferred between verification invocations. Storage and equality
effort must have explicit finite auxiliary bounds; exceeding those bounds
falls back to ordinary fresh execution. No auxiliary bound may shrink the
original semantic input domain or turn an incomplete check into acceptance.

The proposed fixed auxiliary bounds are 32 entries, 8 MiB of retained canonical
data and 64 * 1024 * 1024 auxiliary accounting units. The byte footprint measures
canonical data, not process memory or OCaml heap use. The entry count also bounds
table overhead. Key construction needs a preflight bound before encoding, and
the original immutable plan is owned by physical identity. Complete canonical
state/input/guard bytes are compared directly; a hash cannot establish equality.
The auxiliary meter charges structural allowances plus encoded and equality
bytes. It is not a count or conservative bound of every CPU operation or byte
visit: canonical object-key sorting is bounded by the finite key/data limits
but is not separately charged by this counter. Actual candidate-phase CPU
includes this bookkeeping. These details remain subject to hosted measurements.

## Preservation boundary

The source evaluator still checks every original prefix. Domain enumeration,
source/candidate correspondence, requirement monitors, original obligations,
first witnesses, coverage, publication and logical resource charges remain
unchanged. The shared candidate transition incurs the same logical execution
charge as its fresh counterpart, including the same cumulative successor
usage. Auxiliary proof bookkeeping is measured separately from logical
execution work.

This rule reduces repeated candidate execution where exact runtime states
converge. It does not prune original histories, infer independence between
encounters, reuse requirement verdicts, or prove arbitrary component
interactions. The complete source/material/context/export acceptance chain
continues to require fresh checking. Supplied biological contracts remain
premises, and empirical therapeutic claims remain outside this rule.

## Required distinguishing evidence

- A literal convergence witness must reach equal complete candidate states
  through distinct histories and avoid at least one subsequent execution.
- Enabled and disabled checking must have identical canonical reports, private
  acceptance decisions, failure prefixes, resource charges and publication.
- Altering any future-read identity, observation reason, attempt, generation,
  limit, per-step guard or input order must prevent an unjustified hit.
- Fresh calls and changed original authority must start with empty proof state.
- Exhausting proof storage or equality effort must recover the ordinary result;
  exhausting original execution/publication resources must remain incomplete.
- Hosted measurements must report fresh/shared transitions, bounded proof cost,
  phase CPU time, whole-command wall time and source/run identity. A passing
  equivalence comparison alone is not evidence of a speed improvement.

The first increment remains useful even if measurements favor disabling sharing
by default. Broader assume-guarantee verification and reducing the original
domain require separately justified rules and independent witnesses.

The diagnostic native API is `Policy_preservation_check.check_measured` with an
explicit `share_candidate_transitions` argument and a caller-supplied diagnostic
clock. Production checker modules never access a process clock; timing values
never select a semantic branch, and a clock exception propagates without a
returned checked result. It returns the ordinary checked
result plus separate measurements. Existing ordinary entry points currently
retain unshared execution pending measurement; no public wire schema or SDK
assurance claim changes. Measurements separate source steps, candidate steps
(including congruence bookkeeping), correspondence, monitor steps and explicit
projection encoding. Initialization, terminal aggregation and publication remain
within total CPU time but outside those phase counters. Whole-command wall time
and native-host provenance are recorded by the hosted witness harness.
