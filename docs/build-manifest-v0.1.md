# Reference build manifest v0.1

`ReferenceBuildRequest` is the frozen authority for the supported
`reference_cds` build profile. It wraps a caller-trusted `ConstructRequest`, fixes
scope to `exact_cds` and records the FASTA line width. The request begins with
selected components and references. It does not fabricate an intent program or
claim an unimplemented behavioral refinement.

The current profile accepts the supported whole DNA-CDS or RNA-CDS construct
through the existing independent checks. Schema validity alone does not establish
that a construct is supported. Richer requests retain their explicit diagnostics
when checked.

## Portable source locations

Every source location inside a reference build request must already use a logical,
relative POSIX path, such as `examples/reference_construct.py`. Absolute paths,
Windows drive names, backslashes, control characters, empty segments and `.` or
`..` segments are rejected. Locations are checked recursively, including both
component and placement ancestry.

The build API does not rewrite legacy source paths or repair their fingerprints.
Choose logical source names before freezing the composition and construct request.
The same frozen request can then move between checkout directories without
changing its meaning or identity.

`RunMetadata` is a separate optional document containing a UTC timestamp, machine
label and mapping from logical source names to absolute host paths. These paths are
informational. Reading metadata never opens them. It supports POSIX and Windows
absolute paths and freezes its location mapping.

## Inventory and accepted-stage identities

`BuildManifest` records the request fingerprint, package version, toolchain pins,
file inventory and the ordered component, construct and molecular stage identities.
Its fixed profile, status and scope are `reference_cds`, `complete` and `exact_cds`.
These fields archive what a build claimed; parsing them does not grant acceptance.

Each `AcceptedStage` records the actual payload schema and two separate hashes:
its canonical payload fingerprint and its full `StageRecord` fingerprint. The
latter binds the stage's dependencies, evidence and source correspondence. The
profile requires the current schemas for all three stages, in that order.

Each `ToolPin` identifies a tool, version and content fingerprint. Tool IDs must be
unique. The runtime verifier must compare the complete toolchain against the
trusted implementation it actually runs; a self-reported version is insufficient.

Each `PackageFile` declares a path, role, SHA-256 digest of exact bytes and byte
length. Required paths and roles are fixed:

| Path | Role |
| --- | --- |
| `request.json` | Frozen reference build request |
| `inputs/registry.json` | Locked component registry |
| `stages/components.json` | Accepted component-stage record |
| `stages/construct.json` | Accepted construct-stage record |
| `stages/molecular.json` | Accepted molecular-stage record |
| `molecular.json` | Structured exact-CDS specification |
| `sequence.fasta` | Exact selected nucleotide sequence |
| `result.json` | Build summary, lineage and remaining obligations |
| `checks/construct.json` | Independent construct check |
| `checks/molecular.json` | Independent exact-sequence check |
| `checks/composition.json` | Independent component check |

Offline reference inputs use the repeated `reference-input` role under
`references/<reference-set>/<file>`. A complete manifest requires reference inputs
as well as every fixed-role file. Runtime package verification also checks the
full expected reference inventory and its source/review identities.

Inventory paths must be canonical relative POSIX names. Duplicate names,
file/directory prefix conflicts, traversal and unsupported role/path combinations
are rejected. Root `manifest.json` and `run.json` are reserved and excluded from
the inventory. This avoids a recursive manifest hash and keeps run metadata out of
canonical build identity.

## Reproducibility boundary

`BuildManifest.build_fingerprint` is the fingerprint of its canonical structured
content. It is an accessor, not an extra serialized self-hash. File and tool
inventories are sorted by path and tool ID; declaration order does not change
identity. Accepted-stage order is semantic and remains fixed.

Changing a packaged byte, file length, request, stage identity, tool pin or package
version changes canonical build identity. Changing separate run metadata does not.
The sequence hash continues to identify nucleotide symbols only; FASTA wrapping
changes file and build identity while preserving canonical sequence identity.

Byte-for-byte reproduction covers the canonical package generated from the same
frozen request, reference bytes and toolchain, without varying run metadata.
When run metadata is included, its execution-specific bytes can change the outer
archive while all inventoried files and canonical build identity remain stable.

## Import and acceptance

All schema records are immutable and versioned. Parsers reject unknown fields,
duplicate JSON keys, malformed shapes, unsupported profiles and invalid hash or
coordinate declarations. They return `SerializationError` at malformed import
boundaries.

Manifest parsing establishes structural validity only. Archive verification must
check the exact member inventory, lengths and byte hashes. Accepted build reuse
then requires strict parsing of the referenced artifacts, current evidence
freshness and independent offline reconstruction. Neither an archived success
label nor a matching hash substitutes for that reconstruction. No imported
artifact executes authoring code or retrieves an unpinned remote dependency.

See [Molecular IR](molecular-ir-v0.1.md) for sequence and feature identity, and
[the exact-CDS pipeline](exact-cds-pipeline-v0.1.md) for the checks that establish the
narrow accepted scope. Complete delivered payload and biological obligations
remain unresolved in this package.

## M10.5 schema update

Build manifest schema v0.2 fixes `intended_use=software_test` and `human_therapeutic_admission=not_admitted`. The accepted Molecular stage uses `biocompiler.molecular.v0.2`; the package toolchain pins the admission policy. [Current admission rules](human-admission-v0.1.md) apply before build, fresh verification and publication. Reconstruct affected software packages from independent inputs; old manifests cannot be relabeled into current authority.
