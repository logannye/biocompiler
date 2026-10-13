# Controlled CAR two-RNA nominal adaptation

This batch supplies a complete **nominal design**, assembled from public source
fragments and explicit design choices. Neither publication discloses these two
complete RNAs. Their encoded products retain the exact numbered patent fragments;
their untranslated regions, termination and chemistry are an attributed
cross-source adaptation. Structural consistency remains separate from whether
the adapted molecules express, localize or implement the controller in cells.

The intended product target remains human immune cells engineered in vivo.
The earlier source experiments used engineered human T cells and a different
expression modality. They do not establish delivery, co-expression, kinetics,
safety or therapeutic activity of this two-RNA design.

## Frozen design

Each linear RNA contains, in order:

1. The complete 79-base mHBB 5′ UTR, SEQ11 of WO2025096878A9.
2. The exact #197 or #206 coding fragment reconstructed from WO2014127261A1.
3. One explicitly designer-supplied UAA stop codon.
4. The complete 126-base PNLIP-RPS3A 3′ UTR, SEQ34 of WO2025096878A9.
5. The 110-base encoded poly(A) suffix of that publication's SEQ151.

No coding base, tag or linker is changed, removed or optimized. The 5′ UTR
already ends with the source initiation-context bases and begins with AG; no
additional initiation or cap-compatible bases are inserted. Joining that UTR to
each different coding fragment is a design choice, not evidence of equivalent
translation efficiency. The source records' component origins are preserved;
they do not change the human recipient target.

The controlled `ordinary_cds` path currently accepts one terminal stop. The new
design therefore selects one UAA explicitly. It does not copy RM_61461's double
UGA/UAA termination or claim that the older patent supplies a terminal stop for
#197 or #206. This choice preserves the exact encoded amino-acid sequences.

| Member | Complete RNA | Source coding fragment | Nominal full translation |
| --- | ---: | ---: | ---: |
| #197 | 1,830 nt | 1,512 nt | 504 aa |
| #206 | 2,097 nt | 1,779 nt | 593 aa |

Coordinates below are zero-based and end-exclusive. The separately identified
stop is included when declaring the complete coding region.

| Region | #197 | #206 |
| --- | --- | --- |
| 5′ UTR | `[0,79)` | `[0,79)` |
| Coding fragment excluding stop | `[79,1591)` | `[79,1858)` |
| Designer-supplied stop | `[1591,1594)` | `[1858,1861)` |
| 3′ UTR | `[1594,1720)` | `[1861,1987)` |
| Encoded poly(A) | `[1720,1830)` | `[1987,2097)` |

The terminal A run is 111 bases because the complete 3′ UTR itself ends in A.
The tail remains 110 bases; shortening the UTR to relabel that boundary would
change the source mapping.

## Public authority and adaptation boundaries

The [controlled source acquisition record](car-controlled-reference-acquisition.md)
identifies the original
[WO2014127261A1](https://patents.google.com/patent/WO2014127261A1/en)
and separately printed
[US20150368342A1](https://patents.google.com/patent/US20150368342A1/en)
sequence listing. The fixed #197 order is
`1, 3, 5, 7, 197-short-linker, 23, 19, 11`;
the fixed #206 order is
`27, 29, 206-short-linker, 23, 31, 33, 15, 17, 19, 21`.
The identifiers are source block identities, not CDS or RNA member numbers.

The source figure locators are Figure 8A/B, PDF pages 90/91, for #197 and
Figure 9A/B/C, PDF pages 92–94, for #206. Numbered DNA records have separate
printed-listing entries on US PDF pages 93–102. The two short linkers are
explicit unnumbered figure material. Both the Myc tag and the mCherry fusion
remain in the full products. Expected product identity refers to the entire
nominal translation, including source signal sequences; it does not assert a
mature processed protein identity or measured processing outcome.

The [RM_61461 qualification](car-rm61461-qualification.md) records the current
[WO2025096878A9 publication](https://patents.google.com/patent/WO2025096878A9/en)
and its [official WIPO listing archive](https://www.wipo.int/published_pct_sequences/publication/2025/0508/WO25_096878/WO2025-096878-TAB-20241115-001.zip).
Figure 3C, PDF page 319, joins RM_61461 to SEQ151 and its named regions;
Figures 8B/8C, PDF pages 348/350, identify the complete UTRs. Fresh independent
substring comparisons against the original XML confirm:

| Copied region | Exact authority |
| --- | --- |
| Entire 5′ UTR | SEQ11 equals SEQ151 `[0,79)` |
| Entire 3′ UTR | SEQ34 equals SEQ151 `[1540,1666)` |
| Encoded tail | SEQ151 `[1666,1776)`, exactly 110 A bases |

ST.26 records RNA uracil using `t`; the existing qualified interpretation
uppercases the literal sequence and replaces T with U for canonical RNA display.
The source-controlled DNA fragments undergo an explicitly declared T-to-U
conversion when represented as RNA. Neither alphabet conversion proves chemical
modification or expression.

Nominal chemistry is **designer adopted** for these new transcripts:

- Cap1 with the Cap-AG structure described in A9 paragraph [00408]. The cap's
  inverted guanosine is a chemical feature, not an added transcript character.
- Replacement of every U with N1-methylpseudouridine, adopting the same source
  paragraph's nominal chemistry; canonical RNA sequence strings retain U.
- A 2′-O-methyladenosine declaration at transcript position zero, representing
  the cap-adjacent A already present in the source prefix.
- A designer-supplied 3′ hydroxyl. The source qualification does not establish
  the historical physical material's 3′ terminal chemistry.
- An explicit complete modification inventory with no further modifications
  and the represented exact 110-A tail.

The source chemistry is attributed through the existing pinned factual pack;
this batch does not claim a new PDF chemistry review. No batch identity,
capping fraction, physical tail distribution, purity or potency is supplied.

## Independent expected identities

The [expected metadata](../data/car_controlled_reference/rna-adaptation-expected.json)
contains the complete original input pins, whole-RNA and product hashes,
per-region hashes, source-domain placements and canonical product fingerprints.
It contains no sequence-bearing transcript or protein records.

| Object | SHA-256 of canonical sequence characters |
| --- | --- |
| #197 RNA | `b222d0b58b6de3349f1afe3c70e7d82f2099e5865d3e753b4aa02ff6ee9d0953` |
| #206 RNA | `dcb106b01b02357b0604349b8a0f81f8ce35f14ba19d0e1ac90c58ea1a5bfc7b` |
| #197 full protein | `15c4999ca0be97c3bdf1180bdf1bd3d43a3d812f08b25651e17b840fc6e29513` |
| #206 full protein | `86d60b35c58fa5562df9fd780a5d9914eec45510febc67e54cece2a040b7f472` |

The product fingerprint additionally hashes the existing
`biocompiler.policy_mrna_product_content.v0.1` object containing `alphabet`,
`schema_version`, `sequence_extent` and `sequence`, encoded as UTF-8 JSON with
sorted keys, compact separators and no newline. These fingerprints differ
from a hash of the sequence characters alone.

Independent arithmetic read the complete pinned XML and all four retained
controlled-source inputs. It reconstructed coding DNA from the separate
printed-listing transcription, compared every numbered entry with the figure
transcription, preserved the two unnumbered figure linkers, and compared
standard-code translation with the separately entered figure proteins.
It then applied the frozen layout and compared original XML region identities.
It imported no producer, compiler, product implementation or cached PASS.

Fresh replay used the preinstalled macOS aarch64 CPython 3.11.15 interpreter and
checked all five original input pins, 16 domains, two products, two complete
RNA identities, ten region hashes, eighteen domain placements and two canonical
product fingerprints. This is focused arithmetic evidence, not the complete
repository test suite or native acceptance. An initial read using Homebrew
CPython 3.14.6 encountered an installed XML dynamic-library mismatch; no package
installation, native rebuild or repair was performed. Required full and native
acceptance remain separate hosted validation work.

Separate arithmetic is not independent-person review of the source images.
Both manual transcriptions were acquired by the same operator, and source
reading remains a trusted acquisition step. Fresh byte equality establishes
consistency with the recorded originals, not source authenticity or correctness
of the manual visual interpretation. Public access does not establish permission
for redistribution, manufacture or use; those statuses remain as recorded.

## Controller and evidence boundaries

The member pairing, same-recipient co-delivery, availability, controller exposure,
observation mapping and temporal behavior require explicit contracts. Neither
the preserved sequences nor the UTR source supplies those guarantees. The
controlled patent pair is not established as exactly identical to the separately
published Wu 2015 I.b/II.d pair. Mechanism descriptions from that paper therefore
cannot silently supply pair-specific AP21967 efficacy or withdrawal timing.

A successful source/design check can establish the exact bases, nominal product
translation and declared chemical/layout consistency. It does not establish
cellular expression, receptor localization, signal processing, drug sensitivity,
withdrawal response, target killing, in-vivo delivery or clinical benefit. The
new RNA adaptation has no direct experimental evidence in this batch. Controller
model assumptions and public-source observations must remain separately named
and bound to their actual construct, context and readout.
