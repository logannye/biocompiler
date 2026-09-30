# Proposed human profile and M10.6 completion scope

The proposed first behavior family is **reversible conditional secretion**:
one human recipient-cell role senses a declared extracellular cue, secretes a
declared product while its source condition requires activity, and returns to
background after the condition ends. M10.1–M10.5 provide the typed declarations,
finite supplied-observation checks and use-admission gates. M10.6 adds an
executable request-case suite and documents what completion means.

This is a frozen **software specification and example profile**, identified as
`biocompiler.proposed_conditional_secretion_examples.v0.1`. It is not an admitted
biological therapeutic profile. No corresponding `compile()` path is enabled.

## Proposed scope and unresolved choices

| Dimension | Present proposal | Required before biological profile admission |
| --- | --- | --- |
| Recipient | Human in-vivo engineering, one recipient role; the example names a CD8-positive T-cell family | Choose and support the precise subtype/state, tissue, disease and population applicability, including exclusions. |
| Payload modality | One RNA request with a declared cytoplasmic destination | Establish the complete delivered molecule, chemistry, expression and delivery relationships. DNA remains a separate future profile decision. |
| Source intent | One goal, extracellular signal, refined predicate, ongoing secretion rule and product | Resolve the cue/product identities and the relationship between the readout and the intended therapeutic benefit. |
| Runtime observations | Cell-accessible extracellular cue; explicit declared input-access loss | Establish sensing, accessibility and failure-response correspondence. |
| Evaluation observations | Per-cell secretion rate, healthy-context classification and external shutdown record | Establish measurements, healthy-context meaning and actuator/control support; evaluator measurements cannot silently become cellular signals. |
| Required behavior | Initialization, activation, persistence while required and recovery within explicit deadlines | Support quantitative response bounds and timing in the declared human context. |
| Prohibited behavior | Background/peak ceilings, prolonged response and activity after applicable loss/shutdown deadlines | Support the limits, uncertainty and implementation mapping, including conflicts with the original source guard. |
| Deployment | Pinned artificial delivery specification, recipient/exposure declarations and independent expression/behavior clocks | Select an evidence-backed platform and characterize exposure, delivery, expression, unintended recipients and any required coexistence. |
| Current output | Inspectable requests, traces, scoped check results, admission refusal and unresolved obligations | A complete molecular implementation and independently supported source-to-payload checks remain M11–M14 work. |

All quantitative values, classifications and trace trajectories in this suite
are invented software fixtures inherited from the earlier contract examples.
Their successful evaluation supplies no biological calibration. The broader
healthy range in the conflict case is also an artificial requirement mutation.
Missing target, measurement, delivery and actuator evidence remains visible even
in the positive case. The artificial delivery source bytes are retained so its
pin can be inspected without implying a real delivery technology.

## Request cases

Run from a checkout with Python 3.11 or later:

```sh
PYTHONPATH=src python3 examples/human_profile_cases.py --output generated/profile-cases
PYTHONPATH=src python3 examples/human_profile_cases.py --verify generated/profile-cases
PYTHONPATH=src python3 -m biocompiler inspect generated/profile-cases/positive/request.json
PYTHONPATH=src python3 -m biocompiler inspect generated/profile-cases/conflicting_healthy/acceptance.json
```

| Case | What changes | Acceptance | Deployment |
| --- | --- | --- | --- |
| `positive` | Full finite coverage with compatible invented declarations | PASS | PASS |
| `negative_silent` | Output stays silent when an active response is due | FAIL | PASS |
| `negative_peak` | Output exceeds the peak ceiling during activation grace | FAIL | PASS |
| `negative_expression_window` | Shorten the declared expression duration below required behavior coverage | FAIL | FAIL |
| `conflicting_healthy` | Broaden the requested healthy range so it includes an observed context while the source requires activity | FAIL, explicit required/prohibited conflict | PASS |
| `underspecified_deployment` | Remove expression and exposure bounds using their explicit unknown representations | UNKNOWN | UNKNOWN |
| `underspecified_observations` | One output interval is unobserved | UNKNOWN | PASS |
| `unsupported_co_payload` | Add a same-cell co-payload requirement | UNSUPPORTED | UNSUPPORTED |
| `unsupported_destination` | Request an RNA destination outside the implemented deployment profile | UNSUPPORTED | UNSUPPORTED |
| `failure_with_unknown` | Combine a measured peak violation with a missing output elsewhere | FAIL, with both diagnostics retained | PASS |

Every row separately reports **human admission: not admitted**,
**compilation: unavailable**, **mechanism search: not performed** and
**biological feasibility: unestablished**. These dimensions are not collapsed
into one success flag. A valid declaration with unknown values is different
from malformed input: deleting a required field, using incompatible units or
breaking source identity remains a schema/authority error.

PASS applies only to the finite supplied piecewise-constant observations and
compatible declarations. It requires active, inactive, ordinary recovery,
healthy, input-loss recovery and shutdown coverage. Missing output is different
from measured zero: the same interval is UNKNOWN when absent, FAIL when zero
violates a due active bound, and potentially PASS when the measurement satisfies
all exercised requirements. Known violations are retained alongside unknowns.

## Search exhaustion and demonstrated contradiction

`explore_traces()` is an example-only enumeration of an explicitly supplied,
ordered list of artificial observation trajectories. It does not search
mechanisms, components or nucleotide sequences. Each report retains the full
candidate inventory, its fingerprint, request fingerprint, budget, checked
results, witness and unchecked count.

The suite contrasts three runs against the same request:

1. The supplied silent and incomplete traces yield FAIL and UNKNOWN. Exhausting
   that two-candidate set reports `candidate_set_exhausted` and
   `infeasibility=not_established`.
2. A budget of one stops before visiting the remaining candidates, reporting
   `budget_exhausted` with a nonzero unchecked count.
3. Adding the positive trace and checking it yields `witness_found`. This
   demonstrates why exhaustion of the earlier list could not prove global
   infeasibility. The witness is a mathematical observation trajectory, not an
   implementation or a prediction that a cell can produce it.

The conflict example provides a different kind of evidence. **Conditional on a
due active source requirement and an observed healthy context**, the same output
must satisfy the active lower rate bound and the healthy background ceiling.
The fixture requires `rate >= 2` and `rate <= 0.1` in the same `molecules/s`
per-cell fixture units, normalized by the checker before comparison. These intervals have no common value. The saved
`rate-conflict.json` explains that inequality directly from the frozen request,
independently of candidate output values.

That is demonstrated infeasibility of the **simultaneous rate constraints under
the stated condition**. It establishes neither reachability of the condition
in biology nor universal infeasibility of a therapeutic goal. A positive trace
that avoids the conflict is not a proof that all permitted input combinations
are compatible. Resolving a conflict requires explicit requirements work;
healthy classification and shutdown cannot silently override the source guard.
The suite does not add a general infeasibility solver or repurpose finite search
as one.

## Retained evidence and completion

Each case writes its full request, supplied trace, fresh acceptance and deployment
results, admission request/assessment and compilation diagnostics. `summary.json`
retains independent status dimensions, identities, coverage and unresolved
evidence. The suite/search/conflict summaries are explanatory example JSON,
not new compiler input schemas or admission tokens. Use the standard CLI to
inspect the underlying typed request/result files.

`--verify` regenerates authority and results from the current example source and
checks the complete saved file inventory and bytes. It does not read expected
results from the saved summary. Altered requests, historical PASS labels, stale
policy records, changed search inventories, extra/missing files and symlinks are
rejected. This is example regression verification, not a therapeutic build
verifier. Source files use logical checkout-relative names while retaining their
authored line/function correspondence; changing example source or tool policy
can require regeneration.

**M10.6 completion** means all five request categories are executable, status
distinctions and narrow proof scope are covered by regressions, examples can be
recomputed and inspected, and hosted Python 3.11/3.14 tests, packaging, examples
and CLI checks pass with the tested revision/platform recorded in the roadmap.
It does not complete M10's biological profile acceptance condition.

The next deliverable is **M11.1's human benchmark/evidence audit**. Resolve the
profile choices above against independently reviewable evidence, retaining
cell-line, primary-cell and in-vivo distinctions. Mechanism selection, complete
reference promotion, predictive validation and compiler admission remain
separate gates. Enable a corresponding `compile()` path only under M14 after
the required M11–M13 obligations pass. See the [roadmap](roadmap.md),
[acceptance contract](human-acceptance-contract-v0.1.md) and
[admission policy](human-admission-v0.1.md).
