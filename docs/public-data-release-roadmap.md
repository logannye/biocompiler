# Controlled CAR: software release and public-data qualification

Decision date: 2026-10-12. **Milestone 5 is the release target.** Ship one
complete, usable research workflow from supported therapeutic intent to exact
nominal RNA specifications, conditional checking, export and independent reopen.
Public-data qualification proceeds in parallel. New wet-lab work, experimental
collaborations and in-vivo studies are deferred and do not gate this release.

This adds the real-reference and authoring work to the existing
[controlled-composition implementation](car-composition-reversible-control-roadmap-2026-10-12.md).
It does not renumber that document's RC1–RC8 engineering checkpoints. Milestones
1–7 below are product milestones; in particular, product Milestone 5 includes
the required RC release/integration gates, not just RC5 behavior checking.
The [user-facing roadmap](https://chatgpt.com/space/page_8331172e5f60819188429a193b5ff9a7)
and this repository record describe the same release boundary.

## Use-case record v0.1

| Field | Selected scope or unresolved decision |
| --- | --- |
| Program | CD19-dependent CAR activity enabled by one external controller; cessation and reactivation within a declared finite domain. |
| Molecular family | An explicitly designed two-mRNA adaptation of `WO2014127261A1-197-206`. Both products must be available in the same recipient. |
| Recipient | One declared human CD8 T-cell context. Intended product deployment remains in vivo; each evidence record keeps its actual experimental context. |
| Controller | External AP21967; the patent's Clontech catalog number is joined to the manufacturer record. Effective exposure in the new RNA adaptation is an explicit categorical assumption. |
| Observable | Named latent modeled receptor/signaling activity with ordinal background/active bands and a one-tick freshness rule. No calibrated assay conversion is claimed; killing remains separate. |
| Material | Exactly two complete coding RNAs, one product per member, complete nominal chemistry, no helper/controller RNA. The new `car197206-rna-v1` pack supplies explicit designs; source publications still supply only the original fragments. |
| Editable intent | Five response deadlines, finite horizon, member/total RNA size ceilings and supported context declarations. Antigen, mechanism family and controller are fixed for this release. |
| Release claim | Exact checked material plus conditional behavior under explicit contracts; public-evidence scope reported separately. |

The [reference-pack batch](controlled-car-reference-pack.md) freezes the
controller identity and conditional model interface. All timing, effective
availability and activity-band interpretations remain explicit uncalibrated
scenario assumptions. A biological assay-to-model map remains unqualified.
Background is not biological zero. Cessation cannot reverse completed cellular
effects. No administration or dosing regimen is generated.

## Completion gates

| Milestone | Deliverable and exit |
| --- | --- |
| 1. Freeze use case | Resolve controller and observation map; give every supported requirement a source field and interpretation. Preserve unsupported requests. |
| 2. Complete molecular pack | Retain original authority and independently prepared expected outputs for both complete RNAs, every region/base, termination, products and chemistry. Provide a distributable starter or rehearsed authorized-input route. No missing field is silently supplied. |
| 3. Bind contract | Bind material, actual mechanism, recipient/deployment and observation contracts to the exact adaptation. Label every parameter measured, source-derived, designer-assumed or unresolved. A fully supplied assumed model may support conditional checking; missing required authority cannot. |
| 4. Author intent | Add a small typed facade over the existing policy records and `ResearchProject`. An ordinary user writes supported requirements without supplying final nucleotide strings or internal JSON. |
| **5. Release** | Compile/explain/export/reopen the real example with matching released SDK, Core and Verify; freeze a candidate, pass required hosted native, cross-platform, installed, integration and fresh actual-main gates, then verify published assets. |
| 6. Deferred cellular evidence | Future evidence about control from the exact emitted RNA pair. No new experiment or experimental collaboration is in the active plan. |
| 7. Deferred in-vivo evidence | Future evidence about the exact implementation and delivery context. No new in-vivo work is in the active plan. |

Milestone 5's usability gate is an unfamiliar researcher completing install →
author → compile → inspect → export → independent reopen through public interfaces.
Target one hour after documented prerequisites, recording acquisition time,
total time, interventions and failures. Export retains exactly `program.fasta`
and `manifest.json`; retain the readable report and independent original project
alongside the archive. Failed, unknown, incomplete or unsupported requests
produce no accepted pair. An artificial fixture cannot substitute for the real
material gate.

Required demonstrations: supported baseline, feasible and infeasible deadline
edits against an unchanged mechanism, too-small RNA limits, unsupported
antigen/controller/context, stale or changed material/chemistry/evidence, and
independent reopening against independently supplied originals. Unchanged RNA
is legitimate when the same fixed implementation satisfies two source programs;
the explanation must make that resolution visible.

## Public references as reusable implementations

Use the [planning inventory](../data/public_reference_programs/qualification-plan.json)
to prioritize a small number of useful references. This is planning metadata,
not a new admission schema. Reuse existing source-readiness machinery and the
profile-specific source checkers; source availability alone is not acceptance.

1. Reuse **RM_61461 / SEQ151** as the complete nominal single-expression baseline.
   Its [qualification](car-rm61461-qualification.md) retains source-declared
   chemistry, explicit design choices and ex-vivo evidence limits.
2. Preserve **RM_61321 / SEQ113** in the separately owned E1 work. That checkpoint
   already has a distinct complete nominal RNA, factual pack, qualification and
   local preparation. Its native, installed and release acceptance remain open;
   reconcile after its owner's integration decision rather than recreate it.
3. Complete the selected **patent #197/#206** route: first reproducible import of
   existing literal coding fragments, then explicit complete-RNA authority and
   a contract for that adaptation. Published DNA coding blocks do not determine
   UTRs, termination, tail, chemistry or mRNA delivery performance.
4. Keep **Wu I.b/II.d** as separately identified mechanism evidence. Exact
   identity with #197/#206 is unresolved. Its reported killing windows cannot
   establish rapid signaling-cessation bounds for the selected adaptation.
5. Make the next targeted acquisition the **Hunter 2025 improved CAR2**
   supplements/construct records, seeking an exact join to the related patent's
   named RNAs. A citation of the patent is not that join. Stop if sufficient
   records are unavailable and retain the unresolved identity.

The primary starting sources are the [2025 patent](https://patents.google.com/patent/WO2025096878A9/en),
[official sequence listing](https://www.wipo.int/published_pct_sequences/publication/2025/0508/WO25_096878/WO2025-096878-TAB-20241115-001.zip),
[controlled-CAR patent](https://patents.google.com/patent/WO2014127261A1/en),
[Wu publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC4721629/) and
[Hunter publication](https://doi.org/10.1126/science.ads8473). Existing pinned
originals are reused; this batch does not download a new sequence collection.

Track three independent axes for each claim: material completeness, exact
construct-to-assay identity, and applicability to the requested context and
endpoint. Match sequence, chemistry, delivery modality, recipient state,
endpoint and observation window. Shared proteins, targets or citations do not
transfer a full-RNA performance claim. Preserve source locators, hashes,
correction boundaries, conflicts and distribution status. In particular, keep
the first two references' unresolved donor attribution visible.

Use public data in three separate ways:

- **Software oracles:** independently extracted reference bytes/products and
  mutation cases test reconstruction and refusal to accept stale authority.
- **Retrospective qualification:** replay published measurements against a
  contract while preserving uncertainty and original assay context. Mark these
  sources as already inspected; do not call them blind validation.
- **Held-out evaluation:** freeze extraction rules, model/contracts, metrics and
  partitions before opening outcomes. Prefer whole constructs, assays, donors
  or source families over correlated rows. Report missing data and uncertainty
  rather than selecting only favorable examples.

New complete designs can be checked in software without demonstrating that
their biological model holds. Public evidence may strengthen individual claims
but does not close all empirical dimensions. If useful evidence requires timing
ranges or variability, support those outcomes explicitly or report the model
as unsupported; do not replace them with favorable deterministic delays.

## Authoring facade specification for the next batch

The proposed facade resolves one versioned implementation entry and one supported
context. It produces a `ControlledWorkflowRequest` and then
`ResearchProject.from_controlled`, preserving all original authority. The
library maintainer owns complete material and mechanism inputs. The user owns
requirements. Preparation is not native acceptance.

| Facade input | Existing representation and rule |
| --- | --- |
| Implementation/version and context | Resolve immutable complete originals, source pins, deployment and contract identity. Reject mismatches and incomplete entries before compile. |
| Activation, controller-loss, antigen-loss, component-loss and reactivation deadlines | Existing `ActivityDeadlines` and `ControlledWorkflowRequest.with_deadlines`; convert explicit units to the fixed time resolution without changing actual delays. |
| Per-member and total RNA size limits | `with_rna_limits`; never truncate or optimize molecules to meet limits. |
| Evaluation horizon | `with_horizon` with complete supplied domain/readout inputs. Do not invent observations or extrapolate applicability. |
| Compile, export, reopen | Existing `ResearchProject.compile` and `verify_bundle`, matching Core/Verify assets, complete independent originals. No alternate checker or cached PASS. |

The facade must retain source locations for diagnostics and a trace from each
requirement through the implementation/products to RNA members and checks.
No numeric kinetic defaults or sample code implying a qualified real contract
is introduced before its authority exists. The first real starter is gated on
Milestones 1–3; artificial examples remain explicitly labeled.

## Work batches and preservation

1. **First batch, completed locally:** offline import tool and adversarial tests; use-case record,
   public qualification inventory and facade specification. Freshly replay the
   already retained originals. Keep imported metadata inert and incomplete.
2. **Material/contract batch, nominal preparation complete:** independently review transcription or obtain
   stronger original authority; close complete RNA/design inputs and exact
   controller/readout binding. Keep source facts separate from adaptation
   choices. The [prepared real pack](controlled-car-reference-pack.md) now has
   independent expected outputs and an explicit conditional contract; hosted
   native admission and independent-person transcription review remain open.
3. **Researcher batch:** implement the facade, real starter/acquisition route,
   source-edit demonstrations and readable report through existing RC6.
4. **Release batch:** freeze one integration candidate and complete Milestone 5
   acceptance and usability gates. Public qualification continues alongside it.

The owned checkout is `Biocompiler 2.0/work/public-reference-readiness`, branch
`codex/public-reference-readiness`, based on controlled-CAR revision
`17a7352b5e6ed1d087c110bedb365132280152c7`. Active RC6 work and its CI remain in
their owner's checkout. E1 remains at its separately inspected checkpoint
`11b6b6da94497fea9afae8dfa12dd900c7295f9f`; first-MVP and typed-kernel ownership
also remain separate. These are source baselines, not transferred acceptance.
Merge/rebase reconciliation and fresh acceptance belong to a later coherent
integration candidate. Native compilation/execution/packaging stays hosted.
