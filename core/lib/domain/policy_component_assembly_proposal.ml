open Bioc_wire
module A = Policy_component_assembly_rule
module M = Molecular_record
module P = Pinned_identity
let schema_version = "biocompiler.policy_component_assembly_proposal.v0.1"
let profile = A.profile
let instance_schema_version = "biocompiler.policy_component_assembly_proposal.v0.2"
let instance_profile = A.instance_profile
let multi_member_schema_version = "biocompiler.policy_component_assembly_proposal.v0.3"
let multi_member_profile = A.multi_member_profile
let grounded_helper_schema_version = "biocompiler.policy_component_assembly_proposal.v0.4"
let grounded_helper_profile = A.grounded_helper_profile
let multi_site_schema_version = "biocompiler.policy_component_assembly_proposal.v0.5"
let multi_site_profile = A.multi_site_profile
type node_binding = { slot:A.slot; node_id:string; actual_id:string }
type t = { multi_site:bool; instanced:bool; multi_member:bool; grounded_helper:bool; rule_value:P.t; node_values:node_binding list }
let require condition message = Diagnostic.require condition "policy_component_assembly_proposal" message
let name raw = let value = Json.name raw in
  require (String.length value <= 128) "Assembly proposal name exceeds its byte bound."; value
let to_json value = Json.Object ["schema_version",Json.String (if value.multi_site then multi_site_schema_version else if value.grounded_helper then grounded_helper_schema_version else if value.multi_member then multi_member_schema_version else if value.instanced then instance_schema_version else schema_version);
  "profile",Json.String (if value.multi_site then multi_site_profile else if value.grounded_helper then grounded_helper_profile else if value.multi_member then multi_member_profile else if value.instanced then instance_profile else profile); "rule",P.to_json value.rule_value;
  "nodes",Json.Array (List.map (fun (row:node_binding) -> Json.Object [
    "slot",Json.String (A.slot_name row.slot); "node",Json.String row.node_id;
    "actual",Json.String row.actual_id]) value.node_values)]
let of_json raw =
  M.check_resources raw;
  let fields = Json.object_fields raw in
  Json.exact_fields ["schema_version";"profile";"rule";"nodes"] fields;
  let multi_site=Json.string (Json.field "profile" fields)=multi_site_profile in
  let grounded_helper=Json.string (Json.field "profile" fields)=grounded_helper_profile in
  let multi_member=grounded_helper || Json.string (Json.field "profile" fields)=multi_member_profile in
  let instanced=multi_site || multi_member || Json.string (Json.field "profile" fields)=instance_profile in
  require ((multi_site && Json.string (Json.field "schema_version" fields)=multi_site_schema_version) ||
    (grounded_helper && Json.string (Json.field "schema_version" fields)=grounded_helper_schema_version) ||
    (multi_member && not grounded_helper && Json.string (Json.field "schema_version" fields)=multi_member_schema_version) ||
    (instanced && not multi_member && not multi_site && Json.string (Json.field "schema_version" fields)=instance_schema_version) ||
    (not instanced && Json.string (Json.field "schema_version" fields)=schema_version &&
      Json.string (Json.field "profile" fields)=profile)) "Unsupported assembly proposal schema or profile.";
  let rule_value = P.of_json (Json.field "rule" fields) in
  require (P.kind rule_value = P.Model) "Assembly proposal must name a complete original rule Model pin.";
  let node_values = List.map (fun raw ->
    let fields = Json.object_fields raw in Json.exact_fields ["slot";"node";"actual"] fields;
    let slot = if instanced then A.slot_of_json ~instanced (Json.field "slot" fields)
      else match Json.string (Json.field "slot" fields) with
        | "decision" -> A.Decision | "driver" -> A.Driver
        | _ -> Diagnostic.fail "policy_component_assembly_proposal" "Unknown assembly proposal slot." in
    {slot;node_id=name (Json.field "node" fields);actual_id=name (Json.field "actual" fields)})
    (M.array ~maximum:256 (Json.field "nodes" fields)) in
  let value = {multi_site;instanced;multi_member;grounded_helper;rule_value;node_values} in
  require (Json.equal raw (to_json value)) "Assembly proposal must retain its complete supplied spelling.";
  value
let fingerprint value = Canonical.fingerprint (to_json value)
let rule value = value.rule_value
let nodes value = value.node_values
let is_multi_site value = value.multi_site
let is_instanced value = value.instanced

let is_multi_member value = value.multi_member

let is_grounded_helper value = value.grounded_helper
