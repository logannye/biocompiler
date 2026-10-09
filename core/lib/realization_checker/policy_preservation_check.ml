open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module F = Bioc_domain.Policy_operating_domain
module D = Bioc_domain.Policy_document
module A = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module W = Bioc_checker.Work_budget
module S = Bioc_semantics.Policy_domain_reference
module P = Bioc_candidate_runtime.Policy_primitives
module T = Policy_trace_correspondence
module M = Policy_requirement_monitor
let profile = "biocompiler.policy_bounded_preservation.v0.1"
let limits_profile = "biocompiler.policy_preservation_resources.v0.1"
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let exact names value=Json.exact_fields names(Json.object_fields value)
let require condition code message=Diagnostic.require condition code message
let positive maximum value =
  let number=Json.integer value in
  require(Z.sign number>0 && Z.leq number(Z.of_int maximum)) "policy_preservation_limits" "Explicit checker resource limit is outside its finite profile.";
  Z.to_int number
type limits = {raw:Json.t;source:S.execution_bounds;candidate:P.limits;monitor:M.limits;
  step_work:int;step_retained:int;report_bytes:int;report_nodes:int}
let limits_of_json raw =
  ignore(D.document_digest raw);
  exact["profile";"source";"candidate";"monitor";"max_step_work";"max_step_retained";"max_report_bytes";"max_report_nodes"]raw;
  require(text "profile" raw=limits_profile) "policy_preservation_limits" "Unknown checker resource profile.";
  let candidate=get "candidate" raw and monitor=get "monitor" raw in
  exact["max_work";"max_events";"max_attempts";"max_microsteps"]candidate;
  exact["max_work";"max_obligations";"max_samples"]monitor;
  {raw;source=S.execution_bounds_of_json(get "source" raw);
   candidate={P.max_work=positive 10000000(get "max_work" candidate);
     max_events=positive 1000000(get "max_events" candidate);
     max_attempts=positive 10000(get "max_attempts" candidate);
     max_microsteps=positive 1000(get "max_microsteps" candidate)};
   monitor={M.max_work=positive 10000000(get "max_work" monitor);
     max_obligations=positive 10000(get "max_obligations" monitor);
     max_samples=positive 1000000(get "max_samples" monitor)};
   step_work=positive 10000000(get "max_step_work" raw);
   step_retained=positive 1000000(get "max_step_retained" raw);
   report_bytes=positive (8*1024*1024)(get "max_report_bytes" raw);
   report_nodes=positive 1000000(get "max_report_nodes" raw)}
let limits_to_json value=value.raw
type checked_implementation={checked:B.checked_binding;evidence_value:Json.t}
type result={report_value:Json.t;accepted_value:checked_implementation option}
type startup_pass=Input|Identity
type measurement = {
  total_cpu_seconds:float; source_step_cpu_seconds:float;
  candidate_step_cpu_seconds:float; correspondence_cpu_seconds:float;
  monitor_step_cpu_seconds:float; projection_encoding_cpu_seconds:float;
  candidate_transitions:P.transition_usage option;
}
let report value=value.report_value
let accepted value=value.accepted_value
let binding value=value.checked
let evidence value=value.evidence_value
type aggregate = {requirement:O.requirement;mutable histories:(string*Z.t)list;
  mutable samples:Z.t;mutable active:Z.t;mutable inactive:Z.t;mutable triggers:Z.t;
  mutable witnesses:(string*Json.t)list}
type stop = {category:string;diagnostic:Diagnostic.t}
exception Stop of stop
let stop category code message=raise(Stop{category;diagnostic={Diagnostic.code;message;path=None}})
let diagnostic_json(diagnostic:Diagnostic.t)=obj["code",str diagnostic.code;"message",str diagnostic.message;
  "path",(match diagnostic.path with None->Json.Null|Some path->str path)]
let work_diagnostic code=List.mem code[
  "policy_primitives_work_limit";"policy_primitives_trace_limit";"policy_primitives_settling_limit";
  "policy_primitives_output_limit";"policy_primitives_attempt_limit";
  "policy_primitives_limit";
  "policy_requirement_monitor_work_limit";"policy_requirement_monitor_obligation_limit";
  "policy_requirement_monitor_sample_limit"]
let source_identity correspondence key id =
  str(if key="events"then T.candidate_event_to_source correspondence id
    else T.candidate_attempt_to_source correspondence id)
let normalized_monitor correspondence row =
  let obligations=List.map(fun obligation->obj(List.map(fun(key,value)->key,
    if key="trigger" then source_identity correspondence "events"(Json.string value)
    else if key="attempt" && value<>Json.Null then source_identity correspondence "attempts"(Json.string value)
    else value)(Json.object_fields obligation)))(items "obligations" row)in
  obj(List.map(fun(key,value)->key,if key="obligations"then arr obligations else value)(Json.object_fields row))
let check_engine ~startup_charge ~clock ~measure ~share_candidate_transitions ~request ~behavior ~implementation ~proposed ~limits =
  let profile=if R.is_multi_site request then "biocompiler.policy_multi_site_preservation.v0.1" else profile in
  let started=if measure then clock()else 0. in
  let source_cpu=ref 0. and candidate_cpu=ref 0. and correspondence_cpu=ref 0.
  and monitor_cpu=ref 0. and encoding_cpu=ref 0. in
  let timed counter operation=if not measure then operation()else
    let before=clock()in
    Fun.protect ~finally:(fun()->counter:= !counter+.clock()-.before)operation in
  (* These constructors check original external roots again on every call. *)
  startup_charge Input(obj["request",R.to_json request;"behavior",O.behavior_to_json behavior]);
  (* Operational admission and independent correspondence each perform their
     own canonical original-document decode. Retain both logical input passes. *)
  startup_charge Input(D.to_json(R.document request));
  startup_charge Input(D.to_json(R.document request));
  let admitted=A.admit ~request ~behavior in
  startup_charge Input(obj["admission",A.report admitted;"implementation",I.to_json implementation;
    "proposed",U.to_json proposed]);
  let checked=B.check ~admitted ~implementation ~proposed in
  let domain=R.operating_domain request and budgets=R.budgets request in
  require(limits.candidate.max_attempts>domain.logical_limits.max_source_attempts)
    "policy_preservation_limits" "Candidate allocation resource ceiling must exceed the original semantic source bound.";
  startup_charge Input(obj["behavior",O.behavior_to_json behavior;"domain",F.to_json domain;
    "bounds",S.execution_bounds_to_json limits.source]);
  let source=S.create ~behavior ~domain ~bounds:limits.source in
  let environment=B.environment checked in
  startup_charge Input(obj["implementation",I.to_json(B.implementation checked);
    "environment",obj["executor",str environment.executor;"horizon_ticks",Json.int environment.horizon_ticks;
      "slots",arr(List.map(fun(slot:B.slot)->obj["identity",str slot.identity;"target",str slot.target;
        "start_tick",Json.int slot.start_tick])environment.slots)];"limits",limits.raw]);
  let candidate=P.initialize ~implementation:(B.implementation checked)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:limits.candidate in
  (* Proof witnesses belong only to this fresh invocation. Domain/source,
     correspondence and requirement execution never consume cached verdicts. *)
  let transition_session=if share_candidate_transitions then
    Some(P.create_transition_session candidate)else None in
  let work=ref 0 and source_work=ref Z.zero and candidate_work=ref Z.zero and monitor_work=ref Z.zero in
  let prefixes=ref 1 and transitions=ref 0 and matched=ref 1 and histories=ref 0 and peak_retained=ref 0 in
  let path=ref [] and latest_source=ref None and latest_candidate=ref None in
  let retained_witnesses=ref 0 and live_trace=ref 0 and activity=ref [] in
  let active_prefixes=ref 0 and inactive_prefixes=ref 0 and created_attempts=ref 0 in
  startup_charge Identity(I.to_json(B.implementation checked));
  let frontier_identity=obj["profile",str profile;"request",str(R.fingerprint request);
    "implementation",str(I.fingerprint(B.implementation checked));"limits",limits.raw]in
  startup_charge Identity frontier_identity;
  let frontier_digest=ref(Canonical.fingerprint frontier_identity)in
  let output=W.create_output ~profile ~error_code:"policy_preservation_report_limit"
    ~max_bytes:limits.report_bytes ~max_nodes:limits.report_nodes ()in
  let aggregates=List.map(fun(requirement:O.requirement)->{requirement;histories=[];samples=Z.zero;
    active=Z.zero;inactive=Z.zero;triggers=Z.zero;witnesses=[]})behavior.requirements in
  let remaining ()=budgets.max_work- !work in
  let reserve amount=if amount<0 || amount>remaining()then
    stop "incomplete" "policy_preservation_work_limit" "Complete traversal lacks the next required execution reservation." in
  let charge amount=reserve amount;work:= !work+amount in
  let charge_json value=let bytes=timed encoding_cpu(fun()->Canonical.encode_bounded ~max_bytes:(8*1024*1024)value)in
    charge(String.length bytes);bytes in
  let memory amount=let total=amount+ !retained_witnesses in if total>budgets.max_trace_items then
    stop "incomplete" "policy_preservation_trace_limit" "Live depth-first traversal exceeds the original retained-trace bound."
    else(live_trace:=amount;peak_retained:=max !peak_retained total)in
  let rec nodes value=match value with
    |Json.Array values->1+List.fold_left(fun count value->count+nodes value)0 values
    |Json.Object values->1+List.fold_left(fun count(_,value)->count+1+nodes value)0 values
    |_->1 in
  let retain_witness witness=
    let bytes=charge_json witness in
    (* Output validation and retained-node census each visit the witness again. *)
    charge(2*String.length bytes);W.reserve_json output witness;
    let count=nodes witness in
    if count>budgets.max_trace_items- !live_trace- !retained_witnesses then
      stop "incomplete" "policy_preservation_trace_limit" "Retained cross-history witnesses exceed the original trace budget.";
    retained_witnesses:= !retained_witnesses+count;memory !live_trace in
  let witnessed aggregate key row = if not(List.mem_assoc key aggregate.witnesses)then(
    let witness=obj["history",arr !path;"requirement",row]in
    retain_witness witness;
    aggregate.witnesses<-aggregate.witnesses@[key,witness])in
  let terminal monitor correspondence source_report =
    let candidate_rows=M.source_view monitor in
    let normalized=List.map(normalized_monitor correspondence)candidate_rows in
    let source_rows=items "requirements" source_report in
    ignore(charge_json(arr normalized));
    if List.length normalized<>List.length source_rows then
      stop "monitor_mismatch" "policy_preservation_monitor" "Requirement ledger cardinality differs.";
    List.iter2(fun candidate source->
      if text "status" candidate="unsupported" || text "status" source="unsupported"then
        List.iter(fun key->if not(Json.equal(get key candidate)(get key source))then
          stop "monitor_mismatch" "policy_preservation_monitor"
            "Unsupported requirement lost original identity or meaning.")["id";"kind";"source"]
      else if not(Json.equal candidate source)then
        stop "monitor_mismatch" "policy_preservation_monitor" "Independent source and candidate requirement ledgers disagree.")normalized source_rows;
    let report=M.report monitor in ignore(charge_json report);
    let rows=items "requirements" report in
    if List.map(fun row->text "id" row)rows<>List.map(fun aggregate->aggregate.requirement.requirement_id)aggregates then
      stop "monitor_mismatch" "policy_preservation_monitor" "Independent monitor changed the original requirement inventory/order.";
    List.iter2(fun aggregate row->
      let source=List.find(fun source->text "id" source=text "id" row)source_rows in
      let status=if text "status" source="unsupported"then "unsupported"else text "status" row in
      let coverage=get "coverage" row in
      require(List.mem status["pass";"fail";"unknown";"not_exercised";"unsupported"])
        "policy_preservation_monitor" "Unknown independent requirement status.";
      let count=Option.value(List.assoc_opt status aggregate.histories)~default:Z.zero in
      aggregate.histories<-List.remove_assoc status aggregate.histories@[status,Z.succ count];
      let add field previous=Z.add previous(Json.integer(get field coverage))in
      aggregate.samples<-add "samples" aggregate.samples;
      aggregate.active<-add "active" aggregate.active;aggregate.inactive<-add "inactive" aggregate.inactive;
      aggregate.triggers<-add "enabled_triggers" aggregate.triggers;
      witnessed aggregate status row;
      if Z.sign(Json.integer(get "active" coverage))>0 then witnessed aggregate "active" row;
      if Z.sign(Json.integer(get "inactive" coverage))>0 then witnessed aggregate "inactive" row;
      if Z.sign(Json.integer(get "enabled_triggers" coverage))>0 then witnessed aggregate "triggered" row)aggregates rows;
    incr histories in
  let rec visit live source candidate monitor correspondence source_report prefix =
    path:=prefix;memory live;
    if S.finished source then(match source_report with Some report->terminal monitor correspondence report
      |None->stop "source_error" "policy_preservation_empty_domain" "A completed domain emitted no source execution.")else(
      let count=ref 0 in
      let rec choices sequence =
        path:=prefix;latest_source:=source_report;latest_candidate:=None;charge 1;
        match sequence()with
        |Seq.Nil->if !count=0 then stop "domain_contradiction" "policy_preservation_no_continuation"
            "A reachable original-domain prefix has no permitted continuation."
        |Seq.Cons(batch,rest)->
            incr count;
            let batch_json=F.batch_to_json batch in
            path:=prefix@[batch_json];ignore(charge_json batch_json);
            if !prefixes>=budgets.max_prefixes || !transitions>=budgets.max_transitions then
              stop "incomplete" "policy_preservation_prefix_limit" "Original traversal prefix/transition budget is exhausted.";
            incr prefixes;incr transitions;
            let reservation=S.next_work_reservation source in
            require(Z.fits_int reservation)"policy_preservation_limits""Source work reservation exceeds the checker integer domain.";
            reserve(Z.to_int reservation);
            let source_ceiling=positive 100000(get "max_trace_items"(S.execution_bounds_to_json limits.source))in
            memory(live+source_ceiling);
            let advanced=match timed source_cpu(fun()->S.step source batch)with
              |S.Stopped failure->
                  let charged=failure.receipt.delta.charged_work in charge(Z.to_int charged);
                  source_work:=Z.add !source_work charged;latest_source:=failure.receipt.execution;
                  raise(Stop{category=(match failure.kind with S.Exhausted->"incomplete"|S.Source_bound->"source_bound"|S.Source_error->"source_error");
                    diagnostic=failure.diagnostic})
              |S.Advanced advanced->
                  let charged=advanced.receipt.delta.charged_work in charge(Z.to_int charged);
                  source_work:=Z.add !source_work charged;latest_source:=advanced.receipt.execution;advanced in
            let source_report=match advanced.receipt.execution with Some report->report
              |None->Diagnostic.fail "policy_preservation_source" "Successful prefix lacks source execution."in
            let source_retained=Z.to_int advanced.receipt.delta.reported_trace_items in
            memory(live+source_retained);
            let translated=T.input correspondence batch in
            let before=P.usage candidate in
            let step_work=min(min limits.step_work(remaining()))(limits.candidate.max_work-before.work)in
            let step_retained=min(min limits.step_retained(budgets.max_trace_items-live-source_retained- !retained_witnesses))
              (limits.candidate.max_events-before.retained)in
            if step_work<=0 || step_retained<=0 then stop "incomplete" "policy_preservation_work_limit" "No resource allowance remains for the independent candidate step.";
            let next_candidate,frame=match timed candidate_cpu(fun()->match transition_session with
              |None->P.step ~max_step_work:step_work ~max_step_retained:step_retained candidate translated
              |Some session->P.step_with_transition_session session
                  ~max_step_work:step_work ~max_step_retained:step_retained candidate translated)with
              |value->value
              |exception Diagnostic.Error diagnostic->charge step_work;candidate_work:=Z.add !candidate_work(Z.of_int step_work);
                  raise(Stop{category=(if work_diagnostic diagnostic.code then "incomplete"else "candidate_error");diagnostic})in
            let after=P.usage next_candidate in
            let delta=after.work-before.work in charge delta;candidate_work:=Z.add !candidate_work(Z.of_int delta);
            let frame_json=P.frame_to_json frame in latest_candidate:=Some frame_json;
            let frame_bytes=charge_json frame_json in
            (* Correspondence independently serializes this frame into its
               history identity as well; do not charge that second visit away. *)
            charge(String.length frame_bytes);
            ignore(charge_json(obj["source_frame",advanced.frame;"source_attempts",arr(items "attempts" source_report)]));
            let next_correspondence=match timed correspondence_cpu(fun()->T.advance correspondence ~batch ~source_frame:advanced.frame
                ~source_attempts:(items "attempts" source_report) ~source_creations:advanced.creations ~candidate:frame)with
              |value->value
              |exception Diagnostic.Error diagnostic->raise(Stop{category="counterexample";diagnostic})in
            let before_monitor=M.usage monitor in
            let reservation=limits.monitor.max_work-before_monitor.work in reserve reservation;
            let next_monitor=match timed monitor_cpu(fun()->M.step monitor frame)with
              |value->value
              |exception Diagnostic.Error diagnostic->charge reservation;monitor_work:=Z.add !monitor_work(Z.of_int reservation);
                  raise(Stop{category=(if work_diagnostic diagnostic.code then "incomplete"else "monitor_error");diagnostic})in
            let after_monitor=M.usage next_monitor in
            let delta=after_monitor.work-before_monitor.work in charge delta;monitor_work:=Z.add !monitor_work(Z.of_int delta);
            let weight=source_retained+after.retained+after_monitor.obligations+after_monitor.samples in
            memory(live+weight);incr matched;
            created_attempts:= !created_attempts+List.length advanced.creations;
            let is_active=List.exists(fun(attempt:P.attempt)->attempt.status=P.Active)frame.attempts in
            if is_active then incr active_prefixes else incr inactive_prefixes;
            let activity_key=if is_active then "active"else "inactive"in
            if not(List.mem_assoc activity_key !activity)then(
              let witness=obj["history",arr !path;"source_frame",advanced.frame]in
              retain_witness witness;activity:= !activity@[activity_key,witness]);
            let correspondence_identity=T.identity next_correspondence in
            let monitor_report=M.identity next_monitor in
            let correspondence_hash=Canonical.sha256(charge_json correspondence_identity)
            and monitor_hash=Canonical.sha256(charge_json monitor_report)in
            frontier_digest:=Canonical.sha256(charge_json(obj["previous",str !frontier_digest;"input",batch_json;
              "correspondence",str correspondence_hash;"monitor",str monitor_hash]));
            visit(live+weight)advanced.next next_candidate next_monitor next_correspondence(Some source_report)!path;
            choices rest in
      choices(S.choices source))in
  (* An enclosing startup exhaustion must propagate with its own identity,
     rather than become a caught source/candidate traversal verdict. *)
  startup_charge Identity(B.report checked);
  let stopped =
    try
      ignore(charge_json(obj["request",R.to_json request;"behavior",O.behavior_to_json behavior;
        "implementation",I.to_json(B.implementation checked);"proposed",U.to_json proposed;"limits",limits.raw]));
      ignore(charge_json(B.report checked));
      let correspondence=T.create checked in
      reserve limits.monitor.max_work;
      let monitor=match M.create ~binding:checked ~limits:limits.monitor with
        |value->let used=(M.usage value).work in charge used;monitor_work:=Z.of_int used;value
        |exception Diagnostic.Error diagnostic->charge limits.monitor.max_work;monitor_work:=Z.of_int limits.monitor.max_work;
            raise(Stop{category=(if work_diagnostic diagnostic.code then "incomplete"else "monitor_error");diagnostic})in
      visit 0 source candidate monitor correspondence None [];
      if !histories=0 then stop "domain_contradiction" "policy_preservation_empty_domain" "No complete permitted input history exists.";
      None
    with
    |Stop value->Some value
    |Diagnostic.Error diagnostic->Some{category=(if String.starts_with ~prefix:"policy_domain_" diagnostic.code then "domain_contradiction"
        else if diagnostic.code="policy_preservation_report_limit" then "incomplete"else "checker_error");diagnostic}in
  let complete=stopped=None in
  let requirement_rows=List.map(fun aggregate->
    let count name=Option.value(List.assoc_opt name aggregate.histories)~default:Z.zero in
    let nonvacuous=if aggregate.requirement.kind="progress" then Z.sign aggregate.triggers>0
      else Z.sign aggregate.samples>0 && Z.sign aggregate.active>0 && Z.sign aggregate.inactive>0 in
    let status=if Z.sign(count "fail")>0 then "fail"else if Z.sign(count "unsupported")>0 then "unsupported"
      else if not complete || Z.sign(count "unknown")>0 || not nonvacuous || Z.sign(count "pass")=0 then "unknown"else "pass"in
    obj["id",str aggregate.requirement.requirement_id;"kind",str aggregate.requirement.kind;
      "source",aggregate.requirement.source;"status",str status;"nonvacuous",Json.Bool nonvacuous;
      "histories",obj(List.map(fun name->name,Json.Int(count name))["pass";"fail";"unknown";"not_exercised";"unsupported"]);
      "coverage",obj["samples",Json.Int aggregate.samples;"active",Json.Int aggregate.active;
        "inactive",Json.Int aggregate.inactive;"enabled_triggers",Json.Int aggregate.triggers];
      "witnesses",obj aggregate.witnesses])aggregates in
  let exercised= !created_attempts>0 && !active_prefixes>0 && !inactive_prefixes>0 in
  let requirements_pass=complete && exercised && List.for_all(fun row->text "status" row="pass")requirement_rows in
  let report_value=obj["schema_version",str "biocompiler.policy_preservation_report.v0.1";"profile",str profile;
    "request_fingerprint",str(R.fingerprint request);"binding",B.report checked;"limits",limits.raw;
    "coverage",obj["complete",Json.Bool complete;"prefixes_started",Json.int !prefixes;
      "matched_prefixes",Json.int !matched;"transitions",Json.int !transitions;"histories",Json.int !histories;
      "traversal",str "exhaustive_depth_first_no_merging";"digest",str !frontier_digest];
    "program_coverage",obj["nonvacuous",Json.Bool exercised;"created_attempts",Json.int !created_attempts;
      "active_prefixes",Json.int !active_prefixes;"inactive_prefixes",Json.int !inactive_prefixes;"witnesses",obj !activity];
    "usage",obj["work",Json.int !work;"source_work",Json.Int !source_work;
      "candidate_work",Json.Int !candidate_work;"monitor_work",Json.Int !monitor_work;
      "peak_retained_trace_items",Json.int !peak_retained];
    "preservation",str(if complete then "pass"else match stopped with
      |Some{category=("counterexample"|"candidate_error"|"monitor_mismatch");_}->"fail"|_->"unassessed");
    "requirements",arr requirement_rows;"assurance",str(if requirements_pass then "bounded_requirements_satisfied"else "not_established");
    "status",str(if requirements_pass then "checked_implementation"else if complete then "requirements_not_satisfied"else "incomplete");
    "stopped",(match stopped with None->Json.Null|Some value->obj["category",str value.category;
      "diagnostic",diagnostic_json value.diagnostic;"history",arr !path;
      "source_execution",Option.value !latest_source ~default:Json.Null;
      "candidate_frame",Option.value !latest_candidate ~default:Json.Null]);
    "target_status",str "unassessed";"material",str "unassessed";"artifact",str "withheld";"export",str "withheld"]in
  let publication=Canonical.encode_bounded ~max_bytes:limits.report_bytes report_value in
  let publication_work=2*String.length publication+256 in
  require(publication_work<=remaining())"policy_preservation_publication_work_limit"
    "No global work remains to publish a complete receipt; no checked implementation is returned.";
  work:= !work+publication_work;
  let report_value=obj(List.map(fun(key,value)->key,if key="usage"then
    obj(List.map(fun(name,item)->name,if name="work"then Json.int !work else item)(Json.object_fields value))
    else value)(Json.object_fields report_value))in
  let final_output=W.create_output ~profile ~error_code:"policy_preservation_report_limit"
    ~max_bytes:limits.report_bytes ~max_nodes:limits.report_nodes ()in
  W.reserve_json final_output report_value;
  let result={report_value;accepted_value=(if requirements_pass then Some{checked;evidence_value=report_value}else None)}in
  result,{total_cpu_seconds=(if measure then clock()-.started else 0.);
    source_step_cpu_seconds= !source_cpu;candidate_step_cpu_seconds= !candidate_cpu;
    correspondence_cpu_seconds= !correspondence_cpu;monitor_step_cpu_seconds= !monitor_cpu;
    projection_encoding_cpu_seconds= !encoding_cpu;
    candidate_transitions=Option.map P.transition_usage transition_session}

let check_with_startup_charge ~startup_charge ~request ~behavior ~implementation ~proposed ~limits =
  fst(check_engine ~startup_charge ~clock:(fun()->0.) ~measure:false ~share_candidate_transitions:false
    ~request ~behavior ~implementation ~proposed ~limits)

let check_measured ~clock ~share_candidate_transitions ~request ~behavior ~implementation ~proposed ~limits =
  check_engine ~startup_charge:(fun _ _->()) ~clock ~measure:true ~share_candidate_transitions
    ~request ~behavior ~implementation ~proposed ~limits

let check ~request ~behavior ~implementation ~proposed ~limits=
  check_with_startup_charge ~startup_charge:(fun _ _->()) ~request ~behavior ~implementation ~proposed ~limits
