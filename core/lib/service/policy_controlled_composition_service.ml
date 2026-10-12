open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module A = Bioc_checker.Policy_controlled_composition_admission
module W = Bioc_checker.Work_budget
let str value = Json.String value
let obj fields = Json.Object fields
let get key value = Json.field key (Json.object_fields value)
let operations = ["admit-policy-component-material"]
let validation_scope = "policy-controlled-composition-admission-v0.1"
let implementation = "biocompiler.ocaml.policy_controlled_composition.v0.1"
let schema_version = "biocompiler.core.policy_controlled_composition.v1"
let resource_profile = "biocompiler.policy_controlled_composition_resources.v0.1"
let max_result_bytes = Limits.max_response_bytes - 6 * Limits.max_string_bytes - 65536
let max_result_nodes = Limits.max_json_nodes - 32
let profile = obj [
  "operations", Json.Array (List.map str operations);
  "request_schema", str "biocompiler.policy_component_material_request.v0.14";
  "request_profile", str "biocompiler.policy_controlled_composition_mrna.v0.1";
  "source_profile", str "biocompiler.policy_controlled_composition_source.v0.1";
  "schema_version", str schema_version; "implementation", str implementation;
  "resource_profile", str resource_profile; "validation_scope", str validation_scope;
  "stage", str "admission"; "artifact", str "none"; "empirical", str "unassessed";
  "max_result_bytes", Json.int max_result_bytes; "max_result_nodes", Json.int max_result_nodes]

let bounded_positive ~path maximum raw =
  let value = Json.integer ~path raw in
  Diagnostic.require ~path (Z.sign value > 0 && Z.leq value (Z.of_int maximum))
    "policy_controlled_service_limit" "Original service budget exceeds its positive finite ceiling.";
  Z.to_int value

let measure budget raw = Bioc_domain.Policy_material_request.preflight
  ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ~max_depth:128
  ~charge:(W.charge budget) raw

let fingerprint budget raw =
  let bytes = measure budget raw in
  W.charge budget bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:max_result_bytes raw in
  Diagnostic.require (String.length encoded = bytes) "policy_controlled_service_accounting"
    "Canonical publication accounting disagrees with the complete body.";
  W.charge budget bytes;
  Canonical.sha256 encoded

let prepare ~executable ~(request:Protocol.request) =
  Diagnostic.require (List.mem request.operation operations) "unsupported_operation"
    "Controlled composition currently exposes read-only admission only.";
  let fields = Json.object_fields ~path:"/payload" request.payload in
  Json.exact_fields ~path:"/payload" ["request"] fields;
  let original = Json.field "request" fields in
  (* Read only the scalar ceiling before the bounded, charged complete decoder.
     No original structure or hash is traversed before the owner exists. *)
  let maximum = bounded_positive ~path:"/payload/request/budgets/max_work"
    1_000_000_000 (get "max_work" (get "budgets" original)) in
  let budget = W.create ~profile:validation_scope
    ~error_code:"policy_controlled_service_work_limit" ~maximum () in
  let original_request = R.of_json ~charge:(W.charge budget) original in
  let decoding_work = maximum - W.remaining budget in
  let limits = R.budgets original_request in
  Diagnostic.require (limits.max_work = maximum) "policy_controlled_service_limit"
    "Complete request changed the original service work ceiling.";
  let admitted = A.admit ~charge:(W.charge budget) original_request in
  let report = A.report admitted in
  Diagnostic.require (get "stage" report = str "admission" &&
    get "status" report = str "admitted" &&
    get "request_fingerprint" report = str (R.fingerprint original_request) &&
    get "construction_status" report = str "not_performed" &&
    get "behavior_status" report = str "not_performed" &&
    get "empirical_status" report = str "unassessed")
    "policy_controlled_service_scope" "Admission report changed its original identity or limited claim.";
  let publication = W.create_output ~profile:validation_scope
    ~error_code:"policy_controlled_service_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  ignore (measure budget report);
  W.reserve_json publication report;
  let report_fingerprint = fingerprint budget report in
  let fields = ["schema_version", str schema_version;
    "implementation", str implementation; "resource_profile", str resource_profile;
    "validation_scope", str validation_scope; "request_fingerprint", str (R.fingerprint original_request);
    "report_fingerprint", str report_fingerprint; "report", report; "artifact", Json.Null] in
  let usage total = obj ["unit", str "logical_data_visits_and_child_semantic_work";
    "preparation_charged_work", Json.int total;
    "request_decoding_work", Json.int decoding_work;
    "publication", str "requires_original_one_shot_frame_guard"] in
  (* The immutable actual preparation count is written after this reservation;
     its decimal width cannot exceed the original maximum used here. *)
  let reserved = obj ["result",obj (fields @ ["usage",usage maximum])] in
  ignore (measure budget reserved);
  let result_limit = W.create_output ~profile:validation_scope
    ~error_code:"policy_controlled_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes () in
  W.reserve_json result_limit reserved;
  let result = obj (fields @ ["usage", usage (maximum - W.remaining budget)]) in
  let expected = Protocol.response ~executable ~request:(Some request)
    ~status:Protocol.Ok ~result:(Some result) [] in
  let consumed = ref false in
  let before_encode actual =
    Diagnostic.require (not !consumed) "policy_controlled_service_publication_guard"
      "The original response publication guard has already been consumed.";
    consumed := true;
    (* One work owner survives admission and checks the actual executable,
       request ID, operation, complete result and outer success envelope. A
       failed check consumes the guard and cannot be retried for publication. *)
    let module Meter = Bioc_checker.Policy_generation_meter.Make(struct
      let charge = W.charge budget
    end) in
    let outer = W.create_output ~profile:validation_scope
      ~error_code:"policy_controlled_service_publication_limit"
      ~max_bytes:(Limits.max_response_bytes - 1) ~max_nodes:Limits.max_json_nodes () in
    (* This bounded iterative reservation is the first traversal: it rejects
       cyclic, deep or oversized callback data before recursive metered work.
       Its byte/node counters debit every visited field even on rejection. *)
    W.reserve_json outer actual;
    Meter.preflight actual;
    Diagnostic.require (Meter.Json.equal actual expected)
      "policy_controlled_service_publication_guard"
      "Actual protocol frame differs from the original prepared admission.";
    Meter.serialization actual;
    let encoded = Canonical.encode_bounded ~max_bytes:(Limits.max_response_bytes - 1) actual in
    W.charge budget (String.length encoded);
    ignore (Json.parse_artifact ~max_bytes:(Limits.max_response_bytes - 1)
      ~max_nodes:Limits.max_json_nodes encoded);
    (* The transport encodes this same immutable frame immediately afterward. *)
    Meter.serialization actual;
    Diagnostic.require (not (W.exhausted budget)) "policy_controlled_service_work_limit"
      "An exhausted admission cannot publish a result."
  in
  result,before_encode
