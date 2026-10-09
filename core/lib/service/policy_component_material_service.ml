open Bioc_wire
module R=Bioc_domain.Policy_component_material_request
module S=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_component_assembly_proposal
module K=Bioc_domain.Construction_content
module P=Bioc_realization_checker.Policy_preservation_check
module Check=Bioc_realization_checker.Policy_component_material_check
module W=Bioc_checker.Work_budget
module Wire=Bioc_domain.Policy_coupled_wire
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let operations=["check-policy-component-material";"replay-policy-component-material";"export-policy-component-material"]
let validation_scope="policy-component-mrna-v0.1"
let implementation="biocompiler.ocaml.policy_component_material.v0.1"
let instance_implementation="biocompiler.ocaml.policy_instance_component_material.v0.1"
let instance_validation_scope="policy-instance-component-mrna-v0.1"
let prerequisite_implementation="biocompiler.ocaml.policy_instance_prerequisite_material.v0.1"
let prerequisite_validation_scope="policy-instance-prerequisite-mrna-v0.1"
let two_observation_implementation="biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1"
let two_observation_validation_scope="policy-instance-two-observation-prerequisite-mrna-v0.1"
let multi_member_implementation="biocompiler.ocaml.policy_multi_member_prerequisite_material.v0.1"
let multi_member_validation_scope="policy-multi-member-prerequisite-mrna-v0.1"
let grounded_helper_implementation="biocompiler.ocaml.policy_grounded_helper_prerequisite_material.v0.1"
let grounded_helper_validation_scope="policy-grounded-helper-prerequisite-mrna-v0.1"
let finite_machine_implementation="biocompiler.ocaml.policy_finite_machine_component_material.v0.1"
let network_validation_scope="policy-network-component-mrna-v0.1"
let network_implementation="biocompiler.ocaml.policy_network_component_material.v0.1"
let finite_machine_validation_scope="policy-finite-machine-component-mrna-v0.1"
let composition_implementation="biocompiler.ocaml.policy_coupled_quantitative_component_material.v0.1"
let composition_validation_scope="policy-coupled-quantitative-component-mrna-v0.1"
let transfer_network_implementation="biocompiler.ocaml.policy_sampled_transfer_network_component_material.v0.1"
let transfer_network_validation_scope="policy-sampled-transfer-network-component-mrna-v0.1"
let transfer_pair_implementation="biocompiler.ocaml.policy_sampled_transfer_pair_component_material.v0.1"
let transfer_pair_validation_scope="policy-sampled-transfer-pair-component-mrna-v0.1"
let step_quantitative_implementation="biocompiler.ocaml.policy_sampled_step_reservoir_component_material.v0.1"
let step_quantitative_validation_scope="policy-sampled-step-reservoir-component-mrna-v0.1"
let quantitative_implementation="biocompiler.ocaml.policy_sampled_reservoir_component_material.v0.1"
let quantitative_validation_scope="policy-sampled-reservoir-component-mrna-v0.1"
let schema_version="biocompiler.core.policy_component_material.v1"
let resource_profile=R.resource_profile
let candidate_schema="biocompiler.policy_component_material_candidate.v0.1"
let max_result_bytes=Limits.max_response_bytes-6*Limits.max_string_bytes-65536
let max_result_nodes=Limits.max_json_nodes-32
let profile=obj["operations",arr(List.map str operations);"request_schema",str R.schema_version;
  "candidate_schema",str candidate_schema;"schema_version",str schema_version;
  "implementation",str implementation;"resource_profile",str resource_profile;
  "validation_scope",str validation_scope;"max_result_bytes",Json.int max_result_bytes;
  "max_result_nodes",Json.int max_result_nodes;
  "artifact",str "on_fresh_export_only";"empirical",str "unassessed"]
let producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str implementation;"validation_scope",str validation_scope]
let instance_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.instance_schema_version
  | "implementation" -> str instance_implementation
  | "validation_scope" -> str instance_validation_scope
  | _ -> value) (Json.object_fields profile))
let instance_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str instance_implementation;"validation_scope",str instance_validation_scope]
let prerequisite_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.prerequisite_schema_version
  | "implementation" -> str prerequisite_implementation
  | "validation_scope" -> str prerequisite_validation_scope
  | _ -> value) (Json.object_fields profile))
let prerequisite_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str prerequisite_implementation;"validation_scope",str prerequisite_validation_scope]
let two_observation_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.two_observation_schema_version
  | "implementation" -> str two_observation_implementation
  | "validation_scope" -> str two_observation_validation_scope
  | _ -> value) (Json.object_fields profile))
let two_observation_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str two_observation_implementation;"validation_scope",str two_observation_validation_scope]
let multi_member_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.multi_member_schema_version
  | "implementation" -> str multi_member_implementation
  | "validation_scope" -> str multi_member_validation_scope
  | _ -> value) (Json.object_fields profile))
let multi_member_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str multi_member_implementation;"validation_scope",str multi_member_validation_scope]
let grounded_helper_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.grounded_helper_schema_version
  | "implementation" -> str grounded_helper_implementation
  | "validation_scope" -> str grounded_helper_validation_scope
  | _ -> value) (Json.object_fields profile))
let grounded_helper_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str grounded_helper_implementation;"validation_scope",str grounded_helper_validation_scope]
let network_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.network_schema_version
  | "implementation" -> str network_implementation
  | "validation_scope" -> str network_validation_scope
  | _ -> value) (Json.object_fields profile))
let network_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str network_implementation;"validation_scope",str network_validation_scope]
let finite_machine_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.finite_machine_schema_version
  | "implementation" -> str finite_machine_implementation
  | "validation_scope" -> str finite_machine_validation_scope
  | _ -> value) (Json.object_fields profile))
let finite_machine_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str finite_machine_implementation;"validation_scope",str finite_machine_validation_scope]
let composition_profile=obj (List.map(fun(key,value)->key,match key with
  |"request_schema"->str R.composition_schema_version
  |"implementation"->str composition_implementation
  |"validation_scope"->str composition_validation_scope|_->value)(Json.object_fields profile))
let composition_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str composition_implementation;"validation_scope",str composition_validation_scope]
let transfer_network_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.transfer_network_schema_version
  | "implementation" -> str transfer_network_implementation
  | "validation_scope" -> str transfer_network_validation_scope
  | _ -> value) (Json.object_fields profile))
let transfer_network_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str transfer_network_implementation;"validation_scope",str transfer_network_validation_scope]
let transfer_pair_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.transfer_pair_schema_version
  | "implementation" -> str transfer_pair_implementation
  | "validation_scope" -> str transfer_pair_validation_scope
  | _ -> value) (Json.object_fields profile))
let transfer_pair_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str transfer_pair_implementation;"validation_scope",str transfer_pair_validation_scope]
let step_quantitative_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.step_quantitative_schema_version
  | "implementation" -> str step_quantitative_implementation
  | "validation_scope" -> str step_quantitative_validation_scope
  | _ -> value) (Json.object_fields profile))
let step_quantitative_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str step_quantitative_implementation;"validation_scope",str step_quantitative_validation_scope]
let quantitative_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.quantitative_schema_version
  | "implementation" -> str quantitative_implementation
  | "validation_scope" -> str quantitative_validation_scope
  | _ -> value) (Json.object_fields profile))
let quantitative_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str quantitative_implementation;"validation_scope",str quantitative_validation_scope]
let validate_publication raw=
  let framed=obj["result",raw]in
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_component_material_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  W.reserve_json output framed;
  let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes framed in
  ignore(Json.parse_artifact ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes encoded)
let is_coupled_request raw=
  let rec field remaining key=function
    |[]->None
    |_ when remaining=0->None
    |(name,value)::rest->if name=key then Some value else field(remaining-1)key rest in
  match raw with
  |Json.Object fields->field 64 "schema_version" fields=Some(str R.composition_schema_version) &&
    field 64 "profile" fields=Some(str R.composition_profile)
  |_->false
let wire_budget ()=W.create ~profile:Wire.schema_version
  ~error_code:"policy_coupled_wire_work_limit" ~maximum:134217728 ()
let unpack_payload ~assurance payload=
  Diagnostic.require(not(Wire.is_export_packet payload))"policy_coupled_wire_profile"
    "The paired assurance export wire format is response-only and cannot supply original authority.";
  if not(Wire.is_packet payload)then payload else
  let work=wire_budget ()in
  let decoded=Wire.decode ~charge:(W.charge work) payload in
  let request=get "request" decoded in
  let material=if assurance then get "material_request" request else request in
  Diagnostic.require(is_coupled_request material)"policy_coupled_wire_profile"
    "The coupled wire format requires a complete original coupled material request.";
  decoded
let publish_result ~coupled result=
  let published=if coupled then
    let work=wire_budget ()in Wire.encode ~charge:(W.charge work) result
    else result in
  validate_publication published;published
let replay_equal ~coupled left right=
  if not coupled then Json.equal left right else
  let work=wire_budget ()in
  let bytes raw=
    let size=Wire.preflight ~charge:(W.charge work) raw in
    W.charge work size;
    let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes raw in
    Diagnostic.require(String.length encoded=size)"policy_coupled_wire_accounting"
      "Coupled replay accounting differs from the complete canonical bytes.";
    encoded in
  let left=bytes left and right=bytes right in
  W.charge work(1+String.length left+String.length right);
  String.equal left right
let export_artifact checked candidate limits=
  let request=Check.request checked and report=Check.evidence checked in
  Diagnostic.require(candidate_schema=Check.candidate_schema &&
    Canonical.fingerprint candidate=Json.string(get "candidate_fingerprint" report) &&
    Json.equal limits(get "limits" report))"policy_component_material_export_identity"
    "Export inputs differ from the freshly checked complete candidate and invocation limits.";
  let rendered=Policy_component_material_format.render checked in
  let members=rendered.members and fasta=rendered.fasta and fasta_sha=rendered.fasta_sha256 in
  let manifest=obj["schema_version",str "biocompiler.policy_component_mrna_manifest.v0.1";
    "profile",str (R.request_profile request);"claim_scope",str "bounded_conditional_policy_via_reusable_components_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "request",R.to_json request;"candidate",candidate;"limits",limits;"assessment",report;
    "bindings",obj["request_fingerprint",str(R.fingerprint request);
      "candidate_fingerprint",get "candidate_fingerprint" report;
      "invocation_fingerprint",get "invocation_fingerprint" report;
      "assessment_fingerprint",str(Canonical.fingerprint report)];
    "members",arr members;"fasta_sha256",str fasta_sha;
    "empirical",str "unassessed";"original_authority",str "retain_original_inputs_separately"]in
  (* Hash the exact canonical bytes published as manifest.json. No self-hash is
     embedded; the enclosing export binds the complete manifest and FASTA pair. *)
  let manifest_bytes=if R.is_quantitative_composition request then (
    (* The full logical manifest remains self-contained and retains its exact
       canonical identity. Only the enclosing coupled operation is packed. *)
    let work=wire_budget ()in
    let size=Wire.preflight ~charge:(W.charge work) manifest in
    W.charge work size;
    let bytes=Canonical.encode_bounded ~max_bytes:max_result_bytes manifest in
    Diagnostic.require(String.length bytes=size)"policy_component_material_export_accounting"
      "Coupled manifest accounting differs from the exact canonical bytes.";
    W.charge work size;bytes)
  else (
    let output=W.create_output ~profile:validation_scope ~error_code:"policy_component_material_service_publication_limit"
      ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
    W.reserve_json output manifest;
    Canonical.encode_bounded ~max_bytes:max_result_bytes manifest)in
  obj["schema_version",str "biocompiler.policy_component_mrna_export.v0.1";
    "fasta",str fasta;"fasta_sha256",str fasta_sha;
    "manifest",manifest;"manifest_sha256",str(Canonical.sha256 manifest_bytes)]
let fresh_check ~request:raw_request ~candidate:raw_candidate ~limits:raw_limits=
  let request=R.of_json raw_request in
  let fields=Json.object_fields ~path:"/payload/candidate" raw_candidate in
  Json.exact_fields ~path:"/payload/candidate"
    ["schema_version";"behavior";"implementation";"binding";"assembly_proposal";"construction"]fields;
  Diagnostic.require(Json.field "schema_version" fields=str candidate_schema)
    "policy_component_material_candidate""Unknown complete material candidate schema.";
  let behavior=O.behavior_of_json(Json.field "behavior" fields)
  and actual=I.of_json ~library:(S.implementation_library(R.implementation_request request))(Json.field "implementation" fields)
  and proposed=U.of_json(Json.field "binding" fields)
  and assembly_proposal=C.of_json(Json.field "assembly_proposal" fields)
  and candidate=K.of_json(Json.field "construction" fields)
  and limits=P.limits_of_json raw_limits in
  let checked=Check.check ~request ~behavior ~implementation:actual ~proposed ~assembly_proposal ~candidate ~limits in
  request,checked
let check ~export ~request:raw_request ~candidate:raw_candidate ~limits:raw_limits=
  let request,checked=fresh_check ~request:raw_request ~candidate:raw_candidate ~limits:raw_limits in
  let report=Check.report checked in
  let artifact=if not export then Json.Null else match Check.accepted checked with
    |Some checked->export_artifact checked raw_candidate raw_limits
    |None->Diagnostic.fail "policy_component_material_export_not_accepted"
      "Fresh original-source, implementation, material, context or obligation checking withheld accepted export."in
  let result=obj["schema_version",str schema_version;
    "implementation",str (if R.is_quantitative_composition request then composition_implementation else if R.is_transfer_network request then transfer_network_implementation else if R.is_transfer_pair request then transfer_pair_implementation else if R.is_multi_site request then step_quantitative_implementation else if R.is_network request then network_implementation
      else if R.is_quantitative request then quantitative_implementation
      else if R.is_finite_machine request then finite_machine_implementation
      else if R.is_grounded_helper request then grounded_helper_implementation
      else if R.is_multi_member request then multi_member_implementation
      else if R.is_two_observation request then two_observation_implementation
      else if R.requires_prerequisite_closure request then prerequisite_implementation
      else if R.is_instanced request then instance_implementation else implementation);
    "resource_profile",str resource_profile;
    "validation_scope",str (if R.is_quantitative_composition request then composition_validation_scope else if R.is_transfer_network request then transfer_network_validation_scope else if R.is_transfer_pair request then transfer_pair_validation_scope else if R.is_multi_site request then step_quantitative_validation_scope else if R.is_network request then network_validation_scope
      else if R.is_quantitative request then quantitative_validation_scope
      else if R.is_finite_machine request then finite_machine_validation_scope
      else if R.is_grounded_helper request then grounded_helper_validation_scope
      else if R.is_multi_member request then multi_member_validation_scope
      else if R.is_two_observation request then two_observation_validation_scope
      else if R.requires_prerequisite_closure request then prerequisite_validation_scope
      else if R.is_instanced request then instance_validation_scope else validation_scope);
    "request_fingerprint",str(R.fingerprint request);"candidate_fingerprint",str(Canonical.fingerprint raw_candidate);
    "invocation_fingerprint",str(Canonical.fingerprint(obj["request",raw_request;"candidate",raw_candidate;"limits",raw_limits]));
    "report_fingerprint",str(Canonical.fingerprint report);"candidate",raw_candidate;"report",report;"artifact",artifact]in
  ignore(publish_result ~coupled:(R.is_quantitative_composition request) result);result
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation""Material service only checks, replays or freshly exports supplied candidates.";
  let payload=unpack_payload ~assurance:false payload in
  let replay=operation="replay-policy-component-material"in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"(["request";"candidate";"limits"]@(if replay then["report"]else[]))fields;
  let coupled=is_coupled_request(Json.field "request" fields)in
  let result=check ~export:(operation="export-policy-component-material") ~request:(Json.field "request" fields)
    ~candidate:(Json.field "candidate" fields) ~limits:(Json.field "limits" fields)in
  if replay then Diagnostic.require(replay_equal ~coupled result(Json.field "report" fields))
    "policy_component_material_replay""Saved full material wrapper differs from complete fresh checking.";
  if coupled then publish_result ~coupled:true result else result
