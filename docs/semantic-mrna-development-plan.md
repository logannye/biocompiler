# Semantic compilation from Python policy to exact mRNA

Prepared 2026-10-05; tracker refreshed 2026-10-06, America/Los_Angeles. This is the active development plan and to-do list for the remainder of this session. Update it as individual implementation, verification and acceptance tasks close; retain the exact scope and evidence for each claim.

## 1. Objective and scope

Given a Python-authored therapeutic policy, versioned implementation contracts and sequence-construction rules, produce an exact mRNA artifact whose complete derivation preserves the program's supported meaning, or return a precise reason compilation cannot proceed.

The acceptance target is internal semantic correctness through every compiler layer. Supplied component behavior and model-to-sequence bindings are explicit premises of compilation. Experimental evidence that those premises hold in cells is not an acceptance prerequisite for this phase.

Included:

- Python therapeutic-design records, builders, patterns, composition, immutable requests and serialization.
- Native source admission, operational semantics, implementation lowering, component/material binding and requirement checking.
- Exact mRNA construction, independent verification, immutable artifacts, fresh SDK/CLI export and installed acceptance.
- Declared recipient, environment, timing, capacity, resource and material constraints as formal contracts.
- Positive compilation, precise rejection, unresolved obligations and bounded verification outcomes.

Deferred: Studio, conversational authoring, biological viability, empirical calibration, therapeutic efficacy, unrestricted mechanism discovery, arbitrary sequence invention and automatic production-wide migration. These are not hidden prerequisites for this plan. Existing empirical/human-use statuses remain separate; this work neither changes their policies nor requires them to become positive.

Completion means a complete stack for an explicitly declared supported profile, plus an exhaustive disposition of the wider source vocabulary. It does not mean that every expressible policy must compile. Unsupported source meaning must remain visible and must prevent a complete-artifact claim when it is required by the program.

## 2. Current checkpoint, starting point and ownership

Most recently completed hosted integration source: [PR85](https://github.com/logannye/biocompiler/pull/85),
`a85b1112ff35ba988a71cc969bfabdfefb354cfe`, contains the policy compiler and the
preserved reference/package migration. It includes exact policy head
`bb84421cf1f93cd1dc02813d80a2c54a3520a919` from
[PR95](https://github.com/logannye/biocompiler/pull/95). The user confirmed that
this session is the sole integration owner. Preserve prior branches and worktrees.

Two bounded Python-policy → exact-mRNA paths are implemented: the original
supplied whole-graph route and a separate reusable-component composition route.
The latter independently checks two policy families sharing the exact same driver
and emits one complete RNA member with fresh paired export. Its hosted source-tree
path passes; installed-package, release and actual-main acceptance remain open.
Bounded alternatives, delivered helpers and multiple RNA members remain future
extensions. Studio, conversational authoring and biological viability remain deferred.

**Overall acceptance is still open.** Completed specification and implementation
tasks are checked for their stated bounded profile. Broader source coverage,
composition and release obligations remain open. An implemented stage, a passing
subset or a supplied contract is not a completed release gate. Use the following
tracker as current status; older checkpoint paragraphs are historical evidence.

**Merge sequencing correction:** the frontend census uncovered two preexisting
authoring defects: encounter construction could leave its generated target after
rejecting the encounter ID, and `state`/`channel`/`require` could erase foreign
ownership before checking a namespaced copy. Both reproduce on a previously
complete source document. Narrow fixes and six regression controls are committed as
`ebfc76b6d` in the isolated follow-up worktree, with the reviewed descriptor and
pattern controls in its preceding commits. The coherent follow-up and tracker
are published on `codex/policy-descriptor-witnesses`. The later source-validation
correction is published there as `360e2cbbd`; its exact scope and independent
evidence are recorded below. PR85 itself
has completed its original 74-job gate at `a85b1112f`. The complete final run,
job, artifact and PR-head/base snapshot is preserved before advancing the head.
Its inert artifact audit can overlap the corrected head's fresh validation;
the old local checkout and captured authority stay frozen. Validate the corrected
exact revision before normal merge. A passing a85 run or PR95 audit cannot accept the
changed frontend. These findings do not establish a failure of the independently
checked native bounded profile.

| Package | Implemented scope / completed work | Verified evidence | Remaining work and acceptance |
| --- | --- | --- | --- |
| SM-00 Operational foundation | Versioned truth/evidence, identity, scoped state, arbitration, silent freshness/timeout, correlated attempts and lifecycle semantics | Current union complete native suites and correction preflights passed; independent audit of both native bundles passed | Full installed/aggregate gate and main acceptance; retain exclusions |
| SM-01 Source authority and coverage | Immutable builders/serialization, original request/definitions, structural mRNA predicate, syntax and contextual ledgers | 612 syntax distinctions; 62 contextual families, 96 production dependencies and 30 witness files; 16 families explicitly partial | Complete promised contextual witnesses or narrow their claims; full source-valid exclusion and pattern/identity coverage; exact union acceptance |
| SM-02 Request/domain/preservation contract | All seven specified tasks implemented for the bounded truth/exclusive profile, including strict admission, causal domain and exact preservation/assurance contracts | Concrete schemas, executable checks and literal counterexamples; separately audited PR95 native/service evidence | Full integration/release remains dependent on SM-00/08; wider assumptions, types and assurance profiles remain excluded |
| SM-03 Independent primitives | Typed executable graph and candidate runtime independent of source evaluation | Current union complete native literal/mutation/dependency suites independently audited; four SDK slots and six full cross-slot comparisons passed | Complete current artifact audit and acceptance gate; new numeric/machine primitives remain future work |
| SM-04 Lowering and bounded preservation | All six tasks implemented for the first one/two-rule family: real lowering, source obligations, complete bounded exploration, independent requirements and distinguishing mutations | Literal nine-history / 47-transition / 48-prefix success, separate rejected/incomplete requests, current union native suites passed | Complete current union audit/main gates; preserve work-exhaustion results and open broader contextual/mutation coverage |
| SM-05 Components and architecture | Original whole-graph binding plus exact two-component composition, original context/provider binding and aggregate finite resources | PR95 original-profile checks; separate component source-tree native and SDK path passed at 5a45d354e | Component installed/release acceptance; finite alternatives, helper dependencies, broader ownership and multiple RNA members remain open |
| SM-06 Exact construction | Whole-graph and ordered component assembly both produce exact single-member construction, coordinates, chemistry and material correspondence | PR95 four-slot original-profile checks; component source-tree exact A/B FASTA/manifest ZIPs passed at 5a45d354e | Component installed/release acceptance; helper products and multiple members require extensions |
| SM-07 Public SDK/CLI and export | All six first-profile tasks implemented and demonstrated: complete manifests, immutable native transport, conservative invalidation, compile/check/replay, producer-free Verify and fresh paired export | Current union four SDK slots, six comparisons, four policy-prebuilt installed slots and prebuilt comparison passed; separate PR95 evidence independently audited | Independent exact-union artifact audit, complete aggregate and main gates |
| SM-08 Compatibility and acceptance | Full combined workflow, retained legacy routes/corpora, exact unit accounting and targeted prebuilt routing | Original a85 union passed all 74 hosted jobs and independent 102-archive audit. PR95 all 42 hosted jobs and independent audit passed | Correct static GMP extraction timestamps after run 37545710899 failed macOS dependency preparation; then fresh full gate/audit, normal merge and actual-main validation |
| SM-09 Vertical expansions | SM-09.1 complete: select exact reusable component composition; fragment, local material/library and assembly-rule decoders/tests implemented; independent assembly checker and literal material tests implemented | Hosted source-tree path passed at 5a45d354e: all sixteen native suites and 26 public SDK observations, including exact A/B paired exports; installed and release acceptance remain open | Source registrations, installed/offline four-slot campaign source and additive audit profile are implemented; hosted installed/full acceptance, independent final artifact audit and actual-main acceptance remain open |

### Completed integration and validation tasks

These checkboxes record the stated completed task only; they do not close the
broader SM acceptance items below.

- [x] Integrate verified PR88 main and the exact PR95 head into PR85 while preserving original reference/package implementations and immutable corpora.
- [x] Commit and push the coherent compatibility correction as `a85b1112f`: exact plan-bound Python selection, byte-exact historical entrypoint restoration, narrow source-identity proofs, corrected workflow assertions and a source-valid ownership fixture.
- [x] Pass the exact 49-selector preflight on Python 3.11.15 and 3.14.6: **416 tests each**, with all four 1,563-file source snapshots unchanged.
- [x] Pass all nine original build-semantics methods on both interpreters with descendant process launches denied; reproduce the complete guarded 39-occurrence continuation oracle unchanged.
- [x] Pass both hosted PR85 preflights and both native builds at the current tested tree.
- [x] Pass the focused native policy/implementation/molecular group on both platforms, including the corrected ownership fixture. The installed campaigns and final acceptance are separate downstream tasks.
- [x] Pass both complete hosted native-suite jobs, covering the retained 149-suite inventory on each platform. Independent final artifact auditing and the full release gate remain open.
- [x] Pass both complete hosted direct-core jobs, retaining all 67 original groups per platform.
- [x] Independently audit both current-union native bundles: 151 executables, 23 fixtures, all 149 suite records and 67 direct-group records per platform, plus exact published Core/Verify bytes and all six successful producer jobs. No local native execution.
- [x] Pass all four current-union architecture SDK slots and the complete six-comparison job, plus all four policy-prebuilt installed slots and their comparison.
- [x] Pass the current union's hosted original-continuation and original-registration comparisons. The 18:26 UTC exact-job read confirms both successful steps; independent final artifact auditing and the remaining reference/prebuilt/aggregate gates are separate.
- [x] Pass all ten current-union unit shards and both unit-accounting jobs with plan-bound interpreters, then independently audit all 14 unit artifacts: each runtime has 4,063 successful tests and 26,705 successful retained subtests, with no duplicates or omissions.
- [x] Independently audit PR95's complete unit accounting, Linux/macOS native packages and source companions, and all four prebuilt ownership/material/offline slots. These results belong to `bb84421cf`, not the later union.
- [x] Independently replay PR95's six complete architecture/policy comparisons against authenticated original artifacts (`six-comparisons-scoped-proof.json`).
- [x] Pass PR95's full 42-job hosted gate and independent final artifact audit at `bb84421cf`: 27 ordinary receipts, 14 unit artifacts, six comparisons, four owned prebuilt slots and all 53 selected ZIPs. Union/main acceptance remains separate; large legacy semantics retain their required hosted checks and receipt evidence.
- [x] Specify the next composition fixture: two source families reuse an identical driver, with independently supplied connections and material fragments. This is completed design preparation only.
- [x] Implement and independently review atomic encounter construction and original-record ownership checks, preserving accepted builder values; pass all six new regression controls on both interpreters. Full hosted integration remains pending.
- [x] Implement the bounded authored-API and source unit/scope ledgers with independent drift/overclaim controls; pass the 55-test authoring/API pair and 29-test source-context pair. This completes the stated static tooling, not the wider SM-01 semantic census.
- [x] Prepare and independently review the separate actual-main identity predicates: four positive and 83 rejection controls pass on synthetic literal inputs, including normal-merge parents, push identity and unchanged accepted trees. No real main revision or main acceptance is established by these controls.
- [x] Implement the separate partial component-fragment domain, closed schema and independent literal native-test source as `4fbf4176f`; pass the 34-test Python boundary/bundle pair and preserve the independently maintained suite/fixture census in `3518db4b7`. This closes source preparation only; native tests, complete schema validation and the composition path remain open.
- [x] Implement and independently review the per-call source-closure validation correction as `360e2cbbd`; pass 22 synthetic/source-lineage tests on each Python version and the two unchanged restoration regressions after preserving their authentication order. Every original semantic check, historical witness and hosted comparison remains required. Original replay and corrected-head release acceptance are still pending.
- [x] Implement local component material/library decoders and independent native tests: complete root identities, exhaustive feature carriers, products, typed symbolic prerequisites and eager exact library membership. Focused hosted compilation/execution passed at a89f80b07; full assembly acceptance remains open.
- [x] Add an opt-in hosted development lane with one native build and a fixed focused suite inventory, separate source/run-bound diagnostics and no release-acceptance claim. All 12 mocked workflow tests pass on Python 3.11.15 and 3.14.6 with native/process/network execution denied. First hosted run 37515212004 passed at a89f80b07 in 2m41s.
- [x] Pass all 74 jobs of the original a85 union and capture its complete final authority before changing PR85. The independent archive audit subsequently passed for that exact subject.
- [x] Implement exact original assembly rules and independent A/B controls; hosted run 37518443101 at ac3a0d3cb passed all ten suites, including 93 assembly-rule controls.
- [x] Independently check complete component graph/material correspondence: all eleven native suites and 403 new assembly controls passed at 25385487c in run 37521613648. This closes the leaf checker, not original context or complete export acceptance.
- [x] Bind original request/catalog/context authority and arrange the complete supplied component graph without replacing original source authority. Hosted run 37523740443 at 9ebd2be39 passed all twelve suites, including 469 assembly checks and 97 request controls.
- [x] Independently check declared context, complete record layouts, exact provider identity, timing and aggregate resource sufficiency. Hosted run 37524498720 at fbfefff75 passed all thirteen suites, including 323 context checks.
- [x] Promote recurring release auditing into stable versioned tools at 832ceb98c. Twelve test methods passed on both supported local Python versions; clean exact-tool CLI preparation and eight authority rejection controls passed. This tool validation is not acceptance of a new release.
- [x] Complete the combined original-obligation checker and public native/Python route through paired artifacts and fresh export for both reusable-component policies. Hosted run 37527311912 at 5a45d354e passed sixteen native suites and 26 SDK observations; root independently verified all 1,133 source pins, retained observations and both exact ZIP pairs. This closes source-tree development only.
- [x] Complete the new component profile’s source registrations at `6ed5a952a`: exact native capability census, separate component rule index, public API/source indices, migration ownership, reviewed source-addition pins and strict typing. Both supported Pythons passed 103 focused tests and 36 extra import-denial controls; historical definitions remain preserved. Fresh hosted development run 37531033330 and its independent artifact audit passed: all 1,134 source records, sixteen native suite records, 26 SDK observations and both actual RNA/manifest ZIPs. This checkbox closes source readiness and development evidence, not installed or release acceptance.
- [x] Implement and independently review the installed component campaign source: one original-packet emission per platform, the shared 26-observation SDK witness, seven-transport/16-observation offline Verify consumer, and additive prebuilt v0.2 comparison in the same four slots. All 142 focused Python cases are covered on both supported interpreters (136 passed in the combined run; six CI tests passed after restoring omitted sparse-checkout inputs and priming read-only host metadata). Each new campaign also passed its isolated guarded pair. All 18 inventory tests and the exact inventory check passed on both runtimes; all 3,760 existing IDs/authority fields and prior test links are preserved. Hosted native, installed and release acceptance remain open.
- [ ] Run the new installed four-slot component and Verify-only offline campaigns on hosted native builds, compare complete results, then require full release and actual-main acceptance. Existing whole-graph installed results do not transfer to the new component profile.
- [x] Pass the exact committed installed-campaign batch through the existing source-tree development lane and independently audit its complete retained evidence at `affe77625`. This is a development regression check only.
- [x] Implement and independently review the hosted macOS ARM64 CPython 3.11.15 bootstrap at `aeb3c95c7`. Both supported local interpreters passed 45 focused and 13 inventory tests under process/network guards; all 3,731 inventory IDs, authority and prior links remain intact. Review corrected receipt publication before the cache completion marker. No native interpreter was downloaded or executed locally.
- [x] Restore hosted availability of the exact supported macOS ARM64 CPython 3.11.15 via the digest-pinned supplied interpreter archive. Isolated run 37543965833 and independent retained-evidence audit passed, including all 31 hosted tests and the unchanged frozen standard-library authority. Full native/installed release acceptance remains open.
- [x] Consolidate recurring release auditing into stable versioned repository tools without weakening source/run identity, complete coverage, archive bounds or merge/main checks. Tool implementation and supported-runtime profile are committed at 129bcd7d7; the bootstrap workflow correction is independently reviewed and committed at `6d73d74e7` (18 focused tests on each Python, with the exact eleven executions and 27 skips preserved). The additive component audit profile is committed at `1c67b5b3c`: 20 legacy and 17 component tests pass on each supported Python, and the exact full source plan derives independently. It retains the original profile and all release gates; prior profile results do not transfer.
- [ ] Validate the three added descriptor rejection controls on hosted CI: valid-format stale digest, unsupported observation formal, unsupported effect result. Source controls are implemented in the corrected follow-up; preserve the shared-context reachability index.
- [x] Complete the original a85 union's full 74-job hosted gate and independent 102-archive audit. Its evidence does not accept the later corrected head.
- [ ] Integrate the reviewed frontend corrections and coherent source-coverage follow-up; complete a fresh exact-revision hosted gate and artifact audit before normal merge. Retain the earlier a85 run as distinct evidence.
- [ ] Merge the corrected, exactly accepted union normally, preserving branches, and validate the actual main revision with its own full fresh gate.
- [ ] Continue reconciling each SM task against its own exit and evidence as work completes; leave wider unsupported/compositional gaps open.

### Exact validation subjects and retained evidence

| Subject | Source / tested checkout / tree | Current evidence boundary |
| --- | --- | --- |
| Original PR85 union | H `a85b1112ff35ba988a71cc969bfabdfefb354cfe`; C `00af6e6bab506d52a700e0a72e16ef2e2e8d8d61`; shared tree `7d22ca4c27eafcd36f018b3f262ef87404a3caf6` | [Run 37471505350, attempt 1](https://github.com/logannye/biocompiler/actions/runs/37471505350): all 74 jobs and the independent 102-archive audit passed. Corrected-head and main acceptance remain distinct |
| Corrected PR85 follow-up | H `510ba5fe8805c8e4ea13aca52283edf17aec6e3f`; C `5f512fa722757ca6c8805f007521dd8c8e62e5a4`; shared tree `1ae5c9885696cd370d7f699fb7bd1d98e056f8cf` | [Run 37519748082](https://github.com/logannye/biocompiler/actions/runs/37519748082), attempt 1, finished with 67 successful, six failed and one skipped job. The inventory omission and hosted Python patch drift explain the failures: the 3.14 unit shard received 3.14.8 and the Linux 3.11 realization aggregator received 3.11.17; dependent accounting, prebuilt and aggregate gates correctly failed. Both 149-suite native jobs, both 67-group direct jobs and all four architecture/policy SDK slots passed, without accepting the failed full run. Final diagnosis and raw evidence are retained at `work/policy-descriptor-witnesses/generated/migration-next/pr85-pr95-union/run-37519748082/final-20261006/diagnosis.json`, SHA-256 `e9f903062013118e4e5771b7add7aeea2eed8ccb4d580ddd0cdf154f1ce965f9` |
| Supported-runtime release correction | H `8c61f45af9969d27d951754be7f633f7207d2547`; tested C `10a7f358363074083afc5b938bf599bb634b46bf`; shared tree `7e7a8b6f9ba3f9e95f37a53dfba9cc14ac754a25` | [Run 37539833174](https://github.com/logannye/biocompiler/actions/runs/37539833174), attempt 1, finished with 30 successful, three failed and eleven skipped jobs. All ten unit shards and both accounting jobs passed; macOS failed before compilation because setup-python lacked the exact 3.11.15 ARM artifact, with dependent prebuilt/final failures. Every healthy job was allowed to finish. Final diagnosis SHA-256 `2c1e29b45c04513ae762e4bec5ee431b890af825650a61b0a5db88430d9c12db`. The separately validated bootstrap is included in the next integrated candidate; this failed run grants no acceptance. |
| Exact macOS Python bootstrap | H `aeb3c95c7f7aa9202e6416154c99d91bb660a369`; tree `4626e69d0247c0ab825dd6f818e2ba07777bc30b` | [Isolated smoke run 37543965833](https://github.com/logannye/biocompiler/actions/runs/37543965833) and independent retained-evidence audit passed: exact supplied interpreter archive, 2,593-entry hosted closure, normal setup-python selection and all 31 tests. Audit proof SHA-256 `460073b32cea203965586596f81d635434c279c3b83cdb52a62094ad8f964f5f`. No compiler/installed release acceptance is implied. Merged into component source at `5717cb288` (tree `634b7865e2b8ce6dafee0e0206ccbd0d6ac4c3b0`), preserving its complete installed campaign additions; 45 focused and 18 inventory tests passed per local supported Python. |
| Component development batch | H `5a45d354ee869f26f0e5d3181c8972a6402baca6`; tree `fbc4b75d38c363e49e2a7314695fa245b426a2df` | [Development run 37527311912](https://github.com/logannye/biocompiler/actions/runs/37527311912): all sixteen native suites and 26 public Python SDK observations passed. Both exact 17/18-base RNA plus complete manifests were independently inspected. Native step completed 3m26s after run creation; full run with SDK took about 5m45s. Installed and full release acceptance remain separate |
| Component source-registration batch | H `6ed5a952a24c295404f4c0cb761948d69f79133f`; tree `4103da6f8ef9c1b9ed2f26108a5714a12dfe08bb` | [Development run 37531033330](https://github.com/logannye/biocompiler/actions/runs/37531033330) and independent artifact audit passed, including all sixteen native suites, 26 Python DSL-to-export observations, 1,134 source records and both exact RNA/manifest ZIPs. The retained inert audit proof is `work/policy-component-composition/generated/hosted-development/37531033330/inert-audit-proof.json`, SHA-256 `280d4163a25056cfba749a919f3e0c7df24ef15cf01f4529d8fee3c658189f2c`. Local source-only checks passed on both supported Pythons: 103 focused methods, 36 extra import rejections, strict core/policy typing and five static coverage/schema checks. The 3,731 original migration entries and authority fields are preserved; 29 entries belong to the two new adapters. Installed/full release acceptance remains open |
| Installed component campaign source | H `affe7762552d2178da011eccbc80fe75d1b89925`; tree `f6ec77b73b348055bbb5e04e90d9bdab4573f5bd` | Committed and pushed with independent source review, 142 focused cases covered per supported Python, 18 inventory tests per runtime and all existing authority preserved. [Development run 37542367988](https://github.com/logannye/biocompiler/actions/runs/37542367988) and independent retained-artifact auditing passed: sixteen native suites, 26 SDK observations, 1,135 exact Git source records and both actual RNA/manifest ZIPs. The run took 7m21s; this source-tree scope does not execute the new installed four-slot gate. Audit proof `work/policy-component-composition/generated/hosted-development/37542367988/inert-audit-proof.json`, SHA-256 `7c18ad24cbf3c95baab9d71ec73ebe435e98ebce1e92c384c71c990841591e38`. Source-review proof: `work/policy-component-composition/generated/component-installed-integration/root-review.json`, SHA-256 `9f6d14aaeafeb72a0e4360830a7693e5cb091084051b8ce95b5a501b106e020f`. The exact macOS runtime bootstrap is now validated and merged into the component branch; full installed/release acceptance awaits fresh hosted checks |
| Current integrated PR85 candidate | H `5717cb28885957e07f4f58805160bdc888f42b01`; tested C `0b4cf661b24bc52e5527447ff79d0ae9599e0f93`; shared tree `634b7865e2b8ce6dafee0e0206ccbd0d6ac4c3b0` | [Fresh full run 37545710899](https://github.com/logannye/biocompiler/actions/runs/37545710899), attempt 1, remains active with a confirmed macOS static-GMP build failure after successful Python bootstrap. The extractor discarded upstream timestamps, making the bundled manual appear older than its inputs and triggering unavailable `makeinfo`. Linux native build passed; healthy remaining jobs continue. Failure diagnosis SHA-256 `082637fdd29331b036b2d156d4a86d3be4b8f9655b2d88d299901c400cdfd11d`. This run cannot supply full acceptance. It began after an ancestry-checked, leased fast-forward of PR85. It combines the reviewed bootstrap and reusable-component installed campaign in one coherent gate: all 74 jobs, 59 receipts, 156 native suites and four installed slots remain required. The strict component-profile plan is prepared with tool `1c67b5b3c`; plan SHA-256 `77fa9086d6de2138065939d5e746eca25af94bccd1cf29f3b674a0396a6a8bca`, preparation proof `e3b5f93ca115d2ae4ce4b320029cb91cf7064088ea987d76f7bd7736b88cc6f2`. Source H and tested C have equal trees and ordered C parents `[f594991ac, H]`. Check-suite predecessor `affe77625` is separately authenticated as the prior component source; PR85 advanced from `8c61f45af`. Preparation, development checks and bootstrap success do not accept this run. Normal merge and fresh actual-main validation remain required. |
| Separate PR95 policy head | H `bb84421cf1f93cd1dc02813d80a2c54a3520a919`; C `4fe47eb1aa69782a03723fda2df892985b4e7328`; shared tree `889583e44a9de598a32beb4154f42c0471e4be83` | [Run 37450940506, attempt 1](https://github.com/logannye/biocompiler/actions/runs/37450940506): all 42 hosted jobs succeeded; independent final artifact audit passed for its stated scope. Normal union integration and fresh main acceptance remain pending |
| Current main baseline | `f594991ac2ff2496723ae5f2427ad93e6df7a51d` | PR88 is merged; the policy/material/package union has not yet been merged or main-validated |

The current union workflow has 27 definitions / 74 executions / 59 ordinary
receipts, all 149 native suites and 67 direct groups per platform, and 20 installed
group jobs covering 17 campaigns in each of four runtime slots. Historical
42-job PR95 or 68-job PR85 gates do not accept this union. The unit plans/results
must independently account for every discovered test; the focused 416-test
preflight is not the full unit suite.

The current union's scoped unit audit has passed at
`acceptance-37471505350/unit-scoped-audit/unit-scoped-proof.json`, SHA-256
`bc586f1b94044840c5b70f36e9ff81a490711b962910aef4b28d565b668d391f`.
Python 3.11.16 and 3.14.7 each account for all 4,063 tests, 431 classes and
26,705 retained subtests across shard counts 676/857/818/826/886. Both complete
124,731-file source inventories, plan/discovery/result/accounting digests and all
14 artifact producer identities were independently checked. This scoped proof
does not replace the remaining installed, aggregate, merge or main gates.

The current union's scoped native audit has also passed at
`acceptance-37471505350/native-scoped-audit/native-scoped-proof.json`, SHA-256
`ae33595d3100be2018220304d8dcc82c26ee43aa7dce0486a6180f9d3a09eeca`.
The audit binds both 151-executable / 23-fixture bundles, all 149 suite and 67
direct-group records per platform, and published Core/Verify bytes to the exact
source/tested tree, run and six successful producer jobs. It rechecks 124,731
source pins and 14 retained archives without extracting or executing native
programs. The complete release and actual-main gates remain open.

Retained local evidence lives under
`work/m11-human-evidence/generated/migration-next/pr85-pr95-union/`
(preflight pair `preflight-unittest-passed-pair-a85b1112f.json`, guarded original
build/continuation proofs, current `acceptance-37471505350/` checklist and hosted
snapshots, including `hosted-progress-native-focused.json`, `hosted-progress-native-complete.json`, `hosted-progress-units-complete.json` and `hosted-progress-campaigns-running.json`). Earlier-head scoped proofs live under
`work/bounded-policy-execution/generated/policy-realization/acceptance-37450940506/`
(unit, platform, `prebuilt-scoped-proof.json` and `six-comparisons-scoped-proof.json`). These generated records remain
evidence with the stated scope, not substitutes for full acceptance.

The later 71-success snapshot is retained in
`acceptance-37471505350-cap640/hosted-gate-20261006T170503Z/`.
All installed groups and four assemblies passed; reproducibility remains active
and the final prebuilt/aggregate gates remain. No timeout, failure or retry of a
hosted validation job is inferred from its active state.

The last complete job snapshot at 17:40:45 UTC still had 71 successes, one active
comparison and two not-yet-materialized final jobs. Later run reads through
18:06 UTC report `in_progress`; the attempt-specific jobs endpoint returned
HTTP 502, so those reads do not establish fresh job counts. This is an API
acquisition failure, not a hosted test failure. The reproducibility job has no
explicit workflow timeout; the 120-minute setting belongs to a different job.

At 18:26 UTC, the run and exact reproducibility-job endpoints recovered narrow
progress: continuation comparison step 23 passed at 17:42:39, registration step
24 passed at 17:43:19, and the final four-slot original-reference comparison
step 25 remains active. The authority-checked run/job proof is retained at
`acceptance-37471505350-assembly-bounds/hosted-progress-20261006T182500Z/progress-proof.json`,
SHA-256 `ea8ea68102061b2023e180282518030d3e7ec3c19992785a069c3556d25e886e`.
This narrow historical read did not refresh the complete 74-job census or
establish final acceptance. At 18:39 UTC the complete census recovered: 72 jobs
succeeded, prebuilt validation is active and the aggregate is pending. Its proof
is `acceptance-37471505350-assembly-bounds/hosted-progress-20261006T184000Z/progress-proof.json`,
SHA-256 `486b0cbca6ada3b8d8cef97fd0e3d0e8900bd1decd560b609c7cb21747801205`.
At 18:43 UTC, 99 of the 102 expected archives are available and authenticated;
the two prebuilt receipts and aggregate receipt remain pending. This is still
not the final artifact audit. The 18:55 UTC final snapshot then confirmed all
74 jobs successful and all 102 selected archives available. Complete run/jobs,
raw commits, check suite, nested/live PR head/base and artifact metadata were
captured before head advance. The final packet is
`acceptance-37471505350-assembly-bounds/hosted-progress-20261006T185500Z/final-authority-packet-proof.json`,
SHA-256 `f78a4904f9c07b00098c3b7da9df3a50f8ccf1a3338103f5149f2447ee771f9a`.
Root rehashed the packet and all captured inputs. The old auditor has no later
live-PR dependency; it remains bound to the unchanged local a85 checkout and
captured authority while the corrected head can begin fresh hosted validation.
The independent final a85 audit then passed with all 102 archives, 59 ordinary
receipts and 14 unit artifacts accounted for. Its proof is
`acceptance-37471505350-assembly-bounds/final-audit-output-20261006T185900Z/proof.json`,
SHA-256 `18822e1667c5a814461f00b544be52f1f5749a1016b823bb22eb03a9e6ffedcd`.
It retains both native bundles, all original campaigns/comparisons and exact
four-slot package/material correspondence. Large legacy replay semantics remain
hosted-gate evidence with independently checked receipt identities; the local
audit executed no native code. New head 510ba5fe8 requires its own fresh audit. The intervening f4dca4f29 run failed preflight and supplies no acceptance.

### Faster development feedback

The full 74-job release workflow is a release boundary, not the inner editing
loop. The new `policy-development.yml` runs only for `codex/dev-policy/**`
pushes: one hosted Linux build and focused component/preservation/material/
construction suites. It records exact source/run/fixture/binary identities and
failure logs in a separate development artifact with `acceptance: false`.
It neither changes required release checks nor cancels a release run. The
first observed feedback time was 2m41s from run creation to job completion:
43s dependencies, 30s compilation and 35s native suites. The later ten-suite assembly-rule run completed in 3m32s, including queue time.
These observations do not guarantee later runtime or substitute for release coverage.
The eleven-suite lane passed in 2m11s with independent assembly checking. A failed
first attempt caught an overly broad alpha-renaming test helper; the narrow
correction changes only node references, preserving input kinds and link names.

Continue independent source work while full acceptance runs. Batch coherent
source changes, focused tests and tracker updates at useful implementation or
validation boundaries. Reserve the full cross-platform/installed/packaging
campaign for release candidates and required correction batches. The index
reconstruction correction below reduces known redundant work; its runtime
benefit still needs measurement on the corrected hosted head.

Prioritize the complete two-policy reusable-component vertical slice through
selection, assembly, independent checking, exact mRNA and fresh export before
alternatives, helpers or multiple members. Keep three roles focused on
implementation, independent tests and release validation. Share independently
authored fixture literals and common test plumbing, while retaining separate
coverage expectations. Promote recurring release auditing into stable versioned
tools so each run needs only authenticated inputs, a plan and results.
Measure time to hosted native feedback, vertical-slice completion and the
full-release critical path; update this tracker at meaningful boundaries.

The complete two-policy source-tree SDK path took about 5m45s in run
37527311912 and 7m17s in the later registration run 37531033330, including one
native build and sixteen suites. These measured times vary with hosted execution. The next acceptance
batch will reuse the existing four installed Linux/macOS × Python slots and
standalone offline harness. It needs a separately scoped component campaign,
original domain-only fixture data, complete cross-slot outputs and actual paired
ZIP checks; existing whole-graph receipts cannot be relabeled. No production
resolver or new packaging API is currently required. The fresh registration
proof is `work/policy-component-composition/generated/component-release-readiness/root-integration.json`,
SHA-256 `33fc6aaf92e92b851d06e02336b53ff4debe7bbcf850bc0255ad36c1d93306c8`.

The stable audit tools are now committed and pushed at `832ceb98ccc4ad7bb29e2f4ed5673dfd3365e4d9` in `work/release-audit-tools`. They preserve the prior identity/receipt/archive semantics and reject changes to source, tool revision, plan seal, declared scope or job evidence. The reviewed profile remains the 74-job/149-native-suite release scope; a later component release needs an explicit reviewed scope update. Clean CLI proof SHA-256: `f28db7d0dd922d9083d41cb3fdb9ca9193d2e3ed18cbfa6b243cd84913633a88`. A subsequent reviewed profile-only update at `129bcd7d73edb9e3195bb953d446b88ec96c9a47` binds the supported-runtime workflow and three added comparator setup steps; all thirteen tooling tests passed on both versions, including fifteen new rejection controls, with every acceptance algorithm and scope unchanged. New release runs need inert plans and authenticated evidence, without copied audit helpers.

A separate source-cost review identified repeated reconstruction of the same
two immutable source indexes inside each row of original-counterpart validation.
For the retained 343-row case, one call reconstructs the index pair 345 times;
the 16 required validations therefore canonicalize 41,456,944,320 input bytes.
This is a static operation count, not measured disk traffic or a runtime estimate.
The review is retained under the authenticated assembly-bounds preparation at
`cost-review/step23-cost-review.json`, SHA-256
`26214592cf8698e782d6803a51a36fe35d783522afa5ada7f9eee44d6dd52ecd`.
The isolated source correction `360e2cbbd` in
`work/original-source-closure-snapshot` captures a
per-call entry inventory and repeats fresh closing source/data/route checks.
The 343-row fixture now reconstructs the index pair four times per call, with
independent repeated calls. All original row/hash/substitution/origin/module
checks and top-level validations remain. No cross-call cache, cached acceptance,
comparison removal or active-run edit was introduced. An additive exact
predecessor proof preserves all four existing historical witnesses byte for
byte. Review caught and corrected an early-hook error-ordering regression;
the unchanged old proof-authentication tests now pass.

Both Python 3.11.15 and 3.14.6 pass all 22 focused tests, with the same 15-file
closure unchanged before/after and process/network execution denied. Two
unchanged policy restoration methods separately pass on Python 3.11.15.
The combined proof is `generated/closure-snapshot/combined-pair-proof.json`,
SHA-256 `cbb7828a4ae96478d2e0272d4c0fdc9665508f3b299f0219917b0c28d922c2d1`,
and the independent final lineage review is
`generated/pipeline-counterpart-closure-review/final-lineage-review.json`,
SHA-256 `da401d1879d754c253e3841c6d4e665789c701cc82f39cbcba2eb783d785dd5e`,
both in that isolated worktree. These are source/synthetic checks; no original
semantic replay or native execution was performed locally. Entry/closing reads
do not claim an atomic filesystem snapshot or detect transient edits restored
between reads. The corrected source requires its own full hosted acceptance.

The original archive preparation and its digest are preserved. A separately
reviewed 640 MiB compressed cap accommodated the four roughly 571 MB assembly
ZIPs. Their complete downloads match API hashes/sizes, but each has about 280,000
entries and 4.16 GB declared contents, exceeding the unchanged entry/expansion
caps. The audit correctly rejected them; successful transfer is not acceptance.
All 97 currently available selected archives total 3,194,331,402 compressed bytes
and 18,327,041,494 declared expanded bytes. A separate preparation is now independently reviewed and authenticated for
bounded 300,000-entry / 4 GiB-per-archive / 20 GiB-aggregate inspection; its
external manifest is
`e754c03a98b50368677c91a5e66375eacfec1aacecc29d11017dbe0dc09be83d`.
All 97 available archives then passed complete size/hash/path/member/CRC
validation without redownload, extraction or native execution. Proof
`available-downloads-20261006T171143Z/download-proof.json` under that preparation
has SHA-256 `9af34c56733539fc5b2e0cae03712707a8fc93dfb64497d54e94d3d1657688ca`.
Five final selected archives and the full final audit remain pending.
Compressed-total, per-member, actual-extraction and nested-native limits remain
unchanged; no complete assembly corpus is to be extracted. Final auditing still
requires authenticated preparation, complete hosted success and fresh metadata.

Actual-main audit preparation is retained separately in
`actual-main-identity-controls/independent-review.json`, SHA-256
`dc5b917760fe884ebb62a6dd0aa5f0ef5e3e6e082041c84f27cf615be96598b9`.
Its reviewed helper distinguishes source/tested identity `M/M` from ordered
normal-merge parents `[previous main, accepted PR head]`, and binds the Git
commit, main ref, merged PR, push run and suite to the accepted tree. The caller
must first authenticate all expectations and helper bytes independently. The
four positive / 83 negative controls use fictional identities; actual `M`, its
push run and all fresh main artifacts remain absent. Optimized Python execution
is rejected before test assertions can be disabled.

PR95's final independent proof is retained at
`final-refresh-20261006T144143Z/final-audit-output/proof.json`, SHA-256
`d331a734c0b863ba4a4e228c66bc260f54113368925634850baeace907be05cd`.
It binds all 42 jobs, 27 ordinary receipts and 53 selected archives to the exact
PR95 source/tested tree above. Each of Python 3.11.16 and 3.14.7 accounts for
2,937 tests, 14,058 subtests and 282 classes with no omissions or duplicates.
Large legacy semantic reconstructions remain mandatory hosted results; the inert
local audit does not claim to rerun them or any native executable.

The 16 partial contextual families are coverage/scope gaps, not a count of
missing compiler stages. The original 486-history request remains incomplete
under its unchanged work bound and cannot export; the separately declared
54-history success has distinct authority. See
[policy-material-acceptance.md](policy-material-acceptance.md) for profile limits.

The descriptor review found three missing distinguishing tests, rather than a
missing production guard: the previous wrong-digest test used malformed text,
and non-effect formals / non-observation results lack direct rejection witnesses.
`descriptor-identity-reachability-a85b1112f.md` records the exact paths, source-valid
mutations and shared guards across eight signature contexts. A separate follow-up
worktree now contains the reviewed test/ledger commit `82c6fa57f` on
`codex/policy-descriptor-witnesses`. All 42 focused pure-Python coverage controls
and the unchanged 3,731-entry migration inventory pass; no production pins or
coverage statuses changed. Native execution and exact-revision acceptance of
these three new controls remain pending. This follow-up is not included in the
currently tested PR85/95 source trees.

Tracker edits are maintained in the isolated `codex/semantic-mrna-tracker`
worktree while both tested source trees remain frozen. Include these documentation
updates in the next coherent integration batch; do not restart a healthy run
merely to publish a progress note.

Completed follow-up source work, with full hosted acceptance still pending:

- **SM-01.3:** a bounded API ledger and independent drift checker now cover 700
  authored AST rows across 32 primary files and six boundary/dependency files,
  163 explicit exports, all 20 public builder methods and two mutable builder
  attributes, six patterns, 17 CLI commands and 13 native operations with exact
  input keys. Ninety witness anchors retain their reviewed roles; 97 rows remain
  explicitly `source_only`. Independent metadata pins reject unrelated-witness
  substitutions and unsupported coverage promotion. Inherited/generated runtime
  attributes and per-body semantic coverage are outside this authored-AST census.
- **SM-01.1b:** the source unit/scope ledger and drift checker now index 40
  reviewed kernel rows and 43 caller contexts against 13 source/dependency pins.
  All 29 static/adversarial controls pass on Python 3.11.15 and 3.14.6 with product
  imports, subprocesses and network denied. Python authoring and native source
  assessment retain distinct enforcement boundaries. This closes the bounded
  source-index implementation, not the whole-stack rule census or its semantic
  witness obligations.

The final API/builder/pattern/boundary test pair passes **55 tests on each of
Python 3.11.15 and 3.14.6**, against the same 56 input hashes, with subprocess and
network denial checked. Its proof is
`work/policy-descriptor-witnesses/generated/policy-api-coverage/final-typing-pair.json`,
SHA-256 `9829748180c3e9b4e08137d2475118658acd7e52cc66d89a483cd87788a41674`.
The source-context frozen manifest is
`generated/policy-source-context-witnesses/frozen-manifest.json`, SHA-256
`e65977ebb050d70301c2b57ad1384899e219d5ca1445abdc4a00c701c10ed419`.
The type-preserving builder precheck also passes strict typing across all 28
policy files. All eight existing wire/operational/material fixture checks, the
material-rule ledger and Core/Verify dependency-boundary checks pass without
native execution. The migration inventory preserves all 3,731 IDs and all 59,072
existing test links, adding 300 links; its only non-reference field change is the
corrected builder module digest. These are focused Python/static results, not
native execution or release evidence.

These reviews are retained under
`work/m11-human-evidence/generated/policy-realization/source-api-census-a85b1112f/`
and `work/m11-human-evidence/generated/migration-next/pr85-pr95-union/sm01-contextual-census/`.
The latter includes three unexecuted source-stage counterexample specifications
for persistence durations, state-reset ownership and message correlation
ownership. They describe stage differences, not established production bugs or
new executable support. Neither review changes either frozen validation subject.

The two reproduced builder defects have separate evidence at
`work/m11-human-evidence/generated/policy-realization/frontend-builder-edge-review-a85b1112f/`.
Their correction prechecks both encounter records before mutation and checks
the original record's ownership before namespace copying. All six new boundary
tests pass on both interpreters in the final 55-test pair above; full hosted
validation remains pending. The initial local selection also
included the historical cross-process digest test, which its process-denial
guard blocked; that mixed 24-test run is **not** a complete passing receipt.
Retain that historical test unchanged in the required hosted suite.

Earlier milestone preparation and diagnostic narratives are preserved in the
[development history](semantic-mrna-development-history.md). The following
starting-point inventory is historical. Use the
current source checkpoint and each task's exit condition to decide what remains.

Historical implementation baseline: f5564f251dcf62627769bb0f855802c315e75dd8, branch codex/bounded-policy-execution, worktree work/bounded-policy-execution. Development base: pushed PR88 revision 88421d068ebc8437d6d0d4fa1a1bfdb32f150883. The following foundation inventory records that starting point; later source and acceptance checkpoints appear under their milestones.

- [PR89](https://github.com/logannye/biocompiler/pull/89) contains the new bounded operational profile.
- [Run 37401642752](https://github.com/logannye/biocompiler/actions/runs/37401642752), attempt 1, passed native compilation, native literal/mutation suites and installed operational Python 3.11 campaigns on both Linux x86_64 and macOS arm64 at the last read-only review.
- Complete acceptance remains open. The observed Python 3.11 shard failed because the workflow source census rejects the new core_policy_operational.py addition as unreviewed. Other gates must be refreshed before claiming their status.
- Source review also found that requirement support classification accepts effect_event without validating its lifecycle phase. This is an SM-00 correction, not an accepted behavior.
- Existing source-only assessment/replay and operational operations retain their current claims and protocol versions. New implementation/material acceptance will use separate versioned profiles.

| Existing foundation | Reuse | Remaining boundary |
| --- | --- | --- |
| [Python policy model](../src/biocompiler/policy/model.py), [builders](../src/biocompiler/policy/programs.py), [serialization](../src/biocompiler/policy/serialization.py) | Existing declarative vocabulary, BuildRequest, Deployment, ImplementationCatalogLock and AssuranceRequest | Field-level executable/material support and complete public routing |
| [Operational domain](../core/lib/domain/policy_operational.mli), [lowering](../core/lib/compiler/policy_lowering.ml), [correspondence](../core/lib/checker/policy_correspondence.ml), [execution](../core/lib/semantics/policy_execution.ml) | Supported source meaning, full source/requirement retention, reference execution | Independently reconstructed implementation semantics and material binding |
| [Architecture refinements](../core/lib/domain/architecture_refinement.mli), [checker](../core/lib/checker/architecture_check.ml) | Component/template/placement identities, helpers, RNA cardinality and declared availability | Current interfaces consume legacy Behavior.t; rich-policy mappings and nonempty resource/domain acceptance are missing |
| [Candidate runtime](../core/lib/candidate_runtime/components.mli) | Independent execution/reconstruction pattern | Rich-policy uncertainty, scoped state, correlated attempts and exact timing |
| [Construction producer](../core/lib/compiler/construction_producer.mli), [checker](../core/lib/checker/construction_check.mli) | Exact molecular construction, chemistry, coordinates and fresh replay | Complete checked policy-to-implementation-to-material chain |
| [Architecture export](../src/biocompiler/compiler/payload_architecture.py) | Fresh verification and paired FASTA/manifest export pattern | A dedicated rich-policy request and acceptance profile |

Current ownership: this session is the sole integration owner. PR88 main and
PR95 are integrated into the frozen PR85 union described in section 2. Preserve
all original branches and continuation worktrees. The reference-package route
already implements prepare/build/reconstruct/publish/export; its compatibility
and hosted acceptance now run within the combined gate. Do not recreate it or
transfer historical acceptance. Recheck identities and ancestry before any
further integration.

This plan controls the session's priorities. The existing product and migration roadmaps retain historical acceptance records and separate release obligations.

## 3. Architectural decisions to hold fixed

### 3.1 Keep the complete original request authoritative

The root request contains the original frozen policy, exact definition bundle, deployment/context declarations, implementation/material catalog locks, assurance request, operating domain and compiler/checker profile identities.

Reuse existing source records when their meaning fits. Add closed native representations and versioned envelopes for missing executable meaning. Do not create another broad Python language or silently convert rich policy into the older BuildRequest/Behavior family.

Every consequential field must be interpreted, checked as a declared premise, or explicitly rejected/unresolved. Retaining a field in JSON does not mean its obligation has been discharged.

### 3.2 Introduce three distinct implementation-side representations

The table below defines the target representation contracts. Current versioned
native and Python interfaces implement the bounded scope listed above;
preferences, reusable composition and delivered helpers remain later milestone
work. Release acceptance is tracked separately from interface presence.

| Representation | Required content |
| --- | --- |
| PolicyRealizationRequest | Complete original authority, admitted operational profile, finite operating domain, supplied implementation and material libraries, hard requirements, preferences and budgets |
| PolicyImplementation | Typed executable primitives/netlist; ports, wires, state encodings, timers, scheduling, atomic groups, arbitration, encounter/attempt encodings, configuration and source occurrence map |
| PolicyMaterialBinding | Exact relation from implementation instances/configurations/connections to component versions, sequence-template members, features, chemistry, placements, helpers and products |

The implementation IR must perform a real decomposition into independently executable operations. An opaque “execute this source policy” node, renamed source AST or copied source ledger is not implementation lowering.

New candidate values are untrusted. Only separate checker-owned constructors produce checked realization/material states. Re-decoding a serialized PASS must never reconstruct acceptance by itself.

### 3.3 Keep authoring, producer, execution and checker responsibilities separate

- Python builds inert declarations, freezes inputs, negotiates native profiles and transports immutable results.
- Source semantics remain in the OCaml operational reference implementation.
- The lowering producer proposes implementation operations, bindings and material choices.
- Candidate execution reconstructs operations, wiring and parameters from actual locked candidate contents. It cannot obtain behavior from the source evaluator, expected trace or producer.
- Independent checkers consume original external authority and actual candidates, reconstruct correspondence, and own acceptance.
- Existing material producers and checkers are reused behind a policy-specific binding layer. Legacy APIs remain intact.

The trusted base explicitly includes bounded decoding, exact arithmetic, canonicalization/hashing, the chosen source/primitive semantic definitions and supplied model-to-sequence contracts. No claim of independent verification may conceal shared producer logic. Hashes establish identity, not behavioral correctness.

### 3.4 Define preservation before implementing the producer

Initial profile: deterministic, exact-clock observable equivalence after a declared projection, within an explicit finite operating domain.

The projection is fixed by independently supplied profile/library authority and is total over potentially observable implementation/component ports and events. The producer cannot hide an extra effect by labeling it internal. Hidden-step classifications are checked against that authority.

For each admissible input history, the implementation's projected observable trace must equal the source trace modulo an explicit injective generated-identity correspondence. Both directions are required: no required event may disappear and no extra observable event may appear.

Pair environmental inputs causally across the two executions. Extend the identity correspondence when matching encounter/attempt creation events occur, then translate correlated feedback through that fixed correspondence. Specify valid, stale and unknown feedback classes. Divergence is a counterexample; it must not narrow the admissible histories, permit retrospective identity remapping or discard feedback that exposes a mismatch.

Preserve:

- Source declaration and occurrence identities; executor, subject and encounter generation; initiating occurrence and correlated attempt/feedback lineage.
- Three-valued truth and separate missing, stale, invalid and conflicting evidence.
- Exact observable timestamps, ordering and multiplicity; observation time versus availability time; equal-deadline precedence.
- Atomic reads/writes, initialization, reset, arbitration, state scope and capacity behavior.
- Required lifecycle events and distinction between request, initiation, completion, failure and timeout.
- The source profile's stated observation boundary, including settled-tick safety rather than a silently stronger or weaker interpretation.

Allow only explicitly hidden, bounded internal microsteps at the same logical time. They cannot create/remove observable behavior, consume unaccounted time or permit divergence. Provide a bound/ranking argument for internal settling. Initial observable latency tolerance is zero. A later latency/refinement profile must declare permitted delays and prove deadline preservation; it cannot relax timing merely to accept a candidate.

Extract a typed incremental source-transition interface if the checker needs it, while preserving current reference outputs against independent literals. Do not create a second competing source authority during this refactor.

### 3.5 Make the operating domain executable

Finite storage capacity is not a finite value domain. Admission must state and check:

- Allowed observation values and evidence-status classes; exact time grid and horizon.
- Initial state, finite integer/enum/text domains, storage capacity, counter widths and overflow policy.
- Maximum live encounters, generations, attempts, queued events and internal steps.
- Legal simultaneous input batches, reset/end schedules and feedback outcomes.
- Which inputs are environmental, which outputs are implementation-produced, and how they are observed.
- Closed predicates for any required timing, feedback, availability or environment premises.

Prose assumptions are retained but cannot prune the explored domain or justify liveness. New premises cannot be invented by the producer. Library preconditions must be entailed by the original supplied request or reported as unmet. Empty/contradictory domains fail; relevant trigger and active/inactive witnesses must be exhibited.

Executable environment premises must describe a causal input process. Future feedback may depend on prior matched requests, but premises cannot constrain implementation-owned outputs or exclude bad candidate behavior. Require a nonempty permitted continuation at each reachable prefix, or an explicit environment termination/end rule. Even a user-supplied premise cannot circularly establish the implementation response being checked.

Use exhaustive reachable exploration for the first small finite profile. Retain the domain identity, transitions/case census, bounds and counterexamples. Any abstraction or equivalence-class reduction requires a separately checked justification. Resource exhaustion yields incomplete/unknown, not PASS or infeasibility.

A passing finite timeline is regression evidence. A complete bounded-domain result is a stronger, separately named result. Neither becomes an unbounded theorem. Inductive proof beyond the declared horizon is a future profile.

### 3.6 Separate preservation, requirements and export eligibility

A faithful translation may preserve a program that violates its own requirement. Report these independently:

1. Source validity and operational admission.
2. Source-to-implementation correspondence.
3. Preservation over the declared domain, with complete/incomplete coverage.
4. Each hard requirement's pass/fail/unknown/unsupported result and witness.
5. Declared implementation/deployment compatibility.
6. Complete material construction and correspondence.
7. Fresh export eligibility.

Hard semantic requirements must pass for complete accepted export; unsupported or unresolved hard requirements block that claim. Preferences rank eligible candidates only. Biological evidence/use status remains separate and is not a prerequisite for the semantic software artifact.

Export must also satisfy the original AssuranceRequest: requested requirement identities, assurance strength, domain/horizon, tolerances and allowed assumptions. Unknown/duplicate requirement references and unsupported assurance levels reject explicitly. A bounded result cannot discharge an unbounded request; a producer cannot shorten the domain, add assumptions or relax tolerances to obtain acceptance.

Define per-history “not exercised” separately from unknown semantics or missing evidence. The new bounded-domain requirement checker must establish the response for every eligible trigger and retain global nonvacuity witnesses; it cannot manufacture proof by relabeling old per-timeline UNKNOWN reports.

Unverified candidates and diagnostics may be inspected, but must not enter the accepted artifact/export path.

### 3.7 Material correspondence is an explicit supplied contract

A material library entry binds an implementation model and supported configuration to exact sequence/feature/chemistry authority. Model and material authorities are supplied independently of candidate generation.

Check that every selected executable operation, required helper and connection has a complete implementation/material disposition. A claimed implementation connection must have a supplied encoding/composition contract; it cannot exist solely as a convenient manifest edge.

Independently reconstruct selected component transition models and their composition. Interface signatures and parameter names alone do not preserve behavior. Establish their exact semantic correspondence to the checked implementation, or rerun preservation against the reconstructed assembly. Substitutions affecting behavior, state, scheduling or wiring invalidate the prior result.

A configuration may affect emitted bases, select a different template, or remain a non-sequence part of the explicit contract. Each case must be declared. Every executable non-sequence value needs a carrier: a modeled host/environment input or an explicit supplied configuration resource checked against the original deployment. A timer or threshold present only in a manifest is unresolved. Changed source may legitimately yield identical RNA only after fresh checking establishes that the complete unchanged implementation/material contract still satisfies it. RNA equality alone is never acceptance.

Exact bytes cannot, by themselves, prove the supplied model-to-sequence axiom. This phase checks derivation and consistency under that explicit axiom, without requiring empirical viability.

## 4. First complete profile and witnesses

Proposed initial policy-realization profile:

- One executor role and at least two independently represented encounter slots in the accepted witness.
- One exact logical clock; finite horizon; observed/available timestamps and silent ticks.
- Truth-valued evidence and finite scoped state; declared finite machine states and fixed typed parameters.
- Explicit exclusive/priority arbitration with atomic assignments.
- One product-bearing effect family; fresh correlated attempts; completion, failure, timeout and reset/end handling.
- Initiation and continuous-authorization behavior exactly as currently specified. No implied cancellation, cessation or reversal.
- A frozen independently authored finite-state implementation library and exact mRNA template/member set.
- Explicit finite capacity, recipient/compartment, helper and material-count contracts.

The material-compilable profile may initially be narrower than the operational profile. Every excluded combination is diagnosed before accepted material generation. Arithmetic expansion, multi-observation coherence, coordination, quantification, spatial relations, inheritance and new cancellation semantics require later complete profiles.

Freeze three witness families before producer development:

| Witness | Required purpose |
| --- | --- |
| Positive compilation | Original Python request with two encounters, exercised guarded activity, scoped state, at least one nonvacuous progress obligation and complete supplied material authority; all requested hard properties hold on its declared domain |
| Semantic rejection | Source violation, unsupported source/requirement, missing implementation, conflicting premise, insufficient capacity and exhausted search each produce distinct expected outcomes |
| Preservation/material mutation | Near-neighbor source, implementation, wiring, parameter, recipient and sequence changes invalidate old acceptance or produce independently justified revised results |

For the initial positive progress witnesses, use properties that the supplied semantics actually guarantees: requested-to-initiated response within its declared bound, and a rising known observation predicate leading to an effect request within one tick through an uncontested enabled rule. The latter must expose a candidate that deletes both request and initiation. Completion is not guaranteed when environmental feedback may be absent or fail. Cover completed, failed and timed-out outcomes separately; a request demanding guaranteed completion must have an explicit adequate premise/model or receive an unmet requirement result. Freeze meaningful safety/guard/state invariants and their distinguishing counterexamples alongside the progress witnesses.

Artificial exact sequence fixtures are sufficient for software tests under explicit supplied contracts. They remain labeled fixtures. Templates for the accepted mRNA path must meet the chosen complete structural mRNA profile, including required regions and declared chemistry; short arbitrary alphabet strings are not a substitute for that profile's structural completion.

Freeze that completeness predicate before fixture acceptance: complete sequence extent, exact molecule/member and tail realization, required regions, product translation and junction authority, and resolved chemistry declarations or explicitly permitted absence/inapplicability. Existing core-only, bounded-tail or unknown-chemistry construction results cannot automatically establish complete exact-mRNA acceptance.

## 5. Ordered work packages

Checkboxes mean completion of the stated task for its declared profile, supported
by the relevant evidence, not merely source written. Specification or
implementation tasks do not wait for unrelated release gates; a checkbox that
explicitly requires installed, aggregate or main acceptance stays open until
those gates pass. During work, record source-ready and hosted-pending checkpoints
separately. Stable SM identifiers are the session to-do IDs; lettered subdivisions
preserve the completed and remaining portions of a mixed-scope task.

The 2026-10-06 SM-00–04 reconciliation is retained in
`work/m11-human-evidence/generated/policy-realization/tracker-sm00-sm04-review-a85b1112f.md`
(SHA-256 `a5e31097099ea42bf57bd39b80786528fc2fd4c23a6aa2aaab621cc7faf7dfb9`).
It records exact source/test anchors and the boundaries summarized below. Native
component evidence for unchanged files and the current union's completed native
jobs support these narrow tasks; neither transfers aggregate acceptance between
revisions nor closes incomplete coverage inventories.

### SM-00 — Close the current operational foundation

Depends on: existing PR87–89 source and verified accepted-main ancestry; preserve the original PR branches during integration.

- [x] **SM-00.1** Refresh local/remote identities and current hosted failures; retain exact diagnostic evidence without taking over PR85/87/88.
- [x] **SM-00.2** Review and register all new source additions/lineage changes in the frozen workflow authority machinery; preserve original comparisons and rejection controls.
- [x] **SM-00.3** Restrict requirement event support to implemented lifecycle phases. Add source-valid cancellation/ceased/outcome negative controls, retaining UNSUPPORTED rather than invented FAIL/PASS.
- [x] **SM-00.4** Audit admission/execution agreement for requirement scopes, reset/order, partial horizons, unknowns and resource limits. Repair concrete gaps in one coherent correction batch.
- [ ] **SM-00.5** Complete exact-revision hosted native, installed four-slot and aggregate gates. Update existing operational checkpoint evidence only when justified.

Current task scope: SM-00.2 closes reviewed registration at `a85b1112f`, with the
49-selector/416-test preflight and byte-exact historical source proofs. SM-00.3
retains source-valid unsupported lifecycle phases and rejects forged promotions.
SM-00.4 closes the focused audit and repairs for the named scope/correlation,
reset/feedback order, partial horizon, Unknown and resource-limit cases. It is
not universal coverage of every admitted combination; that remains SM-01/08.

Exit: the operational dependency is accepted for its declared scope; existing source-assessment contracts and legacy profiles remain unchanged.

Correction checkpoint: run 37401642752/source f5564f251dcf62627769bb0f855802c315e75dd8
tested merge 74ec0ee383a57dea74c00e6ada67846f7e918348. Inspected unit failures
share the unreviewed operational source-registration cause. The correction
preserves the original corpus and adds requirement-phase, expression-retention
and correlation controls. Source registration passed 24 focused Python tests,
including complete independent recapture against unchanged frozen bytes;
native corrections still require hosted validation. PR88 advanced to
5f9b39d354b43070f15114f2e8813e659ab1c4a4 through two merge commits with no file
changes. Its owner's branch and checks remain untouched. Retained diagnostic
details are in the [SM-00 diagnostic review](../protocol/policy-operational-sm00-review.json).

The first correction was pushed in PR89 at
`474b924fcf86d7399c4856260fd630733b934eed`, with source changes in
`a2ee388235536f55aefa5f798af1ddc2d43fdc95` and the unchanged-file PR88 merge.
[Run 37406813336](https://github.com/logannye/biocompiler/actions/runs/37406813336),
attempt 1, has passed native compilation, all native literal/mutation tests and
installed operational Python 3.11 checks on Linux x86_64 and macOS arm64 at the
latest read-only review. Full installed/four-slot/aggregate acceptance is still
pending at that snapshot. Python 3.11 then exposed AST-display fingerprint drift
in the coverage ledger. The portability fix, preserving every reviewed source
distinction and support disposition, is pushed as
`72b0ffcc3ab134e3880b0171d14b9d8bcc58e19b`;
[run 37409588377](https://github.com/logannye/biocompiler/actions/runs/37409588377)
is its new attempt-1 validation. All 25 coverage tests and the complete inventory
agree on installed Python 3.11, 3.12, 3.13 and 3.14. Subsequent SM-01/02 source work
is isolated on the stacked
`codex/policy-realization-contracts` branch so it does not cancel that run.

### SM-01 — Freeze source coverage, complete authority and acceptance fixtures

Depends on: source interfaces already present; final acceptance follows SM-00.

- [x] **SM-01.1a** Create the complete machine-readable syntax inventory: 612 distinctions covering source records, fields, expression operators, enum/lifecycle branches and requirement forms.
- [ ] **SM-01.1b** Complete the individual contextual unit/scope-rule inventory. The existing 62-family matrix is not yet a rule-by-rule ledger; for example, quantity-only unit ownership and positive unit scale still share a family disposition. These inventory gaps are separate from SM-01.2 witness gaps.
- [x] **SM-01.2a** Represent authorable, structurally checked, native-assessed, operationally executable, implementation-lowerable, material-bound and exportable as separate stages.
- [ ] **SM-01.2b** Complete every restriction's owner, positive witness and rejection witness; shared controls and syntax classification alone do not close this coverage task.
- [ ] **SM-01.3** Inventory every public rich-policy builder/pattern/serialization/submission path. Preserve symbolic truth guards, immutable snapshots, exact values, source spans and full request inputs.
- [x] **SM-01.4a** Verify independently authored `once_per_scope` expansion, roundtrip and two namespaces with separate state/effect references.
- [x] **SM-01.4b** Verify all six public patterns against independently authored manual expansions, with full serialization/reference comparisons, separate instance identities, alternate names, supplied arbitration and relevant parameter variants. These bounded authoring controls do not implement module imports/exports or reference rebinding.
- [x] **SM-01.5** Freeze positive, negative and edit-propagation witnesses from section 4, including complete original BuildRequest/deployment/catalog/assurance authority and expected claim scopes.
- [x] **SM-01.6** Define and freeze the complete exact-mRNA structural predicate before accepting material fixtures; distinguish complete members from core-only sequence, unresolved tails and unresolved chemistry.

Current pattern checkpoint: the isolated follow-up branch adds 16 independently
reviewed tests in `tests/test_policy_patterns.py` for all six public patterns.
The focused Python 3.14.6 run passes 33 tests with process/network access denied:
16 new pattern tests, seven unchanged realization-fixture tests and ten existing
serialization tests. It checks 33 complete actual/manual program pairs, 39 literal
expansions, nine invalid arguments and six duplicate-name rejections. The 3,731
migration entries retain their order, nonreference fields and every old reference;
140 entries gain the new test reference. Evidence is retained in
`work/policy-descriptor-witnesses/generated/policy-pattern-witnesses/named-final-authoring.json`.
This completes the bounded authoring task; the follow-up branch's hosted
integration remains pending and these broader patterns gain no new native,
implementation or material support from these tests.

The original source-fixture preparation is retained in the [development history](semantic-mrna-development-history.md#sm-01-source-fixtures). Current source coverage and validation are recorded above and in section 2.

Exit: no authorable distinction can silently disappear, and the first complete compilation target is defined independently of producer output. A new source field/operator fails coverage accounting until classified.

### SM-02 — Specify the realization request, finite domain and preservation contract

Depends on: SM-01; implementation can proceed while SM-00 hosted validation runs.

- [x] **SM-02.1** Specify versioned PolicyRealizationRequest, finite operating-domain records, primitive contracts, PolicyImplementation and PolicyMaterialBinding wire forms for the declared bounded profile.
- [x] **SM-02.2** Implement strict bounded decoders and controlled native admission types; check complete original authority and library identities before selection.
- [x] **SM-02.3** Define input/output ownership, causal executable environment assumptions with prefix continuation/end rules, finite value/identity/time limits, initialization, overflow and interface compatibility. Assumptions cannot exclude bad implementation outputs.
- [x] **SM-02.4** Freeze the exact observable equivalence relation, causal input/feedback coupling, creation-time identity mapping, hidden-step rules, nonvacuity and per-requirement aggregation semantics from section 3.
- [x] **SM-02.5** Publish literal preservation examples and counterexamples for timing, unknowns, target mixing, reset, multiplicity, extra/missing events and divergent internal steps.
- [x] **SM-02.6** Version separate status/report contracts; preserve current assessment/operational operations instead of broadening their meanings.
- [x] **SM-02.7** Check original assurance strength, requested requirement identities, horizon/domain, tolerances and allowed assumptions against the actual result. Reject omitted requirements and stronger requests satisfied only by weaker evidence.

Current bounded-profile evidence (2026-10-06): SM-02.1 is implemented by the
closed [realization decoder](../core/lib/domain/policy_realization_request.ml),
[finite-domain interface](../core/lib/domain/policy_operating_domain.mli),
[primitive/implementation schema](../core/lib/domain/policy_implementation.ml)
and [material contract](../core/lib/domain/policy_material_contract.ml).
SM-02.6 has separate source assessment, operational, preservation and material
service reports, with native controls for forged promotions and replayed export
authority. The other checked tasks have strict original-authority admission,
prefix-owned causal input/feedback enumeration, exact tick/semantic-round
correspondence, creation-time injective identity maps, nonvacuity and exact
bounded assurance checks. Literal controls cover every SM-02.5 example category.
The request/preservation technical exit is met for this declared profile;
upstream coverage and full union/main acceptance remain separate obligations.
Arbitrary assumptions, latency tolerance and hidden-step abstraction are excluded.

See [realization contracts](policy-realization-contracts-v0.1.md) and the [historical foundation](semantic-mrna-development-history.md#sm-02-realization-foundation) for the initial schemas and environment-enumeration fixture.

Exit: request admission and the preservation relation are reviewable and executable without relying on a lowering producer.

### SM-03 — Build independent implementation primitives and reconstruction

Depends on: SM-02.

- [x] **SM-03.1a** Define the closed first-profile primitives for evidence/age encoding, three-valued predicates, scoped storage, atomic commit, explicit arbitration, timers and correlated attempt state.
- [ ] **SM-03.1b** Extend implementation primitives and checked lowering to source-level finite machines and transitions. Operational machine execution already exists, but this implementation profile explicitly rejects machines/transitions.
- [x] **SM-03.2** Implement candidate-state initialization and transitions independently of Policy_execution. Reconstruct exclusively from actual supplied primitive instances, configuration, ports and wiring.
- [x] **SM-03.3** Check well-typed ports, units, clocks, scope, state encoding, capacity and unique ownership; reject combinational/scheduling cycles unless a specified bounded settling rule admits them.
- [x] **SM-03.4** Implement the independently fixed total input/observable projection, causal feedback coupling and injective encounter/attempt mappings fixed at creation. Declare any structural sharing and prove that distinct instances retain independent state.
- [x] **SM-03.5** Add literal primitive and composed-runtime controls authored separately from the producer; enforce the runtime/producer/source dependency boundaries.

Current task scope: candidate execution reconstructs actual supplied graph
contents independently of the source evaluator and producer. Type/unit checking
covers the truth/event/fixed-text profile and exact clock conversion; quantity
signals remain excluded. Mutable encounter slots stay distinct. Permitted sharing
is explicit: pure constants may broadcast and identical nominal rising
expressions may reuse checked edge history; distinct rising expressions may not.
This does not establish multiple reusable driver instances within one assembly.

Exit: a hand-authored implementation candidate executes the accepted/rejected witness histories correctly without consulting the source evaluator or producer.

The [primitive execution contract](policy-primitive-execution-v0.1.md) governs this stage. Initial source preparation and event-order correction are retained in the [development history](semantic-mrna-development-history.md#sm-03-primitive-implementation).

### SM-04 — Implement lowering and independent bounded preservation checking

Depends on: SM-02 and SM-03; accepted results also depend on SM-00.

- [x] **SM-04.1** Lower admitted operational declarations into explicit primitive instances, configuration, wires, state/timer allocation and scheduling groups. Preserve complete source occurrence/requirement ledgers.
- [x] **SM-04.2** Build a producer-independent structural checker that reconstructs every expected obligation against original source and supplied contracts. Reject missing, duplicate or multiply owned behavior.
- [x] **SM-04.3** Implement complete reachable-domain exploration for the first small profile, with exact domain/case census, finite-state coverage, budgets, counterexamples and fresh replay.
- [x] **SM-04.4** Check both-direction observable equivalence, bounded internal settling, environment assumptions and source/candidate requirement outcomes independently.
- [x] **SM-04.5** Retain active/inactive and trigger/response witnesses where relevant. Separate no-trigger histories, unknown evidence, actual failure, unsupported properties and incomplete exploration.
- [x] **SM-04.6** Corrupt the producer and candidate gates, encodings, parameters, wires, clocks, identities and state transitions; demonstrate rejection with the unchanged checker.

Current task scope: these six tasks are complete for the declared first
one/two-rule profile. The independently authored nine-history domain is completely
explored; larger requests retain their own outcomes and budgets. The original
486-history request remains incomplete and cannot export. SM-04.6 records the
frozen mutation demonstrations, including typed rewiring, Unknown/reason loss,
identity/time changes and sequential-write counterexamples; it does not close
every operator/type/context combination in SM-01.2b or SM-08.1–2.

Exit: the first operational policy family has checked implementation preservation over its full declared finite domain, not merely one matching trace. No material producer is yet trusted to preserve that result automatically.

The [bounded-preservation contract](policy-bounded-preservation-v0.1.md) specifies the complete domain, independent requirement monitor and fail-closed budgets. Initial source preparation is retained in the [development history](semantic-mrna-development-history.md#sm-04-bounded-preservation).

### SM-05 — Bind components, deployment contracts and RNA architecture

Depends on: SM-04; schema/library preparation may overlap SM-03.

- [ ] **SM-05.1** Add a policy-specific adapter to reusable component/template/placement/helper/deployment types. Preserve legacy Behavior APIs and reject any lossy conversion.
- [x] **SM-05.2** For the bounded reusable-component profile, independently reconstruct selected component transition semantics and composition, checking exact correspondence to the accepted implementation or repeating preservation on the assembly. Match full locked models and configuration; account for every primitive and connection.
- [ ] **SM-05.3** Implement required finite resource/domain mappings currently rejected by the architecture profile; check cumulative memory, timers, queues, instances and formal resource budgets.
- [ ] **SM-05.4** Check helper bootstrap and dependencies, declared recipient/compartment consistency, co-delivery groups and supplied availability windows against the implementation clock and lifetime. Resolve every executable non-sequence configuration to an authorized host/environment input or supplied resource.
- [ ] **SM-05.5** Select bounded alternatives with hard constraints before preferences. Retain alternatives, deterministic ties, conflict explanations and search exhaustion without claiming global infeasibility/optimality.
- [ ] **SM-05.6** Preserve many-to-many function/component/mRNA relations, count every delivered helper, and check exact/max member and length limits.

Exit: a complete checked implementation has a complete eligible RNA architecture under the original declared contracts, with no hidden helper or unmet semantic constraint.

The four bounded composition slices below now pass focused hosted source-tree validation. Installed four-slot and full release acceptance remain open; alternatives, helpers and multiple members remain separate extensions.
Historical source preparation began in the isolated sparse worktree
`work/policy-component-composition`, branch `codex/policy-component-composition`,
based on the pending corrected union `4157108cb`. This overlaps the long release
gate without changing either frozen acceptance subject. The first task is the
closed partial-graph/interface domain; the current whole-graph decoder requires
all inputs to be driven and cannot represent independently connected fragments.
`Policy_component_fragment` source, a closed JSON Schema and independent literal
test source are committed there as `4fbf4176f` (source preparation only). The decoder preserves complete configured
models, typed boundary/external slots, input ownership, local atomic groups and
all ordered outputs; its identity excludes the surrounding whole-library digest.
The new fixture uses the identical driver across independently supplied A/B
libraries. Static dependency checks and all 34 Python boundary/bundle tests pass
on both Python 3.11.15 and 3.14.6 under process/network denial, with the same
587-file source manifest. The new native test is registered as suite 150;
existing suites and all 23 fixture dependencies are preserved. The independent
native source review counts 55 rejection invocations. These are source/static
results; native compilation/tests and full JSON Schema validation remain pending.
The focused proof is
`work/policy-component-composition/generated/component-fragment/focused-pair-proof.json`,
SHA-256 `21e8061becba5defa76f4057029918b2daf6b1f165a54552eb45137c4b49edfe`.
The separate source commit `3518db4b7` also updates the independently maintained
fixture-wiring census and development inventory to 150 suites, 152 executables,
32 dependency-bearing suites and the unchanged 23 fixtures. A guarded static
comparison checks the exact new fixture arguments; its proof is
`generated/component-fragment/fixture-census-proof.json`, SHA-256
`f6174762f06187da91e6871ec6ba90cdd381ff376c886dfd2ebe87e2148e9502`.
The full fixture-wiring tests require the omitted sparse-checkout corpus and
remain pending. These additional census files were not part of the earlier
587-file test snapshot.
The tracked `docs/policy-component-composition-v0.1.md` there records the full
future path, including constant-broadcast versus encounter-scoped links and a
new original composition context/layout authority. At that initial checkpoint,
no new profile was admitted, executed or exportable. The complete bounded
source-tree path is now demonstrated by run 37527311912; installed/release
acceptance is separate.
The local material/library interface and independent native test matrix are now
implemented and source-reviewed in that tracked composition specification.
They retain one original primary-RNA root per component, exhaustive
ordered feature carriers, complete product declarations and symbolic typed
provider prerequisites. Concrete provider/capacity/layout bodies remain outside
reusable identity. Driver/A/B target inventories are independently 14/82/93;
retained correlations and feedback rows keep their per-executor scopes. Local
decoding does not claim translation, global resource sufficiency or composition
acceptance. Reviews are retained in `generated/policy-component-composition/`
as `c01-local-material-interface.md` (SHA-256
`7e3af65fe34184de819644ba2130f84d304797283807b218ecbabce351f5cb8c`)
and `c01-local-material-test-review.md` (SHA-256
`d66f3678037985a2eb97831625498d072a77bbd03a70c2c1bce8c899266bb5a5`).
Both component suites are now registered: 151 suites, 153 executables, 33
dependency-bearing suites and the unchanged 23 fixtures. The new material suite
checks literal carrier inventories, original chemistry/product metadata, eager
library membership and coherently changed identities. Hosted native feedback
passed in run 37515212004 at source `a89f80b07`, including compilation and all
nine focused native suites. The refreshed 34-test boundary/bundle pair passes on
both Python versions with all 773 source files unchanged. Its proof is
`generated/component-material/focused-pair-proof.json`, SHA-256
`f2c55b3fc04da38626659e6859556da1882b012fba7d65da18fe363b56f14013`.
Independent Dune/AST/original-blob census preserves every prior ordered suite
and all 23 original fixture bytes; its proof SHA-256 is
`f734766cd32257aef45a89715bc902609741587ec722b3c0b1528641b4b10363`.
The hosted feedback report SHA-256 is
`40bab491cc1bc232e0f9ca16428db27d191129b858edeefc71bae1223ecdf8ed`;
root checked all 1,100 source pins before/after, the nine exact suite identities
and every retained command log against that report. All commands returned zero;
the report explicitly retains `acceptance: false`.
The original assembly-rule domain is now implemented: selected component pins,
ordered global inventories and typed cross-links, complete supplied material
authority, exact root bindings, one join and explicit carrier premises. Hosted
run 37518443101 passed all ten suites at ac3a0d3cb, including 93 rule controls.
The independent assembly checker and literal 17/18-base candidate tests passed
all eleven hosted suites at 25385487c in run 37521613648, including 403 new
controls. Root verified all 1,110 source pins and retained command logs; feedback
SHA-256 is `69f5468aa5a2580281b17a03216990e7cf8bda0e5a1973bd2d5de482ec34ac34`.
It requires a fresh preservation capability, reconstructs the exact
graph/material correspondence and checks feature, chemistry and carrier
projections. Its private leaf intentionally leaves catalog authorization,
context/resources, complete obligation discharge and export unassessed.
Assembly-rule/check tests share the unchanged independent literal prelude in a
domain-only test library outside both production executable closures.

Original request/catalog/context records and the bounded untrusted graph arranger passed the twelve-suite run 37523740443 at `9ebd2be390b53c352ce3a7a04c47104de43b22e9`, with 469 assembly and 97 request controls. Its report SHA-256 is `368148509eb88032bd840f1d3713f5943b112f5de0019eac1b4b0baf54985d30`. The independent context checker then passed 323 checks in thirteen-suite run 37524498720 at `fbfefff7513bf8a2840fd6898f4872adfbdd550f`; root verified all 1,121 source pins and every retained command log. Report SHA-256: `f1c56f12cd1f138b4c3f3b8323cfec6c25552659a727322b794851cb216053cf`. It checks declared complete record capacity, shared resource sums, actual identifier width, exact original providers and causal availability. Larger sufficient records are explicitly supported by the new profile; old whole-graph semantics remain unchanged.

The complete coordinator/native service passed sixteen suites at `4d19d7b37c2724579c386007476e638bdf0dc41a` (run 37526163552), including 152 new complete-service controls. The immutable Python adapter passed 44 tests on each supported Python version, retaining 27 old material-route regressions.

The full source-tree Python DSL → Core compile → producer-free Verify check/replay → fresh atomic ZIP export then passed at `5a45d354ee869f26f0e5d3181c8972a6402baca6` in run 37527311912. Both original policies discharge all 23 source obligations over all nine histories, 47 transitions and 48 prefixes; they reuse the exact same supplied driver and emit the independently authored 17/18-base RNA molecules. All 26 SDK observations, complete molecules/projections, source edits and guard/state/feedback/configuration/material rejection controls passed. Root verified 1,133 source pins, every retained command log, all observation bytes and both exact FASTA/manifest ZIP pairs without native execution locally. SDK receipt SHA-256: `35ffc2ac9591a97232cf6759bc47505b03d36436bae57462039160c27cf74a6c`. A ZIP: `09d232483211735a7ffdd3fbe613b973b9825dc14798eeca23d3c97ece8cce30`; B ZIP: `3d776a543f8cf99f72a8da867524b2a5b7630fbc619e913398976a899ce70243`.

Installed source origins, offline consumption, four-slot equality and full release/main gates remain unestablished for this new profile. The current implementation remains one RNA, no helpers, no alternatives, no added hidden steps and one driver instance per assembly. No source-bearing v1 request may be synthesized to replace original composition authority.
Acceptance still depends on the current profile and the complete new vertical
path. Preserve all existing v0.1 contracts and outputs.

| Order | Implementation work | Required boundary |
| --- | --- | --- |
| 1 | Closed component-library, assembly and original-request types; independently authored A/B inputs | Partial fragments need their own decoder. The original catalog must authorize the composition rule; no generated whole-graph v1 request can replace that authority. |
| 2 | Independent ordered-union and local-to-final material checking before the producer | Preserve complete models, all nodes/wires/exports, exact typed cross-links and source occurrences. The driver is byte-identical across the two distinct source/library contexts. |
| 3 | Private composition/context acceptance, complete obligation conjunction and exact construction | Reuse construction and resource predicates through checked interfaces. Derive 17/18-base outputs from supplied roots/join/chemistry rules; recompute identifier-dependent record widths. |
| 4 | Independent producer, negotiated native/SDK profile and complete acceptance | Fresh original-bound Core/Verify checks, nine-history domains for both fixtures, distinguishing mutations, installed/offline export and full hosted/main gates. |

The independently reviewed implementation decomposition and 28 input pins are
retained in
`work/bounded-policy-execution/generated/policy-realization/component-composition-independent-review.md`
and its `-pins.json` companion. No fixture blocker was found. This is design
preparation only; finite alternatives, executable helpers, multiple members and
multiple driver instances remain separate later work.

### SM-06 — Complete implementation-to-material correspondence and exact construction

Depends on: SM-05; construction leaf work can overlap SM-04.

- [x] **SM-06.1a** Define the independently supplied whole-graph material case: full implementation/configuration/connection authority, exact template roots, features, products and context.
- [x] **SM-06.1b** Extend that authority to reusable component configuration-to-template and connection-to-composition rules with independently supplied composition semantics.
- [x] **SM-06.2a** Independently reconstruct the whole-graph binding, including total ordered node/model/wire/group/export/carrier coverage and exact single-member material. Reject orphan operations, phantom connections and extra members.
- [ ] **SM-06.2b** Extend reconstruction to selected reusable component assemblies and their helper dependencies; independently justify any additional behavior and every delivered member.
- [x] **SM-06.3** Reuse existing construction operations and exact chemistry/coordinate checks, then enforce SM-01.6 completeness. Resolve full sequence extent, exact tails, required UTR/CDS/end features, chemistry and supplied product translation/junction authority; reject unresolved partial constructions.
- [x] **SM-06.4** Check every emitted base, member, feature and source/destination coordinate against original roots and authorized transforms. No implicit back-translation, optimization or invented sequence.
- [x] **SM-06.5** Establish complete implementation-configuration-to-material dependency maps. Sequence/layout edits invalidate affected implementation/material claims; identical bytes do not imply identical configuration authority.
- [x] **SM-06.6a** Demonstrate first-profile mutation rejection for guards, state/atomic writes, deadlines/configuration, product/CDS, missing/extra members, altered bases, region geometry, chemistry and recipient.
- [x] **SM-06.6b** Add genuine component-to-component material-junction mutations with the new composition profile. Existing region-gap/overlap checks do not establish those composition semantics.

Current completion scope: one complete linear coding RNA with an ordinary CDS,
full four-region partition, exact supplied product translation, exact represented
tail and nominal chemistry. Fresh reconstruction checks every original root,
authorized transform, base and coordinate. Configuration/carrier coverage and
equal-RNA/wrong-authority controls preserve the conditional model-to-material
relation. The complete profile still requires one RNA and zero helpers; broader
standalone structural leaf tests do not establish full-profile multi-RNA support.
Reusable A/B fragment composition now passes the complete source-tree route. Helper dependencies, multiple members and full installed/release acceptance remain the explicit remainder.

Exit: exact complete mRNA candidates are independently checked against both their material construction authority and the accepted implementation binding.

The [source-neutral construction leaf](construction-content-v0.1.md) and [material acceptance contract](policy-material-acceptance.md) govern the complete first-profile derivation. Initial source preparation is retained in the [development history](semantic-mrna-development-history.md#sm-06-material-construction).

### SM-07 — Integrate fresh acceptance, immutable artifacts and public SDK/CLI

Depends on: SM-04 through SM-06.

- [x] **SM-07.1** Define a canonical accepted-build manifest containing full original source artifact, definitions, domain, implementation/material libraries, every IR, mappings, requirements, bounds, checker identities and emitted member inventory.
- [x] **SM-07.2** Distinguish declaration-content identity from full source-artifact identity, including source maps/provenance. Define a stage-by-stage invalidation graph and exact replay inputs.
- [x] **SM-07.3** Add explicit versioned compile/check/replay/export native operations. Standalone Verify reconstructs acceptance without producer linkage; old result profiles retain their existing statuses.
- [x] **SM-07.4** Route complete rich-policy requests through thin immutable Python SDK/CLI adapters. No semantic fallback on unsupported input, incompatible binaries, timeout, crash, cancellation or exhausted work.
- [x] **SM-07.5** Export only a freshly checked immutable accepted result, atomically binding RNA FASTA and full manifest. Recheck exact bytes at the publication boundary and preserve prior outputs on failure.
- [x] **SM-07.6** Verify outside the checkout with producer modules absent and original authority supplied separately. Reject forged/rehashed reports, stale binaries, altered claims and truncated evidence.

Current completion scope: the manifest retains all original inputs, candidate
stages, bounds, complete fresh assessment and exact molecular inventory. SM-07.2
uses conservative full-chain invalidation: every replay/export reconstructs the
required stages from original authority; no incremental cache scheduler is
claimed. SM-07.5 atomically publishes one read-back-verified FASTA/manifest ZIP
and preserves prior outputs on failure; directory-fsync crash durability is not
claimed. SM-07.6 is demonstrated by authenticated four-slot PR95 standalone
consumer/prebuilt evidence for the unchanged modules; union/main acceptance
remains SM-08 work.

The source/witness reconciliation for SM-06/07 is retained in
`work/m11-human-evidence/generated/policy-realization/tracker-sm06-sm07-review-a85b1112f.md`,
SHA-256 `aa370c32ebe49fd331677dcd175f519b5f80145459bd94308f4b10496edcea70`.
Its exact task scopes complement the revision-bound execution evidence in section 2.

Exit: one complete Python-policy → implementation → exact mRNA path works through installed public APIs with fresh standalone verification and exact request-bound export.

Initial material integration, failed runs and their narrow corrections are retained in the [development history](semantic-mrna-development-history.md#sm-07-public-material-integration). Current exact-revision validation is in section 2; earlier preparation statuses are not current task status.

### SM-08 — Close the declared profile, compatibility and hosted acceptance

Depends on: SM-07; test/campaign design starts at SM-01.

- [ ] **SM-08.1** Run the semantic and edit-propagation matrix in section 6; require positive, distinguishing negative and cross-layer mutation coverage for every supported row.
- [ ] **SM-08.2** Verify rejection coverage for every excluded field/operator/enum combination; distinguish unsupported language, missing library support, contradiction, violation and exhaustion.
- [ ] **SM-08.3** Preserve historical unit/corpus/source-lineage/SDK behavior and all existing release tests. Add reviewed authority entries instead of weakening frozen baselines.
- [ ] **SM-08.4** Run all four installed Linux x86_64/macOS arm64 × Python 3.11/3.14 campaigns on hosted native builds, with Python semantic authorities forbidden.
- [ ] **SM-08.5** Independently compare complete semantic outputs and molecule sets across slots. Preserve actual per-platform binary/provenance differences and exact source/run/attempt binding.
- [ ] **SM-08.6** Complete the full exact-revision aggregate gate and any required integration/main validation under branch ownership rules. Record source-ready, tested and accepted revisions separately.
- [ ] **SM-08.7** Finish targeted prebuilt/installed routing for this profile, including missing/wrong binary, offline invocation, standalone verification and fail-closed upgrade/profile mismatch. Broader default cutover remains separately gated.

Exit: the first declared rich-policy-to-mRNA profile is accepted end to end. A demo, subset of tests, static check or prior branch's receipt cannot close this package.

The original installed campaign, subsequent diagnostic runs, budget-preserving regression work and witness additions are retained in the [development history](semantic-mrna-development-history.md#sm-08-diagnostic-and-witness-history). Section 2 records the latest PR95/PR85 evidence and the corrected-head acceptance prerequisite.

### SM-09 — Expand supported semantics through complete vertical profiles

Depends on: SM-08 for acceptance; design work can be prepared earlier.

- [x] **SM-09.1** Choose exact reusable component composition as the next profile: two independently supplied fragments, three explicit boundary links and two source families reusing one identical driver. Alternatives and helpers/multiple members follow as distinct extensions; design selection does not accept their implementation.
- [x] **SM-09.2** For the bounded reusable-component extension, connect source meaning, primitive semantics, lowering, preservation, material contracts and public profile negotiation; version the separate request/candidate/resource/export contracts and reconstruct acceptance after edits. Hosted source-tree validation passed at 5a45d354e; the repeated installed/full gate remains SM-09.3.
- [ ] **SM-09.3** Add complete accepted/rejected witness families and repeat the same hosted gate. Never mark a feature exportable merely because it is authorable or reference-executable.
- [ ] **SM-09.4** Reconcile affected public workflow/default migration tasks with their owners. Retire a Python semantic authority only when every dependent admitted path is accepted.

Exit per expansion: a complete supported source-to-mRNA path with explicit boundaries. Deferred language forms remain faithfully represented and explicitly unsupported until their own contracts are implemented.

Current profile boundary: the first material profile is a single supplied whole-graph
case with one exact RNA/product and no delivered helper, using a narrow
exclusive truth/encounter family and explicit formal context. The separate bounded composition profile now supports two exact components and
two source families through fresh source-tree export. Its installed/full acceptance
remains open. Broader composition, numeric/state/lifecycle operations, machines, coordination,
quantification, inheritance, independent delivery and helper/multiple-member
closure remain material-profile expansion work. Existing authoring or broader
reference-execution support does not establish admission through that entire
chain; operational and material restrictions remain distinct. Next: choose one
concrete source-coverage need after the initial SM-08 gate, extend every dependent semantic/material/public
boundary, and repeat complete positive/distinguishing-negative hosted acceptance.
No broader support follows from a source declaration, matching sequence or
single-case success; biological viability is outside this session's scope.

## 6. Required semantic and mutation matrix

| Dimension | Positive/control pair and rejection target |
| --- | --- |
| Python construction | Builder versus literal document; pattern versus manual expansion; separate identical instances; reject accidental symbolic truth conversion, foreign/dangling references and namespace collisions |
| Data fidelity | Exact large integers/decimals, units, ordered occurrences and complete ledgers; reject raw floats, duplicate keys, bool/integer aliases and ignored extra fields |
| Source identity | Full definition/version/digest and original artifact; reject stale descriptors, altered source spans/requirements and recomputed self-supplied hashes |
| Evidence | Strong Kleene tables; each invalidity reason; delayed arrival and quiet-time expiry; reject unknown-as-false and inappropriate loss of evidence reasons |
| Identity and state | Equal-valued distinct targets, reset generations, independent pattern instances, finite capacities and overflow; reject merged encounters/attempts, retrospective identity remapping or leaked state |
| Atomicity/arbitration | Common read snapshot, identical/conflicting writes, explicit priority opposing source order, rule/machine competition; reject invented ordering and partial commit |
| Time/lifecycle | Before/at/after deadlines, simultaneous feedback/timeout, repeated attempts, wrong/stale feedback, reset/end and no-input ticks; reject fabricated completion/cancellation |
| Preservation | Missing/extra/reordered observable event, changed timing/multiplicity, incorrect projection, falsely hidden effects, identity collapse and divergent hidden steps |
| Requirements/domain | Real triggers and relevant active/inactive witnesses; source failure, missing feedback, unknown coverage, truncated horizon, empty/contradictory domain and unsupported phase; reject omitted requirements, weaker assurance, reduced domains, producer-added assumptions and circular premises that exclude bad outputs |
| Candidate independence | Alter producer while keeping checker fixed; remove producer linkage; mutate locked operations/wiring/configuration; prevent candidate use of expected source trace |
| Components/resources | Same-signature/different-behavior substitution, missing helper, bootstrap cycle, exceeded capacity, wrong recipient/compartment, incompatible availability, hidden material and cardinality violation |
| Material | Swapped product/CDS, wrong template parameterization, altered base/junction/coordinate/chemistry, unresolved sequence/tail, omitted member, manifest-only connection and configuration without a carrier |
| Freshness/export | Modify any original input, definition, model, domain, template, transformation, bound or checker version; reject old PASS and partially published output |
| Resource accounting | Exact finite-domain census, budget exhaustion and bounded decoding; no successful partial trace/proof/build/export |
| Cross-platform | All four installed slots, actual binary digests, full semantic/material output equality, duplicate/missing/stale receipt rejection |

Metamorphic cases must state their equivalence relation. JSON object-key order/formatting may preserve canonical content; source-map edits may preserve declaration meaning but change full authority; consistent renaming may preserve behavior modulo identities. Do not require unchanged raw traces where generated IDs, source provenance or resource accounting legitimately differ.

For a source edit, accept only one of three reviewable outcomes: a newly checked implementation/material result; precise rejection/unresolved status; or a fresh proof that the existing complete implementation/material contract still satisfies the edited source. Do not demand every semantic edit change RNA bytes, and do not accept unchanged bytes without fresh checking.

## 7. Work sequencing and ownership during implementation

Critical path:

SM-00 → SM-01 → SM-02 → SM-03 → SM-04 → SM-05 → SM-06 → SM-07 → SM-08.

SM-01/02 design and fixture work may proceed while SM-00 CI runs. SM-05 contract preparation and SM-06 reusable material checks may run alongside implementation/runtime work, but acceptance waits for their stated dependencies.

Use one integration owner for protocol schemas, Dune boundaries, status contracts, source-authority registries, CI wiring and final evidence. Delegate disjoint files:

| Track | Ownership |
| --- | --- |
| Source/domain/lowering | Coverage ledger, admitted request/domain, implementation IR and lowering producer |
| Independent execution/checking | Candidate reconstruction, preservation relation, bounded exploration, requirements and mutation controls |
| Python/artifacts/material adapters | Immutable SDK/CLI transport, construction integration, manifests, edit invalidation and installed campaigns |

Agree on interfaces and literal fixtures before parallel source edits. A checker review must be independent of producer expectations. Review borrowed library semantics explicitly; reuse compatible primitives without silently importing old missingness/rising/identity conventions.

Batch coherent changes, run appropriate local static/Python checks once, then native hosted validation. Do not push documentation-only churn that needlessly cancels useful running acceptance. Preserve useful failure logs and refresh exact source identities after each necessary correction.

## 8. Evidence and completion policy

All OCaml/Rust compilation, native executable tests, extension rebuilds and native packaging remain hosted. Local work is editing, documentation/static checks and meaningful Python-only tests without implicit native builds.

For each SM package, retain: task IDs, source commit, tested checkout/merge revision, source tree identity, run/attempt, platform/Python/toolchain, actual Core/Verify hashes, complete case census, full results, counterexamples and remaining obligations. Static checks, tests and formal/bounded proof coverage are separately named evidence.

A task checkbox may be checked only when its stated exit is satisfied. Use a checkpoint note for “source ready; hosted pending.” Source-only work is valuable but is not accepted execution. Preserve every existing gate, discovery accounting and required negative assertion; new work adds coverage.

The session's first major completion gate is SM-08:

- Every supported source distinction has an executable/lowering/material disposition.
- The original Python request reaches exact complete mRNA members through real implementation lowering.
- Independent reconstruction checks preservation and all required obligations over the declared bounded domain.
- Exact material and complete configuration/model/source correspondence are checked.
- Fresh standalone verification and atomic paired export work outside the checkout.
- Source/model/material edits cannot retain stale acceptance.
- All required exact-revision hosted gates pass.
- Unsupported requests receive precise diagnostics.
- No Studio, conversational or empirical-viability work is required to satisfy this gate.

## 9. Immediate execution queue

1. Let healthy jobs finish in [PR85 run 37545710899](https://github.com/logannye/biocompiler/actions/runs/37545710899) at integrated H `5717cb288`, tested C `0b4cf661b`, tree `634b7865e`. Correct the macOS static-GMP failure by preserving validated upstream file timestamps, retaining exact archive pins and configure/build/check/install commands. Validate the coherent correction with inert regression controls and a focused hosted macOS build before a fresh complete PR gate. Require all 74 jobs, 59 ordinary receipts, 156 native suites, four installed slots, complete comparisons and unchanged whole-graph checks. No prior development or bootstrap result supplies release acceptance.
2. Use committed component audit tools `1c67b5b3c` with the explicit `complete-component-release-v1` profile and freshly authenticated final API/ZIP inputs. The failed 5717 plan is preserved at SHA-256 `77fa9086d6de2138065939d5e746eca25af94bccd1cf29f3b674a0396a6a8bca`; the corrected source and fresh run require a separately authenticated new plan. Reconstruct the full evidence against original authority before accepting the candidate. Preserve the legacy profile and all identity/archive/coverage guards.
3. Normally merge exactly the accepted PR85 head after rechecking current main and PR identities. Confirm that the preserved PR95 head is included and its GitHub state reflects that integration. Then validate actual main with its own complete fresh run and independent audit. Preserve branches and source histories; do not relabel a PR receipt as main acceptance.
4. Update the validation-specific checkboxes at their stated exits. A complete PR gate and audit can close the narrow hosted compatibility/installed/comparison tasks. The bundled component release item and SM-08.6 remain open until fresh actual-main acceptance. Exhaustive coverage inventories, helpers, multiple members and production default cutover remain separately scoped.
5. Batch coherent implementation, independent tests, focused review and hosted feedback. Do not cancel healthy work for documentation changes. The old 8c61 run finished before the leased PR update: all ten unit shards and both accounting jobs passed; the unavailable macOS interpreter caused the failed release. Preserve its diagnosis and every earlier run as distinct evidence.
6. Prepare the next bounded alternative-selection contract while the gate runs; implementation/acceptance follows the reusable-component slice. Adopt the narrow complete-inner-check profile below for SM-05.5. Start with explicitly supplied material variants of one unchanged executable component program, keeping exactly two component slots, one driver instance, the existing three boundary links, zero helpers, no added hidden steps and one RNA member. A and B remain separate programs, never competing alternatives.

**Prepared SM-05.5 contract; implementation and acceptance remain open.** A separate versioned selection envelope retains the complete supplied original component request and candidate for every alternative, a closed finite alternative census, a common additional length predicate, supplied nonnegative integer ranks, an explicit deterministic ID tie order and aggregate work/publication bounds. Existing component requests and their inner checks remain unchanged. Every alternative, including every eventual loser, must independently pass the complete inner component checker and discharge all original obligations. Only fresh abstract `Policy_component_material_check.checked_material` values and their checked context/assembly/structure chain authorize the exact RNA used by outer selection. Saved reports, decoded PASS text, producer lengths and winner-only inner acceptance confer no selection authority.

Common authority is exact: every child retains the same complete source, assurance, requirements, definitions, operating domain, implementation contracts, input authority and base deployment obligations. Material-only variants retain identical semantic fragments, models/configurations, graph/order/links, prerequisites and products, and an identical independently derived semantic ordered union. Preserve provider DefinitionRefs, semantic bodies, quantities, sharing, availability, recipient, placement, delivery obligations and every numeric record bound. Check alternative-specific pins by a closed reconstruction from these common originals and each supplied material body: recompute component/library/rule pins, bind the changed rule pin in the context record layout, recompute that layout fingerprint, then recompute each affected provider's capacity `record_layout_digest` and full-body identity pin. Compare all remaining fields exactly. Do not establish common authority by dropping arbitrary digest fields, broad normalization or producer-authored replacement requests; reconstruction checks the supplied originals and never grants permission to weaken them.

The first literal witness supplies two independently authored material realizations of the same A graph and identical driver `AUGGCUUAAGGAAAA`: leader `CC` yields `CCAUGGCUUAAGGAAAA` (17 bases); leader `CGC` yields `CGCAUGGCUUAAGGAAAA` (18 bases). Both complete inner requests declare the same base delivery ceiling `max_total_bases = 18`, so both must receive fresh complete inner acceptance. A common **additional outer** predicate `max_total_nt = 17` then makes only the 17-base alternative eligible, even when the 18-base alternative has the better supplied rank. With an outer ceiling of 18 the preferred 18-base alternative wins; with an outer ceiling of 16 a complete census establishes no eligible alternative in this supplied catalog. Do not substitute B's different decision graph, or copy the current A/B requests with their different base ceilings, to construct this witness. A separate B witness may reuse the same pattern under B's unchanged source and graph.

Only after authenticating and checking the complete alternative census does the independent selector evaluate the additional hard predicate, then minimize the supplied rank and apply the specified ID tie order. Missing, malformed, corrupted, failed, unverified or exhausted children invalidate or leave the entire selection incomplete; none may be classified as an ineligible alternative or omitted to manufacture a winner. Outer predicate rejection is the only per-alternative ineligibility in this first profile. All freshly checked children rejected by that predicate yield complete no-selection and no artifact. Exhausted aggregate work or publication bounds yield an incomplete result and no selected/export capability. These outcomes make no global infeasibility or unrestricted optimality claim. A broad taxonomy for accepting inner-check failures as searchable alternatives is deferred.

The selection checker must grant its own private checked-selection token binding the full original census, common authority, ranks, outer predicate, fresh child evidence and independently derived winner. Reuse the existing producer-independent component checker/token chain; neutral candidate codec or export-helper factoring is permitted without making producer code a verification dependency. Fresh outer export rechecks the complete selection and binds the winner's exact manifest and FASTA to that token. Inner export alone cannot establish that the selected alternative is correct, and edits to losing inputs, ranks or the predicate invalidate prior selection acceptance even if the winning RNA bytes remain unchanged.

Implementation acceptance must include literal positive/no-selection cases, tied ranks, reordered catalogs, changed ranks/predicate, unchanged winner bytes after a losing-input edit, weakened common obligations, unauthorized pin changes, missing or forged losing candidates, an inner failure and inner/aggregate exhaustion after another child passes, and stale selected export. Bound decoding, all child checks, preference evaluation and publication cumulatively without reducing any child's original source/domain/assurance obligations. Require the complete Python-to-native-to-independent-Verify-to-paired-export path, unchanged legacy profiles, new installed/offline witnesses and the full hosted/release/main gates. SM-05.5, implementation/native acceptance and release/main checkboxes remain open; this is completed design preparation only.

## 10. Related governing documents

- [Operational semantics and current boundary](policy-operational-v0.1.md)
- [Python source language](policy-language-v0.1.md)
- [Native source frontend](policy-native-front-end-v0.1.md)
- [Existing architecture contracts](payload-architecture-v0.1.md)
- [Existing molecular design construction](molecular-design-v0.1.md)
- [Independent verification boundaries](verification-independence-v0.1.md)
- [Development validation](development-validation.md)
- [Migration roadmap and historical receipts](language-migration-roadmap.md)
