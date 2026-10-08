open Bioc_wire
open Bioc_domain
module W = Bioc_checker.Work_budget
module B = Bioc_realization_checker.Realization_budget
module X = Verification_exploration.Codec
module Q = Synthetic_build_request
module P = Synthetic_producer_service
let implementation_version = "biocompiler.ocaml.synthetic_producer_public_service.v0.1"
let resource_profile = "biocompiler.core.synthetic_producer_public.resources.v1"
let string value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let profile = Json.parse {profile|{"authority_encoding":"python-json-v1","claim_scope":"Complete portable build request validation and two-strategy software selection with fresh finite-history checks only; no pipeline freshness, package/export acceptance, molecular construction, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"history_samples":"exact_four_field_records_no_numeric_shorthand","history_schema":"biocompiler.synthetic_history.v0.1","implementation":"biocompiler.ocaml.synthetic_producer_public_service.v0.1","limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"operations":["select-synthetic-build-request"],"payload_fields":["profile","limits","build_request"],"presentation_fields":["frame_count","exit_code"],"producer_operation":"select-synthetic","producer_profile":"biocompiler.core.synthetic_selection.v1","producer_record_schema":"biocompiler.synthetic_selection_result.v0.1","profile":"biocompiler.core.synthetic_producer_public.v1","request_schema":"biocompiler.synthetic_build_request.v0.2","resources":{"nested_producer_controls":"five_reductions_with_outer_retained_history_subtracted_before_producer_import","protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_producer_public.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_build_request_payload","work_accounting":"single_ancestor_for_framing_full_source_import_fresh_lowering_selection_and_final_publication"}},"result_schema":"biocompiler.core.synthetic_public_production.v1","role":"bioc-core","source_check_order":["realization_fresh_lowering","history","config","horizon","profile","intended_use","artifact_scope","portable_sources","run_metadata"],"validation_scope":"portable-build-authority-two-strategy-selection-only-v1","wire_encoding":"python-json-v1"}|profile}
let operations = ["select-synthetic-build-request"]
let validation_scopes = [Json.string (get "validation_scope" profile)]
let profiles = ["synthetic_producer_public",profile]
type controls = { max_work : int; max_monitor_items : int; max_request_bytes : int;
  max_report_bytes : int; max_report_nodes : int }
let defaults = {max_work=50_000_000; max_monitor_items=100_000;
  max_request_bytes=Limits.max_request_bytes; max_report_bytes=Limits.max_response_bytes;
  max_report_nodes=Limits.max_json_nodes}
let control_fields = ["max_work"; "max_monitor_items"; "max_request_bytes"; "max_report_bytes"; "max_report_nodes"]
let controls = function
  | Json.Null -> defaults
  | Json.Object fields ->
      Json.exact_fields ~path:"payload.limits" control_fields fields;
      let value key ceiling = match Json.field key fields with
        | Json.Int value when Z.sign value > 0 && Z.compare value (Z.of_int ceiling) <= 0 -> Z.to_int value
        | _ -> Diagnostic.fail ~path:("payload.limits." ^ key) "synthetic_producer_public_limits"
            "Synthetic producer limits must be positive integer reductions of the native profile." in
      let max_work = value "max_work" defaults.max_work in
      let max_monitor_items = value "max_monitor_items" defaults.max_monitor_items in
      let max_request_bytes = value "max_request_bytes" defaults.max_request_bytes in
      let max_report_bytes = value "max_report_bytes" defaults.max_report_bytes in
      let max_report_nodes = value "max_report_nodes" defaults.max_report_nodes in
      {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
  | _ -> Diagnostic.fail ~path:"payload.limits" "synthetic_producer_public_limits"
      "Synthetic producer limits must be null or an exact object of five integer reductions."
let common_limits x = B.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
(* This fixed transport pass precedes control decoding and terminates even for
   in-process cyclic JSON or cyclic list spines. It charges the same ancestor
   used by every later phase. The chosen reduction subtracts this prefix rather
   than granting a new allowance after parsing controls. Wire values, unlike
   checker inventories, exclude object keys from their 250k value ceiling. *)
type pending = Value of Json.t * int | Array_tail of Json.t list * int
  | Object_tail of (string * Json.t) list * int
let preflight_transport work raw =
  let bytes = ref 0 and values = ref 0 in
  let add amount =
    Diagnostic.require (amount <= Limits.max_request_bytes - !bytes) "request_too_large"
      "Complete synthetic producer request exceeds the fixed transport byte limit.";
    W.charge work amount; bytes := !bytes + amount in
  let quoted value =
    Diagnostic.require (String.length value <= Limits.max_string_bytes) "string_limit"
      "A request string exceeds its fixed byte limit.";
    add (String.length value + 2); Json.validate_utf8 value;
    String.iter (function '"' | '\\' -> add 1
      | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | c when Char.code c < 32 -> add 5 | _ -> ()) value in
  let rec visit = function
    | [] -> ()
    | Value (raw,depth) :: rest ->
        Diagnostic.require (depth <= Limits.max_depth) "nesting_limit" "Request nesting exceeds its fixed limit.";
        Diagnostic.require (!values < Limits.max_json_nodes) "node_limit" "Request value count exceeds its fixed limit.";
        incr values; W.charge work 1;
        (match raw with
         | Json.String value -> quoted value; visit rest
         | Json.Object fields -> add 2; visit (Object_tail (fields,depth+1) :: rest)
         | Json.Array items -> add 2; visit (Array_tail (items,depth+1) :: rest)
         | Json.Int value ->
             Diagnostic.require (Z.numbits value <= 4 * Limits.max_number_chars) "number_limit"
               "A request integer exceeds its fixed token limit.";
             W.charge work (1 + Z.numbits value / 3);
             let text = Z.to_string value in
             Diagnostic.require (String.length text <= Limits.max_number_chars) "number_limit"
               "A request integer exceeds its fixed token limit.";
             add (String.length text); visit rest
         | value -> W.charge work 32; add (String.length (Canonical.encode value)); visit rest)
    | Array_tail ([],_) :: rest | Object_tail ([],_) :: rest -> visit rest
    | Array_tail (value :: values,depth) :: rest ->
        (match values with [] -> () | _ -> add 1);
        visit (Value (value,depth) :: Array_tail (values,depth) :: rest)
    | Object_tail ((key,value) :: fields,depth) :: rest ->
        W.charge work 1; quoted key; add 1;
        (match fields with [] -> () | _ -> add 1);
        visit (Value (value,depth) :: Object_tail (fields,depth) :: rest) in
  visit [Value (raw,0)]

let controls_json control = Json.Object ["max_work",Json.int control.max_work;
  "max_monitor_items",Json.int control.max_monitor_items;"max_request_bytes",Json.int control.max_request_bytes;
  "max_report_bytes",Json.int control.max_report_bytes;"max_report_nodes",Json.int control.max_report_nodes]
let resources control =
  let rec reduced = function
    | Json.Object fields -> Json.Object (List.map (fun (key,value) ->
        key,(match List.assoc_opt key (Json.object_fields (controls_json control)) with
          | Some value -> value | None -> reduced value)) fields)
    | Json.Array values -> Json.Array (List.map reduced values)
    | value -> value in
  reduced (get "resources" profile)
type usage = {work_charged:int;request_bytes:int;report_bytes:int;retained_peak:int}
let handle_with_usage ?parent ~executable ~request_id ~operation payload =
  Diagnostic.require (executable=Protocol.Core && List.mem operation operations)
    "unsupported_operation" "Public synthetic selection is available only in the producer executable.";
  let ancestor = match parent with
    | None -> W.create ~profile:resource_profile ~error_code:"synthetic_public_work_limit" ~maximum:defaults.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"synthetic_public_work_limit" ~maximum:defaults.max_work () in
  let initial = W.remaining ancestor in
  W.charge ancestor 1;
  preflight_transport ancestor (Json.Object ["protocol",string Protocol.version;"request_id",string request_id;
    "operation",string operation;"payload",payload]);
  let fields = Json.object_fields ~path:"payload" payload in
  Json.exact_fields ~path:"payload" ["profile";"limits";"build_request"] fields;
  Diagnostic.require (Json.field "profile" fields=get "profile" profile) "synthetic_public_profile"
    "Unsupported public synthetic producer profile.";
  let control = controls (Json.field "limits" fields) in
  let prefix = initial-W.remaining ancestor in
  Diagnostic.require (prefix<=control.max_work) "synthetic_public_work_limit"
    "Public synthetic request framing exceeds the selected work limit.";
  let reduced = W.nested ~parent:ancestor ~profile:resource_profile ~error_code:"synthetic_public_work_limit"
    ~maximum:(control.max_work-prefix) () in
  let budget = B.create ~parent:reduced ~limits:(common_limits control) () in
  B.reserve_request budget payload;
  let size = (B.usage budget).request_bytes in
  B.charge budget (5*size);
  let supplied_authority = Canonical.fingerprint payload in
  let raw_build = Json.field "build_request" fields in
  let supplied_build = Canonical.fingerprint raw_build in
  let limits = X.make_limits ~max_bytes:control.max_request_bytes ~max_nodes:Limits.max_json_nodes
    ~charge:(B.charge budget) () in
  let request = Q.decode_with_realization ~limits ~path:"payload.build_request"
    ~retain_history:(B.retain_monitor budget)
    ~decode_realization:(fun ~path raw ->
      X.preflight ~limits ~path raw;
      let request = Realization_request.of_json ~path raw in
      Bioc_realization_checker.Checked_request.request
        (Bioc_realization_checker.Checked_request.check ~parent:(B.work budget) request)) raw_build in
  let retained = (B.usage budget).monitor_peak in
  Diagnostic.require (retained<control.max_monitor_items) "realization_monitor_limit"
    "No producer capacity remains after complete build authority import.";
  let producer_controls = {control with max_monitor_items=control.max_monitor_items-retained} in
  let producer_payload = Json.Object ["profile",get "producer_profile" profile;
    "limits",controls_json producer_controls;"request",Realization_request.to_json (Q.realization request);
    "config",Synthetic_authority.Config.to_json (Q.config request);
    "history",Json.Array (List.map Execution_data.Input_frame.to_json (Q.history request));
    "until",Runtime_number.to_json (Q.until request)] in
  let production,child_usage = P.handle_with_usage ~parent:(B.work budget) ~executable
    ~request_id ~operation:"select-synthetic" producer_payload in
  let exit_code = if get "outcome" production=string "unsupported" then 2
    else if get "selected_strategy" (get "record" production)=Json.Null then 1 else 0 in
  let result = Json.Object ["schema_version",get "result_schema" profile;"profile",get "profile" profile;
    "service_implementation",string implementation_version;"resources",resources control;
    "validation_scope",get "validation_scope" profile;"claim_scope",get "claim_scope" profile;
    "supplied_authority_fingerprint",string supplied_authority;"supplied_build_request_fingerprint",string supplied_build;
    "build_request_fingerprint",string (Q.fingerprint request);"normalized_build_request",Q.to_json request;
    "production_payload",producer_payload;"production",production;
    "presentation",Json.Object ["frame_count",Json.int (List.length (Q.history request));"exit_code",Json.int exit_code]] in
  B.reserve_report budget result;
  let request = {Protocol.request_id;operation;payload} in
  let response = Protocol.response ~executable ~request:(Some request) ~status:Protocol.Ok ~result:(Some result) [] in
  B.reserve_report budget response;
  let size = Legacy_ascii.measure response in B.charge budget (size.bytes+size.nodes);
  let usage = B.usage budget in
  result,{work_charged=initial-W.remaining ancestor;request_bytes=usage.request_bytes;
    report_bytes=usage.report_bytes;retained_peak=retained+child_usage.retained_peak}
let handle ?parent ~executable ~request_id ~operation payload =
  fst (handle_with_usage ?parent ~executable ~request_id ~operation payload)
