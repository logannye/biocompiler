(* Real framed synchronous transport with scripted host continuations. No
   fabricated accepted manager records: this library has no manager authority. *)
open Bioc_wire
module C = Bioc_pipeline_service.Callback_channel
module W = Bioc_checker.Work_budget
module B = Bioc_artifact.Archive_budget
module M = Bioc_compiler.Pass_manager
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let integer key raw = Z.to_int (Json.integer (get key raw))
let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let encode raw = Canonical.encode_bounded ~max_bytes:33_554_432 raw
let parse raw = Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000 raw
let frame body = Printf.sprintf "%08x\n%s" (String.length body) body
let application = obj ["schema_version",str "callback.channel.test.v1";"operations",Json.Array [str "allocate"]]
let identity = "01234567-89ab-cdef-0123-456789abcdef"
let common kind sequence = ["protocol",str C.protocol;"profile",str C.package_profile;
  "session_id",str identity;"kind",str kind;"sequence",Json.int sequence]
let hello ?(limits=Json.Null) () = obj (common "hello" 0 @ [
  "declaration",C.package_declaration;"application",application;"limits",limits])
let command ?(parent=Json.Null) sequence operation arguments = obj (common "command" sequence @ [
  "parent_invocation",parent;"operation",str operation;"arguments",arguments])
let close sequence = obj (common "close" sequence @ ["parent_invocation",Json.Null])
let continuation sequence invocation raw outcome = obj (common "continue" sequence @ [
  "invocation_id",get "invocation_id" invocation;"invocation_sha256",str (Canonical.sha256 raw);"outcome",outcome])
let returned value = obj ["status",str "return";"value",value]

type harness = {mutable input:string;mutable output:string list;
  mutable on_write:Json.t -> string -> unit}
let harness () = {input="";output=[];on_write=(fun _ _ -> ())}
let enqueue state value = state.input<-state.input ^ frame(encode value)
let consume state count =
  let count=min count(String.length state.input) in
  let result=String.sub state.input 0 count in
  state.input<-String.sub state.input count(String.length state.input-count);result
let io state : C.io = {
  read_header=(fun()->if state.input="" then None else Some(consume state 9));
  read_body=(fun count->consume state count);
  write=(fun bytes->
    require(String.length bytes>=10 && bytes.[8]='\n')"Missing complete output frame";
    let body=String.sub bytes 9(String.length bytes-9) in
    require(int_of_string("0x"^String.sub bytes 0 8)=String.length body)"Wrong output length";
    state.output<-state.output@[body];state.on_write(parse body)body)
}
let target = Bioc_domain.Build_request.Target.of_json(Json.parse {|{"capabilities":[],"compartments":["abstract"],"context_id":"structural","context_version":"1","payload_format":"RNA","resources":{},"schema_version":"biocompiler.target.v0.1"}|})
let payload=obj["schema_version",str "package.channel.input.v1";"nodes",Json.Array[]]
let successful raw=text "kind" raw="reply" && text "status"(get "outcome" raw)="ok"
let controls retained=set "max_retained_bytes"(Json.int retained)(get "limits" C.package_declaration)
let run ?(mixed=false) ?(malformed=false) retained=
  let peer=harness() and channel=ref None and owner=ref None and calls=ref 0 and manager_delta=ref 0 in
  enqueue peer(if malformed then set "declaration" C.declaration(hello ~limits:(controls retained)())
    else hello ~limits:(controls retained)());
  peer.on_write<-(fun raw body->
    if successful raw && integer "sequence" raw=0 then begin
      let active=Option.get !channel in
      let actual=Option.get(C.package_budget active) in owner:=Some actual;
      require(B.owns_retention actual && B.work actual==C.budget active)"Hello exposed another retention/work owner";
      require(integer "retained_bytes"(get "usage" raw)=B.retained actual)"Hello omitted owner retention";
      if mixed then enqueue peer(command 1 "allocate" Json.Null)
    end else if text "kind" raw="invoke" then begin
      enqueue peer(continuation 2 raw body(returned Json.Null));enqueue peer(close 3)
    end);
  let dispatch state (_:C.command)=
    incr calls;
    let budget=C.budget state and actual=Option.get(C.package_budget state) in
    let before=B.retained actual in
    let manager=M.create ~budget ~target ~dependencies:["request",Canonical.fingerprint payload]() in
    ignore(M.add_input manager ~identity:"request" payload);
    manager_delta:=B.retained actual-before;
    require(!manager_delta>0)"Actual manager retained state escaped package ownership";
    let child=W.nested ~parent:budget ~profile:"package.child" ~error_code:"package.child.work" ~maximum:100() in
    let prior=B.retained actual in W.retain child 17;C.retain_bytes state 19;
    require(B.retained actual=prior+36)"Child and framing retained different owners";
    ignore(C.invoke state ~action:"host" ~arguments:Json.Null);
    C.Success Json.Null in
  let actual=C.create_package ~io:(io peer)~application ~dispatch() in
  channel:=Some actual;
  require(C.package_budget actual=None)"Owner existed before negotiated reductions";
  C.run actual;
  let outputs=List.map parse peer.output in
  outputs,!owner,!calls,!manager_delta
let first_hello outputs=match outputs with value::_->successful value && integer "sequence" value=0|[]->false
let last outputs=List.hd(List.rev outputs)
let final_retained outputs=integer "retained_bytes"(get "usage"(last outputs))
let exact_retained mixed=
  let rec settle count selected=
    require(count<12)"Retained handshake size did not converge";
    let outputs,_,_,_=run ~mixed selected in
    require(first_hello outputs)"Resource baseline lost hello";
    if mixed then require(text "kind"(last outputs)="reply" && Json.boolean(get "closed"(last outputs)))"Mixed baseline failed";
    let observed=final_retained outputs in
    if observed=selected then selected else settle(count+1)observed in
  settle 0 536_870_912
let profiles ()=
  require(integer "max_retained_bytes"(get "limits" C.declaration)=134_217_728)"General callback ceiling changed";
  require(integer "max_retained_bytes"(get "limits" C.package_declaration)=536_870_912)"Package profile ceiling differs";
  let outputs,owner,calls,_=run ~malformed:true 536_870_912 in
  require(not(first_hello outputs) && text "kind"(last outputs)="fatal" && owner=None && calls=0)
    "Wrong declaration installed an owner or published acceptance";
  let outputs,owner,calls,_=run 1 in
  require(not(first_hello outputs) && text "kind"(last outputs)="fatal" && owner=None && calls=0)
    "Pre-owner resource failure exposed a manager"
let boundaries ()=
  let hello_limit=exact_retained false in
  let exact,_,calls,_=run hello_limit in
  require(first_hello exact && calls=0)"Exact hello retention rejected";
  let short,_,calls,_=run(hello_limit-1) in
  require(not(first_hello short) && calls=0 && text "kind"(last short)="fatal")"One-short hello escaped";
  let mixed_limit=exact_retained true in
  let exact,owner,calls,delta=run ~mixed:true mixed_limit in
  require(calls=1 && delta>0 && Option.is_some owner && text "kind"(last exact)="reply")"Exact mixed owner rejected";
  let short,_,calls,delta=run ~mixed:true(mixed_limit-1) in
  require(calls=1 && delta>0 && text "kind"(last short)="fatal")"One-short mixed owner published completion";
  require(final_retained short<=mixed_limit-1)"Failed ownership reservation advanced its counter"
let ()=profiles();boundaries();print_endline "Package hello, manager, callback and lifetime ownership passed"
