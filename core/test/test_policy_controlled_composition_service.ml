open Bioc_wire
module Service = Bioc_service.Service
module S = Bioc_service.Policy_controlled_composition_service
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let set key replacement value = obj ((key,replacement)::List.remove_assoc key (Json.object_fields value))
let update key f value = set key (f (get key value)) value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:4_000_000 ~max_nodes:100_000
      (really_input_string channel (in_channel_length channel)))
let rejects label codes action = match action () with
  | _ -> failwith (label ^ ": accepted forbidden operation")
  | exception Diagnostic.Error diagnostic ->
      require (List.mem diagnostic.code codes) (label ^ ": wrong diagnostic " ^ diagnostic.code)
let request original : Protocol.request = {
  request_id="controlled-source-original"; operation="admit-policy-component-material";
  payload=obj ["request",original]
}
let prepare executable request = match Service.scoped_handle executable request with
  | Some reply ->
      require (reply.status=Protocol.Ok && reply.diagnostics=[]) "Admission did not prepare success";
      let result=match reply.result with Some value->value | None->failwith "Absent prepared result" in
      let frame=Protocol.response ~executable ~request:(Some request) ~status:reply.status
        ~result:reply.result reply.diagnostics in
      result,frame,reply.before_encode
  | None -> failwith "Controlled admission is missing its scoped dispatch"
let positive original =
  let invocation=request original in
  let core,core_frame,core_guard=prepare Protocol.Core invocation in
  core_guard core_frame;
  let verify,verify_frame,verify_guard=prepare Protocol.Verify invocation in
  verify_guard verify_frame;
  require (Json.equal core verify) "Core and Verify changed original-authority admission";
  require (text "schema_version" core=S.schema_version && text "validation_scope" core=S.validation_scope)
    "Controlled service lost its narrow version/scope";
  require (get "artifact" core=Json.Null) "Admission published a material artifact";
  let report=get "report" core in
  require (text "stage" report="admission" && text "status" report="admitted" &&
    text "construction_status" report="not_performed" && text "behavior_status" report="not_performed" &&
    text "empirical_status" report="unassessed") "Admission was promoted beyond original authority/domain checking";
  require (text "request_fingerprint" core=Canonical.fingerprint original &&
    text "report_fingerprint" core=Canonical.fingerprint report) "Complete original/report binding changed";
  let usage=get "usage" core in
  Json.exact_fields ["unit";"preparation_charged_work";"request_decoding_work";"publication"] (Json.object_fields usage);
  require (text "publication" usage="requires_original_one_shot_frame_guard") "Prepared result lost publication obligation";
  let prepared=Json.integer(get "preparation_charged_work" usage)
  and decoded=Json.integer(get "request_decoding_work" usage)
  and maximum=Json.integer(get "max_work"(get "budgets" original)) in
  require (Z.sign decoded>0 && Z.leq decoded prepared && Z.lt prepared maximum) "Invalid shared work accounting";
  rejects "consumed core frame" ["policy_controlled_service_publication_guard"] (fun()->core_guard core_frame);
  rejects "low-level scoped bypass" ["policy_controlled_service_publication_guard"]
    (fun()->Service.handle Protocol.Core invocation);
  List.iter (fun executable ->
    let capability_request:Protocol.request={request_id="caps";operation="capabilities";payload=obj []} in
    match Service.handle executable capability_request with
    | Protocol.Ok,Some capabilities,[] ->
        let profile=get "policy_controlled_composition_admission"(get "profiles" capabilities)in
        require (Json.equal profile S.profile) "Capability differs from exact admission profile";
        require (get "operations" profile=Json.Array[str "admit-policy-component-material"] &&
          text "stage" profile="admission" && text "artifact" profile="none") "Capability advertises execution or material publication"
    | _ -> failwith "Capabilities failed") [Protocol.Core;Protocol.Verify];
  Z.to_int prepared
let negative original preparation_work =
  let invocation=request original in
  let forgery label transform =
    let _,frame,guard=prepare Protocol.Verify invocation in
    rejects label ["policy_controlled_service_publication_guard"] (fun()->guard(transform frame));
    rejects (label ^ " reuse") ["policy_controlled_service_publication_guard"] (fun()->guard frame) in
  forgery "different request ID" (set "request_id"(str "foreign-request"));
  forgery "different operation" (set "operation"(str "export-policy-component-material"));
  forgery "different executable" (update "core"(set "executable"(str "core")));
  forgery "different result" (update "result"(set "artifact"(obj["claimed",str "accepted"])));
  forgery "extra outer authority" (set "authority" original);
  forgery "altered report and local rehash" (update "result"(fun result ->
    let report=set "behavior_status"(str "checked")(get "report" result)in
    result |> set "report" report |> set "report_fingerprint"(str(Canonical.fingerprint report))));
  List.iter (fun key ->
    let request={invocation with payload=set key (obj []) invocation.payload} in
    rejects ("unexpected payload " ^ key) ["unknown_field"]
      (fun()->prepare Protocol.Core request)) ["candidate";"report";"limits"];
  let with_budget key value=update "budgets"(set key(Json.int value))original in
  rejects "decoder work exhaustion" ["policy_controlled_service_work_limit"]
    (fun()->prepare Protocol.Core(request(with_budget "max_work" 1)));
  rejects "report byte limit" ["policy_material_input_limit"]
    (fun()->prepare Protocol.Verify(request(with_budget "max_report_bytes" 1)));
  rejects "report node limit" ["policy_material_input_limit"]
    (fun()->prepare Protocol.Verify(request(with_budget "max_report_nodes" 1)));
  (* The publication work shares the same owner. Leave enough for preparation
     after a scalar width change, but less than one full authority frame pass. *)
  let _,frame,guard=prepare Protocol.Core(request(with_budget "max_work" (preparation_work+1024)))in
  rejects "final frame work exhaustion" ["policy_controlled_service_work_limit"] (fun()->guard frame);
  rejects "exhausted guard reuse" ["policy_controlled_service_publication_guard"] (fun()->guard frame);
  rejects "unsupported preparation operation" ["unsupported_operation"] (fun()->
    S.prepare ~executable:Protocol.Core ~request:{invocation with operation="compile-policy-controlled-composition"});
  require (Service.scoped_handle Protocol.Verify {invocation with operation="compile-policy-controlled-composition"}=None)
    "Controlled source admission acquired producer dispatch"
let () =
  require (Array.length Sys.argv=2) "Supply complete original controlled request fixture";
  let original=read Sys.argv.(1)in
  let preparation_work=positive original in negative original preparation_work;
  print_endline "controlled service: source/domain-only admission, exact one-shot protocol publication and resource rejection controls passed"
