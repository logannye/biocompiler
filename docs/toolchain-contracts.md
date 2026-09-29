# Toolchain contracts and future obligations

CellWeave progressively refines authored behavior into a physical implementation. Compiler transformations preserve meaning; synthesis proposes implementations. A precise nucleotide artifact does not establish a precise cellular outcome. This document records cross-layer requirements and distinguishes implemented checks from future molecular capabilities.

Implementation order, stable task IDs and acceptance gates are tracked in the [development roadmap](roadmap.md). Its first molecular milestones use [exact CDS reference benchmarks](reference-benchmarks.md), with completeness judged against an explicit requested artifact scope. CDS identity, synthetic-model correctness and molecular behavioral refinement remain separate checks.

## Current enforcement and remaining obligations

| Responsibility | Implemented boundary | Remaining obligation |
| --- | --- | --- |
| Execution semantics | Immutable Behavior IR, checked source correspondence, independent reference execution | Continuous control, spatial and population profiles |
| Observable meaning | Explicit endpoint, type, role, contact scope, compartment, input field and output mapping | Calibrated interpretation of physical measurements and higher-level effects |
| Required responses | Active/inactive ranges, activation/recovery deadlines, exercised finite-trace coverage | Stochastic tolerances, distributional and population quantifiers, long-term adaptation |
| Operating assumptions | Nonempty typed input domains, contact limits, horizon, declared target capabilities | Cell-state applicability, physical resources, lifecycle and deployment assumptions |
| Independent acceptance | Synthetic candidate runner and checker, independent component/construct/exact-CDS checks, source-linked diagnostics, explicit outcomes | Domain-specific biological adapters and validation evidence |
| Analysis identity | Fingerprints of checked artifacts, histories, context and tool semantics; transitive pass freshness and independently reconstructed reference packages | Persistent analysis cache and signed provenance |
| Composition | Typed graph edges, contract compatibility, circular-assumption detection and declared shared-resource accounting | Calibrated physical resource demands and biological interaction models |
| Parameter meaning | Frozen design bindings with category/provenance/variation metadata, runtime signals kept distinct | Robust checks over uncertain/calibrated quantities |
| Host and payload linking | Explicit encoded-here/co-payload/host/external/unresolved inventory and offline dependency linker | Independent experimental support for supplied host and delivery assumptions |
| Encoding | Checked single-CDS Construct IR, exact DNA/RNA backends, scoped feature declarations and conservative invalidation | General molecular realization, complete payload features and calibrated higher-level revalidation |

The [realization checking profile](realization-checking-v0.1.md) defines the exact implemented scope. Capability declarations are assumptions supplied by a context author, not verified facts about a host. A finite-trace pass is conditional on its recorded inputs; the minimal synthetic operator catalog supplies no characterized molecular component or sequence-generation capability.

| Stage | Required representation and obligation |
| --- | --- |
| Intent | Typed roles, observations, actions, units, scope, parameters, source locations. Python runs at authoring time; explicit operators describe cellular runtime behavior. |
| Behavior | Observable contracts over time: identity, state, events, concurrency, response bounds, required responses, and accepted variability. Preserve both permitted behavior and required responses. |
| Target | Versioned cell context, modality, host capabilities, compartments, resources, persistence and deployment assumptions. Select before mechanism search. |
| Mechanism | Candidate entities and interactions, causal paths, parameter domains, host dependencies, and observation maps back to the behavior contract. |
| Components | Locked implementations with dynamical interface contracts and model references, not only names and sequences. Analyze the composed system, including shared resources. |
| Construct | Molecule inventory, arrangement, regulatory relationships, orientation, boundaries, localization and payload partitioning. Required same-cell coexistence is an explicit assumption. |
| Molecular specification | Exact target-specific sequences, topology, relevant chemistry/end features, coordinates and molecule relationships. DNA and RNA are distinct backends. |
| Artifact | Canonical molecular specifications, hashes, locked dependencies and tools, source maps, chosen alternatives and verification records. Physical manufacture remains external. |

## Every lowering pass

Carry stable requirement identities (within a frozen source graph), source correspondence, context and assumptions. Declare input/output semantics and an observation mapping: which lower-level states and events represent the original observations/actions? Return preservation obligations, results, changed properties and analyses invalidated by the change. Source maps show lineage; they do not prove refinement.

Exact graph checks, model-conditional results, numerical simulation and empirical support are distinct records. Behavioral refinement means the lower-level observable behavior satisfies the higher-level contract under its declared assumptions and tolerances. A checker must include required responses: a design that never responds must not pass a contract requiring a response. Unknown, failed and unsupported outcomes must remain distinct.

## Synthesis and linking

Keep proposal/search separate from independent acceptance checks. Requirements cannot be relaxed by an optimizer; preferences may rank otherwise acceptable candidates. No candidate found is not a proof of infeasibility. Record search configuration and dependencies for reproducibility.

Resolve every dependency as encoded here, encoded in another declared payload, host-provided, externally supplied or unresolved. Component interfaces include signal meaning, units, location, dynamics and shared-resource assumptions. Composition and construct layout are semantic work. A multi-molecule manifest does not establish co-delivery or co-expression in the same cell.

## Encoding and revalidation

Sequence changes can affect higher-level properties even when the encoded protein is unchanged. Each encoding optimization must identify affected model parameters/properties and invalidate dependent analyses. Require complete mappings from encoded features to mechanisms and requirements. A sequence string alone may not fully specify an RNA/DNA molecule; retain target-specific features in the artifact.

## Interoperation and architecture

SBOL can exchange components, sequences and interactions; SBML can exchange mathematical models. Neither substitutes for CellWeave's behavioral contracts. Target capabilities, component libraries and solver/model adapters should evolve independently of the authoring language.

Background: [LLVM code generation](https://llvm.org/docs/CodeGenerator.html), [Cello 2.0](https://www.nature.com/articles/s41596-021-00675-2), [resource-aware mammalian constructs](https://www.nature.com/articles/s41467-023-39252-4), [SBOL](https://sbolstandard.org/docs/SBOL3.1.0.pdf), [SBML](https://sbml.org/documents/specifications/).
