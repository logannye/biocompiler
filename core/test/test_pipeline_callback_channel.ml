(* Real framed synchronous transport with scripted host continuations. No
   fabricated accepted manager records: this library has no manager authority. *)
open Bioc_wire
module C = Bioc_pipeline_service.Callback_channel
module W = Bioc_checker.Work_budget
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let integer key raw = Z.to_int (Json.integer (get key raw))
let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let encode raw = Canonical.encode_bounded ~max_bytes:33_554_432 raw
let parse raw = Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000 raw
let equal message left right = require (encode left=encode right) message
let frame body = Printf.sprintf "%08x\n%s" (String.length body) body
let application = obj ["schema_version",str "callback.channel.test.v1";"operations",Json.Array [str "echo";str "callback"]]
let identity = "01234567-89ab-cdef-0123-456789abcdef"
let common kind sequence = ["protocol",str C.protocol;"profile",str C.profile;
  "session_id",str identity;"kind",str kind;"sequence",Json.int sequence]
let hello ?(limits=Json.Null) () = obj (common "hello" 0 @ [
  "declaration",C.declaration;"application",application;"limits",limits])
let command ?(parent=Json.Null) sequence operation arguments = obj (common "command" sequence @ [
  "parent_invocation",parent;"operation",str operation;"arguments",arguments])
let close sequence = obj (common "close" sequence @ ["parent_invocation",Json.Null])
let continuation sequence invocation raw outcome = obj (common "continue" sequence @ [
  "invocation_id",get "invocation_id" invocation;"invocation_sha256",str (Canonical.sha256 raw);"outcome",outcome])
let returned value = obj ["status",str "return";"value",value]
let raised token = obj ["status",str "raise";"token",str token]
let rec nodes = function
  | Json.Object values -> 1+List.fold_left (fun count (_,value) -> count+1+nodes value) 0 values
  | Json.Array values -> 1+List.fold_left (fun count value -> count+nodes value) 0 values
  | _ -> 1

type harness = {mutable input:string;mutable output:string list;mutable reads:int list;
  mutable trace:(bool*string) list;mutable writes:int;mutable on_write:Json.t -> string -> unit;
  mutable header_error:exn option;mutable body_error:exn option;mutable write_error:bool}
let harness () = {input="";output=[];reads=[];trace=[];writes=0;on_write=(fun _ _ -> ());
  header_error=None;body_error=None;write_error=false}
let enqueue_raw state value = state.input<-state.input ^ value
let enqueue state value = enqueue_raw state (frame (encode value))
let consume state count =
  let count=min count (String.length state.input) in
  let result=String.sub state.input 0 count in
  state.input<-String.sub state.input count (String.length state.input-count);result
let io state : C.io = {
  read_header=(fun () -> state.reads<-state.reads@[9];
    match state.header_error with Some error -> raise error | None ->
    if state.input="" then None else Some (consume state 9));
  read_body=(fun count -> state.reads<-state.reads@[count];
    match state.body_error with Some error -> raise error | None ->
    let body=consume state count in state.trace<-state.trace@[true,body];body);
  write=(fun bytes -> state.writes<-state.writes+1;
    if state.write_error then (
      state.output<-state.output@[String.sub bytes 0 (min 13 (String.length bytes))];
      raise (Sys_error "injected partial write"));
    require (String.length bytes>=10 && bytes.[8]='\n') "Missing complete output frame";
    let body=String.sub bytes 9 (String.length bytes-9) in
    require (int_of_string ("0x"^String.sub bytes 0 8)=String.length body) "Wrong output frame length";
    state.trace<-state.trace@[false,body];state.output<-state.output@[body];
    state.on_write (parse body) body)
}
let create state dispatch = C.create ~io:(io state) ~application ~dispatch ()
let responses state = List.map parse state.output
let last state = List.hd (List.rev (responses state))
let success raw = let result=get "outcome" raw in
  require (text "status" result="ok") "Expected successful reply";get "value" result
let fatal state channel =
  require (C.is_closed channel) "Fatal channel revived";
  let replies=responses state in
  let count=List.fold_left (fun count raw -> if text "kind" raw="fatal" then count+1 else count) 0 replies in
  require (count=1 && text "kind" (last state)="fatal") "Expected exactly one terminal frame";
  List.iteri (fun index raw -> require (integer "event_id" raw=index) "Server event sequence skipped") replies;
  let raw=List.hd (List.rev state.output) in
  require (String.length raw+9<=8192) "Fatal exceeded prepaid capacity";
  require (Json.boolean (get "closed" (last state))) "Fatal did not bind closure";
  let before=state.writes in
  (try ignore (C.invoke channel ~action:"late" ~arguments:Json.Null);failwith "Closed invocation resumed"
   with C.Closed -> ());
  require (state.writes=before) "Closed channel wrote another frame"
let census state =
  let input=ref 0 and output=ref 0 and count=ref 0 and frames=ref 0 and event=ref 0 in
  List.iter (fun (incoming,body) ->
    let raw=parse body in
    incr frames;count:= !count+nodes raw;
    if incoming then input:= !input+String.length body+9 else (
      output:= !output+String.length body+9;
      let usage=get "usage" raw in
      require (integer "event_id" raw= !event) "Nonmonotone server event";incr event;
      require (integer "input_bytes" usage= !input) "Input frame census differs";
      require (integer "output_bytes" usage= !output) "Output frame census differs";
      require (integer "frames" usage= !frames) "Lifetime frame census differs";
      require (integer "json_nodes" usage= !count) "Lifetime key/value census differs";
      require (integer "work_charged" usage+integer "work_remaining" usage=1_000_000_000_000)
        "Lifetime work ancestor differs")) state.trace
let echo _ (command:C.command) = C.Success command.arguments
let test_simple () =
  let h=harness () in
  enqueue h (hello ());let request=command 1 "echo" (Json.int 37) in enqueue h request;enqueue h (close 2);
  let state=create h echo in C.run state;
  require (C.is_closed state && h.input="") "Close did not stop after exact input";
  (match responses h with [greeting;reply;closed] ->
    let result=success greeting in equal "Hello transport declaration differs" (get "declaration" result) C.declaration;
    equal "Hello application declaration differs" (get "application" result) application;
    equal "Echo changed value" (success reply) (Json.int 37);
    equal "Reply lost exact request bytes" (get "request_sha256" reply) (str (Canonical.sha256 (encode request)));
    require (integer "sequence" reply=1 && Json.boolean (get "closed" closed)) "Reply binding or closure differs"
   | _ -> failwith "Wrong simple reply count");
  census h
let test_nested () =
  let h=harness () and mutations=ref [] and outer=ref None and inner=ref None in
  let outer_request=command 1 "outer" Json.Null in
  let nested_request=ref Json.Null in
  enqueue h (hello ());enqueue h outer_request;
  h.on_write<-(fun raw body -> match text "kind" raw with
    | "invoke" when text "action" raw="outer" ->
        outer:=Some (raw,body);
        require (get "parent_invocation" raw=Json.Null && integer "command_sequence" raw=1)
          "Outer invocation parent differs";
        require (integer "pending_invocations" (get "usage" raw)=1) "Outer depth absent";
        nested_request:=command ~parent:(get "invocation_id" raw) 2 "inner" Json.Null;
        enqueue h !nested_request
    | "invoke" ->
        inner:=Some (raw,body);
        let parent,_=Option.get !outer in
        equal "Nested callback parent differs" (get "parent_invocation" raw) (get "invocation_id" parent);
        require (integer "pending_invocations" (get "usage" raw)=2 && integer "command_sequence" raw=2)
          "Inner callback stack differs";
        equal "Inner exact command hash differs" (get "command_sha256" raw) (str (Canonical.sha256 (encode !nested_request)));
        enqueue h (continuation 3 raw body (returned (str "inner result")))
    | "reply" when integer "sequence" raw=2 ->
        equal "Nested result differs" (success raw) (str "inner result");
        require (integer "pending_invocations" (get "usage" raw)=1) "Nested return erased outer invocation";
        let parent,body=Option.get !outer in enqueue h (continuation 4 parent body (returned (str "outer result")))
    | "reply" when integer "sequence" raw=1 ->
        equal "Outer result differs" (success raw) (str "outer result");
        require (integer "pending_invocations" (get "usage" raw)=0) "Completed invocation remained pending";
        enqueue h (close 5)
    | _ -> ());
  let dispatch state (command:C.command) =
    mutations:= !mutations@["before:"^command.operation];
    let value=C.invoke state ~action:command.operation ~arguments:(str command.operation) in
    mutations:= !mutations@["after:"^command.operation];C.Success value in
  let state=create h dispatch in C.run state;
  require (!mutations=["before:outer";"before:inner";"after:inner";"after:outer"])
    "Nested dispatch did not resume actual suspended stack";
  require (!inner<>None && C.is_closed state && h.input="") "Nested campaign incomplete";
  census h
let test_host_exception () =
  let h=harness () and mutations=ref [] in
  enqueue h (hello ());enqueue h (command 1 "raise" Json.Null);
  h.on_write<-(fun raw body -> match text "kind" raw with
    | "invoke" -> enqueue h (continuation 2 raw body (raised "original-exception-7"))
    | "reply" when integer "sequence" raw=1 ->
        equal "Host exception token changed" (get "outcome" raw) (raised "original-exception-7");
        require (not (Json.boolean (get "closed" raw))) "Real host exception closed channel";
        enqueue h (command 3 "inspect" Json.Null);enqueue h (close 4)
    | _ -> ());
  let state=create h (fun channel (command:C.command) ->
    if command.operation="raise" then (
      mutations:= !mutations@["before"];
      try ignore (C.invoke channel ~action:"producer" ~arguments:Json.Null);failwith "Expected host exception"
      with C.Host_exception token as error ->
        require (token="original-exception-7") "Host token altered before dispatcher";
        mutations:= !mutations@["caught"];raise error)
    else C.Success (Json.Array (List.map str !mutations))) in
  C.run state;
  equal "State before host exception was rolled back" (success (List.nth (responses h) 3))
    (Json.Array [str "before";str "caught"]);
  census h
let test_rejection_and_internal () =
  let h=harness () and mutated=ref false in
  enqueue h (hello ());enqueue h (command 1 "reject" Json.Null);enqueue h (command 2 "internal" Json.Null);
  let state=create h (fun _ (command:C.command) -> mutated:=true;
    if command.operation="reject" then C.Rejected (str "expected") else failwith "unexpected application failure") in
  C.run state;
  require !mutated "Mutation before failure was not executed";
  let rejected=List.nth (responses h) 1 in
  require (text "status" (get "outcome" rejected)="rejected" && not (Json.boolean (get "closed" rejected)))
    "Explicit rejection did not retain session";
  fatal h state
let test_bad_continuations () =
  let cases=["stale id",(fun raw -> set "invocation_id" (Json.int 0) raw);
    "wrong hash",(fun raw -> set "invocation_sha256" (str (String.make 64 '0')) raw);
    "wrong session",(fun raw -> set "session_id" (str "11234567-89ab-cdef-0123-456789abcdef") raw);
    "replayed sequence",(fun raw -> set "sequence" (Json.int 1) raw);
    "skipped sequence",(fun raw -> set "sequence" (Json.int 3) raw);
    "unknown field",(fun raw -> set "extra" Json.Null raw);
    "wrong profile",(fun raw -> set "profile" (str "other") raw);
    "invalid outcome",(fun raw -> set "outcome" (obj ["status",str "return";"value",Json.Null;"token",str "extra"]) raw);
    "long token",(fun raw -> set "outcome" (raised (String.make 129 'x')) raw)] in
  List.iter (fun (name,mutate) ->
    let h=harness () and resumed=ref false and caught=ref false in
    enqueue h (hello ());enqueue h (command 1 "callback" Json.Null);
    h.on_write<-(fun raw body -> if text "kind" raw="invoke" then enqueue h (mutate (continuation 2 raw body (returned Json.Null))));
    let state=create h (fun channel _ ->
      (try ignore (C.invoke channel ~action:"callback" ~arguments:Json.Null);resumed:=true
       with C.Closed -> caught:=true);C.Success (str "must never publish")) in
    C.run state;
    require (not !resumed && !caught) (name^": callback resumed or closure escaped incorrectly");fatal h state)
    cases
let test_wrong_nested_parent () =
  List.iter (fun parent ->
    let h=harness () and nested=ref false in
    enqueue h (hello ());enqueue h (command 1 "outer" Json.Null);
    h.on_write<-(fun raw _ -> if text "kind" raw="invoke" then enqueue h (command ~parent 2 "nested" Json.Null));
    let state=create h (fun channel (command:C.command) ->
      if command.operation="nested" then (nested:=true;C.Success Json.Null)
      else C.Success (C.invoke channel ~action:"outer" ~arguments:Json.Null)) in
    C.run state;require (not !nested) "Wrong-parent nested command executed";fatal h state)
    [Json.Null;Json.int 0;Json.int 99]
let test_outer_continuation_during_inner () =
  let h=harness () and outer=ref None in
  enqueue h (hello ());enqueue h (command 1 "outer" Json.Null);
  h.on_write<-(fun raw body -> if text "kind" raw="invoke" then
    if !outer=None then (outer:=Some (raw,body);enqueue h (command ~parent:(get "invocation_id" raw) 2 "inner" Json.Null))
    else let raw,body=Option.get !outer in enqueue h (continuation 3 raw body (returned Json.Null)));
  let state=create h (fun channel (command:C.command) -> C.Success (C.invoke channel ~action:command.operation ~arguments:Json.Null)) in
  C.run state;fatal h state
let test_framing () =
  List.iter (fun raw ->
    let h=harness () in enqueue_raw h raw;
    let state=create h echo in C.run state;fatal h state;
    require (h.reads=[9]) "Invalid header allocated or read its body")
    ["0000000";"0000000A\n";"0000000g\n";"00000001x";"00000000\n";"02000001\n";""];
  List.iter (fun raw ->
    let h=harness () in enqueue_raw h raw;
    let state=create h echo in C.run state;fatal h state)
    ["00000002\n{";frame "{";frame "{\"protocol\":1,\"protocol\":2}";frame "[]"];
  let h=harness () in enqueue h (hello ());h.body_error<-Some End_of_file;
  let state=create h echo in C.run state;fatal h state;
  let h=harness () in h.header_error<-Some C.Closed;
  let state=create h echo in C.run state;fatal h state
let test_uncertain_write () =
  List.iter (fun during_callback ->
    let h=harness () in enqueue h (hello ());enqueue h (command 1 "callback" Json.Null);
    if during_callback then h.on_write<-(fun raw _ -> if text "kind" raw="reply" then h.write_error<-true)
    else h.write_error<-true;
    let state=create h (fun channel _ -> C.Success (C.invoke channel ~action:"callback" ~arguments:Json.Null)) in
    C.run state;
    require (C.is_closed state && h.writes=(if during_callback then 2 else 1))
      "Uncertain write was retried or followed by fatal";
    require (List.length h.output=h.writes) "Unexpected write accounting") [false;true]
let controls key value = set key (Json.int value) (get "limits" C.declaration)
let test_reductions () =
  List.iter (fun limits ->
    let h=harness () in enqueue h (hello ~limits ());
    let state=create h echo in C.run state;fatal h state)
    [controls "max_frame_bytes" 1;controls "max_total_bytes" 8192;
     controls "max_work" 1_000_000;controls "max_json_nodes" 1;
     controls "max_retained_bytes" 1;controls "max_frames" 2;
     controls "max_commands" 0;controls "max_work" 1_000_000_000_001;
     obj ["max_work",Json.int 1_000_000_000_000]];
  let h=harness () in enqueue h (hello ~limits:(controls "max_commands" 1) ());enqueue h (command 1 "echo" Json.Null);
  let state=create h echo in C.run state;fatal h state;
  require (text "kind" (List.hd (responses h))="reply") "Valid prefix reduction rejected hello";
  let h=harness () in enqueue h (hello ~limits:(controls "max_frames" 3) ());enqueue h (close 1);
  let state=create h echo in C.run state;fatal h state;
  require (h.reads=[9;String.length (encode (hello ~limits:(controls "max_frames" 3) ()))])
    "Frame limit read a forbidden header"
let test_lifetime_resources () =
  List.iter (fun operation ->
    let h=harness () and caught=ref false in
    enqueue h (hello ());enqueue h (command 1 operation Json.Null);
    let state=create h (fun channel _ ->
      (try
        if operation="retention" then C.retain_bytes channel 134_217_729
        else let budget=C.budget channel in
          let child=if operation="child work" then W.nested ~parent:budget ~profile:"child"
            ~error_code:"child_limit" ~maximum:0 () else budget in
          W.charge child (if operation="child work" then 1 else W.remaining budget+1)
       with C.Closed | Diagnostic.Error _ -> caught:=true);
      C.Success (str "forbidden after swallowed exhaustion")) in
    C.run state;require !caught "Expected resource exhaustion was not reached";fatal h state)
    ["retention";"work";"child work"];
  let h=harness () in
  enqueue h (hello ~limits:(controls "max_pending_invocations" 1) ());enqueue h (command 1 "outer" Json.Null);
  h.on_write<-(fun raw _ -> if text "kind" raw="invoke" then enqueue h (command ~parent:(get "invocation_id" raw) 2 "inner" Json.Null));
  let state=create h (fun channel (command:C.command) -> C.Success (C.invoke channel ~action:command.operation ~arguments:Json.Null)) in
  C.run state;fatal h state;
  require (List.length (responses h)=3) "Depth overflow published a forbidden nested invocation"
let test_lifetime_nodes () =
  let h=harness () in enqueue h (hello ());enqueue h (close 1);
  let state=create h echo in C.run state;
  let greeting=List.hd (responses h) in
  let prefix_extra=nodes (hello ~limits:(controls "max_json_nodes" 1) ())-nodes (hello ()) in
  let minimum=integer "json_nodes" (get "usage" greeting)+prefix_extra+10 in
  let h=harness () in enqueue h (hello ~limits:(controls "max_json_nodes" minimum) ());enqueue h (command 1 "echo" (Json.Array (List.init 30 (fun _ -> Json.Null))));
  let state=create h echo in C.run state;fatal h state;
  require (List.length (responses h)=2) "Cumulative parser node limit was only enforced per frame"
let test_resource_profile () =
  require (C.protocol="biocompiler.pipeline_callback_channel.v1" &&
    C.profile="biocompiler.core.pipeline_callback_channel.v2") "Framing or resource profile identity differs";
  require (integer "max_json_nodes" (get "limits" C.declaration)=2_000_000 &&
    integer "max_frame_json_nodes" (get "fixed_limits" C.declaration)=1_000_000)
    "Resource profile conflates frame and lifetime nodes";
  let original_profile=str "biocompiler.core.pipeline_callback_channel.v1" in
  let original=set "profile" original_profile
    (set "limits" (controls "max_json_nodes" 1_000_000)
      (set "fixed_limits" (obj (List.remove_assoc "max_frame_json_nodes"
        (Json.object_fields (get "fixed_limits" C.declaration)))) C.declaration)) in
  List.iter (fun greeting ->
    let h=harness () and dispatched=ref false in
    enqueue h greeting;enqueue h (command 1 "echo" Json.Null);
    let state=create h (fun _ _ -> dispatched:=true;C.Success Json.Null) in
    C.run state;fatal h state;
    require (not !dispatched && List.length (responses h)=1)
      "Old resource declaration reached application dispatch")
    [set "profile" original_profile (set "declaration" original (hello ()));
     set "declaration" original (hello ())]
let node_session limits left right =
  let h=harness () and dispatched=ref 0 in
  enqueue h (hello ~limits ());
  enqueue h (command 1 "consume" (Json.Array (List.init left (fun _ -> Json.Null))));
  enqueue h (command 2 "consume" (Json.Array (List.init right (fun _ -> Json.Null))));
  enqueue h (close 3);
  let state=create h (fun _ _ -> incr dispatched;C.Success Json.Null) in
  C.run state;h,state,!dispatched
let test_profile_lifetime_boundary () =
  (* Derive framing overhead from a complete real exchange. Only array cardinality
     changes, so an independent key/value census fixes the exact lifetime total. *)
  let payloads limits =
    let baseline,_,count=node_session limits 0 0 in
    require (count=2 && Json.boolean (get "closed" (last baseline))) "Node baseline did not close";
    census baseline;
    let remaining=2_000_000-integer "json_nodes" (get "usage" (last baseline)) in
    let left=remaining/2 in
    let right=remaining-left in
    List.iter (fun count -> require (count+nodes (command 1 "consume" (Json.Array []))<=1_000_000)
      "Lifetime fixture exceeds the independent frame ceiling") [left;right];
    left,right in
  let left,right=payloads Json.Null in
  let exact,_,count=node_session Json.Null left right in
  require (count=2 && Json.boolean (get "closed" (last exact)) &&
    text "kind" (last exact)="reply" && integer "json_nodes" (get "usage" (last exact))=2_000_000)
    "Default profile did not admit its exact cumulative node boundary";
  census exact;
  let left,right=payloads (controls "max_json_nodes" 2_000_000) in
  let short,state,count=node_session (controls "max_json_nodes" 1_999_999) left right in
  fatal short state;
  require (count=2 && short.input="" && List.length (responses short)=4)
    "One-short lifetime limit did not withhold only the final close reply";
  let reduced,state,count=node_session (controls "max_json_nodes" 1_000_000) left right in
  fatal reduced state;
  require (count<2) "Reduced original lifetime ceiling was reset or ignored"
let test_frame_node_boundaries () =
  let run incoming count =
    let h=harness () and dispatched=ref false in
    let large=Json.Array (List.init count (fun _ -> Json.Null)) in
    enqueue h (hello ());
    enqueue h (command 1 "frame" (if incoming then large else Json.Null));
    enqueue h (close 2);
    let state=create h (fun _ _ -> dispatched:=true;C.Success (if incoming then Json.Null else large)) in
    C.run state;h,state,!dispatched in
  List.iter (fun incoming ->
    let baseline,_,_=run incoming 0 in
    let overhead=if incoming then nodes (command 1 "frame" (Json.Array []))
      else nodes (List.nth (responses baseline) 1) in
    let exact,_,dispatched=run incoming (1_000_000-overhead) in
    require (dispatched && text "kind" (last exact)="reply" &&
      Json.boolean (get "closed" (last exact))) "Exact frame node boundary was rejected";
    census exact;
    let overflow,state,dispatched=run incoming (1_000_001-overhead) in
    fatal overflow state;
    require (dispatched=(not incoming) && List.length (responses overflow)=2)
      "Oversized frame reached dispatch or publication under the larger lifetime ceiling") [true;false]
let test_retention_no_refund () =
  let h=harness () and retentions=ref [] and next=ref 2 in
  enqueue h (hello ());enqueue h (command 1 "twice" Json.Null);
  h.on_write<-(fun raw body -> if text "kind" raw="invoke" then (
    retentions:= !retentions@[integer "retained_bytes" (get "usage" raw)];
    enqueue h (continuation !next raw body (returned (str (String.make 500 'r'))));incr next)
    else if text "kind" raw="reply" && integer "sequence" raw=1 then enqueue h (close !next));
  let state=create h (fun channel _ ->
    ignore (C.invoke channel ~action:"first" ~arguments:Json.Null);
    ignore (C.invoke channel ~action:"second" ~arguments:Json.Null);C.Success Json.Null) in
  C.run state;
  (match !retentions with [first;second] -> require (second>first+500) "Released completion was refunded"
   | _ -> failwith "Both completions were not executed");census h
let test_wrong_hello_and_unsolicited () =
  List.iter (fun request -> let h=harness () in enqueue h request;
    let state=create h echo in C.run state;fatal h state)
    [set "application" Json.Null (hello ());set "declaration" Json.Null (hello ());
     command 0 "echo" Json.Null;set "extra" Json.Null (hello ())];
  List.iter (fun request -> let h=harness () in enqueue h (hello ());enqueue h request;
    let state=create h echo in C.run state;fatal h state)
    [set "sequence" (Json.int 1) (hello ());
     obj (common "continue" 1 @ ["invocation_id",Json.int 0;"invocation_sha256",str (String.make 64 '0');"outcome",returned Json.Null]);
     command ~parent:(Json.int 0) 1 "echo" Json.Null]
let test_output_budget_event () =
  let h=harness () in
  enqueue h (hello ~limits:(controls "max_total_bytes" 24_000) ());enqueue h (command 1 "large" Json.Null);
  let state=create h (fun _ _ -> C.Success (str (String.make 12_000 'x'))) in
  C.run state;fatal h state;
  require (List.length (responses h)=2 && integer "event_id" (last h)=1)
    "Failed output reservation skipped an unpublished event"
let test_mutated_input_body_binding () =
  let h=harness () in enqueue h (hello ());
  let request=" \n" ^ encode (command 1 "echo" Json.Null) ^ " " in
  enqueue_raw h (frame request);enqueue h (close 2);
  let state=create h echo in C.run state;
  equal "Reply used recanonicalized request hash" (get "request_sha256" (List.nth (responses h) 1))
    (str (Canonical.sha256 request));census h
let read path = let channel=open_in_bin path in
  Fun.protect (fun () -> really_input_string channel (in_channel_length channel)) ~finally:(fun () -> close_in channel)
let () =
  require (Array.length Sys.argv=2) "Expected callback declaration path";
  equal "Embedded channel declaration differs from repository authority" C.declaration (parse (read Sys.argv.(1)));
  List.iter (fun test -> test ()) [test_simple;test_nested;test_host_exception;test_rejection_and_internal;
    test_bad_continuations;test_wrong_nested_parent;test_outer_continuation_during_inner;test_framing;
    test_uncertain_write;test_reductions;test_lifetime_resources;test_lifetime_nodes;test_resource_profile;
    test_profile_lifetime_boundary;test_frame_node_boundaries;test_retention_no_refund;
    test_wrong_hello_and_unsolicited;test_output_budget_event;test_mutated_input_body_binding];
  print_endline "pipeline callback channel framing, nested continuations and lifetime limits: PASS"
