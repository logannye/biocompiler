(* Actual framed reference application. Inputs are original caller declarations;
   every accepted record, candidate and final check is produced by native code.
   The boxed peer implements structural host operand behavior only. *)
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
let attribute value name=match value,name with
 | Instance(_,fields),_->List.assoc name fields
 | _,"get" when is_mapping value->Function(function [Data(Json.String key)]->
     Option.value(List.assoc_opt key(mapping value))~default:(Data Json.Null) | _->failwith "get arguments")
 | Data(Json.String value),"strip"->Function(function []->Data(str(String.trim value)) | _->failwith "strip arguments")
 | _->failwith("Missing authored attribute "^name)
type peer={mutable objects:(string*value) list;mutable next_object:int;mutable providers:(string*value) list;
 mutable actions:string list;mutable contexts:(Json.t*Json.t) list;raise_producer:bool;
 request_document:Json.t option;mutable origins:(string*Json.t) list}
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
 | "native-provider" | "reference-molecular-provider"->boxed(Native(text "provider_id" args))
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
 | "hydrate-context"->let value=boxed(Data(get "document" args)) in
   peer.contexts<-peer.contexts@[args,value];value
 | "lookup"->let key=Json.string(json(value "object")) in
   let entries=List.map(function Json.Array[Json.String key;value]->key,value | _->failwith "lookup entry")
      (Json.array(get "entries" args)) in boxed(Data(List.assoc key entries))
 | "ordered-merge"->
   let before=unordered(get "before_tree" args) and after=unordered(get "after_tree" args) in
   require(same before(get "before" args) && same after(get "after" args)) "Ordered merge projection differs";
   let before=Json.object_fields before and after=Json.object_fields after in
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
 let active=ref "hello" and peer_error=ref None and nested=ref [] and sent=ref [] and next_event=ref 0 in
 let enqueue raw=let body=encode raw in input:= !input^Printf.sprintf "%08x\n%s"(String.length body)body in
 let send kind fields=
   let raw=obj(common kind !sequence@fields) in
   sent:=(!sequence,(kind,Canonical.sha256(encode raw)))::!sent;
   enqueue raw;incr sequence in
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
     try
     require(String.sub framed 0 9=Printf.sprintf "%08x\n"(String.length body))"Native frame header differs from actual body";
     require(get "event_id" event=Json.int !next_event)"Native event sequence changed";incr next_event;
     let is_invocation=text "kind" event="invoke" in
     let sequence_field=if is_invocation then "command_sequence" else "sequence" in
     let hash_field=if is_invocation then "command_sha256" else "request_sha256" in
     (if text "kind" event="fatal" && get sequence_field event=Json.Null then
       require(get hash_field event=Json.Null)"Unparsed terminal request acquired a fabricated body hash"
      else begin
       let request_sequence=Z.to_int(Json.integer(get sequence_field event)) in
       let kind,sha=List.assoc request_sequence !sent in
       require(text hash_field event=sha && (not is_invocation || kind="command"))
         "Native reply or invocation detached from actual client command"
      end);
     match text "kind" event with
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
module RM=Bioc_domain.Reference_molecular
module RD=Bioc_domain.Reference_construct
module G=Bioc_compiler.Reference_construct_producer
module W=Bioc_checker.Work_budget
let record_id record=text "record_id"(get "bindings" record)
let outcome event=get "outcome" event
let arguments peer declaration admission=
 let validators=Mapping(List.map(function Json.Array[Json.String name;ref]->name,dereference peer ref
   |_->failwith "Invalid native validator pair")(Json.array(get "validators" declaration))) in
 let obligation_values=List.map(fun binding->require(text "kind" binding="native")"Obligation origin is not native";
   Data(unordered(get "tree" binding)))(Json.array(get "obligation_objects" declaration)) in
 let fields=["contract",get "contract" declaration;"validators",reference peer validators;
   "obligation_objects",Json.Array(List.map(reference peer)obligation_values)] in
 if admission then obj(fields@["obligations_object",reference peer(Sequence obligation_values);
   "requirements_object",reference peer(Data(get "requirements"(get "contract" declaration)))])
 else obj(fields@["producer",get "producer" declaration])
let initialize_reference peer request registry manifests=
 let boxed raw=reference peer(Data raw) in
 let pairs=Json.Array(List.map(fun(key,value)->Json.Array[str key;value])(Json.object_fields manifests)) in
 let policies=obj["translation_policy",boxed(RM.Translation_policy.to_json(RM.Translation_policy.default()));
   "encoding_policy",boxed(RM.Encoding_policy.to_json(RM.Encoding_policy.default()));
   "evidence_policy",boxed(RM.Evidence_policy.to_json(RM.Evidence_policy.default()))] in
 obj["request",request;"request_tree",ordered request;"registry",registry;"registry_tree",ordered registry;
   "manifests",pairs;
   "manifests_tree",ordered pairs;"manager_limits",Json.Null;
   "target_object",boxed(get "target" request);"request_object",boxed request;"registry_object",boxed registry;
   "construct_manifests_object",boxed manifests;"molecular_manifests_object",boxed manifests;"policy_objects",policies]
type mode=Default_native|Host_valid|Wrapped_repeat|Reuse_owner|Public_sources|Raise_generator|Invalid_candidate|Foreign_record|Foreign_result
let reference_invocation mode generated peer name args=match name with
 | "manager-created"->Peer_return Json.Null
 | "reference-generate" | "reference-emit"->
    require(same(unordered(get "tree" args))(get "argument" args))"Parsed producer tree changed its document";
    ignore(Json.object_fields(get "input" args));
    require(same(get "input" args)(get "argument" args))
      "Canonical reference input differs from its complete parsed producer argument";
    let parsed=reference peer(Data(get "argument" args)) in
    if name="reference-generate" then (match mode with
      |Raise_generator->Peer_raise "actual-generator-exception"
      |Host_valid->
        (* The peer proposes a freshly generated candidate, never a captured
           accepted record. Native admission/layout checks still decide it. *)
        let budget=W.create ~profile:"reference.callback.peer" ~error_code:"reference_callback_peer_work" ~maximum:1_000_000_000 () in
        let candidate=G.generate ~parent:budget(RD.Request.of_json(get "argument" args)) in
        let value=reference peer(Data(RD.Candidate.to_json candidate)) in
        generated:=Some value;Peer_return(obj["kind",str "host";"argument",parsed;"output",value])
      |Invalid_candidate->let value=reference peer(Data(obj["schema_version",str "invalid.reference.candidate";"nodes",Json.Array[]])) in
        generated:=Some value;Peer_return(obj["kind",str "host";"argument",parsed;"output",value])
      |Default_native|Wrapped_repeat|Reuse_owner|Public_sources|Foreign_record|Foreign_result->Peer_return(obj["kind",str "native";"argument",parsed;"output",Json.Null]))
    else Peer_return(obj["kind",str "native";"argument",parsed;"output",Json.Null])
 | "reference-proposal"->
    require((mode=Invalid_candidate || mode=Host_valid) && Some(get "output" args)= !generated)"Proposal builder changed opaque output capability";
    let links=List.map(fun raw->Instance("SourceLink",List.map(fun(key,value)->key,Data value)(Json.object_fields raw)))
      (Json.array(get "source_links" args)) in
    require(links<>[])"Host proposal was built before source links existed";
    Peer_return(reference peer(Instance("PassResult",["output",dereference peer(get "output" args);
      "obligations",Sequence[];"source_links",Sequence links;"observation_map",Data(obj[]);"search_status",Data(str "candidate")])))
 | "reference-source-links-equal"->
    let tuple raw=List.map(fun key->text key raw)["requirement_id";"source_node_id";"target_node_id";"pass_name"] in
    let expected=List.sort compare(List.map tuple(Json.array(get "expected" args))) in
    let actual=List.sort compare(List.map(fun ref->tuple(json(dereference peer ref)))(Json.array(get "actual" args))) in
    Peer_return(Json.Bool(actual=expected))
 |_->default_invocation peer name args
let run_request pass input output=obj["pass_id",str pass;"input_id",str input;"output_id",str output;"configuration",Json.Null]
let result_request identity scope=obj["identity",str identity;"scope",str scope]
let framed_reference ?(limits=Json.Null) ?(resource_stop=false) mode request registry manifests=
 let peer=peer() and generated=ref None in
 let upstream=reference peer(Function(fun _->failwith "Upstream wrapper must stay opaque")) in
 let returned_construct=reference peer(Function(fun _->failwith "Returned Construct must stay opaque")) in
 let final_reads=ref [] in
 let wrapped_producer=ref None and direct_calls=ref 0 in
 let wrapper=Function(fun _->failwith "Wrapped producer must use its actual nested native command") in
 let native=mode<>Raise_generator && mode<>Invalid_candidate in
 let admission=ref None and component_record=ref None and construct_record=ref None and molecular_record=ref None in
 let construct_result=ref None and molecular_result=ref None and construct_build=ref None and molecular_build=ref None in
 let preparation=ref None and result_commands=ref 0 and historical_reads=ref 0 in
 let first_preparation=ref None and reentries=ref 0 and leave_count=ref 0 in
 let molecular_provider=ref None and saved_context=ref None and old_calls=ref 0 in
 let molecular_wrapper=Function(fun _->failwith "Molecular wrapper must call the native provider") in
 let on_reply operation event=
  let value()=success(outcome event) in
  match operation with
  |"initialize-reference"->ignore(value());["reference-admission",obj[]]
  |"reference-admission"->let declaration=value() in admission:=Some declaration;
      ["register-component-input",arguments peer declaration true;
       "admit-component-input",obj["contract_id",str "reference_components";"identity",str "components";
         "payload",reference peer(Data request)];"get",obj["identity",str "components"]]
  |"admit-component-input"->let record=value() in
      require(get "accepted"(get "value" record)=Json.Bool true)"Original reference authority was not admitted";
      component_record:=Some record;[]
  |"get" when !construct_record=None && native->
      require(same(value())(Option.get !component_record))"Explicit admission get changed record incarnation";
      ["reference-registration",obj[]]
  |"get" when !construct_record=None && !construct_build=None && !result_commands=0 &&
      (mode=Raise_generator || mode=Invalid_candidate)->
      require(same(value())(Option.get !component_record))"Host failure lost admitted input";
      if !admission=None then failwith "Missing admission capability";
      if !historical_reads=0 then (incr historical_reads;["reference-registration",obj[]]) else []
  |"reference-registration"->let declaration=value() in
      let find name raw=List.find_map(function Json.Array[Json.String key;value] when key=name->Some value|_->None)
        (Json.array(get "validators" raw)) |> Option.get in
      require(same(find "layout_composition" declaration)(find "component_linkage"(Option.get !admission)))
        "Construct pass did not reuse its actual admission linkage provider";
      let registration=arguments peer declaration false in
      let registration=if mode=Wrapped_repeat then begin
        let token=match dereference peer(get "producer" declaration) with
          |Native value->value |_->failwith "Reference producer is not native" in
        wrapped_producer:=Some token;set "producer"(reference peer wrapper)registration
      end else registration in
      ["register",registration;"run",run_request "components_to_construct" "components" "construct"]
  |"run" when !construct_record=None->
      (match mode with
       |Raise_generator->require(same(outcome event)(obj["status",str "raise";"token",str "actual-generator-exception"]))
          "Host generator exception token changed";
          ["inspect-ordered",obj[];"get",obj["identity",str "components"]]
       |Invalid_candidate->ignore(rejection(outcome event));
          ["inspect-ordered",obj[];"get",obj["identity",str "components"]]
       |Default_native|Host_valid|Wrapped_repeat|Reuse_owner|Public_sources|Foreign_record|Foreign_result->let record=value() in construct_record:=Some record;
          require(get "accepted"(get "value" record)=Json.Bool true)"Native construct was not accepted";
          ["result",result_request "construct" "reference_construct"])
  |"result"->incr result_commands;
      let result=value() and sequence=get "sequence" event in
      if !molecular_record=None then begin
        require(same(get "artifact" result)(Option.get !construct_record))"Construct result changed actual run record";
        construct_result:=Some result;
        ["finish-reference-construct",obj["record_id",str(if mode=Foreign_record then "record/foreign" else record_id(Option.get !construct_record));
          "result_sequence",(if mode=Foreign_result then Json.int 0 else sequence)]]
      end else begin
        require(same(get "artifact" result)(Option.get !molecular_record))"Molecular result changed actual run record";
        molecular_result:=Some result;
        ["finish-reference-molecular",obj["preparation_id",Option.get !preparation;
          "record_id",str(record_id(Option.get !molecular_record));"result_sequence",sequence;
          "upstream",(if mode=Public_sources then upstream else Json.Null)]]
      end
  |"finish-reference-construct"->let build=value() in construct_build:=Some build;
      require(text "kind" build="construct" && get "construct" build=Json.Null &&
        same(get "result" build)(Option.get !construct_result))"Construct finish recomputed result";
      require(same(get "value"(get "candidate" build))(get "payload"(get "value"(Option.get !construct_record))))
        "Construct public artifact differs from actual run payload";
      ["reference-build-result",obj["kind",str "construct"]]
  |"reference-build-result" when !molecular_build=None->
      require(same(value())(Option.get !construct_build))"Historical construct build was not stable";
      (if mode=Public_sources then
        let raw=initialize_reference peer request registry manifests in
        let fields=List.map(fun key->key,get key raw)
          ["request";"request_tree";"registry";"registry_tree";"manifests";"manifests_tree";
           "request_object";"registry_object";"molecular_manifests_object";"policy_objects"] in
        ["prepare-reference-molecular-public",obj fields]
       else ["prepare-reference-molecular",obj[]])
  |"prepare-reference-molecular"|"prepare-reference-molecular-public"->let prepared=value() in
      let id=get "preparation_id" prepared in
      (match !first_preparation with None->first_preparation:=Some id | Some prior->
        require(id<>prior)"Reentry reused its old preparation capability";incr reentries);
      preparation:=Some id;
      let dependencies=Json.array(get "dependencies" prepared) in require(List.length dependencies=6)"Molecular dependency count changed";
      List.map(function Json.Array[key;identity]->"set-dependency",obj["key",key;"identity",identity]
        |_->failwith "Invalid dependency pair")dependencies@["reference-molecular-profile",obj["preparation_id",id]]
  |"reference-molecular-profile"->let profile=value() in
      ["register-completion-profile",obj["profile",profile]]@
      (if !reentries=0 then ["reference-molecular-registration",obj["preparation_id",Option.get !preparation]] else [])
  |"register-completion-profile" when !reentries>0->
      require(mode=Reuse_owner)"Unexpected reused completion profile";
      let error=rejection(outcome event) in
      require(text "message" error="Completion profile 'exact_cds' is already registered.")
        "Repeated native owner changed its original duplicate-profile failure";
      ["leave-reference-molecular-attempt",obj["preparation_id",Option.get !preparation];
       "call-native-provider",obj["provider_id",str(Option.get !molecular_provider);"context_id",Option.get !saved_context];
       "reference-build-result",obj["kind",str "molecular"]]
  |"reference-molecular-registration"->let declaration=value() in
      let registration=arguments peer declaration false in
      let registration=if mode=Reuse_owner then begin
        let token=match dereference peer(get "producer" declaration) with Native value->value
          |_->failwith "Molecular producer is not an actual native closure" in
        molecular_provider:=Some token;set "producer"(reference peer molecular_wrapper)registration
      end else registration in
      ["register",registration;"run",run_request "construct_to_molecular" "construct" "molecular"]
  |"run"->let record=value() in molecular_record:=Some record;
      require(get "accepted"(get "value" record)=Json.Bool true)"Native molecule was not accepted";
      ["result",result_request "molecular" "exact_cds"]
  |"finish-reference-molecular"->let build=value() in molecular_build:=Some build;
      require(text "kind" build="molecular" && same(get "result" build)(Option.get !molecular_result))
        "Molecular finish recomputed actual result";
      if mode=Public_sources then begin
        require(get "value"(get "construct" build)=Json.Null)"Opaque returned Construct was serialized";
        let binding=get "binding"(get "construct" build) in
        require(text "kind" binding="host" && same(get "object" binding)returned_construct)
          "Molecular build substituted the checked candidate for the actual second host root";
        require(!final_reads=["check";"return"])"Final candidate reads changed order or multiplicity"
      end else require(same(get "construct" build)(get "candidate"(Option.get !construct_build)))"Molecular build lost actual upstream candidate origin";
      ["leave-reference-molecular-attempt",obj["preparation_id",Option.get !preparation];
       "reference-build-result",obj["kind",str "molecular"]]@
       (if mode=Reuse_owner then [] else ["set-dependency",obj["key",str "layout";"identity",str(Canonical.sha256 "later root")];
       "reference-build-result",obj["kind",str "molecular"];"get",obj["identity",str "molecular"]])
  |"leave-reference-molecular-attempt"->require(value()=Json.Null)"Attempt cleanup returned semantic data";incr leave_count;[]
  |"call-native-provider"->let proposal=value() in
      require(mode=Reuse_owner && !reentries=1 && !leave_count=2 && text "kind" proposal="proposal" &&
        text "role"(get "view" proposal)="construct_to_molecular.producer")
        "Old native provider was rebound or could not run after attempt exit";
      incr old_calls;[]
  |"reference-build-result"->require(same(value())(Option.get !molecular_build))"Historical molecular build changed after live mutation";
      if mode=Reuse_owner && !reentries=0 then ["prepare-reference-molecular",obj[]] else []
  |"get"->ignore(rejection(outcome event));[]
  |"inspect-ordered"->let inspected=value() in
      require(Json.array(get "records"(get "order" inspected))=[str "components"])
        "Host failure stored output or discarded admission";
      require(Json.array(get "passes"(get "order" inspected))=[str "components_to_construct"])
        "Host failure discarded actual registration";[]
  |_->ignore(value());[] in
 let on_invoke peer name args=
   if name="reference-molecular-provider" then begin
     require(get "preparation_id" args=Option.get !first_preparation && !reentries=0)
       "Molecular provider publication changed its actual attempt origin";
     reference_invocation mode generated peer name args
   end else if name="reference-emit" then begin
     require(get "preparation_id" args=Option.get !first_preparation)
       "Saved Molecular provider captured a later attempt's roots";
     if mode=Reuse_owner then require(text "provider_id" args=Option.get !molecular_provider)
       "Emitter action changed the actual saved native closure";
     reference_invocation mode generated peer name args
   end else if name="call-provider" && mode=Reuse_owner then begin
     require(List.assoc(text "provider_id" args)peer.providers==molecular_wrapper)
       "Molecular nested invocation did not use the registered wrapper";
     let context=match List.find_opt(fun(_,value)->same value(get "context" args))peer.contexts with
       |Some(raw,_)->raw |None->failwith "Molecular wrapper has no actual native context" in
     saved_context:=Some(get "context_id" context);
     Peer_command("call-native-provider",obj["provider_id",str(Option.get !molecular_provider);
       "context_id",Option.get !saved_context],(fun reply->
       let proposal=success(outcome reply) in
       require(text "kind" proposal="proposal" && text "role"(get "view" proposal)="construct_to_molecular.producer")
         "Molecular wrapper lost its real native output";
       let raw=get "value" proposal in
       let links=List.map(fun item->Instance("SourceLink",List.map(fun(key,value)->key,Data value)(Json.object_fields item)))
         (Json.array(get "source_links" raw)) in
       Peer_return(reference peer(Instance("PassResult",["output",Data(get "output" raw);
         "obligations",Data(get "obligations" raw);"source_links",Sequence links;
         "observation_map",Data(get "observation_map" raw);"search_status",Data(get "search_status" raw)])))))
   end else if name="reference-upstream-candidate" then begin
     require(mode=Public_sources && same(get "upstream" args)upstream)"Final candidate callback changed its actual upstream wrapper";
     let phase=text "phase" args in final_reads:= !final_reads@[phase];
     if phase="check" then begin
       require(!final_reads=["check"] && !result_commands=2)"Final candidate read occurred before actual result or was repeated";
       let candidate=get "value"(get "candidate"(Option.get !construct_build)) in
       Peer_return(obj["object",reference peer(Data candidate);"value",candidate;"tree",ordered candidate])
     end else begin
       require(phase="return" && !final_reads=["check";"return"])"Opaque return was read before independent checking";
       Peer_return(obj["object",returned_construct])
     end
   end else
   if name="call-provider" && mode=Wrapped_repeat then begin
     require(List.assoc(text "provider_id" args)peer.providers==wrapper)
       "Nested native calls did not originate in the actually registered wrapper";
     let context,context_ref=match List.find_opt(fun(_,value)->same value(get "context" args))peer.contexts with
       |Some value->value |None->failwith "Wrapper received no actual hydrated context capability" in
     require(same context_ref(get "context" args))"Wrapper context handle changed";
     let call=obj["provider_id",str(Option.get !wrapped_producer);"context_id",get "context_id" context] in
     let proposal event=
       incr direct_calls;
       let result=success(outcome event) in
       require(text "kind" result="proposal" && text "role"(get "view" result)="components_to_construct.producer")
         "Direct native producer changed result kind or closure role";
       let value=get "value" result in
       require(same(unordered(get "tree"(get "view" result)))value)"Direct native result tree differs";
       value in
     Peer_command("call-native-provider",call,(fun first_event->
       let first=proposal first_event in
       Peer_command("call-native-provider",call,(fun second_event->
         let second=proposal second_event in
         require(same first second)"Repeated actual provider/context changed deterministic proposal";
         let links=List.map(fun raw->Instance("SourceLink",List.map(fun(key,value)->key,Data value)(Json.object_fields raw)))
           (Json.array(get "source_links" first)) in
         Peer_return(reference peer(Instance("PassResult",["output",Data(get "output" first);
           "obligations",Data(get "obligations" first);"source_links",Sequence links;
           "observation_map",Data(get "observation_map" first);"search_status",Data(get "search_status" first)])))))))
   end else reference_invocation mode generated peer name args in
 let result=exercise ~limits ~on_reply ~on_invoke peer
   ["initialize-reference",initialize_reference peer request registry manifests] in
 let fatal=List.filter(fun event->text "kind" event="fatal")result.events in
 require(result.closed)"Reference channel did not close";
 if resource_stop then begin
   require(List.length fatal=1 && text "kind"(List.hd(List.rev result.events))="fatal")
     "Reduced shared lifetime cap did not terminate exactly once";
   require(List.for_all(fun event->get "closed" event=Json.Bool true)fatal)
     "Resource failure did not latch channel closure";
   require(!direct_calls=2 && !result_commands=2 && Option.is_some !molecular_build)
     "The one-byte-short lifecycle control did not reach its repeated producer calls and native builds"
 end else begin
 if mode=Foreign_record || mode=Foreign_result then begin
   require(List.length fatal=1 && !construct_build=None && !result_commands=1)"Foreign finish capability acquired a build";
   require(Option.is_some !construct_record && Option.is_some !construct_result)"Capability rejection erased prior framed evidence"
 end else require(fatal=[])"Reference session terminated fatally";
 let invocations name=List.filter(fun event->text "kind" event="invoke" && text "action" event=name)result.events in
 require(List.length(invocations "manager-created")=1)"Manager publication count changed";
 require(List.length(invocations "reference-generate")=(if mode=Wrapped_repeat then 2 else 1))"Construct generator callback count changed";
 if mode=Default_native || mode=Host_valid || mode=Wrapped_repeat || mode=Reuse_owner || mode=Public_sources then begin
   require(List.length(invocations "reference-emit")=(if mode=Reuse_owner then 2 else 1) && !result_commands=2)"Native molecular callback/result cadence changed";
   let roles=List.map(fun event->text "role"(get "arguments" event))(invocations "native-provider"@invocations "reference-molecular-provider") in
   require(List.sort String.compare roles=List.sort String.compare["reference_components.authority";"reference_components.linkage";
     "components_to_construct.producer";"components_to_construct.layout";"construct_to_molecular.producer";
     "construct_to_molecular.sequence";"construct_to_molecular.composition"])"Native reference provider role census changed";
   require(Option.is_some !molecular_build)"Molecular build was not published";
   require(!leave_count=(if mode=Reuse_owner then 2 else 1))"Successful lifecycle omitted an actual leave command";
   if mode=Reuse_owner then require(!reentries=1 && !old_calls=1 && List.length(invocations "call-provider")=1)
     "Same-owner reentry omitted partial failure or saved-provider execution";
   if mode=Host_valid then require(List.length(invocations "reference-proposal")=1 &&
     List.length(invocations "reference-source-links-equal")=1)"Host proposal skipped exact native provenance comparison";
   if mode=Wrapped_repeat then require(!direct_calls=2 && List.length(invocations "call-provider")=1 &&
     List.length(invocations "reference-source-links-equal")=1)
     "Repeated provider wrapper skipped actual calls or duplicate-preserving native provenance"
 end else if not native then require(!result_commands=0 && !construct_build=None)"Host failure fabricated a result or build";
 end;
 result
let repeated_provider_retention request registry manifests=
 let defaults=get "limits" Ch.declaration in
 let baseline=framed_reference ~limits:defaults Wrapped_repeat request registry manifests in
 let retained result=Z.to_int(Json.integer(get "retained_bytes"(get "usage"(List.hd(List.rev result.events))))) in
 let total=retained baseline in
 require(total>1 && total<Z.to_int(Json.integer(get "max_retained_bytes" defaults)))
   "Repeated provider lifecycle did not leave room for a meaningful retention reduction";
 (* Every run sends a complete limit object. Only the decimal limit in the
    received hello changes its retained bytes; account for that exact prefix.
    This bounds the whole shared lifetime, not only the producer-origin table. *)
 let reduction desired=
   let rec settle remaining guess=
     require(remaining>0)"Retention prefix adjustment did not converge";
     let limits=set "max_retained_bytes"(Json.int guess)defaults in
     let actual=desired+String.length(encode limits)-String.length(encode defaults) in
     if actual=guess then limits else settle(remaining-1)actual in
   settle 16 desired in
 let exact_limits=reduction total in
 let exact=framed_reference ~limits:exact_limits Wrapped_repeat request registry manifests in
 require(retained exact=Z.to_int(Json.integer(get "max_retained_bytes" exact_limits)))
   "Exact shared retention did not consume the measured lifecycle bound";
 let short_limits=reduction(total-1) in
 let short=framed_reference ~limits:short_limits ~resource_stop:true Wrapped_repeat request registry manifests in
 require(retained short<=Z.to_int(Json.integer(get "max_retained_bytes" short_limits)))
   "Terminal retained usage exceeded the one-byte-short negotiated cap";
 require(List.length short.replies=List.length exact.replies-1 && fst(List.hd(List.rev exact.replies))="close")
   "The one-byte-short lifecycle control failed before the final accounted close request"
let phase_failures request registry manifests=
 List.iter(fun commands->
   let peer=peer() in
   let result=exercise ~on_invoke:(reference_invocation Default_native(ref None)) peer
     (("initialize-reference",initialize_reference peer request registry manifests)::commands) in
   require(result.closed && List.length(List.filter(fun event->text "kind" event="fatal")result.events)=1)
     "Invalid phase did not close the native authority";
   require(List.for_all(fun(operation,_)->not(List.mem operation["run";"result";"finish-reference-construct";"finish-reference-molecular"]))result.replies)
     "Invalid phase manufactured a run or result")
   [["reference-registration",obj[]];["reference-admission",obj[];"reference-registration",obj[]];
    ["reference-admission",obj[];"reference-admission",obj[]];
    ["reference-molecular-profile",obj["preparation_id",str "preparation/foreign"]]]
let main()=
 require(Array.length Sys.argv=3)"Expected exact callback application declaration and reference caller documents directory";
 require(same(read Sys.argv.(1))A.declaration)"Application declaration differs from installed reference service";
 let load identity=
   let value=read(Filename.concat Sys.argv.(2)(identity^".json")) in
   require(Canonical.fingerprint value=identity)"Original reference caller declaration changed";value in
 let manifests=load "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b" in
 let authorities=["8dd63c98217d58dcc2e9591c279ed82b77ff10523eaa3d49f9115a3ce45327e5","132ada7b1d17ee6bd78700ab7f92d2ea8292ff6da859dd21b6e0bfcffaaf5a78";
   "d6d781141c3f32b4eea90176a1da8e286d115a511b346d5e88645cb85432656f","bf205bf9073363a9d6e3999e0c4b59d1854b563f3ad9ee2cc96a7ecac4bd21a4"] in
 List.iter(fun(request,registry)->let request=load request and registry=load registry in
   phase:="native complete reference workflow";ignore(framed_reference Default_native request registry manifests);
   phase:="public authority and distinct final candidate reads";ignore(framed_reference Public_sources request registry manifests);
   phase:="actual host proposal and exact native provenance";ignore(framed_reference Host_valid request registry manifests);
   phase:="repeated actual provider/context and shared retention boundary";repeated_provider_retention request registry manifests;
   phase:="completed owner reentry and saved provider roots";ignore(framed_reference Reuse_owner request registry manifests);
   phase:="opaque host generator exception";ignore(framed_reference Raise_generator request registry manifests);
   phase:="opaque host candidate schema rejection";ignore(framed_reference Invalid_candidate request registry manifests);
   phase:="foreign historical record capability";ignore(framed_reference Foreign_record request registry manifests);
   phase:="foreign historical result command";ignore(framed_reference Foreign_result request registry manifests);
   phase:="missing and repeated phase operations";phase_failures request registry manifests)authorities;
 print_endline "Reference callback service: actual framed admission, construction, emission, retained builds, host errors and capability failures passed."
let ()=try main() with
 |Diagnostic.Error error as cause->prerr_endline(!phase^": "^error.code^": "^error.message);raise cause
 |cause->prerr_endline(!phase^": "^Printexc.to_string cause);raise cause
