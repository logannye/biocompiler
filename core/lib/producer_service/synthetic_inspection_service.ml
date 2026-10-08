open Bioc_wire
open Bioc_domain
module W = Bioc_checker.Work_budget
module B = Bioc_realization_checker.Realization_budget
module X = Verification_exploration.Codec
module E = Realization_evidence
module D = E.Dependency_snapshot
module R = E.Check_result
module Registry = Component_registry
module S = Component_selection
module P = Bioc_compiler.Component_selection_producer
let implementation_version = "biocompiler.ocaml.synthetic_inspection_service.v0.1"
let resource_profile = "biocompiler.core.synthetic_inspection.resources.v1"
let string value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let profile = Json.parse {profile|{"authority_encoding":"python-json-v1","check_result_queries":["coverage","freshness"],"claim_scope":"Fresh structural import and named helper computation over complete supplied historical authority only. Dependency freshness means equality of supplied snapshots; registry selection is freshly recomputed. No current whole-program acceptance, package/export acceptance, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"fingerprints":"sha256_complete_canonical_utf8_payload_each_supplied_input_and_value_no_omissions","freshness_fields":["changed_dependencies","fresh","status"],"implementation":"biocompiler.ocaml.synthetic_inspection_service.v0.1","limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"operations":["inspect-synthetic-mechanism","inspect-synthetic-check-result","compare-synthetic-dependencies","lock-synthetic-registry","resolve-synthetic-registry","select-synthetic-registry","verify-synthetic-registry-selection","inspect-synthetic-registry-selection"],"payload_fields":{"compare-synthetic-dependencies":["profile","limits","previous","current"],"inspect-synthetic-check-result":["profile","limits","record","query","current"],"inspect-synthetic-mechanism":["profile","limits","mechanism"],"inspect-synthetic-registry-selection":["profile","limits","selection"],"lock-synthetic-registry":["profile","limits","registry","instances"],"resolve-synthetic-registry":["profile","limits","registry","lock"],"select-synthetic-registry":["profile","limits","registry","request"],"verify-synthetic-registry-selection":["profile","limits","registry","request","selection"]},"profile":"biocompiler.core.synthetic_inspection.v1","resources":{"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.synthetic_inspection.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_value_complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_inspection_payload","work_accounting":"one_ancestor_for_framing_bounded_import_helpers_replay_hashes_and_final_publication"},"selection":{"ancestor":"same_inspection_request_ancestor","max_components":10000,"profile":"biocompiler.component_selection_producer.resources.v1"},"structural_import":{"comparison_accounting":"complete_import_bytes_plus_bounded_pairwise_identifier_bytes","precharged_byte_multiplier":128,"retention":"all_supplied_json_values_and_object_keys_plus_resolved_component_occurrences"}},"result_fields":["schema_version","profile","service_implementation","operation","resources","validation_scope","claim_scope","supplied_authority_fingerprint","input_fingerprints","value","value_fingerprint"],"result_schema":"biocompiler.core.synthetic_inspection_result.v1","role":"bioc-core","validation_scope":"supplied-synthetic-authority-helper-inspection-only-v1","value_fields":{"compare-synthetic-dependencies":["changed_dependencies"],"inspect-synthetic-check-result":["exercised_requirement_ids","freshness"],"inspect-synthetic-mechanism":["nodes"],"inspect-synthetic-registry-selection":["outcome"],"lock-synthetic-registry":["lock"],"resolve-synthetic-registry":["instances"],"select-synthetic-registry":["selection","outcome"],"verify-synthetic-registry-selection":["valid"]},"verify_selection_null":"false_after_structural_registry_and_request_import_without_selection_replay","wire_encoding":"python-json-v1"}|profile}
let operations = List.map Json.string (Json.array (get "operations" profile))
let validation_scopes = [Json.string (get "validation_scope" profile)]
let profiles = ["synthetic_inspection",profile]
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
        | _ -> Diagnostic.fail ~path:("payload.limits." ^ key) "synthetic_inspection_limits"
            "Synthetic inspection limits must be positive integer reductions of the native profile." in
      let max_work = value "max_work" defaults.max_work in
      let max_monitor_items = value "max_monitor_items" defaults.max_monitor_items in
      let max_request_bytes = value "max_request_bytes" defaults.max_request_bytes in
      let max_report_bytes = value "max_report_bytes" defaults.max_report_bytes in
      let max_report_nodes = value "max_report_nodes" defaults.max_report_nodes in
      {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
  | _ -> Diagnostic.fail ~path:"payload.limits" "synthetic_inspection_limits"
      "Synthetic inspection limits must be null or an exact object of five integer reductions."
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
      "Complete synthetic inspection request exceeds the fixed transport byte limit.";
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
         | Json.Float _ as value -> W.charge work 4096; add (String.length (Canonical.encode value)); visit rest
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
(* Constructors below retain their fixed structural limits. Reserve their complete
   raw authority and a conservative 128 byte-work passes before entering them:
   nested domain constructors, sorted identity inventories, escaped historical
   JSON and SHA-256 are covered without granting a second work allowance. The
   streaming codec charges its own exact walk separately. No input hash omits
   unknown fields; domain exact-field validation remains authoritative. *)
let import budget control ~path decode raw =
  let limits = X.make_limits ~max_bytes:control.max_request_bytes ~max_nodes:Limits.max_json_nodes
    ~charge:(B.charge budget) () in
  let size = X.measure ~limits ~path raw in
  B.charge budget (128 * (size.bytes + 1));
  decode ?path:(Some path) raw
let dependency budget control ~path raw =
  (match raw with Json.Object _ -> () | _ -> Diagnostic.fail ~path "synthetic_inspection_type"
      "Freshness comparison requires a DependencySnapshot.");
  import budget control ~path D.of_json raw
let strings values = Json.Array (List.map string values)
let freshness value = Json.Object ["changed_dependencies",strings (E.Freshness_report.changed_dependencies value);
  "fresh",Json.Bool (E.Freshness_report.fresh value);"status",string (E.Freshness_report.status value)]
let selection_limits control = P.make_limits ~max_work:control.max_work
  ~max_input_bytes:control.max_request_bytes ~max_output_bytes:control.max_report_bytes
  ~max_output_nodes:control.max_report_nodes ()
let evaluate budget control operation fields =
  let raw key = Json.field key fields in
  let decode key decoder = import budget control ~path:("payload."^key) decoder (raw key) in
  match operation with
  | "inspect-synthetic-mechanism" ->
      let mechanism = decode "mechanism" Mechanism.of_json in
      Json.Object ["nodes",Json.Array (List.map Mechanism.Node.to_json (Mechanism.topological_nodes mechanism))]
  | "inspect-synthetic-check-result" ->
      let record = decode "record" R.of_json in
      let query = raw "query" in
      Diagnostic.require ~path:"payload.query" (query=string "coverage" || query=string "freshness")
        "synthetic_inspection_query" "Unsupported check-result inspection query.";
      let report = if query=string "coverage" then begin
        Diagnostic.require ~path:"payload.current" (raw "current"=Json.Null)
          "synthetic_inspection_query" "Coverage inspection requires current=null.";
        Json.Null
      end else
        let current = dependency budget control ~path:"payload.current" (raw "current") in
        freshness (R.freshness record current) in
      Json.Object ["exercised_requirement_ids",strings (R.exercised_requirement_ids record);"freshness",report]
  | "compare-synthetic-dependencies" ->
      let previous = dependency budget control ~path:"payload.previous" (raw "previous") in
      let current = dependency budget control ~path:"payload.current" (raw "current") in
      Json.Object ["changed_dependencies",strings (D.changed previous current)]
  | "lock-synthetic-registry" ->
      let registry = decode "registry" Registry.of_json in
      let instances = Json.object_fields ~path:"payload.instances" (raw "instances") in
      let instances = List.map (fun (id,raw) ->
        id,import budget control ~path:("payload.instances/"^id) Component.of_json raw) instances in
      Json.Object ["lock",Registry.Lock.to_json (Registry.lock registry instances)]
  | "resolve-synthetic-registry" ->
      let registry = decode "registry" Registry.of_json in
      let lock = decode "lock" Registry.Lock.of_json in
      (* Resolve can repeat a large component under many instance IDs. Reserve
         worst-case expansion before invoking its internal lock replay. The
         ordinary resolver still decides every identity and dependency error. *)
      let count = List.length (Registry.Lock.components lock) in
      let maximum = List.fold_left (fun size component -> max size (String.length (Canonical.encode (Component.to_json component))))
        1 (Registry.components registry) in
      B.charge budget (128 * count * (maximum + 1));
      B.retain_monitor budget count;
      let resolved = Registry.resolve registry lock in
      let output = W.create_output ~profile:resource_profile ~error_code:"realization_report_limit"
        ~max_bytes:control.max_report_bytes ~max_nodes:control.max_report_nodes () in
      W.reserve_json output (Json.Object []);
      List.iter (fun (id,component) ->
        W.reserve_json output (string id); W.reserve_json output (Component.to_json component)) resolved;
      Json.Object ["instances",Json.Object (List.map (fun (id,component) -> id,Component.to_json component) resolved)]
  | "select-synthetic-registry" | "verify-synthetic-registry-selection" ->
      let registry = decode "registry" Registry.of_json in
      let request = decode "request" S.Request.of_json in
      B.retain_monitor budget (List.length (Registry.components registry));
      let limits = selection_limits control in
      if operation="select-synthetic-registry" then
        let result = P.select ~limits ~parent:(B.work budget) ~registry ~request () in
        Json.Object ["selection",S.Result.to_json result;"outcome",string (S.Result.outcome_name (S.Result.outcome result))]
      else
        let valid = if raw "selection"=Json.Null then false else
          let supplied = decode "selection" S.Result.of_json in
          P.verify_selection ~limits ~parent:(B.work budget) ~registry ~request supplied in
        Json.Object ["valid",Json.Bool valid]
  | "inspect-synthetic-registry-selection" ->
      let result = decode "selection" S.Result.of_json in
      Json.Object ["outcome",string (S.Result.outcome_name (S.Result.outcome result))]
  | _ -> Diagnostic.fail "unsupported_operation" "Unsupported synthetic inspection operation."
let handle_with_usage ?parent ~executable ~request_id ~operation payload =
  Diagnostic.require (executable=Protocol.Core && List.mem operation operations)
    "unsupported_operation" "Synthetic inspection is available only in the producer executable.";
  let ancestor = match parent with
    | None -> W.create ~profile:resource_profile ~error_code:"synthetic_inspection_work_limit" ~maximum:defaults.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"synthetic_inspection_work_limit" ~maximum:defaults.max_work () in
  let initial = W.remaining ancestor in
  W.charge ancestor 1;
  preflight_transport ancestor (Json.Object ["protocol",string Protocol.version;"request_id",string request_id;
    "operation",string operation;"payload",payload]);
  let fields = Json.object_fields ~path:"payload" payload in
  let expected = List.map Json.string (Json.array (get operation (get "payload_fields" profile))) in
  Json.exact_fields ~path:"payload" expected fields;
  Diagnostic.require ~path:"payload.profile" (Json.field "profile" fields=get "profile" profile)
    "synthetic_inspection_profile" "Unsupported synthetic inspection profile.";
  let control = controls (Json.field "limits" fields) in
  let prefix = initial-W.remaining ancestor in
  Diagnostic.require (prefix<=control.max_work) "synthetic_inspection_work_limit"
    "Synthetic inspection framing exceeds the selected work limit.";
  let reduced = W.nested ~parent:ancestor ~profile:resource_profile ~error_code:"synthetic_inspection_work_limit"
    ~maximum:(control.max_work-prefix) () in
  let budget = B.create ~parent:reduced ~limits:(common_limits control) () in
  B.reserve_request budget payload;
  let limits = X.make_limits ~max_bytes:control.max_request_bytes ~max_nodes:Limits.max_json_nodes
    ~charge:(B.charge budget) () in
  let size = X.measure ~limits ~path:"payload" payload in
  B.retain_monitor budget size.nodes;
  B.charge budget (5 * (size.bytes + size.nodes + 1));
  let supplied_authority = Canonical.fingerprint payload in
  let input_fingerprints = Json.Object (List.filter_map (fun key ->
    if key="profile" || key="limits" then None else
      Some (key,string (Canonical.fingerprint (Json.field key fields)))) expected) in
  let value = evaluate budget control operation fields in
  B.reserve_report budget value;
  let value_size = Legacy_ascii.measure value in
  B.charge budget (5 * (value_size.bytes + value_size.nodes + 1));
  let result = Json.Object ["schema_version",get "result_schema" profile;"profile",get "profile" profile;
    "service_implementation",string implementation_version;"operation",string operation;
    "resources",resources control;"validation_scope",get "validation_scope" profile;"claim_scope",get "claim_scope" profile;
    "supplied_authority_fingerprint",string supplied_authority;"input_fingerprints",input_fingerprints;
    "value",value;"value_fingerprint",string (Canonical.fingerprint value)] in
  B.reserve_report budget result;
  let request = {Protocol.request_id;operation;payload} in
  let response = Protocol.response ~executable ~request:(Some request) ~status:Protocol.Ok ~result:(Some result) [] in
  B.reserve_report budget response;
  let size = Legacy_ascii.measure response in B.charge budget (size.bytes+size.nodes);
  let usage = B.usage budget in
  result,{work_charged=initial-W.remaining ancestor;request_bytes=usage.request_bytes;
    report_bytes=usage.report_bytes;retained_peak=usage.monitor_peak}
let handle ?parent ~executable ~request_id ~operation payload =
  fst (handle_with_usage ?parent ~executable ~request_id ~operation payload)
