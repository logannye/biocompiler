# R5 public workflow views: implementation checkpoint and remaining plan

Checkpoint, 2026-10-02. `src/biocompiler/workflow_backend.py` now implements the
immutable native views and input adapters described below; its 18 focused Python
tests pass. The strict workflow client also implements the compatible v2
presentation contract. These results do not establish hosted native success or
complete public SDK/CLI routing: the original public workflow functions and CLI
remain unchanged. Read with rule 6 of
`migration-realization-workflow-public-plan.md` and
[`workflow-public-contracts-v1.md`](../protocol/workflow-public-contracts-v1.md).

## Accepted public contract

Preserve the current Python default exactly:

- `run_synthetic_verification(request)` returns the existing
  `SyntheticVerificationRecord` through its current implementation.
- `replay_synthetic_verification(record, *, expected_request=request)` retains
  its current nominal checks, constructors, behavior and return type.
- Existing generic enumeration, exploration, reduction and adversarial callback
  APIs keep their Python behavior and original tests. They do not become native
  whole-workflow authority merely by calling a native leaf checker.

An explicit `core=` branch may return a new immutable `NativeWorkflowRecord`.
Its class identity is intentionally different from `SyntheticVerificationRecord`;
new exploration/reduction/request/config views are likewise not instances of the
legacy classes. Do not promise compatibility with `dataclasses.replace`, legacy
nominal checks, arbitrary IR methods, or constructor-based semantic validation.
Keep the original imports and default constructors intact. Missing, incompatible,
rejected or unavailable selected cores must fail; never fall back to Python.

The implementation uses individually audited **CheckResult**,
**RequirementCoverage** and **FailureSignature** structural codecs for leaf
hydration, with narrow execution-guard exceptions and complete re-encoding
checks. CheckResult retains the complete ASCII byte/fingerprint check used by
`realization_backend.py`. This does not permit arbitrary `from_dict` calls, the entire evidence module, or
`_Record.from_dict` for every subclass. No constructor bypasses, `object.__new__`
hacks, monkeypatched validators or forged old-class identities are acceptable.

## Read-only view surface

Use ordinary immutable view constructors over a bounded, deeply frozen copy of
the complete native document. Arrays become tuples; maps remain immutable;
`to_dict()` returns a fresh mutable copy. Cache or preserve canonical bytes so
mutating a returned dictionary cannot alter subsequent fields or identities.
Do not use a generic attribute proxy that shadows real fields such as `values`
with mapping methods, and do not assign a generic JSON hash to an IR property
whose historical meaning is a different semantic fingerprint.

| View / leaf | Required read-only surface |
| --- | --- |
| `NativeWorkflowRecord` | `schema_version`, `request`, `result`, `workflow_version`, `claim_scope`, exact UTF-8 `fingerprint`; complete `to_dict()`/`to_json()`; separately named immutable native receipt/presentation |
| `NativeWorkflowRequest` | All nine fields: `realization`, `candidate`, `operation`, `mode`, `history`, `until`, `bounds`, `signature`, `max_evaluations`; schema and exact UTF-8 codec/identity |
| `NativeExplorationReport` / mixed variant | `config`, ordered typed `results`, `explorer_version`, `claim_scope`; the eight native serialized derived fields, copied exactly |
| `NativeReductionResult` | `original_history`, `history`, `until`, `signature`, typed `original_result` and `result`, `evaluations`, `one_minimal`, `reducer_version`; schema and exact UTF-8 codec/identity |
| Contact/mixed bounds views | `contact_ids`, `observations`, `variable_times`, `until`, `fixed_suffix`, `max_histories`, plus mixed `cell_observations`; native-provided `state_count` and `possible_histories` |
| Observation view | `signal_id`, `field`, schema and exact serialized fields |
| Input-frame/sample views | `time`, immutable `signals` and `contacts`; sample `value`, `present`, `high`, `low`; exact `to_dict()` without evaluator construction |
| Typed `CheckResult` leaves | Existing outcome/evidence enums, dependencies, checked IDs, diagnostics, counterexamples, coverage, `passed`, exercised IDs, structural freshness comparison and complete legacy codecs |
| Failure signature | All eight scalar/null fields and schema; exact serialization through the individually audited `FailureSignature` leaf codec |
| Nested realization/candidate documents | Complete immutable supplied JSON and structural access/serialization. No Python lowering, reconstruction or generated semantic identity; unsupported legacy IR methods must remain explicit |

Exploration's eight derived fields are `state_count`, `possible_histories`,
`evaluated_histories`, `complete`, `all_passed`, `outcome_counts`,
`coverage_totals` and `shared_dependencies`. Python must project these native
values, not enumerate histories, sum counts, filter dependencies or infer
completeness. Coverage totals may use the already audited leaf coverage-record
codec, without performing aggregation.

Bounds themselves do **not** serialize their state-count properties. Within an
accepted exploration workflow, both request bounds and result config can expose
the corresponding native report's serialized counts. Their complete config
bytes must remain unchanged. A standalone bounds view cannot promise these
properties from config JSON alone without supplied native presentation or
semantic computation; standalone import is an explicit open boundary.

## Inventory of the eleven original artifacts

The audited originals are `SyntheticVerificationRequest`,
`SyntheticVerificationRecord`, `BooleanObservation`, `BooleanContactConfig`,
`BooleanInputConfig`, `ExplorationReport`, `BooleanInputExplorationReport`,
`FailureSignature`, `ReductionResult`, `AdversarialConfig` and `HistoryCase`.
The first nine occur in whole workflow records. The last two belong to the
separate generic proposal API and are not produced by the run/replay protocol.
Preserve their original APIs/tests; do not claim their public native routing is
implemented by this view work. Their field shapes are already fully inventoried
in the public workflow plan.

The actual consumer audit includes `_verification_summary` and publication in
`cli.py`, `test_synthetic_verification_workflow.py`, and the generic suites in
`test_verification_exploration.py`. Observed accesses include nested outcome enum
values, dependency `values["settings"]`, config counts, suffix/history frame
maps, diagnostics, counterexamples, coverage, complete/partial campaign fields,
minimality/evaluation counts, exact JSON/fingerprints and signature matching.
Legacy nominal checks and `replace(...)` in these tests continue to exercise the
unchanged default route; native tests must separately state view identities.

## Canonical codecs and construction boundaries

Every view must preserve every original field, including full source authority,
all requirements and diagnostics, not just presentation fields. Workflow and
exploration identities use compact sorted UTF-8 JSON. Each hydrated CheckResult
and DependencySnapshot retains compact sorted **ASCII** identity. Before exposing
a typed leaf, compare its complete re-encoded ASCII bytes and fingerprint with
that same native leaf; an outer UTF-8 hash cannot substitute for this check.

Match the declared legacy `to_json(*, indent=2)` formatting contract, including
sorted keys, Unicode policy and ordinary `indent=None` spacing. Keep compact
canonical artifact bytes separately: legacy `to_json(indent=None)` is not the
compact fingerprint encoding. Output formatting must remain bounded, and CLI
publication retains its newline-inclusive 64 MiB limit. Pretty printing does
not confer semantic validity or change the canonical fingerprint.

Do not expose an unqualified standalone view `from_dict`/`from_json` that silently
performs old semantic construction or claims unavailable properties. The first
route should construct complete views from a fully checked `WorkflowResult`
plus the exact native presentation/frozen authority context. If structural
historical view imports are later added, explicitly distinguish them from fresh
results and require any missing native metadata; neither an imported view nor a
stored receipt is a reusable acceptance token.

Nested RealizationRequest is a specific identity trap: its `fingerprint` is a
hash of semantic component identities, while `artifact_fingerprint` hashes the
complete serialized authority. BuildRequest and Behavior also have scoped
identities. Do not substitute a whole-document JSON hash under a legacy
semantic property name. Full nested raw access is supported initially; exact
legacy IR property compatibility needs separately supplied native identities or
an explicit audited extension.

## Native presentation and CLI formatting

The v2 service and strict client now implement a compact versioned presentation
receipt with `command_exit_code`, `original_frames` and `reduced_frames` (frame
counts null outside reduction). Native source and installed campaign checks are
wired into hosted CI; native execution remains pending. Other summary values
already exist in the native record or approved typed CheckResult leaves. Keep the control response below 64 KiB; full
diagnostics and counterexamples can approach the artifact limit and must stay
in the complete record rather than being duplicated into control metadata.

CLI summaries structurally select already supplied values. They do not decide
`passed`, `all_passed`, minimality, explored counts or exit policy. Fixed summary
and dataclass field order can be a formatting table. Arbitrary signal/contact
map insertion order for fixed suffixes must come from the frozen original raw
authority when exact legacy summary text requires it: canonical artifact bytes
sort those maps and cannot recover the original insertion order. Retain that
bounded formatting context separately; it does not change canonical identity.

## Implemented backend seams and input compatibility

The backend delegates negotiation, artifact transport and semantic receipt
binding to `WorkflowClient.run_public/replay_public`. It exposes:

- `view_result(native, authority=None)` for a complete checked transport result.
- `run_document(*, request, core, limits=None, command=None, cancelled=None)` and
  `replay_document(*, request, record, core, limits=None, command=None, cancelled=None)`
  returning a native view and its immutable transport result.
- `run_record(request, *, core, **options)` and
  `replay_record(record, *, expected_request, core, **options)` returning the view.
- `WorkflowCoreError(SerializationError)` retaining the original CoreError and
  all structured diagnostics. Selected-core errors never enter a Python fallback.

Inputs may be complete bytes, mappings, corresponding native views, or exact
already-authored legacy request/record types. Legacy `to_dict()` executes only
inside the scoped `serializing_legacy_input()` marker. Its exploration-derived
fields are untrusted historical claims: OCaml independently reconstructs and
checks the complete workflow. The marker resets even on failure, before native
transport and output exposure. This narrowly reviewed input compatibility does
not permit legacy constructors, evaluators, lowering or aggregation on native
output. Execution guards must distinguish this input phase from output hydration.

Public `core=` branches in `run_synthetic_verification` and
`replay_synthetic_verification` remain to be added with exact source-lineage
witnesses. Preserve the original default route and all generic callback APIs.

## Audited signature leaf boundary

`FailureSignature.from_dict` has no nested decoders or derived fields. Its
class-specific importer checks exact fields, schema and scalar/null constraints;
it does not enumerate histories, execute checks or call `matches`. The backend
now uses this audited leaf codec and compares its complete serialized bytes.
Do not generalize the exception to `_Record.from_dict` for every subclass:
config/report/request constructors perform semantic work. User signature queries
never replace native selected-failure preservation or fresh replay.

## Required verification before public completion

The 18 focused Python tests cover complete original records across all six
operation/mode pairs, identities, summary formatting, immutability and the input
serialization boundary. Complete installed execution remains required. Its
campaign must retain independent original full-record literals for all three
operations, both modes, all four outcomes, mixed/contact bounds, capped campaigns
and minimal/budget-exhausted reductions. Check every projected field, complete
UTF-8 record identity, every ASCII leaf identity, defensive copies, deep immutability,
Unicode, integer/float distinctions and signed zero. Pin the new class identity
and reject old-class constructor bypasses.

Execution guards must forbid source lowering, old workflow constructors,
history enumeration, result aggregation, reduction, evaluators, producer calls
and unapproved codecs during native execution and output exposure. Allow exact
legacy input serializers only while the scoped input marker is active. Keep
only the exact approved leaf codec exceptions. Test missing/incompatible core, structured native errors,
malformed replies, cancellation and timeout without fallback. Preserve all
original default/callback tests independently. Exercise native replay from raw
historical bytes, native views and exact legacy typed records within the scoped
input boundary. Reject unsupported input types before invoking their serializers.

Installed campaigns must subsequently validate both executable roles, Linux and
macOS, Python 3.11/3.14, complete record publication and exact CLI summaries/exit
codes. A structural SDK view is not new semantic validation, and this plan does
not close R5 or any LM roadmap checkbox by itself.
