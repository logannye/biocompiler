# Trusted pipeline callback continuations

Status: additive library implementation under active development. The
fixed-provider `pipeline-session-v1.json` profile remains unchanged. The new
channel declaration binds transport only; the manager dispatcher, Core entry
point and typed public routing remain pending. This contract does not establish
installed compatibility or permit default cutover.

## Authority and ownership

One Core process owns the actual manager, accepted and rejected records,
registration history, physical native provider closures, dependency freshness,
contract checking and scoped completion. Python owns authored objects and
explicitly registered extension callables. It executes their observable Python
operations only when the native manager requests the corresponding continuation.
Native fixed producers and validators remain native; the extension mechanism
cannot replace a built-in checker with a reported PASS.

A provider token denotes a native-minted closure in this live process. The client
retains the corresponding callable by physical identity, without coalescing
objects that merely compare equal. Tokens have no meaning after process loss.
When the native manager compares distinct validator closures, it asks the
trusted client to perform the actual Python equality operation, including
reflected comparison, Boolean conversion, exceptions and reentrant calls.
Neither a request fingerprint nor an imported stage record registers a provider.

Custom object serialization is authoring. A to_dict call or fingerprint property
must execute at its original point in the operation, after earlier native
preconditions. A supported custom identity is obtained from an actual retained
authored object through that outstanding continuation; there is no ordinary
add-input fingerprint override. Typed BuildRequest identity remains derived by
the native request codec. Canonical document identity, model-conditional checks,
custom extension authority and empirical evidence remain distinct claims.

## Framing and nested execution

The new channel library uses bounded length-prefixed UTF-8 JSON, a separate
protocol/profile and complete hello negotiation. Its
[declaration](../protocol/pipeline-callback-channel-v1.json) binds every transport
frame field and requires an exact application declaration. The application must
bind its operations before entry-point wiring. Existing one-shot and fixed-session
framing/capabilities retain their current contracts.

Client frames have a monotonically increasing sequence across commands and
continuation completions. Server frames have a separate monotonically increasing
event counter across invocation, response and terminal frames. A command binds
its active parent invocation, operation and payload. Its response binds that
original command sequence and the SHA-256 of its exact request bytes; nested
commands may complete before their parent without changing this binding.

An invocation binds the session, native-minted invocation identity, parent
invocation, active command identity, action and complete arguments. The server
retains its exact frame identity. A continuation may complete only the top
outstanding invocation and must bind its exact body hash. While awaiting that
continuation, the native stack can execute correctly parented nested commands
against the same manager. A continuation needs no separate successful command
response; resuming it eventually produces the original command response.

Unsolicited, duplicate, cross-session, wrong-parent, stale or reordered frames
invalidate the session. A fatal frame or uncertain write is terminal. The client
must not retry mutations or reconstruct acceptance from serialized observations.

## Deferred objects and exception preservation

A PassResult is held as a live local object. The native manager checks result
kind, search status and output presence before requesting output conversion. It
checks the output schema and operations before asking for source links; it
checks correspondence before observation maps and obligations. Iteration and
attribute access must retain the original short-circuit behavior. A single eager
serialization of the whole result does not satisfy this contract.

Admission and authoritative-input conversion likewise occur only after the
native prefix checks. Configuration conversion follows accepted-source and
contract preconditions. The public adapter must also preserve the different
synthetic/component history-materialization order before fixed initialization.

Exception frames carry bounded opaque local handles, not serialized acceptance
or a synthesized replacement exception. Python retains the actual exception,
original traceback tail, explicit cause and context. Reentrant failures can be
caught or propagated by the original callback. Native mutations before failure
remain in the real manager. Re-raising occurs outside internal transport except
blocks so transport errors do not silently replace the user's exception context.

## Resources and validation

All native command, framing, import, continuation and publication work consumes
one lifetime ancestor. Bound bytes, JSON nodes, pending invocations, providers,
object/exception handles, command counts and native retained state cumulatively.
Check allowances before allocation and preserve a prepaid terminal response.
Arbitrary trusted Python callback CPU and opaque Python closure captures cannot
be measured by the native work counter; the contract must state that limit rather
than claim a bound on extension execution. Process cancellation closes authority.

Preserve the existing 467-method capture, 91,566 manager events, 1,596 callbacks,
34 equality cases and all fixed-pipeline observations. Add an independent original
Python supplement for deferred conversion, nested run/register/admit, exception
identity and short-circuit iteration; its observer must not itself invoke custom
converters. Compare complete results, errors, event order and before/after state.
The installed campaign must execute actual native continuations, retain complete
framed traffic and rehash source/run/binary authority on both hosted platforms and
both Python versions. Local Python fixtures and static native review do not
establish native or public-workflow parity.

## Implementation boundary and remaining compatibility

`Pass_manager` now exposes trusted deferred object and registration capabilities.
`Host_bridge` maps those capabilities to the closed object-broker actions;
`Callback_channel` owns framed continuation binding and nested command dispatch.
The Python object broker retains actual callables, objects and exceptions.
These are separate library responsibilities. None imports accepted records or
reconstructs a manager from inspection data.

Host SourceLink objects remain available to host validators through a dynamic
sidecar, restored after nested calls and exceptions. A native validator cannot
currently consume that sidecar; the manager rejects this mixed path before the
validator can certify empty substitute links. Supporting it remains necessary
for full public compatibility. Original mapping iteration order and shared
object identities likewise require retained context sidecars; sorted canonical
JSON alone cannot reproduce those Python observations.

Canonical JSON also removes custom Python scalar-subclass comparison and hash
behavior that the old freezer can retain. The current seam does not claim parity
for such behavior after freezing. Before public cutover, supported authoring
semantics must have explicit coverage or an intentional versioned declarative
restriction; incidental agreement on plain JSON fixtures is insufficient.

The original six patched-registration fixed calls require their original
observable registration interception point. Three invalid configuration-type
calls require original boundary validation, and one mocked whole-function call
requires its original mock observation. The 287 callback-dependent observations
stay pending until actual installed adapters replay their complete call chains.
Neither new unit fixtures nor an earlier supported prefix closes that inventory.
