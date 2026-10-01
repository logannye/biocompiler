open Bioc_wire
module P = Bioc_domain.Payload_structure
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let reject label code action = match action () with
  | _ -> failwith (label ^ ": invalid declaration accepted")
  | exception Diagnostic.Error error -> require (error.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ error.code)
let literal () =
  let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"No empirical authority." in
  let a = P.Region.make ~feature_id:"a" ~kind:"supplied_label"
  and z = P.Region.make ~feature_id:"z" ~kind:"supplied_label" in
  let make regions = P.make ~member_id:"payload" ~form:P.Delivered_rna ~topology:G.Circular ~regions ~provenance in
  let value = make [z; a] in
  require (List.map P.Region.feature_id (P.regions value) = ["a"; "z"])
    "Required inventory ordering was confused with geometric order";
  require (P.fingerprint value = P.fingerprint (make [a; z])) "Inventory permutation changed identity";
  require (M.Provenance.status (P.provenance value) = M.Provenance.Unknown) "Unknown provenance was rejected or promoted";
  require (P.alphabet P.Delivered_rna = G.Rna && P.alphabet P.Delivered_dna = G.Dna) "Declared modality alphabet changed";
  require (P.max_regions = 256 && P.max_contracts = 64) "Payload inventory bounds changed";
  reject "empty required inventory" "invalid_payload_structure" (fun () -> make []);
  reject "duplicate feature identity" "invalid_payload_structure" (fun () -> make [a; a]);
  reject "bounded native region list" "molecular_resource_limit" (fun () ->
      let rec regions = a :: regions in make regions);
  reject "cyclic raw value" "molecular_cycle" (fun () -> let rec raw = Json.Array [raw] in P.of_json raw);
  reject "cyclic object spine" "molecular_resource_limit" (fun () ->
      let rec fields = ("x", Json.Null) :: fields in P.of_json (Json.Object fields));
  reject "invalid UTF-8 native text" "invalid_utf8" (fun () -> P.Region.make ~feature_id:"\255" ~kind:"k");
  print_endline "payload structure literals: ordering, unknown authority, modalities and native resource bounds passed"

let inventory corpus =
  let rows keys name = Json.array (field name corpus)
      |> List.map (fun item -> Json.Array (List.map (fun key -> field key item) keys))
      |> List.sort (fun a b -> String.compare (Json.string (List.hd (Json.array a))) (Json.string (List.hd (Json.array b))))
      |> fun values -> Json.Array values in
  Canonical.fingerprint (Json.Object ["records", rows ["id"; "kind"] "records";
      "rejections", rows ["id"; "kind"; "expected_code"] "rejections"])
let retained path =
  require (not (Filename.is_relative path)) "Payload structure corpus path must be absolute";
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= 300_000) "Payload corpus exceeds read budget";
      Json.parse (really_input_string channel size)) in
  require (field "schema_version" corpus = Json.String "biocompiler.payload_structure_conformance.v1") "Unknown payload corpus";
  let expected = "34f60cd9057611341e84ab3572af9839fd7817791496507684d007e590637094" in
  require (inventory corpus = expected && field "inventory_sha256" corpus = Json.String expected)
    "Payload case or intended diagnostic inventory changed";
  let records = Json.array (field "records" corpus) and negatives = Json.array (field "rejections" corpus) in
  require (List.length records = 14 && List.length negatives = 44) "Incomplete payload corpus";
  let decode item = match Json.string (field "kind" item) with
    | "region" -> P.Region.to_json (P.Region.of_json (field "input" item))
    | "contract" -> P.to_json (P.of_json (field "input" item))
    | _ -> failwith "Unknown payload corpus kind" in
  List.iter (fun item -> let result = decode item in
      require (Canonical.encode result = Canonical.encode (field "normalized" item)) "Payload normalized bytes changed";
      require (Json.String (Canonical.fingerprint result) = field "fingerprint" item) "Payload fingerprint changed") records;
  List.iter (fun item -> reject (Json.string (field "id" item)) (Json.string (field "expected_code" item))
      (fun () -> decode item)) negatives;
  Printf.printf "payload structure: %d records and %d intended rejections passed\n" (List.length records) (List.length negatives)
let () = match Array.to_list Sys.argv with
  | [_] -> literal ()
  | [_; path] -> literal (); retained path
  | _ -> failwith "Usage: test_payload_structure.exe [<absolute-corpus.json>]"
