open Bioc_wire
open Bioc_domain
module F=Bioc_pipeline_service.Reference_workflow
module M=Bioc_compiler.Pass_manager
module W=Bioc_checker.Work_budget
module P=Bioc_pipeline.Reference_construct_pipeline
module Q=Bioc_pipeline.Reference_molecular_pipeline
module R=Reference_construct
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

let constructed request registry manifests=
  let work=budget() in let state,retained=make_state work in
  let owner=initialize state work request registry manifests in
  ignore(admission state work owner request);ignore(registration state work owner);
  let record,_=construct_result state work owner in
  let build=F.finish_construct state ~budget:work ~record ~result_sequence:22 in
  state,work,owner,build,retained
let sequence=ref 100
let observed state work owner operation=
  incr sequence;F.notice state ~budget:work ~owner ~sequence: !sequence operation
let prepare ?authority state work owner=
  let prepared=F.prepare_molecular ?authority state ~budget:work () in
  let scope=required(F.active_molecular state) in
  require(F.molecular_prepared scope==prepared)"Preparation changed its scope";
  let writes=ref [] in
  List.iter(fun(key,value)->M.set_dependency owner key value;
    writes:=(key,value)::!writes;observed state work owner(F.Dependency_set(key,value)))(Q.dependencies prepared);
  require(List.rev !writes=Q.dependencies prepared && List.length !writes=6)"Original six writes changed";
  scope
let profile state work owner=
  let value=F.prepare_molecular_profile state ~budget:work () in
  let declaration=Q.completion_profile value in
  M.register_completion_profile owner declaration;observed state work owner(F.Profile_registered declaration)
let register ?emitter_bridge state work owner=
  let value=F.prepare_molecular_registration ?emitter_bridge state ~budget:work () in
  let contract=Q.contract value and producer=Q.producer value and validators=Q.validators value in
  M.register owner contract ~producer ~validators;
  observed state work owner(F.Pass_registered(contract,producer,validators));value
let run_result state work owner=
  let record=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  observed state work owner(F.Ran{pass_id="construct_to_molecular";input_id="construct";output_id="molecular";
    default_configuration=true;record});
  let result=M.result owner ~identity:"molecular" ~scope:"exact_cds" in
  observed state work owner(F.Result_returned{identity="molecular";scope="exact_cds";result});
  record,result,!sequence
let duplicate_profile state work owner=
  let declared=Q.completion_profile(F.prepare_molecular_profile state ~budget:work ()) in
  try M.register_completion_profile owner declared;failwith "Duplicate completion profile accepted"
  with Diagnostic.Error error->require(error.code="pipeline_error" &&
    error.message="Completion profile 'exact_cds' is already registered.")"Duplicate profile error changed"
let complete_and_reuse request registry manifests=
  let state,work,owner,upstream,retained=constructed request registry manifests in
  let old_scope=prepare state work owner in profile state work owner;
  let old_registration=register state work owner in
  let record,result,result_sequence=run_result state work owner in
  let build=F.finish_molecular state ~budget:work ~record ~result_sequence in
  F.leave_molecular state ~budget:work old_scope;
  require(F.active_molecular state=None)"Finished attempt leaked an execution scope";
  let old_retained= !retained in
  (* A changed public Molecular map is a new authority, not an imported manager.
     The original duplicate-profile failure occurs only after all six writes. *)
  M.set_dependency owner "molecular_emitter"(Canonical.sha256 "stale-before-reentry");
  let next=prepare ~authority:({request;registry;manifests=[]}:Q.authority) state work owner in
  require(next!=old_scope && !retained>old_retained)"New attempt aliased/refunded an old capability";
  duplicate_profile state work owner;F.leave_molecular state ~budget:work next;
  require(required(F.molecular_build state)==build && required(F.molecular_build_of state ~budget:work old_scope)==build)
    "Failed attempt replaced a completed historical Build";
  require(Q.record build==record && Q.result build==result && Q.upstream build==upstream && Q.manager build==owner)
    "Reuse replaced original manager/record/result/upstream identities";
  let field key raw=Json.field key(Json.object_fields raw) in
  let registered=M.inspect owner ~provider_identity:(fun provider->
    if provider==Q.producer old_registration then "original-producer" else "another-provider") in
  require(Json.string(field "producer"(field "construct_to_molecular"(field "passes" registered)))="original-producer")
    "Failed reentry replaced the actual registered original producer";
  expect "reference_workflow_capability" (fun()->F.leave_molecular state ~budget:work next);
  (* Old actual registration still executes on its captured authority. *)
  let rerun=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  require(rerun!=record && Q.record build==record)"Rerun replaced a historical Build record";
  F.close state;expect "reference_workflow_closed" (fun()->F.molecular_build_of state ~budget:work old_scope)
let failed_reentry request registry manifests=
  let state,work,owner,_,_=constructed request registry manifests in
  let first=prepare state work owner in profile state work owner;
  let marker=Failure "actual emitter override" in
  let bridge:Q.emitter_bridge={emit=(fun _ ~input:_ ~request:_ ~construct:_ ~registry:_ ~manifests:_->raise marker);
    host_proposal=(fun _ ~output:_ ~source_links:_->failwith "Opaque proposal must follow actual emitter return")} in
  ignore(register ~emitter_bridge:bridge state work owner);
  (try ignore(run_result state work owner);failwith "Emitter marker was swallowed"
   with error->require(error==marker)"Emitter exception identity changed");
  F.leave_molecular state ~budget:work first;
  require(F.molecular_build state=None && F.molecular_attempt_phase first=F.Molecular_registered)
    "Failed run invented a completed build or erased partial registration";
  let next=prepare state work owner in duplicate_profile state work owner;
  F.leave_molecular state ~budget:work next;
  require(required(F.owner state)==owner)"Logical reentry failure lost actual owner"
let nested_notice request registry manifests=
  let state,work,owner,_,_=constructed request registry manifests in
  let prepared=F.prepare_molecular state ~budget:work () in
  let outer=required(F.active_molecular state) in
  let first=List.hd(Q.dependencies prepared) in
  (* Capture scope at command entry; arbitrary nested preparation changes only
     its own phase. Notice the outer actual mutation after inner leave. *)
  let captured=Some outer in
  let inner=prepare state work owner in
  expect "reference_workflow_capability" (fun()->F.leave_molecular state ~budget:work outer);
  F.leave_molecular state ~budget:work inner;
  let key,value=first in M.set_dependency owner key value;incr sequence;
  F.notice_for state ~budget:work ~owner ~sequence: !sequence ~molecular:captured(F.Dependency_set(key,value));
  List.iter(fun(key,value)->M.set_dependency owner key value;observed state work owner(F.Dependency_set(key,value)))
    (List.tl(Q.dependencies prepared));
  ignore(F.prepare_molecular_profile state ~budget:work ());
  require(F.molecular_attempt_phase outer=F.Molecular_profile_available &&
    F.molecular_attempt_phase inner=F.Molecular_dependencies)"Outer notice advanced a nested/retired attempt";
  F.leave_molecular state ~budget:work outer;
  expect "reference_workflow_capability" (fun()->F.notice_for state ~budget:work ~owner ~sequence:999999
    ~molecular:captured(F.Dependency_set(key,value)))
let captured_old_authority request registry manifests=
  let state,work,owner,upstream,_=constructed request registry manifests in
  let first=prepare state work owner in profile state work owner;
  let captured_manifests=P.manifests upstream in
  let observed=ref [] in
  let bridge:Q.emitter_bridge={
    emit=(fun active ~input:_ ~request:actual_request ~construct ~registry:actual_registry ~manifests:actual_manifests->
      observed:=(actual_request,actual_registry,actual_manifests)::!observed;
      Q.Native_artifact(Bioc_compiler.Reference_sequence_emitter.emit ~parent:active
        ~request:actual_request ~construct ~registry:actual_registry ~manifests:actual_manifests ()));
    host_proposal=(fun _ ~output:_ ~source_links:_->failwith "Unexpected host output")} in
  ignore(register ~emitter_bridge:bridge state work owner);
  F.leave_molecular state ~budget:work first;
  let next=prepare ~authority:({request;registry;manifests=[]}:Q.authority) state work owner in
  duplicate_profile state work owner;F.leave_molecular state ~budget:work next;
  ignore(M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" ());
  match !observed with [(a,b,c)]->require(a==request && b==registry && c==captured_manifests)"Old provider lost captured original roots"
    |_->failwith "Old provider did not execute exactly once"
let bounded_attempts request registry manifests=
  let work=budget() and ceiling=ref max_int and retained=ref 0 in
  let reserve amount=Diagnostic.require(amount <= !ceiling- !retained) "attempt_test_retention" "No remaining attempt retention";
    retained:= !retained+amount in
  let state=F.create ~budget:work ~retain_bytes:reserve () in
  let owner=initialize state work request registry manifests in
  ignore(admission state work owner request);ignore(registration state work owner);
  let record,_=construct_result state work owner in ignore(F.finish_construct state ~budget:work ~record ~result_sequence:22);
  ceiling:= !retained+1023;
  expect "attempt_test_retention" (fun()->F.prepare_molecular state ~budget:work ());
  require(F.active_molecular state=None && F.phase state=F.Construct_finished)"Failed reservation published/reset an attempt";
  expect "reference_workflow_budget" (fun()->F.prepare_molecular state ~budget:(budget()) ());
  F.close state
let ()=
  require(Array.length Sys.argv=2)"Expected original authority document directory";
  let directory=Sys.argv.(1) in
  let request=R.Request.of_json(load directory "d6d781141c3f32b4eea90176a1da8e286d115a511b346d5e88645cb85432656f") in
  let registry=Component_registry.of_json(load directory "bf205bf9073363a9d6e3999e0c4b59d1854b563f3ad9ee2cc96a7ecac4bd21a4") in
  let manifests=List.map(fun(key,value)->key,Reference_manifest.of_json value)
    (Json.object_fields(load directory "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")) in
  complete_and_reuse request registry manifests;failed_reentry request registry manifests;
  nested_notice request registry manifests;captured_old_authority request registry manifests;
  bounded_attempts request registry manifests
