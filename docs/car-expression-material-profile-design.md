# Exact expression-material profile for the CAR MVP

Status: **M1 v0.2 assessment correction implemented in the working branch;
focused local validation and direct native workflow probes passed; hosted/main
acceptance pending**. The correction follows
[ADR 0010](decisions/0010-versioned-expression-obligation-dispositions.md) and
[M1 in the refactoring roadmap](architecture-refactoring-roadmap.md#m1--correct-claim-dispositions-and-make-their-algebra-explicit).
The [capability matrix](capability-matrix.md#cap-11-static-car-expression) retains
the separately recorded main and published snapshots.

The original C3 preparation status was **implemented source candidate; hosted
native, installed and release acceptance pending**. That historical status and
the bounded C3 decision in the
[CAR MVP roadmap](car-mvp-and-expansion-roadmap-2026-10-10.md) are preserved;
M1 does not rewrite their evidence or reference pins.
The [first research task](car-first-research-task.md) selects RM_61461 for a
scoped nominal-reference handoff. Its [qualification record](car-rm61461-qualification.md)
separates copied sequence, source-declared chemistry, an explicit designer-supplied
3′ end and unresolved biological applicability. Local source/transport controls
do not close the native or release gates.

## 1. Decision and exact claim

Add one closed native **expression-material** profile for a single complete RNA
encoding one exact supplied protein for one declared human immune recipient
role. It checks a source-requested encoding and localization correspondence
under an explicit supplied expression/localization contract. It does not execute
a synthetic finite machine in place of the receptor mechanism.

The accepted statement is:

> This exact reconstructed RNA encodes the source-selected complete product,
> occupies the selected material/CDS location, satisfies the stated structural
> constraints, and matches the supplied expression/localization contract and its
> declared recipient context. Expression and localization in that context remain
> conditional on the identified premises.

The statement does **not** establish expression magnitude, surface localization,
antigen recognition, signaling, killing, exhaustion, delivery, persistence,
shutdown or human in-vivo efficacy. Evidence for those claims is a separate C2
qualification result. A matching sequence or contract hash is not that evidence.
If C1 requires any of those behaviors to be implemented, this profile alone does
not close C3: return an explicit unsupported requirement until its real mechanism
and corresponding checker exist.

No sequence optimization, codon redesign, inferred UTR/tail, inferred chemistry,
or automatic replacement of missing material is included.

## 2. Honest source construction using the current typed language

The current `Effect` is an attempted runtime action. Its mandatory
`EffectLifecycle` carries authorization, loss/unknown behavior, cancellation,
completion, failure and feedback identity. Current operational admission gives it
abstract-attempt semantics; it has no native receptor-expression interpretation.
An arbitrary initiating `Rule`, completion event or timeout would add behavior
that the static encoding task did not request.

**Admit no `Effect` or `Rule` in this profile.** Use the existing typed
`BuildRequest` with one explicit `Requirement(kind="objective")` whose complete,
versioned requirement definition specifies the static expression-material
objective. Generic structural admission currently retains such requirements; it
does not prove them. The new native checker supplies the narrow semantics below.
An objective with the same English description or an unrecognized definition
does not match.

The public immutable `ExpressionMaterialRequest` carries a typed `BuildRequest`,
`ExpressionSelection`, complete supplied expression and structural authority,
project context and `ExpressionBudgets`. It exposes `.document`, `.selection`,
`.budgets` and detached `.to_request()`. The reference authoring factory
`rm61461_request` builds this supported shape without executing compiler code.
Neither grants acceptance. There is no temporal `.to_limits()` value.

The new root profile is `biocompiler.policy_expression_source.v0.1`. Nested
`PolicyProgram` and `SemanticBundle` retain `biocompiler.policy.v0.1`; their typed
declarations and definition identities are reused without rewriting them.

### Closed source subset

| Source item | Admission rule |
| --- | --- |
| Program | Exactly one `Role`, five fixed `Parameter` declarations and one `Requirement`; unique nominal IDs and no holes. Source maps are retained. Declaration order has no semantic role. |
| Recipient role | A single role, `population=None`, `lineage_role=False`, with its complete capability requirements retained and matched against the supplied contract. Exactly one deployment binding identifies its original human immune/immune-progenitor chassis. |
| Product parameters | Three fixed text parameters encode the complete product identity's `id`, `version` and lowercase SHA-256 content fingerprint. Identity kind is fixed to `reference` by this profile. The expected product body is the existing `policy_mrna_structure.product_content_json` body, including its schema, alphabet and complete sequence extent. |
| Localization parameter | One fixed text parameter names a pinned localization definition in the supplied contract. The value is nominal: it is not a free-text mechanism and is never inferred from a signal peptide or sequence motif. |
| Material constraint parameter | One fixed integer `maximum_rna_nt`, strictly positive and within the profile residue ceiling. This means total emitted nucleotides, including represented UTRs and poly(A), excluding non-nucleotide cap annotations. |
| Objective | `kind="objective"`; `scope=Scope("executor", recipient_ref)`; exact supported requirement-definition body and pin; `applies_to` is the ordered tuple `[recipient, product_id, product_version, product_sha256, localization, maximum_rna_nt]`. The first ref is a Role and the remaining five are Parameters. Every fixed parameter has the exact expected type; `lower`/`upper` are null and `selection="fixed"`. |
| Objective optional fields | `condition`, `response`, `trigger`, `clock`, `deadline`, `lower`, `upper` and `horizon` are null; objective assumptions are empty. Its description is explanatory text, not executable semantics. |
| Deployment | Complete original `Deployment`, route `in_vivo`, one recipient binding; delivery intended recipients exactly that role; RNA format; `design_count=member_count=orf_count=product_count=1`, `helper_count=0`. Copy number, dose and persistence constraints are null. Original environment/delivery definitions and assumptions are retained and matched explicitly. No arrival or expression probability is inferred. |
| Implementation catalog | Exactly one complete supplied implementation entry. Its operation definition is the recognized encoding operation; its realization definition, dependencies, evidence declarations, chassis and RNA format must match the selected expression contract. There is no search or implicit catalog fallback. |
| Assurance | `level="structural"`; requirements exactly the one objective; tolerances and assurance assumptions empty; `horizon="not_applicable"`. This new literal is admitted only by the new expression-source root profile. The report says `temporal_execution: not_requested_by_supported_objective` and never reports simulated or verified time coverage. The factory must not invent a duration. |
| Other declarations or demands | Unsupported, including observations, clocks, encounters, state, channels, machines, transitions, effects, rules, additional objectives, quantitative bounds, temporal guarantees and external-control requests. A valid but unsupported source is distinct from malformed input and from a failed supported equality. |

The mandatory assurance horizon is a present source-layout limitation for a
timeless task. Resolve it with this **versioned source profile**, rather than a
made-up duration or an unversioned widening of the existing language:

- Keep the `BuildRequest` and `AssuranceRequest` Python record classes. Add the
  literal to the latter's type, then require the new root profile, structural
  level and closed objective subset for its use. Generic Python shape decoding
  alone is not semantic admission.
- Keep ordinary native `Policy_document.of_json`'s old accepted language and
  all old request paths unchanged. Add a narrowly named expression-source
  decoder that selects the new root/assurance schema branch and returns the
  same immutable document type. It must independently reject temporal demands;
  it must not normalize the document to an old request with a fabricated horizon.
- Make Python source validation/serialization profile-aware: an old-profile
  BuildRequest containing `not_applicable` is rejected, as is a new-profile
  request with a quantity, `unbounded_requested`, or nonstructural assurance.
  Standalone construction of a data record grants no profile acceptance.
- Native source-assessment metadata must explicitly retain the new root profile;
  do not label its support as an old-profile result. Old reports, schemas,
  fingerprints, exports and negative controls must remain unchanged.
- Initially accept only an explicit BuildRequest at this entry point. Do not
  silently extend the old `CompilationSubmission`, finite-machine or operational
  entry points to accept the new source profile.

A separate `StaticAssuranceRequest` class and BuildRequest union would introduce
another record while still requiring context-sensitive admission. An unversioned
literal addition would change the meaning of the old closed profile. The
root-profile branch above is the smallest strict distinction: current typed
source records, one explicit static assurance value, and no old-path expansion.

The requirement and operation definitions are new closed normative descriptors,
not user-extensible snippets. Their complete typed bodies, version and semantic
digest are checked. Definition text alone never enables the profile. This adds
an explicit source construction without pretending existing `Effect` semantics
already express it, and without introducing a second therapeutic source language.
Other semantic definitions are supplied applicability premises: v0.1 accepts no
executable clauses or formal parameters in them. Require the bundle's exact
reachable definition closure, including the normative definitions and every
recipient/deployment/catalog/localization reference; unused definitions are
unsupported rather than silently ignored.

**Separate open admission gap (AR-11 / M2):** the inspected v0.1 admission
implementation checks pins and reachability but does not enforce the documented
supplied-definition clause/formal restriction. A complete repinned definition
with one unused integer formal was accepted by fresh native check and export at
`18ce1ac64fde799892683460360da008f9e6ae14`; the
[roadmap audit register](architecture-refactoring-roadmap.md#audit-register)
records the exact local diagnostic provenance. An arithmetic assumption clause
also reached material checking, but its extra unresolved obligation withheld
export. Those observations do not make clauses or formals part of the supported
subset. M1 changes report dispositions and census consistency only. A later M2
guard correction needs separate admission tests, including an explicit treatment
of text-only clauses; no supplied clause is executed or discharged by M1.

## 3. Original authority and wire records

### M1 version boundary

The implemented v0.2 boundary changes only these report/implementation identities:

| Identity | Historical baseline | Working-branch M1 |
| --- | --- | --- |
| Assessment schema | `biocompiler.policy_expression_material_assessment.v0.1` | `biocompiler.policy_expression_material_assessment.v0.2` |
| Native checker | `biocompiler.ocaml.policy_expression_material_check.v0.1` | `biocompiler.ocaml.policy_expression_material_check.v0.2` |
| Service/producer implementation | `biocompiler.ocaml.policy_expression_material.v0.1` | `biocompiler.ocaml.policy_expression_material.v0.2` |

These existing identities and their source/material meanings remain unchanged:

| Identity | Retained value |
| --- | --- |
| Request schema | `biocompiler.policy_expression_material_request.v0.1` |
| Material profile | `biocompiler.policy_single_expression_mrna.v0.1` |
| Source profile | `biocompiler.policy_expression_source.v0.1` |
| Contract-body schema | `biocompiler.policy_expression_contract.v0.1` |
| Candidate schema | `biocompiler.policy_expression_material_candidate.v0.1` |
| Result envelope | `biocompiler.core.policy_expression_material.v1` |
| Resource profile | `biocompiler.policy_expression_material_resources.v0.1` |
| Validation scope | `policy-single-expression-mrna-v0.1` |
| Export schema | `biocompiler.policy_expression_mrna_export.v0.1` |
| Manifest schema | `biocompiler.policy_expression_mrna_manifest.v0.1` |

The generic source, static-admission and nominal-structure child schemas and
implementations also remain unchanged. No source semantics, operation signature,
material authority, normative definition or reference-record pin is replaced by
this correction. Retaining a request/profile identity does not make an old
assessment compatible with the changed disposition contract.

The request is a closed record with exactly `schema_version`, `profile`,
`project_context`, `document`, `selection`, `expression_contract`, `structure_authority` and
`budgets`. `document` is the complete original typed BuildRequest. No existing
realization request, operating domain or component graph is synthesized.

`selection` contains the source objective ID, recipient role ID, complete
implementation-entry pin, material member ID and CDS feature ID. The checker
resolves all source fields from the original document; selection is an untrusted
cross-reference, not an alternative source of expected product or recipient.

`expression_contract` is `{identity, body}`. Its identity has kind `model` and a
SHA-256 of the complete canonical body; no self-containing fingerprint is used.
The closed body contains:

| Field | Exact meaning |
| --- | --- |
| `schema_version` | The versioned contract-body schema above. |
| `operation`, `realization` | Complete DefinitionRefs, resolved to original source semantic-definition bodies. They must equal the selected catalog entry's corresponding refs. |
| `product` | Complete reference-kind product identity. All its fields must equal the product identity reconstructed from source and the structural authority's product identity. |
| `recipient` | The full original selected chassis body, not just its name or species. Exact equality is required; v0.1 does not infer subtype or cell-state compatibility. |
| `deployment` | Complete original environment and delivery bodies, including all their definition refs, resolved definitions and declared assumptions. Exact matching makes every applicability premise visible. |
| `localization` | A complete pinned semantic definition, resolved through the original bundle; its ID equals the source localization parameter. The supplied contract asserts this destination conditionally. |
| `material` | Exact structural-authority fingerprint, member ID and CDS feature ID. This pins the full architecture, original construction roots and transforms, regions, chemistry and product; a CDS-only identity is insufficient. |
| `translation` | Explicit `nominal_canonical_parent_bases` interpretation, one or two consecutive terminal stops, and the complete normative model DefinitionRef. This checks nominal correspondence, not modified-base ribosomal behavior. |
| `dependencies`, `evidence` | Complete ordered DefinitionRef inventories matching the selected implementation entry. Every definition body must be present in the original semantic bundle. Evidence declarations are retained as supplied support, not independently validated observations. |
| `claim_scope` | The literal `conditional_encoding_and_localization`; no runtime, functional or empirical claim selector. |

Semantic DefinitionRefs retain the existing policy semantic-digest convention.
Full request/contract/material identities use complete canonical artifact bytes.
The report must name both conventions; it must not mistake a semantic digest
that omits source-map/provenance fields for a full artifact hash.

`structure_authority` is the existing `Policy_mrna_structure` authority, limited
here to one member, one ordinary CDS and one complete expected protein. It
retains original `Payload_template` roots, transforms, exact member order,
UTR/CDS/UTR/poly(A) region identities, translation policy, chemistry and provenance.
Complete source-record locators/digests/reuse terms and assumptions are bound in
`project_context` and must exactly equal the paired project envelope. Original
source bytes remain separately retained in the C2 packet. The source-byte inspector only checks correspondence to declared
digests; it is not material qualification or a biological acceptance token.

The current structural checker already supports the necessary distinction
between sequence and chemistry. It requires canonical A/C/G/U, contiguous
complete regions, ordinary CDS translation and an exact represented terminal
poly(A) tail. Its ordinary-CDS path rejects interpreted modification claims over the CDS.
That old path remains unchanged. The distinct expression structural checker
requires the explicit nominal parent-base model, validates modification positions
and parent identities, and recognizes the stated one/two terminal stops. Its
private token is different from the old structural token. Do not hardcode the candidate lead's chemistry, tail length,
antigen or protein into this generic profile, and do not fill absent chemistry
with an apparently plausible cap or modification declaration.

## 4. Native types, independent checking and outcomes

Use private native types for the trust transitions:

```text
raw JSON
  -> decoded_expression_request              (shape and bounds only)
  -> admitted_expression_source              (fresh source + closed objective)
  -> untrusted Construction_content          (producer proposal)
  -> checked_expression_material option      (fresh independent conjunction)
  -> exact paired export                    (fresh publication checks)
```

The admitted source record contains resolved requirement/role IDs, full product
identity, resolved localization definition, maximum nucleotide count, original
recipient/deployment/catalog values and source paths. It contains no Python
object and no assumption that a stored source report was valid. The checker token
is abstract in the `.mli`; a deserialized report cannot create one.

Fresh checking must perform these steps in order:

1. Bound and decode the complete request and candidate. Verify closed fields,
   full supplied bodies and all original pins before semantic use. Malformed
   records and invalid signatures yield precise path diagnostics.
2. Run the existing `Policy_check` against the original document, then a new
   closed subset admission pass. Resolve the objective's refs and normative
   definition, product, recipient and material constraint independently of the
   producer. Do not route through abstract-attempt operational admission.
3. Reconstruct the selected catalog entry from the original BuildRequest; verify
   its complete entry pin, operation, realization and exact inventory. Check
   every contract/body/product/material/recipient/deployment equality above.
   Unknown or incompatible contracts yield unsupported or failed applicability,
   rather than removing a source requirement.
4. Invoke `Policy_mrna_structure_check.check` on the independently supplied
   structural authority and candidate. This freshly invokes exact original-root
   construction checking and independently checks geometry, translation and
   chemistry. The producer uses `Construction_producer.construct_template`; the
   verifier must not call it or treat its derived intermediates as authority.
5. Require exactly the selected member and CDS, compare the complete translated
   protein to the source-bound product, and compute the complete RNA length
   against `maximum_rna_nt`. Preserve every feature, root and provenance check;
   exact bases alone do not discharge the source binding.
6. Emit a complete obligation ledger: source structural validity, closed source
   support, exact construction, RNA structural completeness, product identity,
   member/CDS correspondence, recipient/deployment applicability, source length
   constraint, and the supplied expression/localization premises. Every original
   generic source obligation is referenced and given a disposition. The generic
   source checker did not prove the new objective.
7. Bound, charge and publish the complete report before returning the private
   checked token. Replay freshly repeats steps 1–7 and compares the complete
   result; it never trusts a saved PASS or a historical token.

### v0.2 disposition contract

Every ledger row has exactly `obligation`, `path`, `status`, `stage` and
`evidence`. `stage` is the reason code. Rows are ordered by ascending obligation
ID and have unique IDs. Preserve the complete fresh original generic source
assessment inside the admission report and preserve its complete assumption
ledger. A row path is a primary original-source locator, not a proof or an
exhaustive list of dependencies.

Let `A` be the complete fresh `source_admission` report, `S` the complete fresh
`structure` report, `C` the complete original
`request.expression_contract.identity`, and `H` the existing canonical JSON
fingerprint. Let `d[i]` be the complete original definition at index `i` in
`document.program.semantics.definitions`. The evidence records below have exactly
the displayed keys and values:

```text
SOURCE = {"source": H(A)}
JOIN = {"source": H(A), "structure": H(S), "contract": C}
DEF(i) = {
  "source": H(A),
  "definition": {
    "$type": "DefinitionRef",
    "id": d[i].id,
    "version": d[i].version,
    "digest": H(semantic_projection(d[i]))
  },
  "body": d[i],
  "contract": C
}
```

The semantic projection is the existing policy definition-digest convention;
`body` retains the entire original definition, including fields omitted by that
projection. Hashes bind the identified bytes, not their physical truth. On a
failed conjunction, evidence must bind fresh child reports from that invocation,
retaining their actual outcomes, rather than a previous successful invocation.
For example, a failed RNA-length bound may retain passing source and structure
children; a failed material child retains its failure.

The following stage abbreviations are only table notation; the wire value is
the full literal in the second column:

| Alias | Exact `stage` |
| --- | --- |
| NA | `closed_static_source_admission` |
| SUPPLIED | `supplied_expression_localization_and_recipient_premises` |
| ENTRY | `complete_supplied_implementation_contract` |
| EXACT | `exact_static_encoding_and_length` |
| NORMATIVE | `closed_normative_static_interpretation` |
| PREMISE | `resolved_original_context_or_component_premise` |
| UNSUPPORTED | `unimplemented_obligation` |

Success in the table means the admitted source's fresh encoding, material and
length conjunction passes. Failure means that this supported conjunction fails
after admission. Malformed or unsupported source and resource failures retain
their existing early diagnostics; they need not produce a completed ledger.

| Obligation | Success `status` | Failed conjunction `status` | `stage` | `path` | `evidence` |
| --- | --- | --- | --- | --- | --- |
| `policy_execution_and_lowering` | `not_applicable` | `not_applicable` | NA | `/document/program` | SOURCE |
| `temporal_and_uncertainty_semantics` | `not_applicable` | `not_applicable` | NA | `/document/program` | SOURCE |
| `safety_and_progress_satisfaction` | `not_applicable` | `not_applicable` | NA | `/document/program` | SOURCE |
| `realizability_and_target_suitability` | `conditional` | `unresolved` | SUPPLIED | `/document/deployment` | JOIN |
| `chassis_capability_and_delivery_suitability` | `conditional` | `unresolved` | SUPPLIED | `/document/deployment` | JOIN |
| `implementation_catalog_applicability` | `conditional` | `unresolved` | SUPPLIED | `/document/implementations` | JOIN |
| `requested_assurance_not_established` | `conditional` | `unresolved` | SUPPLIED | `/document/assurance` | JOIN |
| `implementation_applicability:<entry-id>` | `conditional` | `unresolved` | ENTRY | `/document/implementations/implementations/0` | JOIN |
| `requirement_satisfaction:<objective-id>` | `discharged` | `unresolved` | EXACT | `/document/program/declarations/<j>` | JOIN |
| `expression_material_correspondence` | `conditional` | `unresolved` | SUPPLIED | `/document` | JOIN |
| `semantic_definition:<definition-id>` for a complete recognized normative definition | `discharged` | `discharged` | NORMATIVE | `/document/program/semantics/definitions/<i>` | DEF(i) |
| `semantic_definition:<definition-id>` for another complete reachable supplied definition | `conditional` | `conditional` | PREMISE | `/document/program/semantics/definitions/<i>` | DEF(i) |
| Additional unsupported generic obligation (negative report only) | `unresolved` | `unresolved` | UNSUPPORTED | `/document` | `null` |

`j` and `i` are actual zero-based positions in the complete original lists,
without reordering the source. Derive the implementation entry ID from the
original one-entry catalog, not just the selected pin or returned child. Require
its ID, version and canonical content fingerprint to match selection. Reject
duplicate original definition IDs before constructing a set or index map, even
if duplicate bodies are equal. Recognition of a normative descriptor requires
its complete prescribed body, not its ID or position alone. The three recognized
normative definitions are `biocompiler.expression.objective.v1`,
`biocompiler.expression.encode.v1` and
`biocompiler.expression.nominal_translation.v1`; their existing full bodies and
pins remain unchanged.

For the nine-definition artificial control (`D = 9`), the final 19-row success
ledger has three N/A, four discharged and twelve conditional rows. A failed
material/encoding/length conjunction has three N/A, three discharged, six
conditional and seven unresolved rows. These counts supplement full row equality;
they cannot detect a substituted ID, path, stage or dependency on their own.

The first three rows assert checked absence of runtime, temporal and
safety/progress demands. A failed RNA check does not create those demands;
therefore these dispositions remain N/A. Safety/progress uses `/document/program`
because its absence must hold throughout the source, not just requested
assurance. Temporal absence additionally relies on static assurance through
`SOURCE`. Deployment/catalog/assurance paths likewise locate the primary demand;
`JOIN` retains the wider conjunction and original contract premises. The exact
objective is discharged only within this conditional profile. It cannot
discharge requested assurance or the expression/material premise itself.

### Mandatory census and negative diagnostics

The Python reader independently reconstructs the generic mandatory census from
complete originals: seven fixed IDs (the first seven table rows), one original implementation ID,
one original objective ID, and one ID per original semantic definition. If `D`
is the number of unique original definitions, that is `9 + D` mandatory generic
IDs. Accepted source under the documented subset has exactly that census; the
expression layer adds `expression_material_correspondence` once, giving exactly
`10 + D` final rows. Do not use the returned source obligation list as its own
expected authority.

Require `expression_material_correspondence` to be absent from the generic
child before adding it. A set union must not conceal a forged prior occurrence.
Missing mandatory IDs, duplicates, a reserved-ID occurrence in the generic
child, or disagreement between child, admission and final ledger inventories
are malformed report data, even if the final report says `not_accepted`.

An additional genuine generic obligation rejects acceptance and remains visible
as the final table row: `unresolved`, `unimplemented_obligation`, `/document`,
null evidence. The admission inventory must equal the complete child inventory
plus the one reserved expression ID, and the final ledger must equal that
admission inventory. Never intersect away extras, promote them to a supplied
premise, or grant N/A to the four runtime-only obligations
`persistent_encounter_identity_lifetime`,
`state_lifetime_capacity_and_inheritance`,
`effect_authorization_feedback_and_cancellation` and
`arbitration_fairness_and_conflict_resolution`. Those IDs are absent from a
correctly admitted static success census.

An otherwise passing material/objective check can coexist with an unresolved
extra. Ordinary rows then retain their locally justified successful dispositions,
but `all_original_obligations_dispositioned` is false, overall status is
`not_accepted`, and no accepted token or export exists. The arithmetic-clause
probe described under AR-11 exercises this defensive negative path outside the
documented subset; it does not establish supported clause compilation.

Native source checking establishes the semantic origin of generic extras.
Python reconstructs mandatory IDs and checks transport/census consistency; it
does not become a second semantic interpreter. This does not claim that Python
can detect every coherently forged unsupported extra in an already-negative
report. No extra can gain acceptance through that limitation.

The result names `status` (`checked_expression_material` or `not_accepted`),
`claim_scope` (`conditional_encoding_and_localization`), the supplied premise,
and separate `empirical`/`human_use` values (`unassessed`). Malformed, unsupported
source and resource failures retain bounded protocol diagnostics. Source admission
alone still withholds the expression claim. Successful conditional export uses
its own private token and accepted status. Missing a required premise or
failing any supported structural/source equality withholds the token and export.
Empirical unassessment is displayed, not relabeled as a completed obligation.
Conversely, ordinary conditional compilation does not wait for external empirical
review. C2 qualification and C6 release must independently satisfy their own exits.

## 5. Fixed limits and publication route

The existing ceilings are one member/product/ORF, seven source declarations, at most 64 semantic
definitions and 32 dependency/evidence refs combined. All exact definition
resolution and inventory scans are charged. The request is bounded to 4,000,000
canonical bytes, 100,000 values/object keys and depth 64; the original source also
retains `Policy_document`'s 2 MiB/100,000-node/depth-64 limits. Molecular records
retain their existing stricter checks and one-million-residue ceiling.

Fresh checking and publication share a 100,000,000-unit maximum invocation
budget, with a nested structural ceiling of 50,000,000 units. Callers may request
smaller limits only. Compilation separately bounds the untrusted proposal phase
by the same requested maximum; it then starts a fresh checking invocation. The
reported `total_charged_work` belongs to checking and publication, not the prior
proposal phase. This is not a CPU-time measurement or a single combined
producer-plus-checker allowance. Preflight, decoding, original hashing, lookups, reconstruction,
translation, report creation and publication all consume actual work; no cached
acceptance or uncharged serialization is permitted. M1 must charge added source
path/index lookups within those same limits; the correction does not raise them.

Full report/manifest/result publication must fit the existing ordinary protocol
envelope and an explicitly declared operation output budget. Admission of an
input does not guarantee that its duplicated export evidence fits. Preflight the
actual final payload and return bounded incomplete/no export on exhaustion;
do not raise global limits or import the quantitative coupled-wire exception.
The C1 acceptance case must demonstrate headroom, including reopen input, rather
than discover inevitable oversize at release time.

Add the following closed operations and capability profile:

- Core: `compile-policy-expression-material`, using the existing construction
  producer, followed by the same fresh checker.
- Core and Verify: `check-policy-expression-material`,
  `replay-policy-expression-material`, `export-policy-expression-material`.
- Verify has no producer dependency and never repairs/replaces a candidate.

The new manifest contains the complete original request including its budgets, exact
candidate, fresh assessment, source-to-product/recipient/member/CDS links, and
explicit conditional/unassessed claim scopes. Reuse exact FASTA generation and
atomic `program.fasta`/`manifest.json` publication. Introduce
an explicitly new native checked-token formatting entry point: the existing
`Policy_component_material_format.render` accepts only its existing
`checked_material` type and must not be called with a forged substitute. Shared
low-level formatting can be factored while preserving both capability guards.
Extend `ResearchProject` with
an explicit `expression_material` route and typed `.from_expression` entry point; do not
make a finite-machine request masquerade as this route. A fresh Verify invocation
reopens the pair against a separately supplied original project and compares all
exported bytes. The route uses `biocompiler.research_project.v0.2` with `limits: null`.
Existing v0.1 routes and byte representations remain unchanged.

### M1 project and package migration

Reject old or mixed assessment/checker/service identities rather than relabeling
old evidence. Core and Verify must advertise the exact current material profile;
Core's compile operation additionally requires the current producer profile.
A stale capability rejects before invoking the requested operation. A stale or
mixed response rejects even if its request, candidate and hashes are coherent.

A separately retained original expression project remains loadable because its
project/request/source formats are unchanged. Fresh compilation/checking and
export may produce the corrected assessment for the same exact material. Export
to a separate destination and preserve the old project, archive, manifest and
FASTA bytes. Reopening an old archive still performs fresh Verify export against
the retained original project and compares the exact FASTA/manifest pair; its old
manifest must reject after that fresh comparison. An identical FASTA is
insufficient to accept an obsolete assessment. A newly exported package must
reopen under the new identities and preserve the exact original RNA.

The corrected report includes paths and new dispositions/versions. Its bytes,
fingerprint, dependent manifest/archive identity and measured publication work
therefore change, while the original request/candidate/material and successful
FASTA remain unchanged. Do not rewrite historical validation projections,
released assets, reference packs, normative descriptors or independently pinned
expected reference material to make old records appear v0.2-validated.

## 6. Minimal implementation surface and acceptance controls

Implement new `policy_expression_material.ml/.mli` domain types and closed source
admission, the narrowly selected expression-source schema/decoder branch,
`policy_expression_material_check.ml/.mli` independent conjunction, and
`policy_expression_material_service.ml/.mli` with a small producer adapter. Reuse
`Policy_document`, `Policy_check`, pinned identities, `Payload_template`,
`Construction_producer`, `Construction_check`, `Policy_mrna_structure` and
the distinct `Policy_expression_structure_check`. Do not modify finite-machine lowering, quantitative
laws, component graph semantics or the old material private capability.

On the Python side add typed `policy/expression_material.py`, a strict transport
client/result validator, profile-aware static assurance typing/validation, and
explicit researcher-project route handling. Register
only the new operations/capabilities, source inventories, native boundaries and
test wiring required by these files. UI and CLI changes should call this same
path; no second sequence-only generator is needed.

Required positive and negative controls are:

- The independently qualified full-material case, with exact original RNA,
  features, chemistry and product expectations from C2. Until C2 is ready,
  artificial software tests remain explicitly artificial and cannot close C5.
- A meaningful supported source edit: change `maximum_rna_nt` from a supplied
  allowance above actual length to exactly actual length. Both pass with the same
  RNA and a different, freshly checked hard constraint. Reducing it by one fails
  specifically at that requirement. Expected length comes from independent
  original material; unchanged RNA is justified because this edit changes a
  structural bound, not the expression mechanism. C1 must explicitly accept
  this useful design constraint as an allowed edit; it cannot substitute for a
  requested functional edit.
- Changing the source product, recipient chassis, localization or selected
  implementation while retaining the old authority fails the exact affected
  binding. Coherently repinning a different recipient in a candidate/report
  does not change the independent original BuildRequest.
- Adding an antigen-gated rule, stop request, persistence requirement or effect
  lifecycle returns unsupported with the original requirement ID. It cannot
  receive a static encoding PASS.
- `not_applicable` under the old source profile, temporal assurance under the
  new profile, and the new profile passed to an old operational/material route
  reject. Existing quantity/unbounded source controls and their exact bytes stay
  unchanged. New-profile roundtrip retains the actual static source; no hidden
  translation to an old request is permitted.
- Wrong protein, strand/frame, internal stop, missing UTR/terminal information,
  wrong tail/chemistry, inconsistent modification parent bases, altered root or region and wrong member/CDS
  selection fail independently, including fully repinned candidate mutations.
- A forged stored assessment, truncated obligation ledger, substituted original,
  budget exhaustion, publication overflow or tampered FASTA/manifest withholds
  export; a separate Verify invocation freshly rejects the changed pair.

M1 additionally requires independently specified complete success/failure rows,
including stages, original occurrence paths and exact evidence keys. Reordered
source declarations/definitions must yield current indices. Coherently rehashed
omission, insertion, duplicate, status, path and premise mutations must reject;
include the reserved expression ID inserted into the generic child, original
catalog/selection disagreement and duplicate original definition IDs. Negative
extras must remain unresolved without suppressing ordinary diagnostics. Frozen
v0.1 project/package controls must prove the migration and unchanged successful
FASTA above. Expected dispositions must not be derived from the producer's
classification logic. The implemented controls have the scoped local results
recorded below; complete workflow and hosted acceptance remain separate gates.

Local pure typing/roundtrip/transport/source-subset controls provide fast
feedback. Native producer/checker independence, real construction, negative
cases, installed Core-to-Verify publication and cross-platform identity require
the existing coherent hosted, integration and actual-main gates. The original
C3 preparation record asserted none of those hosted results at drafting time;
its later main/published evidence remains separately recorded in the capability
matrix. M1 is implemented in `codex/m1-obligation-dispositions`. Its independent
native regression first rejected the old ledger; the corrected native build and
focused native/SDK controls passed against recorded working-tree contents. See
the [M1 feedback record](architecture-refactoring-roadmap.md#m1-local-feedback-and-pending-gates)
for counts and retained receipt identities. Direct native legacy-package,
mixed-version and CAR workflow probes also passed locally. Hosted
integration/installed validation and fresh actual-main acceptance remain pending.
Local results do not establish
a new published snapshot or close the separate M2 admission gap.

## 7. Source basis for the decision

Relevant current interfaces are
[`model.py`](../src/biocompiler/policy/model.py) (`EffectLifecycle`, `Requirement`,
`BuildRequest`), [`policy_check.ml`](../core/lib/checker/policy_check.ml),
[`policy_admission.ml`](../core/lib/checker/policy_admission.ml),
[`policy_admitted_ir.mli`](../core/lib/domain/policy_admitted_ir.mli),
[`policy_mrna_structure.mli`](../core/lib/domain/policy_mrna_structure.mli),
[`policy_mrna_structure_check.ml`](../core/lib/checker/policy_mrna_structure_check.ml),
[`construction_producer.mli`](../core/lib/compiler/construction_producer.mli), and
[`research_project.py`](../src/biocompiler/policy/research_project.py).
The existing admitted IR retains generic requirements without assigning this
new meaning. The existing mRNA leaf explicitly grants no source, recipient or
complete export authority. The new conjunction addresses that precise gap,
conditional on original supplied contracts, rather than upgrading either leaf's
current claim.
