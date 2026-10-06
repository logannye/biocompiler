open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module R=Bioc_domain.Policy_material_request
module Q=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module F=Bioc_domain.Policy_operating_domain
module A=Bioc_checker.Policy_realization_admission
module B=Bioc_checker.Policy_implementation_binding_check
module S=Bioc_semantics.Policy_domain_reference
module P=Bioc_candidate_runtime.Policy_primitives
module T=Bioc_realization_checker.Policy_trace_correspondence
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let obj values=Json.Object values
let arr values=Json.Array values
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let items key raw=Json.array(get key raw)
let integer value=Z.to_int(Json.integer value)
let number key raw=integer(get key raw)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let rejects label code action=match action()with
  |_->failwith("Accepted domain negative control: "^label)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)
      (label^": wrong diagnostic "^diagnostic.code)
let run handler role operation payload=
  let request:Protocol.request={request_id="material-timing-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered domain material operation failed: "^operation)
let census = function
  |"simultaneous_deadline_lifecycle"->[1;1;1;27;27;27;27],27,111,112
  |_->failwith "Unreviewed material timing fixture"
let sorted key rows=List.sort(fun a b->String.compare(text key a)(text key b))rows
let original_literals case=
  let request=get "request" case and expected=get "expected" case in
  let prefix,histories,transitions,prefixes=census(text "id" case)in
  require(3*3*3=27)
    "Independent product census changed";
  require(List.map integer(items "prefixes_after_tick" expected)=prefix &&
    List.fold_left(+)0 prefix=transitions && prefixes=transitions+1 &&
    number "histories" expected=histories && number "transitions" expected=transitions &&
    number "prefixes_started" expected=prefixes)"Original finite domain census changed";
  List.iter(fun(key,path)->require(text key expected=Canonical.fingerprint(at path request))
    ("Full original authority changed: "^key))[
    "request_fingerprint",[];"source_request_digest",["implementation_request"];
    "source_artifact_digest",["implementation_request";"document"];
    "definitions_digest",["implementation_request";"definitions"];
    "domain_digest",["implementation_request";"operating_domain"];
    "library_digest",["implementation_request";"implementation_library"];
    "material_contract_digest",["material_contract"];
    "kernel_digest",["material_contract";"body";"kernel"];
    "carrier_digest",["material_contract";"body";"carriers"];
    "context_digest",["context"]];
  require(number "carrier_count" expected=92 &&
    List.length(Json.array(at["material_contract";"body";"carriers"]request))=92 &&
    number "node_count" expected=15)"Original complete primitive/carrier inventory changed";
  let original=R.implementation_request(R.of_json request)in
  let source=Bioc_checker.Policy_check.check(Q.document original)in
  require(text "status" source="valid" && List.length(items "obligations" expected)=23 &&
    items "unresolved_obligations" source=items "obligations" expected)
    "Domain request weakened or omitted an original source obligation";
  let requirements=List.filter(fun value->text "$type" value="Requirement")
    (Json.array(at["implementation_request";"document";"program";"declarations"]request))in
  require(List.map(text "id")(sorted "id" requirements)=
    ["exclusive_selection";"initiation_progress";"request_progress"] &&
    Json.equal(arr requirements)(get "requirements" expected))"Original three hard requirements changed"
let assessment_literals expected compiled=
  let report=get "report" compiled and candidate=get "candidate" compiled in
  List.iter(fun key->require(get key report=get key expected)
    ("Material domain claim changed: "^key^(if key="status" then
      "; original domain "^text "domain_digest" expected^"; complete fresh report: "^Canonical.encode report else "")))
    ["status";"claim_scope";"material_status";"context_status";"empirical";"artifact";"export"];
  require(get "artifact" compiled=Json.Null && get "all_original_obligations_discharged" report=Json.Bool true)
    "Compilation published material or omitted the complete original conjunction";
  require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
    List.for_all(fun row->text "status" row="discharged" && get "evidence" row<>Json.Null)(items "obligations" report))
    "Original obligation ledger lost a discharge or its evidence";
  let preservation=get "preservation" report in
  require(text "status" preservation="checked_implementation" && text "preservation" preservation="pass" &&
    at["coverage";"complete"]preservation=Json.Bool true &&
    at["program_coverage";"nonvacuous"]preservation=Json.Bool true)
    "Domain exploration was incomplete, failing or vacuous";
  List.iter(fun key->require(at["coverage";key]preservation=get key expected)("Exhaustive census differs: "^key))
    ["histories";"transitions";"prefixes_started"];
  require(at["coverage";"matched_prefixes"]preservation=get "prefixes_started" expected)
    "A permitted transition was omitted from correspondence";
  let requirements=items "requirements" preservation in
  require(List.map(text "id")(sorted "id" requirements)=
    ["exclusive_selection";"initiation_progress";"request_progress"])
    "Domain requirement inventory changed";
  require(Json.equal(arr(List.map(get "source")requirements))(get "requirements" expected))
    "A monitored hard requirement differs from its complete original";
  List.iter(fun row->require(text "status" row="pass" && get "nonvacuous" row=Json.Bool true &&
      at["histories";"pass"]row=get "histories" expected &&
      List.for_all(fun key->at["histories";key]row=Json.int 0)["fail";"unknown";"unsupported";"not_exercised"])
    "An original hard requirement was weakened or not exercised in a fixed-rise history")requirements;
  let context=get "context" report in
  require(List.map(get "id")(items "discharges" context)=items "context_discharges" expected)
    "Context changed its separately justified source discharges";
  let resource row=obj(List.map(fun key->key,get key row)["owner";"unit";"scope";"quantity"])in
  let resources rows=arr(List.sort(fun a b->String.compare(Canonical.encode a)(Canonical.encode b))
    (List.map resource rows))in
  require(Json.equal(resources(items "derived_demands" context))
    (resources(items "resource_demands" expected)))"Whole-domain resource minima differ from literal demand inventory";
  List.iter(fun(key,literal)->require(at["record_layout";key]context=get literal expected)
    ("Complete conditional record layout changed: "^key))
    ["maximum_tick","maximum_tick";"ordered_cause_slots","ordered_cause_slots"];
  require(List.length(items "nodes"(get "implementation" candidate))=15)
    "Fresh producer changed the supplied primitive inventory"
let status_name = function
  |P.Active->"active"|P.Completed->"completed"|P.Failed->"failed"|P.Timed_out->"timed_out"
  |P.Reset_invalidated->"encounter_reset"|P.End_invalidated->"encounter_ended"
let attempt_literal(value:P.attempt)=obj[
  "creation_ordinal",Json.int value.ordinal;"slot",Option.fold ~none:Json.Null ~some:str value.binding.slot;
  "target",str value.subject;"generation",Json.int value.binding.generation;
  "started_tick",Json.int value.started_tick;"deadline_tick",Json.int value.deadline_tick;
  "ended_tick",Option.fold ~none:Json.Null ~some:Json.int value.ended_tick;"status",str(status_name value.status)]
let evidence row=match text "status" row with
  |"valid"->F.Known(Json.boolean(get "value" row))|"missing"->F.Missing|"invalid"->F.Invalid
  |"conflicting"->F.Conflicting|_->failwith "Unsupported literal evidence class"
let lifecycle = function "keep"->F.Keep|"reset"->F.Reset|"end"->F.End|_->failwith "Unknown literal lifecycle"
let feedback_outcome = function "completed"->F.Completed|"failed"->F.Failed|_->failwith "Unknown literal feedback"
let select (domain:F.t) witness source=
  let matches(batch:F.input_batch)=
    let expected_lifecycle=List.map(fun(slot:F.encounter)->slot.identity,
      match List.find_opt(fun row->number "tick" row=batch.tick && text "slot" row=slot.identity)(items "lifecycle" witness)with
      |None->F.Keep|Some row->lifecycle(text "action" row))domain.F.encounters in
    let observations=List.filter(fun(row:F.observation_input)->row.available_tick=batch.tick)domain.fixed_observations @
      List.filter_map(fun row->if number "tick" row<>batch.tick then None else
        Some({F.slot=text "slot" row;observation="condition";available_tick=batch.tick;
          observed_tick=batch.tick;evidence=evidence row}:F.observation_input))(items "observations" witness)in
    let feedback=match List.find_opt(fun row->number "tick" row=batch.tick)(items "feedback" witness)with
      |None->[]|Some row->List.map(fun item->number "creation_ordinal" item,feedback_outcome(text "outcome" item))(items "rows" row)in
    batch.lifecycle=expected_lifecycle && batch.observations=observations &&
      List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=feedback in
  match List.filter matches(List.of_seq(S.choices source))with
  |[batch]->batch|_->failwith "Literal history is absent or ambiguous in the original causal grammar"
let event_kind = function
  |P.Primitive_event I.Completed->"completed"|P.Primitive_event I.Failed->"failed"
  |P.Primitive_event I.Timed_out->"timed_out"|P.Attempt_reset->"attempt_reset"
  |P.Attempt_ended->"attempt_ended"|P.Encounter_reset->"encounter_reset"
  |P.Encounter_ended->"encounter_ended"
  |_->failwith "Unexpected event at the simultaneous deadline"
let deadline_literals witness (frame:P.frame)=
  let ordinal identity=(List.find(fun(attempt:P.attempt)->attempt.attempt_id=identity)frame.attempts).ordinal in
  let events=List.map(fun(event:P.event)->obj[
    "kind",str(event_kind event.kind);"slot",Option.fold ~none:Json.Null ~some:str event.binding.slot;
    "generation",Json.int event.binding.generation;
    "creation_ordinal",Option.fold ~none:Json.Null ~some:(fun identity->Json.int(ordinal identity))event.attempt_id;
    "tick",Json.int event.tick;"microstep",Json.int event.microstep])frame.events in
  require(Json.equal(arr events)(get "deadline_events" witness))
    ("Lifecycle/feedback/timeout event order changed: "^text "id" witness);
  let actions=List.map(fun(action:P.action)->
    let kind,identity,attempt,reason=match action.detail with
      |P.Feedback_accepted(identity,attempt)->"feedback_accepted",identity,attempt,Json.Null
      |P.Feedback_rejected(identity,attempt,reason)->"feedback_rejected",identity,attempt,str reason
      |_->failwith "Unexpected action at the simultaneous deadline"in
    obj["kind",str kind;"id",str identity;"creation_ordinal",Json.int(ordinal attempt);
      "reason",reason;"microstep",Json.int action.microstep])frame.actions in
  require(Json.equal(arr actions)(get "deadline_actions" witness))
    ("A simultaneous input lost or reordered its disposition: "^text "id" witness);
  let slots=List.map(fun(slot:P.slot_snapshot)->obj[
    "slot",str slot.slot_id;"generation",Json.int slot.generation;"active",Json.Bool slot.active])frame.slots in
  require(Json.equal(arr slots)(get "deadline_slots" witness))
    "Same-tick feedback revived an ended or old-generation encounter";
  require(Json.equal(arr(List.map attempt_literal frame.attempts))(get "final_attempts" witness))
    "An attempt escaped its exact terminal deadline or lifecycle invalidation"
let run_history request candidate limits witness=
  let original=R.implementation_request(R.of_json request)in
  let behavior=O.behavior_of_json(get "behavior" candidate)in
  let admitted=A.admit ~request:original ~behavior in
  let bound=B.check ~admitted ~implementation:(I.of_json ~library:(Q.implementation_library original)
    (get "implementation" candidate)) ~proposed:(U.of_json(get "binding" candidate))in
  let environment=B.environment bound and runtime_limits=get "candidate" limits in
  let runtime=P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=number "max_work" runtime_limits;max_events=number "max_events" runtime_limits;
      max_attempts=number "max_attempts" runtime_limits;max_microsteps=number "max_microsteps" runtime_limits}in
  let domain=Q.operating_domain original in
  let source=S.create ~behavior ~domain ~bounds:(S.execution_bounds_of_json(get "source" limits))in
  let observations=ref[] and feedback=ref[] and final=ref None and deadline_seen=ref false in
  let rec loop source runtime correspondence=
    if not(S.finished source)then(
      let batch=select domain witness source in
      let input=T.input correspondence batch in
      let ids kind count=List.init count(fun index->"domain/"^kind^"/"^string_of_int batch.tick^"/"^string_of_int index)in
      let observation_ids=List.map(fun(row:P.observation)->row.observation_id)input.observations
      and feedback_ids=List.map(fun(row:P.feedback)->row.feedback_id)input.feedback in
      require(observation_ids=ids "observation"(List.length batch.observations) &&
        feedback_ids=ids "feedback"(List.length batch.feedback))"Timing adapter reordered input occurrences";
      observations:= !observations@observation_ids;feedback:= !feedback@feedback_ids;
      let all_ids= !observations@ !feedback in
      require(List.length(List.sort_uniq String.compare all_ids)=List.length all_ids)
        "Lifecycle/feedback shared a reused input occurrence identity";
      let next_runtime,frame=P.step runtime input in
      let advanced=match S.step source batch with S.Advanced value->value
        |S.Stopped value->failwith("Literal timing prefix stopped: "^value.diagnostic.code)in
      require(List.map(text "id")(items "observations" advanced.receipt.timeline)= !observations &&
        List.map(text "id")(items "feedback" advanced.receipt.timeline)= !feedback)
        "Timing source and candidate adapters disagree on full ordered inputs";
      require(List.length frame.creations=integer(List.nth(items "creations_by_tick" witness)batch.tick))
        "Simultaneous lifecycle/feedback lost or invented an attempt";
      List.iter(fun(attempt:P.attempt)->require(attempt.executor="cell-1" && attempt.product="fixture.product.alpha")
        "Terminal attempt lost executor/product identity")frame.attempts;
      let execution=match advanced.receipt.execution with Some value->value|None->failwith "No fresh source timing execution"in
      let compare candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
        ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate in
      if batch.tick=3 then(
        deadline_seen:=true;
        deadline_literals witness frame;
        (* Each literal has two terminal attempt events, plus reset/end events
           where relevant. Reordering must not preserve the source trace. *)
        require(List.length frame.events>=2)"Deadline event mutation was vacuous";
        rejects "reordered simultaneous events" "policy_trace_correspondence"
          (fun()->compare {frame with events=List.rev frame.events});
        (match frame.actions with
        |[]->()
        |_::rest->rejects "lost simultaneous feedback disposition" "policy_trace_correspondence"
            (fun()->compare {frame with actions=rest});
            if List.length frame.actions>1 then
              rejects "reordered simultaneous dispositions" "policy_trace_correspondence"
                (fun()->compare {frame with actions=List.rev frame.actions}));
        (* A completed/failed attempt cannot be relabeled as a timeout just
           because the supplied receipt has the same tick as its deadline. *)
        (match List.find_opt(fun(event:P.event)->match event.kind with
          |P.Primitive_event I.Completed|P.Primitive_event I.Failed->true|_->false)frame.events with
        |None->()
        |Some selected->let events=List.map(fun(event:P.event)->
            if event.event_id=selected.event_id then {event with kind=P.Primitive_event I.Timed_out}else event)frame.events in
            rejects "deadline feedback replaced by timeout" "policy_trace_correspondence"
              (fun()->compare {frame with events})));
      let correspondence=compare frame in
      List.iter(fun(attempt:P.attempt)->require(T.candidate_attempt_to_source correspondence attempt.attempt_id=
        "attempt/"^string_of_int attempt.ordinal)"Simultaneous outcomes mixed creation-time correlations")frame.attempts;
      final:=Some frame;
      loop advanced.next next_runtime correspondence)in
  loop source runtime(T.create bound);
  let frame=match !final with Some value->value|None->failwith "No inclusive timing frames"in
  require(!deadline_seen && frame.tick=6 &&
    Json.equal(arr(List.map attempt_literal frame.attempts))(get "final_attempts" witness))
    "Quiet suffix changed a completed, failed, timed-out or invalidated attempt";
  List.iter(fun(key,actual)->require(Json.equal(arr(List.map str actual))(get key witness))
    ("Independent input occurrence literal changed: "^key))
    ["observation_occurrence_ids",!observations;"feedback_occurrence_ids",!feedback]
let publication_literals request candidate limits expected report export=
  require(Json.equal(get "report" export)report)"Fresh timing export changed complete assessment";
  let artifact=get "artifact" export in
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  require(fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" &&
    text "sequence" expected="CCAUGGCUUAAGGAAAA")"Timing domain changed the exact original RNA";
  require(text "fasta_sha256" artifact=Canonical.sha256 fasta &&
    text "fasta_sha256" manifest=Canonical.sha256 fasta &&
    text "manifest_sha256" artifact=Canonical.sha256(Canonical.encode manifest))"Timing export lost exact paired-byte fingerprints";
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report)
    "Fresh timing export omitted complete original authority or evidence";
  require(Json.equal(arr(List.map(get "molecule")(items "members" manifest)))(get "molecules" expected))
    "Timing export lost original chemistry, product, coordinates or provenance";
  require(text "claim_scope" manifest="bounded_conditional_policy_to_exact_mrna" &&
    text "empirical" manifest="unassessed" && text "original_authority" manifest="retain_original_inputs_separately")
    "Timing export widened conditional acceptance"
let ()=
  require(Array.length Sys.argv=2)"Supply independently authored complete timing fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_material_timing_literals.v0.1")"Unknown timing witness schema";
  let cases=items "cases" fixture and limits=get "limits" fixture in
  require(List.map(text "id")cases=["simultaneous_deadline_lifecycle"])"Timing fixture case inventory changed";
  let case=List.hd cases in
  original_literals case;
  let request=get "request" case and expected=get "expected" case in
  require(at["implementation_request";"budgets";"max_work"]request=Json.int 100000000)
    "Timing witness raised the frozen complete-domain work ceiling";
  require(number "queue_records" expected=2*(2+1+2+2+5)+4*2+2 &&
    number "ordered_cause_slots" expected=34*7 && number "maximum_tick" expected=8)
    "Simultaneous inputs changed the independently counted complete record capacities";
  let domain=at["implementation_request";"operating_domain"]request in
  require(Json.equal(get "lifecycle_factors" domain)(arr[obj["slots",arr[str "e1"];
    "ticks",arr[Json.int 3];"actions",arr[str "keep";str "reset";str "end"]]]) &&
    Json.equal(get "feedback_factors" domain)(arr[obj["effect",str "response";"ticks",arr[Json.int 3];
      "attempt_selector",str "all_previously_created";"outcomes",arr[str "completed";str "failed"];
      "routes",arr[str "correlated"];"max_rows_per_attempt_tick",Json.int 1]]) &&
    get "observation_factors" domain=arr[])
    "Timing grammar discarded a simultaneous lifecycle/feedback branch";
  let compiled=run Producer.handle Protocol.Core "compile-policy-material"(obj["request",request;"limits",limits])in
  assessment_literals expected compiled;
  let candidate=get "candidate" compiled in
  let payload=obj["request",request;"candidate",candidate;"limits",limits]in
  require(text "request_fingerprint" compiled=Canonical.fingerprint request &&
    text "candidate_fingerprint" compiled=Canonical.fingerprint candidate &&
    text "invocation_fingerprint" compiled=Canonical.fingerprint payload &&
    text "report_fingerprint" compiled=Canonical.fingerprint(get "report" compiled))
    "Complete timing wrapper omitted an authority or evidence binding";
  let exports=List.map(fun(role,handler)->
    require(Json.equal compiled(run handler role "check-policy-material"payload))
      "Independent timing checker differs from generic production";
    require(Json.equal compiled(run handler role "replay-policy-material"(set "report" compiled payload)))
      "Full fresh timing replay changed original evidence";
    let exported=run handler role "export-policy-material"payload in
    publication_literals request candidate limits expected(get "report" compiled)exported;exported)
    [Protocol.Core,Producer.handle;Protocol.Verify,Service.handle]in
  require(Json.equal(List.hd exports)(List.nth exports 1))"Core and standalone Verify timing exports differ";
  let witnesses=items "trace_witnesses" expected in
  let identities=List.concat_map(fun lifecycle->List.concat_map(fun first->
    List.map(fun second->lifecycle^"_"^first^"_"^second)["silence";"completed";"failed"])
      ["silence";"completed";"failed"])["keep";"reset";"end"]in
  require(List.map(text "id")witnesses=identities && List.length witnesses=27)
    "Timing literals omitted an independently enumerated Cartesian history";
  List.iter(run_history request candidate limits)witnesses;
  Printf.printf "policy material simultaneous lifecycle/feedback/deadline, complete27-domain and ordered input/event literals passed (%d checks)\n" !checks
