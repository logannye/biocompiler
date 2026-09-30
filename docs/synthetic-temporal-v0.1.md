# Temporal synthetic generation v0.1

`biocompiler.synthetic.temporal.v0.1` generates an executable digital mechanism
for sustained conditions, onset-triggered pulses and resettable memory. It is an
explicit extension of the [combinational profile](synthetic-profile-v0.1.md).
The source [Behavior semantics](behavior-semantics-v0.1.md) remain unchanged.
The candidate runner executes its own state machines without invoking the
Behavior evaluator. Neither execution engine is a biological simulator.

```python
import biocompiler as bc

config = bc.SyntheticGeneratorConfig(profile_version=bc.TEMPORAL_PROFILE_VERSION)
build = bc.run_synthetic_pipeline(request, history, until=9, config=config)
```

The [complete example](../examples/temporal_pipeline.py) constructs `request` and
`history`, combining two-contact sustained input, cell/contact pulses and bounded
memory with reset. All outputs use explicit abstract readout contracts. Generated
mechanisms emit no nucleotide sequence and cannot grant human admission.

## Supported source operations

The profile adds `held_for`, `became_true`, `action.pulse`, `memory` and
`memory.is_set` to the combinational expressions and abstract ongoing actions.
Both condition-triggered and event-triggered pulses are supported; event rules
require explicit-duration pulses. Memory may be permanent until reset or have a
positive declared expiry duration. Durations are bound design-time constants,
not inferred from observations or invented during lowering.

`recently`, `followed_by`, arbitrary finite-state assignments, arithmetic beyond
the existing comparisons, quantitative secretion laws, multi-role execution and
transport remain unsupported. Unsupported operations produce source-linked
diagnostics. The default configuration remains the combinational profile and
continues to reject temporal requests.

## Independent mechanism operators

| Operator | Digital meaning |
| --- | --- |
| `held_for` | Starts an independent timer when the input becomes true. Output becomes true at the exact deadline if uninterrupted, and false immediately when the input falls. |
| `onset` | Internal event on a false-to-true transition, including an initially true input. It may feed only pulse/memory triggers or event aggregation, never a public continuous readout. |
| `pulse` | An event starts or refreshes one active interval `[trigger, trigger + duration)`. Repeated triggers extend its expiry; a trigger at the previous expiry wins. |
| `memory` | Initially false cell-local latch with an event-set input and a level-reset input. Reset dominates setting and expiry; otherwise a new setting event wins over old expiry. |

The existing inertial `delay` still delays both edges and cancels pending changes.
Its meaning is unchanged; it is not in either generation catalog and cannot
implement `held_for`.

The runner processes external snapshots before due timers at the same timestamp
and schedules internal deadlines between snapshots. There is no inferred
prehistory. Non-finite or non-advancing deadlines are rejected. Memory dependencies
settle in acyclic causal order, so downstream controls see settled upstream
values rather than provisional state at reset/expiry.

## Contact and trigger identity

A contact-bound sustained condition has one timer per object and contact episode.
Disappearance clears that contact's timer, onset history and contact pulse;
reappearance starts fresh. A cell-scoped timer remains cell-scoped when its value
is combined with a contact condition. New contacts can therefore observe an
already-qualified cell signal without inventing per-contact prehistory.

A condition-triggered cell pulse detects onset **after** aggregating the complete
guard over contacts. Adding a second qualifying contact does not retrigger it
while the first remains qualified. An event-triggered cell pulse aggregates
per-contact events, so a second contact's onset can retrigger it. Simultaneous
events coalesce into one pulse with one expiry.

Memory setting likewise detects each binding's onset before aggregation. A new
qualifying contact can refresh cell memory while another remains true. Reset
aggregates the level of its condition. Cell memory and cell pulses persist after
the triggering contact disappears; their own reset/expiry rules still apply.

## Authority, versions and limits

The selected profile pins its own catalog. Generation records typed ports,
source/requirement ancestry, observation maps and component versions. Acceptance
checks that provenance and independently executes both models against unchanged
caller contracts. Active and inactive coverage are still required; sparse or
unexercised cases remain UNKNOWN. Passing one history does not prove all histories.

This change uses Mechanism IR and runner `v0.2`, generator `v0.3`, acceptance
`v0.4`, catalog `v0.2`, generator-config schema `v0.2` and candidate schema `v0.3`.
Previously saved artifacts with obsolete schemas, models or catalog pins must be
regenerated and rechecked; changing their version labels is not migration.

The separate Mechanism-to-Components linker currently has a stateless snapshot
timing contract and explicitly rejects temporal profiles. These builds complete
the `synthetic_realization` scope at Mechanism IR. Full dynamic composition and
molecular realization require their own profiles.

## Verification

The new model tests specify literal expected trajectories, independently of the
Behavior evaluator and generator. Generation tests reuse the pre-existing literal
contact, memory and pulse timelines and add rapid fall/re-rise, startup, exact
deadlines, independent contact dwell, cell-timer broadcast, per-contact memory
refresh and reset/expiry priority. Bounded digital enumeration reports its exact
input/time space; it does not imply universal or biological verification.

Mutants deliberately substitute inertial delay for sustained qualification and
alter timing or contact aggregation; the intended response check must detect the
change. The [synthetic build package](synthetic-build-v0.1.md) retains these
software-use boundaries when reconstructed offline.
