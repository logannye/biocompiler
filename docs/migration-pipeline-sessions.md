# Public checked-pipeline session design

Status: the fixed-provider persistent transport, native engine and client are
implemented in source with Python subprocess tests; hosted native validation is
pending. The complete public proxy and generic callback continuations below
remain design requirements.

The public integration uses a persistent Core session containing the actual
native `Pass_manager.t`. The current process-per-request transport closes stdin
and waits for exit (`src/biocompiler/core_client.py:317`); it cannot return a usable
live manager. Reconstructing that manager from serialized accepted stage records
would violate its authority model. Do not change the existing stateless protocol.

## Required behavior

Preserve all manager operations: construction/target, completion-profile
registration, dependency mutation, pass registration, component-input policy
registration/admission, authoritative input addition, accepted reads, pass
execution and scoped result queries (`compiler/pipeline.py:379–916`). Preserve
complete immutable StageRecord/PipelineResult data, fields, enums and fingerprint
accessors. A returned build's result stays historical; its manager remains live.
Both fixed native pipelines already retain that live manager and partial failure
state. Their public build objects must retain every candidate/assembly/check/
selection/result accessor together with the same manager proxy.

Native state must retain registration history after replacement, frozen execution
contexts, complete rejected records and nontransactional callback mutations.
`run` stores a result before its final freshness check (:889); a stale error may
therefore leave an inspectable record. Callback exceptions also do not roll back
previous mutations. `get` checks current dependencies, contracts and the complete
parent chain (:646); `result` must call it afresh (:896). Adding an unrelated new
dependency differs from changing a dependency recorded by an ancestor.

## Session and callback protocol

1. Add an explicitly negotiated Core-only session mode/process entry and separate
   client transport. A live session owns native manager handles, provider handles,
   pending invocations and one lifetime work ancestor. Verify rejects this mode.
   Pin the actual executable/process generation and complete resource profile.
2. Session commands cover the full manager API plus fixed synthetic/component
   construction. Those fixed operations execute the real native pipelines and
   retain their actual manager in the session; their built-in validators never
   delegate to Python. Native reply records are immutable observations, never
   inputs that authorize reconstruction of a manager.
3. Generic trusted extension registration retains Python callable objects strongly
   and associates them with session-local handles. Native service creates and
   interns actual provider closures. A handle identifies a registered live
   provider; it is not a certificate, source hash, serialized closure or portable
   identity. Releasing/restarting a session invalidates every handle.
4. A provider closure sends an invocation containing the complete native
   PassContext and an outstanding invocation ID, then pumps nested commands while
   waiting. The Python transport invokes the original callable on its calling
   thread. Calls made by that callback to the same manager are dispatched against
   the same native state; nested calls may yield further callbacks. Native
   closures resume only on the matching outstanding completion. This works with
   the synchronous manager and avoids replaying callback side effects.
5. Bind every command/reply/callback to session generation, manager, monotonic
   command ID, parent invocation, operation and complete payload identity. Reject
   duplicate, unsolicited, cross-manager and out-of-order callback completions.
   Keep a bounded invocation stack and command outcome ledger; do not silently
   retry a mutation after an uncertain transport failure.
6. Preserve callback exception instances/tracebacks in the Python process. An
   invocation-error frame unwinds the native callback while retaining preceding
   mutations; the matching public call rethrows the original local exception.
   Native domain errors preserve existing public category/message and full native
   diagnostic cause. Fatal process/protocol failures invalidate the session;
   historical records remain inspectable but cannot reestablish live authority.
7. Charge framing, parsing, retained state and callback continuations to the same
   lifetime ancestor. Bound queued bytes, invocations, managers/providers and
   recursion, and specify cancellation/close behavior. Arbitrary trusted Python
   callback CPU cannot honestly be measured by the native work counter; account
   for this explicitly rather than claiming a total-work proof for extension code.

## Compatibility traps requiring explicit implementation

- Python registration uses producer `is` and validator dictionary equality
  (`pipeline.py:448–452`); admission uses dictionary equality (:478–479). Fresh
  bound-method objects can compare equal without being identical. The default native
  `Pass_manager.same_providers` uses physical equality. An additive trusted
  validator-comparison hook now provides the native integration point; the
  Python continuation adapter and public session protocol remain unimplemented.
  Keep distinct identity and comparison operations: do not merge equal providers
  into one identity and accidentally change self-certification checks. A trusted
  Python comparison continuation can preserve equality ordering, exceptions and
  reentrant side effects; the native manager still owns history and admission.
  Do not replace this with caller-supplied equality/acceptance flags.
- `_document` invokes arbitrary `to_dict()` (:46), and `add_input` reads an optional
  object `fingerprint` (:613–616). Native raw and BuildRequest entries correctly
  derive their own canonical/semantic identities. Preserve known typed codec
  routes. Supporting arbitrary custom identity semantics requires an explicit
  trusted adapter design; a raw fingerprint override is not an acceptable fix.
  This is an unresolved generic-API boundary, not grounds to claim default parity.
- PassResult has no eager validation (`compiler/passes.py:24`). Search status is
  checked before output materialization (:729–749), and later mapping/source-link
  checks have observable error precedence. Eagerly decoding all callback fields
  changes errors and user side effects. The bridge needs staged object/type and
  materialization continuations, or must leave the broader cutover explicitly
  pending until that behavior is implemented and tested.
- Context/result hydration must preserve existing public field shapes, tuple and
  mapping immutability, enums and isinstance behavior where callers rely on them.
  Use data-only compatibility construction or retained authored objects; never
  invoke Python acceptance/ranking/semantic constructors on native output. A
  distinct incomplete view API is not a silent replacement for PassManager.
- Generic validators are trusted extension code, as before. A fresh callback
  CheckDecision is input to native lifecycle checks, not independently native
  biological evidence. Complete migration requires porting the actual production
  validators; do not label arbitrary external callbacks as native verification.

## Implementable checkpoints

A. Freeze a protocol declaration and supplemental original observations for
   callable instances/bound methods/equality failures, A→B→A provider histories,
   callback exceptions and dependency/registration mutations, nested manager calls,
   staged invalid PassResult fields and custom authored-object conversion. Retain
   all existing 467-method captures and pending callback-dependent suffixes.
B. Implement session transport and native handle/lifetime dispatch; first prove
   live fixed-pipeline managers, all ordinary mutations/queries, partial failures,
   close/process-loss behavior and exact resource bounds. This is a useful bounded
   checkpoint but does not complete generic manager compatibility.
C. Implement trusted callback continuations and the identity/equality bridge in
   the native manager, then staged Python object marshaling. Cover registration,
   admission, reentrancy, callback exceptions and exact diagnostic precedence.
D. Add the public proxy/compatibility records and additive explicit native routes
   for PassManager and both fixed pipeline APIs. Audit downstream construct,
   molecular, molecular-design, candidate and implementation pipelines: they all
   register real callbacks and cannot become native merely by returning a proxy.
E. Run installed public-API campaigns against the pinned native executable,
   comparing complete results/state/errors and actual callback effects. Include
   malformed/replayed/session-crossing messages and forbidden Python semantic
   execution guards, with only explicit authoring/callback contexts exempted.
   Default cutover and P2 completion follow full coverage and hosted gates.

Suggested new units: `protocol/checked-pipeline-session-v1.{json,md}`;
`core/lib/pipeline/session.{ml,mli}`; a Core-only session driver outside the
independent verifier; `src/biocompiler/core_pipeline_session.py` and
`pipeline_backend.py`; native session/callback tests and an installed public
pipeline-session campaign. Native Pass_manager changes must be additive and
retain the existing trusted-native provider path and all current tests.
