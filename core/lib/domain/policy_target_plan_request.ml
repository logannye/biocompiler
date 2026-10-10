open Bioc_wire
module Input = Policy_material_request
let schema_version = "biocompiler.policy_target_plan_request.v0.1"
let max_input_bytes = 8*1024*1024
let max_input_nodes = 250000
let max_input_depth = 128
type limits = {max_work:int;max_report_bytes:int;max_report_nodes:int}
let ceilings = {max_work=100000000;max_report_bytes=2*1024*1024;max_report_nodes=100000}
type t = {raw:Json.t;identity:string;decoding_work_value:int;target_value:string;
  document_value:Json.t;definitions_value:Json.t option;
  realization_value:Json.t option;material_value:Json.t option;limit_values:limits}
let of_json ?(charge=fun _->()) raw =
  let work=ref 0 in
  let spend amount =
    Diagnostic.require (amount>=0 && amount<=max_int- !work) "policy_target_plan_work_limit"
      "Planning-envelope accounting overflow.";
    charge amount;work:= !work+amount in
  let bytes=Input.preflight ~max_bytes:max_input_bytes ~max_nodes:max_input_nodes
    ~max_depth:max_input_depth ~charge:spend raw in
  let fields=Json.object_fields ~path:"/request" raw in
  Json.exact_fields ~path:"/request" ["schema_version";"target";"document";"definitions";
    "realization_request";"material_request";"limits"] fields;
  let get key=Json.field key fields in
  Diagnostic.require ~path:"/request/schema_version" (get "schema_version"=Json.String schema_version)
    "policy_target_plan_request" "Unknown policy planning envelope schema.";
  let target_value=Json.string ~path:"/request/target" (get "target") in
  ignore(Policy_target_capabilities.target target_value);
  let optional key = match get key with
    | Json.Null -> None
    | Json.Object _ as value -> Some value
    | _ -> Diagnostic.fail ~path:("/request/"^key) "policy_target_plan_request"
        "Optional planning authority must be a JSON object or explicit null." in
  let definitions_value=optional "definitions" and realization_value=optional "realization_request"
  and material_value=optional "material_request" in
  let limit_fields=Json.object_fields ~path:"/request/limits" (get "limits") in
  Json.exact_fields ~path:"/request/limits" ["max_work";"max_report_bytes";"max_report_nodes"] limit_fields;
  let integer key maximum =
    let path="/request/limits/"^key in
    let value=Json.integer ~path (Json.field key limit_fields) in
    Diagnostic.require ~path (Z.sign value>0 && Z.leq value (Z.of_int maximum))
      "policy_target_plan_request" "Planning allowance must be positive and within its fixed ceiling.";
    Z.to_int value in
  let limit_values={max_work=integer "max_work" ceilings.max_work;
    max_report_bytes=integer "max_report_bytes" ceilings.max_report_bytes;
    max_report_nodes=integer "max_report_nodes" ceilings.max_report_nodes} in
  spend bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:max_input_bytes raw in
  Diagnostic.require (String.length encoded=bytes) "policy_target_plan_accounting"
    "Planning preflight differs from canonical envelope size.";
  spend bytes;
  let identity=Canonical.sha256 encoded in
  {raw;identity;decoding_work_value= !work;target_value;document_value=get "document";
    definitions_value;realization_value;material_value;limit_values}
let to_json value=value.raw
let fingerprint value=value.identity
let decoding_work value=value.decoding_work_value
let target value=value.target_value
let document value=value.document_value
let definitions value=value.definitions_value
let realization_request value=value.realization_value
let material_request value=value.material_value
let limits value=value.limit_values
