# Bounded workflow artifact channel

Implementation checkpoint: Python transport and immutable workflow SDK, native
inherited-descriptor handling, and both native service roles are implemented.
Fresh hosted validation of this revision and installed campaigns remain pending;
legacy public workflow/CLI cutover is still open. Transport binding alone is
neither a checker result nor fresh acceptance.

A small isolated POSIX C primitive duplicates inherited descriptors above every
supplied descriptor number and checks their actual access flags with `F_GETFL`.
This avoids the differing Linux/macOS `/dev/fd` reopen behavior and rejects
writable input descriptors. OCaml owns regular-file checks, alias detection,
bounds, JSON parsing, semantic execution and publication. The boundary gate pins
the exact primitive source and complete external declaration, prohibits new
native sources and permits only reviewed Unix members in the transport module.
All native compilation and tests run on hosted CI.

The existing `biocompiler.core.v1` request/response and its 16/32 MiB defaults stay
unchanged. Whole workflow reports require a separate channel because historical
CLI imports and publications support artifacts up to 64 MiB. The new client
requires an exact `artifact_transport` capability profile before invocation;
there is no fallback to legacy Python semantics.

The executable receives `--artifact-fds-v1 AUTHORITY RECORD OUTPUT` as separate
arguments. These are inherited descriptor numbers; `RECORD` is `-` when absent.
The parent creates private temporary files, opens input descriptors read-only,
unlinks their temporary names and passes only the required descriptors. Source
paths are never protocol authority. The output descriptor refers to a private
empty regular file. Native handling must reject nonregular inputs/outputs,
standard descriptors, aliases, malformed descriptor arguments and nonempty
output before reading or writing any artifact. It must read each input once
within its declared byte bound and validate the actual size and SHA-256.

The two workflow operations are `run-verification-workflow` and
`replay-verification-workflow`. The former supplies the complete workflow request;
the latter independently supplies that same request and the complete retained
record. Check, explore and reduce remain operations inside the workflow request.
Their exact native semantic profile is `biocompiler.core.verification_workflow.v1`.
The `verification_workflow` capability binds schemas, versions, all six
operation/mode pairs and the complete aggregate/leaf resource trees. The control
`operation_payload` contains exactly `profile` and `limits` (null defaults or
all five positive integer reductions).

The standard JSON control request has at most 65,536 bytes. Its payload contains
exactly `transport`, `authority`, `retained_record`, `output_limit` and
`operation_payload`. Each input descriptor is `{bytes, sha256}`; absent retained
records use null. `operation_payload` belongs to the separately checked workflow
profile. Input bytes and the complete control request are frozen before running
capability negotiation. Retained bytes are size/type bounded before transport;
the core validates independent request semantics before parsing retained JSON.
Python verifies retained JSON after successful native completion so its parser
cannot hide a source-authority rejection.

| Channel | Maximum bytes | Maximum JSON keys and values |
| --- | ---: | ---: |
| Independent workflow request | 16,777,216 | 250,000 |
| Historical workflow record | 67,108,864 | 1,000,000 |
| Complete output workflow record | 67,108,864 | 1,000,000 |
| Standard input/output control message | 65,536 each | Existing v1 bound |

Depth, decoded UTF-8 string and numeric-token limits remain 128, 4,194,304 bytes
and 4,300 characters. The Python artifact decoder bounds tokens, nesting and
inventory before allocating the complete decoded tree. It rejects duplicate
keys, malformed UTF-8, nonfinite numbers and invalid JSON kinds. Successful
output must be complete canonical compact UTF-8 JSON, retaining integer/float
distinctions and signed zero. A caller may reduce the output byte limit.

The ordinary v1 response retains its request identity, executable identity,
diagnostics and exit-status checks. A successful result contains exactly:

```json
{
  "schema_version": "biocompiler.core.artifact_response.v1",
  "transport": "biocompiler.core.artifact_transport.v1",
  "authority": {"bytes": 0, "sha256": "actual complete authority digest"},
  "retained_record": null,
  "artifact": {"bytes": 0, "sha256": "actual complete output digest"},
  "result": {}
}
```

The zero sizes and descriptive digests above illustrate field shapes only.
Actual artifacts must contain JSON. The client compares the complete independent
input descriptors, then re-reads and hashes the actual output bytes. A stored
digest, success label, valid JSON or matching byte receipt grants no semantic
authority. The workflow adapter must additionally validate its complete semantic
receipt and require fresh native checking against the independent request.

Timeout, cancellation, nonstandard exit, missing/partial response, oversized
control/stderr/output, stale input binding, changed output digest or noncanonical
artifact rejects the entire operation. Partial output never reaches a public
destination. The selected native program must enforce its own publication bound;
parent polling and final bounded reads additionally detect output excess. This
transport is not a sandbox for arbitrary executables. Executable release pins
are rechecked on each actual operation after negotiation.

Native integration must compose descriptor read/hash/preflight, request/record
decoding, fresh execution/replay and final encoding under one workflow budget.
Use the workflow budget's existing charged encoding operation rather than a
fresh unaccounted serializer. The standalone verifier must retain its producer
exclusion. Installed campaigns must exercise both executable roles, both hosted
platforms, Python 3.11/3.14 and all original CLI publication/exit behaviors.

Current transport evidence consists of real Python subprocess tests, including
a complete 36 MiB report roundtrip, read-only input descriptors, frozen mutable
control, exact output boundaries, changed authority, corrupt/partial records,
flooding, cancellation, timeouts and executable-pin failure. These tests validate
transport mechanics only; they are not native workflow conformance evidence.

The semantic result binds executable role, transport request identity, operation,
workflow operation/mode, profile and implementation/workflow versions, complete
canonical raw request identity, normalized typed request identity, retained record
identity and actual emitted record identity. Effective aggregate and leaf limits
must match the selected reductions. Replay freshly reconstructs and compares the
complete retained record. The Python SDK returns immutable exact record bytes
and defensive structural views without calling historical semantic constructors.

Raw parsed input nodes reserve scoped shared-budget inventory before each key or
value allocation. Final publication cannot release those reservations; descriptor
scope cleanup releases them exactly once, including failure paths, without
refunding work. The conservative reviewed live peak is 7.75 million items within
the 8 million profile. See the [transport audit](../docs/migration-realization-workflow-transport-audit.md).
