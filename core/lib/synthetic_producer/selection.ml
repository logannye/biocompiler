open Bioc_wire
open Bioc_domain
module B = Bioc_realization_checker.Realization_budget
module W = Bioc_checker.Work_budget
module Q = Bioc_realization_checker.Checked_request
module Check = Bioc_realization_checker.Synthetic_candidate_check
module S = Synthetic_selection
module A = Synthetic_authority
module C = A.Candidate
module E = Realization_evidence
let selection_version = S.selection_version
let implementation_version = "biocompiler.ocaml.synthetic_selection.v0.1"
type limits = { common:B.limits; max_work:int; max_monitor_items:int; max_request_bytes:int;
  max_report_bytes:int;max_report_nodes:int }
let make_limits ?(max_work=50_000_000) ?(max_monitor_items=100_000)
    ?(max_request_bytes=Limits.max_request_bytes) ?(max_report_bytes=Limits.max_response_bytes)
    ?(max_report_nodes=Limits.max_json_nodes) () =
  let common = B.make_limits ~max_work ~max_monitor_items ~max_request_bytes ~max_report_bytes ~max_report_nodes () in
  {common;max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile",Json.String "biocompiler.synthetic_selection.producer_resources.v1";
  "shared",B.limits_json limits.common;
  "strategies",Json.Array (List.map (fun value -> Json.String value) S.strategies);
  "child_retention",Json.String "remaining_aggregate_peak_retained_items";
  "publication",Json.String "all_alternatives_and_complete_result_reserved_cumulatively"]
type usage = {work_charged:int;request_bytes:int;report_bytes:int;retained_peak:int}
module type PROPOSER = sig
  val propose : config:A.Config.t -> limits:Generator.limits -> parent:W.t -> Realization_request.t -> C.t
end
module type SELECTOR = sig
  val select_with_usage : ?until:Runtime_number.t -> ?config:A.Config.t -> ?limits:limits -> ?parent:W.t ->
    Realization_request.t -> Execution_data.Input_frame.t list -> S.Result.t * usage
  val select : ?until:Runtime_number.t -> ?config:A.Config.t -> ?limits:limits -> ?parent:W.t ->
    Realization_request.t -> Execution_data.Input_frame.t list -> S.Result.t
end
let str value = Json.String value
let optional encode = function None -> Json.Null | Some value -> encode value
let raw_number = function Runtime_number.Integer value -> Json.Int value | Runtime_number.Real value -> Json.Float value
let strategy_config config strategy = A.Config.make ~profile_version:(A.Config.profile_version config)
  ~generator_version:(A.Config.generator_version config) ~catalog_fingerprint:(A.Config.catalog_fingerprint config)
  ~witness_selection:(A.Config.witness_selection config) ~conjunction_strategy:strategy ()
module Make (Proposer:PROPOSER) = struct
  let select_with_usage ?until ?config ?(limits=default_limits) ?parent request history =
    let config = match config with None -> A.Config.make () | Some value -> value in
    Diagnostic.require (S.valid_horizon until) "synthetic_selection" "Invalid selection horizon.";
    let budget = B.create ?parent ~limits:limits.common () in
    let work = B.work budget in
    let initial = W.remaining work in
    B.reserve_request budget (Json.Object ["request",Json.Null;"history",Json.Array [];
      "until",optional raw_number until;"config",A.Config.to_json config]);
    B.reserve_request budget (Realization_request.to_json request);
    let checked_request = Q.check ~parent:work request in
    (* Policy rejection precedes history materialization and all proposals. *)
    let policy = Generator.policy_for_request ~budget checked_request ~profile:(A.Config.profile_version config) in
    let history = B.bounded_list budget history in
    let retain count = B.retain_monitor budget count in
    let published_nodes = ref 0 in
    retain (List.length history);
    List.iter (fun frame -> B.reserve_request budget (Execution_data.Input_frame.to_json frame)) history;
    (* The input has already been cumulatively bounded. Precharge ASCII expansion
       and list construction before hashing the exact Python history spelling. *)
    B.charge budget (8 * ((B.usage budget).request_bytes+1));
    let raw_history = Json.Array (List.map Execution_data.Input_frame.to_json history) in
    let history_fingerprint = Legacy_ascii.fingerprint raw_history in
    let available_retention () =
      let remaining = limits.max_monitor_items - (B.usage budget).monitor_peak in
      if remaining<=0 then B.retain_monitor budget (limits.max_monitor_items+1);
      remaining in
    let report_capacity () =
      let remaining = limits.max_report_bytes-(B.usage budget).report_bytes in
      if remaining<=0 then B.reserve_report budget Json.Null;
      remaining in
    let node_capacity () =
      let remaining = limits.max_report_nodes - !published_nodes in
      if remaining<=0 then B.reserve_report budget Json.Null;
      remaining in
    let generator_limits () = Generator.make_limits ~max_work:limits.max_work
      ~max_monitor_items:(available_retention ()) ~max_request_bytes:limits.max_request_bytes
      ~max_report_bytes:(report_capacity ()) ~max_report_nodes:(node_capacity ()) () in
    let checker_limits () = Check.make_limits ~max_work:limits.max_work
      ~max_monitor_items:(available_retention ()) ~max_request_bytes:limits.max_request_bytes
      ~max_report_bytes:(report_capacity ()) ~max_report_nodes:(node_capacity ()) () in
    let publish_raw cost raw =
      (* Domain validation/fingerprint construction may scan each retained child
         several times. This charge precedes those scans and allocations. *)
      B.charge budget (16 * (cost+1));
      let size = Legacy_ascii.measure raw in
      B.reserve_report budget raw;
      (* The reservation above bounds depth/cycles and counts object keys too.
         Remaining child publication capacity must use that same census;
         retained JSON values keep their separate value-node accounting. *)
      let rec nodes = function
        | Json.Array values -> List.fold_left (fun total value -> total + nodes value) 1 values
        | Json.Object fields -> List.fold_left (fun total (_,value) -> total + 1 + nodes value) 1 fields
        | _ -> 1 in
      published_nodes := !published_nodes + nodes raw;
      retain size.nodes in
    let propose strategy =
      B.charge budget (8 * (A.Config.canonical_size config+1));
      let configuration = strategy_config config strategy in
      let result = try Ok (Proposer.propose ~config:configuration ~limits:(generator_limits ()) ~parent:work request)
        with Generator.Unsupported error -> Error error in
      match result with
      | Error error ->
          (* Catch only the historical unsupported-source exception. Resource,
             malformed candidate and independent checker errors propagate. *)
          let source_size = match error.source with None -> 0 | Some source ->
            String.length source.Behavior.file + String.length source.function_name + Z.numbits source.line + 128 in
          B.charge budget (4 * (String.length error.message + source_size+1));
          let generation_error = Generator.format_error error in
          let raw = Json.Object ["schema_version",str S.Alternative.schema_version;"strategy",str strategy;
            "candidate",Json.Null;"constraint_violations",Json.Array [];"check",Json.Null;
            "generation_error",str generation_error;"gate_count",Json.Null;"status",str "unsupported"] in
          publish_raw (String.length generation_error+512) raw;
          S.Alternative.make ~strategy ~generation_error ()
      | Ok candidate ->
          (* Retain the actual complete proposal while its independent check runs.
             A test proposer cannot bypass publication or retained-size limits. *)
          B.charge budget (8 * (C.canonical_size candidate+1));
          let candidate_size = Legacy_ascii.measure (C.to_json candidate) in
          retain candidate_size.nodes;
          let violations = Generator.violations ~budget policy (C.mechanism candidate) in
          let check = if violations<>[] then None else
            Some (Check.check ?until ~limits:(checker_limits ()) ~parent:work request candidate history) in
          let gate_count = List.fold_left (fun count node ->
            if List.mem (Mechanism.Node.kind node) ["input";"constant";"output"] then count else count+1)
            0 (Mechanism.nodes (C.mechanism candidate)) in
          let status = if violations<>[] then "hard_rejected" else
            (match E.Check_result.outcome (Option.get check) with
             E.Pass -> "pass" | E.Fail -> "fail" | E.Unknown -> "unknown" | E.Unsupported -> "unsupported") in
          let raw = Json.Object ["schema_version",str S.Alternative.schema_version;"strategy",str strategy;
            "candidate",C.to_json candidate;"constraint_violations",Json.Array (List.map str violations);
            "check",optional E.Check_result.to_json check;"generation_error",Json.Null;
            "gate_count",Json.int gate_count;"status",str status] in
          let cost = C.canonical_size candidate + Option.fold ~none:0 ~some:E.Check_result.canonical_size check +
            List.fold_left (fun total value -> total+String.length value) 512 violations in
          publish_raw cost raw;
          let alternative = S.Alternative.make ~strategy ~candidate ~constraint_violations:violations ?check () in
          B.release_monitor budget candidate_size.nodes;
          alternative in
    let alternatives = List.map propose S.strategies in
    let size = List.fold_left (fun size item -> size+S.Alternative.canonical_size item) 1024 alternatives in
    (* Reserve the complete prospective record before constructing its summaries,
       hashes and repeated child references. The longest possible strategy and
       outcome spellings bound each actual summary without changing its value. *)
    let raw = Json.Object ["schema_version",str S.Result.schema_version;"selection_version",str selection_version;
      "cost_version",str S.cost_version;"intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
      "request_fingerprint",str (Q.fingerprint checked_request);"history_fingerprint",str history_fingerprint;
      "until",optional raw_number until;"config",A.Config.to_json config;"minimize",str (Generator.minimize policy);
      "alternatives",Json.Array (List.map S.Alternative.to_json alternatives);
      "selected_strategy",str "de_morgan";"outcome",str "unsupported";
      "checked_candidates",Json.int 2;"rejected_candidates",Json.int 2;
      "search_scope",str "two_whole_program_conjunction_strategies"] in
    publish_raw size raw;
    let result = S.Result.make ~request_fingerprint:(Q.fingerprint checked_request) ~history_fingerprint
      ?until ~config ~minimize:(Generator.minimize policy) alternatives in
    let usage = B.usage budget in
    result,{work_charged=initial-W.remaining work;request_bytes=usage.request_bytes;
      report_bytes=usage.report_bytes;retained_peak=usage.monitor_peak}
  let select ?until ?config ?limits ?parent request history =
    fst (select_with_usage ?until ?config ?limits ?parent request history)
end
module Production = Make (struct
  let propose ~config ~limits ~parent request = Generator.propose ~config ~limits ~parent request
end)
include Production
