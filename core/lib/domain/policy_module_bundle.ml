open Bioc_wire
let schema_version="biocompiler.policy_module_bundle.v0.1"
let profile="biocompiler.policy_module_linking.v0.1"
type limits={max_work:int;max_bytes:int;max_depth:int;max_instances:int;max_declarations:int;max_ports:int}
let ceilings={max_work=16_000_000;max_bytes=8*1024*1024;max_depth=64;
  max_instances=64;max_declarations=4096;max_ports=256}
type access=Context|Read|Write|Request
type port={name:string;declaration:Json.t;access:access;path:string}
type pin={id:string;version:string;content_fingerprint:string}
type template={raw:Json.t;pin:pin;semantics:Json.t;inputs:port list;outputs:port list;
  declarations:Json.t list;private_refs:Json.t list;assumptions:Json.t list;
  guarantees:Json.t list;source_map:Json.t list;path:string}
type target=Context_ref of Json.t|Output_ref of{instance:string;port:string}
type binding={port:string;target:target;path:string}
type instance={name:string;template:pin;bindings:binding list;assumptions:Json.t list;path:string}
type meter={mutable limits_value:limits;mutable work_value:int;mutable bytes_value:int}
type t={raw:Json.t;context_value:Json.t;template_values:template list;instance_values:instance list;
  limits_value:limits;identity:string;decoding_work_value:int;decoding_bytes_value:int}
let bound condition=Diagnostic.require ~path:"/modules/limits" condition "policy_module_limit"
  "Module data exceeds its original cumulative work, byte, depth or count allowance."
let require path condition message=Diagnostic.require ~path condition "policy_module_bundle" message
let charge (meter:meter) amount=bound(amount>=0 && amount<=meter.limits_value.max_work-meter.work_value);
  meter.work_value<-meter.work_value+amount
let inspect (meter:meter) amount=bound(amount>=0 && amount<=meter.limits_value.max_bytes-meter.bytes_value);
  charge meter amount;meter.bytes_value<-meter.bytes_value+amount
let work (meter:meter)=meter.work_value
let bytes (meter:meter)=meter.bytes_value
(* Explicit list-edge visits bound cyclic spines; active containers and depth
   bound cyclic Json values before sorting, encoding or source decoding. *)
let scan (meter:meter) raw=
  let rec value active depth raw=
    charge meter 1;bound(depth<=meter.limits_value.max_depth);
    match raw with
    |Json.Null->inspect meter 4|Json.Bool v->inspect meter(if v then 4 else 5)
    |Json.Float _->require "/modules" false "Binary floating point is forbidden in module authority."
    |Json.Int n->bound(Z.numbits n<=1024);inspect meter(String.length(Z.to_string n))
    |Json.String text->string text
    |Json.Array rows->enter active raw;inspect meter 2;array(raw::active)(depth+1)true rows
    |Json.Object fields->enter active raw;inspect meter 2;
      let seen=Hashtbl.create 16 in object_fields seen(raw::active)(depth+1)true fields
  and enter active raw=List.iter(fun parent->charge meter 1;bound(parent!=raw))active
  and string text=
    bound(String.length text<=262144);inspect meter(2+String.length text);Json.validate_utf8 text;
    String.iter(function '"'|'\\'|'\b'|'\012'|'\n'|'\r'|'\t'->inspect meter 1
      |c when Char.code c<32->inspect meter 5|_->())text
  and array active depth first=function []->()|item::rest->
    charge meter 1;if not first then inspect meter 1;value active depth item;array active depth false rest
  and object_fields seen active depth first=function []->()|(key,item)::rest->
    charge meter 1;if not first then inspect meter 1;string key;inspect meter 1;
    require "/modules" (not(Hashtbl.mem seen key)) "Duplicate module object field.";
    Hashtbl.add seen key();value active depth item;object_fields seen active depth false rest in
  value [] 0 raw
let encode (meter:meter) raw=
  let before=bytes meter in scan meter raw;let size=bytes meter-before in
  (* Reserve the actual encoding separately from its complete traversal. *)
  inspect meter size;
  let encoded=Canonical.encode_bounded ~max_bytes:meter.limits_value.max_bytes raw in
  bound(String.length encoded=size);encoded
let hash meter raw=let encoded=encode meter raw in inspect meter(String.length encoded);Canonical.sha256 encoded
let get meter path key raw=
  let fields=Json.object_fields ~path raw in
  List.iter(fun(name,_)->charge meter 1;inspect meter(String.length name+String.length key))fields;
  Json.field ~path:(path^"/"^key) key fields
let exact meter path keys raw=scan meter raw;Json.exact_fields ~path keys(Json.object_fields ~path raw)
let text meter path raw=let result=Json.string ~path raw in inspect meter(String.length result);result
let name meter path raw=
  let result=text meter path raw in
  let alpha=function 'A'..'Z'|'a'..'z'->true|_->false in
  require path(String.length result>=1 && String.length result<=64 && alpha result.[0] &&
    String.for_all(function 'A'..'Z'|'a'..'z'|'0'..'9'|'_'|'-'->true|_->false)result)
    "Module, instance and port names require the simple 1-64 character ASCII grammar.";result
let version meter path raw=let result=text meter path raw in
  let characters=String.fold_left(fun count c->if Char.code c land 0xc0=0x80 then count else count+1)0 result in
  require path(characters>0 && characters<=128)"Module version must be explicit bounded text.";result
let rows meter path maximum raw=let result=Json.array ~path raw in
  let rec count n=function []->()|_::rest->charge meter 1;bound(n<maximum);count(n+1)rest in
  count 0 result;result
let pin_to_json(value:pin)=Json.Object["id",Json.String value.id;"version",Json.String value.version;
  "content_fingerprint",Json.String value.content_fingerprint]
let pin meter path raw=
  exact meter path["id";"version";"content_fingerprint"]raw;
  let digest=text meter(path^"/content_fingerprint")(get meter path "content_fingerprint" raw)in
  require path(String.length digest=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)digest)
    "Template fingerprint must be complete lowercase SHA-256.";
  {id=name meter(path^"/id")(get meter path "id" raw);
   version=version meter(path^"/version")(get meter path "version" raw);content_fingerprint=digest}
let of_json raw=
  let budget:meter={limits_value=ceilings;work_value=0;bytes_value=0}in
  scan budget raw;
  let get path key raw=get budget path key raw and exact path keys raw=exact budget path keys raw in
  let path="/modules" in
  exact path["schema_version";"profile";"context";"templates";"instances";"limits"]raw;
  require path(get path "schema_version" raw=Json.String schema_version && get path "profile" raw=Json.String profile)
    "Unknown module bundle schema or profile.";
  let allowance=get path "limits" raw in
  exact(path^"/limits")["max_work";"max_bytes";"max_depth";"max_instances";"max_declarations";"max_ports"]allowance;
  let limit key maximum=let value=Json.integer(get(path^"/limits")key allowance)in
    bound(Z.sign value>0 && Z.leq value(Z.of_int maximum));Z.to_int value in
  let limits_value={max_work=limit "max_work" ceilings.max_work;max_bytes=limit "max_bytes" ceilings.max_bytes;
    max_depth=limit "max_depth" ceilings.max_depth;max_instances=limit "max_instances" ceilings.max_instances;
    max_declarations=limit "max_declarations" ceilings.max_declarations;max_ports=limit "max_ports" ceilings.max_ports}in
  budget.limits_value<-limits_value;charge budget 0;inspect budget 0;
  (* Repeat under caller depth as well; no relaxed first pass grants authority. *)
  scan budget raw;
  let port path raw : port =
    exact path["name";"declaration";"access"]raw;
    let access=match Json.string(get path "access" raw)with
      |"context"->Context|"read"->Read|"write"->Write|"request"->Request
      |_->Diagnostic.fail ~path "policy_module_bundle" "Unknown module access mode."in
    {name=name budget(path^"/name")(get path "name" raw);declaration=get path "declaration" raw;access;path}in
  let map path maximum decode raw=List.mapi(fun index value->charge budget 1;
    decode(path^"/"^string_of_int index)value)(rows budget path maximum raw)in
  let template path raw : template =
    exact path["id";"version";"semantics";"inputs";"outputs";"declarations";"private";"assumptions";"guarantees";"source_map"]raw;
    let inputs=map(path^"/inputs")limits_value.max_ports port(get path "inputs" raw)
    and outputs=map(path^"/outputs")limits_value.max_ports port(get path "outputs" raw)in
    bound(List.length inputs+List.length outputs<=limits_value.max_ports);
    let list key=rows budget(path^"/"^key)limits_value.max_declarations(get path key raw)in
    {raw;pin={id=name budget(path^"/id")(get path "id" raw);
      version=version budget(path^"/version")(get path "version" raw);content_fingerprint=hash budget raw};
      semantics=get path "semantics" raw;inputs;outputs;declarations=list "declarations";
      private_refs=list "private";assumptions=list "assumptions";guarantees=list "guarantees";
      (* A declaration may retain several source spans. The declaration ceiling
         does not count spans; the authoring tuple and source-document bounds do. *)
      source_map=rows budget(path^"/source_map")4096(get path "source_map" raw);path}in
  let binding path raw : binding =
    exact path["port";"target"]raw;
    let target_raw=get path "target" raw and target_path=path^"/target"in
    let target=match Json.string(get target_path "kind" target_raw)with
      |"context"->exact target_path["kind";"reference"]target_raw;
        let reference=get target_path "reference" target_raw in
        exact(target_path^"/reference")["$type";"id";"kind"]reference;
        require target_path(get target_path "$type" reference=Json.String "Ref")"Context target requires a complete source Ref.";
        ignore(Json.name(get target_path "id" reference));ignore(Json.name(get target_path "kind" reference));Context_ref reference
      |"output"->exact target_path["kind";"instance";"port"]target_raw;
        Output_ref{instance=name budget(target_path^"/instance")(get target_path "instance" target_raw);
          port=name budget(target_path^"/port")(get target_path "port" target_raw)}
      |_->Diagnostic.fail ~path:target_path "policy_module_bundle" "Unknown binding target kind."in
    {port=name budget(path^"/port")(get path "port" raw);target;path}in
  let instance path raw : instance =
    exact path["name";"template";"bindings";"assumptions"]raw;
    {name=name budget(path^"/name")(get path "name" raw);template=pin budget(path^"/template")(get path "template" raw);
      bindings=map(path^"/bindings")limits_value.max_ports binding(get path "bindings" raw);
      assumptions=rows budget(path^"/assumptions")limits_value.max_declarations(get path "assumptions" raw);path}in
  let context_value=get path "context" raw in
  let template_values=map(path^"/templates")limits_value.max_instances template(get path "templates" raw)
  and instance_values=map(path^"/instances")limits_value.max_instances instance(get path "instances" raw)in
  let identity=hash budget raw in
  {raw;context_value;template_values;instance_values;limits_value;identity;
    decoding_work_value=work budget;decoding_bytes_value=bytes budget}
let to_json(value:t)=value.raw
let context value=value.context_value
let templates value=value.template_values
let instances value=value.instance_values
let limits(value:t)=value.limits_value
let fingerprint value=value.identity
let decoding_work value=value.decoding_work_value
let decoding_bytes value=value.decoding_bytes_value
let meter(value:t) : meter ={limits_value=value.limits_value;work_value=value.decoding_work_value;bytes_value=value.decoding_bytes_value}
