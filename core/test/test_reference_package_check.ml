open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
module A=Bioc_reference_artifact.Reference_package_container
module D=Bioc_reference_artifact.Reference_package_manifest
module P=Bioc_artifact.Utf8_pretty
module V=Bioc_reference_package_check.Reference_package_check
let require value message=if not value then failwith message
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let parent maximum=W.create ~profile:"package.check.fixture" ~error_code:"package_check_fixture_work" ~maximum()
let budget ?(limits=B.defaults)()=B.create_owner ~parent:(parent 10_000_000_000) ~retain_bytes:(fun _->()) ~limits()
let unhex raw=
  require(String.length raw mod 2=0)"Invalid original package bytes";
  let nibble=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith "Invalid original hex" in
  String.init(String.length raw/2)(fun i->Char.chr(16*nibble raw.[2*i]+nibble raw.[2*i+1]))
let tools input=[
  "reference_build","biocompiler.reference_build.v0.2";
  "human_admission_policy",Admission.policy_version;
  "reference_inputs",Bioc_reference_input.Reference_inputs.inputs_version;
  "archive","biocompiler.reference_archive.v0.4";
  "sequence_export",Bioc_reference_export.Reference_sequence_codec.export_version;
  "sequence_emitter","biocompiler.reference_sequence_emitter.v0.2";
  "construct_pipeline","biocompiler.reference_construct_pipeline.v0.2";
  "molecular_pipeline","biocompiler.exact_cds_pipeline.v0.1";
  "reference_adapter",Reference_components.adapter_version;
  "construct_generator","biocompiler.reference_construct_generator.v0.1";
  "component_checker",Composition_evidence.checker_version;
  "construct_checker",Reference_construct_evidence.checker_version;
  "molecular_checker",(if get "changed_tool" input=Json.Bool true then "fixture-current-checker" else Reference_molecular_evidence.checker_version)]
let authority budget input=V.authority budget ~package_version:(text "package_version" input) ~tool_versions:(tools input)
let data row=unhex(text "data"(get "value"(get "outcome" row)))
let execute ?limits row=
  let scope=budget ?limits() in let input=get "input" row in
  let current=authority scope input in
  let request=D.Request.of_json scope(get "request" input) in
  let checked=V.verify scope ~authority:current ~expected_request:request(data row) in scope,current,request,checked
let caught callback=try callback();failwith "Forged package acquired independent acceptance"
  with Diagnostic.Error error->require(error.code="reference_package_check")
    ("Wrong independent checker rejection: "^error.code^": "^error.message)
let rejected callback=try callback();failwith "Expected bounded failure"with Diagnostic.Error _->()
let literals path=
  let channel=open_in_bin path in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->let size=in_channel_length channel in
    require(size>0 && size<=8_388_608)"Package witness byte bound";really_input_string channel size) in
  require(Canonical.sha256 raw="a867677f97540fcab473cbde9be813b42c139a06c4aa2fd0009e7cde9ed9f135")
    "Complete original package witness changed";
  let root=Json.parse_artifact ~max_bytes:8_388_608 ~max_nodes:500_000 raw in
  require(text "schema" root="biocompiler.reference_package_workflow_literals.v1")"Package witness schema changed";
  let cases=Json.array(get "cases" root) in
  require(List.map(text "id")cases=["DNA:default";"RNA:default";"DNA:width1";"RNA:width10000";
    "DNA:run-metadata";"DNA:current-sdk";"RNA:current-tool";"DNA:unsupported-layout"])
    "Complete package case census changed";
  let successful=List.filter(fun row->text "status"(get "outcome" row)="return")cases in
  List.iter(fun row->let scope,current,request,checked=execute row in
    V.require_checked scope checked ~authority:current ~expected_request:request(data row);
    require(text "outcome"(V.report checked)="pass")"Actual independent package checker did not pass";
    require(V.archive_sha256 checked=text "archive_sha256"(get "value"(get "outcome" row)))"Archive authority changed";
    require(V.build_fingerprint checked=text "build_fingerprint"(get "value"(get "outcome" row)))"Build identity changed";
    require(D.Request.fingerprint(V.request checked)=D.Request.fingerprint request)"Independent request binding changed")successful;
  successful
let replace key value raw=Json.Object(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let rec at path change raw=match path with []->change raw|key::rest->replace key(at rest change(get key raw))raw
let repair ?(manifest_change=Fun.id) row ~file ~change=
  let scope=budget() in let original=A.read scope(data row) in
  let old_manifest=A.manifest original in
  let files=List.map(fun(name,raw)->name,if name=file then change scope raw else raw)(A.files original) in
  let entries=List.map(fun prior->let path=D.File.path prior in let raw=List.assoc path files in
    D.File.make scope ~path ~role:(D.File.role prior) ~sha256:(Canonical.sha256 raw) ~byte_length:(Z.of_int(String.length raw))())
    (D.Manifest.files old_manifest) in
  (* Repair BOTH archive member hashes and all record/payload fingerprints. A
     successful rejection must therefore be semantic, beyond container integrity. *)
  let stages=List.map(fun prior->let stage=D.Accepted_stage.stage prior in
    let id=D.Accepted_stage.name stage in
    let raw=Json.parse_artifact ~max_bytes:16_777_216 ~max_nodes:250_000(List.assoc("stages/"^id^".json")files) in
    let record=Pipeline_contract.Stage_record.of_json raw in
    D.Accepted_stage.make scope ~stage ~artifact_fingerprint:(Canonical.fingerprint(Pipeline_contract.Stage_record.payload record))
      ~record_fingerprint:(Pipeline_contract.Stage_record.fingerprint record)
      ~artifact_schema:(text "schema_version"(Pipeline_contract.Stage_record.payload record))())(D.Manifest.accepted_stages old_manifest) in
  let manifest=D.Manifest.make scope ~request_fingerprint:(D.Manifest.request_fingerprint old_manifest)
    ~files:entries ~accepted_stages:stages ~toolchain:(D.Manifest.toolchain old_manifest)
    ~package_version:(D.Manifest.package_version old_manifest)() in
  let manifest=D.Manifest.of_json scope(manifest_change(D.Manifest.to_json manifest)) in
  let raw=A.assemble scope manifest files ?run_metadata:(A.run_metadata original)() in
  ignore(A.read(budget())raw);raw
let json_change path change budget raw=
  let value=Json.parse_artifact ~max_bytes:16_777_216 ~max_nodes:250_000 raw in
  P.encode budget ~max_bytes:16_777_216(at path change value)
let semantic_mutants row=
  let mutations=[
    "stages/molecular.json",["accepted"],(fun _->Json.Bool false);
    "stages/molecular.json",["checks";"sequence_identity";"evidence";"claim_scope"],(fun _->Json.String "forged PASS scope");
    "stages/construct.json",["checks";"layout";"dependencies";"references"],(fun _->Json.String(Canonical.sha256 "stale"));
    "stages/components.json",["provenance";"authority"],(fun _->Json.String "imported-acceptance");
    "stages/molecular.json",["provenance";"source_links"],(fun _->Json.Array[]);
    "stages/molecular.json",["discharged"],(fun _->Json.Array[Json.String "molecular_behavior"]);
    "checks/molecular.json",["claim_scope"],(fun _->Json.String "therapeutic acceptance");
    "result.json",["unresolved"],(fun _->Json.Array[]);
    "result.json",["human_therapeutic_admission"],(fun _->Json.String "admitted")] in
  List.iter(fun(file,path,change)->let forged=repair row ~file ~change:(json_change path change) in
    let scope=budget() and input=get "input" row in
    let current=authority scope input and request=D.Request.of_json scope(get "request" input) in
    caught(fun()->ignore(V.verify scope ~authority:current ~expected_request:request forged)))mutations;
  let forged=repair row ~file:"sequence.fasta" ~change:(fun _ raw->raw^"A") in
  let scope=budget() and input=get "input" row in
  caught(fun()->ignore(V.verify scope ~authority:(authority scope input)
    ~expected_request:(D.Request.of_json scope(get "request" input))forged));
  let forged=repair ~manifest_change:(replace "package_version"(Json.String "forged-sdk"))row
    ~file:"request.json" ~change:(fun _ raw->raw) in
  let scope=budget() in caught(fun()->ignore(V.verify scope ~authority:(authority scope input)
    ~expected_request:(D.Request.of_json scope(get "request" input))forged))
let binding_controls row=
  let scope,current,request,checked=execute row in
  let foreign=budget() in
  caught(fun()->V.require_checked foreign checked ~authority:current ~expected_request:request(data row));
  let changed=V.authority scope ~package_version:"different-sdk" ~tool_versions:(tools(get "input" row)) in
  caught(fun()->V.require_checked scope checked ~authority:changed ~expected_request:request(data row));
  caught(fun()->V.require_checked scope checked ~authority:current ~expected_request:request(data row^"x"));
  caught(fun()->V.require_checked scope checked ~authority:current ~expected_build_fingerprint:(V.build_fingerprint checked)(data row));
  let fresh=budget() in
  caught(fun()->ignore(V.verify fresh ~authority:(authority fresh(get "input" row))(data row)));
  let fresh=budget() in
  caught(fun()->ignore(V.verify fresh ~authority:(authority fresh(get "input" row))
    ~expected_build_fingerprint:(Canonical.sha256 "wrong")(data row)));
  let fresh=budget() in
  ignore(V.verify fresh ~authority:(authority fresh(get "input" row)) ~expected_build_fingerprint:(V.build_fingerprint checked)(data row));
  let cyclic=let rec values=("reference_build","v1")::values in values in
  caught(fun()->ignore(V.authority(budget()) ~package_version:"v1" ~tool_versions:cyclic));
  caught(fun()->ignore(V.authority(budget()) ~package_version:"v1" ~tool_versions:[]))
let resources row=
  let scope,_,_,_=execute row in let retained=B.retained scope and charged=(B.limits scope).max_work-W.remaining(B.work scope) in
  ignore(execute ~limits:(B.make_limits ~max_retained_bytes:retained ~max_work:charged())row);
  rejected(fun()->ignore(execute ~limits:(B.make_limits ~max_retained_bytes:(retained-1)())row));
  rejected(fun()->ignore(execute ~limits:(B.make_limits ~max_work:(charged-1)())row));
  rejected(fun()->ignore(execute ~limits:(B.make_limits ~max_member_bytes:128())row))
let ()=
  Printexc.record_backtrace true;
  try
    require(Array.length Sys.argv=2)"Usage: test_reference_package_check PACKAGE_LITERALS";
    let cases=literals Sys.argv.(1) in let first=List.hd cases in
    semantic_mutants first;binding_controls first;resources first;
    print_endline "Independent reference package byte, evidence, authority and resource checks passed."
  with Diagnostic.Error error->prerr_endline(error.code^": "^error.message);raise(Diagnostic.Error error)
