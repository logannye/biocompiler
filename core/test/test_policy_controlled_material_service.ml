open Bioc_wire
module Base = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
module S = Bioc_service.Policy_controlled_material_service
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
let rejects label action = match action () with
  | _ -> failwith (label ^ ": accepted forbidden operation")
  | exception Diagnostic.Error _ -> ()
let request operation payload : Protocol.request = {request_id="rc4-original";operation;payload}
let prepare executable request = match Producer.scoped_handle executable request with
  | Some (reply:Base.scoped_reply) ->
      require (reply.status=Protocol.Ok && reply.diagnostics=[]) "Material did not prepare success";
      let result=match reply.result with Some value->value | None->failwith "Absent prepared result" in
      let frame=Protocol.response ~executable ~request:(Some request) ~status:reply.status
        ~result:reply.result reply.diagnostics in
      result,frame,reply.before_encode
  | None -> failwith "Material is missing scoped dispatch"
let complete executable invocation =
  let result,frame,guard=prepare executable invocation in guard frame;result
let () =
  require (Array.length Sys.argv=3) "Supply original request and independent literal material fixtures";
  let original=read Sys.argv.(1) and fixture=read Sys.argv.(2) in
  let literal=get "literal_candidate" fixture in
  let constructed=complete Protocol.Core (request S.producer_operation (obj ["request",original])) in
  require (Json.equal (get "candidate" constructed) literal) "Constructor differs from independent pair literal";
  require (get "artifact" constructed=Json.Null) "Construction bypassed fresh publication";
  let invoke operation=request operation (obj ["request",original;"candidate",literal]) in
  let core=complete Protocol.Core (invoke "check-policy-controlled-material") in
  let verify=complete Protocol.Verify (invoke "check-policy-controlled-material") in
  require (Json.equal core verify) "Core and independent Verify checking differ";
  require (Json.equal (get "report" core) (get "report" constructed)) "Construction history changed structural verdict";
  let published=complete Protocol.Verify (invoke "publish-policy-controlled-material") in
  let artifact=get "artifact" published in
  let fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n>rna_0002 alphabet=RNA\nCCAUGGGUUAAGGAAAA\n" in
  require (text "fasta" artifact=fasta && text "fasta_sha256" artifact=Canonical.sha256 fasta)
    "Whole ordered pair FASTA differs from independent literal";
  let manifest=get "manifest" artifact in
  require (text "manifest_sha256" artifact=Canonical.fingerprint manifest &&
    Json.equal (get "request" manifest) original && Json.equal (get "candidate" manifest) literal &&
    Json.equal (get "report" manifest) (get "report" published)) "Manifest lost complete original authority";
  require (text "status" (get "report" published)="checked_controlled_material" &&
    text "behavior_status" manifest="not_performed" && text "human_use" manifest="unassessed" &&
    text "therapeutic_export" manifest="withheld") "Structural pair acquired an unsupported behavioral claim";
  let rows=Json.array (get "members" manifest) in
  require (List.map (text "member_id") rows=["rna-a";"rna-b"]) "Member mapping/order changed";
  let forged label transform =
    let _,frame,guard=prepare Protocol.Verify (invoke "publish-policy-controlled-material") in
    rejects label (fun () -> guard (transform frame));
    rejects (label ^ " reuse") (fun () -> guard frame) in
  forged "foreign outer id" (set "request_id" (str "foreign"));
  forged "foreign operation" (set "operation" (str S.producer_operation));
  forged "foreign executable" (update "core" (set "executable" (str "core")));
  forged "locally repinned manifest" (update "result" (update "artifact" (fun artifact ->
    let changed=set "human_use" (str "admitted") (get "manifest" artifact) in
    artifact |> set "manifest" changed |> set "manifest_sha256" (str (Canonical.fingerprint changed)))));
  let _,frame,guard=prepare Protocol.Verify (invoke "check-policy-controlled-material") in
  guard frame; rejects "one-shot guard reuse" (fun () -> guard frame);
  rejects "unscoped bypass" (fun () -> Base.handle Protocol.Core (invoke "check-policy-controlled-material"));
  require (Producer.scoped_handle Protocol.Verify
    (request S.producer_operation (obj ["request",original]))=None) "Verify gained construction";
  rejects "Verify generated service bypass" (fun () -> S.prepare_generated ~executable:Protocol.Verify
    ~request:(request S.producer_operation (obj ["request",original]))
    ~produce:(fun ~charge:_ _ -> failwith "Verify invoked a producer"));
  let bad_request=update "budgets" (set "max_work" (Json.int 1)) original in
  rejects "original cumulative work exhaustion" (fun () ->
    prepare Protocol.Core (request S.producer_operation (obj ["request",bad_request])));
  let reverse rows=Json.Array (List.rev (Json.array rows)) in
  let altered=update "construction" (fun content -> content
    |> update "member_order" reverse
    |> update "inventory" (update "molecules" reverse)) literal in
  let refused=complete Protocol.Verify (request "publish-policy-controlled-material"
    (obj ["request",original;"candidate",altered])) in
  require (get "artifact" refused=Json.Null && text "status" (get "report" refused)="not_accepted")
    "Failed independent reconstruction published a partial pair";
  let prepared=Z.to_int (Json.integer (get "preparation_charged_work" (get "usage" core))) in
  let small=update "budgets" (set "max_work" (Json.int (prepared+2048))) original in
  let repinned=set "request_fingerprint" (str (Canonical.fingerprint small)) literal in
  let _,frame,guard=prepare Protocol.Verify (request "check-policy-controlled-material"
    (obj ["request",small;"candidate",repinned])) in
  rejects "final frame exhaustion" (fun () -> guard frame);
  rejects "exhausted frame reuse" (fun () -> guard frame);
  List.iter (fun key ->
    let limited=update "budgets" (set key (Json.int 1)) original in
    let repinned=set "request_fingerprint" (str (Canonical.fingerprint limited)) literal in
    rejects ("original " ^ key ^ " exhausted") (fun () ->
      prepare Protocol.Verify (request "publish-policy-controlled-material"
        (obj ["request",limited;"candidate",repinned])))) ["max_report_bytes";"max_report_nodes"];
  List.iter (fun executable ->
    let caps=request "capabilities" (obj []) in
    match Producer.handle executable caps with
    | Protocol.Ok,Some result,[] ->
        let profile=get "policy_controlled_composition_material" (get "profiles" result) in
        require (Json.equal profile (if executable=Protocol.Core then S.producer_profile else S.profile))
          "Material capability does not describe actual supported operations"
    | _ -> failwith "Capabilities failed") [Protocol.Core;Protocol.Verify];
  print_endline "controlled material service: fresh complete pair, independent verification, bounded one-shot frame and manifest publication passed"
