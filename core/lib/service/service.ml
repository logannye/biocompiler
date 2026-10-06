open Bioc_wire

let capabilities = Json.Object [
    "schema_version", Json.String "biocompiler.core_capabilities.v1";
    "operations", Json.Array (List.map (fun value -> Json.String value) (["capabilities"; "canonicalize"; "validate-intent"; "verify-lowering"; "verify-architecture"; "replay-architecture"] @ Policy_service.operations @ Policy_operational_service.operations @ Policy_implementation_service.operations @ Policy_material_service.operations @ Realization_service.operations @ Verification_workflow_service.operations @ Verification_workflow_authority.operations));
    "intent_schemas", Json.Array [Json.String Bioc_domain.Intent.schema_version];
    "canonicalization", Json.String "python-json-v1";
    "validation_scopes", Json.Array (List.map (fun value -> Json.String value)
      ([Bioc_domain.Intent.validation_scope; Bioc_checker.Lowering_check.validation_scope;
        Architecture_service.validation_scope; Policy_service.validation_scope; Policy_operational_service.validation_scope; Policy_implementation_service.validation_scope; Policy_material_service.validation_scope] @ Realization_service.validation_scopes @ Verification_workflow_service.validation_scopes @ Verification_workflow_authority.validation_scopes));
    "profiles", Json.Object (("policy_material", Policy_material_service.profile) :: ("policy_implementation", Policy_implementation_service.profile) :: ("policy_operational", Policy_operational_service.profile) :: ("policy_frontend", Policy_service.profile) :: ("architecture", Architecture_service.profile) :: ("artifact_transport", Artifact_io.profile) ::
      ("artifact_transport_authority", Artifact_io.authority_profile) ::
      Realization_service.profiles @ Verification_workflow_service.profiles @ Verification_workflow_authority.profiles);
    "limits", Protocol.limits;
    "claim_scope", Json.String "Structural intent validation, frozen source-to-Behavior correspondence, supplied architecture contracts and independently executed finite-history model checks. No search completeness, empirical function or human-use admission."
  ]

let handle executable (request : Protocol.request) =
  match request.operation with
  | "capabilities" ->
      let fields = Json.object_fields request.payload in
      Json.exact_fields [] fields;
      Protocol.Ok, Some capabilities, []
  | "canonicalize" ->
      let canonical_json = Canonical.encode request.payload in
      Protocol.Ok, Some (Json.Object [
          "canonical_json", Json.String canonical_json;
          "sha256", Json.String (Canonical.sha256 canonical_json)]), []
  | "validate-intent" -> Protocol.Ok, Some (Bioc_checker.Intent_check.check request.payload), []
  | operation when List.mem operation Policy_service.operations ->
      Protocol.Ok, Some (Policy_service.handle ~operation request.payload), []
  | operation when List.mem operation Policy_operational_service.operations ->
      Protocol.Ok, Some (Policy_operational_service.handle ~operation request.payload), []
  | operation when List.mem operation Policy_implementation_service.operations ->
      Protocol.Ok, Some (Policy_implementation_service.handle ~operation request.payload), []
  | operation when List.mem operation Policy_material_service.operations ->
      Protocol.Ok, Some (Policy_material_service.handle ~operation request.payload), []
  | "verify-architecture" -> Protocol.Ok, Some (Architecture_service.verify ~replay:false request.payload), []
  | "replay-architecture" -> Protocol.Ok, Some (Architecture_service.verify ~replay:true request.payload), []
  | "verify-lowering" ->
      let fields = Json.object_fields request.payload in
      Json.exact_fields ["expected_request"; "behavior"] fields;
      let expected_request = Bioc_domain.Build_request.of_json (Json.field "expected_request" fields) in
      let behavior = Bioc_domain.Behavior.of_json (Json.field "behavior" fields) in
      (try
         let report = Bioc_checker.Lowering_check.check ~expected_request ~behavior in
         Protocol.Ok, Some (Bioc_checker.Lowering_check.to_json report), []
       with Diagnostic.Error diagnostic when String.starts_with ~prefix:"unsupported_lowering_" diagnostic.code ->
         Protocol.Unsupported, None, [diagnostic])
  | operation when List.mem operation Realization_service.operations ->
      Protocol.Ok, Some (Realization_service.handle ~executable ~request_id:request.request_id
          ~operation request.payload), []
  | _ -> Protocol.Unsupported, None, [{
      Diagnostic.code = "unsupported_operation";
      message = "This executable does not implement the requested operation; no fallback or acceptance is granted.";
      path = Some "/operation" }]

let artifact_request ~budget ~control_bytes ~executable (request:Protocol.request) =
  let fields=Json.object_fields request.payload in
  Json.exact_fields ["transport";"authority";"retained_record";"output_limit";"operation_payload"] fields;
  let authority_only = List.mem request.operation Verification_workflow_authority.operations in
  let transport = if authority_only then "biocompiler.core.artifact_transport.authority.v1"
    else "biocompiler.core.artifact_transport.v1" in
  Diagnostic.require (Json.string (Json.field "transport" fields)=transport)
    "artifact_transport" "Unsupported artifact transport profile.";
  Diagnostic.require (authority_only || List.mem request.operation Verification_workflow_service.operations)
    "unsupported_operation" "This operation is unavailable through the artifact channel.";
  let authority=Artifact_io.descriptor_of_json ~max_bytes:Limits.max_request_bytes (Json.field "authority" fields) in
  let retained_record=match Json.field "retained_record" fields with
    | Json.Null -> None
    | raw -> Some (Artifact_io.descriptor_of_json ~max_bytes:(64*1024*1024) raw) in
  Diagnostic.require ((request.operation="replay-verification-workflow") = Option.is_some retained_record)
    "workflow_protocol_record" "Replay requires a retained record; fresh execution requires none.";
  Diagnostic.require ((Sys.argv.(3)="-") = Option.is_none retained_record)
    "artifact_transport" "Retained descriptor argument presence differs from the control message.";
  let limit=Json.integer (Json.field "output_limit" fields) in
  Diagnostic.require (Z.sign limit>0 && Z.compare limit (Z.of_int (64*1024*1024))<=0)
    "artifact_transport" "Invalid artifact output byte limit.";
  let limit=Z.to_int limit in
  Artifact_io.with_fds ~authority:Sys.argv.(2) ~retained_record:Sys.argv.(3) ~output:Sys.argv.(4) (fun files ->
    Artifact_io.charge_control files ~budget control_bytes;
    let raw_authority=Artifact_io.read_authority files ~budget authority in
    let load_retained_record=Option.map (fun descriptor () ->
      match Artifact_io.read_record files ~budget (Some descriptor) with
      | Some raw -> raw
      | None -> Diagnostic.fail "artifact_transport" "Retained record descriptor is missing.") retained_record in
    let response=if authority_only then
      Verification_workflow_authority.handle_in ~budget ~executable
        ~request_id:request.request_id ~operation:request.operation
        ~payload:(Json.field "operation_payload" fields) ~authority:raw_authority ()
      else Verification_workflow_service.handle_in ~budget ~executable
        ~request_id:request.request_id ~operation:request.operation
        ~payload:(Json.field "operation_payload" fields) ~authority:raw_authority ?load_retained_record () in
    let artifact=Artifact_io.write_output files ~budget ~limit response.artifact in
    Protocol.Ok,Some (Json.Object [
      "schema_version",Json.String "biocompiler.core.artifact_response.v1";
      "transport",Json.String transport;
      "authority",Artifact_io.descriptor_json authority;
      "retained_record",Option.fold ~none:Json.Null ~some:Artifact_io.descriptor_json retained_record;
      "artifact",Artifact_io.descriptor_json artifact;
      "result",response.result]),[])

let run ?(handler=handle) executable =
  let current_request = ref None and current_budget = ref None in
  let artifact_channel = Array.length Sys.argv <> 1 in
  let response, code =
    try
      Diagnostic.require (not artifact_channel ||
        (Array.length Sys.argv=5 && Sys.argv.(1)="--artifact-fds-v1"))
        "unexpected_arguments" "Expected standard JSON input or the exact inherited artifact descriptor arguments.";
      let raw = if artifact_channel then Artifact_io.read_control () else Protocol.read_stdin () in
      let request = Protocol.decode_request (if artifact_channel then
          Json.parse_artifact ~max_bytes:Artifact_io.max_control_bytes ~max_nodes:Limits.max_json_nodes raw
        else Json.parse raw) in
      current_request := Some request;
      let status, result, diagnostics = if artifact_channel then (
        let payload=Json.field "operation_payload" (Json.object_fields request.payload) in
        let limits=if List.mem request.operation Verification_workflow_authority.operations then
            Verification_workflow_authority.limits_of_payload payload
          else Verification_workflow_service.limits_of_payload payload in
        let budget=Bioc_realization_checker.Verification_workflow_budget.create ~limits () in
        current_budget:=Some budget;
        artifact_request ~budget ~control_bytes:(String.length raw) ~executable request)
        else handler executable request in
      Protocol.response ~executable ~request:!current_request ~status ~result diagnostics,
      (match status with Protocol.Ok -> 0 | Protocol.Error -> 2 | Protocol.Unsupported -> 3)
    with
    | Diagnostic.Error diagnostic ->
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None [diagnostic], 2
    | (Stack_overflow | Out_of_memory) ->
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None
          [{ Diagnostic.code = "resource_exhausted"; message = "Core resources exhausted; no acceptance is granted."; path = None }], 2
    | exception_value ->
        (* Internal exception detail goes to stderr, never into a success value. *)
        prerr_endline (Printexc.to_string exception_value);
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None
          [{ Diagnostic.code = "internal_error"; message = "Core failed; no acceptance is granted."; path = None }], 2
  in
  let encoded, code =
    try
      if code=0 then Option.iter (fun budget ->
        Bioc_realization_checker.Verification_workflow_budget.charge budget
          (16*Artifact_io.max_control_bytes+8*Limits.max_json_nodes)) !current_budget;
      let maximum=if artifact_channel then Artifact_io.max_control_bytes else Limits.max_response_bytes in
      let encoded = Canonical.encode_bounded ~max_bytes:maximum response in
      Diagnostic.require (String.length encoded < maximum)
        "response_too_large" "Core response exceeds its byte limit.";
      encoded, code
    with Diagnostic.Error diagnostic ->
      let response = Protocol.response ~executable ~request:None ~status:Protocol.Error ~result:None [diagnostic] in
      Canonical.encode response, 2
  in
  output_string stdout encoded;
  output_char stdout '\n';
  flush stdout;
  exit code
