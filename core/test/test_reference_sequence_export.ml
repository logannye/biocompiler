(* Actual original authorities are inputs; expected bytes/errors are comparisons
   only. Imported artifact identities never substitute for the fresh checker. *)
open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
module S=Bioc_reference_export.Reference_sequence_codec
module X=Bioc_reference_export.Reference_sequence_export
module R=Reference_construct
module Q=Reference_molecular
let require value message=if not value then failwith message
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let parent maximum=W.create ~profile:"reference.sequence.fixture" ~error_code:"reference_sequence_fixture_work" ~maximum()
let budget ?(limits=B.defaults)()=B.create ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits ()
let represented scope value=Json.Object[
  "fasta",Json.String(S.fasta value);"specification",Json.String(S.specification value);
  "line_width",Json.int(S.line_width value);"sequence_sha256",Json.String(S.sequence_sha256 value);
  "molecular_fingerprint",Json.String(S.molecular_fingerprint value);
  "fasta_sha256",Json.String(S.fasta_sha256 scope value);
  "specification_sha256",Json.String(S.specification_sha256 scope value)]
type authority={request:R.Request.t;construct:R.Candidate.t;artifact:Q.Artifact.t;
  registry:Component_registry.t;manifests:(string*Reference_manifest.t)list}
let import_authority raw=
  (* These complete original declarations are independently imported before
     recording the operation's outcome: importer failures cannot stand in for
     the expected sequence-export rejection. *)
  try
    {request=R.Request.of_json(get "request" raw);construct=R.Candidate.of_json(get "construct" raw);
     artifact=Q.Artifact.of_json(get "artifact" raw);registry=Component_registry.of_json(get "registry" raw);
     manifests=List.map(function Json.Array[Json.String key;value]->key,Reference_manifest.of_json value|
       _->failwith "Invalid complete reference authority pair")(Json.array(get "manifests" raw))}
  with Diagnostic.Error error->failwith("Original sequence authority failed import: "^error.code^": "^error.message)
let exported scope authority width=X.export scope ~request:authority.request ~construct:authority.construct
  ~artifact:authority.artifact ~registry:authority.registry ~manifests:authority.manifests ~line_width:width()
let operation scope name input authority=
  match name with
  |"make"->represented scope(S.of_json scope input)
  |"verify"->let candidate=Q.Artifact.of_json(get "artifact" input) in
    let bundle=S.of_json scope(get "bundle" input) in Json.Bool(S.verify scope bundle candidate)
  |"export"->let width=S.line_width_of_json scope(get "line_width" input) in
    represented scope(exported scope(Option.get authority)width)
  |_->failwith "Unknown original sequence operation"
let literal path=
  let channel=open_in_bin path in
  let bytes=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->let size=in_channel_length channel in
    require(size>0 && size<=4_194_304)"Sequence corpus byte limit";really_input_string channel size) in
  require(Canonical.sha256 bytes="8c3b04e08b6bc9c31e82bd82afd085697a67c41388e9bbec8744e28bc00630bd")
    "Complete original sequence corpus changed";
  let corpus=Json.parse_artifact ~max_bytes:4_194_304 ~max_nodes:1_000_000 bytes in
  require(text "schema" corpus="biocompiler.reference_sequence_export_literals.v1")"Sequence corpus schema changed";
  let cases=Json.array(get "cases" corpus) in
  require(List.length cases=140 && List.length(List.sort_uniq String.compare(List.map(text "id")cases))=140)
    "Complete original sequence case census changed";
  require(List.sort_uniq String.compare(List.map(text "operation")cases)=["export";"make";"verify"])
    "Sequence operation census changed";
  List.iter(fun row->let name=text "operation" row and input=get "input" row in
    let authority=if name="export" then Some(import_authority input)else None in
    let actual=try Ok(operation(budget())name input authority)with Diagnostic.Error error->Error error in
    let expected=get "outcome" row in
    match actual,text "status" expected with
    |Ok value,"return"->require(Canonical.encode value=Canonical.encode(get "value" expected))
      ("Exact sequence value/byte mismatch: "^text "id" row)
    |Error error,"raise"->require(List.mem error.code["reference_sequence_export";"reference_molecular";"legacy_artifact_json"] &&
      text "module" expected="biocompiler.errors" && text "type" expected="SerializationError" &&
      error.message=text "message" expected)("Sequence error mismatch: "^text "id" row^": "^error.code^": "^error.message)
    |Ok _,_->failwith("Expected sequence rejection: "^text "id" row)
    |Error error,_->failwith("Unexpected sequence rejection: "^text "id" row^": "^error.code^": "^error.message))cases;
  cases
let caught code call=try call();failwith("Expected "^code)with Diagnostic.Error error->
  require(error.code=code)("Wrong sequence resource diagnostic: "^error.code)
let resources cases=
  let original=get "input"(List.find(fun row->text "id" row="DNA:export-width:80")cases) in
  let authority=import_authority original in
  let exercise scope=
    let bundle=exported scope authority 80 in
    require(S.verify scope bundle authority.artifact)"Fresh bundle failed repeated fidelity";
    ignore(represented scope bundle) in
  let owner=parent 10_000_000_000 and retained=ref 0 in
  let scope=B.create ~parent:owner ~retain_bytes:(fun count->retained:= !retained+count)() in
  exercise scope;
  let work=10_000_000_000-W.remaining owner in
  require(!retained=B.retained scope && !retained>X.checker_reservation_bytes())"Nested checker reservation escaped owner";
  let exact=parent work in
  exercise(B.create ~parent:exact ~retain_bytes:(fun _->()) ~limits:(B.make_limits ~max_retained_bytes:!retained())());
  require(W.remaining exact=0)"Exact sequence work changed";
  let short=parent(work-1) in
  (try exercise(B.create ~parent:short ~retain_bytes:(fun _->())());failwith "Sequence parent one-short accepted"
   with Diagnostic.Error error->require(W.is_exhaustion short error)"Sequence work did not charge supplied ancestor");
  let short=budget ~limits:(B.make_limits ~max_retained_bytes:(!retained-1)())() in
  caught "archive_retention_limit"(fun()->exercise short);
  caught "archive_closed"(fun()->exercise short);
  let insufficient=budget ~limits:(B.make_limits ~max_retained_bytes:(X.checker_reservation_bytes()-1)())() in
  caught "archive_retention_limit"(fun()->ignore(exported insufficient authority 80));
  require(B.retained insufficient<X.checker_reservation_bytes())"Checker ceilings reserved after execution";
  let profile=X.checker_limits_json() in
  let molecular=get "molecular" profile and construct=get "construct" profile and composition=get "composition" profile in
  List.iter(fun key->require(get key molecular=get key construct && get key construct=get key composition)
    ("Actual forwarded checker ceiling differs: "^key))
    ["max_work";"max_retained_intermediate_items";"max_input_bytes";"max_report_bytes";"max_report_nodes"];
  require(Canonical.encode molecular=Canonical.encode(Bioc_checker.Reference_molecular_check.limits_json
    Bioc_checker.Reference_molecular_check.default_limits))"Outer checker default silently reduced";
  let rec fields=("fasta",Json.String "")::fields in
  (try ignore(S.of_json(budget ~limits:(B.make_limits ~max_json_nodes:8())())(Json.Object fields));
       failwith "Cyclic sequence object fields accepted"
   with Diagnostic.Error error->require(error.code<>"reference_sequence_export")"Cycle became a semantic constructor rejection");
  let raw=get "bundle"(get "input"(List.find(fun row->text "id" row="DNA:verify")cases)) in
  caught "reference_export_depth_limit"(fun()->ignore(S.of_json(budget ~limits:(B.make_limits ~max_json_depth:0())())raw))
let ()=
  require(Array.length Sys.argv=2)"Expected complete original sequence export corpus";
  let cases=literal Sys.argv.(1) in resources cases;
  print_endline "Reference sequence export: complete original bytes, fresh checking and shared resources passed."
