open Bioc_wire
open Bioc_domain
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module C = Pipeline_contract
module S = Bioc_pipeline.Synthetic_pipeline
module P = Bioc_pipeline.Component_pipeline
module G = Bioc_synthetic_producer.Generator
let profile = "biocompiler.core.pipeline_session.v1"
let protocol = "biocompiler.pipeline_session.v1"
let maximum_frame_bytes = 33_554_432
let declaration = Json.parse {declaration|{"argument":"--pipeline-session-v1","artifacts":{"components":["candidate","pipeline_result","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","pipeline_result","selection_result"]},"budget":"one_lifetime_ancestor_including_hello_prefix_parse_import_execution_and_publication_no_per_command_reset","callback_scope":"native_fixed_providers_only_no_wire_callbacks_registration_decisions_or_accepted_record_import","claim_scope":"live_native_manager_scoped_acceptance_under_supplied_software_contracts_no_empirical_or_human_use_acceptance","dependencies_encoding":"ordered_unique_string_identity_pairs","exception_fields":["module","type","message","attributes"],"executable":"core","failure":"expected_logical_errors_keep_actual_partial_manager; framing_identity_budget_or_internal_errors_close","fixed_limits":{"max_depth":128,"max_number_chars":4300,"max_string_bytes":4194304,"terminal_reserve_bytes":8192,"terminal_reserve_work":1000000},"framing":"eight_lowercase_hex_body_bytes_then_lf_then_exact_utf8_json","hello_fields":["profile","limits","manager_limits"],"initialization_fields":["kind","manager","artifacts"],"limits":{"max_commands":10000,"max_frame_bytes":33554432,"max_json_nodes":1000000,"max_retained_bytes":134217728,"max_total_bytes":268435456,"max_work":1000000000000},"limits_encoding":"null_defaults_or_exact_all_positive_integer_reductions","manager_limits":{"max_ancestor_depth":128,"max_call_depth":128,"max_document_bytes":16777216,"max_document_nodes":250000,"max_providers":10000,"max_records":10000,"max_retained_bytes":67108864,"max_retained_items":1000000},"operations":{"add-build-request":{"fields":["identity","requirements","obligations","request"],"result":"complete_stage_record"},"add-input":{"fields":["identity","stage","requirements","obligations","document"],"result":"complete_stage_record"},"artifact":{"fields":["name"],"result":"complete_immutable_build_artifact"},"close":{"fields":[],"result":"null"},"get":{"fields":["identity"],"result":"fresh_complete_stage_record"},"hello":{"fields":["profile","limits","manager_limits"],"result":"exact_profile_and_effective_limits"},"initialize-components":{"fields":["request","history","until","config"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles"],"result":"initialization"},"initialize-synthetic":{"fields":["request","history","until","config"],"result":"initialization"},"inspect":{"fields":[],"result":"complete_historical_manager_snapshot_with_process_local_provider_labels"},"register-completion-profile":{"fields":["profile"],"result":"null"},"result":{"fields":["identity","scope"],"result":"fresh_complete_pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"fresh_complete_stage_record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"complete_target"}},"profile":"biocompiler.core.pipeline_session.v1","protocol":"biocompiler.pipeline_session.v1","request_fields":["protocol","session_id","sequence","operation","payload"],"request_identity":"sha256_exact_utf8_body_without_frame_header","response_fields":["protocol","profile","session_id","sequence","operation","request_sha256","status","result","diagnostics","exception","closed","usage","core"],"retention":"conservative_cumulative_service_authorities_and_build_artifacts_separate_from_manager_limits_no_refund","schema_version":"biocompiler.pipeline_session_declaration.v1","sequence":"hello_zero_then_exact_successor_including_logical_errors","session_identity":"client_canonical_lowercase_uuid_bound_to_one_process_no_reconnect","terminal_reserve":"prepaid_work_and_byte_capacity_counted_before_reduced_limits; fatal_reply_may_exceed_reduced_frame_ceiling_up_to8192","usage_fields":["work_charged","work_remaining","input_bytes","output_bytes","commands","retained_bytes"]}|declaration}
let maximum_work = 1_000_000_000_000
let terminal_bytes = 8192
let terminal_work = 1_000_000
let str value = Json.String value
let obj fields = Json.Object fields
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let fields keys raw = let result=Json.object_fields raw in Json.exact_fields keys result;result
let fail code message = Diagnostic.fail code message
let require condition code message = Diagnostic.require condition code message
let number raw = Z.to_int (Json.integer raw)
type controls = {max_frame_bytes:int;max_total_bytes:int;max_commands:int;
  max_retained_bytes:int;max_json_nodes:int;max_work:int}
let defaults = {max_frame_bytes=maximum_frame_bytes;max_total_bytes=268_435_456;
  max_commands=10_000;max_retained_bytes=134_217_728;max_json_nodes=1_000_000;max_work=maximum_work}
let controls_json value = obj ["max_frame_bytes",Json.int value.max_frame_bytes;
  "max_total_bytes",Json.int value.max_total_bytes;"max_commands",Json.int value.max_commands;
  "max_retained_bytes",Json.int value.max_retained_bytes;"max_json_nodes",Json.int value.max_json_nodes;
  "max_work",Json.int value.max_work]
let reductions defaults raw =
  if raw=Json.Null then defaults else (
    let expected=Json.object_fields defaults in
    let supplied=fields (List.map fst expected) raw in
    List.iter (fun (key,maximum) ->
      let value=Json.integer (Json.field key supplied) in
      require (Z.sign value>0 && Z.compare value (Json.integer maximum)<=0)
        "pipeline_session_limits" "Session limits must be complete positive integer reductions.") expected;
    raw)
let controls raw = let n key=number (get key raw) in
  {max_frame_bytes=n "max_frame_bytes";max_total_bytes=n "max_total_bytes";
   max_commands=n "max_commands";max_retained_bytes=n "max_retained_bytes";
   max_json_nodes=n "max_json_nodes";max_work=n "max_work"}
type request = {sequence:int;operation:string;sha256:string}
type response = {bytes:string;closed:bool}
type t = {root:W.t;mutable work:W.t;mutable limits:controls;mutable manager_limits:M.limits;
  mutable manager_json:Json.t;mutable session_id:string option;mutable sequence:int;
  mutable pending:int option;mutable current:request option;mutable input_bytes:int;
  mutable output_bytes:int;mutable commands:int;mutable retained_bytes:int;
  mutable negotiated:bool;mutable initialized:bool;mutable closed:bool;
  mutable manager:M.t option;mutable artifacts:(string*Json.t) list;
  mutable providers:(M.provider*string) list;mutable terminal_sent:bool}
let is_closed (state:t) = state.closed
let codec state = C.Codec.make_limits ~max_bytes:state.limits.max_frame_bytes
    ~max_nodes:state.limits.max_json_nodes ~charge:(W.charge state.work) ()
let manager_codec state = C.Codec.make_limits
    ~max_bytes:(number (get "max_document_bytes" state.manager_json))
    ~max_nodes:(number (get "max_document_nodes" state.manager_json)) ~charge:(W.charge state.work) ()
let create () =
  let work=W.create ~profile ~error_code:"pipeline_session_work" ~maximum:maximum_work () in
  W.charge work terminal_work;
  let manager_json=obj (List.filter (fun (key,_) -> not (List.mem key ["profile";"work";"retention"]))
      (Json.object_fields (M.limits_json M.default_limits))) in
  {root=work;work;limits=defaults;manager_limits=M.default_limits;manager_json;session_id=None;
   sequence=0;pending=None;current=None;input_bytes=0;output_bytes=0;commands=0;retained_bytes=0;
   negotiated=false;initialized=false;closed=false;manager=None;artifacts=[];providers=[];terminal_sent=false}
let charge_product state value multiple =
  if value>W.remaining state.work/multiple then W.charge state.work (W.remaining state.work+1);
  W.charge state.work (value*multiple)
let reserve_frame state length =
  state.current<-None;
  require (not state.closed && state.pending=None) "pipeline_session_frame" "Session is closed or already reading a frame.";
  require (length>0 && length<=state.limits.max_frame_bytes) "pipeline_session_frame" "Session frame exceeds its byte limit.";
  require (state.commands<state.limits.max_commands) "pipeline_session_limit" "Session command limit exhausted.";
  require (length+9<=state.limits.max_total_bytes-terminal_bytes-state.input_bytes-state.output_bytes)
    "pipeline_session_limit" "Session aggregate byte limit exhausted.";
  (* Reserve bounded read, raw SHA-256 and lexical work before body allocation.
     Parser nodes are additionally charged before their individual allocation. *)
  charge_product state (length+9) 8;
  state.input_bytes<-state.input_bytes+length+9;state.commands<-state.commands+1;
  state.pending<-Some length
let retain_bytes state bytes =
  W.charge state.work 1;
  require (bytes>=0 && bytes<=state.limits.max_retained_bytes-state.retained_bytes)
    "pipeline_session_limit" "Session retained authority and build artifacts exceed their byte limit.";
  state.retained_bytes<-state.retained_bytes+bytes
let retain state raw =
  let size=C.Codec.measure ~limits:(codec state) raw in
  retain_bytes state size.bytes
let reserve_fixed_closures state ~components request config until =
  (* Native fixed providers capture more than their supplied request/history:
     generation retains the complete selected alternative report and catalog;
     component generation retains the full adapted registry/composition/check.
     Reserve the actual producer publication ceilings before either producer
     can install closures, including its logical failure path. These ceilings
     already bound complete canonical JSON (ASCII is at least as large as UTF-8),
     not merely successful candidate fragments. No reservation is refunded.
     Shared typed roots supplied above are counted separately, and successful
     artifact JSON copies are counted again when materialized. *)
  let catalog_bytes=max
    (Synthetic_authority.Catalog.canonical_size Synthetic_authority.combinational_catalog)
    (Synthetic_authority.Catalog.canonical_size Synthetic_authority.temporal_catalog) in
  retain_bytes state catalog_bytes;
  (match config with None -> retain state (Synthetic_authority.Config.to_json (Synthetic_authority.Config.make ()))
   | Some _ -> ());
  Option.iter (fun value -> retain state (Runtime_number.to_json value)) until;
  let build=Realization_request.build_request request in
  if Build_request.implementation_constraints build<>[] || Build_request.preferences build<>[] then
    retain_bytes state (number (get "max_report_bytes" (get "shared"
      (Bioc_synthetic_producer.Selection.limits_json Bioc_synthetic_producer.Selection.default_limits))));
  if components then
    retain_bytes state (number (get "max_report_bytes" (get "shared"
      (Bioc_synthetic_producer.Components.limits_json Bioc_synthetic_producer.Components.default_limits))))
let imported state decoder raw =
  let charged=ref 0 in
  let limits=C.Codec.make_limits
    ~max_bytes:(number (get "max_document_bytes" state.manager_json))
    ~max_nodes:(number (get "max_document_nodes" state.manager_json))
    ~charge:(fun amount -> W.charge state.work amount;charged:= !charged+amount) () in
  ignore (C.Codec.encode ~limits raw);charge_product state !charged 127;decoder raw
let usage state output_bytes = obj ["work_charged",Json.int (state.limits.max_work-W.remaining state.work);
  "work_remaining",Json.int (W.remaining state.work);"input_bytes",Json.int state.input_bytes;
  "output_bytes",Json.int output_bytes;"commands",Json.int state.commands;
  "retained_bytes",Json.int state.retained_bytes]
let diagnostic_json (value:Diagnostic.t) = obj ["code",str value.code;"message",str value.message;
  "path",Option.fold ~none:Json.Null ~some:str value.path]
let envelope state ~status ~result ~diagnostics ~exception_value ~usage =
  let request=state.current in
  obj ["protocol",str protocol;"profile",str profile;
    "session_id",Option.fold ~none:Json.Null ~some:str state.session_id;
    "sequence",Option.fold ~none:Json.Null ~some:(fun (value:request) -> Json.int value.sequence) request;
    "operation",Option.fold ~none:Json.Null ~some:(fun value -> str value.operation) request;
    "request_sha256",Option.fold ~none:Json.Null ~some:(fun value -> str value.sha256) request;
    "status",str status;"result",result;"diagnostics",Json.Array (List.map diagnostic_json diagnostics);
    "exception",exception_value;"closed",Json.Bool state.closed;"usage",usage;
    "core",Protocol.identity Protocol.Core]
let final_bytes state ~maximum make =
  (* Only the decimal output counter depends on its own encoded length. Starting
     from its upper bound converges monotonically in at most ten digit changes. *)
  let rec settle count guess =
    require (count<16) "pipeline_session_internal" "Session output counter did not converge.";
    let bytes=Canonical.encode_bounded ~max_bytes:maximum (make guess) in
    let actual=state.output_bytes+String.length bytes+9 in
    if actual=guess then bytes else settle (count+1) actual in
  settle 0 (state.output_bytes+maximum+9)
let release state = state.manager<-None;state.artifacts<-[];state.providers<-[];state.pending<-None
let abort ?(unbound=false) state =
  if unbound then state.current<-None;
  state.closed<-true;release state;
  require (not state.terminal_sent) "pipeline_session_closed" "Terminal response already published.";
  state.terminal_sent<-true;
  let diagnostics=[{Diagnostic.code="pipeline_session_fatal";
    message="Session closed after a framing, identity, resource or internal failure.";path=None}] in
  let bytes=final_bytes state ~maximum:terminal_bytes (fun output ->
    envelope state ~status:"error" ~result:Json.Null ~diagnostics ~exception_value:Json.Null
      ~usage:(usage state output)) in
  require (String.length bytes+9<=terminal_bytes) "pipeline_session_internal" "Terminal response exceeded its prepaid bound.";
  state.output_bytes<-state.output_bytes+String.length bytes+9;
  {bytes;closed=true}
let publish state ~status ~result ~diagnostics ~exception_value =
  (* Charge a conservative complete publication envelope using maximum-width
     counters before the final bounded encoding and its fixed-point rewrites. *)
  let largest_usage=obj ["work_charged",Json.int maximum_work;"work_remaining",Json.int maximum_work;
    "input_bytes",Json.int defaults.max_total_bytes;"output_bytes",Json.int defaults.max_total_bytes;
    "commands",Json.int defaults.max_commands;"retained_bytes",Json.int defaults.max_retained_bytes] in
  let largest=envelope state ~status ~result ~diagnostics ~exception_value ~usage:largest_usage in
  let charged=ref 0 in
  let limits=C.Codec.make_limits ~max_bytes:state.limits.max_frame_bytes ~max_nodes:state.limits.max_json_nodes
    ~charge:(fun amount -> W.charge state.work amount;charged:= !charged+amount) () in
  ignore (C.Codec.encode ~limits largest);charge_product state !charged 17;
  let bytes=final_bytes state ~maximum:state.limits.max_frame_bytes (fun output ->
    envelope state ~status ~result ~diagnostics ~exception_value ~usage:(usage state output)) in
  require (String.length bytes+9<=state.limits.max_total_bytes-terminal_bytes-state.input_bytes-state.output_bytes)
    "pipeline_session_limit" "Session aggregate byte limit exhausted during publication.";
  state.output_bytes<-state.output_bytes+String.length bytes+9;
  if state.closed then release state;
  {bytes;closed=state.closed}
let uuid value =
  String.length value=36 && String.for_all (fun c ->
    (c>='0' && c<='9') || (c>='a' && c<='f') || c='-') value &&
  List.for_all (fun index -> value.[index]='-') [8;13;18;23] &&
  let valid=ref true in String.iteri (fun index c ->
    if c='-' && not (List.mem index [8;13;18;23]) then valid:=false) value;!valid
let decode state raw =
  let parsed_nodes=ref 0 in
  let raw_value=Json.parse_artifact ~max_bytes:state.limits.max_frame_bytes ~max_nodes:state.limits.max_json_nodes
    ~on_node:(fun () -> W.charge state.work 256;incr parsed_nodes) raw in
  let f=fields ["protocol";"session_id";"sequence";"operation";"payload"] raw_value in
  let value key=Json.field key f in
  require (Json.string (value "protocol")=protocol) "pipeline_session_protocol" "Unsupported session protocol.";
  let session_id=Json.string (value "session_id") in
  require (uuid session_id) "pipeline_session_identity" "Session identity must be a canonical lowercase UUID.";
  let sequence=Json.integer (value "sequence") in
  require (Z.sign sequence>=0 && Z.compare sequence (Z.of_int defaults.max_commands)<=0)
    "pipeline_session_identity" "Session sequence is outside its bounded range.";
  let operation=Json.name (value "operation") in
  require (String.length operation<=128) "pipeline_session_protocol" "Session operation name is too long.";
  let request={sequence=Z.to_int sequence;operation;sha256=Canonical.sha256 raw} in
  state.current<-Some request;
  (match state.session_id with
   | None -> state.session_id<-Some session_id
   | Some expected -> require (session_id=expected) "pipeline_session_identity" "Session identity changed.");
  require (request.sequence=state.sequence) "pipeline_session_identity" "Session sequence must be the exact successor.";
  require ((not state.negotiated && request.operation="hello") || (state.negotiated && request.operation<>"hello"))
    "pipeline_session_protocol" "A session requires exactly one initial hello.";
  state.sequence<-state.sequence+1;
  request,value "payload",!parsed_nodes
let hello state payload nodes input_length =
  ignore (fields ["profile";"limits";"manager_limits"] payload);
  require (text "profile" payload=profile) "pipeline_session_protocol" "Unsupported session profile.";
  let limits=controls (reductions (controls_json defaults) (get "limits" payload)) in
  let manager_json=reductions state.manager_json (get "manager_limits" payload) in
  let n key=number (get key manager_json) in
  let manager_limits=M.make_limits ~max_records:(n "max_records") ~max_providers:(n "max_providers")
    ~max_retained_items:(n "max_retained_items") ~max_retained_bytes:(n "max_retained_bytes")
    ~max_call_depth:(n "max_call_depth") ~max_ancestor_depth:(n "max_ancestor_depth")
    ~max_document_bytes:(n "max_document_bytes") ~max_document_nodes:(n "max_document_nodes") () in
  let spent=maximum_work-W.remaining state.root in
  require (spent<limits.max_work && input_length<=limits.max_frame_bytes && nodes<=limits.max_json_nodes &&
    state.input_bytes+terminal_bytes<=limits.max_total_bytes && state.commands<=limits.max_commands)
    "pipeline_session_limits" "Reduced session limits cannot cover the already consumed hello.";
  state.work<-W.nested ~parent:state.root ~profile ~error_code:"pipeline_session_work" ~maximum:(limits.max_work-spent) ();
  state.limits<-limits;state.manager_json<-manager_json;state.manager_limits<-manager_limits;state.negotiated<-true;
  retain state (str (Option.get state.session_id));
  obj ["profile",declaration;"limits",controls_json limits;"manager_limits",manager_json]
let manager state = match state.manager with Some value -> value
  | None -> fail "pipeline_session_state" "This session has no live manager."
let initialize state kind payload =
  require (not state.initialized) "pipeline_session_state" "This session has already attempted initialization.";
  state.initialized<-true;retain state payload;
  let artifact name raw = retain state raw;state.artifacts<-state.artifacts@[name,raw] in
  if kind="empty" then (
    ignore (fields ["target";"dependencies";"completion_profiles"] payload);
    let target=imported state (fun raw -> Build_request.Target.of_json raw) (get "target" payload) in
    let dependencies=List.map (function Json.Array [key;identity] -> Json.string key,Json.string identity
      | _ -> fail "pipeline_session_payload" "Dependencies must be ordered name/identity pairs.")
      (Json.array (get "dependencies" payload)) in
    let names=List.map fst dependencies in
    require (List.length names=List.length (List.sort_uniq String.compare names))
      "pipeline_session_payload" "Dependency names must be unique.";
    let completion_profiles=List.map (fun raw -> C.Completion_profile.of_json ~limits:(manager_codec state) raw)
      (Json.array (get "completion_profiles" payload)) in
    state.manager<-Some (M.create ~budget:state.work ~limits:state.manager_limits ~target ~dependencies ~completion_profiles ()))
  else (
    ignore (fields ["request";"history";"until";"config"] payload);
    let request=imported state (fun raw -> Realization_request.of_json raw) (get "request" payload) in
    let frames=List.map (fun raw -> imported state (fun raw -> Execution_data.Input_frame.of_json raw) raw)
      (Json.array (get "history" payload)) in
    let until=match get "until" payload with Json.Null -> None | raw -> Some (Runtime_number.of_json raw) in
    let config=match get "config" payload with Json.Null -> None
      | raw -> Some (imported state (fun raw -> Synthetic_authority.Config.of_json raw) raw) in
    (* Reserve complete typed roots captured by the fixed native closures, in
       addition to raw supplied authority. Manager records have their own cap. *)
    retain state (Realization_request.to_json request);
    List.iter (fun frame -> retain state (Execution_data.Input_frame.to_json frame)) frames;
    Option.iter (fun value -> retain state (Synthetic_authority.Config.to_json value)) config;
    reserve_fixed_closures state ~components:(kind="components") request config until;
    let selection = function None -> Json.Null | Some value -> Synthetic_selection.Result.to_json value in
    if kind="synthetic" then (
      match S.attempt ~budget:state.work ~manager_limits:state.manager_limits ?until ?config request frames with
      | S.Failed failure -> state.manager<-failure.manager;raise failure.error
      | S.Completed value ->
        state.manager<-Some (S.manager value);
        artifact "candidate" (Synthetic_authority.Candidate.to_json (S.candidate value));
        artifact "pipeline_result" (C.Pipeline_result.to_json (S.result value));
        artifact "selection_result" (selection (S.selection_result value)))
    else (
      match P.attempt ~budget:state.work ~manager_limits:state.manager_limits ?until ?config request frames with
      | P.Failed failure -> state.manager<-failure.manager;raise failure.error
      | P.Completed value ->
        state.manager<-Some (P.manager value);
        artifact "candidate" (Synthetic_authority.Candidate.to_json (P.candidate value));
        artifact "pipeline_result" (C.Pipeline_result.to_json (P.result value));
        artifact "selection_result" (selection (P.selection_result value));
        artifact "assembly" (Component_assembly.to_json (P.assembly value));
        artifact "link_result" (Composition_evidence.Result.to_json (P.link_result value));
        artifact "behavior_result" (Realization_evidence.Check_result.to_json (P.behavior_result value))));
  obj ["kind",str kind;"manager",Json.Bool true;"artifacts",Json.Array (List.map (fun (key,_) -> str key) state.artifacts)]
let dispatch state operation payload =
  let get key=get key payload and text key=text key payload in
  let exact keys=ignore (fields keys payload) in
  match operation with
  | "initialize-empty" -> initialize state "empty" payload
  | "initialize-synthetic" -> initialize state "synthetic" payload
  | "initialize-components" -> initialize state "components" payload
  | "close" -> exact [];state.closed<-true;Json.Null
  | "target" -> exact [];Build_request.Target.to_json (M.target (manager state))
  | "get" -> exact ["identity"];C.Stage_record.to_json (M.get (manager state) (text "identity"))
  | "result" -> exact ["identity";"scope"];
    C.Pipeline_result.to_json (M.result (manager state) ~identity:(text "identity") ~scope:(text "scope"))
  | "set-dependency" -> exact ["key";"identity"];
    M.set_dependency (manager state) (text "key") (text "identity");Json.Null
  | "run" -> exact ["pass_id";"input_id";"output_id";"configuration"];
    C.Stage_record.to_json (M.run (manager state) ~pass_id:(text "pass_id") ~input_id:(text "input_id")
      ~output_id:(text "output_id") ~configuration:(get "configuration") ())
  | "register-completion-profile" -> exact ["profile"];
    let live=manager state in
    let completion=C.Completion_profile.of_json ~limits:(manager_codec state) (get "profile") in
    M.register_completion_profile live completion;Json.Null
  | "add-input" | "add-build-request" ->
    let typed=operation="add-build-request" in
    exact (if typed then ["identity";"requirements";"obligations";"request"]
      else ["identity";"stage";"requirements";"obligations";"document"]);
    let live=manager state in
    let requirements=List.map Json.string (Json.array (get "requirements")) in
    let obligations=List.map (fun raw -> C.Scoped_obligation.of_json ~limits:(manager_codec state) raw)
      (Json.array (get "obligations")) in
    let record=if typed then
      let request=imported state (fun raw -> Build_request.of_json raw) (get "request") in
      M.add_build_request live ~identity:(text "identity") ~requirements ~obligations request
    else M.add_input live ~identity:(text "identity") ~stage:(C.stage_of_json (get "stage"))
      ~requirements ~obligations (get "document") in
    C.Stage_record.to_json record
  | "inspect" -> exact [];
    M.inspect (manager state) ~provider_identity:(fun value ->
      match List.find_opt (fun (other,_) -> W.charge state.work 1;other==value) state.providers with
      | Some (_,name) -> name
      | None ->
        require (List.length state.providers<number (Json.field "max_providers" (Json.object_fields state.manager_json)))
          "pipeline_session_limit" "Session provider label limit exhausted.";
        let name="provider/" ^ string_of_int (List.length state.providers) in
        retain state (str name);state.providers<-state.providers@[value,name];name)
  | "artifact" -> exact ["name"];
    (match List.assoc_opt (text "name") state.artifacts with Some value -> value
     | None -> fail "pipeline_session_state" "This session has no such completed build artifact.")
  | _ -> fail "pipeline_session_unsupported" "This operation is not available in the native session profile."
let exception_json owner kind message attributes =
  obj ["module",str owner;"type",str kind;"message",str message;"attributes",attributes]
let logical_error = function
  | Diagnostic.Error diagnostic ->
    let exception_value=match diagnostic.code with
      | "pipeline_error" -> exception_json "biocompiler.compiler.pipeline" "PipelineError" diagnostic.message (obj [])
      | "pipeline_serialization" | "pipeline_contract" -> exception_json "biocompiler.errors" "SerializationError" diagnostic.message (obj [])
      | _ -> Json.Null in
    (if diagnostic.code="pipeline_session_unsupported" then "unsupported" else "error"),[diagnostic],exception_value
  | M.No_candidate_found value ->
    let exception_value=exception_json "biocompiler.compiler.pipeline" "NoCandidateFound" value.message
      (obj ["pass_id",str value.pass_id;"configuration",value.configuration;
        "dependencies",obj (List.map (fun (key,value) -> key,str value) value.dependencies)]) in
    "error",[{Diagnostic.code="pipeline_no_candidate";message=value.message;path=None}],exception_value
  | G.Unsupported value ->
    let message=G.format_error value in
    "error",[{Diagnostic.code="synthetic_unsupported";message;path=None}],
      exception_json "biocompiler.errors" "UnsupportedBehaviorError" message (obj [])
  | value -> raise value
let resource_error state diagnostic =
  (* This mode runs only fixed trusted native providers, so their resource-code
     convention is authoritative. Resource limits in transitive leaf codecs and
     composition/checker libraries must close the session too; maintaining a
     partial list would incorrectly retain authority after a new leaf limit.
     Work exhaustion still uses the actual ancestor exception identity. *)
  W.is_exhaustion state.work diagnostic ||
  String.ends_with ~suffix:"_limit" diagnostic.Diagnostic.code ||
  List.mem diagnostic.code ["request_too_large";"response_too_large";
    "string_too_large";"number_too_large";"invalid_work_budget"]
let handle_frame (state:t) raw =
  try
    require (not state.closed && state.pending=Some (String.length raw))
      "pipeline_session_frame" "Session frame body does not match its reservation.";
    state.pending<-None;
    let request,payload,nodes=decode state raw in
    if request.operation="hello" then
      let result=hello state payload nodes (String.length raw) in
      publish state ~status:"ok" ~result ~diagnostics:[] ~exception_value:Json.Null
    else (
      let status,result,diagnostics,exception_value=
        try "ok",dispatch state request.operation payload,[],Json.Null with
        | Diagnostic.Error diagnostic when resource_error state diagnostic -> raise (Diagnostic.Error diagnostic)
        | (Diagnostic.Error _ | M.No_candidate_found _ | G.Unsupported _) as cause ->
          let status,diagnostics,exception_value=logical_error cause in status,Json.Null,diagnostics,exception_value in
      publish state ~status ~result ~diagnostics ~exception_value)
  with _ -> abort state
