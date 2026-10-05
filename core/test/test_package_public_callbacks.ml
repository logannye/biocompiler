(* Actual fresh native builds/checks plus trusted host operand observations.
   Forged host PASS/changed report data never supplies acceptance. *)
open Bioc_wire
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
module I=Bioc_reference_input.Reference_inputs
module S=Bioc_reference_package_service.Reference_package_workflow
module D=Bioc_reference_artifact.Reference_package_manifest
module M=Bioc_compiler.Pass_manager
module V=Bioc_pipeline.Reference_molecular_pipeline
module C=Bioc_domain.Pipeline_contract
let require value message=if not value then failwith message
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let set key value raw=Json.Object((key,value)::List.remove_assoc key(Json.object_fields raw))
let unhex raw=let digit=function '0'..'9'as c->Char.code c-48|'a'..'f'as c->Char.code c-87|_->failwith"Bad fixture hex"in
 String.init(String.length raw/2)(fun i->Char.chr(16*digit raw.[2*i]+digit raw.[2*i+1]))
let load path=let channel=open_in_bin path in let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
 let n=in_channel_length channel in require(n>0 && n<=8_388_608)"Bounded whole source witness";really_input_string channel n) in
 require(Canonical.sha256 raw="a867677f97540fcab473cbde9be813b42c139a06c4aa2fd0009e7cde9ed9f135")"Package authority witness changed";
 let rows=Json.array(get"cases"(Json.parse_artifact ~max_bytes:8_388_608 ~max_nodes:500_000 raw)) in
 get"input"(List.find(fun raw->text"id"raw="DNA:default")rows)
let owner()=B.create_owner ~parent:(W.create ~profile:"package.callbacks.test" ~error_code:"package_callbacks_work"
 ~maximum:10_000_000_000())~retain_bytes:(fun _->())()
let files input=List.map(function Json.Array[Json.String name;Json.String bytes]->name,unhex bytes
 |_->failwith"Bad source file pair")(Json.array(get"files"input))
type mutation=Native|Forged_report|False_report|Raised_read|Imported_result
let run input mode=
 let budget=owner() and log=ref[] and native_forced=ref[] in
 let add name=log:= !log@[name] in
 let source=S.native_callbacks ~load:(fun b _->I.validate_snapshot b ~files:(files input))
   ~collect:(fun b reference->I.collect_snapshot b ~reference ~files:(files input))
   ~package_version:(fun()->text"package_version"input) in
 let source={source with construct=(fun b build->add"construct-read";source.construct b build)} in
 let check name native=
   add(name^"-call");
   let actual=if mode=Native then begin native_forced:= !native_forced@[name];Some(native())end else None in
   S.observed_report budget ~passed:(fun _->add(name^"-passed");mode<>False_report)
    ~document:(fun _->add(name^"-document");
      if mode=Raised_read then raise Exit;
      let original=match actual with Some value->value|None->native_forced:= !native_forced@[name];native()in
      let raw=S.native_report_document budget original in
      if mode=Forged_report then set"claim_scope"(Json.String"unsupported acceptance")raw else raw) in
 let hooks:S.hooks={get=(fun _ build ~identity->add("get:"^identity);M.get(V.manager build)identity);
   result=(fun _ build ~identity ~scope->add"result";let result=M.result(V.manager build)~identity ~scope in
     if mode=Imported_result then C.Pipeline_result.of_json(C.Pipeline_result.to_json result)else result);
   composition=(fun _ ~native ~request:_ ~registry:_->check"composition"native);
   construct_check=(fun _ ~native ~request:_ ~construct:_ ~registry:_ ~manifests:_->check"construct"native);
   molecular_check=(fun _ ~native _->check"molecular"native)} in
 let result=try Ok(S.build budget ~callbacks:source ~hooks ~request:(D.Request.of_json budget(get"request"input))())
   with error->Error error in
 result,!log,!native_forced
let reports input=
 let result,log,forced=run input Native in ignore(Result.get_ok result);
 require(log=["construct-read";"get:components";"get:construct";"get:molecular";"result";
  "composition-call";"construct-read";"construct-call";"molecular-call";
  "composition-passed";"composition-document";"construct-passed";"construct-document";
  "molecular-passed";"molecular-document"])"Public checker/getter/read cadence changed";
 require(forced=["composition";"construct";"molecular"])"Native default report was not forced at its actual callpoint";
 List.iter(fun mode->let result,log,forced=run input mode in
  match mode,result with
  |False_report,Error(Diagnostic.Error error)->require(error.code="reference_package" && forced=[] &&
     List.hd(List.rev log)="composition-passed")"False report triggered a later document/check"
  |Forged_report,Error(Diagnostic.Error error)->require(error.code="reference_package" &&
     error.message="Host package evidence disagrees with its fresh independent native check.")"Forged report acquired acceptance"
  |Raised_read,Error Exit->require(List.hd(List.rev log)="composition-document")"Original report exception was changed"
  |Imported_result,Error(Diagnostic.Error error)->require(error.code="reference_package" &&
      not(List.mem"composition-call"log))"Imported result was treated as actual read/result capability"
  |_->failwith"Package host-observation control returned unexpectedly")
  [False_report;Forged_report;Raised_read;Imported_result]
let reads input=
 let source=files input in
 let trial first_bad second_bad=
  let scope=owner()and events=ref[]in
  let read name path=events:= !events@[name^":"^path];
   let bytes=List.assoc path source in
   if (first_bad && name="first-file") || (second_bad && name="source-second") then bytes^"changed"else bytes in
  let reader:I.reader={manifest_first=(fun()->read"manifest-first""manifest.json");retained_first=read"first-file";
    manifest_second=(fun()->read"manifest-second""manifest.json");source_second=read"source-second";
    review_second=read"review-second"}in
  let outcome=try Ok(I.load_snapshot scope ~reader)with error->Error error in outcome,!events in
 let result,events=trial false false in
 let result=Result.get_ok result in
 require(I.files result=I.files(I.validate_snapshot(owner())~files:source))"Actual two-read snapshot changed canonical bytes";
 require(List.hd events="manifest-first:manifest.json" && List.mem"manifest-second:manifest.json"events)
   "Native snapshot collapsed separate filesystem reads";
 let first,events=trial true false in
 (match first with Error(Diagnostic.Error error)->require(error.code="reference_inputs")"First bytes did not fail closed"|_->failwith"Altered first bytes accepted");
 require(not(List.mem"manifest-second:manifest.json"events))"First mismatch read later filesystem state";
 let second,events=trial false true in
 (match second with Error(Diagnostic.Error error)->require(error.code="reference_inputs")"Second bytes did not fail closed"|_->failwith"Altered second bytes accepted");
 require(not(List.exists(String.starts_with ~prefix:"review-second:")events))"Second source mismatch still read review evidence"
let prepared_inputs input=
 let budget=owner() and load_calls=ref 0 and collect_calls=ref 0 in
 let snapshot=I.validate_snapshot budget ~files:(files input) in
 let module Inputs=Bioc_reference_package_service.Reference_build_inputs in
 let prepared=Inputs.prepare budget ~alphabet:Bioc_domain.Reference_manifest.DNA snapshot in
 let source=S.native_callbacks ~load:(fun _ _->failwith"Prepared load was recomputed")
   ~collect:(fun _ _->failwith"Actual collection was replaced")
   ~package_version:(fun()->text"package_version"input) in
 let request=D.Request.of_json budget(get"request"input) in
 let load_prepared b _=require(b==budget)"Prepared load changed its owner";incr load_calls;prepared in
 let collect_files b _=require(b==budget)"Collection changed its owner";incr collect_calls;I.files snapshot in
 let built=S.build budget ~callbacks:source ~load_prepared ~collect_files ~request() in
 require(!load_calls=1 && !collect_calls=1)"Actual loader/collector callpoint repeated";
 require(S.request built==request)"Build replaced the original request capability";
 let foreign=Inputs.supplied(owner()) ~request:(Inputs.request prepared)
   ~reference:(Inputs.reference prepared) ~registry:(Inputs.registry prepared) in
 (match S.build budget ~callbacks:source ~load_prepared:(fun _ _->foreign) ~request() with
 |_->failwith"Foreign prepared input owner was accepted"
 |exception Diagnostic.Error error->require(error.code="reference_input_owner")"Foreign prepared capability did not fail closed");
 let exported=ref [] in
 let module Export=Bioc_reference_export.Reference_sequence_export in
 let build=S.molecular_build built in
 let observe_check ~native=
   exported:= !exported@["called"];
   let first=native() and second=native() in
   require(first==second)"Captured default export checker was recomputed";
   exported:= !exported@["passed"];
   require(Bioc_domain.Reference_molecular_evidence.Result.passed first)"Original export checker failed";
   ignore(Bioc_domain.Reference_molecular_evidence.Result.diagnostics first);
   exported:= !exported@["diagnostics"] in
 ignore(Export.export_checked_owned ~observe_check budget ~request:(D.Request.construct request)
   ~construct:(V.construct build) ~artifact:(V.candidate build) ~registry:(Inputs.registry prepared)
   ~manifests:[Bioc_domain.Reference_manifest.reference_set_id(Inputs.reference prepared),Inputs.reference prepared]
   ~line_width:(D.Request.fasta_line_width request)());
 require(!exported=["called";"passed";"diagnostics"])"Export report observation order changed"
let ()=require(Array.length Sys.argv=2)"Expected the complete package authority corpus";
 let input=load Sys.argv.(1)in reports input;reads input;prepared_inputs input;
 print_endline"Native package public cadence, prepared ownership, export observations, forged reports and two-read snapshots passed"
