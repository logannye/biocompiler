open Bioc_wire
module S = Bioc_domain.Molecule_set
module N = Bioc_domain.Molecule
module M = Bioc_domain.Molecular_record
module A = S.Amount
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code operation = match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Artificial native quantity."
let amount ?(roles = []) quantity = A.make ~id:"amount" ~subject_id:"molecule" ~subject_fingerprint:(String.make 64 'a')
    ~preparation_id:"preparation" ~role_instance_ids:roles ~quantity ~unit:"fixture_unit" ~provenance
let literals () =
  let maximum = Z.pred (Z.shift_left Z.one 1024) in
  let large = amount (A.Integer maximum) in
  require (field "quantity" (A.to_json large) = Json.Int maximum) "Amount was coerced to binary64";
  rejected "amount bit bound" "invalid_experimental_amount" (fun () -> amount (A.Integer (Z.succ maximum)));
  rejected "negative amount" "invalid_experimental_amount" (fun () -> amount (A.Integer Z.minus_one));
  rejected "nonfinite amount" "nonfinite_number" (fun () -> amount (A.Real Float.infinity));
  let identities = List.map (fun quantity -> A.fingerprint (amount quantity)) [A.Unknown; A.Integer Z.zero; A.Real 0.; A.Real (-0.)] in
  require (List.length (List.sort_uniq String.compare identities) = 4) "Unknown, integer zero, floating zero and signed zero collapsed";
  require (A.role_instance_ids (amount ~roles:["z"; "a"] A.Unknown) = ["a"; "z"]) "Amount role normalization differs";
  rejected "duplicate amount role" "invalid_experimental_amount" (fun () -> amount ~roles:["a"; "a"] A.Unknown);
  let rec roles = "a" :: roles in
  rejected "cyclic amount role spine" "molecular_resource_limit" (fun () -> amount ~roles A.Unknown);
  print_endline "molecular amount literals: independent integer/float/null identity, 1024-bit boundary and bounded role lists passed"

let kinds = ["set"; "amount"; "artifact"]
let inspect kind raw = match kind with
  | "amount" -> let value = A.of_json raw in A.to_json value, obj ["fingerprint", str (A.fingerprint value)]
  | "set" ->
      let value = S.of_json raw in
      let ids = List.map N.id (S.molecules value) @ List.map N.Complex.id (S.complexes value) in
      let subjects = obj (List.map (fun identity -> identity, obj ["nominal", str (S.subject_nominal_identity value identity);
          "complete", Json.Bool (S.subject_complete value identity)]) ids) in
      S.to_json value, obj ["fingerprint", str (S.fingerprint value); "declared_nominal_complete", Json.Bool (S.declared_nominal_complete value);
          "declared_nominal_bundle_identity", str (S.declared_nominal_bundle_identity value); "subjects", subjects]
  | "artifact" ->
      let value = S.Artifact.of_json raw in
      S.Artifact.to_json value, obj ["fingerprint", str (S.Artifact.fingerprint value);
          "nominal_bundle_identity", str (S.Artifact.nominal_bundle_identity value);
          "experimental_specification_identity", str (S.Artifact.experimental_specification_identity value);
          "artifact_fingerprint", str (S.Artifact.artifact_fingerprint value)]
  | _ -> failwith "Unknown molecular set test record kind"
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
  let documents = field "documents" corpus and results = Hashtbl.create 64 in
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
  require (!checked = 37 && !rejected_count = 44) "Missing M04 schema or mutation coverage";
  let fixture identity =
    let case = List.find (fun item -> field "id" item = str identity) records in
    field (Json.string (field "document_id" case)) documents in
  let bundle = S.of_json (fixture "set/plain") in
  rejected "unknown nominal subject" "unknown_molecular_subject" (fun () -> S.subject_nominal_identity bundle "missing");
  rejected "unknown subject completeness" "unknown_molecular_subject" (fun () -> S.subject_complete bundle "missing");
  let rec cyclic_molecules = List.hd (S.molecules bundle) :: cyclic_molecules in
  rejected "cyclic set molecule spine" "molecular_resource_limit" (fun () -> S.make ~id:"cyclic" ~request:(S.request bundle)
      ~molecules:cyclic_molecules ~complexes:[] ~role_instances:(S.role_instances bundle) ~form_mappings:[]);
  let artifact = S.Artifact.of_json (fixture "artifact/plain") in
  let rec amounts = List.hd (S.Artifact.experimental_amounts artifact) :: amounts in
  rejected "cyclic artifact amount spine" "molecular_resource_limit" (fun () -> S.Artifact.make ~bundle ~experimental_amounts:amounts ~run_metadata:[]);
  let rec metadata = ("cycle", Json.Null) :: metadata in
  rejected "cyclic metadata spine" "molecular_resource_limit" (fun () -> S.Artifact.make ~bundle ~experimental_amounts:[] ~run_metadata:metadata);
  let rec cyclic_value = Json.Array [cyclic_value] in
  rejected "cyclic metadata value" "molecular_cycle" (fun () -> S.Artifact.make ~bundle ~experimental_amounts:[] ~run_metadata:["cycle", cyclic_value]);
  let full = S.Artifact.of_json (fixture "artifact/full_example") |> S.Artifact.bundle in
  require (List.length (S.molecules full) = 8 && List.length (S.complexes full) = 1 && List.length (S.role_instances full) = 10) "Original wrapped molecular example was narrowed";
  Printf.printf "molecule sets: %d complete records and %d intended rejections; original wrapped example and bounded native constructors passed\n" !checked !rejected_count
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "usage: test_molecule_set.exe [<absolute-molecules-corpus.json>]"
