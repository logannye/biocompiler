# Checked pass-manager migration

This P2 checkpoint implements native contract records and an in-memory checked
manager. Native compilation and runtime validation remain hosted-only and pending.
It does not route the public pipelines or grant package/export acceptance.

## Authority and retained behavior

`Pipeline_contract` owns twelve immutable record types: source links, producer
obligations, scoped obligations, check specifications and decisions, pass
contracts and contexts, component-input contracts, completion profiles, stage
records, pipeline results and pass results. Original serialized records retain
all fields and compact UTF-8 identities. Records without an original serializer
use complete field observations without adding an artifact schema. Structural
import of a claimed accepted stage creates a historical record only.

`Pass_manager` owns live registrations, exact physical callback identities,
provider history, root dependencies, stage records and completion profiles.
There is no state/receipt import operation. Trusted native provider functions
receive the same caller-owned work ancestor. A producer cannot register as its
own independent validator. Re-registering an old contract with changed providers
requires a version change even after intervening registrations.

Every accepted read checks current dependency roots, registered contracts and
complete ancestors. A pass freezes its input/configuration/dependency snapshot,
executes the producer and independent validators, records the result, and then
rechecks the current graph. Dependency changes during callbacks therefore cannot
leave a usable accepted result. Nonpassing stages remain inspectable but cannot
be consumed. No-candidate preserves its search configuration and does not mean
infeasibility. Scoped completion preserves unresolved empirical obligations.

Raw roots derive their identity from their complete document. The separate typed
BuildRequest entry derives its semantic identity using the native BuildRequest
codec. No externally asserted fingerprint override is accepted. CandidateRequest
and ImplementationRequest use complete-document identities and therefore use the
raw entry. The later fixed pipeline work must retain each original typed codec
and fresh source validation before this boundary.

## Resource profile

The new in-memory profile bounds records and distinct providers (10,000 each),
cumulative retained keys/values (1,000,000), cumulative retained bytes (64 MiB),
callback and ancestor depth (128 each), and individual documents (16 MiB and
250,000 keys/values). Callers may reduce these eight controls. Retention accounting
is conservative and cumulative, with no refund. The caller supplies one lifetime
work budget; nested callbacks and all manager operations share it. It cannot be
reset by a method call. Existing direct and workflow protocol profiles are unchanged.

These limits are explicit native resource boundaries. They do not retroactively
claim that arbitrary Python objects or unrestricted callbacks have identical
resource behavior. Fixed production providers must cooperate with the shared
budget; no public wire input can register code or fabricate a callback identity.

## Evidence and remaining work

The prior synthetic corpora ran the 21 original pipeline tests but retained zero
manager API observations. A separate capture now runs the complete inherited
cohort plus all discovered manager consumers, including package and Studio
callers. It retains constructor and property observations, ordered manager
commands, callback bodies/identities/closures/contexts/effects, exact exceptions,
and complete manager state before and after calls. Native replay must account
for every captured context; unported real compiler callbacks remain explicit
pending obligations rather than substituted acceptance results.

The focused fixtures independently execute original Python assertions and retain
thirteen complete domain records, nineteen original constructor rejections, full
Intent-to-Mechanism stage records and a freshly checked Components root. Native
unit sources exercise provider identity, scoped completion, stale ancestors,
callback-time mutation, rejected stages, admission, all eight reduced controls
and an exact/one-unit-short lifetime work boundary. Python fixture/static passes
do not validate those native tests.

P2 remains open until the full original manager corpus, fixed native synthetic
and component pipelines, public manager lifecycle/proxy contract, installed
campaigns and all required hosted gates pass. The process-per-request protocol
cannot preserve native mutable state by trusting serialized accepted records;
public integration needs genuine native sessions or independently replayed
history with explicit callback continuations. P3 canonical package/export work
and default cutover remain dependent on that integration.

## Separate large-artifact obligation

A producer file channel alone would not remove current semantic limits: direct
services count full records and nested receipts against 32 MiB, producer leaves
retain their own resource ceilings, several domain codecs cap 16 MiB inputs,
and public views use the direct decoder. Full large-result support needs a
separate versioned producer artifact profile, Core-only descriptor dispatch,
contextual bounded codecs, one aggregate budget across parsing and publication,
and complete valid semantic fixtures above 32 MiB. Preserve the existing direct
profiles and exact pretty-JSON publication ceiling of 64 MiB including newline.
Serialized-length fault fixtures alone cannot prove that compatibility.
