# Roadmap

The repository begins as an architectural skeleton. Progress should be measured by a small, reviewable vertical slice with explicit acceptance criteria, not by the number of directories or supported concepts.

## 0. Establish the scaffold — implemented

Provide the Python package layout, shared stage and target vocabulary, compiler pass interfaces, and a CLI that lists the planned stages. Reserve modules for future IR schemas. Document what is implemented and what remains conceptual. Do not present the scaffold as a sequence generator or validated biological compiler.

## 1. Define the intent API and its semantic core — implemented in v0.1

The [v0.1 API](intent-api-v0.1.md) implements a broad intent language for in-vivo immune-cell engineering. It includes cell roles, observations, conditional and quantitative responses, memory, phases, communication, and immutable JSON snapshots.

The authoring surface is implemented across these concepts. Planning inspection validates typed parameter bindings and reports unresolved choices. Defining an intent does not require an available molecular realization.

Deliver an inspectable intent representation and diagnostics for undefined semantics. Use synthetic fixtures to test the compiler infrastructure; label them as fixtures rather than biological evidence.

## 2. Build the first checked lowering

Build the first intent-to-behavior pass on the implemented Python authoring interface. Preserve source locations and requirement identifiers. Separate design-time Python evaluation from biological operators.

Acceptance requires reproducible serialization, clear failures for unsupported operations, and tests showing that scope and timing constraints survive lowering.

## 3. Add one modeled realization path

Choose one payload modality, one bounded cell context, and a small behavior set for the first realization path. Define mechanism and component schemas, observation mappings, and a minimal versioned registry. Select a tightly scoped model and define its applicability assumptions. Keep the candidate generator separate from the checker.

Deliver an end-to-end modeled example whose record distinguishes exact checks, model-based results, empirical support, and unresolved obligations. Missing evidence must remain visible. This milestone alone does not establish therapeutic validity.

## 4. Connect constructs to molecular specifications

Implement the selected target backend, explicit construct composition, and exact molecular specification emission for its supported domain. Add invalidation rules so sequence or composition changes trigger affected higher-level analyses.

Acceptance requires traceability from every emitted component to source requirements, deterministic build identities, and rejection when a requirement has no supported realization. Exact artifact generation must not be reported as verified biological performance.

## 5. Package and extend deliberately

Emit a deployment manifest, source maps, locked dependencies, and a machine-readable verification record. Add interoperation only where it supports a concrete workflow. Physical manufacture remains external.

Expand language features and molecular targets as separate tracks. Language extensions need defined semantics, inspectable representations, and preservation checks. Realization extensions additionally need supported mechanisms, diagnostics, and appropriate evidence. Add a second DNA/RNA target as a separate backend rather than assuming equivalent mechanisms across modalities.

See [architecture](architecture.md) for the intended module boundaries.
