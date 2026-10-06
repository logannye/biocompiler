# Development cadence and validation

This protocol reduces feedback time while preserving the compiler's existing
validation coverage and independent checks. The release workflow remains
[Python checks](../.github/workflows/ci.yml). Development feedback has a separate
[opt-in hosted workflow](../.github/workflows/policy-development.yml), triggered
only by pushes to `codex/dev-policy/**`. It builds the native core once on Linux
and runs sixteen fixed component, protocol, preservation, material and construction suites.
The same build then runs the Python SDK witness for both component policies:
an independently authored, domain-only source fixture is exported by a private
test tool, the public DSL reconstructs the originals, and Core/Verify perform
compile/check/replay and fresh exact paired export. Neither the source fixture
nor the development receipt grants release acceptance. Core, Verify and the
private test tool are pinned immediately after the build and rechecked across
both stages; the private tool is absent from installed package entrypoints.
Its first nine-suite run at `a89f80b07` completed successfully in 2 minutes
41 seconds, including 43 seconds of dependency installation, 30 seconds of
compilation and 35 seconds of tests. This is one observed run, not a runtime
guarantee. Full release acceptance still requires every existing gate.

Development reports explicitly contain `acceptance: false`. They retain exact
source/run identities, fixture and executable hashes, command logs and failed
suite outcomes. Missing targets or changed inputs fail the job. This workflow
does not package releases or cancel a release workflow. Native work remains
hosted. Batch tracker updates at useful implementation and validation boundaries
while independent development continues during full release validation.

## Work in coherent batches

All run steps explicitly select Bash so a failed checker piped into `tee`
fails its step. GitHub's unspecified non-Windows shell does not provide that
same pipeline guarantee; see the [official shell behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#defaultsrun).
The native build, native suites, conformance commands, architecture SDK routes,
and installed campaigns have separate jobs. Candidate wheels are available after
compilation and material checks; they do not wait for the long test campaigns.
The final release and merge gates still require every original check. Job timeouts
are failure bounds, not measured performance claims.

Commit useful local checkpoints freely. Push a coherent batch when it is ready
for review and remote validation, rather than pushing every small edit solely
to obtain another CI run. Run appropriate focused checks while editing. A green
cohesive feature can merge without waiting for unrelated work in a longer sprint.
Preserve an active PR and its running checks while independent work continues;
change its tested revision when a correction is needed, not to manufacture
activity or restart a healthy run.

The exact revision being integrated must have passed the required checks.
Record both the source revision and the tested checkout revision when PR merge
checkouts differ, along with Python version, platform and workflow run identity.
Do not transfer a previous revision's PASS to new code. A successful early
artifact comparison is useful evidence but does not complete the remaining
unit, integration or browser gates.

## Triggers and parallel jobs

Validate PR updates, pushes to `main`, and explicit manual dispatches. Ordinary
feature-branch pushes do not also launch a duplicate full push workflow alongside
the PR run. Manual dispatch is available for a deliberate validation need; it
is not an automatic second run of each PR update. A newer run for the same PR
cancels obsolete PR work. Main pushes and manual runs have unique concurrency
groups, so neither cancels another needed run. Main integration and PR checks
remain distinct revision boundaries.

| Job | Coverage and dependency |
| --- | --- |
| `ci-preflight` | Both Python versions run pure scheduling/receipt, native fixture wiring, installed reference-source closure, outside-checkout authoring and bounded failure-diagnostic regressions, then restore the complete reference and workflow source authorities and load all 17 frozen campaign corpora with child processes and network forbidden. It detects source, schema and path-plan failures before expensive jobs. |
| `unit-plan` | Python 3.11 and 3.14 independently discover the full suite and produce five-shard plans. |
| `unit-tests` | Ten jobs: each Python version executes shards 0–4 against its plan, with at most ten running unit jobs. |
| `unit-accounting` | One per Python version independently verifies its complete five-result census against fresh discovery. |
| `installed-executable` | Both Python versions run the installed executable RNA API/CLI path outside the checkout. |
| `installed-architecture` | Both Python versions run all 13 installed architecture cases and complete API/CLI/FASTA/manifest checks outside the checkout, followed by complete expressive-policy authoring and real installed-console checks with separately retained receipts. |
| `circuit-integration` | Both Python versions exercise source metadata, infrastructure, review bundles, construction, molecules, intent and human circuit profiles. |
| `integration-examples` | Both Python versions retain all remaining audit, molecular, synthetic, human, authoring and CLI examples. |
| `studio-browser` | Installed Python 3.11 package, Node 22 and the pinned Playwright/Chromium setup run guided workspace, construction inspection and review suites. |
| `studio-typescript` | Pinned strict TypeScript checks, unchanged generated release assets, runtime response decoding and current migration inventory. |
| `ocaml-build` | Build once per native platform, check library boundaries, generated policy schema/operational/material fixtures, rule coverage and both strict transport/policy type gates. Retain locked inputs and exact compiled suite/role/fixture bytes, assemble candidate platform wheels and stamp their policy source authority. No test result is inferred from building a wheel. |
| `ocaml-native-tests` | Restore the current run/platform-bound bundle, run the 22 focused policy/producer/construction checks with separately retained diagnostics, then all 156 Dune-declared suites with their original arguments and two bounded workers. The bundle binds 158 executable entries and 23 original JSON fixtures; 38 suites have explicit ordered fixture dependencies. The component suites retain the original A/B model fixtures. Assembly-rule and assembly-check tests share independently authored literals through a domain-only test library outside both production executable closures; expected material is declared without the construction producer. These leaf checks do not establish full composition acceptance. Unsupported Dune declarations fail closed; no compilation occurs in consumers. |
| `ocaml-core` | Two workers execute all 67 original direct corpus, protocol, resource-bound and Python/OCaml conformance command groups against the same restored binaries. Commands within each group keep their original order and output paths; complete current-run group/log accounting is required before success. |
| `architecture-sdk` | Four platform/Python jobs run concurrently. Each checks installed policy source assessment, operational execution, implementation preservation, material compilation/fresh export and Verify-only offline consumption against original fixtures and exact restored Core/Verify binaries. The selected interpreter's real console runs outside the checkout; policy reports and logs remain distinct. It then uses two isolated Python workers for all 16 architecture scenarios. Case B retains all its rejection/publication controls. The coordinator applies the unchanged independent 175-check/219-artifact architecture census before reporting success. |
| `executable-rna-reproducibility` | Depends only on `installed-executable`; compares complete relative-file SHA-256 inventories from both Python versions. |
| `payload-architecture-reproducibility` | Depends only on `installed-architecture`; requires all 13 case outputs and compares every relative file across versions. |
| `circuit-reproducibility` | Depends only on `circuit-integration`; compares the complete infrastructure/source/review artifact inventories. |
| `architecture-core-reproducibility` | Depends on both native builds and all four architecture SDK jobs; rehashes complete SDK/CLI artifacts from Python 3.11 and 3.14 on each platform and requires exact four-way equality with current run and executable authority. Five separate policy comparators require complete source, operational, implementation, material and offline-consumer receipts against original fixtures and published binary manifests/bytes. The consumer comparison also binds each original material producer receipt. All six comparison receipts are retained. |
| `installed-campaigns` | Both platforms × Python 3.11/3.14 × five complete campaign groups (20 jobs, at most 20 concurrent). Each group installs the exact same SDK/native wheels outside the checkout and performs the complete smoke/uninstall/missing-package/reinstall lifecycle. Protocol runs alone. Manager, fixed, workflow and synthetic groups may overlap two complete campaigns after the serial install lifecycle; receipts retain the original recipe order. Fixed/reference, workflow and synthetic groups retain their original membership. All groups retain every original case, artifact and independent checker; no stateful scenario is split. |
| `realization-conformance` | Four independent aggregation jobs require all five group receipts and all 17 campaigns exactly once per runtime. Recheck current source/run/candidate identities, complete owned bytes, original command recipes, separate lifecycle logs, campaign logs and artifact hashes. Native input receipts bind the installed files for unchanged cross-runtime checkers. |
| `realization-core-reproducibility` | Rehash complete realization protocol, workflow and producer SDK reports, verify every original applicable occurrence and all additional cases, require current run/source/binary authority and exact equality across all four campaigns. Private producer calls and injected-proposal cases remain explicitly classified as native-library coverage. |
| `prebuilt-core-assembly` | Depends only on both native builds, allowing installation tests to start while other tests run. Independently checks complete platform wheels, original linked sources/notices/relink companions and final executable identities; builds and checks one pure SDK wheel containing both platform pins. |
| `prebuilt-core-validation` | Requires all four fresh-install/lifecycle/campaign receipts, exact owned bytes, original command recipes and successful upstream assembly, all native suites/conformance, architecture SDK checks, and cross-runtime reconstruction. |
| `policy-prebuilt-sdk` | Depends on both native builds; independently checks complete supplied native wheels and source companions, builds a pure SDK with exact platform pins, and retains the policy artifact-source stamp and release candidate. |
| `policy-prebuilt-installed` | Four platform/Python slots install those exact SDK/native wheels outside the checkout and run complete material/fresh export and Verify-only offline-consumer campaigns, retaining owned bytes, command receipts, evidence and failure logs. |
| `policy-prebuilt-reproducibility` | Requires the policy SDK and all four installed slots; independently rechecks original fixture authority, wheel/material ownership, release identities and complete material/consumer results across every slot. |
| `validation` | Final gate requires all 74 jobs, including successful unit accounting, every installed/integration/browser job, TypeScript, both native platforms, all six reproducibility jobs and both existing prebuilt gates plus all three policy-prebuilt jobs. |

Unit shards and accounting select the exact CPython patch version recorded in
their same-run plan before installing the package. An isolated standard-library
bootstrap validates the bounded plan, fingerprint, checkout and requested minor
version before returning the exact interpreter version to `setup-python`.
Discovery, execution and accounting still require identical full environments;
a hosted Python patch rollout cannot justify relaxing that requirement. Failed
selection has no fallback interpreter and cannot supply successful accounting.

The workflow selects CPython 3.11.15 and 3.14.6 through one explicit mapping,
matching the two frozen archive standard-library source profiles. Matrix labels
and receipt identities remain `3.11` and `3.14`. Every hosted Python consumer,
including the three inline artifact comparisons and both reference-replay
interpreters, uses that mapping; shards and accounting retain their checked-plan
selection. The runner's Python is used only for the isolated plan-selector
bootstrap before setup. Patch upgrades require explicit source-profile review,
not replacement of frozen authority records. Preflight runs the original archive
authority tests and migration inventory check before the larger campaigns.

Original-only fixed build and continuation replays restore the historical
package entrypoints alongside their archived session checker. The private
counterpart v2 manifest retains the independently pinned current-to-original
source proof, checked in both parent and child. Other counterpart tasks retain
their current package entrypoints. A separate exact predecessor proof preserves
the earlier capture and continuation witnesses without rewriting their corpora.

The union of PR85 `ae2db34b31efd8d914622630721768b14f0eacd6` and PR95
`bb84421cf1f93cd1dc02813d80a2c54a3520a919` rederives the census from the
combined workflow: 27 job definitions expand to 74 executions. There are
59 ordinary revision-bound job receipts, two unit plans, ten unit shard results,
two independent unit-accounting results and the final aggregate execution.
Policy source-through-material campaigns join the four existing SDK slots;
the three added policy-prebuilt definitions contribute six executions. All
67 direct command groups and 20 installed campaign jobs remain required.
Historical 68-job PR85 and 42-job PR95 runs do not establish acceptance of this
union. Its exact tested revision, subsequent normal merge and actual-main
revision require their own complete acceptance evidence.

All expensive producers wait for the short preflight, then independent work
runs concurrently. The critical path is preflight → candidate build/assembly →
parallel native/SDK/installed work → independent comparisons → final gate.
Actual overlap depends on the hosted concurrency allowance; adding jobs is not
itself a promise of faster execution. Installed groups are capped at 20 jobs,
native suites, direct-core command groups and architecture scenarios at two workers per runner. The matrix
lists all four fixed groups and then all four protocol groups first to request
earlier continuation feedback; runner availability still governs start order. Campaign and
scenario timings and streamed start/completion messages identify remaining slow
work. Rebalance only from measured timings, preserving every stateful sequence.

Synthetic inspection uses two isolated Python processes over disjoint original
occurrence ordinals. It retains all 9,668 rows: 9,658 public helper observations,
two explicit native wire rejections and eight Verify-role rejections. Each case
keeps its capability and operation order. The parent restores the original row
order and rechecks complete raw worker receipts, source pins, logs and artifacts;
serial diagnostic execution cannot satisfy the installed parallel acceptance gate.

Inside each installed protocol and routing campaign, two isolated Python
processes execute the complete core and verify roles. The original per-role
native calls, replay and rejection order remain intact. The coordinator requires
all 13,438 protocol checks and 8,314 routing checks and applies the independent
semantic checker before publishing the combined artifacts. Worker source pins,
raw receipts and complete logs accompany the aggregate.

Before fixed-continuation native execution, each fresh parent reference capture
runs concurrently with its existing isolated original-source counterpart child.
The parent stays on its owning thread; a separate thread only drains the child
pipes. Both complete captures and the unchanged full correspondence proof must
pass before any native work starts. Parent failure kills and drains the child;
child failure or the unchanged 90/600-second timeout prevents publication. No
capture, original assertion, retained object or independent replay is removed.

Fixed-continuation execution partitions only at the four original test-class
boundaries, with at most two worker processes. Each class retains its fixture,
method order and stateful manager sequences. Fresh grouped original-Python
observations must equal the full serial original baseline before native execution;
all 39 native call occurrences are then reconstructed and checked in their original
order. Equal serialized inputs do not replace per-occurrence physical-identity
observations. These concurrency bounds change scheduling, not scientific scope
or migration admission. Manager, fixed, workflow and synthetic groups also use
up to two campaign processes, each retaining its existing internal worker allowance, so the total
process count per runner can exceed two. The six direct continuation controls
run before the 39 native chains to expose short failures earlier; all remain
required for success. The fixed group prioritizes registration alongside provider
checks to expose installed-source comparison failures earlier. Submission order
is recorded separately from the unchanged recipe and receipt order; this priority
is not a dependency barrier between otherwise independent campaigns.
Registration rejection checks bind the final native inspection and its original
record order separately from SDK cache insertion order. They still require every
original cached record object and reject added, missing or replaced records.

Reference reproducibility prepares all four runtime slots and their complete
source, binary and artifact authority before launching up to four independent
reconstruction subprocesses. Each has a finite 10,800-second timeout, matching
the complete installed campaign allowance, with the same diagnostic bound and
unique output. Measured hosted reconstructions exceeded the former 1,800-second
limit; shorter transport deadlines remain unchanged. All started workers finish or fail before
the parent validates reports in the original platform/Python order and requires
complete cross-runtime equality. Instrumentation and transcript peers remain
inside each worker process; the four-slot limit is not a total process limit.

The reference observer filters irrelevant function names before resolving
source paths. Every eligible registration or callback still resolves its
current path and checks the same live function identity. This removes repeated
filesystem work from tracing without caching source authority or changing
the observation census. End-to-end timing remains a hosted measurement.
Flushed phase markers and elapsed times identify long-running reference phases.
The campaign does not arm an asynchronous frame-dump watchdog: Python 3.11 can
corrupt the dump or hang while trace/profile callbacks inspect active frames.
Diagnostic output remains separate from observation documents and receipt schemas.

Reference execution receipts retain every observed Python call count. Their
cross-execution comparison accounts separately for five source-verified I/O
call sites whose counts depend on readiness polling or frame chunking. The
receipt binds each such occurrence to its actual caller, callee and instruction
site, checks its count against the complete raw census, and compares all
remaining call counts exactly. Complete protocol traffic, object graphs, source
permissions, callbacks and public-route evidence remain required. Whole helper
functions are not exempted from comparison: calls from other sites retain their
exact counts. Both Python versions run finite scheduling and tampering controls
before native builds.

If the guarded-execution comparison differs, the campaign retains both guard
documents and the replay's source evidence before its temporary directory closes. A bounded
diagnostic identifies the first unequal field; diagnostic storage or output
errors preserve the original rejection. Retained failure data cannot satisfy
the successful reconstruction gate.

Historical manager views preserve the original attribute insertion order for
all five closed dataclass types without rerunning Python constructors or semantic
checks. The two fixed reference registrations retain the original shared
`PassContract.targets` default after checking its actual source and object
identity; generic view decoding retains separate tuples. Native sequence-range
documents likewise preserve the original public mapping order. The complete raw graph comparison still rejects order changes;
canonical JSON equality alone cannot establish this public object correspondence.

The short authoring, per-occurrence source identity, exact source-restoration
and diagnostics controls run in both preflight slots and remain in full unit
discovery and accounting. Equal serialized requests can have different physical
object identities after a JSON roundtrip, so continuation graphs are bound to
each original call occurrence. They are not repeated in
`unit-plan`; native builds depend on `ci-preflight` directly. The diagnostic
controls use harmless Python children. Full original reference-contract, workflow
and workflow-CLI source restoration runs before native compilation, including
every additive transport witness; changing a source hash without its exact
restoration proof fails this early gate. Synthetic inspection also checks every
case input shape and both frozen wire-rejection obligations before native work.
Those two occurrences retain their original Python observations and require exact
native JSON rejection; they do not claim native helper equivalence. The callback
malformed-frame regression also runs in preflight. Its inert peer co-publishes the
last response fragment and unsolicited suffix, preserving every byte and original
assertion while removing a scheduling race. A separate FIFO-synchronized control
requires genuinely later output to invalidate the next call or close before any
new frame is sent; production transport timing and bounds remain unchanged.
Persistent pipeline sessions likewise drain stdout after process exit before
declaring an incomplete response. Real-pipe regressions require buffered
responses to survive that readiness race while preserving EOF rejection,
frame and aggregate limits, deadlines, cancellation and nonzero exit failure.
The complete source-restoration checks include the two fixed-reference
target additions and preserve the preceding whole-source witness unchanged.
Preflight also loads every closed reference helper through both package and
script entry paths, including the attempt lifecycle validator used after native
execution. The same complete validation functions and manager bindings apply in
both modes, so import failures are caught before the long installed campaign.
Corpus loading
separately denies child processes and network. Failed or timed-out installed commands print a
bounded, escaped tail of their complete retained log. Successful commands
print only the scheduler group/timing envelope. Every opened group closes
on failure as well as success; retained logs remain the diagnostic authority.

The final gate runs even when a dependency fails. Missing, cancelled, skipped,
stale, duplicated, wrong-runtime or failed work cannot become a successful
census. The registry includes 59 ordinary job receipts, ten unit shards, two
unit plans, two unit accounting jobs and the final gate: 74 concrete jobs.
The source-only scheduling controls and artifact fixtures are safe to run
locally; native execution and actual packaging remain hosted-only.

This restructuring has no measured speedup claim until its exact revision passes
hosted validation. Compare full wall time, critical-path steps, runner queue time,
and aggregate runner minutes with the recorded pre-change run. Candidate build
caching or passing receipts from another revision cannot replace current tests.

Rerunning failed jobs may preserve a successful receipt from an earlier attempt
of the same GitHub run and revision. The final gate also requires GitHub's actual
prerequisite result to be successful; an old receipt cannot excuse a failed,
cancelled, skipped or missing job. Uploads replace the same run's artifact names
on retry, and reports from another run or revision cannot satisfy the gate.

## Exact unit-test accounting

[test_shards.py](../tools/test_shards.py) uses real `unittest` discovery. The plan
records the exact sorted test IDs and their fingerprint, discovery configuration,
recorded source hashes, Git revision and full Python version. Import/discovery
errors and duplicate test identities fail planning. There is no maintained
allowlist that could silently omit a newly added test module or case.

The deterministic longest-processing-time assignment keeps each complete
`TestCase` class in one shard, preserving class fixtures. Timing estimates from
[test_shard_weights.json](../tools/test_shard_weights.json) affect placement only;
they cannot exclude tests or substitute for execution. Every discovered class
is assigned exactly once across the five shards for its Python version.

Pure source discovery of the current union on Python 3.14.6 finds 4,039 tests
in 428 classes. This is an inventory result, not test execution or hosted
acceptance. Both hosted Python versions must independently rediscover and
account for the complete current suite. Existing capture scheduling, callback,
reference, source lineage and reconstruction controls remain alongside the
added policy controls. Placement weights retain the historical fixture-inclusive
maximum for every previously measured class. Fresh discovery assigns the
existing two-second fallback to unmeasured methods and classes; the weights file
records its historical measurement and earlier inventory reconciliation.
These estimates guide placement and do not establish a runtime bound.

Each runner rediscovers the suite and verifies the plan before executing its
assigned tests. Results retain test/subtest outcomes, durations, class totals
and failures. Explicitly recorded per-test skips and expected failures retain
their normal `unittest` success semantics; unexpected success, error or failure
is unsuccessful. Unaccounted fixture or subtest skips fail closed rather than
silently removing planned tests from the census.
The accounting job rediscovers again and checks exact membership and execution:
every planned test must finish once in the correct shard, with no missing or
extra IDs, duplicate results, stale revision/source/Python identity or missing
shard report. Interrupted work cannot produce a successful census. A missing
report after a hard kill is a failure, not an empty successful shard.

The same protocol can be reproduced in an environment with the package already
installed. The following commands illustrate one shard; aggregation requires
all five result files from the same plan and Python environment:

```sh
python tools/test_shards.py plan --start-directory tests --shards 5 --output generated/unit-plan.json
python tools/test_shards.py run --plan generated/unit-plan.json --shard 0 --output generated/shard-0.json
python tools/test_shards.py verify --plan generated/unit-plan.json --result generated/shard-0.json --result generated/shard-1.json --result generated/shard-2.json --result generated/shard-3.json --result generated/shard-4.json --output generated/unit-accounting.json
```

## Preserve every existing integration check

Moving a command to another job must retain its expected exit status, retained
authority, CLI inspections, independent replay, sequence comparisons and artifact
upload. The partition of the previous serial package job is:

| Destination | Existing work retained |
| --- | --- |
| `installed-executable` | `executable_payload.py`; installed `payload-build`, `payload-verify`, `payload-fasta`, `inspect`; exact API/CLI build and FASTA equality. |
| `installed-architecture` | `check_payload_architecture_install.py`: A–F, automatic timing, automatic B/F and four functional-control cases; request roundtrips, API/CLI build, verify, export and inspect; complete paired exports and stale-authority rejection. |
| `circuit-integration` | `circuit_sources.py` and source check/verify/readiness; `circuit_infrastructure.py` and binding/evidence checks and replay, inspection and diff; `circuit_review.py` and review create/inspect/verify with exact bundle/result equality. |
| `circuit-integration` | `circuit_construction.py` and build/verify/export/reverify/inspect with API/CLI/export equality; `circuit_molecules.py` and structured inspections; `circuit_intent.py` and check/verify/inspect; `circuit_profile.py` and check/verify/inspect. |
| `integration-examples` | Benchmark audit integrity; reviewed material reconciliation; `intent_programs.py`; `behavior_trace.py`; CLI version/architecture inspection; compiler/context/evidence scaffold imports. |
| `integration-examples` | `intent_candidate.py` and build/verify/FASTA; `molecular_implementation.py` and analyze/build/verify/FASTA/inspect, including strict-build rejection; `component_linking.py`; `molecular_design.py` and portable build/inspect/verify plus handoff and failure inspections. |
| `integration-examples` | `reference_construct.py`, `reference_sequences.py`, `reference_build.py` and reference build/inspect/verify; `molecular_contract.py`, `payload_readiness.py` and molecular result inspection. |
| `integration-examples` | `realization_check.py`, `checked_pipeline.py`, `temporal_pipeline.py`, `synthetic_build.py` and portable build/inspect/verify. |
| `integration-examples` | `synthetic_selection.py`, `synthetic_design.py` and select/build/inspect/verify/explore/replay; `synthetic_verification.py` and check, expected wrong-reset failure, reduce/replay/inspect; `verification_campaign.py` and report inspection. |
| `integration-examples` | `human_target.py`; `human_behavior.py`; `human_deployment.py`; `human_acceptance.py`; `human_admission.py`; `human_profile_cases.py` generation and re-verification, retaining every existing positive, failure, unknown and unsupported inspection. |
| `studio-browser` | `studio.cjs`; independent infrastructure/source fixture generation; `construction.cjs` inspection and review suites; screenshots and diagnostic evidence. |

Every Python producer installs the package and records revision/platform context.
The benchmark audit itself is standard-library-only; material reconciliation
imports `biocompiler` and therefore follows installation. Reference examples
retain access to checkout-relative `data/references/fap_car` authority.

Installed checks use a non-editable package installation and do not set
`PYTHONPATH=src`. Outside-checkout commands retain absolute example/tool paths
and temporary working directories. The architecture installed checker imports
the package before exposing the repository's example modules and asserts that
neither the imported package nor its working directory comes from the checkout.
Browser servers likewise launch the installed package from fresh temporary
directories. Unit discovery keeps access to repository examples and sibling
test helpers without redirecting the package import to `src`.

Artifact producers remain unambiguous; existing names keep their Python suffix:

| Producer | Artifact name prefixes |
| --- | --- |
| `installed-executable` | `executable-rna-payload-py` |
| `installed-architecture` | `payload-architecture-py` |
| `circuit-integration` | `circuit-infrastructure-evidence-py`, `circuit-construction-evidence-py`, `circuit-molecule-declarations-py`, `circuit-intent-evidence-py`, `circuit-profile-evidence-py` |
| `integration-examples` | `intent-candidate-evidence-py`, `molecular-implementation-evidence-py`, `synthetic-workflow-python-`, `synthetic-design-python-`, `molecular-design-python-`, `verification-evidence-python-`, `molecular-readiness-python-`, `reference-build-failure-python-`, `human-behavior-evidence-python-`, `deployment-evidence-python-`, `human-acceptance-evidence-python-`, `human-admission-evidence-python-`, `human-profile-cases-python-` |
| `studio-browser` | `studio-browser-evidence` |

Reference failure evidence retains its failure-only policy. Other existing
retention and failure-upload conditions remain in the workflow. Unit plans,
results and accounting reports add execution evidence; they do not replace any
existing construction, reproducibility or browser artifact. Download consumers
must require the exact expected producer artifacts instead of silently comparing
two empty directories.

## Measure before optimizing

Keep per-test and per-class execution timings, job/step elapsed times, queue
delays and the workflow's end-to-end wall time separate. Inspect the longest
class and shard, not just summed CPU time. Whole-class sharding means one large
class can still determine the critical path. Update timing weights from measured
compatible runs, and record the revision/platform of those measurements.
Include class/module fixture setup and teardown when estimating class costs;
test-method durations alone can understate them. Compare recorded method totals
with shard elapsed time before reseeding estimates from a new report.

Measure three user-visible intervals separately: push to the first actionable
failure, push to complete PR acceptance, and merge to complete main acceptance.
Also record the time spent preparing and reviewing a coherent source update.
For each hosted comparison retain source/tested revisions, event and attempt,
Python/platform identities, job readiness/start/end times and aggregate runner
minutes. Time after prerequisite completion is an observed scheduling delay;
do not attribute it to runner capacity without further evidence. A completed
campaign inside a failed run can inform placement estimates but does not prove
release acceptance or an overall speedup.

Recalibrate the five unit shards when measured balance drifts or substantial
new classes are added. Use fixture-inclusive class totals from all five successful
shards for both Python versions, bound to their exact accounting reports. Take
the larger measured class total across the two runtimes for shared hints.
Reconcile against fresh discovery: identify new or changed classes and their
fallback estimates, retain every ID and keep each class whole. Record the
measurement run, revisions, versions and result hashes in the hints. Placement
estimates never replace test execution. Recheck actual longest-shard time after
the next complete run; a forecast is not an achieved reduction.

Use focused profiling to identify repeated construction, serialization,
verification or fixture setup. Prefer a measured optimization with unchanged
assertions to more retries or a larger runner count. Preserve failure diagnostics
and fresh independent checks while removing avoidable repeated work. Assess the
10–20 minute target from completed runs rather than extrapolating from the first
few green jobs; report any bottleneck that keeps the target out of reach.

Immutable source programs, supplied component contracts, literal sequence parts
and frozen fixture inputs may be reused within an appropriate scope. Tests that
mutate authority must obtain independent copies or immutable replacements. A
cache key must include the complete inputs that affect its contents. Do not
cache an assertion, checker PASS, admission decision or stale verification
receipt as a substitute for running the behavior under test. In particular,
reusing a fixture must not bypass the compiler or checker whose fresh execution
the test intends to exercise. Cross-run artifact reuse is historical input, not
current validation evidence.

## Keep native builds hosted

Editing, formatting, documentation checks and suitable focused pure-Python tests
can remain local. Native compilation, executable native tests, extension rebuilds
and packaging that could trigger native builds run on hosted CI or an already
authorized remote environment by default. Local Rust and OCaml compilation remain opt-in,
including implicit builds through package managers. Do not install or rebuild a
native package just to run a lightweight static check.

Compatible already-installed native libraries can support Python-only edits;
they cannot validate changed native source. Preserve required validation gates and
record their tested revision/platform. If remote execution is unavailable,
continue safe local work and report what remains unvalidated rather than silently
falling back to native compilation. Keep disposable build/download artifacts
bounded and clean only identified task-owned outputs, preserving useful failure
records and user data.

The initial OCaml foundation pins the setup action and opam repository commit,
then records the complete solved dependency lock per platform. CI retains both
executable digests, platform identity and conformance evidence. The
[official runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
select `ubuntu-24.04` for Linux x86_64 and `macos-14` for macOS arm64; each job
asserts the actual system/architecture before building. These are experimental
native validation targets, not a claim that release packaging is complete.

Realization campaigns preserve all original calls, including expected errors and
repeated authorities; content-addressed storage may share equal report files but
cannot remove execution observations. Complete reports and error records accompany
each receipt. Artifact paths must be safe downloaded siblings, and every byte is
rehashed before comparison. Both binaries are downloaded from the same workflow
revision and checked against their native platform manifest; the separate campaigns
do not rebuild them. macOS installs only the GMP runtime if the runner lacks it.
Their 180-minute job limit accommodates the complete initial campaign and does not
establish a measured runtime target. Failed or incomplete campaigns cannot pass the
aggregate gate. Historical 31-job and 36-job receipts retain only their original
revision's scope; the current union requires the complete 74-job census above.

## Bounded policy source-to-material additive gates

The policy increment registers native admission/correspondence, execution,
implementation preservation, material construction, context and service suites
in the complete Dune census and boundary registry. Fixture freshness covers the
operational, lifecycle, compound, domain, closure, simultaneous timing and
state-dependent paths; the material rule coverage inventory remains a separate
source gate. Strict typing checks the union of all 32 core transport files and
the unchanged policy typing scope.

The existing four architecture SDK slots execute every source, operational,
implementation, material and offline-consumer campaign outside the checkout.
Each retains original fixture authority, explicit native role paths, actual
binary digests and the selected Python console. The independent comparator
requires all four complete reports for each layer and full result equality.
The offline consumer has only Verify and requires network isolation; it remains
bound to the original material producer receipt. Independent implementation,
material and consumer diagnostics may continue after an earlier failure once
the native bundle and installed runtime are ready, but a failed step still
prevents the successful whole-job receipt.

The separate four-slot policy-prebuilt campaign checks actual wheel ownership,
material source closure, fresh export and offline consumption under current
release identities. Source-only or mock-peer results cannot satisfy hosted
gates. All previous native corpora, direct command groups, installed campaigns
and release obligations remain required. Static union checks do not close
hosted, merge or actual-main acceptance.
