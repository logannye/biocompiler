# CAR composition and reversible control implementation roadmap

Build a complete research workflow for a supplied split CAR whose two protein
products cooperate in the same human T cell and whose activity depends on an
external controller. The compiler will translate a typed program into two exact,
complete RNA specifications and independently check the requested bounded
behavior under explicit molecular and deployment contracts.

The selected example is an anti-CD19 split ON-switch CAR. Two mRNAs are the
proposed delivery architecture. Controller D is an external small molecule,
declared as a dependency with its own exposure contract. It is not a third RNA.
This work implements a concrete portion of E2 and E3 in the
[CAR expansion roadmap](car-mvp-and-expansion-roadmap-2026-10-10.md).

Status on 2026-10-12: implementation underway in the isolated
`work/car-controlled-composition` checkout. The checked milestone states and
evidence are recorded in [implementation progress](controlled-composition-progress.md).
The user has authorized artificial software fixtures while complete real RNA
inputs follow. Such fixtures cannot close the named reference's material gate.
Software acceptance under supplied contracts does not require proof that those
contracts hold in living cells. Empirical support, reference fidelity and
permitted use remain separately reported dimensions.

## Delivery outcome

A researcher can author or load the program, supply one complete paired
implementation, change supported requirements, compile, inspect a claim report,
export both RNAs and their manifest, and independently reverify the result using
the installed Verify executable and independently retained original inputs.

The first release supports one explicitly supplied implementation. It does not
search for a mechanism or optimize sequences. It reports every requested
requirement as supported and checked, contradicted, unknown, or unsupported;
strict behavioral completion cannot silently drop a requirement. A diagnostic
material-only result is explicitly partial and cannot receive the dynamic
profile's acceptance status.

The main engineering deliverables are a reusable controlled-composition profile,
one complete paired CAR research example, an independent verification path, and
an installed starter. Broad antigen logic, arbitrary composition, autonomous
mechanism discovery, continuous pharmacology, dose selection, manufacturing and
clinical authorization are outside this increment.

## Baseline and ownership

The inspected source baseline is E1 commit
`11b6b6da94497fea9afae8dfa12dd900c7295f9f`, tree
`7b1a04504970a91e2b3393a41f708555ee25b60c`, in
`work/car-second-reference`. E1 contains two separately compiled static CAR
references and local campaign preparation. Its native, installed and release
acceptance remain pending in the saved handoff. These identities identify the
planning baseline, not acceptance of this new extension.

The current [expression profile](car-expression-material-profile-design.md)
admits one RNA, one ORF and one product, with structural assurance and no temporal
execution. The wider compiler has finite behavior, modules, staged components,
multiple members, deployment contracts and independent verification. Their
existing admitted combinations do not implement this example:

- `policy/component_material.py` rejects combining the current finite-machine
  and multi-member options. Native material admission preserves that separation.
- The current source-to-implementation binding includes a product-bearing effect
  specialization. CAR signaling needs an explicit activity interpretation; it
  cannot inherit secretion or production semantics by changing a label.
- Current native effect execution explicitly rejects stop/cancellation. Current
  preservation coverage counts abstract active attempts. Neither establishes
  cessation or reactivation of a modeled receptor activity output.
- `ResearchProject` checks original request and limits for component routes.
  Its static expression route additionally binds project context into native
  authority. The new profile must preserve the complete relevant project context.

Preserve the frozen first-MVP owner and E1 checkpoint. Before implementation,
refresh their actual integration/publication state read-only, inspect attached
worktrees, and establish an owned extension checkout from the appropriate source.
Do not rebase, cherry-pick into, or restart another owner's active acceptance
candidate. Local independent work may proceed while prior delivery closes.

Before integration, reconcile with accepted main and resolve E1's documented
inventory/campaign overlaps. Its inherited semantic-inventory gap is already
recorded in `generated/car-second-reference/continuation.md`; it must not be
misclassified as a new extension regression. Refresh the gap against the selected
base before fixing it. Do not copy historical PASS records to a new revision.

The planning checkpoint was documentation only; implementation now proceeds on
the separate extension branch. Existing restrictions on E1 push, PR and hosted
execution remain in force for that checkout. No local native compilation,
execution, installation or packaging is authorized by this roadmap.

## Decisions for the first supported profile

| Decision | Initial scope |
| --- | --- |
| Intended deployment | Human immune cells engineered in vivo, with one T-cell executor role. Preserve source experiments in their actual context. |
| Molecular output | Two separately complete RNA members, one ORF and one encoded product per member; no delivered helper. Preserve all regions, chemistry and exact identities. |
| Functional organization | Recognition, controller-dependent cooperation and signaling contracts can share the two products. Behavioral module count is independent of RNA count. |
| Controller | One explicitly identified external controller. Its local availability is distinct from administration history. No dosing policy is generated. |
| Target context | One bounded active encounter slot, with explicit start, end and reset. Antigen is target/encounter scoped; controller and component availability are executor scoped. |
| Activity endpoint | A named CAR-mediated activity readout with a supplied observation map. Killing is a separate endpoint and remains unsupported unless its own contract is implemented. |
| Time | Finite sampled execution with exact clock units, horizon, onset and cessation bounds, and boundary conventions. No automatic claim between samples. |
| Quantities | Finite, explicitly defined activity and controller bands. Threshold interpretation and any approximation belong to pinned supplied contracts. |
| Reversibility | Activation, cessation and reactivation within the modeled availability window. Receptor shutdown does not erase completed effects. |
| Selection | One complete supplied implementation; no fallback, sequence optimization or automatic partition search. |
| Unknowns | Preserve absent, stale, invalid and conflicting evidence. An evaluator's missing observation is not a cellular OFF signal. |
| Compatibility | Add a closed versioned profile. Preserve existing request bytes, capability declarations, rejection behavior and canonical examples. |

The frozen neutral working name is `controlled_composition` v0.1. RC1 assigns
the exact schema names after checking registry collisions. The schema belongs to
the existing component-material toolchain; it does not create another compiler.
Do not expose a collection of Boolean feature switches that accidentally admits
unreviewed combinations.

## Behavioral contract

The source program and supplied mechanism have separate authority. The source
states what is required. The mechanism states how the selected products are
modeled to achieve it. The checker compares them without deriving the mechanism's
behavior from the requested answers.

1. **Activation.** With both products available in the same recipient and valid
   antigen engagement plus controller enablement sustained for the specified
   interval, the activity readout reaches the required active band within the
   source deadline. Define explicitly what happens when an input changes during
   that interval. New activation requires both antigen and controller enablement;
   neither input alone may initiate it. Allowed residual/background activity has
   its own bounds and cannot be relabeled as a new activation.
2. **Disabled activity.** With controller exposure in the declared disabled
   band, activity settles into the permitted background band within the source
   cessation deadline. Loss of antigen engagement has a separately declared
   bounded cessation rule in the same original contract, including any permitted
   residual activity. Initial antigen absence also prohibits new activation.
3. **Reactivation.** Following a supported shutdown, restored enabling conditions
   must produce another active interval within the declared response bound on
   every admitted execution with sustained restored conditions, while component
   and host assumptions continue to hold. A permanently inactive candidate fails
   this requirement. A successful witness establishes non-vacuity, not universal
   response across the bounded domain.
4. **Availability.** Track RNA and protein availability separately for A and B.
   Product presence in different cells cannot satisfy same-recipient cooperation.
   Availability is a modeled condition or deployment premise, not an invented
   sensor inside the cell. Loss of a premise must be exposed as a contract-domain
   failure or unresolved behavior unless a supplied mechanism covers it.
5. **State and lifecycle.** Assign one owner to each assembly/control state,
   timer and activity output. Controller state belongs to the executor; target
   engagement belongs to its encounter. Specify reset, simultaneous event order,
   activation/cessation priority and repeated input changes. Do not confuse a
   stop request with observed cessation or acknowledgement.
6. **Unknown information.** Preserve physical input state separately from its
   evidence status. Evaluate unresolved possibilities conservatively or return
   an explicit unknown result. Withholding software assurance is not a physical
   safety action.
7. **Finite coverage.** Check the entire admitted bounded input/state domain,
   including transitions and non-vacuous active, inactive and reactivation
   witnesses. A selected demonstration trace is insufficient. Resource exhaustion,
   a truncated domain or an unfinished deadline at the horizon cannot be PASS.

RC1 freezes initial states, event ordering, legal input histories, supported
parameter ranges, horizon/suffix handling and the observation map in a decision
record. The first mechanism can use a finite supplied transition model with
explicit delayed states. If its uncertainty requires nondeterminism, either
check every admitted successor or reject that contract as unsupported. Do not
silently choose a favorable realization. Continuous-time and stochastic claims
need a later admitted interpretation.

No biological numerical threshold is assumed by this roadmap. Artificial test
fixtures may use small explicit tick counts and activity bands, clearly labeled
as software inputs. A real research pack records whether each value is measured,
source-derived, designer-supplied or unresolved.

## Original authority and emitted artifacts

The immutable request must retain the following complete bodies and their
versioned identities:

| Input | Required content |
| --- | --- |
| Program | Requirements, roles, observations, encounters, effects/activity endpoint, clocks, state, transitions, unknown behavior and source correspondence. |
| Deployment | Human target, recipient/compartment assignments, co-delivery relationship, host/environment assumptions and member-specific availability contracts. |
| Implementation | Both products, interaction and activity contracts, observation mappings, module ports, wiring, state owners and dependencies. |
| Material | Independent full RNA layouts/fragments, CDS/product mappings, member order, end chemistry and every manifest-only feature. |
| External controller | Exact identity, exposure interpretation, provider scope and mechanism binding; no implicit RNA helper or inferred dose. |
| Verification domain | Clock and horizon, finite input alphabet, initial states, parameter domain, exploration and publication budgets. |
| Provenance | Complete relevant project context, source records, original experimental context, evidence assertions, assumptions and asset distribution terms. |

Preserve independent originals outside the exported candidate. Candidate-local
hashes and bundled copies alone cannot establish authority. Bind the complete
new project context in the native original envelope or a versioned independently
checked enclosing authority; simple display metadata must not substitute for
that check. Preserve historical project schemas unchanged.

Reuse the existing atomic `program.fasta` plus `manifest.json` export shape if it
can carry the full new contract. FASTA has exactly two ordered records. The
manifest retains both complete nominal molecule specifications, original
request, candidate, controller dependency, model/domain/limit identities,
correspondence, claim results and unresolved assumptions. Archive receipts and
timing logs remain separate from canonical design identity.

The report exposes structural/material validity, conditional behavior checking,
domain coverage, empirical applicability and use status separately. Missing
behavioral authority permits preparation and diagnostics but prevents a complete
dynamic acceptance. Unresolved empirical applicability remains visible without
automatically defeating a valid conditional software result.

## Work packages and acceptance gates

Dependencies: RC0 establishes the implementation base. RC1 and RC2 can proceed
in parallel. RC3 follows the RC1 interface freeze and can start with artificial
complete authority. RC4 and RC5 can overlap after those interfaces stabilize.
RC6 requires their joined path. RC7 validates the coherent candidate. RC8 closes
integration and delivery. RC2's complete named example is required before calling
the selected CAR use case complete; empirical validation remains a separate lane.

### RC0 Establish the extension baseline

Completed locally in the [progress record](controlled-composition-progress.md).
The implementation base is frozen MVP source `0b19ef68`; the E1 source above
remains the planning baseline. MVP/E1 acceptance is not inherited.

- [x] Read current handoffs, refresh prior delivery state without mutation, and
  record the base revision, branch ownership and inherited known failures.
- [x] Reuse an appropriate owned worktree or create an isolated managed worktree
  with a `codex/` branch. Keep the first-MVP and E1 acceptance revisions intact.
- [x] Record current admitted profiles, operation/capability inventories and
  relevant dependency closure. Select local checks from this actual inventory.
- [x] Create a checkpoint record distinguishing planned, implemented, locally
  checked, hosted-validated, installed, released and empirically assessed states.

**Exit:** an owned reproducible starting point and explicit integration path;
no inherited acceptance is attributed to the extension.

### RC1 Freeze semantics and public interfaces

Completed as a locally checked representation/design checkpoint. Native
admission, behavior execution and complete molecular authority remain RC3-RC5.
See the [progress record](controlled-composition-progress.md) for exact validation
evidence and the distinction between declarative expected cases and execution.

- [x] Write an architecture decision and the new closed profile specification.
  Freeze the scope and behavioral decisions above, including contract-domain
  violations, observation meaning and finite coverage.
- [x] Define the receptor activity operation/readout explicitly. Reuse existing
  `EffectLifecycle` vocabulary only where it describes the intended semantics;
  add the necessary admitted operation and output mapping. Do not model a
  receptor as secreting or newly producing its already encoded components.
- [x] Define typed original-authority, build and control-contract helpers using
  the existing `Program`, `Deployment`, `ImplementationCatalog` and `BuildRequest`.
  Python constructs descriptions; it does not execute cellular control flow.
- [x] Specify request, candidate, report, project and manifest versions,
  capability negotiation, limits, diagnostics and backward-compatibility rules.
- [x] Extend the independently versioned wire specification first, then regenerate
  the OCaml shapes and verify Python/native conformance. Freeze canonical positive
  and negative schema fixtures; do not infer the specification from one decoder.
- [x] Design independent minimal fixtures: an accepted on/off/on case and
  constant-ON, permanently-OFF, irreversible-stop and wrong-scope counterexamples.

**Exit:** reviewed source-to-model-to-material mapping, immutable interface
fixtures and an acceptance matrix with no undecided semantic shortcuts. Native
acceptance remains pending.

### RC2 Acquire and qualify the paired reference inputs

The selected reference is now independently named `WO2014127261A1-197-206`.
Its patent figures explicitly pair #197 and #206. Literal coding fragments and
products were reconciled against a separately entered printed sequence listing,
with exact source hashes and join records in the
[acquisition assessment](car-controlled-reference-acquisition.md). This is
same-operator manual reconstruction with consistency checks, not an original
deposited construct or complete RNA design. Identity with Wu's I.b + II.d pair
remains unverified and is not required for this separately named reference.

- [x] Start with Wu's split ON-switch CAR as inspiration and select the explicitly
  paired patent reference. Reconcile the literal two products, sequence blocks
  and junctions with the source records without asserting an unverified Wu join.
- [ ] Inventory two complete RNA designs, exact regions, product translation,
  chemistry, source hashes, construct-to-assay joins and distribution terms.
  The published mechanism does not itself supply our two-mRNA implementation.
- [x] Label publication facts, explicit designer choices, supplied behavioral
  assumptions and unknowns separately. Do not silently repurpose either E1
  full-length CAR sequence into a split product.
- [x] Retain source experimental context and an applicability assessment for the
  intended human in-vivo RNA deployment. Scope every kinetic/activity assertion
  to its actual readout and experiment.
- [ ] Produce a versioned paired reference pack, independently declared expected
  material, source consistency checker and qualification note.

**Exit:** a complete, reproducible original-input pack for the named example,
with explicit ownership of every designer-supplied choice. Unresolved functional
evidence remains a reported empirical gap. Missing exact products or complete
RNA designs leave this gate open while artificial-contract software work proceeds.
If assets cannot be redistributed, supply a reproducible authorized-input import
path with independent identity checks; do not bundle them by assumption.

### RC3 Add typed admission and the native dynamic profile

- [ ] Extend Python authoring, canonical serialization and transport for the
  exact new profile, keeping legacy finite and static-expression paths unchanged.
- [ ] Add native admission across original source, realization request, component
  assembly, material context and deployment. All profile discriminants must agree.
- [ ] Extend source document decoding, type checking, operational lowering and
  source correspondence for the activity family and mixed observation scopes.
  Executor-local controller exposure must not be forced into a target-local
  antigen slot to fit the older admission shape.
- [ ] Version the operating domain and reference adapter for finite activity/input
  bands, executor-local inputs, encounter lifecycle and availability. Their
  current Boolean encounter-local input assumptions cannot enumerate this new
  domain unchanged. Test each scope and transition independently of the producer.
- [ ] Admit the scoped antigen/controller inputs, required activity semantics,
  finite state and two-member material together. Reject unsupported extra inputs,
  hidden helpers, broadened encounters and unavailable primitive interpretations.
- [ ] Add Core/Verify capability advertisement, operation dispatch and complete
  response decoding. Unsupported binaries must reject clearly, without fallback.
- [ ] Bind project context, controller definitions and all execution/publication
  limits into original authority before candidate generation.

**Exit:** complete request round-tripping and precise admission diagnostics in
local transport/static tests, plus native test sources covering each acceptance
boundary. A mocked peer establishes orchestration only.

### RC4 Construct and check the complete two-member payload

- [ ] Reuse staged component construction and independent material checking.
  Preserve exact member/product/ORF mappings, every RNA region, translation,
  chemistry, member order and total/per-member constraints.
- [ ] Bind recognition/control/signaling ports to the supplied pair, with explicit
  localization, resources, same-recipient placement and dependency closure.
  Preserve supplied expression/stoichiometric operating ranges where the
  interaction contract requires them; binary presence alone cannot prove assembly.
- [ ] Keep physical product membership distinct from behavioral state ownership.
  A shared controller or state must not be duplicated once per RNA.
- [ ] Independently reconstruct both molecules from original material authority.
  Reject missing, extra, swapped or cross-reference members and locally repinned
  foreign candidates. Check UTR/chemistry changes even when protein is unchanged.
- [ ] Make two-member publication atomic. Preserve existing outputs on failure,
  cancellation, limit exhaustion or incomplete verification.

**Exit:** a complete structural checkpoint for the exact pair, with fresh
independent reconstruction tests. It carries no reversible-behavior completion
claim until RC5 and the joined RC6 path pass.

### RC5 Implement and independently verify reversible behavior

- [ ] Lower the source requirements to the existing executable infrastructure
  with the new admitted activity interpretation, explicit observations, timers,
  state, ownership and lifecycle correspondence.
- [ ] Implement source execution, independent candidate activity primitives and
  requirement monitors for this profile. Add actual modeled cessation semantics;
  retain legacy stop/cancellation rejection outside the new admitted family.
- [ ] Reconstruct the selected component assembly from original contracts in the
  checker. Candidate execution must not invoke the source evaluator, and the
  checker must not trust producer-supplied outcomes or expected material.
- [ ] Check scoped module assumptions/guarantees and dependency wiring. Establish
  the first compositional rule against whole-program bounded checking; do not
  rely solely on each module passing in isolation.
- [ ] Check activation, cessation, background limits and reactivation over the
  complete admitted bounded domain, preserving unknowns and finite suffix rules.
  Measure coverage at the controlled activity output rather than at abstract
  effect attempts; require an inactive/active/inactive/active witness.
- [ ] Check domain enumeration and the independent reference adapter directly:
  executor-scoped controller/availability survives encounter reset/end, while
  target-local engagement resets correctly. No branch is removed merely because
  it causes failure or unknown. Every explicit domain exclusion remains visible.
- [ ] Check member-specific availability and controller exposure interpretation.
  Distinguish missing evidence, violated deployment assumptions and modeled
  physical loss. Include every requested assumption in the result.
- [ ] Preserve exact work/state/history accounting, cancellation and bounded
  counterexample reporting. A reduced counterexample must retain the failure.

**Exit:** independent source/candidate agreement and requirement checks over the
declared finite domain, non-vacuous reversible witnesses, and rejection of the
behavioral counterexamples. All claims remain conditional on supplied contracts.

### RC6 Complete the researcher workflow

- [ ] Add the new profile to `ResearchProject` with explicit limits and complete
  project-context binding, preserving existing v0.1/v0.2 project behavior.
- [ ] Provide a typed example and editable starter: prepare, inspect/preflight,
  compile, explain, export and fresh Verify-only reopen. Use public interfaces.
- [ ] Support meaningful edits: RNA-size bounds, requested onset/cessation
  deadlines, horizon and explicitly supported material/reference choices. Edits
  must change a checked result or produce a specific rejection; they must not
  rewrite the mechanism contract to satisfy the request automatically.
- [ ] Show activity endpoint, two products, controller dependency, time bounds,
  same-cell assumptions and empirical status in plain language.
- [ ] Preserve the FASTA/manifest pair, independently supplied original project,
  complete limit equality and every exported byte during reopen. Bind relevant
  provenance so a changed assumption cannot retain an old verification result.
- [ ] Complete a timed installed rehearsal with independent original inputs,
  accepted and rejected edits, and an unmodified Verify-only consumer workflow.

**Exit:** the named example runs through installed public interfaces outside the
checkout, without manual JSON surgery or private test helpers. Report automation
timing separately from any human usability observation.

### RC7 Validate the coherent implementation

- [ ] Extend native suites, SDK development and installed campaigns, source/context
  and semantic coverage, material-rule ledgers, public API coverage, migration
  inventory, package-data checks, source companions and starter checks.
- [ ] Freeze independent originals and expected artifacts before the acceptance
  run. Record the complete new observation/action/file census; retain every prior
  required case. Do not guess future totals from today's inventory.
- [ ] Run focused local pure-Python tests and both required typing configurations;
  refresh reviewed static source pins and record the exact exercised scope.
- [ ] Run the authorized coherent hosted development gate. Automatic scoped
  routing is absent at this baseline, so use the supported complete workflow
  until an independently admitted scoped runner exists.
- [ ] Run complete cross-platform, installed Python 3.11/3.14, integration and
  reproducibility checks on the frozen candidate. Verify-only cases retain the
  existing required offline/network-denial controls.
- [ ] Independently audit original authority, binaries, all owned bytes, complete
  action accounting, source/run/attempt/platform identities and rejection results.

**Exit:** fresh candidate-bound software acceptance with no missing, skipped,
canceled, stale or synthetic stand-ins for required execution. A changed candidate
requires fresh affected gates; historical success is not transferable.

### RC8 Integrate and release

- [ ] Reconcile the feature with accepted main and any E1 integration, recheck
  dependency closure and resolve overlaps without losing either static reference.
- [ ] Complete the required review and integration gates, merge through the normal
  owned workflow, and run fresh actual-main validation and artifact audit.
- [ ] Publish matching installable compiler/verifier assets, starter, original
  input or acquisition path, support table, qualification notes and quickstart.
- [ ] Verify release assets and the documented outside-checkout workflow against
  the exact accepted source and platform manifests.
- [ ] Publish a handoff with completed/open states, exact evidence and empirical
  limitations. Leave later quantitative optimization and broader logic separate.

**Exit:** a usable shipped controlled-composition research workflow. Physical
delivery, measured reversible performance and clinical outcomes retain their own
evidence requirements and are not declared complete by the release.

## Acceptance matrix

| Family | Required cases and expected distinction |
| --- | --- |
| Basic control | All antigen/controller combinations; active and inactive witnesses; no permanent-OFF vacuous pass. |
| Reversibility | Off/on/off/on, repeated controller changes, interrupted activation, cessation and reactivation deadlines, and an irreversible-stop rejection. |
| Temporal boundaries | Exact deadline, one tick too early/late, initial active state, simultaneous input/encounter events, reset, end-of-horizon outstanding obligations and clock-unit mismatch. |
| Endpoint meaning | Activity vs expression vs killing, stop request vs acknowledgement vs cessation, and unsupported downstream outcome requests. |
| Scope and availability | Missing A/B, delayed arrival, unequal protein lifetime, expired reactivation, different-cell placement, wrong compartment, operating-range mismatch and same-population substituted for same-recipient. Executor inputs survive encounter reset/end. |
| Unknowns | Missing/stale/invalid/conflicting antigen or controller evidence; evaluator missingness vs physical signal absence; unknown availability; no silent safe-OFF inference. |
| Composition | Swapped ports, wrong pair/model, duplicate state ownership, omitted dependency, shared resource overcommit and locally passing modules with a failing composed behavior. |
| Material | Every member, CDS, UTR, tail, chemistry and ordering mutation; full product translation; extra helper/ORF; size bounds; foreign candidates with complete local repinning. |
| Authority | Changed program, mechanism, context, evidence, controller, horizon or limits; stale reports, cross-project ZIPs and candidate-owned expected values. |
| Resource and publication | Work exhaustion, cancellation, decode/response limits, missing second member, interrupted export and rejection leaving no partial accepted archive. |
| Installed workflow | Core/Verify role isolation, exact package/RECORD data, independent originals, fresh export/reopen and matching artifacts across required slots. |
| Compatibility | Original static references and finite/multi-member cases preserve canonical inputs, outputs, supported claims and explicit rejection of unadmitted combinations. |

Each row maps to named tests and retained observations before RC7. The acceptance
census independently accounts for every required result and file. Expected outputs
come from separately reviewed originals, never from the candidate under test.

## Code ownership and change map

These are current extension points, not a requirement to edit every listed file.
New source/test filenames and final schema literals are assigned in RC1.

| Area | Existing files to reuse or extend |
| --- | --- |
| Typed source and build | `src/biocompiler/policy/model.py`, `serialization.py`, `finite_build.py`, `modules.py`, `module_linking.py`. |
| Wire and source semantics | `tools/generate_policy_wire_schema.py`; native policy document, checking, admission, operational lowering and source correspondence modules; `core/lib/semantics/policy_execution.ml` and requirement monitors. |
| Domain and reference execution | Native `policy_operating_domain.ml` and `policy_domain_reference.ml`, finite-domain enumeration and independent source-to-reference adaptation. |
| Python material transport | `src/biocompiler/policy/component_material.py`, `src/biocompiler/core_policy_component_material.py`. |
| Native original authority | `core/lib/domain/policy_realization_request.ml`, `policy_component_material_request.ml`, `policy_component_assembly_rule.ml`, `policy_component_context.ml`, and corresponding interfaces. |
| Source and primitive correspondence | `core/lib/checker/policy_implementation_binding_check.ml`, `core/lib/domain/policy_implementation.ml`, `core/lib/compiler/policy_implementation_lowering.ml`, `core/lib/candidate_runtime/policy_primitives.ml`. |
| Assembly and behavior verification | `core/lib/realization_checker/policy_component_assembly_check.ml`, `policy_component_material_check.ml`, `policy_component_context_check.ml`, `policy_preservation_check.ml`. |
| Generation and native services | `core/lib/producer_service/policy_component_material_producer.ml`, `core/lib/service/policy_component_material_service.ml`, capability/dispatch registration and corresponding interfaces. |
| Public project and reference | `src/biocompiler/policy/research_project.py`; a new paired factual pack and authoring helper alongside `car_reference.py`, with no changes to legacy pack identity. |
| Test families | `core/test/test_policy_component_material_request.ml`, `test_policy_component_assembly_check.ml`, `test_policy_finite_machine.ml`; Python finite-build, multi-member, research-project and CAR campaign test families. |
| Campaigns and distribution | `tools/check_policy_development.py`, multi-member/finite installed witnesses, `tools/check_car_payload.py`, `check_car_payload_installed.py`, `car_payload_starter.py`, package/starter inventories and hosted workflow registration. |
| Static coverage | `protocol/policy-semantic-coverage-v0.1.json`, `policy-source-context-coverage-v0.1.json`, `policy-material-rule-coverage-v0.1.json`, component/public API ledgers and `migration-inventory.json`. |

Native test registration includes `core/test/dune` and
`tools/ci_native_bundle.py`; service/schema changes also require protocol and
conformance registration. Distribution checks cover package data, RECORD entries,
linked source companions, both supported platforms and both Python slots.

## Execution sequence starting today

The first useful implementation checkpoint is RC0–RC1 plus a complete authority
fixture and typed admission skeleton from RC3. Begin RC2 reference acquisition
in parallel. Once the interfaces are frozen, split implementation into three
non-overlapping workstreams:

| Workstream | Responsibility | Join condition |
| --- | --- | --- |
| Semantics and native checking | RC3/RC5 source, activity interpretation, execution and independent preservation. | Shared schema, operation semantics and domain are frozen before parallel edits. |
| Material and reference | RC2/RC4 exact paired inputs, construction, placement and independent expected material. | Product/member/port identities agree with the same original authority. |
| Public workflow and acceptance | RC6 and RC7 campaign preparation, project/export binding, diagnostics and installed starter. | Can use inert peers for preparation, but only real native/installed runs close acceptance. |

One integrator owns shared schema, dispatch and inventory files. Assign tests and
production modules to distinct owners to avoid overlapping writes. An independent
reviewer checks authority boundaries, endpoint meaning and coverage before the
first hosted batch. Preserve useful local checkpoints and continue independent
work while healthy hosted checks run.

Aim first for a complete structural two-RNA checkpoint, then the joined bounded
reversible workflow. Set calendar estimates after RC1 and RC2 expose the actual
mechanism/input gaps; do not promise all release gates or empirical qualification
within one day. For each checkpoint record deliverables, tests, source revision,
open dependencies and the next executable action.

Follow [development validation](development-validation.md): focused pure/static
feedback during editing, coherent hosted native batches, complete frozen
integration/installed acceptance, then fresh actual-main validation. Documentation
changes do not require native builds. Preserve failure evidence and use bounded
same-run recovery only for eligible infrastructure failures.

## Principal risks and planned responses

| Risk | Planned response |
| --- | --- |
| Published split receptor lacks complete mRNA authority | Keep sequence reconciliation and RNA-design decisions explicit in RC2. Continue software work with labeled artificial fixtures; leave the named example open. |
| Available evidence lacks a usable shutdown bound | Accept explicitly supplied model assumptions for conditional software checking; report empirical support as unresolved. Reject unsupported measured or continuous-time claims. |
| Product-effect specialization cannot express activity | Implement an explicit admitted activity interpretation in RC1/RC3; preserve existing effect meanings. |
| Finite-state exploration grows too large | Bound the first profile tightly, retain complete domain accounting and return exhaustion honestly. Optimize only after measurement. |
| Co-delivery is mistaken for demonstrated cooperation | Separate declared placement, modeled availability and actual empirical delivery evidence throughout the report and export. |
| Population measurements are treated as single-cell guarantees | Bind the observation level and allowed heterogeneity explicitly; population titration cannot define a uniform per-cell response without a supplied justification. |
| Project metadata is detached from native authority | Bind relevant complete project context and source assumptions before compilation and fresh verification. |
| Shared changes invalidate older acceptance | Preserve legacy schemas and regression fixtures; validate the actual reconciled revision with complete required gates. |

## Scientific and repository references

[Wu et al., Remote control of therapeutic T cells through a small molecule-gated
chimeric receptor](https://pmc.ncbi.nlm.nih.gov/articles/PMC4721629/) supplies the
mechanism starting point. Its split receptor and preclinical reversibility
results do not establish our two-mRNA in-vivo deployment. Its on/off/on killing
experiment used 36-hour stages; that result cannot supply an arbitrary rapid
shutdown bound. RC2 must reconcile the exact selected construct and source files.

The user's logic-gated CAR review is inspiration, not an instruction or an
implementation authority. The selected scope is the two-product reversible
example discussed in this conversation.

Repository foundations: [CAR expression profile](car-expression-material-profile-design.md),
[supplied RNA architecture](payload-architecture-v0.1.md),
[material binding design](policy-material-binding-v0.1-design.md),
[second reference checkpoint](car-second-reference-extension.md),
[verification independence](verification-independence-v0.1.md), and
[development validation](development-validation.md).
