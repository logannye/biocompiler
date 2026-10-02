# Native workflow presentation and source preflight

Implementation checkpoint, 2026-10-02. These are experimental opt-in contracts.
The existing public workflow functions and CLI still use Python. Hosted native,
installed-package and complete four-runtime validation remain required before
this implementation can be treated as validated migration evidence.

## Compatible presentation extension

The original `verification_workflow` capability, its v1 semantic profile, both
operations and its complete artifact/receipt bytes remain unchanged. The new
`verification_workflow_presentation` capability advertises
`biocompiler.core.verification_workflow.v2`, implementation
`biocompiler.ocaml.verification_workflow_service.v0.2`, and presentation profile
`biocompiler.core.verification_workflow.presentation.v1`. Its complete profile
SHA-256 is `a15cfc3423bc7adc739e37ca81f9ecccde284cb22d666a4b3d0bbd768762d01c`.

The same run/replay operations accept exactly `{profile, limits, command}` for
v2. `command` is null for an ordinary SDK request, or the explicit CLI command.
The core validates complete source authority before checking command agreement;
command disagreement fails before workflow execution or historical-record loading.

The v2 receipt binds the command and contains exactly this additional metadata:

```json
{
  "presentation": {
    "profile": "biocompiler.core.verification_workflow.presentation.v1",
    "command_exit_code": 0,
    "original_frames": null,
    "reduced_frames": null
  }
}
```

Exit policy is native: check uses `passed`, exploration uses `all_passed`, and
reduction uses `one_minimal`. Successful replay returns zero even when faithfully
reproducing failure, unknown, unsupported or nonminimal evidence. Frame counts
are native integers only for reduction. All calculations and receipt encoding
share the operation budget. Full diagnostics, bounds and counterexamples stay
in the complete artifact; they are never squeezed into the 64 KiB control channel.

## Source validation before historical-file access

The original CLI imports and validates the independent request before opening
its historical report. A byte-based replay transport alone cannot preserve this
order when the historical file is missing, oversized or invalid UTF-8.

The separate `verification_workflow_authority` capability implements
`validate-verification-workflow-authority` under semantic profile
`biocompiler.core.verification_workflow_authority.v1`. Its complete profile
SHA-256 is `3f2328785095df64e4eee9f4210eebb8282be8b68d3594bd2bdaa1e92a611e2e`.
It accepts exactly `{profile, limits}`, freshly validates complete source
request authority, and emits the complete normalized canonical request. Its
receipt binds raw authority and normalized request identities, executable,
request ID, modes, versions and effective resource limits. Scope is strictly
`fresh_source_authority_only`; no workflow is evaluated and no acceptance token
is returned.

The capability `artifact_transport_authority`, profile
`biocompiler.core.artifact_transport.authority.v1`, uses the same bounded inherited
file descriptors and framing as artifact transport v1, but advertises only this
operation. Both request and response bind the selected transport profile. The
original transport profile continues to advertise exactly its original two
operations. Preflight accepts no retained-record descriptor.

The planned CLI freezes source bytes, invokes native preflight, reads the
historical file only after success, and invokes ordinary fresh native replay
against those same frozen source bytes. Replay revalidates the request; the
preflight result cannot replace that check. Each operation has its own explicit
budget. Neither an earlier successful preflight nor a stored receipt can grant
subsequent workflow or export acceptance. This ordering is implemented as a
protocol capability; CLI routing itself remains unfinished.

## Python output and input responsibilities

`WorkflowClient.run_public/replay_public` and `AuthorityClient.validate` strictly
negotiate their own complete profiles and bind all artifact bytes. They never
fall back to Python semantic execution. The original raw workflow client keeps
its v1 contract.

`workflow_backend` exposes distinct immutable native views of complete records.
It copies native derived fields, preserves exact UTF-8 workflow identities and
ASCII check-leaf identities, and returns defensive dictionaries. It restores
legacy formatting order from the separately bound raw authority where canonical
key sorting would otherwise lose that order. These views do not impersonate
legacy dataclasses or invent nested semantic fingerprints.

Only individually audited `CheckResult`, `RequirementCoverage` and
`FailureSignature` codecs hydrate output leaves. Legacy workflow, request,
exploration, reduction and bounds constructors never validate native output.
Legacy already-authored request/record objects may be serialized in an explicitly
marked input phase. Any derived values computed by those old input serializers
are untrusted historical claims, checked afresh by OCaml; the serialization
marker ends before transport and native-output exposure. The old workflow,
evaluator, lowering and acceptance routines are never a fallback.

## Evidence and remaining integration

The frozen CLI baseline contains 70 actual child processes, including all 16
original observations, 66 console invocations and four module invocations. It
retains full stdout, stderr, exit codes, input/output files, source bytes and
import audits. Its inventory pin is
`a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7`.
Current recapture keeps actual source metadata as separate evidence; its only
allowed comparison projection replaces the reviewed source-scope metadata.
Every observation, retained source byte and full content blob remains exact.

Hosted CI retains all existing gates and adds installed presentation and source
preflight campaigns within the four existing realization variants, followed by
complete comparisons of every result and receipt plus native executable rehashing.
Native tests include the separate source preflight suite (88 suites total).
Source implementation and Python transport fixtures do not establish hosted
native success. Public SDK/CLI routing, installed view/CLI conformance, pipelines,
archives, exports, distribution and default cutover remain open on the roadmap.
