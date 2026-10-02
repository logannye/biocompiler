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
manager API observations. A separate capture passed all 467 unchanged original
tests both before instrumentation (37.358 seconds) and during instrumentation
(329.474 seconds), including package and Studio consumers. Both actual child
process outputs remained exact. It retains 91,566 events, 1,596 callbacks,
2,284 provider identities and 19,412 complete documents, including constructors,
properties, ordered commands, callback bodies/identities/closures/contexts/effects,
exact exceptions and complete manager state before and after calls.

The complete index uses deterministic gzip storage with independently pinned
compressed and expanded identities; all complete documents remain content-addressed.
The bounded native projection retains all 21 original manager-test contexts.
Its driver implements the original callback bodies and compares complete state,
results and errors. Other real compiler callback cohorts remain retained with
explicit pending native parity obligations. No recorded acceptance result becomes
a native action, and native execution remains pending hosted validation.

Eight Python integrity tests pass, including byte-for-byte reconstruction of the
578,996,698-byte original capture from the full ledger and every document. The
[archive manifest](../tests/conformance/checked-pipeline-full-v1.json) pins full
inventory `1b8ce09b5bb39e9bec43dae64c00291716a5971349eafd14c1f9f7e2a6bb6117`;
the [native projection](../tests/conformance/checked-pipeline-v1.json) pins
`1c9391db642c9375cc73cd2e28fc49cc6fb5966e0c30d6e430cfe49946e0dcb6`.
Another 51 focused fixture, boundary, CI-registration and inventory tests pass.
These checks ran on Python 3.14.6 / macOS arm64. Three new native suites bring
the hosted inventory to 94 suites per platform; all 36 workflow jobs remain
required for exact-revision integration.

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

## Fixed pipeline implementation checkpoint

`bioc_pipeline` implements fixed synthetic and component pipelines through actual
native producers and independent checkers. The foundational compiler and verifier
keep their existing dependency boundaries. Results retain live manager authority,
complete records, source correspondences, unresolved obligations and partial
failure state. Ordered source-map insertion is preserved when forming source-link
arrays. `Lowering.lower_with_budget` shares the caller ancestor through lowering
and independent preservation checking; the legacy `lower` entry point is retained.
Opaque legacy imports prepay a scalar-aware codec envelope before decoding.

The supplemental capture reran all 467 original tests unchanged: baseline 38.717s,
instrumented 194.196s. It retains 136 full calls, both actual child outputs (zero
fixed calls), all 309 manager constructors, 445 documents / 104,594,191 bytes and
850 post-return observations. Full fixed inventory:
`28d8befb9fad240a80edf341ad64f822517f6e65f43c611966c9d0b7ff43d652`.
Separate native companions keep complete provider objects in 841 content-addressed
blobs / 34,695,681 bytes, below existing parser limits without altering full indexes:

- Fixed native index: `ce976b30aa5e0a8f6477cc027d7bec4a780a31a567f19cfb0993b10839d58f6d`.
- Continuation native index: `45c78ef53692cb71fe644ea98331c9ce8caa1bda3b1eab67a93061f30557a9eb`.

Eight Python integrity tests passed in 7.093s. The new native driver executes
126 eligible original calls and 563 actual manager commands; it compares complete
results, state, errors and all 121 successful return boundaries. It explicitly
retains ten Python mock/type-dependent calls and the callback-dependent remainder
as pending coverage. Provider identity translation is diagnostic only. Expected
records never establish native acceptance. The additional lowering budget suite
checks exact and one-unit-short caller boundaries against original lowering cases.
These two suites raise the hosted total to 96; native compilation/execution and
all 36 exact-revision jobs are still required. No public service/session cutover
is included in this source checkpoint.

## Validator comparison compatibility

The original Python manager distinguishes physical producer identity from
validator dictionary equality. Distinct bound-method objects can compare equal;
comparison itself can raise, mutate dependencies or reenter the manager. The
native manager now accepts an optional trusted `validator_equivalent` function.
Its default preserves physical comparison. The function is invoked only after the
physical-identity shortcut, in the previous mapping's insertion order, with the
same lifetime work ancestor. Errors and completed mutations remain observable.
Producer history, provider retention and self-certification still use physical
identity. No serialized flag or claimed receipt supplies comparison authority.

The supplemental original-Python oracle retains 34 cases, 78 actual manager
events, 28 comparison events and 18 raised events, with complete before/after
state and source pins. Inventory:
`81462d7732ba6205791831030b21ebcbaa3f8d4c58837deb38d072b3e1025d45`.
Six local integrity tests pass. The native replay is mandatory on both platforms;
its execution remains pending. The hook is a prerequisite for a trusted live
callback adapter, not an implemented Python session transport. Public generic
callbacks, deferred object conversion and the remaining integration obligations
are detailed in the [session design](migration-pipeline-sessions.md).

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
