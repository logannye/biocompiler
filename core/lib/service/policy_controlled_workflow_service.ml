open Bioc_wire
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
module Check = Bioc_realization_checker.Policy_controlled_workflow_check
module W = Bioc_checker.Work_budget
let str value = Json.String value
let obj fields = Json.Object fields
let get key value = Json.field key (Json.object_fields value)
let operations = ["check-policy-controlled-workflow"; "replay-policy-controlled-workflow"; "export-policy-controlled-workflow"]
let producer_operation = "compile-policy-controlled-workflow"
let validation_scope = "policy-controlled-workflow-v0.1"
let implementation = "biocompiler.ocaml.policy_controlled_workflow.v0.1"
let schema_version = "biocompiler.core.policy_controlled_workflow.v1"
let resource_profile = R.resource_profile
let max_result_bytes = Limits.max_response_bytes - 6 * Limits.max_string_bytes - 65536
let max_result_nodes = Limits.max_json_nodes - 32
let make_profile ops = obj [
  "operations", Json.Array (List.map str ops);
  "request_schema", str "biocompiler.policy_controlled_workflow_request.v0.1";
  "request_profile", str "biocompiler.policy_controlled_composition_mrna.v0.1";
  "source_profile", str "biocompiler.policy_controlled_composition_source.v0.1";
  "candidate_schema",str C.schema_version; "limits_schema",str R.limits_schema;
  "schema_version", str schema_version; "implementation", str implementation;
  "resource_profile", str resource_profile; "validation_scope", str validation_scope;
  "stage", str "joined"; "artifact", str "checked_pair"; "empirical", str "unassessed";
  "max_result_bytes", Json.int max_result_bytes; "max_result_nodes", Json.int max_result_nodes]
let profile = make_profile operations
let producer_profile = make_profile (operations @ [producer_operation])
let bounded_positive ~path maximum raw =
  let value = Json.integer ~path raw in
  Diagnostic.require ~path (Z.sign value > 0 && Z.leq value (Z.of_int maximum))
    "controlled_workflow_service_limit" "Original service budget exceeds its positive finite ceiling.";
  Z.to_int value

let measure budget raw = Bioc_domain.Policy_material_request.preflight
  ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ~max_depth:128
  ~charge:(W.charge budget) raw

let fingerprint budget raw =
  let bytes = measure budget raw in
  W.charge budget bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:max_result_bytes raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_workflow_service_accounting"
    "Canonical publication accounting disagrees with the complete body.";
  W.charge budget bytes;
  Canonical.sha256 encoded

let prepare_internal ~produce ~executable ~(request:Protocol.request) =
  let generated = request.operation = producer_operation in
  Diagnostic.require (List.mem request.operation operations ||
      (generated && executable = Protocol.Core && Option.is_some produce))
    "unsupported_operation" "Unsupported joined workflow operation for this executable.";
  let fields = Json.object_fields ~path:"/payload" request.payload in
  let replay = request.operation = "replay-policy-controlled-workflow" in
  Json.exact_fields ~path:"/payload" (if generated then ["request"]
    else if replay then ["request";"candidate";"report"] else ["request";"candidate"]) fields;
  let original = Json.field "request" fields in
  let maximum = bounded_positive ~path:"/payload/request/behavior_request/original/budgets/max_work"
    1_000_000_000 (get "max_work" (get "budgets" (get "original" (get "behavior_request" original)))) in
  let budget = W.create ~profile:validation_scope
    ~error_code:"controlled_workflow_service_work_limit" ~maximum () in
  let original_request = R.of_json ~charge:(W.charge budget) original in
  let decoding_work = maximum - W.remaining budget in
  let limits = R.budgets original_request in
  Diagnostic.require (limits.max_work = maximum) "controlled_workflow_service_limit"
    "Complete request changed the original service work ceiling.";
  let candidate = if generated then (match produce with
    | Some build -> build ~charge:(W.charge budget) original_request
    | None -> Diagnostic.fail "unsupported_operation" "No constructor exists in this service.")
    else C.of_json ~charge:(W.charge budget) (Json.field "candidate" fields) in
  let checked = if replay then Check.replay ~parent:budget ~request:original_request ~candidate
      (Json.field "report" fields)
    else Check.check ~parent:budget ~request:original_request ~candidate () in
  let report = Check.report checked in
  let publication = W.create_output ~profile:validation_scope
    ~error_code:"controlled_workflow_service_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  ignore (measure budget report);
  W.reserve_json publication report;
  let report_fingerprint = fingerprint budget report in
  let artifact = if request.operation = "export-policy-controlled-workflow" then (
    match Check.accepted checked with
    | None -> Json.Null
    | Some joined -> Policy_controlled_workflow_format.render ~charge:(W.charge budget) joined)
    else Json.Null in
  let fields = ["schema_version", str schema_version;
    "implementation", str implementation; "resource_profile", str resource_profile;
    "validation_scope", str validation_scope; "request_fingerprint", str (R.fingerprint original_request);
    "candidate_fingerprint",str (C.fingerprint candidate);
    "invocation_fingerprint",get "invocation_fingerprint" report;
    "candidate",C.to_json candidate;
    "report_fingerprint", str report_fingerprint; "report", report; "artifact", artifact] in
  let usage total = obj ["unit", str "logical_data_visits_and_child_semantic_work";
    "preparation_charged_work", Json.int total;
    "request_decoding_work", Json.int decoding_work;
    "publication", str "requires_original_one_shot_frame_guard"] in
  (* The immutable actual preparation count is written after this reservation;
     its decimal width cannot exceed the original maximum used here. *)
  let reserved = obj ["result",obj (fields @ ["usage",usage maximum])] in
  ignore (measure budget reserved);
  let result_limit = W.create_output ~profile:validation_scope
    ~error_code:"controlled_workflow_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes () in
  W.reserve_json result_limit reserved;
  let result = obj (fields @ ["usage", usage (maximum - W.remaining budget)]) in
  let expected = Protocol.response ~executable ~request:(Some request)
    ~status:Protocol.Ok ~result:(Some result) [] in
  let consumed = ref false in
  let before_encode actual =
    Diagnostic.require (not !consumed) "controlled_workflow_service_publication_guard"
      "The original response publication guard has already been consumed.";
    consumed := true;
    (* One work owner survives construction and checking and checks the actual executable,
       request ID, operation, complete result and outer success envelope. A
       failed check consumes the guard and cannot be retried for publication. *)
    let module Meter = Bioc_checker.Policy_generation_meter.Make(struct
      let charge = W.charge budget
    end) in
    let outer = W.create_output ~profile:validation_scope
      ~error_code:"controlled_workflow_service_publication_limit"
      ~max_bytes:(Limits.max_response_bytes - 1) ~max_nodes:Limits.max_json_nodes () in
    (* This bounded iterative reservation is the first traversal: it rejects
       cyclic, deep or oversized callback data before recursive metered work.
       Its byte/node counters debit every visited field even on rejection. *)
    W.reserve_json outer actual;
    Meter.preflight actual;
    Diagnostic.require (Meter.Json.equal actual expected)
      "controlled_workflow_service_publication_guard"
      "Actual protocol frame differs from the original prepared workflow response.";
    Meter.serialization actual;
    let encoded = Canonical.encode_bounded ~max_bytes:(Limits.max_response_bytes - 1) actual in
    W.charge budget (String.length encoded);
    ignore (Json.parse_artifact ~max_bytes:(Limits.max_response_bytes - 1)
      ~max_nodes:Limits.max_json_nodes encoded);
    (* The transport encodes this same immutable frame immediately afterward. *)
    Meter.serialization actual;
    Diagnostic.require (not (W.exhausted budget)) "controlled_workflow_service_work_limit"
      "An exhausted workflow invocation cannot publish a result."
  in
  result,before_encode

let prepare ~executable ~request = prepare_internal ~produce:None ~executable ~request
let prepare_generated ~executable ~request ~produce =
  Diagnostic.require (request.Protocol.operation = producer_operation) "unsupported_operation"
    "The generated route only constructs joined workflow.";
  prepare_internal ~produce:(Some produce) ~executable ~request
