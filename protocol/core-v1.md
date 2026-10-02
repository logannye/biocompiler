# Local core protocol v1

Status: experimental migration interface. Existing public compiler and export
paths continue to use their current implementation until their conformance and
independent checking gates pass. A successful structural check is not successful
compilation, translation verification, biological evidence or human-use admission.

## Process and framing

Select an absolute path to a compatible executable. The initial supported
transport platforms are Linux and macOS. Run one process per complete operation:
one UTF-8 JSON request on stdin, terminated by EOF, and exactly one UTF-8 JSON
response on stdout. Whitespace around that document is allowed. Extra documents,
logging on stdout, incomplete output, duplicate keys and byte-order marks are
rejected. stderr is diagnostic-only and cannot supply a result or authority.

The Python adapter defaults to a 30-second deadline, accepts explicit positive
timeouts and cancellation, bounds stderr to 1 MiB, and terminates the process
group on a failed or cancelled exchange. Partial output is discarded. Exit 0
means `ok`, exit 2 means `error`, exit 3 means `unsupported`; other exits are
transport failures. No failure triggers a Python semantic fallback. No operation
downloads, compiles or installs an executable automatically.

An optional independently supplied SHA-256 executable pin binds the selected
local file. The identity echoed by a process is a compatibility check, not proof
of binary provenance or a cryptographic signature. Release provenance and atomic
installation are separate LM-30 gates. The adapter's JSON output is ordinary
data; it is not an abstract checked-artifact token.

## Envelopes

Every field below is required and no unknown fields are accepted:

```json
{
  "protocol": "biocompiler.core.v1",
  "request_id": "nonempty caller identity",
  "operation": "capabilities",
  "payload": {}
}
```

`operation` is a nonempty string. Unknown operations return `unsupported`. A
future operation requires a documented contract and advertised capability before
clients may use it. No external object, callback, Python import or executable
code is accepted as payload.

```json
{
  "protocol": "biocompiler.core.v1",
  "request_id": "nonempty caller identity",
  "operation": "capabilities",
  "status": "ok",
  "result": {},
  "diagnostics": [],
  "core": {
    "implementation": "ocaml",
    "version": "0.1.0",
    "protocol": "biocompiler.core.v1",
    "executable": "core"
  }
}
```

The standalone verifier uses executable identity `verify`. Version `0.1.0` is
the experimental core implementation version, separate from the Python package,
domain schema, semantic profile and checker-policy versions. The adapter matches
all identity fields, request ID and operation. Invalid envelopes may return null
request/operation identities; a client that sent a valid request treats a null or
mismatched identity as a protocol failure.

On success `result` is non-null and diagnostics are empty. On `error` or
`unsupported`, result is null and at least one diagnostic is required. Each
diagnostic has exactly `code` (nonempty string), `message` (nonempty string) and
`path` (string or null). These outcomes describe this operation only.

## Bounds and exact JSON values

| Bound | Value |
| --- | ---: |
| Request UTF-8 bytes | 16,777,216 |
| Response UTF-8 bytes | 33,554,432 |
| Nesting depth, root at zero | 128 |
| JSON values, including arrays and objects | 250,000 |
| Bytes per decoded request string or object key | 4,194,304 |
| Characters per number token, including sign/exponent | 4,300 |
| Intent nodes | 50,000 |
| Intent graph edges | 250,000 |

Object keys do not count as separate JSON values; they have the same UTF-8 string
bound. Response strings have the response byte bound, allowing canonicalization
to return an entire request as a string; the total encoded response must still
fit its byte budget, otherwise the core returns an explicit error. Envelope
values count toward the limits. Null, missing fields, false, zero
and empty containers are distinct. Booleans are not numbers. Integers are exact
arbitrary precision values within the token bound; no machine-integer or
JavaScript safe-integer truncation is allowed. Floating tokens represent finite
IEEE-754 binary64 values; overflow, NaN and infinity are rejected. Underflow
follows Python float parsing, including signed zero. Strings contain Unicode
scalar values, not lone surrogates; UTF-8 must be valid, without normalization.

## Canonicalization: python-json-v1

The canonical content is exactly the existing Python serialization contract:
`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False)`, encoded as UTF-8 without a terminal newline. Object keys sort
by Unicode code point. Floats preserve Python's shortest roundtrip representation
and spelling, including `1.0`, `-0.0`, exponent signs/zero padding and notation
thresholds. Integer tokens remain integers, including an integer parsed from
`-0` becoming `0`. No NFC normalization or generic RFC 8785 substitution occurs.
The fingerprint is lowercase SHA-256 over those exact bytes.

Source coordinates are retained for diagnostics but removed from the semantic
Intent fingerprint. Imported Intent records first undergo the existing schema
validation and normalization. Never strip arbitrary fields to hide differences
between implementations. Run metadata remains outside semantic identity.

This contract does not change numeric models in later passes: existing binary64
reference execution and exact decimal interval arithmetic are separate obligations.
The availability checker's `Fraction(str(value))` boundary still requires its own
port and conformance vectors before authority moves.

## Implemented operations

`capabilities` takes exactly `{}`. Its `biocompiler.core_capabilities.v1` result
returns supported operations, Intent schema versions, `canonicalization:
"python-json-v1"`, validation scopes, all limits above, versioned `profiles` and
an explicit limited claim scope. The verifier must advertise only its actual
operations; a standalone executable alone does not establish independent checking.
`CoreClient.negotiate` validates this envelope, exact transport bounds and the
requested operation. `ArchitectureClient` additionally requires its complete
architecture profile before each call. No cached negotiation grants authority.

`canonicalize` takes any valid bounded JSON value. Result fields are exactly
`canonical_json` (string) and `sha256` (string). This is a codec operation, not an
artifact acceptance result.

`validate-intent` takes a `biocompiler.intent.v0.1` document. It checks the existing
structural graph, schema fields, declared types, parameter/literal bindings,
identities, role references, roots and acyclicity. Result contains
`validation_scope: "intent-structure-types-bindings-v1"`, the existing Intent
`summary()` fields, and explicit `unimplemented_obligations`:
`behavior-lowering`, `behavior-execution`, `molecular-realization`,
`independent-translation-checking`, `human-therapeutic-admission`.

Intent's structural schema permits unknown node kinds. Passing this operation
does not mean their behavior is supported; semantic lowering must reject every
unimplemented operation. Full target-context admission, requirement coverage and
all subsequent compiler layers remain later migration gates.

`verify-lowering` takes exactly two fields: `expected_request`, a complete
`biocompiler.build_request.v0.1`, and `behavior`, a supplied
`biocompiler.behavior.v0.1` or `.v0.2`. The caller supplies original request
authority independently of the candidate. The checker does not create the
expected request from candidate metadata, invoke a producer, or accept an
imported verification report.

The checker compares complete ordered operations and input edges, resolved
parameters, role/type/source correspondence, the permitted state/rule/parameter
normalizations, execution policy, requirements, ancestor lineage and contact
identity. Every retained source operation is accounted for. Unknown source
operations and unsupported source policies return `unsupported` with a specific
`unsupported_lowering_*` diagnostic; changed correspondence returns `error` with
a specific `lowering_*` diagnostic. Malformed request or Behavior declarations
retain their schema diagnostics. All unsuccessful responses contain no result.

The result is a `biocompiler.lowering_verification.v0.1` report with exactly:

- `checker_version: "biocompiler.ocaml.lowering_check.v0.1"`,
  `validation_scope: "source-to-behavior-correspondence-v1"`, a fixed limited
  `claim_scope`, and `passed: true`.
- `request_fingerprint`, `request_artifact_fingerprint`, `source_fingerprint`,
  `behavior_fingerprint`, `behavior_artifact_fingerprint` and `behavior_profile`,
  recomputed from the separately decoded inputs. Artifact fingerprints include
  source locations and provenance; semantic fingerprints use each existing
  schema's location/provenance exclusions.
- Ordered `checks`, each containing `property`, `passed` and `detail`: five
  request/graph/binding checks, three checks per source node, then complete
  requirement/lineage and identity checks. Resource limits apply to this report
  as well as the source graph; an over-budget report cannot be accepted.
- `unimplemented_obligations`: source execution, molecular realization,
  source-to-candidate preservation, candidate acceptance, empirical component
  function and human admission. Retained implementation constraints, preferences
  and target/evidence assumptions add their corresponding unresolved obligations.
  Only the declared v0.2 sampling policy is interpreted at this stage.

This operation is independently runnable through both executable roles and the
explicit `CoreClient.verify_lowering` adapter. Production compiler routing remains
unchanged. A successful graph-preservation result does not execute the source or
candidate, accept a molecular architecture, or authorize an export.

## Experimental architecture operations

`verify-architecture` takes exactly `expected_request` (a complete
`biocompiler.payload_architecture_request.v0.1`) and `build` (a supplied
`biocompiler.payload_architecture_build.v0.2`). `replay-architecture` additionally
requires a complete `biocompiler.payload_architecture_verification.v0.1`
`assessment`. Replay reruns the independent checker with the original authority;
an altered historical report returns `architecture_assessment_mismatch`.

Both executable roles link only the public domain/checker service for these
operations. The separate producer and reference evaluator are absent from the
verifier's dependency graph. These calls do not perform candidate execution,
certify exhaustive search, establish empirical function or grant human admission.
Malformed authority and resource exhaustion return an error with no result.
An executed semantic check returns `ok` even when its assessment says `fail`,
`unknown` or `unsupported`; callers must inspect the scoped assessment outcome.
An incomplete `pass` retains its unresolved obligations and completion flags.

The result has exactly these fields:

- `schema_version: "biocompiler.core.architecture_assessment.v1"`;
  `implementation: "biocompiler.ocaml.architecture_check.v0.1"`;
  `resource_profile: "biocompiler.architecture_check.resources.v1"`;
  `validation_scope: "supplied-architecture-correspondence-v1"`.
- `supplied_request_fingerprint` and `supplied_build_fingerprint`, SHA-256 over
  canonical JSON of the exact supplied documents. These are separate from the
  normalized domain fingerprints inside the assessment.
- `assessment`, the complete freshly computed report, and its
  `assessment_fingerprint`. The historical schema and checker policy remain
  unchanged; the wrapper identifies the native implementation that executed it.

The advertised `profiles.architecture` record has exactly `operations`,
`request_schema`, `build_schema`, `assessment_schema`, `implementation`,
`resource_profile` and `validation_scope`. Its operations are
`verify-architecture` and `replay-architecture`; the other values match the
identities above. The Python `ArchitectureClient` freezes caller-owned input
containers before negotiation, verifies all result identities and returns an
immutable `ArchitectureResult`. Reading its assessment creates a separate copy.
The adapter checks protocol shape and integrity; it does not reimplement the
semantic checker or treat its Python class as an unforgeable acceptance token.

Current production SDK/CLI routing remains Python. The experimental typed
adapter does not complete release distribution, runtime isolation of the legacy
Python package initializer, export publication or default-engine cutover.

## Evidence

`tests/conformance/core-json-v1.json` retains independent literal examples and
separately identified Python-oracle vectors. `tools/check_core_conformance.py`
executes both native entry points, compares actual bytes/digests, exercises source
location invariance, validates authored examples and sends malformed raw byte
requests directly to the core. Skipped or absent executables are failures.
The same campaign checks independently supplied source/Behavior pairs through
both entry points, verifies full report identities and preservation census, and
requires intended rejection codes for structurally valid semantic mutations.

`tests/test_core_client.py` exercises subprocess failure, output bounds,
cancellation, request/role/version mismatches and malformed responses with Python
test children. These source tests do not substitute for hosted native validation.

`tools/check_architecture_protocol.py` runs 108 installed process checks across
both executable roles: complete verification and replay for all 13 installed
architectures, the three original case B authorities and eight meaningful
rejected candidates, plus forged-report and missing/extra-authority rejections.
It resolves pinned test-only storage deltas into full documents before transport.
It calls no Python semantic producer or checker. The broader 293-report native
campaign remains separately required. Strict mypy checking covers both migrated
Python adapter modules using the hash-pinned pure-Python tools and configuration
in `tools/typecheck-requirements.txt` and `tools/mypy-core.ini`.
