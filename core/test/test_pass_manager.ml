open Bioc_wire
module C = Bioc_domain.Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module E = Bioc_domain.Realization_evidence
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let same a b = Canonical.encode a=Canonical.encode b
let str value=Json.String value
let read path = let channel=open_in_bin path in
  let raw=really_input_string channel (in_channel_length channel) in close_in channel;Json.parse raw
let rejected fragment action = match action () with
  | _ -> failwith ("Rejected manager action accepted: "^fragment)
  | exception Diagnostic.Error error ->
    let size=String.length fragment in
    let rec contains offset=offset+size<=String.length error.message &&
      (String.sub error.message offset size=fragment || contains(offset+1)) in
    require(contains 0) ("Wrong manager rejection: "^error.message)
let budget maximum=W.create ~profile:"pipeline.literal" ~error_code:"pipeline_literal_exhausted" ~maximum ()
let default_work=1_000_000_000
let document schema value kind=Json.Object["schema_version",str schema;
  "nodes",Json.Array[Json.Object["id",str "n";"kind",str kind;"value",Json.int value]]]
let checked_decision outcome detail work _context=
  let limits=C.Codec.make_limits ~charge:(W.charge work) () in
  M.Decision(C.Check_decision.make ~limits ~outcome ~detail ())
let decision work context=checked_decision E.Pass "Independently matched the expected value." work context
let proposal ?(value=1) ?(kind="constant") ?(links=true) ?(source="n")
    ?(obligations=[]) ?(mapping=Json.Object["output",str "n"]) contract work _context=
  let limits=C.Codec.make_limits ~charge:(W.charge work) () in
  M.Proposal(C.Pass_result.make ~limits
    ~output:(Some(document (C.Pass_contract.output_schema contract) value kind)) ~obligations
    ~source_links:(if links then [C.Source_link.make ~limits ~requirement_id:"r" ~source_node_id:source
      ~target_node_id:"n" ~pass_name:(C.Pass_contract.id contract) ()] else []) ~observation_map:mapping ())
type fixture={manager:M.t;first:C.Pass_contract.t;second:C.Pass_contract.t;work:W.t}
let setup ?limits ?(maximum=default_work) baseline=
  let work=budget maximum in
  let target=Bioc_domain.Build_request.Target.of_json(get "target" baseline) in
  let dependencies=Json.object_fields(get "initial_dependencies" baseline) |> List.map(fun(k,v)->k,Json.string v) in
  (* Python constructs these roots in request,registry order. Canonical fixture
     objects sort keys, so retain that independently documented construction order. *)
  let dependencies=List.map(fun key->key,List.assoc key dependencies)["request";"registry"] in
  let manager=M.create ~budget:work ?limits ~target ~dependencies
      ~completion_profiles:[C.Completion_profile.of_json(get "completion" baseline)] () in
  ignore(M.add_input manager ~identity:"input" ~requirements:["r"]
      ~obligations:(Json.array(get "initial_obligations" baseline) |> List.map C.Scoped_obligation.of_json)
      (get "input" baseline));
  {manager;first=C.Pass_contract.of_json(get "first" baseline);
    second=C.Pass_contract.of_json(get "second" baseline);work}
let first ?(validator=decision) ?producer fixture=
  let producer=match producer with Some value->value | None->proposal fixture.first in
  M.register fixture.manager fixture.first ~producer ~validators:["identity_check",validator];
  M.run fixture.manager ~pass_id:"lower" ~input_id:"input" ~output_id:"behavior" ()
let second ?(validator=decision) ?contract ?producer fixture=
  let contract=Option.value contract ~default:fixture.second in
  let producer=match producer with Some value->value | None->proposal contract in
  M.register fixture.manager contract ~producer ~validators:["response_check",validator];
  M.run fixture.manager ~pass_id:"generate" ~input_id:"behavior" ~output_id:"mechanism"
    ~configuration:(Json.Object["seed",Json.int 7;"tie_break",str "id"]) ()
let complete fixture=ignore(first fixture);second fixture
let changed contract key value=C.Pass_contract.of_json(set key value(C.Pass_contract.to_json contract))
let () =
  require(Array.length Sys.argv=2) "Expected independent manager fixture path";
  let literal_fixture=read Sys.argv.(1) in
  let baseline=get "manager_baseline" literal_fixture in
  let fixture=setup baseline in
  let mechanism=complete fixture in
  List.iter(fun identity->
    require(same(C.Stage_record.to_json(M.get fixture.manager identity)) (get identity(get "records" baseline)))
      (identity^": complete original stage differs"))["input";"behavior";"mechanism"];
  require(same(C.Pipeline_result.to_json(M.result fixture.manager ~identity:"mechanism" ~scope:"synthetic"))
      (get "result" baseline)) "Complete scope/result/unresolved obligations differ";
  require(C.Stage_record.fingerprint mechanism=C.Stage_record.fingerprint(complete(setup baseline)))
    "Repeated manager run changed complete record identity";
  let partial=setup baseline in ignore(first partial);
  require(C.Pipeline_result.status(M.result partial.manager ~identity:"behavior" ~scope:"synthetic")=C.Partial)
    "An intermediate stage completed the final scope";
  rejected "Unsupported completion" (fun()->M.result partial.manager ~identity:"behavior" ~scope:"full_payload");
  M.set_dependency fixture.manager "request" (Canonical.fingerprint(str "new_request"));
  List.iter(fun id->rejected "Stale" (fun()->M.get fixture.manager id))["input";"behavior";"mechanism"];
  let fixture=setup baseline in
  M.set_dependency fixture.manager "model" (Canonical.fingerprint(str "model1"));ignore(complete fixture);
  M.set_dependency fixture.manager "model" (Canonical.fingerprint(str "model2"));
  rejected "model" (fun()->M.result fixture.manager ~identity:"mechanism" ~scope:"synthetic");
  rejected "Target dependency" (fun()->M.set_dependency fixture.manager "target" (Canonical.fingerprint(str "changed")));
  let fixture=setup baseline in ignore(complete fixture);
  let newer=changed fixture.first "version" (str "2") in
  M.register fixture.manager newer ~producer:(proposal newer) ~validators:["identity_check",decision];
  rejected "pass contract" (fun()->M.get fixture.manager "mechanism");
  let fixture=setup baseline in ignore(first fixture);
  rejected "increment" (fun()->M.register fixture.manager fixture.first ~producer:(proposal fixture.first)
      ~validators:["identity_check",decision]);
  List.iter(fun outcome->
    let fixture=setup baseline in
    let record=first ~validator:(checked_decision outcome "Unestablished preservation.") fixture in
    require(not(C.Stage_record.accepted record)) "Nonpassing check was accepted";
    require(get "outcome" (get "identity_check" (C.Stage_record.checks record))=str(C.outcome_name outcome))
      "Recorded nonpassing outcome changed";
    rejected "not passed" (fun()->M.get fixture.manager "behavior"))[E.Fail;E.Unknown;E.Unsupported];
  let fixture=setup baseline in
  let independently_equal _work context=
    let node raw=List.hd(Json.array(get "nodes" raw)) |> get "value" in
    let valid=same(node(C.Pass_context.input context))(node(Option.get(C.Pass_context.output context))) in
    M.Decision(C.Check_decision.make ~outcome:(if valid then E.Pass else E.Fail) ~detail:"Checked input value." ()) in
  require(not(C.Stage_record.accepted(first ~validator:independently_equal ~producer:(proposal ~value:9 fixture.first) fixture)))
    "Internally consistent wrong value bypassed independent provider";
  let fixture=setup baseline in
  let forged=C.Producer_obligation.make ~requirement_id:"identity" ~description:"Only check something easier."
      ~evidence_kind:E.Exact ~evidence_refs:["self_reported_pass"] () in
  rejected "authoritative obligation" (fun()->first ~producer:(proposal ~obligations:[forged] fixture.first) fixture);
  let fixture=setup baseline in let provider=proposal fixture.first in
  rejected "provider" (fun()->M.register fixture.manager fixture.first ~producer:provider ~validators:[]);
  rejected "certify itself" (fun()->M.register fixture.manager fixture.first ~producer:provider ~validators:["identity_check",provider]);
  let fixture=setup baseline in ignore(first fixture);
  let spec=C.Check_spec.make ~id:"response_check" ~evidence_kind:E.Exact ~discharges:["response"] () in
  let bad=changed fixture.second "checks" (Json.Array[C.Check_spec.to_json spec]) in
  rejected "evidence kind" (fun()->second ~contract:bad fixture);
  let fixture=setup baseline in rejected "every input requirement" (fun()->first ~producer:(proposal ~links:false fixture.first) fixture);
  let fixture=setup baseline in ignore(first fixture);
  rejected "observation mapping" (fun()->second ~producer:(proposal ~mapping:(Json.Object[]) fixture.second) fixture);
  let fixture=setup baseline in rejected "unknown requirement or node" (fun()->first ~producer:(proposal ~source:"wrong" fixture.first) fixture);
  let fixture=setup baseline in rejected "Missing pass" (fun()->M.run fixture.manager ~pass_id:"missing" ~input_id:"input" ~output_id:"out" ());
  M.register fixture.manager fixture.second ~producer:(proposal fixture.second) ~validators:["response_check",decision];
  rejected "ordering" (fun()->M.run fixture.manager ~pass_id:"generate" ~input_id:"input" ~output_id:"out" ());
  rejected "Unsupported destination" (fun()->first ~producer:(proposal ~kind:"unimplemented" fixture.first) fixture);
  let fixture=setup baseline in
  let fixture={fixture with first=changed fixture.first "dependency_keys" (Json.Array[str "absent_model"])} in
  rejected "absent_model" (fun()->first fixture);
  let fixture=setup baseline in
  let fixture={fixture with first=changed fixture.first "targets" (Json.Array[str "DNA"])} in
  rejected "requested target" (fun()->first fixture);
  let fixture=setup baseline in
  rejected "request identity" (fun()->M.add_input fixture.manager ~identity:"wrong" (document "intent.v1" 9 "constant"));
  ignore(first fixture);
  let invalidating=fixture.second |> fun c->changed c "changed_properties" (Json.Array[str "layout"])
      |> fun c->changed c "invalidated_analyses" (Json.Array[str "identity"]) in
  ignore(second ~contract:invalidating fixture);
  let result=M.result fixture.manager ~identity:"mechanism" ~scope:"synthetic" in
  require(C.Pipeline_result.status result=C.Partial &&
      List.exists(fun obligation->C.Scoped_obligation.id obligation="identity")(C.Pipeline_result.unresolved result))
    "Invalidated analysis retained an upstream discharge";
  let fixture=setup baseline in
  let mutate work context=M.set_dependency fixture.manager "registry" (Canonical.fingerprint(str "v2"));decision work context in
  rejected "Stale" (fun()->first ~validator:mutate fixture);
  rejected "Stale" (fun()->M.get fixture.manager "behavior");
  let fixture=setup baseline in
  let none _work _context=M.Proposal(C.Pass_result.make ~output:None ~obligations:[] ~source_links:[]
      ~search_status:"no_candidate_found" ()) in
  M.register fixture.manager fixture.first ~producer:none ~validators:["identity_check",decision];
  let configuration=Json.Object["seed",Json.int 1;"budget",Json.int 2] in
  (match M.run fixture.manager ~pass_id:"lower" ~input_id:"input" ~output_id:"behavior" ~configuration () with
   | _->failwith "No-candidate search became a stage"
   | exception M.No_candidate_found value ->require(same value.configuration configuration && value.pass_id="lower")
       "No-candidate lost its complete configuration");
  rejected "Missing artifact" (fun()->M.get fixture.manager "behavior");
  let fixture=setup baseline in
  let original_provider=proposal fixture.first in ignore(first ~producer:original_provider fixture);
  let newer=changed fixture.first "version" (str "2") in
  M.register fixture.manager newer ~producer:(proposal newer) ~validators:["identity_check",decision];
  rejected "increment" (fun()->M.register fixture.manager fixture.first ~producer:(proposal fixture.first)
      ~validators:["identity_check",decision]);
  M.register fixture.manager fixture.first ~producer:original_provider ~validators:["identity_check",decision];
  ignore(M.get fixture.manager "behavior");
  M.set_dependency fixture.manager "later_root" (Canonical.fingerprint(str "later"));
  ignore(M.get fixture.manager "behavior");
  let fixture=setup baseline in
  rejected "explicit CheckDecision" (fun()->first ~validator:(fun _ _->M.Invalid_return Json.Null) fixture);
  let fixture=setup baseline in
  rejected "candidate PassResult" (fun()->first ~producer:(fun _ _->M.Invalid_return Json.Null) fixture);
  let fixture=setup baseline in
  rejected "already registered" (fun()->M.register_completion_profile fixture.manager
      (C.Completion_profile.make ~scope:"synthetic" ~stage:C.Intent ~schema:"intent.v1" ~obligations:["identity"] ()));
  (* Controlled Components roots are checked from supplied request authority.
     Neither an input accepted flag nor a historical Stage_record is imported. *)
  let admission=get "admission_baseline" literal_fixture in
  require(get "assertion_status" admission=str "passed") "Original admission assertion did not pass";
  let policy=C.Component_input_contract.of_json(get "contract" admission) in
  let payload=get "payload" admission in
  let make_admission raw=
    let dependencies=get "dependencies" admission |> Json.object_fields in
    let dependencies=["request",Canonical.fingerprint raw;"registry",Json.string(List.assoc "registry" dependencies)] in
    M.create ~budget:(budget default_work) ~target:(Bioc_domain.Build_request.Target.of_json(get "target" admission))
      ~dependencies () in
  let verify work context=
    let selected=get "nodes" (C.Pass_context.input context) |> Json.array |> List.hd |> get "selected" in
    checked_decision (if selected=Json.int 1 then E.Pass else E.Fail) "Compared with independent selection." work context in
  let manager=make_admission payload in
  M.register_component_input manager policy ~validators:["selection",verify];
  let record=M.admit_component_input manager ~contract_id:"admit" ~identity:"selected" payload in
  require(same(C.Stage_record.to_json record)(get "record" admission)) "Complete original admission record differs";
  ignore(M.get manager "selected");
  rejected "new pipeline" (fun()->M.admit_component_input manager ~contract_id:"admit" ~identity:"another" payload);
  let manager=make_admission payload in
  rejected "Only authoritative intent" (fun()->M.add_input manager ~identity:"unsafe" ~stage:C.Components payload);
  M.register_component_input manager policy ~validators:["selection",verify];
  rejected "identity" (fun()->M.admit_component_input manager ~contract_id:"admit" ~identity:"selected" (set "extra" (str "changed") payload));
  List.iter(fun raw->
    let manager=make_admission raw in
    M.register_component_input manager policy ~validators:["selection",verify];
    rejected "inventory" (fun()->M.admit_component_input manager ~contract_id:"admit" ~identity:"selected" raw))
    [set "nodes" (Json.Array[]) payload;
     set "nodes" (Json.Array[Json.Object["id",str "part";"kind",str "fake"]]) payload;
     set "nodes" (Json.Array(Json.array(get "nodes" payload)@Json.array(get "nodes" payload))) payload];
  let forged=set "accepted" (Json.Bool true) (set "nodes"
      (Json.Array[Json.Object["id",str "part";"kind",str "component_instance";"selected",Json.int 9]]) payload) in
  let manager=make_admission forged in
  M.register_component_input manager policy ~validators:["selection",verify];
  let rejected_record=M.admit_component_input manager ~contract_id:"admit" ~identity:"selected" forged in
  require(not(C.Stage_record.accepted rejected_record)) "Supplied accepted flag replaced independent admission";
  rejected "not passed" (fun()->M.get manager "selected");
  let manager=make_admission payload in
  let mutate work context=M.set_dependency manager "registry" (Canonical.fingerprint(str "changed"));verify work context in
  M.register_component_input manager policy ~validators:["selection",mutate];
  rejected "Stale" (fun()->M.admit_component_input manager ~contract_id:"admit" ~identity:"selected" payload);
  rejected "Stale" (fun()->M.get manager "selected");
  let first_budget=setup baseline in ignore(complete first_budget);
  let charged=default_work-W.remaining first_budget.work in
  let exact=setup ~maximum:charged baseline in ignore(complete exact);
  require(W.remaining exact.work=0) "Manager did not use the same lifetime ancestor";
  (match let short=setup ~maximum:(charged-1) baseline in complete short with
   | _->failwith "Manager escaped short lifetime ancestor"
   | exception Diagnostic.Error error->require(error.code="pipeline_literal_exhausted") "Manager obscured ancestor exhaustion");
  let fixture=setup ~limits:(M.make_limits ~max_records:1 ()) baseline in
  rejected "limit" (fun()->first fixture);
  let fixture=setup ~limits:(M.make_limits ~max_providers:1 ()) baseline in
  rejected "limit" (fun()->first fixture);
  rejected "limit" (fun()->setup ~limits:(M.make_limits ~max_retained_items:1 ()) baseline);
  rejected "limit" (fun()->setup ~limits:(M.make_limits ~max_retained_bytes:1 ()) baseline);
  rejected "resource boundary" (fun()->setup ~limits:(M.make_limits ~max_document_bytes:1 ()) baseline);
  rejected "resource boundary" (fun()->setup ~limits:(M.make_limits ~max_document_nodes:1 ()) baseline);
  let fixture=setup ~limits:(M.make_limits ~max_ancestor_depth:1 ()) baseline in
  rejected "ancestry" (fun()->first fixture);
  let fixture=setup ~limits:(M.make_limits ~max_call_depth:1 ()) baseline in
  let reenter work context=M.set_dependency fixture.manager "nested" (Canonical.fingerprint(str "nested"));decision work context in
  rejected "reentrancy" (fun()->first ~validator:reenter fixture);
  print_endline "Checked manager: complete original baseline, independent checks, scoped completion, rejected stages, provider identity, ancestor freshness and lifetime budgets passed"
