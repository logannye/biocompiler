open Bioc_wire
open Bioc_domain
module C = Construction
module A = Construction_artifact
module E = Construction_assessment
module K = Bioc_checker.Construction_check
module G = Molecule_coordinates
module H = Molecule_chemistry
module N = Molecule
module S = Molecule_set
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected code action = match action () with _ -> failwith ("Expected " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code) ("Expected " ^ code ^ ", got " ^ diagnostic.code)
let circuit_literal = {|{"schema_version":"biocompiler.circuit_request.v0.1","profile":{"schema_version":"biocompiler.circuit_profile_request.v0.1","purpose":"human_reference","mode":"exact_reproduction","molecular_form":"RNA","boundary":"import","target":null,"recipient":null,"source_request":null,"source_experiment":{"schema_version":"biocompiler.human_experiment_context.v0.1","system":"primary_human_cells","immune_classification":"immune","cell_identity":"artificial declared cell","cell_state":"unestablished","compartment":"cytoplasm","delivery_mode":"rna_delivery","sources":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"locator":"literal","assay_conditions":["explicit unknown"],"recipient_taxon_id":9606,"immune_lineage":"t_cell"}},"requirements":[{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"required-output","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"protein","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"declared-product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":null,"source_node_ids":[],"source_location":null,"input_bindings":[]}],"requested_form":"delivered_rna","fidelity_scope":"complete_nominal","deployment_id":null,"selected_realization":{"schema_version":"biocompiler.component_identity.v0.1","kind":"reference","id":"reference","version":"1","content_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"reference_lock":{"schema_version":"biocompiler.circuit_reference_lock.v0.1","expected_behaviors":[{"schema_version":"biocompiler.circuit_behavior_expectation.v0.1","requirement_id":"required-output","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"protein","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"declared-product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]}}],"realization":{"schema_version":"biocompiler.component_identity.v0.1","kind":"reference","id":"reference","version":"1","content_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"authority":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"source_experiment":{"schema_version":"biocompiler.human_experiment_context.v0.1","system":"primary_human_cells","immune_classification":"immune","cell_identity":"artificial declared cell","cell_state":"unestablished","compartment":"cytoplasm","delivery_mode":"rna_delivery","sources":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"locator":"literal","assay_conditions":["explicit unknown"],"recipient_taxon_id":9606,"immune_lineage":"t_cell"},"requested_form":"delivered_rna","fidelity_scope":"complete_nominal"}}|}
let space ?(length = 4) id = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";"id",str id;
    "alphabet",str "RNA";"length",Json.int length;"topology",str "linear";"axis",str "5prime_to_3prime"])
let path frame first last = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";
    "space_id",str (G.Space_id.to_string (G.Space.id frame));"strand",str "+";
    "spans",Json.Array [obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int first;"end",Json.int last]]])
let budget_literals ~circuit ~provenance ~chemistry =
  require (C.max_cumulative_produced_residues = 1_000_000) "Construction work limit changed";
  let root length =
    let frame = space ~length "budget.root.frame" and source = space ~length "budget.authority.frame" in
    let molecule = N.make ~id:"budget.source" ~form:N.Delivered_rna ~space:frame ~sequence:(String.make length 'A')
        ~sequence_extent:H.Complete ~coding_status:N.Noncoding ~assembly:[N.Assembly_origin.make ~id:"origin"
          ~destination:(path frame 0 length) ~source_space:source ~source_path:(path source 0 length) ~provenance]
        ~features:[] ~chemistry ~provenance in
    C.Root_source.make ~id:"root" ~molecule ~provenance in
  let selection kind id = C.Selection.make (C.Value_ref.make ~kind ~id) in
  let port id = C.Product_port.make ~id ~space_id:(id ^ ".frame") ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition:(Molecular_transition.Chemistry.make ~mode:Molecular_transition.Chemistry.Exact_inheritance
        ~output:None ~dispositions:[] ~provenance)
      ~feature_transition:(Molecular_transition.Feature.make ~dispositions:[] ~added:[] ~provenance) in
  let step id operation ports = C.Transform_step.make ~id ~operation:(C.Operation.make operation) ~ports ~assumptions:[] ~provenance in
  let request root steps outputs =
    C.Request.make ~id:"budget" ~circuit ~sources:[root] ~steps
      ~output_members:(List.map (fun id -> C.Output_member.make ~id ~value:(C.Value_ref.make ~kind:C.Value_ref.Product ~id)
          ~space_id:(id ^ ".final") ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Noncoding ~provenance) outputs)
      ~requirements:(List.map (fun id -> C.Member_requirement.make ~id:(id ^ ".required") ~category:C.Member_requirement.Payload
          ~subject:(C.Member_requirement.Materialized id) ~roles:[C.Role.make ~id:(id ^ ".role") ~role:"budget_fixture"
            ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"]) outputs) ~mode:C.Request.Strict () in
  let candidate request values missing diagnostics = A.make ~request_fingerprint:(C.Request.fingerprint request) ~values
      ~bundle:None ~missing_members:missing ~diagnostics ~experimental_amounts:[] in
  let oversized = request (root 8000)
      [step "oversized" (C.Operation.Concatenate (List.init 128 (fun _ -> selection C.Value_ref.Root "root"))) [port "oversized"]] ["oversized"] in
  let empty = candidate oversized [] ["oversized"] ["step:oversized:residue_budget";"member:oversized:unavailable_value"] in
  require (C.Request.fingerprint oversized = "ec126967e79be5e9ad2f805be01ffee4f90a5e21b29d37c058109eb1a1c77d94" &&
           A.fingerprint empty = "42aacf9de3b68d9835d7d9f0e8fde4ce04a3bcff5c1c1a53b950bc7bd6fdfa63")
    "Independent immediate-budget literal authority changed";
  let assessment = K.check ~expected_request:oversized empty in
  require (E.reconstructed_fingerprint assessment = A.fingerprint empty &&
           List.mem "unsupported:step:oversized:residue_budget" (E.diagnostics assessment))
    "Oversized repeated traversal exposed a partial output or lost the default work bound";
  (* The first step spends 524288 residues. Each processing port alone fits
     the remaining budget, but their complete partition does not. *)
  let root = root 4096 and length = 524_288 in
  let first_frame = space ~length "first.frame" in
  let first = step "first" (C.Operation.Concatenate (List.init 128 (fun _ -> selection C.Value_ref.Root "root"))) [port "first"] in
  let processing = step "processing" (C.Operation.Rna_cleavage {input=selection C.Value_ref.Product "first";
      products=[C.Processing_product.make ~port_id:"left" ~path:(path first_frame 0 (length / 2));
                C.Processing_product.make ~port_id:"right" ~path:(path first_frame (length / 2) length)]}) [port "left";port "right"] in
  let authority = request root [first;processing] ["left";"right"] in
  let root_frame = N.space (C.Root_source.molecule root) in
  let value = A.Value.make ~id:"first" ~space:first_frame ~sequence:(String.make length 'A') ~chemistry ~features:[]
      ~segments:(List.init 128 (fun index -> A.Derived_segment.make ~destination:(G.Span.of_json (obj
          ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int (index * 4096);"end",Json.int ((index + 1) * 4096)]))
        ~source_id:"root" ~source_path:(path root_frame 0 4096) ~rule:A.Derived_segment.Copy))
      ~step_id:"first" ~sequence_extent:H.Complete ~consumed:[] in
  let expected = candidate authority [value] ["left";"right"]
      ["step:processing:residue_budget";"member:left:unavailable_value";"member:right:unavailable_value"] in
  require (C.Request.fingerprint authority = "a78adc7c6b08962bd2882bbc7ec277cb504124032c904ec08afdb55b1ae587fc" &&
           A.fingerprint expected = "fa812215d13c82d15dfc68f5fbdcb1ded83116ce18fd7101aad9ad1049dbbbed")
    "Independent processing-budget literal authority changed";
  let assessment = K.check ~expected_request:authority expected in
  require (E.reconstructed_fingerprint assessment = A.fingerprint expected &&
           List.mem "unsupported:step:processing:residue_budget" (E.diagnostics assessment))
    "Processing did not reserve all products atomically against cumulative work"
let literals () =
  let circuit = match Circuit_request.of_json (Json.parse circuit_literal) with Circuit_request.Decoded value -> value | Circuit_request.Unsupported _ -> failwith "Literal reference declarations unsupported" in
  let provenance = Molecular_record.Provenance.make ~status:Molecular_record.Provenance.Declared
      ~authority:[Pinned_identity.make ~kind:Pinned_identity.Source ~id:"artificial-literal" ~version:"1" ~content_fingerprint:(String.make 64 'a')]
      ~locator:(Some "literal") ~reason:"Artificial exact construction literal." in
  let identity = H.Chemical_identity.make ~namespace:"biocompiler.chemical" ~accession:"hydroxyl" ~version:"1" in
  let absent = H.Claim.make ~status:H.Absent ~identity:None ~provenance and declared = H.Claim.make ~status:H.Declared ~identity:(Some identity) ~provenance in
  let chemistry = H.make ~cap:absent ~start_end:declared ~finish_end:declared ~modifications:[] ~modification_inventory_status:H.Declared
      ~modification_inventory_provenance:provenance ~terminal_tail:(H.Tail.make ~status:H.Declared ~placement:(Some H.Tail.Absent_tail)
        ~length:(Some (H.Tail_length.make (H.Tail_length.Exact 0))) ~path:None ~provenance) in
  let root_space = space "root.frame" and original_space = space "independent.frame" and final_space = space "final.frame" in
  let feature frame = N.Feature.make ~id:"region" ~kind:"nominal_test_region" ~path:(Some (path frame 0 1)) ~provenance () in
  let molecule id frame origin_id source_frame sequence =
    N.make ~id ~form:N.Delivered_rna ~space:frame ~sequence ~sequence_extent:H.Complete ~coding_status:N.Noncoding
      ~assembly:[N.Assembly_origin.make ~id:origin_id ~destination:(path frame 0 4) ~source_space:source_frame ~source_path:(path source_frame 0 4) ~provenance]
      ~features:[feature frame] ~chemistry ~provenance in
  let root = molecule "supplied" root_space "supplied.origin" original_space "ACGU" in
  let role = C.Role.make ~id:"payload.role" ~role:"literal_payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm" in
  let member = C.Output_member.make ~id:"payload" ~value:(C.Value_ref.make ~kind:C.Value_ref.Root ~id:"root") ~space_id:"final.frame"
      ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Noncoding ~provenance in
  let contract = Payload_structure.make ~member_id:"payload" ~form:Payload_structure.Delivered_rna ~topology:G.Linear
      ~regions:[Payload_structure.Region.make ~feature_id:"region" ~kind:"nominal_test_region"] ~provenance in
  let request = C.Request.make ~id:"literal" ~circuit ~sources:[C.Root_source.make ~id:"root" ~molecule:root ~provenance]
      ~steps:[] ~output_members:[member] ~requirements:[C.Member_requirement.make ~id:"required" ~category:C.Member_requirement.Payload
        ~subject:(C.Member_requirement.Materialized "payload") ~roles:[role]] ~mode:C.Request.Strict ~payload_structures:[contract] () in
  let candidate sequence =
    let final = molecule "payload" final_space "payload.origin" root_space sequence in
    let bundle = S.make ~id:"literal.molecules" ~request:circuit ~molecules:[final] ~complexes:[]
        ~role_instances:[N.Role.make ~id:"payload.role" ~subject_id:"payload" ~subject_fingerprint:(N.fingerprint final)
          ~role:"literal_payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"] ~form_mappings:[] in
    A.make ~request_fingerprint:(C.Request.fingerprint request) ~values:[] ~bundle:(Some bundle) ~missing_members:[] ~diagnostics:[] ~experimental_amounts:[] in
  let actual = candidate "ACGU" in
  require (C.Request.fingerprint request = "bad9bf874f983c4284286ea965adad5137f36daf048a67b631e5f462372b6e70" &&
           A.fingerprint actual = "641e1d526be09eabf8ca1747e92f02164ff8cf79da0a9c8be67b2ed5b073a846")
    "Independent complete direct-root literal authority changed";
  let assessment = K.check ~expected_request:request actual in
  require (E.passed assessment && E.diagnostics assessment = []) "Literal independent direct-root finalization failed";
  require (E.reconstructed_fingerprint assessment = A.fingerprint actual) "Literal expected complete artifact differs";
  require (E.fingerprint (K.replay ~expected_request:request ~candidate:actual assessment) = E.fingerprint assessment) "Fresh literal replay changed identity";
  let forged = candidate "AGGU" in
  let failed = K.check ~expected_request:request forged in
  require (E.outcome failed = E.Fail && List.mem "fail:final_molecule_inventory_or_authority" (E.diagnostics failed)) "Rehashed forged molecule was accepted";
  rejected "construction_assessment_mismatch" (fun () -> K.replay ~expected_request:request ~candidate:forged assessment);
  budget_literals ~circuit ~provenance ~chemistry;
  print_endline "construction checker literal: independent whole RNA, rehashed mutation, fresh replay and default-budget atomicity passed"
let read_json maximum path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= maximum) "Construction checker fixture read budget";
      Json.parse (really_input_string channel size),size)
let rec replace_at value path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove fixture root")
  | Json.String key :: rest ->
      let fields = Json.object_fields value in
      require (rest = [] && replacement <> None || List.mem_assoc key fields) "Absent fixture edit path";
      if rest = [] then obj (match replacement with None -> List.remove_assoc key fields | Some value -> (key,value) :: List.remove_assoc key fields)
      else obj (List.map (fun (name,child) -> name,if name = key then replace_at child rest replacement else child) fields)
  | _ -> failwith "Invalid historical-report edit path"
let edit_report value edits = List.fold_left (fun value edit ->
    let replacement = match Json.string (field "op" edit) with "set" -> Some (field "value" edit) | "remove" -> None | _ -> failwith "Unknown report edit" in
    replace_at value (Json.array (field "path" edit)) replacement) value (Json.array edits)
let retained path =
  require (not (Filename.is_relative path)) "Construction checker corpus path must be absolute";
  let index,index_bytes = read_json Limits.max_request_bytes path in
  require (field "schema_version" index = str "biocompiler.construction_check_conformance.v1") "Wrong construction checking fixture schema";
  require (Canonical.fingerprint index = "b551a905ddc80fb4a6272612381a8f9111c44df66f4048be0bcc8cc188f7e840") "Construction checker exact case/document/diagnostic inventory changed";
  let descriptors = Json.array (field "documents" index) and cases = Json.array (field "cases" index) in
  require (List.length descriptors = 219 && List.length cases = 83) "Construction checker fixture census differs";
  let directory = Filename.remove_extension path and documents = Hashtbl.create 219 and used_bytes = ref index_bytes in
  List.iter (fun descriptor ->
      let id = Json.string (field "id" descriptor) in
      require (String.length id = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) id) "Unsafe construction document identity";
      require (not (Hashtbl.mem documents id)) "Duplicate construction document identity";
      let declared_bytes = Json.integer (field "bytes" descriptor) in
      require (Z.sign declared_bytes >= 0 && Z.compare declared_bytes (Z.of_int Molecular_record.max_json_bytes) <= 0) "Invalid declared construction document size";
      used_bytes := !used_bytes + Z.to_int declared_bytes;
      require (!used_bytes <= Limits.max_request_bytes) "Aggregate retained construction document budget";
      let raw,bytes = read_json Molecular_record.max_json_bytes (Filename.concat directory (id ^ ".json")) in
      require (bytes = Z.to_int declared_bytes && Canonical.fingerprint raw = id) "Construction document bytes or canonical hash differs";
      let normalized = match Json.string (field "kind" descriptor) with
        | "request" -> C.Request.of_json raw |> C.Request.to_json
        | "candidate" -> A.of_json raw |> A.to_json
        | "assessment" -> E.of_json raw |> E.to_json
        | _ -> failwith "Unknown construction fixture document kind" in
      require (Json.equal normalized raw) "Construction fixture document not canonical";
      Hashtbl.add documents id raw) descriptors;
  let document case key = Hashtbl.find documents (Json.string (field key case)) in
  let case_ids = Hashtbl.create 83 and outcomes = Hashtbl.create 4 and observed_operations = ref [] in
  List.iter (fun case ->
      let id = Json.string (field "id" case) in require (not (Hashtbl.mem case_ids id)) "Duplicate construction checking case";
      Hashtbl.add case_ids id case;
      let request = C.Request.of_json (document case "request") and candidate = A.of_json (document case "candidate") in
      let expected_candidate = A.of_json (document case "reconstructed") and expected_assessment = E.of_json (document case "assessment") in
      let assessment = K.check ~expected_request:request candidate in
      require (Json.equal (E.to_json assessment) (E.to_json expected_assessment)) (id ^ ": full fresh assessment differs");
      require (E.reconstructed_fingerprint assessment = A.fingerprint expected_candidate) (id ^ ": complete reconstructed artifact differs");
      (* Checking the retained complete independent artifact also distinguishes
         candidate corruption failures from the request's intrinsic obligations. *)
      let exact = K.check ~expected_request:request expected_candidate in
      require (E.candidate_fingerprint exact = E.reconstructed_fingerprint exact) (id ^ ": expected candidate is not exact");
      require (E.reconstructed_fingerprint exact = A.fingerprint expected_candidate) (id ^ ": reconstructed authority changed on exact candidate");
      require (not (List.exists (String.starts_with ~prefix:"fail:value:") (E.diagnostics exact))) (id ^ ": retained expected value failed comparison");
      let fresh = K.replay ~expected_request:request ~candidate expected_assessment in
      require (E.fingerprint fresh = E.fingerprint assessment) (id ^ ": fresh replay differs");
      let outcome = E.outcome_name (E.outcome assessment) in
      Hashtbl.replace outcomes outcome (1 + Option.value ~default:0 (Hashtbl.find_opt outcomes outcome));
      observed_operations := List.map (fun step -> C.Operation.schema_version (C.Transform_step.operation step)) (C.Request.steps request) @ !observed_operations) cases;
  require (List.sort_uniq String.compare !observed_operations = List.sort String.compare C.Operation.schema_versions) "Missing actual operation checking coverage";
  List.iter (fun (status,count) -> require (Hashtbl.find_opt outcomes status = Some count) "Construction checker outcome census differs")
    ["pass",40;"fail",34;"unknown",1;"unsupported",8];
  List.iter (fun case -> let source = Hashtbl.find case_ids (Json.string (field "source" case)) in
      let request = C.Request.of_json (document source "request") and candidate = A.of_json (document source "candidate") in
      let historical = E.of_json (document case "assessment") in
      rejected (Json.string (field "expected_code" case)) (fun () -> K.replay ~expected_request:request ~candidate historical)) (Json.array (field "replay_rejections" index));
  List.iter (fun case -> let raw = document case "source" in
      rejected (Json.string (field "expected_code" case)) (fun () -> E.of_json (edit_report raw (field "edits" case)))) (Json.array (field "assessment_rejections" index));
  Printf.printf "construction check: 83 complete cases (40 pass/34 fail/8 unsupported/1 unknown), all14 operations/3caseB,3 fresh-replay and28 historical-import rejects passed\n"
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_;path] -> literals (); retained path
  | _ -> failwith "usage: test_construction_check.exe [<absolute-construction-check-corpus.json>]"
