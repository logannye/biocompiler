Resume the Biocompiler language migration from the saved checkpoint; do not
restart the architecture discussion or recreate completed work.

Repository: https://github.com/logannye/biocompiler
Local checkout: `/Users/logannye/Documents/ChatGPT/GeneMedicineCompiler/work/m11-human-evidence`
Checkpoint branch: `codex/ocaml-package-distribution`.

Latest checkpoint: the user requests continuation in a fresh session after safe
consolidation. PR85 remains unmerged until its corrected exact source passes all
38 jobs. Prior source `4790ac559c70a77dcbd0141331609b837bba0096`, run
`37150039387`, passes both full native jobs, SDK assembly and 3,416 unit tests per
runtime; four fresh slots were still running. PR86's parallel workflow/synthetic
CLI failures exposed a shared installation harness defect: invoking the fresh
Python does not put its installed console script on `PATH`. The new correction
prepends that environment's scripts directory and requires its exact console,
rejecting host fallback. See
[console correction evidence](migration-handoff/2026-10-03/installed-console-correction/correction.json).
Refresh the actual new source/run instead of reusing the prior run. No older PR
has been closed and no branch deleted. PR86 also has a separate stale native-runner
unit assertion to correct without reducing coverage. Keep its branch and history.

First read `AGENTS.md`, `docs/migration-session-handoff.md`,
`docs/language-migration-roadmap.md`, `docs/development-validation.md`, and
`protocol/migration-prebuilt-source-checkpoint.json`. Check GitHub for the
checkpoint branch's actual PR, merge and CI status. If its merge is still pending,
finish the required validation and merge before treating it as accepted. Preserve
local changes and use the latest verified repository state. Earlier PRs and
source-only receipts are historical evidence, not transferable acceptance.

The immediate task is PR85 consolidation and its already-authorized cleanup.
Source `b27f52447f49c749d33cac17f3bbb6fe772cbc24`, run `37133499708`,
passes both complete native jobs, SDK assembly and all 3,408 unit tests on both
runtimes. Its fresh macOS/Python 3.14.7 manager campaign passes all 86 cases.
The original temporal provider case then exceeds the callback session's
one-million-node lifetime ceiling; the next continuation would reach 1,020,793
nodes. Its whole campaign is failed. The correction introduces callback resource
profile v2 with a two-million-node lifetime budget and an explicit one-million-node
per-frame ceiling. All other caps, framing and original campaign cases remain.
Exact declaration matching rejects mixed endpoint profiles. Native and Python
transport plus the independent receipt checker enforce both budgets. Finite
source witnesses preserve whole historical sources and immutable oracle data.
Read the [callback-budget correction evidence](migration-handoff/2026-10-03/callback-budget-correction/correction.json)
for measured failure, exact source pins, local controls and remaining hosted work.
No complete fresh-install slot or full release gate is accepted yet.
The next shared defect was exposed sooner by PR86's parallel campaigns (source
`ee61eb3e94d0bf93abb308cad7715080be4ed524`, run `37148026804`): all
three provider cases and 18 returns complete, but native nested scalar mappings
have `type` second instead of last. Scalar/interval native reconstruction now
matches original public field order; curve roots retain their original order.
The existing native domain suite adds recursive, repeated-normalization and
reversed-input order checks without changing semantic fixture values or the
frozen provider oracle. Read
[literal-order evidence](migration-handoff/2026-10-03/literal-order-correction/correction.json).
The preceding PR85 source `2eb0ac643075966f3803bdfdb174f0d12bff2d75`
passes all 118 native suites and all 3,416 unit IDs on both runtimes; that partial
evidence cannot validate this native correction. PR86 remains a separate draft;
its workflow optimization is not integrated into PR85's 38-job gate.
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
