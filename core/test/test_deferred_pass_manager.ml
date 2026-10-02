open Bioc_wire
module C = Bioc_domain.Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module E = Bioc_domain.Realization_evidence
let require value message=if not value then failwith message
let str value=Json.String value
let obj value=Json.Object value
let get key raw=Json.field key (Json.object_fields raw)
let set key value raw=obj((key,value)::List.remove_assoc key (Json.object_fields raw))
let same left right=Canonical.encode left=Canonical.encode right
let read path=let channel=open_in_bin path in
  Fun.protect (fun()->Json.parse(really_input_string channel (in_channel_length channel)))
    ~finally:(fun()->close_in channel)
let truth=function
  | Json.Null | Json.Bool false | Json.String "" | Json.Array [] | Json.Object []->false
  | Json.Int value->not(Z.equal value Z.zero) | Json.Float value->value<>0. | _->true
let literal=function
  | M.Json_value value->value | M.Json_set values->Json.Array values
  | M.Evidence_kind value->str(C.evidence_kind_name value)
  | M.Check_outcome value->str(C.outcome_name value)
(* These capabilities are actual local closures, not serialized decisions. They
   model boxed objects and record each manager-requested evaluation boundary. *)
let rec box ?(classes=[]) ?(fields=[]) ?(event=(fun _->())) raw =
  let rec value : M.host_value={
    attribute=(fun work key->event("attribute:"^key);match List.assoc_opt key fields with
      | Some value->value
      | None when key="to_dict"->{value with call=(fun _ _->value)}
      | None when key="strip"->let trimmed=box(str(String.trim(Json.string raw))) in
          {trimmed with call=(fun _ _->trimmed)}
      | None->(match raw with Json.Object entries->box(List.assoc key entries)
        | _->ignore work;failwith("Missing mock attribute "^key)));
    attribute_default=(fun work key default->event("default:"^key);
      match List.assoc_opt key fields with Some result->result
      | None->ignore work;box(literal default));
    is_instance=(fun _ kind->List.mem kind classes || match kind,raw with
      | M.Mapping,Json.Object _ | M.String,Json.String _->true | _->false);
    is_none=(fun _->raw=Json.Null);
    truth=(fun _->truth raw);
    compare=(fun _ comparison expected->let equal=Json.equal raw (literal expected) in
      match comparison with M.Eq|M.Is->equal | M.Ne->not equal);
    contains=(fun _ container->let values=match literal container with
      | Json.Array values->values | Json.Object values->List.map(fun(key,_)->str key) values
      | _->failwith "Invalid mock container" in List.exists(Json.equal raw) values);
    attribute_set_equal=(fun work values ~attribute expected->
      let actual=List.map(fun value->let item=value.M.attribute work attribute in item.M.freeze work) values in
      let expected=Json.array(literal expected) in
      List.for_all(fun value->List.exists(Json.equal value) expected) actual &&
      List.for_all(fun value->List.exists(Json.equal value) actual) expected);
    source_link_set_equal=(fun work values expected->
      let actual=List.map(fun value->value.M.freeze work) values in
      let expected=List.map C.Source_link.to_json expected in
      List.for_all(fun value->List.exists(Json.equal value) expected) actual &&
      List.for_all(fun value->List.exists(Json.equal value) actual) expected);
    lookup=(fun _ entries->List.assoc(Json.string raw) entries);
    get_item=(fun _ key->event "get_item";box(get (Json.string(literal key)) raw));
    get=(fun _ key->event("get:"^key);box(match raw with
      | Json.Object fields->Option.value ~default:Json.Null (List.assoc_opt key fields)
      | _->failwith "Mock get on nonmapping"));
    tuple=(fun _->event "tuple";List.map box (Json.array raw));
    iter=(fun _->event "iter";let values=ref(List.map box (Json.array raw)) in
      {M.next=(fun _->event "next";match !values with []->None
        | item::rest->values:=rest;Some item)});
    call=(fun _ _->failwith "Mock object is not callable");
    merge=(fun _ ~before ~after->
      let merged=List.fold_left(fun raw(key,value)->set key value raw) before
        (Json.object_fields raw @ Json.object_fields after) in box merged);
    document=(fun _->event "document";value);
    freeze=(fun _->event "freeze";raw);
    vars=(fun _->event "vars";value);
  } in value
let collection ?(event=(fun _->())) values=
  let base=box(Json.Array[]) in
  {base with tuple=(fun _->event "tuple";values);
    iter=(fun _->event "iter";let rest=ref values in
      {M.next=(fun _->event "next";match !rest with []->None|value::tail->rest:=tail;Some value)})}
let rejected fragment action=match action () with
  | _->failwith("Unexpected acceptance: "^fragment)
  | exception Diagnostic.Error error->
      let n=String.length fragment in
      let rec has index=index+n<=String.length error.message &&
        (String.sub error.message index n=fragment || has(index+1)) in
      require(has 0)("Wrong rejection: "^error.message)
let work ()=W.create ~profile:"pipeline.deferred.test" ~error_code:"deferred_test_limit" ~maximum:1_000_000_000 ()
let dependencies raw=List.map(fun key->key,Json.string(get key raw))["request";"registry"]
let make_manager baseline=M.create ~budget:(work ())
  ~target:(Bioc_domain.Build_request.Target.of_json(get "target" baseline))
  ~dependencies:(dependencies(get "initial_dependencies" baseline)) ()
let add_root manager baseline=ignore(M.add_input manager ~identity:"input" ~requirements:["r"]
  ~obligations:(List.map C.Scoped_obligation.of_json(Json.array(get "initial_obligations" baseline))) (get "input" baseline))
let setup baseline=let manager=make_manager baseline in add_root manager baseline;manager
let run manager=M.run manager ~pass_id:"lower" ~input_id:"input" ~output_id:"behavior" ()
let register manager contract producer validator=M.register manager contract ~producer ~validators:["identity_check",validator]
let logged events prefix action=events:= !events@[prefix^action]
let proposal events contract ?(status="candidate") ?(obligations=[]) ?links ()=
  let raw=obj["schema_version",str "behavior.v1";
    "nodes",Json.Array[obj["id",str "n";"kind",str "constant";"value",Json.int 1]]] in
  let pass_id=Json.string(get "id" (get "first" contract)) in
  let link_raw=obj["requirement_id",str "r";"source_node_id",str "n";"target_node_id",str "n";"pass_name",str pass_id] in
  let links=Option.value links ~default:[box ~classes:[M.Source_link] ~event:(logged events "link.") link_raw] in
  box ~classes:[M.Pass_result] ~event:(logged events "proposal.") ~fields:[
    "search_status",box(str status);"output",box ~event:(logged events "output.") raw;
    "source_links",collection ~event:(logged events "links.") links;
    "observation_map",box(obj["output",str "n"]);
    "obligations",collection ~event:(logged events "obligations.") obligations] Json.Null
let decision ?(actual=E.Pass) baseline=
  ignore baseline;
  let raw=obj["outcome",str "pass";"detail",str "Independently matched the expected value.";"evidence",obj[]] in
  box ~classes:[M.Check_decision] ~fields:["outcome",box(str(C.outcome_name actual))] raw
let hosted manager events proposal decision=
  let producer=M.bind_host_provider manager (fun _ _->events:= !events@["producer"];proposal) in
  let validator=M.bind_host_provider manager (fun _ _->events:= !events@["validator"];decision) in
  producer,validator
let index events expected=
  let rec find i=function []->failwith("Missing event "^expected)|value::rest->if value=expected then i else find(i+1)rest in
  find 0 events
let absent events prefix=not(List.exists(fun value->String.starts_with ~prefix value) events)
let ()=
  require(Array.length Sys.argv=2) "Expected independent manager fixture path";
  let fixture=read Sys.argv.(1) in
  let baseline=get "manager_baseline" fixture in
  let contract=C.Pass_contract.of_json(get "first" baseline) in
  let events=ref [] in
  let manager=setup baseline in
  let producer,validator=hosted manager events (proposal events baseline ()) (decision baseline) in
  register manager contract producer validator;
  let record=run manager in
  require(same(C.Stage_record.to_json record)(get "behavior" (get "records" baseline)))
    "Deferred candidate/check result differs from the independent original record";
  require(index !events "links.tuple" < index !events "link.attribute:pass_name") "Links validated before tuple consumption";
  require(index !events "link.attribute:source_node_id" < index !events "proposal.attribute:observation_map") "Correspondence order changed";
  require(index !events "obligations.next" < index !events "validator") "Obligations consumed after validator";
  require(index !events "validator" < index !events "link.vars") "Source-link provenance frozen before validators";
  require(M.callback_source_links manager=None) "Host source-link sidecar escaped callback dynamic extent";
  let events=ref [] in let manager=setup baseline in
  let producer,validator=hosted manager events (proposal events baseline ~status:"unknown" ()) (decision baseline) in
  register manager contract producer validator;
  rejected "Unknown search outcome" (fun()->run manager);
  require(absent !events "proposal.attribute:output" && absent !events "validator") "Invalid search status touched deferred output";
  let events=ref [] in let manager=setup baseline in
  let wrong=box ~classes:[M.Source_link] ~event:(logged events "wrong.")
    (obj["pass_name",str "wrong"]) in
  let producer,validator=hosted manager events (proposal events baseline ~links:[wrong] ()) (decision baseline) in
  register manager contract producer validator;
  rejected "Invalid source correspondence" (fun()->run manager);
  require(absent !events "wrong.attribute:requirement_id" && absent !events "validator") "Invalid link read later fields";
  let events=ref [] in let manager=setup baseline in
  let bad=box ~event:(logged events "obligation.") (obj["requirement_id",str "unknown"]) in
  let producer,validator=hosted manager events (proposal events baseline ~obligations:[bad] ()) (decision baseline) in
  register manager contract producer validator;
  rejected "authoritative obligation" (fun()->run manager);
  require(absent !events "obligation.attribute:evidence_kind" && absent !events "validator") "Obligation short circuit read later fields";
  require(List.length(List.filter((=)"obligations.next") !events)=1) "Invalid obligation advanced lazy iterator";
  let events=ref [] in let manager=setup baseline in
  let original=List.hd(Json.array(get "initial_obligations" baseline)) in
  let id=Json.string(get "id" original) in
  let key=box(str id) in
  let key={key with lookup=(fun _ entries->Json.parse(Canonical.encode(List.assoc id entries)))} in
  let obligation=box ~event:(logged events "obligation.")
    ~fields:["requirement_id",key]
    (obj["requirement_id",str id;"evidence_kind",get "evidence_kind" original;
      "description",get "description" original;"evidence_refs",Json.Array[]]) in
  let producer,validator=hosted manager events (proposal events baseline ~obligations:[obligation] ()) (decision baseline) in
  register manager contract producer validator;
  require(C.Stage_record.accepted(run manager)) "Equivalent canonical host lookup changed native obligation authority";
  let reads=List.filter(fun event->String.starts_with ~prefix:"obligation.attribute:" event) !events in
  require(reads=["obligation.attribute:requirement_id";"obligation.attribute:evidence_kind";
    "obligation.attribute:requirement_id";"obligation.attribute:description";
    "obligation.attribute:requirement_id";"obligation.attribute:evidence_refs"])
    "Obligation equality reordered attribute access or dictionary lookup";
  let events=ref [] in let manager=setup baseline in
  let producer=M.bind_host_provider manager(fun _ _->proposal events baseline ()) in
  let native_called=ref false in
  let validator _ _=native_called:=true;M.Decision(C.Check_decision.make ~outcome:E.Pass ~detail:"Native check" ()) in
  register manager contract producer validator;
  rejected "cannot yet consume" (fun()->run manager);
  require(not !native_called) "Native checker consumed an empty stand-in for actual host links";
  rejected "Missing artifact" (fun()->M.get manager "behavior");
  let events=ref [] in let manager=setup baseline in
  let producer=M.bind_host_provider manager(fun _ _->proposal events baseline ()) in
  let expected=C.Source_link.make ~requirement_id:"r" ~source_node_id:"n" ~target_node_id:"n" ~pass_name:"lower" () in
  let saved=ref None in
  let validator _ context=
    let links=M.callback_source_links manager in saved:=Some(context,links);
    require(M.host_source_links_equal manager ~expected:[expected]=Some true)
      "Opted-in native checker did not compare actual deferred source links";
    require(M.host_source_links_equal manager ~expected:[]=Some false)
      "Mixed source-link length short circuit lost the original inventory";
    M.Decision(C.Check_decision.make ~outcome:E.Pass ~detail:"Compared original host source links." ()) in
  M.allow_host_source_links manager validator;
  register manager contract producer validator;
  require(C.Stage_record.accepted(run manager)) "Reviewed mixed validator could not acquire native acceptance";
  let context,host_links=Option.get !saved in
  require(M.callback_source_links manager=None) "Completed mixed callback leaked sidecar";
  (match M.invoke_provider manager ~host_links validator context with
   | M.Decision _->() | _->failwith "Retained native provider returned a different result kind");
  require(M.callback_source_links manager=None) "Saved context invocation leaked sidecar";
  let events=ref [] in let manager=setup baseline in
  let producer,validator=hosted manager events (proposal events baseline ()) (decision ~actual:E.Fail baseline) in
  register manager contract producer validator;
  let result=run manager in
  require(C.Stage_record.accepted result) "Serialized outcome comparison was replaced by object outcome identity";
  require(C.Stage_record.discharged result=[]) "Non-PASS object identity discharged an obligation";
  let manager=make_manager baseline in
  let events=ref [] in
  let payload=box ~event:(logged events "input.") (get "input" baseline) in
  ignore(M.add_host_input manager ~identity:"input" payload);
  require(index !events "input.freeze" < index !events "input.default:fingerprint") "Custom identity read before document freeze/default hash";
  events:=[];rejected "already exists" (fun()->M.add_host_input manager ~identity:"input" payload);
  require(!events=[]) "Duplicate input invoked authoring conversion";
  let configuration=box ~event:(logged events "configuration.") (obj[]) in
  rejected "Missing pass" (fun()->M.run_host manager ~pass_id:"missing" ~input_id:"input" ~output_id:"out" ~configuration ());
  require(!events=[]) "Configuration materialized before missing-pass precondition";
  rejected "requires a new pipeline" (fun()->M.admit_host_component_input manager ~contract_id:"missing" ~identity:"root" payload);
  require(!events=[]) "Admission converted payload before existing-root rejection";
  let manager=make_manager baseline in
  let raw=get "input" baseline in let authored=box raw in
  let replacement=Canonical.fingerprint(str "authored semantic identity") in
  let authored={authored with attribute_default=(fun _ key default->
    require(key="fingerprint" && same(literal default)(str(Canonical.fingerprint raw)))
      "Authored fingerprint getter did not receive the already-computed native default";
    M.set_dependency manager "request" replacement;box(str replacement))} in
  let record=M.add_host_input manager ~identity:"authored" authored in
  require(List.assoc "request" (C.Stage_record.dependencies record)=replacement)
    "Native input compared/stored dependency before authored getter mutation";
  let admission=get "admission_baseline" fixture in
  let payload=get "payload" admission in
  let manager=M.create ~budget:(work ())
    ~target:(Bioc_domain.Build_request.Target.of_json(get "target" payload))
    ~dependencies:(dependencies(get "dependencies" admission)) () in
  let validator=M.bind_host_provider manager(fun _ _->
    box ~classes:[M.Check_decision]
      (obj["outcome",str "pass";"detail",str "Compared with independent selection.";"evidence",obj[]])) in
  M.register_component_input manager (C.Component_input_contract.of_json(get "contract" admission))
    ~validators:["selection",validator];
  let record=M.admit_host_component_input manager ~contract_id:"admit" ~identity:"selected" (box payload) in
  require(same(C.Stage_record.to_json record)(get "record" admission))
    "Deferred admission differs from independently captured original record";
  (* Reentrant host validators observe actual SourceLink objects, retain nested
     records, and restore the outer sidecar even when their own callback raises. *)
  List.iter(fun raise_outer->
    let events=ref [] in let manager=setup baseline in let active=ref false in
    let candidate=proposal events baseline () in
    let producer=M.bind_host_provider manager(fun _ _->candidate) in
    let witness=Failure "same callback exception object" in
    let validator=M.bind_host_provider manager(fun _ _->
      let previous=M.callback_source_links manager in
      require(Option.is_some previous) "Host validator lost original source-link objects";
      if not !active then begin
        active:=true;
        ignore(M.run manager ~pass_id:"lower" ~input_id:"input" ~output_id:"inner" ());
        require(M.callback_source_links manager==previous) "Nested invocation did not restore outer source-link sidecar";
        if raise_outer then raise witness
      end;
      decision baseline) in
    register manager contract producer validator;
    if raise_outer then (match run manager with
      | _->failwith "Host exception was swallowed"
      | exception cause->require(cause==witness) "Original host exception object was reconstructed")
    else ignore(run manager);
    require(C.Stage_record.accepted(M.get manager "inner")) "Outer callback erased nested accepted record";
    if raise_outer then rejected "Missing artifact" (fun()->M.get manager "behavior")
    else require(C.Stage_record.accepted(M.get manager "behavior")) "Outer result did not persist";
    require(M.callback_source_links manager=None) "Exception leaked outer callback sidecar") [false;true];
  let manager=setup baseline in let events=ref [] in
  let producer,validator=hosted manager events (proposal events baseline ()) (decision baseline) in
  register manager contract producer validator;
  events:=[];
  let deferred : M.deferred_validators={
    validate=(fun _->events:= !events@["validate"];true);
    keys_match=(fun _ keys->events:= !events@["keys"];keys=["identity_check"]);
    snapshot=(fun _->events:= !events@["snapshot"];["identity_check",validator])} in
  M.register_deferred manager contract ~producer:(fun _->events:= !events@["producer"];producer)
    ~self_certifying:(fun _->events:= !events@["self"];false) deferred;
  require(!events=["validate";"keys";"self";"producer";"snapshot";"snapshot"])
    "Registration collapsed the original comparison and final mapping snapshots";
  let manager=setup baseline in let events=ref [] in
  let producer=M.bind_host_provider manager(fun work _->
    W.charge work (W.remaining work);proposal events baseline ()) in
  let validator=M.bind_host_provider manager(fun _ _->decision baseline) in
  register manager contract producer validator;
  (match run manager with
   | _->failwith "Host callback escaped the manager lifetime work ancestor"
   | exception Diagnostic.Error error->require(error.code="deferred_test_limit") "Wrong lifetime work exhaustion");
  print_endline "deferred pass manager: ordered host capabilities, checks, prefix validation and fail-closed mixed providers passed"
