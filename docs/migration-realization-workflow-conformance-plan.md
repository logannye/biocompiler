# Complete realization workflow conformance plan (R5)

Read-only source and frozen-ledger audit, 2026-10-02. This specifies the next
implementation/capture batch after the nine direct realization operations. It
does not assert native workflow support, hosted validation, or completion of
LM-12/22/25. No fresh capture or executable native run was performed.

## Scope and missing evidence

R5 in [the routing plan](migration-realization-routing-plan.md) requires whole
workflow request/result semantics, candidate and model modes, exploration,
selected-failure reduction, fresh replay and CLI behavior. Calling a native direct
checker from the existing Python workflow is insufficient: Python currently
constructs authoritative dependency settings, validates enumeration order and
stability, derives completeness/coverage, decides minimality and authorizes
whole-record replay.

The existing captures preserve original source tests and nested observations, but
do **not** capture top-level run/replay, enumeration, exploration, reduction or
adversarial-generator calls, nor complete workflow/exploration/reduction records
as their own boundary operations. New capture is necessary. Do not manufacture
whole-record expected outputs from nested checker reports.

| Source module | Original methods | Contexts including setup | Synthetic-acceptance observations | Reached direct checks/dependencies |
| --- | ---: | ---: | ---: | ---: |
| test_verification_exploration.py | 14 | 14 | 0 | 0 |
| test_synthetic_verification_workflow.py | 10 | 11 | 15,267 | 986 |
| test_synthetic_design_workflows.py | 8 | 9 | 7,451 | 380 |

The workflow 986 comprise 237 synthetic checks, 256 realization checks and 493
dependency calls. The design 380 comprise 69 synthetic, 103 realization, 172
dependency, 12 assembly and 24 component-behavior calls. These are nested API
counts, **not** workflow requests, CLI invocations or enumerated histories.
The producer corpus adds 46 selection-record observations in design contexts,
raising that row to 7,497 while preserving the same reached direct calls.

The foundation corpus separately retains 380 evidence-record observations from
the 14 exploration tests: 92 DependencySnapshot constructors, 103 coverage
constructors, 93 CheckResult constructors, 16 CheckResult imports, 22 coverage
imports, 40 diagnostic constructors, 9 diagnostic imports and 5 counterexample
constructors. These do not prove enumeration or reduction algorithms.

Keep these immutable sources and every full document:

- Foundation pin: `ac1499688ec6f0eca41398134b9421de9f95ffe9405422332c2bf43b04db32f8`.
- Acceptance pin: `d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331`.
- Producer pin: `2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b`.
- Direct protocol pin: `9261f5fc259e6d79e56df6bf9cc5ee528e795aa5dd2ef8bc4dcc7b63dfd4d4bf`.

The original complete cohort is 373 methods, 381 contexts and two actual children.
Acceptance contains 47,758 observations; producers contains 47,901. Preserve each
respective projection exactly. Different instrumentation explains their counts;
neither licenses sampling, deduplicating executions, omitting nested producers,
or modifying an original assertion.

R5 additionally restores the omitted `test_verification_campaign.py` cohort:
three unchanged methods and its `setUpClass` execute the complete 625-history
presence-aware campaign, all 21 adversarial cases, selected-failure reduction,
full report roundtrips and historical CLI inspection. The new baseline therefore
contains 376 methods; do not describe the old 373-method census as covering this
campaign. Its new dynamic observation counts must come from the audited capture.

## APIs, caller inventory and records

| API | Existing signature and complete result |
| --- | --- |
| run_synthetic_verification | (request: SyntheticVerificationRequest) -> SyntheticVerificationRecord |
| replay_synthetic_verification | (record: SyntheticVerificationRecord, *, expected_request: SyntheticVerificationRequest) -> SyntheticVerificationRecord |
| enumerate_boolean_histories | (config: BooleanContactConfig) -> iterator of complete ordered InputFrame tuples |
| explore_boolean_histories | (config: BooleanContactConfig, evaluate) -> ExplorationReport or BooleanInputExplorationReport |
| reduce_counterexample | (history, until, evaluate, signature: FailureSignature, *, max_evaluations=1000) -> ReductionResult |
| generate_adversarial_histories | (config: AdversarialConfig) -> tuple[HistoryCase, ...] |
| boolean_config_from_dict | (data) -> exact contact-only or mixed config class |
| FailureSignature methods | from_counterexample(item), from_diagnostic(item), matches(result) |

Production callers at this snapshot:

- `compiler/verification_workflow.py:229` defines run; `:253` defines replay,
  which invokes run at `:271`. `_checker` selects candidate acceptance at `:189`
  or direct realization at `:197`. Run invokes exploration at `:241` or reduction
  at `:243` and constructs the whole record at `:250`.
- `verification/exploration.py:588` defines exploration and invokes enumeration
  at `:595`. Enumeration is at `:417`, reduction at `:865` and adversarial
  generation at `:654`.
- `cli.py:1690` defines `_verification_command`, calling replay at `:1699` or run
  at `:1712`. The summary and bounded read/publication helpers are separate paths.

AST Name/Attribute call-site counts, **not** dynamic invocation counts:

| Scope | Run | Replay | Enumerate | Explore | Reduce | Adversarial |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Production src/biocompiler | 2 | 1 | 1 | 1 | 1 | 0 |
| Existing tests | 17 | 8 | 3 | 6 | 7 | 4 |
| Examples | 5 | 2 | 0 | 1 | 1 | 1 |

Besides the three source-test modules above, retain
`test_temporal_generation.py::TemporalGenerationTests.test_bounded_dwell_campaign_covers_all_81_declared_histories`
(line 512; exploration call 534) and the remaining 14 methods in that module as
part of the original cohort. Examples are `synthetic_verification.py`,
`synthetic_design.py` and `verification_campaign.py`; preserve their complete
main/run outputs and exact record bytes when adding installed consumers.

Implement and capture all 11 concrete classes below: constructors, strict
from_dict/from_json, exports, fingerprints, nominal malformed values, exact
exceptions, inherited methods and computed properties. Shared `_Record` is codec
infrastructure, not a twelfth concrete authority.

| Class | Complete fields beyond schema |
| --- | --- |
| SyntheticVerificationRequest | realization, candidate, operation, mode, history, until, bounds, signature, max_evaluations |
| SyntheticVerificationRecord | request, result, workflow_version, claim_scope |
| BooleanObservation | signal_id, field |
| BooleanContactConfig | contact_ids, observations, variable_times, until, fixed_suffix, max_histories |
| BooleanInputConfig | all contact-config fields plus cell_observations |
| ExplorationReport | config, results, explorer_version, claim_scope and all eight derived fields |
| BooleanInputExplorationReport | same fields with mixed config and distinct schema/version/scope |
| FailureSignature | kind, requirement_id, code, rule_id, specification_id, contact_id, state, node_id |
| ReductionResult | original_history, history, until, signature, original_result, result, evaluations, one_minimal, reducer_version |
| AdversarialConfig | bounds, seed, random_cases |
| HistoryCase | id, kind, history, until, config_fingerprint, intentionally_incomplete |

Corresponding schemas are:

`biocompiler.synthetic_verification_request.v0.1`,
`biocompiler.synthetic_verification_record.v0.1`,
`biocompiler.boolean_observation.v0.1`,
`biocompiler.boolean_contact_config.v0.1`,
`biocompiler.boolean_input_config.v0.1`,
`biocompiler.boolean_exploration_report.v0.1`,
`biocompiler.boolean_input_exploration_report.v0.1`,
`biocompiler.failure_signature.v0.1`,
`biocompiler.history_reduction.v0.1`,
`biocompiler.adversarial_history_config.v0.1` and
`biocompiler.adversarial_history.v0.1`.

Pin workflow `biocompiler.synthetic_verification_workflow.v0.1`, contact
exploration/reduction `biocompiler.boolean_exploration.v0.1` and mixed exploration
`biocompiler.boolean_input_exploration.v0.1`, with exact current claim text.
History identity remains compact **ASCII** JSON; generic workflow/exploration
artifact identity remains its existing compact UTF-8 record hash. Preserve
complete source/artifact identities, 9 versus 9.0, negative zero where valid,
ordered arrays, Unicode spelling, frame inventory and source file/line/function.

The eight exploration derived fields are state_count, possible_histories,
evaluated_histories, complete, all_passed, outcome_counts, coverage_totals and
shared_dependencies. Imports check these values rather than trust or discard
them. Output contains every complete ordered CheckResult, including nonpassing
outcomes and source-bearing diagnostics.

## Semantic responsibilities and oracle requirements

### Whole workflow and replay

Cover all three operations × both modes and every reachable outcome/error.
Check/reduce require nonempty history starting at zero, strictly increasing
within an explicit finite nonnegative horizon. Explore accepts only bounds:
history empty and separate until/signature/max_evaluations null. Check cannot
carry unused bounds/reduction controls. Reduce requires explicit FailureSignature
and integer evaluation budget 1–100,000.

Candidate mode performs complete candidate provenance/acceptance. Model mode
uses the candidate mechanism/map and the original request behavior/contract/domain/
target; it does not claim candidate lineage acceptance. Both add these exact
settings before constructing the authoritative result:

- verification_workflow: current workflow version.
- verification_mode: candidate/model.
- verification_candidate: exact candidate fingerprint.
- verification_realization: full realization artifact fingerprint.

Python must not supply those settings with dataclasses.replace or a new
DependencySnapshot after a selected native check. Native execution constructs the
whole authoritative workflow record.

Replay requires independent complete expected operation authority, compares its
fingerprint to the historical record's request, executes the current whole
operation and compares the complete rebuilt record identity. Preserve error
precedence: changed independent authority differs from stale or altered evidence.
Reproducing FAIL/UNKNOWN/UNSUPPORTED is valid replay; its outcome remains unchanged.

### Enumeration and report claims

Contact absence differs from present/all-false. Observation, contact and time
order determine the exact mixed-radix sequence. Contact state count is
`(1 + 2^observations)^contacts`; mixed state count multiplies by
`2^cell_observations`. Possible histories are `state_count^variable_times`.
Evaluate exactly the ordered prefix bounded by max_histories and preserve the
fixed suffix byte-for-byte.

Current bounds allow at most eight contacts, eight contact observations, eight
cell observations and sixteen variable times; max_histories is 1–100,000.
Mixed cell-only bounds are supported. Signals cannot have both cell and contact
scope. Suffix frames must contain exactly the declared signals and Boolean
fields; undeclared sample values are rejected.

Each callback must return a complete CheckResult for the exact ASCII history
identity and explicit horizon. Shared dependencies exclude **only history**.
Horizon, source artifact, model/request/contract/domain/target and tools remain
stable. Checked requirement inventory stays identical and ordered. Coverage totals
add all four counters and sort requirement IDs as Python does. Complete describes
enumeration; all_passed additionally requires every result PASS. A capped passing
prefix is incomplete, even when all evaluated results pass.

### Reduction and selected failure

Evaluate the original history first (evaluation 1) and require the explicit
selected FAIL. Preserve the first frame and exact horizon. Try deleting frames
in index order from 1. Accept deletion only for the same failure signature and
restart at index 1 after success. UNKNOWN, UNSUPPORTED, PASS and different FAIL
cannot replace the selected failure. Every trial preserves dependency and checked
requirement inventories. Response signatures fix requirement/rule/specification/
contact/active-or-inactive state, not failure time. Diagnostic signatures fix
code, optional requirement and optional node.

Budget exhaustion returns complete original/current results, histories,
evaluations and one_minimal=false. Claim one-minimal only after an unsuccessful
full deletion sweep; this is not global minimality. Capture every rejected trial
as well as accepted deletions. Import checks an unchanged subset of original
snapshots; import alone cannot establish fresh minimality.

### Adversarial proposals

Retain exact ordered startup_active, rapid_oscillation, dropout_reappearance,
absent_contacts, seeded samples and the explicitly incomplete diagnostic case.
The helper emits `4 + random_cases + 1` histories using a SHA-256 counter and
must not allocate the Cartesian product. It does not prove completeness.
Either implement the deterministic helper alongside these domains or explicitly
retain it as Python proposal code with all original cases captured. Do not omit
its two tests or label it an acceptance checker; workflow run does not call it.

## Capture design before another large run

1. Create an isolated `tools/freeze_realization_workflow.py` and new corpus.
   Reuse the existing capture infrastructure without changing old golden files.
   Retain all 373 methods/setup contexts, exact assertions, raw arguments,
   nominal types, source coordinates, exceptions and call order. Capture the 11
   classes and all public APIs above. Every reached direct checker/producer call
   stays explicit or links to an already pinned complete prerequisite. Exclude
   only the new core=None transport selector from historical binding, as R4 does.
2. Add callback transcripts: source module/qualname, code/source identity,
   enclosing test and parent/sequence IDs, exact arguments/history/horizon and
   complete result or original exception for every invocation. Do not pickle or
   import executable closures. Preserve generator yields/close/error behavior
   without eagerly exhausting iterators the original caller consumes partially.
3. Provide a native **test-only** evaluator seam. The native kernel constructs
   its own next history/trial; transcript replay compares that full input against
   the next original call before returning its complete result/error. Reject
   missing, extra or reordered calls and require original transcript exhaustion.
   This independently tests stale, wrong-horizon, changed-model and
   changed-requirement callbacks as well as enumeration/deletion order.
4. Production native workflow uses fixed fresh native candidate/model evaluators
   under original request authority. No transcript, imported report sequence,
   checker override or Python callback is a public wire capability. Generic
   Python callback-taking helpers remain separately inventoried compatibility/
   proposal APIs unless an explicit native bridge is designed; fixed wholeworkflow
   parity must not be misreported as migration of arbitrary Python callbacks.
5. Capture complete top-level requests/records/errors and CLI stdout/stderr,
   exit codes and published bytes. Identify original in-process CLI calls
   accurately, then add installed actual-child counterparts under the same guard.
6. After defining this profile, run the unchanged cohort once and instrumented
   cohort once. Compare every retained prior projection to immutable pins.
   Independently recapture the new profile and compare all new bytes. Freeze
   exact dynamic API/constructor/callback/yield/CLI counts then; current static
   sites are not a substitute census. Do not deduplicate executions.
7. Add native complete literal tests, full transcript/corpus replay, installed
   protocol/SDK/CLI campaigns and cross-platform full-byte comparison. Preserve
   all prior runtime, producer, domain, direct-protocol and original Python gates.

Generic tests deliberately return fake checker/model/evaluator versions and test
dependency hashes. Preserve these as generic-kernel cases under the test seam.
Do not convert them into production trusted workflow reports or replace them
with easier fixed-checker scenarios.

## Exact original scenario inventory

The 14 exploration methods cover full nine-history enumeration, exact outcome/
coverage counts, capped prefixes, stale/wrong-horizon/changed-model/changed-
requirement/nonrecord callbacks, Unicode ASCII history hashing, lone surrogates,
malformed configs/imports, deterministic adversarial transitions, huge-product
avoidance, selected diagnostic and response reductions, budget exhaustion,
changed reducer policy, requirement changes and stale trial dependencies.

The 10 workflow methods cover complete JSON/current replay; UNKNOWN and
UNSUPPORTED without preacceptance; all 100 mixed contact/reset histories; capped
passing prefixes; cell-only four-history enumeration; ignored-reset model failure
and reduction with budgets 100 and 1; candidate-lineage rejection; changed history,
numeric horizon kind, mode and model; narrowed/rehashed campaign authority;
forged settings/stale checker version; malformed operation shapes and forged
derived summaries. The temporal-generation method independently requires all 81
declared dwell histories.

Preserve the precise stale-checker monkeypatch in
`SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay`
(lines 267–271), including all nested observations. Fixed-policy wire routes get
separately frozen current full counterparts and original stale replay witnesses,
never production overrides or broad expected-result normalization.

All eight design tests remain. Selected pipeline, selection policy, package
rebuild and archive assertions are R6 prerequisites, not R5 accomplishments.
Record their unported calls explicitly rather than removing these methods.

## Actual children and CLI semantics

CLI check/explore/reduce use --request and optional --output; replay uses the
historical path, --expected-request and optional --output. Preserve full summaries,
bytes, command/operation agreement, source authority and these exit meanings:

| Command | Exit 0 | Exit 1 | Exit 2 |
| --- | --- | --- | --- |
| check | PASS | retained nonpassing result | malformed/authority/resource/I/O error |
| explore | complete and all PASS | incomplete or nonpassing campaign | malformed/authority/resource/I/O error |
| reduce | one-minimal selected failure | budget-limited reduction | selected failure absent or other error |
| replay | exact fresh reproduction, including nonpassing result | not used | changed authority, stale evidence or other error |

Original operation reads are bounded to 16 MiB; historical report reads and
publication to 64 MiB. Publication is atomic temporary write/flush/fsync/replace,
preserves the previous file on failure, and cannot overwrite independent input.
Original tests include command disagreement, mocked os.replace failure, temporary
cleanup, input overwrite, UNKNOWN check exit 1 then UNKNOWN replay exit 0,
capped campaigns and selected inactive-response reduction. Inspect remains
historical inspection, not fresh acceptance.

The two old actual children are **not CLI children**:
`test_realization_integration.py::RealizationIntegrationTests.test_evidence_is_reproducible_across_hash_seeds/subprocess/{0,1}`.
They run examples.realization_check.run_example with seeds 1 and 37, each retaining
24 nested observations, exact responsive/late/silent fingerprint stdout, empty
stderr and exit 0. Keep them unchanged. Add genuine installed CLI children for
all four commands and relevant success/nonpassing/error scenarios, with the
no-fallback guard active inside each child.

## Resources and selected-core routing

One workflow ancestor budget covers imports, count arithmetic, enumeration,
every fresh checker, settings, aggregation, replay and publication. Do not reset
work per history/trial. Resource exhaustion is distinct from semantic evaluation
caps and completeness/minimality flags.

Measure the full original 100- and 81-history witnesses before fixing a workflow
default: simply reusing direct operations' 50M limit may reject previously
supported complete campaigns. Version a bounded aggregate profile preserving
all original complete cases, with explicit reductions only. Bound big-integer
count arithmetic, use lazy indexed enumeration, and reserve histories/trials/
aggregate reports before allocation. Check exact and one-below limits, repeated
failed calls and inherited exhaustion identity.

Current direct wire limits (16 MiB request / 32 MiB response) differ from the
historical 64 MiB report limit. Freeze an explicit workflow transport profile;
never truncate result arrays or silently sample a complete campaign to fit.
A report too large to replay with its authority requires a documented explicit
bound/error, not imported acceptance.

The installed guard must deny Python workflow dependency mutation, enumeration,
minimality decisions, semantic record validation, lowering, model execution and
fallback. Existing SyntheticVerificationRequest import invokes Python lowering;
ExplorationReport import regenerates histories and validates claims. These are
not harmless transport codecs. Send raw authoritative JSON and return a strict
transport-owned immutable wrapper. Keep historical Python hydration outside the
guard unless a separate nonauthoritative display codec is introduced.

Run complete protocol/SDK and actual CLI children with both executable roles on
Linux/macOS and Python 3.11/3.14. Save complete records/transcripts/CLI bytes/errors
with every occurrence and binary/source/tested/run pins. Preserve exact matrix
accounting and full-byte comparison.

## Implementable next batch and exit conditions

- [ ] W1: freeze run/replay envelopes, all schemas, both modes, full identities/
  claims, aggregate limits and diagnostic precedence. One run and one replay
  operation carrying the explicit request operation tag is sufficient; keep
  the existing nine direct operations unchanged.
- [ ] W2: implement OCaml workflow/exploration/reduction domains and deterministic
  kernels, strict derived-field imports and test-only evaluator seam. Classify
  adversarial proposals and arbitrary Python callbacks explicitly.
- [ ] W3: implement fixed native wholeworkflow execution and independent replay
  under one budget, with full independent literals/transcript tests.
- [x] W4: finalize isolated capture, run unchanged/instrumented complete cohorts,
  independently recapture and preserve every old projection and actual child.
- [ ] W5: add raw protocol/optional SDK/CLI routing, exact exit/publication semantics,
  strict guards and every installed original counterpart.
- [ ] W6: obtain current-revision hosted matrix/full-artifact comparison and
  original discovery receipts; only then mark satisfied R5/LM subitems. R6
  pipeline/archive/export, distribution and default cutover remain separate.

## Audited source identities

### Capture checkpoint

The isolated `tools/freeze_realization_workflow.py` now retains all 376 unchanged
methods, 385 contexts and 69,236 observations, including 1,030 complete callback
invocations, 24 lazy enumerators, 16 original in-process CLI calls and the two
unchanged actual children. The omitted campaign retains all 625 results. All
47,901 prior producer observations compare exactly in order and original nesting;
874 new domain/kernel observations independently replay their full Python
results, properties, exceptions and callback chronology.

All 14 capture/integrity tests pass (96.643 seconds), including an independent
complete 376-method baseline and instrumented recapture, all 874 new Python
replays and every-document byte comparison. Python source compilation checks
also pass. The validation receipt is
`generated/migration-next/realization-workflow-native-preflight-tests.log`.

`tests/conformance/realization-workflow-v1.json` is pinned to
`2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b`.
Its 11,522 documents and index total 188,830,976 bytes; the largest document is
12,430,473 bytes. Context-local call/source/type references preserve every
occurrence and reconstruct the complete original capture with fingerprint
`5e7b74bd456a554dd3b1e3661f25ec42ff00a719b114d19cdd474d9c014b1015`.
Fixtures retain the source hashes captured at freezing time. Subsequent captures
retain actual current source metadata in their raw capture and receipt.

The separately reviewed addition `src/biocompiler/core_artifacts.py` is pinned to
`e4f6888609f9ffdab1d7f2e641072f3545a15c0e41ea6a3ddd85d50477708a68`.
`tools/check_realization_workflow_corpus.py` verifies that every historical source
file remains byte-identical, rejects unreviewed additions, and records both full
source inventories. Baseline and instrumented capture assert that this added
module is absent and block its import. Only after that guard succeeds may the
comparison project the source inventory to the historical inventory; every
observation and artifact must still compare exactly. Current full metadata is
explicitly not claimed byte-identical to historical metadata. Focused captures
cannot authorize a whole-corpus projection.

`core/test/test_realization_workflow_corpus.ml` implements full native replay of
all 47,901 retained prerequisite occurrences, 19,415 newly reached prerequisite
occurrences and 874 new domain/kernel observations. It consumes all 1,030 exact
callback transcripts and 24 enumerators, checks every derived property and
reviewed rejection, and executes the complete 625-case campaign. Original
checker-version mutations compare a fresh fixed-current complete counterpart
before reproducing the exact historical mutation or rejecting stale replay.
The runner also checks the 16 retained CLI observation records and publication
bytes; those records do not establish installed CLI routing. Static peer review
has been performed; the runner has not been compiled or executed locally.

Capture chooses an exclusively owned `/tmp/biocompiler-workflow-conformance-v1`
directory and deterministic child paths before baseline and instrumented runs.
It preserves actual CLI stdout/stderr, file bytes, publication failures and
cleanup assertions without output normalization. The manifest records this
capture-only environment intervention. Collisions fail without modifying existing
contents. Original CLI calls remain in-process evidence; installed guarded CLI
children, execution of the native full-corpus runner and hosted validation remain pending. This
checkpoint does not close R5 or any whole-migration LM item.

Recheck these if implementation starts after source changes:

| File | SHA-256 |
| --- | --- |
| src/biocompiler/compiler/verification_workflow.py | 04d9818933ae3ded190d4139023340f88c1eb7d8f2325173c4c77c056f7b7dd6 |
| src/biocompiler/verification/exploration.py | a4b85d8b0f48198128bc9064fa065eddc8c5f6acb4d68d92a21008c79723ca98 |
| src/biocompiler/cli.py | eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0 |
| tests/test_verification_exploration.py | 7b0225c8b0c85635fc94b64f6a8904c66ec90f4a012f82059a5c8eaf65e37ecc |
| tests/test_synthetic_verification_workflow.py | 77f20911b8eddff90f0294137dfadd9a57fe14a3cc0402bc7875e890c40f1124 |
| tests/test_synthetic_design_workflows.py | c00c25121d5437f1d5c9419d5be9e2286d5f7e8abac4e29213dea6a521dd1322 |
| tests/test_temporal_generation.py | 365d84c37be73619f1a7d099e4e1b405b623d27bd5fe360f9699a1dfe204ba0d |
