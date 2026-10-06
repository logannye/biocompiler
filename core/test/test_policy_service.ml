open Bioc_wire
module Service = Bioc_service.Service
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let replace key replacement value = Json.Object (List.map (fun (name, value) ->
  name, if name = key then replacement else value) (Json.object_fields value))
let request operation payload : Protocol.request = {request_id="policy-service-literal"; operation; payload}
let run executable operation payload =
  match Service.handle executable (request operation payload) with
  | Protocol.Ok, Some result, [] -> result
  | _ -> failwith "Policy service did not return a scoped source assessment"
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in channel)
    (fun () -> Json.parse (really_input_string channel (in_channel_length channel)))
let () =
  require (Array.length Sys.argv = 2) "Supply the frozen policy corpus path";
  let cases = Json.array (field "cases" (read Sys.argv.(1))) in
  let source = field "document" (List.hd cases) in
  let payload = Json.Object ["document",source] in
  let core = run Protocol.Core "assess-policy" payload in
  let verify = run Protocol.Verify "assess-policy" payload in
  require (Json.equal core verify) "Core and verifier source checker routing changed observations";
  let assessment = field "assessment" core in
  require (field "status" assessment = Json.String "valid") "Frozen example failed native source checking";
  List.iter (fun (key, expected) -> require (field key assessment = Json.String expected)
      ("Unsupported policy claim changed: " ^ key))
    ["semantic_status","unresolved";"target_status","unassessed";"lowering","unsupported";"artifact","withheld"];
  let replay = run Protocol.Verify "replay-policy-assessment"
      (Json.Object ["expected_document",source;"assessment",assessment]) in
  require (Json.equal replay verify) "Fresh replay changed its source-bound complete result";
  let forged = replace "artifact" (Json.String "produced") assessment in
  (match run Protocol.Verify "replay-policy-assessment"
      (Json.Object ["expected_document",source;"assessment",forged]) with
   | _ -> failwith "Forged native assessment was accepted"
   | exception Diagnostic.Error diagnostic -> require (diagnostic.code="policy_assessment_mismatch")
       "Fresh replay rejected at an unintended boundary");
  let capabilities = run Protocol.Verify "capabilities" (Json.Object []) in
  require (Json.equal (field "policy_frontend" (field "profiles" capabilities)) Bioc_service.Policy_service.profile)
    "Verifier omitted the exact source-checking profile";
  (match Service.handle Protocol.Core (request "lower-policy" payload) with
   | Protocol.Unsupported, None, _ :: _ -> ()
   | _ -> failwith "Unimplemented policy lowering gained an artifact or acceptance");
  print_endline "Policy native service and fresh replay literals passed"
