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
     Bioc_service.Policy_service.operations @ Bioc_service.Policy_operational_service.operations @ Bioc_service.Policy_implementation_service.operations @ Bioc_service.Policy_material_service.operations @ Bioc_service.Policy_component_material_service.operations @ Bioc_service.Policy_quantitative_assurance_service.operations @ Bioc_service.Policy_refinement_service.operations @ Bioc_service.Policy_module_linking_service.operations @
     ["check-policy-component-selection";"replay-policy-component-selection";"export-policy-component-selection"] @
     Bioc_service.Realization_service.operations @ Bioc_service.Verification_workflow_service.operations @
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
      "policy_coupled_wire",Json.Object(("operations",Json.Array(List.map(fun value->Json.String value)
        ["check-policy-component-material";"replay-policy-component-material";"export-policy-component-material";
         "check-policy-quantitative-assurance";"replay-policy-quantitative-assurance";"export-policy-quantitative-assurance";
         "check-policy-refinement";"replay-policy-refinement"]))::[
        "schema_version",Json.String "biocompiler.policy_coupled_json_graph.v0.1";
        "encoding",Json.String "lossless_typed_postorder_dag";
        "expanded_identity",Json.String "sha256_canonical_json";
        "expanded_node_count",Json.String "values_and_object_keys";
        "max_expanded_bytes",Json.int 8323072;"max_expanded_nodes",Json.int 1000000;
        "max_packet_bytes",Json.int 8323072;"max_packet_nodes",Json.int 249968;
        "max_depth",Json.int 128;"max_string_bytes",Json.int 4194304;"max_number_chars",Json.int 4300;
        "claims",Json.String "transport_only"]);
      "policy_coupled_assurance_export_wire",Json.Object[
        "schema_version",Json.String "biocompiler.policy_coupled_export_json_graph.v0.1";
        "encoding",Json.String "lossless_typed_postorder_dag";
        "expanded_identity",Json.String "sha256_canonical_json";
        "expanded_node_count",Json.String "values_and_object_keys";
        "max_expanded_bytes",Json.int 16646140;"max_expanded_nodes",Json.int 1999999;
        "max_packet_bytes",Json.int 8323072;"max_packet_nodes",Json.int 249968;
        "max_depth",Json.int 128;"max_string_bytes",Json.int 4194304;"max_number_chars",Json.int 4300;
        "claims",Json.String "transport_only";"direction",Json.String "response";
        "partition",Json.String "base_result_and_artifact";
        "max_part_nodes",Json.int 1000000;"max_part_bytes",Json.int 8323072;
        "operations",Json.Array[Json.String "export-policy-quantitative-assurance"]];
      "artifact_transport_authority",Bioc_service.Artifact_io.authority_profile;
      "policy_material",Bioc_service.Policy_material_service.profile;
      "policy_component_material",Bioc_service.Policy_component_material_service.profile;
      "policy_refinement",Bioc_service.Policy_refinement_service.profile;
      "policy_quantitative_assurance",Bioc_service.Policy_quantitative_assurance_service.profile;
      "policy_module_linking",Bioc_service.Policy_module_linking_service.profile;
      "policy_module_material",Bioc_service.Policy_module_linking_service.material_profile;
      "policy_network_material",Bioc_service.Policy_component_material_service.network_profile;
      "policy_network_implementation",Bioc_service.Policy_implementation_service.network_profile;
      "policy_finite_machine_material",Bioc_service.Policy_component_material_service.finite_machine_profile;
      "policy_finite_machine_implementation",Bioc_service.Policy_implementation_service.finite_machine_profile;
      "policy_quantitative_material",Bioc_service.Policy_component_material_service.quantitative_profile;
      "policy_multi_site_implementation",Bioc_service.Policy_implementation_service.multi_site_profile;
      "policy_step_quantitative_material",Bioc_service.Policy_component_material_service.step_quantitative_profile;
      "policy_coupled_implementation",Bioc_service.Policy_implementation_service.coupled_profile;
      "policy_coupled_quantitative_material",Bioc_service.Policy_component_material_service.composition_profile;
      "policy_transfer_network_material",Bioc_service.Policy_component_material_service.transfer_network_profile;
      "policy_transfer_pair_material",Bioc_service.Policy_component_material_service.transfer_pair_profile;
      "policy_component_selection",Bioc_service.Policy_component_selection_service.profile;
      "policy_implementation",Bioc_service.Policy_implementation_service.profile;
      "policy_operational",Bioc_service.Policy_operational_service.profile;
      "policy_frontend",Bioc_service.Policy_service.profile]);
  List.iter(fun operation->
    let export_packet=Json.Object["schema_version",Json.String
      "biocompiler.policy_coupled_export_json_graph.v0.1"]in
    let invocation=Protocol.decode_request(request operation export_packet)in
    match Bioc_service.Service.handle Protocol.Verify invocation with
    |_->failwith "Response-only export wire was accepted as original authority"
    |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_coupled_wire_profile")
      "Response-only export packet was not rejected before input decoding")
    (Bioc_service.Policy_component_material_service.operations @
      Bioc_service.Policy_quantitative_assurance_service.operations @ Bioc_service.Policy_refinement_service.operations);
  let response = Protocol.response ~executable:Protocol.Verify ~request:(Some decoded) ~status ~result diagnostics in
  let identity = Json.field "core" (Json.object_fields response) |> Json.object_fields in
  require (Json.string (Json.field "executable" identity) = "verify") "Verifier identity missing";
  let unsupported = Protocol.decode_request (request "compile" (Json.Object [])) in
  let status, result, diagnostics = Bioc_service.Service.handle Protocol.Core unsupported in
  require (status = Protocol.Unsupported && result = None && diagnostics <> []) "Unsupported compile pretended to succeed";
  List.iter (fun executable ->
      let missing_producer = Protocol.decode_request (request "compile-policy-component-selection" (Json.Object [])) in
      let status, result, diagnostics = Bioc_service.Service.handle executable missing_producer in
      require (status = Protocol.Unsupported && result = None && diagnostics <> [])
        "Selection checking advertised or executed an unavailable producer") [Protocol.Core;Protocol.Verify];
  let malformed = Json.Object ["protocol", Json.String Protocol.version] in
  (match Protocol.decode_request malformed with
   | _ -> failwith "Incomplete request accepted"
   | exception Diagnostic.Error _ -> ());
  (match Protocol.response ~executable:Protocol.Core ~request:None ~status:Protocol.Ok ~result:None [] with
   | _ -> failwith "Malformed success response accepted"
   | exception Diagnostic.Error _ -> ());
  print_endline "protocol: roles, envelopes, errors and unsupported operations checked"
