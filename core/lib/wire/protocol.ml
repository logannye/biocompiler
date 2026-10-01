let version = "biocompiler.core.v1"
type request = { request_id : string; operation : string; payload : Json.t }
type executable = Core | Verify
type status = Ok | Error | Unsupported

let executable_name = function Core -> "core" | Verify -> "verify"

let decode_request value =
  let fields = Json.object_fields value in
  Json.exact_fields ["protocol"; "request_id"; "operation"; "payload"] fields;
  Diagnostic.require (Json.string (Json.field "protocol" fields) = version)
    "protocol_mismatch" "Unsupported core protocol version.";
  { request_id = Json.name (Json.field "request_id" fields);
    operation = Json.name (Json.field "operation" fields);
    payload = Json.field "payload" fields }

let identity executable = Json.Object [
    "implementation", Json.String "ocaml";
    "version", Json.String "0.1.0";
    "protocol", Json.String version;
    "executable", Json.String (executable_name executable)
  ]

let response ~executable ~request ~(status : status) ~result diagnostics =
  Diagnostic.require
    (match status, result, diagnostics with
     | Ok, Some _, [] -> true
     | (Error | Unsupported), None, _ :: _ -> true
     | _ -> false)
    "internal_protocol" "Invalid response construction.";
  Json.Object [
    "protocol", Json.String version;
    "request_id", (match request with None -> Json.Null | Some request -> Json.String request.request_id);
    "operation", (match request with None -> Json.Null | Some request -> Json.String request.operation);
    "status", Json.String (match status with Ok -> "ok" | Error -> "error" | Unsupported -> "unsupported");
    "result", Option.value ~default:Json.Null result;
    "diagnostics", Json.Array (List.map (fun (value : Diagnostic.t) -> Json.Object [
        "code", Json.String value.code; "message", Json.String value.message;
        "path", (match value.path with None -> Json.Null | Some path -> Json.String path)]) diagnostics);
    "core", identity executable
  ]

let limits = Json.Object [
    "max_request_bytes", Json.int Limits.max_request_bytes;
    "max_response_bytes", Json.int Limits.max_response_bytes;
    "max_depth", Json.int Limits.max_depth;
    "max_json_nodes", Json.int Limits.max_json_nodes;
    "max_string_bytes", Json.int Limits.max_string_bytes;
    "max_number_chars", Json.int Limits.max_number_chars;
    "max_intent_nodes", Json.int Limits.max_intent_nodes;
    "max_graph_edges", Json.int Limits.max_graph_edges
  ]

let read_stdin () =
  let buffer = Buffer.create 4096 and chunk = Bytes.create 65_536 in
  let finished = ref false in
  while not !finished do
    let available = min (Bytes.length chunk) (Limits.max_request_bytes + 1 - Buffer.length buffer) in
    let count = input stdin chunk 0 available in
    if count = 0 then finished := true
    else (
      Buffer.add_subbytes buffer chunk 0 count;
      Diagnostic.require (Buffer.length buffer <= Limits.max_request_bytes)
        "request_too_large" "Core request exceeds its byte limit.")
  done;
  Buffer.contents buffer
