open Bioc_wire
module M = Bioc_domain.Molecular_record
module P = M.Provenance

let require condition message = if not condition then failwith message
let field name value = Json.field name (Json.object_fields value)
let rejected code operation = match operation () with
  | () -> failwith ("Expected molecular rejection " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      ("Wrong molecular diagnostic " ^ diagnostic.code ^ "; expected " ^ code)
let unknown () = P.make ~status:P.Unknown ~authority:[] ~locator:None ~reason:"Artificial declaration."

let literals () =
  let provenance = unknown () in
  require (P.status provenance = P.Unknown && P.authority provenance = []) "Unknown provenance invented authority";
  require (Json.equal (P.to_json provenance) (P.of_json (P.to_json provenance) |> P.to_json)) "Provenance roundtrip changed authority";
  rejected "invalid_molecular_provenance" (fun () -> ignore (P.make ~status:P.Declared ~authority:[] ~locator:None ~reason:"Fixture."));
  List.iter (fun value -> rejected "invalid_molecular_text" (fun () -> ignore (M.text (Json.String value))))
    [""; " leading"; "trailing "; "internal\ncontrol"; "bad\127"; "\226\128\131leading"; "trailing\194\133"];
  require (M.text (Json.String "inside\226\128\131space") = "inside\226\128\131space") "Internal Unicode whitespace lost";
  require (M.text ~maximum:8 (Json.String "\195\169\195\169\195\169\195\169") = "\195\169\195\169\195\169\195\169") "UTF-8 exact limit rejected";
  rejected "invalid_molecular_text" (fun () -> ignore (M.text ~maximum:7 (Json.String "\195\169\195\169\195\169\195\169")));
  let rec nested count = if count = 0 then Json.Null else Json.Array [nested (count - 1)] in
  M.check_resources (nested 96);
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (nested 97));
  M.bounded_tree (Json.Array (List.init 99_999 (fun _ -> Json.Null)));
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (Json.Array (List.init 100_000 (fun _ -> Json.Null))));
  M.bounded_tree (Json.Int (Z.shift_left Z.one 4095));
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (Json.Int (Z.shift_left Z.one 4096)));
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (Json.String (String.make 1_000_001 'a')));
  let escaping = Json.String (String.make 700_000 '\001') in
  M.bounded_tree escaping;
  rejected "molecular_resource_limit" (fun () -> M.check_resources escaping);
  let rec cycle = Json.Array [cycle] in
  rejected "molecular_cycle" (fun () -> M.bounded_tree cycle);
  let rec array_spine = Json.Null :: array_spine in
  let rec object_spine = ("x", Json.Null) :: object_spine in
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (Json.Array array_spine));
  rejected "molecular_resource_limit" (fun () -> M.bounded_tree (Json.Object object_spine));
  rejected "molecular_resource_limit" (fun () -> ignore (M.array ~maximum:4 (Json.Array array_spine)));
  rejected "molecular_resource_limit" (fun () -> ignore (M.pretty_size (Json.Array array_spine)));
  let pin = Bioc_domain.Pinned_identity.make ~kind:Bioc_domain.Pinned_identity.Source
      ~id:"fixture" ~version:"1" ~content_fingerprint:(String.make 64 'a') in
  let rec authority_spine = pin :: authority_spine in
  rejected "molecular_resource_limit" (fun () -> ignore (P.make ~status:P.Declared
      ~authority:authority_spine ~locator:(Some "fixture") ~reason:"Fixture."));
  rejected "nonfinite_number" (fun () -> M.bounded_tree (Json.Float Float.infinity));
  rejected "duplicate_key" (fun () -> M.bounded_tree (Json.Object ["x", Json.Null; "x", Json.Bool false]));
  rejected "invalid_molecular_indent" (fun () -> ignore (M.pretty_size ~indent:(Some 9) Json.Null));
  require (M.pretty_size (Json.Object ["a", Json.Array [Json.int 1; Json.int 2]]) = 29) "Literal pretty size changed";
  print_endline "molecular records: provenance, Unicode, tree/number/publication bounds and cycle literals passed"

let retained path =
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Molecular corpus exceeds read bound";
      Json.parse (really_input_string channel size)) in
  require (field "schema_version" corpus = Json.String "biocompiler.molecule_chemistry_conformance.v1") "Unknown molecular corpus";
  let texts = Json.array (field "text_cases" corpus) and pretty = Json.array (field "pretty_cases" corpus) in
  require (List.length texts = 10 && List.length pretty = 50) "Missing molecular text/serialization corpus";
  List.iter (fun case ->
      let maximum = Json.integer (field "maximum" case) |> Z.to_int in
      let accepted = match M.text ~maximum (field "value" case) with
        | _ -> true | exception Diagnostic.Error _ -> false in
      require (accepted = Json.boolean (field "accepted" case)) "Molecular UTF-8 text acceptance differs") texts;
  List.iter (fun case ->
      let indent = match field "indent" case with Json.Null -> None | value -> Some (Json.integer value |> Z.to_int) in
      let actual = M.pretty_size ~indent (field "document" case) in
      require (Json.int actual = field "bytes" case) "Python-compatible molecular pretty byte size differs") pretty;
  Printf.printf "molecular records: %d text and %d pretty-size cases passed\n" (List.length texts) (List.length pretty)

let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_molecular_record.exe [required-corpus.json]"
