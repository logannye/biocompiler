open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module I=Bioc_reference_input.Reference_inputs
module P=Bioc_reference_package_service.Reference_build_inputs
module W=Bioc_checker.Work_budget
let require condition message=if not condition then failwith message
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let unhex value=
  require(String.length value mod 2=0)"Odd original file literal";
  let digit=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith "Invalid original file literal" in
  String.init(String.length value/2)(fun at->Char.chr(16*digit value.[at*2]+digit value.[at*2+1]))
let hex value=let out=Bytes.create(2*String.length value) and chars="0123456789abcdef" in
  String.iteri(fun at c->Bytes.set out(2*at)chars.[Char.code c lsr 4];Bytes.set out(2*at+1)chars.[Char.code c land 15])value;
  Bytes.unsafe_to_string out
let files raw=List.map(function Json.Array[Json.String name;Json.String raw]->name,unhex raw|_->failwith "Invalid original file pair")
  (Json.array raw)
let represented_files values=Json.Array(List.map(fun(name,bytes)->Json.Array[Json.String name;Json.String(hex bytes)])values)
let parent maximum=W.create ~profile:"reference.input.fixture" ~error_code:"reference_input_fixture_work" ~maximum()
let budget ?(limits=B.defaults)()=B.create ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits()
let call scope operation input=
  let files=files(get "files" input) in
  match operation with
  |"load"->let result=I.validate_snapshot scope ~files in Json.Object[
    "manifest",Reference_manifest.to_json(I.manifest result);"files",represented_files(I.files result)]
  |"collect"->let reference=Reference_manifest.of_json(get "reference" input) in
    represented_files(I.files(I.collect_snapshot scope ~reference ~files))
  |"manifest-bytes"->let reference=Reference_manifest.of_json(get "manifest" input) in
    Json.String(hex(I.manifest_bytes scope reference))
  |"prepare"->let alphabet=match text "alphabet" input with "DNA"->Reference_manifest.DNA|"RNA"->Reference_manifest.RNA|
      _->failwith "Unexpected original alphabet" in
    let snapshot=I.validate_snapshot scope ~files in let value=P.prepare scope ~alphabet snapshot in
    Json.Object["request",Reference_construct.Request.to_json(P.request value);
      "manifest",Reference_manifest.to_json(P.reference value);"registry",Component_registry.to_json(P.registry value)]
  |_->failwith "Unknown reference snapshot operation"
let literal path=
  let channel=open_in_bin path in
  let bytes=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->let size=in_channel_length channel in
    require(size>0 && size<=2_097_152)"Reference input literal byte limit";really_input_string channel size) in
  require(Canonical.sha256 bytes="0e23413088d1350bd48cedac6a4b2ef83e94e74dba8b32de5214559952aac8b2")
    "Complete original snapshot literal changed";
  let value=Json.parse_artifact ~max_bytes:2_097_152 ~max_nodes:250_000 bytes in
  require(text "schema" value="biocompiler.reference_input_snapshot_literals.v1")"Original snapshot schema changed";
  let cases=Json.array(get "cases" value) in
  require(List.length cases=17 && List.length(List.sort_uniq String.compare(List.map(text "id")cases))=17)
    "Complete original snapshot case census changed";
  require(List.sort_uniq String.compare(List.map(text "operation")cases)=["collect";"load";"manifest-bytes";"prepare"])
    "Original snapshot operation inventory changed";
  List.iter(fun row->let actual=try Ok(call(budget())(text "operation" row)(get "input" row))with Diagnostic.Error error->Error error in
    let expected=get "outcome" row in match actual,text "status" expected with
    |Ok value,"return"->require(Canonical.encode value=Canonical.encode(get "value" expected))
      ("Complete reference snapshot/constructor mismatch: "^text "id" row)
    |Error error,"raise"->require(List.mem error.code["reference_inputs";"reference_manifest";"legacy_reference_json"] &&
      text "module" expected="biocompiler.errors" && text "type" expected="SerializationError" &&
      text "message" expected=error.message)("Reference snapshot exception mismatch: "^text "id" row^": "^error.code^": "^error.message)
    |Ok _,_->failwith("Expected snapshot rejection: "^text "id" row)
    |Error error,_->failwith("Unexpected snapshot rejection: "^text "id" row^": "^error.code^": "^error.message))cases;
  cases
let caught code call=try call();failwith("Expected "^code)with Diagnostic.Error error->
  require(error.code=code)("Wrong snapshot rejection: "^error.code)
let resources cases=
  let raw=get "input"(List.find(fun row->text "id" row="load:original")cases) in
  let files=files(get "files" raw) in
  let exercise scope=
    let first=I.validate_snapshot scope ~files in
    let second=I.collect_snapshot scope ~reference:(I.manifest first) ~files in
    let prepared=P.prepare scope ~alphabet:Reference_manifest.DNA first in
    require(I.files first=I.files second)"Second actual snapshot changed immutable retained bytes";
    require(Reference_manifest.fingerprint(P.reference prepared)=Pinned_identity.content_fingerprint I.manifest_pin)
      "Preparation replaced independently pinned source" in
  let owner=parent 10_000_000_000 and retained=ref 0 in
  let scope=B.create ~parent:owner ~retain_bytes:(fun bytes->retained:= !retained+bytes)() in
  exercise scope;let used=10_000_000_000-W.remaining owner in
  let exact=parent used in
  exercise(B.create ~parent:exact ~retain_bytes:(fun _->())~limits:(B.make_limits ~max_retained_bytes:!retained())());
  require(W.remaining exact=0)"Exact snapshot/constructor work differed";
  let short=parent(used-1) in
  (try exercise(B.create ~parent:short ~retain_bytes:(fun _->())());failwith "One-short snapshot ancestor accepted"
   with Diagnostic.Error error->require(W.is_exhaustion short error)"Snapshot escaped supplied work ancestor");
  let short=budget ~limits:(B.make_limits ~max_retained_bytes:(!retained-1)())() in
  caught "archive_retention_limit"(fun()->exercise short);
  caught "archive_closed"(fun()->exercise short);
  let scope=budget() in let snapshot=I.validate_snapshot scope ~files in
  caught "reference_input_owner"(fun()->ignore(P.prepare(budget())~alphabet:Reference_manifest.DNA snapshot));
  caught "reference_input_missing"(fun()->ignore(I.validate_snapshot(budget())~files:[]));
  caught "reference_input_member_limit"(fun()->ignore(I.validate_snapshot(budget ~limits:(B.make_limits ~max_entries:1())())~files));
  caught "reference_input_depth_limit"(fun()->ignore(I.validate_snapshot(budget ~limits:(B.make_limits ~max_json_depth:0())())~files));
  let rec cyclic=("unused.txt","")::cyclic in
  caught "reference_inputs"(fun()->ignore(I.validate_snapshot(budget())~files:cyclic))
let ()=
  require(Array.length Sys.argv=2)"Expected complete original reference snapshot corpus";
  let cases=literal Sys.argv.(1)in resources cases;
  print_endline "Reference input snapshot: original bytes, constructors and shared resources passed."
