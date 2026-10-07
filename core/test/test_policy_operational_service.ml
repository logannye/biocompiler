open Bioc_wire
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
let require condition message = if not condition then failwith message
let get name value = Json.field name (Json.object_fields value)
let obj fields = Json.Object fields
let replace name replacement value = obj (List.map (fun (key,item) -> key,if key=name then replacement else item) (Json.object_fields value))
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in channel)
    (fun () -> Json.parse (really_input_string channel (in_channel_length channel)))
let run handler role operation payload =
  let request : Protocol.request = {request_id="policy-operational-literal";operation;payload} in
  match handler role request with
  | Protocol.Ok, Some result, [] -> result
  | _ -> failwith "Operational service failed to return complete scoped result"
let () =
  require (Array.length Sys.argv = 2) "Supply independent operational literal fixture";
  let fixture = read Sys.argv.(1) in
  let document = get "document" fixture and definitions = get "definitions" fixture in
  let authority = ["document",document;"definitions",definitions] in
  let compiled = run Producer.handle Protocol.Core "compile-policy" (obj authority) in
  let candidate = get "candidate" compiled in
  let checked = run Service.handle Protocol.Verify "check-policy-lowering" (obj (authority @ ["candidate",candidate])) in
  require (Json.equal (get "report" compiled) (get "report" checked)) "Independent checker changed complete lowering report";
  let execution = authority @ ["candidate",candidate;"timeline",get "timeline" fixture] in
  let core = run Producer.handle Protocol.Core "execute-policy" (obj execution)
  and verify = run Service.handle Protocol.Verify "execute-policy" (obj execution) in
  require (Json.equal core verify) "Core/Verify reference results differ";
  let report = get "report" verify in
  let replay = run Service.handle Protocol.Verify "replay-policy-execution" (obj (execution @ ["report",report])) in
  require (Json.equal replay verify) "Complete fresh replay changed its authority/result identity";
  List.iter (fun (key, expected) -> require (get key report = Json.String expected) ("Unsupported claim changed: " ^ key))
    ["artifact","withheld";"target_status","unassessed";"realization","unassessed"];
  let forged = obj (List.map (fun (key,value) -> key, if key="artifact" then Json.String "produced" else value)
      (Json.object_fields report)) in
  (match run Service.handle Protocol.Verify "replay-policy-execution" (obj (execution @ ["report",forged])) with
   | _ -> failwith "Forged replay accepted"
   | exception Diagnostic.Error diagnostic -> require (diagnostic.code="policy_execution_replay") "Wrong replay rejection");
  let declarations=Json.array(get "declarations" document) in
  let completion=List.find(fun value->get "id" value=Json.String "completion")declarations in
  let unsupported_replay replacement =
    let source=replace "declarations"(Json.Array(List.map(fun value->if get "id" value=Json.String "completion" then replacement else value)declarations))document in
    let source_authority=["document",source;"definitions",definitions] in
    let source_assessment=run Service.handle Protocol.Verify "assess-policy"(obj["document",source]) in
    require(get "status"(get "assessment" source_assessment)=Json.String "valid")"Unsupported replay control lost source validity";
    let lowered=run Producer.handle Protocol.Core "compile-policy"(obj source_authority) in
    let inputs=source_authority@["candidate",get "candidate" lowered;"timeline",get "timeline" fixture] in
    let result=run Service.handle Protocol.Verify "execute-policy"(obj inputs) in
    let result_report=get "report" result in
    let executed=get "execution" result_report in
    let requirements=Json.array(get "requirements" executed) in
    let row=List.find(fun value->get "id" value=Json.String "completion")requirements in
    require(get "status" row=Json.String "unsupported")"Unsupported requirement gained a monitored verdict through the service";
    require(Json.equal(get "source" row)replacement)"Unsupported service report lost original requirement operands";
    let replayed=run Service.handle Protocol.Verify "replay-policy-execution"(obj(inputs@["report",result_report])) in
    require(Json.equal result replayed)"Fresh replay changed the unsupported requirement ledger";
    let altered_rows=List.map(fun value->if get "id" value=Json.String "completion" then replace "status"(Json.String "pass")value else value)requirements in
    let forged_report=replace "execution"(replace "requirements"(Json.Array altered_rows)executed)result_report in
    (match run Service.handle Protocol.Verify "replay-policy-execution"(obj(inputs@["report",forged_report])) with
     | _->failwith "Forged requirement PASS survived fresh replay"
     | exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_execution_replay")"Wrong forged requirement replay rejection") in
  unsupported_replay(replace "response"(replace "value"(Json.String "ceased")(get "response" completion))completion);
  let condition=get "condition" completion in
  let target=obj["$type",Json.String "Ref";"kind",Json.String "Subject";"id",Json.String "target"] in
  let entity=condition|>replace "value_type"(obj["$type",Json.String "TypeSpec";"kind",Json.String "entity";"unit",Json.Null;"entity_kind",Json.String "cell"])
    |>replace "value"Json.Null|>replace "ref"target|>replace "scope"target in
  let distinct=condition|>replace "op"(Json.String "distinct")|>replace "value"Json.Null|>replace "args"(Json.Array[entity;entity]) in
  unsupported_replay(replace "condition" distinct completion);
  let request : Protocol.request = {request_id="verify-producer-rejection";operation="compile-policy";payload=obj authority} in
  (match Service.handle Protocol.Verify request with
   | Protocol.Unsupported,None,_::_ -> ()
   | _ -> failwith "Standalone Verify acquired producer authority");
  let capabilities = run Service.handle Protocol.Verify "capabilities" (obj []) in
  require (Json.equal (get "policy_operational" (get "profiles" capabilities))
      Bioc_service.Policy_operational_service.profile) "Missing negotiated operational profile";
  let source = run Service.handle Protocol.Verify "assess-policy" (obj ["document",document]) in
  require (get "semantic_status" (get "assessment" source) = Json.String "unresolved")
    "Operational profile widened existing source-assessment claims";
  print_endline "Operational policy service, external authority and fresh standalone replay literals passed"
