# Semantic compilation from Python policy to exact mRNA

Prepared 2026-10-05, America/Los_Angeles. This is the active development plan and to-do list for the remainder of this session.

## 1. Objective and scope

Given a Python-authored therapeutic policy, versioned implementation contracts and sequence-construction rules, produce an exact mRNA artifact whose complete derivation preserves the program's supported meaning, or return a precise reason compilation cannot proceed.

The acceptance target is internal semantic correctness through every compiler layer. Supplied component behavior and model-to-sequence bindings are explicit premises of compilation. Experimental evidence that those premises hold in cells is not an acceptance prerequisite for this phase.

Included:

- Python therapeutic-design records, builders, patterns, composition, immutable requests and serialization.
- Native source admission, operational semantics, implementation lowering, component/material binding and requirement checking.
- Exact mRNA construction, independent verification, immutable artifacts, fresh SDK/CLI export and installed acceptance.
- Declared recipient, environment, timing, capacity, resource and material constraints as formal contracts.
- Positive compilation, precise rejection, unresolved obligations and bounded verification outcomes.

Deferred: Studio, conversational authoring, biological viability, empirical calibration, therapeutic efficacy, unrestricted mechanism discovery, arbitrary sequence invention and automatic production-wide migration. These are not hidden prerequisites for this plan. Existing empirical/human-use statuses remain separate; this work neither changes their policies nor requires them to become positive.

Completion means a complete stack for an explicitly declared supported profile, plus an exhaustive disposition of the wider source vocabulary. It does not mean that every expressible policy must compile. Unsupported source meaning must remain visible and must prevent a complete-artifact claim when it is required by the program.

## 2. Verified starting point and ownership

Implementation baseline: f5564f251dcf62627769bb0f855802c315e75dd8, branch codex/bounded-policy-execution, worktree work/bounded-policy-execution. Development base: pushed PR88 revision 88421d068ebc8437d6d0d4fa1a1bfdb32f150883.

- [PR89](https://github.com/logannye/biocompiler/pull/89) contains the new bounded operational profile.
- [Run 37401642752](https://github.com/logannye/biocompiler/actions/runs/37401642752), attempt 1, passed native compilation, native literal/mutation suites and installed operational Python 3.11 campaigns on both Linux x86_64 and macOS arm64 at the last read-only review.
- Complete acceptance remains open. The observed Python 3.11 shard failed because the workflow source census rejects the new core_policy_operational.py addition as unreviewed. Other gates must be refreshed before claiming their status.
- Source review also found that requirement support classification accepts effect_event without validating its lifecycle phase. This is an SM-00 correction, not an accepted behavior.
- Existing source-only assessment/replay and operational operations retain their current claims and protocol versions. New implementation/material acceptance will use separate versioned profiles.

| Existing foundation | Reuse | Remaining boundary |
| --- | --- | --- |
| [Python policy model](../src/biocompiler/policy/model.py), [builders](../src/biocompiler/policy/programs.py), [serialization](../src/biocompiler/policy/serialization.py) | Existing declarative vocabulary, BuildRequest, Deployment, ImplementationCatalogLock and AssuranceRequest | Field-level executable/material support and complete public routing |
| [Operational domain](../core/lib/domain/policy_operational.mli), [lowering](../core/lib/compiler/policy_lowering.ml), [correspondence](../core/lib/checker/policy_correspondence.ml), [execution](../core/lib/semantics/policy_execution.ml) | Supported source meaning, full source/requirement retention, reference execution | Independently reconstructed implementation semantics and material binding |
| [Architecture refinements](../core/lib/domain/architecture_refinement.mli), [checker](../core/lib/checker/architecture_check.ml) | Component/template/placement identities, helpers, RNA cardinality and declared availability | Current interfaces consume legacy Behavior.t; rich-policy mappings and nonempty resource/domain acceptance are missing |
| [Candidate runtime](../core/lib/candidate_runtime/components.mli) | Independent execution/reconstruction pattern | Rich-policy uncertainty, scoped state, correlated attempts and exact timing |
| [Construction producer](../core/lib/compiler/construction_producer.mli), [checker](../core/lib/checker/construction_check.mli) | Exact molecular construction, chemistry, coordinates and fresh replay | Complete checked policy-to-implementation-to-material chain |
| [Architecture export](../src/biocompiler/compiler/payload_architecture.py) | Fresh verification and paired FASTA/manifest export pattern | A dedicated rich-policy request and acceptance profile |

PR85, PR87, PR88 and their validation/merge owners remain untouched. The preserved reference-package continuation already implements prepare/build/reconstruct/publish/export in source; its owner retains compatibility and hosted acceptance work. Do not recreate it or import that branch wholesale. Integrate accepted main containing the prerequisite source only after a fresh identity/ancestry check, without rewriting other owners' branches.

This plan controls the session's priorities. The existing product and migration roadmaps retain historical acceptance records and separate release obligations.

## 3. Architectural decisions to hold fixed

### 3.1 Keep the complete original request authoritative

The root request contains the original frozen policy, exact definition bundle, deployment/context declarations, implementation/material catalog locks, assurance request, operating domain and compiler/checker profile identities.

Reuse existing source records when their meaning fits. Add closed native representations and versioned envelopes for missing executable meaning. Do not create another broad Python language or silently convert rich policy into the older BuildRequest/Behavior family.

Every consequential field must be interpreted, checked as a declared premise, or explicitly rejected/unresolved. Retaining a field in JSON does not mean its obligation has been discharged.

### 3.2 Introduce three distinct implementation-side representations

Names below are proposed, not shipped APIs.

| Representation | Required content |
| --- | --- |
| PolicyRealizationRequest | Complete original authority, admitted operational profile, finite operating domain, supplied implementation and material libraries, hard requirements, preferences and budgets |
| PolicyImplementation | Typed executable primitives/netlist; ports, wires, state encodings, timers, scheduling, atomic groups, arbitration, encounter/attempt encodings, configuration and source occurrence map |
| PolicyMaterialBinding | Exact relation from implementation instances/configurations/connections to component versions, sequence-template members, features, chemistry, placements, helpers and products |

The implementation IR must perform a real decomposition into independently executable operations. An opaque “execute this source policy” node, renamed source AST or copied source ledger is not implementation lowering.

New candidate values are untrusted. Only separate checker-owned constructors produce checked realization/material states. Re-decoding a serialized PASS must never reconstruct acceptance by itself.

### 3.3 Keep authoring, producer, execution and checker responsibilities separate

- Python builds inert declarations, freezes inputs, negotiates native profiles and transports immutable results.
- Source semantics remain in the OCaml operational reference implementation.
- The lowering producer proposes implementation operations, bindings and material choices.
- Candidate execution reconstructs operations, wiring and parameters from actual locked candidate contents. It cannot obtain behavior from the source evaluator, expected trace or producer.
- Independent checkers consume original external authority and actual candidates, reconstruct correspondence, and own acceptance.
- Existing material producers and checkers are reused behind a policy-specific binding layer. Legacy APIs remain intact.

The trusted base explicitly includes bounded decoding, exact arithmetic, canonicalization/hashing, the chosen source/primitive semantic definitions and supplied model-to-sequence contracts. No claim of independent verification may conceal shared producer logic. Hashes establish identity, not behavioral correctness.

### 3.4 Define preservation before implementing the producer

Initial profile: deterministic, exact-clock observable equivalence after a declared projection, within an explicit finite operating domain.

The projection is fixed by independently supplied profile/library authority and is total over potentially observable implementation/component ports and events. The producer cannot hide an extra effect by labeling it internal. Hidden-step classifications are checked against that authority.

For each admissible input history, the implementation's projected observable trace must equal the source trace modulo an explicit injective generated-identity correspondence. Both directions are required: no required event may disappear and no extra observable event may appear.

Pair environmental inputs causally across the two executions. Extend the identity correspondence when matching encounter/attempt creation events occur, then translate correlated feedback through that fixed correspondence. Specify valid, stale and unknown feedback classes. Divergence is a counterexample; it must not narrow the admissible histories, permit retrospective identity remapping or discard feedback that exposes a mismatch.

Preserve:

- Source declaration and occurrence identities; executor, subject and encounter generation; initiating occurrence and correlated attempt/feedback lineage.
- Three-valued truth and separate missing, stale, invalid and conflicting evidence.
- Exact observable timestamps, ordering and multiplicity; observation time versus availability time; equal-deadline precedence.
- Atomic reads/writes, initialization, reset, arbitration, state scope and capacity behavior.
- Required lifecycle events and distinction between request, initiation, completion, failure and timeout.
- The source profile's stated observation boundary, including settled-tick safety rather than a silently stronger or weaker interpretation.

Allow only explicitly hidden, bounded internal microsteps at the same logical time. They cannot create/remove observable behavior, consume unaccounted time or permit divergence. Provide a bound/ranking argument for internal settling. Initial observable latency tolerance is zero. A later latency/refinement profile must declare permitted delays and prove deadline preservation; it cannot relax timing merely to accept a candidate.

Extract a typed incremental source-transition interface if the checker needs it, while preserving current reference outputs against independent literals. Do not create a second competing source authority during this refactor.

### 3.5 Make the operating domain executable

Finite storage capacity is not a finite value domain. Admission must state and check:

- Allowed observation values and evidence-status classes; exact time grid and horizon.
- Initial state, finite integer/enum/text domains, storage capacity, counter widths and overflow policy.
- Maximum live encounters, generations, attempts, queued events and internal steps.
- Legal simultaneous input batches, reset/end schedules and feedback outcomes.
- Which inputs are environmental, which outputs are implementation-produced, and how they are observed.
- Closed predicates for any required timing, feedback, availability or environment premises.

Prose assumptions are retained but cannot prune the explored domain or justify liveness. New premises cannot be invented by the producer. Library preconditions must be entailed by the original supplied request or reported as unmet. Empty/contradictory domains fail; relevant trigger and active/inactive witnesses must be exhibited.

Executable environment premises must describe a causal input process. Future feedback may depend on prior matched requests, but premises cannot constrain implementation-owned outputs or exclude bad candidate behavior. Require a nonempty permitted continuation at each reachable prefix, or an explicit environment termination/end rule. Even a user-supplied premise cannot circularly establish the implementation response being checked.

Use exhaustive reachable exploration for the first small finite profile. Retain the domain identity, transitions/case census, bounds and counterexamples. Any abstraction or equivalence-class reduction requires a separately checked justification. Resource exhaustion yields incomplete/unknown, not PASS or infeasibility.

A passing finite timeline is regression evidence. A complete bounded-domain result is a stronger, separately named result. Neither becomes an unbounded theorem. Inductive proof beyond the declared horizon is a future profile.

### 3.6 Separate preservation, requirements and export eligibility

A faithful translation may preserve a program that violates its own requirement. Report these independently:

1. Source validity and operational admission.
2. Source-to-implementation correspondence.
3. Preservation over the declared domain, with complete/incomplete coverage.
4. Each hard requirement's pass/fail/unknown/unsupported result and witness.
5. Declared implementation/deployment compatibility.
6. Complete material construction and correspondence.
7. Fresh export eligibility.

Hard semantic requirements must pass for complete accepted export; unsupported or unresolved hard requirements block that claim. Preferences rank eligible candidates only. Biological evidence/use status remains separate and is not a prerequisite for the semantic software artifact.

Export must also satisfy the original AssuranceRequest: requested requirement identities, assurance strength, domain/horizon, tolerances and allowed assumptions. Unknown/duplicate requirement references and unsupported assurance levels reject explicitly. A bounded result cannot discharge an unbounded request; a producer cannot shorten the domain, add assumptions or relax tolerances to obtain acceptance.

Define per-history “not exercised” separately from unknown semantics or missing evidence. The new bounded-domain requirement checker must establish the response for every eligible trigger and retain global nonvacuity witnesses; it cannot manufacture proof by relabeling old per-timeline UNKNOWN reports.

Unverified candidates and diagnostics may be inspected, but must not enter the accepted artifact/export path.

### 3.7 Material correspondence is an explicit supplied contract

A material library entry binds an implementation model and supported configuration to exact sequence/feature/chemistry authority. Model and material authorities are supplied independently of candidate generation.

Check that every selected executable operation, required helper and connection has a complete implementation/material disposition. A claimed implementation connection must have a supplied encoding/composition contract; it cannot exist solely as a convenient manifest edge.

Independently reconstruct selected component transition models and their composition. Interface signatures and parameter names alone do not preserve behavior. Establish their exact semantic correspondence to the checked implementation, or rerun preservation against the reconstructed assembly. Substitutions affecting behavior, state, scheduling or wiring invalidate the prior result.

A configuration may affect emitted bases, select a different template, or remain a non-sequence part of the explicit contract. Each case must be declared. Every executable non-sequence value needs a carrier: a modeled host/environment input or an explicit supplied configuration resource checked against the original deployment. A timer or threshold present only in a manifest is unresolved. Changed source may legitimately yield identical RNA only after fresh checking establishes that the complete unchanged implementation/material contract still satisfies it. RNA equality alone is never acceptance.

Exact bytes cannot, by themselves, prove the supplied model-to-sequence axiom. This phase checks derivation and consistency under that explicit axiom, without requiring empirical viability.

## 4. First complete profile and witnesses

Proposed initial policy-realization profile:

- One executor role and at least two independently represented encounter slots in the accepted witness.
- One exact logical clock; finite horizon; observed/available timestamps and silent ticks.
- Truth-valued evidence and finite scoped state; declared finite machine states and fixed typed parameters.
- Explicit exclusive/priority arbitration with atomic assignments.
- One product-bearing effect family; fresh correlated attempts; completion, failure, timeout and reset/end handling.
- Initiation and continuous-authorization behavior exactly as currently specified. No implied cancellation, cessation or reversal.
- A frozen independently authored finite-state implementation library and exact mRNA template/member set.
- Explicit finite capacity, recipient/compartment, helper and material-count contracts.

The material-compilable profile may initially be narrower than the operational profile. Every excluded combination is diagnosed before accepted material generation. Arithmetic expansion, multi-observation coherence, coordination, quantification, spatial relations, inheritance and new cancellation semantics require later complete profiles.

Freeze three witness families before producer development:

| Witness | Required purpose |
| --- | --- |
| Positive compilation | Original Python request with two encounters, exercised guarded activity, scoped state, at least one nonvacuous progress obligation and complete supplied material authority; all requested hard properties hold on its declared domain |
| Semantic rejection | Source violation, unsupported source/requirement, missing implementation, conflicting premise, insufficient capacity and exhausted search each produce distinct expected outcomes |
| Preservation/material mutation | Near-neighbor source, implementation, wiring, parameter, recipient and sequence changes invalidate old acceptance or produce independently justified revised results |

For the initial positive progress witnesses, use properties that the supplied semantics actually guarantees: requested-to-initiated response within its declared bound, and a rising known observation predicate leading to an effect request within one tick through an uncontested enabled rule. The latter must expose a candidate that deletes both request and initiation. Completion is not guaranteed when environmental feedback may be absent or fail. Cover completed, failed and timed-out outcomes separately; a request demanding guaranteed completion must have an explicit adequate premise/model or receive an unmet requirement result. Freeze meaningful safety/guard/state invariants and their distinguishing counterexamples alongside the progress witnesses.

Artificial exact sequence fixtures are sufficient for software tests under explicit supplied contracts. They remain labeled fixtures. Templates for the accepted mRNA path must meet the chosen complete structural mRNA profile, including required regions and declared chemistry; short arbitrary alphabet strings are not a substitute for that profile's structural completion.

Freeze that completeness predicate before fixture acceptance: complete sequence extent, exact molecule/member and tail realization, required regions, product translation and junction authority, and resolved chemistry declarations or explicitly permitted absence/inapplicability. Existing core-only, bounded-tail or unknown-chemistry construction results cannot automatically establish complete exact-mRNA acceptance.

## 5. Ordered work packages

Checkboxes mean accepted completion of the stated task, not merely source written. During work, record source-ready and hosted-pending checkpoints separately. Stable SM identifiers are the session to-do IDs.

### SM-00 — Close the current operational foundation

Depends on: existing PR87–89 source; coordinate accepted-main integration with their owners.

- [x] **SM-00.1** Refresh local/remote identities and current hosted failures; retain exact diagnostic evidence without taking over PR85/87/88.
- [ ] **SM-00.2** Review and register all new source additions/lineage changes in the frozen workflow authority machinery; preserve original comparisons and rejection controls.
- [ ] **SM-00.3** Restrict requirement event support to implemented lifecycle phases. Add source-valid cancellation/ceased/outcome negative controls, retaining UNSUPPORTED rather than invented FAIL/PASS.
- [ ] **SM-00.4** Audit admission/execution agreement for requirement scopes, reset/order, partial horizons, unknowns and resource limits. Repair concrete gaps in one coherent correction batch.
- [ ] **SM-00.5** Complete exact-revision hosted native, installed four-slot and aggregate gates. Update existing operational checkpoint evidence only when justified.

Exit: the operational dependency is accepted for its declared scope; existing source-assessment contracts and legacy profiles remain unchanged.

Correction checkpoint: run 37401642752/source f5564f251dcf62627769bb0f855802c315e75dd8
tested merge 74ec0ee383a57dea74c00e6ada67846f7e918348. Inspected unit failures
share the unreviewed operational source-registration cause. The correction
preserves the original corpus and adds requirement-phase, expression-retention
and correlation controls. Source registration passed 24 focused Python tests,
including complete independent recapture against unchanged frozen bytes;
native corrections still require hosted validation. PR88 advanced to
5f9b39d354b43070f15114f2e8813e659ab1c4a4 through two merge commits with no file
changes. Its owner's branch and checks remain untouched. Retained diagnostic
details are in the [SM-00 diagnostic review](../protocol/policy-operational-sm00-review.json).

The first correction was pushed in PR89 at
`474b924fcf86d7399c4856260fd630733b934eed`, with source changes in
`a2ee388235536f55aefa5f798af1ddc2d43fdc95` and the unchanged-file PR88 merge.
[Run 37406813336](https://github.com/logannye/biocompiler/actions/runs/37406813336),
attempt 1, has passed native compilation, all native literal/mutation tests and
installed operational Python 3.11 checks on Linux x86_64 and macOS arm64 at the
latest read-only review. Full installed/four-slot/aggregate acceptance is still
pending at that snapshot. Python 3.11 then exposed AST-display fingerprint drift
in the coverage ledger. The portability fix, preserving every reviewed source
distinction and support disposition, is pushed as
`72b0ffcc3ab134e3880b0171d14b9d8bcc58e19b`;
[run 37409588377](https://github.com/logannye/biocompiler/actions/runs/37409588377)
is its new attempt-1 validation. All 25 coverage tests and the complete inventory
agree on installed Python 3.11, 3.12, 3.13 and 3.14. Subsequent SM-01/02 source work
is isolated on the stacked
`codex/policy-realization-contracts` branch so it does not cancel that run.

### SM-01 — Freeze source coverage, complete authority and acceptance fixtures

Depends on: source interfaces already present; final acceptance follows SM-00.

- [ ] **SM-01.1** Create a machine-readable coverage ledger for every source record, field, expression operator, enum/lifecycle branch, unit/scope rule and requirement form.
- [ ] **SM-01.2** Track authorable, structurally checked, native-assessed, operationally executable, implementation-lowerable, material-bound and exportable separately; give each restriction an owner, positive witness and rejection witness.
- [ ] **SM-01.3** Inventory every public rich-policy builder/pattern/serialization/submission path. Preserve symbolic truth guards, immutable snapshots, exact values, source spans and full request inputs.
- [ ] **SM-01.4** Verify pattern/manual expansion and namespacing; separate identical instances' state/effect identity. Any added module composition requires explicit imports/exports and reference rebinding.
- [ ] **SM-01.5** Freeze positive, negative and edit-propagation witnesses from section 4, including complete original BuildRequest/deployment/catalog/assurance authority and expected claim scopes.
- [x] **SM-01.6** Define and freeze the complete exact-mRNA structural predicate before accepting material fixtures; distinguish complete members from core-only sequence, unresolved tails and unresolved chemistry.

Preparation checkpoint: the [coverage ledger](../protocol/policy-semantic-coverage-v0.1.json)
enumerates 612 source syntax distinctions and separately records contextual
support and unresolved witness work. Static inventory completeness does not
close semantic coverage. The [exact-mRNA predicate](policy-mrna-completeness-v0.1.md)
fixes the first complete structural profile; its executable checker remains
SM-06 work.

The [source-only realization fixture](../core/test/data/policy_realization_source_v01.json)
now retains a complete Python BuildRequest, typed product argument, deployment,
bounded assurance, five literal timelines and six source mutations. Seven
Python tests cover independent literal expansion, round-trip authority and
separate pattern instances. Implementation, finite-domain and material authority
remain explicit gaps; passing literal timelines must not be claimed before
native execution, or promoted into whole-domain requirement acceptance.

A separate [exclusion witness](../core/test/data/policy_exclusion_source_v01.json)
adds two defined encounter-scoped flags and an exclusion safety property, five
timelines and four distinguishing source edits. It preserves the original
witness's unknown-safety cases. The 13 source-fixture Python tests and 25 static
coverage tests pass locally. Native source tests now cover both full requests,
exact lifecycle/state literals and fresh replay; their new hosted validation is
pending. Both fixtures still lack complete material authority.

Exit: no authorable distinction can silently disappear, and the first complete compilation target is defined independently of producer output. A new source field/operator fails coverage accounting until classified.

### SM-02 — Specify the realization request, finite domain and preservation contract

Depends on: SM-01; implementation can proceed while SM-00 hosted validation runs.

- [ ] **SM-02.1** Specify versioned PolicyRealizationRequest, finite operating-domain records, primitive contracts, PolicyImplementation and PolicyMaterialBinding wire forms.
- [ ] **SM-02.2** Implement strict bounded decoders and controlled native admission types; check complete original authority and library identities before selection.
- [ ] **SM-02.3** Define input/output ownership, causal executable environment assumptions with prefix continuation/end rules, finite value/identity/time limits, initialization, overflow and interface compatibility. Assumptions cannot exclude bad implementation outputs.
- [ ] **SM-02.4** Freeze the exact observable equivalence relation, causal input/feedback coupling, creation-time identity mapping, hidden-step rules, nonvacuity and per-requirement aggregation semantics from section 3.
- [ ] **SM-02.5** Publish literal preservation examples and counterexamples for timing, unknowns, target mixing, reset, multiplicity, extra/missing events and divergent internal steps.
- [ ] **SM-02.6** Version separate status/report contracts; preserve current assessment/operational operations instead of broadening their meanings.
- [ ] **SM-02.7** Check original assurance strength, requested requirement identities, horizon/domain, tolerances and allowed assumptions against the actual result. Reject omitted requirements and stronger requests satisfied only by weaker evidence.

Foundation checkpoint: the [realization contract](policy-realization-contracts-v0.1.md)
now specifies and connects closed operating-domain, primitive-library/graph and
complete source/domain/model request representations. The new native input
admission checker preserves original source, catalog and assurance authority;
it grants no preservation, whole-domain requirement, material or export claim.
Domain tests specify a literal 1,764-history/3,630-prefix census, including silent
ticks and old-attempt feedback. This is an environment-enumeration fixture, not an
executed source proof. Graph checks and all new native controls await hosted
validation. Primitive transitions, producer-independent behavioral preservation,
complete material bindings and public realization operations remain open.

Exit: request admission and the preservation relation are reviewable and executable without relying on a lowering producer.

### SM-03 — Build independent implementation primitives and reconstruction

Depends on: SM-02.

- [ ] **SM-03.1** Define a small closed primitive set covering evidence/age encoding, three-valued predicates, scoped storage, atomic commit, explicit arbitration, finite machines, timers and correlated attempt state.
- [ ] **SM-03.2** Implement candidate-state initialization and transitions independently of Policy_execution. Reconstruct exclusively from actual supplied primitive instances, configuration, ports and wiring.
- [ ] **SM-03.3** Check well-typed ports, units, clocks, scope, state encoding, capacity and unique ownership; reject combinational/scheduling cycles unless a specified bounded settling rule admits them.
- [ ] **SM-03.4** Implement the independently fixed total input/observable projection, causal feedback coupling and injective encounter/attempt mappings fixed at creation. Declare any structural sharing and prove that distinct instances retain independent state.
- [ ] **SM-03.5** Add literal primitive and composed-runtime controls authored separately from the producer; enforce the runtime/producer/source dependency boundaries.

Exit: a hand-authored implementation candidate executes the accepted/rejected witness histories correctly without consulting the source evaluator or producer.

Source checkpoint: [independent primitive execution](policy-primitive-execution-v0.1.md)
now includes a separate actual-graph runtime, causal source-prefix replay,
producer-independent source/graph binding and exact observable prefix comparison.
Native controls cover the one-rule and exclusion witnesses and altered traces.
The runtime/binding/prefix batch is PR91 at
`22fb05f6901cd037dbffe95ae7750c1e78803200`, with native compilation passing on
Linux and macOS in [run 37412211034](https://github.com/logannye/biocompiler/actions/runs/37412211034).
Full native, installed and aggregate acceptance remains pending. Complete-domain
checking is the next source batch described below; material acceptance remains open.
Review also found an unspecified host-language evaluation order in source
request/initiation event creation. The explicit-order correction is pushed to
PR90 as `4440e08c953a20d07e8d9d3a57c97bdcaa69c434`, with native validation in
[run 37411134501](https://github.com/logannye/biocompiler/actions/runs/37411134501).
PR89's older run cannot establish acceptance of this additional correction.

### SM-04 — Implement lowering and independent bounded preservation checking

Depends on: SM-02 and SM-03; accepted results also depend on SM-00.

- [ ] **SM-04.1** Lower admitted operational declarations into explicit primitive instances, configuration, wires, state/timer allocation and scheduling groups. Preserve complete source occurrence/requirement ledgers.
- [ ] **SM-04.2** Build a producer-independent structural checker that reconstructs every expected obligation against original source and supplied contracts. Reject missing, duplicate or multiply owned behavior.
- [ ] **SM-04.3** Implement complete reachable-domain exploration for the first small profile, with exact domain/case census, finite-state coverage, budgets, counterexamples and fresh replay.
- [ ] **SM-04.4** Check both-direction observable equivalence, bounded internal settling, environment assumptions and source/candidate requirement outcomes independently.
- [ ] **SM-04.5** Retain active/inactive and trigger/response witnesses where relevant. Separate no-trigger histories, unknown evidence, actual failure, unsupported properties and incomplete exploration.
- [ ] **SM-04.6** Corrupt the producer and candidate gates, encodings, parameters, wires, clocks, identities and state transitions; demonstrate rejection with the unchanged checker.

Exit: the first operational policy family has checked implementation preservation over its full declared finite domain, not merely one matching trace. No material producer is yet trusted to preserve that result automatically.

Source checkpoint: [bounded preservation](policy-bounded-preservation-v0.1.md)
now specifies an untrusted deterministic lowering producer, an independent
candidate requirement monitor and fresh exhaustive causal-domain checking.
Tests include a separately authored complete nine-history domain with a literal
47-transition/48-prefix census, original unknown safety, failed/unsupported hard
requirements, no-effect nonvacuity, altered authority and bounded stopping.
These controls are source-ready and require hosted execution. No checker task
is closed from the authored expected census or static validation alone.

### SM-05 — Bind components, deployment contracts and RNA architecture

Depends on: SM-04; schema/library preparation may overlap SM-03.

- [ ] **SM-05.1** Add a policy-specific adapter to reusable component/template/placement/helper/deployment types. Preserve legacy Behavior APIs and reject any lossy conversion.
- [ ] **SM-05.2** Independently reconstruct selected component transition semantics and composition, checking exact correspondence to the accepted implementation or repeating preservation on the assembly. Match full locked models and configuration; account for every primitive and connection.
- [ ] **SM-05.3** Implement required finite resource/domain mappings currently rejected by the architecture profile; check cumulative memory, timers, queues, instances and formal resource budgets.
- [ ] **SM-05.4** Check helper bootstrap and dependencies, declared recipient/compartment consistency, co-delivery groups and supplied availability windows against the implementation clock and lifetime. Resolve every executable non-sequence configuration to an authorized host/environment input or supplied resource.
- [ ] **SM-05.5** Select bounded alternatives with hard constraints before preferences. Retain alternatives, deterministic ties, conflict explanations and search exhaustion without claiming global infeasibility/optimality.
- [ ] **SM-05.6** Preserve many-to-many function/component/mRNA relations, count every delivered helper, and check exact/max member and length limits.

Exit: a complete checked implementation has a complete eligible RNA architecture under the original declared contracts, with no hidden helper or unmet semantic constraint.

### SM-06 — Complete implementation-to-material correspondence and exact construction

Depends on: SM-05; construction leaf work can overlap SM-04.

- [ ] **SM-06.1** Define independently supplied configuration-to-template and connection-to-composition rules, pinning the implementation model, exact template roots, sequence features and relevant context.
- [ ] **SM-06.2** Independently reconstruct material bindings from actual selected components and templates. Reject orphan executable operations, missing helpers, phantom connections and unauthorized extra delivered members.
- [ ] **SM-06.3** Reuse existing construction operations and exact chemistry/coordinate checks, then enforce SM-01.6 completeness. Resolve full sequence extent, exact tails, required UTR/CDS/end features, chemistry and supplied product translation/junction authority; reject unresolved partial constructions.
- [ ] **SM-06.4** Check every emitted base, member, feature and source/destination coordinate against original roots and authorized transforms. No implicit back-translation, optimization or invented sequence.
- [ ] **SM-06.5** Establish complete implementation-configuration-to-material dependency maps. Sequence/layout edits invalidate affected implementation/material claims; identical bytes do not imply identical configuration authority.
- [ ] **SM-06.6** Add source/implementation/material mutations: guard polarity, state encoding, deadline/configuration, product/CDS, missing member, altered base, wrong junction, chemistry or recipient.

Exit: exact complete mRNA candidates are independently checked against both their material construction authority and the accepted implementation binding.

Construction/material source checkpoint: the
[source-neutral construction leaf](construction-content-v0.1.md) reuses the
existing producer and independent reconstruction without a fabricated legacy
circuit. Its own success keeps broader claims unassessed. Separate mRNA
structure, whole-graph material and original-context checkers now have source
implementations, followed by a coordinator that requires private upstream
acceptance and complete original-obligation discharge. The initial case pins
every primitive/configuration/connection disposition to supplied exact material;
it does not infer biological behavior from sequences. The
[material acceptance checkpoint](policy-material-acceptance.md) specifies the
closed schemas, record capacities and conditional scope. New literal controls
retain the complete original request, 23 obligations, exact molecules and
9-history/47-transition/48-prefix expectations. Full material hosted acceptance
is pending; SM-06 checkboxes remain open. Next: execute the exact-content,
configuration/carrier, context and cross-layer mutation controls together, then
retain their exact-revision evidence.

### SM-07 — Integrate fresh acceptance, immutable artifacts and public SDK/CLI

Depends on: SM-04 through SM-06.

- [ ] **SM-07.1** Define a canonical accepted-build manifest containing full original source artifact, definitions, domain, implementation/material libraries, every IR, mappings, requirements, bounds, checker identities and emitted member inventory.
- [ ] **SM-07.2** Distinguish declaration-content identity from full source-artifact identity, including source maps/provenance. Define a stage-by-stage invalidation graph and exact replay inputs.
- [ ] **SM-07.3** Add explicit versioned compile/check/replay/export native operations. Standalone Verify reconstructs acceptance without producer linkage; old result profiles retain their existing statuses.
- [ ] **SM-07.4** Route complete rich-policy requests through thin immutable Python SDK/CLI adapters. No semantic fallback on unsupported input, incompatible binaries, timeout, crash, cancellation or exhausted work.
- [ ] **SM-07.5** Export only a freshly checked immutable accepted result, atomically binding RNA FASTA and full manifest. Recheck exact bytes at the publication boundary and preserve prior outputs on failure.
- [ ] **SM-07.6** Verify outside the checkout with producer modules absent and original authority supplied separately. Reject forged/rehashed reports, stale binaries, altered claims and truncated evidence.

Exit: one complete Python-policy → implementation → exact mRNA path works through installed public APIs with fresh standalone verification and exact request-bound export.

Source checkpoint: separate implementation operations retain their intermediate
claims. The [material path](policy-material-acceptance.md) now has dedicated
compile/check/full-wrapper replay/fresh-export native operations, immutable
Python transport, CLI routing and a complete manifest/FASTA pair. Standalone
Verify checks/replays/exports without producer linkage; compilation remains a
Core proposal followed by fresh checking. No saved report can authorize export.
The helper stages one ZIP, checks its complete bytes/metadata by bounded
readback, then publishes atomically. Request, candidate, invocation and report
identities are separate; all original obligations and empirical-unassessed
statuses remain visible. Native/service/publication tests are source-ready,
not accepted hosted execution. Next: run them with separately retained originals
and fresh installed Core/Verify binaries, including forged/rehashed wrappers,
changed bounds, cancellation, staged corruption and preserved prior output.

Hosted correction: runs 37414250697 and 37414496311 compiled on Linux but their
native suite step failed. A mismatched exclusion-catalog chassis was found in
the inherited positive fixture. A separately named resolved catalog now pins the
matching original chassis; the complete previous mismatch is retained as a
negative control. The original UNKNOWN source and its uncertainty requirement
remain unchanged. A subsequent source-path correction canonicalizes the
unchanged original document root across direct and service ingress. A later
preservation run exposed a 100,000-unit monitor allowance that could not encode
the full binding report at initialization; positive fixtures now explicitly use
1,000,000, with tiny-monitor incomplete controls retained. These are regression
corrections, not transferred acceptance. The coordinator separately charges
logical data visits plus child semantic work, including original decoding and
startup/publication passes. Its frozen request decoder has an independently
calculated 480,645-unit census with exact/one-short controls; this is not native
CPU accounting or a hosted receipt. The prior 480,657 calibration changed only
with the separate context-owned delivery-group schema, which permits empty
assumptions without changing the legacy codec or weakening the context's
rejection of opaque assumptions. Python transport also checks full original
context obligations/provider evidence and exact allocation retention, including
legitimate partial rows on failed checks. All SM-04/05/06/07 acceptance
checkboxes remain open.

New partial native evidence: [run 37418186608](https://github.com/logannye/biocompiler/actions/runs/37418186608),
source `d982d58642d94f9d9c798f20bc672fcc69d1f04f`, passed both early platform
suites through source/source-graph, trace, lowering, independent monitor,
whole-domain preservation (9 histories/47 transitions/48 prefixes and 22 negative
controls) and implementation service. Construction then failed a test expecting
a later bundle-residue diagnostic when the transform had already failed.
Test-only correction `1eeb05817ce73a27a3ef5df109336ddb70d35de7` preserves the
exact earlier member/step failures and separately tests a two-member aggregate
residue overflow; production behavior is unchanged. The correction and subsequent
material stages still require hosted validation. Full gates remain pending.

### SM-08 — Close the declared profile, compatibility and hosted acceptance

Depends on: SM-07; test/campaign design starts at SM-01.

- [ ] **SM-08.1** Run the semantic and edit-propagation matrix in section 6; require positive, distinguishing negative and cross-layer mutation coverage for every supported row.
- [ ] **SM-08.2** Verify rejection coverage for every excluded field/operator/enum combination; distinguish unsupported language, missing library support, contradiction, violation and exhaustion.
- [ ] **SM-08.3** Preserve historical unit/corpus/source-lineage/SDK behavior and all existing release tests. Add reviewed authority entries instead of weakening frozen baselines.
- [ ] **SM-08.4** Run all four installed Linux x86_64/macOS arm64 × Python 3.11/3.14 campaigns on hosted native builds, with Python semantic authorities forbidden.
- [ ] **SM-08.5** Independently compare complete semantic outputs and molecule sets across slots. Preserve actual per-platform binary/provenance differences and exact source/run/attempt binding.
- [ ] **SM-08.6** Complete the full exact-revision aggregate gate and any required integration/main validation under branch ownership rules. Record source-ready, tested and accepted revisions separately.
- [ ] **SM-08.7** Finish targeted prebuilt/installed routing for this profile, including missing/wrong binary, offline invocation, standalone verification and fail-closed upgrade/profile mismatch. Broader default cutover remains separately gated.

Exit: the first declared rich-policy-to-mRNA profile is accepted end to end. A demo, subset of tests, static check or prior branch's receipt cannot close this package.

Source checkpoint: the installed material campaign and Linux/macOS × Python
3.11/3.14 wiring/comparator have source implementations, with complete semantic
outputs, original authority, binary/run/attempt pins and exact artifact-pair
checks. No hosted material run or complete four-gate acceptance is established
by this checkpoint. Next: complete required checks, both hosted native targets,
all four installed slots with independent comparison, and exact-revision
aggregate/integration acceptance. Keep packaged/offline/default-routing work
separately visible, retain all historical gates, and record successful source
and tested revisions before changing any checkbox. The existing reference-package
source implementation remains under its compatibility/acceptance owner's scope.

Current exact-revision checkpoint: source `46fb5a5c9fded877866d333f0e1e8aef75a9fe5b`,
run `37420548147`, passed the focused native tests through 124 context controls
on both platforms. The coordinator then rejected a fixture expecting one extra
persistent-state obligation although its stores have encounter lifetime. The
corrected independent census is 23; original authority and obligations remain
unchanged. Pending corrections additionally cover nominal duration references,
complete ZIP-header integrity, test isolation and metadata-only source-edit
invalidation. These source changes require their own hosted evidence.

Next SM-08 witness queue: exercise initiation/continuous and continue/defer
alternatives while an attempt is active; compound guards and explicit Unknown
state through bound material candidates; distinct delivery providers and
re-pinned provider/channel conflicts; Verify-only consumer packaging with
producer absence and explicit offline enforcement. Keep each item open until
its complete positive and distinguishing negative controls execute successfully.

Further source checkpoint: the installed material campaign now checks an exact
Python-builder-to-canonical-request witness before native execution. A separate
consumer stage removes producer modules/Core from its staged tree, requires
inherited OS network denial, and repeats full original-bound Verify check/replay/
export with four-slot evidence comparison. The native coordinator passed 100
controls on both platforms at source `5e26a18d999328932dbc78cd1182b648d73b38ee`,
run `37421588095`; the service then stopped at an object-key-order-sensitive
test comparison, now corrected to canonical JSON equality. New source and all
remaining installed/aggregate acceptance still require hosted validation.

Current partial evidence: integrated source
`3044e9d62a4c16cc294e4110ab521b019537298d` includes accepted main through PR88
merge `f594991ac2ff2496723ae5f2427ad93e6df7a51d`. Run `37423025439`, attempt 1,
passed both complete early native suites, including context 137, coordinator
100, generic production/independent service/replay/fresh export and lifecycle
1,519 assertions. Both Python 3.11 installed material and inherited-network-
denial Verify-only campaigns also passed. The complete native suites then failed
two stale test inventories: realization admission expected 52 instead of the
54 existing rejection controls, and producer protocol omitted the two new
implementation/material compile operations. Test corrections retain the exact
inventories and extend standalone producer-operation rejection. Remaining
installed/aggregate evidence and the corrections require fresh validation.

The next source batch adds two complete compound-guard/assignment cases with
defined Unknown state and ordered reason multiplicity, each retaining the three
original hard requirements over 54 histories/176 transitions/177 prefixes.
These exercise already admitted meaning rather than expanding the profile.
SM-08.7 additionally needs supplied-wheel installation and package-owned binary
resolution for this material profile. The reusable distribution implementation
already exists in the preserved continuation; use its narrow foundation without
recreating reference-package routing or taking over its owner's acceptance.

The source audit additionally found abstract-effect formal defaults/refinements
that lacked an executable interpretation. Admission now requires signature-only
formals (fixed selection and null value/lower/upper); 20 fully repinned controls
retain generic source validity and must reject at this new guard. The reviewed
contextual matrix inventories 62 rule families with explicit source witnesses
and remaining gaps, complementary to the 612 syntax distinctions. These source
checks do not execute semantics or close hosted acceptance.

Source `54f3bd8ac51486a3fd950578b2d384c000564914`, run `37427381964`, tested
merge `a5a66fa6c69c5144ca557c4864f2ba3bfba81c88`, stopped both native jobs
before compilation during upstream source acquisition. The logs lacked an
active URL; a separate source-only probe reproduced the GNU GMP-host timeout
and verified the fixed kernel.org mirror against the unchanged archive hash and
byte count. The correction retains bounded acquisition attempts and diagnostics
without relaxing source identity or any native gate. The same batch adds 23
source-valid restrictions: 16 exact graph-binding rejections, three operational
admission rejections and four finite-domain type rejections. These require fresh
hosted execution; source inventory and test declarations cannot close acceptance.

### SM-09 — Expand supported semantics through complete vertical profiles

Depends on: SM-08 for acceptance; design work can be prepared earlier.

- [ ] **SM-09.1** Choose the next profile from actual source coverage needs: additional finite numeric domains/quantities, richer state/lifecycle, composition, timing or other already authorable constructs.
- [ ] **SM-09.2** Extend source meaning, primitive semantics, lowering, preservation, material contracts and public profile negotiation together; specify version compatibility and artifact invalidation.
- [ ] **SM-09.3** Add complete accepted/rejected witness families and repeat the same hosted gate. Never mark a feature exportable merely because it is authorable or reference-executable.
- [ ] **SM-09.4** Reconcile affected public workflow/default migration tasks with their owners. Retire a Python semantic authority only when every dependent admitted path is accepted.

Exit per expansion: a complete supported source-to-mRNA path with explicit boundaries. Deferred language forms remain faithfully represented and explicitly unsupported until their own contracts are implemented.

Source checkpoint: the first material profile is a single supplied whole-graph
case with one exact RNA/product and no delivered helper, using a narrow
exclusive truth/encounter family and explicit formal context. General component
composition, broader numeric/state/lifecycle operations, machines, coordination,
quantification, inheritance, independent delivery and helper/multiple-member
closure remain expansion work. Next: choose one concrete source-coverage need
after the initial SM-08 gate, extend every dependent semantic/material/public
boundary, and repeat complete positive/distinguishing-negative hosted acceptance.
No broader support follows from a source declaration, matching sequence or
single-case success; biological viability is outside this session's scope.

## 6. Required semantic and mutation matrix

| Dimension | Positive/control pair and rejection target |
| --- | --- |
| Python construction | Builder versus literal document; pattern versus manual expansion; separate identical instances; reject accidental symbolic truth conversion, foreign/dangling references and namespace collisions |
| Data fidelity | Exact large integers/decimals, units, ordered occurrences and complete ledgers; reject raw floats, duplicate keys, bool/integer aliases and ignored extra fields |
| Source identity | Full definition/version/digest and original artifact; reject stale descriptors, altered source spans/requirements and recomputed self-supplied hashes |
| Evidence | Strong Kleene tables; each invalidity reason; delayed arrival and quiet-time expiry; reject unknown-as-false and inappropriate loss of evidence reasons |
| Identity and state | Equal-valued distinct targets, reset generations, independent pattern instances, finite capacities and overflow; reject merged encounters/attempts, retrospective identity remapping or leaked state |
| Atomicity/arbitration | Common read snapshot, identical/conflicting writes, explicit priority opposing source order, rule/machine competition; reject invented ordering and partial commit |
| Time/lifecycle | Before/at/after deadlines, simultaneous feedback/timeout, repeated attempts, wrong/stale feedback, reset/end and no-input ticks; reject fabricated completion/cancellation |
| Preservation | Missing/extra/reordered observable event, changed timing/multiplicity, incorrect projection, falsely hidden effects, identity collapse and divergent hidden steps |
| Requirements/domain | Real triggers and relevant active/inactive witnesses; source failure, missing feedback, unknown coverage, truncated horizon, empty/contradictory domain and unsupported phase; reject omitted requirements, weaker assurance, reduced domains, producer-added assumptions and circular premises that exclude bad outputs |
| Candidate independence | Alter producer while keeping checker fixed; remove producer linkage; mutate locked operations/wiring/configuration; prevent candidate use of expected source trace |
| Components/resources | Same-signature/different-behavior substitution, missing helper, bootstrap cycle, exceeded capacity, wrong recipient/compartment, incompatible availability, hidden material and cardinality violation |
| Material | Swapped product/CDS, wrong template parameterization, altered base/junction/coordinate/chemistry, unresolved sequence/tail, omitted member, manifest-only connection and configuration without a carrier |
| Freshness/export | Modify any original input, definition, model, domain, template, transformation, bound or checker version; reject old PASS and partially published output |
| Resource accounting | Exact finite-domain census, budget exhaustion and bounded decoding; no successful partial trace/proof/build/export |
| Cross-platform | All four installed slots, actual binary digests, full semantic/material output equality, duplicate/missing/stale receipt rejection |

Metamorphic cases must state their equivalence relation. JSON object-key order/formatting may preserve canonical content; source-map edits may preserve declaration meaning but change full authority; consistent renaming may preserve behavior modulo identities. Do not require unchanged raw traces where generated IDs, source provenance or resource accounting legitimately differ.

For a source edit, accept only one of three reviewable outcomes: a newly checked implementation/material result; precise rejection/unresolved status; or a fresh proof that the existing complete implementation/material contract still satisfies the edited source. Do not demand every semantic edit change RNA bytes, and do not accept unchanged bytes without fresh checking.

## 7. Work sequencing and ownership during implementation

Critical path:

SM-00 → SM-01 → SM-02 → SM-03 → SM-04 → SM-05 → SM-06 → SM-07 → SM-08.

SM-01/02 design and fixture work may proceed while SM-00 CI runs. SM-05 contract preparation and SM-06 reusable material checks may run alongside implementation/runtime work, but acceptance waits for their stated dependencies.

Use one integration owner for protocol schemas, Dune boundaries, status contracts, source-authority registries, CI wiring and final evidence. Delegate disjoint files:

| Track | Ownership |
| --- | --- |
| Source/domain/lowering | Coverage ledger, admitted request/domain, implementation IR and lowering producer |
| Independent execution/checking | Candidate reconstruction, preservation relation, bounded exploration, requirements and mutation controls |
| Python/artifacts/material adapters | Immutable SDK/CLI transport, construction integration, manifests, edit invalidation and installed campaigns |

Agree on interfaces and literal fixtures before parallel source edits. A checker review must be independent of producer expectations. Review borrowed library semantics explicitly; reuse compatible primitives without silently importing old missingness/rising/identity conventions.

Batch coherent changes, run appropriate local static/Python checks once, then native hosted validation. Do not push documentation-only churn that needlessly cancels useful running acceptance. Preserve useful failure logs and refresh exact source identities after each necessary correction.

## 8. Evidence and completion policy

All OCaml/Rust compilation, native executable tests, extension rebuilds and native packaging remain hosted. Local work is editing, documentation/static checks and meaningful Python-only tests without implicit native builds.

For each SM package, retain: task IDs, source commit, tested checkout/merge revision, source tree identity, run/attempt, platform/Python/toolchain, actual Core/Verify hashes, complete case census, full results, counterexamples and remaining obligations. Static checks, tests and formal/bounded proof coverage are separately named evidence.

A task checkbox may be checked only when its stated exit is satisfied. Use a checkpoint note for “source ready; hosted pending.” Source-only work is valuable but is not accepted execution. Preserve every existing gate, discovery accounting and required negative assertion; new work adds coverage.

The session's first major completion gate is SM-08:

- Every supported source distinction has an executable/lowering/material disposition.
- The original Python request reaches exact complete mRNA members through real implementation lowering.
- Independent reconstruction checks preservation and all required obligations over the declared bounded domain.
- Exact material and complete configuration/model/source correspondence are checked.
- Fresh standalone verification and atomic paired export work outside the checkout.
- Source/model/material edits cannot retain stale acceptance.
- All required exact-revision hosted gates pass.
- Unsupported requests receive precise diagnostics.
- No Studio, conversational or empirical-viability work is required to satisfy this gate.

## 9. Immediate execution queue

1. SM-00.1–00.4: repair reviewed source-authority registration and requirement-phase classification; inspect any remaining current-run failures without weakening guards.
2. SM-01.1–01.6: freeze the field-level coverage ledger, complete request authority, exact-mRNA completeness predicate and first accepted/rejected witness families.
3. SM-02.1–02.7: specify and implement the closed finite operating domain, implementation/material contracts, assurance compatibility and exact preservation relation.
4. SM-03/04: build independent candidate primitives/checking and the first actual implementation lowering together.
5. Continue through SM-05–08 using this checklist; select further profile expansions only after the complete first path is established.

## 10. Related governing documents

- [Operational semantics and current boundary](policy-operational-v0.1.md)
- [Python source language](policy-language-v0.1.md)
- [Native source frontend](policy-native-front-end-v0.1.md)
- [Existing architecture contracts](payload-architecture-v0.1.md)
- [Existing molecular design construction](molecular-design-v0.1.md)
- [Independent verification boundaries](verification-independence-v0.1.md)
- [Development validation](development-validation.md)
- [Migration roadmap and historical receipts](language-migration-roadmap.md)
