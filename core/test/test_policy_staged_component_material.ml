open Bioc_wire
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
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
let call handler role operation payload=
  let request:Protocol.request={request_id="staged-material-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let checked request candidate limits=call Service.handle Protocol.Verify "check-policy-component-material"
  (o["request",request;"candidate",candidate;"limits",limits])
let expected_rejection=ref 0
let rejects label operation payload=
  let request:Protocol.request={request_id="staged-material-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Ok,Some result,[] when at["report";"status"]result=s "not_accepted" && get "artifact" result=Json.Null->incr expected_rejection
  |Protocol.Ok,_,_->failwith("Staged material mutant accepted: "^label)
  |_,None,(_::_)->incr expected_rejection
  |_->failwith("Malformed rejection for "^label)
let repin value=edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint(get "body" value)))value
let ()=
  let channel=open_in_bin Sys.argv.(1)in
  let raw=really_input_string channel(in_channel_length channel)in close_in channel;
  let fixture=Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000 raw in
  let request=get "request" fixture and limits=get "limits" fixture and expected=get "expected" fixture in
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"(o["request",request;"limits",limits])in
  require(at["report";"status"]produced=s "checked_component_material")
    ("Staged complete conjunction rejected: "^Canonical.encode(at["report";"status"]produced));
  require(get "artifact" produced=Json.Null)"Staged compilation bypassed fresh export.";
  let candidate=get "candidate" produced in
  let original=Bioc_domain.Policy_component_material_request.of_json request in
  let decode_rule raw=Bioc_domain.Policy_component_assembly_rule.of_json
    ~components:(Bioc_domain.Policy_component_material_request.component_library original)raw in
  let rule=get "composition_rule" request in
  let reject_decode label action=match action () with
    |_->failwith("Staged original contract mutant accepted: "^label)
    |exception Diagnostic.Error _->incr expected_rejection in
  let rule_mutant label f=reject_decode label(fun ()->decode_rule(repin(f rule)))in
  rule_mutant "duplicate-feedback-producer"(edit["body";"links"](fun raw->
    let links=Json.array raw in
    let duplicate=List.find(fun row->get "id" row=s "stage1.completed")links in
    a(List.map(fun row->if get "id" row=s "stage0.completed" then
      set "producer"(get "producer" duplicate)row else row)links)));
  rule_mutant "event-cross-scope"(edit["body";"links"](fun raw->a(List.map(fun row->
    if get "id" row=s "stage0.completed" then set "scope"(s "immutable_executor_broadcast")row else row)(Json.array raw))));
  rule_mutant "shared-stage-bank"(edit["body";"links"](fun raw->
    let links=Json.array raw in
    let first=List.find(fun row->get "id" row=s "stage0.request")links in
    a(List.map(fun row->if get "id" row=s "stage1.request" then set "consumer"(get "consumer" first)row else row)links)));
  List.iter(fun field->reject_decode ("incomplete-record:"^field)(fun ()->
    Bioc_domain.Policy_component_context.of_json(edit["record_layout";"record_shapes";field]
      (fun raw->a(List.filter(fun value->value<>s "machine_bank")(Json.array raw)))(get "context" request))))
    ["active_attempt_records";"retained_correlation_records"];
  reject_decode "incomplete-transition-record"(fun ()->Bioc_domain.Policy_component_context.of_json
    (edit["record_layout";"record_shapes";"control_event_records"](fun raw->a(List.filter
      (fun value->value<>s "ordered_retained_attempt_ids")(Json.array raw)))(get "context" request)));
  reject_decode "legacy-record-profile"(fun ()->Bioc_domain.Policy_component_context.of_json
    (edit["record_layout";"profile"](fun _->s "biocompiler.policy_component_complete_records.v0.1")(get "context" request)));
  let fresh=checked request candidate limits in
  require(Json.equal produced fresh)"Staged compile differs from fresh producer-free Verify.";
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  require(Json.equal fresh(call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",fresh])))"Staged independent replay changed evidence.";
  let report=get "report" fresh in
  require(at["preservation";"coverage";"complete"]report=Json.Bool true &&
    at["preservation";"coverage";"histories"]report=Json.int 25 &&
    at["preservation";"coverage";"transitions"]report=Json.int 86 &&
    at["preservation";"coverage";"matched_prefixes"]report=Json.int 87)
    "Staged checker did not retain the complete independently enumerated 25-history domain.";
  require(List.for_all(fun row->get "status" row=s "pass" && get "nonvacuous" row=Json.Bool true)
    (rows "requirements"(get "preservation" report)))"Staged original requirements are missing or unproved.";
  let obligation=List.find(fun row->get "obligation" row=s "machine_reachability_termination_and_progress")(rows "obligations" report)in
  require(get "stage" obligation=s "bounded_machine_semantics_and_declared_requirements" &&
    at["evidence";"universal_termination"]obligation=s "not_claimed" &&
    at["evidence";"progress"]obligation=s "declared_requirements_only")"Staged ledger widened bounded machine assurance.";
  require(get "all_original_obligations_discharged" report=Json.Bool true && get "empirical" report=s "unassessed")
    "Staged conjunction changed scope.";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  require(Json.equal exported(call Producer.handle Protocol.Core "export-policy-component-material" invocation))
    "Staged Core/Verify fresh paired exports differ.";
  let artifact=get "artifact" exported and molecules=[get "molecule" expected] in
  require(List.length molecules=1 && Json.equal(at["construction";"inventory";"molecules"]candidate)(a molecules))
    "Staged construction differs from independent exact molecule authority.";
  let molecule=List.hd molecules in
  let sequence=text "sequence" molecule in
  let fasta=">rna_0001 alphabet=RNA\n"^sequence^"\n"in
  require(get "fasta" artifact=s fasta && get "fasta_sha256" artifact=s(Canonical.sha256 fasta))
    "Staged exact FASTA differs from retained synthetic RNA.";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    at["bindings";"assessment_fingerprint"]manifest=s(Canonical.fingerprint report) &&
    get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Staged manifest omits complete unchanged original authority or fresh assessment.";
  require(Json.equal(get "members" manifest)(a[o["fasta_id",s "rna_0001";"member_id",s "payload";
    "molecule",molecule;"sequence_sha256",s(Canonical.sha256 sequence)]]))"Staged manifest molecule is not byte-exact.";
  let mutant label change=rejects label "check-policy-component-material"(set "candidate"(change candidate)invocation)in
  mutant "missing-machine-write"(edit["implementation";"wires"](fun raw->a(List.filter(fun wire->
    at["producer";"port"]wire<>s "machine_write" || at["producer";"node"]wire<>s "transition/0/commit")(Json.array raw))));
  mutant "stage-feedback-origin"(edit["implementation";"wires"](fun raw->a(List.map(fun wire->
    if at["producer";"node"]wire=s "attempt/0" && at["producer";"port"]wire=s "events" then
      edit["producer";"node"](fun _->s "attempt/1")wire else wire)(Json.array raw))));
  mutant "stage-request-owner"(edit["implementation";"wires"](fun raw->a(List.map(fun wire->
    if at["consumer";"port"]wire=s "request" then edit["consumer";"node"](function
      |Json.String "attempt/0"->s "attempt/1"|Json.String "attempt/1"->s "attempt/0"|other->other)wire else wire)(Json.array raw))));
  mutant "exact-rna"(edit["construction";"inventory";"molecules"](fun raw->a(List.map(fun molecule->
    set "sequence"(s("A"^String.sub(text "sequence" molecule)1(String.length(text "sequence" molecule)-1)))molecule)(Json.array raw))));
  let source_changed=edit["implementation_request";"document";"program";"declarations"](fun raw->a(List.map(fun value->
    if get "$type" value=s "Transition" && get "id" value=s "regimen/handoff" then set "destination"(s "completed")value else value)(Json.array raw)))request in
  rejects "original-transition-edit" "check-policy-component-material"(set "request" source_changed invocation);
  let deficient=edit["context";"providers"](fun raw->a(List.map(fun provider->
    repin(edit["body";"capacities"](fun raw->a(List.map(fun row->
      if get "unit" row=s "machine_state_bits" then set "quantity"(Json.int 2)row else row)(Json.array raw)))provider))(Json.array raw)))request in
  let denied=checked deficient candidate limits in
  require(at["report";"status"]denied=s "not_accepted" && get "artifact" denied=Json.Null)
    "Insufficient finite machine-state encoding capacity was accepted.";
  incr expected_rejection;
  rejects "capacity-export" "export-policy-component-material"(set "request" deficient invocation);
  let exhausted=checked request candidate(set "max_step_work"(Json.int 1)limits)in
  require(at["report";"status"]exhausted=s "not_accepted" && get "artifact" exhausted=Json.Null)
    "Incomplete bounded checking yielded material acceptance.";
  incr expected_rejection;
  let completion_required=edit["implementation_request";"document";"program";"declarations"](fun raw->a(List.map(fun value->
    if get "$type" value=s "Requirement" && get "id" value=s "second_initiation" then
      edit["response";"value"](fun _->s "completed")value else value)(Json.array raw)))request in
  let cannot_finish=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",completion_required;"limits",limits])in
  require(at["report";"status"]cannot_finish=s "not_accepted" && get "artifact" cannot_finish=Json.Null &&
    List.exists(fun row->get "id" row=s "second_initiation" && get "status" row=s "fail")
      (rows "requirements"(at["report";"preservation"]cannot_finish)))
    "Absent external feedback was incorrectly promoted to guaranteed completion.";
  incr expected_rejection;
  let replay=edit["report";"preservation";"coverage";"histories"](fun _->Json.int 1)fresh in
  rejects "forged-coverage-replay" "replay-policy-component-material"(o["request",request;"candidate",candidate;"limits",limits;"report",replay]);
  Printf.printf "staged_component_material: exact 25-history Python-source-to-RNA conjunction; %d rejection controls\n" !expected_rejection
