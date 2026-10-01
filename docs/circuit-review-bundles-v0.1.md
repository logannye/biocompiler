# Portable circuit review bundles v0.1

Version `0.1.0.dev26` adds a bounded R1/R12/R13 software increment: portable
review of already supplied construction, source metadata, nominal binding and
evidence-dependency records. It also brings the same existing checks into Studio.
It does not complete the R12 family archive or any source-dependent milestone.
The sole product target remains human DNA/RNA payloads for in-vivo immune-cell
deployment, with the complete original request and unresolved obligations retained.

## Authority and claims

`CircuitReviewAuthority` is a separately retained typed record containing the
complete construction request and optional source inventory, binding request and
evidence request. An evidence request also requires an independently retained
historical receipt fingerprint: a replacement snapshot cannot silently rewrite
the evidence history. Every supplied binding/evidence request must refer to the
same complete construction authority. Optional record groups are all-or-none.

`create_circuit_review_bundle` accepts a retained build, external authority and
the corresponding historical assessments/receipt. It replays the independent
checkers before packaging. `verify_circuit_review_bundle` requires external
authority again after import; the archive's own requests, fingerprints and PASS
labels cannot supply that trust root. Retain the authority before creating the
bundle and obtain it independently when receiving someone else's bundle.
The software checks content agreement; it cannot authenticate that a caller
actually obtained authority independently or that a review label is truthful.

An honest failed, stale, unknown or unsupported assessment may be retained for
review. Successful verification means the current independent checkers reproduce
those recorded results; inspect each result for its actual outcome. A forged
PASS, edited assessment, changed external authority or substituted receipt is
rejected. Source inventories are checked as metadata and have no asserted
source-case-to-build join. Storing an inventory beside a build does not establish
published correspondence.

| Track | Claim in this increment |
| --- | --- |
| Software | Container integrity, exact retained identities and fresh replay of individual scoped checks |
| Reviewed reference correspondence | Not established; source bytes and complete independent scientific authority are absent |
| Human biological applicability | Unassessed; human therapeutic admission remains unavailable |

Actual family semantics remain unimplemented and prediction remains unsupported.
The [R6a readiness record](r6a-reference-readiness.md) remains authoritative about
the missing first case. Artificial examples test software contracts only.

## Portable container

The `.bcb` archive uses the existing bounded canonical stored-ZIP policy with a
versioned review manifest and current checker/profile identities. The exact
inventory and every member's length and SHA-256 are checked. Requests, complete
builds, molecule forms/chemistry/maps, source identities and optional assessments
are retained as typed canonical JSON. JSON formatting is normalized; no typed
field or precise numeric value is intentionally discarded.

Optional `RunMetadata` is outside the canonical review identity. Archives without
run metadata reproduce byte-for-byte across supported Python versions. Paths,
duplicate members, compression, unsupported record schemas, oversized inputs
and undeclared members are rejected. Outdated package/checker pins permit
historical inspection but cannot pass fresh verification. Import never extracts files, executes code,
opens metadata paths or fetches URLs. The shared container codec is independent
of construction producers and profile-specific schema dispatch.

`inspect_circuit_review_bundle` checks the container and typed historical records
without claiming a fresh assessment. `publish_circuit_review_bundle` verifies
against current external authority, then atomically publishes a `.bcb` file.
The CLI also prevents overwriting its input files. This is a review handoff,
not a deployment export or physical synthesis authorization.

## Python and CLI

The public Python entry points are `CircuitReviewAuthority`,
`CircuitReviewManifest`, `CircuitReviewBundle`, `create_circuit_review_bundle`,
`inspect_circuit_review_bundle`, `verify_circuit_review_bundle` and
`publish_circuit_review_bundle`.

Run the explicitly artificial example with an already installed package:

```sh
python examples/circuit_review.py --output generated/circuit-review
biocompiler circuit-review-inspect generated/circuit-review/review.bcb
biocompiler circuit-review-verify generated/circuit-review/review.bcb --expected-authority generated/circuit-review/authority.json
biocompiler circuit-review-create generated/circuit-review/build.json --expected-authority generated/circuit-review/authority.json --source-assessment generated/circuit-review/source-assessment.json --binding-assessment generated/circuit-review/binding-assessment.json --evidence-receipt generated/circuit-review/evidence-receipt.json --evidence-assessment generated/circuit-review/evidence-assessment.json --output generated/circuit-review/copied.bcb
```

`inspect` and `verify` accept `--output` for a JSON review report. Exit zero means
the requested inspection or replay succeeded, including faithful replay of an
honest failed assessment. Exit two means invalid input, authority disagreement
or publication failure. The report's individual check results retain their own
statuses; command success cannot be interpreted as biological acceptance.

## Studio review

Open `/construction` in Studio and expand **Review sources, bindings and evidence**.
Supply any of the four optional raw JSON records: current source inventory,
independent binding request, current independent evidence request and historical
evidence receipt. Each input is limited to 1 MiB and the full encoded operation
to 2 MiB; Python/CLI offer the underlying artifact limits for larger reviews.

The view shows all source coverage gaps, nominal requirement/role mappings,
explicit assumptions, evidence uses/observation mappings and dependency freshness.
Sources, bindings and evidence keep separate diagnostics and claim boundaries.
A binding or evidence request contains complete construction authority and can
trigger fresh construction replay; every supplied authority must match the build.
Source metadata or a receipt alone cannot trigger that replay. Missing evidence
authority and missing receipts are shown separately. No unsupported prediction
plot is generated.

All record edits and file imports invalidate pending results and downloads.
Save freshly checks the supplied inputs and preserves only the original build
JSON, including its original valid UTF-8 spelling and line endings until edited.
Optional review inputs are not included in that build download; use the portable
bundle API/CLI to package a complete review. Failed nominal/source diagnostics
remain visible and do not prevent preserving an honest historical build.

## Validation and remaining work

Required hosted gates retain the full regression suite, installed examples and
CLI outside the checkout, browser acceptance, frozen audit integrity, dependency
independence and cross-Python byte comparison. New checks cover rehashed forged
reports, external-authority substitution, stale receipt replacement, missing
cohorts, strict container imports, relocation and stale UI operations. Package
builds and installed validation run on hosted CI; no local rebuild is required.

The [continuation boundary](r5-r13-continuation-boundary.md) remains open for the
first admissible reviewed case, real family semantics, integrated family exports,
models and complete release acceptance. No restricted source reconstruction is
retried by this increment.
