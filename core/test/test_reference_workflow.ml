open Bioc_wire
open Bioc_domain
module F=Bioc_pipeline_service.Reference_workflow
module C=Pipeline_contract
module M=Bioc_compiler.Pass_manager
module W=Bioc_checker.Work_budget
module P=Bioc_pipeline.Reference_construct_pipeline
module Q=Bioc_pipeline.Reference_molecular_pipeline
module R=Reference_construct
module H=Bioc_pipeline_service.Host_bridge
let require condition message=if not condition then failwith message
let required=function Some value->value|None->failwith "Missing test capability"
let expect code action=try ignore(action());failwith("Expected "^code) with Diagnostic.Error error->
  require(error.code=code)("Unexpected diagnostic "^error.code^": "^error.message)
let budget()=W.create ~profile:"reference.workflow.test" ~error_code:"reference_workflow_test_work" ~maximum:2_000_000_000 ()
let load directory identity=
  let channel=open_in_bin(Filename.concat directory(identity^".json")) in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let size=in_channel_length channel in require(size>0 && size<=Limits.max_request_bytes)"Unbounded source authority";
    really_input_string channel size) in
  let value=Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes raw in
  require(Canonical.fingerprint value=identity)"Original caller authority changed";value
let snapshot owner=M.inspect owner ~provider_identity:(fun _->"native-provider")
let keys key value=List.map fst(Json.object_fields(Json.field key(Json.object_fields value)))
let make_state ?(maximum=max_int) work=
  let retained=ref 0 in
  let retain_bytes amount=
    Diagnostic.require(amount>=0 && amount<=maximum- !retained) "workflow_test_retention" "Workflow retention exhausted.";
    retained:= !retained+amount in
  F.create ~budget:work ~retain_bytes (),retained
let notice state work owner sequence operation=F.notice state ~budget:work ~owner ~sequence operation
let initialize state work request registry manifests=
  F.initialize_construct state ~budget:work ~request ~registry ~manifests ()
let admission state work owner request=
  let value=F.prepare_admission state ~budget:work () in
  let contract=P.admission_contract value and validators=P.admission_validators value in
  M.register_component_input owner contract ~validators;
  notice state work owner 10(F.Input_registered(contract,validators));
  let record=M.admit_component_input owner ~contract_id:"reference_components" ~identity:"components"(R.Request.to_json request) in
  notice state work owner 11(F.Admitted{contract_id="reference_components";identity="components";record});
  let record=M.get owner "components" in notice state work owner 12(F.Got{identity="components";record});value
let registration state work owner=
  let value=F.prepare_construct_registration state ~budget:work () in
  let contract=P.contract value and producer=P.producer value and validators=P.validators value in
  M.register owner contract ~producer ~validators;
  notice state work owner 20(F.Pass_registered(contract,producer,validators));value
let construct_result state work owner=
  let record=M.run owner ~pass_id:"components_to_construct" ~input_id:"components" ~output_id:"construct" () in
  notice state work owner 21(F.Ran{pass_id="components_to_construct";input_id="components";output_id="construct";
    default_configuration=true;record});
  let result=M.result owner ~identity:"construct" ~scope:"reference_construct" in
  notice state work owner 22(F.Result_returned{identity="construct";scope="reference_construct";result});record,result
let complete ?maximum request registry manifests=
  let work=budget() in let state,retained=make_state ?maximum work in
  expect "reference_workflow_phase" (fun()->F.prepare_admission state ~budget:work ());
  let published=ref None in
  let owner=F.initialize_construct state ~budget:work ~request ~registry ~manifests
    ~manager_created:(fun actual owner->
      require(actual==work && required(F.owner state)==owner && F.phase state=F.Initializing)"Manager was not retained before publication";
      require(keys "records"(snapshot owner)=[])"Publication followed admission";published:=Some owner) () in
  require(owner==required !published)"Publication owner changed";
  expect "reference_workflow_phase" (fun()->initialize state work request registry manifests);
  ignore(admission state work owner request);ignore(registration state work owner);
  let record,result=construct_result state work owner in
  require(C.Pipeline_result.artifact result==record)"Typed result lost exact run-record identity";
  expect "reference_workflow_capability" (fun()->F.finish_construct state ~budget:work ~record ~result_sequence:21);
  let clone=C.Stage_record.of_json(C.Stage_record.to_json record) in
  expect "reference_workflow_capability" (fun()->F.finish_construct state ~budget:work ~record:clone ~result_sequence:22);
  let build=F.finish_construct state ~budget:work ~record ~result_sequence:22 in
  require(P.record build==record && P.result build==result && P.manager build==owner)"Construct finish reconstructed capabilities";
  expect "reference_workflow_phase" (fun()->F.finish_construct state ~budget:work ~record ~result_sequence:22);
  let prepared=F.prepare_molecular state ~budget:work () in
  let dependencies=Q.dependencies prepared in require(List.length dependencies=6)"Molecular root census changed";
  let first=List.hd dependencies and second=List.nth dependencies 1 in
  let set sequence (key,value)=M.set_dependency owner key value;notice state work owner sequence(F.Dependency_set(key,value)) in
  (* Real out-of-order and duplicate writes are not undone and cannot stand in
     for the missing next required operation. Distinct sequence IDs may finish
     out of order through actual nested callbacks. *)
  set 42 second;
  expect "reference_workflow_phase" (fun()->F.prepare_molecular_profile state ~budget:work ());
  set 40 first;set 41 first;
  expect "reference_workflow_phase" (fun()->F.prepare_molecular_profile state ~budget:work ());
  List.iteri(fun index dependency->set(43+index)dependency)(List.tl dependencies);
  let profile=F.prepare_molecular_profile state ~budget:work () in
  let completion=Q.completion_profile profile in
  M.register_completion_profile owner completion;notice state work owner 50(F.Profile_registered completion);
  let registration=F.prepare_molecular_registration state ~budget:work () in
  let contract=Q.contract registration and producer=Q.producer registration and validators=Q.validators registration in
  M.register owner contract ~producer ~validators;notice state work owner 51(F.Pass_registered(contract,producer,validators));
  let molecular=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  notice state work owner 52(F.Ran{pass_id="construct_to_molecular";input_id="construct";output_id="molecular";
    default_configuration=true;record=molecular});
  let molecular_result=M.result owner ~identity:"molecular" ~scope:"exact_cds" in
  notice state work owner 53(F.Result_returned{identity="molecular";scope="exact_cds";result=molecular_result});
  let before= !retained in
  (* Historical finish consumes saved results even after an ordinary later
     mutation makes fresh reads fail. It never synthesizes another result. *)
  M.set_dependency owner "layout"(Canonical.sha256 "later mutation");
  notice state work owner 54(F.Dependency_set("layout",Canonical.sha256 "later mutation"));
  expect "pipeline_error" (fun()->M.get owner "molecular");
  let final=F.finish_molecular state ~budget:work ~record:molecular ~result_sequence:53 in
  require(Q.upstream final==build && Q.record final==molecular && Q.result final==molecular_result)"Molecular finish lost original capabilities";
  require(required(F.construct_build state)==build && required(F.molecular_build state)==final)"Historical build caches changed";
  require(F.construct_result_sequence state=Some 22 && F.molecular_result_sequence state=Some 53)"Result command ownership changed";
  require(!retained>before)"Final native build was not cumulatively reserved";
  expect "reference_workflow_phase" (fun()->F.finish_molecular state ~budget:work ~record:molecular ~result_sequence:53);
  F.close state;require(F.owner state=None && F.construct_build state=None)"Close retained live capabilities";
  expect "reference_workflow_closed" (fun()->F.prepare_molecular state ~budget:work ());
  !retained
let boundaries request registry manifests=
  let work=budget() in let state,_=make_state work in let owner=initialize state work request registry manifests in
  expect "reference_workflow_budget" (fun()->F.prepare_admission state ~budget:(budget()) ());
  (* A foreign owner must itself be a valid manager; otherwise construction
     rejects the missing request before the workflow ownership check runs. *)
  let other=M.create ~budget:work ~target:(R.Request.target request)
    ~dependencies:["request",R.Request.fingerprint request] () in
  expect "reference_workflow_owner" (fun()->notice state work other 1(F.Dependency_set("unrelated",Canonical.sha256 "x")));
  M.set_dependency owner "unrelated"(Canonical.sha256 "x");
  notice state work owner 1(F.Dependency_set("unrelated",Canonical.sha256 "x"));
  expect "reference_workflow_sequence" (fun()->notice state work owner 1(F.Dependency_set("unrelated",Canonical.sha256 "x")));
  require(F.phase state=F.Construct_created)"Generic call changed reserved phase";
  let value=F.prepare_admission state ~budget:work () in
  let contract=P.admission_contract value and validators=P.admission_validators value in
  M.register_component_input owner contract ~validators;
  (* A real registration without its trusted completion notice cannot authorize
     the next explicit phase. A made-up same-value record cannot replace get. *)
  expect "reference_workflow_phase" (fun()->F.prepare_construct_registration state ~budget:work ());
  notice state work owner 3(F.Input_registered(contract,validators));
  let record=M.admit_component_input owner ~contract_id:"reference_components" ~identity:"components"(R.Request.to_json request) in
  notice state work owner 4(F.Admitted{contract_id="reference_components";identity="components";record});
  let clone=C.Stage_record.of_json(C.Stage_record.to_json record) in
  notice state work owner 5(F.Got{identity="components";record=clone});
  require(F.phase state=F.Admission_returned)"Equal-content get substitute advanced workflow";
  let actual=M.get owner "components" in notice state work owner 6(F.Got{identity="components";record=actual});
  ignore(registration state work owner);
  let record=M.run owner ~pass_id:"components_to_construct" ~input_id:"components" ~output_id:"construct" () in
  notice state work owner 21(F.Ran{pass_id="components_to_construct";input_id="components";output_id="construct";default_configuration=true;record});
  let result=M.result owner ~identity:"construct" ~scope:"reference_construct" in
  let imported=C.Pipeline_result.of_json(C.Pipeline_result.to_json result) in
  notice state work owner 22(F.Result_returned{identity="construct";scope="reference_construct";result=imported});
  require(F.phase state=F.Construct_ran)"Serialized acceptance result advanced workflow";
  notice state work owner 23(F.Result_returned{identity="construct";scope="reference_construct";result});
  ignore(F.finish_construct state ~budget:work ~record ~result_sequence:23)
let failure_lifetime request registry manifests=
  let marker=Failure "actual publication exception" and work=budget() in let state,_=make_state work in
  (try ignore(F.initialize_construct state ~budget:work ~request ~registry ~manifests
    ~manager_created:(fun _ _->raise marker)());failwith "Publication did not raise"
   with error->require(error==marker)"Publication exception was replaced");
  require(F.phase state=F.Interrupted && Option.is_some(F.owner state))"Publication exception lost native manager";
  let owner=required(F.owner state) in require(keys "records"(snapshot owner)=[])"Publication exception admitted input";
  M.set_dependency owner "still_usable"(Canonical.sha256 "yes");
  notice state work owner 1(F.Dependency_set("still_usable",Canonical.sha256 "yes"));
  require(F.phase state=F.Interrupted)"Generic operation resurrected interrupted workflow";
  let work=budget() in let state,_=make_state ~maximum:2048 work in
  expect "workflow_test_retention" (fun()->initialize state work request registry manifests);
  require(F.owner state=None && F.phase state=F.Interrupted)"Early exhaustion invented a manager";
  let work=budget() in let state,_=make_state work in let owner=initialize state work request registry [] in
  let admission=F.prepare_admission state ~budget:work () in
  let contract=P.admission_contract admission and validators=P.admission_validators admission in
  M.register_component_input owner contract ~validators;notice state work owner 1(F.Input_registered(contract,validators));
  let record=M.admit_component_input owner ~contract_id:"reference_components" ~identity:"components"(R.Request.to_json request) in
  notice state work owner 2(F.Admitted{contract_id="reference_components";identity="components";record});
  require(not(C.Stage_record.accepted record))"Missing references admitted authority";
  expect "pipeline_error" (fun()->M.get owner "components");
  expect "reference_workflow_phase" (fun()->F.prepare_construct_registration state ~budget:work ());
  require(keys "records"(snapshot owner)=["components"] && keys "passes"(snapshot owner)=[])"Rejected admission lost partial state"
let generator_failure request registry manifests=
  let work=budget() in let state,_=make_state work in let owner=initialize state work request registry manifests in
  ignore(admission state work owner request);
  let marker=Failure "actual generator exception" in
  let generator_bridge:P.generator_bridge={generate=(fun _ ~input:_ _->raise marker);
    host_proposal=(fun _ ~output:_ ~source_links:_->failwith "Generator failure reached proposal construction")} in
  let registration=F.prepare_construct_registration state ~budget:work ~generator_bridge () in
  let contract=P.contract registration and producer=P.producer registration and validators=P.validators registration in
  M.register owner contract ~producer ~validators;notice state work owner 20(F.Pass_registered(contract,producer,validators));
  (try ignore(M.run owner ~pass_id:"components_to_construct" ~input_id:"components" ~output_id:"construct"());
    failwith "Generator did not raise" with error->require(error==marker)"Generator exception identity changed");
  require(F.phase state=F.Construct_registered && required(F.owner state)==owner)"Generator error lost live phase/owner";
  require(keys "records"(snapshot owner)=["components"] && keys "passes"(snapshot owner)=["components_to_construct"])
    "Generator error discarded admission/registration or invented output";
  let record=M.get owner "components" in notice state work owner 21(F.Got{identity="components";record});
  require(C.Stage_record.accepted record && F.phase state=F.Construct_registered)"Failed generator made ordinary reads unusable"
let closed_callbacks request registry manifests=
  let work=budget() in let state,_=make_state work in
  expect "reference_workflow_closed" (fun()->F.initialize_construct state ~budget:work ~request ~registry ~manifests
    ~manager_created:(fun _ _->F.close state)());
  require(F.phase state=F.Closed && F.owner state=None)"Publication reopened a closed owner";
  let work=budget() in let state,_=make_state work in ignore(initialize state work request registry manifests);
  expect "reference_workflow_closed" (fun()->F.prepare_admission state ~budget:work
    ~provider_observer:(fun _ _ _ _->F.close state)());
  require(F.phase state=F.Closed && F.owner state=None)"Provider observation reopened a closed owner"
let sidecars request registry manifests=
  let work=budget() in let state,_=make_state work in let owner=initialize state work request registry manifests in
  let value=F.prepare_admission state ~budget:work () in
  let contract=P.admission_contract value and expected=P.admission_validators value in
  let called=ref false in
  let replacement _ _=called:=true;failwith "Unreviewed replacement acquired host sidecars" in
  let validators=["reference_authority",replacement;"component_linkage",List.assoc "component_linkage" expected] in
  M.register_component_input owner contract ~validators;notice state work owner 1(F.Input_registered(contract,validators));
  let context=C.Pass_context.make ~input:(R.Request.to_json request) ~output:None ~target:(R.Request.target request)
    ~configuration:(Json.Object[]) ~dependencies:[] ~requirements:(C.Component_input_contract.requirements contract) () in
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->failwith "Linkage inspected opaque source links")() in
  let link=H.of_reference bridge(Json.Object["handle",Json.String "object/0"]) in
  let host_links=Some[link] in
  expect "pipeline_error" (fun()->M.invoke_provider owner ~host_links replacement context);
  require(not !called)"Replacement was invoked through an unauthorized sidecar";
  expect "pipeline_error" (fun()->M.invoke_provider owner ~host_links(List.assoc "reference_authority" expected)context);
  (match M.invoke_provider owner ~host_links(List.assoc "component_linkage" expected)context with
    |M.Decision _->()|_->failwith "Shared linkage validator changed callback kind")
let final_source_bridge request registry manifests mode=
  let work=budget() in let state,retained=make_state work in
  let owner=initialize state work request registry manifests in
  ignore(admission state work owner request);ignore(registration state work owner);
  let record,_=construct_result state work owner in
  let upstream=F.finish_construct state ~budget:work ~record ~result_sequence:22 in
  let authored:Q.authority={request=R.Request.of_json(R.Request.to_json request);
    registry=Component_registry.of_json(Component_registry.to_json registry);
    manifests=List.map(fun(key,value)->key,Reference_manifest.of_json(Reference_manifest.to_json value))manifests} in
  let before= !retained in
  let prepared=F.prepare_molecular ~authority:authored state ~budget:work () in
  require(Q.prepared_authority prepared==authored && !retained>before)
    "Explicit molecular authority was not retained under its existing owner";
  List.iteri(fun index(key,value)->M.set_dependency owner key value;
    notice state work owner (30+index)(F.Dependency_set(key,value)))(Q.dependencies prepared);
  let profile=F.prepare_molecular_profile state ~budget:work () in
  let completion=Q.completion_profile profile in
  M.register_completion_profile owner completion;notice state work owner 40(F.Profile_registered completion);
  let registration=F.prepare_molecular_registration state ~budget:work () in
  let contract=Q.contract registration and producer=Q.producer registration and validators=Q.validators registration in
  M.register owner contract ~producer ~validators;notice state work owner 41(F.Pass_registered(contract,producer,validators));
  let record=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  notice state work owner 42(F.Ran{pass_id="construct_to_molecular";input_id="construct";output_id="molecular";
    default_configuration=true;record});
  let result=M.result owner ~identity:"molecular" ~scope:"exact_cds" in
  notice state work owner 43(F.Result_returned{identity="molecular";scope="exact_cds";result});
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->failwith "Opaque final root was read")() in
  let opaque=H.of_reference bridge(Json.Object["handle",Json.String "object/0"]) in
  let marker=Failure "actual final candidate read" and calls=ref [] in
  let final_source_bridge:Q.final_source_bridge={
    check_construct=(fun active->require(active==work)"Final checker source changed owner";
      calls:= !calls@["first"];
      if mode="first-error" then raise marker;
      if mode="first-close" then F.close state;
      P.candidate upstream);
    return_construct=(fun active->require(active==work)"Final return source changed owner";
      calls:= !calls@["second"];
      if mode="second-error" then raise marker;
      if mode="second-close" then F.close state;
      opaque)} in
  let before= !retained in
  let finish()=F.finish_molecular ~final_source_bridge state ~budget:work ~record ~result_sequence:43 in
  if mode="success" then begin
    let build=finish() in
    require(Q.result build==result && Q.record build==record && Q.build_authority build==authored &&
      (match Q.returned_construct build with Some value->value==opaque|None->false))
      "Workflow final bridge changed captured authority or actual return capabilities";
    require(!calls=["first";"second"] && !retained>before && F.phase state=F.Molecular_finished)
      "Workflow did not reserve the opaque returned source under its lifetime";
    expect "reference_workflow_phase" finish
  end else if mode="first-close" || mode="second-close" then begin
    expect "reference_workflow_closed" finish;
    require(F.phase state=F.Closed && F.owner state=None && F.molecular_build state=None)
      "Final source callback resurrected a closed workflow"
  end else begin
    (try ignore(finish());failwith "Final source callback did not raise"
     with error->require(error==marker)"Final source callback exception identity changed");
    require(F.phase state=F.Interrupted && required(F.owner state)==owner && F.molecular_build state=None)
      "Final callback error discarded the manager or invented a completed build";
    require(M.get owner "molecular"==record && C.Pipeline_result.status result=C.Complete)
      "Final callback error rolled back already completed manager operations";
    expect "reference_workflow_phase" finish
  end;
  require(!calls=(if mode="first-error" || mode="first-close" then ["first"] else ["first";"second"]))
    "Workflow final source-read count differs from source order"
let main()=
  require(Array.length Sys.argv=2)"Expected original reference-pipeline documents directory";
  let load=load Sys.argv.(1) in
  let manifests=Json.object_fields(load "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")
    |>List.map(fun(key,value)->key,Reference_manifest.of_json value) in
  let pairs=["8dd63c98217d58dcc2e9591c279ed82b77ff10523eaa3d49f9115a3ce45327e5","132ada7b1d17ee6bd78700ab7f92d2ea8292ff6da859dd21b6e0bfcffaaf5a78";
    "d6d781141c3f32b4eea90176a1da8e286d115a511b346d5e88645cb85432656f","bf205bf9073363a9d6e3999e0c4b59d1854b563f3ad9ee2cc96a7ecac4bd21a4"] in
  List.iter(fun(request,registry)->let request=R.Request.of_json(load request) and registry=Component_registry.of_json(load registry) in
    let retained=complete request registry manifests in
    require(complete ~maximum:retained request registry manifests=retained)"Exact cumulative retention changed";
    expect "workflow_test_retention" (fun()->complete ~maximum:(retained-1) request registry manifests);
    boundaries request registry manifests;failure_lifetime request registry manifests;
    generator_failure request registry manifests;closed_callbacks request registry manifests;sidecars request registry manifests;
    List.iter(final_source_bridge request registry manifests)["success";"first-error";"second-error";"first-close";"second-close"])pairs;
  print_endline "Reference workflow: actual phased calls, exact result capabilities, historical builds, owner bounds and partial state passed."
let ()=try main() with Diagnostic.Error error as exception_value->
  prerr_endline(error.code^": "^error.message);raise exception_value
