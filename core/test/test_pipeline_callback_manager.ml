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
let encode=Canonical.encode
let same left right=encode left=encode right
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in channel)
  (fun()->Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000(really_input_string channel(in_channel_length channel)))
let rec ordered=function
 | Json.Object fields->Json.Array[str "object";Json.Array(List.map(fun(key,value)->Json.Array[str key;ordered value]) fields)]
 | Json.Array values->Json.Array[str "array";Json.Array(List.map ordered values)]
 | value->Json.Array[str "scalar";value]
type value=Data of Json.t | Mapping of (string*value) list | Sequence of value list
 | Instance of string*(string*value) list | Function of (value list->value)
 | Cursor of value list ref
let rec json=function
 | Data raw->raw | Mapping fields->obj(List.map(fun(key,value)->key,json value)fields)
 | Sequence values->Json.Array(List.map json values)
 | Instance(_,fields)->obj(List.map(fun(key,value)->key,json value)fields)
 | Function _ | Cursor _->failwith "Attempted to serialize a callable or iterator"
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
 mutable actions:string list;mutable contexts:Json.t list;mutable raise_producer:bool}
let peer ()={objects=[];next_object=0;providers=[];actions=[];contexts=[];raise_producer=false}
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
 | "callable"->Json.Bool(match value "object" with Function _->true | _->false)
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
 | "provider-reference"->obj["kind",str "host";"object",get "object" args]
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
let exercise ?(limits=Json.Null) peer commands=
 let input=ref "" and events=ref [] and replies=ref [] and pending=ref commands and sequence=ref 0 in
 let active=ref "hello" and peer_error=ref None in
 let enqueue raw=let body=encode raw in input:= !input^Printf.sprintf "%08x\n%s"(String.length body)body in
 let send kind fields=enqueue(obj(common kind !sequence@fields));incr sequence in
 send "hello"["declaration",Ch.declaration;"application",A.declaration;"limits",limits];
 let consume n=let n=min n(String.length !input) in let value=String.sub !input 0 n in
   input:=String.sub !input n(String.length !input-n);value in
 let io:Ch.io={read_header=(fun()->if !input="" then None else Some(consume 9));read_body=consume;
   write=(fun framed->let body=String.sub framed 9(String.length framed-9) in
     let event=Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000 body in
     events:= !events@[event];
     match text "kind" event with
     | "invoke"->let outcome=try obj["status",str "return";"value",action peer(text "action" event)(get "arguments" event)]
        with Exit->obj["status",str "raise";"token",str "same-original-exception"]
        | cause->peer_error:=Some cause;raise cause in
       send "continue"["invocation_id",get "invocation_id" event;
         "invocation_sha256",str(Canonical.sha256 body);"outcome",outcome]
     | "reply"->
       replies:= !replies@[!active,get "outcome" event];
       if not(Json.boolean(get "closed" event)) then (match !pending with
       | []->active:="close";send "close"["parent_invocation",Json.Null]
       | (operation,arguments)::tail->pending:=tail;active:=operation;
         send "command"["parent_invocation",Json.Null;"operation",str operation;"arguments",arguments])
     | "fatal"->() | _->failwith "Unknown channel event") } in
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
let ()=
 require(Array.length Sys.argv=3) "Expected declaration and original literal corpus paths";
 require(same(read Sys.argv.(1)) A.declaration) "Application declaration differs across languages";
 let baseline=get "manager_baseline"(read Sys.argv.(2)) in
 baseline_test baseline;negative_validator_test baseline;failure_test baseline;no_candidate_test baseline;protocol_test baseline;
 print_endline "callback manager application: framed baseline, negative validator, ordered identities and errors, freshness, host exception and resource closure passed"
