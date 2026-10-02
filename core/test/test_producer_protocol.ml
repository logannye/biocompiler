open Bioc_wire
open Bioc_domain
module Service = Bioc_producer_service.Producer_service
module Base = Bioc_service.Service
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (field key raw)
let replace key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let request operation payload = Protocol.decode_request (obj ["protocol",str Protocol.version;
  "request_id",str "producer:test";"operation",str operation;"payload",payload])
let call executable operation payload = Service.handle executable (request operation payload)
let success operation payload = match call Protocol.Core operation payload with
  | Protocol.Ok,Some result,[] -> result
  | _ -> failwith ("Operation did not complete: " ^ operation)
let rejected code action = match action () with
  | _ -> failwith ("Expected rejection " ^ code)
  | exception Diagnostic.Error error -> require (error.code=code) ("Expected " ^ code ^ ", got " ^ error.code)
let assert_fields names raw = Json.exact_fields names (Json.object_fields raw)
let assert_identity schema result =
  require (text "schema_version" result=schema &&
    text "implementation" result="biocompiler.ocaml.architecture_producer.v0.1" &&
    text "resource_profile" result="biocompiler.architecture_producer.resources.v1" &&
    text "validation_scope" result="supplied-architecture-production-v1") "Producer result profile changed"
let assert_canonical key digest result =
  let value=text key result in
  require (Canonical.sha256 value=text digest result && Canonical.encode (Json.parse value)=value) "Canonical bytes or digest changed";
  Json.parse value
let compile_result raw_request =
  let result=success "compile-architecture" (obj ["request",raw_request]) in
  assert_fields ["schema_version";"implementation";"resource_profile";"validation_scope";"supplied_request_fingerprint";
    "request_fingerprint";"build_fingerprint";"build_json";"verification"] result;
  assert_identity "biocompiler.core.architecture_build.v1" result;
  require (text "supplied_request_fingerprint" result=Canonical.fingerprint raw_request &&
    text "request_fingerprint" result=Architecture_request.fingerprint (Architecture_request.of_json raw_request)) "Producer lost exact or normalized request identity";
  let build=assert_canonical "build_json" "build_fingerprint" result in
  let verification=field "verification" result in
  require (text "supplied_request_fingerprint" verification=Canonical.fingerprint raw_request &&
    text "supplied_build_fingerprint" verification=Canonical.fingerprint build) "Fresh assessment belongs to different supplied authority";
  let checked=match Base.handle Protocol.Verify (request "verify-architecture" (obj ["expected_request",raw_request;"build",build])) with
    | Protocol.Ok,Some checked,[] -> checked | _ -> failwith "Standalone verifier failed" in
  require (Json.equal checked verification) "Compile returned a different assessment from standalone fresh verification";
  result,build
let literal_request = {|{"schema_version":"biocompiler.payload_architecture_request.v0.1","id":"literal","circuit":{"schema_version":"biocompiler.circuit_request.v0.1","profile":{"schema_version":"biocompiler.circuit_profile_request.v0.1","purpose":"human_immune_payload","mode":"candidate_design","molecular_form":"RNA","boundary":"planning","target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"recipient":{"schema_version":"biocompiler.immune_recipient_identity.v0.1","lineage":"t_cell","target_fingerprint":"c103975a7f835e5d42196ea2cbb9208f756c2a39b8b43cb15e209c735a63440f","cell_subtype_claim_fingerprint":"28fca1bc6ea489b70d192cd51f746cd9a0c2b1ae8077a2872c80c777614f7a6c","eligibility_basis":"declared","empirical_support":"unestablished"},"source_experiment":null,"source_request":{"schema_version":"biocompiler.build_request.v0.1","intent":{"schema_version":"biocompiler.intent.v0.1","name":"literal_role","nodes":[{"id":"role","kind":"role","inputs":[],"attributes":{"cell_type":"human_T_cell","engineering":"in_vivo","name":"recipient"},"data_type":null,"role":null,"source":null}],"roots":["role"]},"explicit_overrides":{},"resolved_defaults":{},"resolved_bindings":{},"target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"artifact_scope":"abstract_behavior","behavior_profile":"biocompiler.behavior.v0.1","implementation_constraints":{},"preferences":{},"parameter_metadata":{},"provenance":{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}}},"requirements":[{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"required","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"artificial_alpha","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"readout.0","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"software_fixture","accession":"readout.0","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":"role","source_node_ids":["role"],"source_location":null,"input_bindings":[]}],"requested_form":"delivered_rna","fidelity_scope":"complete_nominal","deployment_id":"declared-human-rna-architecture","selected_realization":null,"reference_lock":null},"library":{"schema_version":"biocompiler.payload_architecture_library.v0.1","id":"empty","refinements":[],"assumptions":[]},"constraints":{"schema_version":"biocompiler.rna_architecture_constraints.v0.2","exact_count":null,"max_count":null,"max_member_bases":null,"max_total_bases":null,"delivery_groups":[],"control_requirements":[],"preferred_refinement_ids":[],"max_combinations":256,"require_complete":false,"max_match_states":100000,"max_match_instances":256,"deployment_requirements":[]}}|}
let literals () =
  let base=match Base.handle Protocol.Verify (request "capabilities" (obj [])) with
    | Protocol.Ok,Some value,[] -> value | _ -> failwith "Base capabilities failed" in
  let verifier=match call Protocol.Verify "capabilities" (obj []) with
    | Protocol.Ok,Some value,[] -> value | _ -> failwith "Delegated verifier capabilities failed" in
  require (Json.equal base verifier) "Verifier acquired producer capabilities";
  List.iter (fun operation -> match call Protocol.Verify operation (obj []) with
    | Protocol.Unsupported,None,[diagnostic] -> require (diagnostic.code="unsupported_operation") "Verifier returned wrong unsupported code"
    | _ -> failwith "Standalone verifier attempted a producer operation") ["compile-architecture";"export-architecture"];
  let capabilities=success "capabilities" (obj []) in
  require (Json.array (field "operations" capabilities)=Json.array (field "operations" base) @ [str "compile-architecture";str "export-architecture"])
    "Core operation census changed";
  require (Json.array (field "validation_scopes" capabilities)=Json.array (field "validation_scopes" base) @ [str Service.validation_scope])
    "Producer scope was not appended to the existing checking scopes";
  let profiles=field "profiles" capabilities in
  require (Json.equal (field "architecture" profiles) (field "architecture" (field "profiles" base)) &&
    Json.equal (field "architecture_producer" profiles) Service.profile) "Producer capability changed existing checker profile";
  assert_fields ["operations";"request_schema";"build_schema";"export_schema";"assessment_schema";"implementation";
    "resource_profile";"checker_implementation";"checker_resource_profile";"validation_scope"] Service.profile;
  List.iter (fun operation -> rejected "missing_field" (fun () -> call Protocol.Core operation (obj []))) ["compile-architecture";"export-architecture"];
  rejected "unknown_field" (fun () -> success "compile-architecture" (obj ["request",Json.parse literal_request;"assessment",obj []]));
  let original=Json.parse literal_request in
  let result,build=compile_result original in
  require (text "status" build="no_solution" && field "plan" build=Json.Null && field "construction" build=Json.Null)
    "Empty library produced material or protocol failure instead of a complete no-solution build";
  let assessment=field "assessment" (field "verification" result) in
  require (text "outcome" assessment="pass" && field "translation_complete" assessment=Json.Bool false &&
    field "construction_complete" assessment=Json.Bool false && field "search_verified" assessment=Json.Bool false &&
    text "empirical_validation" assessment="unknown" && text "human_therapeutic_admission" assessment="not_admitted")
    "Incomplete scoped verification became compilation, exhaustive search or empirical acceptance";
  rejected "architecture_export_rejected" (fun () -> success "export-architecture" (obj ["expected_request",original;"build",build]));
  rejected "missing_field" (fun () -> success "export-architecture" (obj ["build",build]));
  let unnormalized=replace "library" (replace "assumptions" (arr [str "z";str "a"]) (field "library" original)) original in
  let normalized,_=compile_result unnormalized in
  require (text "supplied_request_fingerprint" normalized<>text "request_fingerprint" normalized)
    "Exact raw authority and normalized domain identity were conflated";
  let circuit=field "circuit" original in let profile=field "profile" circuit in
  let source=field "source_request" profile in let intent=field "intent" source in
  let unknown=obj ["id",str "future";"kind",str "future.operation";"inputs",arr [];"attributes",obj [];
    "data_type",Json.Null;"role",Json.Null;"source",Json.Null] in
  let changed_source=replace "intent" (replace "nodes" (arr (Json.array (field "nodes" intent) @ [unknown])) intent) source in
  let unsupported=replace "circuit" (replace "profile" (replace "source_request" changed_source profile) circuit) original in
  let _,unsupported_build=compile_result unsupported in
  require (text "status" unsupported_build="unsupported" && field "plan" unsupported_build=Json.Null)
    "An unsupported source produced an optimistic candidate";
  print_endline "producer protocol literals: core-only capabilities, exact fields/bytes, raw authority pins, no-solution/unsupported scopes and export rejection passed"
let read path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes=in_channel_length channel in require (bytes<=4_000_000) "Case-B authority exceeds domain byte bound";
    Json.parse (really_input_string channel bytes))
let case_b directory =
  require (not (Filename.is_relative directory)) "Case-B directory must be absolute";
  List.iter (fun variant ->
      let root=Filename.concat directory variant in
      let original=read (Filename.concat root "request.json") and expected=read (Filename.concat root "candidate.json") in
      let compiled,build=compile_result original in
      require (Json.equal build expected) ("Complete original case-B producer changed: " ^ variant);
      let result=success "export-architecture" (obj ["expected_request",original;"build",build]) in
      assert_fields ["schema_version";"implementation";"resource_profile";"validation_scope";"supplied_request_fingerprint";
        "supplied_build_fingerprint";"request_fingerprint";"build_fingerprint";"export_fingerprint";"fasta";
        "fasta_sha256";"manifest_json";"manifest_sha256";"verification"] result;
      assert_identity "biocompiler.core.architecture_export.v1" result;
      require (text "supplied_request_fingerprint" result=Canonical.fingerprint original &&
        text "supplied_build_fingerprint" result=Canonical.fingerprint build &&
        text "request_fingerprint" result=text "request_fingerprint" compiled &&
        text "build_fingerprint" result=text "build_fingerprint" compiled) "Export lost full original request/build authority";
      let manifest=assert_canonical "manifest_json" "manifest_sha256" result in
      let fasta=text "fasta" result in
      require (String.starts_with ~prefix:">" fasta && String.ends_with ~suffix:"\n" fasta &&
        Canonical.sha256 fasta=text "fasta_sha256" result) "Exact FASTA bytes or final newline changed";
      require (Json.equal (field "build" manifest) build &&
        Json.equal (field "verification" manifest) (field "assessment" (field "verification" result)) &&
        Json.equal (field "verification" result) (field "verification" compiled)) "Manifest/receipt pair does not bind the emitted build";
      let exported=obj ["schema_version",str Architecture_build.Export.schema_version;"fasta",str fasta;"manifest",manifest] in
      require (Canonical.fingerprint exported=text "export_fingerprint" result) "FASTA/manifest composite identity differs";
      let replay=match Base.handle Protocol.Verify (request "replay-architecture" (obj ["expected_request",original;"build",build;
          "assessment",field "verification" manifest])) with
        | Protocol.Ok,Some value,[] -> value | _ -> failwith "Export receipt standalone replay failed" in
      require (Json.equal replay (field "verification" result)) "Export receipt failed exact standalone replay";
      let plan=field "plan" build in
      let placements=Json.array (field "placements" plan) in
      let changed=match placements with first::rest -> replace "plan" (replace "placements" (arr (replace "member_id" (str "forged-member") first :: rest)) plan) build
        | [] -> failwith "Original case-B placement inventory is empty" in
      rejected "architecture_export_rejected" (fun () -> success "export-architecture" (obj ["expected_request",original;"build",changed]));
      let stale=replace "id" (str (text "id" original ^ ".stale")) original in
      rejected "architecture_export_rejected" (fun () -> success "export-architecture" (obj ["expected_request",stale;"build",build]));
      rejected "unknown_field" (fun () -> success "export-architecture" (obj ["expected_request",original;"build",build;"assessment",field "verification" manifest])))
    ["base";"parameter-default";"parameter-override"];
  print_endline "producer protocol: all three complete original case-B compiles, paired exports, standalone replay and stale/forged authority rejections passed"
let () =
  literals ();
  match Array.to_list Sys.argv with
  | [_] -> ()
  | [_;directory] -> case_b directory
  | _ -> failwith "Usage: test_producer_protocol.exe [absolute-case-b-directory]"
