# Explicit native synthetic producer checkpoint

The three public synthesis functions accept an explicit `core=CoreClient(...)`:
`generate_synthetic`, `select_synthetic`, and `adapt_synthetic_components`.
Omitting it preserves their original Python implementation. Selecting it invokes
the strict raw producer service with no Python semantic fallback. These synthetic
fixtures establish software regression behavior only; they do not establish
human-use admission or empirical biological function.

The explicit route returns immutable `NativeSyntheticCandidate`,
`NativeSyntheticSelectionResult`, or `NativeSyntheticComposition` views. They
preserve the complete native JSON, receipt and source identities. Selection
strategy, outcome and counts come from the native result. Python does not rerank
alternatives or reconstruct semantic classes to accept the result. Typed authoring
inputs, JSON bytes, mappings and historical native views are serialized as
untrusted input for a fresh operation. Ordinary Unsupported errors preserve their
message, node and source location.

These views have a distinct versioned contract. Nested fields, node lookup,
component port lookup and inspection of the exact attached registry lock are
available. `to_dict()` returns an editable copy; editing and resubmitting it
requires a fresh native operation. `from_dict()` and `from_json()` create
historical inspection views without a native receipt. They do not establish
fresh acceptance.

The following compatibility work remains unfinished: mechanism topological
ordering, general registry selection or lock verification, derived exercised
requirements, dependency comparison and check freshness. Those methods fail
explicitly with Unsupported errors. Legacy `isinstance` and `dataclasses.replace`
compatibility is not provided by these distinct views. Explicit SDK and CLI routes
are implemented; complete installed native conformance remains pending. Native
pipeline freshness, package acceptance and default cutover remain open roadmap items.

The separate `select-synthetic-build-request` native operation imports complete
portable build authority and returns a nested selection receipt. Its exact
[protocol](../protocol/synthetic-producer-public-v1.md) includes four complete
Python-derived result fixtures and 42 malformed authority fixtures. The explicit
CLI route below uses this operation; its hosted integration gate remains open.

The source-lineage witness proves that the three public functions add only an
optional keyword and early native branch while retaining their full original
default AST. Original corpora, freezer sources and expected observations remain
pinned. Derived call bindings project only the proven additional `core=None`
default. Local Python fixture, lineage and static checks are separate from native
validation. Both hosted platforms and every required CI gate must pass at the
new revision before any native validation or broader roadmap completion is claimed.

## Implemented full build authority and explicit CLI route

`SyntheticProducerPublicClient.select_document()` accepts raw complete build
request bytes. It verifies the returned original and normalized authority
identities, the exact nested producer payload/receipt, reserved history capacity,
and native frame/exit presentation. `synthetic-select` now accepts the explicit
hidden migration flags `--core-executable`, `--core-sha256` and `--core-timeout`.
The selected route branches before Python request construction and delegates full
request validation and selection to the native operation. Existing file reads,
complete report formatting, atomic publication, stdout/stderr and exit behavior
are preserved. Options without an executable fail explicitly.

Before changing the CLI, a new baseline retained 72 actual Python children and
113 complete content blobs, including the original complete unit method, both
entry points, all four original result literals, all 42 malformed authorities,
file aliases, publication faults and argparse boundaries. Complete repeats on
Python 3.14 and 3.11 differ only in the explicitly pinned unknown-flag usage
wrapping. Each runtime's exact stderr is retained; no general whitespace
normalization is permitted.

Installed campaigns must run every original public producer occurrence through
its explicit SDK route, as well as the complete CLI baseline, and retain raw
native responses and all artifact bytes across both platforms and Python
versions. Their passing Python protocol fixtures do not establish hosted native
validation. The migration remains incomplete until those gates and the remaining
pipeline/package/helper obligations pass at the integrated revision.

The current producer transport uses the direct bounded JSON profile (16 MiB input,
32 MiB complete response). The historical CLI publication ceiling is 64 MiB.
Serialized-length fault fixtures test publication handling; they do not prove
that every valid large semantic result fits this transport. Full large-result
compatibility needs an artifact-channel profile before default cutover.
