# Human immune circuit profiles and subordinate reference authority

## Context

The next circuit work must reproduce published human-cell RNA constructs while
serving one product: complete DNA/RNA payload specifications for immune cells
engineered in vivo in humans. A research paper's cell line is evidence context,
not a replacement for the intended immune recipient. An organism label or a
protein-coding sequence alone establishes neither recipient eligibility nor
functional support.

The existing HumanTargetContract fixes human taxon and in-vivo engineering, but
describes cell subtype through a TargetClaim. Circuit selection therefore needs
an explicit immune identity bound to that exact target authority. Existing
reference, synthetic and precursor schemas have historical meanings and must
not acquire new evidence claims through a migration.

## Decision

Add versioned circuit-profile contracts with two narrowly defined purposes:

1. Human immune payload planning retains the complete original human target and
   any authored behavior/deployment/acceptance wrappers, plus an explicit typed
   immune-recipient identity. The identity binds the target and subtype claim;
   it does not certify that a physical cell has that identity. Evidence-based
   applicability and therapeutic admission remain independent obligations.
2. Human reference reconstruction records the actual human source-experiment
   context and exact reproduction choices. It supplies supporting reference
   artifacts through shared compiler passes, without a fabricated therapeutic
   context or a second general-purpose organism compiler.

Product scope, source-experiment context and component provenance are distinct.
New recipient/reference contexts are human-only. Synthetic or heterologous part
origin is preserved without becoming an alternative recipient or a human-use
permission. Human non-immune cell-line results are reference evidence only.

Exact reproduction must lock material identity and the declared molecular form.
R0 establishes the mode and DNA/RNA modality contract; original material and
processed-form authority are later R1/R3 obligations.
Candidate design is a separate human immune-payload mode and cannot inherit
reference evidence after a sequence, chemistry, target or implementation change.
DNA templates, delivered DNA and delivered/processed RNA remain separate forms;
unsupported forms are explicit rather than implicitly converted.

The profile checker is reusable at import, planning, selection, verification and
export. It validates the full frozen request at the current boundary. Fresh
verification takes separately retained expected-request authority, reevaluates
the current policy and compares the complete assessment. Saved status fields
and self-updated hashes confer no authority.

Scope eligibility, base fidelity, source-described nominal specification,
complete nominal molecule, mechanism correspondence, model assessment,
experimental correspondence and therapeutic admission remain separate dimensions.
R0 supplies scope and claim contracts only; it emits no molecule, establishes no
sequence fidelity and admits no human therapeutic implementation.

## Versioning and compatibility

New schemas and policy identities are explicit. Unknown fields, versions, forms
and modes fail strict import. Their canonical identities include target,
recipient, source context, mode, molecular form and boundary. A changed boundary
requires a new current check; a previous planning result is not an export token.

Old profiles retain their exact semantics and regression identity. An artifact
cannot be upgraded by rewriting a schema string or relabeling a status. Any
supported migration must construct the new complete request and run current
checks under independently retained authority. Historical fixtures remain
software-only and are not added to the human reference corpus.

## Consequences

The next authoring, mechanism, assembly and UI increments have a checked common
boundary, while the unresolved molecular and evidence obligations remain visible.
R1 curates independent source authority before a family can claim reproduction.
R2/R5/R6a/R12/R13 must preserve these contracts in the actual human target path.
No molecular backend or UI is allowed to turn a reference-only success into
complete payload or biological acceptance.

The normative inventory, source-review and early UI decisions are in the
[profile guide](../human-circuit-profile-v0.1.md). The full dependency sequence is
the [R0–R13 plan](../rna-circuit-reproduction-plan.md).
