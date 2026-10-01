# ADR 0007: Language ownership and an OCaml compiler core

- Status: accepted target architecture; implementation pending
- Date: 2026-10-01
- Basis: explicit user decision after comparing Python, OCaml, Rust and C
- Execution plan: [language migration roadmap](../language-migration-roadmap.md)

## Context

The current compiler is implemented in Python and Studio uses JavaScript.
Python also hosts the biological authoring DSL. These are separate roles:
the authoring language does not determine the language implementing semantic
representations, compilation or verification.

Biocompiler must preserve source requirements, scope, units, temporal behavior,
model assumptions, component identities and exact molecular correspondence.
The current implementation has explicit schemas, runtime validators and
independent checkers. Much of its semantic representation still uses string
operation tags and dynamic attribute mappings. We want a statically typed
implementation suited to symbolic transformations while retaining Python's
scientific and authoring interfaces.

## Decision

1. Use TypeScript, HTML and CSS for Studio presentation, editing, diagrams,
   inspection and diagnostics. Browser types do not grant semantic authority.
2. Keep Python for the public DSL, SDK, notebooks, CLI, conversational proposal
   orchestration, scientific adapters and exploratory candidate search.
3. Implement canonical intent validation, behavioral semantics, mechanism and
   component contracts, deterministic compilation, molecular construction,
   independent checking and canonical output content in OCaml.
4. Maintain distinct domain languages and versioned intermediate representations
   within that core. Use explicit variants, nominal identities, immutable
   snapshots and abstract validated types. Use advanced type features where
   they materially enforce an invariant, rather than making complexity a goal.
5. Keep producer and checker libraries structurally separate. The standalone
   verifier must not link producers, matching, synthesis or emitters. Source
   reference execution and reconstructed candidate execution remain separate.
   Record shared codecs, primitive semantics and canonicalization in the
   trusted-base inventory; sharing is not independent evidence.
6. Integrate first through a bounded, versioned local executable protocol.
   Python and Studio submit explicit data. Only the selected core owns fresh
   semantic acceptance for a migrated operation. Do not fall back to Python
   after an OCaml rejection, incompatibility, failure or timeout.
7. Preserve existing APIs, profiles, artifacts, diagnostics and validation gates
   unless an explicit versioned migration is documented. Freeze Python's
   actual canonical JSON and numeric behavior before porting it.
8. Preserve the separation of exact artifact identity, conditional modeled
   behavior, empirical support and human admission. Physical manufacture and
   cellular execution remain outside the software compiler boundary.
9. Do not introduce another primary core language during this migration.
   Specialized native acceleration or proof tools require a concrete later
   need. This decision does not require Rust, C, a solver or a proof assistant.

## Migration and validation

Begin with a capability/authority inventory and compatibility corpus. Build
OCaml decoding and independent checking of existing Python candidates before
replacing their producers. Use a current stateful architecture example as the
first vertical slice, then expand to every supported operation/profile and
historical public workflow.

Use both cross-implementation comparison and independent literal/mutation
expectations. Agreement with Python alone does not establish correctness.
Changing the implementation does not preserve old verification receipts:
record new tool identity and freshly check the exact integrated revision.

Keep native build and executable validation on hosted CI or an already
authorized remote environment under the repository's development protocol.
Package prebuilt supported-platform executables and compiled Studio assets.
Importing or running a released Python package must not silently build a
native toolchain.

The roadmap specifies per-layer work, independence boundaries, cutover,
rollback and completion gates. The planning increment implements none of the
language migration and makes no new claim of compiler or biological validation.

## Consequences

The compiler core gains implementation-level structural guarantees and a
clear executable boundary. Scientific experimentation and user authoring can
continue in Python, and Studio can evolve without becoming a second compiler.

We also take on OCaml expertise, native distribution, cross-language protocol
maintenance and a substantial conformance workload. The first slice measures
these costs and verifies the integration method. It does not waive any existing
semantic, independent-checking or release obligation.

OCaml typing does not prove transformation correctness or empirical biological
function. Correctness still depends on explicit semantics, independent checking,
scoped evidence and required validation.

This decision supersedes only the initial Python-only implementation choice in
[ADR 0001](0001-explicit-contracts-and-staged-compilation.md) as the future target.
The staged-contract architecture and all current product/evidence boundaries
remain in force. Current implementation descriptions remain accurate until
their corresponding migration tasks are completed.
