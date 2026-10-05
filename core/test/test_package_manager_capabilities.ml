(* Complete real manager get/result commands, bound to actual suspended package
   invocations. No serialized accepted record enters the manager. *)
open Bioc_wire
module A=Bioc_pipeline_service.Callback_manager
module Ch=Bioc_pipeline_service.Callback_channel
module B=Bioc_artifact.Archive_budget
module M=Bioc_compiler.Pass_manager
module C=Bioc_domain.Pipeline_contract
let require value message=if not value then failwith message
let obj values=Json.Object values
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let integer key raw=Z.to_int(Json.integer(get key raw))
let encode=Canonical.encode
let frame raw=let body=encode raw in Printf.sprintf "%08x\n%s"(String.length body)body
let rec ordered=function
 |Json.Object values->Json.Array[str"object";Json.Array(List.map(fun(key,value)->Json.Array[str key;ordered value])values)]
 |Json.Array values->Json.Array[str"array";Json.Array(List.map ordered values)]
 |value->Json.Array[str"scalar";value]
let target=Bioc_domain.Build_request.Target.of_json(Json.parse {|{"schema_version":"biocompiler.target.v0.1","context_id":"fixture","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["abstract"],"resources":{}}|})
let payload=obj["schema_version",str "package.capability.input.v1";"nodes",Json.Array[]]
let dependency=Canonical.fingerprint payload
let profile=C.Completion_profile.make ~scope:"input" ~stage:C.Intent ~schema:"package.capability.input.v1" ~obligations:["pending"]()
let application=obj["manager",A.declaration;"test",str "actual-package-operation-capabilities.v1"]
type mode=Current_get|Stale_get|Wrong_invocation|Wrong_manager|Current_result|Stale_result
let exercise mode=
 let incoming=ref"" and events=ref[] and sequence=ref 0 and pending=ref None and stale=ref(-1) in
 let objects=ref["object/0",Bioc_domain.Build_request.Target.to_json target;"object/1",payload;"object/2",Json.Array[]] in
 let next=ref 3 in
 let retain value=let id="object/"^string_of_int !next in incr next;objects:=(id,value)::!objects;obj["handle",str id] in
 let deref raw=List.assoc(text"handle"raw)!objects in
 let send kind values=let current= !sequence in incr sequence;
   incoming:= !incoming^frame(obj(["protocol",str Ch.protocol;"profile",str Ch.package_profile;
     "session_id",str"01234567-89ab-cdef-0123-456789abcdef";"kind",str kind;"sequence",Json.int current]@values));current in
 let command ?(parent=Json.Null) name arguments=send"command"["parent_invocation",parent;"operation",str name;"arguments",arguments] in
 let complete event body value=ignore(send"continue"["invocation_id",get"invocation_id"event;
   "invocation_sha256",str(Canonical.sha256 body);"outcome",obj["status",str"return";"value",value]]) in
 let consume count=let count=min count(String.length !incoming) in let value=String.sub !incoming 0 count in
   incoming:=String.sub !incoming count(String.length !incoming-count);value in
 let selected=match mode with Current_result|Stale_result->"result"|_->"get" in
 let operation_args=if selected="get"then obj["identity",str"input"]else obj["identity",str"input";"scope",str"input"] in
 let initialization=obj["target",Bioc_domain.Build_request.Target.to_json target;
   "dependencies",Json.Array[Json.Array[str"request";str dependency]];
   "completion_profiles",Json.Array[C.Completion_profile.to_json profile];"manager_limits",Json.Null;
   "target_object",obj["handle",str"object/0"]] in
 let input=obj["identity",str"input";"stage",str"typed intent and contracts";"requirements",Json.Array[];
   "obligations",Json.Array[];"obligation_objects",Json.Array[];"obligations_object",obj["handle",str"object/2"];
   "payload",obj["handle",str"object/1"]] in
 let phase=ref 0 in
 let io:Ch.io={read_header=(fun()->if !incoming=""then None else Some(consume 9));read_body=consume;
   write=(fun framed->let body=String.sub framed 9(String.length framed-9) in let event=Json.parse_artifact
       ~max_bytes:33_554_432 ~max_nodes:1_000_000 body in events:=event::!events;
     match text"kind"event with
     |"fatal"->()
     |"reply"->
       require(text"status"(get"outcome"event)="ok")"Fixture manager command rejected";
       (match !pending with
        |Some(invocation,raw,current) when integer"sequence"event=current->pending:=None;
          let use=match mode with Stale_get|Stale_result-> !stale|_->current in
          complete invocation raw(Json.int use)
        |_->if not(Json.boolean(get"closed"event))then begin
          (match !phase with
           |0->ignore(command"initialize-empty"initialization)
           |1->ignore(command"add-input"input)
           |2->stale:=command selected operation_args
           |3->ignore(command"probe"Json.Null)
           |4->ignore(send"close"["parent_invocation",Json.Null])
           |_->failwith"Unexpected fixture reply");incr phase end)
     |"invoke"->
       let action=text"action"event and args=get"arguments"event in
       if action="probe"then begin
         let current=command ~parent:(get"invocation_id"event)selected operation_args in
         pending:=Some(event,body,current)
       end else begin
         let value key=deref(get key args) in
         let result=match action with
          |"document"|"freeze-json"->get"object"args
          |"ordered-json"->ordered(value"object")
          |"literal"->retain(get"value"args)
          |"is-instance"->Json.Bool(match text"type"args,value"object"with
             |"Mapping",Json.Object _|"str",Json.String _->true|_->false)
          |"get-item"->retain(get(Json.string(value"key"))(value"object"))
          |"attr"->(match text"name"args,value"object"with
             |"get",Json.Object _->retain(obj["mapping",value"object"])
             |"strip",Json.String value->retain(obj["stripped",str(String.trim value)])
             |_->failwith"Unexpected fixture attribute")
          |"call"->let callable=value"callable" in
             if List.mem_assoc"mapping"(Json.object_fields callable)then
               let key=deref(List.hd(Json.array(get"args"args)))|>Json.string in retain(get key(get"mapping"callable))
             else retain(get"stripped"callable)
          |"truth"->Json.Bool(value"object"<>str"")
          |"attr-default"->get"default"args
          |"compare"->Json.Bool(not(Json.equal(value"left")(value"right")))
          |_->failwith("Unexpected fixture broker action: "^action) in complete event body result
       end
     |_->failwith"Unexpected fixture event")} in
 ignore(send"hello"["declaration",Ch.package_declaration;"application",application;"limits",Json.Null]);
 let extension state channel (command:Ch.command)=if command.operation<>"probe"then None else begin
   let invocation,raw=Ch.invoke_bound channel ~action:"probe" ~arguments:Json.Null in
   let seq=Z.to_int(Json.integer raw) in
   let manager=A.manager_capability state ~channel in
   let manager=if mode=Wrong_manager then M.create ~budget:(Ch.budget channel) ~target ~dependencies:["request",dependency]()else manager in
   let invocation=if mode=Wrong_invocation then invocation+1 else invocation in
   (if selected="get"then ignore(A.get_return_capability state ~channel ~manager ~sequence:seq ~invocation ~identity:"input")
    else ignore(A.result_return_capability state ~channel ~manager ~sequence:seq ~invocation ~identity:"input" ~scope:"input"));
   require(B.work(Option.get(Ch.package_budget channel))==Ch.budget channel)"Manager ledger lost package owner";
   Some(Ch.Success(Json.Bool true)) end in
 let manager=A.create_package ~io ~application ~extension() in A.run manager;
 let last=List.hd !events in
 let should_pass=mode=Current_get || mode=Current_result in
 require((text"kind"last="reply" && Json.boolean(get"closed"last))=should_pass)
   "Stale/foreign package operation capability crossed its actual invocation boundary";
 if not should_pass then require(text"kind"last="fatal")"Capability misuse did not close authority"
let ()=List.iter exercise[Current_get;Stale_get;Wrong_invocation;Wrong_manager;Current_result;Stale_result];
 print_endline"Exact live package command/owner/invocation capabilities passed"
