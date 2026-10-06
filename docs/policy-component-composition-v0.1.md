# Reusable policy component composition: proposed v0.1 contract

**Source preparation / unaccepted profile.** The literal acceptance fixture was
independently reviewed against `bb84421cf1f93cd1dc02813d80a2c54a3520a919`; source
preparation starts from the corrected union `4157108cbf98a7e48b5c09a5c9dc3beb3a558b40`.
Neither revision accepts this new composition profile. This document specifies
future original authority and independent controls; it is not a decoded request,
execution receipt or export capability. No producer output or expected-trace
generator defines these literal values. Native validation remains hosted.

The first source slice is a closed partial-graph/interface decoder. Component
material libraries, original assembly rules, request/catalog binding, independent
union/material/context checking, producer and public profile negotiation remain
separate work. Track completion in [the development plan](semantic-mrna-development-plan.md).

The preserved design and fixture review under
`work/bounded-policy-execution/generated/policy-realization/` remain historical
review evidence. The scope/context corrections below clarify this tracked
specification without rewriting that evidence.

## Partial-graph domain: current source slice

`Policy_component_fragment.of_json ~library` consumes the closed shape in
[`policy-component-fragment-v0.1.schema.json`](../protocol/policy-component-fragment-v0.1.schema.json).
Its fourteen fields are `schema_version`, `profile`, `primitive_profile`,
`observable_profile`, `phase_profile`, `id`, `version`, `slot_layout`, `nodes`,
`wires`, `boundary_ports`, `external_slots`, `atomic_groups`, and
`semantic_exports`. A node contains the complete original model identity,
configuration digest and body. The independent library must contain that exact
record. A boundary port names one actual primitive endpoint and its exact
direction and signal type; replication is derived from its model. An external
slot declares evidence or feedback input and retains the actual consumer.

Each input has exactly one internal wire, boundary input or external slot.
Every output, including internally consumed outputs, remains in fixed node/port
order. Local groups retain complete arbiters and ordered commits; each action
output has one local destination or one boundary continuation. Locally visible
scope, bank ownership and instantaneous-cycle checks run here; the complete
reconstructed assembly must repeat global checks after linking. Decoding does
not grant source, composition, material, context or export acceptance.

Fragment content identity contains the local graph and interface. It excludes
whole-library, source, provider, material and final-coordinate identities.
The decoder separately retains the library digest as context; equal fragments
must prove membership afresh under each original library. Structural slots
range from one to sixteen, while the first proposed complete fixture below
still admits exactly two slots and one driver instance.

Ingress permits at most 2 MiB canonical JSON, 100,000 value/key visits and depth
48, with no raw floats, duplicate keys or unbounded list traversal. Collection
bounds are 256 nodes, 2,048 wires, 256 boundary ports, 64 external slots, 64
groups of at most 64 commits, and 16,384 semantic outputs. Native string limits
count UTF-8 bytes. JSON Schema documents shape; native decoding additionally
checks complete model membership, digests and cross-field graph predicates.

Independent native test source hand-authors both decision fragments and the
shared driver using only original model declarations from the preserved A/B
fixtures. It includes constant-broadcast controls and 55 rejection invocations,
including exact diagnostic checks for false scope, a local scheduling cycle,
input aliasing, hidden outputs and re-pinned models absent from the original
library. The source is registered in the full native-suite inventory. Native
compilation/execution and a full JSON Schema validator run remain pending;
static inspection is not execution evidence.

## Corrections found in the deeper review

1. Do not use the existing compound fixture with the baseline to claim identical driver reuse: it has timeout **5** and a different attempt model identity; baseline timeout is **2**. Use baseline exclusion and the separately authored state-reading family, whose two driver model records are exactly identical. Existing fixture definitions are references, not producer-derived expected values: `core/test/data/policy_material_request_v01.json` and `policy_material_state_v01.json`.
2. A reusable driver cannot embed the global source digest, whole implementation-library digest, final kernel digest, source effect ID, assembly instance ID or final-member coordinates. Those vary across assemblies. It must pin its own two complete model bodies, local typed ports, local material root and local carrier relation. Each original source catalog independently authorizes those exact used models; the original assembly request binds local interfaces/instances to actual source/graph identities. Fixed two-slot layout is an explicit limitation of this first reuse example.
3. Exact local model-to-fragment relations **do not imply** their concatenation realizes their composed transitions. A new original **composition model-to-material premise** is essential. It must bind all three links, full signal-preserving transport, phases, placements, join, complete material states and context. An interface-compatible RNA with matching peptide is insufficient.
4. Keep all original request/catalog authority intact. Never synthesize an altered v1 `Policy_material_request`, replace its catalog binding with a generated whole-kernel contract, then treat success of the v1 checker as authority for composition. A new original request/coordinator must retain the supplied source/catalog/library/rules/context exactly. Checker-private normalization may create an ordered graph/template only with a checked derivation to those originals, not a fresh invented authority. This is an explicit rejection test below.
5. The first profile allows no added executable helper, connector node, hidden event, latency or buffering. A helper that adds transitions cannot use the ordered-bijection shortcut. A later such profile needs an independently supplied **total** observable projection, explicit bounded hidden-phase semantics and full source preservation over independently reconstructed assembly execution. Merely marking helper outputs internal or counting its RNA is not enough. Static original input/resource providers with already modeled behavior and causal availability can remain premises; they are not evidence of a new executable helper.

## A. Two separately authored source families and immutable domain

A = original exclusion family: select on rising(observation), guard observation, atomically selected:=True and excluded:=False, request response. Exclude on rising(not observation), guard not observation, atomically selected:=False and excluded:=True, no request.

B = state-reading family: retain A's events/exclude branch; select guard `all(observation, not(state selected))`; select atomically writes selected:=True and excluded:=**old selected**, then requests response. Both states initially False. No sequential assignment interpretation. The original three hard requirements remain byte-identical in both families: mutual-exclusion safety and the existing request/initiation progress requirements. Retain every original nonrequirement source obligation and full source map; calculate the new profile's complete obligation inventory rather than assuming it remains 23 after new external authority is introduced.

Copy neither fixture's v1 acceptance into the new profile. Author the new original composition request independently, with a source request matching the selected family, untouched source catalog/model bindings, explicit component catalog/composition-rule pins and original constraints. If new source-side references are needed, author and freeze them as part of the original source before production; never inject them into a checker wrapper after the candidate exists.

Shared finite domain, independently literal: executor role `executor`/identity `cell-1`; clock period exactly 1 second, origin 0; ordered slots `(e1,target-1,0)` then `(e2,target-2,0)`, encounter declaration `encounter`; ticks 0..6 inclusive. Each slot observes False at0, True at1, False at2, all sample time=availability time. No observation or lifecycle factors. At tick2, each of the two previously created attempts independently has silence/completed/failed, max one feedback row per attempt. Logical limits: live slots2, generations per slot2, total source attempts2. No assumptions about success. Histories=3×3=9; prefixes after ticks=[1,1,9,9,9,9,9]; transitions=47; started prefixes=48. The separate broader uncertainty/reset/recreation grammars stay additional full-domain controls and cannot be replaced by this small positive.

The admitted multiplicity is exactly **one driver instance per assembly**. Identical driver reuse across A/B demonstrates reuse across compilations only; it does not establish two same-definition driver instances in one assembly. A doubled driver is an extra-ownership/unsupported source-family negative. Later within-assembly reuse requires a source profile supporting multiple effect instances, independent per-instance state/correlation identities and freshly derived resource totals.

## B. Literal primitive graph and exact composition

No sorting, producer graph dump or target-aware expected-value generator defines these lists. The acceptance test must spell them as literals and compare the actual independently reconstructed candidate under an explicit injective alpha-renaming.

Ordered nodes for A (1-based positions):

```
1 evidence       evidence_bank(freshness_ticks=2), encounter slots
2 select_edge    observed_rising, encounter slots
3 not            truth_not, encounter slots
4 exclude_edge   observed_rising, encounter slots
5 true           truth_constant(True), executor
6 false          truth_constant(False), executor
7 product        product_constant("fixture.product.alpha"), executor
8 select_gate    activation_gate, encounter slots
9 exclude_gate   activation_gate, encounter slots
10 arbiter       exclusive_arbiter(lanes=2), encounter slots
11 select_commit atomic_commit(writes=2,requests=1), encounter slots
12 exclude_commit atomic_commit(writes=2,requests=0), encounter slots
13 selected      truth_register(initial=False,writers=2), encounter slots
14 excluded      truth_register(initial=False,writers=2), encounter slots
15 attempt       attempt_bank(capacity=8,timeout_ticks=2,
                 authorization=continuous,on_loss=continue,on_unknown=defer), encounter slots
```

B adds node16 `selected_not: truth_not`, node17 `select_guard: truth_all(arity=2)`, both encounter slots. All encounter replication is exactly layout `encounters`, slots2. There is one shared global phase profile `biocompiler.policy_primitive_execution.v0.1`; no component has its own scheduler.

The driver definition has local nodes `[product,attempt]` and **no internal wires**. This is not a whole graph: both request and authorization must arrive through checked explicit links. Full model identities shared unchanged in A/B are `exclusion.primitive.product@1`, content `b9f18177e93c478197dc985846db3cf522fdf7286c7217a2ffe2b673ad374be3`, and `exclusion.primitive.attempt@1`, content `7de0c5ffc3e7320d91c8e6e2958bf44ce232ad3952d0e460cb2cee4a367cfdf7`. Pin complete model records/configuration bodies too. Decision owns all other nodes, both atomic commits, both states and the sole arbiter. Global order interleaves driver nodes at7 and15; concatenating instance inventories is incorrect.

Literal ordered wires for A:

```
01 evidence.value -> select_edge.in
02 evidence.value -> not.in
03 not.out -> exclude_edge.in
04 select_edge.events -> select_gate.on
05 exclude_edge.events -> exclude_gate.on
06 evidence.value -> select_gate.guard
07 not.out -> exclude_gate.guard
08 select_gate.candidate -> arbiter.in0
09 arbiter.out0 -> select_commit.grant
10 true.out -> select_commit.value0
11 select_commit.write0 -> selected.write0
12 false.out -> select_commit.value1
13 select_commit.write1 -> excluded.write0
14 exclude_gate.candidate -> arbiter.in1
15 arbiter.out1 -> exclude_commit.grant
16 false.out -> exclude_commit.value0
17 exclude_commit.write0 -> selected.write1
18 true.out -> exclude_commit.value1
19 exclude_commit.write1 -> excluded.write1
20 product.out -> select_commit.product0
21 select_commit.request0 -> attempt.request
22 evidence.value -> attempt.authorization
```

B replaces wire06 producer with `select_guard.out`, wire12 producer with `selected.value`, wire22 producer with `select_guard.out`; appends:

```
23 selected.value -> selected_not.in
24 evidence.value -> select_guard.in0
25 selected_not.out -> select_guard.in1
```

Thus A has13 decision nodes/19 internal decision wires +2 driver nodes/0 internal wires +3 cross-links; B has15 decision nodes/22 internal decision wires +same2/0 driver +3 cross-links. Cross-link IDs and types, ordered at global wire20/21/22, are `product` (Product_symbol, driver→decision), `request` (Effect_request, decision→driver), `authorization` (Truth_value, decision→driver). They transport the complete existing signal: no event/attempt/cause or definedness/reason loss. Driver authorization must name the **same actual producer endpoint** as initiating gate.guard, not an equivalent-looking interface copy. Driver feedback boundary input is Feedback_batch→attempt.feedback, bound to original `feedback`; decision evidence input is Evidence_batch→evidence.samples, bound to original `condition`. External input order is condition then feedback.

Sole atomic group: ID `exclusive_selection`, arbiter `arbiter`, ordered commits `[select_commit,exclude_commit]`. It remains entirely decision-owned; cross-link request delivery participates in the same fixed atomic execution, not a second component commit. No cross-group split or extra arbitration layer.

Exact ordered exports for A (all outputs, including internally connected ones):

```
evidence.value, evidence.updated, select_edge.events, not.out,
exclude_edge.events, true.out, false.out, product.out,
select_gate.candidate, exclude_gate.candidate, arbiter.out0, arbiter.out1,
select_commit.write0, select_commit.write1, select_commit.request0,
exclude_commit.write0, exclude_commit.write1, selected.value, excluded.value,
attempt.events, attempt.snapshot
```

B appends selected_not.out, select_guard.out. Exports are not just component boundary ports. The complete occurrence map derives from original source expressions and actual endpoints, with every source occurrence retained; a composition interface cannot hide a source obligation or observable output.

The checker may retain an untrusted instance→actual-node proposal; it independently proves total one-owner inventory, complete model equality and the above ordered relations. Instance/local name pairs must have an injective encoding. Alpha-renaming preserves semantics only through the fixed correspondence; string prefixes are not an identity proof.

## C. Independent literal traces

For both slots: settled `(selected,excluded)` is `(F,F)` at0, `(T,F)` at1, `(F,T)` at2..6. Two attempts are created at1 in e1,e2 order, generation0, deadlines3. Event creation order is requested then initiated for each attempt. Guard/causal metadata belongs to the actual qualified decision producer.

A select guard at settled ticks0..6 = `[F,T,F,F,U,U,U]`. B = `[F,F,F,F,U,U,U]`; B's **pre-activation** tick1 guard is True and selected is False, whereas post-write guard is False. Attempts are still created and continue; at tick1 B records authorization_changed(False, guard_false) for both, A does not. At tick4 evidence is stale without a new observation; exact reason list `[Stale]` survives the boundary even though attempts have already ended. Undefined raw observation and defined logical Unknown remain distinct typed signals.

Two hand-authored detailed histories per family:
- silence for both feedback choices: both attempts timed_out at3, retained authorizationFalse; no extra attempt at stale tick4.
- e1 completed/e2 failed at2: each ends at2. Retained authorization is True for A, False for B, because feedback occurs before the authorization refresh that would consume the tick2 guard. This distinction tests the shared driver with two genuinely different decision environments.

All nine histories must pass the original safety and progress obligations under the existing nonvacuity criterion. A forged B frame with excluded=True immediately after select would expose sequential writes and must fail correspondence/safety. Compare complete independent traces/requirements, not just these selected literals. Do not derive source expected ledgers from the candidate monitor or vice versa.

## D. Exact material authority and source-to-base path

These are artificial software-only premises, not claimed biological mechanisms. Use fresh original fragment roots, not slices extracted by a producer from its finished output:

- Decision A root `leader_A`, sequence **CC**, length2, feature utr5 `[0,2)`, forward, kind five_prime_utr.
- Decision B root `leader_B`, sequence **CGC**, length3, feature utr5 `[0,3)`, same meaning. This intentional base/length difference distinguishes the decision material while reusing the driver unchanged.
- Shared driver root `driver_body`, sequence **AUGGCUUAAGGAAAA**, length15. Features cds `[0,9)` frame0/coding_sequence; utr3 `[9,11)`/three_prime_utr; poly_a `[11,15)`/poly_a_tail. Complete product spelling **MA** (AUG→M, GCU→A, terminal UAA excluded); ordinary CDS, ncbi_standard_v1, no recodings. Full versioned product identity and provenance are external and shared unchanged.

Each composition uses exactly one authorized `Concatenate` step: full leader then full driver_body, forward, no overlap/gap/reversal/slice/repeat. Derived segment0 copies leader `[0,L)`→output `[0,L)`; segment1 copies driver `[0,15)`→output `[L,L+15)`. Independent complete expected final sequences:

```
A: CCAUGGCUUAAGGAAAA   length17
B: CGCAUGGCUUAAGGAAAA  length18
```

Final member order is exactly `[payload]`, RNA/linear, complete sequence, protein-coding. A regions: utr5 `[0,2)`, cds `[2,11)`, utr3 `[11,13)`, tail `[13,17)`; B: `[0,3)`, `[3,12)`, `[12,14)`, `[14,18)`. Exactly these four features; no extra junction annotation, because current PM leaf explicitly rejects additional feature semantics. Name the junction in the separate composition authority with ordered adjacent endpoints and offset L; do not smuggle a new molecular feature through PM. Feature transition explicitly accounts for each input feature and shifts driver coordinates by L. Both final CDSs still spell AUGGCUUAA and translate to MA.

Full nominal chemistry is supplied for both roots and output. Use declared artificial cap/start-end on the leader, declared finish-end/tail on the driver, known empty modification inventories. The driver cap/start-end and leader finish-end/tail are explicit not-carried facets; all ten root facets get exactly one disposition. In `Explicit_output` mode: map leader cap/start_end to identical output facets; map driver finish_end/tail with exact final endpoint/tail projection; map both known empty modification_inventory facets to the known empty output inventory. Every output facet must have a source disposition. Root claims at non-inherited internal ends remain explicitly accounted for. Do not use Exact_inheritance for a two-root concatenation or silently assume cap/tail construction from sequence letters. Tail is explicit exact length4 and last four A bases. Geometry, status and nominal chemical identities are independently checked and fully pinned; provenance text is not execution authority.

Local carrier authority is exact: driver primitive/configuration/product/replication/feedback/outputs map to its declared local feature sites and/or typed original provider entries, while decision equivalents map to its own sites/providers. Every cross-link has an explicit original composition-rule carrier relation to the two component feature sites and the authorized adjacent join/placement. Feature sites may be existing full regions; do not invent a new PM feature. The checker verifies that local sites project to those actual final features and bases. The rule's full semantic relation includes each link's actual endpoints, type, the exact scope relation (immutable executor-constant broadcast for product; same encounter layout/slot/generation for request and authorization), same tick/phase and ordering. A carrier list attached after the fact is not a substitute for this supplied relation.

The full dependency chain is: original source field/occurrence → fresh admitted behavior → actual primitive/configuration/endpoint → independently selected component-local model and instance → original composition rule for each cross-link → original root/feature and authorized transform → exact final member/base/chemistry/product. Every link is either established or unresolved. Re-pinning a changed producer output cannot create a missing original relation.

Fresh PM structure uses the independently reconstructed aggregate template and original product/chemistry/member authority. Reuse `Construction_check.check_template` and PM through explicit checked interfaces or checker-private factoring. A normalized template/graph must carry a derivation from untouched originals; it cannot replace the original catalog or supplied material contract in a hidden synthetic request. The new coordinator must perform the conjunction itself and retain a complete original-obligation ledger.

## E. Context, resources and negotiation

The existing whole-graph context's record layout binds a whole material-kernel
hash and its v0.1 profile, and each declared capacity binds that exact layout
digest. Composition therefore requires a separately authored context/layout
profile binding the original composition-rule body, its independently derived
canonical component union and new record profile. Candidate node names are
checked by the total isomorphism and identifier-width accounting; a
producer-chosen source-bearing implementation envelope is not the canonical
union. Keep provider bindings and context outside the rule's identity so that
rule, record-layout and capacity digests do not form a circular definition.
Do not copy the old layout, invent
a synthetic v0.1 kernel hash or re-pin supplied capacities to make them fit.
A fresh preservation capability must match the untouched original realization
request fingerprint before the new coordinator checks outer component/rule and
catalog authority. Neither inner PASS text nor a valid result for another
realization request establishes that correspondence.

Both original requests keep one design/member/ORF/product and zero helpers, exact same executor compartment and human-immune/in-vivo constraints. Availability covers inclusive ticks0..6 with exact rational clock. Re-author original max-base limits to admit17/18 only if the request independently intends both; never enlarge a supplied limit to fit B. Components/cross-links cannot strengthen the original environment grammar. Source occurrence IDs, old-attempt feedback and input occurrence validation stay external to candidate-driven selection.

Core logical demand minima are unchanged for A/B: two per-slot truth cells (one per register), evidence3 per slot, two edge-history cells per slot, generation1 per slot, active attempts8/timers8 per slot, retained correlations2 per executor, evidence timer1 per slot, global clock timer1, control queue34, observation row1 per slot/tick, feedback rows2 per executor/tick. Queue formula `2*(2+1+2+2+5)+4*2+2=34`; ordered cause bound `34*7=238`; ordered reason width1; maximum tick8. Preserve separate owners/scope and full original capacity sum/alias rules. Cross-links add no runtime storage only under the explicit identity-transport composition premise. Identifier width must be recomputed after instance qualification and full source/kernel/domain naming; do not freeze the old384-byte layout merely because other quantities match. New complete record/profile identity binds component and join semantics too.

Version request/profile/status negotiation explicitly (provisional name `policy_component_material.v0.1`, separate from existing whole-graph profile). Existing v1 requests/outputs remain unchanged. Old Core/Verify/SDK must reject unsupported composition profile rather than coerce it to a v1 whole graph or fall back to Python. New fresh export binds the complete original composition request, selected component/case/rule identities, graph/material maps, budgets, exhaustive-domain report, final molecules and original source authority. A decoded PASS is never a private accepted value.

## F. Distinguishing mutation inventory and acceptance gates

All semantic controls first establish generic source validity and fresh source/graph admission outside the expected rejection, unless explicitly an ingress test. Refresh only the pins needed to reach the intended boundary; preserve unrelated original authority and expected positive values.

1. Shared-driver positive checks exact complete definition bytes across A/B, not just names; timeout2→5 or continuous→initiation on one driver must fail original model/case relation. B guard stays its actual state-reading endpoint.
2. Missing/duplicate driver node, two owners of one register, undeclared external input, cross-slot endpoint alias, product/feedback route mix-up, omitted/extra/duplicated cross-link, swapped group lanes, changed wire/order/export inventory: fail composition correspondence. Full global23 exports for B,21 for A cannot become only boundary exports.
3. Replace B's authorization link with raw evidence while its gate uses select_guard: typed but wrong retained endpoint; independent runtime/binding rejection before acceptance. Rehashed false operator/source mutation with old candidate: exact source correspondence fails. Sequential-write candidate frame: independent trace counterexample.
4. Same local fragment bindings but no composition-model body; body omits one link, adds delay, claims an unmodeled buffer, changes definedness/reason multiplicity, hides an output, or supplies only a manifest connection: unresolved/unsupported, no export. No implicit composition axiom.
5. Swap/reverse roots, off-by-one join, duplicate a driver base, changed cap/end/tail, wrong feature offset/frame, CDS GCU→GCC (same MA peptide), wrong UTR or altered provenance authority: independent full reconstruction fails against original roots/rule even when product translation still matches. Coherently changing both candidate and a *substituted* original is not allowed by fresh request identity.
6. Freshly valid A candidate supplied with original B request (and vice versa), even with same driver/product, cannot replay/export. Forged catalog binding/producer-invented whole-kernel v1 inner request cannot authorize composition export; final manifest must retain exact external original request, and checker rejects absence/mismatch of its derivation. Stale complete reports/candidate/config/library/component/join/provider bodies cannot be accepted by rehashing only the envelope.
7. Source max_member_bases17 rejects B length18; missing capacity, one-short shared pool, duplicate pool alias, wrong recipient, late provider, narrower environment, omitted original obligation, and undersized qualified-name records fail the corresponding context gate. Budget exhaustion remains incomplete without artifact; no history/prerequisite is pruned.
8. Attempting an executable helper/extra node in this exact-isomorphism profile is explicitly unsupported. A future helper profile needs a total independently authorized projection and full reconstructed assembly/source preservation; no helper-output hiding exception.

Acceptance requires literal graph/material/phase assertions **and** complete independent nine-history preservation for each original family, independent alternative/source/mutation coverage, fresh Core and standalone Verify checks/replay/export, all inherited CI gates, exact source/run/attempt/platform evidence and main integration validation. The specification alone closes nothing. The broader SM05 helper/alternatives/multiple-member work remains separate.

Reviewed relevant code: `policy_implementation_binding_check.ml:160–322`; `policy_primitives.ml:154–179,318–326,372–419,480–500`; `policy_material_binding_check.ml:55–144`; `policy_material_context_check.ml:54–141,157–188,278–299`; `transition_check.ml:230–318`; `policy_mrna_structure_check.ml:83–109,179–210`; `construction_reconstruction.ml:388–401`. Original full fixture/generator literals were inspected, not run or regenerated.
