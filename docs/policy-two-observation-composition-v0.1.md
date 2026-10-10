# Two independent observations through checked composition

Implementation checkpoint, 2026-10-08. Hosted execution, full integration and
actual-main acceptance remain pending for this increment. This implements a
bounded slice of priority 3 in the [core architecture plan](core-architecture-session-priorities-2026-10-08.md),
building on [named instances](policy-instance-composition-v0.1.md) and
[provider prerequisite closure](policy-prerequisite-closure-v0.1.md).

## Semantic contract

The separately negotiated family admits exactly two truth observations owned by
the same executor and encounter subject on the same logical clock. Each retains
its original source identity, distinct coherence label, freshness interval,
evidence bank, external input and provider channel. The existing source profile
still determines expression, rising-edge, exclusive-rule, state-write and effect
lifecycle semantics. There is no new primitive or alternate runtime evaluator.

Source declaration order binds the ordered observation-bank inventory. Component
arrangement must also preserve the original source-to-input mapping; graph shape
alone cannot resolve symmetric banks. The independent binding checker traverses
the original source and checks each actual bank, input endpoint, freshness and
expression wire. The context checker binds each original channel to its own
provider allocation. A shared provider never merges ownership or resource demand.

Conjunction preserves the three truth values and the ordered uncertainty reasons
defined by the existing runtime, including repeated reasons. Distinct coherence
labels permit independent measurements; they do not assert simultaneous sampling
or a maximum measurement-time skew. Available and observed ticks remain separate.
The profile preserves the existing rule that an unknown-to-true transition does
not itself constitute an observed rising edge.

Whole-program preservation, every original hard requirement, private prerequisite
closure, independent material reconstruction and fresh export remain mandatory.
The two-observation binding does not establish acceptance by itself. Unknown
inputs and nonvacuous progress requirements can prevent material acceptance even
when candidate/source correspondence is complete.

## Versioned interface

| Surface | Identity |
| --- | --- |
| Nested realization request | `biocompiler.policy_realization_request.v0.3` |
| Nested profile | `biocompiler.policy_two_observation_prerequisite_inputs.v0.1` |
| Implementation binding and report | v0.3, `biocompiler.policy_two_observation_source_graph.v0.1` |
| Outer material request | `biocompiler.policy_component_material_request.v0.4` |
| Material/context profile | `biocompiler.policy_instance_two_observation_prerequisite_mrna.v0.1` |
| Service implementation | `biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1` |
| Validation scope | `policy-instance-two-observation-prerequisite-mrna-v0.1` |
| Capabilities | `policy_two_observation_material`, `policy_two_observation_material_producer` |

The material assessment remains v0.2 and the context assessment remains v0.1;
their checker implementation is v0.4 on this route. Dependency graph and private
closure semantics are unchanged. Primitive, observable, named assembly/proposal
and molecular schemas are unchanged. Old request/profile combinations remain
closed and retain their earlier limits.

Python implementation builders require `prerequisites=True` and
`two_observations=True`; outer component builders also require `instanced=True`.
Python freezes and transports authority. Native admission and checking retain
semantic authority; SDK report validation cannot create accepted native values.

## Independent witness

The domain-only A/B originals declare three material fragments: two edge
fragments and one control fragment containing both evidence banks and their
conjunction. The graphs have 17 nodes/24 wires and 19 nodes/27 wires respectively.
Both retain one complete 17-base artificial RNA, `CCAUGGCUUAAGGAAAA`, four regions,
one product, two encounter slots, 17 resource-owner allocations and 24 original
obligations. This is a software witness, not a proposed therapeutic sequence.

The complete declared finite domain has 36 histories, 42 transitions and 43
prefixes. It begins with false then true observations to exercise original
progress obligations, checks independent freshness intervals of two and three
ticks, and finally enumerates all pairs of no row, valid false, valid true,
missing, invalid and conflicting observations. The final conjunction census is
11 false, one true and 24 unknown. Literal expected outputs are authored
independently of the producer, source executor and candidate evaluator.

Additional native controls distinguish source/bank/input aliasing, bank and wire
order, freshness, mixed profiles, stale identities, distinct observed/available
ticks and repeated uncertainty reasons. An original domain without an enabled
progress event retains complete correspondence but cannot satisfy the original
nonvacuous requirements or export. The source and installed SDK companions retain
26 lifecycle observations each, both paired archives and all nine original
fixture-source inputs. Registered checks still require execution and audit.

## Deliberate limits and validation

This family keeps one or two exclusive rules, one or two truth stores, one
product-bearing effect, named component instances, nonempty bounded prerequisites,
one RNA and no delivered helpers. It does not support arbitrary observation
counts, cross-subject fusion, temporal alignment inference, new molecular
mechanisms or empirical therapeutic guarantees. Those require their own contracts
and complete checks.

The required development census becomes 36 native suites and eight SDK campaigns
with 208 observations. The full native census becomes 176 suites with 182 bundled
executables and 26 distinct original JSON fixtures. Static source inventories,
mocked transport tests and these counts establish neither executed native results
nor integration acceptance. Each acceptance claim must identify its exact source,
run, platform and independent evidence audit.
