# Development cadence and validation

This protocol reduces feedback time while preserving the compiler's existing
validation coverage and independent checks. The governing workflow is
[Python checks](../.github/workflows/ci.yml). The target is a measured **10–20
minute hosted validation cycle**, subject to runner availability, current test
cost and the slowest remaining job. It is not a promised runtime or permission
to remove tests, supported Python versions, artifacts or verification gates.

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
| `installed-architecture` | Both Python versions run all 13 installed architecture cases and complete API/CLI/FASTA/manifest checks outside the checkout. |
| `circuit-integration` | Both Python versions exercise source metadata, infrastructure, review bundles, construction, molecules, intent and human circuit profiles. |
| `integration-examples` | Both Python versions retain all remaining audit, molecular, synthetic, human, authoring and CLI examples. |
| `studio-browser` | Installed Python 3.11 package, Node 22 and the pinned Playwright/Chromium setup run guided workspace, construction inspection and review suites. |
| `studio-typescript` | Pinned strict TypeScript checks, unchanged generated release assets, runtime response decoding and current migration inventory. |
| `ocaml-build` | Build once per native platform, check library boundaries/type transport, retain locked inputs and exact compiled suite/role bytes, and assemble candidate platform wheels. No test result is inferred from building a wheel. |
| `ocaml-native-tests` | Restore the current run/platform-bound executable bundle and run all Dune-declared suites with their original arguments and two bounded workers. Unsupported Dune declarations fail closed; no compilation occurs in consumers. |
| `ocaml-core` | Two workers execute all 67 original direct corpus, protocol, resource-bound and Python/OCaml conformance command groups against the same restored binaries. Commands within each group keep their original order and output paths; complete current-run group/log accounting is required before success. |
| `architecture-sdk` | Four platform/Python jobs run concurrently. Each uses two isolated Python workers for all 16 architecture scenarios. Case B retains all its rejection/publication controls. The coordinator applies the unchanged independent 175-check/219-artifact census before reporting success. |
| `executable-rna-reproducibility` | Depends only on `installed-executable`; compares complete relative-file SHA-256 inventories from both Python versions. |
| `payload-architecture-reproducibility` | Depends only on `installed-architecture`; requires all 13 case outputs and compares every relative file across versions. |
| `circuit-reproducibility` | Depends only on `circuit-integration`; compares the complete infrastructure/source/review artifact inventories. |
| `architecture-core-reproducibility` | Depends on both native builds and all four architecture SDK jobs; rehashes complete SDK/CLI artifacts from Python 3.11 and 3.14 on each platform and requires exact four-way equality with current run and executable authority. |
| `installed-campaigns` | Both platforms × Python 3.11/3.14 × five complete campaign groups (20 jobs, at most 20 concurrent). Each group installs the exact same SDK/native wheels outside the checkout and performs the complete smoke/uninstall/missing-package/reinstall lifecycle. Protocol runs alone. Manager, fixed, workflow and synthetic groups may overlap two complete campaigns after the serial install lifecycle; receipts retain the original recipe order. Fixed/reference, workflow and synthetic groups retain their original membership. All groups retain every original case, artifact and independent checker; no stateful scenario is split. |
| `realization-conformance` | Four independent aggregation jobs require all five group receipts and all 17 campaigns exactly once per runtime. Recheck current source/run/candidate identities, complete owned bytes, original command recipes, separate lifecycle logs, campaign logs and artifact hashes. Native input receipts bind the installed files for unchanged cross-runtime checkers. |
| `realization-core-reproducibility` | Rehash complete realization protocol, workflow and producer SDK reports, verify every original applicable occurrence and all additional cases, require current run/source/binary authority and exact equality across all four campaigns. Private producer calls and injected-proposal cases remain explicitly classified as native-library coverage. |
| `prebuilt-core-assembly` | Depends only on both native builds, allowing installation tests to start while other tests run. Independently checks complete platform wheels, original linked sources/notices/relink companions and final executable identities; builds and checks one pure SDK wheel containing both platform pins. |
| `prebuilt-core-validation` | Requires all four fresh-install/lifecycle/campaign receipts, exact owned bytes, original command recipes and successful upstream assembly, all native suites/conformance, architecture SDK checks, and cross-runtime reconstruction. |
| `validation` | Final gate requires all 68 jobs, including successful unit accounting, every installed/integration/browser job, TypeScript, both native platforms, all five reproducibility jobs and both prebuilt jobs. |

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
Corpus loading
separately denies child processes and network. Failed or timed-out installed commands print a
bounded, escaped tail of their complete retained log. Successful commands
print only the scheduler group/timing envelope. Every opened group closes
on failure as well as success; retained logs remain the diagnostic authority.

The final gate runs even when a dependency fails. Missing, cancelled, skipped,
stale, duplicated, wrong-runtime or failed work cannot become a successful
census. The registry includes 53 ordinary job receipts, ten unit shards, two
unit plans, two unit accounting jobs and the final gate: 68 concrete jobs.
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

The current suite discovers 3,594 tests in 381 classes on both Python versions.
The capture scheduling and callback fixture changes add 16 controls while
preserving all previous 3,578 test IDs. Placement weights retain the historical
fixture-inclusive maximum for every previously measured class. Fresh discovery
assigns the existing two-second fallback to unmeasured methods and classes;
the weights file records the historical measurement and its earlier inventory
reconciliation. No original test ID was removed. These estimates guide placement
and do not establish a runtime bound.

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
aggregate gate. Historical 31-job receipts retain their original revision's gate;
the new 36-job requirement applies to the realization protocol revision onward.
