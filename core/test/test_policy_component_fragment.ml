open Bioc_wire
module F = Bioc_domain.Policy_component_fragment
module I = Bioc_domain.Policy_implementation

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let items key value = Json.array (get key value)
let replace key replacement value = obj (List.map (fun (name, item) ->
  name, (if key = name then replacement else item)) (Json.object_fields value))
let change index transform values = List.mapi (fun i value -> if index = i then transform value else value) values
let change_item key index transform value = replace key (arr (change index transform (items key value))) value
let remove key value = obj (List.filter (fun (name, _) -> name <> key) (Json.object_fields value))
let add key item value = obj ((key, item) :: Json.object_fields value)
let rehash_model value =
  let body = get "body" value in
  value |> replace "configuration_digest" (str (Canonical.fingerprint (get "configuration" body)))
    |> replace "identity" (replace "content_fingerprint" (str (Canonical.fingerprint body)) (get "identity" value))
let endpoint node port = obj ["node", str node; "port", str port]
let wire source output target input = obj ["producer", endpoint source output; "consumer", endpoint target input]
let boundary id direction signal_type node port = obj ["id", str id;
  "direction", str direction; "signal_type", str signal_type; "endpoint", endpoint node port]
let external_slot id kind node port = obj ["id", str id; "kind", str kind; "consumer", endpoint node port]
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 4_000_000) "Original fixture exceeds bounded input";
    Json.parse (really_input_string channel size))

(* Only original model declarations are borrowed. Node, wire, interface, group
   and output expectations below are hand-authored, never candidate-derived. *)
let original_library fixture = get "implementation_library" (get "implementation_request" (get "request" fixture))
let model library id = match List.find_opt (fun value ->
    get "id" (get "identity" value) = str id) (items "models" library) with
  | Some value -> value
  | None -> failwith ("Original model absent: " ^ id)
let node library id model_id = obj ["id", str id; "model", model library model_id]
let fragment id nodes wires boundary_ports external_slots atomic_groups semantic_exports = obj [
  "schema_version", str "biocompiler.policy_component_fragment.v0.1";
  "profile", str "biocompiler.policy_exact_fragment.v0.1";
  "primitive_profile", str "biocompiler.policy_truth_primitives.v0.1";
  "observable_profile", str "biocompiler.policy_truth_observables.v0.1";
  "phase_profile", str "biocompiler.policy_primitive_execution.v0.1";
  "id", str id; "version", str "1";
  "slot_layout", obj ["id", str "encounters"; "slots", Json.int 2];
  "nodes", arr nodes; "wires", arr wires; "boundary_ports", arr boundary_ports;
  "external_slots", arr external_slots; "atomic_groups", arr atomic_groups;
  "semantic_exports", arr semantic_exports]

let driver library = fragment "fixture.driver"
  [node library "product" "exclusion.primitive.product";
   node library "attempt" "exclusion.primitive.attempt"] []
  [boundary "product" "output" "product_symbol" "product" "out";
   boundary "request" "input" "effect_request" "attempt" "request";
   boundary "authorization" "input" "truth_value" "attempt" "authorization"]
  [external_slot "feedback" "feedback" "attempt" "feedback"] []
  [endpoint "product" "out"; endpoint "attempt" "events"; endpoint "attempt" "snapshot"]

let decision library state_reading =
  let specifications = [
    "evidence", "exclusion.primitive.evidence";
    "select_edge", "exclusion.primitive.edge"; "not", "exclusion.primitive.not";
    "exclude_edge", "exclusion.primitive.edge";
    "true", "exclusion.primitive.true"; "false", "exclusion.primitive.false";
    "select_gate", "exclusion.primitive.gate"; "exclude_gate", "exclusion.primitive.gate";
    "arbiter", "exclusion.primitive.arbiter";
    "select_commit", "exclusion.primitive.select_commit";
    "exclude_commit", "exclusion.primitive.exclude_commit";
    "selected", "exclusion.primitive.register"; "excluded", "exclusion.primitive.register"] @
    (if state_reading then ["selected_not", "exclusion.primitive.not"; "select_guard", "state.primitive.all2"] else []) in
  let nodes = List.map (fun (id, model_id) -> node library id model_id) specifications in
  let guard_node, guard_port = if state_reading then "select_guard", "out" else "evidence", "value" in
  let false_node, false_port = if state_reading then "selected", "value" else "false", "out" in
  let wires = [
    wire "evidence" "value" "select_edge" "in";
    wire "evidence" "value" "not" "in";
    wire "not" "out" "exclude_edge" "in";
    wire "select_edge" "events" "select_gate" "on";
    wire "exclude_edge" "events" "exclude_gate" "on";
    wire guard_node guard_port "select_gate" "guard";
    wire "not" "out" "exclude_gate" "guard";
    wire "select_gate" "candidate" "arbiter" "in0";
    wire "arbiter" "out0" "select_commit" "grant";
    wire "true" "out" "select_commit" "value0";
    wire "select_commit" "write0" "selected" "write0";
    wire false_node false_port "select_commit" "value1";
    wire "select_commit" "write1" "excluded" "write0";
    wire "exclude_gate" "candidate" "arbiter" "in1";
    wire "arbiter" "out1" "exclude_commit" "grant";
    wire "false" "out" "exclude_commit" "value0";
    wire "exclude_commit" "write0" "selected" "write1";
    wire "true" "out" "exclude_commit" "value1";
    wire "exclude_commit" "write1" "excluded" "write1"] @
    (if state_reading then [wire "selected" "value" "selected_not" "in";
       wire "evidence" "value" "select_guard" "in0";
       wire "selected_not" "out" "select_guard" "in1"] else []) in
  let exports = [endpoint "evidence" "value"; endpoint "evidence" "updated";
    endpoint "select_edge" "events"; endpoint "not" "out"; endpoint "exclude_edge" "events";
    endpoint "true" "out"; endpoint "false" "out";
    endpoint "select_gate" "candidate"; endpoint "exclude_gate" "candidate";
    endpoint "arbiter" "out0"; endpoint "arbiter" "out1";
    endpoint "select_commit" "write0"; endpoint "select_commit" "write1"; endpoint "select_commit" "request0";
    endpoint "exclude_commit" "write0"; endpoint "exclude_commit" "write1";
    endpoint "selected" "value"; endpoint "excluded" "value"] @
    (if state_reading then [endpoint "selected_not" "out"; endpoint "select_guard" "out"] else []) in
  fragment (if state_reading then "fixture.decision.state" else "fixture.decision.exclusion") nodes wires
    [boundary "product" "input" "product_symbol" "select_commit" "product0";
     boundary "request" "output" "effect_request" "select_commit" "request0";
     boundary "authorization" "output" "truth_value" guard_node guard_port]
    [external_slot "condition" "evidence" "evidence" "samples"]
    [obj ["id", str "exclusive_selection"; "arbiter", str "arbiter";
       "commits", arr [str "select_commit"; str "exclude_commit"]]] exports

let rejection_count = ref 0
let rejects ?message label action = match action () with
  | () -> failwith ("Fragment mutant accepted: " ^ label)
  | exception Diagnostic.Error diagnostic ->
      (match message with None -> () | Some expected ->
        require (diagnostic.code = "policy_component_fragment" && diagnostic.message = expected)
          ("Fragment mutant rejected at wrong boundary: " ^ label ^ ": " ^ diagnostic.message));
      incr rejection_count

let run first second =
  let a_raw = original_library first and b_raw = original_library second in
  let a = I.library_of_json a_raw and b = I.library_of_json b_raw in
  require (I.library_digest a <> I.library_digest b) "Reuse must span distinct complete libraries";
  let driver_a = driver a_raw and driver_b = driver b_raw in
  require (Json.equal driver_a driver_b) "Literal driver definition changed between originals";
  let da = F.of_json ~library:a driver_a and db = F.of_json ~library:b driver_b in
  require (F.fingerprint da = F.fingerprint db) "Whole-library identity contaminated reusable fragment";
  require (F.model_library_digest da = I.library_digest a && F.model_library_digest db = I.library_digest b)
    "Contextual model-library identity was lost";
  require (Json.equal (F.to_json da) driver_a && F.fingerprint da = Canonical.fingerprint driver_a)
    "Fragment canonical roundtrip changed supplied authority";
  require (List.length (F.nodes da) = 2 && F.wires da = [] && F.atomic_groups da = [])
    "Driver acquired an invented full-graph dependency";
  require (List.length (F.boundary_ports da) = 3 && List.length (F.external_slots da) = 1 &&
    List.length (F.semantic_exports da) = 3) "Driver interface or full output inventory changed";
  let product_port = List.hd (F.boundary_ports da) in
  require (product_port.replication = I.Executor) "Product lost its executor-constant scope";
  let request_port = List.nth (F.boundary_ports da) 1 in
  require (request_port.replication = I.Encounter_slots {layout_id="encounters";slots=2})
    "Request lost distinct encounter-slot identity";
  let decision_a = decision a_raw false and decision_b = decision b_raw true in
  let fa = F.of_json ~library:a decision_a and fb = F.of_json ~library:b decision_b in
  require (List.length (F.nodes fa) = 13 && List.length (F.wires fa) = 19 &&
    List.length (F.semantic_exports fa) = 18) "A literal partition changed";
  require (List.length (F.nodes fb) = 15 && List.length (F.wires fb) = 22 &&
    List.length (F.semantic_exports fb) = 20) "B literal partition changed";
  require (F.fingerprint fa <> F.fingerprint fb) "Different decision bodies collapsed";
  let auth = List.nth (F.boundary_ports fb) 2 in
  require (auth.endpoint = ({node_id="select_guard";port_id="out"}:I.endpoint))
    "B authorization interface lost its actual state-reading producer";
  let check raw = ignore (F.of_json ~library:a raw) in
  List.iter (fun key -> rejects ("missing " ^ key) (fun () -> check (remove key driver_a)))
    ["schema_version";"profile";"primitive_profile";"observable_profile";"phase_profile";
     "id";"version";"slot_layout";"nodes";"wires";"boundary_ports";"external_slots";"atomic_groups";"semantic_exports"];
  List.iter (fun key -> rejects ("unknown " ^ key) (fun () -> check (replace key (str "future") driver_a)))
    ["schema_version";"profile";"primitive_profile";"observable_profile";"phase_profile"];
  List.iter (fun key -> rejects ("foreign authority " ^ key) (fun () -> check (add key (str "untrusted") driver_a)))
    ["source_artifact_digest";"library_digest";"accepted";"material_contract";"hidden_outputs"];
  rejects "duplicate JSON key" (fun () -> check (add "id" (str "fixture.driver") driver_a));
  rejects "long local name" (fun () -> check (replace "id" (str (String.make 129 'x')) driver_a));
  rejects "empty fragment" (fun () -> check (replace "nodes" (arr []) driver_a));
  rejects "duplicate local node" (fun () -> check (replace "nodes" (arr (List.hd (items "nodes" driver_a)::items "nodes" driver_a)) driver_a));
  rejects "undeclared input" (fun () -> check (replace "boundary_ports" (arr [List.hd (items "boundary_ports" driver_a)]) driver_a));
  rejects ~message:"Duplicate fragment boundary endpoint identity." "duplicate input alias" (fun () -> check (replace "boundary_ports"
    (arr (replace "id" (str "second-request") (List.nth (items "boundary_ports" driver_a) 1)::items "boundary_ports" driver_a)) driver_a));
  rejects "duplicate boundary id" (fun () -> check (change_item "boundary_ports" 1 (replace "id" (str "product")) driver_a));
  rejects "wrong boundary direction" (fun () -> check (change_item "boundary_ports" 1 (replace "direction" (str "output")) driver_a));
  rejects "wrong boundary type" (fun () -> check (change_item "boundary_ports" 1 (replace "signal_type" (str "truth_value")) driver_a));
  rejects "absent boundary endpoint" (fun () -> check (change_item "boundary_ports" 1
    (replace "endpoint" (endpoint "foreign" "request")) driver_a));
  rejects "wrong feedback kind" (fun () -> check (change_item "external_slots" 0 (replace "kind" (str "evidence")) driver_a));
  rejects "missing feedback" (fun () -> check (replace "external_slots" (arr []) driver_a));
  rejects "boundary/external input alias" (fun () -> check (replace "boundary_ports"
    (arr (boundary "feedback-alias" "input" "feedback_batch" "attempt" "feedback"::items "boundary_ports" driver_a)) driver_a));
  let with_constant = driver_a
    |> replace "nodes" (arr (items "nodes" driver_a @ [node a_raw "true" "exclusion.primitive.true"]))
    |> replace "semantic_exports" (arr (items "semantic_exports" driver_a @ [endpoint "true" "out"])) in
  check with_constant;
  rejects ~message:"Fragment input has multiple suppliers." "wire/boundary input alias" (fun () -> check (replace "wires"
    (arr [wire "true" "out" "attempt" "authorization"]) with_constant));
  let constant_broadcast = with_constant
    |> replace "boundary_ports" (arr [List.hd (items "boundary_ports" driver_a);
       List.nth (items "boundary_ports" driver_a) 1])
    |> replace "wires" (arr [wire "true" "out" "attempt" "authorization"]) in
  check constant_broadcast;
  let executor_logic_model = model a_raw "exclusion.primitive.not"
    |> fun value -> replace "body" (replace "replication" (obj ["kind",str "executor"]) (get "body" value)) value
    |> rehash_model in
  let logic_library_raw = replace "models" (arr (List.map (fun value ->
      if get "id" (get "identity" value) = str "exclusion.primitive.not" then executor_logic_model else value)
      (items "models" a_raw))) a_raw in
  let logic_library = I.library_of_json logic_library_raw in
  let with_logic = with_constant
    |> replace "nodes" (arr (items "nodes" with_constant @ [obj ["id",str "logic";"model",executor_logic_model]]))
    |> replace "semantic_exports" (arr (items "semantic_exports" with_constant @ [endpoint "logic" "out"]))
    |> replace "wires" (arr [wire "true" "out" "logic" "in"]) in
  ignore (F.of_json ~library:logic_library with_logic);
  rejects ~message:"Fragment wire scope differs; only immutable constants may broadcast to encounter slots."
    "executor logic broadcast" (fun () -> ignore (F.of_json ~library:logic_library
      (with_logic |> replace "boundary_ports" (get "boundary_ports" constant_broadcast)
       |> replace "wires" (arr [wire "true" "out" "logic" "in";wire "logic" "out" "attempt" "authorization"]))));
  let local_logic = fragment "fixture.local-logic" [node a_raw "logic" "exclusion.primitive.not"] []
    [boundary "value" "input" "truth_value" "logic" "in"] [] [] [endpoint "logic" "out"] in
  check local_logic;
  rejects ~message:"Fragment contains an instantaneous local scheduling cycle." "local scheduling cycle"
    (fun () -> check (local_logic |> replace "boundary_ports" (arr [])
      |> replace "wires" (arr [wire "logic" "out" "logic" "in"])));
  rejects ~message:"Fragment wire signal types differ." "signal conversion" (fun () -> check (replace "wires" (arr [wire "product" "out" "attempt" "authorization"]) driver_a));
  rejects ~message:"Fragment semantic exports must contain every output in fixed node/port order."
    "hidden outputs" (fun () -> check (replace "semantic_exports" (arr [endpoint "product" "out"]) driver_a));
  rejects "reordered outputs" (fun () -> check (replace "semantic_exports" (arr (List.rev (items "semantic_exports" driver_a))) driver_a));
  rejects "extra output" (fun () -> check (replace "semantic_exports" (arr (items "semantic_exports" driver_a @ [endpoint "product" "out"])) driver_a));
  rejects "layout replication mismatch" (fun () -> check (replace "slot_layout" (obj ["id",str "encounters";"slots",Json.int 3]) driver_a));
  rejects "raw float layout" (fun () -> check (replace "slot_layout" (obj ["id",str "encounters";"slots",Json.Float 2.]) driver_a));
  rejects ~message:"Fragment changed a complete model or configuration body." "foreign complete model" (fun () -> check (change_item "nodes" 1
    (fun n -> replace "model" (replace "body" (replace "configuration"
      (replace "timeout_ticks" (Json.int 5) (get "configuration" (get "body" (get "model" n))))
      (get "body" (get "model" n))) (get "model" n)) n) driver_a));
  let foreign_model = model a_raw "exclusion.primitive.attempt" |> fun value ->
    replace "body" (replace "configuration" (replace "timeout_ticks" (Json.int 5)
      (get "configuration" (get "body" value))) (get "body" value)) value |> rehash_model in
  let foreign_library_raw = replace "models" (arr (List.map (fun value ->
      if get "id" (get "identity" value) = str "exclusion.primitive.attempt" then foreign_model else value)
      (items "models" a_raw))) a_raw in
  let foreign_library = I.library_of_json foreign_library_raw in
  let foreign_fragment = change_item "nodes" 1 (replace "model" foreign_model) driver_a in
  ignore (F.of_json ~library:foreign_library foreign_fragment);
  rejects ~message:"Fragment model is absent from the independently supplied library." "repinned model from another library"
    (fun () -> check foreign_fragment);
  rejects "orphan atomic nodes" (fun () -> check (replace "atomic_groups" (arr []) decision_a));
  rejects "partial atomic group" (fun () -> check (change_item "atomic_groups" 0
    (replace "commits" (arr [str "select_commit"])) decision_a));
  rejects ~message:"Fragment arbiter lane must drive exactly its local corresponding commit." "swapped arbiter lanes" (fun () -> check (change_item "atomic_groups" 0
    (replace "commits" (arr [str "exclude_commit";str "select_commit"])) decision_a));
  rejects ~message:"Fragment atomic action needs one local destination or one boundary continuation." "atomic request has no continuation" (fun () -> check (replace "boundary_ports"
    (arr [List.hd (items "boundary_ports" decision_a);List.nth (items "boundary_ports" decision_a) 2]) decision_a));
  let rec cycle = Json.Array [cycle] in
  rejects "cyclic JSON value" (fun () -> check cycle);
  let rec spine = Json.Null :: spine in
  rejects "cyclic native list spine" (fun () -> check (Json.Array spine));
  rejects "depth exhaustion" (fun () -> check (List.fold_left (fun value _ -> arr [value]) Json.Null (List.init 49 Fun.id)));
  require (!rejection_count = 55) "Missing or duplicated distinguishing fragment controls";
  Printf.printf "policy component fragment: 4 literal partial graphs plus constant-broadcast controls; %d rejection controls; no composition acceptance\n" !rejection_count

let () = require (Array.length Sys.argv = 3) "Expected two independent original fixture paths";
  run (read Sys.argv.(1)) (read Sys.argv.(2))
