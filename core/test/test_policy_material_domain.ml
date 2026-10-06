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
module Material=Bioc_service.Policy_material_service
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
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec put path replacement raw=match path with []->replacement|key::rest->match raw with
  |Json.Array values->arr(List.mapi(fun index value->
      if index=int_of_string key then put rest replacement value else value)values)
  |_->set key(put rest replacement(get key raw))raw
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let rejects label code action=match action()with
  |_->failwith("Accepted domain negative control: "^label)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)
      (label^": wrong diagnostic "^diagnostic.code)
let run handler role operation payload=
  let request:Protocol.request={request_id="material-domain-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered domain material operation failed: "^operation)
let census = function
  |"extended_evidence"->[1;1;9;54;54;54;54],54,227,228
  |"reset_feedback"->[1;1;1;3;27;27;27],27,87,88
  |"reset_recreate"->[1;1;1;2;18;486;486],486,995,996
  |"reset_recreate_feedback"->[1;1;1;2;2;54;54],54,115,116
  |_->failwith "Unreviewed material domain fixture"
let sorted key rows=List.sort(fun a b->String.compare(text key a)(text key b))rows
let original_literals case=
  let request=get "request" case and expected=get "expected" case in
  let prefix,histories,transitions,prefixes=census(text "id" case)in
  require(3*3*6=54 && 3*3*3=27 && 2*(3*3)*(3*3*3)=486 && 2*(3*3*3)=54)
    "Independent product census changed";
  require(List.map integer(items "prefixes_after_tick" expected)=prefix &&
    List.fold_left(+)0 prefix=transitions && prefixes=transitions+1 &&
    number "histories" expected=histories && number "transitions" expected=transitions &&
    number "prefixes_started" expected=prefixes)"Original finite domain census changed";
  List.iter(fun(key,path)->require(text key expected=Canonical.fingerprint(at path request))
    ("Full original authority changed: "^key))[
    "request_fingerprint",[];"source_request_digest",["implementation_request"];
    "source_artifact_digest",["implementation_request";"document"];
    "definitions_digest",["implementation_request";"definitions"];
    "domain_digest",["implementation_request";"operating_domain"];
    "library_digest",["implementation_request";"implementation_library"];
    "material_contract_digest",["material_contract"];
    "kernel_digest",["material_contract";"body";"kernel"];
    "carrier_digest",["material_contract";"body";"carriers"];
    "context_digest",["context"]];
  require(number "carrier_count" expected=92 &&
    List.length(Json.array(at["material_contract";"body";"carriers"]request))=92 &&
    number "node_count" expected=15)"Original complete primitive/carrier inventory changed";
  let original=R.implementation_request(R.of_json request)in
  let source=Bioc_checker.Policy_check.check(Q.document original)in
  require(text "status" source="valid" && List.length(items "obligations" expected)=23 &&
    items "unresolved_obligations" source=items "obligations" expected)
    "Domain request weakened or omitted an original source obligation";
  let requirements=List.filter(fun value->text "$type" value="Requirement")
    (Json.array(at["implementation_request";"document";"program";"declarations"]request))in
  require(List.map(text "id")(sorted "id" requirements)=
    ["exclusive_selection";"initiation_progress";"request_progress"] &&
    Json.equal(arr requirements)(get "requirements" expected))"Original three hard requirements changed"
let assessment_literals expected compiled=
  let report=get "report" compiled and candidate=get "candidate" compiled in
  List.iter(fun key->require(get key report=get key expected)
    ("Material domain claim changed: "^key^(if key="status" then
      "; original domain "^text "domain_digest" expected^"; complete fresh report: "^Canonical.encode report else "")))
    ["status";"claim_scope";"material_status";"context_status";"empirical";"artifact";"export"];
  require(get "artifact" compiled=Json.Null && get "all_original_obligations_discharged" report=Json.Bool true)
    "Compilation published material or omitted the complete original conjunction";
  require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
    List.for_all(fun row->text "status" row="discharged" && get "evidence" row<>Json.Null)(items "obligations" report))
    "Original obligation ledger lost a discharge or its evidence";
  let preservation=get "preservation" report in
  require(text "status" preservation="checked_implementation" && text "preservation" preservation="pass" &&
    at["coverage";"complete"]preservation=Json.Bool true &&
    at["program_coverage";"nonvacuous"]preservation=Json.Bool true)
    "Domain exploration was incomplete, failing or vacuous";
  List.iter(fun key->require(at["coverage";key]preservation=get key expected)("Exhaustive census differs: "^key))
    ["histories";"transitions";"prefixes_started"];
  require(at["coverage";"matched_prefixes"]preservation=get "prefixes_started" expected)
    "A permitted transition was omitted from correspondence";
  let requirements=items "requirements" preservation in
  require(List.map(text "id")(sorted "id" requirements)=
    ["exclusive_selection";"initiation_progress";"request_progress"])
    "Domain requirement inventory changed";
  require(Json.equal(arr(List.map(get "source")requirements))(get "requirements" expected))
    "A monitored hard requirement differs from its complete original";
  List.iter(fun row->require(text "status" row="pass" && get "nonvacuous" row=Json.Bool true &&
      at["histories";"pass"]row=get "histories" expected &&
      List.for_all(fun key->at["histories";key]row=Json.int 0)["fail";"unknown";"unsupported";"not_exercised"])
    "An original hard requirement was weakened or not exercised in a fixed-rise history")requirements;
  let context=get "context" report in
  require(List.map(get "id")(items "discharges" context)=items "context_discharges" expected)
    "Context changed its separately justified source discharges";
  let resource row=obj(List.map(fun key->key,get key row)["owner";"unit";"scope";"quantity"])in
  let resources rows=arr(List.sort(fun a b->String.compare(Canonical.encode a)(Canonical.encode b))
    (List.map resource rows))in
  require(Json.equal(resources(items "derived_demands" context))
    (resources(items "resource_demands" expected)))"Whole-domain resource minima differ from literal demand inventory";
  List.iter(fun(key,literal)->require(at["record_layout";key]context=get literal expected)
    ("Complete conditional record layout changed: "^key))
    ["maximum_tick","maximum_tick";"ordered_cause_slots","ordered_cause_slots"];
  require(List.length(items "nodes"(get "implementation" candidate))=15)
    "Fresh producer changed the supplied primitive inventory"
let incomplete_literals expected compiled=
  let report=get "report" compiled in
  require(text "status" report="not_accepted" && text "material_status" report="unassessed" &&
    text "context_status" report="unassessed" && get "all_original_obligations_discharged" report=Json.Bool false &&
    text "artifact" report="withheld" && text "export" report="withheld" && get "artifact" compiled=Json.Null)
    "Exhausted original domain gained material acceptance or publication";
  let preservation=get "preservation" report and diagnostic=at["preservation";"stopped";"diagnostic"]report in
  require(text "status" preservation="incomplete" && text "preservation" preservation="unassessed" &&
    at["coverage";"complete"]preservation=Json.Bool false && at["stopped";"category"]preservation=str "incomplete" &&
    text "code" diagnostic=text "incomplete_code" expected && get "path" diagnostic=Json.Null &&
    text "message" diagnostic="Complete traversal lacks the next required execution reservation.")
    "Original large domain failed at an unrelated boundary instead of bounded work exhaustion";
  require(at["binding";"operating_domain_digest"]preservation=get "domain_digest" expected)
    "Incomplete exploration substituted a smaller original domain";
  let histories=number "histories"(get "coverage" preservation) and transitions=number "transitions"(get "coverage" preservation)in
  require(histories>0 && histories<number "histories" expected && transitions<number "transitions" expected)
    "Partial exploration silently acquired a complete-domain census";
  require(Json.equal(arr(List.map(get "source")(items "requirements" preservation)))(get "requirements" expected) &&
    List.for_all(fun row->text "status" row="unknown")(items "requirements" preservation))
    "Incomplete exploration dropped or accepted a hard requirement";
  require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected &&
    List.for_all(fun row->text "status" row="unresolved" && get "evidence" row=Json.Null)(items "obligations" report))
    "Incomplete conjunction dropped or discharged an original obligation"
let status_name = function
  |P.Active->"active"|P.Completed->"completed"|P.Failed->"failed"|P.Timed_out->"timed_out"
  |P.Reset_invalidated->"encounter_reset"|P.End_invalidated->"encounter_ended"
let attempt_literal(value:P.attempt)=obj[
  "creation_ordinal",Json.int value.ordinal;"slot",Option.fold ~none:Json.Null ~some:str value.binding.slot;
  "target",str value.subject;"generation",Json.int value.binding.generation;
  "started_tick",Json.int value.started_tick;"deadline_tick",Json.int value.deadline_tick;
  "ended_tick",Option.fold ~none:Json.Null ~some:Json.int value.ended_tick;"status",str(status_name value.status)]
let evidence row=match text "status" row with
  |"valid"->F.Known(Json.boolean(get "value" row))|"missing"->F.Missing|"invalid"->F.Invalid
  |"conflicting"->F.Conflicting|_->failwith "Unsupported literal evidence class"
let lifecycle = function "keep"->F.Keep|"reset"->F.Reset|"end"->F.End|_->failwith "Unknown literal lifecycle"
let feedback_outcome = function "completed"->F.Completed|"failed"->F.Failed|_->failwith "Unknown literal feedback"
let select (domain:F.t) witness source=
  let matches(batch:F.input_batch)=
    let expected_lifecycle=List.map(fun(slot:F.encounter)->slot.identity,
      match List.find_opt(fun row->number "tick" row=batch.tick && text "slot" row=slot.identity)(items "lifecycle" witness)with
      |None->F.Keep|Some row->lifecycle(text "action" row))domain.F.encounters in
    let observations=List.filter(fun(row:F.observation_input)->row.available_tick=batch.tick)domain.fixed_observations @
      List.filter_map(fun row->if number "tick" row<>batch.tick then None else
        Some({F.slot=text "slot" row;observation="condition";available_tick=batch.tick;
          observed_tick=batch.tick;evidence=evidence row}:F.observation_input))(items "observations" witness)in
    let feedback=match List.find_opt(fun row->number "tick" row=batch.tick)(items "feedback" witness)with
      |None->[]|Some row->List.map(fun item->number "creation_ordinal" item,feedback_outcome(text "outcome" item))(items "rows" row)in
    batch.lifecycle=expected_lifecycle && batch.observations=observations &&
      List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=feedback in
  match List.filter matches(List.of_seq(S.choices source))with
  |[batch]->batch|_->failwith "Literal history is absent or ambiguous in the original causal grammar"
let run_history request candidate limits witness=
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
  let observations=ref[] and feedback=ref[] and accepted=ref[] and rejected=ref[] and final=ref None in
  let rec loop source runtime correspondence=
    if not(S.finished source)then(
      let batch=select domain witness source in
      let input=T.input correspondence batch in
      let ids kind count=List.init count(fun index->"domain/"^kind^"/"^string_of_int batch.tick^"/"^string_of_int index)in
      let observation_ids=List.map(fun(row:P.observation)->row.observation_id)input.observations
      and feedback_ids=List.map(fun(row:P.feedback)->row.feedback_id)input.feedback in
      require(observation_ids=ids "observation"(List.length batch.observations) &&
        feedback_ids=ids "feedback"(List.length batch.feedback))"Candidate adapter changed ordered occurrence identity";
      observations:= !observations@observation_ids;feedback:= !feedback@feedback_ids;
      let all_ids= !observations@ !feedback in
      require(List.length(List.sort_uniq String.compare all_ids)=List.length all_ids)
        "Reset/end/repeated feedback reused a global input occurrence identity";
      let next_runtime,frame=P.step runtime input in
      let advanced=match S.step source batch with S.Advanced value->value
        |S.Stopped value->failwith("Literal source prefix stopped: "^value.diagnostic.code)in
      require(List.map(text "id")(items "observations" advanced.receipt.timeline)= !observations &&
        List.map(text "id")(items "feedback" advanced.receipt.timeline)= !feedback)
        "Source and candidate adapters disagree on complete occurrence history";
      require(List.length frame.creations=integer(List.nth(items "creations_by_tick" witness)batch.tick))
        "A literal tick lost or invented an effect attempt";
      List.iter(fun(attempt:P.attempt)->require(attempt.executor="cell-1" && attempt.product="fixture.product.alpha")
        "Literal attempt lost executor/product identity")frame.attempts;
      let ordinal identity=(List.find(fun(attempt:P.attempt)->attempt.attempt_id=identity)frame.attempts).ordinal in
      List.iter(fun(action:P.action)->match action.detail with
        |P.Feedback_accepted(_,identity)->accepted:= !accepted@[obj["tick",Json.int batch.tick;"creation_ordinal",Json.int(ordinal identity)]]
        |P.Feedback_rejected(_,identity,reason)->rejected:= !rejected@[obj["tick",Json.int batch.tick;
            "creation_ordinal",Json.int(ordinal identity);"reason",str reason]]
        |_->())frame.actions;
      let execution=match advanced.receipt.execution with Some value->value|None->failwith "No fresh source execution"in
      let compare candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
        ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate in
      (* These malformed runtime inputs are outside the admitted grammar. A
         source-owned prefix must not gain a matching trace by changing routes
         or reusing any observation/feedback ID, including after reset. *)
      (match input.feedback with
       |[]->()
       |(first:P.feedback)::rest->
           let wrong={first with subject="foreign-target"}in
           let _,changed=P.step runtime {input with feedback=wrong::rest}in
           rejects "wrong-route runtime feedback" "policy_trace_correspondence"(fun()->compare changed);
           let reused={first with feedback_id="domain/observation/0/0"}in
           rejects "cross-kind reused feedback occurrence" "policy_primitives_identity"
             (fun()->P.step runtime {input with feedback=reused::rest}));
      let correspondence=compare frame in
      List.iter(fun(attempt:P.attempt)->require(T.candidate_attempt_to_source correspondence attempt.attempt_id=
        "attempt/"^string_of_int attempt.ordinal)"Old/new attempts lost their creation-time injective relation")frame.attempts;
      final:=Some frame;
      loop advanced.next next_runtime correspondence)in
  loop source runtime(T.create bound);
  let frame=match !final with Some value->value|None->failwith "No inclusive domain frames"in
  require(frame.tick=6 && Json.equal(arr(List.map attempt_literal frame.attempts))(get "final_attempts" witness))
    ("Literal final attempt/generation/deadline ledger changed: "^text "id" witness);
  require(Json.equal(arr !accepted)(get "feedback_acceptances" witness) &&
    Json.equal(arr !rejected)(get "feedback_rejections" witness))"Repeated old feedback completed or advanced an unrelated attempt";
  List.iter(fun(key,actual)->match List.assoc_opt key(Json.object_fields witness)with
    |None->()|Some expected->require(Json.equal(arr(List.map str actual))expected)
      ("Independent ordered occurrence literal changed: "^key))
    ["observation_occurrence_ids",!observations;"feedback_occurrence_ids",!feedback]
let publication_literals request candidate limits expected report export=
  require(Json.equal(get "report" export)report)"Fresh export changed the complete checked assessment";
  let artifact=get "artifact" export in
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  require(fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" &&
    text "sequence" expected="CCAUGGCUUAAGGAAAA")"Original domain changed exact delivered RNA";
  require(text "fasta_sha256" artifact=Canonical.sha256 fasta &&
    text "fasta_sha256" manifest=Canonical.sha256 fasta &&
    text "manifest_sha256" artifact=Canonical.sha256(Canonical.encode manifest))"Exported paired bytes lost exact fingerprints";
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report)
    "Fresh domain export lost original authority or complete fresh evidence";
  require(Json.equal(arr(List.map(get "molecule")(items "members" manifest)))(get "molecules" expected))
    "Same RNA hid a change in chemistry, product, coordinates or provenance";
  require(text "claim_scope" manifest="bounded_conditional_policy_to_exact_mrna" &&
    text "empirical" manifest="unassessed" && text "original_authority" manifest="retain_original_inputs_separately")
    "Domain export widened conditional acceptance"
let ()=
  require(Array.length Sys.argv=2)"Supply frozen complete material-domain fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_material_domain_literals.v0.1")"Unknown domain witness schema";
  let cases=items "cases" fixture and limits=get "limits" fixture in
  require(List.map(text "id")cases=["extended_evidence";"reset_feedback";"reset_recreate";"reset_recreate_feedback"])
    "Domain witness inventory changed";
  let baseline=get "request"(List.hd cases)in
  let results=List.map(fun case->
    original_literals case;
    let request=get "request" case and expected=get "expected" case in
    List.iter(fun path->require(Json.equal(at path request)(at path baseline))
      "Domain variant changed original source/library/kernel/carriers")
      [["implementation_request";"document"];["implementation_request";"definitions"];
       ["implementation_request";"implementation_library"];["material_contract";"body";"kernel"];
       ["material_contract";"body";"carriers"]];
    let compiled=run Producer.handle Protocol.Core "compile-policy-material"(obj["request",request;"limits",limits])in
    let candidate=get "candidate" compiled in
    let payload=obj["request",request;"candidate",candidate;"limits",limits]in
    List.iter(fun(role,handler)->require(Json.equal compiled(run handler role "check-policy-material"payload))
      "Fresh Core/Verify checks differ from generic production")
      [Protocol.Core,Producer.handle;Protocol.Verify,Service.handle];
    let incomplete=text "check_expectation" expected="incomplete"in
    require(incomplete=(text "id" case="reset_recreate"))"Unreviewed incomplete-domain classification";
    if incomplete then incomplete_literals expected compiled else assessment_literals expected compiled;
    require(text "request_fingerprint" compiled=Canonical.fingerprint request &&
      text "candidate_fingerprint" compiled=Canonical.fingerprint candidate &&
      text "invocation_fingerprint" compiled=Canonical.fingerprint payload &&
      text "report_fingerprint" compiled=Canonical.fingerprint(get "report" compiled))
      "Complete wrapper omitted an authority or evidence binding";
    require(Json.equal compiled(run Service.handle Protocol.Verify "replay-policy-material"(set "report" compiled payload)))
      "Full fresh domain replay changed exact evidence";
    let export=if incomplete then(
      List.iter(fun(role,handler)->rejects "incomplete original-domain export" "policy_material_export_not_accepted"
        (fun()->run handler role "export-policy-material"payload))
        [Protocol.Core,Producer.handle;Protocol.Verify,Service.handle];None)
      else let export=run Service.handle Protocol.Verify "export-policy-material"payload in
        publication_literals request candidate limits expected(get "report" compiled)export;Some export in
    let witnesses=items "trace_witnesses" expected in
    require(List.map(text "id")witnesses=(match text "id" case with
      |"extended_evidence"->["known_true_repeated_attempt"]
      |"reset_feedback"->["keep_old_feedback";"reset_old_feedback";"end_old_feedback"]
      |"reset_recreate"|"reset_recreate_feedback"->["keep_completed";"keep_failed";"keep_silence";"reset_completed";"reset_failed";"reset_silence"]
      |_->assert false))"Literal lifecycle/feedback witness inventory changed";
    List.iter(run_history request candidate limits)witnesses;
    let wrong=put["implementation_request";"operating_domain";"feedback_factors";"0";"routes"]
      (arr[str "correlated";str "wrong_target"])request in
    let reject_route operation payload=match run Service.handle Protocol.Verify operation payload with
      |_->failwith "Full material route admitted unsupported feedback addressing"
      |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_domain_unsupported" &&
          diagnostic.path=None && diagnostic.message="Wrong-address feedback routes are not implemented in this profile.")
          "Wrong route failed on stale authority instead of explicit domain support"in
    reject_route "check-policy-material"(set "request" wrong payload);
    reject_route "export-policy-material"(set "request" wrong payload);
    case,compiled,export)cases in
  (* The smaller accepted grammar has its own complete original authority; it
     cannot discharge the unchanged 486-history request. Keep that failed
     request and every one of its literal histories as independent controls. *)
  let large_case,large,_=List.find(fun(case,_,_)->text "id" case="reset_recreate")results in
  let small_case,small,_=List.find(fun(case,_,_)->text "id" case="reset_recreate_feedback")results in
  require(text "request_fingerprint" large<>text "request_fingerprint" small &&
    text "domain_digest"(get "expected" large_case)<>text "domain_digest"(get "expected" small_case))
    "Separate finite grammar reused the incomplete original authority";
  let large_payload=obj["request",get "request" large_case;"candidate",get "candidate" large;"limits",limits]in
  rejects "small-domain receipt cannot complete the large original" "policy_material_replay"(fun()->
    run Service.handle Protocol.Verify "replay-policy-material"(set "report" small large_payload));
  rejects "small-domain candidate cannot export the large original" "policy_implementation_contract"(fun()->
    Material.check ~export:true ~request:(get "request" large_case) ~candidate:(get "candidate" small) ~limits);
  let accepted=List.filter_map(fun(case,compiled,export)->Option.map(fun export->case,compiled,export)export)results in
  require(List.length accepted=3)"Accepted domain family census changed";
  List.iteri(fun index(case,compiled,export)->
    let other,other_compiled,other_export=List.nth accepted((index+1)mod List.length accepted)in
    let request=get "request" other and candidate=get "candidate" other_compiled in
    let payload=obj["request",request;"candidate",candidate;"limits",limits]in
    rejects "old domain receipt with freshly produced candidate" "policy_material_replay"(fun()->
      run Service.handle Protocol.Verify "replay-policy-material"(set "report" compiled payload));
    rejects "old domain candidate at fresh export" "policy_implementation_contract"(fun()->
      Material.check ~export:true ~request ~candidate:(get "candidate" compiled) ~limits);
    require(text "fasta_sha256"(get "artifact" export)=text "fasta_sha256"(get "artifact" other_export) &&
      text "manifest_sha256"(get "artifact" export)<>text "manifest_sha256"(get "artifact" other_export) &&
      text "request_fingerprint" compiled<>text "request_fingerprint" other_compiled &&
      text "domain_digest"(get "expected" case)<>text "domain_digest"(get "expected" other))
      "Identical RNA reused another domain's acceptance or manifest")accepted;
  Printf.printf "policy material complete finite-domain production/replay/export and 16 literal histories including retained exhaustion passed (%d checks)\n" !checks
