open Bioc_wire
open Bioc_domain
module Manifest = Source_execution_manifest
module Names = Map.Make (String)
module Ids = Set.Make (String)
let implementation_version = "biocompiler.ocaml.source_execution_producer.v0.1"
let diagnostic_profile = Diagnostic_text.profile
let str value = Json.String value
let arr values = Json.Array values
let obj fields = Json.Object fields
let strings values = arr (List.map str values)
let field key value = Json.field key (Json.object_fields value)
let optional key value = Option.value ~default:Json.Null (List.assoc_opt key (Json.object_fields value))
let text key value = Json.string (field key value)
let inputs node = Json.array (field "inputs" node) |> List.map Json.string
let input node index = match List.nth_opt (inputs node) index with Some value -> value
  | None -> Diagnostic.fail "invalid_source_execution" "Source operation is missing an operand."
let semantics node = obj (List.remove_assoc "source" (Json.object_fields node))
let attrs node = field "attributes" node
let attribute node key = optional key (attrs node)
let truthy = function
  | Json.Null | Json.Bool false | Json.String "" | Json.Array [] | Json.Object [] -> false
  | (Json.Int _ | Json.Float _) as value -> Json.number_compare value (Json.int 0) <> 0
  | _ -> true
let pointer value = String.split_on_char '~' value |> String.concat "~0" |> String.split_on_char '/' |> String.concat "~1"

(* These spellings belong to the public Python producer contract. They are
   derived from original source policy, never from a candidate or checker. *)
let unsupported_message lookup node code = match code with
  | "unsupported_lowering_operation" -> "Operation " ^ Diagnostic_text.repr (text "kind" node) ^ " needs an additional execution profile or semantic refinement."
  | "unsupported_lowering_value_kind" -> "The first behavior profile supports bound scalar design values only."
  | "unsupported_lowering_state_policy" -> "Unknown source state-read or arbitration semantics."
  | "unsupported_lowering_rule_policy" ->
      if attribute node "execution" <> str "concurrent" || attribute node "priority" <> str "unspecified" then
        "Unknown source rule execution or priority semantics."
      else if not (List.mem (attribute node "trigger") [str "condition"; str "event"]) then "Unknown source trigger semantics."
      else "Unrecognized source rule policy fields."
  | "unsupported_lowering_event_duration" ->
      if attribute node "ongoing_duration" <> str "explicit_or_design_choice" then "Unknown source event-duration semantics."
      else "Event-triggered ongoing actions require an explicit duration via for_()."
  | "unsupported_lowering_integration" ->
      let local = match inputs node with observed :: [_] ->
          let observed = lookup observed in
          text "kind" observed = "signal" && attribute (lookup (input observed 0)) "scope" = str "contact"
        | _ -> false in
      if local then "Contact-scoped integration needs an explicit identity/history profile."
      else "Rolling integration supports a direct cell-local numeric observation only."
  | "unsupported_lowering_nested_pulse" -> "Nested pulses need an explicit duration-composition policy."
  | "unsupported_lowering_integral_step" -> "Rolling integration requires explicit execution.integral_step authority."
  | "unsupported_lowering_dynamic_duration" -> "A temporal duration must be a bound design-time constant."
  | _ -> Diagnostic.fail "source_execution_diagnostic" "Unknown lowering diagnostic cannot be translated into a legacy source claim."
let unsupported_codes = ["unsupported_lowering_operation"; "unsupported_lowering_value_kind";
    "unsupported_lowering_state_policy"; "unsupported_lowering_rule_policy"; "unsupported_lowering_event_duration";
    "unsupported_lowering_integration"; "unsupported_lowering_nested_pulse"; "unsupported_lowering_integral_step";
    "unsupported_lowering_dynamic_duration"]

let derive source =
  let source = Human_request.of_json (Human_request.to_json source) in
  let build = Human_request.build_request source in
  let nodes = Intent.to_json (Build_request.intent build) |> field "nodes" |> Json.array in
  Diagnostic.require (List.length nodes <= Manifest.max_source_nodes) "source_manifest_limit" "Executable source node limit exceeded.";
  let by_id = List.fold_left (fun map node -> Names.add (text "id" node) node map) Names.empty nodes in
  let lookup identity = match Names.find_opt identity by_id with Some node -> node
    | None -> Diagnostic.fail "invalid_source_execution" "Source operation names an absent dependency." in
  let budget = Manifest.create_resource_budget () in
  let retain raw = Manifest.reserve_json budget raw; raw in
  (* Ancestry is independently traversed for each output. Bounded retained
     dependencies, rather than an unbounded all-pairs closure, bound publication. *)
  let lineage identity =
    let pending = ref [identity] and seen = ref Ids.empty in
    while !pending <> [] do
      let identity = List.hd !pending in pending := List.tl !pending;
      if not (Ids.mem identity !seen) then (
        seen := Ids.add identity !seen;
        let node = lookup identity in
        let refs = match field "role" node with Json.Null -> inputs node | value -> Json.string value :: inputs node in
        pending := List.rev_append refs !pending)
    done;
    Ids.elements !seen in
  let roles = List.filter_map (fun node -> if text "kind" node = "role" then Some (text "id" node) else None) nodes in
  let outputs = ref [] in
  List.iter (fun rule -> if text "kind" rule = "rule" then (
      Diagnostic.require (List.length (inputs rule) >= 3) "invalid_source_execution" "Source rule requires guard and action.";
      let actions = List.tl (List.tl (inputs rule)) in
      List.iter (fun action_id ->
          let action = lookup action_id in
          let primitive = if text "kind" action = "action.pulse" then lookup (input action 0) else action in
          let product = if text "kind" primitive = "action.secrete" && inputs primitive <> [] then
              optional "product" (attrs (lookup (input primitive 0))) else Json.Null in
          let trigger = attribute rule "trigger" in
          let activation = if text "kind" action = "action.pulse" then "explicit_duration"
            else if text "kind" primitive = "action.state_set" then (if trigger = str "event" then "event" else "level")
            else if truthy (attribute primitive "ongoing") then "level"
            else if trigger = str "event" then "event" else "onset" in
          let dependencies = List.map (fun reference -> retain (semantics (lookup reference))) (lineage action_id) in
          let raw = retain (obj ["id", str ("output:" ^ text "id" rule ^ ":" ^ action_id);
            "rule_id", field "id" rule; "action_id", str action_id; "guard_id", str (input rule 1);
            "role_id", field "role" rule; "action_kind", field "kind" primitive; "lineage", strings (lineage (text "id" rule));
            "trigger", trigger; "activation", str activation; "product", product;
            "semantics", obj ["action", semantics action; "primitive_action", semantics primitive; "dependencies", arr dependencies]]) in
          outputs := Manifest.Output.of_json raw :: !outputs) actions)) nodes;
  let outputs = List.rev !outputs in
  let diagnostics = ref [] in
  let diagnostic code category source_node_ids message =
    let value = Manifest.Diagnostic_record.make ~code ~category ~source_node_ids ~message in
    ignore (retain (Manifest.Diagnostic_record.to_json value)); diagnostics := value :: !diagnostics in
  let behavior = try Some (Lowering.lower build) with
    | Diagnostic.Error error when List.mem error.code unsupported_codes ->
        let node = match List.find_opt (fun node -> error.path = Some ("/intent/nodes/" ^ pointer (text "id" node))) nodes with
          | Some node -> node | None -> raise (Diagnostic.Error error) in
        let message = unsupported_message lookup node error.code ^ " [" ^ text "id" node ^ "]" in
        let message = match field "source" node with Json.Null -> message
          | location -> message ^ " at " ^ text "file" location ^ ":" ^ Canonical.encode (field "line" location) in
        diagnostic "source_execution_profile_unsupported" Manifest.Diagnostic_record.Unsupported_semantics [text "id" node] message; None
    | Diagnostic.Error error when error.code = "invalid_lowering_execution_policy" ->
        let message = if error.message = "Integral sampling step must be positive." then error.message
          else "Unknown frozen behavior execution policy fields." in
        diagnostic "invalid_source_execution_semantics" Manifest.Diagnostic_record.Contradiction [] message; None in
  let constraints = Build_request.implementation_constraints build |> List.map fst |> List.filter (fun key ->
      key <> "execution" || Build_request.behavior_profile build <> Build_request.V2) |> List.sort String.compare in
  if constraints <> [] then diagnostic "uninterpreted_implementation_constraints" Manifest.Diagnostic_record.Unsupported_semantics []
      ("Retained implementation constraints require interpretation: " ^ String.concat ", " constraints);
  if Build_request.preferences build <> [] then diagnostic "uninterpreted_source_preferences" Manifest.Diagnostic_record.Unsupported_semantics []
      "Original source preferences require a declared ranking interpretation.";
  if Human_request.kind source <> Human_request.Build then diagnostic "wrapped_source_obligations" Manifest.Diagnostic_record.Missing_refinement []
      "Wrapped deployment and acceptance obligations remain separate from executable source semantics.";
  let ledger = List.map (fun node -> retain (obj ["id", str ("source:" ^ text "id" node); "kind", field "kind" node;
      "source_node_ids", arr [field "id" node]; "semantics", semantics node])) nodes in
  let complete_authority = retain (obj ["id", str "source:complete_authority"; "kind", str "source_authority";
      "source_node_ids", arr (List.map (field "id") nodes); "semantics", Human_request.to_json source]) in
  let role_nodes = roles |> List.map (fun role -> role, retain (arr (List.filter_map (fun node ->
      if field "role" node = Json.Null || field "role" node = str role then Some (field "id" node) else None) nodes))) |> obj in
  let states = List.filter_map (fun node -> if text "kind" node <> "state" then None else (
      let assignments = List.filter_map (fun output ->
          let primitive = field "primitive_action" (Manifest.Output.semantics output) in
          if Manifest.Output.action_kind output = "action.state_set" && input primitive 0 = text "id" node then
            Some (retain (obj ["output_id", str (Manifest.Output.id output); "rule_id", str (Manifest.Output.rule_id output);
              "action_id", str (Manifest.Output.action_id output); "guard_id", str (Manifest.Output.guard_id output);
              "value", attribute primitive "value"])) else None) outputs in
      Some (retain (obj ["id", field "id" node; "declaration", semantics node; "assignments", arr assignments])))) nodes in
  let channels = List.filter_map (fun node -> if text "kind" node <> "channel" then None else (
      let senders = List.filter_map (fun output ->
          let primitive = field "primitive_action" (Manifest.Output.semantics output) in
          if Manifest.Output.action_kind output = "action.emit" && input primitive 1 = text "id" node then
            Some (retain (obj ["output_id", str (Manifest.Output.id output); "role_id", str (Manifest.Output.role_id output);
              "rule_id", str (Manifest.Output.rule_id output); "action_id", str (Manifest.Output.action_id output);
              "value_id", (if List.length (inputs primitive) = 3 then str (input primitive 2) else Json.Null)])) else None) outputs in
      let receivers = List.filter_map (fun item ->
          if text "kind" item = "channel_observation" && input item 1 = text "id" node then
            Some (retain (obj ["observation_id", field "id" item; "role_id", field "role" item])) else None) nodes in
      Some (retain (obj ["id", field "id" node; "declaration", semantics node; "senders", arr senders;
        "receivers", arr receivers; "transport", str "requires_explicit_architecture_contract"])))) nodes in
  Manifest.make ~source ~behavior ~roles ~outputs ~ledger:(ledger @ [complete_authority]) ~role_nodes ~states ~channels
    ~diagnostics:(List.rev !diagnostics)
