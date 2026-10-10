# Exact sampled step reservoirs and multiple request sites

This is the first increment of roadmap item 4. It generalizes exact sampled
amount changes and explicitly represents several transitions requesting one
effect. The earlier single-step reservoir and single-site profiles retain their
wire identities and meanings. Interacting reservoirs, approximate refinement,
uncertainty and experimental evidence contracts remain later increments.

## Authoring and exact semantics

```python
from biocompiler import policy as p

law = p.quantitative.SampledStepReservoir(
    substance="signal", compartment="executor.reservoir", unit=p.COUNT,
    quantum=p.quantity("1", p.COUNT),
    capacity=p.quantity("4", p.COUNT),
    threshold=p.quantity("3", p.COUNT),
    initial=p.quantity("0", p.COUNT),
    sample_period=p.quantity("1", p.SECOND),
    rise=p.quantity("2", p.COUNT),
    fall=p.quantity("1", p.COUNT),
)
# Supply ordinary source machine, observation and effect declarations.
transitions = law.transitions(machine, observation, effect, prefix="reservoir")
quantitative = law.bind(
    instance="control", component=selected_complete_component_pin,
    contract="reservoir", machine=machine, observation=observation, effect=effect,
)
```

`quantum` fixes the state grid. At each accepted True sample the amount becomes
`min(q + rise, capacity)`; at False it becomes `max(q - fall, 0)`. Rise and fall
are positive exact grid multiples no larger than capacity. All amount quantities
retain the complete same nominal unit. The grid contains two through sixteen
levels. Exact decimal arithmetic is independent of Python's Decimal context.

An upward crossing from below the threshold to at least the threshold requests
the declared effect. In this example both `q1 -> q3` and `q2 -> q4` request it.
Unknown and absent updates hold state and create no request. Previously active
attempts retain their declared authorization and lifecycle behavior. Reset
restores the initial state, advances the encounter generation and invalidates
old active attempts without reusing their identities.

The facade produces ordinary source transitions and a snapshot of the original
law; it grants no native capability. Its law uses
`biocompiler.policy_sampled_reservoir.v0.2` and
`biocompiler.policy_sampled_saturating_step_reservoir.v0.1`.

## Shared effect semantics

The explicit realization request uses schema v0.7 and the
`biocompiler.policy_multi_site_inputs.v0.1` profile. One finite encounter machine
uses exclusive reject-on-conflict arbitration, with at most one requested effect
per transition and no separate rules or truth stores. Multiple machines sharing
an effect and request coalescing are outside this profile.

Each effect has one shared `attempt_bank_sites` primitive. Its ordered
`requestN`/`authorizationN` pairs correspond to initiating transitions in source
declaration order. Its feedback, events, snapshots, active capacity, timers and
retained correlation records belong to the bank as a whole. Adding a request site
does not multiply capacity. Every created attempt retains its actual initiating
gate and guard, allowing authorization and terminal feedback to remain correlated
with the right attempt after repeated requests or resets.

Independent source binding reconstructs every site and guard. Runtime admission
also checks that the distinct gates and commits belong to the same exclusive
arbiter and actual machine bank. The correspondence checker matches the complete
site inventory. Existing truth/staged profiles reject the new primitive.

## Selected components, checking and exact material

Prepare the material request with explicit `instanced=True`, `prerequisites=True`,
`finite_machine=True`, `multi_site=True`, and `quantitative=quantitative` through
`policy.component_material.prepare_request`, supplying all existing original
model, component, rule, catalog, context and budget inputs.

The material request uses schema v0.10 and
`biocompiler.policy_sampled_step_reservoir_component_mrna.v0.1`. The selected
quantitative component uses schema v0.3 and
`biocompiler.policy_step_quantitative_local_material.v0.1`. Its complete original
contract includes the law, ordered state/quantity map, state/input model pins,
and an `outputs` inventory with each crossing's `source_state`, Boolean `input`,
local `boundary` and model pin. Outputs are ordered by ascending grid state;
request ports are ordered by source declaration. Checking relates these orders
through transition identity, never by assuming their indices coincide.

The independent quantitative checker enumerates every grid state under True,
False and Unknown and checks exact source transitions, local model bindings,
complete crossing outputs, and the actual commit-to-bank wire for each request.
Its bindings retain `crossing_sites`, including each transition, source state,
input, request endpoint, model and shared bank port. Missing, extra, reordered or
misrouted contract entries cannot establish the complete relation. The sampling
premises still require the exact original clock period, same-tick observations,
one-period freshness and at most one sample per encounter slot per tick.

Fresh preservation, component assembly, context/resource checks, prerequisite
closure, exact construction and publication checks remain mandatory. Assembly
rules/proposals use their explicit v0.5 multi-site family. Shared attempt demand
is counted once per bank. The quantitative assessment uses schema v0.2; the
material assessment uses v0.6. Every discharged source obligation pins the
complete quantitative report. A failed quantitative check publishes neither a
partial table nor partial bindings and withholds material acceptance.

Existing compile/check/replay/export operations negotiate the new
`policy_step_quantitative_material` capability. The implementation-only route
negotiates `policy_multi_site_implementation`. The Python clients retain closed
response shapes, original identities, ordered source-table/site correspondence
and discharge fingerprints. Native checks retain acceptance authority. The ten
named refinement relations and eighteen premises keep their existing meanings;
no approximate or empirical relation is introduced.

Target planning adds `multi_site_implementation` and `step_quantitative_material`.
The catalog now has fourteen targets; its previous twelve descriptors remain
unchanged. Plans leave execution, requirements, quantitative agreement, resource
capacity, exact material and export as fresh downstream obligations.

## Evidence and continuation

`core/test/data/policy_quantitative_step_v01.json` supplies an artificial
five-level contract and independent literal table. Its bounded history covers
both crossing sites, saturation, decay, Unknown, absent updates, re-crossing and
keep/reset alternatives. The complete horizon is sixteen, including ticks zero
through sixteen. Native tests exercise source/candidate correspondence, shared
capacity, retained site identity, adversarial contracts and complete material,
refinement, replay and export. They remain unexecuted until hosted validation.

The claim is exact sampled step-reservoir agreement under the supplied contract.
The fixture does not establish physical component function, continuous kinetics,
stochastic behavior or therapeutic performance. See the
[implementation checkpoint](semantic-quantitative-step-checkpoint-2026-10-09.md)
for the local checks performed and the remaining native and installed gates.

The subsequent [conservative transfer-pair profile](policy-quantitative-transfer-v0.1.md)
composes two reservoir states under one exact joint contract while retaining this
step profile unchanged.
