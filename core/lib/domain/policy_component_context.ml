open Bioc_wire
module X = Policy_material_context
module A = Policy_component_assembly_rule
module C = Policy_component_material
module F = Policy_component_fragment
module I = Policy_implementation
module P = Pinned_identity
module M = Molecular_record
module AC = Architecture_contract
let schema_version = "biocompiler.policy_component_context.v0.1"
let profile = "biocompiler.policy_component_mrna.v0.1"
let instance_profile = "biocompiler.policy_instance_component_mrna.v0.1"
let instance_staged_profile = "biocompiler.policy_instance_staged_component_mrna.v0.1"
let prerequisite_profile = "biocompiler.policy_instance_prerequisite_mrna.v0.1"
let instance_union_profile = "biocompiler.policy_instance_ordered_union.v0.1"
let record_profile = "biocompiler.policy_component_complete_records.v0.1"
let staged_profile = "biocompiler.policy_staged_component_mrna.v0.1"
let staged_record_profile = "biocompiler.policy_staged_component_complete_records.v0.1"
let staged_record_shapes =
  let fields values=Json.Array (List.map (fun value -> Json.String value) values) in
  let base=Json.object_fields X.record_shapes in
  let extend key names=match List.assoc key base with Json.Array values -> Json.Array (values @ List.map (fun value -> Json.String value) names) | _ -> assert false in
  Json.Object (List.map (fun (key,value) -> key,match key with
    | "active_attempt_records" | "retained_correlation_records" -> extend key ["machine_bank"]
    | "control_event_records" -> extend key ["machine_bank";"source_state_index";"destination_state_index";"ordered_retained_attempt_ids"]
    | _ -> value) base @ [
    "machine_state_bits",fields ["machine_bank";"scope_slot_generation";"state_index"];
    "machine_correlation_records",fields ["machine_bank";"scope_slot_generation";"attempt_id"]])
let union_profile = "biocompiler.policy_component_ordered_union.v0.1"
let str value = Json.String value
let obj values = Json.Object values
let arr encode values = Json.Array (List.map encode values)
let get key raw = Json.field key (Json.object_fields raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
let require condition message = Diagnostic.require condition "policy_component_context" message
let slot_name = A.slot_name
let reference slot node = obj ["slot",str (slot_name slot);"node",str node]
let endpoint slot (value:I.endpoint) = obj ["slot",str (slot_name slot);"node",str value.node_id;"port",str value.port_id]
let ordered_union_json rule =
  let fragment slot = C.fragment (A.component rule slot) in
  let boundary (value:A.boundary_ref) = List.find (fun (port:F.boundary_port) -> port.boundary_id=value.boundary_id)
    (F.boundary_ports (fragment value.slot)) in
  let nodes = List.map (fun (row:A.node_ref) ->
    let node = List.find (fun (node:F.node) -> node.node_id=row.node_id) (F.nodes (fragment row.slot)) in
    obj ["slot",str (slot_name row.slot);"node",str row.node_id;
      "model",obj ["identity",P.to_json node.model.identity;"configuration_digest",str node.model.configuration_digest;
        "body",I.model_body_to_json node.model]]) (A.node_order rule) in
  let wires = List.map (function
    | A.Local_wire {slot;index} -> let wire = List.nth (F.wires (fragment slot)) index in
      obj ["producer",endpoint slot wire.producer;"consumer",endpoint slot wire.consumer]
    | A.Cross_link kind -> let link = List.find (fun (link:A.link) -> link.kind=kind) (A.links rule) in
      obj ["producer",endpoint link.producer.slot (boundary link.producer).endpoint;
        "consumer",endpoint link.consumer.slot (boundary link.consumer).endpoint]) (A.wire_order rule) in
  let inputs = List.map (fun (row:A.input_ref) ->
    let input = List.find (fun (input:F.external_slot) -> input.slot_id=row.external_slot) (F.external_slots (fragment row.slot)) in
    obj ["id",str row.input_id;"kind",str (match input.input_kind with I.Evidence_input -> "evidence" | I.Feedback_input -> "feedback");
      "consumer",endpoint row.slot input.consumer]) (A.input_order rule) in
  let groups = List.map (fun (row:A.group_ref) ->
    let group = List.find (fun (group:I.atomic_group) -> group.group_id=row.group_id) (F.atomic_groups (fragment row.slot)) in
    obj ["slot",str (slot_name row.slot);"id",str group.group_id;"arbiter",reference row.slot group.arbiter;
      "commits",arr (reference row.slot) group.commits]) (A.group_order rule) in
  let layout = A.layout rule in
  let staged=A.is_staged rule in
  let value = obj ["schema_version",str (if A.is_instanced rule then instance_union_profile else union_profile);"primitive_profile",str (if staged then I.staged_profile else I.profile);
    "observable_profile",str (if staged then I.staged_observable_profile else I.observable_profile);
    "phase_profile",str (if staged then F.staged_phase_profile else F.phase_profile);"transport_profile",str A.transport_profile;
    "slot_layout",obj ["id",str layout.layout_id;"slots",Json.int layout.slots];
    "nodes",Json.Array nodes;"wires",Json.Array wires;"inputs",Json.Array inputs;"atomic_groups",Json.Array groups;
    "semantic_exports",arr (fun (row:A.endpoint_ref) -> obj ["slot",str (slot_name row.node.slot);
      "node",str row.node.node_id;"port",str row.port_id]) (A.export_order rule);
    "links",get "links" (get "body" (A.to_json rule))] in
  M.check_resources value; value
let ordered_union_digest rule = Canonical.fingerprint (ordered_union_json rule)
type record_layout = {
  staged:bool; rule:P.t; union_digest:string; domain_digest:string; slots:int; generations:int; attempts:int;
  horizon:int; maximum_tick:int; ordered_reasons:int; ordered_causes:int; identifier_bytes:int;
}
let record_layout_to_json (value:record_layout) = obj ["profile",str (if value.staged then staged_record_profile else record_profile);
  "record_shapes",(if value.staged then staged_record_shapes else X.record_shapes);
  "rule",P.to_json value.rule;"union_digest",str value.union_digest;"domain_digest",str value.domain_digest;
  "slots",Json.int value.slots;"generations",Json.int value.generations;"attempts",Json.int value.attempts;
  "horizon_ticks",Json.int value.horizon;"maximum_tick",Json.int value.maximum_tick;
  "ordered_reason_slots",Json.int value.ordered_reasons;"ordered_cause_slots",Json.int value.ordered_causes;
  "identifier_bytes",Json.int value.identifier_bytes]
let pin raw = let value = Json.string raw in
  require (String.length value=64 && String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) value)
    "Composition context requires a lowercase SHA-256 digest."; value
let record_layout_of_json raw =
  M.check_resources raw;
  exact ["profile";"record_shapes";"rule";"union_digest";"domain_digest";"slots";"generations";"attempts";
    "horizon_ticks";"maximum_tick";"ordered_reason_slots";"ordered_cause_slots";"identifier_bytes"] raw;
  let staged=get "profile" raw=str staged_record_profile in
  require ((get "profile" raw=str record_profile || staged) &&
    Json.equal (get "record_shapes" raw) (if staged then staged_record_shapes else X.record_shapes))
    "Composition layout must retain the new profile and complete semantic record shapes.";
  let number minimum key = let value = Json.integer (get key raw) in
    require (Z.geq value (Z.of_int minimum) && Z.leq value (Z.of_int 1000000)) "Composition layout count exceeds its finite bound.";
    Z.to_int value in
  let rule = P.of_json (get "rule" raw) in
  require (P.kind rule=P.Model) "Composition layout requires a complete original rule Model pin.";
  let value = {staged;rule;union_digest=pin (get "union_digest" raw);domain_digest=pin (get "domain_digest" raw);
    slots=number 1 "slots";generations=number 1 "generations";attempts=number 1 "attempts";
    horizon=number 0 "horizon_ticks";maximum_tick=number 0 "maximum_tick";
    ordered_reasons=number 1 "ordered_reason_slots";ordered_causes=number 1 "ordered_cause_slots";
    identifier_bytes=number 1 "identifier_bytes"} in
  require (Json.equal raw (record_layout_to_json value)) "Composition layout must preserve its complete supplied spelling.";
  value
let record_layout_fingerprint value = Canonical.fingerprint (record_layout_to_json value)
type t = {instanced:bool;prerequisite_closure:bool;clock_value:X.clock;recipient_value:X.recipient;layout_value:record_layout;
  placement_value:AC.Placement.t;delivery_value:X.delivery_group;provider_values:X.provider list}
let to_json value = obj ["schema_version",str schema_version;"profile",str (if value.prerequisite_closure then prerequisite_profile else if value.instanced then (if value.layout_value.staged then instance_staged_profile else instance_profile)
    else if value.layout_value.staged then staged_profile else profile);
  "clock",X.clock_to_json value.clock_value;"recipient",X.recipient_to_json value.recipient_value;
  "record_layout",record_layout_to_json value.layout_value;"placement",AC.Placement.to_json value.placement_value;
  "delivery_group",X.delivery_group_to_json value.delivery_value;"helpers",Json.Array [];
  "providers",arr X.provider_to_json value.provider_values]
let of_json raw =
  M.check_resources raw;
  exact ["schema_version";"profile";"clock";"recipient";"record_layout";"placement";"delivery_group";"helpers";"providers"] raw;
  require (get "schema_version" raw=str schema_version && List.mem (get "profile" raw) [str profile;str staged_profile;str instance_profile;str instance_staged_profile;str prerequisite_profile])
    "Unsupported original composition context profile.";
  require (get "helpers" raw=Json.Array []) "Composition context does not support executable or delivered helpers.";
  let instanced=List.mem (get "profile" raw) [str instance_profile;str instance_staged_profile;str prerequisite_profile] in
  let prerequisite_closure=get "profile" raw=str prerequisite_profile in
  let value = {instanced;prerequisite_closure;clock_value=X.clock_of_json (get "clock" raw);recipient_value=X.recipient_of_json (get "recipient" raw);
    layout_value=record_layout_of_json (get "record_layout" raw);placement_value=AC.Placement.of_json (get "placement" raw);
    delivery_value=X.delivery_group_of_json (get "delivery_group" raw);
    provider_values=List.map X.provider_of_json (M.array ~maximum:128 (get "providers" raw))} in
  require (not prerequisite_closure || not value.layout_value.staged)
    "Prerequisite closure requires the unchanged truth record profile.";
  let unique label values = require (List.length values=List.length (List.sort_uniq String.compare values))
    ("Duplicate composition " ^ label ^ " identity.") in
  unique "provider definition" (List.map (fun (provider:X.provider) -> Canonical.encode (Policy_material_contract.provider_ref_to_json provider.definition)) value.provider_values);
  unique "provider" (List.map (fun (provider:X.provider) -> P.kind_name provider.identity ^ ":" ^ P.id provider.identity ^ ":" ^ P.version provider.identity) value.provider_values);
  unique "capacity pool" (List.concat_map (fun (provider:X.provider) -> List.map (fun (capacity:X.capacity) -> capacity.pool_id) provider.capacities) value.provider_values);
  let layout_digest = record_layout_fingerprint value.layout_value in
  List.iter (fun (provider:X.provider) -> List.iter (fun (capacity:X.capacity) ->
    require (capacity.record_layout_digest=layout_digest) "Provider capacity does not pin the complete original composition record layout.") provider.capacities) value.provider_values;
  require (Json.equal raw (to_json value)) "Composition context must preserve its complete original typed body without normalization.";
  value
let fingerprint value = Canonical.fingerprint (to_json value)
let clock value = value.clock_value
let recipient value = value.recipient_value
let record_layout value = value.layout_value
let placement value = value.placement_value
let delivery_group value = value.delivery_value
let providers value = value.provider_values

let is_instanced value = value.instanced
let requires_prerequisite_closure value = value.prerequisite_closure
let context_profile value = if value.prerequisite_closure then prerequisite_profile else if value.instanced then (if value.layout_value.staged then instance_staged_profile else instance_profile)
  else if value.layout_value.staged then staged_profile else profile
