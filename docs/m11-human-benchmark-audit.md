# M11.1 human benchmark and evidence audit

Audit date: **2026-09-29, America/Los_Angeles**. Baseline:
`79b9d4dc7953fa08ff34c00cd4b2d153785d7b1c`. This bounded public-source audit
evaluates the [M10 proposed profile](human-profile-v0.1.md). Its machine-readable
[candidate and gap inventory](../data/evidence/m11-human-benchmarks/audit.json)
is an audit record, not a compiler registry or admission authority.

## Decision

**Defer selection of a complete human therapeutic benchmark.** Prioritize the
Roybal 2016 for direct human secretion observations and Allen 2022 for
complementary component/context review. Retain Equalizer-L as a separate human-cell-line
reporter/model benchmark candidate. Keep the three previous delivery/molecule
leads as comparators. This audit has not established the entire
sequence–material–measurement–model–deployment chain required by M10 for any
reviewed candidate.

This completes M11.1's bounded comparison and justified deferral decision after
source review. It does not complete M11, promote a reference, validate a model,
admit a human profile or enable `compile()`. M11.2–M11.6 and M10's biological
acceptance remain open. The search is not exhaustive; no evidence gap here proves
biological infeasibility or the absence of an accessible resource elsewhere.

The proposed one-RNA, cytoplasmic, human in-vivo profile remains unchanged.
Transcription-based secretion circuits depend on DNA response elements and
experiment-specific engineered cells. Treating those as a supported single-RNA
implementation would require an unestablished mapping. A future modality or
deployment change must explicitly revise the profile and its evidence obligations.

## Candidate comparison

| Candidate | Evidence available for this audit | Decision and principal blocked claim |
| --- | --- | --- |
| [Roybal 2016](https://doi.org/10.1016/j.cell.2016.09.011) | Primary human T-cell antigen-conditioned secretion; author-hosted paper and resource identifiers | Prioritized behavior lead. Complete experimental sequence/material linkage, reversible per-cell rate bounds and the proposed RNA delivery are unestablished. |
| [Allen 2022](https://doi.org/10.1126/science.aba1624) | Human CD8 T-cell conditional IL-2 work and animal-context evaluation | Prioritized behavior lead, kept distinct from Roybal. Exact records, corrected-source reconciliation, recovery observations and matched predictive model require further review. |
| [Zhang 2015](https://doi.org/10.1158/1078-0432.CCR-14-2085) | Patient-context observations after administration of ex-vivo engineered TILs, including adverse outcomes | Negative/clinical-context comparator. Does not establish in-vivo RNA engineering, bounded reversible secretion or applicability to a different product. |
| [Yang 2021 Equalizer-L](https://doi.org/10.1038/s41467-021-23889-0) | Versioned circular-DNA records, processed human Flp-In 293 fluorescence tables and archived models | Retain for scoped reporter/model curation only. No therapeutic secretion, primary-T-cell or patient-delivery claim. |
| [Capstan RM_61461](https://patents.google.com/patent/WO2025096878A9/en) | Named mRNA/sequence-listing links, chemistry descriptions and context-specific expression observations | Delivery/molecule comparator. Exact listing and A1/A9 reconciliation remain unresolved; expression is not secretion. |
| [Addgene 135992](https://www.addgene.org/135992/) / [Ibrahim 2026](https://doi.org/10.1038/s41467-026-71395-y) | Transfer-plasmid locator, human-cell/animal experiments and public supplementary-data locators | Delivery comparator. Sequence access, BBx/BBz naming and experimental modifications require reconciliation; plasmid and packaged vector are distinct. |
| [Wang 2025](https://doi.org/10.1016/j.xcrm.2025.102250) | CAR-opt-3 article, coding-domain supplement and expression/function observations | Circular-RNA comparator. Selected variant, mature circle, junction and material correspondence remain unresolved. |
| [Di Blasi 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10275982/) / [Frei 2020](https://doi.org/10.1038/s41467-020-18392-x) | Historical resource/burden leads; Di Blasi source archive contains actual GenBank files and measurements | Reserves only. Historical source identities were rechecked, but no fresh full candidate assessment or matched therapeutic model is claimed. |

## Observation and context boundaries

Roybal's Figures 2 and S2 and secretion methods describe cytokine output in
primary human cells. The resource table distinguishes receptor/backbone deposits
from study-specific payload constructs. An empty response backbone is not an
identified cytokine-producing experimental material. The author-hosted paper
was retained in an external review cache (byte identity in the source inventory);
the copyrighted PDF is not redistributed here. Its antigen-contact and
transcriptional context must be preserved. The reviewed observations do not
discharge cue-withdrawal-to-background or shutdown deadlines for our profile.
[Author paper](https://ucsf-cmp.github.io/lim-lab/papers/pdfs/ktr_2016_2.pdf)

A bounded follow-up retrieved the indexed [supplement attachment](https://pmc.ncbi.nlm.nih.gov/articles/instance/5072533/bin/NIHMS820006-supplement-1.docx)
as a browser-challenge HTML response, not DOCX. The contents and relationship to
the referenced Table S1 remain uninspected; its advertised presence is not a
validated source freeze. No challenge was solved.

Allen's human-cell experiments and mouse experiments must retain different
recipient-organism labels. The supplement's human IL-2 assay uses intracellular
staining after secretion blockade; its ELISA description concerns mouse T cells.
Tables S1/S2 supply construct-element inventories and mixed protein/regulatory-DNA
sequences, not independently reconciled full nucleotide plasmid records.
Its author-hosted main paper is marked corrected
13 January 2023; the correction and supplemental sequence-to-material relationship
must be resolved before any reference freeze. We do not use its reporter,
proliferation or tumor endpoints as per-cell secretion rates.
[Author paper](https://allen-lab.org/static/pdf/2022_allen_science.pdf),
[supplement](https://hershbhargava.com/static/pdf/2022_Allen_Science_supplement.pdf)

Zhang supplies patient-context evidence for a different intervention: transferred,
previously engineered cells. Its reported systemic cytokine/toxicity observations
are relevant to prohibited-outcome evaluation, not evidence that induction alone
guarantees control. No patient-level records or inferred patient parameters are
retained in this audit. [Primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC4433819/)

The following are compiler obligations inferred from the source/profile comparison:

- Accumulated supernatant concentration, relative fluorescence, population
  expression frequency and per-cell secretion rate are different observations.
  Do not convert between them without a justified observation model, units,
  cell-number/time information and uncertainty. Sparse samples do not justify
  the software fixture's piecewise-constant interpolation.
- Human cell-line, donor-derived primary-cell, human-cell xenograft, nonhuman
  primate and human-patient contexts are separate. Human cells in a mouse do not
  constitute human in-vivo delivery evidence.
- Basal/induced endpoints alone do not establish activation, persistence,
  withdrawal recovery, input-access-loss or external-shutdown coverage.
- A healthy-context label or external shutdown observation is not a cell-accessible
  signal or implemented actuator. Source-required and prohibited behavior remain
  conjunctive, including conflicts.
- Published fits, digitized plots, measured observations and assumptions must
  remain distinct. No new numerical bounds, calibration fit, digitization or
  independent evaluation partition was created in this audit.

## Reuse of the historical Equalizer audit

The previous CellWeave decision addressed a reporter prototype. Its namespace and
completion statement are historical and do not establish current M11 completion.
Its complete frozen local bundle was freshly checked with the existing verifier:
**PASS_STATIC_EVIDENCE_AUDIT**, Python 3.12.14 / openpyxl 3.1.5,
macOS 26.2 arm64, `2026-09-30T01:23:15.148113+00:00` (September 29 locally).
The retained report and historical lock are separately pinned in this package.

Six selected/reserve deposited sequences were checked between GenBank and FASTA;
the original lock contains twenty deposited records. The selected Figure 4 tables
contain 9 and 48 processed summary rows. These are not 57 independent validation
cases. Core constructs, separate reporter material and onboard-reporter variants
remain distinct. Same-database format agreement is not independent experimental
sequence validation.

The [v1.0.0 release](https://doi.org/10.5281/zenodo.4741005) is locked by DOI,
archive SHA-256 and member hashes. Its deterministic models depend on MATLAB /
SimBiology; they were not executed. A plotting input is missing from the frozen
release, and the separate stochastic SBML was only structurally inspected.
Feature-to-model correspondence, independent evaluation and complete experimental
material review remain open. Fresh web availability checks are distinct from
fresh remote-byte verification; the latter was not completed.

The archive includes GPL-3.0 text while Zenodo metadata labels it CC BY 4.0.
Both observations remain recorded; no license precedence is inferred and no
research code or model is integrated. Source article licensing and sequence
repository terms are separate. The small original metadata, historical lock
and fresh verification receipt retained here support the audit trail; **they
are not the complete source/data/model bundle and cannot reconstruct it offline**.

## Delivery-lead reassessment

Capstan A9 paragraphs [0002], [00564], [00471], [00408] and [0089] identify the
listing, construct/formulation relationships and chemistry/heterogeneity issues.
The listing bytes and correction scope remain unvalidated. Figure 3B's
CD5-targeted donor-cell measurements must not be joined to later CD8-targeted
experiments by analogy. Human-PBMC mice and NHP observations retain their species.
[A9](https://patents.google.com/patent/WO2025096878A9/en),
[A1](https://patents.google.com/patent/WO2025096878A1/en)

Ibrahim's Methods names Addgene 135992 as BBx while the deposit names BBz.
The article advertises Source Data, supplementary sequence/plasmid information
and BioImage Archive S-BIAD2901. Those are retrieval leads, not validated complete
material records. The Source Data click failed during review; Addgene's sequence
policy was not accepted. The publisher page states CC BY-NC-ND 4.0.
[Article](https://www.nature.com/articles/s41467-026-71395-y),
[deposit](https://www.addgene.org/135992/),
[data record](https://www.ebi.ac.uk/biostudies/bioimages/studies/S-BIAD2901)

Wang's selected opt-3 identity and mature circular junction remain unresolved.
Primary-cell electroporation and mouse LNP experiments cannot be merged into one
delivery claim. Table S1, the GSE268105 transcriptomic accession and the article's
data/reagent-request terms are distinct evidence routes. Its CC BY-NC notice does
not resolve all downstream reuse questions. No matched executable predictive
model was established in this review. [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12432353/)

## Claim-blocking gaps and next work

| Gap | Claim blocked | Evidence required next |
| --- | --- | --- |
| G1: complete material | Exact complete-molecule reproduction, M11.2 | Versioned full records, required regions, topology/chemistry and independent boundary review; distinguish template, mature molecule and preparation. |
| G2: correspondence | Sequence-linked empirical behavior, M11.3–M11.4 | Exact construct/variant ↔ experimental material ↔ measurement mapping; retain unresolved joins. |
| G3: observation | M10 quantitative secretion acceptance, M11.3/M12 | Matching units/readout, time sampling, uncertainty and a justified observation map. |
| G4: temporal/prohibited coverage | Reversible behavior and control claims, M11.5/M12 | Activation/inactivity/recovery and applicable input-loss/shutdown/healthy-context evidence. |
| G5: deployment/applicability | Human in-vivo profile admission | Supported recipient subtype/state, population, exposure, modality, delivery, destination and unintended recipients. |
| G6: model/evaluation | Independent predictive biological checking, M11.5/M12 | Matched equations/code, parameter provenance and an independently justified evaluation partition. |
| G7: access/reuse | Reviewed source freeze, M11.6 | Obtain permitted source bytes and version/terms records; retrieval failure is not evidence of nonexistence. |
| G8: uncertainty | Robust population-level claims | Donor/cell-state/measurement variability applicable to each claimed scope. |

The next bounded curation task is to resolve the exact experimental-material
records and quantitative observation availability for the two prioritized
secretion leads, including Allen's correction. Reassess whether a candidate can
support the declared modality and deployment before starting M11.2 reference
reconciliation. If the evidence only supports a different profile, record that
as a proposed profile revision rather than silently changing M10. Equalizer
curation can inform a separately scoped model benchmark, but cannot discharge
the therapeutic gaps above. No author contact or terms acceptance is implied.

## Verification and review scope

Run `python tools/check_human_benchmark_audit.py` from the repository root.
It checks the retained byte inventory, JSON relationships and explicit deferral
flags offline. It does not fetch sources, rerun the external Equalizer audit,
execute a model, validate scientific conclusions or establish signed authority.
Changing both content and its lock requires new review; hashes alone cannot
prevent coordinated replacement. Hosted CI preserves the existing compiler,
package, example and CLI gates and adds this bounded audit check.

The NCBI PMC metadata helper could not run because its installed environment
lacked `requests`; direct PMC access also encountered a browser challenge and
the attempted Europe PMC full-text route returned HTTP 500. Accessible primary
author/publisher pages were used instead. Failed lookups establish no evidence
and no claim of resource nonexistence. No native build, downloaded-model
execution, patient-data ingestion or biological experiment was performed.
