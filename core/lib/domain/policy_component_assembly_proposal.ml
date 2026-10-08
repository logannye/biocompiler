open Bioc_wire
module A = Policy_component_assembly_rule
module M = Molecular_record
module P = Pinned_identity
let schema_version = "biocompiler.policy_component_assembly_proposal.v0.1"
let profile = A.profile
type node_binding = { slot:A.slot; node_id:string; actual_id:string }
type t = { rule_value:P.t; node_values:node_binding list }
let require condition message = Diagnostic.require condition "policy_component_assembly_proposal" message
let name raw = let value = Json.name raw in
  require (String.length value <= 128) "Assembly proposal name exceeds its byte bound."; value
let slot_name = function A.Decision -> "decision" | A.Driver -> "driver"
let to_json value = Json.Object ["schema_version",Json.String schema_version;
  "profile",Json.String profile; "rule",P.to_json value.rule_value;
  "nodes",Json.Array (List.map (fun (row:node_binding) -> Json.Object [
    "slot",Json.String (slot_name row.slot); "node",Json.String row.node_id;
    "actual",Json.String row.actual_id]) value.node_values)]
let of_json raw =
  M.check_resources raw;
  let fields = Json.object_fields raw in
  Json.exact_fields ["schema_version";"profile";"rule";"nodes"] fields;
  require (Json.string (Json.field "schema_version" fields) = schema_version &&
    Json.string (Json.field "profile" fields) = profile) "Unsupported assembly proposal schema or profile.";
  let rule_value = P.of_json (Json.field "rule" fields) in
  require (P.kind rule_value = P.Model) "Assembly proposal must name a complete original rule Model pin.";
  let node_values = List.map (fun raw ->
    let fields = Json.object_fields raw in Json.exact_fields ["slot";"node";"actual"] fields;
    let slot = match Json.string (Json.field "slot" fields) with
      | "decision" -> A.Decision | "driver" -> A.Driver
      | _ -> Diagnostic.fail "policy_component_assembly_proposal" "Unknown assembly proposal slot." in
    {slot;node_id=name (Json.field "node" fields);actual_id=name (Json.field "actual" fields)})
    (M.array ~maximum:256 (Json.field "nodes" fields)) in
  let value = {rule_value;node_values} in
  require (Json.equal raw (to_json value)) "Assembly proposal must retain its complete supplied spelling.";
  value
let fingerprint value = Canonical.fingerprint (to_json value)
let rule value = value.rule_value
let nodes value = value.node_values
