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
