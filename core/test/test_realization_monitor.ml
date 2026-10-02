open Bioc_wire
open Bioc_domain
module C = Bioc_realization_checker.Realization_check
module Budget = Bioc_realization_checker.Realization_budget
module W = Bioc_checker.Work_budget
module R = Realization_contract
module E = Realization_evidence
module D = Execution_data
module N = Runtime_number
module M = Measurement_contract
let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run = incr checks; match run () with
  | _ -> failwith ("Unexpected acceptance: " ^ code)
  | exception Diagnostic.Error error ->
      if error.code <> code then failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let strings values = arr (List.map str values)
let n = N.of_int
let dtype scalar = Type_spec.of_json (obj ["kind", str (if scalar then "scalar" else "condition");
  "name", str (if scalar then "Level" else "Condition"); "dimensions", obj []; "arguments", arr []])
let level = dtype true
let condition = dtype false
let duration = Type_spec.of_json (obj ["kind", str "scalar"; "name", str "Duration";
  "dimensions", obj ["time", Json.int 1]; "arguments", arr []])
let scalar dtype unit value = M.Scalar.of_json (obj ["kind", str "scalar";
  "type", Type_spec.to_json dtype; "value", N.to_json value; "unit", str unit; "canonical_value", N.to_json value])
let seconds value = scalar duration "s" value
let amount value = scalar level "1" value
let interval value =
  M.Interval.of_json (obj ["kind", str "interval";
    "type", obj ["kind", str "interval"; "name", str "Interval[Level]";
      "dimensions", obj []; "arguments", arr [Type_spec.to_json level]];
    "lower", M.Scalar.to_json (amount (n value)); "upper", M.Scalar.to_json (amount (n value))])
let behavior contact =
  let scope = if contact then "contact" else "environment" in
  let node ?(dtype = Json.Null) ?(role = str "cell") ?(bound = false) id kind inputs attributes =
    obj ["id", str id; "kind", str kind; "inputs", strings inputs; "attributes", obj attributes;
      "data_type", dtype; "role", role; "source", Json.Null; "contact_bound", Json.Bool bound;
      "requirement_ids", strings ["requirement:rule"]] in
  let nodes = [node ~role:Json.Null "cell" "role" []
      ["name", str "selected"; "cell_type", str "abstract_cell"; "engineering", str "in_vivo"];
    node ~bound:contact "scope" "scope" ["cell"] ["name", str scope; "scope", str scope];
    node ~bound:contact ~dtype:(Type_spec.to_json level) "signal" "signal" ["scope"]
      ["name", str "flag"; "scope", str scope; "observation", str "signal"];
    node ~bound:contact ~dtype:(Type_spec.to_json condition) "present" "qualitative" ["signal"] ["band", str "present"];
    node ~bound:contact "action" (if contact then "action.eliminate" else "action.rest")
      (if contact then ["cell"; "scope"] else ["cell"]) ["ongoing", Json.Bool true];
    node ~bound:contact "rule" "rule" ["cell"; "present"; "action"]
      ["trigger", str "condition"; "execution", str "concurrent"; "priority", str "none";
       "ongoing_activation", str "level"; "impulse_activation", str "onset"; "state_assignment", str "level"]] in
  let lineage = ["action"; "cell"; "present"; "rule"; "scope"; "signal"] in
  Behavior.of_json (obj ["schema_version", str "biocompiler.behavior.v0.1"; "name", str "literal_monitor";
    "nodes", arr nodes; "roots", strings ["cell"; "rule"]; "source_fingerprint", str (String.make 64 '0');
    "requirements", arr [obj ["id", str "requirement:rule"; "kind", str "rule"; "source_node_id", str "rule";
      "lineage", strings lineage; "source", Json.Null]];
    "source_links", obj ["cell", strings ["cell"]; "scope", strings ["cell"; "scope"];
      "signal", strings ["cell"; "scope"; "signal"]; "present", strings ["cell"; "present"; "scope"; "signal"];
      "action", strings (if contact then ["action"; "cell"; "scope"] else ["action"; "cell"]);
      "rule", strings lineage]; "policies", Behavior.execution_policies Behavior.V0_1; "parameter_bindings", obj []])
type fixture = { behavior : Behavior.t; contract : R.Behavior_contract.t; domain : R.Operating_domain.t;
  target : Build_request.Target.t; mechanism : Mechanism.t; observations : Observation_map.t }
let fixture ?(contact = false) ?(silent = false) ?(activation = n 1) ?(deactivation = n 1) () =
  let behavior = behavior contact and scope = if contact then R.Observable.Contact else R.Observable.Cell in
  let observable id dtype = R.Observable.make ~id ~dtype ~role:"cell" ~scope () in
  let input = observable "observed" condition and output = observable "activity" level in
  let domain = R.Operating_domain.make ~id:"domain" ~version:"1" ~role:"cell"
    ~inputs:[R.Input_domain.make ~signal_id:"signal" ~field:Observation_map.Present ~observable:input
      ~allowed:(R.Input_domain.Booleans [false; true])]
    ~minimum_horizon:(seconds (n 8)) ?max_contacts:(if contact then Some (Z.of_int 2) else None) () in
  let response = R.Response.make ~id:"response" ~rule_id:"rule" ~specification_id:"action" ~observable:output
    ~active_range:(interval 1) ~inactive_range:(interval 0)
    ~max_activation_delay:(seconds activation) ~max_deactivation_delay:(seconds deactivation) in
  let contract = R.Behavior_contract.make ~id:"contract" ~behavior_fingerprint:(Behavior.fingerprint behavior)
    ~requirements:[response] in
  let mechanism = Mechanism.make ~name:"literal_candidate" ~outputs:["output"] ~nodes:[
    Mechanism.Node.make ~id:"input" ~operation:Mechanism.Input ~output:input ();
    Mechanism.Node.make ~id:"high" ~operation:(Mechanism.Constant (Mechanism.Scalar (amount (n 1)))) ~output:(observable "high" level) ();
    Mechanism.Node.make ~id:"low" ~operation:(Mechanism.Constant (Mechanism.Scalar (amount N.zero))) ~output:(observable "low" level) ();
    Mechanism.Node.make ~id:"select" ~operation:Mechanism.Select ~output:(observable "selected" level) ~inputs:["input"; "high"; "low"] ();
    Mechanism.Node.make ~id:"output" ~operation:Mechanism.Output ~output ~inputs:[if silent then "low" else "select"] ~requirement_ids:["response"] ()] () in
  let target = Build_request.Target.of_json (obj ["schema_version", str "biocompiler.target.v0.1";
    "context_id", str "fixture"; "context_version", str "1"; "payload_format", str "RNA";
    "capabilities", arr []; "compartments", strings ["abstract"]; "resources", obj []]) in
  let observations = Observation_map.make
    ~inputs:[Observation_map.Input_binding.make ~signal_id:"signal" ~field:Observation_map.Present ~mechanism_input_id:"input"]
    ~outputs:[Observation_map.Output_binding.make ~requirement_id:"response" ~mechanism_output_id:"output"] in
  {behavior; contract; domain; target; mechanism; observations}
let frame time present = D.Input_frame.make ~time ~signals:["signal", D.Sample.make ~present ()] ()
let history values = List.map (fun (time, present) -> frame (n time) present) values
let contact_history values = List.map (fun (time, values) -> D.Input_frame.make ~time
  ~contacts:(List.map (fun (id, present) -> id, ["signal", D.Sample.make ~present ()]) values) ()) values
let run ?until ?limits ?parent fixture history = C.check ?until ?limits ?parent fixture.behavior fixture.contract fixture.domain
  fixture.target fixture.mechanism fixture.observations history
let codes result = List.map E.Check_diagnostic.code (E.Check_result.diagnostics result)
let coverage result active inactive incomplete cancelled =
  let expected = E.Requirement_coverage.make ~requirement_id:"response"
    ~activation_deadlines_checked:(Z.of_int active) ~inactive_deadlines_checked:(Z.of_int inactive)
    ~incomplete_episode_count:(Z.of_int incomplete) ~cancelled_episode_count:(Z.of_int cancelled) () in
  check (List.map E.Requirement_coverage.to_json (E.Check_result.coverage result) = [E.Requirement_coverage.to_json expected])
    "Complete independent episode coverage differs"
let pin label expected result = check (E.Check_result.fingerprint result = expected) (label ^ ": full historical report identity differs")
let timelines () =
  let basic = fixture () and snapshots = history [0, false; 2, true; 6, false; 10, false] in
  check (Behavior.fingerprint basic.behavior = "0501350664e2d7352578ddfeda6ea52b58d936aedba2abe983f93b0654155a2d") "Literal Behavior changed";
  check (Mechanism.fingerprint basic.mechanism = "bd9d619e9fa2252ae106fcdc8e58e06ccf61bd447bc5dd71e6aa40e4f7015c03") "Literal mechanism changed";
  let result = run basic snapshots in
  check (E.Check_result.passed result && codes result = []) "Timely complete response did not pass";
  coverage result 1 2 0 0;
  pin "timely" "066977e60ecfc65cc7ed7ca41dbf3837161508f4769e0f0a6a3fa5d6b36a1d73" result;
  let interrupted = run basic (history [0, false; 2, true; 3, false; 10, false]) in
  check (codes interrupted = ["unexercised_response"; "incomplete_episode"]) "Old deadline was checked before simultaneous transition";
  coverage interrupted 0 2 1 0;
  pin "interrupted" "ec7d37eb3c99b1411c83a0b2759b0a52bb464859407a8f7744e4f72de754848f" interrupted;
  let truncated = run ~until:(N.Real 2.5) basic snapshots in
  check (codes truncated = ["short_horizon"; "unexercised_response"; "incomplete_episode"]) "Truncation diagnostics lost precedence";
  coverage truncated 0 1 1 0;
  pin "truncated" "468dd232a6f66fddc7019a8629dd5582043a8a71c8ca9fbf855122a7ae6d5386" truncated;
  let zero = run (fixture ~activation:N.zero ~deactivation:N.zero ()) snapshots in
  coverage zero 1 2 0 0;
  pin "zero delays" "e9b203c005b311cfeadb82784553d740680ab0dae6b97dc7f5af4ddc66de0438" zero;
  let silent = fixture ~silent:true () in
  let snapshots = [frame N.zero false; frame (N.Real 2.) true; frame (N.Real 4.) true; frame (n 6) false; frame (n 10) false] in
  let failed = run silent snapshots in
  check (E.Check_result.outcome failed = E.Fail && codes failed = ["response_violation"])
    "Violation precedence changed";
  check (List.map (fun example -> N.to_json (E.Counterexample.time example)) (E.Check_result.counterexamples failed)
    = [Json.Float 3.; Json.Float 4.]) "Monitor lost repeated violations or original floating timestamps";
  pin "silent" "8a160ec330e7169b4fa25b7b346aae85bd6a941f04d22b95334b2d4fc15dbc08" failed;
  let horizon = run ~until:(n 4) silent snapshots in
  check (codes horizon = ["short_horizon"; "response_violation"] &&
    List.map (fun value -> N.to_json (E.Counterexample.time value)) (E.Check_result.counterexamples horizon)
      = [Json.Float 3.; Json.int 4]) "Equal horizon timestamp lost first numeric representation";
  pin "horizon representation" "96f183ace54f371ce170a507e6a7193b443f63cb5296bea3c47558e92ea3b01c" horizon;
  let contacts = run (fixture ~contact:true ()) (contact_history
    [N.zero, ["a", true]; N.Real 0.5, []; n 2, ["a", true]; n 4, ["a", false]; n 10, ["a", false]]) in
  coverage contacts 1 1 0 1;
  pin "contact cancellation and reappearance" "89f896c82a44e8bd066050edc3bfc53abbdc2313a94c1d9fb37567f3ff4fd382" contacts;
  let ordered = run (fixture ~contact:true ~silent:true ()) (contact_history
    [N.zero, ["z", true; "a", true]; n 2, ["z", false; "a", false]; n 10, ["z", false; "a", false]]) in
  coverage ordered 2 2 0 0;
  check (List.map E.Counterexample.contact_id (E.Check_result.counterexamples ordered) = [Some "a"; Some "z"])
    "Counterexamples did not preserve lexical contact order";
  pin "contact order" "9ccb4ef19e02cf1c5d2e72be91c0d2866c9a746daf8c5d3e09c013e843c9ac5f" ordered
let numeric_deadlines () =
  let result = run (fixture ~activation:(N.Real 0.25) ()) [frame N.zero false; frame (N.Real 1e16) true] in
  check (codes result = ["numeric_resolution"; "unexercised_response"; "incomplete_episode"])
    "Nonadvancing deadline was converted into success or engine failure";
  coverage result 0 1 1 0;
  pin "nonadvancing" "393dcbaca7d182b1479d52141dbf1c8d95865ae2c8e30c74f225d541bf3e70d6" result;
  let result = run ~until:(N.Real 1.5e308) (fixture ~activation:(N.Real 1e308) ~deactivation:N.zero ())
    [frame N.zero false; frame (N.Real 1e308) true] in
  pin "floating overflow" "6ec93b85d374366326e3274b324a6ce5290f4b4017afa85b563fa3a1c8d52063" result;
  let huge = N.Integer (Z.pow (Z.of_int 10) 308) in
  reject "realization_deadline_overflow" (fun () -> run ~until:(N.Integer (Z.of_float 1.5e308))
    (fixture ~activation:huge ~deactivation:N.zero ()) [frame N.zero false; frame huge true])
let budgets () =
  reject "realization_limits" (fun () -> Budget.make_limits ~max_work:50_000_001 ());
  let parent = W.create ~profile:"literal-parent" ~error_code:"literal_parent_exhausted" ~maximum:5 () in
  let budget = Budget.create ~parent () in
  Budget.charge budget 5;
  (match Budget.charge budget 1 with
   | () -> failwith "Shared parent permitted excess work"
   | exception Diagnostic.Error error ->
       check (error.code = "literal_parent_exhausted" && Budget.is_resource_error budget error) "Lost parent failure identity";
       check (not (Budget.is_resource_error budget {error with message = error.message})) "Unrelated diagnostic impersonated exhaustion");
  check (W.remaining parent = 0 && (Budget.usage budget).work_charged = 5) "Failed work charge was not atomic";
  let budget = Budget.create ~limits:(Budget.make_limits ~max_monitor_items:2 ()) () in
  Budget.retain_monitor budget 2; reject "realization_monitor_limit" (fun () -> Budget.retain_monitor budget 1);
  Budget.release_monitor budget 2; Budget.retain_monitor budget 2;
  check ((Budget.usage budget).monitor_peak = 2) "Retention release or peak accounting changed";
  let budget = Budget.create ~limits:(Budget.make_limits ~max_work:8 ()) () in
  let rec values = 1 :: values in
  reject "realization_work_limit" (fun () -> Budget.bounded_list budget values);
  let rec raw = Json.Array [raw] in
  reject "realization_input_limit" (fun () -> Budget.reserve_request (Budget.create ()) raw);
  let rec spine = Json.Null :: spine in
  reject "realization_input_limit" (fun () -> Budget.reserve_request (Budget.create ()) (arr spine));
  let budget = Budget.create ~limits:(Budget.make_limits ~max_report_bytes:15 ()) () in
  Budget.reserve_report budget (str "β");
  reject "realization_report_limit" (fun () -> Budget.reserve_report budget (str "β"));
  let budget = Budget.create () in
  Budget.reserve_report budget (str "β");
  check ((Budget.usage budget).report_bytes = 9 && (Budget.usage budget).work_charged = 9)
    "ASCII publication did not consume the shared work budget";
  let budget = Budget.create ~limits:(Budget.make_limits ~max_request_bytes:5 ()) () in
  Budget.reserve_request budget Json.Null;
  reject "realization_input_limit" (fun () -> Budget.reserve_request budget Json.Null);
  let budget = Budget.create () in Budget.burn_failure budget 7;
  check ((Budget.usage budget).work_charged = 7 && (Budget.usage budget).reserved_failure_work = 7)
    "Failed execution reservation was falsely reported as exact engine work";
  let fixture = fixture () and frames = history [0, false; 2, true; 6, false; 10, false] in
  reject "realization_work_limit" (fun () -> run ~limits:(C.make_limits ~max_work:1 ()) fixture frames);
  reject "realization_monitor_limit" (fun () -> run ~limits:(C.make_limits ~max_monitor_items:1 ()) fixture frames);
  reject "realization_report_limit" (fun () -> run ~limits:(C.make_limits ~max_report_bytes:1024 ()) fixture frames)
let () =
  timelines (); numeric_deadlines (); budgets ();
  Printf.printf "realization monitor: %d public-entrypoint literal, full-report identity, numeric and cumulative resource checks passed\n" !checks
