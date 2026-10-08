# Working on biocompiler

Current product clarification, 2026-09-30: therapeutic program design is the
input and corresponding payload RNA sequences are the output. New product work
targets human immune cells engineered in vivo and RNA genetic payloads only.
Existing DNA/reference construction utilities remain shared infrastructure;
they are not new product backends. Check translation under explicit supplied
component contracts without requiring biological evidence. Keep whether those
contracts hold in human cells as a separate unresolved empirical question.
Follow `docs/payload-architecture-v0.1.md` for the current composite architecture
profile and `docs/executable-rna-payload-v0.1.md` for the earlier per-operator path.
Package `0.1.0.dev29` keeps behavioral meaning, implementation components, RNA
partitioning and recipient roles separate with explicit many-to-many bindings.
Opt-in exact semantic matching derives source correspondences from supplied
models. Independent bounded control and RNA availability checks retain every
unsupported requirement; neither matching nor availability invents biological
mechanisms, sequences or delivery guarantees.

The sole product purpose is to translate high-level Python and eventually natural-language therapeutic intent into exact, complete RNA payload specifications for immune cells engineered in vivo in humans. Prioritize work that connects source requirements to selected molecular implementations and emitted bases. Quantitative execution and evaluation should support those selected implementations, with explicit observation maps, assumptions and separately assessed evidence, rather than become a disconnected simulator. Bounded compilation under supplied executable component contracts is implemented; natural-language authoring, unrestricted molecular realization and empirical therapeutic validation remain open.

## Human-only product scope

User clarification, 2026-09-30: only human biology and RNA payloads for
in-vivo immune-cell deployment are product targets. Do not add non-human
organism backends, gate libraries, sequencing workflows, organism selectors or
general cell-engineering product tracks. Human-cell literature reconstruction
is a supporting reference/evidence workflow through shared compiler passes,
not an alternate deployment target. Keep source-experiment context separate
from the intended human immune target and preserve all original deployment and
acceptance obligations. Human non-immune or in-vitro results cannot silently
become immune-cell or in-vivo evidence.

Recipient species and component origin are distinct. Preserve exact synthetic,
heterologous or chimeric reference parts and their provenance; assess their
human immune applicability separately. Do not silently humanize a reference or
treat non-human component origin as permission for a non-human target. Existing
historical non-human fixtures retain their limited regression role; do not expand
or promote them into the new benchmark/product scope. Cello is UI/software
inspiration only. This scope must govern plans, implementation and user-facing
workflows. Follow `docs/human-circuit-profile-v0.1.md` for R0 scope declarations,
typed recipient binding, source-context separation and fresh assessment replay.
Declared eligibility establishes neither physical cell identity nor biological
evidence. The executable RNA payload profile generates exact molecule sets under
supplied component contracts; it does not establish that the declared molecular
behavior occurs in human cells.

## Current implementation and engineering rules

biocompiler implements Python intent authoring, immutable build/realization requests and intent/behavior graphs, authoritative lowering, checked passes, automatic combinational/temporal synthetic generation and bounded digital implementation selection, abstract reference execution, finite-trace checking against independent synthetic models, typed component contracts, offline composition linking with executable digital assembly reconstruction, reusable JSON verification workflows, single-CDS reference construct assembly and independently checked exact-reference DNA/RNA emission with reproducible offline reference packaging. A separate software molecular-design profile assembles and independently checks multi-region RNA specifications from supplied fragment/layout authority. The partial intent-candidate compiler selects a supplied product CDS and RNA architecture from source requirements, derives the layout and emits an independently checked structural cassette. The executable RNA payload profile additionally preserves source activation and action semantics, selects compatible supplied executable contracts, constructs complete RNA member sets and independently checks source/component/sequence correspondence. The composite architecture profile extends that same toolchain to supplied full Behavior subgraphs, finite state, quantitative branches, sampled integration and declared channels, many-to-many material bindings, independent control domains, helper initialization/capacity and explicit recipient/co-delivery assignments. Exact CDS references, artificial molecular fixtures and conditional behavior claims remain distinct. Unrestricted molecular mechanism discovery, biological simulation and empirical therapeutic validation remain unimplemented.

- Preserve the distinction between exact artifact identity, model-conditional claims, and empirical evidence. Never label an unresolved biological claim as verified.
- Python authoring will construct typed descriptions. Python control flow must not silently stand in for cellular runtime behavior.
- Carry requirement identities, target context, assumptions, and source correspondence through each compiler pass. Unsupported semantics should produce explicit diagnostics.
- Preserve distinct DNA and RNA alphabets and explicit conversions in shared construction/reference infrastructure. The current therapeutic compiler emits RNA payloads only. Sequence optimization must recheck the higher-level properties it can affect.
- Keep the runtime dependency surface small. Introduce dependencies when a concrete implementation requires them.
- Keep generated build artifacts and scratch work out of version control. Do not add patient data, credentials, or proprietary biological libraries.
- Update the architecture and roadmap when an implementation changes their assumptions.

- Follow `docs/behavior-semantics-v0.1.md` for the executable semantic profile and `docs/toolchain-contracts.md` for downstream obligations. Behavior execution is a language reference, not a biological simulator.
- Follow `docs/realization-checking-v0.1.md` for model checks. Keep candidate execution independent from the behavior evaluator. Preserve non-vacuous coverage and all dependency identities; change tool/profile versions when their semantics change. Never broaden a finite-trace result into a universal or empirical claim.

## Development cadence and validation

Follow the [product vision and integration roadmap](docs/product-vision-and-integration-roadmap.md)
for the 2026-10-08 direction: standalone researcher usefulness first, with the
same compiler and independent verifier serving future agents and closed-loop lab
adapters. Keep lab integration outside the critical path of independently complete
standalone releases and preserve the existing human immune-cell RNA product scope.

Active user-approved delivery work follows
[the researcher-alpha roadmap](docs/researcher-alpha-roadmap.md). Keep its real
research qualification, software rehearsal, hosted validation and release exits
distinct. Preserve the independent expected outputs and complete original inputs.

Follow [development validation](docs/development-validation.md) for the approved
CI protocol. Commit useful local checkpoints freely, push coherent batches, and
merge a cohesive completed feature when its exact revision passes the required
checks. Do not require a fresh remote run for every small local edit or hold a
finished feature for unrelated future work. Preserve active PRs and their valid
running checks unless a necessary correction changes the tested revision.

- User instruction, 2026-10-07: keep the inner loop local with focused pure-Python,
  typing and static checks; when native validation is needed, use one focused
  hosted run per coherent batch. Documentation-only work needs no native build.
  Use complete cross-platform/installed validation for the integration
  candidate and fresh actual-main validation. Batch integration PR updates;
  existing PR-triggered gates are unchanged.
- Select early feedback by changed profile and shared dependencies. Shared
  semantics, transport, authority, packaging or receipt changes require broader
  checks. Profile-specific feedback is a separate scope, not a reduced complete
  census. Until scoped hosted routing is implemented, the supported development
  workflow still requires every declared native suite and SDK observation.
- Profile bottlenecks before adding concurrency. Prioritize repeated canonical
  encoding/fingerprinting where measured; reuse only owned immutable data within
  an explicit invocation, preserving exact bytes, resource limits, execution
  guards, rejection behavior and cumulative publication charges. Do not cache
  acceptance or bypass the fresh compiler/checker under test.
- Preserve infrastructure failure evidence and use bounded same-run/revision
  failed-job recovery when supported. Stop retrying persistent provider or
  billing failures and continue independent safe work. Record outstanding gates.
- Use one PR validation run per update, main-branch push validation, and explicit
  manual dispatch when needed; avoid duplicate branch-push and PR runs.
- Keep all discovered unit tests on Python 3.11 and 3.14, partitioned into five
  balanced shards per version. Exact discovery accounting must reject missing,
  duplicate, failed, canceled or stale execution; skipped jobs are not a pass.
- Run installed-package, integration, browser and reproducibility checks in
  parallel. Keep all existing commands, expected-failure assertions, independent
  verification, exports and artifact comparisons when moving work between jobs.
- Use measured per-test/class and job timings to rebalance. A 10–20 minute hosted
  validation cycle is a target to measure, not a guarantee or a reason to remove
  coverage. Runner availability and slow remaining work must remain visible.
- Reuse immutable fixture inputs where useful, but never substitute a cached
  PASS, stale authority or skipped checker for fresh validation of the current
  revision. Preserve revision/platform metadata and fail-closed aggregate gates.

## Native build storage

Production semantic paths currently use Python; the accepted migration adds an
experimental OCaml core and TypeScript Studio sources. Follow
`docs/language-migration-roadmap.md` and `protocol/core-v1.md`; do not promote
structural intent validation into translation acceptance or silently switch an
unmigrated operation's authority. Keep editing and static work local, and run
OCaml or Rust compilation, executable native tests, extension rebuilds and native
packaging on hosted CI by default. Local native compilation, including implicit
builds through package managers, requires explicit authorization for the work.
Do not silently fall back to local native builds. Record the tested revision and
platform and preserve required validation gates. Studio's tracked generated JS
and hash manifest are release assets needed by installed Python packages; check
them against the pinned TypeScript sources before any CI step regenerates them.
Keep native build trees, dependency installations and other scratch outputs out
of version control.

- Follow `docs/component-contracts-v0.1.md` and `docs/component-linking-v0.1.md` for component changes. Keep model/reference identities locked, providers and resource assumptions explicit, and sequence-only references free of dynamic claims. Component compatibility does not upgrade finite-history evidence.

- Follow `docs/construct-ir-v0.1.md` and `docs/construct-checking-v0.1.md` for assembly. Compare candidates against frozen layout authority and independent reference pins; never use output claims as expected values. Layout changes invalidate affected composition and behavior evidence. The supported reference construct remains one whole CDS with unknown delivered context; multi-molecule acceptance is unsupported; sequence emission is a separate checked exact-CDS stage.

- Follow `docs/molecular-ir-v0.1.md`, `docs/molecular-checking-v0.1.md` and `docs/exact-cds-pipeline-v0.1.md` for emission. DNA and RNA reproduce their own independently pinned records. Exact nucleotide equality, linked-reference consistency and protein translation are separate checks. Optimization is disabled. Keep unknown delivered-molecule features explicit, and recheck current authoritative inputs before export.

- Follow `docs/build-manifest-v0.1.md` and `docs/reference-build-v0.1.md` for packaging. Keep run metadata outside canonical build identity, require independent request/build authority for fresh verification, reconstruct with current checkers and publish one validated archive atomically. Imported PASS labels and self-supplied hashes never establish authority.

- Follow `docs/semantic-regression-matrix-v0.1.md`, `docs/verification-exploration-v0.1.md` and `docs/verification-independence-v0.1.md` when extending verification. State explored state/time bounds and fixed suffixes, keep UNKNOWN distinct from failure, preserve a selected failure during reduction and require both active and inactive response coverage. Bounded model checks never become empirical or universal claims.

- Follow `docs/molecular-behavior-v0.1.md`, `docs/payload-profiles-v0.1.md` and the source limits in `docs/m9-evidence-review.md` for molecular correspondence and whole-molecule readiness. Rerun source/CDS checks against independent authority. A linkage or structural-readiness PASS cannot become biological behavior, reference promotion or complete-payload compiler admission. Citation labels, fitted parameters and proposed adapter identities do not establish independent validation. Preserve explicit topology/end chemistry and retain software fixtures as artificial evidence.

- Follow `docs/human-acceptance-contract-v0.1.md` for M10.4. Keep source behavior and prohibitions conjunctive; never let evaluator-only healthy classification or an external shutdown request silently override the source guard. Distinguish cell input-access loss from evaluator missingness. Preserve coverage, unknowns and explicit unimplemented actuator/evidence obligations. Namespace migration invalidates historical artifact authority; follow `docs/biocompiler-migration.md` without relabeling old PASS records.

- Follow `docs/human-admission-v0.1.md` for M10.5. Re-evaluate use admission at planning, selection, fresh verification and export. Preserve evidence categories and software-use labels; no human profile is currently admitted. Policy changes invalidate dependent results and packages. Supplied-observation PASS remains separate from implementation eligibility.

- Follow `docs/human-profile-v0.1.md` for M10.6 examples and completion scope. Preserve PASS/FAIL/UNKNOWN/UNSUPPORTED, admission and compilation as separate dimensions. Exhausting supplied software trace candidates is not mechanism search or biological infeasibility. Keep the rate-constraint contradiction conditional on its stated simultaneous obligations. Do not grant human-use admission or extend a compiler profile's supported claims from example success.

- For digital design-loop extensions, follow `docs/temporal-components-v0.1.md`, `docs/synthetic-selection-v0.1.md` and `docs/synthetic-verification-v0.1.md`. Reconstruct execution from actual locked component records/wiring/bindings. Keep hard requirements separate from preferences; check all eligible bounded alternatives before ranking. Fresh report replay requires independent complete operation authority, including exact history or bounds, suffix, horizon, mode and budgets. Diagnostic model execution cannot grant candidate provenance or empirical claims.

- For multi-region molecular construction, follow `docs/molecular-design-v0.1.md`. Preserve independent fragment/layout request authority and source/destination coordinates; the generated-candidate checker must not import the assembler/emitter. Keep exact-reference reproduction distinct from new candidate construction. Recheck current authority, chemistry and every emitted region before structural completion or export. Components entry here means literal sequence fragments, with no invented intent/dynamic implementation proof. Handoff describes nominal design identity; actual material, quality, potency and human-use evidence remain unresolved.

- For source-driven molecular candidates, follow `docs/intent-candidate-v0.1.md`. Keep the full original source, human target and unresolved obligations authoritative. The first profile implements product encoding and structural architecture only; never treat constitutive cassette assembly as implementation of the source guard, secretion, shutdown or therapeutic goal. Preserve every bounded alternative and hard-constraint rejection, derive coordinates from selected whole parts, and independently check all stages and exports. Structural completion is separate from therapeutic completion and human admission. Require source-edit regressions that change the emitted sequence or explain rejection; library declarations and artificial fixtures supply no empirical functional evidence.

- For full-source implementation analysis and declared precursor construction, follow `docs/molecular-implementation-v0.1.md` and decision `0004`. Preserve every node and wrapped contract; classify unsupported semantics, missing refinements and known contradictions separately. A declared processing graph is not a dynamic or biological model. Product identities must preserve mature-protein identity across architecture alternatives. Check composite translation, junctions, cleavage coordinates, nominal chemistry and every base against independent authority. Match provider scope, compartment and target declarations without promoting supplied provenance to functional evidence. The `secreted_precursor_structure` profile remains partial therapeutic implementation; strict completeness emits no molecule. Keep the GUI's older candidate profile explicit until it is deliberately integrated.

- For supplied circuit constructions, follow `docs/circuit-construction-v0.1.md` and decision `0006`. Preserve complete independent root/operation authority and the original human request. Keep producer and reconstruction checker independent, preflight order deterministic, cumulative work bounded and multi-output steps atomic. Strict structural handoff requires every declared member, chemistry and payload-region obligation; it never establishes a molecular mechanism, reviewed publication fidelity or human admission. Artificial controls cannot close R1 or source-dependent R5–R13 gates.

- For composite RNA architecture work, follow `docs/payload-architecture-v0.1.md`.
  Preserve original source and every model operation/edge/parameter under explicit
  correspondence; execution-bearing component model pins must identify the
  supplied composite Behavior. Retain exact component/member placements and
  constituent wiring. Never equate independent shutdown, production control,
  effector activity control, RNA separation or dependency disjointness. Check
  helper bootstrap, sharing/capacity and same-recipient assumptions, counting
  every delivered helper RNA. Keep source v0.2 sampled integration and declared
  transport policies explicit; do not claim continuous budget safety or infer
  transport from bases. Unbound external helpers and unmapped component resource
  or operating-domain contracts remain unsupported. Fresh export retains both
  FASTA and complete manifest; search optimality and empirical function remain
  separate from independently checked translation.
