# Fresh-session handoff: finish the existing-workflow language migration

Prepared 2026-10-02 from the current source roadmap, source receipts and frozen agent packets. This is a resumable engineering handoff, not a completion or release claim. The GitHub status described here is the state before the checkpoint push; refresh the branch PR and its exact run before treating any pending work as accepted.

**Consolidation update, 2026-10-03:** the user approved validating and merging
PR85 with a merge commit and proving every PR60–84 head is contained in `main`.
After that proof, close any remaining superseded PRs. Remove obsolete remote
branches only after main validation. Keep the checkpoint branch and local worktrees.
Refresh all older heads before cleanup. Source
`817a8ed1154975befd293327dfabdf7798ed2b4c`, run `37109100797`, passes both
native jobs and SDK-wheel assembly after the
[SDK metadata correction](migration-handoff/2026-10-03/sdk-wheel-correction/correction.json).
The fresh macOS slots on Python 3.11.9 and 3.14.7, plus Linux 3.14.7, pass
package lifecycle, protocol and routing checks, then fail the installed manager
receipt checker. Its deferred-context comparison ignores the actual source-link tuple binding
and compares only the native typed document, whose link array is intentionally
empty on that path. The retained Python 3.11 evidence has ten such observations
across eight cases, differing only in `source_links`; Python 3.14 reports the
same checker exception, also confirmed on Linux 3.14.7. None of these installed
receipts is a PASS.
Read the [retained failure evidence](migration-handoff/2026-10-03/deferred-context-correction/evidence.json).

The checker correction reconstructs that tuple from the actual registered
producer, ordered materialization and native scalar-check receipts. All 37
focused controls pass on each local runtime; six new tests bring discovery to
3,397 test IDs with none removed. Offline checking now validates all 86 original cases and 16,346 retained artifacts on
local Python 3.11.15 and 3.14.6, using an exact historical trace-source overlay.
The original receipt remains failed; replay is not a new native run or a fresh
installation. See the [correction receipt](migration-handoff/2026-10-03/deferred-context-correction/correction.json).

That receipt correction is committed at
`00fbfac6510183d5ddd7cd224305b1c2ccf915ca`. Its run `37120447580` exposes a
separate source-witness failure in Python 3.11 shard 2: the immutable 14-file
installed-path proof still expects the checker before the additive context
correction. The shard executes 690 tests with one failure at that whole-source
hash assertion. The follow-on adds a separately pinned two-span restoration of
only the reviewed function and comparison call before the unchanged historical
hash and AST assertions. All 44 focused controls pass on Python 3.11.15 and
3.14.6. Discovery adds one test, reaching 3,398 IDs with none removed. The
original witness and prior correction receipts remain immutable; product and
checker semantics are unchanged by this follow-on.
See [retained source-witness correction](migration-handoff/2026-10-03/deferred-source-witness-correction/correction.json).

The follow-on source `0dd0fe54f3d1f0e502b30188f096cb5387fbb9b2`, run
`37121925726`, passes both complete native jobs, SDK assembly and all 3,398
unit tests on both runtimes. Its freshly installed macOS/Python 3.14.7 manager
campaign succeeds: 5 identity, 34 comparison and 47 deferred cases. Independent
replay consumes and rehashes all 16,346 artifacts with the current checker and
no historical overlay. The next campaign fails before native execution because
its fixed-provider oracle loader compares the current registration-routed
`pipeline.py` directly with the historical pin. The same finite registration
lineage is already checked in the continuation campaign. Apply it to this one
provider source, retaining the frozen oracle and the other 28 exact source pins.
The adjacent registration runtime also still expects flat binary paths; its
correction uses the same owned-layout resolver as the other installed campaigns,
preserving all role/root/path/hash/symlink/executable checks. The complete original
runtime is restored after exactly the import and path edits. All 40 focused
controls pass on both local Python runtimes; discovery preserves every prior
test and adds ten, for 3,408 IDs/350 classes. The correction and its separate
installed-path source counterpart are recorded
in [fixed-provider lineage evidence](migration-handoff/2026-10-03/fixed-provider-lineage-correction/correction.json).

Corrected exact-source validation, all four fresh-install campaigns and the
complete 38-job release gate remain required before consolidation. Finish this
consolidation and its authorized cleanup before resuming migration scope. Do not
report this checkpoint as merged or release-accepted from partial results.

## Copy/paste task for the next Codex session

Resume Biocompiler's Python-to-OCaml semantic-core migration. Preserve the user's language decisions: TypeScript/HTML/CSS for Studio; Python for scientific authoring, orchestration and exploratory search; OCaml for semantic analysis, behavioral/mechanism/architecture/molecular compiler passes, independent verification, canonical artifacts and export acceptance. The physical biological system remains empirical, outside software compilation.

Start by inspecting the actual Git branch/HEAD/status and reading `docs/language-migration-roadmap.md`, `docs/migration-session-handoff.md`, `protocol/migration-prebuilt-source-checkpoint.json`, and the saved packets listed below. Historical handoff headings and earlier successful jobs do not establish current acceptance. Preserve existing work; do not restart the migration or replace original corpora with new expectations. Continue implementation and meaningful validation, updating the specific `LM-[ ]` items only when their stated exits are evidenced. Keep concise progress updates.

**All four user-directed cutoff gates are OPEN. Python remains the production default.** Finish all four, record exact-revision evidence, then pause for the user's decision about the next phase:

- **LM-CUTOFF-1:** manager compatibility, fixed-producer typed returns and every remaining currently supported workflow family, with public behavior preserved.
- **LM-CUTOFF-2:** existing SDK/CLI/Studio routing and native ownership of canonical package content/export acceptance.
- **LM-CUTOFF-3:** accepted prebuilt distributions and successful fresh installation on supported platforms.
- **LM-CUTOFF-4:** switch validated profiles to native, retire their production Python semantic paths, and pass the complete integrated release gates for the exact final revision.

Conversational authoring and expanded Studio functionality are deferred. Existing Studio workflows are not deferred. Biological quality/correctness work has **not** begun; its scope is a decision after the cutoff, not an assumed next implementation and not a consequence of software parity. Do not equate model checking, source equivalence or artifact integrity with experimental biological reliability.

All OCaml/Rust/C native compilation, native executable tests, extension rebuilding, wheel assembly and fresh native installation must run on hosted CI or an already-authorized remote environment. Do not run Dune, opam builds, cargo, hidden package builds or native binaries locally. Local source edits, static checks and pure Python/scripted-subprocess controls are allowed. No silent Python fallback on a selected native error. No unsupported-profile rejection can replace a previously supported workflow and be counted as migration completion.

## Exact checkpoint boundary

At preparation, the working branch is `codex/ocaml-package-distribution`, based on PR84 commit `56c710a47560297969b2f7159a430340d2feeafe`. The distribution integration and the source correction for PR84's native warnings are in the current working tree. The root agent is checkpointing this work now.

The complete checkpoint is saved on [`codex/ocaml-package-distribution`](https://github.com/logannye/biocompiler/tree/codex/ocaml-package-distribution). Resolve its current source with `git rev-parse HEAD` and inspect its consolidation PR with `gh pr list --head codex/ocaml-package-distribution --state all`. At document creation, the checkpoint's hosted validation and merge are pending. A later successful merge does not close the four migration cutoff gates.

The last fully accepted main checkpoint before this batch was PR59, main commit `d2f65c59aba3a4af97dbcabd59e8142961e12c4a`. PR83's native-library milestone is narrower. PR84 failed as described below. Do not transfer a previous run's results to this checkpoint.

The committed packet is [`docs/migration-handoff/2026-10-02/`](migration-handoff/2026-10-02/README.md). Its manifest binds all unfinished source and original evidence. Run `python3 tools/restore_migration_handoff.py` to verify it, then add `--restore` when the original ignored locations are absent. Identical files are accepted; differing local files are preserved and cause refusal. The packet contains no native build trees or disposable caches. Its fresh-directory restoration was checked against every retained member.

For a concise task prompt, use [`docs/migration-resume-prompt.md`](migration-resume-prompt.md).

The outer `SESSION_HANDOFF.md`, `SESSION_NEXT_IMPLEMENTATION.md`, `SESSION_ROADMAP.md` and `SESSION_LANGUAGE_VALIDATION.json` belong to the local parent workspace, not necessarily a fresh checkout. This committed document supersedes their older PR84 headings. The next session must not depend on the old machine retaining those outer files.

## What is present, and what its evidence actually establishes

There is a substantial native domain/checker/producer foundation, persistent fixed/callback managers, typed Python views, exact artifact/container libraries and explicit public adapters. The reference package library milestone on PR83 source `64eb5a3964c726abab4e3691c6eb13bd53c25693`, run `37090290216`, passed all 117 native suites and direct package/export steps on Linux x86_64 and macOS arm64. It did not establish complete release/public-package acceptance. Read `protocol/migration-reference-package-native-milestone.json` and `docs/migration-reference-package-workflow.md`.

PR84 added same-manager Molecular attempts, bounded LIFO scopes, retained provider identities and historical Build views; its source receipt is `protocol/migration-reference-manager-reuse-checkpoint.json`. PR84 run `37091936085` failed native compilation at nine warning-as-error sites. The current finite correction adds four record annotations and removes unused markers/helpers; no behavior, resource limit or assertion was changed. Both 23-test source-boundary suites pass, but corrected hosted compilation and all downstream gates are still required. Do not report PR84 as accepted.

**Prebuilt distribution source is now integrated**, rebased onto PR84 rather than applying the old packet blindly. It retains exact upstream source/notices/relink materials, specifies static GMP and portable linkage, assembles native and SDK wheel candidates, resolves owned installed files without PATH/mirrors/download/build fallback, and runs four fresh-install slots and full release accounting. The current receipt records 117 focused Python controls on each runtime, strict mypy for 28 transport modules, and all 142 original CLI child outcomes per runtime. A finite two-edit `pyproject.toml` counterpart preserves the historical CLI authorities. Discovery records 3,384 tests/346 classes per runtime; discovery is not execution. Native builds/linkage/wheels/installation/publication are not accepted yet.

The current integrated CI requires 118 native suites and 38 jobs, including the two distribution jobs. Derive the exact census from the integrated tree before adding work; never restore a stale 117-suite/36-job packet. Its 17 installed campaigns cover the existing checkpoint, **not** the final migration. The forthcoming complete public package campaign and any new suites must be added without dropping the original ones.

Useful active files:

- `src/biocompiler/core_distribution.py`; `tools/build_prebuilt_core.py`; `tools/check_prebuilt_core_release.py`; `tools/prebuilt_release_pipeline.py`; `tools/check_prebuilt_matrix.py`; `tools/prebuilt_sources.py`; `tools/collect_prebuilt_materials.py`; `tools/prepare_static_gmp.py`.
- `protocol/core-release-sources-v1.json`, `protocol/core-release-opam/`, `tools/prebuilt-build-requirements.txt`, `tools/relink_prebuilt_core.sh`.
- `tools/package_metadata_source_lineage.py` and `tests/conformance/package-metadata-source-counterpart-v1.json`.
- `src/biocompiler/core_pipeline_manager.py`, `core_reference_manager.py`, `core_reference_host.py`, `core_reference_provider_views.py`, `reference_backend.py`; `core/lib/pipeline_service/{callback_manager,reference_workflow}.ml`.
- `tools/check_pipeline_reference_install.py`, `tools/pipeline_reference_runtime.py`, `tools/reference_execution_guard.py`, `tools/reference_pipeline_transcript.py`; existing fixed-manager/provider/continuation gates.
- `docs/migration-reference-{service,public-routing,manager-reuse,package-workflow}.md`; `protocol/migration-inventory.json`; `docs/migration-coverage.md`; `tools/ci_validation.py`; `.github/workflows/ci.yml`.

## Remaining public surface: audited 20-family / 50-command map

The authoritative detailed map is the frozen `public-routing-cutover-draft/route-map.json` and `.md`. It covers all 50 actual CLI commands exactly once, with concrete public functions, native modules/operations and original test/corpus obligations. Do not treat a similarly named native type as the same public contract.

| Family | Actual remaining distinction |
| --- | --- |
| Architecture | Matching explicit native compile/verify/replay/export adapters exist; ordinary installed selection/default closure remains. |
| Realization/component/synthetic checks | Matching independent native checks exist; public selection and all callpoint/authority guards remain. |
| Synthetic verification workflows | Existing native run/replay and FD authority transport; complete ordinary routing/release remains. |
| Synthetic proposals/selection/adaptation | Matching producer/selection/inspection adapters exist; draft selection is opt-in only. |
| PassManager and fixed pipelines | Explicit native manager exists; ordinary objects, subclasses, duck wrappers and transformed access results are not complete. |
| Reference Construct/Molecular | Explicit public native context exists; full installed 18-method proof and remaining ownership profiles must pass. |
| Reference package/sequence export | Native libraries exist; package-only transport/public continuation/independent Verify packet is incomplete. |
| Synthetic canonical packages | Fixed pipelines and container primitives do not implement the complete existing synthetic package/reconstruction/export contract. |
| CircuitConstruction | Matching `Construction_producer`/`Construction_workflow` and checkers exist; matching public SDK/CLI/Studio service routing is missing. |
| Executable Payload | Construction/template pieces exist; the existing per-operator `PayloadBuild` producer/workflow/checker is not ArchitectureBuild. |
| CandidateBuild / Studio Candidate | Matching native CandidateBuild producer/checker remains missing; synthetic candidate runtime is a different contract. |
| Implementation planning/build | Matching producer/workflow/checker remains missing. |
| MolecularDesign package | Existing multi-region RNA design is not exact-CDS Reference_molecular; matching workflow remains missing. |
| Circuit intent / human scope | Native request domains alone do not implement the complete historical assessment/replay workflows. |
| Circuit source/binding/evidence/review | Metadata workflow is missing; native Boolean `Circuit_binding_check` is not public binding-request metadata. |
| Studio construction | Construction service plus original source/binding/evidence inspection/save routes remain. |
| Human admission/deployment/acceptance | Scoped native Admission_check paths exist; complete public assessment routing remains. |
| Authoring/lowering/reference | Python authoring is intentional; native kernels do not imply every historical lowering/evaluation/planning entry is routed. |
| Direct runtime/component linking | Internal kernels/checkers exist; standalone SDK routes remain incomplete. |
| Artifact inspection / Studio authoring | Presentation stays host-side; semantic per-schema import and acceptance must be separated from mere JSON canonicalization. |

Studio `/api/prepare`, `/api/compile`, `/api/export`, `/api/construction/inspect` and `/api/construction/save` must preserve their actual CandidateBuild/Construction contracts and original security/browser/assets tests. Do not substitute architecture semantics. A ContextVar set around a `ThreadingHTTPServer` factory does not propagate to handler threads. Keep installation controls out of normal Studio flows.

## Frozen unfinished work packets and ownership at handoff

Paths below are under `generated/migration-next/` until the root's preservation index says otherwise. They are ignored source packets, not installed production routes. Save their exact source/authority files in Git or a content-addressed retrievable archive before relying on a fresh checkout.

1. **`public-routing-cutover-draft/` — session_python, frozen.** `installed_backend.installed_native(*profiles, timeout_seconds=30)` selects only four already-matching adapters; `DEFAULT_PROFILES=()`. Fourteen source-local prefixes retain function/alias identity and earlier validation order. Eight hidden `--installed-core` migration flags are testing plumbing, not ordinary CLI completion. There is no Studio placeholder. New17 controls, unchanged47 controls, all51 complete help outputs and strict29-module typing passed on both installed Python versions. No native acceptance. Integration still needs exact source-counterpart consumers, closed semantic-authority guard additions, actual four-runtime replays and package-owned continuation precedence. Patch SHA `4fc00dfff976c30b74d5a6e5a3af6b5d2bb68824b64bd115d81c7f463d49b427`; 74-file manifest SHA `59774db935de458ea7587d84295be6521509283e2630f2bed05d8075e63cd608`.
2. **`reference-package-transport-draft/` — session_native, frozen incomplete.** Package owner, private FD I/O, producer-free Verify, views/host callbacks and native continuation hooks are drafted. Public context is `reference_package_core(core, verify, *, timeout, limits=None)`. A package-only 512MiB/1e10-work owner starts at hello; existing128MiB sessions are never upgraded. Preserve current build/verify/publish/export overrides and shared owner/budget. The shell still imports the **missing `core_reference_package_route.py`**; its prepare/build/reconstruct/publish/export functions are not implemented. `STATUS.json` lists the gaps. 38 Python controls per runtime, syntax17 and mypy5 pass; native suites are unexecuted. Manifest SHA `c277273132b5fb6f2100f7c5c7eb7919a04f8c98da3161de977f2c32fcebd288` covers51 payload files. It includes the source-only real-FD `test_reference_package_verify.ml`; do not count that as execution.
3. **`manager-ownership-draft/` — session_campaign, partial and isolated.** Preserve actual public object, imported/bound methods, dynamic constructor/profile/dependency/get calls and native ownership from creation. Existing ordinary Python state cannot be attached as accepted native state. Current partial split-create/virtual-get design still lacks seven original field-publication effects/live private mappings, transformed get candidates, dynamic targets, same-instance reinitialization, generic-owner Molecular continuation and full duck authority. Exact source guards/counterparts and full compatibility remain. Read its README/manifest/validation; do not integrate as a general default.
4. **`reference-package-campaign-draft/` — root, complete original baseline only.** 32 unchanged original package/audit/admission/molecular-behavior methods,270 actual public calls,3984 complete content documents and518 frozen source files. Original baseline/observed outputs agree on3.11/3.14 apart from the explicit runtime field;14 integrity controls pass each. Preserve both raw captures, all documents/source blobs and capture tool. Actual installed native Core+Verify execution, FD/frame/process/binary/source linkage and same-minor reconstruction are still required; old8 native package fixtures cannot replace these32 public bodies.
5. **`prebuilt-core-draft/` and `prebuilt-core-integration-draft/` — frozen source/provenance.** Original79-file packet targets PR83; its reviewed source is now rebased/integrated in active files. Preserve frozen materials, patches/manifests and exact rebase receipts for lineage. Active source and the final Git commit are authoritative for ongoing implementation. Do not overwrite suite118/current source witnesses with the old base.

Supporting next-work designs worth preserving: `foreign-manager-next-slice.md`, `reference-view-origin-plan.{json,md}`, `synthetic-package-export-native-plan.md`. The synthetic package plan predates the now-existing reference archive library; reuse the current library, and re-audit its old “missing library” descriptions rather than treating them as current facts. The old `reference-installed-draft`, routing draft and native-archive draft largely predate integrated work; do not accidentally apply stale versions. Retain the frozen reuse patch/manifest/validation as provenance; the31 production paths are already in PR84.

## First concrete work sequence

1. Verify the final saved source and every essential packet hash; refresh GitHub status for the exact revision. Finish source-backed CI corrections and required hosted gates without weakening old assertions. A user-authorized source checkpoint/merge is not a claim of migration acceptance.
2. Finish the package route's missing orchestrator and same-owner public callpoint continuations, then run the entire32-method installed package campaign with independent producer-free Verify. Keep original verify->current build, publish->current verify->atomic write, and direct sequence export behavior. A host PASS/report or reconstructed historical accepted record grants no authority.
3. Complete ordinary manager ownership and remaining callback/identity/partial-failure profiles, then the full generic/fixed/reference installed corpora. Preserve transformed/foreign return behavior rather than accepting equal JSON or silently rejecting supported cases as a replacement.
4. Integrate the bounded four-profile installed selector with finite source lineage and real installed evidence; then implement the remaining actual workflow families and current Studio routes from the20-family map. Assign distinct native-producer gaps separately from service/routing gaps.
5. Build portable static-linked native candidates remotely, retain source/notices/relink material, assemble and independently verify wheels/SDK pins, and run all four Linux/macOS x Python3.11/3.14 fresh-install slots plus every integrated campaign. No source or dependency change inherits earlier acceptance.
6. Only when current supported workflows and release evidence are complete, switch validated profiles and retire corresponding production Python semantics. Update all four cutoff boxes with exact evidence, then pause for the user's next-phase decision.

Maintain complete original case/operation/command/provider/record/exception/identity/order censuses. Whole-source restoration and actual installed code/canonical globals are separate proofs. Keep Python3.11 and3.14 runtime-specific proofs; never substitute local3.14 bytecode for3.11. No cloned/relabelled TestCases, blanket frame stripping, expected-result execution inputs, content-based identity interning, semantic fallback or missing-case projection. Resource accounting is lifetime-scoped and charged before allocation; cancellation closes/reaps without retry. Native acceptance binds the exact artifact exported and scoped claims, not storage location or transport success.

Local Python controls can use existing `python3` (3.14.6) and `/Users/logannye/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/bin/python3`. Strict typing uses the already-installed `generated/mypy-static/site` runtime and `tools/mypy-core.ini`; do not install/build native dependencies to run checks. Avoid repeating already-passing suites absent a source change, concrete failure or unresolved concern. Check disk usage before substantial artifact downloads and preserve intentional evidence; never delete unrelated caches/user data.


## After the migration cutoff

The user intends a fresh session dedicated to biological quality and correctness once the migration is accepted. At the cutoff, present the evidence and pause; confirm the next phase with the user instead of starting it automatically. Conversational authoring (LM-11) and expanded Studio remain a separate sequencing decision.

The product continues to target high-level therapeutic intent compiled into exact, complete RNA payload specifications for human immune cells engineered in vivo. Keep historical non-human fixtures only in their limited regression role. Retain reference part origin and exact identity; do not silently humanize sequences.

A proposed quality phase should audit end-to-end requirement traceability, causal/mechanistic adequacy of supplied component models, selected implementation/sequence correspondence, complete molecule inventories and coordinates, chemistry/processing/layout assumptions, human target and delivery context, and preservation of unsupported requirements and uncertainty. Establish discriminating independent benchmarks and adversarial cases, not merely language-port equality. Keep software correctness, model-conditional behavior, experimental applicability and clinical effectiveness as distinct claims. Literature or empirical validation must remain independently sourced and scoped; no compiler PASS establishes that a payload will work safely in vivo. This quality phase has not started and its detailed plan remains to be agreed.
