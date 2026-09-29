# Test boundaries

No semantic compiler passes exist yet. Hosted CI currently performs package and import smoke checks only.

- `unit/`: frontend types, diagnostics, serialization, and deterministic transformations.
- `semantics/`: properties and counterexamples for preservation of scope, time, context, and obligations.
- `integration/`: end-to-end builds using explicitly documented fixtures and implemented backends.

Add meaningful tests with each implemented behavior. Avoid tests that simply reproduce constants or mistake structural identity for biological validity.
