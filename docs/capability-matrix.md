# Biocompiler capability matrix

This is a human-readable inventory of what each layer can establish, reviewed
on 2026-10-13 against main revision
`ae683603dfbac95aeee1b1bc15efa3f873d0c630`. It accompanies the
[architecture charter](architecture-charter.md),
[architecture review](architecture-review.md), and
[refactoring roadmap](architecture-refactoring-roadmap.md).

This document is **editorial inventory, not a second routing registry**.
[The target-capability catalog](../protocol/policy-target-capabilities-v0.1.json)
remains the authoritative target inventory used by runtime planning and its
negotiated native protocol. For an installed executable, use its actual negotiated
capabilities and fresh native admission. Neither a row below nor a planner result
grants execution, material, export, or human-use acceptance. Counts describe
necessary shape constraints; their Cartesian product is not a supported profile.

## Revision and status boundary

| State | Evidence subject | Meaning in this inventory |
| --- | --- | --- |
| Main implemented | `ae683603dfbac95aeee1b1bc15efa3f873d0c630` | Source and interfaces present in the reviewed main tree. This document performs no new execution or release acceptance. Relative links refer to this tree. |
| Published snapshot | `car-payload-mvp-1`; GitHub release metadata checked 2026-10-13 identifies this main revision and publication at `2026-10-13T06:52:02Z` | Published first-CAR prerelease. The [release](https://github.com/logannye/biocompiler/releases/tag/car-payload-mvp-1) and its exact assets/receipts define the released scope; a main-source row does not automatically assert separate public-workflow qualification for every profile. Metadata inspection is not fresh execution or an asset audit. |
| Earlier published snapshot | `researcher-alpha-1`, local tag resolves to `b81d4ee4dcc97c77f549b98a2994ddd7877839c9` | Historical alpha, not acceptance of later source. See the [alpha release](https://github.com/logannye/biocompiler/releases/tag/researcher-alpha-1). |
| Pending controlled composition | Branch snapshot `0e76e25d5f08cca4ca87fd8778d0f4a0dd441039`; RC6 tested source `17a7352b5e6ed1d087c110bedb365132280152c7` | RC6 artificial joined workflow and one installed hosted slot only. Not merged or published in the main snapshot; broader RC7/RC8 gates remain open in its retained receipt. See CAP-14. |
| Local E1 preparation | `11b6b6da94497fea9afae8dfa12dd900c7295f9f` | Second-reference source, tests and campaign preparation; no inherited first-release native or publication acceptance. See CAP-15. |
| Planned | No accepted implementation identified here | A requirement for future work, not an advertised runtime capability. See CAP-16. |

The controlled-branch links below use immutable commit URLs because their files
are absent from this main tree. Local-only E1 records use commit/path locators.
Their dated validation records report historical observations;
neither their results nor the published snapshot's results transfer to a changed
revision. This review did not rerun native validation or refresh those branch gates.

## Reading the dimensions

**A** is authoring/representation; **N** is native admission or source checking;
**P** is execution and behavioral preservation; **M** is molecular construction;
**X** is accepted export; **E** is evidence assessment. “Conditional” means the
named supplied contracts remain premises, not demonstrated cellular behavior.
“Child” means only the underlying admitted profile supplies that capability.

| Capability | A | N | P | M | X | E |
| --- | --- | --- | --- | --- | --- | --- |
| [CAP-01 Policy source](#cap-01-policy-source) | Broad typed vocabulary | Source validity only | Subset-dependent | Separate | Separate | Declarations retained |
| [CAP-02 Operational semantics](#cap-02-operational-semantics) | Explicit descriptors | Closed executable subset | Abstract reference traces | None | No RNA | Model-conditional |
| [CAP-03 Target planning](#cap-03-target-planning) | Complete source/authorities | First-blocker analysis | Deferred | Deferred | None | Requirements unassessed |
| [CAP-04 Modules](#cap-04-modules) | Typed templates/instances | Exact elaboration | Child | Child | Child plus lineage | No module-behavior proof |
| [CAP-05 Behavioral implementation families](#cap-05-behavioral-implementation-families) | Defined shapes | Profile-specific | Complete bounded checking | Separate | No RNA alone | Supplied models |
| [CAP-06 Single-member component material](#cap-06-single-member-component-material) | Complete original libraries | Profile-specific | Bounded child | Exact supplied RNA | Fresh conditional pair | Empirical unassessed |
| [CAP-07 Multiple members and helper](#cap-07-multiple-members-and-helper) | Closed compositions | Explicit context/closure | Fixed staged child | Two or three RNAs | Fresh conditional pair | Supplied helper/transport |
| [CAP-08 Quantitative material](#cap-08-quantitative-material) | Exact finite laws | Grid/profile-specific | Discrete law plus bounded child | Supplied single RNA | Fresh conditional pair | No continuous/stochastic claim |
| [CAP-09 Approximation and measurement compatibility](#cap-09-approximation-and-measurement-compatibility) | Optional typed contracts | Closed finite domain | Bounded error/label relation | Exact child unchanged | Contract-dependent gate | Supplied parameter compatibility |
| [CAP-10 Material selection](#cap-10-material-selection) | Finite full alternatives | Common-meaning relation | Every child checked | Restricted variants | Selected accepted child | No mechanism-discovery claim |
| [CAP-11 Static CAR expression](#cap-11-static-car-expression) | One encoding objective | Closed static subset | Not requested/supported | Exact nominal reference | Published paired handoff | Scoped source qualification |
| [CAP-12 Project and package workflows](#cap-12-project-and-package-workflows) | Immutable complete project | Preflight is structural only | Child | Child | Fresh Verify/reopen | Retains claim boundaries |
| [CAP-13 Earlier construction and behavior routes](#cap-13-earlier-construction-and-behavior-routes) | Separate schemas | Route-specific | Route-specific | Route-specific | Route-specific | No transferred acceptance |
| [CAP-14 Pending controlled composition](#cap-14-pending-controlled-composition) | Branch-only closed source | RC3 subset | RC5 finite artificial model | RC4 exact artificial pair | RC6 joined branch workflow | Unassessed; RC2 inputs open |
| [CAP-15 Local second CAR reference](#cap-15-local-second-car-reference) | Local second pack | Same profile intended | No new behavior | Distinct nominal originals | Hosted acceptance pending | Reference-specific qualification |
| [CAP-16 Planned capabilities](#cap-16-planned-capabilities) | Some representable | Not generally admitted | Not established | Not generally synthesized | No complete claim | Not established |

## CAP-01 Policy source

**State: main implemented.** The Python policy API constructs immutable typed
descriptions: roles, observations, encounters, state, effects, rules, machines,
transitions, channels, quantitative expressions, requirements, deployment and
assurance. Expressibility does not imply executable or material support.
Python control flow constructs a description; it is not cellular runtime.

The native front end accepts complete original programs, build requests and
submissions, checks source contracts and retains complete declaration,
requirement, assumption and unresolved-obligation ledgers. Source validity grants
no mechanism, behavior, RNA or human-use claim. Natural-language authoring is
not an implemented semantic authority.

Evidence: [source language](policy-language-v0.1.md),
[independent language specification](policy-language-specification-v0.1.md),
[native front end](policy-native-front-end-v0.1.md),
[source checker](../core/lib/checker/policy_check.ml).

## CAP-02 Operational semantics

**State: main implemented.** Explicit supplied descriptors bind definitions to
closed meanings such as timestamped external evidence, encounter generations,
abstract attempts and correlated feedback. Missing, unused, stale or unsupported
interpretations reject. The checked Behavior representation retains original
source fields; supported execution interprets that admitted description.

Operational execution is broader than any one material family. A trace check is
not exhaustive finite-domain preservation, and neither is an unbounded proof.
Unsupported requirements remain in the report. Clock resolution, horizons,
source/attempt limits, uncertainty and incomplete episodes remain explicit.

Evidence: [operational contract](policy-operational-v0.1.md),
[admission](../core/lib/checker/policy_admission.ml),
[reference execution](../core/lib/semantics/policy_execution.ml),
[bounded preservation](policy-bounded-preservation-v0.1.md).

## CAP-03 Target planning

**State: main implemented.** Planning consumes the complete original source and
supplied models/material authority. It runs bounded source, lowering, binding and
dependency diagnostics for the selected target, reporting the **first blocker**.
It does not enumerate histories, assess hard requirements, construct RNA or grant
export. A plan may be `planned` even when a later requirement check will fail.

Use the [runtime target catalog](../protocol/policy-target-capabilities-v0.1.json)
for exact target identifiers, schemas, source shapes, ceilings and limitations.
The earlier numerical target count in the [planning narrative](policy-target-planning-v0.1.md)
is a dated description; it must not override that catalog. Saved plans are inert.

## CAP-04 Modules

**State: main implemented.** Exact module elaboration preserves port bindings,
private ownership, declaration references, assumptions and source lineage.
Fixed ceilings are 64 instances, 4096 expanded declarations, 256 ports per
template, depth 64, 8 MiB cumulative inspected/encoded bytes and 16,000,000
logical work units; original caller limits may lower these ceilings.

Linked-material operations then invoke the unchanged complete child checker.
Module elaboration does not prove module guarantees or support arbitrary
assume-guarantee reuse. A supported module bundle may elaborate to a program that
the chosen executable/material profile rejects.

Evidence: [module contract](policy-module-linking-v0.1.md),
[native linkage checker](../core/lib/checker/policy_module_linking_check.ml).
The contract's dated validation preamble is historical; the revision boundary
above identifies the source inspected here.

## CAP-05 Behavioral implementation families

**State: main implemented.** All rows need complete original source, domain,
descriptors, catalog membership and exact supplied primitive models. The common
bounded gate independently executes source and candidate, retains all requirements,
checks nonvacuity and withholds acceptance for unsupported, unknown or incomplete
obligations. It does not emit RNA by itself.

| Family | Important shape bounds | Additional constraints |
| --- | --- | --- |
| Legacy truth rules | One observation, one effect/product, 1–2 rules and 1–2 encounter truth stores; no machine | Exclusive arbitration; exactly one effect-initiating rule. Slot/model configurations must agree. Legacy implementation ceiling is 256 nodes; material families impose their tighter limits. |
| Fixed staged alternative | One machine with exactly 5 states/7 transitions, two effects, one observation/product, two encounter slots | No independent rules/stores; two terminal states; one initiating transition per effect. Staged lowering has a 64-node ceiling. |
| Finite machine | One machine, one observation, 2–16 states, 1–32 transitions, 1–8 effects, one product, two slots | No independent rules/stores; exclusive arbitration; at most one request per transition and exactly one initiating transition per effect. |
| Machine network | 2–4 machines and 2–4 observations, 2–16 states per machine, 1–32 total transitions, 1–8 effects, 0–4 truth stores, one product, two slots | Distinct observation coherence groups; known Boolean store initials and one writer; explicit priority groups and precommit reads. Channels, fairness, preemption and general predicate resets unsupported. |
| Multiple request sites | One machine/observation, 2–16 states, 1–32 transitions, 1–8 effects, one product, two slots | Each effect has 1–32 initiating sites under one machine arbiter; shared attempt capacity with retained site/guard identity. Multi-machine request sharing and coalescing unsupported. |
| Coupled private state | One machine/observation, 2–16 states, 1–32 transitions, 1–8 effects, 2–4 truth stores, one product, two slots | One writer machine; every transition assigns the complete ordered store inventory from the immutable prestate with atomic commit. Quantitative meaning is a separate check. |

Except the explicitly noted legacy ceiling, these targets have ceilings of
64 implementation nodes, 2048 wires, 64 primitive models and 2048 source
occurrences. One executor, one subject, one encounter declaration and one clock
are retained. These are conjunctive limits, not promises that every allowed
count combination compiles.

**Known shape gap:** one machine with two observations is not covered by the
single-observation machine profiles or the network profile, which requires at
least two machines. The two-observation rule profile in CAP-06 does not execute
machines. Adding an artificial second machine is not a supported semantic fix.

Evidence: [target catalog](../protocol/policy-target-capabilities-v0.1.json),
[finite machines](policy-finite-machine-v0.1.md),
[networks](policy-machine-network-v0.1.md),
[source/graph binding](../core/lib/checker/policy_implementation_binding_check.ml),
[preservation checker](../core/lib/realization_checker/policy_preservation_check.ml).

## CAP-06 Single-member component material

**State: main implemented.** These families add independently supplied fragments,
composition rules, provider context, source-derived resource demands and complete
construction authority to the corresponding behavioral gate. Accepted export is
exact RNA plus its full manifest under supplied component/material premises.

| Material family | Supported addition or restriction |
| --- | --- |
| Legacy component material | Two selected component slots and one RNA; legacy truth-rule or fixed staged source. Nonempty catalog dependency/evidence claims do not acquire prerequisite closure here. |
| Named instance material | Up to eight named component instances and one RNA; retains the legacy source families and their restrictions. |
| Prerequisite material | One-observation truth-rule family and one RNA; explicit original provider dependency and capacity closure. |
| Two-observation material | Exactly two observations with distinct coherence groups; 1–2 exclusive rules/stores, one effect/product, no machine; no implicit frame joining. |
| Finite-machine material | The CAP-05 finite-machine shape with selected staged components, context and one RNA. |
| Network material | The CAP-05 network shape with selected staged components, context and one RNA; no general distributed-cell or message-passing implementation. |

Common material ceilings include 16 component definitions, 64 selected graph
nodes, 2048 wires, 64 primitive models and 2048 source occurrences. Named
families allow at most eight instances; legacy two-slot material remains distinct.
The structural mRNA predicate requires exact complete regions, product translation,
chemistry and represented terminal poly(A), with profile-specific restrictions.

These compilers assemble and check supplied material/template authority. They
do not derive a new molecular mechanism or arbitrary sequence from behavior.
Changing an abstract timer or threshold does not automatically synthesize bases
that physically implement it; its material or explicit non-sequence carrier must
remain accounted for.

Evidence: [material acceptance](policy-material-acceptance.md),
[instance composition](policy-instance-composition-v0.1.md),
[prerequisite closure](policy-prerequisite-closure-v0.1.md),
[two observations](policy-two-observation-composition-v0.1.md),
[mRNA completeness](policy-mrna-completeness-v0.1.md),
[material checker](../core/lib/realization_checker/policy_component_material_check.ml).

## CAP-07 Multiple members and helper

**State: main implemented.** The two-member profile retains the fixed staged
5-state/7-transition source, one observation, two effects and **two distinct fixed
products**, two encounter slots and explicit recipient/transport authority. It
produces two complete payload RNAs, not arbitrary partitioning of any program.

The grounded-helper extension adds exactly one material-only helper RNA with its
own complete product and supplied capacity/availability contract: three total
members, ORFs and products. It adds no hidden behavioral effect. Helper material
and bootstrap prerequisites must be empty in this profile; causal delivery,
expression completion and full-window capacity coverage are checked. Arbitrary
helper chains or general recursive assume-guarantee closure are unsupported.

Evidence: [multi-member contract](policy-multi-member-composition-v0.1.md),
[helper contract](policy-grounded-helper-composition-v0.1.md),
[context checker](../core/lib/realization_checker/policy_component_context_check.ml).

## CAP-08 Quantitative material

**State: main implemented.** These are exact sampled laws with complete finite
state maps and source/selected-component correspondence. Amount per accepted
sample is not a continuous production rate. Original clocks, nominal units,
freshness, observation policy, capacities and resets are part of the contract.
Material remains exact supplied single-RNA construction with the CAP-06 limits.

| Family | Supported quantitative domain |
| --- | --- |
| Sampled reservoir | 2–16 grid levels; exact quantum, capacity, threshold and initial amount. Uses the finite-machine single-request-site family; True/False/Unknown rows are independently checked. |
| Sampled step reservoir | 2–16 grid levels with exact positive rise/fall amounts and multiple threshold-crossing request sites, bound to the shared attempt bank. |
| Conservative transfer pair | Two distinct compartments with one substance/unit/grid, at most 16 Cartesian states; 4–16 machine states and 2–18 transitions. True/False transfer in opposite directions from the prestate. |
| Reserved transfer network | 2–4 reservoirs, 1–8 directed transfers, at most 16 Cartesian states; 4–16 machine states and 1–32 transitions. Declared-order reservation prevents reusing incoming stock or freed headroom in the same sample; one atomic owner commits the vector. |
| Coupled component network | 2–4 binary reservoirs with separately selected owners/private stores and one supplied coordinator, at most 16 Cartesian states; the complete selected edge allocation and next-value circuits are checked. One machine/observation, one effect/product, two slots. |

Unknown and absent updates hold within their stated law; reset and conservation
scope remain explicit. A representable grid does not guarantee that its
implementation fits the 64-node or material-region limits. Continuous kinetics,
stochastic dynamics and physical distributed synchronization are not supplied by
these profiles.

Evidence: [reservoir](policy-quantitative-v0.1.md),
[step reservoir](policy-quantitative-step-v0.1.md),
[transfer pair](policy-quantitative-transfer-v0.1.md),
[transfer network](policy-quantitative-network-v0.1.md),
[coupled composition](policy-quantitative-assurance-v0.1.md),
[target catalog](../protocol/policy-target-capabilities-v0.1.json).

## CAP-09 Approximation and measurement compatibility

**State: main implemented, narrowly bounded.** Approximation compares exact
finite network laws through the complete inclusive material horizon, at most
64 samples. It checks reachable state pairs, explicit observation maps and exact
rational coordinate error bounds. Every effect-request label must agree; small
numeric error cannot excuse a different discrete action. Chains preserve middle
endpoints and sum nonnegative error envelopes.

Optional uncertainty enumerates at most eight closed quantum-aligned Cartesian
cases with the nominal case included. This is not continuous uncertainty,
probabilistic confidence, a stochastic solver or general approximate refinement.
The final law must equal the freshly checked selected component mechanism.

Supplied measurement dossiers bind component, instance, parameter, context and
raw interval records. Their result is supplied parameter compatibility:
`supported`, `incompatible` or `unassessed`. It does not authenticate an external
dataset or establish causal validity. Requested approximation must pass for
export; experimental compatibility gates export only when the original contract
explicitly requires it. No evidence report replaces formal prerequisites.

Evidence: [assurance contract](policy-quantitative-assurance-v0.1.md),
[approximation checker](../core/lib/realization_checker/policy_approximation_check.ml),
[evidence checker](../core/lib/realization_checker/policy_realization_evidence_check.ml).

## CAP-10 Material selection

**State: main implemented.** The catalog contains 1–16 complete original
component-material alternatives with common source, domain and executable
composition. The supported material variation changes a decision leader and
induced coordinates while retaining an identical driver: two slots, three
boundary links, no helpers, one RNA.

Every child is checked before selection by the additional length predicate,
then supplied rank and ASCII ID tie-break. A malformed or incompletely checked
child cannot be discarded to obtain a winner. No eligible candidate means none
in this fully assessed supplied catalog, not global infeasibility. This is not
general mechanism search, optimization over arbitrary equivalent graphs or
automatic sequence redesign.

Evidence: [selection contract](policy-component-selection-v0.1.md),
[selection checker](../core/lib/realization_checker/policy_component_selection_check.ml).

## CAP-11 Static CAR expression

**State: main implemented; first-CAR workflow published at the recorded snapshot.**
The closed source has one recipient role, five fixed product/localization/length
parameters and one encoding objective; one supplied implementation, one RNA,
one ORF/product and no helper. Structural assurance is explicitly timeless.
Runtime declarations, observations, clocks, machines, safety/progress requirements,
quantitative guarantees and external-control demands are unsupported here.

The result checks exact nominal RNA, encoded product, CDS location, source length
bound and supplied expression/localization/context correspondence. It does not
execute a synthetic machine as the receptor mechanism. RM_61461 supplies a
source-attributed nominal reference; a designer-supplied 3′ hydroxyl remains
distinguishable from published historical chemistry. Expression/function evidence
retains its ex-vivo context, donor conflict and unresolved material/applicability
questions.

**Known open reporting defect:** the design specifies safety/progress as
`not_applicable`, and requested assurance and expression/material correspondence
as `conditional`, but the main native checker and Python validator classify all
three as `discharged` when the static
objective passes. Closed admission still rejects actual behavioral requirements;
this is not evidence that safety/progress execution is supported. The
[refactoring roadmap](architecture-refactoring-roadmap.md) retains the correction.

Evidence: [expression design](car-expression-material-profile-design.md),
[native disposition logic](../core/lib/checker/policy_expression_material_check.ml),
[Python response validation](../src/biocompiler/core_policy_expression_material.py),
[reference qualification](car-rm61461-qualification.md),
[published workflow instructions](car-payload-quickstart.md).

## CAP-12 Project and package workflows

**State: main implemented.** Immutable projects retain full original source,
models, material authority, provenance, limits and intended scope. Import and
preflight establish literal structural readiness only. Core produces candidates;
fresh Verify establishes the supported child claim and paired artifact before
atomic publication. Reopening requires complete independently retained originals;
an archive hash or saved PASS is insufficient.

The static CAR workflow and finite-machine research builds use their distinct
child profiles. Exact bytes, source-map changes, report scope and original
authority remain bound even when two source revisions emit identical RNA.
There is no generic export permission that overrides an unsupported child.

Evidence: [research projects](../src/biocompiler/policy/research_project.py),
[finite builds](policy-finite-build-v0.1.md),
[CAR quickstart](car-payload-quickstart.md),
[refinement evidence](policy-refinement-v0.1.md).

## CAP-13 Earlier construction and behavior routes

**State: retained main infrastructure with separate contracts.** The earlier
Intent/Behavior, synthetic combinational/temporal, exact-CDS/reference package,
multi-region molecular construction, precursor and composite RNA architecture
routes are not interchangeable with the newer policy families. Their own schema,
runtime routing, source coverage and acceptance boundaries remain authoritative.

| Route | Boundary to preserve |
| --- | --- |
| Synthetic execution/selection | Finite software model histories, active/inactive coverage and declared time bounds; no molecular kinetics or general biological implementation inference. |
| Exact-CDS/reference packaging | Exact independently pinned reference reproduction; a CDS is not a complete delivered RNA. Historical DNA utilities are shared infrastructure, not a new therapeutic target. |
| Multi-region construction/precursor | Exact supplied fragments, coordinates, chemistry and declared processing structure; structural completion does not implement a source guard, secretion dynamics or shutdown. |
| Composite RNA architecture | Supplied full Behavior subgraphs, bounded state/quantitative/channels, many-to-many material placements, helpers, control domains and recipient assignments; no automatic transfer of these features into policy material profiles. |

Evidence: [toolchain contracts](toolchain-contracts.md),
[independence inventory](verification-independence-v0.1.md),
[molecular design](molecular-design-v0.1.md),
[molecular implementation](molecular-implementation-v0.1.md),
[architecture profile](payload-architecture-v0.1.md).

## CAP-14 Pending controlled composition

**State: branch-only snapshot; RC6 scope, not main or released acceptance.**
Snapshot `0e76e25d5f08cca4ca87fd8778d0f4a0dd441039` records admission, artificial
two-member material, reversible behavior and joined project/export/reopen work.
The RC6 receipt binds tested source `17a7352b5e6ed1d087c110bedb365132280152c7`,
hosted run `38333487924` attempt 1 on Linux x86_64 / CPython 3.11.15, including
one installed rehearsal. Full cross-platform/runtime integration, actual-main and
publication gates remain open in that receipt. A later branch documentation
commit does not inherit a fresh execution claim.

The closed domain has one executor/encounter and six input dimensions: antigen,
controller, two RNA presences and two protein availabilities. Physical state is
separate from missing/invalid/conflicting/stale evidence. Horizon is 1–64 ticks;
intervention cutoff is 0–32 with the required response suffix. Five source
deadlines are positive and at most 64 ticks. Actual mechanism delays are distinct
positive integers up to 10,000; a too-slow valid mechanism must fail the bounded
requirement rather than become unrepresentable.

RC5 uses a closed eight-primitive/seven-wire candidate graph, an independent
mechanism interpreter and a source monitor for six original requirements. It
checks reversible activity and physical RNA/protein distinctions under supplied
artificial contracts. RC4 alone grants only structural pair publication; RC6
joins both checks. Numeric expression/stoichiometric ranges, general compositional
proof reuse and complete real RNA adaptations remain open.

Pinned evidence:
[progress](https://github.com/logannye/biocompiler/blob/0e76e25d5f08cca4ca87fd8778d0f4a0dd441039/docs/controlled-composition-progress.md),
[RC6 receipt](https://github.com/logannye/biocompiler/blob/0e76e25d5f08cca4ca87fd8778d0f4a0dd441039/docs/controlled-composition-rc6-validation.json),
[domain](https://github.com/logannye/biocompiler/blob/0e76e25d5f08cca4ca87fd8778d0f4a0dd441039/docs/controlled-composition-domain-v0.1.md),
[behavior](https://github.com/logannye/biocompiler/blob/0e76e25d5f08cca4ca87fd8778d0f4a0dd441039/docs/controlled-composition-behavior-v0.1.md),
[material](https://github.com/logannye/biocompiler/blob/0e76e25d5f08cca4ca87fd8778d0f4a0dd441039/docs/controlled-composition-material-v0.1.md).

## CAP-15 Local second CAR reference

**State: local E1 preparation at `11b6b6da94497fea9afae8dfa12dd900c7295f9f`.**
RM_61321 / SEQ113 / CAR1 is prepared for the same expression-material compiler
and project interface: 1,770 nominal nucleotides and a 502-residue product,
distinct from RM_61461's 1,776 nucleotides and 485-residue product. No new
reference-specific compiler or behavioral semantics is claimed.

Source and campaign preparation, independent originals, cross-reference
substitution controls and local checks do not establish native compilation,
installed acceptance or a second shipped payload. The extension record keeps
hosted execution/publication as separate pending work. Source qualifications and
designer chemistry choices remain reference-specific.

Locally inspected records at the full E1 commit above are
`docs/car-second-reference-extension.md` and
`docs/car-rm61321-qualification.md` in `work/car-second-reference`.
They are not present in this main tree or asserted to be remotely available.
Recheck the owning branch and its evidence before integrating this capability.

## CAP-16 Planned capabilities

The following capabilities are not established by the preceding rows:

- General source-to-mechanism synthesis or sequence invention beyond supplied
  catalogs/templates, including automatic codon/UTR/chemistry optimization with
  independently checked higher-level preservation.
- General composition across arbitrary observations, machines, RNA members,
  helpers, clocks, recipient populations and communication mechanisms.
- Implementation-independent requirement observer automata and broadly admitted
  alternative graph/state encodings; current exact source/graph profiles constrain
  implementation shape.
- General assume-guarantee proofs, context-safe proof reuse, unbounded liveness
  or correctness beyond the declared finite domains.
- Continuous/hybrid or stochastic biochemical semantics, calibrated population
  uncertainty, broad approximate refinement, or probabilistic therapeutic outcomes.
  CAP-09 supplies a narrow finite approximation relation, not these capabilities.
- Validated real-cell execution models connecting exact emitted material to
  expression, sensing, activity, delivery, persistence or clinical effect in the
  intended in-vivo human context. Supplied contracts and source literature remain
  distinct from such qualification.
- Natural-language authoring as an accepted compiler front end; laboratory
  orchestration and empirical model promotion as a complete learning loop.

The [charter](architecture-charter.md) states the required structural qualities;
the [refactoring roadmap](architecture-refactoring-roadmap.md) assigns concrete
software acceptance tests. The [product roadmap](product-vision-and-integration-roadmap.md)
and [CAR expansion roadmap](car-mvp-and-expansion-roadmap-2026-10-10.md) retain
research and product qualification obligations. A future promotion must update
the appropriate runtime authority and retain exact source, test, platform and
artifact evidence before this editorial matrix labels it implemented or released.
