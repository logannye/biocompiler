# R5/R6: complete realization workflows and public routing

## Draft implementation checkpoint, 2026-10-02

The shared tree now contains the complete typed `Verification_exploration` and
`Verification_workflow` domain interfaces and implementations for all eleven
historical artifacts, plus native test source covering eleven complete original
Python documents, their exact identities, sixteen malformed-import rejections,
typed constructor round trips, and bounded-codec cases. Independent execution of
the original Python imports confirmed all eleven literals and sixteen rejection
messages. This confirms the fixtures; it does **not** validate the OCaml implementation.

The initial commit `002344cdfeca2dc599c1e21ff291b9858258c227` passed all
84 native suites on hosted Linux and macOS. The corrected source and new 85th
full-corpus suite require fresh hosted validation. The initial aggregate
encoding-work allowance and transient allocation/retention accounting required
review; the refinement and explicit bounds below replace that provisional
arithmetic and await validation at the corrected revision. Workflow transport, public SDK and
CLI routing remain incomplete; this checkpoint exposes no new public workflow
capability and does not close R5 or R6. The source audit below describes the
starting point and remains the implementation inventory, with this checkpoint
qualifying statements about modules that were absent during that audit.

Source audit of the current shared working tree, 2026-10-02. This document plans
work; it is not a native validation receipt or a completed roadmap checkbox.
It supersedes the *remaining-work inventory* in the earlier
[realization routing plan](migration-realization-routing-plan.md), without
changing its nine-operation contract or the
[language migration roadmap](language-migration-roadmap.md).
The original audit was read-only. The draft implementation checkpoint above records
the subsequent source additions; no local native compilation or execution was used.

## Domain resource accounting refinement

The accounting refinement after the initial PR #58 checkpoint preserves the
64 MiB artifact, 1,000,000 key/value node, depth-128, 4 MiB string, and
4,300-character number limits. It does not change semantic schemas, canonical
bytes, historical import rules, or the existing checker's 50,000,000 work units.
The original checkpoint compiled on hosted Linux and macOS; the refinements
below require a new hosted run. No native execution was performed locally.

`Codec.inspect` now records actual writer work while performing the bounded
inspection. Only floats pay the binary64 conversion charge. Only object keys
contribute to sorting work. Before calling the encoder, it charges the recorded
writer work plus three output-byte passes for buffer growth/copying. SHA-256 is
charged separately. No global sort of all content bytes or blanket `8192 * nodes`
charge remains. Ancestor-cycle detection, bounded/cyclic list-spine handling,
queued-child accounting, escaped-key sizes, and duplicate-key rejection remain.

For canonical UTF-8 byte count `b` and **key plus value** occurrence count `n`,
`Codec.work_bounds` exposes the following conservative individual-pass bounds:

| Operation | Work-unit upper bound |
| --- | --- |
| `M(b,n)`, inspect/measure | `88*b + 4608*n + 1` |
| `E(b,n)`, complete encode including inspection | `180*b + 9216*n + 2` |
| `F(b,n)`, fingerprint including encode | `181*b + 9216*n + 3` |
| `H(b,n)`, streamed ASCII history fingerprint | `320*b + 14000*n + 8` |
| `G(b,n)`, lattice history construction | `M(b,n) + 256*b + 128*n + 131072` |

These are charge bounds, not elapsed-time estimates. The inspection census has
at most `n` enters and `n` container exits, each charged 129 units for bounded
ancestor work; node and spine visits are linear. Each quoted byte is charged
four units. Integer conversion is bounded by four times its decimal character
count plus one, and each float conversion by 4,096 units. Object sorting uses
`4*height*(entries + key_bytes + 1)`, with `height <= 20`. Summing over objects
bounds sort work by `80*(b + 2*n)`. The writer repeats scalar conversion and
per-object sorting, but does not repeat cycle detection. The displayed formulas
round the sums upward. At the artifact ceiling, `M=10,513,580,033`,
`E=21,295,595,522`, and `F=21,362,704,387`.

ASCII history hashing inspects each frame once and checks cumulative bytes and
nodes before passing that frame to the inherited ASCII encoder. It precharges
the encoder's measure/writer passes and up to sixfold escaping, then feeds SHA-256
incrementally. It neither serializes nor rescans a growing history prefix.
`Bounds` caches the exact inventory of its validated immutable fixed suffix.
Each generated history measures only its at-most-sixteen-frame new prefix and
combines the cached suffix inventory before hydration/concatenation. Signal-name
work is charged for emitted observations; absent contacts do not pay to traverse
unused declarations. The bound `G` includes numeric indexing, sample construction,
the prefix inspection and inherited typed-frame hydration.

For a checked result `c`, history `h`, and selected signature byte size `s`, use:

- `V(c,h) = M(c) + H(h) + 2*F(c) + 16*c.bytes + 128*c.nodes + 65536` for
  `validate_result`, including stable dependencies when supplied.
- `S(c,s) = 160*c.bytes + 1024*c.nodes + s + 16384` for selected-failure matching.
  Each generated signature has nine fields and only strings/nulls; its fingerprint
  costs at most `12*signature_bytes + 8192`. The source diagnostic/counterexample
  has at least eleven nodes, and the sum of generated signature bytes is at most
  eight times the complete result's bytes. This is tighter than pretending each
  signature contains a maximal population of floats.

The following constructor census uses `p` for the complete emitted artifact,
`h0/h1` for original/reduced histories, and `c0/c1` for original/final results.
Bounds are deliberately rounded upward; optional absent subrecords contribute
no traversal. They include final canonical identity creation and do not run a
checker or an evaluator callback.

| Typed constructor | Conservative envelope beyond already constructed children |
| --- | --- |
| Observation | `F(p) + 8*p.bytes + 64*p.nodes + 1024` |
| Failure signature | `F(p) + 16*p.bytes + 128*p.nodes + 8192` |
| Contact or mixed bounds | `3*M(p) + 3*F(p) + 4096*p.bytes + 512*p.nodes + 1000000` |
| Adversarial configuration | `F(p) + 8192` |
| History case | `F(p) + M(h) + 8*p.bytes + 64*p.nodes + 4096` |
| Contact or mixed report | `M(p) + F(p) + 4096*p.bytes + 1024*p.nodes + 1000000`, plus `G(h_i)+V(c_i,h_i)` for every retained result |
| Reduction | `F(p) + 4*M(h0) + 4*M(h1) + V(c0,h0) + V(c1,h1) + S(c0,s) + S(c1,s) + 32*p.bytes + 256*p.nodes + 1000000` |
| Workflow request | `F(p) + M(h) + 8*p.bytes + 64*p.nodes + 4096` |
| Workflow record | `4*F(p) + 16*p.bytes + 128*p.nodes + 65536`, plus `V(c,h)` for a check record |

Imports additionally validate nested artifacts before applying constructor
invariants. The inherited `Input_frame` decoder is precharged eight measured
frame passes plus `64*b+64*n`; `Check_result` import is precharged twelve measured
result passes plus the same linear term. The latter covers result packing,
dependency/horizon, diagnostic/source, counterexample/expected/interval/source,
and coverage paths. `check_of_json` only adds this work accounting to the existing
historical codec. Complete-snapshot validation is repeated in bounds import to
preserve original constructor-error precedence. A conservative bounds-import
census is `24*M(p)+6*F(p)+8192*p.bytes+2048*p.nodes+2000000`.
Production workflow settings extension now uses
`Check_result.with_dependencies`: both typed arguments have already passed their
structural constructors; the helper preserves every validated body field, reserves
the exact changed byte/node inventory using cached dependency sizes before building
the enclosing object, then remeasures the whole record to check nesting and refresh
its size. It makes no freshness or acceptance claim. This avoids reimporting every
unchanged diagnostic/counterexample on every trial. The independent test pair
contains the complete original Python settings-extended report and checks the
pinned ASCII fingerprint `c1cf0b6dce4032249e1e73920403950bb30f0a37792795d5024c76ef2b63f2c7`;
a separate boundary case verifies that a dependency fitting alone cannot make the
complete report exceed 32 MiB. Production dependency settings have at most twenty
entries (nine base, seven candidate, four workflow), only pinned versions/enums and
64-character identities, plus a finite horizon. Their conservative envelope is
8,192 bytes and 128 key/value nodes (the current schema uses at most 71 nodes).
This small production-only dependency decoder belongs in the fixed per-trial
scaffold allowance; arbitrary historical/generic callback settings retain the
full import/validation bounds above.

Report imports also compare all eight supplied derived fields, adding at most
two fingerprints of their aggregate volume; they still reconstruct and validate
every expected history. No trusted-construction shortcut replaces these checks.

The runtime allowance must therefore distinguish per-trial history work from
final retained-document passes. A valid `Check_result` needs at least **51**
key/value nodes (19 outer nodes, including a dependency placeholder, plus 32
additional dependency nodes). A retained report can contain at most 19,607
results under the existing million-node ceiling; one additional prospective
trial may fail publication. Generic callback/historical results allow up to
500,000 key/value nodes because the inherited leaf codec counts 250,000 values;
the production checker's stricter 250,000-node report limit is unchanged.
The runtime derivation is recorded separately in
[the native workflow plan](migration-realization-workflow-native-plan.md).
Independent authority and historical-record input volumes remain separately
bounded at 16 MiB and 64 MiB; shared nested subrecords are counted at every
serialized occurrence. Fixed import/publication allowances cannot be charged as
though every trial serializes a fresh maximum-size final report.

New native test source checks the published pass bounds on dense, wide, deep,
Unicode, binary64 and large-integer values; verifies that nonnumeric nodes avoid
float charges; compares one-frame and thousand-frame fixed-suffix generation
work; verifies streamed ASCII identity; and verifies delegated leaf precharging.
A separate pure Python structural census confirms the formulas cover the 28
complete embedded literal documents. Hosted execution remains required.

## Starting point and recommended next batch

The nine direct operations and five explicit `core=` SDK routes are implemented
in the current tree. Their current hosted gates remain a separate requirement.
The native `Generator`, `Selection` and `Components` producers also exist under
`core/lib/synthetic_producer`; do not implement those algorithms a second time.
There is no native implementation of the workflow/exploration/reduction records,
synthetic build manifest or general checked `PassManager` in the current
`core/lib` inventory. Architecture/construction workflow modules implement their
own profiles and do not establish equivalence to these Python workflows.

**Next coherent batch: complete R5 verification workflows, including both modes,
all three operations, complete retained reports and fresh replay.** Add native
workflow/exploration domain records and orchestration over the existing independent
checkers, then expose complete operation authority through both executable roles.
Route `synthetic-check`, `synthetic-explore`, `synthetic-reduce` and
`synthetic-replay` together once all four preserve existing behavior. A smaller
check-only implementation can be an explicitly partial checkpoint, but must not
claim R5 or silently execute explore/reduce in Python after native selection.

R6 should follow as three bounded batches: expose existing deterministic producer
APIs; port checked pipeline authority/freshness; then port canonical package
content and complete fresh export/rebuild. Do not remove `compile(..., core=...)`
profile rejection or reuse accepted-looking serialized stage records to skip a
missing batch.

## Complete current public consumer inventory

An AST scan of every `src/biocompiler/**/*.py` direct call to the listed API names
found the following consumers. It includes calls in nested functions and records
all current module-bound aliases. Dynamic dispatch (`builder(...)`, callback
`evaluate(...)`) is listed separately below; complete captured execution must
supplement the lexical inventory.

| Source | Calls, at current source lines |
| --- | --- |
| `cli.py` | `replay_synthetic_verification:1699`, `run_synthetic_verification:1712`, `select_synthetic:1738`, `build_synthetic_package:1834`, `publish_synthetic_package:1836`, `verify_synthetic_package:1856` |
| `compiler/verification_workflow.py` | `check_synthetic_candidate:189`, `check_realization:197`, `explore_boolean_histories:241`, `reduce_counterexample:243`, `run_synthetic_verification:271` |
| `compiler/synthetic.py` | `select_synthetic:87`, `generate_synthetic:225`, `check_synthetic_candidate:249` |
| `compiler/components.py` | `check_realization:70`, `adapt_synthetic_components:118,185`, `check_component_behavior:161,285`, `run_synthetic_pipeline:183`, `check_component_assembly:265` |
| `compiler/synthetic_build.py` | `check_synthetic_candidate:124`, `build_synthetic_package:262`, `verify_synthetic_package:277`; `builder(...)` at 116 chooses a synthetic or component pipeline |
| `synthesis/components.py` | `check_synthetic_candidate:92` |
| `synthesis/selection.py` | `_generate_synthetic:385`, `check_synthetic_candidate:397` |
| `synthesis/synthetic.py` | `_generate_synthetic:723`, `realization_dependencies:754`, `generate_synthetic:807`, `check_realization:865` |
| `verification/exploration.py` | `enumerate_boolean_histories:595`; evaluator callbacks at 597, 880 and 903 carry semantic obligations |
| `verification/realization.py` | `realization_dependencies:306` in the retained Python default branch |

The package root exports exploration functions at `__init__.py:207`, component
checking/pipeline functions at 278, the synthetic pipeline at 357, package
functions at 363, generation/checking at 397, selection at 403, workflow functions
at 409, and direct checking/dependencies at 525. The component adapter remains
available from its own public module. Preserve module imports as well as root
exports; patching only `biocompiler.check_realization` does not route these calls.
The source scan found no direct Studio consumer of this API inventory.

Existing five SDK checker branches already terminate at the native backend when
`core` is selected. Their retained default branches and nested internal calls are
historical Python behavior, not an additional completed workflow route.
`compiler/workflow.py:408-418` dispatches native `compile` only for
`PayloadArchitectureRequest` and explicitly rejects other profiles. Neither
`RealizationRequest` nor synthetic package compilation is thereby implemented.

## R5 signatures, records and identities to preserve

Current public signatures have **no `core` selection**:

- `run_synthetic_verification(request: SyntheticVerificationRequest) -> SyntheticVerificationRecord`.
- `replay_synthetic_verification(record: SyntheticVerificationRecord, *, expected_request: SyntheticVerificationRequest) -> SyntheticVerificationRecord`.
- `enumerate_boolean_histories(config: BooleanContactConfig)` yields a deterministic prefix.
- `explore_boolean_histories(config: BooleanContactConfig, evaluate) -> ExplorationReport`.
- `reduce_counterexample(history, until, evaluate, signature: FailureSignature, *, max_evaluations=1000) -> ReductionResult`.
- `generate_adversarial_histories(config: AdversarialConfig) -> tuple[HistoryCase, ...]`.

The generic callback APIs are public Python interfaces. A callback cannot cross
the wire or become a checker override. Keep their current Python behavior for
ordinary callback use. Add a separately explicit native full-authority workflow
route; if a future `core=` overload is offered on a callback API, require a
versioned declarative checker authority and reject arbitrary callbacks. Do not
claim that a native check per callback has migrated aggregate semantic decisions.

Records below inherit `verification/exploration.py:_Record` unless noted. That
codec requires exact fields, strict known schemas and UTF-8, invokes all nested
decoders/constructors, and compares every derived field by canonical fingerprint.
All these outer artifacts use `JsonArtifact` compact sorted **UTF-8** identity.
Embedded `CheckResult`, `DependencySnapshot` and history identities retain their
existing compact sorted **ASCII** identity. Their encodings must not be unified.

| Record / schema suffix (all begin `biocompiler.`) | Complete declared fields and defaults |
| --- | --- |
| `SyntheticVerificationRequest` / `synthetic_verification_request.v0.1` | `realization`, `candidate`, `operation`; `mode="candidate"`, `history=()`, `until=None`, `bounds=None`, `signature=None`, `max_evaluations=None` |
| `SyntheticVerificationRecord` / `synthetic_verification_record.v0.1` | `request`, `result`; `workflow_version="biocompiler.synthetic_verification_workflow.v0.1"`, exact historical `claim_scope` |
| `BooleanObservation` / `boolean_observation.v0.1` | `signal_id`, `field="present"`; fields only present/high/low |
| `BooleanContactConfig` / `boolean_contact_config.v0.1` | `contact_ids`, `observations`, `variable_times`, `until`; `fixed_suffix=()`, `max_histories=10000` |
| `BooleanInputConfig` / `boolean_input_config.v0.1` | All contact-config fields plus `cell_observations=()` |
| `ExplorationReport` / `boolean_exploration_report.v0.1` | `config`, ordered `results`, `explorer_version="biocompiler.boolean_exploration.v0.1"`, exact contact-only claim |
| `BooleanInputExplorationReport` / `boolean_input_exploration_report.v0.1` | Same report fields, mixed config, `explorer_version="biocompiler.boolean_input_exploration.v0.1"`, exact mixed claim |
| `FailureSignature` / `failure_signature.v0.1` | `kind`, `requirement_id`; `code`, `rule_id`, `specification_id`, `contact_id`, `state`, `node_id` all default None |
| `ReductionResult` / `history_reduction.v0.1` | `original_history`, `history`, `until`, `signature`, `original_result`, `result`, `evaluations`, `one_minimal`; `reducer_version="biocompiler.boolean_exploration.v0.1"` |
| `AdversarialConfig` / `adversarial_history_config.v0.1` | `bounds`, `seed`, `random_cases=16` |
| `HistoryCase` / `adversarial_history.v0.1` | `id`, `kind`, `history`, `until`, `config_fingerprint`, `intentionally_incomplete=False` |

Exploration reports additionally serialize **all eight** checked derived fields:
`state_count`, `possible_histories`, `evaluated_histories`, `complete`,
`all_passed`, `outcome_counts`, `coverage_totals`, `shared_dependencies`. Preserve
these on output, import disagreement rejection and fresh replay; a list of fresh
per-history verdicts alone is not the report.

`SyntheticVerificationRequest` distinguishes three exact shapes. Explore requires
bounds, empty history and all of until/signature/max_evaluations null. Check and
reduce prohibit bounds and require a nonempty history beginning at zero, strictly
increasing times within an explicit finite nonnegative horizon. Consequently the
constructor's `until=None` default is **not valid** for those operations. Check
prohibits reduction controls. Reduce requires a signature and an actual integer
budget in 1..100000. Preserve constructor/import error order and rejection text;
do not silently fill an effective horizon from the last frame.

Workflow `_checker` selects candidate provenance acceptance or direct model
checking, then adds four authoritative `dependencies.settings` fields:

- `verification_workflow = biocompiler.synthetic_verification_workflow.v0.1`;
- `verification_mode = candidate|model`;
- `verification_candidate = full candidate fingerprint`;
- `verification_realization = RealizationRequest.artifact_fingerprint`.

These must be produced by native workflow checking. Python `replace(result, ... )`
after a native direct check changes the authoritative report and is not a native
workflow. Model mode still has complete supplied source/request authority: the
historical request import constructs `RealizationRequest` and validates lowering.
Validate that source once through native `Checked_request`; model mode then uses
the candidate's actual mechanism/map without asserting synthetic provenance.
Preserve candidate mode's separate source/catalog/provenance obligations.

Current replay checks independent request fingerprint, reruns the declared
operation with current tools, and compares the **entire** rebuilt record
fingerprint. A failure, unknown, unsupported or capped campaign can replay
successfully. Request mode, unused controls, exact source artifact, candidate,
history, bounds, suffix, horizon, selected failure and budgets all remain bound.
Require full report bytes as well as identity at the new transport boundary.

## Enumeration, reduction and proposal responsibilities

Port [exploration.py](../src/biocompiler/verification/exploration.py) as a complete
algorithm/record cohort, including constructors, import rules, properties,
summary ordering, error precedence and original callback-corruption witnesses.

- Contact-only bounds have 1..8 contact IDs and 1..8 observations. Mixed bounds
  may have no contacts if it has cell observations; up to eight cell observations
  are allowed, and a signal cannot be both cell-local and contact-local.
  Both require 1..16 variable times starting at zero, followed by an exact complete
  fixed suffix, and `max_histories` in 1..100000. Preserve declaration order.
- State count is `(1 + 2**n_contact_observations)**n_contacts`, multiplied by
  `2**n_cell_observations` for mixed bounds. Contact absence is distinct from a
  present contact with all false values. `_snapshot` decodes cell bits first,
  then contacts in declared order. `_history_at` decodes lattice positions from
  right to left, and appends the supplied suffix unchanged.
- Enumerate indices `0 .. min(possible_histories,max_histories)-1`. Preserve every
  result in order. A capped all-PASS prefix has `complete=False` and
  `all_passed=False`; UNKNOWN/UNSUPPORTED do not become FAIL or prove infeasibility.
- `_validate_result` binds exact ASCII history identity, supplied/effective
  horizon and stable dependencies. Stable dependencies exclude **only history**;
  horizon, all model/source/target/tool/settings values remain. Preserve Python's
  numeric equality where historically used and exact canonical numeric spelling
  where fingerprints are used. Checked requirement order must remain stable.
- Aggregate all four outcome counts and all four coverage counters, returning
  coverage totals in sorted requirement-ID order. Do not infer coverage from PASS
  counts or enumeration completeness.
- Reduction starts with a fresh original check, counting it as evaluation one.
  It tries deleting positions 1 onward, retains frame zero and the original
  horizon, accepts only the selected exact FAIL signature, and restarts after
  each successful deletion. Preserve candidate trial order and evaluation count.
  Budget exhaustion returns `one_minimal=False`; exhausting every legal single
  deletion returns True. A one-frame history can be one-minimal at budget one.
  Neither means global minimality. Keep both complete original/final results.
- Response signatures bind requirement, rule, specification, contact and
  active/inactive state, deliberately excluding failure time. Diagnostic
  signatures bind code, optional requirement and node; different failures,
  UNKNOWN and UNSUPPORTED cannot replace the selected failure.

The native production evaluator must be fixed to the complete workflow authority;
no wire callback or supplied outcome override. A native test-only functor can
replay captured bad callback reports and prove stale history/dependency/inventory
rejection. Do not remove the public Python callback tests because production
native calls use a fixed evaluator.

Adversarial histories are proposals, not completeness claims. Python may retain
this explicitly separate scientific proposal API, provided records, deterministic
seed identity and their limited claim remain unchanged. Preserve its four named
transition cases, `random_cases` SHA-256-counter samples, and final intentionally
incomplete observation case; its exact contact-only config restriction, seed
0..2**64-1, and random-case cap 1000 remain. Never allocate the whole Cartesian
space to sample it, or relabel its records as exhaustive exploration.

## R5 protocol, SDK and CLI implementation contract

1. Add pure native domain modules for the complete records above. They must not
   import checkers/producers. Structural decoding of nested realization authority
   remains separate from fresh `Checked_request` source validation.
2. Add an independent native workflow checker/orchestrator with fixed candidate
   and model checker routes. Build complete mode-augmented CheckResults natively,
   then full exploration/reduction and workflow records. One parent work budget
   covers import, source validation, every check, retained trial/result data,
   aggregate counts, replay comparison and final publication.
3. Freeze a new explicit workflow capability profile. Suggested operation names
   are `run-synthetic-verification` and `replay-synthetic-verification`, with the
   versioned request's operation discriminator selecting check/explore/reduce.
   These names are proposals, not current advertised capabilities. Payloads must
   include explicit profile/resource controls and full `request`, or independent
   `expected_request` plus complete historical `record`. Bind raw authority
   separately from normalized request/report identities. Replays exclude only the
   historical record from the independent-authority digest.
4. Expose this verifier-safe workflow through both roles; it proposes no mechanisms
   and must not link `synthetic_producer`. Enumeration/deletion of input histories
   belongs to the checker workflow here. Preserve dependency-only and direct-model
   scopes as distinct existing operations.
5. Extend strict Python transport and **raw-document** workflow adapters. Freeze
   all caller containers before negotiation/I/O; negotiate every complete profile;
   reject missing/wrong cores and preserve cancellation/timeout/structured errors;
   never fall back to Python. Return complete immutable record bytes, not a PASS
   summary or a reusable checked token.
6. Resolve SDK hydration deliberately before promising historical return-type
   compatibility. `SyntheticVerificationRecord.from_dict` recursively invokes
   `RealizationRequest.from_dict` and Python lowering; exploration constructors
   regenerate histories and validate derived semantic claims. They are **not**
   among the three audited pure direct-result codecs. Do not add them wholesale
   to an execution-guard allowlist or bypass frozen constructors with object hacks.
   The practical first route is an explicit immutable native record view/raw
   backend for the CLI. If the opt-in public SDK returns that view, document its
   return-type distinction and preserve complete field/codec behavior; if exact
   historical class identity is required, first design and audit a supported
   structural hydration path separated from semantic validation. Keep the Python
   default and its original constructors intact until that decision is implemented.
7. Add explicit core/verifier executable, digest and timeout options to the four
   workflow commands. Reuse the validated architecture flag behavior: no implicit
   executable search/build/download, positive finite timeout, and no digest/timeout
   without an executable. Decode raw authority directly on native routes before
   any legacy `SyntheticVerificationRequest/Record.from_json` call.

Current CLI behavior to retain from `cli.py:1610-1730`:

| Command | Authority and flags | Successful execution exit semantics |
| --- | --- | --- |
| `synthetic-check` | `--request` required; optional `--output` | 0 only for PASS, otherwise 1 |
| `synthetic-explore` | Same; request operation must agree | 0 only for complete `all_passed`, otherwise 1 |
| `synthetic-reduce` | Same; explicit failure/budget inside request | 0 only for `one_minimal`, otherwise 1 |
| `synthetic-replay` | positional historical record, required `--expected-request`, optional `--output` | 0 for exact fresh reproduction, including non-PASS |

Retain full report publication for nonpassing outcomes, historical summary fields,
software-only/no-human-admission claims, stderr errors and exit 2 on operational
failure. `_publish_report` rejects overwriting any independent input, missing
parent directories, symlinks and nonregular destinations; it flushes/fsyncs and
atomically replaces one output, preserving prior output on failure. Python owns
these filesystem actions, not report content. Keep output formatting and terminal
newline where exact file compatibility is expected.

**Resource/transport prerequisite:** existing CLI reads request JSON up to 16 MiB,
historical reports up to 64 MiB and publishes reports up to 64 MiB. Current core
wire limits are 16 MiB requests/32 MiB responses, before complete wrapper overhead.
A valid historical workflow can therefore exceed the direct protocol; replay can
exceed its request bound even if the original output fit. Record this as a real
compatibility decision before declaring full CLI parity. Measure complete original
and boundary fixtures; either add a separately versioned bounded framing/streaming
contract with exact whole-artifact binding, or explicitly expose a limited profile
and leave the unsupported full-workflow exit open. No truncation, outcome-only
replay, arbitrary file-path escape hatch or silent Python fallback.

Compute large Cartesian counts as exact bounded integers without materializing
histories. Retain only the configured prefix and all required reports. Keep
`max_histories`/`max_evaluations` semantic controls separate from work/memory/output
budgets: resource exhaustion is an explicit resource failure, not a forged capped
campaign or a false minimality marker. Charge/reserve before expansion, retained
report allocation and aggregate serialization, including object keys, UTF-8/ASCII
expansion, duplicated authority in records and the complete transport envelope.

## R6: producers, checked pipelines and packages

### Existing producers to expose, not reimplement

| Current Python API | Existing native implementation | Remaining public work |
| --- | --- | --- |
| `generate_synthetic(request, *, config=None)`; private `_generate_synthetic` captured separately | `Generator.generate` / `Generator.propose` | Explicit producer-role operation and SDK routing, complete config/Unsupported errors and candidate identity |
| `select_synthetic(request, history, *, until=None, config=None)` | `Selection.select`; complete `Synthetic_selection` codecs | Full alternatives, hard-rejection order, actual fresh checks, fixed two-strategy ranking, UTF-8 result and ASCII history identity; no selection claim from a single accepted candidate |
| `adapt_synthetic_components(request, candidate, history, *, until=None)` | `Components.adapt` | Full registry/composition/acceptance result; fresh synthetic PASS precondition; no linking/biological upgrade |

All native producers already accept the same five reduced limits and a parent
work budget. Preserve their exact semantics rather than use private checker
witness graphs as producer results. Keep them out of standalone verifier links.
The native selector's proposal-injection functor is a test seam, not a wire
extension point. Its output retains all generation failures and hard-policy/
finite-history rejections before ranking. `synthetic-select --request` currently
imports a **SyntheticBuildRequest**, uses its realization/history/until/config,
prints the full selection report, publishes atomically if requested, and exits 0
only when a candidate is selected (1 otherwise, 2 on error).

### Checked pipeline authority is separate work

Both pipeline signatures are `(request: RealizationRequest, history, *, until=None,
config: SyntheticGeneratorConfig|None=None)` with no core selection. Synthetic
pipeline output is `SyntheticBuild(candidate, result, manager, selection_result=None)`;
component output also includes `assembly`, `link_result`, `behavior_result`.
The returned mutable `PassManager` is part of the public freshness interface,
not just an implementation detail that may silently disappear.

Port the complete authority in
[pipeline.py](../src/biocompiler/compiler/pipeline.py) and
[passes.py](../src/biocompiler/compiler/passes.py): `ScopedObligation`, `CheckSpec`,
`CheckDecision`, `PassContract`, `PassContext`, `ComponentInputContract`,
`CompletionProfile`, `StageRecord`, `PipelineResult`, `PassResult`, and their
constructors/codecs/properties. Preserve public manager registration, controlled
component admission, `add_input`, `set_dependency`, `get`, `run`, and `result`.
Frozen serialized `stage_record.v0.1` contents never confer manager acceptance.

Native authority must enforce stage/schema/profile/target/capability checks,
required providers, input requirement inventories, nested operation inventories,
full source/observation correspondence, evidence-kind-scoped discharges,
producer obligation restrictions, invalidated analyses, accepted ancestors and
fresh dependency identities. Preserve no-candidate versus infeasibility,
nonpassing diagnostics, recorded rejected stages, and changes to dependency roots
*during* a pass: `run` re-resolves accepted output against the current graph after
callbacks, and `get/result` recursively reject stale descendants.

Python may register/execute exploratory proposals and transport data, but a native
manager must validate each candidate and own stage records, acceptance and scope
completion. Callbacks remain local orchestration; no callback import or untrusted
serialized accepted token. Plan an explicit native-backed manager/proxy preserving
existing freshness operations, or a versioned alternative API while keeping the
legacy interface; a one-shot pipeline wrapper does not cover all manager contracts.

Synthetic pipeline dependency inventory (`compiler/synthetic.py:96`) includes
admission policy; semantic/artifact build and realization request identities;
catalog; actual/requested generator configuration; model, checker, synthetic
acceptance and evaluator versions; complete history and horizon; optional
selection result/policy; and the manager's target pin. Its lowering pass freshly
lowers/checks source, records every source link, then its generation pass rebuilds
the bound request, generates the candidate and checks it. A selected candidate
must exactly match regeneration. Native producers alone do not supply those pass
records or completion decisions.

Component pipeline adds registry/lock/composition, adapter/registry-policy/linker/
model and admission pins; exact component source links and observation map;
independent assembly correspondence; fresh generic linking and actual component
behavior. Preserve completion profiles and unresolved `molecular_behavior`:
`synthetic_realization` requires behavior preservation and finite-history response;
`synthetic_components` additionally requires component linkage. Neither closes
`complete_payload` or empirical obligations.

### Canonical package content and fresh publication

Current public signatures:

- `build_synthetic_package(request: SyntheticBuildRequest, *, run_metadata: RunMetadata|None=None) -> SyntheticPackage`.
- `verify_synthetic_package(data: bytes, *, expected_request: SyntheticBuildRequest|None=None, expected_build_fingerprint: str|None=None) -> SyntheticPackage`.
- `publish_synthetic_package(package: SyntheticPackage, output) -> Path`.

Port the full [synthetic build records](../src/biocompiler/artifacts/synthetic_build.py):
`SyntheticHistory(frames)` v0.1; `SyntheticBuildRequest(realization,history,until,
config=default,profile="synthetic_realization",intended_use="software_test")` v0.2;
`SyntheticPackageFile(path,role,sha256,byte_length)` v0.2; and
`SyntheticBuildManifest(request_fingerprint,files,toolchain,package_version,
profile="synthetic_realization",status="complete",scope="synthetic_realization",
intended_use="software_test",human_therapeutic_admission="not_admitted")` v0.2.
Preserve exact history/horizon, source artifact scope, portable source paths,
no host provenance locations/timestamps, exact profile/file inventory, sorted
manifest files/tool pins and manifest/build fingerprint. Run metadata stays outside
canonical build identity; archive bytes still include its supplied representation.

Base package inventory is exactly 11 members: `request.json`, `inputs/history.json`,
`inputs/config.json`, `inputs/catalog.json`, `stages/request.json`,
`stages/behavior.json`, `stages/mechanism.json`, `candidate.json`, `selection.json`,
`checks/realization.json`, `result.json`. Component profile adds exactly four:
`assembly.json`, `stages/components.json`, `checks/composition.json`,
`checks/component-behavior.json`. Preserve the explicit `not_requested` selection
status artifact when constraints/preferences did not request selection.

Native canonical-content ownership includes full requested/selected configuration
identities, stage and payload fingerprints, locks, source links, all checks,
completion/unresolved obligations, exact tool/version pins, and all summary claims.
Package member JSON currently uses sorted keys, indent 2, UTF-8 and a final newline;
this differs from compact identity serialization. Retain byte-for-byte output,
not merely semantically equivalent JSON. Native export must freshly enforce
software-use admission, complete selected scope, independent synthetic PASS and,
for components, independent component behavior PASS.

`verify_synthetic_package` requires independent complete request and/or build
fingerprint, checks packaged/request identities, rechecks admission, rebuilds
with current tools and original metadata, and compares **both full manifest and
complete archive bytes**. `publish_synthetic_package` repeats this verification
before atomic publication. Routing only its inner candidate checker leaves Python
as build/manifest/export authority and does not satisfy R6.

Python may keep bounded ZIP transport, reading and atomic filesystem writes, under
native-bound member inventories and exact manifest/member hashes. Preserve the
shared `archive_container` policy: `biocompiler.reference_archive.v0.4`, 64 MiB
archive, 16 MiB members, 1 MiB reserved metadata, 128 entries, 1024-byte paths,
canonical stored ZIP with fixed metadata and no Zip64. `read_archive` validates
container/inventory/canonical bytes only; it does not grant fresh acceptance.
A native content/check protocol must bind exact bytes written and preserve whole
rebuild comparison. Streaming/resource design from R5 is also prerequisite here;
a 64 MiB archive does not fit the existing direct JSON envelope.

CLI `synthetic-build` requires request/output and accepts run metadata;
`synthetic-verify` takes an archive and exactly one of independent expected request
or expected build; `synthetic-inspect` remains historical integrity inspection.
Preserve status/scope, full archive SHA-256, software-only/no-human-admission and
unresolved molecular behavior summaries. Keep storage operations in Python, but
route every fresh build/verify/publication decision through the selected native
profile with no intermediate Python request constructor/lowering fallback.

## Unsafe shortcuts to reject during implementation

- Passing `core=` only inside `_checker` while Python modifies dependencies,
  enumerates/claims completeness, reduces/claims minimality and authors the record.
- Importing workflow/build request JSON before branching to native; both recursively
  construct `RealizationRequest`, whose current constructor calls Python lowering
  verification. Domain record hydration is not automatically pure.
- Using direct `verify-realization` replay to compare workflow reports: workflow
  settings deliberately differ, and a direct report is not a workflow record.
- Dropping full per-history failures/coverage to fit transport, treating a resource
  exception as ordinary semantic cap exhaustion, or resetting budgets per history.
- Accepting a stored campaign prefix, `one_minimal`, selected result, manifest or
  accepted stage because its self-supplied hash is consistent.
- Forwarding native checks through Python `PassManager` and calling the entire
  pipeline native; its acceptance/freshness/obligation/completion rules remain
  semantic responsibilities.
- Marking archive inspection as verification, trusting a prior build's PASS at
  publication, or checking only candidate identity while member bytes changed.
- Changing unsupported/native-missing operations back to Python behind an explicit
  core selection, or broadening `compile` to an unfinished profile.

## First full-R5 implementation split and proposed module interfaces

These names are proposed for the next batch, not implemented capabilities. Agree
on them before parallel production edits; use existing domain `Runtime_number`,
`Execution_data.Input_frame`, `Realization_evidence.Check_result`,
`Realization_request` and `Synthetic_authority.Candidate` types throughout.

| Owner boundary | Files/responsibilities | Explicit exclusions |
| --- | --- | --- |
| Native domain | New `core/lib/domain/verification_exploration.ml/.mli` and `verification_workflow.ml/.mli`, focused independent codec tests | No checker/producer imports, no imported acceptance token, no Python fallback |
| Native workflow engine | New verifier-safe workflow library; complete check, contact/mixed explore, reduction and replay, native full reports/settings, aggregate budget tests | No mechanism generation or component adaptation, no wire callback injection |
| Public service/routing | Profile/framing choice, core/verifier service dispatch, strict Python workflow client/raw backend/native record view, all four CLI routes, exports, boundaries/CI | No legacy Python request/report import on selected native execution |
| Capture/conformance | Complete original workflow/callback/CLI capture, independent native literals and installed campaigns, exact old-corpus retention | No normalization of changed results, sampled campaigns or golden replacement |

Proposed domain API surface (each record module also has bounded `of_json`,
`to_json` and cached canonical `fingerprint`; constructors preserve original
validation/defaults, not a smaller wire subset):

```ocaml
(* Verification_exploration; abbreviated aliases only for this design sketch. *)
type number = Runtime_number.t
type frame = Execution_data.Input_frame.t
type check = Realization_evidence.Check_result.t
module Observation : sig
  type t
  val make : signal_id:string -> ?field:string -> unit -> t
  val signal_id : t -> string
  val field : t -> string
end
module Bounds : sig
  type kind = Contact | Mixed
  type t
  val make : kind:kind -> contact_ids:string list ->
    observations:Observation.t list -> variable_times:number list -> until:number ->
    ?fixed_suffix:frame list -> ?max_histories:int ->
    ?cell_observations:Observation.t list -> unit -> t
  val kind : t -> kind
  val contact_ids : t -> string list
  val observations : t -> Observation.t list
  val cell_observations : t -> Observation.t list
  val variable_times : t -> number list
  val until : t -> number
  val fixed_suffix : t -> frame list
  val max_histories : t -> int
  val state_count : t -> Z.t
  val possible_histories : t -> Z.t
  (* Schema-dispatch of_json plus exact contact-only and mixed import helpers;
     no extra kind field is added to the historical JSON. *)
end
module Failure_signature : sig
  type t
  (* Complete response/diagnostic variant constructor + original optional IDs. *)
  val from_counterexample : Realization_evidence.Counterexample.t -> t
  val from_diagnostic : Realization_evidence.Check_diagnostic.t -> t
  val matches : t -> check -> bool
end
module Report : sig
  type t
  val make : kind:Bounds.kind -> config:Bounds.t -> results:check list ->
    ?explorer_version:string -> ?claim_scope:string -> unit -> t
  val config : t -> Bounds.t
  val results : t -> check list
  val complete : t -> bool
  val all_passed : t -> bool
  (* All original count/coverage/shared-dependency getters and both schemas. *)
end
module Reduction : sig
  type t
  val make : original_history:frame list -> history:frame list -> until:number ->
    signature:Failure_signature.t -> original_result:check -> result:check ->
    evaluations:int -> one_minimal:bool -> ?reducer_version:string -> unit -> t
  (* Getters for every field; imported one_minimal remains historical. *)
end
```

`Bounds.kind` selects the original schema and invariants; it must not introduce a
new JSON discriminator. Preserve standalone contact-only import rejection of a
mixed schema and mixed report/config pairing. `Report.make` receives the intended
report class explicitly, so a contact report with mixed bounds is rejected rather
than silently promoted to a mixed report. Domain validation of a report's
history prefix/derived fields must use bounded, pure data algorithms. It does not
execute Behavior or a mechanism. The engine charges before each such traversal,
frame expansion, aggregate computation and record construction; domain standalone
imports retain their own explicit structural ceilings. Do not introduce a domain
→ checker dependency merely to obtain `Work_budget`.

```ocaml
(* Verification_workflow. *)
type operation = Check | Explore | Reduce
type mode = Candidate | Model
module Request : sig
  type t
  val make : realization:Realization_request.t ->
    candidate:Synthetic_authority.Candidate.t -> operation:operation ->
    ?mode:mode -> ?history:Execution_data.Input_frame.t list ->
    ?until:Runtime_number.t -> ?bounds:Verification_exploration.Bounds.t ->
    ?signature:Verification_exploration.Failure_signature.t ->
    ?max_evaluations:int -> unit -> t
  (* Exact getters for all nine authority fields, both identities as appropriate;
     fresh source validation belongs to the engine, not structural of_json. *)
end
type result =
  | Checked of Realization_evidence.Check_result.t
  | Explored of Verification_exploration.Report.t
  | Reduced of Verification_exploration.Reduction.t
module Record : sig
  type t
  val make : request:Request.t -> result:result ->
    ?workflow_version:string -> ?claim_scope:string -> unit -> t
  val request : t -> Request.t
  val result : t -> result
end
```

All make/import paths must preserve malformed enum/string/optional-field errors,
not only successful typed construction. Include independently captured raw-import
and constructor recipes so native adapters do not accidentally overwrite omitted
defaults or add computed summary fields to constructor inputs. Engine request
import must preserve historical source-error precedence relative to candidate and
operation validation; structural domain import alone is not fresh source checking.

Proposed engine API is `run[_with_usage] ?limits ?parent Request.t -> Record.t`
and `replay[_with_usage] ?limits ?parent ~expected_request:Request.t Record.t ->
Record.t`, with raw service request import/source checks sharing the same parent.
`limits` includes the complete agreed workflow resource profile, separate from
request `max_histories`/`max_evaluations`; usage reports total work, retained peak
and request/report inventories. `run` handles **all three operations** and both
modes. A private/test functor may inject evaluator responses only for original
callback-corruption tests; the production instance is fixed to current native
independent checkers. No public protocol or retained record can select that seam.

Keep record/view versus exact historical Python return-type compatibility and
large-artifact framing as explicit public-contract decisions in the service work.
The native domain/engine batch can proceed while those are designed, but full R5
routing cannot be declared finished before they are resolved and tested.

## Implementation checkpoints and evidence required

- [ ] **W1 original boundary capture:** extend the complete inherited 373-method /
  381-context cohort without dropping any of its 4,119 direct calls or 2,112 direct
  replays. Capture all newly reached workflow/config/signature/report constructor,
  import, property and public operation calls; complete callback trials; original
  exceptions; all CLI subprocesses; producer/pipeline/archive observations.
  Preserve old source coordinates, call parentage and original assertions. New
  callback-mutant replay seams must reproduce bad callbacks, not trust captured
  aggregate outputs. These new counts must be measured, not inferred from the
  direct-call campaign.
- [ ] **W2 native full workflow:** complete domain records, both check modes,
  deterministic contact/mixed enumeration, selected-failure reduction, exact
  records/replay and aggregate bounds. Add original literals plus malformed,
  ordering, Unicode, numeric, cap/work-exhaustion, stale-policy and changed-source
  cases. Keep adversarial proposal API explicitly separate.
- [ ] **W3 public workflow contract:** settle large-report framing and SDK return/
  hydration compatibility; pin capabilities, inputs, resource scopes and all
  report encodings; expose both roles without producer imports; strict client and
  raw-document backend; all four CLI commands and atomic-output behavior.
- [ ] **P1 direct producers:** expose existing generator/selector/adapter modules
  only in the producer role; preserve complete configs/alternatives/rejections and
  all existing public caller behavior. This does not finish the pipeline.
- [ ] **P2 checked manager/pipelines:** native deterministic pass records, source
  checks, component admission, provider/ancestor freshness, changed-root handling,
  discharges and completion; preserve public manager semantics and full synthetic/
  component output records.
- [ ] **P3 package authority/export:** complete build/history/manifest codecs,
  native exact member content, current tool/admission/whole-scope checks, complete
  independent archive rebuild, byte-for-byte comparison and atomic publication.
- [ ] **G current-revision integration:** fresh native suites Linux/macOS, strict
  installed core/verifier protocol and execution-guard campaigns on Python 3.11 /
  3.14, complete retained CLI examples/subprocesses, all five original unit shards
  per version, package/reproducibility/browser gates and fail-closed aggregate
  accounting. Record tested source and integrated tree; check off R5/R6 and related
  LM items only when their corresponding evidence is complete.

Primary regression modules are `test_verification_exploration.py` (including its
adversarial and reduction classes), `test_synthetic_verification_workflow.py`,
`test_synthetic_design_workflows.py`, `test_synthetic_selection.py`,
`test_synthetic_build.py`, `test_build_archive.py`, `test_checked_pipeline.py`,
`test_component_pipeline.py`, `test_component_pipeline_audit.py`,
`test_component_pipeline_manager.py`, `test_pipeline.py`, existing admission/
independence tests and all inherited conformance suites. Do not replace them with
new convenience fixtures. Original callback mutation tests must still demonstrate
rejection; original CLI tests must still retain full nonpassing reports and exact
exit/output behavior under native selection.

## Source identity for this audit

The following hashes identify the Python authority reviewed; line references above
are navigational and must be refreshed if these files change before implementation.

| Source under `src/biocompiler/` | SHA-256 |
| --- | --- |
| `compiler/verification_workflow.py` | `04d9818933ae3ded190d4139023340f88c1eb7d8f2325173c4c77c056f7b7dd6` |
| `verification/exploration.py` | `a4b85d8b0f48198128bc9064fa065eddc8c5f6acb4d68d92a21008c79723ca98` |
| `compiler/synthetic.py` | `9ecf345ff5ea4da687b6344342862c68cd116296e01308f8d4c76d05dc091ff2` |
| `compiler/components.py` | `dc9edc3cb5fee5aef128a5a096ff6c20bfbf2af97f1077b74851a505d4b5d034` |
| `compiler/synthetic_build.py` | `8ba430132fc1e8dd6158005cc5e3bc810fe36a5efd8225e289276562abf653c4` |
| `compiler/pipeline.py` | `2b1dea35ac3c861f1e933cf7808a241f1f6596e59cc04ceb0ec32e4a54d27331` |
| `compiler/passes.py` | `97250c61b3207a093e0a0d87244724ae078bce6b6257fd1b7049661a91ceafbf` |
| `compiler/request.py` | `6b87777cfad4a06fe485e6fb4d29bdd02312f99df5193ea0d3351a57e1065caf` |
| `artifacts/synthetic_build.py` | `ef7486053bcff2cae082c400fef1860d3a013bbcb375416eb41fd22518db3e19` |
| `artifacts/archive.py` | `3b1d7b8b9881fe0f45d3e25649d761390e037e05c0cbeb3aefbdefe0164a647d` |
| `artifacts/archive_container.py` | `36d598102ffea532b67a3a116266f573ccff07da39166230023d162fd675d43f` |
| `synthesis/selection.py` | `6337ec4e394e0f684344d29b97bc0a411fb2aa4917d53d48e8082566397bae60` |
| `synthesis/components.py` | `ae548945c03b8dca75208abec47fee2e62bc03cceb7958ed645905813e5f2cb0` |
| `synthesis/synthetic.py` | `94b9ff83b411d734ccd18c1ae7191d684be204151ebfc7141be8bfbfb35bdd4b` |
| `cli.py` | `eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0` |
| `compiler/workflow.py` | `90cbe26057ba348c620403415e2c12209e76f4966d1d7b8e90744e0ef619c40e` |
