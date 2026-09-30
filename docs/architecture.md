# Architecture

biocompiler is a proposed compiler for converting an immune-cell engineer's intent into an exact digital specification of a DNA or RNA payload. Its organizing principle is **preservation of a behavioral contract through explicit intermediate representations (IRs)**.

The current repository implements the Python intent frontend, immutable intent and behavior graphs, checked intent-to-behavior lowering, an abstract reference evaluator, planning inspection, frozen build/realization requests, a checked pass manager, automatic combinational and temporal synthetic generation with locked operations, finite-trace realization checking against independent synthetic models, reproducible synthetic workflow packages, immutable typed component contracts, deterministic offline selection, and composition linking with provider/resource checks, independently checked whole-CDS reference construct assembly, and exact-reference DNA/RNA emission. A separate software molecular-design pipeline constructs and independently checks multi-region structural RNA specifications. The intent-candidate pipeline connects one authored product requirement to supplied CDS/architecture selection and automatic RNA assembly, retaining all unimplemented behavior. General molecular mechanism selection, biological simulation, characterized component libraries and human therapeutic-payload generation are not implemented. Physical manufacture, administration, and execution in a recipient cell are outside the compiler boundary.

The [v0.1 intent API](intent-api-v0.1.md) implements the authoring vocabulary: cell roles, scoped observations, expressions, actions, state, outputs, controllers, and communication. Python constructs an inspectable intent graph; molecular realization remains a later stage.

The intended therapeutic target is human biology with in-vivo engineering. The
[human target contract](human-target-contract-v0.1.md) adds explicit cell/state,
tissue/disease, population, host-dependency and operating-condition declarations.
`HumanTargetContext` retains them through frozen requests and strict import while
preserving legacy target identities. Evidence citations remain unvalidated and
planning/compilation retain an applicability diagnostic. This is M10.1's target
specification foundation; later contracts add delivery declarations while human
component admission and biological realization remain separate work.

M10.2 adds the [conditional secretion observation profile](human-behavior-contract-v0.1.md).
`HumanBehaviorRequest` retains the entire source build and binds its goal,
qualitative predicate and secretion rule to explicit measurements and lifecycle
requirements. It checks exact source coverage without rewriting or dropping
unresolved goals into the legacy Behavior IR. `check_secretion_trace` evaluates
the requested ranges and deadlines on supplied piecewise-constant observations;
it provides neither a biological model nor evidence of therapeutic efficacy.
The runtime input must be cell-accessible; the output assay remains an external
evaluation readout. General payload compilation remains unavailable.

M10.3 adds a [frozen deployment contract](deployment-contract-v0.1.md) around that
behavior request. It retains delivery-platform identity, exact human recipient
scope, modality, intracellular destination, exposure, expression timing and
unintended-recipient assumptions. Delivery targeting is separate from the
secretion recognition predicate. The independent deployment checker compares
declared expression availability against the behavior horizon, retains unknowns
and rejects unsupported co-payload dependencies. Compatible declarations do not
establish biological delivery or admit human mechanism selection.

M10.4 adds the [human acceptance contract](human-acceptance-contract-v0.1.md).
`HumanAcceptanceRequest` binds source behavior, deployment and prohibitions into
one frozen authority. Its supplied-trace checker conjoins required secretion
with healthy-context inactivity, background/peak ceilings, maximum activity bouts,
input-access loss recovery and latched external shutdown requirements. Missing
evaluator observations remain unknown. Healthy classification and shutdown never
silently override an active source rule; conflicts are explicit. Observability,
controllability and shutdown implementation remain unresolved evidence obligations.
No actuator, biological model or human payload admission is supplied.

The development-version rename uses the `biocompiler.*` schema namespace and
requires fresh builds and checks; see [migration notes](biocompiler-migration.md).
Historical validation records keep their original revision and evidence scope.

## Compilation layers

| Layer | Representation | Preservation obligation |
| --- | --- | --- |
| Python frontend | Declarative biological operations authored through the typed Python DSL | Separate design-time Python control flow from intended biological control flow. |
| Typed intent | Inputs, outputs, context, requirements, objectives, source locations | Preserve meaning, units, scope, identity, and the distinction between requirements and preferences. |
| Behavior | Logic, state, timing, memory, observables, acceptable variability | Preserve permitted observable trajectories and the operating assumptions under which they are required. |
| Mechanism | Molecular entities, interactions, host dependencies, observation mappings | Connect molecular behavior to the original observables; retain assumptions and uncertainty. |
| Components | Versioned component selections, interfaces, models, evidence | Satisfy assigned roles in the declared context; evaluate composition and shared dependencies. |
| Construct | Complete arrangement and relationships among encoded components | Encode every required mechanism and preserve boundaries, orientation, and regulatory relationships. |
| Molecular specification | Exact sequences plus relevant molecular features | Preserve construct identity and explicitly re-evaluate properties affected by encoding choices. |
| Deployment artifact | Specifications, manifest, source maps, provenance, verification record | Identify the precise build and preserve the conditions supporting its interpretation. |

An exact sequence does not establish exact cellular behavior. Artifact identity is checked directly; behavioral claims are conditional on context, models, assumptions, and supporting evidence.

## Module boundaries

| Module | Intended responsibility |
| --- | --- |
| `frontend` | Construct scoped, typed intent graphs from Python objects; retain source locations, ownership, and dimensional relationships. |
| `ir` | Immutable versioned intent, behavior, mechanism, component, construct and exact-CDS molecular schemas; strict JSON serialization and shared stage identifiers. |
| `semantics` | Types, units, context, requirement meanings, observational mappings, and refinement obligations. |
| `compiler` | Pass interfaces, stage ordering, diagnostics, dependency tracking, and provenance. |
| `synthesis` | Propose candidate mechanisms, component assignments, and encodings within supported design spaces. |
| `verification` | Independently check structural and behavioral obligations; retain unknown or failed outcomes. |
| `registry` | Versioned component interfaces, models, context applicability, and evidence references. |
| `models` | Quantitative model adapters and uncertainty representations. |
| `backends/dna`, `backends/rna` | Target capabilities, modality-specific lowering, and molecular specification emission. |
| `artifacts` | Deterministic serialization, manifests, provenance, and source maps. |
| `interop` | Future import/export adapters for external representations, such as SBOL and SBML. |

Candidate generation and acceptance are separate responsibilities. A search algorithm may propose an implementation; it cannot waive a requirement or treat missing evidence as a passing result.

## Source-driven molecular candidates

The [intent-candidate profile](intent-candidate-v0.1.md) is the first executable
bridge from a source product requirement to emitted RNA. `CandidateRequest`
freezes the original source request, supplied molecular library and separate hard
constraints/preferences. Its source may include the complete human behavior,
deployment and acceptance contracts. The original target and every source node
remain authoritative; unresolved therapeutic requirements stay visible.

The supported source subset contains one role, one secretion product and one
ongoing secretion action installed under a condition rule. Requirements extraction
identifies that product without pretending to implement the condition. The
compiler evaluates all bounded combinations of matching CDS bindings and supplied
architectures, checks literal fragment identities, translation and chemistry, then
ranks eligible options under the declared preference. The selected architecture
orders 5′ UTR, CDS, 3′ UTR and optional exact poly(A) parts. Whole-fragment source
ranges and consecutive destination ranges are derived automatically.

`bc.compile(CandidateRequest(...))` returns `CandidateCompilation` containing the
record, pass manager and pipeline result. The checked chain is source → product
requirements → bounded selection → exact parts → derived layout →
`PayloadMolecule`. Requirements and selection occupy the Behavior and Mechanism
stage slots with this narrow declared scope; they are not a biological dynamics
model. Independent validators reconstruct requirements, alternatives, parts,
layout and emitted bases against the frozen request. They do not use the
requirements lowerer, selector or emitter as acceptance oracles.

Completion means `product_cassette_structure`; therapeutic implementation is
`partial`, biological support is `unestablished` and human admission is
`not_admitted`. A human target remains human through the pipeline. The workflow
does not enter the generic software molecular-design admission path by changing
that target. A region-to-source map identifies product encoding or architectural
support; it supplies no proof of sensing, regulation, secretion or a therapeutic
goal. General `compile(BuildRequest)` remains unavailable.

The JSON record retains full authority, alternatives, exact parts, layout,
molecule, checks and tool versions. Fresh verification requires an independently
retained complete request; FASTA export reruns those checks and includes build
identity and scope labels. These records are separate from the existing `.bcb`
packages. Future quantitative models should bind to the selected part and sequence
identities through explicit observation maps. No sequence-to-rate inference or
empirical support follows from this structural bridge.

## Semantic preservation

Each future pass should consume a versioned IR and produce a new IR with:

- A mapping from output entities to input entities and original requirements.
- Its identity, version, configuration, and relevant dependency versions.
- Obligations introduced or discharged, diagnostic results, and unresolved assumptions.
- An explicit list of properties changed and analyses that must be rerun.

A lowering is acceptable only within its supported semantics. For example, a requirement about two signals on the same contacted cell cannot silently become a requirement about signals anywhere in the surrounding environment. Timing, persistence, spatial scope, and population-level versus individual-cell meanings must remain explicit.

Some properties admit exact checks, such as referential integrity or correspondence between a construct and emitted sequence. Behavioral refinement requires an observation mapping between lower-level model trajectories and higher-level requirements. A model-based proof, a numerical simulation estimate, and experimental support are different kinds of evidence and must remain separately labeled. None automatically proves behavior outside its stated context.

## Target selection and revalidation

DNA and RNA are distinct targets with different available mechanisms. Select the target before choosing mechanisms; emit target-specific molecular details later. A backend must reject an unsupported mechanism rather than approximate it without an explicit contract change.

Sequence optimization may preserve a protein sequence while changing modeled expression or stability. Therefore a later sequence change can invalidate higher-level analyses. Track these dependencies so the compiler reruns affected checks instead of equating sequence-level compatibility with behavioral equivalence.

## Build artifact

The eventual artifact should contain the complete digital molecular specification, an annotated construct map, source maps, a deployment manifest, immutable dependency identities, and the verification record. A packaging manifest describes the intended deployment package; it is not a manufactured formulation.

Reproducibility means that frozen inputs and tool versions reproduce the same digital artifact and analysis record. It does not imply that biological outcomes are deterministic.

See the [roadmap](roadmap.md) for implementation order and the [initial architecture decision](decisions/0001-explicit-contracts-and-staged-compilation.md) for constraints.

## Executable semantic foundation

The [behavior semantics](behavior-semantics-v0.1.md) define an execution profile independently of molecular implementations. `lower_to_behavior` normalizes supported intent, binds scalar design parameters, records source/requirement lineage and explicit runtime policies, and rejects unsupported semantics. `verify_lowering` checks correspondence. Behavior IR is immutable and serializable; its reference evaluator runs one engineered cell against supplied input histories, including same-time state propagation and internal deadlines.

The [toolchain contracts](toolchain-contracts.md) are design obligations for every later layer: target capabilities, observation mappings, required responses, independent synthesis/checking, composed resource models, host linking, construct partitioning, encoding invalidation and complete molecular artifacts. Future module docstrings point to these obligations. The reference evaluator is an oracle for language semantics; biological model adapters belong to `models`.

## Independent realization checking

The first [realization profile](realization-checking-v0.1.md) makes a subset of these obligations executable. Response contracts attach typed endpoints, contact scope, active/inactive ranges, and deadlines to installed behavior actions. Operating domains and versioned target contexts make assumptions inspectable. Observation maps bind explicit input fields and output endpoints to a synthetic Mechanism IR.

The candidate model executes independently of the behavior evaluator. A checker compares the two complete discrete-event traces and produces scoped outcomes, source-linked counterexamples, coverage, and dependency fingerprints. Empty coverage, missing assumptions, and unsupported semantics cannot silently become passing results. Evidence freshness is checked against all recorded dependencies before reuse.

This profile tests the preservation machinery without claiming a molecular mechanism has been realized. Full molecular model applicability, uncertainty propagation, measured resource competition, construct composition, and encoding preservation remain separate obligations. Declared component/provider contracts and shared reservations are now checked by the component linker; these declarations remain conditional assumptions. [ADR 0003](decisions/0003-independent-realization-checking.md) records this boundary.

## Implemented request and pipeline boundary

The [frozen request design](build-requests-v0.1.md) makes explicit bindings authoritative and separates source/behavior identity from the later contract/domain phase. The [pass manager](pass-manager-v0.1.md) admits only independently checked, fresh stage outputs. The [combinational synthetic profile](synthetic-profile-v0.1.md) has an automatic generator and a small versioned operation catalog. Separately [curated reference records](reference-benchmarks.md) establish exact CDS expectations; they are not molecular implementations of the synthetic graphs. The [component contracts](component-contracts-v0.1.md) and [offline linker](component-linking-v0.1.md) now support checked synthetic Mechanism → Components lowering. Interface meaning and domain inclusion, explicit providers, assumption cycles, shared capacities and dependency locks are checked independently. `run_component_pipeline` preserves source lineage and finite-history evidence in a `synthetic_components` scope. A [frozen construct request](construct-ir-v0.1.md) now fixes selected membership, reference ranges and expected layout before generation. The [independent construct checker](construct-checking-v0.1.md) validates a single whole DNA or RNA CDS and retains unknown delivered-molecule context. The [exact-CDS pipeline](exact-cds-pipeline-v0.1.md) now emits that selected reference spelling through a separate DNA or RNA backend and independently verifies nucleotide identity, linked-reference consistency, translation and source correspondence. Multi-molecule assembly, general molecular realization and human therapeutic-payload generation remain future work. The separate structural molecular-design profile below supports explicitly supplied RNA fragment/layout authority.

## Temporal synthetic builds

The [temporal synthetic profile](synthetic-temporal-v0.1.md) independently executes
sustained qualification, pulse/retrigger behavior and resettable memory. It keeps
cell histories separate from contact episodes and gives reset/set/expiry explicit
precedence. An internal onset event cannot escape into a continuous level readout.
The default combinational profile remains available. The [temporal component
profile](temporal-components-v0.1.md) adds explicit event/level interfaces and
executable operator attributes. Reconstruction reads locked component records,
ordered wiring and observation bindings, independently of the source mechanism;
the existing model runner then executes that reconstructed assembly.

[Synthetic workflow packages](synthetic-build-v0.1.md) stop at the checked
Mechanism stage by default and can explicitly include the further checked
Components stage. Their frozen authority includes realization request, supplied
history, horizon and generation configuration. Fresh verification requires an
independent complete request or expected build identity, reruns current tools and
compares every retained deterministic artifact. Runtime metadata stays outside
the canonical build identity. Archive inspection neither executes Python nor
fetches data; publication is atomic. These packages add no molecular output or
human implementation admission.

[Bounded digital selection](synthetic-selection-v0.1.md) evaluates two whole-program
conjunction strategies. Frozen hard constraints filter actual operators and graph
cost; every eligible candidate is independently checked before preference ranking.
The requested and selected configurations remain distinct, with exact alternatives,
rejection reasons and selection-policy dependencies retained in packages.

The [verification workflow](synthetic-verification-v0.1.md) exposes finite checks,
mixed cell/contact exploration and selected-failure reduction through JSON-only
commands. Complete operation authority binds the model, requirements, exact
history/time grid/suffix/horizon, mode and budgets. Fresh replay reexecutes current
checks against that authority. Historical reports, observed failures and incomplete
coverage cannot become accepted compilation merely by parsing or rehashing them.

These interfaces support the intended future source-to-molecular workflow: a
selected implementation must preserve required behavior and carry its evidence
and unresolved obligations downstream. Digital operator equivalence and software
costs supply no characterization of a molecular component or biological efficiency.

## Structural molecular design

The [molecular-design profile](molecular-design-v0.1.md) adds a separate checked
Components → Construct → Molecular path for one mature linear RNA software
specification. Components entry contains exact supplied sequence fragments and
their pins. Frozen layout authority fixes each source slice, destination interval,
region annotation, protein expectation and chemistry declaration. The construct
contains layout; emission proposes the sequence and complete structured molecule.
An independent checker reconciles every region and property with caller authority
and does not import the assembler or emitter.

The pass manager retains layout-only source links, current dependencies and
separate biological/material obligations. This path has no upstream intent or
synthetic-mechanism correspondence. A revised request can authorize a new
combination, while the original request and exact-reference contracts reject
unapproved substitutions. Its package retains all stages, source maps, chemistry,
independent checks and a nominal-design handoff, then reconstructs offline against
independent request/build authority. Structural completion and software fixture
labels cannot grant biological reference promotion or human admission.

## Reference construct entry and evidence

The [reference construct pipeline](reference-construct-pipeline-v0.1.md) starts from an independently checked Components root. It performs no substitute Intent/Behavior/Mechanism passes and makes no behavioral realization claim. A registered input policy checks current registry/reference identity and composition before the Components → Construct pass can run. Layout changes invalidate conditional composition and biological evidence; the narrow single-CDS profile rechecks composition, while empirical claims remain unresolved. Emitted-sequence identity is unresolved at the Construct stage and may be discharged only by the separate checked exact-CDS emission pass.

## Exact coding-reference emission

Molecular artifacts distinguish canonical sequence hashes from complete artifact/file hashes and preserve explicit known, unknown and inapplicable feature states. The checker compares emitted nucleotides directly to the frozen reference record and translated protein to its independently retained linked record. It does not import the emitter. Sequence optimization is disabled, and a matching protein cannot establish unchanged nucleotide identity or preserve expression/behavior evidence. FASTA and JSON export rechecks the current artifact against its authority; the [reference-build profile](reference-build-v0.1.md) packages those accepted records in a deterministic archive with explicit independent reconstruction and atomic publication.

## Implemented reference packages

`ReferenceBuildRequest` is the frozen authority for the supported component-root CDS profile. The manifest pins its request, all accepted stage records, retained references, selected components and current tools. The package retains feature/source maps, exact sequence, checks and unresolved full-payload/biology obligations. An upstream intent `BuildRequest` and behavioral realization are absent and explicitly unclaimed.

Canonical build identity excludes optional timestamps, machine labels and host locations. Core source paths are logical relative names. A strict canonical ZIP container supports identical relocated/repeated builds; fresh verification reconstructs the offline inputs against separately retained request/build authority and compares all records with current checks. Single-file atomic publication exposes either the prior complete archive or the new complete archive. See [reference builds](reference-build-v0.1.md).

## Bounded verification and independence

The verification layer keeps per-history model-conditional evidence separate from
exploration records. Boolean contact exploration states its object IDs, observation
fields, variable snapshot times, fixed suffix and finite horizon. Completion means
that declared finite space was visited; it does not cover arbitrary real-valued
times, unbounded object populations or biological dynamics. Seeded adversarial
histories and deletion-based counterexample reduction retain UNKNOWN outcomes and
the chosen failure signature.

The reference evaluator, synthetic runner and exact-reference checker have
independently exercised execution paths. Shared typed declarations and policy
schemas are documented explicitly, and mutation tests check intended rejection
signatures. Passing response evidence requires exercised active and inactive
deadlines with no unfinished episodes. See [exploration](verification-exploration-v0.1.md),
[semantic matrix](semantic-regression-matrix-v0.1.md) and
[independence audit](verification-independence-v0.1.md).

## Molecular correspondence and payload readiness

The [molecular implementation contract](molecular-behavior-v0.1.md) freezes requested observations and responses against the current realization request, selected components, construct and exact molecular artifact. Its checker reruns source lowering and independent molecular checks, requires complete observation/response correspondence, and retains context, typed parameter provenance and distinct evidence categories. A passing linkage result describes that correspondence. The biological result remains UNKNOWN, or UNSUPPORTED for a proposed unimplemented adapter/profile. No synthetic model is assigned to the FAP CDS.

[Whole-molecule readiness](payload-profiles-v0.1.md) has separate immutable molecule/reference records for narrow mature linear RNA, linear DNA and circular-plasmid profiles. The checker requires a separately supplied authority fingerprint, exact retained source/review bytes, independent sequence extraction, whole-molecule feature coverage and explicit topology/chemistry. These results do not enter the exact-CDS pipeline or authorize a complete-payload build. The example records are nonfunctional software fixtures; no complete biological reference is promoted.

Planning and general therapeutic compilation report source-linked missing obligations for quantitative curves, continuous integration, interval-valued intent, population communication, spatial behavior and feedback. They preserve these authored requests without silently assigning an approximate execution model. The partial intent-candidate profile retains such obligations while implementing only its supported product-cassette structure. The [M9 evidence review](m9-evidence-review.md) identifies the scientific and source inputs needed for subsequent adapter and reference-promotion work.

## Human-profile use admission

The [M10.5 admission policy](human-admission-v0.1.md) is shared by planning, registry selection, fresh implementation verification and export. Its immutable request binds target, intended use, boundary and selected component records; the assessment preserves declared evidence categories and limitations. The current policy admits no human therapeutic profiles. Generic targets can request labeled software workflows only; human contexts cannot bypass admission by requesting software use. The partial research-candidate workflow retains human requirements and admission refusal while emitting a structurally checked cassette; it grants no implementation eligibility. Supplied human-contract observations may pass their finite checks without granting implementation eligibility.

Independent composition, construct and molecular checks rerun admission even for exact manually supplied locks. Synthetic generation and direct realization checks reject human targets. Reference export and archive reconstruction check use before accepting a build. Molecular/synthetic artifacts, reference manifests and summaries carry fixed software-use labels; FASTA carries equivalent header fields. Policy identities enter verification, pass-manager and package dependencies. Matching saved hashes or PASS labels cannot replace fresh current checks.

## Proposed profile cases and completion scope

[M10.6](human-profile-v0.1.md) connects the human target, behavior, deployment, acceptance and admission layers in ten inspectable request cases. The proposed first family is reversible conditional secretion with an RNA deployment declaration; its precise human context, cue/product identities, delivery and biological bounds remain unresolved. Each case reports declaration compatibility, finite-trace acceptance, admission refusal, compilation unavailability and missing evidence separately.

The example-only trace enumerator records an ordered candidate inventory, budget, checked results and unchecked count. Exhausting a candidate set or budget cannot establish global infeasibility; adding a passing observation trajectory can supply a software witness. A separate explanation establishes only an empty intersection of simultaneous active/background rate constraints under an explicit healthy-context condition. Neither path supplies a molecular implementation or establishes biological reachability. Saved evidence is compared with fresh results from current example authority; no compiler backend or admitted biological profile is added.
