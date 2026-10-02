open Bioc_wire
module N = Runtime_number
type number = N.t
type value = Boolean of bool | Number of number
let boundary_version = "biocompiler.model_execution_data.resources.v1"
let limit ?path condition = Diagnostic.require ?path condition "model_data_limit" "Candidate execution data exceeds its native resource limit."
let bounded values =
  let rec loop count = function
    | [] -> values
    | _ :: rest -> limit (count < Limits.max_json_nodes); loop (count + 1) rest in
  loop 0 values

type visit = Enter of Json.t * int | Leave of Json.t
(* Count every occurrence, including shared subtrees, before expanded encoding.
   The node budget follows the wire convention: values count, keys consume bytes.
   Bounded prefix lengths also stop cyclic native list spines. *)
let measure ~path ~maximum value =
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount <= maximum - !bytes); bytes := !bytes + amount in
  let quoted text =
    limit ~path (String.length text <= Limits.max_string_bytes);
    add (String.length text + 2);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | character when Char.code character < 32 -> add 5 | _ -> ()) text;
    Json.validate_utf8 text in
  let length maximum values =
    let rec loop count = function [] -> count | _ :: rest -> limit ~path (count < maximum); loop (count + 1) rest in
    loop 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let item = List.hd !pending in pending := List.tl !pending;
    match item with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes;
        limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "model_data_cycle" "Cyclic candidate execution data.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
         | Json.Null -> add 4
         | Json.Bool value -> add (if value then 4 else 5)
         | Json.Int value ->
             limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
             let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
         | Json.Float value ->
             Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Candidate data contains a nonfinite number.";
             add (String.length (Canonical.float_string value))
         | Json.String value -> quoted value
         | Json.Array values ->
             let count = length (Limits.max_json_nodes - !nodes - !queued) values in
             add (2 + max 0 (count - 1)); enter values count
         | Json.Object fields ->
             let count = length (Limits.max_json_nodes - !nodes - !queued) fields in
             add (2 + count + max 0 (count - 1));
             let seen = Hashtbl.create 16 in
             List.iter (fun (key, _) -> quoted key;
                 Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate candidate data field.";
                 Hashtbl.add seen key ()) fields;
             enter (List.map snd fields) count)
  done;
  !bytes, !nodes

let number ~path ~label value =
  match N.of_json ~path value with
  | result -> result
  | exception Diagnostic.Error diagnostic when diagnostic.code = "evaluation_numeric_type" ->
      Diagnostic.fail ~path "model_numeric_type" (label ^ " must be a finite real number.")
  | exception Diagnostic.Error diagnostic when diagnostic.code = "evaluation_nonfinite" ->
      Diagnostic.fail ~path "model_nonfinite" (label ^ " must be finite.")
let number_json ~label value =
  let json = match value with N.Integer value -> Json.Int value | N.Real value -> Json.Float value in
  ignore (number ~path:"" ~label json); json
let value_of_json ?(path = "") = function
  | Json.Bool value -> Boolean value
  | value -> Number (number ~path ~label:"Signal value" value)
let value_to_json = function Boolean value -> Json.Bool value | Number value -> number_json ~label:"Signal value" value
let time ~path ~label value =
  let value = number ~path ~label value in
  Diagnostic.require ~path (N.compare value N.zero >= 0) "model_time" (label ^ " must be nonnegative."); value
let field path name fields = Json.field ~path:(path ^ "/" ^ name) name fields

(* Typed input constructors reserve the complete nested map before retaining each
   expanded child. Repeated references to large contact maps cannot bypass the
   cumulative boundary by individually fitting in a record. *)
let frame_json ~time ~values ~contacts =
  let bytes = ref 0 and nodes = ref 0 in
  let add byte_count node_count =
    limit (byte_count <= Limits.max_request_bytes - !bytes && node_count <= Limits.max_json_nodes - !nodes);
    bytes := !bytes + byte_count; nodes := !nodes + node_count in
  let reserve value = let byte_count, node_count = measure ~path:"" ~maximum:Limits.max_request_bytes value in
    add byte_count node_count; value in
  let key ~first name =
    let byte_count, _ = measure ~path:"" ~maximum:Limits.max_request_bytes (Json.String name) in
    add (byte_count + 1 + (if first then 0 else 1)) 0 in
  let mapping encode fields =
    add 2 1;
    Json.Object (List.mapi (fun index (name, value) -> key ~first:(index = 0) name; name, encode value) (bounded fields)) in
  add 2 1;
  key ~first:true "time";
  let timestamp = reserve (number_json ~label:"Model time" time) in
  key ~first:false "values";
  let values = mapping (fun value -> reserve (value_to_json value)) values in
  key ~first:false "contacts";
  let contacts = mapping (mapping (fun value -> reserve (value_to_json value))) contacts in
  Json.Object ["time", timestamp; "values", values; "contacts", contacts]

module Make_frame () = struct
  type t = { json : Json.t; size : int; time : number; values : (string * value) list;
             contacts : (string * (string * value) list) list }
  let of_json ?(path = "") value =
    let size, _ = measure ~path ~maximum:Limits.max_request_bytes value in
    let fields = Json.object_fields ~path value in
    Json.exact_fields ~path ["time"; "values"; "contacts"] fields;
    let time = time ~path:(path ^ "/time") ~label:"Model time" (field path "time" fields) in
    let mapping path decode value = Json.object_fields ~path value |> List.map (fun (key, value) ->
        ignore (Json.name ~path (Json.String key)); key, decode (path ^ "/" ^ key) value) in
    let values path value = mapping path (fun path -> value_of_json ~path) value in
    let values_value = values (path ^ "/values") (field path "values" fields) in
    let contacts = mapping (path ^ "/contacts") values (field path "contacts" fields) in
    {json = value; size; time; values = values_value; contacts}
  let make ~time ?(values = []) ?(contacts = []) () = of_json (frame_json ~time ~values ~contacts)
  let to_json value = value.json
  let canonical_size value = value.size
  let time value = value.time
  let values value = value.values
  let contacts value = value.contacts
end
module Input_frame = Make_frame ()
module Frame = Make_frame ()

module Trace = struct
  type t = { json : Json.t; frames : Frame.t list; horizon : number; program : string; fingerprint : string }
  let schema_version = "biocompiler.synthetic.trace.v0.1"
  let model_version = "biocompiler.synthetic.runner.v0.2"
  let require ~path condition message = Diagnostic.require ~path condition "invalid_model_trace" message
  let of_json ?(path = "") value =
    ignore (measure ~path ~maximum:Limits.max_response_bytes value);
    let fields = Json.object_fields ~path value in
    Json.exact_fields ~path ["schema_version"; "frames"; "horizon"; "program_fingerprint"; "model_version"] fields;
    let get key = field path key fields in
    Diagnostic.require ~path (Json.string (get "schema_version") = schema_version) "unsupported_schema" "Unsupported model trace schema.";
    let frames = Json.array ~path:(path ^ "/frames") (get "frames") |> List.mapi
        (fun index -> Frame.of_json ~path:(path ^ "/frames/" ^ string_of_int index)) in
    require ~path (frames <> []) "A model trace needs a nonempty frame array.";
    let horizon = time ~path:(path ^ "/horizon") ~label:"Model horizon" (get "horizon") in
    let first = List.hd frames in
    let last = List.fold_left (fun _ frame -> frame) first frames in
    require ~path (N.equal (Frame.time first) N.zero && N.equal (Frame.time last) horizon)
      "A model trace must start at zero and end at its nonnegative horizon.";
    let previous = ref None in
    List.iter (fun frame ->
        (match !previous with None -> () | Some time -> require ~path (N.compare time (Frame.time frame) < 0)
            "Model trace times must strictly increase.");
        previous := Some (Frame.time frame)) frames;
    let program = Json.string ~path:(path ^ "/program_fingerprint") (get "program_fingerprint") in
    require ~path (String.length program = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) program)
      "A model trace requires a SHA-256 program fingerprint.";
    require ~path (Json.string (get "model_version") = model_version) "Unsupported synthetic model runner version.";
    {json = value; frames; horizon; program; fingerprint = Canonical.fingerprint value}
  let make ~frames ~horizon ~program_fingerprint ?(model_version = model_version) () =
    of_json (Json.Object ["schema_version", Json.String schema_version;
        "frames", Json.Array (List.map Frame.to_json (bounded frames));
        "horizon", number_json ~label:"Model horizon" horizon;
        "program_fingerprint", Json.String program_fingerprint; "model_version", Json.String model_version])
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let frames value = value.frames
  let horizon value = value.horizon
  let program_fingerprint value = value.program
end
