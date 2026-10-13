open Bioc_wire
module Base = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
module S = Bioc_service.Policy_controlled_workflow_service
module R = Bioc_domain.Policy_controlled_workflow_request
module BR = Bioc_domain.Policy_controlled_behavior_request
module Original = Bioc_domain.Policy_controlled_composition_request
let checks=ref 0
let require condition message = incr checks; if not condition then failwith message
let obj fields=Json.Object fields
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec edit path change raw=match path with
  | []->change raw
  | key::rest->match raw with
    | Json.Array rows->Json.Array(List.mapi(fun i row->if string_of_int i=key then edit rest change row else row)rows)
    | _->set key(edit rest change(get key raw))raw
let put path value=edit path(fun _->value)
let read path=
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    Json.parse_bounded ~max_bytes:4_000_000 ~max_nodes:100_000
      (really_input_string channel(in_channel_length channel)))
let rejects code action=incr checks;match action()with
  | _->failwith("Expected rejection "^code)
  | exception Diagnostic.Error diagnostic->
      if diagnostic.code<>code then failwith("Expected "^code^", got "^diagnostic.code)
let request operation payload:Protocol.request={request_id="rc6-independent-original";operation;payload}
let prepare executable invocation=match Producer.scoped_handle executable invocation with
  | Some(reply:Base.scoped_reply)->
      require(reply.status=Protocol.Ok && reply.diagnostics=[])"Joined operation failed preparation";
      let result=Option.get reply.result in
      let frame=Protocol.response ~executable ~request:(Some invocation) ~status:reply.status
        ~result:reply.result reply.diagnostics in result,frame,reply.before_encode
  | None->failwith"Joined operation has no scoped dispatch"
let complete executable invocation=let result,frame,guard=prepare executable invocation in guard frame;result
let refresh raw=set "limits"(R.project_limits(BR.of_json(get "behavior_request" raw)))raw
let rebind raw candidate=
  let authority=R.of_json raw in
  candidate |> set "request_fingerprint"(str(R.fingerprint authority))
    |> put ["material_candidate";"request_fingerprint"](str(Original.fingerprint(R.original authority)))
    |> put ["behavior_candidate";"request_fingerprint"](str(BR.fingerprint(R.behavior authority)))
let rebind_material_roles raw =
  let module N = Bioc_domain.Molecule in
  let material=get "material_candidate" raw in
  let inventory=get "inventory"(get "construction" material)in
  let molecules=List.map N.of_json(Json.array(get "molecules" inventory))in
  edit ["material_candidate";"construction";"inventory";"role_instances"](fun rows->
    Json.Array(List.map(fun row->
      let id=text "subject_id" row in
      let molecule=List.find(fun (value:N.t)->N.id value=id)molecules in
      set "subject_fingerprint"(str(N.fingerprint molecule))row)(Json.array rows)))raw

let ()=
  require(Array.length Sys.argv=3)"Supply workflow and independent material literal fixture";
  let raw=read Sys.argv.(1) and material=read Sys.argv.(2) in
  let compiled=complete Protocol.Core(request S.producer_operation(obj["request",raw]))in
  let candidate=get "candidate" compiled and report=get "report" compiled in
  require(text "status" report="controlled_workflow_accepted" && text "outcome" report="pass" &&
    get "artifact" compiled=Json.Null)"Compilation did not freshly join both original children";
  let invoke operation=request operation(obj["request",raw;"candidate",candidate])in
  let core=complete Protocol.Core(invoke "check-policy-controlled-workflow")
  and verify=complete Protocol.Verify(invoke "check-policy-controlled-workflow")in
  require(Json.equal core verify && Json.equal(get "report" core)report)
    "Core and independent Verify joined checks differ";
  List.iter(fun executable->
    let replay=complete executable(request "replay-policy-controlled-workflow"
      (obj["request",raw;"candidate",candidate;"report",report]))in
    require(Json.equal(get "report" replay)report && get "artifact" replay=Json.Null)
      "Fresh replay altered the exact joined report") [Protocol.Core;Protocol.Verify];
  let exported=complete Protocol.Verify(invoke "export-policy-controlled-workflow")in
  let core_export=complete Protocol.Core(invoke "export-policy-controlled-workflow")in
  require(Json.equal exported core_export)"Core and Verify produced different exact paired exports";
  let artifact=get "artifact" exported in
  Json.exact_fields ["fasta";"fasta_sha256";"manifest";"manifest_sha256"](Json.object_fields artifact);
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  require(str fasta=get "fasta"(get "expected" material) &&
    Canonical.sha256 fasta=text "fasta_sha256" artifact &&
    Canonical.fingerprint manifest=text "manifest_sha256" artifact)
    "Joined publication changed the independent ordered RNA bytes or pins";
  Json.exact_fields ["schema_version";"stage";"request";"limits";"candidate";"report";
    "request_fingerprint";"candidate_fingerprint";"invocation_fingerprint";"report_fingerprint";
    "members";"empirical_status";"human_use";"therapeutic_export"](Json.object_fields manifest);
  require(get "request" manifest=raw && get "limits" manifest=get "limits" raw &&
    Json.equal(get "report" manifest)report && get "candidate" manifest=candidate &&
    text "stage" manifest="joined" && text "empirical_status" manifest="unassessed" &&
    text "human_use" manifest="unassessed" && text "therapeutic_export" manifest="withheld")
    "Manifest lost complete original authority or changed the supported claim";
  let damaged=candidate |> put ["material_candidate";"construction";"inventory";"molecules";"0";"sequence"]
      (str "GCAUGGCUUAAGGAAAA") |> rebind_material_roles in
  let rejected=complete Protocol.Verify(request "export-policy-controlled-workflow"
    (obj["request",raw;"candidate",damaged]))in
  require(get "artifact" rejected=Json.Null && text "outcome"(get "report" rejected)="fail" &&
    text "outcome"(get "behavior"(get "report" rejected))="pass")
    "Behavior-only PASS published structurally rejected material";
  let missing=raw |> edit ["behavior_request";"readout_evidence";"samples";"3"]
    (fun row->row |> set "status"(str "missing") |> set "observed_tick" Json.Null) |> refresh in
  let unknown=complete Protocol.Core(request S.producer_operation(obj["request",missing]))in
  require(text "outcome"(get "report" unknown)="unknown" &&
    text "outcome"(get "material"(get "report" unknown))="pass")
    "Material-only PASS hid unknown source evidence";
  let unknown_export=complete Protocol.Verify(request "export-policy-controlled-workflow"
    (obj["request",missing;"candidate",get "candidate" unknown]))in
  require(get "artifact" unknown_export=Json.Null &&
    Json.equal(get "report" unknown_export)(get "report" unknown))
    "Unknown joined result published or lost complete counterexample evidence";
  let late=raw |> edit ["behavior_request";"original"](fun original->
    let model=get "mechanism_model" original |> edit ["body";"delays"](set "onset_ticks"(Json.int 3))in
    let identity=get "identity" model |> set "content_fingerprint"(str(Canonical.fingerprint(get "body" model)))in
    original |> set "mechanism_model"(set "identity" identity model)
      |> edit ["catalog_binding"](set "model_identity" identity)
      |> put ["source_authority";"control_contract";"actual_delays";"onset_ticks"](Json.int 3)) |> refresh in
  let late_result=complete Protocol.Core(request S.producer_operation(obj["request",late]))in
  let late_report=get "report" late_result in
  require(text "status" late_report="not_accepted" && text "outcome" late_report="fail" &&
    text "outcome"(get "material" late_report)="pass" &&
    text "model_correspondence"(get "behavior" late_report)="pass")
    "Material and exact model PASS hid the independent source deadline failure";
  let late_export=complete Protocol.Verify(request "export-policy-controlled-workflow"
    (obj["request",late;"candidate",get "candidate" late_result]))in
  require(get "artifact" late_export=Json.Null && Json.equal(get "report" late_export)late_report)
    "Known behavior failure was exported or its full evidence changed";
  let child_bytes=max (String.length(Canonical.encode(get "material" report)))
    (String.length(Canonical.encode(get "behavior" report)))+4096 in
  let report_limited=raw |> put ["behavior_request";"original";"budgets";"max_report_bytes"]
    (Json.int child_bytes) |> refresh in
  rejects "controlled_workflow_publication_limit"(fun()->prepare Protocol.Verify
    (request "check-policy-controlled-workflow"(obj["request",report_limited;
      "candidate",rebind report_limited candidate])));
  rejects "controlled_workflow_assessment_mismatch"(fun()->prepare Protocol.Verify
    (request "replay-policy-controlled-workflow"(obj["request",raw;"candidate",candidate;
      "report",set "empirical_status"(str "validated")report])));
  require(Producer.scoped_handle Protocol.Verify(request S.producer_operation(obj["request",raw]))=None)
    "Verify acquired a constructor";
  (match Producer.handle Protocol.Verify(request S.producer_operation(obj["request",raw]))with
   | Protocol.Unsupported,None,[diagnostic]->require(diagnostic.code="unsupported_operation")"Wrong Verify refusal"
   | _->failwith"Verify dispatch attempted joined construction");
  rejects "unsupported_operation"(fun()->S.prepare_generated ~executable:Protocol.Verify
    ~request:(request S.producer_operation(obj["request",raw]))
    ~produce:(fun ~charge:_ _->failwith"Verify invoked producer"));
  rejects "controlled_workflow_service_publication_guard"(fun()->Base.handle Protocol.Verify
    (invoke "export-policy-controlled-workflow"));
  List.iter(fun (label,change)->
    let _,frame,guard=prepare Protocol.Verify(invoke "export-policy-controlled-workflow")in
    rejects "controlled_workflow_service_publication_guard"(fun()->guard(change frame));
    rejects "controlled_workflow_service_publication_guard"(fun()->guard frame);
    require(label<>"")"Unnamed frame mutation")
    ["id",set "request_id"(str "foreign");"operation",set "operation"(str S.producer_operation);
     "role",edit ["core"](set "executable"(str "core"));
     "artifact",edit ["result";"artifact"](fun value->
       let changed=text "fasta" value^"A"in value |> set "fasta"(str changed)
         |> set "fasta_sha256"(str(Canonical.sha256 changed)))];
  let _,frame,guard=prepare Protocol.Verify(invoke "check-policy-controlled-workflow")in
  guard frame;rejects "controlled_workflow_service_publication_guard"(fun()->guard frame);
  let prepared=Z.to_int(Json.integer(get "preparation_charged_work"(get "usage" exported)))in
  let limited=raw |> put ["behavior_request";"original";"budgets";"max_work"](Json.int(prepared+65536)) |> refresh in
  let rebound=rebind limited candidate in
  let _,frame,guard=prepare Protocol.Verify(request "export-policy-controlled-workflow"
    (obj["request",limited;"candidate",rebound]))in
  rejects "controlled_workflow_service_work_limit"(fun()->guard frame);
  rejects "controlled_workflow_service_publication_guard"(fun()->guard frame);
  let tiny=raw |> put ["behavior_request";"original";"budgets";"max_work"](Json.int 1)in
  rejects "controlled_workflow_service_work_limit"(fun()->prepare Protocol.Core
    (request S.producer_operation(obj["request",tiny])));
  List.iter(fun executable->match Producer.handle executable(request "capabilities"(obj[]))with
    | Protocol.Ok,Some result,[]->require(Json.equal(get "policy_controlled_workflow"(get "profiles" result))
        (if executable=Protocol.Core then S.producer_profile else S.profile))"Advertised joined profile differs"
    | _->failwith"Capabilities failed") [Protocol.Core;Protocol.Verify];
  Printf.printf "controlled workflow service: %d checks\n" !checks
