# Construct IR and frozen assembly authority

This document governs the existing exact-reference CDS profile. The separate
[molecular-design profile](molecular-design-v0.1.md) uses independently frozen
fragment/layout authority for multi-region structural RNA candidates and has its
own versioned construct schema and checker. It does not broaden reference acceptance.

M5 introduces a checked representation of how selected components occupy a
sequence reference. It starts with one whole, reviewed CDS. The Construct IR
does not contain emitted nucleotide text, an acceptance certificate, or a claim
that the CDS is a complete delivered molecule.

`ConstructRequest` is the authority supplied before assembly. It embeds the
exact `CompositionRequest`, including its target, component selection, registry
lock and requirement IDs. A `ConstructReference` binds each selected instance
to an independently trusted `ReferenceSelection` containing both manifest and
record identity, version and content hash. Expected molecules, placements and
relationships belong to this request. `ConstructCandidate` carries its own
proposed layout, the request/composition fingerprints and the registry lock.
The independent checker compares the proposal with the request and the current
reference/registry snapshots. Agreement with a candidate's own claims is not
acceptance.

The optional `source_request_fingerprint` records archival input lineage. The
supported profile permits only the embedded composition fingerprint or an
explicit omission. It cannot name an arbitrary report as evidence of acceptance.
The request's top-level target and component-node inventory are derived from
the composition. The candidate's node inventory is derived from its placements.
JSON import rejects contradictory duplicates of these inventories.

## Layout records

All records are frozen and versioned. Every parser rejects missing or unknown
fields, malformed nested shapes, duplicate identities and unsupported schema
versions with `SerializationError`. Arrays are frozen as tuples. JSON exports
are independent copies. Array order is preserved; molecular component order is
also explicitly recorded and checked. An incomplete or unsupported inventory
may be schema-valid so the independent checker can report its limitation.

| Record | Information retained |
|---|---|
| `ConstructMolecule` | Stable ID, DNA/RNA alphabet, artifact class, length, explicit component order, topology, completeness, unknown features and compartment |
| `ComponentPlacement` | Selected instance and component lock, destination molecule, pinned reference, source and destination intervals, orientation, reading frame, requirements and authoring source |
| `ConstructFeature` | Feature kind and boundaries, reference interval, source locator, orientation and nonempty pinned source/review provenance |
| `ConstructJunction` | Adjacent selected instances, direct junction/overlap/gap, explicit coordinates, stated choice and optional pinned provenance |
| `RegulatoryRelationship` | Regulator and target instance IDs, relationship kind, source/review identities and explicit assumptions |
| `ConstructDependency` | Consumer/provider molecules, dependency kind, requirement IDs and an explicit assumption |

Multiple molecule records and co-payload dependencies are representable.
`same_cell` dependencies require an explicit assumption; sharing a manifest
does not establish that two payloads enter the same cell. The initial assembler
and checker reject multiple molecules, co-payloads, junctions and regulatory
layouts as unsupported.

Subcomponent features cannot omit pinned boundary provenance. Providing a
source identity is still only a claim to be checked against a source with exact
coordinates. The current reviewed reference supplies the whole-CDS boundary;
the initial checker accepts that boundary through the component placement and
rejects additional feature annotations. A domain diagram does not establish
precise nucleotide boundaries.

## Coordinates, orientation and frame

[`SequenceRange`](../src/biocompiler/semantics/coordinates.py) defines the central
convention `zero-based-half-open-reference-5prime-to-3prime.v1`. The interval
`[start, end)` includes `start`, excludes `end`, and has length `end - start`.
Coordinates count normalized nucleotide symbols, not source-document bytes or
raw extraction whitespace. Endpoints must be integers, not booleans, with
`0 <= start <= end`. Placements and features require nonempty ranges; an empty
range is permitted for a direct junction. Overlaps and gaps require an explicit
nonempty span.

Source coordinates refer to the pinned record's 5′ to 3′ spelling. Destination
coordinates refer to the declared molecule spelling. Orientation is separately
`forward` or `reverse`; reverse denotes reverse-complement traversal and does
not change coordinate indexing. Reading frame is `0`, `1` or `2` relative to the
first symbol of the oriented source slice. `null` asserts no frame. These fields
do not themselves establish an open reading frame or authorize a sequence
transformation. Reference normalization remains the pinned manifest's existing
policy, with its independently retained DNA and RNA spellings.

The supported reference construct occupies exactly `[0, reference.length)` in
both coordinate spaces, in forward orientation and frame zero. It retains
`CDS-reference-only` completeness and every unknown feature from the reviewed
record. Topology and compartment remain `unspecified`. The system does not add
a promoter, UTR, scaffold, poly(A) tail or backbone.

## Identity and evidence invalidation

`layout_dict()` and `layout_fingerprint` cover molecule/placement inventories,
features, junctions, regulation, dependencies, assumptions, source/requirement
lineage and the evidence policy. Request and candidate fingerprints additionally
cover their distinct authority roots. Full fingerprints include captured source
locations; they are not advertised as source-path-independent semantic IDs.

`LayoutEvidencePolicy` is serialized with each request and candidate. Changes
to membership, order, orientation, boundaries, junctions, frame, regulation,
localization or payload partitioning invalidate affected composition and behavior
analyses. The policy cannot be weakened during construction or import. It is an
invalidation rule, not proof that those analyses were rerun. The current checker
reruns component linking and verifies exact CDS layout; it grants no molecular
behavior or empirical evidence. Historical reports cannot authorize a changed
layout.

See [independent construct checking](construct-checking-v0.1.md) and
[toolchain contracts](toolchain-contracts.md) for acceptance and freshness rules.
