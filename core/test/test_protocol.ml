open Bioc_wire

let require condition message = if not condition then failwith message
let request operation payload = Json.Object [
    "protocol", Json.String Protocol.version;
    "request_id", Json.String "test:1";
    "operation", Json.String operation;
    "payload", payload
  ]
let () =
  let decoded = Protocol.decode_request (request "capabilities" (Json.Object [])) in
  let status, result, diagnostics = Bioc_service.Service.handle Protocol.Verify decoded in
  require (status = Protocol.Ok && diagnostics = []) "Capabilities failed";
  let response = Protocol.response ~executable:Protocol.Verify ~request:(Some decoded) ~status ~result diagnostics in
  let identity = Json.field "core" (Json.object_fields response) |> Json.object_fields in
  require (Json.string (Json.field "executable" identity) = "verify") "Verifier identity missing";
  let unsupported = Protocol.decode_request (request "compile" (Json.Object [])) in
  let status, result, diagnostics = Bioc_service.Service.handle Protocol.Core unsupported in
  require (status = Protocol.Unsupported && result = None && diagnostics <> []) "Unsupported compile pretended to succeed";
  let malformed = Json.Object ["protocol", Json.String Protocol.version] in
  (match Protocol.decode_request malformed with
   | _ -> failwith "Incomplete request accepted"
   | exception Diagnostic.Error _ -> ());
  (match Protocol.response ~executable:Protocol.Core ~request:None ~status:Protocol.Ok ~result:None [] with
   | _ -> failwith "Malformed success response accepted"
   | exception Diagnostic.Error _ -> ());
  print_endline "protocol: roles, envelopes, errors and unsupported operations checked"
