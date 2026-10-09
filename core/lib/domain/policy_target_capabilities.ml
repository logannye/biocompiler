open Bioc_wire
module R = Policy_realization_request
module M = Policy_component_material_request

let schema_version = "biocompiler.policy_target_capabilities.v0.1"
let str value = Json.String value
let strings values = Json.Array (List.map str values)
let obj fields = Json.Object fields
let bound minimum maximum = obj ["minimum",Json.int minimum;"maximum",Json.int maximum]
let source_shape id observations machines states stores rules transitions effects products slots =
  obj ["id",str id;
    "counts",obj ["executor_roles",bound 1 1;"encounter_declarations",bound 1 1;
      "subjects",bound 1 1;"clocks",bound 1 1;"observations",observations;
      "machines",machines;"states_per_machine",states;"truth_stores",stores;
      "rules",rules;"transitions",transitions;"effects",effects;
      "fixed_text_products",products;"encounter_slots",slots]]
let truth_shape observations = source_shape "exclusive_truth_rules"
  (bound observations observations) (bound 0 0) Json.Null (bound 1 2) (bound 1 2)
  (bound 0 0) (bound 1 1) (bound 1 1) Json.Null
let staged_shape products = source_shape "fixed_staged_machine"
  (bound 1 1) (bound 1 1) (bound 5 5) (bound 0 0) (bound 0 0)
  (bound 7 7) (bound 2 2) (bound products products) (bound 2 2)
let finite_shape = source_shape "bounded_finite_machine"
  (bound 1 1) (bound 1 1) (bound 2 16) (bound 0 0) (bound 0 0)
  (bound 1 32) (bound 1 8) (bound 1 1) (bound 2 2)
let transfer_network_shape = source_shape "bounded_reserved_transfer_network"
  (bound 1 1) (bound 1 1) (bound 4 16) (bound 0 0) (bound 0 0)
  (bound 1 32) (bound 1 1) (bound 1 1) (bound 2 2)
let transfer_pair_shape = source_shape "bounded_conservative_transfer_pair"
  (bound 1 1) (bound 1 1) (bound 4 16) (bound 0 0) (bound 0 0)
  (bound 2 18) (bound 1 1) (bound 1 1) (bound 2 2)
let network_shape = source_shape "bounded_machine_network"
  (bound 2 4) (bound 2 4) (bound 2 16) (bound 0 4) (bound 0 0)
  (bound 1 32) (bound 1 8) (bound 1 1) (bound 2 2)
let common_features = ["three_valued_truth";"independent_supplied_evidence";
  "finite_clock_ticks";"atomic_precommit_snapshot";"encounter_generation_reset";
  "retained_effect_attempt_identity";"fixed_text_product";
  "original_hard_requirement_inventory";"supplied_exact_primitive_configurations"]
let truth_features = ["observed_rising";"encounter_truth_state";"exclusive_arbitration"]
let staged_features = ["finite_machine_state";"observed_rising";
  "correlated_terminal_feedback";"exclusive_arbitration"]
let finite_features = staged_features @ ["observation_updated";"source_derived_machine_shape"]
let network_features = ["finite_machine_state";"observed_rising";"observation_updated";
  "correlated_terminal_feedback";"independent_observation_coherence";
  "single_writer_encounter_truth_state";"explicit_priority_groups";
  "simultaneous_independent_groups";"source_derived_machine_shape"]
let material_features = ["supplied_component_fragments";"exact_component_membership";
  "explicit_input_providers";"explicit_resource_providers";
  "source_derived_resource_demand";"exact_rna_and_manifest"]
let common_limitations = [
  "Feature combinations and source counts are descriptive necessary conditions, not admission.";
  "Exact source, descriptor, domain, model configuration, replication and catalog checks remain required.";
  "Missing supplied models do not establish biological infeasibility or an exhaustive mechanism search.";
  "Hard requirements require complete bounded exploration and nonvacuous independent checking.";
  "No planning result establishes empirical mechanism function, therapeutic benefit or human-use admission.";
  "The planner performs no history exploration, execution, payload emission or export."]
let truth_limitations = [
  "Truth-rule events use observed rising predicates and exclusive arbitration; stores have encounter lifetime.";
  "Exactly one rule initiates the single effect; supplied truth-store configurations and slot counts must match."]
let staged_limitations = [
  "The fixed staged alternative requires two terminal states, exclusive arbitration and no independent truth stores.";
  "Each effect has exactly one initiating transition; events use observed rising or correlated terminal feedback.";
  "Staged source lowering is limited to sixty-four selected primitive nodes."]
let finite_limitations = [
  "Finite-machine realization uses exclusive arbitration, no independent rules or stores, and at most one request per transition.";
  "Each effect has exactly one initiating transition; terminal states have no outgoing transitions."]
let multi_site_limitations = [
  "One finite encounter machine uses exclusive reject-on-conflict arbitration and no separate rules or stores.";
  "Each effect has one to thirty-two ordered initiating sites under one machine arbiter; at most one request is made per transition.";
  "All sites share one attempt bank and capacity while retaining the actual initiating site and authorization guard.";
  "Terminal states have no outgoing transitions; multi-machine request sharing and request coalescing are unsupported."]
let network_limitations = [
  "Network observations have distinct coherence groups; stores have known Boolean initial values and one writer machine.";
  "Complete priority policies define groups; guards and assignments read the precommit snapshot.";
  "Each effect has exactly one initiating transition and terminal feedback returns to that initiating machine.";
  "Channels, messages, effect resource contracts, fairness, preemption and explicit predicate resets are unsupported.";
  "Logical shared-resource protocols remain separate from summed physical provider-capacity obligations."]
let material_limitations = [
  "Selected original components, assembly rules, providers and exact RNA references must be supplied explicitly.";
  "Component/context decoding and model-conditional agreement do not establish physical provider function.";
  "Fresh complete material checking and export remain mandatory after planning."]
let deferred_behavior_stages = ["complete_finite_domain_exploration";
  "independent_implementation_execution";"source_implementation_preservation";
  "whole_domain_hard_requirements";"original_assurance_satisfaction"]
let deferred_material_stages = ["source_derived_context_resource_checking";
  "component_material_correspondence";"fresh_exact_payload_construction";"fresh_export_acceptance"]
type specification = {
  id:string; material:bool; schema:string; profile:string;
  realization_schema_value:string; realization_profile_value:string;
  shapes:Json.t list; features:string list; limitations:string list;
  graph_nodes:int;
}
let make id material (schema,profile) (realization_schema_value,realization_profile_value)
    shapes features limitations graph_nodes =
  {id;material;schema;profile;realization_schema_value;realization_profile_value;
    shapes;features;limitations;graph_nodes}
let legacy = R.schema_version,R.profile
let prerequisite = R.prerequisite_schema_version,R.prerequisite_profile
let two_observation = R.two_observation_schema_version,R.two_observation_profile
let multi_product = R.multi_product_schema_version,R.multi_product_profile
let finite = R.finite_machine_schema_version,R.finite_machine_profile
let network = R.network_schema_version,R.network_profile
let multi_site = R.multi_site_schema_version,R.multi_site_profile
let specifications = [
  make "implementation" false legacy legacy [truth_shape 1;staged_shape 1]
    (truth_features@staged_features) (truth_limitations@staged_limitations) 256;
  make "finite_machine_implementation" false finite finite [finite_shape]
    finite_features finite_limitations 64;
  make "network_implementation" false network network [network_shape]
    network_features network_limitations 64;
  make "component_material" true (M.schema_version,M.profile) legacy
    [truth_shape 1;staged_shape 1] (truth_features@staged_features)
    (truth_limitations@staged_limitations@["Legacy component material uses its two selected component slots and one RNA member."]) 64;
  make "instance_material" true (M.instance_schema_version,M.instance_profile) legacy
    [truth_shape 1;staged_shape 1] (truth_features@staged_features@["named_component_instances"])
    (truth_limitations@staged_limitations@["Named component material constructs one RNA member."]) 64;
  make "prerequisite_material" true (M.prerequisite_schema_version,M.prerequisite_profile) prerequisite
    [truth_shape 1] (truth_features@["named_component_instances";"provider_prerequisite_closure"])
    (truth_limitations@["Prerequisite material uses the truth-rule family and one RNA member."]) 64;
  make "two_observation_material" true (M.two_observation_schema_version,M.two_observation_profile) two_observation
    [truth_shape 2] (truth_features@["named_component_instances";"provider_prerequisite_closure";"independent_observation_coherence"])
    (truth_limitations@["Two-observation material has distinct coherence groups; it performs no frame joining or machine execution."]) 64;
  make "multi_member_material" true (M.multi_member_schema_version,M.multi_member_profile) multi_product
    [staged_shape 2] (staged_features@["named_component_instances";"provider_prerequisite_closure";"two_product_rna_members";"explicit_identity_transport"])
    (staged_limitations@["The two fixed product symbols must be distinct and each has one original effect; two RNA members require explicit recipient and transport authority."]) 64;
  make "grounded_helper_material" true (M.grounded_helper_schema_version,M.grounded_helper_profile) multi_product
    [staged_shape 2] (staged_features@["named_component_instances";"provider_prerequisite_closure";"two_product_rna_members";"explicit_identity_transport";"delivered_helper_bootstrap"])
    (staged_limitations@["The two product RNA members and one delivered helper retain explicit bootstrap, co-delivery and capacity obligations."]) 64;
  make "finite_machine_material" true (M.finite_machine_schema_version,M.finite_machine_profile) finite
    [finite_shape] (finite_features@["named_component_instances";"provider_prerequisite_closure"])
    (finite_limitations@["Finite-machine material constructs one RNA member from selected staged components."]) 64;
  make "quantitative_material" true (M.quantitative_schema_version,M.quantitative_profile) finite
    [finite_shape] (finite_features@["named_component_instances";"provider_prerequisite_closure";"exact_sampled_saturating_reservoir"])
    (finite_limitations@["Quantitative checking additionally requires a selected exact two-to-sixteen-level sampled reservoir contract and its independent finite-machine correspondence.";
      "Continuous kinetics, stochastic uncertainty, approximate refinement and general multiple request-site threshold semantics are unsupported."]) 64;
  make "network_material" true (M.network_schema_version,M.network_profile) network
    [network_shape] (network_features@["named_component_instances";"provider_prerequisite_closure"])
    (network_limitations@["Network material constructs one RNA member from selected staged components."]) 64;
  make "multi_site_implementation" false multi_site multi_site [finite_shape]
    (finite_features@["multiple_effect_request_sites";"shared_attempt_capacity"]) multi_site_limitations 64;
  make "step_quantitative_material" true (M.step_quantitative_schema_version,M.step_quantitative_profile) multi_site
    [finite_shape] (finite_features@["multiple_effect_request_sites";"shared_attempt_capacity";"named_component_instances";
      "provider_prerequisite_closure";"exact_sampled_saturating_step_reservoir"])
    (multi_site_limitations@["Exact positive rise and fall amounts lie on the complete two-to-sixteen-level quantity grid.";
      "Every threshold-crossing request site is independently bound to its selected component boundary and shared attempt bank port.";
      "Continuous kinetics, stochastic uncertainty, approximation and empirical mechanism function remain unassessed."]) 64;
  make "transfer_pair_material" true (M.transfer_pair_schema_version,M.transfer_pair_profile) multi_site
    [transfer_pair_shape] (finite_features@["multiple_effect_request_sites";"shared_attempt_capacity";"named_component_instances";
      "provider_prerequisite_closure";"exact_sampled_conservative_transfer_pair";"complete_cartesian_state_mapping";"sparse_zero_transfer_holds"])
    (multi_site_limitations@["Two distinct compartments share one exact substance, nominal unit and quantity grid with at most sixteen Cartesian states.";
      "True and False transfer in opposite directions from the prestate; zero-transfer transitions are omitted canonically.";
      "The complete joint contract checks donor stock, receiver headroom and conservation within each encounter generation; reset restores both initials.";
      "Separate reservoir realization, continuous kinetics, stochastic uncertainty and empirical mechanism function remain unassessed."]) 64;
  make "transfer_network_material" true (M.transfer_network_schema_version,M.transfer_network_profile) multi_site
    [transfer_network_shape] (finite_features@["multiple_effect_request_sites";"shared_attempt_capacity";"named_component_instances";
      "provider_prerequisite_closure";"exact_sampled_reserved_transfer_network";"complete_cartesian_state_mapping";
      "sparse_zero_transfer_holds";"declared_order_prestate_reservation";"single_atomic_state_owner"])
    (multi_site_limitations@["Two to four distinct reservoirs and one to eight named directed transfers share exact units and a complete Cartesian grid of at most sixteen states.";
      "Enabled transfers reserve donor stock and receiver headroom in declared order from one prestate; incoming stock and released room cannot be reused in the same sample.";
      "One selected atomic state owner commits all reserved transfers; the complete table retains every edge allocation and exact conservation within each encounter generation.";
      "Reset restores every initial amount; nonzero flows with zero net state change still require a source transition. All-zero allocations use implicit holds.";
      "Graph and model ceilings remain conjunctive; a representable quantity grid alone does not establish backend admission.";
      "Distributed molecular coordination, continuous kinetics, stochastic uncertainty and empirical transport remain unassessed."]) 64]
let unique values = List.fold_left (fun result value -> if List.mem value result then result else result@[value]) [] values
let descriptor spec = obj [
  "target",str spec.id;"kind",str (if spec.material then "component_material" else "implementation");
  "request_schema",str spec.schema;"request_profile",str spec.profile;
  "realization_schema",str spec.realization_schema_value;"realization_profile",str spec.realization_profile_value;
  "required_inputs",strings (["document";"definitions";"operating_domain";"implementation_library";"catalog_bindings"]@
    (if spec.material then ["component_library";"composition_rule";"catalog_binding";"input_bindings";"resource_bindings";"context"] else [])@
    (if (spec.id="quantitative_material" || spec.id="step_quantitative_material" || spec.id="transfer_pair_material" || spec.id="transfer_network_material") then ["quantitative"] else []));
  "source_shapes",Json.Array spec.shapes;
  "features",strings (unique (common_features@spec.features@(if spec.material then material_features else [])));
  "limits",obj (["primitive_models",Json.int 64;"implementation_nodes",Json.int spec.graph_nodes;
    "implementation_wires",Json.int 2048;"source_occurrences",Json.int 2048]@
    (if spec.material then ["component_definitions",Json.int 16;"component_instances",Json.int (if spec.id="component_material" then 2 else 8)] else []));
  "limitations",strings (common_limitations@spec.limitations@(if spec.material then material_limitations else [])@
    (if spec.realization_schema_value=R.schema_version then
      ["Legacy realization rejects nonempty catalog dependencies and evidence; provider prerequisite closure is not applicable to this family."] else []));
  "deferred_stages",strings (deferred_behavior_stages@
    (if spec.material then deferred_material_stages else [])@
    (if (spec.id="quantitative_material" || spec.id="step_quantitative_material" || spec.id="transfer_pair_material" || spec.id="transfer_network_material") then ["quantitative_refinement_checking"] else []))]
let target_ids = List.map (fun spec -> spec.id) specifications
let find id = match List.find_opt (fun spec -> String.equal spec.id id) specifications with
  | Some spec -> spec
  | None -> Diagnostic.fail ~path:"/request/target" "policy_target_unknown" "Unknown installed policy planning target."
let catalog = obj ["schema_version",str schema_version;
  "claim_scope",str "Installed profile vocabulary and advisory planning only; no compilation, export or biological acceptance.";
  "targets",Json.Array (List.map descriptor specifications)]
let catalog_fingerprint = Canonical.fingerprint catalog
let target id = descriptor (find id)
let is_material id = (find id).material
let request_schema id = (find id).schema
let request_profile id = (find id).profile
let realization_schema id = (find id).realization_schema_value
let realization_profile id = (find id).realization_profile_value
