open Bioc_wire
module P = Bioc_domain.Payload_structure
module S = Bioc_domain.Molecule_set
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
module C = Bioc_checker.Payload_structure_check
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let str value = Json.String value
let strings values = Json.Array (List.map str values)
let result_json (result : C.result) = Json.Object ["diagnostics", strings result.diagnostics; "unsupported", strings result.unsupported]
let expect label diagnostics unsupported (actual : C.result) =
  require (actual.diagnostics = diagnostics && actual.unsupported = unsupported)
    (label ^ ": expected diagnostic/unsupported pair differs: " ^ Canonical.encode (result_json actual))
let invalid_contracts = ["payload_contract_inventory_invalid"]
let invalid_bundle = ["payload_bundle_invalid"]
let unknown_provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Independent native declaration; no empirical authority."
let native_contract () = P.make ~member_id:"payload" ~form:P.Delivered_rna ~topology:G.Linear
    ~regions:[P.Region.make ~feature_id:"feature" ~kind:"supplied_label"] ~provenance:unknown_provenance
let literals () =
  expect "empty authority before invalid bundle" invalid_bundle ["payload_authority_missing"]
    (C.check_json ~contracts:(Json.Array []) ~bundle:Json.Null);
  expect "null authority before invalid bundle" invalid_bundle ["payload_authority_missing"]
    (C.check_json ~contracts:Json.Null ~bundle:Json.Null);
  let contract = P.to_json (native_contract ()) in
  expect "known inventory before invalid bundle" invalid_bundle []
    (C.check_json ~contracts:(Json.Array [contract]) ~bundle:Json.Null);
  expect "duplicate authority before invalid bundle" invalid_contracts []
    (C.check_json ~contracts:(Json.Array [contract; contract]) ~bundle:Json.Null);
  expect "object is not serialized contract inventory" invalid_contracts []
    (C.check_json ~contracts:(Json.Object ["payload", contract]) ~bundle:Json.Null);
  expect "over-limit inventory before invalid bundle" invalid_contracts []
    (C.check_json ~contracts:(Json.Array (List.init 65 (fun _ -> contract))) ~bundle:Json.Null);
  let rec spine = contract :: spine in
  expect "cyclic raw inventory spine" invalid_contracts []
    (C.check_json ~contracts:(Json.Array spine) ~bundle:Json.Null);
  let rec raw = Json.Array [raw] in
  expect "cyclic raw contract value" invalid_contracts []
    (C.check_json ~contracts:(Json.Array [raw]) ~bundle:Json.Null);
  expect "cyclic raw bundle value" invalid_bundle []
    (C.check_json ~contracts:(Json.Array [contract]) ~bundle:raw);
  let rec fields = ("unknown", Json.Null) :: fields in
  expect "cyclic raw bundle map spine" invalid_bundle []
    (C.check_json ~contracts:(Json.Array [contract]) ~bundle:(Json.Object fields));
  let duplicate = Json.Object (("member_id", str "different") :: Json.object_fields contract) in
  expect "duplicate raw contract key" invalid_contracts []
    (C.check_json ~contracts:(Json.Array [duplicate]) ~bundle:Json.Null);
  expect "nonfinite raw contract" invalid_contracts []
    (C.check_json ~contracts:(Json.Array [Json.Float Float.nan]) ~bundle:Json.Null);
  let invalid_utf8 = Json.Object (("member_id", str "\255") :: List.remove_assoc "member_id" (Json.object_fields contract)) in
  expect "invalid native UTF-8 contract" invalid_contracts []
    (C.check_json ~contracts:(Json.Array [invalid_utf8]) ~bundle:Json.Null);
  print_endline "payload checker: 13 independent invalid-boundary, precedence and native resource literals passed"

let inventory cases corpus =
  let row item = Json.Array [field "id" item; field "bundle_document" item;
      str (Canonical.fingerprint (field "contracts" item)); field "expected" item;
      field "source_fingerprint" item; field "original_bundle_document" item; field "boundary" item] in
  let rows = List.map row cases |> List.sort (fun left right ->
      String.compare (Json.string (List.hd (Json.array left))) (Json.string (List.hd (Json.array right)))) in
  Canonical.fingerprint (Json.Object ["cases", Json.Array rows;
      "api_boundary", field "api_boundary" corpus; "coverage", field "coverage" corpus])
let retained path =
  require (not (Filename.is_relative path)) "Payload checker corpus path must be absolute";
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in
      require (size <= Limits.max_request_bytes) "Payload checker corpus exceeds read budget";
      Json.parse (really_input_string channel size)) in
  require (field "schema_version" corpus = str "biocompiler.payload_structure_check_conformance.v1") "Unknown payload checker corpus";
  let cases = Json.array (field "cases" corpus) and documents = Json.object_fields (field "documents" corpus) in
  require (List.length cases = 99 && List.length documents = 48) "Incomplete payload checker corpus";
  let digest = "329fee52707d64ffa448bf5e54ad3ee2688f9e0d5c6ad38b5df41817af20892d" in
  require (inventory cases corpus = digest && field "inventory_sha256" corpus = str digest)
    "Missing or substituted full payload checker input/expected/scope inventory";
  let ids = List.map (fun item -> Json.string (field "id" item)) cases in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate payload checker case";
  List.iter (fun (identity, raw) -> require (Canonical.fingerprint raw = identity) "Payload checker document digest differs") documents;
  let used = Hashtbl.create 64 and typed_count = ref 0 and mutations = ref 0 in
  let document value = let identity = Json.string value in Hashtbl.replace used identity (); Json.field identity documents in
  List.iter (fun case ->
      let identity = Json.string (field "id" case) in
      let raw = document (field "bundle_document" case) in
      let contracts = field "contracts" case in
      let expected = field "expected" case in
      let before = Canonical.encode raw in
      let result = C.check_json ~contracts ~bundle:raw in
      require (Canonical.encode (result_json result) = Canonical.encode expected) (identity ^ ": fresh JSON check differs");
      require (Canonical.encode raw = before) (identity ^ ": checker mutated original authority");
      let source = match raw with
        | Json.Object fields -> (match List.assoc_opt "request" fields with None -> Json.Null | Some source -> str (Canonical.fingerprint source))
        | _ -> Json.Null in
      require (source = field "source_fingerprint" case) (identity ^ ": complete original source identity differs");
      (match field "original_bundle_document" case with
       | Json.Null -> ()
       | original_id ->
           let original = document original_id in
           require (Canonical.encode (field "request" raw) = Canonical.encode (field "request" original)) (identity ^ ": candidate mutation changed source authority");
           require (field "bundle_document" case <> original_id) (identity ^ ": candidate mutation is a no-op");
           incr mutations);
      match Json.string (field "boundary" case) with
      | "serialized_import" -> ()
      | "typed_and_serialized" ->
          let bundle = S.of_json raw in
          let source_before = Bioc_domain.Circuit_request.fingerprint (S.request bundle) in
          let contracts = match contracts with Json.Null -> [] | raw -> List.map P.of_json (Json.array raw) in
          require (Canonical.encode (result_json (C.check ~contracts ~bundle)) = Canonical.encode expected)
            (identity ^ ": fresh typed check differs");
          require (Bioc_domain.Circuit_request.fingerprint (S.request bundle) = source_before)
            (identity ^ ": typed checker mutated source authority");
          incr typed_count
      | _ -> failwith "Unknown payload checker boundary") cases;
  require (Hashtbl.length used = List.length documents) "Unreferenced payload checker document";
  require (!typed_count = 55 && !mutations = 27) "Payload checker boundary or mutation coverage changed";
  let base = List.find (fun item -> field "id" item = str "modality/delivered_rna/linear") cases in
  let bundle = S.of_json (document (field "bundle_document" base)) in
  let contracts = List.map P.of_json (Json.array (field "contracts" base)) in
  expect "independent supplied whole-bundle success" [] [] (C.check ~contracts ~bundle);
  expect "independent missing source contracts" [] ["payload_authority_missing"; "payload_authority_missing:payload"]
    (C.check ~contracts:[] ~bundle);
  let first = List.hd contracts in
  expect "independent typed duplicate contracts" invalid_contracts [] (C.check ~contracts:[first; first] ~bundle);
  let rec cyclic = first :: cyclic in
  expect "independent typed cyclic contract spine" invalid_contracts [] (C.check ~contracts:cyclic ~bundle);
  Printf.printf "payload checker: %d whole-input literal expected pairs, %d typed checks, %d original-source-preserving mutations and 4 independent supplied-bundle checks passed\n"
    (List.length cases) !typed_count !mutations
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_payload_structure_check.exe [<absolute-corpus.json>]"
