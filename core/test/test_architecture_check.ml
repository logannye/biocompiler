open Bioc_wire
open Bioc_domain
module K = Bioc_checker.Architecture_check
module W = Bioc_checker.Work_budget
module A = Architecture_request
module B = Architecture_build
module E = Architecture_assessment
module S = Source_execution_manifest
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let field key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (field key raw)
let replace key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rejected label code action = match action () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error error -> require (error.code = code) (label ^ ": expected " ^ code ^ ", got " ^ error.code)
(* Fixed artificial source and human target declarations. The expected verdict
   below is authored independently: no source execution or search is available. *)
let literal_request = {|{"schema_version":"biocompiler.payload_architecture_request.v0.1","id":"literal","circuit":{"schema_version":"biocompiler.circuit_request.v0.1","profile":{"schema_version":"biocompiler.circuit_profile_request.v0.1","purpose":"human_immune_payload","mode":"candidate_design","molecular_form":"RNA","boundary":"planning","target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"recipient":{"schema_version":"biocompiler.immune_recipient_identity.v0.1","lineage":"t_cell","target_fingerprint":"c103975a7f835e5d42196ea2cbb9208f756c2a39b8b43cb15e209c735a63440f","cell_subtype_claim_fingerprint":"28fca1bc6ea489b70d192cd51f746cd9a0c2b1ae8077a2872c80c777614f7a6c","eligibility_basis":"declared","empirical_support":"unestablished"},"source_experiment":null,"source_request":{"schema_version":"biocompiler.build_request.v0.1","intent":{"schema_version":"biocompiler.intent.v0.1","name":"literal_role","nodes":[{"id":"role","kind":"role","inputs":[],"attributes":{"cell_type":"human_T_cell","engineering":"in_vivo","name":"recipient"},"data_type":null,"role":null,"source":null}],"roots":["role"]},"explicit_overrides":{},"resolved_defaults":{},"resolved_bindings":{},"target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"artifact_scope":"abstract_behavior","behavior_profile":"biocompiler.behavior.v0.1","implementation_constraints":{},"preferences":{},"parameter_metadata":{},"provenance":{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}}},"requirements":[{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"required","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"artificial_alpha","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"readout.0","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"software_fixture","accession":"readout.0","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":"role","source_node_ids":["role"],"source_location":null,"input_bindings":[]}],"requested_form":"delivered_rna","fidelity_scope":"complete_nominal","deployment_id":"declared-human-rna-architecture","selected_realization":null,"reference_lock":null},"library":{"schema_version":"biocompiler.payload_architecture_library.v0.1","id":"empty","refinements":[],"assumptions":[]},"constraints":{"schema_version":"biocompiler.rna_architecture_constraints.v0.2","exact_count":null,"max_count":null,"max_member_bases":null,"max_total_bases":null,"delivery_groups":[],"control_requirements":[],"preferred_refinement_ids":[],"max_combinations":256,"require_complete":false,"max_match_states":100000,"max_match_instances":256,"deployment_requirements":[]}}|}
let gap code = obj ["schema_version",str "biocompiler.architecture_gap.v0.1";
    "category",str "independent_verification_failure";"code",str code;"requirement_ids",arr [];
    "candidate_ids",arr [];"message",str ("Independent architecture check rejected " ^ code ^ ".");"conflict_set",arr []]
let expected_report request build errors = obj ["schema_version",str "biocompiler.payload_architecture_verification.v0.1";
    "request_fingerprint",str (A.fingerprint request);"build_fingerprint",str (B.fingerprint build);
    "outcome",str (if errors=[] then "pass" else "fail");"translation_complete",Json.Bool false;
    "construction_complete",Json.Bool false;"diagnostics",arr (List.map gap errors);
    "unresolved",arr [str "source_execution_unavailable";str "search_outcome_not_independently_replayed"];
    "assumptions",arr [];"checker_version",str "biocompiler.payload_architecture_checker.v0.3";
    "claim_scope",str "Exact source and supplied composite execution-contract correspondence, explicit functional requirements under bounded control proof profiles, declared RNA availability intervals, physical composition and complete RNA construction only. No empirical component function or human therapeutic admission is established.";
    "search_verified",Json.Bool false;"empirical_validation",str "unknown";"human_therapeutic_admission",str "not_admitted"]
let literal_inputs () =
  let request=A.of_json (Json.parse literal_request) in
  let source=A.source request in
  let source_json=Human_request.to_json source in
  let node=List.hd (Json.array (field "nodes" (field "intent" source_json))) in
  let semantics=obj (List.remove_assoc "source" (Json.object_fields node)) in
  let ledger=[obj ["id",str "source:role";"kind",str "role";"source_node_ids",arr [str "role"];"semantics",semantics];
    obj ["id",str "source:complete_authority";"kind",str "source_authority";"source_node_ids",arr [str "role"];"semantics",source_json]] in
  let manifest=S.make ~source ~behavior:None ~roles:["role"] ~outputs:[] ~ledger
    ~role_nodes:(obj ["role",arr [str "role"]]) ~states:[] ~channels:[] ~diagnostics:[] in
  let build=B.make ~request_fingerprint:(A.fingerprint request) ~execution:manifest ~plan:None ~construction:None
    ~alternatives:[] ~diagnostics:[] ~status:B.Unsupported ~match_instances:[] in
  request,build
let literals () =
  require (K.implementation_version="biocompiler.ocaml.architecture_check.v0.1" &&
    K.resource_profile="biocompiler.architecture_check.resources.v1" && K.max_work=50_000_000) "Architecture checker profile changed";
  let request,build=literal_inputs () in
  require (A.fingerprint request="5293d9599ffb6835c1130fa69543f4f2b95ca2a4aedb8b6e316be6602476483d" &&
    B.fingerprint build="c4e7b8590f8f9ab02befbd7e2657f853614364c80a73a5c5593f2297421e7fc7") "Independent no-plan authority changed";
  let expected=expected_report request build [] in
  let report=K.check ~expected_request:request build in
  require (Json.equal (E.to_json report) expected) "No-plan PASS lost unresolved obligations or acquired acceptance";
  require (E.fingerprint (K.replay ~expected_request:request ~build report)=E.fingerprint report) "Fresh literal replay differs";
  let stale=B.of_json (replace "request_fingerprint" (str (String.make 64 'f')) (B.to_json build)) in
  require (Json.equal (E.to_json (K.check ~expected_request:request stale)) (expected_report request stale ["request_authority"])) "Stale request identity was not independently rejected";
  rejected "stale receipt replay" "architecture_assessment_mismatch" (fun () -> K.replay ~expected_request:request ~build:stale report);
  let forged=E.of_json (replace "unresolved" (arr []) expected) in
  rejected "forged unresolved inventory" "architecture_assessment_mismatch" (fun () -> K.replay ~expected_request:request ~build forged);
  let original=A.to_json request in
  let circuit=field "circuit" original in let profile=field "profile" circuit in
  let source=field "source_request" profile in let intent=field "intent" source in
  let node=List.hd (Json.array (field "nodes" intent)) in
  let moved=replace "source" (obj ["file",str "moved.py";"line",Json.int 17;"function",str "literal"]) node in
  let source=replace "intent" (replace "nodes" (arr [moved]) intent) source in
  let moved_request=replace "circuit" (replace "profile" (replace "source_request" source profile) circuit) original |> A.of_json in
  require (Build_request.fingerprint (Human_request.build_request (A.source moved_request))=
    Build_request.fingerprint (Human_request.build_request (A.source request)) && A.fingerprint moved_request<>A.fingerprint request)
    "Source-only literal must preserve semantic identity and change full authority";
  require (Json.equal (E.to_json (K.check ~expected_request:moved_request build))
    (expected_report moved_request build ["request_authority";"source_authority";"source_manifest_ledger"]))
    "Source-only authority change was silently omitted from fresh acceptance";
  (* Both unresolved strings and their separators cost exactly 71 units. *)
  ignore (K.check ~budget:(K.make_budget ~maximum:71 ()) ~expected_request:request build);
  rejected "one below exact work boundary" "architecture_resource_limit" (fun () -> K.check ~budget:(K.make_budget ~maximum:70 ()) ~expected_request:request build);
  let cumulative=K.make_budget ~maximum:142 () in
  ignore (K.check ~budget:cumulative ~expected_request:request build);
  ignore (K.check ~budget:cumulative ~expected_request:request build);
  rejected "cumulative reused allowance" "architecture_resource_limit" (fun () -> K.check ~budget:cumulative ~expected_request:request build);
  let parent=W.create ~profile:"literal.parent" ~error_code:"parent_limit" ~maximum:70 () in
  rejected "shared parent allowance" "parent_limit" (fun () -> K.check ~budget:(K.make_budget ~parent ()) ~expected_request:request build);
  rejected "negative allowance" "invalid_work_budget" (fun () -> K.make_budget ~maximum:(-1) ());
  rejected "override fixed maximum" "invalid_work_budget" (fun () -> K.make_budget ~maximum:(K.max_work+1) ());
  print_endline "architecture checker literals: incomplete historical PASS, exact full verdict, fresh replay, stale authority and aggregate work boundaries passed"
let hash value =
  require (String.length value=64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Unsafe document identity";
  value
let bounded_int maximum raw =
  let value=Json.integer raw in
  require (Z.sign value>=0 && Z.compare value (Z.of_int maximum)<=0) "Invalid retained document size";
  Z.to_int value
let read_json maximum path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes=in_channel_length channel in require (bytes<=maximum) "Retained architecture file exceeds read bound";
    Json.parse (really_input_string channel bytes),bytes)
let rec edit_at raw path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove document root")
  | Json.String key::rest ->
      let fields=Json.object_fields raw in
      if rest=[] then obj (match replacement with
        | None -> require (List.mem_assoc key fields) "Absent delta deletion key";List.remove_assoc key fields
        | Some value -> (key,value)::List.remove_assoc key fields)
      else (require (List.mem_assoc key fields) "Absent delta descent key";
        obj (List.map (fun (name,value) -> name,if name=key then edit_at value rest replacement else value) fields))
  | Json.Int index::rest ->
      let values=Json.array raw in
      require (Z.sign index>=0 && Z.compare index (Z.of_int (List.length values))<0) "Invalid delta index";
      require (rest<>[] || replacement<>None) "Delta removal must target an object field";
      let index=Z.to_int index in
      arr (List.mapi (fun i value -> if i<>index then Some value
        else if rest=[] && replacement=None then None else Some (edit_at value rest replacement)) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid delta path"
let apply_edits raw changes =
  List.fold_left (fun raw change ->
    let fields=Json.object_fields change in
    let replacement=match text "op" change with
      | "set" -> Json.exact_fields ["op";"path";"value"] fields;Some (field "value" change)
      | "remove" -> Json.exact_fields ["op";"path"] fields;None
      | _ -> failwith "Unknown delta operation" in
    let path=Json.array (field "path" change) in
    require (path<>[] && List.length path<=Molecular_record.max_depth) "Invalid delta path depth";
    edit_at raw path replacement) raw changes
type document = { kind:string; format:string; base:string option; raw:Json.t; resolved_bytes:int }
let normalized kind raw = match kind with
  | "request" -> A.of_json raw |> A.to_json
  | "build" -> B.of_json raw |> B.to_json
  | "assessment" -> E.of_json raw |> E.to_json
  | _ -> failwith "Unknown architecture document kind"
let order_sites = ["_refinement_checks.owned";"_refinement_checks.binding_roles";
  "_refinement_checks.controlled_actions";"_delivery_dependency_checks.component_placements"]
let substring_position needle value =
  let width=String.length needle in
  let rec find index = if index+width>String.length value then None
    else if String.sub value index width=needle then Some index else find (index+1) in
  find 0
let diagnostic_group site code = match site with
  | "_refinement_checks.owned" -> Option.map (fun index -> String.sub code 0 index) (substring_position "executable_material_model_missing:" code)
  | "_refinement_checks.binding_roles" ->
      if substring_position "material_recipient_missing:" code=None then None
      else Option.map (fun index -> String.sub code 0 index) (String.rindex_opt code ':')
  | "_refinement_checks.controlled_actions" ->
      if substring_position "activity_control_not_realized:" code=None then None else Some code
  | "_delivery_dependency_checks.component_placements" ->
      if String.starts_with ~prefix:"helper_cross_recipient_supply:" code || String.starts_with ~prefix:"helper_co_delivery_missing:" code then
        Option.map (fun index -> String.sub code (index+1) (String.length code-index-1)) (String.index_opt code ':')
      else None
  | _ -> failwith "Unknown diagnostic grouping site"
let diagnostic_sites raw =
  let diagnostics=Json.array (field "diagnostics" raw) in
  List.filter (fun site -> let counts=Hashtbl.create 8 in
    List.iter (fun diagnostic -> Option.iter (fun key -> Hashtbl.replace counts key
      (1+Option.value ~default:0 (Hashtbl.find_opt counts key))) (diagnostic_group site (text "code" diagnostic))) diagnostics;
    Hashtbl.fold (fun _ count found -> found || count>1) counts false) order_sites
let ordered_diagnostics sites raw =
  let diagnostics=Array.of_list (Json.array (field "diagnostics" raw)) in
  List.iter (fun site ->
    let groups=Hashtbl.create 8 in
    Array.iteri (fun index diagnostic -> Option.iter (fun key -> Hashtbl.replace groups key
      (index::Option.value ~default:[] (Hashtbl.find_opt groups key))) (diagnostic_group site (text "code" diagnostic))) diagnostics;
    Hashtbl.iter (fun _ reversed ->
      let positions=List.rev reversed in
      let values=List.map (Array.get diagnostics) positions |> List.sort (fun a b -> String.compare (Canonical.encode a) (Canonical.encode b)) in
      List.iter2 (fun position value -> diagnostics.(position)<-value) positions values) groups) sites;
  replace "diagnostics" (arr (Array.to_list diagnostics)) raw
let expected_native case expected =
  let mappings=Json.array (field "native_diagnostic_replacements" case) in
  let original=Json.array (field "diagnostics" expected) in
  let names=List.map (fun mapping ->
    Json.exact_fields ["python";"native"] (Json.object_fields mapping);
    let python=text "python" mapping and native=text "native" mapping in
    require (python<>native && List.exists (fun diagnostic -> text "code" diagnostic=python) original) "No-op or absent diagnostic replacement";
    python,native) mappings in
  require (List.length names=List.length (List.sort_uniq String.compare (List.map fst names))) "Duplicate diagnostic replacement";
  let diagnostics=List.map (fun diagnostic ->
    let code=text "code" diagnostic in
    match List.assoc_opt code names with
    | None -> diagnostic
    | Some native ->
        require (text "message" diagnostic="Independent architecture check rejected " ^ code ^ ".") "Unexpected legacy diagnostic message";
        replace "message" (str ("Independent architecture check rejected " ^ native ^ ".")) (replace "code" (str native) diagnostic)) original in
  replace "diagnostics" (arr diagnostics) expected
let comparable case raw =
  let sites=Json.array (field "diagnostic_order_sites" case) |> List.map Json.string in
  require (List.for_all (fun site -> List.mem site order_sites) sites &&
    List.length sites=List.length (List.sort_uniq String.compare sites)) "Unapproved diagnostic order allowance";
  require (sites=diagnostic_sites raw) "Diagnostic order exception lacks the exact affected loop group";
  ordered_diagnostics sites raw
let report_codes report = List.map B.Gap.code (E.diagnostics report)
let exact_native_order_case =
  "test_payload_architecture_verification.PayloadArchitectureVerificationTests.test_component_model_pin_cannot_name_unrelated_graph/0"
let require_exact_native_order id report =
  if id=exact_native_order_case then
    require (report_codes report=[
      "a.one_rna:component_model_authority:a.one_rna.role0.composite";
      "a.one_rna:executable_material_model_missing:n000012";
      "a.one_rna:executable_material_model_missing:n000013";
      "a.one_rna:executable_material_model_missing:n000017";
      "a.one_rna:executable_material_model_missing:n000018";
      "a.one_rna:control_material_correspondence:role0.activation";
      "a.one_rna:control_material_correspondence:role0.shutdown-0";
      "a.one_rna:control_material_correspondence:role0.shutdown-1";
      "compiled_status_without_complete_translation"])
      "Native missing-material diagnostic order differs before compatibility normalization"
let storage_literals () =
  let codes=["refinement:r:executable_material_model_missing:z";"fixed:first";
    "refinement:s:executable_material_model_missing:z";"refinement:r:executable_material_model_missing:a";
    "fixed:second";"refinement:s:executable_material_model_missing:a"] in
  let report=obj ["outcome",str "fail";"unresolved",arr [str "z";str "a"];
    "diagnostics",arr (List.map (fun code -> obj ["code",str code;"message",str code]) codes)] in
  let ordered=ordered_diagnostics ["_refinement_checks.owned"] report in
  let expected=List.map (List.nth codes) [3;1;5;0;4;2] in
  require (List.map (text "code") (Json.array (field "diagnostics" ordered))=expected &&
    field "unresolved" ordered=field "unresolved" report && field "outcome" ordered=field "outcome" report)
    "Selective order normalization crossed independent loop groups or altered other fields";
  require (diagnostic_sites report=["_refinement_checks.owned"]) "Exact unordered loop-site census differs";
  let fixed=obj ["diagnostics",arr (List.map (fun code -> obj ["code",str code]) [List.nth codes 0;List.nth codes 2])] in
  require (diagnostic_sites fixed=[]) "Singleton loop groups acquired an order exception";
  let base=Json.parse {|{"values":[1,2],"old":true}|} in
  let delta=Json.parse {|[{"op":"set","path":["values",1],"value":3},{"op":"remove","path":["old"]}]|} |> Json.array in
  require (Json.equal (apply_edits base delta) (Json.parse {|{"values":[1,3]}|}) &&
    Json.equal base (Json.parse {|{"values":[1,2],"old":true}|})) "Fixture delta changed its baseline or failed exact reconstruction";
  let rejects raw = match apply_edits base (Json.array (Json.parse raw)) with
    | _ -> failwith "Malformed storage delta unexpectedly accepted"
    | exception Failure _ -> () in
  List.iter rejects [
    {|[{"op":"set","path":[],"value":0}]|};
    {|[{"op":"set","path":["absent","nested"],"value":0}]|};
    {|[{"op":"remove","path":["absent"]}]|};
    {|[{"op":"remove","path":["values",0]}]|}];
  print_endline "architecture corpus literals: strict independent deltas and selective diagnostic ordering passed"
let case_b_mutation request build report =
  let raw=B.to_json build in
  let plan=field "plan" raw in
  let placements=Json.array (field "placements" plan) in
  require (placements<>[] && B.status build=B.Compiled && E.passed report && E.translation_complete report) "Retained case B lacks complete placement authority";
  (* Deliberately independent from delta resolution and its path editor. *)
  let changed=match placements with
    | first::rest -> replace "member_id" (str "independent-forged-member") first::rest
    | [] -> assert false in
  let mutant=replace "plan" (replace "placements" (arr changed) plan) raw |> B.of_json in
  require (B.fingerprint mutant<>B.fingerprint build) "Placement mutation is a no-op";
  let failed=K.check ~expected_request:request mutant in
  require (report_codes failed=["plan_placements";"compiled_status_without_complete_translation"] &&
    E.outcome failed=E.Fail && not (E.translation_complete failed) && not (E.construction_complete failed) && E.unresolved failed=[])
    "Rehashed retained plan placement escaped full independent inventory comparison";
  require (E.request_fingerprint failed=A.fingerprint request && E.build_fingerprint failed=B.fingerprint mutant) "Mutation verdict lost full authority identity";
  rejected "complete receipt on changed placement" "architecture_assessment_mismatch" (fun () -> K.replay ~expected_request:request ~build:mutant report)
let retained path =
  require (not (Filename.is_relative path)) "Architecture checking corpus requires an absolute path";
  let index,index_bytes=read_json Limits.max_request_bytes path in
  require (field "schema_version" index=str "biocompiler.architecture_check_conformance.v1") "Wrong architecture checking corpus schema";
  require (field "delta_schema" index=str "biocompiler.test_document_delta.v1") "Wrong architecture delta schema";
  let expected_limits=obj ["stored_bytes",Json.int Limits.max_request_bytes;"resolved_bytes",Json.int (512*1024*1024);
    "cases",Json.int 2048;"document_bytes",Json.int Molecular_record.max_json_bytes;
    "document_nodes",Json.int Molecular_record.max_items;"document_depth",Json.int Molecular_record.max_depth] in
  require (Json.equal (field "resource_limits" index) expected_limits) "Architecture corpus resource profile differs";
  let inventory=obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)) in
  let expected_inventory="bb1e0c3de0eaa45e11513b73379d35e6fd6180cac1d19fa9cec41e13ce96d213" in
  require (Canonical.fingerprint inventory=expected_inventory && field "inventory_fingerprint" index=str expected_inventory) "Architecture full case/document/exception inventory changed";
  let descriptors=Json.array (field "documents" index) and cases=Json.array (field "cases" index) in
  require (List.length cases<=2048) "Architecture case budget exceeded";
  require (List.length cases=293 && List.length descriptors=463 && index_bytes=344075)
    "Frozen architecture case/document/index-byte census differs";
  require (List.length (List.filter (fun descriptor -> text "format" descriptor="full") descriptors)=54 &&
    List.length (List.filter (fun descriptor -> text "format" descriptor="delta") descriptors)=409)
    "Frozen full/delta document census differs";
  let directory=Filename.remove_extension path in
  let documents=Hashtbl.create (List.length descriptors) and used_bytes=ref index_bytes and resolved_total=ref 0 in
  List.iter (fun descriptor ->
    Json.exact_fields ["id";"kind";"format";"stored_fingerprint";"bytes";"resolved_bytes";"base"] (Json.object_fields descriptor);
    let id=hash (text "id" descriptor) and kind=text "kind" descriptor and format=text "format" descriptor in
    require (not (Hashtbl.mem documents id)) "Duplicate architecture document identity";
    require (List.mem kind ["request";"build";"assessment"] && List.mem format ["full";"delta"]) "Unknown architecture document kind or format";
    let declared_bytes=bounded_int Molecular_record.max_json_bytes (field "bytes" descriptor) in
    require (declared_bytes<=Limits.max_request_bytes - !used_bytes) "Aggregate encoded architecture corpus exceeds protocol bound";
    used_bytes:= !used_bytes+declared_bytes;
    let raw,actual_bytes=read_json Molecular_record.max_json_bytes (Filename.concat directory (id ^ ".json")) in
    Molecular_record.check_resources raw;
    require (actual_bytes=declared_bytes && Canonical.fingerprint raw=hash (text "stored_fingerprint" descriptor)) "Stored architecture file bytes or identity differ";
    let base=match field "base" descriptor with Json.Null -> None | value -> Some (hash (Json.string value)) in
    require ((format="full")=(base=None)) "Inconsistent delta base descriptor";
    if format="delta" then (
      Json.exact_fields ["schema_version";"base";"edits"] (Json.object_fields raw);
      require (field "schema_version" raw=str "biocompiler.test_document_delta.v1" && field "base" raw=field "base" descriptor) "Delta wrapper authority differs");
    let resolved_bytes=bounded_int Molecular_record.max_json_bytes (field "resolved_bytes" descriptor) in
    require (resolved_bytes<=512*1024*1024 - !resolved_total) "Aggregate resolved architecture corpus exceeds campaign bound";
    resolved_total:= !resolved_total+resolved_bytes;
    Hashtbl.add documents id {kind;format;base;raw;resolved_bytes}) descriptors;
  let declared_files=List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare in
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare)=declared_files) "Missing or unexpected architecture document files";
  let lookup id = match Hashtbl.find_opt documents id with Some value -> value | None -> failwith ("Missing architecture document: " ^ id) in
  let resolved id =
    let descriptor=lookup id in
    let raw=match descriptor.base with
      | None -> descriptor.raw
      | Some base ->
          let parent=lookup base in
          require (parent.format="full" && parent.base=None && parent.kind=descriptor.kind && base<>id) "Delta chain or cross-kind base rejected";
          let changes=Json.array (field "edits" descriptor.raw) in
          require (changes<>[]) "Empty architecture delta";
          let raw=apply_edits parent.raw changes in
          require (not (Json.equal raw parent.raw)) "No-op architecture delta";raw in
    Molecular_record.check_resources raw;
    require (Molecular_record.pretty_size raw+1=descriptor.resolved_bytes && Canonical.fingerprint raw=id) "Complete resolved architecture bytes or identity differ";
    raw in
  (* Validate every complete record, including documents used only as delta bases.
     Resolve per use, so delta compression cannot create an unbounded cache. *)
  Hashtbl.iter (fun id descriptor -> let raw=resolved id in
    require (Json.equal (normalized descriptor.kind raw) raw) (id ^ ": retained architecture record is not normalized")) documents;
  let reachable=Hashtbl.create (List.length descriptors) and identities=Hashtbl.create (List.length cases) in
  let use case key kind =
    let id=hash (text key case) in let descriptor=lookup id in
    require (descriptor.kind=kind) "Architecture case refers to wrong document kind";
    Hashtbl.replace reachable id ();
    Option.iter (fun base -> Hashtbl.replace reachable base ()) descriptor.base;
    resolved id in
  let case_b_count=ref 0 and order_count=ref 0 and replacement_count=ref 0 and outcomes=Hashtbl.create 4 in
  List.iter (fun case ->
    let id=text "id" case in
    require (not (Hashtbl.mem identities id)) "Duplicate architecture checker case";Hashtbl.add identities id case;
    let request_raw=use case "request" "request" and build_raw=use case "build" "build" and expected=use case "assessment" "assessment" in
    let request=A.of_json request_raw and build=B.of_json build_raw in
    let before=A.fingerprint request,B.fingerprint build in
    let report=K.check ~expected_request:request build in
    require_exact_native_order id report;
    let expected=expected_native case expected |> comparable case and actual=E.to_json report |> comparable case in
    require (Json.equal expected actual) (id ^ ": complete fresh assessment differs; actual=" ^ Canonical.fingerprint actual ^
      ", expected=" ^ Canonical.fingerprint expected ^ ", diagnostics=" ^ Canonical.encode (field "diagnostics" actual));
    require (E.request_fingerprint report=fst before && E.build_fingerprint report=snd before) (id ^ ": report authority identity differs");
    require ((A.fingerprint request,B.fingerprint build)=before) (id ^ ": checking mutated retained input authority");
    let fresh=K.replay ~expected_request:request ~build report in
    require (Json.equal (E.to_json fresh) (E.to_json report)) (id ^ ": fresh full replay differs");
    let outcome=Construction_assessment.outcome_name (E.outcome report) in
    Hashtbl.replace outcomes outcome (1+Option.value ~default:0 (Hashtbl.find_opt outcomes outcome));
    if Json.array (field "diagnostic_order_sites" case)<>[] then incr order_count;
    replacement_count:= !replacement_count+List.length (Json.array (field "native_diagnostic_replacements" case));
    if List.mem id ["case_b/base";"case_b/parameter-default";"case_b/parameter-override"] then (
      incr case_b_count;
      require ((lookup (text "request" case)).format="full" && (lookup (text "build" case)).format="full") "Original case-B authority was replaced by a delta";
      case_b_mutation request build report)) cases;
  let replay_rejections=Json.array (field "replay_rejections" index) in
  require (List.length replay_rejections=2) "Missing historical architecture replay mutations";
  List.iter (fun case ->
    let original=match Hashtbl.find_opt identities (text "source" case) with Some value -> value | None -> failwith "Replay has no original complete case" in
    let request=A.of_json (use original "request" "request") and build=B.of_json (use original "build" "build") in
    let saved=use case "assessment" "assessment" |> E.of_json in
    require (text "assessment" case<>text "assessment" original && text "expected_code" case="architecture_assessment_mismatch") "No-op or unintended replay rejection";
    rejected (text "id" case) "architecture_assessment_mismatch" (fun () -> K.replay ~expected_request:request ~build saved)) replay_rejections;
  require (Hashtbl.length reachable=Hashtbl.length documents) "Unreachable extra architecture document";
  require (!case_b_count=3) "Original three case-B cases missing";
  require (!order_count=1 && !replacement_count=2 && !used_bytes=13996600 && !resolved_total=63103498)
    "Frozen compatibility exception or aggregate byte census differs";
  let coverage=field "coverage" index in
  require (field "cases" coverage=Json.int (List.length cases) && field "documents" coverage=Json.int (List.length descriptors) &&
    field "replay_rejections" coverage=Json.int 2 && field "stored_document_bytes" coverage=Json.int (!used_bytes-index_bytes) &&
    field "resolved_document_bytes" coverage=Json.int !resolved_total) "Stale architecture coverage census";
  let counts=obj (Hashtbl.fold (fun key value values -> (key,Json.int value)::values) outcomes []) in
  require (Json.equal counts (obj ["pass",Json.int 217;"fail",Json.int 76]) &&
    Json.equal counts (field "outcomes" coverage)) "Architecture outcome census differs";
  require (field "diagnostic_order_cases" coverage=arr [str exact_native_order_case] &&
    field "captured_calls" coverage=Json.int 277) "Frozen source-call or exact order-exception inventory differs";
  let installed=Json.array (field "installed" coverage) |> List.map Json.string in
  require (List.length installed=13 && List.length (List.sort_uniq String.compare installed)=13) "Incomplete installed architecture inventory";
  List.iter (fun id -> require (Hashtbl.mem identities id) "Missing installed architecture case") installed;
  let methods=Json.array (field "methods" coverage) in
  require (List.length methods=84 && List.for_all (fun method_ -> text "status" method_="source_assertions_executed") methods &&
    List.length (List.filter (fun method_ -> String.ends_with ~suffix:".setUpClass" (text "method" method_)) methods)=6 &&
    List.fold_left (fun total method_ -> total+bounded_int 277 (field "retained_calls" method_)) 0 methods=246 &&
    field "exclusions" coverage=arr []) "Incomplete source assertion campaign";
  List.iter (fun method_ ->
    let prefix=text "method" method_ ^ "/" in
    require (field "retained_calls" method_=Json.int (List.length (List.filter (fun case ->
      String.starts_with ~prefix (text "id" case)) cases))) "Stale per-method retained-call census") methods;
  require (List.length (List.filter (fun case -> text "origin" case="existing_python_assertion") cases)=277 &&
    List.length (List.filter (fun case -> text "origin" case="existing_python_assertion" &&
      String.starts_with ~prefix:"installed/" (text "id" case)) cases)=31)
    "Captured source assertions or installed-search check census differs";
  Printf.printf "architecture checker: %d full reports, %d documents, %d explicit order exceptions, %d native diagnostic replacements and three independent placement/replay mutations passed\n"
    (List.length cases) (Hashtbl.length documents) !order_count !replacement_count
let () = match Array.to_list Sys.argv with
  | [_] -> literals ();storage_literals ()
  | [_;path] -> literals ();storage_literals ();retained path
  | _ -> failwith "usage: test_architecture_check.exe [<absolute-architecture-check-corpus.json>]"
