open Bioc_wire
let require condition message = if not condition then failwith message
let legacy ?on_node ?(max_bytes=4096) ?(max_nodes=128) profile text =
  Legacy_json.parse ?on_node ~max_bytes ~max_nodes ~profile text
let reject code message action =
  match action () with
  | _ -> failwith ("Expected legacy JSON rejection: "^code)
  | exception Diagnostic.Error error ->
      require (error.code=code && error.message=message)
        ("Legacy JSON diagnostic differs: "^error.code^": "^error.message)
let () =
  let sample="{\"z\":[true,null,1,1.0],\"α\":\"é😀\"}" in
  require (Json.equal (legacy Legacy_json.Artifact sample) (Json.parse sample)) "Legacy parser changed valid scalar identities";
  let pretty=Legacy_json.pretty_utf8 (Json.parse sample) in
  require (pretty="{\n  \"z\": [\n    true,\n    null,\n    1,\n    1.0\n  ],\n  \"α\": \"é😀\"\n}")
    "Historical UTF-8 pretty spelling differs";
  require (Legacy_json.pretty_utf8 (Json.Object [])="{}" &&
    Legacy_json.pretty_utf8 (Json.Array [])="[]") "Empty containers gained whitespace";
  require (Legacy_json.pretty_utf8 (Json.String "\n\t\"\\\001")="\"\\n\\t\\\"\\\\\\u0001\"")
    "Historical UTF-8 scalar escaping differs";
  reject "duplicate_key" "Duplicate JSON object key."
    (fun () -> Json.parse "{\"x\":0,\"x\":{\"k\":1,\"k\":2}}");
  reject "legacy_artifact_json" "Duplicate JSON key: k."
    (fun () -> legacy Legacy_json.Artifact "{\"x\":0,\"x\":{\"k\":1,\"k\":2}}");
  reject "legacy_artifact_json" "Invalid JSON number: NaN."
    (fun () -> legacy Legacy_json.Artifact "{\"x\":0,\"x\":1,\"tail\":NaN}");
  reject "legacy_artifact_json" "Duplicate JSON key: α."
    (fun () -> legacy Legacy_json.Artifact "{\"α\":0,\"\\u03b1\":1}");
  reject "legacy_reference_json" "Invalid reference JSON: Duplicate JSON field: version."
    (fun () -> legacy Legacy_json.Reference "{\"version\":1,\"version\":2}");
  List.iter (fun token ->
    reject "legacy_artifact_json" ("Invalid JSON number: "^token^".")
      (fun () -> legacy Legacy_json.Artifact ("["^token^"]"));
    reject "legacy_reference_json" ("Invalid reference JSON: Invalid number: "^token)
      (fun () -> legacy Legacy_json.Reference token)) ["NaN";"Infinity";"-Infinity"];
  reject "duplicate_key" "Duplicate JSON object key."
    (fun () -> Json.parse_legacy_artifact ~on_duplicate_key:(fun _ -> ())
      ~on_nonfinite:(fun _ -> ()) ~max_bytes:100 ~max_nodes:10 "{\"x\":1,\"x\":2}");
  reject "nonfinite_number" "JSON numbers must be finite."
    (fun () -> Json.parse_legacy_artifact ~on_duplicate_key:(fun _ -> ())
      ~on_nonfinite:(fun _ -> ()) ~max_bytes:100 ~max_nodes:10 "NaN");
  reject "request_too_large" "JSON exceeds the byte limit."
    (fun () -> legacy ~max_bytes:1 Legacy_json.Artifact "null");
  let charged=ref 0 in
  reject "node_limit" "JSON exceeds the value count limit."
    (fun () -> legacy ~on_node:(fun () -> incr charged) ~max_nodes:2 Legacy_json.Artifact "{\"x\":1}");
  require (!charged=2) "Legacy artifact key/value work accounting changed";
  let sentinel={Diagnostic.code="sentinel";message="Original charge failure";path=None} in
  (match legacy ~on_node:(fun () -> raise (Diagnostic.Error sentinel)) Legacy_json.Reference "{}" with
   | _ -> failwith "Legacy JSON swallowed a charge failure"
   | exception Diagnostic.Error error -> require (error==sentinel) "Legacy JSON replaced the original charge exception");
  let rec cycle=Json.Array [cycle] in
  (match Legacy_json.pretty_utf8 cycle with
   | _ -> failwith "Legacy JSON serialized a cycle"
   | exception Diagnostic.Error error -> require (error.code="legacy_ascii_cycle") "Wrong legacy JSON cycle rejection");
  print_endline "Historical JSON spelling, error order and bounded parsing controls passed"
