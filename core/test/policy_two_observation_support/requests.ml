open Bioc_wire
module Prior = Bioc_policy_prerequisite_test_support.Requests
include Bioc_policy_prerequisite_test_support.Requests
open Literals

let local_endpoint slot raw=er slot (Json.string(get "node" raw)) (Json.string(get "port" raw))
let union_literal models state_reading rule_raw =
  let control=control_fragment models state_reading and edge=edge_fragment models in
  let local slot=if slot="control" then control else edge in
  let nodes=List.map(fun reference->
    let slot=Json.string(get "slot" reference) in
    let node=List.find(fun row->get "id" row=get "node" reference)(items "nodes"(local slot)) in
    add "model" (get "model" node) reference)(global_nodes state_reading) in
  let internal=List.map(fun row->obj ["producer",local_endpoint "control"(get "producer" row);
    "consumer",local_endpoint "control"(get "consumer" row)])(control_wires state_reading) in
  let cross id producer consumer=id,obj ["producer",producer;"consumer",consumer] in
  let cross_links=[
    cross "select_truth" (er "control" "all" "out") (er "select_edge" "edge" "in");
    cross "exclude_truth" (er "control" "not" "out") (er "exclude_edge" "edge" "in");
    cross "select_event" (er "select_edge" "edge" "events") (er "control" "select_gate" "on");
    cross "exclude_event" (er "exclude_edge" "edge" "events") (er "control" "exclude_gate" "on")] in
  let wires=List.map(fun reference->if get "kind" reference=str "local" then
      List.nth internal (Z.to_int(Json.integer(get "index" reference)))
    else List.assoc(Json.string(get "id" reference))cross_links)(global_wires state_reading) in
  obj ["schema_version",str "biocompiler.policy_instance_ordered_union.v0.1";
    "primitive_profile",str "biocompiler.policy_truth_primitives.v0.1";
    "observable_profile",str "biocompiler.policy_truth_observables.v0.1";
    "phase_profile",str "biocompiler.policy_primitive_execution.v0.1";
    "transport_profile",str "biocompiler.policy_identity_transport.v0.1";
    "slot_layout",obj ["id",str "encounters";"slots",Json.int 2];"nodes",arr nodes;"wires",arr wires;
    "inputs",arr [obj ["id",str "condition_a";"kind",str "evidence";"consumer",er "control" "evidence" "samples"];
      obj ["id",str "condition_b";"kind",str "evidence";"consumer",er "control" "evidence_b" "samples"];
      obj ["id",str "feedback";"kind",str "feedback";"consumer",er "control" "attempt" "feedback"]];
    "atomic_groups",arr [obj ["slot",str "control";"id",str "exclusive_selection";
      "arbiter",nr "control" "arbiter";"commits",arr [nr "control" "select_commit";nr "control" "exclude_commit"]]];
    "semantic_exports",arr(global_exports state_reading);"links",at ["body";"links"] rule_raw]
let owner_node slot node=obj ["kind",str "node";"slot",str slot;"node",str node]
let owner_input id=obj ["kind",str "input";"id",str id]
let owner_layout=obj ["kind",str "layout"]
let resource_specs = [
  owner_node "select_edge" "edge","edge_history_cells","per_encounter_slot","local.select_edge.edge_history_cells.per_encounter_slot";
  owner_input "condition_a","input_rows_per_tick","per_encounter_slot","condition_a.input_rows_per_tick.per_encounter_slot";
  owner_input "condition_b","input_rows_per_tick","per_encounter_slot","condition_b.input_rows_per_tick.per_encounter_slot";
  owner_input "feedback","input_rows_per_tick","per_executor","feedback.input_rows_per_tick.per_executor";
  owner_node "control" "evidence","evidence_records","per_encounter_slot","local.evidence.evidence_records.per_encounter_slot";
  owner_node "control" "evidence","timer_cells","per_encounter_slot","local.evidence.timer_cells.per_encounter_slot";
  owner_node "control" "evidence_b","evidence_records","per_encounter_slot","local.evidence_b.evidence_records.per_encounter_slot";
  owner_node "control" "evidence_b","timer_cells","per_encounter_slot","local.evidence_b.timer_cells.per_encounter_slot";
  owner_node "control" "selected","truth_cells","per_encounter_slot","shared.truth";
  owner_node "control" "excluded","truth_cells","per_encounter_slot","shared.truth";
  owner_node "control" "attempt","active_attempt_records","per_encounter_slot","local.attempt.active_attempt_records.per_encounter_slot";
  owner_node "control" "attempt","retained_correlation_records","per_executor","local.attempt.retained_correlation_records.per_executor";
  owner_node "control" "attempt","timer_cells","per_encounter_slot","local.attempt.timer_cells.per_encounter_slot";
  owner_node "exclude_edge" "edge","edge_history_cells","per_encounter_slot","local.exclude_edge.edge_history_cells.per_encounter_slot";
  owner_layout,"generation_counters","per_encounter_slot","layout.generation_counters.per_encounter_slot";
  owner_layout,"timer_cells","per_executor","layout.timer_cells.per_executor";
  owner_layout,"control_event_records","per_executor","layout.control_event_records.per_executor"]
let provider_for kind providers=List.find(fun row->at ["body";"kind"] row=str kind)providers
let context_literal fixture state_reading rule_raw union =
  let old=get "context"(get "request" fixture) in
  let original=get "implementation_request"(get "request" fixture) in
  let record_layout=obj ["profile",str "biocompiler.policy_component_complete_records.v0.1";
    "record_shapes",at ["record_layout";"record_shapes"] old;
    "rule",get "identity" rule_raw;"union_digest",str(Canonical.fingerprint union);
    "domain_digest",str(Canonical.fingerprint(get "operating_domain" original));
    "slots",Json.int 2;"generations",Json.int 2;"attempts",Json.int 2;
    "horizon_ticks",Json.int 6;"maximum_tick",Json.int 9;
    "ordered_reason_slots",Json.int 2;"ordered_cause_slots",Json.int 238;"identifier_bytes",Json.int 512] in
  let layout_digest=Canonical.fingerprint record_layout in
  let providers=List.map(fun provider->provider |> edit ["body";"capacities"] (fun rows->arr(List.map
    (replace "record_layout_digest"(str layout_digest))(Json.array rows))) |> repin)(items "providers" old) in
  old |> replace "schema_version"(str "biocompiler.policy_component_context.v0.1")
    |> replace "profile"(str material_profile)
    |> replace "record_layout" record_layout |> replace "providers"(arr providers)
    |> put ["placement";"template_id"] (str(if state_reading then "fixture.instance.B" else "fixture.instance.A"))
    |> put ["delivery_group";"max_total_bases"] (Json.int 17)

let quantities = [1;1;1;1;3;1;3;1;1;1;8;2;8;1;1;1;34]
let observation_row slot observation tick observed_tick status value = obj [
  "slot",str slot;"observation",str observation;"available_tick",Json.int tick;
  "observed_tick",Json.int observed_tick;"status",str status;"value",value]
let fixed_prefix = List.concat_map(fun tick->List.concat_map(fun slot->
  List.map(fun observation->observation_row slot observation tick tick "valid" (Json.Bool(tick=1)))
    ["condition_a";"condition_b"])["e1";"e2"])[0;1]
let observation_factor observation = obj ["slots",arr [str "e1"];"observation",str observation;
  "ticks",arr [Json.int 6];"alphabet",str "known_truth_and_evidence_status.v1";
  "age_ticks",arr [Json.int 0];"max_rows_per_slot_tick",Json.int 1]
let original_domain domain = domain |> replace "fixed_observations"(arr fixed_prefix)
  |> replace "observation_factors"(arr(List.map observation_factor ["condition_a";"condition_b"]))
  |> replace "feedback_factors"(arr [])
let observation_expression raw id = raw |> put ["ref";"id"](str id)
let rec source_expression = function
  |Json.Object fields as raw when List.assoc_opt "$type" fields=Some(str "Expr") &&
      List.assoc_opt "op" fields=Some(str "observe") ->
      require(at ["ref";"id"]raw=str "condition") "Unexpected original observation expression";
      raw |> replace "op"(str "all") |> replace "ref" Json.Null |> replace "scope" Json.Null
        |> replace "args"(arr [observation_expression raw "condition_a";
          observation_expression raw "condition_b"])
  |Json.Object fields->obj(List.map(fun(key,value)->key,source_expression value)fields)
  |Json.Array values->arr(List.map source_expression values)
  |value->value
let source_program program =
  let declarations=List.concat_map(fun declaration->
    if get "$type" declaration=str "Observation" then
      [declaration |> replace "id"(str "condition_a") |> replace "coherence"(str "frame_a");
       declaration |> replace "id"(str "condition_b") |> replace "coherence"(str "frame_b")
         |> put ["freshness";"amount"](str "3")]
    else [source_expression declaration])(items "declarations" program) in
  let source_map=List.mapi(fun index declaration->obj ["$type",str "SourceSpan";
    "declaration_id",get "id" declaration;"file",str "policy_two_observation_source_literal.py";
    "line",Json.int(index+1);"column",Json.int 0;"pattern",Json.Null])declarations in
  program |> replace "declarations"(arr declarations) |> replace "source_map"(arr source_map)
let supplied_models library state_reading =
  let models=items "models" library in
  let evidence=List.find(fun model->at ["identity";"id"]model=str "exclusion.primitive.evidence")models in
  let model id primitive configuration =
    let body=get "body" evidence |> replace "primitive"(str primitive)
      |> replace "configuration" configuration in
    evidence |> replace "body" body |> replace "identity"(pin "model" id(Canonical.fingerprint body))
      |> replace "configuration_digest"(str(Canonical.fingerprint configuration)) in
  models @ [model "two_observation.primitive.evidence_b" "evidence_bank"(obj ["freshness_ticks",Json.int 3])] @
  if state_reading then [] else
    [model "two_observation.primitive.all2" "truth_all"(obj ["arity",Json.int 2])]
let authored_fixture fixture state_reading =
  let old=get "request" fixture in
  let domain=original_domain(at ["implementation_request";"operating_domain"]old) in
  let models=supplied_models(at ["implementation_request";"implementation_library"]old)state_reading in
  let providers=List.map(fun provider->
    let body=get "body" provider in
    let body=match Json.string(get "kind" body) with
      |"environment"->replace "grammar" domain body
      |"interface"->let channels=items "channels" body in
          let evidence=List.find(fun row->get "id" row=str "condition")channels in
          let feedback=List.find(fun row->get "id" row=str "feedback")channels in
          replace "channels"(arr [evidence |> replace "id"(str "condition_a") |> replace "source"(str "condition_a");
            evidence |> replace "id"(str "condition_b") |> replace "source"(str "condition_b");feedback])body
      |_->body in
    provider |> replace "body" body |> repin)(at ["context";"providers"]old |> Json.array) in
  let request=old |> edit ["implementation_request";"document";"program"] source_program
    |> put ["implementation_request";"operating_domain"]domain
    |> put ["implementation_request";"implementation_library";"models"](arr models)
    |> put ["implementation_request";"catalog_bindings";"0";"models"](arr(List.map(get "identity")models))
    |> put ["context";"providers"](arr providers) in
  replace "request" request fixture
let source_models request = at ["implementation_request";"implementation_library"]request
let supplied_capacities context =
  let availability=at ["availability"](get "body"(provider_for "chassis"(items "providers" context))) in
  let layout=str(Canonical.fingerprint(get "record_layout" context)) in
  let unique=List.fold_left(fun acc ((_,unit,scope,id),quantity)->
    match List.assoc_opt id acc with
    |Some (_,_,n)->(id,(unit,scope,quantity+n))::List.remove_assoc id acc
    |None->acc@[id,(unit,scope,quantity)])[] (List.combine resource_specs quantities) in
  arr(List.map(fun(id,(unit,scope,quantity))->obj ["id",str id;"unit",str unit;"scope",str scope;
    "quantity",Json.int quantity;"pool_id",str("executor.pool."^id);"record_layout_digest",layout;
    "slots",arr(if scope="per_encounter_slot"then List.map str ["e1";"e2"]else []);
    "availability",availability])unique)
let request_literal fixture state_reading =
  let authored=authored_fixture fixture state_reading in
  let old,_=Prior.request_literal authored state_reading in
  let models=source_models old in
  let composition_rule=rule models state_reading in
  let union=union_literal models state_reading composition_rule in
  let context=context_literal(replace "request" old authored)state_reading composition_rule union in
  let capacities=supplied_capacities context in
  let context=context |> edit ["providers"] (fun rows->arr(List.map(fun provider->
    if at ["body";"kind"]provider=str "chassis" then
      provider |> put ["body";"capacities"]capacities |> repin else provider)(Json.array rows))) in
  let providers=items "providers" context in
  let provider kind=at ["body";"definition"](provider_for kind providers) in
  let bindings=arr(List.map(fun(input,source)->obj ["input",str input;"source",str source;
    "provider",provider "interface";"channel",str input])
    ["condition_a","condition_a";"condition_b","condition_b";"feedback","response"]) in
  let resources=arr(List.map(fun(owner,unit,scope,capacity)->obj ["owner",owner;"unit",str unit;
    "scope",str scope;"provider",provider "chassis";"capacity",str capacity])resource_specs) in
  let request=old |> replace "schema_version"(str material_schema) |> replace "profile"(str material_profile)
    |> put ["implementation_request";"schema_version"](str realization_schema)
    |> put ["implementation_request";"profile"](str realization_profile)
    |> replace "component_library"(library(components models state_reading))
    |> replace "composition_rule"composition_rule
    |> put ["catalog_binding";"components"](at ["body";"components"]composition_rule)
    |> put ["catalog_binding";"rule"](get "identity" composition_rule)
    |> replace "input_bindings"bindings |> replace "resource_bindings"resources |> replace "context"context in
  request,union

let expected_input_allocations request =
  let provider=original_reference request "exclusion.interface" in
  let available=obj ["onset_min",str "0";"onset_max",str "0";"duration_min",str "6";"duration_max",str "6"] in
  arr(List.map(fun(input,source,kind)->obj ["input",str input;"source",str source;
    "provider",provider;"channel",str input;"kind",str kind;"observer",str "executor";
    "subject",str "encounter/target";"available",available])
    ["condition_a","condition_a","observation";"condition_b","condition_b","observation";"feedback","response","feedback"])
let expected_resource_allocations request =
  let provider=original_reference request "exclusion.chassis" in
  arr(List.map2(fun(owner,unit,scope,capacity)quantity->obj [
    "demand",obj ["owner",owner;"unit",str unit;"scope",str scope;"quantity",Json.int quantity];
    "provider",provider;"capacity",str capacity;"pool",str("executor.pool."^capacity);
    "reserved",Json.int quantity])resource_specs quantities)
let expected_closure request = Prior.expected_closure request
  |> replace "profile"(str material_profile)
  |> replace "input_allocations"(expected_input_allocations request)
  |> replace "resource_allocations"(expected_resource_allocations request)
