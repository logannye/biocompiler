# Architecture charter

Status: normative design direction, adopted 2026-10-13. This charter governs new
architecture decisions and incremental refactoring. It does not declare the
target architecture implemented, enlarge an existing executable profile, or
transfer acceptance to a new revision. Current support belongs in the
[capability matrix](capability-matrix.md); implementation order and unfinished
work belong in the [refactoring roadmap](architecture-refactoring-roadmap.md).
Apply the [architecture review](architecture-review.md) proportionally.

## Product contract

Biocompiler translates high-level therapeutic programs for human immune cells
engineered **in vivo** into precise, complete RNA payload specifications. The
output is the full molecule set and companion manifest: exact bases, molecular
regions and joins, products, topology, nominal chemistry and terminal features,
recipient assignments, dependencies, assumptions and claim dispositions.
FASTA alone cannot express that contract.

Python is an authoring host. Its control flow must not silently become cellular
execution. Natural-language authoring, when introduced, must resolve to the same
inspectable source semantics. A laboratory protocol, administration schedule or
measurement procedure can be an explicit external dependency; it is not an
instruction encoded in RNA unless a supplied implementation actually realizes
that instruction. Preserve these boundaries in source, diagnostics and exports.

Software compilation under supplied component/model contracts is a useful and
independently completable result. Exact construction, satisfaction under a model,
whether that model describes physical behavior, and empirical or human-use
qualification are separate claims. Missing empirical qualification does not
automatically block a software claim whose explicit premises are sufficient.
Conversely, software acceptance cannot establish a premise about physical cells.

## Architectural principles

### AC-01 — Semantic adequacy

Source must describe the therapeutic distinctions that affect correctness:
executor and subject identity, scope and ownership, observations, state, time,
effects and their lifecycle, requirements, deployment and external actions.
Separate requesting an effect, producing a molecule, observing an effect and
stopping ongoing activity. Define supported meanings before adding syntax.

Resolve executable source to typed terms and nominal references. A new feature
must state its source meaning and its realizable subset; a convenience API or
schema entry alone establishes neither. Preserve unsupported requirements with
their identities and reasons. Compilation must not silently narrow the request
to what an available component happens to implement.

### AC-02 — End-to-end soundness and useful coverage

Every accepted output must retain a checked chain from original source through
selected implementation to exact material. State the semantic relation and
premises at each step. A source may denote a set of permitted behaviors;
refinement must satisfy its requirements under the declared context, rather than
merely match one favored execution trace. Check required progress and coverage
as well as safety; an implementation that never acts is not automatically valid.

Pair sound rejection with demonstrated useful acceptance. Each claimed capability
needs a positive source-to-output witness and a meaningful source edit that
changes the result or yields the correct diagnostic. Rejecting everything is
not a completed compiler feature. Unsupported lowering, exhausted search and a
counterexample to a supplied model are different outcomes.

### AC-03 — Context-sensitive composition

Compose modules through explicit interfaces, assumptions, guarantees, ownership,
resources and observation maps. Preserve identity across cells, encounters,
compartments and time; distinguish same-recipient from same-population delivery.
Account for shared state, interference, stoichiometry premises, helper bootstrap,
capacity, transport and RNA/protein persistence when relevant to the contract.

Valid parts do not imply a valid whole. A local result is reusable only through a
checked composition rule with satisfied premises. Compare new bounded
compositional rules with whole-program checking on distinguishing witnesses.
Graph linking and molecular concatenation alone establish no behavioral theorem.
Two modules cannot establish each other's assumptions by circular assertion.
Supported feedback needs an explicit fixed-point, invariant or other checked
composition argument; otherwise retain the premise as unresolved.

### AC-04 — Realization-aware synthesis

Implementation choice must account for material, interfaces, deployment and
resource constraints before committing to a result. Do not choose a primitive
solely by incidental identity order and then treat failure of that choice as
failure of all supplied alternatives. Feed downstream infeasibility back into
bounded selection or carry candidate alternatives until the relevant constraints
have been checked.

Search may use heuristics, nondeterminism or learned proposal generators. A
retained candidate must be independently auditable against original authority;
deterministic generation is not the source of correctness. Record the declared
search space, policy, limits and proposal provenance needed to explain the
result. Distinguish feasible-candidate validity, preference ranking and search
completeness. A valid winner need not wait for proof of global optimality unless
the request demands that proof. Malformed or tampered authority is not an
ordinary losing design.

### AC-05 — Uncertainty and time are semantic data

Represent physical state, cell-accessible observation and evaluator evidence
separately, with explicit maps between them. Missing, stale, invalid and
conflicting evidence must not silently become physical absence or cellular OFF.
Distinguish unresolved design holes from runtime unknowns and checking limits.
When observation error or delay matters, the model must represent observed
values and their relationship to physical values, not only an evidence label.

Specify clocks, units, sampling, freshness boundaries, event ordering, simultaneous
updates, timeout priority, reset and lifetime rules. Preserve these meanings
across passes. State exploration horizons, intervention bounds and held-input
suffixes explicitly. Sampled checks do not establish continuous-time properties;
stopping production does not by itself stop existing effector activity.

### AC-06 — Independent checking with a small trust boundary

Treat producer candidates as untrusted. The verifier must reconstruct the
expectations relevant to its claim from independently supplied original
authority, without calling the producer's claim-defining algorithms. Keep
source execution and candidate execution separate. Shared schemas, codecs,
arithmetic and canonicalization are permitted, but identify their role in the
trusted computing base and test their boundaries.

Separate decoded, admitted, proposed and checked values in pass interfaces.
Opaque checked values must bind exact inputs, context, semantic versions and
limits; a serialized PASS label is not such a value. Do not duplicate semantics
merely to appear independent: share declarative language definitions where
appropriate, while keeping the checking argument and relevant algorithms
independent. Minimize, document and test the trust boundary.

### AC-07 — Complete provenance and change invalidation

Retain original source, requirement/occurrence lineage, supplied models and
components, material authority, context, assumptions and unresolved obligations
through every pass. Content hashes identify records; they do not establish that
the records are authorized or correct. Source and dependency edits must
invalidate affected claims, even when emitted bases happen to remain identical.

Publish the exact paired RNA/manifest artifact only after the required fresh
checks. Reverification must use separately retained original authority and compare
every claimed output. Keep source revision, platform, run, attempt and artifact
provenance for validation; historical results never transfer by description.

### AC-08 — Coherent extensibility

Extend a common semantic core through explicit capabilities and pass contracts.
Do not encode independent features solely as mutually exclusive example-shaped
profiles, or require a new compiler family for every useful combination of
already-supported features. Supported combinations and real bounds must be
discoverable before expensive compilation.

Versioned adapters may preserve existing wire formats and acceptance boundaries.
A temporary specialized path must state why it is needed, what common semantics
it implements and how it will converge or remain deliberately isolated. New
expressions, primitive types or requirement kinds need coherent authoring,
admission, lowering, checking and diagnostic support; update the capability
matrix rather than implying support from their existence in an API.

### AC-09 — Scalable verification and actionable diagnostics

Bound resource use across decoding, elaboration, synthesis, checking and
publication. Exhaustion or cancellation must preserve a scoped incomplete result
and useful diagnostics, never a partial acceptance. Explain failures by original
requirement, source location, selected component, violated premise or exhausted
bound, with a counterexample or rejection reason where available.

Measure compilation, search, verification and publication separately. Reuse
immutable data and sound intermediate results only with explicit dependency and
invalidation rules; do not cache acceptance by resemblance. Optimize the actual
bottleneck while preserving required coverage and independent checks. A usable
compiler must expose why a request fails and what supported change could help.

## Target intermediate representations and pass contracts

This is the target organization, not a claim that all current routes use it.
An implementation may fuse stages internally if their contracts and independent
checking boundaries remain inspectable.

| Stage | Required meaning and retained authority | Obligation before the next claim |
| --- | --- | --- |
| Source request | Original program, deployment, requirements, assumptions and supplied catalog; host and external actions identified | Resolve names/types/scopes; diagnose holes and unsupported constructs without erasing them |
| Semantic IR | Typed observations, state, events, effects, temporal/quantitative relations and allowed behaviors; stable source lineage | Check source correspondence and explicit execution/assurance semantics |
| Realization plan | Candidate mechanisms, model-to-source maps, interfaces, ownership, resources, context, alternatives and unresolved premises | Check refinement, composition and feasibility under the declared domain; retain search outcomes separately |
| Molecular assembly IR | Selected material, complete member inventory, regions/joins, product mappings, chemistry, helpers and recipient assignments | Independently check material-to-plan correspondence and every construction obligation |
| Exact RNA specification | Exact sequences plus complete nominal molecular and deployment metadata | Check every base, feature, coordinate, product and manifest-only property against original authority |
| Checked package | Paired RNA/manifest with claim ledger, exact dependencies, limits and checker identity | Fresh export/replay verifies the artifact and states precisely which claims hold |

Every pass contract must identify its accepted input state, independent
authority, output representation, semantic preservation/refinement relation,
premises, obligation mapping, resource limits, diagnostics and invalidation
dependencies. No pass may turn an unchecked proposal into acceptance by changing
its type name or copying an upstream report. Sequence or architecture
optimization must recheck every affected higher-level relation.

## Claim lattice and result discipline

Claims form a dependency-ordered product, not a single ladder ending in blanket
PASS. Track source validity, supported semantics, model-conditional refinement,
requirement satisfaction, composition/context feasibility, exact molecular
correspondence, search coverage/ranking, empirical applicability and use status
separately. A claim may depend on another claim or on an explicitly retained
supplied premise; the distinction must remain visible.

For each requested claim, retain its subject, premises, scope/bounds, checker and
disposition: checked, refuted, unknown/incomplete or unsupported. Mark a claim
not requested only when it truly lies outside the original request. Report
invalid authority/input separately. A checked structural claim can coexist with
unknown behavior or unassessed empirical applicability. Export must satisfy the
declared export contract and retain every remaining obligation; it must not
rename partial completion as complete therapeutic implementation.

These are conceptual result categories, not replacement wire-enum values.
Versioned profiles retain their explicit `conditional`, `discharged`,
`not_applicable` and unresolved dispositions until a checked migration defines
their mapping. A conditional checked relation never discharges its physical
premises merely because the compiler checked that relation.

Migration and exceptions follow [architecture review](architecture-review.md).
This charter adds design obligations, not extra approval rituals or a native
build requirement for documentation changes. Existing user authorization,
checkout ownership and [development validation](development-validation.md)
continue to govern execution and integration.
