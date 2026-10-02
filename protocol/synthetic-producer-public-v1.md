# Complete build authority for public synthetic selection

`select-synthetic-build-request` is a Core-only preparatory operation with exact
payload fields `profile`, `limits`, and `build_request`. Its immutable declaration
is [synthetic-producer-public-v1.json](synthetic-producer-public-v1.json). It imports
the entire original `SyntheticBuildRequest`, including fields which do not affect
selection but remain part of independent package authority.

The native service preserves constructor order: fresh realization source/lowering
checks, complete history import, complete config import, explicit finite horizon,
package profile, intended use, source artifact scope, portable source locations,
and exclusion of host locations/timestamps. History requires full four-field
samples, nonempty snapshots beginning at numeric zero, strictly increasing times,
and a horizon at least as late as the last snapshot. Both original synthetic
package profiles remain accepted. Portability recursively checks every source
triple throughout the normalized realization, including nested metadata.

The response binds the complete original payload, original build request and
normalized build request separately. It retains `normalized_build_request`, the
exact `production_payload`, and the complete unchanged v1 selection receipt under
`production`. `presentation` contains the native frame count and exit code:
0 for a selected candidate, 1 for a complete selection without a candidate, and
2 for a structured ordinary generator Unsupported outcome. Presentation alone
never establishes acceptance. No original rejection, alternative, historical
check, source identity or unsupported detail is dropped.

The five reduced limits share one work ancestor across framing, typed imports,
fresh source checks, nested production and final response publication. Outer-held
history items are reserved before import and subtracted from the nested producer's
retained-item allowance. Final publication includes the entire outer response,
actual request ID and nested receipt. The existing v1 producer contract is
unchanged.

Four complete original Python reference executions cover combinational selection,
temporal component selection, hard-constraint exhaustion and ordinary Unsupported.
Forty-two malformed authority literals retain exact original error messages and
check source-before-history precedence. These include numeric sample shorthand,
history/schema/config/horizon errors, unsafe paths and host provenance. Deeply
malformed nested realization declarations still use the existing native codecs;
full arbitrary nested-invalid Python diagnostic parity has not been established.
Wire-resource failures intentionally remain explicit native resource diagnostics.

This is a native authority checkpoint. Public CLI routing, complete installed CLI
campaigns, rich SDK compatibility, pipeline freshness and package/export acceptance
remain separate work. No CLI cutover or package acceptance is claimed by this
operation. Native execution and all full hosted validation gates remain required.
