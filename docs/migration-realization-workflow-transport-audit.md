# R5 inherited-descriptor transport audit

Audit checkpoint, 2026-10-02. This document reviews the opt-in artifact channel
against `protocol/artifact-transport-v1.md`, `src/biocompiler/core_artifacts.py`
and the core dependency boundary policy. Transport integrity does not establish
workflow acceptance. Native descriptor tests described here require hosted Linux
and macOS execution; no local native compilation or execution is authorized.

## Descriptor boundary findings

Reopening `/dev/fd/N` is insufficient to enforce the advertised original-input
access mode. Linux can reopen the underlying file with a different access mode;
macOS descriptor reopening can preserve access mode and the shared file offset.
An existing-Python-stdlib probe on this Darwin host opened a temporary O_RDWR
file through `/dev/fd/N` with O_RDONLY: `F_GETFL & O_ACCMODE` remained O_RDWR,
and the offset remained shared. Reopening that descriptor O_WRONLY failed with
EPERM. A channel's declared direction therefore does not prove that the inherited
input descriptor is read-only. Do not probe with nonempty writes.

The implementation therefore uses the explicitly reviewed
`core/lib/service/artifact_fd_stubs.c` bridge. It validates numeric ranges before
C casts, duplicates the original descriptor with `F_DUPFD_CLOEXEC` above every
supplied number, checks `F_GETFL & O_ACCMODE` on that duplicate, and closes it on
invalid access. Inputs require O_RDONLY; output requires O_WRONLY or O_RDWR and
forbids O_APPEND. Duplication preserves the original access mode. The bridge has
one three-argument primitive and performs no pathname, process, network, JSON or
semantic operation. It requires fresh hosted compilation and execution.

Additional requirements:

- Accept only canonical unsigned decimal descriptor arguments greater than two,
  plus exactly `-` for an absent retained record. Reject empty strings, signs,
  whitespace, leading-zero aliases, overflow and arbitrary paths.
- Reject repeated descriptor numbers before opening anything. Reject identical
  `(st_dev, st_ino)` across every input and output, including separately opened
  descriptors of the same file and hard-link aliases.
- Validate all original descriptors before creating duplicates, or ensure new
  duplicates cannot occupy any supplied number. Otherwise an originally closed
  output number can accidentally become valid when an earlier open reuses it.
- Require regular files; reject pipes, sockets, devices and directories before
  any read or write. Require read-only inputs and a writable, initially empty
  output. Check output size before writes, including immediately before final
  publication if execution occurred between validation and publication.
- Do not call `open_out_bin` on a supplied descriptor path: its truncation flag
  can destroy a nonempty output before rejection. No arbitrary filesystem path,
  creation, truncation or append-mode behavior belongs in production transport.
- Read from the beginning deliberately and require exact expected byte length,
  bounded complete input and actual SHA-256. Read each input only once; parse the
  retained bytes. Do not confuse an inherited offset with artifact identity.
- A size check alone is not stable authority. Verify actual bytes/digest and
  detect shortening, extension, incomplete reads and trailing bytes. Duplicating
  descriptors does not make mutable file contents immutable; the existing
  private, unlinked parent files and complete content pins remain relevant.
- Close every owned duplicate on normal completion and any error. Do not close
  caller-owned inherited originals. A failure must not publish a success
  receipt or expose partial output as a complete workflow result.

## Accounting and canonical boundaries

Use one caller-owned workflow budget for descriptor validation/read/hash, JSON
parsing, strict key-and-value preflight, staged request/record decoding, fresh
run/replay and final report encoding/publication. Charge before proportional
allocation or work; neither parsing nor output hashing may silently create a
fresh budget. Preserve per-check 50M caps and the reviewed aggregate workflow
profile. Descriptor byte limits are per artifact; raw aggregate input consists
of at most 16 MiB independent authority, 64 MiB retained record and 64 KiB control.

The authority artifact has 250,000 total key/value nodes and the record/output
have 1,000,000. `Json.parse_bounded` counts value nodes; its successful return
alone does not satisfy the stricter artifact key/value census. The new
`Json.parse_artifact` counts keys as well and invokes its accounting hook before
each node allocation. Keep depth 128, string 4 MiB and numeric
token 4,300-character ceilings. Strict malformed UTF-8, duplicate keys,
nonfinite numbers, integer/float distinction and signed zero remain mandatory.

Input digests identify complete supplied bytes, which may use noncanonical JSON
spelling. Successful output must equal the charged canonical compact UTF-8
encoding, and its receipt binds exact final bytes and SHA-256. Preserve legacy
ASCII hashes inside semantic records; transport hashes do not replace those
identities. The workflow service must additionally compare complete fresh
semantic results and independently supplied authority.

## Narrow boundary policy additions

Keep Unix/process/native escape rejection as the default. Review each allowed
member at the exact production path `core/lib/service/artifact_io.ml` and at the
exact test path `core/test/test_artifact_io.ml`; allowing every Unix member in a
whole library would unnecessarily authorize sockets and process execution.
Add the standard `unix` library only on the required service/test Dune edges.
Any native bridge requires a separately enumerated source and symbol with a
closed source inventory; it must not grant general `external`, `Obj`, `Marshal`,
`Dynlink`, shell or subprocess access to any other core source.

The test-only file needs temporary-file creation/removal, regular-file open/close,
read/write/seek/stat, pipe creation, duplication and mode/identity inspection.
Tests may discover their actual numeric descriptors through a bounded
`/dev/fd/N` stat scan instead of unsafe casts. Mutation tests for the boundary
scanner should reject an unlisted Unix member, a production use at another path,
an unlisted native bridge, and a producer dependency through transport.

## Native test inventory

The native suite must exercise the public artifact I/O API, without semantic
producer imports. Cover complete run and replay channels, absent record handling,
Unicode and exact integer/float/signed-zero bytes, a record larger than the old
32 MiB envelope, and reduced exact/one-under byte/node/work bounds. A shared
ancestor must cover reading, decoding and writing; exhaustion before publication
must leave output empty and an unrelated later operation must remain usable.

Reject standard descriptors, malformed arguments, repeated numeric arguments,
closed descriptors, independently opened inode aliases, hard-link aliases,
input/output aliases, pipes and directories, writable inputs, read-only output,
append output, initially nonempty output, changed output after channel setup,
wrong lengths, wrong digests, oversized inputs, truncated inputs, trailing bytes,
malformed/duplicate/nonfinite JSON, excess object-key census, excessive nesting,
invalid UTF-8 and output publication beyond the reduced limit. Verify complete
caller-owned input contents remain unchanged on all validation failures.

The implemented suite is `core/test/test_artifact_io.ml`. It uses public
`with_fds`, `charge_control`, `read_authority`, `read_record`, `write_output`,
descriptor codecs and the exact advertised profile. The profile literal is
independently frozen from Python, SHA-256
`a7f94cb321755d31bbfd15e85d2d32cd52ee29c51786a6936ff69ab640790771`.
The complete-byte SHA-256 witness for `{}` is independently pinned as well.
Tests exercise a 36 MiB historical artifact, exact 250,000/one-over 250,001
key-and-value inventories, exact/one-under work and shared-parent budgets,
aggregate input bytes including control, publication bytes/nodes, source
mutation, caller exception propagation, retained lifetimes and all descriptor
failure families listed above. Absent record plus null descriptor is a no-op;
actual reads and publication are single-use, including failed attempts.

The suite needs `bioc_service`, `bioc_wire`, `bioc_checker`,
`bioc_realization_checker` and standard `unix`. It uses no unsafe casts, semantic
producer imports or subprocess execution. Existing Python subprocess transport
tests (27 passing at the prior checkpoint) prove adapter mechanics, not native
descriptor handling or workflow acceptance. The new native suite and bridge
remain unvalidated until the exact corrected revision passes hosted execution.

## Incremental input lifetimes and the unchanged 8M ceiling

Plain `B.retain` was unsuitable for parsed input: `B.publish` replaces all
nonscoped retained inventory, so final publication could prematurely release
still-live raw authority and cause a second release during descriptor cleanup.
The workflow budget now exposes an abstract `scope` with `create_scope`,
`retain_in_scope` and `release_scope`. Scope creation charges one work unit.
Each successful incremental reservation first performs the existing capacity
check and work charge, then updates its exact owner and scoped inventory.
Failure changes no retention counters. Final release removes exactly that
scope's amount once, refunds no work, and rejects reuse or double release.
Artifact I/O records each parsed input's scope and releases it when `with_fds`
exits, including parse or callback exceptions. Scoped inventory survives
publication. Native tests exercise publication while a raw input remains live,
failed incremental reservation, parent exhaustion and exact cleanup afterward.

The 8,000,000 live-bookkeeping ceiling remains sufficient without changing
semantic behavior or the work profile. The following simultaneous bounds count
node/list inventory, not process RSS; raw byte buffers retain their independent
16/64 MiB transport ceilings.

| Phase | Concurrent conservative inventory | Total |
| --- | --- | ---: |
| Nested historical import | Raw authority 250,000 + raw record 1,000,000 + two nested 2M workspaces | 5,250,000 |
| Exploration trial | Raw inputs 1,250,000 + retained results 1,000,000 + result-list cells 19,607 + generated prefix 36,000 + prospective result 500,000 + settings workspace 2,000,000 | 4,805,607 |
| Reduction trial | Raw inputs 1,250,000 + initial result 500,000 + current result 500,000 + current spine 1,000,000 + trial spine 1,000,000 + reverse prefix 1,000,000 + prospective result 500,000 + settings workspace 2,000,000 | 7,750,000 |
| Final reduction record construction | Raw inputs 1,250,000 + initial/current results 1,000,000 + current spine 1,000,000 + workspace 2,000,000 | 5,250,000 |
| Report transfer and encoding | Raw inputs 1,250,000 + old or final report 1,000,000 + workspace 2,000,000; transfer itself overlaps only old/new report 2,000,000 | 4,250,000 |

These inventories come from the actual runtime scopes. A CheckResult has at
least 51 key/value nodes, bounding retained exploration list cells by 19,607.
The generated prefix bound is exactly
`3*16*(8+10*8+8*(2+10*8))+2*16+256 = 36,000`.
Every history contains at most 1M nodes, so using 1M cells for each reduction
spine is conservative (each actual frame consumes at least seven nodes).
The 500,000 result ceiling preserves legacy value-only node limits even though
fresh native checker reports use the smaller 250,000 key/value limit. The
prospective callback reservation encloses the 2M workflow settings workspace;
later validation workspaces do not overlap that reservation. Trial replacement
reserves a new result after those workspaces end and then releases the old
current result/spine. Reverse-prefix and trial scopes have exited before final
record construction. No work is refunded when inventories are released.

A native counter-level test exercises the conservative 7,750,000 overlap under
the unchanged default, then proves all 8,000,000 slots can be reserved again
after release. Actual hosted algorithm/corpus runs remain necessary evidence.

## Rejection precedence at the service boundary

The original CLI fully imports the independent workflow request before loading
and importing a historical record (`cli.py` lines 1693–1698 at audit time).
Eagerly parsing both descriptor artifacts before fresh request decoding would
change the error reported for an invalid source request paired with malformed
historical bytes. The service owner implemented an internal deferred
retained-record loader to preserve this order while keeping the same budget and
descriptor scopes; the descriptor call site now uses this deferred loader. The loader is
an implementation callback, never a wire capability or serialized callable.
New direct service tests cover suppression on invalid source authority and
complete fresh loaded replay with identical work to the direct raw service
route. These changes still require fresh hosted validation.

## Final review closure

Both additional findings from the final static pass are resolved in shared
source. `Service.artifact_request` now requires exact agreement between the
retained-record argument (`-` versus a descriptor number) and the control
message's null/present record descriptor before `with_fds`. A fresh operation
cannot silently ignore an extra inherited record file.

The native escape gate now compares the complete OCaml external declaration
block with its one approved declaration, rather than checking only its first
line. This rejects a second native primitive symbol placed on the following
line. `test_descriptor_primitive_cannot_expand_native_or_process_access` includes
that exact mutation alongside C-source, Unix-member and additional-native-source
mutations. Root reports the focused boundary tests passing. This closure was
verified by reading source only; no additional tests, native execution or Git
operations were performed. The corrected revision still needs hosted native
compilation and execution.
