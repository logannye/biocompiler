open Bioc_wire
open Bioc_domain
module P = Bioc_compiler.Architecture_producer
module M = Bioc_compiler.Architecture_matching
module S = Bioc_compiler.Source_execution
module A = Architecture_request
module B = Architecture_build
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (field key raw)
let replace key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rejected code action = match action () with
  | _ -> failwith ("Expected rejection " ^ code)
  | exception Diagnostic.Error error -> require (error.code=code) ("Expected " ^ code ^ ", got " ^ error.code)
let namespace_literals request =
  let refinement = List.hd (Architecture_refinement.Library.refinements (A.library request)) in
  let original = Payload_template.to_json (List.hd (Architecture_refinement.templates refinement)) in
  let first key raw = List.hd (Json.array (field key raw)) in
  let root = first "sources" original and member = first "output_members" original
  and requirement = first "requirements" original in
  let molecule = field "molecule" root in
  let rename identity replacement raw =
    let rec visit = function
      | Json.Object fields as raw ->
          if List.assoc_opt "schema_version" fields=Some (str Molecular_record.Provenance.schema_version) then raw
          else obj (List.map (fun (key,value) -> key,
              if List.mem key ["id";"member_id";"space_id";"source_id";"port_id";"subject_id";"preparation_id"] && value=str identity
              then str replacement
              else if key="role_instance_ids" then arr (List.map (fun value -> if value=str identity then str replacement else value) (Json.array value))
              else visit value) fields)
      | Json.Array values -> arr (List.map visit values)
      | value -> value in
    visit raw in
  let cases = [text "id" original,4096,"Payload template identity";
    text "id" root,4096,"Construction root identity";
    text "id" molecule,4096,"Molecule record identity";
    text "id" (field "space" molecule),4096,"Coordinate space identity";
    text "id" member,4080,"Output member identity";
    text "space_id" member,4096,"Final output coordinate-space identity";
    text "id" requirement,4096,"Required construction member identity";
    text "id" (first "roles" requirement),4096,"id"] in
  let namespace raw = Bioc_compiler.Architecture_material.namespace_template (Payload_template.of_json raw) "a000_t000_" in
  let rejected_message message raw = match namespace raw with
    | _ -> failwith ("Expected exact namespace rejection: " ^ message)
    | exception Diagnostic.Error error -> require (error.code="architecture_synthesized_identity" && error.message=message)
        ("Namespace error differs: " ^ error.code ^ ": " ^ error.message) in
  List.iter (fun (identity,maximum,label) ->
      ignore (namespace (rename identity (String.make (maximum-10) 'x') original));
      rejected_message ("Invalid or excessive " ^ label ^ " text.") (rename identity (String.make (maximum-9) 'x') original);
      let utf8 count = String.concat "" (List.init count (fun _ -> "é")) in
      ignore (namespace (rename identity (utf8 ((maximum-10)/2)) original));
      rejected_message (label ^ " exceeds its byte limit.") (rename identity (utf8 ((maximum-10)/2+1)) original)) cases;
  let two_overflows = original |> rename (text "id" original) (String.make 4087 't')
    |> rename (text "id" (field "space" molecule)) (String.make 4087 's') in
  rejected_message "Invalid or excessive Coordinate space identity text." two_overflows
let candidate_literals request candidate =
  let module W = Bioc_checker.Work_budget in
  require (List.length (Architecture_refinement.Library.refinements (A.library request))=1 && B.status candidate=B.Compiled)
    "Candidate literal needs the retained one-refinement compiled authority";
  namespace_literals request;
  let long_request = A.to_json request |> replace "id" (str (String.make 4070 'r')) |> A.of_json in
  let rejected_build = P.compile long_request in
  let gaps = List.concat_map B.Alternative.gaps (B.alternatives rejected_build) in
  require (B.status rejected_build=B.No_solution && B.plan rejected_build=None && B.construction rejected_build=None &&
    List.map (fun gap -> B.Gap.code gap,B.Gap.message gap) gaps =
      ["construction_authority_rejected","Invalid or excessive Circuit construction identity text."])
    "Construction identity rejection must preserve the literal public message and complete inventory";
  (* A large legal identity makes the first construction reservation fail one
     atomic string charge while leaving ample capacity for a no-plan receipt.
     Catching this as a rejected alternative would incorrectly return no_solution. *)
  let request_with_large_identity = A.to_json request |> replace "id" (str (String.make 2000 'r')) |> A.of_json in
  let parent = W.create ~profile:"literal.parent" ~error_code:"caller_stopped" ~maximum:1024 () in
  rejected "caller_stopped" (fun () -> P.compile ~budget:parent request_with_large_identity);
  require (W.remaining parent > 500) "Atomic construction rejection was swallowed and spent further parent allowance";
  let measured = W.create ~profile:"literal.parent" ~error_code:"caller_stopped" ~maximum:P.max_work () in
  ignore (Bioc_checker.Architecture_check.check ~budget:measured ~expected_request:request candidate);
  let used = P.max_work - W.remaining measured in
  require (used>4) "Selected candidate check unexpectedly consumed no work";
  List.iter (fun maximum ->
      let parent = W.create ~profile:"literal.parent" ~error_code:"caller_stopped" ~maximum () in
      rejected "caller_stopped" (fun () -> Bioc_checker.Architecture_check.check ~budget:parent ~expected_request:request candidate))
    [1;used/4;used/2;used-1];
  print_endline "architecture producer candidate literals: exact rejected construction identity and custom parent exhaustion passed"
let literal_request = {|{"schema_version":"biocompiler.payload_architecture_request.v0.1","id":"literal","circuit":{"schema_version":"biocompiler.circuit_request.v0.1","profile":{"schema_version":"biocompiler.circuit_profile_request.v0.1","purpose":"human_immune_payload","mode":"candidate_design","molecular_form":"RNA","boundary":"planning","target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"recipient":{"schema_version":"biocompiler.immune_recipient_identity.v0.1","lineage":"t_cell","target_fingerprint":"c103975a7f835e5d42196ea2cbb9208f756c2a39b8b43cb15e209c735a63440f","cell_subtype_claim_fingerprint":"28fca1bc6ea489b70d192cd51f746cd9a0c2b1ae8077a2872c80c777614f7a6c","eligibility_basis":"declared","empirical_support":"unestablished"},"source_experiment":null,"source_request":{"schema_version":"biocompiler.build_request.v0.1","intent":{"schema_version":"biocompiler.intent.v0.1","name":"literal_role","nodes":[{"id":"role","kind":"role","inputs":[],"attributes":{"cell_type":"human_T_cell","engineering":"in_vivo","name":"recipient"},"data_type":null,"role":null,"source":null}],"roots":["role"]},"explicit_overrides":{},"resolved_defaults":{},"resolved_bindings":{},"target":{"schema_version":"biocompiler.human_target_context.v0.1","context_id":"illustrative_human_target","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["cytoplasm"],"resources":{},"human_target":{"schema_version":"biocompiler.human_target_contract.v0.1","recipient_taxon_id":9606,"engineering":"in_vivo","cell_subtype":{"schema_version":"biocompiler.target_claim.v0.1","description":"Human CD8-positive T-cell recipients; subtype refinement remains open.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"cell_state":{"schema_version":"biocompiler.target_claim.v0.1","description":"Required recipient activation/differentiation state remains unspecified.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"tissue_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended human tissue context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"disease_context":{"schema_version":"biocompiler.target_claim.v0.1","description":"Intended disease context remains to be selected.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_inclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Eligible human population and inclusion criteria remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"population_exclusion":{"schema_version":"biocompiler.target_claim.v0.1","description":"Population exclusions require an explicit applicability review.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."},"host_dependencies":[{"schema_version":"biocompiler.human_host_dependency.v0.1","id":"translation","capability":"host_translation","compartment":"cytoplasm","support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Host translation support requires context-matched evidence.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"operating_conditions":[{"schema_version":"biocompiler.human_operating_condition.v0.1","id":"resource_availability","observable":"available_translation_resources","compartment":"cytoplasm","domain":{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"unknown","dtype":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"unit":"1","values":[],"lower":null,"upper":null,"reason":"No supported resource operating range is established."},"support":{"schema_version":"biocompiler.target_claim.v0.1","description":"Supported intracellular resource conditions remain unresolved.","basis":"unestablished","evidence_ids":[],"limitations":"Illustrative requirement only; applicable evidence has not been supplied."}}],"evidence":[]}},"artifact_scope":"abstract_behavior","behavior_profile":"biocompiler.behavior.v0.1","implementation_constraints":{},"preferences":{},"parameter_metadata":{},"provenance":{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}}},"requirements":[{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"required","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"artificial_alpha","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"readout.0","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"software_fixture","accession":"readout.0","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":"role","source_node_ids":["role"],"source_location":null,"input_bindings":[]}],"requested_form":"delivered_rna","fidelity_scope":"complete_nominal","deployment_id":"declared-human-rna-architecture","selected_realization":null,"reference_lock":null},"library":{"schema_version":"biocompiler.payload_architecture_library.v0.1","id":"empty","refinements":[],"assumptions":[]},"constraints":{"schema_version":"biocompiler.rna_architecture_constraints.v0.2","exact_count":null,"max_count":null,"max_member_bases":null,"max_total_bases":null,"delivery_groups":[],"control_requirements":[],"preferred_refinement_ids":[],"max_combinations":256,"require_complete":false,"max_match_states":100000,"max_match_instances":256,"deployment_requirements":[]}}|}
let literals () =
  let request=A.of_json (Json.parse literal_request) in
  let source=A.source request in
  let source_raw=Human_request.to_json source in
  let intent=field "intent" source_raw in
  let node=List.hd (Json.array (field "nodes" intent)) in
  let semantics=obj (List.remove_assoc "source" (Json.object_fields node)) in
  let behavior=obj ["schema_version",str "biocompiler.behavior.v0.1";"name",field "name" intent;
    "nodes",arr [node |> replace "contact_bound" (Json.Bool false) |> replace "requirement_ids" (arr [])];
    "roots",field "roots" intent;"source_fingerprint",str (Intent.fingerprint (Intent.of_json intent));
    "requirements",arr [];"source_links",obj ["role",arr [str "role"]];"policies",Behavior.execution_policies Behavior.V0_1;"parameter_bindings",obj []] |> Behavior.of_json in
  let manifest=Source_execution_manifest.make ~source ~behavior:(Some behavior) ~roles:["role"] ~outputs:[]
    ~ledger:[obj ["id",str "source:role";"kind",str "role";"source_node_ids",arr [str "role"];"semantics",semantics];
      obj ["id",str "source:complete_authority";"kind",str "source_authority";"source_node_ids",arr [str "role"];"semantics",source_raw]]
    ~role_nodes:(obj ["role",arr [str "role"]]) ~states:[] ~channels:[] ~diagnostics:[] in
  let gap=B.Gap.make ~category:B.Gap.Missing_implementation ~code:"no_supplied_architecture_satisfies_requirements" ~requirement_ids:[] ~candidate_ids:[]
    ~message:"No examined supplied architecture met all source, composition and construction requirements; the identified conflict set is not claimed minimal." ~conflict_set:[] in
  let expected=B.make ~request_fingerprint:(A.fingerprint request) ~execution:manifest ~plan:None ~construction:None ~alternatives:[] ~diagnostics:[gap] ~status:B.No_solution ~match_instances:[] in
  let result=P.compile request in
  require (Json.equal (B.to_json result) (B.to_json expected)) "Empty-library producer lost exact source or invented selected material";
  require (Architecture_assessment.passed (Bioc_checker.Architecture_check.check ~expected_request:request result)) "Independent checker rejected literal producer";
  rejected "architecture_export_rejected" (fun () -> P.export ~expected_request:request result);
  let parent=Bioc_checker.Work_budget.create ~profile:"literal" ~error_code:"literal_parent_limit" ~maximum:0 () in
  rejected "literal_parent_limit" (fun () -> P.compile ~budget:parent request);
  print_endline "architecture producer literals: independently expected empty search, fresh checking, export rejection and cumulative bound passed"
let read_json maximum path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes=in_channel_length channel in require (bytes<=maximum) "Retained file exceeds read bound";
    Json.parse (really_input_string channel bytes),bytes)
let bounded_int maximum raw =
  let value=Json.integer raw in require (Z.sign value>=0 && Z.compare value (Z.of_int maximum)<=0) "Invalid corpus count";Z.to_int value
let safe_hash identity =
  require (String.length identity=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) identity) "Unsafe content identity";identity
let rec edit_at raw path value = match path with
  | [] -> (match value with Some value->value|None->failwith "Root deletion")
  | Json.String key::rest ->
      let fields=Json.object_fields raw in
      if rest=[] then (
        require (value<>None || List.mem_assoc key fields) "Missing terminal deletion";
        match value with Some value->replace key value raw|None->obj (List.remove_assoc key fields))
      else (require (List.mem_assoc key fields) "Absent object descent";
        replace key (edit_at (List.assoc key fields) rest value) raw)
  | Json.Int index::rest ->
      let values=Json.array raw in
      require (Z.sign index>=0 && Z.compare index (Z.of_int (List.length values))<0 && (rest<>[] || value<>None)) "Invalid array delta";
      let index=Z.to_int index in arr (List.mapi (fun position old -> if position=index then edit_at old rest value else old) values)
  | _ -> failwith "Invalid delta path"
let apply_edits raw edits = List.fold_left (fun raw edit ->
    let value=match text "op" edit with
      | "set"->Json.exact_fields ["op";"path";"value"] (Json.object_fields edit);Some (field "value" edit)
      | "remove"->Json.exact_fields ["op";"path"] (Json.object_fields edit);None
      | _->failwith "Invalid delta operation" in
    let path=Json.array (field "path" edit) in require (path<>[] && List.length path<=96) "Invalid delta depth";
    edit_at raw path value) raw edits
let circuit raw = match Circuit_request.of_json raw with
  | Circuit_request.Decoded value -> value
  | Circuit_request.Unsupported _ -> failwith "Retained circuit authority is unsupported"
let normalized kind raw = match kind with
  | "source"->Human_request.to_json (Human_request.of_json raw)
  | "manifest"->Source_execution_manifest.to_json (Source_execution_manifest.of_json raw)
  | "refinement"->Architecture_refinement.to_json (Architecture_refinement.of_json raw)
  | "behavior"->Behavior.to_json (Behavior.of_json raw)
  | "circuit"->Circuit_request.to_json (circuit raw)
  | "request"->A.to_json (A.of_json raw)
  | "build"->B.to_json (B.of_json raw)
  | _->failwith "Unknown producer document kind"
type descriptor={kind:string;format:string;base:string option;raw:Json.t;resolved_bytes:int}
let corpus path =
  require (not (Filename.is_relative path)) "Corpus path must be absolute";
  let index,index_bytes=read_json (16*1024*1024) path in
  require (text "schema_version" index="biocompiler.architecture_producer_conformance.v1") "Wrong producer corpus schema";
  let pin=text "inventory_fingerprint" index in
  require (pin="269e64293c36d52a5ad797c5c2808e52b0072e520992ade9bfa9f5de97dff90a") "Producer corpus inventory changed";
  require (Canonical.fingerprint (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)))=pin) "Producer corpus hash invalid";
  let directory=Filename.remove_extension path in
  let metadata=Json.array (field "documents" index) and cases=Json.array (field "cases" index) in
  let coverage=field "coverage" index in
  require (List.length metadata=166 && List.length cases=193) "Complete producer census changed";
  let seen=Hashtbl.create 256 and stored_bytes=ref index_bytes and resolved_bytes=ref 0 in
  List.iter (fun item ->
      let identity=safe_hash (text "id" item) in require (not (Hashtbl.mem seen identity)) "Duplicate document";
      Json.exact_fields ["id";"kind";"format";"stored_fingerprint";"bytes";"resolved_bytes";"base"] (Json.object_fields item);
      let expected_bytes=bounded_int 4_000_000 (field "bytes" item) in
      stored_bytes:= !stored_bytes+expected_bytes;require (!stored_bytes<=16*1024*1024) "Aggregate stored campaign bound";
      let raw,bytes=read_json 4_000_000 (Filename.concat directory (identity ^ ".json")) in
      require (bytes=expected_bytes && Canonical.fingerprint raw=text "stored_fingerprint" item) "Stored document hash/bytes changed";
      Molecular_record.check_resources raw;
      let format=text "format" item in
      require (bytes=(if format="full" then Molecular_record.pretty_size raw+1 else String.length (Canonical.encode raw)+1)) "Stored encoding changed";
      let length=bounded_int 4_000_000 (field "resolved_bytes" item) in resolved_bytes:= !resolved_bytes+length;
      require (!resolved_bytes<=512*1024*1024) "Aggregate resolved campaign bound";
      let base=match field "base" item with Json.Null->None|raw->Some (safe_hash (Json.string raw)) in
      Hashtbl.add seen identity {kind=text "kind" item;format;base;raw;resolved_bytes=length}) metadata;
  let filenames=Sys.readdir directory |> Array.to_list |> List.sort String.compare in
  require (filenames=(List.map (fun item->text "id" item ^ ".json") metadata |> List.sort String.compare)) "Stored file inventory differs";
  require (!stored_bytes-index_bytes=bounded_int (16*1024*1024) (field "stored_bytes" coverage) && !resolved_bytes=bounded_int (512*1024*1024) (field "resolved_bytes" coverage)) "Byte census differs";
  let resolve identity =
    let descriptor=Hashtbl.find seen identity in
    let raw=match descriptor.format,descriptor.base with
      | "full",None -> descriptor.raw
      | "delta",Some base ->
          let original=Hashtbl.find seen base in
          require (original.format="full" && original.base=None && original.kind=descriptor.kind && base<>identity && Canonical.fingerprint original.raw=base) "Invalid one-level baseline";
          Json.exact_fields ["schema_version";"base";"edits"] (Json.object_fields descriptor.raw);
          require (text "schema_version" descriptor.raw="biocompiler.test_document_delta.v1" && text "base" descriptor.raw=base) "Delta authority mismatch";
          apply_edits original.raw (Json.array (field "edits" descriptor.raw))
      | _->failwith "Invalid document format" in
    Molecular_record.check_resources raw;
    require (Molecular_record.pretty_size raw+1=descriptor.resolved_bytes && Canonical.fingerprint raw=identity) "Complete resolved authority changed";
    raw in
  Hashtbl.iter (fun identity descriptor -> let raw=resolve identity in
    require (Json.equal (normalized descriptor.kind raw) raw) "Complete typed normalization differs") seen;
  let required=Hashtbl.create 256 and case_ids=Hashtbl.create 256 and counts=Hashtbl.create 4 in
  let candidate_literals_ran = ref false in
  let read expected_kind identity =
    let descriptor=Hashtbl.find seen identity in require (descriptor.kind=expected_kind) "Case authority kind mismatch";
    Hashtbl.replace required identity ();Option.iter (fun base->Hashtbl.replace required base ()) descriptor.base;
    resolve identity in
  List.iter (fun case ->
      let id=text "id" case in require (not (Hashtbl.mem case_ids id)) "Duplicate case identity";Hashtbl.add case_ids id ();
      let operation=text "operation" case in Hashtbl.replace counts operation (1+Option.value ~default:0 (Hashtbl.find_opt counts operation));
      let read_field kind=read kind (text kind case) in
      match operation with
      | "source" ->
          let actual=S.derive (Human_request.of_json (read_field "source")) |> Source_execution_manifest.to_json in
          require (Json.equal actual (read_field "manifest")) ("Complete source output differs: " ^ id)
      | "match" ->
          let refinement=Architecture_refinement.of_json (read_field "refinement") and behavior=Behavior.of_json (read_field "behavior") in
          let circuit=match field "circuit" case with Json.Null->None|raw->Some (circuit (read "circuit" (Json.string raw))) in
          let result=M.match_refinement ?circuit ~max_states:(bounded_int 1_000_000 (field "max_states" case))
              ~max_instances:(bounded_int 256 (field "max_instances" case)) refinement behavior in
          let actual=obj ["instances",arr (List.map Architecture_contract.Instance.to_json (M.instances result));"states_examined",Json.int (M.states_examined result);
            "exhausted",Json.Bool (M.exhausted result);"diagnostics",arr (List.map str (M.diagnostics result))] in
          require (Json.equal actual (field "expected" case) && Canonical.fingerprint actual=text "expected_fingerprint" case) ("Exact matching result differs: " ^ id);
          let fingerprints=List.map (fun instance -> M.instantiate refinement instance |> Architecture_refinement.to_json |> Canonical.fingerprint |> str) (M.instances result) in
          require (Json.equal (arr fingerprints) (field "instantiated_fingerprints" case)) ("Instantiated model authority differs: " ^ id)
      | "compile" ->
          let request=A.of_json (read_field "request") in
          let actual=P.compile request in
          require (Json.equal (B.to_json actual) (read_field "build")) ("Complete architecture candidate differs: " ^ id);
          if id="test_payload_architecture.PayloadArchitectureTests.setUpClass/compile/0" then (
            candidate_literals request actual; candidate_literals_ran := true)
      | "export" ->
          let result=P.export ~expected_request:(A.of_json (read_field "request")) (B.of_json (read_field "build")) in
          require (Canonical.fingerprint (B.Export.to_json result)=text "expected_fingerprint" case && B.Export.fasta result=text "fasta" case) ("Complete exact RNA export differs: " ^ id)
      | _->failwith "Unknown producer operation") cases;
  require (Hashtbl.length required=Hashtbl.length seen) "Unreferenced producer documents";
  require !candidate_literals_ran "Candidate resource and diagnostic literals did not execute";
  List.iter (fun (name,count) -> require (Hashtbl.find_opt counts name=Some count) ("Lost producer operation " ^ name)) ["source",67;"match",40;"compile",56;"export",30];
  Printf.printf "architecture producers: %d complete cases / %d documents, full source/matching/search/export equality passed\n" (List.length cases) (List.length metadata)
let () =
  literals ();
  match Array.to_list Sys.argv with
  | [_]->()
  | [_;path]->corpus path
  | _->failwith "Usage: test_architecture_producer.exe [absolute-corpus.json]"
