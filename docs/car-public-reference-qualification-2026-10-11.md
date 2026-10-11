# Public CAR mRNA reference qualification

Reviewed 2026-10-11. This is a bounded public-source curation record for Phase 1,
not a qualified molecular reference or experimental validation. CAR is the first
chosen payload use case; the product target remains human immune cells engineered
in vivo. No antigen or clinical indication has been selected by this review.
Human-cell experiments outside the body and human cells in mouse models remain
distinct source contexts.

No complete, assay-matched, reusable full-transcript reference has yet been
qualified from the sources below. This does not establish that no eligible
public reference exists. In particular, failed retrieval of a supplement is an
access limitation of this review, not proof that the supplement lacks material.

## Qualification boundary

The existing [reference qualification gate](researcher-alpha-reference-qualification.md)
and [typed-path evidence constraints](typed-path-public-evidence-2026-10-10.md)
remain authoritative. A usable source must join:

1. An identified complete transcript, or a completely documented assembly with
   exact constituent versions, junctions, transcription boundaries and tail.
2. Explicit cap and nucleotide chemistry matching the assayed preparation.
3. The exact material to its human T-cell preparation and separately identified
   expression, receptor-function and delivery observations.
4. Publicly accessible original evidence and terms permitting the intended
   evidence/sequence reuse. Paper copyright, deposit transfer conditions and
   patent permissions are separate questions.

Named backbones, a familiar CAR protein, and a coding-sequence accession do not
fill missing nucleotide regions. A synthesis-kit name does not by itself settle
every chemical property. Exact published assembly is eligible for review when
its full boundaries are documented; undocumented assembly is not.

## Candidate matrix

| Candidate | Verified source context and material description | Remaining qualification issue | Current disposition |
| --- | --- | --- | --- |
| Kahwaji et al., 2026, DOI `10.1016/j.omtn.2025.102805` | Primary human T cells; distinct CAR-expression and target-cell-killing results. Methods compare unmodified uridine with modified variants and name ARCA and the pRNA2-(A)128 backbone. | The article's Table S1 is in a public supplement not yet successfully retrieved. The two named deposits are a backbone and a CAR-containing DNA repair template, not the complete assayed RNA construct. Exact transcript boundaries, material identity and reusable sequence access remain to be joined. | Strongest lead for an unmodified reference; not qualified. |
| Picht et al., 2026, DOI `10.1016/j.omtn.2026.102929` | Primary human T-cell expression/function and electroporation-versus-LNP comparison. Methods explicitly name pRNA2-(A)128, a 128-base tail, ARCA and 5moU. Table S1 contains inserts; Table S2 contains primers. | Exact source tables and the complete backbone/junction/transcription-boundary join are not yet verified. Modified RNA chemistry must be represented as stated; it cannot be converted to an unmodified reference. | Strong public assembly/evidence lead; not qualified. |
| Lao et al., 2026, DOI `10.3390/ijms27020796` | Primary pan-T cells; CAR expression and intracellular m6A-related measurements. Main Table 1 specifies UTR variants; methods name ARCA and a template-coded poly(A) tail. | Full assayed transcript, tail length and boundaries have not been joined. Supplementary alignments are not yet inspected. A killing assay has not been verified in this review. | Expression/material lead; not a qualified functional reference. |
| Parayath et al., 2020, DOI `10.1038/s41467-020-19486-2` | Human-cell expression and function, with separate delivery/treatment studies in mouse models. Methods identify commercially synthesized codon-optimized CAR mRNA and explicit ARCA, pseudouridine and 5-methylcytidine chemistry. | No complete transcript was identified in the main article. Supplementary material and exact commercial material identity remain unjoined. Mouse in-vivo findings do not establish human in-vivo delivery. | Useful delivery-context evidence; not qualified. |
| Du et al., 2016, DOI `10.1371/journal.pone.0161820` | Human PBMC-derived immune populations, CAR expression/function, and a separate mouse experiment. Methods name an alpha-globin 3′UTR and a 150-base tail. | The publication does not expose a complete joined transcript in the inspected text. Its two listed supplements are cell-gating figures. A coding-region reference and construction description cannot supply missing transcript/chemistry identity. | Older unmodified-era lead screened; insufficient material record. |
| Kitte et al., 2023, DOI `10.1016/j.omtm.2023.101139` | Primary human T-cell expression/function and ex-vivo delivery comparison; CleanCap and full m1Ψ substitution are stated. | The tail is added by subsequent enzymatic polyadenylation; a fixed complete assayed transcript is not established. Commercial delivery composition has additional proprietary constraints. | Useful assay/delivery evidence; insufficient exact material reference. |

## Primary sources and access details

### Kahwaji: strongest unmodified lead

- [Article and supplementary-material listing](https://pmc.ncbi.nlm.nih.gov/articles/PMC12984635/)
- [Publisher DOI](https://doi.org/10.1016/j.omtn.2025.102805)
- [Official open full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12984635/fullTextXML)
- [pRNA2-(A)128 deposit, Addgene 174006](https://www.addgene.org/174006/)
- [CAR DNA repair-template deposit, Addgene 183473](https://www.addgene.org/183473/)

The article is CC BY 4.0. Its public supplement is `mmc1.pdf`, described as
Figures S1–S7 and Table S1. Raw study data are available by request; no such
request was made. Addgene 174006's sequence download requires login; the page
lists academic/nonprofit UBMTA terms, no industry availability and a discontinued
material listing. Addgene 183473 requires affinity-reagent sequence-policy
acceptance and is a TRAC homology-directed DNA repair template. No login,
acceptance or sequence download from those deposits was performed.

### Picht: explicit assembly and material-use statement

- [Article and supplemental listing](https://pmc.ncbi.nlm.nih.gov/articles/PMC13139981/)
- [Publisher article and CC BY 4.0 license](https://doi.org/10.1016/j.omtn.2026.102929)
- [Official open full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13139981/fullTextXML)
- [Williams et al. 2010 backbone paper, including inline supplementary methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC3024561/)
- [Williams 2010 publisher copy](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2010.00181/full)
- [Williams et al. 2009 original backbone construction source](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0007474)
- [Williams 2009 Supplementary Methods S1](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0007474.s001)

Picht's availability statement says there are no restrictions on use of
materials. This is a useful explicit statement, not a substitute for checking
the provenance and rights of each retained source file. Its `mmc1.pdf` contains
Figures S1–S8 and Tables S1/S2. The Williams paper provides public backbone maps
and construction details, but is a neuronal-expression study; its biological
results cannot substitute for human T-cell evidence. It may help close a
documented material join without accessing Addgene, subject to exact comparison.

The Williams 2009 supplement was successfully read from PLOS in memory
(452,608-byte Word document). It explicitly identifies the two beta-globin UTR
inserts, their construction junctions, and the promoter modification. The 2010
paper adds the encoded-tail construction and marks the first transcribed base
and cloning region in Figure S4. The 2009 article declares its work public
domain. These records close part of the backbone provenance gap, but no complete
CAR transcript has been reconstructed: the modern assay-specific insert and
junction tables remain unread, and identity with the assayed construct remains
to be checked.

### Other inspected primary sources

- [Lao article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12841529/) and
  [publisher supplement landing page](https://www.mdpi.com/article/10.3390/ijms27020796/s1):
  `ijms-27-00796-s001.zip`; article CC BY; underlying data by request.
- [Parayath article](https://www.nature.com/articles/s41467-020-19486-2) and
  [PMC copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC7695830/):
  `41467_2020_19486_MOESM1_ESM.pdf`; article CC BY 4.0, subject to separately
  credited third-party material.
- [Du article, methods and full supplement census](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0161820):
  article CC BY; supplements `journal.pone.0161820.s001` and `.s002` concern
  cell gating.
- [Kitte article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10663670/) and
  [primary PubMed record](https://pubmed.ncbi.nlm.nih.gov/38027056/).

Previously reviewed Hunter 2025 and Gibor 2026 remain separate incomplete leads;
this search does not promote them. Public sequence deposits for viral or
genome-editing CAR constructs also cannot be relabeled as complete delivered
mRNA references.

## Next bounded curation step

Prioritize the Kahwaji and Picht public supplements and the published Williams
backbone record. Determine whether one source provides a full transcript or
whether all assembly boundaries can be established from the actual published
records. Join that exact material to the corresponding assay variant before
admitting an example. If any region, chemistry or source-to-assay identity
remains unknown, retain a precise missing-field diagnostic and withhold reference
qualification.

Direct publisher/PMC supplement retrieval encountered access errors; the public
Europe PMC supplementary-file service timed out. Official Europe PMC full-text
XML was readable and was inspected in memory. Picht's public publisher metadata
also confirms the open-access license and article identifier
`S2162253126001009`; its full-view API returned an authorization requirement.
No authenticated access was attempted. These are retrieval observations,
not claims about supplement contents. No files were retained from restricted
sources, no access restriction was bypassed, and no author was contacted. No
sequence was designed, optimized, silently reconstructed, or added to a compiler
fixture. This record does not provide an experimental protocol or establish
clinical safety, efficacy, or human in-vivo delivery.
