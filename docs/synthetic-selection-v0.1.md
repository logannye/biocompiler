# Bounded synthetic implementation selection v0.1

M3.7 adds a choice between two concrete digital graphs under frozen software
constraints. It uses the existing synthetic catalogs, exact component locks,
source maps and independent realization checker. It supplies no molecular design,
biological cost, empirical evidence or human therapeutic admission.

## Authored controls and concrete alternatives

The `BuildRequest` fields become authority before Behavior lowering:

```python
implementation_constraints = {
    "allowed_operators": ["input", "constant", "or", "not", "select", "any_contact", "output"],
    "max_gate_count": 6,
}
preferences = {"minimize": "gate_count"}
```

Both constraint keys are optional. Missing `allowed_operators` permits the
selected profile's catalog; an explicit empty list permits no operators. Names
must be unique and belong to that catalog. The constraint applies to every actual
graph operation, including input/constant/output. `max_gate_count` is a
nonnegative integer with an inclusive limit; null, Boolean and negative values
are rejected. Unknown constraint and preference keys are rejected.

`minimize` supports exactly `gate_count` (also the absent-key default) and `none`.
The cost model `biocompiler.synthetic.gate_count.v0.1` counts each graph node once
except `input`, `constant` and `output`. Boolean logic, comparisons, selection,
contact aggregation, timers, onset detectors and latches each cost one. A node
shared by two downstream consumers counts once. Fan-in, runtime activity, contact
population and molecule count are not weights. This is a software graph metric,
not hardware area, latency, nucleotide length or biological efficiency.

The complete search space contains exactly two whole-program strategies:

1. `native`: each source conjunction uses one native `and` operation.
2. `de_morgan`: each source conjunction becomes `not(or(not(a), not(b), ...))`.

Every conjunction uses the same selected strategy. Disjunctions, temporal
operators, output bands and durations are unchanged. There is no mixed per-node
strategy search, algebraic simplification, arbitrary optimization, solver or
hidden random seed. A program without conjunctions retains two strategy records
even when their mechanism graphs coincide; this does not enlarge the search
space. Equivalent rewrites stay inside the original cell/contact scope. An
entire contacted-object guard is evaluated before cell-level aggregation.

## Proposal, checking and selection

```python
from biocompiler.synthesis.selection import select_synthetic

result = select_synthetic(request, history, until=7, config=config)
candidate = result.candidate  # None unless at least one checked alternative passed
```

The caller's profile, catalog pin, generator version and response-witness policy
remain fixed. `conjunction_strategy` is explicitly the configuration axis varied
by this search; both values are enumerated regardless of the initial value in
`config`. Each generated alternative records its concrete configuration.

For each strategy, selection generates an unaccepted graph and recomputes its
hard constraints. Rejected graphs retain their costs and specific constraint
violations. Every remaining graph is independently executed by
`check_synthetic_candidate`, even if an earlier graph passed. Only PASS graphs
can be ranked. Ranking uses software cost when requested, then the fixed order
`native` before `de_morgan`. Preferences cannot excuse a hard constraint or a
failed/unknown behavioral check. Behavioral evidence remains conditional on the
exact supplied history and horizon.

`generate_synthetic(request, config=...)` remains a deterministic,
history-independent proposal API. Its explicit strategy must satisfy the frozen
hard constraints. It does not execute candidates, rank preferences or claim
acceptance; use `select_synthetic` for that workflow. The independent candidate
checker also enforces hard constraints against the candidate's actual graph, so
editing a checked graph or refreshing component hashes cannot bypass authority.

## Reports and failure outcomes

`SyntheticSelectionResult` retains request/history identities, explicit horizon,
original configuration, cost and selection tool versions, both concrete
alternatives, constraint failures and independent check records. Its derived
selection, costs and counts must agree during strict JSON import. The result
binds every check to the same request, history, horizon and corresponding
candidate. Imported reports are historical records; fresh selection must rerun
the current trusted generator and independent checker.

Outcomes are deliberately separate:

| Outcome | Meaning |
| --- | --- |
| `selected` | At least one alternative passed hard constraints and independent finite-history checking; the deterministic ranking selected it. |
| `unknown` | No alternative passed and at least one eligible alternative's behavioral check was UNKNOWN. |
| `unsupported` | No alternative passed or remained UNKNOWN, and generation/checking encountered an unsupported operation/profile. |
| `exhausted` | Both strategies were rejected by hard constraints or failed their finite-history checks. This establishes only that this fixed search produced no accepted candidate. |

No outcome claims global optimality, biological feasibility or universal
behavior. Unexercised active/inactive responses remain UNKNOWN. Search exhaustion
does not prove that another implementation family is impossible.

The generator uses version `v0.4`, acceptance `v0.5`, generator-configuration schema
`v0.3` and candidate schema `v0.4`. Older pins need fresh regeneration and checks;
version relabeling is not migration. The catalogs reuse the existing pinned
operators rather than introducing fictitious molecular implementations.

Run `PYTHONPATH=src python examples/synthetic_selection.py` for least-gate,
AND-forbidden and exhausted cases. Focused tests cover actual graph changes,
inclusive budgets, hard-constraint precedence, deterministic ties, strict
authority/serialization, UNKNOWN, temporal/contact source preservation and an
incorrect De Morgan mutant caught by independent execution.
