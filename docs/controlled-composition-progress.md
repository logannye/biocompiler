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
| RC1 | Complete locally | Reviewed semantic decision, independent schema, typed descriptions, immutable source snapshots, literal wire fixtures and 41 declarative acceptance cases. Frozen 442-test runs passed on Python 3.11 and 3.14; both typing configurations and all seven static checks passed. Native admission and execution remain pending. |
| RC2 | Acquisition checkpoint complete; gate open | The separately named patent pair #197/#206 has source-pinned literal fragments/products and bounded consistency checks. The authorized-input importer and two complete RNA adaptations remain open; see the acquisition assessment. |
| RC3 | Representation started; admission pending | New Python declaration/serialization and generated native shape table are present. Complete request/domain/model/material admission and capability dispatch remain open. |
| RC4 | Planned | Construct and independently check both complete RNA members. |
| RC5 | Planned | Add activity semantics, source requirements, domain enumeration and independent model/candidate checking. |
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

1. **RC3 authority and admission.** Freeze the complete realization, domain,
   model, assembly, context and resource record bodies and independent wire
   fixtures before their decoders. Extend the closed v0.14 request across Python
   transport and native request/source admission. The RC1 source snapshot is
   only the four-field source/contract/context envelope; it is not this complete
   native authority. Bind source definitions, ordered products and members,
   selected model bodies, controller/readout, availability and every limit.
2. **RC3 domain.** Add the explicit controlled branch to operating-domain
   decoding, reference adaptation and source lowering. Existing domains attach
   Boolean evidence to encounters, cannot restart ended slots, and have different
   reset/end monitor behavior. Preserve them. Test executor-owned controller and
   product persistence, evidence generations, reusable encounters, the finite
   cutoff/suffix and unequal controller/antigen/component cessation deadlines.
3. **Parallel RC4 material and RC5 behavior.** Reuse staged construction and
   independent reconstruction for two complete artificial RNAs. In parallel,
   implement independent model realization and source requirement checks. Earlier
   compliant activity can satisfy a later source deadline: exact realization of
   the supplied mechanism and satisfaction of the source are distinct checks.
4. **Join before publication or capabilities.** The existing assembly checker
   requires a fresh checked implementation, and formatting requires checked
   material. Never fabricate those private capabilities to unblock RC4. Until
   RC5 and complete joined checking exist, structural diagnostics remain partial.
   Advertise the native controlled profile only after its full path exists.
5. **RC6 onward.** Bind ResearchProject v0.3, then complete fresh export/reopen,
   hosted native and installed validation, independent artifact audit and normal
   integration. Retain the first-MVP/E1 owner and their gates throughout.

The next source touchpoints are `policy_component_material_request`,
`policy_realization_request`, `policy_component_assembly_rule`,
`policy_component_context`, `policy_document`, `policy_admission`,
`policy_operating_domain` and `policy_domain_reference`. Register new native
tests in `core/test/dune` and `tools/ci_native_bundle.py`. Use focused local
pure/static feedback and a coherent hosted batch; no local native build.

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
