Resume the Biocompiler language migration from the saved checkpoint; do not
restart the architecture discussion or recreate completed work.

Repository: https://github.com/logannye/biocompiler
Local checkout: `/Users/logannye/Documents/ChatGPT/GeneMedicineCompiler/work/m11-human-evidence`
Checkpoint branch: `codex/ocaml-package-distribution`.

First read `AGENTS.md`, `docs/migration-session-handoff.md`,
`docs/language-migration-roadmap.md`, `docs/development-validation.md`, and
`protocol/migration-prebuilt-source-checkpoint.json`. Check GitHub for the
checkpoint branch's actual PR, merge and CI status. If its merge is still pending,
finish the required validation and merge before treating it as accepted. Preserve
local changes and use the latest verified repository state. Earlier PRs and
source-only receipts are historical evidence, not transferable acceptance.

The immediate task is PR85 consolidation and its already-authorized cleanup.
The checker correction at source `00fbfac6510183d5ddd7cd224305b1c2ccf915ca`, run
`37120447580`, fails one unit source-witness assertion: the old 14-file installed
path proof predates the reviewed additive deferred-context checker correction.
A separately pinned two-span restoration now precedes its unchanged assertions;
all 44 focused controls pass locally on both runtimes. Read the
[latest correction evidence](migration-handoff/2026-10-03/deferred-source-witness-correction/correction.json)
and the [earlier context correction](migration-handoff/2026-10-03/deferred-context-correction/correction.json).
The earlier offline 86-case replay passes; corrected hosted acceptance stays open.
Require the corrected revision's four complete fresh-install campaigns and all
38 required CI jobs, then merge and prove older heads are contained before
closing superseded PRs. Validate actual main before deleting remote branches.
Refresh every older PR head and use exact
compare-and-delete leases for approved obsolete branches. Keep the checkpoint
branch and local worktrees. Do not resume broader migration implementation while
this consolidation is still pending; the four migration cutoff gates stay open.

Verify and, if needed, restore the preserved WIP with
`python3 tools/restore_migration_handoff.py --restore`. This restores source and
original evidence under ignored `generated/migration-next/`; it applies no patch
and builds nothing. Read the frozen drafts' README/status/manifests, especially
the complete public-family routing census. Compose overlapping drafts against
current source rather than overwriting it with an old patch.

The agreed architecture is TypeScript/HTML/CSS for Studio; Python for scientific
authoring, conversational orchestration and exploratory proposals; OCaml for
canonical intent, semantic analysis, behavioral and mechanism IRs, deterministic
selection/acceptance, molecular construction, canonical artifacts and separate
independent verification. Physical biological behavior remains empirical.
Python authoring remains intentional. Python semantic execution is what must
retire for validated migrated profiles.

At handoff, all four cutoff gates remain open and Python remains the production
default. Continue systematically until all four are genuinely complete:

1. Finish manager compatibility, fixed-producer typed returns and every remaining
   supported workflow family without narrowing supported behavior.
2. Complete existing SDK/CLI/Studio routing and OCaml package/export ownership.
3. Ship accepted prebuilt distributions and validate fresh supported installations.
4. Switch validated profiles to OCaml, retire their production Python semantic
   paths and pass complete integration/release gates on the exact integrated revision.

Keep the roadmap's `LM-` checkboxes current. The handoff identifies completed
native foundations, the integrated prebuilt source checkpoint, the compile
correction, all unfinished drafts, exact evidence and the next implementation
sequence. In particular, package public orchestration is incomplete, generic
manager compatibility has open cases, and several public families need matching
native workflows. Do not substitute one artifact family for another or equate
structural decoding with semantic acceptance.

All OCaml/Rust compilation, native execution and native packaging must run on
hosted CI; no local native builds without explicit authorization. Preserve full
unit discovery on Python 3.11/3.14, both native platforms, immutable original
corpora, independent checker authority, exact artifact bytes and complete release
accounting. Use focused local Python/static checks and coherent hosted batches.

When the four gates are complete, pause and report the evidence. The intended
next major session is biological quality and correctness: review whether supplied
models, components and emitted complete RNA payloads faithfully express the
therapeutic requirements, while separating software correctness, model-conditional
claims and empirical human immune-cell/in-vivo evidence. Human biology and RNA
payloads remain the product scope. Do not claim clinical validity from compiler
tests. We will decide then whether conversational authoring and expanded Studio
belong in this session or another; do not start them automatically.
