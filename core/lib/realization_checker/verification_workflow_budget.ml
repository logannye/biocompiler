open Bioc_wire
module W = Bioc_checker.Work_budget
module X = Bioc_domain.Verification_exploration
let resource_profile = "biocompiler.verification_workflow.resources.v1"
let maximum_bytes = 64 * 1024 * 1024
let maximum_nodes = 1_000_000
let maximum_live_items = 8 * maximum_nodes
let workspace_items = 2 * maximum_nodes
let maximum_request_bytes = 80 * 1024 * 1024 + 65_536
let maximum_request_nodes = 2 * maximum_nodes
let maximum_evaluations = 100_000
let leaf_work = 50_000_000
let leaf_bytes = Limits.max_response_bytes
(* Legacy Check_result counts values only; native leaves count values and keys.
   Generic callbacks and historical imports must retain the larger legacy cap. *)
let legacy_leaf_nodes = 2 * Limits.max_json_nodes
let measure_bound bytes nodes = 88*bytes + 4608*nodes + 1
let fingerprint_bound bytes nodes = 181*bytes + 9216*nodes + 3
let history_bound bytes nodes = 320*bytes + 14000*nodes + 8
let generation_bound bytes nodes = measure_bound bytes nodes + 256*bytes + 128*nodes + 131072
let signature_bound = 160*leaf_bytes + 1024*legacy_leaf_nodes + maximum_bytes + 16384
let reduction_trial_work = history_bound maximum_bytes maximum_nodes +
  4*measure_bound leaf_bytes legacy_leaf_nodes + 2*fingerprint_bound leaf_bytes legacy_leaf_nodes +
  signature_bound + 32*leaf_bytes + 8*maximum_nodes + 16_000_000
let exploration_trial_work = generation_bound maximum_bytes maximum_nodes +
  history_bound maximum_bytes maximum_nodes + 5*measure_bound leaf_bytes legacy_leaf_nodes +
  2*fingerprint_bound leaf_bytes legacy_leaf_nodes + 32*leaf_bytes + 8*maximum_nodes + 16_000_000
let retained_validation_work = generation_bound maximum_bytes maximum_nodes +
  history_bound maximum_bytes maximum_nodes + measure_bound leaf_bytes legacy_leaf_nodes +
  2*fingerprint_bound leaf_bytes legacy_leaf_nodes + 16*leaf_bytes + 8*maximum_nodes + 8_000_000
let maximum_retained_checks = maximum_nodes / 51
let aggregation_work = 128*fingerprint_bound maximum_bytes maximum_nodes +
  128*measure_bound maximum_bytes maximum_nodes + 256*maximum_bytes + 256*maximum_nodes + 400_000_000
let reduction_work = maximum_evaluations * (leaf_work + reduction_trial_work) + aggregation_work
let exploration_work = (maximum_retained_checks+1) * (leaf_work+exploration_trial_work) +
  2*maximum_retained_checks*retained_validation_work + aggregation_work
let adversarial_work = 1005 * (generation_bound maximum_bytes maximum_nodes +
  4*measure_bound maximum_bytes maximum_nodes + 2*fingerprint_bound maximum_bytes maximum_nodes +
  32*maximum_bytes + 8*maximum_nodes + 16_000_000) + aggregation_work
let maximum_work = max reduction_work (max exploration_work adversarial_work)
let () = Diagnostic.require (maximum_work > 0 && maximum_work <= max_int && maximum_work <= 9_007_199_254_740_991)
    "workflow_limits" "Workflow work profile must fit a native integer and exact JSON integer transport."
type limits = { max_work:int; max_monitor_items:int; max_request_bytes:int;
  max_report_bytes:int; max_report_nodes:int }
let make_limits ?(max_work=maximum_work) ?(max_monitor_items=maximum_live_items)
    ?(max_request_bytes=maximum_request_bytes) ?(max_report_bytes=maximum_bytes)
    ?(max_report_nodes=maximum_nodes) () =
  List.iter (fun (value,ceiling) -> Diagnostic.require (value>0 && value<=ceiling)
      "workflow_limits" "Workflow limits must be positive reductions of the declared profile.")
    [max_work,maximum_work;max_monitor_items,maximum_live_items;max_request_bytes,maximum_request_bytes;
     max_report_bytes,maximum_bytes;max_report_nodes,maximum_nodes];
  {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
let default_limits = make_limits ()
let limits_json x = Json.Object [
  "profile",Json.String resource_profile;"max_work",Json.int x.max_work;
  "max_monitor_items",Json.int x.max_monitor_items;"max_request_bytes",Json.int x.max_request_bytes;
  "max_report_bytes",Json.int x.max_report_bytes;"max_report_nodes",Json.int x.max_report_nodes;
  "max_request_nodes",Json.int maximum_request_nodes;
  "max_workspace_items",Json.int workspace_items;
  "max_artifact_bytes",Json.int maximum_bytes;"max_artifact_nodes",Json.int maximum_nodes;"max_evaluations",Json.int maximum_evaluations;
  "max_evaluation_work",Json.int (min leaf_work x.max_work);
  "aggregation_work_allowance",Json.int aggregation_work;
  "max_reduction_trial_work",Json.int reduction_trial_work;
  "max_exploration_trial_work",Json.int exploration_trial_work;
  "max_retained_validation_work",Json.int retained_validation_work;
  "max_retained_checks",Json.int maximum_retained_checks;
  "max_callback_report_nodes",Json.int legacy_leaf_nodes;
  "max_callback_report_bytes",Json.int leaf_bytes;
  "work_integer_encoding",Json.String "exact_json_integer_below_2_to_53";
  "canonical_encoding",Json.String "compact_utf8";
  "node_accounting",Json.String "values_and_object_keys";
  "report_accounting",Json.String "incremental_records_transfer_to_complete_final_publication";
  "retention_accounting",Json.String "live_items_released_only_when_discarded_work_never_refunded";
  "work_accounting",Json.String "single_ancestor_for_import_all_evaluations_validation_replay_and_publication"]
type t = { limits:limits; work:W.t; initial:int; mutable evaluations:int;
  mutable request_bytes:int; mutable request_nodes:int; mutable fragment_bytes:int;
  mutable fragment_nodes:int; mutable report_bytes:int; mutable report_nodes:int;
  mutable retained:int; mutable scoped:int; mutable retained_peak:int }
let create ?(limits=default_limits) ?parent () =
  let work = match parent with None -> W.create ~profile:resource_profile
      ~error_code:"workflow_work_limit" ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile
        ~error_code:"workflow_work_limit" ~maximum:limits.max_work () in
  {limits;work;initial=W.remaining work;evaluations=0;request_bytes=0;request_nodes=0;
   fragment_bytes=0;fragment_nodes=0;report_bytes=0;report_nodes=0;retained=0;scoped=0;retained_peak=0}
let limits value = value.limits
let work value = value.work
let charge value amount = W.charge value.work amount
let codec maximum_bytes maximum_nodes parent = X.Codec.make_limits
    ~max_bytes:maximum_bytes ~max_nodes:maximum_nodes ~charge:(W.charge parent) ()
let input_codec value = codec (min maximum_bytes value.limits.max_request_bytes) maximum_nodes value.work
let report_codec value = codec value.limits.max_report_bytes value.limits.max_report_nodes value.work
let evaluation_codec value _parent = report_codec value
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
let retain value amount =
  Diagnostic.require (amount>=0 && amount<=value.limits.max_monitor_items-value.retained)
    "workflow_retention_limit" "Live workflow inventory exceeds its declared bound.";
  charge value amount;
  value.retained <- value.retained+amount;
  value.retained_peak <- max value.retained_peak value.retained
let release value amount =
  Diagnostic.require (amount>=0 && amount<=value.retained-value.scoped) "workflow_limits"
    "Cannot release workflow inventory that is not retained.";
  value.retained <- value.retained-amount
let with_retained value amount action =
  retain value amount;
  value.scoped <- value.scoped+amount;
  Fun.protect action ~finally:(fun () -> value.scoped <- value.scoped-amount; release value amount)
let with_workspace value action = with_retained value workspace_items action
let reserve_request value raw = with_workspace value (fun () ->
  let size = X.Codec.measure ~limits:(input_codec value) raw in
  Diagnostic.require (size.bytes < value.limits.max_request_bytes-value.request_bytes
    && size.nodes <= maximum_request_nodes-value.request_nodes) "workflow_input_limit"
    "Complete workflow authority exceeds the aggregate input inventory.";
  value.request_bytes <- value.request_bytes+size.bytes+1;
  value.request_nodes <- value.request_nodes+size.nodes)
let history_size value history =
  let codec = input_codec value in
  let bytes = ref 2 and nodes = ref 1 and count = ref 0 in
  let rec frames = function
    | [] -> ()
    | frame::tail ->
        charge value 1;
        Diagnostic.require (!count < maximum_nodes) "workflow_input_limit" "Workflow history list exceeds its bound.";
        let frame_nodes = ref 7 and names = ref 0 in
        let samples values = List.iter (fun (name,_) -> charge value 1;
          frame_nodes := !frame_nodes+10; names := !names+String.length name) values in
        samples (Bioc_domain.Execution_data.Input_frame.signals frame);
        List.iter (fun (name,values) -> charge value 1; frame_nodes := !frame_nodes+2;
          names := !names+String.length name; samples values)
          (Bioc_domain.Execution_data.Input_frame.contacts frame);
        Diagnostic.require (!frame_nodes <= maximum_nodes - !nodes) "workflow_input_limit"
          "Workflow history node inventory exceeds its bound.";
        charge value (2 * !frame_nodes + !names);
        let size = with_retained value !frame_nodes (fun () -> X.Codec.measure ~limits:codec
          (Bioc_domain.Execution_data.Input_frame.to_json frame)) in
        let added = size.bytes + (if !count=0 then 0 else 1) in
        Diagnostic.require (added <= min maximum_bytes value.limits.max_request_bytes - !bytes)
          "workflow_input_limit" "Workflow history bytes exceed its bound.";
        bytes:= !bytes+added; nodes:= !nodes+size.nodes; incr count; frames tail
  in frames history; ({bytes= !bytes;nodes= !nodes}:X.Codec.size)
let equal_json value left right = with_workspace value (fun () ->
  let limits = report_codec value in
  let a=X.Codec.measure ~limits left and b=X.Codec.measure ~limits right in
  (* Unique, finite JSON values have exactly the canonical equality implemented
     by Json.equal: object order is ignored, scalar kinds and signed zero remain. *)
  charge value (88*(a.bytes+b.bytes)+4608*(a.nodes+b.nodes)+2);
  Json.equal left right)
let encode_report value raw = with_workspace value (fun () -> X.Codec.encode ~limits:(report_codec value) raw)
let reserve_report_fragment value raw =
  let size = with_workspace value (fun () -> X.Codec.measure ~limits:(report_codec value) raw) in
  Diagnostic.require (size.bytes < value.limits.max_report_bytes-value.fragment_bytes
    && size.nodes <= value.limits.max_report_nodes-value.fragment_nodes)
    "workflow_report_limit" "Retained workflow records exceed the final publication inventory.";
  value.fragment_bytes <- value.fragment_bytes+size.bytes+1;
  value.fragment_nodes <- value.fragment_nodes+size.nodes
let publish value raw =
  let size = with_workspace value (fun () -> X.Codec.measure ~limits:(report_codec value) raw) in
  (* Transfer existing child inventories into the complete retained publication.
     Both inventories fit before the transfer; publication never refunds work. *)
  let previous = value.retained-value.scoped in
  retain value size.nodes;
  release value previous;
  value.report_bytes <- size.bytes;
  value.report_nodes <- size.nodes
type usage = { work_charged:int; evaluations:int; request_bytes:int; report_bytes:int;
  report_nodes:int; retained_peak:int }
let usage value = {work_charged=value.initial-W.remaining value.work;evaluations=value.evaluations;
  request_bytes=value.request_bytes;report_bytes=value.report_bytes;report_nodes=value.report_nodes;
  retained_peak=value.retained_peak}
