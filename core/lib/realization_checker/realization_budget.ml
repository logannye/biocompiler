open Bioc_wire
module W = Bioc_checker.Work_budget
module E = Bioc_domain.Realization_evidence
let resource_profile = "biocompiler.realization_checker.resources.v1"
type limits = { max_work : int; max_monitor_items : int; max_request_bytes : int;
  max_report_bytes : int; max_report_nodes : int }
let make_limits ?(max_work = 50_000_000) ?(max_monitor_items = 100_000)
    ?(max_request_bytes = Limits.max_request_bytes) ?(max_report_bytes = Limits.max_response_bytes)
    ?(max_report_nodes = Limits.max_json_nodes) () =
  List.iter (fun (value, maximum) -> Diagnostic.require (value > 0 && value <= maximum)
      "realization_limits" "Realization limits must be positive reductions of the native profile.")
    [max_work, 50_000_000; max_monitor_items, 100_000;
     max_request_bytes, Limits.max_request_bytes; max_report_bytes, Limits.max_response_bytes;
     max_report_nodes, Limits.max_json_nodes];
  {max_work; max_monitor_items; max_request_bytes; max_report_bytes; max_report_nodes}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile", Json.String resource_profile;
  "max_work", Json.int limits.max_work; "max_monitor_items", Json.int limits.max_monitor_items;
  "max_request_bytes", Json.int limits.max_request_bytes;
  "max_request_nodes", Json.int Limits.max_json_nodes;
  "max_report_bytes", Json.int limits.max_report_bytes;
  "max_report_nodes", Json.int limits.max_report_nodes;
  "report_encoding", Json.String "compact_ensure_ascii_true";
  "fragment_punctuation", Json.String "one_conservative_separator_byte_per_request_or_report_fragment";
  "publication_work", Json.String "same_shared_work_ascii_bytes_plus_key_value_nodes";
  "failure_publication", Json.String "request_bounded_capacity_held_outside_engine_allocation"]
type t = { limits : limits; work : W.t; request : W.output; report : W.output;
  mutable charged : int; mutable failed_work : int; mutable retained : int;
  mutable peak : int; mutable request_bytes : int; mutable report_bytes : int;
  mutable resource_error : Diagnostic.t option }
let create ?parent ?(limits = default_limits) () =
  let work = match parent with None -> W.create ~profile:resource_profile
      ~error_code:"realization_work_limit" ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile
        ~error_code:"realization_work_limit" ~maximum:limits.max_work () in
  {limits; work; request = W.create_output ~profile:resource_profile
      ~error_code:"realization_input_limit" ~max_bytes:limits.max_request_bytes ~max_nodes:Limits.max_json_nodes ();
   report = W.create_output ~profile:resource_profile ~error_code:"realization_report_limit"
      ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes ();
   charged = 0; failed_work = 0; retained = 0; peak = 0; request_bytes = 0;
   report_bytes = 0; resource_error = None}
let work budget = budget.work
let remaining budget = W.remaining budget.work
let charge budget amount = W.charge budget.work amount; budget.charged <- budget.charged + amount
let resource budget code message =
  let diagnostic = {Diagnostic.code; message; path = None} in
  budget.resource_error <- Some diagnostic; raise (Diagnostic.Error diagnostic)
let is_resource_error budget error = W.is_exhaustion budget.work error ||
  match budget.resource_error with Some previous -> previous == error | None -> false
let bound budget condition code message = if not condition then resource budget code message
let bounded_list budget values =
  let rec visit count = function [] -> () | _ :: rest ->
    bound budget (count < Limits.max_json_nodes) "realization_input_limit"
      "A native input list exceeds the fixed value-node bound.";
    charge budget 1; visit (count + 1) rest in
  visit 0 values; values
let ascii_measure budget raw =
  try Legacy_ascii.measure raw with
  | Diagnostic.Error error when error.code = "legacy_ascii_limit" || error.code = "legacy_ascii_cycle" ->
      resource budget "realization_report_limit" error.message
let reserve_output budget output raw =
  try W.reserve_json output raw with Diagnostic.Error error
    when error.code = "realization_input_limit" || error.code = "realization_report_limit" ->
      budget.resource_error <- Some error; raise (Diagnostic.Error error)
let count_nodes budget raw =
  let count = ref 0 and pending = ref [raw] in
  while !pending <> [] do
    incr count;
    bound budget (!count <= Limits.max_json_nodes) "realization_input_limit"
      "A supplied record exceeds the native key/value node bound.";
    let item = List.hd !pending in pending := List.tl !pending;
    match item with
    | Json.Array values -> pending := List.rev_append values !pending
    | Json.Object fields -> count := !count + List.length fields;
        pending := List.rev_append (List.rev_map snd fields) !pending
    | _ -> ()
  done;
  bound budget (!count <= Limits.max_json_nodes) "realization_input_limit"
    "A supplied record exceeds the native key/value node bound.";
  !count
let reserve_request budget raw =
  (* The streaming reservation terminates on cyclic values/list spines before
     the following bounded encoding and node traversal are allowed. *)
  reserve_output budget budget.request raw;
  let bytes = String.length (Canonical.encode raw) in
  bound budget (bytes < budget.limits.max_request_bytes - budget.request_bytes)
    "realization_input_limit" "Cumulative supplied input including separators exceeds its byte budget.";
  let nodes = count_nodes budget raw in charge budget (bytes + nodes + 1);
  budget.request_bytes <- budget.request_bytes + bytes + 1
let reserve_report budget raw =
  let size = ascii_measure budget raw in
  (* One separator byte is reserved per fragment, including first fragments;
     the conservative punctuation reserve is part of the native profile. *)
  bound budget (size.bytes < budget.limits.max_report_bytes - budget.report_bytes)
    "realization_report_limit" "Cumulative ASCII evidence publication exceeds its byte budget.";
  reserve_output budget budget.report raw;
  charge budget (size.bytes + count_nodes budget raw);
  budget.report_bytes <- budget.report_bytes + size.bytes + 1
let validate_report budget result =
  let raw = E.Check_result.to_json result in
  let size = ascii_measure budget raw in
  bound budget (size.bytes <= budget.limits.max_report_bytes) "realization_report_limit"
    "Complete ASCII evidence publication exceeds its byte budget.";
  let output = W.create_output ~profile:resource_profile ~error_code:"realization_report_limit"
      ~max_bytes:budget.limits.max_report_bytes ~max_nodes:budget.limits.max_report_nodes () in
  reserve_output budget output raw;
  charge budget (size.bytes + count_nodes budget raw)
let failure_finish_allowance budget =
  (* Current engine errors use fixed prose and input identifiers/source fields.
     Their escaped JSON spelling is bounded by twice the ASCII escape expansion
     of the entire supplied request, plus fixed prose. Every valid diagnostic
     also obeys the 4 MiB string ceiling. Final publication adds the already
     reserved dependency/checked-ID envelope. A JSON node costs at least one
     encoded byte, hence twice the byte bound covers the traversal charge. *)
  let message = min (6 * Limits.max_string_bytes) (12 * budget.request_bytes + 4096) in
  2 * (budget.report_bytes + 2 * (message + 512))
let retain_monitor budget count =
  Diagnostic.require (count >= 0) "realization_limits" "Retention charges cannot be negative.";
  bound budget (count <= budget.limits.max_monitor_items - budget.retained) "realization_monitor_limit"
    "Finite-history monitor state exceeds its native bound.";
  budget.retained <- budget.retained + count; budget.peak <- max budget.peak budget.retained
let release_monitor budget count =
  Diagnostic.require (count >= 0 && count <= budget.retained) "realization_limits"
    "Cannot release unreserved monitor state.";
  budget.retained <- budget.retained - count
let burn_failure budget amount = charge budget amount; budget.failed_work <- budget.failed_work + amount
type usage = { work_charged : int; reserved_failure_work : int; monitor_peak : int;
  request_bytes : int; report_bytes : int }
let usage budget = {work_charged = budget.charged; reserved_failure_work = budget.failed_work;
  monitor_peak = budget.peak; request_bytes = budget.request_bytes; report_bytes = budget.report_bytes}
