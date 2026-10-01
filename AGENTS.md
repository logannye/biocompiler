# Working on biocompiler

The sole product purpose is to translate high-level Python and eventually natural-language therapeutic intent into exact, complete DNA/RNA specifications for immune cells engineered in vivo in humans. Prioritize work that connects source requirements to selected molecular implementations and emitted bases. Quantitative execution and evaluation should support those selected implementations, with explicit observation maps and evidence, rather than become a disconnected simulator. Natural-language authoring and complete therapeutic compilation are not yet implemented.

## Human-only product scope

User clarification, 2026-09-30: only human biology and DNA/RNA payloads for
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
evidence. Molecular circuit generation remains unimplemented.

## Current implementation and engineering rules

biocompiler implements Python intent authoring, immutable build/realization requests and intent/behavior graphs, authoritative lowering, checked passes, automatic combinational/temporal synthetic generation and bounded digital implementation selection, abstract reference execution, finite-trace checking against independent synthetic models, typed component contracts, offline composition linking with executable digital assembly reconstruction, reusable JSON verification workflows, single-CDS reference construct assembly and independently checked exact-reference DNA/RNA emission with reproducible offline reference packaging. A separate software molecular-design profile assembles and independently checks multi-region RNA specifications from supplied fragment/layout authority. The partial intent-candidate compiler now selects a supplied product CDS and RNA architecture from source requirements, derives the layout and emits an independently checked structural cassette. Exact CDS references, artificial molecular fixtures and synthetic behavior remain distinct. General molecular mechanism selection, biological simulation and human therapeutic-payload generation remain unimplemented.

- Preserve the distinction between exact artifact identity, model-conditional claims, and empirical evidence. Never label an unresolved biological claim as verified.
- Python authoring will construct typed descriptions. Python control flow must not silently stand in for cellular runtime behavior.
- Carry requirement identities, target context, assumptions, and source correspondence through each compiler pass. Unsupported semantics should produce explicit diagnostics.
- Treat DNA and RNA as distinct compilation targets. Sequence optimization must recheck the higher-level properties it can affect.
- Keep the runtime dependency surface small. Introduce dependencies when a concrete implementation requires them.
- Keep generated build artifacts and scratch work out of version control. Do not add patient data, credentials, or proprietary biological libraries.
- Update the architecture and roadmap when an implementation changes their assumptions.

- Follow `docs/behavior-semantics-v0.1.md` for the executable semantic profile and `docs/toolchain-contracts.md` for downstream obligations. Behavior execution is a language reference, not a biological simulator.
- Follow `docs/realization-checking-v0.1.md` for model checks. Keep candidate execution independent from the behavior evaluator. Preserve non-vacuous coverage and all dependency identities; change tool/profile versions when their semantics change. Never broaden a finite-trace result into a universal or empirical claim.

## Native build storage

The initial implementation is Python-only. If Rust is introduced, keep editing and static work local, and run compilation, executable native tests, extension rebuilds, and packaging on hosted CI by default. Local Rust compilation, including implicit builds through package managers, requires explicit authorization for the work. Do not silently fall back to local native builds. Record the tested revision and platform and preserve required validation gates.

- Follow `docs/component-contracts-v0.1.md` and `docs/component-linking-v0.1.md` for component changes. Keep model/reference identities locked, providers and resource assumptions explicit, and sequence-only references free of dynamic claims. Component compatibility does not upgrade finite-history evidence.

- Follow `docs/construct-ir-v0.1.md` and `docs/construct-checking-v0.1.md` for assembly. Compare candidates against frozen layout authority and independent reference pins; never use output claims as expected values. Layout changes invalidate affected composition and behavior evidence. The supported reference construct remains one whole CDS with unknown delivered context; multi-molecule acceptance is unsupported; sequence emission is a separate checked exact-CDS stage.

- Follow `docs/molecular-ir-v0.1.md`, `docs/molecular-checking-v0.1.md` and `docs/exact-cds-pipeline-v0.1.md` for emission. DNA and RNA reproduce their own independently pinned records. Exact nucleotide equality, linked-reference consistency and protein translation are separate checks. Optimization is disabled. Keep unknown delivered-molecule features explicit, and recheck current authoritative inputs before export.

- Follow `docs/build-manifest-v0.1.md` and `docs/reference-build-v0.1.md` for packaging. Keep run metadata outside canonical build identity, require independent request/build authority for fresh verification, reconstruct with current checkers and publish one validated archive atomically. Imported PASS labels and self-supplied hashes never establish authority.

- Follow `docs/semantic-regression-matrix-v0.1.md`, `docs/verification-exploration-v0.1.md` and `docs/verification-independence-v0.1.md` when extending verification. State explored state/time bounds and fixed suffixes, keep UNKNOWN distinct from failure, preserve a selected failure during reduction and require both active and inactive response coverage. Bounded model checks never become empirical or universal claims.

- Follow `docs/molecular-behavior-v0.1.md`, `docs/payload-profiles-v0.1.md` and the source limits in `docs/m9-evidence-review.md` for molecular correspondence and whole-molecule readiness. Rerun source/CDS checks against independent authority. A linkage or structural-readiness PASS cannot become biological behavior, reference promotion or complete-payload compiler admission. Citation labels, fitted parameters and proposed adapter identities do not establish independent validation. Preserve explicit topology/end chemistry and retain software fixtures as artificial evidence.

- Follow `docs/human-acceptance-contract-v0.1.md` for M10.4. Keep source behavior and prohibitions conjunctive; never let evaluator-only healthy classification or an external shutdown request silently override the source guard. Distinguish cell input-access loss from evaluator missingness. Preserve coverage, unknowns and explicit unimplemented actuator/evidence obligations. Namespace migration invalidates historical artifact authority; follow `docs/biocompiler-migration.md` without relabeling old PASS records.

- Follow `docs/human-admission-v0.1.md` for M10.5. Re-evaluate use admission at planning, selection, fresh verification and export. Preserve evidence categories and software-use labels; no human profile is currently admitted. Policy changes invalidate dependent results and packages. Supplied-observation PASS remains separate from implementation eligibility.

- Follow `docs/human-profile-v0.1.md` for M10.6 examples and completion scope. Preserve PASS/FAIL/UNKNOWN/UNSUPPORTED, admission and compilation as separate dimensions. Exhausting supplied software trace candidates is not mechanism search or biological infeasibility. Keep the rate-constraint contradiction conditional on its stated simultaneous obligations. Do not enable human compilation from example success.

- For digital design-loop extensions, follow `docs/temporal-components-v0.1.md`, `docs/synthetic-selection-v0.1.md` and `docs/synthetic-verification-v0.1.md`. Reconstruct execution from actual locked component records/wiring/bindings. Keep hard requirements separate from preferences; check all eligible bounded alternatives before ranking. Fresh report replay requires independent complete operation authority, including exact history or bounds, suffix, horizon, mode and budgets. Diagnostic model execution cannot grant candidate provenance or empirical claims.

- For multi-region molecular construction, follow `docs/molecular-design-v0.1.md`. Preserve independent fragment/layout request authority and source/destination coordinates; the generated-candidate checker must not import the assembler/emitter. Keep exact-reference reproduction distinct from new candidate construction. Recheck current authority, chemistry and every emitted region before structural completion or export. Components entry here means literal sequence fragments, with no invented intent/dynamic implementation proof. Handoff describes nominal design identity; actual material, quality, potency and human-use evidence remain unresolved.

- For source-driven molecular candidates, follow `docs/intent-candidate-v0.1.md`. Keep the full original source, human target and unresolved obligations authoritative. The first profile implements product encoding and structural architecture only; never treat constitutive cassette assembly as implementation of the source guard, secretion, shutdown or therapeutic goal. Preserve every bounded alternative and hard-constraint rejection, derive coordinates from selected whole parts, and independently check all stages and exports. Structural completion is separate from therapeutic completion and human admission. Require source-edit regressions that change the emitted sequence or explain rejection; library declarations and artificial fixtures supply no empirical functional evidence.

- For full-source implementation analysis and declared precursor construction, follow `docs/molecular-implementation-v0.1.md` and decision `0004`. Preserve every node and wrapped contract; classify unsupported semantics, missing refinements and known contradictions separately. A declared processing graph is not a dynamic or biological model. Product identities must preserve mature-protein identity across architecture alternatives. Check composite translation, junctions, cleavage coordinates, nominal chemistry and every base against independent authority. Match provider scope, compartment and target declarations without promoting supplied provenance to functional evidence. The `secreted_precursor_structure` profile remains partial therapeutic implementation; strict completeness emits no molecule. Keep the GUI's older candidate profile explicit until it is deliberately integrated.

- For supplied circuit constructions, follow `docs/circuit-construction-v0.1.md` and decision `0006`. Preserve complete independent root/operation authority and the original human request. Keep producer and reconstruction checker independent, preflight order deterministic, cumulative work bounded and multi-output steps atomic. Strict structural handoff requires every declared member, chemistry and payload-region obligation; it never establishes a molecular mechanism, reviewed publication fidelity or human admission. Artificial controls cannot close R1 or source-dependent R5–R13 gates.
