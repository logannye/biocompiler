# Retained case B migration baseline

This corpus is B1.01 input inventory and **current Python baseline evidence**.
It grants no acceptance authority. No OCaml executable has produced any of its
results, and the artificial six-symbol RNA establishes no biological function
or human therapeutic admission. The pilot contract is
[migration-case-b.md](../../../docs/migration-case-b.md).

`base/request.json` is complete independent caller authority, produced by the
existing `examples.payload_architectures.make_architecture_request("B")` after
the deliberate source-coordinate transformation below. `base/candidate.json`
is the result of one call to the current Python producer. Do not use the
candidate's embedded request, PASS labels, construction assessment or hashes as
an expected answer. The future checker must independently reconstruct them.

`parameter-default/` and `parameter-override/` contain separate complete request
and candidate pairs. In each independently authored source and supplier graph,
the unique `held_for` duration edge is changed from a literal to a typed
`dwell_duration` parameter, defaulting to two seconds. The parameter is a graph
root and has no cell role, matching a design-time parameter. The override pair
freezes an explicit three-second binding for both separately authored programs.
The unchanged source graph has the same semantic identity between these two
variants; the frozen bindings and downstream identities differ. These are
explicit fixture authoring transformations, not checker normalization rules.

`expectations.json` is manually authored and is never generated from candidate
output. It retains node/runtime/state/five-output counts, binding values, exact
scope limits and literal settled-state timelines. Every timeline supplies all
three observations and an inclusive horizon. `descriptors.json` separately
retains planned positive/mutation cases and their intended checks. Descriptors
marked `native_execution: not_run` are not implemented native test coverage;
only explicit `python_evidence` fields identify the positives exercised here.
Mutation hash repair must reach the intended semantic check rather than count a
generic stale identity or unsupported-parameter failure as success.

The generator evaluates the literal timelines against the current Python
reference evaluator, checks all three candidates with the current Python
checker, and additionally rechecks the complete base candidate relabeled
`partial`. That relabel changes candidate identity but preserves independently
derived completeness. Its transformation and result are retained in the oracle
without duplicating the whole candidate. The producer is called once per
retained request. No export/assembler rerun is needed to manufacture another
copy of the candidate.

## Source coordinates and identity

Raw source programs capture absolute authoring filenames. Before any
`BuildRequest.freeze`, lowering, source-manifest derivation, supplier-model
freezing, full architecture request or candidate production, the generator
replaces only the checkout prefix with a repository-relative POSIX filename.
Lines and function names are preserved. A source path outside the selected
checkout is rejected rather than silently normalized. Both independently
authored functions are normalized independently.

`source-coordinates.json` records original coordinates with the variable prefix
spelled `<checkout>/`, canonical coordinates and pre-/post-normalization Intent
fingerprints. This prefix token documents the actual original path relation; it
is not a claim that the original raw bytes were retained verbatim. Parameter
variants also record the distinct post-authoring-transform Intent fingerprint.
No absolute machine path is part of the reproducible corpus. Intent semantic
and BuildRequest semantic fingerprints exclude source locations and remain
unchanged by relocation. BuildRequest archival identity and the enclosing full
architecture request identity include the relocated data and are recomputed by
normal constructors before candidate generation. No output hashes are patched
after serialization. Moving the checkout therefore reproduces the same bytes;
moving lines in the authoring example deliberately changes this archive.

## Regeneration and checking

From an environment with the package installed:

```sh
python tools/freeze_migration_case_b.py --check
```

For an explicitly selected local source check, without installation or native
build:

```sh
PYTHONPATH=src python3 tools/freeze_migration_case_b.py --check
PYTHONPATH=src:tests python3 -m unittest test_migration_case_b
```

Omit `--check` only to deliberately regenerate the retained Python baseline
after reviewing any changed literal expectations and intended migration scope.
`--corpus DIR` selects a separate directory that already contains the two
literal JSON files. The generator imports the selected `biocompiler` first and
then adds the repository only to load examples; it never chooses `src`, installs
packages, compiles native code or runs a native executable implicitly.

All generated JSON uses UTF-8, sorted object keys, two-space indentation and one
terminal newline. `current-baseline-oracle.json` hashes exact retained bytes
(including literal inputs) and records semantic/request/candidate identities,
Python checker outputs and matched literal expectations. `schema-census.json`
lists every nested versioned record path and its field set in both inputs.

`generation.json` records the historical Python/platform/machine, generator and
package versions, source-file digests for the **actually imported** Python
package and examples, and the baseline-oracle byte hash. This metadata lives
outside all request/candidate identities. Its Git revision is context, not a
claim of a clean checkout: source byte hashes identify uncommitted code too.
`--check` regenerates every deterministic output and compares without repair;
it preserves the historical generation platform and prints the current check
platform separately. Cross-platform checks must not rewrite the historical
receipt just to match their current platform. Historical source digests are not
substituted for fresh comparison, and the stored Python PASS is never an OCaml
certificate. Preserve all existing unit/integration/native validation gates.
