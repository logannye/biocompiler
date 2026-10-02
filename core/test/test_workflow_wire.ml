open Bioc_wire
let require condition message = if not condition then failwith message
let rejected code run = match run () with
  | _ -> failwith ("Expected bounded artifact rejection: " ^ code)
  | exception Diagnostic.Error error -> require (error.code=code)
      ("Expected " ^ code ^ ", received " ^ error.code)
let maximum = 64 * 1024 * 1024
let parse = Json.parse_bounded ~max_bytes:maximum ~max_nodes:1_000_000
let () =
  (* Literal encodings/digests generated independently with Python json/hashlib. *)
  let small = {literal|{"é":[0,-0.0,1e-07,9007199254740993],"🧬":"\\\n"}|literal} in
  let value = parse small in
  let bytes = Canonical.encode_bounded ~max_bytes:(String.length small) value in
  require (bytes=small && Canonical.sha256 bytes="4f28949b9b1f89bbbd269cd33f89235332a160ddb8f27a0c2edb4885a035261f")
    "Large-artifact codec changed Unicode, binary64 or exact integer spelling";
  require (Canonical.encode value=bytes && Json.equal (Json.parse small) value)
    "Default and artifact codecs disagree within the original limits";
  rejected "response_too_large" (fun () -> Canonical.encode_bounded ~max_bytes:(String.length small-1) value);
  rejected "request_too_large" (fun () -> Json.parse_bounded ~max_bytes:(String.length small-1) ~max_nodes:100 small);
  List.iter (fun text -> rejected "duplicate_key" (fun () -> parse text))
    ["{\"a\":0,\"a\":1}"; "{\"a\":{\"b\":0,\"b\":1}}"];
  rejected "nonfinite_number" (fun () -> parse "1e309");
  rejected "invalid_json" (fun () -> parse "[0,]");
  List.iter (fun limit -> rejected "invalid_json_limits" (fun () -> Canonical.encode_bounded ~max_bytes:limit Json.Null))
    [-1;maximum+1];
  List.iter (fun (bytes,nodes) -> rejected "invalid_json_limits"
    (fun () -> Json.parse_bounded ~max_bytes:bytes ~max_nodes:nodes "null"))
    [-1,1;maximum+1,1;4,0;4,1_000_001];
  require (Json.equal (Json.parse_artifact ~max_bytes:7 ~max_nodes:3 "{\"x\":0}")
      (Json.parse "{\"x\":0}")) "Artifact key/value exact limit differs";
  rejected "node_limit" (fun () -> Json.parse_artifact ~max_bytes:7 ~max_nodes:2 "{\"x\":0}");
  require (Json.equal (Json.parse_bounded ~max_bytes:7 ~max_nodes:2 "{\"x\":0}")
      (Json.parse "{\"x\":0}")) "Historical value-only parser limit changed";
  let chunk = String.make (3*1024*1024) 'x' in
  let document = Json.Array (List.init 12 (fun _ -> Json.String chunk)) in
  let encoded = Canonical.encode_bounded ~max_bytes:37748773 document in
  require (String.length encoded=37748773 && Canonical.sha256 encoded="97e001b01ed2eea50602829b82d65797a2a0409b187e0e7504aba577bbd18b04")
    "Complete artifact above both original byte ceilings differs from independent bytes";
  rejected "response_too_large" (fun () -> Canonical.encode document);
  rejected "response_too_large" (fun () -> Canonical.encode_bounded ~max_bytes:(37748773-1) document);
  rejected "request_too_large" (fun () -> Json.parse encoded);
  let decoded = Json.parse_bounded ~max_bytes:37748773 ~max_nodes:13 encoded in
  require (Json.equal decoded document) "Exact artifact byte/value bounds changed round-trip content";
  rejected "node_limit" (fun () -> Json.parse_bounded ~max_bytes:37748773 ~max_nodes:12 encoded);
  rejected "request_too_large" (fun () -> Json.parse_bounded ~max_bytes:(37748773-1) ~max_nodes:13 encoded);
  let many = "[" ^ String.concat "," (List.init 250_000 (fun _ -> "0")) ^ "]" in
  rejected "node_limit" (fun () -> Json.parse many);
  require (List.length (Json.array (parse many))=250_000)
    "Selected artifact node ceiling still uses the old wire ceiling";
  require (Limits.max_request_bytes=16*1024*1024 && Limits.max_response_bytes=32*1024*1024 &&
           Limits.max_json_nodes=250_000) "Default v1 limits were changed";
  print_endline "workflow artifact codecs: complete 36 MiB identity, strict shared JSON grammar, exact byte/value boundaries and unchanged v1 limits checked"
