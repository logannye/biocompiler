(* Exact additive original authority; outputs are comparisons only. *)
open Bioc_wire
module B=Bioc_artifact.Archive_budget
module Zp=Bioc_artifact.Stored_zip
module Pretty=Bioc_artifact.Utf8_pretty
module M=Bioc_reference_artifact.Reference_package_manifest
module A=Bioc_reference_artifact.Reference_package_container
module W=Bioc_checker.Work_budget
let require value message=if not value then failwith message
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let hex value=let buffer=Bytes.create(2*String.length value) and chars="0123456789abcdef" in
  String.iteri(fun index c->Bytes.set buffer(2*index)chars.[Char.code c lsr 4];Bytes.set buffer(2*index+1)chars.[Char.code c land 15])value;
  Bytes.unsafe_to_string buffer
let unhex value=
  require(String.length value mod 2=0)"Odd byte literal";
  let digit=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith "Invalid byte literal" in
  String.init(String.length value/2)(fun n->Char.chr(16*digit value.[2*n]+digit value.[2*n+1]))
let parent maximum=W.create ~profile:"reference.package.fixture" ~error_code:"reference_package_fixture_work" ~maximum()
let budget ?(limits=B.defaults) ()=B.create ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits ()
let entries raw=List.map(function Json.Array[Json.String path;Json.String bytes]->path,unhex bytes|_->failwith "Invalid entries") (Json.array raw)
let encoded_entries values=Json.Array(List.map(fun(path,bytes)->Json.Array[Json.String path;Json.String(hex bytes)])values)
let represented budget value fingerprint=Json.Object["value",value;"fingerprint",Json.String fingerprint;
  "json",Json.String(Pretty.encode budget ~newline:false ~max_bytes:(B.limits budget).max_member_bytes value)]
let operation profile budget name input=
  let parsed decode decode_text=if String.ends_with ~suffix:"-text" name then decode_text(text "text" input)else decode input in
  let base=if String.ends_with ~suffix:"-text" name then String.sub name 0(String.length name-5)else name in
  match base with
  |"ReferenceBuildRequest"->let value=parsed(M.Request.of_json budget)(M.Request.of_json_text budget) in represented budget(M.Request.to_json value)(M.Request.fingerprint value)
  |"RunMetadata"->let value=parsed(M.Run_metadata.of_json ~runtime:profile budget)(M.Run_metadata.of_json_text ~runtime:profile budget) in represented budget(M.Run_metadata.to_json value)(M.Run_metadata.fingerprint value)
  |"PackageFile"->let value=parsed(M.File.of_json budget)(M.File.of_json_text budget) in represented budget(M.File.to_json value)(M.File.fingerprint value)
  |"AcceptedStage"->let value=parsed(M.Accepted_stage.of_json budget)(M.Accepted_stage.of_json_text budget) in represented budget(M.Accepted_stage.to_json value)(M.Accepted_stage.fingerprint value)
  |"ToolPin"->let value=parsed(M.Tool.of_json budget)(M.Tool.of_json_text budget) in represented budget(M.Tool.to_json value)(M.Tool.fingerprint value)
  |"BuildManifest"->let value=parsed(M.Manifest.of_json budget)(M.Manifest.of_json_text budget) in represented budget(M.Manifest.to_json value)(M.Manifest.fingerprint value)
  |"path"->Json.String(M.validate_package_path budget ~allow_reserved:(Json.boolean(get "allow_reserved" input))(get "path" input))
  |"assemble"->let manifest=M.Manifest.of_json budget(get "manifest" input) in
    let files=entries(get "files" input) in
    let run_metadata=match get "metadata" input with Json.Null->None|raw->Some(M.Run_metadata.of_json ~runtime:profile budget raw) in
    Json.String(hex(A.assemble budget manifest files ?run_metadata()))
  |"read"->let value=A.read ~runtime:profile budget(unhex(text "bytes" input)) in
    Json.Object["manifest",M.Manifest.to_json(A.manifest value);"files",encoded_entries(A.files value);
      "metadata",(match A.run_metadata value with None->Json.Null|Some raw->M.Run_metadata.to_json raw)]
  |_->failwith "Unknown package domain operation"
let literal ~profile ~minor ~pin path=
  let channel=open_in_bin path in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->let size=in_channel_length channel in
    require(size>0 && size<=4_194_304)"Package corpus byte bound";really_input_string channel size) in
  require(Canonical.sha256 raw=pin)"Complete original package corpus changed";
  let document=Json.parse_artifact ~max_bytes:4_194_304 ~max_nodes:1_000_000 raw in
  require(text "schema" document="biocompiler.reference_package_domains.v1" && text "python_minor" document=minor)"Package corpus runtime slot changed";
  let cases=Json.array(get "cases" document) in
  require(List.length cases=511 && List.length(List.sort_uniq String.compare(List.map(text "id")cases))=511)"Package corpus case census changed";
  let names=List.sort_uniq String.compare(List.map(text "operation")cases) in
  require(names=["AcceptedStage";"AcceptedStage-text";"BuildManifest";"BuildManifest-text";"PackageFile";"PackageFile-text";
    "ReferenceBuildRequest";"ReferenceBuildRequest-text";"RunMetadata";"RunMetadata-text";"ToolPin";"ToolPin-text";"assemble";"path";"read"])
    "Package corpus operation inventory changed";
  List.iter(fun row->let actual=try Ok(operation profile(budget())(text "operation" row)(get "input" row))with Diagnostic.Error error->Error error in
    let expected=get "outcome" row in match actual,text "status" expected with
    |Ok value,"return"->require(Canonical.encode value=Canonical.encode(get "value" expected))("Complete package value/bytes mismatch: "^text "id" row)
    |Error error,"raise"->require(List.mem error.code["reference_package_manifest";"reference_package_container";"archive_container";
       "reference_construct";"component_registry";"composition";"legacy_artifact_json"] && text "module" expected="biocompiler.errors" &&
       text "type" expected="SerializationError" && error.message=text "message" expected)
       ("Package exception mismatch: "^text "id" row^": "^error.code^": "^error.message)
    |Ok _,_->failwith("Expected package rejection: "^text "id" row)
    |Error error,_->failwith("Unexpected package rejection: "^text "id" row^": "^error.code^": "^error.message))cases;
  cases
let caught code fn=try fn();failwith("Expected "^code)with Diagnostic.Error error->require(error.code=code)("Wrong resource diagnostic: "^error.code)
let boundaries cases=
  let raw=get "input"(List.find(fun row->text "id" row="BuildManifest:valid")cases) in
  let exercise scope=
    let manifest=M.Manifest.of_json scope raw in
    let second=M.Manifest.of_json scope(M.Manifest.to_json manifest) in
    require(M.Manifest.fingerprint manifest=M.Manifest.fingerprint second)"Manifest identity changed on reimport" in
  let owner=parent 10_000_000_000 in let retained=ref 0 in
  let scope=B.create ~parent:owner ~retain_bytes:(fun bytes->retained:= !retained+bytes)() in
  exercise scope;let work=10_000_000_000-W.remaining owner in
  let exact=parent work in exercise(B.create ~parent:exact ~retain_bytes:(fun _->())~limits:(B.make_limits ~max_retained_bytes:!retained())());
  require(W.remaining exact=0)"Exact package work differs";
  let short=parent(work-1) in
  (try exercise(B.create ~parent:short ~retain_bytes:(fun _->())());failwith "Package work one-short accepted"
   with Diagnostic.Error error->require(W.is_exhaustion short error)"Package work escaped supplied ancestor");
  let short=budget ~limits:(B.make_limits ~max_retained_bytes:(!retained-1)())() in
  caught "archive_retention_limit"(fun()->exercise short);
  caught "archive_closed"(fun()->exercise short);
  caught "reference_package_depth_limit"(fun()->ignore(M.Manifest.of_json(budget ~limits:(B.make_limits ~max_json_depth:0())())raw));
  let rec values=("source.py","/source.py")::values in
  caught "reference_package_collection_limit"(fun()->ignore(M.Run_metadata.make(budget ~limits:(B.make_limits ~max_json_nodes:8())())
    ~timestamp_utc:"2026-10-02T00:00:00Z" ~machine_label:"host" ~locations:values()));
  let rec tree=Json.Array[tree] in
  (try ignore(M.Manifest.of_json(budget())tree);failwith "Cyclic package input accepted"
   with Diagnostic.Error error->require(error.code<>"reference_package_manifest")"Cycle treated as semantic import rejection")
let ()=
  require(Array.length Sys.argv=3)"Expected complete311 and314 package-domain corpora";
  let cases=literal ~profile:Zp.Python311 ~minor:"3.11" ~pin:"223115bd223b0cc86a4b7104230324fa67e56d3c23162640adaa410372992e69" Sys.argv.(1) in
  ignore(literal ~profile:Zp.Python314 ~minor:"3.14" ~pin:"86c33cc21e27b05706937527010130920472ec4457070559a286bd5713aca61d" Sys.argv.(2));
  boundaries cases;print_endline "Reference package domains and structural container: complete original literals and resources passed."
