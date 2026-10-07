# Semantic mRNA compiler: session handoff

Prepared 2026-10-06, America/Los_Angeles. **Closure snapshot: PR95 merged; corrected PR85 gate running;
public selection development passed its independent artifact audit.** Resume from this document and the
[development tracker](semantic-mrna-development-plan.md); do not restart the
architecture discussion or recreate implemented routes. The [README](../README.md)
describes the public vision and current functionality.

The portable packet is [the dated handoff directory](semantic-mrna-handoff/2026-10-06/README.md).
It contains the [reviewed next implementation design](semantic-mrna-handoff/2026-10-06/metered-generation-review.md)
and [machine-readable checkpoint/evidence index](semantic-mrna-handoff/2026-10-06/state.json).
Generated evidence stays in its original worktree; this packet copies no large
artifacts, executables, environments, credentials or patient data.

## Final user direction at session close

On 2026-10-06 Pacific, the user deferred waiting for validation and merging in
this session and requested a clean handoff for continued development in a fresh
Codex session. No further merge, validation restart or active monitoring is part
of this session. The existing hosted PR85 run may finish independently; no
workflow cancellation or automatic merge was requested or configured.

The next development task is **metered selection candidate generation**, using
the reviewed design in this packet and the independently audited selection source
`fbd2230e82d6ba448ae5aa4cdf33ebc0978df16b`. Keep PR85's tested source
`0b2fc34b8b82d5956c81f550a7e5bf9fdf9f15e1` frozen. Development can proceed
in its separate checkout while release validation remains pending. Refresh the
existing run's state on resume; do not restart completed work or treat a green
CI label alone as the required independent release audit.

## Scope and completed source work

The target remains semantic correctness from the Python therapeutic-design DSL
through exact mRNA under supplied, versioned implementation and construction
contracts. Biological viability is outside compiler acceptance. Studio and
conversational authoring are deferred. Python construction-time control flow
does not define the policy's runtime behavior.

Implemented bounded layers include rich source declarations and native
assessment; operational semantics and typed behavioral/implementation IR;
lowering and producer-independent bounded preservation/requirement checking;
whole-graph material realization; reusable two-component composition; exact
single-member RNA construction; immutable Python transport; and fresh paired
FASTA/manifest export. Standalone Verify remains independent of the producer.
These statements describe implemented scope, not blanket release acceptance.
Legacy Behavior architecture routes and rich-policy profiles retain their own
contracts. The reference-package route already has source implementations in
the preserved continuation worktree; its remaining work is compatibility and
hosted acceptance, not recreation.

Finite material selection now has source implementations for closed request and
candidate codecs, independent common-authority reconstruction, complete child
checking, rank/ASCII-ID selection, a shared work/publication scope, native
check/replay/export, and a thin Python client with complete outer manifests.
All losing alternatives remain authoritative. An edited loser invalidates saved
acceptance even if the winner's RNA is unchanged. **Selection compilation is
not implemented.** Its reviewed metering design is preserved in this packet.

## Worktrees and ownership

Paths below are relative to the workspace root
`/Users/logannye/Documents/ChatGPT/GeneMedicineCompiler`. Run Git commands in
the listed checkout: the workspace root is not the shared implementation Git
checkout. Full hashes and the complete observed worktree list are in `state.json`.

| Worktree | Branch | Observed HEAD | Purpose / next action |
| --- | --- | --- | --- |
| `work/policy-component-composition` | `codex/policy-component-composition` | `278f452eccf695a84144f6e69e49bcb0d30cc8b3` | Frozen PR85 source; retain its failed run unchanged |
| `work/session-release-corrections` | `codex/session-release-corrections` | `0b2fc34b8b82d5956c81f550a7e5bf9fdf9f15e1` | Frozen PR85 correction plus README/roadmap/handoff; full run `37563795844` active |
| `work/policy-material-selection` | `codex/policy-material-selection` | `fbd2230e82d6ba448ae5aa4cdf33ebc0978df16b` | Pushed public selection with empty-log correction `8806cf6c4`; run `37562370369` and both independent development audits passed |
| `work/bounded-policy-execution` | `codex/policy-material-export` | `bb84421cf1f93cd1dc02813d80a2c54a3520a919` | Accepted PR95 source, merged as `ddf8e8a603`; main run rejected a Python patch mismatch |
| `work/component-release-audit` | `codex/component-release-audit` | `1c67b5b3c0346bcb8cf2a8b3539056cf004e15fe` | Stable component auditor, already pushed; integrate deliberately later |
| `work/semantic-mrna-tracker` | `codex/semantic-mrna-tracker` | `6a7d70fea717c27d60ed1e7776cf489e5c559f69` | README/tracker and this handoff; final documentation commit will advance HEAD |
| `work/reference-package-continuations` | `codex/reference-package-continuations` | `b7a176dd5c75e700b9aa86ac8006b70fcb3eaf57` | Preserve implemented reference-package continuation |
| `work/release-audit-tools` | `codex/release-audit-tools` | `6d73d74e73ca8f760d32f28ea9cbbd4c1e9d4925` | Earlier stable auditor; keep its old profile authority intact |
| `work/m11-human-evidence` | `codex/ocaml-package-distribution` | `a85b1112ff35ba988a71cc969bfabdfefb354cfe` | Historical accepted union and original release evidence |

The code correction changes only `tools/check_policy_material_prebuilt.py` and
`tests/test_policy_material_prebuilt.py`; the integrated branch also includes the
README, roadmap and closure packet. The source correction is committed as `59c514d72`; independent source review
and 29 guarded pure tests passed on each supported Python. It has no fresh
hosted acceptance. README/tracker/handoff integration may advance this branch. Preserve
all other checkouts and any pending user changes.

## Pending gates and retained diagnoses

**PR85 component release.** Current pushed head is
`0b2fc34b8b82d5956c81f550a7e5bf9fdf9f15e1`; [fresh full run 37563795844](https://github.com/logannye/biocompiler/actions/runs/37563795844)
is running. Its tested merge `66741e5918c4b1b6fd842dfacc91ea7a11dcb9f3`
has ordered parents `[ddf8e8a6031e342ac9fda7b94b03ae35f859bb20, 0b2fc34b8b82d5956c81f550a7e5bf9fdf9f15e1]`
and identical source tree `52a72fff46625e9ae2be6de7a1bc77fc13a910a5`.
Run attempt 1 uses suite `101756034891`; its suite predecessor is
`e95d2ee5e3a825966d872f3f155ef19e1ce732e9`, independently confirmed as the
candidate's first parent. Initial authority is retained under
`work/session-release-corrections/generated/complete-release/37563795844/`.
This checkout is sparse (historical `tests/conformance` excluded); restore the
complete tracked checkout before preparing the complete-source release audit.

The superseded [full run 37551706364](https://github.com/logannye/biocompiler/actions/runs/37551706364)
cannot pass. Its original source H is `278f452ec`, tested C is
`b2a5a860be1745d707f7781d17e158d4a2261aeb`, and the equal H/C tree is
`dee01a8bbc3d213cdc7aaa5c44aecdabb2146d1a`. The prebuilt comparison incorrectly
used wheel RECORD bytes as authority for pip's installed RECORD. Retained
actual slot artifacts distinguish the installed 38,435-byte RECORD from the
22,918-byte wheel RECORD; original module bytes agree. The narrow correction
must authenticate installed RECORD restoration and wheel-owned rows against
the actual wheel, permitting only specified installer-added records. It must
not weaken the installed mutation or full artifact comparisons.

Evidence is under
`work/policy-component-composition/generated/complete-release/37551706364/failures/policy-prebuilt-reproducibility/`
(`job.json`, log, `diagnosis.json`, `slot-linux-py311.zip`, `sdk.zip`). The diagnosis
hash in the evidence index identifies the initial hypothesis; the retained ZIPs
provide the subsequent confirmation. Preserve the failed attempt as failure.
All 20 installed campaigns finished successfully before the necessary revision
update. The old cohort then terminated with 68 successful, three failed and
three cancelled jobs; incomplete downstream checks remain incomplete. Do not
restart or wait on that superseded cohort. The corrected head requires a **fresh complete**
74-job / 59-ordinary-receipt / 156-native-suite / 102-selected-archive gate and
independent audit, followed by normal merge and fresh actual-main validation.
The stable auditor's `complete-component-release-v1` profile preserves the old
whole-graph checks; do not relax it or transfer old receipts to a new revision.

**PR95 original bounded policy release.** Exact source `bb84421cf` passed
[run 37450940506](https://github.com/logannye/biocompiler/actions/runs/37450940506),
all 42 jobs, and independent final audit
`d331a734c0b863ba4a4e228c66bc260f54113368925634850baeace907be05cd`.
The original proof remains under
`work/bounded-policy-execution/generated/policy-realization/acceptance-37450940506/final-refresh-20261006T144143Z/final-audit-output/proof.json`.
PR95 merged normally on 2026-10-06 Pacific as
`ddf8e8a6031e342ac9fda7b94b03ae35f859bb20`. Its separate actual-main
[run 37561753806](https://github.com/logannye/biocompiler/actions/runs/37561753806)
has failed unit shards: the runner selected different CPython patch versions
from their plans and correctly rejected execution as stale. The plan-bound
interpreter correction already exists in the PR85 source. Retain this run as a
failed main attempt; the later corrected main requires a fresh complete gate
and artifact audit before actual-main acceptance. The PR95 audit does not accept PR85 or selection.

**Public selection development.** Previous failed source H
`70f81df1ca62819dcda5f63ea6691af07f9c5ea8`, tree
`56cbb9865c0bf66d5db12d54d4068c3ee91164a2`, is tested by
[run 37561211151](https://github.com/logannye/biocompiler/actions/runs/37561211151).
It failed after all 23 native suites and the old component SDK campaign passed.
The selection stage rejected the authenticated fixture exporter's empty successful
log. The one-line correction `8806cf6c4` accepts an empty log only with its exact
SHA-256/size, successful status and zero return code. Twenty-four guarded
pure controls pass per supported Python; root source review passed. Retain
this failed run as failure. Corrected pushed source
`fbd2230e82d6ba448ae5aa4cdf33ebc0978df16b` (tree
`e2d6a5cbf7a8b2d346245f1e5d9441a4c30a1b9c`) is tested by
[run 37562370369](https://github.com/logannye/biocompiler/actions/runs/37562370369),
passed all 23 native suites, 26 existing SDK observations and 21 new selection
observations. Independent data-only audits on Python 3.11.15 and 3.14.6 passed,
authenticating 1,163 immutable source files, every original alternative and child
obligation, all 90 outer ZIP entries and six exact paired program archives. Both
audit proofs have SHA-256
`e0035a155c779913d421486170c8b726bdbd156733b9c775420ca80b310476b2`.
Artifact `11458380864` is 2,329,016 bytes with SHA-256
`dd3afa8241e748ee0bcfb564682a202de08af838c2ada453ab01a8294f3ee4ed`.
Proofs are retained under
`work/policy-material-selection/generated/hosted-development/37562370369/`.
No native code was executed locally. This closes development validation only.
Require the exact 23-suite native campaign, unchanged 26-observation component
SDK campaign, new 21-observation selection SDK campaign, actual paired artifacts,
binary/source identities and complete retained ZIP audit. Development success
does not supply installed, complete release or actual-main acceptance.

Earlier public-selection failures are retained, not relabeled:

| Run | Subject and diagnosis | Retained correction |
| --- | --- | --- |
| [37559445249](https://github.com/logannye/biocompiler/actions/runs/37559445249) | H `c546fb6705f920bf7c08eef9bc65d672f7e5fd74`; build failed at nonexistent `CV.fingerprint`; no native suites or SDK observations executed | Scoped hashing of complete original-bound candidate JSON; correction committed at `af062c550` |
| [37559878104](https://github.com/logannye/biocompiler/actions/runs/37559878104) | H `505dd1230aede88cfb1ca0a6ad00c865e9a950cb`; build passed, 22/23 suites passed; `test_protocol` had stale advertised-operation census; SDK campaigns skipped | Exact capability-census test correction `e79be46b4bd1feefba76b213653478a4426bac81`, included in current H |

Their original API, logs, archives, diagnoses and protocol-correction static
proofs remain under
`work/policy-material-selection/generated/hosted-development/<run-id>/`.
Known file hashes are in the dated state file. No current-run result was copied
or assumed before its final evidence existed.

## Prepared audit tools and preservation

The exact reviewed selection success auditor is saved in the
[dated packet](semantic-mrna-handoff/2026-10-06/audit-selection-development.py),
SHA-256 `b095bccd26553c81c3f716b27570a660613738fdecaf92c587c7e428c927436a`.
The original remains at
`work/policy-material-selection/generated/selection-publication-integration/audit-development.py`.
It has now passed on both Pythons against the exact successful run above; retain
those proofs rather than repeating the completed audit. For a later source, its
required arguments are
`--root`, `--evidence-dir`, `--head`, `--tree`, `--run-id`, `--run-attempt`,
`--suite-id`, `--job-id`, `--artifact-id`, `--artifact-size`,
`--artifact-sha256` and `--source-count`. Capture raw final run, commit, jobs and
artifact metadata separately; validate the externally pinned ZIP and run on
both supported Pythons. It preserves 90 ZIP entries, 23 native suites, 26 old
component observations and 21 selection observations, complete originals and
paired artifacts. It performs no native execution and cannot establish installed
or release acceptance. Do not regenerate a convenient expected census from output.

The stable component auditor remains `codex/component-release-audit` at
`1c67b5b3c0346bcb8cf2a8b3539056cf004e15fe`, explicitly using
`--profile complete-component-release-v1`. Its nine adapter correspondences passed
all eight guarded tests per Python against corrected source `59c514d72`;
proofs are under `work/component-release-audit/generated/record-correction-review/`.
No adapter or reviewed function pin needed changing for the RECORD fix. Rebuild
source/catalog and current-run authority for the final corrected release head.

Both previously local-only historical branches are now pushed:
`codex/policy-boundary-witnesses` at `0e79df920` and
`codex/reference-package-continuations` at `b7a176dd5`. Preserve their history;
do not merge the old continuation stack wholesale. Its route implementations
are already part of the release integration. The completed parallel session's
PR87/88 roadmap acceptance record is also preserved at `62e83759f` and included
in the current tracker. No historical worktree was reset or deleted.

## First actions on resume

1. Read this handoff, the current README, tracker and applicable `AGENTS.md`.
   Inspect `git status --short`, branch and exact HEAD/tree in every active
   checkout. Refresh GitHub PR85/PR95, main and the named runs through read-only
   API calls. Check for a later closure update before using this snapshot.
2. Reconcile PR95's normal merge and actual-main status with exact parents/tree
   and fresh push-run evidence. Preserve the original 42-job proof's subject.
3. Continue the reviewed RECORD correction and closure documentation from the
   final pushed correction branch `0b2fc34b8`. Inspect fresh run `37563795844`,
   restore the complete checkout for the audit and update exact-source authority.
   Regenerate an exact-source audit plan;
   never reuse the failed subject's plan as new acceptance.
4. Preserve the accepted selection development subject `fbd2230e8` and its
   completed both-Python audit. Public selection checking/replay/export no longer
   needs another development repair. Metered candidate generation is the next
   source task; keep it separate from the frozen PR85 release candidate.
5. Ship the accepted bounded component compiler first. Integrate selection as a
   subsequent complete increment with its own installed/offline/release gates.
   Merge stable audit and tracker branches deliberately; they are not assumed
   present on main just because they are pushed or included in selection.
6. Implement the preserved metered-generation design in the separate selection
   development checkout; this source work need not wait for PR85 to merge. Reuse
   the existing architecture and shared scope. Keep helpers, finite-machine
   extensions and multiple RNA members for later complete profiles. Update the
   tracker at source/tested/merged/main milestones rather than polling events.

All OCaml/Rust compilation, executable native tests and packaging remain hosted.
No local native fallback or package-manager implicit rebuild is authorized.
Use focused pure/static checks locally, retain source/run/parent/tree identities,
and never count a skipped, partial, historical or merely source-reviewed result
as acceptance. JSON Schema document consistency still needs its separately
recorded hosted validator work; do not claim it from native decoding alone.

## Resume prompt

> Continue Biocompiler development from
> `/Users/logannye/Documents/ChatGPT/GeneMedicineCompiler/work/semantic-mrna-tracker/docs/semantic-mrna-session-handoff.md`
> and the adjacent `semantic-mrna-development-plan.md`. We deferred merge work
> at session close. Verify current worktree and GitHub identities, preserve the
> frozen PR85 candidate and its existing run, and begin the reviewed metered
> selection-generation milestone from audited source `fbd2230e8` in the separate
> development checkout. Keep all native compilation, execution and packaging
> hosted. Preserve completed audits and the implemented reference-package route;
> do not recreate them. Update the tracker as milestones actually complete.
