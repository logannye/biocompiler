# Live native manager and typed Python views

Status: source implementation complete for the declared additive profile; hosted
acceptance and public default cutover are incomplete. The exact application is declared in
[pipeline-callback-manager-v1.json](../protocol/pipeline-callback-manager-v1.json).
It runs only in Core through `--pipeline-callback-session-v1`, over the existing
bounded callback channel. The standalone verifier has no producer or manager
linkage.

## State and authority

The application retains one actual OCaml pass manager. Registration, dependency
freshness, candidate checks, obligation discharge and scoped completion execute
there. Initialization may create an empty manager or retain the manager produced
by the native synthetic/component pipeline. Inspection is historical observation;
there is no operation that imports records as accepted state.

The explicit Python `CorePassManager` adapter preserves the familiar typed views
and registered extension callbacks. It does not invoke the original Python
manager's semantic methods. Every `get` and `result` first asks the live native
manager to recheck its authority; an existing Python view cannot bypass a stale
dependency or failed check. Losing the process invalidates the session. Mutations
are never retried or reconstructed from inspection output.

Host exceptions retain their original objects through the callback broker.
Expected native errors use a closed exception descriptor. Malformed frames,
resource exhaustion, unexpected internal errors and uncertain writes terminate
authority. Logical errors preserve mutations that already occurred, including a
record stored before a final freshness check fails.

## Identity is separate from canonical content

Canonical JSON establishes content identity but cannot express Python object
sharing or insertion order. The application therefore supplies separate view
bindings. A native binding names one process-local value and carries an ordered
tree; a host binding refers to an actual retained authored object. Neither grants
acceptance.

Record tokens identify physical native records, including rejected records.
Producer and validation contexts remain distinct, while validators in one run
share their validation context. Input, target, configuration, dependency snapshot,
requirements and source-link bindings preserve the sharing observed by the
original callbacks. Individual obligation objects and their containing tuples
have separate bindings because the original API sometimes retains a tuple and
sometimes constructs a fresh tuple with the same elements.

A read-only native observation hook records context and record origins at their
actual creation points. It does not supply checker decisions. Its work and
retention consume the same session budget. Built-in validators can consume host
source links only through explicit native opt-in: synthetic validators ignore
links, while component checking performs the original length and set comparison.

## Validation and remaining scope

The additive identity oracle runs five original-manager cases, retaining all 34
observations and ten complete records. Its mutations demonstrate that equivalent
copies and sorted mappings can fail compatibility despite identical canonical
content. The installed campaign must execute these cases through the actual
native process on Linux x86_64 and macOS arm64, each with Python 3.11 and 3.14.
It must retain full framed traffic, verify the source/run/executable identities,
reject the manager mode in Verify, and compare all four complete results.

This focused campaign supplements the original lifecycle, fixed-pipeline,
deferred-access and validator-comparison corpora. It cannot replace them. Full
fixed-registration interception, all callback-dependent continuations, public
workflow routing, distribution and default cutover remain separate required
gates. Arbitrary authoring subclasses and scalar operators are not established
by the typed canonical boundary; they require complete coverage or an intentional
versioned language restriction before cutover. Full compatibility also requires
typed fixed-producer return objects and the original ordering and shared snapshot
objects in no-candidate exceptions; decoding a closed exception descriptor alone
does not establish those properties.

All native compilation and execution remain hosted. Passing local Python
fixtures, static checks or typing does not establish native acceptance. Conditional
software translation remains distinct from empirical biological function and
human-use admission.

The source checkpoint registers 102 native suites in total and discovers 2,922
Python tests in 284 classes for the complete hosted unit plan. Discovery is not
execution. Strict typing covers 20 transport/view modules. Original workflow
capture tests and the complete CLI lineage checks remain in place, including
all literal source-addition assertions and unchanged frozen observations.

The next compatibility increment is the 34-case original validator-comparison
campaign. It requires ordered inspection of manager state and exact retained
provider identity before the complete original case bodies can run against the
installed manager. This does not close deferred access, fixed registration,
remaining native workflow families, distribution or default-engine gates.
