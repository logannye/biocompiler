open Bioc_wire
module W = Bioc_checker.Work_budget
module X = Bioc_domain.Verification_exploration
let resource_profile = "biocompiler.verification_workflow.resources.v1"
let maximum_bytes = 64 * 1024 * 1024
let maximum_nodes = 1_000_000
let maximum_request_bytes = 80 * 1024 * 1024 + 65_536
let maximum_request_nodes = 2 * maximum_nodes
let maximum_evaluations = 100_000
let leaf_work = 50_000_000
let maximum_work = maximum_evaluations * leaf_work + 32 * maximum_bytes
type limits = { max_work:int; max_monitor_items:int; max_request_bytes:int;
  max_report_bytes:int; max_report_nodes:int }
let make_limits ?(max_work=maximum_work) ?(max_monitor_items=maximum_nodes)
    ?(max_request_bytes=maximum_request_bytes) ?(max_report_bytes=maximum_bytes)
    ?(max_report_nodes=maximum_nodes) () =
  List.iter (fun (value,ceiling) -> Diagnostic.require (value>0 && value<=ceiling)
      "workflow_limits" "Workflow limits must be positive reductions of the declared profile.")
    [max_work,maximum_work;max_monitor_items,maximum_nodes;max_request_bytes,maximum_request_bytes;
     max_report_bytes,maximum_bytes;max_report_nodes,maximum_nodes];
  {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
let default_limits = make_limits ()
let limits_json x = Json.Object [
  "profile",Json.String resource_profile;"max_work",Json.int x.max_work;
  "max_monitor_items",Json.int x.max_monitor_items;"max_request_bytes",Json.int x.max_request_bytes;
  "max_report_bytes",Json.int x.max_report_bytes;"max_report_nodes",Json.int x.max_report_nodes;
  "max_request_nodes",Json.int maximum_request_nodes;
  "max_artifact_bytes",Json.int maximum_bytes;"max_artifact_nodes",Json.int maximum_nodes;"max_evaluations",Json.int maximum_evaluations;
  "max_evaluation_work",Json.int (min leaf_work x.max_work);
  "aggregation_work_allowance",Json.int (32 * maximum_bytes);
  "canonical_encoding",Json.String "compact_utf8";
  "node_accounting",Json.String "values_and_object_keys";
  "report_accounting",Json.String "incremental_records_transfer_to_complete_final_publication";
  "retention_accounting",Json.String "live_items_released_only_when_discarded_work_never_refunded";
  "work_accounting",Json.String "single_ancestor_for_import_all_evaluations_validation_replay_and_publication"]
type t = { limits:limits; work:W.t; initial:int; mutable evaluations:int;
  mutable request_bytes:int; mutable request_nodes:int; mutable fragment_bytes:int;
  mutable fragment_nodes:int; mutable report_bytes:int; mutable report_nodes:int;
  mutable retained:int; mutable retained_peak:int }
let create ?(limits=default_limits) ?parent () =
  let work = match parent with None -> W.create ~profile:resource_profile
      ~error_code:"workflow_work_limit" ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile
        ~error_code:"workflow_work_limit" ~maximum:limits.max_work () in
  {limits;work;initial=W.remaining work;evaluations=0;request_bytes=0;request_nodes=0;
   fragment_bytes=0;fragment_nodes=0;report_bytes=0;report_nodes=0;retained=0;retained_peak=0}
let limits value = value.limits
let work value = value.work
let charge value amount = W.charge value.work amount
let codec maximum_bytes maximum_nodes parent = X.Codec.make_limits
    ~max_bytes:maximum_bytes ~max_nodes:maximum_nodes ~charge:(W.charge parent) ()
let input_codec value = codec (min maximum_bytes value.limits.max_request_bytes) maximum_nodes value.work
let report_codec value = codec value.limits.max_report_bytes value.limits.max_report_nodes value.work
let evaluation_codec value parent = codec value.limits.max_report_bytes value.limits.max_report_nodes parent
let evaluation value =
  Diagnostic.require (value.evaluations < maximum_evaluations) "workflow_evaluation_limit"
    "Workflow evaluator count exceeds the declared maximum.";
  charge value 1;
  value.evaluations <- value.evaluations+1;
  W.nested ~parent:value.work ~profile:"biocompiler.verification_workflow.evaluation.v1"
    ~error_code:"workflow_evaluation_work_limit" ~maximum:(min leaf_work value.limits.max_work) ()
let realization_limits value =
  let x = value.limits in
  Realization_check.make_limits ~max_work:(min leaf_work x.max_work)
    ~max_monitor_items:(min 100_000 x.max_monitor_items)
    ~max_request_bytes:(min Limits.max_request_bytes x.max_request_bytes)
    ~max_report_bytes:(min Limits.max_response_bytes x.max_report_bytes)
    ~max_report_nodes:(min Limits.max_json_nodes x.max_report_nodes) ()
let synthetic_limits value =
  let x = value.limits in
  Synthetic_candidate_check.make_limits ~max_work:(min leaf_work x.max_work)
    ~max_monitor_items:(min 100_000 x.max_monitor_items)
    ~max_request_bytes:(min Limits.max_request_bytes x.max_request_bytes)
    ~max_report_bytes:(min Limits.max_response_bytes x.max_report_bytes)
    ~max_report_nodes:(min Limits.max_json_nodes x.max_report_nodes) ()
let reserve_request value raw =
  let size = X.Codec.measure ~limits:(input_codec value) raw in
  Diagnostic.require (size.bytes < value.limits.max_request_bytes-value.request_bytes
    && size.nodes <= maximum_request_nodes-value.request_nodes) "workflow_input_limit"
    "Complete workflow authority exceeds the aggregate input inventory.";
  value.request_bytes <- value.request_bytes+size.bytes+1;
  value.request_nodes <- value.request_nodes+size.nodes
let retain value amount =
  Diagnostic.require (amount>=0 && amount<=value.limits.max_monitor_items-value.retained)
    "workflow_retention_limit" "Live workflow inventory exceeds its declared bound.";
  charge value amount;
  value.retained <- value.retained+amount;
  value.retained_peak <- max value.retained_peak value.retained
let release value amount =
  Diagnostic.require (amount>=0 && amount<=value.retained) "workflow_limits"
    "Cannot release workflow inventory that is not retained.";
  value.retained <- value.retained-amount
let reserve_report_fragment value raw =
  let size = X.Codec.measure ~limits:(report_codec value) raw in
  Diagnostic.require (size.bytes < value.limits.max_report_bytes-value.fragment_bytes
    && size.nodes <= value.limits.max_report_nodes-value.fragment_nodes)
    "workflow_report_limit" "Retained workflow records exceed the final publication inventory.";
  value.fragment_bytes <- value.fragment_bytes+size.bytes+1;
  value.fragment_nodes <- value.fragment_nodes+size.nodes
let publish value raw =
  let size = X.Codec.measure ~limits:(report_codec value) raw in
  value.report_bytes <- size.bytes;
  value.report_nodes <- size.nodes
type usage = { work_charged:int; evaluations:int; request_bytes:int; report_bytes:int;
  report_nodes:int; retained_peak:int }
let usage value = {work_charged=value.initial-W.remaining value.work;evaluations=value.evaluations;
  request_bytes=value.request_bytes;report_bytes=value.report_bytes;report_nodes=value.report_nodes;
  retained_peak=value.retained_peak}
