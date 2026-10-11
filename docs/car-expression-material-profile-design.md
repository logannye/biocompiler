# Proposed exact expression-material profile for the CAR MVP

Status: **implemented source candidate; hosted native, installed and release
acceptance pending**. This records the bounded C3 decision for the
[CAR MVP roadmap](car-mvp-and-expansion-roadmap-2026-10-10.md).
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

## 3. Original authority and wire records

Versioned implementation names:

- Request schema: `biocompiler.policy_expression_material_request.v0.1`.
- Profile: `biocompiler.policy_single_expression_mrna.v0.1`.
- Contract-body schema: `biocompiler.policy_expression_contract.v0.1`.
- Assessment schema: `biocompiler.policy_expression_material_assessment.v0.1`.
- Export manifest schema: `biocompiler.policy_expression_mrna_manifest.v0.1`.

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

The generic source obligations require a **closed, complete disposition census**,
not an arbitrary list of exceptions. Under the subset above it is exactly the
following nine fixed/instantiated entries plus one per semantic definition:

| Original obligation | Permitted successful disposition and evidence |
| --- | --- |
| `policy_execution_and_lowering` | `not_applicable` to runtime execution, justified by the closed absence of runtime declarations; link the new static source-to-material derivation separately. |
| `temporal_and_uncertainty_semantics` | `not_applicable`, justified by static assurance and rejection of all temporal/uncertain declarations or requested guarantees. |
| `safety_and_progress_satisfaction` | `not_applicable`, because there are no safety/progress requirements in the admitted source; adding one rejects. |
| `realizability_and_target_suitability` | `conditional`: exact material is independently checked; physical realization and recipient suitability remain the explicitly pinned supplied premises. |
| `chassis_capability_and_delivery_suitability` | `conditional`: exact recipient/deployment/capability correspondence plus the complete supplied applicability premises; no empirical suitability PASS. |
| `implementation_catalog_applicability` | `conditional`: exact selected entry and contract/dependency correspondence, with its unresolved physical premises. |
| `requested_assurance_not_established` | `conditional`: link the new structural objective result and its premises; establish no stronger assurance level. |
| `implementation_applicability:<entry-id>` | `conditional`: link that exact entry, expression contract and material/CDS correspondence. |
| `requirement_satisfaction:<objective-id>` | `discharged` within the explicitly conditional profile: all encoding, localization-contract correspondence and length checks pass under the named premises. |
| `semantic_definition:<definition-id>` | `discharged` only for a recognized normative descriptor; otherwise `conditional`, linked to that complete reachable supplied premise. |

Every disposition contains the original ID, source path, reason code and relevant
checked-clause or premise identities. Preserve the entire original source
assessment as a child report. Require set equality with its independently
reconstructed obligation IDs, reject duplicates, and reject any unexpected ID
instead of defaulting it to a premise. Preserve every original assumption in a
separate complete ledger. In particular, a new checker obligation cannot vanish
because the source still appears superficially static.
The new source profile additionally declares
`expression_material_correspondence`; its conditional disposition must link the
entire fresh conjunction. This is not a claim that the generic v0.1 checker
already discharged it.

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

Implemented ceilings, still requiring hosted acceptance and measured headroom, are one member/product/ORF, seven source declarations, at most 64 semantic
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
acceptance or uncharged serialization is permitted.

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

Local pure typing/roundtrip/transport/source-subset controls provide fast
feedback. Native producer/checker independence, real construction, negative
cases, installed Core-to-Verify publication and cross-platform identity require
the existing coherent hosted, integration and actual-main gates. The current implementation claims none of those hosted results yet.

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
