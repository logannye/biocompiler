open Bioc_wire
open Literals
module R = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context
module X1 = Bioc_domain.Policy_material_context
module R1 = Bioc_domain.Policy_material_request
module RR = Bioc_domain.Policy_realization_request
module F = Bioc_domain.Policy_operating_domain
module RC = Bioc_domain.Policy_material_contract

(* The expected source-neutral ordered union is independently spelled from the
   shared original graph literals. No candidate or decoder output supplies it. *)
let local_endpoint slot raw = er slot (Json.string (get "node" raw)) (Json.string (get "port" raw))
let union_literal models state_reading rule_raw =
  let decision_raw=decision models state_reading and driver_raw=driver models in
  let local slot=if slot="decision" then decision_raw else driver_raw in
  let nodes=List.map (fun reference ->
    let slot=Json.string (get "slot" reference) in
    let node=List.find (fun row -> get "id" row=get "node" reference) (items "nodes" (local slot)) in
    add "model" (get "model" node) reference) (global_nodes state_reading) in
  let internal=List.map (fun row -> obj ["producer",local_endpoint "decision" (get "producer" row);
    "consumer",local_endpoint "decision" (get "consumer" row)]) (items "wires" decision_raw) in
  let cross id producer consumer=obj ["id",str id;"producer",producer;"consumer",consumer] in
  let cross_links=[cross "product" (er "driver" "product" "out") (er "decision" "select_commit" "product0");
    cross "request" (er "decision" "select_commit" "request0") (er "driver" "attempt" "request");
    cross "authorization" (er "decision" (if state_reading then "select_guard" else "evidence")
      (if state_reading then "out" else "value")) (er "driver" "attempt" "authorization")] in
  let wires=List.map (fun reference -> if get "kind" reference=str "local" then
    List.nth internal (int_of_string (Canonical.encode (get "index" reference))) else
    let row=List.find (fun row -> get "id" row=get "id" reference) cross_links in
    obj ["producer",get "producer" row;"consumer",get "consumer" row]) (global_wires state_reading) in
  obj ["schema_version",str "biocompiler.policy_component_ordered_union.v0.1";
    "primitive_profile",str "biocompiler.policy_truth_primitives.v0.1";
    "observable_profile",str "biocompiler.policy_truth_observables.v0.1";
    "phase_profile",str "biocompiler.policy_primitive_execution.v0.1";
    "transport_profile",str "biocompiler.policy_identity_transport.v0.1";
    "slot_layout",obj ["id",str "encounters";"slots",Json.int 2];"nodes",arr nodes;"wires",arr wires;
    "inputs",arr [obj ["id",str "condition";"kind",str "evidence";"consumer",er "decision" "evidence" "samples"];
      obj ["id",str "feedback";"kind",str "feedback";"consumer",er "driver" "attempt" "feedback"]];
    "atomic_groups",arr [obj ["slot",str "decision";"id",str "exclusive_selection";
      "arbiter",nr "decision" "arbiter";"commits",arr [nr "decision" "select_commit";nr "decision" "exclude_commit"]]];
    "semantic_exports",arr (global_exports state_reading);"links",at ["body";"links"] rule_raw]
let owner_node slot node=obj ["kind",str "node";"slot",str slot;"node",str node]
let owner_input id=obj ["kind",str "input";"id",str id]
let owner_layout=obj ["kind",str "layout"]
(* Complete local prerequisite order, then the three global layout demands.
   Quantities belong to independent provider/domain checking, not this census. *)
let resource_specs = [
  owner_input "condition","input_rows_per_tick","per_encounter_slot","condition.input_rows_per_tick.per_encounter_slot";
  owner_node "decision" "evidence","evidence_records","per_encounter_slot","local.evidence.evidence_records.per_encounter_slot";
  owner_node "decision" "evidence","timer_cells","per_encounter_slot","local.evidence.timer_cells.per_encounter_slot";
  owner_node "decision" "select_edge","edge_history_cells","per_encounter_slot","local.select_edge.edge_history_cells.per_encounter_slot";
  owner_node "decision" "exclude_edge","edge_history_cells","per_encounter_slot","local.exclude_edge.edge_history_cells.per_encounter_slot";
  owner_node "decision" "selected","truth_cells","per_encounter_slot","shared.truth";
  owner_node "decision" "excluded","truth_cells","per_encounter_slot","shared.truth";
  owner_input "feedback","input_rows_per_tick","per_executor","feedback.input_rows_per_tick.per_executor";
  owner_node "driver" "attempt","active_attempt_records","per_encounter_slot","local.attempt.active_attempt_records.per_encounter_slot";
  owner_node "driver" "attempt","retained_correlation_records","per_executor","local.attempt.retained_correlation_records.per_executor";
  owner_node "driver" "attempt","timer_cells","per_encounter_slot","local.attempt.timer_cells.per_encounter_slot";
  owner_layout,"generation_counters","per_encounter_slot","layout.generation_counters.per_encounter_slot";
  owner_layout,"timer_cells","per_executor","layout.timer_cells.per_executor";
  owner_layout,"control_event_records","per_executor","layout.control_event_records.per_executor"]
let provider_for kind providers=List.find (fun row -> at ["body";"kind"] row=str kind) providers
let context_literal fixture state_reading rule_raw union =
  let old=get "context" (get "request" fixture) in
  let original=get "implementation_request" (get "request" fixture) in
  let record_layout=obj ["profile",str "biocompiler.policy_component_complete_records.v0.1";
    "record_shapes",at ["record_layout";"record_shapes"] old;
    "rule",get "identity" rule_raw;"union_digest",str (Canonical.fingerprint union);
    "domain_digest",str (Canonical.fingerprint (get "operating_domain" original));
    "slots",Json.int 2;"generations",Json.int 2;"attempts",Json.int 2;
    "horizon_ticks",Json.int 6;"maximum_tick",Json.int 8;
    "ordered_reason_slots",Json.int 1;"ordered_cause_slots",Json.int 238;"identifier_bytes",Json.int 512] in
  let layout_digest=Canonical.fingerprint record_layout in
  let providers=List.map (fun provider -> provider |> edit ["body";"capacities"] (fun rows -> arr (List.map
    (replace "record_layout_digest" (str layout_digest)) (Json.array rows))) |> repin) (items "providers" old) in
  old |> replace "schema_version" (str "biocompiler.policy_component_context.v0.1")
    |> replace "profile" (str "biocompiler.policy_component_mrna.v0.1")
    |> replace "record_layout" record_layout |> replace "providers" (arr providers)
    |> put ["placement";"template_id"] (str (if state_reading then "fixture.join.B" else "fixture.join.A"))
    |> put ["delivery_group";"max_total_bases"] (Json.int (if state_reading then 18 else 17))
let request_literal fixture state_reading =
  let old=get "request" fixture and models=original_library fixture in
  let d=decision_component models state_reading and driver=driver_component models in
  let component_library=library [d;driver] in
  let composition_rule=rule state_reading d driver in
  let union=union_literal models state_reading composition_rule in
  let context=context_literal fixture state_reading composition_rule union in
  let providers=items "providers" context in
  let provider kind=at ["body";"definition"] (provider_for kind providers) in
  let original_bridge=get "catalog_binding" old in
  let catalog_binding=obj (List.map (fun key -> key,get key original_bridge)
    ["entry_id";"entry_version";"entry_digest";"operation";"realization"] @ [
    "components",at ["body";"components"] composition_rule;"rule",get "identity" composition_rule]) in
  let input_bindings=arr [obj ["input",str "condition";"source",str "condition";"provider",provider "interface";"channel",str "condition"];
    obj ["input",str "feedback";"source",str "response";"provider",provider "interface";"channel",str "feedback"]] in
  let resource_bindings=arr (List.map (fun (owner,unit,scope,capacity) -> obj ["owner",owner;"unit",str unit;
    "scope",str scope;"provider",provider "chassis";"capacity",str capacity]) resource_specs) in
  obj ["schema_version",str "biocompiler.policy_component_material_request.v0.1";
    "profile",str "biocompiler.policy_component_mrna.v0.1";
    "implementation_request",get "implementation_request" old;"component_library",component_library;
    "composition_rule",composition_rule;"catalog_binding",catalog_binding;"input_bindings",input_bindings;
    "resource_bindings",resource_bindings;"context",context;
    "budgets",replace "profile" (str "biocompiler.policy_component_material_resources.v0.1") (get "budgets" old)],union
let refresh_provider_pins raw = edit ["providers"] (fun rows -> arr (List.map repin (Json.array rows))) raw
let refresh_layout_pins raw =
  let digest=Canonical.fingerprint (get "record_layout" raw) in
  raw |> edit ["providers"] (fun rows -> arr (List.map (fun row -> row
    |> edit ["body";"capacities"] (fun capacities -> arr (List.map
      (replace "record_layout_digest" (str digest)) (Json.array capacities))) |> repin) (Json.array rows)))
