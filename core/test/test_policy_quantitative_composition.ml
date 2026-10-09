open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module Composition_contract = Bioc_domain.Policy_quantitative_composition_contract
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
module Composition = Bioc_realization_checker.Policy_quantitative_composition_check
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
   separate network suite tests a repinned B->C-first variant for freed
   headroom; this suite adds actual selected allocation and owner-write ports. *)
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
let change_component request instance change=
  let selected=List.find(fun row->text "slot" row=instance)(rows "components"(at["composition_rule";"body"]request))|>get "component" in
  let components=rows "components"(get "component_library" request)in
  let component=List.find(fun value->Json.equal(get "identity" value)selected)components in
  let body=change(get "body" component)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" component)in
  let component=component|>set "body" body|>set "identity" identity in
  let selected_rows values=a(List.map(fun value->
    if Json.equal(get "component" value)selected then set "component" identity value else value)(Json.array values))in
  let rule=get "composition_rule" request|>edit["body";"components"]selected_rows in
  let rule=set "identity"(set "content_fingerprint"(s(Canonical.fingerprint(get "body" rule)))(get "identity" rule))rule in
  let request=request|>edit["component_library";"components"](fun _->a(List.map(fun value->
      if Json.equal(get "identity" value)selected then component else value)components))
    |>set "composition_rule" rule|>edit["catalog_binding";"components"]selected_rows
    |>edit["catalog_binding";"rule"](fun _->get "identity" rule)
    |>edit["quantitative";"owners"]selected_rows
    |>edit["context";"record_layout";"rule"](fun _->get "identity" rule)in
  let request=if instance="control" then edit["quantitative";"network";"selection";"component"](fun _->identity)request else request in
  refresh_context request
let change_contract request instance change=
  change_component request instance(edit["quantitative_contracts"](fun values->a(List.map change(Json.array values))))
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
      List.iteri(fun coordinate (state:B.state)->
        let port=List.find(fun(value:Runtime.port_value)->value.endpoint.node_id=state.register &&
          value.endpoint.port_id="value" && value.binding.slot=Some slot)frame.outputs in
        let wanted=if expected.[coordinate+1]='1' then I.True else I.False in
        require((match port.signal with Runtime.Truth signal->signal.value=Some wanted|_->false))
          "Separate selected reservoir register differs from its atomic machine coordinate") (B.states bound);
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


let ()=
  require(Array.length Sys.argv=3)"Expected coupled and unchanged single-owner network fixtures";
  let fixture=read Sys.argv.(1) and previous=read Sys.argv.(2)in
  let previous_request=M.of_json(get "request" previous)in
  require(M.is_transfer_network previous_request && not(M.is_quantitative_composition previous_request))
    "Coupled profile changed the existing exact single-owner network route";
  require(text "schema_version" fixture="biocompiler.policy_quantitative_composition_literals.v0.1" &&
    Json.equal(at["expected";"table"]fixture)expected_table)
    "Coupled fixture changed its independent full-grid allocation oracle";
  let request=get "request" fixture and limits=get "limits" fixture in
  let original=M.of_json request in
  require(M.is_quantitative_composition original && M.is_multi_site original &&
    R.is_coupled(M.implementation_request original) && Option.is_some(M.network_quantitative original))
    "Partitioned composition lost its explicit source and selected-network authority";
  let realization=get "implementation_request" request in
  let plan_request=o["schema_version",s "biocompiler.policy_target_plan_request.v0.1";
    "target",s "coupled_quantitative_material";"document",get "document" realization;
    "definitions",get "definitions" realization;"realization_request",realization;"material_request",request;
    "limits",o["max_work",Json.int 100000000;"max_report_bytes",Json.int 2097152;"max_report_nodes",Json.int 100000]]in
  let planned=call Producer.handle Protocol.Core "plan-policy-target"(o["request",plan_request])in
  require(at["report";"status"]planned=s "planned" && List.length(rows "selected_components"(get "report" planned))=4 &&
    at["report";"claims";"execution"]planned=s "not_performed" && at["report";"claims";"export"]planned=s "withheld")
    "Coupled planning omitted selected owners or promoted diagnostic planning into acceptance";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"(o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete partitioned quantitative material"(Check.accepted result)in
  let report=Check.report result and contextual=Check.context checked in
  let preservation=A.implementation(C.assembly contextual)in
  let bound=P.binding preservation in
  let quantitative=Quant.check ~request:original ~context:contextual ()in
  let composition=Composition.check ~request:original ~context:contextual ()in
  let summary=Quant.report quantitative in
  require(Option.is_some(Quant.accepted quantitative) && Option.is_some(Composition.accepted composition) &&
    Json.equal summary(Composition.report composition) && Json.equal summary(get "quantitative" report) &&
    Json.equal(get "table" summary)expected_table && Json.equal(get "conservation" summary)conservation &&
    get "schema_version" summary=s "biocompiler.policy_quantitative_assessment.v0.5" &&
    get "claim_scope" summary=s "exact_atomic_component_transfer_network_under_supplied_coordination_contract" &&
    get "synchronization" summary=s "one_prestate_one_atomic_commit" &&
    get "ownership" summary=s "partitioned_reservoir_storage_single_atomic_writer" &&
    get "transport_scope" summary=s "selected_boolean_allocation_signals_under_supplied_component_contracts" &&
    get "empirical" summary=s "unassessed" &&
    get "schema_version" report=s "biocompiler.policy_component_material_assessment.v0.9")
    "Fresh composition evidence changed its actual signal checks or conditional scope";
  let bindings=get "bindings" summary in
  require(List.map(text "compartment")(rows "owners" bindings)=["a";"b";"c"] &&
    List.map(text "source_state")(rows "owners" bindings)=["amount_a";"amount_b";"amount_c"] &&
    List.map(text "transfer")(rows "transfers" bindings)=edge_ids &&
    List.map(text "source_state")(rows "crossing_sites" bindings)=["q100";"q101"] &&
    List.length(B.states bound)=3 && List.length(B.transitions bound)=7 &&
    List.length(I.nodes(B.implementation bound))=49)
    "Selected distinct private owners or complete counterfactual crossing/flow census changed";
  selected_trace bound false;selected_trace bound true;
  let selected=get "quantitative" request in
  rejects "undeclared coordination premise"(fun()->Composition_contract.selection_of_json
    (set "synchronization"(s "eventual_commit")selected));
  rejects "owner coordinate permutation"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.rev(Json.array values)))selected));
  rejects "missing private owner"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.tl(Json.array values)))selected));
  rejects "aliased private store"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.map(fun row->set "state"(s "amount_a")row)(Json.array values)))selected));
  rejects "aliased component instance"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.map(fun row->set "instance"(s "control")row)(Json.array values)))selected));
  rejects "nonbinary selected reservoir"(fun()->Composition_contract.selection_of_json
    (edit["network";"mechanism";"reservoirs"](fun values->a(List.mapi(fun index row->
      if index=0 then edit["capacity";"amount"](fun _->s "2")row else row)(Json.array values)))selected));
  rejects "legacy realization route cannot own state"(fun()->
    let legacy=R.of_multi_site_json(get "implementation_request" request|>set "schema_version"(s R.multi_site_schema_version)|>set "profile"(s R.multi_site_profile))in
    RA.admit ~request:legacy ~behavior:(O.behavior_of_json(get "behavior" candidate)));
  rejects "single-owner material route cannot consume partitioned components"(fun()->M.of_json
    (request|>set "schema_version"(s M.transfer_network_schema_version)|>set "profile"(s M.transfer_network_profile)));
  rejects "zero composition checking work"(fun()->Composition.check ~maximum:0 ~request:original ~context:contextual ());
  let components=rows "components"(get "component_library" request)in
  let component instance=List.find(fun value->text "id"(get "identity" value)="coupled."^instance)components in
  let owner_local=List.hd(rows "quantitative_contracts"(get "body"(component "owner_a")))in
  rejects "empty atomic writer inventory"(fun()->Composition_contract.local_of_json(set "writes"(a[])owner_local));
  rejects "duplicate owner incident flow"(fun()->Composition_contract.local_of_json(edit["flows"]
    (fun values->let first=List.hd(Json.array values)in a[first;first])owner_local));
  let localchange label instance change=
    quantitative_failure preservation label(change_contract request instance change)candidate in
  localchange "owner next signal falsely claims the snapshot model" "owner_a"
    (edit["next";"model"](fun _->at["state";"model"]owner_local));
  localchange "owner next endpoint is old snapshot" "owner_a"(fun contract->contract
    |>edit["next";"boundary"](fun _->get "snapshot_boundary" contract)
    |>edit["next";"model"](fun _->at["state";"model"]contract));
  localchange "omitted source atomic writer" "owner_a"(edit["writes"](fun values->a(List.tl(Json.array values))));
  localchange "permuted source write lanes" "owner_b"(edit["writes"](fun values->a(List.rev(Json.array values))));
  localchange "omitted explicit edge incidence" "owner_c"(edit["flows"](fun values->a(List.tl(Json.array values))));
  localchange "permuted explicit edge incidence" "owner_a"(edit["flows"](fun values->a(List.rev(Json.array values))));
  localchange "selected initial register model mismatched" "owner_a"
    (edit["state";"model"](fun _->at["next";"model"]owner_local));
  localchange "unreachable crossing omitted" "control"(edit["network";"outputs"]
    (fun values->a(List.filter(fun row->text "source_state" row<>"q100")(Json.array values))));
  localchange "false crossing polarity" "control"(edit["network";"outputs"]
    (fun values->a(List.map(fun row->set "input"(Json.Bool false)row)(Json.array values))));
  localchange "same-node-kind actual edge ports swapped" "control"(edit["flows"](fun values->match Json.array values with
    |first::second::rest->a(set "boundary"(get "boundary" second)first::set "boundary"(get "boundary" first)second::rest)
    |_->failwith "Missing flow pair"));
  let reverse=edit["transfers"](fun values->a(List.rev(Json.array values)))in
  let wrong_law=edit["quantitative";"network";"mechanism"]reverse request in
  quantitative_failure preservation "different original reserved network" wrong_law candidate;
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" invocation in
  require(Json.equal(get "report" verified)report)"Fresh independent material service changed coupled evidence";
  let replayed=call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replayed produced)"Fresh composition replay changed complete wrapper";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  let artifact=get "artifact" exported in
  require(get "fasta" artifact=s(">rna_0001 alphabet=RNA\n"^text "sequence"(get "expected" fixture)^"\n"))
    "Four selected component roots lost exact payload sequence construction";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "assessment" manifest)report && get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Export omitted original owners, coupling, components or fresh assessment";
  let named=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  require(Json.equal(at["material_report";"quantitative"]named)summary)
    "Named refinement erased selected composition evidence";
  rejected_service "saved PASS cannot bypass checking work" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",edit["max_step_work"](fun _->Json.int 1)limits;"report",produced]);
  let saved=edit["report";"quantitative";"bindings";"owners"](fun values->a(List.rev(Json.array values)))produced in
  rejected_service "saved owner provenance permutation" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",saved]);
  let saved=edit["report";"quantitative";"synchronization"](fun _->s "physical_distributed_guarantee")produced in
  rejected_service "saved report broadens atomic coordination premise" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",saved]);
  require(!controls=25)"Coupled quantitative rejection census is incomplete";
  Printf.printf "policy_quantitative_composition: independent 24-row actual-circuit law, three private material owners, atomic reset/state invariant, four-root exact RNA, %d rejection controls\n" !controls
