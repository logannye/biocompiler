open Bioc_wire
open Bioc_domain
module P=Bioc_pipeline.Reference_construct_pipeline
module M=Bioc_compiler.Pass_manager
module G=Bioc_compiler.Reference_construct_producer
module C=Pipeline_contract
module R=Reference_construct
module E=Reference_construct_evidence
module W=Bioc_checker.Work_budget
let require condition message=if not condition then failwith message
let field key value=Json.field key (Json.object_fields value)
let changed key replacement value=Json.Object(List.map(fun(name,old)->name,if name=key then replacement else old)(Json.object_fields value))
let parent maximum=W.create ~profile:"reference.construct.pipeline.test" ~error_code:"reference_pipeline_test_work" ~maximum ()
let budget ()=parent 2_000_000_000
let load directory identity=
  let channel=open_in_bin(Filename.concat directory(identity^".json")) in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let length=in_channel_length channel in require(length>0 && length<=Limits.max_request_bytes)"Unbounded source authority";
    really_input_string channel length) in
  let value=Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes raw in
  require(Canonical.fingerprint value=identity)"Original caller authority changed";value
let snapshot manager=M.inspect manager ~provider_identity:(fun _->"native-provider")
let keys key value=List.map fst(Json.object_fields(field key value))
let expect code run=
  try ignore(run());failwith("Expected "^code) with Diagnostic.Error error->
    require(error.code=code)("Unexpected diagnostic "^error.code^": "^error.message);error
let failed=function P.Failed value->value | P.Completed _->failwith "Expected failed construct pipeline"
let retained (failure:P.failure)=match failure.manager with Some value->value|None->failwith "Published manager was discarded"
let obligations record=List.map C.Scoped_obligation.id(C.Stage_record.obligations record)
let roots=["human_admission_policy";"request";"composition";"component_registry";"component_lock";"layout";
  "references";"reference_adapter";"component_checker";"construct_checker";"construct_generator";"construct_pipeline"]
let all_obligations=["reference_authority";"component_linkage";"construct_layout";"emitted_sequence_identity";
  "complete_payload_features";"molecular_behavior"]
let no_host _ ~output:_ ~source_links:_=failwith "Native generator unexpectedly requested a host proposal"
let observed_run request registry manifests=
  let work=budget() and events=ref [] and observed=ref [] and admitted_linkage=ref None in
  let event value=events:= !events@[value] in
  let manager_created actual manager=
    require(actual==work)"Publication switched lifetime ancestor";
    let value=snapshot manager in
    require(keys "records" value=[] && keys "passes" value=[] && keys "component_inputs" value=[])
      "Manager publication occurred after registration or admission";
    require(keys "dependencies" value=roots@["target"])"Authoritative dependency order changed";
    require(keys "profiles" value=["reference_construct"])"Initial completion profile changed";
    event "created" in
  let provider_observer actual _ provider role=
    require(actual==work)"Provider observation switched budget";
    require(not(List.exists(fun(_,other)->other==provider)!observed))"Distinct native closure roles collapsed";
    observed:= !observed@[role,provider] in
  let register_input actual manager contract ~validators=
    require(actual==work && !events=["created"])"Input registration cadence changed";
    require(List.map fst validators=["reference_authority";"component_linkage"])"Admission validator order changed";
    admitted_linkage:=Some(List.assoc "component_linkage" validators);
    M.register_component_input manager contract ~validators;event "input" in
  let register_fixed actual manager contract ~producer ~validators=
    require(actual==work && !events=["created";"input"])"Pass registration cadence changed";
    require(C.Stage_record.accepted(M.get manager "components"))"Pass registered before fresh admission";
    require(List.map fst validators=["layout";"layout_composition"])"Pass validator order changed";
    let previous=match !admitted_linkage with Some value->value|None->failwith "Missing admission provider" in
    require(previous==List.assoc "layout_composition" validators)"Linkage provider identity was not reused";
    M.register manager contract ~producer ~validators;event "pass" in
  let build=P.run ~budget:work ~manager_created ~provider_observer ~register_input ~register_fixed ~request ~registry ~manifests () in
  require(!events=["created";"input";"pass"])"A registration hook ran more than once";
  require(List.map fst !observed=[P.Authority_validator;P.Linkage_validator;P.Construct_producer;P.Layout_validator])
    "Native provider creation order changed";
  let context=C.Pass_context.make ~input:(Json.Object[]) ~output:None ~target:(R.Request.target request)
    ~configuration:(Json.Object[]) ~dependencies:[] ~requirements:[] () in
  List.iter(fun(_,provider)->ignore(expect "reference_construct_pipeline_budget" (fun()->provider (budget()) context)))!observed;
  require(P.budget build==work && P.request build==request && P.registry build==registry)"Original upstream authority was replaced";
  require(C.Pipeline_result.status(P.result build)=C.Complete && C.Pipeline_result.scope(P.result build)="reference_construct")
    "Layout scope did not complete";
  require(E.Result.passed(P.check_result build))"Final independent construct check did not pass";
  require(C.Stage_record.accepted(P.record build) && C.Stage_record.parent(P.record build)=Some "components")"Construct ancestry changed";
  require(P.record build==M.get(P.manager build)"construct")"Build lost actual stored record incarnation";
  require(List.sort String.compare(obligations(P.record build))=List.sort String.compare all_obligations)"An obligation disappeared";
  require(List.map C.Scoped_obligation.id(C.Pipeline_result.unresolved(P.result build))=
    ["emitted_sequence_identity";"complete_payload_features";"molecular_behavior"])"Layout closed another scope's obligations";
  ignore(expect "pipeline_error" (fun()->M.result(P.manager build)~identity:"construct" ~scope:"exact_cds"));
  build
let freshness build=
  let owner=P.manager build in
  List.iter(fun(key,identity)->if key<>"target" then begin
    M.set_dependency owner key(Canonical.fingerprint(Json.String("changed:"^key)));
    let error=expect "pipeline_error" (fun()->M.result owner ~identity:"construct" ~scope:"reference_construct") in
    require(String.starts_with ~prefix:"Stale" error.message)"Freshness failure changed category";
    ignore(expect "pipeline_error" (fun()->M.get owner "components"));
    M.set_dependency owner key identity
  end)(C.Stage_record.dependencies(P.record build));
  ignore(expect "pipeline_error" (fun()->M.set_dependency owner "target"(Canonical.sha256 "changed target")))
let failed_authority request registry manifests=
  let stale=Component_registry.of_json(changed "version"(Json.String "stale")(Component_registry.to_json registry)) in
  List.iter(fun(registry,manifests)->
    let called=ref false in
    let generator_bridge={P.generate=(fun _ ~input:_ _->called:=true;failwith "Rejected admission invoked candidate generation");host_proposal=no_host} in
    let failure=failed(P.attempt ~budget:(budget()) ~generator_bridge ~request ~registry ~manifests ()) in
    require(not !called)"Failed root reached generator";
    let owner=retained failure in let state=snapshot owner in
    require(keys "records" state=["components"] && keys "passes" state=[] && keys "component_inputs" state=["reference_components"])
      "Rejected admission lost partial state or registered a pass";
    require(not(Json.boolean(field "accepted"(field "components"(field "records" state)))))"Rejected authority became accepted";
    ignore(expect "pipeline_error" (fun()->M.get owner "components"))) [stale,manifests;registry,[]]
let changed_candidate request registry manifests=
  let generator_bridge={P.generate=(fun work ~input:_ bound->
    let actual=G.generate ~parent:work bound in
    let placements=List.map(fun value->changed "orientation"(Json.String "reverse") value)
      (Json.array(field "placements"(R.Candidate.to_json actual))) in
    P.Native_candidate(R.Candidate.of_json(changed "placements"(Json.Array placements)(R.Candidate.to_json actual))));host_proposal=no_host} in
  let failure=failed(P.attempt ~budget:(budget()) ~generator_bridge ~request ~registry ~manifests ()) in
  let owner=retained failure in let state=snapshot owner in
  require(keys "records" state=["components";"construct"])"Rejected candidate was not retained historically";
  require(not(Json.boolean(field "accepted"(field "construct"(field "records" state)))))"Generator's edited orientation was accepted";
  require(C.Stage_record.accepted(M.get owner "components"))"Candidate rejection invalidated unchanged admitted authority"
let provenance request registry manifests=
  List.iter(fun duplicate->
    let register_fixed _ owner contract ~producer ~validators=
      let wrapped work context=match producer work context with
        | M.Proposal value->
            let links=C.Pass_result.source_links value in
            let links=if duplicate then links@[List.hd links] else links in
            M.Proposal(C.Pass_result.make ~output:(C.Pass_result.output value) ~obligations:(C.Pass_result.obligations value)
              ~source_links:links ~observation_map:(if duplicate then C.Pass_result.observation_map value
                else Json.Object["behavior",Json.String "verified"]) ())
        | _->failwith "Native construction returned another callback kind" in
      M.register owner contract ~producer:wrapped ~validators in
    let failure=failed(P.attempt ~budget:(budget()) ~register_fixed ~request ~registry ~manifests ()) in
    (match failure.error with Diagnostic.Error error->require(error.code="pipeline_error" && error.message=
      "Construct pass changed authoritative provenance or introduced unestablished observations.")"Provenance rejection changed"
     | _->failwith "Unexpected provenance exception");
    let state=snapshot(retained failure) in
    require(keys "records" state=["components"] && keys "passes" state=["components_to_construct"])
      "Failed provenance stored an output or discarded the actual registration") [false;true]
let exception_lifetime request registry manifests=
  let marker=Failure "actual constructor callback exception" in
  let owner=ref None in
  let manager_created _ value=owner:=Some value in
  let generate _ ~input:_ _=raise marker in
  let generator_bridge={P.generate;host_proposal=no_host} in
  (try ignore(P.attempt ~budget:(budget()) ~manager_created ~generator_bridge ~request ~registry ~manifests ());
       failwith "Expected original callback exception"
   with error->require(error==marker)"Original callback exception was translated");
  let manager=match !owner with Some value->value|None->failwith "Callback failure lost published owner" in
  let state=snapshot manager in
  require(keys "records" state=["components"] && keys "passes" state=["components_to_construct"])
    "Callback failure changed partial manager state";
  let error=Diagnostic.Error{code="test_hook_error";message="actual input registration failure";path=None} in
  let register_input _ manager contract ~validators=M.register_component_input manager contract ~validators;raise error in
  let failure=failed(P.attempt ~budget:(budget()) ~register_input ~request ~registry ~manifests ()) in
  require(failure.error==error)"Logical hook failure lost actual exception identity";
  let state=snapshot(retained failure) in
  require(keys "records" state=[] && keys "component_inputs" state=["reference_components"])
    "Post-registration failure rolled back or admitted a record"
let opaque_generator request registry manifests=
  let touched=ref false in
  let denied ()=touched:=true;failwith "Opaque candidate was observed before proposal construction" in
  let host:M.host_value={
    attribute=(fun _ _->denied());attribute_default=(fun _ _ _->denied());
    is_instance=(fun _ _->denied());is_none=(fun _->denied());truth=(fun _->denied());
    compare=(fun _ _ _->denied());contains=(fun _ _->denied());
    attribute_set_equal=(fun _ _ ~attribute:_ _->denied());source_link_set_equal=(fun _ _ _->denied());
    lookup=(fun _ _->denied());get_item=(fun _ _->denied());get=(fun _ _->denied());
    tuple=(fun _->denied());iter=(fun _->denied());call=(fun _ _->denied());
    merge=(fun _ ~before:_ ~after:_->denied());document=(fun _->denied());
    freeze=(fun _->denied());vars=(fun _->denied())} in
  let marker=Failure "actual construct proposal-builder exception" and calls=ref [] and owner=ref None in
  let generator_bridge:P.generator_bridge={
    generate=(fun _ ~input:_ bound->
      require(bound!=request && R.Request.fingerprint bound=R.Request.fingerprint request)
        "Generator lost fresh context import";
      calls:= !calls@["generate"];P.Host_candidate host);
    host_proposal=(fun _ ~output ~source_links->
      require(output==host && not !touched)"Candidate identity or deferred materialization changed";
      require(source_links<>[] && List.for_all(fun link->C.Source_link.pass_name link="components_to_construct")source_links)
        "Proposal did not receive native-derived source links";
      calls:= !calls@["proposal"];raise marker)} in
  (try ignore(P.run ~budget:(budget()) ~manager_created:(fun _ value->owner:=Some value)
       ~generator_bridge ~request ~registry ~manifests ());failwith "Expected original host-builder exception"
   with error->require(error==marker)"Host-builder exception identity changed");
  require(!calls=["generate";"proposal"] && not !touched)"Opaque generator/proposal cadence changed";
  let owner=match !owner with Some value->value|None->failwith "Opaque generator lost published manager" in
  require(keys "records"(snapshot owner)=["components"])"Opaque callback failure stored a candidate"
let staged request registry manifests=
  let work=budget() in let prepared=P.prepare ~budget:work ~request ~registry ~manifests () in
  require(List.map fst(P.dependencies prepared)=roots)"Staged root order changed";
  require(List.map C.Scoped_obligation.id(P.obligations prepared)=all_obligations)"Staged obligation order changed";
  ignore(expect "reference_construct_pipeline_budget" (fun()->P.create ~budget:(budget()) prepared));
  let initialized=P.create ~budget:work prepared in
  let owner=P.initialized_manager initialized in
  let admission=P.prepare_admission ~budget:work initialized in
  M.register_component_input owner(P.admission_contract admission) ~validators:(P.admission_validators admission);
  P.allow_admission_host_source_links admission;
  ignore(M.admit_component_input owner ~contract_id:"reference_components" ~identity:"components"(R.Request.to_json request));
  let admitted=M.get owner "components" in
  let registration=P.prepare_registration ~budget:work admission ~admitted in
  M.register owner(P.contract registration) ~producer:(P.producer registration) ~validators:(P.validators registration);
  P.allow_host_source_links registration;
  let record=M.run owner ~pass_id:"components_to_construct" ~input_id:"components" ~output_id:"construct" () in
  let result=M.result owner ~identity:"construct" ~scope:"reference_construct" in
  M.set_dependency owner "layout"(Canonical.sha256 "changed after result");
  let build=P.finish ~budget:work registration ~record ~result in
  require(P.record build==record && P.result build==result && P.manager build==owner)"Finish reconstructed historical capabilities";
  require(E.Result.passed(P.check_result build))"Historical finish lost independently frozen authority";
  ignore(expect "pipeline_error" (fun()->M.get owner "construct"))
let resources request registry manifests=
  let stored=ref [] in
  let observer _=function M.Record_stored(_,_,record)->stored:= !stored@[record]|M.Context_created _->() in
  let maximum=2_000_000_000 in let work=parent maximum in
  let original=P.run ~budget:work ~observer ~request ~registry ~manifests () in
  let consumed=maximum-W.remaining work in require(consumed>1)"Pipeline did not charge its ancestor";
  stored:=[];
  let exact=parent consumed in let repeated=P.run ~budget:exact ~observer ~request ~registry ~manifests () in
  require(W.remaining exact=0 && R.Candidate.fingerprint(P.candidate repeated)=R.Candidate.fingerprint(P.candidate original))
    "Exact full-pipeline lifetime budget was not deterministic";
  let short=parent(consumed-1) in
  stored:=[];
  let failure=failed(P.attempt ~budget:short ~observer ~request ~registry ~manifests ()) in
  (match failure.error with Diagnostic.Error error->require(W.is_exhaustion short error)"Resource failure was remapped"
   | _->failwith "Expected actual limiting-ancestor diagnostic");
  require(W.exhausted short)"Work exhaustion was not sticky";
  require(Option.is_some failure.manager && List.map C.Stage_record.id !stored=["components";"construct"])
    "Final-check exhaustion discarded previously stored records";
  let published=ref false in
  let manager_created _ _=published:=true in
  let failure=failed(P.attempt ~budget:(budget()) ~manager_created
    ~manager_limits:(M.make_limits ~max_document_bytes:1 ()) ~request ~registry ~manifests ()) in
  require(not !published && Option.is_none failure.manager)"Prepublication resource failure invented a manager";
  (match failure.error with Diagnostic.Error error->require(error.code="verification_exploration_limit")"Input cap was remapped"
   | _->failwith "Expected bounded input failure")
let main ()=
  require(Array.length Sys.argv=2)"Expected original reference-pipeline documents directory";
  let load=load Sys.argv.(1) in
  let manifests=Json.object_fields(load "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")
    |>List.map(fun(key,value)->key,Reference_manifest.of_json value) in
  let authorities=["8dd63c98217d58dcc2e9591c279ed82b77ff10523eaa3d49f9115a3ce45327e5","132ada7b1d17ee6bd78700ab7f92d2ea8292ff6da859dd21b6e0bfcffaaf5a78";
    "d6d781141c3f32b4eea90176a1da8e286d115a511b346d5e88645cb85432656f","bf205bf9073363a9d6e3999e0c4b59d1854b563f3ad9ee2cc96a7ecac4bd21a4"] in
  List.iter(fun(request,registry)->
    (* Only original caller declarations enter; every record/report/candidate is
       produced and checked by the current native pipeline. *)
    let request=R.Request.of_json(load request) and registry=Component_registry.of_json(load registry) in
    let build=observed_run request registry manifests in freshness build;
    failed_authority request registry manifests;changed_candidate request registry manifests;
    provenance request registry manifests;exception_lifetime request registry manifests;
    opaque_generator request registry manifests;
    staged request registry manifests;resources request registry manifests) authorities;
  print_endline "Reference construct pipeline: live admission, closure identities, provenance, historical results and one lifetime budget passed."
let ()=try main() with Diagnostic.Error error as exception_value->
  prerr_endline(error.code^": "^error.message);raise exception_value
