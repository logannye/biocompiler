# Toolchain contracts and future obligations

The [RNA architecture profile](payload-architecture-v0.1.md) provides a
connected contract-conditional path from complete therapeutic Behavior through
supplied composite implementations, RNA partitions and recipient assignments to
exact RNA sets for human immune cells engineered in vivo. The earlier
[per-operator payload profile](executable-rna-payload-v0.1.md) remains available. Software translation is checked against
original source and supplied component/template authority independently of
biological evidence. Component function and clinical applicability remain
separate obligations; unsupported source requirements remain explicit.

biocompiler progressively refines authored behavior into a physical implementation. Compiler transformations preserve meaning; synthesis proposes implementations. A precise nucleotide artifact does not establish a precise cellular outcome. This document records cross-layer requirements and distinguishes implemented checks from future molecular capabilities.

Implementation order, stable task IDs and acceptance gates are tracked in the [development roadmap](roadmap.md). Its first molecular milestones use [exact CDS reference benchmarks](reference-benchmarks.md), with completeness judged against an explicit requested artifact scope. CDS identity, synthetic-model correctness and molecular behavioral refinement remain separate checks.

## Current enforcement and remaining obligations

| Responsibility | Implemented boundary | Remaining obligation |
| --- | --- | --- |
| Execution semantics | Immutable Behavior IR, finite state/rates, versioned sampled integration, checked source correspondence and declared finite-grid channel execution | Continuous control, spatial and population profiles |
| Observable meaning | Explicit endpoint, type, role, contact scope, compartment, input field and output mapping; source-linked conditional secretion measurements with cell/evaluator access | Calibrated interpretation of physical measurements and higher-level effects |
| Required responses | Active/inactive ranges, activation/recovery deadlines, exercised finite-trace coverage | Stochastic tolerances, distributional and population quantifiers, long-term adaptation |
| Operating assumptions | Nonempty typed input domains, contact limits, horizon, declared target capabilities and frozen human deployment/expression assumptions | Empirical cell-state, delivery, resource and lifecycle applicability |
| Independent acceptance | Synthetic candidate runner and checker, independent component/construct/exact-CDS checks, source-linked diagnostics, explicit outcomes | Domain-specific biological adapters and validation evidence |
| Analysis identity | Fingerprints of checked artifacts, histories, context and tool semantics; transitive pass freshness and independently reconstructed reference packages | Persistent analysis cache and signed provenance |
| Composition | Typed graph edges; composite model pins; many-to-many behavior/component/RNA/recipient bindings; exact member placements; control independence, helper bootstrap/capacity and same-recipient checks. Older linker resource accounting remains separate; the new architecture profile rejects unmapped nonempty resource/domain records | Calibrated physical resource demands and biological interaction models |
| Parameter meaning | Frozen design bindings with category/provenance/variation metadata, runtime signals kept distinct | Robust checks over uncertain/calibrated quantities |
| Host and payload linking | Explicit encoded-here/co-payload/host/external/unresolved inventory and offline dependency linker | Independent experimental support for supplied host and delivery assumptions |
| Encoding | Selected supplied architecture templates through complete molecule-set construction and independent replay, plus legacy exact-CDS/multi-region/precursor paths; exact fragment/layout/chemistry authority and conservative invalidation | General molecular realization, biologically supported complete payloads and calibrated higher-level revalidation |

The [realization checking profile](realization-checking-v0.1.md) defines the exact implemented scope. Capability declarations are assumptions supplied by a context author, not verified facts about a host. A finite-trace pass is conditional on its recorded inputs; the minimal synthetic operator catalog supplies no characterized molecular component or sequence-generation capability.

| Stage | Required representation and obligation |
| --- | --- |
| Intent | Typed roles, observations, actions, units, scope, parameters, source locations. Python runs at authoring time; explicit operators describe cellular runtime behavior. |
| Behavior | Observable contracts over time: identity, state, events, concurrency, response bounds, required responses, and accepted variability. Preserve both permitted behavior and required responses. |
| Target | Versioned cell context, modality, host capabilities, compartments, resources, persistence and deployment assumptions. Select before mechanism search. |
| Mechanism | Candidate entities and interactions, causal paths, parameter domains, host dependencies, and observation maps back to the behavior contract. |
| Components | Locked implementations with dynamical interface contracts and model references, not only names and sequences. Analyze the composed system, including shared resources. |
| Construct | Molecule inventory, arrangement, regulatory relationships, orientation, boundaries, localization and payload partitioning. Required same-cell coexistence is an explicit assumption. |
| Molecular specification | Exact target-specific sequences, topology, relevant chemistry/end features, coordinates and molecule relationships. Current therapeutic output is RNA; legacy DNA roots/reference backends retain distinct alphabets. |
| Artifact | Canonical molecular specifications, hashes, locked dependencies and tools, source maps, chosen alternatives and verification records. Physical manufacture remains external. |

## Every lowering pass

Carry stable requirement identities (within a frozen source graph), source correspondence, context and assumptions. Declare input/output semantics and an observation mapping: which lower-level states and events represent the original observations/actions? Return preservation obligations, results, changed properties and analyses invalidated by the change. Source maps show lineage; they do not prove refinement.

Exact graph checks, model-conditional results, numerical simulation and empirical support are distinct records. Behavioral refinement means the lower-level observable behavior satisfies the higher-level contract under its declared assumptions and tolerances. A checker must include required responses: a design that never responds must not pass a contract requiring a response. Unknown, failed and unsupported outcomes must remain distinct.

## Synthesis and linking

Keep proposal/search separate from independent acceptance checks. Requirements cannot be relaxed by an optimizer; preferences may rank otherwise acceptable candidates. No candidate found is not a proof of infeasibility. Record search configuration and dependencies for reproducibility.

Resolve every dependency as encoded here, encoded in another declared payload, host-provided, externally supplied or unresolved. Component interfaces include signal meaning, units, location, dynamics and shared-resource assumptions. Composition and construct layout are semantic work. A multi-molecule manifest does not establish co-delivery or co-expression in the same cell.
The architecture profile therefore requires explicit recipient delivery groups,
material placements and same-recipient assumptions. Delivered helpers count in
all RNA budgets; capacity counts named consumers under the supplied contract.
Neither shared activation nor independent shutdown determines RNA count.
Production adjustment, activity control, memory reset, physical separation and
dependency disjointness are distinct control requirements. Production cessation
cannot discharge an effector-clearance or inactivation obligation.

## Bounded execution and conditional architecture proof

A composite supplied Behavior graph must preserve actual source nodes, edges,
roles, types, action identities, parameters and execution policies under explicit
correspondence. Modeled components pin that graph, while template/placement
bindings retain its material realization assumptions. Independent checking
reconstructs both selected behavior and every emitted molecule from separately
supplied authority; it does not accept a family label, claimed coverage or saved
PASS as proof. Search exhaustiveness and optimality are not independently certified.

Behavior v0.2 rolling integrals use exact piecewise-constant area with explicitly
sampled guard evaluation. Coupled numeric channels use supplied finite-grid
latency/persistence/aggregation/failure contracts. Continuous budget guarantees,
zero-latency feedback in the coupled executor, arbitrary external helpers and
unmapped component resource/domain contracts remain unsupported. Complete export
retains the FASTA and full manifest together, including all conditional assumptions.

## Encoding and revalidation

Sequence changes can affect higher-level properties even when the encoded protein is unchanged. Each encoding optimization must identify affected model parameters/properties and invalidate dependent analyses. Require complete mappings from encoded features to mechanisms and requirements. A sequence string alone may not fully specify an RNA/DNA molecule; retain target-specific features in the artifact.

## Interoperation and architecture

SBOL can exchange components, sequences and interactions; SBML can exchange mathematical models. Neither substitutes for biocompiler's behavioral contracts. Target capabilities, component libraries and solver/model adapters should evolve independently of the authoring language.

Background: [LLVM code generation](https://llvm.org/docs/CodeGenerator.html), [Cello 2.0](https://www.nature.com/articles/s41596-021-00675-2), [resource-aware mammalian constructs](https://www.nature.com/articles/s41467-023-39252-4), [SBOL](https://sbolstandard.org/docs/SBOL3.1.0.pdf), [SBML](https://sbml.org/documents/specifications/).

## Human acceptance authority

Before human mechanism selection, retain the [M10.4 acceptance request](human-acceptance-contract-v0.1.md)
as one authority for source behavior, deployment and prohibitions. Its healthy
classifier remains evaluator-only; input-loss and shutdown requirements need
separate mechanism mappings. A source/control conflict cannot be resolved by
silently adding priority. Rerun supplied-trace checks against independent request
and observation authority; imported results and current fingerprints alone do
not establish acceptance. Biological applicability and actuator support remain
unestablished/unimplemented even when all declared observations pass.

## Human-profile admission gate

[M10.5](human-admission-v0.1.md) adds a current use-eligibility check at planning, component selection, fresh verification and export. There are no empirically admitted human therapeutic profiles in this release. The supplied-contract architecture compiler checks code translation in the original human target without requiring or granting biological admission. The admission-governed reference/synthetic workflows permit generic software targets and require independent admission for human-use claims. The architecture profile preserves its human source context while making only conditional translation claims; it neither bypasses nor grants empirical admission. Source/CDS identity, finite-model PASS, supplied human-contract observations and self-declared evidence categories cannot authorize human implementations. Policy identity is retained in affected dependency snapshots and reference packages. Future supported profiles must revise this gate with independently reviewed authority rather than adding an override label.

## Proposed-profile examples and result distinctions

The [M10.6 profile document](human-profile-v0.1.md) fixes the scope of the first request-case suite before its evidence-supported human `compile()` path is enabled. The later supplied-contract RNA compiler has a separate conditional software-translation scope. Keep missing measurements and unknown deployment bounds distinct from observed failures and unsupported dependencies. Report admission independently from observation consistency. The example-only trace search retains finite candidate/budget bounds and cannot infer infeasibility from exhaustion. Its conditional rate-bound contradiction has a narrower mathematical scope than therapeutic feasibility. M11 evidence review and M12–M14 implementation/admission work remain necessary.
