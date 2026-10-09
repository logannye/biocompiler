(** Closed vocabulary for named, conditional refinement evidence.
    These values describe claims; only checker-owned capabilities establish them. *)
open Bioc_wire
type stage = Source_document | Operational_behavior | Implementation_graph
  | Construction_content | Deployment_context
type relation = Exact_source_occurrence | Source_graph_binding
  | Bounded_observable_correspondence | Original_hard_requirements
  | Supplied_component_material_correspondence | Conditional_deployment_context
  | Complete_original_obligations | Exact_source_graph_correspondence
  | Bounded_source_observable_correspondence | Conditional_source_material_correspondence
type premise_kind = Original_source | Semantic_definitions | Operating_domain
  | Implementation_catalog | Implementation_models | Checker_limits
  | Component_library | Composition_rule | Material_authority | Deployment_context_contract
  | Material_request | Source_admission | Implementation_binding | Bounded_preservation
  | Component_assembly | Mrna_structure | Component_context | Complete_material_check
type rule = Checked_admission | Checked_binding | Checked_preservation | Checked_assembly
  | Checked_context | Checked_material | Conjunction
  | Source_graph_chain | Source_behavior_chain | Source_material_chain
type endpoint = {stage:stage; fingerprint:string}
type scope = {
  implementation_request_fingerprint:string;
  operating_domain_fingerprint:string;
  limits_fingerprint:string option;
  material_request_fingerprint:string option;
}
type claim = {relation:relation; source:endpoint; target:endpoint; scope:scope}
type premise = {kind:premise_kind; fingerprint:string}
val schema_version : string
val stage_name : stage -> string
val relation_name : relation -> string
val premise_name : premise_kind -> string
val rule_name : rule -> string
val stages : relation -> stage * stage
val endpoint_to_json : endpoint -> Json.t
val scope_to_json : scope -> Json.t
val claim_to_json : claim -> Json.t
val premise_to_json : premise -> Json.t
