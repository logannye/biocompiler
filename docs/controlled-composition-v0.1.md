# Controlled composition v0.1

Status: RC1 implementation specification, dated 2026-10-12. This document freezes
the first closed family; it does not claim native support or validated CAR
function. [ADR 0008](decisions/0008-controlled-composition.md) records the design
decision and the [roadmap](car-composition-reversible-control-roadmap-2026-10-12.md)
owns the delivery gates. The inspected implementation base is
`0b19ef68ad029de1c10245008fddf81a3a4bfddd`.

## 1. Scope and complete result

V0.1 compiles a supplied two-product implementation of one controlled activity
to exactly two ordered, complete RNA specifications. It independently checks
the source requirements over a finite operating domain under supplied material,
mechanism and deployment contracts. The first named example is a split ON-switch
CAR; the kernel and profile do not contain antigen-specific compiler rules.

The closed inventory is one human T-cell executor, one target subject and one
encounter slot, one clock, two source observations (antigen and controller), two
fixed product parameters, one `ControlledActivity`, one selected implementation,
two RNA members with one ORF/product each, and no delivered helper. Additional
requirements are retained and either admitted explicitly or reported unsupported;
they cannot be dropped to produce a complete result. Molecular and behavioral
component counts need not equal RNA count. State and resource ownership is unique.

The external controller is a declared dependency, not a third RNA. Its local
exposure band is distinct from administration history. No PK solver, dosing,
mechanism discovery, sequence optimization, general cancellation, killing
semantics or intersample guarantee is admitted. Reaching background activity
does not undo prior activity or completed downstream effects.

Complete acceptance requires source admission, model realization, bounded
requirement checking, material reconstruction, context/dependency closure and
fresh exact publication. An accepted conditional software result may retain
unassessed empirical applicability and human-use status. Missing executable
authority or a requested unsupported behavior prevents complete acceptance;
missing biological validation does not by itself do so.

## 2. Source records and profile separation

The new source root and the contained `PolicyProgram` use
`biocompiler.policy_controlled_composition_source.v0.1`. The semantic bundle keeps
its existing record profile. The initial entry point accepts a complete
`BuildRequest` with bounded assurance, an explicit finite quantity horizon,
complete original semantic definitions, catalog and deployment. A bare draft,
standalone program, old `CompilationSubmission`, unbounded horizon or
`not_applicable` horizon is not accepted by this source entry point.

The additive declaration has these exact fields, in addition to its wire tag:

| Field | Type and interpretation |
| --- | --- |
| `id` | Unique declaration identity. |
| `executor` | `Ref` to the sole `Role`; owns activity state. |
| `subject` | `Ref` to the sole encounter `Subject`; identifies antigen context, not an RNA recipient. |
| `clock` | `Ref` to the sole `Clock`. |
| `contract` | Complete `DefinitionRef` to the normative controlled-activity operation. |
| `gate` | Typed truth `Expr`: exact conjunction of the two original antigen/controller observation references. No evaluator-only predicate is an actuator. |
| `products` | Ordered tuple of exactly two distinct `Ref`s to fixed text `Parameter`s; resolve to the complete product identities through the original realization/material bridge. |
| `readout` | Complete `DefinitionRef` to a text-valued activity endpoint/map; output alphabet is exactly `background`, `active`. |

`activity_band` is a nullary text-valued expression referring to the activity and
its source subject. It reads the modeled physical endpoint for requirement
checking; it neither requests activity nor creates a feedback loop. Its `args`
are empty, its literal `value` is null, and its `ref` and `scope` retain those
original identities. Comparisons use exact text literals from the closed band
alphabet. Unknown is an evidence/result status, never a third physical band.

Existing `Requirement` records carry the safety/progress demands, applicable
activity reference, clock, horizon, source assumption IDs and requested
deadlines. Complete pinned normative requirement definitions identify the six
obligations in section 6. Display text alone does not implement an operation or
requirement. No `Effect` is inserted to manufacture the already encoded products.
No product-bearing effect argument is used as a substitute for the activity.

The independent source schema is normative. Generate an additive native shape
table and verify Python representation against it without changing old schema
bytes. Old source profiles reject `ControlledActivity` and `activity_band`,
including when nested in an otherwise old-profile document. New records being
constructible as Python values establishes representation only.

## 3. Original source, mechanism and evidence are different inputs

Source requirements state acceptable behavior. The independently supplied
mechanism describes actual modeled behavior. In v0.1 that mechanism is the
deterministic delayed-control family below; it has explicit actual
`onset_ticks`, `cessation_ticks` and `reactivation_ticks`, each a positive integer.
Those parameters are original mechanism inputs, not copies of requested
deadlines. An actual delay shorter than a source bound is valid if all other
requirements hold. A bound shorter than the actual response yields a concrete
counterexample where the response conditions persist.

The source reference establishes allowed output histories and executes source
requirements. Candidate execution separately reconstructs the exact supplied
mechanism from selected component bodies and wiring. Verify checks (a) that the
candidate realizes those bodies and (b) that each actual candidate history is
allowed by the source and satisfies every requested requirement. It must not
demand equality with one arbitrary earliest/latest source trace or derive the
mechanism's delays from source deadlines. Nondeterministic or stochastic model
successors are unsupported in v0.1; a future version must check all successors.

Every semantic reference resolves to its full original body. The operation,
readout, controller/exposure interpretation, availability and model parameters
must be tied to the selected products, material, recipient and original catalog.
The readout map names its observable and exact finite abstraction. It cannot map
protein abundance or a killing observation to CAR activity just by changing a
label. Supplied threshold definitions retain units, boundaries, provenance and
applicability; arbitrary continuous numerical execution is outside v0.1.

Evidence assertions are retained separately as measured, source-derived,
designer-supplied or unresolved. A valid *modeled evidence record* can be supplied
for software checking; it need not be an actual experiment. That declaration
does not establish empirical validity.

## 4. Physical inputs, evidence and ownership

Each complete input history specifies the physical factors below at every tick.
Their finite domains and allowed trajectories are original authority. An
independent observation/availability contract binds each factor to its source
or dependency; physical factors cannot be invented by the producer.

| Factor | Physical values | Owner |
| --- | --- | --- |
| Encounter | inactive/live plus generation | Sole encounter slot. |
| Antigen engagement | absent/present | Current encounter generation. |
| Controller exposure | disabled/enabled | Executor. |
| RNA A, RNA B availability | absent/present for each | Executor and respective member. |
| Functional protein A, protein B availability | absent/present for each | Executor and respective product. |
| Activity | background/active | Executor; retains encounter-generation cause. |

Protein availability means satisfaction of the supplied functional operating
range and localization/stoichiometry prerequisites, not merely a positive
abundance measurement. More detailed ranges can be premises of the supplied
finite availability map; no quantitative assembly guarantee is inferred from
binary presence. Both proteins must belong to the same concrete executor and
the supplied compatible compartment. Same-population placement is insufficient.

RNA and protein availability are separate. Losing RNA does not immediately
remove an existing protein. Supplied expression/persistence contracts constrain
their trajectories; the compiler does not infer translation or decay kinetics
from sequence. Confirmed functional protein loss is covered by the v0.1
cessation rule. An availability claim outside a supplied contract is a reported
domain/contract violation, not a branch silently removed from exploration.

Each factor's associated evidence retains `valid`, `missing`, `stale`, `invalid`
or `conflicting`, observation/availability time and original nominal binding.
Freshness is evaluated in the original clock; future-dated evidence, a valid
value outside its alphabet and stale old-generation antigen evidence are not
usable current evidence. The physical factor and evidence status are distinct.
Missing evidence does not rewrite that factor or set activity to background.

V0.1 conservatively yields unknown when evidence needed to discharge a demanded
requirement is unresolved. Model correspondence and the physical activity
history remain reportable independently. A required unknown prevents complete
behavioral acceptance. This rule concerns the declared observation semantics,
not the presence of empirical biological validation. The admitted domain's
evidence constraints are explicit; an accepted example may not secretly discard
a permitted missing/stale/invalid/conflicting history.

## 5. Exact clock, events and deterministic activity model

All times are nonnegative integer ticks of one exact positive clock resolution.
Source quantities must convert exactly to integral ticks; no rounding is allowed.
Tick zero is included. Initial activity is `background`, no timer is pending and
no activation has occurred. Initial active state is unsupported in v0.1. Source
deadlines and actual model delays are strictly positive.

The sole reusable slot is initially inactive and requires an explicit `start`
before engagement. `start` is valid only while inactive, including after an
`end`; `end` and `reset` are valid only while live. Every start/reset creates a
fresh observation generation. Reset ends the old generation and creates the next
one in the same slot. Start/end/reset combinations at the same tick are invalid.
Engagement without a prior start, duplicate start, end/reset while inactive and
old-generation observations receive explicit domain diagnostics. Event count,
generation count and retained history are bounded by original exploration limits.

The complete tick order is:

1. Apply the sole declared lifecycle event. End/reset invalidate old antigen
   evidence and pending encounter-owned onset. Reset preserves executor state,
   controller/RNA/protein factors and any existing cessation deadline. End leaves
   the slot inactive. An end/reset tick requires antigen `absent` and cannot
   initiate new activation. A start tick may supply new-generation antigen.
2. Apply the physical-input batch and assess the separate evidence batch. The
   batch is atomic; repeated conflicting writes are not resolved by list order.
3. Compute qualified gate `G`: encounter live AND antigen present AND controller
   enabled AND both functional proteins available. The declared source gate is
   its antigen/controller conjunction; live context and product availability are
   checked context/realization prerequisites. On end/reset, `G` is false for that
   boundary tick regardless of restored executor factors.
4. Apply the activity transition rules below, with disabling before activation
   maturity. Record the resulting band and transition cause for this tick.
5. Evaluate every source requirement and evidence obligation on that completed
   frame, including obligations whose deadline equals this tick.

The deterministic transition rules are:

| Current phase | Tick condition | Required next behavior |
| --- | --- | --- |
| Background, no timer | `G` true | Start onset at this tick if never active; otherwise start reactivation. The band remains background until its due tick. |
| Pending onset/reactivation | `G` false, end or reset | Cancel the pending activation. There is no new activity and no stop request. |
| Pending onset/reactivation | `G` true and due tick reached | Become active. Record one new activation and its original generation. |
| Active | `G` true | Remain active. |
| Active | `G` false | Commit to cessation at `tick + cessation_ticks`. Activity remains active until that due tick. |
| Stopping | Any input before due tick | Keep the original cessation deadline; restored input cannot cancel or postpone it. Further losses do not restart the timer. |
| Stopping | Due tick reached | Become background. If `G` is true, start a reactivation timer at this same tick; the band still remains background. |

If a pending activation's due tick coincides with a disabling event, it is
canceled: no active pulse is created. If cessation maturity coincides with
restored enablement, cessation occurs first and reactivation starts afterward.
Actual positive reactivation delay prevents a background-to-active transition in
that same tick. A reset while active initiates ordinary bounded cessation; it
does not erase residual activity. A reset while already stopping cannot extend
the stop deadline. Controller restoration during stopping begins a response
interval only when background is reached and the gate is still qualified.

For example, with all three actual delays equal to two: enable at tick 0 gives
active at tick 2; disable at tick 3 gives background at tick 5; restore at tick 6
gives active at tick 8. These numbers are artificial software parameters, not a
biological timing claim.

## 6. Allowed source behavior and mandatory requirements

The following six obligations retain distinct original requirement identities.
The source request supplies their deadlines and permitted background/active
endpoint mapping. Their normative definitions fix trigger/cancellation meaning;
neither free-form text nor candidate-local parameters may replace those bodies.

| Obligation | Semantics |
| --- | --- |
| No unauthorized activation | Every background-to-active transition has qualified `G` at the transition tick and an uninterrupted qualifying interval since its onset/reactivation trigger. Initial absence of either antigen or controller cannot initiate activity. |
| Initial activation | When background, never previously active, and `G` becomes qualified, start a source obligation at that tick. If `G` remains qualified, activity must reach active by the inclusive onset deadline. Loss before completion cancels that response obligation and prohibits new activation. |
| Controller cessation | A controller loss while activity is active starts a background obligation with its own source deadline. Restoration does not cancel it. Later losses cannot replace an earlier pending obligation. |
| Antigen cessation | Antigen loss, encounter end or reset while active starts the analogous independently named background obligation. Its deadline is separately supplied. |
| Component cessation | Confirmed loss of either functional product while active starts the analogous background obligation. Loss of RNA alone does not trigger it while both proteins remain available. |
| Reactivation | Once an earlier active episode has reached background, qualified `G` starts a new response obligation. Sustained `G` must yield active by the inclusive reactivation deadline on every admitted history. A loss cancels this pending activation obligation; it does not erase an already pending cessation obligation. |

Simultaneous losses create all applicable source obligations. Each remains
independently checked; the earliest deadline controls the earliest required
background response. One observed background frame can discharge multiple
obligations. Repeated losses of the same cause while its cessation obligation
is pending coalesce into that obligation without replacing its trigger or
deadline, including a repeat on its due tick. Activity within a committed cessation interval is allowed residual
activity, not a new activation. Bounds refer to the named sampled endpoint;
they do not assert instantaneous physical zero or downstream reversal.

The first two-parameter gate does not itself prove any additional requested
safety property. All requirements named in `AssuranceRequest` must remain in the
ledger. Source scope, subject, clock, activity references, deadline units and
assumption identities are checked before execution. Unsupported additions or
unresolved evidence cannot be reclassified as satisfied by an unrelated model.

## 7. Complete finite domain, suffix and non-vacuity

The RC3 [closed operating-domain grammar](controlled-composition-domain-v0.1.md)
specifies the original typed inputs, fixed restrictions and finite Cartesian
factors. Its native cursor enumerates input histories without evaluating the
activity mechanism. Receipts distinguish complete enumeration, exhaustion and
cancellation, and retain the domain fingerprint and fixed/factor census.

The original domain declares a decision cutoff `C`, positive source deadlines,
and an inclusive final horizon `H`. Every admitted physical/evidence/lifecycle
choice through tick `C` is explored. After `C`, the suffix has no start/end/reset
or physical input changes: it holds the last physical inputs, separately
retaining the declared evidence schedule and freshness interpretation. No fresh
valid evidence is fabricated by holding a physical value. These restrictions
are explicit original domain assumptions and are displayed in the report.

Require at least
`H - C >= max(controller_off, antigen_off, component_off) + max(onset, reactivation)`
using source deadline ticks. This allows a stop pending at the cutoff to reach
background and then a restored gate to complete reactivation. Actual mechanism
delays do not replace requested deadlines when computing this suffix. A model
too slow for the source must fail by the applicable deadline. Every pending
obligation and state transition is checked throughout the suffix; unresolved
obligations at `H` cannot pass. The assurance horizon equals `H` exactly.

Input-alphabet completeness, trajectory restrictions and the finite product of
choices are checked independently of the producer. No unsupported factor,
impossible fixed input, violated premise, dead branch or over-budget branch is
silently pruned. Invalid original domains are diagnosed; an exhausted valid
domain is incomplete. Counters cover starts, transitions, completed histories,
all modeled successors, retained state/trace, work and published bytes.

Besides universal satisfaction within this domain, complete acceptance requires
retained witnesses for: active and background activity, antigen absent while
controller enabled, controller disabled while antigen present, and a complete
background/active/background/active history. Reactivation must complete before
the horizon. Required availability-loss cases are checked against the admitted
domain. A permanently background candidate, irreversible stop, empty domain or
missing triggering interval cannot pass through vacuity. A witness is coverage,
not a substitute for checking every admitted history.

## 8. Joint authority, request and artifact boundaries

Reserve these version boundaries for the family:

| Surface | Version/behavior |
| --- | --- |
| Source | `biocompiler.policy_controlled_composition_source.v0.1`; additive source schema. |
| Component request | `biocompiler.policy_component_material_request.v0.14`. |
| Material profile | `biocompiler.policy_controlled_composition_mrna.v0.1`. |
| Operations | Existing `compile/check/replay/export-policy-component-material`; explicit new profile capability required. |
| Control contract | `biocompiler.policy_controlled_composition_contract.v0.1`. |
| Source authority preparation | `biocompiler.policy_controlled_composition_source_authority.v0.1`; retains source, contract and supplied context, not complete native material authority. |
| Realization request | `biocompiler.policy_controlled_composition_realization_request.v0.1`. |
| Operating domain | `biocompiler.policy_controlled_composition_domain.v0.1`. |
| Mechanism model | `biocompiler.policy_controlled_activity_model.v0.1`. |
| Candidate | `biocompiler.policy_controlled_composition_candidate.v0.1`. |
| Assessment | `biocompiler.policy_controlled_composition_assessment.v0.1`. |
| Native result | `biocompiler.core.policy_controlled_composition.v1`. |
| Resources | `biocompiler.policy_controlled_composition_resources.v0.1`. |
| Manifest / export | `biocompiler.policy_controlled_composition_manifest.v0.1` / `biocompiler.policy_controlled_composition_export.v0.1`. |
| ResearchProject | Reserve `biocompiler.research_project.v0.3` with explicit limits and complete native context equality; preserve historical v0.1/v0.2. |
| Publication | Exact two-record ordered FASTA and complete manifest, atomically published only after fresh checks. |

These literals are reserved in
[`controlled-composition-profile-v0.1.json`](../protocol/controlled-composition-profile-v0.1.json).
Reservation grants no native capability. Each decoder must freeze its closed
record and independent fixtures before admission; those realization, domain,
material and publication records are RC3–RC6 work. The request retains the
existing component-material original authority roles and adds full
`project_context` and a complete controlled-composition contract. This contract
retains source activity/operation/readout bindings, actual mechanism parameters,
controller, original product identities, member/material authority, deployment,
availability interpretation and dependencies. It is not a candidate-provided
summary. Profile tags must agree across source, realization, domain, assembly,
context and selected models.

The original authority includes complete bodies for source semantic definitions,
all selected catalog entries, component models and ports, assembly rule, both
material members and their order, original construction roots/transforms,
regions, chemistry, translation policy, localization, resources, controller and
availability maps, project source records/assumptions, empirical assertions,
domain, and budgets. The canonical invocation identity binds the exact original
request **and** explicit execution limits; replay compares both to the caller's
independent originals. Metadata-excluding source digests are not sufficient for
full project authority. Derived pins never replace complete expected bodies.

Capability negotiation requires the exact operation, source profile, request
schema/profile, result family, resource family, implementation identity
`biocompiler.ocaml.policy_controlled_composition.v0.1` and validation scope
`policy-controlled-composition-mrna-v0.1`. A missing or incompatible advertisement
is an explicit capability rejection. There is no legacy fallback. Python record
construction and a generated shape table must never advertise that capability.

Diagnostics retain their stage, original requirement/reference identity, source
path and reason. The reserved families are profile, source, scope, contract,
domain, material, authority, requirement, evidence, resource, capability and
publication. Invalid authority/admission, a concrete requirement violation,
unresolved evidence, unsupported semantics and exhausted resources remain
distinct non-accepting outcomes. No test may require a downstream diagnostic
when an earlier independent check correctly rejects the same candidate.

Explicit limits cover input bytes/nodes/depth, ticks, lifecycle generations,
physical/evidence choices, complete histories, source and candidate transitions,
obligations, retained frames/state, work, report bytes/nodes and publication
bytes. No automatic increase, truncated domain or omitted history can yield
complete acceptance. RC3 freezes hard ceilings and exact counters with native
resource decoders; the RC1 corpus checker has its own smaller structural limits.

Two products can share one control module without duplicating its state. The
full product/member/port mapping and each resource owner must be reconstructed.
Every RNA retains its complete regions, nominal modified-base/parent-base
interpretation, terminal chemistry and translation identity. Whole template plus
member order is construction authority. A foreign candidate remains foreign
after local hashes are recomputed or one RNA/UTR/chemistry is substituted.

The manifest retains source, request, limits, candidate, complete model/domain
identities, original assumptions, selected material and controller, requirement
results, source/primitive/material correspondence and complete report. Run timing
and hosted receipts remain separate from canonical design identity. Failed,
canceled, incomplete or unknown dynamic checks publish no complete-profile
archive and leave an existing accepted output unchanged. A structural diagnostic
must have an explicitly partial status and cannot masquerade as this result.

## 9. Pass ownership and integration

The implementation extends the existing pass boundaries in this order:

1. Independent source schema; Python `model.py`/serialization conformance;
   additive native document shapes and decoding. Representation is not admission.
2. `policy_check`, `policy_admission`, `policy_operational`, `policy_lowering`
   and source correspondence: preserve the new activity and every requirement.
3. `policy_operating_domain` and `policy_domain_reference`: versioned band inputs,
   executor/encounter scopes, lifecycle and evidence adaptation, complete choice
   enumeration, suffix and resource accounting.
4. `policy_execution`: source allowed-relation/requirement reference behavior;
   realization admission and implementation binding/lowering: supplied mechanism
   and primitive graph construction with complete original identities.
5. `policy_primitives`, trace correspondence, requirement monitor and preservation
   checker: independently execute candidate activity, compare the appropriate
   relation, check every requirement, and count physical activity/reactivation
   coverage rather than abstract active attempts.
6. Component arrangement/assembly and existing construction/structure leaves:
   preserve two members and exact molecular authority. Component context and
   resource/dependency checks close same-recipient, localization, availability,
   model/material, controller and project authority.
7. Component-material service/capability dispatch, Python transport and
   ResearchProject: public compile/check/replay/export with fresh independent
   verification and exact atomic publication.

The checker reconstructs the selected model and molecules without calling
producer lowering or assembly. Candidate execution cannot call the source
evaluator. Shared codecs, exact arithmetic and canonical bytes are declared
trusted dependencies. No acceptance consumes a saved report or a candidate-owned
expected sequence, transition result, parameter or domain.

## 10. Required acceptance boundaries

The independent corpus must cover deadline equality and one tick too early/late;
different compliant actual/source delays; no antigen, no controller and missing
partner; RNA disappearance with persisting protein; stopping with restored gate;
reset during pending onset, active and stopping phases; stale old-generation
antigen; simultaneous cessation/restore; interrupted qualification; complete
reactivation; unknown evidence without physical OFF; impossible domain and
insufficient suffix; permanently OFF and irreversible-stop models; altered
operation/readout/clock/model parameters; wrong-recipient or duplicated state;
and each material/project/original-authority substitution, including repinning.

Tests of the current representation slice use literal independent expectations
and pure/static checks only. Native test sources, hosted execution, complete
installed/package/source inventory acceptance, independent artifact audit and
fresh integrated-main validation close later gates on their exact revision.
An inert peer tests orchestration; an artificial mechanism tests software; a
reference source check tests identity/fidelity. None substitutes for another.

## 11. Inert authoring descriptions and source snapshots

`biocompiler.policy.controlled_composition` provides typed preparation records.
Import these records from that submodule. They perform no I/O, source evaluation,
mechanism execution, empirical assessment or native/material admission. They are
not a complete component-material request. Their reserved schema identities do
not grant the capabilities specified in section 8.

`ControlledCompositionContractDescription` has the following exact fields:

| Field | Supplied value |
| --- | --- |
| `schema_version` | Fixed `biocompiler.policy_controlled_composition_contract.v0.1` |
| `profile` | Fixed `biocompiler.policy_controlled_composition_mrna.v0.1` |
| `products` | Exactly two ordered `ProductMemberBinding` records |
| `controller` | `ControllerBinding` |
| `readout` | `ActivityReadout` |
| `actual_delays` | `ActualActivityDelays` |
| `requested_deadlines` | `ActivityDeadlines` |
| `mechanism` | Fixed `deterministic_delay` |
| `initial_activity` | Fixed `background` |

The subordinate records are closed:

| Record | Fields |
| --- | --- |
| `ProductMemberBinding` | Original `product_parameter: Ref`, `member_id`, `cds_id`, `product_definition: DefinitionRef` |
| `ControllerBinding` | Original `definition: DefinitionRef`, `executor: Ref`; fixed `scope=executor` |
| `ActivityReadout` | Original `activity: Ref`, `definition: DefinitionRef`; fixed ordered `physical_bands=[background, active]` |
| `ActualActivityDelays` | `onset_ticks`, `cessation_ticks`, `reactivation_ticks` |
| `ActivityDeadlines` | `onset_ticks`, `controller_off_ticks`, `antigen_off_ticks`, `component_off_ticks`, `reactivation_ticks` |

All delays/deadlines are positive exact integers; Booleans and floats are not
ticks. The preparation helper's ceiling of 10,000 ticks is a representation
limit, not an admitted runtime budget. Product/member identities must be distinct.
Definition references retain exact original lowercase SHA-256 pins; the helper
never computes replacement definition pins. It does not compare actual delays
with requested deadlines: a contradictory supplied contract remains representable
for later native admission and requirement checking. Physical bands do not include
unknown; evidence status is a distinct later domain input.

`SourceAuthoritySnapshot` accepts a typed controlled-profile `BuildRequest`, the
typed contract description and complete supplied project context. It freezes
canonical bytes of exactly this envelope:

| Field | Meaning |
| --- | --- |
| `schema_version` | Fixed `biocompiler.policy_controlled_composition_source_authority.v0.1` |
| `document` | Complete original BuildRequest, including metadata and assumptions |
| `control_contract` | Complete description above |
| `project_context` | Exact `project_id`, `title`, `sources`, `assumptions` |

Each supplied source record preserves all existing ResearchProject `SourceRecord`
fields: `id`, `locator`, `version`, `sha256`, `role`, `reuse_terms`. This is supplied
context, not a checked ResearchProject. The snapshot binds one activity's original
identity, readout, executor and ordered product references to the description.
It does not resolve those references, verify original definition bodies or infer
that a product implements the requested activity.

Accessors return detached records; mutations cannot change captured bytes. Import
rejects normalization or repair that would alter original canonical authority.
`with_document` replaces only the source while preserving original contract
parameters, project provenance and pins; it never repins a foreign source to make
it acceptable. `native_status` and `material_status` are always `not_performed`.
Those status properties are not extra authority-envelope fields or proof records.

The full native authority bridge remains RC3 work: complete definition bodies,
selected model/domain/assembly/construction/material/context/resource subrecords,
joint request decoding, budgets, capability negotiation and independent native
checking are still required. No opaque placeholder claims to provide them.

The standalone originals in `data/controlled_composition_v01/source-wire/` freeze
one shape-only positive source and twenty explicit wire rejection mutations with
literal byte hashes. Codec acceptance is representation-only; the legacy
authoring checker still rejects the new profile and declaration. The existing
24 legacy source-document digest witnesses remain unchanged.
