open Bioc_wire
module D = Bioc_domain.Architecture_deployment
module A = D.Availability
module R = D.Requirement
module T = D.Time
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let reject label code action = match action () with
  | _ -> failwith (label ^ ": invalid declaration accepted")
  | exception Diagnostic.Error error -> require (error.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ error.code)
let seconds value = T.of_json (Json.Float value)
let literal () =
  require (T.compare_sum (seconds 0.1) (seconds 0.2) (seconds 0.3) = 0) "Decimal tenth boundary changed";
  require (T.compare_sum (seconds 0.7) (seconds 0.1) (seconds 0.8) = 0) "Decimal eighth boundary changed";
  require (T.compare_sum (seconds 0.1) (seconds 31_535_999.9) T.maximum = 0) "Decimal cap boundary changed";
  let numerator, denominator = T.ratio (seconds 0.1) in
  require (Z.equal numerator Z.one && Z.equal denominator (Z.of_int 10)) "Decimal seconds became binary rational";
  let negative_zero = T.to_json (seconds (-. 0.)) in
  require (Canonical.encode negative_zero = "-0.0") "Authority lost signed floating zero";
  List.iter (fun value -> reject "time boundary" "invalid_deployment_time" (fun () -> T.of_json value))
    [Json.Null; Json.Bool false; Json.String "0.1"; Json.int (-1); Json.int (D.max_seconds + 1);
     Json.Float infinity; Json.Float nan; Json.Int (Z.shift_left Z.one 20_000)];
  let available = A.make ~id:"a" ~placement_id:"member" ~onset_min:T.zero ~onset_max:(seconds 9.)
      ~duration_min:(seconds 1.) ~duration_max:(seconds 2.) ~assumptions:["z"; "a"] in
  require (A.assumptions available = ["a"; "z"]) "Assumption normalization changed";
  require (T.compare_sum (A.onset_min available) (A.duration_min available) (A.onset_max available) < 0)
    "Structurally valid empty common window was discarded";
  let req = R.make ~id:"r" ~delivery_group_id:"group" ~recipient_role:"role" ~compartment:"abstract"
      ~required_from:(seconds 0.1) ~required_until:(seconds 0.3) ~unavailable_after:None
      ~require_same_recipient:false ~assumptions:["declaration"] in
  require (not (R.require_same_recipient req) && R.compartment req = "abstract")
    "Structural import performed contextual deployment assessment";
  require (Json.equal (R.to_json req) (R.to_json (R.of_json (R.to_json req)))) "Full requirement changed on import";
  reject "cyclic native assumptions" "molecular_resource_limit" (fun () ->
      let rec assumptions = "a" :: assumptions in
      A.make ~id:"cycle" ~placement_id:"member" ~onset_min:T.zero ~onset_max:T.zero
        ~duration_min:(seconds 1.) ~duration_max:(seconds 1.) ~assumptions);
  reject "cyclic raw authority" "molecular_cycle" (fun () ->
      let rec value = Json.Array [value] in A.of_json value);
  print_endline "deployment literals: decimal boundaries, retained numeric kinds, structural scope and resource bounds passed"

let retained path =
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let length = in_channel_length channel in
      require (length <= 100_000) "Deployment corpus exceeds read bound";
      Json.parse (really_input_string channel length)) in
  require (field "schema_version" corpus = Json.String "biocompiler.architecture_deployment_conformance.v1")
    "Wrong deployment corpus schema";
  let records = Json.array (field "records" corpus) and rejections = Json.array (field "rejections" corpus)
  and decimals = Json.array (field "decimals" corpus) and sums = Json.array (field "sums" corpus) in
  require (List.length records = 15 && List.length rejections = 78 && List.length decimals = 18 && List.length sums = 6)
    "Deployment corpus is incomplete";
  let ids = List.map (field "id") (records @ rejections @ decimals @ sums) in
  let expected_ids = "c2a7f64b484d3208d2608131f860b0d8d2a0edeaffbe573e252b619aa460cd1d" in
  require (Canonical.fingerprint (Json.Array ids) = expected_ids && field "case_ids_sha256" corpus = Json.String expected_ids)
    "Deployment case inventory changed";
  let decode item = match Json.string (field "kind" item) with
    | "availability" -> A.to_json (A.of_json (field "input" item))
    | "requirement" -> R.to_json (R.of_json (field "input" item))
    | _ -> failwith "Unknown deployment corpus kind" in
  List.iter (fun item ->
      let name = Json.string (field "id" item) in
      let output = decode item in
      require (Canonical.encode output = Canonical.encode (field "normalized" item)) (name ^ ": normalized bytes differ");
      require (Json.String (Canonical.fingerprint output) = field "fingerprint" item) (name ^ ": identity differs")) records;
  List.iter (fun item -> reject (Json.string (field "id" item)) (Json.string (field "expected_code" item))
      (fun () -> decode item)) rejections;
  List.iter (fun item ->
      let numerator, denominator = T.ratio (T.of_json (field "input" item)) in
      require (Z.equal numerator (Json.integer (field "numerator" item)) &&
               Z.equal denominator (Json.integer (field "denominator" item)))
        (Json.string (field "id" item) ^ ": exact decimal ratio differs")) decimals;
  List.iter (fun item ->
      let result = T.compare_sum (T.of_json (field "left" item)) (T.of_json (field "right" item)) (T.of_json (field "bound" item)) in
      let sign = if result < 0 then -1 else if result > 0 then 1 else 0 in
      require (Json.int sign = field "expected" item) (Json.string (field "id" item) ^ ": decimal sum boundary differs")) sums;
  Printf.printf "deployment: %d records, %d intended rejections, %d exact ratios and %d literal sum boundaries passed\n"
    (List.length records) (List.length rejections) (List.length decimals) (List.length sums)
let () = match Array.to_list Sys.argv with
  | [_] -> literal ()
  | [_; path] -> literal (); retained path
  | _ -> failwith "Usage: test_architecture_deployment.exe [required-corpus.json]"
