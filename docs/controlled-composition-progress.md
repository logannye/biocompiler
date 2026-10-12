# Controlled composition implementation progress

The extension is owned by `work/car-controlled-composition` on
`codex/dev-policy/car-controlled-composition`. Work follows the
[implementation roadmap](car-composition-reversible-control-roadmap-2026-10-12.md).
MVP and E1 remain in their existing checkouts and retain their own delivery gates.

## RC0 baseline

The implementation base is frozen first-MVP source
`0b19ef68ad029de1c10245008fddf81a3a4bfddd`, tree
`c100832f7e2127006b84a1f3212f23cdb6255a3b`. This deliberately excludes E1 feature
commits. Only the roadmap document was copied from the E1 working tree.
The earlier roadmap's E1 commit remains its inspected planning baseline.

Read-only GitHub refresh on 2026-10-12 found PR 103 OPEN at this source,
main at `b670ca767838a41188c81eba35ca0a643c8aacf4`, the first-MVP integration
run 38235352482 in progress, and no published first-CAR release in the returned
release inventory. Preserve that owner's running checks. No external state was
changed. Before integration, refresh accepted main and reconcile with separately
accepted E1 work; none of their acceptance transfers to this extension.

The app-managed worktree attempt could not resolve the local E1 reference. An
ordinary separate Git worktree was then created from the existing frozen MVP
commit. No repository configuration or protected checkout was changed.

Five baseline static checks passed: language schema conformance, semantic
inventory, source-context inventory, material-rule inventory and migration
inventory. These check source representation/accounting only. Unlike E1's older
base, this base includes the corrected static-expression inventory registrations.
Current original component-material request versions occupy v0.1 through v0.13;
v0.14 is reserved for controlled composition in the new specification.

Baseline records, exact commands, metadata, profile census, logs and protected
checkout fingerprints are retained under
`generated/car-controlled-composition/rc0/`. Native execution, installation and
empirical assessment have not occurred. Free disk was approximately 2.65 GB at
the baseline snapshot; keep acquisition and generated outputs bounded and run
all native work hosted under the applicable authorization.

## Milestone state

| Milestone | State | Evidence and next action |
| --- | --- | --- |
| RC0 | Complete locally | Owned branch, read-only upstream refresh, protected-checkout snapshot, five static baselines, explicit reconciliation path and progress record. |
| RC1 | Complete locally | Reviewed semantic decision, independent schema, typed descriptions, immutable source snapshots, literal wire fixtures and 41 declarative acceptance cases. Frozen 442-test runs passed on Python 3.11 and 3.14; both typing configurations and all seven static checks passed. Native admission and execution were outside that checkpoint. |
| RC2 | Acquisition checkpoint complete; gate open | The separately named patent pair #197/#206 has source-pinned literal fragments/products and bounded consistency checks. The authorized-input importer and two complete RNA adaptations remain open; see the acquisition assessment. |
| RC3 | Complete for admission and finite input-domain support | Closed v0.14 original authority, native source/material/context closure, complete finite-domain enumeration, guarded read-only admission and immutable Python transport. Hosted development validation and independently audited evidence are bound to `8b4506ed5013e21b1dbb58c34e22d31cd9b84df2`; see the RC3 validation receipt. |
| RC4 | Complete for the direct-root artificial two-RNA subset | Fresh native construction, independent full-pair reconstruction and atomic structural publication; no behavior or numeric stoichiometric-range claim. Hosted development and independently audited evidence bind `a2a1d53345987cfd339bef17e696fa5141293b76`; see the RC4 validation checkpoint. |
| RC5 | Planned | Add activity semantics, source requirement monitors and independent model/candidate checking over the RC3 domain. |
| RC6 | Planned | Complete ResearchProject, export/reopen and installed starter. |
| RC7 | Planned | Coherent hosted, cross-platform, installed and artifact acceptance. |
| RC8 | Planned | Reconcile, integrate, validate actual main and publish under its own evidence. |

Track implementation, local checking, hosted validation, installed acceptance,
release and empirical status separately. A checked specification or artificial
case is not executable profile acceptance. Commit useful local checkpoints;
do not modify MVP/E1 branches, running jobs, releases or automations.

## Next implementation slices

The user explicitly selected continued software work with artificial fixtures
on 2026-10-12; real RNA inputs will follow. Keep each fixture labeled artificial
and retain complete original authority. Do not silently fill missing regions
in the named patent reference or infer its activity model from requested answers.

RC3 authority, admission and input-domain support are implemented and validated.
Its typed source obligations and original correspondence are ready for later
executable lowering; RC3 does not execute an activity model or source monitor.
Remaining implementation slices are:

1. **RC5 behavior.** Add executable activity lowering, independent candidate
   interpretation and source requirement monitors over the complete RC3 domain.
   Check onset, cessation and reactivation with explicit state ownership, lifecycle,
   availability, unknowns and work bounds. Exact realization of the supplied
   mechanism and satisfaction of source deadlines remain distinct checks.
   Any quantitative expression/stoichiometric ranges required by the selected real
   interaction need RC2 inputs, a versioned contract and independent RC5 checks
   before named-case completion; current binary availability does not supply them.
2. **RC6 joined workflow.** Join fresh behavioral and structural evidence before
   advertising full controlled compile/check/export. Add ResearchProject v0.3,
   independent-original Verify-only reopen, an editable starter and an installed
   rehearsal. RC4's separate structural publication does not supply the missing
   behavior capability or complete this joined workflow.
3. **RC7/RC8 acceptance and release.** Complete cross-platform and installed gates,
   integration, fresh actual-main validation and artifact audit for the joined
   candidate. Preserve the first-MVP/E1 owner and their separate gates. RC2's real
   reference and complete RNA adaptations remain open in parallel.

Connect `policy_controlled_source` and `policy_controlled_domain` to executable
activity lowering and independent reference interpretation without widening
legacy profiles. Reuse RC4's exact original material binding when joining evidence;
never manufacture private capabilities. Register new native suites and retain
focused local pure/static feedback plus coherent hosted validation.

## RC1 validation checkpoint

The final local batch passed 442 tests on each of CPython 3.11.15 and 3.14.3
on macOS arm64. Both required typing configurations passed (40 core transport
files and 46 policy files). Seven static checks passed: wire-schema conformance,
semantic inventory, public API inventory, source-context inventory, material-rule
inventory, migration inventory and the declarative foundation corpus.

The tested source is frozen MVP base plus the 36-file manifest with canonical
SHA-256 `63dc29f4ca73e986788860f3ae1f4eeb6a9c6d75bf7b91a4a9df5937f4d328f2`.
The [validation receipt](controlled-composition-rc1-validation.json) binds the
local source checkpoint, file hashes, exact test commands, results and retained
log identities. There was no native build/execution, installed acceptance, remote
mutation, release or empirical assessment.

Earlier failed attempts are retained, not relabeled: the first batch exposed
26 outdated inventory/test assertions per Python version; the second test batch
passed but a separate static check found a stale generated migration inventory.
The final batch followed those repairs and regeneration on unchanged frozen files.
No old coverage disposition or historical comparison hash was weakened.

Independent review found no RC1 design/interface blocker and no premature native
capability advertisement. The 41 expected cases are declarative and unexecuted;
their corpus checker is structural only. The legacy 45-record schema retains its
exact bytes, and legacy authoring rejects controlled activity. MVP and E1 HEADs,
branches, working-tree status and planning-file hashes match the RC0 snapshot.

Local RC1 source checkpoint: `060666350ed40dc4f6e75084a04091fcbd694d93`.
The accompanying acquisition metadata and validation receipt are a separate local
documentation checkpoint; no push, PR, hosted run or release was performed.

## RC3 implementation checkpoint

The user authorized artificial fixtures and hosted native validation on
2026-10-12. RC3 is an additive native admission route, separate from all existing
MVP/E1 source and material profiles. The original request is closed v0.14 and
retains complete source definitions, model, two complete artificial MA/MG RNA
roots, expected products, context, assembly, domain and resource authority. No
real reference RNA design has been inferred from the acquired fragments.

The controlled domain is a factorized Cartesian grammar with explicit fixed
frames, executor-owned controller/availability, generation-owned antigen
evidence, reusable encounters, a finite intervention cutoff and a hold-physical
suffix. Missing, stale, invalid and conflicting evidence cannot rewrite physical
inputs. Every permitted prefix is retained even when states converge. A domain
contradiction rejects the entire request; cancellation or exhaustion cannot
produce admission. A fixed example and independent 12-history Cartesian case
passed their literal native test censuses on hosted CI.

The new `admit-policy-component-material` operation is read-only on Core and
Verify. Its capability is separate from compile/check/export. The result binds
the complete originals and full source correspondence, includes grammar and
traversal counts, and reports construction/behavior as `not_performed` and
empirical status as `unassessed`. A one-shot native guard owns the work budget
through publication of the exact complete protocol response.

RC3 initially admits exactly two direct complete supplied roots, explicit RNA
regions and chemistry, one declared product per member and no transforms,
complexes or helpers. This is an explicit admission restriction, not material
reconstruction or translation evidence. RC4 adds independent construction and
RC5 adds source/behavior acceptance. See the [request contract](controlled-composition-request-v0.14.md),
[domain grammar](controlled-composition-domain-v0.1.md), and
[admission operation](controlled-composition-native-admission-v0.1.md).

## RC3 validation checkpoint

The tested implementation is `8b4506ed5013e21b1dbb58c34e22d31cd9b84df2`,
tree `d6c7c5c5608e7436fa68a2cb16df975b9dbda82c`. The complete hosted development
workflow [38283992405, attempt 1](https://github.com/logannye/biocompiler/actions/runs/38283992405)
passed on Linux x86_64. It built fresh native binaries once and completed all
59 selected native suites, 14 controlled-admission observations, 21 quantitative
observations, all ten existing SDK campaigns (278 observations), and the
first-MVP CAR campaign (22 observations with 29 evidence files).

At the same frozen revision, 542 pure-Python tests passed on each of CPython
3.11.15 and 3.14.3 on macOS arm64, along with all eight static checks and both
typing configurations (41 core transport files and 47 policy files). These local
checks performed no native compilation or native execution. Independent audits
verified local receipts, source/log hashes, historical metadata and protected
MVP/E1 assets, followed by the complete hosted result census and retained evidence.

The [RC3 validation receipt](controlled-composition-rc3-validation.json) binds
the exact implementation tree, hosted run/attempt/artifact, complete changed-file
manifest, local commands and logs, audit receipts and protected-checkout states.
The later documentation checkpoint is not a new native-validated source revision.
The two earlier hosted compiler-warning failures remain retained as failed runs;
they provide no native pass evidence. An initial supplemental source manifest
predated those fixes; its failed audit is preserved and explicitly superseded by
the final 62-file manifest and passing audit.

Admission remains read-only and limited to complete original authority and its
supplied finite input domain. The fixed fixture enumerates 1 history, 11 transitions
and 12 prefixes; the Cartesian fixture enumerates 12 histories, 113 transitions
and 114 prefixes. No branch or converged prefix is silently dropped. Exhaustion,
cancellation and contradictions cannot produce admission. The hosted cancellation
campaign covers prelaunch cancellation; native unit tests separately exercise the
domain callback. It does not establish arbitrary midflight transport cancellation.

This is RC3 development validation, not cross-platform/installed or release
acceptance. The 41 RC1 full-profile cases remain declarative rather than executed
activity-verification results. RC2 complete real RNA designs and reference
qualification remain open; RC4 construction and RC5 behavior verification are
next. No clinical or empirical assessment, merge or release was performed. Both
MVP and E1 checkouts retain their baseline commits and working-tree changes.

## RC4 implementation scope

The [RC4 material contract](controlled-composition-material-v0.1.md) defines the
separate structural constructor/checker/publication capability. Complete original
authority stays immutable; the independent checker freshly admits originals and
reconstructs the two delivered RNAs before checking geometry, translation, exact
chemistry and actual resource limits. The ordered pair publishes as one atomic
FASTA/manifest ZIP only after fresh checking. No legacy behavior capability is
manufactured. Numerical stoichiometric contracts remain outside the admitted
closed subset, and binary availability is not evidence of assembly. RC5/RC6
remain necessary for reversible behavior and the joined workflow.

## RC4 validation checkpoint

The [RC4 validation receipt](controlled-composition-rc4-validation.json) records
the exact source, run, artifact, local checks, independent audits and protected
checkout states for this checkpoint.

The tested implementation is `a2a1d53345987cfd339bef17e696fa5141293b76`, tree
`cc246ae062b8baf8fd49fd25ed4a6ed1040463fb`. The complete hosted development
workflow [38296469528, attempt 1](https://github.com/logannye/biocompiler/actions/runs/38296469528)
passed on Linux x86_64 with fresh native binaries: all 63 selected native suites,
23 RC4 material observations, 14 controlled-admission observations, 21 quantitative
observations, all ten existing SDK campaigns (278 observations), and the first-MVP
CAR campaign (22 observations, 22 native actions and 29 evidence files).
Independent audits checked the exact source/run/attempt, retained originals,
reports, mutation diagnostics, binary/import pins and published bytes. Binary
identity is limited to retained same-run pins where executable bytes were not
part of the downloaded artifact; no offline auditor reran native code.

At the same frozen revision, 562 pure-Python tests passed on each of CPython
3.11.15 and 3.14.3 on macOS arm64. All eight static checks and both typing
configurations passed (42 core transport files and 48 policy files). Local
checks performed no native compilation or execution. The earlier run
38294711313 at `f5d87eacda4abe028ee0a98e8da28deafa000a89` remains a failed gate;
its three test corrections received this fresh complete validation.

Completion covers exactly two direct, complete supplied artificial RNA roots,
independent reconstruction and atomic structural publication. The literal pair
contains two 17-nt RNAs encoding MA and MG; it supplies software evidence only.
Numeric expression/stoichiometric ranges, physical assembly, reversible activity,
empirical function and human use are not validated. RC2 complete real RNA designs,
RC5 behavior, RC6 joined ResearchProject/export/reopen, RC7 installed/cross-platform
acceptance and RC8 integration/release remain open. The RC3 sections above retain
their historical checkpoint statements. This later documentation update does not
transfer native acceptance to a different implementation revision.
