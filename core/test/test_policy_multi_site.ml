open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module Admission = Bioc_checker.Policy_admission
module A = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module L = Bioc_compiler.Policy_lowering
module G = Bioc_compiler.Policy_implementation_lowering
module P = Bioc_candidate_runtime.Policy_primitives
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path change value=match path with []->change value|key::rest->set key(edit rest change(get key value))value
let require condition message=if not condition then failwith message
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Multi-site adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let source request=Admission.admit ~document:(R.document request) ~descriptors:(R.definitions request)|>L.lower
let bind request implementation proposed=
  B.check ~admitted:(A.admit ~request ~behavior:(source request)) ~implementation ~proposed
let endpoint node port=o["node",s node;"port",s port]
let initialize bound implementation=
  let environment=B.environment bound in
  P.initialize ~implementation
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=40_000_000;max_events=400000;max_attempts=32;max_microsteps=30}
let machine (frame:P.frame)=List.find(fun(value:P.machine_snapshot)->value.binding.slot=Some "e1")frame.machines
let input bound tick evidence reset feedback=
  let observation=List.hd(B.observations bound)and effect=List.hd(B.effects bound)in
  ({P.tick=tick; lifecycle=(if reset then ["e1",P.Reset]else []);
    observations=(match evidence with None->[]|Some evidence->
      [{P.observation_id="literal/"^string_of_int tick;input_id=observation.input;slot_id="e1";
        observed_tick=tick;observer="cell-1";subject="target-1";evidence}]);
    feedback=List.map(fun attempt_id->{P.feedback_id="feedback/"^string_of_int tick;input_id=effect.feedback;
      attempt_id;executor="cell-1";subject="target-1";slot_id="e1";outcome=P.Complete})feedback}:P.input_batch)
let step bound runtime tick evidence=P.step runtime(input bound tick evidence false [])

(* This fixture supplies models independently. Repinning the changed model in
   every original library/bridge/graph reference avoids a stale-pin rejection. *)
let repin ?primitive raw graph node_id change=
  let library=get "implementation_library" raw in
  let selected=List.find(fun node->text "id" node=node_id)(rows "nodes" graph)in
  let old=get "model" selected in
  let original=List.find(fun model->Json.equal(get "identity" model)old)(rows "models" library)in
  let body=edit["configuration"]change(get "body" original)in
  let body=match primitive with None->body|Some name->set "primitive"(s name)body in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))old in
  let digest=s(Canonical.fingerprint(get "configuration" body))in
  let model=original|>set "body" body|>set "identity" identity|>set "configuration_digest" digest in
  let library=edit["models"](fun values->a(List.map(fun value->
    if Json.equal(get "identity" value)old then model else value)(Json.array values)))library in
  let raw=raw|>set "implementation_library" library|>edit["catalog_bindings"](fun values->a(List.map(fun bridge->
    edit["models"](fun values->a(List.map(fun pin->if Json.equal pin old then identity else pin)(Json.array values)))bridge)(Json.array values)))in
  let graph=graph|>edit["authority";"library_digest"](fun _->s(Canonical.fingerprint library))
    |>edit["nodes"](fun values->a(List.map(fun node->if Json.equal(get "model" node)old then
      node|>set "model" identity|>set "configuration_digest" digest else node)(Json.array values)))in
  R.of_multi_site_json raw,I.of_json ~library:(I.library_of_json library)graph

let ()=
  require(Array.length Sys.argv=2)"Expected independent quantitative-step fixture";
  let fixture=read Sys.argv.(1)in
  let raw=at["request";"implementation_request"]fixture in
  let request=R.of_multi_site_json raw in
  require(R.is_multi_site request && R.is_finite_machine request)"Multi-site authority was not explicit";
  let admitted=A.admit ~request ~behavior:(source request)in
  let proposal=G.lower ~admitted ~library:(R.implementation_library request)in
  let bound=B.check ~admitted ~implementation:proposal.implementation ~proposed:proposal.binding in
  let effect=List.hd(B.effects bound)in
  require(List.map(fun(site:B.effect_site)->site.initiating_rule)effect.request_sites=["up1";"up2"])
    "Request sites do not retain original transition declaration order";
  require(effect.initiating_rule="up1" && effect.machine=Some "machine" &&
    I.implementation_profile proposal.implementation=I.multi_site_profile &&
    P.execution_profile proposal.implementation=P.multi_site_execution_profile)
    "Multi-site profiles or retained machine owner differ";
  let graph=I.to_json proposal.implementation in
  let decode graph=I.of_json ~library:(R.implementation_library request)graph in
  let check graph=bind request(decode graph)proposal.binding in
  let bank=effect.bank in
  let wire consumer=List.find(fun wire->Json.equal(get "consumer" wire)consumer)(rows "wires" graph)in
  let mutate_wire consumer producer=edit["wires"](fun values->a(List.map(fun wire->
    if Json.equal(get "consumer" wire)consumer then set "producer" producer wire else wire)(Json.array values)))graph in
  let request0=endpoint bank "request0"and request1=endpoint bank "request1"in
  let swap=edit["wires"](fun values->a(List.map(fun current->
    if Json.equal(get "consumer" current)request0 then set "producer"(get "producer"(wire request1))current
    else if Json.equal(get "consumer" current)request1 then set "producer"(get "producer"(wire request0))current
    else current)(Json.array values)))graph in
  rejects "site order cannot be swapped"(fun()->check swap);
  rejects "missing site driver"(fun()->decode(edit["wires"](fun values->a(List.filter(fun wire->
    not(Json.equal(get "consumer" wire)request1))(Json.array values)))graph));
  rejects "duplicate site driver"(fun()->decode(edit["wires"](fun values->a(wire request0::Json.array values))graph));
  let down=List.find(fun(t:B.transition)->t.source="down0")(B.transitions bound)in
  let wrong_guard=get "producer"(wire(endpoint down.gate "guard"))in
  let misguard=mutate_wire(endpoint bank "authorization0")wrong_guard in
  rejects "source site guard"(fun()->check misguard);
  rejects "runtime retained site guard"(fun()->initialize bound(decode misguard));
  let proposed=U.to_json proposal.binding in
  rejects "missing original site anchor"(fun()->B.check ~admitted ~implementation:proposal.implementation
    ~proposed:(U.of_json(edit["transitions"](fun values->a(List.filter(fun value->text "source" value<>"up2")(Json.array values)))proposed)));
  rejects "legacy request decoder"(fun()->R.of_finite_machine_json raw);
  rejects "legacy request does not widen initiator scope"(fun()->
    let legacy=R.of_finite_machine_json(raw|>set "schema_version"(s R.finite_machine_schema_version)
      |>set "profile"(s R.finite_machine_profile))in
    A.admit ~request:legacy ~behavior:(source legacy));
  rejects "legacy binding downgrade"(fun()->B.check ~admitted ~implementation:proposal.implementation
    ~proposed:(U.of_json(proposed|>set "schema_version"(s U.finite_machine_schema_version)|>set "profile"(s U.finite_machine_profile))));
  rejects "sites cannot cross source machine ownership"(fun()->
    let changed=edit["document";"program";"declarations"](fun values->
      let declarations=Json.array values in
      let original=List.find(fun value->text "$type" value="Machine")declarations in
      a(set "id"(s "other_machine")original::List.map(fun value->
        if text "$type" value="Transition" && text "id" value="up1" then
          edit["machine";"id"](fun _->s "other_machine")value else value)declarations))raw in
    let changed=R.of_multi_site_json changed in A.admit ~request:changed ~behavior:(source changed));
  let arbiter=(List.hd(B.transitions bound)).arbiter in
  let priority_request,priority=repin ~primitive:"priority_arbiter" raw graph arbiter(fun _->
    o["order",a(List.init(List.length(B.transitions bound))Json.int)])in
  rejects "source binding cannot introduce site priority"(fun()->bind priority_request priority proposal.binding);
  rejects "runtime shared sites require exclusive arbitration"(fun()->initialize bound priority);
  let runtime=initialize bound proposal.implementation in
  let runtime,frame0=step bound runtime 0(Some(P.Known true))in
  require((machine frame0).state="q2" && frame0.creations=[])"First two-quantum increment requested below threshold";
  let runtime,frame1=step bound runtime 1(Some(P.Known true))in
  let first=List.hd frame1.creations and site1=List.nth effect.request_sites 1 in
  require(List.length frame1.creations=1 && first.bank=bank && first.gate=site1.gate &&
    first.guard=site1.guard && first.attempt_id="primitive/attempt/1" && (machine frame1).state="q4")
    "Second crossing site did not retain its own exact attempt identity and guard";
  let runtime,_=step bound runtime 2(Some(P.Known false))in
  let runtime,_=step bound runtime 3(Some(P.Known false))in
  let runtime,frame4=step bound runtime 4(Some(P.Known false))in
  require((machine frame4).state="q1")"Literal decay trace differs from q4 to q1";
  let runtime,frame5=step bound runtime 5(Some(P.Known true))in
  let second=List.hd frame5.creations and site0=List.hd effect.request_sites in
  require(List.length frame5.creations=1 && second.bank=first.bank && second.gate=site0.gate &&
    second.guard=site0.guard && second.attempt_id="primitive/attempt/2" && second.attempt_id<>first.attempt_id &&
    (machine frame5).retained_attempts=[second.attempt_id])"Repeated effect sites coalesced attempts or retained the old request";
  let runtime,unknown=step bound runtime 6(Some P.Missing_evidence)in
  require((machine unknown).state="q3" && unknown.creations=[] &&
    (List.find(fun(value:P.attempt)->value.attempt_id=second.attempt_id)unknown.attempts).authorization=I.Unknown)
    "Unknown sample did not hold without request and retain continuous authorization uncertainty";
  let runtime,reset=P.step runtime(input bound 7 None true [])in
  require((machine reset).state="q0" && (machine reset).binding.generation=1 &&
    (machine reset).retained_attempts=[] &&
    (List.find(fun(value:P.attempt)->value.attempt_id=second.attempt_id)reset.attempts).status=P.Reset_invalidated)
    "Encounter reset retained a previous generation request";
  let runtime,_=step bound runtime 8(Some(P.Known true))in
  let runtime,new_attempt=step bound runtime 9(Some(P.Known true))in
  require((List.hd new_attempt.creations).attempt_id="primitive/attempt/3")"Reset reused an old attempt identity";
  let _,stale=P.step runtime(input bound 10 None false [second.attempt_id])in
  require(List.exists(fun(action:P.action)->match action.detail with P.Feedback_rejected _->true|_->false)stale.actions)
    "Old request-site feedback crossed the generation boundary";
  (* A single shared bank must charge active capacity across both sites. Extend
     the supplied timeout in this isolated primitive test so both remain live. *)
  let _,small=repin raw graph bank(fun value->value|>set "capacity"(Json.int 1)|>set "timeout_ticks"(Json.int 20))in
  let runtime=initialize bound small in
  let runtime,_=step bound runtime 0(Some(P.Known true))in
  let runtime,_=step bound runtime 1(Some(P.Known true))in
  let runtime,_=step bound runtime 2(Some(P.Known false))in
  let runtime,_=step bound runtime 3(Some(P.Known false))in
  let runtime,_=step bound runtime 4(Some(P.Known false))in
  rejects "capacity is shared across request sites"(fun()->step bound runtime 5(Some(P.Known true)));
  require(!controls>=13)"Multi-site rejection controls are incomplete";
  Printf.printf "policy_multi_site: two original request sites, distinct attempt identities, shared capacity, Unknown/reset/stale feedback, %d rejection controls\n" !controls
