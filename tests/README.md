# Test boundaries

The standard-library `unittest` suite exercises the authoring API and its serialized
intent graph. Run from the repository root with Python 3.11 or later:

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
