open Bioc_wire
module C = Bioc_domain.Molecule_chemistry
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
let require condition message = if not condition then failwith message
let field name value = Json.field name (Json.object_fields value)
let str value = Json.String value
let rejected label code operation = match operation () with
  | () -> failwith (label ^ ": intended chemistry rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Artificial software chemistry."
let chemical accession = C.Chemical_identity.make ~namespace:"biocompiler.chemical" ~accession ~version:"1"
let claim status = C.Claim.make ~status ~identity:(if status = C.Declared then Some (chemical "hydroxyl") else None) ~provenance
let absent_tail () = C.Tail.make ~status:C.Declared ~placement:(Some C.Tail.Absent_tail)
    ~length:(Some (C.Tail_length.make (C.Tail_length.Exact 0))) ~path:None ~provenance
let chemistry ?(modifications = []) () = C.make ~cap:(claim C.Absent) ~start_end:(claim C.Declared)
    ~finish_end:(claim C.Declared) ~modifications ~modification_inventory_status:C.Declared
    ~modification_inventory_provenance:provenance ~terminal_tail:(absent_tail ())
let space () = G.Space.of_json (Json.parse {|{"schema_version":"biocompiler.molecule_coordinate_space.v0.1","id":"molecule","alphabet":"RNA","length":4,"topology":"linear","axis":"5prime_to_3prime"}|})
let literals () =
  let value = chemistry () in
  C.validate_for value (space ()) ~sequence:"ACGU" ~sequence_extent:C.Complete;
  require (C.declared_nominal_complete value) "Unknown provenance prevented complete declared chemistry";
  let modification = C.Modification.make ~id:"inosine" ~identity:(chemical "inosine") ~canonical_base:'A'
      ~scope:C.Modification.Positions ~positions:[0] ~provenance in
  C.validate_for (chemistry ~modifications:[modification] ()) (space ()) ~sequence:"ACGU" ~sequence_extent:C.Complete;
  rejected "literal spelling" "invalid_chemistry" (fun () -> C.validate_for (chemistry ~modifications:[modification] ())
      (space ()) ~sequence:"GCGU" ~sequence_extent:C.Complete);
  rejected "wrong parent" "invalid_chemistry" (fun () -> ignore (C.Modification.make ~id:"wrong" ~identity:(chemical "inosine")
      ~canonical_base:'G' ~scope:C.Modification.Positions ~positions:[0] ~provenance));
  rejected "uncertain length" "invalid_chemistry" (fun () -> ignore (C.Tail_length.make (C.Tail_length.Bounded (3,3))));
  require (not (C.Chemical_identity.declared_nominal_complete (chemical "unknown"))) "Unknown identity became complete";
  let nominal = C.Modification.nominal_json modification in
  require (field "canonical_base" nominal = str "A") "Chemical modification rewrote canonical parent";
  require (not (List.mem_assoc "id" (Json.object_fields nominal)) && not (List.mem_assoc "provenance" (Json.object_fields nominal))) "Nominal modification retained archival metadata";
  let reordered = C.Modification.make ~id:"positions" ~identity:(chemical "inosine") ~canonical_base:'A'
      ~scope:C.Modification.Positions ~positions:[7;0;4] ~provenance in
  require (C.Modification.positions reordered = [0;4;7]) "Position normalization lost order contract";
  let rec positions_spine = 0 :: positions_spine in
  rejected "cyclic position list" "molecular_resource_limit" (fun () -> ignore (C.Modification.make
      ~id:"cyclic" ~identity:(chemical "inosine") ~canonical_base:'A' ~scope:C.Modification.Positions
      ~positions:positions_spine ~provenance));
  let rec modifications_spine = modification :: modifications_spine in
  rejected "cyclic modification list" "molecular_resource_limit" (fun () -> ignore (chemistry ~modifications:modifications_spine ()));
  print_endline "molecule chemistry: literal parent spelling, completeness, metadata and bounded declaration cases passed"

let inspect kind raw =
  let complete value = Json.Bool value in
  match kind with
  | "provenance" -> let value = M.Provenance.of_json raw in M.Provenance.to_json value, Json.Null, Json.Null
  | "chemical_identity" -> let value = C.Chemical_identity.of_json raw in C.Chemical_identity.to_json value, C.Chemical_identity.nominal_json value, complete (C.Chemical_identity.declared_nominal_complete value)
  | "claim" -> let value = C.Claim.of_json raw in C.Claim.to_json value, C.Claim.nominal_json value, complete (C.Claim.declared_nominal_complete value)
  | "modification" -> let value = C.Modification.of_json raw in C.Modification.to_json value, C.Modification.nominal_json value, Json.Null
  | "tail_length" -> let value = C.Tail_length.of_json raw in C.Tail_length.to_json value, C.Tail_length.nominal_json value, Json.Null
  | "tail" -> let value = C.Tail.of_json raw in C.Tail.to_json value, C.Tail.nominal_json value, complete (C.Tail.declared_nominal_complete value)
  | "chemistry" -> let value = C.of_json raw in C.to_json value, C.nominal_json value, complete (C.declared_nominal_complete value)
  | _ -> failwith ("Unknown chemistry record kind " ^ kind)
let retained path =
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Chemistry corpus exceeds read bound";
      Json.parse (really_input_string channel size)) in
  require (field "schema_version" corpus = str "biocompiler.molecule_chemistry_conformance.v1") "Unknown chemistry corpus schema";
  let records = Json.array (field "records" corpus) and rejections = Json.array (field "rejections" corpus)
  and validations = Json.array (field "validations" corpus) in
  require (List.length records = 47 && List.length rejections = 82 && List.length validations = 29) "Missing required molecular chemistry corpus cases";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ rejections @ validations) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate molecular chemistry fixture identity";
  let kinds = List.map (fun item -> Json.string (field "kind" item)) records |> List.sort_uniq String.compare in
  require (kinds = ["chemical_identity"; "chemistry"; "claim"; "modification"; "provenance"; "tail"; "tail_length"]) "Missing supported chemistry record kind";
  List.iter (fun item ->
      let label = Json.string (field "id" item) in
      let normalized, nominal, complete = inspect (Json.string (field "kind" item)) (field "input" item) in
      require (Json.equal normalized (field "normalized" item)) (label ^ ": normalization differs");
      require (str (Canonical.fingerprint normalized) = field "fingerprint" item) (label ^ ": fingerprint differs");
      require (Json.equal nominal (field "nominal" item)) (label ^ ": nominal content differs");
      require (complete = field "declared_nominal_complete" item) (label ^ ": nominal completeness differs")) records;
  List.iter (fun item -> rejected (Json.string (field "id" item)) (Json.string (field "expected_code" item))
      (fun () -> ignore (inspect (Json.string (field "kind" item)) (field "input" item)))) rejections;
  List.iter (fun item ->
      let identity = Json.string (field "chemistry_id" item) in
      let source = List.find (fun item -> field "id" item = str identity) records in
      let chemistry = C.of_json (field "normalized" source) and space = G.Space.of_json (field "space" item) in
      let extent = match Json.string (field "sequence_extent" item) with
        | "complete" -> C.Complete | "exact_core" -> C.Exact_core | _ -> failwith "Unknown fixture sequence extent" in
      let run () = C.validate_for chemistry space ~sequence:(Json.string (field "sequence" item)) ~sequence_extent:extent in
      match field "expected_code" item with
      | Json.Null -> run ()
      | code -> rejected (Json.string (field "id" item)) (Json.string code) run) validations;
  Printf.printf "molecule chemistry: %d records, %d decoder failures and %d molecular-context checks passed\n"
    (List.length records) (List.length rejections) (List.length validations)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_molecule_chemistry.exe [required-corpus.json]"
