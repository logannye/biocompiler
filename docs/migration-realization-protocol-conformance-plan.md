# Realization protocol conformance audit

Preserved implementation checkpoint: the reported component-behavior resource fixes are included in the PR56 correction. Their hosted validation is pending. The protocol below remains proposed and unimplemented.

Read-only design audit, 2026-10-02. This document specifies the next validation
batch; it does not report implementation or native execution. Current priority
is to finish and validate the corrections to the existing native batch before
adding the public service. No production source, shared CI, or frozen corpus was
modified for this audit.

## Decision and source of truth

Implement and validate all nine operations in
`docs/migration-realization-routing-plan.md` together. Preserve the distinct
authority and claim of each family. Both `biocompiler-core` and the independent
`biocompiler-verify` must expose the checker operations; neither role may infer a
PASS from a stored artifact, hash, or producer assertion.

The current protocol design agreement requires a family-specific `profile` and
`limits` field on every payload. `limits` is either null (documented defaults) or
an exact five-field record of strict positive reductions of native limits.
`supplied_authority_fingerprint` hashes every payload field except the replay
`assessment`, including `profile` and `limits`. Freeze the exact profile strings,
schema records, operation names, default limits, and capability order from the
companion native-service design before implementation. This resolves the older
routing plan's open question about optional resource controls.

The requested `tools/check_core_protocol.py` does not exist. Relevant existing
campaigns are `tools/check_core_conformance.py`,
`tools/check_architecture_protocol.py`,
`tools/check_architecture_producer_protocol.py`, and
`tools/check_architecture_routing_reproducibility.py`; corresponding tests include
`tests/test_core_client.py`, `tests/test_core_conformance.py`,
`tests/test_architecture_protocol_corpus.py`, and
`tests/test_core_architecture.py`. Extend their exact capability expectations and
retain every existing gate. In particular, the generic campaign's claim that
there is no candidate execution must be updated when that stops being true.

## Full frozen authority inventory

Use the already complete `tests/conformance/synthetic-acceptance-v1.json` as the
direct-check baseline. Its pin is
`d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331`.
The newer `synthetic-producers-v1.json` preserves all the same acceptance
observations and adds the producer and selection-domain coverage; its pin is
`2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b`.
Do not concatenate both and count repeated observations as additional evidence.

| Original API | All calls | Distinct complete inputs | Complete recorded outcomes |
| --- | ---: | ---: | --- |
| `realization_dependencies` | 1,996 | 585 | 1,996 dependency records |
| `check_realization` | 1,080 | 579 | 969 PASS; 56 FAIL; 54 UNKNOWN; 1 UNSUPPORTED |
| `check_synthetic_candidate` | 906 | 534 | 860 PASS; 13 FAIL; 30 UNKNOWN; 3 UNSUPPORTED |
| `check_component_behavior` | 85 | 11 | 80 PASS; 4 FAIL; 1 UNKNOWN |
| `check_component_assembly` | 52 | 17 | 41 PASS; 9 source-correspondence errors; 2 synthetic-acceptance precondition errors |
| Total | 4,119 | 1,726 per-API distinct inputs | 4,108 returns and 11 exceptions |

The distinct-input counts are an audit, not permission to sample. A call with the
same authority may have a different expected result under an explicit original
monkeypatch. Preserve every original occurrence and its context in the protocol
receipt. Default to executing all 4,119 direct calls per executable role. If
subprocess measurements justify coalescing, require a separate reviewed,
lossless mapping keyed by operation, full wire payload, and full expected
result/error; record every original occurrence and preserve the original native
and Python campaigns that execute all occurrences. Never select only PASS cases,
one case per profile, or a few convenient representative tests.

Each of the 2,112 returned checker reports is also a replay input: 1,080 direct,
906 synthetic, 85 component behavior, and 41 assembly reports. The two original
checker-version-mutated reports must reject as stale on replay; their current
counterparts should additionally replay successfully. This gives 6,231 base
direct/replay calls per role, or 6,233 including those two current counterparts,
before added mutation, Unicode, malformed-wire, and resource cases. Negotiated
client calls commonly launch at least two processes, so measure and partition
the hosted workload rather than quietly narrowing it.

The machine-readable audits alongside this plan preserve the exact inputs,
results, source locations, stages, and representative IDs:

- `migration-realization-protocol-corpus-audit.json`: four corpus pins, stage census,
  distinct full authorities, full result/input document hashes, exact five
  mutation IDs, and Unicode census.
- `migration-realization-protocol-outcome-audit.json`: all outcomes, per-outcome distinct
  input counts, and raw horizon type census.

Those representative IDs aid debugging; the full pinned corpus remains the
execution source. Frozen native input documents contain JSON strings: resolve
the content-addressed document, then parse that string to recover the original
bound arguments. Do not accidentally transport the wrapper string or rehydrate
through Python semantic constructors.

## Nine operations and complete comparison

All rows also carry the required `profile` and `limits`. Replay adds the complete
raw `assessment` to the otherwise identical authority. Rename captured Python
`request` to wire `expected_request`; retain every other original field.

| Operation | Complete authority | Original oracle |
| --- | --- | --- |
| `realization-dependencies` | behavior, contract, domain, target, mechanism, observation_map, history, until | `realization_dependencies` |
| `verify-realization` | Same eight fields | `check_realization` |
| `replay-realization` | Same eight fields plus assessment | Fresh direct checker, exact report comparison |
| `verify-synthetic-candidate` | expected_request, candidate, history, until | `check_synthetic_candidate` |
| `replay-synthetic-candidate` | Same four fields plus assessment | Fresh synthetic checker, exact report comparison |
| `verify-component-behavior` | expected_request, assembly, history, until | `check_component_behavior` |
| `replay-component-behavior` | Same four fields plus assessment | Fresh behavior checker, exact report comparison |
| `verify-component-assembly` | expected_request, candidate, assembly, history, until | `check_component_assembly` |
| `replay-component-assembly` | Same five fields plus assessment | Fresh assembly checker, exact report comparison |

Compare complete report content and identity, not just the outcome. Preserve
dependencies, checker/model versions, assumptions, scope, observations,
requirements, exercised/unexercised coverage, counterexamples, complete histories,
and diagnostics exactly as in the original records. A semantic FAIL, UNKNOWN,
or UNSUPPORTED is a successful protocol response carrying the complete report.
An import, resource, precondition, or replay mismatch is a protocol error with no
accepted result. Dependencies return no semantic PASS.

Direct realization checks do not establish source-to-Behavior lowering. Synthetic
checks bind source and candidate provenance; generic component behavior checks
do not establish synthetic correspondence. Assembly checks must bind the full
request, candidate, assembly, history and horizon even though the inner
CompositionResult dependency record alone does not identify every one of those
outer inputs. None establishes empirical behavior in human immune cells.

`CheckResult` and `DependencySnapshot` identities use their existing ASCII JSON
canonicalization; `CompositionResult` and wire envelopes use UTF-8 canonical
content. Neither `DependencySnapshot` nor `InputFrame` has a `schema_version`.
Do not invent one to make transport uniform. Raw replay comparison must detect
extra fields and representation changes that a permissive importer could erase.

## Exact version-mutation migration

The existing five observations are deliberate original test monkeypatches, not
public policy inputs. Do not add a wire checker-version override or broadly
normalize any result field. The current original checker version is
`biocompiler.realization_checker.v0.3`; freeze the current-version full counterpart
of each below and retain the exact original mutated record and lineage.

| Original context and call | API | Original checker mutation |
| --- | --- | --- |
| `tests/test_realization_checker.py::CheckArtifactTests.test_public_dependency_helper_detects_context_parameter_and_history_changes/api/5` | dependencies | `changed` |
| `tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay/api/128` | synthetic check | `changed.v999` |
| Same workflow context `/api/130` | dependencies | `changed.v999` |
| Same workflow context `/api/190` | direct check | `changed.v999` |
| Same workflow context `/api/191` | dependencies | `changed.v999` |

The first is called at source line 540; the workflow mutation is at source line
271. Direct protocol responses compare against complete current-policy records.
The original two mutated check reports become precise stale-replay rejections;
dependency-only mutations have no invented replay endpoint. Existing Python and
native fixture tests retain the original monkeypatch semantics unchanged.

## Gaps to close with new full witnesses

**Unicode:** the complete authority census found zero non-ASCII input characters
in all 4,119 acceptance observations. Existing raw Unicode codec vectors cannot
prove the distinction between ASCII evidence hashes and UTF-8 wire/report hashes.
Add independently evaluated full cases with Unicode in valid contact/history
identities, including a failing report whose complete counterexample retains that
history; also add consistently relocated Unicode source paths/functions and
valid requirement/observable labels where supported. Regenerate the coherent
request/candidate and Python report using original semantics before freezing.
Never edit only an expected report or fabricate its fingerprints. Check composed
versus decomposed strings, escaped versus literal Unicode on the wire, and exact
source-artifact identity separately from semantic identity.

**Horizon:** direct-check inputs contain 34 null, 1,036 integer, and 10 float
horizons; dependencies contain 40 null, 1,939 integer, and 17 float. Synthetic has
899 integer and 7 float; component behavior has 85 integer; assembly has 51
integer and 1 float. Add valid null-horizon wrapper cases, plus explicit effective
horizons, integer/float equality, zero and signed zero where valid. Preserve the
raw original form in authority hashing. Equal model behavior does not authorize
silently replacing the original supplied authority.

**Acceptance and replay mutations:** preserve all original policy, catalog,
lock, source-correspondence, wiring, graph, initialization, output, dependency,
history, and horizon mutations. Include coherent altered candidates that pass
and actual altered behavior that fails. Retain UNKNOWN and UNSUPPORTED as such.
Mutate every report field family, including complete nonpassing reports, and
rehash forged reports coherently: fresh replay still rejects a disagreement.
Bare PASS, the original hash, partial summaries, or stale dependency records are
insufficient. Add exact missing/unknown field tests at each outer boundary and
wrong-family profile/schema/assessment cases. Never claim an unobserved outcome
is covered merely because a related family produces it.

**Resources:** test all five strict positive reduction fields, null/default,
exact key set, booleans, floats, zero, negatives, and attempted increases. Each
tiny independent limit must yield the intended resource diagnostic with no
partial accepted result, including inherited/shared work exhaustion in nested
assembly behavior checks. Retain native exact/one-below usage and repeated fresh
call tests. Budget input construction, translated histories, repeated source and
domain expansion, report construction, replay assessment, and final envelope.
The native request/report budgets and wire request/response framing bounds are
different limits; neither can substitute for the other. Include profile and
limits in the outer authority hash, so null and an explicit default-valued record
can have equal semantic results but distinct supplied authority fingerprints.

**Wire and failure handling:** retain raw duplicate-key, invalid UTF-8, lone
surrogate, NaN/Infinity, long-number, exact-integer, signed-zero, single-request
NDJSON, oversized response, malformed stderr/stdout, crash, timeout, and
cancellation controls. Typed JSON encoding cannot create every malformed wire
case; use the existing raw exchange helper for those. Cyclic in-memory graphs
cannot be represented on the wire; keep existing domain cycle tests and state
that boundary honestly. Verify cancellation reaches the process and no Python
fallback runs. Distinguish unavailable-operation `CoreUnsupported` from a valid
semantic UNSUPPORTED report.

## Installed execution and fallback guard

Add a dedicated `tools/check_realization_protocol.py` and its pure Python corpus
integrity/recipe tests. Use the stronger architecture producer campaign pattern:
run from a temporary directory outside the source tree; assert the installed
`biocompiler` package and every loaded submodule resolve outside the repository;
select both binaries by explicit absolute path; assert their negotiated roles.
Use a `sys.setprofile` call guard that rejects Python execution inside all
`biocompiler` semantic modules, permitting only the explicitly reviewed transport
modules. This catches previously imported aliases as well as dynamic imports.

Decode frozen JSON with the standard library and send complete wire records.
In particular, Python `RealizationRequest.__post_init__` invokes lowering
verification and is unsuitable for a transport-only fixture loader. Any public
returned-record hydration must be audited separately for hidden semantic calls.
Do not whitelist a semantic package broadly just to make the guard pass.

Keep negotiation strict: full operation/schema/implementation/resource/scope
records and ordering, exact executable role, current request id, all response
identities, and complete dependency/report identities. Mutating caller-owned
containers after negotiation must not modify accepted capabilities. Missing
operations fail closed with no Python fallback. Add protocol metadata mutation
tests in the existing strict client suite rather than relying solely on native
happy-path responses.

Existing hosted jobs use installed Python and explicit hosted-built native files:
`core/_build/default/bin/core/main.exe` and
`core/_build/default/bin/verify/main.exe`. This is distinct from testing native
installation itself. For an installed-native gate, install the already-built
Dune package into a single hosted temporary prefix and select
`PREFIX/bin/biocompiler-core` and `PREFIX/bin/biocompiler-verify`; the Dune public
names and package `biocompiler_core` are already declared. Verify the installation
command against the pinned hosted Dune version when wiring CI. No local native
build or executable run is authorized by this plan.

## CI, receipts, and boundaries

Extend the existing hosted Linux x86_64 and macOS arm64 native jobs and run the
installed protocol campaign on Python 3.11 and 3.14. Retain pinned native toolchain,
all original Dune tests and frozen corpora, all Python discovery shards, generic
core conformance, architecture protocol, architecture producer/routing, and
reproducibility gates. `check_architecture_protocol.py` currently selects 24
architecture cases for 108 checks; its sampling design is not a reason to reduce
the complete realization inventory.

Each receipt should bind tested revision, source revision, platform/architecture,
Python version, binary role/path/SHA-256, installed package location, frozen corpus
pin, profile/capability identity, complete occurrence-to-operation mapping,
executed outcome/error counts, no-fallback guard status, and artifact hashes.
Store deterministic full assessments or content-addressed references for every
distinct authority, not just aggregate PASS counts. Extend the cross-platform
comparison with a separate realization receipt matrix; preserve the existing
architecture comparison intact. Missing, stale, skipped, canceled, or failed
matrix cells cannot count as completion. Measure subprocess overhead before
adjusting partitioning or the 90-minute native job limit.

Permit only the necessary checker/source-evaluator/candidate-runtime service
dependencies. The standalone verifier must remain independent of compiler and
producer libraries and private witness entrypoints. Keep boundary tests exact
as service dependencies expand. Generator, selector and adapter implementations
already exist internally, but their public dispatch, pipeline/archive routing,
export acceptance, and unported workflow semantics are separate migration work.
Do not mark R5/R6 or all LM architecture layers complete because these nine direct
operations pass. Preserve the routing plan's original workflow/caller inventory,
all consumer assertions and actual subprocess tests; record any remaining Python
authority explicitly.

## Completion sequence

1. Finish current native corrections and obtain the required hosted result.
2. Freeze exact nine-operation profiles, payload/result/limits/capability schemas,
   outer authority identities, replay comparison, diagnostics, and claim scopes.
3. Implement native service, strict transport and all direct public routes;
   independently review verifier dependencies and inherited work-budget handling.
4. Build the lossless full-corpus protocol mapping, current-policy counterparts,
   original stale-replay witnesses, new coherent Unicode/horizon cases, and
   malformed/resource recipes. Freeze new cases only after original Python replay.
5. Run the complete installed guarded campaign for both executables across the
   platform/Python matrix; compare full deterministic artifacts and exact receipts.
6. Update the tracked migration plan and LM checkboxes only for the obligations
   actually completed. Continue workflow/producer/archive routing as its own
   complete batch, retaining all original acceptance and consumer tests.

Audit limitation: source and frozen JSON inspection only. No new production
service, client, corpus, test execution, or native result is claimed here.
