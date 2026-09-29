# 0002: Define an executable abstract behavior profile before molecular lowering

Date: 2026-09-29
Status: Accepted

## Context

The Python API constructs a typed intent graph but does not assign every operation a complete executable meaning. Lowering directly to molecular parts would hide decisions about contacted-object identity, concurrency, state, triggering and time inside backend heuristics. Future implementations need a common behavior specification against which their observation mappings can be checked.

## Decision

Introduce immutable, versioned Behavior IR and a checked intent-to-behavior pass. Preserve original node identities, source locations, requirement ownership and source fingerprints. Normalize explicit policies for rule activation, event ordering, simultaneous writes, memory and pulses. Bind scalar design parameters before execution; reject unsupported or unresolved execution semantics with source-linked diagnostics.

The reference evaluator executes one engineered cell against externally supplied, piecewise-constant observations. Contact identities bind compound predicates before existential reduction. Cell-local output requests aggregate qualifying contacts; targeted/contact-valued requests retain their bindings. Each runtime owns its state independently. Qualitative bands are supplied observations; no threshold is invented.

Use event-driven time: process input snapshots and internal deadlines, settle automatic memory controls in dependency order before rule effects, then settle atomic finite-state changes through same-time microsteps, and reject conflicting writes or nonconvergent state updates. A finite evaluation horizon bounds the computation. Actions are abstract requests and never change supplied observations automatically.

Keep the authoring vocabulary broader than the first executable profile. Unsupported control, spatial transport and quantitative model operations remain authorable and serializable but cannot be silently omitted from executable lowering.

## Consequences

Reference execution checks language meaning and provides examples/counterexamples for future model comparisons. It does not predict cellular dynamics, choose molecular components, or emit nucleic acid sequences. Exact structural correspondence checks are not a general proof of biological refinement.

Every downstream pass must implement the [toolchain contracts](../toolchain-contracts.md). The normative current language policy is [behavior semantics v0.1](../behavior-semantics-v0.1.md). Changing an execution policy requires an explicit semantic-version decision and regression examples; Python declaration order must never become an implicit priority.
