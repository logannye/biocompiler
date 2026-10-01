# Partial material reconciliation toward M11.2

Reviewed 2026-09-29 (America/Los_Angeles), following the frozen
[M11.1 audit](m11-human-benchmark-audit.md) on main `42a76a7`.
This companion adds two independently reviewed source-literal component records
and resolves source-version questions. **M11.2–M11.6 remain open.** No complete
construct, calibrated secretion model or human therapeutic profile is admitted.
The historical M11.1 audit remains intact; the findings below supersede its
specific unresolved Allen correction and supplement-copy questions.

## What the new evidence establishes

| Question | Result | Limit |
| --- | --- | --- |
| Allen correction | The publisher's 13 January 2023 notice identifies incorrect x-axis labels and day numbers in structured-abstract figure panel C. | It does not describe sequence/supplement changes; absence of such a statement is not a historical byte comparison. |
| Allen supplemental source | Current publisher, PMC and author-hosted PDFs have identical bytes. | A shared PDF does not identify a complete experimental construct or preparation. |
| Allen component text | Table S2 GAL4UAS regulatory DNA and Human IL-2 protein rows independently agree with the retained transcription. | Neither is a complete nucleotide molecule. The protein is not a CDS or an independently established mature-product boundary. |
| Roybal supplement | Author-manuscript XML references a DOCX; the current PMC distribution and inspected institutional/author inventories expose no matching supplement. | Its contents remain uninspected. This does not establish that the supplement does not exist. |

The [Science publication and correction](https://www.science.org/doi/10.1126/science.aba1624),
[publisher supplement](https://www.science.org/doi/suppl/10.1126/science.aba1624/suppl_file/science.aba1624_sm.pdf),
[PMC supplement](https://pmc-oa-opendata.s3.amazonaws.com/PMC9970000.1/NIHMS1871154-supplement-Supp_Mats_Allen_GM.pdf)
and [author supplement](https://hershbhargava.com/static/pdf/2022_Allen_Science_supplement.pdf)
were inspected as separate source objects. The common PDF is 13,338,063 bytes,
SHA-256 `4b48bb5f8098b2ab595af856ce2ea0355c5e564e5f92b07ad09caf6d92b5b5b4`.
PMC's advertised MD5 `cd19b12bfd414876f655f08db7885ce0` also matches.
PMC metadata reports manuscript version `PMC9970000.1` with `CC BY`; this
manuscript metadata does not establish terms for every publisher/third-party
object. The repository retains only the attributed factual row transcriptions
and curation records, not the complete paper or PDF.

## Retained extraction and correspondence

The [evidence directory](../data/evidence/m11-material-reconciliation/) contains:

- `raw/`: two literal sequence-column transcriptions, preserving printed line breaks.
- `authority.json`: source pins, table/row locators, alphabet and role, a Table S1 named-component association, and a separately scoped assay descriptor.
- `candidates.json`: freshly normalized rows, lengths, hashes and transformation logs; all broader admission/evidence claims are false.
- `review.json`: independent review of source spelling and correspondence, binding the authority, raw inputs and separately checked normalized identities.

| Component | Source locator | Alphabet/role | Length | Normalized SHA-256 |
| --- | --- | --- | --- | --- |
| GAL4UAS | Table S2, printed p26 | DNA / regulatory component | 250 nt | `3b3a17e28bdfdc37d1d6457fdc67c5175a1316d7db852b49f77ac2ff3dce96d8` |
| Human IL-2 | Table S2, printed p27 | protein component | 153 aa | `e667127c8e1b5595f8cdcba9c81b3a15ee9c5eb1a5db018c3e84839b66318365` |

Extraction used `pdftotext -layout`; an independent software agent inspected
rendered original pages and checked a fresh `pdftotext -raw` extraction.
Only the existing ASCII-whitespace/uppercase normalization is allowed. Source
labels are preserved without independently asserting their functional motif
counts. No residues/bases were repaired, back-translated or concatenated.
This is software-agent source review, not human or experimental validation.

Table S1 p24 associates these named components with its human-IL-2 response
vector entry. That association does not supply complete nucleotide sequence,
junctions, all backbone regions, topology/chemistry or exact measured-preparation
identity. Production template, packaged vector, engineered cell preparation,
mature product and administered material remain different objects.

The p4 human IL-2 methods describe intracellular staining after secretion
blockade. The retained record has no numerical observations, units, replicate
statistics or exact construct-to-assay join. Adjacent mouse ELISA methods are a
different context. No extracellular per-cell secretion rate is inferred.

## Offline reconstruction and trust boundary

Run from a checkout with Python 3.11 or later:

```sh
PYTHONPATH=src python tools/check_material_reconciliation.py
PYTHONPATH=src python -m unittest discover -s tests -p 'test_material_reconciliation.py' -v
```

The checker reconstructs candidate rows from the retained transcriptions using
the existing normalizer, compares source/class/locator correspondence and the
independently reviewed normalized hashes, and rejects unsupported claims.
It is bounded to these two reviewed rows, with no public registry, compiler IR
or admission interface. It does not extract arbitrary PDFs or fetch sources.
Clean-checkout verification is offline **from the reviewed transcriptions**;
repeating the original visual/PDF extraction requires the separately pinned PDF.

Authority comes from the reviewed repository revision and independent source
inspection. Local hashes detect changes relative to that authority; a caller
who rewrites every input, review and checker can manufacture a new apparent
result. A source-literal extraction pass does not establish external scientific
truth, biological function or exact experimental-material identity.

## Roybal source-access boundary

The [official PMC dataset](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) exposes
Roybal as manuscript `PMC5072533.1`, license code `TDM`, without distributed
PDF/media entries. Its
[XML](https://pmc-oa-opendata.s3.amazonaws.com/PMC5072533.1/PMC5072533.1.xml)
is 162,422 bytes, SHA-256
`ddaacb509edb49b7a0fce306f19fb7368a5aea78282ebe5e926cdb568cf744d2`.
The supplement locator `supplementary-material[@id='SD1']/media/@xlink:href`
names `NIHMS820006-supplement-1.docx`; the XML supplies no content description.
The [distribution policy](https://pmc.ncbi.nlm.nih.gov/tools/textmining/)
explains why non-CC manuscripts can expose XML/TXT without supplementary media.

The [author repository tree](https://api.github.com/repos/UCSF-CMP/lim-lab/git/trees/50180ae8c58b81ddb390d6957f355ad1b0eb5cdf?recursive=1)
contains the inspected publication PDF as Git blob
`cb5ac7d0d719c1a2d923454d54229c5457d2ca99`, exactly matching the retained
5,783,563-byte PDF (SHA-256
`fac865695eb070c7b2c621b1c0a1fc24089a91903c9e3cfbbe396233b7ae2e6c`).
No matching DOCX was found in that untruncated snapshot. The documented public
eScholarship API resolves [the publication](https://escholarship.org/uc/item/4z7460gm)
but returns `suppFiles: null`. These are bounded inventory observations, not
proof of global absence. A similarly named supplement for a different Roybal
paper was not joined to this study.

## Next evidence gate

M11.2 requires a versioned **complete nucleotide record** for a selected
source-described construct, independently reconciled with required regions,
boundaries, topology/chemistry and the measured material. Obtain Roybal's actual
supplement and determine its scope, or an Allen full construct record with that
correspondence. Component tables and empty/receptor backbones cannot substitute.
If access requires author contact or new repository terms, prepare that specific
request for the user; no external contact or terms acceptance has occurred.

Numerical observations, assay normalization and calibration/evaluation separation
remain separate M11.3–M11.5 obligations. A supported ex-vivo/vector benchmark
would require an explicit profile decision; it cannot silently replace the
current proposed RNA/in-vivo scope.
