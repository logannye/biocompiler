# Architecture

CellWeave is a proposed compiler for converting an immune-cell engineer's intent into an exact digital specification of a DNA or RNA payload. Its organizing principle is **preservation of a behavioral contract through explicit intermediate representations (IRs)**.

The current repository implements the Python intent frontend, immutable intent and behavior graphs, checked intent-to-behavior lowering, an abstract reference evaluator, planning inspection, frozen build/realization requests, a checked pass manager, automatic combinational synthetic generation with locked operations, finite-trace realization checking against independent synthetic models, immutable typed component contracts, deterministic offline selection, and composition linking with provider/resource checks, and independently checked whole-CDS reference construct assembly. Molecular lowering, biological simulation, characterized component libraries, and sequence generation are not implemented. Physical manufacture, administration, and execution in a recipient cell are outside the compiler boundary.

The [v0.1 intent API](intent-api-v0.1.md) implements the authoring vocabulary: cell roles, scoped observations, expressions, actions, state, outputs, controllers, and communication. Python constructs an inspectable intent graph; molecular realization remains a later stage.

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
| `ir` | Immutable versioned intent and behavior graphs and JSON serialization; shared stage identifiers and reserved later-stage schemas. |
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

The [frozen request design](build-requests-v0.1.md) makes explicit bindings authoritative and separates source/behavior identity from the later contract/domain phase. The [pass manager](pass-manager-v0.1.md) admits only independently checked, fresh stage outputs. The [combinational synthetic profile](synthetic-profile-v0.1.md) has an automatic generator and a small versioned operation catalog. Separately [curated reference records](reference-benchmarks.md) establish exact CDS expectations; they are not molecular implementations of the synthetic graphs. The [component contracts](component-contracts-v0.1.md) and [offline linker](component-linking-v0.1.md) now support checked synthetic Mechanism → Components lowering. Interface meaning and domain inclusion, explicit providers, assumption cycles, shared capacities and dependency locks are checked independently. `run_component_pipeline` preserves source lineage and finite-history evidence in a `synthetic_components` scope. A [frozen construct request](construct-ir-v0.1.md) now fixes selected membership, reference ranges and expected layout before generation. The [independent construct checker](construct-checking-v0.1.md) validates a single whole DNA or RNA CDS and retains unknown delivered-molecule context. Multi-molecule assembly, molecular lowering and sequence emission remain future work.

## Reference construct entry and evidence

The [reference construct pipeline](reference-construct-pipeline-v0.1.md) starts from an independently checked Components root. It performs no substitute Intent/Behavior/Mechanism passes and makes no behavioral realization claim. A registered input policy checks current registry/reference identity and composition before the Components → Construct pass can run. Layout changes invalidate conditional composition and biological evidence; the narrow single-CDS profile rechecks composition, while empirical claims and emitted-sequence identity remain unresolved.
