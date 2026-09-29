# Checked pass manager v0.1

`compiler.pipeline.PassManager` accepts frozen inputs, registers trusted pass contracts and independent validators, and keeps accepted stages in memory. This profile enforces stage ordering, destination operation inventories, target applicability, source correspondence, required observation mappings, and dependency freshness. Molecular passes and persistent caching remain unimplemented.

## Authority and acceptance

Create a manager with an explicit `TargetContext`, a canonical `request` dependency identity, other pinned dependency identities, and named `CompletionProfile` records. `add_input` only admits Intent-stage inputs whose identity matches the request. A separate `ComponentInputContract` can admit an independently selected Components root through fresh registered checks, as described below. Input records are authoritative descriptions, not evidence that a downstream implementation exists.

A `PassContract` pins pass/profile versions, input/output schemas, supported target modalities and operations, capability requirements, consumed requirement IDs, assumptions, introduced obligations, required independent checks, and changed properties. A pass advances exactly one declared stage. `register` requires one provider for every contracted check. Changed providers require a contract version change. Compiler registrations and validator implementations are trusted code and need code review; this API is not a sandbox for malicious plugins.

`run` freezes configuration and dependency identities before calling the producer. The producer returns a `PassResult`, with its candidate, source links and optional observation map. It cannot redefine upstream obligations or supply its own accepted evidence. Empty producer obligation lists do not remove the manager's authoritative obligations. The current destination inventory is an explicit `nodes` array at the contract's declared `operation_path`; source inventories use the accepted parent contract's declared path, and strict artifact decoding belongs in the independently registered schema/preservation checks.

Validators receive a `PassContext` containing frozen input and output, target, requirements, source maps, observation map, configuration and dependency identities. Each returns `CheckDecision(pass|fail|unknown|unsupported, detail, evidence)`. All required checks must pass before the stage can be consumed downstream. A source map is correspondence, not a model-based behavioral certificate: every discharge must match the obligation's required evidence kind.

The manager retains rejected records for inspection but `get`, downstream `run`, and `result` refuse them. Exceptions cannot leave an accepted candidate. A `no_candidate_found` search result raises `NoCandidateFound` with the exact configuration and dependencies; it does not establish infeasibility.

## Dependency graph and freshness

Every accepted record carries its parent, pass contract identity, and the complete dependency snapshot available at that stage. `set_dependency` updates a root when a request, registry, model, reference or tool changes. `get`, `run`, and `result` automatically compare the current roots and walk accepted ancestors. Replacing an upstream pass contract therefore invalidates descendants even if their immediate output bytes have not changed. Changing a root during generation/checking also prevents acceptance.

Dependency changes must be supplied to the manager: it never fetches remote registries or guesses that files outside the frozen inputs changed. Target changes require a new manager. Existing records cannot be overwritten or imported as acceptance certificates. There is no persistent cache or untrusted record-import route. Independently selected structural roots enter through the checked component admission policy, never through an imported success record.

Within a transformation, `changed_properties` records the change. `invalidated_analyses` names obligation IDs whose prior discharges must be removed; those obligations require a new appropriate check. The compiler author must specify the affected analyses in the pass contract. Conservative dependency roots additionally invalidate all stages that consumed them, including layout/encoding/model changes.

## Scoped completeness

Acceptance of a stage and completion of a requested artifact are different. A `CompletionProfile` declares the terminal stage, exact output schema and required obligation IDs. `register_completion_profile` can add a new scope after initialization but cannot replace an existing scope or weaken its promise. `result(scope=...)` returns `partial` until that stage and every required obligation for the scope are satisfied. Unresolved obligations in other scopes remain listed even when the requested scope is `complete`.

For example, exact-CDS identity obligations can eventually be complete while full-payload and empirical biological obligations remain unresolved. There is currently no exact-CDS completion implementation. The first concrete integration is the synthetic finite-history profile, whose success remains conditional on its model, declared domain and exercised history.

`run_component_pipeline` extends the finite-history integration through a third checked pass. The `synthetic_components` scope requires inherited behavior preservation and response checks plus component linkage. Assembly acceptance verifies exact source correspondence as well as generic composition compatibility; a compatible rewired graph is insufficient.

## Determinism and tests

Pass configuration records search seeds and tie-breaking choices; the initial synthetic generator has deterministic catalog ordering and no randomized search. Canonical records are stable for identical frozen inputs and configuration. Source-bearing record provenance is archival metadata, separate from source-free semantic build identities.

`tests/test_pipeline.py` checks multi-stage invalidation, missing providers, wrong stage/schema/target, unsupported operations, source maps, immutable snapshots, self-certifying output, changed obligations, evidence-kind mismatch, explicit fail/unknown/unsupported results, scope completeness, invalidated analyses, repeated execution, and bounded-search failure. Persistent caching is intentionally deferred until a concrete storage design preserves these invariants.

## Checked component-root admission

Reference construction has no upstream behavioral realization to claim. `register_component_input` registers a trusted `ComponentInputContract` with exact schema, version, required dependency roots, source requirements, obligations and an independent provider for every declared check. `admit_component_input` is available only on a new manager with no records. It verifies the canonical input document against the frozen request root, the full target and unique component inventory, then executes every check. Only an all-pass record can be consumed by a real Components → Construct pass.

Admission does not accept a serialized success flag or trust a producer-defined fingerprint property. Input-policy/provider changes require version changes and stale all descendants. Dependency changes during checking also prevent fresh acceptance. The original Intent-only input API still rejects later-stage injection. This is trusted compiler configuration, like pass registration; an arbitrary always-pass plugin is not an independent checker.

`run_construct_pipeline` admits only the supported single-CDS reference authority and completes the `reference_construct` scope after layout/source checks and renewed conditional composition checks. Sequence emission, complete delivered-payload features and biological behavior remain separate unresolved obligations.
