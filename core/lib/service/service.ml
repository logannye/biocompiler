open Bioc_wire

let capabilities = Json.Object [
    "operations", Json.Array (List.map (fun value -> Json.String value) ["capabilities"; "canonicalize"; "validate-intent"; "verify-lowering"]);
    "intent_schemas", Json.Array [Json.String Bioc_domain.Intent.schema_version];
    "canonicalization", Json.String "python-json-v1";
    "validation_scopes", Json.Array [Json.String Bioc_domain.Intent.validation_scope;
                                     Json.String Bioc_checker.Lowering_check.validation_scope];
    "limits", Protocol.limits;
    "claim_scope", Json.String "Structural intent validation and exact frozen source-to-Behavior correspondence only; no execution, architecture acceptance, molecular correctness, empirical function or human-use admission."
  ]

let handle _executable (request : Protocol.request) =
  match request.operation with
  | "capabilities" ->
      let fields = Json.object_fields request.payload in
      Json.exact_fields [] fields;
      Protocol.Ok, Some capabilities, []
  | "canonicalize" ->
      let canonical_json = Canonical.encode request.payload in
      Protocol.Ok, Some (Json.Object [
          "canonical_json", Json.String canonical_json;
          "sha256", Json.String (Canonical.sha256 canonical_json)]), []
  | "validate-intent" -> Protocol.Ok, Some (Bioc_checker.Intent_check.check request.payload), []
  | "verify-lowering" ->
      let fields = Json.object_fields request.payload in
      Json.exact_fields ["expected_request"; "behavior"] fields;
      let expected_request = Bioc_domain.Build_request.of_json (Json.field "expected_request" fields) in
      let behavior = Bioc_domain.Behavior.of_json (Json.field "behavior" fields) in
      (try
         let report = Bioc_checker.Lowering_check.check ~expected_request ~behavior in
         Protocol.Ok, Some (Bioc_checker.Lowering_check.to_json report), []
       with Diagnostic.Error diagnostic when String.starts_with ~prefix:"unsupported_lowering_" diagnostic.code ->
         Protocol.Unsupported, None, [diagnostic])
  | _ -> Protocol.Unsupported, None, [{
      Diagnostic.code = "unsupported_operation";
      message = "This executable does not implement the requested operation; no fallback or acceptance is granted.";
      path = Some "/operation" }]

let run executable =
  let current_request = ref None in
  let response, code =
    try
      Diagnostic.require (Array.length Sys.argv = 1) "unexpected_arguments" "Core reads one JSON request on standard input; command arguments are unsupported.";
      let request = Protocol.decode_request (Json.parse (Protocol.read_stdin ())) in
      current_request := Some request;
      let status, result, diagnostics = handle executable request in
      Protocol.response ~executable ~request:!current_request ~status ~result diagnostics,
      (match status with Protocol.Ok -> 0 | Protocol.Error -> 2 | Protocol.Unsupported -> 3)
    with
    | Diagnostic.Error diagnostic ->
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None [diagnostic], 2
    | (Stack_overflow | Out_of_memory) ->
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None
          [{ Diagnostic.code = "resource_exhausted"; message = "Core resources exhausted; no acceptance is granted."; path = None }], 2
    | exception_value ->
        (* Internal exception detail goes to stderr, never into a success value. *)
        prerr_endline (Printexc.to_string exception_value);
        Protocol.response ~executable ~request:!current_request ~status:Protocol.Error ~result:None
          [{ Diagnostic.code = "internal_error"; message = "Core failed; no acceptance is granted."; path = None }], 2
  in
  let encoded, code =
    try
      let encoded = Canonical.encode response in
      Diagnostic.require (String.length encoded < Limits.max_response_bytes)
        "response_too_large" "Core response exceeds its byte limit.";
      encoded, code
    with Diagnostic.Error diagnostic ->
      let response = Protocol.response ~executable ~request:None ~status:Protocol.Error ~result:None [diagnostic] in
      Canonical.encode response, 2
  in
  output_string stdout encoded;
  output_char stdout '\n';
  flush stdout;
  exit code
