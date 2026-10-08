open Bioc_wire
include Bioc_policy_instance_test_support.Literals

(* Original declarations only. No producer, executable interpretation or closure
   checker supplies these expectations. The existing instance material and full
   finite-domain literals remain untouched. *)
let realization_schema = "biocompiler.policy_realization_request.v0.2"
let realization_profile = "biocompiler.policy_prerequisite_realization_inputs.v0.1"
let material_schema = "biocompiler.policy_component_material_request.v0.3"
let material_profile = "biocompiler.policy_instance_prerequisite_mrna.v0.1"
let closure_schema = "biocompiler.policy_provider_prerequisite_closure.v0.1"
let definition_id = "fixture.prerequisite_environment"
let environment_definition = obj ["$type",str "SemanticDefinition";
  "id",str definition_id;"version",str "1";"category",str "environment";
  "meaning",str "Supplied exact finite environment prerequisite; no new source behavior or empirical evidence.";
  "parameters",arr [];"result",Json.Null;"clauses",arr [];"assumptions",arr [];
  "executor_kind",Json.Null;"subject_kind",Json.Null]
let definition_reference definition = obj ["$type",str "DefinitionRef";
  "id",get "id" definition;"version",get "version" definition;
  "digest",str(Bioc_domain.Policy_document.document_digest definition)]
let environment_reference = definition_reference environment_definition

let expected_obligations = List.map str [
  "arbitration_fairness_and_conflict_resolution";
  "chassis_capability_and_delivery_suitability";
  "effect_authorization_feedback_and_cancellation";
  "implementation_applicability:exclusion.response.primitives.resolved_chassis";
  "implementation_catalog_applicability";"policy_execution_and_lowering";
  "realizability_and_target_suitability";"requested_assurance_not_established";
  "requirement_satisfaction:exclusive_selection";"requirement_satisfaction:initiation_progress";
  "requirement_satisfaction:request_progress";"safety_and_progress_satisfaction";
  "semantic_definition:exclusion.chassis";"semantic_definition:exclusion.delivery";
  "semantic_definition:exclusion.effect";"semantic_definition:exclusion.encounter";
  "semantic_definition:exclusion.environment";"semantic_definition:exclusion.interface";
  "semantic_definition:exclusion.lifecycle";"semantic_definition:exclusion.observation";
  "semantic_definition:fixture.prerequisite_environment";
  "semantic_definition:fixture.realization.primitives";
  "state_lifetime_capacity_and_inheritance";"temporal_and_uncertainty_semantics"]
let expected_provider_ids = ["exclusion.chassis";"exclusion.environment";
  "exclusion.interface";"exclusion.delivery";definition_id]
let expected_instance_names = ["select_edge";"control";"exclude_edge"]

let phase label=Printf.eprintf "prerequisite witness: %s\n%!" label
let provider_definition_id provider=at ["body";"definition";"id"] provider
let modify_provider id transform request = edit ["context";"providers"] (fun rows->
  arr(List.map(fun provider->if provider_definition_id provider=str id then transform provider else provider)
    (Json.array rows))) request
let repin_provider id transform request = modify_provider id (fun provider->
  provider |> edit ["body"] transform |> repin) request
