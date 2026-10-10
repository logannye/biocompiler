(* Independent finite-domain equivalence and diagnostic timing only. Timings are
   outside canonical evidence and cannot grant material/export authority. *)
open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module R = Bioc_domain.Policy_realization_request
module U = Bioc_domain.Policy_implementation_binding
module L = Bioc_compiler.Policy_lowering
module P = Bioc_candidate_runtime.Policy_primitives
module C = Bioc_realization_checker.Policy_preservation_check
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let arr values=Json.Array values
let str value=Json.String value
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let integer name value=Z.to_int(Json.integer(get name value))
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000(really_input_string channel(in_channel_length channel)))
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Absent original field "^key);
    obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |_->failwith "Mutation escaped the original fixture object"
let behavior request=L.lower(Bioc_checker.Policy_admission.admit
  ~document:(R.document request) ~descriptors:(R.definitions request))
let repin case=
  (* Refresh only original authority. No compiler supplies the candidate graph,
     correspondence map, expected domain census, verdict or resource diagnosis. *)
  let request=R.of_json(get "request" case)in
  set["implementation";"authority"](obj[
    "source_artifact_digest",str(D.artifact_digest(R.document request));
    "descriptors_digest",str(O.descriptors_digest(R.definitions request));
    "domain_digest",str(F.digest(R.operating_domain request));
    "implementation_catalog_digest",str(Canonical.fingerprint(get "implementations"(D.to_json(R.document request))));
    "library_digest",str(I.library_digest(R.implementation_library request))])case
let limits_json=obj[
  "profile",str "biocompiler.policy_preservation_resources.v0.1";
  "source",obj["max_ticks",Json.int 16;"max_inputs",Json.int 256;"max_encounters",Json.int 4;
    "max_attempts",Json.int 32;"max_work",Json.int 100000;"max_trace_items",Json.int 2000;"max_microsteps",Json.int 32];
  "candidate",obj["max_work",Json.int 1000000;"max_events",Json.int 100000;"max_attempts",Json.int 32;"max_microsteps",Json.int 32];
  "monitor",obj["max_work",Json.int 1000000;"max_obligations",Json.int 1000;"max_samples",Json.int 100000];
  "max_step_work",Json.int 1000000;"max_step_retained",Json.int 100000;
  "max_report_bytes",Json.int(8*1024*1024);"max_report_nodes",Json.int 1000000]
let observation tick slot value=obj["slot",str slot;"observation",str "condition";
  "available_tick",Json.int tick;"observed_tick",Json.int tick;"status",str "valid";"value",Json.Bool value]
let observations tick value=List.map(fun slot->observation tick slot value)["e1";"e2"]
let domain_case original fixed factors feedback=
  let domain=get "operating_domain"(get "request" original)in
  let domain=set["fixed_observations"](arr fixed)(set["observation_factors"](arr factors)
    (set["lifecycle_factors"](arr[])(set["feedback_factors"](arr feedback)domain)))in
  let budgets=obj["max_prefixes",Json.int 100000;"max_transitions",Json.int 100000;
    "max_work",Json.int 100000000;"max_trace_items",Json.int 1000000]in
  let result=repin(set["request";"budgets"]budgets(set["request";"operating_domain"]domain original))in
  require(Json.equal(get "document"(get "request" original))(get "document"(get "request" result)))
    "Timing witness changed original source, deployment, catalog or hard assurance";
  require(Json.equal(get "proposed" original)(get "proposed" result))"Timing witness changed original binding";
  let without_authority value=obj(List.filter(fun(key,_)->key<>"authority")(Json.object_fields value))in
  require(Json.equal(without_authority(get "implementation" original))(without_authority(get "implementation" result)))
    "Timing witness changed the independently supplied candidate graph";
  result
exception Measurement_clock_failure
let run ?(limits=limits_json) ?(clock=Sys.time) share case=
  let request=R.of_json(get "request" case)in
  let behavior=behavior request in
  let implementation=I.of_json ~library:(R.implementation_library request)(get "implementation" case)
  and proposed=U.of_json(get "proposed" case)and limits=C.limits_of_json limits in
  (* This collection is identical in both modes and excluded from check timing.
     Whole-command monotonic wall time remains in the development receipt. *)
  Gc.full_major();
  let start=Unix.gettimeofday()in
  let result,measurement=C.check_measured ~clock ~share_candidate_transitions:share ~request ~behavior ~implementation ~proposed ~limits in
  result,measurement,Unix.gettimeofday()-.start
let compare label (fresh,_,_) (shared,_,_)=
  require(Canonical.encode(C.report fresh)=Canonical.encode(C.report shared))
    (label^": sharing changed full canonical evidence, charges, original histories or first failure");
  require(Option.is_some(C.accepted fresh)=Option.is_some(C.accepted shared))
    (label^": sharing changed private acceptance");
  Option.iter(fun checked->require(Json.equal(C.evidence checked)(C.report shared))
    (label^": accepted token evidence differs"))(C.accepted shared)
let coverage result histories transitions prefixes=
  let report=C.report result and coverage=get "coverage"(C.report result)in
  require(get "complete" coverage=Json.Bool true && text "preservation" report="pass")
    ("Independent finite timing domain did not complete: "^Canonical.encode(get "stopped" report));
  List.iter(fun(name,expected)->require(integer name coverage=expected)("Independent timing census differs at "^name))
    ["histories",histories;"transitions",transitions;"prefixes_started",prefixes;"matched_prefixes",prefixes];
  require(text "traversal" coverage="exhaustive_depth_first_no_merging")"Timing comparison pruned original histories";
  List.iter(fun key->require(text key report="withheld")"Preservation benchmark acquired material/export authority")["artifact";"export"]
let measurement_row label iteration share (result,(measurement:C.measurement),wall)=
  let number value=str(Printf.sprintf "%.9f" value)in
  let transitions=match measurement.candidate_transitions with None->Json.Null|Some(value:P.transition_usage)->
    obj["requests",Json.int value.requests;"evaluations",Json.int value.evaluations;"reuses",Json.int value.reuses;
      "bypasses",Json.int value.bypasses;"proof_work",Json.int value.proof_work;"peak_bytes",Json.int value.peak_bytes;
      "current_entries",Json.int value.current_entries]in
  let report=C.report result in
  obj["case",str label;"iteration",Json.int iteration;"share_candidate_transitions",Json.Bool share;
    "wall_clock_seconds",number wall;"total_cpu_seconds",number measurement.total_cpu_seconds;
    "source_step_cpu_seconds",number measurement.source_step_cpu_seconds;
    "candidate_step_cpu_seconds",number measurement.candidate_step_cpu_seconds;
    "correspondence_cpu_seconds",number measurement.correspondence_cpu_seconds;
    "monitor_step_cpu_seconds",number measurement.monitor_step_cpu_seconds;
    "projection_encoding_cpu_seconds",number measurement.projection_encoding_cpu_seconds;
    "candidate_transitions",transitions;"report_sha256",str(Canonical.fingerprint report);
    "coverage",get "coverage" report;"usage",get "usage" report;
    "accepted",Json.Bool(Option.is_some(C.accepted result))]
let failure_pair label code limits case=
  let fresh=run ~limits false case and shared=run ~limits true case in
  compare label fresh shared;
  let result,_,_=shared in
  require(Option.is_none(C.accepted result)) (label^": exhausted checking acquired authority");
  let report=C.report result in
  require(get "complete"(get "coverage" report)=Json.Bool false &&
    text "code"(get "diagnostic"(get "stopped" report))=code)(label^": wrong independent exhaustion boundary")
let exception_pair label codes limits case=
  let rejected share=match run ~limits share case with
    |_->failwith(label^": failed publication returned authority")
    |exception Diagnostic.Error diagnostic->require(List.mem diagnostic.code codes)(label^": unexpected diagnostic");diagnostic in
  require(rejected false=rejected true)(label^": sharing changed the exact thrown diagnostic")
let ()=
  require(Array.length Sys.argv=2)"Supply the independently authored source/graph fixture";
  let fixture=read Sys.argv.(1)in
  let original=List.find(fun row->text "name" row="exclusion_sibling_resolved_chassis")(items "cases" fixture)in
  let original_bytes=Canonical.encode original in
  let feedback=obj["effect",str "response";"ticks",arr[Json.int 2];
    "attempt_selector",str "all_previously_created";"outcomes",arr[str "completed";str "failed"];
    "routes",arr[str "correlated"];"max_rows_per_attempt_tick",Json.int 1]in
  let baseline=domain_case original(observations 0 false@observations 1 true@observations 2 false)[][feedback]in
  let factor=obj["slots",arr[str "e1"];"observation",str "condition";"ticks",arr[Json.int 0];
    "alphabet",str "known_truth_and_evidence_status.v1";"age_ticks",arr[Json.int 0];"max_rows_per_slot_tick",Json.int 1]in
  let convergent=domain_case original([observation 0 "e2" false]@observations 1 true@observations 2 false)[factor][]in
  (* Complete alphabet: none,true,false,missing,invalid,conflicting. Seven ticks
     per leaf yield6 histories,42 edges,43 prefixes. Missing/Invalid are not
     merged in the source or monitor; only their later exact candidate states
     may share the same next transition after the strictly newer observation. *)
  let rows=ref []in
  let pair label iteration reverse case histories transitions prefixes=
    let fresh,shared=if reverse then let shared=run true case in let fresh=run false case in fresh,shared
      else let fresh=run false case in let shared=run true case in fresh,shared in
    compare label fresh shared;
    let result,_,_=fresh in coverage result histories transitions prefixes;
    let _,fresh_measure,_=fresh and _,shared_measure,_=shared in
    require(Option.is_none fresh_measure.candidate_transitions)"Disabled benchmark created a sharing session";
    let usage=Option.get shared_measure.candidate_transitions in
    require(usage.requests=transitions && usage.evaluations+usage.reuses=usage.requests)
      "Candidate sharing accounting omitted an original transition";
    require(usage.proof_work<=64*1024*1024 && usage.peak_bytes<=8*1024*1024 && usage.current_entries<=32)
      "Candidate congruence exceeded its independently fixed auxiliary bounds";
    List.iter(fun(measurement:C.measurement)->
      let phases=[measurement.source_step_cpu_seconds;measurement.candidate_step_cpu_seconds;
        measurement.correspondence_cpu_seconds;measurement.monitor_step_cpu_seconds;
        measurement.projection_encoding_cpu_seconds]in
      let finite_nonnegative value=match classify_float value with FP_nan|FP_infinite->false|_->value>=0. in
      require(List.for_all finite_nonnegative(measurement.total_cpu_seconds::phases) &&
        List.fold_left(+.)0. phases<=measurement.total_cpu_seconds+.0.001)
        "Diagnostic CPU phases are nonfinite, negative or exceed their enclosing check")
      [fresh_measure;shared_measure];
    rows:= !rows@[measurement_row label iteration false fresh;measurement_row label iteration true shared];
    result,usage in
  let positive,_=pair "independent_nine_history_baseline" 1 false baseline 9 47 48 in
  require(Option.is_some(C.accepted positive))"Original passing baseline lost independent acceptance";
  let first,usage=pair "independent_six_history_convergence" 1 false convergent 6 42 43 in
  require(usage.reuses>0 && usage.evaluations<usage.requests)"Literal convergence witness avoided no candidate execution";
  let second,repeated_usage=pair "independent_six_history_convergence" 2 true convergent 6 42 43 in
  require(Json.equal(C.report first)(C.report second) && usage=repeated_usage)
    "Fresh invocation reused stale proof state or changed its complete transition census";
  List.iter(fun(label,path,code)->failure_pair label code(set path(Json.int 1)limits_json)convergent)[
    "source work",["source";"max_work"],"policy_execution_work_limit";
    "candidate work",["candidate";"max_work"],"policy_primitives_work_limit";
    "candidate per-step work",["max_step_work"],"policy_primitives_work_limit";
    "candidate per-step retained",["max_step_retained"],"policy_primitives_trace_limit";
    "monitor work",["monitor";"max_work"],"policy_requirement_monitor_work_limit"];
  failure_pair "original prefix budget" "policy_preservation_prefix_limit" limits_json
    (set["request";"budgets";"max_prefixes"](Json.int 1)convergent);
  exception_pair "publication work" ["policy_preservation_publication_work_limit"] limits_json
    (set["request";"budgets";"max_work"](Json.int 1)convergent);
  exception_pair "publication bytes" ["response_too_large";"policy_preservation_report_limit"]
    (set["max_report_bytes"](Json.int 1)limits_json)convergent;
  List.iter(fun share->match run ~clock:(fun()->raise Measurement_clock_failure) share baseline with
    |_->failwith "A diagnostic clock exception returned checked authority"
    |exception Measurement_clock_failure->())[false;true];
  require(Canonical.encode original=original_bytes)"Benchmark mutated its independently supplied authority";
  let output=obj["schema_version",str "biocompiler.policy_candidate_congruence_measurement.v0.1";
    "scope",str "Hosted diagnostic timing and canonical-equivalence controls; no speedup, material or release acceptance claim.";
    "fixture_fingerprint",str(Canonical.fingerprint fixture);
    "timing_boundary",str "Fresh complete C.check_measured; decoding and preceding full_major collection excluded. Native wall uses Unix.gettimeofday; development receipt retains whole-command monotonic wall. CPU phases are diagnostic only.";
    "samples",arr !rows;"negative_controls",Json.int 9]in
  print_endline(Canonical.encode output)
