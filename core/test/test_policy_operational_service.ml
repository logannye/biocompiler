open Bioc_wire
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
let require condition message = if not condition then failwith message
let get name value = Json.field name (Json.object_fields value)
let obj fields = Json.Object fields
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
