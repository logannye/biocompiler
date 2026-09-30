# 0006 — Reconstruct circuit transformations from independent supplied authority

Status: implementation in progress under R4. The public family interface remains
provisional until R6. This decision does not close R4's processing, translation,
whole-modality or complete export acceptance criteria.

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

The first core implements slicing, ordered concatenation, nucleotide orientation
and explicit coding-strand DNA-to-RNA symbol mapping. Their capability is software
correspondence only. RNA/protein processing, editing, translation variants,
complex assembly and complete modality/export gates remain separate R4 work.
Existing ordinary-CDS, legacy molecular design and therapeutic admission checks
remain unchanged. All development fixtures are explicitly artificial.

## Limits and claims

Authority, generated values and reports have bounded versioned schemas. Work
limits apply before sequence allocation and cumulatively across the operation
graph. Nominal species, required roles, experimental quantities and original
source obligations remain separate. A complete software reconstruction does not
prove source-paper fidelity, cellular processing, logic-gate function, external
provider availability, experimental material identity or human therapeutic use.
