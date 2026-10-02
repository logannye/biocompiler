# Native workflow presentation handoff

Reviewed against PR59 checkpoint `4d14a08` on 2026-10-02. Design only;
no production edits or native execution were performed for this follow-up.
Implementation has not started; this plan is retained in the separate public-workflow checkpoint.

## Native authority and control size

`cli.py::_verification_summary` currently supplies check diagnostics,
counterexamples and coverage; exploration bounds and native derived properties;
or reduction result, minimality, evaluation count and frame counts.
The full summary can approach the complete artifact size. Do not put that
summary or its JSON text inside the artifact channel's 65,536-byte control
receipt: that would narrow the supported 64 MiB workflow artifact boundary.

Recommended compact receipt addition:

```json
{
  "presentation": {
    "profile": "biocompiler.core.verification_workflow.presentation.v1",
    "command_exit_code": 0,
    "original_frames": null,
    "reduced_frames": null
  }
}
```

Frame counts are integers for reduction and null otherwise. Compute the exit
code in OCaml from the validated typed result: check `passed`, exploration
`all_passed`, reduction `one_minimal`; successful replay always returns zero,
including replay of a retained failure. Precharge reduction frame traversal
against its cached complete canonical size before taking either list length.
Every phase remains on the passed workflow budget.

Other authoritative exploration properties already occur in the complete
native report: state count, possible/evaluated histories, completeness,
all-passed, outcome counts, coverage totals and shared dependencies. Python
copies those values; it does not recompute them. Config state-count properties
can project the corresponding native report fields. Root approved reuse of the
existing audited pure `CheckResult` hydration path for typed leaf behavior;
workflow/request/exploration constructors remain forbidden on the selected
native route. No object-construction bypasses or Python semantic fallback.

## Exact legacy rendering

Keep complete canonical workflow artifact bytes unchanged. Freeze the summary
format in the presentation profile: `json.dumps(..., indent=2)` with default
ASCII escaping, original insertion order, and one stdout newline. Common keys
are record fingerprint, request fingerprint, operation, mode, intended use,
human admission and claim scope, followed by operation-specific keys in the
current CLI order. Append replay text and optional output path last.

The audited CheckResult codec restores diagnostic/counterexample/coverage
`to_dict` field ordering. Structural bounds and signature views must restore
their dataclass field order, plus InputFrame and SignalSample field order.
Arbitrary fixed-suffix signal/contact map insertion order must come from the
frozen raw independent authority: InputFrame preserves that order, while the
canonical output record sorts object keys. Preserve that raw-order context in
the native view or provide it explicitly to the formatting layer. This is
formatting only; field values remain bound to native output and authority.
The draft CLI capture tool includes a noncanonical-order authority case.
No child capture has run yet; exact stdout reproduction remains unvalidated.

## Command mismatch precedence

The existing CLI first imports and validates complete authority, then rejects
a mismatch between the selected command and the request operation, then runs
the workflow. Checking raw JSON operation before native source validation
changes failure precedence; checking only after a completed native run changes
precedence relative to evaluator failures.

Recommended v2 control addition: nullable explicit `command` (or an agreed
equivalent expected-operation field). SDK sends null; CLI supplies its exact
command. Native handling validates this after `decode_request_in` and before
`run_in`, preserving the original message:
`Command and frozen verification operation disagree.` Bind the supplied command
in the semantic receipt/presentation. Replay uses `synthetic-replay`. This
control's final name, error code and exact field shape still need agreement.

## Versioning decision still open

Prefer a new workflow semantic profile v2, service implementation v0.2 and
semantic receipt v2; retain artifact transport v1 and existing record schemas.
Alternatively preserve v1 negotiation alongside a separately named presentation
capability. Do not silently add fields to an exact v1 profile/receipt.

Root must coordinate the selected option across service, strict client,
immutable native views, public SDK/CLI routes, independent supplemental profile
fixtures, complete installed campaigns and four-way comparator. Preserve the
original frozen corpus and the current PR59 validation; no reviewed profile
pins or goldens were changed during this design task.
