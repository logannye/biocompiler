# Biocompiler language migration: session roadmap

Created: 2026-10-01, America/Los_Angeles.

**Decision:** TypeScript for Studio; Python for authoring, orchestration and scientific exploration; OCaml for the semantic compiler, independent checking and canonical emission.

**Status:** production semantic authority remains Python. The validated foundation is merged in [PR37](https://github.com/logannye/biocompiler/pull/37), with the exact revision/platform results in the [foundation receipt](../protocol/migration-foundation-validation.json). Typed request, all 42 Behavior operations and molecular-coordinate domains are merged in [PR38](https://github.com/logannye/biocompiler/pull/38); the [domain receipt](../protocol/migration-domain-validation.json) records both native platforms and full Python/integration checks. Both integrated main revisions also passed their required gates.

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
- [ ] Validate exact decimal interval semantics in the complete availability checker. The current architecture batch implements this contextual check but awaits hosted validation. Numeric-model improvements require a separately versioned semantic change.
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
| B2 | Port producer for that same slice; extend LM-23/24/26 | Python authoring → OCaml compilation → independent OCaml check → paired RNA/manifest export works outside checkout | Producers validated in PR46; installed operations validated and merged in PR47; public SDK/CLI routing in PR48 awaits complete gates |
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
- [ ] **B1.08a independent candidate execution and coupled transport**, before any such execution claim.
  The next internal batch ports all 14 synthetic mechanism operations and
  candidate-specific snapshots/traces into a separately linked runtime. Its
  dependency policy permits only shared wire/domain/numeric primitives; source
  execution, producers and acceptance libraries are prohibited. The initial
  50-method Python baseline captures 55 executions (43 complete traces and 12
  failures) and replays exactly. Expanded capture includes transitive callers;
  complete operation coverage, independent timeline literals, resource boundaries
  and both hosted native platforms remain required. Locked assembly reconstruction,
  realization checking and molecular correspondence remain subsequent obligations.

  **Implementation checkpoint (unvalidated natively):** the complete internal
  mechanism domain, candidate frame/trace codecs and fresh-session scheduler are
  implemented. The final corpus pins 155 original methods, one class fixture and
  two observed subprocesses: 11,938 domain observations and 549 executions (537
  full traces, 12 failures), 73 programs and all 14 operations. All 12,487 calls
  are classified; five failures belong to the stricter wire boundary (four
  nonfinite values and one duplicate-key document). The original 50-method,
  55-execution, 727-call baseline is retained unchanged. Corpus pin
  `e29da7150c3a80621967d332f8bb03065b07ebcb30b58b30fc8029e296393599`
  covers 3,955 documents and 16,098,793 bytes. Seven integrity/replay tests and
  fresh full recapture pass locally; native compilation, 50 native suites and
  complete mandatory corpus execution remain required on both hosted platforms.
  Draft [PR49](https://github.com/logannye/biocompiler/pull/49) preserves this
  implementation. Its first hosted run compiled and passed the domain/runtime
  literals, but Dune omitted the corpus argument; the invocation is corrected
  and full native corpus validation remains pending.

- [ ] **B1.09 fresh acceptance and protocol exposure**, followed by B2 producer/export and the remaining B3–B6 product gates.

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
- [ ] **PR47 integrated-main validation:** separate
  [run 36961812619](https://github.com/logannye/biocompiler/actions/runs/36961812619)
  is running at the integrated revision. Do not transfer the PR result to it.

- [ ] **B2 public architecture routing:** explicit `core=` SDK selection and
  architecture CLI executable options preserve historical classes, raw request
  authority, summaries, exit codes and atomic single-file paired JSON export.
  The bridge checks complete native identities after historical codec hydration;
  selected-core errors never fall back to Python semantics. All 13 installed
  examples and three original case-B workflows require hosted routing validation
  under Python 3.11 and 3.14 on Linux x86_64 and macOS arm64. The new required
  reproducibility gate compares complete artifacts across all four executions;
  175 routing checks per execution and all 31 required jobs must pass.
  See [explicit core workflows](architecture-core-workflows.md).


PR42 source `06da8b4bee4110597caed15fa2da4f2bb7724268`, tested merge `902cae85932dfc1202f68d7d9bc7502941eeb701` and integrated main share tree `06898b1f7ac5e51e692ef976d5834ec5976a495a`. Both complete PR and integrated-main gates passed. PR43 source `7fb3ec8983b038b03f0efa8f8233e4bef4e5a613`, tested merge `9f0c10ea218c4df49aa9f143718eb82d2daff842` and integrated main share tree `836da9375e1206d708194eecd48419f529ab5ff0`. Both complete PR and integrated-main gates passed. PR44 source `ae56d0c7e3dd8202aa015d7a7b769a75bd8ca037`, tested merge `8ff4d1911a6525c58be16e6db9d030b5fb670a91` and integrated main share tree `7ecc2c56f1370c0540f3c74c5795c6868d8e3841`; full PR and integrated-main gates passed. PR45 adds validated independent full architecture acceptance and its control/deployment/build prerequisites. PR46 validates experimental verification protocol, producers and coupled source transport. PR47 validates installed producer operations and is merged; its separate main run, public routing and full cutover remain open.

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
- [ ] Add validated operation negotiation and production adapters for each migrated capability. Architecture verification negotiation passed PR46 and producer operations passed PR47; explicit public routing remains in validation.
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
- [ ] Keep the source interpreter and independently reconstructed candidate runtime in different libraries. Shared primitive numeric definitions must be declared and covered by independent literal cases.
- [x] Compare complete actions, reactions, state, event times and requirement traces, including boundary timestamps; summary PASS agreement is insufficient.

**Exit:** every supported operation/policy profile has positive and negative coverage; literal boundary timelines and existing semantic regressions pass under OCaml.

### LM-22 — Layer 6: mechanisms and realization contracts

Starting points: [mechanism IR](../src/biocompiler/ir/mechanism.py), [realization semantics](../src/biocompiler/semantics/realization.py), [synthetic model](../src/biocompiler/models/synthetic.py), [component model](../src/biocompiler/models/components.py), [molecular behavior contract](molecular-behavior-v0.1.md).

Depends on LM-20/21.

- [ ] Port the currently supported mechanism/model contracts, endpoint observation maps, parameter identities, operating contexts and causal dependencies.
- [ ] Reconstruct candidate execution from actual locked records/wiring, not from requested source outputs.
- [ ] Preserve independent active/inactive response coverage, unfinished deadlines, failure precedence and exact bounded-history claims.
- [ ] Define Python scientific adapter requests/results with pinned model, parameter, context, numerical-method and execution identities. Adapter outputs remain scoped results, not self-authenticating verification.
- [ ] Keep unsupported mechanism discovery, general biological simulation and unmapped operating/resource contracts explicit. This migration does not fill them with nominal implementations.

**Exit:** existing synthetic and supplied-contract realization paths preserve their actual claims and limits; mutated wiring/parameters fail the intended response or identity check.

### LM-23 — Layer 7: component selection and architecture

Starting points: [component contracts](../src/biocompiler/ir/component_contracts.py), [component compiler](../src/biocompiler/compiler/components.py), [architecture compiler](../src/biocompiler/compiler/payload_architecture.py), [matcher](../src/biocompiler/compiler/architecture_matching.py), [architecture profile](payload-architecture-v0.1.md).

Depends on LM-20/21/22; checker ports proceed before producer replacement.

- [x] Port component, provider/interface and architecture declaration domains, including complete source/model maps, material placements and recipient/delivery bindings. PR41–44 validate their full imports and rejection campaigns.
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
