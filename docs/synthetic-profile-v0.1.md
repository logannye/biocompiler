# Combinational synthetic generation v0.1

`biocompiler.synthetic.combinational.v0.1` automatically generates an abstract
digital mechanism from a frozen `RealizationRequest`. It is a software model
fixture, not a molecular implementation of a CAR or a prediction of cellular
effects. The existing `compile()` molecular boundary remains unavailable.

## Supported inputs and outputs

The request must explicitly select `synthetic_realization` scope, contain one
executing cell role, and declare an operating domain with a finite concurrent
contact bound and a positive minimum history horizon. The target must provide
the `synthetic_signal_graph` capability and the `abstract` compartment. All
model ports use this compartment. DNA/RNA context is retained as provenance;
this profile emits neither DNA nor RNA.

Supported guard expressions are:

- Explicit `present`, `high` and `low` Boolean observations. Generation never
  invents a threshold or derives a qualitative observation from a number.
- Scalar observations, typed literals or bound parameters and their `lt`, `le`,
  `gt`, `ge`, `eq` and `ne` comparisons in compatible dimensions.
- Boolean `and`, `or`, `not`, and signature wrappers around supported guards.

Condition-triggered `rest`, `eliminate` and `engulf` actions produce **abstract
request readouts**. Each installed action in each rule requires its own authored
response requirement: exact observable identity, units, role and scope, disjoint
closed active/inactive ranges, and activation/deactivation deadlines. Contracts
cover all installed actions. Observation maps cover exactly the domain's runtime
input fields. Other action classes and dynamic requested output laws are outside
this generation profile.

There is one deterministic implementation per supported operation. Nonempty
implementation constraints or preferences are rejected until a resolver exists.
The profile also rejects arithmetic, threshold-count conditions, temporal and
state operations, pulses, events, multi-role execution and cross-compartment
transport. Unsupported nodes retain their source identity and location in the
diagnostic; unused state declarations cannot disappear into an accepted result.

## Identity, scope and initialization

Contact snapshots use stable object identities. The generator evaluates an
entire contact-bound guard separately for each object. A cell output then uses
`any_contact` on that complete guard. Thus A and B on different objects do not
satisfy `A & B`. Contact-targeted output remains keyed to the individual object;
an object satisfying the guard cannot enable another object's response.

Cell observations broadcast into contact-bound expressions when combined with
contact observations. Cell-scoped guards can similarly enable every current
contact for a contact-targeted action. An empty contact set produces false for
an existential guard and no contact outputs. Object removal/reappearance changes
the current snapshot; this profile has no retained state or timers.

All operators settle at each atomic input timestamp, including startup, under
right-continuous piecewise-constant semantics. The model has zero transition
delay because it is a stateless digital fixture. This is not an empirical speed
guarantee. The generator preserves the authored contract deadlines unchanged.
`held_for` is never replaced with the synthetic runner's inertial `delay`:
those operators have different semantics.

The generator selects the lower endpoint of each authored closed response band
as its deterministic numeric witness. That value is a recorded compiler choice,
not a user-requested exact level or a biological measurement. Constants preserve
the endpoint's typed literal and units. No response band or deadline is inferred
from an action name.

## Artifacts, catalog and acceptance

```python
from biocompiler.synthesis.synthetic import generate_synthetic, check_synthetic_candidate

candidate = generate_synthetic(realization_request)
result = check_synthetic_candidate(realization_request, candidate, history, until=7)
```

The immutable `SyntheticCandidate` retains the realization request identity,
mechanism, explicit observation map, full source ancestry, original Behavior
requirement IDs, response requirement IDs on model nodes, exact component locks
and the generator configuration. Strict JSON round trips reject unknown schemas.
Semantic identities contain no filesystem locations or timestamps; source IDs
resolve through the frozen request's Behavior artifact.

`registry.synthetic.SYNTHETIC_CATALOG` supplies offline, versioned definitions of
input, constant, Boolean, comparison, selection, existential aggregation and
output operators. Each record identifies its runner, interface semantics,
applicable profile, assumptions and digital guarantees. Each generated node is
locked to its component version and content hash. Its concrete typed ports carry
meaning, units, role, contact scope and compartment, and Mechanism IR validates
the graph's edges. The catalog deliberately has no delay component.

This is the synthetic subset of component work. General producer/consumer domain
inclusion, external providers, biological capacities, shared resources and
sequence-reference components require later M4 work. Unmeasured biological
capacity is not encoded as an unlimited resource.

Generation does not accept the candidate. Acceptance first validates the request's
supported profile, pinned components and deterministic provenance policy, then
uses the existing independent mechanism runner and realization checker. The
runner neither imports nor calls the Behavior evaluator. Provenance checking
does not discharge behavioral obligations; candidate edges and values must pass
the independent finite-history check.

The acceptance wrapper requires both active and inactive deadlines to be
exercised for every response. Empty, incomplete, out-of-domain or unexercised
histories produce `unknown`; unsupported requests cannot pass through vacuous
histories. Component/request mismatches and observed response violations fail.
Evidence retains the supplied history/horizon, model/checker identities, the
wrapper's version and coverage policy, frozen request, candidate, configuration
and catalog identities. All results remain conditional on that finite history.

## Validation bounds

`tests/test_synthetic_generation.py` checks generated candidates, source/lock
integrity, canonical round trips, startup-active input, contact loss/reappearance,
scalar comparisons, and Boolean negation. Mutations test silence, late responses
at exact deadlines, aggregation before conjunction, broadcasting one object's
response to another, and changed output scope. Unsupported temporal/state
operators are tested explicitly, including a forged candidate over an unsupported
request. The public example now generates its candidate automatically.

One bounded exhaustive regression enumerates **256** ordered transitions among
the **16** Boolean states of two observations on each of two fixed contact
objects. Snapshots occur at 0 and 2 seconds, followed by a fixed all-active
snapshot at 4 and all-inactive snapshot at 6, checked through 7 seconds. That
suffix exercises both response states with 0.5-second deadlines. These bounds
cover this finite Boolean transition test, not every history, continuous input,
contact lifecycle or biological operating domain.

## Software-use admission

Synthetic candidate schema v0.2 fixes `intended_use=software_test` and `human_therapeutic_admission=not_admitted`. The generator and independent realization checker reject human implementation contexts under the [M10.5 admission policy](human-admission-v0.1.md). Exact request identities and a passing finite history cannot promote a software model to a human implementation. Policy identity participates in verification and pipeline dependencies.
