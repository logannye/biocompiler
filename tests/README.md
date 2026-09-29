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
validate molecular realization, biological behavior, or clinical performance. There
is no implemented sequence-generation backend to exercise yet.

Behavior tests exercise identity-preserving contact binding, exact temporal boundaries, concurrent updates, memory and repeated triggers, serialization and source correspondence. Malformed IR, unsupported lowering and incomplete histories must fail explicitly.

Realization tests independently execute synthetic candidates, exercise active and inactive output contracts, and reject silent, late, wrongly scoped or incorrectly mapped candidates. Coverage tests distinguish unexercised or unfinished responses from success. Artifact and freshness tests check strict serialization, immutability, context/parameter changes, and dependency completeness. Synthetic signal-graph correctness does not validate molecular performance.
