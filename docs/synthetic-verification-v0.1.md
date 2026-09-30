# Reusable synthetic verification v0.1

The verification workflow accepts immutable JSON requests for a finite-history
check, bounded Boolean exploration or selected-failure reduction. It uses the
existing candidate checker, independent realization checker, enumeration engine
and reducer. It never imports an executable callback, runs authoring Python from
an input document or retrieves an outside data source.

These operations retain `PASS`, `FAIL`, `UNKNOWN` and `UNSUPPORTED` separately.
They do not require a passing build before checking a candidate: an all-inactive
history can be checked and recorded as `UNKNOWN`, and a wrong-reset mechanism can
retain its actual response counterexample. No workflow result admits molecular
compilation, human therapeutic use or biological performance.

## Complete operation authority

`SyntheticVerificationRequest` (`biocompiler.synthetic_verification_request.v0.1`)
contains a frozen `RealizationRequest`, an explicit `SyntheticCandidate`, a mode,
and exactly one operation's inputs:

| Operation | Required inputs | Other operation inputs |
| --- | --- | --- |
| `check` | `history`, explicit `until` | Empty/null |
| `explore` | `bounds` | Empty/null |
| `reduce` | `history`, explicit `until`, `signature`, `max_evaluations` | `bounds` null |

JSON always includes all declared fields, using `history: []` and null for unused
fields. Histories use complete `InputFrame` snapshots with explicit `SignalSample`
fields, start at zero and strictly increase within their finite horizon. Inputs
are frozen recursively. Duplicate JSON keys, unknown fields, unsupported schemas,
malformed histories and unused operation controls are rejected.

The request's canonical fingerprint binds the realization, candidate, mode and
all operation controls. A separate realization-only identity is insufficient:
changing the history, time lattice, fixed suffix, horizon, budget or selected
failure changes the trusted operation. Canonical numeric spelling is preserved;
integer `9` and floating `9.0` have different artifact identities.

The modes make different checks explicit:

- `candidate` reruns `check_synthetic_candidate`, including current hard selection constraints,
  source correspondence, component identities and independent finite-history
  response checking. This is the default.
- `model` calls the independent `check_realization` on the supplied candidate's
  mechanism and observation map. It supports explicit diagnostic mutants and
  makes no candidate-provenance, generation or component-admission claim.

Both modes retain current checker/model dependencies. A model-mode `PASS` is not
candidate acceptance. No mode upgrades bounded model evidence into empirical or
universal evidence.

## Mixed cell and contact exploration

`BooleanInputConfig` adds `cell_observations` to the existing contact bounds. The
remaining fields are `contact_ids`, `observations` (contact Boolean fields),
`variable_times`, `until`, `fixed_suffix` and `max_histories`. Every observation
is a `BooleanObservation(signal_id, field)`, where the field is `present`, `high`
or `low`.

For `L` cell fields, `O` contact fields and `C` named contacts:

```text
state_count = 2**L * (1 + 2**O)**C
possible_histories = state_count**len(variable_times)
```

Cell fields are always explicitly observed. Each contact is absent or present
with one complete Boolean assignment; absent differs from present with all fields
false. Cell bits vary fastest within each snapshot; declared contact/observation
order and the fixed time lattice determine a reproducible enumeration order.

Bounds allow zero to eight cell fields, zero to eight contacts with zero to eight
contact fields, and one to sixteen increasing variable times starting at zero.
At least one observation is required. Contact IDs and contact observations must
both be present or both be empty. A signal cannot be declared in both scopes.
Cell-only enumeration is supported. The fixed suffix must follow the variable
times, remain inside the explicit horizon and contain the exact declared signal
inventory. The cap is one to 100,000 histories.

The new configuration and report have distinct versioned schemas. Existing
`BooleanContactConfig` ordering, counts, reports and seeded adversarial behavior
remain unchanged. The existing seeded adversarial helper is still contact-only;
this workflow does not relabel those samples as mixed-input coverage.

`BooleanInputExplorationReport` retains exact bounds, declared state/history
counts, evaluated count, outcome counts, coverage totals and shared dependency
identities. `complete` means the exact finite space was exhausted. `all_passed`
requires complete enumeration and a `PASS` for every history. A passing capped
prefix has both flags false. Complete enumeration containing `UNKNOWN` also has
`all_passed=False`. Enumeration does not cover arbitrary times, additional input
fields, additional contacts or infinite histories.

## Execute, retain and replay

The public functions are:

```python
record = run_synthetic_verification(operation_request)
restored = replay_synthetic_verification(
    imported_record, expected_request=independently_retained_operation_request
)
```

`SyntheticVerificationRecord` contains the full operation request, its matching
`CheckResult`, exploration report or `ReductionResult`, and the workflow version.
Its JSON parser checks structural consistency and derived counts. Parsing is
historical inspection: it does not establish that any stored result was obtained
from the current checker or that a reduction is minimal.

Fresh replay first compares the independently supplied complete operation's
canonical fingerprint with the saved operation, then reruns it using current
trusted code and compares the complete resulting record identity. Recomputed
self-hashes cannot authorize a narrowed campaign, changed observations, altered
candidate, forged result or stale checker. Independently retain the request when
it is created; a request taken from the same untrusted report is not independent
authority.

The CLI maps `synthetic-check`, `synthetic-explore` and `synthetic-reduce` to these
three operation kinds using `--request` full-operation JSON. The operation kind
must match the command. `synthetic-replay` requires a saved record and independent
complete operation authority. Import never executes Python supplied by the user.

## Reduction preserves the selected failure

Reduction reuses `reduce_counterexample` and the existing `FailureSignature`.
Response signatures retain requirement, rule, action specification, contact and
expected active/inactive state. Diagnostic signatures retain diagnostic code,
requirement and node. Only an explicit `FAIL` with the selected signature can
replace the original witness; a different failure, `UNKNOWN`, `UNSUPPORTED` or
`PASS` cannot substitute.

The reducer deletes noninitial snapshots only, preserving the initial snapshot,
surviving snapshot contents, horizon and all non-history dependencies. Its
explicit budget includes the initial evaluation. It retains the original and
reduced results and records evaluation count. `one_minimal=True` means no one
remaining noninitial snapshot can be deleted while preserving this selected
failure under the deterministic checker; it does not mean globally shortest.
An exhausted budget sets `one_minimal=False`.

## Runnable code-only example

```sh
PYTHONPATH=src python examples/synthetic_verification.py \
  --output generated/synthetic-verification
```

Run its saved operations directly through the CLI:

```sh
PYTHONPATH=src python -m biocompiler synthetic-check \
  --request generated/synthetic-verification/check-request.json \
  --output generated/synthetic-verification/check-fresh.json
PYTHONPATH=src python -m biocompiler synthetic-explore \
  --request generated/synthetic-verification/exploration-request.json \
  --output generated/synthetic-verification/exploration-fresh.json
PYTHONPATH=src python -m biocompiler synthetic-reduce \
  --request generated/synthetic-verification/reduction-request.json \
  --output generated/synthetic-verification/reduction-fresh.json
PYTHONPATH=src python -m biocompiler synthetic-replay \
  generated/synthetic-verification/reduction-record.json \
  --expected-request generated/synthetic-verification/reduction-request.json
```

Exit status is zero for a passing check, complete all-passing exploration or
completed one-minimal reduction; one records a nonpassing/incomplete outcome;
two reports malformed input or a failed operation. Replay returns zero when fresh
execution reproduces the independently authorized record, including a retained
failure; it does not turn that failure into `PASS`. JSON reports are written
atomically, retain diagnostic outcomes and cannot overwrite the command's input
authority. Their parent directory must exist. Request input is capped at 16 MiB;
reports are capped at 64 MiB. Lower campaign budgets when a full report would
exceed the output limit.

The example retains independent request and historical record files for a normal
check, mixed exploration, wrong-reset diagnostic check and reduction. Its bounds
include one contact with two Boolean markers and one cell-local reset: ten
snapshot states at two variable timestamps yield 100 histories, each followed by
the exact suffix at seconds 2, 5, 6 and 8, through horizon 10. All 100 pass this
finite campaign. An explicitly supplied model that ignores reset fails and
reduces from five snapshots to three while preserving the memory readout's
inactive-response failure. These are deterministic software regressions.

See [bounded exploration](verification-exploration-v0.1.md),
[temporal semantics](synthetic-temporal-v0.1.md) and
[synthetic packages](synthetic-build-v0.1.md) for the underlying evidence boundaries.
