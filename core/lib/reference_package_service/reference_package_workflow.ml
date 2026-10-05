open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module P=Bioc_artifact.Utf8_pretty
module D=Bioc_reference_artifact.Reference_package_manifest
module A=Bioc_reference_artifact.Reference_package_container
module I=Bioc_reference_input.Reference_inputs
module U=Bioc_pipeline.Reference_construct_pipeline
module V=Bioc_pipeline.Reference_molecular_pipeline
module M=Bioc_compiler.Pass_manager
module C=Pipeline_contract
module X=Bioc_reference_export.Reference_sequence_codec
module Export=Bioc_reference_export.Reference_sequence_export
module Construct_check=Bioc_checker.Reference_construct_check
module Composition_check=Bioc_checker.Composition_check
module Codec=Verification_exploration.Codec
let build_version="biocompiler.reference_build.v0.2"
let require value message=Diagnostic.require value "reference_package" message
let str value=Json.String value
let field key raw=Json.field key(Json.object_fields raw)
let default_tool_versions()=[
  "reference_build",build_version;"human_admission_policy",Admission.policy_version;
  "reference_inputs",I.inputs_version;"archive","biocompiler.reference_archive.v0.4";
  "sequence_export",X.export_version;"sequence_emitter",Bioc_compiler.Reference_sequence_emitter.emitter_version;
  "construct_pipeline",U.pipeline_version;"molecular_pipeline",V.pipeline_version;
  "reference_adapter",Reference_components.adapter_version;
  "construct_generator",Bioc_compiler.Reference_construct_producer.generator_version;
  "component_checker",Composition_evidence.checker_version;
  "construct_checker",Reference_construct_evidence.checker_version;
  "molecular_checker",Reference_molecular_evidence.checker_version]
type callbacks={load:B.t->Reference_manifest.alphabet->I.t;collect:B.t->Reference_manifest.t->I.t;
  run:B.t->request:Reference_construct.Request.t->registry:Component_registry.t->
    manifests:(string*Reference_manifest.t)list->V.t;
  construct:B.t->V.t->Reference_construct.Candidate.t;
  export:B.t->request:Reference_construct.Request.t->construct:Reference_construct.Candidate.t->
    artifact:Reference_molecular.Artifact.t->registry:Component_registry.t->
    manifests:(string*Reference_manifest.t)list->line_width:int->Export.checked;
  package_version:unit->string;tool_versions:unit->(string*string)list}
let native_callbacks ~load ~collect ~package_version={load;collect;package_version;tool_versions=default_tool_versions;
  run=(fun budget ~request ~registry ~manifests->
    let upstream=U.run ~budget:(B.work budget) ~request ~registry ~manifests() in
    V.run ~budget:(B.work budget) upstream);
  construct=(fun _ build->V.construct build);
  export=(fun budget ~request ~construct ~artifact ~registry ~manifests ~line_width->
    Export.export_checked_owned budget ~request ~construct ~artifact ~registry ~manifests ~line_width())}
let codec budget=let limits=B.limits budget in Codec.make_limits
  ~max_bytes:(min limits.max_member_bytes Limits.max_response_bytes)
  ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
let json budget raw=
  let size=Codec.measure ~limits:(codec budget) raw in
  B.reserve budget(size.bytes+64*size.nodes+128);
  P.encode budget ~max_bytes:(B.limits budget).max_member_bytes raw
let fingerprint budget raw=Codec.fingerprint ~limits:(codec budget) raw
let sha budget bytes=B.charge budget(String.length bytes+1);B.reserve budget 128;Canonical.sha256 bytes
let sorted budget values=
  let rec count n bytes=function []->n,bytes| (key,_)::rest->
    B.charge budget(String.length key+1);
    require(n<(B.limits budget).max_entries)"Package member inventory exceeds its native bound.";
    count(n+1)(bytes+String.length key)rest in
  let count,bytes=count 0 0 values in
  let rec levels n=if n<=1 then 1 else 1+levels(n/2) in
  B.product budget(count+bytes+1)(4*levels count);B.reserve budget(128*count+128);
  List.sort(fun(a,_)(b,_)->String.compare a b)values
let tools budget values=
  let values=sorted budget values in
  B.reserve budget(128*List.length values+128);
  List.map(fun(id,version)->D.Tool.make budget ~id ~version ~content_fingerprint:(fingerprint budget(str version))())values
let manifests reference=[Reference_manifest.reference_set_id reference,reference]
type report_view={report_owner:B.t;passed:B.t->bool;document:B.t->Json.t;native_document:Json.t option}
let observed_report budget ~passed ~document=
  B.guard budget;B.reserve budget 192;{report_owner=budget;passed;document;native_document=None}
let native_report budget ~passed raw=
  let size=Codec.measure ~limits:(codec budget)raw in
  B.reserve budget(size.bytes+128*size.nodes+704);
  {report_owner=budget;passed=(fun owner->B.guard owner;passed);document=(fun owner->B.guard owner;raw);native_document=Some raw}
let native_report_document budget view=
  B.guard budget;require(view.report_owner==budget)"Package report belongs to another native lifetime.";
  match view.native_document with Some raw->raw|None->
    Diagnostic.fail "reference_package" "A host report cannot supply a native report capability."
type hooks={
  get:B.t->V.t->identity:string->C.Stage_record.t;
  result:B.t->V.t->identity:string->scope:string->C.Pipeline_result.t;
  composition:B.t->native:(unit->report_view)->request:Composition.t->registry:Component_registry.t->report_view;
  construct_check:B.t->native:(unit->report_view)->request:Reference_construct.Request.t->
    construct:Reference_construct.Candidate.t->registry:Component_registry.t->
    manifests:(string*Reference_manifest.t)list->report_view;
  molecular_check:B.t->native:(unit->report_view)->V.t->report_view}
let materialize_report budget ~native view=
  B.guard budget;
  require(view.report_owner==budget)"Package report view belongs to another native lifetime.";
  let passed=view.passed budget in B.guard budget;
  require passed "A current independent check failed during packaging.";
  let raw=view.document budget in B.guard budget;
  let size=Codec.measure ~limits:(codec budget)raw in
  B.reserve budget(size.bytes+128*size.nodes+512);
  (* A replaced host report may be observed, but only this actual fresh native
     result can authorize its full content. The default native view is memoized
     at its original callpoint, avoiding a duplicate independent check. *)
  let expected=native() in B.guard budget;
  require(expected.report_owner==budget && expected.passed budget)
    "A current independent check failed during packaging.";
  let current=expected.document budget in
  let left=Codec.encode ~limits:(codec budget)raw and right=Codec.encode ~limits:(codec budget)current in
  B.charge budget(String.length left+String.length right+1);
  require(String.equal left right)"Host package evidence disagrees with its fresh independent native check.";
  raw
let guard_build budget build=
  B.guard budget;
  require(U.budget(V.upstream build)==B.work budget)"Package pipeline belongs to another resource lifetime."
let admission budget target boundary=
  let raw=Build_request.Target.to_json target in
  let size=Codec.measure ~limits:(codec budget)raw in
  B.product budget(size.bytes+size.nodes+1)128;B.reserve budget(16*size.bytes+128*size.nodes+8192);
  ignore(Bioc_checker.Admission_check.require_software_use ~target ~boundary ~components:[])
type t={owner_value:B.t;request_value:D.Request.t;manifest_value:D.Manifest.t;data_value:string;
  archive_identity:string;build_value:V.t;records_value:C.Stage_record.t list;
  completion_value:C.Pipeline_result.t;files_value:Bioc_artifact.Stored_zip.entry list}
let build budget ~callbacks ?hooks ?load_prepared ?collect_files ?tool_pins ~request ?run_metadata()=
  B.charge budget 1;
  require(B.owns_retention budget)"Package construction requires one configured persistent-data owner.";
  let construct_request=D.Request.construct request in
  let target=Reference_construct.Request.target construct_request in
  admission budget target Admission.Export;
  let alphabet=match Build_request.Target.payload_format target with
    |"DNA"->Reference_manifest.DNA|"RNA"->Reference_manifest.RNA
    |_->Diagnostic.fail "reference_inputs" "The reviewed reference build supports only DNA or RNA." in
  let inputs=match load_prepared with
    |Some load->let value=load budget alphabet in Reference_build_inputs.require_owner budget value;value
    |None->let loaded=callbacks.load budget alphabet in I.require_owner budget loaded;
      Reference_build_inputs.prepare budget ~alphabet loaded in
  let reference=Reference_build_inputs.reference inputs and registry=Reference_build_inputs.registry inputs in
  let retained=match collect_files with
    |Some collect->collect budget reference
    |None->let retained=callbacks.collect budget reference in I.require_owner budget retained;
      require(Reference_manifest.fingerprint(I.manifest retained)=Reference_manifest.fingerprint reference)
        "Supplied manifest differs from the current pinned offline reference snapshot.";I.files retained in
  B.guard budget;
  let manifests=manifests reference in
  let build=callbacks.run budget ~request:construct_request ~registry ~manifests in guard_build budget build;
  let candidate=V.candidate build in
  let export_construct=callbacks.construct budget build in
  let checked_export=callbacks.export budget ~request:construct_request ~construct:export_construct
    ~artifact:candidate ~registry ~manifests ~line_width:(D.Request.fasta_line_width request) in
  Export.require_checked budget checked_export ~request:construct_request ~construct:export_construct
    ~artifact:candidate ~registry ~manifests ~line_width:(D.Request.fasta_line_width request);
  let exported=Export.checked_bundle checked_export in
  B.guard budget;
  let manager=V.manager build in
  let records=List.map(fun identity->
    let record=match hooks with None->M.get manager identity
      |Some hooks->hooks.get budget build ~identity in
    B.guard budget;
    require(C.Stage_record.id record=identity)"Package read returned another stage capability.";
    record)["components";"construct";"molecular"] in
  let completion=match hooks with None->M.result manager ~identity:"molecular" ~scope:"exact_cds"
    |Some hooks->hooks.result budget build ~identity:"molecular" ~scope:"exact_cds" in
  B.guard budget;
  require(C.Pipeline_result.artifact completion==List.nth records 2 && C.Pipeline_result.scope completion="exact_cds")
    "Package completion is not its actual molecular read/result capability.";
  let members=ref [] in
  let add path role bytes=
    B.charge budget(String.length path+String.length role+1);
    require(List.length !members<(B.limits budget).max_entries)"Package member inventory exceeds its native bound.";
    B.reserve budget(String.length bytes+String.length path+String.length role+192+64*(List.length !members+1));
    members:= !members@[path,(role,bytes)] in
  add "request.json" "request"(json budget(D.Request.to_json request));
  add "inputs/registry.json" "registry"(json budget(Component_registry.to_json registry));
  List.iter(fun record->let id=C.Stage_record.id record in
    add("stages/"^id^".json")(id^"-stage")(json budget(C.Stage_record.to_json record)))records;
  add "molecular.json" "molecular-specification"(X.specification exported);
  add "sequence.fasta" "sequence"(X.fasta exported);
  (match hooks with
  |None->
  let composition=Composition_check.check ~parent:(B.work budget)
    ~request:(Reference_construct.Request.composition construct_request) ~registry() in
  let construct=Construct_check.check ~parent:(B.work budget) ~request:construct_request
    ~candidate:(callbacks.construct budget build) ~registry ~manifests() in
  let molecular=V.check_result build in
  List.iter(fun raw->let size=Codec.measure ~limits:(codec budget)raw in
    B.reserve budget(size.bytes+128*size.nodes+512))
    [Composition_evidence.Result.to_json composition;Reference_construct_evidence.Result.to_json construct;
      C.Pipeline_result.to_json completion];
  let checks=["composition",Composition_evidence.Result.passed composition,Composition_evidence.Result.to_json composition;
    "construct",Reference_construct_evidence.Result.passed construct,Reference_construct_evidence.Result.to_json construct;
    "molecular",Reference_molecular_evidence.Result.passed molecular,Reference_molecular_evidence.Result.to_json molecular] in
  List.iter(fun(name,passed,raw)->require passed "A current independent check failed during packaging.";
    add("checks/"^name^".json")(name^"-check")(json budget raw))checks
  |Some _->
  let composition_native=lazy(
    let checked=Composition_check.check ~parent:(B.work budget)
      ~request:(Reference_construct.Request.composition construct_request) ~registry() in
    native_report budget ~passed:(Composition_evidence.Result.passed checked)(Composition_evidence.Result.to_json checked)) in
  let composition=match hooks with None->Lazy.force composition_native|Some hooks->
    hooks.composition budget ~native:(fun()->Lazy.force composition_native)
      ~request:(Reference_construct.Request.composition construct_request) ~registry in
  B.guard budget;
  (* Preserve the separate second read and eager constructor call before the
     first report's passed/to_dict observations. *)
  let checked_construct=callbacks.construct budget build in
  let construct_native=lazy(
    let checked=Construct_check.check ~parent:(B.work budget) ~request:construct_request
      ~candidate:checked_construct ~registry ~manifests() in
    native_report budget ~passed:(Reference_construct_evidence.Result.passed checked)(Reference_construct_evidence.Result.to_json checked)) in
  let construct=match hooks with None->Lazy.force construct_native|Some hooks->
    hooks.construct_check budget ~native:(fun()->Lazy.force construct_native) ~request:construct_request
      ~construct:checked_construct ~registry ~manifests in
  B.guard budget;
  let molecular_native=lazy(let checked=V.check_result build in
    native_report budget ~passed:(Reference_molecular_evidence.Result.passed checked)(Reference_molecular_evidence.Result.to_json checked)) in
  let molecular=match hooks with None->Lazy.force molecular_native|Some hooks->
    hooks.molecular_check budget ~native:(fun()->Lazy.force molecular_native)build in
  B.guard budget;
  let completion_size=Codec.measure ~limits:(codec budget)(C.Pipeline_result.to_json completion) in
  B.reserve budget(completion_size.bytes+128*completion_size.nodes+512);
  List.iter(fun(name,view,native)->
    let raw=materialize_report budget ~native view in
    add("checks/"^name^".json")(name^"-check")(json budget raw))
    ["composition",composition,(fun()->Lazy.force composition_native);
     "construct",construct,(fun()->Lazy.force construct_native);
     "molecular",molecular,(fun()->Lazy.force molecular_native)]
  );
  let raw_candidate=Reference_molecular.Artifact.to_json candidate in
  let first=match Json.array(field "records" raw_candidate)with value::_->value|[]->
    Diagnostic.fail "reference_package" "Checked molecular build has no sequence record." in
  B.reserve budget(8192+256*List.length records);
  let summary=Json.Object[
    "schema_version",str "biocompiler.reference_build_summary.v0.2";
    "intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
    "status",str(C.status_name(C.Pipeline_result.status completion));"scope",str(C.Pipeline_result.scope completion);
    "request_fingerprint",str(D.Request.fingerprint request);
    "selected_alternatives",field "references"(Reference_construct.Request.to_json construct_request);
    "feature_map",field "feature_statuses" first;
    "source_maps",Json.Object(List.map(fun record->C.Stage_record.id record,C.Stage_record.provenance record)records);
    "unresolved",Json.Array(List.map C.Scoped_obligation.to_json(C.Pipeline_result.unresolved completion));
    "model_locks",Json.Array[];
    "model_scope",str "Sequence-reference components supply no dynamic model or biological refinement evidence.";
    "upstream_intent",Json.Null;
    "upstream_scope",str "This component-root reference request has no accepted upstream intent or behavior realization."] in
  add "result.json" "build-summary"(json budget summary);
  List.iter(fun(path,bytes)->add("references/"^Reference_manifest.reference_set_id reference^"/"^path)
    "reference-input" bytes)retained;
  let entries=List.map(fun(path,(role,bytes))->D.File.make budget ~path ~role ~sha256:(sha budget bytes)
    ~byte_length:(Z.of_int(String.length bytes))())(sorted budget !members) in
  let stages=List.map(fun record->
    let stage=match C.Stage_record.id record with "components"->D.Accepted_stage.Components
      |"construct"->D.Accepted_stage.Construct|"molecular"->D.Accepted_stage.Molecular|_->assert false in
    D.Accepted_stage.make budget ~stage ~artifact_fingerprint:(fingerprint budget(C.Stage_record.payload record))
      ~record_fingerprint:(C.Stage_record.fingerprint record)
      ~artifact_schema:(Json.string(field "schema_version"(C.Stage_record.payload record)))())records in
  (* Keep the original late SDK lookup before the current module tool table. *)
  let package_version=callbacks.package_version() in B.guard budget;
  let toolchain=match tool_pins with None->tools budget(callbacks.tool_versions())|Some get->get budget in B.guard budget;
  let manifest=D.Manifest.make budget ~request_fingerprint:(D.Request.fingerprint request)
    ~files:entries ~accepted_stages:stages ~toolchain ~package_version() in
  let files=List.map(fun(path,(_,bytes))->path,bytes) !members in
  let data=A.assemble budget manifest files ?run_metadata() in
  let identity=sha budget data in B.reserve budget 256;
  {owner_value=budget;request_value=request;manifest_value=manifest;data_value=data;archive_identity=identity;
   build_value=build;records_value=records;completion_value=completion;files_value=files}
let request value=value.request_value
let manifest value=value.manifest_value
let data value=value.data_value
let archive_sha256 value=value.archive_identity
let build_fingerprint value=D.Manifest.fingerprint value.manifest_value
let owner value=value.owner_value
let molecular_build value=value.build_value
let records value=value.records_value
let completion value=value.completion_value
let files value=value.files_value

let tool_pins=tools
