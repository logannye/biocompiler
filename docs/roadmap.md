# Development roadmap

This roadmap turns the current semantic foundation into a reproducible compiler path, using **exact, published coding-sequence (CDS) references** for the first molecular benchmarks. Milestones below are planned work, not implemented capabilities. Task IDs are stable so implementation PRs can cite them and mark individual items complete.

Baseline reviewed on 2026-09-29 at commit `03db52381beeb3bfbf64bf51da281935d638b98e`:

| Boundary | Current implementation | Next responsibility |
| --- | --- | --- |
| Python → Intent | Typed authoring, immutable graphs and planning inspection | Freeze authoritative build inputs and elaboration provenance |
| Intent → Behavior | Checked lowering, versioned Behavior IR and reference execution | Verify against the requested bindings; strengthen independent semantic checks |
| Behavior → Mechanism | Separately authored synthetic candidates and an independent runner/checker | Generate candidates automatically for an explicit supported profile |
| Mechanism → Components | Placeholder component/registry modules | Lock implementations, interfaces, dependencies and composition contracts |
| Components → Construct | Placeholder | Preserve molecular membership, order, orientation, boundaries and relationships |
| Construct → Molecular specification | DNA/RNA placeholders | Emit and independently check exact scoped sequence artifacts |
| Molecular specification → Package | Placeholder manifest/pass manager | Package locked inputs, source maps, scoped checks and reproducible identities |

`compile()` still raises `CompilationUnavailableError`. The existing synthetic checking example constructs its candidate manually. No molecular lowering or sequence emission is implemented by adding this roadmap.

## Development strategy and first deliverables

Two tracks share build identities, pass contracts and artifact infrastructure:

1. **Semantic correctness:** automatically lower a small Behavior profile into versioned synthetic components and check it independently against abstract histories.
2. **Molecular reference fidelity:** resolve an explicitly selected published implementation and reproduce its exact CDS through component, construct, molecular and packaging stages.

A synthetic signal graph is not a molecular implementation of a CAR. Connecting the tracks requires an explicit implementation contract and observation mapping; passing either track alone does not supply that connection.

The initial molecular reference is the patent-disclosed, study-associated murine FAP-CAR set: **WO2022081694A1, SEQ ID NO:2 (coding DNA), NO:3 (coding RNA), NO:1 (protein)**. These disclosures are available, but repository fixtures still need extraction, independent review and version locking. They specify coding regions, not complete delivered RNA molecules. See the [reference benchmark plan](reference-benchmarks.md) for sources, promotion gates and pending full-payload candidates.

The first molecular milestone should report **“exact CDS reference reproduced”** and emit its verification record. A later complete-payload profile must additionally resolve regulatory regions, molecule boundaries, relevant chemistry and every obligation required by that profile.

High-level intent generally permits many sequences. Exact reproduction requires a frozen intent **plus pinned implementation choices, component versions and tool semantics**. The compiler must record those choices rather than implying that a therapeutic goal uniquely determines a nucleotide string.

## Milestone order

| Milestone | Depends on | Reviewable result |
| --- | --- | --- |
| M0. Curate the reference benchmark | Source review | Independently frozen expected DNA, RNA and protein records |
| M1. Freeze build authority | Existing Intent/contract/context schemas | BuildRequest/BoundIntent and binding-verification regression |
| M2. Enforce pass contracts | M1 | Checked pass manager with transitive invalidation |
| M3. Generate a synthetic realization | M1–M2 | Automatic lowering for one declared semantic subset |
| M4. Link versioned components | M2; M3 for synthetic integration | Checked interfaces, providers, applicability and resource accounting |
| M5. Assemble explicit constructs | M0, M4 | Immutable Construct IR with validated sequence layout |
| M6. Emit exact CDS artifacts | M0, M5 | Independently verified DNA-CDS and RNA-CDS outputs |
| M7. Package reproducible reference builds | M1–M2, M6 | One-command reference build and portable manifest |
| M8. Broaden independent verification | Begins with M1; gates each relevant milestone | Adversarial, generated and bounded-exhaustive checks |
| M9. Connect molecular behavior and expand | M3–M8 and suitable models/reference data | Evidence-backed realization profiles and complete payload targets |

M0 can proceed alongside M1–M2. M8 is continuous work, not a final testing phase. No milestone requires implementation of the entire authoring language.

## M0 — Establish independently curated sequence references

**Primary locations:** `data/`, `registry/`, `tests/` under their existing repository/module roots; detailed record design in [reference-benchmarks.md](reference-benchmarks.md). New paths and schema names below are proposals.

- [ ] **M0.1** Add a small reference manifest schema: stable reference/variant ID, source locator, artifact class, retrieval date, source hash, normalized sequence hash, normalization log and review status.
- [ ] **M0.2** Independently curate FAP-CAR SEQ IDs 1–3, preserving original source text and declared DNA/RNA/protein alphabets. Record the paper association separately from exact experimental-material identity.
- [ ] **M0.3** Specify allowed normalization, genetic code, reading frame and terminal-stop conventions. Resolve extraction discrepancies against the source; never silently repair them.
- [ ] **M0.4** Freeze expected DNA, RNA and protein records independently of the emitter. Check source DNA/RNA T↔U correspondence and translation to the separately curated protein.
- [ ] **M0.5** Give fixtures explicit states such as candidate, curated and blocked, with machine-readable missing information. Keep synthetic fixtures separately identified.
- [ ] **M0.6** Define storage and provenance policy for small reviewed references versus large source files/generated output. Record source terms and provenance without introducing a runtime network dependency.

**Acceptance:** a reviewer can trace every expected base to a specific disclosed record. Tests can distinguish exact nucleotide identity, protein consistency and artifact completeness. Source ambiguity blocks fixture promotion, rather than becoming a compiler-selected base.

## M1 — Freeze authoritative build inputs and reproducible elaboration

**Primary modules:** `frontend/`, `compiler/workflow.py`, `compiler/behavior.py`, `artifacts/provenance.py`, `ir/serialization.py`, `semantics/`.

- [ ] **M1.1** Define an immutable, versioned `BuildRequest` and/or `BoundIntent` containing the frozen intent, explicit overrides, resolved defaults, target context, required artifact scope, implementation constraints and preferences. Bind realization contracts and operating domains in a later immutable request phase as described in M1.8.
- [ ] **M1.2** Make resolved bindings authoritative inputs to lowering and verification. Output-reported bindings must agree with this input; they cannot establish their own authority.
- [ ] **M1.3** Separate user-selected constants, compiler-selected alternatives, measured/calibrated parameters, uncertain quantities and runtime observations. Preserve units, provenance and allowed variation for each category.
- [ ] **M1.4** Record authoring source and dependency identities, explicit external inputs and the resulting graph. Build from the frozen graph without re-executing authoring Python. Capture nondeterministic inputs when used; source text alone is insufficient for reproducible elaboration.
- [ ] **M1.5** Preserve the distinction between design-time Python control flow and explicit cellular runtime operators. Explain it in diagnostics and examples.
- [ ] **M1.6** Specify canonical serialization, content identities, schema compatibility and migration/rejection policy. Distinguish semantic identity from file-location and timestamp provenance so workspace relocation does not alter sequence bytes.
- [ ] **M1.7** Plan compatibility for `BuildProfile`, `RealizationPlan`, `lower_to_behavior`, verification and eventual `compile` entry points. Keep the current unavailable-compilation boundary until a supported artifact profile exists.

- [ ] **M1.8** Freeze contract binding in two phases: freeze source/bindings, then derive and verify Behavior against that authority; subsequently freeze a realization request containing that exact Behavior identity, its response contracts and operating domain. Existing BehaviorContract records refer to a Behavior fingerprint. Preserve the upstream request identity without creating a circular hash dependency or mutating an accepted request.

**Acceptance:** a request selecting value `1` rejects a Behavior artifact whose node and binding manifest were both changed to `9`. An explicitly requested override to `9` succeeds. Unknown, missing and incorrectly typed bindings produce source-linked diagnostics. Mutating caller-owned inputs after freezing cannot change the request.

## M2 — Make preservation obligations an enforced pipeline

**Primary modules:** `compiler/passes.py`, `compiler/pipeline.py`, `verification/evidence.py`, `artifacts/provenance.py`.

- [ ] **M2.1** Extend pass contracts with input/output schemas, semantic/profile versions, target applicability, consumed requirements and assumptions, introduced/discharged obligations, source correspondence and observation mappings.
- [ ] **M2.2** Record pass/tool/configuration identities, dependency fingerprints, changed properties and invalidated analyses. Build an explicit dependency graph, including upstream request and registry/model identities.
- [ ] **M2.3** Enforce pass ordering and target legalization: every operation admitted to a completed stage must be supported by that destination profile. Preserve actionable diagnostics for remaining operations.
- [ ] **M2.4** Separate candidate generation from acceptance. Require appropriate independent checks before promoting a candidate to the next accepted stage; an optimizer cannot weaken requirements to obtain success.
- [ ] **M2.5** Make freshness validation automatic before evidence reuse or artifact acceptance. Propagate invalidation transitively through components, layout, encodings, context and models.
- [ ] **M2.6** Define statuses for partial designs, complete artifacts within a requested scope, and individual `pass`/`fail`/`unknown`/`unsupported` checks. An exact CDS artifact may be complete as a CDS while full-payload and biological obligations remain unresolved and visible.
- [ ] **M2.7** Define deterministic tie-breaking and recorded search seeds/configuration. Distinguish “no candidate found within this search” from demonstrated infeasibility. Add persistent caching only after dependency and invalidation behavior is tested.

**Acceptance:** missing passes/providers and unsupported operations cannot disappear from a completed profile. A changed dependency prevents reuse of stale evidence, including changes several passes upstream. Source correspondence alone cannot discharge behavioral refinement.

## M3 — Generate the first synthetic mechanism automatically

**Primary modules:** `synthesis/`, `compiler/`, `ir/mechanism.py`, `models/synthetic.py`, `verification/realization.py`.

- [ ] **M3.1** Publish a minimal supported profile: one cell role, explicit observations, a combinational condition and a contracted abstract output over a bounded history. Specify input/output meaning, identity, contact scope, initialization and observation mapping. Require authored response bands and deadlines; do not invent quantitative guarantees during lowering.
- [ ] **M3.2** Implement Behavior → synthetic Mechanism lowering for that profile, retaining requirement IDs and source maps. Generate the candidate rather than constructing it manually in the example.
- [ ] **M3.3** Run the existing independent model runner and realization checker on the generated candidate. The runner must not delegate its semantics to the Behavior evaluator.
- [ ] **M3.4** Preserve contacted-object binding. Same-object conjunction and conjunction over different objects must remain distinct in generation and checking.
- [ ] **M3.5** Add temporal support only through separately specified operators and acceptance tests. The current synthetic `delay` delays both edges with inertial cancellation; it is not equivalent to `held_for`. Test rapid fall/re-rise histories before introducing sustained-input lowering.
- [ ] **M3.6** Extend supported patterns incrementally for pulses, simultaneous events, reset precedence and repeated triggers, with explicit startup/rearming semantics. Reject unsupported timing/state operators until their profile exists.

**Acceptance:** a supported Behavior program produces a candidate without manual graph construction and passes exercised finite-history contracts. Silent, late, wrong-object and wrongly scoped candidates fail. Unsupported temporal operators report diagnostics rather than being approximated.

## M4 — Select and compose versioned components

**Primary modules:** `ir/components.py`, `registry/`, `semantics/`, `models/`, `synthesis/`, `verification/`.

- [ ] **M4.1** Define immutable component records with stable versions/content hashes, typed interfaces, implementation roles, supported targets, model identities, assumptions/guarantees and evidence references. Distinguish a sequence-only reference from a dynamically characterized component.
- [ ] **M4.2** Express interface meaning, units, role/contact scope, compartment, timing, initialization and parameter provenance. Do not infer compatibility from matching labels or numeric ranges alone.
- [ ] **M4.3** Check required operating domain ⊆ supported component domain and producer guarantees ⊆ consumer accepted inputs, using a deliberately small first contract language. Report unknown when inclusion cannot be established.
- [ ] **M4.4** Resolve dependencies to explicit providers: encoded here, another declared payload, host, external supply or unresolved. Detect missing/ambiguous providers and circular justifications of assumptions.
- [ ] **M4.5** Account for shared resource reservations across the composition, including units, provider capacity, reuse and relevant lifecycle. Define how unknown capacities are represented; absence of a measurement is not unlimited capacity.
- [ ] **M4.6** Lock registry/model/reference versions before acceptance; make resolution deterministic and runnable offline. Record alternatives considered and why a selection satisfies hard constraints before ranking preferences.
- [ ] **M4.7** Populate a minimal synthetic component catalog for M3 and a separately classified FAP CDS reference component for M5–M6. Encode only supported sequence identity/structure claims for the latter until a molecular behavioral contract exists.

**Acceptance:** compatible compositions link; incompatible meaning/scope/compartment, missing providers, unsupported domains, resource over-allocation and stale versions are rejected or explicitly unresolved. Circular assumption chains cannot establish their own guarantees.

## M5 — Preserve selected implementations through Construct IR

**Primary modules:** `ir/construct.py`, `compiler/`, `verification/`, `artifacts/provenance.py`.

- [ ] **M5.1** Define immutable, versioned Construct IR: molecule IDs, artifact class, components, order, orientation, junctions, boundaries, regulatory relationships, dependencies and source/requirement correspondence.
- [ ] **M5.2** Define coordinate and orientation conventions centrally, including zero/one-based indexing, inclusive/exclusive ends, strand interpretation and sequence normalization. Validate exact membership and coverage.
- [ ] **M5.3** Start with a single reference CDS construct. Preserve that boundary explicitly; do not invent a promoter, UTR, circularization scaffold, poly(A) tail or plasmid backbone to make it appear complete.
- [ ] **M5.4** Permit subcomponent features only where their boundaries are sourced or separately reviewed. A whole CDS can initially be one pinned component; a domain diagram is insufficient to invent exact junction coordinates.
- [ ] **M5.5** Independently check that assembly contains each required component with the selected version, orientation, order and frame, and no unexplained bases. Report intentional overlaps and junction choices explicitly.
- [ ] **M5.6** Represent multiple molecules and co-payload dependencies in the schema, while initially rejecting unsupported multi-molecule assembly. Record same-cell coexistence as an assumption, not a consequence of sharing a manifest.
- [ ] **M5.7** Treat layout changes as semantic changes where appropriate and invalidate affected composition/behavior evidence.

**Acceptance:** swapped components, missing segments, reversed orientation, off-by-one boundaries, wrong molecule membership and unsupported junctions are detected. Every emitted region has an origin, including any explicitly introduced sequence.

## M6 — Emit and independently check exact coding sequences

**Primary modules:** `ir/molecular.py`, `backends/dna/`, `backends/rna/`, `verification/`, `registry/`.

- [ ] **M6.1** Define narrow DNA-CDS and RNA-CDS output profiles, separate from complete DNA constructs or complete mRNA/circRNA payload profiles. Record reference identity and scope in the molecular artifact itself.
- [ ] **M6.2** Emit the selected reference spelling deterministically through Construct IR. Keep codon/sequence optimization disabled in reference-reproduction mode unless an explicit new mode and comparison contract are introduced.
- [ ] **M6.3** Validate alphabet, orientation, length, feature coordinates, frame and termination conventions with an independent artifact checker. Reconcile emitted sequence with both Construct IR and the separately curated expected record.
- [ ] **M6.4** Check exact DNA against source SEQ2, exact RNA against source SEQ3, and translation against source SEQ1. T/U conversion is a consistency check, not evidence that a delivered DNA medicine and an mRNA medicine are interchangeable.
- [ ] **M6.5** Return explicit fields for known, unknown and inapplicable molecular features. A CDS record must not imply known cap, nucleotide modifications, transcript ends, regulatory context or full-molecule topology.
- [ ] **M6.6** Define identity-preserving file export, for example FASTA plus a structured molecular specification. Line wrapping may change file bytes; canonical sequence identity must remain separately defined.
- [ ] **M6.7** Attach any future encoding optimization to a change record and invalidation policy. Protein preservation alone cannot preserve all expression, structural or behavioral analyses.

**Acceptance:** exact normalized nucleotide outputs match independently frozen references. A synonymous substitution fails exact-reference equality even if translation passes. Missense changes, truncation, wrong alphabet, frame errors and incorrect reference selection fail their respective checks.

## M7 — Package one reproducible reference build

**Primary modules:** `artifacts/manifest.py`, `artifacts/provenance.py`, `compiler/workflow.py`, `cli.py`, `examples/`, `.github/workflows/ci.yml`.

- [ ] **M7.1** Package the BuildRequest, all accepted IR identities, locked components/models/tools, exact molecular records, feature maps, source maps, selected alternatives, checks and unresolved obligations.
- [ ] **M7.2** Separate deterministic artifact/build identity from run metadata such as timestamps, absolute source paths and machine labels. Define what byte-for-byte reproducibility covers.
- [ ] **M7.3** Expose an explicit reference-build API/CLI/example without suggesting that arbitrary existing intent plans now compile. Publish which request/profile combinations succeed and preserve diagnostics for unsupported requests.
- [ ] **M7.4** Validate imported artifacts strictly, including schema/version, referenced IDs, payload hashes and evidence freshness. Inspection must not execute authoring code or fetch unpinned dependencies.
- [ ] **M7.5** Ensure a failed build cannot leave a success manifest or partially overwrite a previous accepted result. Make output publication atomic and reproducible from the frozen request.
- [ ] **M7.6** Add hosted CI reference builds on the supported Python matrix. Verify offline reconstruction and relocation/repeated-run determinism; record tested revision/platform and retain useful failure evidence.

**Acceptance:** one documented command resolves the pinned reference, traverses the accepted component/construct/molecular stages, emits an exact CDS and manifest, and explains every remaining biological/full-payload obligation. A clean environment reproduces the same canonical identities. No claim of biological refinement is fabricated to complete the package.

## M8 — Strengthen independent verification throughout

**Primary modules:** `tests/`, `verification/`, `models/`, `semantics/evaluator.py`; retain the existing tests and hosted release checks.

- [ ] **M8.1** Add the M1 binding-tamper regression first, including an independently specified expected request. Extend tamper tests to contexts, contracts, reference choices and evidence dependencies.
- [ ] **M8.2** Maintain a semantic regression matrix for same/different contacted objects, sustained/transient inputs, simultaneous/ordered events, memory resets/expiry and repeated triggers. Include boundaries between snapshots and exact deadlines.
- [ ] **M8.3** Generate adversarial histories with deterministic seeds and minimal counterexample reduction. Cover rapid oscillation, contact removal/reappearance, startup-active inputs and incomplete observation histories.
- [ ] **M8.4** Add metamorphic checks where semantics permit them: consistent object renaming, serialization round trips, reordered independent declarations and redundant unchanged snapshots that introduce no event. State the preconditions for each equivalence.
- [ ] **M8.5** Add bounded exhaustive checking for a small finite profile. Record explored bounds, state/input space and coverage separately from ordinary finite-trace results.
- [ ] **M8.6** Audit independence between transformations and validators. Use separately specified expected behavior/reference artifacts so a shared normalization bug cannot validate itself. Avoid duplicating entire runtimes merely to add another nominal checker.
- [ ] **M8.7** Mutation-test the obligations that matter: incorrect bindings, scope changes, silent responses, shifted deadlines, stale dependencies, wrong component order and changed bases must be caught by the intended check.
- [ ] **M8.8** Keep exact structural checks, model-conditional checks and empirical evidence separately reported. Exercise required active and inactive responses; unexercised coverage must not become a passing realization result.

**Acceptance:** each milestone has a focused positive case and failure cases that would catch plausible compiler bugs. Passing a bounded suite reports its bounds; it does not claim correctness throughout an unexamined biological operating domain.

## M9 — Connect molecular behavior and expand beyond CDS references

**Primary modules:** `models/`, `semantics/`, `synthesis/`, `registry/`, both backends and `interop/` as needed.

- [ ] **M9.1** Add an explicit molecular implementation contract connecting a supported therapeutic Behavior pattern to selected mechanisms/components and their observation mapping. Record applicability, parameters, evidence and unestablished claims. Do not attach a synthetic delay/gate model to a CAR by analogy alone.
- [ ] **M9.2** Introduce calibrated biological adapters only for concrete supported contexts. Separate model validation, uncertainty, parameter fitting and observed therapeutic outcomes from sequence identity.
- [ ] **M9.3** Promote a full-mRNA or complete DNA/vector reference only after the [reference promotion gates](reference-benchmarks.md#extending-to-a-complete-payload) pass. Add modality-specific completeness rules and actual delivered-molecule boundaries.
- [ ] **M9.4** Add quantitative tracking, continuous dynamics, uncertain/population responses, spatial behavior and feedback as separately versioned semantic/model profiles. Keep the broad authoring API available with explicit unsupported-compilation diagnostics.
- [ ] **M9.5** Introduce optimization, search over alternative implementations and SBOL/SBML interoperation when concrete use cases justify them. Preserve hard requirements, context, source correspondence and revalidation obligations.

**Acceptance:** each additional feature has defined semantics, a supported realization profile, independently checked output and an explicit evidence boundary. Full-payload compilation has its own completion contract; a CDS-only success is never silently promoted.

## Suggested implementation PRs

1. **Authoritative request and binding verification:** M1 plus M8.1; freeze current gap as a regression and close it.
2. **Reference curation:** M0, in parallel with PR 1; review expected artifacts before emitter implementation.
3. **Checked pass manager:** M2; enforce dependencies and status/freshness rules.
4. **Automatic synthetic candidate generation:** M3.1–M3.4 plus the minimal M4 synthetic catalog; defer temporal operators until independently specified.
5. **Component contracts and linker:** remaining M4, with domain/provider/resource failures tested.
6. **Construct and exact CDS backends:** M5–M6, using the reviewed FAP references and independent mutation tests.
7. **Reproducible packaged reference build:** M7 and the applicable M8 gates; document one-command behavior and remaining obligations.
8. **Molecular behavior adapters and full-payload references:** M9, each as a separately scoped change.

For each PR, update task checkboxes only for completed work, list relevant acceptance evidence, preserve existing tests and record the tested revision/platform. Documentation-only planning does not complete an implementation milestone. Follow the [native build policy](../AGENTS.md#native-build-storage) if Rust is introduced; local native builds remain opt-in.

See [architecture](architecture.md), [Behavior semantics](behavior-semantics-v0.1.md), [realization checking](realization-checking-v0.1.md) and [cross-layer contracts](toolchain-contracts.md) for the governing designs.
