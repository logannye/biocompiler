# Synthetic producer protocol v1

The adjacent immutable [declaration](synthetic-producer-v1.json) defines three
Core-only operations: `generate-synthetic`, `select-synthetic`, and
`adapt-synthetic-components`. They call the existing OCaml producer implementations
without adding a proposal override or checker callback. The standalone verifier
has neither these operations nor a producer-library dependency.

Each payload has the exact fields listed in its profile. Generation receives the
complete realization request and nullable generator configuration. Selection also
receives the entire finite history and exact nullable horizon. Adaptation receives
the actual candidate, complete request and history, and horizon. A null config
selects the historical default configuration; a supplied config remains complete.
Profiles and unknown/missing/duplicate fields fail closed. Numeric kinds and
Unicode source locations survive canonical transport.

Every successful protocol response uses `biocompiler.core.synthetic_production.v1`
and has exactly these fields:

- `schema_version`, `profile`, `implementation`, `service_implementation`,
  `resource_profile`, `resources`, `validation_scope`, and `claim_scope`;
- `supplied_authority_fingerprint`, covering the entire original payload with
  UTF-8 canonical JSON, including explicit versus null controls;
- `authority_identities`, including the semantic realization request identity and
  separate normalized UTF-8 request artifact identity, effective config identity
  where applicable, normalized ASCII history identity where applicable, and the
  actual candidate identity for adaptation;
- `outcome`, `record`, `record_fingerprint`, and `generation_error`.

A `produced` outcome contains the complete original candidate, complete selection
record (including every alternative, rejection, check and ranking result), or
complete registry/composition/acceptance triple. `record_fingerprint` hashes that
whole record using UTF-8 canonical JSON. A produced selection can still have no
selected candidate; clients must preserve the complete selection outcome.

An ordinary `Generator.Unsupported` exception becomes an `unsupported` outcome
with null record and record fingerprint. Its `generation_error` retains the
original message, nullable node ID, nullable complete `{file,line,function}`
source, and formatted historical exception text. The protocol status is `ok`
because this is a complete structured producer result, not protocol unavailability
or acceptance. Structural/resource errors remain protocol errors. Unsupported
operations, including every producer operation on the verifier, remain protocol
status `unsupported` with `unsupported_operation` and no result.

`limits` is null or an exact object of five positive integer reductions:
`max_work`, `max_monitor_items`, `max_request_bytes`, `max_report_bytes`, and
`max_report_nodes`. Limits never enlarge the fixed native ceilings. One work
ancestor includes complete request framing, bounded structural import, authority
hashing, the actual producer and its fresh checks, record hashing, and complete
result/final-envelope publication. Framing is charged before control decoding;
its cost is deducted from the selected work allowance. Protocol-held history
items are deducted from the producer's available retained-item allowance before
production. Traversals terminate for cyclic native JSON and cyclic list spines.
Request reservations count key/value nodes and UTF-8 bytes. Reports cumulatively
reserve the record, wrapper and actual final response using conservative ASCII
bytes before UTF-8 publication, including the actual request ID and role.

Generation establishes a software proposal and hard-policy checking. Selection
establishes only the documented two-strategy finite-history result. Adaptation
requires fresh synthetic acceptance and constructs software components; it does
not establish linking or biological applicability. No operation grants empirical
function or human therapeutic admission.

This boundary is preparation for public producer routing. Existing Python
synthesis functions, CLI commands, pipelines, package construction, and export
acceptance remain separate migration work. A raw service result does not establish
pipeline freshness or exported-archive acceptance.

The explicit raw-document SDK is
`biocompiler.core_synthetic_producer.SyntheticProducerClient(CoreClient(...))`.
Its keyword-only `generate(request=..., config=None, limits=None)`,
`select(request=..., history=..., until=None, config=None, limits=None)`, and
`adapt(request=..., candidate=..., history=..., until=None, limits=None)` methods
accept complete JSON values. Corresponding `generate_document`,
`select_document`, and `adapt_document` methods accept immutable bytes containing
the complete operation payload, including profile and controls. Each call
negotiates the exact producer capability before dispatch. The SDK rejects a
verifier-role client before starting a process.

Results are immutable `NativeSyntheticProduction` views. They retain the
original input bytes, canonical authority bytes, complete receipt bytes, and
complete canonical record bytes and fingerprint when produced. Decoded property
access returns copies. Ordinary Unsupported results retain structured error
details; protocol, availability and resource failures retain their transport
exceptions. No Python producer, semantic constructor, ranking implementation or
fallback runs on this path. These views deliberately do not hydrate a Python
selection object whose properties would recompute a selection decision.

The native protocol test contains 23 independently retained complete Python
literals, including Unicode and complete ordinary Unsupported errors. The test
compares all capability/resource fields to this declaration's frozen literal,
checks role separation and malformed payloads, and exercises all five reduced
resource boundaries plus exact and one-under shared ancestor work. Hosted native
execution is required; static construction of these tests is not native validation.
