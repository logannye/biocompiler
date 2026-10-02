# R5: complete native realization workflows

Implementation checkpoint, 2026-10-02: the domain records, callback engines,
fixed candidate/model workflows and independent literal tests are implemented.
The original revision `002344cd` passed all 84 native suites on hosted Linux and
macOS. The corrected accounting, allocation checks and complete corpus runner
(the 85th native suite) are now implemented and require fresh hosted validation
at the corrected revision; the earlier passes do not validate these changes.
The reviewed aggregate work ceiling is `8,500,125,714,074,944`, derived from the
bounded traversals documented below while preserving each checker's full
50,000,000-unit allowance. The next batch adds native descriptor handling,
workflow endpoints in both executables, a strict immutable Python SDK, and two
more native suites (87 total). Python transport/client tests pass (37 tests).
The corrected native source and complete installed campaign still require hosted
validation. Legacy public workflow/CLI routing remains pending.
No native compilation or execution has been performed locally.


Audited 2026-10-02 against the current shared checkout. This is an implementation
plan, not a native validation receipt or a completed roadmap item. The audit
changed only this document, executed no native code, and performed no Git or
network operations. Read together with `language-migration-roadmap.md`,
`migration-realization-routing-plan.md` R5, and the nine-operation protocol
contract. The historical audit below predates the new artifact-channel service;
its remaining public workflow/CLI and hosted-validation obligations still apply.

## Outcome and ownership

Implement one complete workflow profile: all three operations (`check`,
`explore`, `reduce`) in both `candidate` and `model` modes, historical request/
report codecs, complete fresh replay, and CLI publication/exit behavior.
The core owns workflow dependencies, enumeration order and counts, selected
failure preservation, deletion decisions, minimality, and canonical final reports.
Python can author requests, supply exploratory proposals, transport artifacts and
perform atomic file publication. A loop over the nine direct operations that
constructs an authoritative campaign or reduction report in Python is incomplete.

Keep this separate from R6's pass manager, generation/pipeline completion,
synthetic manifests, archive rebuilding and export admission. A workflow result
does not prove sequence emission, physical function or human-use admission.

The required native algorithm should accept a typed evaluator internally. Its
production workflow instance binds only the existing independent native
checkers. Abstract evaluators in tests retain original callback behavior,
including stale results, switched dependencies, wrong requirements and different
failures. Do not expose callbacks, code paths, serialized functions, a checker
version override or a saved PASS as authority on the production protocol.

## Historical audit: original seams and missing implementation

The inventory in this section records the original pre-implementation audit.
Its “missing” entries describe that historical starting point, not the current
checkpoint above; implemented runtime details and accounting appear below.

Available: structural `Realization_request`, fresh `Checked_request`, complete
`Synthetic_authority.Candidate`, reference/candidate execution, all
`Realization_evidence` types, direct `Realization_check`,
`Synthetic_candidate_check`, `Runtime_number`, exact Z integers,
`Legacy_ascii` and UTF-8 `Canonical`, plus shared `Work_budget`.
The new direct protocol supplies transport patterns, not workflow records.

Missing: all eleven exploration/workflow artifact types inventoried below,
Boolean enumeration/adversarial generation, report aggregation/validation,
failure signatures and greedy reduction, complete workflow run/replay, native
workflow SDK/CLI routing, and original top-level workflow capture. No existing
native exploration/reduction implementation was found.

Suggested modules, deliberately separate from producers:

- `domain/verification_exploration.ml/.mli`: typed observation/bounds,
  adversarial declarations/history cases, failure signatures, imported
  exploration and reduction reports, complete getters/codecs/derived properties.
  This layer validates historical consistency; it does not execute checkers.
- `domain/synthetic_verification.ml/.mli`: structural complete workflow
  request and record, operation/mode variants, result sum type. Imported record
  consistency is not fresh acceptance.
- `realization_checker/verification_exploration.ml/.mli`: bounded
  index-to-history construction, callback-parametric exploration and reduction,
  shared-dependency validation and authoritative final report construction.
  A separate bounded adversarial generator can live here or in a neutral
  proposal utility; it grants no acceptance.
- `realization_checker/synthetic_verification.ml/.mli`: fresh staged authority
  import, fixed native checker selection, the four workflow settings pins,
  `run[_with_usage]` and complete `replay[_with_usage]`.
- `service/verification_workflow_service.ml/.mli`: complete run/replay
  endpoints with exact versioned capability/resource/authority envelopes.
  Both core and verifier roles can expose them. Preserve verifier exclusion
  of compiler/producers/private producer witnesses.
- Python transport/backend and CLI changes: complete raw requests in, opaque
  native records out. Keep model execution, replay decisions, derived fields
  and minimality out of the adapter.

Use a typed internal evaluator with `parent:Work_budget.t`, effective child
limits, exact explicit horizon, and frozen frames, returning `Check_result.t`.
Every call must consume the same workflow ancestor. A callback exception is an
operation exception, never an invented UNKNOWN report. An abstract test evaluator
can consume an independently captured ordered transcript and assert every input;
a production workflow must never select this implementation.

## Structural codecs and authority order

`_Record.from_dict` first checks every nested string for valid UTF-8, then exact
fields (including every declared derived field), then the schema, then invokes
field decoders in dataclass field order, then constructor predicates, then
derived-field fingerprints in declared order. It wraps listed non-serialization
Python exceptions as `Invalid <class>: <detail>`; preserve observed exception
precedence in a frozen malformed corpus rather than guessing equivalent errors.
Text JSON must keep duplicate-key rejection and exact numeric representations.

Workflow request field order is realization, candidate, operation, mode, history,
until, bounds, signature, max_evaluations. Original nested
`RealizationRequest.from_dict` performs fresh source lowering before decoding
the candidate or applying workflow operation predicates. Native domain imports
are only structural, so a checker-owned staged import must supply that missing
fresh check in the same order. Keep the domain-to-checker dependency acyclic:
decode request fields structurally, perform `Checked_request.check` at the
original nested-authority boundary, then finish candidate and workflow decoding.
Do not validate candidate fields first and thereby change competing-error order.
Record import likewise decodes its request before its result. Raw protocol replay
must import the independently expected request and historical record in the
documented order; CLI historically imports expected authority first.

Constructor rules, after nested imports:

1. Require nominal realization, candidate, operation in check/explore/reduce,
   and mode in candidate/model, in that order.
2. Explore requires Boolean bounds; history must be an empty tuple/list and
   until, signature and max_evaluations must all be null. Normalize history to
   empty; no unused alternative authority may survive.
3. Check/reduce forbid bounds. Validate frozen frame inventory, UTF-8, explicit
   finite nonnegative horizon, nonempty time-zero initial frame, strictly
   increasing times and every time at or before horizon. Although the Python
   field defaults to None, check/reduce with until=None are invalid.
4. Check forbids signature and max_evaluations. Reduce requires a FailureSignature
   and an actual integer budget in 1..100000; Boolean/float are invalid.

Fresh model mode must still validate original realization/source authority on
raw import and execution. It deliberately skips synthetic generation provenance,
catalog correspondence and candidate acceptance. It executes the actual supplied
candidate mechanism/map via the direct checker. Never promote it to candidate
mode, silently regenerate the candidate, or reuse source outputs as model outputs.
Candidate mode invokes the full independent synthetic checker, retaining
FAIL/UNKNOWN/UNSUPPORTED without an up-front passing-candidate requirement.

Each evaluated CheckResult receives exactly four additional dependency settings:

- verification_workflow = biocompiler.synthetic_verification_workflow.v0.1
- verification_mode = the explicit candidate/model value
- verification_candidate = the complete actual candidate fingerprint
- verification_realization = realization artifact fingerprint, including source

Preserve every existing setting and every other report field. The wrapper must
bind full candidate identity even in diagnostic model mode. No additional check
result policy version is inferred from the language used to implement it.

## Boolean bounds and deterministic enumeration

Contact-only bounds require 1..8 unique contact IDs and 1..8 typed observations.
Mixed bounds allow zero contacts/zero contact observations but both must be empty
together, allow up to eight cell observations, require some observation overall,
and forbid any signal ID appearing in both cell and contact observations. A
signal can have multiple distinct Boolean fields; duplicate (signal,field) is
invalid. Fields are exactly present/high/low. Mixed constructor validates its
cell declaration predicates before the parent's contact/time predicates, after
all imported field decoders have run.

Variable lattice contains 1..16 exact finite nonnegative numbers, starts at zero,
strictly increases, and ends no later than until. Fixed suffix may be empty,
strictly follows the last variable time, is increasing and remains within until.
Suffix cell signals must equal the exact declared cell inventory; each present
contact must use the complete declared contact signal inventory. Contacts may
be absent but cannot have undeclared IDs. Every declared field must be an actual
Boolean and every undeclared sample field, including numeric value, must be null.
Native Input_frame accepts numeric sample shorthand; this workflow's historical
`_frame` importer does not. Add a strict workflow frame codec instead of
inadvertently widening the artifact schema by reusing only Input_frame.of_json.

Let c be cell-field count, o contact-field count and n named contacts:
state_count = 2^c * (1+2^o)^n. Contact-only uses c=0.
possible_histories = state_count^(number of variable times). Use Z arithmetic:
these counts can greatly exceed machine integers; never enumerate the product
merely to count it. max_histories is an actual integer in 1..100000.

History index is expanded into base-state_count digits, last variable time the
least significant position. At each snapshot, cell state is the lowest c bits.
Then each contact in declared order takes a radix-(1+2^o) digit: zero is absence;
digit k>0 means present with Boolean bit mask k-1. Observation order fixes bit
positions. Present/all-false differs from absent. Append the exact fixed suffix
without reordering, deduplication, truncation or time conversion. Enumerate indices
0 through min(possible_histories,max_histories)-1. Do not stop on FAIL/UNKNOWN/
UNSUPPORTED or merely because a passing prefix exists.

For every returned result, before retaining it, require CheckResult, valid UTF-8,
ASCII exact normalized-history hash, and both recorded horizon.until and effective
horizon numerically equal to the explicit until. The original comparison here is
Python numeric equality, not canonical-byte equality: integer and equal float can
pass this one predicate. Stable dependency equality is UTF-8 fingerprint equality
of the complete dependency object with **only history removed**; horizon,
settings, checker/evaluator/model versions and every authority pin remain.
Do not erase horizon or source artifact pins.

Exploration report import admits 1..min(possible,max_histories) results, not
necessarily a complete capped run. It validates each against its exact indexed
history, stable dependencies and identical ordered checked-requirement inventory.
Mixed config requires mixed report class, mixed explorer version and claim text;
contact-only requires its own pair. Fresh exploration always evaluates the entire
declared prefix. An imported shorter report must not become fresh complete output.

Derived fields must be independently reconstructed and compared on import:
state_count, possible_histories, evaluated_histories, complete, all_passed,
outcome_counts (all four keys), coverage_totals and shared_dependencies.
Complete means evaluated==possible, not evaluated==cap.
All_passed requires complete AND every result PASS. Coverage sums all four counts
per requirement, uses exact integers and sorts requirement IDs; enumeration
completion is separate from response coverage and empirical claims.

## Selected-failure reduction

Failure signature contains kind, requirement_id, code, rule_id, specification_id,
contact_id, state, node_id, preserving optional nulls and nonempty UTF-8 names.

- Response: requirement/rule/specification required; state active/inactive;
  code and node_id null; contact optional. Do not include failure time, actual
  value, interval or source location in equality.
- Diagnostic: code required; requirement and node optional; rule, specification,
  contact and state all null.
- A signature matches only a FAIL result with an exactly equal projected
  counterexample/diagnostic signature. UNKNOWN/UNSUPPORTED or another failure
  cannot replace the selected one.

Reduction validates history first, then callback/signature, then integer
evaluation budget. Evaluate the original history once, validate its dependencies
and exact horizon, require the selected FAIL, and count that evaluation as one.
Attempt deletion at indices 1..length-1, never index zero. Before each trial, if
evaluations>=max_evaluations return current result with one_minimal=false.
Run/validate each trial, increment count, require ordered checked requirements
equal to the initial result; accept deletion only if the same signature survives.
After an accepted deletion restart at index one. If a complete current pass
removes nothing, return one_minimal=true. A one-frame initial history can be
one-minimal at budget one because no deletion is possible; a longer history at
budget one returns false. Reaching the budget after the final necessary
unsuccessful trial can still yield true. Preserve these loop-edge cases exactly.

ReductionResult import checks both histories/horizon, typed signature,
evaluations in 1..100000, actual Boolean one_minimal, reducer version,
both result/history bindings, stable dependencies, ordered requirement equality,
selected failure in both results, then initial-state and deletion-only relation.
Python compares snapshots by dictionary/numeric equality here; do not accidentally
substitute a canonical identity comparison for that historical predicate.
Import does not prove minimality or recompute evaluation count. Fresh replay
reruns the original deletion sequence and budget to establish the whole record.

## Adversarial proposal utility

Preserve this existing API and its artifacts, although it is not a fourth
workflow operation. AdversarialConfig requires exact contact-only bounds
(not a mixed subclass), at least three variable times, seed integer 0..2^64-1
and random_cases integer 0..1000. There are four named cases in fixed order:
startup_active, rapid_oscillation, dropout_reappearance, absent_contacts.
Append seeded_0000 onward, then incomplete_observation.

For each random index/step, hash ASCII
`biocompiler.boolean_exploration.v0.1:<seed>:<index>:<step>` with SHA-256,
interpret the full digest as unsigned big-endian, and reduce modulo state_count.
Use exact integer arithmetic; avoid signed/word truncation or a platform PRNG.
All-inactive means every named contact present with false fields, not absent.
Append the fixed suffix verbatim. The final diagnostic case removes exactly the
first declared observation field from the first contact of the all-active initial
snapshot, replacing that field with null; retain all later startup-active frames.
Its intentionally_incomplete flag alone is true. Case fingerprints bind the
adversarial configuration. Sampling neither exhausts the huge Cartesian product
nor establishes proof.

## Whole-record replay and encoding

Workflow record constructor first validates request and fixed workflow version/
claim scope, then operation-specific result type. Check validates exact
history/horizon. Explore requires result.config fingerprint==request.bounds
fingerprint. Reduce requires UTF-8 fingerprints of original history and horizon,
exact signature equality, and evaluations<=request.max_evaluations.

Replay order is historical record nominal type, independent complete request
nominal type, equality of request fingerprints, one fresh whole operation,
then equality of complete record fingerprints. A wrong independently supplied
history, 9 versus 9.0 horizon, mode, candidate, bounds, suffix, selected signature
or budget must fail before evaluating a mismatching authority. Matching imported
PASS, internally consistent hashes or narrowed rehashed bounds never replace
the independently supplied request. A stale report/checker/workflow setting
fails after current native execution. Reproducing FAIL/UNKNOWN/UNSUPPORTED is a
successful replay and preserves that outcome.

All eleven new artifacts inherit JsonArtifact: their fingerprints/text are
UTF-8 ensure_ascii=False. Nested CheckResult/DependencySnapshot *own* fingerprints
and normalized-history identity remain compact ASCII ensure_ascii=True.
Stable-dependency comparisons and derived-field comparisons use UTF-8.
The enclosing workflow hashes its complete JSON, not a concatenation of the
nested ASCII fingerprints. Keep canonical integer/float/signed-zero/null/source
differences even where individual historical predicates use numeric equality.
As in the direct service, compare raw imported record bytes, typed roundtrip
bytes and fresh bytes; a normalizing decoder cannot erase a replay mutation.

Suggested protocol endpoints: `run-synthetic-verification` and
`replay-synthetic-verification`, one new workflow profile supporting all six
operation/mode combinations. Required payload is profile, limits,
expected_request; replay additionally requires record. Freeze exact field names,
profile/resource defaults and errors before implementing, rather than extending
the existing direct-family payloads implicitly. Return the complete historical
record plus implementation/profile/resource/scoped claims, raw supplied authority
hash (excluding only historical record), typed request/artifact/candidate pins,
and UTF-8 record fingerprint. Input control changes remain bound outside historical
artifact content. Native resource failures return no partial authoritative record.

## Resources: separate operation caps from native implementation bounds

max_histories and max_evaluations are immutable semantic request controls; native
work, retained items, bytes and nodes are independent reduction-only resource
controls. Reaching max_histories returns the exact capped report; reaching the
reducer evaluation cap follows the algorithm above. Native resource exhaustion
is an error, never an implicit smaller cap, early successful prefix or fabricated
one_minimal=false record.

Use a single workflow ancestor for staged imports, source checks, all histories/
trials, evaluator phases, workflow setting extension, stable-dependency hashes,
final derived fields, historical replay comparison and exact response publication.
Keep each leaf's existing 50M/default or reduced limits, but **do not give the
workflow only a fresh 50M budget per history**. No refunds for rejected trials,
exceptions or discarded intermediate evidence. Charge immutable sizes before
repeated encoding/importing; prospective cumulative report/node/retention
reservation precedes allocating a results list or an entire final record.
Index histories lazily; never materialize the huge product. Keep ordered records
for the actually evaluated prefix and exact failures; do not reduce retention by
dropping fields needed for final reports.

A dedicated workflow aggregate work profile must be calibrated and frozen before
release. Simply reusing the direct service's 50M total may reject the unchanged
81/100/625-history regressions; increasing each child's allowance silently is
also wrong. Proposed engineering starting point: separate aggregate budget with
a fixed declared ceiling and reduction-only controls, preserving current leaf
limits and any externally supplied ancestor. Select its exact default using
complete original-campaign hosted usage, not a reduced test subset. Until this is
measured, resource-profile numbers are an outstanding design decision, not a
reason to claim complete R5 parity.

Likewise distinguish actual retained inventory from cumulative work/report scans:
reconstructing every report three times into separate byte reservations can reject
an otherwise bounded original campaign. Inventory each retained result, current
history/trial, original/current reduction results and wrapper. Release only memory
whose references are truly discarded, never work. Preserve the wire's 16 MiB input,
32 MiB response, 128 depth, 250k wire values, 4 MiB strings and 4300-char numbers;
count keys too in checker allocations. A generated report can be too large to
replay through the smaller input boundary and must fail explicitly. CLI's existing
64 MiB historical file-read ceiling does not increase native transport capacity.

Require exact/one-under tests at each aggregate transition and final publication,
parent exhaustion recognition, no replacement budget after failed callback,
raw JSON/list-spine cycles, deep bounds, integer power size and Unicode expansion,
and repeat-after-failure isolation. Preserve diagnostic identity of actual
ancestor exhaustion; never catch it as an ordinary model-conditional result.

## Python callback APIs, SDK and CLI

Original generic functions accept arbitrary Python evaluators; they are not
aliases for the fixed SyntheticVerificationRequest workflow. Preserve those
scientific/default APIs and their full behavior as an explicit remaining Python
boundary, not migration-complete canonical authority. A native callback-parametric
engine with abstract test evaluators ports their algorithms without importing
Python code into the verifier. Explicit native whole-workflow routing takes
complete domain authority and uses fixed native evaluators.

Do not promise that `explore_boolean_histories(config, arbitrary_python_callback,
core=...)` runs wholly native. A dedicated native evaluator descriptor could map
known explicit authority to the complete workflow endpoint; arbitrary callbacks
remain an explicitly Python scientific seam unless a separately scoped interactive
callback protocol is designed. Such a protocol would require native ownership of
the next-history/deletion state machine and final report and could only claim
consistency under supplied external evaluator results. It cannot substitute for
fresh native candidate acceptance. At final cutover, Python may keep exploratory proposals, but authoritative
enumeration/minimality/records still require core construction or a complete
transcript checker. Such validation establishes consistency under the declared
external evaluator, not the truth of an arbitrary callback. No callable
introspection or silent fallback.

Raw workflow imports must avoid Python RealizationRequest hydration and Python
ExplorationReport/ReductionResult constructors doing semantic validation or
derived-field construction on the selected native path. Use immutable opaque
artifact views with exact roundtrip bytes and metadata, or explicitly audited
read-only projections. Merely allowlisting these constructors as codecs would
silently preserve Python authority. Historical inspection stays historical.

Preserve all four CLI commands and operation agreement:
synthetic-check exit0 only PASS; synthetic-explore exit0 only all_passed;
synthetic-reduce exit0 only one_minimal; synthetic-replay exit0 on exact
reproduction even for retained failures. Ordinary nonpassing completion is exit1,
input/authority/transport errors exit2. Preserve bounded file reads, fresh complete
expected-request replay, no input-file overwrite, atomic publication and old-file
preservation on failure. Summary counts/signature/scopes must come from the core
record, not a Python recomputation presented as acceptance.

## Original evidence and acceptance gates

The existing 373-method/29-module captures reach downstream checkers but contain
**zero instrumented top-level workflow/explore/reduce operations**. They are
necessary inherited evidence, not complete R5 capture. Add a new capture boundary
without changing old corpus bytes or deleting any old checks:

- All eleven artifact constructors/imports/text paths, derived properties,
  FailureSignature projections/matches, typed/malformed constructors and errors.
- run/replay_synthetic_verification including current-mode dependency extension
  and original nominal authority/replay rejection order.
- enumerate/explore/reduce/adversarial functions. Iterators must be observed
  completely at original consumers. Record every callback's exact ordered
  history/until, complete report or exception, and enclosing operation identity;
  fake callback results in original utility tests remain test-only inputs.
- Preserve all module aliases, package-root calls, constructors reached by
  dataclasses.replace, source fixture scopes, version patches and real subprocess
  consumers/hash seeds. Never rewrite test expectations to bypass callbacks.
- Extend the unchanged 373-method cohort with the three methods in
  test_verification_campaign.py, which the current capture omits. Its example
  exercises 625 complete histories plus adversarial histories and reduction.
  Recompute context/observation/document counts rather than predicting them.
  The focused workflow-related module set below contains 50 test methods; it
  complements, and does not replace, the full cohort.
- Independently add competing-invalid import predicates, exact boundary values,
  same numeric value/different encoding, Unicode supplementary text, multiple
  fields on one signal, all four outcomes, no early campaign termination,
  one-frame reduction at budget1, budget reached on last trial, preserved fixed
  suffix, changed signatures and forged minimality/completion/counts.

Native units drive the same callback engine with original complete transcripts,
plus fixed real checkers for every workflow mode/operation and fresh replay.
Installed Linux/macOS and Python3.11/3.14 campaigns exercise both executable roles,
raw and typed SDK seams, all CLI exit/publication cases and no-fallback guards.
A guard must reject Python lowering, evaluation, campaign/reduction logic,
dependency settings, derived summaries/minimality, semantic constructors and
producer reruns on a native-selected complete workflow. Legitimate legacy
scientific callbacks and independent Python baseline capture are separate paths.

Preserve every pre-existing required CI gate and exact tree/revision receipts.
No LM-12/22/25/26 completion or R5 checkbox closes until all operations/modes,
artifacts, original callers, complete record replay and installed CLI tests pass.
R6 and default cutover remain explicitly open.

## Concrete decisions still required

1. Freeze aggregate workflow resource defaults against the original full
   campaigns on hosted native builds; retain their semantic caps unchanged.
2. Freeze the two proposed endpoint names, wrapper keys, precise native error
   family and complete capability record. Do not reuse direct report schemas.
3. Choose the explicit native SDK result-view/authoring seam so hydration cannot
   execute Python lowering or report semantics. Preserve arbitrary scientific
   callbacks without misrepresenting them as native whole-workflow acceptance.

There is no missing biological model required to port this software scope.
The real prerequisites are new historical artifact codecs, whole-operation
semantic authority, complete original capture and the decisions above.

## Complete artifact field inventory

All schemas below are literal current Python declarations. Inherited fields are
expanded in constructor order; each JSON record also requires schema_version.
Every exploration report additionally requires all eight derived fields listed
above. Optional values remain explicit nulls.

- **BooleanObservation** (biocompiler.boolean_observation.v0.1): signal_id, field.
- **BooleanContactConfig** (biocompiler.boolean_contact_config.v0.1): contact_ids, observations, variable_times, until, fixed_suffix, max_histories.
- **BooleanInputConfig** (biocompiler.boolean_input_config.v0.1): contact_ids, observations, variable_times, until, fixed_suffix, max_histories, cell_observations.
- **ExplorationReport** (biocompiler.boolean_exploration_report.v0.1): config, results, explorer_version, claim_scope.
- **BooleanInputExplorationReport** (biocompiler.boolean_input_exploration_report.v0.1): config, results, explorer_version, claim_scope.
- **AdversarialConfig** (biocompiler.adversarial_history_config.v0.1): bounds, seed, random_cases.
- **HistoryCase** (biocompiler.adversarial_history.v0.1): id, kind, history, until, config_fingerprint, intentionally_incomplete.
- **FailureSignature** (biocompiler.failure_signature.v0.1): kind, requirement_id, code, rule_id, specification_id, contact_id, state, node_id.
- **ReductionResult** (biocompiler.history_reduction.v0.1): original_history, history, until, signature, original_result, result, evaluations, one_minimal, reducer_version.
- **SyntheticVerificationRequest** (biocompiler.synthetic_verification_request.v0.1): realization, candidate, operation, mode, history, until, bounds, signature, max_evaluations.
- **SyntheticVerificationRecord** (biocompiler.synthetic_verification_record.v0.1): request, result, workflow_version, claim_scope.

## Complete static caller inventory

AST inventory of direct calls and package/module-qualified constructors or methods
in source, examples and tests. This includes artifact imports and signature
helpers, not just run/replay. Dynamic callbacks, dataclasses.replace, inherited
methods, imported example helpers and child processes additionally require the
full runtime capture; static call counts are not a runtime conformance census.

- src/biocompiler/cli.py: SyntheticVerificationRequest.from_json@1693, SyntheticVerificationRecord.from_json@1696, replay_synthetic_verification@1699, SyntheticVerificationRequest.from_json@1705, run_synthetic_verification@1712.
- src/biocompiler/compiler/verification_workflow.py: boolean_config_from_dict@62, FailureSignature.from_dict@65, explore_boolean_histories@241, reduce_counterexample@243, SyntheticVerificationRecord@250, run_synthetic_verification@271.
- src/biocompiler/verification/exploration.py: enumerate_boolean_histories@595, HistoryCase@703, HistoryCase@720, ReductionResult@891, ReductionResult@914.
- examples/synthetic_design.py: bc.SyntheticVerificationRequest@67, bc.run_synthetic_verification@76, bc.replay_synthetic_verification@78.
- examples/synthetic_verification.py: BooleanObservation@47, BooleanObservation@52, BooleanInputConfig@69, SyntheticVerificationRequest@123, run_synthetic_verification@126, SyntheticVerificationRequest@128, run_synthetic_verification@131, run_synthetic_verification@134, FailureSignature.from_counterexample@144, run_synthetic_verification@147, replay_synthetic_verification@149.
- examples/verification_campaign.py: BooleanObservation@39, BooleanContactConfig@49, explore_boolean_histories@54, BooleanContactConfig@69, AdversarialConfig@72, generate_adversarial_histories@73, FailureSignature.from_counterexample@113, reduce_counterexample@114.
- tests/test_synthetic_design_workflows.py: bc.SyntheticVerificationRequest@32, bc.run_synthetic_verification@217, bc.FailureSignature.from_counterexample@218.
- tests/test_synthetic_verification_workflow.py: SyntheticVerificationRequest@34, SyntheticVerificationRequest.from_json@43, run_synthetic_verification@44, SyntheticVerificationRecord.from_json@46, replay_synthetic_verification@48, run_synthetic_verification@60, run_synthetic_verification@70, SyntheticVerificationRecord.from_json@81, enumerate_boolean_histories@87, SyntheticVerificationRequest@110, run_synthetic_verification@113, replay_synthetic_verification@119, SyntheticVerificationRecord.from_json@120, run_synthetic_verification@128, SyntheticVerificationRequest@129, run_synthetic_verification@144, BooleanObservation@152, BooleanInputConfig@153, enumerate_boolean_histories@155, BooleanInputConfig.from_json@157, run_synthetic_verification@172, FailureSignature.from_counterexample@180, run_synthetic_verification@184, replay_synthetic_verification@191, SyntheticVerificationRecord.from_json@192, run_synthetic_verification@197, run_synthetic_verification@201, run_synthetic_verification@204, run_synthetic_verification@208, run_synthetic_verification@219, replay_synthetic_verification@224, replay_synthetic_verification@228, SyntheticVerificationRequest@231, run_synthetic_verification@243, replay_synthetic_verification@245, run_synthetic_verification@248, replay_synthetic_verification@266, replay_synthetic_verification@271, SyntheticVerificationRequest.from_dict@287, SyntheticVerificationRequest@288, run_synthetic_verification@294, SyntheticVerificationRecord.from_dict@298, SyntheticVerificationRecord.from_dict@302.
- tests/test_temporal_generation.py: BooleanContactConfig@524, BooleanObservation@526, explore_boolean_histories@534.
- tests/test_verification_exploration.py: BooleanContactConfig@103, BooleanObservation@105, enumerate_boolean_histories@118, explore_boolean_histories@152, ExplorationReport.from_json@164, BooleanContactConfig@171, BooleanObservation@173, BooleanObservation@173, explore_boolean_histories@178, ExplorationReport.from_dict@189, explore_boolean_histories@238, explore_boolean_histories@242, BooleanObservation@250, BooleanContactConfig.from_json@256, explore_boolean_histories@266, BooleanContactConfig.from_json@270, BooleanObservation@280, BooleanObservation@281, BooleanContactConfig.from_dict@308, AdversarialConfig@315, generate_adversarial_histories@318, generate_adversarial_histories@319, AdversarialConfig.from_json@340, HistoryCase.from_json@342, generate_adversarial_histories@344, AdversarialConfig@355, BooleanContactConfig@356, BooleanObservation@358, generate_adversarial_histories@366, FailureSignature.from_diagnostic@399, reduce_counterexample@400, ReductionResult.from_json@409, FailureSignature.from_json@410, FailureSignature.from_counterexample@417, FailureSignature.from_counterexample@420, FailureSignature.from_counterexample@428, FailureSignature.from_diagnostic@439, reduce_counterexample@442, reduce_counterexample@449, reduce_counterexample@452, FailureSignature.from_diagnostic@462, reduce_counterexample@465, ReductionResult.from_json@470, ReductionResult.from_json@474, FailureSignature.from_diagnostic@481, reduce_counterexample@483, reduce_counterexample@498.

Package-root exports are also in src/biocompiler/__init__.py. CLI discovery and
historical inspection include both bound/report variants, reduction and workflow
records; preserve those readers even where they execute no fresh check.

## Required focused original test inventory

Keep every method in these modules (50 total), including shared fixtures and
existing tests whose only direct workflow use is inside an imported example or
CLI command. Keep the full prior cohort in parallel.

### tests/test_verification_exploration.py (14 methods)

- BooleanExplorationTests.test_full_presence_and_boolean_state_product_has_no_missing_or_duplicate_histories
- BooleanExplorationTests.test_report_counts_outcomes_and_coverage_separately_from_enumeration_completion
- BooleanExplorationTests.test_capped_prefix_never_claims_exhaustive_completion_or_all_passed
- BooleanExplorationTests.test_callback_results_must_match_history_horizon_dependencies_and_requirements
- BooleanExplorationTests.test_unicode_ids_use_the_existing_checkers_history_hash_format
- BooleanExplorationTests.test_lone_unicode_surrogates_are_rejected_in_configs_and_results
- BooleanExplorationTests.test_config_rejects_invalid_times_observations_suffixes_and_imports
- AdversarialHistoryTests.test_seeded_histories_cover_named_transitions_and_separate_incomplete_case
- AdversarialHistoryTests.test_adversarial_sampling_does_not_allocate_its_huge_cartesian_product
- CounterexampleReductionTests.test_deletion_preserves_initial_state_horizon_and_selected_failure_not_unknown
- CounterexampleReductionTests.test_response_signature_keeps_obligation_object_and_state_without_fixing_failure_time
- CounterexampleReductionTests.test_budget_exhaustion_and_different_initial_failure_never_claim_minimality
- CounterexampleReductionTests.test_import_rejects_changed_requirement_inventory_and_reducer_policy
- CounterexampleReductionTests.test_reduction_rejects_stale_callback_results_or_changed_model_dependencies

### tests/test_synthetic_verification_workflow.py (10 methods)

- SyntheticVerificationWorkflowTests.test_check_json_roundtrip_and_current_replay
- SyntheticVerificationWorkflowTests.test_unknown_and_unsupported_are_retained_without_preacceptance
- SyntheticVerificationWorkflowTests.test_mixed_bounds_enumerate_cell_reset_and_contact_presence
- SyntheticVerificationWorkflowTests.test_capped_passing_prefix_is_not_complete_or_all_passed
- SyntheticVerificationWorkflowTests.test_cell_only_space_and_exact_snapshot_inventory
- SyntheticVerificationWorkflowTests.test_wrong_reset_model_reduces_only_the_selected_inactive_failure
- SyntheticVerificationWorkflowTests.test_complete_independent_authority_binds_history_horizon_mode_and_model
- SyntheticVerificationWorkflowTests.test_narrowed_rehashed_campaign_cannot_replay_under_original_bounds
- SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay
- SyntheticVerificationWorkflowTests.test_strict_json_operation_shapes_and_report_counts

### tests/test_verification_campaign.py (3 methods)

- VerificationCampaignTests.test_presence_aware_space_complete_and_coverage_explicit
- VerificationCampaignTests.test_reduction_keeps_selected_failure_and_explicit_horizon
- VerificationCampaignTests.test_reports_roundtrip_and_cli_inspection_cannot_recheck

### tests/test_temporal_generation.py (15 methods)

- TemporalGenerationTests.test_existing_literal_contact_matrix_is_preserved_by_generation
- TemporalGenerationTests.test_existing_literal_pulse_matrix_condition_and_event
- TemporalGenerationTests.test_existing_literal_dependent_memory_matrix
- TemporalGenerationTests.test_held_for_fall_and_rapid_rerise_start_a_complete_new_interval
- TemporalGenerationTests.test_cell_temporal_operand_runs_without_contacts_and_survives_dropout
- TemporalGenerationTests.test_contact_timers_do_not_share_sustained_intervals
- TemporalGenerationTests.test_contact_event_refresh_differs_from_cell_condition_pulse
- TemporalGenerationTests.test_new_contact_onset_refreshes_memory_while_another_remains_active
- TemporalGenerationTests.test_memory_without_duration_remains_set_until_reset
- TemporalGenerationTests.test_premature_pulse_expiry_fails_independent_check
- TemporalGenerationTests.test_bounded_dwell_campaign_covers_all_81_declared_histories
- TemporalGenerationTests.test_temporal_profile_still_rejects_unsupported_recent_history
- TemporalGenerationTests.test_explicit_profile_roundtrip_and_pipeline_keep_software_scope
- TemporalGenerationTests.test_temporal_candidate_uses_explicit_discrete_event_component_interfaces
- TemporalGenerationTests.test_profile_catalog_and_schema_pins_reject_stale_authority

### tests/test_synthetic_design_workflows.py (8 methods)

- SyntheticDesignWorkflowTests.test_selected_temporal_components_package_reconstructs_every_stage
- SyntheticDesignWorkflowTests.test_rehashed_component_and_selection_documents_do_not_establish_acceptance
- SyntheticDesignWorkflowTests.test_unconstrained_default_stays_at_mechanism_and_does_not_invent_search
- SyntheticDesignWorkflowTests.test_selected_pipeline_receipts_expire_when_selection_policy_changes
- SyntheticDesignWorkflowTests.test_component_package_and_selection_cli_report_actual_scope
- SyntheticDesignWorkflowTests.test_cli_retains_unknown_and_replays_without_turning_it_into_pass
- SyntheticDesignWorkflowTests.test_cli_capped_campaign_and_selected_failure_reduction
- SyntheticDesignWorkflowTests.test_invalid_cli_and_failed_atomic_publication_preserve_previous_report

## Audited source hashes

These identify inspected source content, not a tested Git revision.

- src/biocompiler/verification/exploration.py: a4b85d8b0f48198128bc9064fa065eddc8c5f6acb4d68d92a21008c79723ca98
- src/biocompiler/compiler/verification_workflow.py: 04d9818933ae3ded190d4139023340f88c1eb7d8f2325173c4c77c056f7b7dd6
- src/biocompiler/compiler/request.py: 6b87777cfad4a06fe485e6fb4d29bdd02312f99df5193ea0d3351a57e1065caf
- src/biocompiler/ir/serialization.py: 4d5ad0c7572a3ca70159dc4657c1815e85ff62cc37f542f8584200964a0149e3
- src/biocompiler/cli.py: eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0
- examples/verification_campaign.py: ab9da8553235963a8164641e85c759b3ddfde297cac7813215b1dd7d58ab7604
- examples/synthetic_verification.py: 5ab8fe27967eb21288389a6fc4385d811c875ed23cdcb5d76f8b3ac4e9c4ec12
- examples/synthetic_design.py: be35a2742e790157b7ca4fe9a77453b0b217bdfe4533a5dcc893fee8f7cfd70a
- tests/test_verification_exploration.py: 7b0225c8b0c85635fc94b64f6a8904c66ec90f4a012f82059a5c8eaf65e37ecc
- tests/test_synthetic_verification_workflow.py: 77f20911b8eddff90f0294137dfadd9a57fe14a3cc0402bc7875e890c40f1124
- tests/test_verification_campaign.py: 830871446966615da8ed64ced213a650265311b0309f017ec8a75cb18273a11f
- tests/test_temporal_generation.py: 365d84c37be73619f1a7d099e4e1b405b623d27bd5fe360f9699a1dfe204ba0d
- tests/test_synthetic_design_workflows.py: c00c25121d5437f1d5c9419d5be9e2286d5f7e8abac4e29213dea6a521dd1322

## First coherent implementation split

Implement and capture the whole three-operation runtime before advertising any
new endpoint. A check-only workflow profile is not the R5 deliverable.

1. **Domain agent:** the two proposed domain modules, complete eleven artifact
   codecs/constructors/getters and derived fields, strict workflow InputFrame
   importer, immutable request/result sum types and independent domain tests.
   Coordinate staged checked import with runtime ownership; no checker imports
   in domain. Every imported historical result remains distinguishable from a
   newly computed one.
2. **Runtime agent (this audit's suggested next ownership):**
   core/lib/realization_checker/verification_workflow_budget.ml/.mli,
   verification_exploration.ml/.mli and synthetic_verification.ml/.mli;
   core/test/test_verification_exploration.ml and
   core/test/test_synthetic_verification_workflow.ml. Implement full enumeration,
   mixed/contact reports, adversarial utility, signature-preserving reduction,
   staged fresh request authority, both modes, all operations and complete replay.
   Public engine signature is conceptually:
   explore ?limits ?parent bounds ~evaluate -> Exploration_report.t;
   reduce ?limits ?parent ~history ~until ~signature ~max_evaluations ~evaluate
   -> Reduction_result.t. The evaluator receives the shared ancestor and exact
   effective child controls. Fullworkflow exposes decode_checked, run and replay
   plus usage variants; replay requires independently supplied expected_request.
   No public endpoint can select the abstract test evaluator.
3. **Capture/client agent:** new full original corpus and callback transcripts,
   mutation census, strict raw workflow transport/backend/SDK and CLI tests,
   complete installed no-fallback campaign. Preserve existing scientific callback
   APIs explicitly; no authoritative Python summary/minimality construction on
   selected native workflows. Do not use native output as expected literals.
4. **Root:** freeze workflow resource/capability contract, native workflow service
   and both-role dispatch, Dune/dependency boundaries, all required CI gates,
   protocol/roadmap documentation and hosted integration/merge evidence.

Freeze the domain/runtime interface before heavy edits. Workflow_budget must own
one ancestor over imports and every leaf call, cumulative retention of live
results and exact final publication. Do not reuse the direct service's repeated
fragment reservation without checking full 625-history report capacity. Reserve
and transfer prospective publication inventory when references become part of a
wrapper; charge all scans while avoiding false double-counting of released or
transferred memory. A bounded workflow-specific aggregate work ceiling is a
necessary new policy, while every leaf remains under its existing limits.

Suggested implementation-order checkpoints are complete domains, complete
callback-parametric engine plus fixed wholeworkflow delegates, then one service/
SDK/CLI batch exposing all three operations. Each checkpoint retains explicit
unimplemented scope until the final wholeworkflow hosted conformance passes.

## R5 runtime accounting derivation and staged ownership (2026-10-02)

This section supersedes the provisional `100000 * 50M + 32 * 64MiB` work
allowance. The original checker retains its complete 50,000,000-unit child
allowance for every evaluation. History generation, workflow settings,
structural result validation, aggregation, historical import, replay comparison
and output encoding charge the same operation ancestor, outside that child.
Semantic `max_histories` / `max_evaluations` remain unchanged (maximum 100,000).
Exhaustion remains a resource exception, never a shortened successful campaign
or a minimality claim. Native compilation/execution of this correction remains
hosted validation work; the initial PR58 revision's passing suites do not test it.

The domain codec exposes `Codec.work_bounds`. Its conservative successful-pass
bounds, with UTF-8 canonical bytes `b` and key-plus-value occurrences `n`, are:

- `M(b,n) = 88b + 4608n + 1` for measuring/preflighting.
- `F(b,n) = 181b + 9216n + 3` for full canonical fingerprinting.
- `H(b,n) = 320b + 14000n + 8` for the streamed legacy ASCII history identity.
- `G(b,n) = M(b,n) + 256b + 128n + 131072` for a generated bounded history.
  The generation bound measures the at-most-sixteen-frame prefix, caches the
  validated fixed-suffix census, and charges only actual emitted declarations.
  It does not charge an entire large suffix separately for every variable frame.

These are upper envelopes, not fixed charges: the codec charges actual scalar
kinds, byte lengths, list walks and per-object key sorting. In particular,
non-numeric nodes no longer incur two hypothetical binary64 conversions.
The domain audit and tests document these bounds in the public workflow plan.

Use `A=67,108,864`, `N=1,000,000`, `L=33,554,432`, `J=500,000`.
`J` deliberately preserves the historical CheckResult boundary: its legacy
250,000-node limit counts values only, so typed callback/historical results may
approach 500,000 key-plus-value nodes. Native checker output still has its
existing 250,000 key-plus-value-node ceiling, 32MiB byte ceiling and 100,000
monitor-item ceiling. No historical result is rejected merely to fit the
smaller native checker node convention.

A selected-signature scan is bounded by
`S = 160L + 1024J + A + 16384`. Every generated signature has nine fixed fields;
its total byte volume is at most eight times the source diagnostics or
counterexamples, and each source record consumes at least eleven nodes.
The selected signature's own bytes are separately included. This is tighter
than multiplying the generic worst-case numeric encoder cost by every
string/null-only signature.

The runtime declares these per-trial envelopes:

| Phase | Derived bound | Exact units |
| --- | --- | ---: |
| Reduction trial `R` | `H(A,N) + 4M(L,J) + 2F(L,J) + S + 32L + 8N + 16000000` | 84,910,277,138 |
| Exploration trial `E` | `G(A,N) + H(A,N) + 5M(L,J) + 2F(L,J) + 32L + 8N + 16000000` | 112,040,813,076 |
| Retained report validation `V` | `G(A,N) + H(A,N) + M(L,J) + 2F(L,J) + 16L + 8N + 8000000` | 90,468,782,096 |

`R` includes result/settings validation, complete history identity, two stable
metadata fingerprints, selected-failure scanning, accepted-result sizing, and
list/persistent-inventory charges. `E` replaces signature scanning with bounded
history construction and includes both incremental fragment reservation and
complete result sizing. `V` reconstructs each required prefix history and
rechecks its full dependency/horizon/inventory claims without invoking a
checker. Extra byte/node terms cover cached-volume precharges, constant wrapper
fields, list copying, and prospective workspace reservations. The typed
CheckResult dependency replacement preserves the already-validated unchanged
body; it does not repeatedly reimport all diagnostics/counterexamples in each
trial. Newly supplied historical results still undergo complete charged import.
The fixed native dependency envelope has at most twenty settings, fewer than
8192 bytes and at most 128 nodes (controlled version/enumeration strings and
64-hex identities, with finite horizons). Its explicit preflight plus three
inherited dependency measurements fit the per-trial 16M scaffold allowance.
The complete updated report is measured once and the typed helper's inherited
ASCII measure is prepaid once; result validation and accepted-result sizing
supply the other two full-result measurements in `R`. Generic callbacks do not
perform this fixed-checker settings extension.

A structurally valid complete CheckResult consumes at least 51 key-plus-value
nodes: nineteen outer nodes including the dependency placeholder and at least
thirty-two further dependency nodes. Thus a retained complete report has at
most `K=floor(1000000/51)=19607` results. One further callback may run before
incremental retention rejects its result. This bound does not change the
100,000 semantic cap; it follows from the separately declared 1M-node artifact
capacity. Historical import and final report validation each perform at most
`K` history reconstructions. Discarded reduction trials are separately allowed
up to the full 100,000 evaluations; their result bytes are never accumulated
into the retained 64MiB report quota.

The fixed import/final/replay/publication allowance is:

`Z = 128F(A,N) + 128M(A,N) + 256A + 256N + 400000000`
`  = 4,098,000,274,944`.

The constructor census behind this allowance includes three independent Bounds
imports during exploration replay: the independent request, the historical
embedded request, and the historical report's configuration. Constructor-order
validation and nested observation/frame decoding bound each import by
`6M + 6F + 8192b + 1024n + 2000000`, at most `24(M+F)` at the declared maxima.
Those three imports account for at most 72 paired passes. The remaining 56
paired passes cover complete request/record and result dispatch preflights,
whole historical CheckResult imports (at most thirteen measuring passes over
their cumulative retained volume), final domain construction, derived-field
identity checks, complete record fingerprints, raw replay comparison and the
final charged output encoding. The extra linear terms cover reads, hashes,
framing, list inventories, source-authority staging and fixed constructors.
Repeated per-result history validation is in `V`, not hidden in this fixed
allowance. No final 64MiB serialization allowance is multiplied by 100,000.

The default is the maximum of the full operation bounds:

- Reduction: `100000 * (50000000 + R) + Z = 8,500,125,714,074,944`.
- Exploration: `(K+1) * (50000000 + E) + 2K*V + Z = 5,749,617,484,181,696`.
- Adversarial generation has at most 1005 cases (four named, at most 1000 seeded,
  one incomplete), and is below both preceding bounds even when each case is
  conservatively charged at the full history/artifact envelope.

The profile therefore declares **8,500,125,714,074,944** maximum work units. This
is below `2^53-1 = 9,007,199,254,740,991`, fits the supported native integer, and
remains an exact JSON integer for Python and prospective TypeScript consumers.
Both profile initialization and native tests assert the ceiling. The integer
is computed from named terms in the implementation, not rounded to a decimal
power or chosen by truncating accepted histories.

### Live inventory and allocation order

Per-artifact ceilings remain 64MiB and 1M key-plus-value nodes. Aggregate
independent-authority plus historical-record input is separately bounded at
80MiB plus 64KiB framing and 2M nodes. The selected request byte reduction
applies to that aggregate; each fragment also passes its own artifact bound.
The service separately enforces the existing 16MiB independent request limit.

The runtime live-inventory ceiling is **8,000,000 bookkeeping slots**, distinct
from the 1M-node publication limit. Its concurrent inventories are explicitly
bounded: at most 1M retained report occurrences, up to 500k prospective callback
result occurrences, up to three 1M-scale original/current/trial or reconstruction
inventories, and up to 4M slots for two nested domain-import workspaces. The
extrema are not all simultaneously allocated: native frame prefixes have at
most sixteen snapshots/eight contacts/eight observations per scope, reduction
trials copy list spines while sharing sealed frame values, and import workspaces
finish before evaluation. Eight million covers the reachable combinations
without reducing a valid 1M-node historical artifact. Each native checker
retains its separately declared bounded internal monitor profile.

Before constructing a generated prefix, the runtime reserves three copies of
its explicit worst-case node inventory (raw prefix, hydrated frames and
reconstruction scratch). Reduction reserves the entire reverse-prefix and
trial-list inventories before cons/reverse operations. An accepted trial
transfers its reservation to the retained current history; discarded trials
release theirs. Replacements reserve the new result before releasing the old
one. Exception cleanup releases scoped inventories and never refunds work.

Domain construction, import, raw comparison and final encoding reserve bounded
2M-slot workspaces before traversal/allocation. Nested record/request decoding
therefore reserves 4M slots on the same budget. History preflight counts sealed
frame contents before constructing per-frame JSON and rejects cumulative
byte/node overflow before building an aggregate history value. Final
publication reserves the full new retained census before transferring the old
child inventories; it preserves any enclosing scoped workspace reservations.
No output buffer is treated as authority, and each encoded buffer retains its
own fixed 64MiB (workflow) or inherited per-frame ASCII ceiling.

### Replay equality and service composition

Fresh replay first compares the independently retained complete request
fingerprint, reruns the entire operation, and compares complete canonical record
fingerprints. When raw historical JSON is supplied, both raw and rebuilt trees
receive strict charged preflight and an exact `Json.equal` comparison. The
implementation of that equality was inspected: integer and float variants stay
distinct; finite floats compare exact bits, preserving negative zero; UTF-8
strings compare exact decoded contents; objects compare sorted unique keys;
array order is retained. These are the existing canonical serialization's
identity distinctions. Cycles, duplicate keys and nonfinite/invalid scalars are
rejected before recursive comparison. This avoids simultaneous full 64MiB
canonical string allocations while preserving the complete canonical identity
check; it does not substitute an outcome comparison or normalized subset.

Service composition uses exactly one caller-owned budget:

1. `Verification_workflow_budget.create ?limits ?parent ()`.
2. Pass `B.charge budget` to bounded descriptor-read, parse and hash work.
3. `B.reserve_request budget raw` exactly once for every complete incoming
   independent-authority/historical artifact fragment.
4. `Synthetic_verification.decode_request_in` / `decode_record_in ~budget`.
5. `run_in ~budget` or `replay_in ~budget ~raw_record ~expected_request`.
6. `B.encode_report budget (Record.to_json result)` for final artifact emission.

The `_in` entry points do not create a fresh operation budget. Their staged
imports use the checked-source decoder seam, preserving original header,
source-lowering, candidate and remaining-field rejection order. The transport
must not create a new budget for output encoding. Native tests cover exact and
one-under work/ancestor boundaries, the full 50M callback allowance, typed
historical capacity, scoped cleanup/no-refund, signed-zero/numeric-kind replay,
raw-cycle rejection, and full staged decode/replay/publication accounting.
