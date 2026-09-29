# M9 evidence review and promotion boundaries

Review date: **2026-09-29**. This review records what the inspected sources can support for molecular behavior contracts and broader payload profiles. It does not curate a new accepted sequence, calibrate a biological simulator, or establish manufactured-material identity. The existing [FAP reference curation](../data/references/fap_car/curation.md) and [reference promotion rules](reference-benchmarks.md) remain authoritative for accepted sequence inputs.

## FAP behavior evidence

[Rurik et al., Science (2022), DOI 10.1126/science.abm0594](https://doi.org/10.1126/science.abm0594), Figures 1–2 and the text accompanying Figure S1/Table S1, report the following distinct observations:

| Observation | Applicable context | Contract interpretation |
| --- | --- | --- |
| FAPCAR-positive population measured by flow cytometry | Activated murine T cells exposed to CD5-targeted mRNA-LNP; 48-hour endpoint | Population expression observation, not a single-cell output guarantee |
| Expression peaks around 24 hours and declines over subsequent days | In-vitro expression time course | Transient expression evidence, not an inferred decay constant |
| Killing of FAP-expressing target cells | Cultured target-cell assay | Contextual target-response evidence, not a fixed per-contact deadline |
| FAPCAR-positive splenic T cells at 48 hours; no detected expression at one week | Injured mouse model with the reported delivery formulation | Distinct in-vivo population observations; non-detection is not an exact zero |

The [PMC manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC9983611/) provides the same study association. It does not supply a validated mapping from the compiler's Boolean contact histories, timers, memory, or pulses to molecular dynamics. No reviewed, numerical calibration dataset with a compatible executable model, parameter uncertainty, and independent validation was established in this review.

The patent's experimental methods describe a larger expression context: FAPCAR with a P2A-separated RISR-RIAD coding region, UTR elements, a reported 101-nucleotide poly(A) tail, and Cap1 chemistry. The locator is **Materials and Methods → RNA synthesis and complexing into lipid nanoparticles** in [WO2022081694A1](https://patents.google.com/patent/WO2022081694A1/en). Its separately disclosed SEQ IDs 1–3 remain the named Murine-FAPCAR CDS reference. These records were not reconciled to the entire experimental composite or to a manufactured lot. A method description and neighboring sequences are not authority to add missing sequence segments.

Consequently, the current reference can have a **source-linked, unresolved molecular behavior contract**. The contract should retain the exact reference fingerprint, study association, cellular context, observable definitions and missing obligations. It cannot acquire calibrated-model or empirical-realization status merely by attaching a study citation to an exact-CDS PASS.

## Complete-payload candidates

### Capstan linear-mRNA candidate

[WO2025096878A1](https://patents.google.com/patent/WO2025096878A1/en) maps RM_61461 to SEQ ID NO:151. A later publication, [WO2025096878A9](https://patents.google.com/patent/WO2025096878A9/en), is dated 2025-07-10. The A1/A9 correction relationship must be reviewed before choosing a locked source version.

The A9 document identifies `23-1871-WO_SequenceListing.xml`, created 2024-10-28, with a stated size of 669,450 bytes in paragraph **[0002]**. Paragraph **[00564]** maps the named construct to SEQ151; **[00471]** identifies its experimental formulation label. Paragraph **[00408]** describes full uridine substitution with N1-methylpseudouridine and Cap1 chemistry. Paragraph **[0089]** explicitly discusses heterogeneous poly(A) lengths.

The [official WIPO record](https://patentscope.wipo.int/search/en/detail.jsf?_gid=202519&docId=WO2025096878) presented an image CAPTCHA during this review. No CAPTCHA was solved or bypassed. The listing was not retrieved and validated. Google Patents body text and its linked PDF did not produce an independently reconciled exact listing through the attempted routes. This records a retrieval limitation, not a conclusion that public access is impossible.

Promotion remains pending: listing bytes, source version, exact sequence, full boundary/feature review, chemistry linkage, and independent extraction review. A nominal sequence, chemical specification, and heterogeneous manufactured preparation require separate identities. Nothing here establishes identity with a separately associated study's selected material.

### Other pending candidates

| Candidate | Verified source locator | Remaining boundary |
| --- | --- | --- |
| [Addgene #135992, pSLCAR-CD19-BBz](https://www.addgene.org/135992/) | Sequence Information advertises a complete map but requires acceptance of the Affinity Reagent Sequence Policy for further sequence information | No terms were accepted and no raw record was validated. A map image is not a frozen nucleotide record. |
| [Ibrahim et al., Nature Communications (2026)](https://www.nature.com/articles/s41467-026-71395-y) | Methods → Vector design names #135992 as `pSLCAR-CD19-BBx` | Reconcile naming and deposited version. A transfer plasmid does not itself identify the packaged viral genome or full delivery system. |
| [Wang et al., Cell Reports Medicine (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12432353/) | Results → CircRNA expression identifies `circRNA CAR-opt-3` as the selected variant; supplemental Table S1 is linked | The existing reviewed workbook provides coding-domain records. Exact selected-variant correspondence, complete mature circular sequence and its junction remain unresolved; a linear precursor is a different artifact. |

No candidate crosses the existing complete-payload promotion gate in this review. The detailed prior retrieval record remains in [reference benchmarks](reference-benchmarks.md#pending-reference-candidates).

## Consequences for M9 implementation

The following are software requirements inferred from these gaps:

1. Keep exact sequence, source association, chemical specification, biological model and experiment/material identity as distinct typed relationships. Missing evidence must be representable without inventing a substitute.
2. A biological adapter needs an explicitly scoped model, matched observations with units and sampling semantics, identifiable parameter/calibration evidence, uncertainty, and separate validation. A synthetic truth table or replay of its own expected outputs does not meet that gate.
3. Expose different profiles for coding DNA/RNA, template DNA, mature linear RNA, circular RNA and vector genomes. Validate molecule boundaries, topology, noncoding regions and chemical features according to the requested class. Unsupported profiles must explain the missing obligations.
4. Recheck dependent claims whenever sequence, layout, topology, chemistry, model, assumptions or observation mapping changes. A synonymous sequence edit can preserve translation while invalidating molecular behavior evidence.
5. Software tests may use explicitly artificial records to exercise these contracts. They do not become accepted therapeutic fixtures or biological calibration data.

M9 can deliver these enforceable boundaries while leaving calibration and full-payload promotion pending. Mark those scientific/source gates complete only when the corresponding independently reviewable evidence exists.
