# ADR 0003: independent candidate execution and scoped evidence

Status: accepted for the first realization-checking profile.

## Context

Behavior IR and its evaluator define what an authored program requests. Copying those requests into a candidate model would make preservation checks circular. Structural lineage also cannot establish latency, response magnitude, or correct contact binding.

## Decision

Keep the reference evaluator, candidate model runner, and acceptance checker separate. Implement a synthetic typed signal graph before introducing molecular models. Bind requested actions to explicit endpoint contracts through observation mappings, under a declared operating domain and target context.

Report `pass`, `fail`, `unknown`, and `unsupported` separately from evidence kind. Results identify their finite history, exercised requirements, counterexamples, and exact dependencies. A response that was never exercised or whose deadline is unfinished cannot support a complete passing claim. Contract changes are visible artifact changes, never a hidden synthesis operation.

Store dependency identities with each result and compare them before reuse. Content hashes establish reproducible identity, not biological truth or authentic execution.

## Consequences

We can test the preservation machinery with deliberately wrong candidates before relying on it for molecular design. The first runner is independently executable and exact for its declared discrete-event semantics. Its success establishes only a finite model-conditional claim.

Continuous models, empirical calibration, population behavior, full assumption composition, host/payload linking, and sequence emission require further profiles. Their absence does not restrict the authoring vocabulary: unsupported realization remains explicit.

See [realization checking](../realization-checking-v0.1.md) and [toolchain contracts](../toolchain-contracts.md).
