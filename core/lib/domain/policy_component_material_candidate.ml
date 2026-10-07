open Bioc_wire
module O = Policy_operational
module I = Policy_implementation
module U = Policy_implementation_binding
module Q = Policy_component_assembly_proposal
module K = Construction_content
module Input = Policy_material_request

let schema_version = "biocompiler.policy_component_material_candidate.v0.1"
type t = {
  raw:Json.t; decoding_work_value:int; behavior_value:O.behavior;
  implementation_value:I.t; binding_value:U.t;
  assembly_value:Q.t; construction_value:K.t;
}

let of_json ?(charge=fun _ -> ()) ~library raw =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "policy_component_material_candidate_work_limit" "Candidate decoding work counter overflow.";
    charge amount; work := !work + amount in
  let measure value = Input.preflight ~max_bytes:8388608 ~max_nodes:250000
    ~max_depth:128 ~charge:spend value in
  let decode parser value = ignore (measure value); parser value in
  ignore (measure raw);
  let fields = Json.object_fields ~path:"/payload/candidate" raw in
  Json.exact_fields ~path:"/payload/candidate"
    ["schema_version"; "behavior"; "implementation"; "binding"; "assembly_proposal"; "construction"] fields;
  Diagnostic.require (Json.field "schema_version" fields = Json.String schema_version)
    "policy_component_material_candidate" "Unknown complete material candidate schema.";
  let behavior_value = decode O.behavior_of_json (Json.field "behavior" fields) in
  let implementation_value = decode (I.of_json ~library) (Json.field "implementation" fields) in
  let binding_value = decode U.of_json (Json.field "binding" fields) in
  let assembly_value = decode Q.of_json (Json.field "assembly_proposal" fields) in
  let construction_value = decode (fun value -> K.of_json value) (Json.field "construction" fields) in
  {raw; decoding_work_value= !work; behavior_value; implementation_value;
   binding_value; assembly_value; construction_value}

let to_json value = value.raw
let decoding_work value = value.decoding_work_value
let behavior value = value.behavior_value
let implementation value = value.implementation_value
let binding value = value.binding_value
let assembly_proposal value = value.assembly_value
let construction value = value.construction_value
