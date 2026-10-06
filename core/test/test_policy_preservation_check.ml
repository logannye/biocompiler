open Bioc_wire
let () = Printexc.register_printer (function
  | Diagnostic.Error diagnostic -> Some (Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      diagnostic.code (Option.value ~default:"<none>" diagnostic.path) diagnostic.message)
  | _ -> None)
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module R = Bioc_domain.Policy_realization_request
module U = Bioc_domain.Policy_implementation_binding
module B = Bioc_checker.Policy_implementation_binding_check
module L = Bioc_compiler.Policy_lowering
module C = Bioc_realization_checker.Policy_preservation_check
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let str value=Json.String value
let arr values=Json.Array values
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let integer name value=Z.to_int(Json.integer(get name value))
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000(really_input_string channel(in_channel_length channel)))
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Absent mutation field "^key);
      obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |index::rest,Json.Array values->arr(List.mapi(fun i value->if i=int_of_string index then set rest replacement value else value)values)
  |_->failwith "Mutation escaped independently authored fixture"
let declarations case=items "declarations"(get "program"(get "document"(get "request" case)))
let declaration case id=List.find(fun row->text "id" row=id)(declarations case)
let behavior request=L.lower(Bioc_checker.Policy_admission.admit
    ~document:(R.document request) ~descriptors:(R.definitions request))
let repin case=
  (* Only external authority and source obligation metadata are refreshed. No
     producer, binder or runtime supplies the expected graph or census. *)
  let rec expressions path value=match value with
    |Json.Object fields->(if List.assoc_opt "$type" fields=Some(str "Expr")then[path]else[])@
        List.concat_map(fun(key,value)->expressions(path^"/"^key)value)fields
    |Json.Array values->List.concat(List.mapi(fun index value->expressions(path^"/"^string_of_int index)value)values)
    |_->[]in
  let paths=List.concat(List.mapi(fun index row->if text "$type" row="Requirement"then
    let path="/document/program/declarations/"^string_of_int index in path::expressions path row else [])(declarations case))in
  let retained=List.filter(fun row->text "role" row<>"requirement")(items "occurrences"(get "implementation" case))in
  let obligations=List.map(fun path->obj["source_path",str path;"role",str "requirement";
    "disposition",str "obligation";"targets",arr[]])paths in
  let case=set["implementation";"occurrences"](arr(List.sort(fun a b->String.compare(text "source_path" a)(text "source_path" b))(retained@obligations)))case in
  let request=R.of_json(get "request" case)in
  set["implementation";"authority"](obj[
    "source_artifact_digest",str(D.artifact_digest(R.document request));
    "descriptors_digest",str(O.descriptors_digest(R.definitions request));
    "domain_digest",str(F.digest(R.operating_domain request));
    "implementation_catalog_digest",str(Canonical.fingerprint(get "implementations"(D.to_json(R.document request))));
    "library_digest",str(I.library_digest(R.implementation_library request))])case
let edit case id path replacement=
  repin(set["request";"document";"program";"declarations"]
    (arr(List.map(fun row->if text "id" row=id then set path replacement row else row)(declarations case)))case)
let limits_json=obj[
  "profile",str "biocompiler.policy_preservation_resources.v0.1";
  "source",obj["max_ticks",Json.int 16;"max_inputs",Json.int 256;"max_encounters",Json.int 4;
    "max_attempts",Json.int 32;"max_work",Json.int 100000;"max_trace_items",Json.int 2000;"max_microsteps",Json.int 32];
  "candidate",obj["max_work",Json.int 1000000;"max_events",Json.int 100000;
    "max_attempts",Json.int 32;"max_microsteps",Json.int 32];
  "monitor",obj["max_work",Json.int 1000000;"max_obligations",Json.int 1000;"max_samples",Json.int 100000];
  "max_step_work",Json.int 1000000;"max_step_retained",Json.int 100000;
  "max_report_bytes",Json.int(8*1024*1024);"max_report_nodes",Json.int 1000000]
let limits=C.limits_of_json limits_json
let generous case=set["request";"budgets"](obj["max_prefixes",Json.int 100000;
  "max_transitions",Json.int 100000;"max_work",Json.int 100000000;"max_trace_items",Json.int 1000000])case
let observation tick slot status value=obj["slot",str slot;"observation",str "condition";
  "available_tick",Json.int tick;"observed_tick",Json.int tick;"status",str status;"value",value]
let observations tick status value=List.map(fun slot->observation tick slot status value)["e1";"e2"]
let fixed_domain case fixed feedback=
  let domain=get "operating_domain"(get "request" case)in
  let domain=set["fixed_observations"](arr fixed)(set["feedback_factors"](arr feedback)
    (set["observation_factors"](arr[])(set["lifecycle_factors"](arr[])domain)))in
  repin(generous(set["request";"operating_domain"]domain case))
let run ?(limits=limits) case=
  let request=R.of_json(get "request" case)in
  C.check ~request ~behavior:(behavior request)
    ~implementation:(I.of_json ~library:(R.implementation_library request)(get "implementation" case))
    ~proposed:(U.of_json(get "proposed" case)) ~limits
let row id result=List.find(fun row->text "id" row=id)(items "requirements"(C.report result))
let equal_int expected name value=require(integer name value=expected)
  ("Independent census mismatch at "^name^": expected "^string_of_int expected^", got "^string_of_int(integer name value))
let scope result=
  let report=C.report result in
  List.iter(fun key->require(text key report="unassessed")("Preservation promoted "^key))["target_status";"material"];
  List.iter(fun key->require(text key report="withheld")("Preservation authorized "^key))["artifact";"export"]
let complete result histories transitions prefixes=
  scope result;let report=C.report result in let coverage=get "coverage" report in
  require(get "complete" coverage=Json.Bool true)("Coverage incomplete: "^Canonical.encode(get "stopped" report));
  require(text "preservation" report="pass")"Complete independent traces did not preserve behavior";
  equal_int histories "histories" coverage;equal_int transitions "transitions" coverage;
  equal_int prefixes "prefixes_started" coverage;equal_int prefixes "matched_prefixes" coverage;
  require(get "stopped" report=Json.Null)"Completed traversal retained a stop";
  require(text "traversal" coverage="exhaustive_depth_first_no_merging")"Traversal silently changed its census meaning"
let withheld result=
  scope result;require(Option.is_none(C.accepted result))"An incomplete or unsatisfied case acquired private accepted authority";
  require(text "assurance"(C.report result)="not_established")"A hard requirement or coverage gap was promoted"
let verdict result id expected=require(text "status"(row id result)=expected)("Wrong whole-domain verdict for "^id)
let controls=ref 0
let rejects label codes action=incr controls;match action()with
  |_->failwith("Negative control returned authority: "^label)
  |exception Diagnostic.Error diagnostic->require(List.mem diagnostic.code codes)(label^": unexpected diagnostic "^diagnostic.code)
let stopped label category diagnostic result=
  incr controls;withheld result;let report=C.report result in
  require(get "complete"(get "coverage" report)=Json.Bool false)(label^": stopped tree claimed completeness");
  let stop=get "stopped" report in
  require(text "category" stop=category)(label^": wrong stop category "^text "category" stop);
  require(text "code"(get "diagnostic" stop)=diagnostic)(label^": wrong stop diagnostic "^text "code"(get "diagnostic" stop));
  require(text "preservation" report="unassessed")(label^": resource/domain stop claimed a behavioral verdict")
let resource_limits positive=
  (* This former fixture allowance cannot even pin the complete independently
     checked binding. Keep its hosted failure as an explicit incomplete case. *)
  stopped "complete binding exceeds former monitor allowance" "incomplete"
    "policy_requirement_monitor_work_limit"
    (run ~limits:(C.limits_of_json(set ["monitor";"max_work"](Json.int 100000)limits_json))positive);
  List.iter(fun(label,path,code)->
    let altered=C.limits_of_json(set path(Json.int 1)limits_json)in
    stopped label "incomplete" code(run ~limits:altered positive))[
    "source evaluator work",["source";"max_work"],"policy_execution_work_limit";
    "source evaluator trace",["source";"max_trace_items"],"policy_execution_trace_limit";
    "candidate total work",["candidate";"max_work"],"policy_primitives_work_limit";
    "candidate retained events",["candidate";"max_events"],"policy_primitives_trace_limit";
    "candidate per-call work",["max_step_work"],"policy_primitives_work_limit";
    "candidate per-call retained",["max_step_retained"],"policy_primitives_trace_limit";
    "monitor initialization work",["monitor";"max_work"],"policy_requirement_monitor_work_limit";
    "monitor obligations",["monitor";"max_obligations"],"policy_requirement_monitor_obligation_limit";
    "monitor samples",["monitor";"max_samples"],"policy_requirement_monitor_sample_limit"];
  List.iter(fun(field,code)->
    let changed=repin(set["request";"budgets";field](Json.int 1)positive)in
    stopped field "incomplete" code(run changed))[
      "max_prefixes","policy_preservation_prefix_limit";
      "max_transitions","policy_preservation_prefix_limit";
      "max_trace_items","policy_preservation_trace_limit"];
  (* A cap too small to publish even its failure receipt must throw explicitly;
     the caller must not receive either a success report or private authority. *)
  rejects "global work cannot fund publication" ["policy_preservation_publication_work_limit"]
    (fun()->run(set["request";"budgets";"max_work"](Json.int 1)positive));
  rejects "bounded report bytes" ["response_too_large";"policy_preservation_report_limit"]
    (fun()->run ~limits:(C.limits_of_json(set["max_report_bytes"](Json.int 1)limits_json))positive);
  rejects "bounded report nodes" ["policy_preservation_report_limit"]
    (fun()->run ~limits:(C.limits_of_json(set["max_report_nodes"](Json.int 1)limits_json))positive);
  rejects "monitor decoder and runtime ceilings agree" ["policy_preservation_limits"]
    (fun()->C.limits_of_json(set["monitor";"max_obligations"](Json.int 10001)limits_json))
let no_effect_source first=
  (* This is a distinct negative-control request, not a weaker reinterpretation
     of the original scoped-memory property. All runtime declarations remain. *)
  let old=declaration first "request_progress"in
  let observed=get "when"(declaration first "respond")in
  let updated=set["op"](str "updated")(set["value_type";"kind"](str "event")observed)in
  let requirement=set["description"](str "A known update is observed, without requiring an effect.")
    (set["trigger"]updated(set["response"]observed old))in
  let rows=List.filter(fun row->text "$type" row<>"Requirement")(declarations first)@[requirement]in
  let case=set["request";"document";"program";"declarations"](arr rows)first in
  let program=get "program"(get "document"(get "request" case))in
  let identities=List.map(fun row->text "id" row)rows in
  let case=set["request";"document";"program";"source_map"]
    (arr(List.filter(fun row->List.mem(text "declaration_id" row)identities)(items "source_map" program)))case in
  let case=set["request";"document";"assurance";"requirements"](arr[str "request_progress"])case in
  fixed_domain case(observations 0 "valid"(Json.Bool true))[]
let ()=
  require(Array.length Sys.argv=2)"Supply independently authored policy source/graph fixture";
  let cases=items "cases"(read Sys.argv.(1))in
  let first=List.find(fun row->text "name" row="original_unknown_safety")cases
  and second=List.find(fun row->text "name" row="exclusion_sibling_resolved_chassis")cases in
  let fixed=observations 0 "valid"(Json.Bool false)@observations 1 "valid"(Json.Bool true)@
    observations 2 "valid"(Json.Bool false)in
  let feedback=obj["effect",str "response";"ticks",arr[Json.int 2];
    "attempt_selector",str "all_previously_created";"outcomes",arr[str "completed";str "failed"];
    "routes",arr[str "correlated"];"max_rows_per_attempt_tick",Json.int 1]in
  let positive=fixed_domain second fixed[feedback]in
  require(Json.equal(get "document"(get "request" positive))(get "document"(get "request" second)))
    "Positive domain changed original source, deployment, catalog or hard assurance";
  let result=run positive in
  (* Two earlier requests each independently receive none/completed/failed at
     tick2, alongside known-false evidence exercising the exclusion branch.
     Hence9 leaves; transitions=1+1+5*9=47, plus the root=48 prefixes.
     No expectation is obtained from the domain enumerator or either runtime. *)
  complete result 9 47 48;
  require(text "status"(C.report result)="checked_implementation")"Complete passing domain lacks accepted status";
  let accepted=match C.accepted result with Some value->value|None->failwith "Complete nonvacuous hard requirements withheld accepted value"in
  require(Json.equal(C.evidence accepted)(C.report result))"Private accepted value detached from exact fresh evidence";
  require(Json.equal(B.report(C.binding accepted))(get "binding"(C.report result)))"Accepted graph binding differs from checked report";
  let required=["request_progress";"initiation_progress";"exclusive_selection"]in
  require(List.map(fun row->text "id" row)(items "requirements"(C.report result))=required)"Whole-domain report dropped or reordered a hard requirement";
  List.iter(fun id->verdict result id "pass";
    require(Json.equal(get "source"(row id result))(declaration positive id))"Requirement changed original meaning";
    equal_int 9 "pass"(get "histories"(row id result));
    List.iter(fun status->equal_int 0 status(get "histories"(row id result)))["fail";"unknown";"unsupported";"not_exercised"];
    require(get "nonvacuous"(row id result)=Json.Bool true)"Requirement lacks independent exercise coverage")required;
  let activity=get "program_coverage"(C.report result)in
  equal_int 2 "created_attempts" activity;equal_int 6 "active_prefixes" activity;equal_int 41 "inactive_prefixes" activity;
  require(get "nonvacuous" activity=Json.Bool true)"Both encounters did not exercise effects and inactivity";
  let safety=get "coverage"(row "exclusive_selection" result)in
  equal_int 126 "samples" safety;equal_int 24 "active" safety;equal_int 102 "inactive" safety;
  List.iter(fun id->equal_int 18 "enabled_triggers"(get "coverage"(row id result)))["request_progress";"initiation_progress"];
  let usage=get "usage"(C.report result)in
  require(integer "work" usage<=100000000 && integer "peak_retained_trace_items" usage<=1000000)"Receipt exceeds original budget";
  require(integer "work" usage>integer "source_work" usage+integer "candidate_work" usage+integer "monitor_work" usage)
    "Projection, publication and traversal work escaped accounting";
  let unknown=fixed_domain first(observations 0 "invalid" Json.Null@
    observations 1 "valid"(Json.Bool false)@observations 2 "valid"(Json.Bool true))[]in
  require(Json.equal(get "document"(get "request" unknown))(get "document"(get "request" first)))
    "Unknown control weakened original safety or assurance";
  let uncertain=run unknown in complete uncertain 1 5 6;withheld uncertain;
  verdict uncertain "scoped_memory" "unknown";equal_int 1 "unknown"(get "histories"(row "scoped_memory" uncertain));
  List.iter(fun id->verdict uncertain id "pass")["request_progress";"initiation_progress";"request_authorization"];
  let unsupported=edit positive "initiation_progress"["response";"value"](str "ceased")in
  let unresolved=run unsupported in complete unresolved 9 47 48;withheld unresolved;
  verdict unresolved "initiation_progress" "unsupported";
  equal_int 9 "unsupported"(get "histories"(row "initiation_progress" unresolved));
  let completion=edit(edit positive "initiation_progress"["response";"value"](str "completed"))
    "initiation_progress"["deadline";"amount"](str "2")in
  let failed=run completion in complete failed 9 47 48;withheld failed;
  verdict failed "initiation_progress" "fail";equal_int 1 "pass"(get "histories"(row "initiation_progress" failed));
  equal_int 8 "fail"(get "histories"(row "initiation_progress" failed));
  let idle=run(no_effect_source first)in complete idle 1 5 6;withheld idle;
  verdict idle "request_progress" "pass";equal_int 2 "enabled_triggers"(get "coverage"(row "request_progress" idle));
  let idle_coverage=get "program_coverage"(C.report idle)in
  equal_int 0 "created_attempts" idle_coverage;equal_int 0 "active_prefixes" idle_coverage;equal_int 5 "inactive_prefixes" idle_coverage;
  require(get "nonvacuous" idle_coverage=Json.Bool false)"Progress-only empty activity was treated as therapeutic execution";
  let source_bound=repin(set["request";"operating_domain";"logical_limits";"max_source_attempts"](Json.int 1)positive)in
  let bounded=run source_bound in stopped "original source bound" "source_bound" "policy_domain_source_bound" bounded;
  equal_int 0 "histories"(get "coverage"(C.report bounded));
  resource_limits positive;
  (* The unmodified broad domain is retained as a bounded stopping control; no
     complete 1764-history result is inferred from a small witness domain. *)
  let original=repin(set["request";"budgets";"max_prefixes"](Json.int 1)(generous second))in
  stopped "original broad domain prefix cap" "incomplete" "policy_preservation_prefix_limit"(run original);
  let changed_budget=repin(set["request";"budgets";"max_prefixes"](Json.int 100001)positive)in
  let new_result=run changed_budget in complete new_result 9 47 48;
  require(Option.is_some(C.accepted new_result))"Independent safe budget edit lost new acceptance";
  require(text "request_fingerprint"(C.report result)<>text "request_fingerprint"(C.report new_result) &&
    get "digest"(get "coverage"(C.report result))<>get "digest"(get "coverage"(C.report new_result)))
    "Budget edit reused old request/exploration evidence";
  require(not(Json.equal(C.evidence accepted)(C.report new_result)))"Old accepted evidence silently followed a changed request";
  let foreign_domain=set["request";"operating_domain";"fixed_observations"](arr(observations 0 "valid"(Json.Bool true)))positive in
  rejects "unrepinned external domain" ["policy_implementation_contract"](fun()->run foreign_domain);
  let request=R.of_json(get "request" positive)in
  let old_behavior=behavior request in
  let moved=repin(set["request";"document";"program";"source_map";"0";"file"](str "separately_authored.py")positive)in
  let moved_request=R.of_json(get "request" moved)in
  rejects "old behavior with changed full source provenance" ["policy_correspondence"](fun()->
    C.check ~request:moved_request ~behavior:old_behavior
      ~implementation:(I.of_json ~library:(R.implementation_library moved_request)(get "implementation" moved))
      ~proposed:(U.of_json(get "proposed" moved)) ~limits);
  let wires=List.map(fun wire->let consumer=get "consumer" wire in
    if text "node" consumer="select_gate" && text "port" consumer="guard"then
      set["producer"](obj["node",str "true";"port",str "out"])wire else wire)(items "wires"(get "implementation" positive))in
  rejects "well-typed candidate authorization mismatch" ["policy_implementation_source_binding"]
    (fun()->run(set["implementation";"wires"](arr wires)positive));
  Printf.printf "Whole-domain preservation: independently counted 9-history passing domain, original unknown safety, failed/unsupported hard requirements, no-effect nonvacuity and %d fail-closed controls; material/export withheld.\n" !controls
