open Bioc_wire
module Coordinates = Bioc_domain.Molecule_coordinates

let require condition message = if not condition then failwith message
let field name value = Json.field name (Json.object_fields value)
let fixture_integer value = int_of_string (Canonical.encode value)
let str value = Json.String value

let space ?(id = "frame") ?(alphabet = "RNA") ?(length = 10)
    ?(topology = "linear") ?(axis = "5prime_to_3prime") () =
  Json.Object [
    "schema_version", str "biocompiler.molecule_coordinate_space.v0.1";
    "id", str id; "alphabet", str alphabet; "length", Json.int length;
    "topology", str topology; "axis", str axis]

let span start stop = Json.Object [
    "schema_version", str "biocompiler.molecule_index_span.v0.1";
    "start", Json.int start; "end", Json.int stop]

let path ?(id = "frame") ?(strand = "+") spans = Json.Object [
    "schema_version", str "biocompiler.molecule_coordinate_path.v0.1";
    "space_id", str id; "strand", str strand;
    "spans", Json.Array (List.map (fun (start, stop) -> span start stop) spans)]

let rejected label code operation =
  match operation () with
  | () -> failwith (label ^ ": invalid coordinates accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code)
        (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)

let positions label space_json path_json expected =
  let selected = Coordinates.Path.of_json path_json
  and declared = Coordinates.Space.of_json space_json in
  require (Coordinates.Path.positions selected declared = expected)
    (label ^ ": changed supplied traversal order")

let literals () =
  positions "forward discontinuous" (space ()) (path [6, 8; 1, 3; 4, 5]) [6; 7; 1; 2; 4];
  positions "reverse within spans" (space ()) (path ~strand:"-" [0, 2; 5, 7]) [1; 0; 6; 5];
  positions "reverse reordered spans" (space ()) (path ~strand:"-" [5, 7; 0, 2]) [6; 5; 1; 0];
  positions "circular origin" (space ~topology:"circular" ()) (path [8, 10; 0, 3]) [8; 9; 0; 1; 2];
  positions "circular reverse origin" (space ~topology:"circular" ())
    (path ~strand:"-" [0, 3; 8, 10]) [2; 1; 0; 9; 8];
  positions "linear reordered segments remain explicit" (space ()) (path [8, 10; 0, 3]) [8; 9; 0; 1; 2];
  positions "adjacent disjoint spans" (space ()) (path [2, 4; 0, 2; 4, 6]) [2; 3; 0; 1; 4; 5];
  let declared = Coordinates.Space.of_json (space ()) in
  List.iter (fun strand -> List.iter (fun boundary ->
      let selected = Coordinates.Path.of_json (path ~strand [boundary, boundary]) in
      require (Coordinates.Path.length selected = 0) "Boundary selected a residue";
      require (Coordinates.Path.positions ~limit:0 selected declared = []) "Boundary materialized a residue")
    [0; 10]) ["+"; "-"];
  let protein = Coordinates.Space.of_json (space ~alphabet:"protein" ~axis:"N_to_C" ()) in
  require (Coordinates.Space.alphabet protein = Coordinates.Protein
           && Coordinates.Space.axis protein = Coordinates.N_to_c)
    "Protein coordinate alphabet/axis changed";
  rejected "protein reverse boundary" "protein_orientation" (fun () ->
      Coordinates.Path.validate_for (Coordinates.Path.of_json (path ~strand:"-" [0, 0])) protein);
  rejected "self overlap" "coordinate_overlap" (fun () ->
      ignore (Coordinates.Path.of_json (path [0, 8; 2, 3])));
  rejected "mixed boundary" "mixed_boundary_path" (fun () ->
      ignore (Coordinates.Path.of_json (path [0, 0; 1, 2])));
  let independent = List.map (fun selected -> Coordinates.Path.of_json selected)
      [path [2, 7]; path [4, 9]] in
  List.iter (fun selected -> Coordinates.Path.validate_for selected declared) independent;
  let intervals = List.rev (List.init 128 (fun index -> 2 * index, 2 * index + 1)) in
  let selected = Coordinates.Path.of_json (path intervals)
  and declared_long = Coordinates.Space.of_json (space ~length:256 ()) in
  require (Coordinates.Path.positions selected declared_long = List.rev (List.init 128 (fun index -> 2 * index)))
    "Maximum span inventory changed order";
  rejected "span inventory bound" "coordinate_span_limit" (fun () ->
      ignore (Coordinates.Path.of_json (path ((256, 257) :: intervals))));
  let maximum = Coordinates.Space.of_json (space ~length:1_000_000 ()) in
  let full = Coordinates.Path.of_json (path [0, 1_000_000]) in
  rejected "bounded materialization" "position_limit" (fun () ->
      ignore (Coordinates.Path.positions ~limit:100_000 full maximum));
  let exact = Coordinates.Path.of_json (path [0, 100_000]) in
  let materialized = Coordinates.Path.positions ~limit:100_000 exact maximum in
  require (List.length materialized = 100_000 && List.hd materialized = 0
           && List.hd (List.rev materialized) = 99_999)
    "Exact maximum materialization changed coverage";
  let default = Coordinates.Path.of_json (path [0, 4096]) in
  require (List.length (Coordinates.Path.positions default maximum) = 4096)
    "Default position budget rejected its exact boundary";
  rejected "default materialization bound" "position_limit" (fun () ->
      ignore (Coordinates.Path.positions (Coordinates.Path.of_json (path [0, 4097])) maximum));
  List.iter (fun limit -> rejected "invalid position limit" "position_limit" (fun () ->
      ignore (Coordinates.Path.positions ~limit default maximum))) [-1; 100_001];
  rejected "invalid UTF-8 identity" "invalid_utf8" (fun () ->
      ignore (Coordinates.Space.of_json (space ~id:"bad\192\128" ())));
  rejected "surrounding Unicode whitespace" "invalid_coordinate_text" (fun () ->
      ignore (Coordinates.Space.of_json (space ~id:"\194\160frame" ())));
  let first = Coordinates.Space.of_json (space ())
  and second = Coordinates.Space.of_json (space ~length:9 ()) in
  require (Coordinates.Space_id.equal (Coordinates.Space.id first) (Coordinates.Space.id second))
    "Nominal coordinate identity unexpectedly depends on frame contents";
  require (Coordinates.Space.fingerprint first <> Coordinates.Space.fingerprint second)
    "Full coordinate authority fingerprint omitted frame length";
  let first = Coordinates.Path.of_json (path ~strand:"-" [0, 2; 5, 7])
  and second = Coordinates.Path.of_json (path ~strand:"-" [5, 7; 0, 2]) in
  require (Coordinates.Path.fingerprint first <> Coordinates.Path.fingerprint second)
    "Canonical path identity discarded supplied segment order";
  print_endline "molecule coordinates: literal traversal, nominal authority and resource limits checked"

let read_fixture filename =
  let channel = open_in_bin filename in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let length = in_channel_length channel in
      require (length <= Limits.max_request_bytes) "Coordinate fixture exceeds bounded JSON size";
      Json.parse (really_input_string channel length))

let retained_fixture filename =
  let data = read_fixture filename in
  let fields = Json.object_fields data in
  Json.exact_fields ["schema_version"; "claim_scope"; "records"; "positions"; "rejections"] fields;
  require (Json.string (field "schema_version" data) = "biocompiler.molecule_coordinates_conformance.v1")
    "Unknown coordinate fixture schema";
  let records = Json.array (field "records" data)
  and position_cases = Json.array (field "positions" data)
  and rejections = Json.array (field "rejections" data) in
  require (records <> [] && position_cases <> [] && rejections <> []) "Coordinate fixture lost required case families";
  List.iter (fun case ->
      let label = Json.string (field "id" case) and value = field "value" case in
      let normalized, fingerprint = match Json.string (field "kind" case) with
        | "space" -> let decoded = Coordinates.Space.of_json value in
            Coordinates.Space.to_json decoded, Coordinates.Space.fingerprint decoded
        | "span" -> let decoded = Coordinates.Span.of_json value in
            Coordinates.Span.to_json decoded, Coordinates.Span.fingerprint decoded
        | "path" -> let decoded = Coordinates.Path.of_json value in
            Coordinates.Path.to_json decoded, Coordinates.Path.fingerprint decoded
        | kind -> failwith ("Unknown coordinate fixture record kind " ^ kind)
      in
      require (Json.equal normalized value) (label ^ ": roundtrip discarded record contents");
      require (Canonical.encode normalized = Json.string (field "canonical_json" case))
        (label ^ ": canonical bytes differ from Python literal");
      require (fingerprint = Json.string (field "sha256" case))
        (label ^ ": canonical identity differs from Python literal")) records;
  List.iter (fun case ->
      let label = Json.string (field "id" case) in
      let declared = Coordinates.Space.of_json (field "space" case)
      and selected = Coordinates.Path.of_json (field "path" case) in
      let actual = match field "limit" case with
        | Json.Null -> Coordinates.Path.positions selected declared
        | value -> Coordinates.Path.positions ~limit:(fixture_integer value) selected declared
      in
      let expected = Json.array (field "positions" case) |> List.map fixture_integer in
      require (actual = expected) (label ^ ": positions differ from literal authority")) position_cases;
  List.iter (fun case ->
      let label = Json.string (field "id" case) and code = Json.string (field "code" case) in
      rejected label code (fun () -> match Json.string (field "operation" case) with
        | "space" -> ignore (Coordinates.Space.of_json (field "value" case))
        | "span" -> ignore (Coordinates.Span.of_json (field "value" case))
        | "path" -> ignore (Coordinates.Path.of_json (field "value" case))
        | "validate" -> Coordinates.Path.validate_for
            (Coordinates.Path.of_json (field "path" case)) (Coordinates.Space.of_json (field "space" case))
        | "positions" -> ignore (Coordinates.Path.positions ~limit:(fixture_integer (field "limit" case))
            (Coordinates.Path.of_json (field "path" case)) (Coordinates.Space.of_json (field "space" case)))
        | operation -> failwith ("Unknown coordinate fixture operation " ^ operation))) rejections;
  Printf.printf "molecule coordinates: %d canonical records, %d literal positions, %d rejection cases passed\n"
    (List.length records) (List.length position_cases) (List.length rejections)

let () =
  match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; filename] -> literals (); retained_fixture filename
  | _ -> failwith "Usage: test_molecule_coordinates.exe [required-fixture-path]"
