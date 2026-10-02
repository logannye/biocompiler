open Bioc_wire
open Bioc_domain
module P = Bioc_compiler.Construction_producer
module R = Bioc_compiler.Recoding_producer
module W = Bioc_compiler.Construction_workflow
module C = Construction
module A = Construction_artifact
module G = Molecule_coordinates
module H = Molecule_chemistry
module N = Molecule
module T = Molecular_transition
let count = ref 0
let require condition message = incr count; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key raw = Json.field key (Json.object_fields raw)
let rejected code run = incr count; match run () with _ -> failwith ("Expected " ^ code)
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then failwith (code ^ ": got " ^ diagnostic.code)
(* The complete artificial reference authority is an independently authored
   retained literal shared with the checker campaign, not a producer output. *)
let circuit_literal = {|{"schema_version":"biocompiler.circuit_request.v0.1","profile":{"schema_version":"biocompiler.circuit_profile_request.v0.1","purpose":"human_reference","mode":"exact_reproduction","molecular_form":"RNA","boundary":"import","target":null,"recipient":null,"source_request":null,"source_experiment":{"schema_version":"biocompiler.human_experiment_context.v0.1","system":"primary_human_cells","immune_classification":"immune","cell_identity":"artificial declared cell","cell_state":"unestablished","compartment":"cytoplasm","delivery_mode":"rna_delivery","sources":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"locator":"literal","assay_conditions":["explicit unknown"],"recipient_taxon_id":9606,"immune_lineage":"t_cell"}},"requirements":[{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"required-output","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"protein","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"declared-product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":null,"source_node_ids":[],"source_location":null,"input_bindings":[]}],"requested_form":"delivered_rna","fidelity_scope":"complete_nominal","deployment_id":null,"selected_realization":{"schema_version":"biocompiler.component_identity.v0.1","kind":"reference","id":"reference","version":"1","content_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"reference_lock":{"schema_version":"biocompiler.circuit_reference_lock.v0.1","expected_behaviors":[{"schema_version":"biocompiler.circuit_behavior_expectation.v0.1","requirement_id":"required-output","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[],"outputs":[true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"protein","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"declared-product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]}}],"realization":{"schema_version":"biocompiler.component_identity.v0.1","kind":"reference","id":"reference","version":"1","content_fingerprint":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"authority":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"source_experiment":{"schema_version":"biocompiler.human_experiment_context.v0.1","system":"primary_human_cells","immune_classification":"immune","cell_identity":"artificial declared cell","cell_state":"unestablished","compartment":"cytoplasm","delivery_mode":"rna_delivery","sources":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"source","id":"source","version":"1","content_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"locator":"literal","assay_conditions":["explicit unknown"],"recipient_taxon_id":9606,"immune_lineage":"t_cell"},"requested_form":"delivered_rna","fidelity_scope":"complete_nominal"}}|}
let frame alphabet length id = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";
  "id",str id;"alphabet",str (match alphabet with G.Dna->"DNA" | G.Rna->"RNA" | G.Protein->"protein");"length",Json.int length;
  "topology",str "linear";"axis",str (if alphabet=G.Protein then "N_to_C" else "5prime_to_3prime")])
let path frame first last = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";
  "space_id",str (G.Space_id.to_string (G.Space.id frame));"strand",str "+";
  "spans",arr [obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int first;"end",Json.int last]]])
let literals () =
  let circuit = match Circuit_request.of_json (Json.parse circuit_literal) with Circuit_request.Decoded value->value
    | Circuit_request.Unsupported _ -> failwith "Literal declarations unsupported" in
  let provenance = Molecular_record.Provenance.make ~status:Molecular_record.Provenance.Declared
    ~authority:[Pinned_identity.make ~kind:Pinned_identity.Source ~id:"artificial-literal" ~version:"1" ~content_fingerprint:(String.make 64 'a')]
    ~locator:(Some "literal") ~reason:"Artificial exact construction literal." in
  let identity = H.Chemical_identity.make ~namespace:"biocompiler.chemical" ~accession:"hydroxyl" ~version:"1" in
  let claim status identity = H.Claim.make ~status ~identity ~provenance in
  let chemistry alphabet = H.make ~cap:(claim (if alphabet=G.Rna then H.Absent else H.Inapplicable) None)
    ~start_end:(claim H.Declared (Some identity)) ~finish_end:(claim H.Declared (Some identity)) ~modifications:[]
    ~modification_inventory_status:H.Declared ~modification_inventory_provenance:provenance
    ~terminal_tail:(if alphabet=G.Rna then H.Tail.make ~status:H.Declared ~placement:(Some H.Tail.Absent_tail)
        ~length:(Some (H.Tail_length.make (H.Tail_length.Exact 0))) ~path:None ~provenance
      else H.Tail.make ~status:H.Inapplicable ~placement:None ~length:None ~path:None ~provenance) in
  let molecule ?(features=[]) id sequence =
    let space=frame G.Rna (String.length sequence) "root.frame" and original=frame G.Rna (String.length sequence) "independent.frame" in
    N.make ~id ~form:N.Delivered_rna ~space ~sequence ~sequence_extent:H.Complete ~coding_status:N.Noncoding
      ~assembly:[N.Assembly_origin.make ~id:"supplied.origin" ~destination:(path space 0 (String.length sequence))
        ~source_space:original ~source_path:(path original 0 (String.length sequence)) ~provenance]
      ~features ~chemistry:(chemistry G.Rna) ~provenance in
  let root_frame=frame G.Rna 4 "root.frame" in
  let feature=N.Feature.make ~id:"region" ~kind:"nominal_test_region" ~path:(Some (path root_frame 0 1)) ~provenance () in
  let root=molecule ~features:[feature] "supplied" "ACGU" in
  let selection=C.Selection.make (C.Value_ref.make ~kind:C.Value_ref.Root ~id:"root") in
  let member=C.Output_member.make ~id:"payload" ~value:(C.Selection.value selection) ~space_id:"final.frame"
    ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Noncoding ~provenance in
  let role=C.Role.make ~id:"payload.role" ~role:"literal_payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm" in
  let contract=Payload_structure.make ~member_id:"payload" ~form:Payload_structure.Delivered_rna ~topology:G.Linear
    ~regions:[Payload_structure.Region.make ~feature_id:"region" ~kind:"nominal_test_region"] ~provenance in
  let request=C.Request.make ~id:"literal" ~circuit ~sources:[C.Root_source.make ~id:"root" ~molecule:root ~provenance]
    ~steps:[] ~output_members:[member] ~requirements:[C.Member_requirement.make ~id:"required" ~category:C.Member_requirement.Payload
      ~subject:(C.Member_requirement.Materialized "payload") ~roles:[role]] ~mode:C.Request.Strict ~payload_structures:[contract] () in
  let candidate=P.construct request in
  require (C.Request.fingerprint request="bad9bf874f983c4284286ea965adad5137f36daf048a67b631e5f462372b6e70") "Independent request literal changed";
  require (A.fingerprint candidate="641e1d526be09eabf8ca1747e92f02164ff8cf79da0a9c8be67b2ed5b073a846") "Independent whole candidate literal differs";
  let build=W.build request in
  require (Construction_assessment.passed (W.verify ~expected_request:request build)) "Fresh literal workflow failed";
  require (List.map N.sequence (Molecule_set.molecules (Molecule_set.Artifact.bundle (W.verified_molecules ~expected_request:request build)))=["ACGU"])
    "Fresh strict literal handoff lost complete bases";
  let limited=P.construct ~limits:(P.Limits.make ~final_residues:3 ()) request in
  require (A.bundle limited=None && A.missing_members limited=["payload"] && A.diagnostics limited=["bundle:residue_budget"])
    "Final aliases were allocated before the exact residue preflight";
  rejected "construction_producer_limit" (fun () -> P.Limits.make ~produced_residues:1_000_001 ());
  rejected "construction_producer_limit" (fun () -> P.construct ~limits:(P.Limits.make ~work:0 ()) request);
  let available=R.Available.of_bindings ["root",R.Root (molecule "translation" "AUGGCUUAA")] in
  let port id alphabet = C.Product_port.make ~id ~space_id:(id ^ ".frame") ~alphabet ~topology:G.Linear
    ~chemistry_transition:(T.Chemistry.make ~mode:T.Chemistry.Explicit_output ~output:(Some (chemistry alphabet)) ~dispositions:[] ~provenance)
    ~feature_transition:(T.Feature.make ~dispositions:[] ~added:[] ~provenance) in
  let policy=Molecular_recoding.Translation_policy.make ~profile:Molecular_recoding.Translation_policy.Ordinary_cds () in
  let step=C.Transform_step.make ~id:"translate" ~operation:(C.Operation.make (C.Operation.Translation {input=selection;policy}))
    ~ports:[port "peptide" G.Protein] ~assumptions:[] ~provenance in
  let translated=R.construct_step ~step ~available ~remaining_residues:2 () in
  require (translated.diagnostic=None && translated.used_residues=2 && List.map A.Value.sequence translated.values=["MA"])
    "Independent AUG/GCU/UAA literal failed";
  let value=List.hd translated.values in
  let derived=List.hd (A.Value.segments value) and consumed=List.hd (A.Value.consumed value) in
  require (G.Path.length (A.Derived_segment.source_path derived)=6 && A.Derived_segment.rule derived=A.Derived_segment.Translation_codon &&
    G.Span.start (List.hd (G.Path.spans (A.Consumed_segment.source_path consumed)))=6 && G.Path.length (A.Consumed_segment.source_path consumed)=3)
    "Terminal stop or codon-to-residue provenance was lost";
  let insufficient=R.construct_step ~step ~available ~remaining_residues:1 () in
  require (insufficient.values=[] && insufficient.used_residues=0 && insufficient.diagnostic=Some "residue_budget") "Translation allocated before budget reservation";
  let bad_available=R.Available.of_bindings ["root",R.Root (molecule "invalid" "AUGGCUAAA")] in
  let bad=R.construct_step ~step ~available:bad_available ~remaining_residues:2 () in
  require (bad.values=[] && bad.used_residues=2 && bad.diagnostic=Some "invalid_translation") "Failed translation lost attempted work or exposed staged values";
  rejected "invalid_construction_producer_input" (fun () -> R.Available.of_bindings ["root",R.Root root;"root",R.Root root]);
  let rec bindings=("root",R.Root root)::bindings in
  rejected "molecular_resource_limit" (fun () -> R.Available.of_bindings bindings);
  rejected "construction_producer_limit" (fun () -> R.make_budget ~maximum:(R.max_work+1) ());
  rejected "construction_producer_limit" (fun () -> R.construct_step ~budget:(R.make_budget ~maximum:0 ()) ~step ~available ~remaining_residues:2 ());
  let parent maximum=Bioc_checker.Work_budget.create ~profile:"literal" ~error_code:"literal_parent_limit" ~maximum () in
  rejected "literal_parent_limit" (fun () -> P.construct ~parent:(parent 0) request);
  rejected "construction_producer_limit" (fun () -> P.construct ~parent:(parent 100_000_000) ~limits:(P.Limits.make ~work:0 ()) request);
  rejected "literal_parent_limit" (fun () -> R.construct_step ~budget:(R.make_budget ~parent:(parent 0) ()) ~step ~available ~remaining_residues:2 ());
  let measured=parent 100_000_000 in
  ignore (P.construct ~parent:measured request);
  let spent=100_000_000-Bioc_checker.Work_budget.remaining measured in
  require (spent>0) "Native construction was not charged to its ancestor";
  let cumulative=parent (2*spent-1) in
  ignore (P.construct ~parent:cumulative request);
  rejected "literal_parent_limit" (fun () -> P.construct ~parent:cumulative request);
  rejected "literal_parent_limit" (fun () -> W.build ~parent:(parent 0) request);
  rejected "literal_parent_limit" (fun () -> W.verify ~parent:(parent 0) ~expected_request:request build);
  rejected "literal_parent_limit" (fun () -> W.verified_molecules ~parent:(parent 0) ~expected_request:request build);
  rejected "construction_resource_limit" (fun () -> Bioc_checker.Construction_check.check ~maximum:0 ~expected_request:request candidate);
  rejected "construction_resource_limit" (fun () -> Bioc_checker.Construction_check.check ~maximum:50_000_001 ~expected_request:request candidate);
  let checked_parent=parent 50_000_000 in
  ignore (Bioc_checker.Construction_check.check ~parent:checked_parent ~expected_request:request candidate);
  let checked_spent=50_000_000-Bioc_checker.Work_budget.remaining checked_parent in
  require (checked_spent>spent) "Independent full reconstruction/checking was not charged";
  rejected "literal_parent_limit" (fun () -> Bioc_checker.Construction_check.check ~parent:(parent (checked_spent-1)) ~expected_request:request candidate);
  let bundle=Option.get (A.bundle candidate) in
  let payload_parent=parent 10_000_000 in
  ignore (Bioc_checker.Payload_structure_check.check_with_parent ~parent:(Some payload_parent) ~contracts:[contract] ~bundle);
  let payload_spent=10_000_000-Bioc_checker.Work_budget.remaining payload_parent in
  require (payload_spent>1) "Payload region work was not charged";
  rejected "literal_parent_limit" (fun () -> Bioc_checker.Payload_structure_check.check_with_parent ~parent:(Some (parent (payload_spent-1))) ~contracts:[contract] ~bundle);
  rejected "transition_resource_limit" (fun () -> Bioc_checker.Transition_check.make_budget ~parent:(parent 50_000_000) ~max_work:10_000_001 ());
  let publication=R.make_budget () in
  R.protect (fun () -> R.reserve_output publication (str (String.make 2_000_000 'x')));
  rejected "construction_producer_output_limit" (fun () -> R.protect (fun () -> R.reserve_output publication (str (String.make 2_000_000 'x'))));
  let staged=R.make_budget () in
  R.protect (fun () -> R.reserve_staged staged (str (String.make 2_000_000 'x')));
  rejected "construction_producer_output_limit" (fun () -> R.protect (fun () -> R.reserve_staged staged (str (String.make 2_000_000 'x'))));
  let rec raw_values=Json.Null::raw_values in
  rejected "construction_producer_limit" (fun () -> R.protect (fun () -> R.reserve_json (R.make_budget ~maximum:4 ()) (arr raw_values)));
  Printf.printf "construction producer: %d independent literal and resource checks passed\n" !count
let read_json maximum path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in require (size<=maximum) "Producer fixture file exceeds read budget";
    Json.parse (really_input_string channel size),size)
let retained path =
  require (not (Filename.is_relative path)) "Producer corpus path must be absolute";
  let index,index_bytes=read_json Limits.max_request_bytes path in
  require (field "schema_version" index=str "biocompiler.construction_producer_conformance.v1") "Wrong producer corpus";
  let fields=Json.object_fields index in
  let fingerprint=Canonical.fingerprint (obj (List.remove_assoc "inventory_fingerprint" fields)) in
  require (fingerprint="191464d3a469fbedfacf6d9951104578054a531b917fd98e289962231fbcc1d6" && field "inventory_fingerprint" index=str fingerprint)
    "Complete producer inventory changed";
  let docs=Hashtbl.create 256 and used=Hashtbl.create 256 and total=ref index_bytes in
  let directory=Filename.remove_extension path in
  let metadata=Json.array (field "documents" index) in
  require (List.length metadata=172) "Truncated producer document census";
  List.iter (fun entry ->
    let id=Json.string (field "id" entry) and kind=Json.string (field "kind" entry) in
    require (String.length id=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) id && not (Hashtbl.mem docs id)) "Invalid producer document identity";
    let raw,bytes=read_json 4_000_000 (Filename.concat directory (id ^ ".json")) in
    total := !total+bytes; require (!total<=16*1024*1024 && Json.int bytes=field "bytes" entry) "Producer aggregate byte census differs";
    require (Canonical.fingerprint raw=id) "Complete producer document changed";
    let normalized=match kind with
      | "request" -> C.Request.to_json (C.Request.of_json raw) | "candidate" -> A.to_json (A.of_json raw)
      | "step" -> C.Transform_step.to_json (C.Transform_step.of_json raw) | "root" -> N.to_json (N.of_json raw)
      | "value" -> A.Value.to_json (A.Value.of_json raw) | "build" -> Construction_build.to_json (Construction_build.of_json raw)
      | "assessment" -> Construction_assessment.to_json (Construction_assessment.of_json raw)
      | "molecules" -> Molecule_set.Artifact.to_json (Molecule_set.Artifact.of_json raw) | _ -> failwith "Unknown producer document kind" in
    require (Canonical.encode normalized=Canonical.encode raw) "Producer authority normalization differs";
    Hashtbl.add docs id (kind,raw)) metadata;
  let files=Sys.readdir directory |> Array.to_list |> List.filter (fun name -> Filename.check_suffix name ".json") |> List.sort String.compare in
  require (files=(List.map (fun entry -> Json.string (field "id" entry) ^ ".json") metadata |> List.sort String.compare))
    "Missing/extra producer stored files";
  let get kind identity = let id=Json.string identity in Hashtbl.replace used id ();
    let actual,raw=Hashtbl.find docs id in require (actual=kind) "Producer case document kind changed";raw in
  let cases key census run =
    let rows=Json.array (field key index) and identities=Hashtbl.create 128 in
    require (List.length rows=census) ("Truncated producer " ^ key);
    List.iter (fun row -> let id=Json.string (field "id" row) in require (not (Hashtbl.mem identities id)) "Duplicate producer case";
      Hashtbl.add identities id ();run id row) rows in
  cases "constructions" 61 (fun id case ->
    let request=C.Request.of_json (get "request" (field "request" case)) in
    let integer key=Z.to_int (Json.integer (field key case)) in
    let actual=P.construct ~limits:(P.Limits.make ~produced_residues:(integer "produced_residues") ~final_residues:(integer "final_residues") ()) request in
    let expected=get "candidate" (field "candidate" case) in
    require (Canonical.encode (A.to_json actual)=Canonical.encode expected) (id ^ ": exact complete candidate differs"));
  cases "recodings" 37 (fun id case ->
    let step=C.Transform_step.of_json (get "step" (field "step" case)) in
    let available=Json.array (field "available" case) |> List.map (fun binding ->
      let kind=Json.string (field "kind" binding) in let raw=get kind (field "document" binding) in
      Json.string (field "id" binding),(match kind with "root"->R.Root (N.of_json raw)|"value"->R.Product (A.Value.of_json raw)|_->failwith "Bad recoding material")) |> R.Available.of_bindings in
    let result=R.construct_step ~step ~available ~remaining_residues:(Z.to_int (Json.integer (field "remaining_residues" case))) () in
    let expected=Json.array (field "values" case) |> List.map (get "value") in
    require (Canonical.encode (arr (List.map A.Value.to_json result.values))=Canonical.encode (arr expected) &&
      Json.int result.used_residues=field "used_residues" case &&
      (match result.diagnostic with None->Json.Null|Some code->str code)=field "diagnostic" case)
      (id ^ ": atomic recoding result or attempted residue accounting differs"));
  cases "workflows" 88 (fun id case ->
    let request=C.Request.of_json (get "request" (field "request" case)) in
    let build=match field "build" case with Json.Null->None|value->Some (Construction_build.of_json (get "build" value)) in
    let operation=Json.string (field "operation" case) in
    let run ()=match operation with
      | "build_circuit_construction" -> Construction_build.to_json (W.build request)
      | "verify_circuit_construction" -> Construction_assessment.to_json (W.verify ~expected_request:request (Option.get build))
      | "verified_circuit_molecules" -> Molecule_set.Artifact.to_json (W.verified_molecules ~expected_request:request (Option.get build))
      | _ -> failwith "Unknown construction workflow" in
    match field "expected_error" case with
    | Json.String code -> rejected code run
    | Json.Null ->
        let kind=match operation with "build_circuit_construction"->"build"|"verify_circuit_construction"->"assessment"|_->"molecules" in
        let expected=get kind (field "result" case) in
        require (Canonical.encode (run ())=Canonical.encode expected) (id ^ ": fresh public workflow differs")
    | _ -> failwith "Malformed workflow outcome");
  require (Hashtbl.length used=Hashtbl.length docs) "Unused producer fixture document";
  require (!total=9_275_816) "Producer exact file-byte census changed";
  Printf.printf "construction producer: 61 exact candidates, 37 atomic recoding steps, 88 fresh workflows and 172 complete documents passed\n"
let ()=match Array.to_list Sys.argv with [_]->literals () | [_;path]->literals ();retained path
  | _->failwith "Usage: test_construction_producer.exe [<absolute-corpus.json>]"
