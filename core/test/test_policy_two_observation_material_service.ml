open Bioc_wire
open Bioc_policy_two_observation_test_support.Literals
open Bioc_policy_two_observation_test_support.Requests
module S = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let call handler role operation payload =
  let request:Protocol.request={request_id="prerequisite-material-original";operation;payload} in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered prerequisite operation failed: "^operation)
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material"
  (obj ["request",request;"limits",limits])
let invocation request candidate limits=obj ["request",request;"candidate",candidate;"limits",limits]
let checked result =
  let report=get "report" result in
  require(get "status" report=str "checked_component_material" &&
    get "all_original_obligations_discharged" report=Json.Bool true)
    ("Fresh prerequisite conjunction failed: "^Canonical.encode report);
  require(get "implementation" result=str "biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1" &&
    get "validation_scope" result=str "policy-instance-two-observation-prerequisite-mrna-v0.1" &&
    get "schema_version" report=str "biocompiler.policy_component_material_assessment.v0.2" &&
    get "implementation" report=str "biocompiler.ocaml.policy_component_material_check.v0.4" &&
    get "profile" report=str material_profile && get "empirical" report=str "unassessed")
    "Prerequisite result changed its separate interpretation or empirical scope";
  require(at ["preservation";"binding";"schema_version"]report=str "biocompiler.policy_implementation_binding_report.v0.3" &&
    at ["preservation";"binding";"profile"]report=str "biocompiler.policy_two_observation_source_graph.v0.1" &&
    at ["context";"implementation_version"]report=str "biocompiler.ocaml.policy_component_context_check.v0.4")
    "Two-observation interpretation was published under a legacy source-binding or context checker";
  report
let not_accepted label result =
  let report=get "report" result in
  require(get "status" report=str "not_accepted" && get "artifact" result=Json.Null &&
    get "all_original_obligations_discharged" report=Json.Bool false)
    ("Mutation retained complete acceptance: "^label);
  report
let check_closure request report =
  let closure=get "prerequisites" report in
  let expected=expected_closure request
    |> add "assembly_fingerprint"(str(Canonical.fingerprint(get "assembly" report))) in
  require(Json.equal closure expected &&
    Json.equal closure(at ["context";"prerequisite_closure"]report) &&
    get "prerequisite_status" report=str "pass")
    ("Closure differs from independently declared roots, owners, allocations or exact pins: "^
      Canonical.encode closure);
  let obligations=items "obligations" report in
  require(List.length obligations=24 && List.map(get "obligation")obligations=expected_obligations &&
    List.for_all(fun row->get "status" row=str "discharged")obligations)
    "Original twenty-four obligations were dropped, replaced or left unresolved";
  let pin=str(Canonical.fingerprint closure) in
  List.iter(fun row->if List.mem(get "stage" row)
    [str "declared_context";str "conditional_component_context_conjunction"] then
      require(at ["evidence";"prerequisites"]row=pin)
        "Contextual obligation omitted its exact freshly checked prerequisite evidence")obligations
let check_original_graph union candidate state_reading =
  let proposed=at ["assembly_proposal";"nodes"]candidate |> Json.array in
  let actual reference=get "actual"(List.find(fun row->get "slot" row=get "slot" reference &&
    get "node" row=get "node" reference)proposed) in
  let endpoint reference=obj ["node",actual reference;"port",get "port" reference] in
  let nodes=List.map(fun row->let model=get "model" row in
    obj ["id",actual row;"model",get "identity" model;"configuration_digest",get "configuration_digest" model])
    (items "nodes" union) in
  let wires=List.map(fun row->obj ["producer",endpoint(get "producer" row);"consumer",endpoint(get "consumer" row)])
    (items "wires" union) in
  let inputs=List.map(fun row->replace "consumer"(endpoint(get "consumer" row))row)(items "inputs" union) in
  let graph=get "implementation" candidate in
  require(Json.equal(get "nodes" graph)(arr nodes) && Json.equal(get "wires" graph)(arr wires) &&
    Json.equal(get "inputs" graph)(arr inputs) &&
    Json.equal(get "semantic_exports" graph)(arr(List.map endpoint(items "semantic_exports" union))))
    "Actual graph differs from independently authored complete ordered node, wire, input or export union";
  require(List.length nodes=(if state_reading then 19 else 17) &&
    List.length wires=(if state_reading then 27 else 24) && List.length proposed=List.length nodes)
    "Two-observation graph inventory changed";
  let bank node=actual(nr "control" node) in
  require(bank "evidence"<>bank "evidence_b" &&
    Json.equal(at ["binding";"observations"]candidate)(arr [
      obj ["source",str "condition_a";"bank",bank "evidence";"input",str "condition_a"];
      obj ["source",str "condition_b";"bank",bank "evidence_b";"input",str "condition_b"]]))
    "Distinct original observations lost their distinct memory and source input identity"

let positive fixture state_reading =
  let request,union=request_literal fixture state_reading and limits=get "limits" fixture in
  let compiled=compile request limits in
  let candidate=get "candidate" compiled in
  check_original_graph union candidate state_reading;
  let payload=invocation request candidate limits in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" payload in
  require(Json.equal compiled verified && get "artifact" compiled=Json.Null)
    "Producer and independent verifier disagree or compilation grants premature export";
  let report=checked verified in
  check_closure request report;
  List.iter(fun(key,value)->require(at ["preservation";"coverage";key]report=Json.int value)
    ("Original finite causal census changed: "^key))expected_coverage;
  require(at ["preservation";"coverage";"complete"]report=Json.Bool true)
    "Incomplete exploration became accepted prerequisite material";
  let requirements=at ["preservation";"requirements"]report |> Json.array in
  require(List.map(get "id")requirements=List.map str expected_requirements &&
    List.for_all(fun row->get "status" row=str "pass" && at ["histories";"pass"]row=Json.int 36)requirements)
    "Original hard requirements changed with prerequisite admission";
  require(at ["preservation";"program_coverage";"created_attempts"]report=Json.int 2 &&
    at ["preservation";"program_coverage";"nonvacuous"]report=Json.Bool true)
    "Shared success prefix was not exercised before independent uncertainty tails";
  List.iter(fun row->let id=Json.string(get "id" row) in
    if id="exclusive_selection" then
      require(Json.equal(get "coverage" row)(obj ["samples",Json.int 504;"active",Json.int 144;
        "inactive",Json.int 360;"enabled_triggers",Json.int 0]))
        "Safety census lost active or inactive independent subject samples"
    else require(at ["coverage";"enabled_triggers"]row=Json.int 72)
      "A complete history silently omitted a required request or initiation trigger")requirements;
  let carriers,links=expected_projections state_reading (source_models request) in
  let proposed=at ["assembly_proposal";"nodes"]candidate |> Json.array in
  let endpoint reference=
    let binding=List.find(fun row->get "slot" row=get "slot" reference &&
      get "node" row=get "node" reference)proposed in
    obj ["node",get "actual" binding;"port",get "port" reference] in
  let links=arr(List.map(fun row->row
    |> replace "producer_endpoint"(endpoint(get "producer_endpoint" row))
    |> replace "consumer_endpoint"(endpoint(get "consumer_endpoint" row)))(Json.array links)) in
  require(Json.equal(at ["assembly";"carrier_projections"]report)carriers &&
    Json.equal(at ["assembly";"link_projections"]report)links)
    "Prerequisite closure changed an original material carrier or typed link";
  require(Json.equal verified(call Service.handle Protocol.Verify "replay-policy-component-material"
    (add "report" verified payload))) "Fresh prerequisite replay failed";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" payload in
  let artifact=get "artifact" exported in
  let fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" in
  require(get "fasta" artifact=str fasta && get "fasta_sha256" artifact=str(Canonical.sha256 fasta))
    "Prerequisite closure changed the independently specified exact seventeen-base RNA";
  let manifest=get "manifest" artifact in
  require(get "profile" manifest=str material_profile && Json.equal(get "request" manifest)request &&
    Json.equal(get "candidate" manifest)candidate && Json.equal(get "assessment" manifest)report &&
    Json.equal(get "limits" manifest)limits)
    "Paired prerequisite manifest omitted complete original authority";
  require(get "members" manifest=arr [obj ["fasta_id",str "rna_0001";"member_id",str "payload";
    "molecule",N.to_json(expected_molecule());"sequence_sha256",str(Canonical.sha256 expected_sequence)]])
    "Emitted prerequisite molecule differs in exact regions, product, chemistry, origin or sequence";
  require(get "manifest_sha256" artifact=str(Canonical.sha256(Canonical.encode manifest)))
    "Manifest hash does not bind the actual paired bytes";
  request,limits,compiled

module Runtime = Bioc_candidate_runtime.Policy_primitives
let batch ?(observations=[]) tick : Runtime.input_batch = {tick;observations;feedback=[];lifecycle=[]}
let observation ?observed slot input tick evidence : Runtime.observation = {
  observation_id=slot^"/"^input^"/"^string_of_int tick;input_id=input;slot_id=slot;
  observed_tick=Option.value observed ~default:tick;observer="cell-1";
  subject=(if slot="e1"then "target-1"else "target-2");evidence}
let actual_node candidate slot node =
  let row=List.find(fun row->get "slot" row=str slot && get "node" row=str node)
    (at ["assembly_proposal";"nodes"]candidate |> Json.array) in Json.string(get "actual" row)
let truth_at frame node port slot value reasons =
  let actual=List.find(fun (row:Runtime.port_value)->row.endpoint.node_id=node &&
    row.endpoint.port_id=port && row.binding.slot=Some slot)frame.Runtime.outputs in
  require(match actual.signal with Runtime.Truth signal->signal.value=value && signal.reasons=reasons|_->false)
    ("Independent truth/reason oracle failed at "^node^"/"^port^"/"^slot^" tick "^string_of_int frame.tick)
let directed_runtime request candidate =
  let graph=I.of_json ~library:(I.library_of_json(source_models request))(get "implementation" candidate) in
  let environment:Runtime.environment={executor="cell-1";slots=[
    {slot_id="e1";target="target-1";start_tick=0};{slot_id="e2";target="target-2";start_tick=0}];horizon_ticks=6} in
  let limits:Runtime.limits={max_work=20_000_000;max_events=100_000;max_attempts=32;max_microsteps=100} in
  let initial=Runtime.initialize ~implementation:graph ~environment ~limits in
  let both tick value=List.concat_map(fun slot->List.map(fun input->observation slot input tick(Runtime.Known value))
    ["condition_a";"condition_b"])["e1";"e2"] in
  let node=actual_node candidate "control" in
  let zero,f0=Runtime.step initial(batch 0 ~observations:(both 0 false)) in
  let one,f1=Runtime.step zero(batch 1 ~observations:(both 1 true)) in
  require(f0.creations=[] && List.length f1.creations=2 &&
    List.map(fun(value:Runtime.attempt)->value.started_tick,value.deadline_tick)f1.creations=[1,3;1,3])
    "Both original subjects did not request and initiate exactly once on their shared known rising prefix";
  List.iter(fun slot->truth_at f0(node "all")"out"slot(Some I.False)[];
    truth_at f1(node "all")"out"slot(Some I.True)[];
    truth_at f1(node "selected")"value"slot(Some I.True)[];
    truth_at f1(node "excluded")"value"slot(Some I.False)[])["e1";"e2"];
  let two,f2=Runtime.step one(batch 2) in
  require(List.for_all(fun(value:Runtime.attempt)->value.status=Runtime.Active)f2.attempts)
    "Quiet tick advanced original attempt timeout early";
  let three,f3=Runtime.step two(batch 3) in
  truth_at f3(node "evidence")"value""e1"None[Runtime.Stale];
  truth_at f3(node "evidence_b")"value""e1"(Some I.True)[];
  truth_at f3(node "all")"out""e1"(Some I.Unknown)[Runtime.Stale];
  require(List.for_all(fun(value:Runtime.attempt)->value.status=Runtime.Timed_out)f3.attempts)
    "Known prefix attempts did not time out independently of observation uncertainty";
  let four,f4=Runtime.step three(batch 4) in
  truth_at f4(node "all")"out""e1"(Some I.Unknown)[Runtime.Stale;Runtime.Stale];
  let five,_=Runtime.step four(batch 5) in
  (* Literal six-by-six truth table, in no-row/false/true/missing/invalid/conflicting
     order. All 36 choices are explored; no candidate-selected precondition filters
     this original domain. Reasons retain the independent left-to-right channels. *)
  let choices=[None,[Runtime.Stale];Some(Runtime.Known false),[];Some(Runtime.Known true),[];
    Some Runtime.Missing_evidence,[Runtime.Missing];Some Runtime.Invalid_evidence,[Runtime.Invalid];
    Some Runtime.Conflicting_evidence,[Runtime.Conflicting]] in
  let expected=[
    [I.Unknown;I.False;I.Unknown;I.Unknown;I.Unknown;I.Unknown];
    [I.False;I.False;I.False;I.False;I.False;I.False];
    [I.Unknown;I.False;I.True;I.Unknown;I.Unknown;I.Unknown];
    [I.Unknown;I.False;I.Unknown;I.Unknown;I.Unknown;I.Unknown];
    [I.Unknown;I.False;I.Unknown;I.Unknown;I.Unknown;I.Unknown];
    [I.Unknown;I.False;I.Unknown;I.Unknown;I.Unknown;I.Unknown]] in
  let totals=ref(0,0,0) in
  List.iteri(fun i(a,reasons_a)->List.iteri(fun j(b,reasons_b)->
    let rows=List.filter_map(fun(input,evidence)->Option.map(observation "e1" input 6)evidence)
      ["condition_a",a;"condition_b",b] in
    let _,frame=Runtime.step five(batch 6 ~observations:rows) in
    let expected=List.nth(List.nth expected i)j in
    truth_at frame(node "all")"out""e1"(Some expected)(reasons_a@reasons_b);
    truth_at frame(node "all")"out""e2"(Some I.Unknown)[Runtime.Stale;Runtime.Stale];
    require(frame.creations=[] && not(List.exists(fun(event:Runtime.event)->
      event.kind=Runtime.Primitive_event I.Rising)frame.events))
      "Final unknown-to-known evidence fabricated a rising edge or an out-of-horizon progress obligation";
    let f,t,u= !totals in totals:=(match expected with I.False->f+1,t,u|I.True->f,t+1,u|I.Unknown->f,t,u+1))choices)choices;
  require(!totals=(11,1,24)) "Independent 36-history final truth census changed";
  phase "directed asymmetric evidence and ordered uncertainty";
  List.iter(fun(a,b,reasons,value)->
    let _,frame=Runtime.step one(batch 2 ~observations:[observation "e1" "condition_a" 2 a;
      observation "e1" "condition_b" 2 b]) in
    truth_at frame(node "all")"out""e1"(Some value)reasons;
    truth_at frame(node "all")"out""e2"(Some I.True)[];
    if value=I.False then (
      truth_at frame(node "selected")"value""e1"(Some I.False)[];
      truth_at frame(node "excluded")"value""e1"(Some I.True)[]))[
      Runtime.Known false,Runtime.Known true,[],I.False;
      Runtime.Known true,Runtime.Known false,[],I.False;
      Runtime.Missing_evidence,Runtime.Invalid_evidence,[Runtime.Missing;Runtime.Invalid],I.Unknown;
      Runtime.Invalid_evidence,Runtime.Missing_evidence,[Runtime.Invalid;Runtime.Missing],I.Unknown;
      Runtime.Invalid_evidence,Runtime.Invalid_evidence,[Runtime.Invalid;Runtime.Invalid],I.Unknown;
      Runtime.Known false,Runtime.Invalid_evidence,[Runtime.Invalid],I.False];
  phase "independent observed and available timestamps";
  let delayed,fresh=Runtime.step two(batch 3 ~observations:[
    observation ~observed:2 "e1" "condition_a" 3(Runtime.Known true);
    observation ~observed:3 "e1" "condition_b" 3(Runtime.Known true)]) in
  List.iter(fun(name,observed)->let row=List.find(fun(row:Runtime.evidence_snapshot)->row.bank=node name &&
    row.binding.slot=Some "e1")fresh.evidence in
    require(row.observed_tick=Some observed && row.available_tick=Some 3)
      "Separate source observation/availability timestamps were collapsed") ["evidence",2;"evidence_b",3];
  let _,fresh4=Runtime.step delayed(batch 4) in
  truth_at fresh4(node "evidence")"value""e1"None[Runtime.Stale];
  truth_at fresh4(node "evidence_b")"value""e1"(Some I.True)[];
  truth_at fresh4(node "all")"out""e1"(Some I.Unknown)[Runtime.Stale]

let candidate_negatives request limits compiled =
  let candidate=get "candidate" compiled in
  let reject ?(code="policy_implementation_source_binding") label changed = phase("candidate negative: "^label);
    rejected code label(fun()->S.check ~export:false ~request ~candidate:changed ~limits) in
  let bank=actual_node candidate "control" in
  reject ~code:"policy_implementation_binding" "Aliased observation memory"(put ["binding";"observations";"1";"bank"](str(bank "evidence"))candidate);
  reject "Swapped declaration anchor order"(edit ["binding";"observations"](fun rows->arr(List.rev(Json.array rows)))candidate);
  reject ~code:"policy_implementation_binding" "Aliased external observation input"(put ["binding";"observations";"1";"input"](str "condition_a")candidate);
  let reverse_wires=edit ["implementation";"wires"](fun rows->arr(List.map(fun row->
    if at ["consumer";"node"]row=str(bank "all") then
      let port=at ["consumer";"port"]row in
      if port=str "in0"then put ["producer";"node"](str(bank "evidence_b"))row
      else if port=str "in1"then put ["producer";"node"](str(bank "evidence"))row else row
    else row)(Json.array rows)))candidate in
  reject "Boolean-equivalent reversed operands change ordered reasons" reverse_wires;
  let a=List.find(fun row->get "id" row=str(bank "evidence"))(at ["implementation";"nodes"]candidate |> Json.array) in
  let wrong_freshness=edit ["implementation";"nodes"](fun rows->arr(List.map(fun row->
    if get "id" row=str(bank "evidence_b") then row |> replace "model"(get "model" a)
      |> replace "configuration_digest"(get "configuration_digest" a) else row)(Json.array rows)))candidate in
  reject "Second bank cannot borrow first observation freshness" wrong_freshness;
  let wrong_channel=edit ["implementation";"inputs"](fun rows->arr(List.map(fun row->
    if get "id" row=str "condition_a"then put ["consumer";"node"](str(bank "evidence_b"))row
    else if get "id" row=str "condition_b"then put ["consumer";"node"](str(bank "evidence"))row else row)(Json.array rows)))candidate in
  reject "Same-subject source channels cannot be swapped" wrong_channel;
  phase "source input binding and profile remain closed";
  rejected "policy_component_material_request" "Wrong original channel source is not an alias"
    (fun()->S.check ~export:false ~request:(put ["input_bindings";"1";"source"](str "condition_a")request)~candidate ~limits);
  let same_coherence=request |> edit ["implementation_request";"document";"program";"declarations"]
    (fun rows->arr(List.map(fun row->if get "id" row=str "condition_b"then replace "coherence"(str "frame_a")row
      else row)(Json.array rows))) in
  rejected "policy_implementation_lowering_unsupported" "Separate observations require distinct original coherence groups"
    (fun()->compile same_coherence limits);
  let legacy=request |> replace "schema_version"(str "biocompiler.policy_component_material_request.v0.3")
    |> replace "profile"(str "biocompiler.policy_instance_prerequisite_mrna.v0.1")
    |> put ["implementation_request";"schema_version"](str "biocompiler.policy_realization_request.v0.2")
    |> put ["implementation_request";"profile"](str "biocompiler.policy_prerequisite_realization_inputs.v0.1")
    |> put ["context";"profile"](str "biocompiler.policy_instance_prerequisite_mrna.v0.1") in
  rejected "policy_implementation_lowering_unsupported" "Legacy source profile still admits only one observation"
    (fun()->compile legacy limits)

let nonaccepted_original fixture =
  phase "complete uncertainty-only original must remain nonaccepted";
  let request,_=request_literal fixture false in
  let old=at ["implementation_request";"operating_domain"]request in
  let rows=List.map(fun row->if get "available_tick" row=Json.int 1 && get "observation" row=str "condition_b"then
    row |> replace "status"(str "invalid") |> replace "value" Json.Null else row)fixed_prefix in
  let domain=old |> replace "fixed_observations"(arr rows) |> replace "observation_factors"(arr []) in
  let layout=get "record_layout"(get "context" request) |> replace "domain_digest"(str(Canonical.fingerprint domain)) in
  let request=request |> put ["implementation_request";"operating_domain"]domain
    |> put ["context";"record_layout"]layout
    |> edit ["context";"providers"](fun values->arr(List.map(fun provider->
      let body=get "body" provider in
      let body=if get "kind" body=str "environment"then replace "grammar"domain body else body in
      provider |> replace "body"body |> edit ["body";"capacities"](fun rows->arr(List.map
        (replace "record_layout_digest"(str(Canonical.fingerprint layout)))(Json.array rows))) |> repin)(Json.array values))) in
  let limits=get "limits" fixture in
  let compiled=compile request limits in
  let report=not_accepted "Uncertainty without any enabled original progress event" compiled in
  require(at ["preservation";"coverage";"complete"]report=Json.Bool true &&
    at ["preservation";"coverage";"histories"]report=Json.int 1 &&
    at ["preservation";"coverage";"transitions"]report=Json.int 7 &&
    at ["preservation";"preservation"]report=str "pass" &&
    at ["preservation";"status"]report=str "requirements_not_satisfied" &&
    at ["preservation";"program_coverage";"created_attempts"]report=Json.int 0)
    "Nonvacuity was weakened or complete uncertainty was mistaken for preservation failure";
  require(List.for_all(fun row->get "status" row=str "unknown" && get "nonvacuous" row=Json.Bool false)
    (at ["preservation";"requirements"]report |> Json.array))
    "An unexercised original hard requirement was promoted to acceptance";
  rejected "policy_component_material_export_not_accepted" "Nonvacuous hard requirements still guard export"
    (fun()->S.check ~export:true ~request ~candidate:(get "candidate" compiled)~limits)

let () =
  try
    require(Array.length Sys.argv=3) "Supply the two complete original A/B inputs";
    let a=read Sys.argv.(1) and b=read Sys.argv.(2) in
    phase "service A: complete independently factored two-observation domain";
    let request,limits,compiled=positive a false in
    phase "service B: state-dependent guard retains both original observation channels";
    ignore(positive b true);
    directed_runtime request(get "candidate" compiled);
    candidate_negatives request limits compiled;
    nonaccepted_original a;
    Printf.printf "two-observation material service: %d independent controls passed\n" !checks
  with Diagnostic.Error value->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None->"<none>"|Some path->path)value.message;exit 1
