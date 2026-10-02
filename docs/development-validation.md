# Development cadence and validation

This protocol reduces feedback time while preserving the compiler's existing
validation coverage and independent checks. The governing workflow is
[Python checks](../.github/workflows/ci.yml). The target is a measured **10–20
minute hosted validation cycle**, subject to runner availability, current test
cost and the slowest remaining job. It is not a promised runtime or permission
to remove tests, supported Python versions, artifacts or verification gates.

## Work in coherent batches

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
| `unit-plan` | Python 3.11 and 3.14 independently discover the full suite and produce five-shard plans. |
| `unit-tests` | Ten jobs: each Python version executes shards 0–4 against its plan, with at most ten running unit jobs. |
| `unit-accounting` | One per Python version independently verifies its complete five-result census against fresh discovery. |
| `installed-executable` | Both Python versions run the installed executable RNA API/CLI path outside the checkout. |
| `installed-architecture` | Both Python versions run all 13 installed architecture cases and complete API/CLI/FASTA/manifest checks outside the checkout. |
| `circuit-integration` | Both Python versions exercise source metadata, infrastructure, review bundles, construction, molecules, intent and human circuit profiles. |
| `integration-examples` | Both Python versions retain all remaining audit, molecular, synthetic, human, authoring and CLI examples. |
| `studio-browser` | Installed Python 3.11 package, Node 22 and the pinned Playwright/Chromium setup run guided workspace, construction inspection and review suites. |
| `studio-typescript` | Pinned strict TypeScript checks, unchanged generated release assets, runtime response decoding and current migration inventory. |
| `ocaml-core` | Linux x86_64 and macOS arm64 native builds, native tests, independent-library boundaries and exact Python/OCaml conformance. |
| `executable-rna-reproducibility` | Depends only on `installed-executable`; compares complete relative-file SHA-256 inventories from both Python versions. |
| `payload-architecture-reproducibility` | Depends only on `installed-architecture`; requires all 13 case outputs and compares every relative file across versions. |
| `circuit-reproducibility` | Depends only on `circuit-integration`; compares the complete infrastructure/source/review artifact inventories. |
| `architecture-core-reproducibility` | Depends on both native platforms; rehashes complete SDK/CLI artifacts from Python 3.11 and 3.14 on each platform and requires exact four-way equality with current run and executable authority. |
| `validation` | Final gate requires successful unit accounting, every installed/integration/browser job, TypeScript, both native platforms and all four reproducibility jobs. |

Reproducibility no longer waits behind the full unit suite. The intended steady
work comprises ten unit runners, eight producer runners, one browser runner,
one TypeScript runner and two OCaml runners;
planning and accounting are shorter phases. Actual overlap depends on the hosted
concurrency allowance. The final gate runs even when a dependency fails so that
failure, cancellation, missing artifacts and unexpected skipped jobs cannot
become an implicit success. Matrix failures must not cancel sibling coverage.

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
