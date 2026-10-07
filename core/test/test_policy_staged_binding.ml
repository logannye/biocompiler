open Bioc_wire
open Bioc_policy_staged_test_support.Literals
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module R = Bioc_domain.Policy_realization_request
module U = Bioc_domain.Policy_implementation_binding
module A = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module S = Bioc_semantics.Policy_domain_reference
module P = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
let () = Printexc.register_printer(function
  | Diagnostic.Error d -> Some(Printf.sprintf "Diagnostic.Error(%s, %s, %s)" d.code
      (Option.value ~default:"<none>" d.path) d.message)
  | _ -> None)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let controls=ref 0
let rejects label code action=incr controls;match action()with
  |_->failwith("Staged adversary accepted: "^label)
  |exception Diagnostic.Error d->require(d.code=code)(label^": unexpected diagnostic "^d.code)
let transitions=["regimen/start","start";"regimen/handoff","handoff";"regimen/completed","finish";
  "regimen/first_failed","first_fail";"regimen/second_failed","second_fail";
  "regimen/first_timed_out","first_timeout";"regimen/second_timed_out","second_timeout"]
let source_id="regimen/stages"

(* This oracle uses the separately handwritten primitive graph. Neither an
   implementation producer nor its output determines the graph, source map,
   anchors, primitive configurations, or expected stage/attempt observations. *)
let original_graph ()=
  let library,graph=fixture()in
  let library,graph=reconfigure library graph "evidence"(o["freshness_ticks",Json.int 10])in
  let library,graph=reconfigure library graph "product"(o["product",s "fixture.product.alpha"])in
  let configuration=o["capacity",Json.int 4;"timeout_ticks",Json.int 2;
    "authorization",s "continuous";"on_loss",s "continue";"on_unknown",s "defer"]in
  let library,graph=reconfigure library graph "first" configuration in
  let library,graph=reconfigure library graph "second" configuration in
  let graph=graph|>rewire "start_gate" "guard"(endpoint "evidence" "value")
    |>rewire "first" "authorization"(endpoint "evidence" "value")in
  library,graph
let authority request=o[
  "source_artifact_digest",s(D.artifact_digest(R.document request));
  "descriptors_digest",s(O.descriptors_digest(R.definitions request));
  "domain_digest",s(F.digest(R.operating_domain request));
  "implementation_catalog_digest",s(Canonical.fingerprint(get "implementations"(D.to_json(R.document request))));
  "library_digest",s(I.library_digest(R.implementation_library request))]
let occurrences request=
  let declarations=D.declarations(R.document request)in
  let declaration id=List.find(fun(d:D.declaration)->d.id=id)declarations in
  let path id=(declaration id).path in
  let occurrence ?(disposition="executable") role source_path targets=o[
    "source_path",s source_path;"role",s role;"disposition",s disposition;"targets",a targets]in
  let expr ?(constant=false) path target=occurrence ~disposition:(if constant then "constant"else "executable")
    "predicate" path [target]in
  let rec requirement path value=match value with
    |Json.Object fields->
        (if List.assoc_opt "$type" fields=Some(s "Expr")then
          [occurrence ~disposition:"obligation" "requirement" path []]else [])@
        List.concat_map(fun(key,value)->requirement(path^"/"^key)value)fields
    |Json.Array values->List.concat(List.mapi(fun index value->requirement(path^"/"^string_of_int index)value)values)
    |_->[]in
  let metadata=List.concat_map(fun(d:D.declaration)->match d.kind with
    |D.Role|D.Subject|D.Encounter->[occurrence ~disposition:"retained_metadata" "declaration" d.path []]
    |D.Clock->[occurrence ~disposition:"retained_metadata" "clock" d.path []]
    |D.Requirement->occurrence ~disposition:"obligation" "requirement" d.path []::requirement d.path d.value
    |_->[])declarations in
  let source_events=["start","edge","events";"handoff","first_completed","selected";
    "finish","second_completed","selected";"first_fail","first_failed","selected";
    "second_fail","second_failed","selected";"first_timeout","first_timed_out","selected";
    "second_timeout","second_timed_out","selected"]in
  let mapped=List.concat(List.mapi(fun lane(id,node)->
    let _,event,port=List.find(fun(name,_,_)->name=node)source_events in
    let commit_outputs=(if node="start" || node="handoff"then[endpoint(node^"_commit")"request0"]else [])@
      [endpoint(node^"_commit")"machine_write"]in
    [occurrence "declaration"(path id)([endpoint(node^"_gate")"candidate";endpoint "arbiter"("out"^string_of_int lane)]@commit_outputs);
     expr(path id^"/on")(endpoint event port);
     expr ~constant:(node<>"start")(path id^"/when")(if node="start"then endpoint "evidence" "value"else endpoint "true" "out")]@
    (if node="start"then[expr(path id^"/on/args/0")(endpoint "evidence" "value")]else []))transitions)in
  let effects=List.concat_map(fun(id,bank)->
    [occurrence "lifecycle"(path id)[endpoint bank "events";endpoint bank "snapshot"];
     occurrence "lifecycle"(path id^"/lifecycle")[endpoint bank "events";endpoint bank "snapshot"];
     occurrence ~disposition:"constant" "effect_parameter"(path id^"/parameters/0/value")[endpoint "product" "out"]])
    ["stage_one","first";"stage_two","second"]in
  a(List.sort(fun first second->String.compare(text "source_path" first)(text "source_path" second))(metadata@mapped@effects@[
    occurrence "declaration"(path "condition")[endpoint "evidence" "value";endpoint "evidence" "updated"];
    occurrence "declaration"(path source_id)[endpoint "machine" "snapshot"];
    occurrence "declaration"(path source_id^"/arbitration")(List.init 7(fun index->endpoint "arbiter"("out"^string_of_int index)));
    occurrence ~disposition:"constant" "effect_parameter"(path "product")[endpoint "product" "out"]]))
let proposed request=o[
  "schema_version",s U.staged_schema_version;"profile",s U.staged_profile;
  "catalog_entry",s((List.hd(R.catalog_bindings request)).entry_id);
  "observations",a[o["source",s "condition";"bank",s "evidence";"input",s "condition"]];
  "states",a[];"rules",a[];
  "effects",a(List.map(fun(source,bank)->o["source",s source;"bank",s bank;"feedback",s(bank^"_feedback")])
    ["stage_one","first";"stage_two","second"]);
  "machines",a[o["source",s source_id;"bank",s "machine"]];
  "transitions",a(List.mapi(fun lane(source,node)->o["source",s source;"gate",s(node^"_gate");
    "arbiter",s "arbiter";"lane",Json.int lane;"commit",s(node^"_commit")])transitions)]
let prepare raw (library,graph)=
  let raw=raw|>replace "implementation_library" library
    |>replace "catalog_bindings"(a(List.map(fun bridge->replace "models"
      (a(List.map(get "identity")(rows "models" library)))bridge)(rows "catalog_bindings" raw)))in
  let request=R.of_json raw in
  let behavior=Bioc_compiler.Policy_lowering.lower
    (Bioc_checker.Policy_admission.admit ~document:(R.document request) ~descriptors:(R.definitions request))in
  let admitted=A.admit ~request ~behavior in
  let graph=graph|>replace "authority"(authority request)|>replace "occurrences"(occurrences request)in
  admitted,I.of_json ~library:(R.implementation_library request)graph,U.of_json(proposed request)
let bind raw original=let admitted,implementation,proposed=prepare raw original in
  B.check ~admitted ~implementation ~proposed
let static_controls raw original=
  let admitted,implementation,proposal=prepare raw original in
  let graph=I.to_json implementation and library=I.library_to_json(R.implementation_library(A.request admitted))in
  let semantic label (library,graph)=
    let admitted,implementation,proposed=prepare raw(library,graph)in
    rejects label "policy_implementation_source_binding"(fun()->B.check ~admitted ~implementation ~proposed)in
  semantic "start ignores observation"(library,rewire "start_gate" "guard"(endpoint "true" "out")graph);
  semantic "handoff listens to stage two"(library,rewire "handoff_gate" "on"(endpoint "second_completed" "selected")graph);
  semantic "stage-one feedback drives both banks"(library,rewire "second_completed" "events"(endpoint "first" "events")graph);
  semantic "first-stage destination skipped"(reconfigure library graph "start_commit"
    (o["destination",s "second";"writes",Json.int 0;"requests",Json.int 1]));
  semantic "retained-attempt correlation removed"(reconfigure library graph "handoff_gate"
    (o["source",s "first";"correlation",s "unbound"]));
  semantic "machine starts past first effect"(reconfigure library graph "machine"
    (o["states",a(List.map s["ready";"first";"second";"completed";"failed"]);"initial",s "second";
      "terminal",a[s "completed";s "failed"];"writers",Json.int 7;"retained_capacity",Json.int 1]));
  semantic "one effect changes product"(reconfigure library graph "product"(o["product",s "fixture.product.other"]));
  let malformed label proposed=let proposed=U.of_json proposed in
    rejects label "policy_implementation_source_binding"(fun()->B.check ~admitted ~implementation ~proposed)in
  malformed "missing transition"(replace "transitions"(a(List.tl(rows "transitions"(U.to_json proposal))))(U.to_json proposal));
  malformed "lane permutation"(replace "transitions"(a(List.rev(rows "transitions"(U.to_json proposal))))(U.to_json proposal));
  malformed "effects swapped"(replace "effects"(a(List.rev(rows "effects"(U.to_json proposal))))(U.to_json proposal));
  let graph=replace "occurrences"(a(List.map(fun row->if text "source_path" row=(List.find(fun(d:D.declaration)->d.id=source_id)
    (D.declarations(R.document(A.request admitted)))).path then replace "role"(s "predicate")row else row)(rows "occurrences" graph)))graph in
  let altered=I.of_json ~library:(R.implementation_library(A.request admitted))graph in
  rejects "machine declaration erased" "policy_implementation_source_binding"
    (fun()->B.check ~admitted ~implementation:altered ~proposed:proposal)

let bounds=S.execution_bounds_of_json(o(List.map(fun(k,v)->k,Json.int v)
  ["max_ticks",50;"max_inputs",1000;"max_encounters",4;"max_attempts",32;
   "max_work",8_000_000;"max_trace_items",100000;"max_microsteps",30]))
let initialize bound=
  let admitted=B.admitted_inputs bound and environment=B.environment bound in
  S.create ~behavior:(A.behavior admitted) ~domain:(R.operating_domain(A.request admitted)) ~bounds,
  P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=20_000_000;max_events=200000;max_attempts=32;max_microsteps=30},T.create bound
let select source predicate=
  let rec scan sequence=match sequence()with Seq.Nil->failwith "Declared independent domain lacks witness branch"
    |Seq.Cons(value,rest)->if predicate value then value else scan rest in scan(S.choices source)
let attempts (advanced:S.advanced)=rows "attempts"(Option.get advanced.receipt.execution)
let compare correspondence batch (advanced:S.advanced) candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
  ~source_attempts:(attempts advanced) ~source_creations:advanced.creations ~candidate
let execute source runtime correspondence batch=
  let runtime,frame=P.step runtime(T.input correspondence batch)in
  let advanced=match S.step source batch with S.Advanced value->value
    |S.Stopped result->failwith("Source witness stopped: "^result.diagnostic.code)in
  advanced.next,runtime,compare correspondence batch advanced frame,advanced,frame
let trace_controls correspondence batch advanced (frame:P.frame)=
  let reject label frame=rejects label "policy_trace_correspondence"(fun()->compare correspondence batch advanced frame)in
  reject "machine snapshots omitted"{frame with machines=[]};
  reject "machine outputs omitted"{frame with outputs=List.filter(fun(p:P.port_value)->match p.signal with P.Machine _->false|_->true)frame.outputs};
  let change_machine label edit=
    let first=List.hd frame.machines in
    let altered=edit first in
    reject label {frame with machines=altered::List.tl frame.machines;
      outputs=List.map(fun(p:P.port_value)->match p.signal with P.Machine value when value=first->
        {p with signal=P.Machine altered}|_->p)frame.outputs}in
  change_machine "state label changes despite consistent output"(fun(value:P.machine_snapshot)->{value with state="ready"});
  change_machine "retained attempt is erased"(fun(value:P.machine_snapshot)->{value with retained_attempts=[]});
  change_machine "cross-encounter retained attempt"(fun(value:P.machine_snapshot)->
    {value with retained_attempts=(List.nth frame.machines 1).retained_attempts});
  reject "machine action omitted"{frame with actions=List.filter(fun(action:P.action)->match action.detail with
    P.Machine_transition _->false|_->true)frame.actions};
  reject "machine action invents completion"{frame with actions=List.map(fun(action:P.action)->match action.detail with
    P.Machine_transition value->{action with detail=P.Machine_transition{value with destination="completed"}}|_->action)frame.actions};
  reject "attempt ownership erased"{frame with attempts=List.map(fun(value:P.attempt)->{value with machine=None})frame.attempts};
  reject "creation ownership erased"{frame with creations=List.map(fun(value:P.attempt)->{value with machine=None})frame.creations};
  reject "old execution profile"{frame with execution_profile=P.profile}

type scenario = Silent | Complete | First_failed | Second_failed | Mixed | Reset_end
let feedback scenario tick=match scenario,tick with
  |(Complete|Second_failed),2->["attempt/1",F.Completed;"attempt/2",F.Completed]
  |(First_failed),2->["attempt/1",F.Failed;"attempt/2",F.Failed]
  |Mixed,2->["attempt/1",F.Completed;"attempt/2",F.Failed]
  |Reset_end,2->["attempt/1",F.Completed;"attempt/2",F.Completed]
  |Complete,3->["attempt/3",F.Completed;"attempt/4",F.Completed]
  |Second_failed,3->["attempt/3",F.Failed;"attempt/4",F.Failed]
  |_->[]
let literal_state scenario tick slot=
  if tick=0 then Some(0,"ready",[])else if tick=1 then Some(0,"first",[if slot="e1"then 1 else 2])else
  match scenario with
  |Reset_end->if slot="e2"then None else if tick=2 then Some(1,"ready",[])
      else if tick<5 then Some(1,"first",[3])else Some(1,"failed",[])
  |First_failed->Some(0,"failed",[])
  |Silent->if tick=2 then Some(0,"first",[if slot="e1"then 1 else 2])else Some(0,"failed",[])
  |Mixed->if slot="e2"then Some(0,"failed",[])else if tick<4 then Some(0,"second",[3])else Some(0,"failed",[])
  |Complete|Second_failed->if tick=2 then Some(0,"second",[if slot="e1"then 3 else 4])
      else Some(0,(if scenario=Complete then "completed"else "failed"),[])
let assert_literal scenario(frame:P.frame)=
  List.iter(fun slot->
    let actual=List.find_opt(fun(value:P.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
    match literal_state scenario frame.tick slot,actual with
    |None,None->()
    |Some(generation,state,retained),Some actual->
        require(actual.binding.generation=generation && actual.state=state &&
          actual.retained_attempts=List.map(fun id->"primitive/attempt/"^string_of_int id)retained)
          ("Literal stage/lineage differs at tick "^string_of_int frame.tick^" in "^slot)
    |_->failwith("Literal encounter lifetime differs in "^slot))["e1";"e2"]
let run bound scenario mutations=
  let source,runtime,correspondence=initialize bound in
  let rec loop source runtime correspondence=
    if S.finished source then correspondence else
    let batch=select source(fun(batch:F.input_batch)->
      List.map(fun(row:F.feedback_input)->row.attempt.source_attempt_id,row.outcome)batch.feedback=feedback scenario batch.tick &&
      (if scenario=Reset_end && batch.tick=2 then batch.lifecycle=["e1",F.Reset;"e2",F.End]
       else List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle))in
    let next,runtime,next_correspondence,advanced,frame=execute source runtime correspondence batch in
    assert_literal scenario frame;
    if mutations && batch.tick=1 then trace_controls correspondence batch advanced frame;
    if scenario=Reset_end && batch.tick=2 then(
      require(List.length frame.attempts=2 && List.map(fun(value:P.attempt)->value.status)frame.attempts=
        [P.Reset_invalidated;P.End_invalidated])"Reset/end erased historical attempt dispositions";
      require(List.length(List.filter(fun(action:P.action)->match action.detail with P.Feedback_rejected _->true|_->false)frame.actions)=2)
        "Prior-generation completion feedback was discarded or rebound");
    if scenario=Reset_end && batch.tick=3 then(
      let actual=List.hd frame.machines in
      let stale={actual with retained_attempts=["primitive/attempt/1"]}in
      let altered={frame with machines=[stale];outputs=List.map(fun(value:P.port_value)->match value.signal with
        P.Machine snapshot when snapshot=actual->{value with signal=P.Machine stale}|_->value)frame.outputs}in
      rejects "old generation retained as new stage" "policy_trace_correspondence"
        (fun()->compare correspondence batch advanced altered));
    loop next runtime next_correspondence in
  let matched=loop source runtime correspondence in
  require(text "profile"(T.report matched)=T.staged_profile && text "claim"(T.report matched)="matched_prefix_only")
    "Staged trace report broadened its profile or bounded claim"
let reset_request raw=
  let domain=get "operating_domain" raw in
  let observation tick value=o["available_tick",Json.int tick;"observation",s "condition";"observed_tick",Json.int tick;
    "slot",s "e1";"status",s "valid";"value",Json.Bool value]in
  replace "operating_domain"(domain|>replace "lifecycle_factors"(a[o["actions",a(List.map s["keep";"reset";"end"]);
    "slots",a[s "e1";s "e2"];"ticks",a[Json.int 2]]])
    |>replace "fixed_observations"(a(rows "fixed_observations" domain@[observation 2 false;observation 3 true])))raw

let ()=
  let raw=read Sys.argv.(1)in
  let original=original_graph()in
  let bound=bind raw original in
  require(text "profile"(B.report bound)=U.staged_profile && B.rules bound=[] &&
    List.length(B.machines bound)=1 && List.length(B.transitions bound)=7 && List.length(B.activations bound)=7)
    "Staged source ownership was erased into legacy rule semantics";
  static_controls raw original;
  List.iter(fun scenario->run bound scenario(scenario=Silent))[Silent;Complete;First_failed;Second_failed;Mixed];
  run(bind(reset_request raw)original)Reset_end false;
  Printf.printf "Independent staged binding and trace controls passed; %d explicit rejection controls.\n" !controls
