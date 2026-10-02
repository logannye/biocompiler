# Native realization protocol implementation audit

Preserved implementation checkpoint: the reported component-behavior resource fixes are included in the PR56 correction. Their hosted validation is pending. The protocol below remains proposed and unimplemented.

Read-only design checkpoint, 2026-10-02. This proposes the next coherent batch;
it is not an implemented capability, native validation receipt or roadmap closure.
Reviewed the routing plan, actual service/producer-service dispatch, wire protocol,
all four public realization checkers, dependency calculation, domain codecs and
resource interfaces. No production/shared files, native builds, Git or network
operations were performed. Root is separately preserving PR56 and earlier gates.

The exact proposed capability objects, payload inventories, schema names,
encodings and complete default resource trees are saved in
`migration-realization-protocol-profiles.json` beside this document. Values
were assembled from literal native interface review; they have not been obtained
from an executable. Root agreed the profile and reduction decisions below.

## One nine-operation batch

Add `core/lib/service/realization_service.ml/.mli`, with public immutable profiles
and a dispatch helper. Delegate exclusively to public checker APIs. Base
`Service.handle` dispatches all nine operations for both roles; the existing
producer service continues to delegate them to Base. Do not move handlers into
producer_service or link synthetic/architecture producers into verification.

Every payload has required `profile` and `limits`, followed by exactly the fields
below. Replay alone adds `assessment`, containing the complete historical inner
report, not its old protocol wrapper, fingerprint or PASS flag.

| Family/profile suffix | Operations | Other exact fields | Delegate/result |
| --- | --- | --- | --- |
| `realization` | `realization-dependencies`, `verify-realization`, `replay-realization` | behavior, contract, domain, target, mechanism, observation_map, history, until | Realization_check.dependencies or check; Dependency_snapshot or Check_result |
| `synthetic_candidate` | `verify-synthetic-candidate`, `replay-synthetic-candidate` | expected_request, candidate, history, until | Synthetic_candidate_check.check; Check_result |
| `component_behavior` | `verify-component-behavior`, `replay-component-behavior` | expected_request, assembly, history, until | Component_behavior_check.check; Check_result |
| `component_assembly` | `verify-component-assembly`, `replay-component-assembly` | expected_request, candidate, assembly, history, until | Component_assembly_check.check; Composition_evidence.Result |

Profile IDs are `biocompiler.core.<suffix>.v1`. Do not accept a profile for another
family. `limits` is null for fixed defaults or an object containing exactly
max_work, max_monitor_items, max_request_bytes, max_report_bytes, max_report_nodes.
Every value must be an actual positive integer no larger than its native ceiling;
reject Boolean/float/null members, incomplete objects, unknown keys and increases.
Compare arbitrary integers to ceilings before converting them to machine ints.
No checker-version overrides, file paths, callbacks, imported checked tokens,
producer witnesses, alternate target injection or undocumented optional fields.

Capabilities expose four profiles under the fixture's exact keys. Include all
five validation scopes: dependency-only plus the four checking scopes. Preserve
existing architecture/intent profiles. Update **both** Service.capabilities and
Producer_service.capabilities claim text: their current unconditional “No
candidate execution” wording becomes false after this batch.

## Decode, delegate, replay and publish

1. Preserve current Protocol framing, exact top-level fields, byte/JSON checks,
   role/version/request/operation identities and process exit discipline. Check
   exact payload keys, profile and the five reduction controls in that order.
   A profile mismatch is a protocol error, proposed diagnostic
   `realization_protocol_profile`; malformed fields retain strict JSON diagnostics.
2. Create one operation budget before domain imports. Reserve the complete raw
   payload, including controls and replay assessment, then charge imports and
   authority hashing before performing them. Import fields in the documented
   table order; reserve the history list before allocating typed frames. Decode
   historical assessment structurally on replay, but never consult its claimed
   dependencies/outcome to select or skip a fresh check.
3. Decode `until` as null/None, Json.Int/Runtime_number.Integer or
   Json.Float/Runtime_number.Real without coercion. Non-numeric types are strict
   wire errors. Do not eagerly call Runtime_number.of_json: huge integers would
   become evaluation_nonfinite before the direct checker's horizon validation.
   Preserve each delegate's existing semantic error precedence. Negative values
   and huge integers remain rejection cases, never sanitized into a new horizon.
4. Call the exact public delegate once with all original authority, exact history,
   optional horizon, mapped limits and shared Work_budget parent. The three full
   request wrappers already perform fresh Checked_request validation; the service
   must not duplicate/reorder it. The direct model API deliberately receives no
   BuildRequest and must not acquire a source-lowering or synthetic-provenance
   claim. Dependency-only calls must not execute either model or claim acceptance.
5. Replay independently computes the entire fresh result. Compare the complete
   report-family canonical bytes of the decoded historical report to fresh bytes,
   and verify the corresponding fingerprint. Do not compare only dependencies,
   freshness, selected fields or outcome. Proposed mismatch diagnostic:
   `realization_assessment_mismatch`, no result. FAIL, UNKNOWN and UNSUPPORTED are
   valid historical outcomes to reproduce; replay success does not turn them PASS.
6. Build the fixed result wrapper, pre-reserve complete publication and bound the
   final Protocol.response envelope before encoding. Return Protocol.Ok with empty
   transport diagnostics for complete semantic results of every outcome. Preserve
   Diagnostic.Error as protocol error with no result, including source authority,
   horizon, resource and assembly precondition errors. Do not indiscriminately
   copy verify-lowering's special unsupported-prefix conversion into these routes.

Outer report schemas are `biocompiler.core.<suffix>_assessment.v1`; dependency
schema is `biocompiler.core.realization_dependencies.v1`. Exact common fields are
in the JSON fixture. Resources include both complete protocol accounting and the
delegate's complete nested effective limits, not just a profile label. Replay
returns the same fresh wrapper as verification under the same supplied controls.
Do not add a second copy of a potentially 32 MiB report as a JSON text string.

## Exact authority and canonical identity

`supplied_authority_fingerprint` is core UTF-8 canonical SHA-256 of **every raw
payload field except assessment**. In particular it includes profile, supplied
limits, full source coordinates, exact history and explicit until. Null limits
and an explicit default object therefore bind different supplied documents even
when successful inner reports are identical. Request ID and operation remain
bound by the Protocol envelope. Verify/replay of the same family use the same
authority digest because assessment alone is removed. Never hash a domain-
normalized replacement in place of this raw authority.

`authority_identities` has an exact family-specific shape:

- Direct model: behavior_fingerprint, behavior_artifact_ascii_fingerprint,
  contract_fingerprint, domain_fingerprint, target_fingerprint,
  mechanism_fingerprint, observation_map_fingerprint, history_ascii_fingerprint.
- Full-request families: request_fingerprint, request_artifact_fingerprint,
  history_ascii_fingerprint, plus candidate_fingerprint and/or
  assembly_fingerprint exactly when that authority is present in the payload.

Use typed semantic/artifact getters and normalized complete Input_frame.to_json
history for these identities; raw input identity remains separately pinned above.
These shapes also bind assembly's history/candidate/request authority, which its
inner CompositionResult dependencies alone do not contain.

CheckResult and DependencySnapshot fingerprints use **compact ASCII** JSON;
CompositionResult and outer/raw authority use **compact UTF-8** JSON. The fixture
names those profiles python-json-ascii-v1 and existing python-json-v1. Preserve
1 versus 1.0, negative zero, null versus effective horizon, ordered arrays and
source file/line/function. DependencySnapshot's behavior_artifact and history
are ASCII pins even though its contract/domain/target/mechanism/map entries are
their existing UTF-8 domain fingerprints. Do not apply one encoder to everything.

InputFrame and DependencySnapshot have **no schema_version field**. Frame is
exactly time/signals/contacts, sample is value/present/high/low. Numeric sample
shorthand is accepted and normalized by the existing native importer, so raw
history and normalized dependency history can legitimately differ. Never sort,
deduplicate, discard later frames or replace supplied horizon during routing.
Dependency-only identity construction is not full history/model validation.

## Resources and concrete prerequisites

Use one ancestor 50M-or-reduced Work_budget for raw import, authority identity,
fresh checker, replay comparison and wrapper publication. Each delegate receives
the same five reductions and that parent; do not allocate a fresh full allowance
after imports or for replay. Charge cached immutable sizes before repeated
canonical work. Bound input-list allocation, derived result retention and both
historical/fresh reports before copying or formatting them. Service-local report
reservation can conservatively use Realization_budget ASCII counting even when
the final wire transport is UTF-8; publish that distinction in resources.

The protocol layer reserves the complete payload against its reduced input
budget; nested checker input reservations remain their existing documented
fragment accounting. Preserve 16 MiB streaming request versus 32 MiB response,
250k wire values versus checker key/value nodes, depth128, 4 MiB decoded request
strings and 4300-character number tokens. A 32 MiB inner report may not fit a
16 MiB replay request with authority: explicit rejection is required, not a
hidden alternate transport or limit increase. A report fitting inside a checker
can still exceed its enlarged result/response envelope and must fail publication.

Two current defects were reported to root and assigned to synthetic_domains:

1. Component_behavior_check can reach zero remaining work before reconstruction.
   Components.make_limits accepts zero, then reconstruction raises
   component_model_limit; burning zero work does not recognize the actual exhausted
   custom ancestor. Match assembly's zero-allowance B.charge 1 guard.
2. Component_behavior_check currently invokes Composition_check with a parent but
   default linker limits. Map max_monitor_items to max_items, max_request_bytes to
   max_input_bytes and the other three unchanged; publish/pass composition limits.
   The agent confirmed the new limits_json key is `composition`. The fixture
   already specifies this corrected resource tree, also nested under assembly.

## Dependency boundaries and evidence gates

Add bioc_realization_checker to bioc_service's explicit Dune dependencies.
Verification's exact transitive closure becomes bioc_wire, bioc_domain,
bioc_checker, bioc_service, bioc_realization_checker, bioc_semantics,
bioc_candidate_runtime, digestif, zarith. Continue excluding bioc_compiler,
bioc_synthetic_producer, bioc_producer_service and bioc_source_adapter. Candidate
runtime still excludes source semantics/checkers. Private realization_monitor,
synthetic_provenance and synthetic_component_authority remain inaccessible.
Update exact link-boundary inventories and producer-leak mutation/build tests;
do not broadly weaken verifier exclusions to permit every runtime library.

Implement native service tests for all nine routes and both roles, full results
and dependencies, replay of all four outcomes, every profile/key/limits mismatch,
numeric and Unicode distinctions, source relocation, stale authority, invalid
horizon precedence, source-only/component-only mutation, custom ancestor
exhaustion, exact/one-under wrapper budgets and repeat-after-failure isolation.
Tests must compare full report bytes and fingerprints, not just outcomes/counts.

Retain the existing 4,119 captured acceptance/dependency calls with original
context/call identities: 1996 dependency, 1080 realization, 906 synthetic,
85 component-behavior, 52 assembly (41 results/11 exceptions). Existing cohort
has no Unicode authorities; coherent additional source/history/contact/diagnostic
Unicode vectors are required. Preserve all five patched-checker witnesses: fresh
direct routing uses pinned current native policy and replay rejects historical
version-mutant reports. Do not add a checker-version override.

Exact five mutation identities and projection details are being saved separately
by synthetic_capture in migration-realization-protocol-conformance-plan.md. SDK/CLI
constructor traps and guarded installed routing remain root's parallel client
review. RealizationRequest Python construction invokes verify_lowering; do not
mistake it for a harmless hydration codec. All hosted Linux/macOS native and
Python3.11/3.14 installed/sharded/product/browser/reproducibility/aggregate gates
remain mandatory. No native service implementation or new full corpus capture
was started in this audit.

The JSON profile fixture is ready for exact client negotiation design. Full
concrete nine-operation request/result example documents are not included in
this checkpoint; derive them from the retained original corpus during the
implementation batch and label original Python results separately from hosted
native validation. R5/R6 workflows, exploration, reduction, pipelines, archive
authority, default routing cutover and full LM completion remain separate work.
