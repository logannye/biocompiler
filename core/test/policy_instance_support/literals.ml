open Bioc_wire
include Bioc_policy_component_test_support.Literals

(* Independent original declarations: two copies of one stateful edge fragment
   flank a control fragment. Their complete material definitions differ. The
   source, primitive model library and finite domain are unchanged A/B inputs.
   No producer, source evaluator or completed candidate supplies these literals. *)
let assembly_profile = "biocompiler.policy_instance_component_assembly.v0.1"
let feature_id instance local = Canonical.encode (arr [str instance;str local])
let edge_fragment models = fragment "fixture.reusable.edge"
  [node models "edge" "exclusion.primitive.edge"] []
  [boundary "truth" "input" "truth_value" "edge" "in";
   boundary "events" "output" "event_batch" "edge" "events"] [] []
  [endpoint "edge" "events"]

let control_nodes state_reading =
  ["evidence";"not";"true";"false";"product";"select_gate";"exclude_gate";
   "arbiter";"select_commit";"exclude_commit";"selected";"excluded";"attempt"] @
  if state_reading then ["selected_not";"select_guard"] else []
let control_wires state_reading =
  let guard = if state_reading then "select_guard","out" else "evidence","value" in
  let value1 = if state_reading then "selected","value" else "false","out" in
  [wire "evidence" "value" "not" "in";
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
   wire (fst guard) (snd guard) "attempt" "authorization"] @
  if state_reading then [wire "selected" "value" "selected_not" "in";
    wire "evidence" "value" "select_guard" "in0";
    wire "selected_not" "out" "select_guard" "in1"] else []
let control_exports state_reading =
  List.map (fun (id,port)->endpoint id port)
    (["evidence","value";"evidence","updated";"not","out";"true","out";
      "false","out";"product","out";"select_gate","candidate";"exclude_gate","candidate";
      "arbiter","out0";"arbiter","out1";"select_commit","write0";
      "select_commit","write1";"select_commit","request0";"exclude_commit","write0";
      "exclude_commit","write1";"selected","value";"excluded","value";
      "attempt","events";"attempt","snapshot"] @
     if state_reading then ["selected_not","out";"select_guard","out"] else [])
let control_fragment models state_reading =
  let specifications =
    ["evidence","exclusion.primitive.evidence";"not","exclusion.primitive.not";
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
    [boundary "select_truth" "output" "truth_value" "evidence" "value";
     boundary "exclude_truth" "output" "truth_value" "not" "out";
     boundary "select_event" "input" "event_batch" "select_gate" "on";
     boundary "exclude_event" "input" "event_batch" "exclude_gate" "on"]
    [external_slot "condition" "evidence" "evidence" "samples";
     external_slot "feedback" "feedback" "attempt" "feedback"]
    [obj ["id",str "exclusive_selection";"arbiter",str "arbiter";
      "commits",arr [str "select_commit";str "exclude_commit"]]]
    (control_exports state_reading)

let local_root id sequence features coding tail =
  let frame=id^".frame" in
  let raw=root id sequence false in
  let chemistry=chemistry frame false in
  let chemistry=if tail then chemistry
    |> put ["terminal_tail";"placement"] (str "represented_terminal")
    |> put ["terminal_tail";"length";"exact"] (Json.int 4)
    |> put ["terminal_tail";"path"] (path frame 2 6) else chemistry in
  raw |> put ["molecule";"coding_status"] (str (if coding then "coding" else "noncoding"))
    |> put ["molecule";"features"] (arr features)
    |> put ["molecule";"chemistry"] chemistry
let leader_root = local_root "edge_leader" "CC"
  [feature "edge_leader.frame" "utr5" "five_prime_utr" 0 2 Json.Null] false false
let coding_root = local_root "control_cds" "AUGGCUUAA"
  [feature "control_cds.frame" "cds" "coding_sequence" 0 9 (Json.int 0)] true false
let trailer_root = local_root "edge_trailer" "GGAAAA"
  [feature "edge_trailer.frame" "poly_a" "poly_a_tail" 2 6 Json.Null;
   feature "edge_trailer.frame" "utr3" "three_prime_utr" 0 2 Json.Null] false true

let edge_targets = triple "edge" @ [target "boundary_port" "truth";
  target "boundary_port" "events";indexed "semantic_export" 0;obj ["kind",str "slot_layout"]]
let edge_component models leading =
  let id,local_root,material_site = if leading then
      "fixture.instance.edge.leading",leader_root,site "edge_leader" "utr5" 0 2
    else "fixture.instance.edge.trailing",trailer_root,site "edge_trailer" "utr3" 0 2 in
  let carriers=List.map(fun target->obj ["target",target;"sites",arr [material_site]]) edge_targets in
  component id (edge_fragment models) local_root carriers []
    [capacity "edge_history" "node" "edge" "edge_history_cells" "per_encounter_slot" 1]
let control_targets state_reading =
  List.concat_map triple (control_nodes state_reading) @
  List.init (if state_reading then 21 else 18) (indexed "local_wire") @
  [target "external_slot" "condition";target "external_slot" "feedback";
   target "boundary_port" "select_truth";target "boundary_port" "exclude_truth";
   target "boundary_port" "select_event";target "boundary_port" "exclude_event";
   target "atomic_group" "exclusive_selection"] @
  List.init (if state_reading then 21 else 19) (indexed "semantic_export") @
  [obj ["kind",str "slot_layout"]]
let control_component models state_reading =
  let carriers=List.map(fun target->obj ["target",target;
    "sites",arr [site "control_cds" "cds" 0 9]]) (control_targets state_reading) in
  component (if state_reading then "fixture.instance.control.state" else "fixture.instance.control.exclusion")
    (control_fragment models state_reading) coding_root carriers
    [obj ["node",str "product";"symbol",str "fixture.product.alpha";
      "root",str "control_cds";"cds_feature",str "cds";"expected",expected_product]]
    [input "condition_input" "condition";input "feedback_input" "feedback";
     capacity "condition_rows" "external_slot" "condition" "input_rows_per_tick" "per_encounter_slot" 1;
     capacity "feedback_rows" "external_slot" "feedback" "input_rows_per_tick" "per_executor" 1;
     capacity "samples" "node" "evidence" "evidence_records" "per_encounter_slot" 1;
     capacity "freshness_timer" "node" "evidence" "timer_cells" "per_encounter_slot" 1;
     capacity "selected_memory" "node" "selected" "truth_cells" "per_encounter_slot" 1;
     capacity "excluded_memory" "node" "excluded" "truth_cells" "per_encounter_slot" 1;
     capacity "active" "node" "attempt" "active_attempt_records" "per_encounter_slot" 8;
     capacity "retained" "node" "attempt" "retained_correlation_records" "per_executor" 1;
     capacity "attempt_timers" "node" "attempt" "timer_cells" "per_encounter_slot" 8]
let components models state_reading =
  [edge_component models true;control_component models state_reading;edge_component models false]

let output_chemistry frame = chemistry frame true
  |> put ["terminal_tail";"path"] (path frame 13 17)
let output_features frame =
  [feature frame (feature_id "select_edge" "utr5") "five_prime_utr" 0 2 Json.Null;
   feature frame (feature_id "control" "cds") "coding_sequence" 2 11 (Json.int 0);
   feature frame (feature_id "exclude_edge" "utr3") "three_prime_utr" 11 13 Json.Null;
   feature frame (feature_id "exclude_edge" "poly_a") "poly_a_tail" 13 17 Json.Null]
let material_authority state_reading =
  let p=M.Provenance.of_json provenance in
  let facets=["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"] in
  let dispositions source copied=List.map(fun facet->
    let component=T.Component.of_string facet and carry=List.mem facet copied in
    T.Chemistry_disposition.make ~source_id:source ~component
      ~decision:(if carry then T.Chemistry_disposition.Mapped_copy else T.Chemistry_disposition.Not_carried)
      ~destination_components:(if carry then [component] else []) ~provenance:p) facets in
  let chemistry_transition=T.Chemistry.make ~mode:T.Chemistry.Explicit_output
    ~output:(Some(H.of_json(output_chemistry "join.frame")))
    ~dispositions:(dispositions "edge_leader" ["cap";"start_end";"modification_inventory"] @
      dispositions "control_cds" ["modification_inventory"] @
      dispositions "edge_trailer" ["finish_end";"terminal_tail";"modification_inventory"]) ~provenance:p in
  let feature_transition=T.Feature.make ~dispositions:(List.map2(fun (source,id) feature->
    T.Feature_disposition.make ~source_id:source ~feature_id:id ~decision:T.Feature_disposition.Exact
      ~outputs:[N.Feature.of_json feature] ~provenance:p)
      ["edge_leader","utr5";"control_cds","cds";"edge_trailer","utr3";"edge_trailer","poly_a"]
      (output_features "join.frame")) ~added:[] ~provenance:p in
  let whole id=CT.Selection.make(CT.Value_ref.make ~kind:CT.Value_ref.Root ~id) in
  let step=CT.Transform_step.make ~id:"join" ~operation:(CT.Operation.make
    (CT.Operation.Concatenate(List.map whole ["edge_leader";"control_cds";"edge_trailer"])))
    ~ports:[CT.Product_port.make ~id:"joined" ~space_id:"join.frame" ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition ~feature_transition] ~assumptions:[] ~provenance:p in
  let output=CT.Output_member.make ~id:"payload" ~value:(CT.Value_ref.make ~kind:CT.Value_ref.Product ~id:"joined")
    ~space_id:"payload.frame" ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Coding ~provenance:p in
  let requirement=CT.Member_requirement.make ~id:"payload" ~category:CT.Member_requirement.Payload
    ~subject:(CT.Member_requirement.Materialized "payload")
    ~roles:[CT.Role.make ~id:"payload.role" ~role:"payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"] in
  let regions=[feature_id "select_edge" "utr5","five_prime_utr";feature_id "control" "cds","coding_sequence";
    feature_id "exclude_edge" "utr3","three_prime_utr";feature_id "exclude_edge" "poly_a","poly_a_tail"] in
  let structure=PS.make ~member_id:"payload" ~form:PS.Delivered_rna ~topology:G.Linear
    ~regions:(List.map(fun(feature_id,kind)->PS.Region.make ~feature_id ~kind)regions) ~provenance:p in
  let template=PT.make ~id:(if state_reading then "fixture.instance.B" else "fixture.instance.A")
    ~sources:(List.map CT.Root_source.of_json [leader_root;coding_root;trailer_root])
    ~steps:[step] ~output_members:[output] ~requirements:[requirement] ~payload_structures:[structure] () in
  obj ["schema_version",str "biocompiler.policy_mrna_structure_authority.v0.1";
    "profile",str "biocompiler.policy_mrna_completeness.v0.1";"template",PT.to_json template;
    "member_order",arr [str "payload"];"members",arr [obj ["id",str "payload";
      "regions",obj ["utr5",str(feature_id "select_edge" "utr5");"cds",str(feature_id "control" "cds");
        "utr3",str(feature_id "exclude_edge" "utr3");"poly_a",str(feature_id "exclude_edge" "poly_a")];
      "product",expected_product;"chemistry",output_chemistry "payload.frame"]]]

let instance_of_node = function "select_edge"->"select_edge","edge" | "exclude_edge"->"exclude_edge","edge" | id->"control",id
let global_nodes state_reading =
  List.map(fun id->let slot,node=instance_of_node id in nr slot node)
    (["evidence";"select_edge";"not";"exclude_edge";"true";"false";"product";
      "select_gate";"exclude_gate";"arbiter";"select_commit";"exclude_commit";
      "selected";"excluded";"attempt"] @ if state_reading then ["selected_not";"select_guard"] else [])
let local index=obj ["kind",str "local";"slot",str "control";"index",Json.int index]
let global_wires state_reading =
  [link_wire "select_truth";local 0;link_wire "exclude_truth";link_wire "select_event";link_wire "exclude_event"] @
  List.init (if state_reading then 20 else 17) (fun index->local(index+1))
let global_exports state_reading =
  List.map(fun row->let slot,node=instance_of_node(Json.string(get "node" row)) in
    er slot node (Json.string(get "port" row)))
    (Bioc_policy_component_test_support.Literals.global_exports state_reading)
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
    "input_order",arr [obj ["slot",str "control";"external_slot",str "condition";"id",str "condition"];
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

let expected_sequence = "CCAUGGCUUAAGGAAAA"
let expected_coverage = ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48]
let expected_requirements = ["request_progress";"initiation_progress";"exclusive_selection"]

let expected_molecule () =
  let frame="payload.frame" and p=M.Provenance.of_json provenance in
  N.make ~id:"payload" ~form:N.Delivered_rna ~space:(G.Space.of_json(space frame 17))
    ~sequence:expected_sequence ~sequence_extent:H.Complete ~coding_status:N.Coding
    ~assembly:[N.Assembly_origin.make ~id:"payload.origin" ~destination:(G.Path.of_json(path frame 0 17))
      ~source_space:(G.Space.of_json(space "join.frame" 17))
      ~source_path:(G.Path.of_json(path "join.frame" 0 17)) ~provenance:p]
    ~features:(List.map N.Feature.of_json(output_features frame))
    ~chemistry:(H.of_json(output_chemistry frame)) ~provenance:p

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
    link "select_truth" "leader_cds" 2 "control" "select_truth" "evidence" "value" "select_edge" "truth" "edge" "in";
    link "exclude_truth" "cds_trailer" 11 "control" "exclude_truth" "not" "out" "exclude_edge" "truth" "edge" "in";
    link "select_event" "leader_cds" 2 "select_edge" "events" "edge" "events" "control" "select_event" "select_gate" "on";
    link "exclude_event" "cds_trailer" 11 "exclude_edge" "events" "edge" "events" "control" "exclude_event" "exclude_gate" "on"] in
  require(List.length carriers=(if state_reading then 109 else 98) && List.length links=4)
    "Independent instance projection inventory changed";
  arr carriers,arr links
