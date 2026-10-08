open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module P=Bioc_artifact.Utf8_pretty
module F=Reference_manifest
module C=Verification_exploration.Codec
let inputs_version="biocompiler.reference_build_inputs.v0.1"
let manifest_pin=Pinned_identity.make ~kind:Pinned_identity.Reference
  ~id:"wo2022081694a1.murine-fapcar.cds" ~version:"1"
  ~content_fingerprint:"e6bd93305ccf638757844d744c9ce9f8d84bbea4cfed40ba4cb224f28e610102"
let require condition message=Diagnostic.require condition "reference_inputs" message
let reference_pin budget alphabet=
  B.charge budget 1;B.reserve budget 512;
  let id,identity=match alphabet with
    |F.DNA->"wo2022081694a1.murine-fapcar.seq2","be64d2c4e6a5887a78c193be6f3aa747460487fa3e0a3a479784a95f58bcad90"
    |F.RNA->"wo2022081694a1.murine-fapcar.seq3","8c4deb2c377aa04b1586abdef9eda951418ea3dc04b3146dba2a2bef5b40a5d5"
    |F.Protein->Diagnostic.fail "reference_inputs" "The reviewed reference build supports only DNA or RNA." in
  Pinned_identity.make ~kind:Pinned_identity.Reference ~id ~version:"1" ~content_fingerprint:identity
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let codec budget=let limits=B.limits budget in C.make_limits
  ~max_bytes:(min limits.max_member_bytes Limits.max_request_bytes)
  ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
let bound_json budget raw=
  let size=C.measure ~limits:(codec budget) raw in
  let rec walk depth value=B.charge budget 1;
    Diagnostic.require(depth<=(B.limits budget).max_json_depth)"reference_input_depth_limit"
      "Reference snapshot JSON exceeds its depth limit.";
    match value with Json.Array values->List.iter(walk(depth+1))values
    |Json.Object values->List.iter(fun(_,value)->walk(depth+1)value)values|_->() in walk 0 raw;size
let path budget value=
  B.charge budget(String.length value+1);
  Diagnostic.require(String.length value<=(B.limits budget).max_path_bytes)"reference_input_path_limit"
    "Retained reference path exceeds its byte limit.";
  require(value<>"")"Invalid retained reference path.";
  B.reserve budget(64*String.length value+128);
  let segments=String.split_on_char '/' value in
  require(not(String.contains value '\\') && List.for_all(fun value->value<>"" && value<>"." && value<>"..")segments)
    "Retained reference paths must be canonical relative file paths.";
  Json.validate_utf8 value
let source_bytes budget files=
  let rec walk count total values=function
    |[]->List.rev values
    |(name,data)::rest->
      B.charge budget 1;
      Diagnostic.require(count<(B.limits budget).max_entries)"reference_input_member_limit"
        "Reference snapshot exceeds its member limit.";
      path budget name;
      B.product budget(String.length name+1)(count+1);
      require(not(List.mem_assoc name values))"Duplicate retained reference snapshot path.";
      require(String.length data<=16*1024*1024)"Retained reference file exceeds the bounded offline input size.";
      Diagnostic.require(String.length data<=(B.limits budget).max_member_bytes &&
        String.length data<=(B.limits budget).max_archive_bytes-total)"reference_input_byte_limit"
        "Reference snapshot exceeds its cumulative byte limit.";
      B.reserve budget(String.length data+String.length name+128);
      walk(count+1)(total+String.length data)((name,data)::values)rest in
  walk 0 0 [] files
let read budget files name=
  B.product budget(String.length name+1)(List.length files+1);
  match List.assoc_opt name files with Some value->value|None->
  Diagnostic.fail "reference_input_missing"("Reference snapshot is missing retained file: "^name^".")
let hashed budget value=B.charge budget(String.length value+1);Canonical.sha256 value
let parsed budget bytes=
  Diagnostic.require(String.length bytes<=min Limits.max_request_bytes(B.limits budget).max_member_bytes)
    "reference_input_byte_limit" "Reference manifest exceeds its byte limit.";
  B.reserve budget(128*String.length bytes+8192);
  Json.validate_utf8 bytes;
  let value=F.of_json_text ~limits:(codec budget) bytes in
  ignore(bound_json budget(F.to_json value));value
let sort budget values=
  let length=List.length values in
  let bytes=List.fold_left(fun total(name,_)->total+String.length name)0 values in
  let rec levels count n=if count<=1 then n else levels(count/2)(n+1) in
  B.product budget(bytes+length+1)(4*levels length 1);B.reserve budget(128*length+128);
  List.sort(fun(a,_)(b,_)->String.compare a b)values
let retained_paths budget manifest=
  let count=List.length(F.sources manifest)+List.length(F.reviews manifest) in
  B.reserve budget(256*count+128);
  let values=ref [] in
  let put name identity=
    B.reserve budget(64*(List.length !values+1));
    B.product budget(String.length name+1)(List.length !values+1);
    let rec update=function []->[name,identity]|(key,value)::rest->
      if name=key then(key,identity)::rest else(key,value)::update rest in
    values:=update !values in
  List.iter(fun source->B.charge budget 1;match get "local_path" source with
    |Json.Null->()|raw->let name=Json.string raw in path budget name;put name(text "sha256" source))(F.sources manifest);
  List.iter(fun review->B.charge budget 1;match get "evidence" review with
    |Json.Null->()|evidence->let name=text "local_path" evidence and identity=text "sha256" evidence in
      path budget name;
      B.product budget(String.length name+String.length identity+1)(List.length !values+1);
      require(match List.assoc_opt name !values with None->true|Some previous->previous=identity)
        "Conflicting retained reference identities.";put name identity)(F.reviews manifest);
  B.product budget 14 (List.length !values+1);
  require(not(List.mem_assoc "manifest.json" !values))"Reference evidence cannot replace its manifest.";
  sort budget !values
let independent_evidence budget files manifest=
  require(F.fingerprint manifest=Pinned_identity.content_fingerprint manifest_pin)"Reference manifest lock mismatch.";
  let retained=ref false in
  List.iter(fun source->B.charge budget 1;match get "local_path" source with
    |Json.Null->()|raw->let name=Json.string raw in
      require(hashed budget(read budget files name)=text "sha256" source)
        ("Source artifact hash mismatch: "^text "id" source^".");retained:=true)(F.sources manifest);
  require !retained "At least one source extraction artifact must be retained offline.";
  List.iter(fun review->B.charge budget 1;match get "evidence" review with
    |Json.Null->()|evidence->require(hashed budget(read budget files(text "local_path" evidence))=text "sha256" evidence)
      ("Review evidence hash mismatch: "^text "reviewer" review^"."))(F.reviews manifest)
let manifest_bytes budget manifest=
  ignore(bound_json budget(F.to_json manifest));
  let utf8=P.encode budget ~max_bytes:(B.limits budget).max_member_bytes(F.to_json manifest) in
  (* The reference manifest's historical JSON profile uses ensure_ascii=True,
     unlike package documents. Escape Unicode scalars after complete JSON
     encoding; JSON delimiters and existing ASCII escapes remain untouched. *)
  B.product budget(String.length utf8+1)8;
  let size=ref 0 in
  let rec count offset=if offset<String.length utf8 then
    let decoded=String.get_utf_8_uchar utf8 offset in let code=Uchar.to_int(Uchar.utf_decode_uchar decoded) in
    size:= !size+(if code<128 then 1 else if code<=0xffff then 6 else 12);
    count(offset+Uchar.utf_decode_length decoded) in count 0;
  Diagnostic.require(!size<=(B.limits budget).max_member_bytes)"reference_input_byte_limit"
    "Canonical reference manifest exceeds its byte limit.";
  B.reserve budget(!size+128);let output=Bytes.create !size and at=ref 0 and hex="0123456789abcdef" in
  let escape code=Bytes.set output !at '\\';Bytes.set output(!at+1)'u';
    for i=0 to 3 do Bytes.set output(!at+2+i)hex.[(code lsr(4*(3-i)))land 15]done;at:= !at+6 in
  let rec write offset=if offset<String.length utf8 then
    let decoded=String.get_utf_8_uchar utf8 offset in let code=Uchar.to_int(Uchar.utf_decode_uchar decoded) in
    (if code<128 then(Bytes.set output !at(Char.chr code);incr at)else if code<=0xffff then escape code
     else(let code=code-0x10000 in escape(0xd800+(code lsr 10));escape(0xdc00+(code land 0x3ff))));
    write(offset+Uchar.utf_decode_length decoded) in write 0;Bytes.unsafe_to_string output
type t={owner:B.t;reference:F.t;retained:(string*string)list}
let require_owner budget snapshot=B.guard budget;
  Diagnostic.require(budget==snapshot.owner)"reference_input_owner" "Reference snapshot belongs to another resource lifetime."
let validate_snapshot budget ~files=
  B.charge budget 1;
  let files=source_bytes budget files in
  let raw=read budget files "manifest.json" in
  let manifest=parsed budget raw in
  require(F.reference_set_id manifest=Pinned_identity.id manifest_pin && F.version manifest=Pinned_identity.version manifest_pin &&
    F.fingerprint manifest=Pinned_identity.content_fingerprint manifest_pin)
    "Reference build manifest differs from the independently reviewed pin.";
  let paths=retained_paths budget manifest in
  let retained=List.map(fun(name,identity)->let bytes=read budget files name in
    require(hashed budget bytes=identity)("Retained reference hash mismatch: "^name^".");name,bytes)paths in
  (* Independent second import and source/review gate over the exact supplied
     snapshot. This does not claim a second filesystem read occurred. *)
  let checked=parsed budget raw in independent_evidence budget files checked;
  require(F.fingerprint checked=F.fingerprint manifest)"Reference manifest changed while reading offline inputs.";
  let canonical=manifest_bytes budget checked in B.reserve budget(256+64*List.length retained);
  {owner=budget;reference=checked;retained=("manifest.json",canonical)::retained}
let collect_snapshot budget ~reference ~files=
  let snapshot=validate_snapshot budget ~files in
  require(F.fingerprint reference=F.fingerprint snapshot.reference)
    "Supplied manifest differs from the current pinned offline reference snapshot.";snapshot
let manifest snapshot=snapshot.reference
let files snapshot=snapshot.retained
