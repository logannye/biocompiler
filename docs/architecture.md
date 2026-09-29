# Architecture

CellWeave is a proposed compiler for converting an immune-cell engineer's intent into an exact digital specification of a DNA or RNA payload. Its organizing principle is **preservation of a behavioral contract through explicit intermediate representations (IRs)**.

The current repository is a skeleton. It supplies vocabulary and extension points, not a biological compiler, validated component library, or sequence generator. Physical manufacture, administration, and execution in a recipient cell are outside the compiler boundary.

The [v0.1 intent API proposal](intent-api-v0.1.md) defines the planned authoring vocabulary: cell roles, scoped observations, expressions, actions, state, outputs, controllers, and communication. Python constructs an inspectable intent graph; molecular realization remains a later stage.

## Compilation layers

| Layer | Representation | Preservation obligation |
| --- | --- | --- |
| Python frontend | Declarative biological operations authored through a future typed DSL | Separate design-time Python control flow from intended biological control flow. |
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
| `frontend` | Parse or construct a typed intent graph; retain source locations and reject unsupported authoring constructs. |
| `ir` | Shared stage identifiers and reserved modules for future versioned stage-specific schemas. |
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
