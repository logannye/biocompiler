open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module Q = Bioc_domain.Policy_quantitative_network_contract
module K = Bioc_domain.Construction_content
module U = Bioc_domain.Policy_component_assembly_proposal
module RA = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module S = Bioc_semantics.Policy_domain_reference
module Runtime = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
module P = Bioc_realization_checker.Policy_preservation_check
module A = Bioc_realization_checker.Policy_component_assembly_check
module C = Bioc_realization_checker.Policy_component_context_check
module Check = Bioc_realization_checker.Policy_component_material_check
module Quant = Bioc_realization_checker.Policy_quantitative_check
module Network = Bioc_realization_checker.Policy_quantitative_network_check
module Local = Bioc_domain.Policy_component_material
module Fragment = Bioc_domain.Policy_component_fragment
module Outcome = Bioc_domain.Construction_assessment
module Material = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let ()=Printexc.register_printer(function
  |Diagnostic.Error d->Some(Printf.sprintf "Diagnostic.Error(%s, %s)" d.code d.message)
  |_->None)
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let accepted label=function Some value->value|None->failwith(label^" withheld its checked capability")
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="quantitative-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Quantitative adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let rejected_service label operation payload=
  let request:Protocol.request={request_id="quantitative-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Error,None,(_::_)->incr controls
  |_->failwith("Quantitative service adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let edge_ids=["a_to_b";"b_to_c";"a_to_c";"b_to_a";"c_to_a"]
let table_row source input destination request before after allocations=o[
  "source",s source;"input",s input;"destination",s destination;"request",Json.Bool request;
  "before",a(List.map Json.int before);"after",a(List.map Json.int after);
  "flows",a(List.map2(fun transfer quanta->o["transfer",s transfer;"quanta",Json.int quanta])edge_ids allocations)]

(* Independent literal oracle. The edge order is A->B, B->C, A->C on True,
   B->A, C->A on False. q100 distinguishes reuse of incoming stock. The
   independently repinned B->C-first variant below distinguishes reuse of
   freed headroom at q110; both incorrect strategies conserve the total. *)
let expected_table=a[
  table_row "q000" "true" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q000" "false" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q000" "unknown" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q001" "true" "q001" false [0;0;1] [0;0;1] [0;0;0;0;0];
  table_row "q001" "false" "q100" false [0;0;1] [1;0;0] [0;0;0;0;1];
  table_row "q001" "unknown" "q001" false [0;0;1] [0;0;1] [0;0;0;0;0];
  table_row "q010" "true" "q001" false [0;1;0] [0;0;1] [0;1;0;0;0];
  table_row "q010" "false" "q100" false [0;1;0] [1;0;0] [0;0;0;1;0];
  table_row "q010" "unknown" "q010" false [0;1;0] [0;1;0] [0;0;0;0;0];
  table_row "q011" "true" "q011" false [0;1;1] [0;1;1] [0;0;0;0;0];
  table_row "q011" "false" "q101" false [0;1;1] [1;0;1] [0;0;0;1;0];
  table_row "q011" "unknown" "q011" false [0;1;1] [0;1;1] [0;0;0;0;0];
  table_row "q100" "true" "q010" true [1;0;0] [0;1;0] [1;0;0;0;0];
  table_row "q100" "false" "q100" false [1;0;0] [1;0;0] [0;0;0;0;0];
  table_row "q100" "unknown" "q100" false [1;0;0] [1;0;0] [0;0;0;0;0];
  table_row "q101" "true" "q011" true [1;0;1] [0;1;1] [1;0;0;0;0];
  table_row "q101" "false" "q101" false [1;0;1] [1;0;1] [0;0;0;0;0];
  table_row "q101" "unknown" "q101" false [1;0;1] [1;0;1] [0;0;0;0;0];
  table_row "q110" "true" "q101" false [1;1;0] [1;0;1] [0;1;0;0;0];
  table_row "q110" "false" "q110" false [1;1;0] [1;1;0] [0;0;0;0;0];
  table_row "q110" "unknown" "q110" false [1;1;0] [1;1;0] [0;0;0;0;0];
  table_row "q111" "true" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0];
  table_row "q111" "false" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0];
  table_row "q111" "unknown" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0]]
let conservation=o[
  "scope",s "accepted_samples_within_encounter_generation";
  "quantity",s "sum_all_reservoirs";"reset",s "restore_declared_initial_vector";
  "checked_rows",Json.int 24]

(* Repin the complete independently supplied local contract and every direct
   selected-component/rule reference. These mutants are not stale-hash tests. *)
let refresh_context request=
  let layout=Canonical.fingerprint(at["context";"record_layout"]request)in
  edit["context";"providers"](fun providers->a(List.map(fun provider->
    let body=get "body" provider in
    let body=if text "kind" body="environment" then
      set "grammar"(at["implementation_request";"operating_domain"]request)body else body in
    let body=edit["capacities"](fun capacities->a(List.map(fun capacity->
      set "record_layout_digest"(s layout)capacity)(Json.array capacities)))body in
    provider|>set "body" body|>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body)))
    (Json.array providers)))request
let change_contract request change=
  let selected=at["quantitative";"selection";"component"]request in
  let components=rows "components"(get "component_library" request)in
  let component=List.find(fun value->Json.equal(get "identity" value)selected)components in
  let body=edit["quantitative_contracts"](fun values->a(List.map change(Json.array values)))(get "body" component)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" component)in
  let component=component|>set "body" body|>set "identity" identity in
  let selected_rows values=a(List.map(fun value->
    if Json.equal(get "component" value)selected then set "component" identity value else value)(Json.array values))in
  let rule=get "composition_rule" request|>edit["body";"components"]selected_rows in
  let rule=set "identity"(set "content_fingerprint"(s(Canonical.fingerprint(get "body" rule)))(get "identity" rule))rule in
  let request=request|>edit["component_library";"components"](fun _->a(List.map(fun value->
      if Json.equal(get "identity" value)selected then component else value)components))
    |>set "composition_rule" rule
    |>edit["catalog_binding";"components"]selected_rows
    |>edit["catalog_binding";"rule"](fun _->get "identity" rule)
    |>edit["quantitative";"selection";"component"](fun _->identity)
    |>edit["context";"record_layout";"rule"](fun _->get "identity" rule)in
  (* Complete capacity records pin the whole record layout, which in turn pins
     the original rule. Provider references are unchanged DefinitionRefs; each
     changed supplied provider Model identity must nevertheless be refreshed. *)
  refresh_context request
let candidate_for request candidate=
  edit["assembly_proposal";"rule"](fun _->at["composition_rule";"identity"]request)candidate
let quant_check preservation request candidate=
  let request=M.of_json request in
  let assembly=A.check ~original:(M.implementation_request request) ~components:(M.component_library request)
    ~rule:(M.composition_rule request) ~implementation:preservation
    ~proposed:(U.of_json(get "assembly_proposal" candidate))
    ~candidate:(K.of_json(get "construction" candidate))() in
  let assembly=accepted "Fresh repinned assembly"(A.accepted assembly)in
  let context=C.check ~request ~assembly () in
  let context=accepted "Fresh repinned context"(C.accepted context)in
  Quant.check ~request ~context ()
let quantitative_failure preservation label request candidate=
  let result=quant_check preservation request(candidate_for request candidate)in
  require(Quant.accepted result=None && Quant.outcome result=Outcome.Fail &&
    get "table"(Quant.report result)=a[] &&
    get "bindings"(Quant.report result)=Json.Null && get "conservation"(Quant.report result)=Json.Null)
    ("Quantitative semantic mutant did not fail at the quantitative checker: "^label);
  incr controls

let source_bounds=S.execution_bounds_of_json(o(List.map(fun(k,v)->k,Json.int v)
  ["max_ticks",32;"max_inputs",1000;"max_encounters",4;"max_attempts",32;
   "max_work",8_000_000;"max_trace_items",100000;"max_microsteps",30]))
let initialize bound=
  let admitted=B.admitted_inputs bound and environment=B.environment bound in
  S.create ~behavior:(RA.behavior admitted) ~domain:(R.operating_domain(RA.request admitted)) ~bounds:source_bounds,
  Runtime.initialize ~implementation:(B.implementation bound)
    ~environment:{Runtime.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{Runtime.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{Runtime.max_work=20_000_000;max_events=200000;max_attempts=32;max_microsteps=30},T.create bound
let select source reset=
  let rec scan count sequence=
    require(count<100)"Quantitative literal selection exceeded its independent search bound";
    match sequence()with
    |Seq.Nil->failwith "Original finite domain lacks the handwritten quantitative witness"
    |Seq.Cons(value,rest)->
      if List.for_all(fun(_,action)->action=(if reset && value.F.tick=7 then F.Reset else F.Keep))value.lifecycle
      then value else scan(count+1)rest in
  scan 0(S.choices source)
let expected_state reset tick=
  List.nth (if reset then
    ["q101";"q011";"q011";"q101";"q011";"q011";"q011";"q110";"q101";"q011";"q011";"q101";"q101"]
    else ["q101";"q011";"q011";"q101";"q011";"q011";"q011";"q101";"q011";"q011";"q011";"q101";"q101"]) tick
let selected_trace bound reset=
  let source,runtime,correspondence=initialize bound in
  let created=ref 0 in
  let rec loop source runtime correspondence=
    if S.finished source then correspondence else
    let batch=select source reset in
    let runtime,frame=Runtime.step runtime(T.input correspondence batch)in
    let advanced=match S.step source batch with S.Advanced value->value
      |S.Stopped stopped->failwith("Quantitative literal source stopped: "^stopped.diagnostic.code)in
    let matched=T.advance correspondence ~batch ~source_frame:advanced.frame
      ~source_attempts:(rows "attempts"(Option.get advanced.receipt.execution))
      ~source_creations:advanced.creations ~candidate:frame in
    let expected=expected_state reset frame.tick in
    List.iter(fun slot->
      let machine=List.find(fun(value:Runtime.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
      require(machine.state=expected && machine.binding.generation=(if reset && frame.tick>=7 then 1 else 0))
        ("Literal reserved network candidate state/generation differs at "^string_of_int frame.tick);
      let source_machine=List.find(fun row->at["binding";"encounter"]row=s slot)(rows "machines" advanced.frame)in
      require(get "state" source_machine=s expected)
        "Literal quantitative source state differs from the independent amount trajectory")["e1";"e2"];
    let new_requests=if frame.tick=1 || frame.tick=4 || frame.tick=(if reset then 9 else 8) then 2 else 0 in
    require(List.length frame.creations=new_requests && List.length advanced.creations=new_requests)
      "Threshold crossing created missing or extra abstract effect attempts";
    created:= !created+List.length frame.creations;
    let expected_initiator="forward5"in
    List.iter(fun(attempt:Runtime.attempt)->
      let transition=List.find(fun(value:B.transition)->value.gate=attempt.gate)(B.transitions bound)in
      require(transition.source=expected_initiator)
        "Shared effect bank lost the actual initiating transition identity")frame.creations;
    if frame.tick=2 || (reset && frame.tick=10) then (
      require(frame.creations=[] && List.length(List.filter(fun(value:Runtime.attempt)->
        value.status=Runtime.Active && value.authorization=I.Unknown)frame.attempts)=2)
        "Unknown sample cancelled old active attempts or created a new request";
      require(List.length(List.filter(fun(event:Runtime.event)->event.kind=Runtime.Primitive_event I.Updated)frame.events)=2)
        "Unknown sample lost its update event");
    if frame.tick=6 then require(not(List.exists(fun(event:Runtime.event)->
      event.kind=Runtime.Primitive_event I.Updated)frame.events) && frame.creations=[])
        "No-update interval produced a quantitative sample step";
    loop advanced.next runtime matched in
  let matched=loop source runtime correspondence in
  require(!created=6 && text "claim"(T.report matched)="matched_prefix_only")
    "Selected quantitative trace changed request count or broadened its prefix scope"

let change_both_laws request change=
  change_contract (edit["quantitative";"mechanism"]change request)(edit["mechanism"]change)
let first_transfer change=edit["transfers"](fun values->match Json.array values with
  |first::rest->a(change first::rest)|[]->failwith "Missing independent transfer declaration")

let ()=
  require(Array.length Sys.argv=3)"Expected independent network and unchanged transfer-pair originals";
  let fixture=read Sys.argv.(1) and previous=read Sys.argv.(2)in
  require(Canonical.fingerprint previous="62e7fd29a1fa3917a20b70149ae7fc57595badeee58655f63d004f70c512259d")
    "Existing exact transfer-pair fixture changed under the network profile";
  let previous_request=M.of_json(get "request" previous)in
  require(M.is_transfer_pair previous_request && not(M.is_transfer_network previous_request) &&
    M.request_profile previous_request=M.transfer_pair_profile)
    "New transfer network changed the previous pair route";
  require(text "schema_version" fixture="biocompiler.policy_quantitative_network_literals.v0.1")
    "Wrong reserved transfer network fixture schema";
  require(Json.equal(at["expected";"table"]fixture)expected_table)
    "Network fixture disagrees with the independent 24-row prestate reservation oracle";
  let request=get "request" fixture and limits=get "limits" fixture in
  let original=M.of_json request in
  require(M.is_transfer_network original && not(M.is_transfer_pair original) && M.is_multi_site original &&
    M.is_finite_machine original && M.is_quantitative original && M.quantitative original=None &&
    M.transfer_pair_quantitative original=None && Option.is_some(M.network_quantitative original))
    "Network lost its distinct joint law and existing finite multi-site implementation family";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete reserved transfer network material"(Check.accepted result)in
  let report=Check.report result and contextual=Check.context checked in
  let preservation=A.implementation(C.assembly contextual)in
  let bound=P.binding preservation in
  let quantitative=Quant.check ~request:original ~context:contextual ()in
  let network=Network.check ~request:original ~context:contextual ()in
  let summary=Quant.report quantitative in
  require(Quant.outcome quantitative=Outcome.Pass && Option.is_some(Quant.accepted quantitative) &&
    Network.outcome network=Outcome.Pass && Option.is_some(Network.accepted network) &&
    Json.equal summary(Network.report network) && Json.equal summary(get "quantitative" report) &&
    Json.equal(get "table" summary)expected_table && Json.equal(get "conservation" summary)conservation &&
    get "schema_version" summary=s "biocompiler.policy_quantitative_assessment.v0.4" &&
    get "profile" summary=s "biocompiler.policy_sampled_reserved_transfer_network.v0.1" &&
    get "claim_scope" summary=s "exact_sampled_reserved_transfer_network_under_supplied_contract" &&
    get "arbitration" summary=s "declared_order_prestate_reservation" &&
    get "ownership" summary=s "single_atomic_state_owner" && get "empirical" summary=s "unassessed" &&
    get "schema_version" report=s "biocompiler.policy_component_material_assessment.v0.8")
    "Fresh network evidence changed its complete law, ownership, reservation or conservation scope";
  let sites=rows "crossing_sites"(get "bindings" summary)in
  require(List.map(text "transition")sites=["forward4";"forward5"] &&
    List.map(text "source_state")sites=["q100";"q101"] &&
    List.map(text "attempt_port")sites=["request0";"request1"] &&
    List.for_all(fun row->get "input" row=Json.Bool true && at["request_endpoint";"port"]row=s "request0")sites)
    "Network checking pruned an unreachable crossing or detached its request lane";
  let effect_value=List.hd(B.effects bound)in
  require(List.length(B.effects bound)=1 && List.map(fun(value:B.effect_site)->value.initiating_rule)effect_value.request_sites=
    ["forward4";"forward5"] && at["bindings";"attempt_bank"]summary=s effect_value.bank &&
    List.length(B.transitions bound)=7 && List.length(I.nodes(B.implementation bound))=21)
    "Joint transfer ownership or sparse source/graph inventory changed";
  selected_trace bound false;
  selected_trace bound true;
  let law=at["quantitative";"mechanism"]request in
  List.iter(fun(label,path,value)->rejects label(fun()->Q.of_json(edit path(fun _->value)law)))
    ["implicit transfer arbitration",["arbitration"],s "simultaneous_unreserved";
     "unproved independent state owners",["ownership"],s "independent_reservoir_owners"];
  List.iter(fun(label,path,value)->rejects label(fun()->Q.of_json(first_transfer(edit path(fun _->value))law)))
    ["nonboolean transfer activation",["when"],s "true";
     "absent receiving compartment",["destination"],s "absent";
     "self-edge",["destination"],s "a";
     "binary float amount",["amount";"amount"],Json.Float 1.;
     "off-grid transfer",["amount";"amount"],s "0.5";
     "zero transfer bound",["amount";"amount"],s "0"];
  rejects "duplicate transfer identities"(fun()->Q.of_json(edit["transfers"]
    (fun values->let first=List.hd(Json.array values)in a[first;first])law));
  rejects "Cartesian product over sixteen"(fun()->Q.of_json(edit["reservoirs"]
    (fun values->a(List.map(edit["capacity";"amount"](fun _->s "2"))(Json.array values)))law));
  rejects "empty edge inventory"(fun()->Q.of_json(set "transfers"(a[])law));
  let component=List.find(fun row->Json.equal(get "identity" row)(at["quantitative";"selection";"component"]request))
    (rows "components"(get "component_library" request))in
  let local=List.hd(rows "quantitative_contracts"(get "body" component))in
  rejects "projected reachable state slice"(fun()->Q.local_of_json(edit["state";"values"]
    (fun values->a(List.filter(fun row->List.mem(text "state" row)["q011";"q101";"q110"])(Json.array values)))local));
  rejects "permuted joint-state grid"(fun()->Q.local_of_json(edit["state";"values"]
    (fun values->a(List.rev(Json.array values)))local));
  rejects "missing reservoir coordinate"(fun()->Q.local_of_json(edit["state";"values"]
    (fun values->a(List.map(edit["amounts"](fun amounts->a(List.tl(Json.array amounts))))(Json.array values)))local));
  rejects "aliased ordered reservoir coordinates"(fun()->Q.local_of_json(edit["state";"values"]
    (fun values->a(List.map(fun row->if text "state" row="q100" then
      edit["amounts"](fun amounts->a(List.rev(Json.array amounts)))row else row)(Json.array values)))local));
  rejects "empty crossing inventory"(fun()->Q.local_of_json(set "outputs"(a[])local));
  rejects "duplicate crossing coordinate"(fun()->Q.local_of_json(edit["outputs"]
    (fun values->let first=List.hd(Json.array values)in a[first;first])local));
  let library=R.implementation_library(M.implementation_request original)in
  let legacy_fragment=component|>edit["body";"fragment"](fun fragment->fragment
    |>set "profile"(s Fragment.staged_profile)|>set "primitive_profile"(s I.staged_profile)
    |>set "observable_profile"(s I.staged_observable_profile)|>set "phase_profile"(s Fragment.staged_phase_profile))in
  let legacy_fragment=edit["identity";"content_fingerprint"]
    (fun _->s(Canonical.fingerprint(get "body" legacy_fragment)))legacy_fragment in
  rejects "joint contract hidden inside a legacy fragment"(fun()->Local.of_json ~library legacy_fragment);
  rejects "pair local family consumes network ownership"(fun()->Local.of_json ~library
    (component|>set "schema_version"(s Local.transfer_pair_schema_version)|>set "profile"(s Local.transfer_pair_profile)));
  rejects "pair material route consumes a network contract"(fun()->M.of_json(request
    |>set "schema_version"(s M.transfer_pair_schema_version)|>set "profile"(s M.transfer_pair_profile)));
  rejects "step material route consumes a network contract"(fun()->M.of_json(request
    |>set "schema_version"(s M.step_quantitative_schema_version)|>set "profile"(s M.step_quantitative_profile)));
  rejects "network material route consumes the old pair law"(fun()->M.of_json(get "request" previous
    |>set "schema_version"(s M.transfer_network_schema_version)|>set "profile"(s M.transfer_network_profile)));
  rejects "zero network work"(fun()->Network.check ~maximum:0 ~request:original ~context:contextual ());
  let change_outputs f=change_contract request(edit["outputs"](fun rows->a(f(Json.array rows))))in
  quantitative_failure preservation "omitted counterfactual-total-one crossing"
    (change_outputs(fun values->List.filter(fun row->text "source_state" row<>"q100")values))candidate;
  quantitative_failure preservation "reordered local crossing coordinates"(change_outputs List.rev)candidate;
  quantitative_failure preservation "wrong crossing polarity"(change_outputs(fun values->
    List.mapi(fun index row->if index=0 then set "input"(Json.Bool false)row else row)values))candidate;
  quantitative_failure preservation "wrong crossing commit model"(change_outputs(fun values->
    List.mapi(fun index row->if index=0 then set "model"(at["state";"model"]local)row else row)values))candidate;
  quantitative_failure preservation "swapped real crossing boundaries"(change_outputs(function
    |[first;second]->[set "boundary"(get "boundary" second)first;set "boundary"(get "boundary" first)second]
    |_->failwith "Expected two independent crossing boundaries"))candidate;
  let reverse_order=edit["transfers"](fun values->a(List.rev(Json.array values)))in
  let reversed_original=edit["quantitative";"mechanism"]reverse_order request in
  quantitative_failure preservation "original/component edge priority mismatch" reversed_original candidate;
  (* Reversing order conserves total stock but changes q100 True from q010 to
     q001 and q110 True from q101 to q011. The old source must not be accepted. *)
  let reversed=change_both_laws request reverse_order in
  quantitative_failure preservation "reversed priority with unchanged conservative source" reversed candidate;
  let wrong_receiver=change_both_laws request(edit["transfers"](fun values->a(List.map(fun edge->
    if text "id" edge="b_to_c" then set "destination"(s "a")edge else edge)(Json.array values))))in
  quantitative_failure preservation "conservative but wrong receiving coordinate" wrong_receiver candidate;
  let disabled=change_both_laws request(edit["transfers"](fun values->a(List.map(fun edge->
    if text "id" edge="b_to_c" then set "when"(Json.Bool false)edge else edge)(Json.array values))))in
  quantitative_failure preservation "disabled edge still has a source transition" disabled candidate;
  (* B->C can be reserved before A->B without making B's freed space available
     to A. This positive law change leaves every source state/request identical
     while changing the ordered flow inventory. A write-through evaluator would
     incorrectly change q110 to q011 instead of q101. *)
  let swap_first_two values=match Json.array values with
    |first::second::rest->a(second::first::rest)|_->failwith "Missing independent priority pair"in
  let earlier_outflow=change_both_laws request(edit["transfers"]swap_first_two)in
  let earlier=quant_check preservation earlier_outflow(candidate_for earlier_outflow candidate)in
  let reordered_table=a(List.map(edit["flows"]swap_first_two)(Json.array expected_table))in
  require(Option.is_some(Quant.accepted earlier) && Json.equal(get "table"(Quant.report earlier))reordered_table &&
    get "mechanism_fingerprint"(Quant.report earlier)<>get "mechanism_fingerprint" summary)
    "Earlier outflow incorrectly freed same-sample headroom or lost declared flow ordering";
  (* Renaming nominal compartment identities consistently changes the authority
     pins while preserving the independently checked state and flow table. *)
  let renamed=change_both_laws request(fun law->law
    |>edit["reservoirs"](fun values->a(List.map(fun row->set "compartment"(s("renamed."^text "compartment" row))row)(Json.array values)))
    |>edit["transfers"](fun values->a(List.map(fun row->row
      |>set "source"(s("renamed."^text "source" row))|>set "destination"(s("renamed."^text "destination" row)))(Json.array values)))
    |>edit["threshold";"compartment"](fun value->s("renamed."^Json.string value)))in
  let renaming=quant_check preservation renamed(candidate_for renamed candidate)in
  require(Option.is_some(Quant.accepted renaming) && Json.equal(get "table"(Quant.report renaming))expected_table &&
    get "mechanism_fingerprint"(Quant.report renaming)<>get "mechanism_fingerprint" summary)
    "Consistent nominal renaming changed semantic allocations or reused original authority pins";
  let _,bad=Material.fresh_check ~request:reversed ~candidate:(candidate_for reversed candidate) ~limits in
  require(Check.accepted bad=None && at["quantitative";"outcome"](Check.report bad)=s "fail" &&
    get "all_original_obligations_discharged"(Check.report bad)=Json.Bool false)
    "Conserved-but-wrong priority acquired a complete material capability";
  incr controls;
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let replayed=call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replayed produced)"Fresh network replay changed the complete wrapper";
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" invocation in
  require(Json.equal(get "report" verified)report)"Independent verify service changed fresh network evidence";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  let artifact=get "artifact" exported and expected=get "expected" fixture in
  require(at["construction";"inventory";"molecules"]candidate=a[get "molecule" expected] &&
    get "fasta" artifact=s(">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n"))
    "Reserved network/source correspondence lost exact supplied RNA identity";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Network export omitted exact originals or complete fresh checking";
  let named=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  require(Json.equal(at["material_report";"quantitative"]named)summary)
    "Named refinement erased joint network reservation evidence";
  rejected_service "saved PASS cannot substitute fresh work" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",edit["max_step_work"](fun _->Json.int 1)limits;"report",produced]);
  let tampered=edit["report";"quantitative";"table"](fun values->a(List.map(fun row->
    if text "source" row="q100" && text "input" row="true" then
      edit["flows"](fun flows->a(List.map(fun flow->set "quanta"(Json.int(if text "transfer" flow="a_to_c" then 1 else 0))flow)
        (Json.array flows)))row else row)(Json.array values)))produced in
  rejected_service "saved flow changes winning donor reservation" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",tampered]);
  let tampered=edit["report";"quantitative";"table"](fun values->a(List.map
    (edit["flows"](fun flows->a(List.rev(Json.array flows))))(Json.array values)))produced in
  rejected_service "saved flow order changes declared priority" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",tampered]);
  let tampered=edit["report";"quantitative";"conservation";"scope"]
    (fun _->s "all_ticks_including_reset")produced in
  rejected_service "saved evidence broadens conservation across reset" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",tampered]);
  require(!controls=37)"Reserved transfer network rejection census is incomplete";
  Printf.printf "policy_quantitative_network: independent 24-row joint law, stock and headroom reservation, no sample cascade, two checked metamorphisms, reset and RNA export, %d rejection controls\n" !controls
