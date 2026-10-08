open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Check = Bioc_realization_checker.Policy_component_context_check
module Assembly = Bioc_realization_checker.Policy_component_assembly_check
module Preserve = Bioc_realization_checker.Policy_preservation_check
module SA = Bioc_checker.Policy_admission
module RA = Bioc_checker.Policy_realization_admission
module SL = Bioc_compiler.Policy_lowering
module GL = Bioc_compiler.Policy_implementation_lowering
module CL = Bioc_compiler.Policy_component_lowering
module CP = Bioc_compiler.Construction_producer
module O = Bioc_domain.Policy_operational
module U = Bioc_domain.Policy_implementation_binding
module QP = Bioc_domain.Policy_component_assembly_proposal
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module W = Bioc_checker.Work_budget

type fixture_case = { request:R.t; assembly:Assembly.checked_assembly; behavior:O.behavior;
  graph:I.t; binding:U.t; proposal:QP.t; content:K.t; limits:Preserve.limits }
let checked_assembly request behavior graph binding proposal content limits =
  let original=R.implementation_request request in
  let result=Preserve.check ~request:original ~behavior ~implementation:graph ~proposed:binding ~limits in
  let report=Preserve.report result in
  require (get "complete" (get "coverage" report)=Json.Bool true && get "preservation" report=str "pass")
    ("Actual arranged implementation failed finite preservation: "^Canonical.encode report);
  List.iter (fun (key,value) -> require (at ["coverage";key] report=Json.int value) ("Original finite census: "^key))
    ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48];
  require (List.map (get "id") (items "requirements" report)=List.map str
    ["request_progress";"initiation_progress";"exclusive_selection"]) "Original hard requirement order changed";
  List.iter (fun row -> require (get "status" row=str "pass" && at ["histories";"pass"] row=Json.int 9)
    "Context fixture lacks complete hard requirement satisfaction") (items "requirements" report);
  let implementation=match Preserve.accepted result with Some value -> value | None -> failwith "No private preserved implementation" in
  let result=Assembly.check ~original ~components:(R.component_library request) ~rule:(R.composition_rule request)
    ~implementation ~proposed:proposal ~candidate:content () in
  require (Assembly.outcome result=E.Pass) ("Actual constructed assembly failed: "^Canonical.encode (Assembly.report result));
  require (get "artifact" (Assembly.report result)=str "withheld" && get "context" (Assembly.report result)=str "unassessed")
    "Assembly supplied its own contextual or export authority";
  match Assembly.accepted result with Some value -> value | None -> failwith "No private checked assembly"
let prepare fixture state_reading raw =
  let request=R.of_json raw in
  let original=R.implementation_request request in
  let behavior=SL.lower (SA.admit ~document:(RR.document original) ~descriptors:(RR.definitions original)) in
  let admitted=RA.admit ~request:original ~behavior in
  let library=RR.implementation_library original in
  let arranged=CL.arrange ~library ~rule:(R.composition_rule request) (GL.lower ~admitted ~library) in
  let content=CP.construct_template ~member_order:["payload"] (PM.template (A.material_authority (R.composition_rule request))) in
  let molecules=K.Inventory.molecules (Option.get (K.inventory content)) in
  require (List.map N.sequence molecules=[if state_reading then "CGCAUGGCUUAAGGAAAA" else "CCAUGGCUUAAGGAAAA"] &&
    List.map (fun molecule -> List.map N.Feature.id (N.features molecule)) molecules=[["cds";"poly_a";"utr3";"utr5"]])
    "Context fixture lost exact independently authored bases or complete four-region inventory";
  let limits=Preserve.limits_of_json (get "limits" fixture) in
  let assembly=checked_assembly request behavior arranged.implementation arranged.binding arranged.assembly content limits in
  {request;assembly;behavior;graph=arranged.implementation;binding=arranged.binding;proposal=arranged.assembly;content;limits}
let check case = Check.check ~request:case.request ~assembly:case.assembly ()
let checked label result =
  require (Check.outcome result=E.Pass) (label^": "^Canonical.encode (Check.report result));
  let report=Check.report result in
  List.iter (fun key -> require (get key report=str "withheld") ("Context authorized "^key)) ["artifact";"export"];
  List.iter (fun key -> require (get key report=str "unassessed") ("Context promoted "^key)) ["biological_validity";"human_use"];
  require (get "source_receipt_status" report=str "unchanged") "Context replaced source assessment";
  match Check.accepted result with Some value -> value | None -> failwith (label^": no private context")
let fail_result reason result =
  require (Check.outcome result=E.Fail && Option.is_none (Check.accepted result)) ("Context mutation accepted: "^reason);
  require (get "diagnostics" (Check.report result)=arr [str reason]) ("Wrong context boundary: "^Canonical.encode (Check.report result))
let with_raw case raw = {case with request=R.of_json raw}
let mutate_provider index transform raw = edit ["context";"providers";string_of_int index] (fun row -> transform row |> repin) raw
let mutate_layout transform raw = edit ["context"] (fun context -> edit ["record_layout"] transform context |> refresh_layout_pins) raw
let capacity id transform = edit ["body";"capacities"] (fun rows -> arr (List.map (fun row -> if get "id" row=str id then transform row else row) (Json.array rows)))
let expected_quantities=[1;3;1;1;1;1;1;2;8;2;8;1;1;34]
let expected_demands = List.map2 (fun (owner,unit,scope,_) quantity ->
  obj ["owner",owner;"unit",str unit;"scope",str scope;"quantity",Json.int quantity]) resource_specs expected_quantities
let expected_minimum case = at ["context";"record_layout"] (R.to_json case.request)
  |> replace "identifier_bytes" (Json.int 384)
let expected_discharges = ["chassis_capability_and_delivery_suitability";
  "semantic_definition:exclusion.chassis";"semantic_definition:exclusion.delivery";
  "semantic_definition:exclusion.environment";"semantic_definition:exclusion.interface"]
let positive case =
  let result=check case in
  let accepted=checked "fresh complete component context" result and report=Check.report result in
  require (Json.equal (R.to_json (Check.request accepted)) (R.to_json case.request) &&
    Json.equal (X.to_json (Check.context accepted)) (X.to_json (R.context case.request)) &&
    Json.equal (Assembly.evidence (Check.assembly accepted)) (Assembly.evidence case.assembly))
    "Private context changed complete original request, context or assembly";
  require (Json.equal (Check.evidence accepted) report) "Private contextual evidence differs from complete report";
  require (Json.equal (get "minimum_record_layout" report) (expected_minimum case))
    "Derived complete records differ from literal slots2/generations2/attempts2/horizon6/tick8/reasons1/causes238/identifier384";
  (* Per slot:3 retained observation rows,1 timer,2 edge histories,2 truth cells.
     Attempt capacity8 and retained history2 are different obligations.
     The queue is2*(2+1+2+2+5)+4*2+2=34; seven ticks require238 cause slots. *)
  require (Json.equal (get "derived_demands" report) (arr expected_demands)) "Complete fourteen demand quantities/owners/scopes changed";
  let provider=at ["context";"providers";"0";"body";"definition"] (R.to_json case.request) in
  let expected_allocations=List.map2 (fun demand (_,_,_,id) -> obj ["demand",demand;"provider",provider;
    "capacity",str id;"pool",str ("executor.pool."^id);"reserved",get "quantity" demand]) expected_demands resource_specs in
  require (Json.equal (get "resource_allocations" report) (arr expected_allocations)) "Exact shared-pool reservation inventory changed";
  require (List.map (fun (row:Check.discharge) -> row.obligation) (Check.discharges accepted)=expected_discharges)
    "Context discharged a source obligation outside the five original provider premises";
  let rows=items "source_obligations" report in
  require (List.length rows=23 && List.map (fun row -> Json.string (get "id" row)) rows=case.behavior.unresolved_obligations)
    "Complete original source obligation ledger was lost";
  List.iter (fun row -> require (get "context_status" row=str
    (if List.mem (Json.string (get "id" row)) expected_discharges then "discharged" else "outside_stage"))
    "Context silently discharged an unrelated original obligation") rows;
  let providers=at ["context";"providers"] (R.to_json case.request) |> Json.array |> List.map (get "identity") |> arr in
  List.iter (fun (row:Check.discharge) -> require (Json.equal row.evidence providers) "Discharge lost complete supplied provider pins") (Check.discharges accepted);
  List.iter (fun (key,value) -> require (get key report=str value) ("Complete contextual receipt pin: "^key))
    ["request_fingerprint",R.fingerprint case.request;"context_fingerprint",X.fingerprint (R.context case.request);
     "assembly_fingerprint",Canonical.fingerprint (Assembly.evidence case.assembly)];
  require (Json.equal report (Check.report (Check.replay ~request:case.request ~assembly:case.assembly report)))
    "Fresh context replay changed complete report";
  report
let layout_controls case report =
  let raw=R.to_json case.request in
  let larger=mutate_layout (fun layout -> List.fold_left (fun layout (key,value) -> replace key (Json.int value) layout) layout
    ["generations",3;"attempts",3;"maximum_tick",9;"ordered_reason_slots",2;"ordered_cause_slots",239;"identifier_bytes",513]) raw in
  let result=check (with_raw case larger) in
  ignore (checked "explicit larger complete record declarations" result);
  require (Json.equal (get "minimum_record_layout" (Check.report result)) (expected_minimum case) &&
    Json.equal (get "derived_demands" (Check.report result)) (arr expected_demands)) "Larger records changed the original finite domain or demand";
  List.iter (fun (key,value) -> let changed=mutate_layout (put [key] (Json.int value)) raw in
    fail_result ("finite_record_bound:"^key) (check (with_raw case changed)))
    ["generations",1;"attempts",1;"maximum_tick",7;"ordered_cause_slots",237;"identifier_bytes",383];
  rejected ~message:"Composition layout count exceeds its finite bound." "policy_component_context"
    "zero reason slots fail at the declared shape boundary" (fun () -> R.of_json (mutate_layout (put ["ordered_reason_slots"] (Json.int 0)) raw));
  fail_result "complete_finite_record_identity" (check (with_raw case (mutate_layout (put ["horizon_ticks"] (Json.int 5)) raw)));
  rejected "policy_component_context_assessment_mismatch" "old receipt cannot transfer to larger original records" (fun () ->
    Check.replay ~request:(R.of_json larger) ~assembly:case.assembly report)
let capacity_controls case =
  let raw=R.to_json case.request in
  List.iter (fun (id,quantity) -> let changed=mutate_provider 0 (capacity id (replace "quantity" (Json.int quantity))) raw in
    fail_result "shared_capacity_sum_exceeded" (check (with_raw case changed)))
    ["shared.truth",1;"local.evidence.evidence_records.per_encounter_slot",2;
     "feedback.input_rows_per_tick.per_executor",1;"local.attempt.active_attempt_records.per_encounter_slot",7;
     "local.attempt.retained_correlation_records.per_executor",1;"local.attempt.timer_cells.per_encounter_slot",7;
     "layout.control_event_records.per_executor",33];
  fail_result "capacity_slot_inventory" (check (with_raw case (mutate_provider 0
    (capacity "shared.truth" (replace "slots" (arr [str "e1"]))) raw)));
  let extra=at ["context";"providers";"0";"body";"capacities";"0"] raw
    |> replace "id" (str "unused.truth") |> replace "pool_id" (str "unused.pool") in
  fail_result "unused_original_capacity" (check (with_raw case (mutate_provider 0
    (edit ["body";"capacities"] (fun rows -> arr (Json.array rows@[extra]))) raw)))
let contextual_controls case =
  let raw=R.to_json case.request in
  let bad reason transform=fail_result reason (check (with_raw case (transform raw))) in
  bad "executor_recipient_binding" (put ["context";"recipient";"identity"] (str "another.cell"));
  bad "placement_identity_or_compartment" (put ["context";"placement";"compartment"] (str "nucleus"));
  bad "same_concrete_executor_delivery" (put ["context";"delivery_group";"same_recipient"] (Json.Bool false));
  bad "provider_executor_or_compartment" (mutate_provider 0 (put ["body";"recipient";"identity"] (str "another.cell")));
  List.iter (fun field -> bad "complete_input_source_binding"
    (mutate_provider 2 (put ["body";"channels";"0";field] (str "another.identity")))) ["observer";"subject"];
  bad "original_exact_clock_relation" (put ["context";"clock";"period_seconds"] (str "0.5"));
  bad "original_exact_clock_relation" (put ["context";"clock";"original_clock";"id"] (str "another.clock"));
  bad "guaranteed_inclusive_availability:exclusion.chassis"
    (mutate_provider 0 (put ["body";"availability";"duration_min"] (str "5")));
  bad "guaranteed_inclusive_availability:shared.truth"
    (mutate_provider 0 (capacity "shared.truth" (put ["availability";"duration_min"] (str "5"))));
  bad "guaranteed_inclusive_availability:condition"
    (mutate_provider 2 (put ["body";"channels";"0";"availability";"duration_min"] (str "5")));
  bad "causal_arrival_expression_activation"
    (mutate_provider 3 (put ["body";"arrival";"latest"] (str "1")));
  bad "complete_original_chassis_body" (mutate_provider 0 (put ["body";"chassis";"subtype"] (str "another.supplied.subtype")));
  bad "complete_original_environment_grammar" (mutate_provider 1
    (put ["body";"grammar";"feedback_factors";"0";"outcomes"] (arr [str "completed"])));
  let extra=at ["context";"providers";"2";"body";"channels";"0"] raw |> replace "id" (str "unused.input") in
  bad "unused_original_input_channel" (mutate_provider 2 (edit ["body";"channels"] (fun rows -> arr (Json.array rows@[extra]))));
  bad "unchanged_original_realization_request" (put ["implementation_request";"document";"program";"id"] (str "different.original.policy"));
  bad "unchanged_original_realization_request" (put ["implementation_request";"budgets";"max_work"] (Json.int 99999999));
  bad "unchanged_original_component_library" (edit ["component_library";"components"] (fun rows -> arr (List.rev (Json.array rows))))
let replay_and_budget_controls case report =
  List.iter (fun forged -> rejected "policy_component_context_assessment_mismatch" "serialized contextual claims are not authority"
    (fun () -> Check.replay ~request:case.request ~assembly:case.assembly forged))
    [replace "artifact" (str "accepted") report;replace "source_obligations" (arr []) report;
     put ["resource_allocations";"0";"reserved"] (Json.int 0) report];
  List.iter (fun maximum -> rejected "policy_component_context_resource_limit" "closed context work allowance"
    (fun () -> Check.check ~maximum ~request:case.request ~assembly:case.assembly ())) [0;100000001];
  let parent=W.create ~profile:"literal.component.parent" ~error_code:"literal_parent_limit" ~maximum:1 () in
  rejected "literal_parent_limit" "aggregate parent can deny fresh request redecoding" (fun () ->
    Check.check ~parent ~request:case.request ~assembly:case.assembly ());
  require (W.exhausted parent) "Parent resource exhaustion was not sticky"
let larger_local_minimum fixture case =
  let raw=R.to_json case.request in
  let driver=at ["component_library";"components";"1"] raw |> edit ["body";"provider_requirements"] (fun rows ->
    arr (List.map (fun row -> if get "kind" row=str "capacity" && get "unit" row=str "active_attempt_records" then
      replace "minimum" (Json.int 9) row else row) (Json.array rows))) |> repin in
  let rule=at ["composition_rule"] raw |> put ["body";"components";"1";"component"] (get "identity" driver) |> repin in
  let raw=raw |> put ["component_library";"components";"1"] driver |> replace "composition_rule" rule
    |> put ["catalog_binding";"components";"1";"component"] (get "identity" driver)
    |> put ["catalog_binding";"rule"] (get "identity" rule)
    |> mutate_layout (put ["rule"] (get "identity" rule))
    |> mutate_provider 0 (capacity "local.attempt.active_attempt_records.per_encounter_slot" (replace "quantity" (Json.int 9))) in
  (* This changes a complete original component prerequisite and its rule pin;
     all lower source/graph/material checks must freshly accept the new body. *)
  let larger=prepare fixture false raw in
  let result=check larger in
  ignore (checked "larger original local minimum is reserved" result);
  let expected=List.mapi (fun index row -> if index=8 then replace "quantity" (Json.int 9) row else row) expected_demands in
  require (Json.equal (get "derived_demands" (Check.report result)) (arr expected))
    "Domain-derived capacity8 silently discarded supplied local minimum9";
  fail_result "shared_capacity_sum_exceeded" (check (with_raw larger (mutate_provider 0
    (capacity "local.attempt.active_attempt_records.per_encounter_slot" (replace "quantity" (Json.int 8))) raw)))
let actual_identifier_width case =
  let old=(List.hd (I.nodes case.graph)).node_id and long=String.make 100 'x' in
  let rename = function Json.String value when value=old -> str long | value -> value in
  let fields keys raw=List.fold_left (fun raw key -> edit [key] rename raw) raw keys in
  let rows key transform=edit [key] (fun rows -> arr (List.map transform (Json.array rows))) in
  let endpoint=fields ["node"] in
  let raw=I.to_json case.graph |> rows "nodes" (fields ["id"])
    |> rows "wires" (fun row -> row |> edit ["producer"] endpoint |> edit ["consumer"] endpoint)
    |> rows "inputs" (edit ["consumer"] endpoint)
    |> rows "atomic_groups" (fun row -> row |> fields ["arbiter"]
      |> edit ["commits"] (fun values -> arr (List.map rename (Json.array values))))
    |> rows "semantic_exports" endpoint |> rows "occurrences" (rows "targets" endpoint) in
  let graph=I.of_json ~library:(RR.implementation_library (R.implementation_request case.request)) raw in
  let binding=U.to_json case.binding |> rows "observations" (fields ["bank"])
    |> rows "states" (fields ["register"]) |> rows "effects" (fields ["bank"])
    |> rows "rules" (fields ["gate";"arbiter";"commit"]) |> U.of_json in
  let proposal=QP.to_json case.proposal |> rows "nodes" (fields ["actual"]) |> QP.of_json in
  let assembly=checked_assembly case.request case.behavior graph binding proposal case.content case.limits in
  let renamed={case with assembly;graph;binding;proposal} in
  fail_result "finite_record_bound:identifier_bytes" (check renamed);
  let exact=with_raw renamed (mutate_layout (put ["identifier_bytes"] (Json.int 528)) (R.to_json case.request)) in
  let result=check exact in
  ignore (checked "actual long names fit complete explicit record width" result);
  require (at ["minimum_record_layout";"identifier_bytes"] (Check.report result)=Json.int 528)
    "Actual node names were omitted from complete correlation/event records";
  fail_result "finite_record_bound:identifier_bytes" (check (with_raw renamed
    (mutate_layout (put ["identifier_bytes"] (Json.int 527)) (R.to_json case.request))))
let run first second =
  let a=prepare first false (fst (request_literal first false)) and b=prepare second true (fst (request_literal second true)) in
  let report_a=positive a and report_b=positive b in
  require (get "request_fingerprint" report_a<>get "request_fingerprint" report_b) "Source families collapsed full contextual authority";
  List.iter (fun (case,report) -> layout_controls case report;capacity_controls case;contextual_controls case) [a,report_a;b,report_b];
  fail_result "delivery_sequence_length" (check (with_raw b (put ["context";"delivery_group";"max_total_bases"] (Json.int 17) (R.to_json b.request))));
  fail_result "unchanged_original_realization_request" (Check.check ~request:a.request ~assembly:b.assembly ());
  rejected "policy_component_context_assessment_mismatch" "A receipt cannot transfer to B" (fun () ->
    Check.replay ~request:b.request ~assembly:b.assembly report_a);
  replay_and_budget_controls a report_a;
  larger_local_minimum first a;actual_identifier_width a;
  Printf.printf "component context checker: %d independent checks passed\n" !checks
let () =
  Printexc.register_printer (function Diagnostic.Error value -> Some (Printf.sprintf "Diagnostic.Error(code=%s,path=%s,message=%s)"
    value.code (Option.value ~default:"<none>" value.path) value.message) | _ -> None);
  require (Array.length Sys.argv=3) "Supply independent A/B original request fixtures";
  run (read Sys.argv.(1)) (read Sys.argv.(2))
