open Bioc_wire
open Bioc_domain
module Names = Map.Make (String)
module Ids = Set.Make (String)

let producer_version = "biocompiler.ocaml.lowering.v0.1"
let str value = Json.String value
let strings values = Json.Array (List.map str values)
let require = Diagnostic.require
let fail = Diagnostic.fail
type source_node = {
  id : string;
  kind : string;
  inputs : string list;
  attrs : (string * Json.t) list;
  dtype : Json.t;
  role : string option;
  source : Json.t;
}
let field key value = Json.field key (Json.object_fields value)
let read_node value = {
  id = Json.string (field "id" value); kind = Json.string (field "kind" value);
  inputs = Json.array (field "inputs" value) |> List.map Json.string;
  attrs = Json.object_fields (field "attributes" value); dtype = field "data_type" value;
  role = (match field "role" value with Json.Null -> None | value -> Some (Json.string value));
  source = field "source" value;
}
let attribute node key = Option.value ~default:Json.Null (List.assoc_opt key node.attrs)
let pointer text = String.split_on_char '~' text |> String.concat "~0" |> String.split_on_char '/' |> String.concat "~1"
let error node code message =
  let context = match node.source with
    | Json.Null -> ""
    | value -> " (" ^ Json.string (field "file" value) ^ ":" ^ Canonical.encode (field "line" value) ^ ")" in
  fail ~path:("/intent/nodes/" ^ pointer node.id) code (message ^ context)
let input node index = match List.nth_opt node.inputs index with Some value -> value
  | None -> error node "invalid_lowering_source" "Malformed source operation is missing an input."
let lookup map identity = match Names.find_opt identity map with Some value -> value
  | None -> fail "invalid_lowering_source" "Malformed source contains a missing reference."
let supported = Ids.of_list [
    "role"; "scope"; "signal"; "qualitative"; "literal"; "parameter";
    "and"; "or"; "not"; "at_least"; "add"; "subtract"; "multiply"; "divide"; "negate"; "compare";
    "held_for"; "recently"; "became_true"; "followed_by"; "memory"; "memory.is_set"; "state"; "state.is";
    "signature"; "secretion"; "rule"; "action.state_set"; "action.report"; "action.pulse";
    "action.eliminate"; "action.engulf"; "action.secrete"; "action.present"; "action.retain";
    "action.expand"; "action.rest"; "action.differentiate"]
let extension = Ids.of_list ["integrated"; "channel"; "channel_observation"; "action.emit"]
let truthy = function
  | Json.Null | Json.Bool false | Json.String "" | Json.Array [] | Json.Object [] -> false
  | (Json.Int _ | Json.Float _) as value -> Json.number_compare value (Json.int 0) <> 0
  | _ -> true

(* Producer-local policy interpretation. The checker independently reconstructs
   its expectations; none of these helpers is exported or shared with it. *)
let profile_sources profile map nodes =
  List.iter (fun node ->
      if not (Ids.mem node.kind supported || profile = Build_request.V2 && Ids.mem node.kind extension) then
        error node "unsupported_lowering_operation" "Operation requires another execution profile or a semantic refinement.";
      if List.mem node.kind ["literal"; "parameter"] && Type_spec.kind (Type_spec.of_json node.dtype) <> Type_spec.Scalar then
        error node "unsupported_lowering_value_kind" "Behavior lowering accepts bound scalar design values only.";
      match node.kind with
      | "state" ->
          if attribute node "observation" <> str "prior_state" || attribute node "arbitration" <> str "unspecified" then
            error node "unsupported_lowering_state_policy" "Unknown source state-read or arbitration policy."
      | "rule" ->
          if attribute node "execution" <> str "concurrent" || attribute node "priority" <> str "unspecified" then
            error node "unsupported_lowering_rule_policy" "Unknown source rule concurrency or priority.";
          let event = attribute node "trigger" = str "event" in
          if not event && attribute node "trigger" <> str "condition" then
            error node "unsupported_lowering_rule_policy" "Unknown source rule trigger.";
          let allowed = ["trigger"; "execution"; "priority"; "name"] in
          let allowed = if event then (
              if attribute node "ongoing_duration" <> str "explicit_or_design_choice" then
                error node "unsupported_lowering_event_duration" "Unknown source event-duration policy.";
              List.iteri (fun index reference -> if index >= 2 then (
                  let action = lookup map reference in
                  if truthy (attribute action "ongoing") && action.kind <> "action.pulse" then
                    error node "unsupported_lowering_event_duration" "Event-triggered ongoing actions require an explicit pulse.")) node.inputs;
              "ongoing_duration" :: allowed) else allowed in
          if List.exists (fun (key, _) -> not (List.mem key allowed)) node.attrs then
            error node "unsupported_lowering_rule_policy" "Unrecognized source rule policy field."
      | "integrated" ->
          if List.length node.inputs <> 2 then
            error node "unsupported_lowering_integration" "Integration requires a direct local observation and a window.";
          let observed = lookup map (input node 0) in
          if not (List.mem observed.kind ["signal"; "channel_observation"]) then
            error node "unsupported_lowering_integration" "Integration requires a direct local numeric observation.";
          if observed.kind = "signal" && attribute (lookup map (input observed 0)) "scope" = str "contact" then
            error node "unsupported_lowering_integration" "Contact integration requires an identity/history refinement."
      | "action.pulse" ->
          (match node.inputs with first :: _ when (lookup map first).kind = "action.pulse" ->
             error node "unsupported_lowering_nested_pulse" "Nested pulse durations require an explicit composition policy."
           | _ -> ())
      | _ -> ()) nodes

let rewritten bindings node =
  let put key value fields = (key, value) :: List.remove_assoc key fields in
  match node.kind with
  | "parameter" ->
      let name = Json.string (attribute node "name") in
      let value = match Names.find_opt name bindings with Some value -> value
        | None -> error node "invalid_lowering_source" "Frozen request omits a declared binding." in
      node.attrs |> put "bound" (Json.Bool true) |> put "default" value
  | "state" ->
      node.attrs |> put "observation" (str "shared_pre_update_state")
                 |> put "arbitration" (str "coalesce_identical_else_error")
  | "rule" ->
      let event = attribute node "trigger" = str "event" in
      let attrs = node.attrs |> put "priority" (str "none")
          |> put "ongoing_activation" (str (if event then "explicit_duration" else "level"))
          |> put "impulse_activation" (str (if event then "event" else "onset"))
          |> put "state_assignment" (str (if event then "event" else "level")) in
      if event then put "ongoing_duration" (str "explicit") attrs else attrs
  | _ -> node.attrs

let policies request nodes =
  match Build_request.behavior_profile request with
  | Build_request.V1 -> Behavior.execution_policies Behavior.V0_1
  | Build_request.V2 ->
      let specification = Option.value ~default:(Json.Object [])
          (List.assoc_opt "execution" (Build_request.implementation_constraints request)) in
      let fields = match specification with Json.Object value -> value
        | _ -> fail "invalid_lowering_execution_policy" "Frozen execution policy must be an object." in
      require (List.for_all (fun (key, _) -> key = "integral_step") fields)
        "invalid_lowering_execution_policy" "Frozen execution policy contains unknown fields.";
      let raw_step = Option.value ~default:Json.Null (List.assoc_opt "integral_step" fields) in
      (match List.find_opt (fun node -> node.kind = "integrated") nodes with
       | Some node when raw_step = Json.Null ->
           error node "unsupported_lowering_integral_step" "Integration requires explicit execution.integral_step authority."
       | _ -> ());
      let integral_step = match raw_step with
        | Json.Null -> Json.Null
        | value ->
            let duration = Type_spec.of_json (Json.Object ["kind", str "scalar"; "name", str "Duration";
                "dimensions", Json.Object ["time", Json.int 1]; "arguments", Json.Array []]) in
            let normalized = Type_spec.normalize_binding ~expected:duration value in
            require (Json.number_compare (field "canonical_value" normalized) (Json.int 0) > 0)
              "invalid_lowering_execution_policy" "Integral sampling step must be positive.";
            normalized in
      Behavior.execution_policies ~integral_step Behavior.V0_2

let dependencies node = match node.role with None -> node.inputs | Some role -> role :: node.inputs
let derive map nodes =
  let pending = ref (List.map (fun node -> node.id, false) nodes) and seen = ref Ids.empty in
  let ancestry = ref Names.empty and contacts = ref Names.empty and constants = ref Names.empty in
  let retained = ref 0 in
  while !pending <> [] do
    let identity, closing = List.hd !pending in pending := List.tl !pending;
    let node = lookup map identity in
    if closing then (
      let lineage = List.fold_left (fun result reference -> Ids.union result (Names.find reference !ancestry))
          (Ids.singleton identity) (dependencies node) in
      retained := !retained + Ids.cardinal lineage;
      require (!retained <= Limits.max_json_nodes) "lowering_lineage_limit" "Complete retained source ancestry exceeds the JSON budget.";
      ancestry := Names.add identity lineage !ancestry;
      let contact = match node.kind with
        | "scope" -> attribute node "scope" = str "contact"
        | "role" | "state" | "state.is" | "memory" | "memory.is_set" | "literal" | "parameter"
        | "secretion" | "action.state_set" -> false
        | "signature" -> Names.find (input node 0) !contacts
        | _ -> List.exists (fun reference -> Names.find reference !contacts) node.inputs in
      contacts := Names.add identity contact !contacts;
      let constant = match node.kind with
        | "literal" | "parameter" -> true
        | "negate" ->
            if List.length node.inputs <> 1 then error node "invalid_lowering_source" "Negation requires one input.";
            Names.find (input node 0) !constants
        | "add" | "subtract" | "multiply" | "divide" ->
            if List.length node.inputs <> 2 then error node "invalid_lowering_source" "Arithmetic requires two inputs.";
            List.for_all (fun reference -> Names.find reference !constants) node.inputs
        | _ -> false in
      constants := Names.add identity constant !constants)
    else if not (Ids.mem identity !seen) then (
      seen := Ids.add identity !seen;
      pending := List.map (fun reference -> reference, false) (dependencies node) @ ((identity, true) :: !pending))
  done;
  !ancestry, !contacts, !constants

let constant_durations constants nodes =
  List.iter (fun node ->
      let reference = match node.kind, node.inputs with
        | ("held_for" | "recently" | "action.pulse" | "integrated"), [_; duration] -> Some duration
        | "followed_by", [_; _; duration] -> Some duration
        | "memory", inputs ->
            let names = Json.array (attribute node "input_names") |> List.map Json.string in
            let rec duration index = function
              | [] -> None
              | "duration" :: _ -> (match List.nth_opt inputs index with Some value -> Some value
                    | None -> error node "invalid_lowering_source" "Memory duration has no matching input.")
              | _ :: remaining -> duration (index + 1) remaining in
            duration 0 names
        | _ -> None in
      Option.iter (fun reference -> if not (Names.find reference constants) then
          error node "unsupported_lowering_dynamic_duration" "A temporal duration must be a bound design-time constant.") reference) nodes

let bound_document value =
  (* Count keys too at this native construction boundary. All ancestry and
     membership expansion is already cumulatively bounded before construction. *)
  let pending = ref [value, 0] and count = ref 0 in
  while !pending <> [] do
    let value, depth = List.hd !pending in pending := List.tl !pending;
    incr count;
    require (!count <= Limits.max_json_nodes && depth <= Limits.max_depth)
      "lowering_output_limit" "Complete lowered document exceeds the JSON value/depth budget.";
    (match value with
     | Json.Array values -> pending := List.map (fun value -> value, depth + 1) values @ !pending
     | Json.Object fields ->
         require (List.length fields <= Limits.max_json_nodes - !count)
           "lowering_output_limit" "Complete lowered document exceeds the JSON key/value budget.";
         List.iter (fun (key, _) -> require (String.length key <= Limits.max_string_bytes)
             "lowering_output_limit" "Lowered object key exceeds the wire string budget.") fields;
         count := !count + List.length fields;
         pending := List.map (fun (_, value) -> value, depth + 1) fields @ !pending
     | Json.String value ->
         require (String.length value <= Limits.max_string_bytes)
           "lowering_output_limit" "Lowered string exceeds the wire string budget."
     | _ -> ())
  done;
  ignore (Canonical.encode value)

let lower request =
  let original = Build_request.intent request in
  let source = Intent.to_json original in
  let nodes = Json.array (field "nodes" source) |> List.map read_node in
  require (7 + 3 * List.length nodes <= (Limits.max_json_nodes - 256) / 4)
    "lowering_report_limit" "Independent complete preservation report would exceed its JSON budget.";
  let map = List.fold_left (fun result node -> Names.add node.id node result) Names.empty nodes in
  profile_sources (Build_request.behavior_profile request) map nodes;
  let bindings = Build_request.resolved_bindings request in
  let by_name = List.fold_left (fun map (name, value) -> Names.add name value map) Names.empty bindings in
  let normalized = List.map (fun node -> { node with attrs = rewritten by_name node }) nodes in
  let normalized_map = List.fold_left (fun result node -> Names.add node.id node result) Names.empty normalized in
  let ancestry, contacts, constants = derive normalized_map normalized in
  constant_durations constants normalized;
  let requirements = List.filter (fun node -> List.mem node.kind ["rule"; "state"; "memory"]) nodes in
  let memberships = Hashtbl.create (List.length nodes) in
  (* Insert reversed, then reverse each membership once to preserve declaration
     order without a quadratic scan over all nodes and all requirements. *)
  List.iter (fun node ->
      Ids.iter (fun ancestor ->
          let old = Option.value ~default:[] (Hashtbl.find_opt memberships ancestor) in
          Hashtbl.replace memberships ancestor (("requirement:" ^ node.id) :: old))
        (Names.find node.id ancestry)) requirements;
  let emitted = List.map (fun node ->
      let memberships = Option.value ~default:[] (Hashtbl.find_opt memberships node.id) |> List.rev in
      Json.Object ["id", str node.id; "kind", str node.kind; "inputs", strings node.inputs;
        "attributes", Json.Object node.attrs; "data_type", node.dtype;
        "role", (match node.role with None -> Json.Null | Some role -> str role);
        "source", node.source; "contact_bound", Json.Bool (Names.find node.id contacts);
        "requirement_ids", strings memberships]) normalized in
  let requirements = List.map (fun node -> Json.Object [
      "id", str ("requirement:" ^ node.id); "kind", str node.kind; "source_node_id", str node.id;
      "lineage", strings (Ids.elements (Names.find node.id ancestry)); "source", node.source]) requirements in
  let profile = match Build_request.behavior_profile request with
    | Build_request.V1 -> Behavior.V0_1 | Build_request.V2 -> Behavior.V0_2 in
  let document = Json.Object [
      "schema_version", str (Behavior.schema_version profile); "name", field "name" source;
      "nodes", Json.Array emitted; "roots", field "roots" source; "source_fingerprint", str (Intent.fingerprint original);
      "requirements", Json.Array requirements;
      "source_links", Json.Object (Names.bindings ancestry |> List.map (fun (identity, values) -> identity, strings (Ids.elements values)));
      "policies", policies request nodes; "parameter_bindings", Json.Object bindings] in
  bound_document document;
  let behavior = Behavior.of_json document in
  ignore (Bioc_checker.Lowering_check.check ~expected_request:request ~behavior);
  behavior
