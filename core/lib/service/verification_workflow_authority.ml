open Bioc_wire
module B = Bioc_realization_checker.Verification_workflow_budget
module K = Bioc_realization_checker.Synthetic_verification
module R = Bioc_realization_checker.Realization_check
module S = Bioc_realization_checker.Synthetic_candidate_check
module X = Bioc_domain.Verification_exploration
module V = Bioc_domain.Verification_workflow

let implementation_version = "biocompiler.ocaml.verification_workflow_authority.v0.1"
let profile_version = "biocompiler.core.verification_workflow_authority.v1"
let operations = ["validate-verification-workflow-authority"]
let validation_scope = "fresh_source_authority_only"
let validation_scopes = [validation_scope]
let string value = Json.String value
let strings values = Json.Array (List.map string values)
let get key raw = Json.field key (Json.object_fields raw)
let default_resources = B.limits_json B.default_limits
let control_fields = ["max_work";"max_monitor_items";"max_request_bytes";"max_report_bytes";"max_report_nodes"]
let profile = Json.Object [
  "profile",string profile_version;"implementation_version",string implementation_version;
  "engine_version",string K.implementation_version;"workflow_version",string V.workflow_version;
  "request_schema",string V.Request.schema_version;"operations",strings operations;
  "workflow_operations",strings ["check";"explore";"reduce"];
  "modes",strings ["candidate";"model"];"validation_scope",string validation_scope;
  "artifact_encoding",string "python-json-v1";
  "resources",get "resources" Verification_workflow_service.profile]
let profiles = ["verification_workflow_authority",profile]
let control_codec ?charge () = X.Codec.make_limits ~max_bytes:65_536 ~max_nodes:4096 ?charge ()
let decode_controls payload =
  let fields = Json.object_fields ~path:"payload.operation_payload" payload in
  Json.exact_fields ~path:"payload.operation_payload" ["profile";"limits"] fields;
  Diagnostic.require (Json.string ~path:"payload.operation_payload.profile" (Json.field "profile" fields) = profile_version)
    "workflow_authority_profile" "Unsupported verification workflow authority profile.";
  match Json.field "limits" fields with
  | Json.Null -> B.default_limits
  | Json.Object limits ->
      Json.exact_fields ~path:"payload.operation_payload.limits" control_fields limits;
      let value key = match Json.field key limits with
        | Json.Int number when Z.sign number > 0 && Z.compare number (Json.integer (get key default_resources)) <= 0 ->
            Z.to_int number
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

type result = Verification_workflow_service.result = { artifact : string; result : Json.t }
let workflow_operation = function V.Check -> "check" | V.Explore -> "explore" | V.Reduce -> "reduce"
let mode = function V.Candidate -> "candidate" | V.Model -> "model"
let resources budget = Json.Object ["workflow",B.limits_json (B.limits budget);
  "realization",R.limits_json (B.realization_limits budget);
  "synthetic",S.limits_json (B.synthetic_limits budget)]
let handle_in ~budget ~executable ~request_id ~operation ~payload ~authority () =
  let control_limits = control_codec ~charge:(B.charge budget) () in
  X.Codec.preflight ~limits:control_limits payload;
  X.Codec.preflight ~limits:control_limits (Json.Array [string request_id;string operation]);
  ignore (Json.name ~path:"request_id" (string request_id));
  Diagnostic.require (operation="validate-verification-workflow-authority")
    "workflow_authority_operation" "Unknown verification workflow authority operation.";
  let selected_limits = decode_controls payload in
  B.charge budget 1024;
  Diagnostic.require (Json.equal (B.limits_json selected_limits) (B.limits_json (B.limits budget)))
    "workflow_limits" "Workflow controls differ from the shared operation budget.";
  B.reserve_request budget authority;
  let authority_fingerprint = B.with_workspace budget (fun () ->
    X.Codec.fingerprint ~limits:(B.input_codec budget) authority) in
  (* This invokes the same fresh source lowering and complete request checks as
     run/replay, then stops before any workflow evaluation or stored evidence. *)
  let request = K.decode_request_in ~budget ~path:"authority" authority in
  let raw_request = V.Request.to_json request in
  B.publish budget raw_request;
  let artifact = B.encode_report budget raw_request in
  B.charge budget (String.length artifact + 1);
  let request_fingerprint = Canonical.sha256 artifact in
  Diagnostic.require (request_fingerprint=V.Request.fingerprint request) "workflow_authority_identity"
    "Complete workflow authority encoding differs from its validated request identity.";
  B.charge budget 4096;
  let result = Json.Object [
    "schema_version",string "biocompiler.core.verification_workflow_authority_result.v1";
    "profile",string profile_version;"operation",string operation;
    "executable",string (Protocol.executable_name executable);"request_id",string request_id;
    "validation_scope",string validation_scope;"implementation_version",string implementation_version;
    "workflow_version",string V.workflow_version;
    "workflow_operation",string (workflow_operation (V.Request.operation request));
    "mode",string (mode (V.Request.mode request));
    "authority_fingerprint",string authority_fingerprint;"request_fingerprint",string request_fingerprint;
    "resources",resources budget] in
  ignore (X.Codec.encode ~limits:control_limits result);
  {artifact;result}
