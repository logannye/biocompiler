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
compatibility is not provided by these distinct views. Native pipeline freshness,
complete public SDK conformance, CLI routing, package acceptance and default
cutover remain open roadmap items.

The separate `select-synthetic-build-request` native operation imports complete
portable build authority and returns a nested selection receipt. Its exact
[protocol](../protocol/synthetic-producer-public-v1.md) includes four complete
Python-derived result fixtures and 42 malformed authority fixtures. It is a
preparatory service; this checkpoint does not wire it into the CLI.

The source-lineage witness proves that the three public functions add only an
optional keyword and early native branch while retaining their full original
default AST. Original corpora, freezer sources and expected observations remain
pinned. Derived call bindings project only the proven additional `core=None`
default. Local Python fixture, lineage and static checks are separate from native
validation. Both hosted platforms and every required CI gate must pass at the
new revision before any native validation or broader roadmap completion is claimed.
