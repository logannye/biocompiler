# ADR 0001: Explicit contracts and staged compilation

- Status: Accepted for the initial scaffold
- Date: 2026-09-29

## Context

biocompiler explores compilation from an immune-cell engineer's high-level intent to an exact DNA or RNA payload specification. A single translation from Python to nucleotide letters would hide the mechanism choices and assumptions that give the result meaning. The project also needs to distinguish exact artifact identity from conditional predictions of cellular behavior.

## Decision

1. Use Python for the initial implementation, with a standard-library-only runtime. Do not introduce Rust or native compilation in the scaffold. Any future local Rust compilation requires explicit authorization under the user's development preferences; use hosted CI or an already-authorized remote environment by default.
2. Model compilation as explicit stages: typed intent, behavior, mechanism, components, construct, molecular specification, and deployment artifact. Begin with shared vocabulary and pass interfaces; add stage-specific schemas with their semantics.
3. Add a restricted, typed Python DSL later. Python constructs the design; biological operations describe the eventual system. Unsupported or ambiguous semantics must stop the affected compilation path with a diagnostic.
4. Treat a behavioral contract, its operating context, and requirement identities as persistent compilation inputs. Every lowering must preserve them or explicitly report a required contract change.
5. Separate synthesis from verification. Distinguish exact structural checks, conditional model-based results, empirical support, and unknown outcomes. Do not convert uncertainty into a successful check.
6. Maintain separate DNA and RNA backends. Their capabilities influence mechanism selection before final sequence emission.
7. Define the compiler output as an exact **digital molecular specification** and deployment manifest. Physical manufacture and in-vivo execution remain outside this compiler.

## Consequences

The initial package is intentionally small and does not compile biological programs or generate therapeutic sequences. New features require an explicit semantic definition and preservation checks, not just a new frontend function.

Versioned IRs, source maps, dependency tracking, and per-pass provenance become core architecture. Changes at the sequence level may invalidate higher-level analyses. Models can support conditional refinement claims, but cannot by themselves guarantee biological outcomes.

This structure adds deliberate work before broad language support. In return, unsupported requirements, evidence gaps, and implementation assumptions remain visible and reviewable.

See [architecture](../architecture.md) and [roadmap](../roadmap.md).
