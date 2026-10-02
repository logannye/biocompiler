# Native workflow presentation checkpoint and remaining integration

Implementation checkpoint, 2026-10-02. The native v2 presentation service, strict
Python transport, immutable views and separate source-only preflight capability
are implemented. Python fixture and campaign-tool checks pass; hosted native and
installed-runtime validation remain pending. Public SDK and CLI routing remain
unfinished. The exact contracts are recorded in
[`workflow-public-contracts-v1.md`](../protocol/workflow-public-contracts-v1.md).

## Native authority and control size

The new `verification_workflow_presentation` capability advertises workflow
semantic profile v2, service implementation v0.2 and semantic receipt v2. The
original v1 capability, profile, complete artifact/receipt bytes and two-operation
artifact transport remain unchanged. The v2 profile SHA-256 is
`a15cfc3423bc7adc739e37ca81f9ecccde284cb22d666a4b3d0bbd768762d01c`.

The implemented compact receipt addition is:

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

Frame counts are integers for reduction and null otherwise. OCaml derives the
exit code from the typed result: check `passed`, exploration `all_passed`,
reduction `one_minimal`; successful replay returns zero, including retained
failure or nonminimal evidence. Reduction frame traversal is precharged against
its cached complete canonical size before either list length. Every phase shares
the operation budget.

Full diagnostics, bounds and counterexamples remain in the complete artifact.
Do not duplicate a potentially 64 MiB summary inside the 65,536-byte control
receipt. Exploration's eight derived fields are copied from the native report,
not recomputed by Python; bounds views project the corresponding native counts.
The backend uses only the individually audited CheckResult, RequirementCoverage
and FailureSignature leaf codecs. Legacy workflow/request/exploration
constructors remain forbidden on native output.

## Exact legacy rendering

Canonical workflow bytes remain unchanged. The CLI formatting contract remains
`json.dumps(..., indent=2)` with default ASCII escaping, original insertion order
and one stdout newline. Common keys are record fingerprint, request fingerprint,
operation, mode, intended use, human admission and claim scope, followed by
operation-specific keys in the current CLI order. Replay text and optional output
path remain last.

The immutable views restore diagnostic, counterexample, coverage, bounds,
signature, InputFrame and SignalSample field order structurally. Arbitrary
fixed-suffix signal/contact map order comes from the separately retained frozen
raw authority because canonical artifact sorting cannot recover it. This context
controls formatting only; it cannot alter native field values or identity.

The baseline is now frozen from 70 actual child processes: 66 console invocations
and four module invocations, including all 16 original observations and a
noncanonical-order authority case. Complete stdout, stderr, exits and files are
retained. The inventory pin is
`a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7`.
Current-source recapture preserves actual metadata separately and permits only
the explicit reviewed source-scope comparison projection. No observation or
content blob is normalized. Actual native CLI reproduction remains unvalidated.

## Command and historical-file precedence

V2 controls contain exactly `{profile, limits, command}`. SDK commands are null;
CLI commands are explicit. After fresh `decode_request_in`, native handling
checks command agreement before workflow execution or historical-record loading.
Mismatch diagnostic `workflow_protocol_command` retains the original message:
`Command and frozen verification operation disagree.` The receipt binds command;
replay uses `synthetic-replay`.

Original CLI replay also validates source before opening its historical file.
The implemented `verification_workflow_authority` service and separate
`artifact_transport_authority` profile supply source-only preflight to preserve
that precedence. Planned CLI integration must freeze source bytes, preflight,
then read the historical file and perform ordinary fresh replay using those same
source bytes. Preflight performs no workflow evaluation and returns no acceptance
token. Replay must validate afresh; each operation has its own explicit budget.

## Remaining integration and required evidence

Hosted CI now includes installed presentation and source-preflight campaigns in
all four existing realization variants, followed by comparisons of complete
artifacts, receipts and executable identities. The source contains 88 native
test suites, including preflight. These gates must pass for the exact revision;
Python fixtures or previous v1 runs cannot substitute for native validation.

Next add the explicit public SDK route and CLI routing without changing default
behavior or failure precedence. Preserve command usage output, bounded atomic
publication and all original observations. Add installed immutable-view/public
CLI campaigns across both executable roles, Linux/macOS and Python 3.11/3.14.
Existing v1 goldens and gates remain mandatory. This checkpoint does not close
R5 or any language-migration completion item.
