open Bioc_wire
let schema_version = "biocompiler.source_execution_manifest.v0.1"
let claim_scope = "exact_declared_source_execution_no_empirical_function"
let boundary_version = "biocompiler.native_source_manifest.v0.1"
let max_source_nodes = 1024
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let require ?path condition message = Diagnostic.require ?path condition "invalid_source_manifest" message

(* This is a native transport bound, not an extra source semantic predicate.
   Count keys and every repeated child occurrence before canonical allocation. *)
type budget = { mutable nodes : int; mutable bytes : int }
let budget () = { nodes = 0; bytes = 0 }
let preflight ?(path = "") ?budget:shared value =
  let budget = match shared with None -> budget () | Some budget -> budget in
  let limit condition = Diagnostic.require ~path condition "source_manifest_limit" "Source manifest exceeds its native resource contract." in
  let add amount = limit (amount <= Limits.max_response_bytes - budget.bytes); budget.bytes <- budget.bytes + amount in
  let node () = budget.nodes <- budget.nodes + 1; limit (budget.nodes <= Limits.max_json_nodes) in
  let quoted text =
    limit (String.length text <= Limits.max_string_bytes);
    add 2; add (String.length text);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | c when Char.code c < 32 -> add 5 | _ -> ()) text;
    Json.validate_utf8 text in
  let rec visit depth value =
    limit (depth <= Limits.max_depth); node ();
    match value with
    | Json.Null -> add 4 | Json.Bool value -> add (if value then 4 else 5)
    | Json.Int value ->
        limit (Z.numbits value <= 4 * Limits.max_number_chars);
        let text = Z.to_string value in limit (String.length text <= Limits.max_number_chars); add (String.length text)
    | Json.Float value ->
        Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Source manifest numbers must be finite.";
        add (String.length (Canonical.float_string value))
    | Json.String value -> quoted value
    | Json.Array values ->
        add 2; let first = ref true in
        List.iter (fun value -> if !first then first := false else add 1; visit (depth + 1) value) values
    | Json.Object fields ->
        add 2; let seen = Hashtbl.create 16 and first = ref true in
        List.iter (fun (key, value) -> node (); quoted key;
            Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate source manifest key.";
            Hashtbl.add seen key (); if !first then first := false else add 1;
            add 1; visit (depth + 1) value) fields in
  visit 0 value
type resource_budget = budget
let create_resource_budget = budget
let reserve_json budget value = preflight ~budget value
let bounded_length ~path ~maximum values =
  let rec loop count = function [] -> () | _ :: rest ->
    require ~path (count < maximum) "Source manifest inventory limit exceeded."; loop (count + 1) rest in
  loop 0 values
let array ~path ~maximum value = let values = Json.array ~path value in bounded_length ~path ~maximum values; values
let record ~path keys raw = preflight ~path raw; let fields = Json.object_fields ~path raw in Json.exact_fields ~path keys fields; fields
let text ~path ~nonempty raw =
  let value = Json.string ~path raw in require ~path (not nonempty || value <> "") "Source manifest text must be nonempty."; value
let texts ~path ~maximum ~nonempty raw = array ~path ~maximum raw |> List.map (text ~path ~nonempty)
let strings values = arr (List.map str values)
let choose ~path options raw = match List.assoc_opt (Json.string ~path raw) options with
  | Some value -> value | None -> Diagnostic.fail ~path "invalid_source_manifest" "Unsupported source manifest declaration."
let fingerprint encode value = Canonical.fingerprint (encode value)
let mapped ~maximum encode values =
  bounded_length ~path:"" ~maximum values;
  let reservation = budget () in
  arr (List.map (fun value -> let raw = encode value in preflight ~budget:reservation raw; raw) values)

module Diagnostic_record = struct
  type category = Unsupported_semantics | Missing_refinement | Contradiction
  type t = { code : string; category : category; source_node_ids : string list; message : string }
  let category_name = function Unsupported_semantics -> "unsupported_semantics" | Missing_refinement -> "missing_refinement" | Contradiction -> "contradiction"
  let to_json value =
    bounded_length ~path:"/source_node_ids" ~maximum:max_source_nodes value.source_node_ids;
    obj ["code", str value.code; "category", str (category_name value.category); "source_node_ids", strings value.source_node_ids; "message", str value.message]
  let of_json ?(path = "") raw =
    let fields = record ~path ["code"; "category"; "source_node_ids"; "message"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let value = { code = text ~path:(path ^ "/code") ~nonempty:true (get "code");
      category = choose ~path:(path ^ "/category") ["unsupported_semantics", Unsupported_semantics; "missing_refinement", Missing_refinement; "contradiction", Contradiction] (get "category");
      source_node_ids = texts ~path:(path ^ "/source_node_ids") ~maximum:max_source_nodes ~nonempty:true (get "source_node_ids");
      message = text ~path:(path ^ "/message") ~nonempty:true (get "message") } in
    preflight ~path (to_json value); value
  let make ~code ~category ~source_node_ids ~message = of_json (to_json {code; category; source_node_ids; message})
  let fingerprint = fingerprint to_json
  let code value = value.code
  let category value = value.category
  let source_node_ids value = value.source_node_ids
  let message value = value.message
end

module Output = struct
  type trigger = Condition | Event
  type activation = Level | Event_activation | Onset | Explicit_duration
  type t = { id : string; rule_id : string; action_id : string; guard_id : string; role_id : string;
    action_kind : string; lineage : string list; trigger : trigger; activation : activation;
    product : string option; semantics : Json.t }
  let trigger_name = function Condition -> "condition" | Event -> "event"
  let activation_name = function Level -> "level" | Event_activation -> "event" | Onset -> "onset" | Explicit_duration -> "explicit_duration"
  let to_json value =
    bounded_length ~path:"/lineage" ~maximum:Limits.max_json_nodes value.lineage;
    obj ["id", str value.id; "rule_id", str value.rule_id; "action_id", str value.action_id;
      "guard_id", str value.guard_id; "role_id", str value.role_id; "action_kind", str value.action_kind;
      "lineage", strings value.lineage; "trigger", str (trigger_name value.trigger); "activation", str (activation_name value.activation);
      "product", (match value.product with None -> Json.Null | Some value -> str value); "semantics", value.semantics]
  let of_json ?(path = "") raw =
    let fields = record ~path ["id"; "rule_id"; "action_id"; "guard_id"; "role_id"; "action_kind"; "lineage"; "trigger"; "activation"; "product"; "semantics"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let name key = text ~path:(path ^ "/" ^ key) ~nonempty:true (get key) in
    let semantics = get "semantics" in ignore (Json.object_fields ~path:(path ^ "/semantics") semantics);
    let value = { id = name "id"; rule_id = name "rule_id"; action_id = name "action_id"; guard_id = name "guard_id"; role_id = name "role_id"; action_kind = name "action_kind";
      lineage = texts ~path:(path ^ "/lineage") ~maximum:Limits.max_json_nodes ~nonempty:false (get "lineage");
      trigger = choose ~path:(path ^ "/trigger") ["condition", Condition; "event", Event] (get "trigger");
      activation = choose ~path:(path ^ "/activation") ["level", Level; "event", Event_activation; "onset", Onset; "explicit_duration", Explicit_duration] (get "activation");
      product = (match get "product" with Json.Null -> None | raw -> Some (text ~path:(path ^ "/product") ~nonempty:false raw)); semantics } in
    preflight ~path (to_json value); value
  let make ~id ~rule_id ~action_id ~guard_id ~role_id ~action_kind ~lineage ~trigger ~activation ~product ~semantics =
    of_json (to_json {id; rule_id; action_id; guard_id; role_id; action_kind; lineage; trigger; activation; product; semantics})
  let fingerprint = fingerprint to_json
  let id value = value.id
  let rule_id value = value.rule_id
  let action_id value = value.action_id
  let guard_id value = value.guard_id
  let role_id value = value.role_id
  let action_kind value = value.action_kind
  let lineage value = value.lineage
  let trigger value = value.trigger
  let activation value = value.activation
  let product value = value.product
  let semantics value = value.semantics
end

type t = { source : Human_request.t; behavior : Behavior.t option; roles : string list;
  outputs : Output.t list; ledger : Json.t list; role_nodes : Json.t; states : Json.t list;
  channels : Json.t list; diagnostics : Diagnostic_record.t list }
let to_json value =
  bounded_length ~path:"/roles" ~maximum:max_source_nodes value.roles;
  obj ["schema_version", str schema_version; "claim_scope", str claim_scope;
    "source", Human_request.to_json value.source;
    "behavior", (match value.behavior with None -> Json.Null | Some behavior -> Behavior.to_json behavior);
    "roles", strings value.roles; "outputs", mapped ~maximum:(4 * max_source_nodes) Output.to_json value.outputs;
    "ledger", mapped ~maximum:(max_source_nodes + 1) Fun.id value.ledger; "role_nodes", value.role_nodes;
    "states", mapped ~maximum:(max_source_nodes + 1) Fun.id value.states;
    "channels", mapped ~maximum:(max_source_nodes + 1) Fun.id value.channels;
    "diagnostics", mapped ~maximum:(4 * max_source_nodes) Diagnostic_record.to_json value.diagnostics]
let of_json ?(path = "") raw =
  let fields = record ~path ["schema_version"; "claim_scope"; "source"; "behavior"; "roles"; "outputs"; "ledger"; "role_nodes"; "states"; "channels"; "diagnostics"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  Diagnostic.require ~path (Json.string (get "schema_version") = schema_version && Json.string (get "claim_scope") = claim_scope)
    "unsupported_schema" "Unsupported source execution manifest profile.";
  let mappings key = array ~path:(path ^ "/" ^ key) ~maximum:(max_source_nodes + 1) (get key)
    |> List.map (fun raw -> ignore (Json.object_fields ~path:(path ^ "/" ^ key) raw); raw) in
  let role_nodes = get "role_nodes" in ignore (Json.object_fields ~path:(path ^ "/role_nodes") role_nodes);
  let value = { source = Human_request.of_json (get "source");
    behavior = (match get "behavior" with Json.Null -> None | raw -> Some (Behavior.of_json raw));
    roles = texts ~path:(path ^ "/roles") ~maximum:max_source_nodes ~nonempty:false (get "roles");
    outputs = array ~path:(path ^ "/outputs") ~maximum:(4 * max_source_nodes) (get "outputs") |> List.mapi (fun i -> Output.of_json ~path:(path ^ "/outputs/" ^ string_of_int i));
    ledger = mappings "ledger"; role_nodes; states = mappings "states"; channels = mappings "channels";
    diagnostics = array ~path:(path ^ "/diagnostics") ~maximum:(4 * max_source_nodes) (get "diagnostics") |> List.mapi (fun i -> Diagnostic_record.of_json ~path:(path ^ "/diagnostics/" ^ string_of_int i)) } in
  preflight ~path (to_json value); value
let make ~source ~behavior ~roles ~outputs ~ledger ~role_nodes ~states ~channels ~diagnostics =
  of_json (to_json {source; behavior; roles; outputs; ledger; role_nodes; states; channels; diagnostics})
let fingerprint = fingerprint to_json
let source value = value.source
let behavior value = value.behavior
let roles value = value.roles
let outputs value = value.outputs
let ledger value = value.ledger
let role_nodes value = value.role_nodes
let states value = value.states
let channels value = value.channels
let diagnostics value = value.diagnostics
let build_request value = Human_request.build_request value.source
let source_fingerprint value = Human_request.fingerprint value.source
let complete value = Option.is_some value.behavior && value.diagnostics = []
