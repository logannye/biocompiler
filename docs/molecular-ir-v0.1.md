# Molecular IR v0.1

This document governs exact-reference CDS artifacts. The separate
[molecular-design profile](molecular-design-v0.1.md) wraps a complete structural
RNA `PayloadMolecule` with request, construct and fragment-source identities.
Its generated-candidate checks are distinct from exact-reference reproduction.

`MolecularArtifact` is an immutable candidate for the `DNA-CDS` or `RNA-CDS`
profile with `artifact_scope="exact_cds"`. Each record carries an exact nucleotide
spelling and its CDS-only scope. Schema validity grants no acceptance. The
independent molecular checker must reconcile the current frozen construct request,
Construct IR, registry and separately curated reference records.

The initial profiles support one whole forward reference CDS on one coding
segment. They do not specify a complete DNA construct, mRNA, circRNA or delivered
molecule. Encoding selects the corresponding independently extracted DNA or RNA
reference; transcription is a cross-reference consistency check. It is not a
basis for treating DNA and RNA medicines as interchangeable.

## Identity and lineage

The artifact pins the construct request, construct candidate, complete layout,
upstream source request and registry lock. Every molecular record retains its
source instance, molecule, component lock, manifest and reference identities,
source and molecule coordinates, requirement IDs, source location and evidence
relationships. The serialized pass inventory is derived from source instance IDs
with the `cds_record` operation; imports cannot override it.

Three identities serve different purposes:

- `sequence_sha256` hashes the exact uppercase ASCII nucleotide symbols only.
- The artifact fingerprint hashes the complete canonical structured specification,
  including scope, lineage, features, references and policies.
- An exported file hash identifies its exact bytes, including header, wrapping and
  newlines. File layout can change without changing the canonical sequence hash.

The schema accepts only nonempty `ACGT` DNA or `ACGU` RNA. It never strips
whitespace, uppercases, reverse complements or changes T/U during import. Those
operations would otherwise hide an edited candidate. The schema checks fingerprint
syntax; the independent checker recomputes the declared sequence fingerprint.

Coordinates reuse the normalized-symbol, zero-based, half-open convention from
[Construct IR](construct-ir-v0.1.md). Orientation is separate. Sequence length is
derived and serialized; a supplied conflicting length or derived node inventory
is rejected during import. Typed but semantically incompatible frame, orientation,
translation policy or coordinate claims remain candidate data for independent
diagnostics.

## Known, unknown and inapplicable features

Each `FeatureStatus` identifies a feature, its scope, status, reason and optional
known value. Unknown or inapplicable declarations cannot carry a value. Statuses
are unique within each scope.

The reference profile declares the CDS alphabet, reference orientation, coding
boundaries, frame, genetic code, terminal-stop convention, completeness and
canonical sequence identity. All unknown reference features remain explicit.
Domain-feature coordinates are unknown within the CDS; full delivered boundaries,
regulatory context, UTRs, cap, nucleotide modifications, poly(A) tail and delivered
molecule topology remain unknown for the delivered molecule.

Those delivered features are also inapplicable to the abstract CDS spelling as a
complete-molecule claim. These are two different scopes: an inapplicable `cap`
field on a CDS record does not establish that a delivered RNA molecule is uncapped.
The profile preserves unresolved experimental-material identity and molecular
behavior relationships from the reference.

`TranslationPolicy` explicitly states the standard genetic code, frame zero at the
record, required ATG/AUG start and exactly one terminal stop with the terminal
protein star retained. A candidate can declare other typed translation settings;
the exact-reference checker rejects conventions that differ from the reviewed
reference policy.

## Encoding changes and evidence

`EncodingPolicy` fixes `mode="exact_reference"`, `optimization="disabled"` and an
empty transformation list. No synonymous substitution, optimization or implicit
alphabet conversion is enabled by this profile.

`EncodingChange` can archive a future transformation proposal with before/after
sequence hashes, changed properties, a reason and explicitly unverified
preservation claims. Exact-reference acceptance rejects nonempty change records.
A future mode needs a new comparison contract and checks appropriate to its scope.

The serialized `EncodingEvidencePolicy` cannot be weakened. Changes to sequence,
chemistry, end features, topology or boundaries invalidate affected construct,
composition, molecular, structure, expression and behavior analyses. A claim that
protein sequence is preserved does not preserve those analyses. The policy records
what must be rechecked; it is not a receipt that rechecking occurred.

All records use strict versioned serialization, reject unknown fields and duplicate
JSON keys, freeze nested inventories and return `SerializationError` for malformed
imports. An artifact contains no producer-supplied success certificate.

## Software-use labels

M10.5 advances MolecularArtifact to schema v0.2 with fixed `intended_use=software_test` and `human_therapeutic_admission=not_admitted` fields. These change artifact identity, while nucleotide-content hashes are unchanged. Import rejects promotion or missing labels. See [human admission](human-admission-v0.1.md) for fresh checks and migration.
