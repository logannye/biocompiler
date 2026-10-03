# Explicit public reference workflow routing

The existing `run_construct_pipeline` and `run_molecular_pipeline` functions can
now select the native reference manager through `reference_core(core)`. This is
an opt-in source checkpoint. Python remains the production default; installed
workflow parity and all four migration cutoff gates remain open.

## Public entry points and lifetime

Each original function has exactly five added dispatch lines after its docstring.
Its signature and function object remain intact, so previously imported aliases
use the current selection. The selection is held in a `ContextVar`, restores on
normal or exceptional exit, and requires an explicit `CoreClient`. Returned
managers retain their own channel lifetimes; callers close them after their last
use. The context does not confer native package or export authority.

The source witness records the complete original and current module hashes and
the exact inserted bytes at their original offsets. Reversing those insertions
recovers every original byte. The separate Core source witness reverses the one
application-declaration update, then the earlier six finite spans, recovering the
complete archived original Core manager. Neither proof replaces current native
execution or permits arbitrary changes to those files.

## Molecular call ordering and authority

The Molecular route first makes the original outer read-only manifest snapshot.
It calls the actual current `run_construct_pipeline` module global and reads the
returned object's `manager` once. The normal route keeps the distinct inner
Construct snapshot. A returned native-owned Construct manager can have different
original request or manifest roots; the current Molecular invocation retains its
own request, registry and snapshot for its emission and independent final check.
The upstream manager and its actual Construct result remain provenance rather
than a replacement for that current authority.

Native finalization preserves the two separate reads of `upstream.candidate`:

1. After parsing the actual Molecular record, request the candidate used by the
   independent final checker. Import it as untrusted typed data under the current
   authority. A non-candidate value retains the original serialization rejection.
2. After that check returns, request the candidate used in the returned Build.
   Retain this object as an opaque host reference. It may differ from the first
   candidate and need not itself be a serializable Construct record.

The second field supplies identity only. It cannot change the native check report
or import manager acceptance. A failed independent report can therefore coexist
with the actual manager's earlier completion result, as in the original source.
Exceptions preserve their source order and the manager's prior successful writes.

The application declaration adds `prepare-reference-molecular-public` and the
closed `reference-upstream-candidate` action. Preparation retains the complete
current authority and ordered trees. Finalization binds both reads to the same
live owner, active command and ordered phase. The declaration has 33 operations
and 14 actions and is identical in the protocol, service and Python adapter.

## Resource and capability checks

Preparation, authority documents, callback results and retained Builds consume
the original channel's cumulative work and retention limits. No new budget root
or refund is introduced. Finish still requires the actual observed run record
and matching result-command sequence. Callback entry and exit check owner budget
and closed state; close during a callback cannot reopen the channel.

Native tests cover separate authority roots, checked-versus-returned candidates,
opaque second roots, original callback exceptions, malformed output precedence,
foreign budgets, exhaustion and close during callbacks. The framed test exercises
the actual public preparation and final-source exchange as well as the earlier
native-only service path. These suites require hosted execution.

## Evidence and remaining work

Seventy facade, public-route, provider-view, registration and trace controls pass
on each of Python 3.11.15 and 3.14.6. Strict mypy checks all 27 selected modules.
The 48 complete source-guard controls pass on both runtimes.
The domain original-source counterpart passes eight controls per runtime and
executes its unchanged original child against the complete frozen source and
fixture closure. Source review verifies the native/Python interface and exact
source restorations; no native code was compiled or executed locally.

Exact file pins and local evidence are recorded in the
[source checkpoint](../protocol/migration-reference-public-routing-checkpoint.json).

Complete installed replay of the original 18 reference methods, 27 managers and
439 top-level operations remains required. A recorded-frame reconstruction may
check Python identities and traffic, but cannot substitute for actual native
execution. All original events, including internal semantic observations, must
remain accounted for before that campaign can be accepted.

Already completed/interrupted native owner reuse still needs source-ordered
continuation attempts. Ordinary Python-owned managers, arbitrary wrappers and
custom typed subclasses are not silently converted to native authority. These
compatibility boundaries and the remaining reference package/admission/behavior
workflows remain open. Package construction, fresh export checking, prebuilt
installation and production cutover are separate required work in the
[language migration roadmap](language-migration-roadmap.md).
