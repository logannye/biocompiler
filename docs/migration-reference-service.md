# Reference workflow service migration

The reference service connects the historical Components → Construct →
Molecular pipelines to one live OCaml manager. This is shared reference
infrastructure, not a new therapeutic backend. Exact reference identity remains
distinct from complete payload construction and empirical biological behavior.
Python remains the production default until the full migration gates pass.

## Actual public operations

`reference_workflow.ml` retains the typed native preparation, registration and
completion capabilities. `callback_manager.ml` reports each successful real
manager operation to that coordinator with its actual objects and command
sequence. It does not reconstruct successful registrations or accepted records
from a serialized snapshot.

The Construct path publishes its manager, prepares admission, and requires the
actual public register-input, admit and get calls before preparing its pass.
The actual register, run and result calls then precede the independent final
check. Molecular continues with the same manager and completed Construct build:
six ordered dependency writes, profile registration, pass registration, run,
result and final check. Extra generic manager calls preserve their ordinary
behavior; only a matching operation advances a workflow phase. Explicit wrong
phases and foreign capabilities are protocol errors.

Finalization consumes the exact retained run record and result command sequence.
It performs no extra get or result call. `Pipeline_result.make` retains its
actual typed record and unresolved objects after the same structural validation
and canonical packing. An external `of_json` import still creates fresh objects.
Neither the historical result nor a build view grants fresh export acceptance.

## Authoring callbacks and public views

Each original generator or emitter lookup is observable at its original call
point, after native input parsing. The host broker distinguishes the exact,
verified default function from a real replacement. The default invokes the
native producer. A replacement executes once, retains its output opaquely, and
receives the ordinary PassResult wrapper only after native source links are
ready. Attribute reads, conversion, validation and exceptions remain at the
manager's deferred materialization points.

Each source callback carries both the actual context input and the complete
native parsed argument. They need not have identical JSON fields: valid parsing
may supply omitted defaults. Closed Python decoders create the fresh parsed
argument and retain both documents as invocation evidence; they do not execute
legacy semantic parsers. A returned native proposal is associated with that
invocation by the physical native output object, not equal content or a mutable
last-call slot. Nested calls cannot substitute another invocation's origins.

The shared admission linkage validator remains the same callable when used by
the Construct pass. Source-link comparison preserves duplicates and the
original expected-first sorting of four-field tuples, including host attribute
reads, comparison order and exceptions.

Public producer views retain the specific original constructor sharing:
Construct layout objects come from its freshly parsed request; Molecular
placement objects come from its freshly parsed Construct, while reference
selection comes from the authored request and policies come from their actual
class defaults. Final build candidates and reports are fresh parsed views.
MolecularBuild.construct retains the exact upstream ConstructBuild.candidate.
Historical manager, result and artifact identities remain separate from equal
frozen JSON payloads.

## Authority and resources

All native operations use the owning channel's lifetime work budget and
cumulative retention accounting. Manager document reductions also bound native
reference parsing, generation and emission. The application declaration is
identical in the checked-in protocol, OCaml service and Python adapter.
Host object references convey identity only; they cannot import acceptance.
The finite reference SerializationError leaves preserve logical rejection,
while resource, malformed protocol, internal, phase and capability failures
remain fatal. Python host execution retains the existing trusted authoring
boundary; native limits do not claim to bound arbitrary host code.

## Validation still required

The source batch has passed its focused Python controls and source review. Native workflow
tests and the framed service suite are complementary evidence, not substitutes
for the unchanged public workflow campaign. The frozen original 18-method,
27-manager, 439-operation corpus remains unchanged. Its canonical historical
source counterpart proves the original baseline; that child does not validate
the current bridge. Installed current-runtime replay must independently retain
actual operations, callbacks, object identities, exceptions and complete
original test outcomes.

Before acceptance, execute native compilation and all direct suites on both
hosted platforms, the complete Python and installed-runtime campaigns, all
36 integration/release jobs, and independent artifact reconstruction for the
exact source revision. The additional reference package, admission and behavior
consumers remain separate required migration work. SDK/CLI/Studio routing,
canonical export ownership, prebuilt distribution and default cutover stay open
in the [session roadmap](language-migration-roadmap.md).
