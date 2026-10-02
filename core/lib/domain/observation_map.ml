open Bioc_wire
type field = Value | Present | High | Low
let field_name = function Value -> "value" | Present -> "present" | High -> "high" | Low -> "low"
let resource_profile = "biocompiler.observation_map.resources.v1"
let str value = Json.String value
let limit ?path condition = Diagnostic.require ?path condition "observation_map_limit"
    "Observation map exceeds its native resource boundary."
let preflight ?(path = "") value =
  try Measurement_contract.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" -> limit ~path false
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "observation_map_cycle" "Cyclic observation map."
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let checked_fields ~path keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in Json.exact_fields ~path keys fields; fields
let name path key fields = Json.name ~path:(path ^ "/" ^ key) (get path key fields)

module Input_binding = struct
  type t = { json : Json.t; size : int; signal_id : string; field : field; mechanism_input_id : string }
  let of_json ?(path = "") value =
    let fields = checked_fields ~path ["signal_id"; "field"; "mechanism_input_id"] value in
    let signal_id = name path "signal_id" fields and mechanism_input_id = name path "mechanism_input_id" fields in
    let field = match Json.string ~path:(path ^ "/field") (get path "field" fields) with
      | "value" -> Value | "present" -> Present | "high" -> High | "low" -> Low
      | _ -> Diagnostic.fail ~path "invalid_observation_map" "Unknown observation field." in
    {json = value; size = String.length (Canonical.encode value); signal_id; field; mechanism_input_id}
  let make ~signal_id ~field ~mechanism_input_id = of_json (Json.Object [
      "signal_id",str signal_id; "field",str (field_name field); "mechanism_input_id",str mechanism_input_id])
  let to_json value = value.json
  let signal_id value = value.signal_id
  let field value = value.field
  let field_name value = field_name value.field
  let mechanism_input_id value = value.mechanism_input_id
  let size value = value.size
end
module Output_binding = struct
  type t = { json : Json.t; size : int; requirement_id : string; mechanism_output_id : string }
  let of_json ?(path = "") value =
    let fields = checked_fields ~path ["requirement_id"; "mechanism_output_id"] value in
    let requirement_id = name path "requirement_id" fields and mechanism_output_id = name path "mechanism_output_id" fields in
    {json = value; size = String.length (Canonical.encode value); requirement_id; mechanism_output_id}
  let make ~requirement_id ~mechanism_output_id = of_json (Json.Object [
      "requirement_id",str requirement_id; "mechanism_output_id",str mechanism_output_id])
  let to_json value = value.json
  let requirement_id value = value.requirement_id
  let mechanism_output_id value = value.mechanism_output_id
  let size value = value.size
end
type t = { json : Json.t; fingerprint : string; size : int; inputs : Input_binding.t list; outputs : Output_binding.t list }
let schema_version = "biocompiler.observation_map.v0.1"
let encode ~inputs ~outputs =
  let skeleton = Json.Object ["schema_version",str schema_version; "inputs",Json.Array []; "outputs",Json.Array []] in
  let bytes = ref (String.length (Canonical.encode skeleton)) and nodes = ref 4 in
  let array child_nodes size encode values =
    let rec loop first result = function
      | [] -> Json.Array (List.rev result)
      | value :: rest ->
          let amount = size value + (if first then 0 else 1) in
          limit (amount <= Limits.max_request_bytes - !bytes && child_nodes <= Limits.max_json_nodes - !nodes);
          bytes := !bytes + amount; nodes := !nodes + child_nodes;
          loop false (encode value :: result) rest in
    loop true [] values in
  let inputs = array 4 Input_binding.size Input_binding.to_json inputs in
  let outputs = array 3 Output_binding.size Output_binding.to_json outputs in
  Json.Object ["schema_version",str schema_version; "inputs",inputs; "outputs",outputs]
let of_json ?(path = "") value =
  let fields = checked_fields ~path ["schema_version"; "inputs"; "outputs"] value in
  Diagnostic.require ~path (Json.string (get path "schema_version" fields) = schema_version)
    "unsupported_schema" "Unsupported observation-map schema.";
  let inputs = Json.array (get path "inputs" fields) |> List.mapi
      (fun index -> Input_binding.of_json ~path:(path ^ "/inputs/" ^ string_of_int index)) in
  let outputs = Json.array (get path "outputs" fields) |> List.mapi
      (fun index -> Output_binding.of_json ~path:(path ^ "/outputs/" ^ string_of_int index)) in
  let json = encode ~inputs ~outputs in
  preflight ~path json;
  let canonical = Canonical.encode json in
  {json; fingerprint = Canonical.sha256 canonical; size = String.length canonical; inputs; outputs}
let make ~inputs ~outputs = of_json (encode ~inputs ~outputs)
let to_json value = value.json
let fingerprint value = value.fingerprint
let canonical_size value = value.size
let inputs value = value.inputs
let outputs value = value.outputs
