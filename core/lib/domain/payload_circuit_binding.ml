open Bioc_wire
module M = Molecular_record
type t = { requirement_id:string; rule_id:string; action_id:string; signals:(string * string) list }
let schema_version = "biocompiler.payload_circuit_binding.v0.1"
let max_signals = 256
let to_json value =
  ignore (M.bounded_length ~maximum:max_signals value.signals);
  Json.Object ["schema_version",Json.String schema_version;"requirement_id",Json.String value.requirement_id;
    "rule_id",Json.String value.rule_id;"action_id",Json.String value.action_id;
    "signals",Json.Object (List.map (fun (key,value) -> key,Json.String value) value.signals)]
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["requirement_id";"rule_id";"action_id";"signals"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let signals = Json.object_fields ~path:(path ^ "/signals") (get "signals") in
  Diagnostic.require ~path (List.length signals <= max_signals) "invalid_payload_circuit_binding" "Too many supplied signal correspondences.";
  let signals = List.map (fun (key,value) -> M.text ~path (Json.String key),M.text ~path value) signals
    |> List.sort (fun (left,_) (right,_) -> String.compare left right) in
  let value = {requirement_id=M.text ~path (get "requirement_id");rule_id=M.text ~path (get "rule_id");
    action_id=M.text ~path (get "action_id");signals} in
  M.check_resources ~path (to_json value); value
let make ~requirement_id ~rule_id ~action_id ~signals = of_json (to_json {requirement_id;rule_id;action_id;signals})
let fingerprint value = Canonical.fingerprint (to_json value)
let requirement_id value = value.requirement_id
let rule_id value = value.rule_id
let action_id value = value.action_id
let signals value = value.signals
