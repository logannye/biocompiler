# Test boundaries

The standard-library `unittest` suite exercises the authoring API and its serialized
intent graph, checked lowering, and abstract execution histories. Run from the repository root with Python 3.11 or later:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover complete programs, role and target associations, temporal and state
semantics, quantitative typing, communication, inert actions, declaration conflicts,
immutable snapshots, deterministic serialization, and the explicit boundary between
an intent plan and sequence generation.

These tests validate the software representation of authored intent. They do not
validate molecular realization, biological behavior, or clinical performance. Exact-reference DNA/RNA backends are exercised separately from general
molecular realization, which remains unsupported.

Behavior tests exercise identity-preserving contact binding, exact temporal boundaries, concurrent updates, memory and repeated triggers, serialization and source correspondence. Malformed IR, unsupported lowering and incomplete histories must fail explicitly.

Realization tests independently execute synthetic candidates, exercise active and inactive output contracts, and reject silent, late, wrongly scoped or incorrectly mapped candidates. Coverage tests distinguish unexercised or unfinished responses from success. Artifact and freshness tests check strict serialization, immutability, context/parameter changes, and dependency completeness. Synthetic signal-graph correctness does not validate molecular performance.

Build-request tests cover coordinated binding tampering, strict round trips, input immutability and two-phase identities. Pipeline tests cover provider contracts, source/observation maps, scoped completeness and transitive invalidation. Reference tests compare independently frozen sequence records with retained sources and mutation failures. Generation tests include 256 bounded two-object Boolean transitions; this does not assert universal or empirical correctness.

Component tests exercise typed/semantic interface mismatches, directional domain inclusion, initialization, missing and ambiguous providers, circular dependencies, shared resource capacities and lifecycle reuse, exact registry/model/reference locks, deterministic hard-constraint selection, reference-only classification, graph tampering and transitive pipeline invalidation. Provider and capacity declarations are test assumptions, not biological measurements.

Construct tests reject changed membership, swapped versions/references, reversed orientation, frame errors, off-by-one coverage, invented features, unsupported junctions/multi-molecule assembly and weakened unknown-feature metadata. They mutate authority and candidate together to ensure matching producer claims cannot establish their own validity. Admission and pipeline tests cover forged fingerprints/receipts, source maps, complete-scope limits, dependency changes and layout evidence invalidation.

Molecular tests compare independent DNA/RNA/protein expectations, distinguish synonymous nucleotide mismatch from protein consistency, and reject missense edits, truncation, wrong alphabets, frame/termination errors, invented features and stale locks. Export checks distinguish canonical sequence hashes from wrapped FASTA/JSON file hashes and reject corrupted or mismatched content. Scoped pipeline tests retain unresolved full-payload and empirical obligations.
