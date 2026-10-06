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
let number key raw=Z.to_int(Json.integer(get key raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let set key value raw=
  require(List.mem_assoc key(Json.object_fields raw))("Absent state mutation field: "^key);
  obj(List.map(fun(name,original)->name,if name=key then value else original)(Json.object_fields raw))
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let run handler role operation payload=
  let request:Protocol.request={request_id="material-state-literal";operation;payload}in
  match handler role request with Protocol.Ok,Some result,[]->result
  |_->failwith("Registered state operation failed: "^operation)
let roles=[Protocol.Core,Producer.handle;Protocol.Verify,Service.handle]
let rejects label code action=match action()with
  |_->failwith("Accepted state negative control: "^label)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)(label^": wrong diagnostic "^diagnostic.code)
let requirements request=List.filter(fun row->text "$type" row="Requirement")
  (Json.array(at["implementation_request";"document";"program";"declarations"]request))
let source_literals request expected=
  List.iter(fun(key,path)->require(text key expected=Canonical.fingerprint(at path request))
    ("State original authority differs: "^key))[
    "request_fingerprint",[];"source_request_digest",["implementation_request"];
    "source_artifact_digest",["implementation_request";"document"];
    "definitions_digest",["implementation_request";"definitions"];
    "domain_digest",["implementation_request";"operating_domain"];
    "library_digest",["implementation_request";"implementation_library"];
    "material_contract_digest",["material_contract"];"context_digest",["context"];
    "kernel_digest",["material_contract";"body";"kernel"];
    "carrier_digest",["material_contract";"body";"carriers"]];
  let source=Bioc_checker.Policy_check.check(Q.document(R.implementation_request(R.of_json request)))in
  require(text "status" source="valid" && items "unresolved_obligations" source=items "obligations" expected &&
    List.length(items "obligations" expected)=23)"State source lost validity or an original obligation";
  require(List.map(text "id")(requirements request)=["request_progress";"initiation_progress";"exclusive_selection"] &&
    Json.equal(arr(requirements request))(get "requirements" expected))"State witness changed original hard requirements";
  require(get "prefixes_after_tick" expected=arr(List.map Json.int[1;1;9;9;9;9;9]) &&
    number "histories" expected=3*3 && number "transitions" expected=47 && number "prefixes_started" expected=48)
    "State fixture changed the independently counted full environment";
  let kernel=at["material_contract";"body";"kernel"]request in
  require(List.length(items "nodes" kernel)=17 && List.length(items "wires" kernel)=25 &&
    List.length(Json.array(at["material_contract";"body";"carriers"]request))=103)
    "Complete independently supplied state kernel/carrier census differs"
let local_node candidate local=
  let rows=List.filter(fun row->text "local_id" row="local."^local)(items "nodes"(get "material_binding" candidate))in
  match rows with [row]->text "node_id" row|_->failwith "Missing or duplicated independently checked local node"
let assessment_literals request expected compiled=
  let report=get "report" compiled and candidate=get "candidate" compiled in
  if text "status" report<>"checked_material"then
    failwith("State material request was not accepted: "^Canonical.encode report);
  List.iter(fun key->require(get key report=get key expected)("State assessment changed "^key))
    ["status";"claim_scope";"material_status";"context_status";"empirical";"artifact";"export"];
  require(get "artifact" compiled=Json.Null && get "all_original_obligations_discharged" report=Json.Bool true &&
    List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
    List.for_all(fun row->text "status" row="discharged" && get "evidence" row<>Json.Null)(items "obligations" report))
    "State material assessment omitted an original discharge or prematurely exported";
  require(Json.equal(at["behavior";"source_document"]candidate)(at["implementation_request";"document"]request))
    "State producer replaced original source authority";
  let preservation=get "preservation" report in
  require(text "status" preservation="checked_implementation" && text "preservation" preservation="pass" &&
    at["coverage";"complete"]preservation=Json.Bool true && at["program_coverage";"nonvacuous"]preservation=Json.Bool true)
    "State lowering acquired incomplete, vacuous or failing preservation";
  List.iter(fun key->require(at["coverage";key]preservation=get key expected)("State domain census changed "^key))
    ["histories";"transitions";"prefixes_started"];
  require(at["coverage";"matched_prefixes"]preservation=Json.int 48)"State correspondence omitted a permitted prefix";
  require(Json.equal(arr(List.map(get "source")(items "requirements" preservation)))(get "requirements" expected))
    "State requirement monitor changed a complete original requirement";
  List.iter(fun row->require(text "status" row="pass" && get "nonvacuous" row=Json.Bool true &&
    at["histories";"pass"]row=Json.int 9 &&
    List.for_all(fun key->at["histories";key]row=Json.int 0)["fail";"unknown";"unsupported";"not_exercised"])
    "An unchanged state hard requirement was not exercised and proved")(items "requirements" preservation);
  let context=get "context" report in
  require(List.map(get "id")(items "discharges" context)=items "context_discharges" expected)
    "State context omitted an original supplied-provider discharge";
  let resources rows=arr(List.sort(fun a b->String.compare(Canonical.encode a)(Canonical.encode b))
    (List.map(fun row->obj(List.map(fun key->key,get key row)["owner";"unit";"scope";"quantity"]))rows))in
  require(Json.equal(resources(items "derived_demands" context))(resources(items "resource_demands" expected)))
    "State reads or pure guards changed the independently supplied resource census";
  List.iter(fun key->require(at["record_layout";key]context=get key expected)("State record layout changed "^key))
    ["ordered_cause_slots";"ordered_reason_slots";"maximum_tick";"identifier_bytes"];
  require(List.length(items "nodes"(get "implementation" candidate))=17 &&
    List.length(items "wires"(get "implementation" candidate))=25)"Generic state graph changed the supplied complete inventory";
  List.iter(fun expected->let rows=List.filter(fun row->get "source_path" row=get "source_path" expected)
      (items "occurrences"(get "implementation" candidate))in
    let target=obj["node",str(local_node candidate "selected");"port",str "value"]in
    require(match rows with [row]->get "role" row=get "role" expected && text "disposition" row="executable" &&
      Json.equal(get "targets" row)(arr[target])|_->false)
      "State read occurrence was changed to a constant or another register")
    (items "state_occurrences" expected)
let publication_literals request candidate limits expected report export=
  require(Json.equal(get "report" export)report)"Fresh state export changed complete evidence";
  let artifact=get "artifact" export in
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  require(fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" && text "sequence" expected="CCAUGGCUUAAGGAAAA")
    "State source changed exact supplied RNA bytes";
  require(text "fasta_sha256" artifact=Canonical.sha256 fasta && text "fasta_sha256" manifest=Canonical.sha256 fasta &&
    text "manifest_sha256" artifact=Canonical.sha256(Canonical.encode manifest))"State publication lost paired exact-byte identities";
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    Json.equal(arr(List.map(get "molecule")(items "members" manifest)))(get "molecules" expected))
    "State publication omitted original authority, chemistry, coordinates or derivation";
  require(text "claim_scope" manifest="bounded_conditional_policy_to_exact_mrna" && text "empirical" manifest="unassessed" &&
    text "original_authority" manifest="retain_original_inputs_separately")"State export widened conditional claims"
let truth_name=function I.True->"true"|I.False->"false"|I.Unknown->"unknown"
let status_name=function P.Active->"active"|P.Completed->"completed"|P.Failed->"failed"|P.Timed_out->"timed_out"
  |P.Reset_invalidated->"encounter_reset"|P.End_invalidated->"encounter_ended"
let value_at ports node port slot=
  match List.filter(fun(value:P.port_value)->value.endpoint.node_id=node && value.endpoint.port_id=port &&
    value.binding={P.slot=Some slot;generation=0})ports with
  |[{P.signal=P.Truth value;_}]->value
  |_->failwith "Missing, duplicate or mistyped literal state/guard port"
let select (domain:F.t) witness source=
  let matches(batch:F.input_batch)=
    let observations=List.filter(fun(row:F.observation_input)->row.available_tick=batch.tick)domain.fixed_observations in
    let feedback=if batch.tick<>2 then[]else List.map(fun row->number "creation_ordinal" row,
      match text "outcome" row with "completed"->F.Completed|"failed"->F.Failed|_->failwith "Unknown state literal outcome")
      (items "feedback" witness)in
    List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle && batch.observations=observations &&
    List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=feedback in
  match List.filter matches(List.of_seq(S.choices source))with [batch]->batch
  |_->failwith "State literal history is absent or ambiguous in the complete original grammar"
let run_history request candidate limits expected witness=
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
  let selected=local_node candidate "selected" and excluded=local_node candidate "excluded"
  and guard=local_node candidate "select_guard" in
  let final=ref None and seen_snapshots=ref 0 in
  let rec loop source runtime correspondence=if not(S.finished source)then(
    let batch=select domain witness source in
    let input=T.input correspondence batch in
    let runtime,frame=P.step runtime input in
    let advanced=match S.step source batch with S.Advanced value->value
      |S.Stopped value->failwith("State literal source stopped: "^value.diagnostic.code)in
    let execution=Option.get advanced.receipt.execution in
    let compare candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
      ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate in
    List.iter(fun row->if number "tick" row=frame.tick then(
      incr seen_snapshots;
      List.iter(fun(name,node)->let value=value_at frame.outputs node "value"(text "slot" row)in
        require(value.reasons=[] && Option.map truth_name value.value=Some(text name row))
          "Settled source state differs from the literal common-prestate result")
        ["selected",selected;"excluded",excluded]))(items "settled_states" expected);
    List.iter(fun slot->let value=value_at frame.outputs guard "out" slot in
      require(Option.map(fun value->str(truth_name value))value.value=
        Some(List.nth(items "guard_by_tick" expected)frame.tick) &&
        value.reasons=(if frame.tick>=4 then[P.Stale]else[]))"State-dependent settled guard lost truth or evidence age")
      ["e1";"e2"];
    require(List.length frame.creations=(if frame.tick=1 then 2 else 0))"State guard changed the literal attempt-creation census";
    if frame.tick=1 then(
      let before=match frame.rounds with first::_->first.ports|_->failwith "Missing pre-activation round"in
      List.iter(fun slot->
        require((value_at before selected "value" slot).value=Some I.False &&
          (value_at before excluded "value" slot).value=Some I.False &&
          (value_at before guard "out" slot).value=Some I.True)
          "State guard or second assignment read state after the atomic write") ["e1";"e2"];
      require(List.for_all(fun(value:P.attempt)->value.authorization=I.True)frame.creations &&
        List.for_all(fun(value:P.attempt)->value.authorization=I.False && value.status=P.Active)frame.attempts)
        "State write did not preserve initiating true authorization then continuous false authorization";
      let changes=List.filter_map(fun(action:P.action)->match action.detail with
        |P.Authorization_changed(identity,value,reasons,response)->Some(identity,value,reasons,response,action.microstep)
        |_->None)frame.actions in
      require(List.length changes=2 && List.for_all(fun(_,value,reasons,response,microstep)->
        value=I.False && reasons=[] && response="continue" && microstep=1)changes)
        "Continuous authorization did not change exactly after the atomic write";
      let wrong={frame with outputs=List.map(fun(value:P.port_value)->
        if value.endpoint.node_id=excluded && value.endpoint.port_id="value" && value.binding.slot=Some "e1"
        then {value with signal=P.Truth{value=Some I.True;reasons=[]}}else value)frame.outputs}in
      rejects "sequential assignment reads newly written selected" "policy_trace_correspondence"(fun()->compare wrong));
    let correspondence=compare frame in
    List.iter(fun(value:P.attempt)->require(value.executor="cell-1" && value.product="fixture.product.alpha" &&
      T.candidate_attempt_to_source correspondence value.attempt_id="attempt/"^string_of_int value.ordinal)
      "State guard reassigned an encounter, payload or attempt correlation")frame.attempts;
    final:=Some frame;loop advanced.next runtime correspondence)in
  loop source runtime(T.create bound);
  require(!seen_snapshots=14)"State literal inventory omitted a settled slot/tick";
  let frame=Option.get !final in
  let rows=List.map(fun(value:P.attempt)->obj[
    "creation_ordinal",Json.int value.ordinal;"slot",Option.fold ~none:Json.Null ~some:str value.binding.slot;
    "target",str value.subject;"generation",Json.int value.binding.generation;"started_tick",Json.int value.started_tick;
    "deadline_tick",Json.int value.deadline_tick;"ended_tick",Option.fold ~none:Json.Null ~some:Json.int value.ended_tick;
    "status",str(status_name value.status);"authorization",str(truth_name value.authorization)])frame.attempts in
  require(frame.tick=6 && Json.equal(arr rows)(get "final_attempts" witness))
    "State literal history changed final attempt status, generation, deadline or authorization"
let mutations request candidate limits=
  let endpoint node port=obj["node",str(local_node candidate node);"port",str port]in
  let rewire candidate consumer producer=
    let graph=get "implementation" candidate in
    let count=ref 0 in
    let wires=List.map(fun wire->if Json.equal(get "consumer" wire)consumer then(
      incr count;set "producer" producer wire)else wire)(items "wires" graph)in
    require(!count=1)"State mutation missed or duplicated its actual typed wire";
    set "implementation"(set "wires"(arr wires)graph)candidate in
  let bypass=rewire candidate(endpoint "select_gate" "guard")(endpoint "evidence" "value")in
  let bypass=rewire bypass(endpoint "attempt" "authorization")(endpoint "evidence" "value")in
  let controls=[
    "wrong state read",rewire candidate(endpoint "select_commit" "value1")(endpoint "excluded" "value");
    "same-domain constant is not the declared state read",rewire candidate(endpoint "select_commit" "value1")(endpoint "false" "out");
    "guard reads another register",rewire candidate(endpoint "selected_not" "in")(endpoint "excluded" "value");
    "guard ignores state",bypass]in
  List.iter(fun(label,changed)->
    (* Typed graph decoding is outside the rejection catch. The unchanged
       original source and independently supplied material contract remain the
       authority, including where a constant mimics this finite input domain. *)
    let original=R.implementation_request(R.of_json request)in
    ignore(I.of_json ~library:(Q.implementation_library original)(get "implementation" changed));
    let payload=obj["request",request;"candidate",changed;"limits",limits]in
    List.iter(fun(role,handler)->List.iter(fun operation->
      rejects(label^" "^operation)"policy_implementation_source_binding"
        (fun()->run handler role operation payload))["check-policy-material";"export-policy-material"])roles)controls
let ()=
  require(Array.length Sys.argv=2)"Supply the frozen complete state material fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_material_state_literals.v0.1")"Unknown state fixture schema";
  let request=get "request" fixture and limits=get "limits" fixture and expected=get "expected" fixture in
  source_literals request expected;
  let compiled=run Producer.handle Protocol.Core "compile-policy-material"(obj["request",request;"limits",limits])in
  let candidate=get "candidate" compiled in
  let payload=obj["request",request;"candidate",candidate;"limits",limits]in
  List.iter(fun(role,handler)->
    require(Json.equal compiled(run handler role "check-policy-material"payload))"Fresh state Core/Verify check differs";
    require(Json.equal compiled(run handler role "replay-policy-material"(obj["request",request;"candidate",candidate;
      "limits",limits;"report",compiled])))"Fresh state full-wrapper replay differs")roles;
  require(text "request_fingerprint" compiled=Canonical.fingerprint request &&
    text "candidate_fingerprint" compiled=Canonical.fingerprint candidate &&
    text "invocation_fingerprint" compiled=Canonical.fingerprint payload &&
    text "report_fingerprint" compiled=Canonical.fingerprint(get "report" compiled))"State public wrapper lost exact authorities";
  assessment_literals request expected compiled;
  let exports=List.map(fun(role,handler)->let export=run handler role "export-policy-material"payload in
    publication_literals request candidate limits expected(get "report" compiled)export;export)roles in
  require(Json.equal(List.nth exports 0)(List.nth exports 1))"Fresh state Core/Verify paired exports differ";
  require(List.map(text "id")(items "trace_witnesses" expected)=["quiet_timeout";"mixed_feedback"])
    "State fixture dropped a literal feedback/timeout history";
  List.iter(run_history request candidate limits expected)(items "trace_witnesses" expected);
  mutations request candidate limits;
  Printf.printf "policy material state reads, common-prestate writes, continuous guard phases and independent mutations passed (%d checks)\n" !checks
