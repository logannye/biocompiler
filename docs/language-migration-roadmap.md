# Biocompiler language migration: session roadmap

Created: 2026-10-01, America/Los_Angeles.

**Decision:** TypeScript for Studio; Python for authoring, orchestration and scientific exploration; OCaml for the semantic compiler, independent checking and canonical emission.

**Resumed migration checkpoint, 2026-10-02:** PR57 and PR58 passed all 36
exact-head jobs and are merged. Independent aggregate reconstruction, both
platform binary manifests and all four full artifact comparisons reproduce their
hosted receipts. Source, tested and integrated trees are identical; see the
[protocol/workflow validation record](../protocol/migration-realization-protocol-workflow-validation.json).
Later PR59–68 still require successful corrected gates. The resumed session
implementation is additive source work with Python process tests; native
compilation, installed replay and full public-manager integration remain pending.
The [archived scaffold](migration-pipeline-session-scaffold.md) records the earlier
credit-limit draft, not the current implementation status.

**Callback foundation checkpoint:** deferred native manager operations, retained
Python object capabilities, nested framed continuations and a typed Python
transport are now implemented as additive libraries. Three new hosted native
suites bring the required inventory to 101. The standalone verifier remains
separate. A manager application dispatcher, public typed adapters, complete
installed callback replay and default cutover remain open. The PR69 compilation
warning was corrected at `85dfc8ca114ea629ad1f65eb010d0a635f71d556`;
its replacement [hosted run](https://github.com/logannye/biocompiler/actions/runs/37036025402)
is pending. Neither the correction nor the new libraries is a native PASS.
PR70 also required a documentation-spacing correction after warning 50 in
`callback_channel.mli`; corrected source `6c31b59a789a0b5a8d8b8edc6fea93d586292d78`
is awaiting [replacement hosted validation](https://github.com/logannye/biocompiler/actions/runs/37041405310).
The [callback source checkpoint](../protocol/migration-pipeline-callback-checkpoint.json)
pins the implemented files, 134 passing local Python checks, strict typing across
19 modules and the unresolved native/public integration gates.

**Live manager source checkpoint:** the Core-only application dispatcher, typed
Python adapter and installed identity campaign are implemented. Native suite 102
and a complete four-runtime comparison are wired into existing hosted gates.
The default remains Python. See the [manager implementation](migration-pipeline-manager.md)
and [source checkpoint](../protocol/migration-pipeline-manager-checkpoint.json).
PR70's exact source-list test also needed the two reviewed callback additions;
corrected source `40fad81c5124f540c56914816f4bf21c077ac059` now awaits
[replacement validation](https://github.com/logannye/biocompiler/actions/runs/37046030719).
The earlier PR70 runs are superseded, not acceptance evidence.

PR71 source `5568a0f7135efc042e95a0a25a67e77e678bb659` is now pushed as a
[draft checkpoint](https://github.com/logannye/biocompiler/pull/71). In
[run 37046612682](https://github.com/logannye/biocompiler/actions/runs/37046612682),
Linux job `110969508717` has completed compilation and the complete native literal
and mutation-suite step successfully. The rest of that job, macOS and installed
replay remain pending; this is partial hosted evidence, not final acceptance.
The next branch implements ordered inspection and complete live comparison replay.

The [next-phase biological handoff](biological-correctness-next-phase-handoff.md)
is preserved as future-session context. Its BC checklist remains unexecuted;
finish the LM release and cutover gates before that separate development phase.

**Installed-fixture correction:** subsequent PR71/72 unit runs exposed assumptions
about checkout traceback filenames and the origin of an already installed
package. The frozen deferred oracle, all 47 case bodies and the production import
guard remain unchanged. An additive checker retains complete raw observations,
binds loaded functions to their source and module namespace, and checks two exact
interpreter-frame correspondences against independently executed primitives.
All 17 focused tests pass on local Python 3.11.15 and 3.14.6; four source/installed
origin controls also pass. The [correction record](../protocol/migration-deferred-runtime-correction.json)
is pushed in PR70 `c7f91226f260b64c52556fc8cda87e533ea0ccac`
([run](https://github.com/logannye/biocompiler/actions/runs/37055359931)),
PR71 `76349a197a937ca9d3653600396851054298509a`
([run](https://github.com/logannye/biocompiler/actions/runs/37055362599)), and
PR72 `b28ce4cef6786212bda97abc33cd075a619c506b`
([run](https://github.com/logannye/biocompiler/actions/runs/37055359590)).
These replacement runs remain pending; earlier runs are superseded for acceptance.

- [x] **LM-03/12 realization protocol hosted checkpoint (PR57):** run
  `36987943622`, source `41ab0f99375d7293a4b86c28da1cd5408b7376c0`,
  integrated `71c56d2fc2eecbdb9efbb3da1e9d82a25c8b4e22`: all 36 jobs,
  2,505 tests per Python version, 6,719 protocol and 4,157 SDK checks per role,
  complete four-runtime equality and rehashed native executable authority.
- [x] **LM-03/25 workflow engine hosted checkpoint (PR58):** run
  `36987950690`, source `241bd423b3b1b877d03c2a556b325994ffe8633b`,
  integrated `15c58934619909d5a8b97e1aa1f3cc556b010c3d`: all 36 jobs,
  2,528 tests per Python version and the complete native workflow engine corpus.
  Descriptor service, installed public routing and export integration remain open.
- [ ] **LM-03 PR57/58 separate integrated-main runs:** their merge trees equal
  the tested trees, but the new main push runs remain a separate pending gate.

- [x] **LM-03 CI native fixture wiring:** bind every registered Dune fixture in
  the complete native-suite step and add an exhaustive source regression.
- [x] **LM-03 complete unit-plan transport:** use matching bounded 64 MiB plan
  readers/writers while retaining 20 MB limits for other shard JSON. The focused
  campaign passes 33 tests, including a complete plan exceeding 20 MB, exact
  byte boundaries, atomic writer failure and full plan/run/accounting traversal.
- [x] **LM-03 resumed gate corrections:** the exact earliest leaf diagnostic,
  complete eight-operation inspection census and individually pinned unused CLI
  transport source lineage are corrected and pushed across PR59–68. All original
  CLI children and full source/artifact comparisons remain required.
  [Exact corrected heads](../protocol/migration-resume-gate-corrections.json).
- [ ] **LM-03 corrected hosted acceptance:** require all 36 jobs on the corrected
  heads, including full unit accounting and both native platforms, before merge.

**Status:** the default remains Python; explicit architecture SDK/CLI selection uses the validated OCaml core. PR48–58 have completed their exact-revision gates and are integrated (PR52 through PR53). PR59–65 preserve descriptor workflow services, public workflow routes, synthetic producers, installed SDK/CLI integration and rich native inspection; their complete corrected-revision gates remain pending. The current P2 checkpoint implements native checked-manager contracts, lifecycle authority and fixed synthetic/component pipelines, with complete original Python captures retained and hosted native validation pending. Distribution, remaining profiles, public native pipeline/package authority and default cutover remain open.

The validated foundation is merged in [PR37](https://github.com/logannye/biocompiler/pull/37), with the exact revision/platform results in the [foundation receipt](../protocol/migration-foundation-validation.json). Typed request, all 42 Behavior operations and molecular-coordinate domains are merged in [PR38](https://github.com/logannye/biocompiler/pull/38); the [domain receipt](../protocol/migration-domain-validation.json) records both native platforms and full Python/integration checks. Both integrated main revisions also passed their required gates.

Circuit declarations and independent source-to-Behavior correspondence are merged in [PR39](https://github.com/logannye/biocompiler/pull/39), main revision `c0c15d9b535a5ddda4f4e59cf392d419524ab26f`. The [source-correspondence receipt](../protocol/migration-source-correspondence-validation.json) records nine native suites on Linux x86_64/macOS arm64, 936 protocol checks and exactly 2,084 tests on each Python version. The integrated main [run 36929139838](https://github.com/logannye/biocompiler/actions/runs/36929139838) passed. This establishes source correspondence only.

[PR40](https://github.com/logannye/biocompiler/pull/40) is merged at `10382dd5c662c924a460a5113cbd5d58b3dffe48`. Its [reference-execution receipt](../protocol/migration-reference-execution-validation.json) binds source `e4846f0`, tested merge `7e321bb` and the successful [complete run 36935066451](https://github.com/logannye/biocompiler/actions/runs/36935066451): 2,095 tests on each Python version, 12 native suites on both platforms, 936 protocol checks and all installed, browser and reproducibility gates. Per-role source execution, typed execution records and exact numeric compatibility are validated. The separate [post-merge main run 36936774523](https://github.com/logannye/biocompiler/actions/runs/36936774523) passed every required gate. No runtime operation or production routing was added.

[PR41](https://github.com/logannye/biocompiler/pull/41) is merged at `e3d3cbcf1a7b05ccdbc34fdb69127c22e8ea8345`. Its [lowering/domain receipt](../protocol/migration-lowering-contracts-validation.json) records source `569b430`, tested merge `2f70984`, all 17 native suites on both platforms and all 2,122 tests on each Python version in successful [run 36935530782](https://github.com/logannye/biocompiler/actions/runs/36935530782). All installed, browser and reproducibility gates passed; the integrated tree is identical to the validated source. Separate [main run 36937189850](https://github.com/logannye/biocompiler/actions/runs/36937189850) passed every required gate.

[PR42](https://github.com/logannye/biocompiler/pull/42) is merged at `f278ce01336c537d250df4f90219903a25174ae0`. Complete component records, intact human source wrappers, molecular inventories/sets and exact decimal deployment declarations passed all PR and integrated-main gates; the [receipt](../protocol/migration-complete-domains-validation.json) records 22 native suites on both platforms, 2,155 tests on each Python version and all product gates. [PR43](https://github.com/logannye/biocompiler/pull/43) validated architecture leaves, transition/recoding and construction records plus independent required-region checking: all 28 native suites on both platforms, 2,207 tests per Python version and every product gate passed. Its [receipt](../protocol/migration-construction-domains-validation.json) pins the source, tested merge and identical integrated tree. [PR44](https://github.com/logannye/biocompiler/pull/44) is merged at `e24ef03261ab46689a2c2cb8434aa24280eab028`: complete refinements/templates, independent construction reconstruction and source-manifest checking passed all required PR gates, with 34 native suites on both platforms and exactly 2,244 tests on each Python version; [receipt](../protocol/migration-reconstruction-validation.json). Its separate integrated-main run passed every required gate at the merged revision. [PR45](https://github.com/logannye/biocompiler/pull/45) validates complete architecture records, independent controls/deployment proofs and fresh architecture acceptance; full PR and integrated-main validation passed. Coupled transport, producer/construction emission, installed export acceptance and cutover remain incomplete.

**Validated baseline:** package 0.1.0.dev29, commit 6156ed2841fd3308df833f1afe0e3f6af5d12bf6. [Hosted run 36900639059](https://github.com/logannye/biocompiler/actions/runs/36900639059), attempt 2, passed all required gates and exactly 2,001 discovered tests on each Python version (3.11.16 and 3.14.7). The first attempt lost a hosted runner; the retry passed. [Pinned baseline receipt](../protocol/migration-baseline.json) retains revision, tree, receipts and shard/job timings. New revisions rediscover their own tests; this count is not the migration acceptance target.

Governing references: [language decision](decisions/0007-language-boundaries-and-ocaml-core.md), [architecture](architecture.md), [toolchain contracts](toolchain-contracts.md), [development validation](development-validation.md), [verification independence](verification-independence-v0.1.md), and [existing product roadmap](roadmap.md).

## 1. Outcome and scope

The completed migration must preserve the public therapeutic-program-to-RNA product while moving authoritative semantic work to OCaml. Python remains the public authoring language. The complete corresponding RNA set and companion manifest remain the output for human immune cells engineered in vivo, conditional on explicit supplied contracts.

Completion requires a working installed product, complete checker coverage, cross-language compatibility, all existing release gates, new OCaml/TypeScript gates, and recorded validation of the exact integrated revision. Schemas, stubs, an OCaml executable that delegates semantics back to Python, or a single passing demonstration do not establish migration completion.

This roadmap covers all eleven agreed layers. It does not expand the biological target, introduce new organism backends, discover mechanisms or sequences, establish empirical therapeutic function, or remove existing limitations. The conversational layer is new product functionality and has its own completion criteria; preserving an extension point alone does not complete that layer.

Work begins with the ordered session batches in section 5 and continues through the remaining checklist. No fixed wall-clock promise is attached to a system-wide migration. At every handoff, retain the last fully checked product and identify the next uncompleted task.

## 2. Fixed architectural decisions

| Layer | Target language and ownership | Migration task |
| --- | --- | --- |
| 1. Studio | TypeScript, HTML and CSS; presentation and editing only | LM-10 |
| 2. Conversational authoring | Python proposal orchestration; explicit reviewable intent as output | LM-11 |
| 3. SDK, notebooks and CLI | Python restricted DSL and thin core adapter | LM-12 |
| 4. Canonical intent and analysis | OCaml validated types, identity, units and scope | LM-20 |
| 5. Behavioral IR and reference semantics | OCaml typed operations, lowering and reference execution | LM-21 |
| 6. Mechanism IR and realization contracts | OCaml causal/model contracts; Python scientific adapters | LM-22 |
| 7. Components and architecture | OCaml deterministic compilation and acceptance; Python exploratory proposals | LM-23 |
| 8. Construction and emission | OCaml molecular types, transformations and exact candidate emission | LM-24 |
| 9. Independent verification and acceptance | Separately runnable OCaml checker with independent reconstruction | LM-25 |
| 10. Canonical artifacts | OCaml canonical content and acceptance binding; Python storage/workflow | LM-26 |
| 11. Physical biological execution | No software implementation language; explicit external boundary | LM-27 |

### 2.1 One semantic core, explicit internal separation

Use one OCaml project with explicit Dune library dependencies and separate compiler/checker entry points. Target layout (foundation libraries now exist; later semantic libraries remain to be implemented):

    core/
      dune-project
      lib/wire/                 bounded decoding, protocol envelopes
      lib/domain/               validated types, IDs, units, schemas
      lib/semantics/            versioned source reference semantics
      lib/compiler/             lowering, matching, selection, generation
      lib/candidate_runtime/    execution reconstructed from candidate records
      lib/checker/              independent correspondence and acceptance
      lib/artifact/             canonical representation and archive rules
      bin/core/                 biocompiler-core command interface
      bin/verify/               biocompiler-verify standalone verifier
      test/
    protocol/                   versioned transport/schema specifications
    tests/conformance/          retained inputs, literal expectations, mutations
    studio/                     TypeScript sources and pinned build configuration

The checker must not link compiler, synthesis, matcher, assembler or emitter libraries. Keep candidate execution separate from source reference execution. Shared primitive types, decoding and canonicalization are part of the documented trusted base; sharing them does not constitute independent verification. The artifact library must separate content/codec rules from producer-dependent assembly.

OCaml abstract types and controlled constructors protect validated representations. Distinguish structural validation, conditional behavioral results, empirical assessment and admission as independent dimensions. Do not represent them as one universal Verified state.

Prefer explicit variants, immutable snapshots and nominal IDs. Use GADTs only where a concrete invariant benefits. Make incomplete matches errors for closed semantic variants; reject catch-all handling that could silently accept a new operation.

No Rust, C, Haskell, Julia, SMT solver or proof assistant is required by this migration. Existing scientific libraries remain behind explicit Python adapters. Add specialized execution or proof tools only when a concrete later obligation justifies them.

### 2.2 A local executable protocol

Start with bounded, versioned requests to an explicitly selected local core executable. Python submits complete operations rather than exposing OCaml object pointers. Initial operation families: capabilities/version, validate, lower, evaluate, compile, verify, inspect and checked export. Define the exact subset at LM-02; these names describe planned families, not shipped commands.

Each envelope carries request identity, protocol version, operation/profile, complete source authority or verified content references, limits and expected tool compatibility. Responses carry structured outcomes, diagnostics, artifacts and execution identity. Standard output is protocol-only; diagnostics use standard error. Define cancellation, timeouts, bounded response size, process failure and partial-output rejection.

The standalone verifier accepts the candidate and separately supplied full expected request, component/library pins and sequence/construction roots. A candidate's own hashes, embedded source or stored PASS cannot supply independent authority.

Python and TypeScript models support authoring and display. Only the core validates imported semantic authority after the relevant operation is migrated. No executable Python object serialization or dynamic import of supplied code is part of the wire protocol.

### 2.3 Preserve compatibility without accepting stale claims

Freeze Python API names, CLI commands, exception categories, diagnostic codes, supported profiles and wire schemas before migrating their implementation. Preserve compatibility unless an intentional versioned change is documented and tested.

Transport version, domain schema version, source-semantics version, checker-policy version and implementation/tool identity are separate. A new checker implementation receives an explicit identity and fresh receipts. Do not silently relabel historical Python receipts as OCaml verification.

Compare canonical request/IR bytes where the contract is unchanged and exact molecule bytes for equivalent builds. Full build/report bytes may intentionally change when tool identity changes: enumerate those fields in a reviewed migration manifest and regenerate affected identities. Never use a broad normalization that hides missing obligations, changed assumptions or changed decisions.

## 3. Starting conditions and migration risks

| Observed baseline | Required response |
| --- | --- |
| Core is Python, setuptools, no declared runtime dependencies | Introduce OCaml distribution deliberately; end users must not acquire a compiler merely to use a released package. |
| Behavior includes v0.1 and v0.2 sampled integration/channels | Port each supported semantic profile; a Boolean-only slice cannot replace the product. |
| Architecture checker policy is v0.3; architecture records include matching and availability authority | Preserve all matching, control, helper, recipient and bounded-execution obligations. |
| Studio has app.js and construction.js; its guided builder uses the older CandidateRequest profile | Preserve existing Studio behavior during the TypeScript conversion. Add modern architecture authoring as a separately tested increment. |
| Hashes use Python JSON serialization conventions | Freeze exact compatibility vectors before any canonicalization rewrite. |
| CI has a fail-closed registry of required jobs and receipts | Update workflow, registry, accounting tests and aggregate dependencies together when adding language gates. |
| Multiple historical/reference/synthetic public workflows remain | Inventory every public entry point; explicitly retain, migrate or deprecate each. No invisible loss of coverage. |

The largest risks are semantic drift, canonical identity drift, a checker that accidentally calls a producer, platform packaging failures, and two engines becoming permanent competing authorities.

## 4. Foundation work

### LM-00 — Freeze the capability and authority inventory

- [x] Record starting commit/tree, package version, active branch and exact latest applicable CI receipts. Preserve unrelated work and use a dedicated codex/language-migration branch for implementation.
- [x] Inventory public exports, CLI commands, profiles, artifact schemas, serializers, example families, source/candidate execution paths and Studio endpoints. See the reproducible [coverage ledger](migration-coverage.md).
- [x] For every entry point, record: current implementation; source of authority; target owner; dependent tasks; compatibility contract; candidate static test references; and migration state. Static references are not executed coverage or parity; gaps remain visible in the ledger.
- [x] Discover the current test suite using the existing accounting mechanism in the authorized validation environment. Do not copy an old test count into the new acceptance criteria.
- [ ] Freeze representative positive, failed, unknown, unsupported, malformed and stale-authority inputs; retain literal expectations and current engine outputs separately.

**Deliverables:** migration coverage ledger, baseline receipt, pinned input corpus and measured baseline timings/memory for representative cases.

**Exit:** every supported public path has an owner and disposition; no implementation work relies on a stale handoff as its sole baseline.

### LM-01 — Establish OCaml, TypeScript and hosted build foundations

Depends on LM-00.

- [x] Pin OCaml, Dune and dependencies with a reproducible lock strategy, warnings-as-errors and bounded hosted test execution. PR37–44 retain the exact toolchain, solved platform dependencies and required test receipts.
- [ ] Add and validate the OCaml formatting gate; preserve the pinned build and warning policy.
- [x] Create the core library dependency graph and two real executable entry points. Add a dependency test that fails when the verifier links producer libraries.
- [x] Add TypeScript strict configuration, a package lock and deterministic build into the existing installed static asset locations. Avoid a new UI framework or redesign unless separately needed.
- [x] Produce an initial hosted binary for Linux x86_64 and macOS arm64, and test its protocol startup on those platforms. Inventory other current distribution targets before claiming they are supported.
- [x] Extend the CI registry and aggregate gate alongside workflow changes. Keep every existing job and receipt requirement.

**Exit:** hosted builds produce revision-bound binaries and packaged Studio assets; a separately executable verifier starts without producer libraries. Skeleton success is foundation completion only.

### LM-02 — Specify and implement wire, numeric and canonical contracts

Depends on LM-00; implementation uses LM-01.

- [x] Specify strict decoding, unknown-field/version rejection, exact field types, duplicate-key rejection, null versus absence, Unicode validity and cumulative input/work limits.
- [x] Freeze fingerprint behavior from [serialization.py](../src/biocompiler/ir/serialization.py). It is SHA-256 over Python's compact sorted-key UTF-8 JSON, not an assumed generic canonical-JSON standard.
- [x] Test arbitrary-size integers, the JavaScript safe-integer boundary, bool versus int, int versus float, exponent spelling, negative zero, finite float roundtrips, invalid Unicode and object-key ordering. Do not truncate Python integers to OCaml machine integers.
- [x] Preserve the exact decimal-to-rational primitive and existing reference floating-point behavior. PR40 validates the reference numeric corpus; PR42 validates `Fraction(str(value))` compatibility, 18 exact ratios and six literal decimal-sum boundaries.
- [x] Validate exact decimal interval semantics in the complete availability checker. PR45 and its integrated-main run passed 30 complete deployment results/witnesses on both native platforms, including exact decimal equality and a genuine decimal gap. [Validation receipt](../protocol/migration-architecture-validation.json). Numeric-model improvements require a separately versioned semantic change.
- [x] Preserve raw authoritative JSON through browser and adapter workflows; parsed JavaScript objects are display/editing aids and must not silently reserialize imported authority.
- [ ] Separate semantic fingerprints from run timestamps, local paths and packaging metadata. Document canonical binary/text encodings and archive determinism.
- [x] Implement protocol errors, crash/timeout/cancellation handling and executable compatibility checks. Reject incomplete responses and ambiguous outputs.

**Exit:** Python and OCaml agree on the retained canonical vectors and rejection cases; TypeScript roundtrips original authority without numeric or text loss. Any necessary format break is explicit, versioned and accompanied by a conversion/reverification policy.

### LM-03 — Create conformance, mutation and performance evidence

Depends on LM-00 and LM-02; grows throughout implementation.

- [ ] Establish Python-to-OCaml and OCaml-to-Python import/replay checks where the profile is compatible.
- [x] Compare implemented modules against both baseline outputs and independent literal expectations. PR37–44 exercise the growing conformance harness on both native platforms; each later profile must extend it before promotion. Agreement between two implementations is not proof that either is correct.
- [x] Require and retain intended failure signatures in the implemented conformance campaigns. Native tests compare exact diagnostic codes or complete reports; a crash or unrelated rejection is not successful detection. New profiles must retain this gate.
- [ ] Record wall time, peak memory, serialized size and protocol overhead for representative small and composite programs on the same platform.
- [x] Require explicit case accounting in the conformance harness and exact discovered Python-test accounting. Pinned native case inventories, expected outcomes and required jobs fail closed; every new profile must extend those inventories. Skipped, missing, unsupported-by-the-new-engine and timed-out migrated cases cannot count as parity.

**Exit:** the harness exposes structured mismatches and cannot promote a partially tested profile.

## 5. Ordered session batches

Reread this roadmap before each batch and update its scoped checkboxes and status table as work proceeds. Mark a checkpoint complete only after its stated validation gate passes; implemented or prepared work remains unchecked. Parallel work may start when its contracts are stable.

| Batch | Work | Completion gate | Status |
| --- | --- | --- | --- |
| B0 | LM-00 inventory; LM-01 skeleton; LM-02 protocol/canonical vectors | Baseline and executable interface are pinned; canonical compatibility is established | Native protocol/canonical foundation validated; broader corpus, performance, formatting and distribution-plan obligations remain |
| B1 | First checker-led vertical slice: LM-20/21/22/24/25 subset, LM-23 records/decoders, Python adapter in shadow mode | Existing case B request and Python candidate are independently checked in OCaml; targeted temporal/authority/sequence mutants fail correctly | BuildRequest/Behavior/coordinate and circuit declarations plus independent source correspondence validated in PR38/39; per-role reference execution and lowering/contract/chemistry prerequisites validated in PR40/41; complete human wrappers, component models, molecules/sets and decimal deployment declarations validated in PR42; architecture/construction declarations and independent required-region checking validated in PR43; full architecture request authority, construction reconstruction and source-manifest checking validated in PR44; complete architecture checker validated in PR45; installed protocol and independent candidate execution remain open |
| B2 | Port producer for that same slice; extend LM-23/24/26 | Python authoring → OCaml compilation → independent OCaml check → paired RNA/manifest export works outside checkout | Producers validated in PR46; installed operations validated and merged in PR47; explicit public SDK/CLI routing validated and merged in PR48; distribution/default cutover open |
| B3 | Expand all behavior/architecture/control profiles and historical public coverage | Complete capability ledger and all 13 current architecture cases pass with fresh identity and mutation evidence | Queued |
| B4 | LM-10 TypeScript parity; LM-12 installed SDK/CLI parity; deliberate architecture UI integration | Existing browser and installed workflows pass; migrated paths visibly use compatible OCaml core | TypeScript parity and installed browser checks passed; architecture integration and installed SDK cutover pending |
| B5 | LM-11 conversational draft/review flow and LM-27 scope enforcement | Draft → explicit reviewed intent → existing validated pipeline; ambiguity and unsupported claims remain visible | Queued |
| B6 | LM-30 release/cutover and legacy retirement | All required gates pass at the integrated revision; supported-platform installations and rollback are verified | Queued |

### Scoped implementation checkpoints

These checkpoints record narrower validated work; they do not complete a broad LM layer or the B1 acceptance gate. [Protocol v1](../protocol/core-v1.md) remains the advertised interface.

- [x] **PR37 — protocol/canonical foundation and TypeScript parity:** merged and validated on both native platforms, through the complete required CI and integrated main gates; [receipt](../protocol/migration-foundation-validation.json).
- [x] **PR38 — B1.02/03 domain subset:** typed BuildRequest/target, all 42 Behavior operation declarations and molecular coordinates; merged with complete CI and integrated main validation; [receipt](../protocol/migration-domain-validation.json).
- [x] **PR39 — B1.02 circuit declarations and B1.04 source correspondence:** checked circuit/profile/recipient records and independent original-source/Behavior correspondence, including retained case B pairs; merged with complete CI and integrated main validation; [receipt](../protocol/migration-source-correspondence-validation.json).
- [x] **B1.02 complete wrapped source authority:** typed measurement, human behavior, deployment and acceptance imports plus intact circuit source correspondence passed full PR42 validation (40 records, 244 staged rejections, four literals). Downstream observation, actuator, evidence and admission obligations remain unresolved.
- [x] **PR40 — B1.05 per-role reference execution:** complete source profiles and full traces validated by [run 36935066451](https://github.com/logannye/biocompiler/actions/runs/36935066451), then merged; [exact receipt](../protocol/migration-reference-execution-validation.json).
- [x] **PR40 integrated-main validation:** separate [run 36936774523](https://github.com/logannye/biocompiler/actions/runs/36936774523) passed every required gate at `10382dd5c662c924a460a5113cbd5d58b3dffe48`.
- [x] **Fresh lowering producer:** `bioc_compiler.Lowering`, 31 exact productions, 32 intended failures and six independent literals; full PR41 validation passed and merged.
- [x] **B1.06 contract prerequisites:** shared pins and all four component contract types/algebra; 30 records, 35 malformed inputs and 77 algebra cases passed full PR41 validation.
- [x] **Diagnostic compatibility profile:** pinned Unicode 14 diagnostics, official provenance/license and three compatibility witnesses passed full PR41 validation. The deliberate diagnostic-text/hash exception remains documented.
- [x] **B1.07 molecular prerequisites:** provenance and chemistry, with 47 records, 82 decode failures, 29 context checks, 10 text and 50 serialization cases, passed full PR41 validation.
- [x] **PR41 integrated-main validation:** separate [run 36937189850](https://github.com/logannye/biocompiler/actions/runs/36937189850) passed every required gate at `e3d3cbcf1a7b05ccdbc34fdb69127c22e8ea8345`.
- [x] **B1.06 component record subset:** all eight record families, contextual synthetic-model checks, 60 records, 112 rejections and 42 fresh assessments passed full PR42 validation.
- [x] **B1.06 architecture leaf subset:** 12 output, binding, placement and constraint types, with 88 positives, 345 rejections and four independent literals, passed complete PR43 validation.
- [x] **B1.06 complete architecture request domains:** full refinements, templates, library and request validation passed complete PR44 validation: 65 positive records, 192 rejections and 25 actual construction-request conversions.
- [x] **B1.07 molecule/set/artifact subset:** 109 records, 136 rejections and 16 identity relations passed full PR42 validation, preserving the original wrapped eight-member example and all nine case B occurrences.
- [x] **B1.07 complete construction declaration subset:** transition/recoding, required-region, all 30 construction schemas/14 operations and unchecked candidate-artifact records passed complete PR43 validation, including the original three case B candidates.
- [x] **B1.07 independent construction reconstruction:** all 14 operations, complete assessment/replay and scoped transition checks passed full PR44 validation: 83 complete construction cases, 125 transition reports, all three original case B candidates and independent resource/atomicity literals.
- [x] **LM-02/B1.06 decimal deployment prerequisites:** 15 records, 78 rejections, 18 exact ratios and six literal sum boundaries passed full PR42 validation. The contextual checker remains open.
- [x] **PR42 complete PR validation:** [run 36938602636](https://github.com/logannye/biocompiler/actions/runs/36938602636) passed all 30 jobs, 2,155 tests on each Python version, 22 native suites on both platforms and 936 protocol checks; [receipt](../protocol/migration-complete-domains-validation.json). Merged as `f278ce01336c537d250df4f90219903a25174ae0`.
- [x] **PR42 integrated-main validation:** [run 36940233185](https://github.com/logannye/biocompiler/actions/runs/36940233185) passed every required gate at `f278ce01336c537d250df4f90219903a25174ae0`.
- [x] **M09 required-region checker subset:** independent comparison with complete molecule sets passed full PR43 validation: 99 cases, 55 typed/serialized checks, 44 import cases and 27 source-preserving mutations. Contradictions and unresolved obligations remain separate. This does not complete construction or architecture acceptance.
- [x] **PR43 complete PR validation:** [run 36941895831](https://github.com/logannye/biocompiler/actions/runs/36941895831) passed every required gate at source `7fb3ec8`, tested merge `9f0c10e`, integrated as `aa62bdceec57eda5a4a1949af17c8b729486ed0d`; [receipt](../protocol/migration-construction-domains-validation.json).
- [x] **PR43 integrated-main validation:** separate [run 36943390725](https://github.com/logannye/biocompiler/actions/runs/36943390725) passed every required gate, with exactly 2,207 tests on each Python version.
- [x] **B1.08 source-manifest subset:** historical records and independent original-source reconstruction passed full PR44 validation: 34 records, 56 import rejections and 35 exact source pairs, including 17 meaningful candidate mutations.
- [x] **PR44 complete PR validation:** [run 36945426505](https://github.com/logannye/biocompiler/actions/runs/36945426505) passed every required gate; [receipt](../protocol/migration-reconstruction-validation.json).
- [x] **PR44 integrated-main validation:** [run 36946981717](https://github.com/logannye/biocompiler/actions/runs/36946981717) passed every required gate at `e24ef03261ab46689a2c2cb8434aa24280eab028`; the receipt retains its full aggregate digest.
- [x] **B1.08 historical build and proof prerequisites:** complete build/assessment records (48 records, 117 import rejections), 53 supplementary circuit checks, 112 control-proof cases and 30 deployment cases passed full PR45 validation. Prefix-only fixture normalization preserves every case and diagnostic; binding pin `e2fc5cdebb0867269483d3f3da58433221d681f6b9a0585d8eb45a5d0281852a` is portable across checkouts.
- [x] **B1.08 complete ledger and architecture reconstruction:** 293 fresh reports from all 78 named source-test methods, all 13 installed architecture examples and all three original case B authorities passed full PR45 validation. All 463 document identities, two finite diagnostic replacements and one narrowly scoped ordering difference remain pinned; [exact receipt](../protocol/migration-architecture-validation.json).
- [x] **PR45 complete PR validation and merge:** all 30 required jobs passed, including 2,283 tests per Python version, 40 native suites on both platforms and 936 protocol checks. Source `99914ca274745ca65a9005f918ed15fc569141f2`, tested merge `40cf9525ec9b3f19a10e9e789b6651dbf68ec69d` and integrated commit `83ce68cecc1634f1b143f67e198ff083df425af5` share tree `5d963c11f618ae4fec2ac341c35f296d35fdeeaf`.
- [x] **PR45 integrated-main validation:** separate [run 36954221531](https://github.com/logannye/biocompiler/actions/runs/36954221531) passed all 30 required jobs at `83ce68cecc1634f1b143f67e198ff083df425af5`, with 2,283 tests on each Python version; the retained receipt records its full aggregate digest.
- [x] **B1.08a independent candidate execution and coupled transport**, under the supplied model profiles.
  The next internal batch ports all 14 synthetic mechanism operations and
  candidate-specific snapshots/traces into a separately linked runtime. Its
  dependency policy permits only shared wire/domain/numeric primitives; source
  execution, producers and acceptance libraries are prohibited. The initial
  50-method Python baseline captures 55 executions (43 complete traces and 12
  failures) and replays exactly. Expanded capture includes transitive callers;
  complete operation coverage, independent timeline literals, resource boundaries
  and both hosted native platforms remain required. Locked assembly reconstruction,
  realization checking and molecular correspondence remain subsequent obligations.

  **Validated implementation checkpoint:** the complete internal
  mechanism domain, candidate frame/trace codecs and fresh-session scheduler are
  implemented. The final corpus pins 155 original methods, one class fixture and
  two observed subprocesses: 11,938 domain observations and 549 executions (537
  full traces, 12 failures), 73 programs and all 14 operations. All 12,487 calls
  are classified; five failures belong to the stricter wire boundary (four
  nonfinite values and one duplicate-key document). The original 50-method,
  55-execution, 727-call baseline is retained unchanged. Corpus pin
  `e29da7150c3a80621967d332f8bb03065b07ebcb30b58b30fc8029e296393599`
  covers 3,955 documents and 16,098,793 bytes. Seven integrity/replay tests and
  fresh full recapture pass locally. Native compilation, all 50 native suites,
  complete mandatory corpus execution and every product gate passed on both
  hosted platforms in [run 36962357736](https://github.com/logannye/biocompiler/actions/runs/36962357736).
  [PR49](https://github.com/logannye/biocompiler/pull/49) merged at
  `0347211f987b11639881675e308ecef2def06032`; source, tested and integrated trees
  match, and both Python versions passed all 2,419 tests.
  [Exact receipt](../protocol/migration-candidate-runtime-validation.json).
  Its first hosted run compiled and passed the domain/runtime
  literals, but Dune omitted the corpus argument; the invocation is corrected
  and the complete native corpus now passes on both platforms. Separate
  integrated-main run `36968854701` remains pending. Public realization routing
  and full migration cutover are still open.

- [x] **B1.08b locked-component reconstruction and execution:** full registry/lock, composition,
  observation-map and assembly containers retain complete authority. The runner
  derives operations, parameters and ordered inputs from actual selected records
  and wiring. The unchanged 163-method baseline retains all 52,476 calls and
  exact domains, reconstructed graphs and full traces. Six source integrity/replay
  tests pass; 56 native suites, the full mandatory corpus and all product gates
  passed on both hosted platforms. The corpus pin is
  `aea8309d6efa172777f550d4a91cd3ebb7b40c301234fc7e90636fb4f466fcbf`
  (4,934 documents, 64,530,645 bytes).
  [PR50](https://github.com/logannye/biocompiler/pull/50) is merged.
  The initial Linux run compiled all targets but exposed a malformed-inventory
  diagnostic mismatch in the full corpus. That branch is corrected without
  changing retained expectations. A source audit also corrected kind-specific
  ValueDomain rejection precedence, with 26 new literal assertions. The reader
  reports all case failures before failing its aggregate gate. All 56 native
  suites, including the complete corpus, now pass on both hosted platforms at
  `ca1228753dd5ae6f7e803c866800ff703ef5d05f`. All 31 required jobs in
  [run 36964842188](https://github.com/logannye/biocompiler/actions/runs/36964842188)
  passed: 2,425 tests on each Python version and four complete 175-check/219-artifact
  installed campaigns. Source, tested merge and integrated commit
  `1b1ffa182e05ba688c6d309f80980adac87a6f3e` share the exact tested tree.
  [Validation receipt](../protocol/migration-locked-component-validation.json).
  Separate integrated-main run `36970818826` remains pending.
  Generic composition acceptance, realization checking, scientific
  adapters and empirical validity are separate unfinished obligations.

- [x] **B1.09a realization contracts and complete evidence:** port InputDomain,
  OperatingDomain, BehaviorContract and all finite-history evidence records.
  Preserve the historical ASCII-escaped evidence/dependency identities separately
  from canonical UTF-8 artifact identities, full history and explicit horizon.
  The typed contract/evidence/admission implementation in
  [PR51](https://github.com/logannye/biocompiler/pull/51) passed all 31 required
  jobs at source `8e8e191cce34182a85b3ea7765a01cc650b7711c` in run
  `36966315057`: 2,429 tests on each Python version, 60 native suites on each
  platform and exact four-way equality for 175 routing checks / 219 artifacts.
  The source, tested and integrated trees match
  `b866ee680f8110080c6c837a9762dd914dcb1d43`; integrated revision is
  `652e2aa0aa24bf563412483827d07c4bc027a4e0`.
  [Validation receipt](../protocol/migration-realization-foundation-validation.json).
  The separate integrated-main run 36972688727 also passed and its complete
  receipts were independently verified; broader LM-22/25 exits
  remain open for their remaining operations and public routes.
  The complete 324-method capture now retains 70,019 observations, including
  both actual subprocesses; fresh recapture and four integrity/replay checks
  pass. Corpus `ac1499688ec6f0eca41398134b9421de9f95ffe9405422332c2bf43b04db32f8`
  contains 19,458 documents / 103,174,628 bytes. All 3,198 future acceptance
  observations remain explicitly deferred. The full foundation corpus is
  mandatory in Dune and a separate hosted campaign (60 native suites total).
  An initial ambiguous record-field warning was corrected before the complete
  successful validation above.
- [x] **B1.09b fresh admission, generic linking and selection:** reproduce complete
  policy assessments, provider grounding, lifetime/resource accounting and ranked
  alternatives. Retained decisions and identity-only freshness cannot grant use.
  The implementation includes complete composition reports, independent generic
  linking with exact rational resource accounting, deterministic selection and
  fresh actual-component behavior checking. The original 373-method capture
  retains all 4,539 calls, including 415 link checks, 35 selections, eight fresh
  selection replays and 85 component behavior checks. The 52 source-correspondence
  calls remain explicitly deferred to B1.09d. PR53 passed all 69 native suites
  per platform and all 31 hosted jobs, including 2,441 tests on each Python
  version. The integrated tree exactly matches the tested tree; the separate
  main run remains pending. Fresh full recapture is byte-identical;
  the corpus retains 5,394 documents / 30,453,450 bytes under pin
  `9eb76b8f697b00be207e6bb2e1cccdfd46ee974b09a3525d21eb4f32634ee116`.
  Three exact original admission-policy version mutations have test-only
  handling; production APIs remain fixed. Only two originally unordered binding
  diagnostic groups gain deterministic pair ordering, with complete independent
  [three-seed source witnesses](../tests/conformance/component-link-order-v1.json).
  Neither change normalizes the original corpus's complete reports. The full
  capture/replay, 41 boundary/CI/inventory tests, independent report literals and
  peer resource reviews precede 69 hosted native suites and all product gates.
  [PR53](https://github.com/logannye/biocompiler/pull/53) preserves this batch.
  Its first hosted build caught two ambiguous status constructors and one
  partially applied test limit constructor. Explicit type annotations and the
  missing unit argument correct those errors; strict warnings and all required
  gates remain enabled. Corrected source `7449f71c89966b9123752a6ed69d6c4d0ae4710b`
  passed run 36980275430 and merged as `18a141e85a425cd801d5e831c8cf36d021692138`.
  [Complete validation and integration receipt](../protocol/migration-realization-stack-validation.json).
- [x] **B1.09c independent realization acceptance:** combine independently executed
  source and actual candidate traces, preserving active/inactive nonvacuity,
  deadline transitions, cancelled and incomplete episodes, failure precedence,
  counterexamples and exact bounded claims. Bound preparation, both executions,
  monitoring and result publication; budget exhaustion cannot become acceptance.
  Typed RealizationRequest import and a separate fresh Checked_request wrapper
  are now implemented, together with independent source/candidate execution,
  finite-history monitoring, exact dependency identities and shared bounded work.
  The new complete capture retains 74,803 calls from 340 unchanged original
  methods, 348 contexts and both actual subprocesses. Fresh recapture is
  byte-identical; all five integrity/replay tests and 29 boundary/CI tests pass.
  Corpus `8ddc5a929f90e8364e3ffb53c6902ff23bd5dec2524897a8d463f543b887d80a`
  contains 26,410 documents / 201,611,674 bytes. Four explicitly identified
  checker-version mutation observations verify the complete current result,
  then change only its version in test code and check the retained mutant and
  freshness result; production APIs expose no version override. All 137 generic
  component-acceptance observations remain deferred. Four new suites bring the
  native total to 64, with the complete corpus mandatory in both hosted campaigns.
  Corrected PR52 source `23b142b42a263227a8565403fb4f62cc8a1d638c` passed all
  31 product gates in run 36980274253, with 2,435 tests per Python version.
  PR53 independently validated and integrated all of this implementation and
  its corrections; PR52 was then closed as superseded, preserving its branch
  and complete receipts. Broader public-routing and default-cutover exits remain
  open. [Validation and inclusion evidence](../protocol/migration-realization-stack-validation.json).
  Earlier [PR52](https://github.com/logannye/biocompiler/pull/52) source
  `d55d660f700d3da4368e6755e60a76efa1a45447` had passed all 64 native suites
  on both hosted platforms while full product workflows were still pending.
  Hosted Python 3.11 replay exposed six version-specific mappingproxy error
  messages. Correction `097e9789b30742b45afa16fcc11def083325a644` pins exactly
  those counterparts without changing capture inputs, errors or native codes;
  all six source replay/integrity tests pass. Fresh complete hosted gates were
  required; the earlier native PASS was not transferred to the new revision.
  The later Python 3.11 campaign exposed six additional list/dict set-membership
  messages in the same retained corpus. The correction pins all twelve exact
  version-specific rejection identities, messages and native codes without
  altering source inputs or corpus expectations. All six source replay/integrity
  tests pass; the correction was propagated to PR52/53/54 and each subsequently
  passed its fresh complete hosted validation. No prior native PASS was transferred.
- [x] **B1.09d component correspondence and fresh replay:** independently reconstruct
  the expected source/assembly correspondence without importing its adapter or
  producer; require complete generic linking before behavior acceptance.
  The [independent acceptance implementation plan](migration-synthetic-acceptance-plan.md)
  records the current producer dependencies, exact synthetic provenance and
  policy obligations, temporal rules, candidate-dependent component declarations,
  diagnostic precedence and required independent mutation evidence. Typed
  synthetic catalog/configuration/candidate declarations are the next prerequisite;
  their structural import does not establish candidate provenance or acceptance.
  The implemented declaration batch retains both complete 9/13-operation catalogs,
  all four profile/strategy configurations, candidate source/requirement maps and
  locked identities. Its 373 unchanged source methods and both actual subprocesses
  produce 47,758 observations across 381 contexts. All 41,267 domain/catalog calls
  have complete native expectations; 6,491 generation, selection and acceptance
  observations remain explicitly deferred, including the private generator used
  by selection. Corpus pin
  `caf19f88640281b28b4ea4a39d131a5e2ecf8c696465af1c5a020a265aa161fa`
  covers 3,759 documents / 75,488,401 bytes. Six Python integrity/replay tests and
  independent full recapture/byte comparison pass. Independent review confirms
  22 complete artifact/fingerprint/byte literals, 74 original rejection witnesses
  and three constructor-order cases. Two new suites bring the required native
  total to 71; native execution and complete hosted product gates remain pending.
  [PR54](https://github.com/logannye/biocompiler/pull/54) preserves this declaration
  batch. Its first hosted build caught two ambiguous documentation comments;
  correcting those annotations preserves strict warnings and leaves the full
  replacement native/product gates required. Corrected source `7098c102ba02fc42f0dad25632cd81fc0fb5886f`
  subsequently passed all 71 native suites per platform and all 31 jobs, with
  2,447 tests per Python version, in run 36980279079. Its integrated revision
  `fb0217324a0550717fc369501de601ed2be22e82` has the exact tested tree.
  The separate main run remains pending, and this declaration checkpoint does
  not close B1.09d's later acceptance implementation.
  The next acceptance batch now implements private independent source provenance
  and actual-candidate-derived component authority, plus public fresh synthetic
  and assembly checkers. Expected declarations remain private, actual candidate
  execution remains independent, and coherent in-band candidate changes can pass.
  All 4,119 reached acceptance calls now have complete native expectations:
  906 synthetic checks, 52 assembly checks, 1,080 realization checks, 1,996
  dependency snapshots and 85 component behavior checks. Corpus pin
  `d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331`
  retains 4,910 documents / 109,400,531 bytes from the same 373-method capture.
  Only 2,372 producer, selection and adaptation observations remain deferred.
  Seven Python corpus tests and byte-identical full recapture pass. Independent
  native test inputs include 12 complete candidate reports, 62 provenance cases,
  12 complete assembly reports and 14 exact assembly rejections, with shared
  resource limits and failure isolation. Static private-boundary mutations and
  all 41 boundary/CI/inventory checks pass. Four new native suites bring the
  required total to 75. Corrected source `d59af59488344812b5d8895b339c37e852411d54`
  passed all 31 jobs in [run 36980282550](https://github.com/logannye/biocompiler/actions/runs/36980282550),
  including all 75 native suites on Linux and macOS and 2,454 tests per Python
  version. Independent receipt reconstruction and rehashing reproduced all four
  sets of 175 observations and 219 artifacts. [PR55](https://github.com/logannye/biocompiler/pull/55)
  merged as `c0b32b668c328ee88c5320886d13b91ea3e24038`; its tree exactly matches
  the tested tree. The [stack validation record](../protocol/migration-realization-stack-validation.json)
  retains this evidence. This scoped checkpoint is complete; broader LM exits
  remain open.
- [x] **B2 direct synthetic production and selection:** the next implementation
  independently ports generation/proposal, both-strategy selection and full
  component adaptation, with complete Alternative/Result domain records. The
  producer library calls public fresh checkers and cannot import their private
  provenance or component-authority witnesses. The complete capture preserves
  all earlier 47,758 observations and adds 143 selection-record observations:
  47,901 total across the same 373 original methods / 381 contexts. All 2,372
  formerly deferred producer calls now have native expectations, including the
  exact original proposal mutations through a restricted test seam. Corpus pin
  `2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b`
  retains 5,192 documents / 114,234,914 bytes. Nine complete Python integrity and
  replay checks and independent byte-identical recapture pass. Independent full
  producer/domain literals and exact resource-boundary cases supplement this
  capture. Four mandatory suites bring the native total to 79. Corrected source
  `2024d8fdd2a9a8c300ef2dc0980623b820f1997c` passed all 31 jobs in
  [run 36980326616](https://github.com/logannye/biocompiler/actions/runs/36980326616),
  with all 79 native suites on both hosted platforms and 2,463 tests per Python
  version. Complete aggregate reconstruction and four-runtime artifact rehashing
  match the retained receipts. PR56 merged as
  `01c211dfe0be459c6e272c87efdec6aa9bc2e405`, with the exact tested tree. Public routing, checked pipelines, packaging and default cutover remain
  separate unfinished work. The [producer implementation audit](migration-synthetic-producer-plan.md)
  and [next public-routing plan](migration-realization-routing-plan.md) retain
  the exact source responsibilities and remaining exit criteria.
  [PR56](https://github.com/logannye/biocompiler/pull/56) preserves this batch.
  Its first hosted compiler run rejected an unused functor parameter in the
  public interface; using an anonymous parameter preserves strict warnings and
  the same proposal-only test seam. A reviewed unit fixture now sends the
  ordinary constrained-selection case through the production selector; only the
  two actual original selector mutations use injected proposals. All 123 full
  Python selection/domain literals still reproduce their original results.
  The follow-up resource audit also forwards all five component-behavior limit
  reductions into generic linking and preserves ancestor exhaustion at the
  exact reconstruction boundary. Selector child publication allowances now
  subtract object keys as well as values, matching the enforcing report budget.
  These corrections require fresh hosted gates;
  the first failed run does not establish native validation.
  The corrected Linux build compiles; its native suite then exposed one stale
  test budget in `test_component_behavior_check`. Correction
  `693a55157cdb4cd120e6fc1e1d7073aa74a61df2` preserves production enforcement and
  tests the larger 2,800-byte generic-link reservation before the 2,238-byte
  outer publication. [Replacement run 36976350244](https://github.com/logannye/biocompiler/actions/runs/36976350244)
  must pass the complete gates; the superseded failed run was cancelled after
  its replacement existed and its diagnostic log was retained locally.
- [ ] **B1.09e protocol exposure and public routing:** accept full external authority,
  freshly recompute complete results, and preserve every existing caller and
  export gate. The audited realization baseline contains 324 methods across 23
  existing modules; capture actual calls, complete artifacts and original
  assertions, including nested and subprocess consumers. Source-only direct
  contract/checker tests do not establish native or full-workflow parity.
  The protocol implementation now exposes dependency snapshots, four direct
  checks and four fresh replays through both executable roles. Each operation
  requires complete external authority, a negotiated family profile and explicit
  limits; it preserves raw authority identity, report-family encoding and shared
  bounded work. The five corresponding Python APIs accept optional `core=`;
  their default behavior remains unchanged. Typed transport and output hydration
  do not confer source correspondence or empirical acceptance.
  The new corpus projects all 4,119 original direct calls and 2,112 original
  replays without sampling, and retains the original 373 methods / 381 contexts
  and actual-child lineage. Corpus pin
  `9261f5fc259e6d79e56df6bf9cc5ee528e795aa5dd2ef8bc4dcc7b63dfd4d4bf`
  adds 69 documents while reusing immutable original records. Current-policy
  mutant counterparts, Unicode records
  and boundary mutations are additional cases. The new native protocol suite is
  registered as the 80th suite. Four separately required installed campaigns
  cover both native platforms and Python 3.11/3.14, followed by a complete
  artifact comparison. These add five jobs while preserving all previous 31.
  Static Python checks are available; native execution and all 36 hosted gates
  remain required. This item and the broader LM-12/22/25 exits stay unchecked.
  Full workflow, exploration/reduction, archive, CLI and export routing are
  separate unfinished obligations in the [routing plan](migration-realization-routing-plan.md).
  PR57's first Python run exposed historical source-hash assertions after the
  intentional optional routing changes. A separately pinned source-lineage
  witness now retains all original source bytes and hashes, pins current bytes,
  and verifies whole-file AST preservation after removing only those five
  reviewed routes. All six original corpus census checks and five mutation
  checks pass locally; original corpus pins and observations are unchanged.
  The corrected revision still requires fresh complete hosted validation.

- [x] **LM-03 workflow capture checkpoint:** all fourteen integrity/replay tests
  pass, including independent reproduction of all 376 original methods, complete
  prior-call projection, callbacks and CLI publication bytes. The new transport
  module has a separately pinned addition witness and is forbidden from loading
  during the original cohort. Actual current source metadata is retained
  separately; only the historical source inventory is projected for comparison.
  Original observation/document bytes and all golden pins remain unchanged.
  This records Python baseline evidence; native conformance remains open below.
- [ ] **B1.09f complete verification workflows:** draft OCaml domain records and
  engines now cover check/explore/reduce, candidate/model modes, complete fresh
  replay, deterministic adversarial histories and shared operation budgets.
  The initial 84 native suites passed on Linux and macOS at draft source
  `002344cdfeca2dc599c1e21ff291b9858258c227`; its broader hosted gates were still
  running. The complete 69,236-observation native runner is now registered as
  the 85th suite and as a separately logged mandatory corpus campaign. It
  includes every original callback, yield and prerequisite observation, with
  bounded 64 MiB codec hooks preserving existing protocol defaults. The retained R5
  corpus contains all 376 unchanged original methods, 385 contexts, 69,236
  calls, 1,030 evaluator invocations and the full 625-history campaign; its pin is
  `2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b`.
  The complete 47,901-observation prior projection is preserved. This is an
  implementation/capture checkpoint: the new runner and accounting changes
  require fresh hosted native validation. The reviewed accounting derivation
  preserves each checker's 50-million-unit allowance, charges added workflow
  work to one ancestor, bounds live retention explicitly, and keeps its total
  integer allowance below the exact binary64 integer boundary. That arithmetic
  is documented in the native plan and still requires executable validation.
  The Python [artifact transport](../protocol/artifact-transport-v1.md) passes
  real subprocess tests including a complete 36 MiB report, strict byte binding,
  cancellation and corruption rejection. A subsequent service batch implements
  native descriptor handling, both executable roles, and a strict immutable Python
  workflow SDK for all six operation/mode pairs. It uses a narrowly pinned POSIX
  descriptor primitive, scoped raw-input retention and authority-first replay.
  Local transport/client tests pass (37 tests); native compilation and the new
  full installed campaign/comparison require fresh hosted validation. All existing
  required CI jobs remain, with workflow evidence added to the four installed
  variants and their comparison. The installed campaign covers 112 calls per role
  (224 per runtime), retaining every original top-level workflow occurrence,
  full artifacts/receipts/errors, supplemental operation/mode pairs and boundary
  failures; its 13 projection/comparator unit tests pass locally. Legacy public
  workflow/CLI routing and R6 remain
  unfinished; no default route is changed. The batch adds two native suites
  (87 total) and preserves the complete 85-suite predecessor run separately.
  At `683c6a23d3ddbecc514c614cd55506df46437057`, hosted Linux compilation and
  the complete 85-suite step passed in run `36981094835`; macOS and the full
  36-job gate were still pending. That result does not validate this service batch.
  See the [native implementation plan](migration-realization-workflow-native-plan.md),
  [public workflow audit](migration-realization-workflow-public-plan.md) and
  [complete capture audit](migration-realization-workflow-conformance-plan.md).

- [x] **LM-03 actual CLI capture checkpoint:** all 70 actual child processes were
  independently repeated with exact stdout, stderr, exits and complete filesystem
  bytes. The 16 original CLI observations and four original test methods remain
  intact; 66 console invocations and four module invocations retain all operation
  and mode pairs, nonpassing replay, publication failures, ordering and size
  boundaries. Eleven integrity/recapture tests pass. The complete inventory pin
  is `a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7`;
  114 content documents retain 5,200,804 bytes. This proves the original Python
  CLI baseline, not migrated native CLI execution.
- [ ] **LM-12/R5 native public-workflow preparation:** compatible presentation v2
  now retains v1 while adding native exit policy, reduction frame counts and
  command validation after source validation. Separate native source preflight
  preserves the future replay route's source-before-file-error order. Immutable
  Python views preserve complete records and formatting through audited output
  leaf codecs; legacy input serialization remains untrusted input only. Local
  focused transport/view checks pass; the 88 native suites, installed campaigns
  and full 36-job gate require hosted validation. The original public workflow
  functions and CLI remained unchanged at this PR60 preparation checkpoint. The
  subsequent explicit-routing work is recorded below; hosted installed view/CLI
  conformance, R6 and distribution/cutover remain required.
  See [contracts and evidence scope](../protocol/workflow-public-contracts-v1.md).

- [x] **LM-03 public-route default preservation checkpoint:** the two complete
  historical source files are retained in a separately pinned exact source/AST
  witness. All fourteen workflow recapture tests pass (102.329 seconds), and all
  70 original CLI children reproduce unchanged outputs, exits and filesystem
  bytes. Actual source/import metadata and the added implicit `core=None` binding
  remain in retained evidence; only explicitly proved source and derived-signature
  metadata are projected for baseline comparison. Eighteen lineage mutation tests
  and all eight earlier source-census tests pass; 2,132 entries across nine source
  inventories were independently checked. No original freezer or golden was edited.
- [ ] **LM-12/R5 explicit public workflow routing:** the two public workflow
  functions now accept optional `core=` and delegate to immutable native views.
  The four workflow CLI commands accept explicit core/verifier paths, digest and
  timeout controls while preserving default argparse text. Native preflight
  precedes replay historical-file I/O, and fresh replay rechecks the same frozen
  source bytes. Native presentation supplies exit policy and reduction counts.
  Nine SDK and twelve actual-child Python fixture tests pass; strict typing covers
  eleven adapter modules. The public SDK campaign retains 164 observations per
  executable role, including every original workflow occurrence and all supported
  input forms. The CLI campaign retains all 70 children per role, exact publication
  bytes and full native wire responses. Their four-runtime comparators rehash
  complete evidence. Python protocol fixtures pass; installed native execution on
  both platforms and the complete hosted gate remain required for this revision. This is implementation progress, not R5
  completion or default cutover. See [native workflow routing](native-workflow-routing.md).

**Credit-limit preservation, 2026-10-02:** implementation through
[PR62](https://github.com/logannye/biocompiler/pull/62) is committed and pushed at
`b5d5aa69f4fbf54a6c484245d82552c7d71dd6cb`, with fresh
[run 36989978642](https://github.com/logannye/biocompiler/actions/runs/36989978642)
queued at preservation. This subsequent documentation checkpoint is on
`codex/ocaml-producer-routing-checkpoint`, preserving PR62's running revision.
PR53, PR54, PR55 and PR56 are merged after their full exact-revision gates and independent
receipt/tree checks; PR52 is included through PR53 and closed as superseded
after its own 31-job gate also passed. PR57–62 still require complete gates;
no pending or automatic merge is enabled. The PR57–59 source-lineage correction retains every
original corpus pin and reviewed whole-file AST witness. Earlier partial native
success remains historical only. All unfinished layer checkboxes remain unchecked.

A subsequent source-census audit found the remaining candidate-runtime direct-hash
assertion. Its one-test correction is pushed to PR57–60 with byte-identical
inventories and unchanged goldens. [Exact corrections and replacement runs](../protocol/candidate-source-census-corrections.json)
record current parent heads; previous partial native passes are historical only.

- [ ] **LM-12/R6 P1 producer service:** expose the existing OCaml generator,
  complete two-strategy selector and freshly checked component adapter through
  producer-only operations and a strict raw-document SDK. Preserve complete
  candidates, alternatives, rejections, configuration and finite-history result
  identities under one bounded operation budget. Installed campaigns must retain
  every applicable original producer occurrence and compare full results across
  both native platforms and Python versions. Service and raw SDK are implemented;
  native validation is pending. The installed campaign covers all 1,226 original
  public occurrences and three verifier rejections per runtime, retaining the
  1,146 private/injected producer occurrences explicitly as native-library coverage.
  The public synthesis functions retain their original default route; the following
  checkpoints add explicit SDK and CLI native routes while preserving the default.
  Hosted public routing, native manager integration, canonical packages and default
  cutover remain separate unfinished work.

- [x] **LM-03 producer-service Python fixture checkpoint:** ten strict client
  tests and six installed-campaign/comparator fixture tests pass, including actual
  Python protocol child processes, full original occurrence accounting and
  rehashed content forgeries. Strict typing passes for all twelve adapter modules;
  33 CI and native dependency-boundary tests pass. Native/Python declaration
  metadata matches exactly. Existing public source, corpus and freezer files
  remain unchanged. These checks validate transport and the evidence harness;
  the 23 complete native literals and all hosted native campaigns still require
  execution at the new revision.

- [ ] **LM-12/R6 P1 explicit public producer routing checkpoint:** the current
  `codex/ocaml-public-synthetic-producers` branch adds three optional `core=` SDK
  routes, complete immutable native inspection views and a separate native full
  build-request selection operation. Eight public SDK fixtures, strict typing for
  thirteen adapter modules, source-lineage checks and static dependency checks
  pass locally. The lineage/default suite passes 66 focused tests and preserves
  all 2,132 source entries across nine corpora plus complete original argument
  comparisons for all 47,901 producer observations. The exact three-function AST
  witness preserves old default bodies and every original corpus pin. The new native suite retains four complete result
  fixtures and 42 original malformed authority messages; native execution is
  hosted-only and pending. Installed public SDK campaigns and explicit CLI routing
  are implemented in the following checkpoints; rich helpers are implemented in
  the inspection checkpoint below. Their hosted acceptance, package acceptance
  and default cutover remain unfinished. No full recapture or rich legacy API parity is claimed by
  this bounded checkpoint. See [explicit producer routing](native-synthetic-producer-routing.md).

- [x] **LM-03 exact CLI runtime counterpart checkpoint:** the archived pre-route
  CLI at `e8c640b74e34c1ac3db094b776e5478da67ce69e` was independently executed
  under Python 3.11.15. Its complete `unknown-flag` diagnostic matches the
  separately pinned 3.11 counterpart; the original 3.14 baseline remains intact.
  The strict comparator selects only declared Python 3.11/3.14 runtime families,
  rejects unknown runtimes, checks the entire original case and full byte pins,
  and retains actual observations before the explicit comparison projection.
  This corrects the confirmed PR60/PR61 hosted capture failure without changing
  a freezer or golden. Eleven runtime/lineage tests pass on Python 3.11; the
  complete 70-child workflow recapture passes again after the selection route.
  Exact corrections are pushed and remotely verified for PR60–63 at
  `946ff8eb`, `8f3eacc2`, `246d15ab` and `79eeedfd`; fresh parent hosted gates
  remain required.

- [x] **LM-03 synthetic-select capture and default preservation checkpoint:** the
  unchanged original test method and all 72 actual CLI children are retained:
  68 console calls, four module calls, eight complete reference-authority cases,
  42 original malformed-authority messages and publication/argument boundaries.
  The baseline inventory is
  `69556f367752be3076513d96e63c933fb250eaf7d9736f9e39baac1dec47e5d9`, with
  113 content documents retaining 2,252,596 bytes. All 72 children pass fresh
  default-route recapture on Python 3.11 and 3.14. A new whole-file source witness
  removes exactly the hidden-option helper, registration and early branch to
  recover the complete previous CLI AST, then chains through the unchanged
  workflow witness. Twenty-seven capture/lineage tests pass on Python 3.14,
  including all 2,132 historical source identities across nine corpora. Complete
  stdout, stderr, exits, files and actual import/source metadata remain retained;
  only the exact source witness and separately pinned argparse counterpart are
  projected. No original corpus, freezer or prior witness was edited.

- [x] **LM-03 current public CLI Python fixture checkpoint:** all 72 selection
  invocations also execute successfully with Python protocol child fixtures.
  Six workflow CLI campaign/comparator tests pass on Python 3.11, including four
  actual fixture children and the complete 140-observation, four-runtime
  comparison with content-forgery checks. These are transport and evidence-harness
  checks; Python protocol fixtures establish no native execution result. Final
  local validation also passes 62 focused tests (33.184 seconds),
  strict typing for 15 adapter modules and the complete 3,135-entry inventory check.

- [ ] **LM-12/R6 P1 installed public SDK and selection CLI hosted integration:**
  the current `codex/ocaml-synthetic-public-integration` batch adds explicit
  `synthetic-select` core path/digest/timeout selection and native full build-request
  handling while preserving the default Python route. The installed SDK campaign
  covers all 1,226 original public producer occurrences plus nine supported input
  forms, with separate verifier rejection evidence. The installed CLI campaign
  retains all 72 complete baseline observations, native wire/receipt bytes,
  publication behavior and execution guards. Both campaigns and their strict
  four-runtime comparators require fresh installed native execution on Linux
  x86_64/macOS arm64 with Python 3.11/3.14, exact source/binary/run identities and
  the complete required hosted gate before this item can be checked. This batch
  is preserved in [PR64](https://github.com/logannye/biocompiler/pull/64) at
  `acdf2383e60c785edbeb2d63755686a9045636af`, with run 36994062954 pending.
  Rich helpers are preserved in [PR65](https://github.com/logannye/biocompiler/pull/65)
  at `c6382d62da14fbd5f15534a46ffcf932b2266051`, run 36995989631 pending.
  Their hosted compatibility, native manager integration, canonical package acceptance,
  distribution and default cutover remain open; no broader LM exit is completed.
  The [public integration checkpoint](../protocol/migration-synthetic-public-checkpoint.json)
  records exact source hashes, corrected parent commits and local-only evidence.

- [x] **LM-12/R6 P1 rich helper implementation checkpoint:** eight Core-only
  operations and strict Python transport now expose topology, registry
  lock/resolve/select/verification, selection outcome, coverage identities and
  dependency comparison/freshness through immutable native views. Historical
  views require explicit core context; helper receipts do not grant production
  acceptance or empirical claims. Separate protocol and 28 original-Python
  supplemental fixtures are pinned. Shared-budget checks and the 91st native
  suite are wired into the existing 36-gate workflow; native execution remains
  pending. See [inspection protocol](../protocol/synthetic-inspection-v1.md).

- [x] **LM-03 rich helper local evidence checkpoint:** 23 client/public-view
  tests pass, as do 13 corpus/campaign tests and seven final campaign tests
  against the frozen client (overlapping scopes). The campaign executes all 28
  supplemental public calls, eight Verify rejections and Verify capabilities
  through 65 actual Python fixture children. Static CI/boundary checks pass 35
  tests; lineage/inventory checks pass 32 tests; strict mypy passes all 16
  adapter modules. All 72 older selection CLI fixture children pass against
  the frozen sources. The regenerated inventory retains 3,162 entries. These
  results establish local fixture/static behavior only, not native acceptance.

- [ ] **LM-12/R6 P1 rich helper hosted acceptance:** execute all 9,632 retained
  original occurrences plus 28 supplemental cases through installed public
  helpers on both platforms and Python versions. Retain complete authority,
  original values/properties/errors and raw native artifacts; independently
  rehash and compare all four campaigns. All eight producer operations must
  remain unavailable to Verify. Local Python fixture/static evidence cannot
  close this gate, whole-program freshness, large-result transport, package
  acceptance or default cutover.

- [x] **LM-25/R6 P2 native manager implementation checkpoint:** twelve immutable
  contract/record modules and an opaque in-memory checked pass manager now own
  registration/provider identity, controlled roots, acceptance, obligation
  invalidation, recursive freshness and scoped completion. No serialized record
  imports acceptance. Callback-time mutations share a lifetime work ancestor;
  retained bytes/items and graph/callback depth are bounded. This checks the
  source implementation only; all native execution and broader P2 exits remain
  pending. See [manager migration scope](migration-checked-pass-manager.md).

- [ ] **LM-03/25 P2 complete lifecycle conformance and integration:** retain and
  replay the complete original manager/callback/state cohort, validate native
  contract, manager and fixed native pipeline tests on both platforms, then
  complete the public mutable-manager contract.
  Historical records, script fixtures or a one-shot producer wrapper cannot
  satisfy full pipeline, package or fresh export acceptance.

- [x] **LM-03 P2 original lifecycle capture checkpoint:** all 467 unchanged
  original tests pass before and during instrumentation, retaining both actual
  child outputs, 91,566 events, 1,596 callbacks, 2,284 provider identities and
  19,412 complete documents. The complete compressed ledger and bounded native
  replay projection preserve separate scopes. Eight integrity tests verify every
  document, exact projection and full original-capture reconstruction. Another
  51 focused fixture/static checks and the 3,162-entry inventory pass. This checkbox records Python
  capture only; replay of real compiler callbacks, native execution and complete
  lifecycle integration remain pending above.

- [x] **LM-25/R6 P2 fixed pipeline source checkpoint:** separate `bioc_pipeline`
  modules connect actual native lowering, selection, synthetic generation and
  component adaptation to independent checkers and the live manager. They retain
  original ordered source links, partial failure state and one caller work
  ancestor. Budget-aware lowering preserves the legacy entry point. This marks
  implementation only; native execution and public session integration remain open.

- [x] **LM-03 P2 complete fixed-pipeline capture checkpoint:** all 467 unchanged
  original tests pass before and during narrow function tracing. The capture
  retains 136 complete calls (124 returns, 12 errors), 445 documents and all
  850 subsequent manager observations. Eight integrity/projection tests pass.
  Separate bounded native indexes retain complete provider records externally;
  neither the full capture nor existing corpora are reduced. See the
  [pipeline scope and pins](migration-checked-pass-manager.md).

- [ ] **LM-03/25 P2 fixed native pipeline validation:** the hosted driver must
  execute 126 ordinary original calls (121 returns, five failures), 121 returned
  manager rechecks and 563 subsequent commands with complete state/record/error
  comparison. Six patched-callback calls, three Python-type inputs and one mocked
  call remain explicitly pending, as do 254 callback-dependent commands and
  24 prefix/nine suffix commands associated with patched calls. Both new suites
  bring the native total to 96 per platform; all 36 exact-revision jobs remain
  mandatory. Broader lifecycle, public sessions and package/export exits stay open.

- [x] **LM-03 P2 original validator comparison capture:** 34 supplemental
  original-Python cases retain complete state, ordered comparisons and errors,
  including distinct equal bound methods, producer identity, self-certification,
  short-circuit order, reflected equality, mutation and reentrancy. Six integrity
  tests pass; existing lifecycle and fixed-pipeline captures are unchanged.

- [x] **LM-25 P2 validator comparison source checkpoint:** the native manager
  accepts a trusted comparison function for distinct validator objects while
  preserving physical producer identity, self-certification checks and provider
  retention. The function receives the same work ancestor; comparison order,
  exceptions and reentrant mutations remain observable. A source-reviewed native
  driver covers all 34 original cases and 106 nested events, plus default,
  retention, recursion and exact/one-short budget controls. Native execution is
  pending; this 97th hosted suite does not implement public sessions.

- [x] **LM-03/25 P2 installed comparison campaign source checkpoint:** add
  ordered native inspection and retained callable identity bindings; execute the
  unchanged 34 original comparison case bodies through the installed adapter.
  The campaign requires all 78 manager events, 28 comparison events, 18 raised
  events and 280 actual state inspections, together with the existing five
  identity cases. Command arguments, outcomes, nested timing and original host
  exceptions bind to complete wire evidence. Rehashed semantic mutations must
  fail for their intended diagnostic. Local validation totals 102 focused checks
  and strict typing across 20 modules. Hosted replay remains pending; see the
  [source checkpoint](../protocol/migration-callback-comparison-checkpoint.json).
- [ ] **LM-25 P2 validator comparison and public sessions:** validate the additive
  trusted native comparison hook and its complete original-observation replay on
  both platforms, then implement the persistent transport, callback continuations,
  deferred object conversion and public proxy described in the
  [session design](migration-pipeline-sessions.md). Preserve producer identity,
  fresh native manager authority and all original public workflows. The hook
  alone does not close generic callback compatibility or session integration.

- [x] **LM-25 P2 persistent-session source checkpoint:** Core-only framed
  service retains one real native manager, partial logical-error state, immutable
  build artifacts and stable process-local provider identities. Exact hello,
  sequence and request-byte binding share one lifetime work/byte/retention
  budget. Reduced limits include already-consumed hello work and prepaid terminal
  capacity. Malformed frames, identity failures, resource exhaustion and internal
  errors close authority. Separate Verify remains free of session/producer linkage.
- [x] **LM-12 P2 Python session transport checkpoint:** 27 new real Python
  subprocess/codec tests plus all 18 direct-client tests pass; strict typing
  passes for all 17 adapter modules. Tests cover partial I/O, process ownership
  after fork, cancellation/reaping, immutable byte receipts, logical-error
  continuation and cumulative limits. These are Python subprocess fixtures,
  not native execution or original public API compatibility.
- [x] **LM-03 P2 complete session campaign harness:** 11 Python integrity,
  mutation and subprocess tests pass. The hosted driver retains 1,493 complete
  manager-state observations, 17 malformed/framing/lifecycle process probes and
  actual Verify rejection, alongside all original fixed calls and continuations.
  The four-runtime comparator rehashes every frame and full artifact against
  current source/run/executable authority. [Source checkpoint and pending gates](../protocol/migration-pipeline-session-checkpoint.json).
- [ ] **LM-03/25 P2 session hosted acceptance:** the 98th native suite and
  four installed campaigns must compile and pass on both hosted platforms.
  Reexecute all 126 eligible original fixed calls, 121 boundary rechecks and
  563 supported continuations against actual live managers, retaining every
  complete artifact/state/error and process identity. Original source/corpus
  bytes stay pinned; ten excluded calls and 287 callback-dependent observations
  remain explicit pending coverage. Full public typed manager routes, generic
  callback continuations, 64 MiB artifacts and default cutover remain open.

- [x] **LM-03 P2 deferred callback oracle checkpoint:** 47 additional cases
  execute the unchanged original Python manager and retain all 157 manager
  events, 290 user accesses, 21 nested events and 19 original exception-object
  propagations. Nine focused Python tests pass. Observation avoids invoking
  user conversion, equality, iteration or descriptors. The frozen Python 3.14
  bytes remain exact; one explicitly named exception-text difference requires a
  fresh same-runtime original-manager and primitive counterpart. This is an
  additive oracle, not native callback parity. Original corpora remain intact.
- [x] **LM-12 P2 retained host object broker checkpoint:** the additive Python
  broker preserves physical callable identity, original exception objects,
  deferred Mapping conversion, rich comparisons and short-circuit iterator
  primitives. All 23 new broker tests and 27 existing fixed-session tests pass;
  the fixed-session implementation and protocol remain unchanged. This broker
  performs native-requested authoring actions and grants no acceptance.
- [x] **LM-25 P2 deferred native library source checkpoint:** ordered host
  capabilities preserve deferred input, configuration, registration and proposal
  evaluation. Native manager tests cover original result equality, short-circuit
  checks, reentrant state and original exception identity. The bridge retains
  physical object identities; the generic channel binds exact nested frame bytes
  and one lifetime budget. Sticky work exhaustion prevents a caught resource
  error from later authorizing success. All three new native suites are registered
  for hosted validation; only static review has run locally.
- [ ] **LM-25 P2 deferred callback implementation and public compatibility:**
  implement native deferred access, bounded nested continuations and typed public
  adapters under the [callback contract](migration-pipeline-callback-contract.md).
  Replay complete original and supplemental observations on both native platforms
  and both Python versions. Preserve mixed native/host provider behavior, fixed
  registration interception, exception identity and post-error mutations. A
  callback object broker or generic framing library alone does not close this gate.

- [x] **LM-12/25 P2 ordered exception source checkpoint:** logical native
  rejections carry both canonical attributes and a fresh ordered attribute tree.
  The adapter requires their exact agreement and reconstructs independent frozen
  `NoCandidateFound` snapshots without reusing context containers. Native resource
  reservations precede tree construction; a failed publication closes the
  session. Python controls and native test sources cover nested order, repeated
  errors and exhausted publication. Native execution remains a hosted gate.
- [x] **LM-03 P2 original runtime preservation correction:** retain all frozen
  deferred observations and all raw current captures while explicitly proving
  installed source-path and Python 3.11/3.14 frame correspondence. Require actual
  source-bound functions in their original module namespaces, fresh independent
  capture and primitive execution. The installed-origin negative control now
  injects its forbidden source path explicitly in both source and installed
  environments. This is a Python fixture correction, not native compatibility.
- [ ] **LM-03 P2 deferred installed replay and runtime correspondence:** require
  every original case, access, nested mutation and exception observation through
  the installed native manager. Retain raw installed tracebacks and check exact,
  source-bound correspondences for installation paths and Python-version frame
  differences. PR71's original deferred-fixture comparison exposed this missing
  runtime handling; the frozen oracle and complete observation census remain
  unchanged. This gate also requires complete four-runtime receipts and all
  existing identity and comparison cases.

- [x] **LM-03 P2 original identity and ordering oracle:** five additional
  original-manager cases retain 34 complete observations and ten records,
  including shared contexts, records, target and obligation objects, mapping
  insertion order, nested exceptions and records stored before freshness errors.
  Eight Python tests pass. Adversarial copies and reordered mappings fail these
  comparisons even when their values agree. Original frozen corpora are unchanged.
- [x] **LM-12/25 P2 live manager source implementation:** retain an actual OCaml
  manager behind bounded callbacks; add explicit Python typed views with ordered
  values, shared object bindings, fresh access checks and fail-closed sessions.
  Add a real framed native suite and installed five-case identity campaign with
  full frame/artifact receipts, independent Verify rejection and four-runtime
  comparison. Local Python/static checks are separate from native acceptance.
- [ ] **LM-12/25 P2 live typed manager integration:** connect the callback
  application to Core and the explicit Python manager adapter, preserve retained
  object identity and order, and replay the identity oracle through installed
  native executables on both platforms and Python versions. Keep all original
  callback and fixed-pipeline compatibility gates above open until their complete
  live replay passes; an additive adapter is not the default cutover.

- [x] **LM-03 CI harness correction checkpoint:** the installed architecture
  guard now permits only the exact new parser-registration helpers while rejecting
  semantic handlers and similar names; ten focused tests pass. The macOS artifact
  test obtains the actual supported POSIX descriptor number instead of comparing
  devfs inode identities. Every original artifact test body remains byte-identical,
  and the boundary checker pins the one test-only representation conversion.
  Forty-eight boundary/inventory/CI tests and each affected parent's static graph
  pass. The [correction receipt](../protocol/migration-ci-harness-corrections.json)
  records exact affected revisions; native execution and all hosted gates remain
  pending, so this does not close the native acceptance checkpoint.

**Hosted corrections, 2026-10-02:** PR67's native build exposed an ambiguous
OCaml interface documentation comment; comments were disambiguated without
changing signatures or disabling warnings. PR64's conformance run exposed an
expected-scope ordering error inherited by PR62–67: native declaration order is
generation, selection, components, while canonical JSON object iteration differs.
The campaign now derives the exact expected array from reviewed family order,
keeps strict ordering and complete field checks, and identifies mismatched fields.
Seventeen focused Python conformance tests pass, including ordering and field
mutants. Corrected revisions still require every hosted gate; this does not close
any native acceptance checkbox. Exact parent corrections and local proof scope
are recorded in the [correction receipt](../protocol/migration-capability-order-corrections.json).

The integrated PR51 main revision `652e2aa0aa24bf563412483827d07c4bc027a4e0`
passed all 31 jobs in [run 36972688727](https://github.com/logannye/biocompiler/actions/runs/36972688727).
Its aggregate was independently reconstructed, both platform binaries rehashed,
and all four sets of 175 architecture observations and 219 exact artifacts
compared with the retained receipt. Both Python versions accounted for all
2,429 tests. The [foundation validation receipt](../protocol/migration-realization-foundation-validation.json)
records this main-branch evidence; it does not validate later revisions.

These stages precede the remaining B2 producer/export and B3–B6 product gates.

**Hosted validation correction, 2026-10-02:** PR52–55 Linux native jobs exceeded
their 90-minute limit during final corpus work. Their full gates did not pass.
The pending stack now uses a 150-minute allowance and explicitly selects Bash
so a failed command piped through `tee` cannot be hidden. All existing commands,
assertions and required jobs remain. Corrected revisions need fresh validation;
no earlier partial success is transferred. The complete migration remains open.

**Validated producer checkpoint, 2026-10-01:** [PR46](https://github.com/logannye/biocompiler/pull/46)
merged at `e4c6d8d4bea9975ac5e9c6c1bb342034a34a82c0` after complete
[run 36956697449](https://github.com/logannye/biocompiler/actions/runs/36956697449)
passed all 30 required jobs. Both native platforms passed 45 suites, all retained
corpora and 108 installed architecture protocol checks; exactly 2,328 tests ran
on each Python version. Source `95f18956e537845b15098206f255c6ac3074809c`, tested
merge `972d0427c9b9608ecda3b4d0eb7d0026355ce80c` and integrated main share tree
`6ea0da7870964526736c5e7de2c8bf5495e14448`.
[Exact receipt](../protocol/migration-producer-validation.json).

- [x] **B2 producer checkpoint:** independent molecular/recoding/workflow producers,
  source-manifest derivation, matching, architecture production and paired export
  passed full hosted validation. Construction capture retains 61 construction,
  37 recoding and 88 workflow calls; architecture capture retains 193 cases,
  166 documents, all 13 installed examples and three original case B authorities.
  Generated identity diagnostics and arbitrary shared-parent exhaustion are covered.
- [x] **LM-21 coupled source checkpoint:** 51 source-transport cases retain 20 full
  traces, 31 rejection signatures, all nine original test methods and seven
  independent timeline projections. Both platforms passed failed-prefix shared
  allowance and replay-budget regressions. Independent candidate execution remains
  separately required by LM-22/25.
- [x] **LM-12/25 protocol checkpoint:** standalone architecture verify/replay,
  strict capability negotiation and immutable typed Python results passed the
  108-check installed campaign on both native platforms and complete required gates.
  Public production routing and distribution remain open.
- [x] **PR46 integrated-main validation:** separate
  [run 36958643394](https://github.com/logannye/biocompiler/actions/runs/36958643394)
  passed all 30 required jobs at the integrated revision, with exactly 2,328 tests
  on each Python version. The retained receipt binds its full aggregate digest.

- [x] **B2 installed producer operations:** [PR47](https://github.com/logannye/biocompiler/pull/47)
  passed all 30 required jobs in [run 36959458593](https://github.com/logannye/biocompiler/actions/runs/36959458593)
  and merged at `4415d59acd83750dd824218a1c8ab1500d8fc749`.
  Both platforms passed 46 native suites and 62 installed producer checks;
  exactly 2,351 tests passed on each Python version.
  [Pinned receipt](../protocol/migration-installed-producer-validation.json).
  Core-only `compile-architecture` and `export-architecture` preserve exact
  immutable build/FASTA/manifest transport and fresh assessment binding; the
  verifier's producer-free link graph remains enforced. Source `92cb223`, tested
  merge `03936f8` and integrated main share tree
  `64e2732d72b07468b4a7e89ddddf0f7805416f36`. Public routing and distribution
  remain separate checkpoints.
- [x] **PR47 integrated-main validation:** separate
  [run 36961812619](https://github.com/logannye/biocompiler/actions/runs/36961812619)
  passed all 30 required jobs at the integrated revision, including exactly 2,351
  tests on each Python version. The pinned receipt records the full aggregate digest.

- [x] **B2 public architecture routing:** explicit `core=` SDK selection and
  architecture CLI executable options preserve historical classes, raw request
  authority, summaries, exit codes and atomic single-file paired JSON export.
  The bridge checks complete native identities after historical codec hydration;
  selected-core errors never fall back to Python semantics. All 13 installed
  examples and three original case-B workflows passed hosted routing validation
  under Python 3.11 and 3.14 on Linux x86_64 and macOS arm64. All four executions
  passed 175 routing checks and produced the same complete 219-artifact inventory;
  all 31 required jobs passed. [PR48](https://github.com/logannye/biocompiler/pull/48)
  merged as `0921a0b7c6506c1b1282ae0d8f209b4561497a5e`, with matching source,
  tested and integrated trees and 2,410 tests on each Python version.
  [Exact receipt](../protocol/migration-architecture-routing-validation.json).
  Separate integrated-main run `36968652116` remains pending.
  See [explicit core workflows](architecture-core-workflows.md).


PR42 source `06da8b4bee4110597caed15fa2da4f2bb7724268`, tested merge `902cae85932dfc1202f68d7d9bc7502941eeb701` and integrated main share tree `06898b1f7ac5e51e692ef976d5834ec5976a495a`. Both complete PR and integrated-main gates passed. PR43 source `7fb3ec8983b038b03f0efa8f8233e4bef4e5a613`, tested merge `9f0c10ea218c4df49aa9f143718eb82d2daff842` and integrated main share tree `836da9375e1206d708194eecd48419f529ab5ff0`. Both complete PR and integrated-main gates passed. PR44 source `ae56d0c7e3dd8202aa015d7a7b769a75bd8ca037`, tested merge `8ff4d1911a6525c58be16e6db9d030b5fb670a91` and integrated main share tree `7ecc2c56f1370c0540f3c74c5795c6868d8e3841`; full PR and integrated-main gates passed. PR45 adds validated independent full architecture acceptance and its control/deployment/build prerequisites. PR46 validates experimental verification protocol, producers and coupled source transport. PR47 validates installed producer operations and is merged with full integrated-main validation; public routing and full cutover remain open.


- [x] **PR48 integrated-main validation:** [run 36968652116](https://github.com/logannye/biocompiler/actions/runs/36968652116)
  passed all 31 jobs at `0921a0b7c6506c1b1282ae0d8f209b4561497a5e`, with
  2,410 tests on each Python version. The [routing receipt](../protocol/migration-architecture-routing-validation.json)
  records exact aggregate reconstruction and fresh rehashing of both native
  binaries and all four 175-check / 219-artifact installed campaigns.
- [x] **PR49 integrated-main validation:** [run 36968854701](https://github.com/logannye/biocompiler/actions/runs/36968854701)
  passed all 31 jobs at `0347211f987b11639881675e308ecef2def06032`, with
  2,419 tests on each Python version. The [candidate-runtime receipt](../protocol/migration-candidate-runtime-validation.json)
  binds the complete aggregate and rehashed four-way artifacts to that revision.
- [x] **PR50 integrated-main validation:** [run 36970818826](https://github.com/logannye/biocompiler/actions/runs/36970818826)
  passed all 31 jobs at `1b1ffa182e05ba688c6d309f80980adac87a6f3e`, with
  2,425 tests on each Python version. The [component-runtime receipt](../protocol/migration-locked-component-validation.json)
  binds the complete aggregate and rehashed four-way artifacts to that revision.
  These receipt checks read artifact bytes without executing native code. Later
  pending revisions must pass their own complete gates.

**First vertical slice:** [the case B acceptance map](migration-case-b.md) and [retained corpus](../tests/conformance/case-b/README.md) now pin its real source/candidate and independent literal timelines. Architecture acceptance/mutation descriptors remain unexecuted; domain and source-correspondence receipts are scoped above, and per-role reference execution has complete PR40 validation. Use the existing artificial architecture case B (prime/act/recover, timeout, reset and shutdown) with exact supplied source correspondence. Reuse its actual request/templates. The initial checker stage reads the existing Python-produced candidate and independently reconstructs it. Then port its producer. Do not replace this slice with an unrelated toy expression interpreter.

Required pilot negatives: missing or extra source requirement; changed temporal boundary/reset priority; source/controller mismatch; stale independent request or component authority; modified emitted nucleotide; incomplete molecule inventory; malformed or exhausted input; missing or incompatible core executable. Every failure must retain the intended reason and emit no accepted export.

Expand material-cardinality cases A/E, sampled integration C, channel/state composition D/F, automatic B/F matching, automatic timing, and the four control cases. These are coverage increments; dependencies may require implementing shared primitives earlier.

## 6. Work by architectural layer

### LM-10 — Layer 1: Studio in TypeScript

Starting points: [app.js](../src/biocompiler/studio/static/app.js), [construction.js](../src/biocompiler/studio/static/construction.js), [server.py](../src/biocompiler/studio/server.py), [service.py](../src/biocompiler/studio/service.py), [construction service](../src/biocompiler/studio/construction.py).

Depends on LM-02 for protocol contracts; the UI source port can run alongside core development.

- [x] Move the two clients into strict TypeScript modules with typed transport, editor state, diagnostics, request/result identities and artifact views.
- [x] Preserve existing DOM behavior, accessibility, responsive layouts, hostile-label escaping, request bounds and source/assumption visibility.
- [x] Keep raw uploaded authority intact, including existing CRLF/BOM behavior. Reject invalid encodings according to the existing contract. Preserve request-generation tokens and rejection of late responses/downloads.
- [ ] Generate only syntactic client models from shared schemas; retain runtime response validation. No client-generated PASS or local hash becomes authoritative.
- [ ] Preserve the Python Studio server's loopback Host/Origin, session-token, header/body/encoding bounds, route allowlist, CSP and no-store protections while replacing service internals with core adapters.
- [x] Build and include JavaScript assets in installed packages. End users do not need Node or TypeScript; no stale checked-in asset may mask a changed source.
- [x] Pass both existing browser suites unchanged against the installed package.
- [ ] Add full architecture editing/inspection through explicit new service endpoints, preserving the older partial profile's label until deliberately superseded.

**Exit:** strict TypeScript build and installed browser suites pass; architecture UI behavior is separately exercised; every downloaded artifact derives from the same current accepted request. A language-only UI port does not complete architecture feature integration.

### LM-11 — Layer 2: conversational authoring in Python

Current state: future frontend, not an existing capability to merely port.

Depends on LM-02, LM-12 and validated LM-20; a deterministic draft adapter can be developed in parallel.

- [ ] Define a versioned draft/ambiguity model with source-text spans, proposed intent, explicit assumptions, missing information and unsupported requests.
- [ ] Implement a Python proposal adapter that produces declarative data. Do not execute model-generated Python or grant model text checker authority.
- [ ] Route drafts through the same OCaml validation path as authored programs. Require an explicit reviewed-intent state before compilation; retain the draft and revision lineage.
- [ ] Add concise clarification handling for unresolved meaning. Do not infer missing sequences, component mechanisms, delivery guarantees or numerical parameters.
- [ ] Test paraphrases, contradictory requirements, unsupported timing/context, unknown components, attempted instruction injection in imported text and edited drafts that invalidate old review state.
- [ ] Exercise a real configured provider through the same interface before claiming the end-to-end conversational feature. Deterministic adapter fixtures validate orchestration only. Provider selection and credentials remain an explicit integration prerequisite; independent migration work continues without them.

**Exit:** a reviewed conversation draft produces the same canonical intent and compiler behavior as an equivalent Python-authored fixture; ambiguous requests cannot silently compile. If no provider is configured, record this layer as adapter-complete/integration-pending, not complete.

### LM-12 — Layer 3: Python SDK, notebooks and CLI

Starting points: [frontend](../src/biocompiler/frontend/api.py), [symbolic expressions](../src/biocompiler/frontend/expressions.py), [public exports](../src/biocompiler/__init__.py), [CLI](../src/biocompiler/cli.py), [packaging](../pyproject.toml).

Depends on LM-02; individual operations route to OCaml only after their core parity gate.

- [x] Add the thin typed core-process transport with explicit executable selection, timeouts, cancellation, digest/version checks and stable error mapping. `core_client.py` and its protocol/process tests passed PR37–44; current public compiler routing remains Python.
- [ ] Add validated operation negotiation and production adapters for each migrated capability. Architecture verification negotiation passed PR46 and producer operations passed PR47; explicit architecture routing passed PR48; other public profiles remain open.
- [ ] Preserve Python symbolic construction and its ban on Python truth testing. Retain cross-program, role, type and unit diagnostics.
- [ ] Keep public class/function names, return interfaces, JSON roundtrips and CLI behavior where specified. Inventory and test intentional changes rather than silently substituting dictionaries for public objects.
- [ ] Add strict static checking for new adapters and touched public boundaries; expand by module with an explicit remaining ledger. Do not mask migrated paths with Any or blanket ignore rules.
- [ ] Keep reference Python internals available for conformance during migration. Production routing is explicit per operation/profile; no retry through Python after an OCaml rejection, crash or timeout.
- [ ] Update every example and notebook-facing path to work using installed packages outside the source checkout.

**Exit:** existing public workflows pass on Python 3.11 and 3.14 using the selected core; missing/wrong binaries fail clearly; no implicit native build or network download occurs at import or compile time.

### LM-20 — Layer 4: canonical intent and semantic analysis

Starting points: [intent IR](../src/biocompiler/ir/intent.py), [types](../src/biocompiler/semantics/types.py), [context](../src/biocompiler/semantics/context.py), [build request](../src/biocompiler/compiler/request.py).

Depends on LM-02.

- [x] Define nominal node, requirement, role, observation, product, component and molecule IDs, plus units and typed values. Keep domain identity distinct from identical sequence content. `Identity` and `Type_spec` are covered by the validated domain foundation; later construction campaigns preserve distinct member identities.
- [x] Decode and validate existing Intent/BuildRequest/Behavior graph references, ownership, types, dimensions and bounds, retaining complete human target/deployment/acceptance wrappers. PR38–42 validate these domains and PR44 exercises complete wrapped architecture request authority. Downstream policy acceptance remains in LM-25.
- [x] Produce abstract validated intent types through controlled constructors; prevent downstream code from bypassing validation. `Intent.t` is abstract and its constructor validates structure and typed literals; independent lowering checks supply the separate semantic correspondence gate.
- [ ] Preserve original requirements, source locations, assumptions, hard constraints versus preferences, and unsupported meanings.
- [ ] Port strict import limits and rejection behavior; test duplicate IDs, missing references, invalid scalar types and scope mixing.

**Exit:** all inventoried intent/request schemas roundtrip or reject consistently; canonical identities agree for unchanged semantics; unsupported requirements remain in the ledger.

### LM-21 — Layer 5: behavior lowering and reference semantics

Starting points: [behavior IR](../src/biocompiler/ir/behavior.py), [lowerer](../src/biocompiler/compiler/behavior.py), [reference evaluator](../src/biocompiler/semantics/evaluator.py), [coupled executor](../src/biocompiler/semantics/architecture_execution.py), [semantic specification](behavior-semantics-v0.1.md).

Depends on LM-20 and LM-03.

- [x] Port closed typed operation variants and Intent-to-Behavior lowering with source correspondence, bindings and obligations.
- [x] Implement behavior v0.1 timelines: same-contact conjunction, onset semantics, dwell/recent/followed-by boundaries, pulses, reset priority, initialization and bounded same-time settling.
- [x] Preserve simultaneous state assignment, conflict rejection, ordering policies, missing observations, non-finite rejection and explicit horizons.
- [x] Port per-role behavior v0.2 sampled integration and the four v0.2 operation variants. PR40 validates full source-reference traces and numeric boundaries.
- [x] Port coupled declared-channel latency, persistence, aggregation and failure policies. PR46 validates complete finite-grid source traces, failure policies and cumulative budgets on both platforms; it does not establish continuous guarantees.
- [x] Keep the source interpreter and independently reconstructed candidate runtime in different libraries. PR49 validates all 14 candidate operations, complete retained traces and independent numeric/timeline literals on both platforms; dependency checks prohibit either runtime importing the other.
- [x] Compare complete actions, reactions, state, event times and requirement traces, including boundary timestamps; summary PASS agreement is insufficient.

**Exit:** every supported operation/policy profile has positive and negative coverage; literal boundary timelines and existing semantic regressions pass under OCaml.

### LM-22 — Layer 6: mechanisms and realization contracts

Starting points: [mechanism IR](../src/biocompiler/ir/mechanism.py), [realization semantics](../src/biocompiler/semantics/realization.py), [synthetic model](../src/biocompiler/models/synthetic.py), [component model](../src/biocompiler/models/components.py), [molecular behavior contract](molecular-behavior-v0.1.md).

Depends on LM-20/21.

- [ ] Port the currently supported mechanism/model contracts, endpoint observation maps, parameter identities, operating contexts and causal dependencies.
- [x] Reconstruct candidate execution from actual locked records/wiring, not from requested source outputs. PR50 validates complete locked-component reconstruction and actual execution on both native platforms; source correspondence, fresh acceptance and biological validity remain separate obligations.
- [ ] Preserve independent active/inactive response coverage, unfinished deadlines, failure precedence and exact bounded-history claims.
- [ ] Define Python scientific adapter requests/results with pinned model, parameter, context, numerical-method and execution identities. Adapter outputs remain scoped results, not self-authenticating verification.
- [ ] Keep unsupported mechanism discovery, general biological simulation and unmapped operating/resource contracts explicit. This migration does not fill them with nominal implementations.

**Exit:** existing synthetic and supplied-contract realization paths preserve their actual claims and limits; mutated wiring/parameters fail the intended response or identity check.

### LM-23 — Layer 7: component selection and architecture

Starting points: [component contracts](../src/biocompiler/ir/component_contracts.py), [component compiler](../src/biocompiler/compiler/components.py), [architecture compiler](../src/biocompiler/compiler/payload_architecture.py), [matcher](../src/biocompiler/compiler/architecture_matching.py), [architecture profile](payload-architecture-v0.1.md).

Depends on LM-20/21/22; checker ports proceed before producer replacement.

- [x] Port component contracts and RNA architecture provider/interface declarations, including complete source/model maps, material placements and recipient/delivery bindings. PR41–44 validate these imports and rejection campaigns.
- [ ] Complete generic registry/composition declarations and their distinct contextual linker, selection and admission paths. PR50 implements locked containers and execution; generic provider grounding, lifetime/resource acceptance, complete ranked alternatives and fresh policy replay remain open. Architecture-profile validation does not discharge these existing generic-profile obligations.
- [x] Complete fresh contextual checking of those declarations against original source and selected architecture. PR45 validates complete independent architecture assessments and replay across 293 reports, all 13 installed cases and the original case B authorities.
- [x] Preserve many-to-many behavior/component/RNA relations and namespace refinement instances. PR46 validates complete producer outputs across all 13 installed cases, original case B variants and namespace boundaries without sequence-based instance deduplication.
- [x] Port exact semantic matching, partial anchors, ambiguity handling, cumulative search/match limits and deterministic tie-breaking. PR46 retains all original matching assertions and full matching/producer results.
- [x] Preserve hard-constraint rejection before preference ranking; exhaustion and no-candidate results cannot become infeasibility or certified optimality. PR46 validates complete retained alternatives and resource outcomes.
- [x] Port helper bootstrap, sharing/capacity, compartment and same-recipient availability checks, counting every delivered helper RNA. PR45 validates the 30-case deployment corpus and complete architecture correspondence.
- [x] Preserve activation, production adjustment, activity control, memory reset, shutdown, physical separation and dependency disjointness as separate contracts; port every bounded proof and its witnesses. PR45 validates 112 control-proof cases and their complete reports.
- [ ] Python search may propose candidates through a versioned proposal interface. Every proposal undergoes the same OCaml acceptance; search has no power to weaken source authority.

**Exit:** all 13 installed architecture cases and targeted matching/control/resource mutations pass the conformance gate; retained candidate/rejection inventories are complete and deterministic.

### LM-24 — Layer 8: molecular construction and emission

Starting points: [molecular records](../src/biocompiler/ir/molecule_records.py), [chemistry](../src/biocompiler/ir/molecule_chemistry.py), [construction IR](../src/biocompiler/ir/circuit_construction.py), [construction backend](../src/biocompiler/backends/circuit_construction.py), [recoding backend](../src/biocompiler/backends/circuit_recoding.py).

Depends on LM-02 and the required domain types from LM-20/22/23.

- [x] Port exact molecular alphabets, structured chemistry, topology, region/feature inventories, molecule membership and coordinate frames. Full domain and native conformance gates passed in PR38 and PR41–43.
- [ ] Preserve source/destination residue maps, overlap rules, strand/orientation, junction/processing correspondence and protein identity checks where supported.
- [x] Independently reconstruct all 14 supplied construction operations with deterministic order, cumulative bounds and atomic multi-output checking. PR44 validates 83 complete cases and independent resource/atomicity literals.
- [x] Port the separate construction producer with deterministic order, cumulative bounds, complete multi-output results and atomic candidate creation. PR46 validates all supplied operations and producer/checker separation across the complete construction campaign.
- [ ] Retain distinct template/intermediate/delivered identities. Existing DNA reference utilities remain shared infrastructure; therapeutic delivered genetic members remain RNA.
- [ ] Make producer emission deterministic, then independently verify every emitted base, required feature and member against external roots and operation authority.

**Exit:** molecule bytes and required structural meaning match compatible baseline outputs; missing members, wrong bases/coordinates/chemistry and changed supplied authority fail independently.

### LM-25 — Layer 9: independent verification and export acceptance

Starting points: [architecture checker](../src/biocompiler/verification/payload_architecture.py), [control checker](../src/biocompiler/verification/architecture_controls.py), [availability checker](../src/biocompiler/verification/architecture_deployment.py), [independence audit](verification-independence-v0.1.md).

Begins immediately after LM-02/20 with existing Python-produced candidates; expands with LM-21–24.

- [x] Define the trusted-base/dependency inventory and separate OCaml checker executable before producer migration. Both platform builds and negative dependency tests enforce the documented separation; each new checker batch extends the reviewed static policy.
- [x] Port independent source-to-Behavior and source-manifest correspondence, complete construction reconstruction and fresh construction-assessment replay. PR39 and PR44 validate full authority comparisons and mutation rejection.
- [x] Complete architecture/model correspondence and fresh architecture-assessment replay. PR45 validates complete external request/build authority and retained mutation reports.
- [ ] Complete independent candidate execution for each supported runtime profile; source-reference execution does not satisfy this obligation.
- [ ] Port the authoritative checked pass manager from [pipeline.py](../src/biocompiler/compiler/pipeline.py) and [passes.py](../src/biocompiler/compiler/passes.py): stage order/schema/target validation, controlled Components-root admission, scoped completion, obligation invalidation, ancestor freshness and dependency changes during execution. Require [pipeline regressions](../tests/test_pipeline.py); these decisions must not remain in Python workflow orchestration.
- [ ] Require full external expected authority for fresh verification and reject altered claims even when candidate hashes are recomputed.
- [ ] Preserve PASS/FAIL/UNKNOWN/UNSUPPORTED, translation completeness, structural completeness, empirical support and admission as separate dimensions.
- [ ] Port current adversarial mutation and dependency-isolation tests. Verify successfully with producer modules absent; ensure deliberate emitter/matcher corruption cannot manufacture acceptance.
- [ ] Export freshly checked immutable content or recheck the exact content immediately before atomic publication. Prevent changes between acceptance and writing.
- [ ] Preserve honest residual sharing: common decoding/canonicalization needs separate conformance evidence; do not call common-mode agreement independent proof.

**Exit:** standalone installed verification works without Python semantic execution or linked OCaml producers; all acceptance categories and independence tests pass; no stale report can authorize export.

### LM-26 — Layer 10: canonical artifacts and manifests

Starting points: [manifest](../src/biocompiler/artifacts/manifest.py), [archive codec](../src/biocompiler/artifacts/archive_container.py), [review bundles](../src/biocompiler/artifacts/circuit_review_bundle.py), [construction artifacts](../src/biocompiler/artifacts/circuit_construction_build.py), [manifest contract](build-manifest-v0.1.md).

Depends on LM-02/24/25.

- [ ] Port canonical semantic content, fingerprints, complete relative-file inventories, bounded archive decoding and deterministic package ordering/metadata.
- [ ] Bind FASTA and manifest as one accepted output set; retain all source/model/material/recipient identities, assumptions, outstanding obligations and checker scope.
- [ ] Preserve independent authority requirements for imported packages, source review bundles, inspection and fresh replay.
- [ ] Keep timestamps, machine paths and transport details outside canonical semantic identities. Preserve exact original evidence/source bytes where required.
- [ ] Test cross-Python and cross-platform semantic artifact identity. Preserve complete canonical ToolPin/tool-source identities and bind each platform executable digest and distribution receipt to the actual checked execution. Compare exact molecule and unchanged semantic payload identity across platforms; record explicit versioned build/provenance differences where platform binary identities differ. Do not remove tool pins or detach execution receipts to force byte equality.
- [ ] Implement explicit old-to-new artifact compatibility/reverification records and atomic writes. Python workflow code transports opaque accepted artifacts; it cannot rewrite their semantic content while retaining acceptance.

**Exit:** complete installed builds and exports reproduce; no partial paired export, empty comparison directory, stale receipt or self-supplied hash passes.

### LM-27 — Layer 11: preserve the physical-execution boundary

Cross-cutting; depends on LM-20/22/25/26 for enforcement.

- [ ] Carry target context, source-experiment context, deployment assumptions, empirical evidence and admission through every representation.
- [ ] Preserve the distinction among exact digital molecule identity, model-conditional behavior and actual biological performance.
- [ ] Keep manufacturing, delivery, expression, potency and clinical outcomes outside the software compiler's success claim.
- [ ] Add regressions showing that software PASS, artificial fixtures, imported citations and compatible declarations do not become biological validation or human-use admission.
- [ ] Update UI, API, manifests and documentation consistently; conditional translation remains possible without requiring empirical evidence.

**Exit:** all layer outputs and user-facing claims retain the same scoped meaning; no physical execution engine, wet-lab work or empirical collection is introduced by the migration.

## 7. Packaging, CI and integration

### LM-30 — Distribution and release gates

Depends on LM-01 onward; implement packaging early and expand required gates with coverage.

**Distribution plan**

- [x] Build OCaml binaries on hosted runners; record source revision, toolchain/lock identity, OS/architecture and artifact digest. Prefer one reusable build workspace per runner/job and bounded caches.
- [ ] Package a matching core distribution for each declared platform, selected through an explicit Python installation dependency or bundled platform package strategy fixed at B0. Test the actual strategy on Linux x86_64 and macOS arm64 before expanding it.
- [ ] End-user installation must use prebuilt supported artifacts. No silent opam, Dune, Rust, C, npm or other native build at Python import or compiler execution. Unsupported platforms receive a clear documented outcome.
- [x] Verify package/core protocol and release compatibility at startup. Do not execute an unrelated binary found implicitly on PATH.
- [x] Include compiled Studio assets in wheels and source-release build workflows; do not require Node on end-user machines.
- [ ] Test fresh installation, offline runtime, missing/wrong binaries, cancellation, uninstall/upgrade behavior and standalone verification outside the repository.

**Existing gates that remain required**

Keep the complete [development validation protocol](development-validation.md): Python 3.11 and 3.14, all discovered tests in five whole-class shards per version, independent unit accounting, installed-executable, installed-architecture, circuit-integration, integration-examples, studio-browser, and all three reproducibility jobs. Preserve every expected-failure assertion and output artifact.

**New gates**

| Gate | Required evidence |
| --- | --- |
| OCaml static/build/test | Pinned toolchain, warnings policy, unit/property tests, complete test accounting and clean executable packaging |
| Core dependency independence | Verifier cannot depend on producers; candidate runtime does not call source evaluator |
| Wire/canonical conformance | Exact compatibility vectors, hostile/malformed inputs and cross-language roundtrips |
| Semantic/architecture parity | Complete migrated operation census, literal timelines, all required examples and intended mutation failures |
| TypeScript static/build | Strict checking, deterministic assets and package-content assertions |
| Supported-platform install | Linux x86_64 and macOS arm64 installed SDK/core/standalone-verifier smoke, plus any further platform explicitly advertised |
| Aggregate migration acceptance | Exact revision/platform/artifact identity; every required existing and new prerequisite successful |

Update [.github/workflows/ci.yml](../.github/workflows/ci.yml), [tools/ci_validation.py](../tools/ci_validation.py), [tests/test_ci_validation.py](../tests/test_ci_validation.py) and aggregate dependencies together. The job registry rejects unregistered or missing work; adding YAML alone is insufficient.

Retain one coherent PR validation run per update, main integration validation and deliberate manual dispatch where needed. Preserve successful independent work while a longer gate runs. Never remove tests or treat skipped/canceled/missing jobs as success to meet a time target.

Native compilation, native executable tests and package builds run on hosted CI or an already-authorized remote environment. This roadmap deliberately applies the existing hosted-native workflow to OCaml as well. Local editing, documentation, formatting and genuinely non-build static checks can continue. Do not silently install toolchains or compile locally if hosted execution is unavailable.

### LM-31 — Controlled cutover and retirement

Depends on complete per-profile gates and LM-30.

- [ ] Track each operation/profile as legacy, shadow, OCaml-supported, default or retired in the coverage ledger.
- [ ] In shadow mode, the current engine remains explicit; mismatches block promotion and produce retained diagnostics. Shadow results cannot grant authority.
- [ ] Switch one complete profile at a time only after its installed, semantic, mutation, packaging and reproducibility gates pass.
- [ ] Fail closed on a selected OCaml engine's rejection, incompatibility, crash or timeout. Do not automatically retry a rejected request through a more permissive engine.
- [ ] Roll back by selecting a known validated release/profile with compatible artifacts. Keep historical receipts and inputs intact; a rollback is not permission to reuse stale acceptance.
- [ ] Remove duplicated production Python semantic/checker code only after every dependent public path is migrated or explicitly deprecated with compatibility coverage. Retain compact independent conformance oracles and test fixtures.
- [ ] Update AGENTS, architecture, public docs, examples, package metadata and migration instructions to describe actual ownership and installed behavior.

**Exit:** every inventoried public path has a final disposition, OCaml is authoritative for all agreed core layers, and no hidden Python semantic dependency remains in migrated production operations.

## 8. Parallel work and session tracking

After B0 stabilizes the protocol, use three bounded workstreams:

| Workstream | Owned scope | Shared dependencies |
| --- | --- | --- |
| Core semantics/representation | LM-20/21/22 and domain types | LM-02 protocol and numeric contracts |
| Independent checking/construction | LM-25 first, then LM-23/24/26 integration | Same public schemas; no producer implementation sharing |
| Python/Studio/distribution | LM-10/11/12 and LM-30 | Versioned protocol and per-profile capability ledger |

One integrating owner controls protocol/schema changes, Dune library dependencies, CI registry changes and cutover. Agents must use separate file ownership and coherent checkpoints. Do not multiply local toolchains, build trees or native validation processes.

At each batch start, reread the relevant checklist and remaining dependencies; after implementation or validation changes, reconcile the scoped checkpoint status without promoting a partial layer. Every completed task records: task ID; implemented scope; commit/tree; applicable schema/semantic/checker versions; hosted run and platform; positive/negative/mutation census; artifact paths/digests; unresolved limitations; next task. Update task checkboxes only when their stated exit conditions pass.

### Session acceptance checkpoints

- [ ] **Checkpoint A — foundation:** LM-00/01/02 complete and LM-03 harness running.
- [ ] **Checkpoint B — checker-led pilot:** existing case B independently accepted/rejected in OCaml with required mutants.
- [ ] **Checkpoint C — complete migrated slice:** Python authoring through OCaml producer/checker to exact RNA plus manifest; installed replay succeeds.
- [ ] **Checkpoint D — product parity:** every supported core profile and historical public workflow accounted for; all architecture/control cases and scope boundaries preserved.
- [ ] **Checkpoint E — frontend completion:** TypeScript parity and intentional architecture integration, Python compatibility, and conversational integration status honestly recorded.
- [ ] **Checkpoint F — system migration complete:** supported-platform distribution, all exact-revision gates, default routing, documentation and legacy disposition complete.

If the session ends before Checkpoint F, save the highest completed checkpoint, the exact remaining task and any active hosted validation identity. A partial port is a useful checkpoint, not a completed system migration.

## 9. Non-negotiable regression checklist

Before promoting any migrated profile, verify the relevant obligations below:

- Source requirements, human target and wrapped deployment/acceptance contracts are retained.
- Python authoring control flow cannot silently become cellular execution semantics.
- Same-contact and same-recipient scope survive transformations.
- Active and inactive obligations are non-vacuous; unknowns remain explicit.
- Reset, simultaneous state updates, event boundaries and finite-grid policies remain exact.
- Hard constraints precede preferences; exhausted search is not infeasibility.
- Components, functional instances, RNA partitions and recipient roles retain distinct identities.
- Helpers cannot bootstrap from circular absent supply; delivered helpers count in material budgets.
- Production control, activity control, shutdown, physical separation and dependency independence remain distinct.
- Molecular alphabet, chemistry, coordinates, processing relationships and every required member are checked against independent authority.
- Imported PASS labels and rehashed tampered candidates cannot authorize export.
- Semantic changes invalidate dependent results; tool changes receive fresh execution identity.
- FASTA and manifest refer to the same freshly accepted content.
- Artificial controls and software compilation never establish empirical behavior or human admission.
