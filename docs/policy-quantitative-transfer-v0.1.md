# Exact sampled conservative transfer pairs

This increment composes two quantitative states through an exact shared transfer
law. A single selected joint component contract binds both reservoirs, the source
machine, all threshold request sites and the existing exact RNA construction
path. Existing scalar and step-reservoir profiles retain their identities.

## Python interface

```python
from biocompiler import policy as p

pair = p.quantitative.SampledTransferPair(
    substance="signal", unit=p.COUNT, quantum=p.quantity("1", p.COUNT),
    source=p.quantitative.ReservoirCompartment(
        compartment="executor.source", capacity=p.quantity("2", p.COUNT),
        initial=p.quantity("2", p.COUNT)),
    destination=p.quantitative.ReservoirCompartment(
        compartment="executor.destination", capacity=p.quantity("2", p.COUNT),
        initial=p.quantity("0", p.COUNT)),
    forward=p.quantity("2", p.COUNT), reverse=p.quantity("1", p.COUNT),
    threshold=p.quantity("2", p.COUNT), sample_period=p.quantity("1", p.SECOND),
)
transitions = pair.transitions(machine, observation, effect, prefix="transfer")
quantitative = pair.bind(
    instance="control", component=selected_complete_component_pin,
    contract="transfer", machine=machine, observation=observation, effect=effect,
)
```

These frozen descriptions author ordinary source transitions and immutable wire
snapshots. Python control flow does not execute the therapeutic program. The two
compartment identities must differ. Substance, complete nominal unit and quantum
are shared; capacities, initial amounts, directional transfer bounds and the
destination threshold use exact grid quantities. Forward is positive and no
larger than source capacity; reverse is positive and no larger than destination
capacity. No unit conversion is implicit.

The full Cartesian state grid has at most sixteen states. Source amount is the
major coordinate and destination amount the minor coordinate. The machine's
ordered state labels must cover every pair, including pairs unreachable from
its declared initial total. `state_values` retains both complete quantities in
every row; it never reduces a pair to total amount alone.

## Atomic transfer semantics

For pre-sample amounts `(A, B)` and capacities `(CA, CB)`:

| Input | Actual transferred amount | Next pair |
| --- | --- | --- |
| True | `min(forward, A, CB - B)` | `(A - amount, B + amount)` |
| False | `min(reverse, B, CA - A)` | `(A + amount, B - amount)` |
| Unknown or absent update | zero | `(A, B)` |

Both quantities update from the same prestate. The actual transfer accounts for
both donor stock and recipient headroom before either amount changes. This
preserves `A + B` within an encounter generation. Debit-then-clamp and sequential
updates are not this law. Reset restores the declared pair together; conservation
is not asserted across that external initialization boundary.

An upward crossing of the destination threshold requests the selected effect.
Several joint states may cross that threshold. All sites retain the existing
shared attempt bank, per-site authorization and correlation semantics. Amount
capacity and effect-attempt capacity are distinct quantities and remain separately
checked. Unknown creates no transfer or new request; existing active attempts
retain their own lifecycle rules.

Known samples with zero actual transfer are canonical holds and have no source
transition. Every nonzero transfer has exactly one source transition with the
correct destination and effect request. The independent checker still publishes
and checks True, False and Unknown rows for every product state. This sparse
representation needs at most eighteen moving transitions for sixteen joint
states, fitting the existing transition and graph limits without changing them.
Fresh lowering still checks the actual supplied models and graph. Both independent
execution engines consume observation updates in the initial settling round;
subsequent rounds receive only newly created events. A machine cannot apply the
same sample again after its first transfer changes state.

## Original contracts and evidence

The law has schema `biocompiler.policy_sampled_transfer_pair.v0.1` and profile
`biocompiler.policy_sampled_conservative_transfer_pair.v0.1`. The native domain
uses a separate strongly typed transfer representation. It does not fill scalar
reservoir fields with placeholders.

The material request uses schema v0.11 and
`biocompiler.policy_sampled_transfer_pair_component_mrna.v0.1`; the joint local
component uses schema v0.4 and
`biocompiler.policy_transfer_pair_local_material.v0.1`. Original realization,
assembly, context and primitive profiles reuse the existing multi-site path.
The original `quantitative` envelope retains the complete law, exact component
selection and source machine/observation/effect identities.

The local contract supplies the full Cartesian state map, state/input model pins
and every crossing output boundary. Source declaration order defines request
ports; Cartesian order defines the table and local outputs. Their correspondence
is checked through transition identity. Complete output checking includes
counterfactual grid states even when the bounded history starts on a smaller
constant-total slice.

The quantitative assessment v0.3 retains exact before/after integer grid
coordinates and `transfer_quanta` on every row. Its separate conservation scope
is `accepted_samples_within_encounter_generation`; reset restores the original
pair. Failure withholds the entire table, bindings and conservation assessment.
All selected component identities, resource checks, prerequisite closure,
quantitative discharge hashes and fresh material/export checks remain required.
The material assessment is v0.7; service capability is
`policy_transfer_pair_material`. Typed material preparation selects
`transfer_pair=True` with the existing explicit finite-machine, multi-site,
named-instance and quantitative arguments.

Planning adds `transfer_pair_material` and retains all fourteen previous target
descriptors. Its plan remains diagnostic and leaves quantitative checking,
execution, requirements, resource sufficiency and exact export unresolved. The
existing named refinement vocabulary remains unchanged.

## Scope and continuation

The primary artificial fixture uses capacities two, quantum one, forward two,
reverse one, destination threshold two and initial pair `(2, 0)`. Its independent
27-row table covers all nine states. Its reachable histories exercise donor and
headroom limits, reversal, multiple crossing sites, Unknown, absent updates and
reset. A crossing from `(2, 1)` belongs to another total and is checked in the
complete table, not claimed as visited by a total-two trajectory.

The accepted relation concerns one supplied joint component contract. It does
not independently realize two separately selected reservoir components or infer
a molecular transport mechanism between them. Splitting the joint contract will
require explicit coupling, resource ownership, atomicity and transport premises.
General networks, continuous or stochastic kinetics, approximate refinement and
experimental evidence interfaces remain subsequent work. See the
[implementation checkpoint](semantic-quantitative-transfer-checkpoint-2026-10-09.md)
for current validation and its limits.
