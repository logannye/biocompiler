open Bioc_wire
module R=Bioc_domain.Policy_realization_request
module M=Bioc_domain.Policy_component_material_request
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module O=Bioc_domain.Policy_operational
module F=Bioc_domain.Policy_operating_domain
module A=Bioc_checker.Policy_realization_admission
module B=Bioc_checker.Policy_implementation_binding_check
module Source=Bioc_checker.Policy_check
module S=Bioc_semantics.Policy_domain_reference
module P=Bioc_candidate_runtime.Policy_primitives
module T=Bioc_realization_checker.Policy_trace_correspondence
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
let ()=Printexc.register_printer(function Diagnostic.Error d->
  Some(Printf.sprintf "Diagnostic.Error(%s, %s, %s)" d.code(Option.value ~default:"<none>" d.path)d.message)|_->None)
let s value=Json.String value
let a values=Json.Array values
let o values=Json.Object values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key replacement value=o(List.map(fun(name,value)->name,if name=key then replacement else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="network-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects ?code label action=match action()with
  |_->failwith("Network adversary accepted: "^label)
  |exception Diagnostic.Error error->
    Option.iter(fun expected->require(error.code=expected)(label^": wrong diagnostic "^error.code))code;incr controls
let rec contains_string expected=function
  |Json.String value->value=expected|Json.Array values->List.exists(contains_string expected)values
  |Json.Object fields->List.exists(fun(_,value)->contains_string expected value)fields|_->false
let bind raw candidate=
  let request=R.of_network_json raw in
  let behavior=O.behavior_of_json(get "behavior" candidate)in
  let admitted=A.admit ~request ~behavior in
  B.check ~admitted ~implementation:(I.of_json ~library:(R.implementation_library request)(get "implementation" candidate))
    ~proposed:(U.of_json(get "binding" candidate))
let admit_source raw=
  let request=R.of_network_json raw in
  require(get "status"(Source.check(R.document request))=s "valid")"Network semantic mutant is not independently source-valid";
  let source=Bioc_checker.Policy_admission.admit ~document:(R.document request) ~descriptors:(R.definitions request)in
  let behavior=Bioc_compiler.Policy_lowering.lower source in A.admit ~request ~behavior
let source_edit id transform raw=edit["document";"program";"declarations"]
  (fun values->a(List.map(fun value->if text "id" value=id then transform value else value)(Json.array values)))raw

(* Re-pin the actual supplied model and every matching original and candidate
   reference, so these controls reach semantic correspondence, not stale hashes. *)
let changed_model raw candidate node_id transform=
  let graph=get "implementation" candidate and library=get "implementation_library" raw in
  let actual=List.find(fun node->text "id" node=node_id)(rows "nodes" graph)in
  let old=get "model" actual in
  let original=List.find(fun model->Json.equal(get "identity" model)old)(rows "models" library)in
  let body=edit["configuration"]transform(get "body" original)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" original)in
  let model=original|>set "body" body|>set "identity" identity|>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))in
  let library=set "models"(a(List.map(fun value->if Json.equal(get "identity" value)old then model else value)(rows "models" library)))library in
  let raw=raw|>set "implementation_library" library|>edit["catalog_bindings"]
    (fun values->a(List.map(fun bridge->edit["models"](fun pins->a(List.map(fun pin->if Json.equal pin old then identity else pin)(Json.array pins)))bridge)(Json.array values)))in
  let graph=graph|>edit["authority";"library_digest"](fun _->s(Canonical.fingerprint library))|>edit["nodes"]
    (fun values->a(List.map(fun node->if Json.equal(get "model" node)old then node|>set "model" identity
      |>set "configuration_digest"(get "configuration_digest" model)else node)(Json.array values)))in
  raw,set "implementation" graph candidate
let static_controls raw candidate bound=
  let binding=get "binding" candidate in
  let anchor field id=List.find(fun row->text "source" row=id)(rows field binding)in
  let first field=List.hd(rows field binding)in
  let changed label node transform=let original,mutant=changed_model raw candidate node transform in
    rejects ~code:"policy_implementation_source_binding" label(fun()->bind original mutant)in
  changed "complete policy priority reversed"(text "arbiter"(first "transitions"))(edit["order"](fun values->a(List.rev(Json.array values))));
  changed "known register initialization changed"(text "register"(first "states"))(set "initial"(s "true"));
  changed "launch destination changed"(text "commit"(anchor "transitions" "alpha/launch_a"))(set "destination"(s "ready"));
  changed "own-machine feedback correlation removed"(text "gate"(anchor "transitions" "alpha/complete_a"))(set "correlation"(s "unbound"));
  changed "independent evidence freshness changed"(text "bank"(first "observations"))(set "freshness_ticks"(Json.int 9));
  changed "effect timeout changed"(text "bank"(first "effects"))(set "timeout_ticks"(Json.int 9));
  let changed_binding label field transform=rejects label(fun()->bind raw(edit["binding";field]transform candidate))in
  changed_binding "observation anchors swapped" "observations"(fun values->a(List.rev(Json.array values)));
  changed_binding "machine anchors swapped" "machines"(fun values->a(List.rev(Json.array values)));
  changed_binding "omitted shared store" "states"(fun _->a[]);
  changed_binding "wrong group lane" "transitions"(fun values->a(List.mapi(fun index row->if index=0 then set "lane"(Json.int 1)row else row)(Json.array values)));
  changed_binding "distinct source policy groups spliced" "transitions"(fun values->
    let foreign=get "arbiter"(anchor "transitions" "beta/launch_b")in
    a(List.map(fun row->if text "source" row="alpha/launch_a"then set "arbiter" foreign row else row)(Json.array values)));
  let beta=anchor "transitions" "beta/launch_b" and alpha=anchor "transitions" "alpha/launch_a"in
  rejects "transition reads sibling machine snapshot"(fun()->bind raw(edit["implementation";"wires"]
    (fun values->a(List.map(fun wire->if at["consumer";"node"]wire=get "gate" alpha && at["consumer";"port"]wire=s "machine"then
      set "producer"(o["node",get "bank"(anchor "machines" "beta/machine_b");"port",s "snapshot"])wire else wire)(Json.array values)))candidate));
  rejects "shared read silently retargeted"(fun()->bind raw(edit["implementation";"wires"]
    (fun values->a(List.map(fun wire->if at["consumer";"node"]wire=get "gate" beta && at["consumer";"port"]wire=s "guard"then
      set "producer"(o["node",get "bank"(first "observations");"port",s "value"])wire else wire)(Json.array values)))candidate));
  rejects "extra or missing source occurrence"(fun()->bind raw(edit["implementation";"occurrences"]
    (fun values->a(List.tl(Json.array values)))candidate));
  rejects "legacy decoder accepts network request"(fun()->R.of_json raw);
  rejects "finite decoder accepts network request"(fun()->R.of_finite_machine_json raw);
  rejects "finite binding downgrade"(fun()->bind raw(edit["binding"](fun value->value|>set "schema_version"(s U.finite_machine_schema_version)
    |>set "profile"(s U.finite_machine_profile))candidate));
  rejects ~code:"network_test_budget" "meter callback bounds correspondence"(fun()->B.check_network_metered
    ~charge:(fun _->Diagnostic.fail "network_test_budget" "No remaining owned work") ~admitted:(B.admitted_inputs bound)
    ~implementation:(B.implementation bound)~proposed:(U.of_json binding));
  let counters=ref 0 in
  let checked=B.check_network_metered ~charge:(fun amount->counters:= !counters+amount)
    ~admitted:(B.admitted_inputs bound)~implementation:(B.implementation bound)~proposed:(U.of_json binding)in
  require(!counters>String.length(Canonical.encode raw) && Json.equal(B.report checked)(B.report bound))
    "Metered network reconstruction changed evidence or omitted actual traversal work";
  let assignment=List.hd(rows "assignments"(List.find(fun row->text "id" row="alpha/launch_a")
    (rows "declarations"(at["document";"program"]raw))))in
  rejects ~code:"policy_realization_network" "state has a second writer machine"(fun()->admit_source
    (source_edit "beta/launch_b"(set "assignments"(a[assignment]))raw));
  rejects ~code:"policy_realization_network" "peer completion treated as communication"(fun()->admit_source
    (source_edit "beta/complete_b"(edit["on";"ref";"id"](fun _->s "alpha/response_a"))raw));
  rejects ~code:"policy_realization_network" "explicit predicate reset has no register interpretation"(fun()->admit_source
    (source_edit "alpha/permit"(set "reset"(get "value" assignment))raw))

let source_bounds=S.execution_bounds_of_json(o(List.map(fun(key,value)->key,Json.int value)
  ["max_ticks",32;"max_inputs",1000;"max_encounters",4;"max_attempts",16;
   "max_work",8_000_000;"max_trace_items",100000;"max_microsteps",32]))
let initialize ?(max_attempts=32) bound=
  let admitted=B.admitted_inputs bound and environment=B.environment bound in
  S.create ~behavior:(A.behavior admitted)~domain:(R.operating_domain(A.request admitted))~bounds:source_bounds,
  P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=20_000_000;max_events=200000;max_attempts;max_microsteps=32},T.create bound
let select source predicate=
  let rec scan count sequence=require(count<100000)"Handwritten network prefix search exceeded its own bound";
    match sequence()with Seq.Nil->failwith "Original network domain lacks the independent handwritten prefix"
    |Seq.Cons(value,rest)->if predicate value then value else scan(count+1)rest in scan 0(S.choices source)
let main_batch source=select source(fun(batch:F.input_batch)->
  let expected=match batch.tick with
    |3->["attempt/1",F.Completed;"attempt/2",F.Failed]
    |5->["attempt/1",F.Completed]|_->[]in
  List.sort compare(List.map(fun(row:F.feedback_input)->row.attempt.source_attempt_id,row.outcome)batch.feedback)=List.sort compare expected &&
  List.for_all(fun(slot,action)->action=(if batch.tick=7 && slot="e1" then F.Reset else F.Keep))batch.lifecycle)
let advance correspondence batch (source:S.advanced) candidate=
  T.advance correspondence ~batch ~source_frame:source.frame
    ~source_attempts:(rows "attempts"(Option.get source.receipt.execution))~source_creations:source.creations ~candidate
(* These expected states and attempt ordinals are handwritten from the source
   protocol. They are not derived from a producer graph or a saved receipt. *)
let expected_machine machine tick slot=
  let ordinal=1 in
  if slot="e2"then "ready",[] else if machine="alpha/machine_a"then
    if tick=0 || tick=7 then "ready",[]
    else if tick=3 then "ready",[ordinal]
    else if tick<=2 then "active",[ordinal]
    else if tick<=6 then "active",[ordinal+2]
    else "active",[ordinal+4]
  else if tick<=1 || tick=7 || tick=8 then "ready",[]
    else if tick=2 then "active",[ordinal+1]
    else if tick<=4 then "ready",[ordinal+1]
    else if tick<=6 then "active",[ordinal+3]
    else "active",[ordinal+5]
let literal_trace bound=
  let source,runtime,correspondence=initialize bound in
  let rec loop source runtime correspondence=
    if S.finished source then ()else
    let batch=main_batch source in
    let runtime,frame=P.step runtime(T.input correspondence batch)in
    let original=match S.step source batch with S.Advanced value->value
      |S.Stopped value->failwith("Handwritten network source stopped: "^value.diagnostic.code)in
    let matched=advance correspondence batch original frame in
    List.iter(fun(machine:B.machine)->List.iter(fun slot->
      let expected,attempts=expected_machine machine.source frame.tick slot in
      let value=List.find(fun(value:P.machine_snapshot)->value.bank=machine.bank && value.binding.slot=Some slot)frame.machines in
      require(value.state=expected && value.binding.generation=(if frame.tick>=7 && slot="e1" then 1 else 0) &&
        value.retained_attempts=List.map(fun n->"primitive/attempt/"^string_of_int n)attempts)
        ("Literal candidate machine/attempt/slot differs: "^machine.source^"/"^slot^"/"^string_of_int frame.tick);
      let row=List.find(fun value->get "machine" value=s machine.source && at["binding";"encounter"]value=s slot)(rows "machines" original.frame)in
      require(get "state" row=s expected && get "attempts" row=a(List.map(fun n->s("attempt/"^string_of_int n))attempts))
        "Literal source machine/retained attempts differ") ["e1";"e2"])(B.machines bound);
    let store=List.hd(B.states bound)in
    List.iter(fun slot->let permit=slot="e1" && not(List.mem frame.tick[0;3;7])in
      let port=List.find(fun(port:P.port_value)->port.endpoint.node_id=store.register &&
      port.endpoint.port_id="value" && port.binding.slot=Some slot)frame.outputs in
      require(port.signal=P.Truth{value=Some(if permit then I.True else I.False);reasons=[]})"Literal shared register differs";
      let row=List.find(fun row->get "state" row=s "alpha/permit" && at["binding";"encounter"]row=s slot)(rows "states" original.frame)in
      require(get "value" row=Json.Bool permit)"Literal source shared state differs") ["e1";"e2"];
    if frame.tick=1 then require(List.length frame.creations=1)"Peer read a same-batch write instead of precommit snapshot";
    if frame.tick=2 then (
      let a_bank=(List.find(fun(v:B.observation)->v.source="sense/condition_a")(B.observations bound)).bank
      and b_bank=(List.find(fun(v:B.observation)->v.source="sense/condition_b")(B.observations bound)).bank in
      require(List.for_all(fun(value:P.evidence_snapshot)->if value.bank=a_bank then (if value.binding.slot=Some "e1"then value.signal.value=None else value.signal.value=Some I.False)
        else if value.bank=b_bank then value.signal.value=Some(if value.binding.slot=Some "e1"then I.True else I.False) && value.observed_tick=Some 1 else false)frame.evidence)
        "Independent Missing versus aged-known truth evidence collapsed";
      require(List.length frame.creations=1)"Later update did not consume committed communication state";
      let first=List.find(fun(value:P.machine_snapshot)->value.bank=(List.hd(B.machines bound)).bank && value.binding.slot=Some "e1")frame.machines in
      let forged={first with retained_attempts=["primitive/attempt/2"]}in
      rejects "cross-machine retained attempt cannot splice"(fun()->advance correspondence batch original
        {frame with machines=List.map(fun value->if value=first then forged else value)frame.machines;
          outputs=List.map(fun(value:P.port_value)->match value.signal with P.Machine actual when actual=first->
            {value with signal=P.Machine forged}|_->value)frame.outputs}));
    if frame.tick=3 then require(List.length(List.filter(fun(action:P.action)->match action.detail with P.Machine_transition _->true|_->false)frame.actions)=2)
      "Independent priority groups did not commit both controllers in the active slot";
    if frame.tick=5 then require(List.length(List.filter(fun(action:P.action)->match action.detail with P.Feedback_rejected _->true|_->false)frame.actions)=1)
      "Stale prior-attempt feedback advanced a newer controller attempt";
    if frame.tick=6 then (
      let bank id=(List.find(fun(v:B.observation)->v.source=id)(B.observations bound)).bank in
      let evidence id=List.find(fun(value:P.evidence_snapshot)->value.bank=bank id && value.binding.slot=Some "e1")frame.evidence in
      require((evidence "sense/condition_a").signal={P.value=None;reasons=[P.Stale]} &&
        (evidence "sense/condition_b").signal={P.value=Some I.True;reasons=[]})
        "Independent freshness did not retain stale A alongside still-known B");
    if frame.tick=7 then require(frame.creations=[] && List.for_all(fun(value:P.slot_snapshot)->value.generation=(if value.slot_id="e1"then 1 else 0))frame.slots)
      "Reset failed to preserve the independent encounter generations";
    loop original.next runtime matched in loop source runtime correspondence
let lower_bound raw=
  let admitted=admit_source raw in
  let actual,proposed=Bioc_compiler.Policy_network_lowering.lower_metered
    ~charge:Bioc_checker.Policy_generation_meter.no_charge ~admitted ~library:(R.implementation_library(A.request admitted))in
  B.check ~admitted ~implementation:actual ~proposed
let interleaved_controls raw=
  (* Both controllers can now start in one batch. Interleave their original
     transition declarations with beta first; the literal order must survive. *)
  let raw=source_edit "beta/launch_b"(edit["when"](fun value->List.hd(rows "args" value)))raw in
  let raw=edit["document";"program";"declarations"](fun values->
    let all=Json.array values in
    let transition id=List.find(fun value->text "id" value=id)all in
    a(List.filter(fun value->text "$type" value<>"Transition")all @ List.map transition
      ["beta/launch_b";"alpha/launch_a";"beta/complete_b";"alpha/complete_a";
       "beta/fail_b";"alpha/fail_a";"beta/timeout_b";"alpha/timeout_a"]))raw in
  let bound=lower_bound raw in
  let run max_attempts failing=
    let source,runtime,correspondence=initialize ~max_attempts bound in
    let batch=main_batch source in let runtime,frame=P.step runtime(T.input correspondence batch)in
    let original=match S.step source batch with S.Advanced value->value|S.Stopped _->failwith "Interleaved prefix stopped"in
    let correspondence=advance correspondence batch original frame in
    let batch=main_batch original.next in
    if failing then (
      let before=P.state_fingerprint runtime in
      rejects ~code:"policy_primitives_attempt_limit" "simultaneous independent requests reserve before any write"
        (fun()->P.step runtime(T.input correspondence batch));
      require(P.state_fingerprint runtime=before)"Rejected atomic batch mutated its predecessor")
    else (
      let _,frame=P.step runtime(T.input correspondence batch)in
      let original=match S.step original.next batch with S.Advanced value->value|S.Stopped _->failwith "Interleaved activation stopped"in
      ignore(advance correspondence batch original frame);
      let bank id=(List.find(fun(effect_value:B.effect_binding)->effect_value.source=id)(B.effects bound)).bank in
      require(List.map(fun(attempt:P.attempt)->attempt.bank)frame.creations=[bank "beta/response_b";bank "alpha/response_a"])
        "Interleaved source group order changed exact attempt creation ordinals";
      require(List.map(fun(attempt:P.attempt)->attempt.ordinal)frame.creations=[1;2])"Interleaved attempt identities were normalized away")in
  run 32 false;run 1 true

let shared_case shared limits=
  let raw=get "request" shared in
  let produced=call Producer.handle Protocol.Core "compile-policy-implementation"(o["request",raw;"limits",limits])in
  let candidate=get "candidate" produced and report=get "report" produced in
  require(get "implementation" produced=s "biocompiler.ocaml.policy_network_implementation.v0.1" &&
    get "status" report=s "checked_implementation" && at["coverage";"complete"]report=Json.Bool true)
    "Shared policy did not retain complete native bounded checking";
  let safety=List.find(fun row->get "id" row=s "shared_capacity_one")(rows "requirements" report)in
  require(get "status" safety=s "pass" && get "nonvacuous" safety=Json.Bool true &&
    get "source" safety=List.find(fun row->get "id" row=s "shared_capacity_one")
      (rows "declarations"(at["document";"program"]raw)))"Logical capacity-one safety was lost or replaced by physical capacity claims";
  let replay=call Service.handle Protocol.Verify "replay-policy-implementation"
    (o["request",raw;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replay produced)"Shared-policy replay did not recheck the exact originals";
  let bound=bind raw candidate in
  require(List.length(I.atomic_groups(B.implementation bound))=1)"Identical complete policies were split into independent arbiters";
  let source,runtime,correspondence=initialize bound in
  let rec loop source runtime correspondence=
    if S.finished source then ()else
    let batch=select source(fun(batch:F.input_batch)->
      List.map(fun(row:F.feedback_input)->row.attempt.source_attempt_id,row.outcome)batch.feedback=
        (if batch.tick=3 then["attempt/1",F.Completed]else[]))in
    let runtime,frame=P.step runtime(T.input correspondence batch)in
    let original=match S.step source batch with S.Advanced value->value|S.Stopped _->failwith "Shared protocol source stopped"in
    let matched=advance correspondence batch original frame in
    List.iter(fun slot->
      let truth id=let row=List.find(fun row->get "state" row=s id && at["binding";"encounter"]row=s slot)(rows "states" original.frame)in
        get "value" row=Json.Bool true in
      let a_busy=truth "alpha/busy" and b_busy=truth "beta/busy"in
      require(not(a_busy && b_busy))"Handwritten logical capacity-one invariant violated";
      require(a_busy=(slot="e1" && (frame.tick=1 || frame.tick=2)) && b_busy=(slot="e1" && frame.tick=4))
        "Shared priority/busy communication differs from literal protocol") ["e1";"e2"];
    if frame.tick=1 then (
      let alpha=(List.find(fun(e:B.effect_binding)->e.source="alpha/response_a")(B.effects bound)).bank in
      require(List.map(fun(e:P.attempt)->e.bank)frame.creations=[alpha])"Shared group chose the wrong capacity-one winner";
      let beta=(List.find(fun(t:B.transition)->t.source="beta/launch_b")(B.transitions bound)).gate in
      require(List.exists(fun(action:P.action)->match action.detail with P.Suppressed(value,_)->value.gate=beta|_->false)frame.actions)
        "Shared group erased explicit priority suppression");
    if frame.tick=2 then require(frame.creations=[])"Held busy state permitted a second logical user";
    loop original.next runtime matched in loop source runtime correspondence;
  (* Keep the complete shared priority order and original safety requirement;
     re-pin the selected arbiter after reversing its actual priority. *)
  let arbiter=(List.hd(I.atomic_groups(B.implementation bound))).arbiter in
  let raw,candidate=changed_model raw candidate arbiter(edit["order"](fun values->a(List.rev(Json.array values))))in
  rejects ~code:"policy_implementation_source_binding" "shared priority reversal does not inherit safety evidence"(fun()->bind raw candidate)

let pool_deficit request=
  edit["context";"providers"](fun values->a(List.map(fun provider->
    let body=get "body" provider in
    let capacities=rows "capacities" body in
    if not(List.exists(fun capacity->text "unit" capacity="active_attempt_records")capacities)then provider else
    let changed=List.map(fun capacity->if text "unit" capacity="active_attempt_records"then set "quantity"(Json.int 23)capacity else capacity)capacities in
    let body=set "capacities"(a changed)body in
    provider|>set "body" body|>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body))) (Json.array values)))request
let rejected_module label ?issue operation payload=
  let request:Protocol.request={request_id="network-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Ok,Some result,[]->
    require(at["material";"report";"status"]result=s "not_accepted" && get "artifact" result=Json.Null)
      ("Network material adversary accepted: "^label);
    Option.iter(fun code->require(contains_string code result)("Network rejection did not reach intended semantic issue: "^code))issue;incr controls
  |_,None,errors when errors<>[]->
    require(issue=None)("Network semantic material control stopped before checker: "^label);incr controls
  |_->failwith("Malformed network material rejection: "^label)
  |exception Diagnostic.Error error->require(issue=None)("Network semantic material control threw early: "^label^"/"^error.code);incr controls

let ()=
  require(Array.length Sys.argv=2)"Expected independent machine-network fixture";
  let fixture=read Sys.argv.(1)in
  require(get "schema_version" fixture=s "biocompiler.policy_machine_network_literals.v0.1")"Wrong network fixture profile";
  let modules=get "modules" fixture and program=get "program" fixture and request=get "request" fixture
  and limits=get "limits" fixture and expected=get "expected" fixture in
  require(Json.equal program(get "program" expected) && Json.equal program(at["implementation_request";"document";"program"]request))
    "Independent flattened program is not the complete material original";
  let original=M.of_json request in
  require(M.is_network original && not(M.is_finite_machine original) && M.requires_prerequisite_closure original)
    "Network material family widened or downgraded another profile";
  require(Json.equal(Bioc_domain.Policy_component_context.ordered_union_json(M.composition_rule original))(get "ordered_union" expected))
    "Network component assembly differs from independent complete supplied union";
  let produced=call Producer.handle Protocol.Core "compile-policy-module-material"(o["modules",modules;"request",request;"limits",limits])in
  let material=get "material" produced and linkage=get "linkage" produced in
  let candidate=get "candidate" material and report=get "report" material in
  require(get "status" report=s "checked_component_material" && get "artifact" produced=Json.Null && get "artifact" material=Json.Null &&
    get "implementation" material=s "biocompiler.ocaml.policy_network_component_material.v0.1")
    "Complete network material conjunction was not freshly checked with export withheld";
  require(get "relation" linkage=s "exact_module_elaboration" && get "behavior" linkage=s "unassessed" &&
    get "empirical" linkage=s "unassessed" && get "program_fingerprint" linkage=s(Canonical.fingerprint program))
    "Module linkage changed source meaning or asserted separate behavioral proof";
  let binding=get "binding" candidate in
  require(get "schema_version" binding=s U.network_schema_version && get "profile" binding=s U.network_profile)
    "Network producer selected a legacy binding family";
  List.iter(fun(field,count)->require(List.length(rows field binding)=count)("Literal complete network binding census differs: "^field))
    ["observations",2;"states",1;"machines",2;"transitions",8;"effects",2];
  require(List.length(rows "nodes"(get "implementation" candidate))=35 &&
    List.length(rows "wires"(get "implementation" candidate))=70)"Independent supplied network graph census differs";
  require(at["preservation";"coverage";"complete"]report=Json.Bool true &&
    get "all_original_obligations_discharged" report=Json.Bool true && get "empirical" report=s "unassessed" &&
    List.for_all(fun row->get "status" row=s "pass" && get "nonvacuous" row=Json.Bool true)(rows "requirements"(get "preservation" report)))
    "Network material omitted original requirements, full exploration or its empirical boundary";
  let invocation=o["modules",modules;"request",request;"candidate",candidate;"limits",limits]in
  let checked=call Service.handle Protocol.Verify "check-policy-module-material" invocation in
  require(Json.equal checked produced)"Fresh independent module/material check changed exact evidence";
  let replay=call Service.handle Protocol.Verify "replay-policy-module-material"(o(("report",checked)::Json.object_fields invocation))in
  require(Json.equal replay checked)"Saved network report did not require exact fresh replay";
  let exported=call Service.handle Protocol.Verify "export-policy-module-material" invocation in
  let artifact=get "artifact" exported and child=at["material";"artifact"]exported in
  let manifest=get "manifest" artifact in
  let fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n"in
  require(get "sequence" expected=s "CCAUGGCUUAAGGAAAA" && get "fasta" artifact=s fasta &&
    get "fasta_sha256" artifact=s(Canonical.sha256 fasta) && get "fasta" child=s fasta &&
    Json.equal(get "modules" manifest)modules && Json.equal(get "linkage" manifest)linkage &&
    Json.equal(get "material_manifest" manifest)(get "manifest" child) &&
    get "manifest_sha256" artifact=s(Canonical.fingerprint manifest) &&
    get "material_manifest_sha256" manifest=get "manifest_sha256" child)
    "Exact paired network RNA export lost original authority or changed literal bases";
  require(Json.equal(at["construction";"inventory";"molecules"]candidate)(a[get "molecule" expected]))
    "Network realization differs from the independently supplied exact RNA molecule";
  let raw=get "implementation_request" request in
  let bound=bind raw candidate in
  static_controls raw candidate bound;literal_trace bound;interleaved_controls raw;
  let deficit=pool_deficit request in
  ignore(M.of_json deficit);
  rejected_module "shared physical capacity below sum" ~issue:"shared_capacity_sum_exceeded" "check-policy-module-material"
    (set "request" deficit invocation);
  rejected_module "exact emitted RNA mutation" "export-policy-module-material"
    (edit["candidate";"construction";"inventory";"molecules"](fun values->a(List.map(fun value->set "sequence"(s "ACAUGGCUUAAGGAAAA")value)(Json.array values)))invocation);
  rejected_module "incomplete exploration cannot inherit module linkage" "check-policy-module-material"
    (edit["limits";"max_step_work"](fun _->Json.int 1)invocation);
  rejected_module "forged saved pass cannot substitute for fresh checking" "replay-policy-module-material"
    (o(("report",checked)::Json.object_fields(edit["limits";"max_step_work"](fun _->Json.int 1)invocation)));
  shared_case(get "shared" fixture)limits;
  require(!controls=28)"Network rejection control census is incomplete";
  Printf.printf "policy_network: independent controllers, shared state, exact arbitration, bounded resources, module/RNA export, %d rejections\n" !controls
