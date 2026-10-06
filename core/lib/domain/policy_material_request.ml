open Bioc_wire
module R=Policy_realization_request
module C=Policy_material_contract
module X=Policy_material_context
module P=Pinned_identity
module M=Molecular_record
let schema_version="biocompiler.policy_material_request.v0.1"
let profile="biocompiler.policy_truth_mrna.v0.1"
let resource_profile="biocompiler.policy_material_resources.v0.1"
type catalog_binding={entry_id:string;entry_version:string;entry_digest:string;
  operation:C.provider_ref;realization:C.provider_ref;material_contract:P.t}
type budgets={max_work:int;max_report_bytes:int;max_report_nodes:int}
type t={raw:Json.t;identity:string;request_value:R.t;contract_value:C.t;context_value:X.t;
  binding_value:catalog_binding;budget_values:budgets;decoding_work_value:int}
let get name raw=Json.field name(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let require condition message=Diagnostic.require condition "policy_material_request" message
let text raw=M.text ~maximum:256 raw
let digest raw=let value=Json.string raw in
  require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
    "Material request identity must be lowercase SHA-256.";value
let integer maximum raw=let value=Json.integer raw in
  require(Z.sign value>0 && Z.leq value(Z.of_int maximum))"Material resource allowance exceeds its closed bound.";
  Z.to_int value
(* A work unit is an explicit preflight value/key/list-edge visit or scalar
   byte, not an estimate of OCaml instructions inside downstream decoders.
   Each decoder keeps its own fixed hard limits as well. The callback receives
   only counts, so it cannot substitute or mutate the supplied authority. *)
type preflight_frame=Value of Json.t*int|Array_tail of Json.t list*int*bool
  |Object_tail of (string*Json.t)list*int*bool|Leave
let preflight ?(max_bytes=M.max_json_bytes) ?(max_nodes=M.max_items) ?(max_depth=M.max_depth) ~charge raw=
  Diagnostic.require(max_bytes>0 && max_bytes<=8388608 && max_nodes>0 && max_nodes<=250000 &&
    max_depth>=0 && max_depth<=128)"policy_material_input_limit"
    "Material preflight limits exceed the fixed protocol ceiling.";
  let nodes=ref 0 and bytes=ref 0 and active=ref []in
  let bounded condition=Diagnostic.require condition "policy_material_input_limit"
    "Material accounting input exceeds its bounded JSON traversal profile."in
  let byte amount=bounded(amount>=0 && amount<=max_bytes- !bytes);bytes:= !bytes+amount in
  let node()=charge 1;incr nodes;bounded(!nodes<=max_nodes)in
  let string value=
    bounded(String.length value<=M.max_residues);charge(String.length value);
    byte 2;byte(String.length value);
    String.iter(function '"'|'\\'|'\b'|'\012'|'\n'|'\r'|'\t'->byte 1
      |value when Char.code value<32->byte 5|_->())value in
  let enter value=
    List.iter(fun parent->charge 1;bounded(parent!=value))!active;
    active:=value:: !active in
  let rec visit=function
    |[]->()
    |Leave::rest->(match !active with _::parents->active:=parents|[]->assert false);visit rest
    |Value(value,depth)::rest->
      bounded(depth<=max_depth);node();
      (match value with
       |Json.String value->string value;visit rest
       |Json.Array values->enter value;byte 2;visit(Array_tail(values,depth+1,true)::Leave::rest)
       |Json.Object fields->enter value;byte 2;visit(Object_tail(fields,depth+1,true)::Leave::rest)
       |Json.Int value->
         bounded(Z.numbits value<=4096);
         let length=String.length(Z.to_string value)in charge length;byte length;visit rest
       |Json.Float value->
         Diagnostic.require(Float.is_finite value)"nonfinite_number""Material accounting input must be finite.";
         let length=String.length(Canonical.float_string value)in charge length;byte length;visit rest
       |Json.Null->byte 4;visit rest
       |Json.Bool value->byte(if value then 4 else 5);visit rest)
    |Array_tail([],_,_)::rest|Object_tail([],_,_)::rest->visit rest
    |Array_tail(value::values,depth,first)::rest->
      charge 1;if not first then byte 1;
      visit(Value(value,depth)::Array_tail(values,depth,false)::rest)
    |Object_tail((key,value)::fields,depth,first)::rest->
      charge 1;if not first then byte 1;node();string key;byte 1;
      visit(Value(value,depth)::Object_tail(fields,depth,false)::rest)in
  visit[Value(raw,0)];!bytes
let of_json ?(charge=fun _->()) raw=
  let decoding_work_value=ref 0 in
  let spend amount=
    Diagnostic.require(amount>=0 && amount<=max_int- !decoding_work_value)
      "policy_material_work_limit""Material logical work counter overflow.";
    charge amount;decoding_work_value:= !decoding_work_value+amount in
  let decode decoder raw=ignore(preflight ~charge:spend raw);decoder raw in
  let raw_bytes=preflight ~charge:spend raw in
  M.check_resources raw;
  exact["schema_version";"profile";"implementation_request";"material_contract";"context";"catalog_binding";"budgets"]raw;
  require(get "schema_version" raw=Json.String schema_version && get "profile" raw=Json.String profile)
    "Unsupported original policy material request profile.";
  let request_value=decode R.of_json(get "implementation_request" raw)in
  let contract_value=decode(C.of_json ~library:(R.implementation_library request_value))(get "material_contract" raw)in
  let context_value=decode X.of_json(get "context" raw)in
  let binding=get "catalog_binding" raw in
  exact["entry_id";"entry_version";"entry_digest";"operation";"realization";"material_contract"]binding;
  let binding_value={entry_id=text(get "entry_id" binding);entry_version=text(get "entry_version" binding);
    entry_digest=digest(get "entry_digest" binding);operation=C.provider_ref_of_json(get "operation" binding);
    realization=C.provider_ref_of_json(get "realization" binding);material_contract=P.of_json(get "material_contract" binding)}in
  require(P.kind binding_value.material_contract=P.Model)"Material case must be an explicitly supplied model identity.";
  let budget=get "budgets" raw in
  exact["profile";"max_work";"max_report_bytes";"max_report_nodes"]budget;
  require(get "profile" budget=Json.String resource_profile)"Unsupported material resource profile.";
  let budget_values={max_work=integer 1000000000(get "max_work" budget);
    max_report_bytes=integer 8323072(get "max_report_bytes" budget);
    max_report_nodes=integer 249968(get "max_report_nodes" budget)}in
  (* Encoding and hashing each consume the exact canonical byte inventory,
     charged before that pass. No multiplier guesses a decoder's instruction
     count and the already retained encoding is reused for the digest. *)
  spend raw_bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:M.max_json_bytes raw in
  Diagnostic.require(String.length encoded=raw_bytes)"policy_material_accounting"
    "Preflight canonical byte inventory differs from the actual encoding.";
  spend raw_bytes;
  let identity=Canonical.sha256 encoded in
  {raw;identity;request_value;contract_value;context_value;binding_value;budget_values;
    decoding_work_value= !decoding_work_value}
let to_json value=value.raw
let fingerprint value=value.identity
let implementation_request value=value.request_value
let material_contract value=value.contract_value
let context value=value.context_value
let catalog_binding value=value.binding_value
let budgets value=value.budget_values
let decoding_work value=value.decoding_work_value
