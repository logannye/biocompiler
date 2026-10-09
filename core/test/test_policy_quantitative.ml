open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module Q = Bioc_domain.Policy_quantitative_contract
module K = Bioc_domain.Construction_content
module U = Bioc_domain.Policy_component_assembly_proposal
module Library = Bioc_domain.Policy_component_library
module Rule = Bioc_domain.Policy_component_assembly_rule
module Context = Bioc_domain.Policy_component_context
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
let remove key value=o(List.filter(fun(name,_)->name<>key)(Json.object_fields value))
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
let table_row source input destination request=o[
  "source",s source;"input",s input;"destination",s destination;"request",Json.Bool request]

(* This literal oracle does not call the mechanism evaluator, producer, checker,
   or fixture's table builder. The q3/True row distinguishes clamp-after-net
   production/clearance from clamp-production-before-clearance. *)
let expected_table=a[
  table_row "q0" "true" "q1" false;table_row "q0" "false" "q0" false;table_row "q0" "unknown" "q0" false;
  table_row "q1" "true" "q2" true;table_row "q1" "false" "q0" false;table_row "q1" "unknown" "q1" false;
  table_row "q2" "true" "q3" false;table_row "q2" "false" "q1" false;table_row "q2" "unknown" "q2" false;
  table_row "q3" "true" "q3" false;table_row "q3" "false" "q2" false;table_row "q3" "unknown" "q3" false]

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
      if List.for_all(fun(_,action)->action=(if reset && value.F.tick=13 then F.Reset else F.Keep))value.lifecycle
      then value else scan(count+1)rest in
  scan 0(S.choices source)
let expected_state reset tick=
  if tick=13 then if reset then "q0" else "q2"
  else if tick>=14 then if reset then "q1" else "q3"
  else List.nth["q0";"q1";"q2";"q2";"q3";"q3";"q3";"q2";"q1";"q0";"q0";"q1";"q2"]tick
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
      require(machine.state=expected && machine.binding.generation=(if reset && frame.tick>=13 then 1 else 0))
        ("Literal quantitative candidate state/generation differs at "^string_of_int frame.tick);
      let source_machine=List.find(fun row->at["binding";"encounter"]row=s slot)(rows "machines" advanced.frame)in
      require(get "state" source_machine=s expected)
        "Literal quantitative source state differs from the independent amount trajectory")["e1";"e2"];
    let new_requests=if frame.tick=2 || frame.tick=12 then 2 else 0 in
    require(List.length frame.creations=new_requests && List.length advanced.creations=new_requests)
      "Threshold crossing created missing or extra abstract effect attempts";
    created:= !created+List.length frame.creations;
    if frame.tick=3 then (
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
  require(!created=4 && text "claim"(T.report matched)="matched_prefix_only")
    "Selected quantitative trace changed request count or broadened its prefix scope"

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
let rec replace_exact original replacement value=
  if Json.equal original value then replacement else match value with
  |Json.Array values->a(List.map(replace_exact original replacement)values)
  |Json.Object fields->o(List.map(fun(key,value)->key,replace_exact original replacement value)fields)
  |_->value
let freshness_request request=
  let original_model=List.find(fun value->at["body";"primitive"]value=s "evidence_bank")
    (rows "models"(at["implementation_request";"implementation_library"]request))in
  let body=edit["configuration";"freshness_ticks"](fun _->Json.int 2)(get "body" original_model)in
  let model=original_model|>set "body" body
    |>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))
    |>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body))in
  let request=request|>replace_exact original_model model
    |>replace_exact(get "identity" original_model)(get "identity" model)
    |>edit["implementation_request";"document";"program";"declarations"](fun declarations->
      a(List.map(fun value->if text "$type" value="Observation" then
        edit["freshness";"amount"](fun _->s "2")value else value)(Json.array declarations)))in
  let request=List.fold_left(fun request component->
    let old=get "identity" component in
    let fresh=set "content_fingerprint"(s(Canonical.fingerprint(get "body" component)))old in
    replace_exact old fresh request)request(rows "components"(get "component_library" request))in
  let old=at["composition_rule";"identity"]request in
  let fresh=set "content_fingerprint"(s(Canonical.fingerprint(at["composition_rule";"body"]request)))old in
  let request=replace_exact old fresh request in
  let original=R.of_finite_machine_json(get "implementation_request" request)in
  let components=Library.of_json ~library:(R.implementation_library original)(get "component_library" request)in
  let rule=Rule.of_json ~components(get "composition_rule" request)in
  request|>edit["context";"record_layout";"union_digest"](fun _->s(Context.ordered_union_digest rule))
    |>refresh_context
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
    get "table"(Quant.report result)=a[])
    ("Quantitative semantic mutant did not fail at the quantitative checker: "^label);
  incr controls
let domain_failure request candidate limits domain expected_issue=
  let request=request|>edit["implementation_request";"operating_domain"](fun _->domain)
    |>edit["context";"record_layout";"domain_digest"](fun _->s(Canonical.fingerprint domain))
    |>refresh_context in
  let candidate=edit["implementation";"authority";"domain_digest"]
    (fun _->s(Canonical.fingerprint domain))candidate in
  let original=M.implementation_request(M.of_json request)in
  let preservation=P.check ~request:original ~behavior:(O.behavior_of_json(get "behavior" candidate))
    ~implementation:(I.of_json ~library:(R.implementation_library original)(get "implementation" candidate))
    ~proposed:(Bioc_domain.Policy_implementation_binding.of_json(get "binding" candidate))
    ~limits:(P.limits_of_json limits)in
  let checked=accepted "Fresh altered sampling domain"(P.accepted preservation)in
  let quantitative=quant_check checked request candidate in
  require(Quant.outcome quantitative=Outcome.Fail && Quant.accepted quantitative=None &&
    List.mem(s expected_issue)(rows "issues"(Quant.report quantitative)))
    "A fully preserved sampling domain evaded its independent quantitative sampling contract";
  incr controls

let () =
  require(Array.length Sys.argv=2)"Expected independent quantitative originals";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_quantitative_literals.v0.1")
    "Wrong quantitative fixture schema";
  require(Json.equal(get "table"(get "expected" fixture))expected_table)
    "Independent fixture table drifted from the handwritten native oracle";
  let request=get "request" fixture and limits=get "limits" fixture in
  let original=M.of_json request in
  require(M.is_quantitative original && M.is_finite_machine original && M.requires_prerequisite_closure original)
    "Quantitative originals lost finite source or prerequisite closure";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete quantitative material"(Check.accepted result)in
  let report=Check.report result in
  require(Json.equal report(get "report" produced) &&
    get "schema_version" report=s "biocompiler.policy_component_material_assessment.v0.5" &&
    get "quantitative_status" report=s "pass" &&
    get "all_original_obligations_discharged" report=Json.Bool true)
    "Quantitative acceptance was not conjunctive with the fresh complete material check";
  let contextual=Check.context checked in
  let assembly=C.assembly contextual in
  let preservation=A.implementation assembly in
  let bound=P.binding preservation in
  let quantum=Quant.check ~request:original ~context:contextual ()in
  require(Quant.outcome quantum=Outcome.Pass && Option.is_some(Quant.accepted quantum) &&
    Json.equal(get "table"(Quant.report quantum))expected_table)
    "Quantitative checker differs from the full independent level/input table";
  require(Json.equal(get "quantitative" report)(Quant.report quantum))
    "Material report did not retain the actual checked quantitative result";
  let summary=Quant.report quantum in
  require(at["sampling";"no_update"]summary=s "hold" &&
    at["sampling";"unknown"]summary=s "hold_without_request" &&
    at["sampling";"reset"]summary=s "initial" &&
    at["sampling";"reservation"]summary=s "existing_atomic_reservation" &&
    get "empirical" summary=s "unassessed")
    "Sample, reset, resource or empirical boundary changed";
  require(at["bindings";"crossing_transition"]summary=s "up1" &&
    at["bindings";"request_endpoint";"port"]summary=s "request0")
    "Quantitative threshold was detached from the actual selected request endpoint";
  selected_trace bound false;
  selected_trace bound true;
  let law=at["quantitative";"mechanism"]request in
  let component=List.hd(rows "components"(get "component_library" request))in
  let local=List.hd(rows "quantitative_contracts"(get "body" component))in
  List.iter(fun(label,path,value)->rejects label(fun()->Q.of_json(edit path(fun _->value)law)))
    ["float quantum",["quantum";"amount"],Json.Float 0.5;
     "nonpositive quantum",["quantum";"amount"],s "0";
     "off-grid threshold",["threshold";"amount"],s "0.75";
     "unsupported concentration unit",["unit";"dimension"],s "concentration";
     "different nominal quantity unit",["quantum";"unit";"id"],s "other_count";
     "unit conversion hidden in amount",["quantum";"unit";"scale"],s "2";
     "negative sample period",["sample_period";"amount"],s "-1"];
  rejects "omitted unconditionally required level map"(fun()->
    Q.local_of_json(edit["state";"values"](fun values->a(List.rev(List.tl(List.rev(Json.array values)))))local));
  rejects "duplicate level label"(fun()->Q.local_of_json(edit["state";"values"](fun values->
    a(List.mapi(fun index value->if index=3 then set "state"(s "q2")value else value)(Json.array values)))local));
  rejects "ordinary finite route ignores quantitative component"(fun()->M.of_json(request
    |>remove "quantitative"|>set "schema_version"(s M.finite_machine_schema_version)|>set "profile"(s M.finite_machine_profile)));
  rejects "zero quantitative checking allowance"(fun()->Quant.check ~maximum:0 ~request:original ~context:contextual ());
  let wrong_law=edit["quantitative";"mechanism";"threshold";"amount"](fun _->s "1.5")request in
  let splice=Quant.check ~request:(M.of_json wrong_law) ~context:contextual ()in
  require(Quant.outcome splice=Outcome.Fail && Quant.accepted splice=None)
    "Fresh quantitative token accepted a different original request than its context";
  incr controls;
  quantitative_failure preservation "independent source and component laws differ" wrong_law candidate;
  let both_laws=change_contract wrong_law(edit["mechanism";"threshold";"amount"](fun _->s "1.5"))in
  quantitative_failure preservation "repinned law moves crossing but actual source does not" both_laws candidate;
  let initial=edit["quantitative";"mechanism";"initial";"amount"](fun _->s "0.5")request
    |>fun raw->change_contract raw(edit["mechanism";"initial";"amount"](fun _->s "0.5"))in
  quantitative_failure preservation "repinned initial amount differs from actual reset state" initial candidate;
  let period=edit["quantitative";"mechanism";"sample_period";"amount"](fun _->s "2")request
    |>fun raw->change_contract raw(edit["mechanism";"sample_period";"amount"](fun _->s "2"))in
  quantitative_failure preservation "repinned sample clock differs from original clock" period candidate;
  let relabel=change_contract request(edit["state";"values"](fun values->
    a(List.map(fun value->match text "state" value with
      |"q2"->set "state"(s "q3")value|"q3"->set "state"(s "q2")value|_->value)(Json.array values))))in
  quantitative_failure preservation "repinned complete map assigns wrong amounts to states" relabel candidate;
  quantitative_failure preservation "selected source identity" (edit["quantitative";"source";"machine"](fun _->s "other_machine")request)candidate;
  quantitative_failure preservation "selected component node identity" (change_contract request
    (edit["state";"node"](fun _->s "other_machine")))candidate;
  quantitative_failure preservation "selected component full model pin" (change_contract request
    (edit["state";"model"](fun _->at["input";"model"]local)))candidate;
  quantitative_failure preservation "selected input port identity" (change_contract request
    (edit["input";"updated_port"](fun _->s "value")))candidate;
  quantitative_failure preservation "selected request boundary identity" (change_contract request
    (edit["output";"boundary"](fun _->s "response.authorization")))candidate;
  quantitative_failure preservation "selected crossing commit model identity" (change_contract request
    (edit["output";"model"](fun _->at["state";"model"]local)))candidate;
  (* A stale Missing row preserves this fixture's Unknown behavior. Recheck the
     complete altered domain independently, then require quantitative sampling
     failure rather than accepting a semantically harmless age violation. *)
  let aged_domain=edit["fixed_observations"](fun values->a(List.map(fun value->
    if get "available_tick" value=Json.int 3 && get "slot" value=s "e1"
    then set "observed_tick"(Json.int 2)value else value)(Json.array values)))
    (at["implementation_request";"operating_domain"]request)in
  domain_failure request candidate limits aged_domain "fixed_sample_complete_identity_and_zero_age";
  let domain=at["implementation_request";"operating_domain"]request in
  rejects "duplicate original input coordinate"(fun()->F.of_json(edit["fixed_observations"]
    (fun values->a(List.hd(Json.array values)::Json.array values))domain));
  let factor=o["observation",s "condition";"slots",a[s "e1"];"ticks",a[Json.int 6];
    "age_ticks",a[Json.int 0];"max_rows_per_slot_tick",Json.int 2;
    "alphabet",s "known_truth_and_evidence_status.v1"]in
  rejects "fixed and factored sample coordinates overlap"(fun()->F.of_json(set "observation_factors"
    (a[set "ticks"(a[Json.int 5])factor])domain));
  domain_failure request candidate limits(set "observation_factors"(a[factor])domain)
    "factored_sample_complete_identity_and_zero_age";
  let wide_freshness=freshness_request request in
  let widened=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",wide_freshness;"limits",limits])in
  require(at["report";"status"]widened=s "not_accepted" &&
    at["report";"preservation";"status"]widened=s "checked_implementation" &&
    at["report";"assembly_status"]widened=s "pass" && at["report";"context_status"]widened=s "pass" &&
    List.mem(s "one_tick_fresh_truth_observation")(rows "issues"(at["report";"quantitative"]widened)))
    "Freshly repinned two-tick source/model freshness failed to reach quantitative rejection";
  incr controls;
  (* The full root must withhold acceptance even though unchanged source
     preservation, assembly and context all still pass under freshly repinned
     component authority. A quantitative PASS sidecar cannot replace this step. *)
  let _,bad=Material.fresh_check ~request:both_laws ~candidate:(candidate_for both_laws candidate) ~limits in
  require(Check.accepted bad=None && at["quantitative";"outcome"](Check.report bad)=s "fail" &&
    get "status"(Check.report bad)=s "not_accepted" &&
    get "all_original_obligations_discharged"(Check.report bad)=Json.Bool false)
    "A quantitative contradiction reached a complete material capability";
  incr controls;
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let replayed=call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replayed produced)"Fresh quantitative material replay changed the complete wrapper";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  let artifact=get "artifact" exported and expected=get "expected" fixture in
  require(Json.equal(at["construction";"inventory";"molecules"]candidate)(a[get "molecule" expected]) &&
    get "fasta" artifact=s(">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n"))
    "Quantitative proof lost exact independently supplied molecule/FASTA identity";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Quantitative export omitted its complete independent originals or fresh assessment";
  let named=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  let complete=List.find(fun row->text "kind" row="complete_material_check")
    (rows "premises"(get "evidence" named))in
  require(get "fingerprint" complete=s(Canonical.fingerprint report) &&
    Json.equal(at["material_report";"quantitative"]named)summary)
    "Named refinement erased the freshly checked quantitative material premise";
  let tampered=edit["candidate";"construction";"inventory";"molecules"](fun values->
    a(List.map(fun value->set "sequence"(s("A"^String.sub(text "sequence" value)1(String.length(text "sequence" value)-1)))value)
      (Json.array values)))invocation in
  rejected_service "exact RNA mutation" "export-policy-component-material" tampered;
  let incomplete=call Service.handle Protocol.Verify "check-policy-component-material"
    (edit["limits";"max_step_work"](fun _->Json.int 1)invocation)in
  require(get "artifact" incomplete=Json.Null && at["report";"status"]incomplete=s "not_accepted" &&
    at["report";"quantitative"]incomplete=Json.Null && at["report";"quantitative_status"]incomplete=s "unassessed")
    "Incomplete original-domain evidence minted quantitative material acceptance";
  incr controls;
  rejected_service "saved PASS cannot replace incomplete fresh checking" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",edit["max_step_work"](fun _->Json.int 1)limits;
      "report",produced]);
  require(!controls>=32)"Quantitative semantic rejection census is incomplete";
  Printf.printf "policy_quantitative: exact 12-row law, two sampled/reset traces, complete original material/export, %d rejection controls\n" !controls
