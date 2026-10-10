open Bioc_wire
let schema_version="biocompiler.policy_coupled_json_graph.v0.1"
let max_expanded_nodes=1_000_000
let max_expanded_bytes=8*1024*1024-65536
let max_packet_nodes=249968
let max_depth=128
let max_string_bytes=4*1024*1024
let max_number_chars=4300
let export_schema_version="biocompiler.policy_coupled_export_json_graph.v0.1"
let max_export_nodes=2*max_expanded_nodes-1
let max_export_bytes=2*max_expanded_bytes-4
let s value=Json.String value
let a value=Json.Array value
let o value=Json.Object value
let profile=o["schema_version",s schema_version;"encoding",s "lossless_typed_postorder_dag";
  "expanded_identity",s "sha256_canonical_json";"expanded_node_count",s "values_and_object_keys";
  "max_expanded_bytes",Json.int max_expanded_bytes;"max_expanded_nodes",Json.int max_expanded_nodes;
  "max_packet_bytes",Json.int max_expanded_bytes;"max_packet_nodes",Json.int max_packet_nodes;
  "max_depth",Json.int max_depth;"max_string_bytes",Json.int max_string_bytes;
  "max_number_chars",Json.int max_number_chars;"claims",s "transport_only"]
let export_profile=Json.Object(List.map(fun(key,value)->key,match key with
  |"schema_version"->s export_schema_version
  |"max_expanded_bytes"->Json.int max_export_bytes
  |"max_expanded_nodes"->Json.int max_export_nodes|_->value)(Json.object_fields profile)@
  ["direction",s "response";"partition",s "base_result_and_artifact";
   "max_part_nodes",Json.int max_expanded_nodes;"max_part_bytes",Json.int max_expanded_bytes;
   "operations",a[s "export-policy-quantitative-assurance"]])
let require condition message=Diagnostic.require condition "policy_coupled_wire" message
let bounded condition message=Diagnostic.require condition "policy_coupled_wire_limit" message
let get key value=Json.field key(Json.object_fields value)
let has_schema expected=function Json.Object fields->
  (* Dispatch precedes preflight. Inspect at most the closed envelope's four
     fields, so even a cyclic native field-list cannot trap the caller here. *)
  let rec probe remaining=function
    |[]->false|_ when remaining=0->false
    |(key,value)::rest->
      if String.length key=14 && String.equal key "schema_version"then
        (match value with Json.String value->String.length value=String.length expected &&
          String.equal value expected|_->false)
      else probe(remaining-1)rest in probe 4 fields
  |_->false
let is_packet value=has_schema schema_version value
let is_export_packet value=has_schema export_schema_version value
let add maximum left right=
  bounded(left>=0 && right>=0 && right<=maximum-left)"Coupled JSON exceeds its closed expanded or physical bounds.";
  left+right
let string_bytes ~charge value=
  let length=String.length value in
  bounded(length<=max_string_bytes)"Coupled JSON string exceeds its byte bound.";
  charge length;Json.validate_utf8 value;
  let size=ref 2 in
  String.iter(fun character->charge 1;
    size:=add max_expanded_bytes !size(match character with
      |'"'|'\\'|'\b'|'\012'|'\n'|'\r'|'\t'->2
      |value when Char.code value<32->6|_->1))value;
  !size
let scalar_bytes ~charge=function
  |Json.Null->4|Json.Bool true->4|Json.Bool false->5
  |Json.String value->string_bytes ~charge value
  |Json.Int value->
    bounded(Z.numbits value<=4*max_number_chars)"Coupled JSON integer exceeds its numeric bound.";
    charge(1+Z.numbits value);
    let text=Z.to_string value in
    bounded(String.length text<=max_number_chars)"Coupled JSON integer exceeds its decimal bound.";
    charge(String.length text);String.length text
  |Json.Float value->
    require(Float.is_finite value)"Coupled JSON cannot contain a nonfinite number.";
    charge 64;
    let text=Canonical.float_string value in
    bounded(String.length text<=max_number_chars)"Coupled JSON float exceeds its numeric bound.";
    charge(String.length text);String.length text
  |_->assert false
let sort_fields ~charge fields=
  List.sort(fun(left,_)(right,_)->charge(1+String.length left+String.length right);
    String.compare left right)fields
let export_shape ~charge ~fields ~string raw=
  let object_fields value=match fields value with Some values->values|None->
    Diagnostic.fail "policy_coupled_wire" "Paired export requires the closed assurance response shape."in
  let exact names value=
    let actual=sort_fields ~charge(object_fields value)in
    charge(List.length names+List.length actual);
    List.iter(fun name->charge(String.length name))names;
    List.iter(fun(key,_)->charge(String.length key))actual;
    require(List.map fst actual=names)"Paired export contains an unsupported response or artifact field."in
  let field name value=
    match List.find_map(fun(key,value)->charge(1+String.length name+String.length key);
      if key=name then Some value else None)(object_fields value)with
    |Some value->value|None->Diagnostic.fail "policy_coupled_wire" "Paired export is missing a required field."in
  let text name expected value=
    let actual=string(field name value)in
    charge(1+String.length expected+Option.fold ~none:0 ~some:String.length actual);
    require(actual=Some expected)"Paired export has an unsupported schema, implementation or scope."in
  exact["artifact";"candidate";"candidate_fingerprint";"implementation";"invocation_fingerprint";
    "report";"report_fingerprint";"request_fingerprint";"schema_version";"validation_scope"]raw;
  text "schema_version" "biocompiler.core.policy_quantitative_assurance.v1" raw;
  text "implementation" "biocompiler.ocaml.policy_quantitative_assurance.v0.1" raw;
  text "validation_scope" "policy-quantitative-assurance-v0.1" raw;
  let artifact=field "artifact" raw in
  exact["fasta";"fasta_sha256";"manifest";"manifest_sha256";"schema_version"]artifact;
  text "schema_version" "biocompiler.policy_quantitative_assurance_export.v0.1" artifact;
  text "schema_version" "biocompiler.policy_quantitative_assurance_manifest.v0.1"(field "manifest" artifact);
  artifact
let export_partitions ~nodes ~bytes ~artifact_nodes ~artifact_bytes=
  bounded(artifact_nodes>0 && artifact_nodes<=max_expanded_nodes && artifact_bytes<=max_expanded_bytes)
    "Paired export artifact exceeds the original part bounds.";
  bounded(nodes-artifact_nodes+1<=max_expanded_nodes && bytes-artifact_bytes+4<=max_expanded_bytes)
    "Paired export base result exceeds the original part bounds."
let measure ?(export=false) ~charge ~max_nodes raw=
  let max_bytes=if export then max_export_bytes else max_expanded_bytes in
  let nodes=ref 0 and bytes=ref 0 in
  let artifact_nodes=ref 0 and artifact_bytes=ref 0 in
  let node()=charge 1;
    (if !nodes>=max_nodes then bounded false("Coupled JSON node bound exceeded: maximum "^
      string_of_int max_nodes^"; next node "^string_of_int(!nodes+1)^"."));
    nodes:= !nodes+1 in
  let byte count=
    (if count<0 || count>max_bytes- !bytes then bounded false
      ("Coupled JSON byte bound exceeded: maximum "^string_of_int max_bytes^
       "; consumed "^string_of_int !bytes^"; next bytes "^string_of_int count^"."));
    bytes:= !bytes+count in
  let rec visit active depth value=
    bounded(depth<=max_depth)"Coupled JSON exceeds its depth bound.";node();
    match value with
    |Json.Array values->
      List.iter(fun parent->charge 1;require(parent!=value)"Coupled JSON contains a cycle.")active;
      byte 2;
      let first=ref true in
      List.iter(fun child->charge 1;if !first then first:=false else byte 1;
        visit(value::active)(depth+1)child)values
    |Json.Object fields->
      List.iter(fun parent->charge 1;require(parent!=value)"Coupled JSON contains a cycle.")active;
      byte 2;
      let first=ref true in
      List.iter(fun(key,child)->charge 1;if !first then first:=false else byte 1;
        node();byte(string_bytes ~charge key);byte 1;
        if export && depth=0 then(
          charge(1+String.length key);
          if key="artifact"then(
            let before_nodes= !nodes and before_bytes= !bytes in
            visit(value::active)(depth+1)child;
            artifact_nodes:= !nodes-before_nodes;artifact_bytes:= !bytes-before_bytes)
          else visit(value::active)(depth+1)child)
        else visit(value::active)(depth+1)child)fields;
      let sorted=sort_fields ~charge fields in
      let rec unique=function (left,_)::((right,_)::_ as rest)->
        charge(1+String.length left+String.length right);
        require(left<>right)"Coupled JSON contains duplicate object keys.";unique rest|_->()in
      unique sorted
    |scalar->byte(scalar_bytes ~charge scalar)in
  visit [] 0 raw;
  if export then(
    export_partitions ~nodes:!nodes ~bytes:!bytes ~artifact_nodes:!artifact_nodes ~artifact_bytes:!artifact_bytes;
    ignore(export_shape ~charge ~fields:(function Json.Object fields->Some fields|_->None)
      ~string:(function Json.String value->Some value|_->None)raw));
  !bytes
let preflight ?(charge=fun _->()) raw=measure ~charge ~max_nodes:max_expanded_nodes raw
let preflight_export ?(charge=fun _->()) raw=measure ~export:true ~charge ~max_nodes:max_export_nodes raw
let encoded ?(export=false) ~charge ~bytes raw=
  charge bytes;
  let value=Canonical.encode_bounded ~max_bytes:(if export then max_export_bytes else max_expanded_bytes) raw in
  require(String.length value=bytes)"Coupled JSON canonical byte accounting differs from its encoding.";
  value
let fingerprint ?(export=false) ~charge ~bytes raw=
  let value=encoded ~export ~charge ~bytes raw in charge bytes;Canonical.sha256 value

let encode_value ~export ~charge raw=
  let bytes=if export then preflight_export ~charge raw else preflight ~charge raw in
  (* Logical preflight above counts every expanded occurrence before any
     reuse. This second, invocation-local index only skips rebuilding rows for
     the very same immutable JSON value. Its hash reads immediate children,
     never recursively hashes an unbounded subtree or uses moving addresses. *)
  let scalar_hash value=charge 1;match value with
    |Json.Null->0|Json.Bool false->1|Json.Bool true->2
    |Json.Int value->charge(1+Z.numbits value);Hashtbl.hash(3,value)
    |Json.Float value->charge 8;Hashtbl.hash(4,Int64.bits_of_float value)
    |Json.String value->charge(String.length value);Hashtbl.hash(5,value)
    |Json.Array _->6|Json.Object _->7 in
  let mix left right=charge 1;Hashtbl.hash(left,right)in
  let module Physical=Hashtbl.Make(struct
    type t=Json.t
    let equal left right=charge 1;left==right
    let hash value=match value with
      |Json.Array children->List.fold_left(fun found child->charge 1;
          mix found(scalar_hash child))6 children
      |Json.Object fields->List.fold_left(fun found(key,child)->charge(1+String.length key);
          mix(mix found(Hashtbl.hash key))(scalar_hash child))7 fields
      |scalar->scalar_hash scalar
  end)in
  let module Keys=Hashtbl.Make(struct
    type t=string
    let hash value=charge(1+String.length value);Hashtbl.hash value
    let equal left right=charge(1+String.length left+String.length right);String.equal left right
  end)in
  charge 64;
  let keys=Keys.create 32 and physical=Physical.create 32 and reversed=ref [] and count=ref 0 in
  let rec intern value=
    charge 1;
    let cached=match value with Json.Array _|Json.Object _->Physical.find_opt physical value|_->None in
    match cached with Some ordinal->ordinal|None->
    let row=match value with
      |Json.Null->o["kind",s "null"]
      |Json.Bool _->o["kind",s "boolean";"value",value]
      |Json.Int _->o["kind",s "integer";"value",value]
      |Json.Float _->o["kind",s "float";"value",value]
      |Json.String _->o["kind",s "string";"value",value]
      |Json.Array values->o["kind",s "array";"items",a(List.map(fun child->charge 1;Json.int(intern child))values)]
      |Json.Object fields->o["kind",s "object";"fields",a(List.map(fun(key,child)->charge 1;
          a[s key;Json.int(intern child)])(sort_fields ~charge fields))]in
    let row_bytes=measure ~charge ~max_nodes:max_packet_nodes row in
    let key=encoded ~charge ~bytes:row_bytes row in
    let ordinal=match Keys.find_opt keys key with Some ordinal->ordinal|None->
      bounded(!count<max_packet_nodes)"Coupled JSON has too many distinct transport nodes.";
      charge 1;let ordinal= !count in incr count;
      Keys.add keys key ordinal;reversed:=row:: !reversed;ordinal in
    (* Scalar equality is already cheap and exact in the typed-key index.
       Caching physically distinct equal strings here would only create long
       collision chains in the identity-only table. *)
    (match value with Json.Array _|Json.Object _->Physical.add physical value ordinal|_->());ordinal in
  let root=intern raw in
  charge !count;
  let packet=o["schema_version",s(if export then export_schema_version else schema_version);
    "expanded_sha256",s(fingerprint ~export ~charge ~bytes raw);
    "root",Json.int root;"nodes",a(List.rev !reversed)]in
  let packet_bytes=measure ~charge ~max_nodes:max_packet_nodes packet in
  (* Reserve the complete physical publication, including canonical encoding,
     even when this caller returns the immutable JSON to an outer transport. *)
  ignore(encoded ~charge ~bytes:packet_bytes packet);packet
let encode ?(charge=fun _->()) raw=encode_value ~export:false ~charge raw
let encode_export ?(charge=fun _->()) raw=encode_value ~export:true ~charge raw

type node=Scalar of Json.t|Items of int list|Fields of (string*int)list
type size={nodes:int;bytes:int;depth:int}
let decode_value ~export ~charge packet=
  let max_nodes=if export then max_export_nodes else max_expanded_nodes
  and max_bytes=if export then max_export_bytes else max_expanded_bytes in
  ignore(measure ~charge ~max_nodes:max_packet_nodes packet);
  Json.exact_fields["schema_version";"expanded_sha256";"root";"nodes"](Json.object_fields packet);
  require(get "schema_version" packet=s(if export then export_schema_version else schema_version))"Unknown coupled JSON packet schema.";
  let claimed=Json.string(get "expanded_sha256" packet)in
  require(String.length claimed=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)claimed)
    "Coupled JSON expanded identity must be lowercase SHA-256.";
  let rows=Json.array(get "nodes" packet)in
  let count=List.length rows in charge count;
  require(count>0)"Coupled JSON packet needs a root node.";
  let root=Json.integer(get "root" packet)in
  require(Z.equal root(Z.of_int(count-1)))"Coupled JSON root must be the final postorder node.";
  let module Keys=Hashtbl.Make(struct
    type t=string
    let hash value=charge(1+String.length value);Hashtbl.hash value
    let equal left right=charge(1+String.length left+String.length right);String.equal left right
  end)in
  charge(32+2*count);
  let keys=Keys.create 32 and nodes=Array.make count(Scalar Json.Null)
  and sizes=Array.make count{nodes=0;bytes=0;depth=0}in
  let reference ordinal value=
    charge 1;let value=Json.integer value in
    require(Z.sign value>=0 && Z.lt value(Z.of_int ordinal))"Coupled JSON references must point strictly backward.";
    Z.to_int value in
  List.iteri(fun ordinal raw->charge 1;
    let fields=Json.object_fields raw in
    let kind=Json.string(Json.field "kind" fields)in
    let exact names=Json.exact_fields names fields in
    let scalar predicate=
      exact["kind";"value"];let value=Json.field "value" fields in
      require(predicate value)"Coupled JSON scalar kind and value disagree.";Scalar value in
    let node=match kind with
      |"null"->exact["kind"];Scalar Json.Null
      |"boolean"->scalar(function Json.Bool _->true|_->false)
      |"integer"->scalar(function Json.Int _->true|_->false)
      |"float"->scalar(function Json.Float _->true|_->false)
      |"string"->scalar(function Json.String _->true|_->false)
      |"array"->exact["kind";"items"];Items(List.map(reference ordinal)(Json.array(Json.field "items" fields)))
      |"object"->exact["kind";"fields"];
        let previous=ref None in
        Fields(List.map(fun pair->charge 1;match Json.array pair with
          |[Json.String key;target]->
            Option.iter(fun before->charge(1+String.length before+String.length key);
              require(String.compare before key<0)"Coupled JSON object keys must be strictly sorted and unique.")!previous;
            previous:=Some key;key,reference ordinal target
          |_->Diagnostic.fail "policy_coupled_wire" "Coupled JSON object fields need exact key/reference pairs.")
          (Json.array(Json.field "fields" fields)))
      |_->Diagnostic.fail "policy_coupled_wire" "Unknown coupled JSON node kind."in
    let row_bytes=measure ~charge ~max_nodes:max_packet_nodes raw in
    let key=encoded ~charge ~bytes:row_bytes raw in
    require(not(Keys.mem keys key))"Coupled JSON repeats an interned node.";Keys.add keys key ();
    let size=match node with
      |Scalar value->{nodes=1;bytes=scalar_bytes ~charge value;depth=0}
      |Items children->
        let n=ref 1 and b=ref 2 and depth=ref 0 and first=ref true in
        List.iter(fun child->charge 1;let size=sizes.(child)in
          n:=add max_nodes !n size.nodes;
          if !first then first:=false else b:=add max_bytes !b 1;
          b:=add max_bytes !b size.bytes;depth:=max !depth(1+size.depth))children;
        {nodes= !n;bytes= !b;depth= !depth}
      |Fields children->
        let n=ref 1 and b=ref 2 and depth=ref 0 and first=ref true in
        List.iter(fun(key,child)->charge 1;let size=sizes.(child)in
          n:=add max_nodes(add max_nodes !n 1)size.nodes;
          if !first then first:=false else b:=add max_bytes !b 1;
          b:=add max_bytes(add max_bytes !b(string_bytes ~charge key))1;
          b:=add max_bytes !b size.bytes;depth:=max !depth(1+size.depth))children;
        {nodes= !n;bytes= !b;depth= !depth}in
    bounded(size.depth<=max_depth)"Coupled JSON expanded depth exceeds its bound.";
    nodes.(ordinal)<-node;sizes.(ordinal)<-size)rows;
  if export then(
    let fields ordinal=charge 1;match nodes.(ordinal)with Fields values->Some values|_->None
    and string ordinal=charge 1;match nodes.(ordinal)with Scalar(Json.String value)->Some value|_->None in
    let artifact=export_shape ~charge ~fields ~string(count-1)in
    charge 2;
    let total=sizes.(count-1)and artifact=sizes.(artifact)in
    export_partitions ~nodes:total.nodes ~bytes:total.bytes
      ~artifact_nodes:artifact.nodes ~artifact_bytes:artifact.bytes);
  (* Enforce deterministic first-visit DFS postorder, which also proves that
     every supplied row is reachable. No logical JSON has been built yet. *)
  charge count;let visited=Array.make count false and next=ref 0 in
  let rec order ordinal=charge 1;if not visited.(ordinal)then(
    (match nodes.(ordinal)with Scalar _->()|Items values->List.iter order values
      |Fields values->List.iter(fun(_,value)->order value)values);
    require(ordinal= !next)"Coupled JSON node order is not canonical reachable postorder.";
    visited.(ordinal)<-true;incr next)in
  order(count-1);require(!next=count)"Coupled JSON contains unreachable nodes.";
  charge count;let values=Array.make count Json.Null in
  Array.iteri(fun ordinal node->charge 1;
    values.(ordinal)<-(match node with Scalar value->value
      |Items children->Json.Array(List.map(fun child->charge 1;values.(child))children)
      |Fields children->Json.Object(List.map(fun(key,child)->charge 1;key,values.(child))children)))nodes;
  let value=values.(count-1)and size=sizes.(count-1)in
  require(fingerprint ~export ~charge ~bytes:size.bytes value=claimed)"Coupled JSON expanded identity differs from its complete contents.";
  value
let decode ?(charge=fun _->()) packet=decode_value ~export:false ~charge packet
let decode_export ?(charge=fun _->()) packet=decode_value ~export:true ~charge packet
