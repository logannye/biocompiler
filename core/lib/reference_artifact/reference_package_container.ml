open Bioc_wire
module B=Bioc_artifact.Archive_budget
module Zp=Bioc_artifact.Stored_zip
module M=Reference_package_manifest
let require condition message=Diagnostic.require condition "reference_package_container" message
type t={manifest:M.Manifest.t;files:Zp.entry list;run_metadata:M.Run_metadata.t option}
let declarations budget manifest=
  B.reserve budget(128*(List.length(M.Manifest.files manifest)+1));
  List.map(fun value->B.charge budget 1;
    let size=M.File.byte_length value in
    (* Any value above max_int cannot equal a bounded actual member size. *)
    {Zp.path=M.File.path value;byte_length=(if Z.fits_int size then Z.to_int size else max_int);sha256=M.File.sha256 value})
    (M.Manifest.files manifest)
let assemble budget manifest files ?run_metadata ()=
  let members=declarations budget manifest in
  ignore(Zp.validate_files budget members files);
  Zp.assemble budget ~manifest:(M.Manifest.to_json manifest) ~members ~files
    ?run_metadata:(Option.map M.Run_metadata.to_json run_metadata)()
let parse budget raw=
  let limits=B.limits budget in
  B.product budget(String.length raw+1)32;B.reserve budget(64*String.length raw+128);
  (try Json.validate_utf8 raw with Diagnostic.Error error when error.code="invalid_utf8"->
    Diagnostic.fail "reference_package_container" "Archive metadata is not UTF-8 JSON.");
  Legacy_json.parse ~on_node:(fun()->B.charge budget 1) ~max_bytes:limits.max_metadata_bytes
    ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~profile:Legacy_json.Artifact raw
let read ?(runtime=Zp.Python314) budget raw=
  let entries=Zp.read budget ~diagnostics:runtime raw in
  require(List.mem_assoc "manifest.json" entries)"Archive has no build manifest.";
  let document=parse budget(List.assoc "manifest.json" entries) in
  require(match document with Json.Object _->true|_->false)"Archive manifest must be an object.";
  let fields=Json.object_fields document in
  let schema=List.assoc_opt "schema_version" fields in
  require(match schema with Some(Json.String _)->true|_->false)"Archive manifest schema must be text.";
  require(schema=Some(Json.String M.Manifest.schema_version))"Unsupported archive manifest schema.";
  let manifest=M.Manifest.of_json budget document in
  let run_metadata=match List.assoc_opt "run.json" entries with None->None|
    Some raw->Some(M.Run_metadata.of_json ~runtime budget(parse budget raw)) in
  B.reserve budget(64*(List.length entries+1));
  let files=List.filter(fun(name,_)->B.charge budget(String.length name+1);name<>"manifest.json" && name<>"run.json")entries in
  ignore(Zp.validate_files budget(declarations budget manifest)files);
  let encoded=assemble budget manifest files ?run_metadata () in
  B.charge budget(String.length raw+String.length encoded+1);
  require(encoded=raw)"Archive bytes are not canonical for the declared files and metadata.";
  B.reserve budget 128;{manifest;files;run_metadata}
let manifest (value:t)=value.manifest
let files (value:t)=value.files
let run_metadata (value:t)=value.run_metadata
