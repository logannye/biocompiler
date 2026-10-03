open Bioc_wire
open Bioc_domain
module W=Bioc_checker.Work_budget
module M=Bioc_compiler.Pass_manager
module C=Pipeline_contract
module R=Reference_construct
module Q=Reference_molecular
module E=Reference_molecular_evidence
module U=Bioc_pipeline.Reference_construct_pipeline
module P=Bioc_pipeline.Reference_molecular_pipeline
let require condition message=if not condition then failwith message
let field key raw=Json.field key(Json.object_fields raw)
let same left right=Canonical.encode left=Canonical.encode right
let change key value raw=Json.Object(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let budget ()=W.create ~profile:"reference.pipeline.focused" ~error_code:"reference_pipeline_test_work" ~maximum:1_000_000_000 ()
let load directory identity=
  let channel=open_in_bin(Filename.concat directory(identity^".json")) in
  let raw=Fun.protect ~finally:(fun()->close_in channel)(fun()->really_input_string channel(in_channel_length channel)) in
  let value=Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes raw in
  require(Canonical.fingerprint value=identity)"Original molecular authority bytes changed";value
let error ?message code action=
  try ignore(action());failwith("Expected "^code) with Diagnostic.Error value->
    require(value.code=code)("Unexpected diagnostic "^value.code^": "^value.message);
    Option.iter(fun expected->require(value.message=expected)"Original diagnostic wording changed")message
let provider_labels ()=
  let retained=ref [] in fun provider->
    match List.find_opt(fun(previous,_)->previous==provider)!retained with
    | Some(_,identity)->identity
    | None->let identity="provider/"^string_of_int(List.length !retained) in
        retained:= !retained@[provider,identity];identity
let inspect manager=M.inspect manager ~provider_identity:(provider_labels ())
let keys key raw=List.map fst(Json.object_fields(field key raw))
let roots=["human_admission_policy";"molecular_emitter";"molecular_checker";
  "molecular_profile";"encoding_policy";"molecular_pipeline"]
let rebuild="Molecular provider or policy identity changed; rebuild the pipeline with current providers."
let correspondence="Molecular emission changed source correspondence or introduced unestablished observations."
let authority directory alphabet=
  let request,registry=match alphabet with
    | "RNA"->"d6d781141c3f32b4eea90176a1da8e286d115a511b346d5e88645cb85432656f",
        "bf205bf9073363a9d6e3999e0c4b59d1854b563f3ad9ee2cc96a7ecac4bd21a4"
    | "DNA"->"8dd63c98217d58dcc2e9591c279ed82b77ff10523eaa3d49f9115a3ce45327e5",
        "132ada7b1d17ee6bd78700ab7f92d2ea8292ff6da859dd21b6e0bfcffaaf5a78"
    | _->failwith"Unreviewed fixture alphabet" in
  let request=R.Request.of_json(load directory request) in
  let registry=Component_registry.of_json(load directory registry) in
  let manifests=Json.object_fields(load directory "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")
    |>List.map(fun(key,value)->key,Reference_manifest.of_json value) in
  request,registry,manifests
let original directory alphabet=
  let request,registry,manifests=authority directory alphabet in
  let work=budget() in
  let upstream=U.run ~budget:work ~request ~registry ~manifests () in
  work,upstream
let register manager registration=
  M.register manager(P.contract registration) ~producer:(P.producer registration) ~validators:(P.validators registration);
  P.allow_host_source_links registration
let successful directory alphabet=
  let work,upstream=original directory alphabet in
  let owner=U.manager upstream and retained_result=U.result upstream and retained_record=U.record upstream in
  let before=inspect owner in
  let prepared=P.prepare ~budget:work upstream in
  require(List.map fst(P.dependencies prepared)=roots)"The six dependency writes lost source order";
  require(same before(inspect owner))"Molecular preparation changed the live manager";
  error "reference_molecular_pipeline_budget" (fun()->P.prepare ~budget:(budget()) upstream);
  List.iter(fun(key,value)->M.set_dependency owner key value)(P.dependencies prepared);
  let profiled=P.prepare_profile ~budget:work prepared in
  require(C.Completion_profile.obligations(P.completion_profile profiled)=
    ["reference_authority";"component_linkage";"construct_layout";"emitted_sequence_identity"])
    "Completion scope changed";
  M.register_completion_profile owner(P.completion_profile profiled);
  let providers=ref [] in
  let observer active manager provider role=
    require(active==work && manager==owner)"Provider publication changed its owner";
    providers:= !providers@[provider,role] in
  let registration=P.prepare_registration ~budget:work ~provider_observer:observer profiled in
  require(List.map snd !providers=[P.Emit;P.Sequence_identity;P.Encoding_composition])"Provider role order changed";
  let emit=P.producer registration and checks=P.validators registration in
  require(List.map fst checks=["sequence_identity";"encoding_composition"] &&
    fst(List.nth !providers 0)==emit && fst(List.nth !providers 1)==snd(List.nth checks 0) &&
    fst(List.nth !providers 2)==snd(List.nth checks 1))"Published providers are not the registered closures";
  require(emit!=snd(List.nth checks 0) && emit!=snd(List.nth checks 1) &&
    snd(List.nth checks 0)!=snd(List.nth checks 1))"Molecular provider identities were collapsed";
  let context=C.Pass_context.make ~input:(Json.Object[]) ~output:None ~target:(R.Request.target(U.request upstream))
    ~configuration:(Json.Object[]) ~dependencies:(P.dependencies prepared) ~requirements:[] () in
  List.iter(fun provider->error "reference_molecular_pipeline_budget" (fun()->provider (budget()) context))
    (emit::List.map snd checks);
  register owner registration;
  let native_record=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  let native_result=M.result owner ~identity:"molecular" ~scope:"exact_cds" in
  let build=P.finish ~budget:work registration ~record:native_record ~result:native_result in
  require(P.manager build==owner && P.upstream build==upstream && P.construct build==U.candidate upstream)
    "Molecular build detached its upstream authority";
  require(P.record build==native_record && P.result build==native_result)
    "Finish reconstructed the historical manager returns";
  require(U.record upstream==retained_record && U.result upstream==retained_result)
    "Molecular continuation replaced an earlier build observation";
  require(C.Pipeline_result.status(P.result build)=C.Complete && E.Result.passed(P.check_result build))
    "Native molecular generation/checking did not complete exact_cds";
  require(List.sort String.compare(List.map C.Scoped_obligation.id(C.Pipeline_result.unresolved(P.result build)))=
    ["complete_payload_features";"molecular_behavior"])"Molecular emission granted unresolved payload or biological claims";
  let emitted=List.hd(Q.Artifact.records(P.candidate build)) in
  let selection=R.Reference.selection(List.hd(R.Request.references(U.request upstream))) in
  let manifest=List.assoc(Pinned_identity.id(Reference_components.Selection.manifest selection))(U.manifests upstream) in
  let source=Reference_manifest.record manifest(Pinned_identity.id(Reference_components.Selection.reference selection)) in
  require(Q.Record.sequence emitted=Reference_manifest.Record.sequence source &&
    Q.Record.sequence_sha256 emitted=Reference_manifest.Record.sequence_sha256 source && Q.Record.length emitted=1491)
    "Emission did not reproduce the selected reference's own spelling";
  require(Reference_manifest.alphabet_name(Q.Record.alphabet emitted)=alphabet)"DNA/RNA identity was converted";
  require(C.Stage_record.parent native_record=Some "construct" &&
    not(List.mem "molecular_behavior"(C.Stage_record.discharged native_record)))"Record scope or ancestry changed";
  require(C.Pipeline_result.status(M.result owner ~identity:"construct" ~scope:"reference_construct")=C.Complete)
    "Molecular continuation invalidated unchanged upstream scope";
  (* Each actual native closure rejects captured provider drift before parsing
     any candidate input or invoking a checker/emitter. *)
  List.iter(fun(key,original)->
    let current=List.map(fun(name,value)->name,if name=key then String.make 64 'a' else value)(P.dependencies prepared) in
    let context=C.Pass_context.make ~input:(Json.Object[]) ~output:None ~target:(R.Request.target(U.request upstream))
      ~configuration:(Json.Object[]) ~dependencies:current ~requirements:[] () in
    List.iter(fun provider->error ~message:rebuild "pipeline_error" (fun()->provider work context))(emit::List.map snd checks);
    if key<>"human_admission_policy" then begin
      M.set_dependency owner key(String.make 64 'a');
      error ~message:rebuild "pipeline_error" (fun()->M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"recreated" ());
      M.set_dependency owner key original
    end)(P.dependencies prepared);
  ignore(M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"recreated" ());
  require(C.Pipeline_result.status(M.result owner ~identity:"recreated" ~scope:"exact_cds")=C.Complete)
    "Restored provider authority could not rerun";
  require(W.remaining work<1_000_000_000)"The pipeline did not charge its lifetime ancestor";
  build

let proposal_mutations directory=
  List.iter(fun observation->
    let work,upstream=original directory "RNA" in
    let hook _ owner contract ~producer ~validators=
      let mutated work context=match producer work context with
        | M.Proposal original->
            let links=C.Pass_result.source_links original in
            M.Proposal(C.Pass_result.make ~output:(C.Pass_result.output original)
              ~obligations:(C.Pass_result.obligations original)
              ~source_links:(if observation then links else links@[List.hd links])
              ~observation_map:(if observation then Json.Object["biological_response",Json.String"passed"] else Json.Object[]) ())
        | _->failwith"Native emitter did not return its actual proposal" in
      M.register owner contract ~producer:mutated ~validators in
    match P.attempt ~budget:work ~register_fixed:hook upstream with
    | P.Completed _->failwith"Mutated source correspondence completed"
    | P.Failed failure->
        require(failure.manager==U.manager upstream)"Failure lost its actual manager";
        (match failure.error with Diagnostic.Error error->require(error.code="pipeline_error" && error.message=correspondence)
          "Original correspondence rejection changed"|_->raise failure.error);
        require(keys "records"(inspect failure.manager)=["components";"construct"])
          "Rejected correspondence published a molecular record") [false;true]

let changed_sequence directory valid=
  let work,upstream=original directory "RNA" in
  let raw=Q.Artifact.to_json(P.candidate valid) in
  let records=Json.array(field "records" raw) in
  let record=List.hd records in
  let sequence=Bytes.of_string(Json.string(field "sequence" record)) in
  Bytes.set sequence 30 (if Bytes.get sequence 30='A' then 'C' else 'A');
  let sequence=Bytes.to_string sequence in
  let record=change "sequence_sha256"(Json.String(Canonical.sha256 sequence))
    (change "sequence"(Json.String sequence)record) in
  let changed=Q.Artifact.of_json(change "records"(Json.Array[record])raw) in
  let invoked=ref 0 in
  let bridge:P.emitter_bridge={emit=(fun _ ~input:_ ~request ~construct ~registry ~manifests->
    incr invoked;
    require(request==U.request upstream && registry==U.registry upstream && manifests==U.manifests upstream)
      "Override received reconstructed captured authority";
    require(construct!=U.candidate upstream && R.Candidate.fingerprint construct=R.Candidate.fingerprint(U.candidate upstream))
      "Override did not receive the fresh context import";
    P.Native_artifact changed);
    host_proposal=(fun _ ~output:_ ~source_links:_->failwith"Native artifact used host conversion")} in
  match P.attempt ~budget:work ~emitter_bridge:bridge upstream with
  | P.Completed _->failwith"Rehashed nucleotide mutation completed"
  | P.Failed failure->
      require(!invoked=1)"Emitter override invocation count changed";
      (match failure.error with Diagnostic.Error error->require(error.code="pipeline_error")"Independent rejection changed exception class"
       |_->raise failure.error);
      let record=field "molecular"(field "records"(inspect failure.manager)) in
      require(field "accepted" record=Json.Bool false && same(field "payload" record)(Q.Artifact.to_json changed))
        "Failure lost the actual stored rejected artifact"

let partial_order directory=
  let work,upstream=original directory "RNA" in
  let prepared=P.prepare ~budget:work upstream in
  let profiled=P.prepare_profile ~budget:work prepared in
  let owner=U.manager upstream in
  M.register_completion_profile owner(P.completion_profile profiled);
  error ~message:"Completion profile 'exact_cds' is already registered." "pipeline_error"
    (fun()->P.run ~budget:work upstream);
  let state=inspect owner in
  List.iter(fun(key,identity)->require(field key(field "dependencies" state)=Json.String identity)
    "Profile rejection moved before its original dependency writes")(P.dependencies prepared);
  require(keys "passes" state=["components_to_construct"] && keys "records" state=["components";"construct"])
    "Profile rejection moved later than original registration/run";
  W.charge work(W.remaining work);
  (try ignore(P.prepare ~budget:work upstream);failwith"Exhausted ancestor accepted preparation" with
   | Diagnostic.Error value->require(value.code="reference_pipeline_test_work" && W.is_exhaustion work value)
       "Pipeline replaced its actual exhausted ancestor");
  require(W.exhausted work)"Pipeline work exhaustion was not sticky"

let opaque_host ?touched message : M.host_value =
  let denied ()=Option.iter(fun value->value:=true)touched;failwith message in {
    attribute=(fun _ _->denied());attribute_default=(fun _ _ _->denied());
    is_instance=(fun _ _->denied());is_none=(fun _->denied());truth=(fun _->denied());
    compare=(fun _ _ _->denied());contains=(fun _ _->denied());
    attribute_set_equal=(fun _ _ ~attribute:_ _->denied());source_link_set_equal=(fun _ _ _->denied());
    lookup=(fun _ _->denied());get_item=(fun _ _->denied());get=(fun _ _->denied());
    tuple=(fun _->denied());iter=(fun _->denied());call=(fun _ _->denied());
    merge=(fun _ ~before:_ ~after:_->denied());document=(fun _->denied());
    freeze=(fun _->denied());vars=(fun _->denied())}
let opaque_emitter directory=
  let work,upstream=original directory "RNA" in
  let touched=ref false in
  let host=opaque_host ~touched "Opaque override was observed before proposal construction" in
  let marker=Failure"original proposal-builder exception" and calls=ref [] in
  let bridge:P.emitter_bridge={
    emit=(fun _ ~input:_ ~request ~construct ~registry ~manifests->
      require(request==U.request upstream && registry==U.registry upstream && manifests==U.manifests upstream)
        "Opaque emitter lost original captured arguments";
      require(R.Candidate.fingerprint construct=R.Candidate.fingerprint(U.candidate upstream))
        "Opaque emitter lost the actual context construct";
      calls:= !calls@["emit"];P.Host_artifact host);
    host_proposal=(fun _ ~output ~source_links->
      require(output==host && not !touched)"Host artifact identity or deferred observation changed";
      require(source_links<>[] && List.for_all(fun link->C.Source_link.pass_name link="construct_to_molecular")source_links)
        "Native source links were not derived after the override";
      calls:= !calls@["proposal"];raise marker)} in
  (try ignore(P.run ~budget:work ~emitter_bridge:bridge upstream);failwith"Original callback exception was swallowed" with
   | error when error==marker->());
  require(!calls=["emit";"proposal"] && not !touched)"Emitter/proposal callback sequence changed";
  let state=inspect(U.manager upstream) in
  require(keys "passes" state=["components_to_construct";"construct_to_molecular"] &&
    keys "records" state=["components";"construct"])"Callback exception rolled back or advanced original state"

let final_sources directory=
  let work,upstream=original directory "RNA" in
  let owner=U.manager upstream in
  let prepared=P.prepare ~budget:work upstream in
  List.iter(fun(key,value)->M.set_dependency owner key value)(P.dependencies prepared);
  let profile=P.prepare_profile ~budget:work prepared in
  M.register_completion_profile owner(P.completion_profile profile);
  let registration=P.prepare_registration ~budget:work profile in
  register owner registration;
  let record=M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular" () in
  let result=M.result owner ~identity:"molecular" ~scope:"exact_cds" in
  let before=inspect owner and calls=ref [] in
  let host=opaque_host "Final return value was semantically inspected" in
  let selected=R.Candidate.of_json(change "request_fingerprint"(Json.String(Canonical.sha256 "external source"))
    (R.Candidate.to_json(U.candidate upstream))) in
  let bridge:P.final_source_bridge={
    check_construct=(fun active->require(active==work)"First final-source read changed budget";
      calls:= !calls@["check-source"];selected);
    return_construct=(fun active->require(active==work)"Second final-source read changed budget";
      calls:= !calls@["return-source"];host)} in
  let build=P.finish ~budget:work ~final_source_bridge:bridge registration ~record ~result in
  require(!calls=["check-source";"return-source"] && (match P.returned_construct build with Some value->value==host|None->false))
    "Final source reads lost their order or exact opaque return";
  require(not(E.Result.passed(P.check_result build)) && C.Pipeline_result.status(P.result build)=C.Complete)
    "External final source replaced manager completion or bypassed independent checking";
  let dependencies=field "dependencies"(E.Result.to_json(P.check_result build)) in
  require(field "construct" dependencies=Json.String(R.Candidate.fingerprint selected))
    "Final check did not bind the actual first source read";
  require(P.result build==result && P.record build==record && same before(inspect owner))
    "Final reads changed real manager state or historical results";
  let normal=P.finish ~budget:work registration ~record ~result in
  require(P.returned_construct normal=None && P.construct normal==U.candidate upstream && E.Result.passed(P.check_result normal))
    "Default native final source changed";
  let request,registry,manifests=authority directory "DNA" in
  let authored:P.authority={request;registry;manifests} in
  let alternative=P.prepare ~budget:work ~authority:authored upstream in
  let alternative=P.prepare_profile ~budget:work alternative in
  let alternative=P.prepare_registration ~budget:work alternative in
  (* Exercise the final checker with the same actual historical record/result
     but an explicitly different caller authority; no acceptance is imported. *)
  let checked=P.finish ~budget:work alternative ~record ~result in
  let dependencies=field "dependencies"(E.Result.to_json(P.check_result checked)) in
  require(P.build_authority checked==authored && not(E.Result.passed(P.check_result checked)) &&
    field "request" dependencies=Json.String(R.Request.fingerprint request) &&
    field "registry" dependencies=Json.String(Component_registry.fingerprint registry))
    "Final molecular check substituted upstream request or registry authority";
  List.iter(fun first->
    let marker=Failure(if first then "first final source" else "second final source") in
    let observed=ref [] in
    let failing:P.final_source_bridge={
      check_construct=(fun _->observed:= !observed@["first"];if first then raise marker else U.candidate upstream);
      return_construct=(fun _->observed:= !observed@["second"];raise marker)} in
    (try ignore(P.finish ~budget:work ~final_source_bridge:failing registration ~record ~result);
      failwith "Final source exception was swallowed" with error->require(error==marker)"Final source exception identity changed");
    require(!observed=(if first then ["first"] else ["first";"second"]))"Final source exception changed read order") [true;false];
  let malformed=C.Stage_record.of_json(change "payload" Json.Null(C.Stage_record.to_json record)) in
  calls:=[];
  error "reference_molecular" (fun()->P.finish ~budget:work ~final_source_bridge:bridge registration ~record:malformed ~result);
  require(!calls=[])"Malformed artifact invoked final source reads";
  calls:=[];
  error "reference_molecular_pipeline_budget" (fun()->P.finish ~budget:(budget()) ~final_source_bridge:bridge registration ~record ~result);
  require(!calls=[])"Foreign ancestor invoked final source reads";
  (* Checker exhaustion after the first read must not reach the second read. *)
  let exhausting:P.final_source_bridge={bridge with check_construct=(fun active->
    calls:= !calls@["check-source"];W.charge active(W.remaining active);U.candidate upstream)} in
  (try ignore(P.finish ~budget:work ~final_source_bridge:exhausting registration ~record ~result);
    failwith "Exhausted final check accepted" with Diagnostic.Error value->
      require(W.is_exhaustion work value)"Final check lost its actual lifetime exhaustion");
  require(!calls=["check-source"])"Exhausted independent check invoked return source"

let explicit_authority directory=
  let work,upstream=original directory "DNA" in
  let request,registry,manifests=authority directory "RNA" in
  let authored:P.authority={request;registry;manifests} in
  let owner=U.manager upstream in
  let prepared=P.prepare ~budget:work ~authority:authored upstream in
  require(P.prepared_authority prepared==authored && U.request upstream!=request && U.registry upstream!=registry)
    "Molecular authoring authority was replaced with Construct authority";
  require(List.assoc "molecular_profile"(P.dependencies prepared)=Canonical.fingerprint(Json.String "RNA-CDS"))
    "Molecular dependency profile used the returned Construct target";
  List.iter(fun(key,value)->M.set_dependency owner key value)(P.dependencies prepared);
  let profile=P.prepare_profile ~budget:work prepared in
  M.register_completion_profile owner(P.completion_profile profile);
  let marker=Failure "external authored molecular call" and invoked=ref false in
  let emitter_bridge:P.emitter_bridge={emit=(fun active ~input:_ ~request:actual ~construct ~registry:actual_registry ~manifests:actual_manifests->
    require(active==work && actual==request && actual_registry==registry && actual_manifests==manifests)
      "Molecular callback lost the exact caller-authored roots";
    require(R.Candidate.fingerprint construct=R.Candidate.fingerprint(U.candidate upstream))
      "Molecular callback lost actual upstream record input";
    invoked:=true;raise marker);
    host_proposal=(fun _ ~output:_ ~source_links:_->failwith "Failed emitter reached proposal")} in
  let registration=P.prepare_registration ~budget:work ~emitter_bridge profile in
  require(C.Pass_contract.consumes_requirements(P.contract registration)=Composition.requirement_ids(R.Request.composition request))
    "Molecular contract used upstream requirements instead of caller authority";
  register owner registration;
  (try ignore(M.run owner ~pass_id:"construct_to_molecular" ~input_id:"construct" ~output_id:"molecular"());
    failwith "Authored callback did not raise" with error->require(error==marker)"Authored callback exception changed");
  require(!invoked && keys "records"(inspect owner)=["components";"construct"])
    "Caller authority mismatch lost ordinary partial-manager behavior";
  let context=C.Pass_context.make ~input:(C.Stage_record.payload(U.record upstream)) ~output:None
    ~target:(R.Request.target(U.request upstream)) ~configuration:(Json.Object[])
    ~dependencies:(P.dependencies prepared) ~requirements:[] () in
  (match List.assoc "encoding_composition"(P.validators registration) work context with
   |M.Decision decision->let evidence=C.Check_decision.evidence decision in
       require(field "registry"(field "dependencies" evidence)=Json.String(Component_registry.fingerprint registry))
         "Linkage validator used captured upstream registry"
   |_->failwith "Linkage validator did not return a decision")

let ()=
  require(Array.length Sys.argv=2)"Expected independent original reference-manager authority directory";
  let directory=Sys.argv.(1) in
  let rna=successful directory "RNA" in
  ignore(successful directory "DNA");
  proposal_mutations directory;
  changed_sequence directory rna;
  partial_order directory;
  opaque_emitter directory;
  final_sources directory;
  explicit_authority directory;
  print_endline "Reference molecular pipeline: same manager, staged mutation order, live provider roots, exact spelling and retained failures checked."
