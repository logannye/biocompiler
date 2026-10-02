open Bioc_wire
module X = Bioc_domain.Verification_exploration
module E = Bioc_domain.Realization_evidence
module N = Bioc_domain.Runtime_number
module F = Bioc_domain.Execution_data.Input_frame
module B = Verification_workflow_budget
module W = Bioc_checker.Work_budget
type evaluator = parent:W.t -> until:N.t -> F.t list -> E.Check_result.t
let require condition message = Diagnostic.require condition "verification_exploration" message
let check_raw budget result =
  B.charge budget (E.Check_result.canonical_size result);
  E.Check_result.to_json result
let check_size budget result = X.Codec.measure ~limits:(B.report_codec budget) (check_raw budget result)
let evaluate_one budget ?stable ~evaluate ~until history =
  let parent = B.evaluation budget in
  let result = evaluate ~parent ~until history in
  W.charge parent (E.Check_result.canonical_size result);
  let limits = B.evaluation_codec budget parent in
  X.validate_result ~limits ?stable result history until;
  result,parent,limits
let explore_in ~budget config ~evaluate =
  let limits = B.report_codec budget in
  let count = Z.to_int (Z.min (X.Bounds.possible_histories config) (Z.of_int (X.Bounds.max_histories config))) in
  let stable = ref None and results = ref [] in
  for index = 0 to count-1 do
    B.charge budget 1;
    let history = X.Bounds.history_at ~limits config (Z.of_int index) in
    let result,parent,_ = evaluate_one budget ?stable:!stable ~evaluate ~until:(X.Bounds.until config) history in
    W.charge parent (E.Check_result.canonical_size result);
    stable := Some (X.stable_dependencies result);
    let raw = check_raw budget result in
    B.reserve_report_fragment budget raw;
    let size = X.Codec.measure ~limits raw in
    B.retain budget (size.nodes+1);
    results := result :: !results
  done;
  B.charge budget count;
  let report = X.Report.make ~limits ~kind:(X.Bounds.kind config) ~config ~results:(List.rev !results) () in
  B.publish budget (X.Report.to_json report);
  report
let explore_with_usage ?limits ?parent config ~evaluate =
  let budget = B.create ?limits ?parent () in
  B.reserve_request budget (X.Bounds.to_json config);
  let result = explore_in ~budget config ~evaluate in result,B.usage budget
let explore ?limits ?parent config ~evaluate = fst (explore_with_usage ?limits ?parent config ~evaluate)
let reduce_in ~budget ~history ~until ~signature ~max_evaluations ~evaluate =
  let limits = B.report_codec budget in
  X.validate_history ~limits history until;
  require (max_evaluations>=1 && max_evaluations<=100_000) "Invalid reduction evaluation budget.";
  let initial,parent,initial_limits = evaluate_one budget ~evaluate ~until history in
  require (X.Failure_signature.matches ~limits:initial_limits signature initial)
    "Initial history does not exhibit the selected FAIL signature.";
  W.charge parent (E.Check_result.canonical_size initial);
  let stable = X.stable_dependencies initial in
  let initial_size = check_size budget initial in
  B.retain budget initial_size.nodes;
  let current = ref history and result = ref initial and result_nodes = ref 0 and evaluations = ref 1 in
  let finished = ref false and one_minimal = ref false in
  while not !finished do
    let remaining = ref (match !current with [] -> [] | _::tail -> tail) in
    let prefix = ref (match !current with [] -> [] | first::_ -> [first]) in
    let removed = ref false in
    while not !finished && not !removed && !remaining<>[] do
      if !evaluations>=max_evaluations then finished:=true
      else match !remaining with
      | [] -> ()
      | item::tail ->
          let prefix_count = List.length !prefix in
          B.retain budget prefix_count;
          let trial = List.rev_append !prefix tail in
          let checked,parent,trial_limits = evaluate_one budget ~stable ~evaluate ~until trial in
          incr evaluations;
          W.charge parent (E.Check_result.canonical_size initial + E.Check_result.canonical_size checked);
          require (E.Check_result.checked_requirement_ids checked = E.Check_result.checked_requirement_ids initial)
            "Reducer evaluator changed checked requirements.";
          if X.Failure_signature.matches ~limits:trial_limits signature checked then begin
            let size = check_size budget checked in
            B.retain budget size.nodes;
            B.release budget !result_nodes;
            result_nodes:=size.nodes;
            current:=trial; result:=checked; removed:=true
          end else begin
            B.charge budget 1;
            prefix:=item::!prefix; remaining:=tail
          end;
          B.release budget prefix_count
    done;
    if not !finished && not !removed then (one_minimal:=true;finished:=true)
  done;
  let report = X.Reduction.make ~limits ~original_history:history ~history:!current ~until ~signature
      ~original_result:initial ~result:!result ~evaluations:!evaluations ~one_minimal:!one_minimal () in
  B.publish budget (X.Reduction.to_json report);
  report
let reduce_with_usage ?limits ?parent ~history ~until ~signature ?(max_evaluations=1000) ~evaluate () =
  let budget = B.create ?limits ?parent () in
  let codec = B.input_codec budget in
  X.validate_history ~limits:codec history until;
  B.reserve_request budget (Json.Object ["history",X.history_json history;"until",N.to_json until;
    "signature",X.Failure_signature.to_json signature;"max_evaluations",Json.int max_evaluations]);
  let result = reduce_in ~budget ~history ~until ~signature ~max_evaluations ~evaluate in result,B.usage budget
let reduce ?limits ?parent ~history ~until ~signature ?max_evaluations ~evaluate () =
  fst (reduce_with_usage ?limits ?parent ~history ~until ~signature ?max_evaluations ~evaluate ())
let generate_adversarial_histories_in ~budget config =
  let limits = B.report_codec budget in
  let bounds = X.Adversarial_config.bounds config in
  let times = X.Bounds.variable_times bounds in
  let all_active = Z.pred (X.Bounds.state_count bounds) in
  let radix = Z.succ (Z.shift_left Z.one (List.length (X.Bounds.observations bounds))) in
  let _,all_inactive = List.fold_left (fun (power,total) _ ->
    B.charge budget (1+Z.numbits power+Z.numbits total); Z.mul power radix,Z.add total power)
    (Z.one,Z.zero) (X.Bounds.contact_ids bounds) in
  let cases = ref [] in
  let add label kind code =
    let prefix = List.mapi (fun index time ->
      B.charge budget 1; X.Bounds.snapshot ~limits bounds ~time ~code:(code index)) times in
    B.charge budget (List.length prefix);
    let history = prefix @ X.Bounds.fixed_suffix bounds in
    let item = X.History_case.make ~limits ~id:label ~kind ~history ~until:(X.Bounds.until bounds)
      ~config_fingerprint:(X.Adversarial_config.fingerprint config) () in
    let raw = X.History_case.to_json item in
    B.reserve_report_fragment budget raw;
    let size = X.Codec.measure ~limits raw in B.retain budget (size.nodes+1);
    cases:=item::!cases
  in
  add "startup_active" "startup_active" (fun _ -> all_active);
  add "rapid_oscillation" "rapid_oscillation" (fun index -> if index mod 2=0 then all_active else all_inactive);
  add "dropout_reappearance" "dropout_reappearance" (fun index -> if index=1 then Z.zero else all_active);
  add "absent_contacts" "absent_contacts" (fun _ -> Z.zero);
  B.charge budget (Z.numbits (X.Adversarial_config.seed config)+1);
  let seed = Z.to_string (X.Adversarial_config.seed config) in
  for index=0 to X.Adversarial_config.random_cases config-1 do
    add (Printf.sprintf "seeded_%04d" index) "seeded" (fun step ->
      B.charge budget (String.length seed+String.length X.exploration_version+512);
      let text = X.exploration_version ^ ":" ^ seed ^ ":" ^ string_of_int index ^ ":" ^ string_of_int step in
      Z.erem (Z.of_string ("0x" ^ Canonical.sha256 text)) (X.Bounds.state_count bounds))
  done;
  let first = X.Bounds.snapshot ~limits bounds ~time:N.zero ~code:all_active in
  let contact = List.hd (X.Bounds.contact_ids bounds) in
  let observation = List.hd (X.Bounds.observations bounds) in
  let signal = X.Observation.signal_id observation and field = X.Observation.field observation in
  let first_raw = F.to_json first in
  let size = X.Codec.measure ~limits first_raw in B.charge budget size.bytes;
  let replace name update raw = Json.Object (List.map (fun (key,value) -> key,(if key=name then update value else value)) (Json.object_fields raw)) in
  let first_raw = replace "contacts" (replace contact (replace signal (replace field (fun _ -> Json.Null)))) first_raw in
  let first = F.of_json first_raw in
  B.charge budget (List.length !cases);
  let ordered = List.rev !cases in
  let startup = List.hd ordered in
  let history = first :: List.tl (X.History_case.history startup) in
  let incomplete = X.History_case.make ~limits ~id:"incomplete_observation" ~kind:"diagnostic" ~history
    ~until:(X.Bounds.until bounds) ~config_fingerprint:(X.Adversarial_config.fingerprint config)
    ~intentionally_incomplete:true () in
  let raw = X.History_case.to_json incomplete in
  B.reserve_report_fragment budget raw;
  let size = X.Codec.measure ~limits raw in B.retain budget (size.nodes+1);
  B.charge budget (List.length ordered);
  let result = ordered @ [incomplete] in
  B.publish budget (Json.Array (List.map X.History_case.to_json result)); result
let generate_adversarial_histories_with_usage ?limits ?parent config =
  let budget = B.create ?limits ?parent () in
  B.reserve_request budget (X.Adversarial_config.to_json config);
  let result = generate_adversarial_histories_in ~budget config in result,B.usage budget
let generate_adversarial_histories ?limits ?parent config =
  fst (generate_adversarial_histories_with_usage ?limits ?parent config)
