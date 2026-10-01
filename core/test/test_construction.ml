open Bioc_wire
module C = Bioc_domain.Construction
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
module T = Bioc_domain.Molecular_transition
module R = Bioc_domain.Molecular_recoding
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code operation = match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Artificial construction literal."
let span first last = G.Span.of_json (obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int first;"end",Json.int last])
let literal_path spans = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";"space_id",str "frame";
    "strand",str "+";"spans",Json.Array (List.map G.Span.to_json spans)])
let port id = C.Product_port.make ~id ~space_id:(id ^ ".frame") ~alphabet:G.Rna ~topology:G.Linear
    ~chemistry_transition:(T.Chemistry.make ~mode:T.Chemistry.Exact_inheritance ~output:None ~dispositions:[] ~provenance)
    ~feature_transition:(T.Feature.make ~dispositions:[] ~added:[] ~provenance)
let literals () =
  let reference = C.Value_ref.make ~kind:C.Value_ref.Root ~id:"root" in
  let whole = C.Selection.make reference in
  let selected = C.Selection.make ~path:(literal_path [span 3 6; span 0 3]) reference in
  require (C.Selection.path whole = None) "Whole-selection constructor default differs";
  rejected "missing path default" "missing_field" (fun () -> C.Selection.of_json (obj (List.remove_assoc "path" (Json.object_fields (C.Selection.to_json whole)))));
  let concatenate = C.Operation.make (C.Operation.Concatenate [whole;whole]) in
  require (List.length (C.operation_selections concatenate) = 2) "Concatenation multiplicity lost";
  let rec selections = whole :: selections in
  rejected "cyclic selection spine" "molecular_resource_limit" (fun () -> C.Operation.make (C.Operation.Concatenate selections));
  let policy = R.Translation_policy.make ~profile:R.Translation_policy.Ordinary_cds () in
  let products = [C.Translation_product.make ~port_id:"z" ~input:selected ~policy; C.Translation_product.make ~port_id:"a" ~input:selected ~policy] in
  let multi = C.Operation.make (C.Operation.Multi_orf_translation products) in
  require (List.length (C.operation_selections multi) = 1) "Identical ORF selections were not deduplicated";
  require (C.Operation.product_ids multi = Some ["a";"z"]) "Named product inventory not canonical";
  let spans = match C.Selection.path (List.hd (C.operation_selections multi)) with None -> failwith "Lost ORF path" | Some path -> G.Path.spans path in
  require (List.map G.Span.start spans = [3;0]) "Ordered residue path was sorted";
  let rec products_cycle = List.hd products :: products_cycle in
  rejected "cyclic product spine" "molecular_resource_limit" (fun () -> C.Operation.make (C.Operation.Multi_orf_translation products_cycle));
  let conditional_policy = R.Translation_policy.make ~profile:R.Translation_policy.Conditional_cds
      ~recodings:[R.Codon_recoding.make ~codon_index:0 ~expected_triplet:"ACG" ~amino_acid:'U' ~condition:"readout"] () in
  let producing = C.Translation_branch.make ~id:"on" ~condition:"present" ~input:selected ~policy:(Some conditional_policy) ~port_id:(Some "output")
  and absent = C.Translation_branch.make ~id:"off" ~condition:"absent" ~input:whole ~policy:None ~port_id:None in
  let branches = C.Operation.make (C.Operation.Conditional_translation [producing;absent]) in
  require (C.Operation.conditions branches = ["absent";"present";"readout"]) "Conditions omitted branch or recoding authority";
  require (List.length (C.operation_selections branches) = 2) "No-product branch input was dropped";
  let step = C.Transform_step.make ~id:"step" ~operation:branches ~ports:[port "output"] ~assumptions:["readout";"present";"absent"] ~provenance in
  require (C.Transform_step.assumptions step = ["absent";"present";"readout"]) "Assumptions not canonical";
  rejected "missing exact assumption" "invalid_construction" (fun () -> C.Transform_step.make ~id:"step" ~operation:branches ~ports:[port "output"] ~assumptions:["readout";"present"] ~provenance);
  let rec ports = port "output" :: ports in
  rejected "cyclic port spine" "molecular_resource_limit" (fun () -> C.Transform_step.make ~id:"step" ~operation:branches ~ports ~assumptions:[] ~provenance);
  let rec assumptions = "x" :: assumptions in
  rejected "cyclic assumption spine" "molecular_resource_limit" (fun () -> C.Transform_step.make ~id:"step" ~operation:concatenate ~ports:[port "output"] ~assumptions ~provenance);
  let processing = C.Processing_product.make ~port_id:"output" ~path:(literal_path [span 0 3]) in
  let peptide = C.Peptide_product.make ~port_id:"output" ~residues:(span 0 1) in
  let all = [C.Operation.Slice whole; C.Operation.Concatenate [whole;whole]; C.Operation.Orientation {input=whole;action=C.Operation.Reverse_complement};
      C.Operation.Transcription selected; C.Operation.Rna_cleavage {input=whole;products=[processing]}; C.Operation.Rna_splicing {input=whole;products=[processing]};
      C.Operation.Protein_cleavage {input=whole;products=[processing]}; C.Operation.Protein_splicing {input=whole;products=[processing]};
      C.Operation.Circularization {input=whole;origin=1_000_000};
      C.Operation.Base_editing {input=whole;canonical_edits=[R.Canonical_edit.make ~position:0 ~expected:'A' ~replacement:'G'];chemical_edits=[]};
      C.Operation.Translation {input=selected;policy}; C.Operation.specification multi; C.Operation.specification branches;
      C.Operation.Ribosomal_skipping {input=selected;policy;products=[peptide];event_id="skip"}] |> List.map C.Operation.make in
  require (List.length (List.sort_uniq String.compare (List.map C.Operation.schema_version all)) = 14) "Literal operation census incomplete";
  List.iter (fun operation -> require (Json.equal (C.Operation.to_json operation) (C.Operation.to_json (C.Operation.of_json (C.Operation.to_json operation)))) "Operation roundtrip failed") all;
  rejected "selected processing input" "invalid_construction" (fun () -> C.Operation.make (C.Operation.Rna_cleavage {input=selected;products=[processing]}));
  rejected "fragmented cleavage" "invalid_construction" (fun () -> C.Operation.make (C.Operation.Rna_cleavage {input=whole;
      products=[C.Processing_product.make ~port_id:"output" ~path:(literal_path [span 0 1;span 2 3])]}));
  let rec edits = R.Canonical_edit.make ~position:0 ~expected:'A' ~replacement:'G' :: edits in
  rejected "cyclic edit spine" "molecular_resource_limit" (fun () -> C.Operation.make (C.Operation.Base_editing {input=whole;canonical_edits=edits;chemical_edits=[]}));
  let role = C.Role.make ~id:"role" ~role:"declared" ~purpose:Bioc_domain.Molecule.Role.Requested_payload ~compartment:"cytoplasm" in
  rejected "role category mismatch" "invalid_construction" (fun () -> C.Member_requirement.make ~id:"member" ~category:C.Member_requirement.Control
      ~subject:(C.Member_requirement.Materialized "member") ~roles:[role]);
  let rec roles = role :: roles in
  rejected "cyclic role spine" "molecular_resource_limit" (fun () -> C.Member_requirement.make ~id:"member" ~category:C.Member_requirement.Payload
      ~subject:(C.Member_requirement.Materialized "member") ~roles);
  let amount quantity = C.Amount_declaration.make ~id:"amount" ~subject_id:"member" ~preparation_id:"preparation" ~role_instance_ids:[] ~quantity ~unit:"fixture" ~provenance in
  let amounts = List.map amount [C.Amount_declaration.Integer Z.zero; C.Amount_declaration.Real 0.; C.Amount_declaration.Real (-0.)] in
  require (List.length (List.sort_uniq String.compare (List.map C.Amount_declaration.fingerprint amounts)) = 3) "Amount integer/float/signed-zero identity conflated";
  (* A valid child may be shared many times by a native caller. The parent must
     reject its aggregate before retaining an unbounded expanded inventory. *)
  let large_provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:(String.make 4000 'x') in
  let dispositions = List.init 100 (fun index -> T.Feature_disposition.make ~source_id:"root" ~feature_id:(string_of_int index)
      ~decision:T.Feature_disposition.Unknown ~outputs:[] ~provenance:large_provenance) in
  let transition = T.Feature.make ~dispositions ~added:[] ~provenance in
  let large_port = C.Product_port.make ~id:"large" ~space_id:"large.frame" ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition:(C.Product_port.chemistry_transition (port "base")) ~feature_transition:transition in
  rejected "aggregate repeated child" "molecular_resource_limit" (fun () -> C.Transform_step.make ~id:"step" ~operation:concatenate
      ~ports:(List.init 16 (fun _ -> large_port)) ~assumptions:[] ~provenance);
  print_endline "construction literals: all 14 typed operations, exact selections/conditions, numeric identity and bounded constructors passed"

let inspect kind raw =
  let basic json = json, obj ["fingerprint",str (Canonical.fingerprint json)] in
  match kind with
  | "root_source" -> C.Root_source.of_json raw |> C.Root_source.to_json |> basic
  | "value_ref" -> C.Value_ref.of_json raw |> C.Value_ref.to_json |> basic
  | "selection" -> C.Selection.of_json raw |> C.Selection.to_json |> basic
  | "product_port" -> C.Product_port.of_json raw |> C.Product_port.to_json |> basic
  | "processing_product" -> C.Processing_product.of_json raw |> C.Processing_product.to_json |> basic
  | "translation_product" -> C.Translation_product.of_json raw |> C.Translation_product.to_json |> basic
  | "translation_branch" -> C.Translation_branch.of_json raw |> C.Translation_branch.to_json |> basic
  | "peptide_product" -> C.Peptide_product.of_json raw |> C.Peptide_product.to_json |> basic
  | "transform_step" -> C.Transform_step.of_json raw |> C.Transform_step.to_json |> basic
  | "output_member" -> C.Output_member.of_json raw |> C.Output_member.to_json |> basic
  | "role" -> C.Role.of_json raw |> C.Role.to_json |> basic
  | "member_requirement" -> C.Member_requirement.of_json raw |> C.Member_requirement.to_json |> basic
  | "complex_constituent" -> C.Complex_constituent.of_json raw |> C.Complex_constituent.to_json |> basic
  | "complex_member" -> C.Complex_member.of_json raw |> C.Complex_member.to_json |> basic
  | "amount" -> C.Amount_declaration.of_json raw |> C.Amount_declaration.to_json |> basic
  | "request" -> C.Request.of_json raw |> C.Request.to_json |> basic
  | _ ->
      let value = C.Operation.of_json raw in
      require (C.Operation.name value = kind) "Unknown operation fixture kind";
      C.Operation.to_json value, obj ["fingerprint",str (C.Operation.fingerprint value);
        "selections",Json.Array (List.map C.Selection.to_json (C.operation_selections value));
        "conditions",Json.Array (List.map str (C.Operation.conditions value))]
let rec replace_at value path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove fixture root")
  | Json.String key :: tail ->
      let fields = Json.object_fields value in
      require (tail = [] && replacement <> None || List.mem_assoc key fields) "Absent fixture edit path";
      if tail = [] then obj (match replacement with None -> List.remove_assoc key fields | Some value -> (key,value) :: List.remove_assoc key fields)
      else obj (List.map (fun (name,child) -> name, if name = key then replace_at child tail replacement else child) fields)
  | Json.Int index :: tail ->
      let index = Z.to_int index and values = Json.array value in
      require (index >= 0 && index < List.length values) "Fixture index out of range";
      Json.Array (List.mapi (fun i child -> if i = index then (if tail = [] && replacement = None then None else Some (replace_at child tail replacement)) else Some child) values |> List.filter_map Fun.id)
  | _ -> failwith "Unknown fixture path component"
let apply_edits value edits = List.fold_left (fun value edit ->
    let replacement = match Json.string (field "op" edit) with "set" -> Some (field "value" edit) | "remove" -> None | _ -> failwith "Unknown fixture edit" in
    replace_at value (Json.array (field "path" edit)) replacement) value (Json.array edits)
let inventory keys cases = List.sort (fun a b -> String.compare (Json.string (field "id" a)) (Json.string (field "id" b))) cases
    |> List.map (fun item -> Json.Array (List.map (fun key -> field key item) keys)) |> fun values -> Canonical.fingerprint (Json.Array values)
let retained path =
  require (not (Filename.is_relative path)) "Construction corpus requires an absolute path";
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let bytes = in_channel_length channel in require (bytes <= Limits.max_request_bytes) "Construction corpus read budget";
      Json.parse (really_input_string channel bytes)) in
  require (field "schema_version" corpus = str "biocompiler.construction_conformance.v1") "Wrong construction corpus schema";
  let records = Json.array (field "records" corpus) and negatives = Json.array (field "rejections" corpus) in
  require (List.length records = 72 && List.length negatives = 245) "Construction corpus census changed";
  require (inventory ["id";"kind"] records = "52a3a22769118e29acbabe5982ad74c5beb32a1333e4b414937fbf12ee55ae1b") "Construction positive inventory changed";
  require (inventory ["id";"kind";"expected_code"] negatives = "06c50607b0bdf67a2e27396a91ccb1c4cd957c873cb9a25ffece0ac3b2c634d2") "Construction intended rejection inventory changed";
  require (Canonical.fingerprint (field "coverage" corpus) = "c8f2959ae407564867dfb4bfb1b25a14b220b4d0aa5e213c5e9cc965a6031d09") "Construction scope/coverage inventory changed";
  let ids = List.map (fun case -> Json.string (field "id" case)) (records @ negatives) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate construction fixture ID";
  let documents = field "documents" corpus in
  List.iter (fun case ->
      let id = Json.string (field "id" case) and digest = Json.string (field "document_id" case) in
      let document = field digest documents in require (Canonical.fingerprint document = digest) (id ^ ": source document hash differs");
      let actual, expected = inspect (Json.string (field "kind" case)) (apply_edits document (field "edits" case)) in
      require (Json.equal actual document) (id ^ ": normalized construction differs");
      require (Json.equal expected (field "expected" case)) (id ^ ": construction identity/semantics differs")) records;
  List.iter (fun case ->
      let document = field (Json.string (field "document_id" case)) documents in
      let raw = apply_edits document (field "edits" case) in
      rejected (Json.string (field "id" case)) (Json.string (field "expected_code" case)) (fun () -> inspect (Json.string (field "kind" case)) raw)) negatives;
  Printf.printf "construction: %d complete records, all 30 schemas/14 operations/3 case-B requests and %d intended rejections passed\n" (List.length records) (List.length negatives)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_;path] -> literals (); retained path
  | _ -> failwith "usage: test_construction.exe [<absolute-construction-corpus.json>]"
