# Semantic mRNA compiler: session handoff

Prepared 2026-10-06, America/Los_Angeles. **Closure snapshot: PR95 merged; PR85 and
public selection still require corrected hosted validation.** Resume from this document and the
[development tracker](semantic-mrna-development-plan.md); do not restart the
architecture discussion or recreate implemented routes. The [README](../README.md)
describes the public vision and current functionality.

The portable packet is [the dated handoff directory](semantic-mrna-handoff/2026-10-06/README.md).
It contains the [reviewed next implementation design](semantic-mrna-handoff/2026-10-06/metered-generation-review.md)
and [machine-readable checkpoint/evidence index](semantic-mrna-handoff/2026-10-06/state.json).
Generated evidence stays in its original worktree; this packet copies no large
artifacts, executables, environments, credentials or patient data.

## Active selection-generation increment

The current branch is `codex/dev-policy/selection-generation` in
`work/policy-material-selection`, based on `fbd2230e8`. The preceding public
selection development run `37562370369` has succeeded since the closure snapshot.
This branch adds metered Core selection generation under the reviewed design;
its new source has no inherited native or release acceptance. Guarded Python adapter/SDK/witness checks (29) and inventory/source checks (113) have passed on installed Python 3.11.15 and 3.14.6 across focused runs, with process, network and native loading denied. The initial 142-test runs encountered a concurrent interface-pin update only in source-context tests; the affected 113-check reruns passed after the reviewed update. These local checks do not establish native or hosted release acceptance. Strict core and policy Python typing also passed on 3.11.15.

The initial native checkpoint `9c782d2b5` reached hosted compilation in run `37570769562` and failed strict interface warnings before native validation. Five narrow interface corrections preserve runtime source: four comment-separation fixes and an anonymous functor-signature parameter. A fresh integrated-source hosted run and artifact audit remain required.

Keep the original three Verify operations and the full component campaign.
The new producer profile and 35-observation selection witness supersede only
Core's former compile-unsupported control; Verify still cannot compile. Complete
new native validation and an exact-source artifact audit before promoting this
increment. The user selected state machines and staged regimens as the following
profile; do not start that work by treating an authorable machine as an accepted
molecular implementation.

One read-only release refresh found PR85 still open at `0b2fc34b8`, with
`37563795844` failed on exact-source-restoration preflight checks. Main remains
`ddf8e8a603`; its separate run `37561753806` is still running with failures already
recorded. Preserve that separately owned release work. The remaining sections
and dated packet below retain the earlier closure evidence and ownership map.

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
| `work/session-release-corrections` | `codex/session-release-corrections` | `59c514d72` | Reviewed, committed RECORD-comparison correction; final closure docs will advance HEAD |
| `work/policy-material-selection` | `codex/policy-material-selection` | `70f81df1ca62819dcda5f63ea6691af07f9c5ea8` | Current public selection batch; obtain fresh hosted result and audit |
| `work/bounded-policy-execution` | `codex/policy-material-export` | `bb84421cf1f93cd1dc02813d80a2c54a3520a919` | Accepted PR95 source, merged as `ddf8e8a603`; separate main run pending |
| `work/component-release-audit` | `codex/component-release-audit` | `1c67b5b3c0346bcb8cf2a8b3539056cf004e15fe` | Stable component auditor, already pushed; integrate deliberately later |
| `work/semantic-mrna-tracker` | `codex/semantic-mrna-tracker` | `6a7d70fea717c27d60ed1e7776cf489e5c559f69` | README/tracker and this handoff; final documentation commit will advance HEAD |
| `work/reference-package-continuations` | `codex/reference-package-continuations` | `b7a176dd5c75e700b9aa86ac8006b70fcb3eaf57` | Preserve implemented reference-package continuation |
| `work/release-audit-tools` | `codex/release-audit-tools` | `6d73d74e73ca8f760d32f28ea9cbbd4c1e9d4925` | Earlier stable auditor; keep its old profile authority intact |
| `work/m11-human-evidence` | `codex/ocaml-package-distribution` | `a85b1112ff35ba988a71cc969bfabdfefb354cfe` | Historical accepted union and original release evidence |

The isolated correction owns only `tools/check_policy_material_prebuilt.py` and
`tests/test_policy_material_prebuilt.py`. The source correction is committed as `59c514d72`; independent source review
and 29 guarded pure tests passed on each supported Python. It has no fresh
hosted acceptance. README/tracker/handoff integration may advance this branch. Preserve
all other checkouts and any pending user changes.

## Pending gates and retained diagnoses

**PR85 component release.** [Full run 37551706364](https://github.com/logannye/biocompiler/actions/runs/37551706364)
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
Let remaining healthy jobs finish. A corrected head requires a **fresh complete**
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
is in progress. Require its fresh complete gate and artifact audit before
recording actual-main acceptance. The PR95 audit does not accept PR85 or selection.

**Public selection development.** Current source H
`70f81df1ca62819dcda5f63ea6691af07f9c5ea8`, tree
`56cbb9865c0bf66d5db12d54d4068c3ee91164a2`, is tested by
[run 37561211151](https://github.com/logannye/biocompiler/actions/runs/37561211151).
It failed after all 23 native suites and the old component SDK campaign passed.
The selection stage rejected the authenticated fixture exporter's empty successful
log. A narrow correction is being prepared; retain this failed run as failure.
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

## First actions on resume

1. Read this handoff, the current README, tracker and applicable `AGENTS.md`.
   Inspect `git status --short`, branch and exact HEAD/tree in every active
   checkout. Refresh GitHub PR85/PR95, main and the named runs through read-only
   API calls. Check for a later closure update before using this snapshot.
2. Reconcile PR95's normal merge and actual-main status with exact parents/tree
   and fresh push-run evidence. Preserve the original 42-job proof's subject.
3. Continue the reviewed RECORD correction and closure documentation from the
   final pushed correction branch. Require fresh full PR85 validation and update
   exact-source audit inputs after the failed existing attempt finishes. Regenerate an exact-source audit plan;
   never reuse the failed subject's plan as new acceptance.
4. Close the current selection development run and independently audit complete
   original artifacts. If it fails, retain the specific diagnosis and make only
   the necessary coherent correction. Keep the existing release source separate.
5. Ship the accepted bounded component compiler first. Integrate selection as a
   subsequent complete increment with its own installed/offline/release gates.
   Merge stable audit and tracker branches deliberately; they are not assumed
   present on main just because they are pushed or included in selection.
6. After those boundaries are secure, implement the preserved metered-generation
   design as the next selection batch. Reuse the existing architecture and shared
   scope. Keep helpers, finite-machine extensions and multiple RNA members for
   later complete profiles. Update the tracker at source/tested/merged/main
   milestones rather than polling events.

All OCaml/Rust compilation, executable native tests and packaging remain hosted.
No local native fallback or package-manager implicit rebuild is authorized.
Use focused pure/static checks locally, retain source/run/parent/tree identities,
and never count a skipped, partial, historical or merely source-reviewed result
as acceptance. JSON Schema document consistency still needs its separately
recorded hosted validator work; do not claim it from native decoding alone.

## Resume prompt

> Continue Biocompiler from `docs/semantic-mrna-session-handoff.md` and
> `docs/semantic-mrna-development-plan.md`. Verify live branch, PR, run and main
> identities first; preserve all worktree ownership and retained failed evidence.
> Close the isolated installed-RECORD correction and exact component release
> gates, reconcile PR95 normal merge/actual-main validation, and audit the current
> public selection batch before integration. Keep all native work hosted. Do not
> recreate completed layers or the implemented reference-package route. Selection
> compile remains unimplemented: use the dated reviewed metering design only
> after the current acceptance boundaries close. Maintain the tracker as each
> source, hosted, merge and main milestone actually completes.
