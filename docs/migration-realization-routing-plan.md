# B1.09e: realization protocol and public routing next plan

Implementation checkpoint, 2026-10-02: The direct synthetic producer batch now supplies internal generation, selection and adaptation APIs. The public service/routing work below remains unimplemented. Re-read the current interfaces and language migration roadmap before beginning; this audit grants no validation or cutover claim.

Read-only audit of the PR55 working tree, 2026-10-02. This is an implementation
roadmap, not a validation receipt. No production code, CI, roadmap checkbox or
native executable was changed or executed for this audit. Reconfirm hosted PR55
and integrated-main results before treating its internal checkers as validated.

The subsequent [native protocol audit](migration-realization-protocol-native-plan.md)
and [complete conformance audit](migration-realization-protocol-conformance-plan.md)
freeze the proposed nine-operation payloads, explicit reduction controls, exact
capability records and full original-call/replay inventory. Their
[profile fixture](migration-realization-protocol-profiles.json) is a design
artifact, not an advertised or validated capability. They also identify the
required additional Unicode witnesses and distinguish keys from JSON values in
resource accounting.

## Starting state and completion boundary

`docs/language-migration-roadmap.md:392` leaves B1.09e open: accept complete external
authority, freshly recompute complete results, preserve every existing caller and
export gate. PR55 supplies internal checkers; it does not satisfy this public
boundary. `core/lib/service/service.ml` currently advertises only `capabilities`,
`canonicalize`, `validate-intent`, `verify-lowering`, `verify-architecture` and
`replay-architecture`. Producer service additionally exposes the existing
architecture production/export profile. No realization operation is dispatched.

`bioc_service` currently links `bioc_wire bioc_domain bioc_checker`.
`biocompiler-verify` transitively excludes `bioc_realization_checker`,
`bioc_semantics` and `bioc_candidate_runtime`; exact assertions enforce those
exclusions in `tests/test_core_boundaries.py:32-55`. Exposing realization checking
requires a deliberate dependency and documented trust-boundary update. It must
continue to exclude `bioc_compiler` and `bioc_producer_service`. Candidate execution
must still exclude source semantics; private provenance/assembly authority modules
must stay private and unavailable as generation endpoints.

Explicit native architecture SDK/CLI routing provides the transport pattern.
`compiler/workflow.py:415` rejects `compile(..., core=...)` for every other profile.
Keep that rejection until the corresponding producer contract exists. A working
native acceptance endpoint alone cannot authorize native generation, selection,
component adaptation, pipeline completion or archive publication.

Product scope remains human immune cells engineered in vivo and exact RNA
payloads. These historical synthetic profiles remain software regression support;
finite-history model acceptance does not establish empirical behavior or human
therapeutic admission.

## Exact internal APIs available for exposure

All paths below are relative to the repository root. Public signatures and
current policy/resource records are in `core/lib/realization_checker/*.mli` and
implementation files; use their constants rather than duplicating drifting names.

| API | Complete authority | Return / responsibility |
| --- | --- | --- |
| `Checked_request.of_json/check/make` | Full RealizationRequest: BuildRequest, Behavior, BehaviorContract, OperatingDomain; target in BuildRequest | Fresh source-to-Behavior lowering and matching contract/role/target authority; structural `Realization_request.of_json` alone is insufficient. |
| `Realization_check.dependencies[_with_usage]` | Behavior, BehaviorContract, OperatingDomain, Target, actual Mechanism, ObservationMap, exact InputFrame list, optional horizon | Complete DependencySnapshot. Identity/preflight evidence only; no model execution PASS. |
| `Realization_check.check[_with_usage]` | Same direct model authority | Complete CheckResult, including coverage and counterexample; deliberately does not claim BuildRequest lowering or synthetic generation provenance. |
| `Synthetic_candidate_check.check[_with_usage]` | Full RealizationRequest, actual SyntheticCandidate, exact history, optional horizon | Fresh lowering, independent provenance/catalog/policy checks, then actual independent source/candidate execution. Complete CheckResult. |
| `Component_behavior_check.check[_with_usage]` | Full RealizationRequest, actual ComponentAssembly, exact history, optional horizon | Fresh source authority, actual locked assembly reconstruction, linking and behavior. Complete CheckResult. No synthetic candidate correspondence claim. |
| `Component_assembly_check.check[_with_usage]` | Full RealizationRequest, actual SyntheticCandidate and ComponentAssembly, exact history, optional horizon | Fresh synthetic acceptance, independently derived full component correspondence, actual reconstruction/linking/behavior. Complete CompositionResult or exact rejection. |

All four checker modules and direct dependency calculation accept reduction-only
limits and optional shared parent Work_budget. Public wire calls must not accept
serialized private checked tokens or cached acceptance in place of the authority.
Assembly's CompositionResult does not itself contain the full history/candidate
identity needed to bind the public operation: the outer result must bind those
complete inputs too.

## Proposed wire operations (new, not currently implemented)

Use separate versioned profiles so callers cannot confuse their claim boundaries.
Freeze names and exact fields in `protocol/core-v1.md` before implementation;
the following is the proposed operation inventory, not existing capabilities.

| Proposed operation | Exact semantic payload fields | Native delegate |
| --- | --- | --- |
| `realization-dependencies` | `behavior`, `contract`, `domain`, `target`, `mechanism`, `observation_map`, `history`, `until` | `Realization_check.dependencies` |
| `verify-realization` | Same eight fields | `Realization_check.check` |
| `replay-realization` | Same eight fields plus complete `assessment` | Fresh `Realization_check.check`, then complete report comparison |
| `verify-synthetic-candidate` | `expected_request`, `candidate`, `history`, `until` | `Synthetic_candidate_check.check` |
| `replay-synthetic-candidate` | Same four fields plus complete `assessment` | Fresh synthetic check then complete report comparison |
| `verify-component-behavior` | `expected_request`, `assembly`, `history`, `until` | `Component_behavior_check.check` |
| `replay-component-behavior` | Same four fields plus complete `assessment` | Fresh component behavior check then complete report comparison |
| `verify-component-assembly` | `expected_request`, `candidate`, `assembly`, `history`, `until` | `Component_assembly_check.check` |
| `replay-component-assembly` | Same five fields plus complete `assessment` | Fresh assembly check then complete report comparison |

Wire `until` must be explicit null or the original exact numeric kind; public
optional Python arguments map to that field. Do not replace null with effective
horizon or coerce integer/float spelling in authority. If callers may request
resource reductions, add exactly one documented `limits` field with a frozen
five-field reduction schema; reject unknown fields, increases, zero and booleans.
Otherwise expose fixed limits only in this first protocol profile and retain
reduction tests at the native API. Do not invent undocumented optional fields.

Verification operations belong in both executable roles. Replay must compare
complete fresh reports and dependencies, including retained failures and unknowns;
it must not merely test the imported report's hash or PASS flag. Dependency-only
responses must be unmistakably non-accepting. Do not add generation or export
operations to the verifier.

Use a new versioned outer result schema per report family, e.g.
`biocompiler.core.realization_assessment.v1` and
`biocompiler.core.component_assembly_assessment.v1`, plus a separate dependency
result. These names are proposals to freeze. Include exact implementation,
resource profile, validation scope, supplied-authority fingerprint, assessment
fingerprint and complete assessment. Bind the full semantic payload (including
history/horizon and candidate/assembly when present); on replay exclude only the
historical assessment from the authority digest, while the process request still
binds it. Retain normalized domain identities and source artifact identities
separately. If additional individual supplied-document hashes are exposed,
verify every one against the frozen request snapshot.

Fresh semantic FAIL/UNKNOWN/UNSUPPORTED CheckResults are successful transport
responses carrying those complete outcomes. Structural, source-authority, invalid
horizon, resource, replay mismatch and assembly precondition failures are protocol
errors with no result. Preserve the existing exception precedence and native code
census; do not convert arbitrary errors into a generic unsupported report. Example:
invalid horizon precedes candidate identity rejection; assembly's nonpassing
synthetic precondition is `synthetic_component_acceptance`, while assembly source
correspondence rejection is `component_assembly`.

## Schema, identity and resource inventory

| Artifact | Existing schema / identity boundary |
| --- | --- |
| RealizationRequest | `biocompiler.realization_request.v0.1`; complete source artifact and separate semantic fingerprint |
| BuildRequest | `biocompiler.build_request.v0.1`; preserve target, bindings, source locations, policies, requirements |
| BehaviorContract / OperatingDomain / InputDomain | `biocompiler.behavior_contract.v0.1`, `biocompiler.operating_domain.v0.1`, `biocompiler.input_domain.v0.1` |
| SyntheticCandidate / GeneratorConfig | `biocompiler.synthetic_candidate.v0.4`, `biocompiler.synthetic_generator_config.v0.3` |
| SyntheticCatalog / SyntheticComponent | `biocompiler.synthetic_catalog.v0.1`, `biocompiler.component.synthetic.v0.1`; full pinned catalogs and locks, no name-only replacement |
| ComponentAssembly | `biocompiler.component_assembly.v0.2`; complete registry/composition/observation/source inventories |
| CheckResult | `biocompiler.realization_check.v0.1`; full diagnostics, checked requirements, counterexample, coverage and dependencies |
| CompositionResult | `biocompiler.component_link_result.v0.3`; full dependency, diagnostic and requirement inventories |
| Verification workflow | `biocompiler.synthetic_verification_request.v0.1`, `biocompiler.synthetic_verification_record.v0.1` |
| Synthetic build/history/manifest | `biocompiler.synthetic_build_request.v0.2`, `biocompiler.synthetic_history.v0.1`, `biocompiler.synthetic_build_manifest.v0.2` |

InputFrame, Mechanism, ObservationMap, Target and nested records must use their
existing complete codecs; do not replace them with a smaller invented wire
record. Pin accepted Behavior versions and all nested schema constants from the
current modules in capabilities/tests rather than inferring them from labels.

Core wire canonicalization uses compact sorted UTF-8 JSON (`ensure_ascii=False`).
Realization DependencySnapshot and CheckResult retain their historical compact
ASCII canonicalization (`ensure_ascii=True`). CompositionResult uses UTF-8.
Do not use the architecture adapter's UTF-8 hash helper unchanged for realization
report identity. Bind outer payloads with the core wire encoder and reports with
the report-family encoder, checking exact bytes as well as digest where provided.
Unicode, integer/float distinctions, negative zero, order-sensitive lineage and
full source-coordinate artifacts all remain observable.

Core transport ceilings remain 16,777,216 request bytes, 33,554,432 response bytes,
128 depth, 250,000 JSON values, 4,194,304 bytes per decoded request string/key and
4,300 characters per number. Envelope bytes/values count. Wire values exclude
object keys from node count; realization budgets separately count values and keys.
Document that distinction rather than accidentally changing either accounting.

`Realization_budget` defaults: 50,000,000 work, 100,000 retained monitor items,
16 MiB request, 32 MiB report, 250,000 report nodes. Resource record is
`biocompiler.realization_checker.resources.v1`; direct realization additionally
limits cumulative translated history to 16 MiB/250k key-value nodes, charging
translation before import. Wrapper resource profiles are
`biocompiler.synthetic_candidate_checker.resources.v1`,
`biocompiler.component_behavior_checker.resources.v1` and
`biocompiler.component_assembly_checker.resources.v1`. Publish complete nested
`limits_json` records: naming a wrapper profile alone does not describe its shared
budget or reconstruction/authority charges. Preserve conservative failure reserves,
report publication charges and assembly's cumulative derived-fragment reservations.
Transport framing/wrapping must be bounded as well as the inner report; no report
that fits internally is guaranteed to fit an arbitrarily enlarged envelope.

Current synthetic policy identities are acceptance v0.5, generator v0.4,
catalog v0.2, runner v0.2; their full prefixes come from Synthetic_authority.
Keep these semantic identities distinct from OCaml implementation versions and
protocol versions. Changing implementation language does not justify rewriting
historical evidence or erasing a dependency mismatch.

## Python adapter and public callers

Implement a transport-only client analogous to `core_architecture.py`: freeze
caller-owned JSON before capabilities negotiation/subprocess I/O; negotiate the
complete operation/schema/implementation/resource/scope profile on every call;
validate role, request ID, protocol/core versions, exact keys, outcome/claims,
complete result identity and authority binding. Never fall back to Python after
native selection. Preserve timeout, cancellation, process/encoding failures and
original diagnostics under the public error wrapper.

A `realization_backend.py` may hydrate historical result views only if round-trip
bytes and report-family fingerprints reproduce the complete native result.
Constructors are not automatically harmless codecs: Python
`RealizationRequest.__post_init__` (`compiler/request.py:495-511`) calls
`verify_lowering`. Existing workflow imports recursively construct that request.
Do not permit Python semantic validation during native request import or replay
merely by adding its module to a codec allowlist. Prefer raw JSON entry points for
CLI authority; native Checked_request owns fresh source validation. Design any
public typed workflow hydration explicitly and test it under the execution guard.
Do not bypass private immutability with unreviewed constructor hacks.

Add explicit `core` selection to the five existing direct public APIs, preserving
historical Python behavior when no selection is supplied:
`check_realization`, `realization_dependencies`, `check_synthetic_candidate`,
`check_component_behavior`, `check_component_assembly`. Preserve original nominal
argument errors and iterable-history semantics at the SDK boundary, before strict
JSON transport where necessary; enumerate unavoidable wire representation limits.
Update package-root exports and all module-bound/nested call sites, not only the
root namespace. A direct adapter test does not demonstrate downstream routing.

Python may retain scientific proposal/search orchestration, storage and transport,
but native-selected acceptance and canonical report construction cannot depend on
Python evaluators/checkers or producer reruns. Per-history native checking alone
does not port the semantic responsibilities of exploration/reduction or workflow
report construction. See dependency work below.

### Exact current source-call inventory

The following inventory was obtained by parsing every `src/biocompiler/**/*.py`
source file with Python AST. It includes direct Name/Attribute calls for the
listed APIs, not dynamic aliases or tests; the original full capture remains
necessary to detect those additional paths.

- `src/biocompiler/cli.py`: call `replay_synthetic_verification` at 1699; call `run_synthetic_verification` at 1712; call `select_synthetic` at 1738; call `build_synthetic_package` at 1834; call `publish_synthetic_package` at 1836; call `verify_synthetic_package` at 1856.
- `src/biocompiler/compiler/components.py`: definition `check_component_behavior` at 54; call `check_realization` at 66; definition `check_component_assembly` at 93; call `adapt_synthetic_components` at 103; call `check_component_behavior` at 146; definition `run_component_pipeline` at 154; call `run_synthetic_pipeline` at 168; call `adapt_synthetic_components` at 170; call `check_component_assembly` at 250; call `check_component_behavior` at 270.
- `src/biocompiler/compiler/synthetic.py`: definition `run_synthetic_pipeline` at 56; call `select_synthetic` at 87; call `generate_synthetic` at 225; call `check_synthetic_candidate` at 249.
- `src/biocompiler/compiler/synthetic_build.py`: definition `build_synthetic_package` at 98; call `check_synthetic_candidate` at 124; definition `verify_synthetic_package` at 224; call `build_synthetic_package` at 262; definition `publish_synthetic_package` at 274; call `verify_synthetic_package` at 277.
- `src/biocompiler/compiler/verification_workflow.py`: call `check_synthetic_candidate` at 189; call `check_realization` at 197; definition `run_synthetic_verification` at 229; definition `replay_synthetic_verification` at 253; call `run_synthetic_verification` at 271.
- `src/biocompiler/synthesis/components.py`: definition `adapt_synthetic_components` at 82; call `check_synthetic_candidate` at 92.
- `src/biocompiler/synthesis/selection.py`: definition `select_synthetic` at 354; call `check_synthetic_candidate` at 397.
- `src/biocompiler/synthesis/synthetic.py`: definition `generate_synthetic` at 717; definition `check_synthetic_candidate` at 734; call `realization_dependencies` at 750; call `generate_synthetic` at 803; call `check_realization` at 861.
- `src/biocompiler/verification/realization.py`: definition `realization_dependencies` at 191; definition `check_realization` at 262; call `realization_dependencies` at 294.

## Workflow and producer dependencies that remain separate work

1. **Synthetic verification workflow.** `verification_workflow.py` supports
   `check`, `explore`, `reduce` and candidate/model modes. Its `_checker` extends
   dependencies with workflow version, mode, exact candidate and realization
   artifact identity. Native routing must preserve these fields, not return a
   bare internal CheckResult in their place. Replay requires independently supplied
   complete operation authority and exact rebuilt record equality, including
   retained failures. Check command exit is PASS-dependent; replay exit zero means
   reproduction, not PASS. Port/version the full workflow authority/result codecs
   and semantic wrapper before claiming end-to-end native workflow acceptance.
2. **Exploration and reduction.** `verification/exploration.py` defines Boolean
   contact/input bounds, complete ordered campaign records, selected failure
   signatures, exact evaluation budgets and one-minimality. Treat enumeration as
   orchestration only if the core independently validates all claims and constructs
   authoritative final records; otherwise port the semantic campaign/reduction
   implementation. Fresh checks of a subset do not establish complete enumeration,
   original order or minimality. Advertise no native explore/reduce capability until
   the complete original workflow is preserved. Adversarial history generation
   retains its separate historical proposal role.
3. **Generation and bounded selection.** `_generate_synthetic`, `generate_synthetic`
   and `select_synthetic` remain producer obligations. Full configurations,
   alternatives, hard-policy rejection order, objective ranking, search bounds and
   selected candidate/coverage must remain present. Private Synthetic_provenance is
   an independent checker witness, not a substitute public producer. Existing native
   generic Component_selection_producer does not port synthetic mechanism search.
4. **Component adaptation and pipelines.** `adapt_synthetic_components` remains a
   producer; it first requires fresh synthetic PASS. Synthetic/component pipelines
   retain PassManager contracts, consumed/produced requirements, source links,
   obligations, profile completion and final independent checks. Propagate selected
   native check routing through nested calls and keep incomplete producer migration
   visible. Do not label a mixed Python-proposal/native-check path wholly native.
5. **Synthetic archives and export.** `build_synthetic_package` chooses synthetic
   or component pipeline, reruns standalone synthetic acceptance, then materializes
   all historical artifacts, manifests, reports and deterministic archive bytes.
   `verify_synthetic_package` requires a complete independent request and/or build
   fingerprint, rebuilds with current tools and compares manifest plus entire archive
   bytes. `publish_synthetic_package` re-verifies before atomic publication. Preserve
   these gates, independent software-use/admission checks and external authority;
   replacing rebuild with imported PASS/hash checking is a regression. Storage and
   atomic archive writes can remain Python after canonical content and acceptance
   are core-owned. Until these producer/reconstruction dependencies are implemented,
   B1.09e's entire-caller/export exit remains open.

CLI inventory: `synthetic-check`, `synthetic-explore`, `synthetic-reduce`,
`synthetic-replay` route through `_verification_command`; `synthetic-select`
through `_selection_command`; `synthetic-build`, `synthetic-verify`,
`synthetic-inspect` through `_synthetic_command`. Add executable selection only for
implemented profiles with the existing architecture flags/error discipline.
Inspection remains historical integrity inspection. Preserve bounded file reads,
command/operation agreement, exit meanings, atomic report publication and input
file overwrite protection. Failure must not leave an apparently accepted output.

## Complete conformance and installed-routing requirements

Use the full existing original cohort, not a new convenient subset. B1.09e's older
324-method/23-module baseline was expanded by synthetic authority/acceptance to
**373 methods across 29 modules, 381 contexts and 47,758 observations**, including
two actual subprocess consumers (hash seeds 1 and 37, 24 observed APIs each).
Retain original baseline assertions unchanged, then run the routed counterparts
with identical authority/results/exceptions and actual subprocesses.

The synthetic acceptance corpus covers **4,119 reached acceptance calls**:
906 synthetic checks, 52 assembly checks, 85 component behavior checks,
1,080 realization checks and 1,996 dependency calls. Preserve all calls and exact
source context, not only distinct inputs. It retains **2,372 explicit unported
producer calls** (1,144 private generation, 1,086 public generation, 38 selection,
104 adaptation); keep these visible as dependencies rather than deleting them to
make a native-only campaign look complete.

Mandatory existing evidence: source transport, candidate runtime, component runtime,
realization foundation, realization checks, component acceptance, synthetic
authority and synthetic acceptance corpora, plus original complete product suites.
Source/candidate traces already have complete mandatory runtime corpora; do not
replace them with fingerprints or remove those gates. The synthetic acceptance
inventory is `d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331`
(4,910 documents / 109,400,531 bytes); source capture fingerprint is
`9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29`.
Freeze a separate routing corpus with exact installed invocation expectations;
leave prior corpus bytes unchanged. Independently recapture all original calls
and compare complete documents byte-for-byte.

Preserve exact five existing checker-version mutation witnesses and full current
report comparisons. The fixture adapter is test-only; expose no production checker
version override. Preserve original malformed argument/nominal boundary errors,
resource errors and known version-specific Python exception witnesses precisely;
do not broadly normalize messages to conceal mismatches.

Build `tools/check_realization_protocol.py` and
`tools/check_realization_routing.py` (proposed names) following the installed
architecture campaigns. Both executable roles must run from installed packages
outside the checkout, without PYTHONPATH/source leakage. Run Python 3.11 and 3.14,
Linux and macOS with exact census receipts. The routing execution guard must block
Python lowering, source/candidate evaluators, acceptance, dependency construction,
semantic report mutation, producer reruns during check/replay and fallback.
Whitelist only audited code-object/record codec paths and explicit orchestration;
exercise the real CLI in child processes under the same guard. Guard tests must
fail when a semantic callback is inserted behind an innocently named helper.

Protocol/routing mutation matrix must include: missing/unknown profile and fields;
wrong role/version/operation/request ID; missing/stale/swapped complete authority;
mutable input changes during negotiation; forged report/dependencies/coverage/
counterexamples; source-coordinate relocation; coherent actual-candidate mutations
that legitimately pass or fail; both profiles and both conjunction strategies;
Unicode and int/float/null horizon distinctions; stale catalogs/locks; altered
assembly inventory, wiring and parameters; nonpassing synthetic adaptation;
unsupported source policy; exact diagnostic precedence; unavailable executable;
invalid JSON/UTF-8/duplicate keys/NaN; timeout/cancellation/nonzero exit; every
resource limit and repeated invocation after failure. Replaying a historical
FAIL/UNKNOWN/UNSUPPORTED must reproduce it without converting it to acceptance.

Do not launch another enormous cohort just to count observations. Inspect existing
raw capture and receipts first, define the routing projection and additional
consumer census, then run the one complete capture needed for changed routing.

## Coherent implementation sequence and exit gates

- [ ] **R1 protocol specification:** freeze operation/payload/result/profile schema,
  complete input identities, outcome/error rules, limits and claims. Choose whether
  reduction controls are public. Record distinction between direct model and full
  source/candidate/assembly authority.
- [ ] **R2 native service:** add the bounded realization service and dispatch;
  expose both verifier/core roles; keep producers/private witnesses inaccessible;
  fresh full-result replay and dependency-only nonacceptance; update exact boundary
  inventory/mutation tests and stale architecture-only claim text.
- [ ] **R3 strict Python transport and public direct routes:** implement negotiated
  clients/raw-document adapters, exact report encoding/hydration, optional public
  selection, nominal error parity and cancellation; prove no semantic fallback.
- [ ] **R4 installed full direct-caller campaign:** retain every captured acceptance
  call and original assertion, profile/type/mutation/resource errors and actual
  children. Separate inherited producer calls as incomplete dependencies. This is
  a useful releasable checkpoint, not closure of B1.09e.
- [ ] **R5 complete workflow routing:** implement check/mode dependency semantics,
  full request/result codecs and fresh replay, then complete exploration/reduction
  authority and claims; preserve CLI behavior and complete historical reports.
- [ ] **R6 producer/pipeline/archive dependencies:** port or explicitly separate
  authorized Python exploratory proposals from core-owned deterministic passes,
  canonical manifests and fresh export acceptance; preserve full archive rebuild,
  admission, provenance and completion obligations. Never remove guards to fake
  progress while a profile is unimplemented.
- [ ] **R7 hosted integration receipt:** all required native suites on Linux/macOS,
  installed protocol/routing campaigns for both Python versions, complete five-shard
  original tests per version with exact discovery accounting, all product/browser/
  reproducibility gates, and exact source/tested merge/integrated tree identity.
  Update B1.09e and relevant LM checkboxes only to the extent actually completed;
  default engine cutover and distribution remain their separate roadmap gates.

## Audited source snapshot

The following hashes bind the read-only inventory; they do not assert CI status.
Re-run the audit if these files change before implementation.

- `docs/language-migration-roadmap.md`: `ba230594e074b531d98eeec86c3f6fc7a786f6ac3863cf756e59743ea5cf5dc0`
- `protocol/core-v1.md`: `b32585c8b8fe65011f299b6524872d7f60fe520ccbcf7cb58b64725a00435609`
- `core/lib/service/service.ml`: `3754b646ff6fc6474189ca8cd0c4d6453be7dcfd6156305d368276e96b607b67`
- `core/lib/service/architecture_service.ml`: `d5ddadad21528e76d221c9b653c9b01c92ef407b1f9008336c45adad122f9320`
- `core/lib/service/dune`: `507ecbbcb1b8b1b10458d5c329f208a6c8446e676f4d2ba4b0478ee34a53cbbf`
- `core/lib/realization_checker/dune`: `df1a3fe7a1ac84ef51f1f6ed6eaf5801a0305303ae7b8b984ecab9c6413c0b72`
- `core/lib/realization_checker/realization_check.mli`: `fbd17b867fa278870078249fb72f84786961ad13fda8a318d15ef01898fc411b`
- `core/lib/realization_checker/synthetic_candidate_check.mli`: `d07cb5fa80fe6ac8f01d972eae1c20445acb9bad1faff92af9faecc5c4858720`
- `core/lib/realization_checker/component_behavior_check.mli`: `93542ee658fadc0a20b182fd5e0dee43de4b51fafe013faa5330642c069f5b39`
- `core/lib/realization_checker/component_assembly_check.mli`: `0d73dd22d447c9188fe9e57cd082f876b4c692bd1333317d58c408ea2fda752d`
- `src/biocompiler/core_client.py`: `c8d65a42c1f92cbd75cb5edd176a9463657e03509be8ed487496d78b17be00fc`
- `src/biocompiler/core_architecture.py`: `091c6b78aa112f4a5de5dabfb664fee8f47a8eb021eacc7801023b5dccecb31b`
- `src/biocompiler/architecture_backend.py`: `faac33bfc42f3768f70fb89ae7f31773ff943d8488acd133c874f4cdb3e2caf6`
- `src/biocompiler/compiler/request.py`: `6b87777cfad4a06fe485e6fb4d29bdd02312f99df5193ea0d3351a57e1065caf`
- `src/biocompiler/compiler/workflow.py`: `90cbe26057ba348c620403415e2c12209e76f4966d1d7b8e90744e0ef619c40e`
- `src/biocompiler/compiler/verification_workflow.py`: `04d9818933ae3ded190d4139023340f88c1eb7d8f2325173c4c77c056f7b7dd6`
- `src/biocompiler/compiler/synthetic_build.py`: `8ba430132fc1e8dd6158005cc5e3bc810fe36a5efd8225e289276562abf653c4`
- `src/biocompiler/compiler/components.py`: `c196b78c44411599ffa5d68dc0c6a9095635ffc8a994f9b273c9d5fc26a2d4f8`
- `src/biocompiler/compiler/synthetic.py`: `9ecf345ff5ea4da687b6344342862c68cd116296e01308f8d4c76d05dc091ff2`
- `src/biocompiler/synthesis/synthetic.py`: `704679757c3a39c9edd2cd5e67b149791a00907ae45ee83282a15c0beccec488`
- `src/biocompiler/synthesis/selection.py`: `6337ec4e394e0f684344d29b97bc0a411fb2aa4917d53d48e8082566397bae60`
- `src/biocompiler/synthesis/components.py`: `ae548945c03b8dca75208abec47fee2e62bc03cceb7958ed645905813e5f2cb0`
- `src/biocompiler/verification/realization.py`: `1c0507ecde8da253061cffec6cbd003fb271ad2df930c7516b18b473f2f862a3`
- `src/biocompiler/verification/exploration.py`: `a4b85d8b0f48198128bc9064fa065eddc8c5f6acb4d68d92a21008c79723ca98`
- `src/biocompiler/cli.py`: `eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0`
- `tools/check_architecture_routing.py`: `c01230f705f8b37a1dda02e7e69f6459a00ba96c199a09c189c28296d0bcfafd`
- `tools/check_core_boundaries.py`: `b2dd63e80c1d25e770247698954754be8b7c7b8f3802b83bb0e06caa20a6d80b`
- `tests/test_core_boundaries.py`: `d9c1d14cb344a4294c45a1b25ad4d0b7df0626bf0bc7a079dbefac2c83a2a6a1`
- `tools/freeze_synthetic_acceptance.py`: `b31ba8f59a33fa03e6a3694bd98005fd85e4139d1ea6fbaac8f4f6af2e29e616`
