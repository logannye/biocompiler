# Independent reference-CDS construct checking

`check_construct(request, candidate, registry, manifests)` accepts only the
single whole-reference-CDS profile. The frozen `ConstructRequest` supplies the
authoritative selection and layout. The candidate is an untrusted proposal.
The checker does not import the assembler and cannot accept an assembler's
success flag or a previously serialized report in place of recomputation.

The offline manifest inventory is keyed by reference-set ID. Load each manifest
with `load_reference_manifest(path, expected_fingerprint=trusted_hash)` before
freezing this input snapshot. That loader verifies retained source and review
bytes; the checker then validates the immutable manifest and record identity
against the independently supplied selection. A frozen snapshot does not watch
the filesystem for later edits.

For each selected instance, the checker independently recreates its reference
component contract from the reviewed manifest. Exact equality with the locked
registry record prevents a selected record from inventing a dynamic guarantee,
changing its sequence version or silently changing the source selection. The
component linker is rerun against the current composition and registry. Missing
references remain unknown; stale pins and inconsistent records fail.

The supported construct has one molecule inventory entry and one encoded
component. Its zero-based half-open source and molecule ranges are both
`[0, reference.length)`. Its orientation is forward in the source's 5′ to 3′
direction and its reading frame is zero. The alphabet, artifact class, length,
coding-only completeness and unknown features must agree with the reviewed
record. Its delivered-molecule topology and compartment remain unspecified.
The selected component lock, ordered membership, source location, requirements
and conditional assumptions are preserved exactly. This establishes complete
coverage of the reference interval without clipping, unexplained bases or gaps;
it does not emit sequence text.

The current manifest contains whole-CDS boundaries, with no independently
reviewed nucleotide ranges for subcomponent features. Feature annotations,
junctions, overlaps and regulatory relationships therefore remain unsupported
by this checker even when the general IR can represent them. A domain diagram
or free-text citation is insufficient to assign nucleotide coordinates.
Multiple molecules, co-payload placement, providers and explicit construct
dependencies are also represented but cannot pass this initial assembly
profile. A shared manifest establishes no same-cell coexistence claim.

`check_construct_request(request, registry, manifests)` validates the frozen
authority before an externally selected Components root is admitted. It returns
diagnostics and does not depend on a candidate. The subsequent full candidate
check compares all layout fields and dependency identities with that validated
authority; a malicious candidate cannot replace the caller's request with an
internally consistent alternative.

`ConstructResult` is immutable and records exact request, candidate, layout,
composition, registry, registry-lock, target, reference and checker identities.
Its diagnostics retain the affected component, molecule, source and requirement
IDs. Outcome precedence is fail, unsupported, unknown, then pass.
`result.freshness(request, candidate, registry, manifests)` reports which current
inputs changed. Every layout edit changes the layout and candidate roots,
including order, orientation, frame, membership, boundaries, dependencies and
source correspondence. An imported result is a historical record and cannot
authorize a new candidate or preserve previous behavior evidence.

A passing result establishes the stated coding-reference layout only.
Component compatibility remains conditional on its declared contracts; neither
complete delivered-payload construction nor molecular behavior is established.

The M10.5 construct checker/result uses v0.2 and includes the current human admission policy in its dependency snapshot. It reruns composition admission; matching candidate/request metadata cannot authorize a human implementation. See [admission](human-admission-v0.1.md).
