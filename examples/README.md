# Examples

[intent_programs.py](intent_programs.py) builds six complete programs: contextual
clearance, priming and phases, temporal response, graded secretion, feedback
regulation, and cooperation between cell roles. Each function returns an immutable
`IntentProgram` for inspection or serialization.

From the repository root, with Python 3.11 or later:

```sh
PYTHONPATH=src python examples/intent_programs.py
```

All biological names and parameters are symbolic. These examples construct intent
graphs; they do not choose molecular mechanisms or generate therapeutic sequences.
See the [v0.1 API reference](../docs/intent-api-v0.1.md) for the vocabulary and its
meaning.

[behavior_trace.py](behavior_trace.py) lowers a generic authored program and evaluates its abstract output requests against contacted-object histories. Internal timers execute between input snapshots. Run `PYTHONPATH=src python examples/behavior_trace.py`; no molecular model is involved.

[realization_check.py](realization_check.py) binds an explicit output contract to the behavior and automatically generates a combinational candidate and checks it with an independent runner. It demonstrates passing behavior, silent and late counterexamples, and stale evidence after a model change. Run `PYTHONPATH=src python examples/realization_check.py`. This fixture tests the checker; it provides no biological evidence or sequences.

[checked_pipeline.py](checked_pipeline.py) freezes build authority, runs two checked passes, checks a generated candidate and demonstrates automatic transitive invalidation. Run `PYTHONPATH=src python examples/checked_pipeline.py`. Its completion scope is a synthetic finite history; molecular obligations remain unresolved.

[component_linking.py](component_linking.py) extends the synthetic pipeline to locked component contracts and separately inspects a pinned FAP RNA-CDS reference. Run `PYTHONPATH=src python examples/component_linking.py`. It preserves finite-history evidence and CDS-only scope; no molecular sequence is emitted.
