# Public evidence constraints for the typed compiler path

Reviewed 2026-10-10. This is a bounded source review and compiler-design note,
not an admitted component library, a molecular fixture, or an experimental
validation result. No sequence was designed, modified, reconstructed from a
protein, downloaded through restricted access, or added to the compiler.

The immediate use of these sources is to identify distinctions that the typed
path must preserve. They do not establish that the current supplied component
models implement these experiments or that an emitted RNA payload will behave
as specified in human immune cells in vivo.

## Preserve the completed curation work

The [reference qualification](researcher-alpha-reference-qualification.md),
[M11 audit](m11-human-benchmark-audit.md),
[material reconciliation](m11-material-reconciliation.md), and
[biological-correctness handoff](biological-correctness-next-phase-handoff.md)
remain the starting authority for repository curation status. In particular:

- Allen 2022's correction and current supplement copies were reconciled. The
  retained GAL4UAS DNA and Human IL-2 protein rows are component records, not a
  complete nucleotide construct. Its retained human assay description concerns
  intracellular staining after secretion blockade, not extracellular secretion
  rate. This review does not reopen those resolved source questions.
- The earlier Roybal secretion study is DOI `10.1016/j.cell.2016.09.011`.
  The recognition study below is a **different paper**, DOI
  `10.1016/j.cell.2016.01.011`; its accessible material cannot repair the missing
  supplement join for the secretion study.
- The historical `WO2022081694A1` Murine-FAPCAR record is a 1,491-base RNA CDS
  reference, not a complete delivered mRNA or human experimental evidence.
  The existing Addgene #183475/#203348 and human-T-cell RNA-backbone access,
  chemistry and full-material gaps remain unresolved here.
- The previously identified human-T-cell 5′UTR study and `GSE232927` remain a
  separate translation-proxy curation lead. Mean ribosome load must not become
  a secretion, killing, or in-vivo delivery measurement.

## Primary sources checked in this review

### Rurik et al., Science 2022: delivered mRNA and recipient context

`10.1126/science.abm0594`, PMID `34990237`, PMCID `PMC9983611`.
The study reports CD5-targeted LNP delivery of modified mRNA encoding FAPCAR,
transient CAR expression, and antifibrotic activity in a mouse cardiac-injury
model. Figure 1 distinguishes expression measurements from target-cell killing;
Figures 2–4 distinguish recipient-cell measurements, antigen transfer, and
organ-level outcomes. These are separate observations with separate subjects.
The paper also reports trogocytosis: an observed antigen need not identify the
cell that originally produced it. [Primary record and figure legends](https://pubmed.ncbi.nlm.nih.gov/34990237/)

Material identifiers include `CD5/LNP-FAPCAR`, `CD5/LNP-GFP`, and
`IgG/LNP-FAPCAR`; these are experimental preparation labels, not complete
sequence-and-formulation manifests. This review did not verify a public,
redistributable full delivered transcript with all boundaries and chemistry.
The article's competing-interest statement identifies relevant patents,
including `PCT/US21/54764` and `PCT/US21/54769`; public description alone is not
a material or redistribution license. No human in-vivo claim is inferred.
[Primary material and interest statements](https://pubmed.ncbi.nlm.nih.gov/34990237/)

### Roybal et al., Cell 2016: priming is a stateful process

`10.1016/j.cell.2016.01.011`, PMID `26830879`, PMCID `PMC4752902`.
The recognition circuit induces CAR expression after synNotch stimulation;
Figure 2 measures subsequent activation and receptor-expression decay in
**Jurkat cells**. The reported approximate eight-hour expression half-life after
stimulus removal is an assay-specific observation, not a universal shutdown
deadline. Primary-human-T-cell and mouse tumor experiments are separate
contexts. Methods describe lentiviral engineering with modified
`pHR’SIN:CSW` vectors; this transcriptional implementation is not an mRNA-only
implementation. The primary-cell preparation also excluded basal-CAR-expressing
cells during sorting, a preparation condition that a component contract cannot
silently omit. [Author-hosted paper, Figure 2 and Experimental Procedures](https://limlab.ucsf.edu/pdfs/ktr_2016.pdf)

A concrete public material locator is `RRID:Addgene_79129`,
`pHR_EGFPligand`: a lentiviral plasmid for the synthetic surface ligand, not the
complete recognition circuit, CAR transcript, or administered material. Its
depositor comments associate the recognition paper while its principal citation
is the companion synNotch paper. The record lists academic/nonprofit UBMTA
terms and no industry availability; those transfer terms do not establish a
sequence-redistribution grant. No sequence file was obtained or joined to a
measured preparation here. [Depositor record](https://www.addgene.org/79129/)

### Williams et al., Science 2020: ordering and delayed inhibition

`10.1126/science.abc6270`, PMID `33243890`, PMCID `PMC8054651`.
Figure 3 distinguishes serial receptor induction from a parallel split-receptor
implementation, despite a shared three-antigen recognition objective. Figure 2
reports an antigen-triggered apoptotic inhibitory branch: some off-target
killing occurred during the first 24 hours before later suppression. That
observation directly argues against treating this biological NOT operation as
an instantaneous Boolean veto. The paper distinguishes primary human T-cell
assays from a mouse tumor model. [Primary record, Figures 2–3](https://pubmed.ncbi.nlm.nih.gov/33243890/)

The source identifies expression plasmids available from Addgene under an MTA
and a supplement named `NIHMS1685408-supplement-SUPP_Williams_2020.pdf`.
This pass did not reconcile individual plasmid accessions, full nucleotide
records, measured preparations, or reusable code licenses. Those remain
material-acquisition tasks, not inferred compiler inputs.
[Primary manuscript's availability statement](https://pmc.ncbi.nlm.nih.gov/articles/PMC8054651/)

## Design obligations and proposed acceptance criteria

These are architectural deductions from the distinctions above, not newly
established experimental guarantees. They can guide artificial semantic tests
without pretending those tests reproduce a biological experiment.

| Distinction to retain | Proposed typed-path acceptance criterion |
| --- | --- |
| Predicate versus event versus remembered state | Keep the admitted expression constructor, resolved declaration and occurrence identity through lowering. Repeated evaluation of a predicate must not create a fresh event; a causal priming step must not become a commutative conjunction without an explicit checked refinement. |
| Executor, observed cell, affected cell and encounter | Keep nominal bindings through every IR and endpoint map. Reject a same-target conjunction assembled from observations of two different subjects unless the source explicitly authorizes that scope. Antigen observation alone must not assert antigen-production origin. |
| Stateful priming versus current authorization | Exercise unprimed, primed, stimulus-removed and re-encounter histories. Source-declared persistence/reset rules determine the software result; literature half-lives must not silently supply those rules. |
| Initiation versus completion versus shutdown | Distinguish suppressing new requests, cancelling an active attempt, stopping production, loss of receptor activity, and completion of a downstream effect. Reject an implementation that substitutes one for another. A delayed inhibitor cannot satisfy an immediate-veto contract by relabeling its output. |
| Material layer and implementation mechanism | Represent template DNA, CDS, full transcript, RNA chemistry, recipient preparation and delivery formulation as distinct authorities. A DNA-transcription component must not become eligible for an RNA-only target solely because it encodes a familiar protein. Missing required regions or chemistry remain explicit gaps. |
| Assay and applicability | Preserve assay endpoint, units, sampling time, preparation, cell type/species and experimental setting. A receptor-expression measurement cannot discharge a killing obligation; intracellular staining cannot discharge extracellular secretion; mouse or human-cell-in-mouse evidence cannot discharge human in-vivo applicability. |
| Evidence versus model assumptions | Each selected contract should retain separately named evidence and assumptions, with explicit applicability results. Exact source/component/payload correspondence may pass under supplied assumptions while empirical realization remains unresolved. Unknown or absent evidence must not be coerced to a negative observation or a validated biological claim. |

The first implementation increment need not model all these biological processes.
It should preserve the existing declared distinctions through the typed path and
reject unsupported forms explicitly. The corresponding checker should derive
its endpoint correspondence from original authority, independently of producer
annotations. Source edits to event ordering, subject binding, lifetime or effect
kind should change the checked implementation or yield a precise rejection;
they must not disappear during serialization or lowering.

## Evidence boundary and next curation gate

No complete delivered-mRNA/programmed-CAR-T benchmark was qualified in this
bounded review. This is a statement about the sources inspected and the joins
verified here, not a claim that such material is globally unavailable. Public
paper access and deposited-plasmid availability are insufficient to manufacture
a complete executable-RNA fixture.

A future empirical reference needs a versioned full material record, explicit
reuse terms, exact construct-to-preparation-to-assay correspondence, and an
observation map compatible with the selected model. Parameters and numerical
bounds need their own curation and uncertainty treatment. Until then, use these
sources as design constraints, retain artificial fixtures as software evidence,
and keep the real-reference qualification gate open.

Access notes: primary PubMed figure legends and the author-hosted Roybal PDF
were readable on the review date. Direct PMC page requests encountered browser
challenges; indexed primary manuscript text exposed the Williams availability
statement. No access restriction was bypassed. URLs and identifiers are source
locators, not newly frozen evidence-byte pins. No external contact, MTA
acceptance, sequence/code redistribution, model calibration, or experiment was
performed.
