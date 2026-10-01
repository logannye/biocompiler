open Bioc_wire

type number = Behavior.number
type state_value = Behavior.state_value
type source_location = Behavior.source_location
let boundary_version = "biocompiler.native_execution_data.v0.1"
let require = Diagnostic.require
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let option_json encode = function None -> Json.Null | Some value -> encode value
let optional decode = function Json.Null -> None | value -> Some (decode value)

(* This preflight precedes all projection and encoding, including native
   constructors. Shared/repeated strings count on every occurrence. The byte
   counter is the exact compact canonical UTF-8 size, without first allocating
   the expanded serialized value. Container traversal stops at the first bound.
   JSON keys count as nodes as well as values at this native boundary. *)
let preflight ~path value =
  let nodes = ref 0 and bytes = ref 0 in
  let limit condition = require ~path condition "execution_data_limit" "Execution data exceeds its native resource limit." in
  let add amount = limit (amount <= Limits.max_response_bytes - !bytes); bytes := !bytes + amount in
  let node () = incr nodes; limit (!nodes <= Limits.max_json_nodes) in
  let quoted text =
    limit (String.length text <= Limits.max_string_bytes);
    add 2; add (String.length text);
    String.iter (function
      | '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | character when Char.code character < 32 -> add 5
      | _ -> ()) text;
    Json.validate_utf8 text
  in
  let rec visit depth value =
    limit (depth <= Limits.max_depth); node ();
    match value with
    | Json.Null -> add 4
    | Json.Bool value -> add (if value then 4 else 5)
    | Json.Int value ->
        (* A bit bound avoids allocating an unbounded decimal for native Z.t. *)
        limit (Z.numbits value <= 4 * Limits.max_number_chars);
        let text = Z.to_string value in
        limit (String.length text <= Limits.max_number_chars); add (String.length text)
    | Json.Float value ->
        require ~path (Float.is_finite value) "nonfinite_number" "Execution data contains a nonfinite number.";
        add (String.length (Canonical.float_string value))
    | Json.String value -> quoted value
    | Json.Array values ->
        add 2;
        let first = ref true in
        List.iter (fun value -> if !first then first := false else add 1; visit (depth + 1) value) values
    | Json.Object fields ->
        add 2;
        let seen = Hashtbl.create 16 and first = ref true in
        List.iter (fun (key, value) ->
            node (); quoted key;
            require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate execution-data object key.";
            Hashtbl.add seen key ();
            if !first then first := false else add 1;
            add 1; visit (depth + 1) value) fields
  in
  visit 0 value

let record ~path keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path keys fields;
  fields
let field ~path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let named ~path value = Json.name ~path value
let text ~path value = Json.string ~path value
let number ~path value = Runtime_number.of_json ~path value
let number_json = Runtime_number.to_json
let time ~path value =
  let value = number ~path value in
  require ~path (Runtime_number.compare value Runtime_number.zero >= 0)
    "execution_data_time" "Execution timestamps must be nonnegative.";
  value
let source_json (value : source_location) =
  obj ["file", str value.file; "line", Json.Int value.line; "function", str value.function_name]
let source ~path value =
  let fields = record ~path ["file"; "line"; "function"] value in
  let line = Json.integer ~path:(path ^ "/line") (field ~path "line" fields) in
  require ~path (Z.sign line > 0) "invalid_source" "Source line must be positive.";
  { Behavior.file = named ~path:(path ^ "/file") (field ~path "file" fields);
    line; function_name = named ~path:(path ^ "/function") (field ~path "function" fields) }
let names ~path value =
  Json.array ~path value |> List.mapi (fun index -> named ~path:(path ^ "/" ^ string_of_int index))
let names_json values = arr (List.map str values)
let state ~path = function
  | Json.String value -> Behavior.Text value
  | Json.Bool value -> Behavior.Boolean value
  | Json.Int value -> Behavior.State_integer value
  | Json.Float value when Float.is_finite value -> Behavior.State_real value
  | _ -> Diagnostic.fail ~path "execution_data_state" "Trace state must be a string, Boolean, integer or finite float."
let state_json = function
  | Behavior.Text value -> str value | Behavior.Boolean value -> Json.Bool value
  | Behavior.State_integer value -> Json.Int value | Behavior.State_real value -> Json.Float value
let mapping ~path decode value =
  Json.object_fields ~path value |> List.map (fun (key, value) ->
      ignore (named ~path (str key)); key, decode ~path:(path ^ "/" ^ key) value)
let items ~path decode value =
  Json.array ~path value |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index))
let fingerprint ~path value =
  let value = text ~path value in
  require ~path (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "execution_data_fingerprint" "Trace fingerprints must be lowercase SHA-256 hexadecimal.";
  value
let checked_list values =
  let rec count remaining = function
    | [] -> ()
    | _ :: rest ->
        require (remaining > 0) "execution_data_limit" "Execution-data collection exceeds the native node limit.";
        count (remaining - 1) rest
  in count Limits.max_json_nodes values; values
let mapped encode values = checked_list values |> List.map encode

module Sample = struct
  type t = { value : number option; present : bool option; high : bool option; low : bool option }
  let of_json ?(path = "") value =
    let fields = record ~path ["value"; "present"; "high"; "low"] value in
    let get name = field ~path name fields in
    let band name = optional (Json.boolean ~path:(path ^ "/" ^ name)) (get name) in
    { value = optional (number ~path:(path ^ "/value")) (get "value"); present = band "present"; high = band "high"; low = band "low" }
  let to_json value = obj ["value", option_json number_json value.value;
    "present", option_json (fun value -> Json.Bool value) value.present;
    "high", option_json (fun value -> Json.Bool value) value.high;
    "low", option_json (fun value -> Json.Bool value) value.low]
  let make ?value ?present ?high ?low () = of_json (to_json { value; present; high; low })
  let value value = value.value
  let present value = value.present
  let high value = value.high
  let low value = value.low
end

module Input_frame = struct
  type t = { time : number; signals : (string * Sample.t) list; contacts : (string * (string * Sample.t) list) list }
  let samples_json values = obj (mapped (fun (key, value) -> key, Sample.to_json value) values)
  let to_json value = obj ["time", number_json value.time; "signals", samples_json value.signals;
    "contacts", obj (mapped (fun (key, values) -> key, samples_json values) value.contacts)]
  let sample ~path = function
    | (Json.Int _ | Json.Float _) as value -> Sample.make ~value:(number ~path value) ()
    | value -> Sample.of_json ~path value
  let of_json ?(path = "") value =
    let fields = record ~path ["time"; "signals"; "contacts"] value in
    let parsed = { time = time ~path:(path ^ "/time") (field ~path "time" fields);
      signals = mapping ~path:(path ^ "/signals") sample (field ~path "signals" fields);
      contacts = mapping ~path:(path ^ "/contacts") (fun ~path -> mapping ~path sample) (field ~path "contacts" fields) } in
    preflight ~path (to_json parsed); parsed
  let make ~time ?(signals = []) ?(contacts = []) () = of_json (to_json { time; signals; contacts })
  let time value = value.time
  let signals value = value.signals
  let contacts value = value.contacts
end

module Action = struct
  type t = { json : Json.t; action_id : string; rule_id : string; kind : string; contact_id : string option;
    attributes : Json.t; values : Json.t; requirement_ids : string list; source : source_location option;
    rule_source : source_location option; started_at : number option; expires_at : number option;
    specification_id : string; specification_source : source_location option }
  let of_json ?(path = "") value =
    let fields = record ~path ["action_id"; "rule_id"; "kind"; "contact_id"; "attributes"; "values";
        "requirement_ids"; "source"; "rule_source"; "started_at"; "expires_at"; "specification_id"; "specification_source"] value in
    let get key = field ~path key fields in
    let name key = named ~path:(path ^ "/" ^ key) (get key) in
    let maybe decode key = optional (decode ~path:(path ^ "/" ^ key)) (get key) in
    let object_value key = let value = get key in ignore (Json.object_fields ~path:(path ^ "/" ^ key) value); value in
    let action_id = name "action_id" and source_value = maybe source "source" in
    (* Python ActionRequest.__post_init__ substitutes both specification fields
       only when specification_id is None; a supplied ID preserves null source. *)
    let declared_specification_source = maybe source "specification_source" in
    let specification_id, specification_source = match get "specification_id" with
      | Json.Null -> action_id, source_value
      | value -> named ~path:(path ^ "/specification_id") value, declared_specification_source
    in
    let json = obj (List.map (fun (key, value) -> key, match key with
        | "specification_id" -> str specification_id
        | "specification_source" -> option_json source_json specification_source
        | _ -> value) fields) in
    preflight ~path json;
    { json; action_id; rule_id = name "rule_id"; kind = name "kind"; contact_id = maybe named "contact_id";
      attributes = object_value "attributes"; values = object_value "values";
      requirement_ids = names ~path:(path ^ "/requirement_ids") (get "requirement_ids");
      source = source_value; rule_source = maybe source "rule_source";
      started_at = maybe time "started_at"; expires_at = maybe time "expires_at";
      specification_id; specification_source }
  let encode value = obj ["action_id", str value.action_id; "rule_id", str value.rule_id; "kind", str value.kind;
    "contact_id", option_json str value.contact_id; "attributes", value.attributes; "values", value.values;
    "requirement_ids", names_json value.requirement_ids; "source", option_json source_json value.source;
    "rule_source", option_json source_json value.rule_source; "started_at", option_json number_json value.started_at;
    "expires_at", option_json number_json value.expires_at; "specification_id", str value.specification_id;
    "specification_source", option_json source_json value.specification_source]
  let make ~action_id ~rule_id ~kind ?contact_id ~attributes ~values ~requirement_ids ?source ?rule_source
      ?started_at ?expires_at ?specification_id ?specification_source () =
    let specification_id, specification_source = match specification_id with
      | None -> action_id, source | Some value -> value, specification_source
    in
    ignore (checked_list requirement_ids);
    of_json (encode { json = Json.Null; action_id; rule_id; kind; contact_id; attributes; values; requirement_ids; source;
      rule_source; started_at; expires_at; specification_id; specification_source })
  let to_json value = value.json
  let action_id value = value.action_id
  let rule_id value = value.rule_id
  let kind value = value.kind
  let contact_id value = value.contact_id
  let attributes value = value.attributes
  let values value = value.values
  let requirement_ids value = value.requirement_ids
  let source value = value.source
  let rule_source value = value.rule_source
  let started_at value = value.started_at
  let expires_at value = value.expires_at
  let specification_id value = value.specification_id
  let specification_source value = value.specification_source
end

module Event = struct
  type t = { json : Json.t; node_id : string; contact_id : string option; requirement_ids : string list; source : source_location option }
  let of_json ?(path = "") value =
    let fields = record ~path ["node_id"; "contact_id"; "requirement_ids"; "source"] value in
    { json = value; node_id = named ~path:(path ^ "/node_id") (field ~path "node_id" fields);
      contact_id = optional (named ~path:(path ^ "/contact_id")) (field ~path "contact_id" fields);
      requirement_ids = names ~path:(path ^ "/requirement_ids") (field ~path "requirement_ids" fields);
      source = optional (source ~path:(path ^ "/source")) (field ~path "source" fields) }
  let encode value = obj ["node_id", str value.node_id; "contact_id", option_json str value.contact_id;
    "requirement_ids", names_json value.requirement_ids; "source", option_json source_json value.source]
  let make ~node_id ?contact_id ~requirement_ids ?source () =
    ignore (checked_list requirement_ids); of_json (encode { json = Json.Null; node_id; contact_id; requirement_ids; source })
  let to_json value = value.json
  let node_id value = value.node_id
  let contact_id value = value.contact_id
  let requirement_ids value = value.requirement_ids
  let source value = value.source
end

module Frame = struct
  type t = { json : Json.t; time : number; actions : Action.t list; reactions : Action.t list; events : Event.t list;
    states : (string * state_value) list; memories : (string * bool) list; microsteps : int }
  let of_json ?(path = "") value =
    let fields = record ~path ["time"; "actions"; "reactions"; "events"; "states"; "memories"; "microsteps"] value in
    let get key = field ~path key fields in
    let microsteps = Json.integer ~path:(path ^ "/microsteps") (get "microsteps") in
    require ~path (Z.sign microsteps > 0 && Z.fits_int microsteps) "execution_data_microsteps" "Trace microsteps must be a positive machine integer.";
    let actions = items ~path:(path ^ "/actions") (fun ~path -> Action.of_json ~path) (get "actions")
    and reactions = items ~path:(path ^ "/reactions") (fun ~path -> Action.of_json ~path) (get "reactions") in
    let json = obj (List.map (fun (key, value) -> key, match key with
        | "actions" -> arr (List.map Action.to_json actions)
        | "reactions" -> arr (List.map Action.to_json reactions)
        | _ -> value) fields) in
    preflight ~path json;
    { json; time = time ~path:(path ^ "/time") (get "time");
      actions; reactions;
      events = items ~path:(path ^ "/events") (fun ~path -> Event.of_json ~path) (get "events");
      states = mapping ~path:(path ^ "/states") state (get "states");
      memories = mapping ~path:(path ^ "/memories") (fun ~path -> Json.boolean ~path) (get "memories");
      microsteps = Z.to_int microsteps }
  let encode value = obj ["time", number_json value.time; "actions", arr (mapped Action.to_json value.actions);
    "reactions", arr (mapped Action.to_json value.reactions); "events", arr (mapped Event.to_json value.events);
    "states", obj (mapped (fun (key, value) -> key, state_json value) value.states);
    "memories", obj (mapped (fun (key, value) -> key, Json.Bool value) value.memories); "microsteps", Json.int value.microsteps]
  let make ~time ~actions ~reactions ~events ~states ~memories ~microsteps =
    of_json (encode { json = Json.Null; time; actions; reactions; events; states; memories; microsteps })
  let to_json value = value.json
  let time value = value.time
  let actions value = value.actions
  let reactions value = value.reactions
  let events value = value.events
  let states value = value.states
  let memories value = value.memories
  let microsteps value = value.microsteps
end

module Result = struct
  type t = { json : Json.t; frames : Frame.t list; role : string; horizon : number; behavior_fingerprint : string;
    source_fingerprint : string; execution_profile : string }
  let of_json ?(path = "") value =
    let fields = record ~path ["role"; "horizon"; "behavior_fingerprint"; "source_fingerprint"; "execution_profile"; "frames"] value in
    let get key = field ~path key fields in
    let frames = items ~path:(path ^ "/frames") (fun ~path -> Frame.of_json ~path) (get "frames") in
    let json = obj (List.map (fun (key, value) -> key, if key = "frames" then arr (List.map Frame.to_json frames) else value) fields) in
    preflight ~path json;
    { json; frames;
      role = named ~path:(path ^ "/role") (get "role"); horizon = time ~path:(path ^ "/horizon") (get "horizon");
      behavior_fingerprint = fingerprint ~path:(path ^ "/behavior_fingerprint") (get "behavior_fingerprint");
      source_fingerprint = fingerprint ~path:(path ^ "/source_fingerprint") (get "source_fingerprint");
      execution_profile = named ~path:(path ^ "/execution_profile") (get "execution_profile") }
  let encode value = obj ["role", str value.role; "horizon", number_json value.horizon;
    "behavior_fingerprint", str value.behavior_fingerprint; "source_fingerprint", str value.source_fingerprint;
    "execution_profile", str value.execution_profile; "frames", arr (mapped Frame.to_json value.frames)]
  let make ~frames ~role ~horizon ~behavior_fingerprint ~source_fingerprint ~execution_profile =
    of_json (encode { json = Json.Null; frames; role; horizon; behavior_fingerprint; source_fingerprint; execution_profile })
  let to_json value = value.json
  let frames value = value.frames
  let role value = value.role
  let horizon value = value.horizon
  let behavior_fingerprint value = value.behavior_fingerprint
  let source_fingerprint value = value.source_fingerprint
  let execution_profile value = value.execution_profile
end
