# Original controlled-composition authority, request v0.14

This is the normative RC3 wire contract, authored before its request decoder.
The literal artificial fixture is `core/test/data/policy_controlled_request_v014.json`.
The independently authored source is `core/test/data/policy_controlled_source_v01.json`.
All records below are closed: every named field is required, unknown fields,
duplicate keys and alternate scalar types are rejected. Arrays preserve order.
No input is a candidate, checked-material token or replacement digest summary.

## Root and retained originals

Root keys: `schema_version`, `profile`, `source_authority`, `mechanism_model`,
`operating_domain`, `material_authority`, `catalog_binding`, `assembly`, `context`,
`resources`, `budgets`. Schema is
`biocompiler.policy_component_material_request.v0.14`; profile is
`biocompiler.policy_controlled_composition_mrna.v0.1`.

`source_authority` retains the RC1 closed source-authority schema: schema_version,
document, control_contract, project_context. The document is a complete bounded
controlled BuildRequest, including original definitions, complete selected
catalog entry, deployment, assurance, source map and provenance. The control
contract retains RC1 products/controller/readout, actual delays and requested
deadlines. Deadlines must equal the independently admitted source obligations;
actual delays are independent supplied model parameters. Project context keys
are project_id, title, sources, assumptions. Source records are exactly id,
locator, version, sha256, role, reuse_terms; supplied source pins do not
authenticate a publication or establish an empirical premise.

`material_authority` uses the existing complete
`biocompiler.policy_mrna_structure_authority.v0.1` / mRNA-completeness profile,
with exactly two ordered members. Its template retains every original source,
transform, member, requirement, complex, amount and payload-structure declaration.
Each member retains regions (utr5, cds, utr3, poly_a), the complete product body
and identity, translation policy, provenance and full nominal chemistry. No
sequence or missing region is generated. RC3 admits the original graph and
mapping only; reconstruction/translation checking is RC4.
The admitted RC3 subset requires exactly two directly referenced complete RNA
roots and no transforms, complexes, amounts or helper members. Unsupported
construction graphs fail closed; retaining their shape is not admission.
Each root's four contiguous forward regions partition its complete spelling;
both original payload manifests match that region census. Exactly one cytoplasmic
payload role belongs to each member. Output chemistry must equal the original
root chemistry, including provenance, under its explicit coordinate-frame rename.
Cap, both ends, modification inventory and a positive exact represented poly-A
tail must be explicitly declared; tail coordinates equal the poly-A region.
Every molecular provenance declaration is declared and has at least one supplied
pin resolving by id/version/hash to project_context.sources. This is internal
consistency of caller-supplied provenance, not authentication of external bytes,
licensing, experimental fidelity or empirical support.

## Selected model, interfaces and assembly

`mechanism_model` keys: schema_version, identity, body. Schema is
`biocompiler.policy_controlled_activity_model.v0.1`. Identity is a complete
PinnedIdentity of kind model whose content fingerprint binds the exact body.
Body keys: operation, readout, controller, products, components, ports, delays,
initial_activity, clock, assumptions. Operation/readout/controller/products
are full DefinitionRefs resolving against original SemanticDefinitions.
Products are exactly two ordered references. Clock is Ref(Clock). Delays are
the RC1 actual-delay record. Initial activity is background. Assumptions are
nonempty distinct strings present in project_context.assumptions.
Each product SemanticDefinition has exactly three fixed text Parameters named
product_identity, product_version and product_sha256. Their values equal the
complete material product pin, whose id also equals the source product Parameter.
Product content pins bind the full original protein body; labels alone never
supply product correspondence. The admitted translation declaration is ordinary_cds.

Each of exactly two components has id, member_id, product_definition,
localization, model. The last three fields are full DefinitionRefs resolving
against the original document; component body and identity remain in the model
body. Each of exactly five ports has id, direction, signal, scope, reference.
In order they are antigen (input, physical_antigen, encounter_generation,
Ref(Observation)), controller (input, physical_controller, executor,
Ref(Observation)), component-a and component-b (input, component_available,
executor, the respective Ref(Parameter)), and activity (output, activity_band,
executor, Ref(ControlledActivity)). Activity and its timers are executor-owned
and survive encounter end/reset. These are physical model
interfaces, not truth evidence, expression, killing or clinical endpoints.

`catalog_binding` keys: entry, model_identity, component_ids. Entry is the complete
original selected ImplementationBinding, byte-for-byte canonical equal to the
sole source catalog entry. Model identity equals the complete model identity;
component_ids equals the complete ordered component inventory.

`assembly` keys: schema_version, policy, member_order, product_bindings,
helper_members. Schema is biocompiler.policy_controlled_composition_assembly.v0.1;
policy is supplied_template_only; helper_members is empty. Each of exactly two
product bindings has product_parameter, member_id, cds_id, product_definition,
product_identity. The first four match the corresponding control-contract
binding exactly; product_identity is the material member's complete product pin.
Member order is identical across assembly, material and control contract.

## Deployment, resources and limits

`context` keys: schema_version, executor_identity, slot, deployment, co_delivery,
localizations, availability, controller, empirical_assertions. Schema is
biocompiler.policy_controlled_composition_context.v0.1. Deployment is the complete
original source Deployment, canonical equal to that body. Executor identity and
slot are nonempty caller identifiers. Co-delivery keys: mode, members, assumptions;
mode is same_recipient, members equals material order, assumptions is nonempty
and resolves to project assumptions. Each localization has member_id, rna_compartment,
product_compartment, definition; compartments are cytoplasm and cell_surface,
definition is a resolved full DefinitionRef. Availability has exactly two records
with member_id, rna, product, scope; rna/product are domain and scope is executor.
Controller equals the complete RC1 controller binding. Empirical assertions are
bounded records id, claim, status, source_ids; status is unassessed; source_ids
resolve project sources. Admission never promotes these to demonstrated evidence.

`resources` keys: schema_version, max_member_rna_nt, max_total_rna_nt,
controller_records, evidence_records, timer_cells, state_bits. Schema is
biocompiler.policy_controlled_composition_resources.v0.1. Counts are exact positive
integers. RNA limits are at most 1,000,000 per member and 2,000,000 total;
controller_records >= 1, evidence_records >= 2, timer_cells >= 3, state_bits >= 4,
each at most 1,000,000. These are supplied capacities, not empirical availability.
RNA size checks at admission apply exact original root inventory; reconstructed
output size remains a construction check. Resources cannot stand in for explicit
availability factors or co-delivery premises.

`budgets` keys: profile, max_work, max_report_bytes, max_report_nodes. Profile is
biocompiler.policy_controlled_composition_resources.v0.1. Exact positive ceilings
are 1,000,000,000 logical work units, 8,323,072 report bytes, and 249,968 report
nodes. Original JSON preflight ceilings are 4,000,000 bytes, 100,000 nodes and
96 depth. Every decode/hash is charged before traversal. Source/domain tick,
generation, factor/history/prefix and transition limits are separately specified
in the controlled-domain contract. Exhaustion or cancellation never returns an
admission token. The entire factorized domain must enumerate within its limits.

## Admission output

The checker report has exactly schema_version, profile, stage, status, claim_scope,
request_fingerprint, source_fingerprint, domain_fingerprint, material_fingerprint,
authority_inventory, domain_inventory, domain_counters, source_admission, budgets, construction_status,
behavior_status, empirical_status. Schema is
biocompiler.policy_controlled_composition_assessment.v0.1, stage admission,
status admitted, claim_scope supplied_authority_and_complete_finite_domain_only.
Construction/behavior statuses are not_performed and empirical status unassessed.
The source fingerprint binds the whole source_authority.document. All
fingerprints retain the complete original records, including source locations
and project provenance; source_admission is the complete native source report.

Authority inventory is exactly definitions, catalog_entries, model_components,
model_ports, members, products, roots, transforms, source_records,
empirical_assertions (nonnegative counts). Domain counters are exactly prefixes,
transitions, histories, work, all nonnegative integral counts from complete
enumeration. Budgets is the original complete budget object. The service owns
the enclosing response and publication accounting; no material artifact is emitted.
Domain inventory is exactly fixed_input_count, physical_factor_count,
evidence_factor_count, lifecycle_factor_count, equal to their original array
lengths. A single fixed history is never represented as a variable-factor domain.

The fixture's MA/MG products, tiny artificial RNA roots and nominal chemistry
are software inputs only. They are unrelated to the patent acquisition and do
not supply its missing designer RNA adaptations or empirical validation.
