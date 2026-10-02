# Biocompiler: biological correctness and evidence coverage handoff

Prepared: 2026-10-02, America/Los_Angeles.

Purpose: give a fresh Codex session the context, objective, constraints, sources,
and acceptance criteria for the development phase after the OCaml migration.
The user has no wet lab. Improve the biological grounding of compiler outputs
using existing public experiments, exact material records, reproducible analyses,
and appropriately evaluated models.

## 1. Instructions to the next session

Read this document and the repository instructions, establish the actual final
migration baseline, then systematically execute the BC checklist below. Preserve
existing work. Re-read this document before each batch and update its checkboxes
only when their stated deliverables and validation gates have been met. Record
partial progress without marking a whole milestone complete.

The objective is to build a small, defensible, evidence-backed implementation
library and an executable public-data benchmark system connected to the actual
compiler. A literature summary, a collection of URLs, or a simulator disconnected
from selected molecular implementations is insufficient.

### Verify the end-of-session baseline; do not assume it

This handoff was written during the migration, not after its final acceptance.
At preparation time, the inspected checkout HEAD was
`6c31b59a789a0b5a8d8b8edc6fea93d586292d78`, with active uncommitted migration work.
The live migration roadmap still described Python as the default, explicit
validated OCaml architecture routes, and pending native/public-manager,
distribution, validation, and default-cutover work. These are a preparation-time
snapshot, not assertions about the revision you will receive. Hosted status was
not independently refreshed for this handoff.

Begin by reading:

1. [Repository instructions](../AGENTS.md).
2. [Language migration roadmap](language-migration-roadmap.md), including its
   latest status, LM checkboxes, distribution/cutover gates, and linked receipts.
3. [Language decision](decisions/0007-language-boundaries-and-ocaml-core.md).
4. [Product roadmap](roadmap.md), especially M11–M16 and current product scope.
5. [Composite RNA architecture](payload-architecture-v0.1.md),
   [component contracts](component-contracts-v0.1.md), and
   [development validation](development-validation.md).

Record the received branch/commit, dirty-file state, actual default engine,
supported public routes, and exact revision/platform validation evidence. Distinguish
implemented source from validated functionality and a merged PR from successful
integration/release gates. An old handoff or historical test count is not current
authority. Prefer the current migration roadmap over older narrative handoffs.

If migration is incomplete, identify the remaining dependency explicitly. Continue
independent source curation and benchmark planning; do not silently restart the
migration, change the default engine, or claim its completion. Tie core integration
to the actual available and validated interfaces.

## 2. Product context and agreed architecture

Biocompiler translates explicit therapeutic intent into exact, complete RNA
payload specifications for human immune cells engineered in vivo. Python and
eventually conversational authoring produce explicit programs. Natural language
and Python execution do not themselves define cellular runtime behavior.

The accepted language allocation is:

| Layer | Owner | Responsibility |
| --- | --- | --- |
| Studio and visual interfaces | TypeScript, HTML, CSS | Editing, review, diagnostics, artifact and evidence inspection |
| Conversational authoring | Python orchestration | Propose explicit reviewable programs |
| SDK, notebooks, CLI | Python restricted DSL and thin adapters | Accessible scientific authoring and workflow integration |
| Canonical intent and semantics | OCaml | Identity, types, units, scope, target context, assumptions |
| Behavioral IR and reference execution | OCaml | Conditions, events, state, timing, concurrency, observations |
| Mechanism IR and realization contracts | OCaml | Causal/model interfaces, dependencies, unresolved obligations |
| Component selection and architecture | OCaml; Python for exploratory proposals | Deterministic compatibility and acceptance; external search/model proposals |
| Molecular construction and emission | OCaml | Exact sequences, coordinates, chemistry, complete member inventories |
| Independent verification | Separately runnable OCaml checker | Reconstruct candidates against independent original authority |
| Canonical artifacts and manifests | OCaml; Python for workflow/storage | Canonical content, provenance, claim scope, exact export binding |
| Physical biological execution | Outside software | Empirical behavior of manufactured material in cells |

After a fully accepted migration, the intended foundation is one authoritative
semantic core with preserved public behavior and independently checked RNA plus
manifest export. The migration does not discover molecular mechanisms, install a
characterized biological library, or demonstrate function in human recipients.

### Existing capabilities to preserve

The documented compiler already supports bounded compilation under supplied
executable component models and exact molecular templates. It preserves source
correspondence, obligations, helper inventories, recipient assignments, and
many-to-many relationships between behavior, components, and RNA molecules.
Composite profiles include finite-state behavior, explicit controls, quantitative
branches, sampled integration, and declared channels within documented limits.
Inspect their current implementations before relying on any particular route.

The structural molecular workflows include supplied linear RNA assembly and a
declared secreted-product precursor profile. Their demonstrations use artificial
sequences; structural completion does not establish expression, processing,
secretion, activity, delivery, or human therapeutic eligibility. See
[molecular design](molecular-design-v0.1.md) and
[molecular implementation](molecular-implementation-v0.1.md).

Potential future library families include secreted-product, receptor, reporter,
intracellular regulator, antigen, and helper/control mRNAs, plus cooperative
multi-RNA implementations. This is a development direction, not an already
validated catalog. Guide RNA, silencing RNA, circular RNA, self-amplifying RNA,
and functional RNA sensors need appropriate additional implementation and checking
profiles; storing their sequences is not equivalent to compiling their behavior.

## 3. Existing evidence work: continue it, do not restart it

Read these records before selecting a benchmark:

- [M11.1 human benchmark audit](m11-human-benchmark-audit.md): a bounded source
  comparison that deferred selection of a complete human therapeutic benchmark.
- [Partial material reconciliation](m11-material-reconciliation.md): later findings
  that supersede specific earlier Allen correction/supplement uncertainties.
- [Machine-readable audit](../data/evidence/m11-human-benchmarks/audit.json) and
  [material authority](../data/evidence/m11-material-reconciliation/authority.json).
- [Reference promotion rules](reference-benchmarks.md),
  [human target contract](human-target-contract-v0.1.md),
  [human acceptance contract](human-acceptance-contract-v0.1.md), and
  [human admission policy](human-admission-v0.1.md).

Preparation-time findings, subject to subsequent repository updates:

| Existing lead | What it contributes | What remains unresolved |
| --- | --- | --- |
| Roybal 2016 | Primary-human-cell conditional secretion observations | Complete experimental material, advertised supplement, quantitative/temporal interpretation, and applicability to the RNA/in-vivo target |
| Allen 2022 | Human-cell conditional-output/context evidence; two source-literal component rows reconciled | Full nucleotide construct and measured-material correspondence; the human assay descriptor is intracellular staining after secretion blockade, not extracellular secretion rate |
| Allen correction | Current reconciliation identifies structured-abstract axis/day-label changes and matching current supplement copies | This does not supply the missing full construct or establish historical byte equality |
| Equalizer-L | Human non-immune-cell reporter/model benchmark candidate with historical source records | Model execution/evaluation and material correspondence; archived code/license questions require resolution; no primary-immune-cell or in-vivo transfer |
| Historical exact-CDS reference | Independently pinned sequence-reproduction regression | Not a complete delivered RNA, not human biological validation, and not a new product backend |

M11.1 is complete within its audit scope. M11.2–M11.6 and downstream biological
acceptance were still open in the inspected roadmap. Do not mark them complete
because an unrelated assay can be reproduced. Preserve their existing acceptance
criteria and explicitly map narrower new accomplishments to them.

## 4. Non-negotiable scientific and product boundaries

1. Preserve the product target: RNA payloads for human immune cells engineered in
   vivo. Human-cell literature reconstruction is supporting evidence work, not a
   replacement ex-vivo, DNA, non-immune, or non-human product track.
2. Separate component origin from recipient species. Do not silently humanize a
   supplied synthetic or heterologous sequence. Do not expand historical non-human
   fixtures into new organism backends or treat them as human applicability evidence.
3. Keep exact sequence identity, structural consistency, model-conditional
   translation, empirical support, predictive evaluation, and use admission as
   separate dimensions. A pass in one cannot confer a pass in another.
4. Continue allowing supported software compilation under explicit supplied
   contracts even when empirical support is unresolved. This phase adds evidence
   and controls biological claims; it must not conflate missing evidence with
   incorrect translation or require every software fixture to be experimentally
   validated. Preserve existing use-admission gates separately.
5. Do not infer a complete transcript, chemistry, mature molecule, or experimental
   preparation from a CDS, protein, plasmid, patent association, or neighboring
   sequence listing. Do not repair, back-translate, concatenate, or optimize source
   sequences without explicit transformation authority and a new artifact identity.
6. Human cell lines, primary human cells, human cells in animal hosts, and human
   in-vivo experiments remain distinct. Delivery method and cell state are part of
   applicability. Do not transfer results across these contexts implicitly.
7. Keep observation meanings distinct: RNA abundance, ribosome loading, fluorescence,
   intracellular protein, extracellular concentration, per-cell secretion rate,
   protein activity, and clinical outcome are not interchangeable. Any conversion
   needs an explicit observation model and sufficient measurements.
8. Separate missingness, non-detection, measured zero, failure, and contradictory
   evidence. Sparse endpoints do not establish continuous-time bounds or shutdown
   deadlines. A fitted range is not a universal biological guarantee.
9. A publication, database annotation, source hash, reviewer label, or model-generated
   citation does not establish truth. Repeated mirrors and multiple papers using the
   same data are not independent experiments.
10. Preserve strict/partial behavior and explicit unresolved obligations. Where a
    requested biological claim lacks support, abstain or retain the gap; never
    fabricate missing material, parameters, observations, or applicability.

## 5. Target evidence architecture

Build a traceable chain:

```text
Versioned source and accession
  -> source-literal extraction
  -> exact material/context/observation correspondence
  -> reviewed claim and analysis inputs
  -> reproduced result or evaluated predictive model
  -> versioned component applicability and evidence assessment
  -> build-specific manifest with supported claims and remaining obligations
```

Use existing content-addressed records, schemas, authority resolution, and
dependency invalidation before adding new infrastructure. A graph of typed linked
records does not require a new graph database. Keep large raw datasets in a
versioned permitted artifact store; keep compact manifests, fixtures, and receipts
in the repository according to its data policy.

### Claim record requirements

Each claim should contain, directly or by pinned reference:

- Exact subject/material identity, construct variant, full/partial sequence scope,
  chemistry/topology where relevant, and the strength of its link to measured material.
- Recipient species/subtype/state, experimental environment, delivery, exposures,
  relevant host dependencies, and explicitly unknown context dimensions.
- A typed assertion: structural fact, reported observation, model assumption,
  reproduced analysis, prediction, or independently evaluated prediction.
- Observable definition, units, sampling, assay mapping, controls, detection limits,
  biological versus technical replicate identities, and donor/study relationships.
- DOI/accession/version, exact figure/table/file locator, raw and normalized hashes,
  extraction/normalization history, licenses/access conditions, and review provenance.
- Uncertainty, applicability domain, extrapolation status, contradictory evidence,
  missing obligations, and the precise claims that may be exposed to users.
- Model/code/environment/parameter identities and data-partition identities when used.

Do not flatten these dimensions into one confidence score. The existing closed
interval domain language is not a statistical uncertainty system. Add explicit,
versioned representations only as required by an actual benchmark; do not reinterpret
existing hard bounds as confidence or prediction intervals.

### Language ownership

| Responsibility | Implementation home |
| --- | --- |
| Retrieval, parsing, extraction proposals, data preparation | Python tools/adapters |
| Numerical analysis, fitting, model comparison, exploratory proposals | Python scientific adapters with frozen inputs/results |
| Review interface and evidence/context inspection | TypeScript Studio when an actual workflow warrants it |
| Canonical evidence/claim types, compatibility, applicability policy, dependency invalidation | OCaml authority |
| Independent reconstruction and allowed-claim/export checks | Separate OCaml checker modules |
| Storage, transport, literature discovery | Integration layer; cannot confer validity |

LLMs may discover sources and propose extractions. Require source-located support,
deterministic validation, and independent review for authoritative records. Multiple
LLM outputs agreeing is not biological replication. Distinguish software source review
from review by a qualified scientist. Expert remote review can help without a wet lab,
but record exactly what was reviewed and by whom.

## 6. Public resource strategy

Use primary sources, original data, and resource-owner documentation. Use reviews
for discovery; trace consequential claims back to the underlying experiment.
Record access failures without concluding the resource does not exist.

| Resource | Intended contribution | Boundary |
| --- | --- | --- |
| [NCBI RefSeq](https://www.ncbi.nlm.nih.gov/refseq/) | Versioned transcript/protein identity and reference annotations | A reference is not necessarily the engineered construct or measured preparation |
| Study-linked GenBank/ENA records and [Addgene sequence records](https://www.addgene.org/134403/sequences/) | Exact construct candidates and sequencing provenance | Distinguish depositor, assembled, full, and partial verified records; access may require terms/login |
| [PMC developer services](https://pmc.ncbi.nlm.nih.gov/tools/developers/), primary publisher/author supplements | Machine-readable papers, methods, tables, corrections, accession discovery | Use permitted automated routes and source-specific reuse terms |
| [GEO/SRA](https://www.ncbi.nlm.nih.gov/geo/info/seq.html) | Raw and processed functional-genomics measurements and metadata | Expression and translation endpoints need assay-specific interpretation |
| [ImmPort](https://pmc.ncbi.nlm.nih.gov/articles/PMC5827693/) and [FlowRepository documentation](https://flowrepository.org/images/pdf/FlowRepository_Workshop_CYTO2012.pdf) | Immunological measurements, cytometry, study context | Verify actual files, controls, calibration, gating and donor information for each selected dataset |
| [DICE](https://dice-database.org/) and [CELLxGENE Census](https://chanzuckerberg.github.io/cellxgene-census/notebooks/analysis_demo/comp_bio_census_info.html) | Human immune-cell context and host-dependency investigations | Transcript detection does not prove functional capacity; non-detection is not definitive absence |
| [BioModels](https://www.ebi.ac.uk/training/online/courses/biomodels-quick-tour/what-is-biomodels/) and publication-specific archived code | Executable model candidates and reproducible published simulations | Reproducing a publication is distinct from predictive validity in the compiler's target context |
| [Evidence and Conclusion Ontology](https://www.evidenceontology.org/) and [SBOL](https://sbolstandard.org/datamodel/) | Evidence/assertion vocabulary and design interchange | Standard conformance is not biological validation |

Follow each selected study across its paper, supplement, sequence deposit, data
accession, and code release. Preserve unresolved joins between these objects.
Patent disclosures can help locate material but are not substitutes for matched
experimental measurements. Do not infer exact experimental identity from a shared
name or a paper–patent association.

No author contact, new terms acceptance, restricted-data acquisition, paid services,
or wet-lab work was performed or authorized by this planning conversation. Use
accessible permitted alternatives and prepare any essential external request for
the user rather than sending it without authorization.

## 7. New quantitative benchmark lead: primary-human-T-cell RNA translation

The side conversation identified this additional primary study:

**Optimizing 5'UTRs for mRNA-delivered gene editing using deep learning**,
Nature Communications (2024), DOI
[10.1038/s41467-024-49508-2](https://www.nature.com/articles/s41467-024-49508-2).

The article reports approximately 200,000 shared 5'UTR variants across experimental
cell types, including donor-derived human T cells. Its polysome-profiling endpoint
is mean ribosome load, a translation proxy. The article identifies:

- New raw/processed data: [GSE232927](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE232927).
- Earlier related library data: [GSE114002](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE114002).
- Figure source data: [Zenodo 10.5281/zenodo.11398662](https://doi.org/10.5281/zenodo.11398662).
- Analysis/model code: [repository](https://github.com/castillohair/paper-5utr-design)
  and [archived release](https://doi.org/10.5281/zenodo.11403014).

**Review status:** article methods and data/code-availability statements were read.
The linked datasets and code were not downloaded, frozen, audited, or executed in
this side conversation. This is a promising curation lead, not an accepted benchmark.

Initial question: can we reconstruct sequence-to-assay correspondence and reproduce
reported translation-proxy measurements, then evaluate a bounded model connected to
supplied RNA components? Start with the reporter/translation observations. This does
not authorize a new genome-editing product profile or imply editing efficacy.

Preserve exact cell state, material/library architecture, assay context, normalization,
chemistry, and replicate structure. Determine sequence overlap with earlier training
data before claiming independent validation. Do not interpret variant count as donor
count, independent-study count, or complete-payload coverage. A good result here can
support a narrow translation claim; it does not establish secretion, clinical effect,
in-vivo delivery, or full M11 therapeutic-reference completion.

## 8. Ordered development checklist

Use BC identifiers for this next phase. Keep LM migration status and M11–M16 product
status separate; cross-reference them rather than relabeling existing milestones.

### BC-00 — Establish current authority and choose the first bounded claim

- [ ] Record the actual received revision, migration state, core interfaces, and
  current applicable validation receipts without disturbing ongoing work.
- [ ] Inventory existing evidence/schema/registry/checker facilities and unresolved
  M11 gaps; incorporate the newer material reconciliation over older audit gaps.
- [ ] Compare the new T-cell translation lead and existing human evidence leads for
  exact material, accessible measurements, relevant context, and reproducibility.
- [ ] Write an explicit first-claim specification with endpoint, inputs, supported
  context, exclusions, unresolved obligations, and acceptance criteria.

Exit: one implementable, testable claim is selected, or a specific missing-source
diagnostic is recorded and a useful independent curation task is selected. Do not
broaden the claim to fit convenient data.

### BC-01 — Implement the minimal evidence and claim schema

- [ ] Reuse or extend existing types with material–observation correspondence,
  evidence roles, contextual applicability, and explicit uncertainty semantics.
- [ ] Add versioned canonical encoding, bounded strict import, dependency identities,
  and independent reconstruction for the selected scope.
- [ ] Separate translation acceptance from biological evidence assessment and existing
  human-use admission. Preserve unsupported, unknown, contradicted, and supported states.
- [ ] Verify rejected malformed records, swapped contexts, stale dependencies, and
  attempts to promote a citation or a model result into empirical support.

Exit: a minimal source-backed claim round-trips and reconstructs independently;
unsupported promotions fail without breaking supported conditional compilation.

### BC-02 — Freeze and reconcile the first source/data package

- [ ] Retrieve permitted source versions, corrections, exact data/code releases, and
  relevant sequence/material records; record reuse/access terms and checksums.
- [ ] Retain source-literal values plus narrow, auditable normalization; preserve
  ambiguous or missing material boundaries instead of repairing them silently.
- [ ] Independently review the sequence ↔ construct ↔ experimental material ↔ assay
  correspondence. Exact equality of two mirrors is not independent biological evidence.
- [ ] Provide bounded importers and offline reconstruction for the retained inputs.
  Explicitly distinguish offline reanalysis from repeating original-source extraction.

Exit: a compact, reviewable package reconstructs its documented claims. Missing
full-molecule authority remains missing; it cannot be filled from a related record.

### BC-03 — Reproduce observations and evaluate bounded predictions

- [ ] Reproduce selected published results with pinned code/environment and units;
  report deviations and distinguish observed, processed, fitted, and digitized values.
- [ ] Freeze fitting, model-selection, and evaluation partitions before tuning; group
  related sequences and repeated donor/study material to avoid leakage where applicable.
- [ ] Compare against simple baselines; evaluate relevant error and uncertainty
  calibration, not correlation alone. Record effective replication and measurement noise.
- [ ] Evaluate held-out studies/donors/contexts where available. If no suitable
  independent data exist, report reproduction or internal evaluation only.
- [ ] Define and test out-of-domain abstention. A prediction interval needs demonstrated
  coverage within a stated evaluation context; it is not a hard physical bound.

Exit: distinguish computational reproduction, internal model evaluation, and any
independent predictive evidence. Connect the result to the selected component and
observation interface; do not label an unrelated simulator as compiler validation.

### BC-04 — Integrate evidence into component selection and output claims

- [ ] Bind evidence to exact component/material/model versions and relevant target
  context; retain original source and runtime obligations through transformations.
- [ ] Add build-specific evidence assessment and manifest reporting with exact
  supported claims, assumptions, contradictions, and remaining gaps.
- [ ] Require fresh independent checking of evidence applicability and export claims.
  Stored PASS values and candidate-supplied authority cannot grant acceptance.
- [ ] Test synonymously changed sequences, changed chemistry, swapped donors/cell
  states/assays, altered observation units, and stale evidence as applicable.
- [ ] Preserve empirical-policy boundaries: stronger evidence is not automatic
  human therapeutic admission, and weak evidence is not incorrect software translation.

Exit: a real compiler output exposes the evidence applicable to that exact artifact
and refuses unsupported claims. Existing software and admission behavior remains intact.

### BC-05 — Expand coverage with complete implementations and composition evidence

- [ ] Curate a small set of complete published implementations before attempting a
  broad library assembled from unrelated fragments. Choose records by evidence quality
  and product relevance, not popularity or paper count.
- [ ] Record dependencies, recipients, localization, shared resources, timing, and
  required helpers. Separate individual-component evidence from combination evidence.
- [ ] Maintain a coverage matrix: payload family × cell/context × observable × material
  completeness × evidence/evaluation level. Make unsupported cells visible.
- [ ] Add negative/conflicting results with exact conditions. Lack of statistical
  significance is not proof of no effect, and absence of a publication is not failure.
- [ ] Expand within a documented applicability domain. A new modality, mechanism,
  environment, or composition needs corresponding checking and evidence work.

Exit: coverage grows through specific supported claims with explicit boundaries;
unmeasured combinations remain conditional or unresolved.

### BC-06 — Establish release and evidence maintenance

- [ ] Freeze versioned library releases with reviewed provenance and source/code/data
  pins; normal compilation must not depend on live internet retrieval.
- [ ] Add source correction/retraction/version-change review and invalidate affected
  assessments transitively when their authority changes. Do not silently overwrite history.
- [ ] Maintain a challenge suite for wrong material/context/units, missing dependencies,
  contradictions, and unsupported extrapolations alongside positive benchmark cases.
- [ ] Report claim coverage, exact-material linkage, reproduced analyses, independent
  evaluation, calibration, and correct abstention. Avoid a single biological-validity score.

Exit: a new evidence release is reviewable and reproducible; changing evidence cannot
silently preserve an obsolete claim. Scheduling any recurring automation is a separate
user decision; this document itself creates none.

## 9. Useful ways to improve coverage without a wet lab

- **Search from missing obligations.** Rank literature tasks by the exact compiler
  gap they could close: complete sequence, material identity, a time-course endpoint,
  recipient state, helper availability, or evidence for a combination.
- **Triangulate across sources without inventing joins.** Reconcile the paper,
  supplement, sequence deposit, and data accession; require explicit evidence that
  each refers to the same construct and experiment.
- **Use contradictory studies as tests.** Determine which contextual differences
  explain disagreement and where the current model must abstain.
- **Backtest across time or laboratories.** Where suitable independent datasets
  exist, fit using earlier studies and evaluate later studies or a different lab.
  Audit pretrained-model and shared-dataset leakage before calling a test independent.
- **Prioritize information value.** Prefer a source that resolves an important missing
  context or whole-material correspondence over another citation for an already
  documented phenomenon.
- **Request targeted scientific review when available.** A qualified remote reviewer
  can inspect an assay interpretation or material join without a wet lab. Prepare
  specific questions; do not send messages without the user's authorization.

## 10. Validation, storage, and progress reporting

Follow repository validation requirements for any implementation. Keep editing,
documentation, and non-build static checks local. OCaml/Rust compilation, native
executable tests, rebuilds, and packaging run on hosted CI or an already-authorized
remote environment by default. Local native compilation requires explicit permission;
avoid implicit builds through package managers. Do not treat an installed older native
library as validation of modified core source.

Use bounded downloads and explicit dataset inventories. Avoid fetching entire public
atlases when a targeted subset suffices. Preserve licenses and use permitted public
data; do not add credentials, identifiable patient data, or proprietary libraries.
Pin environments and inspect external analysis code before execution. Reuse existing
toolchains and keep generated datasets, caches, and build trees out of Git.

Each completed batch should record:

| Field | Required content |
| --- | --- |
| Task | BC ID and links to relevant M11–M16/LM dependencies |
| Scope | Exact claim, component/material, target context, observation and limitations |
| Authority | Source/data/model versions, extraction/review provenance and content identities |
| Implementation | Changed interfaces, schema/policy versions, revision and relevant artifact identities |
| Validation | Actual commands, tested revision/platform, receipts, positive and rejection coverage |
| Scientific status | What was reproduced, what was independently evaluated, and what remains assumed or unknown |
| Next action | The smallest meaningful remaining evidence or implementation gap |

Document-only edits need appropriate static checks, not native builds. Scientific
analysis and implementation changes require their own meaningful validation; do not
equate passing software tests with confirmation of scientific conclusions.

## 11. First-session deliverable and definition of success

The first new session should produce a verified baseline note, a bounded first-claim
specification, and a reviewed source inventory for the selected benchmark, then begin
the smallest implementation needed to reconstruct that evidence. The T-cell translation
dataset is the leading new quantitative candidate; the existing Roybal/Allen material
work remains a separate path toward secretion evidence and M11 completeness.

Do not wait for universal biological coverage before making useful progress. Equally,
do not declare the whole phase complete after ingesting one dataset. Mark each BC item
only at its actual exit, maintain the scope of the existing roadmap, and record an
unavailable source or missing evaluation set as a specific unresolved obligation.

A successful evidence-backed output should be able to state:

> This artifact implements this supplied design under these contracts. These exact
> materials and experimental observations support these particular claims in these
> contexts. These predictions have this evaluation history. These other behaviors,
> deployment assumptions, and empirical obligations remain unresolved.

That is the development objective. Public-data analysis can substantially improve
correctness, applicability, and coverage; it does not independently demonstrate the
behavior of newly manufactured payloads or arbitrary untested combinations.
