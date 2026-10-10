# Exact sampled transfer networks

This profile composes two to four quantitative reservoirs through one to eight
named, directed transfers. It makes competition for donor stock and receiver
headroom explicit, then checks the resulting joint state update against the
source program and the selected component's complete supplied contract. The
existing scalar, step and transfer-pair profiles retain their identities.

## Python interface

```python
from biocompiler import policy as p

q = lambda amount: p.quantity(amount, p.COUNT)
network = p.quantitative.SampledTransferNetwork(
    substance="signal", unit=p.COUNT, quantum=q(1),
    reservoirs=(
        p.quantitative.ReservoirCompartment("executor.a", q(1), q(1)),
        p.quantitative.ReservoirCompartment("executor.b", q(1), q(1)),
        p.quantitative.ReservoirCompartment("executor.c", q(1), q(0)),
    ),
    transfers=(
        p.quantitative.TransferEdge("a_to_b", "executor.a", "executor.b", q(1), True),
        p.quantitative.TransferEdge("b_to_c", "executor.b", "executor.c", q(1), True),
        p.quantitative.TransferEdge("a_to_c", "executor.a", "executor.c", q(1), True),
        p.quantitative.TransferEdge("b_to_a", "executor.b", "executor.a", q(1), False),
        p.quantitative.TransferEdge("c_to_a", "executor.c", "executor.a", q(1), False),
    ),
    threshold_compartment="executor.b", threshold=q(1),
    sample_period=p.quantity(1, p.SECOND),
)
transitions = network.transitions(machine, observation, effect, prefix="transfer")
selection = network.bind(
    instance="control", component=selected_complete_component_pin,
    contract="network", machine=machine, observation=observation, effect=effect,
)
```

These immutable descriptions author source transitions and exact wire records;
Python control flow does not execute the cellular program. Compartment names and
edge identities are distinct nominal identities. All amounts use the same exact
unit and positive quantum; no conversion is implicit. A transfer cannot target
its own donor, use an absent compartment, or exceed its donor's declared capacity.
Its Boolean `when` selects True or False observations.

The machine covers the complete Cartesian quantity grid, including states
unreachable from its initial total. There are at most sixteen states, ordered
with the first reservoir as the major coordinate. Every state map row retains
all coordinates. One observation supplies fresh samples, and an upward crossing
of one named reservoir's threshold requests one effect through the existing
shared attempt bank. Each crossing site remains separately bound and checked.

## Reservation and atomic update

The wire contract fixes `arbitration` to
`declared_order_prestate_reservation` and `ownership` to
`single_atomic_state_owner`. These are explicit supported semantic choices.
Reordering transfers changes meaning when they compete.

For the immutable pre-sample vector `x`, capacities `C`, and initially zero
outgoing and incoming reservations `O` and `I`, visit transfers in declaration
order. An enabled edge from `s` to `d` with limit `a` reserves

```
flow = min(a, x[s] - O[s], C[d] - x[d] - I[d])
O[s] += flow
I[d] += flow
```

A disabled edge reserves zero. After all reservations, commit the vector
`x' = x - O + I` in one source transition. Incoming stock and room released by
outgoing transfers are unavailable until the next sample. This prevents a chain
from forwarding newly received stock in the same sample and prevents capacity
from being spent twice. This profile does not promise proportional allocation,
fairness, simultaneous swaps into initially full reservoirs, or continuous flow.

Every reservation is nonnegative, total outgoing stock is bounded by `x`, and
total incoming stock is bounded by `C - x`. Thus every final coordinate remains
within its capacity. Every allocation contributes one debit and one equal credit,
so the sum of all coordinates is preserved. Reset restores the declared initial
vector and starts a new encounter generation; conservation excludes that reset.

Unknown and absent samples hold the vector and create no new request. A known
sample with all-zero allocations has no source transition. Nonzero allocations
must have a transition even if opposing transfers leave the vector unchanged.
The report retains those flows rather than erasing them through a state-only
comparison. Source and candidate runtimes consume each observation update once.

For example, with binary amounts and the True edges above:

| Before `(a,b,c)` | After | Reason |
| --- | --- | --- |
| `(1,0,0)` | `(0,1,0)` | `a_to_b` takes the stock; `b_to_c` cannot reuse its receipt. |
| `(1,1,0)` | `(1,0,1)` | Initially full `b` rejects inflow; `b_to_c` takes `c`'s headroom. |
| `(1,0,1)` | `(0,1,1)` | Full `c` rejects inflow. |

Putting `a_to_c` first changes the first row to `(0,0,1)`. That is a different
original contract and invalidates its dependent checking evidence.

## Versioned contracts and independent evidence

The mechanism schema is `biocompiler.policy_sampled_transfer_network.v0.1`,
with profile `biocompiler.policy_sampled_reserved_transfer_network.v0.1`.
The OCaml domain uses private typed reservoir, transfer, threshold, arbitration,
ownership, local contract and selection representations. Decoding preserves the
complete original wire body and rejects unknown fields or semantic modes.

Local component schema v0.5 uses
`biocompiler.policy_transfer_network_local_material.v0.1`. Material request
schema v0.12 uses
`biocompiler.policy_sampled_transfer_network_component_mrna.v0.1` and requires
the complete original quantitative selection. Existing multi-site realization,
assembly and context profiles are reused. Material preparation selects
`transfer_network=True` with the existing explicit finite-machine, multi-site,
named-instance and quantitative arguments.

The independent OCaml checker reconstructs every True, False and Unknown row
without calling the Python transition author. It checks the full state map,
initial vector, clock, sample multiplicity, edge reservations, resulting vector,
conservation, sparse transition inventory and all threshold request sites.
Selected local state/input/commit models must match their actual assembled
instances and request-bank ports. A matching aggregate total alone is insufficient.

Quantitative assessment v0.4 retains complete `before` and `after` vectors in
integer quanta and an ordered `flows` list containing every edge's identity and
allocation, including disabled or saturated zero flows. It records arbitration,
ownership and conservation within an encounter generation. Failure withholds
bindings, table and conservation evidence. Fresh successful evidence remains
bound into quantitative discharges and the existing named refinement chain.
Material assessment v0.8, service capability `policy_transfer_network_material`,
fresh verification and exact RNA export complete the existing conditional path.
Python transport validation also checks the retained exact allocations against
the original edge order, so a changed report cannot substitute different flows
with the same aggregate state update. Crossing evidence uses state/True/False
order while preserving each request lane's original source-declaration index.
These consistency checks do not replace the native checker capability.

The planning catalog adds `transfer_network_material`, retaining the previous
fifteen descriptors. Planning remains advisory. Source, component, graph,
resource, bounded behavior, requirement and exact material checks remain
conjunctive; description-level support does not grant acceptance.

## Realization boundary

This profile uses one selected component to own the entire atomic state vector.
Its edge allocations are independently reconstructed consequences of the
supplied law. The executable finite-machine comparison observes state changes
and effect requests; it does not measure molecular flux or independently realize
each edge. Exact material construction preserves the selected component's
supplied RNA authority and does not infer transport from emitted bases.

Decomposing the network across separately selected molecular components needs
an explicit reservation/commit interface, compartment ownership, coupling and
transport premises, and resource accounting for the shared coordinator. Merely
joining scalar or pair contracts would not establish that property. Uncertainty,
approximation and experimental realization evidence remain separate follow-ups.

The local implementation and pending native validation are recorded in the
[network checkpoint](semantic-quantitative-network-checkpoint-2026-10-09.md).
