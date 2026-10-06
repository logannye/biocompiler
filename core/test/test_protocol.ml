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
  let fields = Json.object_fields (Option.get result) in
  require (Json.string (Json.field "schema_version" fields) = "biocompiler.core_capabilities.v1") "Capability schema missing";
  require (Json.array (Json.field "operations" fields) |> List.map Json.string =
    (["capabilities";"canonicalize";"validate-intent";"verify-lowering";"verify-architecture";"replay-architecture"] @
     Bioc_service.Policy_service.operations @ Bioc_service.Policy_operational_service.operations @ Bioc_service.Policy_implementation_service.operations @ Bioc_service.Policy_material_service.operations @ Bioc_service.Realization_service.operations @ Bioc_service.Verification_workflow_service.operations @
     Bioc_service.Verification_workflow_authority.operations))
    "Advertised operation census differs";
  let architecture = Json.field "architecture" (Json.object_fields (Json.field "profiles" fields)) in
  require (Json.equal architecture Bioc_service.Architecture_service.profile) "Architecture profile differs";
  List.iter (fun operation ->
      let missing = Protocol.decode_request (request operation (Json.Object [])) in
      match Bioc_service.Service.handle Protocol.Verify missing with
      | _ -> failwith "Standalone architecture checking accepted missing original authority"
      | exception Diagnostic.Error diagnostic -> require (diagnostic.code = "missing_field") "Unexpected architecture envelope diagnostic")
    ["verify-architecture";"replay-architecture"];
  List.iter (fun (name, expected) ->
      let actual = Json.field name (Json.object_fields (Json.field "profiles" fields)) in
      require (Json.equal actual expected) ("Realization profile differs: " ^ name))
    (Bioc_service.Realization_service.profiles @ Bioc_service.Verification_workflow_service.profiles @
     Bioc_service.Verification_workflow_authority.profiles @
     ["artifact_transport",Bioc_service.Artifact_io.profile;
      "artifact_transport_authority",Bioc_service.Artifact_io.authority_profile;
      "policy_material",Bioc_service.Policy_material_service.profile;
      "policy_implementation",Bioc_service.Policy_implementation_service.profile;
      "policy_operational",Bioc_service.Policy_operational_service.profile;
      "policy_frontend",Bioc_service.Policy_service.profile]);
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
