# Exact sequence reference benchmarks

This document defines the molecular fixtures planned in [M0 and M5–M7 of the development roadmap](roadmap.md). It records the research and implementation state as of 2026-09-29. The [offline reference set](../data/references/fap_car/curation.md) now contains separately extracted nucleotide/protein records and immutable manifests; molecular emission and full-payload compilation remain unimplemented.

## What the first benchmark establishes

A reference build selects a particular implementation and reproduces its disclosed sequence. The immediate scope is **coding DNA and coding RNA**, not a complete delivered medicine. Keep three claims separate:

| Claim | Required evidence |
| --- | --- |
| Exact artifact identity | Independently curated source record, declared normalization and exact equality/hash comparison |
| Structural consistency | Explicit frame/genetic-code/termination rules, translation and feature-coordinate checks |
| Therapeutic behavior | Applicable experimental evidence or a checked model with explicit assumptions and observation mappings |

The abstract synthetic test suite continues to check language and model semantics. Its success does not establish that a published CDS implements those mathematical dynamics. Conversely, an experiment-linked sequence does not prove arbitrary Behavior IR transformations correct.

## First reference: murine FAP-CAR CDS

**Reference source:** [WO2022081694A1, “In vivo targeting of fibrosis by anti-CD5-targeted FAP-CAR T mRNA-LNP”](https://patents.google.com/patent/WO2022081694A1/en), the Compositions disclosure of Murine-FAPCAR and SEQ IDs 1–3.

**Associated study:** [Rurik et al., Science (2022), “CAR T cells produced in vivo to treat cardiac injury”](https://doi.org/10.1126/science.abm0594). The paper cites PCT/US2021/054764, associated with this publication, and reports transient in-vivo FAP-directed CAR T-cell generation in a mouse cardiac-injury model.

| Record | Disclosed scope | Planned use |
| --- | --- | --- |
| SEQ ID NO:1 | Murine-FAPCAR amino-acid sequence | Independently curated protein consistency oracle |
| SEQ ID NO:2 | Murine-FAPCAR coding DNA | Exact DNA-CDS expected artifact |
| SEQ ID NO:3 | Murine-FAPCAR coding RNA | Exact RNA-CDS expected artifact |

**Current status:** DNA/RNA/protein extracted separately, raw source and normalized hashes pinned, original PDF body cross-checked, and exact correspondence/translation checks pass. A second Codex agent independently re-extracted full HTML, separately OCRed and visually reviewed PDF pages 18–20, and confirmed all three hashes. The set is accepted for software exact-CDS reference use in [manifest.json](../data/references/fap_car/manifest.json); this is not human, empirical or therapeutic validation. Use the label **patent-disclosed, study-associated CDS reference**. Do not assert that these records fully identify the manufactured RNA used in the paper. A paper association, exact construct identity and lot-level material identity are different provenance relationships.

The patent also describes other variants. Lock the named variant and each sequence ID; do not substitute an adjacent sequence or concatenate additional elements because they appear in the same patent. UTRs, cap, modifications, tail and delivered-transcript boundaries are not supplied by this CDS benchmark. The DNA and RNA spellings do not establish two independently tested therapeutic delivery modalities.

## Curation tasks and promotion gate

- [x] **REF.1** Retrieve a stable source artifact and record publication/version, exact sequence locator, retrieval date, source URL and raw-file hash. If extracting from rendered text, preserve the original text and review against the original listing or document where available.
- [x] **REF.2** Store independently reviewed expected records for DNA, RNA and protein. Record extraction tool/version, reviewer evidence and any discrepancies. Do not derive expected RNA or protein solely from the emitter output under test.
- [x] **REF.3** Define normalization narrowly: declared layout-whitespace removal and case normalization may be allowed. Preserve alphabets and source conventions. Do not silently correct OCR, ambiguity symbols, missing bases or apparent sequence errors.
- [x] **REF.4** Record canonical sequence lengths and hashes after review. Keep raw-source, normalized sequence, feature annotation and serialized file identities distinct.
- [x] **REF.5** Check DNA/RNA correspondence under explicit T↔U conversion and translation against the independently curated protein. Record the genetic code, frame and stop-symbol convention; surface any inconsistency before accepting the fixture.
- [x] **REF.6** Record artifact class, completeness and provenance relationships as structured fields. Unknown full-transcript features must remain unknown. Add domain coordinates only after sourcing or independently reviewing them.
- [x] **REF.7** Pin the records in a minimal offline reference registry. Keep runtime resolution deterministic; a changed source/reference identity must invalidate dependent accepted builds.
- [x] **REF.8** Review source attribution and redistribution terms when adding fixtures. Keep bulky source documents and generated products outside Git; track small curated reference inputs according to [data policy](../data/README.md).

**Promotion rule:** all three expected records must be reviewed and internally reconciled before becoming accepted FAP exact-CDS fixtures. If source records disagree, retain a blocked candidate and a precise diagnostic; do not choose a corrected sequence without documenting a new artifact identity.

## Proposed reference record and build contents

`cellweave.registry.references.ReferenceRecord` and `ReferenceManifest` implement the first narrow CDS-reference schema. A reference record captures:

- `reference_id`, `variant_id`, record version and schema version;
- source publication/accession, exact locator, URL, retrieval record and source hash;
- `artifact_class` such as coding DNA, coding RNA, protein, expression cassette, full transcript or transfer plasmid;
- sequence alphabet, direction, normalization policy, length and canonical sequence hash;
- linked sequence IDs, feature annotations and their independent provenance;
- completeness, unknown features, review status and unresolved discrepancies;
- evidence relationships such as study-associated, explicitly experiment-linked or exact material identity unresolved.

A build adds its frozen request, selected component/construct identities, compiler/profile versions, locked choices, source/requirement maps and independent check results. Sequence data is a reference input; expected build results must not be regenerated by the implementation being tested.

## Acceptance and regression matrix

| Test | Expected result |
| --- | --- |
| Rebuild pinned DNA-CDS / RNA-CDS | Exact equality to the respective independently frozen source record |
| Translate either accepted coding record | Agreement with source protein under declared termination conventions |
| Change one synonymous codon | Protein consistency can pass; exact nucleotide identity fails |
| Change a residue, truncate a record or shift its frame | Relevant identity/translation/structure checks fail |
| Use wrong alphabet, variant or source record | Source-linked diagnostic; no successful reference reproduction |
| Corrupt extraction or omit a source fragment | Fixture promotion blocked until source reconciliation |
| Change component order, orientation or feature boundaries | Construct-to-molecular consistency check fails |
| Modify a reference, request, model or pass version | Dependent evidence cannot be reused as fresh |
| Repeat offline in another workspace | Same canonical sequences/build identities; run-location metadata may differ |
| Request a full transcript from CDS-only data | Unsupported/incomplete full-payload result with missing features listed |
| Attach a synthetic behavioral pass to the CDS | No automatic promotion to a molecular behavior guarantee |

The first CLI/API result should state its successful scope, for example **exact CDS reference reproduced**. It should retain unknown therapeutic and full-payload obligations without preventing useful scoped sequence checks.

## Pending reference candidates

These are curation leads, not accepted fixtures. None should become expected whole-payload output merely because its title mentions in-vivo engineering.

| Candidate | What was verified | What must happen before promotion |
| --- | --- | --- |
| **Capstan full-mRNA candidate:** [WO2025096878A1](https://patents.google.com/patent/WO2025096878A1/en), [official WIPO record](https://patentscope.wipo.int/search/en/detail.jsf?_gid=202519&docId=WO2025096878) | The patent maps RM_61461 to SEQ ID NO:151 and names it in animal experiments. It identifies `23-1871-WO_SequenceListing.xml`; a Sequence Listing tab is advertised, but the attachment was not retrieved/validated. | Retrieve and inspect the exact listing, pin its version, confirm sequence/construct/experiment linkage, and check complete transcript coverage and separately described chemistry. Identity with the associated Science study's chosen construct remains a separate question. |
| **CD19-CAR transfer plasmid:** [Ibrahim et al., Nature Communications (2026)](https://www.nature.com/articles/s41467-026-71395-y), [Addgene #135992](https://www.addgene.org/135992/) | The in-vivo study explicitly names #135992. Addgene advertises a full sequence map, but raw sequence retrieval required login/terms and was not completed. Paper spelling `BBx` differs from the deposit's `BBz`. | Retrieve the sequence record, lock deposit version/hash, reconcile naming and any modifications, and distinguish complete transfer plasmid, expression cassette and packaged viral RNA. Do not equate them. |
| **Anti-HER2 circRNA coding domains:** [Wang et al., Cell Reports Medicine (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12432353/), [Table S1 workbook](https://ars.els-cdn.com/content/image/1-s2.0-S2666379125003234-mmc2.xlsx) | Inspected Sheet1 provides individual CAR coding-domain sequences totaling 1,500 bases. It does not specify the entire circRNA scaffold or clearly identify the selected `opt-3` variant. | Curate as partial component records if useful; establish exact variant linkage and complete scaffold/product boundaries before any whole-circRNA or experiment-linked artifact claim. |
| **Earlier DNA/mRNA nanocarriers:** [Smith et al. (2017)](https://www.nature.com/articles/nnano.2017.57), [Parayath et al. (2020)](https://www.nature.com/articles/s41467-020-19486-2) | In-vivo therapeutic designs and construct architectures were documented; exact therapeutic nucleotide artifacts were not verified in inspected materials. | Obtain a source-linked exact construct record. Architecture diagrams, delivery-antibody sequences and unrelated packaging plasmids do not establish therapeutic payload identity. |

Retrieval limitations are recorded as **not verified**, not as proof that a sequence is unavailable publicly. Pending references do not block the first CDS curation and compiler-development track.

## Extending to a complete payload

A future full-payload fixture must identify the actual emitted molecule or coordinated molecule set, including boundaries, relevant noncoding regions, topology and target-specific molecular features. A DNA transcription template, mature linear RNA, circular RNA, transfer plasmid and packaged vector genome require different artifact classes and conversion contracts.

Promotion also requires a supported implementation profile, complete source correspondence, fresh checks and explicit context/evidence linkage. Every added sequence choice changes the reference artifact unless the source already specifies it. Keep molecular behavior modeling and new sequence optimization as separately reviewable work in [M9](roadmap.md#m9--connect-molecular-behavior-and-expand-beyond-cds-references).
