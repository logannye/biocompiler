# 0006 — Reconstruct circuit transformations from independent supplied authority

Status: implemented for the R4 supplied-construction software profile in
`0.1.0.dev24`, subject to exact-revision validation before merge. The public
family interface remains provisional until R6. Source-backed mechanism families
and the R12 complete export system remain open.

## Problem

R3 can preserve supplied molecule spellings, nominal chemistry and annotations.
Those declarations do not establish that a transformed molecule corresponds to
its sources. The existing same-alphabet, equal-count `AssemblyOrigin` cannot
represent a DNA-to-RNA symbol transformation or a codon-to-residue relationship.
Relaxing that assembly invariant would make ordinary coordinate coverage
ambiguous. Treating a generated output as a new independent source would make
verification circular.

## Decision

A frozen construction request carries the entire original human `CircuitRequest`,
independently supplied root records, explicitly ordered operations, sequence-free
output metadata, chemistry/feature transition authority and required member
roles. Root sources are separate from the final payload set. Internal references
name declared roots or operation products; they do not require future generated
fingerprints. Typed parsing rejects forward references, cycles, reused frames,
orphan operations and missing member declarations.

The executor produces candidate intermediate values and compact derivation
segments. Final covalent members use the independently reconstructed intermediate
frames as ordinary assembly sources. A separate derivation chain connects those
frames to actual supplied roots. Every output residue must be accounted for; a
supplied literal is a root, never a hidden string in output metadata.

The independent checker reads the complete separately retained request and
reconstructs operations without importing the producer. It compares every
intermediate spelling, coordinate map, chemistry declaration, annotation and
final member, even if a candidate's self-reported hashes have been recomputed.
Saved assessments require fresh complete replay; parsing a saved PASS grants no
new authority.

Chemistry and feature transitions are explicit. Exact chemistry inheritance is
restricted to complete unchanged material declarations with an identity residue
map. Otherwise every incoming facet and annotation has a declared disposition.
Mapped correspondence is checked against independently reconstructed coordinates;
a declared replacement specifies product chemistry without proving biochemical
fate. Unknown or unsupported transitions cannot acquire strict success.

The executor implements slicing, ordered concatenation, nucleotide orientation,
explicit coding-strand DNA-to-RNA symbol mapping, declared RNA/protein cleavage
and splicing, circularization, canonical/chemical edits, ordinary/conditional
and multi-ORF translation, residue-preserving skipping and nominal complexes.
All remain software correspondence to supplied authority. Splicing preserves
declared path order but currently supports increasing spans within each source;
it never silently sorts an unsupported path. Translation requires an explicit
forward contiguous AUG-initiated region and terminal stop. Conditional no-product
branches remain unsupported pending family-specific absence semantics.

Final requested linear/circular DNA/RNA members require explicit payload-region
contracts. Declared nucleotide complexes expand to their covalent constituents;
missing chemistry, regions, members or stoichiometry blocks complete handoff.
Contracts do not infer functional regulatory elements. Build/verify/export and
`compile(CircuitConstructionRequest)` share one public path. Export replays the
independent authority and atomically publishes the complete retained build JSON;
it is not the later multi-format archive or human deployment export.

Preflight order is deterministic in producer and checker. Common inputs and
coordinates are checked first; port form precedes editing/translation allocation.
Translation checks path/frame/AUG and known modification inventory before work
reservation. Skipping allocation and codon interpretation follow reservation.
Editing checks modification inventory and edit symbols after reservation.
Attempted work stays consumed when materialization fails; sibling outputs remain
atomic. Combined-defect and exhausted-budget cases exercise these phase rules.

Existing ordinary-CDS, legacy molecular design and therapeutic admission checks
remain unchanged. All development fixtures are explicitly artificial.

## Limits and claims

Authority, generated values and reports have bounded versioned schemas. Work
limits apply before sequence allocation and cumulatively across the operation
graph. Nominal species, required roles, experimental quantities and original
source obligations remain separate. A complete software reconstruction does not
prove source-paper fidelity, cellular processing, logic-gate function, external
provider availability, experimental material identity or human therapeutic use.
