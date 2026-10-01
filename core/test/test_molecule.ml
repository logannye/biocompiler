open Bioc_wire
module N = Bioc_domain.Molecule
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
module C = Bioc_domain.Molecule_chemistry
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code operation = match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Artificial native literal."
let chemical accession = C.Chemical_identity.make ~namespace:"biocompiler.chemical" ~accession ~version:"1"
let claim status = C.Claim.make ~status ~identity:(if status = C.Declared then Some (chemical "hydroxyl") else None) ~provenance
let coordinates identity length topology = G.Space.of_json (obj ["schema_version", str "biocompiler.molecule_coordinate_space.v0.1";
    "id", str identity; "alphabet", str "RNA"; "length", Json.int length; "topology", str topology; "axis", str "5prime_to_3prime"])
let path space start stop = G.Path.of_json (obj ["schema_version", str "biocompiler.molecule_coordinate_path.v0.1";
    "space_id", str (G.Space.id space |> G.Space_id.to_string); "strand", str "+";
    "spans", Json.Array [obj ["schema_version", str "biocompiler.molecule_index_span.v0.1"; "start", Json.int start; "end", Json.int stop]]])
let molecule ?(topology = "linear") ?(modifications = []) sequence =
  let length = String.length sequence in
  let space = coordinates "literal" length topology and source = coordinates "source" length "linear" in
  let circular = topology = "circular" in
  let chemistry = C.make ~cap:(claim (if circular then C.Inapplicable else C.Absent))
      ~start_end:(claim (if circular then C.Inapplicable else C.Declared))
      ~finish_end:(claim (if circular then C.Inapplicable else C.Declared)) ~modifications
      ~modification_inventory_status:C.Declared ~modification_inventory_provenance:provenance
      ~terminal_tail:(if circular then C.Tail.make ~status:C.Inapplicable ~placement:None ~length:None ~path:None ~provenance
        else C.Tail.make ~status:C.Declared ~placement:(Some C.Tail.Absent_tail)
          ~length:(Some (C.Tail_length.make (C.Tail_length.Exact 0))) ~path:None ~provenance) in
  let origin = N.Assembly_origin.make ~id:"origin" ~destination:(path space 0 length) ~source_space:source ~source_path:(path source 0 length) ~provenance in
  N.make ~id:"literal" ~form:N.Delivered_rna ~space ~sequence ~sequence_extent:C.Complete ~coding_status:N.Unknown
    ~assembly:[origin] ~features:[] ~chemistry ~provenance
let literals () =
  let value = molecule "ACGU" in
  require (N.spelling_identity value = "dd73f322ba91ede79b4469fcf7ff2f58d2853405f6cd9d078aba4cb5458df08e") "Independent spelling digest differs";
  let coverage value = field "known_coverage_identity" (field "modifications" (field "chemistry" (N.nominal_json value))) in
  require (coverage value = str "f15dee373707f437f74afdfbb3e9c7b43e0e527e39cf2afcd2a787ad503526f4") "Empty positioned chemistry separator differs";
  require (N.declared_nominal_complete value && N.complete_nominal_identity value <> None) "Unknown provenance changed chemical completeness";
  require (N.base_rotation_identity value = None) "Linear molecule acquired rotation identity";
  let modification positions = C.Modification.make ~id:"sites" ~identity:(chemical "inosine") ~canonical_base:'A'
      ~scope:C.Modification.Positions ~positions ~provenance in
  let sequence = "A" ^ String.make 255 'C' ^ "A" in
  require (coverage (molecule ~modifications:[modification [0;256]] sequence)
      = str "4b1cd83f362497739ac3d153077a39e728c24b679b921c3c19de4b4428dc3e2c") "Independent eight-byte big-endian coverage witness differs";
  let circle = molecule ~topology:"circular" "CGUAAC" in
  require (N.base_rotation_identity circle = Some "c6b225c08ae0b513c3f8b0176200349d670a8d4ab3ff5abf87ce86596669afa5") "Independent circular least rotation differs";
  require (N.sequence circle = "CGUAAC") "Rotation identity rewrote stored origin";
  let feature = N.Feature.make ~id:"feature" ~kind:"unknown" ~path:None ~provenance () in
  require (N.Feature.reading_frame feature = None) "Feature constructor default differs";
  rejected "omitted feature default" "missing_field" (fun () -> N.Feature.of_json (obj (List.remove_assoc "reading_frame" (Json.object_fields (N.Feature.to_json feature)))));
  let rec features = feature :: features in
  rejected "cyclic feature spine" "molecular_resource_limit" (fun () -> N.make ~id:"literal" ~form:N.Delivered_rna ~space:(N.space value)
      ~sequence:"ACGU" ~sequence_extent:C.Complete ~coding_status:N.Unknown ~assembly:(N.assembly value) ~features ~chemistry:(N.chemistry value) ~provenance);
  let rec origins = List.hd (N.assembly value) :: origins in
  rejected "cyclic assembly spine" "molecular_resource_limit" (fun () -> N.make ~id:"literal" ~form:N.Delivered_rna ~space:(N.space value)
      ~sequence:"ACGU" ~sequence_extent:C.Complete ~coding_status:N.Unknown ~assembly:origins ~features:[] ~chemistry:(N.chemistry value) ~provenance);
  let constituent = N.Constituent.make ~molecule_id:(N.id value) ~molecule_fingerprint:(N.fingerprint value) ~stoichiometry:(Some 1) ~provenance in
  rejected "single-copy alias" "invalid_molecular_complex" (fun () -> N.Complex.make ~id:"alias" ~kind:N.Complex.Rna_complex ~constituents:[constituent] ~provenance);
  let rec constituents = constituent :: constituents in
  rejected "cyclic constituent spine" "molecular_resource_limit" (fun () -> N.Complex.make ~id:"cycle" ~kind:N.Complex.Rna_complex ~constituents ~provenance);
  print_endline "molecule literals: spelling, streamed chemical coverage, circular identity, defaults and bounded constructors passed"

let kinds = ["assembly_origin"; "feature"; "molecule"; "constituent"; "complex"; "role"; "mapping"]
let inspect kind raw =
  let basic json = json, obj ["fingerprint", str (Canonical.fingerprint json)] in
  match kind with
  | "assembly_origin" -> N.Assembly_origin.of_json raw |> N.Assembly_origin.to_json |> basic
  | "feature" -> N.Feature.of_json raw |> N.Feature.to_json |> basic
  | "constituent" -> N.Constituent.of_json raw |> N.Constituent.to_json |> basic
  | "complex" -> N.Complex.of_json raw |> N.Complex.to_json |> basic
  | "role" -> N.Role.of_json raw |> N.Role.to_json |> basic
  | "mapping" -> N.Form_mapping.of_json raw |> N.Form_mapping.to_json |> basic
  | "molecule" ->
      let value = N.of_json raw in
      let optional = function None -> Json.Null | Some value -> str value in
      N.to_json value, obj ["fingerprint", str (N.fingerprint value); "spelling_identity", str (N.spelling_identity value);
        "nominal", N.nominal_json value; "declared_nominal_identity", str (N.declared_nominal_identity value);
        "declared_nominal_complete", Json.Bool (N.declared_nominal_complete value);
        "complete_nominal_identity", optional (N.complete_nominal_identity value); "base_rotation_identity", optional (N.base_rotation_identity value)]
  | _ -> failwith "Unknown molecule test record kind"
let rec replace_at value path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove fixture root")
  | Json.String key :: tail ->
      let fields = Json.object_fields value in
      require (tail = [] && replacement <> None || List.mem_assoc key fields) "Fixture edit has an absent object path";
      if tail = [] then obj (match replacement with None -> List.remove_assoc key fields
          | Some value -> (key, value) :: List.remove_assoc key fields)
      else obj (List.map (fun (name, child) -> name, if name = key then replace_at child tail replacement else child) fields)
  | Json.Int index :: tail ->
      let index = Z.to_int index in
      let values = Json.array value in
      require (index >= 0 && index < List.length values) "Fixture edit index out of range";
      Json.Array (List.mapi (fun i child -> if i = index then (if tail = [] && replacement = None then None else Some (replace_at child tail replacement)) else Some child) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid fixture edit path"
let apply_edits value edits = List.fold_left (fun value edit ->
    let replacement = match Json.string (field "op" edit) with "set" -> Some (field "value" edit)
      | "remove" -> None | _ -> failwith "Unknown fixture edit operation" in
    replace_at value (Json.array (field "path" edit)) replacement) value (Json.array edits)
let check_inventory corpus records negatives =
  let inventory keys cases = List.map (fun item -> Json.Array (List.map (fun key -> field key item) keys)) cases
      |> List.sort (fun left right -> String.compare
          (Json.string (List.hd (Json.array left))) (Json.string (List.hd (Json.array right))))
      |> fun values -> Canonical.fingerprint (Json.Array values) in
  require (inventory ["id"; "kind"] records = "ebe9245b2ca4f0919e7d7733d1fe684c75350cffcbff186a0f31a93a1818a31b")
    "Missing or substituted molecule case inventory";
  require (inventory ["id"; "kind"; "expected_code"] negatives = "40386f7ff68cd4f5bd09dc018fe86785ff74c482490f3c5d4607007a4806190f")
    "Missing or substituted molecule rejection/diagnostic inventory";
  let relations = Json.array (field "relations" corpus) |> List.sort (fun left right ->
      Stdlib.compare (Json.string (field "left" left), Json.string (field "right" left))
        (Json.string (field "left" right), Json.string (field "right" right))) in
  require (Canonical.fingerprint (Json.Array relations) = "7c1b51c1d264194cf5911b58ecf634d82ccf37d65ab2a187cba1ff69d0ae3ebe")
    "Missing or substituted molecule identity relation inventory"
let retained path =
  require (not (Filename.is_relative path)) "Molecule corpus path must be absolute";
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let bytes = in_channel_length channel in require (bytes <= Limits.max_request_bytes) "Molecule corpus read bound";
      Json.parse (really_input_string channel bytes)) in
  require (field "schema_version" corpus = str "biocompiler.molecules_conformance.v1") "Unknown molecule corpus";
  let records = Json.array (field "records" corpus) and negatives = Json.array (field "rejections" corpus) in
  require (List.length records = 109 && List.length negatives = 136) "Incomplete molecule corpus";
  check_inventory corpus records negatives;
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ negatives) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate molecule fixture identity";
  let documents = field "documents" corpus and results = Hashtbl.create 128 in
  let checked = ref 0 and rejected_count = ref 0 in
  List.iter (fun case -> let kind = Json.string (field "kind" case) in if List.mem kind kinds then (
      let identity = Json.string (field "id" case) in
      let digest = Json.string (field "document_id" case) in
      let document = field digest documents in
      require (Canonical.fingerprint document = digest) "Molecule fixture document pin differs";
      let actual, summary = inspect kind (apply_edits document (field "edits" case)) in
      require (Json.equal actual document) (identity ^ ": normalized molecular record differs");
      require (Json.equal summary (field "expected" case)) (identity ^ ": molecular identities differ");
      Hashtbl.add results identity summary; incr checked)) records;
  List.iter (fun case -> let kind = Json.string (field "kind" case) in if List.mem kind kinds then (
      let document = field (Json.string (field "document_id" case)) documents in
      let raw = apply_edits document (field "edits" case) in
      rejected (Json.string (field "id" case)) (Json.string (field "expected_code" case)) (fun () -> inspect kind raw);
      incr rejected_count)) negatives;
  List.iter (fun relation ->
      match Hashtbl.find_opt results (Json.string (field "left" relation)), Hashtbl.find_opt results (Json.string (field "right" relation)) with
      | Some left, Some right ->
          List.iter (fun key -> let key = Json.string key in require (Json.equal (field key left) (field key right)) "Molecule identity equality relation differs") (Json.array (field "equal" relation));
          List.iter (fun key -> let key = Json.string key in require (not (Json.equal (field key left) (field key right))) "Molecule identity inequality relation differs") (Json.array (field "different" relation))
      | None, None -> () | _ -> failwith "Cross-domain relation requires explicit test ownership") (Json.array (field "relations" corpus));
  require (!checked = 72 && !rejected_count = 92) "Missing M03 schema or mutation coverage";
  Printf.printf "molecules: %d complete records and %d intended rejections passed\n" !checked !rejected_count
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "usage: test_molecule.exe [<absolute-molecules-corpus.json>]"
