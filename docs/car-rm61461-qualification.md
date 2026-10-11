# RM_61461 public-reference qualification

Reviewed 2026-10-11. RM_61461 is suitable for a **scoped nominal-reference
handoff**: its complete published RNA sequence, constituent boundaries and
encoded protein can be identified without designing or filling a missing
sequence. This does not qualify manufactured material, establish human in-vivo
performance, grant human-use admission or complete the CAR MVP.

The product target remains human immune cells engineered in vivo. This reference
is an anti-CD19 CAR disclosed in human-cell research; selecting it as a software
reference does not select the product's antigen or clinical indication. Its
mouse-origin UTR remains an exact reference component, not a non-human product
target or permission to alter the published sequence.

## Pinned source and correction boundary

The authority is the current [WO2025096878A9 publication PDF](https://patentimages.storage.googleapis.com/aa/28/2d/e21333e54fee5a/WO2025096878A9.pdf)
and the [official WIPO sequence-listing ZIP](https://www.wipo.int/published_pct_sequences/publication/2025/0508/WO25_096878/WO2025-096878-TAB-20241115-001.zip).
The [indexed publication](https://patents.google.com/patent/WO2025096878A9/en)
provides searchable paragraph references; the PDF figures were also visually
inspected. Retrieval required no authentication or terms-acceptance action.

| Retained object | Bytes | SHA-256 |
| --- | ---: | --- |
| A9 PDF | 17,210,052 | `e95bc99f5cc4f9c69d4ca4a40590fb437b17980b93f5a2f7a18e794ca5b9b2da` |
| Official listing ZIP | 50,876 | `9ea75052596054c5301fd000ea39a60cbb3b024499c0213c075428bafc417092` |
| `23-1871-WO_SequenceListing.xml` | 669,450 | `7df4fd171f285adc6e5d0b37442a8bc77ab1b28c275b04a52c822ed15e7b938e` |

Files and retrieval records are retained under
`generated/car-reference-qualification-20261011/`. A9 paragraph [0002], on
PDF page 2, names this listing, its creation date (2024-10-28), and its exact
byte count. The XML contains 401 sequence entries.

The initial qualification pinned current A9 bytes without establishing the
correction's scope. A subsequent public WIPO inspection, after the user completed
its browser verification, retrieved the correction request, authorizing decision,
rectified sheets and official A9 PDF. The [WIPO Documents and Notices tabs](https://patentscope.wipo.int/search/en/detail.jsf?docId=WO2025096878)
identify the A9 publication on 2025-07-10 and its authorized description correction.

The four-page request lists five corrections: the citation in [00116], list
punctuation in [00162], conjugation terminology in [00219], the Table 17 heavy-chain
label, and the RM_61356/RM_61358 identifiers in [00568]. The one-page ISA/217 decision
of 2025-06-17 authorizes the changes as requested. The request's page 3 and rectified
sheet 5 both retain **RM_61461 as SEQ151**. This is evidence about the inspected
correction record, not a complete A1-versus-A9 comparison or a biological finding.

| Additional WIPO object | Bytes | SHA-256 |
| --- | ---: | --- |
| Correction request, 4 pages | 151,385 | `8e9741f55c09df5424da5343057762b2c9229701b47654fcf00e7647ded1c99b` |
| ISA/217 decision, 1 page | 36,351 | `ca5be841472d360f85aeca74f4806247bcfddd0cbe4f6b06bc0112c21503c9bd` |
| Rectified sheets, 5 pages | 252,264 | `36cb12afda5d804359f3401dd731bb30140213baa9b9504762c52a49af237675` |
| Official WIPO A9 PDF, 402 pages | 17,086,237 | `48ea8261883b444f2892bb84c05a13580600ae62ab830c41b9531312610aa8b1` |

The official PDF differs in file bytes from the earlier mirror. Its cover and
listing identity page were separately visually inspected; pages 312, 319, 348
and 350 have identical rendered pixels under the recorded comparison. No
whole-document byte or pixel equality is claimed. The retrieval URLs and scope
are retained in `wipo-correction-retrieval-20261011.json` and
`wipo-a9-selected-page-comparison.json` in the generated evidence directory.
The immutable packaged reference is the earlier scoped snapshot; this addendum
does not silently change its original source hashes or grant new acceptance.

## Independent sequence identity and boundaries

Figure 3C, drawing 9/85 (PDF page 319), maps SEQ151 to RM_61461, mHBB,
CAR2-OPT4 and PNLIP-RPS3A. Figure 2A, drawing 2/85 (PDF page 312), identifies
CAR2 as SEQ2, with 485 amino acids including its signal peptide. Figures 8B/8C,
drawings 38/85 and 40/85 (PDF pages 348/350), identify the entire UTR records.

The following are independently computed exact substring comparisons against
existing XML entries. Coordinates are zero-based, end-exclusive; no sequence
was optimized or synthesized.

| Region in SEQ151 | Coordinates | Length | Exact existing reference |
| --- | --- | ---: | --- |
| Entire 5′ UTR, mHBB | `[0,79)` | 79 nt | SEQ11 |
| Protein-coding ORF, excluding stops | `[79,1534)` | 1,455 nt | SEQ101, CAR2-OPT4 |
| Two consecutive stop codons | `[1534,1540)` | 6 nt | ORF plus both stops exactly equals SEQ65 at `[79,1540)` |
| Entire 3′ UTR, PNLIP-RPS3A | `[1540,1666)` | 126 nt | SEQ34 |
| Encoded poly(A) region | `[1666,1776)` | 110 nt | Remaining suffix of SEQ151, all A |

The maximal terminal A run is **111**, because SEQ34 itself ends in A. It must
not be relabeled as a 111-base tail by shortening the published UTR. Ordinary
standard-code translation of the existing ORF produces exactly SEQ2 (485 aa),
not SEQ4. The first stop begins at 1534 and the second at 1537. These checks
establish sequence correspondence, not translation efficiency or protein
processing in cells.

SEQ151 is typed RNA in ST.26, although its literal nucleotide text uses `t`.
[WIPO's explanation of ST.26](https://www.wipo.int/en/web/pct-system/w/news/2022/news_0039)
explicitly specifies that RNA uracil is represented by `t`. A declared
alphabet conversion to uppercase RNA spelling is therefore required; it is
not DNA-to-RNA design or proof of chemical modification.

| Independently computed identity | SHA-256 |
| --- | --- |
| SEQ151, uppercase literal ST.26 spelling | `3fe2f6e607338999db7c22e538e043bd25dbc7fe7a7ffdc834ac48097f3f8ac3` |
| SEQ151, uppercase RNA spelling | `7a0e872d51987d1c0064accb5197e605943d90ea2c20104d86e9f41f12617335` |
| SEQ101, uppercase RNA spelling | `7fd04e1c7ccb7623c9f152608f600d5684cbdace8b1fc8c6f8a35efb43402cc8` |
| SEQ2, uppercase amino-acid spelling | `833bd17e675e9595d01865a0109c9c795d2ba8b78481ab06f12da043019e404d` |

The retained independent arithmetic receipt is
`generated/car-reference-qualification-20261011/rm61461-independent-sequence-review.json`,
SHA-256 `9e98c7865dc81812b7840396379fd831b2fe3a7946f6bb2c921e64bad79ce375`.
It checks all five regions, both stops and the complete protein identity.

## Chemistry and evidence join

Paragraph [00408] specifies full uridine replacement by N1-methylpseudouridine
and co-transcriptional Cap1 using Cap-AG,
`m7G(5′)ppp(5′)(2′OMeA)pG`. These are source-declared nominal chemistry
attributes; the XML has only a source feature for SEQ151. Neither its alphabet
nor a successful translation check supplies those attributes.

The listed transcript already begins with **AG**; its first ten RNA-spelled
bases exactly match the cap-compatible prefix described in [00402]. Thus the
Cap-AG description is compatible with the listed first two transcript bases,
without prepending an invented AG initiator. The cap's inverted methylated
guanosine is a separately declared chemical structure, not an extra base to
silently insert into the 1,776-base transcript string. This is a nominal
sequence/chemistry compatibility check, not evidence of a particular batch's
capping efficiency.

Examples 1/2 disclose expression in expanded and freshly activated primary
human T cells; Figure 5H explicitly includes RM_61461. Example 3 and Figure 10
join the same construct to a Nalm6 coculture readout. Figure 10 reports
348.3 CAR molecules-equivalent/cell (SE 5.03), 2.9 relative expression, and
12% residual Nalm6 signal/cells as labeled. These remain patent-disclosed
measurements in their stated ex-vivo context, not an independently verified
efficacy claim. The separate animal studies do not establish human in-vivo
delivery or therapeutic benefit.

There is a source conflict: paragraphs [00414] and [00451] name **donor 3** for
Example 3, whereas Figure 6's description [0030] names **donor 4**. Preserve
both citations and mark that assay's donor identity unresolved. Do not silently
merge it with the separate, consistently labeled expression experiments.

## Qualified dimensions and unresolved premises

| Dimension | Disposition for a reference handoff |
| --- | --- |
| Complete nominal sequence and region identity | Established by the exact XML comparisons above and the current A9 construct table. |
| Nominal coding identity | Established against the existing complete CAR2 protein record. |
| Nominal cap and nucleotide replacement | Explicitly attributed to the source's synthesis description; not measured in this review. |
| Human T-cell expression relevance | Source-disclosed ex-vivo evidence with construct and cell-state context retained. |
| Functional readout | Source-disclosed; retain the donor conflict and measured endpoint definition. |
| Actual material and chemistry | Unassessed: no batch identity, capping fraction, tail distribution, independent quality data or explicit 3′ terminal chemistry was qualified. |
| Raw assay reproducibility | Unassessed: figure/table values are available, but raw instrument files, analysis pipeline and independent replication were not qualified. |
| Human in-vivo applicability, delivery and safety | Unassessed; these are still product obligations. |
| Redistribution and permitted use | Public source access is established. No affirmative sequence/content reuse license, material-transfer permission or patent-use permission was identified or accepted in this review. No legal conclusion is made. |
| Historical correction scope | The retrieved request and authorization identify five description corrections; RM_61461 remains SEQ151 in the inspected records. Full A1/A9 equivalence remains unassessed. |

The appropriate next compiler input is a versioned, source-attributed **nominal
reference** carrying these separate statuses. A checker may verify the supplied
sequence, translation and explicit nominal chemistry. There are two distinct
ways to represent the unreported end identity:

- A source-only record leaves 3′ terminal chemistry unknown and cannot claim
  that the publication specifies it completely.
- A complete nominal design may explicitly supply a 3′ hydroxyl as a
  **designer-supplied choice**, with separate provenance from the copied
  sequence and source-declared cap/modifications. That would reproduce the
  listed bases and encoded product under the supplied chemistry specification;
  it would not establish exact reproduction of the historical physical
  material or source-verified 3′ chemistry.

The checker must distinguish these authorities and reject missing required
fields instead of silently inserting defaults. A positive structural result
must not upgrade the evidence table, resolve the donor conflict, or manufacture
a license or clinical claim. An initial distribution can retain source URLs,
retrieval instructions and content hashes instead of bundling the entire PDF;
that distribution choice makes no claim about permission to reuse other
content or manufacture a product.

This review performed public-source reading, selected PDF rendering and pure
sequence comparisons only. It produced no new molecular sequence, experimental
protocol, compiler input packet, native execution or clinical recommendation.
