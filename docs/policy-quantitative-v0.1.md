# Exact sampled reservoir authoring v0.1

`policy.quantitative.SampledReservoir` describes a bounded sampled amount. For a
known Boolean sample `u`, the next amount is
`clamp(q + 2 * quantum * u - quantum, 0, capacity)`. A True sample adds one quantum;
a False sample subtracts one quantum. Clamping occurs after production and
consumption are combined, so True at capacity stays at capacity.

Unknown input and absent updates both hold the reservoir state and create no new
effect request. Unknown does not itself cancel an already active effect: the
original effect lifecycle and its reservation rules still apply. Only an upward
crossing from below the threshold to at least the threshold requests the selected
effect. Falling below it and crossing again can request another attempt. Encounter
reset restores the declared initial amount.

This is an exact discrete amount law under a supplied component contract. Quantum
means **amount per accepted sample**, not a continuous production rate. No sample
arrival guarantee, stochastic biochemical dynamics, concentration model,
pharmacokinetics, or empirical efficacy is inferred.

## Python authoring

```python
from biocompiler import policy as p

law = p.quantitative.SampledReservoir(
    substance="signal", compartment="executor.reservoir", unit=p.COUNT,
    quantum=p.quantity("0.5", p.COUNT),
    capacity=p.quantity("1.5", p.COUNT),
    threshold=p.quantity("1", p.COUNT),
    initial=p.quantity("0", p.COUNT),
    sample_period=p.quantity("1", p.SECOND),
)
assert [value.amount for value in law.levels] == ["0", "0.5", "1", "1.5"]

# Existing source declarations: an encounter machine with these four states,
# initial q0, no terminal states, and exclusive reject-on-conflict arbitration;
# one truth observation with one-period freshness; one same-subject effect.
transitions = law.transitions(machine, observation, effect, prefix="reservoir")
quantitative = law.bind(
    instance="control", component=selected_complete_component_pin,
    contract="reservoir", machine=machine, observation=observation, effect=effect,
)
```

`transitions` returns ordinary policy `Transition` records with explicit
`Observation.updated` triggers, True/False guards, and `unknown="defer"`. It does
not mutate a program or select a biological implementation. Native source
admission still checks the full declarations, clock, domain and lifecycle.
`law.state_values(machine.states)` returns the complete ordered quantity map for
authoring the selected local component's independent quantitative contract.

The law is a frozen Python dataclass with its own material-contract `to_data()`;
it does not expand the stable policy source Record registry. Quantities use exact
decimal source `Quantity` values and complete `Unit` identities. Units must denote
count/count or amount/amount; changing id, scale, reference, dimension or kind is
not an implicit conversion. Capacity, threshold and initial must lie on the
quantum grid, with two through sixteen states. Binary floats are rejected.
Grid arithmetic is independent of the process Decimal precision.

Pass the independent original contract to
`policy.component_material.prepare_request(..., instanced=True,
prerequisites=True, finite_machine=True, quantitative=quantitative)`. The resulting
request uses `biocompiler.policy_component_material_request.v0.8` and the explicit
sampled-reservoir material profile. The selected local component uses
`biocompiler.policy_component_material.v0.2` and carries a complete quantitative
contract: original law, ordered state/quantity map, complete state and input model
pins, observation ports, and the crossing request boundary's model pin. A legacy
material request cannot silently consume such a component.

## What native acceptance checks

The new quantitative stage requires exact agreement between the independently
supplied original law and the selected component contract. It binds the selected
local state/input/output models to the checked assembly and source-to-graph
mapping, and checks every True, False and Unknown row at every grid state against
the source machine. It requires the original clock resolution to equal the whole
sample-period Quantity, one-tick observation freshness, zero observed age, and at
most one sample per encounter slot per tick. A one-tick freshness window accepts
same-tick observations; zero freshness is not usable in this runtime.

The component material assessment v0.5 retains `quantitative` and
`quantitative_status`. A failed quantitative check returns no partial binding or
table, withholds material acceptance, and keeps original obligations unresolved.
Every discharged obligation in an accepted request pins the complete quantitative
report, including the separate bounded-machine obligation. The existing
preservation, component assembly, context, prerequisite and publication checks
remain required. Compile/check/replay/export use the existing operation names
with an explicitly negotiated `policy_quantitative_material` capability.

The Python client checks response shapes, original identities, source-table
consistency, sampling premises, resource bounds, and required discharge hashes.
It does not recompute the quantitative law as an acceptance fallback. Named
refinement still exposes ten relations and eighteen premises; the complete
material-report premise now includes the quantitative stage. No additional
biological relation is implied.

## Fixture and validation scope

`core/test/data/policy_quantitative_v01.json` contains an artificial four-level
component-to-RNA contract with quantum 0.5, capacity 1.5, threshold 1, and initial
zero. Its finite domain includes accumulation, saturation, decay, an Unknown
sample while an effect is active, an absent update, a second crossing, and
encounter reset. Its resource and availability premises cover the complete
declared horizon. This is software evidence under supplied artificial premises.

Focused Python tests cover exact authoring, immutable snapshots, explicit profile
routing, report consistency and tampered obligation hashes using inert peers.
Native table, selected execution, material/export and rejection controls are
authored separately. Native acceptance remains pending hosted execution of the
exact revision; neither the fixture nor Python tests establish biological
realization.
