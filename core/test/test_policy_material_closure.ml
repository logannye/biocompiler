open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module R=Bioc_domain.Policy_material_request
module Q=Bioc_domain.Policy_realization_request
module D=Bioc_domain.Policy_document
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
let set key value raw=
  require(List.mem_assoc key(Json.object_fields raw))("Absent mutation key "^key);
  obj(List.map(fun(name,original)->name,if name=key then value else original)(Json.object_fields raw))
let add key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec put path replacement raw=match path with []->replacement|key::rest->match raw with
  |Json.Array values->let index=int_of_string key in
      require(index>=0 && index<List.length values)"Mutation escaped original array";
      arr(List.mapi(fun i value->if i=index then put rest replacement value else value)values)
  |_->set key(put rest replacement(get key raw))raw
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let run handler role operation payload=
  let request:Protocol.request={request_id="material-closure-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered closure operation failed: "^operation)
let roles=[Protocol.Core,Producer.handle;Protocol.Verify,Service.handle]
let rejects label code action=match action()with
  |_->failwith("Accepted closure negative control: "^label)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)(label^": wrong diagnostic "^diagnostic.code)
let requirements request=List.filter(fun row->text "$type" row="Requirement")
  (Json.array(at["implementation_request";"document";"program";"declarations"]request))
let requirement_paths request=
  let rec expressions path=function
    |Json.Object fields->(if List.assoc_opt "$type" fields=Some(str "Expr")then[path]else[])@
        List.concat_map(fun(key,value)->expressions(path^"/"^key)value)fields
    |Json.Array values->List.concat(List.mapi(fun index value->expressions(path^"/"^string_of_int index)value)values)
    |_->[]in
  List.concat(List.mapi(fun index row->if text "$type" row<>"Requirement"then[]else
    let path="/document/program/declarations/"^string_of_int index in path::expressions path row)
    (Json.array(at["implementation_request";"document";"program";"declarations"]request)))
  |>List.sort String.compare
let census = function
  |"one_rule"->[1;1;9;9;9],9,29,30,9
  |"aged_evidence"->[1;1;1;16;16;16;16],16,67,68,15
  |"ordered_multiplicity"->[1;1;1;31;31;31;31],31,127,128,15
  |_->failwith "Unreviewed closure family"
let witness_ids = function
  |"one_rule"->["mixed_feedback";"quiet_timeouts"]
  |"aged_evidence"->["silence";"newer_true";"tied_false";"tied_true_conflicts";"older_true_ignored"]
  |"ordered_multiplicity"->["silence";"double_true";"false_then_true";"true_then_false";"double_false";
      "missing_then_invalid";"double_missing"]
  |_->failwith "Unreviewed closure trace family"
let original_literals case=
  let request=get "request" case and expected=get "expected" case in
  let widths,histories,transitions,prefixes,nodes=census(text "id" case)in
  require(3*3=9 && 1+5*3=16 && 1+5+5*5=31)"Independent finite alphabet census changed";
  require(List.map integer(items "prefixes_after_tick" expected)=widths &&
    number "histories" expected=histories && number "transitions" expected=transitions &&
    number "prefixes_started" expected=prefixes && List.fold_left(+)0 widths=transitions &&
    prefixes=transitions+1 && number "node_count" expected=nodes)"Literal closure census differs";
  List.iter(fun(key,path)->require(text key expected=Canonical.fingerprint(at path request))
    ("Original closure authority differs: "^key))[
    "request_fingerprint",[];"source_request_digest",["implementation_request"];
    "source_artifact_digest",["implementation_request";"document"];
    "definitions_digest",["implementation_request";"definitions"];
    "domain_digest",["implementation_request";"operating_domain"];
    "library_digest",["implementation_request";"implementation_library"];
    "material_contract_digest",["material_contract"];"kernel_digest",["material_contract";"body";"kernel"];
    "carrier_digest",["material_contract";"body";"carriers"];"context_digest",["context"]];
  let source=Bioc_checker.Policy_check.check(Q.document(R.implementation_request(R.of_json request)))in
  require(text "status" source="valid" && items "unresolved_obligations" source=items "obligations" expected)
    "Closure source is invalid or omits original obligations";
  require(Json.equal(arr(requirements request))(get "requirements" expected) &&
    List.length(requirements request)=(if text "id" case="one_rule"then 4 else 3))
    "Closure source changed its complete hard-requirement inventory";
  require(List.length(Json.array(at["material_contract";"body";"carriers"]request))=number "carrier_count" expected)
    "Closure source lost a supplied material carrier"
let compile_check_replay request limits=
  let compiled=run Producer.handle Protocol.Core "compile-policy-material"(obj["request",request;"limits",limits])in
  let candidate=get "candidate" compiled and report=get "report" compiled in
  let payload=obj["request",request;"candidate",candidate;"limits",limits]in
  List.iter(fun(role,handler)->
    require(Json.equal compiled(run handler role "check-policy-material"payload))"Fresh Core/Verify check differs from generic production";
    require(Json.equal compiled(run handler role "replay-policy-material"(add "report" compiled payload)))
      "Full-wrapper replay differs from fresh original-input checking")roles;
  require(get "artifact" compiled=Json.Null &&
    text "request_fingerprint" compiled=Canonical.fingerprint request &&
    text "candidate_fingerprint" compiled=Canonical.fingerprint candidate &&
    text "invocation_fingerprint" compiled=Canonical.fingerprint payload &&
    text "report_fingerprint" compiled=Canonical.fingerprint report)"Complete public wrapper lost original authority or evidence pins";
  require(Json.equal(at["behavior";"source_document"]candidate)(at["implementation_request";"document"]request))
    "Generic producer changed the separately supplied complete original document";
  let obligations=List.filter(fun row->text "role" row="requirement")
    (items "occurrences"(get "implementation" candidate))in
  require(List.map(text "source_path")obligations=requirement_paths request &&
    List.for_all(fun row->text "disposition" row="obligation" && items "targets" row=[])obligations)
    "Fresh generic lowering omitted or promoted an original requirement expression occurrence";
  compiled,payload
let assessment_literals expected compiled=
  let report=get "report" compiled and candidate=get "candidate" compiled in
  if text "status" report<>"checked_material"then
    failwith("Complete closure authority was not accepted: "^Canonical.encode report);
  List.iter(fun key->require(get key report=get key expected)
    ("Closure claim changed: "^key^(if key="status" then "; complete fresh report: "^Canonical.encode report else "")))
    ["status";"claim_scope";"material_status";"context_status";"empirical";"artifact";"export"];
  require(get "all_original_obligations_discharged" report=Json.Bool true &&
    List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
    List.for_all(fun row->text "status" row="discharged" && get "evidence" row<>Json.Null)(items "obligations" report))
    "Closure accepted without discharging every original obligation";
  let preservation=get "preservation" report in
  require(text "status" preservation="checked_implementation" && text "preservation" preservation="pass" &&
    at["coverage";"complete"]preservation=Json.Bool true && at["program_coverage";"nonvacuous"]preservation=Json.Bool true)
    "Closure accepted an incomplete, failing or vacuous domain";
  List.iter(fun key->require(at["coverage";key]preservation=get key expected)("Closure domain census differs: "^key))
    ["histories";"transitions";"prefixes_started"];
  require(at["coverage";"matched_prefixes"]preservation=get "prefixes_started" expected)
    "Closure omitted a permitted prefix from correspondence";
  let rows=items "requirements" preservation in
  require(Json.equal(arr(List.map(get "source")rows))(get "requirements" expected))"Closure monitor dropped or changed a hard requirement";
  List.iter(fun row->require(text "status" row="pass" && get "nonvacuous" row=Json.Bool true &&
    at["histories";"pass"]row=get "histories" expected &&
    List.for_all(fun key->at["histories";key]row=Json.int 0)["fail";"unknown";"unsupported";"not_exercised"])
    "A closure hard requirement was unproved or unexercised")rows;
  let context=get "context" report in
  require(List.map(get "id")(items "discharges" context)=items "context_discharges" expected)
    "Closure context changed its independently justified discharges";
  let resources rows=arr(List.sort(fun a b->String.compare(Canonical.encode a)(Canonical.encode b))
    (List.map(fun row->obj(List.map(fun key->key,get key row)["owner";"unit";"scope";"quantity"]))rows))in
  require(Json.equal(resources(items "derived_demands" context))(resources(items "resource_demands" expected)))
    "Closure resource demand inventory differs from independent literals";
  List.iter(fun key->require(at["record_layout";key]context=get key expected)("Closure record layout differs: "^key))
    ["horizon_ticks";"maximum_tick";"ordered_cause_slots";"ordered_reason_slots";"identifier_bytes"];
  let queue=List.filter(fun row->text "unit" row="control_event_records")(items "derived_demands" context)in
  require(match queue with [row]->get "quantity" row=get "queue_records" expected|_->false)
    "Closure omitted the complete literal control queue allowance";
  require(List.length(items "nodes"(get "implementation" candidate))=number "node_count" expected)
    "Generic producer changed the supplied primitive inventory";
  require(List.length(items "wires"(get "implementation" candidate))=number "wire_count" expected)
    "Generic producer changed the complete supplied wire inventory"
let publication_literals request candidate limits expected report export=
  require(Json.equal(get "report" export)report)"Fresh export changed the complete assessment";
  let artifact=get "artifact" export in
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  require(fasta=">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n" &&
    text "sequence" expected="CCAUGGCUUAAGGAAAA")"Closure changed exact RNA bases, order or FASTA newlines";
  require(text "fasta_sha256" artifact=Canonical.sha256 fasta && text "fasta_sha256" manifest=Canonical.sha256 fasta &&
    text "manifest_sha256" artifact=Canonical.sha256(Canonical.encode manifest))"Paired publication lost exact byte identities";
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report)
    "Closure manifest lost original authority or complete fresh evidence";
  let bindings=get "bindings" manifest in
  require(text "request_fingerprint" bindings=Canonical.fingerprint request &&
    text "candidate_fingerprint" bindings=Canonical.fingerprint candidate &&
    text "invocation_fingerprint" bindings=Canonical.fingerprint(obj["request",request;"candidate",candidate;"limits",limits]) &&
    text "assessment_fingerprint" bindings=Canonical.fingerprint report)"Closure manifest pins differ from its complete original pair";
  require(Json.equal(arr(List.map(get "molecule")(items "members" manifest)))(get "molecules" expected))
    "Closure manifest changed chemistry, products, coordinates or derivation";
  require(text "claim_scope" manifest="bounded_conditional_policy_to_exact_mrna" && text "empirical" manifest="unassessed" &&
    text "original_authority" manifest="retain_original_inputs_separately")"Closure export widened its conditional claim"
let truth_name=function I.True->"true"|I.False->"false"|I.Unknown->"unknown"
let reason_name=function P.Missing->"missing"|P.Stale->"stale"|P.Invalid->"invalid"|P.Conflicting->"conflicting"
let optional_int=Option.fold ~none:Json.Null ~some:Json.int
let status_name=function P.Active->"active"|P.Completed->"completed"|P.Failed->"failed"|P.Timed_out->"timed_out"
  |P.Reset_invalidated->"encounter_reset"|P.End_invalidated->"encounter_ended"
let attempt_literal(value:P.attempt)=obj[
  "creation_ordinal",Json.int value.ordinal;"slot",Option.fold ~none:Json.Null ~some:str value.binding.slot;
  "target",str value.subject;"generation",Json.int value.binding.generation;
  "started_tick",Json.int value.started_tick;"deadline_tick",Json.int value.deadline_tick;
  "ended_tick",optional_int value.ended_tick;"status",str(status_name value.status)]
let evidence row=match text "status" row with
  |"valid"->F.Known(Json.boolean(get "value" row))|"missing"->F.Missing|"invalid"->F.Invalid
  |"conflicting"->F.Conflicting|_->failwith "Unknown literal observation evidence"
let select (domain:F.t) witness source=
  require(items "lifecycle" witness=[])"Closure literals may not silently add lifecycle assumptions";
  let matches(batch:F.input_batch)=
    let observations=List.filter(fun(row:F.observation_input)->row.available_tick=batch.tick)domain.fixed_observations @
      List.filter_map(fun row->if number "tick" row<>batch.tick then None else
        Some({F.slot=text "slot" row;observation="condition";available_tick=batch.tick;
          observed_tick=number "observed_tick" row;evidence=evidence row}:F.observation_input))(items "observations" witness)in
    let feedback=match List.find_opt(fun row->number "tick" row=batch.tick)(items "feedback" witness)with
      |None->[]|Some row->List.map(fun item->number "creation_ordinal" item,
          match text "outcome" item with "completed"->F.Completed|"failed"->F.Failed|_->failwith "Unknown literal feedback")
          (items "rows" row)in
    List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle && batch.observations=observations &&
    List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=feedback in
  match List.filter matches(List.of_seq(S.choices source))with
  |[batch]->batch|_->failwith "Closure history is absent or ambiguous in the original causal grammar"
let snapshots bound witness (frame:P.frame)=
  let observation=match B.observations bound with [value]->value|_->failwith "Closure observation inventory changed"in
  List.iter(fun expected->if number "tick" expected=frame.tick then(
    let values=List.filter(fun(value:P.evidence_snapshot)->value.bank=observation.bank &&
      value.binding.slot=Some(text "slot" expected))frame.evidence in
    let value=match values with [value]->value|_->failwith "Missing or duplicate settled evidence snapshot"in
    let actual=obj["tick",Json.int frame.tick;"slot",get "slot" expected;
      "observed_tick",optional_int value.observed_tick;"available_tick",optional_int value.available_tick;
      "occurrence_ids",arr(List.map str value.occurrences);"defined",Json.Bool(Option.is_some value.signal.value);
      "value",Option.fold ~none:Json.Null ~some:(fun truth->str(truth_name truth))value.signal.value;
      "reasons",arr(List.map(fun reason->str(reason_name reason))value.signal.reasons)]in
    require(Json.equal actual expected)"Age/merge/expiry changed literal retained evidence or ordered occurrence identity"))
    (items "evidence_snapshots" witness);
  List.iter(fun expected->if number "tick" expected=frame.tick then(
    let state=List.find(fun(value:B.state)->value.source=text "source" expected)(B.states bound)in
    let values=List.filter(fun(value:P.port_value)->value.endpoint.node_id=state.register && value.endpoint.port_id="value" &&
      value.binding.slot=Some(text "slot" expected))frame.outputs in
    let truth=match values with [{P.signal=P.Truth{value=Some value;reasons=[]};_}]->value
      |_->failwith "Missing, uncertain or duplicate settled state snapshot"in
    require(Json.equal(obj["tick",Json.int frame.tick;"slot",get "slot" expected;"source",str state.source;
      "value",str(truth_name truth)])expected)"Closure literal scoped state differs"))
    (items "state_snapshots" witness);
  let batches=List.filter_map(fun(action:P.action)->match action.detail with
    |P.Observation_batch{bank;binding;input_ids;retained_ids;evidence;observed_tick}->
        require(bank=observation.bank)"Observation action has another independently bound bank";
        Some(obj["tick",Json.int frame.tick;"slot",Option.fold ~none:Json.Null ~some:str binding.slot;
          "input_ids",arr(List.map str input_ids);"retained_ids",arr(List.map str retained_ids);
          "observed_tick",Json.int observed_tick;"status",str(match evidence with P.Known _->"valid"
            |P.Missing_evidence->"missing"|P.Invalid_evidence->"invalid"|P.Conflicting_evidence->"conflicting")])
    |_->None)frame.actions in
  List.iter(fun expected->if number "tick" expected=frame.tick then
    require(match List.filter(fun row->get "slot" row=get "slot" expected)batches with
      |[actual]->Json.equal actual expected|_->false)
      "Ordered observation merge changed complete input/retained occurrence lists")
    (items "observation_batches" witness)
let run_history request candidate limits witness=
  let original=R.implementation_request(R.of_json request)in
  let behavior=O.behavior_of_json(get "behavior" candidate)in
  let admitted=A.admit ~request:original ~behavior in
  let bound=B.check ~admitted ~implementation:(I.of_json ~library:(Q.implementation_library original)
    (get "implementation" candidate)) ~proposed:(U.of_json(get "binding" candidate))in
  let environment=B.environment bound and runtime_limits=get "candidate" limits in
  let domain=Q.operating_domain original in
  require(List.length(items "creations_by_tick" witness)=domain.horizon_ticks+1)"Literal creation history does not cover the inclusive horizon";
  List.iter(fun key->let rows=items key witness in
    require(List.for_all(fun row->number "tick" row>=0 && number "tick" row<=domain.horizon_ticks)rows &&
      List.length(List.sort_uniq String.compare(List.map Canonical.encode rows))=List.length rows)
      "Literal snapshot inventory contains an unreachable tick or duplicate")
    ["evidence_snapshots";"state_snapshots";"observation_batches"];
  let runtime=P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=number "max_work" runtime_limits;max_events=number "max_events" runtime_limits;
      max_attempts=number "max_attempts" runtime_limits;max_microsteps=number "max_microsteps" runtime_limits}in
  let source=S.create ~behavior ~domain ~bounds:(S.execution_bounds_of_json(get "source" limits))in
  let observations=ref[] and feedback=ref[] and accepted=ref[] and rejected=ref[] and final=ref None in
  let rec loop source runtime correspondence=
    if not(S.finished source)then(
      let batch=select domain witness source in
      let input=T.input correspondence batch in
      let ids kind count=List.init count(fun index->"domain/"^kind^"/"^string_of_int batch.tick^"/"^string_of_int index)in
      let observed=List.map(fun(row:P.observation)->row.observation_id)input.observations
      and delivered=List.map(fun(row:P.feedback)->row.feedback_id)input.feedback in
      require(observed=ids "observation"(List.length batch.observations) && delivered=ids "feedback"(List.length batch.feedback))
        "Closure adapter changed ordered occurrence identity";
      observations:= !observations@observed;feedback:= !feedback@delivered;
      let runtime,frame=P.step runtime input in
      let advanced=match S.step source batch with S.Advanced value->value
        |S.Stopped value->failwith("Closure literal source stopped: "^value.diagnostic.code)in
      require(List.map(text "id")(items "observations" advanced.receipt.timeline)= !observations &&
        List.map(text "id")(items "feedback" advanced.receipt.timeline)= !feedback)
        "Source adapter lost ordered input occurrence history";
      require(List.length frame.creations=integer(List.nth(items "creations_by_tick" witness)batch.tick))
        "Closure tick lost or invented an effect creation";
      snapshots bound witness frame;
      let ordinal identity=(List.find(fun(attempt:P.attempt)->attempt.attempt_id=identity)frame.attempts).ordinal in
      List.iter(fun(action:P.action)->match action.detail with
        |P.Feedback_accepted(_,identity)->accepted:= !accepted@[obj["tick",Json.int batch.tick;"creation_ordinal",Json.int(ordinal identity)]]
        |P.Feedback_rejected(_,identity,reason)->rejected:= !rejected@[obj["tick",Json.int batch.tick;
            "creation_ordinal",Json.int(ordinal identity);"reason",str reason]]
        |_->())frame.actions;
      let execution=match advanced.receipt.execution with Some value->value|None->failwith "Missing fresh closure source replay"in
      let correspondence=T.advance correspondence ~batch ~source_frame:advanced.frame ~source_attempts:(items "attempts" execution)
        ~source_creations:advanced.creations ~candidate:frame in
      List.iter(fun(attempt:P.attempt)->require(attempt.executor="cell-1" && attempt.product="fixture.product.alpha" &&
        T.candidate_attempt_to_source correspondence attempt.attempt_id="attempt/"^string_of_int attempt.ordinal)
        "Closure attempt changed executor/product or creation-time identity")frame.attempts;
      final:=Some frame;loop advanced.next runtime correspondence)in
  loop source runtime(T.create bound);
  let frame=match !final with Some value->value|None->failwith "Missing inclusive closure frames"in
  require(frame.tick=domain.horizon_ticks && Json.equal(arr(List.map attempt_literal frame.attempts))(get "final_attempts" witness))
    ("Literal closure final attempt ledger changed: "^text "id" witness);
  require(Json.equal(arr !accepted)(get "feedback_acceptances" witness) && Json.equal(arr !rejected)(get "feedback_rejections" witness))
    "Closure feedback changed its exact attempt correlation"
let requirement_controls case limits baseline=
  let original=get "request" case and expected=get "expected" case in
  let declarations=Json.array(at["implementation_request";"document";"program";"declarations"]original)in
  let index=List.find_index(fun row->text "id" row="request_progress")declarations|>Option.get in
  let requirement=List.nth declarations index in
  let operation=List.find(fun row->text "$type" row="Effect")declarations in
  let path=["implementation_request";"document";"program";"declarations";string_of_int index]in
  List.iter(fun(field,value)->
    let request=put(path@[field])value original in
    (* Structural source validity is required before public compilation. No
       stale candidate or expected-error catch can stand in for this boundary. *)
    let decoded=R.of_json request in
    let source=Bioc_checker.Policy_check.check(Q.document(R.implementation_request decoded))in
    require(text "status" source="valid" && items "unresolved_obligations" source=items "obligations" expected)
      ("Requirement "^field^" mutation is source-invalid or changed the original hard-obligation inventory");
    let compiled,payload=compile_check_replay request limits in
    let report=get "report" compiled and candidate=get "candidate" compiled in
    List.iter(fun key->require(get key compiled<>get key baseline)("Requirement edit retained stale "^key))
      ["request_fingerprint";"candidate_fingerprint";"invocation_fingerprint";"report_fingerprint"];
    require(at["implementation";"authority";"source_artifact_digest"]candidate=
      str(D.artifact_digest(Q.document(R.implementation_request decoded))))
      "Generic requirement lowering reused a stale source-artifact pin";
    let preservation=get "preservation" report in
    require(text "status" report="not_accepted" && text "material_status" report="unassessed" &&
      text "context_status" report="unassessed" && get "all_original_obligations_discharged" report=Json.Bool false &&
      text "status" preservation="requirements_not_satisfied" && text "preservation" preservation="pass" &&
      at["coverage";"complete"]preservation=Json.Bool true && get "stopped" preservation=Json.Null)
      "Unsupported requirement became accepted or failed at an unrelated boundary";
    List.iter(fun key->require(at["coverage";key]preservation=get key expected)("Requirement edit changed complete domain census "^key))
      ["histories";"transitions";"prefixes_started"];
    let rows=items "requirements" preservation in
    require(Json.equal(arr(List.map(get "source")rows))(arr(requirements request)))
      "Unsupported requirement was omitted or rewritten";
    List.iter(fun row->if text "id" row="request_progress"then(
      require(text "status" row="unsupported" && at["histories";"unsupported"]row=get "histories" expected &&
        List.for_all(fun key->at["histories";key]row=Json.int 0)["pass";"fail";"unknown";"not_exercised"])
        "Unsupported requirement was assessed as passing, failing or merely unexercised";
      let witness=at["witnesses";"unsupported";"requirement"]row in
      require(text "unsupported_reason" witness="unsupported_requirement_fields" &&
        Json.equal(get "source" witness)(set field value requirement))"Exact unsupported field or original source was lost")
      else require(text "status" row="pass")"Unsupported requirement hid another hard-property failure")rows;
    require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
      List.for_all(fun row->text "status" row="unresolved" && get "evidence" row=Json.Null)(items "obligations" report))
      "Failed conjunction dropped or discharged an original obligation";
    require(text "artifact" report="withheld" && text "export" report="withheld" && get "artifact" compiled=Json.Null)
      "Unsupported requirement published material";
    List.iter(fun(role,handler)->rejects("requirement "^field^" export")"policy_material_export_not_accepted"
      (fun()->run handler role "export-policy-material"payload))roles)
    ["lower",get "deadline" requirement;"upper",get "deadline" requirement;"contract",get "contract" operation]
let nonzero_start_control request limits compiled=
  let changed=put["implementation_request";"operating_domain";"encounters";"0";"start_tick"](Json.int 1)request in
  let candidate=get "candidate" compiled in
  let check action=match action()with
    |_->failwith "Public decoder accepted nonzero encounter start"
    |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_domain_unsupported" && diagnostic.path=None &&
        diagnostic.message="This profile creates fixed encounter slots at tick zero.")
        "Nonzero encounter start failed on stale candidate authority instead of its explicit decoder boundary"in
  check(fun()->run Producer.handle Protocol.Core "compile-policy-material"(obj["request",changed;"limits",limits]));
  List.iter(fun(role,handler)->List.iter(fun operation->check(fun()->run handler role operation
      (obj["request",changed;"candidate",candidate;"limits",limits])))
      ["check-policy-material";"export-policy-material"])roles
let requirement_alternative_controls case limits baseline=
  let original=get "request" case and expected=get "expected" case in
  let declarations=Json.array(at["implementation_request";"document";"program";"declarations"]original)in
  let declaration identity=List.find(fun row->text "id" row=identity)declarations in
  let path identity=["implementation_request";"document";"program";"declarations";
    string_of_int(Option.get(List.find_index(fun row->text "id" row=identity)declarations))]in
  let edit identity suffix value request=put(path identity@suffix)value request in
  let truth=get "condition"(declaration "request_progress")in
  let falsehood=set "value"(Json.Bool false)truth in
  let equality left right=truth|>set "op"(str "eq")|>set "value" Json.Null|>set "args"(arr[left;right])in
  let text_literal=truth|>set "value_type"(set "kind"(str "text")(get "value_type" truth))
    |>set "value"(str "same product label")in
  let scope=obj["$type",str "Scope";"kind",str "executor";
    "subject",obj["$type",str "Ref";"kind",str "Role";"id",str "executor"]]in
  let completion=get "response"(declaration "initiation_progress")|>set "value"(str "completed")in
  let cases=[
    "executor_reads_encounter","scoped_memory","unsupported",Some "scope_requires_encounter",
      edit "scoped_memory"["scope"]scope original;
    "text_literal_equality","scoped_memory","unsupported",Some "unsupported_literal_type",
      edit "scoped_memory"["condition"](equality text_literal text_literal)original;
    "truth_equality","scoped_memory","pass",None,
      edit "scoped_memory"["condition"](equality truth truth)original;
    "false_truth_equality","scoped_memory","fail",None,
      edit "scoped_memory"["condition"](equality truth falsehood)original;
    "pending_completion","request_authorization","unknown",None,
      (original|>edit "request_authorization"["response"]completion
        |>edit "request_authorization"["deadline";"amount"](str "8"))
  ]in
  List.iter(fun(label,identity,status,unsupported,request)->
    let decoded=R.of_json request in
    let source=Bioc_checker.Policy_check.check(Q.document(R.implementation_request decoded))in
    require(text "status" source="valid" && items "unresolved_obligations" source=items "obligations" expected)
      (label^": requirement alternative must reach checking with the complete valid original source");
    let compiled,payload=compile_check_replay request limits in
    List.iter(fun key->require(get key compiled<>get key baseline)(label^": stale "^key))
      ["request_fingerprint";"candidate_fingerprint";"invocation_fingerprint";"report_fingerprint"];
    let report=get "report" compiled in
    let preservation=get "preservation" report in
    require(text "preservation" preservation="pass" && at["coverage";"complete"]preservation=Json.Bool true &&
      get "stopped" preservation=Json.Null)
      (label^": requirement alternative failed outside the fully explored requirement boundary: "^Canonical.encode report);
    List.iter(fun key->require(at["coverage";key]preservation=get key expected)(label^": changed domain census "^key))
      ["histories";"transitions";"prefixes_started"];
    let rows=items "requirements" preservation in
    require(Json.equal(arr(List.map(get "source")rows))(arr(requirements request)))
      (label^": a requirement alternative omitted original hard obligations");
    List.iter(fun row->if text "id" row<>identity then require(text "status" row="pass")
      (label^": another unchanged requirement did not pass")else(
      require(text "status" row=status)(label^": exact requirement outcome changed");
      let count key=number key(get "histories" row)in
      List.iter(fun key->require(count key=(if key=status then (if status="unknown"then 8 else 9)
          else if status="unknown" && key="pass"then 1 else 0))
        (label^": complete requirement-outcome census differs: "^key))
        ["pass";"fail";"unknown";"unsupported";"not_exercised"];
      let witness=at["witnesses";status;"requirement"]row in
      require(get "unsupported_reason" witness=Option.fold ~none:Json.Null ~some:str unsupported)
        (label^": requirement reason changed");
      if status="unknown"then(
        let obligations=items "obligations" witness in
        require(List.length obligations=2 && List.for_all(fun obligation->
          text "status" obligation="unknown" && text "reason" obligation="pending_horizon" &&
          get "opened_tick" obligation=Json.int 1 && text "deadline_tick" obligation="9" &&
          get "closed_tick" obligation=Json.Null && get "response_unknown" obligation=Json.Bool false)obligations)
          "Beyond-horizon completion must retain both unanswered correlated obligations")))rows;
    if status="pass"then(
      let expected=set "requirements"(arr(requirements request))expected in
      assessment_literals expected compiled;
      List.iter(fun(role,handler)->let exported=run handler role "export-policy-material"payload in
        publication_literals request(get "candidate" compiled)limits expected report exported)roles)
    else(
      require(text "status" report="not_accepted" && text "status" preservation="requirements_not_satisfied" &&
        text "material_status" report="unassessed" && text "context_status" report="unassessed" &&
        get "all_original_obligations_discharged" report=Json.Bool false && get "artifact" compiled=Json.Null &&
        text "artifact" report="withheld" && text "export" report="withheld")
        (label^": failed, unknown or unsupported requirement became accepted material");
      require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
        List.for_all(fun row->text "status" row="unresolved" && get "evidence" row=Json.Null)(items "obligations" report))
        (label^": incomplete conjunction discharged or dropped an original obligation");
      List.iter(fun(role,handler)->rejects(label^" export")"policy_material_export_not_accepted"
        (fun()->run handler role "export-policy-material"payload))roles))cases;
  (* Structurally valid fractional time is excluded by operational admission,
     before a candidate monitor can interpret it. Assert that exact boundary. *)
  let request=edit "request_progress"["deadline";"amount"](str "0.5")original in
  let decoded=R.of_json request in
  let source=Bioc_checker.Policy_check.check(Q.document(R.implementation_request decoded))in
  require(text "status" source="valid" && items "unresolved_obligations" source=items "obligations" expected)
    "Fractional requirement deadline was rejected by structural source checking";
  let expected_path="/"^String.concat "/"(List.tl(path "request_progress")@["deadline"])in
  let reject_fractional action=match action()with
    |_->failwith "Public material route admitted an unaligned operational requirement deadline"
    |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_operational_unsupported" &&
        diagnostic.path=Some expected_path && diagnostic.message=
        "Operational durations must be positive integral multiples of the shared clock resolution.")
        "Fractional deadline failed outside its explicit operational admission boundary"in
  reject_fractional(fun()->run Producer.handle Protocol.Core "compile-policy-material"
    (obj["request",request;"limits",limits]));
  List.iter(fun(role,handler)->List.iter(fun operation->reject_fractional(fun()->run handler role operation
      (obj["request",request;"candidate",get "candidate" baseline;"limits",limits])))
      ["check-policy-material";"export-policy-material"])roles
let ()=
  require(Array.length Sys.argv=2)"Supply independently authored complete closure fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_material_closure_literals.v0.1")"Unknown closure fixture schema";
  let cases=items "cases" fixture and limits=get "limits" fixture in
  require(List.map(text "id")cases=["one_rule";"aged_evidence";"ordered_multiplicity"])
    "Closure witness family inventory changed";
  let results=List.map(fun case->
    original_literals case;
    let request=get "request" case and expected=get "expected" case in
    let compiled,payload=compile_check_replay request limits in
    assessment_literals expected compiled;
    let exported=List.map(fun(role,handler)->let export=run handler role "export-policy-material"payload in
      publication_literals request(get "candidate" compiled)limits expected(get "report" compiled)export;export)roles in
    require(Json.equal(List.nth exported 0)(List.nth exported 1))"Fresh Core/Verify paired closure exports differ";
    let witnesses=items "trace_witnesses" expected in
    require(List.map(text "id")witnesses=witness_ids(text "id" case))
      "Closure family dropped or reordered a distinguishing literal history";
    List.iter(run_history request(get "candidate" compiled)limits)witnesses;
    case,compiled)cases in
  let first,compiled=List.hd results in
  requirement_controls first limits compiled;
  requirement_alternative_controls first limits compiled;
  nonzero_start_control(get "request" first)limits compiled;
  Printf.printf "policy material public closure, age/ordered-multiplicity literals, nine requirement controls and nonzero-start rejection passed (%d checks)\n" !checks
