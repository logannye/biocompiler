open Bioc_wire
module W = Bioc_checker.Work_budget
module C = Bioc_domain.Verification_exploration.Codec
let protocol = "biocompiler.pipeline_callback_channel.v1"
let profile = "biocompiler.core.pipeline_callback_channel.v1"
let declaration = Json.parse {|{"application":"caller_supplied_exact_declaration;channel_has_no_manager_or_acceptance_authority","client_fields":{"close":["protocol","profile","session_id","kind","sequence","parent_invocation"],"command":["protocol","profile","session_id","kind","sequence","parent_invocation","operation","arguments"],"continue":["protocol","profile","session_id","kind","sequence","invocation_id","invocation_sha256","outcome"],"hello":["protocol","profile","session_id","kind","sequence","declaration","application","limits"]},"close":"top_level_only;successful_null_reply_with_closed_true;no_resume","continuation_binding":"only_exact_current_top_invocation_id_and_body_sha256_may_complete","continuation_outcomes":{"raise":["status","token"],"return":["status","value"]},"event_sequence":"zero_then_exact_successor_across_replies_invocations_and_fatal","exception":"opaque_bounded_host_token_preserved;only_explicit_rejected_reply_or_Host_exception_keeps_application_live","fatal":"pipeline_callback_fatal;closed_latched;nullable_last_validated_request_binding;no_retry_or_fatal_write_after_uncertain_write","fixed_limits":{"frame_header_bytes":9,"max_action_bytes":128,"max_json_depth":128,"max_json_number_characters":4300,"max_json_string_bytes":4194304,"max_token_bytes":128,"terminal_bytes":8192,"terminal_work":1000000},"framing":"8_lowercase_hex_utf8_body_bytes_then_LF_then_exact_body","hello":"exact_complete_transport_and_application_declarations;null_or_complete_positive_integer_limit_reductions;already_consumed_prefix_counts","hello_result_fields":["declaration","application","limits"],"host_execution":"arbitrary_host_callback_cpu_and_memory_outside_native_bound;application_must_charge_its_native_work_and_retention_to_channel","invocation_identity":"event_id_and_sha256_exact_invocation_body_without_frame_header","limits":{"max_commands":10000,"max_frame_bytes":33554432,"max_frames":1000000,"max_json_nodes":1000000,"max_pending_invocations":128,"max_retained_bytes":134217728,"max_total_bytes":268435456,"max_work":1000000000000},"parent_binding":"command_parent_is_current_top_invocation_or_null_at_top_level;invocation_parent_is_enclosing_invocation","profile":"biocompiler.core.pipeline_callback_channel.v1","protocol":"biocompiler.pipeline_callback_channel.v1","reply_outcomes":{"ok":["status","value"],"raise":["status","token"],"rejected":["status","value"]},"request_identity":"sha256_exact_utf8_body_without_frame_header","retention":"cumulative_canonical_application_declaration_and_received_body_bytes_plus_callback_arguments_and_explicit_application_reservations;no_refund","schema_version":"biocompiler.pipeline_callback_channel_declaration.v1","sequence":"hello_zero_then_exact_successor_across_commands_continuations_and_close","server_fields":{"fatal":["protocol","profile","session_id","kind","event_id","sequence","request_sha256","code","closed","usage"],"invoke":["protocol","profile","session_id","kind","event_id","invocation_id","parent_invocation","command_sequence","command_sha256","action","arguments","usage"],"reply":["protocol","profile","session_id","kind","event_id","sequence","request_sha256","outcome","closed","usage"]},"session_identity":"client_canonical_lowercase_uuid_bound_to_one_channel_no_reconnect","terminal_reserve":"prepaid_1000000_work;normal_frames_leave_8192_bytes_and_one_frame;one_fatal_may_exceed_reduced_frame_and_node_ceilings_within_prepaid_byte_work_bound","usage":"conservative_reservations_before_io_or_allocation;partial_headers_and_bodies_remain_charged;json_nodes_counts_all_received_and_published_keys_and_values","usage_fields":["work_charged","work_remaining","input_bytes","output_bytes","frames","commands","json_nodes","pending_invocations","retained_bytes"]}|}
let terminal_bytes = 8192
let terminal_work = 1_000_000
let maximum_work = 1_000_000_000_000
let str value = Json.String value
let obj fields = Json.Object fields
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
let require condition message = Diagnostic.require condition "pipeline_callback_protocol" message
let limit condition = Diagnostic.require condition "pipeline_callback_limit" "Callback channel resource limit exhausted."
let number raw = Z.to_int (Json.integer raw)
let optional_int = function None -> Json.Null | Some value -> Json.int value
let optional_string = function None -> Json.Null | Some value -> str value

type limits = {max_frame_bytes:int;max_total_bytes:int;max_retained_bytes:int;
  max_work:int;max_json_nodes:int;max_pending_invocations:int;max_commands:int;max_frames:int}
let defaults = {max_frame_bytes=33_554_432;max_total_bytes=268_435_456;
  max_retained_bytes=134_217_728;max_work=maximum_work;max_json_nodes=1_000_000;
  max_pending_invocations=128;max_commands=10_000;max_frames=1_000_000}
let limits_json value = obj ["max_frame_bytes",Json.int value.max_frame_bytes;
  "max_total_bytes",Json.int value.max_total_bytes;"max_retained_bytes",Json.int value.max_retained_bytes;
  "max_work",Json.int value.max_work;"max_json_nodes",Json.int value.max_json_nodes;
  "max_pending_invocations",Json.int value.max_pending_invocations;
  "max_commands",Json.int value.max_commands;"max_frames",Json.int value.max_frames]
let reduced raw = match raw with Json.Null -> defaults | _ ->
  let maximum=Json.object_fields (limits_json defaults) in
  exact (List.map fst maximum) raw;
  List.iter (fun (key,bound) -> let value=Json.integer (get key raw) in
    require (Z.sign value>0 && Z.compare value (Json.integer bound)<=0)
      "Limits must be complete positive integer reductions.") maximum;
  let n key=number (get key raw) in
  {max_frame_bytes=n "max_frame_bytes";max_total_bytes=n "max_total_bytes";
   max_retained_bytes=n "max_retained_bytes";max_work=n "max_work";
   max_json_nodes=n "max_json_nodes";max_pending_invocations=n "max_pending_invocations";
   max_commands=n "max_commands";max_frames=n "max_frames"}

type io = {read_header:unit -> string option;read_body:int -> string;write:string -> unit}
type command = {sequence:int;operation:string;arguments:Json.t;body_sha256:string;parent_invocation:int option}
type reply = Success of Json.t | Rejected of Json.t
exception Host_exception of string
exception Closed
type binding = {request_sequence:int;request_sha256:string}
type invocation = {id:int;mutable sha256:string}
type t = {io:io;application:Json.t;application_bytes:string;
  dispatch:t -> command -> reply;root:W.t;mutable work:W.t;mutable limits:limits;
  mutable session_id:string option;mutable next_sequence:int;mutable next_event:int;
  mutable negotiated:bool;mutable running:bool;mutable closed:bool;
  mutable write_uncertain:bool;mutable terminal_sent:bool;
  mutable current:binding option;mutable active:command list;mutable pending:invocation list;
  mutable input_bytes:int;mutable output_bytes:int;mutable frames:int;mutable commands:int;
  mutable json_nodes:int;mutable retained_bytes:int;mutable largest_input:int}
let is_closed state = state.closed
let ensure_open state =
  if state.closed || W.exhausted state.root then (state.closed<-true;raise Closed)
let budget state = ensure_open state;state.work
let multiply state amount factor =
  if amount>W.remaining state.work/factor then W.charge state.work (W.remaining state.work+1);
  W.charge state.work (amount*factor)
let retain_bytes state amount =
  ensure_open state;
  try
    W.charge state.work 1;
    limit (amount>=0 && amount<=state.limits.max_retained_bytes-state.retained_bytes);
    state.retained_bytes<-state.retained_bytes+amount
  with _ -> state.closed<-true;raise Closed
let codec state ~max_nodes =
  limit (max_nodes>0);
  C.make_limits ~max_bytes:state.limits.max_frame_bytes ~max_nodes ~charge:(W.charge state.work) ()
let usage_with_output ?(extra_frames=0) ?(extra_nodes=0) state output = obj [
  "work_charged",Json.int (state.limits.max_work-W.remaining state.work);
  "work_remaining",Json.int (W.remaining state.work);"input_bytes",Json.int state.input_bytes;
  "output_bytes",Json.int output;"frames",Json.int (state.frames+extra_frames);"commands",Json.int state.commands;
  "json_nodes",Json.int (state.json_nodes+extra_nodes);"pending_invocations",Json.int (List.length state.pending);
  "retained_bytes",Json.int state.retained_bytes]
let usage state = usage_with_output state state.output_bytes
let create ~io ~application ~dispatch () =
  let root=W.create ~profile ~error_code:"pipeline_callback_work" ~maximum:maximum_work () in
  W.charge root terminal_work;
  let application_bytes=C.encode ~limits:(C.make_limits ~max_bytes:defaults.max_frame_bytes
    ~max_nodes:defaults.max_json_nodes ~charge:(W.charge root) ()) application in
  let retained=String.length application_bytes in
  limit (retained<=defaults.max_retained_bytes);
  {io;application;application_bytes;dispatch;root;work=root;limits=defaults;session_id=None;
   next_sequence=0;next_event=0;negotiated=false;running=false;closed=false;
   write_uncertain=false;terminal_sent=false;current=None;active=[];pending=[];
   input_bytes=0;output_bytes=0;frames=0;commands=0;json_nodes=0;retained_bytes=retained;largest_input=0}
let common state kind event = ["protocol",str protocol;"profile",str profile;
  "session_id",optional_string state.session_id;"kind",str kind;"event_id",Json.int event]
let framed body = Printf.sprintf "%08x\n%s" (String.length body) body
let write state body =
  (* Once a write starts, any exception may mean a prefix was published. Latch
     closure immediately and never append a second frame to uncertain bytes. *)
  try state.io.write (framed body)
  with _ -> state.write_uncertain<-true;state.closed<-true;raise Closed
let settle state maximum make =
  let rec loop count guess =
    require (count<16) "Output byte accounting failed to converge.";
    let body=Canonical.encode_bounded ~max_bytes:maximum (make guess) in
    let actual=state.output_bytes+9+String.length body in
    if actual=guess then body else loop (count+1) actual in
  loop 0 (state.output_bytes+9+maximum)
let publication state kind fields =
  ensure_open state;
  limit (state.frames<state.limits.max_frames-1);
  let event=state.next_event in
  let fields=common state kind event @ fields in
  (* Preflight the complete tree, with maximum-width counters, before any
     unmetered encoder traversal. Sixteen fixed-point rewrites, SHA and framing
     copies are all prepaid by a conservative successful traversal bound. *)
  let largest_usage=obj ["work_charged",Json.int maximum_work;"work_remaining",Json.int maximum_work;
    "input_bytes",Json.int defaults.max_total_bytes;"output_bytes",Json.int defaults.max_total_bytes;
    "frames",Json.int defaults.max_frames;"commands",Json.int defaults.max_commands;
    "json_nodes",Json.int defaults.max_json_nodes;"pending_invocations",Json.int defaults.max_pending_invocations;
    "retained_bytes",Json.int defaults.max_retained_bytes] in
  let size=C.measure ~limits:(codec state ~max_nodes:(state.limits.max_json_nodes-state.json_nodes))
    (obj (fields @ ["usage",largest_usage])) in
  let bound=(C.work_bounds size).encode in
  multiply state bound 18;
  let body=settle state state.limits.max_frame_bytes (fun output ->
    obj (fields @ ["usage",usage_with_output ~extra_frames:1 ~extra_nodes:size.nodes state output])) in
  limit (String.length body+9<=state.limits.max_total_bytes-terminal_bytes-state.input_bytes-state.output_bytes);
  state.json_nodes<-state.json_nodes+size.nodes;
  state.frames<-state.frames+1;state.next_event<-event+1;
  state.output_bytes<-state.output_bytes+String.length body+9;
  write state body;
  event,body
let terminate state =
  state.closed<-true;
  if not state.terminal_sent && not state.write_uncertain then (
    state.terminal_sent<-true;
    let sequence=Option.map (fun value -> value.request_sequence) state.current in
    let hash=Option.map (fun value -> value.request_sha256) state.current in
    let fields=common state "fatal" state.next_event @ [
      "sequence",optional_int sequence;"request_sha256",optional_string hash;
      "code",str "pipeline_callback_fatal";"closed",Json.Bool true] in
    (* Fixed fields and bounded identities only; no application data, exception
       message or untrusted tree is serialized on this prepaid terminal path. *)
    let nodes=(C.measure ~limits:(C.make_limits ~max_bytes:terminal_bytes ~max_nodes:2048 ())
      (obj (fields @ ["usage",usage state]))).nodes in
    state.json_nodes<-state.json_nodes+nodes;state.frames<-state.frames+1;
    state.next_event<-state.next_event+1;
    (try let body=settle state (terminal_bytes-9) (fun output ->
       obj (fields @ ["usage",usage_with_output state output])) in
       state.output_bytes<-state.output_bytes+String.length body+9;
       write state body with _ -> ()))
let frame_length header =
  require (String.length header=9 && header.[8]='\n') "Incomplete or invalid frame header.";
  let length=ref 0 in
  for index=0 to 7 do
    let digit=match header.[index] with
      | '0'..'9' as value -> Char.code value-Char.code '0'
      | 'a'..'f' as value -> Char.code value-Char.code 'a'+10
      | _ -> Diagnostic.fail "pipeline_callback_frame" "Frame length requires lowercase hexadecimal." in
    length:=16* !length+digit
  done;!length
let reserve_input state amount =
  limit (amount<=state.limits.max_total_bytes-terminal_bytes-state.input_bytes-state.output_bytes);
  multiply state amount 8;
  state.input_bytes<-state.input_bytes+amount
let uuid value =
  String.length value=36 &&
  let valid=ref true in
  String.iteri (fun index character ->
    let separator=List.mem index [8;13;18;23] in
    if (separator && character<>'-') || (not separator &&
      not ((character>='0' && character<='9') || (character>='a' && character<='f')))
    then valid:=false) value;
  !valid
let read state =
  ensure_open state;state.current<-None;
  limit (state.frames<state.limits.max_frames-1);
  reserve_input state 9;state.frames<-state.frames+1;
  let header=match state.io.read_header () with Some value -> value
    | None -> Diagnostic.fail "pipeline_callback_frame" "Unexpected end of channel." in
  let length=frame_length header in
  limit (length>0 && length<=state.limits.max_frame_bytes);
  reserve_input state length;
  (* Count complete incoming bodies conservatively before reading them, even
     when the decoded command/completion is subsequently released or rejected. *)
  retain_bytes state length;
  state.largest_input<-max state.largest_input length;
  let body=state.io.read_body length in
  require (String.length body=length) "Incomplete frame body.";
  let raw=Json.parse_artifact ~max_bytes:state.limits.max_frame_bytes
    ~max_nodes:(max 1 (state.limits.max_json_nodes-state.json_nodes))
    ~on_node:(fun () -> limit (state.json_nodes<state.limits.max_json_nodes);
      W.charge state.work 256;state.json_nodes<-state.json_nodes+1) body in
  require (text "protocol" raw=protocol && text "profile" raw=profile) "Channel protocol or profile changed.";
  let identity=text "session_id" raw in
  require (uuid identity) "Channel identity must be a canonical lowercase UUID.";
  (match state.session_id with None -> state.session_id<-Some identity
   | Some expected -> require (identity=expected) "Channel identity changed.");
  let seq=Json.integer (get "sequence" raw) in
  require (Z.equal seq (Z.of_int state.next_sequence)) "Client sequence must be the exact successor.";
  state.next_sequence<-state.next_sequence+1;
  let binding={request_sequence=Z.to_int seq;request_sha256=Canonical.sha256 body} in
  state.current<-Some binding;
  raw,binding
let base_fields = ["protocol";"profile";"session_id";"kind";"sequence"]
let count_command state = limit (state.commands<state.limits.max_commands);state.commands<-state.commands+1
let top state = match state.pending with [] -> None | value::_ -> Some value.id
let parent state raw =
  let value=get "parent_invocation" raw in
  require (value=optional_int (top state)) "Command parent does not match the active invocation.";
  top state
let bounded_text maximum raw =
  let value=Json.string raw in
  require (String.length value>0 && String.length value<=maximum) "Channel name or token exceeds its bound.";
  value
let reply state binding ~closed outcome =
  ignore (publication state "reply" ["sequence",Json.int binding.request_sequence;
    "request_sha256",str binding.request_sha256;"outcome",outcome;"closed",Json.Bool closed]);
  if closed then state.closed<-true
let success raw = obj ["status",str "ok";"value",raw]
let hello state raw binding =
  exact (base_fields @ ["declaration";"application";"limits"]) raw;
  require (text "kind" raw="hello" && binding.request_sequence=0 && not state.negotiated)
    "Exactly one initial hello is required.";
  let encoded value=C.encode ~limits:(codec state ~max_nodes:state.limits.max_json_nodes) value in
  require (encoded (get "declaration" raw)=encoded declaration) "Complete transport declaration differs.";
  require (encoded (get "application" raw)=state.application_bytes) "Complete application declaration differs.";
  let controls=reduced (get "limits" raw) in
  let spent=maximum_work-W.remaining state.root in
  limit (spent<controls.max_work && state.largest_input<=controls.max_frame_bytes &&
    state.input_bytes+state.output_bytes+terminal_bytes<=controls.max_total_bytes &&
    state.retained_bytes<=controls.max_retained_bytes && state.json_nodes<controls.max_json_nodes &&
    state.frames<controls.max_frames-1 && state.commands<=controls.max_commands);
  state.work<-W.nested ~parent:state.root ~profile ~error_code:"pipeline_callback_work"
    ~maximum:(controls.max_work-spent) ();
  state.limits<-controls;state.negotiated<-true;
  reply state binding ~closed:false (success (obj ["declaration",declaration;
    "application",state.application;"limits",limits_json controls]))
let dispatch_command state raw binding =
  exact (base_fields @ ["parent_invocation";"operation";"arguments"]) raw;
  require (text "kind" raw="command") "Expected a command.";
  count_command state;
  let parent_invocation=parent state raw in
  let command={sequence=binding.request_sequence;body_sha256=binding.request_sha256;
    operation=bounded_text 128 (get "operation" raw);arguments=get "arguments" raw;parent_invocation} in
  let previous=state.active in
  state.active<-command::previous;
  let outcome=Fun.protect ~finally:(fun () -> state.active<-previous) (fun () ->
    try match state.dispatch state command with
      | Success value -> success value
      | Rejected value -> obj ["status",str "rejected";"value",value]
    with Host_exception token ->
      ensure_open state;
      let token=bounded_text 128 (str token) in
      obj ["status",str "raise";"token",str token]) in
  ensure_open state;reply state binding ~closed:false outcome
let close_command state raw binding =
  exact (base_fields @ ["parent_invocation"]) raw;
  require (state.pending=[] && get "parent_invocation" raw=Json.Null) "Close is permitted only at top level.";
  count_command state;reply state binding ~closed:true (success Json.Null)
let invoke state ~action ~arguments =
  ensure_open state;
  let previous=state.pending in
  try
    require (state.negotiated && state.running) "Invocation requires a live negotiated dispatcher.";
    let command=match state.active with value::_ -> value
      | [] -> Diagnostic.fail "pipeline_callback_state" "Invocation has no active command." in
    let action=bounded_text 128 (str action) in
    limit (List.length previous<state.limits.max_pending_invocations);
    let size=C.measure ~limits:(codec state ~max_nodes:state.limits.max_json_nodes) arguments in
    retain_bytes state size.bytes;
    let invocation={id=state.next_event;sha256=""} in
    state.pending<-invocation::previous;
    let _,body=publication state "invoke" ["invocation_id",Json.int invocation.id;
      "parent_invocation",optional_int (match previous with [] -> None | value::_ -> Some value.id);
      "command_sequence",Json.int command.sequence;"command_sha256",str command.body_sha256;
      "action",str action;"arguments",arguments] in
    invocation.sha256<-Canonical.sha256 body;
    let rec wait () =
      ensure_open state;
      let raw,binding=read state in
      match text "kind" raw with
      | "command" -> dispatch_command state raw binding;wait ()
      | "continue" ->
          exact (base_fields @ ["invocation_id";"invocation_sha256";"outcome"]) raw;
          require (get "invocation_id" raw=Json.int invocation.id &&
            get "invocation_sha256" raw=str invocation.sha256 &&
            (match state.pending with value::_ -> value==invocation | [] -> false))
            "Continuation is stale or does not bind the exact active invocation.";
          let outcome=get "outcome" raw in
          (match text "status" outcome with
           | "return" -> exact ["status";"value"] outcome;get "value" outcome
           | "raise" -> exact ["status";"token"] outcome;
               raise (Host_exception (bounded_text 128 (get "token" outcome)))
           | _ -> Diagnostic.fail "pipeline_callback_protocol" "Unknown continuation outcome.")
      | _ -> Diagnostic.fail "pipeline_callback_protocol" "Only nested commands or the active continuation are permitted." in
    let value=wait () in
    state.pending<-previous;ensure_open state;value
  with
  | Host_exception _ as error -> state.pending<-previous;ensure_open state;raise error
  | Closed -> terminate state;state.pending<-previous;raise Closed
  | _ -> terminate state;state.pending<-previous;raise Closed
let run state =
  ensure_open state;
  if state.running then (terminate state;raise Closed);
  state.running<-true;
  Fun.protect ~finally:(fun () -> state.running<-false;state.active<-[];state.pending<-[]) (fun () ->
    try
      let raw,binding=read state in
      count_command state;hello state raw binding;
      while not state.closed do
        let raw,binding=read state in
        match text "kind" raw with
        | "command" -> dispatch_command state raw binding
        | "close" -> close_command state raw binding
        | _ -> Diagnostic.fail "pipeline_callback_protocol" "Expected a top-level command or close."
      done
    with Closed -> terminate state | _ -> terminate state)
