(* Real framed application exercise. The peer provides actual authoring objects,
   proposals and independent decisions; no accepted stage record is an input. *)
open Bioc_wire
module A = Bioc_pipeline_service.Callback_manager
module Ch = Bioc_pipeline_service.Callback_channel
let obj fields=Json.Object fields
let str value=Json.String value
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let require value message=if not value then failwith message
let phase=ref "declaration and fixture loading"
let encode=Canonical.encode
let same left right=encode left=encode right
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in channel)
  (fun()->Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000(really_input_string channel(in_channel_length channel)))
let rec ordered=function
 | Json.Object fields->Json.Array[str "object";Json.Array(List.map(fun(key,value)->Json.Array[str key;ordered value]) fields)]
 | Json.Array values->Json.Array[str "array";Json.Array(List.map ordered values)]
 | value->Json.Array[str "scalar";value]
let rec unordered=function
 | Json.Array[Json.String "scalar";value]->value
 | Json.Array[Json.String "array";Json.Array values]->Json.Array(List.map unordered values)
 | Json.Array[Json.String "object";Json.Array values]->obj(List.map(function
     Json.Array[Json.String key;value]->key,unordered value | _->failwith "Invalid ordered object")values)
 | _->failwith "Invalid ordered binding"
type value=Data of Json.t | Mapping of (string*value) list | Sequence of value list
 | Instance of string*(string*value) list | Function of (value list->value)
 | Cursor of value list ref | Native of string
let rec json=function
 | Data raw->raw | Mapping fields->obj(List.map(fun(key,value)->key,json value)fields)
 | Sequence values->Json.Array(List.map json values)
 | Instance(_,fields)->obj(List.map(fun(key,value)->key,json value)fields)
 | Function _ | Cursor _ | Native _->failwith "Attempted to serialize a callable or iterator"
let collection=function
 | Sequence values->values | Data(Json.Array values)->List.map(fun value->Data value)values
 | Mapping fields->List.map(fun(key,_)->Data(str key))fields
 | Data(Json.Object fields)->List.map(fun(key,_)->Data(str key))fields
 | _->failwith "Not iterable"
let mapping=function Mapping fields->fields | Data(Json.Object fields)->List.map(fun(key,value)->key,Data value)fields
 | _->failwith "Not a mapping"
let is_mapping=function Mapping _ | Data(Json.Object _)->true | _->false
let apply fn args=match fn with Function callback->callback args | _->failwith "Not callable"
let data value=Data value
let attribute value name=match value,name with
 | Instance(_,fields),_->List.assoc name fields
 | _,"get" when is_mapping value->Function(function [Data(Json.String key)]->
     Option.value(List.assoc_opt key(mapping value))~default:(Data Json.Null) | _->failwith "get arguments")
 | Data(Json.String value),"strip"->Function(function []->Data(str(String.trim value)) | _->failwith "strip arguments")
 | _->failwith("Missing authored attribute "^name)
type peer={mutable objects:(string*value) list;mutable next_object:int;mutable providers:(string*value) list;
 mutable actions:string list;mutable contexts:Json.t list;mutable raise_producer:bool;
 mutable request_document:Json.t option;mutable origins:(string*Json.t) list}
let peer ()={objects=[];next_object=0;providers=[];actions=[];contexts=[];raise_producer=false;
 request_document=None;origins=[]}
let reference peer value=
 match List.find_opt(fun(_,previous)->previous==value)peer.objects with
 | Some(key,_)->obj["handle",str key]
 | None->let key="object/"^string_of_int peer.next_object in peer.next_object<-peer.next_object+1;
   peer.objects<-(key,value)::peer.objects;obj["handle",str key]
let dereference peer raw=List.assoc(text "handle" raw)peer.objects
let truth=function Data Json.Null->false | Data(Json.Bool value)->value | Data(Json.String value)->value<>""
 | Sequence values->values<>[] | Mapping fields->fields<>[] | _->true
let action peer name args=
 peer.actions<-peer.actions@[name];
 let value key=dereference peer(get key args) in
 let boxed value=reference peer value in
 let items values=boxed(Sequence values) in
 match name with
 | "ordered-json"->ordered(json(value "object"))
 | "literal"->boxed(Data(get "value" args))
 | "enum"->boxed(Data(get "value" args))
 | "document" | "freeze-json" | "tuple" | "dict"->get "object" args
 | "attr"->boxed(attribute(value "object")(text "name" args))
 | "attr-default"->(try boxed(attribute(value "object")(text "name" args)) with Failure _->get "default" args)
 | "call"->boxed(apply(value "callable")(List.map(dereference peer)(Json.array(get "args" args))))
 | "get-item"->let actual=match value "object",json(value "key") with
   | (Sequence values),Json.Int index->List.nth values(Z.to_int index)
   | source,Json.String key when is_mapping source->List.assoc key(mapping source)
   | _->failwith "get-item type" in boxed actual
 | "callable"->Json.Bool(match value "object" with Function _ | Native _->true | _->false)
 | "is-instance"->let actual=value "object" in Json.Bool(match text "type" args with
   | "Mapping"->is_mapping actual | "str"->(match actual with Data(Json.String _)->true | _->false)
   | kind->(match actual with Instance(name,_)->kind=name | _->false))
 | "is-none"->Json.Bool(match value "object" with Data Json.Null->true | _->false)
 | "truth"->Json.Bool(truth(value "object"))
 | "compare"->let left=value "left" and right=value "right" in
   let equal=if text "operator" args="is" then
     (match left,right with Data(Json.String a),Data(Json.String b)->a=b | _->left==right)
     else same(json left)(json right) in
   Json.Bool(if text "operator" args="ne" then not equal else equal)
 | "contains"->Json.Bool(List.exists(fun member->same(json member)(json(value "item")))(collection(value "container")))
 | "set-equal"->let keys=List.map(fun value->encode(json value))(collection(value "object")) in
   let expected=List.map encode(Json.array(get "values" args)) in
   Json.Bool(List.sort_uniq String.compare keys=List.sort_uniq String.compare expected)
 | "set-attribute-equal"->let keys=List.map(fun raw->json(attribute(dereference peer raw)(text "name" args)))(Json.array(get "objects" args)) in
   Json.Bool(List.sort_uniq String.compare(List.map encode keys)=
     List.sort_uniq String.compare(List.map encode(Json.array(get "values" args))))
 | "mapping-values"->items(List.map snd(mapping(value "object")))
 | "mapping-items"->items(List.map(fun(key,value)->Sequence[Data(str key);value])(mapping(value "object")))
 | "iter"->boxed(Cursor(ref(collection(value "object"))))
 | "next"->(match value "object" with Cursor values->(match !values with
   | []->obj["exhausted",Json.Bool true;"object",Json.Null]
   | head::tail->values:=tail;obj["exhausted",Json.Bool false;"object",boxed head]) | _->failwith "Not a cursor")
 | "provider-reference"->(match value "object" with Native token->obj["kind",str "native";"provider_id",str token]
    | _->obj["kind",str "host";"object",get "object" args])
 | "native-provider"->boxed(Native(text "provider_id" args))
 | "origin-reference"->
    let key=encode args in
    (match List.assoc_opt key peer.origins with Some value->value | None->
      let root=text "root" args and path=Json.array(get "path" args) in
      let type_value kind name dimensions=obj["kind",str kind;"name",str name;
        "dimensions",Json.Array dimensions;"arguments",Json.Array[]] in
      let rec at raw=function []->raw | Json.String key::rest->at(get key raw)rest
       | Json.Int index::rest->at(List.nth(Json.array raw)(Z.to_int index))rest
       | _->failwith "Invalid source origin path" in
      let raw=match root with
       | "request"->at(Option.get peer.request_document)path
       | "BOOLEAN"->type_value "condition" "Condition" []
       | "LEVEL"->type_value "scalar" "Level" []
       | "DURATION"->type_value "scalar" "Duration" [Json.Array[str "time";Json.int 1]]
       | "defaultLifecycle"->obj["start",Json.int 0;"end",Json.Null;"unit",str "s"]
       | "syntheticCapabilities"->Json.Array[str "synthetic_signal_graph"]
       | _->failwith "Unknown source origin root" in
      let result=boxed(Data raw) in peer.origins<-(key,result)::peer.origins;result)
 | "bind-provider"->peer.providers<-(text "provider_id" args,value "object")::peer.providers;Json.Null
 | "call-provider"->if peer.raise_producer then raise Exit else
   boxed(apply(List.assoc(text "provider_id" args)peer.providers)[value "context"])
 | "hydrate-context"->peer.contexts<-peer.contexts@[args];boxed(Data(get "document" args))
 | "lookup"->let key=Json.string(json(value "object")) in
   let entries=List.map(function Json.Array[Json.String key;value]->key,value | _->failwith "lookup entry")
      (Json.array(get "entries" args)) in boxed(Data(List.assoc key entries))
 | "merge"->let before=Json.object_fields(get "before" args) and after=Json.object_fields(get "after" args) in
   let merged=List.fold_left(fun fields(key,value)->
     if List.mem_assoc key fields then List.map(fun(k,v)->k,if k=key then value else v)fields else fields@[key,value])
     before(Json.object_fields(json(value "object"))@after) in boxed(Data(obj merged))
 | "vars"->boxed(Data(json(value "object")))
 | _->failwith("Unimplemented test peer action "^name)
let uuid="01234567-89ab-cdef-0123-456789abcdef"
let common kind sequence=["protocol",str Ch.protocol;"profile",str Ch.profile;
 "session_id",str uuid;"kind",str kind;"sequence",Json.int sequence]
type result={replies:(string*Json.t) list;events:Json.t list;closed:bool}
(* Test peer supports real nested commands during a suspended invocation. *)
type invocation_plan = Peer_return of Json.t | Peer_raise of string
 | Peer_command of string * Json.t * (Json.t -> invocation_plan)
let fixed_registration_arguments peer arguments=
 let validators=Mapping(List.map(function Json.Array[Json.String key;reference]->key,dereference peer reference
   | _->failwith "Malformed fixed validator declaration")(Json.array(get "validators" arguments))) in
 let obligations=List.map(fun binding->require(text "kind" binding="native") "Fixed obligation lacks its native origin";
   reference peer(Data(unordered(get "tree" binding))))(Json.array(get "obligation_objects" arguments)) in
 obj["contract",get "contract" arguments;"producer",get "producer" arguments;
   "validators",reference peer validators;"obligation_objects",Json.Array obligations]
let default_invocation peer name arguments=match name with
 | "manager-created"->Peer_return Json.Null
 | "register-fixed"->Peer_command("register",fixed_registration_arguments peer arguments,
     (fun event->require(text "status"(get "outcome" event)="ok") "Native fixed registration failed";Peer_return Json.Null))
 | _->Peer_return(action peer name arguments)
let exercise ?(limits=Json.Null) ?(on_reply=(fun _ _->[])) ?(on_invoke=default_invocation) peer commands=
 let input=ref "" and events=ref [] and replies=ref [] and pending=ref commands and sequence=ref 0 in
 let active=ref "hello" and peer_error=ref None and nested=ref [] in
 let enqueue raw=let body=encode raw in input:= !input^Printf.sprintf "%08x\n%s"(String.length body)body in
 let send kind fields=enqueue(obj(common kind !sequence@fields));incr sequence in
 send "hello"["declaration",Ch.declaration;"application",A.declaration;"limits",limits];
 let consume n=let n=min n(String.length !input) in let value=String.sub !input 0 n in
   input:=String.sub !input n(String.length !input-n);value in
 let rec continue invocation body=function
  | Peer_return value->complete invocation body(obj["status",str "return";"value",value])
  | Peer_raise token->complete invocation body(obj["status",str "raise";"token",str token])
  | Peer_command(operation,arguments,resume)->
      let client_sequence= !sequence in
      nested:=(client_sequence,(fun event->continue invocation body(resume event)))::!nested;
      send "command"["parent_invocation",get "invocation_id" invocation;"operation",str operation;"arguments",arguments]
 and complete invocation body outcome=
   send "continue"["invocation_id",get "invocation_id" invocation;
     "invocation_sha256",str(Canonical.sha256 body);"outcome",outcome] in
 let io:Ch.io={read_header=(fun()->if !input="" then None else Some(consume 9));read_body=consume;
   write=(fun framed->let body=String.sub framed 9(String.length framed-9) in
     let event=Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000 body in
     events:= !events@[event];
     try match text "kind" event with
     | "invoke"->let plan=try on_invoke peer(text "action" event)(get "arguments" event)
         with Exit->Peer_raise "same-original-exception" in
       continue event body plan
     | "reply"->
       let client_sequence=Z.to_int(Json.integer(get "sequence" event)) in
       (match List.assoc_opt client_sequence !nested with
        | Some resume->nested:=List.remove_assoc client_sequence !nested;resume event
        | None->
          replies:= !replies@[!active,get "outcome" event];
          pending:= !pending@on_reply !active event;
          if not(Json.boolean(get "closed" event)) then (match !pending with
          | []->active:="close";send "close"["parent_invocation",Json.Null]
          | (operation,arguments)::tail->pending:=tail;active:=operation;
            send "command"["parent_invocation",Json.Null;"operation",str operation;"arguments",arguments]))
     | "fatal"->() | _->failwith "Unknown channel event"
     with cause->peer_error:=Some cause;raise cause) } in
 let service=A.create ~io () in A.run service;
 Option.iter raise !peer_error;
 {replies= !replies;events= !events;closed=A.is_closed service}
let success outcome=require(text "status" outcome="ok")("Expected success: "^encode outcome);get "value" outcome
let rejection outcome=
 require(text "status" outcome="rejected")("Expected rejection: "^encode outcome);
 let value=get "value" outcome in
 require(List.sort String.compare(List.map fst(Json.object_fields value))=
   ["attributes";"attributes_tree";"message";"module";"type"])
   "Rejection omitted its exact canonical and ordered attributes";
 value
let nth result index=snd(List.nth result.replies index)
let payload baseline peer=
 let obligations=Json.array(get "initial_obligations" baseline) in
 let refs=List.map(fun raw->reference peer(Data raw))obligations in
 obj["identity",str "input";"stage",str "typed intent and contracts";"requirements",Json.Array[str "r"];
   "obligations",Json.Array obligations;"obligation_objects",Json.Array refs;
   "obligations_object",reference peer(Sequence(List.map data obligations));
   "payload",reference peer(Data(get "input" baseline))]
let initialize baseline peer=obj["target",get "target" baseline;
 "dependencies",Json.Array(List.map(fun(key,value)->Json.Array[str key;value])(Json.object_fields(get "initial_dependencies" baseline)));
 "completion_profiles",Json.Array[get "completion" baseline];"manager_limits",Json.Null;
 "target_object",reference peer(Data(get "target" baseline))]
let registration ?(candidate_value=1) baseline peer field=
 let contract=get field baseline in let pass_id=text "id" contract in
 let input=get "input" baseline in
 let nodes=Json.array(get "nodes" input) in
 let output=set "schema_version"(get "output_schema" contract)
   (set "nodes"(Json.Array(List.map(set "value"(Json.int candidate_value))nodes))input) in
 let source=Instance("SourceLink",["requirement_id",Data(str "r");"source_node_id",Data(str "n");
   "target_node_id",Data(str "n");"pass_name",Data(str pass_id)]) in
 let obligations=List.map(fun raw->Instance("ProducerObligation",[
   "requirement_id",Data(get "id" raw);"evidence_kind",Data(get "evidence_kind" raw);
   "description",Data(get "description" raw);"evidence_refs",Sequence[]]))(Json.array(get "introduces" contract)) in
 let proposal=Instance("PassResult",["search_status",Data(str "candidate");"output",Data output;
   "source_links",Sequence[source];"observation_map",Data(obj["output",str "n"]);"obligations",Sequence obligations]) in
 let producer=Function(fun _->proposal) in
 let validator=Function(function [context]->
   let context=json context in
   let value document=get "value"(List.hd(Json.array(get "nodes" document))) in
   let expected=value input in
   let passed=same(value(get "input" context))expected && same(value(get "output" context))expected in
   let outcome=if passed then "pass" else "fail" in
   let detail=if passed then "Independently matched the expected value." else "Candidate value differs from source expectation." in
   let decision=obj["outcome",str outcome;"detail",str detail;"evidence",obj[]] in
   Instance("CheckDecision",["to_dict",Function(fun _->Data decision);"outcome",Data(str outcome)])
   | _->failwith "Validator context inventory changed") in
 let validators=Mapping(List.map(fun raw->text "id" raw,validator)(Json.array(get "checks" contract))) in
 obj["contract",contract;"producer",reference peer producer;"validators",reference peer validators;
   "obligation_objects",Json.Array(List.map(fun raw->reference peer(Data raw))(Json.array(get "introduces" contract)))]
let run pass_id input_id output_id configuration="run",obj["pass_id",str pass_id;"input_id",str input_id;
 "output_id",str output_id;"configuration",configuration]
let baseline_test baseline=
 let p=peer () in
 let commands=["initialize-empty",initialize baseline p;"add-input",payload baseline p;
   "register",registration baseline p "first";run "lower" "input" "behavior" Json.Null;
   "get",obj["identity",str "behavior"];"register",registration baseline p "second";
   run "generate" "behavior" "mechanism"(reference p(Data(obj["seed",Json.int 7;"tie_break",str "id"])));
   "result",obj["identity",str "mechanism";"scope",str "synthetic"];
   "inspect",obj[];"target",obj[];
   "set-dependency",obj["key",str "registry";"identity",str(Canonical.sha256 "changed")];
   "get",obj["identity",str "mechanism"];"inspect",obj[];
   "register",registration baseline p "first";"inspect-ordered",obj[];"inspect-ordered",obj[]] in
 let result=exercise p commands in
 require(result.closed && List.for_all(fun value->text "kind" value<>"fatal")result.events) "Baseline terminated fatally";
 let input=success(nth result 2) and behavior=success(nth result 4) and repeated=success(nth result 5)
 and mechanism=success(nth result 7) and completed=success(nth result 8) in
 List.iter(fun(name,actual)->require(same(get "value" actual)(get name(get "records" baseline)))
   ("Original full record differs: "^name))["input",input;"behavior",behavior;"mechanism",mechanism];
 require(same(get "bindings" behavior)(get "bindings" repeated)) "Repeated get changed record incarnation";
 require(same(get "artifact" completed)mechanism) "Result substituted a reconstructed record incarnation";
 require(same(get "value" completed)(get "result" baseline)) "Original scoped result differs";
 let history=success(nth result 9) in
 require(same(get "mechanism"(get "records" history))mechanism) "Inspection lost actual historical incarnation";
 ignore(success(nth result 11));
 require(text "status"(nth result 12)="rejected") "Changed dependency remained fresh";
 let after=success(nth result 13) in require(same(get "mechanism"(get "records" after))mechanism)
   "Stale read discarded historical record";
 require(List.length p.contexts=4) "Producer and validation contexts not hydrated exactly once";
 let before=List.nth p.contexts 0 and validation=List.nth p.contexts 1 in
 List.iter(fun key->require(same(get key(get "bindings" before))(get key(get "bindings" validation)))
   ("Context field identity changed: "^key))["input";"target";"configuration";"dependencies";"requirements"];
 require(get "source_links"(get "bindings" validation)<>Json.Null) "Hosted source link tuple identity absent";
 require(text "status"(nth result 14)="rejected") "Changed producer retained its prior contract version";
 let ordered=success(nth result 15) and repeated_ordered=success(nth result 16) in
 require(same ordered repeated_ordered) "Repeated ordered inspection changed identities or historical order";
 require(same(get "snapshot" ordered)after) "Ordered inspection changed the historical snapshot";
 let order=get "order" ordered in
 require(same(get "passes" order)(Json.Array[str "lower";str "generate"])) "Pass insertion order was sorted";
 let identities=List.map(fun name->get "pass_identity"(get "value"(get name(get "records" after))))["behavior";"mechanism"] in
 require(same(get "combined_provider_history" order)(Json.Array identities)) "Provider history chronology changed";
 require(List.length(Json.array(get "providers" ordered))=4 && List.length p.providers=5)
   "Ordered inspection included an uncommitted provider or lost a reachable provider"
let compact_inspection_test baseline=
 let p=peer () in
 let compact="inspect-ordered-references",obj[] and full="inspect-ordered",obj[] in
 let result=exercise p["initialize-empty",initialize baseline p;"add-input",payload baseline p;
   "register",registration baseline p "first";run "lower" "input" "behavior" Json.Null;
   "register",registration baseline p "second";
   run "generate" "behavior" "mechanism"(reference p(Data(obj["seed",Json.int 7;"tie_break",str "id"])));
   compact;compact;full;run "lower" "input" "behavior_next" Json.Null;
   compact;compact;full;
   "set-dependency",obj["key",str "registry";"identity",str(Canonical.sha256 "compact inspection stays historical")];
   compact;full] in
 require(result.closed && List.for_all(fun event->text "kind" event<>"fatal")result.events)
   "Compact historical inspection terminated fatally";
 let compact_values=List.filter_map(fun(operation,outcome)->
   if operation="inspect-ordered-references" then Some(success outcome) else None)result.replies in
 let full_values=List.filter_map(fun(operation,outcome)->
   if operation="inspect-ordered" then Some(success outcome) else None)result.replies in
 require(List.map(fun raw->List.length(Json.array(get "record_definitions" raw)))compact_values=[3;0;1;0;0])
   "Compact inspection repeated definitions or omitted a new record incarnation";
 require(List.map(fun envelope->text "id"(get "value" envelope))
   (Json.array(get "record_definitions"(List.hd compact_values)))=["input";"behavior";"mechanism"])
   "Initial compact definitions changed manager record order";
 require(text "id"(get "value"(List.hd(Json.array(get "record_definitions"(List.nth compact_values 2)))))="behavior_next")
   "A newly stored record reused a previous compact definition";
 let definitions=ref [] in
 let expand raw=
   List.iter(fun envelope->let token=text "record_id"(get "bindings" envelope) in
     require(not(List.mem_assoc token !definitions)) "A compact incarnation was defined twice";
     definitions:=(token,envelope)::!definitions)(Json.array(get "record_definitions" raw));
   let snapshot=get "snapshot" raw in
   let records=List.map(fun(name,reference)->
     require(List.map fst(Json.object_fields reference)=["record_id"]) "Compact record contains authority beyond its incarnation";
     let envelope=List.assoc(text "record_id" reference)!definitions in
     require(text "id"(get "value" envelope)=name) "Compact record reference names another artifact";
     name,envelope)(Json.object_fields(get "records" snapshot)) in
   obj["snapshot",set "records"(obj records)snapshot;"order",get "order" raw;"providers",get "providers" raw] in
 let expanded=List.map expand compact_values in
 require(same(List.nth expanded 0)(List.nth expanded 1) && same(List.nth expanded 1)(List.nth full_values 0))
   "Initial compact expansion differs from complete historical inspection";
 require(same(List.nth expanded 2)(List.nth expanded 3) && same(List.nth expanded 3)(List.nth full_values 1))
   "New-record compact expansion differs from complete historical inspection";
 require(same(List.nth expanded 4)(List.nth full_values 2))
   "Stale compact inspection changed historical records or acquired fresh acceptance"
let negative_validator_test baseline=
 let p=peer () in
 let result=exercise p ["initialize-empty",initialize baseline p;"add-input",payload baseline p;
   "register",registration ~candidate_value:2 baseline p "first";run "lower" "input" "behavior" Json.Null;
   "get",obj["identity",str "behavior"];"inspect-ordered",obj[]] in
 let record=success(nth result 4) in
 require(get "accepted"(get "value" record)=Json.Bool false) "Changed candidate was accepted by its independent validator";
 require(get "discharged"(get "value" record)=Json.Array[]) "Failed decision discharged a source obligation";
 require(text "outcome"(get "identity_check"(get "checks"(get "value" record)))="fail")
   "Independent failed outcome was replaced by producer success";
 require(text "status"(nth result 5)="rejected") "Fresh read accepted the failed output";
 let snapshot=get "snapshot"(success(nth result 6)) in
 require(same(get "behavior"(get "records" snapshot))record) "Failed validation record was not retained historically"
let failure_test baseline=
 let p=peer () in p.raise_producer<-true;
 let result=exercise p ["initialize-empty",initialize baseline p;"add-input",payload baseline p;
   "register",registration baseline p "first";run "lower" "input" "behavior" Json.Null;
   "get",obj["identity",str "input"];"inspect",obj[]] in
 require(same(nth result 4)(obj["status",str "raise";"token",str "same-original-exception"]))
   "Original host exception token did not survive native stack";
 ignore(success(nth result 5));let history=success(nth result 6) in
 require(List.map fst(Json.object_fields(get "records" history))=["input"]) "Failed callback imported an output record"
let no_candidate_test baseline=
 let configuration=obj["z",Json.Array[obj["last",Json.int 1;"first",Json.int 2]];
   "a",obj["right",Json.Bool true;"left",Json.Null];
   "inventory",Json.Array(List.init 256(fun index->obj["z",Json.int index;"a",Json.int(index+1)]))] in
 let dependencies=List.map(fun key->key,get key(get "initial_dependencies" baseline))["request";"registry"] in
 let make ?(limits=Json.Null) ~repeat ()=
   let p=peer () in
   let initialization=set "dependencies"(Json.Array(List.map(fun(key,value)->Json.Array[str key;value])dependencies))
     (initialize baseline p) in
   let registration=registration baseline p "first" in
   (* Access to any candidate-only attribute fails in this peer. A no-candidate
      result must stop after checking status and absent output. *)
   let proposal=Instance("PassResult",["search_status",Data(str "no_candidate_found");"output",Data Json.Null]) in
   let registration=set "producer"(reference p(Function(fun _->proposal)))registration in
   let config=reference p(Data configuration) in
   let commands=["initialize-empty",initialization;"add-input",payload baseline p;"register",registration;
     run "lower" "input" "absent" config] in
   let commands=if repeat then commands@[run "lower" "input" "absent-again" config;
     "get",obj["identity",str "input"];"get",obj["identity",str "missing"];"inspect",obj[]] else commands in
   p,exercise ~limits p commands in
 let p,result=make ~repeat:true () in
 require(result.closed && List.for_all(fun event->text "kind" event<>"fatal")result.events)
   "No-candidate failure closed the usable manager";
 let expected_dependencies=obj(dependencies@["target",str(Canonical.sha256(encode(get "target" baseline)))]) in
 let expected=obj["pass_id",str "lower";"configuration",configuration;"dependencies",expected_dependencies] in
 List.iter(fun index->let error=rejection(nth result index) in
   require(text "module" error="biocompiler.compiler.pipeline" && text "type" error="NoCandidateFound")
     "No-candidate result changed its exception class";
   require(same(get "attributes" error)expected) "No-candidate canonical attributes changed";
   require(same(get "attributes_tree" error)(ordered expected)) "No-candidate attribute or nested mapping order changed") [4;5];
 ignore(success(nth result 6));
 let missing=rejection(nth result 7) in
 require(same(get "attributes" missing)(obj[]) && same(get "attributes_tree" missing)(ordered(obj[])))
   "Ordinary logical rejection omitted its empty ordered attributes";
 require(List.map fst(Json.object_fields(get "records"(success(nth result 8))))=["input"])
   "No-candidate failure stored an output record";
 require(List.length p.contexts=2) "No-candidate result reached validation";
 let limits=get "limits" Ch.declaration in
 let _,baseline_result=make ~limits ~repeat:false () in
 ignore(rejection(nth baseline_result 4));
 let last_invocation=List.find(fun event->text "kind" event="invoke")(List.rev baseline_result.events) in
 require(text "action" last_invocation="is-none") "No-candidate rejection moved before its final output check";
 let retained=Z.to_int(Json.integer(get "retained_bytes"(get "usage" last_invocation))) in
 (* The remaining continuation, message and three dependency wrappers fit well
    within 8192 bytes. The 256 nested configuration objects require a larger
    preflight reservation for the fresh error tree. Complete-limit hello size
    changes by fewer than ten bytes when replacing this one integer. *)
 let limits=set "max_retained_bytes"(Json.int(retained+8192))limits in
 let reduced_peer,reduced=make ~limits ~repeat:false () in
 require(List.hd(List.rev reduced_peer.actions)="is-none") "Reduced limit failed before the no-candidate result was read";
 require(text "kind"(List.hd(List.rev reduced.events))="fatal") "Error-tree allocation exhaustion was treated as logical rejection";
 require(List.length reduced.replies=4 && reduced.closed) "Exhausted error publication returned or revived the manager"
let protocol_test baseline=
 let p=peer () in let initialization=initialize baseline p in
 let result=exercise p ["initialize-empty",initialization;"initialize-empty",initialization] in
 require(text "kind"(List.hd(List.rev result.events))="fatal") "Second initialization did not close";
 let p=peer () in
 let result=exercise p ["initialize-empty",set "accepted_records"(Json.Array[]) (initialize baseline p)] in
 require(text "kind"(List.hd(List.rev result.events))="fatal") "State import field was accepted";
 let p=peer () in
 let limits=get "limits" Ch.declaration in
 let limits=set "max_retained_bytes"(Json.int 1) limits in
 let result=exercise ~limits p [] in
 require(text "kind"(List.hd(List.rev result.events))="fatal") "Retention exhaustion revived authority"
module C = Bioc_domain.Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module S = Bioc_pipeline.Synthetic_pipeline
module P = Bioc_pipeline.Component_pipeline
module V = Bioc_pipeline_service.Fixed_provider_views
let rec at_path raw=function
 | []->raw
 | Json.String key::rest->at_path(get key raw)rest
 | Json.Int index::rest->at_path(List.nth(Json.array raw)(Z.to_int index))rest
 | _->failwith "Invalid typed alias path"
(* All proposals below are returned by actual native providers in this run. *)
let interception_budget ()=W.create ~profile:"fixed_registration_hooks"
  ~error_code:"fixed_registration_hook_limit" ~maximum:1_000_000_000_000 ()
let historical manager=M.inspect manager ~provider_identity:(fun _->"actual-native-provider")
let keys key raw=List.map fst(Json.object_fields(get key raw))
let no_fixed_scope request=
 let raw=Bioc_domain.Realization_request.to_json request in
 Bioc_domain.Realization_request.of_json(set "build_request"
   (set "artifact_scope"(str "abstract_behavior")(get "build_request" raw))raw)
let mutate_fixed_proposal mode context raw=
 let links=Json.array(get "source_links" raw) in
 match mode with
 | "observation"->set "observation_map"(obj["forged",str "endpoint"])raw
 | "wrong-source"->
     let nodes=Json.array(get "nodes"(get "mechanism"(C.Pass_context.input context))) in
     let replacement=get "id"(List.hd(List.rev nodes)) in
     let changed=List.map(set "source_node_id" replacement)links in
     require(not(same(Json.Array links)(Json.Array changed))) "Wrong-source recipe made no real change";
     set "source_links"(Json.Array changed)raw
 | "duplicate"->require(links<>[]) "Duplicate recipe lacks an actual source link";
     set "source_links"(Json.Array(links@[List.hd links]))raw
 | _->raw
let fixed_registration_library_tests request history config until=
 let budget=interception_budget () and published=ref None and calls=ref [] and observed=ref [] in
 let manager_created work manager=
   require(work==budget && !published=None) "Fixed creation published another lifetime or manager";
   let state=historical manager in
   require(keys "records" state=[] && keys "passes" state=[]) "Manager publication ran after input or pass storage";
   published:=Some manager in
 let provider_observer work owner provider _=
   require(work==budget && (match !published with Some actual->actual==owner | None->false))
     "Fixed closure role arrived before its actual owner was published";
   observed:=provider::!observed in
 let register_fixed work manager contract ~producer ~validators=
   require(work==budget && (match !published with Some actual->actual==manager | None->false))
     "Registration hook received another manager or work ancestor";
   require(List.exists(fun value->value==producer)!observed &&
     List.for_all(fun(_,provider)->List.exists(fun value->value==provider)!observed)validators)
     "Registration hook arrived before actual closure role publication";
   let id=C.Pass_contract.id contract and before=historical manager in
   let prior,records=match id with
    | "intent_to_behavior"->[],["request"]
    | "behavior_to_synthetic"->["intent_to_behavior"],["request";"behavior"]
    | "synthetic_to_components"->["intent_to_behavior";"behavior_to_synthetic"],["request";"behavior";"mechanism"]
    | _->failwith "Unexpected fixed registration" in
   require(keys "passes" before=prior && keys "records" before=records)
     "Fixed registration moved ahead of its original partial state";
   calls:= !calls@[id];M.register manager contract ~producer ~validators in
 let completed=P.run ~budget ~manager_created ~provider_observer ~register_fixed ?until ?config request history in
 require(!calls=["intent_to_behavior";"behavior_to_synthetic";"synthetic_to_components"])
   "Fixed registration hook was skipped or invoked twice";
 require((match !published with Some actual->actual==P.manager completed | None->false))
   "Completed build substituted another published manager";
 let unchanged=P.run ~budget:(interception_budget ()) ?until ?config request history in
 require(same(C.Pipeline_result.to_json(P.result completed))(C.Pipeline_result.to_json(P.result unchanged)))
   "Delegating fixed hooks changed the ordinary native result";
 let publication=ref None and budget=interception_budget () in
 let captured=Failure "same original fixed hook exception" in
 let manager_created work manager=require(work==budget) "Publication budget changed";publication:=Some manager in
 let register_fixed _ manager contract ~producer ~validators=
   if C.Pass_contract.id contract="behavior_to_synthetic" then (
     M.set_dependency manager "hook_marker"(Canonical.sha256 "retained nested mutation");raise captured)
   else M.register manager contract ~producer ~validators in
 (try ignore(P.attempt ~budget ~manager_created ~register_fixed ?until ?config request history);
    failwith "Unexpected hook exception was converted into a completed or logical result"
  with error->require(error==captured) "Fixed hook replaced its original exception value");
 let manager=Option.get !publication in
 let retained=historical manager in
 require(keys "records" retained=["request";"behavior"] && keys "passes" retained=["intent_to_behavior"])
   "A later host hook failure discarded or advanced partial state";
 require(text "hook_marker"(get "dependencies" retained)=Canonical.sha256 "retained nested mutation")
   "Hook failure rolled back its completed nested mutation";
 ignore(M.get manager "request");
 let budget=interception_budget () and publication=ref None in
 let manager_created _ manager=publication:=Some manager in
 let skipped _ _ _ ~producer:_ ~validators:_=() in
 (match S.attempt ~budget ~manager_created ~register_fixed:skipped ?until ?config request history with
  | S.Completed _->failwith "Skipped registration acquired a fallback provider"
  | S.Failed failure->require((match failure.manager,!publication with Some a,Some b->a==b | _->false))
      "Logical registration failure lost the published owner";
      require(keys "passes"(historical(Option.get failure.manager))=[] &&
        keys "records"(historical(Option.get failure.manager))=["request"])
        "Skipped hook installed a pass or rolled back the actual input");
 let created=ref None and publication_error=Failure "same publication exception" in
 (try ignore(S.attempt ~budget:(interception_budget ())
    ~manager_created:(fun _ manager->created:=Some manager;raise publication_error)
    ?until ?config request history);failwith "Publication exception was hidden"
  with error->require(error==publication_error) "Publication replaced its original exception value");
 let published_state=historical(Option.get !created) in
 require(keys "records" published_state=[] && keys "passes" published_state=[])
   "Failed publication advanced or discarded the actual empty owner";
 let early=ref false in
 (match S.attempt ~budget:(interception_budget ()) ~manager_created:(fun _ _->early:=true)
    ?until ?config(no_fixed_scope request)history with
  | S.Completed _->failwith "Non-synthetic request reached fixed registration"
  | S.Failed failure->require(failure.manager=None && not !early) "Pre-manager failure published fabricated state");
 List.iter(fun mode->
   let budget=interception_budget () and publication=ref None and before_run=ref None in
   let manager_created _ manager=publication:=Some manager in
   let register_fixed _ manager contract ~producer ~validators=
     let producer=if C.Pass_contract.id contract<>"synthetic_to_components" then producer else
       (fun work context->before_run:=Some(historical manager);
         match producer work context with
         | M.Proposal proposal->M.Proposal(C.Pass_result.of_json(mutate_fixed_proposal mode context(C.Pass_result.to_json proposal)))
         | M.Decision _ | M.Invalid_return _ | M.Host_return _->failwith "Fixed producer did not return its native proposal") in
     M.register manager contract ~producer ~validators in
   match P.attempt ~budget ~manager_created ~register_fixed ?until ?config request history with
   | P.Completed _->failwith("Forged fixed provenance was accepted: "^mode)
   | P.Failed failure->
       (match failure.error with Diagnostic.Error diagnostic->
          require(diagnostic.code="pipeline_error" && diagnostic.message=
            "Component pass provenance changed authoritative source links or observations.")
            "Native fixed validator rejected at another semantic branch"
        | _->failwith "Provenance mutation changed exception type");
       let manager=Option.get failure.manager in
       require((match !publication with Some actual->actual==manager | None->false))
         "Provenance failure lost its actual manager";
       require(same(Option.get !before_run)(historical manager)) "Rejected component proposal changed historical manager state";
       require(keys "records"(historical manager)=["request";"behavior";"mechanism"])
         "Rejected component proposal stored an output") ["observation";"wrong-source";"duplicate"]

(* Framed registration tests exercise the same live native hooks. *)
let proposal_object raw=
 let objects kind values=Sequence(List.map(fun value->Instance(kind,
   List.map(fun(key,value)->key,Data value)(Json.object_fields value)))values) in
 Instance("PassResult",["search_status",Data(get "search_status" raw);"output",Data(get "output" raw);
   "source_links",objects "SourceLink"(Json.array(get "source_links" raw));
   "obligations",objects "ProducerObligation"(Json.array(get "obligations" raw));
   "observation_map",Data(get "observation_map" raw)])
let interception_peer peer mode=
 let published=ref false and registrations=ref [] and contexts=ref [] and wrappers=ref [] in
 let before_component=ref None in
 let wrap_registration arguments=
   let arguments=fixed_registration_arguments peer arguments in
   if text "id"(get "contract" arguments)<>"synthetic_to_components" then arguments else
   let producer=dereference peer(get "producer" arguments) in
   let token=match producer with Native value->value | _->failwith "Fixed source is not the actual native proxy" in
   let wrapper=Function(fun _->failwith "Wrapped native provider escaped its live continuation") in
   wrappers:=(wrapper,token)::!wrappers;set "producer"(reference peer wrapper)arguments in
 let on_invoke peer name arguments=match name with
 | "manager-created"->
     require(not !published) "The fixed initializer published two managers";published:=true;
     if mode="bad-publication" then Peer_return(str "replacement-manager") else
     Peer_command("inspect",obj[],fun event->let state=success(get "outcome" event) in
       require(keys "records" state=[] && keys "passes" state=[]) "Framed publication followed input storage";
       Peer_return Json.Null)
 | "register-fixed"->
     require !published "Fixed registration ran before manager publication";
     let id=text "id"(get "contract" arguments) in registrations:= !registrations@[id];
     if mode="skip" && id="intent_to_behavior" then Peer_return Json.Null
     else if mode="raise" && id="behavior_to_synthetic" then
       Peer_command("set-dependency",obj["key",str "hook_marker";"identity",str(Canonical.sha256 "retained framed mutation")],
         fun event->ignore(success(get "outcome" event));Peer_raise "same-original-exception")
     else Peer_command("register",wrap_registration arguments,fun event->ignore(success(get "outcome" event));Peer_return Json.Null)
 | "hydrate-context"->
     let reference=action peer name arguments in
     contexts:=(text "handle" reference,arguments)::!contexts;Peer_return reference
 | "call-provider"->
     let provider=List.assoc(text "provider_id" arguments)peer.providers in
     (match List.find_opt(fun(value,_)->value==provider)!wrappers with
      | None->default_invocation peer name arguments
      | Some(_,token)->
          let context=List.assoc(text "handle"(get "context" arguments))!contexts in
          Peer_command("inspect",obj[],fun event->before_component:=Some(success(get "outcome" event));
            Peer_command("call-native-provider",obj["provider_id",str token;"context_id",get "context_id" context],
              fun event->let returned=success(get "outcome" event) in
                require(text "kind" returned="proposal") "Wrapped source did not execute its actual native producer";
                let context=C.Pass_context.of_json(get "document" context) in
                let raw=mutate_fixed_proposal mode context(get "value" returned) in
                let proposal=proposal_object raw in
                (* The original duplicate recipe appends the actual first SourceLink
                   object, retaining its physical identity. *)
                let proposal=if mode<>"duplicate" then proposal else match proposal with
                  | Instance(kind,fields)->let actual=match List.assoc "source_links" fields with
                     | Sequence values->values | _->failwith "Source links are not a tuple" in
                    let unique=List.rev(List.tl(List.rev actual)) in
                    Instance(kind,("source_links",Sequence(unique@[List.hd unique]))::List.remove_assoc "source_links" fields)
                  | _->failwith "Native proposal did not hydrate as PassResult" in
                Peer_return(reference peer proposal))))
 | "source-link-set-equal"->
     let actual=List.map(fun reference->encode(json(dereference peer reference)))(Json.array(get "objects" arguments)) in
     let expected=List.map encode(Json.array(get "expected" arguments)) in
     Peer_return(Json.Bool(List.sort_uniq String.compare actual=List.sort_uniq String.compare expected))
 | _->default_invocation peer name arguments in
 on_invoke,wrap_registration,published,registrations,before_component
let framed_fixed_interception_tests initialization=
 List.iter(fun mode->
   let peer=peer () in
   let on_invoke,_,published,registrations,before_component=interception_peer peer mode in
   let args=initialization peer in
   let initial_body=encode(obj(common "command" 1@["parent_invocation",Json.Null;
     "operation",str "initialize-components";"arguments",args])) in
   let result=exercise ~on_invoke peer["initialize-components",args;"inspect-ordered",obj[];"target",obj[]] in
   require !published "Fixed initialization never published its actual owner";
   if mode="bad-publication" then (
     let terminal=List.hd(List.rev result.events) in
     require(text "kind" terminal="fatal" && result.closed) "Malformed publication kept authority open";
     let invocation=List.find(fun event->text "kind" event="invoke" && text "action" event="manager-created")result.events in
     let continuation=encode(obj(common "continue" 2@[
       "invocation_id",get "invocation_id" invocation;"invocation_sha256",str(Canonical.sha256(encode invocation));
       "outcome",obj["status",str "return";"value",str "replacement-manager"]])) in
     require(get "sequence" terminal=Json.int 2 && text "request_sha256" terminal=Canonical.sha256 continuation)
       "Publication protocol failure lost its last validated continuation binding")
   else (
     let initialization=nth result 1 in
     require(List.for_all(fun event->text "kind" event<>"fatal")result.events && result.closed)
       "Logical/host fixed failure closed before historical observation";
     let inspected=success(nth result 2) in
     let state=get "snapshot" inspected in
     (* Canonical framed objects sort their keys. Historical insertion order is
        carried by the explicit order arrays, not JSON object member order. *)
     let ordered_keys key=
       let values=List.map Json.string(Json.array(get key(get "order" inspected))) in
       require(List.sort_uniq String.compare values=List.sort String.compare(keys key state) &&
         List.length values=List.length(keys key state))
         "Ordered inspection does not cover its complete historical mapping";
       values in
     ignore(success(nth result 3));
     if mode="raise" then (
       require(text "status" initialization="raise" && text "token" initialization="same-original-exception")
         "Outer initialization lost its original opaque callback exception";
       require(ordered_keys "records"=["request";"behavior"] && ordered_keys "passes"=["intent_to_behavior"])
         "Host registration exception discarded or advanced partial state";
       require(text "hook_marker"(get "dependencies" state)=Canonical.sha256 "retained framed mutation")
         "Host registration exception lost its nested mutation")
     else if mode="skip" then (
       ignore(rejection initialization);
       require(ordered_keys "records"=["request"] && ordered_keys "passes"=[])
         "Skipped fixed hook acquired a fallback registration")
     else if mode="passthrough" then (
       ignore(success initialization);
       require(ordered_keys "records"=["request";"behavior";"mechanism";"components"])
         "Actual wrapped native producer failed to retain its complete records")
     else (
       let error=rejection initialization in
       require(text "type" error="PipelineError" && text "message" error=
         "Component pass provenance changed authoritative source links or observations.")
         "Mixed native validator rejected before checking actual source provenance";
       require(same(Option.get !before_component)state) "Rejected wrapper changed its manager's historical state";
       require(ordered_keys "records"=["request";"behavior";"mechanism"])
         "Rejected wrapper stored an accepted component output");
     if List.mem mode["passthrough";"observation";"wrong-source";"duplicate"] then (
       let comparisons=List.filter(fun event->text "kind" event="invoke" &&
         text "action" event="source-link-set-equal")result.events in
       require(List.length comparisons=(if mode="duplicate" then 0 else 1))
         "Deferred source correspondence changed its length/set short circuit");
     let outer=List.find(fun event->text "kind" event="reply" && get "sequence" event=Json.int 1)result.events in
     require(text "request_sha256" outer=Canonical.sha256 initial_body)
       "Nested registration replaced the original initialization request binding";
     require(!registrations=(if mode="skip" then ["intent_to_behavior"] else if mode="raise" then
       ["intent_to_behavior";"behavior_to_synthetic"] else
       ["intent_to_behavior";"behavior_to_synthetic";"synthetic_to_components"]))
       "Actual fixed registration was omitted or duplicated"))
   ["passthrough";"observation";"wrong-source";"duplicate";"raise";"skip";"bad-publication"];
 let peer=peer () in
 let arguments=initialization peer in
 let raw=get "request" arguments in
 let raw=set "build_request"(set "artifact_scope"(str "abstract_behavior")(get "build_request" raw))raw in
 let arguments=set "request" raw(set "request_tree"(ordered raw)arguments) in
 let result=exercise peer["initialize-synthetic",arguments] in
 let error=rejection(nth result 1) in
 require(text "type" error="PipelineError" && text "message" error=
   "The request must explicitly select synthetic_realization scope.") "Early fixed failure changed its native error";
 require(not(List.exists(fun event->text "kind" event="invoke" && text "action" event="manager-created")result.events))
   "A failure before construction published a fabricated manager";
 require(result.closed && List.for_all(fun event->text "kind" event<>"fatal")result.events)
   "Expected pre-manager rejection was converted into a protocol failure"

let phased_component_test request history config until=
 let budget=W.create ~profile:"phased_component_pipeline" ~error_code:"phased_component_pipeline_limit"
   ~maximum:1_000_000_000_000 () in
 let upstream=S.run ~budget ?config ?until request history in
 let manager=S.manager upstream in
 let original_record=S.record upstream and original_result=S.result upstream in
 let historical=encode(C.Pipeline_result.to_json original_result) in
 let snapshot ()=M.inspect manager ~provider_identity:(fun _->"native-closure") in
 let initial=snapshot () in
 let prepared=P.prepare ~budget ?until request history upstream in
 require(same initial(snapshot ())) "Component adaptation mutated its live upstream manager";
 let dependencies=P.dependencies prepared in
 require(List.length dependencies=8) "Component preparation changed its dependency census";
 List.iter(fun(key,value)->M.set_dependency manager key value)dependencies;
 let after_dependencies=snapshot () in
 let foreign=W.create ~profile:"foreign_component_phase" ~error_code:"foreign_component_phase_limit"
   ~maximum:1_000_000 () in
 (try ignore(P.prepare_profile ~budget:foreign prepared);
    failwith "A component phase accepted a foreign lifetime budget"
  with Diagnostic.Error value->require(value.code="component_pipeline_budget") "Wrong foreign-budget rejection");
 let profiled=P.prepare_profile ~budget prepared in
 require(same after_dependencies(snapshot ())) "Profile construction registered or mutated state early";
 M.register_completion_profile manager(P.completion_profile profiled);
 let after_profile=snapshot () in
 let registration=P.prepare_registration ~budget profiled in
 require(same after_profile(snapshot ())) "Provider construction registered or mutated state early";
 M.register manager(P.contract registration) ~producer:(P.producer registration) ~validators:(P.validators registration);
 P.allow_host_source_links registration;
 let record=M.run manager ~pass_id:(C.Pass_contract.id(P.contract registration))
   ~input_id:"mechanism" ~output_id:"components" () in
 let result=M.result manager ~identity:"components" ~scope:"synthetic_components" in
 let before_finish=snapshot () in
 let completed=P.finish ~budget registration ~record ~result in
 require(same before_finish(snapshot ())) "Final component checks changed the manager";
 require(P.manager completed==manager && P.upstream completed==upstream && P.record completed==record
   && P.result completed==result) "Component finish replaced an actual retained capability";
 require(S.record(P.upstream completed)==original_record && S.result(P.upstream completed)==original_result)
   "Component continuation replaced the earlier synthetic result";
 require(List.mem_assoc "request"(C.Stage_record.dependencies original_record)) "Mechanism lacks its request dependency";
 M.set_dependency manager "request"(Canonical.sha256 "phased historical result is stale");
 (try ignore(M.get manager "mechanism");failwith "A changed dependency retained fresh mechanism acceptance"
  with Diagnostic.Error value->require(value.code="pipeline_error") "Wrong stale-record rejection");
 require(S.record upstream==original_record && encode(C.Pipeline_result.to_json(S.result upstream))=historical)
   "Dependency mutation rewrote the cached historical synthetic build"
let framed_component_test initialization mode=
 let p=peer () in
 let on_invoke,wrap_registration,_,_,_=interception_peer p "passthrough" in
 let preparation=ref Json.Null and record_id=ref Json.Null and run_sequence=ref Json.Null in
 let synthetic=ref None and components=ref None and changed=ref false in
 let candidate_aliases value=List.filter(fun entry->List.exists(function
    Json.Array(Json.String "candidate"::_)->true | _->false)(Json.array(get "paths" entry)))
    (Json.array(get "aliases"(get "view" value))) in
 let check_candidate_aliases value=
  let candidate=get "value"(get "candidate"(get "artifacts" value)) in
  let nodes=Json.array(get "nodes"(get "mechanism" candidate)) in
  let aliases=candidate_aliases value in
  require(List.length aliases=List.length nodes) "Build candidate lacks the exact parsed node type origin census";
  let identities=List.mapi(fun index node->
    let path=Json.Array[str "candidate";str "mechanism";str "nodes";Json.int index;str "output";str "dtype"] in
    let alias=List.find(fun entry->get "paths" entry=Json.Array[path])aliases in
    require(text "kind" alias="biocompiler.semantics.types.TypeSpec") "Build node origin changed its closed class";
    let binding=get "binding" alias in
    require(text "kind" binding="native" && same(unordered(get "tree" binding))(get "dtype"(get "output" node)))
      "Build node type binding differs from its parsed candidate source";
    text "identity" binding)nodes in
  require(List.length identities=List.length(List.sort_uniq String.compare identities))
    "Equal-valued parsed node types were incorrectly interned" in
 let build kind="build-result",obj["kind",str kind] in
 let phase operation=operation,obj["preparation_id",!preparation] in
 let on_reply operation event=
  if operation="hello" || operation="close" then [] else
  let outcome=get "outcome" event in
  if operation="get" then (
    let rejected=rejection outcome in
    require(text "type" rejected="PipelineError") "Dependency mutation produced another exception";
    [build "synthetic"])
  else let value=success outcome in match operation with
  | "initialize-synthetic"->[build "synthetic"]
  | "build-result" when text "kind" value="synthetic"->
      (match !synthetic with None->check_candidate_aliases value;synthetic:=Some value;["prepare-components",obj[]]
       | Some previous->require(same previous value) "A later operation replaced the historical synthetic envelope";
           [build "components"])
  | "build-result"->
      check_candidate_aliases value;
      require(same(Json.Array(candidate_aliases(Option.get !synthetic)))(Json.Array(candidate_aliases value)))
        "Component build replaced its actual upstream parsed type origins";
      require(same(Option.get !components)value) "A later operation replaced the historical component envelope";
      require(same(get "candidate"(get "artifacts"(Option.get !synthetic)))(get "candidate"(get "artifacts" value)))
        "Component build lost its actual upstream candidate identity";
      require(same(get "selection_result"(get "artifacts"(Option.get !synthetic)))(get "selection_result"(get "artifacts" value)))
        "Component build lost its actual upstream selection identity";
      require(same(get "candidate"(get "sources"(Option.get !synthetic)))(get "candidate"(get "sources" value)))
        "Component parser lost the original mechanism record incarnation";
      if !changed then [] else (changed:=true;
        ["set-dependency",obj["key",str "request";"identity",str(Canonical.sha256 "framed build is historical")];
         "get",obj["identity",str "mechanism"]])
  | "prepare-components"->
      preparation:=get "preparation_id" value;
      if mode="phase" then [phase "component-profile"] else
      List.map(function Json.Array[key;identity]->"set-dependency",obj["key",key;"identity",identity]
        | _->failwith "Malformed native dependency declaration")(Json.array(get "dependencies" value))@
        [phase "component-profile"]
  | "set-dependency"->[]
  | "component-profile"->["register-completion-profile",obj["profile",value];phase "component-registration"]
  | "register-completion-profile"->[]
  | "component-registration"->
      ["register",(if mode="wrapped" then wrap_registration value else fixed_registration_arguments p value)]
  | "register"->["run",obj["pass_id",str "synthetic_to_components";"input_id",str "mechanism";
      "output_id",str "components";"configuration",Json.Null]]
  | "run"->record_id:=get "record_id"(get "bindings" value);run_sequence:=get "sequence" event;
      ["result",obj["identity",str "components";"scope",str "synthetic_components"]]
  | "result"->
      let actual_record=if mode="record" then
          get "record_id"(get "bindings"(get "candidate"(get "sources"(Option.get !synthetic)))) else !record_id in
      let sequence=if mode="result" then !run_sequence else get "sequence" event in
      ["finish-components",obj["preparation_id",!preparation;"record_id",actual_record;"result_sequence",sequence]]
  | "finish-components"->components:=Some value;[build "synthetic"]
  | _->failwith("Unexpected phased workflow operation "^operation) in
 let result=exercise ~on_reply ~on_invoke p["initialize-synthetic",initialization p] in
 require(result.closed) "Phased workflow left its channel open";
 if mode="complete" || mode="wrapped" then (
   require(!components<>None && !changed) "Complete phased workflow did not reach stale historical reads";
   require(text "kind"(List.hd(List.rev result.events))="reply") "Valid staged continuation closed fatally")
 else require(!components=None && text "kind"(List.hd(List.rev result.events))="fatal")
   "An invalid phase or unrelated result capability completed the build"
let fixed_provider_tests path=
 phase:="fixed provider authority index: "^path;
 let index=read path in
 require(text "document_directory" index="fixed-pipeline-literals-v1") "Fixed authority directory changed";
 let run case_id=
  phase:="fixed provider case: "^case_id;
  let case=List.find(fun value->text "id" value=case_id)(Json.array(get "cases" index)) in
  require(text "api" case="run_component_pipeline" && text "outcome" case="returned")
    "Typed provider authority is not an original component call";
  let identity=text "authority" case in
  let authority=read(Filename.concat(Filename.concat(Filename.dirname path)"fixed-pipeline-literals-v1")(identity^".json")) in
  require(Canonical.sha256(encode authority)=identity) "Original fixed authority changed";
  let request_raw=get "request" authority in
  (* Deliberately noncanonical source map order reaches the native constructor
     through an ordered document. Values and original request identities stay
     unchanged; this detects accidental key sorting and prepend-on-update. *)
  let build=get "build_request" request_raw in
  let intent=get "intent" build in
  let authored_nodes=List.map(fun node->set "attributes"
      (obj(List.rev(Json.object_fields(get "attributes" node)))) node)(Json.array(get "nodes" intent)) in
  let request_raw=set "build_request"(set "intent"(set "nodes"(Json.Array authored_nodes)intent)build)request_raw in
  let request=Bioc_domain.Realization_request.of_json request_raw in
  let history=List.map(fun raw->Bioc_domain.Execution_data.Input_frame.of_json raw)(Json.array(get "history" authority)) in
  let config=match get "config" authority with Json.Null->None
    | value->Some(Bioc_domain.Synthetic_authority.Config.of_json value) in
  let until=match get "until" authority with Json.Null->None | value->Some(Bioc_domain.Runtime_number.of_json value) in
  if case_id="tests/test_component_pipeline.py::fixture.setUpClass/event/0" then (
    fixed_registration_library_tests request history config until;
    phased_component_test request history config until;
    let initialization peer=
      peer.request_document<-Some request_raw;
      let config=match config with Some value->value | None->Bioc_domain.Synthetic_authority.Config.make () in
      let config=Bioc_domain.Synthetic_authority.Config.to_json config in
      let target=Option.get(Bioc_domain.Realization_request.target request) in
      obj["request",request_raw;"request_tree",ordered request_raw;"history",get "history" authority;
        "until",get "until" authority;"config",config;"manager_limits",Json.Null;
        "target_object",reference peer(Data(Bioc_domain.Build_request.Target.to_json target));
        "config_object",reference peer(Data config);"request_object",reference peer(Data request_raw)] in
    let p=peer () in
    let completed=exercise p["initialize-synthetic",initialization p;"artifact",obj["name",str "candidate"]] in
    ignore(success(nth completed 1));ignore(success(nth completed 2));
    let p=peer () in
    let rejected=exercise p["initialize-synthetic",set "request_tree"(ordered Json.Null)(initialization p)] in
    require(text "kind"(List.hd(List.rev rejected.events))="fatal")
      "A differently ordered-tree projection replaced fixed request authority";
    framed_fixed_interception_tests initialization;
    List.iter(framed_component_test initialization)["complete";"wrapped";"record";"result";"phase"]);
  let budget=W.create ~profile:"fixed_provider_views" ~error_code:"fixed_provider_views_limit" ~maximum:1_000_000_000_000 () in
  let providers=ref [] and contexts=ref [] in
  let observer supplied=function
   | M.Context_created(_,M.Pass_origin(_,contract),context)->
       require(supplied==budget) "Context metadata lost its lifetime budget";
       contexts:=(C.Pass_contract.id contract,context)::!contexts
   | M.Context_created _ | M.Record_stored _->() in
  let provider_observer supplied owner provider role=
   require(supplied==budget) "Fixed metadata lost its lifetime budget";
   providers:=(owner,provider,role)::!providers in
  let completed=match P.attempt ~budget ~observer ~provider_observer ?config ?until request history with
   | P.Completed value->value | P.Failed failure->raise failure.error in
  let manager=P.manager completed in
  let producers=List.filter_map(fun(owner,provider,role)->
   require(owner==manager) "Provider metadata points to a different manager";
   match role with
   | S.Intent_to_behavior_producer->Some("intent_to_behavior",provider,role,None)
   | S.Behavior_to_synthetic_producer _->Some("behavior_to_synthetic",provider,role,None)
   | S.Synthetic_to_components_producer value->
       require(value.candidate==P.candidate completed && value.candidate==S.candidate(P.upstream completed))
         "Component provider captured a different upstream candidate incarnation";
       Some("synthetic_to_components",provider,role,
       Some(Bioc_domain.Synthetic_authority.Candidate.to_json value.candidate))
   | S.Intent_to_behavior_validator | S.Behavior_to_synthetic_validator | S.Synthetic_to_components_validator->None) !providers in
  require(List.length producers=3 && List.length !providers=6) "Closed fixed provider census differs";
  List.iter(fun(pass,provider,role,candidate)->
   let _,context=List.find(fun(id,context)->id=pass && C.Pass_context.output context=None) !contexts in
   let produce ()=match M.invoke_provider manager ~host_links:None provider context with
    | M.Proposal proposal->C.Pass_result.to_json proposal
    | M.Decision _ | M.Invalid_return _ | M.Host_return _->failwith "Fixed producer returned another role" in
   let first=produce () and second=produce () in
   require(same first second) "Repeated fixed provider calls changed their immutable values";
   let retained=ref 0 in
   let sites=V.aliases ~charge:(W.charge budget) ~reserve:(fun count->retained:= !retained+count)
     ~request:request_raw ~candidate ~role first in
   require(sites<>[] && !retained>0) "Fixed provider emitted no origin metadata or retention charge";
   let paths=List.map(fun(site:V.site)->encode(Json.Array site.path))sites in
   require(List.length paths=List.length(List.sort_uniq String.compare paths)) "A typed path acquired duplicate origins";
   List.iter(fun(site:V.site)->
    require(same site.value(at_path first site.path)) "Alias value differs from its actual provider field";
    match site.origin with
    | V.Host("request",path)->require(same site.value(at_path request_raw path)) "Authored origin differs from its native field"
    | V.Host(("BOOLEAN"|"LEVEL"|"DURATION"|"defaultLifecycle"),[])->()
    | V.Host _->failwith "Unknown fixed host origin grammar"
    | V.Upstream_type(node,indices)->
        let upstream=Option.get candidate in
        let source=List.find(fun value->text "id" value=node)(Json.array(get "nodes"(get "mechanism" upstream))) in
        let path=List.concat_map(fun index->[str "arguments";Json.int index])indices in
        require(same site.value(at_path(get "dtype"(get "output" source))path))
          "Component type origin differs from its actual parsed upstream node"
    | V.Fresh _ | V.Retained _->())sites;
   let same_origin (left:V.site) (right:V.site)=left.origin=right.origin in
   List.iter(fun(left:V.site)->List.iter(fun(right:V.site)->if same_origin left right then
    require(left.kind=right.kind && same left.value right.value) "One constructor origin acquired different typed fields")sites)sites;
   (match role with
    | S.Intent_to_behavior_producer->
        require(List.for_all(fun(site:V.site)->match site.origin with V.Fresh _->true | _->false)sites)
          "Lowered source identity escaped its invocation";
        List.iter(fun node->
          let source=List.find(fun source->text "id" source=text "id" node)authored_nodes in
          let original=List.map fst(Json.object_fields(get "attributes" source)) in
          let updates=match text "kind" source with
            | "parameter"->["bound";"default"] | "state"->["observation";"arbitration"]
            | "rule"->["priority";"ongoing_activation";"impulse_activation";"state_assignment"] @
                (if text "trigger"(get "attributes" source)="event" then ["ongoing_duration"] else [])
            | _->[] in
          let expected=original@List.filter(fun key->not(List.mem key original))updates in
          require(List.map fst(Json.object_fields(get "attributes" node))=expected)
            "Native lower attributes differ from original dict.update ordering")
          (Json.array(get "nodes"(get "output" first)))
    | S.Behavior_to_synthetic_producer _->
        require(List.exists(fun(site:V.site)->site.origin=V.Host("BOOLEAN",[]))sites)
          "Synthetic control lost the shared Boolean type"
    | S.Synthetic_to_components_producer _->
        let upstream_nodes=Json.array(get "nodes"(get "mechanism"(Option.get candidate))) in
        let type_origins=List.filter_map(fun(site:V.site)->match site.origin with
          | V.Upstream_type(node,[])->Some node | _->None)sites in
        require(List.sort_uniq String.compare type_origins=
          List.sort_uniq String.compare(List.map(text "id")upstream_nodes))
          "Component provider omitted an actual upstream parsed node type origin";
        let output=get "output" first in
        let components=Json.array(get "components"(get "registry" output)) in
        let instances=Json.array(get "instances"(get "composition" output)) in
        let domains=List.filter(fun(site:V.site)->site.origin=V.Retained "required-domain")sites in
        require(List.length domains=List.length components+List.length instances)
          "Required operating domain is not shared by every record and instance";
        List.iteri(fun instance_index instance->
          let path=[str "output";str "composition";str "instances";Json.int instance_index;str "component"] in
          let selected=List.find(fun(site:V.site)->site.path=path)sites in
          let matches=List.filter(same_origin selected)sites in
          require(List.length matches=2) "Composition lock is not exactly the registry lock object";
          require(text "node_id" selected.value=text "id" instance) "Composition lock origin references another instance")instances
    | S.Intent_to_behavior_validator | S.Behavior_to_synthetic_validator | S.Synthetic_to_components_validator->assert false);
   (* Compute actual deterministic metadata cost, then prove both exact limits
      succeed and a one-unit reduction fails before completing construction. *)
   let metadata_work=ref 0 and metadata_retained=ref 0 in
   ignore(V.aliases ~charge:(fun count->metadata_work:= !metadata_work+count)
     ~reserve:(fun count->metadata_retained:= !metadata_retained+count) ~request:request_raw ~candidate ~role first);
   let bounded maximum_work maximum_retained=
    let work=ref 0 and retained=ref 0 in
    let spend total maximum count=if count>maximum- !total then raise Exit else total:= !total+count in
    try ignore(V.aliases ~charge:(spend work maximum_work) ~reserve:(spend retained maximum_retained)
      ~request:request_raw ~candidate ~role first);true with Exit->false in
   require(bounded !metadata_work !metadata_retained) "Exact metadata resource cost failed";
   require(not(bounded(!metadata_work-1) !metadata_retained)) "Metadata work exhaustion returned a partial alias graph";
   require(not(bounded !metadata_work(!metadata_retained-1))) "Metadata retention exhaustion returned a partial alias graph")producers in
 List.iter run ["tests/test_component_pipeline.py::fixture.setUpClass/event/0";
   "tests/test_temporal_components.py::fixture.setUpClass/event/0";
   "tests/test_synthetic_design_workflows.py::fixture.setUpClass/event/0"]
let main ()=
 require(Array.length Sys.argv=4) "Expected declaration, original contract and fixed authority corpus paths";
 require(same(read Sys.argv.(1)) A.declaration) "Application declaration differs across languages";
 require(same(get "default_generator_config" A.declaration)
   (Bioc_domain.Synthetic_authority.Config.to_json(Bioc_domain.Synthetic_authority.Config.make ())))
   "Negotiated default generator configuration differs from the actual native constructor";
 let baseline=get "manager_baseline"(read Sys.argv.(2)) in
 List.iter(fun(name,test)->phase:=name;test baseline)
  ["baseline",baseline_test;"compact inspection",compact_inspection_test;
   "negative validator",negative_validator_test;"callback failure",failure_test;
   "no candidate",no_candidate_test;"protocol",protocol_test];
 fixed_provider_tests Sys.argv.(3);
 print_endline "callback manager application: framed state/errors and 18 actual fixed producer returns with typed construction origins and exact metadata resource bounds passed"
let ()=
 Printexc.record_backtrace true;
 try main () with error->
  let backtrace=Printexc.get_raw_backtrace () in
  let detail=match error with
   | Diagnostic.Error value->value.code^": "^value.message^
       (match value.path with None->"" | Some path->" at "^path)
   | _->Printexc.to_string error in
  Printf.eprintf "Callback manager test failed during %s: %s\n%!" !phase detail;
  Printexc.raise_with_backtrace error backtrace
