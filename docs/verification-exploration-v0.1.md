# Bounded verification exploration v0.1

`cellweave.verification.exploration` supplies explicit Boolean history enumeration,
seeded adversarial histories and failure-preserving history reduction. It calls a
supplied checker on finite histories. It does not establish universal temporal,
whole-profile or biological refinement.

## Exact bounded enumeration

`BooleanObservation(signal_id, field="present")` selects one Boolean field:
`present`, `high` or `low`. A `BooleanContactConfig` declares named contacts,
observations, a variable time lattice beginning at zero, an explicit horizon,
an optional fixed suffix and an evaluation cap.

For `O` observations and `C` contacts, each snapshot has
`state_count = (1 + 2**O)**C` states. Each contact is either absent or present with
one complete Boolean assignment. Absent differs from present with every field
false. With `T` variable times, the exact history count is
`possible_histories = state_count**T`.

Only those variable times are enumerated. Every history then receives the same
fixed suffix, whose timestamps must follow the variable lattice and remain within
the horizon. Complete snapshots contain only the declared contact identities and
Boolean fields; this profile does not enumerate cell-local signals, numeric values,
additional contacts or arbitrary transition times.

| Configuration | Supported bounds |
| --- | --- |
| Named contacts | 1–8 |
| Distinct `(signal_id, field)` observations | 1–8 |
| Variable timestamps | 1–16, strictly increasing from zero |
| Horizon | Finite, nonnegative and no earlier than the last snapshot |
| `max_histories` | 1–100,000; default 10,000 |

`enumerate_boolean_histories(config)` lazily yields a deterministic prefix of at
most `max_histories` histories. Declared contact/observation order and the time
lattice determine that order. `explore_boolean_histories(config, check)` evaluates
the prefix and retains its `CheckResult` records in an `ExplorationReport`.

The report separates enumeration coverage from checking outcomes:

- `complete` means that every history in these exact bounds was evaluated.
- `all_passed` requires complete enumeration and `PASS` for every result.
- `outcome_counts` retains `FAIL`, `UNKNOWN` and `UNSUPPORTED` separately.
- `coverage_totals` sums recorded per-requirement deadline/episode counts across
  histories; it does not expand the declared state or time bounds.

A capped prefix is incomplete even if every evaluated history passes. Complete
enumeration can still contain unknown or failing results. Neither case may be
reported as a proof beyond the declared finite lattice and exact suffix.

## Checker callback contract

The callback has the form `check(history, *, until) -> CheckResult`. Each result
must identify the exact supplied history and explicit horizon. Across calls,
request, model, contract, domain, target and tool dependencies must remain fixed,
as must the checked requirement inventory. Stale or unrelated results are rejected.

For example, a caller can close over a frozen request and candidate and call
`check_synthetic_candidate(request, candidate, history, until=until)`. The existing
checker then establishes its own narrow finite-history claim.

The callback is trusted executable code chosen by the caller. Matching dependency
hashes cannot turn a fabricated callback result into an independent proof. The
callback must also be deterministic for a fixed history, horizon and dependency
set; the exploration utilities do not establish that property themselves.

## Seeded adversarial histories

`AdversarialConfig(bounds, seed, random_cases=16)` requires at least three variable
timestamps, a seed from `0` through `2**64 - 1`, and `0–1,000` seeded cases. The
history generator returns four fixed patterns—startup active, rapid oscillation,
contact dropout/reappearance and absent contacts—plus the requested seeded cases
and one intentionally incomplete-observation diagnostic case.

Seeded assignments use an exploration-version/seed/case/step SHA-256 counter.
They are deterministic stress samples, not a coverage or probabilistic guarantee.
The total is `random_cases + 5`; the finite enumerator's `max_histories` does not
replace this separate case-count setting. Every case retains its configuration
fingerprint, explicit horizon and exact fixed suffix.

The diagnostic case removes one required Boolean observation and carries
`intentionally_incomplete=True`. It is not a complete member of the enumeration
space. Callers retain the checker's diagnostic outcome rather than treating the
missing field as false or silently repairing it.

## Failure-preserving deletion

`reduce_counterexample(history, until, check, signature, max_evaluations=1000)`
selects a failure explicitly through `FailureSignature.from_counterexample(...)`
or `.from_diagnostic(...)`. The budget is 1–100,000 checker calls, including the
initial evaluation.

A response signature retains the requirement, rule, action specification, contact
binding and expected active/inactive state. A diagnostic signature retains its
code, requirement and node identity. The reducer preserves this signature within
an explicit `FAIL`; `UNKNOWN`, `UNSUPPORTED`, a passing result or an unrelated
failure cannot replace the selected counterexample. The witness timestamp can
change while the selected failure identity remains the same.

Reduction deletes snapshots only. It preserves the initial snapshot exactly,
keeps surviving snapshots unchanged and fixes the original horizon and all
non-history dependencies. It tries deletions in deterministic order and restarts
after each successful deletion. It does not rename contacts, edit observations,
move timestamps or shorten the horizon.

`one_minimal=True` means no single remaining noninitial snapshot can be deleted
while retaining the selected failure, under the deterministic callback. It does
not mean globally shortest. If the budget prevents completing that scan,
`one_minimal=False` explicitly withholds the minimality claim; `evaluations` records
the calls used. `reducer_version` pins the reduction policy. The original and reduced
histories and their check results remain available for diagnosis.

## Runnable campaign and saved evidence

Run the [verification campaign](../examples/verification_campaign.py) with:

```sh
PYTHONPATH=src python examples/verification_campaign.py
```

Its declared two-contact, two-observation space has 25 snapshot states. Two
variable times produce 625 histories, followed by an exact active/inactive suffix;
the horizon is seven seconds. All 625 pass within those bounds. A separate seeded
campaign produces 21 cases, retaining eight `PASS` and thirteen `UNKNOWN` outcomes.
The delayed-model counterexample reduces from seven snapshots to two while
preserving the selected failure. These are software-model regression results,
not universal or empirical claims.

Add `--output DIRECTORY` to save the bounded report, adversarial configuration and
case histories, and reduced failure. Versioned imports validate their schemas,
recorded identities, derived counts and structural consistency. Imported reports
are historical evidence: parsing does not execute callbacks, freshly recheck
models, prove enumeration outcomes or establish deletion minimality. Fresh reuse
requires current trusted checker execution with the declared inputs.

The [semantic regression matrix](semantic-regression-matrix-v0.1.md) separately
checks literal timelines and behavior-preserving transformations. It complements
these bounded campaigns without extending the supported synthesis profile.
