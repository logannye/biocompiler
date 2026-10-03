(* Full original Python bytes/errors; never imported accepted packages. *)
open Bioc_wire
module B=Bioc_artifact.Archive_budget
module Zp=Bioc_artifact.Stored_zip
module P=Bioc_artifact.Utf8_pretty
module W=Bioc_checker.Work_budget
let require value message=if not value then failwith message
let get name raw=Json.field name(Json.object_fields raw)
let text name raw=Json.string(get name raw)
let n raw=Z.to_int(Json.integer raw)
let hex text=
  let encoded=Bytes.create(2*String.length text) and alphabet="0123456789abcdef" in
  String.iteri(fun i ch->let value=Char.code ch in Bytes.set encoded(2*i)alphabet.[value lsr 4];
    Bytes.set encoded(2*i+1)alphabet.[value land 15])text;Bytes.unsafe_to_string encoded
let unhex text=
  require(String.length text mod 2=0)"Odd literal hex size";
  let digit=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith "Invalid literal hex" in
  let raw=Bytes.create(String.length text/2) in
  for i=0 to Bytes.length raw-1 do Bytes.set raw i(Char.chr(16*digit text.[2*i]+digit text.[2*i+1]))done;
  Bytes.unsafe_to_string raw
let obj fields=Json.Object fields
let bytes value=obj["bytes",Json.String(hex value)]
let entries raw=List.map(function Json.Array[Json.String path;Json.String value]->path,unhex value
  |_->failwith "Invalid literal member") (Json.array(get "entries" raw))
let encoded_entries values=obj["entries",Json.Array(List.map(fun(name,value)->Json.Array[Json.String name;Json.String(hex value)])values)]
let members raw=List.map(fun raw->{Zp.path=text "path" raw;byte_length=n(get "byte_length" raw);sha256=text "sha256" raw})
  (Json.array(get "members" raw))
let controls raw=
  let fields=Json.object_fields raw in
  require(List.for_all(fun(key,_)->List.mem key["max_archive_bytes";"max_member_bytes";"max_metadata_bytes";"max_entries";"max_path_bytes"])fields)"Unknown literal limit";
  let opt name=Option.map n(List.assoc_opt name fields) in
  B.make_limits ?max_archive_bytes:(opt "max_archive_bytes") ?max_member_bytes:(opt "max_member_bytes")
    ?max_metadata_bytes:(opt "max_metadata_bytes") ?max_entries:(opt "max_entries") ?max_path_bytes:(opt "max_path_bytes")()
let parent maximum=W.create ~profile:"archive.fixture" ~error_code:"archive_fixture_work" ~maximum ()
let budget ?(limits=B.defaults) ()=B.create ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits ()
let operation diagnostics budget name raw=match name with
 |"encode"->bytes(Zp.encode budget(entries raw))
 |"read"->encoded_entries(Zp.read budget ~diagnostics(unhex(text "bytes" raw)))
 |"pretty"->bytes(P.encode budget ~max_bytes:(B.limits budget).max_archive_bytes(get "document" raw))
 |"validate-files"->encoded_entries(Zp.validate_files budget(members raw)(entries raw))
 |"assemble"->let run=match get "run_metadata" raw with Json.Null->None|value->Some value in
   bytes(Zp.assemble budget ~manifest:(get "manifest" raw) ~members:(members raw) ~files:(entries raw) ?run_metadata:run ())
 |_->failwith "Unknown source literal operation"
let literals ~profile ~pin path=
 let channel=open_in_bin path in
 let raw=Fun.protect ~finally:(fun()->close_in channel)(fun()->
   let size=in_channel_length channel in
   require(size>0 && size<=4_194_304)"Archive literal file byte bound";
   really_input_string channel size) in
 require(Canonical.sha256 raw=pin)"Complete immutable archive literal bytes changed";
 let document=Json.parse_artifact ~max_bytes:4_194_304 ~max_nodes:250_000 raw in
 require(text "python_minor" document=profile)"Archive literal runtime slot differs";
 let diagnostics=match text "python_minor" document with
  |"3.11"->Zp.Python311|"3.14"->Zp.Python314|_->failwith "Unknown pinned Python profile" in
 require(text "schema" document="biocompiler.archive_container_literals.v1")"Unknown archive literal schema";
 require(text "sha256"(get "source" document)="36d598102ffea532b67a3a116266f573ccff07da39166230023d162fd675d43f")
   "Original archive source changed";
 let cases=Json.array(get "cases" document) in
 let identities=List.map(text "id")cases and operations=List.map(text "operation")cases in
 require(List.length cases=125 && List.length(List.sort_uniq String.compare identities)=125)
   "Complete original archive case census differs";
 require(List.sort_uniq String.compare operations=["assemble";"encode";"pretty";"read";"validate-files"])
   "Archive literal operation inventory differs";
 List.iter(fun row->
   let actual=try Ok(operation diagnostics(budget ~limits:(controls(get "limits" row))())(text "operation" row)(get "input" row))
     with Diagnostic.Error error->Error error in
   let expected=get "outcome" row in
   match actual,text "status" expected with
   |Ok value,"return"->require(Canonical.encode value=Canonical.encode(get "value" expected))("Byte/value mismatch: "^text "id" row)
   |Error error,"raise"->require(error.code="archive_container" && text "module" expected="biocompiler.errors" &&
      text "type" expected="SerializationError" && error.message=text "message" expected)
      ("Error mismatch: "^text "id" row^": "^error.code^": "^error.message)
   |Ok _,_->failwith("Expected rejection: "^text "id" row)
   |Error error,_->failwith("Unexpected rejection: "^text "id" row^": "^error.code^": "^error.message))
   cases
let caught code fn=try fn();failwith("Expected "^code)with Diagnostic.Error error->require(error.code=code)("Unexpected diagnostic: "^error.code)
let budget_cases()=
 let exercise budget=
   let data=Zp.encode budget["z",String.make 256 'x';"a.json","{\n  \"a\": 1\n}\n"] in
   require(Zp.read budget data=["a.json","{\n  \"a\": 1\n}\n";"z",String.make 256 'x'])"Actual roundtrip differs";
   require(P.encode budget ~max_bytes:4096(obj["integer",Json.int 7;"float",Json.Float 7.;"negative_zero",Json.Float(-0.)])=
     "{\n  \"float\": 7.0,\n  \"integer\": 7,\n  \"negative_zero\": -0.0\n}\n")"Pretty scalar identities changed" in
 let root=parent 10_000_000_000 in let observed=ref 0 in
 let state=B.create ~parent:root ~retain_bytes:(fun value->observed:= !observed+value)() in
 exercise state;let spent=10_000_000_000-W.remaining root and retained=B.retained state in
 require(retained= !observed && retained>0)"Retention reservations did not reach supplied owner";
 let exact_root=parent spent in
 exercise(B.create ~parent:exact_root ~retain_bytes:(fun _->()) ~limits:(B.make_limits ~max_retained_bytes:retained())());
 require(W.remaining exact_root=0)"Exact work boundary differs";
 let short_root=parent(spent-1) in
 (try exercise(B.create ~parent:short_root ~retain_bytes:(fun _->())());failwith "Work one-short accepted"
  with Diagnostic.Error error->require(W.is_exhaustion short_root error)"One-short did not exhaust actual ancestor");
 let limited=budget ~limits:(B.make_limits ~max_retained_bytes:(retained-1)())() in
 caught "archive_retention_limit"(fun()->exercise limited);
 caught "archive_closed"(fun()->ignore(Zp.encode limited["a","b"]));
 let shared=parent 100 in let first=W.nested ~parent:shared ~profile:"first" ~error_code:"first" ~maximum:100 () in
 W.charge first 100;
 caught "archive_fixture_work"(fun()->ignore(Zp.encode(B.create ~parent:shared ~retain_bytes:(fun _->())())["a","b"]));
 caught "archive_limits"(fun()->ignore(B.make_limits ~max_work:max_int()));
 caught "archive_limits"(fun()->ignore(B.make_limits ~max_archive_bytes:(-1)()));
 let state=budget() in caught "archive_work_limit"(fun()->B.product state max_int max_int);
 let rec graph=Json.Array[graph] in caught "archive_json_cycle"(fun()->ignore(P.encode(budget())~max_bytes:4096 graph));
 let rec spine=Json.Null::spine in caught "archive_json_limit"(fun()->ignore(P.encode(budget ~limits:(B.make_limits ~max_json_nodes:8())())~max_bytes:4096(Json.Array spine)));
 caught "archive_json_limit"(fun()->ignore(P.encode(budget ~limits:(B.make_limits ~max_json_depth:0())())~max_bytes:4096(Json.Array[Json.Null])));
 caught "archive_json_limit"(fun()->ignore(P.encode(budget())~max_bytes:1(Json.String "a")));
 let halted=budget() in caught "sentinel_retention"(fun()->
   let callback _=Diagnostic.fail "sentinel_retention" "Actual retention owner refused allocation." in
   let state=B.create ~parent:(B.work halted) ~retain_bytes:callback() in ignore(Zp.encode state["a","b"]))
let ()=
 require(Array.length Sys.argv=3)"Expected both closed Python minor literal paths";
 literals ~profile:"3.11" ~pin:"0de6d702d2ea0dece95d73740a9d58b2e526ed6a82341af26b0034e2f00dff5f" Sys.argv.(1);
 literals ~profile:"3.14" ~pin:"94c4b13d75a02bb15d707d64b571b8dd61ff6ca974040df27423b61ff5446361" Sys.argv.(2);budget_cases();
 print_endline "Stored ZIP and UTF-8 pretty JSON: source literal and cumulative resource controls passed."
