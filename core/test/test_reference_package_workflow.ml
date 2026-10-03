open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
module I=Bioc_reference_input.Reference_inputs
module S=Bioc_reference_package_service.Reference_package_workflow
module D=Bioc_reference_artifact.Reference_package_manifest
module E=Bioc_reference_export.Reference_sequence_export
module U=Bioc_pipeline.Reference_construct_pipeline
module V=Bioc_pipeline.Reference_molecular_pipeline
module C=Pipeline_contract
module Rebuild=Bioc_reference_package_service.Reference_package_rebuild
let require value message=if not value then failwith message
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let unhex raw=
  require(String.length raw mod 2=0)"Invalid original byte literal";
  let nibble=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith "Invalid original hex" in
  String.init(String.length raw/2)(fun i->Char.chr(16*nibble raw.[i*2]+nibble raw.[i*2+1]))
let hex raw=let chars="0123456789abcdef" in
  let output=Bytes.create(2*String.length raw) in String.iteri(fun i c->
    Bytes.set output(i*2)chars.[Char.code c lsr 4];Bytes.set output(i*2+1)chars.[Char.code c land 15])raw;
  Bytes.unsafe_to_string output
let files input=Json.array(get "files" input)|>List.map(function
  |Json.Array[Json.String name;Json.String data]->name,unhex data|_->failwith "Invalid original snapshot pair")
let parent maximum=W.create ~profile:"reference.package.fixture" ~error_code:"reference_package_fixture_work" ~maximum()
let budget ?(limits=B.defaults)()=B.create_owner ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits()
let caught code callback=try callback();failwith("Expected "^code)with Diagnostic.Error error->
  require(error.code=code)("Wrong package failure: "^error.code^": "^error.message)
let callbacks scope input calls captured=
  let raw=files input in
  let call name=calls:= !calls@[name] in
  let source=S.native_callbacks ~load:(fun owner _->call "load_reference_inputs";I.validate_snapshot owner ~files:raw)
    ~collect:(fun owner reference->call "collect_reference_files";I.collect_snapshot owner ~reference ~files:raw)
    ~package_version:(fun()->call "package_version";text "package_version" input) in
  {source with
    run=(fun owner ~request ~registry ~manifests->call "run_molecular_pipeline";
      require(owner==scope)"Native pipeline lost package owner";
      source.run owner ~request ~registry ~manifests);
    construct=(fun owner build->call "construct";source.construct owner build);
    export=(fun owner ~request ~construct ~artifact ~registry ~manifests ~line_width->call "export_reference_sequence";
      let result=source.export owner ~request ~construct ~artifact ~registry ~manifests ~line_width in
      captured:=Some(result,request,construct,artifact,registry,manifests,line_width);result);
    tool_versions=(fun()->call "_tools";List.map(fun(key,value)->key,
      if key="molecular_checker" && get "changed_tool" input=Json.Bool true then "fixture-current-checker" else value)
      (source.tool_versions()))}
let execute scope input=
  let calls=ref [] and captured=ref None in
  let request=D.Request.of_json scope(get "request" input) in
  let metadata=match get "run_metadata" input with Json.Null->None|raw->Some(D.Run_metadata.of_json scope raw) in
  let result=S.build scope ~callbacks:(callbacks scope input calls captured) ~request ?run_metadata:metadata() in
  result,!calls,Option.get !captured
let complete result input=
  let files=List.sort(fun(a,_)(b,_)->String.compare a b)(S.files result) in
  Json.Object["request",D.Request.to_json(S.request result);"manifest",D.Manifest.to_json(S.manifest result);
    "data",Json.String(hex(S.data result));"archive_sha256",Json.String(S.archive_sha256 result);
    "build_fingerprint",Json.String(S.build_fingerprint result);
    "files",Json.Array(List.map(fun(name,bytes)->Json.Array[Json.String name;Json.String(hex bytes)])files);
    "run_metadata",get "run_metadata" input]
let literal path=
  let channel=open_in_bin path in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->let size=in_channel_length channel in
    require(size>0 && size<=8_388_608)"Original package literal byte ceiling";really_input_string channel size) in
  require(Canonical.sha256 raw="a867677f97540fcab473cbde9be813b42c139a06c4aa2fd0009e7cde9ed9f135")
    "Complete original package witness changed";
  let value=Json.parse_artifact ~max_bytes:8_388_608 ~max_nodes:500_000 raw in
  require(text "schema" value="biocompiler.reference_package_workflow_literals.v1")"Original package schema changed";
  let cases=Json.array(get "cases" value) in
  require(List.length cases=8 && List.length(List.sort_uniq String.compare(List.map(text "id")cases))=8)
    "Original package case census changed";
  List.iter(fun row->let input=get "input" row in
    let actual=try let result,calls,_=execute(budget())input in Ok(result,calls)with Diagnostic.Error error->Error error in
    let expected=get "outcome" row in match actual,text "status" expected with
    |Ok(result,calls),"return"->
      require(Canonical.encode(complete result input)=Canonical.encode(get "value" expected))
        ("Complete native package differs from original: "^text "id" row);
      require(calls=["load_reference_inputs";"collect_reference_files";"run_molecular_pipeline";"construct";
        "export_reference_sequence";"construct";"package_version";"_tools"])
        "Original late metadata/two candidate read cadence changed";
      require(C.Pipeline_result.artifact(S.completion result)==List.nth(S.records result)2)
        "Final completion imported a different accepted record";
      require(U.budget(V.upstream(S.molecular_build result))==B.work(S.owner result))
        "Package build lost original manager lifetime"
    |Error error,"raise"->require(error.code="pipeline_error" && text "module" expected="biocompiler.compiler.pipeline" &&
        text "type" expected="PipelineError" && error.message=text "message" expected)
        ("Original package failure changed: "^text "id" row^": "^error.code^": "^error.message)
    |Ok _,_->failwith "Unsupported package acquired acceptance"
    |Error error,_->failwith("Unexpected package error: "^error.code^": "^error.message))cases;
  cases
let resources cases=
  let input=get "input"(List.find(fun row->text "id" row="DNA:default")cases) in
  let work=parent 10_000_000_000 and retained=ref 0 in
  let scope=B.create_owner ~parent:work ~retain_bytes:(fun amount->retained:= !retained+amount)() in
  let result,_,(checked,request,construct,artifact,registry,manifests,width)=execute scope input in
  require(!retained=B.retained scope && !retained<=B.defaults.max_retained_bytes)
    "Actual full package ownership escaped explicit 512 MiB profile";
  E.require_checked scope checked ~request ~construct ~artifact ~registry ~manifests ~line_width:width;
  caught "reference_export_binding"(fun()->E.require_checked(budget())checked ~request ~construct ~artifact ~registry ~manifests ~line_width:width);
  let altered=Reference_molecular.Artifact.to_json artifact in
  let altered=Reference_molecular.Artifact.of_json(Json.Object(List.map(fun(key,value)->key,
    if key="source_request_fingerprint"then Json.String(Canonical.sha256 "changed artifact")else value)(Json.object_fields altered))) in
  caught "reference_export_binding"(fun()->E.require_checked scope checked ~request ~construct ~artifact:altered ~registry ~manifests ~line_width:width);
  let stale=List.map(fun(key,value)->key,Reference_manifest.of_json(Json.Object(List.map(fun(name,raw)->name,
      if name="version"then Json.String "2"else raw)(Json.object_fields(Reference_manifest.to_json value)))))manifests in
  caught "reference_export_binding"(fun()->E.require_checked scope checked ~request ~construct ~artifact ~registry ~manifests:stale ~line_width:width);
  (* Measure only the first complete operation, before negative-capability probes. *)
  let baseline=parent 10_000_000_000 and retained=ref 0 in
  let owner=B.create_owner ~parent:baseline ~retain_bytes:(fun n->retained:= !retained+n)() in
  let expected,_,_=execute owner input in
  let used=10_000_000_000-W.remaining baseline in
  let exact=parent used in
  let actual,_,_=execute(B.create_owner ~parent:exact ~retain_bytes:(fun _->())
    ~limits:(B.make_limits ~max_retained_bytes:!retained())())input in
  require(W.remaining exact=0 && S.data actual=S.data expected)"Exact package lifetime changed work or bytes";
  let short=budget ~limits:(B.make_limits ~max_retained_bytes:(!retained-1)())() in
  caught "archive_retention_limit"(fun()->ignore(execute short input));
  caught "archive_closed"(fun()->ignore(execute short input));
  let one_short=parent(used-1) in
  (try ignore(execute(B.create_owner ~parent:one_short ~retain_bytes:(fun _->())())input);failwith "One-short package work accepted"
   with Diagnostic.Error error->require(W.is_exhaustion one_short error || W.exhausted one_short)
     "Package work did not fail through original ancestor");
  let before=B.retained scope in
  let descendant=W.nested ~parent:(B.work scope) ~profile:"package.sibling" ~error_code:"package_sibling_work" ~maximum:100() in
  W.retain descendant 17;require(B.retained scope=before+17)"Descendant growth missed persistent owner";
  caught "archive_retention_owner"(fun()->ignore(B.create_owner ~parent:descendant ~retain_bytes:(fun _->())()));
  require(S.data result=S.data expected)"Capability checks mutated accepted package bytes"
let reconstruction cases=
  let input=get "input"(List.find(fun row->text "id" row="DNA:default")cases) in
  let built,_,_=execute(budget())input in
  let factory files=S.native_callbacks
    ~load:(fun owner _->I.validate_snapshot owner ~files)
    ~collect:(fun owner reference->I.collect_snapshot owner ~reference ~files)
    ~package_version:(fun()->text "package_version" input) in
  let expected_request=S.request built and expected_build_fingerprint=S.build_fingerprint built in
  let checked=Rebuild.verify(budget())~callbacks:factory ~expected_request ~expected_build_fingerprint(S.data built) in
  require(S.data checked=S.data built && not(S.molecular_build checked==S.molecular_build built))
    "Verification reused imported acceptance instead of a fresh native pipeline";
  caught "reference_package"(fun()->ignore(Rebuild.verify(budget())~callbacks:factory "not an archive"));
  caught "reference_package"(fun()->ignore(Rebuild.verify(budget())~callbacks:factory
    ~expected_build_fingerprint:(Canonical.sha256 "stale expected build")(S.data built)));
  let changed files=let current=factory files in
    {current with tool_versions=(fun()->List.map(fun(key,value)->key,
      if key="molecular_checker"then "fixture-current-checker"else value)(current.tool_versions()))} in
  caught "reference_package"(fun()->ignore(Rebuild.verify(budget())~callbacks:changed
    ~expected_request ~expected_build_fingerprint(S.data built)));
  let marker=Failure "actual current pipeline callback" in
  let changed files=let current=factory files in
    {current with run=(fun _ ~request:_ ~registry:_ ~manifests:_->raise marker)} in
  (try ignore(Rebuild.verify(budget())~callbacks:changed ~expected_request(S.data built));
      failwith "Current pipeline exception was swallowed"
   with error->require(error==marker)"Current pipeline exception identity changed")
let ()=require(Array.length Sys.argv=2)"Expected complete original package corpus";
  let cases=literal Sys.argv.(1)in resources cases;reconstruction cases;
  print_endline "Full reference package: original bytes, fresh calls, bound export and cumulative lifetime passed."
