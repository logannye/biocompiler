# Explicit OCaml architecture workflows

The architecture SDK and CLI can select a compatible OCaml executable explicitly.
The default reference route remains Python until distribution and cutover gates
are complete. Explicit selection never retries through the reference engine after
a rejection, timeout, unavailable executable or incompatible protocol.

Use an absolute executable path from independently trusted release authority. The
optional SHA-256 pin identifies those exact executable bytes. Importing or calling
these APIs never downloads or compiles a core.

```python
from pathlib import Path
import biocompiler as bc
from biocompiler.core_client import CoreClient

core = CoreClient(Path('/absolute/path/biocompiler-core'), timeout_seconds=60)
verifier = CoreClient(Path('/absolute/path/biocompiler-verify'), role='verify',
                      timeout_seconds=60)

build = bc.compile(request, core=core)
assessment = bc.check_payload_architecture(build, expected_request=request,
                                           core=verifier)
replayed = bc.verify_payload_architecture(assessment, build,
                                          expected_request=request, core=verifier)
export = bc.export_payload_architecture(build, expected_request=request, core=core)
```

`request` is a complete `PayloadArchitectureRequest`. The named
`compile_payload_architecture` function accepts the same keyword. Public methods
return the existing build, verification and export classes with their existing
JSON interfaces. A supplied core for any other `bc.compile` request profile is
rejected explicitly. Compilation and export require the core executable;
verification and replay also support the separately linked verifier.

Record hydration uses historical bounded JSON codecs and requires the complete
normalized native identity to survive the round trip. It does not execute Python
source lowering, matching, construction or fresh verification. Historical string
Enums retain their declared JSON strings. The low-level clients retain exact
native canonical bytes and execution identities when callers need those directly.
CLI pretty JSON is a separate serialization of the same semantic content.

```sh
biocompiler architecture-build --request request.json --output build.json \
  --core-executable /absolute/path/biocompiler-core --core-timeout 60
biocompiler architecture-verify build.json --expected-request request.json \
  --verifier-executable /absolute/path/biocompiler-verify --core-timeout 60
biocompiler architecture-export build.json --expected-request request.json \
  --output export.json --core-executable /absolute/path/biocompiler-core \
  --core-timeout 60
```

`--core-sha256` pins the selected executable for either role. Digest and timeout
options require an executable; relative paths are rejected. The CLI keeps raw
supplied authority before native normalization and uses the operation's fresh
assessment for its unchanged summary. A build may be a valid incomplete artifact:
unsupported, no-solution and search-exhausted statuses remain explicit. Exit codes
remain 0 for passing construction, 1 for a checked incomplete/nonpassing build,
and 2 for malformed input, export refusal, I/O or selected-core failures.

The JSON export is one inseparable envelope containing FASTA and its complete
manifest. Publication atomically replaces that single file after fresh checking;
refused exports leave an existing destination intact. No API promises atomic
replacement of two unrelated plain files. Retain the independently supplied
request separately: an old report or caller-reconstructed export object cannot
authorize a new export. Partial translation may remain exportable when the
existing passing-construction predicate holds; unresolved obligations and all
biological claim limits remain visible.

`ArchitectureCoreError` is a public `SerializationError` subtype retaining the
operation, original `CoreError`, structured native diagnostics and exception cause.
Low-level clients retain their original error API. Neither a valid software
artifact nor fresh supplied-contract verification establishes empirical component
function or human therapeutic admission.

The installed routing campaign checks all 13 existing architecture examples and
three original case-B authorities under Python 3.11 and 3.14 on both supported
native platforms (175 checks per execution). A separate required gate rehashes
the complete 219-file artifact inventory from each execution and compares all
four inventories, including current workflow and executable authority. It compares
complete outputs, uses standalone verification, preserves mutation/publication
failures, and blocks Python semantic execution during selected-core calls.
Distribution, default routing, other historical profiles and independent candidate
execution retain their separate migration gates.
