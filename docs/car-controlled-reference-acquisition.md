# Controlled CAR reference acquisition

Status: partial RC2 acquisition, 2026-10-12. The selected acquisition path is
`WO2014127261A1-197-206`. Its primary pairing is verified; a bounded manual
material reconstruction passes the checks below. Its admission does not require
identity with Wu I.b + II.d. This is a provenance inventory, not an admitted
molecular pack or a completed RNA design. It supports the
[controlled-composition roadmap](car-composition-reversible-control-roadmap-2026-10-12.md).
The machine-readable record is
[`source-inventory.json`](../data/car_controlled_reference/source-inventory.json).

The subsequent [reference-pack batch](controlled-car-reference-pack.md) now
prepares a separately named, complete nominal two-RNA adaptation and conditional
controller/readout contract. This does not change what the original publications
supplied, establish the adaptation experimentally, or complete native admission.

Only metadata and this assessment are source files. Downloaded originals,
retrieval failures and inspection derivatives remain under the ignored
`generated/car-controlled-composition/reference-acquisition/` directory. Every
retained response has a byte count and SHA-256 in the retrieval record. The
entire acquisition directory is limited to 25 MiB; no source PDF or molecular
sequence is bundled as package data by this checkpoint.

## Verified source records

The [Wu publication](https://pmc.ncbi.nlm.nih.gov/articles/PMC4721629/) identifies
I.b + II.d as its selected pair. Figure 2 shows two membrane-associated products
and the AP21967-dependent FKBP/FRB* interaction. Figures 3 and 4 concern
lentivirally engineered human T cells. The on/off/on killing experiment uses
36-hour stages; its endpoint is not a measured rapid receptor-shutdown bound.
Figure 2 includes different activation readouts, so an ideal zero-background
Boolean truth table is not automatically a measured contract. The original
context is preclinical, not human in-vivo two-mRNA delivery.

The [author-hosted version](https://limlab.ucsf.edu/pdfs/cyw2015_2.pdf) is retained
as an 11-page PDF, SHA-256
`f5b970fbc6b6174589535a2aeabf839160b04057d5f93f28e2e3b58f205cf259`.
Its final page discloses the related patent application WO2014127261. Figure 2
was visually inspected on PDF page 4 (printed article page aab4077-3).

The [cited patent record](https://patents.google.com/patent/WO2014127261A1/en) and
its linked 142-page original PDF were retrieved. The PDF SHA-256 is
`324d9d765144de730d1fa898abf57b4b516260ed0e2d8d82eedab4f541e2e397`.
Visual inspection confirms sequence-bearing figures and a tested pair:

| Patent identity | Original PDF location | What is established |
| --- | --- | --- |
| Construct #197 | PDF pages 90-91; drawing sheets 15/64-16/64; Figures 8A-B | Labeled domain nucleotide/protein records, including linkers and an epitope tag. |
| Construct #206 | PDF pages 92-94; drawing sheets 17/64-19/64; Figures 9A-C | Labeled domain nucleotide/protein records, including linkers and mCherry. |
| Pair #197 + #206 | PDF page 107; drawing sheet 32/64; Figure 18B | The record pairs these constructs and reports control behavior. |
| Referenced sequence listing | Description paragraph [0003] | Names `UCSF-464WO SeqList_ST25.txt`, dated 2014-02-13, reported as 153 KB; original text file not acquired. |

The related [US20150368342A1 publication](https://patents.google.com/patent/US20150368342A1/en)
supplies a 157-page PDF, SHA-256
`87565b78e73ad5778d6efabc1783e69daa53e25682f615f9b162954f78d96bb5`,
including a printed listing of 145 SEQ IDs beginning at PDF page 93. Listing
pages 93-103 were visually inspected. This improves sequence authority
availability; it is not acquisition of the original ST25 text file.

## Separately named patent-pair route

The selected identity is `WO2014127261A1-197-206`, preserving that source and
those construct numbers. Figures 8 and 9 contain domain DNA and protein blocks,
not complete plasmid/vector records. Their source order is indexed by SEQ IDs
in the inventory. #197 includes Myc; #206 includes mCherry. Both include a
short, unnumbered Ser-Leu linker after CD8, with distinct DNA encodings. The
terminal domain blocks do not supply a stop codon. Figure 15 reports
drug-dependent cytotoxicity for this pair in engineered primary human CD8 T
cells; it does not supply a verified withdrawal/readdition bound for this pair.

The manual reconstruction below preserves the explicitly shown order and
junctions. Its checks use separate printed DNA and protein records; they do
not promote the PDF's noisy OCR text into sequence authority.

This pair was selected without claiming identity with Wu I.b/II.d. Conversely,
using the Wu name or importing Wu's assay-specific timing evidence still needs
that join. Compatible architectures cannot establish identical bases, tags,
junctions or assay variants. No exact paper/patent identity is claimed here.

## Bounded local material reconstruction

Two manual entries were made: domain DNA/protein blocks from WO Figures 8-9,
and the 14 numbered DNA records from the US printed listing. The two unnumbered
linkers retain their explicit figure records. Only whitespace removal and
uppercase normalization were applied. The checker verifies original PDF sizes
and hashes, exact record census, numbered DNA agreement, printed lengths,
translation against separately entered protein text, and the exact block order.
It reconstructs both products without adding bases at boundaries:

| Literal figure reconstruction | Coding fragment | Protein | Stop codon |
| --- | ---: | ---: | --- |
| #197 | 1,512 nt | 504 aa | Not supplied |
| #206 | 1,779 nt | 593 aa | Not supplied |

All 16 component translations and both full concatenation translations pass.
Four in-memory controls reject a synonymous DNA substitution, omitted junction,
unshown stop codon and changed protein authority. The synonymous change is
rejected by the separate listing comparison even though translation is unchanged.
Three initial manual-entry errors were corrected by rereading the original
figures/listing; `transcription-corrections.json` records the source locations.
No unresolved figure/listing base conflict was found in this bounded comparison.

This is **same-operator double entry**, not independent-person review. Visual
source reading remains a trusted acquisition step: agreement, length and
translation checks cannot prove that the operator read every source pixel
correctly. The results establish consistency of this literal reconstruction;
they do not establish an original deposited plasmid, a complete RNA design,
distribution permission or biological behavior.

The ignored acquisition directory contains:

- `patent-domain-transcription.json` and `patent-listing-transcription.json`:
  separate literal entries with source/page/SEQ ID locations.
- `check_patent_transcription.py`: bounded, offline, standard-library checks.
- `patent-transcription-check.json`: source/input/checker pins, component/product
  hashes, half-open nucleotide spans for every join and control results.
- `patent-pair-coding-fragments.fasta` and `patent-pair-products.fasta`: ordered
  #197/#206 reconstructions. The former deliberately lacks termination and is
  not a therapeutic RNA export.

Exact hashes for these local artifacts are in the source inventory. The tracked
offline importer now replays the four original input files using ordinary Python
on macOS/Linux; no package install, network access or native execution is involved.
Point it at the retained authorized-input directory. Keep output in an owned
checkout and use a fresh path:

```text
mkdir -p generated/public-reference-readiness
python3 -B tools/import_controlled_car_reference.py \
  --inputs /absolute/path/to/retained/reference-acquisition \
  --output generated/public-reference-readiness/fragment-import.json
```

The output is an inert metadata receipt with component/product hashes and exact
spans, not a sequence export or an admitted molecular pack. The historical
ignored checker and receipt remain acquisition evidence, not this tool's
acceptance authority. The [first batch record](public-reference-first-batch.md)
records fresh replay and local validation.

## Authorized-input import contract

Keep sequence-bearing assets as explicitly supplied local inputs while
redistribution remains unassessed. An importer must accept the two raw pinned
PDFs and both entered record files, check their pinned bytes before parsing,
reject symlink inputs/path escape or extra/unbounded requested authority, and
replay the material checks rather than accept a saved PASS. Require exactly the recorded domains,
tags, two distinct unnumbered linkers and fixed construct order. Record the
literal/manual acquisition status, checks and explicit user input authority in
the imported pack. Do not fetch, replace bases, strip tags, optimize codons,
insert a stop or infer transcript context during import.

The finite cap is 25 MiB for all acquisition inputs and derivatives. The
original PDFs and transcription hashes in the inventory provide the expected
authority. Product hashes in the receipt are derived checks, not substitutes
for those original inputs. RNA-design input is a different required authority;
an incomplete RNA manifest must fail admission even when material checks pass.
The tracked tool accepts only the four fixed file names, opens them relative to
the supplied directory, and verifies their sizes and hashes against the tracked
inventory before parsing either transcription. Other retained acquisition files
are not consumed. Publication is atomic and never overwrites an existing path.
No sequence-bearing package data is added. Fresh import still does not close
complete RNA design, independent-person review or native admission.

## Exact outstanding two-RNA design inputs

For each separately identified #197 and #206 RNA member, a designer must supply:

1. An exact complete transcript-region layout and sequences for every emitted
   region, including untranslated regions, initiation context, an explicit
   termination codon and a specified tail. Region ordering and CDS coordinates
   must be explicit; no default sequence may fill a missing region.
2. The exact mapping to the corresponding reconstructed product. Retaining or
   removing Myc/mCherry, changing a linker or changing coding bases is a declared
   adaptation requiring its own expected product/sequence authority. These
   choices cannot be inferred from the source program's desired behavior.
3. Cap/end chemistry, nucleotide modifications and all other manifest-only
   features required by the complete-RNA profile, with explicit absence where
   a supported feature is unused. Exact bases and manifest declarations remain
   distinct and jointly checked.
4. The two-member recipient/co-delivery assignment, member-specific availability
   assumptions and independently supplied activity/control/observation contract.
   Controller exposure is an external dependency, not a third RNA.

These are supplied design/contract obligations, not a request for a clinical
regimen or a requirement to validate the constructs experimentally before
conditional compilation. The current literal products do not determine these
values.

## Acquisition failures and limits

- PMC's exact linked `NIHMS751362-supplement-Supplementary.pdf` returned HTTP 200
  with an HTML browser challenge, not a PDF. Its response was retained as HTML.
- The documented Europe PMC `supplementaryFiles` endpoint returned an XML error
  stating that this article is not open access. It is retained as an error XML,
  not a supplement archive. This is a retrieval result, not a legal conclusion
  about every possible use of the paper or its sequences.
- One conventional publisher supplement-file locator returned HTTP 403. Its
  file name was not independently confirmed; it cannot establish absence of the
  supplement. A separate NCBI OA-status endpoint returned HTTP 404.
- Official USPTO PSIPS document-detail queries returned 404 for the US
  publication and one related grant. The service explains that shorter listings
  are accessed through Patent Public Search. Bounded NCBI patent-identifier
  searches returned no matching entries. Neither outcome establishes absence.
- The EPO public document-list page returned 403. WIPO's public filing page
  returned a browser challenge; it was retained as a failure diagnostic. No
  challenge was bypassed. A first response-limit failure and a bounded retry
  are both recorded.
- Bounded indexed searches did not locate an exact Addgene deposit for the pair
  or an original ST25/XML file. The patent's statement that FKBP/FRB starting
  materials came from Addgene is not a deposit identity for the complete pair.
  No author was contacted.

## Remaining original-input obligations

1. Preserve the selected patent-pair identity explicitly. Its
   primary pairing is established. Only a Wu-labeled reproduction needs
   the open I.b/II.d join and assay-variant mapping. This is not a mandatory
   dependency of the independently named patent reference.
2. The tracked authorized-input importer now replays the bounded reconciliation
   against original pins and retains its acquisition limitations. Independent
   source-transcription review or stronger original material authority remains
   open; this consistency check does not admit a molecular pack.
   Do not guess bases, normalize synonymous linkers, infer missing junctions or
   silently repair later discrepancies. Complete CDS/RNA termination choices
   remain separately supplied adaptation inputs.
3. The separate `car197206-rna-v1` design supplies complete regions, ordering,
   CDS mappings, chemistry and tails, with independent expected sequence/product
   identities. Native validation remains pending. Supplying termination and
   transplanting transcript context are explicit adaptations, not reproduction
   of complete RNA material from the original controlled-CAR publication.
4. Preserve the authorized-input route and record permitted redistribution
   before bundling acquired assets. Public accessibility, a patent citation and
   a successful download are not affirmative asset-distribution permissions.
   Rights remain unassessed; this checkpoint makes no freedom-to-operate claim.

## Conditional compilation and empirical status

The source program's requirements and the independently supplied mechanism
contract remain different authorities. Acquisition must not create a mechanism
model by copying the requested answers. Designer-supplied onset, cessation,
background and reactivation assumptions can support conditional software
checking when explicitly labeled and scoped to the admitted finite domain.
Measured applicability is a separate status, not a prerequisite for that check.

The proposed deployment requires both RNA members to reach the same human T-cell
recipient and the products to have the modeled localization, abundance and
availability. None of those deployment premises follows from the retrieved
paper/patent. Controller availability, RNA decay, protein decay, receptor
activity cessation and irreversible downstream effects retain distinct meaning.

Until the reference material and complete RNA inputs are admitted together,
RC3-RC5 can continue with clearly artificial, complete software fixtures. That fallback
cannot close a named real reference example or emit a purported real payload.
RC2 remains open; no empirical-validation gate is added to software acceptance.
