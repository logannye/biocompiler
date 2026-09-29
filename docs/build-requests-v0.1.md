# Frozen build requests v0.1

The authoritative compiler input is a `BuildRequest`, not the bindings reported
by generated Behavior. A request copies and freezes the graph, typed input
overrides, defaults actually used, resolved bindings, target, requested artifact
scope, execution profile, implementation constraints, preferences and elaboration
provenance. No authoring Python executes while importing or lowering a request.

```python
from cellweave.compiler.request import BuildRequest
from cellweave.compiler.behavior import lower_to_behavior, verify_lowering

# intent is the result of therapy.freeze(); it is already an immutable graph.
request = BuildRequest.freeze(intent, parameters={"threshold": 1})
behavior = lower_to_behavior(request)
report = verify_lowering(request, behavior)
saved_input = request.to_json()
```

Changing both an emitted parameter node and its output binding manifest from `1`
to `9` fails verification against this request. Selecting `9` requires a new input
request with an explicit override; it cannot mutate the previously accepted
request. Serialized requests also rederive their bindings from the frozen intent
and explicit overrides, so changing only a derived binding/default record fails
import. Content hashes establish identity and correspondence, not signatures or
authorization to replace an input request.

## Two immutable phases

1. Freeze the intent, target and design bindings as a `BuildRequest`.
2. Lower Behavior and verify it against that request.
3. Author response bands, deadlines and an operating domain against that exact
   Behavior identity, then freeze a `RealizationRequest`.

```python
from cellweave.compiler.request import RealizationRequest

realization = RealizationRequest.freeze(request, behavior, contract, domain)
assert realization.upstream_request_fingerprint == request.fingerprint
```

A realization request requires an explicit `TargetContext`. Its constructor and
deserializer recheck lowering authority, the contract's Behavior fingerprint and
the selected role. The independent realization checker still checks observation
coverage, endpoint semantics, contract completeness and each finite history.
Freezing a request does not establish that a candidate satisfies those contracts.

The second phase contains the unchanged upstream request, verified Behavior,
contract and domain. Its semantic fingerprint depends on those four identities.
The upstream fingerprint contains no contract or downstream fingerprint. Changing
a response band creates a different second-phase request without mutating the
first phase or introducing a circular hash dependency. Pass/check records must
retain the upstream request identity separately from the graph identity:
different targets or constraints may share the same Behavior graph.

## Design values, variation and runtime observations

Each parameter has a `BindingMetadata` record whose category is `user_selected`
(the default), `compiler_selected`, `measured` or `uncertain`. Typed resolved
values preserve their declared units, serialized values and canonical values.
Metadata records semantic provenance references, such as a calibration or
selection-policy identity; file locations and recording times belong in the
separate elaboration provenance location fields.

An optional `allowed_variation` is a serialized typed `Interval` with compatible
units. The frozen scalar value must lie within it. This records the variation
obligation; abstract execution evaluates the selected value and does not prove
correctness over the interval. Interval/curve design parameters remain expressible
in requests but are unsupported by the current scalar Behavior execution profile.
Compiler-selected metadata also does not imply a search was performed: the
selection's provenance and configuration must be supplied by its producer.

Signals remain runtime observations. `request.runtime_observations` lists their
node IDs, including signals retained as graph metadata; exact used observation
coverage is checked later against the selected role and operating domain. A
`runtime_observation` parameter category is rejected. Missing parameters and
incorrectly typed values identify their source nodes and source locations;
unknown names list the source program and declared parameter identities.

Python `if`, loops and external reads run during authoring and choose the graph.
They do not run inside a cell. For example, Python choosing which `cells.when(...)`
declarations to author is a design decision; `cells.when(signal.present())` is an
explicit runtime condition. Use the language's condition, temporal and state
operators for runtime behavior. A frozen request preserves the resulting graph,
so importing it never repeats a random choice, file read or environment lookup.

## Reproducible elaboration and identities

`ElaborationProvenance` separates these fields:

| Field | Meaning | Included in request semantic identity |
| --- | --- | --- |
| `source_identities` | Stable logical source names mapped to supplied content identities | Yes |
| `dependency_identities` | Stable dependency names mapped to pinned identities | Yes |
| `external_inputs` | Explicit captured inputs, including random seeds and external selections | Yes |
| `locations` | Logical source names mapped to archival file locations | No |
| `recorded_at` | Provenance recording timestamp | No |

Provenance is explicitly supplied by the caller. Empty provenance means it was
not supplied; the API cannot recover unrecorded external inputs or certify the
authoring environment. Source identities should identify content, not absolute
paths. The frozen graph is always included, even when authoring provenance is
incomplete. Source text alone is not sufficient to reproduce arbitrary Python
elaboration.

`request.fingerprint` hashes canonical JSON with sorted object keys, compact
separators, UTF-8 text and finite JSON numbers. It excludes graph source locations
and provenance locations/timestamps. `request.artifact_fingerprint` includes
those archival details. Both request phases expose this distinction. Moving a
workspace therefore preserves semantic identity while retaining independently
inspectable source correspondence. Semantically equivalent alternative numeric
encodings are not promised identical identities; exact typed input encoding is
preserved. `to_json()` emits the complete archival form.

Every top-level record and nested artifact has a versioned schema. Imports reject
unknown or missing fields, duplicate JSON keys, nonfinite numbers, unsupported
schema versions, unsupported Behavior profiles and inconsistent derived fields.
There is no implicit migration. A future migration must be explicit and produce
a new versioned artifact/identity. Supported requested scopes are
`abstract_behavior`, `synthetic_realization`, `exact_cds` and `complete_payload`.
The latter three require a target. Recognizing a requested scope is not a claim
that its compiler backend or acceptance checks exist. Constraints and preferences
are preserved input declarations; a destination pass must interpret supported
ones or reject them before accepting an artifact.

## Compatibility

`lower_to_behavior(intent, parameters=...)` remains supported and internally
freezes those inputs. `verify_lowering(intent, behavior)` authorizes only the
intent's defaults. Callers that selected overrides must pass the original
`parameters=...` again or retain a `BuildRequest`. Verification never infers an
override from output-reported bindings. Passing additional parameters alongside
an existing request rejects the call; create a new request instead.

Existing `BuildProfile` and `RealizationPlan` retain their planning behavior.
`profile.freeze_request(intent, **request_options)` and
`plan.freeze_request(**request_options)` establish the explicit freezing
boundary. Incomplete design bindings reject that conversion, while unresolved
molecular choices remain visible and do not become implemented merely because
inputs are frozen. `compile()` accepts the plan or either request phase and
continues to raise `CompilationUnavailableError` until a supported molecular
artifact profile exists.
