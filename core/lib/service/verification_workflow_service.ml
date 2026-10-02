open Bioc_wire
module B = Bioc_realization_checker.Verification_workflow_budget
module K = Bioc_realization_checker.Synthetic_verification
module R = Bioc_realization_checker.Realization_check
module S = Bioc_realization_checker.Synthetic_candidate_check
module X = Bioc_domain.Verification_exploration
module V = Bioc_domain.Verification_workflow

let implementation_version = "biocompiler.ocaml.verification_workflow_service.v0.1"
let profile_version = "biocompiler.core.verification_workflow.v1"
let operations = ["run-verification-workflow"; "replay-verification-workflow"]
let validation_scope = "complete_fresh_verification_workflow"
let validation_scopes = [validation_scope]
let string value = Json.String value
let strings values = Json.Array (List.map string values)
let get key raw = Json.field key (Json.object_fields raw)
let integer key raw = Z.to_int (Json.integer (get key raw))
let control_fields = ["max_work"; "max_monitor_items"; "max_request_bytes";
  "max_report_bytes"; "max_report_nodes"]
let default_resources = B.limits_json B.default_limits

(* These mappings use the same public constructors as the workflow budget. The
   live receipt below takes the effective leaf limits from that actual budget. *)
let default_leaf_work = min 50_000_000 (integer "max_work" default_resources)
let default_leaf_items = min 100_000 (integer "max_monitor_items" default_resources)
let default_leaf_request = min Limits.max_request_bytes (integer "max_request_bytes" default_resources)
let default_leaf_report = min Limits.max_response_bytes (integer "max_report_bytes" default_resources)
let default_leaf_nodes = min Limits.max_json_nodes (integer "max_report_nodes" default_resources)
let profile_resources = Json.Object ["workflow",default_resources;
  "realization",R.limits_json (R.make_limits ~max_work:default_leaf_work
    ~max_monitor_items:default_leaf_items ~max_request_bytes:default_leaf_request
    ~max_report_bytes:default_leaf_report ~max_report_nodes:default_leaf_nodes ());
  "synthetic",S.limits_json (S.make_limits ~max_work:default_leaf_work
    ~max_monitor_items:default_leaf_items ~max_request_bytes:default_leaf_request
    ~max_report_bytes:default_leaf_report ~max_report_nodes:default_leaf_nodes ())]
let profile = Json.Object [
  "profile",string profile_version; "implementation_version",string implementation_version;
  "engine_version",string K.implementation_version; "workflow_version",string V.workflow_version;
  "request_schema",string V.Request.schema_version; "record_schema",string V.Record.schema_version;
  "operations",strings operations; "workflow_operations",strings ["check";"explore";"reduce"];
  "modes",strings ["candidate";"model"]; "validation_scope",string validation_scope;
  "artifact_encoding",string "python-json-v1"; "resources",profile_resources]
let profiles = ["verification_workflow",profile]

let control_codec ?charge () = X.Codec.make_limits ~max_bytes:65_536 ~max_nodes:4096 ?charge ()
let decode_controls payload =
  let fields = Json.object_fields ~path:"payload.operation_payload" payload in
  Json.exact_fields ~path:"payload.operation_payload" ["profile";"limits"] fields;
  Diagnostic.require
    (Json.string ~path:"payload.operation_payload.profile" (Json.field "profile" fields) = profile_version)
    "workflow_protocol_profile" "Unsupported verification workflow profile.";
  match Json.field "limits" fields with
  | Json.Null -> B.default_limits
  | Json.Object limits ->
      Json.exact_fields ~path:"payload.operation_payload.limits" control_fields limits;
      let value key = match Json.field key limits with
        | Json.Int number when Z.sign number > 0 &&
            Z.compare number (Json.integer (get key default_resources)) <= 0 -> Z.to_int number
        | _ -> Diagnostic.fail ~path:("payload.operation_payload.limits." ^ key)
            "workflow_limits" "Workflow limits must be positive integer reductions of the declared profile." in
      let max_work = value "max_work" in
      let max_monitor_items = value "max_monitor_items" in
      let max_request_bytes = value "max_request_bytes" in
      let max_report_bytes = value "max_report_bytes" in
      let max_report_nodes = value "max_report_nodes" in
      B.make_limits ~max_work ~max_monitor_items ~max_request_bytes ~max_report_bytes ~max_report_nodes ()
  | _ -> Diagnostic.fail ~path:"payload.operation_payload.limits" "workflow_limits"
      "Workflow limits must be null or an exact object of five integer reductions."
let limits_of_payload payload =
  X.Codec.preflight ~limits:(control_codec ()) payload;
  decode_controls payload

type result = { artifact : string; result : Json.t }
let workflow_operation = function V.Check -> "check" | V.Explore -> "explore" | V.Reduce -> "reduce"
let mode = function V.Candidate -> "candidate" | V.Model -> "model"
let resources budget = Json.Object ["workflow",B.limits_json (B.limits budget);
  "realization",R.limits_json (B.realization_limits budget);
  "synthetic",S.limits_json (B.synthetic_limits budget)]
let fingerprint budget raw = B.with_workspace budget (fun () ->
  X.Codec.fingerprint ~limits:(B.input_codec budget) raw)

let handle_in ~budget ~executable ~request_id ~operation ~payload ~authority ?retained_record ?load_retained_record () =
  let control_limits = control_codec ~charge:(B.charge budget) () in
  X.Codec.preflight ~limits:control_limits payload;
  (* Scalar transport identities are bounded before their first scans or copies. *)
  X.Codec.preflight ~limits:control_limits (Json.Array [string request_id;string operation]);
  ignore (Json.name ~path:"request_id" (string request_id));
  let replay = match operation with
    | "run-verification-workflow" -> false
    | "replay-verification-workflow" -> true
    | _ -> Diagnostic.fail "workflow_protocol_operation" "Unknown verification workflow operation." in
  let selected = decode_controls payload in
  B.charge budget 1024;
  Diagnostic.require (Json.equal (B.limits_json selected) (B.limits_json (B.limits budget)))
    "workflow_limits" "Workflow controls differ from the shared operation budget.";
  Diagnostic.require (not (Option.is_some retained_record && Option.is_some load_retained_record))
    "workflow_protocol_record" "Supply one retained record source only.";
  Diagnostic.require (replay = (Option.is_some retained_record || Option.is_some load_retained_record)) "workflow_protocol_record"
    "Replay requires one retained record; fresh execution requires none.";
  B.reserve_request budget authority;
  let authority_fingerprint = fingerprint budget authority in
  let request = K.decode_request_in ~budget ~path:"authority" authority in
  let retained_record = match load_retained_record with None -> retained_record | Some load -> Some (load ()) in
  let retained_record_fingerprint,current = match retained_record with
    | None -> Json.Null,K.run_in ~budget request
    | Some raw ->
        B.reserve_request budget raw;
        let identity = fingerprint budget raw in
        let historical = K.decode_record_in ~budget ~path:"retained_record" raw in
        string identity,K.replay_in ~budget ~raw_record:raw ~expected_request:request historical in
  let artifact = B.encode_report budget (V.Record.to_json current) in
  (* The cached domain fingerprint is bound to the actual complete emitted bytes,
     not merely to a re-imported/normalized report. Hashing shares the ancestor. *)
  B.charge budget (String.length artifact + 1);
  let record_fingerprint = Canonical.sha256 artifact in
  Diagnostic.require (record_fingerprint = V.Record.fingerprint current) "workflow_protocol_identity"
    "Complete workflow encoding differs from its validated record identity.";
  B.charge budget 4096;
  let result = Json.Object [
    "schema_version",string "biocompiler.core.verification_workflow_result.v1";
    "profile",string profile_version; "operation",string operation;
    "executable",string (Protocol.executable_name executable); "request_id",string request_id;
    "validation_scope",string validation_scope; "implementation_version",string implementation_version;
    "workflow_version",string V.workflow_version;
    "workflow_operation",string (workflow_operation (V.Request.operation request));
    "mode",string (mode (V.Request.mode request));
    "authority_fingerprint",string authority_fingerprint;
    "request_fingerprint",string (V.Request.fingerprint request);
    "retained_record_fingerprint",retained_record_fingerprint;
    "record_fingerprint",string record_fingerprint; "resources",resources budget] in
  (* Prepay a complete compact receipt serialization and enforce its independent
     control envelope before returning anything to the descriptor writer. *)
  ignore (X.Codec.encode ~limits:control_limits result);
  {artifact;result}
