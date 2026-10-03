# Synthetic inspection protocol v1

`synthetic-inspection-v1.json` is the immutable capability declaration. Only
`bioc-core` advertises or executes these operations. `bioc-verify` rejects them
before importing payloads and does not link the producer service or selection
producer. The existing synthetic producer and public build protocols are unchanged.

Every payload contains the exact declared fields, the profile
`biocompiler.core.synthetic_inspection.v1`, and `limits` (null for defaults or the
complete object of five positive integer reductions). Booleans and floating point
numbers cannot substitute for integer controls. Unknown fields, unsupported
profiles, malformed domain records and incomplete dependency identities fail.

| Operation | Complete supplied authority | Result value |
| --- | --- | --- |
| `inspect-synthetic-mechanism` | `mechanism` | Complete `nodes` in native sorted ready-layer order |
| `inspect-synthetic-check-result` | `record`, `query`, `current` | `exercised_requirement_ids` in coverage order and `freshness` |
| `compare-synthetic-dependencies` | `previous`, `current` | Sorted `changed_dependencies`, preserving numeric kinds |
| `lock-synthetic-registry` | `registry`, `instances` mapping IDs to complete component records | Complete dependency `lock` |
| `resolve-synthetic-registry` | `registry`, `lock` | `instances` mapping IDs to complete resolved components |
| `select-synthetic-registry` | `registry`, `request` | Complete `selection`, including alternatives/admission, and native `outcome` |
| `verify-synthetic-registry-selection` | `registry`, `request`, `selection` | `valid`, determined by fresh complete selection replay |
| `inspect-synthetic-registry-selection` | Historical complete `selection` | Native `outcome` from the structurally validated record |

Check-result query `coverage` requires `current:null` and returns `freshness:null`.
Query `freshness` requires a complete dependency snapshot and returns
`{changed_dependencies, fresh, status}`. This distinction preserves the original
TypeError for `freshness(None)` and `is_fresh(None)`. Non-object dependency operands
use `synthetic_inspection_type` with the original message; malformed objects use
the domain import diagnostic. A null supplied selection represents the original
wrong-result-type case and returns false after registry/request structural import,
without selection replay. A nonnull selection is fully imported before fresh replay.

Results contain exactly the declared `result_fields`. Complete canonical UTF-8
JSON (`python-json-v1`) SHA-256 binds the entire supplied payload, every
operation-specific input field including `query` and null values, and the entire
returned value. No identity field is omitted, and normalization does not replace
original supplied bytes in these identities. Results also carry implementation,
operation, effective resource profile, validation scope and claim scope.

Existing OCaml domain modules implement graph ordering, coverage, dependency
comparison and registry locks/resolution. `Component_selection_producer` implements
selection and verification. The service adds transport, bounded structural import,
identity bindings and publication; it does not duplicate selection semantics.
Registry resolution replays the complete dependency lock. Historical selection
outcome inspection imports a historical record; only the separate verification
operation recomputes selection against supplied current registry/request authority.

One ancestor work budget covers fixed framing, reduced controls, bounded import,
helper execution, selection replay, hashing and final response publication. Framing
terminates on cyclic native JSON and cyclic list spines before ordinary decoders.
Each structural import is measured with the charged bounded codec and precharged
128 work units per complete UTF-8 byte for fixed nested domain construction,
identity sorting, serialization and hashing. Resolution additionally reserves the
worst complete component expansion before lock replay. Selection uses its existing
bounded producer with the same ancestor and the outer selected limits. The default
50-million work ceiling is not increased. Larger structurally admissible values may
still exhaust this combined work allowance.

Retention counts every supplied JSON value/object key plus resolved component and
selection inventory occurrences. Request bytes cover the complete payload plus a
separator. Report bytes and key/value nodes cumulatively cover the complete value,
complete result and final protocol response, using conservative ASCII bytes before
UTF-8 wire publication. Resolution reserves repeated component fragments before
constructing its result map. Every successful reduction is published in resources;
all five controls can independently reject an otherwise valid request.

Freshness here is equality of complete supplied snapshots. None of these helpers
establishes current whole-program acceptance, empirical biological function,
package/export acceptance or human-use admission. Storage, historical PASS and a
matching receipt cannot grant those claims.

`tests/conformance/synthetic-inspection-supplemental-v1.json` retains 28 complete
supplemental observations, original Python source hashes and the independent capture
source. It supplements the complete original helper corpus; it does not replace or
narrow that corpus. Native tests compare full values, identity envelopes, exact
original errors, role rejection, five reduced limits, Unicode, cycles and shared
ancestor exhaustion. Native compilation and executable validation run on hosted CI.
