# Architecture

The [product vision and integration roadmap](product-vision-and-integration-roadmap.md)
defines the shared core for standalone researchers and future AI-directed labs,
including boundaries between compilation, experimental execution, and model
updates. It adds integration design targets without changing the supported
profiles or their acceptance scope described here.

The new [`biocompiler.policy` authoring family](policy-language-v0.1.md) supplies
layer 3's expressive declarative documents, builders, structural checks,
inspection, serialization and explicit compiler submissions. It is independent
of the current executable Intent/Behavior families: importing or freezing one of
these documents grants no semantic, realization or acceptance result. Later
OCaml layers must independently validate the full declared profile before
lowering it. Layer 1 Studio and layer 2 conversational integration are deferred.

The accepted target implementation uses TypeScript for Studio, Python for
authoring/orchestration/scientific exploration, and OCaml for the compiler,
independent checking and canonical emission. See [ADR 0007](decisions/0007-language-boundaries-and-ocaml-core.md)
and the [session migration roadmap](language-migration-roadmap.md). Studio now
builds from strict TypeScript. Production compiler and acceptance paths remain
Python; the experimental OCaml core provides canonicalization, structural
intent validation and explicit independent source-to-Behavior correspondence.
Internal typed request and coordinate layers prepare architecture checking. A separate
`bioc_semantics` library implements per-role reference execution for hosted
conformance; it is not linked by the checker service or standalone verifier. Its
execution records and numeric primitives are part of the declared trusted base.
Channels are supplied observation/action endpoints at this layer; coupled transport
still requires its own architecture implementation and validation.
The domain layers and preservation obligations below continue to govern both.

The current product interface is **therapeutic program design → corresponding
payload RNA sequences for human immune cells engineered in vivo**. The
[RNA architecture profile](payload-architecture-v0.1.md) connects complete source
Behavior programs, supplied composite component contracts, bounded architecture
and RNA-partition selection, recipient roles and the existing construction engine.
Its independent checker reconstructs source meaning and selected templates before
RNA export. This contract-conditional code path requires no biological evidence;
whether the supplied parts fulfill their contracts remains unresolved. The
broader DNA utilities and earlier milestones described below are infrastructure
and historical context, not an additional current product target.


The additive persistent pipeline session source now keeps one native manager in
one Core process, with explicit original-authority commands and a shared lifetime
budget. Python transports framed commands and immutable byte receipts; serialized
records cannot install acceptance. Fixed synthetic/component providers and
partial logical-error state remain native. Independent Verify has no session
entry point or producer dependency. This source checkpoint still requires hosted
validation and public typed manager/callback integration before production use;
see the [migration roadmap](language-migration-roadmap.md).

biocompiler translates supported high-level therapeutic intent into exact RNA payload specifications for human immune cells engineered in vivo, conditional on supplied executable component contracts and sequence templates. Python is the implemented authoring language; natural-language authoring is a future frontend to the same explicit requirements. Its organizing principle is **preservation of a behavioral contract through explicit intermediate representations (IRs)**. Each molecular choice remains traceable to the intended response, its deployment context, declared assumptions and any separately supplied evidence.

**Human in-vivo immune-cell deployment is the sole product target.** Non-human
organism compilation, sequencing and general cell-engineering workflows are out
of scope. Human source experiments are supporting evidence with their own actual
cell and assay context; that context never substitutes for the deployment target.
Component origin is separate from recipient biology and requires its own
provenance and human-context applicability assessment.

The current repository implements the Python intent frontend, immutable intent and behavior graphs, checked intent-to-behavior lowering, an abstract reference evaluator, planning inspection, frozen build/realization requests, a checked pass manager, automatic combinational and temporal synthetic generation with locked operations, finite-trace realization checking against independent synthetic models, reproducible synthetic workflow packages, immutable typed component contracts, deterministic offline selection, and composition linking with provider/resource checks, independently checked whole-CDS reference construct assembly, and exact-reference DNA/RNA emission. A separate software molecular-design pipeline constructs and independently checks multi-region structural RNA specifications. The intent-candidate pipeline connects one authored product requirement to supplied CDS/architecture selection and automatic RNA assembly, retaining all unimplemented behavior. The checked molecular-implementation pipeline adds full requirement analysis, declared precursor/processing relationships, explicit providers and composite coding-segment construction under the separate `secreted_precursor_structure` scope. The executable RNA payload profile connects source activation and action semantics to bounded selection of supplied contracts, complete molecule-set construction and independent source/component/sequence checking. Unrestricted molecular mechanism discovery, biological simulation, characterized component libraries and empirically supported therapeutic function remain open. Physical manufacture, administration, and execution in a recipient cell are outside the compiler boundary.

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
evaluation readout. This observation profile alone supplies no molecular
implementation; the separate executable RNA profile requires supplied component
contracts and sequence templates.

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

## Current composite RNA architecture path

`PayloadArchitectureRequest` retains the original human circuit/source request,
independently supplied composite Behavior contracts and hard architecture
constraints. `SourceExecutionManifest` preserves every source node and installed
rule/action, including state, memory, numerical rates and role/channel boundaries.
`ExecutableCircuitBehavior` carries full temporal/stateful source semantics for
supplementary readouts instead of approximating them with a stateless table.

`ArchitectureBinding` connects model nodes, locked components, exact templates and
specific member placements many-to-many. One component can require several RNAs;
several components can share one explicitly supplied RNA. Refinement selection,
RNA partitions, helper placement and recipient/co-delivery assignments are solved
together. Distinct refinement instances are namespaced, with no deduplication by
sequence equality. Component models pin the full supplied composite Behavior;
sequence-only records and unrelated intrinsic operators cannot discharge runtime
meaning. The independent checker reconstructs source/model correspondence and
construction authority from the original request.

In `0.1.0.dev29`, `ArchitectureMatchPolicy` permits exact semantic subgraph
matching with empty or partial source anchors. Matching preserves node kinds,
attributes, types, ordered inputs, roles, execution policies and explicitly
pinned output identities. The compiler records each complete correspondence as
an `ArchitectureRefinementInstance`, bounds both search work and the retained
match census, and refuses sequence emission when matching is exhausted. The
checker reconstructs selected correspondences without calling the matcher.
This automates supplied implementation reuse across source node IDs; arbitrary
mechanism discovery and parameter synthesis remain open.

Source-side control requirements distinguish activation, production adjustment,
activity control, memory reset, shutdown, physical separation and dependency
disjointness. Declared control domains and causal inputs are checked independently
of RNA count. Helper capabilities, initialization, capacity, sharing, compartment
and explicit same-recipient delivery determine availability. All delivered helper
RNAs contribute to count/size constraints and export.

Bounded functional proofs additionally cover reset-priority Boolean memory,
finite-state reset, monotone changes to the complete requested production rate
for a role/product, and explicit ongoing activity gating. Proofs require
nonvacuous controls and inspect all relevant source writers or action branches.
Production independence includes every branch's causal inputs and implementing
components. Unsupported temporal or quantitative control proofs retain precise
failures even when the underlying Behavior is executable.

`RNAAvailabilityContract` supplies an onset interval and duration interval for a
placement relative to a declared exposure start. `RNADeploymentRequirement`
requires every group/recipient member, including helpers, to cover an execution
window in its declared compartment and optionally cease availability by a
deadline. The checker uses worst-case interval endpoints and explicit
same-recipient assumptions. It predicts neither delivery success nor effector
clearance. These requirements do not discharge unmapped source deployment or
acceptance wrappers.

Behavior v0.2 provides restricted sampled rolling integration and typed channel
observations/emissions. Coupled execution reuses the original per-role evaluator
under supplied finite-grid latency, persistence, aggregation and failure policies.
These are executable language assumptions, not biological kinetics. Sampled
budgets do not prove continuous exposure bounds; production cessation does not
prove effector clearance. Unbound external helpers and nonempty unmapped component
resource/domain contracts remain unsupported. See the
[complete profile and A–F examples](payload-architecture-v0.1.md).

## Compilation layers

The planned [human immune-cell RNA-circuit track](rna-circuit-reproduction-plan.md)
extends these layers with typed molecular observations, separate human
source-experiment metadata, selected molecular mechanisms, complete molecule
sets, checked molecular-form transformations, overlapping features and structured
chemistry. It preserves
separate base identity, nominal molecular identity, mechanistic correspondence,
model and experimental results. Its Cello-inspired UI will expose linked views
of the same checked human immune request and artifacts, with human-reference
validation as a supporting workflow. Integration into the existing human
target/deployment/acceptance path is required. R0 now adds the
[human circuit profile](human-circuit-profile-v0.1.md): strict scope requests,
typed immune-recipient bindings, separate source context, independent claim
dimensions and fresh assessment replay against the complete expected request.
Original behavior/deployment/acceptance wrappers remain intact. The CLI exposes
scope checking and verification; `compile(CircuitProfileRequest)` explicitly
refuses molecular generation. [R2 circuit intent](circuit-intent-v0.1.md) now adds
role-bound supplemental requirements, exact nominal observations, canonical
Boolean tables, output/provider/lifecycle requirements and declared reference
locks. The independent checker retains the complete original graph and wrappers;
`compile(CircuitRequest)` also refuses molecular generation. [R3 molecular declarations](circuit-molecules-v0.1.md) add named strands/chains,
nominal complexes, explicit coordinates/chemistry, separate assembly partitions
and overlapping annotations, plus independent identity and experimental-amount
layers. R3 declarations alone leave source bytes and transformations unverified.
[R4 checked construction](circuit-construction-v0.1.md) adds separate producer and
reconstruction implementations over retained roots, sequence-free operation
ports, complete residue maps, chemistry/feature dispositions and required-member
inventories. Payload contracts check declared linear/circular DNA/RNA regions;
they do not establish regulatory function. Strict JSON export freshly verifies
the complete external request and retains its full derivation authority.
[Circuit authority infrastructure](circuit-infrastructure-v0.1.md) layers strict
source metadata, nominal requirement/role/observation bindings and evidence
dependency receipts over those artifacts. Binding and evidence checkers re-run
independent construction verification and import no producer. Observation, model
and reference metadata have distinct uses; current identities grant no predictions.
Read-only inspection separates stored assessments from fresh external-authority
replay; its browser saves the exact original JSON and rejects late results.
Software, reviewed reference correspondence and human applicability have separate
acceptance tracks. R1 and R5–R13 remain open; source-backed reconstruction, family
semantics and human admission are not established.

[Portable circuit review bundles](circuit-review-bundles-v0.1.md) retain those
artifacts as bounded canonical archives. A schema-neutral ZIP codec is shared
with existing packages so the review checker never imports producer-dependent
profile dispatch. External complete authority and a pinned historical evidence
receipt are required for fresh replay. Run metadata stays outside the canonical
identity. Studio uses the existing independent checkers for source gaps, nominal
bindings and evidence freshness; it never supplies a second compiler.

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
| `ir` | Immutable versioned intent, behavior, mechanism, component, construct and molecular schemas, including implementation requirements and declared precursor plans; strict JSON serialization and shared stage identifiers. |
| `semantics` | Types, units, context, requirement meanings, observational mappings, and refinement obligations. |
| `compiler` | Pass interfaces, stage ordering, diagnostics, dependency tracking, and provenance. |
| `synthesis` | Propose candidate mechanisms, component assignments, and encodings within supported design spaces. |
| `verification` | Independently check structural and behavioral obligations; retain unknown or failed outcomes. |
| `registry` | Versioned component interfaces, models, context applicability, and evidence references. |
| `models` | Quantitative model adapters and uncertainty representations. |
| `backends/dna`, `backends/rna` | Distinct reference/construction alphabets and emission rules; therapeutic payload output is restricted to RNA. |
| `artifacts` | Deterministic serialization, manifests, provenance, and source maps. |
| `interop` | Future import/export adapters for external representations, such as SBOL and SBML. |

Candidate generation and acceptance are separate responsibilities. A search algorithm may propose an implementation; it cannot waive a requirement or treat missing evidence as a passing result.

## Source-driven molecular candidates

The [guided local workspace](studio-v0.1.md) is a browser frontend to the earlier
`CandidateRequest` product-cassette profile. It prepares the bundled example or validates an imported frozen request,
calls the existing compiler and independent checks, and freshly verifies each
download against complete request authority. Its presentation summary has no
independent authority to establish biological behavior. The package includes all
static assets and the portable artificial request; Python's standard library
serves them only on loopback. No JavaScript build or external runtime dependency
is required. Editing inputs invalidates visible results, and imports remain
read-only rather than receiving silent source rewrites. It does not yet expose
the newer `ImplementationRequest` precursor family described below.

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

## Checked requirements and declared molecular implementations

The [molecular-implementation profile](molecular-implementation-v0.1.md) extends
source-driven construction through a separate checked chain:

```text
original source + supplied library + hard constraints/preferences
    → implementation requirements
    → bounded selection and declared molecular plan
    → exact selected components
    → composite precursor construct
    → complete structural RNA specification
```

`analyze_implementation_requirements(source)` accepts the existing frozen source
request types, retaining every source node, original provenance, target and
wrapped behavior/deployment/acceptance contract. Typed obligations expose
encoding, localization/processing, sensing, control, timing/state, quantitative
response, actions, host/deployment and evidence requirements. Each carries exact
operation arguments and source/context links. Broader unsupported designs remain
analyzable; diagnostics separate unsupported semantics, missing refinements and
known contradictions. An accurate analysis of an unsupported design can pass its
independent correspondence check without making that design implementable.

`ImplementationRequest` freezes source, `ImplementationLibrary` and
`ImplementationConstraints`. The first selectable family contains one role and
one ongoing product secretion under a condition rule. Each supplied RNA
architecture explicitly declares UTRs, a signal-peptide coding segment, an
optional coding junction, a mature-product segment, a terminal stop, optional
poly(A), precursor/product expectations, processing boundary and RNA chemistry.
One product identity must retain the same mature protein throughout the library;
different product variants need distinct identities. Sequence provenance can be
an artificial fixture, supplied sequence or supplied pinned reference. Those
categories record attribution and do not establish biological support.

The plan separates encoded structure from declared processing and transport.
Its typed roles and edges connect translation, precursor, processing, mature
product and extracellular destination. Translation, secretory translocation,
processing and secretion transport each need an explicit compatible host or
external provider. Selection checks exact recipient role, cell scope, physical
compartments and target identity; human host assumptions remain in the original
human contract. Missing or incompatible providers reject an alternative.
Compatible declarations still leave physical function unestablished.

The compiler enumerates product-matching architectures, retains all rejection
reasons, and ranks eligible options after hard constraints. It derives whole-
segment nucleotide placements, in-frame junctions, protein ranges and the
declared processing boundary. Independent checks reconstruct the requirements,
selection, relationships, layout, precursor/mature-protein correspondence,
chemistry and emitted bases from the original request. The checker does not use
the analyzer, selector, construct generator or emitter as an oracle.

`bc.compile(ImplementationRequest(...))` integrates these stages with the pass
manager. Requirements and declared plans occupy the Behavior and Mechanism stage
slots under this profile's structural scope; they are not biological dynamics.
Completion means `secreted_precursor_structure`, with
`therapeutic_implementation="partial"`, `physical_function="unestablished"` and
`human_therapeutic_admission="not_admitted"`. Every implementation obligation
remains unresolved. A strict `require_implementation_complete=True` request
cannot emit a molecule from this family. Neither the default partial mode nor a
structural PASS implements the source guard, shutdown priority, secretion rate,
physical processing, delivery or therapeutic effect.

Saved JSON records retain original authority, alternatives, all stages, tool
identities and independent checks. Fresh verification and FASTA export require
the separately retained complete request and reject stale or altered records.
FASTA omits structured chemistry and remaining obligations, so the corresponding
request and build record remain necessary. These artifacts do not add a `.bcb`
package format or change existing exact-reference contracts. Future functional
families and quantitative adapters must bind their claims to the selected
components, emitted sequences and explicit observation maps. See
[ADR 0004](decisions/0004-checked-molecular-implementation.md).

## Semantic preservation

Each future pass should consume a versioned IR and produce a new IR with:

- A mapping from output entities to input entities and original requirements.
- Its identity, version, configuration, and relevant dependency versions.
- Obligations introduced or discharged, diagnostic results, and unresolved assumptions.
- An explicit list of properties changed and analyses that must be rerun.

A lowering is acceptable only within its supported semantics. For example, a requirement about two signals on the same contacted cell cannot silently become a requirement about signals anywhere in the surrounding environment. Timing, persistence, spatial scope, and population-level versus individual-cell meanings must remain explicit.

Some properties admit exact checks, such as referential integrity or correspondence between a construct and emitted sequence. Behavioral refinement requires an observation mapping between lower-level model trajectories and higher-level requirements. A model-based proof, a numerical simulation estimate, and experimental support are different kinds of evidence and must remain separately labeled. None automatically proves behavior outside its stated context.

## Target selection and revalidation

The therapeutic product target is human in-vivo immune-cell RNA. Shared reference and construction infrastructure preserves distinct DNA and RNA alphabets, coordinate systems and explicit conversion rules; DNA roots or intermediates do not authorize a delivered DNA payload. Select the RNA target and its context before choosing implementations. A backend must reject an unsupported mechanism rather than approximate it without an explicit contract change.

Sequence optimization may preserve a protein sequence while changing modeled expression or stability. Therefore a later sequence change can invalidate higher-level analyses. Track these dependencies so the compiler reruns affected checks instead of equating sequence-level compatibility with behavioral equivalence.

## Build artifact

The eventual artifact should contain the complete digital molecular specification, an annotated construct map, source maps, a deployment manifest, immutable dependency identities, and the verification record. A packaging manifest describes the intended deployment package; it is not a manufactured formulation.

Reproducibility means that frozen inputs and tool versions reproduce the same digital artifact and analysis record. It does not imply that biological outcomes are deterministic.

See the [roadmap](roadmap.md) for implementation order and the [initial architecture decision](decisions/0001-explicit-contracts-and-staged-compilation.md) for constraints.

## Executable semantic foundation

The [behavior semantics](behavior-semantics-v0.1.md) define an execution profile independently of molecular implementations. `lower_to_behavior` normalizes supported intent, binds scalar design parameters, records source/requirement lineage and explicit runtime policies, and rejects unsupported semantics. `verify_lowering` checks correspondence. Behavior IR is immutable and serializable; its reference evaluator runs one engineered cell against supplied input histories, including same-time state propagation and internal deadlines. The architecture executor couples these per-role executions through explicitly supplied, bounded sampled transport; v0.2 integral policies remain pinned in frozen source authority.

The [toolchain contracts](toolchain-contracts.md) are design obligations for every later layer: target capabilities, observation mappings, required responses, independent synthesis/checking, composed resource models, host linking, construct partitioning, encoding invalidation and complete molecular artifacts. Future module docstrings point to these obligations. The reference evaluator is an oracle for language semantics; biological model adapters belong to `models`.

## Independent realization checking

The first [realization profile](realization-checking-v0.1.md) makes a subset of these obligations executable. Response contracts attach typed endpoints, contact scope, active/inactive ranges, and deadlines to installed behavior actions. Operating domains and versioned target contexts make assumptions inspectable. Observation maps bind explicit input fields and output endpoints to a synthetic Mechanism IR.

The candidate model executes independently of the behavior evaluator. A checker compares the two complete discrete-event traces and produces scoped outcomes, source-linked counterexamples, coverage, and dependency fingerprints. Empty coverage, missing assumptions, and unsupported semantics cannot silently become passing results. Evidence freshness is checked against all recorded dependencies before reuse.

This profile tests the preservation machinery without claiming a molecular mechanism has been realized. Full molecular model applicability, uncertainty propagation, measured resource competition, construct composition, and encoding preservation remain separate obligations. Declared component/provider contracts and shared reservations are now checked by the component linker; these declarations remain conditional assumptions. [ADR 0003](decisions/0003-independent-realization-checking.md) records this boundary.

## Implemented request and pipeline boundary

The [frozen request design](build-requests-v0.1.md) makes explicit bindings authoritative and separates source/behavior identity from the later contract/domain phase. The [pass manager](pass-manager-v0.1.md) admits only independently checked, fresh stage outputs. The [combinational synthetic profile](synthetic-profile-v0.1.md) has an automatic generator and a small versioned operation catalog. Separately [curated reference records](reference-benchmarks.md) establish exact CDS expectations; they are not molecular implementations of the synthetic graphs. The [component contracts](component-contracts-v0.1.md) and [offline linker](component-linking-v0.1.md) now support checked synthetic Mechanism → Components lowering. Interface meaning and domain inclusion, explicit providers, assumption cycles, shared capacities and dependency locks are checked independently. `run_component_pipeline` preserves source lineage and finite-history evidence in a `synthetic_components` scope. A [frozen construct request](construct-ir-v0.1.md) now fixes selected membership, reference ranges and expected layout before generation. The [independent construct checker](construct-checking-v0.1.md) validates a single whole DNA or RNA CDS and retains unknown delivered-molecule context. The [exact-CDS pipeline](exact-cds-pipeline-v0.1.md) now emits that selected reference spelling through a separate DNA or RNA backend and independently verifies nucleotide identity, linked-reference consistency, translation and source correspondence. This exact-reference path retains its single-CDS scope. Complete multi-member construction and bounded source-to-RNA translation are implemented by the separate supplied-construction and executable payload profiles; unrestricted molecular realization and empirical therapeutic function remain open. The structural molecular-design profile below supports explicitly supplied RNA fragment/layout authority.

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

These interfaces support the current bounded source-to-RNA workflow and its extensions: a
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

Planning and unsupported general compilation retain missing obligations for arbitrary quantitative curves, continuous integration, interval-valued intent, population/spatial behavior and feedback. The composite architecture profile separately implements explicit rate branches, sampled rolling integration and declared numeric channels within its documented bounds. They preserve these authored requests without silently assigning an approximate execution model. The partial intent-candidate and declared precursor profiles retain such obligations while implementing only their supported structural scopes. The [M9 evidence review](m9-evidence-review.md) identifies the scientific and source inputs needed for subsequent adapter and reference-promotion work.

## Human-profile use admission

The [M10.5 admission policy](human-admission-v0.1.md) is shared by planning, registry selection, fresh implementation verification and export. Its immutable request binds target, intended use, boundary and selected component records; the assessment preserves declared evidence categories and limitations. The current policy admits no human therapeutic profiles. Generic targets can request labeled software workflows only; human contexts cannot bypass admission by requesting software use. The partial product-cassette and declared precursor workflows retain human requirements and admission refusal while emitting structurally checked research candidates; they grant no therapeutic implementation eligibility. Supplied human-contract observations may pass their finite checks without granting implementation eligibility. The composite architecture path separately checks conditional software translation in the original human context without biological-evidence gating or human-use admission.

Independent composition, construct and molecular checks rerun admission even for exact manually supplied locks. Synthetic generation and direct realization checks reject human targets. Reference export and archive reconstruction check use before accepting a build. Molecular/synthetic artifacts, reference manifests and summaries carry fixed software-use labels; FASTA carries equivalent header fields. Policy identities enter verification, pass-manager and package dependencies. Matching saved hashes or PASS labels cannot replace fresh current checks.

## Proposed profile cases and completion scope

[M10.6](human-profile-v0.1.md) connects the human target, behavior, deployment, acceptance and admission layers in ten inspectable request cases. The proposed first family is reversible conditional secretion with an RNA deployment declaration; its precise human context, cue/product identities, delivery and biological bounds remain unresolved. Each case reports declaration compatibility, finite-trace acceptance, admission refusal, compilation unavailability and missing evidence separately.

The example-only trace enumerator records an ordered candidate inventory, budget, checked results and unchecked count. Exhausting a candidate set or budget cannot establish global infeasibility; adding a passing observation trajectory can supply a software witness. A separate explanation establishes only an empty intersection of simultaneous active/background rate constraints under an explicit healthy-context condition. Neither path supplies a molecular implementation or establishes biological reachability. Saved evidence is compared with fresh results from current example authority; no compiler backend or admitted biological profile is added.
