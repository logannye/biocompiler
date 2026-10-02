open Bioc_wire
open Bioc_domain
module S = Source_execution_manifest
module Names = Map.Make (String)
module Seen = Set.Make (String)
let checker_version = "biocompiler.ocaml.source_manifest_check.v0.1"
let claim_scope = "original_source_and_retained_execution_inventory_correspondence_only"
type result = { failures : string list; unresolved : string list }
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let strings values = arr (List.map str values)
let field key value = Json.field key (Json.object_fields value)
let optional_field key value = Option.value ~default:Json.Null (List.assoc_opt key (Json.object_fields value))
let text key value = Json.string (field key value)
let inputs value = Json.array (field "inputs" value) |> List.map Json.string
let input index value = match List.nth_opt (inputs value) index with
  | Some value -> value
  | None -> Diagnostic.fail "invalid_source_manifest_authority" "Original source is missing a required operand."
let semantics value = obj (List.filter (fun (key, _) -> key <> "source") (Json.object_fields value))
let truthy = function
  | Json.Null | Json.Bool false | Json.String "" | Json.Array [] | Json.Object [] -> false
  | (Json.Int _ | Json.Float _) as value -> Json.number_compare value (Json.int 0) <> 0
  | _ -> true
let check ~expected_source ~manifest =
  let original = Human_request.build_request expected_source in
  let nodes = Build_request.intent original |> Intent.to_json |> field "nodes" |> Json.array in
  Diagnostic.require (List.length nodes <= S.max_source_nodes) "source_manifest_limit" "Source manifest reconstruction exceeds the native source-node limit.";
  let by_id = List.fold_left (fun found node -> Names.add (text "id" node) node found) Names.empty nodes in
  let lookup identity = match Names.find_opt identity by_id with Some value -> value
    | None -> Diagnostic.fail "invalid_source_manifest_authority" "Original source contains a missing reference." in
  let lineage_cache = Hashtbl.create (List.length nodes) in
  let lineage identity = match Hashtbl.find_opt lineage_cache identity with
    | Some value -> value
    | None ->
    let rec visit seen = function
      | [] -> Seen.elements seen
      | identity :: rest when Seen.mem identity seen -> visit seen rest
      | identity :: rest ->
          let node = lookup identity in
          let parents = match field "role" node with Json.Null -> inputs node | role -> Json.string role :: inputs node in
          visit (Seen.add identity seen) (List.rev_append parents rest) in
    let result = visit Seen.empty [identity] in
    Hashtbl.add lineage_cache identity result; result in
  let budget = S.create_resource_budget () in
  let reserve raw = S.reserve_json budget raw; raw in
  let failures = ref [] and unresolved = ref [] in
  let fail code = failures := code :: !failures and unknown code = unresolved := code :: !unresolved in
  if not (Json.equal (Human_request.to_json (S.source manifest)) (Human_request.to_json expected_source)) then fail "source_authority";
  let roles = List.filter (fun node -> text "kind" node = "role") nodes |> List.map (text "id") in
  let outputs = List.filter (fun node -> text "kind" node = "rule") nodes |> List.concat_map (fun rule ->
      let actions = match inputs rule with _ :: _ :: actions -> actions
        | _ -> Diagnostic.fail "invalid_source_manifest_authority" "Source rule is missing guard or action authority." in
      List.map (fun identity ->
          let action = lookup identity in
          let primitive = if text "kind" action = "action.pulse" then lookup (input 0 action) else action in
          let trigger = optional_field "trigger" (field "attributes" rule) in
          let kind = text "kind" primitive in
          let activation = if text "kind" action = "action.pulse" then "explicit_duration"
            else if truthy (optional_field "ongoing" (field "attributes" primitive)) || (kind = "action.state_set" && Json.equal trigger (str "condition")) then "level"
            else if Json.equal trigger (str "event") then "event" else "onset" in
          let product = if kind = "action.secrete" then optional_field "product" (field "attributes" (lookup (input 0 primitive))) else Json.Null in
          reserve (obj ["id", str ("output:" ^ text "id" rule ^ ":" ^ identity);
            "rule_id", field "id" rule; "action_id", str identity; "guard_id", str (input 1 rule); "role_id", field "role" rule;
            "action_kind", str kind; "lineage", strings (lineage (text "id" rule)); "trigger", trigger; "activation", str activation; "product", product;
            "semantics", obj ["action", semantics action; "primitive_action", semantics primitive;
              "dependencies", arr (List.map (fun identity -> semantics (lookup identity)) (lineage identity))]])) actions) in
  let ledger = List.map (fun node -> reserve (obj ["id", str ("source:" ^ text "id" node); "kind", field "kind" node;
      "source_node_ids", arr [field "id" node]; "semantics", semantics node])) nodes in
  let complete = reserve (obj ["id", str "source:complete_authority"; "kind", str "source_authority";
      "source_node_ids", arr (List.map (field "id") nodes); "semantics", Human_request.to_json expected_source]) in
  let states = List.filter (fun node -> text "kind" node = "state") nodes |> List.map (fun node ->
      let assignments = List.filter_map (fun output ->
          let primitive = field "primitive_action" (field "semantics" output) in
          if text "action_kind" output = "action.state_set" && input 0 primitive = text "id" node then
            Some (obj ["output_id", field "id" output; "rule_id", field "rule_id" output; "action_id", field "action_id" output;
              "guard_id", field "guard_id" output; "value", field "value" (field "attributes" primitive)]) else None) outputs in
      reserve (obj ["id", field "id" node; "declaration", semantics node; "assignments", arr assignments])) in
  let channels = List.filter (fun node -> text "kind" node = "channel") nodes |> List.map (fun node ->
      let senders = List.filter_map (fun output ->
          let primitive = field "primitive_action" (field "semantics" output) in
          if text "action_kind" output = "action.emit" && input 1 primitive = text "id" node then
            Some (obj ["output_id", field "id" output; "role_id", field "role_id" output; "rule_id", field "rule_id" output;
              "action_id", field "action_id" output; "value_id", (if List.length (inputs primitive) = 3 then str (input 2 primitive) else Json.Null)]) else None) outputs in
      let receivers = List.filter_map (fun item ->
          if text "kind" item = "channel_observation" && input 1 item = text "id" node then
            Some (obj ["observation_id", field "id" item; "role_id", field "role" item]) else None) nodes in
      reserve (obj ["id", field "id" node; "declaration", semantics node; "senders", arr senders;
        "receivers", arr receivers; "transport", str "requires_explicit_architecture_contract"])) in
  let role_nodes = obj (List.map (fun role -> role, arr (List.filter_map (fun node ->
      let bound = field "role" node in if bound = Json.Null || Json.equal bound (str role) then Some (field "id" node) else None) nodes)) roles) |> reserve in
  let inventory = ["roles", strings roles, strings (S.roles manifest);
    "outputs", arr outputs, arr (List.map S.Output.to_json (S.outputs manifest));
    "ledger", arr (ledger @ [complete]), arr (S.ledger manifest);
    "role_nodes", role_nodes, S.role_nodes manifest;
    "states", arr states, arr (S.states manifest); "channels", arr channels, arr (S.channels manifest)] in
  List.iter (fun (key, expected, supplied) -> if not (Json.equal expected supplied) then fail ("source_manifest_" ^ key)) inventory;
  (match S.behavior manifest with
  | None -> unknown "source_execution_unavailable"
  | Some behavior ->
      (try ignore (Lowering_check.check ~expected_request:original ~behavior)
       with Diagnostic.Error error -> fail ("source_behavior:" ^ error.code)));
  let constraints = Build_request.implementation_constraints original |> List.map fst in
  let constraints = match Build_request.behavior_profile original with Build_request.V1 -> constraints
    | Build_request.V2 -> List.filter (fun key -> key <> "execution") constraints in
  if constraints <> [] then unknown "uninterpreted_implementation_constraints";
  if Build_request.preferences original <> [] then unknown "uninterpreted_source_preferences";
  if Human_request.kind expected_source <> Human_request.Build then unknown "wrapped_source_obligations";
  {failures = List.rev !failures; unresolved = List.rev !unresolved}
let check_json ~expected_source ~manifest =
  check ~expected_source:(Human_request.of_json expected_source) ~manifest:(S.of_json manifest)
