open Bioc_wire
open Bioc_domain
module Codec = Verification_exploration.Codec
module Strings = Set.Make(String)
type limits={max_work:int;max_items:int;max_input_bytes:int;max_report_bytes:int;max_report_nodes:int}
let profile="biocompiler.reference_check.resources.v1"
let make_limits ?(max_work=50_000_000) ?(max_items=100_000) ?(max_input_bytes=Limits.max_request_bytes)
    ?(max_report_bytes=Limits.max_response_bytes) ?(max_report_nodes=Limits.max_json_nodes) ()=
  List.iter(fun(value,maximum)->Diagnostic.require(value>0 && value<=maximum) "reference_check_limits"
      "Reference checker limits must be positive reductions of the fixed native profile.")
    [max_work,50_000_000;max_items,100_000;max_input_bytes,Limits.max_request_bytes;
     max_report_bytes,Limits.max_response_bytes;max_report_nodes,Limits.max_json_nodes];
  {max_work;max_items;max_input_bytes;max_report_bytes;max_report_nodes}
let default_limits=make_limits()
let str value=Json.String value
let limits_json value=Json.Object["profile",str profile;"max_work",Json.int value.max_work;
  "max_retained_intermediate_items",Json.int value.max_items;"max_input_bytes",Json.int value.max_input_bytes;
  "max_input_nodes",Json.int Limits.max_json_nodes;"max_report_bytes",Json.int value.max_report_bytes;
  "max_report_nodes",Json.int value.max_report_nodes;"intermediate_accounting",str "cumulative_no_refunds"]
type t={limits:limits;work:Work_budget.t;codec:Codec.limits;input:Codec.limits;output:Work_budget.output;mutable retained:int}
let create ?parent limits=
  let work=match parent with None->Work_budget.create ~profile ~error_code:"reference_check_work_limit" ~maximum:limits.max_work ()
    |Some parent->Work_budget.nested ~parent ~profile ~error_code:"reference_check_work_limit" ~maximum:limits.max_work () in
  let charge=Work_budget.charge work in
  {limits;work;codec=Codec.make_limits ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes ~charge ();
   input=Codec.make_limits ~max_bytes:limits.max_input_bytes ~max_nodes:Limits.max_json_nodes ~charge ();
   output=Work_budget.create_output ~profile ~error_code:"reference_check_report_limit"
     ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes ();retained=0}
let work value=value.work
let settings value=value.limits
let codec value=value.codec
let charge value amount=Work_budget.charge value.work amount
let keep value count=Diagnostic.require(count>=0 && count<=value.limits.max_items-value.retained)
    "reference_check_item_limit" "Reference checker intermediate inventory exceeds its native cumulative item limit.";
  charge value count;value.retained<-value.retained+count
let prepare value authorities=
  List.iter(fun(size,_)->charge value (size+1))authorities;
  Codec.preflight ~limits:value.input(Json.Array(List.map snd authorities))
let reserve value raw=Codec.preflight ~limits:value.codec raw;
  Work_budget.reserve_json value.output(Json.Array[raw])
let fingerprint value raw=Codec.fingerprint ~limits:value.codec raw
let equal value left right=
  let left=Codec.encode ~limits:value.codec left in
  let right=Codec.encode ~limits:value.codec right in
  charge value(String.length left+String.length right+1);String.equal left right
let field key raw=Json.field key(Json.object_fields raw)
let array key raw=Json.array(field key raw)
let text key raw=Json.string(field key raw)
let strings key raw=List.map Json.string(array key raw)
let same_set value left right=
  let set values=List.fold_left(fun result item->charge value((String.length item+1)*(Strings.cardinal result+1));
    keep value 1;Strings.add item result)Strings.empty values in
  Strings.equal(set left)(set right)
let manifests value values=
  let seen=Hashtbl.create 8 in
  List.iter(fun(key,item)->charge value(String.length key+Reference_manifest.canonical_size item+1);keep value 1;
    Diagnostic.require(not(Hashtbl.mem seen key)) "reference_check" "Duplicate reference manifest inventory key.";
    Hashtbl.add seen key ())values;
  (* Complete manifest documents are reserved before sorting or fingerprint views. *)
  Codec.preflight ~limits:value.input(Json.Object(List.map(fun(key,item)->key,Reference_manifest.to_json item)values));
  let count=List.length values and key_bytes=List.fold_left(fun total(key,_)->total+String.length key)0 values in
  charge value((count+key_bytes+1)*(count+1));
  Json.Object(List.sort(fun(a,_)(b,_)->String.compare a b)values|>List.map(fun(key,item)->key,str(Reference_manifest.fingerprint item)))
let priority values=let open Realization_evidence in
  if List.mem Fail values then Fail else if List.mem Unsupported values then Unsupported else if List.mem Unknown values then Unknown else Pass

let manifest value key values=
  let cost=List.fold_left(fun total(name,_)->total+String.length name+String.length key+1)0 values in
  charge value cost;List.assoc_opt key values
