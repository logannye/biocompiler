open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module X = Bioc_domain.Policy_component_context
module A = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module S = Bioc_semantics.Policy_domain_reference
module P = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let () = Printexc.register_printer(function
  | Diagnostic.Error d -> Some(Printf.sprintf "Diagnostic.Error(%s, %s, %s)" d.code
      (Option.value ~default:"<none>" d.path) d.message)
  | _ -> None)
let s value=Json.String value
let o values=Json.Object values
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="finite-machine-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Finite-machine adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let rejected_material label operation payload=
  let request:Protocol.request={request_id="finite-machine-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Ok,Some result,[] when at["report";"status"]result=s "not_accepted" && get "artifact" result=Json.Null->incr controls
  |Protocol.Ok,_,_->failwith("Finite-machine material mutant accepted: "^label)
  |_,None,(_::_)->incr controls
  |_->failwith("Malformed finite-machine rejection: "^label)
  |exception Diagnostic.Error _->incr controls

let bind raw candidate=
  let request=R.of_finite_machine_json raw in
  let behavior=O.behavior_of_json(get "behavior" candidate)in
  let admitted=A.admit ~request ~behavior in
  let implementation=I.of_json ~library:(R.implementation_library request)(get "implementation" candidate)
  and proposed=U.of_json(get "binding" candidate)in
  B.check ~admitted ~implementation ~proposed

(* Mutate a valid supplied model and freshly pin every corresponding original
   library/bridge/graph reference. Rejection must come from actual source/graph
   semantics, not merely a stale model digest or missing catalog membership. *)
let changed_model raw candidate node_id change=
  let graph=get "implementation" candidate and library=get "implementation_library" raw in
  let actual=List.find(fun node->text "id" node=node_id)(rows "nodes" graph)in
  let old=get "model" actual in
  let original=List.find(fun model->Json.equal(get "identity" model)old)(rows "models" library)in
  let body=edit["configuration"]change(get "body" original)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" original)in
  let model=original|>set "body" body|>set "identity" identity
    |>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))in
  let library=set "models"(a(List.map(fun value->if Json.equal(get "identity" value)old then model else value)(rows "models" library)))library in
  let raw=raw|>set "implementation_library" library
    |>edit["catalog_bindings"](fun value->a(List.map(fun bridge->edit["models"]
      (fun pins->a(List.map(fun pin->if Json.equal pin old then identity else pin)(Json.array pins)))bridge)(Json.array value)))in
  let graph=graph|>edit["authority";"library_digest"](fun _->s(Canonical.fingerprint library))
    |>edit["nodes"](fun value->a(List.map(fun node->if Json.equal(get "model" node)old then
      node|>set "model" identity|>set "configuration_digest"(get "configuration_digest" model)else node)(Json.array value)))in
  raw,set "implementation" graph candidate

let static_controls raw candidate=
  let change_binding label change=rejects label(fun()->bind raw(edit["binding"]change candidate))in
  change_binding "lane"(edit["transitions"](fun value->a(List.mapi(fun index row->
    if index=0 then set "lane"(Json.int 1)row else row)(Json.array value))));
  change_binding "missing transition"(edit["transitions"](fun value->a(List.tl(Json.array value))));
  change_binding "profile downgrade"(fun value->value|>set "schema_version"(s U.staged_schema_version)|>set "profile"(s U.staged_profile));
  let anchors=rows "transitions"(get "binding" candidate)in
  let complete=List.find(fun row->text "source" row="complete")anchors in
  let changed label node change=let raw,candidate=changed_model raw candidate node change in
    rejects label(fun()->bind raw candidate)in
  changed "retained correlation removed"(text "gate" complete)(set "correlation"(s "unbound"));
  changed "completion returns to ready"(text "commit" complete)(set "destination"(s "ready"));
  let machine=List.hd(rows "machines"(get "binding" candidate))in
  changed "machine initial state differs"(text "bank" machine)(fun config->
    set "initial"(List.nth(rows "states" config)1)config);
  rejects "original topology changed"(fun()->bind
    (edit["document";"program";"declarations"](fun value->a(List.map(fun row->
      if text "$type" row="Transition" && text "id" row="complete" then set "destination"(s "ready")row else row)(Json.array value)))raw)candidate);
  rejects "legacy decoder accepts finite authority"(fun()->R.of_json raw);
  let observation=List.hd(rows "observations"(get "binding" candidate))in
  let launch=List.find(fun row->text "source" row="launch")anchors in
  let source=List.find(fun row->text "id" row="launch")(rows "declarations"(at["document";"program"]raw))in
  if at["on";"op"]source=s "updated" then
    rejects "updated listens to selected effect"(fun()->bind raw(edit["implementation";"wires"](fun value->a(List.map(fun wire->
      if at["consumer";"node"]wire=get "gate" launch && at["consumer";"port"]wire=s "on" then
        set "producer"(o["node",get "bank" observation;"port",s "value"])wire else wire)(Json.array value)))candidate))

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
  let rec scan count sequence=
    require(count<100000)"Literal witness selection exceeded its own search bound";
    match sequence()with Seq.Nil->failwith "Original finite domain lacks the handwritten witness"
    |Seq.Cons(value,rest)->if predicate value then value else scan(count+1)rest in scan 0(S.choices source)
let feedback scenario tick=match scenario,tick with
  |"retry_cycle",2->["attempt/1",F.Failed;"attempt/2",F.Failed]
  |"retry_cycle",4->List.map(fun n->"attempt/"^string_of_int n,F.Completed)[1;2;3;4]
  |("guarded_branch"|"branch_unknown"),2->["attempt/1",F.Completed;"attempt/2",F.Completed]
  |("guarded_branch"|"branch_unknown"),3->["attempt/3",F.Completed]
  |"updated_fork",3->["attempt/1",F.Completed;"attempt/2",F.Completed]
  |_->[]
let expected_machine scenario tick slot=
  let ordinal=if slot="e1"then 1 else 2 in
  match scenario with
  |"retry_cycle"->if tick=0 then "ready",[] else if tick=1 then "active",[ordinal]
      else if tick=2 then "ready",[ordinal] else if tick=3 then "active",[ordinal+2]else "done",[]
  |"updated_fork"->if tick<2 then "ready",[] else if tick=2 then "active",[ordinal]else "success",[]
  |"guarded_branch"|"branch_unknown"->if tick=0 then "ready",[] else if tick=1 then "deciding",[ordinal]
      else if slot="e1" then(if scenario="branch_unknown"then "deciding",[1]else "rejected",[])
      else if tick=2 then "accepted",[3]else "done",[]
  |_->failwith "Unknown literal finite-machine scenario"
let compare_frame correspondence batch (advanced:S.advanced) candidate=
  let attempts=rows "attempts"(Option.get advanced.receipt.execution)in
  T.advance correspondence ~batch ~source_frame:advanced.frame ~source_attempts:attempts
    ~source_creations:advanced.creations ~candidate
let selected_trace bound scenario=
  let source,runtime,correspondence=initialize bound in
  let rec loop source runtime correspondence=
    if S.finished source then correspondence else
    let batch=select source(fun(batch:F.input_batch)->
      List.sort compare(List.map(fun(row:F.feedback_input)->row.attempt.source_attempt_id,row.outcome)batch.feedback)=
        List.sort compare(feedback scenario batch.tick) &&
      List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle &&
      (if List.mem scenario["guarded_branch";"branch_unknown"] && batch.tick=2 then
        List.exists(fun(row:F.observation_input)->row.slot="e1" &&
          row.evidence=(if scenario="branch_unknown"then F.Missing else F.Known false))batch.observations else true))in
    let runtime,frame=P.step runtime(T.input correspondence batch)in
    let advanced=match S.step source batch with S.Advanced value->value
      |S.Stopped stopped->failwith("Literal source prefix stopped: "^stopped.diagnostic.code)in
    let matched=compare_frame correspondence batch advanced frame in
    List.iter(fun slot->
      let state,retained=expected_machine scenario frame.tick slot in
      let machine=List.find(fun(value:P.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
      require(machine.state=state && machine.binding.generation=0 &&
        machine.retained_attempts=List.map(fun n->"primitive/attempt/"^string_of_int n)retained)
        (scenario^": literal candidate state/correlation differs at tick "^string_of_int frame.tick^"/"^slot);
      let machine=List.find(fun row->at["binding";"encounter"]row=s slot)(rows "machines" advanced.frame)in
      require(get "state" machine=s state && get "attempts" machine=a(List.map(fun n->s("attempt/"^string_of_int n))retained))
        (scenario^": literal source state/correlation differs"))["e1";"e2"];
    if scenario="retry_cycle" && frame.tick=4 then
      require(List.length(List.filter(fun(action:P.action)->match action.detail with
        P.Feedback_rejected _->true|_->false)frame.actions)=2)"Old retry feedback did not remain rejected";
    if scenario="updated_fork" && frame.tick=1 then (
      require(frame.creations=[] && frame.attempts=[])"Unknown observation update started an effect";
      require(List.length(List.filter(fun(event:P.event)->event.kind=P.Primitive_event I.Updated)frame.events)=2)
        "Unknown samples lost their explicit observation-update events");
    if (scenario="retry_cycle" && frame.tick=3) || (scenario="updated_fork" && frame.tick=2) then (
      let first=List.hd frame.machines in
      let altered={first with retained_attempts=[]}in
      let mutate replacement={frame with machines=replacement::List.tl frame.machines;
        outputs=List.map(fun(value:P.port_value)->match value.signal with
          P.Machine machine when machine=first->{value with signal=P.Machine replacement}|_->value)frame.outputs}in
      rejects "trace retained identity erased"(fun()->compare_frame correspondence batch advanced(mutate altered));
      if scenario="retry_cycle"then
        rejects "trace retained stale retry identity"(fun()->compare_frame correspondence batch advanced
          (mutate{first with retained_attempts=["primitive/attempt/1"]})));
    loop advanced.next runtime matched in
  let matched=loop source runtime correspondence in
  require(text "claim"(T.report matched)="matched_prefix_only")"Finite trace broadened its claim"

let case limits row=
  let name=text "id" row and request=get "request" row and expected=get "expected" row in
  let original=M.of_json request in
  require(M.is_finite_machine original && M.requires_prerequisite_closure original)
    "Finite material family lost prerequisite closure";
  require(Json.equal(X.ordered_union_json(M.composition_rule original))(get "ordered_union" expected))
    "Independent supplied ordered union changed";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"(o["request",request;"limits",limits])in
  require(at["report";"status"]produced=s "checked_component_material" && get "artifact" produced=Json.Null)
    (name^": complete finite material conjunction was not checked with export withheld");
  let candidate=get "candidate" produced in
  let graph=get "implementation" candidate and binding=get "binding" candidate in
  require(get "schema_version" binding=s U.finite_machine_schema_version && get "profile" binding=s U.finite_machine_profile)
    "Producer used the legacy staged binding profile";
  List.iter(fun(field,expected_field)->require(Json.int(List.length(rows field graph))=get expected_field expected)
    (name^": source-independent declared graph census differs"))["nodes","node_count";"wires","wire_count"];
  require(Json.int(List.length(rows "transitions" binding))=get "transition_count" expected &&
    Json.int(List.length(rows "effects" binding))=get "effect_count" expected)"Source binding census differs";
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let fresh=call Service.handle Protocol.Verify "check-policy-component-material" invocation in
  require(Json.equal produced fresh)"Producer and independent fresh material results differ";
  require(Json.equal fresh(call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",fresh])))"Fresh replay changed finite evidence";
  let report=get "report" fresh in
  require(at["preservation";"coverage";"complete"]report=Json.Bool true &&
    get "all_original_obligations_discharged" report=Json.Bool true && get "empirical" report=s "unassessed")
    "Finite complete-domain/context/prerequisite conjunction or empirical boundary changed";
  require(List.for_all(fun value->get "status" value=s "pass" && get "nonvacuous" value=Json.Bool true)
    (rows "requirements"(get "preservation" report)))"Original finite requirements are missing or unproved";
  let obligation=List.find(fun value->get "obligation" value=s "machine_reachability_termination_and_progress")(rows "obligations" report)in
  require(at["evidence";"universal_termination"]obligation=s "not_claimed")"Retry cycles acquired universal termination claims";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  require(Json.equal exported(call Producer.handle Protocol.Core "export-policy-component-material" invocation))
    "Core and Verify paired finite exports differ";
  let artifact=get "artifact" exported and molecule=get "molecule" expected in
  require(at["construction";"inventory";"molecules"]candidate=a[molecule] && get "sequence" molecule=get "sequence" expected)
    "Finite material differs from independently retained exact RNA authority";
  let sequence=text "sequence" expected in
  let fasta=">rna_0001 alphabet=RNA\n"^sequence^"\n"in
  require(get "fasta" artifact=s fasta && get "fasta_sha256" artifact=s(Canonical.sha256 fasta))"Exact finite FASTA differs";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))"Finite manifest lost full fresh authority";
  let raw=get "implementation_request" request in
  let bound=bind raw candidate in
  let behavior=A.behavior(B.admitted_inputs bound)in
  let machine=List.hd behavior.O.machines in
  require(Json.int(List.length machine.states)=get "state_count" expected)
    "Original state alphabet census differs";
  static_controls raw candidate;
  selected_trace bound name;
  if name="guarded_branch"then selected_trace bound "branch_unknown";
  if name="retry_cycle"then (
    let entry=List.hd(rows "implementations"(at["implementation_request";"document";"implementations"]request))in
    let entry=set "dependencies"(a[])entry in
    let empty=request
      |>edit["implementation_request";"document";"implementations";"implementations"](fun _->a[entry])
      |>edit["implementation_request";"catalog_bindings"](fun values->a(List.map
        (set "entry_digest"(s(Canonical.fingerprint entry)))(Json.array values)))
      |>edit["catalog_binding";"entry_digest"](fun _->s(Canonical.fingerprint entry))in
    rejects "empty original prerequisite inventory"(fun()->
      let original=M.of_json empty in
      Bioc_domain.Policy_provider_prerequisites.pending_dependencies(M.implementation_request original));
    rejected_material "exact RNA mutation" "check-policy-component-material"
      (edit["candidate";"construction";"inventory";"molecules"](fun value->a(List.map(fun molecule->
        set "sequence"(s("A"^String.sub sequence 1(String.length sequence-1)))molecule)(Json.array value)))invocation);
    rejected_material "incomplete exploration" "check-policy-component-material"
      (edit["limits";"max_step_work"](fun _->Json.int 1)invocation);
    rejected_material "forged replay coverage" "replay-policy-component-material"
      (o["request",request;"candidate",candidate;"limits",limits;
          "report",edit["report";"preservation";"coverage";"histories"](fun _->Json.int 0)fresh]));
  Printf.printf "finite_machine: %s exact source/graph/component/RNA and selected literal prefixes\n%!" name

let ()=
  require(Array.length Sys.argv=2)"Expected independent finite-machine fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_finite_machine_literals.v0.1")"Wrong finite fixture profile";
  require(List.map(text "id")(rows "cases" fixture)=["retry_cycle";"guarded_branch";"updated_fork"])
    "Finite topology fixture census changed";
  List.iter(case(get "limits" fixture))(rows "cases" fixture);
  require(!controls>=30)"Finite semantic rejection control census incomplete";
  Printf.printf "finite_machine: three supplied topologies, four handwritten source/candidate traces, %d rejections\n" !controls
