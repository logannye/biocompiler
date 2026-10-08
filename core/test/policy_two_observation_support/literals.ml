open Bioc_wire
include Bioc_policy_prerequisite_test_support.Literals

(* Independent original two-observation declarations. Graphs, carrier rows and
   the finite-domain oracle are authored here; no producer or evaluator is used. *)
let realization_schema = "biocompiler.policy_realization_request.v0.3"
let realization_profile = "biocompiler.policy_two_observation_prerequisite_inputs.v0.1"
let material_schema = "biocompiler.policy_component_material_request.v0.4"
let material_profile = "biocompiler.policy_instance_two_observation_prerequisite_mrna.v0.1"
let phase label=Printf.eprintf "two-observation witness: %s\n%!" label
let expected_coverage = ["histories",36;"transitions",42;"prefixes_started",43;"matched_prefixes",43]

let control_nodes state_reading =
  ["evidence";"evidence_b";"all";"not";"true";"false";"product";"select_gate";"exclude_gate";
   "arbiter";"select_commit";"exclude_commit";"selected";"excluded";"attempt"] @
  if state_reading then ["selected_not";"select_guard"] else []
let control_wires state_reading =
  let guard = if state_reading then "select_guard","out" else "all","out" in
  let value1 = if state_reading then "selected","value" else "false","out" in
  [wire "all" "out" "not" "in";
   wire (fst guard) (snd guard) "select_gate" "guard";
   wire "not" "out" "exclude_gate" "guard";
   wire "select_gate" "candidate" "arbiter" "in0";
   wire "arbiter" "out0" "select_commit" "grant";
   wire "true" "out" "select_commit" "value0";
   wire "select_commit" "write0" "selected" "write0";
   wire (fst value1) (snd value1) "select_commit" "value1";
   wire "select_commit" "write1" "excluded" "write0";
   wire "exclude_gate" "candidate" "arbiter" "in1";
   wire "arbiter" "out1" "exclude_commit" "grant";
   wire "false" "out" "exclude_commit" "value0";
   wire "exclude_commit" "write0" "selected" "write1";
   wire "true" "out" "exclude_commit" "value1";
   wire "exclude_commit" "write1" "excluded" "write1";
   wire "product" "out" "select_commit" "product0";
   wire "select_commit" "request0" "attempt" "request";
   wire (fst guard) (snd guard) "attempt" "authorization";
   wire "evidence" "value" "all" "in0";wire "evidence_b" "value" "all" "in1"] @
  if state_reading then [wire "selected" "value" "selected_not" "in";
    wire "all" "out" "select_guard" "in0";
    wire "selected_not" "out" "select_guard" "in1"] else []
let control_exports state_reading =
  List.map (fun (id,port)->endpoint id port)
    (["evidence","value";"evidence","updated";"evidence_b","value";"evidence_b","updated";"all","out";"not","out";"true","out";
      "false","out";"product","out";"select_gate","candidate";"exclude_gate","candidate";
      "arbiter","out0";"arbiter","out1";"select_commit","write0";
      "select_commit","write1";"select_commit","request0";"exclude_commit","write0";
      "exclude_commit","write1";"selected","value";"excluded","value";
      "attempt","events";"attempt","snapshot"] @
     if state_reading then ["selected_not","out";"select_guard","out"] else [])
let control_fragment models state_reading =
  let specifications =
    ["evidence","exclusion.primitive.evidence";
     "evidence_b","two_observation.primitive.evidence_b";
     "all",(if state_reading then "state.primitive.all2" else "two_observation.primitive.all2");"not","exclusion.primitive.not";
     "true","exclusion.primitive.true";"false","exclusion.primitive.false";
     "product","exclusion.primitive.product";"select_gate","exclusion.primitive.gate";
     "exclude_gate","exclusion.primitive.gate";"arbiter","exclusion.primitive.arbiter";
     "select_commit","exclusion.primitive.select_commit";
     "exclude_commit","exclusion.primitive.exclude_commit";
     "selected","exclusion.primitive.register";"excluded","exclusion.primitive.register";
     "attempt","exclusion.primitive.attempt"] @
    if state_reading then ["selected_not","exclusion.primitive.not";"select_guard","state.primitive.all2"] else [] in
  fragment (if state_reading then "fixture.control.state" else "fixture.control.exclusion")
    (List.map (fun (id,model_id)->node models id model_id) specifications)
    (control_wires state_reading)
    [boundary "select_truth" "output" "truth_value" "all" "out";
     boundary "exclude_truth" "output" "truth_value" "not" "out";
     boundary "select_event" "input" "event_batch" "select_gate" "on";
     boundary "exclude_event" "input" "event_batch" "exclude_gate" "on"]
    [external_slot "condition_a" "evidence" "evidence" "samples";
     external_slot "condition_b" "evidence" "evidence_b" "samples";
     external_slot "feedback" "feedback" "attempt" "feedback"]
    [obj ["id",str "exclusive_selection";"arbiter",str "arbiter";
      "commits",arr [str "select_commit";str "exclude_commit"]]]
    (control_exports state_reading)

let control_targets state_reading =
  List.concat_map triple (control_nodes state_reading) @
  List.init (if state_reading then 23 else 20) (indexed "local_wire") @
  [target "external_slot" "condition_a";target "external_slot" "condition_b";target "external_slot" "feedback";
   target "boundary_port" "select_truth";target "boundary_port" "exclude_truth";
   target "boundary_port" "select_event";target "boundary_port" "exclude_event";
   target "atomic_group" "exclusive_selection"] @
  List.init (if state_reading then 24 else 22) (indexed "semantic_export") @
  [obj ["kind",str "slot_layout"]]
let control_component models state_reading =
  let carriers=List.map(fun target->obj ["target",target;
    "sites",arr [site "control_cds" "cds" 0 9]]) (control_targets state_reading) in
  component (if state_reading then "fixture.instance.control.state" else "fixture.instance.control.exclusion")
    (control_fragment models state_reading) coding_root carriers
    [obj ["node",str "product";"symbol",str "fixture.product.alpha";
      "root",str "control_cds";"cds_feature",str "cds";"expected",expected_product]]
    [input "condition_a_input" "condition_a";input "condition_b_input" "condition_b";input "feedback_input" "feedback";
     capacity "condition_a_rows" "external_slot" "condition_a" "input_rows_per_tick" "per_encounter_slot" 1;
     capacity "condition_b_rows" "external_slot" "condition_b" "input_rows_per_tick" "per_encounter_slot" 1;
     capacity "feedback_rows" "external_slot" "feedback" "input_rows_per_tick" "per_executor" 1;
     capacity "samples" "node" "evidence" "evidence_records" "per_encounter_slot" 1;
     capacity "freshness_timer" "node" "evidence" "timer_cells" "per_encounter_slot" 1;
     capacity "samples_b" "node" "evidence_b" "evidence_records" "per_encounter_slot" 1;
     capacity "freshness_timer_b" "node" "evidence_b" "timer_cells" "per_encounter_slot" 1;
     capacity "selected_memory" "node" "selected" "truth_cells" "per_encounter_slot" 1;
     capacity "excluded_memory" "node" "excluded" "truth_cells" "per_encounter_slot" 1;
     capacity "active" "node" "attempt" "active_attempt_records" "per_encounter_slot" 8;
     capacity "retained" "node" "attempt" "retained_correlation_records" "per_executor" 1;
     capacity "attempt_timers" "node" "attempt" "timer_cells" "per_encounter_slot" 8]
let components models state_reading =
  [edge_component models true;control_component models state_reading;edge_component models false]

let instance_of_node = function "select_edge"->"select_edge","edge" | "exclude_edge"->"exclude_edge","edge" | id->"control",id
let global_nodes state_reading =
  List.map(fun id->let slot,node=instance_of_node id in nr slot node)
    (["evidence";"evidence_b";"all";"select_edge";"not";"exclude_edge";"true";"false";"product";
      "select_gate";"exclude_gate";"arbiter";"select_commit";"exclude_commit";
      "selected";"excluded";"attempt"] @ if state_reading then ["selected_not";"select_guard"] else [])
let local index=obj ["kind",str "local";"slot",str "control";"index",Json.int index]
let global_wires state_reading =
  [link_wire "select_truth";local 0;link_wire "exclude_truth";link_wire "select_event";link_wire "exclude_event"] @
  List.init (if state_reading then 22 else 19) (fun index->local(index+1))
let global_exports state_reading =
  List.map(fun row->let slot,node=instance_of_node(Json.string(get "node" row)) in
    er slot node (Json.string(get "port" row)))
    (let prior=Bioc_policy_component_test_support.Literals.global_exports state_reading in
      List.concat_map(fun row->if get "node" row=str "evidence" && get "port" row=str "updated"
        then [row;endpoint "evidence_b" "value";endpoint "evidence_b" "updated";endpoint "all" "out"] else [row])prior)
let rule models state_reading =
  let selected=components models state_reading in
  let link id source source_boundary destination destination_boundary signal_type = obj ["id",str id;
    "producer",br source source_boundary;"consumer",br destination destination_boundary;
    "signal_type",str signal_type;"scope",str "same_encounter_slot"] in
  let join id left right offset=obj ["id",str id;"step",str "join";"port",str "joined";
    "left",str left;"right",str right;"offset",Json.int offset] in
  let body=obj ["primitive_profile",str "biocompiler.policy_truth_primitives.v0.1";
    "observable_profile",str "biocompiler.policy_truth_observables.v0.1";
    "phase_profile",str "biocompiler.policy_primitive_execution.v0.1";
    "transport_profile",str "biocompiler.policy_identity_transport.v0.1";
    "slot_layout",obj ["id",str "encounters";"slots",Json.int 2];
    "components",arr(List.map2(fun slot component->obj ["slot",str slot;"component",get "identity" component])
      ["select_edge";"control";"exclude_edge"] selected);
    "links",arr [link "select_truth" "control" "select_truth" "select_edge" "truth" "truth_value";
      link "exclude_truth" "control" "exclude_truth" "exclude_edge" "truth" "truth_value";
      link "select_event" "select_edge" "events" "control" "select_event" "event_batch";
      link "exclude_event" "exclude_edge" "events" "control" "exclude_event" "event_batch"];
    "node_order",arr(global_nodes state_reading);"wire_order",arr(global_wires state_reading);
    "input_order",arr [obj ["slot",str "control";"external_slot",str "condition_a";"id",str "condition_a"];
      obj ["slot",str "control";"external_slot",str "condition_b";"id",str "condition_b"];
      obj ["slot",str "control";"external_slot",str "feedback";"id",str "feedback"]];
    "group_order",arr [obj ["slot",str "control";"group",str "exclusive_selection"]];
    "export_order",arr(global_exports state_reading);
    "root_bindings",arr(List.map2(fun slot source->obj ["slot",str slot;"source",str source])
      ["select_edge";"control";"exclude_edge"] ["edge_leader";"control_cds";"edge_trailer"]);
    "joins",arr [join "leader_cds" "select_edge" "control" 2;join "cds_trailer" "control" "exclude_edge" 11];
    "link_carriers",arr(List.map(fun(id,join)->obj ["link",str id;"producer_site",Json.int 0;
      "consumer_site",Json.int 0;"joins",arr [str join]])
      ["select_truth","leader_cds";"exclude_truth","cds_trailer";
       "select_event","leader_cds";"exclude_event","cds_trailer"]);
    "material_authority",material_authority state_reading] in
  obj ["schema_version",str "biocompiler.policy_component_assembly_rule.v0.2";
    "profile",str assembly_profile;
    "identity",pin "model" (if state_reading then "fixture.instance.rule.B" else "fixture.instance.rule.A") (Canonical.fingerprint body);
    "body",body]

let expected_projections state_reading models =
  let selected=components models state_reading in
  let slots=["select_edge";"control";"exclude_edge"] in
  let definitions=List.combine slots selected in
  let component slot=get "body"(List.assoc slot definitions) in
  let source=function "select_edge"->"edge_leader"|"control"->"control_cds"|_->"edge_trailer" in
  let projected slot site =
    let local=Json.string(get "feature" site) in
    let first,last=match slot,local with
      | "select_edge","utr5"->0,2 | "control","cds"->2,11
      | "exclude_edge","utr3"->11,13 | "exclude_edge","poly_a"->13,17
      | _->failwith "Undeclared projection in instance literal" in
    obj ["slot",str slot;"root",get "root" site;"source",str(source slot);
      "feature",str local;"final_feature",str(feature_id slot local);
      "local_path",get "path" site;"member",str "payload";"path",path "payload.frame" first last] in
  let carriers=List.concat_map(fun slot->List.map(fun row->obj ["slot",str slot;"target",get "target" row;
    "sites",arr(List.map(projected slot)(items "sites" row))])(items "carriers"(component slot)))slots in
  let boundary_site slot id=
    let carrier=List.find(fun row->get "target" row=target "boundary_port" id)(items "carriers"(component slot)) in
    projected slot(List.hd(items "sites" carrier)) in
  let link id join offset producer_slot producer_boundary producer_node producer_port consumer_slot consumer_boundary consumer_node consumer_port=
    obj ["link",str id;"joins",arr [str join];"offsets",arr [Json.int offset];
      "producer_endpoint",er producer_slot producer_node producer_port;
      "consumer_endpoint",er consumer_slot consumer_node consumer_port;
      "producer",boundary_site producer_slot producer_boundary;"consumer",boundary_site consumer_slot consumer_boundary] in
  let links=[
    link "select_truth" "leader_cds" 2 "control" "select_truth" "all" "out" "select_edge" "truth" "edge" "in";
    link "exclude_truth" "cds_trailer" 11 "control" "exclude_truth" "not" "out" "exclude_edge" "truth" "edge" "in";
    link "select_event" "leader_cds" 2 "select_edge" "events" "edge" "events" "control" "select_event" "select_gate" "on";
    link "exclude_event" "cds_trailer" 11 "exclude_edge" "events" "edge" "events" "control" "exclude_event" "exclude_gate" "on"] in
  require(List.length carriers=(if state_reading then 121 else 110) && List.length links=4)
    "Independent instance projection inventory changed";
  arr carriers,arr links
