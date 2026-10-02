# Explicit native verification workflows

The migration adds an explicit OCaml route for the existing verification
workflow API and four CLI commands. The default Python route remains available
until the complete migration and release gates pass. These routes preserve the
existing synthetic fixtures as historical software regressions; they do not
expand the human immune-cell RNA product scope.

## SDK selection

Construct a `CoreClient` with an absolute executable path and the digest of the
trusted installed binary, then pass it through the public API:

```python
from biocompiler import run_synthetic_verification, replay_synthetic_verification
from biocompiler.core_client import CoreClient

core = CoreClient(
    "/absolute/path/biocompiler-core",
    role="core",
    expected_sha256=installed_core_sha256,
    timeout_seconds=300,
)
record = run_synthetic_verification(authored_request, core=core)
replayed = replay_synthetic_verification(
    record, expected_request=authored_request, core=core,
)
```

The standalone verifier supports these same independently checked operations;
select its path with `role="verify"` and its own exact digest. Selecting a missing,
incompatible, rejected or unavailable core raises an error. It never silently
falls back to Python.

The selected route accepts complete request/record bytes, mappings, already
authored legacy objects, or the corresponding immutable native views. Legacy
input serialization is explicitly untrusted: any stored derived properties must
be checked afresh by OCaml. A replay always requires independent complete request
authority. Neither a stored PASS nor a previously successful receipt replaces
fresh replay.

The returned `NativeWorkflowRecord` is a distinct immutable view. It preserves
complete `to_dict()`/`to_json()` content, workflow identities, native result fields
and scoped diagnostics. It does not impersonate a legacy dataclass or promise
`dataclasses.replace`, legacy nominal type checks, arbitrary IR methods, or
nested semantic fingerprints that the native response does not supply. Returned
dictionaries are defensive copies. Native exploration counts, coverage totals,
completion and exit policy are projected from the checked response.

## CLI selection

The opt-in flags are accepted by `synthetic-check`, `synthetic-explore`,
`synthetic-reduce` and `synthetic-replay`:

```sh
biocompiler synthetic-check --request request.json --output report.json \
  --core-executable /absolute/path/biocompiler-core \
  --core-sha256 "$BIOCOMPILER_CORE_SHA256" --core-timeout 300

biocompiler synthetic-replay report.json --expected-request request.json \
  --verify-executable /absolute/path/biocompiler-verify \
  --core-sha256 "$BIOCOMPILER_VERIFY_SHA256" --core-timeout 300
```

The two executable flags are mutually exclusive. Digest and timeout options
require an explicit executable. During this compatibility stage these flags are
documented here and suppressed from the historical argparse usage text so old
default CLI diagnostics remain byte-compatible. No executable is downloaded or
built at import or command invocation.

Replay freezes the original request bytes, validates them through native source
preflight, and only then reads the historical report. Fresh native replay checks
those same frozen source bytes again. Run commands validate source before checking
command agreement and executing the operation. This preserves source-before-file
and source-before-command failure order without invoking Python semantic request
constructors on the selected route.

Native presentation supplies command exits and reduction frame counts. Complete
stdout summaries, report bytes, exit codes and atomic publication retain their
existing contracts. A faithfully replayed FAIL remains FAIL evidence while the
replay command succeeds. The original path-alias, regular-file, size, flush and
atomic replacement checks still protect publication.

## Validation and remaining cutover

The frozen Python CLI baseline contains 70 actual child invocations and all 16
original CLI observations. Optional routes require exact historical-source
lineage, complete default recapture, installed public SDK checks, all 70 CLI
children against both executable roles, and four-runtime comparisons of complete
artifacts and receipts. Real generated request IDs remain in full evidence; only
validated runtime metadata may be projected for cross-runtime comparison.

Local Python fixture tests and static checks do not establish native parity.
The new routing revision still requires both hosted native platforms, Python
3.11/3.14 and every required CI gate. Pipeline, archive, export, distribution and
default cutover obligations remain on the
[language migration roadmap](language-migration-roadmap.md).
