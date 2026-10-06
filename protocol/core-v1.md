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
requested operation. `ArchitectureClient` and `RealizationClient` additionally
require their complete operation profiles before each call. No cached negotiation
grants authority.

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
operations. The verifier excludes producers. Its realization operations link separate source
and candidate runtimes; these architecture calls do not perform candidate execution,
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

## Architecture production and paired export

The core executable additionally advertises `compile-architecture` and
`export-architecture` in a distinct `architecture_producer` profile. The standalone
verifier advertises neither operation and links no producer service. The existing
`architecture` verification profile remains unchanged. Production profile fields
are exactly `operations`, `request_schema`, `build_schema`, `export_schema`,
`assessment_schema`, `implementation`, `resource_profile`, `checker_implementation`,
`checker_resource_profile` and `validation_scope`. These pin existing domain schemas,
`biocompiler.ocaml.architecture_producer.v0.1`,
`biocompiler.architecture_producer.resources.v1`, the existing architecture checker
identities, and `supplied-architecture-production-v1`.

`compile-architecture` accepts exactly `{"request": <complete architecture request>}`.
Its result fields are exactly `schema_version`, `implementation`, `resource_profile`,
`validation_scope`, `supplied_request_fingerprint`, `request_fingerprint`,
`build_fingerprint`, `build_json` and `verification`. The result schema is
`biocompiler.core.architecture_build.v1`. `build_json` contains the entire normalized
historical build encoded as canonical UTF-8 JSON without a terminal newline;
its SHA-256 is `build_fingerprint`. The source wire fingerprint remains separate
from the normalized request fingerprint. `verification` is the same complete
assessment envelope returned by `verify-architecture`, produced by the final fresh
independent check within the compilation budget. It binds the supplied request
and the returned complete build.

Successful transport can carry any supported build status: `compiled`, `partial`,
`unsupported`, `no_solution` or `search_exhausted`. A consistent incomplete build
can pass its checker while retaining unresolved obligations. Neither a successful
protocol exchange nor a valid receipt upgrades translation completeness, proves
search optimality, establishes empirical behavior or grants human-use admission.

`export-architecture` accepts exactly `{"expected_request": <original request>,
"build": <complete candidate>}`. It accepts no old assessment as authority. Fresh
independent checking must establish the existing export predicate: a passing
assessment, complete construction and an actual construction result. The predicate
preserves existing partial translation scope instead of silently strengthening or
weakening the public export contract.

Its result fields are exactly `schema_version`, `implementation`, `resource_profile`,
`validation_scope`, `supplied_request_fingerprint`, `supplied_build_fingerprint`,
`request_fingerprint`, `build_fingerprint`, `export_fingerprint`, `fasta`,
`fasta_sha256`, `manifest_json`, `manifest_sha256` and `verification`. The schema is
`biocompiler.core.architecture_export.v1`. FASTA preserves exact member order, RNA
bases, headers and line endings. `manifest_json` is the complete native canonical
manifest with no terminal newline. Each byte digest binds its returned content;
`export_fingerprint` binds the existing domain export record containing both the
FASTA and decoded manifest. The manifest retains the complete build, fresh
assessment, delivered member inventory and instruction to retain independent
request authority. The separate verification envelope binds the exact supplied
request and candidate, even if decoding normalizes their inventories.

Outputs are immutable process results; oversized or failed operations return no
accepted partial output. Python transport freezes inputs before negotiation,
validates the negotiated profile and all exact output identities, and retains
canonical output bytes. Decoded properties return defensive copies. This protocol
does not itself publish filesystem paths or make a reconstructed result object
fresh authority. Atomic publication, public SDK/CLI routing and distribution
remain separately tracked migration obligations. No failure retries through Python
semantic execution.


## Experimental realization operations

This extension is an explicit experimental selection. Native and installed
conformance gates must pass before default engine cutover. Both executable roles
expose all nine checking/dependency operations below. The standalone verifier
links separate source-reference and actual-candidate execution libraries and the
independent realization checkers; it still excludes compiler, synthetic producer,
architecture producer service and source adapter libraries. Private provenance
and component-authority witnesses are not public generation endpoints.

Every payload is an object with exactly the named fields. `profile` and `limits`
are always present, including replay. `profile` is the exact family identity
below. `limits` is null for defaults or an object containing all five positive
integer reductions: `max_work` (at most 50,000,000), `max_monitor_items` (100,000),
`max_request_bytes` (16,777,216), `max_report_bytes` (33,554,432), and
`max_report_nodes` (250,000). Booleans, floats, zero, unknown/missing keys and
increases are rejected. Replay adds only `assessment`, the complete historical
inner report, to the same original authority.

| Family / exact profile | Operations | Authority fields beyond profile and limits |
| --- | --- | --- |
| `biocompiler.core.realization.v1` | `realization-dependencies`, `verify-realization`, `replay-realization` | `behavior`, `contract`, `domain`, `target`, `mechanism`, `observation_map`, `history`, `until` |
| `biocompiler.core.synthetic_candidate.v1` | `verify-synthetic-candidate`, `replay-synthetic-candidate` | `expected_request`, `candidate`, `history`, `until` |
| `biocompiler.core.component_behavior.v1` | `verify-component-behavior`, `replay-component-behavior` | `expected_request`, `assembly`, `history`, `until` |
| `biocompiler.core.component_assembly.v1` | `verify-component-assembly`, `replay-component-assembly` | `expected_request`, `candidate`, `assembly`, `history`, `until` |

`until` is explicit null or the exact integer/finite float supplied; no effective
horizon substitution or integer/float coercion occurs. History contains complete
InputFrame records (`time`, `signals`, `contacts`) using the existing sample
codec (`value`, `present`, `high`, `low`, including supported numeric shorthand).
Neither InputFrame nor DependencySnapshot has a `schema_version`. The original
complete domain schemas are enumerated in the exact
[capability profile records](../docs/migration-realization-protocol-profiles.json);
no reduced replacement for request, candidate, assembly or history is accepted.

`realization-dependencies` constructs complete dependency identity only; it does
not execute either model or grant acceptance. Direct model verification executes
the supplied Behavior and actual Mechanism over the finite history, without a
source-lowering or synthetic-provenance claim. Synthetic checking additionally
validates the full original source request and independent candidate provenance.
Component-behavior checking reconstructs the actual locked assembly, checks
linking and compares source/candidate behavior without asserting synthetic
correspondence. Complete assembly checking additionally requires the supplied
candidate's provenance and exact independently reconstructed component/source
correspondence. None establishes search completeness, empirical behavior or human
therapeutic admission.

All report outcomes (PASS, FAIL, UNKNOWN, UNSUPPORTED) remain complete successful
transport results when the checker returns them. Source-authority, structural,
horizon, resource, assembly-precondition and replay-mismatch errors return no
result. Replay runs the complete fresh check, then requires exact full historical
report reproduction; a reproduced failure remains a failure. Imported PASS,
matching dependency hashes, normalized omissions or self-supplied artifact pins
cannot replace that calculation.

`supplied_authority_fingerprint` binds core UTF-8 canonical bytes of every raw
payload field except replay `assessment`, including profile, full source
coordinates, actual history/horizon and supplied limits. Null limits and explicit
default limits therefore have distinct raw authority identities. Normalized
semantic/request/history identities remain separate in `authority_identities`.
The outer wrapper binds all assembly authority even where its historical inner
CompositionResult lacks history or candidate identity. Request ID, operation,
role and implementation version remain bound by the process envelope.

Realization CheckResult and DependencySnapshot use `python-json-ascii-v1`:
compact sorted JSON with `ensure_ascii=True`, no newline, SHA-256 over ASCII
bytes. CompositionResult and outer/wire identity retain `python-json-v1` UTF-8.
Unicode normalization, integer/float distinctions, signed zero, ordered arrays,
and complete diagnostics/coverage/counterexamples remain observable. Replay must
also reject raw representation changes that a record importer could normalize
away. Complete result field inventories and effective resource trees are frozen
in the profile records above and checked during every client negotiation.

One reduced ancestor work budget covers input checks, imports, all fresh checker
phases, exact identity computation, replay comparison and publication. Reduced
limits propagate into the corresponding nested checker scopes. Protocol framing
retains its fixed transport bounds; operation payload and derived fragments have
separate declared cumulative accounting. Checker report budgets count keys plus
values and conservatively reserve ASCII publication, while wire node limits count
values. Both the result and the complete outgoing protocol envelope must fit;
a report that fits internally can still fail envelope publication. A report too
large to replay inside a 16 MiB request is explicitly rejected.

`RealizationClient` freezes caller containers before negotiation, validates exact
profiles, effective resources, identities, report encoding and claims, and returns
immutable complete report bytes. The five direct SDK APIs accept explicit `core=`
selection while retaining their existing default behavior. Selected native calls
do not run Python evaluators, acceptance, producer reruns or fallback. Raw-document
backend entry points do not hydrate a Python RealizationRequest, whose current
constructor performs Python lowering verification. Historical pure result views
may be hydrated only with exact round-trip bytes and fingerprints. Full workflows,
exploration/reduction, pipelines, archive/export authority and default cutover
remain separate migration gates; these direct operations do not advertise them.

## Bounded rich-policy operational profile

`policy_operational` negotiates the exact v0.1 operational contract documented in
[policy-operational-v0.1](../docs/policy-operational-v0.1.md). Core and standalone
Verify expose `check-policy-lowering`, `execute-policy` and
`replay-policy-execution`; Core alone exposes `compile-policy` under the additional
`policy_operational_producer` profile. The source-only `policy_frontend` profile
and its results are unchanged.

| Operation | Exact payload fields |
| --- | --- |
| `compile-policy` | `document`, `definitions` |
| `check-policy-lowering` | `document`, `definitions`, `candidate` |
| `execute-policy` | `document`, `definitions`, `candidate`, `timeline` |
| `replay-policy-execution` | `document`, `definitions`, `candidate`, `timeline`, `report` |

The result schema is `biocompiler.core.policy_operational.v1`, with exact fields
`schema_version`, `implementation`, `resource_profile`, `validation_scope`,
`request_fingerprint`, `candidate_fingerprint`, `report_fingerprint`, `candidate`
and `report`. Input identity hashes the complete payload excluding only replay's
retained `report`. Execution bounds are explicit in the timeline and therefore
part of this authority. Replay returns only after complete fresh report equality.

A lowering report retains the original native source assessment, independent
correspondence report and unchanged `artifact=withheld`,
`target_status=unassessed`, `realization=unassessed`. Execution adds its complete
trace and requirement ledger. Unsupported admission, malformed source or values,
changed candidate authority and resource exhaustion do not produce successful
partial results. This profile has no artifact publication operation or implicit
Python fallback and does not establish supplied-realization correspondence.

## Bounded policy implementation v0.1

The separate `bounded-policy-implementation-v0.1` validation scope negotiates
`biocompiler.core.policy_implementation.v1` and
`biocompiler.ocaml.policy_implementation.v0.1`. Core advertises producer operation
`compile-policy-implementation`; Core and standalone Verify advertise
`check-policy-implementation` and `replay-policy-implementation`. Verify does not
link the producer or support the compile operation.

Compile consumes exactly `{request, limits}`. Check consumes exactly
`{request, candidate, limits}`. Replay additionally requires `report`, containing
the **complete saved result wrapper**, not only its inner report. The original
request is a `biocompiler.policy_realization_request.v0.1` with the complete
BuildRequest, exact semantic descriptors, original finite operating domain,
supplied primitive library/catalog bridges and exploration budgets. The separate
limits use `biocompiler.policy_preservation_resources.v0.1`.

The candidate is `biocompiler.policy_implementation_candidate.v0.1`, containing
`behavior`, `implementation` and `binding`. Every check freshly admits original
source, independently checks both IR boundaries, explores the complete supplied
finite domain, reconstructs candidate execution and independently monitors the
original hard requirements. The producer proposes this candidate and invokes the
same checking service. The first family and precise acceptance conditions are in
[bounded preservation](../docs/policy-bounded-preservation-v0.1.md).

The result retains schema/implementation/resource/scope identities, full request,
candidate and invocation fingerprints, the complete candidate and complete report
with its fingerprint. Invocation identity includes the original request, candidate
and limits. Replay recomputes and compares the **entire wrapper**. A serialized
`checked_implementation` is inspection evidence; parsing it grants no checked
native value or export permission. Preservation and hard requirements have
separate outcomes, and incomplete exploration cannot authorize acceptance.

Publication reserves the worst-case escaped legal request identity and protocol
framing. The negotiated result limits are 8,323,072 bytes and 249,968 key/value
nodes; the complete wrapper must fit without trimming. Native work, monitor,
retained trace and publication limits remain distinct from therapeutic capacity.

The Python `PolicyImplementationClient` and policy CLI commands
`compile-implementation-native`, `check-implementation-native`, and
`replay-implementation-native` are inert transport adapters. Each command requires
`--limits`; check/replay require `--candidate`, and replay requires the saved full
wrapper through `--report`. Authoring validation is never executed as a fallback.
CLI exit codes are 0 for checked implementation, 1 for a completed native response
that withholds acceptance, and 2 for input/transport/native protocol failure.
All results retain target/material unassessed and artifact/export withheld.

## Conditional policy material v0.1

The new `policy-truth-mrna-v0.1` scope negotiates
`biocompiler.core.policy_material.v1`,
`biocompiler.ocaml.policy_material.v0.1`, and
`biocompiler.policy_material_resources.v0.1`. Core alone advertises
`compile-policy-material`; Core and standalone Verify expose
`check-policy-material`, `replay-policy-material`, and `export-policy-material`.
The verifier dependency boundary still excludes the producer.

Compile takes exactly `{request, limits}`. Check and export take exactly
`{request, candidate, limits}`. Replay additionally takes the full saved wrapper
as `report`. No operation accepts a saved report as native acceptance authority.
The original `biocompiler.policy_material_request.v0.1` retains the full
implementation request, full supplied material case, exact provider/context
contracts, an original catalog-entry/material-case binding, and aggregate work
and publication budgets. The request profile is
`biocompiler.policy_truth_mrna.v0.1`; `limits` retains the unchanged preservation
resource schema. Fields, timing, resources and unsupported cases are specified
in [material acceptance](../docs/policy-material-acceptance.md).

The candidate schema `biocompiler.policy_material_candidate.v0.1` contains
`behavior`, `implementation`, `binding`, `material_binding`, and `construction`.
Fresh checking reruns source admission, both IR correspondences, full finite
preservation and requirement evaluation, exact whole-graph/material binding,
independent molecular construction, original context contracts and every original
source obligation. Only the complete conjunction creates private native material
acceptance. Missing, unknown, unsupported, incomplete or failed obligations cannot
authorize export. Supplied model-to-sequence and provider contracts are explicit
premises; empirical validity remains unassessed.

The result wrapper contains schema, implementation, resource and scope fields,
request/candidate/invocation/report fingerprints, complete candidate and report,
and `artifact`. Compile/check/replay set `artifact` to null. Replay compares the
whole freshly reconstructed wrapper. Export independently rechecks the full
chain and returns an artifact only from its private accepted material value.
The underlying assessment retains `artifact=withheld` and `export=withheld`;
export does not relabel historical leaf assessments.

The artifact schema is `biocompiler.policy_mrna_export.v0.1`, with exact fields
`schema_version`, `fasta`, `fasta_sha256`, `manifest`, `manifest_sha256`. Ordered
members receive headers `rna_0001`, `rna_0002`, etc., with `alphabet=RNA`,
80-column sequence lines and final newlines. The canonical manifest has no
trailing newline and includes complete original request, candidate, limits,
assessment, their binding fingerprints, the full molecule records and exact
FASTA hash. Its own hash is carried in the outer artifact. The manifest records
that original authority must be retained separately; it cannot substitute for
those original inputs during later checking.

The service reserves complete publication within 8,323,072 bytes and 249,968
key/value nodes, including worst-case legal request identity/framing. It never
trims proof evidence. Aggregate work is explicitly measured as logical data
visits and child semantic work, with charged decoding and startup passes; it is
not a wall-clock or machine-instruction bound. Decoder and child bounds remain
independent requirements.

`PolicyMaterialClient` and `policy.material` transport inert immutable snapshots.
The CLI provides `compile-material-native`, `check-material-native`,
`replay-material-native`, and `export-material-native`, with required `--limits`.
Fresh export requires an output `.zip` and publishes `program.fasta` plus
`manifest.json` as one deterministic stored archive. The Python helper verifies
the fresh native pair, writes and fsyncs a temporary archive, reads back exact
member bytes/metadata, and atomically publishes it. Existing destinations require
explicit `--replace`; original inputs and aliases cannot be overwritten. Failed
checking, cancellation, changed staged bytes and publication failures preserve
prior output. Exit codes remain 0 for acceptance, 1 for a completed nonaccepted
assessment, and 2 for input/transport/native errors. There is no Python semantic
fallback.

## Reusable-component policy material v0.1

The separate `policy-component-mrna-v0.1` scope negotiates
`biocompiler.core.policy_component_material.v1`,
`biocompiler.ocaml.policy_component_material.v0.1`, and
`biocompiler.policy_component_material_resources.v0.1`. Core alone advertises
`compile-policy-component-material`. Core and producer-free Verify expose
`check-policy-component-material`, `replay-policy-component-material`, and
`export-policy-component-material`. Payload shapes follow the conditional
material operations above; capability negotiation requires the exact component
profile, and no older material capability substitutes for it.

The closed `biocompiler.policy_component_material_request.v0.1` retains the
original `implementation_request`, supplied `component_library`,
`composition_rule`, `catalog_binding`, `input_bindings`, `resource_bindings`,
`context`, and `budgets`, plus `schema_version` and the
`biocompiler.policy_component_mrna.v0.1` profile. Its candidate schema is
`biocompiler.policy_component_material_candidate.v0.1`, with `behavior`,
`implementation`, `binding`, `assembly_proposal`, and `construction`.
The original source request remains the authority throughout checking.

Fresh checking independently reconstructs source/IR preservation, exact component
ownership and wiring, ordered assembly and molecular construction, complete
context records and shared resource demands, original catalog binding, and every
source obligation. Only their complete conjunction can authorize export. This
bounded profile supports one RNA assembled from one decision component and one
reusable driver, with no helpers or alternative selection. Two supported policy
families can use the same unchanged driver specification. Supplied component,
composition and provider contracts are premises; empirical behavior is unassessed.

The wrapper binds the full original request, candidate and invocation limits.
Compile/check/replay withhold artifacts; replay compares the entire fresh wrapper.
Fresh export emits `biocompiler.policy_component_mrna_export.v0.1` and a canonical
`biocompiler.policy_component_mrna_manifest.v0.1`, retaining original inputs,
assessment, exact molecule records and paired FASTA/manifest hashes.
`PolicyComponentMaterialClient` and `policy.component_material` provide immutable
Python transports and the same atomic, independently read-back ZIP publication
used by the conditional material route. This increment adds no component CLI
command or top-level Python re-export.
