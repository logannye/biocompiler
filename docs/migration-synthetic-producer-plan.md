# Next synthetic producer migration batch

Implementation checkpoint, 2026-10-02: The direct implementation described below is now present in the synthetic producer batch. Source replay and peer review are complete; native and full product validation remain pending. This preserves the original pre-implementation audit; its starting-state observations are historical, and the language migration roadmap records current status.

Read-only source audit at `acf969ca` (2026-10-02). This plan changes no production
code and grants no native validation or completion claim. It follows the full
language migration roadmap, AGENTS.md and `docs/migration-synthetic-acceptance-plan.md`.
Historical digital fixtures remain software regressions; they add no organism
backend, molecular implementation, human admission or biological guarantee.

## Current boundary and evidence

The tree now contains complete synthetic domain/catalog codecs, independent
Synthetic_candidate_check and Component_assembly_check, private source/component
authority derivation, actual source/candidate/component execution and generic
composition checking. Preserve those checker implementations and their distinct
hosted evidence. Do not turn their private declaration witnesses into producers.
The acceptance batch at this revision still requires its complete hosted gates.

The producer operations remain Python. The current synthetic acceptance corpus
`d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331`
retains exactly 2,372 explicitly deferred calls:

| Operation | Retained calls | Authoritative source |
| --- | ---: | --- |
| generate_synthetic | 1,086 | synthesis/synthetic.py |
| _generate_synthetic | 1,144 | synthesis/synthetic.py |
| adapt_synthetic_components | 104 | synthesis/components.py |
| select_synthetic | 38 | synthesis/selection.py |

These are overlapping nested observations, not 2,372 independent requests.
Capture identity is
`9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29`.
All input/outcome documents and original producer corruption assertions must
remain. Selection record constructors are not yet part of the four-class
capture inventory; add their full imports, constructors, computed properties and
malformed cases rather than inferring that coverage from select_synthetic calls.

The installed services currently advertise canonicalize/validate-intent,
verify-lowering, verify/replay-architecture and compile/export-architecture only.
The Python client is `src/biocompiler/core_client.py`; native handlers are
`core/lib/service/service.ml` and `core/lib/producer_service/producer_service.ml`.
Native synthetic modules currently have no installed transport/public routing.

## Recommended coherent implementation batch: direct production and selection

Port all four deferred operations together, plus complete selection records.
This closes the deterministic source-to-candidate-to-component producer chain
without claiming PassManager, workflow, package or SDK cutover. It builds on the
new independent checkers and the already-retained complete producer observations.

1. Add domain `Synthetic_selection` with complete Alternative and Result codecs.
   Preserve schema/version/cost/profile/use labels and all derived fields.
   Alternative has exactly one of: ungenerated with nonempty error only;
   generated with nonempty unique constraint violations and no check; generated
   with no violations and an independent CheckResult. Bind check mechanism,
   observation_map and settings.synthetic_candidate to that exact candidate.
   Preserve candidate/strategy agreement; do not validate historical imported
   PASS by merely decoding it. Result requires native then de_morgan exactly
   once; every candidate binds request and configuration with only strategy
   replaced. Every check binds history, horizon and realization request.
   Validate recomputed gate_count/status/selected_strategy/outcome/count fields,
   including strict integer-versus-Boolean summary types. Retain Python numeric
   equality for dependency horizon comparisons while preserving exact integer,
   float and signed-zero representation in canonical content. Horizon accepts
   null or a finite nonnegative Python-real-equivalent number; huge integers
   that overflow math.isfinite remain rejected. Domain fingerprints use the
   legacy UTF-8 JsonArtifact profile; history/check dependencies use ASCII.

2. Add an independently implemented synthetic producer library, suggested
   `bioc_synthetic_producer`, depending on wire/domain/checker/realization_checker
   and zarith. This avoids expanding every existing architecture producer's
   dependency closure. New Dune/boundary inventory entries must explicitly permit
   producer-to-public-checker edges and continue forbidding all reverse edges.
   It must not access private Synthetic_provenance or Synthetic_component_authority,
   directly or through aliases. Those private modules remain checker-only.
   Share typed records, canonical/numeric leaves and component domain algebra,
   not graph generation or source-to-component correspondence algorithms.

3. Implement generator with separate internal `propose` and public `generate`
   operations corresponding to _generate_synthetic and generate_synthetic.
   Both preserve complete profile eligibility and declaration constructor rules;
   only public generate additionally rejects final proposal hard violations.
   Use explicit bounded graph tasks/memoization, never recursion proportional to
   source depth. Preserve both profiles and conjunction strategies, source and
   requirement maps, sorted locks and observations, literal numeric/unit content,
   exact witness lower endpoints, all memory declarations before responses,
   repeated-observation updates, signature versus memory.is_set asymmetry, and
   source-bearing rejection order. The complete recipe and generated identifiers
   are already specified in the tracked independent-acceptance plan. Implement
   that recipe independently here. A generator result is still only a proposal;
   generate must not unexpectedly execute history or require finite acceptance.
   Retain source location/function fields separately from formatted exception
   text and expose a typed UnsupportedBehavior analogue for the Python adapter.

4. Implement selection using propose, not public generate. Validate horizon,
   configuration and policy before materializing/checking history in the original
   order. Preserve native then de_morgan even when configuration initially says
   de_morgan, and retain two records when no AND yields equivalent graphs.
   Catch only unsupported generation into generation_error; ordinary schema,
   resource and runtime errors keep their actual rejection. Keep actual proposed
   candidate and ordered violations on hard_rejected alternatives. Freshly run
   Synthetic_candidate_check for every eligible alternative before ranking;
   never short-circuit after the first PASS. Rank PASS only, by gate count when
   requested and then fixed strategy order; minimize=none uses strategy order.
   Outcomes are selected, then unknown, then unsupported, then exhausted.
   Exhausted covers this exact pair only. Both complete checks/diagnostics and
   unselected candidates remain in the result. Hash exact supplied history with
   compact sort_keys/ensure_ascii=True JSON, matching realization dependencies.
   Candidate request/config fields must be preserved even when check outcome is
   FAIL/UNKNOWN. Recompute the winner rather than importing a selected label.

5. Implement adaptation from the accepted actual candidate, with a distinct
   public result containing registry, composition and complete acceptance.
   Select its exact catalog, freshly check request/candidate/history/horizon and
   require PASS before building declarations. Preserve original acceptance error
   text. Independently build runtime and initialization domains, event propagation
   through onset/any_contact only, complete required domain on every record and
   instance, exact out/in:index ports, all source/model/catalog/operator pins,
   parameter methods, fixed assumptions/guarantees, temporal timing, actual model
   attributes and every edge. Preserve the first non-null source in the candidate's
   ordered source map, source coordinates, default placement/lifetime and sorted
   complete requirement inventory. Keep registry/composition production separate
   from Component_assembly_check; an in-band altered actual witness must remain
   eligible for adaptation. Do not call the private expected-declaration module.
   Preserve the three-field SyntheticComposition interface; adaptation alone
   does not silently replace the separate linker/assembly acceptance API.

## Resource contract and exception boundaries

Give every public operation reduction-only work, request, derived-item and
publication limits, with one ancestor Work_budget for the whole operation.
Selection shares that allowance across both proposals, both checks, ranking and
complete result publication. Adaptation shares it across fresh acceptance, two
output-domain passes, full port/record construction and final publication.
Do not allocate a fresh 50M allowance for each strategy or nested checker.

Charge cached immutable input sizes before repeated canonical work. Reserve
prospective complete output skeletons/fragments before typed record constructors
copy them. Bound cumulative copied ports and operating coordinates against their
actual fanout product, not only node count. Bound source/response/ancestor unions,
retained descriptor/maps, task stacks and graph edges before expansion. Use
cached sizes or fixed bounded tree heights; Set/Map.cardinal inside every lookup
creates uncharged quadratic work. Preserve 16 MiB request versus 32 MiB evidence
ceilings and exact applicable UTF-8 versus ASCII accounting. A limit must remain
an explicit resource failure, never unsupported generation, exhausted search,
UNKNOWN, a partial selection or an accepted export. Keep parent exhaustion
recognition and failure-then-retry isolation.

## Required evidence for this batch

- Preserve all prior corpora untouched. Add a full producer corpus deriving from
  the existing 373-method baseline; retain every original assertion, nested call,
  two actual child processes, exact source locations, producer-patched mutant and
  complete document. Reclassify the exact 2,372 retained producer observations;
  independently inventory any additional selection constructor/property calls.
- Compare entire candidates, maps, catalogs, configs, registry/composition and
  acceptance records, full selection alternatives, properties and fingerprints.
  Do not settle for count/status equality or export the checker witness as the
  expected producer output. Both strategy candidates must remain distinct by
  configuration even when their mechanism graphs coincide.
- Retain all 17 generation, 15 temporal generation, 15 selection and 5 component
  adapter methods, plus their original pipeline/build/workflow callers. The two
  historical reference-adapter methods remain regressions; they are not a request
  to add a reference producer or nonhuman product scope to this batch.
- Add literal both-strategy reports for hard rejection, faulty De Morgan proposal,
  tie/no-AND, UNKNOWN, exhausted and unsupported; malformed summaries and numeric
  horizon counterparts; coherent in-band versus wrong actual candidates; shared
  signature/memory/repeated observations; complete temporal component parameters.
  Mutation tests corrupt a producer while independent checkers reject its output.
  Preserve original selector tests that monkeypatch _generate_synthetic: a fixed
  correct native generator cannot reproduce their injected bad proposal by itself.
  Provide an internal typed selection orchestration seam/functor whose production
  instance is fixed to the real generator. Test instances supply only the exact
  independently retained candidate/unsupported outcome for each pinned mutation;
  native hard checks, fresh acceptance and ranking still execute normally. Bind
  this counterpart to explicit original context/call identities. Do not expose
  callback import or a checker-result override over the wire, drop mutated calls,
  or broadly reinterpret differences as generator-policy normalization.
- Add exact/one-under local and parent resource tests, large fanout/lineage and
  deep alias bounds, complete result publication failure, repeated nested checks
  and independence builds with producer libraries unavailable to verification.
- Hosted Linux/macOS native validation and all discovered Python 3.11/3.14 shards,
  existing installed/integration/browser/reproducibility/aggregate checks remain
  required. Preserve source/tested/integrated tree identities and receipts before
  marking only these direct producer operations complete.

## Work that must follow, not disappear into Python orchestration

1. Expose direct realization/synthetic/assembly verification through an installed
   checker service that does not link producers, and generation/selection/adaptation
   through the core producer service. Version complete payloads/capability profiles,
   external authority, strict errors and resource reductions; extend SDK adapters
   with actual existing return classes and no Python fallback after rejection,
   crash or timeout. Keep each operation opt-in until installed parity is proven.

2. Port authoritative PassManager state/decisions from compiler/pipeline.py and
   passes.py: root admission, stages/schemas/targets, dependency and ancestor
   freshness, source/requirement links, scoped completion, obligation invalidation,
   candidate selection and changes during execution. Then port run_synthetic_pipeline
   and run_component_pipeline. Preserve their selected-config versus requested-config
   pins, regenerate-and-compare selected candidate, exact pass links and all
   post-pipeline link/behavior checks. Python may own storage and workflow invocation;
   it must not remain the authority deciding that these stages are complete.

3. Port SyntheticVerificationRequest/Record and check/explore/reduce workflows,
   Boolean enumeration, fixed suffix, selected FailureSignature and bounded
   reduction. Candidate and model modes deliberately differ in provenance claims.
   Fresh replay binds full independent operation authority, exact history or
   bounds, horizon, suffix, mode, selected failure and evaluation budget; it must
   compare the entire rebuilt result. Direct finite-history acceptance does not
   implement enumeration, reduction or workflow authority.

4. Port SyntheticHistory/BuildRequest/PackageFile/BuildManifest and canonical
   document production. Preserve nonempty ordered build history, explicit horizon,
   portable source paths, host/run metadata separation, exact file inventories
   (11 base files plus 4 component files), requested/selected configuration pins,
   toolchain and all stage/check documents. Python can retain archive transport
   and atomic writing, but fresh verification must reconstruct current authoritative
   content and compare exact manifest and archive bytes against independent request
   or trusted build identity before publication. Current verifier calls the Python
   builder; merely routing direct generation does not migrate this authority.

5. Complete all remaining roadmap layers: wider reference/molecular profiles,
   scientific-adapter and Python proposal interfaces, Studio architecture service
   integration, conversational draft/review, supported-platform distribution,
   rollback and deliberate default cutover. This synthetic batch is one necessary
   existing-workflow migration, not completion of LM-12/22/23/25/26/30/31 or the
   entire system migration.
