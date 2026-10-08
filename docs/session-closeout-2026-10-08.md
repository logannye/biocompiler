# Session closeout and next-session entry point

The user requested this stopping point on 2026-10-08: preserve the work and
prepare a fresh Codex session without another CI validation cycle. No new run,
PR source update, merge or release was started for closeout. Existing hosted jobs
were left untouched; local observers were stopped. This is a saved engineering
checkpoint, not completed integration acceptance.

## What is implemented

All five bounded compiler priorities have source implementations and separately
audited Linux development results: named component instances, typed provider
prerequisites, two independent observations, two RNA products/members with a
separate grounded helper increment, and candidate-transition congruence.
The final focused development run `37814607452` at `bc61505f9` exercised 40 native
suites and ten SDK campaigns with 260 observations. Congruence reuse remains
disabled by default because its measured bookkeeping cost exceeded the saving.
These checks establish bounded software behavior under supplied contracts,
not biological efficacy or general modular-proof reuse.

The [core checkpoint](core-architecture-session-checkpoint-2026-10-08.md)
records exact sources, audits, implementation boundaries and failure history.
The standalone/closed-loop direction remains in the
[product vision](product-vision-and-integration-roadmap.md).

## Preserved branches and evidence

| Work | Where to resume | Status |
| --- | --- | --- |
| Core integration | `work/core-composition-integration`, branch `codex/core-composition-integration`; PR source checkout `work/core-instance-composition` | Both remain frozen at `158d07fc52675c3ab2709efbc859f4d38528bebe`. [PR99](https://github.com/logannye/biocompiler/pull/99) is open and unmerged. |
| Deferred CI routing and closeout | `work/ci-change-scope`, branch `codex/ci-change-scope` | Saved on GitHub without opening a PR. Its branch matches no push workflow. Includes the README-only route, retry correction and this handoff; no full integration acceptance. |
| Current main at snapshot | `e253ed5b3370af9a7d8b9ba96af2e7f8f025798a` | Unchanged by closeout. Refresh before any integration. |

At **19:53 UTC**, existing [run 37830070576](https://github.com/logannye/biocompiler/actions/runs/37830070576)
had 25 successful jobs, 20 active, 17 queued and one failed job:
`unit-tests (3.14, 0)`, ID `113498979567`. This is a timestamped snapshot,
not its eventual result. That shard ran 966 tests; its 21 failures and one error
all came from three stale source-context registration hashes. The earlier
hash-drift error masked the negative controls' expected diagnostics.

The affected sources are `policy_implementation_binding_check.ml`,
`policy_material_context.ml` and `policy_material_context_check.ml`.
The correction must preserve their existing `deferred_boundary` disposition,
all 40 rules, 43 contexts and 15 source registrations, and the independent
declaration baseline. The isolated correction is `d0888e2cddb30133c71eb6beca5c2cd7d392bade` on the checkpoint
branch (two files, three hash substitutions each). Its coverage gate and all
31 focused pure-Python source-context tests pass. It changes no native source;
full integration remains unvalidated. Review
`work/ci-change-scope/generated/ci-routing/source-context-pin-review.json`
before cherry-picking that commit alone into the core candidate. Do not merge the
checkpoint branch wholesale, because it also contains the deferred CI route.

Local evidence beneath `work/core-composition-integration/generated/integration-review/`:

- `closeout-37830070576/snapshot.json`: raw GitHub responses and their hashes.
- `closeout-37830070576/unit-python314-shard0-failed.log`: complete failure log;
  SHA-256 `363fc899a950d7345628b1e6be145a7cc70a5484fc1506108831f0869a4645d2`.
- `closeout-37830070576/source-context-pin-drift.json`: old/current source pins.
- `session-state.json`, `README.md`, `plan.json`, `audit.py` and
  `retain_artifacts.py`: exact core integration and artifact-audit handoff.
- `ci-timing/`, `rapid-iteration-workflow.md` and
  `closeout-docs-followup.patch`: measurements and deferred documentation work.

These generated files are intentionally local evidence, not tracked release
assets. Preserve them and their owning checkouts. Before retaining large hosted
artifacts, inspect available disk and archive sizes; about 3.6 GiB was free at
the closeout check. Preserve source, unique evidence and other owners' work.

## Deferred CI routing

The initial route at `27055f1f9` passed 108 focused tests per Python version and
diagnostic run `37830438134` (54 seconds, 49 pure controls plus actual skipped
matrix-name evidence). The subsequent retry correction passed 115 focused tests
on Python 3.11.15 and 3.14.6. It authenticates earlier collapsed skipped matrix
families without allowing them to replace later required expanded jobs.
Neither result qualifies the changed production workflow or a release.

Before deploying this route, review
`work/ci-change-scope/generated/ci-routing/fullgate-audit-plan.md`.
The old core audit expects 74 successful jobs and the exact old receipt shape;
the new route has 76 selected jobs, including intentionally skipped
`docs-validation`, and added routing evidence. Keep the original strict receipt
check while auditing routing separately. A complete independent classifier replay
also needs the original event/environment authority; the workflow currently does
not separately retain `event.json`. Do not invent a main-push `before` value from
its first parent. This audit work is deferred and must precede a deployment claim.

Other optimizations are plans only: cheap readiness before expensive mandatory
regressions, checked selection of complete SDK campaigns, and measured reductions
in repeated serialization/replay/comparison. Until those are implemented, keep
the supported complete development runner. The saved project-memory notes record
the rapid iteration cadence; use focused local checks and coherent hosted batches,
with complete frozen integration and fresh actual-main gates.

## Resume in this order

1. Read this handoff and each relevant `AGENTS.md`; inspect exact branch heads,
   working trees, PR99, main and all outcomes of the existing run. Do not restart
   the architecture review or rebuild completed increments.
2. Inspect the isolated source-context pin correction and every new failure.
   Carry only the needed core corrections into the core candidate. Run cheap
   pure checks for API/rule/source-context/fixture inventories before remote work.
3. Once validation work is resumed, submit one coherent core correction batch.
   Require fresh complete cross-platform/installed results and an independent
   exact source/run/attempt/artifact/merge-parent/tree audit. Then merge normally
   and validate the actual main revision separately. Existing partial results
   and development passes do not satisfy those gates.
4. Keep CI routing deferred unless the user chooses to resume it. Before its full
   validation, finish the independent audit compatibility work described above.
   Never cherry-pick its workflow changes into PR99 just to combine checkpoints.
5. Preserve unrelated researcher-authoring, encoding, feedback, performance and
   historical migration checkouts. No branch or worktree deletion is needed.

Suggested first message for the new session:

> Resume Biocompiler from `work/ci-change-scope/docs/session-closeout-2026-10-08.md`.
> Refresh PR99 and the existing run, review the saved source-context pin correction,
> and finish core integration and fresh actual-main validation in a coherent batch.
> Keep CI routing deferred and all native work hosted; preserve unrelated worktrees.
