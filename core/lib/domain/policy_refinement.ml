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
let schema_version = "biocompiler.policy_refinement_evidence.v0.1"
let stage_name = function
  | Source_document -> "source_document" | Operational_behavior -> "operational_behavior"
  | Implementation_graph -> "implementation_graph" | Construction_content -> "construction_content"
  | Deployment_context -> "deployment_context"
let relation_name = function
  | Exact_source_occurrence -> "exact_source_occurrence" | Source_graph_binding -> "source_graph_binding"
  | Bounded_observable_correspondence -> "bounded_observable_correspondence"
  | Original_hard_requirements -> "original_hard_requirements"
  | Supplied_component_material_correspondence -> "supplied_component_material_correspondence"
  | Conditional_deployment_context -> "conditional_deployment_context"
  | Complete_original_obligations -> "complete_original_obligations"
  | Exact_source_graph_correspondence -> "exact_source_graph_correspondence"
  | Bounded_source_observable_correspondence -> "bounded_source_observable_correspondence"
  | Conditional_source_material_correspondence -> "conditional_source_material_correspondence"
let premise_name = function
  | Original_source -> "original_source" | Semantic_definitions -> "semantic_definitions"
  | Operating_domain -> "operating_domain" | Implementation_catalog -> "implementation_catalog"
  | Implementation_models -> "implementation_models" | Checker_limits -> "checker_limits"
  | Component_library -> "component_library" | Composition_rule -> "composition_rule"
  | Material_authority -> "material_authority" | Deployment_context_contract -> "deployment_context"
  | Material_request -> "material_request" | Source_admission -> "source_admission"
  | Implementation_binding -> "implementation_binding" | Bounded_preservation -> "bounded_preservation"
  | Component_assembly -> "component_assembly" | Mrna_structure -> "mrna_structure"
  | Component_context -> "component_context" | Complete_material_check -> "complete_material_check"
let rule_name = function
  | Checked_admission -> "checked_admission" | Checked_binding -> "checked_binding"
  | Checked_preservation -> "checked_preservation" | Checked_assembly -> "checked_assembly"
  | Checked_context -> "checked_context" | Checked_material -> "checked_material"
  | Conjunction -> "conjunction" | Source_graph_chain -> "source_graph_chain"
  | Source_behavior_chain -> "source_behavior_chain" | Source_material_chain -> "source_material_chain"
let stages = function
  | Exact_source_occurrence -> Source_document,Operational_behavior
  | Source_graph_binding | Bounded_observable_correspondence | Original_hard_requirements ->
    Operational_behavior,Implementation_graph
  | Supplied_component_material_correspondence -> Implementation_graph,Construction_content
  | Conditional_deployment_context -> Construction_content,Deployment_context
  | Complete_original_obligations | Conditional_source_material_correspondence ->
    Source_document,Construction_content
  | Exact_source_graph_correspondence | Bounded_source_observable_correspondence ->
    Source_document,Implementation_graph
let endpoint_to_json (value:endpoint) = Json.Object [
  "stage",Json.String(stage_name value.stage);"fingerprint",Json.String value.fingerprint]
let scope_to_json (value:scope) =
  let optional = function None->Json.Null|Some value->Json.String value in
  Json.Object ["implementation_request_fingerprint",Json.String value.implementation_request_fingerprint;
    "operating_domain_fingerprint",Json.String value.operating_domain_fingerprint;
    "limits_fingerprint",optional value.limits_fingerprint;
    "material_request_fingerprint",optional value.material_request_fingerprint]
let claim_to_json (value:claim) = Json.Object [
  "relation",Json.String(relation_name value.relation);
  "source",endpoint_to_json value.source;"target",endpoint_to_json value.target;
  "scope",scope_to_json value.scope]
let premise_to_json (value:premise) = Json.Object [
  "kind",Json.String(premise_name value.kind);"fingerprint",Json.String value.fingerprint]
